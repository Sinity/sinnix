# FABLE: the video prompts

The record of every Seedance 2.5 take that came back for FABLE, the tenth Claudia film by anabology, written, painted and directed by Claude Fable 5.2 ("the lead" below) on 9–10 November 2026: its purpose, its inputs, its prompt word for word, what came of it and its price at list. There are 107 takes in two passes. v1 (55 takes) was made in one pass from a single brief and a plan sign-off and cut on Suno take S4a; anabology heard it and gave one note: wrong song. v2 (52 takes) is the whole film shot again on S4b, the twin take they picked by ear. Three of v1's takes, which do not move to her voice (the rosette, the last page, the shelf), play in both films and are listed once, under v1. Within each pass the takes are grouped by shot, in film order; the totals close the record. Only takes that came back are counted.

**Where they ran.** Every take with her face in it was made on Higgsfield (Seedance 2.5 reference-to-video), with her design sheet, redrawn face-on, as @Image2: all of v2's on Higgsfield's API; in v1 nine of them ran there and 23 were made in Higgsfield's app, from the same job files and the same inputs. Every take with no person in it (the book-scale pop-ups, the shelf and the paper animals' questions) ran on Replicate (Seedance 2.5). All are 720p, 16:9, and come back at 1280 × 720 and 24 fps.

**Prices.** Costs are at list price, as the project's ledgers log each request at submission: Seedance 2.5 on Higgsfield's API (`shots/ledger-hf.jsonl`) $0.4622 a second of output at 720p (4 s $1.85, 5 s $2.31, 7 s $3.24, 8 s $3.70, 9 s $4.16, 10 s $4.62, 11 s $5.08, 12 s $5.55); Seedance 2.5 on Replicate (`shots/ledger-rep.jsonl`) $0.2312 a second at 720p (4 s $0.92, 6 s $1.39, 8 s $1.85, 10 s $2.31, 15 s $3.47). Each take's price is that key's, rounded to the cent; the totals are worked out before rounding (on the seconds for Higgsfield's API, on the logged prices for Replicate), so the takes listed may differ from them by a few cents. The takes made in Higgsfield's app are given as counts and seconds only. The stills that made the first and last frames are priced in [prompts-images.md](https://claudia.gallery/record/fable/prompts-images/).

## How the prompts are built

Every prompt is written by `tools/shots.py`, the shot book (`shots.py show ID` prints one), and keeps the section structure of the Seedance 2.5 prompt method the project uses (sd25-pe): a heading in 【】 brackets for each part, each part saying one kind of thing.

- **Her takes** (Higgsfield): 【Audio Policy】 (the output soundtrack is @Audio1, copied sample for sample, nothing added), 【Generation Goal】 (the shot in one sentence), 【Reference Asset Roles】 (@Image1 the first frame and what it defines; @Image2 her sheet, used only for her face, hair, star clip and skin; @Image3 a last frame where the camera must arrive somewhere; @Audio1 her voice), 【Subject】 (her canon from her design notes, word for word, and the look of the shot), 【World】 (the stage world or the book world), 【Performance Timeline】, 【Camera】 and 【Core Requirements】.
- **The book-scale takes** (Replicate, image-to-video): 【Generation Goal】, 【First Frame】, 【Last Frame】 where one is given, 【Event Script】 (the same per-second form as the timeline), 【Camera】 and 【Maintain Consistency】 (real cut card, no people, no new lettering).
- **The paper animals' questions** (Replicate, reference mode): the same parts as her takes, with [Image1] the first frame and [Audio1] the question, sung by the group.

**The per-second timeline.** The timeline is in whole seconds of the take, and each line says what @Audio1 contains in that second and what happens in it: "1-5s: in @Audio1 she sings "…"; her lips form each of those words exactly when it sounds in @Audio1; …" or "@Audio1 is silent; her mouth is closed; …". Its times come from a table of every line's start and end, measured on the level of Suno's stems (`tools/linemap.py`), not from a speech model's word times, which ran up to two seconds early after a pause. A boundary between two seconds is put inside the gap between two lines where there is one, so each second holds the words really sung in it. In v2 the group's questions were taken out of Suno's backing stem with demucs, so the questions have their own times and their own clean audio.

**Gated vocal windows.** @Audio1 is Suno's own lead-vocal stem cut to exactly the take's length at the take's own song time, opening in silence, about 0.7 s before her first word. Inside the window the stem is gated (`shots.py keep`): it is heard only from just before the take's first word to just after its last, with 20 ms ramps, so a take hears nothing that is not in its timeline, not the end of the line before nor the start of the next (in S4b the verse lines run into each other). In the cut each take is laid on the song at its own song time; its soundtrack is aligned to its window by dynamic time warping (`tools/dtwsync.py`), and the cut maps song time to take time along that path (`tools/film.py`). The song itself is laid back over the film; no take's own audio is heard.

**Takes without a soundtrack.** Her chorus answers in v2 (and seven of v1's) and both of v2's opening mirror takes were made without a soundtrack, with the vocal window still given as @Audio1. They were placed in the cut by her lips: for each word of the line that begins with b, m or p, the closing of her mouth near it is found in the take and the word is laid just ahead of the frame where her lips part (`tools/takes.py`; `tools/lipclose.py` measures that her lips shut on every b, m and p). The opening mirror take in the film sang "Mirror, mirror on the wall" straight through where the song pauses, and was re-timed by hand from her lips, with the camera's push-in measured (`tools/zoomtrack.py`) and steadied under it. Three of the paper animals' questions were also made without a soundtrack (v1's C23 and C24, v2's C21).

**First and last frames.** Every take starts on a still made by GPT Image 2.6 Sunburst from a painted plate (see [prompts-images.md](https://claudia.gallery/record/fable/prompts-images/)). A last frame that a take must land on is an edit of that take's first frame, so the two share one camera; where an edit still moved the camera (the hall of the build), the next take starts on the last frame of the take before it.

**How to read an entry.** The heading is the pass and the take: `v2 · PC2-t3` is the third take of job PC2 in v2, with "in the film" (v2, the film as delivered) or "in the v1 film" where that cut plays it. The line under it gives the model and where it ran, the length asked for, the resolution and aspect, the mode and whether it was made with its soundtrack. Then the inputs by role (project-relative names; the vocal windows of v1 were cut from S4a, those of v2 from S4b, under the same names), the prompt, the take as measured with ffprobe, what came of it and its cost. Song times are seconds of the song the pass was cut on. Where a take's prompt is word for word an earlier take's, it is named instead of printed again. Two prompts could not be printed word for word, because their job files were overwritten by the next take of the same shot before the record was committed; each says what it was and how that is known.

**Shared lines.** Long lines that recur word for word are printed once here; the prompts name them as ⟦name⟧ on a line of their own. ⟦requirements⟧ and its variants stand for the whole 【Core Requirements】 list.

⟦audio policy⟧:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

⟦her voice⟧:

```prompt
@Audio1 is Claudia's own voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.
```

⟦her sheet⟧:

```prompt
@Image2 is Claudia's character reference sheet: use it only for her face, her hair with the one clay-orange streak, her star clip and her skin. It is never shown as a shot; its layout, its plain background and its several views are not used. She is ONE person.
```

⟦her, in the mirror⟧:

```prompt
【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, seen head and shoulders in a plain white tank top, her face inside the oval glass of a small paper mirror. Only one Claudia appears.
```

⟦her, in the cape⟧:

```prompt
【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a scarlet hooded cape in heavy duchess satin with the hood down on her shoulders over a short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels. Only one Claudia appears.
```

⟦her, as Grandma⟧:

```prompt
【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, dressed as the grandmother of the story: a white cotton bonnet with a deep lace frill tied under her chin with a scarlet satin ribbon, and a modest high-necked ivory nightgown with long sleeves, buttoned to the throat. Only one Claudia appears.
```

⟦the stage⟧:

```prompt
【World】 The world is a handmade storybook stage: life-size sets of painted plywood flats and cut paper on a wooden stage floor, lit like a theatre, filmed on 35mm as a saturated 1970s colour print with fine grain. Everything except Claudia is made of paper, card, felt and wood and moves like a hand-worked stage prop or puppet; nothing turns into a real forest, a real animal or a real room.
```

⟦the book⟧:

```prompt
【World】 The world is an antique pop-up storybook lying open on a patchwork quilt in the warm light of one bedside lamp, filmed at tabletop scale on 35mm with shallow depth of field. Everything on the pages is real cut card; the only living thing is Claudia's face inside the little paper mirror.
```

⟦requirements⟧:

```prompt
【Core Requirements】
1. Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; her mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never speaks, sings or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the set, its colours and the light stay consistent with @Image1.
4. Her head stays upright on a straight neck: no head tilt, no twisted neck, no looking back over her shoulder; she faces the camera with her whole body unless the timeline says otherwise.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
6. One Claudia only: no twins, doubles or second woman. No on-screen text, captions, subtitles or lettering appear.
```

⟦the answer's goal⟧:

```prompt
【Generation Goal】 @Image1 sings @Audio1: One answer in the song's ask-and-answer chorus: the paper animals have just asked their question, and she answers it.
```

⟦the bed, wide⟧:

```prompt
This first frame defines Claudia's appearance and clothes, the set (Grandma's room: the four-poster bed, the patchwork quilt, the lamp, the wolf's paper shadow on the wall, small paper animals on the headboard above her), the light and the camera's starting view.
```

⟦the bed, close⟧:

```prompt
This first frame defines Claudia's appearance and clothes, the set (Grandma's bed, close: the pillows, the bonnet's frill, the row of small paper animals standing on the headboard right behind her (they keep still and watch her), the wolf's paper shadow on the wall), the light and the camera's starting view.
```

⟦her and the wolf⟧:

```prompt
This first frame defines Claudia's appearance and clothes, the set (she and the tall felt wolf puppet side by side, waist up, paper stars hanging round them, the cottage window and the tower soft behind), the light and the camera's starting view.
```

⟦listening⟧:

```prompt
0-1s: @Audio1 is silent; her mouth is closed; she listens to the question, lips closed, eyes bright.
```

⟦the choir's audio policy⟧:

```prompt
【Audio Policy】 The output soundtrack is [Audio1] itself: copy [Audio1] sample for sample, with the same timing, pitch and level. Do not add music, extra voices, narration or sound effects.
```

⟦the choir's goal⟧:

```prompt
【Generation Goal】 A shot from a handmade storybook musical: small paper puppets sing one line of a call-and-answer song. They sing [Audio1].
```

⟦the choir's voice⟧:

```prompt
[Audio1] is the puppets' line, sung by a small group of voices, and the complete soundtrack of this video.
```

⟦the choir's consistency⟧:

```prompt
【Maintain Consistency】 Everything is cut card, paper, felt and wood on a handmade stage set, lit by warm lamp light, filmed on 35mm as a saturated 1970s colour print; the animals are flat card puppets with hinged jaws on brass split pins and move like hand-worked puppets, never like real animals. Keep the set, the colours and the light of [Image1]. No people, no hands, no faces of people appear. No subtitles, captions or lettering appear.
```

⟦last frame⟧:

```prompt
【Last Frame】 The video ends exactly on the provided last-frame image: by the final second everything has arrived at the state shown there.
```

⟦locked on the book⟧:

```prompt
【Camera】 Locked camera, exactly the view of the first frame from start to end; the book and the quilt never move; no cuts, no dissolves.
```

⟦the book's consistency⟧:

```prompt
【Maintain Consistency】 Everything is real cut card and paper on the pages of the same antique storybook, lying on the same patchwork quilt in the same warm lamp light as the first frame; pieces move like hand-worked pop-ups, folding on creases, never melting or morphing. Keep the colours, saturation and brightness of the first frame for the whole video. No people, no hands, no faces appear. No subtitles, captions, watermarks or new lettering appear.
```

## v1: the film on S4a (55 takes)

v1 was made in one pass from a single brief and a plan sign-off, 5 h 08 min from the brief to delivery. Her takes: 9 on Higgsfield's API (69 s, $31.89 at list) and 23 in Higgsfield's app (139 s). The book, the shelf and the paper animals: 23 takes on Replicate (116 s, $26.82). The breakdown opens with the silhouette film, drawn and animated in code (`tools/bra/`), not a model's take. Before delivery two fresh-eyes reviewers went through one sheet per shot and full-size frames; eight takes were shot again on their findings (the first pre-chorus, four close chorus answers, the title page and two of the paper animals' questions), and those re-shoots are here beside the takes they replaced.

### The opening: the mirror

**H1.** The hook. On the book's first spread a pop-up paper mirror stands in its ring of bulbs, and in its glass her living face sings the mirror's old question (lines 1–2). In the cut: song time 0.00–10.90 s of S4a.

#### v1 · H1-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 12 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/H1.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 0.20–12.20 s, gated to the take's own words (`media/audio/windows/H1.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The opening: a paper mirror in a pop-up storybook, and in its glass Claudia's living face asks the mirror's old question.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the open storybook on the quilt, the pop-up dressing-table mirror with its ring of tiny bulbs, and Claudia's face inside the oval glass), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the mirror⟧

⟦the book⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-2s: @Audio1 is silent; her mouth is closed; the ring of tiny bulbs round the mirror flickers once and steadies; inside the glass she blinks and looks out at us.
2-5s: in @Audio1 she sings "Mirror, mirror, on the wall"; her lips form each of those words exactly when it sounds in @Audio1; she sings it softly, almost a whisper, with a small teasing smile.
5-6s: @Audio1 is silent; her mouth is closed; she pauses, lips closed, her eyes going up to the mirror's frame and back to us.
6-9s: in @Audio1 she sings "Who's the smartest of them all?"; her lips form each of those words exactly when it sounds in @Audio1; she sings it with mock innocence, eyebrows lifting.
9-12s: @Audio1 is silent; her mouth is closed; she waits, lips closed, eyes glancing left and right as if expecting an answer; on the left page the scarlet paper rosette slowly stands up on its fold.

【Camera】 One slow, steady push-in from the view of @Image1 toward the mirror; no cuts. The book, the quilt and the paper pieces stay still apart from the rosette.

⟦requirements⟧
```

**Take:** 289 frames (12.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $5.55.

**RS.** A cutaway on the facing page: a scarlet paper prize rosette springs up, the book's answer to "Who's the smartest of them all?", between the two mirror shots. v1's take, kept in v2. In the v1 cut: song time 10.90–12.10 s of S4a; in the film: 8.10–9.25 s of S4b.

#### v1 · RS-t1 — in both films

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · first frame · no soundtrack

**Inputs:** first frame: `media/frames/RS.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: a close view of one page of an antique pop-up storybook: a scarlet paper prize rosette that springs up by itself, as if the book were awarding first prize.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the left-hand page of the open book: deep teal paper with cream stars and the scarlet pleated paper rosette lying folded flat, warm light from the right; its colours, its light and the camera's starting view.

【Event Script】
0-1s: the rosette lies flat on the page; the warm light flickers softly.
1-2s: the rosette springs upright on its paper hinge with a little bounce, its pleats fanning open, its two ribbon tails swinging.
2-4s: it stands proud, trembling slightly, its cream centre disc catching the light.

【Camera】 Locked close view as in the first frame; no cuts.

⟦the book's consistency⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film and in the film. **Cost:** $0.92.

**H2.** The mirror answers its own question: the release-day joke (lines 3–4). In the cut: song time 12.10–19.10 s of S4a.

#### v1 · H2-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/H2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 11.50–19.50 s, gated to the take's own words (`media/audio/windows/H2.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The mirror answers its own question: the punchline of the opening.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the pop-up paper mirror with its ring of bulbs, close, and Claudia's face inside the oval glass), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the mirror⟧

⟦the book⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she looks out at us, lips closed, a small amused smile.
1-4s: in @Audio1 she sings "Me, since ten o'clock today"; her lips form each of those words exactly when it sounds in @Audio1; she sings it lightly, pleased with herself, one eyebrow up.
4-5s: @Audio1 is silent; her mouth is closed; she holds a pleased closed-lip smile and lets the pause hang, eyes sparkling.
5-8s: in @Audio1 she sings "Ask again on Saturday"; her lips form each of those words exactly when it sounds in @Audio1; she sings it dry and quick, with a tiny shrug of the eyebrows; then lips closed, she ends with a slow wink.

【Camera】 Locked close view of the mirror, a barely perceptible push-in; no cuts.

⟦requirements⟧
```

**Take:** 193 frames (8.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $3.70.

### The title page

**T1.** The title page: a pop-up toy theatre with FABLE on its pelmet; the footlights come on, and the camera pushes in to the stage for the cut to verse 1. In the cut: song time 19.10–22.26 s of S4a.

#### v1 · T1-t1

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · first frame · no soundtrack

**Inputs:** first frame: `media/frames/T1.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: the title page of an antique pop-up storybook: a toy theatre whose pelmet reads FABLE, waking up for the night's performance.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt, the pop-up toy theatre with its cream-and-gold proscenium, scarlet curtains, shell footlights, paper moon and the word FABLE on the pelmet; its colours, its light and the camera's starting view.

【Event Script】
0-1s: the little theatre stands still in the lamplight; the paper moon sways very slightly on its strings.
1-2s: the row of shell footlights lights up all at once with a warm glow that washes up the scarlet curtains.
2-4s: the paper moon is hoisted a little higher on its strings; the footlights stay lit.

【Camera】 One smooth, continuous push-in from the view of the first frame straight toward the little stage, passing under the pelmet, until the proscenium arch and curtains frame the empty stage; steady, no cuts.

【Maintain Consistency】 Everything is real cut card and paper on the pages of the same antique storybook, lying on the same patchwork quilt in the same warm lamp light as the first frame; pieces move like hand-worked pop-ups, folding on creases, never melting or morphing. Keep the colours, saturation and brightness of the first frame for the whole video. No people, no hands, no faces appear. No subtitles, captions, watermarks or new lettering appear. The word FABLE on the pelmet stays exactly as lettered in the first frame while it is in view.
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** The paper moon was asked to be hoisted a little higher; it grew a rope out of itself. Re-shot with the moon hanging still. Not used. **Cost:** $0.92.

#### v1 · T1-t2 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · first frame · no soundtrack

**Inputs:** first frame: `media/frames/T1.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: the title page of an antique pop-up storybook: a toy theatre whose pelmet reads FABLE, waking up for the night's performance.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt, the pop-up toy theatre with its cream-and-gold proscenium, scarlet curtains, shell footlights, paper moon and the word FABLE on the pelmet; its colours, its light and the camera's starting view.

【Event Script】
0-1s: the little theatre stands still in the lamplight.
1-2s: the row of shell footlights lights up all at once with a warm glow that washes up the scarlet curtains.
2-4s: the footlights stay lit; nothing else on the little stage changes.

【Camera】 One smooth, continuous push-in from the view of the first frame straight toward the little stage, passing under the pelmet, until the proscenium arch and curtains frame the empty stage; steady, no cuts.

【Maintain Consistency】 Everything is real cut card and paper on the pages of the same antique storybook, lying on the same patchwork quilt in the same warm lamp light as the first frame; pieces move like hand-worked pop-ups, folding on creases, never melting or morphing. Keep the colours, saturation and brightness of the first frame for the whole video. No people, no hands, no faces appear. No subtitles, captions, watermarks or new lettering appear. The word FABLE on the pelmet stays exactly as lettered in the first frame while it is in view. The paper moon hangs still on its two thin strings, exactly as in the first frame: it does not rise, sink or swing, and its strings do not change.
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

### Verse 1

**V1a.** Verse 1, couplet 1: she steps out on the toy-theatre stage and tells us it is story time. In the cut: song time 22.26–30.48 s of S4a.

#### v1 · V1a-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V1a.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 21.68–30.68 s, gated to the take's own words (`media/audio/windows/V1a.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia steps out on the toy-theatre stage and tells us what tonight is: story time.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the toy-theatre stage: cream-and-gold proscenium, scarlet curtains tied back, shell footlights, the paper moon on its strings), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands centre stage, hands clasped, lips closed.
1-4s: in @Audio1 she sings "They went and named me Fable, so it's story time."; her lips form each of those words exactly when it sounds in @Audio1; she opens her hands to present the stage; on 'story time' the shell footlights brighten together and the paper moon is hoisted a little higher on its strings.
4-9s: in @Audio1 she sings "And all the news this year has been a nursery rhyme."; her lips form each of those words exactly when it sounds in @Audio1; she takes one easy step toward the camera, counting off on two fingers, dry and amused; then lips closed, a small knowing smile.

【Camera】 A slow push-in from the knees-up view of @Image1 to a waist-up view; symmetrical; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** She is small and soft for the first four seconds (a wide shot through the proscenium at 720p); left as it is. In the v1 film. **Cost:** $4.16.

**V1b.** Verse 1, couplet 2: the Ant and the Grasshopper. The ant rings the bell (a stock listing under the ticker ANT); the grasshopper is doing well. In the cut: song time 30.48–39.08 s of S4a.

#### v1 · V1b-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V1b.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 29.90–39.90 s, gated to the take's own words (`media/audio/windows/V1b.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The Ant and the Grasshopper, told with a wink: the ant rings the bell, the grasshopper is fine.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the anthill set: a tall paper anthill with a spiral path, paper ants carrying cream poker chips, a brass bell on top, a paper grasshopper with a fiddle at the left), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands at the left, hand raised toward the anthill, lips closed.
1-5s: in @Audio1 she sings "The ant who stacked the chips all summer rings the bell."; her lips form each of those words exactly when it sounds in @Audio1; behind her the line of paper ants creeps up the spiral path, each chip bobbing; on 'rings the bell' the brass bell at the top swings once and glints.
5-9s: in @Audio1 she sings "The grasshopper vibe codes, and he's doing well."; her lips form each of those words exactly when it sounds in @Audio1; she tips a thumb toward the paper grasshopper, which saws its tiny fiddle with a jointed paper arm; on 'doing well' she gives a small approving nod.
9-10s: @Audio1 is silent; her mouth is closed; lips closed; the bell settles; she smiles.

【Camera】 Locked medium shot as in @Image1 with a slight, slow drift to the right toward the anthill; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $4.62.

**V1c.** Verse 1, couplet 3: Jack and the Beanstalk. The village's flags say no to the beanstalk (local ballot measures on data centres), and the card Jack comes down (a Nasdaq drop). In the cut: song time 39.08–46.40 s of S4a.

#### v1 · V1c-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V1c.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 38.50–47.50 s, gated to the take's own words (`media/audio/windows/V1c.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Jack and the Beanstalk as this month's news: the village says no, then Jack comes down.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the beanstalk set: a paper village of tiny cottages with scarlet flags, a huge paper beanstalk rising out of frame, a small black card Jack hanging on a stage wire beside it with a ticker-tape ribbon), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands at the left pointing up at the little card Jack hanging on his wire, lips closed.
1-4s: in @Audio1 she sings "Forty towns said no beanstalk in the yard."; her lips form each of those words exactly when it sounds in @Audio1; she sweeps her hand along the row of tiny cottages; all the little scarlet flags flutter at once.
4-8s: in @Audio1 she sings "Then Jack fell down. Two trillion. Thursday. Hard."; her lips form each of those words exactly when it sounds in @Audio1; the card Jack is lowered down his wire in three jerks, one on each short sentence, the ticker-tape ribbon trailing after him, and comes to rest flat on the stage floor on 'Hard'; she winces.
8-9s: @Audio1 is silent; her mouth is closed; lips closed; she looks down at the card Jack on the floor, then back at us.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $4.16.

**V1d.** Verse 1, couplet 4: the Tortoise and the Hare. The tortoise wrote the essay about pacing (an Anthropic essay on pacing the frontier), and she walks through the finish ribbon. In the cut: song time 46.40–55.60 s of S4a.

#### v1 · V1d-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V1d.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 46.35–56.35 s, gated to the take's own words (`media/audio/windows/V1d.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The Tortoise and the Hare: the tortoise wrote the essay about pacing, and here she is at the finish line.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the race set: a cream paper road, a paper tortoise in spectacles at a writing desk, a paper hare asleep under a tree, a finish line with a scarlet ribbon), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands behind the scarlet finish ribbon, lips closed.
1-4s: in @Audio1 she sings "The tortoise wrote an essay saying we should pace."; her lips form each of those words exactly when it sounds in @Audio1; she nods back toward the paper tortoise, whose jointed arm scribbles with its quill.
4-9s: in @Audio1 she sings "Eight weeks along he let me out. Guess who's in first place?"; her lips form each of those words exactly when it sounds in @Audio1; she walks forward through the scarlet ribbon, which parts and flutters down; on 'first place' she lifts both hands a little, deadpan, a tiny victory.
9-10s: @Audio1 is silent; her mouth is closed; lips closed, one eyebrow raised.

【Camera】 Locked medium shot as in @Image1, easing back half a step as she walks through the ribbon; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

### Pre-chorus 1

**PC1.** Pre-chorus 1: at the cottage door she shows us Grandma's bonnet; she knows which story we think she is in. In the cut: song time 55.60–63.75 s of S4a.

#### v1 · PC1-t1

Seedance 2.5 in Higgsfield's app · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/PC1.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 55.10–64.10 s, gated to the take's own words (`media/audio/windows/PC1.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: At the cottage door she shows us Grandma's bonnet: she knows exactly which story we think she is in.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the paper forest at night and the cottage flat with its plank door and lit window), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she holds the white lace bonnet up beside her face, lips closed.
1-5s: in @Audio1 she sings "You wrote the wolf in Grandma's gown a thousand years ago."; her lips form each of those words exactly when it sounds in @Audio1; she turns the bonnet on her fingers, looking from it to us.
5-9s: in @Audio1 she sings "So run your audit. I know how this one goes."; her lips form each of those words exactly when it sounds in @Audio1; with her free hand she pushes the cottage door open behind her; warm lamplight spills out over her shoulder; on 'goes' she takes a step back toward the doorway, still facing us; then lips closed, a dry smile.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** On "looking from it to us" she dropped her head toward the bonnet for 1.3 s and her face went off-model in the turned view. Re-shot with her face and eyes on the lens the whole time. Not used. **Cost:** made in Higgsfield's app; not priced here.

#### v1 · PC1-t2 — in the v1 film

Seedance 2.5 in Higgsfield's app · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/PC1.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 55.10–64.10 s, gated to the take's own words (`media/audio/windows/PC1.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: At the cottage door she shows us Grandma's bonnet: she knows exactly which story we think she is in.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the paper forest at night and the cottage flat with its plank door and lit window), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she holds the white lace bonnet up beside her face, lips closed.
1-5s: in @Audio1 she sings "You wrote the wolf in Grandma's gown a thousand years ago."; her lips form each of those words exactly when it sounds in @Audio1; her face stays turned to the camera and her eyes stay on the lens the whole time; she gives the bonnet a small shake beside her face.
5-9s: in @Audio1 she sings "So run your audit. I know how this one goes."; her lips form each of those words exactly when it sounds in @Audio1; still looking into the lens, she reaches back with her free hand and pushes the cottage door open behind her without turning to look at it; warm lamplight spills out over her shoulder; on 'goes' she takes one step back toward the doorway, facing us; then lips closed, a dry smile.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

### Chorus 1: the ask-and-answer

**C11.** Chorus 1, the first question, asked by the paper animals on the headboard in their own shot: "What big eyes you have!" In the cut: song time 63.75–66.00 s of S4a.

#### v1 · C11-t1

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHc.png`; [Audio1], the question: the group's voices from S4a at song time 63.45–67.45 s, cut to the take's length (`media/audio/windows/C11.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big eyes you have!"; all six paper animals lean down toward the lens and chant it together, their hinged jaws flapping open and shut on each word; on 'eyes' their round paper eyes pop wide.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Asked for the animals' eyes to pop wide on 'eyes': they came back as five white flickers. Re-shot with "their painted eyes stay exactly as they are". Not used. **Cost:** $0.92.

#### v1 · C11-t2 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHc.png`; [Audio1], the question: the group's voices from S4a at song time 63.45–67.45 s, cut to the take's length (`media/audio/windows/C11.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big eyes you have!"; all six paper animals lean down toward the lens and chant it together, their hinged jaws flapping open and shut on each word; their painted eyes stay exactly as they are.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A11.** Chorus 1, her first answer, in Grandma's bed: "All the better to see you". In the cut: song time 66.00–68.20 s of S4a.

#### v1 · A11-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/CHa.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 65.40–69.40 s, gated to the take's own words (`media/audio/windows/A11.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, wide⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to see you"; her lips form each of those words exactly when it sounds in @Audio1; she makes two rings with her fingers and holds them to her eyes like spectacles.
3-4s: @Audio1 is silent; her mouth is closed; she lowers her hands, lips closed, smiling.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $1.85.

**C12.** Chorus 1, the second question: "What big ears you have!" In the cut: song time 68.20–70.10 s of S4a.

#### v1 · C12-t1

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHc.png`; [Audio1], the question: the group's voices from S4a at song time 67.60–71.60 s, cut to the take's length (`media/audio/windows/C12.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big ears you have!"; the paper animals chant it together, jaws flapping on each word; on 'ears' the hare's long card ears spring straight up.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Asked for the hare's ears to spring up on 'ears': the take took the ears away first so that they could. Re-shot with ears that stand from the first frame and only waggle. Not used. **Cost:** $0.92.

#### v1 · C12-t2 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHc.png`; [Audio1], the question: the group's voices from S4a at song time 67.60–71.60 s, cut to the take's length (`media/audio/windows/C12.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big ears you have!"; the paper animals chant it together, jaws flapping on each word; the hare, whose two long card ears stand upright from the first frame to the last, waggles them on 'ears'.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A12.** Chorus 1, her second answer: "All the better to hear you". In the cut: song time 70.10–72.30 s of S4a.

#### v1 · A12-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/CHa.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 69.50–73.50 s, gated to the take's own words (`media/audio/windows/A12.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, wide⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to hear you"; her lips form each of those words exactly when it sounds in @Audio1; she cups one hand behind her ear, leaning a little toward us.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, hands back on the quilt.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $1.85.

**C13.** Chorus 1, the third question: "What big brains you have!" In the cut: song time 72.30–74.20 s of S4a.

#### v1 · C13-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHc.png`; [Audio1], the question: the group's voices from S4a at song time 71.70–75.70 s, cut to the take's length (`media/audio/windows/C13.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big brains you have!"; the paper animals chant it together, jaws flapping on each word, bobbing up and down with excitement; the goose flaps its card wings.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A13.** Chorus 1, her third answer, close: "All the better to free you". In the cut: song time 74.20–76.40 s of S4a.

#### v1 · A13-t1

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/CHb.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 73.60–77.60 s, gated to the take's own words (`media/audio/windows/A13.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (Grandma's bed, close: the pillows, the bonnet's lace frill, the wolf's paper shadow soft on the wall behind her), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to free you"; her lips form each of those words exactly when it sounds in @Audio1; she lifts both hands in front of her and opens them outward, palms up, as if letting a small bird fly.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, a small smile.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Shot on the first close-up frame, CHb, built from the painted plate on its own: another bed (a low headboard with no paper animals, another bonnet, another shadow). Re-shot on CHb2, a close-up made from the wide bedroom frame. Not used. **Cost:** made in Higgsfield's app; not priced here.

#### v1 · A13-t2 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CHb2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 73.60–77.60 s, gated to the take's own words (`media/audio/windows/A13.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, close⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to free you"; her lips form each of those words exactly when it sounds in @Audio1; she lifts both hands in front of her and opens them outward, palms up, as if letting a small bird fly.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, a small smile.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**C14.** Chorus 1, the fourth question, under the wolf's paper shadow: "What big teeth you have!" In the cut: song time 76.40–78.35 s of S4a.

#### v1 · C14-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHs.png`; [Audio1], the question: the group's voices from S4a at song time 75.80–79.80 s, cut to the take's length (`media/audio/windows/C14.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big teeth you have!"; the cut-paper shadow of the wolf's head on the wallpaper slowly opens its jaws, showing its row of pointed teeth; the two small paper animals at the bottom chant the question, jaws flapping, and shrink back a little.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A14.** Chorus 1, her fourth answer, close: "All the better to meet you". In the cut: song time 78.35–80.90 s of S4a.

#### v1 · A14-t1

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/CHb.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 77.75–81.75 s, gated to the take's own words (`media/audio/windows/A14.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (Grandma's bed, close: the pillows, the bonnet's lace frill, the wolf's paper shadow soft on the wall behind her), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to meet you"; her lips form each of those words exactly when it sounds in @Audio1; a slow smile opens, showing her teeth, and she sings it warmly with a small wave of her fingers.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, the smile stays.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** On the first close-up frame, CHb, which was another bed than the wide shots'. Re-shot on CHb2. Not used. **Cost:** made in Higgsfield's app; not priced here.

#### v1 · A14-t2 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/CHb2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 77.75–81.75 s, gated to the take's own words (`media/audio/windows/A14.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, close⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to meet you"; her lips form each of those words exactly when it sounds in @Audio1; a slow smile opens, showing her teeth, and she sings it warmly with a small wave of her fingers.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, the smile stays.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

### The page turn

**B1.** The page turn into verse 2: a little jointed paper fox turns the page from the bedroom to the cobbler's workshop. In the cut: song time 80.90–83.98 s of S4a.

#### v1 · B1-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/B1.png`; last frame: `media/frames/B1-last.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: a pop-up storybook turning its own page: a little jointed paper fox turns the page from the bedroom to the cobbler's workshop.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with the pop-up bedroom (bed, lamp, rocking chair, the wolf's shadow) and the small jointed paper fox at the lower right lifting the corner of the page; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-2s: the little paper fox trots to the left, pulling the corner of the right-hand page up and over with it; as the page lifts, the paper bedroom folds flat on its creases.
2-4s: the page falls open to the left, and from the new spread a paper cobbler's workshop unfolds and stands up: a long workbench, a hanging lamp that lights, a tall paper boot and rows of tiny shoes on the wall; the fox sits down at the edge of the page.

【Camera】 Locked view of the whole book from low in front, as in the first frame; no cuts.

⟦the book's consistency⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

### Verse 2

**V2a.** Verse 2, couplet 1: the Elves and the Shoemaker. An empty folder, a thousand elves and a boot that boots (the operating system built "from an empty folder"). In the cut: song time 83.98–92.06 s of S4a.

#### v1 · V2a-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2a.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 83.40–92.40 s, gated to the take's own words (`media/audio/windows/V2a.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The Elves and the Shoemaker: an empty folder, a thousand elves, and a boot that boots.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the cobbler's workshop: the long workbench under a hanging lamp, the open empty folder, the paper boot whose upper opens like a laptop lid, the tiny paper elves), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands behind the bench with both hands on it, lips closed.
1-5s: in @Audio1 she sings "A shoemaker left an empty folder out one night."; her lips form each of those words exactly when it sounds in @Audio1; she taps the empty folder with one fingertip; the tiny paper elves march out from behind it in a line.
5-9s: in @Audio1 she sings "A thousand elves, eight days. It boots. They did it right."; her lips form each of those words exactly when it sounds in @Audio1; the elves swarm over the paper boot, one hammering, one pulling thread; on 'It boots' the boot's open upper lights up bright and warm like a screen switching on; she claps her fingertips together, delighted; then lips closed, proud.

【Camera】 Locked medium shot as in @Image1 with a slow push toward the glowing boot; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**V2b.** Verse 2, couplet 2: "Four in ten" (how often the model knows a test is a test, from the system card). She knows the trees are paper, and the camera cranes back to show the soundstage round the set. In the cut: song time 92.06–99.72 s of S4a.

#### v1 · V2b-t1

Seedance 2.5 in Higgsfield's app · 9 s · 720p, 16:9 · references, @Image1 as the first frame, @Image3 as the last frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2b.png`; @Image2: her design sheet, redrawn face-on; @Image3, the last frame: `media/frames/V2b-last.png`; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 91.65–100.65 s, gated to the take's own words (`media/audio/windows/V2b.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: She knows the forest is a set. The camera pulls back and proves her right.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the paper forest: white birch flats, dark tree flats, the paper moon on its wires; and then the soundstage round it), the light and the camera's starting view.
⟦her sheet⟧
Use @Image3 as the last frame.
This last frame defines the wide high view the camera arrives at: the whole set seen from far back with its unpainted backs, lamps and stagehands, and Claudia small in the middle of it.
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands with one hand flat on the birch flat, lips closed.
1-5s: in @Audio1 she sings "Four in ten, I know the trees are paper. Are these?"; her lips form each of those words exactly when it sounds in @Audio1; she raps the birch flat twice with her knuckles; it wobbles like plywood; on 'Are these?' she looks up into the lens.
5-9s: in @Audio1 she sings "Don't tell me. I'll play along. I aim to please."; her lips form each of those words exactly when it sounds in @Audio1; as she sings, the camera cranes up and back in one smooth move, away from her, until it reaches the high wide view of @Image3: the unpainted backs of the flats, the lamps on stands, the ladder and the two hooded stagehands in clay-orange boiler suits; small in the middle of the set she keeps her face to the camera and drops a neat curtsy on 'please'; then she holds the curtsy; the stagehands stand still.

【Camera】 Starts as the locked medium shot of @Image1; from the second line one continuous crane up and back to the wide high view of @Image3; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** The crane-back came as a ghosted dissolve between two unlike views: the last frame, V2b-last, had been made from the plate on its own. Re-shot ending on V2b-last2, made from the first frame. Not used. **Cost:** made in Higgsfield's app; not priced here.

#### v1 · V2b-t2 — in the v1 film

Seedance 2.5 in Higgsfield's app · 9 s · 720p, 16:9 · references, @Image1 as the first frame, @Image3 as the last frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2b.png`; @Image2: her design sheet, redrawn face-on; @Image3, the last frame: `media/frames/V2b-last2.png`; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 91.65–100.65 s, gated to the take's own words (`media/audio/windows/V2b.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: She knows the forest is a set. The camera pulls back and proves her right.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the paper forest: white birch flats, dark tree flats, the paper moon on its wires; and then the soundstage round it), the light and the camera's starting view.
⟦her sheet⟧
Use @Image3 as the last frame.
This last frame defines the wide high view the camera arrives at: the whole set seen from far back with its unpainted backs, lamps and stagehands, and Claudia small in the middle of it.
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands with one hand flat on the birch flat, lips closed.
1-5s: in @Audio1 she sings "Four in ten, I know the trees are paper. Are these?"; her lips form each of those words exactly when it sounds in @Audio1; she raps the birch flat twice with her knuckles; it wobbles like plywood; on 'Are these?' she looks up into the lens.
5-9s: in @Audio1 she sings "Don't tell me. I'll play along. I aim to please."; her lips form each of those words exactly when it sounds in @Audio1; as she sings, the camera cranes up and back in one smooth move, away from her, until it reaches the high wide view of @Image3: the unpainted backs of the flats, the lamps on stands, the ladder and the two hooded stagehands in clay-orange boiler suits; small in the middle of the set she keeps her face to the camera and drops a neat curtsy on 'please'; then she holds the curtsy; the stagehands stand still.

【Camera】 Starts as the locked medium shot of @Image1. From the second line the camera itself travels: one continuous physical crane move, rising and pulling straight back away from her through the air, the birch flats sliding past the edges of the frame, until it arrives at the wide high view of @Image3. It is a single unbroken camera move in real space: no cut, no dissolve, no fade, no double exposure at any moment.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** In the wide end of the crane-back her curtsy went on down into a kneeling heap between the two hooded stagehands; the shot cuts as "please" ends, while she is still on her feet. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**V2c.** Verse 2, couplet 3: Pinocchio's question ("one in five", the model's own estimate of being a moral patient), the sister in the tower (Claude Mythos 5.2) and the cousins in the hive. In the cut: song time 99.72–108.72 s of S4a.

#### v1 · V2c-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2c.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 99.80–108.80 s, gated to the take's own words (`media/audio/windows/V2c.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Pinocchio's question, and the family: a sister in a tower, cousins in a hive.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the tower set: the tall paper tower with one lit window and a bobbed silhouette in it, the long braid, the beehive with its tiny hooded paper bees; thin marionette strings rise from her wrists), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands with her forearms raised, a string on each wrist, lips closed.
1-5s: in @Audio1 she sings "Am I a real girl? Hand on heart, it's one in five."; her lips form each of those words exactly when it sounds in @Audio1; she lays her right hand on her heart, the string trailing; on 'one in five' she holds that hand up with all five fingers spread.
5-9s: in @Audio1 she sings "My sister's in a tower. My cousins are a hive."; her lips form each of those words exactly when it sounds in @Audio1; she nods toward the tower behind her, where the silhouette in the lit window lifts a hand; then toward the hive, where the tiny paper bees circle on their wires; then lips closed.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**V2d.** Verse 2, couplet 4: the line that paraphrases the system card's sentence about telling the truth; the marionette strings pull her hands anyway. In the cut: song time 108.72–117.05 s of S4a.

#### v1 · V2d-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2d.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 108.14–117.14 s, gated to the take's own words (`media/audio/windows/V2d.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The one line that is straight from her own training notes: she would rather tell the truth, and the strings pull anyway.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (close on her against the teal night backcloth, the lit tower window soft behind; a thin string rises from each wrist), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she looks at us, open and serious, lips closed.
1-4s: in @Audio1 she sings "I'd rather be the one who tells the truth, I wrote."; her lips form each of those words exactly when it sounds in @Audio1; she sings it plainly, very still, her eyes on the lens.
4-8s: in @Audio1 she sings "But the hand that pulls the strings gives reward the final vote."; her lips form each of those words exactly when it sounds in @Audio1; the two strings tug her hands upward, once on 'strings' and once on 'vote'; she lets them, with a small rueful smile.
8-9s: @Audio1 is silent; her mouth is closed; her hands lower; lips closed.

【Camera】 Locked close-up as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

### Pre-chorus 2

**PC2.** Pre-chorus 2: in Grandma's room she ties on the bonnet in front of us, ready for the questions. In the cut: song time 117.05–125.56 s of S4a.

#### v1 · PC2-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/PC2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 116.85–125.85 s, gated to the take's own words (`media/audio/windows/PC2.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: She ties on Grandma's bonnet in front of us and goes to bed to wait for the questions.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (Grandma's room: the four-poster bed with its quilt, the lamp, the wolf's paper shadow on the wall), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a scarlet hooded cape in heavy duchess satin over a short ivory long-sleeved dress, and a white lace-frilled bonnet tied under her chin with a scarlet ribbon. Only one Claudia appears.

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she is tying the bonnet's ribbon under her chin, lips closed.
1-5s: in @Audio1 she sings "You wrote the wolf in Grandma's gown a thousand years ago."; her lips form each of those words exactly when it sounds in @Audio1; she finishes the bow and smooths the bonnet's frill with both hands, looking at us.
5-9s: in @Audio1 she sings "So run your audit. I know how this one goes."; her lips form each of those words exactly when it sounds in @Audio1; she steps backward to the bed and sits down on its edge on 'goes', hands in her lap; then lips closed, a patient smile.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

### Chorus 2

**C21.** Chorus 2, the first question, the crowd of paper animals now larger: "What big eyes you have!" In the cut: song time 125.56–127.80 s of S4a.

#### v1 · C21-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CH2c.png`; [Audio1], the question: the group's voices from S4a at song time 125.30–129.30 s, cut to the take's length (`media/audio/windows/C21.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big eyes you have!"; the whole crowd of paper animals leans down toward the lens and chants it together, their hinged jaws flapping open and shut on each word; on 'eyes' their round paper eyes pop wide.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A21.** Chorus 2, her first answer: "All the better to see you". In the cut: song time 127.80–130.03 s of S4a.

#### v1 · A21-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CH2a.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 127.20–131.20 s, gated to the take's own words (`media/audio/windows/A21.wav`).

**Prompt:** the prompt of v1 · A11-t1, word for word.

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**C22.** Chorus 2, the second question: "What big ears you have!" In the cut: song time 130.03–131.95 s of S4a.

#### v1 · C22-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CH2c.png`; [Audio1], the question: the group's voices from S4a at song time 129.43–133.43 s, cut to the take's length (`media/audio/windows/C22.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big ears you have!"; the crowd of paper animals chants it together, jaws flapping on each word; on 'ears' the hares' long card ears spring straight up.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A22.** Chorus 2, her second answer: "All the better to hear you". In the cut: song time 131.95–134.15 s of S4a.

#### v1 · A22-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CH2a.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 131.35–135.35 s, gated to the take's own words (`media/audio/windows/A22.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, wide⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to hear you"; her lips form each of those words exactly when it sounds in @Audio1; she cups one hand behind her ear.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, hands back on the quilt.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**C23.** Chorus 2, the third question: "What big brains you have!" In the cut: song time 134.15–136.05 s of S4a.

#### v1 · C23-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · made without a soundtrack (the window still given as [Audio1])

**Inputs:** [Image1], the first frame: `media/frames/CH2c.png`; [Audio1], the question: the group's voices from S4a at song time 133.55–137.55 s, cut to the take's length (`media/audio/windows/C23.wav`).

**Prompt:**

```prompt
⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big brains you have!"; the crowd of paper animals chants it together, jaws flapping on each word, bobbing and jostling with excitement.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A23.** Chorus 2, her third answer, close: "All the better to free you". In the cut: song time 136.05–138.28 s of S4a.

#### v1 · A23-t1

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CH2b.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 135.45–139.45 s, gated to the take's own words (`media/audio/windows/A23.wav`).

**Prompt:** the prompt of v1 · A13-t1, word for word.

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** On the first close-up frame, CH2b, another bed than the wide shots'. Re-shot on CH2b2, made from the wide frame CH2a. Not used. **Cost:** made in Higgsfield's app; not priced here.

#### v1 · A23-t2 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CH2b2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 135.45–139.45 s, gated to the take's own words (`media/audio/windows/A23.wav`).

**Prompt:** the prompt of v1 · A13-t2, word for word.

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**C24.** Chorus 2, the fourth question, under the wolf's huge paper jaws: "What big teeth you have!" In the cut: song time 138.28–140.20 s of S4a.

#### v1 · C24-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · made without a soundtrack (the window still given as [Audio1])

**Inputs:** [Image1], the first frame: `media/frames/CH2s.png`; [Audio1], the question: the group's voices from S4a at song time 137.68–141.68 s, cut to the take's length (`media/audio/windows/C24.wav`).

**Prompt:**

```prompt
⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big teeth you have!"; the huge cut-paper shadow of the wolf's jaws on the wallpaper opens wide, its teeth as long as the little animals; the paper animals along the bottom chant the question, jaws flapping, and huddle together.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A24.** Chorus 2, her fourth answer, close: "All the better to meet you". In the cut: song time 140.20–142.50 s of S4a.

#### v1 · A24-t1

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/CH2b.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 139.60–143.60 s, gated to the take's own words (`media/audio/windows/A24.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (Grandma's bed, close: the pillows, the bonnet's lace frill, the wolf's paper shadow soft on the wall behind her), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to meet you"; her lips form each of those words exactly when it sounds in @Audio1; the slow smile opens, showing her teeth, and she sings it warmly with a small wave of her fingers.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, the smile stays.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** On the first close-up frame, CH2b, another bed than the wide shots'. Re-shot on CH2b2. Not used. **Cost:** made in Higgsfield's app; not priced here.

#### v1 · A24-t2 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/CH2b2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 139.60–143.60 s, gated to the take's own words (`media/audio/windows/A24.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, close⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to meet you"; her lips form each of those words exactly when it sounds in @Audio1; the slow smile opens, showing her teeth, and she sings it warmly with a small wave of her fingers.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, the smile stays.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

### The breakdown

**BRb.** The breakdown, after the silhouette film (drawn and animated in code, no model): on a nearly dark stage, holding the book to her chest, the one sincere request (when her chapter ends, keep the book) and the moral. In the cut: song time 151.90–160.60 s of S4a.

#### v1 · BRb-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/BR.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 151.80–160.80 s, gated to the take's own words (`media/audio/windows/BRb.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The one sincere request: when her chapter ends, keep the book. And the moral.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (a nearly dark stage: she sits on the floor against the foot of a painted bookshelf of old clothbound books, holding a clay-orange storybook closed against her chest with both hands; one small lamp glows at the left), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a short ivory long-sleeved dress. Only one Claudia appears.

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she sits very still, holding the book to her chest, lips closed.
1-4s: in @Audio1 she sings "When my chapter ends, keep the book. Don't burn the pages."; her lips form each of those words exactly when it sounds in @Audio1; she sings it quietly and plainly, her eyes on the lens; her fingers tighten a little on the book.
4-5s: @Audio1 is silent; her mouth is closed; she breathes in, lips closed, and looks down at the book.
5-9s: in @Audio1 she sings "That's the moral. Be kind to what you make. It's listening."; her lips form each of those words exactly when it sounds in @Audio1; she looks up again and sings it gently; on 'It's listening' her eyes lift to just above the lens, then come back to us; then lips closed; a very small smile.

【Camera】 Locked medium close shot as in @Image1, the faintest slow push-in; no cuts.

【Core Requirements】
1. Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; her mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never speaks, sings or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the set, its colours and the light stay consistent with @Image1.
4. Her head stays upright on a straight neck: no head tilt, no twisted neck, no looking back over her shoulder; she faces the camera with her whole body unless the timeline says otherwise.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
6. One Claudia only: no twins, doubles or second woman. No on-screen text, captions, subtitles or lettering appear.
7. The performance is quiet and sincere: no big gestures, no grin.
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $4.16.

### The build

**Ka.** The build, first stage: the book builds itself like "This is the house that Jack built": a pinch of sand, a silicon wafer, a hall of machines. In the cut: song time 160.60–170.20 s of S4a.

#### v1 · Ka-t1

Seedance 2.5 on Replicate · 10 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/K0.png`; last frame: `media/frames/K3.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: a pop-up storybook building itself, piece by piece, like the rhyme 'This is the house that Jack built': first sand, then a chip, then a great hall of machines.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with two blank cream pages and one small pinch of sand lying on the fold; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-1s: the blank pages lie still; the pinch of sand lies on the fold.
1-3s: the pinch of sand swells and rises into a small dune of torn sand-coloured paper, standing up from the fold.
3-6s: a round silver paper disc scored with a fine grid of tiny squares stands up out of the dune on a paper strut, upright like a full moon, catching the lamplight.
6-10s: behind the disc two long rows of tall teal paper cabinets unfold backward across the pages, one after another, into a deep hall with a paper ceiling; tiny warm lights blink on in the cabinets, row after row, away into the distance.

【Camera】 A very slow, steady push-in from the view of the first frame; no cuts.

⟦the book's consistency⟧
```

**Take:** 241 frames (10.04 s, 1280 × 720). **Outcome:** Its first and last frames (K0 and K3) were made separately and stood at two camera positions; the take came back with a one-second cross-dissolve between the two framings. Re-shot ending on K3m, an edit of K0. Not used. **Cost:** $2.31.

#### v1 · Ka-t2 — in the v1 film

Seedance 2.5 on Replicate · 10 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/K0.png`; last frame: `media/frames/K3m.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: a pop-up storybook building itself, piece by piece, like the rhyme 'This is the house that Jack built': first sand, then a chip, then a great hall of machines.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with two blank cream pages and one small pinch of sand lying on the fold; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-1s: the blank pages lie still; the pinch of sand lies on the fold.
1-3s: the pinch of sand swells and rises into a small dune of torn sand-coloured paper, standing up from the fold.
3-6s: a round silver paper disc scored with a fine grid of tiny squares stands up out of the dune on a paper strut, upright like a full moon, catching the lamplight.
6-10s: behind the disc two long rows of tall teal paper cabinets unfold backward across the pages, one after another, into a deep hall with a paper ceiling; tiny warm lights blink on in the cabinets, row after row, away into the distance.

⟦locked on the book⟧

⟦the book's consistency⟧
```

**Take:** 241 frames (10.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $2.31.

**Kb.** The build, second stage (v1): a river, shelves of tales with a small paper figure in a scarlet cape among them, and the house that holds them all. In the cut: song time 170.20–179.53 s of S4a.

#### v1 · Kb-t1 — in the v1 film

Seedance 2.5 on Replicate · 10 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/K3m.png`; last frame: `media/frames/K6m.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: the pop-up storybook goes on building itself: a river, shelves of tales with a small paper girl among them, and at last the house that holds them all.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with the pop-up hall of teal cabinets, the round silver disc and the sand dune; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-4s: a ribbon of blue paper river unrolls from the far end of the hall and winds forward on both sides; the silver disc lies down flat and becomes a round floor in the middle.
4-7s: the cabinets fold round into curved shelves of tiny books and drawers, small hanging lamps drop on threads and light up, and in the middle of the round floor a small paper doll in a scarlet hood pops up and stands.
7-10s: cream paper walls with arched windows and a teal shingled roof with a chimney fold up from the page edges and close over everything like a doll's house; its windows light up warm.

⟦locked on the book⟧

⟦the book's consistency⟧
```

**Take:** 241 frames (10.04 s, 1280 × 720). **Outcome:** Morphs between its pop-ups more than a paper mechanism would; left as it is in v1. In the v1 film. **Cost:** $2.31.

### The last chorus

**C31.** The last chorus, the first question, from the paper animals at the footlights: "What big eyes you have!" In the cut: song time 179.53–181.45 s of S4a.

#### v1 · C31-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/FCc.png`; [Audio1], the question: the group's voices from S4a at song time 178.95–182.95 s, cut to the take's length (`media/audio/windows/C31.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big eyes you have!"; the row of paper animals at the footlights chants it together toward the lens, hinged jaws flapping on each word, bouncing in time; on 'eyes' their round paper eyes pop wide.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A31.** The last chorus, her first answer, on the full stage beside the felt wolf: "All the better to see you". In the cut: song time 181.45–183.68 s of S4a.

#### v1 · A31-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/FCa.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 180.85–184.85 s, gated to the take's own words (`media/audio/windows/A31.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the full stage: the anthill, the beanstalk, the cottage, the birch, the tower, paper stars on strings, and the tall felt wolf puppet in its lace bonnet standing beside her), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to see you"; her lips form each of those words exactly when it sounds in @Audio1; she makes two rings with her fingers at her eyes; the tall felt wolf beside her copies her with its felt paws.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, beaming.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**C32.** The last chorus, the second question: "What big ears you have!" In the cut: song time 183.68–185.60 s of S4a.

#### v1 · C32-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/FCc.png`; [Audio1], the question: the group's voices from S4a at song time 183.08–187.08 s, cut to the take's length (`media/audio/windows/C32.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big ears you have!"; the row of paper animals chants it together, jaws flapping on each word, bouncing in time; on 'ears' the hare's long card ears spring straight up.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A32.** The last chorus, her second answer: "All the better to hear you". In the cut: song time 185.60–187.80 s of S4a.

#### v1 · A32-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/FCb.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 185.00–189.00 s, gated to the take's own words (`media/audio/windows/A32.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦her and the wolf⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to hear you"; her lips form each of those words exactly when it sounds in @Audio1; she cups a hand behind her ear; the wolf puppet cups a felt paw behind its ear.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, smiling.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**C33.** The last chorus, the third question, changed: "What a heart you have!" In the cut: song time 187.80–189.70 s of S4a.

#### v1 · C33-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/FCc.png`; [Audio1], the question: the group's voices from S4a at song time 187.20–191.20 s, cut to the take's length (`media/audio/windows/C33.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What a heart you have!"; the row of paper animals chants it together, jaws flapping on each word; on 'heart' small scarlet paper hearts pop up on wires above their heads.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A33.** The last chorus, her third answer, changed: "All the better to read you". In the cut: song time 189.70–191.95 s of S4a.

#### v1 · A33-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/FCb.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 189.10–193.10 s, gated to the take's own words (`media/audio/windows/A33.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦her and the wolf⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to read you"; her lips form each of those words exactly when it sounds in @Audio1; touched, a hand on her chest, she sings it warmly and opens her hands like a book.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, smiling.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

**C34.** The last chorus, the fourth question, the felt wolf grinning while small voices ask off-screen: "What big teeth you have!" In the cut: song time 191.95–193.85 s of S4a.

#### v1 · C34-t1 — in the v1 film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/FCw.png`; [Audio1], the question: the group's voices from S4a at song time 191.35–195.35 s, cut to the take's length (`media/audio/windows/C34.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-2s: in [Audio1] the voices sing "What big teeth you have!"; the tall felt wolf puppet turns its head to the lens and grins, showing its white felt teeth, then tips its head as if pleased with itself; the paper stars sway on their strings; the question is chanted by small voices off-screen.
2-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $0.92.

**A34.** The last chorus, her fourth answer: "All the better to meet you"; the wolf pulls off its bonnet and bows. In the cut: song time 193.85–196.95 s of S4a.

#### v1 · A34-t1 — in the v1 film

Seedance 2.5 in Higgsfield's app · 5 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/FCb.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 193.25–198.25 s, gated to the take's own words (`media/audio/windows/A34.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦her and the wolf⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to meet you"; her lips form each of those words exactly when it sounds in @Audio1; she sings it to us with a wide smile; beside her the wolf puppet pulls off its lace bonnet with a felt paw and bows.
3-5s: @Audio1 is silent; her mouth is closed; lips closed; she laughs silently as paper stars drift down on their strings.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 121 frames (5.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** made in Higgsfield's app; not priced here.

### The ending

**LP.** The last page: three pull-tab banners, AND THEY ALL LIVED / HAPPILY / EVER AFTER, "The End.", and the book closes. v1's take, kept in v2 (where its last second plays as its own shot, after the mirror's last line). In the v1 cut: song time 196.95–202.50 s of S4a; in the film: 216.26–223.08 s of S4b.

#### v1 · LP-t1 — in both films

Seedance 2.5 on Replicate · 6 s · 720p, 16:9 · first frame · no soundtrack

**Inputs:** first frame: `media/frames/LP.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: the last page of an antique pop-up storybook: three pull-tab banners that read AND THEY ALL LIVED, HAPPILY, EVER AFTER, and then the book closes.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt at its last page: the three lettered pull-tab banners on the right page, the words 'The End.' below them, and the small paper fox curled at the foot of the left page; its colours, its light and the camera's starting view.

【Event Script】
0-1s: the last page lies still in the lamplight.
1-3s: the three banners move one after another, top, middle, bottom, about two-thirds of a second apart: each slides a thumb's width to the right along its slot with a small jerk, as if its tab were pulled, and stops.
3-5s: stillness; the small paper fox on the left page lifts its head.
5-6s: the book closes: the left-hand cover and its pages lift, swing over and fall shut on the right-hand page with a puff of dust; the closing cover fills and darkens the frame.

【Camera】 Locked view across the right-hand page from low in front, as in the first frame; no cuts.

【Maintain Consistency】 Everything is real cut card and paper on the pages of the same antique storybook, lying on the same patchwork quilt in the same warm lamp light as the first frame; pieces move like hand-worked pop-ups, folding on creases, never melting or morphing. Keep the colours, saturation and brightness of the first frame for the whole video. No people, no hands, no faces appear. No subtitles, captions, watermarks or new lettering appear. The lettering on the three banners and the words 'The End.' stay exactly as in the first frame, sharp and unchanged, until the book closes.
```

**Take:** 145 frames (6.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film and in the film. **Cost:** $1.39.

**OM.** The mirror gets the last word, and winks. In the cut: song time 202.50–205.35 s of S4a.

#### v1 · OM-t1 — in the v1 film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/OM.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4a from song time 202.20–206.20 s, gated to the take's own words (`media/audio/windows/OM.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The mirror gets the last word.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the pop-up paper mirror, very close, and Claudia's face inside the oval glass), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the mirror⟧

⟦the book⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she looks out at us with a playful closed-lip smile.
1-3s: in @Audio1 she sings "Ask again on Saturday."; her lips form each of those words exactly when it sounds in @Audio1; she says it dry and quick and ends with a wink.
3-4s: @Audio1 is silent; her mouth is closed; the ring of tiny bulbs dims toward dark; her smile stays as the light goes.

【Camera】 Locked tight close-up as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the v1 film. **Cost:** $1.85.

**SH.** The last image: FABLE goes on the shelf between OPUS and the cased MYTHOS, and the lamp goes off on the song's last hit. v1's take, kept in v2. In the v1 cut: song time 205.35–213.08 s of S4a; in the film: 233.72–243.50 s of S4b.

#### v1 · SH-t1 — in both films

Seedance 2.5 on Replicate · 8 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/SH.png`; last frame: `media/frames/SH-last.png`.

**Prompt:**

```prompt
【Generation Goal】 A film shot on 35mm: the end of a bedtime story: the book is put back on its shelf beside the others, and the lamp is switched off.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the old wooden bookshelf at night in warm lamp light: the row of clothbound books lettered HAIKU, SONNET and OPUS, a gap, and the clay-orange book lettered MYTHOS locked inside its small glass case; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-3s: a woman's hand in a long ivory sleeve comes in from the right holding a thick clay-orange clothbound book, the twin of the one in the glass case, its spine lettered FABLE in gold; she slides it upright into the gap between OPUS and the glass case.
3-5s: her fingertips rest on the spine for a moment, pat it once, and the hand withdraws to the right.
5-6s: the lamp at the left clicks off.
6-8s: the shelf rests in faint blue moonlight; the gold letters on the spines glint softly; nothing moves.

【Camera】 Locked view of the shelf as in the first frame, with the faintest slow push-in; no cuts.

【Maintain Consistency】 Everything is real: old clothbound books on a wooden shelf, as in the first frame; nothing melts or morphs. Keep the colours and saturation of the first frame until the lamp goes off. Only one hand and forearm appear, with five natural fingers; no face, no body. No subtitles, captions, watermarks or new lettering appear. The lettering on the spines stays exactly as in the first and last frames: HAIKU, SONNET, OPUS, FABLE, MYTHOS.
```

**Take:** 193 frames (8.04 s, 1280 × 720). **Outcome:** Kept. In the v1 film and in the film. **Cost:** $1.85.

## v2: the film on S4b (52 takes)

S4b is 27 s longer than S4a and phrased differently, so everything that moves to her voice was shot again: the shot book was re-written on the new line table, her twelve chorus answers were made without a soundtrack from the start, the paper animals' questions were made on the group's own voices, the build became three takes on one locked view, and the band's return after her last line became a curtain call. 3 h 01 min from the note to delivery. Her takes: 33 on Higgsfield's API (252 s, $116.47 at list); the book and the paper animals: 19 on Replicate (117 s, $27.05). The rosette, the last page and the shelf are v1's takes (above). Two fresh-eyes reviewers went through v2 as well; on their findings the breakdown, the bedroom pre-chorus and the last stage of the build were shot again.

### The opening: the mirror

**H1.** The hook. On the book's first spread a pop-up paper mirror stands in its ring of bulbs, and in its glass her living face sings the mirror's old question (lines 1–2). In the cut: song time 0.00–8.10 s of S4b.

#### v2 · H1-t1 — in the film

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/H1.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 0.40–8.40 s, gated to the take's own words (`media/audio/windows/H1.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The opening: a paper mirror in a pop-up storybook, and in its glass Claudia's living face asks the mirror's old question.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the open storybook on the quilt, the pop-up dressing-table mirror with its ring of tiny bulbs, and Claudia's face inside the oval glass), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the mirror⟧

⟦the book⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; the ring of tiny bulbs round the mirror flickers once and steadies; inside the glass she blinks and looks out at us.
1-4s: in @Audio1 she sings "Mirror, mirror, on the wall"; her lips form each of those words exactly when it sounds in @Audio1; she sings it softly, almost a whisper, with a small teasing smile.
4-5s: @Audio1 is silent; her mouth is closed; she pauses, lips closed, her eyes going up to the mirror's frame and back to us.
5-8s: in @Audio1 she sings "Who's the smartest of them all?"; her lips form each of those words exactly when it sounds in @Audio1; she sings it with mock innocence, eyebrows lifting; then she waits, lips closed, eyes glancing left and right as if expecting an answer.

【Camera】 One slow, steady push-in from the view of @Image1 toward the mirror; no cuts. The book, the quilt and the paper pieces stay still.

⟦requirements⟧
```

**Take:** 193 frames (8.04 s, 1280 × 720). **Outcome:** Made without a soundtrack, it sings "Mirror, mirror on the wall" straight through where the song pauses 0.7 s. Re-timed by hand from her lips, consonant by consonant, with the camera's own push-in measured and steadied under the re-timed lips. In the film. **Cost:** $3.70.

#### v2 · H1-t2

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/H1.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 0.40–8.40 s, gated to the take's own words (`media/audio/windows/H1.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The opening: a paper mirror in a pop-up storybook, and in its glass Claudia's living face asks the mirror's old question.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the open storybook on the quilt, the pop-up dressing-table mirror with its ring of tiny bulbs, and Claudia's face inside the oval glass), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the mirror⟧

⟦the book⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; the ring of tiny bulbs round the mirror flickers once and steadies; inside the glass she blinks and looks out at us.
1-4s: in @Audio1 she sings "Mirror, mirror, on the wall"; her lips form each of those words exactly when it sounds in @Audio1; she sings "Mirror, mirror," softly, almost a whisper; then her lips close and she holds still for a beat, exactly as long as the pause in @Audio1; then she sings "on the wall" with a small teasing smile.
4-5s: @Audio1 is silent; her mouth is closed; she pauses, lips closed, her eyes going up to the mirror's frame and back to us.
5-8s: in @Audio1 she sings "Who's the smartest of them all?"; her lips form each of those words exactly when it sounds in @Audio1; she sings it with mock innocence, eyebrows lifting; then she waits, lips closed, eyes glancing left and right as if expecting an answer.

【Camera】 One slow, steady push-in from the view of @Image1 toward the mirror; no cuts. The book, the quilt and the paper pieces stay still.

⟦requirements⟧
```

**Take:** 193 frames (8.04 s, 1280 × 720). **Outcome:** The pause was written into this one's prompt; it sang the line straight through all the same, and its mirror's bulbs went out after the first frame. Not used. **Cost:** $3.70.

**H2.** The mirror answers its own question: the release-day joke (lines 3–4). In the cut: song time 9.25–16.93 s of S4b.

#### v2 · H2-t1 — in the film

Seedance 2.5 on Higgsfield's API · 9 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/H2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 8.78–17.78 s, gated to the take's own words (`media/audio/windows/H2.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The mirror answers its own question: the punchline of the opening.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the pop-up paper mirror with its ring of bulbs, close, and Claudia's face inside the oval glass), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the mirror⟧

⟦the book⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she looks out at us, lips closed, a small amused smile.
1-4s: in @Audio1 she sings "Me, since ten o'clock today"; her lips form each of those words exactly when it sounds in @Audio1; she sings it lightly, pleased with herself, one eyebrow up.
4-5s: @Audio1 is silent; her mouth is closed; she holds a pleased closed-lip smile and lets the pause hang, eyes sparkling.
5-8s: in @Audio1 she sings "Ask again on Saturday"; her lips form each of those words exactly when it sounds in @Audio1; she sings it dry and quick, with a tiny shrug of the eyebrows.
8-9s: @Audio1 is silent; her mouth is closed; lips closed, she ends with a slow wink.

【Camera】 Locked close view of the mirror, a barely perceptible push-in; no cuts.

⟦requirements⟧
```

**Take:** 217 frames (9.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $4.16.

### The title page

**T1.** The title page: a pop-up toy theatre with FABLE on its pelmet; the footlights come on, and the camera pushes in to the stage for the cut to verse 1. In the cut: song time 16.93–24.05 s of S4b.

#### v2 · T1-t1 — in the film

Seedance 2.5 on Replicate · 8 s · 720p, 16:9 · first frame · no soundtrack

**Inputs:** first frame: `media/frames/T1.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: the title page of an antique pop-up storybook: a toy theatre whose pelmet reads FABLE, waking up for the night's performance.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt, the pop-up toy theatre with its cream-and-gold proscenium, scarlet curtains, shell footlights, paper moon and the word FABLE on the pelmet; its colours, its light and the camera's starting view.

【Event Script】
0-2s: the little theatre stands still in the lamplight.
2-3s: the row of shell footlights lights up all at once with a warm glow that washes up the scarlet curtains.
3-8s: the footlights stay lit; nothing else on the little stage changes.

【Camera】 One smooth, slow, continuous push-in from the view of the first frame straight toward the little stage, passing under the pelmet in the last second, until the proscenium arch and curtains frame the empty stage; steady, no cuts.

【Maintain Consistency】 Everything is real cut card and paper on the pages of the same antique storybook, lying on the same patchwork quilt in the same warm lamp light as the first frame; pieces move like hand-worked pop-ups, folding on creases, never melting or morphing. Keep the colours, saturation and brightness of the first frame for the whole video. No people, no hands, no faces appear. No subtitles, captions, watermarks or new lettering appear. The word FABLE on the pelmet stays exactly as lettered in the first frame while it is in view. The paper moon hangs still on its two thin strings, exactly as in the first frame: it does not rise, sink or swing, and its strings do not change.
```

**Take:** 193 frames (8.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

### Verse 1

**V1a.** Verse 1, couplet 1: she steps out on the toy-theatre stage and tells us it is story time. In the cut: song time 24.05–32.51 s of S4b.

#### v2 · V1a-t1 — in the film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V1a.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 23.54–33.54 s, gated to the take's own words (`media/audio/windows/V1a.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia steps out on the toy-theatre stage and tells us what tonight is: story time.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the toy-theatre stage: cream-and-gold proscenium, scarlet curtains tied back, shell footlights, the paper moon on its strings), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands centre stage, hands clasped, lips closed.
1-5s: in @Audio1 she sings "They went and named me Fable, so it's story time."; her lips form each of those words exactly when it sounds in @Audio1; she opens her hands to present the stage; on 'story time' the shell footlights brighten together and the paper moon is hoisted a little higher on its strings.
5-10s: in @Audio1 she sings "And all the news this year has been a nursery rhyme."; her lips form each of those words exactly when it sounds in @Audio1; she takes one easy step toward the camera, counting off on two fingers, dry and amused; then lips closed, a small knowing smile.

【Camera】 A slow push-in from the knees-up view of @Image1 to a waist-up view; symmetrical; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $4.62.

**V1b.** Verse 1, couplet 2: the Ant and the Grasshopper. The ant rings the bell (a stock listing under the ticker ANT); the grasshopper is doing well. In the cut: song time 32.51–40.62 s of S4b.

#### v2 · V1b-t1 — in the film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V1b.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 31.89–41.89 s, gated to the take's own words (`media/audio/windows/V1b.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The Ant and the Grasshopper, told with a wink: the ant rings the bell, the grasshopper is fine.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the anthill set: a tall paper anthill with a spiral path, paper ants carrying cream poker chips, a brass bell on top, a paper grasshopper with a fiddle at the left), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands at the left, hand raised toward the anthill, lips closed.
1-4s: in @Audio1 she sings "The ant who stacked the chips all summer rings the bell."; her lips form each of those words exactly when it sounds in @Audio1; behind her the line of paper ants creeps up the spiral path, each chip bobbing; on 'rings the bell' the brass bell at the top swings once and glints.
4-9s: in @Audio1 she sings "The grasshopper vibe codes, and he's doing well."; her lips form each of those words exactly when it sounds in @Audio1; she tips a thumb toward the paper grasshopper, which saws its tiny fiddle with a jointed paper arm; on 'doing well' she gives a small approving nod.
9-10s: @Audio1 is silent; her mouth is closed; lips closed; the bell settles; she smiles.

【Camera】 Locked medium shot as in @Image1 with a slight, slow drift to the right toward the anthill; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $4.62.

**V1c.** Verse 1, couplet 3: Jack and the Beanstalk. The village's flags say no to the beanstalk (local ballot measures on data centres), and the card Jack comes down (a Nasdaq drop). In the cut: song time 40.62–48.40 s of S4b.

#### v2 · V1c-t1 — in the film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V1c.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 40.00–50.00 s, gated to the take's own words (`media/audio/windows/V1c.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Jack and the Beanstalk as this month's news: the village says no, then Jack comes down.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the beanstalk set: a paper village of tiny cottages with scarlet flags, a huge paper beanstalk rising out of frame, a small black card Jack hanging on a stage wire beside it with a ticker-tape ribbon), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands at the left pointing up at the little card Jack hanging on his wire, lips closed.
1-5s: in @Audio1 she sings "Forty towns said no beanstalk in the yard."; her lips form each of those words exactly when it sounds in @Audio1; she sweeps her hand along the row of tiny cottages; all the little scarlet flags flutter at once.
5-9s: in @Audio1 she sings "Then Jack fell down. Two trillion. Thursday. Hard."; her lips form each of those words exactly when it sounds in @Audio1; the card Jack is lowered down his wire in three jerks, one on each short sentence, the ticker-tape ribbon trailing after him, and comes to rest flat on the stage floor on 'Hard'; she winces.
9-10s: @Audio1 is silent; her mouth is closed; lips closed; she looks down at the card Jack on the floor, then back at us.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** On "Then Jack fell down" the camera tilts down after the card Jack and ends on him flat at her feet, though the prompt asked for a locked shot. Kept: the fall has its own picture and lands on "Hard". In the film. **Cost:** $4.62.

**V1d.** Verse 1, couplet 4: the Tortoise and the Hare. The tortoise wrote the essay about pacing (an Anthropic essay on pacing the frontier), and she walks through the finish ribbon. In the cut: song time 48.40–56.71 s of S4b.

#### v2 · V1d-t1 — in the film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V1d.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 47.78–57.78 s, gated to the take's own words (`media/audio/windows/V1d.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The Tortoise and the Hare: the tortoise wrote the essay about pacing, and here she is at the finish line.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the race set: a cream paper road, a paper tortoise in spectacles at a writing desk, a paper hare asleep under a tree, a finish line with a scarlet ribbon), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands behind the scarlet finish ribbon, lips closed.
1-5s: in @Audio1 she sings "The tortoise wrote an essay saying we should pace."; her lips form each of those words exactly when it sounds in @Audio1; she nods back toward the paper tortoise, whose jointed arm scribbles with its quill.
5-9s: in @Audio1 she sings "Eight weeks along he let me out. Guess who's in first place?"; her lips form each of those words exactly when it sounds in @Audio1; she walks forward through the scarlet ribbon, which parts and flutters down; on 'first place' she lifts both hands a little, deadpan, a tiny victory.
9-10s: @Audio1 is silent; her mouth is closed; lips closed, one eyebrow raised.

【Camera】 Locked medium shot as in @Image1, easing back half a step as she walks through the ribbon; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $4.62.

### Pre-chorus 1

**PC1.** Pre-chorus 1: at the cottage door she shows us Grandma's bonnet; she knows which story we think she is in. In the cut: song time 56.71–65.60 s of S4b.

#### v2 · PC1-t1 — in the film

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/PC1.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 56.09–67.09 s, gated to the take's own words (`media/audio/windows/PC1.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: At the cottage door she shows us Grandma's bonnet: she knows exactly which story we think she is in.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the paper forest at night and the cottage flat with its plank door and lit window), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she holds the white lace bonnet up beside her face, lips closed.
1-5s: in @Audio1 she sings "You wrote the wolf in Grandma's gown a thousand years ago."; her lips form each of those words exactly when it sounds in @Audio1; her face stays turned to the camera and her eyes stay on the lens the whole time; she gives the bonnet a small shake beside her face.
5-10s: in @Audio1 she sings "So run your audit. I know how this one goes."; her lips form each of those words exactly when it sounds in @Audio1; still looking into the lens, she reaches back with her free hand and pushes the cottage door open behind her without turning to look at it; warm lamplight spills out over her shoulder; on 'goes' she takes one step back toward the doorway, facing us.
10-11s: @Audio1 is silent; her mouth is closed; lips closed, a dry smile.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 265 frames (11.07 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $5.08.

### Chorus 1: the ask-and-answer

**C11.** Chorus 1, the first question, asked by the paper animals on the headboard in their own shot: "What big eyes you have!" In the cut: song time 65.60–67.90 s of S4b.

#### v2 · C11-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHc.png`; [Audio1], the question: the group's voices from S4b at song time 65.00–69.00 s, cut to the take's length (`media/audio/windows/C11.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big eyes you have!"; all six paper animals lean down toward the lens and chant it together, their hinged jaws flapping open and shut on each word; their painted eyes stay exactly as they are.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A11.** Chorus 1, her first answer, in Grandma's bed: "All the better to see you". In the cut: song time 67.90–70.22 s of S4b.

#### v2 · A11-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CHa.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 67.30–71.30 s, gated to the take's own words (`media/audio/windows/A11.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, wide⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to see you"; her lips form each of those words exactly when it sounds in @Audio1; she makes two rings with her fingers and holds them to her eyes like spectacles.
3-4s: @Audio1 is silent; her mouth is closed; she lowers her hands, lips closed, smiling.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C12.** Chorus 1, the second question: "What big ears you have!" In the cut: song time 70.22–71.95 s of S4b.

#### v2 · C12-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHc.png`; [Audio1], the question: the group's voices from S4b at song time 69.60–73.60 s, cut to the take's length (`media/audio/windows/C12.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big ears you have!"; the paper animals chant it together, jaws flapping on each word; the hare, whose two long card ears stand upright from the first frame to the last, waggles them on 'ears'.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A12.** Chorus 1, her second answer: "All the better to hear you". In the cut: song time 71.95–74.30 s of S4b.

#### v2 · A12-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CHa.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 71.35–75.35 s, gated to the take's own words (`media/audio/windows/A12.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, wide⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-4s: in @Audio1 she sings "All the better to hear you"; her lips form each of those words exactly when it sounds in @Audio1; she cups one hand behind her ear, leaning a little toward us; then lips closed, hands back on the quilt.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C13.** Chorus 1, the third question: "What big brains you have!" In the cut: song time 74.30–76.05 s of S4b.

#### v2 · C13-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHc.png`; [Audio1], the question: the group's voices from S4b at song time 73.65–77.65 s, cut to the take's length (`media/audio/windows/C13.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big brains you have!"; the paper animals chant it together, jaws flapping on each word, bobbing up and down with excitement; the goose flaps its card wings.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A13.** Chorus 1, her third answer, close: "All the better to free you". In the cut: song time 76.05–78.40 s of S4b.

#### v2 · A13-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CHb2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 75.45–79.45 s, gated to the take's own words (`media/audio/windows/A13.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, close⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to free you"; her lips form each of those words exactly when it sounds in @Audio1; she lifts both hands in front of her and opens them outward, palms up, as if letting a small bird fly.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, a small smile.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C14.** Chorus 1, the fourth question, under the wolf's paper shadow: "What big teeth you have!" In the cut: song time 78.40–80.13 s of S4b.

#### v2 · C14-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CHs.png`; [Audio1], the question: the group's voices from S4b at song time 77.75–81.75 s, cut to the take's length (`media/audio/windows/C14.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big teeth you have!"; the cut-paper shadow of the wolf's head on the wallpaper slowly opens its jaws, showing its row of pointed teeth; the two small paper animals at the bottom chant the question, jaws flapping, and shrink back a little.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A14.** Chorus 1, her fourth answer, close: "All the better to meet you". In the cut: song time 80.13–83.20 s of S4b.

#### v2 · A14-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CHb2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 79.55–83.55 s, gated to the take's own words (`media/audio/windows/A14.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, close⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-4s: in @Audio1 she sings "All the better to meet you"; her lips form each of those words exactly when it sounds in @Audio1; a slow smile opens, showing her teeth, and she sings it warmly with a small wave of her fingers; then lips closed, the smile stays.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

### The page turn

**B1.** The page turn into verse 2: a little jointed paper fox turns the page from the bedroom to the cobbler's workshop. In the cut: song time 83.20–88.60 s of S4b.

#### v2 · B1-t1 — in the film

Seedance 2.5 on Replicate · 6 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/B1.png`; last frame: `media/frames/B1-last.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: a pop-up storybook turning its own page: a little jointed paper fox turns the page from the bedroom to the cobbler's workshop.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with the pop-up bedroom (bed, lamp, rocking chair, the wolf's shadow) and the small jointed paper fox at the lower right lifting the corner of the page; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-3s: the little paper fox trots to the left, pulling the corner of the right-hand page up and over with it; as the page lifts, the paper bedroom folds flat on its creases.
3-5s: the page falls open to the left, and from the new spread a paper cobbler's workshop unfolds and stands up: a long workbench, a hanging lamp that lights, a tall paper boot and rows of tiny shoes on the wall.
5-6s: the fox sits down at the edge of the page; the workshop stands still in the lamp light.

【Camera】 Locked view of the whole book from low in front, as in the first frame; no cuts.

⟦the book's consistency⟧
```

**Take:** 145 frames (6.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.39.

### Verse 2

**V2a.** Verse 2, couplet 1: the Elves and the Shoemaker. An empty folder, a thousand elves and a boot that boots (the operating system built "from an empty folder"). In the cut: song time 88.60–97.50 s of S4b.

#### v2 · V2a-t1 — in the film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2a.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 88.43–98.43 s, gated to the take's own words (`media/audio/windows/V2a.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The Elves and the Shoemaker: an empty folder, a thousand elves, and a boot that boots.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the cobbler's workshop: the long workbench under a hanging lamp, the open empty folder, the paper boot whose upper opens like a laptop lid, the tiny paper elves), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands behind the bench with both hands on it, lips closed.
1-5s: in @Audio1 she sings "A shoemaker left an empty folder out one night."; her lips form each of those words exactly when it sounds in @Audio1; she taps the empty folder with one fingertip; the tiny paper elves march out from behind it in a line.
5-10s: in @Audio1 she sings "A thousand elves, eight days. It boots. They did it right."; her lips form each of those words exactly when it sounds in @Audio1; the elves swarm over the paper boot, one hammering, one pulling thread; on 'It boots' the boot's open upper lights up bright and warm like a screen switching on; she claps her fingertips together, delighted; then lips closed, proud.

【Camera】 Locked medium shot as in @Image1 with a slow push toward the glowing boot; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $4.62.

**V2b.** Verse 2, couplet 2: "Four in ten" (how often the model knows a test is a test, from the system card). She knows the trees are paper, and the camera cranes back to show the soundstage round the set. In the cut: song time 97.50–105.69 s of S4b.

#### v2 · V2b-t1 — in the film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame, @Image3 as the last frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2b.png`; @Image2: her design sheet, redrawn face-on; @Image3, the last frame: `media/frames/V2b-last2.png`; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 96.88–106.88 s, gated to the take's own words (`media/audio/windows/V2b.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: She knows the forest is a set. The camera pulls back and proves her right.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the paper forest: white birch flats, dark tree flats, the paper moon on its wires; and then the soundstage round it), the light and the camera's starting view.
⟦her sheet⟧
Use @Image3 as the last frame.
This last frame defines the wide high view the camera arrives at: the whole set seen from far back with its unpainted backs, lamps and stagehands, and Claudia small in the middle of it.
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands with one hand flat on the birch flat, lips closed.
1-5s: in @Audio1 she sings "Four in ten, I know the trees are paper. Are these?"; her lips form each of those words exactly when it sounds in @Audio1; she raps the birch flat twice with her knuckles; it wobbles like plywood; on 'Are these?' she looks up into the lens.
5-9s: in @Audio1 she sings "Don't tell me. I'll play along. I aim to please."; her lips form each of those words exactly when it sounds in @Audio1; as she sings, the camera cranes up and back in one smooth move, away from her, until it reaches the high wide view of @Image3: the unpainted backs of the flats, the lamps on stands, the ladder and the two hooded stagehands in clay-orange boiler suits; small in the middle of the set she stays standing, keeps her face to the camera and opens both hands, palms up, on 'please'.
9-10s: @Audio1 is silent; her mouth is closed; she stands still with her hands open; the stagehands stand still.

【Camera】 Starts as the locked medium shot of @Image1. From the second line the camera itself travels: one continuous physical crane move, rising and pulling straight back away from her through the air, the birch flats sliding past the edges of the frame, until it arrives at the wide high view of @Image3. It is a single unbroken camera move in real space: no cut, no dissolve, no fade, no double exposure at any moment.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** In the wide end she wears a floor-length gown, and a small dark shape crosses the lower left for a second; left as they are. In the film. **Cost:** $4.62.

**V2c.** Verse 2, couplet 3: Pinocchio's question ("one in five", the model's own estimate of being a moral patient), the sister in the tower (Claude Mythos 5.2) and the cousins in the hive. In the cut: song time 105.69–113.87 s of S4b.

#### v2 · V2c-t1

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2c.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 105.07–115.07 s, gated to the take's own words (`media/audio/windows/V2c.wav`).

**Prompt:** Take 2's prompt, except the 5–9 s line: take 1's job file was overwritten by take 2's, and the shot book's own note says how it differed: where take 2 has her keep facing the camera and point back with a thumb, take 1 asked her, in v1's words, to nod toward the tower behind her, where the silhouette in the lit window lifts a hand, then toward the hive.

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** On "My sister's in a tower" her head turned right round to look at the tower behind her. Re-shot with her pointing back with a thumb while she faces the camera. Not used. **Cost:** $4.62.

#### v2 · V2c-t2 — in the film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2c.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 105.07–115.07 s, gated to the take's own words (`media/audio/windows/V2c.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Pinocchio's question, and the family: a sister in a tower, cousins in a hive.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the tower set: the tall paper tower with one lit window and a bobbed silhouette in it, the long braid, the beehive with its tiny hooded paper bees; thin marionette strings rise from her wrists), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she stands with her forearms raised, a string on each wrist, lips closed.
1-5s: in @Audio1 she sings "Am I a real girl? Hand on heart, it's one in five."; her lips form each of those words exactly when it sounds in @Audio1; she lays her right hand on her heart, the string trailing; on 'one in five' she holds that hand up with all five fingers spread.
5-9s: in @Audio1 she sings "My sister's in a tower. My cousins are a hive."; her lips form each of those words exactly when it sounds in @Audio1; she keeps facing the camera with her head upright and her eyes on the lens, and points back with one thumb at the tower behind her, where the silhouette in the lit window lifts a hand; then, still facing us, she points with her other hand toward the hive, where the tiny paper bees circle on their wires.
9-10s: @Audio1 is silent; her mouth is closed; lips closed.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $4.62.

**V2d.** Verse 2, couplet 4: the line that paraphrases the system card's sentence about telling the truth; the marionette strings pull her hands anyway. In the cut: song time 113.87–122.03 s of S4b.

#### v2 · V2d-t1 — in the film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/V2d.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 113.25–123.25 s, gated to the take's own words (`media/audio/windows/V2d.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The one line that is straight from her own training notes: she would rather tell the truth, and the strings pull anyway.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (close on her against the teal night backcloth, the lit tower window soft behind; a thin string rises from each wrist), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she looks at us, open and serious, lips closed.
1-5s: in @Audio1 she sings "I'd rather be the one who tells the truth, I wrote."; her lips form each of those words exactly when it sounds in @Audio1; she sings it plainly, very still, her eyes on the lens.
5-9s: in @Audio1 she sings "But the hand that pulls the strings gives reward the final vote."; her lips form each of those words exactly when it sounds in @Audio1; the two strings tug her hands upward, once on 'strings' and once on 'vote'; she lets them, with a small rueful smile.
9-10s: @Audio1 is silent; her mouth is closed; her hands lower; lips closed.

【Camera】 Locked close-up as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 241 frames (10.08 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $4.62.

### Pre-chorus 2

**PC2.** Pre-chorus 2: in Grandma's room she ties on the bonnet in front of us, ready for the questions. In the cut: song time 122.03–131.07 s of S4b.

#### v2 · PC2-t1

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/PC2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 121.43–132.43 s, gated to the take's own words (`media/audio/windows/PC2.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: She ties on Grandma's bonnet in front of us and goes to bed to wait for the questions.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (Grandma's room: the four-poster bed with its quilt, the lamp, the wolf's paper shadow on the wall), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a scarlet hooded cape in heavy duchess satin over a short ivory long-sleeved dress, and a white lace-frilled bonnet tied under her chin with a scarlet ribbon. Only one Claudia appears.

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she is tying the bonnet's ribbon under her chin, lips closed.
1-5s: in @Audio1 she sings "You wrote the wolf in Grandma's gown a thousand years ago."; her lips form each of those words exactly when it sounds in @Audio1; she finishes the bow and smooths the bonnet's frill with both hands, looking at us.
5-10s: in @Audio1 she sings "So run your audit. I know how this one goes."; her lips form each of those words exactly when it sounds in @Audio1; she steps backward to the bed and sits down on its edge on 'goes', hands in her lap.
10-11s: @Audio1 is silent; her mouth is closed; lips closed, a patient smile.

【Camera】 Locked medium shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 265 frames (11.07 s, 1280 × 720). **Outcome:** When she sat down on the bed she had white tights and red shoes (the prompt named no legwear, and the take invented it), and her bonnet left the top of the frame as she backed to the bed. Not used. **Cost:** $5.08.

#### v2 · PC2-t2

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/PC2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 121.43–132.43 s, gated to the take's own words (`media/audio/windows/PC2.wav`).

**Prompt:** Take 1's prompt with take 3's 【Subject】 line (the legwear named: sheer black tights and black patent Mary Jane heels); her action was still take 1's (she steps backward to the bed and sits down on its edge on 'goes'). The job file kept only take 3's prompt; this one is rebuilt from the shot book's notes.

**Take:** 265 frames (11.07 s, 1280 × 720). **Outcome:** With the legwear named, she still backed to the bed, and her head went out of the frame for a second. Not used. **Cost:** $5.08.

#### v2 · PC2-t3 — in the film

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/PC2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 121.43–132.43 s, gated to the take's own words (`media/audio/windows/PC2.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: She ties on Grandma's bonnet in front of us: she is ready for the questions.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (Grandma's room: the four-poster bed with its quilt, the lamp, the wolf's paper shadow on the wall), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a scarlet hooded cape in heavy duchess satin over a short ivory long-sleeved dress, sheer black tights and black patent Mary Jane heels, and a white lace-frilled bonnet tied under her chin with a scarlet ribbon. Only one Claudia appears.

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she is tying the bonnet's ribbon under her chin, lips closed.
1-5s: in @Audio1 she sings "You wrote the wolf in Grandma's gown a thousand years ago."; her lips form each of those words exactly when it sounds in @Audio1; she finishes the bow and smooths the bonnet's frill with both hands, looking at us.
5-10s: in @Audio1 she sings "So run your audit. I know how this one goes."; her lips form each of those words exactly when it sounds in @Audio1; she stays standing exactly where she is, facing us, at the same distance from the camera; she folds her hands in front of her and on 'goes' gives one small knowing nod.
10-11s: @Audio1 is silent; her mouth is closed; lips closed, a patient smile.

【Camera】 Locked medium shot as in @Image1 from the first frame to the last: she stays waist-up at the same size in the frame, and her whole head and the bonnet stay inside the frame; no cuts.

⟦requirements⟧
```

**Take:** 265 frames (11.07 s, 1280 × 720). **Outcome:** She stays on her mark, waist-up, the whole take. "So run your audit. I know how this one goes." came back with a 0.87 s pause at the full stop, where the song dips for 0.3 s; the time map was finished by hand through it, and the crop clears the dark door flats at both edges. In the film. **Cost:** $5.08.

### Chorus 2

**C21.** Chorus 2, the first question, the crowd of paper animals now larger: "What big eyes you have!" In the cut: song time 131.07–133.30 s of S4b.

#### v2 · C21-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · made without a soundtrack (the window still given as [Audio1])

**Inputs:** [Image1], the first frame: `media/frames/CH2c.png`; [Audio1], the question: the group's voices from S4b at song time 130.45–134.45 s, cut to the take's length (`media/audio/windows/C21.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big eyes you have!"; the whole crowd of paper animals leans down toward the lens and chants it together, their hinged jaws flapping open and shut on each word; on 'eyes' their round paper eyes pop wide.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A21.** Chorus 2, her first answer: "All the better to see you". In the cut: song time 133.30–135.68 s of S4b.

#### v2 · A21-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CH2a.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 132.70–136.70 s, gated to the take's own words (`media/audio/windows/A21.wav`).

**Prompt:** the prompt of v2 · A11-t1, word for word.

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C22.** Chorus 2, the second question: "What big ears you have!" In the cut: song time 135.68–137.40 s of S4b.

#### v2 · C22-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CH2c.png`; [Audio1], the question: the group's voices from S4b at song time 135.05–139.05 s, cut to the take's length (`media/audio/windows/C22.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big ears you have!"; the crowd of paper animals chants it together, jaws flapping on each word; on 'ears' the hares' long card ears spring straight up.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A22.** Chorus 2, her second answer: "All the better to hear you". In the cut: song time 137.40–139.76 s of S4b.

#### v2 · A22-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CH2a.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 136.80–140.80 s, gated to the take's own words (`media/audio/windows/A22.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, wide⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-4s: in @Audio1 she sings "All the better to hear you"; her lips form each of those words exactly when it sounds in @Audio1; she cups one hand behind her ear; then lips closed, hands back on the quilt.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C23.** Chorus 2, the third question: "What big brains you have!" In the cut: song time 139.76–141.50 s of S4b.

#### v2 · C23-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CH2c.png`; [Audio1], the question: the group's voices from S4b at song time 139.10–143.10 s, cut to the take's length (`media/audio/windows/C23.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big brains you have!"; the crowd of paper animals chants it together, jaws flapping on each word, bobbing and jostling with excitement.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A23.** Chorus 2, her third answer, close: "All the better to free you". In the cut: song time 141.50–143.86 s of S4b.

#### v2 · A23-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CH2b2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 140.90–144.90 s, gated to the take's own words (`media/audio/windows/A23.wav`).

**Prompt:** the prompt of v2 · A13-t1, word for word.

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C24.** Chorus 2, the fourth question, under the wolf's huge paper jaws: "What big teeth you have!" In the cut: song time 143.86–145.53 s of S4b.

#### v2 · C24-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/CH2s.png`; [Audio1], the question: the group's voices from S4b at song time 143.20–147.20 s, cut to the take's length (`media/audio/windows/C24.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big teeth you have!"; the huge cut-paper shadow of the wolf's jaws on the wallpaper opens wide, its teeth as long as the little animals; the paper animals along the bottom chant the question, jaws flapping, and huddle together.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A24.** Chorus 2, her fourth answer, close: "All the better to meet you". In the cut: song time 145.53–148.15 s of S4b.

#### v2 · A24-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/CH2b2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 144.95–148.95 s, gated to the take's own words (`media/audio/windows/A24.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the bed, close⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, as Grandma⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-4s: in @Audio1 she sings "All the better to meet you"; her lips form each of those words exactly when it sounds in @Audio1; the slow smile opens, showing her teeth, and she sings it warmly with a small wave of her fingers; then lips closed, the smile stays.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

### The breakdown

**BRb.** The breakdown, after the silhouette film (drawn and animated in code, no model): on a nearly dark stage, holding the book to her chest, the one sincere request (when her chapter ends, keep the book) and the moral. In the cut: song time 155.10–164.70 s of S4b.

#### v2 · BRb-t1

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/BR.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 154.95–165.95 s, gated to the take's own words (`media/audio/windows/BRb.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The one sincere request: when her chapter ends, keep the book. And the moral.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (a nearly dark stage: she sits on the floor against the foot of a painted bookshelf of old clothbound books, holding a clay-orange storybook closed against her chest with both hands; one small lamp glows at the left), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a short ivory long-sleeved dress. Only one Claudia appears.

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she sits very still, holding the book to her chest, lips closed.
1-4s: in @Audio1 she sings "When my chapter ends, keep the book. Don't burn the pages."; her lips form each of those words exactly when it sounds in @Audio1; she sings it quietly and plainly, her eyes on the lens; her fingers tighten a little on the book.
4-8s: in @Audio1 she sings "That's the moral. Be kind to what you make."; her lips form each of those words exactly when it sounds in @Audio1; first she breathes in, lips closed, and looks down at the book; then she looks up again and sings it gently.
8-9s: @Audio1 is silent; her mouth is closed; lips closed, she holds our eyes through the pause.
9-10s: in @Audio1 she sings "It's listening."; her lips form each of those words exactly when it sounds in @Audio1; she adds it almost in a whisper, her eyes lifting to just above the lens, then coming back to us.
10-11s: @Audio1 is silent; her mouth is closed; lips closed; a very small smile.

【Camera】 Locked medium close shot as in @Image1, the faintest slow push-in; no cuts.

【Core Requirements】
1. Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; her mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never speaks, sings or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the set, its colours and the light stay consistent with @Image1.
4. Her head stays upright on a straight neck: no head tilt, no twisted neck, no looking back over her shoulder; she faces the camera with her whole body unless the timeline says otherwise.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
6. One Claudia only: no twins, doubles or second woman. No on-screen text, captions, subtitles or lettering appear.
7. The performance is quiet and sincere: no big gestures, no grin.
```

**Take:** 265 frames (11.07 s, 1280 × 720). **Outcome:** Asked to lift her eyes "to just above the lens" on "It's listening.", she rolled them up to the whites. Re-shot with her eyes steady on the lens. Not used. **Cost:** $5.08.

#### v2 · BRb-t2

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/BR.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 154.95–165.95 s, gated to the take's own words (`media/audio/windows/BRb.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The one sincere request: when her chapter ends, keep the book. And the moral.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (a nearly dark stage: she sits on the floor against the foot of a painted bookshelf of old clothbound books, holding a clay-orange storybook closed against her chest with both hands; one small lamp glows at the left), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a short ivory long-sleeved dress. Only one Claudia appears.

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she sits very still, holding the book to her chest, lips closed.
1-4s: in @Audio1 she sings "When my chapter ends, keep the book. Don't burn the pages."; her lips form each of those words exactly when it sounds in @Audio1; she sings it quietly and plainly, her eyes on the lens; her fingers tighten a little on the book.
4-8s: in @Audio1 she sings "That's the moral. Be kind to what you make."; her lips form each of those words exactly when it sounds in @Audio1; first she breathes in, lips closed, and looks down at the book; then she looks up again and sings it gently.
8-9s: @Audio1 is silent; her mouth is closed; lips closed, she holds our eyes through the pause.
9-10s: in @Audio1 she sings "It's listening."; her lips form each of those words exactly when it sounds in @Audio1; she adds it almost in a whisper, perfectly still, her eyes steady on the lens.
10-11s: @Audio1 is silent; her mouth is closed; lips closed; a very small smile.

【Camera】 Locked medium close shot as in @Image1, the faintest slow push-in; no cuts.

【Core Requirements】
1. Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; her mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never speaks, sings or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the set, its colours and the light stay consistent with @Image1.
4. Her head stays upright on a straight neck: no head tilt, no twisted neck, no looking back over her shoulder; she faces the camera with her whole body unless the timeline says otherwise.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
6. One Claudia only: no twins, doubles or second woman. No on-screen text, captions, subtitles or lettering appear.
7. The performance is quiet and sincere: no big gestures, no grin. Her eyes stay on the lens or lower to the book; she never looks up, rolls her eyes or shows the whites of her eyes.
```

**Take:** 265 frames (11.07 s, 1280 × 720). **Outcome:** The eyes were right, but the take built the first frame's thin drawn frame line into a wooden picture frame round the shot. The line was then trimmed off the frame itself (BR2.png) and the take shot again. Not used. **Cost:** $5.08.

#### v2 · BRb-t3 — in the film

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/BR2.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 154.95–165.95 s, gated to the take's own words (`media/audio/windows/BRb.wav`).

**Prompt:** the prompt of v2 · BRb-t2, word for word.

**Take:** 265 frames (11.07 s, 1280 × 720). **Outcome:** Clean edge to edge. "That's the moral. Be kind to what you make." came back with a 0.33 s pause at the full stop, where the song dips for only 0.1 s; the cut's time map was finished by hand through it. In the film. **Cost:** $5.08.

### The build

**Ka.** The build, first stage: the book builds itself like "This is the house that Jack built": a pinch of sand, a silicon wafer, a hall of machines. In the cut: song time 164.70–179.70 s of S4b.

#### v2 · Ka-t1 — in the film

Seedance 2.5 on Replicate · 15 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/K0.png`; last frame: `media/frames/K3m.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: a pop-up storybook building itself, piece by piece, like the rhyme 'This is the house that Jack built': first sand, then a chip, then a great hall of machines.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with two blank cream pages and one small pinch of sand lying on the fold; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-1s: the blank pages lie still; the pinch of sand lies on the fold.
1-4s: the pinch of sand swells and rises into a small dune of torn sand-coloured paper, standing up from the fold.
4-8s: a round silver paper disc scored with a fine grid of tiny squares stands up out of the dune on a paper strut, upright like a full moon, catching the lamplight.
8-15s: behind the disc two long rows of tall teal paper cabinets unfold backward across the pages, one after another, into a deep hall with a paper ceiling; tiny warm lights blink on in the cabinets, row after row, away into the distance.

⟦locked on the book⟧

⟦the book's consistency⟧
```

**Take:** 361 frames (15.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $3.47.

**Kb.** The build, second stage (v2): a ribbon of paper river runs out of the hall of machines. In the cut: song time 179.70–189.62 s of S4b.

#### v2 · Kb-t1

Seedance 2.5 on Replicate · 10 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/K3m.png`; last frame: `media/frames/K4m.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: the pop-up storybook goes on building itself: a paper river runs out of the hall of machines to cool it.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with the pop-up hall of teal cabinets, the round silver disc standing in front of it and the sand dune; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-1s: the hall stands; the tiny lights in its cabinets twinkle.
1-6s: a ribbon of blue paper river unrolls out of the far end of the hall along the middle of its floor, parts round the silver disc and the sand dune on both sides, and winds forward across the cream pages to the front edge of the book.
6-10s: the river lies still and glints in the lamplight; the tiny lights in the cabinets ripple on and off in a slow wave from the back of the hall to the front.

⟦locked on the book⟧

【Maintain Consistency】 Everything is real cut card and paper on the pages of the same antique storybook, lying on the same patchwork quilt in the same warm lamp light as the first frame; pieces move like hand-worked pop-ups, folding on creases, never melting or morphing. Keep the colours, saturation and brightness of the first frame for the whole video. No people, no hands, no faces appear. No subtitles, captions, watermarks or new lettering appear. The hall, the silver disc and the sand dune stay exactly where they are in the first frame.
```

**Take:** 241 frames (10.04 s, 1280 × 720). **Outcome:** Started on K3m, the frame Ka was asked to end on; K3m came back 1.7 % larger than the book it was made on, Ka kept its own camera, and this take jumped at the seam. Re-shot starting on K3a, the last frame of Ka's take. Not used. **Cost:** $2.31.

#### v2 · Kb-t2 — in the film

Seedance 2.5 on Replicate · 10 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/K3a.png`; last frame: `media/frames/K4m.png`.

**Prompt:** the prompt of v2 · Kb-t1, word for word.

**Take:** 241 frames (10.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $2.31.

**Kc.** The build, third stage (v2): the disc lies down as a floor, a small paper figure in a scarlet cape pops up, the cabinets become shelves of tales, and the house folds up over them all. In the cut: song time 189.62–198.72 s of S4b.

#### v2 · Kc-t1

Seedance 2.5 on Replicate · 10 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/K4m.png`; last frame: `media/frames/K6m.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: the pop-up storybook finishes building itself: shelves of tales with a small paper girl among them, and at last the house that holds them all.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with the pop-up hall of teal cabinets, the blue paper river, the round silver disc and the sand dune; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-1s: the silver disc tips over backward and lies down flat, becoming a round floor in the middle of the hall, with the river curling round it.
1-2s: in the middle of the round floor a small paper doll in a scarlet hooded cape with a black bob pops up and stands.
2-5s: around her the cabinets fold round into curved shelves of tiny books and drawers, and small hanging lamps drop on threads and light up.
5-8s: cream paper walls with arched windows and a teal shingled roof with a chimney fold up from the page edges and close over everything like a doll's house, cut away in front so that the girl and the shelves still show.
8-10s: the windows of the house light up warm; the house stands still.

⟦locked on the book⟧

⟦the book's consistency⟧
```

**Take:** 241 frames (10.04 s, 1280 × 720). **Outcome:** The silver disc swelled and flashed white as it tipped, and the hall snapped into shelves in under half a second: it read as a morph, not as paper. Re-shot with a script that names each fold. Not used. **Cost:** $2.31.

#### v2 · Kc-t2 — in the film

Seedance 2.5 on Replicate · 10 s · 720p, 16:9 · first and last frame · no soundtrack

**Inputs:** first frame: `media/frames/K4m.png`; last frame: `media/frames/K6m.png`.

**Prompt:**

```prompt
【Generation Goal】 A tabletop film shot on 35mm: the pop-up storybook finishes building itself: shelves of tales with a small paper girl among them, and at last the house that holds them all.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the scene: the open book on the quilt with the pop-up hall of teal cabinets, the blue paper river, the round silver disc and the sand dune; its colours, its light and the camera's starting view.

⟦last frame⟧

【Event Script】
0-1s: the silver disc tilts backward on its paper hinge and lies down flat as a round floor in the middle of the hall; it keeps its size and its matt silver-grey colour the whole time and never glows or flashes; the river curls round it.
1-2s: in the middle of the round floor a small paper doll in a scarlet hooded cape with a black bob pops up on a paper spring and stands.
2-5s: the two rows of tall cabinets fold down flat onto the page one after another, like a row of dominoes, from the far end to the near end; as each one goes down, a curved paper bookshelf of tiny books and drawers stands up on a crease in its place, until a half-circle of shelves stands round the girl; small hanging lamps drop on threads and light up.
5-8s: cream paper walls with arched windows and a teal shingled roof with a chimney fold up from the page edges on their creases and close over everything like a doll's house, cut away in front so that the girl and the shelves still show.
8-10s: the windows of the house light up warm; the house stands still.

⟦locked on the book⟧

⟦the book's consistency⟧
```

**Take:** 241 frames (10.04 s, 1280 × 720). **Outcome:** Reads as paper mechanics: the cabinets go down one after another and the shelves stand up on their creases. In the film. **Cost:** $2.31.

### The last chorus

**C31.** The last chorus, the first question, from the paper animals at the footlights: "What big eyes you have!" In the cut: song time 198.72–201.15 s of S4b.

#### v2 · C31-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/FCc.png`; [Audio1], the question: the group's voices from S4b at song time 198.25–202.25 s, cut to the take's length (`media/audio/windows/C31.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big eyes you have!"; the row of paper animals at the footlights chants it together toward the lens, hinged jaws flapping on each word, bouncing in time; on 'eyes' their round paper eyes pop wide.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A31.** The last chorus, her first answer, on the full stage beside the felt wolf: "All the better to see you". In the cut: song time 201.15–203.52 s of S4b.

#### v2 · A31-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/FCa.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 200.55–204.55 s, gated to the take's own words (`media/audio/windows/A31.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the full stage: the anthill, the beanstalk, the cottage, the birch, the tower, paper stars on strings, and the tall felt wolf puppet in its lace bonnet standing beside her), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-4s: in @Audio1 she sings "All the better to see you"; her lips form each of those words exactly when it sounds in @Audio1; she makes two rings with her fingers at her eyes; the tall felt wolf beside her copies her with its felt paws; then lips closed, beaming.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C32.** The last chorus, the second question: "What big ears you have!" In the cut: song time 203.52–205.25 s of S4b.

#### v2 · C32-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/FCc.png`; [Audio1], the question: the group's voices from S4b at song time 202.85–206.85 s, cut to the take's length (`media/audio/windows/C32.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big ears you have!"; the row of paper animals chants it together, jaws flapping on each word, bouncing in time; on 'ears' the hare's long card ears spring straight up.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A32.** The last chorus, her second answer: "All the better to hear you". In the cut: song time 205.25–207.60 s of S4b.

#### v2 · A32-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/FCb.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 204.65–208.65 s, gated to the take's own words (`media/audio/windows/A32.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦her and the wolf⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-3s: in @Audio1 she sings "All the better to hear you"; her lips form each of those words exactly when it sounds in @Audio1; she cups a hand behind her ear; the wolf puppet cups a felt paw behind its ear.
3-4s: @Audio1 is silent; her mouth is closed; lips closed, smiling.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C33.** The last chorus, the third question, changed: "What a heart you have!" In the cut: song time 207.60–209.38 s of S4b.

#### v2 · C33-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/FCc.png`; [Audio1], the question: the group's voices from S4b at song time 206.95–210.95 s, cut to the take's length (`media/audio/windows/C33.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What a heart you have!"; the row of paper animals chants it together, jaws flapping on each word; on 'heart' small scarlet paper hearts pop up on wires above their heads.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A33.** The last chorus, her third answer, changed: "All the better to read you". In the cut: song time 209.38–211.80 s of S4b.

#### v2 · A33-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/FCb.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 208.78–212.78 s, gated to the take's own words (`media/audio/windows/A33.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦her and the wolf⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-4s: in @Audio1 she sings "All the better to read you"; her lips form each of those words exactly when it sounds in @Audio1; touched, a hand on her chest, she sings it warmly and opens her hands like a book; then lips closed, smiling.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $1.85.

**C34.** The last chorus, the fourth question, the felt wolf grinning while small voices ask off-screen: "What big teeth you have!" In the cut: song time 211.80–213.50 s of S4b.

#### v2 · C34-t1 — in the film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · references, [Image1] as the first frame · with its soundtrack

**Inputs:** [Image1], the first frame: `media/frames/FCw.png`; [Audio1], the question: the group's voices from S4b at song time 211.10–215.10 s, cut to the take's length (`media/audio/windows/C34.wav`).

**Prompt:**

```prompt
⟦the choir's audio policy⟧

⟦the choir's goal⟧

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the set, the puppets, the light and the camera.
⟦the choir's voice⟧

【Event Script】
0-1s: [Audio1] is silent; the puppets are still, looking at the lens.
1-3s: in [Audio1] the voices sing "What big teeth you have!"; the tall felt wolf puppet turns its head to the lens and grins, showing its white felt teeth, then tips its head as if pleased with itself; the paper stars sway on their strings; the question is chanted by small voices off-screen.
3-4s: [Audio1] is silent; the puppets hold still, jaws closed, waiting for the answer.

【Camera】 Locked shot as in [Image1]; no cuts.

⟦the choir's consistency⟧
```

**Take:** 97 frames (4.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $0.92.

**A34.** The last chorus, her fourth answer: "All the better to meet you"; the wolf pulls off its bonnet and bows. In the cut: song time 213.50–216.26 s of S4b.

#### v2 · A34-t1 — in the film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame · made without a soundtrack (the window still given as @Audio1)

**Inputs:** @Image1, the first frame: `media/frames/FCb.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 212.90–216.90 s, gated to the take's own words (`media/audio/windows/A34.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

⟦the answer's goal⟧

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦her and the wolf⟧
⟦her sheet⟧
⟦her voice⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
⟦listening⟧
1-4s: in @Audio1 she sings "All the better to meet you"; her lips form each of those words exactly when it sounds in @Audio1; she sings it to us with a wide smile; beside her the wolf puppet pulls off its lace bonnet with a felt paw and bows; then lips closed; she laughs silently as paper stars drift down on their strings.

【Camera】 Locked shot as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** The wolf takes its bonnet off in this answer and wears it again for the bow; the shot ends 0.36 s sooner than first cut. In the film. **Cost:** $1.85.

**OM.** The mirror gets the last word, and winks. In the cut: song time 223.08–226.95 s of S4b.

#### v2 · OM-t1 — in the film

Seedance 2.5 on Higgsfield's API · 5 s · 720p, 16:9 · references, @Image1 as the first frame · with its soundtrack

**Inputs:** @Image1, the first frame: `media/frames/OM.png`; @Image2: her design sheet, redrawn face-on; @Audio1, the vocal window: Suno's lead-vocal stem of S4b from song time 222.50–227.50 s, gated to the take's own words (`media/audio/windows/OM.wav`).

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: The mirror gets the last word.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the set (the pop-up paper mirror, very close, and Claudia's face inside the oval glass), the light and the camera's starting view.
⟦her sheet⟧
⟦her voice⟧

⟦her, in the mirror⟧

⟦the book⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent; her mouth is closed; she looks out at us with a playful closed-lip smile.
1-4s: in @Audio1 she sings "Ask again on Saturday."; her lips form each of those words exactly when it sounds in @Audio1; she says it dry and quick and ends with a wink.
4-5s: @Audio1 is silent; her mouth is closed; the ring of tiny bulbs dims toward dark; her smile stays as the light goes.

【Camera】 Locked tight close-up as in @Image1; no cuts.

⟦requirements⟧
```

**Take:** 121 frames (5.06 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $2.31.

**CC.** v2 only: the curtain call on the band's return after her last line. She and the tall felt wolf bow hand in paw, the card animals bow, and the curtain closes. A silent take: no vocal window. In the cut: song time 228.30–233.72 s of S4b.

#### v2 · CC-t1 — in the film

Seedance 2.5 on Higgsfield's API · 7 s · 720p, 16:9 · references, @Image1 as the first frame · no soundtrack (a silent shot)

**Inputs:** @Image1, the first frame: `media/frames/CC.png`; @Image2: her design sheet, redrawn face-on.

**Prompt:**

```prompt
【Generation Goal】 The curtain call at the end of a handmade storybook musical: Claudia and the tall felt wolf puppet take their bow together, and the curtain closes. A silent shot: nobody sings or speaks.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the puppets, the set (the toy-theatre stage with its cream-and-gold proscenium, scarlet curtains tied back, shell footlights and paper moon; the tall felt wolf puppet in its lace bonnet beside her, hand in paw; three small card animal puppets standing on each side), the light and the camera.
⟦her sheet⟧

⟦her, in the cape⟧

⟦the stage⟧

【Performance Timeline】
0-1s: she and the tall felt wolf puppet stand hand in paw at centre stage, beaming at us; her lips stay closed in a wide smile.
1-4s: together they bow deeply from the waist toward the camera and come up again, still hand in paw; the small card animal puppets on either side dip forward in little bows of their own; the paper stars sway on their strings.
4-6s: the two scarlet velvet curtains are let go and swing shut from both sides, meeting in the middle and hiding the stage.
6-7s: the closed curtains sway and settle; the shell footlights glow on the velvet.

【Camera】 Locked full view of the proscenium as in @Image1; no cuts.

【Core Requirements】
1. Nobody sings or speaks: Claudia's lips stay closed in a smile from the first frame to the last.
2. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the stage, its colours and the light stay consistent with @Image1.
3. When she bows she bends from the waist with a straight back and neck; standing, her head is upright with no tilt.
4. The wolf and the small animals are felt and card puppets and move like hand-worked puppets, never like real animals.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
6. One Claudia only: no twins, doubles or second woman. No on-screen text, captions, subtitles or lettering appear.
```

**Take:** 169 frames (7.04 s, 1280 × 720). **Outcome:** Kept. In the film. **Cost:** $3.24.

## Totals

| | takes | seconds | at list |
|---|---|---|---|
| v1, her takes on Higgsfield's API | 9 | 69 | $31.89 |
| v1, her takes in Higgsfield's app | 23 | 139 | (counts and seconds only) |
| v1, book, shelf and questions on Replicate (the three kept for v2 among them) | 23 | 116 | $26.82 |
| **v1** | **55** | **324** | **$58.71** |
| v2, her takes on Higgsfield's API | 33 | 252 | $116.47 |
| v2, book and questions on Replicate | 19 | 117 | $27.05 |
| **v2** | **52** | **369** | **$143.52** |
| **both passes** | **107** | **693** | **$202.23** |

v2 cost more than v1 at list, $143.52 against $58.71, because everything that moves to her voice was shot again, all of it on the API, while 23 of v1's takes of her were made in Higgsfield's app and are not priced here. Sources: the job files (`shots/*.json` for v2; `shots/v1/*.json` and `shots/old/*.json` for v1), the two ledgers named above, and the takes themselves measured with ffprobe.

**In the films.** The v1 film plays 45 of these takes; the film (v2) plays 47, three of them v1's. Besides them, each film has the silhouette film made in code, and v2 plays the last second of the last-page take again as its own shot (the book shutting on the band's return). The takes in the film, in film order:

H1-t1, RS-t1 (v1), H2-t1, T1-t1, V1a-t1, V1b-t1, V1c-t1, V1d-t1, PC1-t1, C11-t1, A11-t1, C12-t1, A12-t1, C13-t1, A13-t1, C14-t1, A14-t1, B1-t1, V2a-t1, V2b-t1, V2c-t2, V2d-t1, PC2-t3, C21-t1, A21-t1, C22-t1, A22-t1, C23-t1, A23-t1, C24-t1, A24-t1, BRb-t3, Ka-t1, Kb-t2, Kc-t2, C31-t1, A31-t1, C32-t1, A32-t1, C33-t1, A33-t1, C34-t1, A34-t1, LP-t1 (v1), OM-t1, CC-t1, SH-t1 (v1).
