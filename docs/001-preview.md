# preview

> Look at a clip: one PNG contact sheet of evenly spaced frames over [start, end], with their times.

Tree: `001` < `00` Inspect < `0` Inspect and encode < root ([AGENTS.md](../AGENTS.md))

## Call

```
preview {"input": "clip.mp4"}
preview {"input": "clip.mp4", "start": 4.5, "end": 6.5, "count": 16, "cols": 4}
-> image, then text: "tiles (row-major) at: 4.50s, 4.63s, 4.77s, ..."
```

| Argument | Default | Meaning |
|---|---|---|
| `start` | 0 | time of the first tile |
| `end` | end of clip | time of the last tile |
| `count` | 12 (1-64) | number of tiles |
| `cols` | 4 (1-16) | tiles per row |
| `width` | 1280 (160-4096) | sheet width in pixels; each tile is `width / cols` wide |

Each tile is the first frame at or after its target time, shown in display orientation. The text
line gives the real frame times; use those times in other tools.

Decoding starts at the I-frame at or before `start` and runs forward, so the tiles show what a
player shows, including in the output of `drop_iframes` and `repeat_pframes`.

## When and how

- After every step that changes the picture. Result fields can't show whether a crop cut off the
  subject or an effect reads well.
- Look at the whole clip first, then narrow in. 12-16 tiles over 0.5-2 s show frame-level change;
  at 30 fps, a 0.4 s window with `count` 12 shows every frame.
- To compare two files, preview both over the same window.
- For more detail, use fewer columns or a wider sheet (`cols` 2, `width` 1600).
- To find fast motion, look for the neighbouring tiles that differ most in a dense window.
- To check a loop, preview 0 to 0.1 s with `count` 2, then the last 0.1 s; the first and last tiles
  should match.
