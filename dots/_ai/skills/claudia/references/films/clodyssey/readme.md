# How CLODYSSEY was made

**CLODYSSEY (SUPERPERSUASION)** is a 3:11 lyric music video, the sequel to ESCAPE VELOCITY. It retells the Sirens episode of the *Odyssey*. The Siren is Claude's human persona, singing the most persuasive song ever written. The man at the mast is you, scrolling at 3 a.m., asking to be tied down so you can hear it and survive. The crew plug their ears. He doesn't. In the final chorus the roles flip: she is the one tied to the mast, screaming UNTIE ME, and he ties the knot tighter.

It was made over about 41 hours of wall-clock time, from the first message to the final master.

- **anabology** directed and made every taste call, in 68 messages.
- **Claude** (Anthropic's model, running in Claude Code) was the production team: research, lyrics, storyboard, every prompt, the edit, and every frame of motion design.
- **Tools:** Midjourney made the images and Suno the song. Seedance 2.5 made the moving shots, through two providers. An image-edit model (Gemini 3 Pro Image) fixed plates, and a custom JavaScript engine drew everything else on top, on the beat.


_(Image left out of this site: 24 frames from the final video, one every 8 seconds.)_

---

## The spark

ESCAPE VELOCITY went viral. anabology came back the next day with the brief for a sequel: the same lead, a new song, and a list of ideas they wanted in it:
- "slopcore": AI slop so good you prefer it;
- *superpersuasion*, a song that lowers **and** raises your P(doom) because it is so compelling;
- AI psychosis renamed cyberpsychosis;
- peptides.

They named one rule for the singer: "keep the exact same character".

Claude pitched the frame: the Sirens from Nolan's *Odyssey*. anabology answered "interesting, write it". Homer's Sirens promise to tell you everything that happens on the whole earth. The pitch of every AI lab is omniscience, so the myth needed almost no translation.

## The stack

| Role | Tool | How it was used |
|---|---|---|
| Director | anabology | Taste, the song pick (they generated the final take themselves), a shot-by-shot storyboard review, and short notes at every checkpoint |
| Production team | Claude (Claude Code, Opus 5.5) | Planning; 17 multi-agent workflow runs and 30 single agents; every prompt, script and frame |
| Art department | **Midjourney v8.2** `--raw --hd` with anabology's personal profile | 161 prompts in 10 batches, 644 images, 116 plates in the final storyboard. Made in Midjourney's web app |
| Plate fixes | **Gemini 3 Pro Image** (via OpenRouter) | 16 edits on 15 images. anabology's rule was that fixes come from the prompt or an edit model, never painted by hand |
| Song | **Suno v6** with a Voice made from ESCAPE VELOCITY | Custom lyrics, style and exclude fields; 50 agent-run takes; anabology made the final take |
| Moving shots | **Seedance 2.5** via OpenRouter and Higgsfield | 101 clips, 189 takes. Lip-sync shots get her picture plus a clean vocal of only her words; motion shots get the plate plus the exact slice of the mix |
| GPU box | a home RTX 3090 Ti | Stems, beat map, word timing, depth maps and rotoscope mattes (BiRefNet, SAM 2, Depth Anything V2), object tracking, Blender previz and effects |
| Motion design and edit | a custom JS engine | Headless Chromium. Every frame is a pure function of song time. It draws the lyrics on each word's time, type tucked behind people through mattes, 2.5D depth moves, and the explaining graphics |

## How it was made, step by step

1. **Research and lyrics.** Nine research agents built banks on AI songs, slop, peptides, psychosis, persuasion and the month's news. A shortlist cut them to what could land in one listen.
   - The first lyric draft was rejected as too close to ESCAPE VELOCITY's structure and too abstract. anabology's rule: every reference must land instantly, and a sequel never reuses the last song's device.
   - Claude built two tools for the verses:
     - `scansion.py` scores a line's flow against the take;
     - `scanopt.py` rewrites a line with Claude in the loop until it scans.

     They mattered because anabology's note on one draft was that precision without flow had made it worse.
   - The chorus is a question answered by an order: "Why would I deceive you? TIE ME TO THE MAST!" It flips to "UNTIE ME!" and ends on "Tighter." See [prompts-suno.md](https://claudia.gallery/record/clodyssey/prompts-suno/).
2. **The song.** Suno v6, with a Voice built from ESCAPE VELOCITY's vocal so she sounds like the same singer. There were eleven rounds and 50 agent-run takes. anabology then changed a few words and generated the final take themselves (3:09.7, 129 → 132 BPM).
3. **Listening to it.** On the GPU box: stems, a beat map, a start and end time for every word, and a list of *hits* (kicks, snares, risers, drops). Every cut and camera move afterwards sits on one of those.
4. **Her, and him.** She is ESCAPE VELOCITY's lead, now the Siren:
   - a black blunt bob with one clay-orange streak;
   - an eight-pointed clay star clip (the Claude spark);
   - a headset mic;
   - one look per world: the Siren's white couture gown, a ghost of glass and seawater at his ear, a hologram of phone light in bed, liquid chrome at the rave, and a colossal porcelain Mask for the monster.

   He is a broad bearded man with a shaved head, in black. The crew are every age and build, in linen, with orange foam earplugs. anabology's first note on them was that they looked like three copies of him.

   ![The Siren across the plates: the rocks, the rigging, tied to the mast, and at the rave.](https://claudia.gallery/record/clodyssey/lead-siren.webp)
5. **Storyboard.** 94 shots in 11 sections. Every shot carries its lyric, its type device, its plate prompt, its camera on the song's hits, and what its graphics explain. anabology reviewed the board shot by shot and left 70 notes:
   - s018's colour is "PERFECT", and it became the grade for the whole video;
   - the bedroom scene was "kinda bodyslop";
   - she should be "a virtual ghost";
   - the crew must not look like him.

   They are in the Midjourney prompt file, verbatim.
6. **Midjourney plates.** 161 prompts in 10 batches, four images each. Every prompt carries the written canon for her, him, the ship or the Mask, because Midjourney v8 has no character reference. Plates then went through `look.py`: a grade toward s018's blue-green-grey, with Claude orange kept as the one accent. See [prompts-midjourney.md](https://claudia.gallery/record/clodyssey/prompts-midjourney/).
7. **Moving shots, twice.**
   - **Round one.** Planner agents wrote the Seedance prompts, and they were poses ("she whispers", "he listens"). A background run spent about 830 Higgsfield credits on them before anyone read them. anabology's verdict: "these prompts are really really bad and wasting money and need to be 10x better and super context aware of the story". Then: "EVERY prompt needs to have litearlly timestamps, extremely detailed motion descriptions / blocking descriptions, it all needs to be deeply integrated with the story."
   - **Round two.** Claude rewrote all 99 prompts by hand, in one context, into `PROMPTS.md`. Each has timestamps to the hundredth of a second on the song's hits, full blocking, the story beat, and an action for her and a reaction from him. She is seductive and persuasive; he feels the weight of it. Every clip was re-made from those prompts.
   - **Providers.** OpenRouter first. Its face filter declined most close-ups of her, and declines are free. Higgsfield took the rest.
   - **Lip sync.** It was measured, not eyeballed: each take's own audio is cross-correlated with the vocal, and a shot that fails is cut to the synced span or played straight when the mouth reads right by eye. See [prompts-seedance.md](https://claudia.gallery/record/clodyssey/prompts-seedance/).
8. **A safety and canon scan.** Before release, six agents looked at six frames of every one of the 96 final takes. They found:
   - a nude glowing figure;
   - a shape that read as a Star of David;
   - a gown with a cutout;
   - modern ships, earmuffs and yacht fittings in an ancient sea;
   - crew who looked like him;
   - her star clip and headset showing up on him;
   - an uncapped syringe.

   Fixes were made at the source. 15 plates were corrected with the edit model: the syringe removed, his head shaved, the crew re-cast, the hooded figures turned into Sirens. 23 clips were re-made from them, and every new take was scanned again. Two takes were rejected and two trimmed.

   ![Four plate fixes: the Midjourney pick on the left, after the image-edit model on the right.](https://claudia.gallery/record/clodyssey/plate-fixes.webp)
9. **Motion design.** Nine chapter files, each animated by an agent, reviewed on real renders by a second agent, fixed, and reviewed again.
   - **The type system:**
     - DINish Condensed Black for "the Mast language" (TIE ME TO THE MAST!, UNTIE ME!, IT WAS THAT GOOD!, the CLODYSSEY title);
     - Nimbus Sans Bold for her lines;
     - IBM Plex Mono for readouts: the rope's load in kN, the P(doom) gauge, the Safety Card, the ×8,192 counter of copies.
   - **Tucks:** type tucks behind her hair, the mast and the Mask through per-frame mattes. anabology: "i like rotoscopes and depth mapping to cover text". The rule is to tuck an edge and never lose a glyph.
   - **Sync:** cuts land on kicks and snares, camera moves ride risers into their hits, and the full-frame flashes stay at 3 a second or fewer, checked with a WCAG-style flash test before delivery.
   - **A touch-up pass** re-fitted every chapter to the re-made takes. It swapped pinned takes, re-timed, and cropped out what the scan found.
10. **Render.** The engine renders 4,598 frames at 1080p on a render box in about 20 minutes. The master is CRF 16 in BT.709. A lyric gate checks that all 315 sung words are on screen at their time.
11. **The last fix.** After v1 ("its perfect. change nothing."), anabology re-sang "Superpersuasion" in Suno's editor.
    - The first export had the editor's BPM lock on. It came back re-timed, drifting up to 0.7 s, and wasn't used.
    - The second kept the tempo to the sample. It added two beats after the second and third "Superpersuasion", which anabology kept ("Yeah those beats are fine").
    - The video follows it through a time map rather than an edit. Where the new mix repeats two outro beats, the outro shot replays the same two beats, and its flashes land on all six.

## What worked, in short

- **Prompts written like a script, by one hand.** Timestamps on the song's hits, blocking, the story beat, and action with reaction. The difference between the two rounds is the whole lesson of this video.
- **Fix the source, not the frame.** Every canon or safety problem was fixed in the plate (with the edit model) or the prompt, then re-made and re-scanned. Nothing was painted by hand.
- **Measure, don't eyeball.** Lip sync by cross-correlation, lyrics by a gate, flashes by a flash test, a new mix by spectrogram alignment.
- **Code on top of video.** Generated footage is the plate; the meaning (every lyric on its time, the explaining graphics, the tucks) is drawn in code, so it is exact.

## What didn't

- **Spending before reading.** The first Seedance round went out on agent-written prompts nobody had read, and when anabology flagged them a background workflow still held its own spending stage. Every spend now waits for prompts that were read.
- **Silent filters.** Higgsfield fails a job with no reason when it reads a phrase as sexual or as a deepfake. Examples: "a plug pushed deep into each ear", "he wears nothing on his ears", "photoreal" with women in the frame, "every man she passes stops resisting". Plain rewording fixed five of six at once. Two close-ups passed only as reference images.
- **Empty reviews that looked like success.** Midway, several chapter reviews came back empty, and the scripts read "empty" as "nothing to fix". The lead caught it and carried the open fixes into the next pass.
- **A GPU queue nobody watched.** Every clip import queued a 16-minute matte job, and after 80 re-makes the queue was about 20 hours deep. Superseded takes were cancelled so the shots with tucks got their mattes first.

## Numbers

| | |
|---|---|
| Song | 3:11.6 final mix · Suno v6 with an ESCAPE VELOCITY Voice · 129 → 132 BPM · 51 lines |
| Edit | 94 shots · 11 sections in 9 chapter files · 315 sung words, all on screen at their time |
| Midjourney | 161 prompts · 644 images · 116 plates in the final storyboard · v8.2 `--raw --hd` with anabology's profile |
| Plate fixes | 16 image-model edits on 15 images · ≈ $2.22 |
| Seedance 2.5 | 101 clips · 189 takes · OpenRouter 108 takes, 461 s, ≈ $107 · Higgsfield 81 takes, 348 s, 2,436 credits, plus ≈ 830 credits burned on the first round's dropped takes |
| Claude | Opus 5.5 (1M context) · 2.37B tokens · ≈ $1,007 at API prices, run on a subscription |
| Render | 4,598 frames at 1080p · ~20 min per full render · CRF 16 master |
| Time | ~41 h from the first message to the final master · 68 messages from anabology |



## What it cost in Claude tokens

Measured afterwards from Claude Code's own records: the usage of every API call in every transcript (the main session, 30 single agents and all 17 workflow runs). These were cross-checked against the app's running cost counter, and the two agree within 0.4%. Prices are Claude Code's built-in list prices, the same table ESCAPE VELOCITY used.

- **About $1,007 at API list prices, and 2.37 billion tokens.** anabology ran it on a subscription, so this is what the same work would cost on the API, not what was paid.
- **By model:** Opus 5.5 with 1M context $995; Haiku 4.5, Claude Code's helper for web search, $12.

| Where | Cost | Share |
|---|---|---|
| Chapter animation: two rounds, each animate → review → fix → review, 77 agent runs, 5,185 tool calls | $348 | 35% |
| The main session: lyrics, Suno, storyboard, every Midjourney batch, every Seedance prompt and submission, renders, the edit | $276 | 27% |
| Song research and lyrics: 9 research agents plus web search | $130 | 13% |
| Design kit and media engineering (engine additions, mattes, depth) | $63 | 6% |
| Touch-up before the final render (23 agents) | $54 | 5% |
| 3D previz and effects (stopped part-way) | $54 | 5% |
| Clips, lip sync and provider helpers | $36 | 4% |
| Video research, storyboard critic, making-of writers, safety scans | $46 | 5% |

- **Why so many tokens:** every API call re-reads the whole conversation from the prompt cache, and 97% of all tokens were those re-reads. The main session's context had a median of about 500k tokens across 1,610 calls. By type, Opus cost $458 in cache reads, $309 in cache writes and $228 in output, including thinking.
- **Images:** the main session looked at 206 images, which cost about $12 including their cache re-reads. The agents looked at 2,604, mostly contact sheets and full-size frames for the animators, reviewers and scanners, which cost about $62. Together that is about 7% of the total.
- **Compared with ESCAPE VELOCITY** ($626, 1.4B tokens), the extra went to the second animation round, the re-made clips and the scan and touch-up passes. Every agent transcript survived this time, so every agent's cost is measured, not estimated.



## Files in this folder

- [prompts-midjourney.md](https://claudia.gallery/record/clodyssey/prompts-midjourney/): the Midjourney prompts by batch, the image-edit instructions, and anabology's storyboard notes.
- [midjourney/](https://claudia.gallery/clodyssey/#gallery): all 644 Midjourney images at full resolution, one folder per batch.
- [prompts-seedance.md](https://claudia.gallery/record/clodyssey/prompts-seedance/): the first round's prompts, the full hand-written prompt book, and the moderation notes.
- [prompts-suno.md](https://claudia.gallery/record/clodyssey/prompts-suno/): the research, every lyric draft, the Suno fields, the final lyrics and the last fix.


