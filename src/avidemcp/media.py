"""Media facts via PyAV (no ffprobe needed).

read(path)  --> Media: container, duration, first video and audio stream facts
video(c)    --> first real video stream of an open container (cover art excluded)
rate(v, ts) --> nominal frame rate of a video stream, checked against its frame spacing
facts(m)    --> compact JSON-able summary for tool results
"""

import os
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from itertools import islice
from pathlib import Path
from statistics import median_low

import av

HDR = {16: "pq", 18: "hlg"}  # AVColorTransferCharacteristic codes
SAMPLE = 240  # presentation times rate() looks at


@dataclass(frozen=True)
class Video:
    index: int
    codec: str
    width: int
    height: int
    rate: Fraction
    bframes: bool
    hdr: str | None
    rotation: int


@dataclass(frozen=True)
class Audio:
    index: int
    codec: str
    rate: int
    channels: int


@dataclass(frozen=True)
class Media:
    path: str
    format: str
    duration: float
    size: int
    video: Video | None
    audio: Audio | None


def video(c: av.container.InputContainer) -> av.VideoStream | None:
    """First video stream that is not an attached picture."""
    return next((s for s in c.streams.video if not s.disposition & av.stream.Disposition.attached_pic), None)


def rate(v: av.VideoStream, pts: Iterable[int]) -> Fraction | None:
    """Nominal frame rate: the stream's guessed rate, unless the frames are spaced otherwise.

    spacing = median gap between the first SAMPLE presentation times (pts, in v's time base).
    The guess is the lowest rate that fits every timestamp, so it survives dropped frames, but a
    clip mixing 1/24 s and 1/30 s gaps guesses 120. A guess more than 1.5x away from 1 / spacing
    is replaced by 1 / spacing.
    """
    t = sorted(islice(pts, SAMPLE))
    gap = median_low(b - a for a, b in zip(t, t[1:])) if len(t) > 1 else 0
    guess = v.guessed_rate or v.average_rate
    if not gap:
        return guess
    seen = 1 / (gap * v.time_base)
    return guess if guess and 2 / 3 < guess / seen < 3 / 2 else seen


def read(path: str | Path) -> Media:
    """Collect the facts every tool needs; decodes one frame to learn the display rotation."""
    with av.open(str(path)) as c:
        v, a = video(c), next(iter(c.streams.audio), None)
        dur = c.duration / av.time_base if c.duration else 0.0
        return Media(str(Path(path).resolve()), c.format.name, dur, os.path.getsize(path), v and _video(c, v), a and _audio(a))


def _video(c: av.container.InputContainer, v: av.VideoStream) -> Video:
    """Stream facts; decodes the first frame for its rotation, then rewinds to sample frame times for rate()."""
    cc = v.codec_context
    first = next(c.decode(v), None)
    c.seek(0)
    fps = rate(v, (p.pts for p in c.demux(v) if p.pts is not None)) or Fraction(25)
    return Video(v.index, cc.name, cc.width, cc.height, fps, bool(cc.has_b_frames), HDR.get(cc.color_trc), int(first.rotation) if first else 0)


def _audio(a: av.AudioStream) -> Audio:
    cc = a.codec_context
    return Audio(a.index, cc.name, cc.sample_rate, len(cc.layout.channels))


def facts(m: Media) -> dict:
    """Duration, size and stream summary of a file, for tool results."""
    v, a = m.video, m.audio
    return {
        "duration": round(m.duration, 3),
        "size": m.size,
        "video": v and {"codec": v.codec, "size": f"{v.width}x{v.height}", "fps": round(float(v.rate), 3), "bframes": v.bframes, "hdr": v.hdr, "rotation": v.rotation},
        "audio": a and {"codec": a.codec, "rate": a.rate, "channels": a.channels},
    }
