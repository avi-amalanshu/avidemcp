# concat

> Join clips end to end in one encode, each clip running its own ops first; returns the junction times.

Tree: `1101` < `110` Many edits in one encode < `11` Chained and frame-level edits < `1` Edit < root ([AGENTS.md](../AGENTS.md))

## Call

```
concat {"clips": [{"input": "a.mov"},
                  {"input": "b.mov", "ops": [{"op": "trim", "start": 7.6}, {"op": "reverse"}]}],
        "width": 1080, "height": 1350}
-> {"output": "a.concat.mp4", "junctions": [4.7333], ...}
```

| Argument | Default | Meaning |
|---|---|---|
| `clips` | required, at least 1 | `[{"input": path, "ops": [op objects]}]`, played in order |
| `width`, `height` | the first clip's size after its ops | output size; even; give both or neither |
| `crf` | 18 | H.264 quality |
| `output` | `<first clip's stem>.concat.mp4` | |

## What happens to each clip

1. Its own `ops` run, exactly as in `render` ([1100-render.md](1100-render.md)).
2. It is scaled to cover `width` x `height` and centre-cropped to fit.
3. It is set to the first clip's frame rate and to a whole number of frames.
4. Its audio becomes 48 kHz stereo; a clip without audio gets silence.

Then all the clips are joined in one H.264/AAC MP4 encode.

`junctions` lists the time where each clip after the first begins in the output. They are exact
frame times, so they can be passed unchanged to other tools, for example as `prepare`'s
`keyframes`.

## When and how

- One input can appear many times with different ops. That is how to build boomerangs and loops,
  or to slow down only part of a shot.
- Boomerang: `[{"input": x}, {"input": x, "ops": [{"op": "reverse"}]}]`. A partial boomerang trims
  the reversed copy: `{"input": x, "ops": [{"op": "trim", "start": 3.6}, {"op": "reverse"}]}` plays
  from the end back to 3.6 s, then the next clip starts.
- Seamless loop: end on the frame you started on. If the first clip is `x` from 0, make the last
  clip `x` reversed down to 0, with the same crop on both.
- Mixed orientations: the automatic cover-crop centres each clip. When a subject is off-centre,
  add a `crop` to that clip's ops to aim the framing first.
- `reverse` inside `concat` holds the clip in RAM. For long clips, run the `reverse` tool first and
  concat its output.
- `concat` with a single clip is `render` plus size fitting.

[EXAMPLES.md](../EXAMPLES.md) has worked recipes.
