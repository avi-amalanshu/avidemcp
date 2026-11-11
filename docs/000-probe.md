# probe

> Read a file's duration, streams, frame rate, frame count and I-frame times; quick, since it reads packets rather than pictures.

Tree: `000` < `00` Inspect < `0` Inspect and encode < root ([AGENTS.md](../AGENTS.md))

## Call

```
probe {"input": "clip.mov"}
-> {"path": "/abs/clip.mov", "format": "mov,mp4,m4a,3gp,3g2,mj2", "duration": 14.4, "size": 18633449,
    "video": {"codec": "hevc", "size": "1920x1080", "fps": 30.0, "bframes": true,
              "hdr": "hlg", "rotation": 0},
    "audio": {"codec": "aac", "rate": 44100, "channels": 2},
    "frames": 432, "keyframes": [0.0, 1.0, ...], "keyframe_count": 15}
```

The values are illustrative.

| Field | Meaning |
|---|---|
| `duration`, `size` | seconds, bytes |
| `video.size` | coded size; when `rotation` is 90 or -90 the picture displays with width and height swapped |
| `video.fps` | frame rate; measured from the frame spacing when the header is more than 1.5x off |
| `video.bframes` | `true`: frames are stored out of display order; `drop_iframes` and `repeat_pframes` refuse such files until `prepare` has run |
| `video.hdr` | `"hlg"`, `"pq"` or null; re-encodes tone-map HDR to SDR |
| `audio` | null when there is no audio |
| `frames` | number of video packets |
| `keyframes` | I-frame times (s), at most 500; `keyframe_count` is the full count |

## When to use it

- First, on any file you haven't seen. Size and rotation decide crops, `fps` gives frame times, and
  `audio` says whether there is sound to keep.
- Before a copy-mode `trim` or `cut`: I-frames are the only places where copy mode cuts cleanly.
- Before `drop_iframes`: choose a range that covers the I-frames to drop and leaves out the rest.
- After `prepare`: `keyframes` should be exactly `0.0` plus the times you asked for.

## Notes

- Only I-frame times are listed. At a constant frame rate, frame `n` starts at `n / fps`.
- In camera footage the I-frames come at the encoder's regular intervals, not at scene changes.
