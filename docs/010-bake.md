# bake

> Re-encode any file to a plain H.264/AAC MP4 at a constant frame rate.

Tree: `010` < `01` Encode < `0` Inspect and encode < root ([AGENTS.md](../AGENTS.md))

## Call

```
bake {"input": "clip.mkv"}
bake {"input": "final.mp4", "crf": 26, "output": "share/final.mp4"}
-> {"output": "clip.bake.mp4", "video": {"codec": "h264", ...}, ...}
```

| Argument | Default | Meaning |
|---|---|---|
| `crf` | 18 (0-51) | H.264 quality: lower is better and bigger; 18 looks lossless |
| `output` | `<stem>.bake.mp4` | |

`bake` is `render` with no ops: one decode and one encode, HDR tone-mapped to SDR, output at the
source frame rate.

## When to use it

- To finish the output of `drop_iframes` or `repeat_pframes`. Those MKVs depend on broken frame
  references, which players, editors and upload sites can decode differently or refuse. Baking
  stores the frames the decoder produced as ordinary pictures, so everyone sees the same thing.
- To freeze an intermediate result so later tools treat it as plain footage.
- To make a smaller copy for sharing: bake the master again at `crf` 23-26 into another file.
- To turn an awkward source (variable frame rate, HDR, MKV) into a plain MP4.
