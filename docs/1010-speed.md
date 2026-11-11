# speed

> Play a clip faster or slower; audio keeps its pitch, follows the speed, or is dropped, and copy mode retimes without re-encoding the video.

Tree: `1010` < `101` Time < `10` One edit per call < `1` Edit < root ([AGENTS.md](../AGENTS.md))

## Call

```
speed {"input": "clip.mov", "factor": 0.5}
speed {"input": "clip.mov", "factor": 2, "audio": "tape"}
speed {"input": "clip.mov", "factor": 0.5, "mode": "copy"}
```

| Argument | Default | Meaning |
|---|---|---|
| `factor` | required (0.01-100) | 2 = twice as fast, 0.5 = half speed |
| `audio` | `"pitch"` | `pitch` keeps the pitch; `tape` lets the pitch follow the speed; `none` drops the audio |
| `mode` | `"exact"` | `exact` re-encodes; `copy` keeps every video packet |
| `crf` | 18 | exact mode only |
| `output` | `<stem>.speed.mp4` (exact) or `<stem>.speed.<input ext>` (copy) | |

## Modes

- `exact` re-encodes at the source frame rate: slowing down repeats frames, speeding up drops them.
- `copy` scales the timestamps and keeps every video packet, so the frame rate changes (30 fps at
  0.5 becomes 15 fps). The audio is still re-encoded, to AAC. The container stays the input's.

## When and how

- Slowing a nearly still shot to 0.5 reads as stillness rather than slow motion; it gives a quiet
  moment more time. On moving footage the repeated frames show as a stutter.
- Check `fps` with `probe` before planning slow motion. A clip whose header claims 120 fps may hold
  24, and slowing that to 0.25 shows only 6 new frames per second.
- To change the speed of only part of a shot, use `concat` with the shot twice, the second copy
  with a `speed` op ([1101-concat.md](1101-concat.md)).
- Inside `render` and `concat`, `{"op": "speed", "factor": 0.5, "audio": "pitch"}` does the same as
  exact mode.
