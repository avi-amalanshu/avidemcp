"""Media facts via PyAV (no ffprobe needed).

read(path)  --> Media: container, duration, first video and audio stream facts
video(c)    --> first real video stream of an open container (cover art excluded)
facts(m)    --> compact JSON-able summary for tool results
"""

import os
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av

HDR = {16: "pq", 18: "hlg"}  # AVColorTransferCharacteristic codes


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


def read(path: str | Path) -> Media:
    """Collect the facts every tool needs; decodes one frame to learn the display rotation."""
    with av.open(str(path)) as c:
        v, a = video(c), next(iter(c.streams.audio), None)
        dur = c.duration / av.time_base if c.duration else 0.0
        return Media(str(Path(path).resolve()), c.format.name, dur, os.path.getsize(path), v and _video(c, v), a and _audio(a))


def _video(c: av.container.InputContainer, v: av.VideoStream) -> Video:
    """Stream facts; rate is the nominal (guessed) rate, which survives timestamp gaps."""
    cc = v.codec_context
    first = next(c.decode(v), None)
    rate = v.guessed_rate or v.average_rate or Fraction(25)
    return Video(v.index, cc.name, cc.width, cc.height, rate, bool(cc.has_b_frames), HDR.get(cc.color_trc), int(first.rotation) if first else 0)


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
