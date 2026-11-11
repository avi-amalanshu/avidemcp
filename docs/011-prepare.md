# prepare

> Re-encode to MPEG-4 Part 2 with only I- and P-frames, a constant frame rate, and I-frames only where you choose: the input format for drop_iframes and repeat_pframes.

Tree: `011` < `01` Encode < `0` Inspect and encode < root ([AGENTS.md](../AGENTS.md))

## Call

```
prepare {"input": "clip.mp4"}
prepare {"input": "joined.mp4", "keyframes": [4.7333, 9.8], "intra_penalty": 300}
-> {"output": "joined.prep.mkv", "keyframes": [0.0, 4.7333, 9.8], "video": {"codec": "mpeg4", ...}}
```

| Argument | Default | Meaning |
|---|---|---|
| `keyframes` | `"scene"` | where I-frames go besides frame 0: `"scene"`, `"none"`, or a list of times (s) |
| `threshold` | 0.3 (0-1) | scene-cut sensitivity for `"scene"`; lower finds more cuts |
| `intra_penalty` | 0 (0-1000000) | discourages blocks coded from scratch; see below |
| `quality` | 3 (1-31) | MPEG-4 quantiser: lower is sharper and bigger |
| `output` | `<stem>.prep.mkv` | |

The result's `keyframes` lists the I-frames the file actually has.

## What it produces

MPEG-4 Part 2 video in MKV, at the source frame rate, with HDR tone-mapped to SDR and the audio
carried over. It has no B-frames, so packets are stored in display order, and the encoder's own
I-frames are switched off (at scene changes and every 600 frames). That makes it safe to remove or
repeat packets with `drop_iframes` and `repeat_pframes`. The file is larger than the source; treat
it as an intermediate.

## `keyframes`

- A list of times puts an I-frame on the first frame at or after each time. Use it when you know
  where the cuts are, for example `concat`'s `junctions`, passed unchanged.
- `"scene"` detects hard cuts and puts I-frames there. Check the result: it can miss a soft cut or
  fire on a flash or a whip pan.
- `"none"` keeps only frame 0, so the whole clip is one run of P-frames.

An I-frame restarts prediction from a complete picture. Any I-frame that `drop_iframes` leaves in
place therefore ends the effect of earlier drops at that point.

## `intra_penalty`

The encoder codes some blocks of a P-frame from scratch (intra blocks), especially in flat or noisy
areas such as snow, sky or walls. After `drop_iframes`, each intra block replaces part of the wrong
picture with the right one. A higher penalty means fewer intra blocks, so a broken picture lasts
longer:

| Value | Effect after a dropped I-frame |
|---|---|
| 0 | faithful encode; flat areas are replaced within about half a second |
| 300 | the old picture holds, and the new one is back after about 2 s |
| 1000 | holds noticeably longer |
| 3000+ | the new picture shows only as faint residue and never fully returns without a later I-frame |

These values come from real footage; see the datamosh section of [EXAMPLES.md](../EXAMPLES.md).

## Notes

- Run `prepare` after `render` and `concat`, not before them: every later re-encode brings
  B-frames and the encoder's own I-frames back.
- Check the result's `keyframes` against the times you asked for. An I-frame one frame away from a
  junction sits on the wrong frame.
