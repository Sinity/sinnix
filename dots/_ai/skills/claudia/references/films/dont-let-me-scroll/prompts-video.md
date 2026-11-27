# Wan 3.0 and Seedance 2.5 — every video job (DON'T LET ME SCROLL)

Models: **Wan 3.0** (`alibaba/wan-3.0`, image-to-video and reference-to-video) and **Seedance 2.5** (`bytedance/seedance-2.5`, reference-to-video and video-edit), both through **Higgsfield's pay-per-generation API**. There were 90 submissions to 86 jobs: 49 to Wan and 41 to Seedance. 87 came back with one take each. Three were refused and refunded: two Seedance runs of the white-satin drop dance (blocked by Seedance's output filter) and one Wan double-tap (status "nsfw").

- **Wan, image-to-video** (39 submissions, 38 takes): her performances on grey and the bedroom, from a Midjourney first frame and a prompt, at 1080p (1080 × 1920 for her on grey, 1920 × 1080 for the bedroom and the v1 stocks shot), 5 to 8 s, 30 fps, exactly as long as asked, with a seed.
- **Wan, reference-to-video** (10): finished shots handed back as Video 1, re-lit and repaired, at 1080p 16:9, 4 to 8 s; five of them with her face as Image 1. Wan returns the length it is given, so each source was padded to whole seconds with its last frame held.
- **Seedance, reference-to-video** (15 submissions, 13 takes): twelve dances at 720p 9:16, each from a first frame (@Image1) and the shot's own window of the song's instrumental (@Audio1, rhythm and timing only, with `generate_audio` on so the take follows it; the take's audio is never used), and the escape at 1080p 16:9 from two images. 24 fps: 24 frames per second asked, plus one (121 for 5 s).
- **Seedance, video-edit** (26): sixteen outfit swaps of existing takes, nine re-lights (eight of rendered frames, one of the bedroom take; one of the samples also re-dressed her) and one face edit, each with the video as @Video1 and up to three images; returned at 24 fps (lengths below).

**Direction.** anabology: "We can use Wan 3.0 for vids for a bit cheaper than Seedance 2.5 - default to Wan and if it doesnt work well then use Seedance for tricky scenes." In the notes on v1: "we can do reshoots with seedance to make stuff better or mj reshoots then wan again as well", and "ideally we use seedance mostly for re-texturing adn cleaning, and we do the recomposition ourself with animation. seedance is wonderful for mastering an animated prompt - load the skill for it, you will describe in real depth." Then: "you can totally replace backgrounds with seedance btw." In the last notes: "you could maybe just throw the entire clip thru Wan 3.0 (with your edits and stuff) and specify to remove the foot so you dont have to re-edit. and have it relight at the same time."

**Price.** List price, as the runner records it (`video/tools/hfapi.py`). Wan 3.0: $0.20 a second at 1080p, priced per generated second by resolution (Higgsfield's estimate), and by the same estimate (as read for DOWNFORCE) a video input is priced per second too. Seedance 2.5: $1.1372 a second at 1080p and $0.4622 at 720p, a video input billing its own seconds at the same rate, image and audio references free. So a 5 s Wan take costs $1.00, a 5 s Wan pass over a 5 s shot $2.00, a 5 s Seedance dance at 720p $2.31, and a 5 s swap of a 5 s take at 1080p $11.37. Refused requests are refunded. The runner's ledger priced the ten Wan passes at their generated seconds only ($10.40); the prices here add their 52 s of input video ($10.40 more), as DOWNFORCE's package did. These are list prices; what was actually charged is not recorded.

**Budget.** The runner refuses a submission that would pass its cap at list price. In v1 the lead set the cap at $40, which stopped ten Wan jobs; they went out again under a $75 cap.

There are four delivered cuts: **v1**, **v2**, **v3** and **the final**. Times written as 0:55 are times in the song (the final cut starts at the song's 0:03). Inside anabology's quotes a time is in the cut they were watching: in the v3 cut from 0:03 and the final, add 3 s for the song; "at 0:12" and "at 0:18" are in the red-look chapter's review cut. Shots are numbered S01–S35 on the storyboard (`STORYBOARD.md`, `shots.json`).

## Totals

Measured for this package from `shots/ledger-hf.jsonl` (a line per submission with its list price, and a line per refund), the job files `shots/*.json` and the delivered takes (`media/clips/`). "In the final" counts a take whose frames the final cut shows, directly or under a swap or a re-light (see the Index).

| Round | Submissions | Wan | Seedance | Refused | Seconds asked (completed jobs) | List price | After refunds |
|---|---|---|---|---|---|---|---|
| Round 1 · v1's takes | 40 | 29 | 11 | 2 | 204 | $60.00 | $52.60 |
| The re-light samples | 4 | 0 | 4 | 0 | 21 | $47.81 | $47.81 |
| The first outfit swaps, in the pink look (dropped) | 8 | 0 | 8 | 0 | 40 | $64.08 | $64.08 |
| The escape | 1 | 0 | 1 | 0 | 15 | $17.06 | $17.06 |
| v2's takes in looks C, D and F | 8 | 6 | 2 | 0 | 51 | $13.87 | $13.87 |
| The white-shirt swaps | 8 | 0 | 8 | 0 | 40 | $64.08 | $64.08 |
| The lavender takes | 4 | 3 | 1 | 1 | 16 | $5.51 | $4.51 |
| The bedroom re-light | 1 | 0 | 1 | 0 | 5 | $11.42 | $11.42 |
| The turn again | 1 | 1 | 0 | 0 | 5 | $1.00 | $1.00 |
| v2's re-lights of the cut | 4 | 0 | 4 | 0 | 23 | $51.18 | $51.18 |
| v3: Wan relight-and-repair | 5 | 5 | 0 | 0 | 28 | $11.20 | $11.20 |
| The face reference | 4 | 4 | 0 | 0 | 20 | $8.00 | $8.00 |
| S17 again: options A and B | 2 | 1 | 1 | 0 | 8 | $10.70 | $10.70 |
| **Total** | **90** | **49** | **41** | **3** | **476** | **$365.90** | **$357.51** |

| Kind | Model, endpoint | Submissions | Takes | Seconds | List price | Takes in the final |
|---|---|---|---|---|---|---|
| Her performances and the bedroom, v1 | Wan 3.0 image-to-video | 29 | 29 | 159 | $31.80 | 16 |
| The dances on the beat, v1 | Seedance 2.5 reference-to-video | 11 | 9 | 45 | $28.20 | 8 |
| Re-light samples of v1's frames | Seedance 2.5 video-edit | 4 | 4 | 21 | $47.81 | 0 |
| Outfit swaps | Seedance 2.5 video-edit | 16 | 16 | 80 | $128.16 | 8 |
| The escape | Seedance 2.5 reference-to-video | 1 | 1 | 15 | $17.06 | 1 |
| Her v2 takes, Wan | Wan 3.0 image-to-video | 10 | 9 | 53 | $11.60 | 7 |
| Her v2 dances, Seedance | Seedance 2.5 reference-to-video | 3 | 3 | 19 | $8.78 | 3 |
| Re-lights for v2: the bedroom take and four windows of the cut | Seedance 2.5 video-edit | 5 | 5 | 28 | $62.60 | 5 |
| Wan relight-and-repair passes | Wan 3.0 reference-to-video | 10 | 10 | 52 | $20.80 | 6 |
| Seedance face edit | Seedance 2.5 video-edit | 1 | 1 | 4 | $9.10 | 0 |
| **Total** | | **90** | **87** | **476** | **$365.90** | **54** |

- **By model:** Wan 3.0, 49 submissions, 264 s generated and 52 s of input video, $64.20 at list, $63.20 after the refund. Seedance 2.5, 41 submissions, 212 s asked by the completed jobs (the two refused asked 16 s more), $301.70 at list, $294.31 after the two refunds. In all $365.90 at list and $357.51 after $8.40 of refunds; the runner's ledger, without the Wan passes' input video, came to $355.50. The prices in the tables are rounded to the cent, so a column may not add up exactly to its total, which comes from the unrounded ledger.
- **Takes:** 87, one per completed submission. The project kept no take log for this film; each take's verdict below comes from the lead's review messages, the chapter agents' notes (`wf/notes/`) and the job files. v1 plays 37 of v1's 38 takes. The final cut shows 54 of the 87: 33 with their own frames and 21 under a swap or a re-light. $148.10 at list went to the 33 takes the final does not show, $16.51 of it v1 takes that played in v1.

## How the jobs were made

**Who wrote the prompts.** Claude, the production lead, wrote every one, through a job builder per kind: `tools/wan.py` (v1's Wan takes; its prompt book, `PROMPTS.md`, went to anabology with the plates before anything was spent: 37 takes planned, $39.80), `tools/sddance.py` (v1's Seedance dances), `tools/relight.py` (the Seedance re-lights), `tools/swapfit.py` (the outfit swaps), `tools/escape.py` (the escape) and `tools/v2takes.py` (v2's takes). The Wan passes and the two last options for S17 were written in the conversation, the four face-reference passes by `tools/wanface.py`. The Seedance prompts follow the house contract for Seedance 2.5 (`video/SEEDANCE-2.5.md`) and, for the edits, Seedance's prompt-optimising skill, as anabology asked. Each job file in `shots/` keeps its request body as it was last submitted, and every prompt below is copied from there, with two exceptions marked where they occur: the refused Seedance drop dance and the refused first double-tap, whose job files were overwritten when the shots were remade.

**The request.** Each body has the prompt, a `duration` in whole seconds, a `resolution`, an `aspect_ratio` (Wan and the Seedance dances; the edits take the source's) and `generate_audio` (on only for the dances, which hear @Audio1). The input files are uploaded and passed as URLs. Wan's image-to-video jobs carry a seed: 1000 plus the take's place in the alphabetical list of v1's takes (P04 is 1003, R35 1036), and v2's from 2000 up, not strictly one per take (P05B and P21B share 2001, P32B and P29B's second take 2006; P21C has 2101). Wan's reference-to-video jobs and every Seedance job have none. A job is written locked, the runner submits only locked jobs, and jobs went out in parallel, up to eight at a time.

**The inputs.** First frames are the Midjourney picks of [prompts-midjourney.md](https://claudia.gallery/record/dont-let-me-scroll/prompts-midjourney/), cut to the take's frame: 1080 × 1920 for Wan, 720 × 1280 for the Seedance dances ("sc-02-perf P08 #2" is image 2 of the job P08 in that batch). A dance's @Audio1 is the shot's window of the song's stems, drums, bass and the rest mixed without the vocal, starting a beat or so before the shot. A swap's @Video1 is the take itself, her on grey before any roto. A re-light's @Video1 is cut from the render box's own frames of the cut, and its references are pictures from the library's moodboards: two from liquid-glass (lg006, lg022) and two from acid-blur (ab001, ab007). The Wan passes take the cut's frames of the shot as Video 1; the five face-reference passes (the four from `tools/wanface.py` and S17's option B) also take her face (face 1) as Image 1.

Prompt lengths: 117 to 664 words (median 264.5).

## The house preambles

Every v1 Wan prompt opens with KEEP, which names what Image 1 fixes; `{w}` is the look's wardrobe in words:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes ({w}). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. 
```

A take of her on grey adds GREY, which locks the camera and keeps her whole body in frame (her performances are cut out and placed in the code world, so the camera never moves in the take):

```
The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 
```

The bedroom adds ROOM instead, and the dances add BEAT before their action:

```
Native colour, cinematic, shallow focus; one continuous shot, no cuts. 
```

```
She moves to a fast UK garage two-step beat at 133 BPM: sharp accents on the beat every 0.45 seconds, loose and bouncy between. 
```

The shot's own beats follow in seconds ("0–1 s: … 1–4 s: …"). v2's Wan takes use the same KEEP and a GREY that also asks for "Native colour, one continuous shot, no cuts." The Seedance dances share a structure from `tools/sddance.py` and `tools/v2takes.py`: 【Audio Policy】 at the top and the bottom, 【Generation Goal】, 【Reference Asset Roles】 ("Use @Image1 as the first frame." and @Audio1 for "rhythm and timing only"), 【Subject】 with the short canon and the wardrobe, 【Performance】 ("Claudia does not sing or speak … continuing the motion of her pose in @Image1 with no pause:" and the beats in whole seconds), 【Camera】 (locked off, full length), 【Core Requirements】 and 【Final Acceptance Criteria】. The swaps and re-lights are Seedance video edits: 【Editing Goal】, 【Role of the Source Video】 ("@Video1 is the sole editing master"), 【Role of the Target Material】 (what each image is used for, and what not), 【Edit Objects and Scope】 (what changes, then "Do not modify Claudia: …" with her description, and the scope-closing sentence "Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed."), and 【Timeline Inheritance】. The Wan passes open "Reimagine Video 1 as the same shot, physically lit and photographic. Keep every element exactly in place and in time …", and add the face: "Image 1 is the face of the woman: keep her face exactly as in Image 1 in every frame … Image 1 is only a reference for her face; it is never shown as a shot."

## What the takes did

From the lead's review messages and the chapter agents' notes; the second of the take is given where it was measured.

| What happened | Takes | What changed after it |
|---|---|---|
| Wan's dance held the first pose, reset and shuffled | P08 | Every dance that had to land on the beat went to Seedance with the shot's instrumental as @Audio1 |
| Seedance's output filter blocked a dance in white satin | P28 (twice, from two different first frames) | Made on Wan; the later red-look drop dance passed on Seedance |
| Higgsfield refused a leaning, pointing pose ("nsfw") | P05B's first request | Restaged upright, pointing up at the post above her |
| Drew things the prompt did not ask for | P23 (a white object, a green yo-yo falling onto her toes, a book), P26 (a stool seat from 3.0 s), P21B (a holographic glass panel), P21C (focus brackets round her fingertip) | Matte surgery (P23), re-take with "nothing is visible in the air" (P21B → P21C), the brackets keyed out |
| The green screen was the back of a phone | P21 | v2 has no phone in her hand: a giant screen she works from behind |
| Moved the camera although told it was locked off | P06 (she shrinks about 20 % from 3 s), P16 (eases back to 2.8 s), P30B (her height 0.98 → 0.77 of the frame) | Placed by her feet frame by frame, read as a step back (P06) |
| Played the prompt's order backwards | P22 (arms folded first), R35 (looks back first) | Used as they came; R35 played backwards in v1 |
| Limbs or hair leave the take's frame | P05, P10, P11, P15, P16, P24, P28, P29, P30, P07B (wrists in 98 of 121 frames), P19B (sleeves, about 4 frames), P10's swap (the back foot) | Faded at the frame's edge, which read as a "blurred bounding box"; covered by posts (P07B); in v3, completed by Wan passes (S10, S19, S28, S30) |
| Backwards legs, from the still | P29B's first take | Made again from the one still with her knees and feet forward |
| Roto defects | P08-sd (floor plateaus at the feet), P17 (one fingertip half transparent), P19B (a shadow ghost, holes where the legs cross), P30B (a heel shadow, a lost back shoe), P28B (grey squiggles for about three frames) | Patched in the chapters; P30B rotoscoped again with BiRefNet's full general model |
| Too short for the shot at 1×, so the shot ended on a held frame | S11, S12, S18, S19, S23 and S30 (flagged in v2's plan once the beat warps were floored at 1×); P12 is 5.04 s for a 5.40 s shot | S12 became a sampler at 1×; S11 a two-beat loop near its end (v3); S19 and S30 were taken again in v2 |
| 24 fps content inside a 30 fps file | R33 | Frame-blended at 30 fps |
| Letterbox bars | R02 (picture rows 35–1050) | Drawn at a zoom of 1.07 or more |

## Seedance edits: length and alignment, measured

Every edit came back at 24 fps. The table gives each source and what came back (ffprobe on the files):

| Job | Source | Source frames, fps, length | Returned frames, length |
|---|---|---|---|
| RL-DIGITS | v1 frames | 183 at 24 fps, 7.625 s | 177, 7.375 s |
| RL-RIVER | v1 frames | 79 at 24 fps, 3.292 s | 89, 3.709 s |
| RL-RIVER-DRESS | v1 frames | 79 at 24 fps, 3.292 s | 89, 3.709 s |
| RL-E | v1 frames | 164 at 24 fps, 6.834 s | 161, 6.709 s |
| SW-E-P12 | P12's take 1 | 121 at 24 fps, 5.056 s | 121, 5.042 s |
| SW-E-P11 | P11's take 1 | 121 at 24 fps, 5.056 s | 121, 5.042 s |
| SW-E-G-B | G-B's take 1 | 121 at 24 fps, 5.056 s | 121, 5.042 s |
| SW-E-P08 | P08's take 2 | 121 at 24 fps, 5.056 s | 121, 5.042 s |
| SW-E-P09 | P09's take 1 | 150 at 30 fps, 5.000 s | 113, 4.709 s |
| SW-E-P10 | P10's take 1 | 150 at 30 fps, 5.000 s | 113, 4.709 s |
| SW-E-P13 | P13's take 1 | 150 at 30 fps, 5.000 s | 113, 4.709 s |
| SW-E-P06 | P06's take 1 | 150 at 30 fps, 5.000 s | 113, 4.709 s |
| SW-E2-P13 | P13's take 1 | 150 at 30 fps, 5.000 s | 113, 4.709 s |
| SW-E2-P09 | P09's take 1 | 150 at 30 fps, 5.000 s | 113, 4.709 s |
| SW-E2-P10 | P10's take 1 | 150 at 30 fps, 5.000 s | 113, 4.709 s |
| SW-E2-P08 | P08's take 2 | 121 at 24 fps, 5.056 s | 121, 5.042 s |
| SW-E2-G-B | G-B's take 1 | 121 at 24 fps, 5.056 s | 121, 5.042 s |
| SW-E2-P11 | P11's take 1 | 121 at 24 fps, 5.056 s | 121, 5.042 s |
| SW-E2-P06 | P06's take 1 | 150 at 30 fps, 5.000 s | 113, 4.709 s |
| SW-E2-P12 | P12's take 1 | 121 at 24 fps, 5.056 s | 121, 5.042 s |
| RL-R02 | the R02 take at 24 fps | 121 at 24 fps, 5.042 s | 121, 5.042 s |
| RL2-RIVER | the cut | 89 at 24 fps, 3.709 s | 89, 3.709 s |
| RL2-DIGITS | the cut | 189 at 24 fps, 7.875 s | 185, 7.709 s |
| RL2-BLUE | the cut | 89 at 24 fps, 3.709 s | 89, 3.709 s |
| RL2-E | the cut | 161 at 24 fps, 6.709 s | 161, 6.709 s |
| SDF-S17 | the cut | 96 at 24 fps, 4.000 s | 89, 3.709 s |

- **The whole motion is rescaled.** A 5.0 s Wan take at 1080p (150 frames at 30 fps) came back as 113 frames, 4.709 s: the same motion from the first frame to the last, 0.942 of the length. The 720p Seedance takes (121 frames at 24 fps) came back as 121 frames. There is no head trim and no offset.
- **Align by the ratio, check on what the edit does not change.** `tools/swapalign.py` maps take frame i to the edit at a·tᵢ with a the ratio of the lengths, then checks the fit on her hair (the glossy black in the top 40 % of the frame) and her body's x position: correlations of 0.71 to 0.998 across the eight swaps. The first swap was fitted on her silhouette instead. The new skirt changed her outline, the fit read 0.36–0.5 s missing from the head and the rest running 4–6 % fast, and the 0:55 shot went in with a frozen half-second until it was aligned again.
- **4n+1 frames.** A 24 fps source of 4n+1 frames came back frame for frame for 121, 89, 89 and 161 frames; 189 came back as 185. Shorter sources came back as 89 frames, never fewer: 79 frames (the river sample) and 96 (SDF-S17) both returned 89.

## Splicing re-lights into the cut

`tools/splice.py` puts a re-light back into the cut it was made from:

- `splice.py src` cuts the source from the render box's own frames of the cut (24 fps, CRF 10), rounded up to 4n+1 frames and to at least 89, the extra frames taken from the real frames after the window, and records the window.
- `splice.py put` writes the delivered clip back over exactly that window: window frame k takes re-lit frame round(k·(nr − 1)/(ns − 1)), so any rescale is absorbed. The originals are kept beside it, and `splice.py undo` puts them back.
- `--keep x,y,w,h` keeps the original pixels in fixed rectangles (feathered), for interface and small type the edit softened; `--keepjson` gives a rectangle per frame for something that moves.
- Wan's passes go through `tools/colormatch.py` first: one global per-channel mean and spread map, measured on frames sampled across the source and the re-light, so the correction cannot flicker.

| Job | Window (song) | Frames written | Kept from the original | In the final |
|---|---|---|---|---|
| RL2-E | 0:23.06–0:29.75 | 161 | — | yes |
| RL2-RIVER | 0:30.83–0:34.30 | 83 | — | yes |
| WANF-S10 (WAN-S10 in v3) | 0:39.25–0:43.30 | 97 | — | yes |
| WANF2-S17 (WAN-S17 in v3, WANF-S17 in the first final) | 1:13.89–1:17.48 | 87 | — | yes |
| WAN-S19 | 1:22.88–1:28.28 | 130 | — | yes |
| WANF-S21 | 1:31.43–1:37.28 | 141 | the interface platter and the status bar (two rectangles) | yes |
| RL2-BLUE | 1:37.29–1:38.46 | 28 | — | yes |
| RL2-DIGITS | 1:38.46–1:46.27 | 188 | the Reminders card, tracked over 48 frames | yes |
| WAN-S28 | 2:00.67–2:07.86 | 173 | — | yes |
| WANF-S30 (WAN-S30 in v3) | 2:11.46–2:16.13 | 112 | — | yes |

The bedroom re-light (RL-R02) is not a splice: it is a take in its own right, R02's take 2, drawn by the hook.

## Index

Every submission in the order of the prompt book below. "Returned" is the delivered take (ffprobe). "v1" and "final" give the shot where the take plays; "under" means the final shows it beneath a swap, a re-light or a Wan pass.

| Job | Round | Model, endpoint | Asked | List price | Returned | v1 | Final |
|---|---|---|---|---|---|---|---|
| P08 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | — | — |
| R02 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1920×1080 | S02 | under RL-R02 |
| P21 | v1 | Wan 3.0 image-to-video | 6 s, 1080p | $1.20 | 180 frames at 30 fps (6.000 s), 1920×1080 | S21 | — |
| P08-sd | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S08 | under its swap |
| P05 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S05 | — |
| P06 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S06 | under its swap |
| P07 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S07 | — |
| P04 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S04 | — |
| R03 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1920×1080 | S03 | S03 |
| P09 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S09 | under its swap |
| P14 | v1 | Wan 3.0 image-to-video | 8 s, 1080p | $1.60 | 240 frames at 30 fps (8.000 s), 1080×1920 | S14 | S14 |
| P10 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S10 | under its swap |
| P15 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S15 | S15 |
| P11 | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S11 | under its swap |
| P12 | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S12 | under its swap |
| P18 | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S18 | S18 |
| P19 | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S19 | — |
| P16 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S16 | S16 |
| P17 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S17 | under WANF2-S17 |
| P20 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S20 | S20 |
| P22 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S22 | under RL2-BLUE, RL2-DIGITS |
| P23 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S23 | under RL2-DIGITS |
| P24 | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S24 | S24 |
| P28 (Seedance 1) | v1 | Seedance 2.5 reference-to-video | 8 s, 720p | $3.70 | refused, refunded | — | — |
| G-B | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S28 | under its swap |
| P25 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S25 | S25 |
| G-C | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S28 | under WAN-S28 |
| G-D | v1 | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | S28 | under WAN-S28 |
| P28 (Seedance 2) | v1 | Seedance 2.5 reference-to-video | 8 s, 720p | $3.70 | refused, refunded | — | — |
| P13 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S13 | under its swap |
| P29 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S29 | — |
| P30 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S30 | — |
| P26 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S26 | S26 |
| P31 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | S31 | — |
| P28 (Wan) | v1 | Wan 3.0 image-to-video | 8 s, 1080p | $1.60 | 240 frames at 30 fps (8.000 s), 1080×1920 | S28 | — |
| P32 | v1 | Wan 3.0 image-to-video | 6 s, 1080p | $1.20 | 180 frames at 30 fps (6.000 s), 1080×1920 | S32 | — |
| R27 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1920×1080 | S27 | S27 |
| R33 | v1 | Wan 3.0 image-to-video | 8 s, 1080p | $1.60 | 240 frames at 30 fps (8.000 s), 1920×1080 | S33 | — |
| R34 | v1 | Wan 3.0 image-to-video | 8 s, 1080p | $1.60 | 240 frames at 30 fps (8.000 s), 1920×1080 | S34 | — |
| R35 | v1 | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1920×1080 | S35 | — |
| RL-DIGITS | samples | Seedance 2.5 video-edit | 8 s, 1080p | $17.77 | 177 frames at 24 fps (7.375 s), 1920×1080 | — | — |
| RL-RIVER | samples | Seedance 2.5 video-edit | 3 s, 1080p | $7.16 | 89 frames at 24 fps (3.709 s), 1920×1080 | — | — |
| RL-RIVER-DRESS | samples | Seedance 2.5 video-edit | 3 s, 1080p | $7.16 | 89 frames at 24 fps (3.709 s), 1920×1080 | — | — |
| RL-E | samples | Seedance 2.5 video-edit | 7 s, 1080p | $15.73 | 161 frames at 24 fps (6.709 s), 1920×1080 | — | — |
| SW-E-P12 | pink swaps | Seedance 2.5 video-edit | 5 s, 720p | $4.65 | 121 frames at 24 fps (5.042 s), 720×1280 | — | — |
| SW-E-P11 | pink swaps | Seedance 2.5 video-edit | 5 s, 720p | $4.65 | 121 frames at 24 fps (5.042 s), 720×1280 | — | — |
| SW-E-G-B | pink swaps | Seedance 2.5 video-edit | 5 s, 720p | $4.65 | 121 frames at 24 fps (5.042 s), 720×1280 | — | — |
| SW-E-P08 | pink swaps | Seedance 2.5 video-edit | 5 s, 720p | $4.65 | 121 frames at 24 fps (5.042 s), 720×1280 | — | — |
| SW-E-P09 | pink swaps | Seedance 2.5 video-edit | 5 s, 1080p | $11.37 | 113 frames at 24 fps (4.709 s), 1080×1920 | — | — |
| SW-E-P10 | pink swaps | Seedance 2.5 video-edit | 5 s, 1080p | $11.37 | 113 frames at 24 fps (4.709 s), 1080×1920 | — | — |
| SW-E-P13 | pink swaps | Seedance 2.5 video-edit | 5 s, 1080p | $11.37 | 113 frames at 24 fps (4.709 s), 1080×1920 | — | — |
| SW-E-P06 | pink swaps | Seedance 2.5 video-edit | 5 s, 1080p | $11.37 | 113 frames at 24 fps (4.709 s), 1080×1920 | — | — |
| ESC-W4 | escape | Seedance 2.5 reference-to-video | 15 s, 1080p | $17.06 | 361 frames at 24 fps (15.042 s), 1920×1080 | — | S33–S35 |
| P21B | v2 C/D/F | Wan 3.0 image-to-video | 7 s, 1080p | $1.40 | 210 frames at 30 fps (7.000 s), 1080×1920 | — | — |
| P30B | v2 C/D/F | Wan 3.0 image-to-video | 6 s, 1080p | $1.20 | 180 frames at 30 fps (6.000 s), 1080×1920 | — | under WANF-S30 |
| P32B | v2 C/D/F | Wan 3.0 image-to-video | 7 s, 1080p | $1.40 | 210 frames at 30 fps (7.000 s), 1080×1920 | — | S32 |
| P29B (1) | v2 C/D/F | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | — | — |
| P31B | v2 C/D/F | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | — | S31 |
| P28B | v2 C/D/F | Seedance 2.5 reference-to-video | 8 s, 720p | $3.70 | 193 frames at 24 fps (8.064 s), 720×1280 | — | under WAN-S28 |
| P19B | v2 C/D/F | Seedance 2.5 reference-to-video | 6 s, 720p | $2.77 | 145 frames at 24 fps (6.080 s), 720×1280 | — | under WAN-S19 |
| P21C | v2 C/D/F | Wan 3.0 image-to-video | 7 s, 1080p | $1.40 | 210 frames at 30 fps (7.000 s), 1080×1920 | — | under WANF-S21 |
| SW-E2-P13 | shirt swaps | Seedance 2.5 video-edit | 5 s, 1080p | $11.37 | 113 frames at 24 fps (4.709 s), 1080×1920 | — | S13 |
| SW-E2-P09 | shirt swaps | Seedance 2.5 video-edit | 5 s, 1080p | $11.37 | 113 frames at 24 fps (4.709 s), 1080×1920 | — | S09 |
| SW-E2-P10 | shirt swaps | Seedance 2.5 video-edit | 5 s, 1080p | $11.37 | 113 frames at 24 fps (4.709 s), 1080×1920 | — | under WANF-S10 |
| SW-E2-P08 | shirt swaps | Seedance 2.5 video-edit | 5 s, 720p | $4.65 | 121 frames at 24 fps (5.042 s), 720×1280 | — | under RL2-RIVER (3 frames direct) |
| SW-E2-G-B | shirt swaps | Seedance 2.5 video-edit | 5 s, 720p | $4.65 | 121 frames at 24 fps (5.042 s), 720×1280 | — | under WAN-S28 |
| SW-E2-P11 | shirt swaps | Seedance 2.5 video-edit | 5 s, 720p | $4.65 | 121 frames at 24 fps (5.042 s), 720×1280 | — | S11 |
| SW-E2-P06 | shirt swaps | Seedance 2.5 video-edit | 5 s, 1080p | $11.37 | 113 frames at 24 fps (4.709 s), 1080×1920 | — | under RL2-E |
| SW-E2-P12 | shirt swaps | Seedance 2.5 video-edit | 5 s, 720p | $4.65 | 121 frames at 24 fps (5.042 s), 720×1280 | — | S12 |
| P04B | v2 lavender | Wan 3.0 image-to-video | 6 s, 1080p | $1.20 | 180 frames at 30 fps (6.000 s), 1080×1920 | — | S04 |
| P05B (1) | v2 lavender | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | refused, refunded | — | — |
| P07B | v2 lavender | Seedance 2.5 reference-to-video | 5 s, 720p | $2.31 | 121 frames at 24 fps (5.056 s), 720×1280 | — | S07 (and under RL2-E) |
| P05B (2) | v2 lavender | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | — | S05 |
| RL-R02 | R02 re-light | Seedance 2.5 video-edit | 5 s, 1080p | $11.42 | 121 frames at 24 fps (5.042 s), 1920×1080 | — | the hook |
| P29B (2) | turn again | Wan 3.0 image-to-video | 5 s, 1080p | $1.00 | 150 frames at 30 fps (5.000 s), 1080×1920 | — | S29 |
| RL2-RIVER | v2 re-lights | Seedance 2.5 video-edit | 4 s, 1080p | $8.77 | 89 frames at 24 fps (3.709 s), 1920×1080 | — | S08 |
| RL2-DIGITS | v2 re-lights | Seedance 2.5 video-edit | 8 s, 1080p | $18.05 | 185 frames at 24 fps (7.709 s), 1920×1080 | — | S22–S23 |
| RL2-BLUE | v2 re-lights | Seedance 2.5 video-edit | 4 s, 1080p | $8.77 | 89 frames at 24 fps (3.709 s), 1920×1080 | — | S22 |
| RL2-E | v2 re-lights | Seedance 2.5 video-edit | 7 s, 1080p | $15.59 | 161 frames at 24 fps (6.709 s), 1920×1080 | — | S06–S07 |
| WAN-S30 | v3 repairs | Wan 3.0 reference-to-video | 5 s, 1080p | $2.00 | 150 frames at 30 fps (5.000 s), 1920×1080 | — | — |
| WAN-S17 | v3 repairs | Wan 3.0 reference-to-video | 4 s, 1080p | $1.60 | 120 frames at 30 fps (4.000 s), 1920×1080 | — | — |
| WAN-S10 | v3 repairs | Wan 3.0 reference-to-video | 5 s, 1080p | $2.00 | 150 frames at 30 fps (5.000 s), 1920×1080 | — | — |
| WAN-S28 | v3 repairs | Wan 3.0 reference-to-video | 8 s, 1080p | $3.20 | 240 frames at 30 fps (8.000 s), 1920×1080 | — | S28 |
| WAN-S19 | v3 repairs | Wan 3.0 reference-to-video | 6 s, 1080p | $2.40 | 180 frames at 30 fps (6.000 s), 1920×1080 | — | S19 |
| WANF-S17 | face ref | Wan 3.0 reference-to-video | 4 s, 1080p | $1.60 | 120 frames at 30 fps (4.000 s), 1920×1080 | — | — |
| WANF-S30 | face ref | Wan 3.0 reference-to-video | 5 s, 1080p | $2.00 | 150 frames at 30 fps (5.000 s), 1920×1080 | — | S30 |
| WANF-S10 | face ref | Wan 3.0 reference-to-video | 5 s, 1080p | $2.00 | 150 frames at 30 fps (5.000 s), 1920×1080 | — | S10 |
| WANF-S21 | face ref | Wan 3.0 reference-to-video | 6 s, 1080p | $2.40 | 180 frames at 30 fps (6.000 s), 1920×1080 | — | S21 |
| SDF-S17 | S17 A/B | Seedance 2.5 video-edit | 4 s, 1080p | $9.10 | 89 frames at 24 fps (3.709 s), 1920×1080 | — | — |
| WANF2-S17 | S17 A/B | Wan 3.0 reference-to-video | 4 s, 1080p | $1.60 | 120 frames at 30 fps (4.000 s), 1920×1080 | — | S17 |

## The prompt book

Each entry: the job, the model and endpoint, the length and resolution asked, the seed (Wan image-to-video), and the list price. Under it:

- **for:** the storyboard shot and its song time, and what the take was for.
- **inputs:** the first frame, the audio or video and the images it was given.
- **take:** what came back and what it did.
- **v1** and **final:** where it plays in each.

Quotes under **for** are anabology's notes or the lyric, and quotes under **take** the lead's review messages, unless they are marked otherwise.

### Round 1 · v1's takes · 40 submissions · $60.00 at list, $52.60 after refunds

#### P08

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1007 · $1.00

- **for:** S08 (0:30.70–0:34.30), the drop of chorus 1: her bouncy 2-step in look B.
- **inputs:** first frame: sc-02-perf P08 #2.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Wan held the first pose, reset to neutral, then shuffled: not a real two-step (the lead). This pilot take's verdict sent every dance that had to land on the beat to Seedance.
- **v1:** not used (P08-sd danced S08).
- **final:** not used.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized iridescent oil-slick satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. She moves to a fast UK garage two-step beat at 133 BPM: sharp accents on the beat every 0.45 seconds, loose and bouncy between. 0–5 s: she dances a bouncy UK garage two-step: skipping steps side to side, shoulders and hips on the swung beat, arms loose, the iridescent satin catching the light; she spins once at 3 s and keeps stepping.
```

#### R02

Wan 3.0 image-to-video · 5 s · 1080p 16:9 · seed 1031 · $1.00

- **for:** S02 (0:07.32–0:12.71): she turns the phone over in bed.
- **inputs:** first frame: sc-02-perf R02 #2.
- **take:** 150 frames at 30 fps (5.000 s), 1920×1080. "came out lovely" (the lead). Letterbox bars: the picture fills rows 35–1050. She lies looking at the camera to 1.3 s, glances down at 1.4, lifts the phone 1.45–2.0 and props herself up to read.
- **v1:** S02, frame-blended through a hand-made map that played 2.78 s of take over 5.4 s of song, about half speed. The notes on v1: "the clip where she looks on her phone at 8 seconds, never slow these down. you lowered the framerate for no reason, just looks bad."
- **final:** in the hook at 1×, inside the pills, as its re-lit version (RL-R02, below).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. Native colour, cinematic, shallow focus; one continuous shot, no cuts. A dark high-rise bedroom at night, city lights through the window behind. 0–1.5 s: she lies on her stomach on the white sheets, eyes half closed; the phone beside her buzzes once, its edge glowing. 1.5–3 s: she reaches for it without lifting her head and turns it face up; its cold white light blooms over her fingers and her face. 3–5 s: she props herself on one elbow and stares into the screen, the light flickering softly on her face as she reads. The camera creeps in slowly.
```

#### P21

Wan 3.0 image-to-video · 6 s · 1080p 16:9 · seed 1020 · $1.20

- **for:** S21 (1:31.43–1:37.28), the stocks: "when shes scrolling stocks on her phone, i wanna see her look at her phone and its a small stock on the screen […]".
- **inputs:** first frame: sc-02-perf P21 #4, the phone's screen bright green.
- **take:** 180 frames at 30 fps (6.000 s), 1920×1080. "the phone screen came out flat green and her thumb crosses it". The take is frontal, not over the shoulder, and the green surface Wan drew is the back of a phone, its screen facing her. v1 keyed it by brightness and green-minus-red and tracked its edges as sub-pixel lines (RANSAC), with the interface upright for the camera.
- **v1:** S21, the tracked phone, its first segment at 0.57×. anabology: "her phone is slop - the back of her phone is used as the screen, its silly."
- **final:** not used (P21C: no phone in her hand).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a sharp black blazer over a black ribbed top and loose black satin trousers). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. Over-the-shoulder medium close-up; the camera is still. Her phone's screen stays plain bright flat green the whole time (it will be replaced), always visible in her hands. 0–1.5 s: she looks down at the phone, thumb scrolling. 1.5–2.5 s: her eyes widen, excited. 2.5–3.5 s: she winces, shocked. 3.5–6 s: excited again, she bites her lip and leans in.
```

#### P08-sd

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S08, the same dance: one Seedance test against Wan's.
- **inputs:** @Image1: sc-02-perf P08 #2 at 720 × 1280; @Audio1: the instrumental (drums, bass and the rest of the stems, no vocal) from song 0:30.40, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. "its bent-knee 2-step bounce and spin hold together with no reset", at 720 × 1280 and 24 fps: the dances moved to Seedance. Its matte kept flat grey plateaus of floor at her feet, removed in the chapter.
- **v1:** S08 (as P08's take 2).
- **final:** re-dressed in the white satin skirt (SW-E2-P08), under the river's re-light.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances a bouncy UK garage two-step to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in oversized iridescent oil-slick satin pyjamas, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: she lands the step from @Image1 on the first beat and bounces straight into a two-step: a skip to her left, a skip to her right, shoulders popping on the beat.
1-3s: the swung two-step continues: knees bent, hips and shoulders hitting the strong beats of @Audio1, arms loose and swinging, the satin catching the light.
3-4s: a quick spin on the spot, the oversized satin flaring, landing exactly on a beat.
4-5s: she keeps bouncing on the beat with a confident smile.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P05

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1004 · $1.00

- **for:** S05 (0:19.01–0:23.06): the double-tap on the phone, delight.
- **inputs:** first frame: sc-02-perf P05 #4.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. A medium close-up whose frame cuts her below the chest. Two taps at 0.57 and 0.77 s, her hand to her mouth 2.3–3.0, the phone hugged to her chest from 3.7.
- **v1:** S05.
- **final:** not used (P05B: the double-tap in the air).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–1 s: she looks down at her phone, absorbed. 1–1.6 s: a quick double-tap on the screen with her thumb. 1.6–3.5 s: her face lights up with delight, a small laugh, her free hand rising to her mouth. 3.5–5 s: she hugs the phone to her chest, glowing.
```

#### P06

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1005 · $1.00

- **for:** S06 (0:23.06–0:26.21): tiny, looking up at the colossal E.
- **inputs:** first frame: sc-02-perf P06 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. She looks straight up. From about 3 s she shrinks by about 20 % and her feet rise: Wan eased its camera out although the prompt locked it off. The chapter reads it as her stepping back from the E.
- **v1:** S06.
- **final:** re-dressed in the lavender skirt (SW-E2-P06), under the E's re-light.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–2 s: she stands small and still, head tilted far back, looking straight up at something enormous. 2–5 s: her mouth opens slightly in awe; she takes one slow step back without lowering her gaze.
```

#### P07

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1006 · $1.00

- **for:** S07 (0:26.21–0:30.70): she pulls the world down into the refresh.
- **inputs:** first frame: sc-02-perf P07 #3.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Arms overhead, the pull at 2.2–2.5 s, the hold, the release at 4.2–4.6.
- **v1:** S07, through the chapter's own map (as slow as 0.44×). anabology: "dont love her pose here. doing some weird stretch with stubby legs."
- **final:** not used (P07B: the spin).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–2 s: arms raised high, she grips the air above her head with both hands, her body stretching up. 2–3.5 s: she pulls down hard as if dragging a heavy curtain, bending her knees, leaning back. 3.5–4.2 s: she holds the strain. 4.2–5 s: she lets go with both hands at once and her arms fly apart.
```

#### P04

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1003 · $1.00

- **for:** S04 (0:14.51–0:19.01): inside the phone, scrolling.
- **inputs:** first frame: sc-02-perf P04 #3.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. She looks up in wonder, then flicks fast with her fingers from 2.1 to 3.9 s, about every 0.2 s; the phone's back faces the camera.
- **v1:** S04: small, at the bottom centre ("a claudia in the middle bottom of the screen").
- **final:** not used (P04B: she swipes the feed).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–1 s: she stands barefoot, looking up and around in wonder, the phone held at her chest. 1–4 s: she scrolls with quick upward thumb flicks, one on every second beat, her eyes following something rising past her. 4–5 s: she stops, eyes fixed on one thing above her.
```

#### R03

Wan 3.0 image-to-video · 5 s · 1080p 16:9 · seed 1032 · $1.00

- **for:** S03 (0:12.71–0:14.51): her face lit by the screen, then the dive into it.
- **inputs:** first frame: sc-02-perf R03 #3.
- **take:** 150 frames at 30 fps (5.000 s), 1920×1080. Her hand enters at 2.2 s, the flick at about 3.0, a faint smile from 3.2.
- **v1:** S03.
- **final:** in the hook, at 1×, ending on its own last frame at 0:14.5.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. Native colour, cinematic, shallow focus; one continuous shot, no cuts. Close-up, she lies in the dark, her face lit cold from below by her phone screen. 0–2 s: her eyes move across the screen, reading. 2–2.6 s: a quick thumb flick (we see her eyes follow the content up). 2.6–5 s: her pupils catch the light, a faint smile; the screen light shifts colour across her face. The camera is still.
```

#### P09

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1008 · $1.00

- **for:** S09 (0:34.30–0:39.25): she stops before Screen Time's limit sheet.
- **inputs:** first frame: sc-02-perf P09 #3.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Hands on hips; one arm swings out (0.43–0.87 s) and touches the frame's edge, then she holds.
- **v1:** S09.
- **final:** re-dressed in the white satin skirt (SW-E2-P09).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized iridescent oil-slick satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–1 s: she is mid-dance. 1–1.5 s: she stops dead, hands on hips. 1.5–5 s: she faces something huge in front of her, unimpressed, one eyebrow raised; she shifts her weight and taps one foot twice.
```

#### P14

Wan 3.0 image-to-video · 8 s · 1080p 9:16 · seed 1013 · $1.60

- **for:** S14 (0:58.59–1:05.34): inside the wall-sized reel, then the shrug.
- **inputs:** first frame: sc-02-perf P14 #2.
- **take:** 240 frames at 30 fps (8.000 s), 1080×1920. Flicks at about 1.3, 1.7, 2.3, 2.85, 3.5 and 4.45 s, a glance up, the turn and the shrug at 6.3–6.7. A headset cable hangs to the floor in the footage; her crown leaves the frame in the shrug (feathered).
- **v1:** S14, its own map smoothed down to 0.53× in one stretch.
- **final:** S14, mapped at 1.02–1.26× with every flick on its kick.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (an oversized acid-green mohair sweater and white sleep shorts). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–1 s: she stands with her phone, looking at it. 1–5 s: she flicks the screen up with her thumb on every second beat, deadpan, glancing up as if something behind her changes each time. 5–6 s: she turns to the camera. 6–8 s: she gives a slow deadpan shrug, palms up.
```

#### P10

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1009 · $1.00

- **for:** S10 (0:39.25–0:43.30): she pushes the Ignore Limit pill until it gives way.
- **inputs:** first frame: sc-02-perf P10 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Side view, her palms on the frame's left edge: that edge is the contact line with the pill. Pushing to 3.0 s, giving way at 3.0–3.47, laughing after.
- **v1:** S10.
- **final:** re-dressed (SW-E2-P10), under Wan's repair with the face reference (WANF-S10).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized iridescent oil-slick satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Side view. 0–1 s: she leans forward with both palms flat on an invisible wall in front of her. 1–3.5 s: she pushes with her whole body, straining, her back foot sliding. 3.5–4.2 s: the invisible wall gives way and she stumbles forward two steps. 4.2–5 s: she catches herself and laughs.
```

#### P15

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1014 · $1.00

- **for:** S15 (1:05.34–1:09.84): "They call me Alexander Graham", on the receiver.
- **inputs:** first frame: sc-02-perf P15 #3 (a vintage handset, kept as a Bell joke).
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Crouched, the receiver at her ear, a hand in her hair from 2.4 s. The matte touches the frame's left, right and bottom edges, so the chapter framed her as a close-up on the right with her lower body falling into the dark.
- **v1:** S15.
- **final:** S15.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (an oversized acid-green mohair sweater and white sleep shorts). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Medium-full shot. 0–5 s: she holds the receiver to her ear and talks, amused, nodding, rolling her eyes, then laughing at what she hears; her free hand twirls the end of her hair.
```

#### P11

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S11 (0:43.30–0:48.70): the tunnel, the hardest flick.
- **inputs:** @Image1: sc-02-perf P11 #2 at 720 × 1280; @Audio1: the instrumental from 0:43.20, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. Spinning and dancing hard, arms and satin sweeping; she touches the side edges often (soft-faded in the chapter).
- **v1:** S11.
- **final:** re-dressed in the black skirt (SW-E2-P11). At 1× it ran 0.4 s short of the shot, which v2 covered with a one-beat freeze; in v3 a two-beat loop near the end of the shot replaced the freeze.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in oversized iridescent oil-slick satin pyjamas, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: from the pose in @Image1 she spins on the first beat, arms sweeping wide, the oversized satin flaring.
1-3s: hard two-step footwork with big arm sweeps, a sharp accent on every strong beat of @Audio1.
3-4s: a second full spin, landing exactly on a beat.
4-5s: she keeps dancing hard, arms cutting the air.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P12

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S12 (0:48.70–0:54.09): the stutter, "don't, don't let let me scroll".
- **inputs:** @Image1: sc-02-perf P12 #2 at 720 × 1280; @Audio1: the instrumental from 0:48.70, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. Small in its frame (her box is 0.74 of it). Shoulder hits and head snaps to 2.9 s, bouncing jumps after. 5.04 s of take for a 5.40 s shot.
- **v1:** S12, through a map that ran it at 0.51–0.94×.
- **final:** re-dressed in the black skirt (SW-E2-P12), played as a sampler at 1×.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in oversized iridescent oil-slick satin pyjamas, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: from the pose in @Image1, a sharp shoulder hit on the first beat.
1-3s: stuttering hits that follow the chopped rhythm of @Audio1: shoulder, shoulder, head snap, a freeze, then a double hit.
3-5s: she bounces through the rest, a sly smile, a final snap of the head on the last beat.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P18

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S18 (1:17.48–1:22.88): dancing in a reel that stands like a doorway.
- **inputs:** @Image1: sc-02-perf P18 #2 at 720 × 1280; @Audio1: the instrumental from 1:17.40, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. A full-length two-step; her feet touch the frame's bottom, and the hair flip touches its right edge. 169 hearts in the shot are thrown off where her matte moves.
- **v1:** S18.
- **final:** S18.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in an oversized acid-green mohair sweater and white sleep shorts, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: from the pose in @Image1 she lands a playful hop on the first beat.
1-3s: a bouncy swung two-step: little hops, heel-toe steps, arms bent, the mohair bouncing on every beat.
3-4s: a turn on the spot with a grin.
4-5s: she keeps hopping on the beat.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P19

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S19 (1:22.88–1:28.28): she spins in the column of posts.
- **inputs:** @Image1: sc-02-perf P19 #2 at 720 × 1280; @Audio1: the instrumental from 1:22.90, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. A spin to 0.9 s (her hair out of the top), the hand-in-hair pose, then bounces.
- **v1:** S19.
- **final:** not used. anabology: "1:24 - would do a differnet dance" (P19B).

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in an oversized acid-green mohair sweater and white sleep shorts, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: from @Image1 she spins once, landing on a beat.
1-2s: she lands a pose, one hand in her hair.
2-5s: she bounces on the beat, shoulders and knees, playful, a small skip on the strong beats.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P16

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1015 · $1.00

- **for:** S16 (1:09.84–1:13.89): the bell, and the buzz on "damn".
- **inputs:** first frame: sc-02-perf P16 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Medium; Wan's camera eases back 0–2.8 s; the flinch at 2.85–3.0, laughing after.
- **v1:** S16.
- **final:** S16, recomposed on thirds.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (an oversized acid-green mohair sweater and white sleep shorts). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Medium-full shot. 0–2 s: she looks up, curious. 2–2.4 s: she flinches as if the floor buzzed under her, shoulders jumping. 2.4–5 s: she bursts out laughing.
```

#### P17

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1016 · $1.00

- **for:** S17 (1:13.89–1:17.48): Wind Down; she lies on the glass, then taps it awake.
- **inputs:** first frame: sc-02-perf P17 #4.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. A low frontal view at floor level, curled on her side; heavy lids, eyes closed, then the two taps at 3.20–3.27 and 3.53–3.57 s. The take crops her at both sides. One frame's fingertip matte came out half transparent and was replaced by the next.
- **v1:** S17.
- **final:** under Wan's re-light with the face reference (WANF2-S17).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (an oversized acid-green mohair sweater and white sleep shorts). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–3 s: she lies on her side on the grey floor, head on her arm, sleepy, eyes closing slowly. 3–3.8 s: she lifts one finger and taps the floor twice. 3.8–5 s: she opens her eyes wide, awake.
```

#### P20

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1019 · $1.00

- **for:** S20 (1:28.28–1:31.43): down the canyon of app icons, the blazer on.
- **inputs:** first frame: sc-02-perf P20 #2.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. She walks toward the camera, swings the blazer on at 2.3–3.3 s and tugs the lapels.
- **v1:** S20.
- **final:** S20.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a black ribbed long-sleeve top and loose black satin trousers). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–2.5 s: she walks toward the camera, barefoot, a black blazer slung over one shoulder. 2.5–4 s: still walking, she swings the blazer on, one arm, then the other. 4–5 s: she tugs the lapels straight, all business.
```

#### P22

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1021 · $1.00

- **for:** S22 (1:37.28–1:40.87): under the lock screen's digits, "Locked In".
- **inputs:** first frame: sc-02-perf P22 #3.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Arms folded looking up to 2.6 s, then unfolded: the reverse of the prompt's order.
- **v1:** S22.
- **final:** under the blue-beat re-light (RL2-BLUE) and the digits re-light (RL2-DIGITS).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a sharp black blazer over a black ribbed top and loose black satin trousers). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–3 s: in the blazer she stands small and still, looking up at something enormous. 3–5 s: she folds her arms and narrows her eyes.
```

#### P23

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1022 · $1.00

- **for:** S23 (1:40.87–1:46.27): notifications rain round her as she hugs her knees.
- **inputs:** first frame: sc-02-perf P23 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. She looks up and lowers her chin onto her knees. Wan drew falling things the prompt only implied: a white object, a green yo-yo that falls onto her toes inside the matte, and a book on the floor. The chapter kept the matte's largest part and replaced her feet from a clean frame.
- **v1:** S23.
- **final:** under the digits re-light (RL2-DIGITS).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a black ribbed long-sleeve top and loose black satin trousers). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–5 s: she sits on the floor hugging her knees, looking up as things fall around her; she flinches slightly twice, then rests her chin on her knees.
```

#### P24

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S24 (1:46.27–1:51.22): the re-drop, her hardest dance.
- **inputs:** @Image1: sc-02-perf P24 #4 (anabology's correction of the lead's #2, which has three arms) at 720 × 1280; @Audio1: the instrumental from 1:46.20, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. Into the dance on the first beat, a hair flip at 2.2–2.6 s, a jump at 2.75–3.1 (her head leaves the top), fierce two-step to the end.
- **v1:** S24. anabology: "1:46 - LOVE THIS!"
- **final:** S24.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in a black ribbed long-sleeve top and loose black satin trousers, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: from the pose in @Image1 she explodes into her hardest dance on the first beat.
1-2s: fast footwork, arm hits cutting the air on every beat.
2-3s: a hair flip on the strong beat.
3-4s: a jump, landing exactly on a beat.
4-5s: driving two-step footwork, fierce.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P28 · the drop dance, Seedance (refused)

Seedance 2.5 reference-to-video · 8 s · 720p 9:16 · $3.70 (refunded)

- **for:** S28 (2:00.67–2:07.86), the final drop: her explosive dance in white satin.
- **inputs:** @Image1: sc-02-perf P28 #2 at 720 × 1280; @Audio1: the instrumental from 2:00.60, 8 s.
- **take:** Refused: "The generated result was blocked by content safety checks. Try a different prompt or reference media." Refunded.
- **v1:** —
- **final:** —

Prompt, rebuilt from its job builder, `tools/sddance.py`, which is unchanged since; the job file now holds the Wan request:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in oversized white silk-satin pyjamas, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-2s: on the first beat (the biggest drop of the song) she bursts into an explosive, joyful dance from the pose in @Image1, arms flung wide, head thrown back.
2-4s: big jumps and turns on the beat, the white satin flying.
4-6s: a full spin with her arms open, then bouncing two-step steps.
6-8s: free and euphoric, arms up, still landing every accent on the beat.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### G-B

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S28: her look-B self, dancing behind her in the final drop.
- **inputs:** @Image1: sc-02-perf G-B #2 at 720 × 1280; @Audio1: the instrumental from 2:00.60, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. Passed the filter in iridescent satin; arms leave the sides.
- **v1:** S28's ghost.
- **final:** re-dressed in the white shirt and black skirt (SW-E2-G-B), under Wan's repair of S28.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in oversized iridescent oil-slick satin pyjamas, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-2s: on the first beat she bursts into an explosive, joyful dance from the pose in @Image1, arms flung wide.
2-4s: a jump and a spin on the beat, the iridescent satin flying.
4-5s: arms up, bouncing on the beat.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P25

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1024 · $1.00

- **for:** S25 (1:51.22–1:55.27): "But I have to scroll" in the dying tunnel.
- **inputs:** first frame: sc-02-perf P25 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Head down over the phone; flicks from 1.13 to 2.47 s, weakening; her head droops 2.8–3.9 s. Her head touches the frame's top.
- **v1:** S25.
- **final:** S25.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a black ribbed long-sleeve top and loose black satin trousers). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–5 s: swaying, exhausted, she scrolls her phone with heavy thumb flicks that slow down, her head drooping, then jerking back up.
```

#### G-C

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S28: her look-C self.
- **inputs:** @Image1: sc-02-perf G-C #3 at 720 × 1280; @Audio1: the instrumental from 2:00.60, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. Passed; arms leave the sides.
- **v1:** S28's ghost.
- **final:** under Wan's repair of S28.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in an oversized acid-green mohair sweater and white sleep shorts, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-2s: on the first beat she bursts into an explosive, joyful dance from the pose in @Image1, arms flung wide.
2-4s: a jump and a spin on the beat, the mohair flying.
4-5s: arms up, bouncing on the beat.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### G-D

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S28: her look-D self.
- **inputs:** @Image1: sc-02-perf G-D #2 at 720 × 1280; @Audio1: the instrumental from 2:00.60, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. Passed; her figure leaves the bottom-left corner in the crouch at 2.9–3.4 s.
- **v1:** S28's ghost.
- **final:** under Wan's repair of S28.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in a black ribbed long-sleeve top and loose black satin trousers, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-2s: on the first beat she bursts into an explosive, joyful dance from the pose in @Image1, arms flung wide.
2-4s: a jump and a spin on the beat.
4-5s: arms up, bouncing on the beat.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P28 · the drop dance, Seedance again (refused)

Seedance 2.5 reference-to-video · 8 s · 720p 9:16 · $3.70 (refunded)

- **for:** S28, the same dance.
- **inputs:** @Image1: sc-02-perf P28 #4 at 720 × 1280; @Audio1: as before.
- **take:** Refused again, the same message; refunded. The shot went to Wan.
- **v1:** —
- **final:** —

Prompt, rebuilt from its job builder, `tools/sddance.py`, which is unchanged since; the job file now holds the Wan request:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone, in oversized white silk-satin pyjamas, barefoot. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-2s: on the first beat (the biggest drop of the song) she bursts into an explosive, joyful dance from the pose in @Image1, arms flung wide, head thrown back.
2-4s: big jumps and turns on the beat, the white satin flying.
4-6s: a full spin with her arms open, then bouncing two-step steps.
6-8s: free and euphoric, arms up, still landing every accent on the beat.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1; she never stops dancing.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, two arms and two legs, hands with five fingers, no extra or fused fingers, no distorted limbs; normal eyes.
4. No subtitles, captions, lyrics, titles, signs, logos, watermarks or any on-screen text; no lettering on her clothes.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.

【Audio Policy】 The output soundtrack is @Audio1 unchanged, copied sample for sample; no music, BGM, score, instrumental, melody, synth, pad, drone, riser, vocals, narration or sound effects added.
```

#### P13

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1012 · $1.00

- **for:** S13 (0:54.09–0:58.59): the slow dance among the pills at 0:55.
- **inputs:** first frame: sc-02-perf P13 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. A slow dance, her arms flowing; a clean matte. Its film was baked from her matte.
- **v1:** S13. anabology: "0:55 LOVE THIS. THis is the best part. more like this!!!!"
- **final:** re-dressed in the black skirt (SW-E2-P13).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized iridescent oil-slick satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–5 s: a slow, sensual dance: her arms flow above her head and down like smoke, her hips sway, her eyes half closed, the satin rippling with every move.
```

#### P29

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1027 · $1.00

- **for:** S29 (2:07.86–2:11.46): "Don't let me scroll", the film swirling round her.
- **inputs:** first frame: sc-02-perf P29 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Back to the camera, arms rising, she turns at 2.4–3.0 s and faces us, arms in an arch, eyes closed; her hands leave the top from 2.6.
- **v1:** S29.
- **final:** not used (P29B).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–5 s: she turns slowly on the spot, a full turn, arms rising above her head, eyes closed, serene.
```

#### P30

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1028 · $1.00

- **for:** S30 (2:11.46–2:16.86): the flowing dance; SCROLL torn by her arms.
- **inputs:** first frame: sc-02-perf P30 #2.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Long arm sweeps; arms wide from 4.2 s, her hands leaving the sides. The sweeps are slow, so the lead found the shot gentle.
- **v1:** S30.
- **final:** not used (P30B).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–5 s: a flowing dance with long arm sweeps, the white satin rippling; slow turns, deep and graceful.
```

#### P26

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1025 · $1.00

- **for:** S26 (1:55.27–1:57.07): the last flick, the freeze.
- **inputs:** first frame: sc-02-perf P26 #2.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Seated: a white stool seat appears in the matte from about 3.0 s. The flick at 1.07–1.45 s, a look up at the lens at 2.3–2.6, frozen wide-eyed after.
- **v1:** S26.
- **final:** S26.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a black ribbed long-sleeve top and loose black satin trousers). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Medium-full shot. 0–1 s: she looks at her phone. 1–1.4 s: one last hard thumb flick. 1.4–5 s: she freezes completely, wide-eyed, as if everything stopped.
```

#### P31

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 1029 · $1.00

- **for:** S31 (2:16.86–2:20.00): she taps Ask App Not to Track.
- **inputs:** first frame: sc-02-perf P31 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. A medium close-up pointing at the camera, the hand dropping at 2.75–3.1 s, then a smile.
- **v1:** S31.
- **final:** not used (P31B).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Medium-full shot. 0–2 s: she looks at something floating in front of her at chest height, reading. 2–2.6 s: she reaches out and taps it with one finger. 2.6–5 s: she lowers her hand and smiles, relieved.
```

#### P28 · the drop dance, Wan

Wan 3.0 image-to-video · 8 s · 1080p 9:16 · seed 1026 · $1.60

- **for:** S28, the drop dance, after Seedance refused it twice.
- **inputs:** first frame: sc-02-perf P28 #4.
- **take:** 240 frames at 30 fps (8.000 s), 1080×1920. Crouched, head back, then a jump at 2.6–2.85 s (arms and head leave the top), a hair flip at about 4.5, big kicks and flings to 8 s. Grey motion-blur wisps in the matte on fast limbs.
- **v1:** S28.
- **final:** not used (P28B, in the red coat dress).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. She moves to a fast UK garage two-step beat at 133 BPM: sharp accents on the beat every 0.45 seconds, loose and bouncy between. 0–8 s: an explosive, joyful dance: arms flung wide, head thrown back, big jumps and spins, free and euphoric, the white satin flying.
```

#### P32

Wan 3.0 image-to-video · 6 s · 1080p 9:16 · seed 1030 · $1.20

- **for:** S32 (2:20.00–2:25.85): "Be free", walking into the light.
- **inputs:** first frame: sc-02-perf P32 #2.
- **take:** 180 frames at 30 fps (6.000 s), 1080×1920. From behind she walks slowly away, shrinking from 0.93 to 0.46 of the frame's height.
- **v1:** S32.
- **final:** not used (P32B).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain mid-grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. 0–6 s: seen from behind, she walks slowly away from the camera, barefoot, arms loose, shoulders relaxing, toward the back of the studio.
```

#### R27

Wan 3.0 image-to-video · 5 s · 1080p 16:9 · seed 1033 · $1.00

- **for:** S27 (1:57.07–2:00.67): her face in the dead phone's black glass.
- **inputs:** first frame: sc-02-perf R27 #1.
- **take:** 150 frames at 30 fps (5.000 s), 1920×1080. She stares, blinks at 2.13–2.3 s; the phone moves away and shows the satin; her breath fogs the glass at 2.5 s and clears by about 4. The take is bright and was darkened for "near darkness".
- **v1:** S27: the fog on the glass became the film's first colour after the phone died.
- **final:** S27: the glass contracts into a pill round her eyes.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. Native colour, cinematic, shallow focus; one continuous shot, no cuts. Near darkness. Extreme close-up of the dead black phone screen in her hands, her face faintly reflected in the glass. 0–5 s: she stares at her own reflection, blinks slowly, her breath fogging the glass for a moment. Almost no movement.
```

#### R33

Wan 3.0 image-to-video · 8 s · 1080p 16:9 · seed 1034 · $1.60

- **for:** S33 (2:25.85–2:33.05): dawn at the window.
- **inputs:** first frame: sc-02-perf R33 #2.
- **take:** 240 frames at 30 fps (8.000 s), 1920×1080. Back view, arms out at the window, lowering, then she sits on the bed's edge. 24 fps content inside a 30 fps file, with blended frames; Wan's camera dollies in.
- **v1:** S33.
- **final:** not used: the escape replaced the dawn.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. Native colour, cinematic, shallow focus; one continuous shot, no cuts. The real bedroom at dawn, golden sunrise through the floor-to-ceiling window. 0–8 s: she stands at the window in white satin, stretches her arms out slowly, the sun rising, the city waking; the camera drifts very slowly.
```

#### R34

Wan 3.0 image-to-video · 8 s · 1080p 16:9 · seed 1035 · $1.60

- **for:** S34 (2:33.05–2:39.35): she plugs the phone in and leaves.
- **inputs:** first frame: sc-02-perf R34 #1.
- **take:** 240 frames at 30 fps (8.000 s), 1920×1080. She plugs a white cable into a phone on a white bedside block; its screen lights with Wan's own lock screen, which the chapter darkened and replaced along a tracked outline; she gets up and leaves.
- **v1:** S34.
- **final:** not used.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. Native colour, cinematic, shallow focus; one continuous shot, no cuts. The real bedroom at dawn, golden light. 0–3 s: on the bed, she plugs the charging cable into her phone. 3–4 s: she sets the phone down on the sheets; its screen lights up. 4–8 s: she gets up and walks out of frame toward the window; the phone glows on the empty bed. The camera is still.
```

#### R35

Wan 3.0 image-to-video · 5 s · 1080p 16:9 · seed 1036 · $1.00

- **for:** S35 (2:39.35–2:40.80): "I scroll on X", the loop.
- **inputs:** first frame: sc-02-perf R35 #2.
- **take:** 150 frames at 30 fps (5.000 s), 1920×1080. She already looks back over her shoulder in the first frame and turns away by the end: the opposite of the prompt. v1 played it backwards.
- **v1:** S35.
- **final:** not used.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (oversized white silk-satin pyjamas). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. Native colour, cinematic, shallow focus; one continuous shot, no cuts. The real bedroom at dawn. 0–2 s: she stands at the window, her back to the bed. 2–3 s: the phone on the bed lights up. 3–5 s: she turns her head back over her shoulder toward it, slowly.
```

### The re-light samples · 4 submissions · $47.81 at list

#### RL-DIGITS

Seedance 2.5 video-edit · 8 s · 1080p · $17.77

- **for:** v1's 1:38.6–1:46.2: the lock screen's digits (S22) into the notification rain (S23). anabology: "relight the scene adn the numbers/letters to be ray traced liquid glass with chromatic aberration and prismatic effects".
- **inputs:** @Video1: v1's own frames, 7.625 s (183 frames at 24 fps); @Image1 and @Image2: two pictures from the liquid-glass moodboard (lg006, lg022).
- **take:** 177 frames at 24 fps (7.375 s), 1920×1080. Shorter than its 183-frame source. "the 4:13 digits come back as thick liquid glass with prismatic pink, violet and green edges. All the UI text and lyrics survive crisp. It was conservative on the later cards" (the lead).
- **v1:** —
- **final:** not used: a sample, made before the composition changed.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only the materials and the lighting. The giant clock numerals, the padlock shackle, the floor and the falling notification cards are re-rendered as ray-traced liquid glass in a physically lit space: thick, smooth, polished glass that refracts and magnifies what is behind it, with chromatic aberration splitting every edge into red, green and blue fringes, and prismatic dispersion throwing small moving rainbow caustics across the floor and across Claudia.

【Role of the Source Video】
@Video1 is the sole editing master. It contains two shots joined by one hard cut. It governs every shape, outline, position and motion, Claudia's face, body, pose and movements, the camera position and the camera moves (a slow drift in the first shot; a crane up and away from her in the second), the cut, the occlusion between objects, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the glass material of the numerals: clear liquid glass with soft rounded edges, smooth internal refraction and a faint iridescent sheen; do not use its shape, its lettering or its black background.
@Image2 is used only for the prismatic light: rainbow dispersion along glass edges and rainbow caustics cast onto nearby surfaces; do not use its bolt and rod shapes or its composition.

【Edit Objects and Scope】
1. First shot, Claudia standing: the tall translucent violet numerals "4:13" that stand behind and around her become thick liquid glass with exactly the same shapes, sizes and positions; they still read clearly as 4:13. The thin arc of a padlock shackle that lowers around her becomes a polished glass tube with the same chromatic edges.
2. Second shot, Claudia crouching: the frosted numerals behind her, which count up from 4:13 to 4:50, become the same liquid glass and keep counting exactly as in @Video1.
3. The coloured notification cards that fall, tumble and pile up on the floor in the second shot become thin slabs of tinted glass in the same colours, on the same paths, landing at the same moments in the same places; they catch and bend the light.
4. The floor becomes polished black glass with true mirror reflections of Claudia, the numerals and the cards.
5. The dark violet background becomes a deep space of soft violet, indigo and teal light with gentle volumetric haze, lit by the glass.
6. Lighting: path-traced global illumination. The glass numerals and cards refract and split the light; small rainbow caustics drift across the floor and across Claudia's black clothes and face as the glass moves. Claudia is lit naturally by the scene, with a soft cool rim light from the glass behind her.
Do not modify Claudia: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek, in her black outfit; her face, expression, pose and every movement stay exactly as in @Video1, with natural anatomy and hands with five fingers. Do not modify any interface graphic: the status bar at the top, the black Dynamic Island pill with its white words and its red waveform, the date "Sat Oct 17", the Reminders notification, and the Low Battery and Low Power banners keep their exact words, shapes, colours, positions and timing. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every object inherits the appearance timing, path, speed and occlusion of its counterpart in @Video1. The numerals count up exactly as in @Video1, the hard cut stays at the same moment, and both camera moves stay as in @Video1.
```

#### RL-RIVER

Seedance 2.5 video-edit · 3 s · 1080p · $7.16

- **for:** v1's 0:31.0–0:34.3: the river (S08). anabology: "light the scene with ray tracing and beautiful lighting as if it's a real room".
- **inputs:** @Video1: v1's frames, 3.292 s (79 frames).
- **take:** 89 frames at 24 fps (3.709 s), 1920×1080. Longer than its 79-frame source: no edit came back shorter than 89 frames. "the plain re-light is too subtle in edit mode".
- **v1:** —
- **final:** not used: a sample.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only the lighting and the surface materials: re-light this room made of glowing photo screens as a real physical room, path-traced, as if it were filmed on a real set.

【Role of the Source Video】
@Video1 is the sole editing master. It governs every screen tile's position, image and motion, Claudia's face, pose and dance, the camera, the event order and the timing, frame by frame.

【Edit Objects and Scope】
1. The walls, floor and ceiling of photo tiles become real glossy screens set behind glass in a physical room: each tile keeps its image and its motion, including the smeared streaks of the scrolling images, and emits its image as light; that light spills and bounces onto the floor, the other walls and Claudia, mixing their colours.
2. The floor tiles get a glossy glass finish with soft ray-traced reflections of the walls, the ceiling and Claudia, and soft contact shadows under her feet.
3. The air holds a thin volumetric haze lit by the screens.
4. The iridescent flame-shaped glow around Claudia's legs becomes real luminous soap-film light in the same shape and motion, casting coloured light onto her and onto the floor.
5. Claudia is lit by the room: coloured light from the surrounding screens on her clothes and skin, a soft key light from the screens in front of her and a rim light from behind.
Do not modify Claudia: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek, in iridescent satin pyjamas; her face, pose and every dance movement stay exactly as in @Video1, with natural anatomy and hands with five fingers. The black pill with the white words "DON'T LET ME SCROLL", the status bar and the Dynamic Island at the top keep their exact words, shapes, positions and timing. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every tile, streak and movement keeps the timing and speed of @Video1; Claudia's dance and the camera stay as in @Video1.
```

#### RL-RIVER-DRESS

Seedance 2.5 video-edit · 3 s · 1080p · $7.16

- **for:** The same shot with her outfit changed: a test of re-dressing ("no more silver pajamas by this point please").
- **inputs:** @Video1: the same 79 frames; the outfit described in words.
- **take:** 89 frames at 24 fps (3.709 s), 1920×1080. "Seedance re-dressed her in a white ballet top and lilac tulle skirt with the same dance and the same face": the test that made the swaps possible.
- **v1:** —
- **final:** not used: a sample.

Prompt:

```
【Editing Goal】
Edit @Video1, changing Claudia's outfit and re-lighting the scene: her iridescent satin pyjamas become a feminine dream-world outfit, and this room made of glowing photo screens is re-lit as a real physical room, path-traced, as if it were filmed on a real set.

【Role of the Source Video】
@Video1 is the sole editing master. It governs every screen tile's position, image and motion, Claudia's face, body, pose and every dance movement, the camera, the event order and the timing, frame by frame.

【Edit Objects and Scope】
1. Claudia's iridescent satin pyjamas are replaced by a feminine dream-world outfit: a fitted white long-sleeve ballet top with a soft scoop neck, a knee-length layered skirt of pale iridescent lilac tulle that catches rainbow light, white ankle socks and silver ballet flats. The skirt sways and flares naturally with every step and turn of her dance. Only her clothes change: her face, hair, star clip, headset microphone, body, pose and every movement stay exactly as in @Video1.
2. The walls, floor and ceiling of photo tiles become real glossy screens set behind glass in a physical room: each tile keeps its image and its motion, including the smeared streaks of the scrolling images, and emits its image as light; that light spills and bounces onto the floor, the other walls and Claudia, mixing their colours.
3. The floor tiles get a glossy glass finish with soft ray-traced reflections of the walls, the ceiling and Claudia, and soft contact shadows under her feet.
4. The air holds a thin volumetric haze lit by the screens.
5. The iridescent flame-shaped glow around Claudia's legs becomes real luminous soap-film light in the same shape and motion, casting coloured light onto her and onto the floor.
6. Claudia is lit by the room: coloured light from the surrounding screens on her clothes and skin, a soft key light from the screens in front of her and a rim light from behind.
Claudia is one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; she stays one person with natural anatomy and hands with five fingers. The black pill with the white words "DON'T LET ME SCROLL", the status bar and the Dynamic Island at the top keep their exact words, shapes, positions and timing. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every tile, streak and movement keeps the timing and speed of @Video1; Claudia's dance, the swing of her new skirt following it, and the camera stay as in @Video1.
```

#### RL-E

Seedance 2.5 video-edit · 7 s · 1080p · $15.73

- **for:** v1's 0:23.1–0:29.9: the E (S06–S07). anabology: "give it the entire E scene, tell it to move the tweets inward, fill the environment with beautiful glass acidblur lighting, reredner the E to be a better mateiral".
- **inputs:** @Video1: v1's frames, 6.834 s (164 frames); @Image1: liquid glass (lg006); @Image2 and @Image3: two acid-blur pictures (ab001, ab007).
- **take:** 161 frames at 24 fps (6.709 s), 1920×1080. Shorter than its 164-frame source. "the E becomes one solid glass letter, which also fixes the broken top bar. It adds MOD-style light streaks, but it didn't move the tweets inward or fill the world lushly." Seedance re-textures; the recomposition is done in code.
- **v1:** —
- **final:** not used: a sample.

Prompt:

```
【Editing Goal】
Edit @Video1: keep Claudia, her movements, the camera and the timing, and re-render the world around her lushly. The giant letter E becomes a monumental sculpture of thick polished liquid glass, the open sky and the plain floor fill with beautiful glass acid-blur light, and the two post cards move inward so that each sits fully inside the frame.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, pose and every movement, the camera position and the camera moves, the rise of the E out of the floor, the arrival of the second post card and the rocket launching inside it, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the material of the letter E: clear liquid glass with smooth rounded edges, internal refraction and an iridescent sheen; do not use its shape, its lettering or its background.
@Image2 is used only for the light in the environment: vertical streaks of smeared, saturated colour light like a long-exposure scan; do not use its lettering, its border or its layout.
@Image3 is used only for soft acid colour light: a blurred glow of magenta, violet, acid green and warm orange; do not use its composition or its lettering.

【Edit Objects and Scope】
1. The giant letter E becomes one continuous, solid monumental sculpture of thick polished liquid glass with crisp, clean, straight edges and softly rounded corners; its stem and three bars form one solid letterform with no overlapping or broken parts. It refracts the sunset and the coloured light behind it, splits its edges into fine rainbow fringes and casts a soft caustic glow onto the floor. It rises out of the floor with exactly the timing, size and position of @Video1.
2. The environment: the pink and violet sunset sky stays as the backdrop, and the space between the sky and the floor fills with tall translucent panes of frosted glass standing at different depths, glowing with smeared vertical streaks of acid colour light in magenta, violet, electric blue, acid green and warm orange; soft volumetric haze and bokeh; the light drifts slowly.
3. The floor becomes a dark polished glass plain with long mirror reflections of the E, the glass panes, the colour light and Claudia.
4. The two black post cards move inward toward the centre so that each card sits fully inside the frame with a clear margin from the frame edges: the first card reads "The big man in Texas: E," and the second reads "He runs SpaceX, for free" and shows a rocket launching. Each card keeps its size, tilt, words, image and timing; the small price tag "$0.00" stays with the second card.
5. Lighting: path-traced; the coloured light falls on Claudia's white satin clothes and skin as soft coloured reflections and a rim light.
Do not modify Claudia: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek, in white satin pyjamas; her face, pose and every movement stay exactly as in @Video1, with natural anatomy and hands with five fingers. The black Dynamic Island pill and the status bar at the top keep their shape, position and timing. Every word on the cards stays exactly as written. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
The E rises, the second card arrives and its rocket launches with exactly the timing, paths and speeds of @Video1; Claudia's movements and the camera moves stay as in @Video1.
```

### The first outfit swaps, in the pink look (dropped) · 8 submissions · $64.08 at list

#### SW-E-P12

Seedance 2.5 video-edit · 5 s · 720p · $4.65

- **for:** P12's take re-dressed in the dream-world look anabology picked first (e2-pink-2).
- **inputs:** @Video1: P12's take 1; @Image1: e2-pink-2 (the pink cardigan and the lavender pleated skirt).
- **take:** 121 frames at 24 fps (5.042 s), 720×1280. Delivered, and never reviewed or cut in.
- **v1:** —
- **final:** not used: anabology changed the look to the white shirt.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E-P11

Seedance 2.5 video-edit · 5 s · 720p · $4.65

- **for:** P11's take re-dressed in the dream-world look anabology picked first (e2-pink-2).
- **inputs:** @Video1: P11's take 1; @Image1: e2-pink-2 (the pink cardigan and the lavender pleated skirt).
- **take:** 121 frames at 24 fps (5.042 s), 720×1280. Delivered, and never reviewed or cut in.
- **v1:** —
- **final:** not used: anabology changed the look to the white shirt.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E-G-B

Seedance 2.5 video-edit · 5 s · 720p · $4.65

- **for:** G-B's take re-dressed in the dream-world look anabology picked first (e2-pink-2).
- **inputs:** @Video1: G-B's take 1; @Image1: e2-pink-2 (the pink cardigan and the lavender pleated skirt).
- **take:** 121 frames at 24 fps (5.042 s), 720×1280. Delivered, and never reviewed or cut in.
- **v1:** —
- **final:** not used: anabology changed the look to the white shirt.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E-P08

Seedance 2.5 video-edit · 5 s · 720p · $4.65

- **for:** P08's take re-dressed in the dream-world look anabology picked first (e2-pink-2).
- **inputs:** @Video1: P08's take 2; @Image1: e2-pink-2 (the pink cardigan and the lavender pleated skirt).
- **take:** 121 frames at 24 fps (5.042 s), 720×1280. Delivered, and never reviewed or cut in.
- **v1:** —
- **final:** not used: anabology changed the look to the white shirt.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E-P09

Seedance 2.5 video-edit · 5 s · 1080p · $11.37

- **for:** P09's take re-dressed in the dream-world look anabology picked first (e2-pink-2).
- **inputs:** @Video1: P09's take 1; @Image1: e2-pink-2 (the pink cardigan and the lavender pleated skirt).
- **take:** 113 frames at 24 fps (4.709 s), 1080×1920. Delivered, and never reviewed or cut in.
- **v1:** —
- **final:** not used: anabology changed the look to the white shirt.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E-P10

Seedance 2.5 video-edit · 5 s · 1080p · $11.37

- **for:** P10's take re-dressed in the dream-world look anabology picked first (e2-pink-2).
- **inputs:** @Video1: P10's take 1; @Image1: e2-pink-2 (the pink cardigan and the lavender pleated skirt).
- **take:** 113 frames at 24 fps (4.709 s), 1080×1920. Delivered, and never reviewed or cut in.
- **v1:** —
- **final:** not used: anabology changed the look to the white shirt.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E-P13

Seedance 2.5 video-edit · 5 s · 1080p · $11.37

- **for:** P13's take re-dressed in the dream-world look anabology picked first (e2-pink-2).
- **inputs:** @Video1: P13's take 1; @Image1: e2-pink-2 (the pink cardigan and the lavender pleated skirt).
- **take:** 113 frames at 24 fps (4.709 s), 1080×1920. Delivered, and never reviewed or cut in.
- **v1:** —
- **final:** not used: anabology changed the look to the white shirt.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E-P06

Seedance 2.5 video-edit · 5 s · 1080p · $11.37

- **for:** P06's take re-dressed in the dream-world look anabology picked first (e2-pink-2).
- **inputs:** @Video1: P06's take 1; @Image1: e2-pink-2 (the pink cardigan and the lavender pleated skirt).
- **take:** 113 frames at 24 fps (4.709 s), 1080×1920. Delivered, and never reviewed or cut in.
- **v1:** —
- **final:** not used: anabology changed the look to the white shirt.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized white silk-satin pyjamas with the outfit from @Image1: a cropped baby-pink mohair cardigan with pearl buttons, a pleated pearlescent lavender satin mini skirt, white knee socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

### The escape · 1 submission · $17.06 at list

#### ESC-W4

Seedance 2.5 reference-to-video · 15 s · 1080p 16:9 · $17.06

- **for:** S33–S35 (2:25.85–2:40.80), the escape: anabology: "she should enter a world with no phones, like escaping the truman show. it should be grand, art house, almost like wes anderson"; "w4 exit 1 feels best, if we did a zoom in shot".
- **inputs:** @Image1: w4-exit-1 (cut to 1920 × 1080), the first frame and the world; @Image2: f3-red-2, her look only.
- **take:** 361 frames at 24 fps (15.042 s), 1920×1080. Read by eye: the grand wide to 6 s (she is about 50 px tall on the stair), the zoom closing and the door opening 6–10 s, the top step and the door 10–12 s, the head turn at 12.6–13.1 s, eye contact and a small smile 13.1–14.25, the turn away 14.3–14.6, then the light. The turn comes just before "I": at "I" she is already looking at us.
- **v1:** —
- **final:** S34, frame-locked at 1× (song frame n shows take frame n − 3499); the push into its light (S33) and the painted sign (S35) are drawn over it.

Prompt:

```
【Generation Goal】
Generate one continuous, grand art-house shot: Claudia climbs a white staircase that runs up a vast wall painted to look like the sky, toward a small open door full of warm golden light, while the camera slowly zooms in toward the door; at the top she looks back once, then steps through into the light.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the starting composition and the world: a calm sea in the foreground, a vast flat wall painted as a pale blue sky with soft clouds rising straight out of the sea, banks of cloud at its foot, a white staircase climbing diagonally along the wall to a small open door full of warm golden light, and the camera's direction.
@Image2 is used only for Claudia's appearance and clothes: a woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip, a thin headset microphone at her cheek, a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black patent shoes. Do not use the pink staircase, the background or the framing of @Image2.

【Event Script】
0-3s: The shot begins on the first frame. Claudia, small in the frame, is on the lower part of the white staircase, climbing toward the door with steady, unhurried steps, one hand trailing along the painted wall. The sea glitters and the clouds drift slowly.
3-10s: The camera slowly and smoothly zooms in toward the door, keeping it near the centre of the frame, while Claudia keeps climbing step by step; close up, the clouds on the wall read as painted brushstrokes on a flat surface.
10-13s: Claudia reaches the top step in front of the open door; warm golden light from the doorway falls across her red coat and her face; the zoom continues until the doorway and Claudia fill the middle of the frame.
13-15s: Claudia pauses on the threshold, turns her head back over her shoulder toward the camera with a small, free smile, then steps through the door into the light.

【Camera】
One continuous shot with no cuts: a slow, steady zoom in from the wide first frame toward the door, ending close on the doorway with Claudia in it.

【Maintain Consistency】
Only one Claudia appears; her face, hair, star clip, microphone, red coat dress, beret, socks and shoes stay as defined by @Image2, with natural anatomy and hands with five fingers. The staircase, the painted sky wall, the door and the sea stay as defined by @Image1. No other people, no phones or screens, and no text, signs, logos or watermarks.
```

### v2's takes in looks C, D and F · 8 submissions · $13.87 at list

#### P21B

Wan 3.0 image-to-video · 7 s · 1080p 9:16 · seed 2001 · $1.40

- **for:** S21: no phone in her hand; she works a giant screen in the air.
- **inputs:** first frame: v2-02-acts a21-swipe #2 (look D).
- **take:** 210 frames at 30 fps (7.000 s), 1080×1920. A floating holographic glass panel stands where the invisible screen should be.
- **v1:** —
- **final:** not used: made again as P21C.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a black ribbed top, an oversized black blazer and loose black satin trousers). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. She faces a giant invisible screen in front of her at chest height. 0–1 s: she lifts her right hand toward it, focused. 1–2 s: a firm swipe sideways across the air. 2–3 s: a second swipe. 3–4 s: a third swipe, then a quick tap in the air with her index finger. 4–5.5 s: she leans in, eyes wide, lips parting in surprise. 5.5–7 s: she laughs and does a small fist pump.
```

#### P30B

Wan 3.0 image-to-video · 6 s · 1080p 9:16 · seed 2004 · $1.20

- **for:** S30 (2:11.46–2:16.13; v2 moved the boundaries of S30–S32): the SCROLL masthead dance in look F.
- **inputs:** first frame: v2-02-acts a30-flow #1.
- **take:** 180 frames at 30 fps (6.000 s), 1080×1920. Wan's camera eases back (her height from 0.98 to 0.77 of the frame). The lite matte lost her motion-blurred back shoe for a few frames and kept a sliver of heel shadow; anabology: "roto could be better on shoe at 0:18". BiRefNet's full general model, run again, fixed both.
- **v1:** —
- **final:** under Wan's repair with the face reference (WANF-S30).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black patent shoes). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. A slow, flowing dance: 0–2 s: her arms sweep in wide arcs as she shifts her weight from one leg to the other. 2–4 s: a gentle turn on the spot, the coat dress swinging. 4–6 s: she opens both arms wide and holds the pose with a soft sway, eyes closed; both hands stay inside the frame.
```

#### P32B

Wan 3.0 image-to-video · 7 s · 1080p 9:16 · seed 2006 · $1.40

- **for:** S32 (2:20.91–2:25.85): the climb up the pill staircase.
- **inputs:** first frame: v2-02-acts a32-stairs #3.
- **take:** 210 frames at 30 fps (7.000 s), 1080×1920. Its first 1.6 s she looks back over her shoulder, which the film never shows (S32 starts at 2.007 s of the take); then five steps up.
- **v1:** —
- **final:** S32.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black patent shoes). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. Seen from behind, she climbs a white staircase away from the camera, one step on every beat, steady and unhurried, her arms swinging lightly; she stays inside the frame from head to feet the whole time.
```

#### P29B · the arch, first take

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed not kept · $1.00

- **for:** S29 (2:07.86–2:11.46): the arch, her hands rising into the island.
- **inputs:** first frame: v2-02-acts a29-turn #4.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Her legs turned backwards, from the still. anabology: "bodyslop at 0:12 - her feet /legs are backwards lol. need different ref".
- **v1:** —
- **final:** not used: made again (P29B).

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black patent shoes). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. 0–1 s: she stands still, eyes closed. 1–3.5 s: she slowly raises both arms up into a high arch above her head. 3.5–5 s: she tilts her head back a little, eyes closed, serene, swaying gently.
```

#### P31B

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 2005 · $1.00

- **for:** S31 (2:16.13–2:20.91): she taps Ask App Not to Track on "soul".
- **inputs:** first frame: v2-02-acts a31-tap #3.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Her arm out from the first frame, the finger cocks, the tap at 2.2 s (on "soul"), a push on the accent, a smile from 3.2.
- **v1:** —
- **final:** S31.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black patent shoes). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. 0–2.4 s: she holds her arm out to the side at shoulder height, index finger hovering over a button in the air, a small smile. 2.5–2.8 s: she presses it with one small, decisive tap. 3–5 s: she lowers her arm and smiles, relieved and free.
```

#### P28B

Seedance 2.5 reference-to-video · 8 s · 720p 9:16 · $3.70

- **for:** S28 (2:00.67–2:07.86): the final drop in look F.
- **inputs:** @Image1: v2-02-acts a28-drop #1 at 720 × 1280; @Audio1: the instrumental from 1:59.90, 8 s.
- **take:** 193 frames at 24 fps (8.064 s), 720×1280. At 1× the drop lands on 0.80 s of the take, as she bursts out of the crouch; the jump peaks at 1.75 s and lands on a kick. Thin grey squiggles in the matte beside her hands for about three frames.
- **v1:** —
- **final:** under Wan's repair of S28.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek, in a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black patent shoes. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: she stays coiled low in the crouch of @Image1, still, gathering; on the huge downbeat of @Audio1 just before the 1-second mark she explodes upward.
1-3s: a big jump with both arms flung wide, peaking at about 2.5 seconds, the red coat dress flaring; she lands on a beat.
3-5s: driving two-step footwork with sharp arm hits on every beat, fierce and joyful.
5-6s: a full spin, landing exactly on a beat.
6-8s: arms up, bouncing on the beat, euphoric; her whole body and both hands stay inside the frame.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.
```

#### P19B

Seedance 2.5 reference-to-video · 6 s · 720p 9:16 · $2.77

- **for:** S19 (1:22.88–1:28.28): anabology's "differnet dance", look C.
- **inputs:** @Image1: v2-02-acts a19-dance #2 at 720 × 1280; @Audio1: the instrumental from 1:22.80, 6 s.
- **take:** 145 frames at 24 fps (6.080 s), 720×1280. Her spin whirls the column of posts. Her sleeves leave the frame for about four frames in the spin; the roto left a soft grey ghost of her floor shadow and holes where her legs cross, patched in the chapter.
- **v1:** —
- **final:** under Wan's sleeve repair (WAN-S19).

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek, in an oversized acid-green mohair sweater and white sleep shorts. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: from the pose in @Image1 she sways her hips into a playful step on the first beat, eyes half closed, smiling.
1-3s: a bouncy swung two-step: shoulders and hips pop on every beat, arms loose, the mohair bouncing.
3-4s: she turns once on the spot and lands facing the camera exactly on a beat.
4-6s: she keeps bouncing on the beat and runs one hand through her hair on the strong beat, laughing.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.
```

#### P21C

Wan 3.0 image-to-video · 7 s · 1080p 9:16 · seed 2101 · $1.40

- **for:** S21 (1:31.43–1:37.28): the stocks scene, no phone in her hand.
- **inputs:** first frame: v2-02-acts a21-swipe #2.
- **take:** 210 frames at 30 fps (7.000 s), 1080×1920. "P21C is good. The panel is gone, leaving only tiny touch marks at her fingertip". Wan drew focus brackets round her fingertip at three touches; they were keyed out and the glass answers each touch with its own ripple. The interface is keyed to the take's time, so it stays under her fingertips.
- **v1:** —
- **final:** under Wan's re-light with the face reference (WANF-S21), the interface kept from the original render.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a black ribbed top, an oversized black blazer and loose black satin trousers). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. She mimes using a giant screen in the empty air in front of her at chest height; nothing is visible in the air: no screen, no panel, no glass, no hologram, no light, no interface, her hands move through empty space. 0–1 s: she lifts her right hand toward it, focused. 1–2 s: a firm swipe sideways across the air. 2–3 s: a second swipe. 3–4 s: a third swipe, then a quick tap in the air with her index finger. 4–5.5 s: she leans in, eyes wide, lips parting in surprise. 5.5–7 s: she laughs and does a small fist pump.
```

### The white-shirt swaps · 8 submissions · $64.08 at list

#### SW-E2-P13

Seedance 2.5 video-edit · 5 s · 1080p · $11.37

- **for:** S13 (0:54.09–0:58.59): the take re-dressed in the white "morning after" shirt over the black pleated skirt.
- **inputs:** @Video1: P13's take 1; @Image1: s2-black-2.
- **take:** 113 frames at 24 fps (4.709 s), 1080×1920. Same face, the moves intact. It was aligned first on her silhouette, which the new skirt had changed: that fit (the edit's time scaled by 1.060 and shifted by 0.5 s) froze half a second at the start of 0:55. Aligned again by the ratio of the lengths and registered as P13's take 3.
- **v1:** —
- **final:** S13.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E2-P09

Seedance 2.5 video-edit · 5 s · 1080p · $11.37

- **for:** S09 (0:34.30–0:39.25): the take re-dressed in the white "morning after" shirt over the white satin skirt.
- **inputs:** @Video1: P09's take 1; @Image1: s3-white-2.
- **take:** 113 frames at 24 fps (4.709 s), 1080×1920. Same face, the moves intact. Aligned to the original timeline by the ratio of the lengths, checked on her hair (r 0.846), and registered as P09's take 2.
- **v1:** —
- **final:** S09.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short white satin A-line skirt, white socks and white ballet flats — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short white satin A-line skirt, white socks and white ballet flats. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E2-P10

Seedance 2.5 video-edit · 5 s · 1080p · $11.37

- **for:** S10 (0:39.25–0:43.30): the take re-dressed in the white "morning after" shirt over the white satin skirt.
- **inputs:** @Video1: P10's take 1; @Image1: s3-white-2.
- **take:** 113 frames at 24 fps (4.709 s), 1080×1920. Same face, the moves intact. Aligned to the original timeline by the ratio of the lengths, checked on her hair (r 0.944), and registered as P10's take 2.
- **v1:** —
- **final:** S10, under Wan's repair (WANF-S10): Seedance's frame cut her back foot, which the chapter faded until Wan restored it.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short white satin A-line skirt, white socks and white ballet flats — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short white satin A-line skirt, white socks and white ballet flats. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E2-P08

Seedance 2.5 video-edit · 5 s · 720p · $4.65

- **for:** S08 (0:30.70–0:34.30): the take re-dressed in the white "morning after" shirt over the white satin skirt.
- **inputs:** @Video1: P08's take 2 (the Seedance dance); @Image1: s3-white-2.
- **take:** 121 frames at 24 fps (5.042 s), 720×1280. Same face, the moves intact. Aligned to the original timeline by the ratio of the lengths, checked on her hair (r 0.869), and registered as P08's take 3.
- **v1:** —
- **final:** S08, under the river's re-light (RL2-RIVER); its first three frames show it directly.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short white satin A-line skirt, white socks and white ballet flats — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short white satin A-line skirt, white socks and white ballet flats. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E2-G-B

Seedance 2.5 video-edit · 5 s · 720p · $4.65

- **for:** S28's dream-self (2:00.67–2:07.86): the take re-dressed in the white "morning after" shirt over the black pleated skirt.
- **inputs:** @Video1: G-B's take 1; @Image1: s2-black-2.
- **take:** 121 frames at 24 fps (5.042 s), 720×1280. Same face, the moves intact. Aligned to the original timeline by the ratio of the lengths, checked on her hair (r 0.813), and registered as G-B's take 2.
- **v1:** —
- **final:** S28, under Wan's repair of S28.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E2-P11

Seedance 2.5 video-edit · 5 s · 720p · $4.65

- **for:** S11 (0:43.30–0:48.70): the take re-dressed in the white "morning after" shirt over the black pleated skirt.
- **inputs:** @Video1: P11's take 1; @Image1: s2-black-2.
- **take:** 121 frames at 24 fps (5.042 s), 720×1280. Same face, the moves intact. Aligned to the original timeline by the ratio of the lengths, checked on her hair (r 0.881), and registered as P11's take 2.
- **v1:** —
- **final:** S11.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E2-P06

Seedance 2.5 video-edit · 5 s · 1080p · $11.37

- **for:** S06 (0:23.06–0:26.21): the take re-dressed in the white "morning after" shirt over the lavender satin skirt.
- **inputs:** @Video1: P06's take 1; @Image1: s1-lavender-1.
- **take:** 113 frames at 24 fps (4.709 s), 1080×1920. Same face, the moves intact. Aligned to the original timeline by the ratio of the lengths, checked on her hair (r 0.998), and registered as P06's take 2.
- **v1:** —
- **final:** S06, under the E's re-light (RL2-E).

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short pleated lavender satin skirt, white socks and white Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized white silk-satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short pleated lavender satin skirt, white socks and white Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### SW-E2-P12

Seedance 2.5 video-edit · 5 s · 720p · $4.65

- **for:** S12 (0:48.70–0:54.09): the take re-dressed in the white "morning after" shirt over the black pleated skirt.
- **inputs:** @Video1: P12's take 1; @Image1: s2-black-2.
- **take:** 121 frames at 24 fps (5.042 s), 720×1280. Same face, the moves intact. Aligned to the original timeline by the ratio of the lengths, checked on her hair (r 0.713), and registered as P12's take 2. Its first attempt stopped before reaching the API: one parallel upload read the uploads cache while another was writing it. It was submitted again.
- **v1:** —
- **final:** S12, as the sampler at 1×.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's clothes: she now wears the outfit shown in @Image1.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, hair, body, pose and every movement, the plain grey backdrop, the floor, the light, the framing and the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the outfit: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes — its garments, cut, colours, fabrics and shoes. Do not use the person, the pose, the background or the framing of @Image1.

【Edit Objects and Scope】
1. Replace Claudia's oversized iridescent oil-slick satin pyjamas with the outfit from @Image1: an oversized white men's button-down shirt, half-tucked into a short black pleated skirt, white socks and black Mary Jane shoes. The new garments fit her body and move naturally with every movement in @Video1: the fabric swings, folds and flares with her motion.
2. Do not modify Claudia herself: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, hair, star clip and headset microphone stay exactly as in @Video1. She stays one person with natural anatomy and hands with five fingers.
3. The plain grey backdrop, the floor, the light and the framing stay exactly as in @Video1. No new objects and no text appear.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

### The lavender takes · 4 submissions · $5.51 at list, $4.51 after refunds

#### P04B

Wan 3.0 image-to-video · 6 s · 1080p 9:16 · seed 2000 · $1.20

- **for:** S04 (0:14.51–0:19.01): "she could reach over and scroll up with her arm".
- **inputs:** first frame: v2-04-shirtacts a04-swipe #3 (look E, lavender).
- **take:** 180 frames at 30 fps (6.000 s), 1080×1920. Three swipes (1.47–1.70, 2.27–2.47 and 4.60–4.77 s), the reach leaving the frame's top, bounces between; played at 1.21× so the swipes land on the beat. The chapter locks the feed to her measured palm.
- **v1:** —
- **final:** S04.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (an oversized white men's shirt half-tucked into a short pleated lavender satin skirt, white socks and white Mary Jane shoes). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. She is playful and delighted. 0–1 s: she reaches up high with her right arm toward a giant screen above her. 1–2 s: she swipes her open palm upward through the air, scrolling it. 2–3 s: a second swipe up, laughing. 3–6 s: she bounces lightly on her toes, smiling up at what she scrolled, then swipes once more.
```

#### P05B · the double-tap (refused)

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 2001 · $1.00 (refunded)

- **for:** S05 (0:19.01–0:23.06): the double-tap in the air.
- **inputs:** first frame: v2-04-shirtacts a05-tap #3: she leans toward the camera and points at the lens.
- **take:** Refused by Higgsfield: status "nsfw" ("Generation failed"), refunded. The project's notes read that status as a flag on the output. The lead put it down to the leaning staging and restaged it.
- **v1:** —
- **final:** —

Prompt, rebuilt from the job builder's version of that hour (`tools/v2takes.py`, in the project's history) with the same wardrobe; the job file now holds the restaged request:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (an oversized white men's shirt half-tucked into a short pleated lavender satin skirt, white socks and white Mary Jane shoes). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. 0–1 s: she leans toward the camera, index finger raised. 1–1.6 s: she taps the air twice with her fingertip, a quick double-tap. 1.6–3.5 s: her face lights up with delight, a small laugh, both hands coming to her chest. 3.5–5 s: she hugs herself, glowing.
```

#### P07B

Seedance 2.5 reference-to-video · 5 s · 720p 9:16 · $2.31

- **for:** S07 (0:26.21–0:30.70): a joyful spin in place of v1's stretch.
- **inputs:** @Image1: v2-04-shirtacts a06-spin #3 at 720 × 1280; @Audio1: the instrumental from 0:26.10, 5 s.
- **take:** 121 frames at 24 fps (5.056 s), 720×1280. Spin, two-step, a second spin. Its frame cuts her wrists in 98 of 121 frames, so the two posts float in front of the cut sides. White shorts under the skirt show for a few frames in the spin, as in any skirt spin; kept.
- **v1:** —
- **final:** S07: under the E's re-light to 0:29.75, directly after.

Prompt:

```
【Audio Policy】 @Audio1 is the song's instrumental, used for rhythm and timing only. The output soundtrack is @Audio1 unchanged, copied sample for sample from the first frame to the last. Do not add music, background music, score, instrumental, melody, synth, pad, drone, riser, vocals, singing, humming, narration or sound effects.

【Generation Goal】 Claudia dances to @Audio1 in an empty grey studio: a full-body dance performance for a music video, every step and accent landing on the beat of @Audio1.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines Claudia's appearance and wardrobe, her pose, the plain grey studio, the light and the full-length camera framing.
@Audio1 is the music she dances to: rhythm and timing only.

【Subject】 Claudia: a Caucasian American woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek, in an oversized white men's shirt half-tucked into a short pleated lavender satin skirt, white socks and white Mary Jane shoes. Only one Claudia appears.

【Performance】 Claudia does not sing or speak: her mouth stays closed or in a natural smile throughout. She dances with the rhythm of @Audio1 from the very first frame, continuing the motion of her pose in @Image1 with no pause:
0-1s: from the pose in @Image1 she spins on the first beat, arms open wide, the skirt flaring.
1-3s: a bouncy, feminine swung two-step, hips and shoulders on every beat, the oversized shirt swinging.
3-4s: a second spin, landing exactly on a beat, laughing.
4-5s: she keeps dancing on the beat, arms loose, free.

【Camera】 A locked-off full-length frame on a tripod: the camera never moves, pans or zooms; her whole body stays inside the frame from head to feet the whole time; the plain grey backdrop stays empty and evenly lit.

【Core Requirements】
1. Every step, bounce and accent lands on the beat of @Audio1.
2. Keep Claudia's identity, face, hair with one clay-orange streak, star clip, headset microphone and wardrobe exactly as in @Image1 throughout.
3. Natural anatomy: natural neck and shoulders, hands with five fingers, no extra or fused fingers, no distorted limbs.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 She dances on the beat of @Audio1 for the whole clip, full body in frame, one Claudia on-model with natural anatomy, no on-screen text; the soundtrack is @Audio1 unchanged.
```

#### P05B · the double-tap, restaged

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 2001 · $1.00

- **for:** S05, restaged: upright, she double-taps the post above her, following on from the swipe.
- **inputs:** first frame: v2-04-shirtacts a04-swipe #2.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Taps at 1.17–1.20 and 1.47–1.53 s, a laugh and a bounce, the clap at 3.63–4.03. At exactly 1× from the hit, the taps fall on the stabs at 0:20.19 and 0:20.52 and the clap on the hit at 0:22.61.
- **v1:** —
- **final:** S05.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (an oversized white men's shirt half-tucked into a short pleated lavender satin skirt, white socks and white Mary Jane shoes). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. She looks up at a giant screen above her, delighted. 0–1 s: she points her raised index finger up at one spot on it. 1–1.6 s: she taps that spot twice in the air with her fingertip, a quick double-tap. 1.6–3.5 s: her face lights up, she laughs and gives a small happy bounce on her toes. 3.5–5 s: she claps her hands once and smiles up at it.
```

### The bedroom re-light · 1 submission · $11.42 at list

#### RL-R02

Seedance 2.5 video-edit · 5 s · 1080p · $11.42

- **for:** The hook's bedroom take (S01–S02 in v2), in the lead's words: "soft, dim next to the graphics".
- **inputs:** @Video1: the R02 take resampled to 24 fps, 121 frames (5.042 s).
- **take:** 121 frames at 24 fps (5.042 s), 1920×1080. Frame for frame. Judged alone by the lead: "darker and a touch softer than the original", kept out. anabology: "the first re-light is behind the animation thought right?  like, weonly see that scene behind the hyperbloom starting animation right? can we see how it looks w/ vs w/o the relight?" Side by side in the pills, the cooler screen light read better. anabology: "New better."
- **v1:** —
- **final:** the hook (R02's take 2).

Prompt:

```
【Editing Goal】
Edit @Video1, changing only the lighting, the focus and the image quality: re-light this night scene in a dark bedroom as a crisp, high-end cinematic shot filmed on a large-sensor camera with a fast prime lens.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's face, expression, gaze, hair, body, pose and every movement, the phone in her hand and its motion, the bed and the sheets, the window and the city behind it, the framing, the camera, the event order and the timing, frame by frame.

【Edit Objects and Scope】
1. Focus and clarity: Claudia's face, eyes, freckles, hair, star clip and hands are in crisp, sharp focus with fine natural skin texture; the city lights outside the window stay soft round bokeh.
2. Light: the phone's screen is the key light, a cool clean white-blue glow that lights her face, her eyes with small catchlights and her fingers from below, rising and falling exactly as the phone moves in @Video1; while the phone lies under her hand its glow spills onto the sheets and her fingers. A faint warm rim light from the city glow outlines her hair and shoulder. The room stays dark, with deep clean blacks and no grey haze.
3. Materials: her white satin pyjamas show soft real satin highlights from the screen light; the white sheets catch the glow.
4. Image: clean low-noise night photography with a fine film grain; no colour grade beyond the light itself.
Do not modify Claudia: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek; her face, expression, gaze direction, pose and every movement stay exactly as in @Video1, with natural anatomy and hands with five fingers. The phone keeps its shape, size and position, its screen facing her as in @Video1. No text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last, and the camera stays as in @Video1.
```

### The turn again · 1 submission · $1.00 at list

#### P29B · the arch, second take

Wan 3.0 image-to-video · 5 s · 1080p 9:16 · seed 2006 · $1.00

- **for:** S29, made again.
- **inputs:** first frame: v2-02-acts a29-turn #3, knees and feet forward.
- **take:** 150 frames at 30 fps (5.000 s), 1080×1920. Elbows out, arms wide, hands to her face, up into the arch; at 1× from 1.3 s of the take her accents land within about 15 ms of the snares and kicks, and her fingertips rise into the island.
- **v1:** —
- **final:** S29.

Prompt:

```
Image 1 is the first frame. Keep the woman exactly as in Image 1 throughout: her face, her glossy black blunt bob with heavy bangs and its one clay-orange streak, the small clay-orange star hair clip, the thin headset microphone, and her clothes (a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black patent shoes). Only one woman appears; natural anatomy, five fingers on each hand, no extra limbs; no text, no logos, no lettering on her clothes. The plain grey studio backdrop stays empty and evenly lit. The camera is locked off on a tripod and never moves, pans or zooms; her whole body stays inside the frame from head to feet the entire time. Native colour, one continuous shot, no cuts. 0–1 s: she stands still, eyes closed. 1–3.5 s: she slowly raises both arms up into a high arch above her head. 3.5–5 s: she tilts her head back a little, eyes closed, serene, swaying gently.
```

### v2's re-lights of the cut · 4 submissions · $51.18 at list

#### RL2-RIVER

Seedance 2.5 video-edit · 4 s · 1080p · $8.77

- **for:** S08 (0:30.83–0:34.30) in the final composition: the river as a real room.
- **inputs:** @Video1: the cut's own frames, 83 of the window plus 6 after it, 89 frames (3.709 s).
- **take:** 89 frames at 24 fps (3.709 s), 1920×1080. Frame for frame. "The type survives the re-light at 100%: a touch softer, still clean and legible".
- **v1:** —
- **final:** S08, spliced over the window.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only the lighting and the surface materials: re-light this room made of glowing photo screens as a real physical room, path-traced, as if it were filmed on a real set.

【Role of the Source Video】
@Video1 is the sole editing master. It governs every screen tile's position, image and motion, Claudia's face, pose and dance, her clothes, the camera, the event order and the timing, frame by frame.

【Edit Objects and Scope】
1. The walls, floor and ceiling of photo tiles become real glossy screens set behind glass in a physical room: each tile keeps its image and its motion, including the smeared streaks of the scrolling images, and emits its image as light; that light spills and bounces onto the floor, the other walls and Claudia, mixing their colours.
2. The floor tiles get a glossy glass finish with soft ray-traced reflections of the walls, the ceiling and Claudia, and soft contact shadows under her feet.
3. The air holds a thin volumetric haze lit by the screens.
4. The iridescent flame-shaped glow around Claudia's legs becomes real luminous soap-film light in the same shape and motion, casting coloured light onto her and onto the floor.
5. Claudia is lit by the room: coloured light from the surrounding screens on her clothes and skin, a soft key light from the screens in front of her and a rim light from behind.
Do not modify Claudia: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek, in an oversized white men's shirt with the sleeves pushed up, half-tucked into a short white satin A-line skirt, white socks and white ballet flats; her face, pose, clothes and every dance movement stay exactly as in @Video1, with natural anatomy and hands with five fingers. The black pill with the white words "DON'T LET ME SCROLL", the status bar and the Dynamic Island at the top keep their exact words, shapes, positions and timing. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every tile, streak and movement keeps the timing and speed of @Video1; Claudia's dance and the camera stay as in @Video1.
```

#### RL2-DIGITS

Seedance 2.5 video-edit · 8 s · 1080p · $18.05

- **for:** S22's lock screen into S23 (1:38.46–1:46.27): ray-traced liquid glass.
- **inputs:** @Video1: the cut's frames, 188 of the window plus 1, 189 frames (7.875 s); @Image1 and @Image2: lg006, lg022.
- **take:** 185 frames at 24 fps (7.709 s), 1920×1080. Four frames short of its source, so the splice maps them by the ratio. The digits, the shackle and the falling cards became glass. Seedance smeared the Reminders notification, so the original card was put back over it, its rectangle tracked frame by frame over 48 frames.
- **v1:** —
- **final:** S22–S23, spliced.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only the materials and the lighting. The giant clock numerals, the padlock shackle, the floor and the falling notification cards are re-rendered as ray-traced liquid glass in a physically lit space: thick, smooth, polished glass that refracts and magnifies what is behind it, with chromatic aberration splitting every edge into red, green and blue fringes, and prismatic dispersion throwing small moving rainbow caustics across the floor and across Claudia.

【Role of the Source Video】
@Video1 is the sole editing master. It contains two shots joined by one hard cut. It governs every shape, outline, position and motion, Claudia's face, body, pose, clothes and movements, the camera position and the camera moves (a slow drift in the first shot; a crane up and away from her in the second), the cut, the occlusion between objects, every interface graphic, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the glass material of the numerals: clear liquid glass with soft rounded edges, smooth internal refraction and a faint iridescent sheen; do not use its shape, its lettering or its black background.
@Image2 is used only for the prismatic light: rainbow dispersion along glass edges and rainbow caustics cast onto nearby surfaces; do not use its bolt and rod shapes or its composition.

【Edit Objects and Scope】
1. First shot, Claudia standing on the lock screen: the tall translucent violet numerals "4:13" that stand behind and around her become thick liquid glass with exactly the same shapes, sizes and positions; they still read clearly as 4:13. The thin arc of a padlock shackle that lowers around her becomes a polished glass tube with the same chromatic edges.
2. Second shot, Claudia crouching: the frosted numerals behind her, which count up from 4:13 to 4:51, become the same liquid glass and keep counting exactly as in @Video1.
3. The coloured notification cards that rain down, tumble and pile up on the floor in the second shot become thin slabs of tinted glass in the same colours, on the same paths, landing at the same moments in the same places; they catch and bend the light.
4. The floor becomes polished black glass with true mirror reflections of Claudia, the numerals and the cards.
5. The dark violet background becomes a deep space of soft violet, indigo and teal light with gentle volumetric haze, lit by the glass.
6. Lighting: path-traced global illumination. The glass numerals and cards refract and split the light; small rainbow caustics drift across the floor and across Claudia's black clothes and face as the glass moves. Claudia is lit naturally by the scene, with a soft cool rim light from the glass behind her.
Do not modify Claudia: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek, in a black ribbed top, an oversized black blazer and loose black satin trousers; her face, expression, pose and every movement stay exactly as in @Video1, with natural anatomy and hands with five fingers. Do not modify any interface graphic: the status bar at the top with its time and battery, the black Dynamic Island pill with its white words and its red waveform, the date "Sat Oct 17", the Reminders notification, and the Low Battery and Low Power Mode banners keep their exact words, shapes, colours, positions and timing. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every object inherits the appearance timing, path, speed and occlusion of its counterpart in @Video1. The numerals count up exactly as in @Video1, the hard cut stays at the same moment, and both camera moves stay as in @Video1.
```

#### RL2-BLUE

Seedance 2.5 video-edit · 4 s · 1080p · $8.77

- **for:** S22's first 1.2 s (1:37.29–1:38.46): the flat LinkedIn-blue bridge. anabology: "ya re-imagine - you can totally replace backgrounds with seedance btw. but yeah sounds good relight it".
- **inputs:** @Video1: the cut's frames, 28 of the window padded with real frames after it to 89 (3.709 s).
- **take:** 89 frames at 24 fps (3.709 s), 1920×1080. Frame for frame. "a dark glass atrium of tall blue light columns, with a polished floor reflecting her. The reel card and the pouring reels are unchanged."
- **v1:** —
- **final:** S22, spliced.

Prompt:

```
【Editing Goal】
Edit @Video1: keep Claudia, the tall LinkedIn reel card beside her, the interface at the top, the camera and the timing, and replace the flat blue background of the first shot with a real, physically lit space: LinkedIn's world re-imagined as a vast glass atrium at night.

【Role of the Source Video】
@Video1 is the sole editing master. It contains two shots joined by one hard cut. It governs Claudia's face, body, pose, clothes and every movement, the position, size and motion of the reel card and of the columns of reels on both sides, every interface graphic, the camera, the cut, the event order and the timing, frame by frame.

【Edit Objects and Scope】
1. First shot, before the cut: the flat blue background becomes a vast, real architectural space at night: a tall glass atrium of a corporate tower lit in deep LinkedIn blue, its walls made of tall vertical glass screens that rise out of the top of the frame and play vertical videos; the columns of reels on the left and right become real glowing screens in those walls, their images streaming downward like waterfalls of light; a polished dark stone floor with long mirror reflections of the screens, of Claudia and of the card; soft volumetric blue haze with shafts of light; path-traced global illumination.
2. The tall reel card beside her (the post that reads "They put reels on LinkedIn" above "Follow Claudia") keeps its words, picture, shape, size, position and motion exactly; it becomes a bright glass screen standing in the atrium and casts its colourful light onto the floor and onto her.
3. Claudia is lit by the room: cool blue light from the screen walls, colourful spill from the reel card beside her, a soft rim light, a soft contact shadow and her reflection on the polished floor.
4. Second shot, after the cut: unchanged.
Do not modify Claudia: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek, in a black ribbed top, an oversized black blazer and loose black satin trousers; her face, expression, pose, clothes and every movement stay exactly as in @Video1, with natural anatomy and hands with five fingers. The status bar and the black Dynamic Island pill with its LinkedIn icon and red waveform at the top keep their exact shapes, positions and timing. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every object inherits the timing, path and speed of its counterpart in @Video1; the cut stays at the same moment, and the camera stays as in @Video1.
```

#### RL2-E

Seedance 2.5 video-edit · 7 s · 1080p · $15.59

- **for:** S06–S07 (0:23.06–0:29.75): the E, after chapter 02's rebuild.
- **inputs:** @Video1: the cut's frames, 161 (6.709 s); @Image1: lg006; @Image2 and @Image3: ab001, ab007.
- **take:** 161 frames at 24 fps (6.709 s), 1920×1080. Frame for frame. "The E re-light (0:23–0:30) came out bold. The whole dusk sky is now a psychedelic thin-film swirl and the E is a puffy liquid-glass letter." Kept; the plain render was offered back.
- **v1:** —
- **final:** S06–S07, spliced.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only the materials and the lighting of the world around Claudia: the giant letter E becomes a monumental sculpture of thick polished liquid glass, and the dusk sky, the horizon and the plain floor fill with beautiful glass acid-blur light.

【Role of the Source Video】
@Video1 is the sole editing master. It contains two shots joined by one hard cut. It governs Claudia's face, body, pose, clothes and every movement, every shape, outline, position and motion, the rise of the E, the post cards and their content, the camera and its moves, the cut, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the material of the letter E: clear liquid glass with smooth rounded edges, internal refraction and an iridescent sheen; do not use its shape, its lettering or its background.
@Image2 is used only for the light in the environment: vertical streaks of smeared, saturated colour light like a long-exposure scan; do not use its lettering, its border or its layout.
@Image3 is used only for soft acid colour light: a blurred glow of magenta, violet, acid green and warm orange; do not use its composition or its lettering.

【Edit Objects and Scope】
1. The giant white letter E becomes one continuous, solid monumental sculpture of thick polished liquid glass with crisp straight edges and softly rounded corners; its stem and three bars form one solid letterform. It refracts the dusk sky and the coloured light behind it, splits its edges into fine rainbow fringes and casts a soft caustic glow onto the floor. It rises, jolts and locks with exactly the timing, size and position of @Video1.
2. The environment: the pink and violet dusk sky stays the backdrop; between the sky and the floor, tall translucent panes of frosted glass stand at different depths, glowing with smeared vertical streaks of acid colour light in magenta, violet, electric blue, acid green and warm orange; soft volumetric haze and bokeh; the light drifts slowly.
3. The floor becomes a dark polished glass plain with long mirror reflections of the E, the glass panes, the colour light, the post cards and Claudia.
4. The floating dark post cards, which read "The big man in Texas: E," and "He runs SpaceX, for free", keep their exact words, pictures, shapes, sizes, positions and motion, and so does the small price tag "$0.00"; the cards become slabs of dark glass that catch the colour light along their edges.
5. Lighting: path-traced; the coloured light falls on Claudia's white shirt, lavender satin skirt and skin as soft coloured reflections and a rim light.
Do not modify Claudia: one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek, in an oversized white men's shirt half-tucked into a short pleated lavender satin skirt, white socks and white Mary Jane shoes; her face, pose, clothes and every movement stay exactly as in @Video1, with natural anatomy and hands with five fingers. Every word on the cards stays exactly as written. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
The E rises and locks, the cards rise and the tag swings with exactly the timing, paths and speeds of @Video1; Claudia's movements, both camera setups and the cut stay as in @Video1.
```

### v3: Wan relight-and-repair · 5 submissions · $11.20 at list

#### WAN-S30

Wan 3.0 reference-to-video · 5 s · 1080p 16:9 · $2.00 (includes 5 s of input video)

- **for:** S30 (2:11.46–2:16.13): anabology: "similar cutout issue at 2:13ish for that scene with her hands going off the edges of her bounding box".
- **inputs:** Video 1: the cut's frames of the shot, 112, with the last held to 5 s (120 frames).
- **take:** 150 frames at 30 fps (5.000 s), 1920×1080. Her hands complete. Wan turned the warm grey paper blue-grey and darker, its mean level from about 172 to about 113 with red falling furthest; one per-channel gain and offset (`tools/colormatch.py`) brought it back to about 168.
- **v1:** —
- **final:** in v3; replaced in the final by the face-reference pass (WANF-S30).

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black shoes; she dances exactly as in Video 1. Her whole body stays complete in every frame: both arms end in complete, natural hands with five fingers, never cut off or faded at any edge, and both feet are complete. The giant black letters SCROLL across the top, with the iridescent thin-film light inside them, keep their exact shapes, positions and timing. Re-light the scene as a real photographic studio: a soft grey paper backdrop and floor, a soft key light, a gentle contact shadow under her feet, native colour.
```

#### WAN-S17

Wan 3.0 reference-to-video · 4 s · 1080p 16:9 · $1.60 (includes 4 s of input video)

- **for:** S17 (1:13.89–1:17.48): anabology: "need a new pose/ reshoot for 1:14 - get rid of her foot lol".
- **inputs:** Video 1: the cut's frames of the shot, 87, with the last held to 4 s (96 frames).
- **take:** 120 frames at 30 fps (4.000 s), 1920×1080. "the stray foot is gone. Wan re-rendered the shot so she sits naturally in a real-looking dark bedroom, with the clock and cards intact". The dark scene came back brighter (mean about 28 → 45), matched back.
- **v1:** —
- **final:** in v3; replaced by WANF-S17, then WANF2-S17.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in an oversized acid-green mohair sweater; her face, expression, pose and every movement stay exactly as in Video 1. Remove the stray bare foot and leg that appear beside her at the lower right of her body: there is nothing there but the dark room, and her body continues naturally below the frame. Re-light the scene as a real dark bedroom at night, lit by the cool glow of the giant glass clock numerals and the moon: soft violet and blue light on her face and sweater, a gentle rim light, deep clean blacks, a faint haze. The clock numerals, the moon, the notification cards with their words, the status bar and the black Dynamic Island at the top stay exactly as in Video 1, sharp and legible.
```

#### WAN-S10

Wan 3.0 reference-to-video · 5 s · 1080p 16:9 · $2.00 (includes 5 s of input video)

- **for:** S10 (0:39.25–0:43.30): anabology: "0:40 - the cutout of her - she loses her right foot".
- **inputs:** Video 1: the cut's frames, 97, with the last held to 5 s (120 frames).
- **take:** 150 frames at 30 fps (5.000 s), 1920×1080. "her back foot is complete while she pushes the pill, and the pill is now glass". The scene came back brighter (mean about 67 → 85), matched back.
- **v1:** —
- **final:** in v3; replaced by WANF-S10.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in an oversized white men's shirt over a short white satin skirt, white socks and white ballet flats; she leans in and pushes against the large glowing glass pill with both palms exactly as in Video 1. Her whole body stays complete in every frame: both legs and both feet are fully visible and complete, her back foot planted on the floor, never cut off or faded at any edge. Re-light the room of glowing photo screens on the walls and floor as a real physical room, path-traced: the screens emit their images as light that bounces onto her, the floor and the pill; soft glossy reflections on the floor, a thin volumetric haze. The pill and its words and the line "You keep asking me to go" keep their exact words, positions and timing, sharp and legible.
```

#### WAN-S28

Wan 3.0 reference-to-video · 8 s · 1080p 16:9 · $3.20 (includes 8 s of input video)

- **for:** S28 (2:00.67–2:07.86): her hands leave the frame in the drop's jump (found by the lead).
- **inputs:** Video 1: the cut's frames, 173, with the last held to 8 s (192 frames).
- **take:** 240 frames at 30 fps (8.000 s), 1920×1080. Her hands complete. The paper came back darker (mean levels about 161 → 110), matched back to about 159.
- **v1:** —
- **final:** S28, spliced.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black shoes; she bursts up out of a crouch into a big jump and dances exactly as in Video 1. Her whole body stays complete in every frame: both arms end in complete, natural hands with five fingers and both feet are complete, never cut off or faded at any edge. The large black rounded pills that slam in from the sides, with her other selves dancing inside their windows, and the iridescent thin-film light inside the black, keep their exact shapes, positions, contents and timing. Re-light the scene as a real photographic studio: a soft grey paper backdrop and floor, a soft key light, a gentle contact shadow under her, native colour.
```

#### WAN-S19

Wan 3.0 reference-to-video · 6 s · 1080p 16:9 · $2.40 (includes 6 s of input video)

- **for:** S19 (1:22.88–1:28.28): her sleeves leave the frame in the spin (found by the lead).
- **inputs:** Video 1: the cut's frames, 130, with the last held to 6 s (144 frames).
- **take:** 180 frames at 30 fps (6.000 s), 1920×1080. Her sleeves complete. The dark scene came back brighter (mean about 34 → 53), matched back.
- **v1:** —
- **final:** S19, spliced.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in an oversized acid-green mohair sweater and white sleep shorts; she dances exactly as in Video 1, spinning with her arms out. Her whole body stays complete in every frame: both arms end in complete, natural hands with five fingers and her sleeves are never cut off or faded at any edge. The tall column of glowing picture posts beside her keeps its posts and the big white words BUT, I, HAVE, TO, SCROLL, DON'T, LET ME stacked on it, exactly as in Video 1, sharp and legible. Re-light the scene as a real dark space: the column's screens emit their pictures as light that falls on her sweater and the floor, soft reflections on a dark glossy floor, a faint haze, deep clean blacks.
```

### The face reference · 4 submissions · $8.00 at list

#### WANF-S17

Wan 3.0 reference-to-video · 4 s · 1080p 16:9 · $1.60 (includes 4 s of input video)

- **for:** S17 again: anabology: "1:11 and 0:36 reshoots lose her face consistency - can you feed in a good face ref? […] its too fat in 1:11".
- **inputs:** Video 1: the original render of the shot (as WAN-S17); Image 1: face 1, DOWNFORCE's identity portrait cropped to her face.
- **take:** 120 frames at 30 fps (4.000 s), 1920×1080. Slimmer, but still full: anabology: "1:11 her face is still too fat." The chin tucked into the collar was the cause.
- **v1:** —
- **final:** not used: replaced by WANF2-S17.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Image 1 is the face of the woman: keep her face exactly as in Image 1 in every frame — the same facial structure, a slim, angular adult face with defined cheekbones and jaw, the same eyes, nose, lips, freckles and skin; her slim, slender build stays exactly as in Video 1. Image 1 is only a reference for her face; it is never shown as a shot. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in an oversized acid-green mohair sweater; her face, expression, pose and every movement stay exactly as in Video 1. Remove the stray bare foot and leg that appear beside her at the lower right of her body: there is nothing there but the dark room, and her body continues naturally below the frame. Re-light the scene as a real dark bedroom at night, lit by the cool glow of the giant glass clock numerals and the moon: soft violet and blue light on her face and sweater, a gentle rim light, deep clean blacks, a faint haze. The clock numerals, the moon, the notification cards with their words, the status bar and the black Dynamic Island at the top stay exactly as in Video 1, sharp and legible.
```

#### WANF-S30

Wan 3.0 reference-to-video · 5 s · 1080p 16:9 · $2.00 (includes 5 s of input video)

- **for:** S30 again, with the face reference: "her face is a bit wrong at the re-lit 2:13 scene as well […] re-do the relighting with the face ref added from the original scene".
- **inputs:** Video 1: the original render (as WAN-S30); Image 1: face 1.
- **take:** 150 frames at 30 fps (5.000 s), 1920×1080. Her face held; the paper matched back from a mean of about 111 to about 169 (the original about 172).
- **v1:** —
- **final:** S30, spliced.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Image 1 is the face of the woman: keep her face exactly as in Image 1 in every frame — the same facial structure, a slim, angular adult face with defined cheekbones and jaw, the same eyes, nose, lips, freckles and skin; her slim, slender build stays exactly as in Video 1. Image 1 is only a reference for her face; it is never shown as a shot. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in a red tailored coat dress with a wide white collar, a matching red beret, white knee socks and black shoes; she dances exactly as in Video 1. Her whole body stays complete in every frame: both arms end in complete, natural hands with five fingers, never cut off or faded at any edge, and both feet are complete. The giant black letters SCROLL across the top, with the iridescent thin-film light inside them, keep their exact shapes, positions and timing. Re-light the scene as a real photographic studio: a soft grey paper backdrop and floor, a soft key light, a gentle contact shadow under her feet, native colour.
```

#### WANF-S10

Wan 3.0 reference-to-video · 5 s · 1080p 16:9 · $2.00 (includes 5 s of input video)

- **for:** S10 again, with the face reference ("looks off in the 0:36").
- **inputs:** Video 1: the original render (as WAN-S10); Image 1: face 1.
- **take:** 150 frames at 30 fps (5.000 s), 1920×1080. Her face held, the back foot whole.
- **v1:** —
- **final:** S10, spliced.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Image 1 is the face of the woman: keep her face exactly as in Image 1 in every frame — the same facial structure, a slim, angular adult face with defined cheekbones and jaw, the same eyes, nose, lips, freckles and skin; her slim, slender build stays exactly as in Video 1. Image 1 is only a reference for her face; it is never shown as a shot. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in an oversized white men's shirt over a short white satin skirt, white socks and white ballet flats; she leans in and pushes against the large glowing glass pill with both palms exactly as in Video 1. Her whole body stays complete in every frame: both legs and both feet are fully visible and complete, her back foot planted on the floor, never cut off or faded at any edge. Re-light the room of glowing photo screens on the walls and floor as a real physical room, path-traced: the screens emit their images as light that bounces onto her, the floor and the pill; soft glossy reflections on the floor, a thin volumetric haze. The pill and its words and the line "You keep asking me to go" keep their exact words, positions and timing, sharp and legible.
```

#### WANF-S21

Wan 3.0 reference-to-video · 6 s · 1080p 16:9 · $2.40 (includes 6 s of input video)

- **for:** S21, never re-lit before: "did we relight the 1:29 scene? thats the only other place where her face gets lost again - so we could use a face ref there too".
- **inputs:** Video 1: the cut's frames of the shot, 141, padded to 6 s (144 frames); Image 1: face 1.
- **take:** 180 frames at 30 fps (6.000 s), 1920×1080. "1:29 (the stocks scene) now reads as her face"; the interface platter and the status bar were kept from the original render by two keep-rectangles.
- **v1:** —
- **final:** S21, spliced.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Image 1 is the face of the woman: keep her face exactly as in Image 1 in every frame — the same facial structure, a slim, angular adult face with defined cheekbones and jaw, the same eyes, nose, lips, freckles and skin; her slim, slender build stays exactly as in Video 1. Image 1 is only a reference for her face; it is never shown as a shot. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in a black ribbed top and an oversized black blazer; she stands behind a large clear glass screen and swipes and taps it exactly as in Video 1, her hands complete with five fingers. The glass screen's interface keeps its exact words, numbers, charts, positions and timing. Re-light the scene as a real, physically lit space: the giant glass wall refracts the light with soft chromatic fringes, the room behind her is a soft out-of-focus space lit by the screen's green and red light, which falls on her face and blazer; native colour, deep clean blacks.
```

### S17 again: options A and B · 2 submissions · $10.70 at list

#### SDF-S17

Seedance 2.5 video-edit · 4 s · 1080p · $9.10

- **for:** S17 (1:11 in the final cut, 1:14 in the song), option A: a Seedance edit toward the face reference.
- **inputs:** @Video1: the original render of S17 (96 frames); @Image1: face 1.
- **take:** 89 frames at 24 fps (3.709 s), 1920×1080. Shorter than its 96-frame source. "A (Seedance) barely moved her face."
- **v1:** —
- **final:** not used.

Prompt:

```
【Editing Goal】
Edit @Video1, changing only Claudia's face shape and removing one stray object: her face becomes slimmer and more angular, like the face in @Image1, and the stray bare foot beside her disappears.

【Role of the Source Video】
@Video1 is the sole editing master. It governs Claudia's identity, expression, eyes, hair, body, pose and every movement, the dark bedroom, the giant clock numerals, the moon, the notification cards, the status bar and the Dynamic Island, the framing, the camera, the event order and the timing, frame by frame.

【Role of the Target Material】
@Image1 is used only for the shape of her face: a slim, angular adult face with defined cheekbones, a defined jaw and a slender neck; do not use its clothes, its lighting, its background or its framing.

【Edit Objects and Scope】
1. Claudia's face becomes slimmer and more angular, like @Image1: defined cheekbones, a defined jaw and chin, slimmer cheeks, a slender neck; her chin lifts very slightly out of the sweater collar. Her eyes, eyelids, sleepy expression, freckles, lips, hair, star clip and headset microphone stay as in @Video1, and her head keeps every movement of @Video1.
2. The stray bare foot and leg that appear beside her at the lower right of her body are removed; there is only the dark room there.
3. Claudia is one woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange eight-pointed star hair clip and a thin headset microphone at her cheek, in an oversized acid-green mohair sweater; she stays one person with natural anatomy.
The dark bedroom, the giant clock numerals, the moon, the notification cards with their words, the status bar and the Dynamic Island stay exactly as in @Video1. No new text appears.
Except for the objects explicitly modified above, all other visible characters, props, and background elements in @Video1 remain unchanged and are not to be replaced or removed.

【Timeline Inheritance】
Every movement keeps the timing, path and speed of @Video1 from the first frame to the last.
```

#### WANF2-S17

Wan 3.0 reference-to-video · 4 s · 1080p 16:9 · $1.60 (includes 4 s of input video)

- **for:** S17 (1:11 in the final cut), option B: Wan with the face reference and an explicit slim face, the chin lifted.
- **inputs:** Video 1: the original render of S17; Image 1: face 1.
- **take:** 120 frames at 30 fps (4.000 s), 1920×1080. "It's the slimmest and closest to face 1." anabology: "ok cool both look fixed! B is good. slice those in and render and we're good!"
- **v1:** —
- **final:** S17, spliced: 87 frames written from its 120.

Prompt:

```
Reimagine Video 1 as the same shot, physically lit and photographic. Image 1 is the face of the woman: keep her face exactly as in Image 1 in every frame — the same facial structure, a slim, angular adult face with defined cheekbones and jaw, the same eyes, nose, lips, freckles and skin; her face is slim and angular, never round or full: slim cheeks, defined cheekbones and jaw, a slender neck, and her chin lifts slightly out of the sweater collar so her jawline shows; her slim, slender build stays exactly as in Video 1. Image 1 is only a reference for her face; it is never shown as a shot. Keep every element exactly in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera stays exactly as in Video 1, no cuts, no new objects, no added text. The woman is Claudia, a Caucasian woman in her late twenties with pale skin and light freckles, a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a small clay-orange star hair clip and a thin headset microphone at her cheek, in an oversized acid-green mohair sweater; her face, expression, pose and every movement stay exactly as in Video 1. Remove the stray bare foot and leg that appear beside her at the lower right of her body: there is nothing there but the dark room, and her body continues naturally below the frame. Re-light the scene as a real dark bedroom at night, lit by the cool glow of the giant glass clock numerals and the moon: soft violet and blue light on her face and sweater, a gentle rim light, deep clean blacks, a faint haze. The clock numerals, the moon, the notification cards with their words, the status bar and the black Dynamic Island at the top stay exactly as in Video 1, sharp and legible.
```

