# reverse

> Play a clip backwards, video and audio, working in chunks so clips of any length fit in memory.

Tree: `1011` < `101` Time < `10` One edit per call < `1` Edit < root ([AGENTS.md](../AGENTS.md))

## Call

```
reverse {"input": "clip.mov"}
reverse {"input": "long4k.mov", "chunk": 2}
-> {"output": "clip.rev.mp4", ...}
```

| Argument | Default | Meaning |
|---|---|---|
| `chunk` | sized to about 1 GiB of frames, 1-10 s | seconds reversed at a time; more than 0.2 |
| `crf` | 18 | H.264 quality |
| `output` | `<stem>.rev.mp4` | |

The tool splits the clip into near-lossless chunks, reverses each, and joins them last to first;
the audio is reversed in one pass. The output is H.264/AAC MP4.

## The reverse op

`{"op": "reverse"}` inside `render` and `concat` reverses in the same encode as the other ops, but
it holds the whole timeline in RAM and refuses past about 2 GiB of frames (at 30 fps, about 5 s of
4K or 20 s of 1080p). Trim before it, or reverse with this tool first and use the output.

## When to use it

- For a long or high-resolution clip on its own.
- For boomerangs and reversed parts inside a longer edit, `concat` with a `reverse` op does
  everything in one encode ([1101-concat.md](1101-concat.md)).
