"""Contact sheets, so a multimodal client can see frames of a clip.

make(path, start, end, count, cols, width) --> (png bytes, frame times)
targets = `count` times evenly spaced over [start, end]. decoding runs forward from the keyframe
at or before start (the only correct way to show a moshed clip) and takes the first frame at or
after each target; thumbnails follow the display rotation and tile row-major on a black grid.
"""

import math
from pathlib import Path

import av
import numpy as np

from .media import video


def thumb(f: av.VideoFrame, w: int) -> np.ndarray:
    """RGB thumbnail `w` px wide in display orientation: (h, w, 3) uint8."""
    k = (f.rotation // 90) % 4
    fw, fh = (f.height, f.width) if k % 2 else (f.width, f.height)
    h = max(2, round(w * fh / fw / 2) * 2)
    sw, sh = (h, w) if k % 2 else (w, h)
    return np.rot90(f.reformat(width=sw, height=sh, format="rgb24").to_ndarray(), k)


def grid(tiles: list[np.ndarray], cols: int) -> np.ndarray:
    """Tile equal-size images row-major, padding the last row with black."""
    rows = math.ceil(len(tiles) / cols)
    cells = tiles + [np.zeros_like(tiles[0])] * (rows * cols - len(tiles))
    return np.vstack([np.hstack(cells[r * cols : (r + 1) * cols]) for r in range(rows)])


def png(img: np.ndarray) -> bytes:
    """Encode an (h, w, 3) uint8 image as PNG with libavcodec's encoder."""
    cc = av.CodecContext.create("png", "w")
    cc.width, cc.height, cc.pix_fmt = img.shape[1], img.shape[0], "rgb24"
    frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(img), format="rgb24")
    return b"".join(bytes(p) for p in [*cc.encode(frame), *cc.encode(None)])


def make(path: str | Path, start: float = 0.0, end: float | None = None, count: int = 12, cols: int = 4, width: int = 1280) -> tuple[bytes, list[float]]:
    """Render the contact sheet; returns PNG bytes and the time of each tile (row-major)."""
    with av.open(str(path)) as c:
        v = video(c)
        v.thread_type = "AUTO"
        dur = c.duration / av.time_base if c.duration else None
        end = min((x for x in (end, dur) if x is not None), default=None)
        if end is None or start >= end:
            raise ValueError(f"empty or unknown range [{start}, {end})")
        targets = [start + (end - start) * k / max(count - 1, 1) for k in range(count)]
        if start > 0:
            c.seek(int(start / v.time_base), stream=v, backward=True)
        tiles, times, last, w = [], [], None, width // max(cols, 1) // 2 * 2
        for f in c.decode(v):
            if f.time is None:
                continue
            last = f
            while len(tiles) < count and f.time >= targets[len(tiles)] - 1e-6:
                tiles.append(thumb(f, w))
                times.append(round(f.time, 3))
            if len(tiles) == count:
                break
        if last is None:
            raise ValueError(f"no decodable frames in [{start}, {end})")
        while len(tiles) < count:
            tiles.append(thumb(last, w))
            times.append(round(last.time, 3))
    return png(grid(tiles, min(cols, count))), times
