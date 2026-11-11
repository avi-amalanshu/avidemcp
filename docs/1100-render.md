# render

> Run a chain of ops (trim, cut, speed, reverse, crop, scale) on one file in a single decode and encode.

Tree: `1100` < `110` Many edits in one encode < `11` Chained and frame-level edits < `1` Edit < root ([AGENTS.md](../AGENTS.md))

## Call

```
render {"input": "clip.mov", "ops": [{"op": "trim", "start": 1, "end": 5},
                                     {"op": "speed", "factor": 0.5},
                                     {"op": "reverse"}]}
-> {"output": "clip.render.mp4", "duration": 8.0, ...}
```

| Argument | Default | Meaning |
|---|---|---|
| `ops` | required | list of op objects, run in order |
| `crf` | 18 | H.264 quality |
| `output` | `<stem>.render.mp4` | |

The output is H.264/AAC MP4 at the source frame rate.

## The ops

The same op objects go in each clip's `ops` in `concat`.

| Op | Fields | Effect |
|---|---|---|
| `trim` | `start` = 0, `end` = null | keep `[start, end)` |
| `cut` | `start`, `end` (both required) | remove `[start, end)` and join the rest |
| `speed` | `factor` (0.01-100), `audio` = `"pitch"` | as the `speed` tool in exact mode |
| `reverse` | none | play backwards; holds the timeline in RAM (about 2 GiB cap) |
| `crop` | `width`, `height` (even), `x` = null, `y` = null | keep a window; an omitted `x` or `y` centres it |
| `scale` | `width` (even), `height` = null | resize; an omitted `height` keeps the aspect ratio (rounded to even) |

## How the chain runs

- Ops run in order, and each one works on what the previous one produced. After `speed` 0.5 every
  later time is doubled; after `crop`, the next `scale` or `crop` sees the cropped frame.
- Crop coordinates are display pixels of the frame at that point in the chain, with rotation
  already applied.
- The whole chain costs one encode. One `render` loses less quality than several `trim`, `speed`
  or `reverse` calls in a row.
- Errors name the problem: an empty trim range, a crop that "does not fit the 1080x1920 frame", or
  a reverse over the RAM cap.

## Common frames

| Goal | From 1080x1920 portrait | From 1920x1080 landscape |
|---|---|---|
| 4:5 portrait (Instagram), 1080x1350 | `crop` 1080x1350 (`y` to aim) | `crop` 864x1080 (`x` to aim), then `scale` 1080 |
| square 1080x1080 | `crop` 1080x1080 | `crop` 1080x1080 |

To give different parts of one file different ops (slowing only the ending, for example), use
`concat` with the same input several times ([1101-concat.md](1101-concat.md)).
