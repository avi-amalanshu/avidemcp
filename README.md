# avidemcp

avidemcp is an MCP server for editing video files on your computer. MCP, the Model Context
Protocol, lets AI assistants such as Claude call tools that other programs provide. Once you
register the server, you can ask Claude to edit a video, and Claude calls avidemcp's tools to do
the work. The server has no user interface of its own.

The tools inspect clips, trim them, cut ranges out of them, change their speed, play them
backwards, crop and scale them, and join them. They can also edit a clip's compressed frames
without decoding them, as the free video editor Avidemux does in its copy mode. Datamoshing works
this way too. In a datamosh, compressed frames are deleted or repeated, so that the motion of one
shot drags the picture of another.

The `preview` tool returns a grid of frames from a clip as one image, so that Claude can look at
the result of each step. Over time, avidemcp is meant to match the features of Avidemux, and the
[roadmap](#roadmap) lists what is still missing.

## Requirements

You install two programs yourself: uv and git. uv is a package manager for Python. It downloads
Python and the packages that avidemcp needs, and those packages include FFmpeg.

| Requirement | Versions | Notes |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | any recent version; tested with 0.13 | installs Python and the packages, and runs the server |
| Python | 3.12 to 3.14 | uv downloads it if you don't have it |
| `mcp`, the MCP SDK for Python | `>=2.3,<3` | the server uses the 2.x API, so version 1.x won't work |
| `av` (PyAV) | `>=19,<20` | its wheels include their own FFmpeg libraries |
| `imageio-ffmpeg` | `>=0.8,<0.9` | includes an `ffmpeg` program (FFmpeg 9.0) |
| `numpy` | `>=2,<3` | assembles the grids of frames |
| Claude Code | any version that supports MCP | Claude Desktop and other MCP clients that use stdio also work |

The tests ran on the versions that `uv.lock` pins: av 19.0.2, imageio-ffmpeg 0.8.1, mcp 2.3.0 and
numpy 2.5.4.

### FFmpeg

You don't need to install FFmpeg. The server runs the first `ffmpeg` program that it finds, in
this order:

1. the path in the environment variable `AVIDEMCP_FFMPEG`
2. `ffmpeg` on your `PATH`
3. the copy that comes with imageio-ffmpeg

If the server uses an FFmpeg that you installed, that FFmpeg needs these parts:

| Part | Needed by |
|---|---|
| FFmpeg 6 or later (9.0 is the tested version) | every tool |
| the `libx264` encoder | every tool that re-encodes |
| the `mpeg4` encoder, which every build of FFmpeg includes | `prepare` |
| the `zscale` filter (libzimg) | converting HDR video to SDR; without it, HDR video passes through unchanged |

### Platforms

| Platform | Status |
|---|---|
| macOS 14 or later on Apple Silicon | tested |
| macOS 11 or later on Intel | untested; every dependency has prebuilt wheels |
| Linux on x86_64 or aarch64, with glibc 2.28 or later | untested; every dependency has prebuilt wheels |
| Windows on x64 or ARM64 | untested; every dependency has prebuilt wheels |
| Alpine Linux (musl), and 32-bit ARM | untested; imageio-ffmpeg has no `ffmpeg` program for these, so install FFmpeg yourself and set `AVIDEMCP_FFMPEG` to its path |

Only the macOS build of the bundled FFmpeg has been checked for `libx264` and `zscale`. The builds
for other platforms might lack them.

## Set up avidemcp with Claude Code

1. Install uv, unless `uv --version` already works.

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS / Linux
   # or: brew install uv
   # Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Clone the repository and install its dependencies. This downloads about 100 MB, FFmpeg
   included.

   ```bash
   git clone https://github.com/avi-amalanshu/avidemcp.git
   cd avidemcp
   uv sync
   uv run pytest -q          # optional; runs the tests in a few seconds
   ```

3. Register the server with Claude Code in one of two ways.
   - To use the server only in this project, start `claude` in the `avidemcp` folder. Claude Code
     reads the `.mcp.json` file in the repository and prompts you once to approve the server.
   - To use the server in every project, run this command from any folder, with the absolute path
     of your clone:

     ```bash
     claude mcp add --scope user avidemcp -- uv run --directory /absolute/path/to/avidemcp avidemcp
     ```

To check that Claude Code can see the server, run `claude mcp list`, or type `/mcp` in a session.
Then ask Claude for an edit. Here are three examples:

> Trim ~/Movies/clip.mov to 0:12-0:40, crop it to 4:5 for Instagram, and show me a preview.

> Join these three clips into one 1080x1350 video and slow the last two seconds to half speed.

> Make a boomerang from ~/Movies/wave.mov that loops seamlessly.

### Claude Desktop

Claude Desktop runs the server with the same command. Add this entry to its
`claude_desktop_config.json` file:

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

Desktop apps sometimes start without the `PATH` that your shell sets. If Claude Desktop can't find
`uv`, put the full path that `which uv` prints in `command`.

### Files and long jobs

The server reads and writes files only on your computer, and it uploads nothing. No tool changes
the file that you give it.

Each tool writes its result to a new file. When you don't give an `output` path, the file goes
next to the input and gets the name `<stem>.<op>.<ext>`, such as `clip.trim.mp4`. If that name is
taken, the server adds `.2`, `.3` and so on, so a name made this way never replaces an existing
file. When you do give an `output` path, the server writes to it as given and replaces any file
that is already there.

Tools that re-encode report their progress while they run. A long job can run past Claude Code's
time limit for MCP tools. To raise the limit to 30 minutes, start Claude Code with
`MCP_TOOL_TIMEOUT=1800000 claude`.

## Tools

| Tool | What it does |
|---|---|
| `probe` | reports a file's duration, streams, frame rate and number of frames, and the times of its I-frames (keyframes) |
| `preview` | returns one PNG image with a grid of evenly spaced frames, and the time of each frame |
| `trim` | keeps one range of a clip |
| `cut` | removes one range of a clip and joins the parts on either side of it |
| `speed` | plays a clip faster or slower; the audio can keep its pitch, change pitch with the speed, or be dropped |
| `reverse` | plays a clip backwards, a few seconds at a time, so that long and 4K clips fit in memory |
| `render` | applies a list of edits to one file with a single re-encode; the edits are trim, cut, speed, reverse, crop and scale |
| `concat` | joins clips with a single re-encode, like Avidemux's Append command; each clip can have its own list of edits, and the result gives the time where each clip starts |
| `bake` | re-encodes any file to an ordinary MP4 with H.264 video and AAC audio |
| `prepare` | re-encodes a clip so that it has only I-frames and P-frames, with I-frames only at the times you choose |
| `drop_iframes` | deletes the I-frames in a range without decoding the video, so that the frames after each one are built on the wrong picture |
| `repeat_pframes` | plays one P-frame, or a short run of them, several times without decoding the video, so that its motion builds up |

The tools that re-encode write MP4 files with H.264 video and AAC audio. `prepare` is the
exception; it writes MPEG-4 Part 2 video in an MKV file.

By default, `trim`, `cut` and `speed` re-encode, which makes them exact to the frame. With
`mode="copy"`, they copy the compressed video instead, which takes seconds and loses no quality.
Copied video can only start cleanly on an I-frame. In copy mode, `trim` therefore starts at the
I-frame before `start`, and `cut` resumes at the I-frame after `end`. With `snap=false`, they keep
the cut where you put it, and the frames after the cut lose the picture that they were built on.

Most frames in a compressed video store only changes. An I-frame holds a whole picture, and a
P-frame holds the motion and the corrections that turn the previous picture into the next one.
`drop_iframes` and `repeat_pframes` work on these compressed frames, which is what makes a
datamosh possible. Both of them need a file from `prepare`, and `bake` turns their output into an
ordinary video.

## Documentation

[AGENTS.md](AGENTS.md) is the reference that agents read. It lists the rules that every tool
follows and gives one line per tool. It also indexes the [docs/](docs/) folder, which has a page for
each tool with its arguments, its defaults, and advice on when to use it. The pages are arranged as
a binary tree, and each page has a one-line summary. An agent can therefore keep AGENTS.md in its
context and open only the pages that it needs.

[EXAMPLES.md](EXAMPLES.md) shows how to combine the tools and explains each choice. It has recipes
for editing and a [datamoshing tutorial](EXAMPLES.md#tutorial-an-i-frame-transition-between-two-clips),
along with the settings and lessons from datamoshing real footage.

The server also publishes these files as MCP resources, such as `avidemcp://docs/AGENTS.md`. Every
MCP client receives the server's instructions when it connects, and those instructions name these
resources. An agent can therefore read the documentation from any folder.

## How it works

avidemcp edits video in two ways, which match the two kinds of output in Avidemux. Some edits copy
the compressed video and change only which packets play and when. Other edits decode the video,
filter it and encode it again.

`packets.py` makes the first kind of edit with PyAV. It reads a file's packets into a table without
decoding them. Each edit is a pure function that takes a plan and returns a new one, where a plan
lists which source packet plays at which output time. One streaming pass then writes the plan to a
file. `drop_iframes`, `repeat_pframes`, and the copy modes of `trim` and `cut` work this way, so
they lose no quality.

`ops.py`, `graph.py` and `jobs.py` make the second kind of edit with FFmpeg's command-line
program. Each edit is a pydantic model, and one rule in `graph.link` turns it into part of the
filtergraph that FFmpeg runs. `render` runs a whole list of edits as one filtergraph, so the video is
decoded and encoded only once. A new edit of this kind takes one model and one rule.

## Development

```bash
uv sync && uv run pytest -q
```

The tests create their own video clips with FFmpeg while they run, so the repository holds no video
files.

## Roadmap

### Features that Avidemux has

Avidemux 2.8 has the following features, and avidemcp doesn't have them yet.

- A choice of output for every tool that re-encodes. All of these tools write H.264 video and AAC
  audio in MP4 today. Each call would set:
  - a video encoder: copy, H.264, H.265, MPEG-4 ASP, VP9, AV1, FFV1, HuffYUV, ProRes or DNxHD
  - a way to control the bitrate: a quality level, a target bitrate, or two passes
  - an audio encoder and its bitrate: copy, AAC, MP3, Opus, Vorbis, AC3, FLAC, PCM, or no audio
  - a container: MP4, MKV, WebM, MOV, AVI or MPEG-TS, with a check that the chosen codecs fit in it
- More edits without re-encoding. `concat` would copy the video when the clips' streams match.
  Copy mode would keep several ranges in one pass, and it would copy the audio while the video is
  re-encoded.
- More control over audio. You could choose a track or keep all of them, add or replace a track
  from another file, and delay the audio to fix its sync with the video. Gain, normalization,
  mixing down to stereo or mono, and resampling would also be available.
- New video filters would do the following:
  - rotating by 90 or 180 degrees, or by any angle
  - flipping and mirroring
  - adding borders, and resizing with padding to fit a given size
  - fading in and fading out
  - adjusting brightness, contrast, saturation, hue and color balance, and applying 3D lookup
    tables (LUTs)
  - deinterlacing, inverse telecine, and removing duplicate frames
  - removing noise, sharpening, and removing color banding
  - adding a logo, and removing one
  - burning in subtitles
  - blurring one region of the frame
  - zooming in
  - stabilizing shaky footage
  - applying any filter to one range of time only
- Converting a clip to a higher or lower frame rate. The conversion would drop and repeat frames,
  blend neighboring frames, or use motion interpolation. Avidemux calls this filter Resample FPS.
- Chroma keying, which replaces a green screen with a still image.
- Small tools that save one frame as an image at full resolution, find black frames and scene cuts,
  and list the time and type of every frame.
- Project files that store an edit as a list of `render` edits, so that it can be loaded and
  changed later.

### Other planned features

These features go beyond what Avidemux does.

- Motion blur that averages motion-interpolated frames between the real ones, the way a longer
  camera shutter blurs motion. It would work whether or not the frame rate goes down. Avidemux's
  blend mode averages only the existing frames, which leaves ghost images on fast motion.
- Chroma keying with a video as the background, and removal of the green that spills onto the edges
  of the subject.
- Transitions where `concat` joins two clips: crossfades, dissolves and wipes, with the audio
  crossfaded to match.
- Several clips on screen at once, as picture-in-picture, split screens or grids.
- Titles and captions drawn on the video between chosen times.
- Speed that changes smoothly over time, and freeze frames that hold one frame for a set time.
- Clips made from still images, with an optional slow pan and zoom.
- A new aspect ratio for a clip, made by placing the clip over a blurred, enlarged copy of itself.
- Audio mixing that lowers background music while someone speaks, fades audio in and out, removes
  silent stretches, and normalizes loudness to the target of a platform.
- GIF export with a palette made from the clip, which gives better colors.
- An analysis tool that reports how much each frame moves, using the motion vectors that the
  decoder exports. It would help find frames worth repeating or cutting on. It would also score how
  much two frames differ, for example with SSIM, to check the seams of loops and to compare
  versions of an edit.
- More edits of compressed frames: reversing or shuffling their order, and running `drop_iframes`
  and `repeat_pframes` on H.264 files without `prepare`.
