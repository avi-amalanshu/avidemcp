"""Compile decoded-domain ops into one ffmpeg filtergraph.

Pad    = labels of the graph's current video/audio outputs + duration, frame count, frame size,
         and the frame rate the output is conformed to
link   = one rule per op: (op, pad, tag, media) --> (graph lines, next pad)
branch = input k -> head (hdr tone-map) -> its ops in order
graph  = one branch -> tail (cfr at the pad's rate, yuv420p)
join   = one branch per input -> conform (size, rate, audio format) -> concat
"""

from fractions import Fraction
from functools import singledispatch
from typing import NamedTuple

from . import ff
from .media import Media
from .ops import Crop, Cut, Fps, MotionBlur, Op, Reverse, Scale, Speed, Trim

LIMIT = 2 << 30  # bytes of decoded frames reverse may buffer
TONEMAP = ["zscale=t=linear:npl=100", "format=gbrpf32le", "zscale=p=bt709", "tonemap=tonemap=hable:desat=0", "zscale=t=bt709:m=bt709:r=tv"]
MCI = "mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"  # minterpolate: motion-compensated, overlapped blocks
AUDIO = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"


class Pad(NamedTuple):
    v: str
    a: str | None
    dur: float
    frames: float
    size: tuple[int, int]
    rate: Fraction


def num(x: float) -> str:
    """Plain decimal for ffmpeg args (no exponent, no trailing zeros)."""
    return f"{x:.6f}".rstrip("0").rstrip(".")


def rational(fps: float) -> Fraction:
    """Frame rate as a fraction; 23.976, 29.97, 59.94 and 119.88 snap to the NTSC rates n * 1000/1001."""
    n = round(fps * 1.001)
    if fps < 200 and abs(fps * 1.001 - n) < 0.005 and abs(fps - n) > 0.01:
        return Fraction(n * 1000, 1001)
    return Fraction(fps).limit_denominator(1000)


def chain(src: str, filters: list[str], dst: str) -> str:
    return f"[{src}]{','.join(filters)}[{dst}]"


def tempo(f: float) -> list[str]:
    """atempo stages multiplying to f, each in [0.5, 2] (atempo drops samples above 2)."""
    out = []
    while f > 2:
        out.append("atempo=2")
        f /= 2
    while f < 0.5:
        out.append("atempo=0.5")
        f /= 0.5
    return [*out, f"atempo={num(f)}"]


def tape(f: float, rate: int) -> list[str]:
    """Speed audio like a tape: resample-free rate change, so pitch follows speed."""
    return [f"asetrate={round(rate * f)}", f"aresample={rate}"]


def head(m: Media) -> list[str]:
    """Normalising filters for the decoded source: HDR is tone-mapped to SDR bt709 when zscale exists."""
    return TONEMAP if m.video.hdr and "zscale" in ff.filters() else []


def shown(m: Media) -> tuple[int, int]:
    """Display size: coded size with width and height swapped for a quarter-turn rotation."""
    w, h = m.video.width, m.video.height
    return (h, w) if abs(m.video.rotation) % 180 == 90 else (w, h)


@singledispatch
def link(op, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    raise TypeError(f"no filter rule for {op!r}")


@link.register
def _(op: Trim, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    end = pad.dur if op.end is None else min(op.end, pad.dur)
    if op.start >= end:
        raise ValueError(f"trim [{op.start}, {op.end}) is empty on a {pad.dur:.3f}s timeline")
    rng = f"start={num(op.start)}" + ("" if op.end is None else f":end={num(end)}")
    lines = [chain(pad.v, [f"trim={rng}", "setpts=PTS-STARTPTS"], f"v{tag}")]
    if pad.a:
        lines.append(chain(pad.a, [f"atrim={rng}", "asetpts=PTS-STARTPTS"], f"a{tag}"))
    dur = end - op.start
    return lines, pad._replace(v=f"v{tag}", a=pad.a and f"a{tag}", dur=dur, frames=pad.frames * dur / pad.dur)


def halves(src: str, p: str, s: float, e: float, dst: str) -> list[str]:
    """[src] split; keep [0, s) and [e, end); concat into [dst]. p = '' for video, 'a' for audio."""
    x, y = f"{dst}x", f"{dst}y"
    kind = "v=0:a=1" if p else "v=1:a=0"
    return [
        f"[{src}]{p}split[{x}0][{y}0]",
        chain(f"{x}0", [f"{p}trim=end={num(s)}", f"{p}setpts=PTS-STARTPTS"], f"{x}1"),
        chain(f"{y}0", [f"{p}trim=start={num(e)}", f"{p}setpts=PTS-STARTPTS"], f"{y}1"),
        f"[{x}1][{y}1]concat=n=2:{kind}[{dst}]",
    ]


@link.register
def _(op: Cut, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    end = min(op.end, pad.dur)
    if op.start >= end:
        raise ValueError(f"cut [{op.start}, {op.end}) is empty on a {pad.dur:.3f}s timeline")
    if op.start <= 0 and end >= pad.dur:
        raise ValueError("the cut removes the whole timeline")
    if op.start <= 0:
        return link(Trim(op="trim", start=end), pad, tag, m)
    if end >= pad.dur:
        return link(Trim(op="trim", end=op.start), pad, tag, m)
    lines = halves(pad.v, "", op.start, end, f"v{tag}") + (halves(pad.a, "a", op.start, end, f"a{tag}") if pad.a else [])
    dur = pad.dur - (end - op.start)
    return lines, pad._replace(v=f"v{tag}", a=pad.a and f"a{tag}", dur=dur, frames=pad.frames * dur / pad.dur)


@link.register
def _(op: Speed, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    lines = [chain(pad.v, [f"setpts=PTS/{num(op.factor)}"], f"v{tag}")]
    a = None
    if pad.a and op.audio != "none":
        af = tempo(op.factor) if op.audio == "pitch" else tape(op.factor, m.audio.rate)
        lines.append(chain(pad.a, af, f"a{tag}"))
        a = f"a{tag}"
    return lines, pad._replace(v=f"v{tag}", a=a, dur=pad.dur / op.factor)


@link.register
def _(op: Reverse, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    need = pad.frames * pad.size[0] * pad.size[1] * 1.5
    if need > LIMIT:
        raise ValueError(f"reverse here would buffer ~{need / 2**30:.1f} GiB of frames; trim first or use the reverse tool")
    lines = [chain(pad.v, ["reverse"], f"v{tag}")] + ([chain(pad.a, ["areverse"], f"a{tag}")] if pad.a else [])
    return lines, pad._replace(v=f"v{tag}", a=pad.a and f"a{tag}")


@link.register
def _(op: Crop, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    w, h = pad.size
    x = (w - op.width) // 2 if op.x is None else op.x
    y = (h - op.height) // 2 if op.y is None else op.y
    if x < 0 or y < 0 or x + op.width > w or y + op.height > h:
        raise ValueError(f"crop {op.width}x{op.height} at ({x}, {y}) does not fit the {w}x{h} frame")
    return [chain(pad.v, [f"crop={op.width}:{op.height}:{x}:{y}"], f"v{tag}")], pad._replace(v=f"v{tag}", size=(op.width, op.height))


@link.register
def _(op: Scale, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    w, h = pad.size
    height = op.height or max(2, round(op.width * h / w / 2) * 2)
    return [chain(pad.v, [f"scale={op.width}:{height}", "setsar=1"], f"v{tag}")], pad._replace(v=f"v{tag}", size=(op.width, height))


@link.register
def _(op: Fps, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    r = rational(op.rate)
    vf = {"drop": f"fps={r}", "blend": f"framerate=fps={r}", "motion": f"minterpolate=fps={r}:{MCI}"}[op.method]
    return [chain(pad.v, [vf], f"v{tag}")], pad._replace(v=f"v{tag}", frames=pad.dur * r, rate=r)


@link.register
def _(op: MotionBlur, pad: Pad, tag: str, m: Media) -> tuple[list[str], Pad]:
    """Interpolate to `samples` x the output rate, average the frames the shutter spans, keep one per output frame."""
    r = pad.rate if op.rate is None else rational(op.rate)
    n = max(1, round(op.samples * op.shutter / 360))
    vf = [f"minterpolate=fps={r * op.samples}:{MCI}", f"tmix=frames={n}", f"fps={r}"]
    return [chain(pad.v, vf, f"v{tag}")], pad._replace(v=f"v{tag}", frames=pad.dur * r, rate=r)


def branch(m: Media, ops: list[Op], k: int = 0) -> tuple[list[str], Pad]:
    """Input k through its head filters and ops; labels carry k so inputs never collide."""
    pad = Pad(f"{k}:{m.video.index}", m.audio and f"{k}:{m.audio.index}", m.duration, m.duration * float(m.video.rate), shown(m), m.video.rate)
    lines = []
    if hd := head(m):
        lines.append(chain(pad.v, hd, f"hdr{k}"))
        pad = pad._replace(v=f"hdr{k}")
    for j, op in enumerate(ops):
        more, pad = link(op, pad, f"{k}_{j}", m)
        lines += more
    return lines, pad


def graph(ops: list[Op], m: Media) -> tuple[str, Pad]:
    """ops --> (-filter_complex text, final pad labelled vout / aout)."""
    lines, pad = branch(m, ops)
    lines.append(chain(pad.v, [f"fps={pad.rate}", "format=yuv420p"], "vout"))
    if pad.a:
        lines.append(chain(pad.a, ["anull"], "aout"))
    return ";".join(lines), pad._replace(v="vout", a=pad.a and "aout")


def join(parts: list[tuple[Media, list[Op]]], size: tuple[int, int] | None = None) -> tuple[str, Pad, list[float]]:
    """Concatenate inputs, each through its own branch.

    every branch is conformed to `size` (default: the first branch's size; scaled to cover, then
    center-cropped), the first branch's frame rate (after its ops) and 48 kHz stereo fltp audio (silence when a
    branch has none), then all meet in one concat filter.
    each branch is forced to exactly n = round(dur * fps) frames (fps alone emits n or n + 1
    depending on timestamp phase): clone one extra frame, trim to n; audio padded/trimmed to match.
    Returns (-filter_complex text, pad vout / aout, junctions): junctions are the start times of
    every input after the first, exact frame times by construction.
    """
    lines, t, cuts, rate = [], 0.0, [], None
    for k, (m, ops) in enumerate(parts):
        more, pad = branch(m, ops, k)
        size, rate = size or pad.size, rate or pad.rate
        w, h = size
        fps = float(rate)
        n = max(1, round(pad.dur * fps))
        end = num(n / fps)
        fit = [f"scale={w}:{h}:force_original_aspect_ratio=increase", f"crop={w}:{h}", "setsar=1", f"fps={rate}", "tpad=stop_mode=clone:stop=1", f"trim=end_frame={n}", "format=yuv420p"]
        lines += [*more, chain(pad.v, fit, f"cv{k}")]
        sound = [AUDIO, f"apad=whole_dur={end}", f"atrim=end={end}"]
        lines.append(chain(pad.a, sound, f"ca{k}") if pad.a else f"anullsrc=r=48000:cl=stereo,{','.join(sound)}[ca{k}]")
        if k:
            cuts.append(t)
        t += n / fps
    n = len(parts)
    lines.append("".join(f"[cv{k}][ca{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[vout][aout]")
    return ";".join(lines), Pad("vout", "aout", t, t * fps, size, rate), cuts
