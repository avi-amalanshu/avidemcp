# Examples: chaining avidemcp tools

> Worked recipes that chain the tools into finished effects, with the reasoning behind each choice: editing recipes, then datamoshing as one example worked through in depth.

Each recipe lists its calls in order, then explains the choices. Calls are written
`tool {JSON arguments}`, file names are placeholders, and each tool's own doc is linked from
[AGENTS.md](AGENTS.md). Values in the editing recipes are illustrative. The datamoshing recipes
rebuild videos made from iPhone footage while this project was developed; their times, counts and
settings were read back from the intermediate files of those renders. The source clips are
described rather than named.

Editing:
[Shorten a long clip without re-encoding](#shorten-a-long-clip-without-re-encoding) ·
[Time-lapse without re-encoding](#time-lapse-without-re-encoding) ·
[Reframe to 4:5 and slow only the ending](#reframe-to-45-and-slow-only-the-ending) ·
[Join clips shot in different orientations](#join-clips-shot-in-different-orientations) ·
[Boomerangs, full and partial](#boomerangs-full-and-partial) ·
[A seamless loop](#a-seamless-loop)

Datamoshing:
[How it works](#how-it-works) ·
[Settings that matter](#settings-that-matter) ·
[Tutorial: an I-frame transition](#tutorial-an-i-frame-transition-between-two-clips) ·
[A P-frame bloom](#a-p-frame-bloom) ·
[Repeat schedules](#repeat-schedules) ·
[Smear into a cut](#smear-into-a-cut) ·
[A moshed sandwich loop](#a-moshed-sandwich-loop) ·
[A multi-clip night loop](#a-multi-clip-night-loop) ·
[Moshing with a copy-mode cut](#moshing-with-a-copy-mode-cut) ·
[Checking a mosh](#checking-a-mosh) ·
[What worked and what didn't](#what-worked-and-what-didnt)

## Editing

### Shorten a long clip without re-encoding

```
probe {"input": "talk.mov"}
-> {"duration": 1800.2, "keyframes": [0.0, 1.0, 2.0, ...]}
trim {"input": "talk.mov", "start": 312, "end": 655, "mode": "copy"}
-> {"output": "talk.trim.mov", "kept": [[312.0, 655.0]]}
```

- Copy mode keeps the original quality and takes seconds on a long file.
- It can only start on an I-frame, so with I-frames every second the result starts at most a second
  early. `kept` says where it really starts.
- When the start must be frame-exact, copy-trim with a margin, then `trim` the short result in exact
  mode. Only the short part gets re-encoded.

### Time-lapse without re-encoding

```
speed {"input": "sky.mov", "factor": 8, "audio": "none", "mode": "copy"}
-> {"output": "sky.speed.mov", "duration": 75.0, "video": {"fps": 240.0, ...}}
```

- Copy mode keeps every frame and only rescales the timestamps, so the picture keeps its full
  quality. The frame rate is multiplied by the factor (30 fps becomes 240).
- Many players and sites drop frames above 60 fps. For a file that plays the same everywhere,
  speed it in exact mode instead, which keeps the source frame rate by dropping frames:
  `speed {"input": "sky.mov", "factor": 8, "audio": "none"}`.

### Reframe to 4:5 and slow only the ending

A portrait (1080x1920) pan that settles on its subject in its last second:

```
concat {"clips": [
  {"input": "pan.mov", "ops": [{"op": "trim", "end": 3.6},
                               {"op": "crop", "width": 1080, "height": 1350, "y": 60}]},
  {"input": "pan.mov", "ops": [{"op": "trim", "start": 3.6},
                               {"op": "crop", "width": 1080, "height": 1350, "y": 60},
                               {"op": "speed", "factor": 0.5}]}],
        "width": 1080, "height": 1350}
```

- `render` applies its ops to the whole timeline. To treat parts of one shot differently, use the
  shot twice in `concat`. The frames on either side of the join are consecutive, so the join can't
  be seen.
- Use the same crop on both parts, or the framing jumps at the join. `y` aims the window; when it is
  omitted, the window is centred.
- 1080x1350 (4:5) is Instagram's portrait size.
- Slowing a nearly still moment reads as stillness, which gives it room. For a moving pan, the
  partial boomerang below worked better.

### Join clips shot in different orientations

A portrait phone clip (1080x1920) followed by a landscape one (1920x1080), as one 4:5 video:

```
probe {"input": "street.mov"}
probe {"input": "park.mov"}
concat {"clips": [{"input": "street.mov"},
                  {"input": "park.mov", "ops": [{"op": "crop", "width": 864, "height": 1080, "x": 300}]}],
        "width": 1080, "height": 1350}
preview {"input": "street.concat.mp4", "count": 16}
```

- `concat` scales each clip to cover the output size and centre-crops it, so `street.mov` needs no
  ops.
- A centred crop of a landscape clip keeps its middle. When the subject is elsewhere, crop the clip
  yourself first: here a 4:5 window (864x1080) starting 300 px from the left.
- The output takes the first clip's frame rate, and a clip without sound gets silence, so mixed
  sources join without extra steps.

### Boomerangs, full and partial

```
concat {"clips": [{"input": "x.mov"}, {"input": "x.mov", "ops": [{"op": "reverse"}]}]}

concat {"clips": [{"input": "x.mov"},
                  {"input": "x.mov", "ops": [{"op": "trim", "start": 3.6}, {"op": "reverse"}]},
                  {"input": "next.mov"}]}
```

- A full boomerang works on its own. Inside a longer piece, a forward-back-forward run looked like
  bouncing.
- A partial boomerang reverses for a moment and then cuts away to the next shot. The reversal reads
  as momentum, and the frame where it cuts away is a new place to mosh. Choose `start` in the
  reversed copy to land on the frame the next shot should meet.
- The turnaround isn't a cut: the picture continues. Don't key it for a mosh.

### A seamless loop

A sandwich (A, B, then A reversed), ending on A's first frame:

```
concat {"clips": [{"input": "a.mov", "ops": [{"op": "trim", "end": 6.6}]},
                  {"input": "b.mov"},
                  {"input": "a.mov", "ops": [{"op": "trim", "end": 15}, {"op": "reverse"}]}],
        "width": 1080, "height": 1350}
```

- The last frame played is `a.mov` at 0 s, which is also the first frame, so playback wraps
  without a jump.
- Both A parts need the same crop. Re-aiming either one breaks the seam.
- Check the seam: `preview` 0 to 0.1 s and the last 0.1 s; the first and last tiles should match.
  Measured outside the MCP, our loops had a mean pixel difference of 2.4-2.9 across the seam,
  against 17-20 between neighbouring frames of the moving shot.

## Datamoshing

Datamoshing breaks a video's frame references on purpose, so motion lands on the wrong picture. It
chains most of the tools: `concat` and `render` to assemble, `prepare` to make the frames
editable, `drop_iframes` and `repeat_pframes` to break them, `preview` to judge, `bake` to finish.

### How it works

- An I-frame stores a complete picture. A P-frame stores motion plus small corrections relative to
  the picture before it; the decoder builds it by moving pixels of the picture it already has.
- I-frame mosh (`drop_iframes`): delete the I-frame that starts a new shot, and the new shot's
  P-frames move the old shot's last picture. Call that picture the canvas and the new shot's motion
  the brush: the old image is dragged, swept or melted by the new movement.
- P-frame mosh (`repeat_pframes`): play one P-frame's motion again and again, and it builds into
  smears, streaks and blooms.
- Combined: a P-frame smear that runs straight into a dropped I-frame carries a melt across a cut.
- Why `prepare` first: phone H.264 and HEVC use B-frames, which store frames out of display order,
  and the encoder adds I-frames of its own. `prepare` removes both, so the only I-frames are the
  ones you place.
- Why a mosh fades: P-frames also contain intra blocks, coded from scratch, and each one repaints
  part of the canvas with the real new picture. Flat or noisy areas (snow, sky, walls) heal first.
  Any I-frame left in place ends the mosh at once.

Choosing the canvas and the brush:

- The canvas, the old shot's last frame, should be worth smearing: a clear subject, colour and
  contrast.
- A still camera with a moving subject paints that subject into the canvas, as with a hand rising
  into a frozen sunset. One steady pan sweeps the whole canvas sideways. A fast or shaky camera (15-28
  px per frame in our footage) wipes the canvas away into noise.
- A subject moving out of frame doesn't drag the canvas along. It uncovers the new shot behind it,
  leaving a subject-shaped window with blocky edges.

### Settings that matter

I-frames, placed with `prepare`'s `keyframes`, have two roles:

- Mosh points are the first frames of the shots whose motion should move the previous picture.
  Pass `concat`'s `junctions` unchanged, then delete these with `drop_iframes`.
- Reset points are I-frames you keep, so a mosh ends where you choose. Put one inside fast camera
  motion (a whip pan, a quick tilt, a swing from one side of the subject to another), where the jump
  from moshed to clean picture is lost in the motion. Keep it outside the `drop_iframes` range.
- Only real cuts are worth moshing. A boomerang's turnaround continues the same picture, so dropping
  its I-frame changes nothing.

`intra_penalty` on `prepare` sets how long the canvas survives:

| Value | Seen on our footage |
|---|---|
| 0 | snow repainted a moshed sunset within half a second |
| 300 | the canvas held through the cut, and the new shot was fully back about 2 s later; start here |
| 1000 | needed when a large subject arriving (a bus over a running cat) painted over the canvas at 300; pair it with a reset |
| 3000 | the mosh never cleared |

The value applies to the whole file. For a long hold at one cut and quick healing at another, put a
reset after the long one, or mosh the parts separately, bake them, and `concat`.

`timing` on `drop_iframes` and `repeat_pframes`:

- `keep` (the default) suits transitions and anything with sound worth keeping. On `drop_iframes`
  it costs a one-frame hold, which nobody sees.
- `shift` plays every repeat in full without eating the footage after it, but removes all audio.
  To keep the soundtrack elsewhere, mosh that part on its own, bake it, and `concat` it with the
  rest, which keeps its sound.

Blooms with `repeat_pframes`:

- The smear follows the motion in the repeated frame. Pick a frame of fast, even motion: a pan at
  full speed, a hand moving straight up. Narrow previews find it; look for the neighbouring tiles
  that differ most.
- About 8 plays (a quarter second at 30 fps) is an accent on a gesture; 30-45 plays make an obvious
  smear of 1-1.5 s, after which the normal frames paint the picture back.
- An irregular sideways gesture breaks into blocky fragments. A long inserted run on a frame with
  bright content streaks that content across the picture.

### Tutorial: an I-frame transition between two clips

The sources:

- `sunset.mov`: portrait iPhone HDR, 4.7 s. A pan along a railing that ends on the sun beside a
  tower.
- `hand.mov`: landscape, 14.4 s. A hand scoops snow. The camera holds still from 7.6 to 14.3 s.

The goal is a hand that rises into the frozen sunset and closes around the sun.

1. Look at both.

   ```
   probe {"input": "sunset.mov"}
   preview {"input": "sunset.mov"}
   probe {"input": "hand.mov"}
   preview {"input": "hand.mov"}
   ```

2. Choose the canvas and the brush ([How it works](#how-it-works)). The canvas is
   the last frame of the first clip; the sunset's last frame (sun and tower) is the strongest image
   in either clip. The brush is the motion of the second clip. Forward, the hand clip's camera moves
   15-28 px per frame during the scoop, which would wipe the canvas away. Its still stretch,
   reversed, shows the hand entering instead of leaving.

3. Join them in one encode, both fitted to the same frame.

   ```
   concat {"clips": [{"input": "sunset.mov"},
                     {"input": "hand.mov", "ops": [{"op": "trim", "start": 7.5, "end": 14.4},
                                                   {"op": "reverse"}]}],
           "width": 1080, "height": 1080, "output": "work/reach.mp4"}
   -> {"junctions": [4.7333]}
   ```

4. Prepare, with one I-frame on the junction and a strong hold.

   ```
   prepare {"input": "work/reach.mp4", "keyframes": [4.7333], "intra_penalty": 300}
   -> {"output": "work/reach.prep.mkv", "keyframes": [0.0, 4.733]}
   ```

5. Drop it, then look at the cut up close.

   ```
   drop_iframes {"input": "work/reach.prep.mkv", "start": 1}
   -> {"output": "work/reach.prep.drop.mkv", "dropped": [4.733]}
   preview {"input": "work/reach.prep.drop.mkv", "start": 4.5, "end": 7, "count": 16}
   ```

   After 4.73 s the sunset holds still, and the rising hand pushes its pixels upward.

6. Add an accent: replay the frame where the fingertips close around the sun, 8 times.

   ```
   repeat_pframes {"input": "work/reach.prep.drop.mkv", "at": 4.96, "times": 8}
   -> {"output": "work/reach.prep.drop.bloom.mkv", "frame": 4.967}
   ```

7. Bake.

   ```
   bake {"input": "work/reach.prep.drop.bloom.mkv", "output": "reach_for_the_sun.mp4"}
   ```

Versions we rejected along the way:

- With the default `intra_penalty` (0), snow repainted the sunset within half a second.
- A 15-play bloom inserted with `shift` streaked white snow into the sky.
- A bloom on the hand's sideways swing (5.53 s) broke into blocky fragments.
- The other order (hand first, then sunset) works differently. The open snowy palm is the canvas,
  and the pan's single leftward sweep drags it into the shrubs. At `intra_penalty` 3000 that version
  never recovered; at 300 the sunset was clean again about 2 s after the cut.
- A hand boomerang as the brush (rise, then withdraw at half speed) was meant to drag the sun down.
  The hand left a hand-shaped window onto the snowfield instead.

### A P-frame bloom

A demonstration of the P-frame mosh on its own, using `sunset.mov` from the tutorial:

```
prepare {"input": "sunset.mov", "keyframes": "none"}
repeat_pframes {"input": "sunset.prep.mkv", "at": 1.3, "times": 45}
-> {"output": "sunset.prep.bloom.mkv", "frame": 1.3}
bake {"input": "sunset.prep.bloom.mkv"}
```

- 1.3 s is the fastest part of the pan, about 26 px of leftward motion per frame. Each of the 45
  plays pushes the picture left again, so the scene smears into longer and longer horizontal
  streaks for about 1.5 s.
- When normal frames resume (around 2.8 s), the real sunset paints back in over the smear.
- `keep` timing overwrote the frames after the run, so the length and the audio are unchanged.
- The I-frame mosh in the tutorial and this bloom are the two basic moves. Every recipe below
  combines them.

### Repeat schedules

The source is `cat.mp4`: portrait, 30 fps, 8.6 s, no audio. At 4.233 s (frame `p`) the cat turns
right and the camera following it speeds up from 22 to 67 px per frame.

Two schedules of growing repeats:

| Schedule | Frames (times played) | Result |
|---|---|---|
| Doubling | `p` (2), `p+2` (4), `p+6` (8), `p+14` (16), `p+30` (32) | separate smear pulses while the cat trots; it stays recognisable. The last run stretches the ground into coloured streaks that stay to the end. |
| Stacked | `p` (2), `p+1` (4), `p+2` (8), `p+3` (16), `p+4` (32) | one smear that grows from 4.3 to 6.4 s; the cat dissolves into horizontal streaks, then the real cat runs back out of it |

The stacked schedule, applied from the last repeat to the first, each call on the previous output:

```
prepare {"input": "cat.mp4", "keyframes": "none", "intra_penalty": 300, "output": "work/cat.prep.mkv"}
repeat_pframes {"input": "work/cat.prep.mkv", "at": 4.362, "times": 32, "timing": "shift", "output": "work/s4.mkv"}
repeat_pframes {"input": "work/s4.mkv", "at": 4.328, "times": 16, "timing": "shift", "output": "work/s3.mkv"}
repeat_pframes {"input": "work/s3.mkv", "at": 4.295, "times": 8, "timing": "shift", "output": "work/s2.mkv"}
repeat_pframes {"input": "work/s2.mkv", "at": 4.262, "times": 4, "timing": "shift", "output": "work/s1.mkv"}
repeat_pframes {"input": "work/s1.mkv", "at": 4.228, "times": 2, "timing": "shift", "output": "work/s0.mkv"}
bake {"input": "work/s0.mkv", "output": "stacked.mp4"}
```

- Frame `p+k` is at `(127 + k) / 30` s. Each `at` is 5 ms early, so it can't miss its frame.
- `shift` plays every run in full. The clip has no audio, so inserting frames costs nothing; both
  versions grew by 57 frames (1.9 s).
- Applying the latest repeat first keeps the earlier `at` times valid. The stacked runs overlap, so
  `keep` timing would repeat copies instead of the original frames
  ([repeat_pframes](docs/1111-repeat-pframes.md)).
- The doubling schedule is built the same way, with `at` 5.228, 4.695, 4.428, 4.295 and 4.228.

### Smear into a cut

The goal: the cat's smear melts straight into a second shot, `bus.mov` (portrait iPhone HDR,
5.6 s). A bus drives through, the camera swings from its side to its rear, zooms in on the rear,
then whips down to the road.

```
repeat_pframes {"input": "work/cat.prep.mkv", "at": 4.395, "times": 64, "timing": "shift", "output": "work/m5.mkv"}
repeat_pframes {"input": "work/m5.mkv", "at": 4.362, "times": 32, "timing": "shift", "output": "work/m4.mkv"}
repeat_pframes {"input": "work/m4.mkv", "at": 4.328, "times": 16, "timing": "shift", "output": "work/m3.mkv"}
repeat_pframes {"input": "work/m3.mkv", "at": 4.295, "times": 8, "timing": "shift", "output": "work/m2.mkv"}
repeat_pframes {"input": "work/m2.mkv", "at": 4.262, "times": 4, "timing": "shift", "output": "work/m1.mkv"}
repeat_pframes {"input": "work/m1.mkv", "at": 4.228, "times": 2, "timing": "shift", "output": "work/m0.mkv"}
bake {"input": "work/m0.mkv", "output": "work/cat.smear.mp4"}
concat {"clips": [{"input": "work/cat.smear.mp4", "ops": [{"op": "trim", "end": 7.4}]},
                  {"input": "bus.mov", "ops": [{"op": "trim", "start": 0.3}]}],
        "output": "work/melt.mp4"}
-> {"junctions": [7.4]}
prepare {"input": "work/melt.mp4", "keyframes": [7.4, 9.8], "intra_penalty": 1000}
drop_iframes {"input": "work/melt.prep.mkv", "start": 7.35, "end": 7.45}
-> {"dropped": [7.4]}
bake {"input": "work/melt.prep.drop.mkv", "output": "cat_melts_into_bus.mp4"}
```

The first version ended the cat's smear before the bus arrived, and the two effects felt separate.
Three changes joined them:

- A longer smear. The stacked schedule gets one more step, `p+5` x64, which keeps the smear going
  from 4.3 s through the cut. It is the latest frame, so it is applied first and the schedule is
  rebuilt from the prepared clip.
- The cat cut early. The cut at 7.4 s falls about 1 s into the last run, while the cat is still a
  dark silhouette inside the streaks.
- The bus started late. Starting 0.3 s in, the bus is already moving through the frame. It takes
  shape inside the cat's streaks and is sharp by about 8.6 s.

Other settings:

- `intra_penalty` 1000: at 300 the arriving bus simply painted over the cat.
- A reset I-frame at 9.8 s, where the camera swings from the bus's side to its rear, kept out of
  the drop range. Without it, dark bars from a gate stayed in the sky through the zoom. With it,
  the zoom and the whip play clean, and the last frame matches the clean footage (mean difference
  1.6). The reset costs one visible change: a dark band in the sky turns blue on a single frame, in
  the middle of the swing.
- The bus runs to its real end. "Stable by the end" meant the mosh should settle, not that the
  clip should stop at the zoom.
- Bake before the second `concat`. It freezes the smear into plain frames, so `prepare` can treat it
  as ordinary footage. The silent cat part stays silent, and the bus keeps its sound.

### A moshed sandwich loop

Snowball, sunset, snowball: a 4:5 loop of about 31 s with three moshed cuts and a bloom. It uses
`sunset.mov` from the tutorial and `hand.mov` (landscape, 1920x1080). That clip opens on an empty
snowfield; a hand arrives, scoops a snowball, holds it, and later shows an open palm.

```
concat {"clips": [
  {"input": "hand.mov", "ops": [{"op": "trim", "end": 6.6},
                                {"op": "crop", "width": 864, "height": 1080, "x": 1056, "y": 0}]},
  {"input": "hand.mov", "ops": [{"op": "trim", "start": 11.6, "end": 13.3},
                                {"op": "crop", "width": 864, "height": 1080, "x": 1056, "y": 0},
                                {"op": "speed", "factor": 0.5}]},
  {"input": "sunset.mov", "ops": [{"op": "crop", "width": 1080, "height": 1350, "x": 0, "y": 60}]},
  {"input": "sunset.mov", "ops": [{"op": "trim", "start": 3.6},
                                  {"op": "crop", "width": 1080, "height": 1350, "x": 0, "y": 60},
                                  {"op": "reverse"}]},
  {"input": "hand.mov", "ops": [{"op": "trim", "end": 15},
                                {"op": "crop", "width": 864, "height": 1080, "x": 1056, "y": 0},
                                {"op": "reverse"}]}],
        "width": 1080, "height": 1350, "output": "work/loop.mp4"}
-> {"junctions": [6.6, 10.0, 14.7333, 15.8667]}
prepare {"input": "work/loop.mp4", "keyframes": [6.6, 10.0, 15.8667], "intra_penalty": 300}
drop_iframes {"input": "work/loop.prep.mkv", "start": 0.5}
-> {"dropped": [6.6, 10.0, 15.867]}
repeat_pframes {"input": "work/loop.prep.drop.mkv", "at": 16.695, "times": 8}
bake {"input": "work/loop.prep.drop.bloom.mkv", "output": "loop_snow_sunset_snow.mp4"}
```

What plays:

1. The empty snowfield; the hand arrives and scoops a snowball.
2. At the cut (6.6 s) the fingers open on a bare palm, and the snowball dissolves into speckles in
   place. The palm plays at half speed.
3. At 10.0 s the palm is swept into the sunset pan and melts into the shrubs; the sunset recovers.
4. The pan reverses for 1.1 s, then cuts (15.87 s) to the hand rising. The reversal's momentum
   carries through the cut: the sunset keeps sliding and smears into horizontal streaks as the hand
   rises, and the bloom at 16.7 s stretches it upward.
5. The whole hand clip plays backwards: the snow gathers, the hand leaves, and the last frame is
   the first.

Choices:

- The snow vanishing. The cut goes from holding the snowball (6.6 s) to the open palm (11.6 s).
  The palm time was chosen so the palm sits where the snowball was: at 10.8 s it was 210 px off;
  at 11.6 s it is almost exactly in place. Moving the cut point aligned it. Re-cropping would have
  broken the loop, which needs the same crop on its first and last frames.
- Pacing. Earlier versions felt rushed. This one keeps the 4 s of empty snowfield at the start,
  slows the palm to half speed, and plays the sunset pan in full.
- The sunset's ending. A slowed ending (0.5) kept the sun still but felt like padding. A full
  forward-back-forward boomerang looked like bouncing. The partial reverse that cuts away won. The
  further it reverses, the further the sun drifts from where the hand rises: reversing to 3.6 s
  puts the hand just beside the sun, and 3.2 s sends it toward a lamp post.
- Only real cuts are keyed. The turnaround at 14.73 s, where the sunset starts reversing, is left
  out of `keyframes`.
- The bloom. 8 plays at the frame of fastest upward hand motion, between 0.3 and 2 s after the last
  cut.
- The seam measured 2.4-2.9 (mean pixel difference), against 17-20 between neighbouring frames of
  the moving shot.
- An earlier square (1:1) crop felt too tight. 4:5 fits a phone screen better.

### A multi-clip night loop

Three night clips with no shared subject, linked by mood:

- `gym.mov` (29.97 fps, 4.9 s): the camera tilts up from the floor to bright windows and machines,
  then holds still.
- `sidewalk.mov` (2 s): a blurry whip pan that settles on a snowy sidewalk under streetlights. Its
  header claims 120 fps, but it holds 50 frames.
- `snowfall.mov` (7 s): snow falling on a tree; the camera tilts down past a streetlight and a car
  to footprints.

First, the gym moshed into the sidewalk played backwards, with a stacked smear on the reversed
whip:

```
concat {"clips": [
  {"input": "gym.mov"},
  {"input": "sidewalk.mov", "ops": [{"op": "trim", "start": 0.45}, {"op": "reverse"}, {"op": "speed", "factor": 0.5}]},
  {"input": "sidewalk.mov", "ops": [{"op": "trim", "end": 0.45}, {"op": "reverse"}]}],
        "width": 1080, "height": 1350, "output": "work/a.mp4"}
-> {"junctions": [4.872, ...]}
prepare {"input": "work/a.mp4", "keyframes": [4.872], "intra_penalty": 300}
drop_iframes {"input": "work/a.prep.mkv", "start": 1, "output": "work/a.drop.mkv"}
repeat_pframes {"input": "work/a.drop.mkv", "at": 8.37, "times": 32, "timing": "shift", "output": "work/a4.mkv"}
repeat_pframes {"input": "work/a4.mkv", "at": 8.337, "times": 16, "timing": "shift", "output": "work/a3.mkv"}
repeat_pframes {"input": "work/a3.mkv", "at": 8.303, "times": 8, "timing": "shift", "output": "work/a2.mkv"}
repeat_pframes {"input": "work/a2.mkv", "at": 8.27, "times": 4, "timing": "shift", "output": "work/a1.mkv"}
repeat_pframes {"input": "work/a1.mkv", "at": 8.237, "times": 2, "timing": "shift", "output": "work/a0.mkv"}
bake {"input": "work/a0.mkv", "output": "work/a.smear.mp4"}
```

Then the whole loop, cut mid-smear into the snowfall:

```
concat {"clips": [{"input": "work/a.smear.mp4", "ops": [{"op": "trim", "end": 9.4}]},
                  {"input": "snowfall.mov"},
                  {"input": "gym.mov", "ops": [{"op": "reverse"}]}],
        "width": 1080, "height": 1350, "output": "work/night.mp4"}
-> {"junctions": [9.4094, 16.4498]}
prepare {"input": "work/night.mp4", "keyframes": [9.4094, 16.4498, 21.02], "intra_penalty": 300}
drop_iframes {"input": "work/night.prep.mkv", "start": 1, "end": 21}
-> {"dropped": [9.409, 16.45]}
bake {"input": "work/night.prep.drop.mkv", "output": "night_loop.mp4"}
```

What plays (21 s):

1. The gym's tilt, then about 3.5 s of stillness.
2. The cut into the sidewalk. Its motion is calm, so the gym stays frozen while the night street
   builds up over it block by block.
3. The reversed whip smears in five growing runs, and the piece cuts mid-smear to the snowfall:
   flakes fall through what's left of the smear.
4. The cut into the reversed gym: the footprints freeze while the gym builds up, and the tilt down
   lands on the floor that the loop opens with.

Choices:

- Clips were chosen by mood (winter night). Spring blossoms, a sunny lawn and a daytime tower
  were left out, and so was a static snowfall shot that repeated the other.
- `sidewalk.mov` was planned as 0.25 slow motion of 120 fps footage. Its 50 frames in 2 s are
  really about 24 fps, so 0.25 would have shown 6 new frames per second. Only the calm part was
  slowed, to 0.5, and the whip plays at real speed. `probe` now reports the measured rate for clips
  like this one.
- Smear into a cut again, as with the cat and the bus. The whip's frames are dark and blurry, so
  the repeats spread mostly brown blocks; a smear needs contrast to read well.
- A reset I-frame at 21.02 s, inside the final fast tilt (56-62 px per frame), clears what's left of
  the mosh before the loop point. The seam measured 4.9, against 4.0 for the same assembly without
  any mosh.
- The first part was baked before the second `concat`. Its shift-timing repeats removed its audio,
  so the first 9 s are silent, but the snowfall and the gym keep their sound.

### Moshing with a copy-mode cut

Within one shot, a copy-mode `cut` with `snap: false` makes an I-frame mosh in one lossless step:

```
prepare {"input": "hand.mov", "keyframes": "none", "intra_penalty": 300}
cut {"input": "hand.prep.mkv", "start": 6.6, "end": 11.6, "mode": "copy", "snap": false}
bake {"input": "hand.prep.cut.mkv"}
```

- The P-frames at 11.6 s now predict from the frame at 6.6 s, so the later motion moves the earlier
  picture, as at a dropped junction.
- This suits a cut inside one shot that needs no crop, speed change or reversal. The renders above
  needed those, so they used `concat` and `drop_iframes`; this route is untested on real footage.
- On raw phone footage, B-frames and frequent I-frames make the result shorter and harder to
  predict, so prepare first.

### Checking a mosh

1. After `prepare`: its `keyframes` are `0.0` plus your times, nothing else.
2. After `drop_iframes`: `dropped` lists exactly the mosh points, and `probe` still shows each
   reset.
3. Preview each mosh point from 0.2 s before the cut to about 2 s after it (`count` 12-16). Look for
   the canvas holding on the first frames, the new motion moving it, and the moment the new shot is
   fully back.
4. Preview each bloom over its run plus 1 s after.
5. For a loop, compare the first and last frames (see [A seamless loop](#a-seamless-loop)).
6. `bake`, then preview the MP4 at the same windows. It should match the MKV previews.

| What you see | Cause | Fix |
|---|---|---|
| The cut plays clean, no mosh | The I-frame isn't on the junction, or wasn't dropped | Prepare again with `concat`'s junction times as returned; check `dropped` |
| The canvas is gone within half a second | `intra_penalty` too low | 300 |
| The mosh never clears | `intra_penalty` too high and no reset | Lower it, or key a reset inside fast motion |
| The new shot paints over the canvas at once | A large moving subject at 300 | 1000, plus a reset |
| Leftover blocks or bars stay to the end | Nothing resets the mosh | A reset where the camera moves fast |
| The bloom breaks into blocks | The repeated frame's motion is irregular | A frame with fast, even motion |
| The bloom lands on the wrong frame | `at` fell just after the frame you meant | Pass a time a few ms earlier; check `frame` |
| No sound | `shift` timing removes all audio | `keep`, or mosh that part alone, bake it, `concat` |
| "run prepare first" | The file has B-frames | `prepare` |

### What worked and what didn't

These choices follow one person's taste over several sessions. Use them as defaults, not rules.

- Mosh on subjects people recognise, so the effect means something: a hand catches the sun, a
  snowball dissolves, a cat is swept into a bus.
- Leave room. Keep the empty stretches of the source, slow nearly still moments to 0.5, and lengthen
  with partial boomerangs instead of trimming tight. A rushed pace was the most common complaint.
- Build sandwiches and loops (A, B, A reversed), framed at 4:5 (1080x1350).
- Let a P-frame smear run straight into an I-frame cut.
- End clean: a reset I-frame inside fast motion, and a last shot that settles.
- Align a subject across a cut by choosing the cut time, not by re-cropping.

| Tried | What happened | What worked instead |
|---|---|---|
| `intra_penalty` 0 | the sunset was repainted within half a second | 300 |
| `intra_penalty` 3000 | the mosh never recovered | 300, which heals in about 2 s |
| 300 for a large subject arriving | the bus painted over the cat | 1000, plus a reset I-frame |
| no reset after a strong mosh | dark bars stayed in the sky through the zoom | a reset at the camera's swing |
| a fast-moving camera as the brush | the canvas was wiped away | a still-camera stretch, reversed |
| a bloom on a sideways swing | blocky fragments | a frame of even upward motion |
| a long inserted bloom on a bright frame | white snow streaked into the sky | 8 plays with `keep` |
| a full forward-back-forward boomerang | it looked like bouncing | a partial reverse that cuts away |
| a subject leaving as the brush | a subject-shaped window, no drag | a subject entering |
| 0.25 slow motion of a "120 fps" clip | it was 24 fps; it would stutter | check `fps`; 0.5 on calm parts |
| a smear that ended before the next shot | two separate effects | a longer smear, cut mid-smear |

Bloom frames and alignment points were found outside the MCP, from the decoder's motion vectors
(PyAV with `flags2=+export_mvs`) and a skin-colour search. With the MCP alone, narrow `preview`
windows find them more slowly.
