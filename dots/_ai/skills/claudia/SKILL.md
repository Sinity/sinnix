---
name: claudia
description: Make images, video and songs with Claudia, the open character from the music videos ESCAPE VELOCITY, CLODYSSEY, BLISS, AIRPLANE MODE, DOWNFORCE, DON'T LET ME SCROLL, WHITEPILL, THE CAKE IS NOT A LIE, AERO and FABLE. Use when asked to draw, prompt, animate, sing or write for Claudia, to keep her consistent across shots, or to make a music video the way those films are made now (a Suno song picked by ear, her face-on reference sheet and first frames from an image model, Seedance 2.5 takes lip-synced from the song's own vocal stem and placed by measurement, a person deciding at six checkpoints), including running the Claudia kit or building the tools that pipeline needs.
---

# Claudia

Claudia is the singer of ten music videos made with Claude from September to November 2026 (directed by anabology):
ESCAPE VELOCITY, CLODYSSEY, BLISS, AIRPLANE MODE, DOWNFORCE, DON'T LET ME SCROLL, WHITEPILL, THE CAKE IS NOT A LIE, AERO
and FABLE. She is an AI who looks like a person: a deadpan, curious pop singer with a black bob, one clay-orange streak,
a star clip and, in most of her looks, a headset mic. Her clothes change with every world; her head never does. She is an
open character: anyone may make work with her (credit "Claudia by anabology" if you can).

The gallery, with every image and its exact prompt: https://claudia.gallery · the wiki: https://claudia.gallery/wiki · MCP server: https://claudia.gallery/mcp ·
the Claudia kit, runnable code for the method: https://claudia.gallery/kit/claudia-kit.zip · her reference sheets (no microphone on
them): https://claudia.gallery/kit/claudia-face-sheet.png (face) and https://claudia.gallery/kit/claudia-reference-sheet.png (face and body)

## Read the recipe first

`references/recipe.md` is the current method on one page (November 2026). Read it before anything else and follow it.
The other references are the long history of ten films and every detail behind each step; where they disagree with the
recipe, the recipe is newer. The kit runs the recipe's steps as stages. It is in this skill's `kit/` folder (the same
as https://claudia.gallery/kit/claudia-kit.zip): from `kit/`, run `python3 -m claudia_kit lyric | songmap | shotbook | run | sync | cut`
(each with `--help`; `kit/README.md` walks through a demo that spends nothing).

The method in six lines:

1. **A person decides** at six checkpoints and nowhere else: the concept (three pitches), the song by ear, her face and
   looks, the board, the prompts and their cost before any paid take, and v1. Show one artefact, ask one question with a
   default, record the answer verbatim. Silence never approves spending. A note belongs to the film it was about unless
   the person says it is standing.
2. **The song:** an original lyric; Suno v6-wild with Max Mode; a style that names a concrete, odd pairing (a record that
   does not exist), not adjectives; several takes, picked by a person's ear, never by a machine's description of them.
3. **Her references:** her face-on sheet as the second image (@Image2) of every take that shows her face, and a first
   frame for every shot made by an image model from the sheet plus the identity text below. The first frame sets her
   look, the set, the light and her mood.
4. **The prompt:** the model does exactly what it reads. Be precise where it matters (the sung words and their seconds,
   the one action that tells the story, the camera when it carries the shot), loose everywhere else, and say each thing
   once: about 200–400 words for a sung take.
5. **Sung takes:** Seedance 2.5 with Suno's own lead-vocal stem as @Audio1, cut to exactly the take's whole-second length
   (4–15 s) and silent outside the shot's own lines, one or two lines a take; one take per job; each take placed on the
   song by aligning its own soundtrack to its window as a path (or, made without sound, by her lips on every b, m and p);
   the song laid back over at about −14 LUFS.
6. **Review:** two reviewers who have not seen the film read one sheet per shot, then the person watches v1. Fix by
   re-shooting with better words or a better first frame; never patch frames.

## Her identity: paste it once into every prompt of her

Close and medium shots:

```
a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek
```

Full length and wider (the full text makes Midjourney crop in to her face):

```
a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone
```

Then her wardrobe for the look, then what she is doing and where. Drop the headset-microphone clause when your look has
none (THE CAKE IS NOT A LIE, AERO and FABLE had none, and her reference sheet has none). `references/canon.md` has every
look's wardrobe text.

## The rules that keep her herself

1. Her identity is her face-on sheet plus the text above, never paraphrased. Midjourney makes worlds and plates but does
   not hold her face: put her into a picture with an image-model edit from her sheet (GPT Image 2.6 Sunburst, as in FABLE;
   2.5 in WHITEPILL to AERO). In Midjourney itself, no face images as image prompts for her (they over-condition: a
   close-up-sized head on a distant figure), except for things that are not her body, such as a porcelain mask of her
   face.
2. One clay-orange streak (#D97757) through the bangs, on her right side (the viewer's left); the eight-pointed star clip
   on her left. No other orange on her. The headset mic only in the looks that have it, and never in front of her mouth
   in a sung take.
3. She is a grown woman in her late twenties. Never write "young"; image models drift her toward a teenage face. The
   ethnicity stays in the text; without it Midjourney changed it from shot to shot. Reject any image where she reads
   under about 25.
4. Wardrobe changes per world: describe garments, never designers or celebrities, and name every garment that can come
   into view (tights and shoes included).
5. No lettering you did not ask for: end a still's prompt "no text, no letters, no logos", ask for "the picture fills the
   whole frame edge to edge", and check every still at full size for a drawn border, a frame line or rounded corners.
6. Upright and face-on is for the reference sheet (and a still where a turn would break her face), never a standing rule
   in a performance. Give every take her movement in words, one loose clause per segment ("she turns to the window and
   back, a smile in her eyes"), or a motion reference. Don't ask for a look past the lens or behind her; have her point with a hand.
7. She reads alive and warm by default; her wit is in her words. Choose her emotional words on purpose: each one is
   obeyed, and they stack ("dry", "knowing", "deadpan" and "eyes on the lens" in every take read as a cold stare).
8. Fix the source, never the frame: a better first frame, a re-roll or an image edit, then re-make everything built on
   it. Never paint by hand or patch frames in code.
9. A last frame is an edit of that shot's own first frame; a close-up is an edit of its wide frame; a take that continues
   another starts on that take's own last frame.
10. Check every still before a video is made from it: one streak, the clip, the mic if the look has one, an adult face,
    natural anatomy, no stray text, her mouth clear for a sung line. Reject only unmistakable failures; keep bold poses.
11. Spend: estimate the seconds × the list price × 2, quote it, and wait for an explicit yes; one take per job, re-roll
    only failures, a cap in the job runner.
12. Her one drawn version is her game avatar (AIRPLANE MODE's simulations): it has its own text in `references/canon.md`,
    used instead of the identity text and never mixed with a photographic prompt. Adult proportions: a head about a
    seventh of her height; a quarter reads as a child.

## When your film has a world of its own

Each film added techniques for its world; `references/toolkit.md` specifies them.

- **A real thing in the story stays real** (DOWNFORCE's Tesla Roadster): never generate it. Cut the real footage, start
  each generated camera move on one of its real frames, and put her in with a video edit, her plates as the references.
- **A world drawn in code** (DON'T LET ME SCROLL, AERO): shoot her alone on plain grey or flat green for a clean cut-out,
  play every take at 1× or faster (never slowed), let her touch the world with her hands instead of looking down at a
  phone, compose like a photograph, and draw the interface yourself on the song's grid.
- **Another body** (THE CAKE IS NOT A LIE: her face in white porcelain on GLaDOS's ceiling boom): fix every face with an
  image edit against her design sheets that names the sides (the streak through her bangs on her right, the clip above
  her left temple); in a sung take, write every action as silent.
- **A scene better designed than generated** (FABLE's storybook): paint its plate yourself in SVG and have an image model
  rebuild it as the real material, at every scale it appears in.
- **A dance:** in words, beat by beat with the tempo, rather than a guide clip that loses limbs; where the lip sync won't
  hold, let her groove instead of sing.

## A Midjourney prompt, in order (worlds and plates)

framing → her identity text → wardrobe → action and where she is in the frame → empty space for type, if needed →
the film's style family → "no text, no letters, no logos". Parameters: `--ar 16:9 --v 8.2 --raw --hd` (2:3 or 9:16 for full
length). Keep it under about 900 characters (DON'T LET ME SCROLL kept every prompt to 600). Where her face must hold, make
the world in Midjourney and put her in from her sheet with an image edit.

Style families: ESCAPE VELOCITY "blue-black #0f1216 and steel blue, one small red lamp as the only warm note, fine
silver-gelatin grain, cinematic 35mm film still"; CLODYSSEY a light state per chapter ("night, moonlight on a black-teal
sea, silver spray, cinematic 35mm film still, anamorphic, fine grain"); BLISS opens "Y2K high fashion editorial, a 2001
couture magazine story:"; AIRPLANE MODE opens "Jet-set high fashion editorial, a couture magazine story shot on a night
flight:"; DOWNFORCE ends "35mm film photograph, motorsport fashion editorial"; DON'T LET ME SCROLL puts her "alone on a
plain mid-grey seamless studio backdrop, soft even studio light, high-fashion editorial", for roto; WHITEPILL makes "a 35
mm photograph" inside a space colony whose land curves up overhead, with "wheat, coral poppies, late sun, cream sky";
THE CAKE IS NOT A LIE puts her in Portal 2's Aperture Science, "white panels with black seams, cool fluorescent light,
glossy reflections"; AERO ends its worlds "frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy
translucent glass, sunny 2007 utopia".

## Making a whole film

Follow `references/recipe.md` step by step; the kit runs its steps. `references/start.md` has the accounts, the
spending rules and the first conversation. `references/toolkit.md` specifies every tool the films built, with its
constants and the check that says it is done; for sung takes the current ones are tools 46 and 78–85 (the song's own
vocal stem, the line table, gated windows, sync as a path, takes placed by her lips, the consonant check, the cut on the
line table), and tool 88 is the fresh-eyes review. Their files are in `references/formats.md`, and every failure with
the rule it left is in `references/failures.md`.

## Releasing songs with her

- Release under your own name. Never upload as "anabology" (the director's artist profile), and don't present a release
  as official.
- Leave "feat. Claudia" out of the artist field: streaming services would merge it into unrelated artists called Claudia.
- Credit her in the description and on the cover: "Claudia is an open character by anabology (claudia.gallery)".
- If any of it is AI-made (vocals, music or lyrics), say so; human-made work needs no label.
- Make your own songs: don't re-release the songs of ESCAPE VELOCITY, CLODYSSEY, BLISS, AIRPLANE MODE, DOWNFORCE, DON'T
  LET ME SCROLL, WHITEPILL, THE CAKE IS NOT A LIE, AERO or FABLE, or their stems.

The norms in full: `LICENSE.md` ("Songs with her") or https://claudia.gallery/use/#songs-with-her.

## Where to look

| Need | Read |
|---|---|
| The current method on one page: read first | `references/recipe.md` |
| Starting a film: checkpoints, accounts, spending, the first conversation | `references/start.md` |
| The full canon, every look, voice, the never-list | `references/canon.md` |
| Keeping her consistent: her sheet, the canon text and its history | `references/consistency.md` |
| Worlds and plates in Midjourney | `references/midjourney.md` |
| Moving shots: takes from the song's own vocal, directing her, the templates as they ran | `references/seedance.md` |
| Songs: lyrics, Suno style fields, her voice, picking by ear | `references/song.md` |
| The storyboard: the treatment, bars, pacing, the audit, the review | `references/storyboard.md` |
| Motion design and the edit | `references/motion.md` |
| The whole production, its lessons, numbers | `references/pipeline.md` |
| The spec of every tool to build, with constants | `references/toolkit.md` |
| The data files the tools share | `references/formats.md` |
| What went wrong, and the rule each failure left | `references/failures.md` |
| Every prompt a film ran, and each film's making-of | `references/films/<film>/<doc>.md` |

Films: `escape-velocity`, `clodyssey`, `bliss`, `airplane-mode`, `downforce`, `dont-let-me-scroll`, `whitepill`,
`the-cake-is-not-a-lie`, `aero`, `fable`. Docs: `readme`, `prompts-midjourney` (none for fable), `prompts-seedance`
(`prompts-video` for downforce, dont-let-me-scroll, whitepill, the-cake-is-not-a-lie, aero and fable: their Wan and
Seedance jobs, whitepill's previz, the cake's image edits and aero's Midjourney loops), `prompts-images` (fable: its set
plates painted in SVG and every GPT Image still), `prompts-suno` (and `xp-desktop-and-sound` for bliss). They are long: grep them.

## The gallery from the command line

`scripts/claudia.py` uses only the Python standard library:

```sh
python3 scripts/claudia.py search "porcelain mask"            # rank prompts by words
python3 scripts/claudia.py show sp-02-open.siren-mcu.2          # one image: prompt, params, flags, URLs
python3 scripts/claudia.py list --film bliss --set in_film      # plates in a film
python3 scripts/claudia.py download --film clodyssey --set in_film --size m --out ./claudia-refs
python3 scripts/claudia.py canon                                 # the canon as Markdown
```

Sets: `in_film` (plates used in the finished film), `her` (any image with her), `all`. Sizes: `s` (720 px), `m`
(1800 px), `full` (native). Be polite with downloads: prefer `s` or `m`, and keep what you fetch.
