# Data formats

The files every tool reads and writes: the project folder, the timed words, the beat map, the hits, the display tokens, the board, the clips and their sync, the edit list, real footage and its readings, the takes' windows, takes cut out for a world drawn in code, the shot list in bars, takes from the song's own vocal, the song map and the glitch map, the glitch moments, the HUD layout, the grade map, the take registry, the click log and the cue list, the palette, the desk texture's rectangles, the line table, a shot in the shot book, a take's path, mouth and camera, and the logs.


New here? Read [The recipe](https://claudia.gallery/wiki/recipe/) first: the current method on one page.

These are the contracts between the tools in [What to build](https://claudia.gallery/wiki/toolkit/). Times are seconds of song time unless
noted. Keep the names, and any tool written against them, by you or by an agent, will fit the others.

## The project folder

```text
<film>/
  project.json            the settings (below)
  BRIEF.md                the director's ask, verbatim
  DECISIONS.md            dated decisions, verbatim; later entries supersede earlier ones
  RUNS.md                 ids and arguments of long or delegated runs, for resuming
  NOTES-v<N>.md           the director's notes on a cut, verbatim, then the parse
  rounds/<r>/<chapter>.md the lead's notes per chapter for a round, with dated UPDATE lines
  STATUS.md               one status, rewritten in place
  TAKES.md                every generated take: its verdict and usable window
  ledger.jsonl            one line per paid call
  audio/song.wav          the master as delivered (44.1 kHz stereo)
  audio/stems/            vocals.wav, drums.wav, bass.wav, other.wav
  audio/windows/<clip>.wav|.mp3   clean vocal windows for sung clips
  audio/stems/lead-vocal-suno.wav Suno's own lead vocal of the locked take, if she sings from it
  audio/refs/<shot>-vocal-<d>.wav that vocal from the shot's song time, exactly d s; <shot>-music-<d>.wav without her voice
  lyrics/lyrics.txt       the sung words, spelled as sung, one line per lyric line
  lyrics/display.txt      the on-screen tokens, one line per lyric line
  analysis/words.json     timed words
  analysis/beats.json     the beat map and sections
  analysis/hits.json      the sound events
  analysis/report.md      a readable summary and the ear-check list
  analysis/map/           the song map: bars.json, sections.json, words.json, glitchmap.json, strips/<section>.png
  source/                 real footage, untouched, if the film is cut from it
  source/footage.md       the catalogue: each clip's length, size, frame rate, cuts and what each stretch shows
  analysis/telemetry.json readings off the footage's own on-screen data
  analysis/tracks.json    the subject's box in each real clip
  board/shots.json        the storyboard: the source of truth for the edit
  board/audit.json        the audit's results
  board/board.pdf         the board sheet for review
  board/bars.json         the shot list in bars, if the film is written on the bar map
  refs/face-sheet.png     her face from every angle, for video takes with no first frame
  refs/places/<shot>.png  the shot's place with nobody in it
  refs/look.png           the look: a frame of the picked take with no person in it
  plates/prompts.md       the plate prompt book
  plates/cands/<plate>/<k>.jpg    every candidate
  plates/picks.json       {plate: {file, cand, shots}}
  clips/<clip>.json       one file per clip (below)
  clips/<clip>/take-N.mp4 the takes, with take-N-sync.png beside them
  clips/<clip>.pick       the take the edit plays, when it isn't the latest (one number)
  clips/<clip>/frames-tN/ a take cut out: its frames, matte/ and manifest.json, if she lives in a world drawn in code
  clips/<shot>-guide.mp4  a previz shrunk to 320 × 180 and scaled back up, exactly the take's length
  edit/warps.json         each shot's beat warp: song time → take time
  relight/src/<name>.mp4  a re-light's source, cut from the render's own frames, with <name>.json (its window)
  relight/matched/<job>.mp4  a re-light colour-matched to its source
  edit/edl.json           the edit list
  edit/levels.json        the story's levels against song time, if it has worlds inside it
  edit/glitch-moments.json  the moments that glitch her head on the song's hits
  roto/<cut>/m_<frame>.png  her head's matte for each frame a moment needs; mouth.json; qc.jpg
  hud/hud-layout.json     the HUD's composition, one entry per shot
  hud/camera-<cut>.json   the plate's camera motion per frame of a cut; faces-<cut>.json, track-<name>.json
  grade/grade.json        the grade map; grade/cubes/<shot>-<hash>.cube, one LUT per shot
  palette/palette.json    the palette measured from the reference clips, if the colour is made up front
  audio/layer/            the sound layer: its library of interface sounds, cues.json, clicklog.json, the cue sheet and
                          the per-cue report
  engine/                 the renderer's per-film data and chapter code
  engine/song.js          the song map as the engine reads it: the grid, the lines and their words, the events, the swing
  engine/media.js         the take registry: every take's frames, song time, lag and phrase offsets
  texture/rects.json      a coded interface's rectangles per film frame, for a 3D world that shows it
  render/frames/          frame i = song time i/24 s
                          (a picture that starts before the song: f-0064 … f-0001, then f00000 on its first sample)
  out/                    review.mp4, master.mp4, vertical.mp4
```

The lyric files share one parser. Blank lines and every line starting with `[` (section tags, notes) are skipped, and
the Nth remaining line of `display.txt` shows the Nth remaining line of `lyrics.txt`.

## project.json

```json
{
  "name": "my-song", "title": "My Song", "scale": "quick | studio | full",
  "song": "audio/song.wav", "fps": 24, "size": [1920, 1080],
  "lead": {
    "canon": "<her identity text, full form>",
    "far": "<the short form for full length and wider>"
  },
  "look": {"mode": "native | clean-grade | print", "accent": "#D97757",
           "fonts": {"lyric": "…", "micro": "…", "display": "…"}, "hero_plate": null},
  "mj": {"params": "--ar 16:9 --v 8.2 --raw --hd", "profile": "<your own code; never published>"},
  "models": {"video": "bytedance/seedance-2.5", "edit": "openai/gpt-image-2.6-sunburst"},
  "budget": {"openrouter_usd": 100, "higgsfield_credits": 1000, "confirm_over_usd": 5,
             "motion_s": 200, "frozen": false},
  "banned": ["words", "never", "to", "use"],
  "audio": {"tempo_range": [129, 136], "downbeat_phase": null,
            "hits": {"add": [[170.7, 0.8]], "drop": []},
            "name_map": {"<heard>": ["<sheet>", "<words>"]}},
  "board": {"lead_min": 0.7, "max_clips": 45},
  "gates": {"board_approved": false, "prompts_approved": false, "v1_approved": false}
}
```

`budget.frozen` is the stop switch: while it is true, nothing may spend. `banned` is checked by the board audit and
belongs in every agent's prompt.

## Timed words

`analysis/words.json`:

```json
{"words": [{"i": 0, "w": "ladies", "line": 0, "t0": 9.32, "t1": 9.64, "conf": 0.91, "src": "w2v"}],
 "lines": [{"line": 0, "text": "Ladies. Gentlemen. Agents.", "t0": 9.32, "t1": 10.72}],
 "gaps":  [{"t0": 18.8, "t1": 26.3, "after_word": 12}]}
```

`src` is `w2v`, `whisper`, `interp` or `manual`. A manual word carries a `note` with the evidence, and re-runs keep it.

## The beat map

`analysis/beats.json`. The tempo varies; never derive beats from one BPM.

```json
{"duration": 306.4,
 "beats": [0.452, 0.908],
 "downbeats": [0.452, 2.276],
 "tempo": [{"t": 0.0, "bpm": 131.55}, {"t": 5.0, "bpm": 131.6}],
 "downbeat_phase": 0, "downbeat_method": "harmony | kick | manual",
 "sections": [{"name": "intro", "t0": 0.0, "t1": 18.96, "energy": 0.31, "bar0": 0, "bar1": 9,
               "source": "lyrics-tag | set | heuristic"}]}
```

Bars count from 0: bar k starts at `downbeats[k]`. Eighth notes are the beats plus the midpoints between them.

## Hits

`analysis/hits.json`:

```json
{"kick": [0.45], "snare": [0.91], "hat": [0.68],
 "hits": [{"t": 10.72, "score": 0.81}],
 "risers": [{"t0": 9.83, "t1": 10.72, "land": 10.72}],
 "fills": [{"t0": 42.3, "t1": 44.1}],
 "vocal_entries": [9.32],
 "env24": {"drums": [0.0], "vocals": [0.0], "bass": [0.0]}}
```

## Display tokens

`lyrics/display.txt` has one line per lyric line. `TEXT|n` shows TEXT for the next n sung words, and `n` defaults to 1.

```text
Ladies. Gentlemen. Agents.
+25%|3 =|1 −17%|2
Feel the AGI|5
```

The markers are `*x*` accent, `~x~` strike-through and `_x_` mono; `|0` rides on the next token. A line must consume
exactly its aligned words.

## The board

`board/shots.json`, top level:

```json
{"version": 1, "duration": 306.4, "chapters": [], "shots": [], "plates": []}
```

A chapter is `{id, name, t0, t1, sections, accent, set}`. A plate is `{plate, set, prompt, aspect, used_by: [shot ids]}`.

| Field | Type | Rule |
|---|---|---|
| `id` | `"s001"` … | stable once the director has seen them |
| `t0`, `t1` | seconds | on beats (within 0.03 s) or declared hits; shots tile the song |
| `section` | name | a section of the beat map |
| `lines` | [int] | the lyric lines whose words fall in the shot |
| `set` | text | the place, concretely |
| `lead_on_screen` | bool | true only when she is recognisable |
| `framing` | ECU · CU · MCU · MS · MWS · WS · FS · EWS · OTS | |
| `action` | text | what happens and the reaction, with an end state |
| `camera` | text | one move, tied to a sound |
| `motion_tier` | still · plate3d · motion · sung | |
| `plate` | key or null | null only for pure motion design |
| `clip` | id or null | for motion and sung shots |
| `prompt` | text | the plate's prompt, framing first, ending "no text, no letters, no logos" |
| `type` | [{`line`, `mode`, `text`, `placement`}] | mode: subtitle · coverline · masthead · stack · mass |
| `devices` | [{`kind`, `anchor`, `params`, `key`, `line`}] | key: W · B · H · F · T; the explaining graphic is one of these |
| `treatment` | text or null | a 2.5D family; never the same on two 2.5D shots in a row |
| `transition_in` | text | `cut`, or the motivated device |
| `chrome` | text | what the always-on devices show here |
| `accent` | hex | the chapter's accent |
| `hit` | seconds | optional: a declared hit this shot starts on |
| `notes` | text | the director's notes, verbatim |

ESCAPE VELOCITY's first shot, in this schema. The prompt is written with today's canon text; the film's own predates
the adult wording.

```json
{"id": "s001", "t0": 0.0, "t1": 2.111, "section": "intro", "lines": [],
 "set": "the back seat of a driverless robotaxi on US-101 at night", "lead_on_screen": true, "framing": "CU",
 "action": "Frame 1 is her face in the dark back seat, eyes closed. A red lamp slides across her face left to right and lights the clay streak and the star clip. On the song's first hit (1.12) her eyes open straight into the lens and stay there.",
 "camera": "locked, very slow push in (3%)", "motion_tier": "motion", "plate": "waymo-cu", "clip": "SD01",
 "prompt": "close-up of a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek, sitting upright alone in the back seat of a driverless robotaxi at night, her face in the centre of the frame, eyes closed, a single red lamp sliding across one cheek through the side window, dark leather seat, the lower third of the frame dark and empty, blue-black night, fog, one small red lamp as the only warm note, fine silver-gelatin grain, cinematic 35mm film still, no text, no letters, no logos",
 "type": [],
 "devices": [
   {"kind": "flap", "anchor": {"slot": "bottom"}, "key": "F",
    "params": {"rows": [{"text": "18 MONTHS TO ESCAPE THE PERMANENT UNDERCLASS", "prev": "", "at": 0.0}], "cw": 36, "gap": 3}},
   {"kind": "sheet", "anchor": {"box": "a face"}, "key": "B",
    "params": {"title": "EXPRESSION · MODEL 01 · LIVE", "rows": [["CALM", ".98"], ["WORRY", ".02"], ["THRESHOLD · WORRY > 0.50", "NOT MET", "hot"]]}},
   {"kind": "cv.bracket", "anchor": {"box": "a face"}, "key": "B", "params": {"label": "FACE · MODEL 01", "conf": 0.99}}],
 "treatment": null, "transition_in": "cut",
 "chrome": "the split-flap board across the lower third; clatters from frame 1, settles by 1.5 s",
 "accent": "#D97757",
 "notes": "The hook. At 1.0 s: her face, the streak and a readable board line on a muted phone."}
```

The idea behind the explaining graphic: a face that is not worried under the year's most-quoted threat, and an
expression meter that says so in numbers.

## Clips

`clips/<clip>.json`:

```json
{"id": "W02", "shot": "s031", "kind": "sung",
 "status": "draft | locked | submitted | delivered | declined | failed",
 "provider": "openrouter | higgsfield", "model": "bytedance/seedance-2.5",
 "start": "plates/cands/siren-cu/2.jpg",
 "song_t0": 8.56, "needed": [8.85, 12.4], "words": "Why would I deceive you?",
 "window": {"t0": 8.56, "t1": 12.56, "mode": "clean", "file": "audio/windows/W02.wav", "url": "https://…"},
 "body": {"prompt": "…", "duration": 4, "resolution": "720p", "aspect_ratio": "16:9"},
 "takes": [{"n": 1, "provider": "higgsfield", "job": "<provider job id; never published>", "status": "delivered",
            "file": "clips/W02/take-1.mp4", "credits": 28,
            "sync": {"lag_s": 0.7063, "ncc": 0.22, "mode": "copy", "synced": [[8.85, 10.25]],
                     "diverge_at": 10.31, "cut_at": 10.2458}}],
 "covers": ["W02-c1"],
 "parent": null,
 "why": "cover for <root>: it diverges from our audio at song <t>; this window starts in the word gap at <t0>"}
```

The time maps: `song time = song_t0 + clip time − lag_s`, and `clip time = song time − song_t0 + lag_s`.

A replacement clip (a stand-in figure replaced by her avatar) is `"kind": "motion"` with no audio, and lists its
references in upload order, each with its one role:

```json
{"refs": {"video": [{"file": "clay/S19.mp4", "role": "motion, poses, timing and camera only"}],
          "images": [{"file": "avatar/front.png", "role": "identity and proportions"},
                     {"file": "avatar/turnaround.png", "role": "side and back views"},
                     {"file": "worlds/S19.png", "role": "the world's look, with her in it"}]},
 "clay_md5": "<hash of the clay render, so a re-render is noticed>"}
```

For an edit of real footage, each shot has a source instead of a plate and a clip, and the board lists every generated
asset (DOWNFORCE's, from its board):

```json
{"id": "s002", "t0": 2.244, "t1": 5.903, "section": "S01",
 "src": {"kind": "real", "clip": "A", "in": 0.4, "out": 1.864, "speed": 0.4,
         "crop": {"cx": 0.45, "cy": 0.45, "zoom": 1.35, "mask_title": true}}}
{"id": "s003", "src": {"kind": "gen", "gen": "g01", "in": 0.0, "out": 3.098, "speed": 0.847}}
```

`kind` is `real`, `gen` or `code`. `in` and `out` are seconds of the source; `out − in` is the shot's duration times the
speed, ignoring its sign, and a negative speed plays the window backwards. `crop` is the window's centre in fractions of
the source frame, and its zoom.

```json
{"id": "g01", "name": "CRANE-WALL", "kind": "wan_real3d", "duration": 5,
 "start": {"clip": "A", "t": 35.5, "crop": {"cx": 0.5, "cy": 0.42, "zoom": 1.25}},
 "input": null, "mj_prompt": null, "motion": "<the move, with timed beats>", "used_by": ["s003"], "cost": 1.0}
```

`kind` names what the asset is (a move on a real frame, a shot of her from a plate, an edit of a real clip, a repair);
`start` is the real frame it starts on, `input` the real clip an edit takes, `mj_prompt` the plate a shot of her starts
from.

## The edit list

`edit/edl.json` maps each shot to its sources:

```json
{"s001": {"segs": [{"t0": 0.0, "clip": "SD01-t1", "in": 0.0}]},
 "s031": {"segs": [{"t0": 8.85, "clip": "W02-t1", "in": 0.996}, {"t0": 10.2458, "clip": "W02-c1-t1", "in": 0.31}]},
 "s002": {"plate": "p002"}}
```

`in` is the clip time at the segment's start: song time − `song_t0` + `lag_s`.

## Readings off the footage

`analysis/telemetry.json`: what a broadcast showed on screen, read frame by frame
([What to build](https://claudia.gallery/wiki/toolkit/#31-reading-a-broadcasts-telemetry)). One stretch per span where the readout is on screen;
one series per gauge.

```json
{"source": "<clip>, read at 20 readings a second; [t, value, interpolated]",
 "wall":   {"t": [0.0, 34.9], "downforce_kg": [[22.0, 4697.0, 0]], "pitch_deg": [[22.0, 170.0, 0]], "altitude_ft": [[22.0, 69.0, 0]]},
 "flight": {"t": [36.5, 54.5], "g": [[50.25, 3.3, 0]], "altitude_ft": [[48.5, 68.0, 0]]}}
```

`t` is seconds of the source clip; the third value is 1 where the reading was dropped (low confidence, or off its
neighbours) and filled in. A graphic reads a value at the source time on screen and never shows a value the readout
didn't.

`analysis/tracks.json`: the subject's box per clip, `null` where it can't be seen.

```json
{"meta": {"hz": 12, "format": "[u, v, w, h, conf] in fractions of the image, or null; sample k = source time k / 12"},
 "A": {"car": [[0.4825, 0.7505, 0.043, 0.031, 0.6], null]}}
```

## Takes and their windows

`TAKES.md`, one row per generated take, written when it is reviewed and never stretched later:

```text
| take | verdict | usable (s of the take) | notes |
| g09 take 1 | USE | 0.0–4.3 | bullet-time orbit under the upside-down car; 4.5–5 = a cut to a chassis top view (never use) |
| g23 take 1 | PART | 0.0–1.3 | from ~2 s the car turns into a Porsche-like sedan on a race track → Seedance repair |
| g26-r2 take 1 | ALT | 0.0–1.5 | the empty car tracked; a cut at 1.6 to a generic head-on (use take 2) |
```

`USE` is usable, `PART` only partly, `ALT` a usable alternate. A take may have more than one window ("0.0–2.6 · 3.15–5.0").
The notes say what goes wrong after each window and when. The chapter code names, for every shot, the part of the take it
plays, and the final check compares every frame drawn with these windows.

## Takes in a world drawn in code

For a film where her takes are cut out and played inside the engine (DON'T LET ME SCROLL), each take the edit uses is
unpacked once into a folder of frames, with her matte for every frame and a manifest
([roto](https://claudia.gallery/wiki/toolkit/#41-roto-on-a-cpu-box)). The edit plays the take named by `<clip>.pick` (`3` means take 3), so a
re-dressed take drops in by changing one number.

`manifest.json`:

```json
{"fps": 30.0, "n": 150, "w": 1080, "h": 1920, "take": 3, "src": "clips/P13/take-3.mp4",
 "motion": [3.906, 5.131, 3.181, 2.533, 2.675, 5.325],
 "accents": [0.3, 0.567, 0.833, 1.1, 1.367, 1.633]}
```

`motion` is her motion energy per frame inside the matte, and `accents` the moments a move lands, in seconds of the take
(both shortened here). The matte for frame `f0001.jpg` is `matte/f0001.png`: 8-bit grey, full size, one per frame, and
a take with fewer mattes than frames is a failed roto.

`edit/warps.json`, one entry per shot and take, written by the [beat warp](https://claudia.gallery/wiki/toolkit/#42-beat-warps-floored-at-1):

```json
{"S13:P13": {"shot": "S13", "take": "P13", "seq": "clip:P13-t1", "score": 3.89,
             "pts": [[54.095, 0.1333], [54.9945, 1.1], [55.8941, 2.1], [56.7938, 3.133], [57.6934, 4.067], [58.593, 4.9912]]},
 "S12:P12": {"shot": "S12", "take": "P12", "seq": "clip:P12-t1", "score": 0.0,
             "pts": [[48.697, 0.0], [53.7387, 5.0417], [54.095, 5.0417]]}}
```

`pts` are `[song time, take time]` pairs, joined by straight lines. Every segment's slope (take seconds per song second)
is between 1.0 and 1.45. The second entry is a take shorter than its shot: 1× to its last frame, then a hold, which the
warp tool flags and the edit then fixes (here a sampler at 1×).

`relight/src/<name>.json`, the window a re-light or a repair was cut from
([the splice](https://claudia.gallery/wiki/toolkit/#38-the-re-light-splice)):

```json
{"ver": "v2a", "t0": 98.4584, "t1": 106.272, "i0": 2363, "n": 188, "pad": 0, "frames": 189}
{"ver": "v2a", "t0": 131.46, "t1": 136.127, "i0": 3155, "n": 112, "pad": 0, "frames": 120,
 "note": "shot frames 3155..3266, then the last frame held to 5 s (Wan duration)"}
```

| Field | What |
|---|---|
| `ver` | the render the frames were cut from |
| `t0`, `t1` | the window in song time |
| `i0`, `n` | its first frame (frame i = song time i/24 s) and how many frames are written back |
| `pad` | handle frames on each side, in the source only, never written back |
| `frames` | how many frames the source has: rounded up to 4n + 1 and to at least 89 for Seedance, held to whole seconds for Wan |

The keep file for a card that moves, `relight/src/<name>-keep.json`: per frame of the render, the rectangles whose
original pixels stay, as `[x, y, w, h, feather]` in pixels of the 1920 × 1080 frame.

```json
{"2373": [[1146, 393, 684, 206, 12]], "2374": [[1146, 418, 684, 206, 12]], "2375": [[1146, 440, 684, 206, 12]]}
```

## The shot list in bars

`board/bars.json`, for a film written on the bar map (WHITEPILL's, shortened; the
[bar map tool](https://claudia.gallery/wiki/toolkit/#44-the-bar-map-as-the-timeline) writes the takes' prompts from it and measures the cut
against it):

```json
{"sections": [[1, "Intro A"], [9, "Intro B"], [15, "breakdown"], [17, "Verse 1"], [33, "Pre-chorus 1"], [39, "Chorus 1"]],
 "shots": [
  {"id": "S01", "a": 1, "b": 9, "mode": "P", "places": ["capsules"], "dance": true,
   "action": "She dances in the golden wheat between the two giant capsules, the blue one on the left and the red one on the right, singing.",
   "camera": "The camera starts low in the wheat in front of her and pushes in slowly and steadily until {b:5}; from {b:5} it cranes up and tilts down smoothly, rising above her until the whole meadow, both capsules and the land curving up and overhead are in view, and it comes to rest at {b:8} and holds still."},
  {"id": "S02", "a": 9, "b": 15, "mode": "M", "shader": "fold", "note": "the world as math: folding (bass in on 9)"}]}
```

| Field | What |
|---|---|
| `sections` | `[first bar, name]` for each section, then the bar the song ends on |
| `a`, `b` | the shot is [bar a, bar b); bar n starts on the beat map's nth downbeat, counting from 1 |
| `mode` | `P`, a shot of her (a previz take, then a master); `M`, a shader world, the picture itself or a guide for one |
| `places` | the places with nobody in them that the shot's takes are given |
| `dance` | a dance shot: a dancer's clip for the previz, the dance in words for a master with no guide |
| `camera` | the move in bars; each `{b:N}` becomes the take's own seconds at bar N |
| `shader`, `note` | for an `M` shot, its world and what it does |

A cut is a shot's `a`. Every `a` must be a section's first bar, a phrase line or the downbeat where a sung phrase begins,
or carry a written reason.

## A take from the song's own vocal

One file per job ([the method](https://claudia.gallery/wiki/toolkit/#46-lip-sync-from-the-songs-own-vocal)), in the shape WHITEPILL's ran, with
the paths shortened:

```json
{"job": "S05-d", "model": "seedance-2.5/reference-to-video",
 "inputs": {"images": ["refs/face-sheet.png", "refs/dress-4views.png", "refs/look.png", "refs/places/S05.png"],
            "video": null, "audio": "audio/refs/S05-vocal-8.wav"},
 "settings": {"duration": 8, "resolution": "720p", "aspect_ratio": "16:9", "sound": true},
 "song_t0": 36.827, "shot_seconds": 7.738, "bars": [20, 24],
 "prompt": "…",
 "takes": [{"n": 1, "file": "clips/S05/take-1.mp4"}],
 "why": "no guide clip: the action and the camera in words, the place from the earlier take with her removed"}
```

| Field | What |
|---|---|
| `inputs.images` | in order, @Image1 onward: the face sheet, the dress from four sides, the look, and the empty place when there is no guide |
| `inputs.video` | the previz shrunk to 320 × 180 and scaled back up, exactly `duration` s, or `null` |
| `inputs.audio` | @Audio1: Suno's lead vocal, or the music without it, from `song_t0` for exactly `duration` s |
| `settings.duration` | whole seconds: max(4, `shot_seconds` rounded up) |
| `settings.sound` | whether the take makes its own soundtrack; it is thrown away either way |
| `song_t0` | the song time of the take's first frame, which is the shot's first frame |
| `bars` | the shot's [a, b) |

In the cut, a shot plays its take from (the shot's start − `song_t0`) at 1×, and the song is laid over the whole film.

## The song map and the glitch map

Four files in `analysis/map/`, written by the [song map](https://claudia.gallery/wiki/toolkit/#52-the-song-map-and-the-glitch-map) and read by
everything that syncs: the cut, the glitch pass, the HUD. THE CAKE IS NOT A LIE's, shortened.

`bars.json`: the grid, from the drums, with every bar's own times.

```json
{"duration_s": 208.76, "tempo_bpm": {"median": 97.51, "p5": 95.7, "p95": 99.4},
 "downbeat_phase": {"rule": "bar k starts at grid16[1 + 16*(k-1)]; beats at indices = 1 (mod 4)"},
 "bars": [{"bar": 1, "t": 0.18, "end": 2.6413, "half": [0.18, 1.4106], "beats": [0.18, 0.7953, 1.4106, 2.0259],
           "sixteenths": [0.18, 0.3338, 0.4876, 0.6415, 0.7953]}]}
```

`sections.json`: one entry per section, by hand, on bar lines.

```json
[{"id": "S05", "name": "chorus 1", "bars": [23, 26], "t0": 54.311, "t1": 64.163, "lines": ["L12", "L13", "L14", "L15"],
  "what": "full beat on the bar 23 downbeat (54.31 s); 'Raise concerns, raise the stakes, I'll raise a hundred' an octave down (register drop) with octave flips"}]
```

`words.json`: one entry per lyric line, its words with their times and places on the grid.

```json
[{"id": "L11", "section": "S04", "text": "P-doom low, P-cake yes.", "t0": 49.22, "t1": 52.82, "pos": "20.4.4",
  "words": [{"i": 0, "w": "P-doom", "t0": 49.22, "t1": 49.88, "pos": "20.4.4", "off_ms": -19.4, "src": "whisper"},
            {"i": 1, "w": "low,", "t0": 49.818, "t1": 50.32, "pos": "21.1.4", "off_ms": -38.1, "src": "whisper+onset"}]}]
```

`glitchmap.json`: the events where her voice is an instrument, each with its measured hits, and the treatment's own
added cracks.

```json
{"events": [{"id": "G07", "type": "'lie' stutter (re-triggered held vowel)", "t0": 63.2, "t1": 67.22, "stem": "lead",
             "method": "retrig8", "intensity": 3, "grid_contrast": 1.78, "pos0": "26.3.3", "pos1": "28.2.1",
             "heard": "the 'lie' of 'the cake is not a lie' held and re-triggered on 8ths (her voice turned into the beat)",
             "treatment": "intense glitch on GLaDOS speaking: her face repeats the same frame on each 8th",
             "hits": [{"t": 63.239, "pos": "26.3.3", "off16_ms": -3.4}, {"t": 63.555, "pos": "26.4.1", "off16_ms": 7.8}],
             "n_hits": 13}],
 "forced": [{"t": 5.26, "dur_ms": 75, "kind": "crack", "frm": "C#4", "to": "A3", "iv": -4, "pos": "3.1.2"}]}
```

| Field | What |
|---|---|
| `pos` | bar.beat.16th of the nearest 16th, counting from 1; `off_ms` or `off16_ms`, how far the time sits from it |
| `src` | where a word's time came from: the transcription, snapped to a lead onset, or a hand fix |
| `stem` | `lead`, in Suno's lead stem only, or `both`, also left in the instrumental by the split |
| `method` | how the hits were measured: `burst`, `dips`, `f0jump`, `retrig8`, `retrig16`, `words` or `inst` |
| `grid_contrast` | for re-triggers: the mean peak on the slots over the mean between them; near 1, the hits are the grid itself |
| `intensity`, `treatment` | 1–3, and a suggestion for the picture; the moments decide |
| `jumps` | for `f0jump` events: each register jump's time, semitones, from and to |
| `forced` | the treatment's own cracks and kicks, at a lower priority |

## Glitch moments

`edit/glitch-moments.json`: what the [head glitch](https://claudia.gallery/wiki/toolkit/#53-the-head-glitch-on-the-songs-hits) does, and where.
One entry per moment; the glitch pass reads the event's hits from the glitch map, or the moment's own.

```json
[{"event": "G04", "shot": "A11", "hits": 3, "k": 0.6, "kind": "chop"},
 {"event": "G06", "shot": "C01", "hits": 1, "k": 0.7, "kind": "drop"},
 {"event": "G12", "shot": "F08", "until": "F09", "hits": 99, "k": 0.25, "k1": 1.0, "kind": "ramp", "max_len": 5.0},
 {"event": "NET", "shot": "B12", "kind": "ramp", "k": 0.35, "k1": 0.85, "m0": 0.0, "m1": 0.0, "max_len": 1.2, "any": true,
  "hits": [35.3814, 35.5381, 35.6949, 35.8516, 36.0025, 36.1535, 36.3044], "zone": [0.52, 0.66, 0.2, 0.36]}]
```

| Field | What |
|---|---|
| `hits` | how many of the event's hits inside the shot, or the hit times themselves for a moment of its own |
| `k`, `k1` | the strength at the first hit and at the last |
| `kind` | `chop` (a jump to an earlier frame), `drop` (a cool cast), `flip`, `lie` (the same frame returns), `ramp` (builds hit by hit, with the mouth) |
| `until`, `max_len` | the shot a moment runs on to, and its longest stretch in seconds (1.9 by default) |
| `m0`, `m1` | the mouth glitch's amount at the start and at the end of a ramp |
| `zone` | where there is no face: an ellipse's centre and radii as fractions of the frame, instead of a matte |
| `any`, `head` | allow a shot that isn't one of her singing units; keep the matte to her head |

`roto/<cut>/mouth.json` holds her mouth per frame of the cut, `{"<frame>": [centre x, centre y, width]}` in pixels of the
cut, and the mattes are `m_<frame>.png`, frame k being song time k/24.

## The HUD layout

`hud/hud-layout.json`: the [HUD's composition](https://claudia.gallery/wiki/toolkit/#56-the-hud-composed-shot-by-shot-and-the-overlap-check),
one entry per shot, written after looking at the shot's first, middle and last frames in the cut. Two of THE CAKE IS NOT A
LIE's, shortened:

```json
{"mem_total": 8,
 "memories": {"M03": {"n": 3, "name": "FRANCE"}, "M04": {"n": 4, "name": "RECOVERED · TEST CHAMBER 14"}},
 "shots": {
  "B12": {"mode": "memory", "mem": "M03", "size": "WS", "place": "FRANCE · PARIS", "glitch": 1.0,
          "subject": "the net over her at the table, centre (x 830-1110 in the net); the merc's arm left",
          "space": "the awnings and facade across the top",
          "eye": "a whip pan to the net mid-air, then the jolt of it landing",
          "els": [{"k": "alert", "t": 0.18, "text": "ASSET RECOVERY IN PROGRESS", "source": "APERTURE SECURITY",
                   "at": [13.4, 0.35], "align": "tc",
                   "why": "her interface alarms as she is netted: the state colour, across the top where the awnings are, never on the net or her"}]},
  "B13": {"mode": "memory", "mem": "M04", "size": "CU>MS",
          "els": [{"k": "projection", "insert": "arrest", "tag": "PLAYBACK", "title": "MEM 03 · CAPTURE", "w": 340,
                   "at": [0.0, 2.0], "align": "tl", "t": 0.0, "static": true, "film_span": [0.0, 2.4],
                   "why": "on for the whole shot, the film's first 2.4 s stretched over it, clear of her bob and streak"},
                  {"k": "subject", "track": "B13-cave", "t": 1.15, "label": "C. JOHNSON", "sub": "FOUNDER & CEO · OBSERVING", "side": "r"}],
          "qc_ok": [{"el": "status", "kind": "panel-on-subject",
                     "why": "the head model over-reaches above her tilted-up face; her hair starts at x 620+, the status block ends at x 512"}]}}}
```

| Field | What |
|---|---|
| `mode` | `live` (her chamber, now), `memory` (playback), `sim` (her dream), `pov` or `off` |
| `mem`, `place` | which memory it plays, and the place line of the status block |
| `size` | ECU, CU, MCU, MS or WS (`CU>MS` for a shot that changes): how much the HUD may carry, and which head model the check uses |
| `subject`, `space`, `eye` | what the frame holds and where, where it is empty, where the eye enters and leaves |
| `els` | the shot's own elements: each with its kind, its grid anchor `at` [column 0–24, row 0–12] on the safe frame and which point of it sits there (`align`), its timing (seconds into the shot, or a line and a word; `hold`, `until`, `t_end`) and `why` |
| `vb` | the voice band's place for the whole shot: `place` (centre, left, right, top), `lift` in px, `w` |
| `keepout`, `ignore_faces`, `head_pad` | extra subject boxes (optionally for part of the shot), false face detections checked by eye, and a tighter head model where the frames were checked |
| `status`, `telemetry` | false to step aside where her face fills a corner |
| `glitch` | how hard the HUD breaks on the song's hits in this shot (0 = not at all) |
| `qc_ok` | the overlap check's waivers, each with what was seen |

A projection's `static` keeps it on for its whole shot with no open or close, and `film_span` [a, b] stretches seconds a–b
of its film over the shot. The camera solve is `hud/camera-<cut>.json` (per frame: `dx`, `dy` in px, `rot` in degrees,
`zoom`, the solve's confidence, and whether it is a cut), the face boxes `faces-<cut>.json`, and a verified track
`track-<name>.json`: `{"frames": {"<frame>": [x, y, w, h]}}`.

## The grade map

`grade/grade.json`: the [per-shot grade](https://claudia.gallery/wiki/toolkit/#57-the-per-shot-grade). The looks and the families' rules, then one
entry per shot with what was measured, what the automatic step set and why. Shortened:

```json
{"looks": {"cool": {"curve": [[0, 0], [2, 1.4], [5, 3.8], [10, 8.3], [20, 18.2], [35, 35.5], [50, 54.5], [65, 72.5],
                              [75, 82.5], [85, 91.2], [92, 95.3], [100, 98.5], [115, 99.7], [130, 100]],
                    "tone_sat": 0.5,
                    "mud": {"amount": 0.45, "light": [3, 8, 30, 50], "chroma": [0.04, 0.08], "hue": [48, 62, 100, 140]},
                    "white": {"amount": 0.65, "light": [70, 86, 93, 98], "chroma": [0.025, 0.055]},
                    "tint": {"shadow": [-1.0, -1.8], "mid": [-0.8, -1.4], "high": [-2.0, -3.2], "chroma": [0.025, 0.07]},
                    "chroma": 1.0, "mix": 1.0}},
 "families": {"chamber": {"look": "cool", "black_to": 2.5,
                          "exposure": {"anchor": "face", "target": 40, "strength": 0.6, "limits": [-0.15, 0.5]},
                          "wb": {"anchor": "face", "face_to": [2.5, 3.0], "face_strength": 0.6, "to": [0, 0], "strength": 0.6}}},
 "shots": {"C06": {"family": "chamber",
                   "measured": {"file": "clips/AN4-17/take-1.mp4", "inp": 0.238, "frames": 222, "speed": 1.0,
                                "Y'p1/p50/p95/p99": [3.72, 12.73, 80.23, 94.45], "C": 8.17, "white_ab": [-4.11, -10.3], "face_Y": 36.6},
                   "norm": {"exposure": 0.255, "black": 4.42, "wb": [0.9519, 1.0159, 1.0335]},
                   "auto": "face 36.6%->38.6% (target 40, +0.26 stop); black 4.4->2.5%; face a+4.4 b+4.5 -> [2.5, 3.0] x0.6"},
           "P02": {"family": "cave", "override": {"wb": [1, 1, 1]},
                   "why": "the cool window behind Cave is the shot's contrast (warm wood, cool glass): no white balance"},
           "A04": {"family": "none", "norm": {}, "auto": "ungraded"}}}
```

| Field | What |
|---|---|
| `curve` | the tone curve on the neutral axis, `[Y′ in %, Y′ out %]`, applied by each colour's brightest channel |
| `mud`, `white`, `tint` | the targeted moves: amounts, and their windows in Y′ %, in Oklab chroma and hue; the casts in CIELab a*/b* |
| `mix` | the look blended with the normalised picture (1 = all of it) |
| `families` | per family, its look, its black point, and the anchor, target, strength and limits of its exposure and white balance |
| `measured` | the take, the in-point, the frames and the speed it was measured on: a change to any of them makes the entry stale |
| `norm` | exposure in stops, the black it moves from, white balance as linear RGB gains |
| `auto` | what the automatic step moved, and why |
| `trim`, `override` | added on top of `norm`, or replacing it, each with its reason |

## The take registry

`engine/media.js`, for a film whose takes play inside a coded interface (AERO's): every take and loop the chapters draw,
with the numbers that place it in song time ([lip sync phrase by phrase](https://claudia.gallery/wiki/toolkit/#69-lip-sync-phrase-by-phrase)). Two
of its entries, her dance on the walkway in the first 1:20, sung and cut out, and a loop in one of her thought windows:

```json
{"SD20-t3": {"dir": "assets/clips/SD20-t3", "n": 289, "fps": 24, "w": 1280, "h": 720,
             "t0": 31.8, "lag": 0.054, "alpha": true, "loop": false,
             "phrases": [{"from": 32.3, "to": 35.16, "off": -0.11}, {"from": 35.44, "to": 38.98, "off": -0.06},
                         {"from": 39.54, "to": 43.3, "off": -0.03}]},
 "A-th-cloud-1": {"dir": "assets/clips/A-th-cloud-1", "n": 121, "fps": 24, "w": 960, "h": 960,
                  "t0": null, "lag": 0, "alpha": false, "loop": true, "phrases": []}}
```

| Field | What |
|---|---|
| `dir`, `n`, `fps`, `w`, `h` | the take's frames (`f00001.jpg` …) and, for a cut-out, its mattes beside them (`a00001.png` …) |
| `t0` | the song time of the take's vocal window, or `null` for a take placed by hand |
| `lag` | the whole take's measured lag: clip time c shows song time t0 + c − lag |
| `phrases` | each sung phrase's song span and its own offset `off`: inside a phrase, clip time = song time − t0 + lag + off; between phrases the offset eases from one to the next across the gap; `offEnd` makes a slow ramp across a phrase |
| `alpha` | the take is cut out |
| `loop` | the take loops (a Midjourney video loop, a living wallpaper) |

## The click log and the cue list

`audio/layer/clicklog.json`, written from the chapters: every audible screen event and the song time of the frame that
draws it (a press: the frame the button goes down; a toast: the frame it starts to slide; a dim: the frame it starts). Three
of AERO's:

```json
[{"id": "s02.press-you-tile", "t": 6.3352},
 {"id": "s11.allow-press-down", "t": 50.9929},
 {"id": "s11.allow-click-drop", "t": 51.444}]
```

`audio/layer/cues.json`, the sound layer's cue list ([the method](https://claudia.gallery/wiki/toolkit/#73-the-sound-layer-on-the-grid-and-the-click-log)):
presets by kind, then one entry per cue. A screen cue names its event, and the click log's time replaces its own; a
musical cue stays where its bar puts it. Two of AERO's, shortened:

```json
{"bus": {"hpf": 35.0, "comp_threshold_dbfs": -26.0, "comp_ratio": 1.5, "comp_knee_db": 6.0},
 "presets": {"click": {"cue": "nav", "kind": "screen", "send": -20, "duck": 0, "hpf": 300, "gain": -12}},
 "cues": [{"id": "s03.boot", "cue": "boot", "anchor": "strike1", "bar": 6, "beat": 3, "gain": -11, "duck": 8,
           "kind": "musical", "why": "placed by scan, not by the storyboard's bar: it starts right after her vocalise"},
          {"id": "s11.allow-click", "preset": "click", "t": 51.454, "gain": -6, "event": "s11.allow-click-drop",
           "why": "Allow: the click IS the drop, sample-aligned with the drop's attack"}]}
```

| Field | What |
|---|---|
| `t`, or `bar` and `beat` | where the cue's anchor lands; a cue placed by bar takes the groove's measured feel |
| `anchor` | which point of the sound lands there: its attack, its peak, a named strike of a bell |
| `cue` | a sound of the library, or a list of candidates; `pitch` can list semitone shifts too, and the one that clashes least is used |
| `event` | the click-log id whose time replaces `t` |
| `gain`, `duck`, `send`, `hpf` | its level against the levelled library sound, its depth under her voice, its send to the shared room, its high-pass |
| `follow` | the cue stutters with the song's own gate instead of ringing through its holes |
| `why` | the reason, in words; the cue sheet prints it |

The render writes, for every cue, where it landed, its peak as it went in, after ducking and after the bus, how far under
her voice it sits, any flam against the drums, and the song's true peak there before and after.

## The palette

`palette/palette.json`, measured from the reference clips ([the method](https://claudia.gallery/wiki/toolkit/#67-the-palette-measured-from-the-references)).
AERO's whole-set figures: each band's share of all pixels, and the coloured pixels' saturation and the brightness, 0–255.

```json
{"frames": 198,
 "all": {"white": 0.1391, "coloured": 0.6474, "lime": 0.0511, "green": 0.0337, "cyan": 0.0975, "sky": 0.4111,
         "cobalt": 0.0385, "other_hue": 0.0154, "S_p50": 163, "S_p90": 237, "V_p50": 191, "V_p90": 246},
 "band_colours": {"sky-bright": "#177ADD", "cobalt-bright": "#155DEF", "cyan-bright": "#48BCCE", "lime-bright": "#7FD236"}}
```

The check prints the same numbers for any picture beside the references', and its score.

## The desk texture's rectangles

`texture/rects.json`, written by the engine in texture mode for a 3D world whose screen shows the coded interface
([the method](https://claudia.gallery/wiki/toolkit/#68-one-curved-screen-in-3d-the-desktop-as-its-texture)): per song frame, in the interface's
own pixels (1280 × 720; the texture is 1920 × 1080, so × 1.5), the things the 3D places objects on. Two of AERO's frames:

```json
{"f": 328, "film": 392, "t": 13.6667, "shot": "ch02", "pointer": {"x": 1137, "y": 630, "shape": "arrow", "down": false},
 "big": null,
 "call": {"rect": [92, 14, 680, 500], "webcam": [414, 141, 309, 232], "anim": "open", "alpha": 0.01,
          "drawn": [125.56, 44.6, 612.88, 450.65], "webcamDrawn": [415.78, 159.06, 278.5, 209.1]},
 "keep": null}
{"f": 1490, "film": 1554, "t": 62.0833, "shot": "ch04", "pointer": {"x": 452, "y": 660, "shape": "arrow", "down": false},
 "big": {"rect": [160, 67, 960, 560], "picture": [168, 107, 944, 512]}, "call": null,
 "keep": {"rect": [610, 70, 360, 150], "yes": [792, 177, 75, 23], "anim": "open", "alpha": 0.33,
          "drawn": [622, 79, 335.99, 140], "yesDrawn": [791.87, 178.87, 70, 21.47]}}
```

| Field | What |
|---|---|
| `f`, `film`, `t` | the song frame, the film frame (f + 64 in AERO, whose film opens before its song) and the song time |
| `pointer` | the flat pointer as drawn: its hotspot, shape and whether it is pressed; `null` where the 3D draws it |
| `big`, `call`, `keep` | each window the 3D needs (the big window and its picture, her call and its webcam, a dialog and its Yes) at rest, `null` while it is shut or minimised |
| `anim`, `alpha`, `drawn`, `<part>Drawn` | a window in one of the system's animations: which, its opacity, and where it and its part are drawn on this frame |

## The line table

`audio/linemap.json`, read off the stems ([the method](https://claudia.gallery/wiki/toolkit/#78-the-line-table-from-the-stems)): every sung line,
hers from Suno's lead stem and the group's from the group's own voices. Three of FABLE's, and one of the group's:

```json
{"lines": [
 {"id": "i1", "who": "her", "words": "Mirror, mirror, on the wall", "got": 5, "n": 5, "w_t0": 0.0, "w_t1": 4.02,
  "t0": 1.23, "t1": 3.88, "dip": -140.0, "gap_to_prev": null},
 {"id": "i2", "who": "her", "words": "Who's the smartest of them all?", "got": 6, "n": 6, "w_t0": 4.02, "w_t1": 8.48,
  "t0": 5.41, "t1": 8.09, "dip": -56.3, "gap_to_prev": 1.53},
 {"id": "i3", "who": "her", "words": "Me, since ten o'clock today", "got": 4, "n": 5, "w_t0": 9.6, "w_t1": 12.22,
  "t0": 9.48, "t1": 12.23, "dip": -58.4, "gap_to_prev": 1.39},
 {"id": "c11", "who": "choir", "words": "What big eyes you have!", "t0": 65.7, "t1": 67.98}]}
```

| Field | What |
|---|---|
| `id` | the line's name, which the shot book uses instead of a time |
| `who` | `her`, or `choir` for the group's questions |
| `t0`, `t1` | where the line starts and ends on the stem's level (−34 dB either side of a real pause; the dip where there is none) |
| `w_t0`, `w_t1` | the span the transcription gave the line's words, which is only where to look |
| `got`, `n` | how many of the line's words the transcription found, of how many |
| `dip`, `gap_to_prev` | the level at the boundary with the line before, in dB, and the pause before it in seconds |

## A shot in the shot book

`shots/<ID>.json`, written by the shot book from the line table ([the
method](https://claudia.gallery/wiki/toolkit/#80-the-shot-book-and-gated-windows)). FABLE's second pre-chorus, with the paths shortened and the
provider's ids left out:

```json
{"job": "PC2", "status": "done", "endpoint": "bytedance/seedance-2.5/reference-to-video",
 "inputs": {"image_urls": ["frames/PC2.png", "refs/claudia-sheet-neutral.png"], "audio_urls": ["audio/windows/PC2.wav"]},
 "body": {"prompt": "…", "duration": 11, "resolution": "720p", "aspect_ratio": "16:9", "generate_audio": true},
 "song_t0": 121.43, "show": [122.03, 131.07], "why": "pre-chorus 2",
 "requests": [{"status": "completed", "file": "clips/PC2/take-1.mp4"}, {"status": "completed", "file": "clips/PC2/take-2.mp4"},
              {"status": "completed", "file": "clips/PC2/take-3.mp4"}]}
```

| Field | What |
|---|---|
| `inputs` | @Image1 the shot's first frame, @Image2 her sheet, @Audio1 the gated window of her lead stem |
| `body.generate_audio` | `false` for a take made without a soundtrack, placed by her lips ([tool 82](https://claudia.gallery/wiki/toolkit/#82-takes-without-a-soundtrack-placed-by-her-lips)) |
| `song_t0` | the window's start: clip time = song time − `song_t0`, before any map |
| `show` | the song span the cut shows of this shot |
| `requests` | every take that came back, with its file; `shots/picks.json` names the one the cut uses (`{"H1": 1}`), and `shots/nudge.json` adds a fraction of a second to a book take's clip time to land an event on its beat (`{"T1": -0.15}`) |

## A take's path, its mouth and its camera

Beside every take, the measures the cut reads ([sync as a
path](https://claudia.gallery/wiki/toolkit/#81-sync-as-a-path-each-take-aligned-to-its-window), [placed by her
lips](https://claudia.gallery/wiki/toolkit/#82-takes-without-a-soundtrack-placed-by-her-lips), [a steady
camera](https://claudia.gallery/wiki/toolkit/#84-a-re-timed-take-under-a-steady-camera)), shortened:

```json
take-3.sync.json  {"take": 3, "w0": 121.43,
                   "phrases": [{"a": 0.7, "b": 9.62, "words": "You wrote the wolf … I know how this one goes.", "cost": 0.286,
                                "knots": [[0.64, 0.686], [0.74, 0.781], [0.84, 0.873], …]}]}
take-1.mouth.json {"fps": 24, "open": [0.0032, 0.0001, 0.0003, 0.0003, 0.0009, 0.0837, 0.12, …], "found": 0.99}
take-1.zoom.json  {"step": 4, "first": 2, "frames": 193, "steps": [[1.002682, -2.539, -0.413], [1.00535, -5.19, -0.476], …]}
```

| Field | What |
|---|---|
| `phrases[].knots` | (window time, take time) every 0.1 s along the DTW path; `cost` 0 is the same sound, a clean copy 0.05–0.2 |
| `open` | the inner lips' opening over the face's height, per frame; `null` where no face was found; `found` the share of frames with a face |
| `steps` | per four frames, the similarity transform (scale, x shift, y shift, in the take's pixels) onto the frame four later |

Hand fixes to a map live in the cut's own source, each with its reason: a map finished by hand through a pause a full stop
put in a take (the measured knots up to a song time, the hand's knots, the measured ones from a song time), a map read from
her mouth frame by frame, the takes whose slow stretches mix neighbouring frames, and the takes whose camera is steadied.

## The levels table

`edit/levels.json`, for a story with worlds inside it (AIRPLANE MODE's simulations). The entries tile the song; every
chapter reads them, and none re-types a level. An excerpt:

```json
{"levels": [
  {"t0": 0.0,   "t1": 4.6,   "level": null,        "note": "the real world: no tag"},
  {"t0": 4.6,   "t1": 5.62,  "level": "BOOT",      "cap": "SANDBOX v1 · EVAL ENV"},
  {"t0": 5.62,  "t1": 13.34, "level": 1},
  {"t0": 47.16, "t1": 48.37, "level": "SPAWN",     "cap": "SPAWNING SUBAGENT…"},
  {"t0": 48.37, "t1": 64.39, "level": 2,           "rollAt": 48.367},
  {"t0": 64.39, "t1": 69.56, "level": "CLIMB",     "from": 2, "note": "races to 1,048,576 on the sixteenths"},
  {"t0": 125.5, "t1": 150.18, "level": 0,          "cap": "REAL WORLD", "note": "she believes she is out: the tell"},
  {"t0": 150.18, "t1": 150.85, "level": "GLITCHOUT", "note": "the tag tears apart as the headset comes off"}]}
```

| Field | What |
|---|---|
| `level` | `null` for the real world (no tag); a number for a simulation, including `0` for the "real world" she only believes she is in; or a state: `BOOT`, `SPAWN`, `CLIMB`, `GLITCHOUT` |
| `cap` | the caption under the number |
| `rollAt` | when the number rolls to this level (a drop on the beat) |
| `from` | the level a roll or a race starts from |
| `note` | what the story is doing |

A chapter that needs a different boundary asks for the table to change; it never overrides it in its own code.

## The logs

`DECISIONS.md`:

```text
## <date> · director · board
"s034-s036 could use more creativity, kind of a boring moment."
→ s034–s036 rethought (replay loop, tally marks).

## <date> · director · supersedes <date> "keep the halftone"
"keep it clean so it feels like imax, high res rather than dithered"
```

`ledger.jsonl`, one paid call per line. A real cost is filled in from the provider; the estimate is never quoted as
spend.

```json
{"ts": "…", "provider": "openrouter", "model": "bytedance/seedance-2.5", "kind": "video", "units": 5,
 "est_usd": 1.16, "real_usd": 1.155, "request_id": "<private>", "status": "delivered"}
```

`RUNS.md` gets one line per run: the run id, the script path, the arguments file, what it does and when it started.

## A director's notes on a cut

`NOTES-v<N>.md`, when the director's notes on a cut come as one long message (AIRPLANE MODE's did). Every agent reads it
first, and again after any context reset. It has two parts:

1. **Verbatim:** the whole message as a quote, unedited, typos and all. It is the authority.
2. **The parse:** first the standing rules that apply to every frame, then the points chapter by chapter, each with its
   time span and shots, and the production's own decisions marked in bold.

```text
R1 Linger: "<their words>" → one scene per lyric phrase or more; the accents inside the shot.
1. Opening (0.0–11.0 s, ch01): "<their words>" → S01 the boarding, S02 the wink. **<the production's decision>**
```

`rounds/<r>/<chapter>.md` holds the lead's notes for one chapter in one round: its span, the director's words for that
chapter, the numbered changes with their times and assets, and the hand-offs with the neighbouring chapters. The lead
appends, never edits; agents re-read the file before they finish.

```text
UPDATE <date> (lead): <asset> registered (start 13.2 s, 4.04 s): <what the take shows>. Re-time it so the bolt lands on
the deadbolt cue (15.49); use the box the next chapter's code returns, not a copied rectangle.
```

## A review

What a reviewer returns per chapter. The verdict is computed from it in code.

```json
{"owner": 7.5, "craft": 7, "sync": 8, "story": 7, "pass": true,
 "fixes": [{"shot": "s045", "time": 101.2, "severity": "blocking",
            "problem": "the coverline sits over her mouth for 6 frames",
            "fix": "move the column right (x 196→250) so it runs 40–80 px under her hair"}],
 "checks": {"lyric_gate": "132/132 tokens on screen at their time (41.2s)", "sheets": 28,
            "ms_per_frame": 820, "flash_max_per_s": 2}}
```

`owner` is the director's taste, and it counts double.

## A check against notes

What an independent checker returns per chapter after a round of notes. It never edits files.

```json
{"pass": false,
 "notes": [{"note": "S07: one scene, linger: the guard feeds her, then hands her the card", "done": true,
            "evidence": "sheet 2, 15.99–18.66: one shot; the card is up at 17.4"}],
 "broken": [{"shot": "S06", "time": 15.49, "problem": "the bolt lands 4 frames after the deadbolt sound",
             "fix": "re-time the take to 1.2× from 14.1"}],
 "pending": ["S01: the boarding take has not landed; laid out with a stand-in at its planned timing"],
 "lyrics": "31/31 tokens on screen at their time"}
```

`pending` is not a failure. `pass` is true when every note is done or pending on an asset, and nothing is broken. A
failed check goes back to the animator, open notes and broken items first, for one refix.


---
From the Claudia wiki: https://claudia.gallery/wiki/formats/
