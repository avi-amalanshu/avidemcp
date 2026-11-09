"""ffmpeg discovery and execution: the only place a subprocess is spawned.

exe()       --> binary: $AVIDEMCP_FFMPEG > ffmpeg on PATH > imageio-ffmpeg bundle
filters()   --> names of the filters that binary supports
run(args)   --> awaits ffmpeg; -progress out_time_us / total --> prog(fraction)
part(prog)  --> maps one pass's [0, 1] progress into a slice of a multi-pass job
"""

import os
import re
import shutil
import subprocess
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import cache

import anyio
import imageio_ffmpeg
from anyio.abc import ByteReceiveStream
from anyio.streams.text import TextReceiveStream

Prog = Callable[[float], Awaitable[None]]


class FFError(RuntimeError):
    """ffmpeg exited non-zero; the message carries its stderr tail."""


@cache
def exe() -> str:
    """Resolve the ffmpeg binary once: env override, then PATH, then the pip bundle."""
    return os.environ.get("AVIDEMCP_FFMPEG") or shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


@cache
def filters() -> frozenset[str]:
    """Filter names compiled into exe(), parsed from `ffmpeg -filters` rows like ' TSC name  V->V  ...'."""
    out = subprocess.run([exe(), "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return frozenset(re.findall(r"^\s*\S{2,3}\s+(\w+)\s+\S+->\S+", out, re.M))


def part(prog: Prog | None, lo: float, hi: float) -> Prog | None:
    """Rescale a pass's progress f in [0, 1] to lo + (hi - lo) f of the whole job."""
    if prog is None:
        return None

    async def sub(f: float) -> None:
        await prog(lo + (hi - lo) * f)

    return sub


async def lines(stream: ByteReceiveStream) -> AsyncIterator[str]:
    """Yield decoded text lines from a byte stream as they arrive."""
    buf = ""
    async for chunk in TextReceiveStream(stream, errors="replace"):
        buf += chunk
        *done, buf = buf.split("\n")
        for line in done:
            yield line
    if buf:
        yield buf


async def run(args: list[str], total: float = 0.0, prog: Prog | None = None, cwd: str | None = None) -> None:
    """Run `ffmpeg <args>` to completion.

    cmd = exe -hide_banner -nostdin -y -nostats -v error -progress pipe:1 <args>
    stdout carries progress blocks; out_time_us / total seconds --> prog(f), f increasing in [0, 1].
    stderr (errors only) is drained concurrently into a bounded tail, so no pipe deadlock.
    cancelling the caller kills ffmpeg (anyio Process.aclose).

    Raises:
        FFError: on a non-zero exit, with the last stderr lines.
    """
    cmd = [exe(), "-hide_banner", "-nostdin", "-y", "-nostats", "-v", "error", "-progress", "pipe:1", *args]
    tail: deque[str] = deque(maxlen=25)

    async def track() -> None:
        last = 0.0
        async for line in lines(proc.stdout):
            key, _, val = line.partition("=")
            if prog and total > 0 and key == "out_time_us" and val.isdigit():
                f = min(int(val) / 1e6 / total, 1.0)
                if f > last:
                    last = f
                    await prog(f)

    async def drain() -> None:
        async for line in lines(proc.stderr):
            tail.append(line)

    async with await anyio.open_process(cmd, cwd=cwd) as proc:
        async with anyio.create_task_group() as tg:
            tg.start_soon(track)
            tg.start_soon(drain)
        code = await proc.wait()
    if code:
        raise FFError(f"ffmpeg exited {code}:\n" + "\n".join(tail))
