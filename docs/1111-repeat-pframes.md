# repeat_pframes

> Replay one P-frame, or a short run of them, several times without decoding, so its motion is applied again and again.

Tree: `1111` < `111` Frame-level edits < `11` Chained and frame-level edits < `1` Edit < root ([AGENTS.md](../AGENTS.md))

## Call

```
repeat_pframes {"input": "clip.prep.mkv", "at": 1.3, "times": 45}
-> {"output": "clip.prep.bloom.mkv", "frame": 1.3, ...}
repeat_pframes {"input": "clip.prep.mkv", "at": 4.228, "times": 8, "span": 3, "timing": "shift"}
```

| Argument | Default | Meaning |
|---|---|---|
| `at` | required | time (s); the first P-frame shown at or after it is used |
| `times` | 30 (2-10000) | total plays of the run, the original included |
| `span` | 1 (1-1000) | consecutive P-frames in the run; the run stops at the next I-frame |
| `timing` | `"keep"` | `keep`: the copies overwrite the frames after the run, so the duration and audio are unchanged and copies past the end are cut off. `shift`: the copies are inserted, the clip gets `(times - 1) * span` frames longer, and all audio is removed |
| `output` | `<stem>.bloom.mkv` | |

`frame` is the time of the first frame of the run that was actually used.

## What it does

Each P-frame stores motion relative to the picture before it. Playing the same P-frame again
applies the same motion to a picture that has already moved, so the motion builds up into a smear
along its direction (a "bloom"). This is the P-frame datamosh. Repeating a decoded frame would only
freeze the picture; this tool repeats the compressed one.

## Requirements and behaviour

- The input needs to be made by `prepare` (no B-frames).
- An I-frame at `at` is skipped in favour of the next P-frame; repeating an I-frame would only
  freeze the picture.
- To hit a given frame, pass a time a few milliseconds before it: frame `n` of a 30 fps file is at
  `n / 30`, so pass `n / 30 - 0.005`. Check `frame`.
- Takes seconds. Writes MKV; `bake` turns it into a plain MP4.

## Several repeats in one file

Call once per repeat, each call on the previous output.

- With `shift`, each repeat moves everything after it. Apply the repeats from the latest time to the
  earliest, so the planned `at` times stay valid.
- With `keep`, a repeat overwrites the frames after its run, and a later repeat aimed at an
  overwritten frame repeats the copy, not the original. Plan runs that don't overlap.

The datamosh section of [EXAMPLES.md](../EXAMPLES.md) covers choosing the frame, how many times to
repeat it, and schedules of growing repeats.
