"""MCP surface: thin async tools over the engines, served on stdio.

each tool: resolve paths -> run an engine (PyAV in a worker thread, ffmpeg as a subprocess)
-> return {output, ...facts}. Failures surface as ToolError carrying the cause's message,
because mcp 2.x hides the text of any other exception from the client.
"""

import functools
import math
from pathlib import Path
from typing import Annotated, Any, Literal

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver import Context, Image
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from . import jobs, media, packets, paths, sheet
from .ops import Cut, Op, Sound, Speed, Trim

GUIDE = """\
Video editing and datamoshing on local files. Every tool reads `input` and writes a new file
(never the input); omit `output` for <stem>.<op>.<ext> beside it. Times are in seconds.

Datamosh: prepare -> probe (I-frame times) -> drop_iframes and/or repeat_pframes -> preview ->
bake. timing="keep" (default) keeps the duration and the audio in sync; "shift" is the classic
behaviour (drops shorten, repeats insert, audio is removed).

Edits: trim (keep a range), cut (remove a range), speed, reverse, or render(ops=[...]) to chain
them (plus crop and scale) in one encode. concat joins clips, each with its own ops, and returns
the junction times to hand to prepare for a transition mosh. mode="copy" on trim/cut/speed skips
re-encoding. preview shows any result.
"""

mcp = MCPServer("avidemcp", instructions=GUIDE)

Timing = Annotated[Literal["keep", "shift"], Field(description="keep: duration and audio sync preserved; shift: classic, clip length changes and audio is dropped")]
Mode = Annotated[Literal["exact", "copy"], Field(description="exact: frame-accurate re-encode to H.264; copy: lossless, no re-encode")]
Out = Annotated[str | None, Field(description="output file; omit for <input stem>.<op>.<ext> beside the input")]
Crf = Annotated[int, Field(ge=0, le=51, description="H.264 quality of re-encodes: lower is better, 18 is visually lossless")]


def tool(**kw):
    """Register an async tool whose failures become ToolErrors the client can read."""

    def deco(fn):
        @functools.wraps(fn)
        async def safe(*a, **k):
            try:
                return await fn(*a, **k)
            except ToolError:
                raise
            except Exception as e:
                raise ToolError(f"{type(e).__name__}: {e}") from e

        mcp.tool(**kw)(safe)
        return fn

    return deco


def bg(fn, *args):
    """Run a blocking (PyAV) call in a worker thread."""
    return anyio.to_thread.run_sync(functools.partial(fn, *args))


def report(ctx: Context):
    """Progress callback: fraction in [0, 1] --> MCP progress notification (no-op if not requested)."""

    async def send(f: float) -> None:
        await ctx.report_progress(f, 1.0)

    return send


async def done(dst: Path, **extra) -> dict[str, Any]:
    """Result payload: output path, its facts, and op-specific details."""
    m = await bg(media.read, dst)
    return {"output": m.path, **media.facts(m), **extra}


async def rendered(input: str, ops: list[Op], crf: int, output: str | None, tag: str, ctx: Context) -> dict[str, Any]:
    """Shared body of every re-encoding edit: one jobs.render pass into an MP4."""
    src = paths.source(input)
    dst = paths.target(src, output, tag, ".mp4")
    await jobs.render(await bg(media.read, src), ops, dst, crf, report(ctx))
    return await done(dst)


async def copied(input: str, output: str | None, tag: str, op, lo: float, hi: float, snap: bool) -> dict[str, Any]:
    """Shared body of copy-mode trim/cut: packet plan + audio warp, remuxed into the input's container."""
    src = paths.source(input)
    dst = paths.target(src, output, tag)
    idx = await bg(packets.index, src)
    plan, warp = op(idx, packets.base(idx), lo, hi, snap)
    await bg(packets.write, src, dst, plan, warp)
    end = packets.extent(idx, packets.base(idx))[1]
    return await done(dst, kept=[[round(a, 3), round(min(b, end), 3)] for a, b, _ in warp])


@tool()
async def probe(input: str) -> dict[str, Any]:
    """Describe a media file: container, duration, video/audio streams, frame count and the times
    of its I-frames (keyframes). Use it to choose where to drop I-frames or repeat P-frames."""
    src = paths.source(input)
    m, idx = await bg(media.read, src), await bg(packets.index, src)
    ks = packets.keys(idx)
    return {"path": m.path, "format": m.format, **media.facts(m), "frames": len(idx.pkts), "keyframes": ks[:500], "keyframe_count": len(ks)}


@tool(structured_output=False)
async def preview(
    input: str,
    start: Annotated[float, Field(ge=0)] = 0.0,
    end: float | None = None,
    count: Annotated[int, Field(ge=1, le=64)] = 12,
    cols: Annotated[int, Field(ge=1, le=16)] = 4,
    width: Annotated[int, Field(ge=160, le=4096, description="total sheet width in px")] = 1280,
) -> list:
    """Look at a clip: one PNG contact sheet of `count` frames evenly spaced over [start, end]
    seconds, row-major, plus their timestamps. Decoding starts at the keyframe before `start`,
    so moshed clips look exactly as they will play."""
    data, times = await bg(sheet.make, paths.source(input), start, end, count, cols, width)
    return [Image(data=data, format="png"), "tiles (row-major) at: " + ", ".join(f"{t:.2f}s" for t in times)]


@tool()
async def prepare(
    input: str,
    ctx: Context,
    keyframes: Annotated[Literal["scene", "none"] | list[float], Field(description='"scene": I-frames at detected hard cuts; "none": first frame only; or a list of times')] = "scene",
    quality: Annotated[int, Field(ge=1, le=31, description="mpeg4 qscale: lower is better")] = 3,
    threshold: Annotated[float, Field(gt=0, lt=1, description="scene-cut sensitivity: lower finds more cuts")] = 0.3,
    intra_penalty: Annotated[int, Field(ge=0, le=1_000_000, description="how long a moshed picture survives: 0 = faithful encode, 300-1000 = strong hold, 3000+ = new content only as ghostly residuals")] = 0,
    output: Out = None,
) -> dict[str, Any]:
    """Make a datamosh-ready copy: MPEG-4 Part 2 video (no B-frames, constant frame rate) in MKV
    whose only I-frames are frame 0 and the ones you ask for. Dropping an I-frame at a scene cut
    later makes the next shot's motion drag the previous shot's pixels. The encoder repaints flat
    areas (snow, sky) with fresh intra blocks, erasing a mosh within frames; intra_penalty
    discourages that. HDR (iPhone HLG/PQ) is tone-mapped to SDR; audio is carried over."""
    src = paths.source(input)
    dst = paths.target(src, output, "prep", ".mkv")
    await jobs.prepare(await bg(media.read, src), dst, keyframes, quality, threshold, intra_penalty, report(ctx))
    return await done(dst, keyframes=packets.keys(await bg(packets.index, dst)))


@tool()
async def drop_iframes(
    input: str,
    start: Annotated[float, Field(ge=0)] = 0.0,
    end: float | None = None,
    timing: Timing = "keep",
    output: Out = None,
) -> dict[str, Any]:
    """Datamosh by deleting the I-frames (keyframes) presented in [start, end) seconds while keeping
    the P-frames that predict from them, so later motion smears the old picture. The first frame
    always stays. Needs a prepared clip (no B-frames). Writes MKV; bake it for a normal MP4."""
    src = paths.source(input)
    dst = paths.target(src, output, "drop", ".mkv")
    idx = await bg(packets.index, src)
    plan = packets.drop(idx, packets.base(idx), start, math.inf if end is None else end, timing == "shift")
    gone = sorted(set(range(len(idx.pkts))) - {s.i for s in plan})
    if not gone:
        raise ToolError(f"no I-frames in [{start}, {end}) besides the first frame; probe lists keyframe times and prepare can add some")
    await bg(packets.write, src, dst, plan, packets.KEEP if timing == "keep" else packets.MUTE)
    return await done(dst, dropped=[round(packets.secs(idx, idx.pkts[i].pts), 3) for i in gone])


@tool()
async def repeat_pframes(
    input: str,
    at: Annotated[float, Field(ge=0)],
    times: Annotated[int, Field(ge=2, le=10000, description="total plays of the run, including the original")] = 30,
    span: Annotated[int, Field(ge=1, le=1000, description="consecutive P-frames in the repeated run")] = 1,
    timing: Timing = "keep",
    output: Out = None,
) -> dict[str, Any]:
    """Datamosh bloom: replay the P-frame at `at` seconds (or a run of `span` P-frames) `times`
    times in total, re-applying its motion so the picture smears and blooms. keep: the copies
    overwrite the frames that follow; shift: they are inserted (longer clip, audio dropped). If
    `at` lands on an I-frame the next P-frame is used. Needs a prepared clip."""
    src = paths.source(input)
    dst = paths.target(src, output, "bloom", ".mkv")
    idx = await bg(packets.index, src)
    plan, k = packets.repeat(idx, packets.base(idx), at, times, span, timing == "shift")
    await bg(packets.write, src, dst, plan, packets.KEEP if timing == "keep" else packets.MUTE)
    return await done(dst, frame=round(packets.secs(idx, idx.pkts[k].pts), 3))


@tool()
async def bake(input: str, ctx: Context, crf: Crf = 18, output: Out = None) -> dict[str, Any]:
    """Render a moshed (or any) clip to an ordinary H.264/AAC MP4 at constant frame rate,
    freezing the glitches into real pixels so every player shows the same thing."""
    return await rendered(input, [], crf, output, "bake", ctx)


@tool()
async def trim(
    input: str,
    ctx: Context,
    start: Annotated[float, Field(ge=0)] = 0.0,
    end: float | None = None,
    mode: Mode = "exact",
    snap: bool = True,
    crf: Crf = 18,
    output: Out = None,
) -> dict[str, Any]:
    """Keep only [start, end) seconds. exact: frame-accurate, re-encoded to H.264 MP4. copy:
    lossless and instant like Avidemux's copy mode; the start snaps back to the previous
    keyframe, while snap=false starts exactly at `start` on frames whose references are gone."""
    if mode == "exact":
        return await rendered(input, [Trim(op="trim", start=start, end=end)], crf, output, "trim", ctx)
    return await copied(input, output, "trim", packets.trim, start, math.inf if end is None else end, snap)


@tool()
async def cut(
    input: str,
    start: Annotated[float, Field(ge=0)],
    end: Annotated[float, Field(gt=0)],
    ctx: Context,
    mode: Mode = "exact",
    snap: bool = True,
    crf: Crf = 18,
    output: Out = None,
) -> dict[str, Any]:
    """Remove [start, end) seconds and join the rest. exact: frame-accurate re-encode. copy:
    lossless; playback resumes at the next keyframe at or after `end` (so a little more is
    removed), while snap=false resumes exactly at `end` on P-frames that then predict from the
    frame before `start`: the classic Avidemux copy-mode mosh."""
    if mode == "exact":
        return await rendered(input, [Cut(op="cut", start=start, end=end)], crf, output, "cut", ctx)
    return await copied(input, output, "cut", packets.cut, start, end, snap)


@tool()
async def speed(
    input: str,
    factor: Annotated[float, Field(ge=0.01, le=100, description="2 = twice as fast, 0.5 = half speed")],
    ctx: Context,
    audio: Sound = "pitch",
    mode: Mode = "exact",
    crf: Crf = 18,
    output: Out = None,
) -> dict[str, Any]:
    """Change playback speed. audio: pitch keeps the pitch, tape lets it follow the speed, none
    drops it. exact re-encodes at the source frame rate (frames dropped or repeated); copy keeps
    every video packet untouched and only rescales timestamps (the frame rate changes; the audio
    is still re-encoded)."""
    if mode == "exact":
        return await rendered(input, [Speed(op="speed", factor=factor, audio=audio)], crf, output, "speed", ctx)
    src = paths.source(input)
    dst = paths.target(src, output, "speed")
    await jobs.retime(await bg(media.read, src), dst, factor, audio, report(ctx))
    return await done(dst)


@tool()
async def reverse(
    input: str,
    ctx: Context,
    chunk: Annotated[float | None, Field(gt=0.2, description="seconds reversed at a time; default fits ~1 GiB of frames")] = None,
    crf: Crf = 18,
    output: Out = None,
) -> dict[str, Any]:
    """Play a clip backwards, video and audio. Works through chunks, so long or 4K clips never
    need every frame in RAM. Output is H.264 MP4."""
    src = paths.source(input)
    dst = paths.target(src, output, "rev", ".mp4")
    await jobs.reverse(await bg(media.read, src), dst, crf, chunk, report(ctx))
    return await done(dst)


class Clip(BaseModel):
    """One input of concat and the ops it runs before joining."""

    input: str
    ops: list[Op] = Field(default_factory=list)


@tool()
async def concat(
    clips: Annotated[list[Clip], Field(min_length=1)],
    ctx: Context,
    width: Annotated[int | None, Field(gt=0, multiple_of=2)] = None,
    height: Annotated[int | None, Field(gt=0, multiple_of=2)] = None,
    crf: Crf = 18,
    output: Out = None,
) -> dict[str, Any]:
    """Join clips end to end in ONE encode, like Avidemux's Append. Each clip first runs its own
    ops (trim, cut, speed, reverse, crop, scale), then is fitted to width x height (scaled to
    cover, center-cropped; default: the first clip's size after its ops), the first clip's frame
    rate and 48 kHz stereo audio (silence for clips without). Returns `junctions`: the times where
    each later clip starts, i.e. where prepare(keyframes=[...]) should put the I-frames that a
    transition mosh drops. A boomerang is [{"input": x}, {"input": x, "ops": [{"op": "reverse"}]}]."""
    if (width is None) != (height is None):
        raise ToolError("give both width and height, or neither")
    srcs = [paths.source(c.input) for c in clips]
    dst = paths.target(srcs[0], output, "concat", ".mp4")
    parts = [(await bg(media.read, s), c.ops) for s, c in zip(srcs, clips)]
    cuts = await jobs.concat(parts, dst, (width, height) if width else None, crf, report(ctx))
    return await done(dst, junctions=[round(t, 4) for t in cuts])


@tool()
async def render(input: str, ops: list[Op], ctx: Context, crf: Crf = 18, output: Out = None) -> dict[str, Any]:
    """Apply a chain of edits in ONE decode/encode pass, so no quality is lost between steps.
    ops run in order, each on the timeline the previous one produced, e.g.
    [{"op": "trim", "start": 1, "end": 5}, {"op": "speed", "factor": 0.5}, {"op": "reverse"}].
    reverse here buffers its frames in RAM: trim long clips first or use the reverse tool."""
    return await rendered(input, ops, crf, output, "render", ctx)


def main() -> None:
    """Console entry point: serve on stdio."""
    mcp.run()
