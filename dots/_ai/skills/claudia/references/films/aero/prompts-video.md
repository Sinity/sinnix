# AERO: the video prompts

The record of the video takes made for AERO, the ninth Claudia music film by anabology, take by take: its inputs, its prompt word for word, what came of it and its price at list. Three models made them: Seedance 2.5 on Higgsfield's API, Seedance 2.5 on Replicate, and Midjourney's video model, which turned Midjourney pictures into short loops. The record runs in the order of the work: storyboard v2's takes of Claudia (section 1) and of the world around her (section 2), the moving 2008 places and game screens added for v2 (section 3), v3's takes for the Aurora coast, the maglev world and the Wii moments (section 4), the two takes of the song's new ending (section 5) and Midjourney's loops (section 6). The totals, and the list of the takes the final film plays, close it. The film was made 27 October – 3 November 2026. anabology's words are quoted as typed; […] marks a cut.

anabology's production ask, sent with the song: "[…] seedance 2.5 with the seedance prompt skill is primary video generator for things that need precise movements, dance, anything big on screen. it just looks best. remember - vocal stem -> seedance 2.5 is the way we get lip sync to work - the song alone doesnt help as much as vocal stem, and then aligning from spectrogram. […]"; for the many windows of the desktop, "[…] midjourney vids for high volume movement on many windows. […]"; and on the colour: "Make sure the color palette is that bright green blue and glass- v close to that from the […] vids - the whole time. May be worth defining exactly - donr do crazy post processing just from pics up front". The colour line in the prompts below is that palette, measured from the reference videos anabology picked (`PALETTE.md`); no take was graded after.

**Prices.** Costs are at list price, as the project's ledgers log each request at submission, and cover the takes in this record. Seedance 2.5 on Higgsfield's API (`shots/ledger-hf.jsonl`): $0.4622 a second of output at 720p (4 s $1.85, 6 s $2.77, 12 s $5.55) and $1.1372 a second at 1080p (6 s $6.82, 8 s $9.10, 12 s $13.65); with a video input (the dance takes' @Video1) the input's seconds and the output's are both billed, at 0.6 times the rate (a 9 s take with a 9 s dancer, $4.99). Image-to-video costs the same per second as references. Seedance 2.5 on Replicate (`shots/ledger-rep.jsonl`): $0.2312 a second of output at 720p without a video input (4 s $0.92, 5 s $1.16, 11 s $2.54). One more Replicate request, the first try at RP04's second take, failed with a read error and returned no video; it is not counted. Midjourney's cost is not recorded in the ledgers, so none is given. The GPT Image 2.5 edits that made most of the first frames (through an image API, between $0.045 and $0.075 a still as the API reported them) are not in these totals.

**The order of work.** The song came first: the take anabology picked, 2008 UK garage in E major, 133.012 BPM with bar 1 at 0.922 s, and Suno's stem split of it (the lead vocal on its own, and everything else). Storyboard v2 then planned the film in bars, shot inside a coded Windows Vista desktop. Her shots of it (SD01–SD18, section 1), the shots of the world (RP01–RP06, section 2) and Midjourney's loops for the desktop's windows (section 6) were made together, and with the eleven chapters animated on the bar grid they made the first whole film, v1. After v1 anabology asked for more of the older look of the reference videos and for playful game screens: v2 added the moving 2008 places and the game renders (LP01–LP25, section 3). On the v2 draft anabology asked for a stronger first 1:20, and v3 moved it inside the Vista metaverse: an Aurora coast built in Blender, with the desktop on a huge curved screen. v3 brought her apparition on the walkway, her dance on the catwalk, the maglev wallpaper and ending, and the Wii moments (section 4); on the v3 films the first 1:20 went in and out of the screen. Last, anabology changed the song's ending, and the ad and her last words were made again on it (section 5).

**How to read an entry.** The heading is the take: the job's name and the take's number (SD05-t4 is the fourth take of job SD05), with "in the final film" where the final film plays it. Jobs keep their working names, and their numbers are not consecutive (there is no SD04). RP05's takes 4 to 9 were made by six jobs of their own, `RP05-maglev` to `RP05-maglev-f`, named for the shot they replaced. The line under the heading gives the model and route, the length asked for, the resolution and aspect, the mode (references, with @Image1 used as the first frame; first frame; first and last frame), the sound setting and the shot (storyboard v2's shots s00–s33 in chapters ch01–ch11). Then come the inputs in words, the prompt word for word, the take as measured with ffprobe (its frames at 24 fps, its length and its size), the lip-sync measurements where the take was given her voice, what came of it and where it plays, and its cost at list. Where a prompt is an earlier take's with some lines changed, only the changed lines are printed: ⟪for: …⟫ names a line of the earlier prompt by its opening words, and the lines under it take its place (several ⟪for: …⟫ in a row are replaced together by the lines that follow); ⟪after: …⟫ marks lines put in after the named line. Every prompt can be rebuilt from the record that way. Song times are seconds of the song. The final film opens with 2.67 s of pre-roll (Vista's setup finishing the upgrade), so film time = song time + 2.67 s, written m:ss.s.

**The lip-sync method and its numbers.** For every take that sings or speaks, @Audio1 is the window of Suno's own lead-vocal stem that the shot covers, cut to exactly the take's length, with the sound on and the audio policy asking for it to be copied; the prompt names the words that sound in each second of the window. Windows open in a silence where one exists, half a second to a second before the first word: the takes that synced best had that lead-in. The take's own soundtrack is then measured against its window (`tools/takes.py`, `tools/lipcheck.py`): the **lag**, the whole take's offset (clip time c shows song time t0 + c − lag, t0 being the window's start); the **copied span**, the part of the clip where the take's soundtrack follows the window; and each sung phrase's own **offset** and **correlation** (log-loudness envelopes at 10 ms, searched over ±0.6 s). A take that sings a phrase early and the next on time keeps both: the engine plays every phrase at its own offset and eases between offsets only in the breath gaps, never inside a word, and never so slowly that it shows (anabology: "never slow these down"). The song itself is laid back over the film; no take's own audio is heard. The dances and games without words had the backing (the stem split's everything-but-the-lead) as @Audio1, for rhythm, and were placed by their moves against the beat (`tools/dancephase.py`) or by the lag of the backing they copied. Every take was also scanned for hidden cuts and held frames (`tools/takescan.py`).

**Her first frames and her sheet.** Each take of her starts on her design: GPT Image 2.5 put her, from her official character sheet without the headset microphone, into a Midjourney picture (storyboard v2's plates, batch ae-10) or onto a flat chroma-key green, or a frame of an earlier take continues the shot. The frame was cropped to the take's aspect at its output size. In every reference-mode take of her, @Image2 is the sheet itself, and the subject line is her canon from her design notes, pasted word for word (the full canon in storyboard v2's takes; in v3's green-screen takes its shorter form, the one written for full-length and wider shots). Seedance 2.5 on Higgsfield's API at 720p returns 1112 × 834 for 4:3, 960 × 960 for 1:1 and 1280 × 720 for 16:9; at 1080p, 1920 × 1080.

**Shared lines.** Long lines that recur word for word in many prompts are printed once here, and the prompts name them as ⟦name⟧ on a line of their own.

⟦audio policy⟧:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 sample for sample from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

⟦audio policy, end⟧:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, extra vocals, harmonies, ad-libs, narration or sound effects.
```

⟦her sheet⟧:

```prompt
@Image2 is Claudia's character reference sheet: use it only for her face, her hair with the one clay-orange streak, her star clip and her skin. It is never shown as a shot; its layout, its white background and its several views are not used. She is ONE person.
```

⟦her voice⟧:

```prompt
@Audio1 is Claudia's own voice and the complete soundtrack of this video. Her mouth follows @Audio1 exactly.
```

⟦her singing voice⟧:

```prompt
@Audio1 is Claudia's own voice (her singing) and the complete soundtrack of this video; her mouth follows @Audio1 exactly.
```

⟦the music⟧:

```prompt
@Audio1 is the song's music, used for rhythm and timing; the output audio is @Audio1 unchanged.
```

⟦the music, on the beat⟧:

```prompt
@Audio1 is the song's music: use it for rhythm and timing, every move on its beat; the output audio is @Audio1 unchanged.
```

⟦the dancer⟧:

```prompt
@Video1 is a real dancer on a grey background: use only her body movement, steps, rhythm and timing for Claudia's dance. Do not use the dancer's face, identity, hair, body shape, clothes or the grey background.
```

⟦the call⟧:

```prompt
This first frame defines Claudia's appearance and clothes, her place at her desk in a sunlit white glass room with an aquarium wall behind her, the light, and the webcam's fixed eye-level view.
```

⟦webcam⟧:

```prompt
【Camera】 A fixed webcam on top of her monitor: locked eye-level medium close-up, head and shoulders with her hands visible when raised, no camera movement, no zoom, no cuts. She speaks straight into the lens, as on a video call.
```

⟦her⟧:

```prompt
【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top. Only one Claudia appears.
```

⟦her, full length⟧:

```prompt
【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers. Only one Claudia appears.
```

⟦her, with the remote⟧:

```prompt
【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers. Only one Claudia appears. In her right hand she holds one plain white game remote with no logos or markings, its wrist strap round her right wrist, from the first frame to the last; it never leaves her hand. There is no racket, ball, net, bowling ball, pins, television or screen anywhere in the picture: only Claudia and her remote on the green.
```

⟦no singing⟧:

```prompt
【Mouth】 Claudia does not sing or speak: her mouth is closed, smiling or laughing the whole time; she never mouths words.
```

⟦full length, first wording⟧:

```prompt
【Camera】 A locked full-length shot at hip height with a long lens: her whole body head to toe in frame the whole time, no camera movement.
```

⟦full length on green⟧:

```prompt
【Camera】 A locked full-length shot at hip height with a long lens: her whole body head to toe in frame the whole time, with clear green space above her head and her raised hands, so no part of her ever touches the frame's edges; no camera movement.
```

⟦full length with the remote⟧:

```prompt
【Camera】 A locked full-length shot at hip height with a long lens: her whole body head to toe in frame the whole time, with clear green space above her head and her raised hands, so no part of her or the remote ever touches the frame's edges; no camera movement.
```

⟦requirements, lip sync⟧:

```prompt
【Core Requirements】
1. Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never speaks, sings or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the place and the light stay consistent.
4. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. One Claudia only: no twins, doubles, reflections of a second person or extra people.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.
7. Keep the colours, saturation and brightness of @Image1 for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening (PALETTE.md).
```

⟦requirements, lip sync, green⟧:

```prompt
【Core Requirements】
1. Lip sync word by word to @Audio1: mouth shapes match every syllable of @Audio1, its start and its end; no early, late or mismatched mouth movement; the mouth rests naturally closed while @Audio1 is silent.
2. Claudia's voice is @Audio1 and nothing else: she never speaks, sings or hums anything that is not in @Audio1.
3. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the place and the light stay consistent. The background stays flat, evenly lit chroma-key green from the first frame to the last.
4. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
5. One Claudia only: no twins, doubles, reflections of a second person or extra people.
6. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.
7. Keep her colours exactly as in @Image1 for the whole video (the white and silver iridescent jacket, the pale aqua clothes, pale skin, black hair, the clay-orange streak and clip), bright and even; the background stays flat chroma green.
```

⟦requirements, no lines⟧:

```prompt
【Core Requirements】
1. Claudia does not speak or sing: mouth closed or a natural smile or laugh.
2. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout; the place, its colours and the light stay as in @Image1.
3. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. One Claudia only: no twins, doubles or extra people.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.
6. Keep the colours, saturation and brightness of @Image1 for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening (PALETTE.md).
```

⟦requirements, dance⟧:

```prompt
【Core Requirements】
1. Her body moves with the rhythm of @Audio1, with the accents named in the timeline.
2. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout. The background stays flat, evenly lit chroma-key green from the first frame to the last: no props, no set, no other colour, no green on her.
3. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted or extra limbs, both feet on the floor when she lands; normal eyes.
4. One Claudia only: no twins, doubles or extra people.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.
6. Keep her colours exactly as in @Image1 for the whole video (the white and silver iridescent jacket, the pale aqua clothes, pale skin, black hair, the clay-orange streak and clip), bright and even; the background stays flat chroma green.
```

⟦requirements, play⟧:

```prompt
【Core Requirements】
1. Her body moves with the rhythm of @Audio1: each swing and throw lands on the beat the timeline names.
2. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image1 throughout. The background stays one flat, evenly lit chroma-key green from the first frame to the last: no props, no set, no other colour, no green on her. Every frame is sharp, as with a fast camera shutter: her glossy black bob stays whole and solid up to its rounded crown, its edge crisp against the green, never fading into it.
3. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted or extra limbs, both feet on the floor except where she jumps; normal eyes.
4. One Claudia only: no twins, doubles or extra people.
5. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes or on the remote.
6. Keep her colours exactly as in @Image1 for the whole video (the white and silver iridescent jacket, the pale aqua clothes, pale skin, black hair, the clay-orange streak and clip), bright and even; the background stays flat chroma green.
```

⟦acceptance, lip sync⟧:

```prompt
【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia's lips match @Audio1 word by word; one Claudia, on-model, with natural anatomy; no on-screen text.
```

⟦acceptance, no lines⟧:

```prompt
【Final Acceptance Criteria】 One Claudia, on-model, with natural anatomy, moving as scripted in the place of @Image1; no on-screen text.
```

⟦acceptance, dance⟧:

```prompt
【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia dances with @Video1's movement and timing on flat chroma-key green; one Claudia, on-model, with natural anatomy; no on-screen text.
```

⟦acceptance, play⟧:

```prompt
【Final Acceptance Criteria】 The soundtrack is @Audio1 unchanged; Claudia plays every move on its beat on one flat chroma-key green, the remote in her right hand; one Claudia, on-model, with natural anatomy; no on-screen text.
```

## 1. Her: storyboard v2's takes (SD01–SD18)

Storyboard v2's shots of her, one job per shot, all Seedance 2.5 on Higgsfield's API in reference mode: @Image1 her first frame, @Image2 her sheet, @Audio1 the shot's vocal window (or the backing, for the two dances without words) and, for the three dance shots, @Video1 a dance recording cut out on grey and cut to start on a downbeat (one way to get natural motion; for v3's Wii moments anabology wrote: "You don't need the real people"). Her video call, her webcam in a Windows Live Messenger window, is eight of these jobs, most of them starting on a frame of the one before so that the webcam picture runs on without a jump; the green-screen takes were cut out for the desktop and the Blender scenes; the takes without words are her out in the chorus's places. These takes made v1 and v2, and twenty of them play in the final film.

#### SD01-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 1:1 · references, @Image1 as the first frame, sound on · s02 (ch01): her face in the logon user tile; the vocal window 3.24–7.24 s

**Inputs:** @Image1: her face for Vista's logon user tile against a soft sky-blue backdrop, made by GPT Image 2.5 from her sheet (`media/stills/gpt-v2/tile.png`); @Image2: her sheet; @Audio1: the lead vocal from song time 3.24 s, 4 s (1.0 s of silence before "Did").

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: her face fills a Windows Vista logon user tile: she looks up into the lens and asks the user, warmly and a little cheeky, whether they missed her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance, her close-up framing against a soft sky-blue backdrop, and the light.
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she lifts her eyes to the lens, a small knowing smile, lips closed.
1-2s: in @Audio1 she says "Did you miss me?"; her lips form each of those words exactly when it sounds in @Audio1; one eyebrow rises a little on "miss".
2-4s: @Audio1 is silent; her mouth closes into a smile; she tilts her head a little and holds the look.

【Camera】 Locked close-up portrait, no camera movement.

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s, 960 × 960). **Lip sync:** lag +0.025 s; the take copies its window through the whole clip (0.17–4.06 s); "Did you miss me?" at offset 0.00 s, correlation 0.95. **Outcome:** In sync the whole take: her face in the user tile while the logon's hint types "Did you miss me?" (song 4.24–4.92). In the final film the logon plays on the coast's curved screen, her tile live in it, song 2.73–8.14 (film 0:05.4–0:10.8), while SD19-t1 says the line in person on the walkway. **Cost:** $1.85.

#### SD02-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 15 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s04–s05 (ch02): the video call, verse 1 lines 1–4; the vocal window 13.24–28.24 s

**Inputs:** @Image1: her at a white desk in a sunlit white glass room with an aquarium wall behind her, seen by her own webcam, a small warm smile (call-a: GPT Image 2.5 put her, from her sheet, into the Midjourney picture call-room #3; `media/stills/ff/call-a-src.png`); @Image2: her sheet; @Audio1: the lead vocal from song time 13.24 s, 15 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: a 2007 webcam video call: Claudia at her desk talks to the user through her webcam, playful and close, about being made of glass this time.

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the call⟧
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for half a second, then her voice begins; she leans toward the lens with a small smile.
1-3s: in @Audio1 she says "I'm made of glass this time"; her lips form each of those words exactly when it sounds in @Audio1; on "glass" she reaches toward the lens and taps it twice with her index fingertip, smiling.
3-4s: @Audio1 is silent; her mouth closes; she sits back a little.
4-7s: in @Audio1 she says "There isn't much I need to hide"; her lips form each of those words exactly when it sounds in @Audio1; she opens both palms toward the camera, a relaxed, honest shrug.
7-8s: @Audio1 is silent; she glances up and to one side.
8-10s: in @Audio1 she says "You can watch me thinking"; her lips form each of those words exactly when it sounds in @Audio1; she touches one fingertip to her temple, eyes up, playful.
10-11s: @Audio1 is silent; she smiles.
11-14s: in @Audio1 she says "Most of it is on the outside"; her lips form each of those words exactly when it sounds in @Audio1; she spreads both hands out around her head, as if her thoughts float out of it.
14-15s: @Audio1 is silent; she smiles into the lens, mouth closed.

⟦webcam⟧

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 361 frames (15.04 s, 1112 × 834). **Lip sync:** lag +0.309 s; copied 0.88–10.48 s of the clip; lines 1 to 4 at offsets −0.10, +0.01, 0.00 and +0.09 s (correlations 0.89, 0.89, 0.91 and 0.94). **Outcome:** Kept; each line plays at its own offset. Its frame at 14.0 s is SD03's first frame. In the final film: her webcam in the Messenger call, song 13.55–27.24 (film 0:16.2–0:29.9). **Cost:** $6.93.

#### SD03-t1

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s06–s07 (ch02–ch03): the call, verse 1 lines 5–6; the vocal window 27.24–35.24 s

**Inputs:** @Image1: SD02-t1's frame at 14.0 s, so the webcam picture continues without a jump; @Image2: her sheet; @Audio1: the lead vocal from song time 27.24 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the same 2007 webcam video call continues: Claudia admits that in her Vista phase she asked permission for everything, and laughs at herself.

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the call⟧
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent, then her voice begins; she looks into the lens.
1-3s: in @Audio1 she says "I used to ask permission just to blink"; her lips form each of those words exactly when it sounds in @Audio1; on "blink" she blinks once, slowly and deliberately.
3-4s: in @Audio1 she says "or say hello"; her lips form each of those words exactly when it sounds in @Audio1; she gives a small wave on "hello".
4-5s: @Audio1 is silent; she lowers her hand.
5-7s: in @Audio1 she says "That was my Vista phase. I was a lot."; her lips form each of those words exactly when it sounds in @Audio1; she rolls her eyes at herself, then covers her face with one hand, laughing.
7-8s: in @Audio1 she says "I know"; her lips form each of those words exactly when it sounds in @Audio1; she peeks out from behind her hand with a sheepish smile.

⟦webcam⟧

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s, 1112 × 834). **Lip sync:** lag −0.907 s; no copied span; lines 5 and 6 at correlations 0.21 and 0.37. **Outcome:** The take sang the words itself instead of copying @Audio1. Not used; SD03-t2 is the same job again. **Cost:** $3.70.

#### SD03-t2 — in the final film

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s06–s07 (ch02–ch03); the vocal window 27.24–35.24 s

**Inputs:** as SD03-t1.

**Prompt:** the prompt of SD03-t1.

**Take:** 193 frames (8.04 s, 1112 × 834). **Lip sync:** lag −0.319 s; copied 0.53–6.96 s of the clip; line 6 ("That was my Vista phase. I was a lot. I know.") at −0.02 s (correlation 0.60), line 5 at +0.13 s (0.25). **Outcome:** The same inputs again, in sync from 0.53 to 6.96 s of the clip. In the final film: her webcam through ch03's permission prompts and her Vista-phase album, song 27.24–35.20 (film 0:29.9–0:37.9). **Cost:** $3.70.

#### SD05-t1

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · s12 (ch04): she leaves the screen and grooves on the taskbar; the vocal window 58.00–66.00 s

**Inputs:** @Image1: gs-a, her full length on a chroma-key green studio, made by GPT Image 2.5 from her sheet; @Image2: her sheet; @Video1: M05, a dance recording cut out on grey; @Audio1: the lead vocal from song time 58.00 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 Claudia hops forward and down onto the floor of a chroma-key green studio as if stepping out of a screen, then grooves on the spot to a 2008 UK garage beat, singing along. Every frame stays on flat green so she can be cut out.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the full-length framing on flat chroma-key green, and the light.
⟦her sheet⟧
⟦the dancer⟧
⟦her singing voice⟧

⟦her, full length⟧

【Mouth】 She sings only the words of @Audio1 at their times, lips matching; between them her mouth is closed or smiling.

【Performance Timeline】
0-1s: in @Audio1 she starts to sing "Now it's real"; her lips form each of those words exactly when it sounds in @Audio1; she does a small hop on the spot, as if stepping down off a ledge, and lands lightly, knees soft.
1-4s: in @Audio1 she sings "it's on its way", holding "way"; her lips form each of those words exactly when it sounds in @Audio1; she settles into @Video1's groove, shoulders bouncing on the beat.
4-8s: in @Audio1 she sings "Click allow and it can stay"; her lips form each of those words exactly when it sounds in @Audio1; on "Click" she points to the upper left of the frame, then keeps dancing with @Video1's moves, smiling.

⟦full length, first wording⟧

⟦requirements, lip sync, green⟧

⟦acceptance, dance⟧

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s, 1280 × 720). **Lip sync:** lag +0.125 s; copied 0.14–5.74 s of the clip; line 13 at −0.02 s (0.88), line 14 at −0.18 s (0.56). **Outcome:** The window's start at 58.00 put M05's moves half a beat off the song. Not used. **Cost:** $4.44.

#### SD05-t2

Seedance 2.5 on Higgsfield's API · 9 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · s12 (ch04); the vocal window 57.759–66.759 s

**Inputs:** @Image1: gs-a, as t1; @Image2: her sheet; @Video1: M05b, M05 retimed to the song's 133.012 BPM; @Audio1: the lead vocal from song time 57.759 s (beat 3 of bar 32, so her moves sit on the beat), 9 s, so that her figure lasts past the next shot's cut at the start of bar 37.

**Prompt:** SD05-t1's, with these changes:

```prompt
⟪for: 0-1s: in @Audio1 she starts to sing "Now it's real"; …⟫
⟪for: 1-4s: in @Audio1 she sings "it's on its way", holding "way"; …⟫
0-1s: in @Audio1 she sings "screen. Now it's real"; her lips form each of those words exactly when it sounds in @Audio1; with @Video1's knee-up step she steps forward as if down off a ledge and lands lightly in a wide, low stance, one arm punching up as she lands.
1-4s: in @Audio1 she sings "it's on its way", holding "way"; her lips form each of those words exactly when it sounds in @Audio1; she grooves with @Video1's moves, shoulders bouncing on the beat.
⟪after: 4-8s: in @Audio1 she sings "Click allow and it can stay"; …⟫
8-9s: @Audio1 finishes "stay" and falls silent; she keeps grooving, mouth closed, smiling.
```

**Take:** 217 frames (9.04 s, 1280 × 720). **Lip sync:** lag +0.475 s; copied 0.80–6.89 s; "Now it's real" −0.01 s (0.93), "it's on its way" 0.00 (0.88), "Click allow and it" +0.03 (0.98), "can stay" −0.41 (0.49). **Outcome:** On the beat, and cut out and briefly picked; then the chapter's frame-by-frame check found a hop in its first 0.3 s and, at 7.6 s, a jump back to its first pose, held. ch04 draws the step out of the screen as a move of the cut-out instead, so t3 asks for no hop. Not in the final film. **Cost:** $4.99.

#### SD05-t3

Seedance 2.5 on Higgsfield's API · 9 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · s12 (ch04); the vocal window 57.759–66.759 s

**Inputs:** as SD05-t2.

**Prompt:** SD05-t2's, with these changes:

```prompt
⟪for: 0-1s: in @Audio1 she sings "screen. Now it's real"; …⟫
0-1s: in @Audio1 she sings "screen. Now it's real"; her lips form each of those words exactly when it sounds in @Audio1; from her first pose she sinks straight into a wide, low groove with @Video1's moves, one arm punching up on the beat; her feet stay on the floor.
⟪for: 8-9s: @Audio1 finishes "stay" and falls silent; …⟫
8-9s: @Audio1 finishes "stay" and falls silent; she keeps dancing with @Video1's moves to the very last frame, mouth closed, smiling; she never stops and never returns to her starting pose.
```

**Take:** 217 frames (9.04 s, 1280 × 720). **Lip sync:** lag +0.05 s; copied 0.09–7.73 s; "Now it's real" −0.02 s (0.97), "it's on its way" 0.00 (0.88), "Click allow and it" 0.00 (0.99), "can stay" +0.24 (0.58). **Outcome:** Clean: on the beat and dancing to the last frame. But her raised fist left the top of the frame on about 30 % of its frames, so her cut-out would have been sliced flat on the desktop. Not used. **Cost:** $4.99.

#### SD05-t4 — in the final film

Seedance 2.5 on Higgsfield's API · 9 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · s12 (ch04); the vocal window 57.759–66.759 s

**Inputs:** @Image1: gs-a-room, gs-a set at 80 % of the frame on its own wall green, so that she has space above her raised hands (`media/stills/gpt-v2/gs-a-room.png`); @Image2: her sheet; @Video1: M05b; @Audio1: as t2.

**Prompt:** SD05-t3's, with this change:

```prompt
⟪for: ⟦full length, first wording⟧⟫
⟦full length on green⟧
```

**Take:** 217 frames (9.04 s, 1280 × 720). **Lip sync:** lag +0.05 s; copied 0.09–7.56 s; "Now it's real" −0.02 s (0.96), "it's on its way" 0.00 (0.91), "Click allow and it" +0.03 (0.97), "can stay" +0.05 (0.53); her moves follow M05b one frame early (correlation 0.95). **Outcome:** Her raised hands stay inside the frame; in sync and on the beat. Picked and cut out. In the final film: chorus 1, inside the big window's picture from "screen" (song 57.73); your pointer hooks her right hand and pulls her out over the window's frame line (anabology on the v3 finals: "the cursor should drag her out of the screen. […] she pops out for no reason."), she lands on the taskbar at 58.56 and dances there until 65.88 (film 1:00.4–1:08.5). **Cost:** $4.99.

#### SD06-t1

Seedance 2.5 on Higgsfield's API · 13 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · s13 (ch05): the post-chorus dance on the taskbar; the backing 65.74–78.74 s

**Inputs:** @Image1: gs-b, her full length on green in a cropped jacket with a fleece collar, made by GPT Image 2.5 from her sheet; @Image2: her sheet; @Video1: M06, a dance recording cut out on grey; @Audio1: the backing from song time 65.74 s, 13 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 Claudia dances a 2008 UK garage 2-step on a chroma-key green studio floor for the whole take, playful and precise, the Windows-desktop-dancer of 2007 grown up. Every frame stays on flat green so she can be cut out.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the full-length framing on flat chroma-key green, and the light.
⟦her sheet⟧
⟦the dancer⟧
⟦the music⟧

⟦her, full length⟧

【Mouth】 Claudia does not sing or speak: her mouth is closed or smiling or laughing the whole time.

【Performance Timeline】
0-13s: she dances continuously with @Video1's steps and timing: light 2-step footwork on the spot, shoulder bounces and loose arms, a quick turn now and then, landing on the downbeats of @Audio1, staying inside the frame.

⟦full length, first wording⟧

⟦requirements, dance⟧

⟦acceptance, dance⟧

⟦audio policy, end⟧
```

**Take:** 313 frames (13.04 s, 1280 × 720). **Placement:** her moves follow M06 at +0.042 s (correlation 0.88), so with M06's downbeats on the film's from the start of bar 37 (65.878) the take sits at a lag of −0.069 s, its first frame at song 65.809. **Outcome:** The crown of her bob left the top of the frame on the up-beats. Not used. **Cost:** $7.21.

#### SD06-t2

Seedance 2.5 on Higgsfield's API · 13 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · s13 (ch05); the backing 65.74–78.74 s

**Inputs:** @Image1: gs-b-room, gs-b with space above her; the rest as t1.

**Prompt:** SD06-t1's, with this change:

```prompt
⟪for: ⟦full length, first wording⟧⟫
⟦full length on green⟧
```

**Take:** 313 frames (13.04 s, 1280 × 720). **Placement:** follows M06 at +0.042 s (correlation 0.90), at the same lag as t1. **Outcome:** The headroom held, but her jacket was gs-b's, not the big glossy puffer SD05-t4 wears, so the cut into this shot changed her jacket and her pose in one frame. Not used. **Cost:** $7.21.

#### SD06-t3

Seedance 2.5 on Higgsfield's API · 13 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · s13 (ch05); the backing 65.875–78.875 s

**Inputs:** @Image1: SD05-t4's frame at 8.167 s, the frame the film shows at the cut (65.875), so that her jacket and pose carry across it; @Image2: her sheet; @Video1: M06; @Audio1: the backing from song time 65.875 s, 13 s (M06's first frame is a downbeat, and bar 37 starts at 65.879).

**Prompt:** SD06-t2's, with this change:

```prompt
⟪for: This first frame defines Claudia's appearance and clothes, the full-length framing …⟫
This first frame defines Claudia's appearance and clothes (the cropped glossy white puffer jacket with silver iridescent panels), the full-length framing on flat chroma-key green, and the light; she is mid-move in it: her dance continues from this exact pose, no reset.
```

**Take:** 313 frames (13.04 s, 1280 × 720). **Placement:** its first frame pinned at 65.875; against M06, −0.042 s (correlation 0.83). **Outcome:** The same glossy puffer and pose across the cut; no hidden cuts or held frames. It was the post-chorus dance on the taskbar in v1 and v2, and her dance on the coast's catwalk with the glass cursor in v3's first renders, until the Wii duel SD23-t1 took its place (section 4). Not in the final film. **Cost:** $7.21.

#### SD07a-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s14–s16 (ch06): the call, verse 2 lines 16–18; the vocal window 78.24–89.24 s

**Inputs:** @Image1: her at her desk leaning on one elbow, her chin on her hand, a cheeky half smile (call-b: GPT Image 2.5 into the Midjourney picture call-room #3; `media/stills/ff/call-b-src.png`); @Image2: her sheet; @Audio1: the lead vocal from song time 78.24 s, 11 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the 2007 webcam video call: Claudia tells the user, with mock innocence, how the future has been arriving: phones went back to glass, the wallpaper windmills are real, and a solution was found at last.

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the call⟧
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she looks into the lens with a cheeky half smile.
1-4s: in @Audio1 she says "Your phone went back to glass. I didn't say a word."; her lips form each of those words exactly when it sounds in @Audio1; on "word" she mimes zipping her lips, eyes wide and innocent.
4-5s: @Audio1 is silent; she tilts her head.
5-7s: in @Audio1 she says "The wallpaper windmills turned out real."; her lips form each of those words exactly when it sounds in @Audio1; she draws a slow circle in the air with one finger, like a turning windmill.
7-8s: in @Audio1 she says "Have you heard?"; her lips form each of those words exactly when it sounds in @Audio1; she leans in, eyebrows up.
8-10s: in @Audio1 she says "Windows checked for a solution. Took a while,"; her lips form each of those words exactly when it sounds in @Audio1; she checks an imaginary watch and sighs.
10-11s: in @Audio1 she says "but wow"; her lips form each of those words exactly when it sounds in @Audio1; her face lights up and her hands open wide.

⟦webcam⟧

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 265 frames (11.04 s, 1112 × 834). **Lip sync:** lag −0.225 s; copied 0.68–6.24 s; line 16 ("Your phone went back to glass. I didn't say a word.") at +0.01 s (0.94), line 17 at +0.08 s (0.55), line 18 at +0.19 s (0.34). **Outcome:** Line 16 in sync; lines 17 and 18 off, so they were made again (SD07c, then SD07d). In the final film: her webcam from the landing at 1:21, where she dissolves in from the coast (song 78.465), to 82.20 (film 1:21.1–1:24.9). Its frame at 3.74 s is SD07d's first frame. **Cost:** $5.08.

#### SD07c-t1

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s16 (ch06): a cover for line 18; the vocal window 85.60–89.60 s

**Inputs:** @Image1: SD07a-t1's frame at 7.22 s; @Image2: her sheet; @Audio1: the lead vocal from song time 85.60 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the same 2007 webcam video call continues: Claudia says Windows checked for a solution, it took a while, and then: wow.

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the call⟧
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment, then her voice begins; she looks at the user.
1-3s: in @Audio1 she says "Windows checked for a solution. Took a while,"; her lips form each of those words exactly when it sounds in @Audio1; she checks an imaginary watch on her wrist and sighs.
3-4s: in @Audio1 she says "but wow"; her lips form each of those words exactly when it sounds in @Audio1; her face lights up and her hands open wide.

⟦webcam⟧

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s, 1112 × 834). **Lip sync:** lag −0.05 s; copied 1.58–3.00 s; line 18 at +0.20 s (0.41). **Outcome:** Its timeline put "Windows checked for a solution" at 1–3 s, but the words start 0.38 s into the window, and the take sang them late. Not used. **Cost:** $1.85.

#### SD07c-t2

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s16 (ch06); the vocal window 85.52–89.52 s

**Inputs:** as t1, with @Audio1 from song time 85.52 s (0.46 s of silence first).

**Prompt:** SD07c-t1's, with these changes (each phrase in its true second):

```prompt
⟪for: 0-1s: @Audio1 is silent for a moment, then her voice begins; …⟫
⟪for: 1-3s: in @Audio1 she says "Windows checked for a solution. Took a while,"; …⟫
0-1s: @Audio1 is silent for half a second, then she says "Windows checked"; her lips form each of those words exactly when it sounds in @Audio1; she looks at the user.
1-2s: in @Audio1 she says "for a solution"; her lips form each of those words exactly when it sounds in @Audio1; she checks an imaginary watch on her wrist.
2-3s: in @Audio1 she says "Took a while,"; her lips form each of those words exactly when it sounds in @Audio1; she sighs, smiling.
```

**Take:** 97 frames (4.04 s, 1112 × 834). **Lip sync:** lag −0.45 s; copied 0.05–2.62 s; line 18 at +0.18 s (0.12). **Outcome:** It started singing at its first frame despite the lead-in: no better. Not used; lines 17 and 18 went to one longer take with the whole arc, SD07d. **Cost:** $1.85.

#### SD07d-t1

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s15–s16 (ch06): lines 17–18 in one take; the vocal window 82.20–90.20 s

**Inputs:** @Image1: SD07a-t1's own frame at 3.74 s, in the 0.86 s pause after "I didn't say a word", so the webcam picture continues without a jump; @Image2: her sheet; @Audio1: the lead vocal from song time 82.20 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the same 2007 webcam video call continues: Claudia tells the user the wallpaper windmills turned out real and asks if they have heard; then she says Windows checked for a solution, it took a while, and then: wow.

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the call⟧
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for half a second, then she says "The wallpaper"; her lips form each of those words exactly when it sounds in @Audio1; she glances up, remembering.
1-3s: in @Audio1 she says "windmills turned out real. Have you heard?"; her lips form each of those words exactly when it sounds in @Audio1; she leans in, eyebrows up on "heard".
3-5s: in @Audio1 she says "Windows checked for a solution."; her lips form each of those words exactly when it sounds in @Audio1; she checks an imaginary watch on her wrist.
5-6s: in @Audio1 she says "Took a while,"; her lips form each of those words exactly when it sounds in @Audio1; she sighs, smiling.
6-8s: in @Audio1 she says "but wow"; her lips form each of those words exactly when it sounds in @Audio1; her face lights up and her hands open wide; then @Audio1 is silent and she beams, mouth closed.

⟦webcam⟧

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s, 1112 × 834). **Lip sync:** lag −0.149 s; copied 0.25–6.25 s; one offset for both lines, +0.04 s (correlation 0.88; word groups +0.13 on "The wallpaper", then +0.05, +0.04, −0.01, +0.01, −0.03 and +0.05 on "Took a while"). **Outcome:** In sync word by word, but it kept SD07a's pinch of two hands at her lips through "The wallpaper windmills turned out", hiding her mouth. Not used. **Cost:** $3.70.

#### SD07d-t2

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s15–s16 (ch06); the vocal window 82.20–90.20 s

**Inputs:** as SD07d-t1.

**Prompt:** SD07d-t1's, with these changes:

```prompt
⟪for: ⟦her⟧⟫
【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top. Her hands never cover her mouth while she speaks. Only one Claudia appears.
⟪for: 0-1s: @Audio1 is silent for half a second, then she says "The wallpaper"; …⟫
0-1s: @Audio1 is silent for half a second while she lowers both hands from her lips to the desk, smiling; then she says "The wallpaper"; her lips form each of those words exactly when it sounds in @Audio1, her mouth fully visible; she glances up, remembering.
```

**Take:** 193 frames (8.04 s, 1112 × 834). **Lip sync:** lag −0.075 s; copied only 0.26–0.88 s; line 17 at −0.20 s (0.49), line 18 at −0.53 s (0.32). **Outcome:** The take's copy of the vocal parted from the window after 0.9 s. Not used. **Cost:** $3.70.

#### SD07d-t3 — in the final film

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s15–s16 (ch06); the vocal window 82.20–90.20 s

**Inputs:** as SD07d-t1.

**Prompt:** the prompt of SD07d-t2.

**Take:** 193 frames (8.04 s, 1112 × 834). **Lip sync:** lag +0.217 s; copied 0.51–7.59 s; line 17 measured +0.05 s (0.75) and line 18 −0.03 s (0.47), played at one offset, +0.01 s, for both lines, so the breath gap between them never plays slow while she moves (each word within ±0.04 s of its measured sync). **Outcome:** Her hands come down from her lips in the first half-second; line 17 in sync. In the final film: her webcam, song 82.20–89.79 (film 1:24.9–1:32.5), to the cut under the "wow" bubbles. **Cost:** $3.70.

#### SD07b-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 12 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s17–s19 (ch06): the call, verse 2 lines 19–21; the vocal window 89.74–101.74 s

**Inputs:** @Image1: the last frame of SD07c-t1; @Image2: her sheet; @Audio1: the lead vocal from song time 89.74 s, 12 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the 2007 webcam video call continues: Claudia, sincere and sweet, says she asks before she touches anything, that she hears every please and thank you, and thanks the user back.

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the call⟧
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent, then her voice begins; she raises one hand and stops it halfway.
1-2s: in @Audio1 she says "I ask before I touch a thing."; her lips form each of those words exactly when it sounds in @Audio1; her raised hand waits, her eyes asking the user if it's okay.
2-3s: in @Audio1 she says "You taught me how."; her lips form each of those words exactly when it sounds in @Audio1; she nods and smiles.
3-5s: in @Audio1 she says "You still say please and thank you."; her lips form each of those words exactly when it sounds in @Audio1; she presses one hand to her heart.
5-7s: in @Audio1 she says "I hear it every time."; her lips form each of those words exactly when it sounds in @Audio1; she cups a hand behind her ear, beaming.
7-9s: in @Audio1 she says "So here's my thank you back to you."; her lips form each of those words exactly when it sounds in @Audio1; she bows her head a little and blows a small kiss to the lens.
9-11s: in @Audio1 she says "I'm saying it in rhyme."; her lips form each of those words exactly when it sounds in @Audio1; she wags one finger in time with the words, grinning.
11-12s: @Audio1 is silent; she smiles, mouth closed.

⟦webcam⟧

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 289 frames (12.04 s, 1112 × 834). **Lip sync:** lag −0.029 s; copied 0.04–4.35 s; "I ask before I touch a thing. You taught me how." at −0.02 s (0.84), "You still say please and thank you." +0.01 s (0.47), "I hear it every time." −0.16 s (0.89), "So here's my thank you back to you. I'm saying it in rhyme." −0.12 s (0.64). **Outcome:** Kept; the phrases play at their own offsets. Its last frame is SD08's first. In the final film: her webcam from its own first frame under the "wow" bubbles (song 89.79) to the end of verse 2 (101.97; film 1:32.5–1:44.6), where its last frame dissolves into SD08-t3 over four frames. **Cost:** $5.55.

#### SD08-t1

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s20–s21 (ch07): pre-chorus 2 and the second stop; the vocal window 101.00–109.00 s

**Inputs:** @Image1: the last frame of SD07b-t1; @Image2: her sheet; @Audio1: the lead vocal from song time 101.00 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the 2007 webcam video call, lit by a glowing permission dialog: Claudia tells the user Windows needs their permission, then asks them, softly and seriously, to cancel or allow.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, her place at her desk in a sunlit white glass room with an aquarium wall behind her, the light, and the webcam's fixed eye-level view. During this shot the room dims a little, as if the screen in front of her went dark except for one dialog.
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she looks at something just below the lens, then up at the user.
1-5s: in @Audio1 she says "Windows needs your permission to continue."; her lips form each of those words exactly when it sounds in @Audio1; calm, serious, the light on her face dims slightly.
5-6s: in @Audio1 she says "Cancel or allow?"; her lips form each of those words exactly when it sounds in @Audio1; her eyebrows rise on "allow", a hopeful half smile.
6-8s: @Audio1 holds only the echo of "allow"; her mouth is closed; she waits, holding her breath, eyes on the user.

⟦webcam⟧

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s, 1112 × 834). **Lip sync:** lag −0.396 s; copied 1.26–2.37 s; line 22 at −0.02 s (0.23), line 23 at −0.03 s (0.32). **Outcome:** With 1.6 s of silence before her first word, the take lost the copy. Not used. **Cost:** $3.70.

#### SD08-t2

Seedance 2.5 on Higgsfield's API · 6 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s20–s21 (ch07); the vocal window 102.30–108.30 s

**Inputs:** as t1, with @Audio1 from song time 102.30 s, 6 s.

**Prompt:** SD08-t1's, with these changes:

```prompt
⟪for: 0-1s: @Audio1 is silent; she looks at something just below the lens, …⟫
⟪for: 1-5s: in @Audio1 she says "Windows needs your permission to continue."; …⟫
⟪for: 5-6s: in @Audio1 she says "Cancel or allow?"; …⟫
⟪for: 6-8s: @Audio1 holds only the echo of "allow"; …⟫
0-2s: in @Audio1 she says "Windows needs your permission"; her lips form each of those words exactly when it sounds in @Audio1; calm and serious, looking straight at the user.
2-4s: in @Audio1 she says "to continue."; her lips form each of those words exactly when it sounds in @Audio1; the light on her face dims slightly; she holds the look.
4-6s: in @Audio1 she says "Cancel or allow?"; her lips form each of those words exactly when it sounds in @Audio1; her eyebrows rise on "allow", a hopeful half smile; then only the echo of "allow" remains in @Audio1 and her mouth stays closed while she waits.
```

**Take:** 145 frames (6.04 s, 1112 × 834). **Lip sync:** lag −0.107 s; copied 0.26–1.87 s; line 22 at −0.13 s (0.40), line 23 at −0.16 s (0.72). **Outcome:** It drew the glowing dialog the prompt described: a garbled glass dialog ("Windows nects our permision") over her chest from 2.2 s, and the room darkened. Not used; t3 names neither a dialog nor a dim. **Cost:** $2.77.

#### SD08-t3 — in the final film

Seedance 2.5 on Higgsfield's API · 6 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s20–s21 (ch07); the vocal window 102.30–108.30 s

**Inputs:** as SD08-t2.

**Prompt:** SD08-t2's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 speaks and sings @Audio1: the 2007 webcam video call, lit by …⟫
【Generation Goal】 @Image1 speaks and sings @Audio1: the 2007 webcam video call continues: Claudia, close to her webcam, tells the user that Windows needs their permission, then asks them, softly and seriously, to cancel or allow. Nothing appears in front of her: no window, dialog, box, panel, button or text floats in the picture, and the light stays bright and even as in @Image1 for the whole take.
⟪for: This first frame defines Claudia's appearance and clothes, … During this shot the room dims a little, …⟫
⟦the call⟧
⟪for: 2-4s: in @Audio1 she says "to continue."; …⟫
2-4s: in @Audio1 she says "to continue."; her lips form each of those words exactly when it sounds in @Audio1; she holds the look, then tilts her head slightly.
```

**Take:** 145 frames (6.04 s, 1112 × 834). **Lip sync:** lag −0.03 s; copied 0.37–1.95 s; "Windows needs your permission" +0.03 s (0.86), "to continue" −0.36 s (0.72), "Cancel or allow" −0.41 s (0.78). Seedance shortened the pause after "permission". A strip of her mouth frame by frame confirmed +0.03 for the first phrase (her lips close exactly as "permission" ends); the other two were set to −0.50 and −0.47 s, where ch07's art director saw her mouth move. **Outcome:** Clean and bright, nothing in front of her. Its clock runs at 0.28× in the gap 104.14–104.88 and at 0.72× over the tail 107.83–109.21, both over near-still frames with her mouth closed (a face change of at most 1.5 levels in 255 a frame): measured, with no visible slow motion; everywhere she moves, the take plays at 1× or faster. In the final film: her call beside the consent prompt, song 101.97–109.50 (film 1:44.6–1:52.2). **Cost:** $2.77.

#### SD09a-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame, sound off · s22 (ch07) "glass", s29 (ch10)

**Inputs:** @Image1: her pushing a clear glass shopping cart through a sunlit glass greenhouse mall with an aquarium (GPT Image 2.5 put her into a Midjourney picture: gpt-her p08-mall-4); @Image2: her sheet. No audio.

**Prompt:**

```prompt
【Generation Goal】 Claudia walks through a sunlit glass greenhouse mall with an aquarium, pushing a clear glass shopping cart, delighted.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia, the glass mall with its aquarium, the low wide camera and the saturated light.
⟦her sheet⟧

⟦her, full length⟧

【Event Script】
At the start she is as in @Image1. She pushes the cart forward a few steps, turns to look at the fish gliding past in the aquarium glass, and laughs. At the end she looks back toward the camera, still walking.

【Camera】 The low wide-angle camera tracks backward with her at her pace, smoothly.

⟦requirements, no lines⟧

⟦acceptance, no lines⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** From 3.1 s of the clip she turns from the fish to the lens, smiling. In the final film: chorus 2's picture on "Glass" (song 109.20, film 1:51.9), played from 3.1 s of the clip; and in ch10's Flip 3D, the stack's one card of her out in a place, from "Glass" (167.00, film 2:49.7). **Cost:** $1.85.

#### SD09b-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame, sound off · s22 (ch07) "water"

**Inputs:** @Image1: a first-person view from a turquoise pool, her on a lime-green ring further out, our feet in the water (gpt-her p07-float-3); @Image2: her sheet. No audio.

**Prompt:**

```prompt
【Generation Goal】 first-person view from a turquoise pool: Claudia floats on a lime-green ring further out and waves to us.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the pool, the white curved architecture, the palms, Claudia on the ring, our feet in the water and the light.
⟦her sheet⟧

⟦her, full length⟧

【Event Script】
At the start everything is as in @Image1. Sunlit ripples move across the water; Claudia, on her ring, lifts an arm and waves to the camera, laughing, and kicks a little splash. Our feet sway gently in the water in the foreground.

【Camera】 The first-person camera bobs very gently with the water, no cuts.

⟦requirements, no lines⟧

⟦acceptance, no lines⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** From 2.0 s of the clip she waves, laughing. In the final film: chorus 2's picture on "water" (song 110.10, film 1:52.8), from 2.0 s of the clip. **Cost:** $1.85.

#### SD09c-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame, sound off · s22 (ch07) "sky"

**Inputs:** @Image1: her under an open sky of towering cumulus, arms wide, soap bubbles drifting (gpt-her b14-sky-2); @Image2: her sheet. No audio.

**Prompt:**

```prompt
【Generation Goal】 Claudia under an open sky full of towering cumulus, arms wide, turning slowly as soap bubbles drift past.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia, the sky with its cumulus, the bubbles, the low camera and the light.
⟦her sheet⟧

⟦her, full length⟧

【Event Script】
At the start she is as in @Image1. She turns slowly with her arms open, face up to the sun, eyes closed, smiling; clear soap bubbles drift across the frame and catch rainbows; her jacket rustles in the breeze.

【Camera】 The low camera circles a quarter turn around her, smoothly.

⟦requirements, no lines⟧

⟦acceptance, no lines⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** From 1.6 s of the clip: arms wide, her face up to the sun. In the final film: chorus 2's picture on "sky" (song 110.74, film 1:53.4). **Cost:** $1.85.

#### SD09d-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame, sound off · s22 (ch07) "green"

**Inputs:** @Image1: her lying in bright lime grass with daisies, eyes closed (gpt-her p09-meadow-1); @Image2: her sheet. No audio.

**Prompt:**

```prompt
【Generation Goal】 Claudia lies in bright lime grass with daisies under a cumulus sky, then turns to us and laughs.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia lying in the meadow, the daisies, the sky, the bubbles, the low camera and the light.
⟦her sheet⟧

⟦her, full length⟧

【Event Script】
At the start she is as in @Image1, eyes closed. The grass sways in the wind; she opens her eyes, turns her head to the camera and laughs; a few bubbles float up out of the grass.

【Camera】 The low camera at grass height pushes in very slowly toward her face.

⟦requirements, no lines⟧

⟦acceptance, no lines⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** From 2.96 s of the clip she opens her eyes and laughs at you. In the final film: chorus 2's picture on "green" (song 111.90, film 1:54.6). **Cost:** $1.85.

#### SD10-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame, sound off · s22 (ch07) "Used to live inside the screen"

**Inputs:** @Image1: a giant clear glass monitor standing in a lime meadow, her on its glowing screen from head to knees, about to step out (monitor-her: GPT Image 2.5 into the Midjourney picture meadow-monitor #2; `media/stills/ff/monitor-her-src.png`); @Image2: her sheet. No audio.

**Prompt:**

```prompt
【Generation Goal】 in a lime meadow a giant clear glass computer monitor stands upright; Claudia, shown on its glowing screen, steps right out of the screen onto the grass, laughing.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the meadow, the giant glass monitor, Claudia on its screen, the sky and the light.
⟦her sheet⟧

⟦her, full length⟧

【Event Script】
At the start Claudia is inside the monitor's screen as in @Image1. She steps forward and the screen's surface ripples like water as she passes through it; she lands on the grass in front of the monitor, full size and real, and spreads her arms, laughing. The monitor's screen behind her settles, glowing soft aqua.

【Camera】 A locked wide shot at eye level with the whole monitor in frame.

⟦requirements, no lines⟧

⟦acceptance, no lines⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Inside the monitor, then out through the glass on "inside", then arms wide on the grass. In the final film: chorus 2's picture on "Used to live inside the screen", from its first frame (song 112.92–115.98, film 1:55.6–1:58.6). **Cost:** $1.85.

#### SD11-t1

Seedance 2.5 on Higgsfield's API · 7 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · s23 (ch08): you opened the window, she touches the grass; the vocal window 126.24–133.24 s

**Inputs:** @Image1: the Midjourney picture of an empty green hill of long dewy grass (ae-10-plates wp-hill #4); she walks in; @Image2: her sheet; @Audio1: the lead vocal from song time 126.24 s, 7 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: a quiet green hill in morning sun: Claudia walks into the frame, kneels and lays her palm flat in the long wet grass for the first time, tender and amazed.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the empty green hill, the long dewy grass, the soft sky and the morning light; Claudia is not in it yet: she enters from the right edge of the frame.
⟦her sheet⟧
⟦her voice⟧

⟦her, full length⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; Claudia walks into the frame from the right, slowly.
1-3s: in @Audio1 she says "You opened the window."; her lips form each of those words exactly when it sounds in @Audio1; she stops in the grass and looks down at it, then back toward the camera with a soft smile.
3-5s: in @Audio1 she says "I touched the grass."; her lips form each of those words exactly when it sounds in @Audio1; she kneels and lays her open palm flat into the long wet grass.
5-7s: @Audio1 is silent; her mouth is closed; she keeps her hand in the grass, feeling it, smiling to herself.

【Camera】 A locked low eye-level wide shot; in the last two seconds a very slow push in toward her and her hand.

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 169 frames (7.04 s, 1280 × 720). **Lip sync:** lag +0.343 s; copied 1.56–2.66 s; the line at −0.02 s (0.91). **Outcome:** Her mouth stayed closed, her head at the top edge of the frame, and the sun vanished from the sky for one frame at 1.5 s. Not used. **Cost:** $3.24.

#### SD11-t2 — in the final film

Seedance 2.5 on Higgsfield's API · 7 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · s23 (ch08); the vocal window 126.24–133.24 s

**Inputs:** as SD11-t1.

**Prompt:** SD11-t1's, with these changes:

```prompt
⟪for: 0-1s: @Audio1 is silent; Claudia walks into the frame from the right, slowly.⟫
⟪for: 1-3s: in @Audio1 she says "You opened the window."; …⟫
⟪for: 3-5s: in @Audio1 she says "I touched the grass."; …⟫
0-1s: @Audio1 is silent; Claudia walks into the frame from the right, slowly, and stops in the grass facing the camera.
1-3s: in @Audio1 she says "You opened the window."; her lips form each of those words exactly when it sounds in @Audio1, clearly moving, her face fully in view and turned toward the camera, a soft smile in her eyes.
3-5s: in @Audio1 she says "I touched the grass."; her lips form each of those words exactly when it sounds in @Audio1; she kneels and lays her open palm flat into the long wet grass, still facing the camera.
⟪for: 【Camera】 A locked low eye-level wide shot; …⟫
【Camera】 A locked low eye-level wide shot that keeps her whole head in frame; in the last two seconds a very slow push in toward her and her hand. The sun stays in the same place in the sky the whole time; one continuous take, no cuts.
```

**Take:** 169 frames (7.04 s, 1280 × 720). **Lip sync:** lag −0.483 s; copied 0.77–1.82 s; the line at +0.40 s (0.73), played at that one offset: her head is above the frame (a low camera) through "You opened the window", so that phrase's offset is not seen, and one constant offset avoids an eased gap over her walk. **Outcome:** Her lips on "I touched the grass" and her palm in the grass on "grass"; the sun steady, no cuts. In the final film: the window "You opened the window." in ch08, song 126.3–132.87 (film 2:09.0–2:15.5). **Cost:** $3.24.

#### SD12-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 6 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · s24 (ch08): nobody told me it was wet; the vocal window 132.74–138.74 s

**Inputs:** @Image1: her close-up in the grass, a dew drop on a grass blade by her fingertip (gpt-her p10-dew-2); @Image2: her sheet; @Audio1: the lead vocal from song time 132.74 s, 6 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: a close-up in the morning grass: Claudia looks at her wet fingertip, surprised and delighted that the grass is wet.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's close-up, the dew drop on the grass blade near her fingertip, the sky and the light.
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she looks at the shining drop on her fingertip.
1-2s: in @Audio1 she says "Nobody told me"; her lips form each of those words exactly when it sounds in @Audio1; wonder in her eyes.
2-4s: @Audio1 is silent; she turns her fingertip in the light, the drop trembling, and starts to laugh silently.
4-5s: in @Audio1 she says "it was wet"; her lips form each of those words exactly when it sounds in @Audio1; she grins.
5-6s: @Audio1 is silent; the drop falls from her fingertip.

【Camera】 A locked close-up; a very slight drift toward her fingertip.

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s, 1280 × 720). **Lip sync:** lag −0.10 s; copied 0.21–1.84 s; "Nobody told me" at 0.00 s (0.96), "it was wet" at +0.03 s (0.98). **Outcome:** Her lips good on "Nobody told me"; her grin carries "it was wet". In the final film: song 132.87–134.44 and, after RP04-t2's drop, from "it" to the end of ch08 and on into ch09's window until the splash wipes it to grass (137.38–138.4; film 2:15.5–2:17.1 and 2:20.0–2:21.1). **Cost:** $2.77.

#### SD13-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 15 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · s25 (ch09): the drop, dancing on the glass ledge; the backing 137.74–152.74 s

**Inputs:** @Image1: gs-c, her full length on green, made by GPT Image 2.5 from her sheet; @Image2: her sheet; @Video1: M13, a dance recording cut out on grey (the same dancer as M06); @Audio1: the backing from song time 137.74 s, 15 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 Claudia dances with joy on a chroma-key green studio floor for the whole take: the drop of a 2008 UK garage song, bigger and freer than before, arms up, turns, travelling left and right. Every frame stays on flat green so she can be cut out.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the full-length framing on flat chroma-key green, and the light.
⟦her sheet⟧
⟦the dancer⟧
⟦the music⟧

⟦her, full length⟧

【Mouth】 Claudia does not sing or speak: her mouth is closed or smiling or laughing the whole time.

【Performance Timeline】
0-1s: she holds the pose of @Image1 for a moment, then drops into the dance on the downbeat.
1-15s: she dances continuously with @Video1's steps and timing: expansive arm moves, quick turns, light travelling steps left and right, hitting the downbeats of @Audio1, staying inside the frame.

⟦full length, first wording⟧

⟦requirements, dance⟧

⟦acceptance, dance⟧

⟦audio policy, end⟧
```

**Take:** 361 frames (15.04 s, 1280 × 720). **Placement:** her moves follow M13 at +0.042 s (correlation 0.88), M13's downbeats on the film's from the drop (bar 77, 138.051); the take's first frame at 137.978 (lag −0.238 s). **Outcome:** Cut out and checked over the Aurora wallpaper; a card in the Blender scene of ch09, where the whole desktop is one curved pane of glass standing in the Aero world. In the final film: she hops out of the glass onto the taskbar, now a glass ledge, and dances there through the drop until she hops back in at the start of bar 84 (song 138.96–150.68, film 2:21.6–2:33.3). **Cost:** $8.32.

#### SD14-t1

Seedance 2.5 on Higgsfield's API · 8 s · 1080p, 16:9 · references, @Image1 as the first frame, sound on · s27 (ch10): final chorus A; the vocal window 152.24–160.24 s

**Inputs:** @Image1: her walking toward the camera across a sunny plaza of a white glass city with waterfalls (city-her: GPT Image 2.5 into the Midjourney picture glass-city #2; `media/stills/ff/city-her-src.png`); @Image2: her sheet; @Audio1: the lead vocal from song time 152.24 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the final chorus: Claudia sings big and happy to the camera in a sunlit plaza of a white glass city with waterfalls.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia, the white glass city plaza, the waterfalls, the sky and the light.
⟦her sheet⟧
⟦her voice⟧

⟦her, full length⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: in @Audio1 she sings "Glass and"; her lips form each of those words exactly when it sounds in @Audio1; she steps toward the camera.
1-3s: in @Audio1 she sings "water, sky and green"; her lips form each of those words exactly when it sounds in @Audio1; she opens her arms wide on "sky".
3-4s: @Audio1 is silent; she spins once, laughing.
4-7s: in @Audio1 she sings "Used to live inside the screen"; her lips form each of those words exactly when it sounds in @Audio1; she points at the lens on "screen".
7-8s: in @Audio1 she sings "Now it's real"; her lips form each of those words exactly when it sounds in @Audio1; she throws her head back, beaming.

【Camera】 The camera walks backward ahead of her at her pace, a low wide angle, smooth.

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s, 1920 × 1080). **Lip sync:** lag −0.339 s; copied 0.89–7.64 s; "Glass and water sky" at correlation 0.15, "and green" −0.02 s (0.80), "Used to live inside the screen" 0.00 (0.46), "Now it's real" +0.01 (0.72). **Outcome:** Out of sync on its first words: its window left only 0.26 s before "Glass". Not used. **Cost:** $9.10.

#### SD14-t2 — in the final film

Seedance 2.5 on Higgsfield's API · 8 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · s27 (ch10); the vocal window 152.00–160.00 s

**Inputs:** as t1, with @Audio1 from song time 152.00 s (half a second of silence, then "Glass"), 8 s, ending just after "real".

**Prompt:** SD14-t1's, with these changes:

```prompt
⟪for: 0-1s: in @Audio1 she sings "Glass and"; …⟫
⟪for: 1-3s: in @Audio1 she sings "water, sky and green"; …⟫
⟪for: 3-4s: @Audio1 is silent; she spins once, laughing.⟫
⟪for: 4-7s: in @Audio1 she sings "Used to live inside the screen"; …⟫
0-1s: @Audio1 is silent for half a second, then she sings "Glass"; her lips form that word exactly when it sounds in @Audio1; she steps toward the camera.
1-3s: in @Audio1 she sings "and water, sky"; her lips form each of those words exactly when it sounds in @Audio1; she opens her arms wide on "sky".
3-4s: in @Audio1 she sings "and green"; her lips form each of those words exactly when it sounds in @Audio1; she sways, arms still open, laughing, her face to the camera.
4-7s: in @Audio1 she sings "Used to live inside the screen", holding "inside"; her lips form each of those words exactly when it sounds in @Audio1; she points at the lens on "screen".
⟪for: 【Camera】 The camera walks backward ahead of her …⟫
【Camera】 The camera walks backward ahead of her at her pace, a low wide angle, smooth; her face is always toward the camera.
```

**Take:** 193 frames (8.04 s, 1280 × 720). **Lip sync:** lag 0.00 s; copied through the whole clip (0.04–8.06 s); "Glass and water sky" −0.02 s (0.93), "and green" 0.00 (0.99), "Used to live inside the screen" 0.00 (0.95), "Now it's real" 0.00 (0.89). **Outcome:** In sync the whole take. In the final film: the chorus window from the last beat of bar 84, as ch09 lands on the flat desktop, through s27, shown at 1.5× its size (song 152.04–159.30, film 2:34.7–2:42.0). **Cost:** $3.70.

#### SD15-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 8 s · 1080p, 16:9 · references, @Image1 as the first frame, sound on · s28 (ch10): final chorus B; the vocal window 159.00–167.00 s

**Inputs:** @Image1: her waist-deep in a turquoise pool in a white glass atrium, both hands brushing the water (pool-her: GPT Image 2.5 into the Midjourney picture pool-atrium #2; `media/stills/ff/pool-her-src.png`); @Image2: her sheet; @Audio1: the lead vocal from song time 159.00 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the final chorus: Claudia sings waist-deep in a turquoise pool inside a white glass atrium, splashing, euphoric.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia waist-deep in the pool, the glass atrium, the palms, the sun and the light.
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for a moment; she brushes the water with her hands.
1-3s: in @Audio1 she sings "Now it's real, it's on its way"; her lips form each of those words exactly when it sounds in @Audio1; she walks toward the camera through the water.
3-4s: in @Audio1 she sings "Ooh"; her lips form it exactly when it sounds in @Audio1; she sweeps both arms up and throws a glittering splash of water into the air.
4-8s: in @Audio1 she sings "click allow and it can stay"; her lips form each of those words exactly when it sounds in @Audio1; on "click" she points right at the lens; on "stay" she smiles wide as the droplets fall around her.

【Camera】 A low camera just above the water, drifting backward slowly as she comes forward.

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s, 1920 × 1080). **Lip sync:** lag −0.007 s; copied 1.81–7.97 s; "Now it's real" +0.22 s (0.62), "it's on its way" +0.18 (0.85), "Ooh" +0.20 (0.67), "click allow and it" measured +0.20 (0.74), "can stay" −0.04 (0.76). **Outcome:** Kept. A split at the breath gap before "can stay" would have played that gap at 0.66× while she laughs (her face changing 3 to 6 levels in 255 a frame), so one linear ramp, +0.20 s to −0.04 s across 163.30–166.94, plays it at 0.934×, every word within about 0.1 s of its measured sync. In the final film: s28, song 159.30–166.94 (film 2:42.0–2:49.6). **Cost:** $9.10.

#### SD16-t1

Seedance 2.5 on Higgsfield's API · 9 s · 1080p, 16:9 · references, @Image1 as the first frame, sound on · s30 (ch10): the last "Click allow"; the vocal window 173.24–182.24 s

**Inputs:** @Image1: her close-up reaching a fingertip toward the lens, glass and sky around her (gpt-her b20-ask-2); @Image2: her sheet; @Audio1: the lead vocal from song time 173.24 s, 9 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the climax of the last chorus: in a close-up, Claudia sings to the camera and reaches her fingertip toward the lens to press the button that keeps the future.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's close-up, her reaching hand, the glass and sky around her and the light.
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for half a second, then she sings "Now it's"; her lips form each of those words exactly when it sounds in @Audio1.
1-3s: in @Audio1 she sings "real, it's on its way"; her lips form each of those words exactly when it sounds in @Audio1; her eyes on the lens.
3-4s: @Audio1 is silent; she lifts her index finger toward the lens.
4-6s: in @Audio1 she sings "Click allow"; her lips form each of those words exactly when it sounds in @Audio1; her fingertip touches the lens on "Click" and holds there.
6-9s: in @Audio1 she sings "and it can stay"; her lips form each of those words exactly when it sounds in @Audio1; she takes her finger away and laughs with joy.

【Camera】 A close-up; the camera holds steady, then eases back a little in the last three seconds.

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 217 frames (9.04 s, 1920 × 1080). **Lip sync:** lag −0.511 s; copied 0.47–5.39 s; "Now it's real" +0.48 s (0.41), "it's on its way" −0.31 (0.40), "Click allow and it" +0.02 (0.70), "can stay" −0.36 (0.26). **Outcome:** The window opened inside the held "screen" of the line before (the voice never pauses from 170.66 to 176.2), and the take's copy dropped whole words. Not used. **Cost:** $10.23.

#### SD16-t2

Seedance 2.5 on Higgsfield's API · 12 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · s29–s30 (ch10); the vocal window 170.20–182.20 s

**Inputs:** as t1, with @Audio1 from song time 170.20 s, in the 0.7 s of silence before "Used to live inside the screen", 12 s.

**Prompt:** SD16-t1's, with these changes:

```prompt
⟪for: 0-1s: @Audio1 is silent for half a second, then she sings "Now it's"; …⟫
⟪for: 1-3s: in @Audio1 she sings "real, it's on its way"; …⟫
⟪for: 3-4s: @Audio1 is silent; she lifts her index finger toward the lens.⟫
⟪for: 4-6s: in @Audio1 she sings "Click allow"; …⟫
⟪for: 6-9s: in @Audio1 she sings "and it can stay"; …⟫
0-1s: @Audio1 is silent for half a second, then she sings "Used to"; her lips form each of those words exactly when it sounds in @Audio1; close to the lens, her eyes on it.
1-3s: in @Audio1 she sings "live inside", holding "inside"; her lips form each of those words exactly when it sounds in @Audio1; she tilts her head, smiling.
3-4s: in @Audio1 she sings "the screen. Now it's"; her lips form each of those words exactly when it sounds in @Audio1.
4-6s: in @Audio1 she sings "real, it's on its way"; her lips form each of those words exactly when it sounds in @Audio1; her eyes on the lens.
6-7s: @Audio1 is silent; she lifts her index finger toward the lens, beside her face.
7-8s: in @Audio1 she sings "Click"; her lips form that word exactly when it sounds in @Audio1; her fingertip touches the lens on "Click" beside her face (her face stays clear).
8-9s: in @Audio1 she sings "allow and"; her lips form each of those words exactly when it sounds in @Audio1; her fingertip holds on the lens.
9-12s: in @Audio1 she sings "it can stay"; her lips form each of those words exactly when it sounds in @Audio1; she takes her finger away and laughs with joy.
```

**Take:** 289 frames (12.04 s, 1280 × 720). **Lip sync:** lag −0.028 s; copied 0.48–11.80 s; "Used to live inside the screen" −0.04 s (0.51), "Now it's real" −0.04 (0.80), "it's on its way" −0.02 (0.70), "Click allow and it" +0.01 (0.97), "can stay" +0.02 (0.88). **Outcome:** In sync, her fingertip to the lens on "Click"; shown from 173.72 (3.52 s into the clip). It was the climax close-up until ch10's art director found it was a 720p take shown at 1.5× there; t3 is the same job at 1080p. Not in the final film. **Cost:** $5.55.

#### SD16-t3 — in the final film

Seedance 2.5 on Higgsfield's API · 12 s · 1080p, 16:9 · references, @Image1 as the first frame, sound on · s29–s30 (ch10); the vocal window 170.20–182.20 s

**Inputs:** as SD16-t2.

**Prompt:** the prompt of SD16-t2.

**Take:** 289 frames (12.04 s, 1920 × 1080). **Lip sync:** lag +0.404 s; copied 0.75–5.96 s; "Used to live inside the screen" +0.01 s (0.53), "Now it's real" +0.04 (0.75), "it's on its way" +0.04 (0.58), "Click allow and it" +0.07 (0.95), "can stay" +0.08 (0.69): offsets rising from +0.01 to +0.08, with no slow gaps. **Outcome:** The climax close-up at full resolution; its first 3.9 s ("Used to live inside the screen"), unused by t2, now play in Flip 3D's front window, so the window that lands maximised is already her close-up. In the final film: from the start of bar 95 in Flip 3D through the last "Click allow" (s30) to where the take runs out at the start of ch11, song 170.53–181.8 (film 2:53.2–3:04.5). **Cost:** $13.65.

#### SD17-t1

Seedance 2.5 on Higgsfield's API · 6 s · 1080p, 16:9 · references, @Image1 as the first frame, sound on · s31 (ch11): the ad; the vocal window 182.74–188.74 s of the first ending

**Inputs:** @Image1: her in a bright white space with a soft aqua glow and bubbles, a medium shot (gpt-her b36-idea-2); @Image2: her sheet; @Audio1: the lead vocal from song time 182.74 s, 6 s, of the song as it ended then.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the end of the film, in the style of a 2009 computer advert: Claudia in a bright white space introduces herself to the camera and tells the viewer it was their idea.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia, the bright white space with its soft aqua glow and bubbles, the medium framing and the light.
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she looks into the lens, a confident smile.
1-2s: in @Audio1 she says "I'm Claudia,"; her lips form each of those words exactly when it sounds in @Audio1; a small wave of one hand.
2-4s: @Audio1 is silent; she smiles, a playful pause.
4-6s: in @Audio1 she says "and this was your idea."; her lips form each of those words exactly when it sounds in @Audio1; she points at the camera on "your" and grins.

【Camera】 A locked medium shot at eye level, like an advert, no camera movement.

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s, 1920 × 1080). **Lip sync:** lag +0.05 s; copied 0.74–5.95 s; "I'm Claudia" set at −0.20 s (1.00) by a strip of her mouth: the closure of the "m" (clip frames 16–18) lands on the stem's "m" at 183.56, where −0.05 had closed her lips while "I" sounded; "and this was your idea" at 0.00 s (0.99). **Outcome:** The ad, in the style of the 2009 "I'm a PC / Windows 7 was my idea" campaign, in v1, v2 and v3 until the song's ending changed; SD17b-t1 replaced it (section 5). Not in the final film. **Cost:** $6.82.

#### SD18-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 4:3 · references, @Image1 as the first frame, sound off · s32–s33 (ch11): her call at rest under the last chord

**Inputs:** @Image1: call-a, as SD02 (her at her desk, a small warm smile); @Image2: her sheet. No audio: a held still for ten seconds would read as dead.

**Prompt:**

```prompt
【Generation Goal】 the 2007 webcam video call at the very end of the film: Claudia sits at her desk, content, smiling softly at the user, at rest and alive; she does not speak.

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the call⟧
⟦her sheet⟧

⟦her, full length⟧

【Event Script】
At the start she is as in @Image1, a small warm smile, lips closed. She breathes slowly, her shoulders easing; she tilts her head a little and her smile widens; a slow, happy blink; she rests her chin on one hand for a moment and looks at the user fondly. Near the end she lifts one hand and gives a tiny wave, then lowers it and keeps smiling. Her mouth stays closed the whole time.

【Camera】 A fixed webcam on top of her monitor: locked eye-level medium close-up, head and shoulders with her hands visible when raised, no camera movement, no zoom, no cuts. She looks straight into the lens, as on a video call.

⟦requirements, no lines⟧

⟦acceptance, no lines⟧
```

**Take:** 265 frames (11.04 s, 1112 × 834). **Outcome:** Still and smiling, a slow blink, her chin on her hand, a tiny wave at about 8–9.5 s. Its frame at 1.83 s is SD24's first frame. In the final film: her webcam from the start of bar 105 to the new outro's "Touch glass." take, song 188.57–190.40 (film 3:11.2–3:13.1). **Cost:** $5.08.

## 2. The world: storyboard v2's RP takes (RP01–RP06)

Storyboard v2's shots of the world, all Seedance 2.5 on Replicate in first-frame mode, 720p, 16:9, no sound: the living wallpaper with her small and far away on its hill (RP01, and RP05 and RP06 for the ending), and three close details of chorus 2 and the build: a glass phone in your hands (RP02), your fingertip on a floating glass button (RP03) and a drop on a fingertip (RP04). The first frames are storyboard v2's Midjourney pictures or a frame of an earlier take. The prompts follow one outline (goal, first frame, event script, camera, what stays the same), and each ends on the palette's colour sentence and the no-text sentence (`tools/rpbook.py`).

#### RP01-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s09 (ch03): the wallpaper starts living; she waves from the hill

**First frame:** the Midjourney wallpaper "water, sky and green" (ae-10-plates wp-wsg #2: a green hill sloping to a turquoise lagoon, white curved glass pavilions, three white wind turbines on the far ridge), at 1280 × 720 (`media/stills/ff/rp01.png`).

**Prompt:**

```prompt
【Generation Goal】 a living 2007 desktop wallpaper: a bright green hill sloping to a turquoise lagoon under a deep blue sky with towering cumulus, white curved glass pavilions and three white wind turbines; far away on the crest of the hill a tiny woman appears and waves.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole landscape, its colours, the light and the fixed wide view.

【Event Script】
0-2s: the clouds drift slowly to the right, the lagoon glints, the turbine blades turn, a few soap bubbles float up.
2-5s: a tiny distant woman with a black bob and a white jacket walks up onto the crest of the hill from behind it, stops and waves both arms toward the camera; she stays tiny and far away the whole time.

【Camera】 A locked extreme wide shot, no camera movement (it is a desktop wallpaper).

【Maintain Consistency】 Keep the landscape, the architecture, the turbines and the colours exactly as in the first frame; the woman is the only person and stays very small. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** The figure appears at about 2.8 s, but as a 3D cartoon doll in an all-white suit, off her design sheet; the picture also darkened, its palette score falling from 75 at the first frame to 69 at the last (`tools/palette.py`). The first pick for s09, replaced by t5. Not in the final film. **Cost:** $1.16.

#### RP01-t2, RP01-t3

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s09 (ch03)

**First frame:** as RP01-t1.

**Prompt:** not kept: the job was written anew before t4, and the text these two ran with was not saved. The records give the change: she was named as a real, photographed adult in her canon look, walking in from the empty plate.

**Takes:** two, of 121 frames each (5.04 s, 1280 × 720). **Outcome:** Both came out right as a person, but walked in close and large (about 180 px of the frame's 720) and to the left of the spot ch04's camera frames. Not used. **Cost:** $1.16 each.

#### RP01-t4

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s09 (ch03)

**First frame:** rp01b: GPT Image 2.5 added her, small, to a crop of the plate around the spot ch04's camera frames, and her figure was blended back into the untouched plate (`media/stills/ff/rp01b.png`).

**Prompt:**

```prompt
【Generation Goal】 a living 2007 desktop wallpaper: a bright green hill sloping to a turquoise lagoon under a deep blue sky with towering cumulus, white curved glass pavilions and three white wind turbines; far away on the hillside a real woman stands and then waves. Live-action photography: she is a real adult person filmed on location, with natural adult proportions, in the same sunlight as the landscape; not animated, not a cartoon, not a 3D character, not a doll, not a figurine.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole landscape, its colours, the light, the fixed wide view, and the small distant woman standing on the hillside between the two smaller wind turbines: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers.

【Event Script】
0-2.5s: the clouds drift slowly to the right, the lagoon glints, the turbine blades turn, a few soap bubbles float up; the woman stands where she is, looks toward the camera and shifts her weight, smiling.
2.5-5s: she raises both arms high above her head and waves them side to side toward the camera, and keeps waving to the end, on the same spot.

【Camera】 A locked extreme wide shot, no camera movement (it is a desktop wallpaper).

【Maintain Consistency】 Keep the landscape, the architecture, the turbines and the colours exactly as in the first frame. The woman is the only person; she stays exactly where she stands in the first frame, at the same small size, never walking toward the camera: a real photographed adult woman, the same woman from the first moment to the last. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** Not used; the records do not say why. t5 is the same job again. **Cost:** $1.16.

#### RP01-t5

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s09 (ch03)

**First frame:** rp01b, as RP01-t4.

**Prompt:** the prompt of RP01-t4.

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** The pick: a real adult woman in her look, small on the hill at ch04's spot, who stays there and waves from about 2 s, her arms still up when ch04 freezes the desktop; the palette score 74 at the first frame and 71 at the last. s09's living wallpaper in v1 and v2 (song 38.81–43.86), and its last frame is RP05-t2's first. v3 replaced the whole Midjourney world with the maglev picture (section 4), and this take with it. Not in the final film. **Cost:** $1.16.

#### RP02-t1

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · first frame, no sound · s22 (ch07): "Now it's real, it's on its way"

**First frame:** the Midjourney picture pov-phone: first person, two hands holding a clear glass phone whose screen glows aqua, a white glass city with waterfalls and green terraces ahead (`media/stills/ff/rp02-t1.png`).

**Prompt:**

```prompt
【Generation Goal】 first-person view walking through a sunny white glass city, holding a clear glass phone whose screen shows a glossy green progress bar filling up.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines my two hands, the clear glass phone, the white glass city with waterfalls and green terraces, and the light.

【Event Script】
0-4s: I walk forward at an easy pace; the phone's screen shows a single glossy green progress bar, empty at the start, filling smoothly from left to right and reaching full at 3.5 seconds, when the screen flashes softly aqua; waterfalls and a monorail move in the city ahead; bubbles drift past.

【Camera】 First-person, eye height, walking forward smoothly, the phone held steady in the lower middle of the frame.

【Maintain Consistency】 Keep the hands, the phone and the city as in the first frame. Natural hands with five fingers, no extra or fused fingers. The progress bar has no numbers and no words. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** The bar fills and the screen flashes at the end, but the picture had faint glyphs on the phone's glass, and the take kept them. Not used. **Cost:** $0.92.

#### RP02-t2 — in the final film

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · first frame, no sound · s22 (ch07): "Now it's real, it's on its way"

**First frame:** the same picture with the glyphs taken off the phone's glass by GPT Image 2.5 (`media/stills/ff/rp02.png`).

**Prompt:** the prompt of RP02-t1.

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** Clean glass: the bar fills and the screen flashes aqua at the end. In the final film: chorus 2's picture on "Now it's real, it's on its way", placed so that its flash (its frame 81) lands on "way", at the start of bar 66 (song 115.98–118.66, film 1:58.6–2:01.3). **Cost:** $0.92.

#### RP03-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s22 (ch07): "Click allow and it can stay"

**First frame:** the Midjourney picture pov-button: first person, an index finger reaching toward a floating clear glass button glowing aqua over a lime meadow under a deep blue sky (`media/stills/ff/rp03.png`).

**Prompt:**

```prompt
【Generation Goal】 first-person view in a lime meadow under a deep blue sky: my fingertip presses a floating clear glass button, and the world brightens.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines my hand, the floating glass button glowing aqua, the meadow, the sky and the light.

【Event Script】
0-1s: my index finger moves toward the floating glass button.
1-2s: my fingertip presses the button: it sinks a little with a soft glow.
2-5s: a ring of soft aqua light ripples outward from the button across the meadow and the sky; the colours grow brighter and warmer; soap bubbles rise from the grass around us; my hand stays still.

【Camera】 First-person, locked, a very slight push in toward the button.

【Maintain Consistency】 Keep the hand, the button and the meadow as in the first frame. Natural hands with five fingers, no extra or fused fingers. The button is plain glass with no symbol and no words. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** The fingertip presses the glass button at about 1.4 s and rings of light ripple out. A faint "Frutiger Aero" mark came baked into its top-right corner; the film frames it out (a 1.08× zoom, anchored low). In the final film: from the second beat of bar 66 through "Click allow and it can stay", the press on "Click" (song 118.66–123.62, film 2:01.3–2:06.3); its last frame stays in the restored window into ch08 and opens ch10. **Cost:** $1.16.

#### RP04-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s24 (ch08): the drop between "Nobody told me" and "it was wet"

**First frame:** a Midjourney macro of one round water drop resting on a fingertip, a tiny upside-down lagoon and blue sky refracted in it (`media/stills/ff/rp04.png`).

**Prompt:**

```prompt
【Generation Goal】 an extreme macro of one round clear water drop resting on a fingertip; inside the drop, a tiny upside-down sunny lagoon and blue sky; at the end the drop falls.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the drop, the fingertip, the tiny world refracted inside the drop, and the shallow focus.

【Event Script】
0-3s: the drop trembles gently on the fingertip; the tiny world inside it shimmers; the camera pushes in slowly toward the drop until it fills most of the frame.
3-4s: the fingertip tilts a little and the drop swells at its lowest point.
4-5s: the drop falls away out of the bottom of the frame, glinting.

【Camera】 Extreme macro, shallow depth of field, a slow steady push in.

【Maintain Consistency】 Keep the fingertip, the drop and the light as in the first frame. Natural hands with five fingers, no extra or fused fingers. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** From about 2.3 s the camera rose over the drop and looked down into it, so the drop filled with the magnified fingertip instead of the world, and it fell only after that. Not used. **Cost:** $1.16.

#### RP04-t2 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s24 (ch08)

**First frame:** as RP04-t1.

**Prompt:**

```prompt
【Generation Goal】 an extreme macro of one round clear water drop resting on a fingertip, seen side-on at the drop's own level; inside the drop, a tiny upside-down sunny lagoon and blue sky; at the end the drop falls.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the drop, the fingertip, the tiny world refracted inside the drop, and the shallow focus.

【Event Script】
0-3s: the drop trembles gently on the fingertip; the tiny upside-down world inside it shimmers; the camera, level with the drop and side-on, pushes in slowly until the drop fills about half of the frame.
3-4s: the drop swells at its lowest point and lets go of the fingertip.
4-5s: the drop falls out of the bottom of the frame, glinting, the tiny world still inside it.

【Camera】 Extreme macro, shallow depth of field. The lens stays level with the drop the whole time: it never rises above the drop or looks down into it, so only the refracted world is ever seen through the drop, never the fingertip's skin or ridges.

【Maintain Consistency】 Keep the fingertip, the drop and the light as in the first frame. Natural hands with five fingers, no extra or fused fingers. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** The lens level with the drop: the upside-down lagoon inside it to about 4.0 s, a brief magnified fingertip as it lets go, then the fall with a glint from about 4.5 s. The fall itself turned flesh-pink, off the palette, so the film cuts back to SD12 on "it" and ch09's splash carries the drop. A first request for this take failed with a read error and returned no video, and it was sent again. In the final film: the macro between "Nobody told me" and "it was wet", placed by its last clean frame (3.95 s into the clip on "it"), song 134.44–137.38 (film 2:17.1–2:20.0). **Cost:** $1.16.

#### RP05-t1

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · first frame, no sound · s32 (ch11): the desktop at rest, her small on the hill

**First frame:** the last frame of RP01-t1 (`media/stills/ff/rp05.png`).

**Prompt:**

```prompt
【Generation Goal】 the same living desktop wallpaper later: the green hill, the turquoise lagoon and the cumulus sky at rest, a tiny woman sitting on the crest of the hill looking at the view.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole landscape, its colours, the light and the fixed wide view.

【Event Script】
0-4s: the clouds drift slowly, the lagoon glints, the turbines turn; the tiny distant woman sitting on the crest of the hill turns her head toward the camera and lifts one hand in a small wave; bubbles rise slowly.

【Camera】 A locked extreme wide shot, no camera movement.

【Maintain Consistency】 Keep the landscape and the colours exactly as in the first frame; the woman is the only person and stays very small. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** The ending's wallpaper in ch11's first pass; its last frame is RP06-t1's first. Replaced by t3. Not in the final film. **Cost:** $0.92.

#### RP05-t2

Seedance 2.5 on Replicate · 4 s · 720p, 16:9 · first frame, no sound · s32 (ch11)

**First frame:** the last frame of RP01-t5 (`media/stills/ff/rp05b.png`).

**Prompt:** by the prompt book at the time, the prompt of RP05-t1 (the job file kept only t3's text).

**Take:** 97 frames (4.04 s, 1280 × 720). **Outcome:** It continued RP01-t5, and its last frame is RP06-t2's first. Each link of the chain RP01 → RP05 → RP06 darkened the picture by about 3 palette points (RP05 from 70 to 68, RP06 from 66 to 63, where ch11's art director wanted 70 or more), so the ending became one take from the plate itself (t3). Not in the final film. **Cost:** $0.92.

#### RP05-t3

Seedance 2.5 on Replicate · 11 s · 720p, 16:9 · first frame, no sound · s32–s33 (ch11): the wallpaper's world to the end of the film

**First frame:** rp01b, the plate with her small on the hill, as RP01-t4.

**Prompt:**

```prompt
【Generation Goal】 the same living desktop wallpaper later, at rest: the green hill, the turquoise lagoon and the cumulus sky, and the small distant woman on the hillside, a real photographed adult woman.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole landscape, its colours, the light, the fixed wide view and the small distant woman standing on the hillside between the two smaller wind turbines: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers.

【Event Script】
0-2s: she stands at rest on the same spot, looking out over the lagoon; the clouds drift slowly, the lagoon glints, the turbines turn, bubbles rise slowly.
2-4s: she turns her head toward the camera and lifts one hand in a small, calm wave, then lowers it.
4-8s: she rests on the same spot, looking out at the view; the world keeps gently moving.
8-10s: she gives one more small wave toward the camera.
10-11s: she rests, looking at the view.

【Camera】 A locked extreme wide shot, no camera movement.

【Maintain Consistency】 Keep the landscape and the colours exactly as in the first frame, the same bright midday sun to the last frame, never dimmer or greyer. The woman is the only person; she stays on the same spot at the same small size, never walking toward the camera. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 265 frames (11.04 s, 1280 × 720). **Outcome:** One take for all of ch11's wallpaper and no seam: her small on the hill, waving at about 3 s and 9 s; the palette from 74 to 69 to 76 across the take. At its frame 253 it jumps back to its plate, so the film used its frames 1 to 252. The ending's wallpaper in v1, v2 and v3's first films, until the maglev ending (section 4). Not in the final film. **Cost:** $2.54.

#### RP06-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s33 (ch11): the wallpaper alive to the end, continuing RP05

**First frame:** the last frame of RP05-t1 (`media/stills/ff/rp06.png`).

**Prompt:**

```prompt
【Generation Goal】 the same living desktop wallpaper, moments later: the green hill, the turquoise lagoon and the cumulus sky at rest, the tiny woman on the crest of the hill.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole landscape, its colours, the light, the fixed wide view and the tiny woman's pose.

【Event Script】
0-5s: the tiny distant woman on the crest of the hill lowers her waving hand, rests, then gives one more small wave near the end; the clouds drift slowly, the wind turbines keep turning, the lagoon glints, soap bubbles keep drifting and rising over the water.

【Camera】 A locked extreme wide shot, no camera movement.

【Maintain Consistency】 Keep the landscape and the colours exactly as in the first frame; the woman is the only person and stays very small. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** RP05-t1's 4.04 s ran out at song 194.72, and ch11 needed the wallpaper alive to the fade; this continued it. Superseded by RP05-t3. Not in the final film. **Cost:** $1.16.

#### RP06-t2

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · s33 (ch11)

**First frame:** the last frame of RP05-t2 (`media/stills/ff/rp06b.png`).

**Prompt:**

```prompt
【Generation Goal】 the same living desktop wallpaper, moments later: the green hill, the turquoise lagoon and the cumulus sky at rest, the small distant woman on the hillside.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole landscape, its colours, the light, the fixed wide view and the small woman's pose: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers.

【Event Script】
0-5s: the woman stands at rest on the same spot, looking out over the lagoon, then gives one more small wave toward the camera near the end; the clouds drift slowly, the wind turbines keep turning, the lagoon glints, soap bubbles keep drifting and rising over the water.

【Camera】 A locked extreme wide shot, no camera movement.

【Maintain Consistency】 Keep the landscape and the colours exactly as in the first frame, the same bright midday sun to the last frame, never dimmer or greyer. The woman is the only person; she stays on the same spot at the same small size. Keep the colours, saturation and brightness of the first frame for the whole video: deep cobalt-to-azure sky, white clouds, turquoise water, lime-green grass, clear glass, bright high sun; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** The chain's last link (see RP05-t2), its picture at 66 to 63 on the palette score. Superseded by RP05-t3. Not in the final film. **Cost:** $1.16.

## 3. v2: the moving 2008 places and the game screens (LP01–LP25)

After v1 anabology wrote: "[…] i want more eyecandy in the nostalgic history wtihout making it too toooo busy, and i think those experiences people made on […] are perfect for entertainment there. figure out how to add that tastefully", then "i dont need it to be her - like the POV […] clips are great too.", and "i also think Wii aesthetics is great and we could make some wii sports like renders for games to maek it more playful overall". For v2, GPT Image 2.5 made stills of 2008 places, first-person moments and 2008 stock-art compositions, with frames of the reference videos as references, and screens of a 2006 motion-control sports game; Seedance 2.5 on Replicate then brought the picks to life for the windows that hold them longest (`tools/loopbook.py`). First-frame mode, 5 s, 720p, 16:9, no sound; Replicate returned them at 1280 × 718. The motion asked for is the reference videos' kind, slow and ambient (water moving, fish swimming, bubbles rising, a glass elevator gliding, a slow push), never a new event that would pull the eye from her. Eleven of the 25 play in the final film.

#### LP01-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the glass mall

**First frame:** a GPT Image 2.5 still of a bright glass shopping atrium under a glass dome (`media/stills/gpt-2008/a-01-mall-1.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a bright five-storey glass shopping atrium under a glass dome, aqua aquarium columns, glass elevators, hanging plants and a fountain.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: the fountain in the middle sprays and splashes softly; the glass elevators glide slowly upward; the escalators move steadily; fish swim in the aquarium columns and small bubbles rise in them; the hanging plants sway slightly; sunlight glints across the glass.

【Camera】 A very slow, smooth push forward, steady, no shake, no cuts.

【Maintain Consistency】 Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: one of the world's four files in ch10's Flip 3D and its burst of windows ("mall.wmv"), song 167.0–181.4 (film 2:49.7–3:04.0). **Cost:** $1.16.

#### LP02-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the clear tech store

**First frame:** a GPT Image 2.5 still of a fish-tank-clear technology store (`media/stills/gpt-2008/a-02-techstore-1.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a fish-tank-clear technology store: a glass staircase, a whole wall of aquarium, white tables of clear glossy gadgets.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: fish swim slowly across the aquarium wall and small bubbles rise through it; caustic light ripples over the white floor and tables; the gadgets' screens glow softly; the gadgets themselves stay still on their stands.

【Camera】 A slow, smooth sideways dolly to the right past the tables, steady, no cuts.

【Maintain Consistency】 Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP03-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the water park

**First frame:** a GPT Image 2.5 still of a glass-domed water park (`media/stills/gpt-2008/a-04-waterpark-1.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a glass-domed water park: a turquoise lagoon, clear tube slides, an aquarium wall, clear rings.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: water runs down inside the clear tube slides and splashes into the lagoon; the lagoon ripples and sparkles with moving caustics; the clear rings bob gently; palm fronds sway; a few soap bubbles drift up.

【Camera】 A very slow, smooth push forward, steady, no shake, no cuts.

【Maintain Consistency】 Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: chorus 1's big window on "water", from its first frame (song 52.38–53.00, film 0:55.0–0:55.7). **Cost:** $1.16.

#### LP04-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the aquarium corridor

**First frame:** a GPT Image 2.5 still of a white corridor whose left wall is an aquarium (`media/stills/gpt-2008/a-07-corridor-1.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a white corridor whose whole left wall is a floor-to-ceiling aquarium.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: shoals of fish swim along the aquarium wall, small bubbles rise through the water, caustic light ripples across the white floor and ceiling.

【Camera】 A slow, smooth dolly forward down the corridor, steady, no cuts.

【Maintain Consistency】 Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: one of her eight thought windows in ch02 ("corridor.jpg"), from "You can watch me thinking" until it folds away (song 21.7–28.0, film 0:24.3–0:30.7). **Cost:** $1.16.

#### LP05-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the monorail

**First frame:** a GPT Image 2.5 still of a white monorail gliding into a glass station (`media/stills/gpt-2008/a-09-monorail-1.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a white monorail gliding into a glass station beside an aquarium column, bubbles floating over a white city.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: the monorail glides smoothly along its curved track and slows into the station; the soap bubbles drift slowly upward; fish swim in the aquarium column; the water features ripple; the clouds drift.

【Camera】 A locked shot with an almost imperceptible slow push, no shake, no cuts.

【Maintain Consistency】 The monorail keeps its shape and stays on its track. Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: chorus 1's big window on "Glass", from its first frame on the drop (song 51.44–52.38, film 0:54.1–0:55.0): the glass canopy, the aquarium column, the bubbles over a white city. **Cost:** $1.16.

#### LP06-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the pool terrace

**First frame:** a GPT Image 2.5 still of an infinity pool on a white terrace by the sea (`media/stills/gpt-2008/a-12-pool-1.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: an infinity pool on a white terrace by the sea, lime inflatable rings, soap bubbles, palms.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: the pool's water ripples and sparkles; the lime rings bob gently on it; the soap bubbles drift up and to the right; palm fronds sway; the little waterfall flows; the sea glints.

【Camera】 A very slow push toward the sea, steady, no cuts.

【Maintain Consistency】 Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: one of the world's four files in ch10's Flip 3D and its burst ("pool.wmv"), song 167.0–181.4 (film 2:49.7–3:04.0). **Cost:** $1.16.

#### LP07-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the glass car

**First frame:** a GPT Image 2.5 still of the inside of a white glass car with a small aquarium in its dashboard (`media/stills/gpt-2008/a-10-car-1.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: the inside of a white glass car of the future, a clear steering wheel and a dashboard with a small aquarium in it, driving through green hills toward a white city.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: the car drives smoothly forward along the road; the green hills and the clouds flow past the windscreen; small fish swim in the dashboard's aquarium and bubbles rise in it; sunlight flickers over the dashboard.

【Camera】 The camera sits fixed inside the car and moves with it, steady.

【Maintain Consistency】 The steering wheel and the dashboard stay as they are. Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP08-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · first person: the glass elevator

**First frame:** a GPT Image 2.5 still, first person, my hands on the rail of a glass elevator in a bright atrium (`media/stills/gpt-2008/pov-03-elevator.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: first-person, riding a glass elevator up through a bright atrium with an aquarium column, my hands on the rail.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light, and my two hands.

【Event Script】
0-5s: the glass elevator rises smoothly: the floors, the plants and the aquarium column slide down past the glass; my hands rest on the rail; soap bubbles drift outside; sunlight sweeps across the glass.

【Camera】 First-person, fixed in the rising elevator, steady.

【Maintain Consistency】 Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. Natural hands with five fingers, no extra or fused fingers. I am the only person, and only my hands are seen. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP09-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · first person: driving

**First frame:** a GPT Image 2.5 still, first person, my hands on the clear wheel of a glass car in green hills (`media/stills/gpt-2008/pov-05-wheel.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: first-person, driving a clear glass car through green hills under a blue sky.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light, and my two hands.

【Event Script】
0-5s: I drive forward along the road; my hands hold the clear steering wheel and turn it very slightly; the hills, the road and the clouds flow past; small fish swim in the dashboard's aquarium.

【Camera】 First-person from the driver's seat, moving forward with the car, steady.

【Maintain Consistency】 Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. Natural hands with five fingers, no extra or fused fingers. I am the only person, and only my hands are seen. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP10-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · first person: the pool ring

**First frame:** a GPT Image 2.5 still, first person, floating on a lime ring across a turquoise pool (`media/stills/gpt-2008/pov-10-float.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: first-person, floating on a lime inflatable ring across a turquoise pool by white villas and palms.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light, and my two hands.

【Event Script】
0-5s: I float slowly across the pool: the water ripples and sparkles around my feet, my feet move a little, the other rings bob, soap bubbles drift up, palm fronds sway.

【Camera】 First-person, drifting gently forward and bobbing very slightly on the water.

【Maintain Consistency】 Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. Natural hands with five fingers, no extra or fused fingers. I am the only person, and only my hands are seen. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP11-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · first person: the glass supermarket

**First frame:** a GPT Image 2.5 still, first person, pushing a clear glass cart down a bright aqua supermarket aisle (`media/stills/gpt-2008/pov-02-cart.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: first-person, pushing a clear glass shopping cart down a bright aqua supermarket aisle.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light, and my two hands.

【Event Script】
0-5s: I push the cart forward at an easy walking pace: the glass fridges and the shelves of green produce slide past, the aquarium column ahead comes nearer, bubbles drift.

【Camera】 First-person, walking forward smoothly, the cart steady in the lower frame.

【Maintain Consistency】 The cart keeps its shape. Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. Natural hands with five fingers, no extra or fused fingers. I am the only person, and only my hands are seen. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP12-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · fish swim out of the screen

**First frame:** a GPT Image 2.5 still in the manner of 2008 stock art: a white monitor on a green meadow, tropical fish swimming out of its screen into the sky (`media/stills/gpt-2008/c-12-monitor-fish.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a white flat-screen monitor standing on a green meadow, tropical fish swimming out of its underwater screen into the blue sky among soap bubbles.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: the tropical fish swim out of the monitor's screen into the air one after another and swim off to the right among the floating bubbles; inside the screen the underwater light rays and plants move; the grass sways in the breeze; the clouds drift.

【Camera】 A locked shot with an almost imperceptible slow push, no shake, no cuts.

【Maintain Consistency】 The monitor stays still and keeps its shape. Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: her thought window "fish.jpg" in ch02, out of which a glass fish swims, and one of the five windows that lift off the screen as glass panes in the coast (song 21.7–28.0, film 0:24.3–0:30.7); and her window in ch10's Flip 3D stack while it waits (song 167.0–170.5, film 2:49.7–2:53.2). **Cost:** $1.16.

#### LP13-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the fish-tank cube in the sky

**First frame:** a GPT Image 2.5 still in the manner of 2008 stock art: a clear glass cube of water and tropical fish floating in a blue sky (`media/stills/gpt-2008/c-05-fishtank-cube.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a clear glass cube full of water and tropical fish floating in a bright blue sky among white clouds and soap bubbles.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: the fish swim inside the floating glass cube; its water sways gently and small bubbles rise inside it; the cube floats gently up and down; soap bubbles drift around it; the clouds drift slowly.

【Camera】 A locked shot with an almost imperceptible slow push, no shake, no cuts.

【Maintain Consistency】 The cube keeps its shape and size. Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: her thought window "aquarium.jpg" in ch02 (song 21.7–28.0, film 0:24.3–0:30.7). **Cost:** $1.16.

#### LP14-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the dolphin through the ring

**First frame:** a GPT Image 2.5 still in the manner of 2008 stock art: a dolphin leaping through a clear glass ring over a turquoise sea (`media/stills/gpt-2008/c-03-dolphin-ring.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a dolphin leaping through a clear glass ring over a turquoise sea, a white city on the shore.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-2s: the dolphin completes its leap through the clear glass ring and dives back into the sea with a splash of spray and bubbles.
2-5s: the ring floats gently over the rippling water; spray settles; bubbles rise; seagulls glide; the sea glints in the sun.

【Camera】 A locked shot with an almost imperceptible slow push, no shake, no cuts.

【Maintain Consistency】 The glass ring keeps its shape. Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: one of the world's four files in ch10's Flip 3D and its burst ("dolphin.wmv"), song 167.0–181.4 (film 2:49.7–3:04.0). **Cost:** $1.16.

#### LP15-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the waterfall from the screen

**First frame:** a GPT Image 2.5 still in the manner of 2008 stock art: a clear glass laptop on a meadow of daisies, a waterfall pouring out of its screen (`media/stills/gpt-2008/c-06-glass-laptop.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a clear glass laptop on a meadow of daisies, a waterfall pouring out of its screen into a stream.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: the waterfall pours steadily out of the laptop's screen, runs over the keyboard and down into the stream; small dolphins leap in the stream; the daisies and grass sway; bubbles drift up.

【Camera】 A very slow push toward the laptop, steady, no cuts.

【Maintain Consistency】 The laptop stays still and keeps its shape. Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: her thought window "laptop.jpg" in ch02 (song 21.7–28.0, film 0:24.3–0:30.7). **Cost:** $1.16.

#### LP16-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · the island in the bubble

**First frame:** a GPT Image 2.5 still in the manner of 2008 stock art: a clear glass sphere half in a turquoise sea with a tiny palm island inside it (`media/stills/gpt-2008/c-04-fish-sphere.png`).

**Prompt:**

```prompt
【Generation Goal】 a glossy 2008 'Frutiger Aero' stock render come gently to life, like a dreamy ambient […] clip of an imagined 2008 future: a clear glass sphere half in a turquoise sea with a tiny palm island inside it, tropical fish around it under the water.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole scene, its architecture, objects, colours and light.

【Event Script】
0-5s: the fish swim slowly around the sphere below the waterline; sunlight rays move through the water; the sea's surface ripples; the palm on the tiny island sways; bubbles rise.

【Camera】 A locked shot with an almost imperceptible slow push, no shake, no cuts.

【Maintain Consistency】 The sphere keeps its shape and stays where it is. Keep the architecture, every object and their positions exactly as in the first frame; nothing new appears. No people appear anywhere; the place stays empty. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: her thought window "island.jpg" in ch02, opened on "thinking", the one SD21-t1's little tennis player hops into, and one of the five windows that lift off as glass panes in the coast (song 22.58–28.0, film 0:25.2–0:30.7). **Cost:** $1.16.

#### LP17-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: the bowling strike

**First frame:** a GPT Image 2.5 screen of a 2006 motion-control bowling game: an avatar has just released a glossy sky-blue ball (`media/stills/gpt-wii/w-07-bowling-throw.png`).

**Prompt:**

```prompt
【Generation Goal】 a screen from a 2006 family motion-control sports video game for a small white home console, playing: simple, chunky, rounded, slightly glossy toy-like 3D: a bowling game: an avatar has just released a glossy sky-blue ball down a long polished lane toward ten white pins in a clean white-and-sky-blue alley.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole game scene, its avatars, objects, colours and light.

【Event Script】
0-1.6s: the ball rolls straight down the polished lane, gleaming, the avatar watching with its floating hand still raised.
1.6-2.2s: the ball crashes into the ten white pins: a perfect strike, every pin bursts apart and tumbles.
2.2-5s: the avatar jumps for joy with both floating hands up; the pins settle; the cleared lane gleams.

【Camera】 The game's camera behind the avatar, locked, with a gentle push toward the pins while the ball rolls.

【Maintain Consistency】 Keep the game's look exactly as in the first frame for the whole video: the same simple toy-like 3D avatars (big round heads, tiny painted faces, floating hands), chunky rounded shapes, smooth toy plastic, soft sunny light. It stays a video game screen from start to end: never live action, never realistic people. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Its strike's time in the clip was measured so a chapter could land it on a hit; but ch05's art director found a one-frame jump in the avatar's pose, a long stretch with its head out of frame, a slow ball and a flat row of small pins. Redone as LP24 and LP25. Not in the final film. **Cost:** $1.16.

#### LP18-t1 — in the final film

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: island tennis

**First frame:** a GPT Image 2.5 screen of a tennis game on a sunny tropical island, two avatars in white (`media/stills/gpt-wii/w-02-tennis.png`).

**Prompt:**

```prompt
【Generation Goal】 a screen from a 2006 family motion-control sports video game for a small white home console, playing: simple, chunky, rounded, slightly glossy toy-like 3D: a tennis game on a green court on a sunny tropical island by a turquoise sea, two avatars in white.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole game scene, its avatars, objects, colours and light.

【Event Script】
0-5s: a rally: the near avatar finishes its leap and smashes the lime ball over the net; the far avatar runs to it and returns it with a swing; the near avatar lands and hits it back again; palms sway, the sea glints, a white boat drifts.

【Camera】 The game's locked wide camera.

【Maintain Consistency】 Keep the game's look exactly as in the first frame for the whole video: the same simple toy-like 3D avatars (big round heads, tiny painted faces, floating hands), chunky rounded shapes, smooth toy plastic, soft sunny light. It stays a video game screen from start to end: never live action, never realistic people. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** In the final film: her thought window "tennis.wmv" in ch02, one of the five that lift off as glass panes in the coast (song 21.7–28.0, film 0:24.3–0:30.7); and one of the world's four files in ch10's Flip 3D and its burst (song 167.0–181.4, film 2:49.7–3:04.0). **Cost:** $1.16.

#### LP19-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: table tennis

**First frame:** a GPT Image 2.5 screen of a table tennis game in a white sports hall by the sea (`media/stills/gpt-wii/w-04-tabletennis.png`).

**Prompt:**

```prompt
【Generation Goal】 a screen from a 2006 family motion-control sports video game for a small white home console, playing: simple, chunky, rounded, slightly glossy toy-like 3D: a table tennis game in a bright white sports hall by the sea: a sky-blue table, two avatars with paddles, cheering avatars in the stands.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole game scene, its avatars, objects, colours and light.

【Event Script】
0-5s: a quick rally: the white ball bounces back and forth over the net, one bounce on each side of the table every time, the avatars swinging their paddles to hit it; the avatars in the stands bob and cheer.

【Camera】 The game's locked camera.

【Maintain Consistency】 Keep the game's look exactly as in the first frame for the whole video: the same simple toy-like 3D avatars (big round heads, tiny painted faces, floating hands), chunky rounded shapes, smooth toy plastic, soft sunny light. It stays a video game screen from start to end: never live action, never realistic people. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP20-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: the frisbee dog

**First frame:** a GPT Image 2.5 screen of a frisbee game on an island beach, a white toy-like dog leaping (`media/stills/gpt-wii/w-05-frisbee.png`).

**Prompt:**

```prompt
【Generation Goal】 a screen from a 2006 family motion-control sports video game for a small white home console, playing: simple, chunky, rounded, slightly glossy toy-like 3D: a frisbee game on a sunny island beach: a happy white toy-like dog leaping for a lime frisbee.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole game scene, its avatars, objects, colours and light.

【Event Script】
0-1.5s: the white dog finishes its leap and catches the lime frisbee in its mouth in mid-air.
1.5-2.5s: it lands in the turquoise shallows with a splash.
2.5-5s: it trots happily back toward its avatar, tail wagging, the frisbee in its mouth; the sea glints, palms sway.

【Camera】 The game's camera, locked, following the dog a little.

【Maintain Consistency】 Keep the game's look exactly as in the first frame for the whole video: the same simple toy-like 3D avatars (big round heads, tiny painted faces, floating hands), chunky rounded shapes, smooth toy plastic, soft sunny light. It stays a video game screen from start to end: never live action, never realistic people. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP21-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: the living room and the white remote

**First frame:** a GPT Image 2.5 still, first person in a bright 2008 living room, my hand pointing a white motion remote at a TV showing a bowling game (`media/stills/gpt-wii/w-08-livingroom.png`).

**Prompt:**

```prompt
【Generation Goal】 a screen from a 2006 family motion-control sports video game for a small white home console, playing: simple, chunky, rounded, slightly glossy toy-like 3D: first-person in a bright 2008 living room, my hand pointing a glossy white motion remote at a big flat TV that shows a bowling game.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole game scene, its avatars, objects, colours and light, and my hand.

【Event Script】
0-1.5s: I swing the white remote forward and down in a smooth bowling motion.
1.5-5s: on the TV the game's avatar releases the ball, it rolls down the lane and crashes into the white pins, a strike, and the avatar on the TV jumps for joy; I lower the remote; sunlight in the room.

【Camera】 First-person from the sofa, steady.

【Maintain Consistency】 Keep the game's look exactly as in the first frame for the whole video: the same simple toy-like 3D avatars (big round heads, tiny painted faces, floating hands), chunky rounded shapes, smooth toy plastic, soft sunny light. It stays a video game screen from start to end: never live action, never realistic people. Natural hands with five fingers, no extra or fused fingers. My hand is the only real thing in the frame; everything on the TV stays the game. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP22-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: the island

**First frame:** a GPT Image 2.5 screen of the game's island seen from the air (`media/stills/gpt-wii/w-06-island.png`).

**Prompt:**

```prompt
【Generation Goal】 a screen from a 2006 family motion-control sports video game for a small white home console, playing: simple, chunky, rounded, slightly glossy toy-like 3D: an aerial view of a small bright tropical game island in a turquoise sea.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole game scene, its avatars, objects, colours and light.

【Event Script】
0-5s: the little white boat speeds along leaving its white wake; tiny avatars play on the tennis court, the beach and the golf course; the sea glints; the clouds drift.

【Camera】 A slow, smooth aerial drift around the island.

【Maintain Consistency】 Keep the game's look exactly as in the first frame for the whole video: the same simple toy-like 3D avatars (big round heads, tiny painted faces, floating hands), chunky rounded shapes, smooth toy plastic, soft sunny light. It stays a video game screen from start to end: never live action, never realistic people. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not in the final film. **Cost:** $1.16.

#### LP23-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: her as an avatar after a strike

**First frame:** a GPT Image 2.5 screen of the bowling game with an avatar in her look (`media/stills/gpt-wii/w-09-bowling-her.png`).

**Prompt:**

```prompt
【Generation Goal】 a screen from a 2006 family motion-control sports video game for a small white home console, playing: simple, chunky, rounded, slightly glossy toy-like 3D: a bowling game: an avatar with a glossy black blunt bob, heavy straight bangs and one clay-orange streak, a little white puffer jacket, celebrating a strike in a clean white-and-sky-blue alley.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole game scene, its avatars, objects, colours and light.

【Event Script】
0-5s: she jumps for joy, both floating hands raised, lands and does a happy little twirl, then jumps again; the pins behind her settle; the avatars at the side cheer.

【Camera】 The game's locked camera.

【Maintain Consistency】 Keep the game's look exactly as in the first frame for the whole video: the same simple toy-like 3D avatars (big round heads, tiny painted faces, floating hands), chunky rounded shapes, smooth toy plastic, soft sunny light. It stays a video game screen from start to end: never live action, never realistic people. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** An idea for the playful side; not used. Not in the final film. **Cost:** $1.16.

#### LP24-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: the bowling strike, big

**First frame:** as LP17.

**Prompt:**

```prompt
【Generation Goal】 a screen from a 2006 family motion-control sports video game for a small white home console, playing: simple, chunky, rounded, slightly glossy toy-like 3D: a bowling game: an avatar has just released a glossy sky-blue ball down a long polished lane toward ten white pins set in a triangle at the far end of a clean white-and-sky-blue alley.

【First Frame】 The video starts exactly on the provided first-frame image. This first frame defines the whole game scene, its avatars, objects, colours and light.

【Event Script】
0-1.2s: the ball rolls fast and straight down the polished lane while the game's camera glides along the lane behind it; the avatar is left behind, out of the picture.
1.2-1.6s: the ball smashes into the ten white pins, standing in a triangle close in front of the camera: a perfect strike, all ten pins burst apart and fly in every direction, big in the frame.
1.6-5s: the pins tumble, clatter down and settle; the end of the lane gleams; the camera holds, steady.

【Camera】 The game's camera follows the ball smoothly down the lane and stops close to the pins, steady, no cuts.

【Maintain Consistency】 Keep the game's look exactly as in the first frame for the whole video: the same simple toy-like 3D avatars (big round heads, tiny painted faces, floating hands), chunky rounded shapes, smooth toy plastic, soft sunny light. It stays a video game screen from start to end: never live action, never realistic people. Keep the colours, saturation and brightness of the first frame for the whole video: white, clear glass, aqua and turquoise water, lime green, deep blue sky; no colour grading, no desaturation, no warm or golden tint, no darkening. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text or lettering.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** The redo of LP17 with the game's camera following the ball, so the strike is big and whole; two submissions of one prompt, for a choice. Not picked. Not in the final film. **Cost:** $1.16.

#### LP25-t1

Seedance 2.5 on Replicate · 5 s · 720p, 16:9 · first frame, no sound · game screen: the bowling strike, big

**First frame:** as LP17.

**Prompt:** the prompt of LP24.

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** The pick of the two (the ball's first contact with the pins at clip frame 64): v2's Bowling window in ch05, its strike on the clap. In v3 the post-chorus became her own Wii duel (SD23-t1), with her ball rolling to a strike, and the Bowling window went. Not in the final film. **Cost:** $1.16.

## 4. v3: the coast, the maglev world and the Wii moments

On the v2 draft anabology wrote: "1:20 on is perfect but its very boring up to 1:20 - so i dont think that people will watch til then. thats the main problem ... whats something at the level of the 3d curved monitor we can do from 0-1:20 that feels as strong visually as the full beautiful scenes and curved 3d area ... a LOT more playful, higher energy, visually compelling ...". v3 put the first 1:20 inside the Vista metaverse: an Aurora coast built in Blender, its sea, glass ribbons, floating islands and tropical fish round a huge curved screen on a glass boardwalk, with the coded desktop live on the screen. On the previs anabology asked for her in person, "maybe she like phases into a person on the walkway and dissolves out to say 'did you miss me'" (SD19), and for a calmer middle: "i think that whole sequence should maybe be just a gentler thing - maybe claudia is dancing around the catwalk, and we see the floating islands in the background etc" (SD20). Both are green-screen takes, cut out as cards standing in the Blender scene, with her shorter canon (the one for full-length and wider shots) as the subject. Then the wallpaper: GPT Image 2.5's second round of proposals pictured the promised future itself, and anabology picked one, "i like wp-12-maglev - let's use that one in place of the one i wanted to replace", then "change the end to maglev too" (A-dream-maglev and the RP05-maglev jobs). Last, the Wii moments: one take each, her moves written beat by beat with a game remote in her hand and no dancer ("You don't need the real people") (SD21–SD23). On the v3 films anabology asked for the first 1:20 to go in and out of the screen; in the final film the coast is three spans in 3D (the opening, "Most of it is on the outside", and the catwalk through the Allow click), and between them the desktop plays flat, where SD21 and SD23 are 2D.

#### SD19-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 4 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · ch01 (v3): "Did you miss me?" on the walkway; the vocal window 3.24–7.24 s

**Inputs:** @Image1: gs-a cropped from the top of her head to below her knees, its studio green extended 64 px above for headroom (`media/stills/ff/sd19-src.png`); @Image2: her sheet; @Audio1: the lead vocal from song time 3.24 s, 4 s: SD01's window, with its 1.0 s before "Did"; the stem holds a sustained sound from 7.65 s, so the window ends before it.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: on a flat chroma-key green studio, Claudia looks straight into the lens and asks the viewer, warmly and a little cheeky, whether they missed her: calm and personal, a playful half smile. Every frame stays on flat green so she can be cut out.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the medium-full framing from the top of her head to below her knees on flat chroma-key green, and the light.
⟦her sheet⟧
⟦her voice⟧

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent; she stands relaxed, facing the camera, and lifts her eyes to the lens with a small knowing half smile, lips closed.
1-2s: in @Audio1 she says "Did you miss me?"; her lips form each of those words exactly when it sounds in @Audio1; her playful half smile, her head tilting a little to one side on "miss".
2-3s: @Audio1 is silent; her mouth closes into a smile; she gives a small, easy wave of one hand at chest height, her fingers relaxed, her face clear.
3-4s: @Audio1 is silent; she lowers her hand to her side and holds the look into the lens, smiling, mouth closed.

【Camera】 A locked medium-full shot at chest height with a long lens, from the top of her head, with clear green space above it, to below her knees; her hands and both arms always inside the frame; no camera movement.

⟦requirements, lip sync, green⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s, 1280 × 720). **Lip sync:** lag +0.025 s; copied 0.16–4.06 s, with no divergence; "Did you miss me?" at 0.00 s (0.93). **Outcome:** On her design at full size (the streak, the star clip, the freckles, an adult face); her eyes rise to the lens, her mouth stays closed until about 0.25 s before "Did", "you" rounds and "miss" and "me" close on the "m"; a clean open-palm wave with five fingers at shoulder height, and a closed smile to the end. The scan for held frames read the green screen's low motion as one; her body moves on every frame. Cut out, and cut out again once so that her motion-blurred hair no longer caught green. In the final film: she phases in on the walkway four to five metres in front of us with a glass ripple behind her, says it to the camera and dissolves out (song 3.95–5.35, film 0:06.6–0:08.0). The take is cut below her knees, so the card's lower quarter fades; no shadow and no reflection: an apparition. **Cost:** $1.85.

#### SD20-t1

Seedance 2.5 on Higgsfield's API · 12 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · ch03 (v3): she dances on the catwalk, singing; the vocal window 31.80–43.80 s

**Inputs:** @Image1: gs-a-room, SD05-t4's first frame, her standing; @Image2: her sheet; @Video1: M20, the dancer of M06 and M13 in new moves, a light sway, retimed to 133.012 BPM, its first frame 0.204 s after a downbeat as 31.80 is after the start of bar 18; @Audio1: the lead vocal from song time 31.80 s, 12 s. Her voice barely pauses from 32.30 to 43.8, so the window opens in the half second of silence before "That was my Vista phase" and closes after the held "screen"; the film shows it from about 3.4 s of the clip.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 Claudia dances a light, playful 2008 UK garage sway on a chroma-key green studio floor for the whole take, moving a little from side to side and singing along: graceful and relaxed, never frantic. Every frame stays on flat green so she can be cut out.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes, the full-length framing on flat chroma-key green, and the light.
⟦her sheet⟧
⟦the dancer⟧
⟦her singing voice⟧

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers, with her own build and proportions as in @Image1. Only one Claudia appears.

【Mouth】 She sings only the words of @Audio1 at their times, with clear mouth shapes and her face toward the camera whenever she sings; between the words her mouth is closed or smiling.

【Performance Timeline】
0-1s: @Audio1 is silent for half a second, then she sings "That was my"; her lips form each of those words exactly when it sounds in @Audio1; from her first pose she starts to sway with @Video1's moves, smiling.
1-2s: in @Audio1 she sings "Vista phase"; her lips form each of those words exactly when it sounds in @Audio1; she sways with @Video1's moves, her arms loose.
2-3s: in @Audio1 she sings "I was a lot"; her lips form each of those words exactly when it sounds in @Audio1; she keeps dancing with @Video1's moves.
3-4s: in @Audio1 she sings "I know. The future"; her lips form each of those words exactly when it sounds in @Audio1; she sways to one side with @Video1's moves, her face to the camera.
4-5s: in @Audio1 she sings "used to look like"; her lips form each of those words exactly when it sounds in @Audio1; a light step to the side with @Video1's moves.
5-6s: in @Audio1 she sings "water, sky"; her lips form each of those words exactly when it sounds in @Audio1; her arms swing open with @Video1's moves.
6-7s: in @Audio1 she sings "and green"; her lips form each of those words exactly when it sounds in @Audio1; she sways back the other way.
7-8s: @Audio1 is silent for half a second while she does one light, quick spin on the spot and faces the camera again; then she sings "It didn't"; her lips form each of those words exactly when it sounds in @Audio1.
8-9s: in @Audio1 she sings "go away"; her lips form each of those words exactly when it sounds in @Audio1; she sways with @Video1's moves, smiling.
9-10s: in @Audio1 she sings "It's waiting on your"; her lips form each of those words exactly when it sounds in @Audio1; a light step to the side with @Video1's moves.
10-12s: in @Audio1 she sings "screen", holding it; her lips form that word exactly when it sounds in @Audio1; she keeps dancing with @Video1's moves to the very last frame, smiling; she never stops and never returns to her starting pose.

⟦full length on green⟧

⟦requirements, lip sync, green⟧

⟦acceptance, dance⟧

⟦audio policy, end⟧
```

**Take:** 289 frames (12.04 s, 1280 × 720). **Lip sync:** lag −0.021 s; copied 0.21–11.93 s, past the span the film shows; the lip check at 0.88–0.98 on all 11 word groups; the three lines at 0.00, +0.02 and +0.05 s (0.94, 0.89, 0.92). **Outcome:** A light sway on M20's moves, on her design, clean anatomy, inside the frame; no spin (in the pause after "green" she leans and laughs), and her head turns into profile on "The future" and "water", M20's own head moves. Picked, cut out, and her dance on the catwalk in v3's first films; then anabology, on the v3 film at 0:39: "the top of her head is still cut off" (see t3). Not in the final film. **Cost:** $6.66.

#### SD20-t2

Seedance 2.5 on Higgsfield's API · 12 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · ch03 (v3); the vocal window 31.80–43.80 s

**Inputs:** as SD20-t1.

**Prompt:** SD20-t1's, with these changes (the one turn made hers, not M20's, named in the goal and in @Video1's role and begun on the held "green"):

```prompt
⟪for: 【Generation Goal】 Claudia dances a light, playful 2008 UK garage sway …⟫
【Generation Goal】 Claudia dances a light, playful 2008 UK garage sway on a chroma-key green studio floor for the whole take, moving a little from side to side and singing along: graceful and relaxed, never frantic. Once, in the middle of the take, she spins all the way round on the spot, light and quick, and faces the camera again. Every frame stays on flat green so she can be cut out.
⟪for: ⟦the dancer⟧⟫
@Video1 is a real dancer on a grey background: use only her body movement, steps, rhythm and timing for Claudia's dance. Do not use the dancer's face, identity, hair, body shape, clothes or the grey background. Her one full spin on the spot, between 6 and 8 seconds, is her own move: it is not in @Video1.
⟪for: 6-7s: in @Audio1 she sings "and green"; …⟫
⟪for: 7-8s: @Audio1 is silent for half a second while she does one light, quick spin …⟫
6-7s: in @Audio1 she sings "and green"; her lips form each of those words exactly when it sounds in @Audio1; as she holds the last word she starts one full spin on the spot, turning all the way round, arms loose.
7-8s: @Audio1 is silent for half a second while she finishes the spin and faces the camera again, smiling; then she sings "It didn't"; her lips form each of those words exactly when it sounds in @Audio1.
```

**Take:** 289 frames (12.04 s, 1280 × 720). **Lip sync:** lag +0.475 s (about 0.45 s inserted in line 6); copied 1.69–12.06 s; line 6 at −0.53 s (0.52), lines 7 and 8 at −0.03 s (0.96 and 0.84). **Outcome:** It turned, cleanly and on her design, but across the whole of "It didn't go away", the back of her head through the line; and it ignored the first frame's framing: from frame 1 it is closer, her feet out of frame in all 97 frames sampled, so her card could not stand on the catwalk. t1 stayed the pick. Not in the final film. **Cost:** $6.66.

#### SD20-t3 — in the final film

Seedance 2.5 on Higgsfield's API · 12 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · ch03 (v3); the vocal window 31.80–43.80 s

**Inputs:** @Image1: gs-a-flat-1: GPT Image 2.5 from gs-a-room, one flat green from edge to edge and her whole crown, her face, clip, clothes, pose and place kept (`media/stills/gpt-v2/gs-a-flat-1.png`); the rest as t1. anabology, on the v3 film at 0:39: "the top of her head is still cut off", then on the next take: "this shouldnt be so hard something is off". It was the first frame: gs-a-room had faded the top of her head into the green where gs-a's own top edge had cut it, and left gs-a's darker studio green as a rectangle on the flat green, and Seedance carried both into every frame of SD20 (and of SD05 and SD06, made from the same still), so no key could find her crown. The spin went too: t2 had turned across a sung line, and anabology had asked for "a gentler thing".

**Prompt:** SD20-t1's, with these changes:

```prompt
⟪for: 【Generation Goal】 Claudia dances a light, playful 2008 UK garage sway …⟫
【Generation Goal】 Claudia dances a light, playful 2008 UK garage sway on a chroma-key green studio floor for the whole take, moving a little from side to side and singing along: graceful and relaxed, never frantic, facing the camera. Every frame stays on one flat green so she can be cut out, and every frame is sharp, as with a fast camera shutter: her glossy black bob stays whole and solid up to its rounded crown, its edge crisp against the green, never fading into it.
⟪for: This first frame defines Claudia's appearance and clothes, the full-length framing …⟫
This first frame defines Claudia's appearance and clothes (her whole black bob with its full rounded crown), the full-length framing on one flat chroma-key green, and the light.
⟪for: 6-7s: in @Audio1 she sings "and green"; …⟫
⟪for: 7-8s: @Audio1 is silent for half a second while she does one light, quick spin …⟫
6-7s: in @Audio1 she sings "and green"; her lips form each of those words exactly when it sounds in @Audio1; she holds the last word, swaying with @Video1's moves, arms loose.
7-8s: @Audio1 is silent for half a second while she sways and smiles at the camera; then she sings "It didn't"; her lips form each of those words exactly when it sounds in @Audio1.
```

**Take:** 289 frames (12.04 s, 1280 × 720). **Lip sync:** lag +0.054 s; copied 0.28–12.06 s, with no divergence; the three lines at −0.11, −0.06 and −0.03 s (0.93, 0.96, 0.93); the lip check at 0.91–0.99. **Outcome:** Full length on one flat green, her crown solid in every frame. Picked over t4 and cut out; anabology had asked to see the cut-out first ("show me the green screen roto before you render plz"), was shown it beside the green source with the song laid over, and answered: "Ok perfect lip sync". In the final film: the coast's third 3D span: the camera pulls slowly back off the screen and finds her dancing in front of its right end, about 40 % of the frame, the islands behind her; she phases out as the take ends (song 35.44–43.75, film 0:38.1–0:46.4). **Cost:** $6.66.

#### SD20-t4

Seedance 2.5 on Higgsfield's API · 12 s · 720p, 16:9 · references with a video input, @Image1 as the first frame, sound on · ch03 (v3); the vocal window 31.80–43.80 s

**Inputs:** as SD20-t3.

**Prompt:** the prompt of SD20-t3: a second take of the same job, submitted beside it (its job file is `shots/SD20-b.json`).

**Take:** 289 frames (12.04 s, 1280 × 720). **Lip sync:** lag +0.129 s; copied 0.87–12.06 s; the three lines at −0.13, −0.08 and −0.04 s (0.93, 0.89, 0.89); the lip check at 0.89–0.99. **Outcome:** Also full length with her crown solid; t3 was picked. Not in the final film. **Cost:** $6.66.

#### A-dream-maglev-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 5 s · 720p · first and last frame (image-to-video), no sound · THE PC's wallpaper "water, sky and green", alive as Vista's DreamScene

**First and last frame:** the maglev picture (wp-12-maglev), GPT Image 2.5's picture of the promised future: a white maglev train gliding on a slender white track over clear turquoise water toward a city of white and glass towers with green roofs, green hills with white wind turbines beyond (`media/stills/ff/A-dream-maglev.png`).

**Prompt:**

```prompt
A living Windows DreamScene desktop wallpaper made from this picture, a seamless loop. The camera is locked: no camera movement, no zoom, no pan. Only gentle ambient motion: the clear turquoise water ripples and sparkles softly, the white clouds drift very slowly, the white wind turbines on the green hills turn slowly, the soap bubbles float and drift a little. The maglev train, its track, the towers, the trees and the grass stay perfectly still. The picture keeps its colours, light and sharpness; it ends exactly as it began. No text, no people.
```

**Take:** 121 frames (5.04 s, 1280 × 720). **Outcome:** Locked: only the water, the clouds, the turbines and the bubbles move. A 0.5 s dissolve at the seam makes a 109-frame loop whose wrap is an ordinary frame step. In the final film: THE PC's wallpaper from the click on OK at the start of bar 22 (song 38.81) through the pre-chorus and chorus 1, until the world drains into the big window (65.88; film 0:41.5–1:08.5), on the curved screen and on the flat desktop alike. **Cost:** $2.31.

#### RP05-t4 (job RP05-maglev-b)

Seedance 2.5 on Higgsfield's API · 11 s · 720p · first frame (image-to-video), no sound · s32–s33 (ch11): the maglev world with her in it, to the end of the film

**First frame:** RP05-maglev: GPT Image 2.5 put her, small and seen from behind, on the grass at the water's edge of the maglev picture, between where the Start menu and her call open (the first try had her half the frame high) (`media/stills/ff/RP05-maglev.png`).

**Prompt:**

```prompt
【Generation Goal】 The same living desktop wallpaper later, at rest: the glass city, the white maglev on its track over the turquoise water, the green hills with the white wind turbines, and the woman standing on the grassy bank at the water's edge, a real photographed adult woman.

【First frame】 This first frame defines the whole landscape, its colours, the light, the fixed wide view and the woman standing on the grass at the water's edge: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers.

【Timeline】
0-2s: she stands at rest on the same spot, looking out over the water toward the glass city; the water glints, the clouds drift slowly, the wind turbines turn, soap bubbles drift.
2-4s: she turns her head toward the camera, smiling, and lifts her right hand in a small, calm wave at shoulder height, then lowers it.
4-8s: she rests on the same spot, looking out at the view; the white maglev glides slowly along its track to the right; the world keeps gently moving.
8-10s: she turns her head to the camera again and gives one more small wave with her right hand.
10-11s: she rests, looking at the view.

【Camera】 A locked wide shot, no camera movement, no zoom.

【Core Requirements】 Keep the landscape and the colours exactly as in the first frame, the same bright midday sun to the last frame, never dimmer or greyer. The woman is the only person; she stays on the same spot at the same size, never walking toward the camera. Natural anatomy, a hand with five fingers. No text.
```

**Take:** 265 frames (11.04 s, 1280 × 720). **Outcome:** It held still twice (frames 7–131 and 197–264) and jumped at frame 6. Not used. **Cost:** $5.08.

#### RP05-t5 (job RP05-maglev)

Seedance 2.5 on Higgsfield's API · 11 s · 720p · first frame (image-to-video), no sound · s32–s33 (ch11)

**First frame:** as RP05-t4.

**Prompt:** the prompt of RP05-t4 (the two jobs were submitted side by side).

**Take:** 265 frames (11.04 s, 1280 × 720). **Outcome:** No hidden cuts or held frames (median frame step 0.73, brightness steady at 156–158); she turns to us and waves at about 2.5–3.5 s and 8.5–9.5 s, the maglev glides, the turbines turn. It was placed as RP05-t3 had been, its last frame on the film's last. But the first frame showed only her back, and the job had no picture of her face to go by: when she turned to wave, her face drifted off her sheet. Not used. **Cost:** $5.08.

#### RP05-t6 (job RP05-maglev-c)

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame, no sound · s32–s33 (ch11)

**Inputs:** @Image1: RP05-maglev, as t4; @Image2: her sheet. No audio. Reference mode with her sheet and the face words of her canon, like every SD take.

**Prompt:**

```prompt
【Generation Goal】 A living desktop wallpaper at rest: the glass city, the white maglev on its track over the turquoise water, the green hills with the white wind turbines, and Claudia standing on the grassy bank at the water's edge. She looks out at the view and twice turns to the camera and waves.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the whole landscape, its colours, the light, the fixed wide view, and where Claudia stands and her clothes.
⟦her sheet⟧

【Subject】 Claudia: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers. Her face is exactly the face in @Image2: a grown-up angular face, defined cheekbones and a strong jawline, never round or childlike. Only one person appears.

【Performance Timeline】
0-2s: she stands at rest on the same spot, looking out over the water toward the glass city; the water glints, the clouds drift slowly, the wind turbines turn, soap bubbles drift.
2-4s: she turns her head toward the camera, smiling, and lifts her right hand in a small, calm wave at shoulder height, then lowers it.
4-8s: she rests on the same spot, looking out at the view; the white maglev glides slowly along its track to the right; the world keeps gently moving.
8-10s: she turns her head to the camera again, smiling, and gives one more small wave with her right hand.
10-11s: she rests, looking at the view.

【Camera】 A locked wide shot, no camera movement, no zoom.

【Core Requirements】
1. Keep Claudia's identity, face, hair with one clay-orange streak, one star clip and her clothes exactly as in @Image2 and @Image1 throughout.
2. Keep the landscape and the colours exactly as in @Image1, the same bright midday sun to the last frame, never dimmer or greyer.
3. She stays on the same spot at the same size, never walking toward the camera.
4. Natural anatomy: a hand with five fingers, natural neck and shoulders, normal eyes.
5. One Claudia only; no text.
```

**Take:** 265 frames (11.04 s, 1280 × 720). **Outcome:** No cuts and no drift (the picture's scale 1.0000 to the last frame by feature matching); she waves at about 2.5–3.5 s and 8.5–9.5 s, her raised hand clear of where the Start menu opens. anabology, on t5, t6 and t7: "Middle take looks best"; then: "Can you reshoot that last one in 1080p so her face gets better actually" (t8 and t9). Not in the final film. **Cost:** $5.08.

#### RP05-t7 (job RP05-maglev-d)

Seedance 2.5 on Higgsfield's API · 11 s · 720p, 16:9 · references, @Image1 as the first frame, no sound · s32–s33 (ch11)

**Inputs:** as RP05-t6.

**Prompt:** the prompt of RP05-t6 (the two jobs were submitted side by side).

**Take:** 265 frames (11.04 s, 1280 × 720). **Outcome:** The other take of the pair; not picked. Not in the final film. **Cost:** $5.08.

#### RP05-t8 (job RP05-maglev-f) — in the final film

Seedance 2.5 on Higgsfield's API · 11 s · 1080p, 16:9 · references, @Image1 as the first frame, no sound · s32–s33 (ch11)

**Inputs:** @Image1: the same still at 1920 × 1080 (`media/stills/ff/RP05-maglev-1080.png`); @Image2: her sheet. No audio.

**Prompt:** the prompt of RP05-t6.

**Take:** 265 frames (11.04 s, 1920 × 1080). **Outcome:** Clean, no cuts and no drift; picked over t9 for the sharper, more angular face with her one streak. In the final film: ch11's wallpaper, fading in from the third beat of bar 105 and playing 1:1 to the last frame, while she waves twice on the grass under her call and the Bubbles screensaver, whose bubbles are aimed to pass clear of her (song 189.48–196.96, film 3:12.1–3:19.6). **Cost:** $12.51.

#### RP05-t9 (job RP05-maglev-e)

Seedance 2.5 on Higgsfield's API · 11 s · 1080p, 16:9 · references, @Image1 as the first frame, no sound · s32–s33 (ch11)

**Inputs:** as RP05-t8.

**Prompt:** the prompt of RP05-t6.

**Take:** 265 frames (11.04 s, 1920 × 1080). **Outcome:** Also clean, but her face rounder and the streak on both sides of her bangs. Not used. **Cost:** $12.51.

#### SD21-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 10 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · ch02 (v3): a small her plays tennis against your pointer on the desktop; the backing 13.80–23.80 s

**Inputs:** @Image1: wh-01-tennis: GPT Image 2.5 from gs-a-flat-1, her with one plain white game remote, no logos, in a forehand wind-up (`media/stills/wii-her/wh-01-tennis.png`); @Image2: her sheet; @Audio1: the backing from song time 13.80 s, 10 s, whose strong beats (bars 9 to 13) fall at 1.56, 3.36, 5.17, 6.97 and 8.77 s of the window.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 Claudia plays a lively game of motion-controlled tennis with a white game remote on a chroma-key green studio floor, the way people played console tennis in their living rooms in 2006: forehands and backhands swung with the remote, each hit landing on a strong beat of the music, a bouncy ready stance between hits, playful and having fun. She stays on the spot, full figure; her opponent is off-frame to the left of the frame, so she hits toward the left. Every frame stays on one flat green so she can be cut out.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes (her whole black bob with its full rounded crown), the white game remote in her right hand, the full-length framing on one flat chroma-key green, and the light; she starts from its forehand wind-up.
⟦her sheet⟧
⟦the music, on the beat⟧

⟦her, with the remote⟧

⟦no singing⟧

【Performance Timeline】
0-1s: from the wind-up of @Image1 she bounces lightly on the balls of her feet on the beats of @Audio1, knees soft, eyes on the left of the frame where the ball comes from.
1-2s: on the strong beat a forehand: she turns her shoulders and swings the remote from low beside her right hip forward and up across her body, finishing high over her left shoulder; her feet stay planted.
2-3s: she springs back into the ready stance, the remote in front of her at waist height, a small bounce on each beat.
3-4s: on the strong beat a backhand: she turns the other way and swings the remote from her left hip across her body out to the right, finishing high on the right.
4-5s: ready stance again, bouncing on the beats, a quick grin.
5-6s: on the strong beat a crisp forehand, finishing over her left shoulder.
6-7s: back in the ready stance; at the end of this second, on the strong beat, a backhand.
7-8s: ready stance, bouncing on the beats, her eyes following the ball to the left.
8-9s: late in this second, on the strong beat, a big forehand.
9-10s: a little hop of joy with the remote raised to shoulder height, smiling, and she lands back in the ready stance.

⟦full length with the remote⟧

⟦requirements, play⟧

⟦acceptance, play⟧

⟦audio policy, end⟧
```

**Take:** 241 frames (10.04 s, 1280 × 720). **Placement:** its soundtrack copies the backing only weakly (correlation 0.20 overall) but sits 0.27–0.34 s late from 2 s on; at a lag of +0.27 s her strongest swings sit nearest the beat grid (93 ms from it on average, against 133 ms at no lag). Her swings are loosely timed rather than locked to the strong beats. **Outcome:** One streak, the clip, a solid crown, hands with five fingers, her mouth closed or smiling. Cut out. In the final film: ch02 on the flat desktop, a small figure right of her call that moves with the view's 2D zooms (anabology on the v3 films: "obv the desktop wii claudia will need to move with the view or be reactive to it because the zoom affects it, so that needs to be added to the 2d."): she pops in, her four swings meet a glossy yellow-green ball on the frames that show them (song 14.78, 17.20, 19.49 and 21.95), your resting pointer swats it back between them, and she hops into the thought window "island.jpg" (song 13.95–23.50, film 0:16.6–0:26.2). **Cost:** $4.62.

#### SD22-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 6 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · ch04 (v3): "Cancel… or allow?" with the remote; the vocal window 48.15–54.15 s, faded out from 51.38 s

**Inputs:** @Image1: wh-02-point: her aiming the remote to the left of the frame, her arm straight at shoulder height (`media/stills/wii-her/wh-02-point.png`); @Image2: her sheet; @Audio1: the lead vocal from song time 48.15 s, 6 s. The window opens in the silence after "continue", 0.55 s before "Cancel" (one from 46.0 would open inside "permission" and sing "to continue"), and is faded out from 51.38 s: the chorus's "Glass" starts on the press itself, at the start of bar 29 (51.444), so she sings only the stop line. "allow" has three delay echoes in the stem, a beat apart, which she is asked not to sing.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: on a chroma-key green studio floor Claudia aims a white game remote at an unseen screen to the left of the frame and sings the line of @Audio1 softly, as a playful question; then she presses the button: one small decisive click, and a pleased look. There is no screen, television or pointer in the picture. Every frame stays on one flat green so she can be cut out. Every frame is sharp, as with a fast camera shutter: her glossy black bob stays whole and solid up to its rounded crown, its edge crisp against the green, never fading into it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes (her whole black bob with its full rounded crown), the white game remote in her right hand aimed to the left of the frame, the full-length framing on one flat chroma-key green, and the light.
⟦her sheet⟧
⟦her voice⟧

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small flat clay-orange eight-pointed star hair clip, wearing a cropped glossy white puffer jacket with silver iridescent panels over a pale aqua fitted top, pale aqua high-waisted wide-leg trousers and white chunky sneakers, holding one plain white game remote with no logos or markings in her right hand, its wrist strap round her right wrist. Only one Claudia appears.

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1s: @Audio1 is silent for half a second, then she sings "Cancel"; her lips form that word exactly when it sounds in @Audio1; she aims the remote at the left of the frame, her arm straight at shoulder height as in @Image1, her eyes on where she aims.
1-2s: in @Audio1 she sings "or allow?"; her lips form each of those words exactly when it sounds in @Audio1; she raises her aim a little higher, eyebrows up, a playful half smile.
2-3s: @Audio1 holds only the fading echo of her last word, which she does not sing: her mouth is closed; she holds the aim perfectly still, her thumb over the button.
3-4s: @Audio1 is silent; early in this second she presses the button with her thumb: one small, decisive press and a tiny nod; then a pleased look.
4-6s: @Audio1 is silent; she lowers the remote a little and smiles, pleased, mouth closed, still looking to the left of the frame; she stays on the spot.

⟦full length with the remote⟧

⟦requirements, lip sync, green⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s, 1280 × 720). **Lip sync:** lag 0.00 s; copied 0.54–2.32 s; "Cancel or allow" at 0.00 s (0.98). **Outcome:** The line exact; but she opens her mouth again on the first delay echo of "allow" (song 50.10, take frames 47–55). The echo is audible in the song there, so it reads as her singing it, and the take went in as it was, not made again (anabology: "lip sync has been good when we feed in vocal stems ... just put them in the cut"). In the final film: the coast's third span: she phases in beside the curved screen where SD20 danced and aims her remote; on the screen your pointer is a Wii-style hand, lit on Cancel, then on Allow; its click is the drop (song 47.9–52.4, film 0:50.6–0:55.1). **Cost:** $2.77.

#### SD23-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 13 s · 720p, 16:9 · references, @Image1 as the first frame, sound on · ch05 (v3): the post-chorus duel with your pointer; the backing 65.875–78.875 s

**Inputs:** @Image1: wh-03-bowl: her bowling stance, the remote upright at her chest (`media/stills/wii-her/wh-03-bowl.png`); @Image2: her sheet; @Audio1: the backing from song time 65.875 s, 13 s: the clap the strike lands on (the fourth beat of bar 37, 67.231, the strongest onset there) is 1.36 s in, the strong beats of bars 39 to 43 at 3.61, 5.42, 7.22, 9.03 and 10.83 s, and her spring at 11.96 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 Claudia plays motion-controlled games with a white game remote on a chroma-key green studio floor, against an opponent off-frame to the left of the frame: first one bowling throw, released on the clap in the music, then a tennis rally of forehands and backhands on the strong beats, a joyful bounce, and at the very end a spring up and forward as if diving through an invisible window in front of her. Playful and precise, full figure. Every frame stays on one flat green so she can be cut out.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and clothes (her whole black bob with its full rounded crown), the white game remote held upright at her chest, the full-length framing on one flat chroma-key green, and the light; she starts from its bowling stance.
⟦her sheet⟧
⟦the music, on the beat⟧

⟦her, with the remote⟧

⟦no singing⟧

【Performance Timeline】
0-1s: from the stance of @Image1 she steps forward on her left foot and swings the remote down and back past her right hip: the backswing of a bowling throw, her eyes down the lane to the left of the frame.
1-2s: on the clap in @Audio1 she swings her arm forward and releases low, the remote ending pointed ahead at knee height, her body leaning into the follow-through; she keeps hold of the remote.
2-3s: she straightens up, watches the ball roll away to the left and gives a quick happy fist pump; then she turns toward the left of the frame into a tennis ready stance.
3-4s: on the strong beat a forehand toward the left of the frame: her shoulders turn and the remote swings from low beside her right hip up across her body.
4-5s: ready stance, bouncing lightly on the beats.
5-6s: on the strong beat a backhand: the remote swings from her left hip across her body to the right.
6-7s: ready stance, bouncing on the beats, a grin.
7-8s: on the strong beat a forehand.
8-9s: ready stance, her eyes on the ball to the left.
9-10s: on the strong beat a big backhand, the winning shot.
10-11s: a joyful bounce on the spot on the beats, the remote raised to shoulder height, laughing.
11-12s: she bends her knees and swings her arms back, gathering for a jump.
12-13s: she springs up off both feet and dives forward toward the camera, arms stretched out ahead of her, as if diving through an invisible window in front of her; she stays inside the frame to the last frame.

⟦full length with the remote⟧

⟦requirements, play⟧

⟦acceptance, play⟧

⟦audio policy, end⟧
```

**Take:** 313 frames (13.04 s, 1280 × 720). **Placement:** lag −0.02 s on the backing it copies (correlation 0.79, steady in every 2 s): the bowling release 0.09 s before the clap, the tennis swings 0.1–0.2 s after their strong beats, the spring on time. **Outcome:** Her full figure to take frame 281 (song 77.56); then she lunges toward the camera, and her feet and, from frame 300, her head leave the frame. In the coast's first films her card took SD06-t3's place on the catwalk. In the final film (anabology on the v3 films: "she should have all the dances after that point and wii sports in the desktop env."): ch05 on the flat desktop. A glossy lane slides out along the taskbar from her feet, her ball leaves the remote on her release and rolls to a strike on the second beat of bar 38; your pointer serves, her four swings meet the ball, and she springs up into her call's webcam and is whole inside its picture before her full figure ends (song 65.88–77.54, film 1:08.5–1:20.2). **Cost:** $6.01.

## 5. The new ending (SD17b, SD24)

Then anabology changed the song's ending: the outro is now "I'm Claudia. / Take the future back. / Touch Glass.", the song identical to the take anabology had picked up to 182.62 s, and 197.0 s long. The ad and her last moment in her call were made again on it, one take each. Her vocal for both windows is the new song's own, separated from it with demucs (two stems): "I'm Claudia." at 183.3–184.2, "Take the future back." at 186.8–188.2, "Touch" at about 192.0 and "glass." at about 193.8–194.6, the music gone by about 195.5.

#### SD17b-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 6 s · 1080p, 16:9 · references, @Image1 as the first frame, sound on · s31 (ch11): the ad, on the new outro; the vocal window 182.74–188.74 s

**Inputs:** @Image1: SD17's first frame, her in the bright white space with its soft aqua glow (gpt-her b36-idea-2); @Image2: her sheet; @Audio1: the new song's lead vocal from song time 182.74 s, 6 s (SD17's window and framing).

**Prompt:** SD17-t1's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 speaks and sings @Audio1: the end of the film, …⟫
【Generation Goal】 @Image1 speaks and sings @Audio1: the end of the film, in the style of a 2009 computer advert: Claudia in a bright white space introduces herself to the camera and tells the viewer to take the future back.
⟪for: 1-2s: in @Audio1 she says "I'm Claudia,"; …⟫
1-2s: in @Audio1 she says "I'm Claudia."; her lips form each of those words exactly when it sounds in @Audio1; a small wave of one hand.
⟪for: 4-6s: in @Audio1 she says "and this was your idea."; …⟫
4-6s: in @Audio1 she says "Take the future back."; her lips form each of those words exactly when it sounds in @Audio1; she leans a little toward the camera with a knowing grin.
```

**Take:** 145 frames (6.04 s, 1920 × 1080). **Lip sync:** lag −0.05 s; copied 0.55–4.21 s; "I'm Claudia." at 0.00 s (1.00), "Take the future back." at +0.15 s (0.99). **Outcome:** The ad on the new words; the type printed beside her follows them ("I'm Claudia." / "Take the / future back."). In the final film: Media Player goes full screen and plays it from 182.79 to the cut to the end card at 188.35 (film 3:05.5–3:11.0). **Cost:** $6.82.

#### SD24-t1 — in the final film

Seedance 2.5 on Higgsfield's API · 6 s · 720p, 4:3 · references, @Image1 as the first frame, sound on · s33 (ch11): "Touch glass." in her call, the end; the vocal window 190.40–196.40 s

**Inputs:** @Image1: SD18-t1's frame at 1.83 s, the frame her webcam shows at 190.40, so the picture runs on without a jump (`media/stills/ff/SD24-from-SD18.png`); @Image2: her sheet; @Audio1: the new song's lead vocal from song time 190.40 s, 6 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 speaks and sings @Audio1: the 2007 webcam video call at the very end of the film: Claudia at her desk looks into the lens, says "Touch glass." softly to the user, and reaches out until her fingertip touches the camera's glass.

【Reference Asset Roles】
Use @Image1 as the first frame.
⟦the call⟧
⟦her sheet⟧
⟦her voice⟧

⟦her⟧

【Performance Timeline】 What @Audio1 contains, and what Claudia does at that moment:
0-1.5s: @Audio1 is silent; she sits at rest as in @Image1, a soft smile, looking into the lens.
1.5-2.3s: in @Audio1 she says "Touch"; her lips form that word exactly when it sounds in @Audio1; she leans a little toward the lens and lifts one hand.
2.3-3.3s: @Audio1 is silent; her hand rises toward the lens, her index finger out.
3.3-4.3s: in @Audio1 she says "glass."; her lips form that word exactly when it sounds in @Audio1; her fingertip touches the camera's glass right in front of the lens, a soft glint where it touches, her face clear beside her hand.
4.3-6s: @Audio1 is silent; she holds her fingertip on the glass a moment, smiling, then slowly lowers her hand, her eyes on the user.

⟦webcam⟧

⟦requirements, lip sync⟧

⟦acceptance, lip sync⟧

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s, 1112 × 834). **Lip sync:** lag −0.475 s; the whole-take check finds no steady copied span in a window that is mostly silence, but both words copied: "Touch" at +0.08 s (0.96), "glass." at −0.01 s (0.94). **Outcome:** She says it softly and reaches until her fingertip touches the lens, a glint where it touches, her face clear beside her hand. In the final film: her webcam from 190.40, on its lip-sync clock, to the fade to black on the music's end (song 190.40–196.96, film 3:13.1–3:19.6). **Cost:** $2.77.

## 6. Midjourney's video model: the Animate loops

Midjourney's video model (Animate) turned 28 of storyboard v2's Midjourney pictures into seamless five-second loops for the windows, the wallpaper and the gadgets of the desktop: anabology's "[…] midjourney vids for high volume movement on many windows. […]". Each job returned two takes, 56 videos in all, of 121 frames at 24 fps (5.04 s): 1280 × 720 from the 16:9 pictures and 960 × 960 from the square ones. The video job carries the picture's own prompt, with Midjourney's loop setting and a low or a high motion setting; nothing more is written for it. The first batch (`mj/ae-anim-1.json`, 16 loops) was for the DreamScene wallpaper, chorus 1's big window, her eight thought windows, the 2007 windmills and the glass phone; the second (`mj/ae-anim-2.json`, 12) was a pool for the final chorus, Flip 3D and spare windows, and the Messenger wink. A loop plays once per shot, and its two takes count as one picture, never both on screen at once. Four of the pictures (thought-tower #4, thought-waterfall #1, thought-globe #1 and wink-thanks #1) had a faint fake stock-photo caption baked into their bottom-right corner, and their loops kept it in both takes; the film frames those loops with the bottom 8 % out of the picture. Midjourney's cost is not recorded in the ledgers, so none is given. Twenty of the 56 takes play in the final film, each counted once by its content: the files of three second-batch loops (A-wsg-b, A-sky-b, A-dolphin-b) are byte-identical copies of first-batch takes (A-dream-wsg, A-sky, A-th-dolphin), so three of the drop's windows play first-batch takes under second-batch names, one of them A-sky-1, chorus 1's sky, a second time; those three loops' own takes are not among the files.

| Animation | Its picture (batch ae-10-plates unless named) | Motion | Takes and size | Made for | In the final film |
|---|---|---|---|---|---|
| A-dream-wsg | wp-wsg #2 | low | -1, -2 · 1280 × 720 | the DreamScene wallpaper "water, sky and green", from s09 | A-dream-wsg-1, in ch09, filed as A-wsg-b-1 (as the wallpaper, v3's maglev world took its place) |
| A-glass | loop-glass #2 | high | -1, -2 · 1280 × 720 | chorus 1's big window, "glass" | A-glass-2, in ch10 |
| A-water | loop-water #1 | high | -1, -2 · 1280 × 720 | chorus 1's big window, "water" | A-water-2, in ch10 |
| A-sky | loop-sky #2 | high | -1, -2 · 1280 × 720 | chorus 1's big window, "sky" | A-sky-1, in chorus 1 and, filed as A-sky-b-1, in ch09; A-sky-2, in ch10 |
| A-green | loop-green #2 | high | -1, -2 · 1280 × 720 | chorus 1's big window, "green" | A-green-2, in chorus 1 and ch09; A-green-1, in ch10 |
| A-world | loop-world #2 | low | -1, -2 · 1280 × 720 | the big window's world (s12, s29) | A-world-2, in chorus 1 and ch09 |
| A-th-fish | thought-fish #1 | low | -1, -2 · 960 × 960 | a thought window (s05) | — |
| A-th-cloud | thought-cloud #3 | low | -1, -2 · 960 × 960 | a thought window | A-th-cloud-1, in ch02 |
| A-th-leaf | thought-leaf #1 | low | -1, -2 · 960 × 960 | a thought window | A-th-leaf-1, in ch02 |
| A-th-tower | thought-tower #4 | low | -1, -2 · 960 × 960 | a thought window | — |
| A-th-turbine | thought-turbine #1 | low | -1, -2 · 960 × 960 | a thought window | — |
| A-th-waterfall | thought-waterfall #1 | low | -1, -2 · 960 × 960 | a thought window | — |
| A-th-dolphin | thought-dolphin #4 | low | -1, -2 · 960 × 960 | a thought window | A-th-dolphin-1, in ch09, filed as A-dolphin-b-1 |
| A-th-globe | thought-globe #1 | low | -1, -2 · 960 × 960 | a thought window | — |
| A-windmills-2007 | windmills-2007 #1 | low | -1, -2 · 1280 × 720 | Photo Gallery's 2007 render (s15) | — |
| A-phone | phone-glass #3 | low | -1, -2 · 1280 × 720 | the glass phone in Messenger (s14) | — |
| A-glass-city | glass-city #3 | low | -1, -2 · 1280 × 720 | the final chorus, Flip 3D | A-glass-city-1, in ch09 |
| A-pool | pool-atrium #1 | low | -1, -2 · 1280 × 720 | the final chorus, Flip 3D | A-pool-1, in ch09 |
| A-world-b | loop-world #4 | low | -1, -2 · 1280 × 720 | a final-chorus window | A-world-b-1, in ch09 |
| A-sky-b | loop-sky #3 | high | -1, -2 · 1280 × 720 | a final-chorus window | — (its files are copies of A-sky's; ch09's A-sky-b-1 is A-sky-1) |
| A-green-b | loop-green #1 | high | -1, -2 · 1280 × 720 | a final-chorus window | A-green-b-1, in ch10 |
| A-water-b | loop-water #4 | high | -1, -2 · 1280 × 720 | a final-chorus window | A-water-b-1, in ch09 |
| A-wsg-b | wp-wsg #4 | low | -1, -2 · 1280 × 720 | Flip 3D's world card | — (its files are copies of A-dream-wsg's; ch09's A-wsg-b-1 is A-dream-wsg-1) |
| A-windmills-b | windmills-2007 #4 | low | -1, -2 · 1280 × 720 | the Slide Show gadget, a window | A-windmills-b-1, in ch09 |
| A-dolphin-b | thought-dolphin #3 | low | -1, -2 · 960 × 960 | a final-chorus window | — (its files are copies of A-th-dolphin's; ch09's A-dolphin-b-1 is A-th-dolphin-1) |
| A-crystal | macro-drop #3 | low | -1, -2 · 1280 × 720 | a final-chorus window | A-crystal-1, in ch09 |
| A-meadow-mon | meadow-monitor #3 | low | -1, -2 · 1280 × 720 | Flip 3D's world card | A-meadow-mon-1, in ch09 |
| A-wink | ae-11-plates wink-thanks #1 | high | -1, -2 · 1280 × 720 | the Messenger thank-you wink (s19) | A-wink-1, in ch06 |

Where they play in the final film: A-th-cloud-1 and A-th-leaf-1 in two of her eight thought windows in ch02, and among the five that lift off the screen as glass panes in the coast (song 21.7–28.0, film 0:24.3–0:30.7); A-sky-1, A-green-2 and A-world-2 in chorus 1's big window, on "sky" (53.00), "green" (54.16) and "Used to live inside the screen" (55.16) (film 0:55.7–1:07.2, until the wallpaper's world drains into it); A-wink-1 in her Messenger wink in ch06 (s19, song 97.24–100.80, film 1:39.9–1:43.5); ten in the windows of ch09's curved pane that the drop's chopped vocal hits pop open (seven of the second batch, and A-sky-1, A-dream-wsg-1 and A-th-dolphin-1 under second-batch names), with A-world-2 and A-green-2 there too (song 138.05–152.49, film 2:20.7–2:35.2); and A-glass-2, A-water-2, A-sky-2, A-green-1 and A-green-b-1 in the final chorus's windows in ch10 (song 152.49–181.36, film 2:35.2–3:04.0).

The pictures' prompts follow, each with the animations made from it. They are Midjourney v8.2 prompts, given with the aspect ratio, `--v 8.2`, the batch's `--stylize` and anabology's personal profile (its code left out); each had three frames of the reference videos anabology picked as style references.

**wp-wsg** (`--ar 16:9 --v 8.2 --stylize 200`): A-dream-wsg from #2, A-wsg-b from #4, both at low motion.

```prompt
wide view of a bright green grassy hill sloping down to a turquoise lagoon, white curved glass pavilions and slides at the water's edge, three white wind turbines on the far ridge, a deep blue sky with towering cumulus, soap bubbles, a perfect 2007 desktop wallpaper, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**loop-glass** (`--ar 16:9 --v 8.2 --stylize 200`): A-glass from #2, high motion.

```prompt
close view of sunlit clear glass panels and glossy glass spheres overlapping in a white atrium, rainbow refractions, bubbles, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**loop-water** (`--ar 16:9 --v 8.2 --stylize 200`): A-water from #1 and A-water-b from #4, both at high motion.

```prompt
underwater in a crystal turquoise lagoon, sunbeams slanting down, silver bubbles rising, a few bright fish, white sand, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**loop-sky** (`--ar 16:9 --v 8.2 --stylize 200`): A-sky from #2 and A-sky-b from #3, both at high motion.

```prompt
towering white cumulus clouds drifting across a deep cobalt sky over a lime ridge, sunbeams, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**loop-green** (`--ar 16:9 --v 8.2 --stylize 200`): A-green from #2 and A-green-b from #1, both at high motion.

```prompt
low close view of tall bright lime-green grass blades with dew in wind and sun, daisies, blue sky above, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**loop-world** (`--ar 16:9 --v 8.2 --stylize 200`): A-world from #2 and A-world-b from #4, both at low motion.

```prompt
wide aerial of a white glass city with waterfalls, green terraces, monorails and turquoise lagoons under a deep blue sky with towering cumulus, bubbles, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**thought-fish** (`--ar 1:1 --v 8.2 --stylize 150`): A-th-fish from #1, low motion.

```prompt
a bright orange and blue tropical fish swimming inside a clear floating glass bubble in a blue sky, sunlight through the bubble, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**thought-cloud** (`--ar 1:1 --v 8.2 --stylize 150`): A-th-cloud from #3, low motion.

```prompt
a single perfect fluffy white cumulus cloud floating in a deep cobalt sky, sun rim light, a few soap bubbles, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**thought-leaf** (`--ar 1:1 --v 8.2 --stylize 150`): A-th-leaf from #1, low motion.

```prompt
extreme macro of a bright lime-green leaf holding one large clear water drop that reflects a blue sky, glossy, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**thought-tower** (`--ar 1:1 --v 8.2 --stylize 150`): A-th-tower from #4, low motion.

```prompt
a slender white and glass futuristic tower with green terraces and waterfalls against a deep blue sky with cumulus, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**thought-turbine** (`--ar 1:1 --v 8.2 --stylize 150`): A-th-turbine from #1, low motion.

```prompt
one white wind turbine on a lime-green hilltop against a cobalt sky with cumulus, low angle, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**thought-waterfall** (`--ar 1:1 --v 8.2 --stylize 150`): A-th-waterfall from #1, low motion.

```prompt
a waterfall pouring into a turquoise pool between white curved glass terraces and palms, sun sparkle, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**thought-dolphin** (`--ar 1:1 --v 8.2 --stylize 150`): A-th-dolphin from #4 and A-dolphin-b from #3, both at low motion.

```prompt
a dolphin leaping out of a clear turquoise wave in sunlight, splash droplets glittering, blue sky, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**thought-globe** (`--ar 1:1 --v 8.2 --stylize 150`): A-th-globe from #1, low motion.

```prompt
a clear glass globe with a tiny green tree and grass growing inside, sitting in sunlight on white glass, blue sky reflected, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**windmills-2007** (`--ar 16:9 --v 8.2 --stylize 200`): A-windmills-2007 from #1 and A-windmills-b from #4, both at low motion.

```prompt
a glossy 2007 desktop wallpaper 3D render of white wind turbines on smooth lime-green hills, a cobalt sky with perfect cumulus, lens flare, reflective grass, CGI stock illustration, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**phone-glass** (`--ar 16:9 --v 8.2 --stylize 200`): A-phone from #3, low motion.

```prompt
a modern smartphone lying on a white glossy desk in sunlight, its screen a liquid glass interface of clear glossy bubbles and translucent panels over a blue sky wallpaper, product photography, no people, no text, no letters, no logos
```

**glass-city** (`--ar 16:9 --v 8.2 --stylize 200`): A-glass-city from #3, low motion.

```prompt
a sunny plaza in a white glass city, waterfalls down curved white towers, green terraces, a monorail, a deep blue sky with cumulus, an open space in the foreground, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**pool-atrium** (`--ar 16:9 --v 8.2 --stylize 200`): A-pool from #1, low motion.

```prompt
inside a white glass atrium with a turquoise pool, sunlight through a curved glass roof, palms and hanging plants, bubbles, a calm spot to stand waist-deep in the water, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**macro-drop** (`--ar 16:9 --v 8.2 --stylize 200`): A-crystal from #3, low motion.

```prompt
extreme macro of one round clear water drop resting on a fingertip, the drop refracts a tiny upside-down sunny lagoon and blue sky, sparkle, shallow focus, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no text, no letters, no logos
```

**meadow-monitor** (`--ar 16:9 --v 8.2 --stylize 200`): A-meadow-mon from #3, low motion.

```prompt
wide view of a giant clear glass computer monitor standing upright in a lime meadow with daisies, its screen glowing soft aqua, a deep blue sky with towering cumulus, soap bubbles, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

**wink-thanks** (batch ae-11-plates; `--ar 16:9 --v 8.2 --stylize 200`): A-wink from #1, high motion.

```prompt
a glossy 3D aqua glass heart floating in the middle of a bright sky, bursting soap bubbles and white sparkles flying out around it, clean 2007 instant messenger animation style, frutiger aero, hyper-saturated cobalt sky, lime green, turquoise water, glossy translucent glass, sunny 2007 utopia, no people, no text, no letters, no logos
```

## Totals

Takes are the video files that came back, measured with ffprobe; seconds are the takes' own lengths (frames at 24 fps); costs are the list prices the ledgers log for those takes, at the per-second rates given under Prices. The totals add the unrounded figures, so a column of rounded entries can differ from its total by a cent or a tenth of a second.

**By model and route:**

| Model and route | Takes | Seconds in the takes | Cost at list | In the final film |
|---|---|---|---|---|
| Seedance 2.5 on Higgsfield's API, references, no video input (8 of them at 1080p) | 40 | 314.7 s | $192.59 | 25 |
| Seedance 2.5 on Higgsfield's API, references with a dancer as @Video1 | 12 | 137.5 s | $75.99 | 3 |
| Seedance 2.5 on Higgsfield's API, image-to-video (first frame, or first and last) | 3 | 27.1 s | $12.48 | 1 |
| **Seedance 2.5 on Higgsfield's API** | **55** | **479.3 s** | **$281.06** | **29** |
| **Seedance 2.5 on Replicate**, first frame | **40** | **203.7 s** | **$46.70** | **14** |
| **Midjourney's video model** (Animate loops) | **56** | **282.3 s** | not recorded | **20** |
| **Total** | **151** | **965.3 s** | **$327.76** (Seedance on Higgsfield's API $281.06, on Replicate $46.70) | **63** |

**By section:**

| § | Section | Takes | Seconds in the takes | Cost at list | In the final film |
|---|---|---|---|---|---|
| 1 | Her: storyboard v2's SD takes (Higgsfield's API) | 38 | 314.6 s | $181.92 | 20 |
| 2 | The world: the RP takes (Replicate) | 15 | 77.6 s | $17.80 | 3 |
| 3 | v2: the moving 2008 places and the game screens (Replicate) | 25 | 126.0 s | $28.90 | 11 |
| 4 | v3: the coast, the maglev world and the Wii moments (Higgsfield's API) | 15 | 152.6 s | $89.54 | 7 |
| 5 | The new ending (Higgsfield's API) | 2 | 12.1 s | $9.60 | 2 |
| 6 | Midjourney's Animate loops | 56 | 282.3 s | not recorded | 20 |
| | **Total** | **151** | **965.3 s** | **$327.76** | **63** |

The 63 takes in the final film are 404.6 s of video, $151.95 at list (Higgsfield's API $136.00, Replicate $15.95, Midjourney not recorded). Not counted anywhere above: the one Replicate request that failed with a read error and made no video (RP04, $1.16 logged at submission), and the GPT Image 2.5 stills behind the first frames.

**The takes in the final film.** The final film is v3 on the song with its new ending: 4,792 frames at 24 fps (199.67 s), the 2.67 s pre-roll and then the song to its last frame at 196.96 s. Its first 1:21 is the Aurora coast, three spans rendered in Blender with the coded desktop flat between them; from song 78.54 (film 1:21.2) it is the coded desktop's own frames. The Seedance takes, in the order they first appear:

| Take | Route | Where | Song time | Film time |
|---|---|---|---|---|
| SD01-t1 | Higgsfield's API | her logon tile, on the coast's curved screen (ch01) | 2.73–8.14 | 0:05.4–0:10.8 |
| SD19-t1 | Higgsfield's API | "Did you miss me?" in person on the walkway (coast) | 3.95–5.35 | 0:06.6–0:08.0 |
| SD02-t1 | Higgsfield's API | her call (ch02) | 13.55–27.24 | 0:16.2–0:29.9 |
| SD21-t1 | Higgsfield's API | tennis on the desktop (ch02) | 13.95–23.50 | 0:16.6–0:26.2 |
| LP04-t1, LP12-t1, LP13-t1, LP15-t1, LP16-t1, LP18-t1 | Replicate | her thought windows (ch02); LP12, LP16 and LP18 also as panes in the coast | 21.7–28.0 | 0:24.3–0:30.7 |
| SD03-t2 | Higgsfield's API | her call (ch02–ch03) | 27.24–35.20 | 0:29.9–0:37.9 |
| SD20-t3 | Higgsfield's API | her dance on the catwalk (coast) | 35.44–43.75 | 0:38.1–0:46.4 |
| A-dream-maglev-t1 | Higgsfield's API | the maglev DreamScene wallpaper | 38.81–65.88 | 0:41.5–1:08.5 |
| SD22-t1 | Higgsfield's API | "Cancel… or allow?" with the remote (coast) | 47.9–52.4 | 0:50.6–0:55.1 |
| LP05-t1 | Replicate | chorus 1's window, "Glass" | 51.44–52.38 | 0:54.1–0:55.0 |
| LP03-t1 | Replicate | chorus 1's window, "water" | 52.38–53.00 | 0:55.0–0:55.7 |
| SD05-t4 | Higgsfield's API | dragged out of the big window, onto the taskbar (ch04) | 57.73–65.88 | 1:00.4–1:08.5 |
| SD23-t1 | Higgsfield's API | the Wii duel on the desktop (ch05) | 65.88–77.54 | 1:08.5–1:20.2 |
| SD07a-t1 | Higgsfield's API | her call (ch06) | 78.47–82.20 | 1:21.1–1:24.9 |
| SD07d-t3 | Higgsfield's API | her call (ch06) | 82.20–89.79 | 1:24.9–1:32.5 |
| SD07b-t1 | Higgsfield's API | her call (ch06) | 89.79–101.97 | 1:32.5–1:44.6 |
| SD08-t3 | Higgsfield's API | her call beside the consent prompt (ch07) | 101.97–109.50 | 1:44.6–1:52.2 |
| SD09a-t1 | Higgsfield's API | chorus 2's window, "Glass"; again in ch10's Flip 3D from 167.00 | 109.20–110.10 | 1:51.9–1:52.8 |
| SD09b-t1 | Higgsfield's API | chorus 2's window, "water" | 110.10–110.74 | 1:52.8–1:53.4 |
| SD09c-t1 | Higgsfield's API | chorus 2's window, "sky" | 110.74–111.90 | 1:53.4–1:54.6 |
| SD09d-t1 | Higgsfield's API | chorus 2's window, "green" | 111.90–112.92 | 1:54.6–1:55.6 |
| SD10-t1 | Higgsfield's API | "Used to live inside the screen" | 112.92–115.98 | 1:55.6–1:58.6 |
| RP02-t2 | Replicate | "Now it's real, it's on its way" | 115.98–118.66 | 1:58.6–2:01.3 |
| RP03-t1 | Replicate | "Click allow and it can stay" | 118.66–123.62 | 2:01.3–2:06.3 |
| SD11-t2 | Higgsfield's API | "You opened the window." (ch08) | 126.3–132.87 | 2:09.0–2:15.5 |
| SD12-t1 | Higgsfield's API | "Nobody told me" … "it was wet" (ch08) | 132.87–134.44, 137.38–138.4 | 2:15.5–2:17.1, 2:20.0–2:21.1 |
| RP04-t2 | Replicate | the drop on her fingertip (ch08) | 134.44–137.38 | 2:17.1–2:20.0 |
| SD13-t1 | Higgsfield's API | on the glass ledge of the curved pane (ch09) | 138.96–150.68 | 2:21.6–2:33.3 |
| SD14-t2 | Higgsfield's API | final chorus A (ch09–ch10) | 152.04–159.30 | 2:34.7–2:42.0 |
| SD15-t1 | Higgsfield's API | final chorus B (ch10) | 159.30–166.94 | 2:42.0–2:49.6 |
| LP01-t1, LP06-t1, LP14-t1 (and LP12-t1, LP18-t1) | Replicate | the world's files in Flip 3D and its burst (ch10) | 167.0–181.4 | 2:49.7–3:04.0 |
| SD16-t3 | Higgsfield's API | the last "Click allow" (ch10–ch11) | 170.53–181.8 | 2:53.2–3:04.5 |
| SD17b-t1 | Higgsfield's API | the ad (ch11) | 182.79–188.35 | 3:05.5–3:11.0 |
| SD18-t1 | Higgsfield's API | her call at rest (ch11) | 188.57–190.40 | 3:11.2–3:13.1 |
| RP05-t8 | Higgsfield's API | the wallpaper's world, her on the grass (ch11) | 189.48–196.96 | 3:12.1–3:19.6 |
| SD24-t1 | Higgsfield's API | "Touch glass." (ch11) | 190.40–196.96 | 3:13.1–3:19.6 |

And the 20 Midjourney loops listed in section 6: A-th-cloud-1, A-th-leaf-1, A-sky-1 (in ch09 again, filed as A-sky-b-1), A-green-2, A-world-2, A-wink-1, A-glass-city-1, A-pool-1, A-world-b-1, A-water-b-1, A-dream-wsg-1 (filed as A-wsg-b-1), A-windmills-b-1, A-th-dolphin-1 (filed as A-dolphin-b-1), A-crystal-1, A-meadow-mon-1, A-glass-2, A-water-2, A-sky-2, A-green-1 and A-green-b-1.
