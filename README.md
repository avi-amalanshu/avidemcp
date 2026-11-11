# avidemcp

avidemcp is a headless MCP server that edits video files on your machine. Through it, Claude or any
other MCP client can inspect clips and trim, cut, speed up, slow down, reverse, crop, scale and join
them. It can also edit a clip's compressed frames directly, as Avidemux does in copy mode; that is
how datamoshing is done. A `preview` tool returns contact sheets of frames, so the agent can look at
each result. The long-term goal is to match Avidemux's features.

## Requirements

You install only `uv` and `git` yourself. uv fetches Python and everything else, including FFmpeg.

| Requirement | Version | Notes |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | any recent version (tested with 0.13) | installs Python and the dependencies, and runs the server |
| Python | 3.12 to 3.14 | uv downloads one if you don't have it |
| `mcp` (Python SDK) | `>=2.3,<3` | the server uses the 2.x API (`MCPServer`); 1.x won't work |
| `av` (PyAV) | `>=19,<20` | its wheels bundle their own FFmpeg libraries |
| `imageio-ffmpeg` | `>=0.8,<0.9` | ships a static `ffmpeg` binary (FFmpeg 9.0) |
| `numpy` | `>=2,<3` | tiles the contact sheets |
| Claude Code | any version with MCP support | Claude Desktop or any other stdio MCP client also works |

`uv.lock` pins the versions that the tests ran on: av 19.0.2, imageio-ffmpeg 0.8.1, mcp 2.3.0 and
numpy 2.5.4.

You don't need FFmpeg installed on your system. The server uses the first `ffmpeg` binary it finds
in this order:

1. the path in `$AVIDEMCP_FFMPEG`
2. `ffmpeg` on your `PATH`
3. the build bundled with imageio-ffmpeg

If you bring your own, it needs the following:

| Component | Needed for |
|---|---|
| FFmpeg 6 or later | everything (9.0 is the tested version) |
| `libx264` | every tool that re-encodes |
| the `mpeg4` encoder (always built in) | `prepare` |
| `zscale` (libzimg) | converting HDR to SDR; without it, HDR passes through unchanged |

### Platforms

Every dependency has prebuilt wheels for these platforms:

| Platform | Status |
|---|---|
| macOS on Apple Silicon (14+) | tested |
| macOS on Intel (11+) | expected to work |
| Linux x86_64 or aarch64, glibc 2.28+ | expected to work |
| Windows x64 or ARM64 | expected to work |
| Alpine (musl), 32-bit ARM | install a system `ffmpeg` and set `AVIDEMCP_FFMPEG`, because imageio-ffmpeg has no binary for these |

## Use it with Claude Code on your laptop

1. Install uv, unless `uv --version` already works:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS / Linux
   # or: brew install uv
   # Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Clone the repository and install it. This downloads about 100 MB of wheels, FFmpeg included.

   ```bash
   git clone https://github.com/avi-amalanshu/avidemcp.git
   cd avidemcp
   uv sync
   uv run pytest -q          # optional: a 3 s test on generated clips
   ```

3. Register the server with Claude Code in one of two ways. To use it in this project only, start
   `claude` inside the `avidemcp` directory; Claude Code reads the bundled `.mcp.json` and asks you
   once to approve the server. To use it in every project, run this from anywhere, with an
   absolute path:

   ```bash
   claude mcp add --scope user avidemcp -- uv run --directory /absolute/path/to/avidemcp avidemcp
   ```

To check that the server is registered, run `claude mcp list`, or `/mcp` inside a session. Then ask
for an edit, for example:

> Trim ~/Movies/clip.mov to 0:12-0:40, crop it to 4:5 for Instagram, and show me a preview.

> Join these three clips into one 1080x1350 video and slow the last two seconds to half speed.

> Make a boomerang from ~/Movies/wave.mov that loops seamlessly.

Claude Desktop needs the same command. Add this to `claude_desktop_config.json`:

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

GUI apps sometimes don't inherit your shell's `PATH`. If the client can't find `uv`, put the full
path from `which uv` in `command`.

### Files, names and long jobs

The server reads and writes files only on your machine and never uploads anything. No tool changes
its input file.

Unless you pass `output`, each tool writes its result beside the input as `<stem>.<op>.<ext>`, for
example `clip.trim.mp4`. If that name is taken, the server appends `.2`, `.3` and so on, so it never
overwrites an existing file this way.

Tools that re-encode report their progress. A long job can take longer than Claude Code's MCP
timeout; to raise the timeout to 30 minutes, start Claude Code with
`MCP_TOOL_TIMEOUT=1800000 claude`.

## Tools

| Tool | What it does |
|---|---|
| `probe` | reports duration, streams, frame rate, frame count and the times of I-frames (keyframes) |
| `preview` | returns a PNG contact sheet of evenly spaced frames |
| `bake` | re-encodes any file to an ordinary H.264/AAC MP4 |
| `prepare` | re-encodes to MPEG-4 Part 2 with only I- and P-frames and with I-frames where you choose, so that `drop_iframes` and `repeat_pframes` can edit the file |
| `trim`, `cut` | keep or remove one range. `mode="exact"` re-encodes and cuts on the exact frame. `mode="copy"` doesn't re-encode, so it loses no quality, but it moves the cut to a keyframe; with `snap=false` it cuts exactly and leaves the next frames without their reference picture |
| `speed` | plays a clip faster or slower. The audio can keep its pitch, change pitch with the speed (`tape`), or be dropped. `mode="copy"` only rescales the timestamps |
| `reverse` | plays a clip backwards, in chunks, so that long and 4K clips fit in memory |
| `render` | runs a chain of `trim`, `cut`, `speed`, `reverse`, `crop` and `scale` with one decode and one encode |
| `concat` | joins clips in one encode, like Avidemux's Append. Each clip runs its own ops first, and then all of them are fitted to one size and frame rate. It returns the times where the clips meet |
| `drop_iframes` | deletes the I-frames in a range without decoding, so the frames after each one are built from the wrong picture |
| `repeat_pframes` | plays one P-frame, or a run of them, several times without decoding, so its motion adds up |

## Documentation

[AGENTS.md](AGENTS.md) is the reference for agents. It lists the rules that all tools share, gives
one line per tool, and indexes [docs/](docs/), which has a page for each tool with its full syntax
and advice on when to use it. The pages form a binary tree in which every node has a one-line
summary, so an agent can keep the top of the tree in its context and open only the pages it needs.

[EXAMPLES.md](EXAMPLES.md) shows how to combine the tools. It has editing recipes and a
[datamoshing tutorial](EXAMPLES.md#tutorial-an-i-frame-transition-between-two-clips), along with
the settings and lessons from datamoshing real footage.

The server publishes all of these files as MCP resources, such as `avidemcp://docs/AGENTS.md`. Its
built-in instructions tell agents to read them, so an agent can use them from any folder.

## How it works

avidemcp has two engines, which follow Avidemux's split between copy output and encoder output.

The packet engine (`packets.py`) uses PyAV. It reads a file's packets once into a table, without
decoding them. Each edit is a pure function on a plan that lists which source packet plays at which
output time, and one streaming pass writes the plan out. `drop_iframes`, `repeat_pframes` and the
copy modes of `trim` and `cut` run here, so they lose no quality.

The filter engine (`ops.py`, `graph.py` and `jobs.py`) runs the FFmpeg command-line tool. Each op is
a pydantic model, and one `graph.link` rule turns it into lines of an FFmpeg filter graph. `render`
runs a chain of ops in one pass. A new op therefore needs one model and one rule.

## Development

```bash
uv sync && uv run pytest -q
```

The tests generate their own media with FFmpeg when they run, so the repository contains no video
files.

## Roadmap

### Toward Avidemux's features

These features exist in Avidemux 2.8 and are missing here.

| Area | Planned |
|---|---|
| Output | a choice of video encoder (copy, H.264, H.265, MPEG-4 ASP, VP9, AV1, FFV1, HuffYUV, ProRes, DNxHD) and of rate control (quality level, target bitrate, two passes); a choice of audio encoder (copy, AAC, MP3, Opus, Vorbis, AC3, FLAC, PCM, none) and bitrate; a choice of container (MP4, MKV, WebM, MOV, AVI, MPEG-TS), with a check that the codecs fit it. This replaces the fixed H.264 + AAC + MP4 output of every tool that re-encodes. |
| Copy mode | `concat` without re-encoding when the streams match; keeping several ranges in one copy pass; copying the audio while the video is re-encoded |
| Audio | choosing a track or keeping all of them; adding or replacing a track from a file; delaying the audio to fix A/V sync; gain and normalization; mixdown to stereo or mono; resampling |
| Video filters | rotating by 90 or 180 degrees or by any angle; flipping and mirroring; borders, and resizing with padding to fit a size; fades in, out and through; brightness, contrast, saturation, hue, color balance and 3D LUTs; deinterlacing, inverse telecine and removing duplicate frames; denoising, sharpening and debanding; logo overlay and removal; burned-in subtitles; blurring a region; zoom; image stabilization; applying any filter to a time range only |
| Frame rate | converting to a new frame rate, up or down, by dropping and repeating frames, by blending neighboring frames, or by motion interpolation (Avidemux's "Resample FPS") |
| Chroma key | replacing a green screen with an image |
| Tools | saving one full-resolution frame as an image; finding black frames and scene cuts; listing the time and type of every frame |
| Projects | saving and reloading an edit as a list of `render` ops |

### Other planned features

These features go beyond Avidemux.

| Feature | What it adds |
|---|---|
| Motion blur | blur from averaging motion-interpolated frames between the real ones, as a longer camera shutter would; it works with or without lowering the frame rate. Avidemux's blend mode averages only the existing frames, which leaves ghosts on fast motion. |
| Keying onto video | chroma key with another clip as the background, and removing green spill from the edges |
| Transitions | crossfades, dissolves and wipes at the junctions of `concat`, with the audio crossfaded to match |
| Layering | picture-in-picture, split screens, and grids of different clips playing together |
| Text | titles and captions drawn on the video between chosen times |
| Speed ramps | speed that changes smoothly over time, and freeze frames that hold one frame for a set time |
| Stills | turning an image into a clip, with an optional slow pan and zoom |
| Aspect conversion | fitting a clip to a new aspect ratio by placing it over a blurred, enlarged copy of itself |
| Audio mixing | background music that gets quieter under speech; audio fades; finding and removing silence; normalizing loudness to a platform's target |
| GIF export | GIFs that use a palette generated from the clip, for better colors |
| Analysis | per-frame motion from the decoder's motion vectors, to find frames worth repeating or cutting on; a difference score (such as SSIM) between two frames, to check loop seams and compare versions |
| Frame-level edits | reversing or shuffling the order of compressed frames; running `drop_iframes` and `repeat_pframes` on H.264 files without `prepare` |
