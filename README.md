# avidemcp

A headless MCP server for video editing and datamoshing. Claude (or any MCP client) can trim,
cut, speed up, slow down and reverse clips, and do Avidemux-style datamoshing: removing I-frames
and repeating P-frames. A `preview` tool returns contact-sheet images, so the agent can see results.
The long-term goal is Avidemux's feature set.

## Requirements

You only install **two things yourself**: `uv` and `git`. uv fetches Python and everything else,
including FFmpeg.

| Requirement | Version | Notes |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | any recent (tested 0.13) | Installs Python and the deps; runs the server |
| Python | 3.12 – 3.14 | uv downloads one if you don't have it |
| `mcp` (Python SDK) | `>=2.3,<3` | 2.x API (`MCPServer`); 1.x will not work |
| `av` (PyAV) | `>=19,<20` | Wheels bundle their own FFmpeg libraries |
| `imageio-ffmpeg` | `>=0.8,<0.9` | Ships a static `ffmpeg` binary (FFmpeg 9.0) |
| `numpy` | `>=2,<3` | Contact-sheet tiling |
| Claude Code | any version with MCP support | Or Claude Desktop / any stdio MCP client |

Exact tested versions are pinned in `uv.lock` (av 19.0.2, imageio-ffmpeg 0.8.1, mcp 2.3.0,
numpy 2.5.4).

**No system FFmpeg is needed.** The server picks the `ffmpeg` binary in this order:
1. `$AVIDEMCP_FFMPEG`
2. `ffmpeg` on your `PATH`
3. the bundled build

If you bring your own, it needs these:

| What | Needed for |
|---|---|
| FFmpeg ≥ 6 | everything (9.0 is the tested version) |
| `libx264` | every re-encoding tool |
| `mpeg4` encoder (always built in) | `prepare` |
| `zscale` (libzimg) | HDR tone-mapping only; without it HDR is passed through untouched |

### Platforms

Prebuilt wheels exist for all dependencies on:

| Platform | Status |
|---|---|
| macOS Apple Silicon (14+) | **tested** |
| macOS Intel (11+) | expected to work |
| Linux x86_64 / aarch64, glibc 2.28+ | expected to work |
| Windows x64 / ARM64 | expected to work |
| Alpine (musl) / 32-bit ARM | install a system `ffmpeg` and set `AVIDEMCP_FFMPEG`; imageio-ffmpeg has no binary there |

## Use it with Claude Code on your laptop

**1. Install uv** (skip if `uv --version` works):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS / Linux
# or: brew install uv
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**2. Clone and install** (downloads ~100 MB of wheels, including FFmpeg):

```bash
git clone https://github.com/avi-amalanshu/avidemcp.git
cd avidemcp
uv sync
uv run pytest -q          # optional: ~3 s smoke test on synthetic clips
```

**3. Register the server with Claude Code.** Pick one of:

- **This project only.** Start `claude` inside the `avidemcp` directory. It reads the bundled
  `.mcp.json` and asks you to approve the server once.
- **Every project.** Run this from anywhere, with an absolute path:

  ```bash
  claude mcp add --scope user avidemcp -- uv run --directory /absolute/path/to/avidemcp avidemcp
  ```

Check with `claude mcp list` or `/mcp` inside a session. Then just ask:

> Datamosh ~/Movies/clip.mov at its scene cuts, add a bloom around 5 s, and show me a preview.

**Claude Desktop** works the same way. Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "avidemcp": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/avidemcp", "avidemcp"]
    }
  }
}
```

If the client can't find `uv`, as GUI apps sometimes don't inherit your shell `PATH`, use its
full path (`which uv`) as `command`.

### Things to know

- **Files stay local.** The server reads and writes files on your machine and never uploads
  anything. Tools never modify their input.
- **Output names.** Outputs land beside the input as `<stem>.<op>.<ext>` unless you pass `output`.
  Existing files are never overwritten: `.2`, `.3`, … are appended.
- **Long renders.** These report progress. For very long jobs, raise Claude Code's MCP timeout,
  e.g. `MCP_TOOL_TIMEOUT=1800000 claude` (30 min).

## Tools

| Tool | What it does |
|---|---|
| `probe` | Duration, streams, frame count, I-frame (keyframe) times |
| `preview` | PNG contact sheet of evenly spaced frames |
| `prepare` | Mosh-ready copy: MPEG-4 Part 2 with no B-frames and constant frame rate. I-frames go at scene cuts, nowhere, or at given times. HDR is tone-mapped to SDR. `intra_penalty` makes a mosh last: without it, flat areas like snow or sky get repainted within frames. |
| `drop_iframes` | Delete I-frames in a range, so later motion smears the old picture |
| `repeat_pframes` | Replay a P-frame (or a run of them) N times: the "bloom" |
| `bake` | Render any clip, e.g. a mosh, to a normal H.264/AAC MP4 |
| `trim` / `cut` | Keep / remove a range. `mode="exact"` re-encodes frame-accurately. `mode="copy"` is lossless and snaps to keyframes; `snap=false` breaks references on purpose. |
| `speed` | Faster or slower. Audio can keep its pitch, follow the speed (`tape`), or be dropped. `mode="copy"` only rescales timestamps. |
| `reverse` | Play backwards, in chunks, so long and 4K clips fit in RAM |
| `render` | Chain `trim` / `cut` / `speed` / `reverse` / `crop` / `scale` in one decode/encode pass |
| `concat` | Join clips in one encode, like Avidemux's Append. Each clip runs its own ops, then all are fitted to one size and frame rate. Returns the junction times. |

### Datamosh workflow

```
prepare(clip.mov)                       -> clip.prep.mkv   (I-frames at hard cuts)
probe(clip.prep.mkv)                    -> keyframes: [0.0, 4.2, 9.8]
drop_iframes(clip.prep.mkv, start=4)    -> clip.prep.drop.mkv
repeat_pframes(..., at=5.0, times=40)   -> ...bloom.mkv
preview(...)                            -> look at it
bake(...)                               -> ...bake.mp4
```

To mosh **two clips** into each other:
1. `concat` them; it returns the junction times.
2. `prepare(keyframes=[junction], intra_penalty=300)`.
3. `drop_iframes` at the junction, so the second clip's motion moves the first clip's last frame.

Timing modes:
- **`timing="keep"`** (default) preserves duration and audio sync. A dropped I-frame becomes a
  one-frame hold, and repeated P-frames overwrite the frames after them.
- **`timing="shift"`** is the classic behaviour. Drops shorten the clip, repeats insert frames,
  and the audio is removed.

## How it works

Two engines, mirroring Avidemux's split between *Copy* output and encoder output:

- **Packet engine** (`packets.py`, PyAV). Demuxes once into a packet table. Edits are pure
  functions on a plan of `(source packet, output timestamps)`, and one streaming remux writes it.
  Datamosh ops and copy-mode trim/cut live here: no decoding, no quality loss.
- **Filter engine** (`ops.py`, `graph.py`, `jobs.py`; the FFmpeg command-line tool). Ops are
  pydantic models, each compiled into filtergraph lines by one `graph.link` rule; `render` runs a
  chain of them in one pass. Adding a feature means one model plus one rule.

## Development

```bash
uv sync && uv run pytest -q
```

Tests generate their media with FFmpeg at run time; no video files are committed.

## Roadmap toward Avidemux parity

- **Editing:** project files (a saved `render` op list)
- **Video filters:** rotate/flip, deinterlace, denoise/sharpen, color, fades, subtitles,
  logo overlay, frame-rate change
- **Audio:** gain, normalize, delay, replace, external tracks
- **Output:** encoder choice (x265, VP9, AV1, ProRes) and settings, container choice
- **Datamosh:** packet-level reverse/shuffle moshes, moshing H.264 directly
