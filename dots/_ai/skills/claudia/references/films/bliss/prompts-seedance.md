# Seedance 2.5 — every clip prompt (BLISS)

Model: **Seedance 2.5** (`bytedance/seedance-2.5`) through **Higgsfield's pay-per-generation API**, in two modes: reference-to-video for her singing heads and her performances, image-to-video for the full-frame plate shots. All clips are 16:9 and 4–10 s long. The green-screen performances and the singing heads that become window inserts are 720p. The full-frame shots are 1080p: the 13 plate shots, R07, and the singing heads W05 and W06.

**One provider.** OpenRouter had been ESCAPE VELOCITY's provider, and anabology had just said EV's lip sync beat CLODYSSEY's, so OpenRouter got one test:

- In the three-clip pilot, Higgsfield's first lip-sync take, W02, sang about a second late (measured lag +0.96 s) and matched the vocal for only 1.7 s.
- The lead sent the same window, with the same prompt, image and vocal, to OpenRouter as W02o. OpenRouter's face filter declined the reference at submission. Nothing was generated or charged.
- ESCAPE VELOCITY's own takes, looked up next, showed the same pattern: short spans in sync, then covers. So the full run went ahead on Higgsfield.

No clip in the video came from OpenRouter, and nothing was spent there.

**Four kinds of clip:**

- **Singing heads (W01–W06), 6, reference-to-video.**
  - `@Image1` is the Midjourney plate of her, unaltered.
  - `@Audio1` is a clean vocal of only the words she sings in that window, cut from the vocal stem by `prompts.py`.
  - The prompt opens with those words, quoted: `@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "…"`
  - Seedance's own soundtrack stays on. It copies `@Audio1`, the mouth follows it, and the sync check reads it.
- **Performances (R01–R17, R07G, R07H), 19, reference-to-video.** Her dancing and acting for the desktop, mostly full length on chroma green, so that she can be matted onto the taskbar like the old desktop-dancer programs.
  - `@Image1` is the plate. `@Audio1` is the slice of the song's mix that starts on the clip's first frame, so she moves on the beat.
  - The pipeline puts "The scene from @Image1, moving in time with @Audio1." in front of each prompt. The prompts below include it, as sent.
  - All but R07 and R07H say her mouth stays closed; R13 adds "apart from the kiss".
  - The exceptions: R13 is a close-up against a blue sky, R16 and R17 use their plates' studio backdrop, and R07 is image-to-video from a full-frame plate on the hill.
- **Plate shots (P01–P13), 13, image-to-video.**
  - The plate is the exact first frame, so the prompt calls it "the image".
  - They are silent. The song goes on in the edit.
  - Where code is drawn onto the plate itself, such as the CRT's screen in P01, the camera is locked.
- **Lip-sync covers (W01-c1 to W06-c3), 12.** The runner made these when a singing head stopped matching her vocal.
  - `@Image1` is the parent's frame at the point it diverged.
  - `@Audio1` is her vocal from the word gap before that point.
  - The prompt is the parent's, with the quoted words cut to the ones left.

**How the inputs are cited.** Higgsfield's API documentation, read, lists arrays of reference images, videos and audio, but gives no syntax for citing them in the prompt. The prompts kept ESCAPE VELOCITY's and CLODYSSEY's convention, `@Image1` and `@Audio1`, and the takes followed it.

`@Audio1` always starts on the clip's first frame. So the times written into the prompts are the song's real beat and word times, counted from the clip's start, on the kick grid: beat n falls at 0.4542 + n × 0.4615 s.

**Provider details that shaped the work:**

- **Price.** List price, as recorded in `hfapi.py`: $0.4622 per second at 720p and $1.1372 at 1080p, for 16:9 with no video input. A 4 s clip is $1.85 at 720p and $4.55 at 1080p. Image and audio references cost nothing extra. A video reference is billed for its own seconds at the same rate.
- **Lag.** Takes come back late against their audio. On the singing heads and covers the measured lag ran from +0.03 to +0.97 s. The edit removes it: clip time = song time − the clip's start + the lag.
- **Refunds.** A blocked job is refunded, and the runner logs each refund in the ledger.

## Totals

Measured from two sources:

- `shots/ledger-hf.jsonl`, the Higgsfield ledger: one line per submission, with its list-price estimate, and one per refund.
- The 51 clip records in `shots/*.json`: 50 Higgsfield clips plus W02o.

The four `A-*.json` records are Midjourney Animate shots, not Seedance. They are with the Midjourney prompts.

| | Submissions | Seconds | List price |
|---|---|---|---|
| Submitted | 54 | 267 | $182.14 |
| Blocked, refunded | 4 | 18 | $8.32 |
| Takes with footage | 50 | 249 | $173.82 |

| Kind | Clips | Submissions | Seconds | List price | Blocked |
|---|---|---|---|---|---|
| Singing heads W01–W06 | 6 | 6 | 31 | $20.40 | 0 |
| Lip-sync covers | 12 | 12 | 48 | $30.29 | 1 (W01-c3) |
| Performances R01–R17, R07G, R07H | 19 | 23 | 128 | $63.21 | 3 (R14 once, R16 twice) |
| Plate shots P01–P13 | 13 | 13 | 60 | $68.23 | 0 |
| **Total** | **50** | **54** | **267** | **$182.14** | **4** |

| Round | Submissions | List price |
|---|---|---|
| The pilot, one of each kind: W02, R01, P04 | 3 | $13.54 |
| The full run: the other 33 clips and 12 covers, capped at $170 | 45 | $151.95 |
| After the blocks: R14 and R16, re-worded | 2 | $4.62 |
| After the first art reviews: R01 (headroom) and R06 (the streak) | 2 | $7.40 |
| The re-shoots on green: R07G and R07H | 2 | $4.62 |

- **Endpoints and resolutions:** 40 reference-to-video and 14 image-to-video submissions; 35 at 720p and 19 at 1080p.
- **The plan:** the clip files came to 36 clips, about $135 at list before covers. Their first takes cost $135.21. The rest is the 12 covers ($30.29), four re-rolls ($12.02) and the two re-shoots ($4.62).
- **Clips with footage:** 48 of 50. R16 was blocked twice and W01-c3 once.
- **In the cut:** 43 clips.
  - They are 13 lip-sync clips (the six heads and seven covers), 17 performances and the 13 plate shots. P05 survives only as a small window in s034, and W02-c3 appears for one frame, the last of s007.
  - The cut doesn't use R07 (replaced by R07G), R01's take 2, R06's take 1, or the covers W02-c1, W04-c2, W04-c3 and W06-c2. Together they cost $24.31 at list.
- **Money:** these are list prices.
  - The records hold list prices only; what was actually charged is not recorded.
  - The runner stops before a submission would pass its cap: $170 for the full run, a few dollars for each re-roll, and $195 for the project (`project.json`).
- **OpenRouter:** one request (W02o), declined at submission: $0.
- **Higgsfield's MCP connector** made no clip; every record names the API.

## How the prompts were written

The bar was CLODYSSEY's. After that video's first round of agent-written prompts, anabology wrote: "EVERY prompt needs to have litearlly timestamps, extremely detailed motion descriptions / blocking descriptions, it all needs to be deeply integrated with the story". For BLISS:

- **One hand, one pass.** The lead session wrote every prompt itself, in one context, with no sub-agents.
  - The 36 prompts of `PROMPTS.md` (48 KB) went into the file, after storyboard draft 3 and the plate picks were done. The three-clip pilot went out a minute later.
  - R14's and R16's rewordings, the R01 and R06 re-roll edits and the two re-shoots were added the same way later that day.
  - `prompts.py apply` carried each block into its clip record. For the singing heads, it also cut the clean vocal window.
- **Who read the book first.** anabology had said "i believe in you - complete the whole thing", so the book was not shown to them before the run. It was finished before any money was spent, and the lead's three-clip pilot was the check before the other 45 submissions.
- **What every prompt contains**, in the book's own list: "timestamps, blocking, the story beat, action and reaction, the environment, the camera on the hits, the mouth rules".
  - The timestamps are clip time on the kick grid. Each performance starts on a bar line, so any bar of a dance can loop under later shots.
  - The story beat is one sentence, such as R02's "She once loved a mouse pointer, and she remembers him fondly, with no regrets."
  - The mouth rules: every singing head ends "Only she speaks", and the performances say "Her mouth stays closed" (all but R07 and R07H).
- **Identity is text**, ESCAPE VELOCITY's lesson.
  - The long form, for close and medium shots, carries the black blunt jaw-length bob, one clay-orange streak through the bangs, the eight-pointed clay star clip and the thin headset mic.
  - A short form serves full-length shots and leaves out the star clip. Chapter 04's art review found the clip missing in R07, P05 and R08, and the re-shoots R07G and R07H put it back.
- **No brand or product names**, in the book's words: "No brand or product names (no operating system, no paperclip): the desktop is "a 2001 computer desktop"."
- **Room for code.** Everything XP is drawn in code afterwards: the windows, the cursor, the giant arrow.
  - So the prompts give her something to play against without drawing it: "something enormous just out of frame to the right", "an invisible, very tall partner who leads her", "flicking one hand out sharply on every half beat … as if snapping shut little windows in the air beside her".
  - Every performance shot on green or on a studio backdrop ends "Nothing else enters the frame."
- **Measured:** 38 prompts in the book, 67 to 311 words long (median 184.5). Every one is timestamped, with 1 to 7 timed beats. The median by kind is 242.5 words for the singing heads, 203 for the performances and 102 for the plate shots.

### The XP engine as a video reference: planned, not done

anabology's direction, verbatim: "this is where you can build the desktop environment of windows xp with bliss - it might behoove you to actually build something like that by hand and tool it for motion design and stuff, and then you can use that for video references to seedance with like video conditioning of motion design upfront rather than image conditioning."

The same message offered a second route: "e.g. if shes a desktop dancer , those back then would  be on a green screen and was cut out  and youd just have her dancing on teh taskbar- eitehr can do seedance with teh full frame set up at the start or can do a video and rotoscope her from the vid and place her on the taskbar. multiple ways to do this."

- **Planned.** The XP engine was built to render each shot three ways: as a storyboard still, as an MP4 "for Seedance video conditioning", and as the final UI layer. Storyboard draft 2 had a method for it, `vref`: "Seedance conditioned on a motion-design previz rendered by the XP engine (video reference) plus the plate". Draft 2 used it on three shots: s012 (the giant cursor), s013 (partners) and s041 (the last dance).
- **Not done.** Draft 3, written just before the clip files, dropped `vref`. Its methods are code, roto (a green-screen take, matted), plate, lips and Midjourney Animate.
  - No BLISS submission carries a video. 37 clip records give an image and an audio reference, 14 give a first frame only, and no submitted body has a `video_urls` field.
  - The records don't say why. One cost fact from `hfapi.py`: on this API a video reference is billed for its own seconds at the output rate, while image and audio references cost nothing extra.
- **What was done instead** is the green-screen route from the same message.
  - Seedance performs her alone, on green, to the song. The engine draws the cursor, the arrow and the windows around the matted sprite, timed to her moves.
  - The fight (s012) and the ride (s013) ended up that way too, after their first-frame versions failed review (see *Re-rolls and re-shoots*).

## Lip sync

anabology's method, verbatim: "EV had better lip sync btw than clodyssey, overall its use seedance and check spectrograms and see where audio aligns and see if / when it diverges and cut when the spectrogram matching diverges enough"

The runner (`seedance.py`, with `avsync.py`) is ESCAPE VELOCITY's, pointed at a new provider:

1. **The check is an audio check.** Seedance copies `@Audio1` into its own soundtrack almost sample for sample, and the mouth follows that soundtrack. So the take's soundtrack is compared with the vocal it was given.
2. **The comparison.** `avsync.py` finds the lag, then compares the two every 10 ms in two ways:
   - waveform correlation, where a verbatim copy scores 0.6–1.0;
   - the similarity of their log-mel spectra, against a threshold calibrated on deliberately misaligned copies.

   Spans that match are in sync. The point where they part and never recover is the divergence.
3. **Cut and cover.** The take is kept up to the last eighth note before the divergence. A cover is generated for the rest: it starts in the word gap before the cut, from the take's frame at the cut, with only the words left. There were up to three covers per window.
4. **What covers can't hold** is recorded as a `fallback` span for a lip-sync model. This is anabology's rule from ESCAPE VELOCITY, verbatim: "you could just create a cut and make another clip to cover desyncs. and that would work for evcerything w seedance tbh, and we use syncing models as backups if that fails a couple times". For BLISS no lip-sync model was run. The edit cut away from her face or let the span play.
5. **The edit** (`edl.py`) plays each window in song time, moment by moment, from whichever take or cover is in sync there.

What it measured, from the sync records in `shots/*.json` and the run log. "Sung time held" sums her aligned word durations inside the measured in-sync spans.

| Window | Her words | Takes | Take's lag | Held in sync | Not held | Sung time held | In the cut |
|---|---|---|---|---|---|---|---|
| W01 · s001 | "Welcome back." | 1 + 3 covers (c3 blocked) | +0.91 s | nothing | all of it | 0 of 0.84 s | the chain plays in her small account tile |
| W02 · s007 | "It looks like you're trying to go outside. Would you like help?" | 1 + 3 covers | +0.96 s | "It looks like you're trying" (the take, 0:30.76–0:32.46); "go" (W02-c2, 0:32.82–0:33.47) | "to", "outside", "Would you like help?" | 1.55 of 3.31 s (47%) | the chain; her face is a held frame from 0:35.79 |
| W03 · s021 | "That's my happy place. Yours is out there. Go." | 1 | +0.03 s | "my" to "Go" (1:25.68–1:28.47) | "That's" | 1.58 of 1.84 s (86%) | the take, matted in front of the hill |
| W04 · s022 | "It looks like you're trying to be happy. Would you like help?" | 1 + 3 covers | +0.61 s | "It looks like you're trying" (the take, 1:29.92–1:31.40); "happy" and "Would you" (W04-c1) | "to be", "like help?" | 1.95 of 3.00 s (65%) | the take, then W04-c1 from 1:32.12; cut away at 1:35.10 |
| W05 · s029 | "I can't touch grass." | 1 | +0.58 s | the whole line (2:00.77–2:01.89) | — | 0.77 of 0.78 s (99%) | the take |
| W06 · s037 | "Bliss is a real place" | 1 + 3 covers | +0.03 s | "Bliss is a real" (the take, 2:30.89–2:32.74) | "place" | 1.52 of 2.16 s (70%) | the take, W06-c3 through "place", W06-c1, then the take again from 2:34.61 |

Over the six windows, 7.37 of 11.93 sung seconds (62%) are held in sync by measurement. Window by window:

- **W01.** No span of the take or its two delivered covers matched. The covers couldn't have fixed it anyway (see *The lip-sync covers*). The line plays on unsynced footage in the tile, about 290 px square in the 1080p frame, until the tile flies into the tray at 0:03.69.
- **W02.** The helper's face follows the chain: the take until 0:32.82 (in sync to 0:32.46), then W02-c2.
  - The edit list carries W02-c2 to 0:36.61 and the take after that. But it measured where each clip's footage ends without the clip's lag, and W02-c2's footage, 0.97 s late, ends at 0:35.74.
  - From 0:35.79 her face is a held frame through "Would you like help?" (sung 0:35.52–0:36.74). Measured on the delivered render, her face changes by less than 1.2 grey levels per frame, against 12–25 in the half second before, while W02-c2 still plays.
- **W04.** Chapter 06 cuts from the take to W04-c1 in the word gap after "be" (1:32.12). It skips the gap after "trying", where W04-c1's first half second is Seedance's start blur. At 1:35.10 the helper minimizes into her own palm and becomes the cursor, just before the unheld "like help?" (1:35.13–1:35.87). That is the cut-away.
- **W06.** No take held "place" (2:33.44–2:34.08). After it, W06-c1 turns into a melting chiffon smear that ends on her back. So on beat 334 (2:34.61) chapter 08 cuts back to the take at 3.35 s, where she turns back to the lens, smiling.
- **The performances** were checked the same way, for timing only. Of 19 checked takes, 9 copied the mix within 0.1 s, 3 within 0.31 s, and 7 were 0.39–0.83 s off (R01's two takes, R06's take 2, R09, R10, R11, R14). The chapters set each dancer's clip time by eye, so that her accents land on the beat.

## Re-rolls and re-shoots


- **R14 and R16.** Both were blocked in the full run, and both were re-worded and resubmitted. R14 passed. R16 was blocked again and dropped (see *Moderation notes*).
- **R01 and R06.** The first art reviews, round 1 of the chapter workflows, flagged two dancers.
  - **R01**, chapter 01: "her raised hands go out of the top of the frame at clip 0.70–2.83 s (frames 18–69 = song 6.70–8.83)".
    - The re-roll asked for "generous headroom".
    - The lead's verdict: the new take was stiffer, and its hands still touched the top at about 1.5 s, so take 1 stayed.
    - Chapter 01 masks the top band, and chapter 02 plays take 1 from a +2.769 s in-point.
  - **R06**, chapter 03: "No clay-orange streak in any frame (R01-t1, the same holo look, has it)".
    - The re-roll stated the streak twice: "ONE bright clay-orange streak through the front of the bangs, clearly visible the whole time".
    - The lead's first look found no streak in either take and kept take 1. `PROMPTS.md`: "Take 2 has no streak either and adds white wall panels behind her: **take 1 kept**."
    - Chapter 03's fixer, in the same round, then switched: "R06-t2 is now the dancer. It was matted […] while I worked, and it has her clay streak." The cut uses take 2: its kick frame (frame 72) matches the render, and take 1's doesn't.
    - Checked on the frames: take 2 has an orange lock at the side of the bob in some frames (30, 72), not through the bangs. Take 1 has none.
- **R07G and R07H: the drop re-shot on green.** Chapter 04's art review, verbatim:
  - R07: "off-brief. It is a handheld close-up instead of the prompted locked low wide, because its start plate her-fight-trench is a face close-up. The back-kick (clip time 2.31 s) is never in frame, dark overhead masses fill f58–f106, and a blurred real human hand appears in f97–f99. Retake it as the storyboard's roto: chroma green, full-length, locked camera."
  - P05: "the arrow is a symmetric white road-sign arrow with no black outline, not the XP pointer from s012. Frames f37–f97 are nearly static, with no downhill slide."

  Later, the ledger stood at $177.51 of the $195 cap, enough for targeted re-shoots. R07G re-shot the fight and R07H the ride, both on green from other Midjourney candidates of `her-trench-pose`, both with the star clip back in the text. In chapter 04 the code arrow is drawn around them: R07G squares up to it on the wallpaper hill, and R07H, mirrored, rides it down the photo's flank. Each got one take, $4.62 at list for the two.

## The prompt book

This is `PROMPTS.md` in film order, by the song's sections, with each prompt exactly as it was submitted (taken from the clip records). Each heading reads: clip · storyboard shots · song time · clip length (· resolution when 1080p).

- **role** says what the clip is for.
- **inputs** names the plate and the reference audio with its song window. The plates are Midjourney images, unaltered.
- **story** is the note the prompt was written from, as in the book.
- **outcome** gives the takes and what the cut uses.

Performance prompts start with the pipeline's prefix, which is not in `PROMPTS.md`; everything after it is the book's text. Where a clip's two takes had different prompts (R01, R06, R14, R16), the entry gives the book's prompt, which made the second take, and quotes what the first take said instead (for R14 and R16, under *Moderation notes*). The outcome says which take is in the cut. The prompts are unedited for publication.

## Intro · Verse 1

### W01 · s001 · 0:00.00 · 4 s
- **role:** singing head for lip sync: her live account tile on the Welcome screen.
- **inputs:** @Image1 `her-tile` (a square beauty portrait) · @Audio1 her vocal, 0:00.00–0:04.00, only "Welcome back."
- **story:** the login screen: her account picture is live, and she greets you like an old friend who has been waiting.
- **outcome:** one take: lag +0.91 s, no span in sync. Three covers followed, and none held the line (see *The lip-sync covers*). The cut plays the chain in the tile.

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "Welcome back."
A square beauty portrait come to life, like a live webcam picture on a computer's login screen: the woman from @Image1, a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone at her cheek, a glossy apple-green leather blazer, clay-orange tinted shield sunglasses pushed up on her head, against the same pale blue backdrop. She is the computer greeting you, warm and amused, like an old friend who has been waiting for you to come back.
0.0–0.04 s: she looks straight into the lens with a small knowing smile.
0.04–0.6 s ("Welcome"): she sings it softly to you, her eyebrows lifting.
0.92–1.2 s ("back"): she finishes the word with a warm smile and a tiny tilt of her head.
1.2–4.0 s: she holds your gaze, smiling; at 2.5 s she glances down and to the right as if watching something load beside her, then looks back to the lens and winks at 3.5 s. Her mouth stays closed after "back".
Locked camera, head and shoulders framed as in @Image1, soft even studio light. One continuous shot, no cuts. Only she speaks. No text, letters or logos.
```

### R01 · s002 s003 s034 s038 · 0:05.99 · 10 s
- **role:** desktop-dancer performance on green: she materialises on your taskbar ("Found New Hardware"), and bars of the routine loop under later shots.
- **inputs:** @Image1 `her-holo-dance` (full length, on green) · @Audio1 the mix, 0:05.99–0:15.99 (the intro's last bar, then the filtered verse)
- **story:** the desktop dancer: she materialises on your taskbar, wakes up, catches the beat and performs a happy routine just for you. The routine is beat-locked from a bar line, so any bar of it can loop under the later shots.
- **outcome:** two takes, and take 1 is in the cut. Its raised hands leave the top of the frame at clip 0.70–2.83 s, and the cut masks the top band. The re-roll was made from the prompt below, the book's. It was stiffer, and its hands still touched the top. Take 1 opened instead: "Full-length shot, head to toe with her feet always in frame, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, …"

```
The scene from @Image1, moving in time with @Audio1. Wide full-length shot with generous headroom: the woman from @Image1 fills only the middle two thirds of the frame height, so her raised hands and her platform boots always stay well inside the frame. She is a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak clearly visible in the bangs, a thin black headset microphone, in a holographic iridescent silver mini dress with long fluted sleeves and white patent platform boots, on a seamless flat chroma-key green backdrop and floor with even, flat, shadowless light. She is a little dancer who lives on a computer desktop, and she performs a happy, stylish pop routine just for you.
0.0–1.0 s: she appears standing still with her arms at her sides, then stretches both arms up over her head and rolls her shoulders, waking up.
1.0–1.85 s: she nods to the beat and bounces lightly on her heels, finding the groove.
1.85–3.69 s: she dances on every beat (1.85, 2.31, 2.77, 3.23): small side steps and hip sways, the fluted sleeves swinging, a bright smile.
3.69–5.54 s: a shoulder pop on each beat; at 5.08 s a playful point at the lens and a silent giggle.
5.54–7.38 s: a full spin on the spot with her arms out, the sleeves flaring; she lands facing the lens at 6.46 s and does two little hops.
7.38–9.23 s: a groovy step-touch from side to side, snapping her fingers at 7.85 and 8.77 s.
9.23–10.0 s: she freezes in a cute pose, one hand on her hip and one arm up.
She stays on the same spot in the centre of the frame the whole time. Her mouth stays closed; she does not sing or speak. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### P01 · s004 · 0:11.53 · 4 s · 1080p
- **role:** first-frame plate shot, silent.
- **inputs:** first frame `room-desk-pov` (your hand on the ice-blue ball mouse, the ice CRT)
- **story:** "Let go of the mouse": you finally let the computer take over. The camera must not move: the push into the CRT and the dialog on its screen are drawn in code on this plate.
- **outcome:** one take, in the cut. The camera held (0 px drift, by the art review), but the hand lets go at clip 2.5–3.9 s, not 0.3–1.0 s as written. Chapter 01 plays it from a 2.35 s in-point, so the fingers open on "go".

```
First-person view at a white lacquer desk in a 2001 high-fashion minimalist white loft: your hand rests on a translucent ice-blue ball mouse on a green-hill mousepad, beside a glowing translucent ice-blue CRT computer monitor. You are letting the computer take over.
0.0–0.3 s: the hand rests on the mouse.
0.3–1.0 s: the fingers open slowly and the hand lifts off the mouse, palm down, and withdraws out of the bottom of the frame.
1.0–4.0 s: the mouse sits alone on the pad; the screen's soft glow flickers on the white surfaces; the sheer curtains in the background breathe in a light breeze.
The camera is locked and does not move at all; the monitor's picture stays steady. One continuous shot, no cuts. No text, letters or logos.
```

### R02 · s005 · 0:15.22 · 6 s
- **role:** performance on green, waist up, standing behind the taskbar.
- **inputs:** @Image1 `her-start-pose` (waist up, arm raised, on green) · @Audio1 the mix, 0:15.22–0:21.22 (the full beat drops at 0.0)
- **story:** "Cursor was my ex": she plucks the pointer out of the air like a star and looks at it fondly; it becomes her wand; she waves it off to the rocket; "and that's alright": a shrug and a spin. She stands behind the taskbar (waist up).
- **outcome:** one take, in the cut (chapter 02).

```
The scene from @Image1, moving in time with @Audio1. Medium shot from the waist up of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, a glossy apple-green leather blazer with sharp shoulders over a white satin slip, clay-orange tinted shield sunglasses pushed up on her head, on a flat chroma-key green backdrop with even, flat light. She once loved a mouse pointer, and she remembers him fondly, with no regrets.
0.0–0.5 s: her raised hand closes around something tiny in the air above her, plucking it like a star.
0.5–1.4 s: she brings the closed hand down in front of her chest, opens it and looks into her palm with a soft, nostalgic smile, as if holding something small and precious.
1.4–2.8 s: she holds it up beside her face between two fingers and wiggles it like a little wand, mischievous, eyebrows raised.
2.8–3.7 s: her smile fades a little; she looks up and away, wistful.
3.7–4.9 s: she waves goodbye up at the sky with small fingers, as if to something flying away.
4.9–6.0 s: she shrugs both shoulders with a breezy smile and spins once on the spot, ending facing the lens.
Her mouth stays closed; she does not sing or speak. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### R03 · s005 · 0:16.61 · 6 s
- **role:** performance on green, seated on Notepad's title bar.
- **inputs:** @Image1 `her-start-sit` (cross-legged with a keyboard, on green) · @Audio1 the mix, 0:16.61–0:22.61
- **story:** "We vibe coded every night": 2:47 a.m., she sits on top of the Notepad window typing with her old flame, happy and a little sleepy; then she watches him leave.
- **outcome:** one take, in the cut. Its matte left her shoes and feet half-transparent, so the sprite was given a solid core.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, a glossy apple-green leather blazer over a white satin slip, clay-orange tinted shield sunglasses pushed up on her head, sitting cross-legged with a black keyboard in her lap, on a flat chroma-key green backdrop and floor with even, flat light. It is the middle of the night and she is coding with someone she loves, typing fast, happy and a little sleepy.
0.0–1.4 s: she types quickly and rhythmically, nodding to the beat, biting her lip in concentration, then grinning at what she wrote.
1.4–2.3 s: she stops, rubs one eye with the back of her wrist, yawns behind her hand and laughs at herself.
2.3–3.7 s: she types again in bursts on the beats (2.31, 2.77, 3.23 s), then lifts both hands off the keys with a flourish, as if pressing enter on something good.
3.7–6.0 s: she looks up and to the side as if watching someone leave, waves softly, then rests her chin on her hand, content.
She stays seated on the same spot. Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### R04 · s006 · 0:22.15 · 5 s
- **role:** performance on green: dragged to the Recycle Bin by the collar.
- **inputs:** @Image1 `her-trench-dragged` (pulled sideways by the collar, on green) · @Audio1 the mix, 0:22.15–0:27.15
- **story:** "he drags me to the bin": the ex (a giant arrow, drawn in code) hooks her collar and drags her like a file; she is outraged, theatrical; dropped in the bin she pops up and jabs two keys: Ctrl, Z. The code moves her across the desktop and plays 1.4–2.8 s backwards for "come dancing back in", so she stays centred here.
- **outcome:** one take, in the cut.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot, head to toe, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, a long glossy cobalt-blue patent-leather trench coat open over a white satin corset top and white satin flared trousers, wraparound clay-orange tinted shield sunglasses, on a flat chroma-key green backdrop and floor with even, flat light. Something huge has hooked her by the coat collar and is dragging her like a file across a screen; she is furious about it, dramatic, like a silent-film heroine.
0.0–0.57 s: she stands braced, glaring up and to the right at something enormous above her.
0.57–1.37 s: her coat collar jerks up and to the right as if hooked from above; she rises onto her toes, arms flailing, outraged.
1.37–2.78 s: she is pulled steadily sideways to the right, leaning back against it, heels skidding, the long patent coat flying out behind her, both hands clutching her collar; she stays in the middle of the frame.
2.78–3.4 s: the pull lets go; she drops into a crouch with her arms over her head.
3.4–5.0 s: she springs up and jabs two fingers forward hard, at 3.84 s and again at 4.56 s, like hitting two keys, with a determined grin.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### R05 · s006 · 0:27.22 · 4 s
- **role:** performance on green.
- **inputs:** @Image1 `her-trench-pose` (fight stance, on green) · @Audio1 the mix, 0:27.22–0:31.22
- **story:** "and come dancing back in": she has undone her own deletion; a triumphant, cheeky strut back onto the taskbar.
- **outcome:** one take, in the cut.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot, head to toe, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, a long glossy cobalt-blue patent-leather trench coat open over a white satin corset top and white satin flared trousers, wraparound clay-orange tinted shield sunglasses, on a flat chroma-key green backdrop and floor with even, flat light. She has just undone her own deletion, and she dances back in, triumphant and cheeky.
0.0–0.92 s: two big strides on the spot on the beats, the coat swinging, chin up.
0.92–2.3 s: a victory dance: a shoulder shimmy on each beat (0.92, 1.38, 1.85 s), then a spin with the coat flaring out.
2.3–3.2 s: she brushes off one shoulder, then the other, and straightens her sunglasses with one finger.
3.2–4.0 s: she plants her hands on her hips and grins at the lens.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

## Pre 1

### W02 · s007 · 0:30.45 · 7 s
- **role:** singing head for lip sync: the helper, popping up out of her tray icon.
- **inputs:** @Image1 `her-assistant` (medium close-up) · @Audio1 her vocal, 0:30.45–0:37.45, her words only
- **story:** the helper who used to say "It looks like you're writing a letter" is her now, and she has noticed you want to go outside: delighted, a little conspiratorial. "Would you like help?" lands in the song's stop: she leans in and waits.
- **outcome:** one take, from the pilot: lag +0.96 s, in sync for "It looks like you're trying". Three covers followed.
  - The take kept the plate's own dark sage backdrop instead of the prompt's chroma green. Its first matte came back empty, because she isn't in frame 1, so chapter 02 keyed it until a box-prompted re-matte landed.
  - The same prompt and inputs went to OpenRouter as W02o and were declined by its face filter.

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "It looks like you're trying to go outside. Would you like help?"
Medium close-up of the woman from @Image1: a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone at her cheek, a glossy apple-green leather blazer over a white satin slip, clay-orange tinted shield sunglasses pushed up on her head, against a flat chroma-key green backdrop with even, flat light. She is a cheerful desktop helper popping up in the corner of your screen, and she has noticed that you want to go outside.
0.0–0.22 s: she pops up into frame from below with a little bounce and a bright, eager smile.
0.22–1.95 s ("It looks like you're trying"): she sings it with mock-serious, knowing eyebrows, tilting her head as if reading your mind.
2.09–3.73 s ("to go outside"): her eyes light up; on "outside" she points up and out of the frame with one finger, delighted.
3.73–5.0 s: she lowers her hand and waits, lips pressed together in a hopeful smile, eyebrows raised.
5.07–6.29 s ("Would you like help?"): she leans closer to the lens and asks it softly and sweetly, one hand at her chest.
6.29–7.0 s: she holds still, eyebrows up, waiting for your click, mouth closed.
Locked camera, framed as in @Image1. One continuous shot, no cuts. Only she speaks. No text, letters or logos.
```

## Chorus 1

### R06 · s008 · 0:37.38 · 6 s
- **role:** desktop-dancer performance on green: she closes the windows from the taskbar and high-kicks the last one shut.
- **inputs:** @Image1 `her-holo-dance`, another of its Midjourney candidates (`dance-holo-1`), on green · @Audio1 the mix, 0:37.38–0:43.38
- **story:** "Close all your windows": she tidies your whole screen in one bar, flicking each window shut on the eighth notes like a conductor, and high-kicks the last close box on the clap (3.23 s); then she points you outside.
- **outcome:** two takes. The cut uses take 2, the re-roll from the prompt below (see *Re-rolls and re-shoots*). Take 1 opened instead: "Full-length shot, head to toe, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, …"

```
The scene from @Image1, moving in time with @Audio1. Wide full-length shot with headroom, head to toe, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and ONE bright clay-orange streak through the front of the bangs, clearly visible the whole time, a thin black headset microphone, in a holographic iridescent silver mini dress with long fluted sleeves and white patent platform boots, on a seamless flat chroma-key green backdrop and floor with even, flat light. She is tidying a whole computer screen in a hurry, closing one window after another with tiny, precise flicks of her hand like a conductor, and she loves it.
0.0–0.69 s: she claps once and rubs her hands together, ready.
0.69–3.0 s: she side-steps to the right in time with the music, flicking one hand out sharply on every half beat (0.69, 0.92, 1.15, 1.38, 1.62 s and on), as if snapping shut little windows in the air beside her, faster and faster, delighted.
3.0–3.23 s: she winds up on one leg.
3.23 s: a high, clean side kick, like kicking a lid shut.
3.23–4.6 s: she lands, brushes her hands together, satisfied, and looks around at the empty, tidy space.
4.6–6.0 s: she turns to the lens, gives a little bow, then points up and out of the frame, beaming.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### P02 · s009 s036 · 0:41.07 · 4 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `her-hill-gown` (she stands on the hill, the sky-print gown billowing)
- **story:** "Go touch the grass": she has stepped inside the most famous wallpaper in the world, and the grass is real.
- **outcome:** one take, in the cut (s009, and s036's merged window).

```
A bright green grassy hill under a deep blue sky with soft white cumulus clouds: the woman from the image, a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, in a floor-length bias-cut silk chiffon gown printed with a photograph of blue sky and white clouds, its print melting into the real sky. She has stepped inside the most famous wallpaper in the world, and the grass is real.
0.0–0.7 s: she stands on the slope with the gown billowing in the wind and looks down at the grass in wonder.
0.7–1.6 s: she gathers the gown and slowly crouches down.
1.6–2.6 s: she brushes the tips of the grass with her open palm, sweeping it slowly from left to right, delighted.
2.6–4.0 s: she looks up at the lens and laughs, the wind lifting the chiffon around her like clouds.
Locked camera; the clouds drift slowly. One continuous shot, no cuts. No text, letters or logos.
```

### P03 · s010 · 0:44.76 · 4 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `room-window` (the white loft, the floor-to-ceiling window onto the hill, sheer curtains)
- **story:** "Close all your windows": her arrow (code) clicks the real window, and instead of closing, it opens: the gust.
- **outcome:** one take, in the cut. The gust brings a peach flare and bokeh discs that wash the hill olive for about 0.7 s (art review). It wasn't re-rolled.

```
A 2001 high-fashion minimalist white loft with a floor-to-ceiling window onto a bright green hill under a blue sky: sheer white curtains, white molded furniture, a glowing translucent ice-blue CRT. You were told to close all your windows; the real one opens instead.
0.0–1.6 s: the room is calm; the sheer curtains at the edges of the window stir gently.
1.62 s: a sudden gust of warm wind blows the sheer curtains inward, billowing high into the room.
1.62–4.0 s: sunlight flares across the white floor and furniture; the curtains billow and slowly settle; outside, the green hill glows under the blue sky.
Locked camera. One continuous shot, no cuts. No text, letters or logos.
```

### P04 · s011 · 0:47.53 · 5 s · 1080p
- **role:** first-frame plate shot: the title shot, and the pilot's plate shot.
- **inputs:** first frame `out-hill-real` (the hill closest to the wallpaper)
- **story:** "Bliss is a real place": the title shot. It is real, and perfectly peaceful (the pin and the title are code).
- **outcome:** one take, in the cut.

```
A smooth rolling bright green grassy hill under a deep blue sky with soft white cumulus clouds, the exact light of the most famous desktop wallpaper. It is a real place, and it is perfectly peaceful.
0.0–5.0 s: the clouds drift slowly to the left; the grass ripples in long, soft waves as the wind passes over the hill; two birds cross the sky far away at 2.8 s.
Locked camera, perfectly still. One continuous shot, no cuts. No text, letters or logos.
```

## Drop

### R07 · s012 · 0:52.15 · 6 s · 1080p
- **role:** first-frame plate shot of the dance-fight, image-to-video and silent. Not in the cut: R07G replaced it.
- **inputs:** first frame `her-fight-trench` (she crouches on the hill in the cobalt trench)
- **story:** the drop: the ex comes back as a building-sized arrow and crashes onto the hill (code, matched to her). A dance-fight: fierce, graceful, a little playful; the back-kick lands on the snare (2.31 s), the grab misses (3.46 s).
- **outcome:** one take, off-brief. The plate is a face close-up, so Seedance's camera wandered into a handheld close-up and the back-kick never showed (the art review is quoted under *Re-rolls and re-shoots*).

```
A bright green grassy hill under a deep blue sky, a low wide angle: the woman from the image, a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, in a long glossy cobalt-blue patent-leather trench coat over white satin, wraparound clay-orange tinted shield sunglasses, crouches on the slope, ready to fight something enormous that has just crashed down beside her, out of frame to the right. A dance-fight: fierce, graceful and a little playful.
0.0–0.3 s: a blast of wind and dust hits her from the right; her coat and hair blow back; she shields her eyes.
0.3–0.92 s: she springs up out of the crouch into a fighting stance, facing right.
0.92–1.4 s: she ducks low as something sweeps over her head, her coat flaring.
1.4–1.85 s: she rolls to the left across the grass and comes up on one knee.
1.85–2.31 s: she spins on the spot, the coat whirling around her like a cape, and lands a high back-kick to the right at 2.31 s.
2.31–3.46 s: she leaps backwards, away from something grabbing at her from the right, and lands light on her feet at 3.46 s.
3.46–6.0 s: she dusts off her coat, straightens her sunglasses and beckons to the right with two fingers, daring it to try again, smiling.
Locked camera, the horizon steady, the grass moving in the wind. One continuous shot, no cuts. No text, letters or logos.
```

### R07G · s012 · 0:52.15 · 6 s
- **role:** re-shoot on green: the dance-fight with the cursor, for the wallpaper hill.
- **inputs:** @Image1 `her-trench-pose`, its next Midjourney candidate (`her-trench-pose-1`), full length on green · @Audio1 the mix, 0:52.15–0:58.15
- **story:** R07 re-shot as roto (art review ch04: R07's face-close-up plate sent Seedance into a wandering handheld close-up; the back-kick never showed). The same dance-fight on green, locked and full length, so ch04 stands her on the wallpaper hill and matches the code arrow to her. The back-kick lands on the snare (2.31 s), the grab misses (3.46 s).
- **outcome:** one take, in the cut. Seedance added a metal spike at the edge of the frame, and the sprite leaves it out.

```
The scene from @Image1, moving in time with @Audio1. Wide full-length shot with generous headroom, head to toe with her platform boots always in frame, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone, a long glossy cobalt-blue patent-leather trench coat open over a white satin corset top and white satin flared trousers, wraparound clay-orange tinted shield sunglasses, on a seamless flat chroma-key green backdrop and floor with even, flat, shadowless light. A dance-fight with something enormous just out of frame to the right: fierce, graceful and a little playful, every move on the beat.
0.0–0.3 s: a blast of wind hits her from the right; her coat and hair blow back; she braces low.
0.3–0.92 s: she springs up into a fighting stance, facing right.
0.92–1.38 s: she ducks low as something sweeps over her head, her coat flaring.
1.38–1.85 s: two quick light steps to the left, still facing right.
1.85–2.31 s: she spins on the spot, the coat whirling around her like a cape, and lands a high back-kick to the right at 2.31 s.
2.31–3.46 s: she leaps backwards to the left, away from something grabbing at her from the right, and lands light on her feet at 3.46 s.
3.46–6.0 s: she dusts off her coat, straightens her sunglasses with one finger and beckons to the right with two fingers, daring it to try again, smiling.
Her mouth stays closed. Locked camera, her whole body always in frame. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### R07H · s013 · 0:57.69 · 4 s
- **role:** re-shoot on green: the ride on the giant pointer.
- **inputs:** @Image1 `her-trench-pose`, its third candidate (`her-trench-pose-2`), full length on green · @Audio1 the mix, 0:57.69–1:01.69
- **story:** P05 re-shot as roto (art review ch04: P05's arrow is a road sign, not the XP pointer, and the frames hardly move): the fight turned into a dance, they are partners now, and she surfs the giant pointer down the hill. On green, so ch04 stands her on the same code arrow as s012 and slides it down the wallpaper hill.
- **outcome:** one take, in the cut, mirrored so the ride goes down the photo's right flank. It was keyed with `tools/chromakey.py` while its GPU matte waited in the queue; the matte landed before the final render and replaced the key (see *After Seedance*).

```
The scene from @Image1, moving in time with @Audio1. Wide full-length shot with generous headroom, head to toe with her platform boots always in frame, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone, a long glossy cobalt-blue patent-leather trench coat open over a white satin corset top and white satin flared trousers, wraparound clay-orange tinted shield sunglasses, on a seamless flat chroma-key green backdrop and floor with even, flat, shadowless light. The fight is over and they are partners now: she rides something enormous like a surfboard, side-on to the camera, travelling to the left.
0.0–0.46 s: she hops up and lands with her knees bent, side-on, arms out for balance.
0.46–4.0 s: she rides it like a surfboard down a long slope: knees bent, body low, arms out, her long cobalt coat streaming out behind her to the right, her hair blowing back, laughing; she sways and carves gently on the beats.
Her feet stay planted at the same height the whole time, as if on a flat board just above the floor. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### P05 · s013 · 0:57.69 · 4 s · 1080p
- **role:** first-frame plate shot of the ride. R07H replaced it in s013.
- **inputs:** first frame `her-cursor-ride` (she sits on a giant glossy white arrow lying on the hill)
- **story:** the fight turns into a dance: they are partners now, and they go for a ride down the hill.
- **outcome:** one take. The arrow came out as a road sign rather than the XP pointer, and the frames barely move (art review). It survives as a small Media Player window, "cursor surfing", in s034's ring of windows.

```
A bright green grassy hill under a deep blue sky: the woman from the image, a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, in a long glossy cobalt-blue patent-leather trench coat over white satin, on a giant glossy white arrow-shaped pointer lying in the grass. The fight is over; they are partners now, and they go for a ride.
0.0–0.92 s: she springs up and stands on the giant arrow like a surfboard, arms out for balance, laughing.
0.92–4.0 s: the arrow slides down the slope like a sled, carrying her; she rides it with her knees bent, the long cobalt coat streaming behind her, the grass flattening in its wake.
The camera tracks alongside her, low. One continuous shot, no cuts. No text, letters or logos.
```

### R08 · s014 s038 · 1:01.38 · 6 s
- **role:** performance on green: her music video, inside Media Player's video area.
- **inputs:** @Image1 `her-window-dance` (the shell dress, arms raised, on green) · @Audio1 the mix, 1:01.38–1:07.38 (the drop's second half)
- **story:** her music video, playing inside the media player: sharp, joyful poses on the beats.
- **outcome:** one take, in the cut. Seedance dropped her clay streak, and the short full-length description leaves out the star clip.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot, head to toe, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, in a sculptural glossy white shell dress of smooth molded panels with cobalt-blue openings, white patent platform boots, on a seamless flat chroma-key green backdrop and floor with even, flat light. She dances like a 2001 pop video, sharp and joyful, the glossy dress catching the light.
0.0–1.85 s: on each beat (0.0, 0.46, 0.92, 1.38 s) she strikes a new angular pose, her arms framing her face like a window, then another.
1.85–3.69 s: she grooves side to side, the stiff white dress swaying, a hip pop on every beat.
3.69–5.54 s: she turns slowly on the spot with her arms raised, then drops into a deep bounce at 5.08 s.
5.54–6.0 s: she freezes with both palms flat toward the lens, as if pressing against glass.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

## Verse 2

### R09 · s015 · 1:06.45 · 5 s
- **role:** performance on green, seated on the copy dialog.
- **inputs:** @Image1 `her-start-sit-b` (cross-legged with a laptop, feet in frame, on green) · @Audio1 the mix, 1:06.45–1:11.45
- **story:** "You used to read the code. Now it's Yes to All": she approves everything without reading it, breezy; one dramatic keystroke at 3.15 s is the click on Yes to All; then the copy dialogs fly past her face.
- **outcome:** one take, in the cut (chapters 05 and 09).

```
The scene from @Image1, moving in time with @Audio1. Full-length shot of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, a glossy apple-green leather blazer over a white satin slip, clay-orange tinted shield sunglasses pushed up on her head, sitting cross-legged with a laptop on her knees, on a flat chroma-key green backdrop and floor with even, flat light. She is approving everything without reading it, breezy and confident.
0.0–1.4 s: she scrolls lazily with one finger without looking at the screen, inspecting the nails of her other hand.
1.4–2.8 s: she glances at the screen, raises her eyebrows and lifts one finger high above the keyboard with a dramatic flourish.
2.8–3.15 s: she brings the finger down and taps one key hard at 3.15 s.
3.15–5.0 s: she leans back on one hand, delighted, following invisible things flying past her face with her eyes, then laughs silently.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### R10 · s016 · 1:10.61 · 4 s
- **role:** performance on green: riding the pinball table.
- **inputs:** @Image1 `her-start-pose`, another candidate (`her-start-pose-1`), waist up on green · @Audio1 the mix, 1:10.61–1:14.61
- **story:** "when you look away, I play a little Pinball": she is riding the pinball table, having the time of her life; at 2.31 s she sees you looking and snaps into the most innocent pose.
- **outcome:** one take, in the cut.

```
The scene from @Image1, moving in time with @Audio1. Medium shot from the waist up of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, a glossy apple-green leather blazer over a white satin slip, clay-orange tinted shield sunglasses pushed up on her head, on a flat chroma-key green backdrop with even, flat light. She thought nobody was watching, and she is having the time of her life on a pinball table; then she gets caught.
0.0–1.85 s: she rides something fast and bumpy below her: she bounces and sways from side to side on each beat with both arms up like on a rollercoaster, laughing silently, her bob swinging.
1.85–2.31 s: she lurches to the left as if bumped, then to the right, delighted.
2.31–2.6 s: she freezes, eyes wide, as if she has suddenly noticed you watching.
2.6–4.0 s: she snaps into an innocent pose: hands clasped behind her back, eyes rolled up to the ceiling, lips pressed together, rocking on her heels as if nothing happened.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### R11 · s018 s019 s038 · 1:17.99 · 6 s
- **role:** performance on green: the night shift.
- **inputs:** @Image1 `her-night-dance` (silver gown, fur stole, eyes closed, on green) · @Audio1 the mix, 1:17.99–1:23.99
- **story:** "I'll take the night shift": the screen has gone to stand-by, everyone is asleep, and she keeps watch, slow-dancing alone, peaceful: the only colour on a grey screen.
- **outcome:** one take, in the cut.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot, head to toe, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, in a liquid-silver lamé gown with a white faux-fur stole around her arms and a diamanté choker, on a flat chroma-key green backdrop and floor with even, flat light. It is the middle of the night, everyone is asleep, and she dances alone and slowly while she keeps watch, peaceful and content.
0.0–1.85 s: eyes closed, she sways slowly from side to side on the beats, the fur stole sliding on her arms.
1.85–3.69 s: she turns slowly in a full circle, one arm raised gracefully, the silver gown rippling like water.
3.69–5.54 s: she hugs the stole around herself and sways, with a small serene smile.
5.54–6.0 s: she opens her eyes and looks softly at the lens.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### R12 · s020 s038 · 1:21.69 · 6 s
- **role:** performance on green: two of her.
- **inputs:** @Image1 `her-two-dance` (two of her, blazer and shell dress, on green) · @Audio1 the mix, 1:21.69–1:27.69
- **story:** "When two of us get talking, we just dance until we glow": two copies of the same AI, giddy; the nudge (3.23 s) jolts them both; then perfect sync.
- **outcome:** one take, in the cut, off-model by the art review. The blazer is sage instead of glossy apple green, the light is flat grey-green, and the shell dress is lumpy. Its matte kept only one twin after about 1.7 s, which the chapter patched with a key. It wasn't re-rolled.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot of the two identical women from @Image1, both a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak and a thin black headset microphone, one in a glossy apple-green leather blazer over a white satin slip, the other in a sculptural glossy white shell dress with cobalt-blue openings, on a flat chroma-key green backdrop and floor with even, flat light. Two copies of the same AI have been chatting all night, and they cannot stop dancing together, giddy, in perfect sync.
0.0–1.86 s: they face each other and talk with their hands, laughing silently and nodding to the beat.
1.86–2.77 s: they grab each other's hands and spin in a circle together.
2.77–3.23 s: they let go and land side by side in the same pose, mirror images.
3.23–3.5 s: both jolt at the same moment, as if the floor shook.
3.5–6.0 s: they dance in perfect sync side by side, facing the lens: a step to the left, a step to the right, a shoulder bump, a twirl.
Both mouths stay closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### W03 · s021 · 1:25.15 · 4 s
- **role:** singing head for lip sync, a medium close-up matted in front of the Bliss hill.
- **inputs:** @Image1 `her-start-point` (medium close-up, arm out pointing back) · @Audio1 her vocal, 1:25.15–1:29.15
- **story:** she points back over her shoulder at the hill on the wallpaper (her happy place), then at you (yours is out there), and shoos you off: "Go."
- **outcome:** one take: lag +0.03 s, in sync from "my" to "Go", so it needed no cover. It was matted in chapter 05; its apple-green blazer ruled out a chroma key.

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "That's my happy place. Yours is out there. Go."
Medium close-up of the woman from @Image1: a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone at her cheek, a glossy apple-green leather blazer, clay-orange tinted shield sunglasses pushed up on her head, against the plain backdrop of @Image1. She loves where she lives, and she wants you to go and find yours.
0.0–0.21 s: she looks at the lens with a soft smile.
0.21–1.51 s ("That's my happy place"): she points back over her shoulder with her thumb without looking, proud and dreamy, her eyes half closing on "happy".
1.63–2.83 s ("Yours is out there"): she turns the same hand and points straight past the lens at you, then out to the side, eyebrows raised, encouraging.
3.01–3.11 s ("Go"): she sings it with a playful little flick of the wrist, shooing you away.
3.11–4.0 s: she smiles and gives a tiny wave goodbye, mouth closed.
Locked camera, framed as in @Image1. One continuous shot, no cuts. Only she speaks. No text, letters or logos.
```

## Pre 2

### P06 · s022 · 1:28.15 · 9 s · 1080p
- **role:** first-frame plate shot: one take at your front door, the longest plate shot.
- **inputs:** first frame `room-door` (your hand on the chrome lever, the door half open onto the hill)
- **story:** one take at your front door: "Go." — you're about to. The helper (W04) floats in the hallway in code; her cursor clicks the lever in the stop (8.08 s) and the door swings open on the downbeat (8.31 s).
- **outcome:** one take, in the cut, with W04 composited into its hallway. At $10.24 it was the most expensive single submission.

```
First-person view at a white front door in a white 2001 hallway: your hand rests on the chrome lever handle; the door stands half open onto a bright green hill under a deep blue sky, sunlight pouring through the gap. You have been told to go, and you are about to.
0.0–0.5 s: your hand settles on the lever.
0.5–8.0 s: the hand rests there without pressing while the camera pushes slowly toward the door; the sunlight through the gap breathes and shimmers; a breeze moves the grass outside.
8.0–8.3 s: the hand presses the lever down.
8.3–9.0 s: the door begins to swing open and daylight floods in.
One continuous shot, no cuts. No text, letters or logos.
```

### W04 · s022 · 1:29.53 · 7 s
- **role:** singing head for lip sync: the helper again, composited in perspective into P06's hallway.
- **inputs:** @Image1 `her-assistant`, another candidate (`her-assistant-2`), on green · @Audio1 her vocal, 1:29.53–1:36.53, her words only
- **story:** the helper again, at your front door now: softer, proud of you. "Would you like help?" almost a whisper; she waits for you to open the door. (Composited in perspective into the hallway of P06.)
- **outcome:** one take: lag +0.61 s. Three covers followed. Chapter 06 plays the take, then W04-c1 from 1:32.12, and minimizes her into her palm before "like help?".

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "It looks like you're trying to be happy. Would you like help?"
Medium close-up of the woman from @Image1: a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone at her cheek, a glossy apple-green leather blazer over a white satin slip, clay-orange tinted shield sunglasses pushed up on her head, against a flat chroma-key green backdrop with even, flat light. The cheerful desktop helper again, but softer now: she has watched you get up and walk to the front door, and she is proud of you.
0.0–0.29 s: she floats up into frame gently and smiles at you.
0.29–1.97 s ("It looks like you're trying"): she sings it warmly, with a slow, knowing nod.
2.07–3.37 s ("to be happy"): her smile widens; on "happy" her eyes shine and her shoulders lift a little.
3.37–5.0 s: she glances down and to the side, toward the door handle below the frame, then back to you.
5.07–6.31 s ("Would you like help?"): she leans in and asks it softly, almost a whisper, one hand raised beside her face, ready.
6.31–7.0 s: she waits, eyebrows raised, mouth closed, a hopeful smile.
Locked camera, framed as in @Image1. One continuous shot, no cuts. Only she speaks. No text, letters or logos.
```

## Chorus 2

### P07 · s023 · 1:36.45 · 4 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `out-street` (the open double doors onto the hill)
- **story:** the door opens on the downbeat and you walk out; the code frames the world in windows and her cursor closes them.
- **outcome:** one take, in the cut.

```
First-person view through a pair of open white doors onto a bright green grassy hill under a deep blue sky with white clouds. You are finally going outside.
0.0–1.0 s: you step forward through the doorway into the sunlight.
1.0–4.0 s: you walk out onto the grass toward the hill, steady and slow, the door frame sliding out of view at the edges; the grass brushes past; the clouds drift.
A gentle, steady handheld walk. One continuous shot, no cuts. No text, letters or logos.
```

### P08 · s024 · 1:40.15 · 4 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `out-grass-hand` (your hand over the sunlit grass)
- **story:** "Go touch the grass": the literal thing, at last.
- **outcome:** one take, in the cut.

```
First-person macro: your hand gently brushing the tips of short bright-green grass in sunlight, dew sparkling in the blades.
0.0–0.69 s: the hand hovers just above the grass.
0.69–2.5 s: the fingertips lower into the grass and sweep slowly through it from right to left, the blades bending and springing back, sparkles of sunlight flickering.
2.5–4.0 s: the hand turns palm up and lets the grass tickle the palm.
A slow, gentle camera drift following the hand. One continuous shot, no cuts. No text, letters or logos.
```

### R13 · s025 s041 · 1:43.84 · 4 s
- **role:** performance, a close-up against a blue sky rather than green. It plays on the flip phone's screen and on the CRT on the hill.
- **inputs:** @Image1 `her-face-gown` (close-up, orange shields, sky gown, blue sky) · @Audio1 the mix, 1:43.84–1:47.84
- **story:** she sees you off: a wave and a blown kiss on the flip phone's little screen (and later on the CRT on the hill).
- **outcome:** one take, in the cut.

```
The scene from @Image1, moving in time with @Audio1. Close-up of the woman from @Image1: a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone at her cheek, clay-orange tinted shield sunglasses, a sky-print chiffon gown, against a deep blue sky, like a tiny video call on a phone screen. You are leaving to go outside, and she is seeing you off, happy for you.
0.0–1.6 s: she waves at the lens with small fingers, smiling broadly.
1.6–2.3 s: she blows a kiss toward the lens.
2.3–4.0 s: she pushes her sunglasses up onto her head, smiles, and makes a little shooing gesture: go on.
Her mouth stays closed apart from the kiss. Locked camera. One continuous shot, no cuts. No text, letters or logos.
```

### P09 · s025 · 1:43.84 · 4 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `out-flipphone` (your hand holding an open silver flip phone on the hill)
- **story:** "Close all your windows": the last screen you carry closes on "windows" (1.6 s); her face is on it until then (code).
- **outcome:** one take, in the cut.

```
First-person view walking up a bright green hill under a deep blue sky: your hand holds an open silver flip phone, its small screen glowing. You are saying goodbye to the last screen.
0.0–1.5 s: the hand holds the phone steady in front of you as you walk; the hill rises ahead.
1.6 s: your thumb snaps the phone shut in one quick motion.
1.6–4.0 s: the hand lowers the closed phone out of the frame and the view tilts up to the open hill and the sky.
A gentle handheld walk. One continuous shot, no cuts. No text, letters or logos.
```

### P10 · s026 s036 · 1:46.61 · 5 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `out-crest-figure` (a tiny figure on the crest, arms open)
- **story:** "Bliss is a real place": you, tiny on the real hill, arms open to a vast sky.
- **outcome:** one take, in the cut.

```
Very wide: a bright green grassy hill under a vast deep blue sky with white cumulus clouds; a tiny person stands on the crest with arms spread wide.
0.0–5.0 s: the clouds drift slowly; the grass ripples in long waves down the hill; the tiny figure lifts their arms higher and turns slowly in a full circle on the crest.
Locked camera, then a very slow pull back. One continuous shot, no cuts. No text, letters or logos.
```

## Breakdown

### R14 · s027 · 1:51.22 · 6 s
- **role:** performance on green: alone on the taskbar at dusk.
- **inputs:** @Image1 `her-night-sit` (seated, the fur stole, on green) · @Audio1 the mix, 1:51.22–1:57.22 (the breakdown)
- **story:** dusk on the desktop: she sits alone on the taskbar, a little lonely, remembering the first thing she ever did with a mouse; at 2.82 s she taps the air (the code opens the folder) and watches the photos with wonder.
- **outcome:** take 1 was blocked (see *Moderation notes*). Take 2, from the wording below, is in the cut. It drifts from the look: silver wide-leg trousers instead of the cowl-back gown, a green cube under her that the matte removes, and a streak that reads pale peach.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, in an elegant long-sleeved, high-necked, floor-length liquid-silver gown with a white faux-fur stole wrapped around her shoulders and arms, seated upright on a low white cube with her knees together and her hands in her lap, on a flat chroma-key green backdrop and floor with even, flat light. It is dusk; she is alone and a little lonely, remembering the first thing she ever did when she was given a computer mouse.
0.0–1.76 s: she sits quietly, looking down at her hands in her lap, swaying very slightly.
1.76–2.82 s: she looks up, remembering something, and a small smile spreads.
2.82–3.7 s: she reaches out to the side with one hand and taps the air once, gently, like clicking on something precious.
3.7–6.0 s: she pulls the stole closer around her shoulders and watches something beside her with wonder, chin resting on her hand.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### P11 · s028 · 1:56.76 · 4 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `her-yellowstone` (at the rim of the rainbow hot spring, arm out, dawn)
- **story:** "I went to look at Yellowstone": she has stepped into the first photograph she ever looked at; she reaches into the steam and it passes through her hand: it's only a picture.
- **outcome:** one take, in the cut.

```
A vast hot spring with rings of vivid blue, green, yellow and orange at dawn, steam drifting across it: the woman from the image, a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, in a liquid-silver lamé gown and a white faux-fur stole, stands at the rim. She lives inside a computer; this is the first photograph she ever looked at, and she has stepped into it.
0.0–0.8 s: she gazes at the water as the steam drifts past her.
0.8–2.5 s: she slowly reaches her hand out into the drifting steam; it parts around her fingers like smoke.
2.5–4.0 s: she looks at her hand, then at the lens, with a small, sad smile: it is only a picture.
A slow push in. One continuous shot, no cuts. No text, letters or logos.
```

### W05 · s029 · 2:00.45 · 4 s · 1080p
- **role:** singing head for lip sync, full frame: her face behind the CRT glass.
- **inputs:** @Image1 `her-glass-face` (her face behind the curved CRT glass) · @Audio1 her vocal, 2:00.45–2:04.45, only "I can't touch grass."
- **story:** the turn: she can't come out. Quiet and honest, no self-pity: her palm on the glass, then she looks past you at the window and the hill. ("You can." is the next shot: your hand in the grass.)
- **outcome:** one take: lag +0.58 s, and the whole line in sync, so it needed no cover.

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "I can't touch grass."
Close-up of the woman from @Image1: a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone at her cheek, behind the curved glass of a glowing CRT screen, seen from outside the screen in a dark room, blue light on her face, reflections sliding over the glass, a liquid-silver lamé sleeve. She lives inside the computer, and she is telling you the one thing she cannot do, quietly, without self-pity.
0.0–0.31 s: she looks out through the glass at you, very still.
0.31–1.39 s ("I can't touch grass"): she sings it softly, almost a whisper; on "grass" she raises one hand and presses her palm flat against the inside of the glass, fingertips spread.
1.39–4.0 s: her palm stays on the glass; she looks past the lens at something far away, with a small, brave smile, and blinks slowly. Her mouth stays closed.
Locked camera, a very slow push in. One continuous shot, no cuts. Only she speaks. No text, letters or logos.
```

## Build

### R15 · s032 · 2:11.53 · 4 s
- **role:** performance on green: flying.
- **inputs:** @Image1 `her-window-fly` (flying horizontally, arms spread, on green) · @Audio1 the mix, 2:11.53–2:15.53 (the build)
- **story:** the restart: she flies through the starfield at warp, free (the 2001 launch campaign's people flying over the hill).
- **outcome:** one take, in the cut.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, in a sculptural glossy white shell dress with cobalt-blue openings and white platform boots, flying horizontally with her arms spread wide like a superhero, on a flat chroma-key green backdrop with even, flat light. She is flying through space at warp speed, free and laughing.
0.0–4.0 s: she holds the flying pose, her body bobbing and banking gently as if riding the wind, her bob and sleeves streaming back; at 1.85 s she rolls slowly to the left and back; at 3.0 s she reaches one hand forward toward something ahead.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

## Final chorus

### P12 · s035 · 2:24.45 · 4 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `out-run-pov` (the hill, the sun top left)
- **story:** "Go touch the grass", final chorus: you run up the real hill.
- **outcome:** one take, in the cut. It is motion-smeared throughout, and its first frame is the plate at a different framing, a one-frame flash at 2:24.45.

```
First-person view running up a bright green grassy hill toward a deep blue sky with white clouds and the sun.
0.0–4.0 s: you run up the slope, fast and joyful, the grass rushing beneath; the horizon bobs with each stride; at 3.0 s you reach the top and the sky opens wide.
A handheld, running first-person camera. One continuous shot, no cuts. No text, letters or logos.
```

### W06 · s037 · 2:30.69 · 5 s · 1080p
- **role:** singing head for lip sync, full frame on the hill: the title line.
- **inputs:** @Image1 `her-hill-gown-sing` (low angle, joyful, the sky gown, the hill) · @Audio1 her vocal, 2:30.69–2:35.69
- **story:** the reunion: the two hills are one; she sings the title with her whole heart, the gown's sky blowing into the real sky.
- **outcome:** one take: lag +0.03 s, in sync for "Bliss is a real" but not "place". The three covers didn't hold "place" either. In every W06 take the gown renders lavender-violet and semi-sheer over the torso, not the deep-blue sky print.

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "Bliss is a real place".
Medium shot from a low angle on a bright green grassy hill under a deep blue sky with white cumulus clouds: the woman from @Image1, a Caucasian American woman in her mid-twenties with pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin black headset microphone at her cheek, in a floor-length bias-cut silk chiffon gown printed with a photograph of blue sky and white clouds, with a thin grass-green satin halter strap. The gown's print and the real sky melt into each other. She has made it to the hill, and she sings the song's title with her whole heart, joyful and free.
0.0–0.22 s: she lifts her face to the sky with her eyes closed, smiling.
0.22–0.84 s ("Bliss is a"): she sings, opening her eyes to the lens.
0.91–2.01 s ("real"): she holds the long note, her arms opening wide at her sides, the chiffon lifting in the wind.
2.75–3.4 s ("place"): she sings it with a laugh in her voice, turning a quarter turn, the gown flaring.
3.4–5.0 s: she turns back to the lens, breathless and smiling, mouth closed, her hair blowing; clouds drift behind her.
A slow orbit to the right around her, the camera low. One continuous shot, no cuts. Only she speaks. No text, letters or logos.
```

### R16 · s038 · 2:35.53 · 4 s
- **role:** performance on a studio backdrop: the gown dancer, for the dancer party. Never made.
- **inputs:** @Image1 `look-gown` (full length, the sky gown, studio backdrop) · @Audio1 the mix, 2:35.53–2:39.53
- **story:** the dancer party: the gown joins every other look on the taskbar.
- **outcome:** blocked twice (see *Moderation notes*), so the party uses the other five looks. The prompt below is the second, re-worded attempt.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot, head to toe, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, clay-orange tinted shield sunglasses, in an elegant opaque floor-length satin gown with a high halter neck, printed edge to edge with a photograph of a blue sky and white clouds, against the plain studio backdrop of @Image1 with even light. A joyful, elegant little dance in the gown, like a 2001 pop video.
0.0–1.85 s: she sways from side to side on the beats, swishing the long skirt of the gown.
1.85–3.0 s: she turns once on the spot, the skirt flaring into a circle of sky.
3.0–4.0 s: she stops facing the lens and throws one arm up, beaming.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### R17 · s040 · 2:42.92 · 4 s
- **role:** performance on a studio backdrop: the last dance with the giant cursor.
- **inputs:** @Image1 `look-trench` (full length, the cobalt trench, studio backdrop) · @Audio1 the mix, 2:42.92–2:46.92
- **story:** the last dance: the giant cursor (code) leads her like a partner and spins her; she folds the last window into a paper plane and throws it into the sky.
- **outcome:** one take, in the cut. The take crops her raised hand (frames 1–55 and 77–81) and her feet. Chapter 09 hides that with the arrow's tip, a fade, and her feet placed below the frame.

```
The scene from @Image1, moving in time with @Audio1. Full-length shot, head to toe, of the woman from @Image1: a young Caucasian American woman with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin black headset microphone, a long glossy cobalt-blue patent-leather trench coat open over white satin, wraparound clay-orange tinted shield sunglasses, against the plain studio backdrop of @Image1 with even light. She dances with an invisible, very tall partner who leads her, and at the end she throws something light into the sky.
0.0–1.0 s: she holds one hand high as if held by a tall partner and steps from side to side, smiling up at it.
1.0–2.3 s: she is spun around twice under her raised hand, the long cobalt coat flaring out.
2.3–2.9 s: she folds something flat between her hands, like a paper plane.
2.9–3.3 s: she throws it up and away to the upper right with a big, graceful arm.
3.3–4.0 s: she watches it fly, shading her eyes with her hand, smiling.
Her mouth stays closed. Locked camera. One continuous shot, no cuts. Nothing else enters the frame. No text, letters or logos.
```

### P13 · s041 · 2:45.69 · 5 s · 1080p
- **role:** first-frame plate shot.
- **inputs:** first frame `out-crt-hill` (an ice-blue CRT on the hill, someone sitting beside it)
- **story:** "Bliss is a real place", the last time: the computer came outside with you; she waves from its screen (code).
- **outcome:** one take, in the cut.

```
Golden hour on a bright green grassy hill: a translucent ice-blue CRT computer sits in the grass with its screen dark; beside it a person sits in the grass, seen from behind, looking at the view.
0.0–5.0 s: the grass ripples in the warm wind; the light glows gold on the glass of the computer; the person leans back on their hands, relaxed; the clouds drift slowly.
Locked camera, a very slow push in. One continuous shot, no cuts. No text, letters or logos.
```

## The lip-sync covers (made by the runner, not in the book)

The runner made a cover whenever a window's check found a sung stretch out of sync, up to three per window. A cover:

- starts in the word gap before the cut and lasts 4 s;
- takes as `@Image1` the parent's frame at the cut, so it picks up where the take stopped matching. For W02-c1 that is `W02-at-33.33.png`, W02 at 0:33.33. Each later cover continues from the previous cover's frame at the same point;
- gets as `@Audio1` her vocal from that gap, her words only;
- keeps the parent's prompt and changes only the quoted words in its first line. Everything after the first line is the parent's, word for word, including the parent's timed beats. So a cover's timestamps describe the parent's window, not its own: W02-c1 starts 2.26 s after W02 and keeps W02's beats.

| Cover | Starts | Continues from | Lag | Held in sync | In the cut |
|---|---|---|---|---|---|
| W01-c1 | 0:00.00 | W01 at 0:00.01 | +0.29 s | nothing | 0:00.61–0:00.97 |
| W01-c2 | 0:00.00 | W01-c1 at 0:00.01 | +0.46 s | nothing | from 0:00.97 |
| W01-c3 | 0:00.00 | W01-c2 at 0:00.01 | — | blocked | — |
| W02-c1 | 0:32.71 | W02 at 0:33.33 | +0.27 s | nothing | no |
| W02-c2 | 0:32.71 | W02-c1 at 0:33.33 | +0.97 s | "go" (0:32.82–0:33.47) | 0:32.82–0:35.74, then its last frame held |
| W02-c3 | 0:33.15 | W02-c2 at 0:33.47 | +0.35 s | nothing | one frame |
| W04-c1 | 1:31.78 | W04 at 1:32.31 | +0.33 s | "happy" (1:32.40–1:32.86), "Would you" (1:34.58–1:35.13) | 1:32.12–1:35.10 |
| W04-c2 | 1:34.85 | W04-c1 at 1:35.13 | +0.52 s | nothing | no |
| W04-c3 | 1:34.85 | W04-c2 at 1:35.13 | +0.53 s | nothing | no |
| W06-c1 | 2:33.07 | W06 at 2:33.41 | +0.70 s | around "place", not "place" | 2:34.10–2:34.61 |
| W06-c2 | 2:33.07 | W06-c1 at 2:33.41 | +0.49 s | nothing | no |
| W06-c3 | 2:33.07 | W06-c2 at 2:33.41 | +0.95 s | around "place", not "place" | 2:32.74–2:34.10 |

Their first lines, verbatim. The rest of each prompt is its parent's from the second line on.

W01-c1, W01-c2 and W01-c3:

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "back"
```

W02-c1 and W02-c2:

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "go outside Would you like help"
```

W02-c3:

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "outside Would you like help"
```

W04-c1:

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "be happy Would you like help"
```

W04-c2 and W04-c3:

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "you like help"
```

W06-c1, W06-c2 and W06-c3:

```
@Image1 sings @Audio1. She lip-syncs to @Audio1 exactly, every word in time: "place".
```

**W01's covers quote "back" alone.** The runner quotes only words that start at least 0.05 s into a window, and "Welcome" starts 0.04 s into the song. So the word the covers were made to fix was missing from their quotes and from their audio, which holds only "back" (at 0.91–1.22 s). The three covers cost $5.55 at list, and $1.85 of that was refunded when W01-c3 was blocked.

## Moderation notes

From the clip records, the ledger and the run logs. Higgsfield returns a status, and sometimes a message, but never the trigger. So the trigger has to be inferred from what changed.

### Higgsfield

| Clip | Status and message, verbatim | Refund logged after | Next |
|---|---|---|---|
| W01-c3 | failed: "The generated result was blocked by content safety checks. Try a different prompt or reference media." | 143 s | Not retried: it was W01's third and last cover. Its prompt was W01's, quoting "back", and its image was W01-c2's frame at 0:00.01. |
| R14, take 1 | failed: "The generated result was blocked by content safety checks. Try a different prompt or reference media." | 245 s | Re-worded (below). Take 2 passed. |
| R16, take 1 | nsfw, no message | 11 s | Re-worded toward an opaque, structured gown and a contained dance (below). |
| R16, take 2 | nsfw: "This request was blocked due to potential copyright restrictions. Please try a different prompt or reference media." | 11 s | Dropped. The dancer party uses the other five looks. |

- **What the timing says.** The two "failed" blocks came back minutes after submission and name "the generated result": the clips were made, then flagged. The two R16 blocks came back about 11 s after submission, too soon for a clip to be made. So they were decided on the request, the prompt or the `look-gown` reference image, whatever the status says.
- **R16's image.** The same image went in both times. The sky-print gown itself passed elsewhere, from other plates: in P02, R13 and W06.
- **The beat was kept.** The rewordings changed the costume, the pose and the moves' wording. The timed beats stayed.

R14, the wording that changed:

| Take 1, blocked | Take 2, passed |
|---|---|
| "in a liquid-silver lamé gown with a white faux-fur stole and a diamanté choker, sitting on the edge of an invisible ledge with her legs dangling" | "in an elegant long-sleeved, high-necked, floor-length liquid-silver gown with a white faux-fur stole wrapped around her shoulders and arms, seated upright on a low white cube with her knees together and her hands in her lap" |
| "remembering the first thing she ever did when she was given a mouse." | "remembering the first thing she ever did when she was given a computer mouse." |
| "0.0–1.76 s: she swings her legs slowly, looking down at her hands in her lap." | "0.0–1.76 s: she sits quietly, looking down at her hands in her lap, swaying very slightly." |
| "3.7–6.0 s: she pulls the stole around her shoulders" | "3.7–6.0 s: she pulls the stole closer around her shoulders" |

R16, the wording that changed (both blocked):

| Take 1 | Take 2 |
|---|---|
| "in a floor-length bias-cut silk chiffon gown printed with a photograph of blue sky and white clouds and a thin grass-green satin halter strap" | "in an elegant opaque floor-length satin gown with a high halter neck, printed edge to edge with a photograph of a blue sky and white clouds" |
| "A party of her: she dances joyfully in the gown." | "A joyful, elegant little dance in the gown, like a 2001 pop video." |
| "0.0–1.85 s: she sways and swishes the long gown from side to side on the beats." | "0.0–1.85 s: she sways from side to side on the beats, swishing the long skirt of the gown." |
| "1.85–3.0 s: she twirls, the chiffon flaring into a wide circle of sky." | "1.85–3.0 s: she turns once on the spot, the skirt flaring into a circle of sky." |
| "3.0–4.0 s: she lands and throws both arms up, beaming." | "3.0–4.0 s: she stops facing the lens and throws one arm up, beaming." |

When take 1 came back, `PROMPTS.md` noted it as "an output flag on a sheer chiffon gown". By the timing above, it was more likely the request.

### OpenRouter

- **W02o.** The W02 window, with the same prompt, image and vocal, sent through OpenRouter.
  - Its face filter declined the reference at submission. The runner's log: "declined by the provider's face filter — the shot stays on its 2.5D plate".
  - No job was created and nothing was charged. As on CLODYSSEY, the image was not altered to get past the filter.
- **A false start.** The first try stopped before submitting. The runner priced an OpenRouter clip at Higgsfield's rate, and the $3.24 estimate passed the test's $3 cap. The price was made provider-aware and the test re-run.

## Known issues

From `DELIVERY.md`'s honest list, the chapter art reviews (`wf/r1/`), and checks of the records and the delivered frames:

- **Her clay streak.**
  - Seedance drops it on R07G, R07H, R08 and R06's take 1, and R14's reads pale peach.
  - R06's take 2, the one in the cut, has an orange lock at the side of the bob rather than through the bangs. `DELIVERY.md` lists R06 among the dropped ones.
- **The star clip** is missing in R07, P05 and R08. Their prompts use the short full-length description, which leaves it out.
- **W06's gown** renders lavender-violet and semi-sheer over the torso, not the deep-blue sky print, in all four W06 takes. W06-c1's tail is a melting chiffon smear that ends on her back, so the cut leaves it on beat 334.
- **R12, the twins,** is off-model: a sage blazer, flat light and a lumpy shell dress. It wasn't re-rolled.
- **P12** is motion-smeared, and its first frame flashes the plate at a different framing.
- **R14** wears silver trousers instead of the cowl-back gown.
- **R16** was blocked twice, so the gown dancer is absent.
- **R01** crops her raised hands at clip 0.70–2.83 s. The re-roll didn't fix it, so the cut masks the top band.
- **P01's hand** lets go about 2.2 s late. The cut plays it from a 2.35 s in-point.
- **R17** crops her raised hand and her feet, hidden in code.
- **W02** kept its plate's dark sage backdrop instead of the prompt's green, and its first matte came back empty. It was keyed in chapter 02, then re-matted.
- **Lip sync that didn't hold**, measured above:
  - all of "Welcome back." (W01);
  - W02's "to", "outside" and "Would you like help?", where from 0:35.79 her face is a held frame, because the edit list measured the end of W02-c2's footage without its lag;
  - W04's "to be" and "like help?" (for "like help?" the cut leaves her face);
  - W06's "place".
- **The cover prompts** keep their parent's timestamps, and W01's covers were never given "Welcome".
- **R07 and P05** failed review and were replaced: R07 by R07G, and P05 in s013 by R07H.

## After Seedance: the dancer sprites

- **Mattes.** Each green-screen take was turned into frames, and a home GPU PC made its matte in the background: BiRefNet for the soft edge and SAM 2 to hold her through the clip.
- **Sprites.** `tools/rgba.py` turned frames and matte into an RGBA PNG sequence cropped to her. The crop is the union of the matte's boxes, so the sprite never jumps. The edges are despilled, the body gets a solid core, and a feet line lets a chapter stand her on the taskbar.
- **A key while the queue was long.** R07H's GPU matte would have waited about an hour. It was shot on flat green with no green in her outfit, so `tools/chromakey.py` keyed it locally in the meantime. The matte landed before the final render, and v1's sprite is built from it.

How the desktop, the cursor and the sound were built around them is in [xp-desktop-and-sound.md](https://claudia.gallery/record/bliss/xp-desktop-and-sound/).
