# Examples: chaining avidemcp tools

> Worked recipes that combine the tools into finished effects and explain each choice: editing recipes first, then datamoshing as one example in depth.

Each recipe lists its calls in order and then explains the choices behind them. A call is written
as `tool {JSON arguments}`, and `-> {...}` shows the result fields that matter. File names are
placeholders, and [AGENTS.md](AGENTS.md) links to each tool's own page.

The values in the editing recipes are made up for illustration. The datamoshing recipes rebuild
videos that were made from iPhone footage while this project was developed. Their times, counts and
settings come from the intermediate files of those renders, and the source clips are described
rather than named.

- [Editing](#editing)
  - [Shorten a long clip without re-encoding](#shorten-a-long-clip-without-re-encoding)
  - [Time-lapse without re-encoding](#time-lapse-without-re-encoding)
  - [Reframe to 4:5 and slow only the ending](#reframe-to-45-and-slow-only-the-ending)
  - [Join clips shot in different orientations](#join-clips-shot-in-different-orientations)
  - [Boomerangs, full and partial](#boomerangs-full-and-partial)
  - [A seamless loop](#a-seamless-loop)
- [Datamoshing](#datamoshing)
  - [How datamoshing works](#how-datamoshing-works)
  - [Settings for datamoshing](#settings-for-datamoshing)
  - [Tutorial: an I-frame transition between two clips](#tutorial-an-i-frame-transition-between-two-clips)
  - [A P-frame smear](#a-p-frame-smear)
  - [Repeat schedules](#repeat-schedules)
  - [A smear that runs into a cut](#a-smear-that-runs-into-a-cut)
  - [A moshed sandwich loop](#a-moshed-sandwich-loop)
  - [A multi-clip night loop](#a-multi-clip-night-loop)
  - [Moshing with a copy-mode cut](#moshing-with-a-copy-mode-cut)
  - [Checking a mosh](#checking-a-mosh)
  - [What worked and what didn't](#what-worked-and-what-didnt)

## Editing

### Shorten a long clip without re-encoding

```
probe {"input": "talk.mov"}
-> {"duration": 1800.2, "keyframes": [0.0, 1.0, 2.0, ...]}
trim {"input": "talk.mov", "start": 312, "end": 655, "mode": "copy"}
-> {"output": "talk.trim.mov", "kept": [[312.0, 655.0]]}
```

Copy mode keeps the original quality and finishes in seconds, even on a long file. It can only start
on an I-frame, so if the file has an I-frame every second, the result starts up to a second early;
`kept` gives the real start. When the start must be exact to the frame, copy-trim with a margin
first, and then `trim` the short result in exact mode, so that only the short part is re-encoded.

### Time-lapse without re-encoding

```
speed {"input": "sky.mov", "factor": 8, "audio": "none", "mode": "copy"}
-> {"output": "sky.speed.mov", "duration": 75.0, "video": {"fps": 240.0, ...}}
```

Copy mode keeps every frame and only rescales the timestamps. The picture keeps its full quality,
and the frame rate is multiplied by the factor, so 30 fps becomes 240 fps. Many players and sites
drop frames above 60 fps. For a file that plays the same everywhere, use exact mode, which keeps the
source frame rate by dropping frames: `speed {"input": "sky.mov", "factor": 8, "audio": "none"}`.

### Reframe to 4:5 and slow only the ending

The source is a portrait (1080x1920) pan that settles on its subject in its last second.

```
concat {"clips": [
  {"input": "pan.mov", "ops": [{"op": "trim", "end": 3.6},
                               {"op": "crop", "width": 1080, "height": 1350, "y": 60}]},
  {"input": "pan.mov", "ops": [{"op": "trim", "start": 3.6},
                               {"op": "crop", "width": 1080, "height": 1350, "y": 60},
                               {"op": "speed", "factor": 0.5}]}],
        "width": 1080, "height": 1350}
```

- `render` applies each op to the whole timeline, so to treat two parts of one shot differently,
  use the shot twice in `concat`. The frames on either side of the join are consecutive, so the
  join is invisible.
- Give both parts the same crop, or the framing jumps at the join. `y` sets the top edge of the
  window; without it, the window is centered.
- 1080x1350 (4:5) is Instagram's portrait size.
- Slowing a nearly still moment to half speed makes it look like a pause and gives it more time on
  screen. For a moving pan, the partial boomerang below worked better.

### Join clips shot in different orientations

This recipe joins a portrait phone clip (1080x1920) and a landscape one (1920x1080) into one 4:5
video.

```
probe {"input": "street.mov"}
probe {"input": "park.mov"}
concat {"clips": [{"input": "street.mov"},
                  {"input": "park.mov", "ops": [{"op": "crop", "width": 864, "height": 1080, "x": 300}]}],
        "width": 1080, "height": 1350}
preview {"input": "street.concat.mp4", "count": 16}
```

- `concat` scales each clip to cover the output size and crops away what sticks out on both sides,
  so `street.mov` needs no ops.
- That automatic crop keeps the middle of a landscape clip. When the subject is somewhere else, crop
  the clip yourself first; here the 4:5 window (864x1080) starts 300 px from the left edge.
- The output uses the first clip's frame rate, and a clip without sound gets silence, so clips from
  different sources join without extra steps.

### Boomerangs, full and partial

```
concat {"clips": [{"input": "x.mov"}, {"input": "x.mov", "ops": [{"op": "reverse"}]}]}

concat {"clips": [{"input": "x.mov"},
                  {"input": "x.mov", "ops": [{"op": "trim", "start": 3.6}, {"op": "reverse"}]},
                  {"input": "next.mov"}]}
```

- A full boomerang works well as a clip on its own. Inside a longer piece, a run that went forward,
  back and forward again looked like bouncing.
- A partial boomerang plays backwards for a moment and then cuts to the next shot. The reversal
  looks like momentum, and the frame where it cuts away is another place to mosh. Choose `start` in
  the reversed copy so that the copy ends on the frame where the next shot should begin.
- The turnaround isn't a cut, because the picture continues, so it gets no I-frame for a mosh.

### A seamless loop

This recipe builds a sandwich of A, B and A reversed, which ends on A's first frame.

```
concat {"clips": [{"input": "a.mov", "ops": [{"op": "trim", "end": 6.6}]},
                  {"input": "b.mov"},
                  {"input": "a.mov", "ops": [{"op": "trim", "end": 15}, {"op": "reverse"}]}],
        "width": 1080, "height": 1350}
```

- The last frame that plays is `a.mov` at 0 s, which is also the first frame, so playback wraps
  around without a jump.
- Both parts from A need the same crop; aiming either one differently breaks the seam.
- To check the seam, preview 0 to 0.1 s and the last 0.1 s; the first and last tiles should match.
  Measured outside the MCP, our loops had a mean pixel difference of 2.4-2.9 across the seam,
  compared with 17-20 between neighboring frames of the moving shot.

## Datamoshing

A datamosh breaks a video's frame references on purpose, so that motion is applied to the wrong
picture. It uses most of the tools: `concat` and `render` assemble the clips, `prepare` makes the
frames editable, `drop_iframes` and `repeat_pframes` break them, `preview` shows the result, and
`bake` turns it into an ordinary video.

### How datamoshing works

An I-frame stores a complete picture. A P-frame stores motion vectors and small corrections
relative to the picture before it, and the decoder builds it by moving pixels of the picture that
it already has.

There are two basic moshes, and they combine:

- `drop_iframes` deletes the I-frame that starts a new shot. The new shot's P-frames then move the
  old shot's last picture, so the old image is dragged, swept or melted by the new shot's movement.
- `repeat_pframes` plays one P-frame's motion over and over, and the motion builds up into smears
  and streaks, often called blooms. The tool repeats the compressed frame; repeating a decoded frame
  in an editor would only freeze the picture.
- A smear from repeated P-frames that runs straight into a dropped I-frame carries a melt across a
  cut.

#### What prepare does

Phone H.264 and HEVC use B-frames, which also predict from later frames. Their packets are stored
out of display order, so dropping or repeating packets gives unpredictable results, and
`drop_iframes` and `repeat_pframes` refuse files with B-frames.

`prepare` re-encodes a clip to MPEG-4 Part 2 with only I- and P-frames, at a constant frame rate,
with I-frames only at frame 0 and at the times you ask for. Without `prepare`, the encoder would add
I-frames of its own at scene changes and every 600 frames, and each of them would end a mosh.

The prepared file is an MKV intermediate. It is larger than the source, its HDR is already
converted to SDR, and it keeps the audio. Prepare once, and then mosh the prepared file as often as
you like: `drop_iframes` and `repeat_pframes` take seconds and never change their input, so trying
variations is cheap.

#### How a mosh clears

Each P-frame also contains some intra blocks, which are coded from scratch. Every intra block
replaces part of the old picture with the real new one, so a mosh clears over time. Flat or noisy
areas such as snow, sky and walls get the most intra blocks and clear first. `prepare`'s
`intra_penalty` controls how fast this happens; see [How long a mosh lasts](#how-long-a-mosh-lasts).

An I-frame left in place ends a mosh at once. Keeping an I-frame is therefore the way to end a mosh
at a chosen time; see [Where to put I-frames](#where-to-put-i-frames).

#### Choosing the clips

With `keep` timing, the frame before a dropped I-frame stays on screen for one extra frame, and then
the new shot's motion starts to move it. Two things decide how strong the effect is: the old shot's
last picture, which gets moved, and the new shot's motion, which moves it. `intra_penalty` and the
next kept I-frame decide how long the effect lasts.

- The old shot's last picture should be worth smearing, with a clear subject, color and contrast.
- A still camera with a moving subject moves pixels of the old picture in the subject's shape, as
  when a hand rises into a frozen sunset. One steady pan drags the whole old picture sideways. A
  fast or shaky camera (15-28 px per frame in our footage) smears the old picture into noise.
- A subject that moves out of frame doesn't drag the old picture with it. It uncovers the new shot
  behind it and leaves a window in the shape of the subject, with blocky edges.
- The old picture lasts longest where the new shot is still. Fast motion moves it out of the frame
  sooner.

### Settings for datamoshing

#### Where to put I-frames

`prepare`'s `keyframes` argument sets the only I-frames that the prepared file has besides frame 0.

- A list of times puts an I-frame on the first frame at or after each time. Use a list whenever you
  know where the cuts are, and pass `concat`'s `junctions` unchanged.
- `"scene"` detects hard cuts in a single file and puts I-frames there. Check the result, because
  the detection can miss a soft cut or trigger on a flash or a whip pan.
- `"none"` keeps only frame 0, so the clip becomes one long run of P-frames. Use it to repeat
  P-frames within a single shot; it leaves nothing for `drop_iframes` to delete.

Each I-frame is either one that you will drop or one that you will keep.

- Drop the I-frame at the start of each shot whose motion should move the previous picture.
- Keep an I-frame where a mosh should end. Put it inside fast camera motion, such as a whip pan, a
  quick tilt, or a swing from one side of the subject to another, where the motion hides the jump
  from the moshed picture to the clean one. Without such an I-frame, a mosh made with a high
  `intra_penalty` can last until the end of the file. Keep these I-frames outside the range that
  you pass to `drop_iframes`.
- Mosh only real cuts. A boomerang's turnaround continues the same picture, so dropping its I-frame
  changes nothing visible; leave it out of `keyframes`.

Run `prepare` after `concat` and `render`, never before them. Every re-encode after `prepare`
(`render`, `concat` or an exact `trim`) brings back B-frames and the encoder's own I-frames. Then
check the result's `keyframes`, which must be `0.0` plus your times. An I-frame that is one frame
away from a junction turns the mosh into a clean cut.

#### How long a mosh lasts

`prepare`'s `intra_penalty` (0-1000000, default 0) makes intra blocks more expensive for the
encoder, so that it keeps predicting from the old picture instead of repainting it.

| Value | What we saw on our footage |
|---|---|
| 0 | A faithful encode. Snow repainted a moshed sunset within half a second. On a flat, noisy test pattern, 99.6% of each frame was intra-coded. |
| 300 | The old picture stayed through the cut, and the new shot was fully back about 2 s later. Start here. |
| 1000 | Needed when the new shot covered the old picture too soon at 300, as when a bus drove in over a running cat. Use it together with a kept I-frame. |
| 3000+ | The new shot appeared only as faint traces, and without a kept I-frame the mosh never cleared. |

- Start at 300. If the new shot covers the old picture before the effect is visible, raise the
  value. If the mosh never clears, lower it, or keep an I-frame where the mosh should end.
- The value applies to the whole file. To make one cut last long and another clear quickly, keep an
  I-frame after the long one, or mosh the parts separately, bake them, and join them with `concat`.
- Trying values is cheap, because only `prepare` re-encodes. Prepare at two values, mosh both
  files, and preview them side by side.
- `quality` (1-31, default 3) sets the MPEG-4 quantizer of the prepared file; lower values give a
  sharper, larger file.

#### Keep or shift timing

Both `drop_iframes` and `repeat_pframes` take `"timing": "keep"` (the default) or `"shift"`.

| | `keep` | `shift` |
|---|---|---|
| `drop_iframes` | each dropped I-frame becomes a one-frame hold, and the duration doesn't change | the frames close up, and the clip gets one frame shorter per drop |
| `repeat_pframes` | the copies overwrite the frames after the run, the duration doesn't change, and copies past the end are cut off | the copies are inserted, and the clip gets `(times - 1) * span` frames longer |
| audio | kept in sync | removed from the whole output |

- Use `keep` for transitions and for anything whose sound you want to keep. For `drop_iframes` it is
  almost always the right choice, because nobody notices a one-frame hold.
- Use `shift` when every repeat must play in full without overwriting the footage after it, as in
  the classic bloom, and when the clip has no sound or you will replace the soundtrack.
- To use `shift` and still keep most of the soundtrack, mosh that part on its own, bake it (it will
  be silent), and then join it to the other parts with `concat`; they keep their audio. The
  [night loop](#a-multi-clip-night-loop) is built this way.

A clip with several repeats needs some planning.

- With `shift`, each repeat moves everything after it. Apply the repeats from the latest time to the
  earliest, so that the planned `at` times stay valid.
- With `keep`, a repeat overwrites the frames after its run, and a later repeat aimed at one of
  those frames repeats the copy instead of the original. Plan runs that don't overlap. The doubling
  schedule (`p` 2 times, `p+2` 4 times, `p+6` 8 times, `p+14` 16 times, `p+30` 32 times) fits
  exactly, because each run starts on the frame right after the previous run's copies.
- A stacked schedule on consecutive frames (`p` 2 times, `p+1` 4 times, `p+2` 8 times, and so on)
  overlaps itself, so it needs `shift`. See [Repeat schedules](#repeat-schedules).

#### Dropping I-frames

- Choose `start` and `end` so that the range covers only the I-frames to delete. When an I-frame to
  keep sits between two to delete, call `drop_iframes` twice, the second time on the first call's
  output.
- `start` 0.5 (any time after frame 0) with no `end` deletes the I-frame at every cut.
- Check that `dropped` lists exactly the I-frames that you meant to delete.

#### Choosing a P-frame to repeat

- The smear follows the motion in the repeated frame, so pick the frame where the motion is fastest
  and most even, such as a pan at full speed or a hand moving straight up. Narrow previews help you
  find it: look for the neighboring tiles that differ most.
- The smear runs in the direction of the motion. A rising hand stretches the picture upward (in our
  footage, a hand seemed to catch the sun), and a pan leaves horizontal streaks.
- An irregular sideways gesture breaks into blocky fragments instead of a smear.
- A long inserted run on a frame with bright content streaks that content across the picture, as
  when white snow streaked into a sky.
- To hit a given frame, pass a time a few milliseconds before it. Frame `n` of a 30 fps file starts
  at `n / 30` s, so pass `n / 30 - 0.005`. The times in `preview`'s list of tiles are frame times.
  Check the result's `frame`.
- An I-frame at `at` is skipped, and the next P-frame is used, because repeating an I-frame only
  freezes the picture.
- A `span` above 1 repeats a short run of frames, such as a whole gesture; the run stops at the
  next I-frame.

#### How many times to repeat it

- About 8 plays, a quarter of a second at 30 fps, mark a single gesture.
- 30-45 plays make an obvious smear of 1-1.5 s, after which the normal frames gradually restore the
  picture.
- A schedule repeats successive frames with growing counts (2, 4, 8, 16, 32 and 64 times). With
  doubling spacing (`p`, `p+2`, `p+6`, `p+14`, `p+30`), the smears come as separate pulses and the
  subject stays recognizable. With stacked spacing (`p`, `p+1`, `p+2`, and so on), they merge into
  one growing smear that dissolves the subject; this needs `shift`, applied from the last repeat to
  the first.
- With `keep`, copies past the end of the file are cut off. With `shift`, only the audio is lost.

### Tutorial: an I-frame transition between two clips

The tutorial uses two clips:

- `sunset.mov`, a 4.7 s portrait iPhone clip in HDR. It pans along a railing and ends on the sun
  beside a tower.
- `hand.mov`, a 14.4 s landscape clip. A hand scoops snow, and the camera holds still from 7.6 to
  14.3 s.

The goal is a hand that rises into the frozen sunset and closes around the sun.

1. Look at both clips.

   ```
   probe {"input": "sunset.mov"}
   preview {"input": "sunset.mov"}
   probe {"input": "hand.mov"}
   preview {"input": "hand.mov"}
   ```

2. Decide which picture gets moved and which motion moves it
   ([Choosing the clips](#choosing-the-clips)). The moved picture is the first clip's last frame,
   and the sunset's last frame, with the sun and the tower, is the strongest image in either clip.
   The motion comes from the second clip. Played forward, the hand clip's camera moves 15-28 px per
   frame during the scoop, which would smear the sunset into noise. Its still stretch, reversed,
   shows the hand entering the frame instead of leaving it.

3. Join the clips in one encode, both fitted to the same frame size.

   ```
   concat {"clips": [{"input": "sunset.mov"},
                     {"input": "hand.mov", "ops": [{"op": "trim", "start": 7.5, "end": 14.4},
                                                   {"op": "reverse"}]}],
           "width": 1080, "height": 1080, "output": "work/reach.mp4"}
   -> {"junctions": [4.7333]}
   ```

4. Prepare the result with one I-frame on the junction and `intra_penalty` 300.

   ```
   prepare {"input": "work/reach.mp4", "keyframes": [4.7333], "intra_penalty": 300}
   -> {"output": "work/reach.prep.mkv", "keyframes": [0.0, 4.733]}
   ```

5. Drop the I-frame, then look closely at the cut.

   ```
   drop_iframes {"input": "work/reach.prep.mkv", "start": 1}
   -> {"output": "work/reach.prep.drop.mkv", "dropped": [4.733]}
   preview {"input": "work/reach.prep.drop.mkv", "start": 4.5, "end": 7, "count": 16}
   ```

   After 4.73 s the sunset stays still, and the rising hand pushes its pixels upward.

6. Replay the frame where the fingertips close around the sun, 8 times.

   ```
   repeat_pframes {"input": "work/reach.prep.drop.mkv", "at": 4.96, "times": 8}
   -> {"output": "work/reach.prep.drop.bloom.mkv", "frame": 4.967}
   ```

7. Bake the result.

   ```
   bake {"input": "work/reach.prep.drop.bloom.mkv", "output": "reach_for_the_sun.mp4"}
   ```

We rejected these versions along the way:

- With the default `intra_penalty` of 0, snow repainted the sunset within half a second.
- A 15-play repeat inserted with `shift` streaked white snow into the sky.
- A repeat on the hand's sideways swing (5.53 s) broke into blocky fragments.
- With the clips in the other order (hand first, then sunset), the open snowy palm is the moved
  picture, and the pan's single sweep to the left drags it into the shrubs. At `intra_penalty` 3000
  that version never cleared; at 300 the sunset was clean again about 2 s after the cut.
- A hand boomerang, in which the hand rises and then withdraws at half speed, was meant to drag the
  sun down. Instead, the hand left a hand-shaped window onto the snowfield.

### A P-frame smear

This recipe shows the P-frame mosh by itself, on `sunset.mov` from the tutorial.

```
prepare {"input": "sunset.mov", "keyframes": "none"}
repeat_pframes {"input": "sunset.prep.mkv", "at": 1.3, "times": 45}
-> {"output": "sunset.prep.bloom.mkv", "frame": 1.3}
bake {"input": "sunset.prep.bloom.mkv"}
```

- At 1.3 s the pan is at its fastest, about 26 px per frame to the left. Each of the 45 plays pushes
  the picture left again, so the scene smears into longer and longer horizontal streaks for about
  1.5 s.
- When the normal frames resume, around 2.8 s, the real sunset gradually returns over the smear.
- With `keep` timing, the copies overwrote the frames after the run, so the length and the audio
  didn't change.
- The tutorial's dropped I-frame and this repeat are the two basic moves, and every recipe below
  combines them.

### Repeat schedules

The source is `cat.mp4`, a portrait clip at 30 fps, 8.6 s long, with no audio. At 4.233 s (frame
`p`) the cat turns right, and the camera that follows it speeds up from 22 to 67 px per frame.

The table compares two schedules of growing repeats.

| Schedule | Frames (times played) | Result |
|---|---|---|
| Doubling | `p` (2), `p+2` (4), `p+6` (8), `p+14` (16), `p+30` (32) | separate smears while the cat trots, and the cat stays recognizable. The last run stretches the ground into colored streaks that last until the end. |
| Stacked | `p` (2), `p+1` (4), `p+2` (8), `p+3` (16), `p+4` (32) | one smear that grows from 4.3 to 6.4 s; the cat dissolves into horizontal streaks, and then the real cat runs back out of them |

The stacked schedule is applied from the last repeat to the first, each call on the previous call's
output:

```
prepare {"input": "cat.mp4", "keyframes": "none", "intra_penalty": 300, "output": "work/cat.prep.mkv"}
repeat_pframes {"input": "work/cat.prep.mkv", "at": 4.362, "times": 32, "timing": "shift", "output": "work/s4.mkv"}
repeat_pframes {"input": "work/s4.mkv", "at": 4.328, "times": 16, "timing": "shift", "output": "work/s3.mkv"}
repeat_pframes {"input": "work/s3.mkv", "at": 4.295, "times": 8, "timing": "shift", "output": "work/s2.mkv"}
repeat_pframes {"input": "work/s2.mkv", "at": 4.262, "times": 4, "timing": "shift", "output": "work/s1.mkv"}
repeat_pframes {"input": "work/s1.mkv", "at": 4.228, "times": 2, "timing": "shift", "output": "work/s0.mkv"}
bake {"input": "work/s0.mkv", "output": "stacked.mp4"}
```

- Frame `p+k` starts at `(127 + k) / 30` s. Each `at` is 5 ms early, so it can't miss its frame.
- With `shift`, every run plays in full. The clip has no audio, so inserting frames loses nothing;
  each version grew by 57 frames (1.9 s).
- Applying the latest repeat first keeps the earlier `at` times valid. The stacked runs overlap, so
  with `keep` timing a later repeat would replay copies instead of the original frames
  ([repeat_pframes](docs/1111-repeat-pframes.md)).
- The doubling schedule is built the same way, with `at` set to 5.228, 4.695, 4.428, 4.295 and
  4.228.

### A smear that runs into a cut

The goal is a cat whose smear turns straight into a second shot, `bus.mov`, a 5.6 s portrait iPhone
clip in HDR. In it, a bus drives through, and the camera swings from the bus's side to its rear,
zooms in on the rear, and then whips down to the road.

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

In the first version, the cat's smear ended before the bus arrived, and the two effects looked
unrelated. Three changes connected them.

- The smear got longer. The stacked schedule got one more step, `p+5` 64 times, which keeps the
  smear going from 4.3 s through the cut. It is the latest frame, so it is applied first, and the
  whole schedule is rebuilt from the prepared clip.
- The cat clip ends earlier. The cut at 7.4 s comes about 1 s into the last run, while the cat is
  still a dark shape inside the streaks.
- The bus clip starts later. Starting 0.3 s in, the bus is already moving through the frame. It
  takes shape inside the cat's streaks and is sharp by about 8.6 s.

Other settings mattered too.

- `intra_penalty` is 1000, because at 300 the arriving bus covered the cat at once.
- An I-frame at 9.8 s, where the camera swings from the bus's side to its rear, is kept outside the
  drop range. Without it, dark bars from a gate stayed in the sky through the zoom. With it, the
  zoom and the whip play without artifacts, and the last frame matches the original footage (mean
  difference 1.6). The kept I-frame causes one visible change: a dark band in the sky turns blue in
  a single frame, in the middle of the swing.
- The bus clip runs to the end of its footage, and the mosh has settled by the zoom.
- The smear is baked before the second `concat`. Baking turns the smear into ordinary frames, so
  `prepare` can treat it as normal footage. The cat part stays silent, and the bus keeps its sound.

### A moshed sandwich loop

This 4:5 loop of about 31 s goes snowball, sunset, snowball, with three moshed cuts and one P-frame
repeat. It uses `sunset.mov` from the tutorial and `hand.mov` (landscape, 1920x1080). That clip
opens on an empty snowfield; a hand arrives, scoops a snowball, holds it, and later shows an open
palm.

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

The loop plays in five parts:

1. The snowfield is empty; then the hand arrives and scoops a snowball.
2. At the cut (6.6 s), the fingers open on a bare palm, and the snowball breaks into speckles where
   it was. The palm plays at half speed.
3. At 10.0 s the palm is swept into the sunset pan and melts into the shrubs, and then the sunset
   returns to normal.
4. The pan reverses for 1.1 s and cuts (15.87 s) to the hand rising. The momentum of the reversal
   carries through the cut: the sunset keeps sliding and smears into horizontal streaks as the hand
   rises, and the repeat at 16.7 s stretches it upward.
5. The whole hand clip plays backwards: the snow gathers, the hand leaves, and the last frame is the
   first one.

Several choices shaped the loop.

- The vanishing snow comes from a cut between holding the snowball (6.6 s) and the open palm
  (11.6 s). The palm time puts the palm where the snowball was: at 10.8 s it was 210 px off, and at
  11.6 s it is almost exactly in place. Moving the cut point lined the two up. Re-cropping would
  have broken the loop, which needs the same crop on its first and last frames.
- Earlier versions felt rushed. This one keeps the 4 s of empty snowfield at the start, slows the
  palm to half speed, and plays the whole sunset pan.
- For the sunset's ending, slowing it to half speed kept the sun still but felt like padding, and a
  full forward-back-forward boomerang looked like bouncing. The partial reverse that cuts away
  worked best. The further it reverses, the further the sun drifts from where the hand rises:
  reversing to 3.6 s puts the hand just beside the sun, and reversing to 3.2 s sends it toward a
  lamp post.
- Only real cuts get I-frames. The turnaround at 14.73 s, where the sunset starts to reverse, is
  left out of `keyframes`.
- The repeat plays 8 times, at the frame of fastest upward hand motion between 0.3 and 2 s after the
  last cut.
- The seam measured 2.4-2.9 (mean pixel difference), compared with 17-20 between neighboring frames
  of the moving shot.
- An earlier square (1:1) crop felt too tight, and 4:5 fits a phone screen better.

### A multi-clip night loop

This loop joins three night clips that share a mood but no subject.

- `gym.mov` is 4.9 s long, at 29.97 fps. The camera tilts up from the floor to bright windows and
  machines, then holds still.
- `sidewalk.mov` is 2 s long. A blurry whip pan settles on a snowy sidewalk under streetlights. Its
  header claims 120 fps, but it holds only 50 frames.
- `snowfall.mov` is 7 s long. Snow falls on a tree, and the camera tilts down past a streetlight and
  a car to footprints.

The first stage moshes the gym into the sidewalk clip played backwards, and then adds a stacked
smear on the reversed whip pan.

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

The second stage builds the whole loop and cuts from the middle of the smear into the snowfall.

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

The 21 s loop plays in four parts:

1. The gym's camera tilts up and then stays still for about 3.5 s.
2. After the cut into the sidewalk, whose motion is calm, the gym stays frozen while the night
   street builds up over it block by block.
3. The reversed whip pan smears in five growing runs, and the loop cuts in the middle of the smear
   to the snowfall, so the flakes fall through what is left of the smear.
4. After the cut into the reversed gym, the footprints freeze while the gym builds up, and the tilt
   down ends on the floor where the loop began.

Several choices shaped the loop.

- The clips were chosen for a winter-night mood. Clips of spring blossoms, a sunny lawn and a
  daytime tower were left out, and so was a static snowfall shot that repeated the other one.
- `sidewalk.mov` was planned as 0.25 slow motion of 120 fps footage. Its 50 frames in 2 s are really
  about 24 fps, so 0.25 would have shown only 6 new frames per second. Only its calm part was
  slowed, to 0.5, and the whip pan plays at real speed. `probe` now reports the measured rate for
  clips like this one.
- The smear runs into a cut, as in the cat-and-bus recipe. The whip pan's frames are dark and
  blurry, so the repeats spread mostly brown blocks; a smear is easier to see when the repeated
  frame has contrast.
- An I-frame kept at 21.02 s, inside the final fast tilt (56-62 px per frame), clears what is left of
  the mosh before the loop point. The seam measured 4.9, compared with 4.0 for the same assembly
  without any mosh.
- The first stage was baked before the second `concat`. Its `shift` repeats removed its audio, so
  the first 9 s are silent, but the snowfall and the gym keep their sound.

### Moshing with a copy-mode cut

Within a single shot, a copy-mode `cut` with `snap: false` makes an I-frame mosh in one step,
without re-encoding.

```
prepare {"input": "hand.mov", "keyframes": "none", "intra_penalty": 300}
cut {"input": "hand.prep.mkv", "start": 6.6, "end": 11.6, "mode": "copy", "snap": false}
bake {"input": "hand.prep.cut.mkv"}
```

- With `snap: false`, `cut` removes `[start, end)` and resumes on the P-frame at `end`, which now
  predicts from the last frame before `start`. The later motion moves the earlier picture, with the
  same effect as `concat`, `prepare` and `drop_iframes` at a junction. Avidemux users get this
  result by accident in copy mode; here it is deliberate.
- With `snap: false`, `trim` starts on a P-frame that has no picture before it. What plays depends
  on the decoder: gray, garbage, or nothing until an I-frame. This is how a broken start happens in
  Avidemux, and it is rarely useful.
- The audio follows the kept video, and the container stays the same as the input's.
- This approach suits a cut inside one shot that needs no crop, speed change or reversal. Prepare
  the clip with `"keyframes": "none"` and an `intra_penalty`; then only an I-frame that you keep can
  end the mosh. The renders above needed crops, speed changes or reversed parts, so they used
  `concat` and `drop_iframes`, and this approach is untested on real footage.
- On raw phone footage, B-frames and frequent I-frames make the result shorter and harder to
  predict, so prepare the clip first.

### Checking a mosh

`preview` shows a moshed MKV correctly without baking it first, because it decodes from the I-frame
at or before `start`, as a player does from the beginning.

1. After `prepare`, check that its `keyframes` are `0.0` plus your times and nothing else.
2. After `drop_iframes`, check that `dropped` lists exactly the I-frames that you meant to delete,
   and that `probe` still shows each I-frame that you kept.
3. Preview each cut from 0.2 s before it to about 2 s after it, with `count` 12-16. The old picture
   should stay on the first frames, and the new motion should move it; note when the new shot is
   fully back.
4. Preview each repeat over its run plus 1 s.
5. For a loop, compare the first and last frames by previewing 0 to 0.1 s and the last 0.1 s. To get
   a number, compare them outside the MCP (mean absolute pixel difference). Our good seams measured
   about 2-5, compared with 17-20 for one frame of camera motion.
6. Bake the file, then preview the MP4 over the same windows; it should match the MKV previews. A
   moshed MKV depends on broken references, which players, editors and upload sites can decode
   differently or refuse. The baked MP4 stores the decoded frames as ordinary pictures, so it plays
   the same everywhere.
7. To share a large file, bake the master again at `crf` 23-26 into a separate file.

| What you see | Cause | Fix |
|---|---|---|
| The cut plays clean, with no mosh | The I-frame isn't on the junction, or wasn't dropped | Prepare again with `concat`'s junction times exactly as returned, and check `dropped` |
| The old picture is gone within half a second | `intra_penalty` is too low | 300 |
| The mosh never clears | `intra_penalty` is too high, and no I-frame was kept | Lower it, or keep an I-frame inside fast motion |
| The new shot covers the old picture at once | A large moving subject at 300 | 1000, plus a kept I-frame |
| Leftover blocks or bars stay until the end | Nothing ends the mosh | Keep an I-frame where the camera moves fast |
| The repeat breaks into blocks | The repeated frame's motion is irregular | A frame with fast, even motion |
| The repeat starts on the wrong frame | `at` fell just after the frame you meant | Pass a time a few ms earlier, and check `frame` |
| No sound | `shift` timing removes all audio | Use `keep`, or mosh that part alone, bake it, and join it with `concat` |
| "run prepare first" | The file has B-frames | `prepare` |

### What worked and what didn't

These choices come from one person's taste over several sessions, so treat them as starting points.

- Mosh subjects that people recognize, so that the effect means something: a hand catches the sun,
  a snowball dissolves, a cat is swept into a bus.
- Leave room in the pacing. Keep the empty stretches of the source, slow nearly still moments to half
  speed, and lengthen shots with partial boomerangs instead of trimming them tight. A rushed pace
  was the most common complaint.
- Build sandwiches and loops (A, B, then A reversed), framed at 4:5 (1080x1350).
- Let a smear of repeated P-frames run straight into a cut with a dropped I-frame.
- End on clean footage: keep an I-frame inside fast motion, and let the last shot settle.
- To line up a subject across a cut, choose the cut time instead of re-cropping.

| Tried | What happened | What worked instead |
|---|---|---|
| `intra_penalty` 0 | the sunset was repainted within half a second | 300 |
| `intra_penalty` 3000 | the mosh never cleared | 300, which clears in about 2 s |
| 300 for a large subject that arrives | the bus covered the cat | 1000, plus a kept I-frame |
| no kept I-frame after a strong mosh | dark bars stayed in the sky through the zoom | an I-frame kept at the camera's swing |
| a fast-moving camera in the second clip | the old picture smeared into noise | a stretch where the camera is still, reversed |
| a repeat on a sideways swing | blocky fragments | a frame of even upward motion |
| a long inserted repeat on a bright frame | white snow streaked into the sky | 8 plays with `keep` |
| a full forward-back-forward boomerang | it looked like bouncing | a partial reverse that cuts away |
| a subject leaving the frame in the second clip | a window in the subject's shape, and no drag | a subject entering the frame |
| 0.25 slow motion of a "120 fps" clip | it was 24 fps and would stutter | check `fps`, and slow only calm parts, to 0.5 |
| a smear that ended before the next shot | two unrelated effects | a longer smear, cut in the middle |

We found the frames to repeat, and the points for lining up subjects, outside the MCP: from the
decoder's motion vectors (PyAV with `flags2=+export_mvs`) and from a search for skin color. With the
MCP alone, narrow `preview` windows find them too, but more slowly.
