"""Jobs that run ffmpeg to produce a file.

scenes  --> hard-cut times from ffmpeg's scene score (one cheap decode at 320 px)
prepare --> mosh-ready MPEG-4 Part 2 in MKV: no B-frames, CFR, I-frames only where asked
render  --> one decode + filtergraph + H.264/AAC encode (bake = render with no ops)
concat  --> several inputs, each with its own ops, conformed and joined in one encode
retime  --> lossless speed change: video packets untouched, timestamps scaled; audio re-encoded
reverse --> chunked: near-lossless segments -> each reversed -> concatenated last to first
"""

import re
import tempfile
from pathlib import Path

import anyio

from . import ff, graph, packets
from .ff import Prog, part
from .graph import num
from .media import Media
from .ops import Op, Sound

AAC = ["-c:a", "aac", "-b:a", "192k"]
COPYABLE = {"aac", "mp3", "opus", "vorbis", "flac", "ac3", "eac3", "alac"}


def h264(crf: int) -> list[str]:
    return ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p"]


def mux(dst: Path) -> list[str]:
    """Container flags: mp4/mov put their index up front."""
    return ["-movflags", "+faststart"] if dst.suffix.lower() in {".mp4", ".mov", ".m4v"} else []


def sound(m: Media) -> list[str]:
    """Carry audio into an mkv: stream copy when mkv holds the codec, else AAC."""
    if not m.audio:
        return []
    keep = m.audio.codec in COPYABLE or m.audio.codec.startswith("pcm_")
    return ["-map", f"0:{m.audio.index}", *(["-c:a", "copy"] if keep else AAC)]


async def scenes(m: Media, threshold: float, prog: Prog | None = None) -> list[float]:
    """Times (s) of frames whose ffmpeg scene score exceeds threshold."""
    with tempfile.TemporaryDirectory() as tmp:
        vf = f"scale=320:-2,select='gt(scene,{num(threshold)})',metadata=print:file=cuts.txt"
        await ff.run(["-i", m.path, "-map", f"0:{m.video.index}", "-vf", vf, "-f", "null", "-"], m.duration, prog, cwd=tmp)
        log = Path(tmp) / "cuts.txt"
        return [float(t) for t in re.findall(r"pts_time:([\d.]+)", log.read_text())] if log.exists() else []


async def prepare(m: Media, dst: Path, keys: str | list[float], q: int, threshold: float, penalty: int = 0, prog: Prog | None = None) -> list[float]:
    """Re-encode m into mosh-ready MPEG-4 Part 2; returns the times given extra I-frames.

    keys: "scene" = I-frames at detected hard cuts | "none" = first frame only | [times]
    video: [tone-map] -> fps=nominal rate -> yuv420p -> mpeg4 -q:v q, -bf 0, unbounded GOP
    (-strict experimental lifts the encoder's 600-frame cap) and its own scene detection off,
    so the only I-frames are frame 0 and the forced ones.
    penalty: -intra_penalty; the encoder otherwise intra-codes flat areas (low variance) even
    when nothing moved, and every intra block repaints a moshed picture with fresh pixels.
    """
    scan = keys == "scene"
    times = await scenes(m, threshold, part(prog, 0, 0.25)) if scan else [] if keys == "none" else sorted(keys)
    force = ["-force_key_frames", ",".join(num(max(t - 1e-3, 0)) for t in times)] if times else []  # 1 ms early: rounded times must not skip their frame
    vf = [*graph.head(m), f"fps={m.video.rate}", "format=yuv420p"]
    args = ["-i", m.path, "-map", f"0:{m.video.index}", *sound(m), "-vf", ",".join(vf), "-c:v", "mpeg4", "-q:v", str(q), "-bf", "0"]
    args += ["-g", "1000000", "-strict", "experimental", "-sc_threshold", "1000000000", "-intra_penalty", str(penalty), *force, str(dst)]
    await ff.run(args, m.duration, part(prog, 0.25 if scan else 0, 1))
    return times


async def render(m: Media, ops: list[Op], dst: Path, crf: int, prog: Prog | None = None) -> None:
    """Decode m once, run ops as one filtergraph, encode H.264 (+AAC) into dst."""
    text, pad = graph.graph(ops, m)
    audio = ["-map", f"[{pad.a}]", *AAC] if pad.a else []
    await ff.run(["-i", m.path, "-filter_complex", text, "-map", f"[{pad.v}]", *h264(crf), *audio, *mux(dst), str(dst)], pad.dur, prog)


async def concat(parts: list[tuple[Media, list[Op]]], dst: Path, size: tuple[int, int] | None, crf: int, prog: Prog | None = None) -> list[float]:
    """Join inputs (each with its own ops) in one decode/encode pass; returns the junction times."""
    text, pad, cuts = graph.join(parts, size)
    ins = [arg for m, _ in parts for arg in ("-i", m.path)]
    await ff.run([*ins, "-filter_complex", text, "-map", "[vout]", "-map", "[aout]", *h264(crf), *AAC, *mux(dst), str(dst)], pad.dur, prog)
    return cuts


async def retime(m: Media, dst: Path, factor: float, audio: Sound, prog: Prog | None = None) -> None:
    """Lossless speed change: -itsscale scales the video timestamps by 1/factor while its packets
    are stream-copied; audio (unless dropped) runs through render's tempo filters, re-encoded."""
    keep = m.audio is not None and audio != "none"
    af = (graph.tempo(factor) if audio == "pitch" else graph.tape(factor, m.audio.rate)) if keep else []
    sound_ = ["-map", f"0:{m.audio.index}", "-af", ",".join(af), *AAC] if keep else []
    args = [f"-itsscale:{m.video.index}", num(1 / factor), "-i", m.path, "-map", f"0:{m.video.index}", "-c:v", "copy"]
    await ff.run([*args, *sound_, *mux(dst), str(dst)], m.duration / factor, prog)


def stride(m: Media) -> float:
    """Default reverse chunk (s): what keeps reverse's buffer near LIMIT / 2, clamped to [1, 10]."""
    rate = m.video.width * m.video.height * 1.5 * float(m.video.rate)
    return min(10.0, max(1.0, graph.LIMIT / 2 / rate))


async def reverse(m: Media, dst: Path, crf: int, chunk: float | None, prog: Prog | None = None) -> None:
    """Reverse m with bounded memory.

    1. one decode -> near-lossless H.264 segments of `chunk` s (keyframes forced on the
       boundaries so the segment muxer splits exactly there)
    2. each segment reversed on its own -> final H.264 settings
    3. audio padded/trimmed to the video length, then reversed in one pass (audio is small)
    4. reversed segments concatenated last-to-first by stream copy; reversed audio muxed in
    """
    chunk = chunk or stride(m)
    src = await anyio.to_thread.run_sync(packets.index, m.path)
    t0, t1 = packets.extent(src, packets.base(src))
    vdur = t1 - t0
    with tempfile.TemporaryDirectory(dir=dst.parent, prefix=".avidemcp-") as tmp:
        vf = [*graph.head(m), f"fps={m.video.rate}", "format=yuv420p"]
        split = ["-force_key_frames", f"expr:gte(t,n_forced*{num(chunk)})", "-f", "segment", "-segment_time", num(chunk), "-reset_timestamps", "1"]
        await ff.run(["-i", m.path, "-map", f"0:{m.video.index}", "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "8", *split, "s%05d.mkv"], vdur, part(prog, 0, 0.3), cwd=tmp)
        segs = sorted(Path(tmp).glob("s*.mkv"))
        for k, s in enumerate(segs):
            await ff.run(["-i", s.name, "-vf", "reverse", *h264(crf), f"r{s.name}"], chunk, part(prog, 0.3 + 0.6 * k / len(segs), 0.3 + 0.6 * (k + 1) / len(segs)), cwd=tmp)
        (Path(tmp) / "list.txt").write_text("".join(f"file 'r{s.name}'\n" for s in reversed(segs)))
        ins, maps = ["-f", "concat", "-safe", "0", "-i", "list.txt"], ["-map", "0:v"]
        if m.audio:
            af = f"apad=whole_dur={num(vdur)},atrim=end={num(vdur)},areverse"
            await ff.run(["-i", m.path, "-map", f"0:{m.audio.index}", "-af", af, *AAC, "a.m4a"], vdur, part(prog, 0.9, 0.97), cwd=tmp)
            ins, maps = [*ins, "-i", "a.m4a"], [*maps, "-map", "1:a"]
        await ff.run([*ins, *maps, "-c", "copy", *mux(dst), str(dst)], vdur, part(prog, 0.97, 1), cwd=tmp)
