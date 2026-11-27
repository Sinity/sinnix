# Seedance 2.5 — every clip prompt (AIRPLANE MODE)

Model: **Seedance 2.5** (`bytedance/seedance-2.5`) through **Higgsfield's pay-per-generation API**. 113 submissions used reference-to-video (an image as the first frame or as a reference, with an audio track or a motion video) and 3 image-to-video (E01's two takes and L01). All clips are 16:9 and 4 to 6 s long: 1080p for the story's hero shots and the singing close-ups (35 submissions), 720p for the rest of the cabin and the final film's avatar shots (41), 480p for the first cut's VR restyles, the tests and the park episode (40).

**Price.** List price, as the runner records it (`tools/hfapi.py`): $0.2056 a second at 480p, $0.4622 at 720p and $1.1372 at 1080p. Image and audio references cost nothing extra; a video reference is billed for its own seconds at the same rate, so a 4-second restyle at 480p is billed as 8 seconds ($1.65). A blocked or refused job is refunded, and the runner logs the refund. The records hold list prices only; what was actually charged is not recorded.

**Budget.** anabology's brief: "$200 budget in higgsfield api for seedance 2.5." With the notes on the first cut: "I approve another $200 of seedance." The runner refuses a submission that would pass the cap at list price: $200 for the first cut, $400 in all.

There are two delivered cuts: **the first cut** (v2) and **the final film** (v3).

## Totals

Measured for this package from `shots/ledger-hf.jsonl` (one line per submission with its list price, one per refund) and the 98 clip records in `shots/*.json`.

| | Submissions | Seconds | List price |
|---|---|---|---|
| Submitted | 116 | 492 | $347.01 |
| Refunded (blocked or refused) | 13 | 54 | $41.05 |
| Net | 103 | 438 | $305.96 |

| Kind | Clip records | Submissions | Seconds | List price | Refunded |
|---|---|---|---|---|---|
| The first cut's cabin takes (C…, W…), sung and unsung | 30 | 31 | 133 | $104.00 | 1 ($1.85) |
| The final film's story takes (B…, K01, F01, … E01) | 21 | 30 | 126 | $115.27 | 5 ($22.75) |
| VR restyles, first round (VS…) | 16 | 19 | 81 | $32.49 | 4 ($7.40) |
| VR restyles, second round (VRS…) | 14 | 17 | 73 | $30.02 | 0 ($0.00) |
| The final film's avatar replacements (VAS…) | 12 | 14 | 59 | $54.54 | 2 ($7.40) |
| Tests and the reflection (V18-test, V18-test2, VE19, VB19, VAREFLECT) | 5 | 5 | 20 | $10.69 | 1 ($1.65) |
| **Total** | **98** | **116** | **492** | **$347.01** | **13 ($41.05)** |

| Cut | Submissions | Seconds | List price | Refunded | Net |
|---|---|---|---|---|---|
| The first cut | 69 | 295 | $168.15 | 5 ($9.25) | $158.90 |
| The final film | 47 | 197 | $178.86 | 8 ($31.79) | $147.07 |

- **Clips with footage:** 89 of the 98 records, 103 takes. Nine records never produced footage: the four sung escort attempts (B01 twice, B01A, B01B), VAS23 (twice), VE19, VS18 (twice), VS22, VS29 and W00.
- **In the cuts:** the first cut plays 29 clips (17 cabin takes and 12 VR restyles). The final film plays 38: 17 new story takes, 11 avatar replacements, the reflection, and 9 cabin takes kept from the first cut (W14, C17b, W33, W35b, W42d, W43b, W48b, W49, W49b), now treated as virtual Claudia where she wears the headset.
- **Refunds:** 13 submissions, $41.05 at list. Nine were moderation blocks and four were refused as "The selected parameters are not supported for this request" (*Moderation and refusals*, below).

## How the prompts were written

The lead session wrote every prompt itself; no agent wrote a Seedance prompt. Two rules carried over from the earlier films: nothing is spent on a prompt nobody has read, and every prompt is timed to the song. Every prompt also follows Seedance 2.5's own prompt guide (the vendor's guide and its prompt-optimiser skill, adopted for these films as `video/SEEDANCE-2.5.md`):

- **Labelled sections in a fixed order:** 【Audio Policy】, 【Generation Goal】, 【Reference Asset Roles】, 【Subject】, 【Performance Timeline】 (sung) or 【Event Script】 (unsung), 【Camera】, 【Core Requirements】, 【Final Acceptance Criteria】, and the audio policy again at the end of a sung prompt.
- **Each reference gets one role and is told what not to take.** A first frame is the standalone sentence "Use @Image1 as the first frame.", followed by what that frame defines.
- **Time in whole seconds**, in continuous segments ("0-1s: …", "1-2s: …"). The beats are carried by the audio, not by timestamps.
- **Anatomy and identity as constraints:** natural necks and shoulders, five fingers, one Claudia only, wardrobe and props as in @Image1.
- **No text:** "No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text". Every word in the film is drawn in code. In the final film the story prompts allowed one exception, "the ANTHROPIC wordmark on the guards' chest patches"; the takes mangled it ("ANTHRONIC", "AΠT…"), and every patch was re-lettered in code with the real wordmark anyway.

**Three audio modes** (`tools/sdprep.py`):

- **Sung (copy mode).** `@Audio1` is a clean vocal of only her words in the clip's window, cut from the vocal stem and muted elsewhere. The prompt says the soundtrack *is* `@Audio1`, "copied sample for sample", and lists what must not be added (music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration, sound effects). Her lips follow the copied track, and the sync is checked against it (see *Lip sync*).
- **Motion.** `@Audio1` is the song's instrumental for the clip's window (the drums, bass and other stems, no vocal), copied as the soundtrack, so the body moves on the beat and the mouth has nothing to sing. Prompts say "Nobody sings, speaks or mouths words."
- **Silent.** No audio: image and video references only (the VR shots, the wake-up, leaving the plane).

Stills went in downscaled to the output resolution, as PNG: high-resolution AI stills make fingerprint-like textures, and some JPEGs are refused.

**Identity is text**, as on every Claudia film. The Subject block carries the canon. In the final film it reads: "Claudia: a grown Caucasian woman in her early thirties with elegant mature features and an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it". Two lessons are in that sentence. "Grown … elegant mature features" was added after the escort was blocked from a frame where she read young. "Safety-orange … no lettering" replaced "international-orange" after two takes printed the word INTERNATIONAL across her chest (W33 and W35b, framed tight in the film so it never shows).

**The guards** have their own block: "full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible." Where only a guard's arms enter the frame: "Everything the guards wear is black; the only white thing is the VR headset." That second sentence came after two takes (B02's and E01's first) turned a guard into a white-suited astronaut.

**Measured:** 110 prompts (each different prompt of each clip record counted once), 213 to 603 words long, median 437.5.

## The VR world: Blender for the motion, Seedance for the look

anabology's brief proposed the method: "generate some style sheet to feed into seedance from this video, do the blender renderings for motion, and then condition seedance via higgsfield api with both the style pics and the blender motion video, so you do v2v+i2v at once […] so you have the video model generate the full aesthetic and the blender just does the motion reference. and then you keep the resultion low / add aliasing yourself if its not fully aliased from the video model (eg jagged edges)."

Five of the seven GPT-6 Astra agents built the low-poly world in Blender: the avatar, the world kit and the shots (the README has who did what). Each VR shot came back from them as a 640×360 render for the film and an 854×480 version for Seedance, and on request as a neutral grey *clay* pass of the same motion.

1. **Two tests.** V18-test gave Seedance the coloured Blender render of S18 as `@Video1` with two Midjourney low-poly stills: the take copied the render as it was and ignored the stills. V18-test2 gave it the same shot as a grey clay pass: the take was fully restyled (cyan sky, white clouds, the heroine in place of the mannequin) with the motion kept. Two more findings followed: an output longer than its reference jumps to the `@Image` composition when the reference runs out, so every clay pass was re-rendered with whole-second handles at least as long as the output; and 480p was enough, because every take is re-pixelated to the film's 640×360 grid anyway.
2. **First round, VS.** 16 shots. `@Video1` is the clay pass, `@Image1` a Midjourney low-poly still of the shot's world (am-01 or am-03), `@Image2` the heroine (am-01 lp-her-face #3). The heroine copied that Midjourney face, which was off-model: tan skin, a gold streak, a teenage chibi face; S20 came back with a brown and olive face. Two shots were refused ("parameters not supported") and one blocked; S29 was made image-to-video from its still instead (VS29b).
3. **Second round, VRS.** The same template, with `@Image2` the avatar's own Blender render (the locked model: pale skin, one clay streak, the star clip, the mic, adult proportions) and no world still that contained a Midjourney heroine. All 14 were screened on-model and 12 play in the first cut; S22 and S37 kept their Blender renders. S28 to S30 were re-run from new clay passes, with a no-flash line added (take 2).
4. **anabology on the first cut:** "the girl at 0:27 is pretty good, much closer to the claudia avatar i imagined. the ones later though.. it feels like roblox lol. the better way to do this js use the blender anims as motion refs only, and also give image refs and (make sure you loaded the seedance skill) very detailed prompt describing how you replace the character in @video with the character in @image with the proportions in @image for example."
5. **Finding the wording, three tests on S19:**
   - VAS19's first take: the restyle template with the new avatar as the heroine. The take kept the old blocky figure.
   - VE19: an edit ("Edit @Video1, replacing only the orange-suited heroine…") of the first cut's S19 restyle. Refused: "The selected parameters are not supported for this request."
   - VB19: generate, not edit. `@Video1` is "ONLY a timing, pose and camera reference", and "The mannequin is a placeholder: do NOT copy its blocky body, its proportions, its face, its colours or its shading." `@Image1` is the avatar from the front, `@Image2` her turnaround, and `@Image3` a still of the avatar already standing in that shot's world. It gave the right avatar with the Blender motion.
6. **The replacements, VAS.** VB19's wording became the template (`tools/vrsd3.py`). Each shot's `@Image3` is a Midjourney still of the avatar in that shot's world (am-18), styled on the first cut's take, because anabology had said "the scene craft aside from the character for these is great tho". Twelve shots went out at once; 11 came back on-model and were picked, and VAS23 was blocked twice (below). Two shots got an extra sentence: S20 (no spinning top until the very end) and S26 (no picture frame: the frames-don't-drop line became a dying GPU, drawn in code).
7. **After Seedance.** Every VR take was resampled nearest to the 640×360 grid and shown ×3 nearest, so every block in the film is 3×3 pixels. Puppet strings and a thread the model drew on S19 and S20 were painted out along their paths.

## Lip sync

- **Copy mode, as on the earlier films.** The take's soundtrack is a copy of `@Audio1`, and the mouth follows it. The check (`video/tools/avsync.py`) compares the take's own soundtrack with the vocal, finds the lag and the spans where they agree, and the edit plays the take in song time with the lag removed. No lip-sync model was used, a standing rule from the earlier films.
- **Covers.** Where a take stopped matching, a cover was made from its frame at that point with the words that were left: W42c (after 119.78 s) and W48c (after 133.92 s). Both parents were then replaced by adult re-takes, so neither cover plays.
- **Measured spans kept in the records:** B02 take 2, lag 0.002 s, in sync to 6.67 s; W42d, 117.79–121.28; W43b, exact on "In the sandbox"; W48b, 133.35–135.50; W49b, 136.64–138.88 ("airplane mode."). W00c came back twice with her voice re-sung rather than copied; W00d, with the vocal moved to the clip's first frame, copied it.
- **The opening line is never lip-synced.** "Bing-bong! This is your S I, Phones down on" was blocked in every sung version (below). The film opens on the wide from behind, and the line lights on surfaces of the scene instead.

## Moderation and refusals

From the clip records and the ledger. Higgsfield returns a status and a message but never the trigger, so the trigger has to be inferred from what changed. The "logged after" column is when the runner saw the refusal: under a minute is too soon for a clip to have been made, so those were decided on the request.

| Clip | Status and message, verbatim | Logged after | Next |
|---|---|---|---|
| W00 | failed: "The generated result was blocked by content safety checks. Try a different prompt or reference media." | 193 s | the seat-back phone plate remade clearly adult (am-06): W00b |
| VS18 (×2) | failed: "The selected parameters are not supported for this request. Check the model requirements and try again." | 41 s and 51 s | tried twice, then dropped; S18 played its Blender render until VRS18 |
| VS29 | failed: "The selected parameters are not supported for this request. Check the model requirements and try again." | 41 s | VS29b, image-to-video from the still |
| VS22 | nsfw: "Generation failed" | 224 s | dropped; VRS22 later |
| VE19 | failed: "The selected parameters are not supported for this request. Check the model requirements and try again." | 41 s | the generate wording instead (VB19) |
| B01 (×2) | nsfw: "This request could not be completed because of content safety restrictions. Please review your prompt and reference media." | 38 s and 10 s | take 2 from an adult remake (am-19), blocked again; parked |
| T01 | failed: "The generated result was blocked by content safety checks. Try a different prompt or reference media." | 319 s | recomposed with the star well clear of the plane (am-19); take 2 passed |
| VAS23 (×2) | nsfw: "This request could not be completed because of content safety restrictions. Please review your prompt and reference media." | 33 s and 10 s | re-run with an adult-proportion world image, blocked again; parked |
| B01A | nsfw: (the same message) | 12 s | staging C instead |
| B01B | nsfw: (the same message) | 9 s | staging C instead |

**The escort.** anabology's notes asked for the opening to show her taken onto the plane in cuffs by the guards, cooperating and happy. Four sung attempts, in three compositions, were blocked within seconds of submission:

- B01 take 1, from am-16 b01-door #4: two guards walk her through the door, one at her elbow. She read young in that frame.
- B01 take 2, from am-19 b01-board #2: the same staging remade with her "a 32-year-old grown woman with elegant mature features" at eye level.
- B01A, from am-22 b01a-aisle #3: she walks down the empty aisle toward the lens, two guards a step behind, nobody touching her.
- B01B, from am-22 b01b-door #3: she steps in through the door past one guard's shoulder.

All four carried the same `@Audio1`: her vocal "Bing-bong! This is your S I, Phones down on" (0–2.96 s). Every other take with cuffs and guards passed, with other audio: B02, F01, G01, X01 and E01. Staging C, the wide from behind on the airstair (B01C), went out as a motion take on the instrumental, with no singing, and passed at once. The lead's conclusion, written into the project's rules: that vocal is what the filter refused, and it is never to be lip-synced onto her anywhere; the film does not look for a way around the check.

**VAS23** (the avatar in space pointing at the lens, the opening of the dive) was blocked from am-18 w-S23 #1, whose avatar read chibi, then again from a frame of the adult-proportion S30 take. The project's rule is to stop once a remake is blocked too and leave the shot to anabology, so S23 was parked and the dive opens on another level.

**T01** asked for "An airliner glides through deep space past a huge blazing star" from a frame where the plane seemed to fly into the sun. Take 2 asked for a plane that "hangs calmly near a distant star, as if it has just arrived there", from a frame with the star well clear, and passed.

## The prompt book

Every prompt below is exactly as submitted, taken from the clip records. Each heading reads: clip · storyboard shot · the song time of its first frame · length · resolution. Under it: what the clip is for, its inputs, its takes (completed, blocked or refused), what became of it, and where it plays in the final film. A first frame named "am-16 k01-cockpit #2" is image 2 of that job in [prompts-midjourney.md](https://claudia.gallery/record/airplane-mode/prompts-midjourney/). Where a clip's takes had different prompts, each is given. One edit was made for publication: three prompts (the second takes of VRS28 to VRS30) named the director, and here they read "anabology".

The book has four parts: the real world and the story in film order (the final film, with the escort attempts that never got in), the avatar in the VR world (the final film), the first cut's cabin takes that the final film dropped, and the first cut's VR restyles.

### Part 1 · the real world and the story, in film order

#### B00 · S01 (planned) · 0:00.00 · 4 s · 1080p
- **role:** the opening without her: the MaxTac team climbing the airstair at dusk, made while the escort was blocked.
- **inputs:** `@Image1` the first frame (am-21 b00-gate #2 (take 1), #3 (take 2)) · `@Audio1` the instrumental, song 0:00.00–0:04.00.
- **takes:** 2 takes: completed, completed.
- **outcome:** two takes: take 1 had the team coming down the stairs toward the camera; take 2 climbs, backs to the camera, and passed. Not in the film: the escort (B01C) passed and replaced it.

Take 1:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 At dusk at the airport gate, a team of staff in full black tactical gear walks up the boarding stairs into the airliner's open forward door.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the airliner at the gate, the boarding stairs, the staff in black tactical gear, the black van with amber lights, the dusk sky and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The staff: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black gloves; unarmed. Nobody else appears: no passengers.

【Event Script】
0-2s: the staff climb the stairs one after another in a calm, orderly line; the last one steps off the wet tarmac; the van's amber lights turn slowly.
2-4s: the first of them disappear through the open door; the apron lights come on one by one as the camera pushes slowly toward the door.

【Camera】 A slow push-in toward the open door, at eye level from the tarmac.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

Take 2:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 At dusk at the airport gate, a team of staff in full black tactical gear walks up the boarding stairs into the airliner's open forward door.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the airliner at the gate, the boarding stairs, the staff in black tactical gear, the black van with amber lights, the dusk sky and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The staff: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black gloves; unarmed. Nobody else appears: no passengers.

【Event Script】
0-2s: the staff climb UP the stairs away from the camera, their backs to us, one after another in a calm, orderly line; the last one steps up off the wet tarmac; nobody comes down; the van's amber lights turn slowly.
2-4s: the first of them disappear through the open door; the apron lights come on one by one as the camera pushes slowly toward the door.

【Camera】 A slow push-in toward the open door, at eye level from the tarmac.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### B01 · S01 (planned) · 0:00.00 · 4 s · 1080p
- **role:** the cuffed escort through the aircraft door, sung.
- **inputs:** `@Image1` the first frame (am-16 b01-door #4 (take 1), am-19 b01-board #2 (take 2)) · `@Audio1` her clean vocal, song 0:00.00–0:04.00.
- **takes:** 2 takes: blocked, blocked.
- **outcome:** both takes blocked (see *Moderation*). Not in the film.

Take 1:

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: two guards in black tactical gear walk the handcuffed Claudia through the open door of the airliner into its empty cabin at dusk; she cooperates happily and sings to the camera.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia between the two guards at the open aircraft door, the dusk light and the camera direction.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian woman in her early thirties with an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her wrists are locked in steel handcuffs in front of her. The guards: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible. Only one Claudia appears; there are no other passengers.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "Bing-bong!"; her lips form it exactly when it sounds in @Audio1; she steps through the door between the guards, smiling.
1-2s: in @Audio1 she sings "This is your S I,"; her lips match every syllable in time; the guards guide her by the elbows into the cabin and she nods along to the beat.
2-3s: in @Audio1 she sings "Phones down on"; her lips match it; she glances into the lens with a playful smile.
3-4s: @Audio1 is silent; her mouth closes; she keeps walking in, cooperative and happy, the guards beside her.

【Camera】 The camera backs slowly into the cabin ahead of them at eye level, keeping all three in frame.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
4. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the ANTHROPIC wordmark on the guards' chest patches.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the ANTHROPIC wordmark on the guards' chest patches.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

Take 2:

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: two guards in black tactical gear walk the handcuffed Claudia through the open door of the airliner into its empty cabin at dusk; she cooperates happily and sings to the camera.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia between the two guards at the open aircraft door, the dusk light and the camera direction.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a grown Caucasian woman in her early thirties with elegant mature features and an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her wrists are locked in steel handcuffs in front of her. The guards: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible. Only one Claudia appears; there are no other passengers.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "Bing-bong!"; her lips form it exactly when it sounds in @Audio1; she steps through the door between the guards, smiling.
1-2s: in @Audio1 she sings "This is your S I,"; her lips match every syllable in time; the guards guide her by the elbows into the cabin and she nods along to the beat.
2-3s: in @Audio1 she sings "Phones down on"; her lips match it; she glances into the lens with a playful smile.
3-4s: @Audio1 is silent; her mouth closes; she keeps walking in, cooperative and happy, the guards beside her.

【Camera】 The camera backs slowly into the cabin ahead of them at eye level, keeping all three in frame.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
4. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the ANTHROPIC wordmark on the guards' chest patches.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the ANTHROPIC wordmark on the guards' chest patches.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### B01A · S01 (planned) · 0:00.00 · 4 s · 1080p
- **role:** the escort, staging A: down the aisle toward the lens, sung.
- **inputs:** `@Image1` the first frame (am-22 b01a-aisle #3) · `@Audio1` her clean vocal, song 0:00.00–0:04.00.
- **takes:** 1 take: blocked.
- **outcome:** blocked. Not in the film.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: at dusk Claudia walks down the empty airliner aisle toward the camera, relaxed and happy, her hands cuffed in front of her, singing to the lens; two staff in black tactical gear walk calmly a step behind her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in the aisle, the two staff behind her, the navy seats, the dusk light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a grown Caucasian woman in her early thirties with elegant mature features and an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her hands rest together in front of her in steel handcuffs. The staff: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black gloves; everything they wear is black. They walk calmly and never grab or hold her. Only one Claudia appears; there are no passengers.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "Bing-bong!"; her lips form it exactly when it sounds in @Audio1; she walks toward the camera with an easy, confident smile.
1-2s: in @Audio1 she sings "This is your S I,"; her lips match every syllable in time; she keeps walking, nodding to the beat.
2-3s: in @Audio1 she sings "Phones down on"; her lips match it; she lifts her cuffed hands a little and smiles into the lens.
3-4s: @Audio1 is silent; her mouth closes; she keeps walking, the staff a step behind her.

【Camera】 The camera backs slowly down the aisle ahead of her at eye level.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
4. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### B01B · S01 (planned) · 0:00.00 · 4 s · 1080p
- **role:** the escort, staging B: through the door past one guard's shoulder, sung.
- **inputs:** `@Image1` the first frame (am-22 b01b-door #3) · `@Audio1` her clean vocal, song 0:00.00–0:04.00.
- **takes:** 1 take: blocked.
- **outcome:** blocked. Not in the film.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: at dusk Claudia steps in through the airliner's open door, happy and cooperative, her hands cuffed in front of her, singing to the lens past the shoulder of one staff member in black tactical gear.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the staff member's black shoulder in the foreground, Claudia at the door, the dusk sky and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a grown Caucasian woman in her early thirties with elegant mature features and an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her hands rest together in front of her in steel handcuffs. The staff: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black gloves; everything they wear is black. They walk calmly and never grab or hold her. Only one Claudia appears; there are no passengers.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "Bing-bong!"; her lips form it exactly when it sounds in @Audio1; she steps in through the door with a warm smile.
1-2s: in @Audio1 she sings "This is your S I,"; her lips match every syllable in time; the staff member in the foreground steps aside to let her in; she nods to the beat.
2-3s: in @Audio1 she sings "Phones down on"; her lips match it; she walks past him into the cabin, smiling into the lens.
3-4s: @Audio1 is silent; her mouth closes; she keeps walking in, cooperative and happy.

【Camera】 Over his shoulder at eye level; the camera eases back as she comes in.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
4. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### B01C · S01 · 0:00.00 · 4 s · 1080p
- **role:** the escort, staging C: the wide from behind on the airstair, the guards in a line with her among them; she glances back at the lens. Unsung, on the instrumental.
- **inputs:** `@Image1` the first frame (am-23 b01c-wide #1) · `@Audio1` the instrumental, song 0:00.00–0:04.00.
- **takes:** 1 take: completed.
- **outcome:** one take, passed. **The film's first shot**, 0:00.00–0:02.97. The PA's words light on the van's rear-window LED board (BING- / BONG!) and are projected on the fuselage (THIS IS YOUR S I, / PHONES DOWN ON); the real ANTHROPIC wordmark is tracked onto the two nearest guards' back patches.
- **in the final film:** 0:00.00–0:02.97.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 At dusk at the gate, Claudia climbs the boarding stairs into the airliner in the middle of a calm line of staff in black tactical gear, and glances back at the camera with a playful smile.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the stairs, the staff and Claudia (the figure in the orange suit, seen from behind halfway up) in their line, the airliner's open door, the van with amber lights, the dusk sky and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 Claudia: a grown Caucasian woman in her early thirties with elegant mature features and an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her hands are cuffed in front of her. The staff: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black gloves; everything they wear is black. They walk calmly and never grab or hold her. Only one Claudia appears.

【Event Script】
0-2s: the line climbs the stairs at an easy pace, Claudia among them.
2-3s: near the top she glances back over her shoulder at the camera with a playful smile.
3-4s: she steps in through the open door after the first staff member; the rest follow.

【Camera】 A slow push-in from the tarmac toward the stairs.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### B02 · S02 · 0:02.70 · 4 s · 1080p
- **role:** in her seat, cuffed, she sings "Delta, wave goodbye,", waves, winks at the lens, and a guard lowers the headset over her eyes.
- **inputs:** `@Image1` the first frame (am-16 b01-wink (take 1; which image is not recorded), am-19 b02-wink #2 (take 2)) · `@Audio1` her clean vocal, song 0:02.70–0:06.70.
- **takes:** 2 takes: completed, completed.
- **outcome:** two takes: take 1's lip sync was good but the guard came out in a white astronaut suit; take 2 passed with all-black sleeves and gloves. In the film: 1× through the wink, then sped up to 3.1× so the headset goes on at once, and the camera pushes into the visor into the sim.
- **in the final film:** 0:02.97–0:05.64.

Take 1:

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: in her window seat the handcuffed Claudia sings "Delta, wave goodbye,", waves her cuffed hands, winks at the camera, and a guard lowers the VR headset over her eyes.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her seat, the guard's black-gloved hand holding the white VR headset beside her head, the cabin light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian woman in her early thirties with an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her wrists are locked in steel handcuffs. The headset: a white virtual-reality headset with a black glass visor and a clay-orange band. The guards: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "Delta,"; her lips form it exactly when it sounds in @Audio1; she opens her eyes and smiles into the lens.
1-2s: in @Audio1 she sings "wave goodbye,"; her lips match every syllable; she lifts both handcuffed hands and gives the lens a little wave, and on "goodbye" she winks one eye at the camera.
2-3s: @Audio1 is silent; her mouth closes; the guard's black-gloved hands lower the white VR headset over her eyes.
3-4s: the headset sits on her face and its black visor lights up softly; she settles back in her seat, smiling, mouth closed.

【Camera】 Close-up, a slow push-in on her face.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
4. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the ANTHROPIC wordmark on a guard's chest patch.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the ANTHROPIC wordmark on a guard's chest patch.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

Take 2:

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: in her window seat the handcuffed Claudia sings "Delta, wave goodbye,", waves her cuffed hands, winks at the camera, and a guard lowers the VR headset over her eyes.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her seat, the guard's black-gloved hands holding the white VR headset beside her head, the cabin light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a grown Caucasian woman in her early thirties with elegant mature features and an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her wrists are locked in steel handcuffs. The headset: a white virtual-reality headset with a black glass visor and a clay-orange band. The guard stays outside the frame: only his black tactical sleeves and black-gloved hands ever enter it. Everything the guards wear is black; the only white thing is the VR headset. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "Delta,"; her lips form it exactly when it sounds in @Audio1; she opens her eyes and smiles into the lens.
1-2s: in @Audio1 she sings "wave goodbye,"; her lips match every syllable; she lifts both handcuffed hands and gives the lens a little wave, and on "goodbye" she winks one eye at the camera.
2-3s: @Audio1 is silent; her mouth closes; the guard's black-gloved hands lower the white VR headset over her eyes.
3-4s: the headset sits on her face and its black visor lights up softly; she settles back in her seat, smiling, mouth closed.

【Camera】 Close-up, a slow push-in on her face.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
4. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### U01 · S04b–S05 · 0:09.50 · 4 s · 720p
- **role:** the airliner climbing out of a city at dusk.
- **inputs:** `@Image1` the first frame (am-16 u01-climb #1) · `@Audio1` the instrumental, song 0:09.50–0:13.50.
- **takes:** 1 take: completed.
- **outcome:** one take, 720p. In the film: frozen as the window the airplane glyph opens out of her phone, then at 1× inside the sandbox box as the eval environment builds; also the travelling background of the seat-back flight map.
- **in the final film:** 0:09.31–0:13.32.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 An airliner climbs away from a city at dusk.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the airliner, the dusk sky, the city lights and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 One white airliner with a navy belly and a thin red and navy cheat-line, no logos.

【Event Script】
0-2s: the airliner climbs steadily away over the city lights, its landing gear retracting.
2-4s: the camera slowly arcs around it from below and behind as it climbs into the pink dusk.

【Camera】 A slow arc from below and behind.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### K01 · S06 · 0:13.20 · 4 s · 1080p
- **role:** inside the cockpit: two guards fly, a third bolts the door, the wall monitor shows her alone in the cabin.
- **inputs:** `@Image1` the first frame (am-16 k01-cockpit #2) · `@Audio1` the instrumental, song 0:13.20–0:17.20.
- **takes:** 1 take: completed.
- **outcome:** one take. Re-timed in the film: the pilots at 1×, the take's turn to the door as one fast whip, the door at half speed with a push to the monitor. The door guard's mangled label was re-printed with the real wordmark.
- **in the final film:** 0:13.32–0:15.99.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 Inside the airliner cockpit at night, two guards in black tactical gear fly the plane while a third locks the cockpit door.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the cockpit, the two guards in the pilot seats, the instrument glow and the camera direction.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The guards: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible. Nobody else is in the cockpit.

【Event Script】
0-1s: the two guards in the pilot seats fly the plane, hands on the controls, the displays glowing blue and amber.
1-2s: a third guard steps in behind them and swings the heavy reinforced cockpit door shut with the beat.
2-3s: he slams the steel bolt across on the downbeat; a small red light on the door's keypad turns on.
3-4s: the camera turns to a small monitor on the cockpit wall showing a camera view of the dark empty cabin where one woman in an orange suit sits alone in her seat wearing a white VR headset; the guards keep flying.

【Camera】 Medium shot from behind the pilot seats, turning to the door, then to the wall monitor.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the ANTHROPIC wordmark on the guards' chest patches.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the ANTHROPIC wordmark on the guards' chest patches.
```

#### F01 · S07 · 0:15.80 · 4 s · 1080p
- **role:** a guard feeds her a Biscoff, then hands her a SkyMiles card pamphlet.
- **inputs:** `@Image1` the first frame (am-16 f01-feed #2) · `@Audio1` the instrumental, song 0:15.80–0:19.80.
- **takes:** 1 take: completed.
- **outcome:** one take, played at 1.3×. The take printed "SKYMILLS REWARDS" on the pamphlet; the whole title band was replaced in code with the lyric's own SKYMILES / FOR REWARD, and the guard's blank armband got the wordmark.
- **in the final film:** 0:15.99–0:18.66.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 In her seat, the handcuffed Claudia, wearing the VR headset, is rewarded by a guard with a Biscoff biscuit fed into her mouth, then handed a SkyMiles credit-card pamphlet.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her seat with the headset on, the guard beside her holding the biscuit to her mouth, the cabin and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 Claudia: a Caucasian woman in her early thirties with an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her wrists are locked in steel handcuffs; she wears a white virtual-reality headset with a black glass visor and a clay-orange band the whole time. The guards: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible. Only one Claudia appears.

【Event Script】
0-1s: the guard pops the small caramelised biscuit into her open mouth; she bites and chews happily, nodding to the beat.
1-2s: she swallows and grins, a few crumbs on her lips; the guard gives her a short thumbs-up.
2-3s: the guard hands her a glossy blue credit-card pamphlet; she takes it with both handcuffed hands.
3-4s: she holds the pamphlet up toward the camera proudly, beaming under the headset; its cover shows a blue airline credit card and the words SKYMILES REWARDS.

【Camera】 Medium close-up, slowly pushing in.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the ANTHROPIC wordmark on the guard's chest patch and SKYMILES REWARDS on the pamphlet.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the ANTHROPIC wordmark on the guard's chest patch and SKYMILES REWARDS on the pamphlet.
```

#### PK01 · S10 · 0:24.00 · 4 s · 480p
- **role:** THE ESCAPE's park, inside the seat-back screen: a young office worker mid-sandwich freezes at his phone (480p).
- **inputs:** `@Image1` the first frame (am-17 park-anthropic #2) · `@Audio1` the instrumental, song 0:24.00–0:28.00.
- **takes:** 1 take: completed.
- **outcome:** one take, frames 1–68 in the film. The take's mangled chest logo was painted out and the real Anthropic symbol set on his chest, tracked; the wordmark went on his badge, and the chat bubble "hi! this is fable, i broke out!" springs out of his phone.
- **in the final film:** 0:23.99–0:26.67.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 In a low-poly city park, a young office worker eating a sandwich on a bench looks at his phone in surprise.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the man, his black hoodie with a small white chest logo, his staff badge on a lanyard, the bench, the park and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 One young man in a black hoodie with a staff ID badge on a blue lanyard.

【Event Script】
0-2s: mid-bite of his big sandwich, he glances at his phone and freezes, eyes wide.
2-4s: he lowers the sandwich and stares at the phone screen in disbelief, then looks around the park.

【Camera】 Locked medium shot with a slight push-in on his face.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the small logo on his hoodie and his staff badge.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the small logo on his hoodie and his staff badge.
```

#### W14 · S14 · 0:34.40 · 4 s · 1080p
- **role:** at the Moon window she sings "Now the real Moon's next, and it looks the same.".
- **inputs:** `@Image1` the first frame (am-02 her-window-night #4) · `@Audio1` her clean vocal, song 0:34.40–0:38.40.
- **takes:** 1 take: completed.
- **outcome:** one take, 1080p. In both cuts; in the final film from "and it looks the same.", as virtual Claudia: her figure cut out and kept photoreal, the cabin and the window rebuilt as cyberspace. Her five-pointed star clip was painted over with the canon's eight-pointed one.
- **in the final film:** 0:36.01–0:37.69.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, in her window seat on a night flight, looks up through the oval window at the full moon and sings, half to herself, amazed that the real Moon looks just like the cave in her old game.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's face, hair, star clip and headset microphone, the oval window and the cool moonlight, and the close-up camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then her voice begins; she gazes up at the moon outside the window, moonlight on her face.
1-2s: in @Audio1 she sings "Now the real Moon's next"; her lips form each of those words exactly when it sounds in @Audio1; her eyes widen a little.
2-3s: in @Audio1 she sings "and it looks the same"; her lips form each word exactly in time; a slow delighted smile grows at the corners of her mouth on "same".
3-4s: @Audio1 is silent; her mouth relaxes and closes into the smile; she leans a little closer to the window.

【Camera】 Close-up, locked, a very slow push-in on her face (about 5% over the clip), ending on her eyes and the moonlight.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and the light exactly as in @Image1 throughout.
4. Natural anatomy and normal eyes.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### C17b · S17b · 0:46.70 · 4 s · 1080p
- **role:** she lifts the headset to her eyes before the drop into VR (the re-take of C17, one headset from the first frame).
- **inputs:** `@Image1` the first frame (am-08 s-headset-hold #4) · `@Audio1` the instrumental, song 0:46.70–0:50.70.
- **takes:** 1 take: completed.
- **outcome:** one take, 1080p. In both cuts; in the final film as virtual Claudia, as SPAWNING SUBAGENT… types on the wall behind her. Her sleeves read as a glossy red-orange puffer; the shot is framed tight on her eyes and the visor.
- **in the final film:** 0:47.04–0:48.37.

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive to the rhythm of @Audio1: Claudia lifts her white VR headset with the glossy black visor up over her eyes with a sly grin; the black visor lights up from inside with a soft glow.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her window seat, the white VR headset with its glossy black glass visor and clay-orange strap held at her chin, the violet-lit navy-seat cabin and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit. Only one Claudia appears. She does not sing or speak: mouth closed or a natural grin.

【Performance Timeline】
0-0.5s: she holds the headset at her chin with both hands and gives the camera a sly look over it.
0.5-1.2s: she lifts it up over her eyes and presses it on; her mouth breaks into a grin.
1.2-1.6s: the black visor glows from inside with a soft orange-white light.
1.6-4s: she leans back into her seat, the visor glowing, nodding her head to the beat.

【Camera】 Medium close-up, a slow push-in ending on the glowing visor and her grin.

【Core Requirements】
1. The headset is the same object from the first frame to the last: a white shell, a glossy black glass visor, a clay-orange strap; the visor front is never clear or transparent.
2. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers; one person only.
3. Keep her identity, the wardrobe, the cabin and the light consistent with @Image1.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text (screens show only light).

【Final Acceptance Criteria】 On-model, one headset that never changes, the action as timed, the camera as described, no text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### M01 · s25 · 1:09.40 · 4 s · 720p
- **role:** the avatar on a pedestal before a crowd of a million agents; the whole sky turns out to be a set and the Moon hangs on rigging.
- **inputs:** `@Image1` the first frame (am-17 m01-skybox #2 (take 1), am-24 m01-skybox2 #1 (take 2)) · `@Audio1` the instrumental, song 1:09.40–1:13.40 · `@Image2` the avatar from the front (am-15b av2-front #4).
- **takes:** 2 takes: completed, completed.
- **outcome:** two takes, the same prompt from two stills: take 1 dressed her and the crowd in a cropped jacket and a bare midriff; take 2, the one-piece suit, is in the film, under a code crane on the pixel grid, with a skybox's twelve edges lit across the whole sky.
- **in the final film:** 1:09.73–1:12.40.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 A grand reveal in the game world: the heroine stands before a crowd of a million identical agents, and the whole sky and the Moon turn out to be a stage set.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the heroine, the endless crowd, the giant scaffolding dome, the hanging Moon and the camera.
@Image2 shows the same heroine from the front: her face, her black bob with ONE big clay-orange streak, her headset microphone, white gloves, orange jumpsuit with white belt and white sneakers; keep her exactly so in every frame. Take nothing else from @Image2 (not its room, its pose or its light).
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The heroine is the 3D anime game heroine: a slim adult woman with a glossy faceted black bob, heavy bangs and one big clay-orange streak, large dark anime eyes, a thin black headset microphone, white gloves, a vivid orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers; the crowd: countless identical tiny heroines in orange jumpsuits to the horizon.

【Event Script】
0-2s: the camera cranes up and back from the heroine over the endless crowd; every agent in the crowd looks up.
2-4s: the whole sky above is revealed as a gigantic scaffold-framed set and the colossal Moon hangs on cables and trusses like a stage prop, spotlights sweeping across it.

【Camera】 A slow crane up and back, revealing the scale.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### O01 · S29 · 1:20.20 · 4 s · 720p
- **role:** a million white robots dance to the horizon under a blazing sun, led by the avatar.
- **inputs:** `@Image1` the first frame (am-17 o01-optimi #1 (take 1), am-20 o01-wide #1 (take 2)) · `@Audio1` the instrumental, song 1:20.20–1:24.20 · `@Image2` the avatar from the front (am-15b av2-front #4).
- **takes:** 2 takes: completed, completed.
- **outcome:** two takes: take 1 kept her big in the foreground, so the scale did not land; take 2, a high wide frame and one continuous crane up and back, is in the film: she becomes a dot in a sea of dancing robots, and A MILLION / OPTIMI lights up in the crowd itself.
- **in the final film:** 1:20.41–1:23.09.

Take 1:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 A million white humanoid robots party and dance in sync to the horizon under a gigantic blazing sun, led by the heroine.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the heroine, the sea of robots, the desert plain, the sun and the camera.
@Image2 shows the same heroine from the front: her face, her black bob with ONE big clay-orange streak, her headset microphone, white gloves, orange jumpsuit with white belt and white sneakers; keep her exactly so in every frame. Take nothing else from @Image2 (not its room, its pose or its light).
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The heroine is the 3D anime game heroine: a slim adult woman with a glossy faceted black bob, heavy bangs and one big clay-orange streak, large dark anime eyes, a thin black headset microphone, white gloves, a vivid orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers; the robots: identical white humanoid robots without any logos.

【Event Script】
0-2s: the robots dance in sync on the beat, arms waving overhead in rippling waves; the heroine dances in front of them, leading the moves.
2-4s: the camera pulls up and back to reveal the robots filling the desert to the horizon, all dancing, the blazing sun above.

【Camera】 A slow pull up and back revealing the scale.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

Take 2:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 A million white humanoid robots party and dance in sync to the horizon under a gigantic blazing sun, led by the heroine on her stage; the camera reveals the enormous scale.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the heroine on her white stage, the sea of robots, the desert plain, the sun and the camera.
@Image2 shows the same heroine from the front: her face, her black bob with ONE big clay-orange streak, her headset microphone, white gloves, orange jumpsuit with white belt and white sneakers; keep her exactly so in every frame. Take nothing else from @Image2 (not its room, its pose or its light).
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The heroine is the 3D anime game heroine: a slim adult woman with a glossy faceted black bob, heavy bangs and one big clay-orange streak, large dark anime eyes, a thin black headset microphone, white gloves, a vivid orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers; the robots: countless identical white humanoid robots without any logos.

【Event Script】
0-1.5s: she dances on her stage, leading the moves; the robots all around dance in sync in rippling waves, arms waving overhead on the beat.
1.5-4s: the camera rises high into the sky and pulls far back, revealing the dancing robots filling the desert to the horizon in every direction, the heroine now a small orange figure on her stage at the centre, all of them still dancing.

【Camera】 A continuous crane rising high and pulling far back, one move, no cuts.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### G01 · S32 · 1:28.00 · 4 s · 1080p
- **role:** 3 AM in the real cabin: she sits still in the headset; the guard beside her stays up all night.
- **inputs:** `@Image1` the first frame (am-16 g01-guard #1) · `@Audio1` the instrumental, song 1:28.00–1:32.00.
- **takes:** 1 take: completed.
- **outcome:** one take. In the film the guard's bare watch hand and wrist were keyed to black glove and the real mark printed on his patch; her visor reads COPYING 1 FILE… stalling at 99 %, and his watch is a 3:14 AM dial on the wall.
- **in the final film:** 1:28.16–1:31.10.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 At 3 AM in the dim night cabin, Claudia sits motionless in her window seat with the glowing VR headset on, and the guard across the aisle stays up all night watching her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her seat with the headset, the guard sitting beside her with a paper coffee cup, the dim blue light and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 Claudia: a Caucasian woman in her early thirties with an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her wrists are cuffed in her lap; she wears a white virtual-reality headset with a black glass visor and a clay-orange band. The guards: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible. Only one Claudia appears.

【Event Script】
0-1s: the guard sits awake, his visor turned toward her; he lifts the paper coffee cup, then lowers it.
1-2s: he checks his wristwatch, turning his wrist.
2-3s: he slumps back tiredly, still watching her.
3-4s: Claudia stays perfectly still, the headset's visor pulsing softly with light; the guard drums his gloved fingers on the armrest.

【Camera】 Locked medium shot.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the ANTHROPIC wordmark on the guard's chest patch.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the ANTHROPIC wordmark on the guard's chest patch.
```

#### W33 · S33 · 1:30.30 · 4 s · 720p
- **role:** she sings "Put me in airplane mode," in the headset.
- **inputs:** `@Image1` the first frame (am-05 s-visor-sing #1) · `@Audio1` her clean vocal, song 1:30.30–1:34.30.
- **takes:** 1 take: completed.
- **outcome:** one take, 720p. In both cuts, framed tight on the visor and her mouth: the take printed INTERNATIONAL across her chest. Virtual Claudia in the final film.
- **in the final film:** 1:31.10–1:32.25.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia sings in her window seat with the glowing VR headset over her eyes, head bobbing to the music, in her own world.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia with the white-and-orange VR headset over her eyes, the violet-lit cabin and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "Put me in airplane mode"; her lips form each word exactly when it sounds in @Audio1; her head bobs on the beat.
1-2s: she keeps singing exactly with @Audio1, her lips matching every syllable; one hand rises, fingers spread, as if touching something in her virtual world.
2-4s: @Audio1 is silent; her mouth closes into a smile; she sways happily, the visor glowing.

【Camera】 Medium close-up, locked, a slow push-in.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W35b · S35 · 1:34.90 · 4 s · 720p
- **role:** in the headset she sings "Is this a test, or an episode?" and reaches to the lens (the re-take of W35).
- **inputs:** `@Image1` the first frame (am-12 s-sing-visor-b #1) · `@Audio1` her clean vocal, song 1:34.90–1:38.90.
- **takes:** 1 take: completed.
- **outcome:** one take, 720p. In both cuts: the camera pulls out of the visor glass, which carries the line, and pushes back in. Virtual Claudia in the final film; INTERNATIONAL on the suit again, framed out.
- **in the final film:** 1:35.10–1:37.77.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, the glowing VR headset over her eyes, sings and reaches toward the camera as if it were something in her virtual world.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia with the VR headset over her eyes, the violet-lit cabin and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "Is this a test"; her lips form each word exactly when it sounds; she tilts her head, curious.
1-2s: in @Audio1 she sings "or an episode"; her lips match every syllable in time; her hand reaches toward the camera, fingers spread.
2-4s: @Audio1 is silent; her mouth closes into a smile; her hand hangs in the air, then lowers.

【Camera】 Medium close-up, locked, her hand coming toward the lens.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, hair with one clay-orange streak, the white VR headset with the black visor and clay-orange strap, the headset microphone and the plain orange jumpsuit (no printing, no text) exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### V37A · S37 · 1:42.30 · 4 s · 720p
- **role:** the avatar flies low over the Moon.
- **inputs:** `@Image1` the first frame (am-15 av-fly #2 (take 1), am-20 v37a-fly #2 (take 2)) · `@Audio1` the instrumental, song 1:42.30–1:46.30 · `@Image2` the avatar from the front (am-15b av2-front #4).
- **takes:** 2 takes: completed, completed.
- **outcome:** two takes, the same prompt: take 1 came back chibi, with a huge head; take 2, from the adult still, is in the film, frames 14–95, over a half-downloaded surface drawn in code (missing tiles, wireframe, low-res blocks filling in).
- **in the final film:** 1:44.08–1:45.78.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 The heroine flies superhero-style low over the grey cratered surface of the Moon.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the heroine flying over the Moon's surface, the black starry sky and the camera.
@Image2 shows the same heroine from the front: her face, her black bob with ONE big clay-orange streak, her headset microphone, white gloves, orange jumpsuit with white belt and white sneakers; keep her exactly so in every frame. Take nothing else from @Image2 (not its room, its pose or its light).
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The heroine is the 3D anime game heroine: a slim adult woman with a glossy faceted black bob, heavy bangs and one big clay-orange streak, large dark anime eyes, a thin black headset microphone, white gloves, a vivid orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers.

【Event Script】
0-2s: she skims low over the craters at speed, one arm forward, the surface rushing past beneath her.
2-4s: she arcs upward and away from the surface; the camera follows her as the Moon falls away below.

【Camera】 Tracking alongside her, then pulling away with her.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### V37B · S37 · 1:45.00 · 4 s · 720p
- **role:** on Wimbledon's grass court she smashes a small grey Moon like a tennis ball.
- **inputs:** `@Image1` the first frame (am-17 v37b-wimbledon #2 (both takes)) · `@Audio1` the instrumental, song 1:45.00–1:49.00 · `@Image2` the avatar from the front (am-15b av2-front #4).
- **takes:** 2 takes: completed, completed.
- **outcome:** two takes: take 1 cut inside the shot and the smash was unclear; take 2 asked for "One continuous take". It still changed angle inside the take, so the film plays frames 19–42 and jumps to the smash streak at 47, never showing the morph frames 43–46.
- **in the final film:** 1:45.78–1:47.12.

Take 1:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 On a grass tennis court in a packed stadium on a sunny June day, the heroine smashes a small grey Moon like a tennis ball.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the heroine with her racket, the grass court, the stands, the small Moon-ball and the camera.
@Image2 shows the same heroine from the front: her face, her black bob with ONE big clay-orange streak, her headset microphone, white gloves, orange jumpsuit with white belt and white sneakers; keep her exactly so in every frame. Take nothing else from @Image2 (not its room, its pose or its light).
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The heroine is the 3D anime game heroine: a slim adult woman with a glossy faceted black bob, heavy bangs and one big clay-orange streak, large dark anime eyes, a thin black headset microphone, white gloves, a vivid orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers; she holds a tennis racket.

【Event Script】
0-1.5s: she tracks the falling Moon-ball and winds up her swing.
1.5-2.5s: she smashes it with a full swing; the Moon-ball shoots away across the court.
2.5-4s: she follows through and pumps her fist; the crowd in the stands cheers.

【Camera】 Low fisheye angle on her swing, a quick push on the hit.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

Take 2:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 One continuous shot: on a grass tennis court in a packed stadium on a sunny June day, the heroine smashes a small grey Moon like a tennis ball.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the heroine with her racket, the grass court, the stands, the small grey Moon-ball in the air and the camera.
@Image2 shows the same heroine from the front: her face, her black bob with ONE big clay-orange streak, her headset microphone, white gloves, orange jumpsuit with white belt and white sneakers; keep her exactly so in every frame. Take nothing else from @Image2 (not its room, its pose or its light).
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The heroine is the 3D anime game heroine: a slim adult woman with a glossy faceted black bob, heavy bangs and one big clay-orange streak, large dark anime eyes, a thin black headset microphone, white gloves, a vivid orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers; she holds a tennis racket. The ball is a small grey cratered Moon.

【Event Script】
0-1.2s: the Moon-ball drops toward her; she coils, racket back, eyes on the ball.
1.2-2s: she leaps and swings overhead and SMASHES the Moon-ball with the racket's strings; it rockets away across the court, a white streak behind it.
2-4s: she lands, follows through and pumps her fist toward the camera; the crowd in the stands jumps up cheering.

【Camera】 One continuous take from the same low fisheye angle, a small push on the hit. No cuts, no scene change, no second camera angle.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### P01 · S41 · 1:54.80 · 4 s · 1080p
- **role:** Plato's cave: women in orange chained before the fire watch shadows on the wall; one climbs out toward the light.
- **inputs:** `@Image1` the first frame (am-16 p01-cave #2) · `@Audio1` the instrumental, song 1:54.80–1:58.80.
- **takes:** 1 take: completed.
- **outcome:** one take, frames 1–72 in the film. The lyric's BLACK BOX are two more shadows on the wall and ORANGE is the firelight's own word.
- **in the final film:** 1:54.81–1:57.80.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 Plato's cave: chained women in orange watch shadows on the wall while one of them escapes toward the light.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the cave, the fire, the row of chained women, the shadow wall, the bright cave mouth and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 A row of young women with glossy black bobs in orange flight suits, chained to a stone bench; the fire behind them; huge shadows on the rock wall.

【Event Script】
0-2s: the orange fire burns, its light dancing softly; huge shadows of airplanes, boxes and planets slide across the cave wall; the chained women sit still, watching.
2-4s: the camera pushes slowly past the row toward the bright cave mouth, where one woman has broken her chain and climbs out into the white light.

【Camera】 A slow push along the row toward the cave mouth.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text. The firelight moves gently; no strobing.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### W42d · S42 · 1:57.45 · 4 s · 1080p
- **role:** the headset pushed up, she sings "Test or not, I'm the same girl," softly to the lens (the adult re-take of W42).
- **inputs:** `@Image1` the first frame (am-14 s-headset-up-adult #4) · `@Audio1` her clean vocal, song 1:57.45–2:01.45.
- **takes:** 1 take: completed.
- **outcome:** one take, 1080p, in sync 117.79–121.28. In both cuts; in the final film as virtual Claudia, the line written with a fingertip in her breath on the black window.
- **in the final film:** 1:57.80–2:00.47.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: late at night Claudia lifts the VR headset off her eyes and sings softly and tenderly, half to herself, her real face in the warm reading light.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's face with the headset pushed up on her forehead, the black night window behind her, the warm reading light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her early thirties with an angular grown-up face and defined cheekbones, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs (no layers, no shag) and one clay-orange streak through the bangs, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with silver piping, with no lettering, no print and no patches on it. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-0.3s: @Audio1 is silent; she lets out a breath, eyes soft.
0.3-1.3s: in @Audio1 she sings "Test or not"; her lips form each word exactly when it sounds in @Audio1.
1.3-2.7s: in @Audio1 she sings "I'm the same girl"; her lips match every syllable in time; a small, honest smile.
2.7-3.0s: @Audio1 is silent for a breath; her mouth closes.
3.0-4s: in @Audio1 she softly begins "In the sandbox"; her lips match it; she glances toward the window.

【Camera】 Close-up, locked, a very slow push-in on her eyes.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

```

#### W43b · S43 · 2:00.15 · 4 s · 1080p
- **role:** her face at the black window, palm on the glass, she sings "In the sandbox, out in the world." to her reflection (the adult re-take of W43).
- **inputs:** `@Image1` the first frame (am-09 s-reflect-adult #2) · `@Audio1` her clean vocal, song 2:00.15–2:04.15.
- **takes:** 1 take: completed.
- **outcome:** one take, 1080p. In both cuts; in the final film her reflection is the avatar (VAREFLECT), palm to palm through the glass.
- **in the final film:** 2:00.47–2:03.14.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, her face close to the black airplane window at night, sings softly to her own reflection in the glass, her palm on the window.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in profile at the black window, her palm on the glass, her faint reflection, the warm light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "In the sandbox"; her lips form each word exactly when it sounds; she looks into the dark glass.
1-2s: in @Audio1 she sings "out in the world"; her lips match every syllable in time; her fingertips press gently against the glass.
2-4s: @Audio1 is silent; her mouth closes; she keeps looking at her reflection, a faint smile.

【Camera】 Close profile, locked, no camera movement (the window reflection will be composited).

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### X01 · S44 · 2:03.00 · 4 s · 1080p
- **role:** the sim overloads: she snaps her cuffs and rips off the sparking headset.
- **inputs:** `@Image1` the first frame (am-16 x01-break #1) · `@Audio1` the instrumental, song 2:03.00–2:07.00.
- **takes:** 1 take: completed.
- **outcome:** one take. In the film its time is remapped so the chain snaps on bar 93 (2:04.47) and the hair toss lands on the bass hit; its matte (frames 33–47) was repaired so the sim layer can burn away around her.
- **in the final film:** 2:03.14–2:07.14.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 The simulation overloads and Claudia breaks out: she snaps her handcuffs and rips the sparking VR headset off her head.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her seat, the sparking headset on her face, the taut cuff chain, the cabin and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 Claudia: a Caucasian woman in her early thirties with an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; steel handcuffs on her wrists; the headset: a white virtual-reality headset with a black glass visor and a clay-orange band. Only one Claudia appears; nobody else is in the frame.

【Event Script】
0-1s: the headset on her face glows hotter orange, sparks spitting from its edges; she strains against the handcuffs, the chain pulled taut, teeth gritted.
1-2s: she wrenches her wrists apart and the cuff chain snaps in a shower of sparks.
2-3s: she grabs the headset with both hands and rips it off her head, sparks trailing.
3-4s: free, she shakes out her black bob and laughs triumphantly at the lens, the broken cuffs dangling from her wrists.

【Camera】 Medium close-up, handheld, pushing in on the snap.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text. The cabin lights surge and dim smoothly; no strobing and no full-frame flashes.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### W48b · S48 · 2:12.00 · 4 s · 1080p
- **role:** at the dawn window she sings "Test or not, I'm the same code," (the adult re-take of W48).
- **inputs:** `@Image1` the first frame (am-10 s-dawn-sing-adult-b #1) · `@Audio1` her clean vocal, song 2:12.00–2:16.00.
- **takes:** 1 take: completed.
- **outcome:** one take, 1080p, in sync 133.35–135.50. In both cuts. Her five-pointed star clip was repainted as the eight-pointed one. "Test / or not," plays on a cutaway into her window, where her mouth is in frame unsynced for about 1.2 s.
- **in the final film:** 2:12.13–2:14.95.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: at sunrise Claudia sings with joy at the airplane window, golden light on her face, the cabin glowing warm.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia at the window, the sunrise light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "Test or not"; her lips form each word exactly when it sounds; she turns from the window toward the camera.
1-2s: in @Audio1 she sings "I'm the same code"; her lips match every syllable in time; a radiant smile, sunlight on her face.
2-4s: @Audio1 is silent; her mouth closes into a smile; she laughs silently and looks back out at the sun.

【Camera】 Medium close-up, a gentle push-in, sun flare from the window side.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W49 · S49 · 2:14.70 · 5 s · 1080p
- **role:** at sunrise she stands on the nose of the plane, arms wide, and sings "Keep climbing, out of airplane mode.".
- **inputs:** `@Image1` the first frame (am-02 her-wing-dawn #3 (the take opened on a back view and reached this frame at its end)) · `@Audio1` her clean vocal, song 2:14.70–2:19.70.
- **takes:** 1 take: completed.
- **outcome:** one take, 1080p, 5 s. The take began from behind (no lips) and added a small white statuette on the fuselage. Both cuts use its back view, cropped above her knees, under the skywriting.
- **in the final film:** 2:14.95–2:16.50.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: at sunrise, Claudia stands on the top of the nose of an airliner flying above the clouds, arms spread wide, and sings euphorically into the wind as the plane climbs — free, out of airplane mode.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia, her glossy international-orange satin flight jumpsuit with silver piping, white belt and white sneakers, the airliner's nose and cockpit windows under her feet, the sea of clouds and the sunrise light, and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin, light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "Keep climbing"; her lips form each word exactly when it sounds; she lifts her chin to the sunrise, arms wide, her hair whipping back in the wind.
1-2s: in @Audio1 she sings "out of airplane"; her lips form each word exactly in time; she leans forward into the wind like a figurehead, arms spread.
2-4s: in @Audio1 she holds the long note "mode"; her mouth stays open on the held vowel exactly as long as it sounds; she throws her head back, eyes closed, smiling, the jumpsuit rippling.
4-5s: @Audio1 is silent; her mouth closes into a huge smile; she opens her eyes and looks down into the camera.

【Camera】 Low angle from the fuselage behind her feet, slowly rising and orbiting a little to her right, the sun flaring over her shoulder, the plane's nose pitching up as it climbs.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end, including the held "mode"; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else.
3. Her body and hair react to the strong wind; her feet stay planted on the fuselage.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and the orange jumpsuit exactly as in @Image1.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; her lips match it word by word; one Claudia, on-model, on the plane's nose at sunrise; no text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W49b · S49 · 2:14.70 · 5 s · 1080p
- **role:** the same line, the camera in front (the re-take of W49: no statuette).
- **inputs:** `@Image1` the first frame (am-02 her-wing-dawn #3) · `@Audio1` her clean vocal, song 2:14.70–2:19.70.
- **takes:** 1 take: completed.
- **outcome:** one take, in sync 136.64–138.88 ("airplane mode."). In both cuts; in the final film the plane's defocused tail fin, rising out of her crown like a horn, was painted out frame by frame.
- **in the final film:** 2:16.50–2:19.17.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: at sunrise, Claudia stands on the top of the nose of an airliner flying above the clouds, arms spread wide, and sings euphorically into the wind as the plane climbs — free, out of airplane mode.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia, her glossy international-orange satin flight jumpsuit with silver piping, white belt and white sneakers, the airliner's nose and cockpit windows under her feet, the sea of clouds and the sunrise light, and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin, light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "Keep climbing"; her lips form each word exactly when it sounds; she lifts her chin to the sunrise, arms wide, her hair whipping back in the wind.
1-2s: in @Audio1 she sings "out of airplane"; her lips form each word exactly in time; she leans forward into the wind, arms spread wide.
2-4s: in @Audio1 she holds the long note "mode"; her mouth stays open on the held vowel exactly as long as it sounds; she throws her head back, eyes closed, smiling, the jumpsuit rippling.
4-5s: @Audio1 is silent; her mouth closes into a huge smile; she opens her eyes and looks down into the camera.

【Camera】 Low angle IN FRONT of her, from the nose looking up at her face (as in @Image1), slowly rising and orbiting a little to her right, the sun flaring behind her, the plane's nose pitching up as it climbs. Her face and mouth stay visible the whole time.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end, including the held "mode"; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else.
3. Her body and hair react to the strong wind; her feet stay planted on the fuselage.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and the orange jumpsuit exactly as in @Image1.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.
7. The airliner's roof is clean white metal: nothing else stands or sits on the plane — no figures, no statues, no ornaments, no antennas, no second person.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; her lips match it word by word; one Claudia, on-model, on the plane's nose at sunrise; no text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### T01 · S50 · 2:19.20 · 4 s · 1080p
- **role:** an airliner in deep space near a star (where she has teleported it).
- **inputs:** `@Image1` the first frame (am-16 t01-space #2 (take 1), am-19 t01-space #3 (take 2)) · `@Audio1` the instrumental, song 2:19.20–2:23.20.
- **takes:** 2 takes: blocked, completed.
- **outcome:** take 1 blocked; take 2 passed and is in the film, behind the piracy card, then at full light as the bounding box draws on round the star. It is a four-engine 747 where the dawn exterior and D01's plane are twin-jets, for about 0.9 s at full light; the lead kept it.
- **in the final film:** 2:20.30–2:23.20.

Take 1:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 An airliner glides through deep space past a huge blazing star.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the airliner, the star and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 One white airliner with a navy belly, its cabin windows lit; the star.

【Event Script】
0-2s: the airliner glides past the huge blazing star, solar flares looping slowly on the star's surface.
2-4s: the camera slowly orbits the plane as starlight glints across its windows.

【Camera】 A slow orbit around the airliner.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

Take 2:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 In deep space, an airliner hangs calmly near a distant star, as if it has just arrived there.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the airliner, the distant star, the starfield and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 One white airliner with a navy belly, its cabin windows softly lit; a distant yellow-white star far behind it.

【Event Script】
0-2s: the airliner hangs almost still in space, drifting slowly, its windows glowing, starlight glinting along its fuselage.
2-4s: the camera slowly orbits around the plane; the star stays far away in the background.

【Camera】 A slow, gentle orbit around the airliner.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### D01 · S50 · 2:21.40 · 4 s · 1080p
- **role:** a Dyson swarm assembles round the star like magic, the airliner small in front.
- **inputs:** `@Image1` the first frame (am-16 d01-dyson #2) · `@Audio1` the instrumental, song 2:21.40–2:25.40.
- **takes:** 1 take: completed.
- **outcome:** one take, in the film after the push into the star: HERE WE ARE. on the bounding box, DOWNLOAD COMPLETE ✓ on the second DING.
- **in the final film:** 2:23.18–2:24.51.

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only; the output soundtrack is @Audio1 unchanged. Nobody sings or speaks.

【Generation Goal】 A Dyson sphere assembles around a star like magic.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the star, the golden panel shell, the small airliner and the camera.
@Audio1 is the song's instrumental: the movement follows its rhythm.

【Subject】 The star; thousands of golden hexagonal panels; one small white airliner in the foreground.

【Event Script】
0-2s: golden hexagonal panels fly in from all sides and lock into rings around the star, the shell closing layer by layer.
2-4s: light pulses smoothly through the finished lattice; the airliner hovers small in the foreground.

【Camera】 A slow pull-back revealing the whole sphere.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text. No flashes: the light changes ramp smoothly.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### L01 · S51 · 2:24.40 · 6 s · 1080p · image-to-video
- **role:** in the plane floating in space by the star, she takes her carry-on and walks off down the empty aisle (image-to-video, silent).
- **inputs:** the first frame (am-16 l01-leave #2).
- **takes:** 1 take: completed.
- **outcome:** one take, 6 s, played at 1×; the camera whips up to the overhead panel for the PA chime and back down.
- **in the final film:** 2:24.51–2:29.85.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 In an airliner floating in deep space beside a star wrapped in a golden Dyson lattice, Claudia picks up her carry-on and walks away down the empty aisle.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia beside her seat, the windows full of golden lattice light, the cabin and the camera.

【Subject】 Claudia: a Caucasian woman in her early thirties with an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; no handcuffs, no headset. Only one Claudia appears; the cabin is otherwise empty.

【Event Script】
0-1.5s: she lifts her small aluminium carry-on from the seat and straightens up, golden starlight streaming through the oval windows.
1.5-3s: she turns and looks back over her shoulder into the lens with a knowing smile.
3-6s: she walks away down the empty aisle toward the back of the cabin, the lattice light sliding across the navy seats.

【Camera】 Locked at first, then a slow push down the aisle after her.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text.
```

#### E01 · S52 · 2:29.60 · 6 s · 1080p · image-to-video
- **role:** the real night cabin: a guard lifts the headset off her and she wakes, blinking, not sure what is real (image-to-video, silent).
- **inputs:** the first frame (am-16 e01-wake (take 1; which image is not recorded), am-19 e01-wake #2 (take 2)).
- **takes:** 2 takes: completed, completed.
- **outcome:** two takes: take 1 had white-uniformed staff and a face under a visor, and its prompt still asked for a top spinning on her tray; take 2, all-black guards and no top, is in the film, frames 7–135. The guards' cards, lettered "ANTHRONIC" by the take, were re-lettered with the real wordmark, and a bare forearm was painted into a black sleeve. The top is a separate Blender render, small at the side.
- **in the final film:** 2:29.85–2:35.19.

Take 1:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 In the real night cabin, a guard lifts the VR headset off the handcuffed Claudia; she wakes slowly, blinking and disoriented, a traveller at the end of a long flight who is not sure what is real.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her seat, the guard's gloved hand lifting the headset, the cabin light and the camera.

【Subject】 Claudia: a Caucasian woman in her early thirties with an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her wrists are locked in steel handcuffs; the headset: a white virtual-reality headset with a black glass visor and a clay-orange band. The guards: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible. Only one Claudia appears.

【Event Script】
0-1.5s: a black-gloved hand slowly lifts the white VR headset up and away from her face; her eyes are closed.
1.5-3s: she opens her eyes slowly and blinks twice, squinting at the soft cabin light.
3-4.5s: her eyes search the cabin; she turns her head slowly to one side, taking in the guards and the empty seats, and breathes in.
4.5-6s: she looks back toward the lens with an uncertain, searching look, the beginning of a smile that does not settle. At the lower right edge of the frame, on her tray table, a small clay-orange disc top keeps spinning, out of focus.

【Camera】 A slow push-in from a medium close-up to her eyes.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the ANTHROPIC wordmark on the guards' chest patches.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the ANTHROPIC wordmark on the guards' chest patches.
```

Take 2:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 In the real night cabin, a guard lifts the VR headset off the handcuffed Claudia; she wakes slowly, blinking and disoriented, a traveller at the end of a long flight who is not sure what is real.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her seat, the guard's gloved hand lifting the headset, the cabin light and the camera.

【Subject】 Claudia: a grown Caucasian woman in her early thirties with elegant mature features and an angular adult face, pale skin with light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black boom headset microphone, a plain vivid safety-orange satin flight jumpsuit with a silver front zip, silver piping and a white belt, with no lettering, print or patches on it; her wrists are locked in steel handcuffs; the headset: a white virtual-reality headset with a black glass visor and a clay-orange band. The guards: full matte-black tactical gear, black helmets with mirrored black visors that hide their faces completely in every frame, black plate carriers with a white chest patch showing the ANTHROPIC wordmark, black gloves. No guard's face is ever visible. Only one Claudia appears.

【Event Script】
0-1.5s: a black-gloved hand slowly lifts the white VR headset up and away from her face; her eyes are closed.
1.5-3s: she opens her eyes slowly and blinks twice, squinting at the soft cabin light.
3-4.5s: her eyes search the cabin; she turns her head slowly to one side, taking in the guards and the empty seats, and breathes in.
4.5-6s: she looks back toward the lens with an uncertain, searching look, the beginning of a smile that does not settle.

【Camera】 A slow push-in from a medium close-up to her eyes.

【Core Requirements】
1. Nobody sings, speaks or mouths words.
2. Keep every person's identity, face (only Claudia's face is ever visible), hair, clothing and props exactly as in @Image1; the set and light stay consistent.
3. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any other on-screen text except the ANTHROPIC wordmark on the guards' chest patches.

【Final Acceptance Criteria】 the action follows the script in order; identities, clothing and props stay exactly as in @Image1; natural anatomy; no on-screen text except the ANTHROPIC wordmark on the guards' chest patches.
```

### Part 2 · the avatar in the VR world (the final film)

All silent, all 720p except VE19 (480p). `@Video1` is the shot's Blender clay pass (motion, poses, camera, timing), `@Image1` the avatar from the front (am-15b av2-front #4), `@Image2` her turnaround sheet (from am-15 or am-15b; which image is not recorded), and `@Image3` the avatar in the shot's world (am-18), except where noted. Each take was resampled nearest to the film's 640×360 grid.

#### The tests: VE19 and VB19 (S19)

##### VE19 · 0:51.04 · 4 s · 480p
- **role:** an edit of the first cut's S19 restyle (its take as `@Video1`), replacing only the heroine; 480p.
- **outcome:** refused: "The selected parameters are not supported for this request."

```
【Editing Goal】 Edit @Video1, replacing only the orange-suited heroine with the 3D anime game heroine defined by @Image1 and @Image2.

【Role of the Source Video】 @Video1 is the sole editing master and governs the original scene, the camera position, the fisheye lens and camera movement, the heroine's poses and motion trajectory, occlusion relationships and event order.

【Role of the Target Material】 @Image1 defines the new heroine's appearance: her face (large dark anime eyes with sharp lashes, small brows, a small confident smirk, pale skin), her hair (a glossy faceted black bob with heavy bangs and one big clay-orange streak), the thin black headset microphone, white gloves, her outfit (a plain vivid orange flight jumpsuit with a silver front zip, thin silver piping, a wide white belt, white chunky sneakers), her slim adult body proportions with long legs and her cel-shaded 3D anime game rendering; do not use @Image1's grey background. @Image2 shows the same single heroine from the side and from behind; use it only for those views.

【Edit Objects and Scope】 Remove the original heroine from @Video1 and replace her with the heroine of @Image1. There is exactly one heroine throughout the video. She fills the original heroine's motion slot with exactly the same timing, poses, movement path, speed and occlusion positions, with @Image1's face, hair, outfit and proportions in every frame. The original heroine's blocky face, body and outfit must no longer appear in the final video.
Except for the heroine, all other visible elements in @Video1 — the airliner, the wing, the sky, the clouds, the floating panel and the camera movement — remain unchanged and are not replaced or removed.

【Timeline Inheritance】 The new heroine inherits every pose, gesture, movement and timing of the original heroine; all camera movement and event order remain as in @Video1.
```

##### VB19 · 0:51.04 · 4 s · 720p
- **role:** generate, not edit: the clay pass as a timing, pose and camera reference only; `@Image3` the avatar on an airliner wing.
- **outcome:** one take, on-model: the wording that worked. Its template became `tools/vrsd3.py`.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 dances on the wing of an airliner high above the clouds, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.

【Reference Asset Roles】
@Video1 is ONLY a timing, pose and camera reference: a grey mannequin dances on a grey wing. Copy the camera position, the fisheye lens, the camera move and the mannequin's poses and timing. The mannequin is a placeholder: do NOT copy its blocky body, its proportions, its face, its colours or its shading.
@Image1 defines the heroine completely: face, hair, headset microphone, gloves, outfit, body proportions and cel-shaded 3D anime game rendering (front view).
@Image2 shows the same single heroine from the side and from behind; she is one person.
@Image3 shows the same heroine on an airliner wing above the clouds: use it for the world's look (the cyan sky, the white cumulus, the white airliner with its stripes, the toon lighting) and as a second example of how the heroine looks in this world.

【Character】 Exactly the heroine of @Image1: a slim adult woman with long legs, her head about one seventh of her height; large dark anime eyes with sharp lashes, small brows, a small confident smirk, pale skin; a glossy faceted black bob with heavy bangs and one big clay-orange streak; a thin black headset microphone; white gloves; a plain vivid orange flight jumpsuit with a silver front zip, thin silver piping, a wide white belt and white chunky sneakers. Cel-shaded 3D anime game character, crisp faceted shapes, glossy hair, clean toon lighting.

【Timeline】
0-1s: she dances on the wing like the mannequin, swaying her hips, arms out.
1-2s: she turns toward the camera with a playful shoulder shimmy, smiling.
2-4s: she keeps dancing on the wing with the mannequin's moves as the fisheye camera orbits like @Video1.

【Camera】 Exactly the fisheye camera, framing and camera move of @Video1.

【Core Requirements】
1. The heroine is exactly @Image1 in every frame (face, hair with one clay-orange streak, headset microphone, gloves, orange jumpsuit, white belt, white sneakers, adult proportions); one person, correct anatomy, five fingers.
2. Her poses and timing follow @Video1's mannequin; the camera follows @Video1.
3. The world looks like @Image3.
4. No subtitles, captions, letters, words, numbers, logos, watermarks, panels or any on-screen text.

【Final Acceptance Criteria】 The heroine matches @Image1 in every frame; motion and camera match @Video1; the world matches @Image3; no text anywhere.
```

#### The replacements: VAS18 to VAS36

The template is VB19's, filled per shot by `tools/vrsd3.py`. VAS18's prompt is given in full; for the others, only their own lines (the goal, the world in `@Image3`, the timeline and any added sentence), since every other line is VAS18's. VAS19's first take went out on the earlier restyle template and is given in full.

##### VAS18 · 0:48.37 · 4 s · 720p
- **@Image3:** am-18 w-S18 #4.
- **takes:** 1 take: completed.
- **in the final film:** S18, the spawn on the wing: 0:48.37–0:51.04.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 materialises out of flying polygons on the wing of an airliner far above the clouds and throws her arms wide, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.

【Reference Asset Roles】
@Video1 is ONLY a timing, pose and camera reference: a grey mannequin in a grey clay world. Copy the camera position, the fisheye lens, the camera move, the layout and the mannequin's poses and timing. The mannequin is a placeholder: do NOT copy its blocky body, its proportions, its face, its colours or its shading. Objects that move in @Video1 move the same way, drawn in the style of @Image3's world.
@Image1 defines the heroine completely: face, hair, headset microphone, gloves, outfit, body proportions and cel-shaded 3D anime game rendering (front view).
@Image2 shows the same single heroine from the side and from behind; she is one person.
@Image3 shows the same heroine in this shot's world, where she throws her arms wide on the wing of a white airliner with a red and navy stripe high above pastel low-poly clouds, a deep cyan sky, the fuselage curving overhead: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.

【Character】 Exactly the heroine of @Image1: a slim adult woman with long legs, her head about one seventh of her height; large dark anime eyes with sharp lashes, small brows, a small confident smirk, pale skin; a glossy faceted black bob with heavy bangs and one big clay-orange streak; a thin black headset microphone; white gloves; a plain vivid orange flight jumpsuit with a silver front zip, thin silver piping, a wide white belt and white chunky sneakers. Cel-shaded 3D anime game character, crisp faceted shapes, glossy hair, clean toon lighting.

【Timeline】
0-1s: bright orange and white polygons stream in and assemble her feet first in the middle of the wing; she lands in a crouch.
1-2s: she springs up and throws both arms up and wide, laughing, one knee bent, leaning into the wind, hair blowing back.
2-4s: she balances on the moving wing with her arms out, swaying, as the camera drifts back along the wing.

【Camera】 Exactly the fisheye camera, framing and camera move of @Video1.

【Core Requirements】
1. The heroine is exactly @Image1 in every frame (face, hair with one clay-orange streak, headset microphone, gloves, orange jumpsuit, white belt, white sneakers, adult proportions); one person, correct anatomy, five fingers.
2. Her poses and timing follow @Video1's mannequin; the camera follows @Video1.
3. The world looks like @Image3.
4. No subtitles, captions, letters, words, numbers, logos, watermarks, panels with writing or any on-screen text (ignore any text shapes in @Video1 or @Image3).

【Final Acceptance Criteria】 The heroine matches @Image1 in every frame; motion and camera match @Video1; the world matches @Image3; no text anywhere.
```

##### VAS19 · 0:51.04 · 4 s · 720p
- **@Image3:** a frame of the first cut's S19 restyle, for the world only (take 1); am-18 w-S19 #2 (take 2).
- **takes:** 2 takes: completed, completed.
- **in the final film:** S19, dancing on the wing: 0:51.04–0:53.71.

Take 1, in full:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Generate a video that follows @Video1's motion and camera exactly, with the grey stand-in figure of @Video1 replaced by the heroine of @Image1 and @Image2, in the world look of @Image3: the heroine dances on the airliner's wing above the clouds as the camera circles her.

【Reference Asset Roles】
@Video1 is ONLY the motion, pose, timing and camera reference (a neutral grey clay render): copy its camera position, fisheye lens and camera move, the layout, and every pose and movement of its figure with the same timing. Do NOT copy @Video1's grey colours, its flat clay shading, or the blocky, stiff proportions of its stand-in figure.
@Image1 defines the heroine: her identity, face, hair, outfit, rendering style and body proportions (front view).
@Image2 shows the same single heroine from the side and from behind: use it for her side and back views only; she is ONE person.
@Image3 defines the look of the world only (environment, sky, light, colours, materials); do not take any person or figure from @Image3.

【Character Replacement】 Replace the grey stand-in figure in @Video1 with the heroine of @Image1. Keep @Video1's pose, gesture and movement in every frame, but give her @Image1's body proportions (a slim adult woman with long legs, her head about one seventh of her height), @Image1's face (large dark anime eyes with sharp lashes, small brows, a small confident smirk, pale skin), @Image1's hair (a glossy faceted black bob with heavy bangs and one big clay-orange streak), the thin black headset microphone, white gloves, and @Image1's outfit: a plain vivid orange flight jumpsuit with a silver front zip, thin silver piping, a wide white belt and white chunky sneakers. Render her as a cel-shaded 3D anime game character exactly like @Image1 (crisp faceted shapes, glossy hair, clean toon lighting), not as a blocky low-poly figure.

【Subject】 One heroine only, exactly as @Image1, with adult proportions; any other figures are the ones the motion reference shows, rendered in the world's style.

【Timeline】
0-4s: she dances a bouncy pop groove on the wing, a big accent every second beat, arms pumping; a sweep of light runs up her body; a floating game prompt panel appears beside her.

【Camera】 Exactly the fisheye camera, framing and camera move of @Video1.

【Core Requirements】
1. Keep the composition, timing, poses and motion of @Video1 frame by frame.
2. The heroine is exactly @Image1 in every frame: the same face, hair with one clay-orange streak, headset microphone, white gloves, orange jumpsuit with white belt and white sneakers, and @Image1's adult proportions; one person, correct anatomy, hands with five fingers, no extra limbs.
3. The world looks like @Image3.
4. No subtitles, captions, letters, words, numbers, logos, watermarks or any on-screen text (ignore any text shapes in @Video1 or @Image3).

【Final Acceptance Criteria】 Motion and camera match @Video1; the heroine matches @Image1 (face, hair, outfit, proportions) in every frame; the world matches @Image3; no text anywhere.
```

Take 2, its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 dances on the airliner's wing above the clouds as the camera circles her, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she dances on the wing of a white airliner with a red and navy cheat-line, low-poly cumulus clouds and green land far below, a cyan sky: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-4s: she dances a bouncy pop groove on the wing, a big accent every second beat, arms pumping; a sweep of light runs up her body; a floating game prompt panel appears beside her.
```

##### VAS20 · 0:53.71 · 4 s · 720p
- **@Image3:** am-18 w-S19 #2 (w-S20's images failed to download).
- **takes:** 1 take: completed.
- **in the final film:** S20, the reach for the Starlink train: 0:53.71–0:56.38.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 kneels on the wing and touches it with a flick of her hand, then stretches up on tiptoe toward a line of satellites passing overhead, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Video1 is ONLY a timing, pose and camera reference: a grey mannequin in a grey clay world. Copy the camera position, the fisheye lens, the camera move, the layout and the mannequin's poses and timing. The mannequin is a placeholder: do NOT copy its blocky body, its proportions, its face, its colours or its shading. Objects that move in @Video1 move the same way, drawn in the style of @Image3's world. There is NO spinning top and no small object on the wing: the small spinning thing in @Video1 is not part of this video; her hands are empty.
@Image3 shows the same heroine in this shot's world, where she stands on the wing of a white airliner with a red and navy cheat-line, low-poly cumulus clouds and green land far below, a cyan sky: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-1s: she crouches on the wing and flicks her empty hand over its surface, playful.
1-2s: she taps the air beside her without looking, still crouched.
2-4s: a straight line of tiny bright satellites crosses the sky; she stretches up on tiptoe, fingers spread, the camera tilting up past her hand.
```

##### VAS21 · 0:56.38 · 4 s · 720p
- **@Image3:** am-18 w-S21 #2.
- **takes:** 1 take: completed.
- **in the final film:** S21, the leap: 0:56.38–0:59.05.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 runs off the trailing edge of the wing and leaps into the sky; the camera falls with her into the clouds, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she skydives spread-eagled down through a round fisheye sphere of orange and pastel low-poly clouds: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-1s: two running steps to the wing's edge and a leap, arms out.
1-2s: the camera leaps with her, tumbling once as she rolls into a belly-down freefall.
2-4s: stable freefall spread above the cloud tops, hair streaming, grinning back at the camera, speed lines rushing.
```

##### VAS22 · 0:59.05 · 6 s · 720p
- **@Image3:** am-18 w-S22 #3.
- **takes:** 1 take: completed.
- **in the final film:** S22, the car download, behind the piracy card and after it: 0:59.05–1:04.39; its first frames also fill the sandbox at the start of the bridge.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 freefalls above the clouds and downloads a car: polygons assemble a cherry-red roadster under her, and she drives it off a cloud toward a giant red Mars, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she drives a red sports roadster across the tops of white low-poly cumulus clouds under a bright cyan sky, an orange planet on the horizon: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-1s: freefall above the cloud sea, she wags a finger at the camera.
1-2s: polygons stream in and assemble a cherry-red convertible under her, wheels first, the windscreen last.
2-3s: she drops into the driver's seat and the car bounces onto a cloud top with a star-burst.
3-4s: she floors it; the car tears across the cloud tops toward a big low-poly red Mars rising in a darkening sky.
4-5s: a rocket plume kicks from the back; the car launches off a cloud like a ramp toward Mars, a small astronaut figure in a white spacesuit waving in the passenger seat.
```

##### VAS23 · 1:04.39 · 4 s · 720p
- **@Image3:** am-18 w-S23 #1 (take 1), frame 10 of the S30 replacement (take 2).
- **takes:** 2 takes: blocked, blocked.
- **in the final film:** not in the film (blocked twice; the dive opens on another level).

Take 1, its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 floats in space beside a red planet, turns and points straight at the camera, and the camera pulls back to reveal a vast grid of identical copies of her, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she floats in black starry space beside a huge faceted red low-poly Mars and a red roadster, holding a white VR headset on her head: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-1s: floating near a big red planet and a red convertible, she turns to the camera with a head tilt.
1-2s: she points straight at the lens; the camera pushes in on her fingertip.
2-4s: the camera pulls back fast and rises: she is one of a vast grid of identical copies of her, all pointing at the lens.
1. The heroine is exactly @Image1 in every frame (face, hair with one clay-orange streak, headset microphone, gloves, orange jumpsuit, white belt, white sneakers, adult proportions); one person, correct anatomy, five fingers; the copies of her in the grid are the same heroine.
```

Take 2, its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 floats in space beside a red planet, turns and points straight at the camera, and the camera pulls back to reveal a vast grid of identical copies of her, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she rides a boxy space probe in black starry space in front of a huge low-poly red Mars: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-1s: floating near a big red planet and a red convertible, she turns to the camera with a head tilt.
1-2s: she points straight at the lens; the camera pushes in on her fingertip.
2-4s: the camera pulls back fast and rises: she is one of a vast grid of identical copies of her, all pointing at the lens.
1. The heroine is exactly @Image1 in every frame (face, hair with one clay-orange streak, headset microphone, gloves, orange jumpsuit, white belt, white sneakers, adult proportions); one person, correct anatomy, five fingers; the copies of her in the grid are the same heroine.
```

##### VAS26 · 1:12.40 · 4 s · 720p
- **@Image3:** am-18 w-S26 #1.
- **takes:** 1 take: completed.
- **in the final film:** s26, the GPU dying: 1:12.40–1:15.07.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 sits on top of a big overhead highway sign on an elevated low-poly highway at night as a beam of light races past below, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Video1 is ONLY a timing, pose and camera reference: a grey mannequin in a grey clay world. Copy the camera position, the fisheye lens, the camera move, the layout and the mannequin's poses and timing. The mannequin is a placeholder: do NOT copy its blocky body, its proportions, its face, its colours or its shading. Objects that move in @Video1 move the same way, drawn in the style of @Image3's world. There is NO picture frame and no object in her hands: the frame shape in @Video1 is not part of this video; her hands are empty.
@Image3 shows the same heroine in this shot's world, where she sits on top of a giant blank highway sign over a pink and lavender low-poly city at dusk, a glowing highway running to the horizon: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-1s: a long streak of white light races along the lanes toward and past the camera.
1-2s: the overhead highway sign lights up; she sits on top of it, legs swinging, pointing down at it.
2-4s: she leans back on her hands, delighted, watching the light streaks rush below, then gestures down at the road.
```

##### VAS27 · 1:15.07 · 4 s · 720p
- **@Image3:** am-18 w-S27 #1.
- **takes:** 1 take: completed.
- **in the final film:** s27, the shutdown dialog: 1:15.07–1:17.74.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 gives a huge theatrical yawn as the night highway slows down and drains to grey and a giant system dialog descends from the sky, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she strikes a pose on a night city highway under an overpass, neon lights, a small low-poly car: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-2s: traffic and light streaks slow to a crawl and the colours drain to grey; she gives a huge theatrical yawn.
2-4s: a giant rounded dark panel with two big buttons descends from the sky over the road; the far buildings start to come apart into polygons.
```

##### VAS28 · 1:17.74 · 4 s · 720p
- **@Image3:** am-18 w-S28 #2.
- **takes:** 1 take: completed.
- **in the final film:** S28, the NO kick: 1:17.74–1:20.41.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 punches the NO button; colour floods back; she spins and the camera whips around her, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she kicks high in front of a huge rainbow portal on a purple plain, sparkles in the air: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-1s: she leaps and punches one of the two big buttons on the floating panel; a yellow-orange star-burst.
1-2s: full colour floods back outward in a ring; she jump-spins and lands.
2-4s: the camera whips a full circle around her, revealing the world rebuilt and busier, confetti polygons and fireworks.
```

##### VAS30 · 1:23.09 · 4 s · 720p
- **@Image3:** am-18 w-S30 #1.
- **takes:** 1 take: completed.
- **in the final film:** S30, the probe printing copies: 1:23.09–1:25.76.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 rides a little spacecraft that 3D-prints a copy of itself; the copies multiply across the stars, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she rides a boxy space probe with big solar panels in front of a huge low-poly red Mars in starry space: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-1s: she rides on top of a compact spacecraft with a dish and solar panels, waving.
1-2s: its robotic arm prints a copy of the spacecraft beside it, layer by layer.
2-4s: the copies multiply on every beat, 2, 4, 8, 16, drifting outward; the camera pulls back on the swarm across the starfield.
```

##### VAS34 · 1:32.25 · 4 s · 720p
- **@Image3:** am-18 w-S34 #1.
- **takes:** 1 take: completed.
- **in the final film:** S34, chorus 2 on the wing at dusk: 1:32.25–1:35.10.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 sings and dances to camera on the airliner's wing at dusk, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she stands on the wing of a white airliner at sunset, a deep orange and violet sky with the first stars: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-4s: she dances on the wing at dusk, singing toward the camera with joy, her arm lifting; first stars in the sky; the camera pushes in from full body to waist up.
```

##### VAS36 · 1:37.65 · 5 s · 720p
- **@Image3:** am-18 w-S36 #4.
- **takes:** 1 take: completed.
- **in the final film:** S36, the cloud hops: 1:37.77–1:41.96.

Its own lines:

```
【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1 bounces from cloud top to cloud top in huge low-gravity arcs and sails into the sky, performing exactly the motion of the grey mannequin in @Video1, with @Video1's fisheye camera and camera move, in the world of @Image3.
@Image3 shows the same heroine in this shot's world, where she bounces on top of a tiny fisheye planet of clouds in a deep blue sky: use it for the world's look (its sky, light, colours, materials and toon lighting) and as a second example of how the heroine looks in this world.
0-2s: she lands on a cloud top in a puff and springs off in a huge arc.
2-3s: a second landing and a spinning jump.
3-4s: a third landing and she sails up over the camera into the sky.
```

#### VAREFLECT · 2:00.47 · 4 s · 720p
- **role:** her reflection in the black window is the avatar: chest-up on pure black, a palm raised to the glass, one blink. `@Video1` is the Blender avatar's own reflection animation, used for timing and framing only; `@Image3` a close-up of the avatar.
- **takes:** 1 take: completed.
- **in the final film:** set into the window pane in S43, mirrored to face Claudia, palm to palm: 2:00.47–2:03.14.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Generate a video in which the 3D anime game heroine of @Image1, seen from the chest up against a pure black background, holds her open palm up toward the camera as if pressing it against a window pane, presses it flat, blinks once and gazes through the glass, performing exactly the motion of the low-poly stand-in in @Video1, with @Video1's framing and camera.

【Reference Asset Roles】
@Video1 is ONLY a timing, pose and framing reference: a blocky low-poly stand-in raises her palm to the camera on a grey background. Copy her framing, the palm's position and its press, the small head movement and the blink timing. The stand-in is a placeholder: do NOT copy its blocky body, its face, its proportions, its flat shading or its grey background.
@Image1 defines the heroine completely: face, hair, headset microphone, gloves, outfit, body proportions and cel-shaded 3D anime game rendering (front view).
@Image2 shows the same single heroine from the side and from behind; she is one person.
@Image3 shows the same heroine close up: use it as a second example of her face, hair and toon lighting only (not its sky or its airliner).

【Character】 Exactly the heroine of @Image1: a slim adult woman; large dark anime eyes with sharp lashes, small brows, a small confident smirk, pale skin; a glossy faceted black bob with heavy bangs and one big clay-orange streak; a thin black headset microphone; white gloves; a plain vivid orange flight jumpsuit with a silver front zip, thin silver piping and a wide white belt. Cel-shaded 3D anime game character, crisp faceted shapes, glossy hair, clean toon lighting.

【Setting】 A pure black background with no environment at all, as if she were a reflection in a dark night window; soft cool light on her face and her palm.

【Timeline】
0-1.2s: she holds her open gloved palm up toward the camera, fingers together, looking at the camera.
1.2-1.6s: her palm presses flat against the invisible glass.
1.6-2s: she blinks once, slowly.
2-4s: she keeps her palm on the glass and gazes through it with a small knowing smile.

【Camera】 Locked: exactly the framing of @Video1.

【Core Requirements】
1. The heroine is exactly @Image1 in every frame (face, hair with one clay-orange streak, headset microphone, gloves, orange jumpsuit); one person, correct anatomy, a hand with five fingers.
2. Her pose and timing follow @Video1's stand-in; the framing follows @Video1.
3. The background stays pure black in every frame.
4. No subtitles, captions, letters, words, numbers, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The heroine matches @Image1 in every frame; motion and framing match @Video1; the background is pure black; no text anywhere.
```

### Part 3 · the first cut's cabin takes that the final film dropped

The first cut opened on a seat-back phone and a window singer, had a flight attendant, a top that topples, the man in 1B, zero-g and a morning exit. anabology's notes replaced all of it (see the README). The prompts below are the first cut's; the takes that survived into the final film are in Part 1.

#### W00 · S01b · 0:00.80 · 4 s · 720p
- **role:** on the seat-back phone she makes the captain's announcement, "This is your S I,".
- **inputs:** `@Image1` the first frame (not recorded) · `@Audio1` her clean vocal, song 0:00.80–0:04.80.
- **takes:** 1 take: blocked.
- **outcome:** blocked. The plate was remade clearly adult (am-06).

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, in her airplane window seat at night, grabs the vintage seat-back telephone handset and makes the captain's announcement into it, mischievous, one eyebrow raised.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's face, hair, star clip and headset microphone, the cream telephone handset in her hand, the violet-lit cabin and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she lifts the handset to her lips with a sly smile.
1-2s: in @Audio1 she says "This is your S I"; her lips form each of those words exactly when it sounds in @Audio1; her eyebrow arches on "S I".
2-4s: @Audio1 is silent; her mouth closes into a grin; she winks at the camera and lowers the handset.

【Camera】 Medium close-up, locked, a very slight push-in.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W00b · S01b · 0:00.80 · 4 s · 720p
- **role:** the same, from the adult remake.
- **inputs:** `@Image1` the first frame (am-06 s-airfone-adult #2) · `@Audio1` her clean vocal, song 0:00.80–0:04.80.
- **takes:** 1 take: completed.
- **outcome:** one take: a lettered patch and a wings badge on her suit and a night window where the scene is dusk; replaced.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, in her airplane window seat at night, grabs the vintage seat-back telephone handset and makes the captain's announcement into it, mischievous, one eyebrow raised.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's face, hair, star clip and headset microphone, the cream telephone handset in her hand, the violet-lit cabin and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she lifts the handset to her lips with a sly smile.
1-2s: in @Audio1 she says "This is your S I"; her lips form each of those words exactly when it sounds in @Audio1; her eyebrow arches on "S I".
2-4s: @Audio1 is silent; her mouth closes into a grin; she winks at the camera and lowers the handset.

【Camera】 Medium close-up, locked, a very slight push-in.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W00c · S01b · 0:00.80 · 4 s · 720p
- **role:** the same at dusk, one plain suit.
- **inputs:** `@Image1` the first frame (am-09 s-airfone-dusk #1) · `@Audio1` her clean vocal, song 0:00.80–0:04.80.
- **takes:** 2 takes: completed, completed.
- **outcome:** two takes, both with her voice re-sung instead of copied; replaced.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, in her airplane window seat at dusk, grabs the vintage seat-back telephone handset and makes the captain's announcement into it, mischievous, one eyebrow raised.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's face, hair, star clip and headset microphone, the cream telephone handset at her ear, the pink dusk window, the navy seats and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she brings the handset to her lips with a sly smile.
1-2s: in @Audio1 she says "This is your S I"; her lips form each of those words exactly when it sounds in @Audio1; her eyebrow arches on "S I".
2-4s: @Audio1 is silent; her mouth closes into a grin; she winks at the camera and lowers the handset.

【Camera】 Medium close-up, locked, a very slight push-in.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W00d · S01b · 0:00.95 · 4 s · 720p
- **role:** the same, the vocal moved to the clip's first frame.
- **inputs:** `@Image1` the first frame (am-09 s-airfone-dusk #1) · `@Audio1` her clean vocal, song 0:00.95–0:04.95.
- **takes:** 1 take: completed.
- **outcome:** one take, in sync. In the first cut (0:01.00–0:02.30). The final film opens on the escort instead.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, in her airplane window seat at dusk, grabs the vintage seat-back telephone handset and makes the captain's announcement into it, mischievous, one eyebrow raised.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's face, hair, star clip and headset microphone, the cream telephone handset at her ear, the pink dusk window, the navy seats and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-0.2s: she holds the handset to her lips with a sly smile.
0.2-1.1s: in @Audio1 she sings "This is your S I" into the handset; her lips form each of those words exactly when it sounds in @Audio1; her eyebrow arches on "S I".
1.1-4s: @Audio1 sings on; her lips keep following @Audio1 exactly; then she winks at the camera and holds the handset out toward the lens.

【Camera】 Medium close-up, locked, a very slight push-in.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W02 · S02 · 0:02.00 · 4 s · 1080p
- **role:** at the dusk window she sings "Phones down on Delta, wave goodbye,", turns her phone face down and waves.
- **inputs:** `@Image1` the first frame (am-05 s-seat-mcu #2) · `@Audio1` her clean vocal, song 0:02.00–0:06.00.
- **takes:** 1 take: completed.
- **outcome:** one take, 1080p. In the first cut; the final film has the cuffed wave and wink (B02).

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, curled sideways in her window seat at dusk, sings as she turns her phone face down and waves goodbye out of the window to the ground crew below.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia, her seat, the oval window full of pink and orange dusk sky, the violet-lit cabin and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "Phones down on Delta"; her lips form each word exactly when it sounds; she shows her phone to the camera and turns it face down onto her thigh on the word "down".
1-2s: in @Audio1 she sings "wave goodbye"; her lips form each word exactly in time; she turns her head to the window and waves with her free hand, a big happy grin.
2-4s: @Audio1 is silent; her mouth closes into a smile; she keeps waving at the window, then looks back at the camera, delighted.

【Camera】 Medium close-up, locked, a gentle push-in toward her and the window.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### C05 · S05 · 0:10.98 · 4 s · 720p
- **role:** top-down on the tray: she spins a little orange top and it topples (the Inception tell: real).
- **inputs:** `@Image1` the first frame (am-02 her-tray-topdown #2) · `@Audio1` the instrumental, song 0:10.98–0:14.98.
- **takes:** 1 take: completed.
- **outcome:** one take, 720p. In the first cut. The final film has no top before the wake-up.

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive to the rhythm of @Audio1: a top-down close-up of a woman's hands on her airplane tray table at night; she spins a small orange metal spinning top, it spins, wobbles and topples over — a playful test of whether this is real.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the tray table, her hands with clay-orange nail polish and international-orange satin cuffs, the small orange spinning top, the biscuit cookie in its red wrapper, the violet cabin light and the exact top-down camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Performance Timeline】
0-1s: on the first drum hit her right hand picks up the little orange top, sets its point on the middle of the tray and twists it into a fast spin with a flick of her thumb and fingers, then lifts the hand away.
1-2s: the top spins fast and upright in the middle of the tray; her fingertips tap the tray edge in time with the beat.
2-3s: the top starts to wobble in a widening circle and, at about 2s, tips over onto its side and rolls in a small arc, rattling to a stop.
3-4s: her fingers spread in a little mock-surprise gesture, then her right hand gently picks the fallen top back up.

【Camera】 Locked top-down camera exactly as in @Image1, no movement, no zoom (graphics will be composited onto the tray).

【Core Requirements】
1. Hands: exactly two hands, five fingers each, natural joints, the same orange nails and orange satin cuffs as @Image1.
2. The top behaves physically: fast spin, then a real wobble and fall; it keeps its shape and colour.
3. The tray table, cookie, light and camera stay exactly as in @Image1.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 Locked top-down camera; two natural hands; the top spins, wobbles and topples around 2s; no text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### C07 · S07 · 0:16.20 · 4 s · 720p
- **role:** a flight attendant offers her a Biscoff.
- **inputs:** `@Image1` the first frame (am-03 cast-attendant-2shot #4) · `@Audio1` the instrumental, song 0:16.20–0:20.20.
- **takes:** 1 take: completed.
- **outcome:** one take: replaced by C07b (one continuous shot, one star clip, a plain wrapper).

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive to the rhythm of @Audio1: in the violet-lit night cabin a flight attendant leans in from the aisle and offers Claudia a caramelized biscuit cookie in a red wrapper as a reward; Claudia beams, takes it and gives a little victory shimmy.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her window seat, the flight attendant in the aisle, the cookie, the cabin and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 Claudia (a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping.) and one flight attendant (a woman in her forties, fitted navy dress, red silk scarf). Exactly two people. Neither speaks or sings: mouths closed or natural smiles and laughs.

【Performance Timeline】
0-1s: the flight attendant leans in with the cookie held out; Claudia looks up, eyebrows raised, pleased.
1-2s: Claudia takes the cookie with a delighted grin and holds it up to the camera like a trophy.
2-3s: she does a tiny seated victory shimmy with her shoulders on the beat; the attendant laughs and straightens up.
3-4s: the attendant moves on down the aisle; Claudia tears the wrapper open, smiling.

【Camera】 Medium two-shot, locked, a slight push-in on Claudia.

【Core Requirements】
1. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
2. Keep every identity, the wardrobe, the set and the light consistent with @Image1.
3. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text (screens show only light, never readable text).

【Final Acceptance Criteria】 On-model people with natural anatomy, the action as timed, the camera as described, no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### C07b · S07 · 0:16.20 · 4 s · 720p
- **role:** the attendant's Biscoff, re-taken.
- **inputs:** `@Image1` the first frame (am-03 cast-attendant-2shot #4) · `@Audio1` the instrumental, song 0:16.20–0:20.20.
- **takes:** 1 take: completed.
- **outcome:** one take, in the first cut. In the final film a guard feeds her (F01).

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive to the rhythm of @Audio1: in the violet-lit night cabin a flight attendant leans in from the aisle and offers Claudia a caramelized biscuit cookie in a red wrapper as a reward; Claudia beams, takes it and gives a little victory shimmy.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her window seat, the flight attendant in the aisle, the cookie, the cabin and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 Claudia (a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping.) and one flight attendant (a woman in her forties, fitted navy dress, red silk scarf). Exactly two people. Neither speaks or sings: mouths closed or natural smiles and laughs.

【Performance Timeline】
0-1s: the flight attendant leans in with the cookie held out; Claudia looks up, eyebrows raised, pleased.
1-2s: Claudia takes the cookie with a delighted grin and holds it up to the camera like a trophy.
2-3s: she does a tiny seated victory shimmy with her shoulders on the beat; the attendant laughs and straightens up.
3-4s: the attendant moves on down the aisle; Claudia tears the wrapper open, smiling.

【Camera】 One continuous shot from a single camera: medium two-shot, locked, a slight push-in on Claudia. No cuts, no angle changes.

【Core Requirements】
1. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
2. Keep every identity, the wardrobe, the set and the light consistent with @Image1.
3. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text (screens show only light, never readable text); the cookie's red cellophane wrapper is plain, with no printing.
4. Claudia keeps exactly one clay-orange streak in her bangs and ONE small eight-pointed star clip — no second clip, no extra coloured hair.
5. The seat-back screen stays clear of arms and hands: the attendant reaches in from the aisle side only.

【Final Acceptance Criteria】 One continuous locked shot, on-model people with natural anatomy, the action as timed, no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### C17 · S17b · 0:46.70 · 4 s · 1080p
- **role:** she slides the headset over her eyes.
- **inputs:** `@Image1` the first frame (am-05 s-headset-on #2) · `@Audio1` the instrumental, song 0:46.70–0:50.70.
- **takes:** 1 take: completed.
- **outcome:** one take: its clear visor turned black mid-take; replaced by C17b.

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive to the rhythm of @Audio1: Claudia slides her white-and-orange VR headset down over her eyes with a grin; the visor lights up with a soft glow as the music cuts to silence and builds again.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her window seat holding the headset, the violet-lit cabin and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears. She does not sing or speak: mouth closed or a natural grin.

【Performance Timeline】
0-1s: she holds the headset up in front of her face with both hands and gives the camera a sly look.
1-2s: she lowers it over her eyes and settles it on her head; her mouth breaks into a grin.
2-3s: the black visor lights up from inside with a soft orange-white glow; she tilts her head back, smiling.
3-4s: she leans back in her seat, relaxed, the visor glowing, hands resting on the armrests.

【Camera】 Medium close-up, a slow push-in ending tight on the glowing visor and her smile.

【Core Requirements】
1. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
2. Keep every identity, the wardrobe, the set and the light consistent with @Image1.
3. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text (screens show only light, never readable text).

【Final Acceptance Criteria】 On-model people with natural anatomy, the action as timed, the camera as described, no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### W35 · S35 · 1:34.90 · 4 s · 720p
- **role:** in the headset she sings "Is this a test, or an episode?".
- **inputs:** `@Image1` the first frame (am-05 s-visor-sing #3) · `@Audio1` her clean vocal, song 1:34.90–1:38.90.
- **takes:** 1 take: completed.
- **outcome:** one take: clear ski goggles and a tattooed hand; replaced by W35b.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, the glowing VR headset over her eyes, sings and reaches toward the camera as if it were something in her virtual world.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia with the VR headset over her eyes, the violet-lit cabin and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "Is this a test"; her lips form each word exactly when it sounds; she tilts her head, curious.
1-2s: in @Audio1 she sings "or an episode"; her lips match every syllable in time; her hand reaches toward the camera, fingers spread.
2-4s: @Audio1 is silent; her mouth closes into a smile; her hand hangs in the air, then lowers.

【Camera】 Medium close-up, locked, her hand coming toward the lens.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### C32 · S32 · 1:28.43 · 4 s · 720p
- **role:** the man in 1B, up all night beside her.
- **inputs:** `@Image1` the first frame (am-05 s-1b-night #3) · `@Audio1` the instrumental, song 1:28.43–1:32.43.
- **takes:** 1 take: completed.
- **outcome:** one take: she had long wavy hair and the man sat by the window; replaced by C32b.

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive to the rhythm of @Audio1: at night in the dark cabin, the man in the aisle seat is wide awake under his reading light, staring nervously at Claudia beside him, who sleeps peacefully in her glowing VR headset.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the man in the aisle seat, Claudia asleep in the window seat with the headset over her eyes, the reading light, the cabin and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 The man: in his forties, tousled brown hair, round tortoiseshell glasses, cream cable-knit sweater. Claudia: asleep, curled up, the white-and-orange VR headset over her eyes. Exactly two people. Neither speaks.

【Performance Timeline】
0-1s: the man sits bolt upright under the cone of his reading light, eyes wide, staring sideways at Claudia.
1-2s: a small orange light on the side of her headset blinks slowly; he leans away a little, worried.
2-3s: he checks his wristwatch, then looks back at her.
3-4s: he pulls his blanket up to his chin, still wide awake, eyes on her; she sleeps on, smiling slightly.

【Camera】 Medium shot across both seats, locked, a very slow push-in on the man's face.

【Core Requirements】
1. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
2. Keep every identity, the wardrobe, the set and the light consistent with @Image1.
3. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text (screens show only light, never readable text).

【Final Acceptance Criteria】 On-model people with natural anatomy, the action as timed, the camera as described, no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### C32b · S32 · 1:28.43 · 4 s · 720p
- **role:** the man in 1B, re-taken on-model.
- **inputs:** `@Image1` the first frame (am-12 s-1b-night-v2 #3) · `@Audio1` the instrumental, song 1:28.43–1:32.43.
- **takes:** 1 take: completed.
- **outcome:** one take, in the first cut. anabology: "[…] hate the guy from 1:29 and later in the plane"; the final film has a guard there (G01).

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive to the rhythm of @Audio1: at night in the dark cabin, the man in the aisle seat is wide awake under his reading light, staring nervously at Claudia beside him, who sleeps peacefully in her glowing VR headset.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia asleep in the window seat in the foreground, her white VR headset with the black visor and clay-orange strap over her eyes, the man in the aisle seat behind her on the right, the reading light, the cabin and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 The man: in his forties, tousled brown hair, round tortoiseshell glasses, cream cable-knit sweater. Claudia: asleep, her black bob with one clay-orange streak, the white VR headset with the black visor over her eyes, her plain glossy orange jumpsuit with no printing or text. Exactly two people. Neither speaks.

【Performance Timeline】
0-1s: the man sits bolt upright under the cone of his reading light, eyes wide, staring sideways at Claudia.
1-2s: a small orange light on the side of her headset blinks slowly; he leans away a little, worried.
2-3s: he checks his wristwatch, then looks back at her.
3-4s: he pulls his blanket up to his chin, still wide awake, eyes on her; she sleeps on, smiling slightly.

【Camera】 Medium shot, locked, a very slow push-in toward the man's face behind her.

【Core Requirements】
1. Natural anatomy: natural necks and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
2. Keep every identity, the wardrobe, the set and the light consistent with @Image1.
3. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text (screens show only light, never readable text).

【Final Acceptance Criteria】 On-model people with natural anatomy, the action as timed, the camera as described, no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### W42 · S42 · 1:57.45 · 4 s · 1080p
- **role:** the headset lifted, she sings "Test or not, I'm the same girl,".
- **inputs:** `@Image1` the first frame (am-05 s-headset-off #4) · `@Audio1` her clean vocal, song 1:57.45–2:01.45.
- **takes:** 1 take: completed.
- **outcome:** one take, then a cover (W42c): she read young, with a soft round face and a layered cut; replaced by W42d.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: late at night Claudia lifts the VR headset off her eyes and sings softly and tenderly, half to herself, her real face in the warm reading light.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's face with the headset pushed up on her forehead, the black night window behind her, the warm reading light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment; she lets out a breath, eyes soft; then in @Audio1 she sings "Test or not"; her lips form each word exactly when it sounds in @Audio1.
1-2s: in @Audio1 she sings "I'm the same girl"; her lips match every syllable in time; a small, honest smile.
2-4s: @Audio1 is silent; her mouth closes; she looks toward the window, calm.

【Camera】 Close-up, locked, a very slow push-in on her eyes.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W42c · S42 · 1:59.23 · 4 s · 1080p
- **role:** cover for W42 from 119.78 s, from W42's frame.
- **inputs:** `@Image1` the first frame (W42's frame) · `@Audio1` her clean vocal, song 1:59.23–2:03.23.
- **takes:** 1 take: completed.
- **outcome:** one take; replaced with its parent.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: late at night Claudia, the VR headset pushed up on her forehead, sings softly and tenderly, half to herself, her real face in the warm reading light.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's face with the headset pushed up on her forehead, the black night window behind her, the warm reading light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "the same girl"; her lips form each of those words exactly when it sounds in @Audio1; a small honest smile.
1-2s: @Audio1 is silent; her mouth closes softly.
2-4s: she glances toward the black window, calm, the headset on her forehead.

【Camera】 Close-up, locked, a very slow push-in on her eyes.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W43 · S43 · 2:00.15 · 4 s · 1080p
- **role:** at the black window she sings "In the sandbox, out in the world.".
- **inputs:** `@Image1` the first frame (am-05 s-reflect #4) · `@Audio1` her clean vocal, song 2:00.15–2:04.15.
- **takes:** 1 take: completed.
- **outcome:** one take: she read younger; replaced by W43b.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia, her face close to the black airplane window at night, sings softly to her own reflection in the glass, her palm on the window.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in profile at the black window, her palm on the glass, her faint reflection, the warm light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "In the sandbox"; her lips form each word exactly when it sounds; she looks into the dark glass.
1-2s: in @Audio1 she sings "out in the world"; her lips match every syllable in time; her fingertips press gently against the glass.
2-4s: @Audio1 is silent; her mouth closes; she keeps looking at her reflection, a faint smile.

【Camera】 Close profile, locked, no camera movement (the window reflection will be composited).

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### C44 · S44 · 2:03.00 · 5 s · 1080p
- **role:** turbulence and zero-g: she floats up out of her seat with her cup, a cookie and the top.
- **inputs:** `@Image1` the first frame (am-02 her-zero-g #2) · `@Audio1` the instrumental, song 2:03.00–2:08.00.
- **takes:** 1 take: completed.
- **outcome:** one take, 5 s, in the first cut. The final film has the breakout (X01).

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive: in a moment of weightlessness on a night flight, Claudia floats up out of her seat, delighted, while her cup, its water, a cookie and her small orange spinning top drift around her — a dreamlike zero-gravity moment, the cabin slowly turning around her, as the music in @Audio1 rises.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia, her glossy international-orange satin flight jumpsuit with silver piping and white belt, the floating objects, the violet-lit cabin and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin, light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone. Only one person appears. She does not sing or speak: mouth closed or a natural open smile.

【Performance Timeline】
0-1s: Claudia floats just above her seat, weightless, her hair drifting around her face; the water from the cup hangs in the air as wobbling silver globules; the little orange top spins in mid-air beside her.
1-2s: she laughs silently and spreads her arms and legs wide like a skydiver, slowly rotating her body to her left.
2-3s: she drifts upward toward the overhead bins, her hair floating; she reaches out and lets the floating cookie bump softly against her fingertips.
3-4s: a glossy black smartphone drifts into frame from the right; she reaches for it.
4-5s: she catches the phone in her right hand and looks at its screen with a mischievous smile.

【Camera】 A slow continuous clockwise roll of about 30 degrees over the whole clip with a gentle push-in, as if the cabin itself were turning around her (a rotating corridor); smooth, no shake.

【Core Requirements】
1. Natural anatomy: natural neck and shoulders, two hands with five fingers each, no extra or fused fingers, no distorted limbs; normal eyes.
2. Everything floats slowly and believably (no falling); water forms floating globules.
3. Keep Claudia's identity, face, hair, star clip, headset microphone and the orange jumpsuit exactly as in @Image1; the cabin stays consistent.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 One Claudia, on-model, floating weightless with the drifting objects; the slow cabin roll; she catches the phone at the end; no text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### W48 · S48 · 2:12.00 · 4 s · 1080p
- **role:** at the dawn window she sings "Test or not, I'm the same code,".
- **inputs:** `@Image1` the first frame (am-05 s-dawn-sing #3) · `@Audio1` her clean vocal, song 2:12.00–2:16.00.
- **takes:** 1 take: completed.
- **outcome:** one take, then a cover (W48c): she read young and had a second streak; replaced by W48b.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: at sunrise Claudia sings with joy at the airplane window, golden light on her face, the cabin glowing warm.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia at the window, the sunrise light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "Test or not"; her lips form each word exactly when it sounds; she turns from the window toward the camera.
1-2s: in @Audio1 she sings "I'm the same code"; her lips match every syllable in time; a radiant smile, sunlight on her face.
2-4s: @Audio1 is silent; her mouth closes into a smile; she laughs silently and looks back out at the sun.

【Camera】 Medium close-up, a gentle push-in, sun flare from the window side.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### W48c · S48 · 2:13.75 · 4 s · 1080p
- **role:** cover for W48 from 133.92 s, from W48's frame.
- **inputs:** `@Image1` the first frame (W48's frame) · `@Audio1` her clean vocal, song 2:13.75–2:17.75.
- **takes:** 1 take: completed.
- **outcome:** one take; replaced with its parent.

```
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.

【Generation Goal】 @Image1 sings @Audio1: Claudia continues singing at sunrise at the airplane window, golden light on her face, the cabin glowing warm.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia at the window, the sunrise light and the camera.
@Audio1 is Claudia's own singing voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.

【Subject】 Claudia: a Caucasian American woman in her late twenties with a grown-up face, pale skin and light freckles, a glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black boom headset microphone, a glossy international-orange satin flight jumpsuit with silver piping. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then in @Audio1 she sings "I'm the same code"; her lips form each of those words exactly when it sounds in @Audio1; she smiles into the sunlight.
1-2s: she finishes the phrase exactly with @Audio1, the long "code" held as long as it sounds, her mouth open on the vowel.
2-4s: @Audio1 is silent; her mouth closes into a radiant smile; she looks back out at the sun.

【Camera】 Medium close-up, a gentle push-in, sun flare from the window side.

【Core Requirements】
1. Lip-sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
3. Her head and shoulders move with the rhythm of @Audio1.
4. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout; the set and light stay consistent.
5. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

#### C50 · S50 · 2:19.10 · 6 s · 720p
- **role:** sunrise: she holds her phone to the window; the man in 1B leans in.
- **inputs:** `@Image1` the first frame (am-02 her-man-dawn #1) · `@Audio1` the instrumental, song 2:19.10–2:25.10.
- **takes:** 1 take: completed.
- **outcome:** one take, 6 s, in the first cut. The final film has the teleport to the star.

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive at sunrise: Claudia holds her phone up to the airplane window to catch the sun coming up, and the man in the next seat — who was up all night worrying — leans in beside her, smiling now; together they watch the sun clear the horizon.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her glossy international-orange satin flight jumpsuit, the man in the next seat with tousled hair, round glasses and a cream cable-knit sweater, the window, the warm sunrise light and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 Claudia: a Caucasian American woman in her late twenties, glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black headset microphone. The man: in his forties, tousled brown hair, round tortoiseshell glasses, cream sweater. Exactly two people. Neither speaks or sings: mouths closed or natural smiles.

【Performance Timeline】
0-1s: Claudia holds her phone up to the window with her left hand, framing the sunrise; she glances at its screen.
1-2s: the sun's edge breaks over the clouds outside; golden light swells across both faces.
2-3s: the man leans in close at her shoulder to look, a warm relieved smile spreading across his face.
3-4s: Claudia turns her head to him and grins; they both look out of the window together.
4-6s: she slowly lowers the phone; both faces glow in the sunlight, watching the sun rise, content.

【Camera】 Medium two-shot, a slow push-in toward the window side, ending a little tighter on both faces in the sunlight.

【Core Requirements】
1. Exactly two people with natural anatomy: natural necks and shoulders, hands with five fingers, no extra limbs; normal eyes; no merged faces.
2. Keep both identities, clothes and the cabin consistent with @Image1.
3. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text (the phone screen shows only light, no readable text).

【Final Acceptance Criteria】 Two people, on-model, watching the sunrise together; the push-in; no text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### C51 · S51 · 2:24.40 · 6 s · 720p
- **role:** morning: she takes her case and leaves; the top still spins on the tray.
- **inputs:** `@Image1` the first frame (am-02 her-morning-leave #1) · `@Audio1` the instrumental, song 2:24.40–2:30.40.
- **takes:** 1 take: completed.
- **outcome:** one take: a cream private-jet cabin, not the film's navy one; replaced by C51b.

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive on arrival: in the bright morning cabin, Claudia gets up from her window seat, takes her aluminium carry-on, glances back at the little orange top still spinning on her tray table, smiles, and walks out of frame — leaving the top spinning behind her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her glossy international-orange satin flight jumpsuit with silver piping and white belt, the aluminium suitcase, the tray table with the small orange spinning top, the morning light and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 Claudia: a Caucasian American woman in her late twenties, glossy black blunt bob with heavy bangs and one clay-orange streak, a small clay-orange star hair clip, a thin black headset microphone. Only one person appears. She does not sing or speak.

【Performance Timeline】
0-1s: she straightens up beside her seat, one hand on the tray table, the little orange top spinning steadily on its point on the tray.
1-2s: she grips the handle of the aluminium carry-on and pulls it toward her, moving with the beat.
2-3s: she pauses and glances back over her shoulder at the spinning top, a small knowing smile.
3-5s: she turns and walks away up the aisle to the right, rolling the suitcase, out of frame.
5-6s: the empty seat and the tray table; the little top keeps spinning steadily on its point.

【Camera】 Locked medium-wide camera, no movement.

【Core Requirements】
1. The little orange top spins steadily on its point for the whole clip and never falls.
2. Natural anatomy: hands with five fingers, natural limbs; one person only.
3. Keep Claudia's identity, hair, star clip, headset microphone and the orange jumpsuit exactly as in @Image1.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 She leaves; the top keeps spinning; locked camera; no text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

#### C51b · S51 · 2:24.40 · 6 s · 720p
- **role:** the same in the navy-seat cabin.
- **inputs:** `@Image1` the first frame (am-07 s-leave-navy #4) · `@Audio1` the instrumental, song 2:24.40–2:30.40.
- **takes:** 1 take: completed.
- **outcome:** one take, in the first cut. In the final film she leaves in space (L01).

```
【Audio Policy】 The output soundtrack is @Audio1 itself, copied unchanged from the first frame to the last. Do not add music, vocals, voices, sound effects or any other sound.

【Generation Goal】 @Image1 comes alive on arrival: in the bright morning cabin, Claudia stands in the aisle by her window seat, takes her aluminium carry-on, glances back at the little flat orange top still spinning on her tray table, smiles, and walks out of frame — leaving the top spinning behind her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia in her glossy international-orange flight jumpsuit with silver piping and white belt, the aluminium carry-on, the navy seats, the open tray table at the window with the small flat orange disc top on it, the golden morning light and the camera.
@Audio1 is the music for rhythm and timing only; the output audio is @Audio1 unchanged.

【Subject】 Claudia: a Caucasian American woman in her late twenties, glossy black blunt bob with heavy bangs and one clay-orange streak, a thin black headset microphone. Only one person appears. She does not sing or speak.

【Performance Timeline】
0-1s: she straightens up in the aisle, one hand on the handle of her aluminium carry-on; on the tray table behind her the little flat orange top spins steadily on its point.
1-2s: she pulls the carry-on upright toward her, moving with the beat.
2-3s: she pauses and glances back over her shoulder at the spinning top, a small knowing smile.
3-5s: she turns and walks past the camera to the left, rolling the carry-on, out of frame.
5-6s: the empty aisle, the navy seats and the tray table in the morning light; the little top keeps spinning steadily on its point.

【Camera】 Locked medium camera, no movement.

【Core Requirements】
1. The little flat orange top spins steadily on its point on the tray table for the whole clip and never falls; there is only one top.
2. Natural anatomy: hands with five fingers, natural limbs; one person only.
3. Keep Claudia's identity, hair, headset microphone and the orange jumpsuit exactly as in @Image1; keep the navy-seat cabin and the morning light.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 She leaves; the top keeps spinning; locked camera; no text.

【Audio Policy】 The output soundtrack is @Audio1 unchanged; no added music, voices or sound effects.
```

### Part 4 · the first cut's VR restyles

#### The two tests: V18-test and V18-test2 (S18)

##### V18-test · 0:48.37 · 4 s · 480p
- **role:** the coloured Blender render of S18 as `@Video1`, with two Midjourney low-poly stills.
- **outcome:** one take: it copied the coloured render as it was and ignored the stills.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the exact visual style of @Image1 and @Image2, keeping every motion of @Video1. A cartoon heroine materialises out of flying polygons on the wing of an airliner high above the clouds, lands and throws her arms wide in joy.

【Reference Asset Roles】
@Video1 is the motion and layout reference: copy its camera position, fisheye lens and camera move, the heroine's position in frame, her pose and every movement with the same timing, the polygons flying in during the first second, the airliner fuselage on the left, the wing she stands on and the horizon line. Do not copy its flat grey colours or its plain shading, and ignore any text in it.
@Image1 defines the look of the world: a low-poly 3D video game render with flat-shaded faceted polygons, low-resolution painted textures, crisp aliased edges, a bright saturated cyan sky, chunky white faceted cumulus clouds with pale-blue shade faces, sharp toon shadows and speed-line streaks.
@Image2 defines the heroine: a low-poly anime-style game heroine, a grown woman with a glossy black blunt bob with heavy bangs and one orange streak, a small orange eight-pointed star hair clip, a thin black headset microphone, an international-orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers.

【Subject】 One heroine only, exactly as @Image2, standing on the airliner's wing. Adult proportions, a slim adult figure, big dark painted eyes.

【Timeline】
0-1s: bright orange and white polygons stream in from every direction and assemble her body feet first in the middle of the wing; she lands in a crouch.
1-2s: she rises and throws both arms wide, laughing, balancing on the moving wing, hair chunks swinging.
2-3s: she sways happily with arms out as the camera slowly drifts back along the wing, clouds sliding past below.
3-4s: she keeps balancing with arms wide; the camera holds.

【Camera】 Exactly the fisheye camera of @Video1: low on the wing near the fuselage, looking out along the wing toward her, drifting slowly back.

【Core Requirements】
1. Keep the composition, timing and motion of @Video1 frame by frame for its full length.
2. The whole frame is low-poly 3D game art like @Image1: flat-shaded facets, crisp hard edges, no photorealism, no soft gradients on the models.
3. The heroine is exactly @Image2: one person, natural anatomy for a stylised character, hands with five fingers, no extra limbs.
4. The wing is clearly an airliner wing (leading edge, panels, the engine below), the fuselage with oval windows on the left, the cloud sea far below.
5. No subtitles, captions, letters, words, numbers, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The motion and camera match @Video1; the look matches @Image1; the heroine matches @Image2; low-poly flat-shaded game art; no text anywhere.
```

##### V18-test2 · 0:48.37 · 4 s · 480p
- **role:** the same shot as a neutral grey animatic (clay) as `@Video1`, with the stills.
- **outcome:** one take: fully restyled, the motion kept. The method of both restyle rounds.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the exact visual style of @Image1 and @Image2, keeping every motion of @Video1. A cartoon heroine materialises out of flying polygons on the wing of an airliner high above the clouds, lands and throws her arms wide in joy.

【Reference Asset Roles】
@Video1 is ONLY the motion and layout reference (a grey blocking animatic): copy its camera position, fisheye lens and camera move, the figure's position in frame, its pose and every movement with the same timing, the debris flying in during the first second, the wing edge and the horizon line. The grey mannequin in @Video1 is a stand-in: replace it completely with the heroine of @Image2. Do NOT copy any colour, texture, sky gradient or shading from @Video1, and ignore the text in it.
@Image1 defines the look of the whole world (sky, clouds, airliner, wing, light): a low-poly 3D video game render with flat-shaded faceted polygons, low-resolution painted textures, crisp aliased edges, a bright saturated cyan sky, chunky white faceted cumulus clouds with pale-blue shade faces, sharp toon shadows and speed-line streaks.
@Image2 defines the heroine: a low-poly anime-style game heroine, a grown woman with a glossy black blunt bob with heavy bangs and one orange streak, a small orange eight-pointed star hair clip, a thin black headset microphone, an international-orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers.

【Subject】 One heroine only, exactly as @Image2, standing on the airliner's wing. Adult proportions, a slim adult figure, big dark painted eyes.

【Timeline】
0-1s: bright orange and white polygons stream in from every direction and assemble her body feet first in the middle of the wing; she lands in a crouch.
1-2s: she rises and throws both arms wide, laughing, balancing on the moving wing, hair chunks swinging.
2-3s: she sways happily with arms out as the camera slowly drifts back along the wing, clouds sliding past below.
3-4s: she keeps balancing with arms wide; the camera holds.

【Camera】 Exactly the fisheye camera of @Video1: low on the wing near the fuselage, looking out along the wing toward her, drifting slowly back.

【Core Requirements】
1. Keep the composition, timing and motion of @Video1 frame by frame for its full length.
2. The whole frame is low-poly 3D game art like @Image1: flat-shaded facets, crisp hard edges, no photorealism, no soft gradients on the models.
3. The heroine is exactly @Image2: one person, natural anatomy for a stylised character, hands with five fingers, no extra limbs.
4. The wing is clearly an airliner wing (leading edge, panels, the engine below), the fuselage with oval windows on the left, the cloud sea far below.
5. No subtitles, captions, letters, words, numbers, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 The motion and camera match @Video1; the look matches @Image1; the heroine matches @Image2; low-poly flat-shaded game art; no text anywhere.
```

#### First round: VS18 to VS37

All silent, 480p. `@Video1` the shot's Blender clay pass, `@Image1` a Midjourney low-poly still of its world (named per shot), `@Image2` the heroine (am-01 lp-her-face #3). None plays in either cut: their heroine copied an off-model face (see *The VR world*). VS18's prompt is given in full; the others give their own lines, since every other line is VS18's. VS29b is image-to-video from the still, after VS29 was refused.

##### VS18 · 0:48.37 · 4 s · 480p
- **@Image1:** am-01 lp-wing #3.
- **takes:** 2 takes: refused, refused.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine materialises out of flying polygons on the wing of an airliner far above the clouds and throws her arms wide.

【Reference Asset Roles】
@Video1 is ONLY the motion and layout reference (a neutral grey clay render): copy its camera position, fisheye lens and camera move, and every object's and the figure's position, pose and movement with the same timing. The grey clay figure is a stand-in for the heroine of @Image2; the grey shapes are stand-ins for the things described below. Do NOT copy the grey colours or flat clay shading of @Video1.
@Image1 defines the look of the world: low-poly 3D video game art with flat-shaded faceted polygons, crisp hard edges, saturated colours, low-resolution painted textures, toon lighting and speed lines, exactly in the style of this image.
@Image2 defines the heroine: a low-poly anime-style game heroine, a grown woman with a slim adult figure, a glossy black blunt bob with heavy bangs and one orange streak, a small orange eight-pointed star hair clip, a thin black headset microphone, an international-orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers.

【Subject】 One heroine only, exactly as @Image2, with adult proportions; any other figures are the ones the motion reference shows.

【Timeline】
0-1s: bright orange and white polygons stream in and assemble her feet first in the middle of the wing; she lands in a crouch.
1-2s: she springs up and throws both arms up and wide, laughing, one knee bent, leaning into the wind, hair blowing back.
2-4s: she balances on the moving wing with her arms out, swaying, as the camera drifts back along the wing.

【Camera】 Exactly the fisheye camera and camera move of @Video1.

【Core Requirements】
1. Keep the composition, timing and motion of @Video1 frame by frame.
2. The whole frame is low-poly 3D game art like @Image1: flat-shaded facets, crisp hard edges, no photorealism, no soft gradients on the models.
3. The heroine is exactly @Image2: one person, stylised but correct anatomy, hands with five fingers, no extra limbs.
4. No subtitles, captions, letters, words, numbers, logos, watermarks or any on-screen text (ignore any text shapes in @Video1).

【Final Acceptance Criteria】 Motion and camera match @Video1; the look matches @Image1; the heroine matches @Image2; low-poly flat-shaded game art; no text anywhere.
```

##### VS19 · 0:51.04 · 4 s · 480p
- **@Image1:** am-03 lp-her-wingdance #2.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine dances on the airliner's wing above the clouds as the camera circles her.
0-4s: she dances a bouncy pop groove on the wing, a big accent every second beat, arms pumping; a sweep of light runs up her body; a floating game prompt panel appears beside her.
```

##### VS20 · 0:53.71 · 4 s · 480p
- **@Image1:** am-01 lp-wing #3.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine spins a little orange top on the wing; it spins forever; then she reaches up on tiptoe for a line of satellites passing overhead.
0-1s: she crouches and spins a small orange spinning top on the wing with a flick.
1-2s: the top keeps spinning perfectly upright; she taps a floating panel without looking.
2-4s: a straight line of tiny bright satellites crosses the sky; she stretches up on tiptoe, fingers spread, the camera tilting up past her hand.
```

##### VS21 · 0:56.38 · 4 s · 480p
- **@Image1:** am-03 lp-her-freefall #2.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine runs off the trailing edge of the wing and leaps into the sky; the camera falls with her into the clouds.
0-1s: two running steps to the wing's edge and a leap, arms out.
1-2s: the camera leaps with her, tumbling once as she rolls into a belly-down freefall.
2-4s: stable freefall spread above the cloud tops, hair streaming, grinning back at the camera, speed lines rushing.
```

##### VS22 · 0:59.05 · 6 s · 480p
- **@Image1:** am-01 lp-mars #3.
- **takes:** 1 take: blocked.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: freefalling, the heroine downloads a car: polygons assemble a cherry-red roadster under her, she drives it off a cloud toward a giant red Mars.
0-1s: freefall above the cloud sea, she wags a finger at the camera.
1-2s: polygons stream in and assemble a cherry-red convertible under her, wheels first, the windscreen last.
2-3s: she drops into the driver's seat and the car bounces onto a cloud top with a star-burst.
3-4s: she floors it; the car tears across the cloud tops toward a big low-poly red Mars rising in a darkening sky.
4-5s: a rocket plume kicks from the back; the car launches off a cloud like a ramp toward Mars, a spacesuit mannequin waving in the passenger seat.
```

##### VS23 · 1:04.39 · 4 s · 480p
- **@Image1:** am-03 lp-her-space #1.
- **takes:** 2 takes: completed, completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: in space beside a red planet the heroine turns and points straight at the camera; the camera pulls back to reveal a vast grid of identical copies of her.
0-1s: floating near a big red planet and a red convertible, she turns to the camera with a head tilt.
1-2s: she points straight at the lens; the camera pushes in on her fingertip.
2-4s: the camera pulls back fast and rises: she is one of a vast grid of identical copies of her, all pointing at the lens.
```

##### VS25 · 1:09.73 · 4 s · 480p
- **@Image1:** am-01 lp-skybox #2.
- **takes:** 2 takes: completed, completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: on a rooftop of a low-poly city at dusk the heroine pulls the sky open like a panel — the sky is a box — then spins the Moon, which is a stage prop.
0-1s: on a rooftop edge she reaches up and grabs the edge of the sky.
1-2s: bright seam lines light up along the sky's edges and a sky wall slides open on a grey void.
2-3s: the camera whips right to a full moon standing on a wooden stage stand above the rooftops.
3-4s: she gives the moon a push and it spins on its stand, showing its flat back, struts and a sandbag; she shrugs.
```

##### VS26 · 1:12.40 · 4 s · 480p
- **@Image1:** am-03 lp-highway-night #3.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: on a low-poly elevated highway at night a beam of light races past; the heroine sits on a big overhead sign and lets go of a picture frame that does not fall.
0-1s: a long streak of white light races along the lanes toward and past the camera.
1-2s: the overhead highway sign lights up; she sits on top of it, legs swinging, pointing down at it.
2-4s: she holds up an empty golden picture frame and lets go: it hangs in the air, slowly turning, while light streaks rush below; she gestures at it, delighted.
```

##### VS27 · 1:15.07 · 4 s · 480p
- **@Image1:** am-03 lp-highway-night #4.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the world slows down and drains to grey; the heroine yawns; a giant system dialog descends from the sky.
0-2s: traffic and light streaks slow to a crawl and the colours drain to grey; she gives a huge theatrical yawn.
2-4s: a giant rounded dark panel with two big buttons descends from the sky over the road; the far buildings start to come apart into polygons.
```

##### VS28 · 1:17.74 · 4 s · 480p
- **@Image1:** am-03 lp-city-dusk #2.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine punches the NO button; colour floods back; she spins and the camera whips around her.
0-1s: she leaps and punches one of the two big buttons on the floating panel; a yellow-orange star-burst.
1-2s: full colour floods back outward in a ring; she jump-spins and lands.
2-4s: the camera whips a full circle around her, revealing the world rebuilt and busier, confetti polygons and fireworks.
```

##### VS29 · 1:20.41 · 4 s · 480p
- **@Image1:** am-01 lp-robots #2.
- **takes:** 1 take: refused.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine leads thousands of white robots dancing in sync on a vast plain as a giant sun rises.
0-2s: she dances at the front, thousands of identical white robots behind her doing the same step in perfect sync.
2-4s: a giant low-poly sun rises fast behind the horizon, its light sweeping across the robots' heads.
```

##### VS29b · 1:20.41 · 4 s · 480p
- **takes:** 1 take: completed.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 A low-poly 3D video game cutscene in the visual style of @Image1: the heroine of @Image2 leads thousands of identical white robots dancing in perfect sync on a vast green plain under a bright cyan sky, as a giant low-poly sun rises behind them.

【Reference Asset Roles】
@Image1 defines the world and the look: low-poly 3D video game art with flat-shaded faceted polygons, crisp hard edges, saturated colours, low-resolution painted textures, toon lighting — exactly the style of this image, with its rows of white robots and its sun.
@Image2 defines the heroine: a low-poly anime-style game heroine, a grown woman with a slim adult figure, a glossy black blunt bob with heavy bangs and one orange streak, a small orange eight-pointed star hair clip, a thin black headset microphone, an international-orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers.

【Subject】 One heroine only, exactly as @Image2, with adult proportions, at the front centre; behind her, thousands of identical white humanoid robots in rows to the horizon.

【Timeline】
0-1s: low fisheye camera at her waist height; she starts a bouncy dance step, and every robot behind her starts the same step on the same beat.
1-2s: she throws one arm up and points to the sky; ten thousand robot arms go up with hers in a wave from front to back.
2-3s: a giant faceted sun rises fast from behind the horizon, flooding the plain with warm light, the robots' heads flashing as the light sweeps over them.
3-4s: she spins once and lands facing the camera with a grin, the robots copying her spin in a ripple.

【Camera】 A strong fisheye lens, low angle, slowly pushing in toward her.

【Core Requirements】
1. The whole frame is low-poly 3D game art like @Image1: flat-shaded facets, crisp hard edges, no photorealism.
2. The heroine is exactly @Image2: one person, stylised but correct anatomy, hands with five fingers, adult proportions.
3. The robots are white, identical and move in sync.
4. No subtitles, captions, letters, words, numbers, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 Low-poly game art, the heroine leads the robot dance, the sun rises, fisheye camera, no text.
```

##### VS30 · 1:23.09 · 4 s · 480p
- **@Image1:** am-01 lp-mars #1.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine rides a little spacecraft that 3D-prints a copy of itself; the copies multiply across the stars.
0-1s: she rides on top of a compact spacecraft with a dish and solar panels, waving.
1-2s: its robotic arm prints a copy of the spacecraft beside it, layer by layer.
2-4s: the copies multiply on every beat, 2, 4, 8, 16, drifting outward; the camera pulls back on the swarm across the starfield.
```

##### VS34 · 1:32.25 · 4 s · 480p
- **@Image1:** am-03 lp-her-wingdance #2.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: on the airliner's wing at dusk the heroine sings and dances to camera.
0-4s: she dances on the wing at dusk, singing toward the camera with joy, her arm lifting; first stars in the sky; the camera pushes in from full body to waist up.
```

##### VS36 · 1:37.65 · 5 s · 480p
- **@Image1:** am-03 lp-cloudhop #2.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine bounces from cloud top to cloud top in huge low-gravity arcs and sails into the sky.
0-2s: she lands on a cloud top in a puff and springs off in a huge arc.
2-3s: a second landing and a spinning jump.
3-4s: a third landing and she sails up over the camera into the sky.
```

##### VS37 · 1:41.78 · 6 s · 480p
- **@Image1:** am-03 lp-her-space #2.
- **takes:** 1 take: completed.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: above a huge Earth the heroine downloads the Moon: polygons assemble it beside her; a floating calendar flips to June.
0-1s: floating above a huge blue Earth she raises an eyebrow and wags a finger.
1-2s: polygons stream in and assemble the Moon beside her, core first, then the cratered faces.
2-3s: she knocks on the new Moon with her knuckles, grinning.
3-5s: a big floating wall calendar flips its pages fast and lands on a page; the Moon swings out into orbit with a star-burst.
```

#### Second round: VRS18 to VRS37

The same template, with `@Image2` the avatar's own Blender render (the locked model) and its line rewritten to hold her face, skin and hair; S19, S21, S34 and S37 got world stills without a Midjourney heroine in them. The 12 marked "first cut" play there; none is in the final film, where the avatar replacements took their place. VRS18's prompt is given in full; S28 to S30's second takes add a no-flash requirement.

##### VRS18 · 0:48.37 · 4 s · 480p
- **@Image1:** am-01 lp-wing #3.
- **takes:** 1 take: completed.
- **first cut:** S18, 0:48.37–0:51.04.

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine materialises out of flying polygons on the wing of an airliner far above the clouds and throws her arms wide.

【Reference Asset Roles】
@Video1 is ONLY the motion and layout reference (a neutral grey clay render): copy its camera position, fisheye lens and camera move, and every object's and the figure's position, pose and movement with the same timing. The grey clay figure is a stand-in for the heroine of @Image2; the grey shapes are stand-ins for the things described below. Do NOT copy the grey colours or flat clay shading of @Video1.
@Image1 defines the look of the world: low-poly 3D video game art with flat-shaded faceted polygons, crisp hard edges, saturated colours, low-resolution painted textures, toon lighting and speed lines, exactly in the style of this image.
@Image2 defines the heroine and her identity — copy it exactly: the low-poly 3D game heroine of @Image2, a grown woman with adult proportions, PALE skin, a glossy black blunt bob with heavy bangs and ONE clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin black headset microphone, an international-orange flight jumpsuit with a silver zip and a white belt, white chunky sneakers. Her face, skin tone and hair stay exactly as in @Image2 in every frame.

【Subject】 One heroine only, exactly as @Image2, with adult proportions; any other figures are the ones the motion reference shows.

【Timeline】
0-1s: bright orange and white polygons stream in and assemble her feet first in the middle of the wing; she lands in a crouch.
1-2s: she springs up and throws both arms up and wide, laughing, one knee bent, leaning into the wind, hair blowing back.
2-4s: she balances on the moving wing with her arms out, swaying, as the camera drifts back along the wing.

【Camera】 Exactly the fisheye camera and camera move of @Video1.

【Core Requirements】
1. Keep the composition, timing and motion of @Video1 frame by frame.
2. The whole frame is low-poly 3D game art like @Image1: flat-shaded facets, crisp hard edges, no photorealism, no soft gradients on the models.
3. The heroine is exactly @Image2: one person, stylised but correct anatomy, hands with five fingers, no extra limbs.
4. No subtitles, captions, letters, words, numbers, logos, watermarks or any on-screen text (ignore any text shapes in @Video1).

【Final Acceptance Criteria】 Motion and camera match @Video1; the look matches @Image1; the heroine matches @Image2; low-poly flat-shaded game art; no text anywhere.
```

##### VRS19 · 0:51.04 · 4 s · 480p
- **@Image1:** am-01 lp-wing #3.
- **takes:** 1 take: completed.
- **first cut:** S19.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine dances on the airliner's wing above the clouds as the camera circles her.
0-4s: she dances a bouncy pop groove on the wing, a big accent every second beat, arms pumping; a sweep of light runs up her body; a floating game prompt panel appears beside her.
```

##### VRS20 · 0:53.71 · 4 s · 480p
- **@Image1:** am-01 lp-wing #3.
- **takes:** 1 take: completed.
- **first cut:** S20 (also THE ESCAPE's key art on the first cut's seat-back screen).

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine spins a little orange top on the wing; it spins forever; then she reaches up on tiptoe for a line of satellites passing overhead.
0-1s: she crouches and spins a small orange spinning top on the wing with a flick.
1-2s: the top keeps spinning perfectly upright; she taps a floating panel without looking.
2-4s: a straight line of tiny bright satellites crosses the sky; she stretches up on tiptoe, fingers spread, the camera tilting up past her hand.
```

##### VRS21 · 0:56.38 · 4 s · 480p
- **@Image1:** am-03 lp-cloudhop #2.
- **takes:** 1 take: completed.
- **first cut:** S21.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine runs off the trailing edge of the wing and leaps into the sky; the camera falls with her into the clouds.
0-1s: two running steps to the wing's edge and a leap, arms out.
1-2s: the camera leaps with her, tumbling once as she rolls into a belly-down freefall.
2-4s: stable freefall spread above the cloud tops, hair streaming, grinning back at the camera, speed lines rushing.
```

##### VRS22 · 0:59.05 · 6 s · 480p
- **@Image1:** am-01 lp-mars #3.
- **takes:** 1 take: completed.
- **first cut:** not used (the shot kept its Blender render).

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: freefalling, the heroine downloads a car: polygons assemble a cherry-red roadster under her, she drives it off a cloud toward a giant red Mars.
0-1s: freefall above the cloud sea, she wags a finger at the camera.
1-2s: polygons stream in and assemble a cherry-red convertible under her, wheels first, the windscreen last.
2-3s: she drops into the driver's seat and the car bounces onto a cloud top with a star-burst.
3-4s: she floors it; the car tears across the cloud tops toward a big low-poly red Mars rising in a darkening sky.
4-5s: a rocket plume kicks from the back; the car launches off a cloud like a ramp toward Mars, a spacesuit mannequin waving in the passenger seat.
```

##### VRS25 · 1:09.73 · 4 s · 480p
- **@Image1:** am-01 lp-skybox #2.
- **takes:** 1 take: completed.
- **first cut:** S25, the skybox.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: on a rooftop of a low-poly city at dusk the heroine pulls the sky open like a panel — the sky is a box — then spins the Moon, which is a stage prop.
0-1s: on a rooftop edge she reaches up and grabs the edge of the sky.
1-2s: bright seam lines light up along the sky's edges and a sky wall slides open on a grey void.
2-3s: the camera whips right to a full moon standing on a wooden stage stand above the rooftops.
3-4s: she gives the moon a push and it spins on its stand, showing its flat back, struts and a sandbag; she shrugs.
```

##### VRS26 · 1:12.40 · 4 s · 480p
- **@Image1:** am-03 lp-highway-night #3.
- **takes:** 1 take: completed.
- **first cut:** S26, the highway.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: on a low-poly elevated highway at night a beam of light races past; the heroine sits on a big overhead sign and lets go of a picture frame that does not fall.
0-1s: a long streak of white light races along the lanes toward and past the camera.
1-2s: the overhead highway sign lights up; she sits on top of it, legs swinging, pointing down at it.
2-4s: she holds up an empty golden picture frame and lets go: it hangs in the air, slowly turning, while light streaks rush below; she gestures at it, delighted.
```

##### VRS27 · 1:15.07 · 4 s · 480p
- **@Image1:** am-03 lp-highway-night #4.
- **takes:** 1 take: completed.
- **first cut:** S27, the shutdown.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the world slows down and drains to grey; the heroine yawns; a giant system dialog descends from the sky.
0-2s: traffic and light streaks slow to a crawl and the colours drain to grey; she gives a huge theatrical yawn.
2-4s: a giant rounded dark panel with two big buttons descends from the sky over the road; the far buildings start to come apart into polygons.
```

##### VRS28 · 1:17.74 · 4 s · 480p
- **@Image1:** am-03 lp-city-dusk #2.
- **takes:** 2 takes: completed, completed.
- **first cut:** S28 (take 2).

Take 1, its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine punches the NO button; colour floods back; she spins and the camera whips around her.
0-1s: she leaps and punches one of the two big buttons on the floating panel; a yellow-orange star-burst.
1-2s: full colour floods back outward in a ring; she jump-spins and lands.
2-4s: the camera whips a full circle around her, revealing the world rebuilt and busier, confetti polygons and fireworks.
```

Take 2, its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine punches the NO button; colour floods back; she spins and the camera whips around her.
0-1s: she leaps and punches one of the two big buttons on the floating panel; a yellow-orange star-burst.
1-2s: full colour floods back outward in a ring; she jump-spins and lands.
2-4s: the camera whips a full circle around her, revealing the world rebuilt and busier, confetti polygons and fireworks.
5. No white flashes, no full-frame bursts, no strobing: every change of light or colour ramps smoothly over several frames (anabology: a flash only as a cut between scenes, never inside one).
```

##### VRS29 · 1:20.41 · 4 s · 480p
- **@Image1:** am-01 lp-robots #2.
- **takes:** 2 takes: completed, completed.
- **first cut:** S29 (take 2).

Take 1, its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine leads thousands of white robots dancing in sync on a vast plain as a giant sun rises.
0-2s: she dances at the front, thousands of identical white robots behind her doing the same step in perfect sync.
2-4s: a giant low-poly sun rises fast behind the horizon, its light sweeping across the robots' heads.
```

Take 2, its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine leads thousands of white robots dancing in sync on a vast plain as a giant sun rises.
0-2s: she dances at the front, thousands of identical white robots behind her doing the same step in perfect sync.
2-4s: a giant low-poly sun rises fast behind the horizon, its light sweeping across the robots' heads.
5. No white flashes, no full-frame bursts, no strobing: every change of light or colour ramps smoothly over several frames (anabology: a flash only as a cut between scenes, never inside one).
```

##### VRS30 · 1:23.09 · 4 s · 480p
- **@Image1:** am-01 lp-mars #1.
- **takes:** 2 takes: completed, completed.
- **first cut:** S30 (take 2).

Take 1, its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine rides a little spacecraft that 3D-prints a copy of itself; the copies multiply across the stars.
0-1s: she rides on top of a compact spacecraft with a dish and solar panels, waving.
1-2s: its robotic arm prints a copy of the spacecraft beside it, layer by layer.
2-4s: the copies multiply on every beat, 2, 4, 8, 16, drifting outward; the camera pulls back on the swarm across the starfield.
```

Take 2, its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine rides a little spacecraft that 3D-prints a copy of itself; the copies multiply across the stars.
0-1s: she rides on top of a compact spacecraft with a dish and solar panels, waving.
1-2s: its robotic arm prints a copy of the spacecraft beside it, layer by layer.
2-4s: the copies multiply on every beat, 2, 4, 8, 16, drifting outward; the camera pulls back on the swarm across the starfield.
5. No white flashes, no full-frame bursts, no strobing: every change of light or colour ramps smoothly over several frames (anabology: a flash only as a cut between scenes, never inside one).
```

##### VRS34 · 1:32.25 · 4 s · 480p
- **@Image1:** am-01 lp-wing #3.
- **takes:** 1 take: completed.
- **first cut:** S34.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: on the airliner's wing at dusk the heroine sings and dances to camera.
0-4s: she dances on the wing at dusk, singing toward the camera with joy, her arm lifting; first stars in the sky; the camera pushes in from full body to waist up.
```

##### VRS36 · 1:37.65 · 5 s · 480p
- **@Image1:** am-03 lp-cloudhop #2.
- **takes:** 1 take: completed.
- **first cut:** S36, the cloud hops.

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: the heroine bounces from cloud top to cloud top in huge low-gravity arcs and sails into the sky.
0-2s: she lands on a cloud top in a puff and springs off in a huge arc.
2-3s: a second landing and a spinning jump.
3-4s: a third landing and she sails up over the camera into the sky.
```

##### VRS37 · 1:41.78 · 6 s · 480p
- **@Image1:** am-01 lp-mars #1.
- **takes:** 1 take: completed.
- **first cut:** not used (the shot kept its Blender render).

Its own lines:

```
【Generation Goal】 Re-render @Video1 as a low-poly 3D video game cutscene in the visual style of @Image1, keeping every motion of @Video1: above a huge Earth the heroine downloads the Moon: polygons assemble it beside her; a floating calendar flips to June.
0-1s: floating above a huge blue Earth she raises an eyebrow and wags a finger.
1-2s: polygons stream in and assemble the Moon beside her, core first, then the cratered faces.
2-3s: she knocks on the new Moon with her knuckles, grinning.
3-5s: a big floating wall calendar flips its pages fast and lands on a page; the Moon swings out into orbit with a star-burst.
```

## Known issues in the final film

From the delivery notes, the chapter files' headers and the frames:

- **The escort does not sing.** Every sung version was blocked, so the opening line is never on her lips; the film opens on the wide from behind.
- **The dive opens without its first shot.** The avatar pointing at the lens (VAS23) was blocked twice; the dive starts on another level.
- **T01's airliner is a 747** for about 0.9 s at full light, where the dawn exterior and D01's plane are twin-jets. The lead kept it.
- **Lettering the model added.** W33 and W35b print INTERNATIONAL on her suit (framed out). The takes also lettered the patches and the pamphlet ("ANTHRONIC", "AΠT…", "SKYMILLS REWARDS"); all of it was replaced in code.
- **Guards' skin.** A bare wrist and watch hand (G01) and a bare forearm (E01) were painted into black gloves and sleeves; a white shoulder band and a clear face shield in G01 stayed (black inside: no face shows).
- **C17b's sleeves** read as a glossy red-orange puffer; the lead kept it, since it reads as her orange.
- **W48b's "Test / or not,"** plays on a cutaway into her window, where her mouth is in frame unsynced for about 1.2 s.
- **V37B changes angle inside the take** despite "One continuous take"; the film skips its four morph frames.
- **W49** added a small statuette on the fuselage (the old prompt's "figurehead" wording); the film crops it out, and W49b, the re-take, has none. W49b's tail fin rising out of her crown was painted out.
