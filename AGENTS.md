# avidemcp: guide for agents

> Root of the docs tree: the rules every tool shares, one reference line per tool, and the index of one doc per tool. Read it before any multi-step edit.

avidemcp is an MCP server that edits video files on the local disk. It inspects files, trims, cuts,
changes speed, reverses, crops, scales and joins clips, and re-encodes them. It also edits
compressed frames directly (dropping I-frames, repeating P-frames), which produces glitch effects
such as datamoshing. Each tool reads one file and writes a new one. `preview` returns images, so
you can look at the result of every step.

## How these docs are organised

They form a binary tree. This file is the root and should stay in your context. Each node in the
tree below splits its group of tools in two and has a one-line summary. Each leaf is one tool's
doc, under `docs/`, with its full syntax, defaults, behaviour, and when and how to use it. Open a
tool's leaf before you first use that tool in a session, and again when a call fails or a result
looks wrong.

[EXAMPLES.md](EXAMPLES.md) chains tools into finished effects and explains each choice. It has
editing recipes and a worked datamoshing example.

Through MCP, every one of these files is a resource named `avidemcp://docs/<file name>`:
`avidemcp://docs/AGENTS.md`, `avidemcp://docs/EXAMPLES.md`, `avidemcp://docs/1101-concat.md`.

## Rules for every tool

Files:

- `input` is a path to a local file (`~` is expanded). No tool modifies its input.
- Omit `output` and the result is written beside the input as `<stem>.<op>.<ext>`, such as
  `clip.trim.mp4`. If that name is taken, `.2`, `.3`, ... is appended, so a derived name never
  overwrites anything. An explicit `output` is used as given: its folders are created, a file
  already there is overwritten, and it must differ from `input`.
- Op names stack up along a chain (`clip.prep.drop.bake.mp4`). For long chains, pass `output` paths
  in a work folder.

Times:

- Seconds, on the timeline of the file you pass in. Ranges are half-open, `[start, end)`; an
  omitted `end` means the end of the clip.
- Inside `render` and `concat` ops, each op's times refer to the timeline that the previous op
  produced.
- After a call that changes timing, take new times from its result or from `probe`.

Output formats:

- Re-encoding tools (`trim`, `cut` and `speed` in exact mode, `reverse`, `render`, `concat`, `bake`)
  write H.264 + AAC in MP4, at a constant frame rate. `crf` (0-51, default 18) sets the quality:
  lower is better and bigger; 23-26 makes a lighter copy for sharing.
- Copy modes (`mode: "copy"` on `trim`, `cut`, `speed`) keep the input's container and its video
  packets.
- `prepare` writes MPEG-4 Part 2 in MKV. `drop_iframes` and `repeat_pframes` write MKV; `bake`
  turns their output into MP4.
- Re-encodes keep the source frame rate (`concat`: the first clip's), follow phone rotation, and
  tone-map HDR to SDR. A frame rate is measured from the frame spacing when the header is more than
  1.5x off.

Results and errors:

- Every tool except `preview` returns JSON: `output`, `duration`, `size`,
  `video` (`codec`, `size`, `fps`, `bframes`, `hdr`, `rotation`) and `audio` (`codec`, `rate`,
  `channels`, or null), plus the tool's own field: `keyframes` (prepare), `dropped`
  (drop_iframes), `frame` (repeat_pframes), `junctions` (concat) or `kept` (copy-mode trim and
  cut). `probe` returns `path` and `format` in place of `output`. Check these after each call.
- A failed call returns text that names the cause and usually the fix. Change the call before
  retrying it.
- Re-encoding tools send progress notifications. A long 4K job can outlast the client's tool
  timeout; in Claude Code, raise it with `MCP_TOOL_TIMEOUT=1800000 claude` (30 min).

Docs notation: `tool {JSON arguments}` is one call, and `-> {...}` shows the result fields that
matter.

## Tools

| Tool | Signature (defaults) | Use it to |
|---|---|---|
| `probe` | `probe(input)` | read duration, streams, fps, frame count and I-frame times |
| `preview` | `preview(input, start=0, end=None, count=12, cols=4, width=1280)` | look at frames; check every step |
| `bake` | `bake(input, crf=18)` | re-encode any file to a plain MP4 |
| `prepare` | `prepare(input, keyframes="scene", quality=3, threshold=0.3, intra_penalty=0)` | re-encode with I-frames only where you choose, for the frame-level tools |
| `trim` | `trim(input, start=0, end=None, mode="exact", snap=True, crf=18)` | keep one range |
| `cut` | `cut(input, start, end, mode="exact", snap=True, crf=18)` | remove one range |
| `speed` | `speed(input, factor, audio="pitch", mode="exact", crf=18)` | play faster or slower |
| `reverse` | `reverse(input, chunk=None, crf=18)` | play backwards, any length |
| `render` | `render(input, ops, crf=18)` | chain trim, cut, speed, reverse, crop and scale in one encode |
| `concat` | `concat(clips=[{input, ops}], width=None, height=None, crf=18)` | join clips, each with its own ops; get the junction times |
| `drop_iframes` | `drop_iframes(input, start=0, end=None, timing="keep")` | delete I-frames so later frames predict from the wrong picture |
| `repeat_pframes` | `repeat_pframes(input, at, times=30, span=1, timing="keep")` | replay a P-frame so its motion builds up |

Every tool also takes `output`. Ops for `render` and `concat` are objects such as
`{"op": "trim", "start": 1, "end": 5}`, `{"op": "speed", "factor": 0.5}`, `{"op": "reverse"}`,
`{"op": "crop", "width": 1080, "height": 1350}` and `{"op": "scale", "width": 720}`.

Chaining: prefer one `render` or `concat` to several single-edit calls, since each re-encode loses
a little quality. The frame-level tools need a `prepare`d input and usually end with `bake`.

## Tree

- `0` Inspect and encode: read a file's facts, look at it, and re-encode it whole.
  - `00` Inspect: facts and pictures, without writing a file.
    - `000` [probe](docs/000-probe.md): read a file's duration, streams, frame rate, frame count and I-frame times; quick, since it reads packets rather than pictures.
    - `001` [preview](docs/001-preview.md): look at a clip: one PNG contact sheet of evenly spaced frames over [start, end], with their times.
  - `01` Encode: re-encode a whole file, to a plain MP4 or to a frame-editable intermediate.
    - `010` [bake](docs/010-bake.md): re-encode any file to a plain H.264/AAC MP4 at a constant frame rate.
    - `011` [prepare](docs/011-prepare.md): re-encode to MPEG-4 Part 2 with only I- and P-frames, a constant frame rate, and I-frames only where you choose: the input format for drop_iframes and repeat_pframes.
- `1` Edit: change what plays.
  - `10` One edit per call: ranges and time.
    - `100` Ranges.
      - `1000` [trim](docs/1000-trim.md): keep one range of a clip; exact mode re-encodes frame-accurately, copy mode is lossless but starts on an I-frame.
      - `1001` [cut](docs/1001-cut.md): remove one range and join what's left; exact mode re-encodes frame-accurately, copy mode is lossless but resumes on an I-frame.
    - `101` Time.
      - `1010` [speed](docs/1010-speed.md): play a clip faster or slower; audio keeps its pitch, follows the speed, or is dropped, and copy mode retimes without re-encoding the video.
      - `1011` [reverse](docs/1011-reverse.md): play a clip backwards, video and audio, working in chunks so clips of any length fit in memory.
  - `11` Chained and frame-level edits.
    - `110` Many edits in one encode.
      - `1100` [render](docs/1100-render.md): run a chain of ops (trim, cut, speed, reverse, crop, scale) on one file in a single decode and encode.
      - `1101` [concat](docs/1101-concat.md): join clips end to end in one encode, each clip running its own ops first; returns the junction times.
    - `111` Frame-level edits: rearrange compressed frames without decoding.
      - `1110` [drop_iframes](docs/1110-drop-iframes.md): delete the I-frames shown in [start, end) without decoding; the P-frames after each one then predict from the wrong picture.
      - `1111` [repeat_pframes](docs/1111-repeat-pframes.md): replay one P-frame, or a short run of them, several times without decoding, so its motion is applied again and again.

## Working on this repo

- Set up and test with `uv sync && uv run pytest -q` (a few seconds; the tests generate their own
  media).
- Decoded-domain features (filters, edits) are one pydantic model in `src/avidemcp/ops.py` plus one
  `graph.link` rule in `graph.py`. Compressed-domain features (frame-level and copy edits) are pure
  plan functions in `packets.py`. Tools are thin wrappers in `server.py`.
- Each tool has one leaf. When a tool changes, update its leaf, its row in the table above, the
  `GUIDE` string in `server.py` (the server instructions every client loads), and the tools table in
  `README.md`. Recipes and techniques that combine tools go in `EXAMPLES.md`, not in the leaves.
- Every docs file starts with a `# title` line and a `> summary` line. The server publishes each
  file as a resource with that summary as its description, so both lines are required. A leaf's
  summary and its line in the tree above are the same sentence.
- A node's id is its path from the root: `0` takes the first half, `1` the second. Leaves are named
  `docs/<id>-<tool>.md`. To add a tool, split the closest leaf into two children (`1011` becomes
  `10110` and `10111`); no other id changes. The layout follows Victor Taelin's OptMem summary
  tree: a small root that is always loaded, with each step down covering half as much in more
  detail.
