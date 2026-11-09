"""Compressed-domain engine: edit demuxed packets without decoding.

index(path) --> Src: video packet table + nominal frame step
ops         --> pure functions (Src, Plan, ...) -> Plan, plus a Warp when audio must move
write(...)  --> one demux pass: video emitted per plan, audio re-timed per warp

A Plan is a tuple of Slots: source video packet i emitted at (pts, dts), in source video
time-base ticks. A Warp re-times audio as windows (lo, hi, shift) in seconds: an audio packet
at t in [lo, hi) is emitted at t - shift, all other audio is dropped. KEEP passes audio
through unchanged; MUTE drops it.
"""

import math
from fractions import Fraction
from pathlib import Path
from typing import NamedTuple

import av

from .media import video


class Pkt(NamedTuple):
    pts: int
    dts: int | None
    key: bool


class Slot(NamedTuple):
    i: int
    pts: int
    dts: int | None


class Src(NamedTuple):
    pkts: tuple[Pkt, ...]
    tb: Fraction
    step: Fraction
    bframes: bool


Plan = tuple[Slot, ...]
Warp = tuple[tuple[float, float, float], ...]
KEEP: Warp = ((-math.inf, math.inf, 0.0),)
MUTE: Warp = ()


def index(path: str | Path) -> Src:
    """Demux the first video stream once (no decoding) into a packet table.

    step = one frame in time-base ticks at the stream's nominal (guessed) rate, kept exact
    (33.33 ticks at 30 fps in a 1 ms time base); timestamps are rounded only when emitted.
    """
    with av.open(str(path)) as c:
        v = video(c)
        if v is None:
            raise ValueError(f"{path}: no video stream")
        pkts = tuple(_pkt(p) for p in c.demux(v) if p.size)
        rate = v.guessed_rate or v.average_rate
        if not pkts or not rate:
            raise ValueError(f"{path}: no video packets or unknown frame rate")
        return Src(pkts, v.time_base, 1 / (rate * v.time_base), bool(v.codec_context.has_b_frames))


def _pkt(p: av.Packet) -> Pkt:
    if p.pts is None and p.dts is None:
        raise ValueError("video packet without timestamps")
    return Pkt(p.dts if p.pts is None else p.pts, p.dts, p.is_keyframe)


def secs(src: Src, ticks: int) -> float:
    return float(ticks * src.tb)


def base(src: Src) -> Plan:
    """Identity plan: every packet at its own timestamps."""
    return tuple(Slot(i, p.pts, p.dts) for i, p in enumerate(src.pkts))


def keys(src: Src) -> list[float]:
    """Presentation times (s) of the keyframes (I-frames)."""
    return [round(secs(src, p.pts), 4) for p in src.pkts if p.key]


def dts(s: Slot) -> int:
    return s.pts if s.dts is None else s.dts


def rebase(plan: Plan, d: int) -> Plan:
    """Shift every timestamp by -d ticks."""
    return tuple(Slot(s.i, s.pts - d, None if s.dts is None else s.dts - d) for s in plan)


def extent(src: Src, plan: Plan) -> tuple[float, float]:
    """Presented time range [t0, t1) of a plan, in seconds."""
    return secs(src, min(s.pts for s in plan)), secs(src, max(s.pts for s in plan) + src.step)


def ordered(src: Src) -> None:
    """Require decode order == presentation order (no B-frames), as datamosh ops assume."""
    if src.bframes:
        raise ValueError("the input has B-frames; run prepare first to get a mosh-ready I/P-only clip")


def restamp(src: Src, plan: Plan) -> Plan:
    """Re-time a plan as gapless CFR from its first pts: slot k at pts0 + k * step."""
    ordered(src)
    t0 = plan[0].pts if plan else 0
    return tuple(Slot(s.i, round(t0 + k * src.step), round(t0 + k * src.step)) for k, s in enumerate(plan))


def drop(src: Src, plan: Plan, lo: float, hi: float, shift: bool) -> Plan:
    """Remove keyframes presented in [lo, hi) seconds, except the plan's first packet.

    keep timing (shift=False): survivors keep their timestamps, so each removed frame is a hold.
    shift timing: survivors are restamped gapless and the clip gets shorter.
    """
    ordered(src)
    first = plan[0].i if plan else -1
    out = tuple(s for s in plan if not (src.pkts[s.i].key and s.i != first and lo <= secs(src, s.pts) < hi))
    return restamp(src, out) if shift else out


def repeat(src: Src, plan: Plan, at: float, times: int, span: int, shift: bool) -> tuple[Plan, int]:
    """Play the run of `span` P-frames starting at `at` seconds `times` times in total.

    k   = first non-key slot presented at or after `at` (repeating a keyframe only freezes)
    run = plan[k : k + span], cut short at the next keyframe
    keep timing: the copies overwrite the slots that follow, so duration is unchanged.
    shift timing: the copies are inserted and the plan restamped, so the clip gets longer.
    Returns the new plan and k.
    """
    ordered(src)
    k = next((j for j, s in enumerate(plan) if secs(src, s.pts) >= at and not src.pkts[s.i].key), None)
    if k is None:
        raise ValueError(f"no P-frame at or after {at}s")
    run = plan[k : k + span]
    run = run[: next((j for j, s in enumerate(run) if src.pkts[s.i].key), len(run))]
    reps = run * times
    if shift:
        return restamp(src, plan[:k] + reps + plan[k + len(run) :]), k
    slots = plan[k : k + len(reps)]
    return plan[:k] + tuple(Slot(r.i, s.pts, s.dts) for r, s in zip(reps, slots)) + plan[k + len(slots) :], k


def window(src: Src, plan: Plan, lo: float, hi: float, snap: bool) -> Plan:
    """Decode-order slice of plan that presents every frame in [lo, hi) seconds.

    snap: open on the last keyframe at or before that slice (clean decode, starts early);
    without snap the slice may open on a P-frame whose references are gone (a mosh cut).
    """
    inside = [j for j, s in enumerate(plan) if lo <= secs(src, s.pts) < hi]
    if not inside:
        raise ValueError(f"no frames in [{lo}, {hi})")
    a, b = inside[0], inside[-1] + 1
    if snap:
        a = max((j for j in range(a + 1) if src.pkts[plan[j].i].key), default=0)
    return plan[a:b]


def trim(src: Src, plan: Plan, lo: float, hi: float, snap: bool) -> tuple[Plan, Warp]:
    """Keep [lo, hi) seconds without decoding, rebased to start at zero; audio follows."""
    seg = window(src, plan, lo, hi, snap)
    d = min(map(dts, seg))
    return rebase(seg, d), ((*extent(src, seg), secs(src, d)),)


def cut(src: Src, plan: Plan, lo: float, hi: float, snap: bool) -> tuple[Plan, Warp]:
    """Remove [lo, hi) seconds without decoding and join what is left; audio follows.

    head = slice presenting everything before lo. tail opens on the first frame presented at or
    after hi; with snap, on the first keyframe from there on (clean decode, removes a little more).
    tail is shifted so its first dts lands one step after head's last. Without snap the tail opens
    on P-frames that now predict from head's last picture: Avidemux's accidental mosh, on purpose.
    """
    j = next((k for k, s in enumerate(plan) if secs(src, s.pts) >= hi), len(plan))
    if snap and j < len(plan):
        j = next((k for k in range(j, len(plan)) if src.pkts[plan[k].i].key), None)
        if j is None:
            raise ValueError(f"no keyframe at or after {hi}s to resume on; use snap=false or mode='exact'")
    head = window(src, plan, -math.inf, lo, True) if secs(src, min(s.pts for s in plan)) < lo else ()
    tail = plan[j:]
    if not head and not tail:
        raise ValueError("the cut removes every frame")
    dh = min(map(dts, head)) if head else 0
    h = rebase(head, dh)
    dt = dts(tail[0]) - round(max(map(dts, h)) + src.step if h else 0) if tail else 0
    warp = ((*extent(src, head), secs(src, dh)),) if head else ()
    warp += ((extent(src, tail)[0], math.inf, secs(src, dt)),) if tail else ()
    return h + rebase(tail, dt), warp


def write(path: str | Path, dst: str | Path, plan: Plan, warp: Warp) -> None:
    """Remux `path` into `dst`: video packets per plan, audio packets per warp.

    one demux pass over video + audio in stored order; a video payload is cached from its
    arrival until its last use in plan, so repeats and reordered plans still stream.
    """
    if not plan:
        raise ValueError("nothing left to write")
    last = {s.i: k for k, s in enumerate(plan)}
    with av.open(str(path)) as inp, av.open(str(dst), "w") as out:
        v = video(inp)
        a = next(iter(inp.streams.audio), None) if warp else None
        ov = out.add_stream_from_template(v)
        oa = a and out.add_stream_from_template(a)
        cache: dict[int, tuple[bytes, bool, int]] = {}
        n = k = 0
        for p in inp.demux(*(s for s in (v, a) if s is not None)):
            if not p.size:
                continue
            if a is not None and p.stream.index == a.index:
                _sound(p, oa, warp, out)
                continue
            if n in last:
                cache[n] = (bytes(p), p.is_keyframe, p.duration or 0)
            n += 1
            while k < len(plan) and plan[k].i in cache:
                s = plan[k]
                data, key, dur = cache[s.i]
                q = av.Packet(data)
                q.pts, q.dts, q.is_keyframe, q.time_base, q.stream = s.pts, s.dts, key, v.time_base, ov
                if dur:
                    q.duration = dur
                out.mux(q)
                if last[s.i] == k:
                    del cache[s.i]
                k += 1
        if k < len(plan):
            raise ValueError(f"plan needs video packet {plan[k].i} but the input has {n}")


def _sound(p: av.Packet, oa: av.AudioStream, warp: Warp, out: av.container.OutputContainer) -> None:
    """Mux one audio packet re-timed by the first warp window holding it, else drop it."""
    t = p.dts if p.pts is None else p.pts
    if t is None:
        return
    sec = float(t * p.time_base)
    for lo, hi, d in warp:
        if lo <= sec < hi:
            tick = round(d / p.time_base)
            if p.pts is not None:
                p.pts -= tick
            if p.dts is not None:
                p.dts -= tick
            p.stream = oa
            out.mux(p)
            return
