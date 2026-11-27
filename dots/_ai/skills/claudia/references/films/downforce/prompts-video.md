# Wan 3.0 and Seedance 2.5 — every video job (DOWNFORCE)

Models: **Wan 3.0** (`alibaba/wan-3.0`) and **Seedance 2.5** (`bytedance/seedance-2.5`), both through **Higgsfield's pay-per-generation API**. There were 79 submissions, 63 to Wan and 16 to Seedance. Every one completed with one take; none was blocked, refused or refunded. Wan ran 52 image-to-video jobs (a first frame and a prompt) and 11 reference-to-video jobs: 9 video edits that add her to a real clip, and 2 moves from a real frame to her behind the glass with two still images. Seedance ran 13 reference-to-video jobs (a first frame plus reference frames of the car's other sides) and 3 image-to-video jobs with a first and a last frame. Every request asked for 1080p at 16:9, without audio, for 3 to 6 seconds, and every take came back at 1920×1080. Wan's takes are 30 fps and exactly as long as asked; Seedance's are 24 fps and run 0.042 s over (4.042 s and 5.042 s).

**Direction.** anabology's words on the video models came in the message that locked the song: "i want it to be like tiktok car edits. many angles, lot of 3d effects, video models are great at 3d effects, moving shots in space, etc. we  should use wan 3.0 primarily via higgsfield api becuase its cheapest and seedance if shots get mangled. go and do the entire thing." Later, they sent SpaceX's 2018 footage: "heres the roadster in space for the orbit scene". In their notes on the first cut: "for reshoots use seedance 2.5 to try and make it better and specify the fix (l;ike say the car is upside down and shooting blue/white cold gas thrusters on the right end to turn for example)."

**Price.** List price, as the runner records it: Wan 3.0 at $0.20 a second at 1080p, billed for the output seconds plus the seconds of any input video (Higgsfield's price estimate); Seedance 2.5 at $1.1372 a second at 1080p, 16:9. Image references cost nothing extra. So a 5 s Wan take from a still costs $1.00, a 6 s Wan edit of a 6 s clip $2.40, and a 4 s Seedance take $4.55. The records hold list prices only; what was actually charged is not recorded.

**Budget.** The runner refuses a submission that would pass its cap at list price. The lead set the cap at $60 for the first roll and the first two repairs. Later, anabology wrote: "oh you can spend a lot more if you want. feel free to spend $200". From the Starman jobs on, the cap was $200. Generation came to **$143.17**.

There are two delivered cuts: **the first cut** (v0), which anabology sent notes on, and **the final film** (v1), which anabology approved: "this is perfect. done. nothing more to do". Times written as 0:05.90 are times in the film, which is the song.

## Totals

Measured for this package from `shots/ledger-hf.jsonl` (one line per submission, with its list price) and the 79 job records in `shots/*.json`. "In the first cut" and "in the final film" count the takes that the chapter files of each cut draw (`engine/ch_v0/` and `engine/ch/`).

| Round | Jobs | Wan | Seedance | Seconds | List price | Takes in the first cut | Takes in the final film |
|---|---|---|---|---|---|---|---|
| Round 1: the storyboard's Wan shots, and one re-roll | 30 | 30 | 0 | 146 | $33.39 | 14 | 14 |
| The Seedance repairs | 2 | 0 | 2 | 10 | $11.37 | 2 | 2 |
| SpaceX's Starman footage | 3 | 2 | 1 | 15 | $7.69 | 2 | 2 |
| Round 2: the head director's plan, 25 shots | 34 | 29 | 5 | 150 | $52.73 | 25 | 19 |
| Round 3: the re-shoots on the notes | 8 | 0 | 8 | 32 | $36.39 | — | 4 |
| The closed-lip re-roll | 2 | 2 | 0 | 8 | $1.60 | — | 1 |
| **Total** | **79** | **63** | **16** | **361** | **$143.17** | **43** | **42** |

| Kind | Model, endpoint | Jobs | Seconds | List price | Takes in the final film |
|---|---|---|---|---|---|
| Camera moves on Tesla's real frames | Wan, image-to-video | 25 | 121 | $24.20 | 13 |
| Camera moves on SpaceX's Starman frames | Wan, image-to-video | 2 | 10 | $2.00 | 1 |
| Her shots, from Midjourney plates or frames of takes | Wan, image-to-video | 25 | 114 | $22.80 | 13 |
| Video edits that add her to Tesla's real footage | Wan, reference-to-video (a real clip and her plate) | 9 | 41 | $16.38 | 4 |
| Moves from a real frame to her behind the glass | Wan, reference-to-video (two images) | 2 | 8 | $1.60 | 1 |
| Moves on the real car with reference frames of its other sides | Seedance, reference-to-video | 12 | 50 | $56.86 | 7 |
| Moves between a given first and last frame | Seedance, image-to-video | 3 | 12 | $13.65 | 2 |
| The orbit round Starman | Seedance, reference-to-video | 1 | 5 | $5.69 | 1 |
| **Total** | | **79** | **361** | **$143.17** | **42** |

- **By model:** Wan 3.0, 63 submissions, 294 s of output, $66.98; the nine edits were also billed for 40.88 s of input video. Seedance 2.5, 16 submissions, 67 s, $76.20. The per-kind prices above are rounded to the cent; their exact sum is $143.17.
- **Takes:** 79, one per submission. Each has a verdict and a usable window in `TAKES.md`: USE, PART (only part of it is usable) or ALT (a usable alternate). The first cut plays 43 takes and the final film 42 (32 Wan, 10 Seedance). 36 are in both; 7 played only in the first cut (g14, g19-r2, g27-r2, g32, g37, g38, g39) and 6 only in the final film (g14sd, g27, g32sd2-t2, g37sd-t2, g38sd-t2, g39r2). 30 takes are in neither.
- **Prompts:** 65 different prompts, because 14 jobs are second takes of the same prompt. Wan's 54 run from 141 to 342 words (median 200); Seedance's 11 from 318 to 618 (median 442).

## How the jobs were made

**Who wrote the prompts.** Claude, the production lead, wrote round 1's 29 Wan prompts (`tools/jobs.py`). It started from the storyboard's draft for each generated shot (the "motion" text of each generation in `shots.json`), the real start frames and the plates. It also wrote the two Seedance repairs, the three Starman jobs, the four re-shoots on the notes (`tools/jobs3.py`) and the closed-lip re-roll. Round 2's 25 prompts were drafted by the head director of a workflow run. It merged three scouts' proposals into one ranked, costed plan with every start frame extracted and checked (`wf/GEN2-PLAN.md`). The scouts looked for more 3D angles at the drops, for Claudia as the pilot reacting to the real stunts, and, adversarially, for anything wrong in the takes. The drafts write the shared preambles as shorthand (REAL+, HER2, EDIT2). The lead tightened the drafts, and `tools/jobs2.py` expanded the shorthand into the text that was sent. Each job file in `shots/` holds its request body exactly as it was submitted, and every prompt below is copied from there. `PROMPTS.md` holds the prompts of rounds 1 to 3 as the job builders wrote them; the two repairs, the Starman jobs and the two re-rolls are only in their job files.

**The request.** Each body has the prompt, a `duration` of 3 to 6 s, `resolution` 1080p, `aspect_ratio` 16:9 and `generate_audio` false; the input files are uploaded and passed as URLs. Wan requests also carry a seed: 99 plus the shot number in round 1 (g01 is 100, g29 is 128), 205 for g05-r2, 130 and 131 for Starman, 200 plus three times the plan's rank in round 2 (one more for a second take), and 411 and 412 for the re-roll. Seedance's documented parameters have no seed, so its second takes are simply a second roll of the same request. A job is written to its file marked locked, and the runner submits only locked jobs. Jobs went out in parallel, two to six at a time, from one or two runners.

**The inputs.** The demo came as three files that anabology supplied, here A, B and C (A and C are Tesla's livestream; the records do not say who filmed B), and SpaceX's footage as D:

- **A**, the 4K feed with Tesla's telemetry readout (105.30 s).
- **B**, a camera beside the lineup (15.45 s).
- **C**, the 1080p stream (42.05 s).
- **D**, SpaceX's 2018 Starman footage (28.14 s, 1280×720), which anabology supplied.

"A 35.50" means second 35.50 of A. A start frame is cut by `tools/gen.py frame`. It takes a 16:9 window above Tesla's readout at a given centre and zoom, scaled to a 1920×1080 PNG. Tesla's segment titles (rows of small white glyphs in the top 17 % of the frame) are found and inpainted. A video input for an edit is cut by `gen.py clip` with the same crop at 30 fps, the titles inpainted on every frame. Her plates are named as in [prompts-midjourney.md](https://claudia.gallery/record/downforce/prompts-midjourney/): "rh-02 g05 #2" is image 2 of the Midjourney job made for g05 in the batch rh-02-plates. The upside-down plates are those images turned 180°.

## The house preambles

Every Wan prompt opens with a fixed preamble that says what Image 1 (or Video 1) is and what must not change. The shot's own lines follow, with its beats in decimal seconds ("0-1 s: … 1-4 s: …") and the camera, and the constraints come last. No prompt names Tesla, the Roadster or SpaceX: the car is "a white electric sports car", and Starman's car is "the red open-top 2008 sports car". Her identity is the canon text of claudia.gallery's consistency guide, pasted verbatim.

Round 1 (`tools/jobs.py`). A camera move on a real frame opens with REAL:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone.
```

A shot of her from a plate opens with HER (the full canon and the suit):

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people.
```

An edit of a real clip opens with EDIT (the canon's short form, and two images):

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1 (her face exactly as in Image 2): a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. She is real and life-size, lit by the real lights of Video 1, standing and walking on the real ground. Keep the real car, the set, the lights, the smoke and the camera move exactly as in Video 1; native colour; no text, no logos, no other people, no other cars. Her lips stay closed.
```

Round 2 (`wf/GEN2-PLAN.md`, expanded by `tools/jobs2.py`) hardened each of them against what round 1's takes had done. REAL+ follows REAL on every move that shows the car:

```
The car is empty and flown by remote: nobody is inside it and its glass stays dark. Its thrusters blow white cold-gas vapour, never flame or fire. No race track, no stands, no crowd, no city lights, no other cars than those in Image 1.
```

HER2 replaces HER. It holds the set and the framing, and adds badges:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior; the camera stays at the same distance. Her lips stay closed; she never talks. No text, no logos, no badges, no other people.
```

(g19-r2, a tilt, uses HER2 without "the camera stays at the same distance".) EDIT2 replaces EDIT, with one image only:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. Image 1 is only a reference for her look; it is never shown as a shot. She is real and life-size, lit by the real lights of Video 1, walking on the real ground, and always seen at full length. Keep the real car, the set, the lights, the smoke and the camera exactly as in Video 1: one continuous shot, no cuts, the same framing from the first frame to the last. Native colour; no text, no logos, no badges, no licence plates, no other people, no other cars. Her lips stay closed.
```

The two Wan jobs on SpaceX's footage open with:

```
Image 1 is the first frame of real footage filmed in space in 2018: the red open-top 2008 sports car with a mannequin in a white spacesuit and white helmet in the driver's seat, the blue Earth behind it, black space. Keep everything exactly as it is: the red car and its exact shape, the astronaut mannequin (it never moves on its own), the Earth, the black sky, the hard sunlight; native colour, no grade, no new objects, no people, no text, no logos, no stars added. One continuous shot, no cuts.
```

The Seedance repairs of round 1 share their 【Core Requirements】; the round-3 re-shoots share a car requirement (`tools/jobs3.py`):

```
【Core Requirements】
1. The car is exactly the real car of the reference images in every frame: a low, wide white two-door electric sports car with a long black glass canopy, a sharp wedge nose and black wheels; the same proportions and details; it never turns into a different car, never a sedan, never another colour, and there is only this one car in the air.
2. Native colour of the night footage: black sky, white car, white plumes, red light; no grade, no added lens effects beyond what the lights make.
3. No people. No new vehicles, buildings, stands or crowds are added.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.
```

```
The car is exactly the real car of the reference images in every frame: a low, wide white two-door electric sports car with a long black glass canopy, a sharp wedge nose, black wheels and a thin red light bar across its tail; one car only, never a sedan, never another colour, nobody inside it (its glass stays dark). It always has exactly four wheels, one at each corner, and they stay attached and visible whenever that side of the car faces the camera. Its thrusters blow white and pale blue cold-gas vapour, never flame or fire.
```

## What Wan did, measured

Every take was viewed on a contact sheet (`review/takes/`) and given a verdict and a usable window in `TAKES.md`. Round 2's repair scout re-checked every round-1 take frame by frame and shortened several windows. The chapter reviewers and the whole-film check found the rest. Each failure below is from those records, with the second of the take where it starts.

| What Wan did | Takes | What changed after it |
|---|---|---|
| Lost the real car on a side the first frame does not show: another model, another colour | g09 (a hatchback with a round rear badge, 1.6 s), g13 (a generic white sedan as the roof comes into view, 2.7 s), g14 (a dark grey car on a race track, about 2 s), g16 (a generic sedan, 0.3 s), g20 (an alloy wheel from 1.0 s, then a sedan landing in a car park), g23 (Porsche-like headlights from 0.6 s, then a Porsche-like sedan on a race track), g26 (a sedan's underside, 3–4 s), g33 (a Lamborghini-like supercar, 1.9 s), g33-t2 (the same on a lit road, 1.2 s) | Seedance with real reference frames of the car's other sides (g20-sd, g23-sd, g09-sd, g13-sd, g32). Wan's later moves stay on the side the frame shows: "The camera stays on this side of the car and never goes around its nose or tail" (g09-r2); arcs of about 40° toward the nose that is already visible (g26-r2, g33, g42) |
| Cut or drifted to another set, mostly in a take's second half | g01 (ground with ladder markings, 4 s), g06 (a white spaceship interior, 2.75 s), g07 (the wall becomes a road with lamp posts, 3 s), g09 (a chassis seen from above, 4.5 s), g10 (another seat, 2.63–3.13 s), g12 (a blue sci-fi screen, 3.3 s), g17 (a cut, 2.63 s), g25 (a bright white spaceship interior, 3 s), g16-r2 (a lit road with a gantry, 2.43 s), g26-r2 (1.6 s), g26-r2-t2 (an electricity pylon, 1.97 s), g38 (a lit bridge and an open-top car, 2.30 s), g39 (daytime sky in the window, 2.8 s), g40 (a white interior, 1.7 s) | A usable window for every take, and chapters that draw only inside it. HER2 for her shots: "the set stays exactly as Image 1 from the first frame to the last" |
| Added to the set | g04 (wider stage beams), g22 (stands at the sides, 3 s), g27 (a coupe in the smoke), g27-r2 (a generic white sports car in the smoke, 1.4 s), g35 (the lineup recedes and the Semi is gone, 2.6 s), g35-t2 (rows of generic parked cars, 1.4 s), g34 and g34-t2 (the wall becomes a long ramp with posts or lights, 2–2.5 s), g42 (a full-width light bar and a hood badge at the head-on end, about 1.9 s), g43 (stadium lights, late), g30 (faint stars), g31w (a second Earth, 2.8–3.6 s) | REAL+: "No race track, no stands, no crowd, no city lights, no other cars than those in Image 1." Windows that end before the addition |
| Cut to the identity reference, as if it were a shot (the edits) | g02 (her face on its grey studio wall, 4.47 s), g27 (a close-up, 2.47 s), g28 (a new set and a close-up, 2.24 s) | Image 2 dropped; one cleaned full-length plate, and "Image 1 is only a reference for her look; it is never shown as a shot" (EDIT2). g02-r2 then ran its 6 s with no cut and g27-r2 with none; g27-r2-t2 and g28-r2 still cut, at 3.57 s and 2.80 s |
| Put a driver in the empty car | g26 (a man in profile in the window, 0.9 s) | REAL+: "The car is empty and flown by remote: nobody is inside it and its glass stays dark." |
| Turned cold gas into fire | g28 (four orange fire nozzles, 0.2–1.0 s), g41 (orange sparks at the impact, 1.1 s) | REAL+: "Its thrusters blow white cold-gas vapour, never flame or fire." g41's sparks are never shown |
| Lettering, badges and plates | g05 ("9RC" on her chest), g01 and g34-t2 (glyphs on the car's rear plate), g28 and g28-r2 (a licence plate), g25 (an arm badge), g27 (a collar badge in its close-up), g42 (a hood badge), g44 (an orange placard), g17 (a mark in the top-left corner) | "no letters, numbers, badges or logos ever appear on it" (g05-r2); "no badges, no licence plates" (EDIT2). In the film the plates are painted blank in their own tone, tracked frame by frame, and the rest is framed or windowed out |
| Opened her mouth | g05 (an open grin), g05-r2 (moving as if talking, 0.9–3.5 s), g19 and g24 (teeth throughout), g39 (teeth in every window), g03 (parted, 1.10–1.90 s), g12 (from 2.13 s), g41 (after 1.1 s), g19-r2 (parted throughout), g25-r2 (slightly, at 1.3 s), g39r2 and g39r2-t2 (during the hair fall) | See *Closed lips*, below |
| Turned a light named on the glass into an object | g19 (a chrome object like a robot glove flies through the cockpit across her face, 0.75 s; the prompt had "two white thruster plumes and a bright light sweep across the glass") | g19-r2: a light only, "the light stays outside the glass", and "Nothing enters the cockpit: no objects, no machines, no other hands." |
| Lifted the blacks | its takes of her and most edits (the extraction tool's note: black at about 14 on a 0–255 scale, where the real footage sits at about 1) | Each take was extracted for the engine with its own black level: 4 to 15 for her shots, 0 to 7 for the edits. The moves on the real night frames needed none |

**How long a move held.** Of the 25 Wan moves on Tesla's real frames, every usable window in `TAKES.md` starts at 0 s, and it ends between 0.9 s and the full take, median 2.2 s. The round-2 check later shortened seven of round 1's: g01, g09, g14, g16, g20, g23 and g26. Five were recorded as usable for the whole take. One of them, g26, was later found to have a man in the window. The other four keep to what the first frame shows: g04 and g22 (dolly-zooms on a car that does not move), g09-r2 (a slide along the visible side) and g43 (a straight rise toward the canopy). anabology's expectation ("video models are great at 3d effects, moving shots in space") held for moves like these. The orbits that revealed a new side of the car needed Seedance and real reference frames.

**Her shots.** The faults in Wan's shots of her were mostly the mouth, the set and lettering. Some takes also drifted off-model. g03 reads rounder and younger after about 4.5 s. g27's close-up has a white streak beside the clay one, red-rimmed eyes and a second mic tip. The film uses neither stretch. The plates themselves were screened before use; [prompts-midjourney.md](https://claudia.gallery/record/downforce/prompts-midjourney/) has the screen.

## Seedance: structured prompts and reference roles

Seedance 2.5 had two jobs: repairing the moves where Wan lost the car, as anabology's direction set it ("seedance if shots get mangled"), and the re-shoots, as their notes set it. Its prompts follow the house contract for Seedance (`video/SEEDANCE-2.5.md`, adopted from the vendor's prompt guide and its sd25-pe prompt-optimiser skill). The sections are labelled and in a fixed order: 【Audio Policy】 at the top and again at the bottom (always "Silent video: no music, no sound effects, no voice."), 【Generation Goal】, 【Reference Asset Roles】, 【Event Timeline】 (in round 3, 【Event Script】), 【Camera】, 【Core Requirements】 as a numbered list, and 【Final Acceptance Criteria】. Time is in whole seconds, in continuous segments. Round 2's Seedance prompts were sent as single paragraphs; the others keep their line breaks.

**Reference roles.** Each image has one stated role and is told what not to take. The first frame is the standalone sentence "Use @Image1 as the first frame.", followed by what that frame defines. The other images are "the SAME car" seen from its other sides, to be used "only for the car's exact shape … when the orbit reveals those sides". Every reference image is a real frame of the same car from the same footage, never a generated one. For the Roadster demo they show its underside (A 80.00), its side upside down (A 79.30), its roof and canopy on black (A 78.30), its front three-quarter (A 50.25), its side in flight (A 77.60 or A 80.60), its rear (A 36.00) and its roof from straight above (A 8.50). For Starman they are SpaceX's views from behind the car and over his shoulder. The car itself is described, never named: "a low, wide white two-door electric sports car with a long black glass canopy, a sharp wedge nose and black wheels". Round 3 adds "and a thin red light bar across its tail".

**What the references did.** They kept the shape. The first two repairs held the real car where Wan had lost it: g23-sd to its cut at 3.5 s, and g20-sd until it began to morph at 2.25 s. But Seedance also cut to its references, as if they were shots of the video. After the first two repairs the lead wrote in `TAKES.md`: Seedance "cuts TO the reference images unless told they are not shots". From the Starman orbit on, every reference-to-video prompt says so: "@Image2 and @Image3 are never shown as shots of this video; there are no cuts to them" (g31), and "They are never shown as shots: never cut to them, never take their framing, power lines, backgrounds or lighting" plus "One continuous shot: it never cuts to a reference image" (round 2). The cuts kept coming:

| Take | Cut or drift | At |
|---|---|---|
| g23-sd | its rear-view reference by the wall; from 2.0 s the background had already become @Image3's sky with power lines | 3.5 s |
| g20-sd | its references (the overhang, the top-down) | 2.92 s and 4.0 s |
| g31 | the over-the-shoulder view, @Image3's angle | 3.67 s |
| g32 | a drift into a pole-and-sky framing | about 2.6 s |
| g32-t2 | other framings | 1.71 s |
| g09-sd | its references | 2.42 s |
| g13-sd | its roof reference on black | 4.0 s |
| g32sd2 | its chassis reference | 1.83 s |
| g32sd2-t2 | a drift into a pole-and-sky framing | about 2.0 s |
| g38sd | the framing of a reference: the car upside down in the sky with a pole | 3.6 s |
| g38sd-t2 | no cut; a pole appears in the sky | 2.9 s |
| g14sd | no cut; the car turns to show its roof | about 2.5 s |
| g14sd-t2 | no cut; the car rolls upright | about 1.4 s |

Of the 13 reference-to-video takes, 8 cut away to another picture, in most cases one of their reference images (between 1.71 and 4.0 s), and 2 drifted into a reference's framing. Of the 11 made after the instruction, 6 still cut and 2 drifted. The round-2 plan, written with the instruction, also made the moves finish early. The first repairs had cut at about 3 s, so it scripted every move to land by 3 s and cut the takes from 5 s to 4 s. Its references became tight crops on black, because g23-sd had taken on the power-line sky of one of its uncropped references. And its cars were told to stay high ("it stays high above the lineup and never descends", "its roofline stays low and never rises"), because Seedance morphed the car as it descended toward other vehicles. Every window in the film ends before the cut. Among the Seedance takes in the film, the usable windows run from 1.6 s (g14sd) to the full 4 s (g36, g37sd-t2, g38sd-t2).

## The first-and-last-frame move

Two shots needed a move that ends on a known picture, and only Seedance takes a verified last frame (the round-2 plan's words). Both went to Seedance's image-to-video endpoint with `image_url` and `end_image_url`. The prompt names them "Use @Image1 as the first frame." and "Use @Image2 as the last frame.", each followed by what that frame defines, and asks for "One continuous move from @Image1 to @Image2 with true parallax; no cut, no dissolve, no fade between the two frames."

- **g36, the wall swing (round 2).** Both ends are real frames: Tesla's side view of the car on the wall face (A 7.54) and Tesla's top-down on the face (A 8.50). The take flies onto the face and lands exactly on the top-down, the real car throughout. In the film it chains three shots on real frames. The real s022 ends on A 7.54, g36 runs from there to A 8.50, and the dive at s024 starts on A 8.50.
- **g37sd, the canopy dive (round 3).** The first frame is the real top-down again; the last is a frame of a Wan take, g37's at 3.5 s, her lying back in the seat looking up into the lens. Wan's own version (g37) had no last frame to aim for. It was a reference-to-video job with the real frame as Image 1 and her plate as Image 2, "never shown as a shot", and its arrival on her read to anabology as "the temporary half-shown cut of claudia". Seedance's take 1 passed through a murky red double exposure; take 2 went through the canopy, into the red-lit cockpit past her hands, and settled on her face in one move. One frame of dissolve is left in the film, at 0:24.54.

## Writing the fix as the car's real physical state

anabology's notes on the first cut flagged four generated shots, and asked for the re-shoots to "specify the fix (l;ike say the car is upside down and shooting blue/white cold gas thrusters on the right end to turn for example)". Before writing, the lead pulled frames of the first cut around each timestamp and a strip of the real footage of the three car moments. Three of the four re-shoots then state, before any timing, what the real car is doing for the whole take, as the real footage shows it (the fourth, the canopy dive, is the first-and-last-frame move above):

- **g32sd2**, the kickflip frozen over the Semi: "The car's state for the whole video: upside down, rotated 180 degrees about its long axis, frozen in mid-air exactly where @Image1 shows it, high above the semi truck. It does not roll, flip, turn over, right itself or move at all: time is stopped. Its four wheels stay attached at its four corners and point up and outward; the four jets stay frozen like glass columns in the same X."
- **g14sd**, the exit off the truss: "The car's motion, in slow motion, the whole video: it stays upside down and keeps travelling away from the end of the ramp toward the lower left. Blue-white cold-gas jets fire continuously from the thrusters at its right end, and they slowly swing its tail around so the car turns smoothly in ONE direction about its vertical axis, a little at a time. It never snaps, jumps, flips back or rights itself: from the first frame to the last it is upside down, wheels toward the sky."
- **g38sd**, the flip off the top of the ramp: "The ramp ENDS at the top edge shown in @Image1: there is nothing above or beyond that edge but black night sky; no further ramp, no platform, no second car."

A matching core requirement repeats the state: "The car never rotates relative to the scene: it stays upside down from the first frame to the last." (g32sd2); "The car is upside down in every frame and turns only slowly and smoothly in one direction; it never rights itself." (g14sd); "The ramp keeps its shape and ends at the edge in @Image1; nothing is added above it." (g38sd). The shared car requirement adds the details the takes had lost: exactly four wheels, one at each corner, attached and visible; the red light bar across the tail; and cold gas that is "white and pale blue … never flame or fire". The earlier prompts for the same shots had described the camera and what it reveals. Round 2's g32, for one, says "the car's white side, upside down with its wheels toward the sky, turns to face the camera".

All eight takes were back and judged within nine minutes of submission, and every job had at least one take that held its state inside a usable window. One take showed the very fault: g14sd-t2 rolls the car upright at about 1.4 s, the glitch of the note. The four picks are in the film, and the whole-film check re-rendered every frame of the seven noted moments.

## Closed lips

She never lip-syncs in this film; the lettering carries her words. Every Wan prompt of her says "Her lips stay closed; she never talks." That was not enough on its own. Every plate with parted lips (rh-02 g05 #2, g19 #3, g24 #3) gave takes in which Wan opened her mouth or showed her teeth. Four measures followed:

- **Closed-lip first frames.** g05-r3 and g41 start on a frame of the g05-r2 take where her lips are closed (3.65 s); g39, g39r2 and the two moves to her behind the glass use rh-02 g10 #1, a closed-lip plate. The round-2 plan rejected candidate plates for parted lips.
- **Never the word "teeth".** The round-2 plan: "Never write 'teeth'. It opened her mouth twice." g05's prompt had "teeth gritted behind closed lips" for the lyric "gritting my teeth"; g05-r3 says "jaw set, lips pressed into a thin line".
- **Stronger wording.** g05-r3: "Her mouth stays shut from the first frame to the last." g39r2: "her lips stay pressed together from the first frame to the last, no teeth ever show, she does not breathe through her mouth and never speaks."
- **Checks.** The chapter reviewers checked her lips on the take frames: g39 (teeth in every window) and g19-r2 (parted throughout) were taken out, and the hair fall was re-rolled as g39r2. The final check went through 34 shots of her face, five take frames each, and found one more: s132 started on three frames of parting lips, and its window now starts at 1.95 s. In the final film her lips are closed in every shot.

## From take to film

- **Windows.** The chapters draw only inside the windows in `TAKES.md`, and the windows below are those records. The chapter files name, for every shot, the part of the take it plays, often speed-ramped. Before v1 went out, the final check logged every footage frame the whole film draws and compared each generated shot's range with its take's window; all were inside.
- **Extraction.** `tools/extract.py gen` turns a take into JPEG frames at the take's own rate (30 fps for Wan, 24 for Seedance), with Wan's black level corrected. The engine's clip names are the job ids without the hyphen, except the picks of the second rounds: g05r3 is g05-r3, g26r2 is g26-r2-t2, g34 is g34-t2, g14r3 is g14sd, g32r3 is g32sd2-t2, g37r3 is g37sd-t2 and g38r3 is g38sd-t2.
- **Repairs in code.** Wan's lettering on the car's rear plate (g01, g34-t2) and its licence plate (g28-r2) are painted blank in the plate's own tone, tracked frame by frame. Her jolt on the touchdown (g41) is a code shake on the kick, not the take's own sparks.

## Index

Every job, in the order of the prompt book below. "Usable" is the window in `TAKES.md`, in seconds of the take; the last two columns count the shots that draw the take in each cut.

| Job | Round | Model, endpoint | Length (s) | List price | Verdict | Usable (s) | First cut | Final film |
|---|---|---|---|---|---|---|---|---|
| g01 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–4.0 | 1 | 1 |
| g02 | 1 | Wan 3.0, reference-to-video | 6 | $2.40 | USE | 0.9–4.3 | — | — |
| g03 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 5 | 5 |
| g04 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 1 | 1 |
| g05 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | ALT | 1.0–3.5 | — | — |
| g05-r2 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | — | — |
| g06 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–2.5 | 3 | 3 |
| g07 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–2.5 | — | — |
| g08 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 4 | 5 |
| g09 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–4.3 | 1 | 1 |
| g10 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–2.6, 3.15–5.0 | — | — |
| g11 | 1 | Wan 3.0, reference-to-video | 3 | $1.20 | USE | 0.0–3.0 | — | — |
| g12 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–3.0 | 3 | 3 |
| g13 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | PART | 0.0–2.5 | — | — |
| g14 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | PART | 0.0–1.8 | 1 | — |
| g15 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 1 | 2 |
| g16 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | PART | 0.0–1.8 | — | — |
| g17 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | PART | 0.0–1.8 | 1 | 1 |
| g18 | 1 | Wan 3.0, reference-to-video | 3 | $1.20 | USE | 0.0–3.0 | 1 | 1 |
| g19 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | — | — |
| g20 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | PART | 0.0–2.2 | — | — |
| g21 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 1 | 1 |
| g22 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 1 | 1 |
| g23 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | PART | 0.0–1.3 | — | — |
| g24 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | — | — |
| g25 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–2.0 | — | — |
| g26 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | — | — |
| g27 | 1 | Wan 3.0, reference-to-video | 4 | $1.60 | USE | 0.8–2.6, 3.0–4.0 | — | 1 |
| g28 | 1 | Wan 3.0, reference-to-video | 5 | $1.99 | USE | 0.0–2.1, 2.5–3.8, 4.0–5.0 | — | — |
| g29 | 1 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 1 | 1 |
| g23-sd | repair | Seedance 2.5, reference-to-video | 5 | $5.69 | USE | 0.0–3.45 | 2 | 2 |
| g20-sd | repair | Seedance 2.5, reference-to-video | 5 | $5.69 | USE | 0.0–2.9 | 2 | 2 |
| g30 | Starman | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 1 | 1 |
| g31w | Starman | Wan 3.0, image-to-video | 5 | $1.00 | PART | 0.0–2.5, 3.8–5.0 | — | — |
| g31 | Starman | Seedance 2.5, reference-to-video | 5 | $5.69 | USE | 0.0–3.6, 3.9–5.0 | 1 | 1 |
| g32 | 2 | Seedance 2.5, reference-to-video | 4 | $4.55 | USE (hero) | 0.0–2.4 | 2 | — |
| g32-t2 | 2 | Seedance 2.5, reference-to-video | 4 | $4.55 | PART | 0.0–1.65 | — | — |
| g09-sd | 2 | Seedance 2.5, reference-to-video | 4 | $4.55 | USE | 0.0–2.3 | 2 | 2 |
| g09-r2 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 1 | 1 |
| g26-r2 | 2 | Wan 3.0, image-to-video | 4 | $0.80 | ALT | 0.0–1.5 | — | — |
| g26-r2-t2 | 2 | Wan 3.0, image-to-video | 4 | $0.80 | USE | 0.0–1.9 | 1 | 1 |
| g27-r2 | 2 | Wan 3.0, reference-to-video | 5 | $1.99 | USE | 0.0–5.0 | 1 | — |
| g27-r2-t2 | 2 | Wan 3.0, reference-to-video | 5 | $1.99 | ALT | 0.0–3.5 | — | — |
| g28-r2 | 2 | Wan 3.0, reference-to-video | 4 | $1.59 | USE | 0.0–2.3, 2.85–4.0 | 1 | 1 |
| g33 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–1.5 | 2 | 2 |
| g33-t2 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | PART | 0.0–0.9 | — | — |
| g02-r2 | 2 | Wan 3.0, reference-to-video | 6 | $2.40 | USE (pick) | 0.0–6.0 | 3 | 3 |
| g05-r3 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE (pick) | 0.0–5.0 | 4 | 4 |
| g05-r3-t2 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | ALT | 0.0–5.0 | — | — |
| g10-r2 | 2 | Wan 3.0, image-to-video | 4 | $0.80 | USE (pick) | 0.0–4.0 | 1 | 1 |
| g10-r2-t2 | 2 | Wan 3.0, image-to-video | 4 | $0.80 | ALT | 0.0–4.0 | — | — |
| g25-r2 | 2 | Wan 3.0, image-to-video | 3 | $0.60 | USE (pick) | 0.0–3.0 | 1 | 1 |
| g25-r2-t2 | 2 | Wan 3.0, image-to-video | 3 | $0.60 | ALT | 0.0–3.0 | — | — |
| g19-r2 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE (pick) | 0.0–5.0 | 1 | — |
| g16-r2 | 2 | Wan 3.0, image-to-video | 3 | $0.60 | USE | 0.0–2.3 | 1 | 1 |
| g34 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | ALT | 0.0–2.1 | — | — |
| g34-t2 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE (pick) | 0.0–3.0 | 2 | 2 |
| g35 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–2.2 | 2 | 2 |
| g35-t2 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | ALT | 0.0–1.2 | — | — |
| g36 | 2 | Seedance 2.5, image-to-video | 4 | $4.55 | USE | 0.0–4.0 | 1 | 1 |
| g37 | 2 | Wan 3.0, reference-to-video | 4 | $0.80 | USE (hero) | 0.0–4.0 | 1 | — |
| g38 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–1.3 | 1 | — |
| g13-sd | 2 | Seedance 2.5, reference-to-video | 4 | $4.55 | USE | 0.0–3.6 | 2 | 2 |
| g39 | 2 | Wan 3.0, image-to-video | 4 | $0.80 | USE | 0.0–2.6 | 2 | — |
| g40 | 2 | Wan 3.0, image-to-video | 4 | $0.80 | USE | 0.0–2.0 (to 4.0 with care) | 2 | 2 |
| g41 | 2 | Wan 3.0, image-to-video | 4 | $0.80 | USE with care | 0.0–1.5, 2.3–4.0 | 2 | 2 |
| g42 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–3.0 | 2 | 2 |
| g43 | 2 | Wan 3.0, image-to-video | 5 | $1.00 | USE | 0.0–5.0 | 1 | 1 |
| g44 | 2 | Wan 3.0, reference-to-video | 4 | $0.80 | USE | 0.0–1.7, 2.3–4.0 | 2 | 2 |
| g32sd2 | 3 | Seedance 2.5, reference-to-video | 4 | $4.55 | ALT | 0.0–1.75 | — | — |
| g32sd2-t2 | 3 | Seedance 2.5, reference-to-video | 4 | $4.55 | USE (pick) | 0.0–1.9 | — | 2 |
| g14sd | 3 | Seedance 2.5, reference-to-video | 4 | $4.55 | USE (pick) | 0.0–1.6 | — | 1 |
| g14sd-t2 | 3 | Seedance 2.5, reference-to-video | 4 | $4.55 | ALT | 0.0–1.2 | — | — |
| g38sd | 3 | Seedance 2.5, reference-to-video | 4 | $4.55 | USE | 0.0–3.4 | — | — |
| g38sd-t2 | 3 | Seedance 2.5, reference-to-video | 4 | $4.55 | USE (pick) | 0.0–4.0 | — | 1 |
| g37sd | 3 | Seedance 2.5, image-to-video | 4 | $4.55 | ALT | 0.0–1.8, 3.0–4.0 | — | — |
| g37sd-t2 | 3 | Seedance 2.5, image-to-video | 4 | $4.55 | USE (pick) | 0.0–4.0 | — | 1 |
| g39r2 | re-roll | Wan 3.0, image-to-video | 4 | $0.80 | USE | 1.8–4.0 | — | 1 |
| g39r2-t2 | re-roll | Wan 3.0, image-to-video | 4 | $0.80 | ALT | 2.6–3.6 | — | — |

## The prompt book

Every prompt below is exactly as submitted, copied from the job records; none needed a change for publication. Each entry reads: the job, its name, the model and endpoint, the length, the seed (Wan only) and the list price. Under it:

- **for:** the storyboard shots it was made for, with their film times on the storyboard (`shots.json`; a few cuts in the break moved by a frame or two in the chapters).
- **inputs:** the frames, clip and plates it was given.
- **takes:** the verdict and usable window in `TAKES.md`.
- **later:** what later checks found.
- **first cut** and **final film:** where it plays in each cut: the shot, its film time and, in brackets, the part of the take it plays, in seconds of the take (for a pair, which take first).

Two takes of the same prompt share one entry. The book has six parts, in the order of production: round 1, the Seedance repairs, the Starman footage, round 2, round 3 and the closed-lip re-roll. Within a part, jobs that went out within minutes of each other are in the order of their ids (round 2 in the plan's order of rank).

### Round 1 · the storyboard's Wan shots

29 jobs, one per Wan shot on the storyboard, plus the re-roll of g05; $33.39 at list. Twelve are camera moves on Tesla's real frames, thirteen are shots of her from the plates, and five are edits that add her to a real clip. The lead reviewed every take as it landed and wrote its window into `TAKES.md`; all 29 were reviewed and in the engine. Round 2's repair scout re-checked them about an hour later, and its corrections are under "later".

#### g01 · CRANE-WALL

Wan 3.0 image-to-video · 5 s · seed 100 · $1.00

- **for:** s003 (0:05.90), in the countdown: a crane up the face of the real wall while the count runs.
- **inputs:** first frame: A 35.50, the car parked at the foot of the wall, seen from behind.
- **takes:** USE, 0.0–4.0 s. A crane up the real wall face; at 4–5 s Wan invents ground with ladder markings.
- **later:** The round-2 check shortened it to 0.0–3.1 s: past the crest, from 3.2 s, a second car and the ladder markings appear.
- **first cut:** s003 (0:05.90), to 3.1 s of the take, where the top of the wall starts to curve away. anabology: "at like 9 seconds the end of the scrolling up ramp clip starts to show curve down, so it should be cut earlier."
- **final film:** s003 0:05.90–0:09.56 (take 0.00–2.40, ramped: slow on the line, a rush over the car on the stab at 0:08.14). The window now ends at 2.40 s, before the crest. Wan re-lettered the car's rear plate as it grows in the frame; the plate is painted blank in its own tone, tracked frame by frame.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car stays parked at the foot of the tall curved white wall, its thin red edge strips glowing; the haze drifts. 0-1 s: the camera is low behind the car, creeping forward. 1-4 s: it cranes straight up the face of the wall, close to the concrete, the centre stripe and the red edge strips streaming down past the lens, the car shrinking far below. 4-5 s: it reaches the lip at the top and tilts down to look straight down the wall at the small white car far below. Slow, steady, ominous; only the camera moves.
```

#### g02 · WALK-TO-CAR

Wan 3.0 reference-to-video · 6 s · seed 101 · $2.40 (includes 6 s of input video)

- **for:** s004 (0:09.56), s040 (0:37.92) and s167 (3:00.58): she walks to the real car, stands at its driver's side, turns to the lens.
- **inputs:** Video 1: A 34.50–40.50, 6 s, the car parked at the foot of the wall; Image 1: rh-02 id-full #3 (full length); Image 2: rh-02 id-face #3 (her face).
- **takes:** USE, 0.9–4.3 s: she walks in from the left, back to us, to the real car. From 5.1 s Wan cuts to her face on a grey studio wall.
- **later:** The round-2 check put the cut at 4.47 s and found its cause: the close-up is Image 2 itself, shown as a shot. Replaced by g02-r2, which drops Image 2.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1 (her face exactly as in Image 2): a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. She is real and life-size, lit by the real lights of Video 1, standing and walking on the real ground. Keep the real car, the set, the lights, the smoke and the camera move exactly as in Video 1; native colour; no text, no logos, no other people, no other cars. Her lips stay closed. The car is parked at the foot of the tall white wall; the camera slowly zooms in. 0-1 s: as Video 1, no one in frame. 1-3 s: she walks into frame from the bottom left, her back to us, toward the car with steady, confident steps; the car's roof is at her ribs. 3-4.5 s: she trails one white glove along the rear deck as she passes to the driver's side at the left and stops there, looking up the wall. 4.5-6 s: she turns her head over her shoulder to the camera, deadpan.
```

#### g03 · EYES

Wan 3.0 image-to-video · 5 s · seed 102 · $1.00

- **for:** s005 (0:11.39), s021 (0:22.09), s078 (1:25.93), s152 (2:44.63), s181 (3:07.46): her eyes snap open on the lens.
- **inputs:** first frame: rh-02 g03 #4.
- **takes:** USE, 0.0–5.0 s: the eyes open, then a push to an extreme close-up of her eyes.
- **later:** The round-2 check found her off-model from 4.5 s (rounder, younger) and the eyes opening at about 1.35 s. The countdown's builder found her lips parting at 1.10–1.90 s; no shot shows that span.
- **first cut:** The same five shots.
- **final film:** s005 0:11.39–0:13.22 (take 0.40–0.886, then a hard cut on the stab to 2.00–3.343); s021 0:22.09–0:22.55 (take 2.70–3.15); s078 1:25.82–1:26.30 (take 3.90–4.38); s152 2:44.63–2:45.30 (take 2.00–2.67); s181 3:07.46–3:07.92 (take 2.70–3.16, cropped 1.6× on her eyes).

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. She is strapped into the racing seat, eyes closed, a band of amber light across her eyes; red light strips outside. 0-1.5 s: eyes closed, still, the amber band breathing slowly across her eyes. 1.5 s: her eyes snap open and lock onto the lens. 1.5-4 s: she holds the stare without blinking; the red strips outside begin to slide sideways. 4-5 s: she lifts her chin a little, ready. Camera: a slow, steady push-in from her face to an extreme close-up of her eyes.
```

#### g04 · VERTIGO-LINE

Wan 3.0 image-to-video · 5 s · seed 103 · $1.00

- **for:** s006 (0:13.22): one held dolly-zoom on the car before the launch, 3 · 2 · 1 behind the wall.
- **inputs:** first frame: A 36.00, the car on the line at the foot of the wall, seen from behind.
- **takes:** USE, 0.0–5.0 s. Wan fans the stage beams wider (the real set has beams at the left).
- **first cut:** The same shot.
- **final film:** s006 0:13.22–0:14.59 (take 0.00–1.37).

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. Rear view: the car parked on the line at the foot of the tall white wall with red edge strips, white light beams fanning at the left, haze. Everything is still. 0-5 s: one slow continuous dolly-zoom (vertigo): the camera dollies back while zooming in, so the car keeps its size while the wall behind it grows taller and steeper until it fills the frame and the light beams swing wider. Slow, ominous, the calm before a launch.
```

#### g05 · G-FORCE

Wan 3.0 image-to-video · 5 s · seed 104 · $1.00

- **for:** s010 (0:15.86), s016 (0:19.77), s030 (0:28.11), s037 (0:34.59) and s136 (2:27.75): she is slammed back into the seat at the launch.
- **inputs:** first frame: rh-02 g05 #2 (her lips parted in the plate).
- **takes:** ALT, 1.0–3.5 s. Wan printed "9RC" on her chest and opened her mouth in a grin at 4–5 s. Re-rolled at once as g05-r2.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. Launch. 0-1 s: the g-force slams her back into the seat; her bob and bangs whip back. 1-3 s: her cheeks are pulled, eyes narrowed and fixed ahead, teeth gritted behind closed lips; the red light strips outside stretch into long lines racing past the glass. 3-5 s: the cockpit shakes hard; a fierce grin breaks through, lips still closed. Camera: hard-mounted on the dash, violent fine vibration, a short zoom punch at 0 s.
```

#### g05-r2 · G-FORCE, re-roll

Wan 3.0 image-to-video · 5 s · seed 205 · $1.00

- **for:** the same shots as g05.
- **inputs:** first frame: rh-02 g05 #2, as g05. The prompt adds "facing her", "the same angle the whole shot", a closed-mouth smirk in place of the grin, and a last sentence on the plain suit.
- **takes:** USE, 0.0–5.0 s: three-quarter to frontal dash view in a red and white streak tunnel, the suit plain.
- **later:** The round-2 check found her mouth open and moving, as if talking, from 0.9 to 3.5 s; it is closed from 3.55 s. Its frame at 3.65 s, lips closed, became the first frame of g05-r3 and g41.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. Launch. 0-1 s: the g-force slams her back into the seat; her bob and bangs whip back. 1-3 s: her cheeks are pulled, eyes narrowed and fixed ahead, teeth gritted behind closed lips; the red light strips outside stretch into long lines racing past the glass. 3-5 s: the cockpit shakes hard; a fierce closed-mouth smirk, her lips pressed together. Camera: hard-mounted on the dash facing her, violent fine vibration, a short zoom punch at 0 s, the same angle the whole shot. Her suit stays plain white with only the thin clay-orange piping: no letters, numbers, badges or logos ever appear on it.
```

#### g06 · YOKE

Wan 3.0 image-to-video · 5 s · seed 105 · $1.00

- **for:** s012 (0:17.46), s018 (0:20.70), s080 (1:26.85): the gloves pull the yoke, the stare.
- **inputs:** first frame: rh-02 g06 #3.
- **takes:** USE, 0.0–2.5 s. From about 3 s Wan dissolves to a white spaceship interior (the round-2 check: from 2.75 s).
- **first cut:** The same three shots.
- **final film:** s012 0:17.46–0:18.39 (take 0.00–0.93); s018 0:20.70–0:21.17 (take 1.00–1.46); s080 1:26.74–1:27.21 (take 1.90–2.33, a two-frame stutter on the chop).

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. 0-1 s: her white-gloved hands tighten on the yoke, her eyes on the lens. 1-2 s: she pulls the yoke back hard with both hands. 2-5 s: the cockpit tilts back steeply as the car climbs; the red strips outside slide down past the glass; she stares into the lens, unblinking. Camera: close on her hands, then tilting up to her face.
```

#### g07 · VERTIGO-90

Wan 3.0 image-to-video · 5 s · seed 106 · $1.00

- **for:** s024 (0:24.20), "ninety,": a dolly-zoom on the car at ninety degrees.
- **inputs:** first frame: A 8.50, Tesla's top-down shot of the car on the vertical wall face (89.7° on Tesla's readout).
- **takes:** USE, 0.0–2.5 s. From 3 s Wan turns the wall into a road with lamp posts.
- **later:** Round 2 gave s024 to the canopy dive (g37) instead. Its start frame stayed in use: the first frame of g37 and of g37sd, and the last frame of g36.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. Seen from straight above, the car is on the vertical face of the white wall, nose up, the centre stripe running down under it, black night on both sides. The car creeps slowly up the stripe. 0-1 s: almost still. 1-4 s: a dolly-zoom: the camera pulls away from the wall face while zooming in, so the car keeps its size while the wall face stretches into a long white drop beneath it and the red edge strips converge far below. 4-5 s: the camera rolls 20 degrees clockwise.
```

#### g08 · UPSIDE

Wan 3.0 image-to-video · 5 s · seed 107 · $1.00

- **for:** s028 (0:27.18), s034 (0:31.51), s043 (0:45.69): she hangs upside down in the cockpit.
- **inputs:** first frame: rh-02 g08 #2, turned 180° (Midjourney would not hang her upside down).
- **takes:** USE, 0.0–5.0 s: upside down for the whole take, a slow roll, a half-smile at 4–5 s.
- **first cut:** s043 (0:45.69), s110 (1:58.27), s159 (2:49.52), s174 (3:04.26).
- **final film:** s034 0:31.51–0:32.40 (take 1.60–1.967 at 0.41×, blended); s043 0:45.69–0:46.60 (take 2.00–2.92); s110 1:58.27–1:58.72 (take 1.90–2.35); s159 2:49.52–2:49.95 (take 3.50–3.93); s174 3:04.26–3:04.71 (take 4.20–4.66). It took over slots planned for takes that showed her teeth: g39's at s034 and s110, and g24's at s159 and s174 (already on the board's second version).

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. The car is upside down: she and the whole cockpit read upside down for the entire shot, her head toward the bottom of the frame, gravity pulling her black bob down toward the roof. 0-2 s: she hangs upside down in her harness, one gloved hand on the control stick, her bob swaying gently. 2-3 s: a slow, knowing half-smile toward the lens, lips closed. 3-5 s: the red light strips outside slide past the glass. Camera: a slow 20-degree roll. The image never flips upright.
```

#### g09 · ORBIT-UPSIDE

Wan 3.0 image-to-video · 5 s · seed 108 · $1.00

- **for:** s032 (0:29.68), s042 (0:44.32), s049 (0:53.92), s147 (2:41.09): bullet time under the car upside down at the top of the wall.
- **inputs:** first frame: A 18.20, the close underside at the top of the wall, the car upside down under the overhang, wheels against it, the round stage light above.
- **takes:** USE, 0.0–4.3 s: a bullet-time orbit under the upside-down car, head-on at 2 s, under the wheel at 4 s. At 4.5 s Wan cuts to a chassis seen from above.
- **later:** The round-2 check found a hatchback with a round rear badge from 1.6 s, the overhang shrinking to a post and a city skyline, and a generic chassis from 4.0 s; usable 0.0–1.3 s. Its slots in chorus 1 and the final drop went to g09-sd and g09-r2.
- **first cut:** s032 (0:29.68).
- **final film:** s032 0:29.68–0:30.60 (take 0.00–1.70, ramped 3.2× to 0.85×).

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. Bullet time: time is frozen; the car hangs upside down under the curved white-and-red overhang, its wheels against it, the round stage light above; nothing in the scene moves, only the camera. 0-1 s: close under the car, the camera starts to orbit to the left. 1-3 s: it swings 90 degrees around the car's nose at the same distance, the red strip and the overhang's curve sweeping past in parallax, the stage light flaring as it crosses the lens. 3-5 s: it glides in under the front wheel and looks up along the upside-down car toward the night sky.
```

#### g10 · SEAT-HERO

Wan 3.0 image-to-video · 5 s · seed 109 · $1.00

- **for:** s039 (0:36.09), the reveal: she turns from the windscreen to the lens.
- **inputs:** first frame: rh-02 g10 #2.
- **takes:** USE, 0.0–2.6 s looking off and 3.15–5.0 s facing the lens. Between them, at 2.63–3.13 s, Wan morphs her into another set, a grey bucket seat, exactly where the prompt asked for a push.
- **later:** Re-shot as g10-r2 with the camera locked off.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. She sits upright in the driver's seat, the door frame around her, red light strips outside. 0-2 s: still, eyes ahead through the windscreen. 2-3 s: in one sharp move she turns her head and looks straight into the lens. 3-5 s: she holds the stare, deadpan, the faintest lift at one corner of her mouth. Camera: a slow push from medium close-up to close-up.
```

#### g11 · IN-CAR-UPSIDE

Wan 3.0 reference-to-video · 3 s · seed 110 · $1.20 (includes 3 s of input video)

- **for:** s044 (0:46.60) and s116 (2:04.32): from the real underside to her, upside down behind the side window.
- **inputs:** Video 1: A 18.00–19.29 slowed to 0.43× to fill 3 s (the close underside, after Tesla's title has faded); Image 1: rh-02 id-full #3; Image 2: rh-02 id-face #3.
- **takes:** USE: 0.0–0.6 s the real underside, 0.6–1.8 s a dissolve, 1.8–3.0 s her upside down through the glass.
- **later:** The round-2 plan called the dissolve "a blotchy double-exposure dissolve, not a move" and replaced the shot with g44.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1 (her face exactly as in Image 2): a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. She is real and life-size, lit by the real lights of Video 1, inside the real car. Keep the real car, the set, the lights, the smoke and the camera move exactly as in Video 1; native colour; no text, no logos, no other people, no other cars. Her lips stay closed. The white car is upside down on the overhang, seen from close below, its side window glass toward us. She is inside the car, seen only through the side window: she hangs upside down in her harness, her black bob falling toward the glass, warm amber cockpit light on her face. 0-1 s: she hangs still, eyes open. 1-2 s: she turns her face toward the camera through the glass. 2-3 s: a calm, faint smile, lips closed. Nothing outside the car changes.
```

#### g12 · WEIGHTLESS

Wan 3.0 image-to-video · 5 s · seed 111 · $1.00

- **for:** s047 (0:50.72), s051 (0:56.21), s115 (2:03.19), s120 (2:08.80): her hair floats at the top of the flight.
- **inputs:** first frame: rh-02 g12 #1.
- **takes:** USE, 0.0–3.0 s: the hair floats, a glove lifts. From about 3.3 s Wan adds a blue sci-fi screen to the cockpit.
- **later:** Chorus 1's builder found her eyes rolling at about 1.73 s and her mouth opening from about 2.13 s, and kept s051 short of both.
- **first cut:** s047 (0:50.72), s051 (0:56.21), s120 (2:08.80).
- **final film:** s047 0:50.72–0:51.64 (take 0.50–1.42, turned in code to carry the world's spin through her); s051 0:56.21–0:57.12 (take 1.435–1.66 at 0.25×, blended); s120 2:08.80–2:09.82 (take 1.00–2.02).

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. Weightless at the top of the flight. 0-1 s: her bob already lifting. 1-3 s: her hair floats and drifts around her face in slow motion, strands rising, the star clip glinting; one gloved hand lifts off the controls and floats. 3-5 s: she glances up, then calmly back into the lens. Camera: a slow float with a slight roll, as if the camera is weightless too.
```

#### g13 · CRANE-HOVER

Wan 3.0 image-to-video · 5 s · seed 112 · $1.00

- **for:** s052 (0:57.12) and s119 (2:07.68): the camera rises over the car hovering in its smoke.
- **inputs:** first frame: C 19.00 (the 1080p stream), the car hovering on its plumes beside the wall.
- **takes:** PART, 0.0–2.5 s: the real hover. From about 2.7 s, as the roof comes into view, the car becomes a generic white sedan seen from above.
- **later:** Both slots went to the Seedance crane g13-sd.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car hovers above the ground on white thruster plumes beside the tall white wall, headlights on, a huge cloud of white smoke churning under it. The car keeps hovering; the plumes and the smoke keep billowing. 0-3 s: the camera rises fast and arcs up and over the hovering car. 3-5 s: it ends looking straight down at the car's white roof through the swirling smoke and the plumes.
```

#### g14 · ORBIT-RAMP-END

Wan 3.0 image-to-video · 5 s · seed 113 · $1.00

- **for:** s056 (1:01.21) and s149 (2:42.41): time freezes as the car leaves the end of the ramp, and the camera orbits it.
- **inputs:** first frame: C 26.25, the drone above the ramp's steel truss as the car leaves its end on its jets.
- **takes:** PART, 0.0–1.8 s. From about 2 s the car turns dark grey and lands on a race track.
- **later:** The round-2 check: usable 0.0–0.45 s; the window `TAKES.md` gave s149 (0.5–0.95 s) shows a scaffold tower.
- **first cut:** s056 (1:01.21) at 2×. anabology: "at 1:01 the car glitches and rights itself  - need to reshoot that." Re-shot in Seedance as g14sd.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. Drone view: the car is leaving the end of the steel-truss ramp sideways on two white thruster jets, its red light strips below, a bright light in the dark. 0-3 s: time freezes with the car hanging off the end of the ramp, the jets frozen like glass; the camera orbits 120 degrees around it, the truss, its red light strips and the night wheeling behind. 3-5 s: time resumes; the car rolls away and down out of frame on its jets.
```

#### g15 · G-PROFILE

Wan 3.0 image-to-video · 5 s · seed 114 · $1.00

- **for:** s061 (1:05.09) and s125 (2:15.78): her profile, pinned back by the acceleration.
- **inputs:** first frame: rh-02 g15 #1.
- **takes:** USE, 0.0–5.0 s: the red and white streaks race past the window from about 1.5 s.
- **first cut:** s125 (2:15.78).
- **final film:** s076 1:24.46–1:25.39 (take 1.00–1.92); s125 2:15.78–2:17.73 (take 0.50–2.45). s076 came to it in the final film from g19-r2, whose lips were parted.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. Profile. 0-1 s: she stares ahead. 1-3 s: acceleration pins her back; her bob whips back; the red light streaks outside the window stretch and race past, faster and faster. 3-5 s: the streaks blur into solid lines of light; her eyes narrow. Camera: locked on her profile, fine vibration, a small zoom punch at 1 s.
```

#### g16 · SMOKE-DOLLY

Wan 3.0 image-to-video · 5 s · seed 115 · $1.00

- **for:** s071 (1:15.42): a slow push into the landing cloud.
- **inputs:** first frame: A 52.00, the smoke cloud after the touchdown, the car low in it.
- **takes:** PART, 0.0–1.8 s. From about 2.3 s a generic sedan comes out of the smoke.
- **later:** The round-2 check: the wrong car, seen side-on, from 0.3 s. Re-made without a car as g16-r2.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. A huge cloud of white smoke after a landing, lit white and pink-red, the white car low in the smoke at the centre. The smoke keeps billowing slowly. 0-1 s: the camera dollies fast toward the car at car height. 1-3 s: it plunges into the smoke; the frame goes soft white; the car's shape appears inside it. 3-5 s: it bursts out beside the car and swings around its flank to the rear, the red light glowing through the smoke.
```

#### g17 · FLY-LINEUP

Wan 3.0 image-to-video · 5 s · seed 116 · $1.00

- **for:** s072 (1:17.24), the break: a flight along the centre line to the lineup.
- **inputs:** first frame: A 60.50, the car on the centre line, the Semi and the lineup behind it (Tesla's title inpainted).
- **takes:** PART, 0.0–1.8 s. From about 2 s the car turns red and the lineup is reinvented.
- **later:** The round-2 check found it better than recorded: the "red car" is the car's tail light bar and the gold car is real; the trouble starts at a cut at 2.63 s.
- **first cut:** The same shot.
- **final film:** s072 1:17.24–1:19.07 (take 0.00–1.76). Framed at 1.05× or more to crop a mark Wan put in the top-left corner.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car sits on the white centre line, the Semi truck and the lineup of cars behind it under a tall stadium light, night haze. The car stays still. 0-2 s: the camera flies forward fast and low along the white centre line toward the car. 2-4 s: it rises over the car's roof and over the Semi and the lineup, tilting down. 4-5 s: it looks straight down on the lineup from high above.
```

#### g18 · HEADLIGHTS-CROSS (CENTRE-LINE in TAKES.md)

Wan 3.0 reference-to-video · 3 s · seed 117 · $1.20 (includes 3 s of input video)

- **for:** s073 (1:19.07): she steps onto the centre line behind the departing car.
- **inputs:** Video 1: A 59.50–62.50, 3 s, the car driving away along the centre line toward the Semi and the lineup; Image 1: rh-02 id-full #3; Image 2: rh-02 id-face #3.
- **takes:** USE, 0.0–3.0 s: she steps onto the centre line, walks after the car, glances back over her shoulder at 2.4–3.0 s.
- **first cut:** The same shot.
- **final film:** s073 1:19.07–1:20.90 (take 1.10–2.93). The PILOT ✶ CLAUDIA callout rides her, keyed to her head as read off the take.

Prompt:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1 (her face exactly as in Image 2): a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. She is real and life-size, lit by the real lights of Video 1, standing and walking on the real ground. Keep the real car, the set, the lights, the smoke and the camera move exactly as in Video 1; native colour; no text, no logos, no other people, no other cars. Her lips stay closed. The camera looks along the white centre line as the white car drives away from us toward the Semi truck and the lineup under the stadium light. 0-0.8 s: she steps into frame from the left onto the white centre line, between the camera and the departing car, her back to us. 0.8-2.2 s: she walks along the centre line after the car, its red tail lights ahead of her. 2.2-3 s: she stops on the line and glances back over her shoulder at the lens, deadpan.
```

#### g19 · LOOK-UP

Wan 3.0 image-to-video · 5 s · seed 118 · $1.00

- **for:** s076 (1:24.56): she looks up at the sky she is about to fly through.
- **inputs:** first frame: rh-02 g19 #3 (her lips parted in the plate).
- **takes:** USE, 0.0–5.0 s: she looks up; a bright light sweeps over the glass.
- **later:** The round-2 check: her lips are parted with teeth in every frame, and a chrome object like a robot glove flies through the cockpit across her face from 0.75 s. The prompt had asked for "two white thruster plumes" to sweep across the glass. Re-made as g19-r2.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. Her head is tilted back in the seat, looking up through the glass roof; red light strips outside. 0-1.5 s: she looks up, still. 1.5-3.5 s: two white thruster plumes and a bright light sweep across the glass above her from left to right; her eyes track them. 3.5-5 s: the light passes; she slowly lowers her gaze. Camera: a slow tilt from her face up toward the glass roof.
```

#### g20 · FREEZE-KICKFLIP

Wan 3.0 image-to-video · 5 s · seed 119 · $1.00

- **for:** s088 (1:33.75), s111 (1:58.72), s130 (2:20.41) and s156 (2:46.63): the kickflip frozen upside down, the camera orbiting it.
- **inputs:** first frame: A 80.00, the kickflip replay: the car upside down in the air, its chassis toward the camera, plumes under it (Tesla's title inpainted).
- **takes:** PART, 0.0–2.2 s. From about 2.5 s the car becomes a sedan landing in a car park.
- **later:** The round-2 check: usable 0.0–1.0 s (it grows an alloy wheel from 1.0 s). Repaired in Seedance as g20-sd; its start frame became @Image2 of g32 and g32sd2.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. Bullet time: time is frozen mid-kickflip: the car is upside down in the air, its dark chassis toward us, the white thruster plumes frozen like columns, a light pole and power lines behind. Only the camera moves. 0-1 s: it begins to orbit upward around the car. 1-4 s: it travels 180 degrees around and over the car, ending above it, looking down on its white roof with the parked vehicles and the red light strips far below. 4-5 s: time resumes; the car rolls on.
```

#### g21 · WALL-PORTRAIT

Wan 3.0 image-to-video · 5 s · seed 120 · $1.00

- **for:** s097 (1:44.68), "Where we're": she stands at the foot of the wall and looks up it.
- **inputs:** first frame: rh-02 g21 #3.
- **takes:** USE, 0.0–5.0 s: the stare, the look up the wall, the crane up the curve.
- **first cut:** The same shot.
- **final film:** s097 1:44.68–1:46.51 (take 0.35–2.18).

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. She stands at the foot of a gigantic curved white concrete wall that bends up into the night, thin red lights along its edges, haze. 0-1.5 s: she stares into the lens, deadpan. 1.5-3 s: she tips her head back and looks up the curve of the wall. 3-5 s: the camera cranes up past her and rises along the curved wall into the night, the red edge lights sliding past the lens.
```

#### g22 · VERTIGO-PILLAR

Wan 3.0 image-to-video · 5 s · seed 121 · $1.00

- **for:** s098 (1:46.51), "going…": a vertigo push on the car between the red pillar and the fans of white light.
- **inputs:** first frame: A 86.00, head-on between the red light pillar and the white light fans before the vertical jump (Tesla's title inpainted).
- **takes:** USE, 0.0–5.0 s. Wan adds stands at the sides of the set from about 3 s.
- **first cut:** The same shot.
- **final film:** s098 1:46.51–1:48.34 (take 1.00–2.83).

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. Night stage: the car faces us, headlights on, on the dark road with its white centre line, between a tall red light pillar and fans of white spark lights; black sky. The car rolls slowly toward us. 0-5 s: a vertigo dolly-zoom: the camera pushes in while the lens widens; the car keeps its size while the red pillar stretches upward and the white light fans splay outward.
```

#### g23 · APEX-VJUMP

Wan 3.0 image-to-video · 5 s · seed 122 · $1.00

- **for:** s101 (1:52.00) and s117 (2:05.41): bullet time at the top of the vertical jump.
- **inputs:** first frame: A 90.35, the car at the apex of the vertical jump facing the camera, plumes under it. The storyboard's frame (A 89.80) was too blurry; the lead re-cut it at 90.35, where the car is level and head-on.
- **takes:** PART, 0.0–1.3 s. From about 2 s the car becomes a Porsche-like sedan on a race track.
- **later:** The round-2 check: Porsche-like headlights from 0.6 s. Repaired in Seedance as g23-sd.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. Bullet time: the car hangs in the air facing us beside the tall red light pillar, its headlights and light bar blazing, two white thruster plumes frozen beneath it, black sky, white stage lights far behind. Time is frozen; only the camera moves. 0-1 s: the camera starts to rise and circle. 1-4 s: it orbits 100 degrees around the hovering car to its side, the red pillar swinging behind it, the headlights flaring across the lens. 4-5 s: time resumes; the car drops toward the road on its plumes.
```

#### g24 · UPSIDE-YOKE

Wan 3.0 image-to-video · 5 s · seed 123 · $1.00

- **for:** s110 (1:58.27), s159 (2:49.52) and s174 (3:04.26): upside down at the yoke.
- **inputs:** first frame: rh-02 g24 #3, turned 180° (her lips parted in the plate).
- **takes:** USE, 0.0–5.0 s: upside down for the whole take, a push and a roll, a glance to the lens.
- **later:** Her upper teeth show throughout. The round-2 plan folded its repair into g39; in the cut, g08 took its slots.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. The car is upside down: she and the whole cockpit read upside down for the entire shot, her head toward the bottom of the frame, gravity pulling her black bob down toward the roof. 0-2.5 s: she hangs in her harness, both gloved hands steady on the controls, her bob swaying; the red strips slide past the glass. 2.5-5 s: she glances into the lens, deadpan, and holds. Camera: a slow push with a slight roll. The image never flips upright.
```

#### g25 · MIC-GO

Wan 3.0 image-to-video · 5 s · seed 124 · $1.00

- **for:** s132 (2:23.30), "Thrusters.": she presses her headset mic and nods.
- **inputs:** first frame: rh-02 g25 #3.
- **takes:** USE, 0.0–2.0 s: the finger at the mic, the stare; the press never happens. From 3 s Wan moves her into a bright white spaceship interior and adds an arm badge.
- **later:** The round-2 check: the gloved index finger is about twice its natural length, already in the plate. Re-made from rh-02 g25 #2 as g25-r2.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the cockpit, the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. In the cockpit, one gloved finger at her cheek by the headset microphone, eyes on the lens. 0-1 s: still. 1-2 s: she presses the microphone with her finger and gives one small nod. 2-4 s: the cockpit jolts upward hard; the red strips outside drop out of the frame; her hair lifts. 4-5 s: she holds a fierce stare. Camera: dash mount, jolting with the car.
```

#### g26 · TRACK-PROFILE

Wan 3.0 image-to-video · 5 s · seed 125 · $1.00

- **for:** s142 (2:34.07), "Flying cars are": the camera tracks the flying car and swings to its nose.
- **inputs:** first frame: A 80.60, the kickflip replay: the car flying level in profile on two plumes.
- **takes:** USE, 0.0–5.0 s: the track, the swing head-on, the car passing over the camera; the lead found the car's shape held.
- **later:** The round-2 check found a short-haired man in profile in the driver's window from 0.9 s, inside the board's window, and a sedan's underside at 3–4 s. The real demo car was empty, and in the film she is the pilot. Re-made as g26-r2.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The white car flies level in profile on two white thruster plumes, the light under it red, a light pole and power lines behind. The car keeps flying forward slowly. 0-2 s: the camera tracks beside it at the same speed. 2-4 s: it swings around the car's nose to face it head-on, the headlights flaring. 4-5 s: the car passes low over the camera.
```

#### g27 · WALK-OUT-LINEUP

Wan 3.0 reference-to-video · 4 s · seed 126 · $1.60 (includes 4 s of input video)

- **for:** s143 (2:35.90), REAL!: she walks out of the real kickflip smoke.
- **inputs:** Video 1: B 11.00–15.00, 4 s, the lineup camera's view of the smoke billowing across the lot after the kickflip landing; Image 1: rh-02 id-full #3; Image 2: rh-02 id-face #3.
- **takes:** USE, 0.8–2.6 s the walk and 3.0–4.0 s a close-up. Wan cuts on its own to the close-up; the lead took it for the look to the lens.
- **later:** The round-2 check: the cut comes at 2.47 s; the close-up has a lettered collar badge and is another set; a generic coupe stands in the smoke during the walk. Re-made in round 2 as g27-r2, which the first cut used.
- **first cut:** not used.
- **final film:** s143 2:35.90–2:39.56 (take 1.067–1.567, frames 33–48, one take frame per eighth note and then per snare of the roll, never blended). In the final film the round-1 take came back. A chapter fixer had put its close-up window (3.0–3.367 s) under REAL!; the whole-film critic flagged it as a blocker (another set, off-model, a second mic tip), and the fix made s143 one held walk-out again, as the storyboard has it. The fixer stopped at frame 48: from about 1.3 s Wan's invented white coupe sharpens in the smoke behind her, and it stays faintly visible from 2:38.4 to 2:39.48.

Prompt:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1 (her face exactly as in Image 2): a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. She is real and life-size, lit by the real lights of Video 1, standing and walking on the real ground. Keep the real car, the set, the lights, the smoke and the camera move exactly as in Video 1; native colour; no text, no logos, no other people, no other cars. Her lips stay closed. White smoke billows across the lot; the Semi truck and cars stand behind it; a steel pole at the right. 0-2.5 s: she walks out of the billowing smoke toward the camera, between the parked vehicles, smoke curling around her legs. 2.5-3.5 s: she stops close, in a medium shot. 3.5-4 s: she looks into the lens, deadpan.
```

#### g28 · WALK-OUT-RED

Wan 3.0 reference-to-video · 5 s · seed 127 · $1.99 (includes 4.97 s of input video)

- **for:** s164 (2:54.20): after the last landing she walks out of the red smoke.
- **inputs:** Video 1: A 100.30–105.27, 4.97 s, the replay of the vertical jump's landing in red smoke; Image 1: rh-02 id-full #3; Image 2: rh-02 id-face #3.
- **takes:** USE, 0.0–2.1 s the real landing, 2.5–3.8 s the walk, 4.0–5.0 s a close-up: Wan cuts to her walking out of red smoke in front of a white car, then to her close-up.
- **later:** The round-2 check: four orange fire nozzles at 0.2–1.0 s where the real car blows cold gas, a hard cut at 2.24 s to a new set with an invented car, a licence plate from 3.0 s, and her faded in semi-transparent. Re-made as g28-r2.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1 (her face exactly as in Image 2): a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. She is real and life-size, lit by the real lights of Video 1, standing and walking on the real ground. Keep the real car, the set, the lights, the smoke and the camera move exactly as in Video 1; native colour; no text, no logos, no other people, no other cars. Her lips stay closed. 0-2 s: as Video 1: the white car comes down on its white thruster plumes and lands in a cloud of red-lit smoke. 2-4 s: she walks out of the red-lit smoke in front of the landed car, toward the camera. 4-5 s: she stops and looks into the lens, deadpan.
```

#### g29 · DEADPAN

Wan 3.0 image-to-video · 5 s · seed 128 · $1.00

- **for:** s165 (2:57.26), "Tell 'em what you saw.": she looks into the lens, lips closed.
- **inputs:** first frame: rh-02 g29 #4.
- **takes:** USE, 0.0–5.0 s: red-lit smoke, red strips behind her, a faint smile at the end.
- **later:** The round-2 repair scout judged that the take reads young at this close size ("soft round face, very large eyes, full cheeks"). The round-2 plan kept a $1 re-roll on plate #2 in reserve; it was not put to anabology and was not run.
- **first cut:** The same shot.
- **final film:** s165 2:57.26–2:59.48 (take 1.00–3.22).

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; keep the set and the light exactly as in Image 1, native colour. One continuous shot, no cuts. Her lips stay closed; she never talks. No text, no logos, no other people. She stands at night in drifting smoke lit red, red light strips behind her. 0-5 s: she looks straight into the lens and holds, utterly calm; at 3 s one corner of her mouth lifts a little; the red-lit smoke drifts behind her. Camera: locked, a slow 3 percent push.
```

### The Seedance repairs

Two of the bullet-time orbits needed seconds of the take after Wan had lost the car: the vertical jump's apex (g23) and the frozen kickflip (g20). The lead rewrote both for Seedance, with the real start frame and three real frames of the car's other sides; $11.37 at list.

#### g23-sd · APEX-VJUMP, Seedance

Seedance 2.5 reference-to-video · 5 s · $5.69

- **for:** s101 (1:52.00) and s117 (2:05.41), which need the orbit's later seconds that Wan's g23 lost.
- **inputs:** @Image1, the first frame: A 90.35 (g23's start). @Image2: A 86.00, the same car head-on on the road between the pillar and the fans (g22's start). @Image3: A 80.60, its side profile in flight (g26's start). @Image4: A 36.00, its rear (g04's start).
- **takes:** USE, 0.0–3.45 s: the real car kept, head-on by the red pillar, then the orbit to its side profile. At 3.5 s Seedance cuts to its rear-view reference by the wall.
- **later:** The round-2 check: the car holds, but from 2.0 s the background turns into @Image3's sky with power lines. Round 2 cut its references tight, on black.
- **first cut:** The same two shots.
- **final film:** s101 1:52.00–1:52.92 (take 0.00–1.20, ramped 1.0× to 1.9×); s117 2:05.41–2:06.57 (take 1.50–2.66).

Prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Bullet time at night: a real white electric sports car hangs frozen in mid-air facing us beside a tall red light pillar, held up by two white thruster plumes, and the camera circles it while time stands still.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the car in the air facing the camera with its headlights and light bar blazing, the two white plumes beneath it, the tall red light pillar on the left, the black sky and where the camera starts.
@Image2 shows the SAME car on the same stage, on the road with its white centre line between the red light pillar and fans of white lights: use it for the car's front, the pillar and the stage. @Image3 shows the same car's side profile flying on two plumes and @Image4 its rear: use them only for the car's exact shape and details when the orbit reveals those sides. Do not take their framing or lighting.

【Event Timeline】
0-1s: time is frozen; the car hangs facing us, headlights blazing, the plumes frozen; the camera starts to rise and circle to the right.
1-4s: the camera orbits about 100 degrees around the frozen car to its side, the red pillar swinging behind it, the headlights flaring across the lens and then turning away, revealing the car's white side profile; nothing in the scene moves.
4-5s: time resumes; the car drops toward the road on its plumes.

【Camera】 One continuous orbit around the car at a constant distance, rising slightly, smooth like a motion-control rig, with true parallax; no cuts.

【Core Requirements】
1. The car is exactly the real car of the reference images in every frame: a low, wide white two-door electric sports car with a long black glass canopy, a sharp wedge nose and black wheels; the same proportions and details; it never turns into a different car, never a sedan, never another colour, and there is only this one car in the air.
2. Native colour of the night footage: black sky, white car, white plumes, red light; no grade, no added lens effects beyond what the lights make.
3. No people. No new vehicles, buildings, stands or crowds are added.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 One continuous bullet-time orbit around the same real white car beside the red pillar, frozen 0-4 s; the car never changes model or colour; no people, no text.

【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

#### g20-sd · FREEZE-KICKFLIP, Seedance

Seedance 2.5 reference-to-video · 5 s · $5.69

- **for:** s130 (2:20.41) and s156 (2:46.63), which need the later orbit that Wan's g20 lost; also s088 (1:33.75) and s111 (1:58.72).
- **inputs:** @Image1, the first frame: A 80.00 (g20's start). @Image2: A 80.60, the side profile on two plumes (g26's start). @Image3: A 18.20, its side upside down under the overhang (g09's start). @Image4: A 8.50, its roof and canopy from straight above (g07's start).
- **takes:** USE, 0.0–2.9 s: the real car kept, from the frozen underside round to its white side profile on the plumes. At 2.92 s and again at 4.0 s Seedance cuts to its reference images (the overhang, the top-down). The lead's lesson in TAKES.md: Seedance keeps the car with three or four real reference frames, but cuts to them unless told they are not shots.
- **later:** The round-2 check: it morphs into a tall hatchback from 2.25 s; usable 0.0–2.2 s. The riser slots (s130, s156) went to g32.
- **first cut:** s088 (1:33.75) and s111 (1:58.72).
- **final film:** s088 1:33.75–1:34.89 (take 0.00–1.14); s111 1:58.72–1:59.84 (take 1.00–2.11).

Prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Bullet time at night: a real white electric sports car hangs frozen upside down in mid-air in the middle of a kickflip, on white thruster plumes, and the camera makes one continuous orbit around it while time stands still.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the car's position upside down in the air with its dark chassis toward the camera, the frozen white thruster plumes, the light pole and power lines, the black night and where the camera starts.
@Image2, @Image3 and @Image4 show the SAME real car from its other sides (its side profile flying on two plumes, its side while upside down under a ramp, its white roof and black glass canopy from straight above). Use them only for the car's exact shape, proportions, colour and details when the orbit reveals those sides. Do not take their backgrounds, framing or lighting.

【Event Timeline】
0-1s: time is frozen; the car hangs upside down, chassis toward us, the white plumes frozen like columns; the camera begins to orbit upward around it.
1-4s: the camera travels about 180 degrees around and over the frozen car, revealing its white side, then its white roof and black glass canopy from above, with a few dark parked vehicles and red light strips far below on the ground; nothing in the scene moves.
4-5s: time resumes: the plumes flow again and the car rolls on through the air.

【Camera】 One continuous orbit around the car at a constant distance, smooth like a motion-control rig, with true parallax; it starts at the framing of @Image1 and ends above the car looking down; no cuts.

【Core Requirements】
1. The car is exactly the real car of the reference images in every frame: a low, wide white two-door electric sports car with a long black glass canopy, a sharp wedge nose and black wheels; the same proportions and details; it never turns into a different car, never a sedan, never another colour, and there is only this one car in the air.
2. Native colour of the night footage: black sky, white car, white plumes, red light; no grade, no added lens effects beyond what the lights make.
3. No people. No new vehicles, buildings, stands or crowds are added.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 One continuous bullet-time orbit around the same real white car, frozen 0-4 s; the car never changes model or colour; no people, no text.

【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

### SpaceX's Starman footage

anabology sent the footage for "while my sister's still in orbit, circling the sun" (1:38.74–1:42.38). The plan: the real side angle, an orbit round the car, a pull-back that shrinks it to a red point by the Earth, and the real JPL orbit drawn in code from that point. The orbit went to Wan and Seedance at once, to keep the better; $7.69 at list.

#### g30 · STARMAN-PULLBACK

Wan 3.0 image-to-video · 5 s · seed 130 · $1.00

- **for:** s095 (1:41.44), "circling the sun": from SpaceX's footage, a pull-back until the car is a red point on the Earth, which the code hands to the real JPL orbit.
- **inputs:** first frame: D 24.00, SpaceX's side view of the red Roadster and Starman with the whole Earth behind (no titles in this footage, so nothing inpainted).
- **takes:** USE, 0.0–5.0 s: the pull-back until the car is a red point by the Earth. Wan added faint stars.
- **first cut:** The same shot.
- **final film:** s095 1:41.44–1:42.85 (take 1.50–4.95, ramped; then the camera keeps pulling back in code and the Earth collapses onto its marker on the JPL orbit).

Prompt:

```
Image 1 is the first frame of real footage filmed in space in 2018: the red open-top 2008 sports car with a mannequin in a white spacesuit and white helmet in the driver's seat, the blue Earth behind it, black space. Keep everything exactly as it is: the red car and its exact shape, the astronaut mannequin (it never moves on its own), the Earth, the black sky, the hard sunlight; native colour, no grade, no new objects, no people, no text, no logos, no stars added. One continuous shot, no cuts. 0-1 s: almost still; the car drifts slowly, the Earth turning behind it. 1-4 s: the camera pulls straight back away from the car into deep space, fast at first and then slower; the red car and the astronaut shrink, and the whole round Earth comes into view behind them, blue and white, hanging in black space. 4-5 s: the car is a tiny red point of light far from the camera, beside the curve of the Earth, and holds there.
```

#### g31w · STARMAN-ORBIT, Wan

Wan 3.0 image-to-video · 5 s · seed 131 · $1.00

- **for:** s094 (1:40.08), "orbit, circling": a slow orbit from the car's side round its tail. Run on Wan and Seedance at once, to keep the better.
- **inputs:** first frame: D 22.00, the car's side with the Earth behind.
- **takes:** PART, 0.0–2.5 and 3.8–5.0 s. At about 2.8–3.6 s the frame shows two Earths.
- **first cut:** not used.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real footage filmed in space in 2018: the red open-top 2008 sports car with a mannequin in a white spacesuit and white helmet in the driver's seat, the blue Earth behind it, black space. Keep everything exactly as it is: the red car and its exact shape, the astronaut mannequin (it never moves on its own), the Earth, the black sky, the hard sunlight; native colour, no grade, no new objects, no people, no text, no logos, no stars added. One continuous shot, no cuts. 0-1 s: almost still, the car drifting, the Earth behind. 1-4 s: the camera orbits slowly around the car at the same distance, from its side around its tail, the Earth swinging behind the car, the sunlight sliding across the red paint. 4-5 s: it ends behind the car, looking over the boot and the astronaut's helmet toward the Earth.
```

#### g31 · STARMAN-ORBIT, Seedance

Seedance 2.5 reference-to-video · 5 s · $5.69

- **for:** s094 (1:40.08), as g31w.
- **inputs:** @Image1, the first frame: D 22.00. @Image2: D 4.00, the same car from behind. @Image3: D 14.00, over Starman's shoulder, DON'T PANIC on the dash.
- **takes:** USE, 0.0–3.6 and 3.9–5.0 s: one continuous move from the side, round the helmet and in behind it toward the cockpit. At 3.67 s it cuts to the over-the-shoulder view, @Image3's angle, which is usable too. The keeper over g31w.
- **first cut:** The same shot.
- **final film:** s094 1:40.08–1:41.44 (take 1.90–2.95, already round at the helmet, so the cut from SpaceX's own view is a new angle).

Prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】 Real footage from space, 2018: the red open-top 2008 sports car drifts above the Earth with a mannequin in a white spacesuit at the wheel, and the camera makes one slow, continuous orbit around it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the car's side, the astronaut, the Earth behind them, the black sky, the hard sunlight and where the camera starts.
@Image2 (the same car seen from behind) and @Image3 (the same car seen over the astronaut's shoulder) show the SAME car and astronaut from the angles the orbit reaches: use them only for the shape and details of the car's tail, boot, seats and dashboard. @Image2 and @Image3 are never shown as shots of this video; there are no cuts to them.

【Event Timeline】
0-1s: almost still; the car drifts, the Earth turning slowly behind it.
1-4s: the camera orbits slowly around the car at the same distance, from its side around its tail, the Earth swinging behind the car and the sunlight sliding across the red paint; the astronaut does not move.
4-5s: the camera ends behind the car, looking over the boot and the astronaut's helmet toward the Earth.

【Camera】 One continuous orbit from the side to behind the car, smooth like a motion-control rig, true parallax; no cuts, no dissolves.

【Core Requirements】
1. The car is exactly the real red 2008 open-top sports car of the images, same shape and details, in every frame; one car only.
2. The astronaut is the same white-suited mannequin, still, hands on the wheel.
3. Native colour, black space, the real Earth; no stars, planets, ships or objects added.
4. One continuous shot: no cuts, no dissolves, no shots of the reference images.
5. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】 One continuous orbit from the car's side to behind it, the same real car and astronaut throughout, the Earth behind; no cuts; no text.

【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

### Round 2 · the head director's plan

A workflow run planned how to spend the raised budget: three scouts, then a head director who ranked 25 shots by impact per dollar, extracted and checked every start frame, and drafted every prompt (`wf/GEN2-PLAN.md`). Repairs of wrong pictures inside the storyboard's windows came first, then the strongest new angles, then her moments. The key shots got two takes: 34 jobs, $52.73 at list. One runner submitted them six at a time, and a second runner worked from the end of the queue. The plan asked for 720p probes of the two moves to her through the glass (g37, g44); both went out at 1080p directly. The lead logged each take as it landed; the last two to be judged were g36 and g13-sd.

#### g32 and g32-t2 · FREEZE-LINEUP · rank 1

Seedance 2.5 reference-to-video · 4 s × 2 takes · $9.10

- **for:** s130 (2:20.41), the riser: bullet time over the Semi, released on the 2:22.19 hit by the real roll from the same camera; s156 (2:46.63) in the final drop; optionally s111 (1:58.72). The plan's reason: g20 (Wan) is a sedan in a car park in these windows and g20-sd a hatchback from 2.25 s.
- **inputs:** @Image1, the first frame: A 64.25, Tesla's side camera: the car upside down mid-kickflip high over the Semi and two sedans, four plumes in an X. @Image2: A 80.00, its underside, close (g20's start). @Image3: A 79.30, its side upside down, wheels up. @Image4: A 78.30, its roof and canopy on black. The three references are from the same kickflip replay.
- **takes:** Take 1: USE (the hero), 0.0–2.4 s: one continuous frozen orbit, the canopy turning to us at 1.7 s, the white side at 2.3 s. From about 2.6 s the lineup drifts away into a pole-and-sky framing. Take 2: PART, 0.0–1.65 s; at 1.71 s it cuts to other framings.
- **first cut:** Take 1 at s130 (2:20.41) and s156 (2:46.63). anabology: "2:21 loses the front wheels and 2:22 flips the car glitching." and "2:47 looks like the same shot - lost front wheels." Re-shot as g32sd2.
- **final film:** not used.

Both takes, the same prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice. 【Generation Goal】 Bullet time at night over a lineup of parked vehicles: the real white electric sports car hangs frozen upside down in mid-kickflip high above a white electric semi truck and two dark sedans, four white cold-gas thruster plumes frozen in an X around it; the camera makes one continuous orbit around the frozen car while time stands still. 【Reference Asset Roles】 Use @Image1 as the first frame. This first frame defines the car upside down in the air with its dark chassis and two headlights toward the camera, the four frozen white plumes, the white semi truck and the two dark sedans on the platform edged with red light strips, the curved steel-truss ramp on the left, the stadium light on the right, the haze, the black sky and where the camera starts. @Image2 (its underside, close), @Image3 (its white side upside down, wheels toward the sky) and @Image4 (its white roof with the long black glass canopy) show the SAME car in the SAME kickflip on the same night; use them only for the car's exact shape, proportions and details when the orbit reveals those sides. They are never shown as shots: never cut to them, never take their framing, power lines, backgrounds or lighting. 【Event Timeline】 0-1s: time is frozen; the plumes stand like glass columns; the camera starts to orbit to the right and slightly down. 1-3s: the camera travels about 90 degrees around the frozen car at the same distance; the semi truck, the sedans and the red strips slide beneath it in deep parallax; the stadium light flares across the lens; the car's white side, upside down with its wheels toward the sky, turns to face the camera. Nothing in the scene moves. 3-4s: the orbit eases to a stop slightly below the car, the semi truck's white cab under it; still frozen. 【Camera】 One continuous orbit at constant distance, motion-control smooth, true parallax, starting exactly at the framing of @Image1; no cuts, no dissolves, no jumps. 【Core Requirements】 1. Exactly the real car in every frame: low, wide, white two-door, long black glass canopy, sharp wedge nose, black wheels; its roofline stays low and never rises; never a sedan, hatchback or another colour; nobody inside; the only car in the air; it stays high above the lineup and never descends. 2. Semi, sedans, truss ramp and red strips stay as in @Image1; no new vehicles, stands, crowds, buildings, tracks or city lights. 3. White cold-gas vapour, never flame. 4. Native colour; no grade. 5. No people; no subtitles, captions, titles, signs, logos, watermarks or on-screen text. 6. One continuous shot: it never cuts to a reference image. 【Final Acceptance Criteria】 One continuous bullet-time orbit from @Image1, frozen 0-4 s; the same real car in every frame; @Image2-@Image4 never appear as shots; no people, no text. 【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

#### g09-sd · ORBIT-UPSIDE, Seedance · rank 2

Seedance 2.5 reference-to-video · 4 s · $4.55

- **for:** s042 (0:44.32), "Hold me,", and s147 (2:41.09): the orbit under the upside-down car, round its nose. The plan's reason: Wan's g09 becomes a hatchback from 1.6 s in three board windows.
- **inputs:** @Image1, the first frame: A 18.20 (g09's start). @Image2: A 78.30, roof and canopy on black. @Image3: A 50.25, a tight crop of its front three-quarter with the headlights. @Image4: A 77.60, its upright side on two plumes.
- **takes:** USE, 0.0–2.3 s: the orbit round the nose. At 2.42 s it cuts to its references.
- **first cut:** The same two shots.
- **final film:** s042 0:44.32–0:45.69 (take 0.88–1.55, ramped; opened in the stage light's flare); s147 2:41.09–2:41.75 (take 1.60–2.26). The whole-film critic found chorus 1 opening on nearly the same picture as the chapter before it (s032, g09 from the same frame); the fix moved s042's window from 0.40 to 0.88 s so it opens round the nose, in the flare.

Prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice. 【Generation Goal】 Bullet time at night: the real white electric sports car hangs upside down under the wide curved white-and-red overhang at the top of a tall wall, its wheels pressed against it, and the camera circles under it while time stands still. 【Reference Asset Roles】 Use @Image1 as the first frame. This first frame defines the car upside down under the overhang, the red strip along the overhang's edge, the round stage light and truss above, the black night below, and where the camera starts. @Image2 (its white roof and long black glass canopy), @Image3 (its front: headlights and sharp wedge nose) and @Image4 (its side profile) show the SAME car from other sides; use them only for the car's exact shape and details when the orbit reveals those sides; never take their backgrounds, smoke, plumes, lighting or framing, and never show @Image2, @Image3 or @Image4 as shots. 【Event Timeline】 0-1s: frozen; close under the car, the camera starts to circle toward the car's nose. 1-3s: it swings about 80 degrees around the nose at the same distance; the wide curved overhang and its red strip sweep past in parallax; the stage light flares across the lens; the upside-down front with its headlights comes into view. 3-4s: it rises in under the front wheel and looks up along the upside-down car to the night sky. Nothing in the scene moves. 【Camera】 One continuous orbit at constant distance, motion-control smooth, true parallax, starting at @Image1's framing; no cuts. 【Core Requirements】 1. Exactly the real car in every frame: low, wide, white two-door, long black glass canopy, sharp wedge nose, black aero wheel covers; never a sedan or hatchback; no badge or emblem; nobody inside (dark glass). 2. The overhang stays a wide curved white wall with a red edge strip; never a post, pillar or beam. 3. Native colour; no grade. 4. No people; no new vehicles, buildings, stands, crowds or city lights. 5. No subtitles, captions, titles, signs, logos, watermarks or on-screen text. 6. One continuous shot: it never cuts to a reference image. 【Final Acceptance Criteria】 One continuous bullet-time orbit under the same real car, frozen 0-4 s; car and overhang never change; no people, no text. 【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

#### g09-r2 · SLIDE-UPSIDE · rank 3

Wan 3.0 image-to-video · 5 s · seed 209 · $1.00

- **for:** s049 (0:53.92), "upside down": a second, different move on the hold, which stays on the side Wan can see.
- **inputs:** first frame: A 18.20 (g09's start).
- **takes:** USE, 0.0–5.0 s: the slide along the upside-down car under the overhang; the car and the overhang hold. Smoke drifts in from 2 s.
- **later:** This prompt went out with the plan's shorthand at its head unexpanded ("REAL + REAL+ (empty car, white vapour, no track/stands/city, no other cars) +"): the expansion step in `tools/jobs2.py` matched only the bare form "REAL + REAL+ +", and its check for leftover shorthand, which looks for whole words, does not match "REAL+" followed by a space. So Wan never received the REAL preamble for this job. The take held anyway, on the side its first frame shows.
- **first cut:** The same shot.
- **final film:** s049 0:53.92–0:55.29 (take 2.00–3.37).

Prompt:

```
REAL + REAL+ (empty car, white vapour, no track/stands/city, no other cars) + Bullet time: time is frozen. The car hangs upside down under the wide curved white-and-red overhang at the top of the wall, its wheels against it, the round stage light and the truss above; nothing in the scene moves, only the camera. 0-1 s: close under the car, the camera starts to glide sideways along it. 1-4 s: it slides slowly along the car's visible side from the rear wheel toward the front wheel at the same distance, looking up; the red strip and the overhang's curve slide past in parallax; the stage light flares as it crosses the lens. 4-5 s: it eases to a stop under the front wheel. The camera stays on this side of the car and never goes around its nose or tail. The overhang stays a wide curved wall, never a post. The car keeps its exact shape: no badge, no emblem, nobody inside.
```

#### g26-r2 and g26-r2-t2 · TRACK-EMPTY · rank 4

Wan 3.0 image-to-video · 4 s × 2 takes · seeds 212 and 213 · $1.60

- **for:** s142 (2:34.07), "Flying cars are", continuing the real slow motion that ends on A 80.594. The plan's reason: g26 has a man in the window, and the "passes over the camera" beat is dropped because g26 showed a sedan's underside there.
- **inputs:** first frame: A 80.60 (g26's start).
- **takes:** Take 1: ALT, 0.0–1.5 s; at 1.6 s it cuts to a generic car head-on. Take 2: USE, 0.0–1.9 s, the glass dark and the car empty; at 1.97 s it cuts to a generic front and an electricity pylon.
- **first cut:** Take 2 at s142 (2:34.07).
- **final film:** s142 2:34.07–2:35.90 (take 2, 0.00–1.83). "Flying" moves from Tesla's real slow motion into this take with no seam.

Both takes, the same prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car is empty and flown by remote: nobody is inside it and its glass stays dark. Its thrusters blow white cold-gas vapour, never flame or fire. No race track, no stands, no crowd, no city lights, no other cars than those in Image 1. The white car flies level in profile on two white thruster plumes, the light under it red, a light pole and power lines behind. The car is empty and flown by remote: nobody is inside it; its side glass stays black from the first frame to the last. It keeps flying forward slowly. 0-2 s: the camera tracks beside it at the same speed and height. 2-4 s: it swings about 40 degrees toward the car's nose; the headlights flare across the lens. Only the camera moves relative to the car; nothing else is added.
```

#### g27-r2 and g27-r2-t2 · WALK-OUT-LINEUP · rank 5

Wan 3.0 reference-to-video · 5 s × 2 takes · seeds 215 and 216 · $3.99 (includes 9.94 s of input video)

- **for:** s143 (2:35.90), REAL!: one unbroken 3.66 s hold of her walking out of the real smoke, her stop and look under REAL!.
- **inputs:** Video 1: B 10.90–15.40 played at 0.9× (4.97 s), the real Roadster entering the smoke at the left in the first second; Image 1 only: rh-02 id-full #3, cleaned (the lettered sleeve patch and the collar star inpainted). Image 2 was dropped because Wan cut to it in g02, g27 and g28.
- **takes:** Take 1: USE, 0.0–5.0 s, one continuous hold: she walks out of the smoke (1.2–3.0 s) and stops full length (3.4–5.0 s), the steel pole at the right. A generic white sports car sits behind her in the smoke from about 1.4 s. Take 2: ALT, 0.0–3.5 s; at 3.57 s it cuts to a closer framing with a gold car.
- **first cut:** Take 1 at s143 (2:35.90).
- **final film:** not used. Retired for the generic white supercar behind her. The final film's REAL! is round 1's g27 (see there).

Both takes, the same prompt:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. Image 1 is only a reference for her look; it is never shown as a shot. She is real and life-size, lit by the real lights of Video 1, walking on the real ground, and always seen at full length. Keep the real car, the set, the lights, the smoke and the camera exactly as in Video 1: one continuous shot, no cuts, the same framing from the first frame to the last. Native colour; no text, no logos, no badges, no licence plates, no other people, no other cars. Her lips stay closed. White smoke billows across the lot after the landing; the white semi truck and the parked cars stand behind it; a steel pole at the right. Keep every vehicle exactly as in Video 1: do not add, move or reshape any car. 0-0.8 s: as Video 1, smoke only. 0.8-3.2 s: she walks out of the billowing smoke from deep in the frame, left of the steel pole, straight toward the camera with steady, confident steps, smoke curling around her legs; she grows from small to full length. 3.2-3.6 s: she stops in the middle distance, full length, in the lower two-thirds of the frame. 3.6-5 s: she looks into the lens and holds, deadpan, lips closed. The camera never moves and never cuts; she is never shown closer than full length.
```

#### g28-r2 · WALK-OUT-RED · rank 6

Wan 3.0 reference-to-video · 4 s · seed 218 · $1.59 (includes 3.97 s of input video)

- **for:** s164 (2:54.20), restraint before "Tell 'em what you saw.": she walks out of the red smoke beside the landed real car.
- **inputs:** Video 1: A 101.30–105.27 (3.97 s), the replay of the landing: the car touches down in the smoke at frame 0, the smoke spreads red, and the car is visible again at 3.9 s; Image 1 only: the cleaned id-full #3.
- **takes:** USE: 0.0–2.3 s the real landing in red smoke (re-rendered by Wan) and 2.85–4.0 s her standing full length in front of the white car in the smoke. It cuts at 2.80 s, and she stands rather than walks.
- **first cut:** The same shot.
- **final film:** s164b 2:56.48–2:57.26 (take 2.85–3.63). Wan's licence plate on the car is painted blank. The board split s164 at its beat: the real landing first, then this take.

Prompt:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. Image 1 is only a reference for her look; it is never shown as a shot. She is real and life-size, lit by the real lights of Video 1, walking on the real ground, and always seen at full length. Keep the real car, the set, the lights, the smoke and the camera exactly as in Video 1: one continuous shot, no cuts, the same framing from the first frame to the last. Native colour; no text, no logos, no badges, no licence plates, no other people, no other cars. Her lips stay closed. After the landing, red-lit and white smoke rolls low across the ground; the white car sits inside the cloud; its thrusters blow white cold-gas vapour, never flame. 0-0.5 s: as Video 1. 0.5-2.8 s: she walks out of the red-lit smoke from beside the landed white car, toward the camera, full length, smoke trailing from her legs and her gloves. 2.8-4 s: she stops in front of the car, full length, and looks into the lens, deadpan, lips closed. The camera never moves closer and never cuts; she is never shown closer than full length; the car stays where it is, the same car as in Video 1.
```

#### g33 and g33-t2 · FREEZE-TOUCHDOWN · rank 7

Wan 3.0 image-to-video · 5 s × 2 takes · seeds 221 and 222 · $2.00

- **for:** s149 (2:42.41), where g14's window is a dark-grey car on a race track, and s060 (1:04.63): the 3.3 g touchdown frozen from a second angle, the drop's move.
- **inputs:** first frame: A 50.25, the car a metre above the asphalt at the touchdown, its own smoke bursting, stage lights behind.
- **takes:** Take 1: USE, 0.0–1.5 s: the touchdown frozen above its smoke while the camera turns toward the nose; from about 1.9 s the car sharpens into a Lamborghini-like supercar. Take 2: PART, 0.0–0.9 s; from about 1.2 s a Lamborghini-like supercar on a lit road.
- **first cut:** Take 1 at s060 (1:04.63) and s149 (2:42.41).
- **final film:** s060 1:04.63–1:05.09 (take 1, 0.30–1.21 at 2×); s149 2:42.41–2:42.87 (take 1, 1.00–1.45).

Both takes, the same prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car is empty and flown by remote: nobody is inside it and its glass stays dark. Its thrusters blow white cold-gas vapour, never flame or fire. No race track, no stands, no crowd, no city lights, no other cars than those in Image 1. Bullet time at the touchdown: the white car hangs a metre above the dark asphalt, nose to the left, its wheels in its own exploding white smoke, a row of white stage lights and a red light strip behind it. Time is frozen and the smoke hangs in mid-burst. 0-0.5 s: frozen, the camera low at the car's height. 0.5-3 s: the camera glides about 40 degrees around toward the car's nose through the frozen smoke, the stage lights sliding behind in parallax, and ends on the car's front three-quarter with the headlights to the lens. 3-3.5 s: time slams back and the car drops onto the asphalt. 3.5-5 s: the smoke explodes outward toward the lens. The car is always the same low, wide white two-door car with a long black glass canopy and a sharp wedge nose; it never changes model or colour, and the shot never cuts to another place.
```

#### g02-r2 · WALK-TO-CAR · rank 8

Wan 3.0 reference-to-video · 6 s · seed 224 · $2.40 (includes 6 s of input video)

- **for:** s040 (0:37.92), "in the driver's seat,"; s167 (3:00.58), the bookend; and s004 (0:09.56). g02 hard-cuts at 4.47 s to the grey studio wall; s040's window crosses the cut, and all of s167 was that studio portrait.
- **inputs:** Video 1: g02's clip again (A 34.50–40.50, 6 s); Image 1 only: the cleaned id-full #3.
- **takes:** USE (the pick), 0.0–6.0 s, one continuous take with no studio cut: she enters at the bottom left at 0.9 s, walks to the real car, stands at the driver's side from 4.3 s and turns slightly at the end.
- **first cut:** The same three shots.
- **final film:** s004 0:09.56–0:11.39 (take 1.00–2.83); s040 0:37.92–0:39.74 (take 3.10–4.93); s167 3:00.58–3:01.51 (take 5.00–5.93).

Prompt:

```
Video 1 is real night footage of a white electric sports car's stunt show. Edit Video 1: add one woman, the woman of Image 1: a Caucasian American woman in her late twenties with pale skin and a glossy black blunt bob with heavy straight bangs and one clay-orange streak, a thin headset microphone, in her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. Image 1 is only a reference for her look; it is never shown as a shot. She is real and life-size, lit by the real lights of Video 1, walking on the real ground, and always seen at full length. Keep the real car, the set, the lights, the smoke and the camera exactly as in Video 1: one continuous shot, no cuts, the same framing from the first frame to the last. Native colour; no text, no logos, no badges, no licence plates, no other people, no other cars. Her lips stay closed. The car is parked at the foot of the tall white wall; the camera slowly zooms in, as in Video 1. 0-1 s: as Video 1, no one in frame. 1-3 s: she walks into frame from the bottom left, her back to us, toward the car with steady, confident steps; the car's roof is at her ribs. 3-4.3 s: she trails one white glove along the rear deck as she passes to the driver's side at the left and stops there. 4.3-5.2 s: she looks up the wall, still, one glove resting on the roof. 5.2-6 s: she turns her head over her left shoulder toward the camera; we see her profile and the clay-orange streak, still from behind, at full length; the camera stays wide.
```

#### g05-r3 and g05-r3-t2 · G-FORCE, closed lips · rank 9

Wan 3.0 image-to-video · 5 s × 2 takes · seeds 227 and 228 · $2.00

- **for:** s010 (0:15.86), s016 (0:19.77), s037 (0:34.59), "gritting my teeth.", and s030 (0:28.11). g05-r2 shows her mouth open and moving from 0.9 to 3.5 s, as if she were singing the words.
- **inputs:** first frame: the frame of the g05-r2 take at 3.65 s, lips closed (not a Midjourney image).
- **takes:** Take 1: USE (the pick), 0.0–5.0 s: lips closed throughout; the red streaks build into a red warp tunnel by 4–5 s, with a closed-mouth smile. Take 2: ALT, 0.0–5.0 s, the same with gentler streaks.
- **first cut:** Take 1 at the same four shots.
- **final film:** s010 0:15.86–0:16.88 (take 1, 0.00–1.02); s016 0:19.77–0:20.24 (take 1, 1.50–1.96); s030 0:28.11–0:28.57 (take 1, 4.05–4.51); s037 0:34.59–0:35.63 (take 1, 2.00–3.04).

Both takes, the same prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior; the camera stays at the same distance. Her lips stay closed; she never talks. No text, no logos, no badges, no other people. Launch. 0-1 s: the g-force slams her back into the seat; her bob and bangs whip back; her lips stay pressed together. 1-3 s: jaw set, lips pressed into a thin line, eyes narrowed and fixed just past the lens, cheeks pulled by the force; the red light strips outside stretch into long lines racing past the glass. 3-5 s: the cockpit shakes hard; a fierce closed-mouth smirk. Camera: hard-mounted on the dash facing her, violent fine vibration, the same angle and framing the whole shot: no pan, no whip, no zoom. Her mouth stays shut from the first frame to the last.
```

#### g10-r2 and g10-r2-t2 · SEAT-HERO, one set · rank 10

Wan 3.0 image-to-video · 4 s × 2 takes · seeds 230 and 231 · $1.60

- **for:** s039 (0:36.09), the reveal, the one place the film says she is the pilot. g10 morphs into another set inside the board's window.
- **inputs:** first frame: rh-02 g10 #2 (as g10).
- **takes:** Take 1: USE (the pick), 0.0–4.0 s, one set: she looks off to the left, turns to the lens at about 0.8–1.5 s and holds, lips closed, red strips outside. Take 2: ALT, the same move, kept in case its turn landed closer to the impact at 0:36.09.
- **first cut:** Take 1 at s039 (0:36.09).
- **final film:** s039 0:36.09–0:37.92 (take 1, 0.60–2.43, ramped: 3× through the turn).

Both takes, the same prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior; the camera stays at the same distance. Her lips stay closed; she never talks. No text, no logos, no badges, no other people. She sits upright in the driver's seat, the white door frame around her, red light strips outside the side window. 0-0.8 s: still, eyes ahead past the lens. 0.8-1.2 s: in one sharp move she turns her head and looks straight into the lens. 1.2-4 s: she holds the stare, deadpan, lips closed; outside, the red strips slide slowly past the glass. Camera: locked off at this distance, a medium close-up from the passenger side for the whole shot; it does not push in and the framing never changes.
```

#### g25-r2 and g25-r2-t2 · MIC-PRESS · rank 11

Wan 3.0 image-to-video · 3 s × 2 takes · seeds 233 and 234 · $1.20

- **for:** s132 (2:23.30), "Thrusters.": the press of the mic lands just after the impact. In g25's plate the finger is twice its natural length.
- **inputs:** first frame: rh-02 g25 #2, with a red glyph at the sleeve's edge inpainted.
- **takes:** Take 1: USE (the pick), 0.0–3.0 s: a natural finger moves onto the mic boom and presses at about 1.3–2.1 s; her lips are slightly parted at 1.3 s. Take 2: ALT, 0.0–3.0 s: the finger at the boom and a steady stare, with no visible press.
- **first cut:** Take 1 at s132 (2:23.30).
- **final film:** s132 2:23.30–2:24.42 (take 1, 1.95–2.96 at 0.94×). The final check found her lips parted and closing in the shot's first three frames (take 1.80–1.92 s) and started the window at 1.95 s.

Both takes, the same prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior; the camera stays at the same distance. Her lips stay closed; she never talks. No text, no logos, no badges, no other people. In the cockpit, the index finger of her white glove resting at her cheek beside the thin headset microphone, eyes on the lens. 0-0.6 s: still. 0.6-1.2 s: she moves her fingertip onto the microphone boom, presses it once and gives one small, sharp nod, lips closed: she is calling a command, and we never see her speak. 1.2-3 s: she holds the press and the stare; the red light strips outside stay steady. Her glove has five fingers of natural length. Camera: locked, a very slight 2 percent push.
```

#### g19-r2 · LOOK-UP · rank 12

Wan 3.0 image-to-video · 5 s · seed 236 · $1.00

- **for:** s076 (1:24.56): she looks up before the kickflip, with nothing in the cockpit.
- **inputs:** first frame: rh-02 g19 #2.
- **takes:** USE (the pick), 0.0–5.0 s: her head back, a white light sweeping across the glass roof at 2.1–3.6 s, her gaze lowered at 4.3–5.0 s.
- **later:** TAKES.md recorded her lips as closed; verse 2's builder found them parted through the whole take.
- **first cut:** s076 (1:24.56).
- **final film:** not used. Out: s076 went to g15.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior. Her lips stay closed; she never talks. No text, no logos, no badges, no other people. Her head is tilted back against the seat; she looks up through the glass roof of the cockpit; red light strips outside. 0-1.5 s: still, eyes up, lips closed. 1.5-3.5 s: a bright white light sweeps across the glass roof above her from left to right; its glow slides over her face and her eyes follow it; the light stays outside the glass. 3.5-5 s: the light has passed; she slowly lowers her gaze toward the lens. Camera: a slow tilt from her face up toward the glass roof. Nothing enters the cockpit: no objects, no machines, no other hands.
```

#### g16-r2 · SMOKE-PUSH · rank 13

Wan 3.0 image-to-video · 3 s · seed 239 · $0.60

- **for:** s071 (1:15.42), the dip after drop 1: a push through the landing cloud, with no car. g16 shows a generic sedan from 0.3 s.
- **inputs:** first frame: A 51.60, the landing cloud lit white and pink-red, red strips on the ground.
- **takes:** USE, 0.0–2.3 s: into the real cloud and through it. At 2.43 s it cuts to an invented lit road with a gantry.
- **first cut:** The same shot.
- **final film:** s071 1:15.42–1:17.24 (take 0.00–0.95 at 0.52×, before Wan's invented lamps, gate and vehicle).

Prompt:

```
Image 1 is the first frame of real night footage of a stunt show. Keep everything in it exactly as it is: the smoke, the lights, the ground, the black night; native colour, no grade, no new objects, no vehicles, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. A huge cloud of white smoke after a landing, lit white and pink-red, thin red light strips on the dark ground at the right, black night. The smoke keeps billowing slowly; only the camera moves. 0-1 s: the camera flies fast and low straight at the cloud. 1-2 s: it plunges into the smoke; the whole frame turns soft white. 2-3 s: it bursts out of the far side into the black night, the red light strips running along the ground ahead. No vehicles and no people appear at any time.
```

#### g34 and g34-t2 · FPV-CHASE · rank 14

Wan 3.0 image-to-video · 5 s × 2 takes · seeds 242 and 243 · $2.00

- **for:** s011 (0:16.88), "sixty", and s102 (1:52.92), the first record of the build: a racing-drone chase behind the real car up the real wall. The launch was only filmed from far away.
- **inputs:** first frame: A 39.60, from behind: the car waiting on the line before its second run.
- **takes:** Take 1: ALT, 0.0–2.1 s; from about 2.5 s the wall flattens into a long straight ramp with posts. Take 2: USE (the pick), 0.0–3.0 s: the launch from the real frame and the chase up the face, the light bar at the rear consistent; from about 2 s the wall reads as a long ramp with lights, which passes at 2× in a fast cut.
- **first cut:** Take 2 at s011 (0:16.88) and s102 (1:52.92).
- **final film:** s011 0:16.88–0:17.46 (take 2, 1.00–2.17 at 2×); s102 1:52.92–1:53.83 (take 2, 0.50–2.23, ramped). Wan's glyphs on the rear plate are replaced by a blank plate in the plate's own tone.

Both takes, the same prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car is empty and flown by remote: nobody is inside it and its glass stays dark. Its thrusters blow white cold-gas vapour, never flame or fire. No race track, no stands, no crowd, no city lights, no other cars than those in Image 1. Rear view: the white car waits on the line at the foot of the tall curved white wall with thin red edge strips. 0-0.5 s: still, the camera hovering low behind the car like an FPV racing drone. 0.5-1.5 s: the car launches straight at the wall, its rear light bar blazing, and climbs onto the curve with its wheels on the concrete; the drone chases it, low and close behind. 1.5-4 s: the drone follows it up the curve as the car turns vertical, staying behind and a little below it, the concrete and the red edge strips streaming past both sides of the lens, the black night above. 4-5 s: the car pulls away up the vertical face toward the black sky. We always see the car's rear and roof. It is always the same low, wide white two-door car with a long black glass canopy; it never changes model or colour. The wall stays a wall (never a road, a track or a bridge), and the shot never cuts.
```

#### g35 and g35-t2 · VERTIGO-LINEUP · rank 15

Wan 3.0 image-to-video · 5 s × 2 takes · seeds 245 and 246 · $2.00

- **for:** s127 (2:18.83), cutting on the hit to the real 3.6 g launch from the same camera; also s077 (1:25.48) and s081 (1:27.31): a dolly-zoom on the car before the kickflip, the lineup looming.
- **inputs:** first frame: A 62.25, the car on the centre line from behind, the lineup ahead under the stadium light.
- **takes:** Take 1: USE, 0.0–2.2 s: the dolly-zoom behind the car, but the lineup recedes instead of looming, and the Semi is gone by about 2.6 s. Take 2: ALT, 0.0–1.2 s; the lineup becomes rows of generic parked cars from about 1.4 s.
- **first cut:** Take 1 at s077 (1:25.48) and s127 (2:18.83).
- **final film:** s077 1:25.39–1:25.82 (take 1, 0.80–1.67, restarting on the chop); s127 2:18.83–2:19.44 (take 1, 0.98–2.19 at 2×, a zoom stutter on the fill).

Both takes, the same prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car is empty and flown by remote: nobody is inside it and its glass stays dark. Its thrusters blow white cold-gas vapour, never flame or fire. No race track, no stands, no crowd, no city lights, no other cars than those in Image 1. The white car sits on the white centre line seen from behind, its red tail-light bar glowing, the lineup of vehicles ahead of it under a tall stadium light. Everything waits; no vehicle moves. 0-4 s: one slow dolly-zoom (vertigo): the camera dollies back low along the centre line while zooming in, so the car keeps its size while the semi truck and the lineup loom taller and closer behind it, the stadium light swells and the centre line stretches. 4-5 s: the car squats on its suspension, ready. Nothing is added: no stands, no crowd, no new vehicles. The car never changes model or colour.
```

#### g36 · WALL-SWING · rank 16 · first and last frame

Seedance 2.5 image-to-video · 4 s · $4.55

- **for:** s023 (0:23.02), "up the wall at": the hero line was cut between two real cameras; this joins them in one move with a real frame at each end.
- **inputs:** first frame: A 7.54, the car on the vertical face of the wall from the side, the truss and the light beams. Last frame: A 8.50, Tesla's top-down on the wall face (g07's start).
- **takes:** USE, 0.0–4.0 s: one continuous move from the real side view onto the wall face, ending on the real top-down; the real car throughout. The lead: "g36 is perfect".
- **first cut:** The same shot.
- **final film:** s023 0:23.02–0:24.20 (take 0.00–3.20, ramped). It chains three shots on real frames: s022 ends on A 7.54, this take starts there and ends on A 8.50, and s024's dive starts on A 8.50.

Prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice. 【Generation Goal】 One continuous camera move at night: the real white car drives straight up the vertical face of a tall curved white concrete wall with thin red edge strips, and the camera flies toward the wall and swings onto its face until it looks straight down at the car's roof. 【Reference Asset Roles】 Use @Image1 as the first frame. It defines the wall, the car on its vertical face with its white roof and black glass canopy toward us, the steel truss, the light beams at the lower left, the black night and where the camera starts. Use @Image2 as the last frame. It defines the end: the camera square to the wall face, the car's white roof and long black canopy filling the frame nose-up, the centre stripe and the red edge strips running down. 【Event Timeline】 0-1s: the camera starts to fly toward the wall; the car creeps up the face. 1-3s: it closes in and swings round onto the face; the curve of the wall and the truss slide away and the red edge strips turn parallel. 3-4s: it settles square to the face, exactly at the framing of @Image2. 【Camera】 One continuous move from @Image1 to @Image2 with true parallax; no cut, no dissolve, no fade between the two frames. 【Core Requirements】 1. Exactly the real car of both frames; it never changes model or colour; nobody visible inside. 2. The wall stays the same white concrete wall with red edge strips; no road, track or lamp posts. 3. Native colour; black night. 4. No people; no subtitles, captions, titles, signs, logos, watermarks or on-screen text. 【Final Acceptance Criteria】 One continuous move that starts on @Image1 and ends on @Image2; same real car; no cut or dissolve; no people, no text. 【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

#### g37 · CANOPY-DIVE · rank 17

Wan 3.0 reference-to-video · 4 s · seed 251 · $0.80

- **for:** s024 (0:24.20), "ninety,": from the real car at 89.7° through its real glass to her lying back at ninety degrees, the one shot that shows her flying it.
- **inputs:** Image 1: A 8.50, the top-down (g07's start), as frame 0. Image 2: rh-02 g10 #1, a closed-lip plate with a clean collar, as the only picture of who is inside. The plan asked for a 720p probe first; it went out at 1080p directly.
- **takes:** USE (the hero), 0.0–4.0 s: from the real top-down the camera dives at the canopy (1.1–2.3 s), passes through, and finds her lying back in the seat looking up (2.9–4.0 s), adult and on-model.
- **later:** Its frame at 3.5 s, her lying back and looking up, became the last frame of the Seedance re-shoot g37sd.
- **first cut:** s024 (0:24.20). anabology: "at 25 seconds i think i dont like the temporary half-shown cut of claudia, either we reshoot to make the shot go all the way in and actually show the interior of the car from the perspective, or leave it black and do motion design on the screen." The lead chose the re-shoot.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage: seen from straight above, the white car drives up the vertical face of the white wall, its large black glass canopy in the middle, the centre stripe under it, thin red edge strips at the sides. Keep the real car exactly as in Image 1 (its exact shape and colour), the wall and the black night; native colour; no text, no logos. Image 2 only shows who sits inside the car: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes. Image 2 is never shown as a shot. One continuous shot, no cuts: one real physical camera move with true parallax. 0-0.8 s: as Image 1; the car creeps up the stripe. 0.8-2.2 s: the camera dives straight down at the black glass canopy, the white roof filling the frame, the tinted glass rushing at the lens. 2.2-2.6 s: it passes through the glass. 2.6-4 s: inside, close above her: she lies back in the driver's seat, pressed into it by the climb, both white gloves on the yoke, her black bob pressed back against the headrest, eyes wide open looking straight up into the lens; thin red light slides across her face. Her lips stay closed. No other people.
```

#### g38 · LIP-RUSH · rank 18

Wan 3.0 image-to-video · 5 s · seed 254 · $1.00

- **for:** s140 (2:31.09), "off the top": a rush up the real wall to the car frozen at the lip; in the real wide the moment is a speck.
- **inputs:** first frame: A 48.05, the car at the top lip of the wall, its roof and canopy toward the camera, before the flight off the ramp.
- **takes:** USE, 0.0–1.3 s: the rush up the wall to the car at the lip with smoke. At 2.30 s it cuts to an invented lit bridge and an open-top car.
- **first cut:** s140 (2:31.09). anabology: "2:31 hallucinates a top part of the ramp and a top part of the car after panning over the flipped over car." Re-shot as g38sd.
- **final film:** not used.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car is empty and flown by remote: nobody is inside it and its glass stays dark. Its thrusters blow white cold-gas vapour, never flame or fire. No race track, no stands, no crowd, no city lights, no other cars than those in Image 1. Bullet time: the white car is frozen at the top lip of the wall with its nose just over the edge, its roof and long black glass canopy toward us, a puff of white thruster gas frozen beside it. Below it the white face sweeps down into the black. 0-3 s: the camera rushes in toward the car, rising along the face of the wall close to the concrete, the centre stripe and the red edge strips streaming beneath the lens, the car growing in the frame. 3-4 s: it stops just behind the car's glass canopy at the lip, the black drop beyond. 4-5 s: time resumes and the car tips off the lip on a white thruster puff. Only the camera moves until 4 s. The car never changes model or colour, and the shot never cuts to another place.
```

#### g13-sd · CRANE-HOVER, Seedance · rank 19

Seedance 2.5 reference-to-video · 4 s · $4.55

- **for:** s119 (2:07.68), "never", and s052 (0:57.12), "touch": the crane over the hover to its roof among the plumes. Wan's g13 became a sedan at 2.7 s, but a free remap of it existed, so this ranked below the true repairs.
- **inputs:** @Image1, the first frame: C 19.00 (g13's start). @Image2: A 78.30, roof and canopy on black. @Image3: A 77.60, the upright side. @Image4: A 50.25, the front three-quarter.
- **takes:** USE, 0.0–3.6 s: the crane from the head-on hover round to the real side profile above the smoke (1.7–2.9 s) and over the roof (3.5 s). At 4.0 s the frame is its roof reference on black. It took both hover slots and retired Wan's g13.
- **first cut:** The same two shots.
- **final film:** s052 0:57.12–0:58.04 (take 0.60–1.55, a speed ramp 2× to 0.7×); s119 2:07.68–2:08.80 (take 1.60–2.73).

Prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice. 【Generation Goal】 At night the real white electric sports car hovers a metre above the asphalt on white thruster plumes in a churning smoke cloud beside a tall white wall, and the camera cranes up and over it until it looks straight down on its roof. 【Reference Asset Roles】 Use @Image1 as the first frame. It defines the hovering car with its headlights toward us, the plumes, the smoke cloud, the tall white wall with red edge strips on the right, the black night and where the camera starts. @Image2 (its white roof with the long black glass canopy), @Image3 (its side profile) and @Image4 (its front three-quarter) show the SAME car; use them only for the car's exact shape and details when the crane reveals those sides. They are never shown as shots: never cut to them, never take their framing, backgrounds or lighting. 【Event Timeline】 0-1s: the car hovers, the plumes roar and the smoke churns; the camera starts to rise. 1-2.5s: the camera cranes up and over the hovering car, tilting down, the wall's top edge sliding past. 2.5-4s: it looks straight down at the white roof and the long black canopy, the white plumes fanning out into the smoke; the car keeps hovering and never touches the ground. 【Camera】 One continuous crane with true parallax; no cuts, no dissolves. 【Core Requirements】 1. Exactly the real car in every frame; never a sedan, never another colour; nobody inside. 2. Wall, smoke and red strips stay as in @Image1; no new vehicles, people, stands, roads or tracks. 3. White cold-gas plumes, never flame; native colour. 4. No subtitles, captions, titles, signs, logos, watermarks or on-screen text. 【Final Acceptance Criteria】 One continuous crane from @Image1 to straight above the same real car; @Image2-@Image4 never appear as shots; no people, no text. 【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

#### g39 · HAIR-FALL · rank 20

Wan 3.0 image-to-video · 4 s · seed 260 · $0.80

- **for:** s034 (0:31.51), "underneath,", and s028 (0:27.18), the third "done"; optionally s110 (1:58.27), s159 (2:49.52), s174 (3:04.26): her hair falls as the car turns over, felt inside the car.
- **inputs:** first frame: rh-02 g10 #1, turned 180° and cropped so her face fills the frame, a closed-lip plate (it replaced the plan's g24 repair, whose plate showed teeth).
- **takes:** USE, 0.0–2.6 s: upside down, her bob falls away from her face strand by strand. From about 2.8 s a daytime blue sky appears in the window.
- **later:** The chapter reviewers of the hold and of verse 2 found her teeth in every window.
- **first cut:** s028 (0:27.18) and s034 (0:31.51).
- **final film:** not used. Out: s034 went to g08, and s028 to the re-roll g39r2.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior; the camera stays at the same distance. Her lips stay closed; she never talks. No text, no logos, no badges, no other people. The car has just turned upside down at the top of the wall: she and the whole cockpit read upside down for the entire shot, her head toward the bottom of the frame. 0-0.5 s: still; her black bob still lies along her cheeks as if she were upright. 0.5-2.0 s: gravity takes it: her bob and the clay-orange streak fall away from her face, down toward the roof at the bottom of the frame, strand by strand, her bangs dropping off her forehead; the thin microphone boom stays at her cheek. 2.0-4 s: her hair hangs straight down and sways once; she looks into the lens, calm, lips closed; outside the window the red light strip slides slowly upward. Camera: locked to the cockpit, no roll. The image never flips upright.
```

#### g40 · WEIGHTLESS-FLIP · rank 21

Wan 3.0 image-to-video · 4 s · seed 263 · $0.80

- **for:** s091 (1:36.70), "now I'm", s115 (2:03.19), "around", and s120 (2:08.80): weightless at the kickflip's apex. It gives chorus 2 its own frames and replaces s115's g12 window, which has the blue screen.
- **inputs:** first frame: rh-02 g12 #4 (screened adult, lips closed, the bob flying up, one glove on the stick, a plain suit).
- **takes:** USE, 0.0–2.0 s, and 2.0–4.0 s with care: her hair floats; from about 1.7 s the cockpit brightens into a white interior with stadium lights in the windows (the world turning); she looks up at 3.4–4 s.
- **first cut:** s091 (1:36.70) and s115 (2:03.19).
- **final film:** s091 1:36.70–1:37.83 (take 0.30–1.43); s115 2:03.19–2:04.32 (take 1.40–2.53, the spin carried on through her).

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior; the camera stays at the same distance. Her lips stay closed; she never talks. No text, no logos, no badges, no other people. Weightless at the top of a kickflip: the car is rolling over in the air. 0-4 s: she floats against her harness, her black bob drifting up and around her face in slow motion, the clay-orange streak and the star clip turning in the light; her gloved hand stays on the stick. Outside the side window, the red light strips and one white stadium light sweep in one slow, smooth circle around the glass as the car rolls (the world turns, not her). 1.5-3 s: she looks into the lens, calm, the faintest lift at one corner of her mouth, lips closed. 3-4 s: she glances up through the glass. Camera: locked to the cockpit, floating with her; it never rolls.
```

#### g41 · IMPACT-SLAM · rank 22

Wan 3.0 image-to-video · 4 s · seed 266 · $0.80

- **for:** s061 (1:05.09), right after the touchdown, and s136 (2:27.75), after the jump's landing: she is slammed into the seat. The smoke billows outside so that it cannot read as a flash inside the scene.
- **inputs:** first frame: the g05-r2 take's frame at 3.65 s, lips closed (as g05-r3).
- **takes:** USE with care: 0.0–1.0 s she floats, 1.0–1.5 s the impact, 2.3–4.0 s the aftermath. At the impact (1.1 s) Wan bursts orange sparks outside, where the thrusters are cold gas, and white smoke whites out the cockpit at 1.4–2.0 s; her hair falls over her face and the glass crazes. The lead left the sparks to the art director, and "never hold the whiteout".
- **first cut:** The same two shots.
- **final film:** s061 1:05.09–1:05.78 (take 0.33–1.03); s136 2:27.75–2:28.19 (take 0.60–1.04). The jolt itself is made in code on the kick; the sparks are never shown, and nothing past 1.1 s, where her mouth opens.

Prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior; the camera stays at the same distance. Her lips stay closed; she never talks. No text, no logos, no badges, no other people. 0-0.8 s: the car is falling; she floats up against her harness, her black bob lifted off her shoulders, eyes on the lens. 0.8 s: impact: the car lands hard; she is slammed down into the seat, her bob slaps down over her forehead, the whole cockpit shudders once, hard; white smoke billows up outside the windows. 1.2-4 s: the smoke swirls past the glass, red light glowing through it; she breathes out slowly through her nose, lips closed, and lifts her eyes back to the lens, deadpan. Camera: hard-mounted on the dash, one violent jolt at 0.8 s, then still.
```

#### g42 · HOVER-ARC · rank 23

Wan 3.0 image-to-video · 5 s · seed 269 · $1.00

- **for:** s050 (0:55.29), "never", and s121 (2:09.82), "touch the": a second 3D view of the one real hover, the arc capped at 40 degrees toward the nose it can see.
- **inputs:** first frame: C 18.40, the car hovering in its smoke cloud beside the wall, headlights toward the camera.
- **takes:** USE, 0.0–3.0 s (3.0–5.0 s to be checked at full size): the arc round the hover to the headlights. The head-on end shows a full-width light bar.
- **first cut:** The same two shots.
- **final film:** s050 0:55.29–0:56.21 (take 0.00–1.83 at 2×); s121 2:09.82–2:11.03 (take 1.00–1.75 at 0.62×). Chorus 2's window stops before an invented hood badge that shows from about 1.9 s.

Prompt:

```
Image 1 is the first frame of real night footage of a white electric sports car's stunt show. Keep everything in it exactly as it is: the real white car and its exact shape, the set, the lights, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth, like a cinema FPV drone. The car is empty and flown by remote: nobody is inside it and its glass stays dark. Its thrusters blow white cold-gas vapour, never flame or fire. No race track, no stands, no crowd, no city lights, no other cars than those in Image 1. The white car hovers a metre above the asphalt on white thruster plumes in a churning white smoke cloud beside the tall white wall, headlights toward us. Time runs at a quarter speed: the smoke rolls slowly and the car hangs in the air. 0-3.5 s: the camera arcs about 40 degrees around toward the car's nose at the car's height until it faces the headlights head-on, the white wall sliding behind it in parallax. 3.5-5 s: a slow push toward the headlights through the drifting smoke. The car keeps hovering and never touches the ground; it never changes model or colour, and the shot never cuts.
```

#### g43 · ROOF-RISE · rank 24

Wan 3.0 image-to-video · 5 s · seed 272 · $1.00

- **for:** s085 (1:30.57), "ten thousand PSI,": the witnesses' view from under the flying car becomes a move through space toward it.
- **inputs:** first frame: B 1.30, full frame: the lineup camera looking up through a parked car's glass roof as the Roadster flies over.
- **takes:** USE, 0.0–5.0 s: the camera rises from the parked car toward the car frozen overhead, its canopy down, a plume under it; stadium lights appear late.
- **first cut:** The same shot.
- **final film:** s085 1:30.57–1:32.17 (take 0.00–0.95, ramped 1.2× to 0.25× so the car hangs on "PSI"). The real B 1.00–1.30 plays first and the take starts on B 1.30, so the cut is seamless.

Prompt:

```
Image 1 is the first frame of real night footage filmed by a camera on the roof of a parked car, looking up at a white electric sports car flying overhead. Keep everything in it exactly as it is: the real white car and its exact shape, the parked car's glass roof and the reflection in it, the smoke, the black night; native colour, no grade, no new objects, no people, no text, no logos. One continuous shot, no cuts; a real physical camera move with true parallax and depth. Bullet time: the white car hangs frozen in the black sky directly overhead, its long black glass canopy facing down at us, a white thruster plume frozen beneath it; nobody is inside it. 0-3 s: the camera rises slowly straight up off the parked car toward the frozen car, the glass roof and its reflection sinking out of the bottom of the frame. 3-5 s: it stops just beneath the car, looking straight up at its white body and black canopy against the black sky. Only the camera moves. The car never changes model or colour.
```

#### g44 · GLASS-PUSH · rank 25

Wan 3.0 reference-to-video · 4 s · seed 275 · $0.80

- **for:** s044 (0:46.60), "upside down", and s116 (2:04.32): a real 3D push from the real underside to her behind the glass, in place of g11's dissolve. The plan ranked it last, since g11 was usable.
- **inputs:** Image 1: A 18.20 (g09's start), as frame 0. Image 2: rh-02 g10 #1 turned 180°, as the only picture of who is inside. Like g37, it went out at 1080p without the planned 720p probe.
- **takes:** USE: 0.0–1.7 s the push in under the real car, 2.3–4.0 s her upside down behind the glass, and between them, 1.77–2.27 s, a Wan transition that can serve as the move into the car.
- **first cut:** The same two shots.
- **final film:** s044 0:46.60–0:47.98 (take 0.00–1.70 ramped 1.25× to 2.75×, then 2.47–2.75 at 0.545×, blended); s116 2:04.32–2:05.41 (take 2.42–2.633 at 0.2×). In chorus 2 the framing is panned so that an orange placard Wan added stays out.

Prompt:

```
Image 1 is the first frame of real night footage: the white car hangs upside down under the curved white-and-red overhang, its wheels against it, its side window glass toward us, a round stage light above. Keep the real car exactly as in Image 1 (its exact shape and colour), the overhang, the light and the night; native colour; no text, no logos. Image 2 only shows who is inside the car: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; she hangs upside down in her harness. Image 2 is never shown as a shot. One continuous shot, no cuts. Bullet time: nothing outside moves, only the camera. 0-1 s: as Image 1. 1-2.5 s: the camera glides in toward the side window glass, the overhang's red strip sweeping past above in parallax. 2.5-4 s: close on the glass: inside, she hangs upside down in her harness, her black bob hanging down toward the glass; she turns her eyes to the lens, lips closed. The car's white body and window frame stay around the edges of the frame; the camera does not pass through the glass. The image never flips upright.
```

### Round 3 · the re-shoots on the notes

Four Seedance jobs, two takes each, for the four generated shots in anabology's notes on the first cut; $36.39 at list. Note numbers refer to the notes in order (`wf/notes-v0`). All eight takes were judged, and the picks reached the chapters through the chapter fixers and the whole-film pass.

#### g32sd2 and g32sd2-t2 · FREEZE-LINEUP · notes 5 and 7

Seedance 2.5 reference-to-video · 4 s × 2 takes · $9.10

- **for:** s130 (2:20.41) and s156 (2:46.63): "2:21 loses the front wheels and 2:22 flips the car glitching"; "2:47 looks like the same shot - lost front wheels".
- **inputs:** as g32: @Image1 A 64.25 (the first frame), @Image2 A 80.00 (the chassis, close), @Image3 A 79.30 (its side upside down), @Image4 A 78.30 (the roof). This time each reference's role is written on its own line, and the car's state comes first in the 【Event Script】.
- **takes:** Take 1: ALT, 0.0–1.75 s: frozen upside down over the Semi, four wheels at the corners, a small orbit, no flip; at 1.83 s it cuts to its chassis reference. Take 2: USE (the pick), 0.0–1.9 s: a bigger, smooth orbit (the real truss tower swings in at the left), the car upside down with all four wheels visible at 1.3–1.9 s; after about 2.0 s it drifts to a pole-and-sky framing.
- **first cut:** not used.
- **final film:** s130 2:20.41–2:22.19 (take 2, 0.80–1.875, ramped 0.7× to 0.5× and blended); s156 2:46.63–2:47.30 (take 2, 1.215–1.889). The whole-film critic found the take's first 0.6 s reading end-on at small size, the front tyres folded into the corners, on the very shot anabology had flagged for wheels. The fix starts s130 at 0.80 s, where both front tyres read, and checked every frame at full size.

Both takes, the same prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】
Bullet time at night over a lineup of parked vehicles: the real white electric sports car hangs frozen upside down in mid-kickflip high above a white electric semi truck, and the camera makes one short, smooth orbit around it while time stands completely still.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the car upside down in the air with its dark chassis facing the camera, its four black wheels pointing up and out at the four corners, four white cold-gas jets frozen in an X from its four corners, the white semi truck and the two dark sedans on the platform edged with red light strips, the curved steel-truss ramp on the left, the stadium light on the right, the haze, the black sky and where the camera starts.
@Image2 is the same car's chassis seen close: use it only for the underside, the four wheel positions and the thruster positions.
@Image3 is the same car upside down seen from its side with all four wheels pointing at the sky: use it only for how the car looks from the side while upside down.
@Image4 is the same car's white roof and long black glass canopy: use it only for the roof shape.
@Image2, @Image3 and @Image4 are never shown as shots of this video, and their backgrounds, power lines and framing are never used.

【Event Script】
The car's state for the whole video: upside down, rotated 180 degrees about its long axis, frozen in mid-air exactly where @Image1 shows it, high above the semi truck. It does not roll, flip, turn over, right itself or move at all: time is stopped. Its four wheels stay attached at its four corners and point up and outward; the four jets stay frozen like glass columns in the same X.
0-1s: everything is frozen; the camera starts to orbit slowly to the right, keeping the same distance.
1-3s: the camera travels about 60 degrees around the frozen car, slightly downward; the semi truck, the sedans and the red light strips slide underneath in deep parallax; the car turns its upside-down side toward the camera, all four wheels visible.
3-4s: the camera eases to a stop; still frozen.

【Camera】
One continuous short orbit at constant distance, smooth like a motion-control rig, starting exactly at the framing of @Image1; no cuts, no dissolves, no jumps.

【Core Requirements】
1. The car is exactly the real car of the reference images in every frame: a low, wide white two-door electric sports car with a long black glass canopy, a sharp wedge nose, black wheels and a thin red light bar across its tail; one car only, never a sedan, never another colour, nobody inside it (its glass stays dark). It always has exactly four wheels, one at each corner, and they stay attached and visible whenever that side of the car faces the camera. Its thrusters blow white and pale blue cold-gas vapour, never flame or fire.
2. The car never rotates relative to the scene: it stays upside down from the first frame to the last.
3. The semi truck, the sedans, the truss ramp and the red strips stay as in @Image1; no new vehicles, stands, crowds or buildings.
4. Native colour of the night footage; no people.
5. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】
One continuous frozen orbit from @Image1; the same real car upside down in every frame with all four wheels; it never flips or rights itself; no cuts; no text.

【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

#### g14sd and g14sd-t2 · TRUSS-EXIT · note 4

Seedance 2.5 reference-to-video · 4 s × 2 takes · $9.10

- **for:** s056 (1:01.21) at 2×: "at 1:01 the car glitches and rights itself".
- **inputs:** @Image1, the first frame: C 26.25 (g14's start): the drone's view down onto the end of the truss, the car just past it, upside down, nose to the lower left, jets from its right end. @Image2: A 79.30, its side upside down. @Image3: A 78.30, its roof. @Image4: A 77.60, its side profile.
- **takes:** Take 1: USE (the pick), 0.0–1.6 s: upside down leaving the truss on its jets, the drone arcing, no righting; from about 2.5 s the car turns to show its roof. Take 2: ALT, 0.0–1.2 s; at about 1.4 s the car rolls upright, the glitch the note was about.
- **first cut:** not used.
- **final film:** s056 1:01.21–1:01.66 (take 1, 0.00–0.91 at 2×). The car is upside down, turned by its jets, in every frame of the shot.

Both takes, the same prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】
A night drone shot: the real white electric sports car has just left the end of a curved steel-truss ramp upside down and turns in the air on its cold-gas thrusters, in slow motion, while the drone camera arcs around it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the drone's view down onto the end of the curved steel-truss ramp with its red light strips, the car just past the end of the ramp, upside down with its wheels toward the sky and its nose pointing down to the lower left, white cold-gas jets shooting from its right end, the bright light and the hazy ground below, and where the camera starts.
@Image2 is the same car upside down from its side with all four wheels pointing at the sky; @Image3 is its white roof and long black glass canopy; @Image4 is its side profile. Use them only for the car's exact shape when the camera sees those sides. @Image2, @Image3 and @Image4 are never shown as shots of this video.

【Event Script】
The car's motion, in slow motion, the whole video: it stays upside down and keeps travelling away from the end of the ramp toward the lower left. Blue-white cold-gas jets fire continuously from the thrusters at its right end, and they slowly swing its tail around so the car turns smoothly in ONE direction about its vertical axis, a little at a time. It never snaps, jumps, flips back or rights itself: from the first frame to the last it is upside down, wheels toward the sky.
0-1s: the car drifts off the end of the ramp, upside down, jets firing from its right end; the drone begins to arc to the left around it.
1-3s: the drone arcs about 45 degrees around the car, the truss and its red strips sliding behind in parallax; the jets keep turning the upside-down car slowly.
3-4s: the car, still upside down, drops gently below the ramp's end; the jets keep firing.

【Camera】
One continuous drone arc at the car's height, smooth, true parallax, starting exactly at the framing of @Image1; no cuts.

【Core Requirements】
1. The car is exactly the real car of the reference images in every frame: a low, wide white two-door electric sports car with a long black glass canopy, a sharp wedge nose, black wheels and a thin red light bar across its tail; one car only, never a sedan, never another colour, nobody inside it (its glass stays dark). It always has exactly four wheels, one at each corner, and they stay attached and visible whenever that side of the car faces the camera. Its thrusters blow white and pale blue cold-gas vapour, never flame or fire.
2. The car is upside down in every frame and turns only slowly and smoothly in one direction; it never rights itself.
3. The truss ramp, its red strips, the light and the hazy ground stay as in @Image1; no new objects, people, stands or buildings.
4. Native colour.
5. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】
One continuous slow-motion drone arc; the same real car, upside down throughout, turned smoothly by the jets at its right end; no righting itself; no cuts; no text.

【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

#### g38sd and g38sd-t2 · LIP · note 6

Seedance 2.5 reference-to-video · 4 s × 2 takes · $9.10

- **for:** s140 (2:31.09): "2:31 hallucinates a top part of the ramp and a top part of the car after panning over the flipped over car".
- **inputs:** @Image1, the first frame: A 48.05 (g38's start). @Image2: A 78.30, the roof and canopy. @Image3: A 77.60, the side profile. @Image4: A 79.30, the car upside down, wheels to the sky.
- **takes:** Take 1: USE, 0.0–3.4 s: the rush up the ramp face, the car at the top in profile (1.2 s), a puff of vapour (2.3 s), the backward flip over the edge (2.6–3.2 s); the ramp ends at the edge and nothing is invented above it; at 3.6–4 s the frame is the reference's framing, the car upside down in the sky with a pole. Take 2: USE (the pick), 0.0–4.0 s: the car in profile at the top (0.8–2.0 s), the puff (2.0 s), the pitch backward over its roof (2.3–2.9 s), and the car hanging upside down above the edge (3.2–4.0 s); the ramp ends cleanly; a pole appears in the sky from 2.9 s.
- **first cut:** not used.
- **final film:** s140 2:31.09–2:32.43 (take 2, 0.15–3.20, ramped: the car in profile on the lip on the kick at 2:31.55, the pitch-over snapping into the cut). Left in, both within the usable window: from 2:32.08 to 2:32.25 Seedance turns the car's roof toward the camera, which reads like a roll, and a utility pole stands in the sky from 2:32.29.

Both takes, the same prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】
At night the camera rushes up the face of a tall white concrete ramp to the real white electric sports car at its very top, just as the car leaves the end of the ramp and flips backward over into the black sky.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the steep white concrete ramp with its centre stripe and thin red edge strips, the steel truss under it, the car at the very top with its white roof and long black canopy facing the camera and its nose at the edge, the black sky above and around the ramp's end, and where the camera starts.
@Image2 is the same car's roof and canopy, @Image3 its side profile, @Image4 the same car upside down with its wheels toward the sky: use them only for the car's shape as it flips. They are never shown as shots of this video.

【Event Script】
The ramp ENDS at the top edge shown in @Image1: there is nothing above or beyond that edge but black night sky; no further ramp, no platform, no second car.
0-2s: the camera rushes up along the ramp face, close to the concrete, the centre stripe and the red edge strips streaming beneath the lens; the car at the top grows in the frame, its wheels on the concrete.
2-3s: the car's nose passes the top edge; a puff of white cold-gas vapour bursts from its thrusters and the car lifts off the end of the ramp, pitching backward over its own roof into the sky.
3-4s: the camera stops just below the top edge, looking up; the car, now upside down with its four wheels toward the sky, arcs away into the black sky trailing white vapour; the empty ramp edge stays in the bottom of the frame.

【Camera】
One continuous rush up the ramp face, then a stop and a tilt up; no cuts, no dissolves.

【Core Requirements】
1. The car is exactly the real car of the reference images in every frame: a low, wide white two-door electric sports car with a long black glass canopy, a sharp wedge nose, black wheels and a thin red light bar across its tail; one car only, never a sedan, never another colour, nobody inside it (its glass stays dark). It always has exactly four wheels, one at each corner, and they stay attached and visible whenever that side of the car faces the camera. Its thrusters blow white and pale blue cold-gas vapour, never flame or fire.
2. The ramp keeps its shape and ends at the edge in @Image1; nothing is added above it.
3. Native colour, black night; no people, no new objects.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】
One continuous rush up the real ramp to the real car, which leaves the top edge and flips backward into the empty black sky; no extra ramp, no extra car; no cuts; no text.

【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

#### g37sd and g37sd-t2 · CANOPY-DIVE · note 3 · first and last frame

Seedance 2.5 image-to-video · 4 s × 2 takes · $9.10

- **for:** s024 (0:24.20): "either we reshoot to make the shot go all the way in and actually show the interior of the car from the perspective, or leave it black".
- **inputs:** first frame: A 8.50, Tesla's top-down (g07's start). Last frame: the g37 take's frame at 3.5 s, her lying back in the seat looking up into the lens. So the last frame traces back through a Wan take to rh-02 g10 #1.
- **takes:** Take 1: ALT, 0.0–1.8 and 3.0–4.0 s: a slower dive; at 2.2–2.7 s a murky red double exposure, like a dissolve. Take 2: USE (the pick), 0.0–4.0 s: one continuous dive from the real top-down, through the canopy at 1.0 s, into the red-lit cockpit with her hands on the stick (1.2–1.8 s), settling on her face looking up (2.4–4.0 s), lips closed.
- **first cut:** not used.
- **final film:** s024 0:24.20–0:25.11 (take 2, 0.00–2.95, ramped: the dive fast, through the canopy at 0:24.46, her face from 0:24.63 at about 1×). One frame, at 0:24.54, still passes through Seedance's dim red dissolve with a faint ghost of a face; the final check judged that at 24 fps it reads as motion through the dark.

Both takes, the same prompt:

```
【Audio Policy】 Silent video: no music, no sound effects, no voice.

【Generation Goal】
One continuous camera dive at night: from straight above the real white sports car driving up the vertical face of a white wall, the camera plunges down through the car's black glass canopy into the cockpit and arrives above the pilot, a woman lying back in her seat looking up into the lens.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the view from straight above: the car on the vertical white wall face, nose up, its white roof and long black glass canopy in the middle, the centre stripe under it, thin red edge strips at the sides, black night around.
Use @Image2 as the last frame.
This last frame defines the inside of the cockpit seen from above: the pilot lying back in a white racing seat, a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek, in a fitted white racing suit with thin clay-orange piping and white racing gloves, one gloved hand on the control stick, a red light strip across the glass behind her, her eyes up at the lens, her lips closed.

【Event Script】
0-1s: from @Image1 the camera starts to descend straight toward the black glass canopy; the car keeps creeping up the stripe.
1-2s: the canopy fills the frame; dim red light and the shapes of the cockpit appear through the tinted glass.
2-3s: the camera passes through the glass into the cockpit: the white seat, the control stick, her gloved hand and her white suit come into view from above; the red light strip slides across.
3-4s: the camera settles above her face and arrives exactly at @Image2: she lies back in the seat, pressed into it by the climb, looking up into the lens, calm, lips closed.

【Camera】
One continuous dive from @Image1 to @Image2 with true parallax: straight down, through the glass, into the cockpit; no cut, no dissolve, no fade between the two frames.

【Core Requirements】
1. The car is the real car of @Image1 until the camera is inside; nobody else is in the cockpit.
2. One woman only, exactly as in @Image2: the same face, bob with one clay-orange streak, star clip, headset microphone, white suit with clay-orange piping and white gloves; natural hands with five fingers; her lips stay closed.
3. Native colour, night.
4. No subtitles, captions, titles, signs, logos, watermarks or any on-screen text.

【Final Acceptance Criteria】
One continuous move that starts on @Image1, goes all the way through the canopy and ends on @Image2 inside the cockpit; no cut or dissolve; one woman, on-model, lips closed; no text.

【Audio Policy】 Silent video: no music, no sound effects, no voice.
```

### The closed-lip re-roll

The chapter reviewers found g39 showing her teeth in every window it was used in. Two Wan takes, $1.60 at list.

#### g39r2 and g39r2-t2 · HAIR-FALL, closed lips

Wan 3.0 image-to-video · 4 s × 2 takes · seeds 411 and 412 · $1.60

- **for:** s028 (0:27.18), the third "done" in the launch: g39 shows her teeth in every window, and a daytime sky from 2.8 s.
- **inputs:** first frame: rh-02 g10 #1 turned 180° (as g39). The prompt is g39's with "lips closed" made "her lips pressed together" and two sentences added at the end: one on her mouth, one on the night outside.
- **takes:** Take 1: USE, 1.8–4.0 s with the lips closed: upside down, the night window; the hair falls at 0.3–2.2 s with her lips slightly parted, which the film avoids. Take 2: ALT, 2.6–3.6 s with the lips closed; the hair falls gradually and the lips part at 0.9–2.2 s.
- **first cut:** not used.
- **final film:** s028 0:27.18–0:27.64 (take 1, 1.80–2.26).

Both takes, the same prompt:

```
Image 1 is the first frame. Keep her exactly as in Image 1: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek; her fitted white racing suit with thin clay-orange piping and a high collar closed to the throat, white racing gloves, no lettering on her clothes; native colour. One continuous shot, no cuts: the set stays exactly as Image 1 from the first frame to the last — the same cockpit, the same seat, the same window, the same light; no new screens, no new lights, no white interior; the camera stays at the same distance. Her lips stay closed; she never talks. No text, no logos, no badges, no other people. The car has just turned upside down at the top of the wall: she and the whole cockpit read upside down for the entire shot, her head toward the bottom of the frame. 0-0.5 s: still; her black bob still lies along her cheeks as if she were upright. 0.5-2.0 s: gravity takes it: her bob and the clay-orange streak fall away from her face, down toward the roof at the bottom of the frame, strand by strand, her bangs dropping off her forehead; the thin microphone boom stays at her cheek. 2.0-4 s: her hair hangs straight down and sways once; she looks into the lens, calm, her lips pressed together; outside the window the red light strip slides slowly upward. Camera: locked to the cockpit, no roll. The image never flips upright. Her mouth is shut for the whole shot: her lips stay pressed together from the first frame to the last, no teeth ever show, she does not breathe through her mouth and never speaks. Night outside the window the whole time: black sky, the red light strip, no daylight, no clouds.
```

## What the final film keeps from the takes

From the chapter files, the whole-film check and the frames. Each of these lies inside its take's usable window.

- **The flip off the ramp (g38sd-t2, s140).** From 2:32.08 to 2:32.25 Seedance turns the car's roof toward the camera, which reads like a roll, and a utility pole stands in the sky from 2:32.29. Neither is the invented ramp top or second car of the note.
- **The canopy dive (g37sd-t2, s024).** One frame, at 0:24.54, passes through Seedance's dim red dissolve with a faint ghost of a face.
- **REAL! (g27, s143).** Wan's invented white coupe is faintly visible in the smoke behind her from 2:38.4 to 2:39.48.
- **The apex orbit by the red pillar (g23-sd, s117).** It plays 1.50–2.66 s of the take, where the round-2 check found the background turning into a reference's sky with power lines; the check judged that window acceptable.
- **The hold's opening orbit (g09, s032).** It plays the take to 1.70 s at the end of a speed ramp. The round-2 check put the start of the hatchback rear at 1.6 s; the window in `TAKES.md`, which the final check used, runs to 4.3 s.
- **Painted out or framed out, so never seen:** Wan's glyphs on the rear plate (g01, g34-t2) and its licence plate (g28-r2), the mark in g17's corner, the orange placard in g44, the hood badge in g42, and the sparks in g41.

