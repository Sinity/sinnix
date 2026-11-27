# claudia-kit

A small toolkit for making a lip-synced music video of Claudia the way the films on claudia.gallery were made. It covers
the parts where the method decides the result: scoring the lyric, timing every sung line from the song's own vocal
stem, making the stills, writing the shot book and its prompts for Seedance 2.5, submitting the takes with a spending
cap, placing each take on the song word by word, and cutting the film with review sheets for a fresh pair of eyes. It
also runs a cheaper video model that takes a first frame only, Grok Imagine Video 1.5, with what that costs in lip sync
([below](#with-a-cheaper-video-model-first-frame-only)).

It is written for a coding agent (or a person) with a Suno song, its stems and a set of first frames. The method it
runs is [the recipe](https://claudia.gallery/wiki/recipe/) (one page; read it first, it has the checkpoints where a person
decides). Her reference sheets: [claudia-face-sheet.png](https://claudia.gallery/kit/claudia-face-sheet.png) (her face, for
every take that shows it) and [claudia-reference-sheet.png](https://claudia.gallery/kit/claudia-reference-sheet.png) (face and
body, for full-length shots). Every stage is a
command that reads and writes plain JSON, so you can stop anywhere, look, change a file and go on. The films are
directed by anabology; the kit is released under the MIT licence.

## The method, in order

1. **Concept.** What the video is, in one sentence, and the world it happens in.
2. **The lyric, scored.** `lyric score` puts every syllable on a 4/4 grid (spoken, sung or chanted) and reports two
   numbers per section: SCANSION (how well the lines sit on the beat) and ASSONANCE (how the line ends ring together).
   `lyric rewrite-loop` ranks rewrites from any LLM you use, round after round.
3. **Suno takes, picked by ear.** Make several takes and listen. The director picks the take by ear, before anything
   is spent on pictures; no measure in this kit replaces listening.
4. **Stems.** From Suno, export the lead vocal and everything else (they line up with the song's WAV to the sample).
   Without them, `songmap separate` runs demucs. A group answering the lead lives in the backing: separate its vocals
   too, and name that file as the group stem.
5. **The line table.** `songmap all` finds when every lyric line really starts and ends, from the lead stem's level. A
   transcription (faster-whisper or any other) only says which words are where: after a pause it puts the next word
   early, by up to 2 s, and a window cut on that time loses the first word. Read the table, check where lines touch with
   `songmap prof`, fix by hand what needs it.
6. **References right.** Her face sheet: one large portrait, face-on and neutral, with her head from every side and a
   row of expressions (upright belongs on the sheet, not in the performance);
   one first frame per shot of the board, made by an image model from her sheet and her identity text (Midjourney is
   good for the worlds and plates; in the recent films it did not hold her face); never the same first frame for two takes unless one continues the
   other; a last frame made as an edit of the first (two frames made separately do not share a camera, and the model
   joins them with a dissolve). `frames make` makes the stills the book's `stills` block describes with GPT Image 2.6
   Sunburst on Replicate (about $0.13 a still at high quality), and `frames edit B --from A` makes B as an edit of A.
7. **The shot book and lint.** Shots name lines, never times, so a new take of the song re-times the whole book.
   `shotbook build` writes each shot's window, its gated vocal and its prompt; `shotbook lint` flags what has cost
   takes before; `shotbook board` puts the first frames, windows and lines on one sheet to look at before paying.
8. **Takes.** `run --dry-run` first. Then one take per job, with `--max-usd` as the cap. Nothing is ever resubmitted
   automatically. In the films every take that carried her face sheet ran on Higgsfield's API (`--provider higgsfield`),
   and the takes with no person in them on Replicate (`--provider replicate`). A first-frame model runs on OpenRouter
   (`--provider openrouter`) or Replicate (`--model xai/grok-imagine-video-1.5`).
9. **Sync.** `sync align` maps song time to clip time for every take, along a path, not by one offset; `sync check`
   says which phrases were re-sung, drifted or paused where the song does not; `sync lips` checks her lips shut on
   every b, m and p. A take from a model that never heard the song is placed by her lips, and `sync check` says how
   well they match.
10. **The cut.** `cut render` lays every take on the song along its map, then lays the song over the picture with one
    plain gain toward -14 LUFS that never takes its peak past -1 dBFS (no compressor, no limiter); `cut audit` lists
    holds, reused takes and hard bends; `cut flash` is the photosensitivity check.
11. **Fresh-eyes review.** `cut sheets` makes one sheet per shot, eight frames as shown in the film. Give them to
    someone (or a model) who has not read the prompts, and ask what reads wrong.
12. **Fix only what was flagged.** Re-take or re-map those shots; leave the rest alone.

## Install

Python 3.10 or newer, numpy and the ffmpeg command-line tools (ffmpeg and ffprobe on your PATH).

```sh
pip install -r requirements.txt                 # numpy
python3 -m claudia_kit lyric fetch-dict          # CMUdict into ~/.cache/claudia-kit (or pass --dict FILE)
```

Optional, each imported only by the step that needs it, with a message if it is missing:

| Package | Used by | Why |
|---|---|---|
| `faster-whisper` | `songmap words` | word labels for the line table (strongly recommended: without them the table is a rough guess) |
| `Pillow` | `cut render`, `shotbook board` | frames for the film and the board |
| `mediapipe` (+ OpenCV, which it installs) | `sync mouth`, `sync lips`, sound-off takes | her mouth's opening per frame |
| `demucs` | `songmap separate` | stems when you have none, and the group's voices from the backing |
| `wordfreq` | `lyric score` | flags rare words, which get misheard when sung |
| `PyYAML` | any stage | a shot book written as `book.yaml` instead of JSON |

MediaPipe needs its face landmarker model: download `face_landmarker.task` from the Face Landmarker page of Google's
MediaPipe documentation (Google AI Edge) and pass it as `--face-model`.

Keys come from the environment only, and are never printed: `REPLICATE_API_TOKEN` (`frames`, and `run` on Replicate),
`HIGGSFIELD_API_KEY` as `id:secret`, `OPENROUTER_API_KEY` (`run` on OpenRouter).

Run every stage as `python3 -m claudia_kit <stage> ...` from this folder (or put it on PYTHONPATH; `python` where that is
your Python 3). Each stage has `--help`.

## A 20-minute walkthrough

The demo makes a synthetic song from the example lyric (a buzzing "voice" placed on the beat by the kit's own scansion
model, a drum loop and a three-voice group), flat colour cards as first frames, and later stand-in takes that sing their
own windows 0.12 s late and 4% slow, the way real takes drift. Nothing is sent anywhere and nothing is paid.

```sh
python3 examples/demo.py audio demo                      # demo/: lyric.txt, book.json, audio/, frames/, refs/
python3 -m claudia_kit lyric score demo/lyric.txt        # per line: score, groove, syllables, Suno's pace, problems
python3 -m claudia_kit songmap all demo/book.json        # beats, hits, phrases and the line table
python3 -m claudia_kit songmap prof demo/book.json 9 12  # the lead stem's level, 50 ms a column
python3 -m claudia_kit shotbook build demo/book.json     # windows, gated vocals, prompts, job files
python3 -m claudia_kit shotbook show demo/book.json S1   # one prompt in full
python3 -m claudia_kit shotbook lint demo/book.json
python3 -m claudia_kit shotbook board demo/book.json demo/board.jpg
python3 -m claudia_kit frames make demo/book.json --max-usd 1 --dry-run   # the stills block: what would be sent
python3 -m claudia_kit run demo/book.json --provider higgsfield --max-usd 10 --dry-run
python3 examples/demo.py takes demo                      # stand-in takes instead of paid ones
python3 -m claudia_kit sync align demo/book.json
python3 -m claudia_kit sync check demo/book.json
python3 -m claudia_kit cut audit demo/book.json
python3 -m claudia_kit cut render demo/book.json demo/film.mp4 --draft
python3 -m claudia_kit cut sheets demo/book.json demo/film.mp4 demo/sheets
python3 -m claudia_kit cut flash demo/film.mp4
```

What to look at:

- **The line table** prints one row per line: `L06 lead 32.40- 35.36 ...`. The demo has no transcription, so the
  table comes from the level alone (`check by ear`). With your own song, run `songmap words` first.
- **`shotbook build`** prints each window: `A1 sung w0 31.70 5 s show 32.10-35.40 voice 0.70-3.67 s, timeline
  0.70-3.66 s`. The voice must start in silence 0.5 to 1.0 s into the window.
- **The stills' dry run** leaves `S1` alone (`frames/S1.png exists: left as it is`: the demo's card is there) and shows
  the request for `Q1-end`, a last frame for Q1 made as an edit of its first: `<upload frames/Q1.png>` goes first, $0.13.
- **The dry run** prints exactly what would be sent and its list price, and stops at the shot that would pass the cap:
  `S2: $6.47 would take the ledger from $6.47 past the cap of $10.00; nothing sent`.
- **`sync check`** finds what the stand-in takes did: `cost 0.05 rate 1.04 offsets +0.14 +0.22 +0.27`: a clean copy
  (cost under 0.2), sung 4% slow, starting 0.14 s late and drifting later along the line. The cut follows that path.
- **The sheets** (`demo/sheets/04-A1-032.10.jpg` ...) show eight frames of each shot as the film shows it.

## With your own song

1. Make a folder with `audio/` (song, lead and rest stems, and the group stem if there is one), `lyric.txt` (every
   line as sung, repeats written out), `frames/`, `refs/sheet.png` and a `book.json` copied from the example.
2. `songmap words`, then `songmap all`. Read the table. Where two lines touch or a line looks wrong, look at
   `songmap prof A B` and add `"line_fixes": {"L14": [null, 65.56]}` to the book (null keeps the measured edge).
3. Write the shots: which lines each sings, what she does in each, the first frame, the camera. One line per take for
   anything sung fast; two lines in 9-10 s for verses. Write a still for each first frame in `stills` and make them
   (`frames make --dry-run`, then with a cap; a low-quality draft first if you like). Build, lint and board until lint
   is clean and the board looks right.
4. Run a dry run, then the takes with a cap. Sync, check, and look at every flagged phrase.
5. Cut, audit, sheets, flash. Fix only what the review flagged: a new take (`picks`), a nudge, or hand knots.

## With a cheaper video model (first frame only)

Grok Imagine Video 1.5 costs about a third of Seedance 2.5 on Higgsfield's API at 720p, and its Lite version less again.
It takes a first frame and a prompt, and nothing else: no reference sheet, and no audio, so it cannot hear the song.
Set the book's `"video_model"` to `"grok-imagine-video-1.5"` (or `"grok-imagine-video-1.5-lite"`; any name without
"seedance" gets the same form) and the kit changes in four places:

- **Stills do all the identity work.** The take knows her only from its first frame, so make each first frame from her
  sheet and her identity text (`frames make`), check it against the sheet, and give each take its own.
- **The prompts are short plain prose** (`shotbook build`, `shotbook show`): the goal, one whole-second step a line,
  the words she sings in quotes so her mouth moves to them, a smile in her eyes while she sings, the camera in one
  line, her look as in the first frame, natural anatomy, one of her, no on-screen text. About 80-150 words: these
  models are not tuned for long structured prompts. The window still sets each take's length and where it sits on the
  song; no sound is sent. `shotbook lint` knows the form: no @Audio1 to check (none is sent), a length note over 150
  words, a last frame is an error (Grok takes none), and a pull-back is a warning.
- **`run` sends the first frame alone,** as a JPEG at the take's size: `--provider openrouter` (`--model
  x-ai/grok-imagine-video-1.5`, `x-ai/grok-imagine-video-1.5-lite`, or any video model OpenRouter lists; by default the
  book's video_model), with prices and limits read from OpenRouter's list at run time; or `--provider replicate --model
  xai/grok-imagine-video-1.5` (480p and 720p; Replicate publishes no price for it, so the kit assumes OpenRouter's and
  says so: give `--rate` when you know it).
- **Sync goes by her lips.** A take comes back with a sound of its own invention (or none), so `sync align` never
  matches it against the song: it places each sung phrase on her mouth's own open runs and each b, m and p on the frame
  where her lips part (`--face-model`, as for takes without sound). `sync check` then prints, per phrase, the mouth run
  it went on and its rate, and, as cut, how often her mouth is open where she sings and shut where she does not.

Lip sync placed by her lips is approximate. The model sings the quoted words at its own pace and its mouth shapes are
its guess at them, so the words land near their syllables, not on them, and a close shot of her singing is where it
shows. Frame the film so it does not depend on exact lips: medium and wider shots, her moving (walking, turning,
dancing) and the camera moving, cutaways (her hands, the place, a `noface` or `silent` shot) over lines that matter
less, and only a few short close singing shots, each from the take whose lips check best.

What Grok Imagine did in an earlier film: it pushed in when asked to pull back (for a wordless shot, ask for a push-in
and play the take backwards), it redrew a painted frame during a pull-back, and it garbled label text in big push-ins.
A Lite take at 480p came back 736 x 400, a little wider than 16:9: the cut fills the frame and crops the edges (`cut
audit` says so; a `crop` in the book decides instead).

| Model | Where | 480p | 720p | 1080p |
|---|---|---|---|---|
| Grok Imagine Video 1.5 | OpenRouter | $0.08 a second | $0.14 | $0.25 |
| Grok Imagine Video 1.5 Lite | OpenRouter | $0.02 a second | $0.03 | $0.14 |
| Grok Imagine Video 1.5 | Replicate | assumed as OpenRouter's | as OpenRouter's | none |
| Seedance 2.5, for comparison | Higgsfield's API / Replicate | $0.21 / $0.10 | $0.46 / $0.23 | $1.14 / none |

OpenRouter adds $0.01 for each input image. A still from GPT Image 2.6 Sunburst on Replicate costs $0.05 at low quality,
$0.09 medium, $0.128 high, $0.25 xhigh and $0.50 max. List prices from November 2026 (Seedance's from October);
providers change them.

The demo runs the same way, free (nothing is sent anywhere but a request for OpenRouter's public price list, and
without a connection the kit uses its own). Its stand-in takes carry a sound of their own and a stand-in mouth measure,
since a colour card has no face to measure:

```sh
python3 examples/demo.py audio demo-ff --video-model grok-imagine-video-1.5
python3 -m claudia_kit songmap all demo-ff/book.json
python3 -m claudia_kit frames make demo-ff/book.json --max-usd 1 --dry-run
python3 -m claudia_kit shotbook build demo-ff/book.json
python3 -m claudia_kit shotbook show demo-ff/book.json A1
python3 -m claudia_kit shotbook lint demo-ff/book.json
python3 -m claudia_kit run demo-ff/book.json --provider openrouter --max-usd 5 --dry-run
python3 examples/demo.py takes demo-ff
python3 -m claudia_kit sync align demo-ff/book.json
python3 -m claudia_kit sync check demo-ff/book.json
python3 -m claudia_kit cut render demo-ff/book.json demo-ff/film.mp4 --draft
```

`shotbook show ... A1` prints the whole prompt:

```
One answer in the call and answer: she answers the radio. Her manner is warm and open: she enjoys singing to us.
0-1s: her lips closed; she listens to the radio, eyes bright.
1-4s: she sings "Only me, and you below"; she leans toward the radio and points down through the floor at the sea below.
4-5s: her lips closed; she sits back with a closed-lip smile.
While she sings there is a smile in her eyes, never a grin.
Camera: Locked close shot as in the first frame; no cuts.
Claudia looks as in the first frame, wearing a heavy navy wool coat over a cream fisherman's jumper, dark trousers and black boots; natural anatomy, five fingers on each hand. Only one Claudia appears. No on-screen text.
```

Lint warns about A2's crane up and back; the dry run sends each first frame as `<JPEG data URL of frames/S1.png at
1280x720>` at $0.14 a second and stops at A1, which would pass the cap; `sync check` says `placed by her lips (the
model did not hear the song)` with each phrase's mouth run and rate (the stand-in's mouth is right by construction: a
real take reads lower, and the b, m and p need word times from `songmap words`).

## What the prompts do, and why

The prompts follow the structure the films used for Seedance 2.5 (Audio Policy, Generation Goal, Reference Asset
Roles, Subject, World, Performance Timeline in whole seconds, Camera, Core Requirements), with what was learned since
(the first-frame form [above](#with-a-cheaper-video-model-first-frame-only) keeps the same lessons in fewer words):

- **The model takes every word literally.** Define precisely only what matters: the words she sings, their seconds,
  the key action. Leave the rest to the reference images, which carry her identity.
- **No standing posture rules in a performance.** Rules like "head upright, no tilt, faces the camera with her whole
  body" made her read frozen. Write movement into each second instead: a turn of the head, a nod, a step, a gesture.
- **One mood word, warm by default.** Stacked mood and irony words (dry, deadpan, knowing, smirk...) are each obeyed,
  and together they read as unhappy or menacing. The book's `manner` sets her register; it defaults to warm.
- **A full stop is a pause.** A full stop between words she sings straight through became a pause in the take, so the
  kit writes those with commas and keeps a full stop only where the stem has a real pause.
- **A take hears only its own words.** The window opens about 0.7 s before her first word, in silence; the lead stem is
  gated to the shot's lines with 20 ms fades; every timed segment holds the words really sung in it.
- **Looks stay in front of her.** A look past the lens or behind her turns her head too far; point at what is behind
  her with a hand. Don't pin her eyes to the lens take after take: it reads as a stare. Name every garment that can
  come into view.
- **A smile in her eyes while she sings.** "Smiling" over sung words drew a toothy grin; her lips stay closed until her
  voice begins.

## The files

**`lyric.txt`**: Suno's lyrics field, every line as sung. `[Section - description]` headers (the words spoken, sung,
chant or chorus in the description set the scoring mode); `(parentheses)` are the group's voices; `#` lines are
comments. A `pron.json` beside it adds pronunciations: `{"claudia": "K L AO1 D IY0 AH0"}`.

**`book.json`, the shot book**, everything relative to its own folder:

| Key | What |
|---|---|
| `lyric`, `build`, `audio` | the lyric file, the output folder, and `song`, `lead`, `rest`, `group`, `words` |
| `character`, `subject`, `sheet` | her name in the prompts, her identity text from the canon, word for word (drop the headset clause when the look has none), her face-on sheet |
| `looks`, `world`, `manner` | named outfits (every garment that can show), the world in one paragraph, her default register |
| `video_model` | `seedance-2.5` (the default: her sheet and the vocal go with each take) or a first-frame model such as `grok-imagine-video-1.5` (a short plain prompt, the first frame alone) |
| `defaults` | `lead_in` (0.7 s), `resolution`, `aspect_ratio`, `sound` |
| `stills` | `{"S1": {"prompt", "images", "aspect", "quality", "from"}}`: what `frames` makes, into `frames/<id>.png` |
| `lint` | `names`: real names and brands to flag; `allow`: names that are fine |
| `line_fixes` | `{"L14": [t0, t1]}` by hand; null keeps the measured edge |
| `picks`, `nudge`, `knots`, `crop`, `sections` | the edit: the take per shot, seconds added to its clip time, a hand map, a crop in take pixels, render sections |

A shot: `id`, `kind` (`sung`, `silent` or `noface`), `first_frame`, optional `last_frame` and `last` (what it shows),
`look`, `goal`, `place`, `camera`, and:

- `sung`: `timeline`, a list of `["rest", "what she does"]` and `["L05", "what she does while she sings L05"]`;
  optional `sound` (false: a take without its own soundtrack, placed by her lips), `manner`, `lead_in`, `duration`,
  `show`, `punctuation: "as written"`.
- `silent` (her on screen, no voice) and `noface` (no face: objects, sets, puppets): `duration`, `events` in contiguous
  whole-second steps (`"0-2s: ..."`), and `at` (a line to start near) or `w0` or `show`. `noface` also takes `first`
  (what the first frame shows) and `keep`.
- For the cut: `show` (the song span shown; by default from the last beat before her first word to where the next shot
  starts), `dissolve` (frames from the shot before), `blend` (mix neighbouring frames where the map slows the take).

A still: `prompt` (`{subject}`, `{world}` and `{look:NAME}` stand for the book's own words), `images` (sent in that
order: name them in the prompt as the first image, the second image ...), `aspect` (a ratio such as `16:9`, or a size
such as `2048x1152`; by default the book's aspect ratio), `quality` (`low`, `medium`, `high` by default, `xhigh`, `max`)
and `from` (a still's id or an image, sent first: the new still is an edit of it).

Hand knots replace the measured map between their first and last song times. A first or last knot with a null clip
time says where the measured map stops and starts again: `"knots": {"S7": [[160.6, null], [160.9, 6.03], [161.0, 6.36],
[163.5, null]]}`. Use them to run a take's map through a pause the song does not have.

**`build/lines.json`**: one entry per line: `id` (L01, L02 ... in lyric order), `who` (lead or group), `section`,
`words`, `t0`, `t1` (song seconds), `pauses` (silences inside the line), and with a transcription `w_t0`, `w_t1`, `got`
of `n` words found, `words_t` (the words with their times), `dip` (the level at the boundary before it, dB) and
`gap_to_prev`.

**`build/jobs/<id>.json`**: what `run` sends, provider-neutral: `model` (the book's video_model), `form` (`seedance` or
`first_frame`), `prompt` (references written `@Image1`, `@Audio1`; `run` rewrites them as `[Image1]` for Replicate),
`images` (first frame, sheet, last frame), `audio` (the gated window, when it is sent), `window` (the gated window),
`mode` (reference or image), `duration`, `resolution`, `aspect_ratio`, `generate_audio`, `sync` (`sound`, or `lips` for
a take without its soundtrack or from a model that never heard the song), `w0` (the window's start: clip time = song
time - w0 before any map), `show`, `lines`, `segments` (the whole-second timeline) and `phrases` (her sung phrases in
window time). `build/windows/<id>.wav` is the gated vocal, exactly `duration` seconds.

**`frames/<id>.png`** and **`frames/<id>.json`**: a still and what was sent for it (prompt, images, aspect, quality,
`from`), the prediction's id, status and numbers, and its list price. A still made again with `--again` keeps the old
one as `frames/<id>.<n>.png`.

**`takes/<id>/`**: `take-N.mp4` (N never reused), `requests.json` (each submit: provider, model, id, status, file, and
`usd` where the provider reports what it cost), `take-N.sync.json` (`method`: sound, lips or none; `phrases` with `cost`
and `knots`; `lips` with each phrase's mouth run and rate; `map`: [song s, clip s] pairs), `take-N.mouth.json` (`fps`,
`open` per frame, `found`).

**`build/ledger.jsonl`**: one line per paid submit, takes and stills (`"kind": "still"`) in one ledger under one cap:
time, shot or still, provider, model, id, `usd_est` (list price), duration and resolution or quality, and `uncertain`
when the connection failed mid-submit. `run --ledger` adds it up.

## Known limits

- Placing a take by her lips can misread a phrase: a long hold or a stretch well below 1× (a dance at 0.57×). `cut audit` flags both; pin those takes to their window at 1× (`knots`) rather than let the cut slow her down.
- Without word labels the line table is a first guess: on one real song about one line in five landed within 0.1 s.
  With a transcription, every line the earlier tool had timed automatically landed within 0.06 s of it.
- The lips check takes word times from the transcription, so a b, m or p right after even a short pause can read
  late; judge by the median and by eye.
- A take whose map bends hard under a camera move can surge; `blend` hides the judder of repeated frames, not the
  surge. Keep bends small, or re-take.
- Prices are list prices recorded in October (Seedance) and November 2026 (stills, Grok Imagine); providers change
  them (`--rate` overrides a video price; OpenRouter's are read at run time). Replicate publishes no price for Grok
  Imagine: the kit assumes OpenRouter's.
- A take from a model that never heard the song is placed by her lips alone: approximate, best hidden by framing (see
  [above](#with-a-cheaper-video-model-first-frame-only)).
- Seedance 2.5 on Replicate or Higgsfield, first-frame models on OpenRouter or Replicate, stills on Replicate: only
  through their HTTP APIs.
- The cut renders frame by frame through Pillow: render a long film in `sections` and `join` them.

## Licence and thanks

MIT (see `LICENSE`). CMUdict is © Carnegie Mellon University under a BSD-style licence and is downloaded separately by
`lyric fetch-dict`, with its licence beside it. MediaPipe (Apache 2.0) and its face landmarker model are Google's and
are installed separately, under their own terms. The method comes from making the Claudia films, directed by anabology.
