# render

> Run a chain of ops (trim, cut, speed, reverse, crop, scale, fps, motion_blur) on one file in a single decode and encode.

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

The output is H.264/AAC MP4 at the source frame rate, unless an `fps` or `motion_blur` op sets
another.

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
| `fps` | `rate` (up to 1000), `method` = `"drop"` | convert the frame rate; see below |
| `motion_blur` | `shutter` = 180, `samples` = 8, `rate` = null | blur motion as a camera shutter would; see below |

## How the chain runs

- Ops run in order, and each one works on what the previous one produced. After `speed` 0.5 every
  later time is doubled; after `crop`, the next `scale` or `crop` sees the cropped frame.
- Crop coordinates are display pixels of the frame at that point in the chain, with rotation
  already applied.
- The whole chain costs one encode. One `render` loses less quality than several `trim`, `speed`
  or `reverse` calls in a row.
- Errors name the problem: an empty trim range, a crop that "does not fit the 1080x1920 frame", or
  a reverse over the RAM cap.

## Frame rate and motion blur

`fps` converts the timeline to `rate` frames per second, like Avidemux's Resample FPS filter. The
duration and the audio don't change. `rate` 23.976, 29.97, 59.94 and 119.88 mean the NTSC rates
(24000/1001 and so on). `method` decides where the new frames come from:

| `method` | New frames | Cost | Artefacts |
|---|---|---|---|
| `drop` | the nearest existing frame, repeated or skipped | none | stutter when converting up |
| `blend` | a cross-fade of the two neighbouring frames | small | double images on fast motion |
| `motion` | motion-compensated interpolation (FFmpeg's `minterpolate`) | slow: about 8 output frames per second at 1080p | warping where objects cover each other, and at cuts |

`motion_blur` blurs moving things as a camera with a slower shutter would. It interpolates
`samples` frames per output frame interval with the `motion` method and averages the ones that the
shutter spans. Then it keeps one frame per interval, at `rate` (default: the current rate).

- `shutter` is the shutter angle: 180 keeps the shutter open for half of each frame interval,
  which is the film look; 360 for all of it, the strongest blur that leaves no gaps. Each output
  frame averages `round(samples * shutter / 360)` frames, starting at its own time.
- `samples` sets how smooth the streak is. Raise it when fast motion leaves visible steps in the
  streak. The cost grows with it: at the default of 8, one second of 1080p30 video took about 36 s
  on an Apple Silicon Mac, so trim first and raise the tool timeout for long clips.
- It works with or without a rate change: `{"op": "motion_blur", "rate": 24}` turns 60 fps
  footage into 24 fps footage with blur that matches the lower rate. Blending real frames
  (`fps` with `blend`) at a lower rate gives stacked copies of a fast subject, not a streak.

Both ops use motion estimation, which follows textured, rigid motion well and fails on cuts,
flashes, smoke and water. `preview` the result, and trim cuts out first or handle each shot in its
own `concat` clip.

Smooth slow motion is `speed` followed by `fps` at the source rate with `method` `"motion"`:
`[{"op": "speed", "factor": 0.25}, {"op": "fps", "rate": 30, "method": "motion"}]`. Without the
`fps` op, a slowdown repeats frames.

## Common frames

| Goal | From 1080x1920 portrait | From 1920x1080 landscape |
|---|---|---|
| 4:5 portrait (Instagram), 1080x1350 | `crop` 1080x1350 (`y` to aim) | `crop` 864x1080 (`x` to aim), then `scale` 1080 |
| square 1080x1080 | `crop` 1080x1080 | `crop` 1080x1080 |

To give different parts of one file different ops (slowing only the ending, for example), use
`concat` with the same input several times ([1101-concat.md](1101-concat.md)).
