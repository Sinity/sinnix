# The recipe

The current method in one page: what makes a Claudia film good, the order of work with the person's checkpoints, the references, how to write a prompt for a model that does exactly what it reads, lip sync from the song's own vocal, the cut and the review. Read this first; every other page goes deeper.


This page is the method as the films make it now (November 2026), in one read. The other guides are the long history of
ten films and every detail behind each step; when they disagree with this page, this page is newer. The tools for each
step are in the [Claudia kit](https://claudia.gallery/kit/), runnable code you can download.

## What makes the films good

1. **A song worth replaying.** An original lyric written for this moment, sung by her, produced in Suno far from stock
   music, and picked from several takes **by a person's ear**. No machine listen picks the song: on FABLE a written
   description of each take chose the worst of fourteen, and the whole film was shot again on its twin.
2. **One idea, legible in a second.** A premise someone gets from one frame, tied to something current, built on who
   she is (an AI who looks like a person, singing about her own situation), and carried by one device through every
   shot: a countdown, a pill, a HUD, a desktop, a storybook.
3. **She performs, on screen, in sync.** She is the singer with a job in the world, on screen for most of the film,
   and her lips match the song because each take is generated from the song's own vocal and placed by measurement.
4. **She reads alive and warm.** She moves: her head turns, she nods, shifts her weight, gestures, steps, looks off and
   back. She is wry in her words, not cold in her face. After FABLE's release, viewers read her as stiff and frozen, and
   as unhappy, even menacing: every take had told her to keep her head upright, and take after take to be dry and
   knowing.
5. **References carry her identity; words carry only what matters.** The video model does exactly what it reads. Get
   the images right, then write precisely only the things that matter (the sung words and their timing, the one key
   action, the camera when it matters) and leave the rest loose.
6. **The picture follows the music.** Cuts on the song's bars, a shot held as long as it has something to show, every
   move with a reason. Recent films: about 7 to 12 shots a minute.
7. **A person decides; fresh eyes check.** The person picks at the checkpoints below; two reviewers who have not seen the
   film read it shot by shot before the person watches. Their notes are proposals: fix the clear errors they find (a
   broken face, stray lettering) and bring the rest to the person with v1. After v1, change only what the person flagged.

## The checkpoints

A person decides at these six points. Silence never approves spending (a waiting window approves the board only if the
person set one).

1. **Concept.** Three pitches of at most 120 words: the premise, the device, the arc, her one sincere line, one risk.
2. **The song, by ear.** "Which take? Or what's wrong?" Send the takes; wait.
3. **Her face and looks.** Her reference sheet, the looks, a first frame or two: "Is this her?"
4. **The board.** The shot list on the song's bars, with first frames. Check it before you show it: the first seconds
   tell part of the story (a hook, not a mood); no two shots in a row from the same camera setup (a new angle or
   framing, or hold); her face in the opening seconds; no stock-looking extras in close-up.
5. **Prompts and cost before any paid take.** "These N takes, about $X at list. Go?"
6. **v1.** "Accept, or what's wrong?" The newest note wins; change only what was flagged.

A note from the person belongs to the film it was about unless they say it is a standing rule. Drop rules that only
patched an older model's limits. Show the person every render as it lands, not only the finals. Use the newest version
of each model family, checked in the provider's catalogue the day you start: the versions named on this page are
November 2026's.

## The order of work

| Step | What | Kit |
|---|---|---|
| 1 | Brief: the first conversation, its answers verbatim | — |
| 2 | Concept: three pitches | — |
| 3 | Lyric: spelled as sung; hooks of 6–7 syllables, spoken verse lines of 10–13; scored for how it sits on the beat | `lyric` |
| 4 | Song: Suno v6-wild with Max Mode; a style that names a concrete, odd pairing (a record that does not exist), not adjectives; 2–3 rounds of takes; the person picks by ear | — |
| 5 | Stems and the song map: Suno's stem split (lead vocal + the rest) of the exact take; the beat and bar map; **the line table**: every sung line's true start and end read off the lead stem's level | `songmap` |
| 6 | References: her face-on sheet; her look for this film; worlds and plates (Midjourney is good at them); a first frame or two of her, to check her face | — |
| 7 | The board and the shot book: shots on the bars, each naming the lines it sings; a first frame for every shot of her, made by an image model from the sheet and the canon text; windows, prompts and jobs; the lint | `shotbook` |
| 8 | Takes: Seedance 2.5, one take per job, re-roll only failures, a spend cap | `run` |
| 9 | Sync: each take's own soundtrack aligned to its window, as a path | `sync` |
| 10 | Cut: takes laid on the song along their paths; the song laid back over; −14 LUFS; the flash check; a 9:16 cut | `cut` |
| 11 | Review: one sheet per shot; two fresh-eyes reviewers; the person watches v1 | `cut sheets` |

## Her references

- **Her face-on reference sheet** goes in as the second image of every take that shows her face, next to the shot's
  own first frame: [her face sheet](https://claudia.gallery/kit/claudia-face-sheet.png) ([JPEG](https://claudia.gallery/kit/claudia-face-sheet.jpg)); for full-length
  shots, [her face and body sheet](https://claudia.gallery/kit/claudia-reference-sheet.png).
  It is one large portrait, face-on and neutral, with her head from every side and a row of expressions beside it. The
  portrait is upright and neutral on purpose: the sheet fixes who she is, not how she moves or feels. It has no microphone; add the
  headset in a prompt only when your look has one.
- **The first frame sets the shot**: her look, the set, the light, the composition and **her mood**. Make it with an
  image model given the sheet and the canon's identity text ([the character](https://claudia.gallery/claudia/)): GPT Image (2.6 Sunburst in
  FABLE, 2.5 in WHITEPILL to AERO). Midjourney is good for the worlds and plates; in the recent films it did not hold her face, so an image
  model put her into its frames from the sheet (the server's `build_prompt` with `model="gpt_image"` writes it the way
  FABLE wrote its stills). For a sung take: her face unblocked, nothing in front of her mouth, lips
  closed or just parted. Make her warm or amused in the first frame if that is what the shot needs; the take follows the
  frame.
- **A last frame** (when a move must land somewhere) is made as an edit of that shot's own first frame, so both share
  one camera. A take that continues another starts on **the previous take's own last frame**, not on a still made for it.
- **Her looks are unmistakably feminine and high fashion**, styled to the film's world: fitted, a skirt or a dress
  where the world allows it, never boxy, bulky or generic workwear. Write "high fashion" into the image prompts. A look
  changes with the story's worlds and never overstays its section. (The director asked for this on five films.)
- **Style her with wardrobe, set and light, never country or ethnicity words** ("K-pop", "Seoul", "K-beauty"): they
  override the canon and changed her face. Describe the clothes, the place and the light instead.
- **Every prop is held or resting**: nothing floats in a still (a sleeve with no arm, an object in mid-air).
- **Check every still at full size**: one clay-orange streak, one star clip, her face; no drawn border, frame line or
  rounded corners (ask for "the picture fills the whole frame edge to edge"); no lettering you did not ask for.

## Writing a prompt for a model that does exactly what it reads

- **Precise where it matters**: the exact words she sings and in which second, the one action that tells the story,
  where people and things are, the camera when it carries the shot.
- **Loose everywhere else.** One plain clause of movement per segment ("she turns to the window and back, a smile in her eyes",
  "she steps toward the camera, hands open"). No list of fixes.
- **No standing posture rules in a performance.** "Head upright, no tilt, faces the camera with her whole body" belongs
  to the reference sheet, not to a take: in every take it freezes her.
- **Choose her emotional words on purpose, warm by default.** Every adjective is obeyed. "Dry", "deadpan", "knowing",
  "smirk", "mock innocence", "eyes on the lens" in take after take add up to a cold stare.
- **No smile on her mouth while she sings.** "Smiling" in a sung take drew a toothy grin; write a smile in her eyes,
  and lips closed until her voice begins.
- **A full stop between two lines she sings straight through becomes a pause in the take.** Use a comma.
- **Nothing appears from nowhere.** Every change in a take (makeup on her face, a prop arriving, a light coming on) is
  a visible action, one step at a time: a hand brings it, she lights it.
- **Say each thing once.** One short audio policy, her identity once, three or four requirements.
- **Don't ask for a look past the lens or behind her**; it turns her head too far. Point with a hand instead.
- Ask the server's `check_prompt` tool, or the kit's `shotbook lint`, before you spend.

## A sung take (Seedance 2.5 with the song's own vocal)

- **@Audio1** is the lead-vocal stem cut to **exactly** the take's length (whole seconds, 4–15), opening on about 0.7 s
  of silence before her first word, with everything outside the shot's own lines silenced (20 ms fades). One or two
  lines per take; two-line takes copy as well as one-line takes.
- **@Image1** is the first frame; **@Image2** her face-on sheet.
- **The prompt**, about 200–400 words, in this order: the audio policy (the soundtrack is @Audio1, copied; no music, no
  other voices); the goal in one sentence; the roles of the references; her identity and look, once; the world in one
  line; the timeline in whole seconds, each sung second with its exact words and one loose action; the camera in one
  line; the requirements: lip sync to @Audio1 word by word, her identity as in the references, natural anatomy and
  hands, no on-screen text. The server's `write_shot` tool writes it from your lines and actions.
- **Generate at 720p** (1080p for close faces if you can), sound on. One take per job.
- **Where, and the cost** (list prices recorded in October 2026): in the films, every take that carried her face sheet
  ran on Higgsfield's API, about $0.46 a second at 720p; takes with no person in them ran on Replicate, about $0.23 a
  second. Plan twice the seconds you need for re-rolls, quote the total, and wait for the yes.

## A cheaper video model that cannot hear the song (Grok Imagine)

The films' lip sync comes from a model that hears the song's vocal (above). A model that cannot is a budget compromise:
the lips land near the words, not on them. Use it knowingly, and keep the sung close-ups for a model that hears the song
if you can afford a few.

Grok Imagine Video 1.5 runs on Replicate at about $0.08 a second (480p or 720p) and on OpenRouter at about $0.14 a
second at 720p ($0.08 at 480p, $0.25 at 1080p; the Lite version about $0.03), against about $0.46 for Seedance 2.5 with
her sheet. It takes **a first frame only**: no reference sheet and no audio. What
changes:

- **Her identity is only the first frame.** Make every first frame of her from her sheet with an image model
  (`build_prompt` with `model="gpt_image"`), and keep takes short (5–8 s): the longer the take, the further her face can
  wander.
- **Lip sync is approximate.** The model never hears the song: write the words she sings in quotes so her mouth moves to
  them, then place each take on the song **by her lips** (the kit's `sync`, lips method), never by the sound the model
  invents. It shows most in close singing shots: favour medium shots where she moves, profiles and cutaways, keep the
  close sung shots few and short, and check each one by eye.
- **The prompt is short prose**, about 80–150 words: the goal, her in the canon's short form "as in the first frame",
  what she does second by second with the sung words in quotes and a smile in her eyes, the camera in one line, her look
  kept as in the first frame, no text on screen. `write_shot` with `model="grok-imagine"` writes it; `check_prompt` with
  the same model checks it.
- **Its habits:** it pushes in when asked to pull back (make the push-in and reverse it), and it redraws a painting or
  garbles lettering during big camera moves.
- `plan_film` with `video_model="grok-imagine"` prices the film this way.

## Sync, the cut, the review

- **Word times come from the stem's level, not from speech recognition.** After a pause a recogniser puts the next word
  up to two seconds early; windows cut on those times lose first words. Use recognition only to label the words.
- **Sync is a path, not an offset.** Seedance keeps each sung phrase at about 1× but shortens or stretches the pauses
  and sometimes sings a line 10–16% slower, so align each take's own soundtrack to its window (dynamic time warping) and
  map song time to take time along that path. A take that came back without sound is placed by her lips: her lips must
  be shut on every b, m and p.
- **Lay the song back over** at a plain gain to about −14 LUFS; the takes' own audio is thrown away.
- **Never show a take's first two frames** (the input still, sharper than what follows); leave a take before it holds
  or freezes; never reuse one image in two shots unless they are one moment.
- **Review**: one sheet per shot (eight frames as shown in the cut) for two reviewers who have not seen the film, then
  the person watches at full speed. Fix by re-shooting with changed words or a better first frame; never patch frames.

## Craft the films kept relearning

Each of these came from a note on one film ([What went wrong](https://claudia.gallery/wiki/failures/) has them with their films); the song and
the concept still decide.

- **Open on a hook** that tells part of the story, not on a mood.
- **A new film, a new sound and a new picture.** The earlier films' looks and sounds are theirs (one was forked so often
  its sound was exhausted); invent this film's for its song.
- **Pace follows the song.** A hype song can cut hard on the beat; a fast song can still be over-cut. Linger when a
  scene has more to show, and put the accents inside the shot: things arriving, building, turning on the beats.
- **Never slow a take down.** Below 1× the motion steps visibly; cut away, add a take, or shoot again.
- **Compose like photography**: a clear subject at a clear scale, thirds, nothing important clipped at the edges, her
  touching the world she is in.
- **Keep the image model's own colour.** Ask before any grade or print texture; new light means new frames with the
  light written into each scene, not a grade over old ones.
- **Flashes only as cuts**, never random strobes; run the flash check and tell the person what fails.
- **No jump cuts inside a scene.** Don't splice two takes of the same setup end to end: cut to a new angle, or hold.
- **The look develops through the film.** An effect that is new in the first chorus is old by the third: escalate it or
  change it.
- **Vast things at their scale, big moments held past their line.** Give the hero object its size in the frame and let a
  big moment breathe a beat after the words.
- **Inserts sit inside a real scene** (a screen, a page, a window in the world), never floating on flat colour.
- **The 9:16 cut keeps the story.** Recrop each shot by hand so the face or prop that carries it stays in, and cut any
  shorter version's audio on bar lines so no word is clipped and no seam is heard.
- **Wry, not cruel.** No roasts or digs at real people, groups or anyone's ideals, in the lyric or the picture.
- **A lyric video is a question, not a default.** When the words are on screen, design them into the picture and let the
  graphics explain what the words say.

## The ten mistakes that cost the most

1. Locking the song by a description instead of a person's ear.
2. Windows cut on recogniser times: first words lost.
3. Placing a take by one offset: lips drift after its first pause.
4. Posture rules and mood words in every take: a frozen, cold performance.
5. Her identity in words only, no sheet: her face drifts on every turn.
6. A first frame with something over her mouth, or her face turned away, for a sung line.
7. A drawn border or lettering in a still, carried into the take.
8. A continuing take started on a separately made still: the camera jumps at the seam.
9. Spending before the person has read the prompts and the cost.
10. Fixing frames in code instead of making a better frame or prompt.

## Where to go deeper

- [Start here](https://claudia.gallery/wiki/start/): the scale to pick, accounts, spending rules, the first conversation.
- [The song](https://claudia.gallery/wiki/song/): lyric craft, Suno styles in words, picking by ear.
- [Keeping her herself](https://claudia.gallery/wiki/consistency/): the canon, looks, her sheet.
- [Seedance](https://claudia.gallery/wiki/seedance/) (read it by section: Lip sync from the song's own vocal; Directing her; the templates).
- [The storyboard](https://claudia.gallery/wiki/storyboard/): the hook, the bar map, pacing.
- [What went wrong](https://claudia.gallery/wiki/failures/): every failure, as what you see, why and the fix.
- The films' own records: every prompt, take and price (`get_record` on the server).


---
From the Claudia wiki: https://claudia.gallery/wiki/recipe/
