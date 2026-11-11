# drop_iframes

> Delete the I-frames shown in [start, end) without decoding; the P-frames after each one then predict from the wrong picture.

Tree: `1110` < `111` Frame-level edits < `11` Chained and frame-level edits < `1` Edit < root ([AGENTS.md](../AGENTS.md))

## Call

```
drop_iframes {"input": "joined.prep.mkv", "start": 0.5}
-> {"output": "joined.prep.drop.mkv", "dropped": [4.733], ...}
drop_iframes {"input": "joined.prep.mkv", "start": 4.7, "end": 4.8, "timing": "shift"}
```

| Argument | Default | Meaning |
|---|---|---|
| `start` | 0 | range start (s) |
| `end` | end of clip | range end (s), not included |
| `timing` | `"keep"` | `keep`: each dropped I-frame becomes a one-frame hold, and the duration and audio are unchanged. `shift`: the frames close up, the clip gets one frame shorter per drop, and all audio is removed |
| `output` | `<stem>.drop.mkv` | |

`dropped` lists the times of the removed I-frames.

## What it does

An I-frame is a complete picture; the P-frames after it store motion and corrections relative to
the picture before them. Without the I-frame, those P-frames are applied to the last picture before
it, so the new motion moves the old image. This is the I-frame datamosh. It lasts until the next
I-frame that is still there, or until the encoder's intra blocks repaint the picture (`prepare`'s
`intra_penalty` controls how soon).

## Requirements and behaviour

- The input needs to be made by `prepare` (no B-frames). Other files are refused with an error that
  names `prepare`.
- The first frame of the file is never dropped.
- Fails with `no I-frames in [...] besides the first frame` when the range holds none; `probe` lists
  the I-frame times.
- Takes seconds: no decoding and no quality loss.
- Writes MKV. `preview` shows it as a player would; `bake` turns it into a plain MP4.

## How

- `start` 0.5 with no `end` drops every I-frame after the first frame.
- To keep some I-frames, choose a range that leaves them out, or call more than once, each call on
  the previous output.
- Check `dropped` before going on.

The datamosh section of [EXAMPLES.md](../EXAMPLES.md) shows how to choose the cuts and what to look
for.
