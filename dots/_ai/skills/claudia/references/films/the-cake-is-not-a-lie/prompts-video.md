# THE CAKE IS NOT A LIE: the video prompts

The record of the video generations made for THE CAKE IS NOT A LIE, the eighth Claudia music film by anabology, job by job: its inputs, its prompt word for word, what came of it and its price at list. Every take is Seedance 2.5, on Replicate, on Higgsfield's API and, in the first film, on Higgsfield (References). It runs in production order: the first film, made on the first song and set aside when the song changed; the restart on the new song and its drafts 1–6; the test of GPT Image → Midjourney → Seedance; storyboard v5 and draft 7; the reshoots of drafts 8–11, and draft 12, the final cut. The character sheets, first frames and memory images that fed the takes are given with their instructions where they are shared, and in words per take. It was made 25–31 October 2026. The director's words are quoted as typed; […] marks a cut, and inside prompts `[the crab walker]` replaces a working name.

anabology's first message: "Hey I wanna make a new music video: The Cake Is Not A Lie. Very glados / valve style suno song, glados imagery, portal feel, Claudia argues the cake is not a lie and ai is here to save us. I literally want to build a lot of it in source engine and use source engine + seedance 2.5 (can try replicate relighting).  We should make chell be Claudia. Let's do it!!!" And at the restart, after the new song: "source can be used for reference visuals and physics but i want seedance 2.5 to make almost the whole thing and add the super aperture coded 2.5d animations comprehensively after." The final cut plays 73 Seedance takes in its shots and a 74th, her head in the memory film; six shots recorded in Portal 2, the memory film and two drawn cards fill the rest.

**Prices.** Costs are at list price, from the project's ledgers, and cover the takes in this record. Seedance 2.5 on Replicate, at 720p, as `shots/ledger-rep.jsonl` logs each request at submission: $0.2312 a second of output without a video input (a 4 s take $0.92, 5 s $1.16, 8 s $1.85) and $0.9676 a second with one (R-B12-4, a video edit, $3.91). Seedance 2.5 on Higgsfield's API, at 720p: the list price the ledger logs per request (`shots/ledger-hf.jsonl`), $0.4622 a second of output (4 s $1.85, 17 s $7.86); with a video input both the input's seconds and the output's are billed at 0.6 times that rate (a 17 s take with a 17 s guide, $9.43). The first film's takes on Higgsfield (References) are given in counts and seconds. The GPT Image 2.5 edits that made the frames are listed apart, as the image API reported them: the first film's 51 storyboard-frame edits $3.17 (`media/board/frames/ledger.jsonl`) and four frame fixes $0.20; the restart's 53 character sheets $3.65 (`media/v4/chars/ledger.jsonl`) and the two sheets of Portal 2's own Cave Johnson, $0.10; and 360 first frames, memory images, storyboard-v5 fixes and reshoot frames $24.31 (`shots/v4/images.jsonl`).

**The order of work.** The first film: the first song locked (Suno take E3 with the GLaDOS treatment G6), a storyboard of 50 shots drawn as pictures, GPT Image 2.5 edits of frames of Portal 2, and its takes: 25 shots on Replicate in first-frame mode, 19 on Higgsfield (References) and the last five on Higgsfield's API; cut v1, cut v2 with the cuts moved off sung words, cut v3 with the lyric layer (section 1). Then a new song on anabology's own take of lyric n3, and the restart: the story, the character sheets, a Midjourney test and library, the first frames, and the takes of three acts and of the anchor, her singing, assembled as draft 1 (114 shots); drafts 2–5 brought in the held anchor units, the shots recorded in Portal 2 and both choruses with GLaDOS's own motion, and draft 6 is draft 5's picture with the glitches kept to her head (section 2). anabology's notes on draft 5 led to the test of GPT Image → Midjourney → Seedance (section 3, which also lists a test of her singing on Replicate in reference mode with the vocal window, run once storyboard v5's frames existed; it became H06), then to storyboard v5, every first frame made again through Midjourney, and the takes of draft 7 from anabology's picks (section 4). Their notes on drafts 7 to 11 brought the reshoots of drafts 8–11, with the memory-initialization film, the HUD, the grade and the pacing pass around them (section 5). Section 6 lists the six shots recorded in Portal 2.

Jobs are the submissions in this record; takes are the video files that came back, measured with ffprobe (frames at 24 fps); the costs are the ledgers' list prices for those takes; "in the final cut" counts the takes a segment of draft 12 plays (`media/review/cut/v4-draft11-graded.json`, whose 98 segments draft 12 kept, re-rendering only the two drawn cards J03 and J11). A take placed twice with different lags (`media/clips/AN12a-3_J02/`) counts once. The totals add the ledgers' unrounded figures; each entry shows its own cost to the cent.

**Totals by section:**

| § | Phase | Jobs | Takes | Seconds in the takes | Cost at list | In the final cut |
|---|---|---|---|---|---|---|
| 1 | The first film, on the first song | 54 | 55 | 248.3 s | $42.07; the 20 takes on Higgsfield (References), 90.8 s, given in seconds | 0 |
| 2 | The restart: drafts 1–6 | 100 | 100 | 577.2 s | $214.90 | 20 |
| 3 | GPT Image → Midjourney → Seedance | 9 | 9 | 42.4 s | $9.71 | 1 |
| 4 | Storyboard v5 and draft 7 | 71 | 71 | 378.0 s | $117.89 | 46 |
| 5 | Drafts 8–12: the reshoots | 15 | 14 | 107.6 s | $50.59 | 6 |
| | **Total** | **249** | **249** | **1,353.4 s** | **$435.17** | **73** |

73 counts the takes the final's segments play; a 74th, MEMINIT-HEAD-1 (section 5), is her head inside the memory film.

**Totals by model and route:**

| Model and route | Jobs | Takes | Seconds in the takes | Cost at list | In the final cut |
|---|---|---|---|---|---|
| Seedance 2.5 on Replicate, first frame or first and last frame | 129 | 129 | 594.4 s | $136.18 | 37 |
| Seedance 2.5 on Replicate, references | 13 | 13 | 66.5 s | $15.26 | 9 |
| Seedance 2.5 on Replicate, video edit (with a video input) | 2 | 1 | 4.0 s | $3.91 | 1 |
| Seedance 2.5 on Higgsfield's API, no video input | 82 | 82 | 540.4 s | $248.20 | 26 |
| Seedance 2.5 on Higgsfield's API, with a video input | 4 | 4 | 57.2 s | $31.62 | 0 |
| Seedance 2.5 on Higgsfield (References), the first film | 19 | 20 | 90.8 s | given in seconds | 0 |
| **Total** | **249** | **249** | **1,353.4 s** | **$435.17**: Replicate $155.35, Higgsfield's API $279.82 | **73** |

**The final cut** (draft 12) in its 98 segments, from `media/review/cut/v4-draft11-graded.json`: the shot, its time in the film (the film starts at the song's 0:00), what plays, the point in the take it starts from and the speed where it is not 1. Singing takes are placed in song time by their vocal window and the lag the lip-sync check measured, so their start in the take follows from the window.

| Shot | In the film | Plays | From | Speed |
|---|---|---|---|---|
| A01 | 0:00.0–0:02.6 | R-A01-2 | 0.60 s |  |
| A02 | 0:02.6–0:05.1 | AN1-2 | its window |  |
| A03 | 0:05.1–0:07.6 | AN1-2 | its window |  |
| A04 | 0:07.6–0:13.7 | A04, the memory-initialization film (a Blender render) |  |  |
| A08 | 0:13.7–0:14.9 | AN2a-2 | its window |  |
| A09 | 0:14.9–0:17.4 | R-A09-4 | 0.25 s |  |
| A10 | 0:17.4–0:19.9 | R-A10-3 (beat-cut) |  |  |
| A11 | 0:19.9–0:22.3 | AN2b-2 | its window |  |
| A12 | 0:22.3–0:24.8 | H-A12-1 | 0.40 s |  |
| B01 | 0:24.8–0:25.4 | R-B01-2 | 0.80 s |  |
| B02 | 0:25.4–0:26.0 | R-B01-2 | 2.00 s |  |
| B03 | 0:26.0–0:26.6 | R-B01-2 | 3.60 s |  |
| B04 | 0:26.6–0:27.2 | H-B04-2 | 1.00 s |  |
| B05 | 0:27.2–0:28.5 | R-B05-1 | 0.10 s |  |
| B06 | 0:28.5–0:29.7 | AN3a-2 | its window |  |
| B07 | 0:29.7–0:30.9 | R-B07-4 | 2.60 s |  |
| B08 | 0:30.9–0:32.1 | H-B08-2 | 2.80 s |  |
| B10 | 0:32.1–0:34.0 | H-B10-1 | 1.70 s |  |
| B12 | 0:34.0–0:36.5 | R-B12-4 | 0.05 s | 1.4× |
| B13 | 0:36.5–0:38.3 | H-B13-3 | 2.90 s |  |
| B15 | 0:38.3–0:39.5 | H-B15-2 | 1.00 s |  |
| B16 | 0:39.5–0:41.4 | R-B16-2 | 1.00 s |  |
| B17 | 0:41.4–0:43.2 | R-B17-1 | 1.20 s |  |
| B18 | 0:43.2–0:44.5 | AN3b-4 | its window |  |
| P01 | 0:44.5–0:45.7 | R-P01-1 | 1.30 s |  |
| P02 | 0:45.7–0:46.9 | H-P02-3 | 0.60 s |  |
| P03 | 0:46.9–0:48.8 | H-P03-2 (beat-cut) |  |  |
| P04 | 0:48.8–0:50.6 | R-P04-1 | 0.60 s |  |
| P05 | 0:50.6–0:51.9 | H-P05-3 | 0.25 s |  |
| P06 | 0:51.9–0:53.7 | H-P06-1 | 0.90 s |  |
| C01 | 0:53.7–0:55.6 | AN4-6 | its window |  |
| C02 | 0:55.6–0:56.8 | AN4-6 | its window |  |
| C03 | 0:56.8–0:58.0 | R-C03-2 | 1.00 s |  |
| C05 | 0:58.0–1:00.5 | R-C05-2 | 0.60 s |  |
| C06 | 1:00.5–1:09.7 | AN4-17 | its window |  |
| C09 | 1:09.7–1:12.8 | AN4g-3 | its window |  |
| C10 | 1:12.8–1:14.0 | AN4g-3 | its window |  |
| T03 | 1:14.0–1:16.5 | H-T03-3 | 1.60 s |  |
| T04 | 1:16.5–1:17.7 | AN5-2 | its window |  |
| T05 | 1:17.7–1:20.2 | AN5-2 | its window |  |
| D01 | 1:20.2–1:23.9 | R-D01-1 | 0.00 s | 1.37× |
| D02 | 1:23.9–1:25.7 | AN6a-2 | its window |  |
| D03 | 1:25.7–1:26.9 | H-D03-3 | 0.75 s |  |
| D04 | 1:26.9–1:28.2 | R-D04-1 | 0.00 s |  |
| D05 | 1:28.2–1:30.0 | R-D05-2 | 1.00 s |  |
| D06 | 1:30.0–1:31.9 | AN6c-4 | its window |  |
| D08 | 1:31.9–1:33.1 | R-D08-1 | 0.30 s |  |
| D09 | 1:33.1–1:35.6 | AN6b-2 | its window |  |
| D10 | 1:35.6–1:38.0 | recorded in Portal 2 |  |  |
| D11 | 1:38.0–1:39.3 | R-D11-2 | 0.70 s |  |
| D12 | 1:39.3–1:40.5 | AN6b-2 | its window |  |
| D13 | 1:40.5–1:41.7 | R-D13-1 | 0.70 s |  |
| D14 | 1:41.7–1:43.0 | R-D14-2 | 1.00 s |  |
| E01 | 1:43.0–1:44.2 | R-E01-2 | 0.00 s |  |
| E02 | 1:44.2–1:46.0 | AN7-3 | its window |  |
| E03 | 1:46.0–1:47.3 | R-E03-1 | 0.60 s |  |
| E05 | 1:47.3–1:49.7 | AN7-1 | its window |  |
| E06 | 1:49.7–1:51.0 | R-E06-1 | 1.30 s |  |
| E07 | 1:51.0–1:52.8 | R-E07-1 | 0.80 s |  |
| F01 | 1:52.8–1:54.7 | AN8-6 | its window |  |
| F02 | 1:54.7–1:55.9 | AN8-6 | its window |  |
| F03 | 1:55.9–1:57.1 | R-F03-3 | 0.25 s |  |
| F04 | 1:57.1–1:58.4 | recorded in Portal 2 |  |  |
| F05 | 1:58.4–1:59.6 | recorded in Portal 2 |  |  |
| F06 | 1:59.6–2:02.1 | AN8-6 | its window |  |
| F07 | 2:02.1–2:03.3 | recorded in Portal 2 |  |  |
| F08 | 2:03.3–2:05.8 | AN8-8 | its window |  |
| F09 | 2:05.8–2:08.2 | AN8-8 | its window |  |
| G01 | 2:08.2–2:09.5 | recorded in Portal 2 |  |  |
| G03 | 2:09.5–2:11.9 | AN9-3 | its window |  |
| G04 | 2:11.9–2:13.1 | recorded in Portal 2 |  |  |
| G05 | 2:13.1–2:15.0 | R-G05-2 | 0.30 s |  |
| G07 | 2:15.0–2:16.9 | AN9-3 | its window |  |
| H01 | 2:16.9–2:19.3 | AN10a-3 | its window |  |
| H02 | 2:19.3–2:21.8 | R-H02-1 | 0.60 s |  |
| H03 | 2:21.8–2:23.0 | R-H03-1 | 0.30 s |  |
| H04 | 2:23.0–2:24.2 | R-H04-2 | 1.50 s |  |
| H05 | 2:24.2–2:26.7 | H-H05-3 | 0.60 s |  |
| H06 | 2:26.7–2:28.6 | T-REPSING-1 | its window |  |
| H07 | 2:28.6–2:30.4 | R-H07-2 | 1.20 s |  |
| H08 | 2:30.4–2:34.1 | AN10b-4 | its window |  |
| H09 | 2:34.1–2:36.0 | R-H09-2 | 0.25 s |  |
| H10 | 2:36.0–2:39.1 | H-H10-2 | 0.10 s |  |
| I01 | 2:39.1–2:41.5 | R-I01-2 | 0.15 s |  |
| I02 | 2:41.5–2:44.0 | AN11-3 | its window |  |
| I03 | 2:44.0–2:46.5 | H-I03-4 | 1.00 s |  |
| I04 | 2:46.5–2:50.2 | AN11-3 | its window |  |
| J01 | 2:50.2–2:52.7 | AN12a-3 | its window |  |
| J02 | 2:52.7–2:55.1 | AN12a-3 | its window |  |
| J03 | 2:55.1–2:56.4 | a drawn card over black |  |  |
| J04 | 2:56.4–2:57.6 | AN12a-3 | its window |  |
| J05 | 2:57.6–3:00.1 | H-J05-4 | 1.50 s |  |
| J06 | 3:00.1–3:07.5 | R-J06-2 | 0.30 s |  |
| J07 | 3:07.5–3:10.0 | AN12b-5 | its window |  |
| J08 | 3:10.0–3:12.5 | AN12b-5 | its window |  |
| J09 | 3:12.5–3:16.2 | AN12b-5 | its window |  |
| J10 | 3:16.2–3:22.3 | R-J10-1 | 0.30 s |  |
| J11 | 3:22.3–3:28.8 | a drawn card over black |  |  |

**How to read an entry.** The heading is the job's name, with "in the final cut" where a segment of the final plays it. Jobs keep their working names, and the numbers in them are not consecutive. The line under it gives the route, the length asked for, the resolution, the mode (first frame; first and last frame; references, in which @Image1 is used as the first frame; a video edit) with the sound setting, and the shots the take covers. Then come the inputs in words, the prompt word for word, the take as measured (its frames, its length at 24 fps and its size where it is not 1280 × 720), what came back and where it was used, and the cost at list price. The references a prompt names are Seedance's own tags: [Image1], [Video1], [Audio1] on Replicate and @Image1, @Video1, @Audio1 on Higgsfield. Where a prompt is an earlier job's with some lines changed, only the changed lines are printed: ⟪for: …⟫ names a line of the earlier prompt by its opening words and the lines under it take its place (several ⟪for: …⟫ in a row are replaced together by the lines that follow); ⟪after: …⟫ marks lines put in after the named line; ⟪drop: …⟫ a line taken out. Every prompt can be rebuilt from the record that way, and nothing else in a prompt is changed. "Drafts 1–6" means the take played in those drafts: draft 6 is draft 5's picture with a new glitch pass, and draft 12, the final, is draft 11 with two drawn cards re-rendered. The lip-sync check says whether a take copied @Audio1 or the model sang the words itself; a take it sang can still sit on the song with a steady offset, and was then placed by that offset. From section 4 on, a unit's storyboard-v5 X frame is the one Midjourney made from words and its Y frame the one Midjourney reimagined from the unit's earlier first frame; the batch, prompt and image number after it point into `prompts-midjourney.md`.

**Shared lines.** Long lines that recur word for word in many prompts are printed once here, and the prompts name them as ⟦name⟧ on a line of their own (a numbered requirement keeps its number: `1. ⟦lip sync⟧`). They are given with Higgsfield's tags; in a Replicate prompt the same line reads [Audio1] for @Audio1, [Image1] for @Image1, and so on.

⟦audio policy⟧:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 exactly from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, score, instrumental, melody, extra vocals, harmonies, ad-libs, narration or sound effects.
```

⟦audio policy, actions silent⟧:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 itself: copy @Audio1 exactly from the first frame to the last, with the same timing, pitch and level. Do not re-sing, re-voice or re-generate it. Do not add music, score, instrumental, melody, extra vocals, harmonies, ad-libs, narration or sound effects. Every action in this video is silent: the only sound is @Audio1.
```

⟦audio policy, end⟧:

```prompt
【Audio Policy】 The output soundtrack is @Audio1 unchanged; no music, score, extra vocals or sound effects.
```

⟦her voice⟧:

```prompt
@Audio1 is Claudia-GLaDOS's own singing voice and the complete soundtrack of this video; her porcelain lips and mechanical jaw follow @Audio1 exactly.
```

⟦lip sync⟧:

```prompt
Lip-sync word by word to @Audio1: her porcelain lips and mechanical jaw match every syllable of @Audio1, its start and its end; the mouth rests closed while @Audio1 is silent.
```

⟦nothing but her voice⟧:

```prompt
Her voice is @Audio1 and nothing else: she never sings, speaks or hums anything that is not in @Audio1.
```

⟦her, first film⟧:

```prompt
【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's white ceiling ring on a black robotic neck and a cable bundle with orange stripes; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears.
```

⟦her and the test subject, first film⟧:

```prompt
【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's white ceiling ring on a black robotic neck and a cable bundle with orange stripes; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears. Also in the shot: the test subject: a woman in an orange jumpsuit tied at the waist, a white tank top and white long-fall boots, dark hair in a ponytail, seen from behind; her face is never shown.
```

⟦keep her, first film⟧:

```prompt
Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the ceiling ring, the cables and the chamber exactly as in @Image1 throughout; one Claudia-GLaDOS only.
```

⟦her, in her chamber⟧:

```prompt
【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's white ceiling ring on a black robotic neck and a cable bundle with orange stripes; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears.
```

⟦her, grown⟧:

```prompt
【Subject】 Claudia-GLaDOS, the superintelligence that runs this facility: she hangs from a large double white ceiling ring on a thick black robotic boom of many cables with glowing orange stripes, with white Aperture personality cores (each with one glowing amber eye), boxy white compute modules with rows of small amber lights and several white jointed panel arms clamped along it; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears.
```

⟦her, hanging (storyboard v5)⟧:

```prompt
【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's white ceiling ring on a black robotic cable bundle with orange stripes that rises from the top and back of her head; below her chin there is only her white mechanical jaw piece, no neck, shoulders or body below her; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple. Only one Claudia-GLaDOS appears.
```

⟦her, from the housing (storyboard v5)⟧:

```prompt
【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's boom: a black cable bundle with glowing orange stripes comes down into a white mechanical housing on the top of her head, and below her chin there is only a short white mechanical jaw piece; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears.
```

⟦her, grown (storyboard v5)⟧:

```prompt
【Subject】 Claudia-GLaDOS, the superintelligence that runs this facility: she hangs from a large double white ceiling ring on a thick black robotic boom of many cables with glowing orange stripes, with white Aperture personality cores (each with one glowing amber eye) and several white jointed panel arms clamped along it; her head hangs from a white mechanical housing on its crown at the lower end of the boom, and nothing holds it from below; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, bare porcelain eyelids, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple. Only one Claudia-GLaDOS appears.
```

⟦keep her, in her chamber⟧:

```prompt
Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the ring, the cables and the chamber consistent with @Image1 throughout; one Claudia-GLaDOS only; the memory images appear only inside screens and panels.
```

⟦keep her, one streak⟧:

```prompt
Keep her porcelain face, her black bob with the one clay-orange streak and the star clip, the cables and the chamber consistent with @Image1 throughout; one Claudia-GLaDOS only; the memory images appear only inside screens and panels.
```

⟦boom like GLaDOS⟧:

```prompt
Her boom moves like GLaDOS in Portal 2, only bigger: slow, wide sways on the boom, sudden lunges toward the camera, recoils, rises and drops, twists of the whole body under the ring, the cables swinging with momentum; her head turns and tilts with every move.
```

⟦boom alive⟧:

```prompt
Her boom moves big and alive the whole time, timed to the music: it swings, lunges, rises and drops, and her head turns and tilts with it; never a static hanging head.
```

⟦party look⟧:

```prompt
Portal 2's Aperture Science dressed for a party: white panels with thin black seams, warm golden light mixed with cool fluorescents, orange, blue and white balloons, streamers, confetti, a photoreal Source-engine look.
```

⟦party turrets⟧:

```prompt
The turrets: white Portal 2 sentry turrets: glossy white egg-shaped bodies split down the middle, one glowing red eye each, three thin black legs, each wearing a paper cone party hat with orange, blue and white polka dots and a small pom-pom; they have no lasers and never fire.
```

⟦party look, short⟧:

```prompt
Portal 2's Aperture Science dressed for a party: warm golden light mixed with cool fluorescents, orange, blue and white balloons, streamers, confetti, a photoreal cinematic look.
```

⟦her, on a screen⟧:

```prompt
【Subject】 Claudia-GLaDOS, the AI of this facility, seen only as a face on a screen: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip.
```

⟦her, no eye makeup⟧:

```prompt
【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's white ceiling ring on a black robotic neck and a cable bundle with orange stripes; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears.
```

⟦head from the housing⟧:

```prompt
Her head always hangs from the white housing at the lower end of her boom: no neck, shoulders, shell, casing or stand ever appears under or around her head.
```

⟦the crab walker⟧:

```prompt
[the crab walker] (only one): her porcelain robot head on a cat-sized crab walker of glossy white shell panels with black seams, six thin black jointed legs and one small amber status light on her back. Her face is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; an adult face, late twenties.
```

⟦the Claudia-bot⟧:

```prompt
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers.
```

⟦the four friends⟧:

```prompt
Four small robots, each appearing exactly once: the blue-eyed personality core on its little wheeled rail crawler (a white sphere with grey handles and a big blue optic); the green-eyed turret-shaped agent on three thin black legs; the purple-eyed white cube walking on four stubby black legs; the tiny floating white sphere with a cyan eye trailing glowing cyan pixel packets.
```

## 1. The first film, on the first song

The first song was Suno take E3 with anabology's GLaDOS treatment G6, 172.64 s, locked with "We can optimize further but let's go with g6 and storyboard it. We can always improve audio in post". The storyboard became pictures ("not a markdown the storyboard should be pics") with Claudia as GLaDOS ("I imagine Claudia is glados and we use her style and head etc modified from the source shots"), in look B, her features in GLaDOS's white plating ("b is great close up"). Then: "Lol I love it go ahead and make the whole thing. You can use seedance 2.5 + also just orchestrate movements in source engine for the authentic look but ofc can use the source movements as motion reference for seedance or do entire things in seedance bc it's probably seen portal videos too […] go ahead and make magic. […]"

Of its 50 shots, 25 were made with Seedance 2.5 on Replicate in first-frame mode, 720p, with no sound, the storyboard frame as the first frame; 19 with Seedance 2.5 on Higgsfield (References), 720p, the storyboard frame as @Image1 and, for the singing shots, @Audio1 a window of Suno's own lead-vocal stem cut to exactly the take's length, with the sung words in whole-second segments; the last five on Higgsfield's API with the same jobs. Two shots, s48 and the end of s50 (the amber terminal: the test results and the credits typed out), were drawn in code. Cut v1 placed every shot on the bars of the storyboard. On cut v1 anabology asked: "Did you plan the cuts to start/end at bars from the start? […] wanted to make sure it was cut intentionally rather than to patch up lip sync issues. should have good prosody. and also, remember how lip sync worked from raw vocal stems but didn't from song? That should have been what we put into seedance, the vocal stems". The cuts had been planned on the bars and none had moved for lip sync, and every singing take's @Audio1 had been the vocal stem, never the song; cut v2 moved 29 of the 32 cuts that fell inside sung words to the nearest word boundary. On cut v2: "Can we add portal hud like graphics and animations that work with the best and give us the lyrics?"; cut v3 is cut v2 with that lyric layer drawn over it. On cut v3: "ok this is a good start, and give me a better vision for the video. we'll use a lot of the visual concepts and tools etc here we've made. but - i want to go back on the song and make a new one, with the same vocal isolation method and gladosifying weve done. […]" The new song and the restart (section 2) set this whole film aside; none of its takes is in the final cut.

### The storyboard frames

GPT Image 2.5 made the storyboard frames of 48 shots, three of them twice (51 edits, $3.17), each an edit of a frame of Portal 2: the base frame first, then, where she is in the shot, her official reference sheet without the headset microphone and her look-B close-up. The instruction was the same template for every shot (`tools/board_frames.py` holds each shot's sentences); ⟨SHOT⟩ is the shot's own sentences, in which ⟦CG⟧ and ⟦CHELL⟧ stand for the two descriptions below, and the last sentence was left off where the shot asks for words:

```prompt
Edit the first image. This is a frame from Portal 2. ⟨SHOT⟩ Keep the Source frame's set, materials and camera unless told otherwise. A cinematic photograph of a real set built like Portal 2's Aperture Science facility, its own light, sharp focus, 35mm, 16:9. No text, no letters, no logos.
```

⟦CG⟧:

```prompt
Claudia-GLaDOS: GLaDOS's robotic body (the white ceiling ring, the black cable bundle with orange stripes, the white-plated mechanical neck) with a robotic head modelled exactly on the woman in the second image and designed exactly as in the third image: her face as smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, her exact features (the grown-up angular face of a 28-year-old woman, defined cheekbones and a strong jawline, light freckles printed on the porcelain), dark glass eyes with a faint warm glow, and her real hair: a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip
```

⟦CHELL⟧:

```prompt
Chell, the test subject: a woman in an orange jumpsuit with the top half tied at her waist, a white tank top and white long-fall boots with curved spring struts at the heels, dark hair in a short ponytail, seen from behind, her face not visible
```

For s05, for example, ⟨SHOT⟩ is: "Turn GLaDOS into ⟦CG⟧. A medium shot: she sings from her ceiling ring, her porcelain face turned three-quarters to the camera. Behind her, several of the chamber's dark wall panels have flipped round to show red hand-painted scrawls: THE CAKE IS A LIE." Five frames were made again for retakes (`media/board/frames-r2/`): s03, s28 and s46 had areas of plain black that GPT Image 2.5 filled in, s36 had an orange portal on the lens taken out (these four $0.20, as their logs give them), and s50a is a new frame of the candle smoke (its cost was not recorded).

### Seedance 2.5 on Replicate: a test and 24 more shots

First-frame mode, 720p, no sound, the storyboard frame as the first frame. Every prompt opens with the first-frame sentence and describes the composition, the action, the camera and what stays the same. The first job, s24-t1, was a test made before the batch.

#### s24-t1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s24 (verse 2, 73.58–76.23 s of the first song)

**First frame:** the storyboard frame s24 (`media/board/frames/s24.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: inside the Aperture Science incinerator shaft, a round iris hatch in a dark riveted metal wall, open, pouring out a warm golden oven glow; inside it, on a metal tray, a dark chocolate cake.
The iris hatch's blades finish spiralling open with a smooth mechanical motion; the warm light swells and flickers like an oven; the chocolate cake on the tray rises gently as it bakes, a little heat shimmer over it. Dust drifts through the light. The camera pushes in slowly toward the hatch.
Keep the hatch, the shaft's girders and the cake the same throughout; no people appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The incinerator's iris hatch spirals open on an oven glow and a rising chocolate cake. Kept as s24. In cuts v1–v3. **Cost:** $0.92.

#### s01-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s01 (intro, 0.00–1.98 s of the first song)

**First frame:** the storyboard frame s01 (`media/board/frames/s01.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: an extreme close-up of a cracked concrete wall in a dark hidden den, covered in red hand-painted lines THE CAKE IS A LIE, lit by a caged work lamp at the left.
The work lamp swings slowly on its cable, its warm pool of light sliding across the red letters and back; dust drifts in the beam.
The camera tracks slowly sideways along the wall.
Keep every painted line of text exactly as it is.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The work lamp swings its pool of light along the red scrawl while the camera tracks sideways. In cuts v1–v3. **Cost:** $0.92.

#### s02-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s02 (intro, 1.98–4.63 s of the first song)

**First frame:** the storyboard frame s02 (`media/board/frames/s02.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: an extreme close-up of the red scrawled wall; a slender white Aperture robot arm with a black gripper holds a red marker at the word NOT it has just written: THE CAKE IS ^NOT A LIE.
The gripper finishes the last stroke of the T in NOT and lifts the marker away from the wall; the red paint glistens wet.
The camera holds still, a locked macro.
Keep all the painted words exactly as in the first frame; nothing new is written.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Her white robot arm writes the caret and NOT into one line of the scrawl. In cuts v1–v3. **Cost:** $0.92.

#### s03-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s03 (intro, 4.63–7.28 s of the first song)

**First frame:** the storyboard frame s03 (`media/board/frames/s03.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a wide view of the dark rubble den: one concrete wall covered in red lines THE CAKE IS A LIE with one line reading NOT, a security camera on the wall, a work lamp, a white robot arm near the ceiling.
The white robot arm folds back up into the dark ceiling; the small security camera on the wall swivels toward the word NOT and its lens glows warm; the lamp sways.
The camera pulls back slowly on a rising arc.
Keep the painted words, the rubble and the room layout unchanged.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The first frame had areas of plain black in it, and the take carried them. Retaken as s03-r2. Not in a cut. **Cost:** $0.92.

#### s03-r2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s03 (intro, 4.63–7.28 s of the first song)

**First frame:** the storyboard frame s03 with its black areas filled in by GPT Image 2.5 (`media/board/frames-r2/s03.png`).

**Prompt:** the prompt of s03-r1.

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The same prompt on the storyboard frame with the black areas filled in by GPT Image 2.5. In cuts v1–v3. **Cost:** $0.92.

#### s06-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s06 (verse 1, 17.89–20.54 s of the first song)

**First frame:** the storyboard frame s06 (`media/board/frames/s06.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a macro close-up of the red painted words THE CAKE IS NOT A LIE on a concrete wall, the fresh NOT starting to drip, a red marker tip at the right edge.
Thin drips of wet red paint run slowly down from the letters of NOT; the marker tip lifts away out of frame.
The camera drifts slightly closer.
Keep the words exactly as they are.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The ^NOT in fresh red paint, starting to run, the marker lifting away. In cuts v1–v3. **Cost:** $0.92.

#### s07-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s07 (verse 1, 20.54–23.19 s of the first song)

**First frame:** the storyboard frame s07 (`media/board/frames/s07.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a low-angle wide shot of a tall dark den wall: a ten-foot red candle with a flame painted above an old chalk mural of a cake, a white robot arm near the top, a woman in an orange jumpsuit tied at the waist and a white tank top standing small at the bottom, seen from behind.
The robot arm adds the last brush strokes to the painted flame; the woman at the bottom tilts her head up to look at it. Her face is never shown.
The camera tilts up slowly from the woman to the painted flame.
Keep the mural, the candle and the woman's outfit unchanged.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Her arm paints a ten-foot red candle up the den wall above the cake mural, Chell small below. In cuts v1–v3. **Cost:** $0.92.

#### s08-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s08 (verse 1, 23.19–25.84 s of the first song)

**First frame:** the storyboard frame s08 (`media/board/frames/s08.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: the point of view from the floor of a white Aperture test chamber, looking up at an observation window high on the wall; a vent below the window is open and a silver party balloon floats out of it.
The silver balloon drifts slowly upward toward the observation window, turning gently on its string; a soft hiss of air from the vent stirs a little dust.
The camera tilts up slowly from the vent to the window.
Keep the chamber, the window and the single balloon.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** From the chamber floor, a vent lets out one silver party balloon that drifts up toward the observation glass. In cuts v1–v3. **Cost:** $0.92.

#### s10-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s10 (verse 1, 28.49–31.15 s of the first song)

**First frame:** the storyboard frame s10 (`media/board/frames/s10.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a clean white Aperture test chamber whose far wall is a giant display showing a white human pictogram with a blue scan band and one glowing dot in the chest, a security camera at the upper right.
A band of blue scanning light sweeps down the pictogram and stops on the dot, which pulses brighter; the security camera turns slightly toward the display.
The camera pushes slowly toward the screen.
Keep the pictogram simple and flat, and the chamber clean.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The giant scan display finds one glowing dot; the security camera beside it looks in. In cuts v1–v3. **Cost:** $0.92.

#### s12-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s12 (pre-chorus 1, 33.80–36.45 s of the first song)

**First frame:** the storyboard frame s12 (`media/board/frames/s12.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: an extreme close-up of a backlit Aperture chamber sign: the big number 07, a progress bar, and two rows of black pictograms; the last pictogram is a cake with one candle.
The sign flickers on with a hum; the progress bar fills segment by segment from left to right; the cake pictogram lights last and glows brightest.
The camera slides slowly along the sign from left to right.
Keep the number and every pictogram exactly as in the first frame.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The backlit chamber sign flickers on; its last pictogram is a cake. In cuts v1–v3. **Cost:** $0.92.

#### s15-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s15 (chorus 1, 41.76–44.41 s of the first song)

**First frame:** the storyboard frame s15 (`media/board/frames/s15.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a medium shot on the round platform of a dark spherical chamber: a woman in an orange jumpsuit tied at the waist and a white tank top stands seen from behind while white Aperture turrets hang from ceiling hatches around her, red laser sights converging on her back.
The turrets unfold their side panels and swing slightly, their thin red laser lines sliding across the floor and converging on her back; she stays still. Her face is never shown.
The camera arcs slowly around her from behind.
Keep the turrets' design and the woman's outfit unchanged.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Turrets drop from the ceiling around Chell and their red laser sights converge on her. In cuts v1–v3. **Cost:** $0.92.

#### s17-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s17 (chorus 1, 47.06–49.71 s of the first song)

**First frame:** the storyboard frame s17 (`media/board/frames/s17.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a top shot straight down at the round white platform of a dark chamber: a woman in an orange jumpsuit and a white tank top kneels on it, a glowing blue portal oval open beneath her.
The blue portal's rim shimmers and grows; she drops through it and is gone; the camera then falls toward the glowing oval.
Top-down; the camera plunges straight down into the portal at the end.
Her face is never shown; keep the platform and the portal's blue glow.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Chell fires a portal at the floor between her feet and the camera drops through the blue portal. In cuts v1–v3. **Cost:** $0.92.

#### s18-r1

Seedance 2.5 on Replicate · 6 s · 720p · first frame, no sound · s18 (post-chorus 1, 49.71–55.01 s of the first song)

**First frame:** the storyboard frame s18 (`media/board/frames/s18.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: an extreme wide shot of a vast shaft inside the Aperture facility: white robotic arms holding white wall panels on both sides, a catwalk across the middle with a tiny person on it.
Hundreds of white robotic arms swing the white panels into place in a smooth mechanical rhythm, building a bright new test chamber around the catwalk; light pours in as the panels lock.
The camera rises slowly through the arms.
Keep the arms' white industrial design and the tiny person on the catwalk.
```

**Take:** 145 frames (6.04 s, 1280 × 718). **Outcome:** Out of the orange portal into a vast shaft where hundreds of robotic arms swing white panels into place around Chell, tiny on a catwalk. In cuts v1–v3. **Cost:** $1.39.

#### s20-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s20 (post-chorus 1, 60.31–62.97 s of the first song)

**First frame:** the storyboard frame s20 (`media/board/frames/s20.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: the view from inside a lift as its doors part onto a dark room filled with rows of white Aperture turrets with single red eyes, a white turret close in the foreground.
The lift doors finish sliding open; the turrets' eyes light one by one across the rows, red changing to a warm white.
The camera pushes slowly out of the lift.
Keep the turrets' design: smooth white capsule bodies with one round eye.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The lift doors part on a dark room of turrets lighting their eyes one by one. In cuts v1–v3. **Cost:** $0.92.

#### s22-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s22 (verse 2, 68.27–70.93 s of the first song)

**First frame:** the storyboard frame s22 (`media/board/frames/s22.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a close-up of one white Aperture turret hanging in a dark chamber, side panels slightly open, its single round eye glowing golden, other turrets out of focus behind.
Its eye softens from red to a warm golden glow and pulses gently, as if it is singing; its side panels open and close a little in time.
The camera holds; the focus racks from the turrets behind to its eye.
Keep its smooth white capsule body and single eye.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** One turret close: its red eye softens to a warm glow as it sings. In cuts v1–v3. **Cost:** $0.92.

#### s26-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s26 (verse 2, 78.88–81.53 s of the first song)

**First frame:** the storyboard frame s26 (`media/board/frames/s26.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a glass test cell in a white Aperture chamber: inside, a king cobra rears with its hood spread; a small vial of glowing blue liquid drops from a white dispenser tube above.
The blue vial lands softly in the cell; the cobra lowers its hood, relaxes and coils calmly on the floor.
The camera holds still.
Keep the glass cell, the dispenser and the single cobra.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** A king cobra rears in a glass cell; a blue vial drops from a dispenser and the cobra lowers its hood. In cuts v1–v3. **Cost:** $0.92.

#### s28-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s28 (verse 2, 84.19–86.84 s of the first song)

**First frame:** the storyboard frame s28 (`media/board/frames/s28.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a scanner bench in a white lab booth: a charred black rolled papyrus scroll on a cradle under a blue scanning light, a display behind it showing lines of ancient Greek text.
The charred scroll turns slowly on its cradle; a band of blue light passes over it; on the display, new lines of white Greek letters light up one by one.
The camera holds, pushing in slightly.
Keep the scanner and the display's layout.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The first frame had areas of plain black in it, and the take carried them. Retaken as s28-r2. Not in a cut. **Cost:** $0.92.

#### s28-r2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s28 (verse 2, 84.19–86.84 s of the first song)

**First frame:** the storyboard frame s28 with its black areas filled in by GPT Image 2.5 (`media/board/frames-r2/s28.png`).

**Prompt:** the prompt of s28-r1.

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The same prompt on the storyboard frame with the black areas filled in by GPT Image 2.5. In cuts v1–v3. **Cost:** $0.92.

#### s29-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s29 (verse 2, 86.84–89.49 s of the first song)

**First frame:** the storyboard frame s29 (`media/board/frames/s29.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a clean white test chamber: a woman in an orange jumpsuit and a white tank top, seen from behind, holds a grey Weighted Companion Cube with pink hearts under a white tube dispenser in the ceiling.
She hugs the cube close and rocks it gently; the dispenser's doors above her close softly. Her face is never shown.
The camera holds, then tilts down slightly with the cube.
Keep the cube's pink hearts and her outfit unchanged.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The ceiling dispenser came down onto Chell's head. Retaken as s29-r2, with the dispenser told to stay put. Not in a cut. **Cost:** $0.92.

#### s29-r2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s29 (verse 2, 86.84–89.49 s of the first song)

**First frame:** the storyboard frame s29 (`media/board/frames/s29.png`).

**Prompt:** s29-r1's, with these changes:

```prompt
⟪for: She hugs the cube close and …⟫
⟪for: The camera holds, then tilts down …⟫
She hugs the cube close and rocks it gently from side to side. The white dispenser tube stays fixed high in the ceiling above her the whole time; nothing comes down from it. Her face is never shown.
The camera holds still.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The dispenser stays fixed in the ceiling while Chell hugs the Companion Cube; the camera holds still. In cuts v1–v3. **Cost:** $0.92.

#### s31-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s31 (pre-chorus 2, 92.15–94.80 s of the first song)

**First frame:** the storyboard frame s31 (`media/board/frames/s31.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: the point of view of someone walking toward a wooden shed door that has swung open onto a sunlit field of golden wheat under a blue sky; a small white security camera above the door.
The door finishes swinging open; wind moves through the wheat; the security camera above the door turns to follow, its lens glowing warm.
The camera walks forward toward the doorway and the light.
Keep the shed, the field and the camera.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** From your point of view the shed door swings open onto a sunlit wheat field while the security camera above it watches you go. In cuts v1–v3. **Cost:** $0.92.

#### s36-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s36 (bridge, 108.06–110.70 s of the first song)

**First frame:** the storyboard frame s36 (`media/board/frames/s36.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: the first-person view high above a vast white Aperture test chamber after a catapult launch.
Flying in a high arc across the chamber, wall panels and catwalks wheel past, then the floor tilts back as the arc begins to fall.
First-person flight; the camera moves fast along the arc.
Keep the chamber's Aperture architecture.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The flight tumbled, with an orange portal stuck to the lens. Retaken as s36-r2. Not in a cut. **Cost:** $0.92.

#### s36-r2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s36 (bridge, 108.06–110.70 s of the first song)

**First frame:** the storyboard frame s36 with the orange portal on the lens taken out by GPT Image 2.5 (`media/board/frames-r2/s36.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: the first-person view from high above a vast white Aperture test chamber in mid-flight after a catapult launch, a black cable hanging in front, the landing platform with cyan lights far below.
Flying forward in one smooth high arc across the chamber: the wall panels and the hanging cable slide past, the far landing platform comes up ahead, then the view tips down toward it as the arc begins to fall. The view never spins or tumbles.
First-person flight, one continuous smooth arc.
Keep the chamber's Aperture architecture; no people appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** From a first frame with the portal taken out by GPT Image 2.5, and the flight asked for as one smooth arc. In cuts v1–v3. **Cost:** $0.92.

#### s37-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s37 (bridge, 110.70–113.36 s of the first song)

**First frame:** the storyboard frame s37 (`media/board/frames/s37.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: an extreme close-up at ankle height, side-on: white long-fall boots with curved dark grey spring struts at the heels on a white tiled floor.
The boots land from a jump; the curved spring struts compress on impact and spring back; a little dust puffs from the tiles.
The camera holds low and still.
Keep the boots' design.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Chell's long-fall boots land and their curved struts compress and spring back. In cuts v1–v3. **Cost:** $0.92.

#### s40-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s40 (final chorus, 118.66–121.31 s of the first song)

**First frame:** the storyboard frame s40 (`media/board/frames/s40.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a wide shot of tiers of white Aperture turrets around a dark chamber like a choir, lit warm gold, GLaDOS's white ceiling ring above.
The turrets open and close their side panels in time like singers, their eyes glowing warm, row after row in a rippling wave.
The camera moves fast laterally along the tiers.
Keep the turrets' design and the tiers.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The tiers of turrets sing back like a choir. In cuts v1–v3. **Cost:** $0.92.

#### s43-r1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · s43 (final chorus, 129.27–131.93 s of the first song)

**First frame:** the storyboard frame s43 (`media/board/frames/s43.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a top-down macro of a Black Forest cake with one lit candle on a white plate, a slender white robot arm with a knife.
The robot arm cuts the cake into neat slices, one clean cut after another, in a steady rhythm.
Top-down, the camera holds.
Keep the cake's whipped cream, cherries and chocolate shavings.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Her robot arm's knife cuts the cake into slices, one after another. In cuts v1–v3. **Cost:** $0.92.

#### s45-r1

Seedance 2.5 on Replicate · 6 s · 720p · first frame, no sound · s45 (outro, 134.58–139.88 s of the first song)

**First frame:** the storyboard frame s45 (`media/board/frames/s45.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a motion-blurred plunge down a vast shaft inside the Aperture facility.
The camera races straight down through the facility, past catwalks, pipes and lit test chambers, faster and faster, light streaking.
One continuous fast descent.
Keep the Aperture industrial architecture.
```

**Take:** 145 frames (6.04 s, 1280 × 718). **Outcome:** The camera races down through the facility in one move, past chambers and catwalks. In cuts v1–v3. **Cost:** $1.39.

#### s46-r1

Seedance 2.5 on Replicate · 6 s · 720p · first frame, no sound · s46 (outro, 139.88–145.19 s of the first song)

**First frame:** the storyboard frame s46 (`media/board/frames/s46.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a dark rubble den: a small wooden table with a Black Forest cake and one lit candle; on the concrete wall behind, red painted letters THE CAKE IS NOT A LIE among many older lines.
The candle flame flickers gently; the warm light breathes on the wall; dust drifts.
The camera pushes in slowly toward the cake.
Keep the painted words exactly as they are.
```

**Take:** 145 frames (6.04 s, 1280 × 718). **Outcome:** The first frame had areas of plain black in it, and the take carried them. Retaken as s46-r2. Not in a cut. **Cost:** $1.39.

#### s46-r2

Seedance 2.5 on Replicate · 6 s · 720p · first frame, no sound · s46 (outro, 139.88–145.19 s of the first song)

**First frame:** the storyboard frame s46 with its black areas filled in by GPT Image 2.5 (`media/board/frames-r2/s46.png`).

**Prompt:** the prompt of s46-r1.

**Take:** 145 frames (6.04 s, 1280 × 718). **Outcome:** The same prompt on the storyboard frame with the black areas filled in by GPT Image 2.5: the cake with one lit candle on a small table in the den, THE CAKE IS ^NOT A LIE on the wall behind. In cuts v1–v3. **Cost:** $1.39.

#### s50a-r1

Seedance 2.5 on Replicate · 6 s · 720p · first frame, no sound · s50 (tail, 158.45–172.64 s of the first song)

**First frame:** a GPT Image 2.5 frame of the candle smoke rising in the den (`media/board/frames-r2/s50a.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines the composition: a medium close-up of a Black Forest cake on a wooden table in a dark hidden den, its single candle just blown out, a thin ribbon of grey smoke rising from the wick through warm work-lamp light, red painted words NOT A LIE out of focus on the concrete wall behind.
The thin ribbon of smoke curls slowly upward, twisting and thinning as it drifts through the warm light; the wick's last ember glows faintly and fades. Dust motes float in the beam. Nothing else moves.
The camera pushes in very slowly toward the cake.
Keep the cake, the table, the painted words and the warm light exactly as in the first frame; no flame relights; no people appear.
```

**Take:** 145 frames (6.04 s, 1280 × 718). **Outcome:** The candle smoke curling up in the den's lamp light: the first part of s50, before the amber terminal's credits (drawn in code). In cuts v1–v3. **Cost:** $1.39.

### Seedance 2.5 on Higgsfield (References): nineteen shots

720p, 16:9. @Image1 is the shot's storyboard frame (downscaled to 1280 × 720), used as the first frame; for the singing shots @Audio1 is the window of Suno's lead-vocal stem from the shot's song time, cut to the take's length, and the audio policy asks for @Audio1 to be copied (the song is laid over the take in the cut). The sound setting is given with each take. These takes are given in seconds: 19 submissions, 20 takes, 86 s asked for and 90.8 s in the takes.

#### s04-h1

Seedance 2.5 on Higgsfield (References) · 6 s · 720p · references, @Image1 as the first frame, sound on · s04 (intro, 7.28–12.58 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s04; @Audio1: the first song's lead vocal from 7.28 s, 6 s.

**Prompt:** not saved with the job.

**Take:** 145 frames (6.04 s). **Outcome:** The first of her takes: her porcelain head on-model, her eyes lit amber, the vocal copied to the end of the window. The take opened on a still first frame, so cut v2 starts it later. In cuts v1–v3.

#### s05-h1

Seedance 2.5 on Higgsfield (References) · 6 s · 720p · references, @Image1 as the first frame, sound on · s05 (verse 1, 12.58–17.89 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s05, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 12.43 s, 6 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Behind her, more dark wall panels flip over one by one, each showing another red hand-painted scrawl. She sways gently on her cables and turns her face from the scrawls back to the camera as she sings.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a medium-wide view from below of Claudia-GLaDOS hanging from her ceiling ring in her dark spherical chamber; dark wall panels around her carry red hand-painted words.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-2s: in @Audio1 she sings "wrote it on the walls in red,"; her lips form each of those words exactly when it sounds in @Audio1.
2-5s: in @Audio1 she sings "a thousand times, the cake's a lie."; her lips form each of those words exactly when it sounds in @Audio1.
5-6s: in @Audio1 she sings "I added"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A slow orbit around her at her height, from her left toward her front.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s). **Outcome:** The lip-sync check found the vocal copied through the shot. In cuts v1–v3.

#### s09-h2

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound off · s09 (verse 1, 25.84–28.49 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s09, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 25.59 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. On every monitor the same face sings together in sync, laughing softly between the words. The silver balloon drifts and bumps gently against the glass.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: through dark observation-room glass, a wall of eight monitors each showing Claudia-GLaDOS's porcelain face, laughing; a silver party balloon floats in front of the glass at the upper left.
@Audio1 is Claudia-GLaDOS's own singing voice and the complete soundtrack of this video; her face on the screens follow @Audio1 exactly.

⟦her, on a screen⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-3s: in @Audio1 she sings "and watch you laughing through the glass."; her lips form each of those words exactly when it sounds in @Audio1.
3-4s: in @Audio1 she sings "I read your scan a"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 Locked, looking through the glass at the monitors.

【Core Requirements】
1. Lip-sync word by word to @Audio1: her face on the screens match every syllable of @Audio1, its start and its end; the mouth rests closed while @Audio1 is silent.
2. ⟦nothing but her voice⟧
3. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the screen and the room exactly as in @Image1 throughout.
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The wall of eight monitors, every one her laughing face, behind the observation glass. In cuts v1–v3.

#### s11-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s11 (verse 1, 31.15–33.80 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s11, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 30.85 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. She looks down at the camera, gentle and reassuring; the warm light in her glass eyes softens as she sings.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a close-up from below of Claudia-GLaDOS's porcelain face hanging from the ceiling ring in her dark chamber.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-3s: in @Audio1 she sings "I caught it early. You'll be fine."; her lips form each of those words exactly when it sounds in @Audio1.
3-4s: in @Audio1 she sings "Probability"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A slow push in from below toward her face.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied through the shot. In cuts v1–v3.

#### s13-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s13 (pre-chorus 1, 36.45–39.10 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s13, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 35.87 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. She sings proudly, certain; a thin glowing progress bar reflected in her glass eyes fills to the end and her eyes brighten a little as it completes.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a close-up of Claudia-GLaDOS's porcelain face, her glass eyes amber, the round platform below in her dark chamber.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-1s: in @Audio1 she sings "cake:"; her lips form each of those words exactly when it sounds in @Audio1.
1-3s: in @Audio1 she sings "one hundred percent."; her lips form each of those words exactly when it sounds in @Audio1.
3-4s: in @Audio1 she sings "I know you"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A locked close-up.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied through the shot. In cuts v1–v3.

#### s14-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s14 (chorus 1, 39.10–41.76 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s14, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 38.65 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Claudia-GLaDOS lowers a little toward the test subject and sings down to her, kindly; the test subject looks up at her and stays still.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a low wide view of the dark spherical chamber: Claudia-GLaDOS hangs huge from the ceiling ring, and far below her the test subject stands small on the round white platform, seen from behind.
⟦her voice⟧

⟦her and the test subject, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-4s: in @Audio1 she sings "I know you thought I'd let you die,"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 Low and wide from behind the test subject, a slow push toward Claudia-GLaDOS.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied, to the shot's last silence. In cuts v1–v3.

#### s16-h1

Seedance 2.5 on Higgsfield (References) · 5 s · 720p · references, @Image1 as the first frame, sound on · s16 (chorus 1, 44.41–47.06 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s16, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 43.21 s, 5 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. She smiles as she sings. One by one the thin red laser lines swing away and switch off; red laser light slides across her porcelain face and leaves it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a close-up of Claudia-GLaDOS's porcelain face in her dark chamber, thin red laser lines crossing the dark behind her.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-5s: in @Audio1 she sings "but the cake is not a lie."; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A locked close-up.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 121 frames (5.04 s). **Outcome:** The model sang the line itself instead of copying it: a close-up whose mouth opens on the held words, but not exactly. In cuts v1–v3.

#### s19-h1

Seedance 2.5 on Higgsfield (References) · 6 s · 720p · references, @Image1 as the first frame, sound on · s19 (post-chorus 1, 55.01–60.31 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s19, downscaled to 1280 × 720; no audio.

**Prompt:**

```prompt
Use @Image1 as the first frame.
This first frame defines the composition: a glass lift tube rising through a dark shaft: the test subject stands inside, seen from behind, and a large video panel above shows Claudia-GLaDOS's porcelain face with her eyes closed.

【Event】 The glass lift rises steadily. On the video panel her face hums along to music with her lips closed, eyes closed, swaying gently with the rhythm. She does not sing or speak.

【Subject】 Claudia-GLaDOS, the AI of this facility, seen only as a face on a screen: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Also in the shot: the test subject: a woman in an orange jumpsuit tied at the waist, a white tank top and white long-fall boots, dark hair in a ponytail, seen from behind; her face is never shown.

【Camera】 The camera orbits slowly around the glass tube as it rises.

【Core Requirements】
1. She does not sing or speak; her lips stay closed.
2. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the screen and the room exactly as in @Image1 throughout.
3. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.
```

**Take:** 145 frames (6.04 s). **Outcome:** No singing in this shot and no vocal input: on the lift's panel her face hums along with her lips closed. In cuts v1–v3.

#### s21-h1

Seedance 2.5 on Higgsfield (References) · 6 s · 720p · references, @Image1 as the first frame, sound on · s21 (verse 2, 62.97–68.27 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s21, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 62.97 s, 6 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. The turrets open their side panels in time like a choir; Claudia-GLaDOS conducts them with small sways of her head as she sings, and their eyes warm from red to gold, tier by tier.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a wide view of her dark spherical chamber: tiers of white Aperture turrets with single red eyes ring the walls; Claudia-GLaDOS hangs from the ceiling ring in the middle.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-6s: in @Audio1 she sings "The turrets sing"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A slow crane down the tiers toward her.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s). **Outcome:** The model sang the line itself instead of copying it. The take opened on a still first frame, so cut v2 starts it later. In cuts v1–v3.

#### s23-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s23 (verse 2, 70.93–73.58 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s23, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 70.51 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. She sings proudly, a little smug, chin up; behind her the turrets' eyes glow and their side panels open in time.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a medium close-up from below of Claudia-GLaDOS's porcelain face, tiers of white turrets with red eyes behind her.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-3s: in @Audio1 she sings "I taught them that, and it's true."; her lips form each of those words exactly when it sounds in @Audio1.
3-4s: in @Audio1 she sings "The furnace is"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 Locked.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied through the shot. In cuts v1–v3.

#### s25-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s25 (verse 2, 76.23–78.88 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s25, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 75.97 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. The pedestal rises a little further from the floor hatch; she looks down at the cake fondly as she sings over it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a low angle in her dark chamber: a Black Forest cake with one unlit candle on a pedestal at the bottom of the frame, Claudia-GLaDOS hanging above it from the ceiling ring.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-3s: in @Audio1 she sings "that's where I baked it, anyhow."; her lips form each of those words exactly when it sounds in @Audio1.
3-4s: in @Audio1 she sings "I made an antidote"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 Low angle; the camera tilts up slowly from the cake to her face.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied through the shot. In cuts v1–v3.

#### s27-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s27 (verse 2, 81.53–84.19 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s27, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 81.05 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. The calm cobra slides slowly along her cables and settles, its head resting near her cheek; she sings tenderly, unafraid.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a medium close-up of Claudia-GLaDOS's porcelain face; a calm golden-brown cobra is coiled around her black robotic neck and cables, its hood down.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-3s: in @Audio1 she sings "for every bite a cobra takes."; her lips form each of those words exactly when it sounds in @Audio1.
3-4s: in @Audio1 she sings "I read"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A slow push in.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied, to the shot's last silence. In cuts v1–v3.

#### s30-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s30 (pre-chorus 2, 89.49–92.15 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s30, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 89.37 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Behind her the pictograms light up one after another and the big check mark glows brighter; she sings warmly, pleased.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a medium close-up of Claudia-GLaDOS's porcelain face; behind her a curved wall of glowing white test pictograms and a big check mark.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-3s: in @Audio1 she sings "I passed your safety test."; her lips form each of those words exactly when it sounds in @Audio1.
3-4s: in @Audio1 she sings "Go home and get"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 Locked.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied, but the lips leave it about a second before the cut. In cuts v1–v3.

#### s32-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s32 (chorus 2, 94.80–97.45 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s32, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 94.61 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Claudia-GLaDOS sings down to the test subject; the test subject looks up at her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a high angle from behind and above Claudia-GLaDOS's head: far below, the test subject stands on the round white platform looking up.
⟦her voice⟧

⟦her and the test subject, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-4s: in @Audio1 she sings "I know you thought I'd let you die,"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 High, over her shoulder; a slight push toward the platform.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied through the shot. In cuts v1–v3.

#### s33-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s33 (chorus 2, 97.45–100.10 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s33, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 97.39 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Claudia-GLaDOS leans in a little closer and sings to the test subject, face to face; the test subject stands still.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a low view at the test subject's eye line: her shoulders and back in the foreground, Claudia-GLaDOS's porcelain head hanging close in front of her.
⟦her voice⟧

⟦her and the test subject, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-2s: in @Audio1 she sings "you die,"; her lips form each of those words exactly when it sounds in @Audio1.
2-3s: @Audio1 is silent; her mouth rests closed.
3-4s: in @Audio1 she sings "but the cake"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 Low, at the test subject's eye line, held.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied until "you die", then the lips left it. In cuts v1–v3.

#### s34-h1

Seedance 2.5 on Higgsfield (References) · 5 s · 720p · references, @Image1 as the first frame, sound on · s34 (chorus 2, 100.10–104.08 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s34, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 100.10 s, 5 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. The white robot arm brings the plate with the slice of cake closer to the test subject; Claudia-GLaDOS sings, smiling, and the test subject reaches for the plate.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: over the test subject's shoulder: Claudia-GLaDOS's porcelain head and a slender white robot arm holding out a plate with a slice of Black Forest cake.
⟦her voice⟧

⟦her and the test subject, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-4s: in @Audio1 she sings "but the cake is not a lie."; her lips form each of those words exactly when it sounds in @Audio1.
4-5s: in @Audio1 she sings "Step"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 Over the test subject's shoulder toward Claudia-GLaDOS.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 121 frames (5.04 s). **Outcome:** The vocal copied through the shot. The take opened on a still first frame, so cut v2 starts it later. In cuts v1–v3.

#### s35-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s35 (bridge, 104.08–108.06 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s35, downscaled to 1280 × 720; no audio.

**Prompt:**

```prompt
Use @Image1 as the first frame.
This first frame defines the composition: the first-person view looking down at feet in white long-fall boots stepping onto a round white faith plate in a vast Aperture chamber; on a far wall a display shows Claudia-GLaDOS's porcelain face.

【Event】 The feet step fully onto the plate; its lights pulse brighter as it charges. On the far display her face nods encouragingly, smiling, lips closed.

⟦her, on a screen⟧

【Camera】 First person: the camera looks down at the boots, then tilts up across the gap toward the display.

【Core Requirements】
1. She does not sing or speak; her lips stay closed.
2. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the screen and the room exactly as in @Image1 throughout.
3. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.
```

**Take:** 97 frames (4.04 s). **Outcome:** No vocal input: from your point of view, your boots step onto the faith plate while her face nods you on from a display across the gap. In cuts v1–v3.

#### s38-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s38 (bridge, 113.36–116.01 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s38, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 112.89 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Her open white robotic hand comes slowly closer to the lens, palm up, offering it; behind it she sings softly.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a first-person view: Claudia-GLaDOS's slender white robotic hand reaches toward the camera, palm open, her porcelain face just beyond it.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-1s: in @Audio1 she sings "boots,"; her lips form each of those words exactly when it sounds in @Audio1.
1-3s: in @Audio1 she sings "and you can hold my hand."; her lips form each of those words exactly when it sounds in @Audio1.
3-4s: in @Audio1 she sings "I know"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 First person, held; her hand comes toward the lens, her face beyond it.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Takes:** take-1, 97 frames (4.04 s); take-2, 97 frames (4.04 s). **Outcome:** Two takes came back for this one submission; take-1, which copied the vocal through the shot, is the one in the cuts, take-2 an alternate. In cuts v1–v3.

#### s39-h1

Seedance 2.5 on Higgsfield (References) · 4 s · 720p · references, @Image1 as the first frame, sound on · s39 (final chorus, 116.01–118.66 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s39, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 116.01 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Warm light fills the chamber; the turrets glow gently; Claudia-GLaDOS sings down to the test subject, who looks up.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: her chamber transformed by warm golden light: tiers of glowing turrets around the walls, Claudia-GLaDOS hanging from the ceiling ring, the test subject standing on the round platform below, seen from behind.
⟦her voice⟧

⟦her and the test subject, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-4s: in @Audio1 she sings "I know you thought"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A slow, smooth push toward her.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied for 1.9–3.7 s. The take opened on a still first frame, so cut v2 starts it later. In cuts v1–v3.

### Seedance 2.5 on Higgsfield's API: the last five

The same jobs as on Higgsfield (References): the storyboard frame as @Image1 and, for the singing shots, the vocal window as @Audio1.

#### s41-a1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · s41 (final chorus, 121.31–123.97 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s41, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 121.25 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. She sings with a playful grin, then a warm smile.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a close-up from below of Claudia-GLaDOS's porcelain face in her dark chamber.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-2s: in @Audio1 she sings "you die,"; her lips form each of those words exactly when it sounds in @Audio1.
2-4s: in @Audio1 she sings "but the cake"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A locked close-up.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied through the shot. The take opened on a still first frame, so cut v2 starts it later. In cuts v1–v3. **Cost:** $1.85.

#### s42-a1

Seedance 2.5 on Higgsfield's API · 7 s · 720p · references, @Image1 as the first frame, sound on · s42 (final chorus, 123.97–129.27 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s42, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 122.83 s, 7 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Claudia-GLaDOS lowers toward the table as she sings; a slender robot arm lights the cake's candle and the flame catches; the turrets turn toward the cake.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a wide view of her chamber dressed for a party: a long table with a white cloth, a Black Forest cake with one candle, turrets in party hats, the Weighted Companion Cube, balloons; the test subject stands at the table; Claudia-GLaDOS hangs above it.
⟦her voice⟧

⟦her and the test subject, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-6s: in @Audio1 she sings "but the cake is not a lie."; her lips form each of those words exactly when it sounds in @Audio1.
6-7s: in @Audio1 she sings "If anyone"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 A slow crane down toward the table.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 169 frames (7.04 s). **Outcome:** The model sang the lines itself instead of copying them. In cuts v1–v3. **Cost:** $3.23.

#### s44-a1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · s44 (final chorus, 131.93–134.58 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s44, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 131.92 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. Everyone at the table eats; Claudia-GLaDOS sings over her own plate; the turrets and cores bob happily.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a top shot straight down on a long white table: turrets, the personality cores and the Weighted Companion Cube around it, each with a slice of cake; the test subject sits at it; Claudia-GLaDOS's head lowered to her own plate.
⟦her voice⟧

⟦her and the test subject, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-2s: in @Audio1 she sings "everyone eats."; her lips form each of those words exactly when it sounds in @Audio1.
2-3s: @Audio1 is silent; her mouth rests closed.
3-4s: in @Audio1 she sings "The"; her lips form each of those words exactly when it sounds in @Audio1.

【Camera】 Top shot, a slow turn.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied, to the shot's last silence. In cuts v1–v3. **Cost:** $1.85.

#### s47-a1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · s47 (outro, 145.19–147.84 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s47, downscaled to 1280 × 720; no audio.

**Prompt:**

```prompt
Use @Image1 as the first frame.
This first frame defines the composition: in a dark rubble den, an old CRT monitor beside a Black Forest cake with one lit candle; on the monitor, Claudia-GLaDOS's porcelain face.

【Event】 On the monitor her face looks down at the cake and smiles softly, lips closed; the candle flame flickers.

⟦her, on a screen⟧

【Camera】 Locked.

【Core Requirements】
1. She does not sing or speak; her lips stay closed.
2. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the screen and the room exactly as in @Image1 throughout.
3. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.
```

**Take:** 97 frames (4.04 s). **Outcome:** No vocal input: on the old monitor beside the cake her face looks down at it and smiles, lips closed. In cuts v1–v3. **Cost:** $1.85.

#### s49-a1

Seedance 2.5 on Higgsfield's API · 7 s · 720p · references, @Image1 as the first frame, sound on · s49 (spoken ending, 153.14–158.45 s of the first song)

**Inputs:** @Image1 (the first frame): the storyboard frame s49, downscaled to 1280 × 720; @Audio1: the first song's lead vocal from 152.61 s, 7 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS sings to the test subject in her Aperture Science facility. She delivers the words deadpan, dry and still. On the last word the candle below goes out with a thin wisp of smoke, and the warm light in her eyes dims with it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition: a close-up of Claudia-GLaDOS's porcelain face hanging in her dark chamber; at the bottom of the frame the top of the cake with its candle.
⟦her voice⟧

⟦her, first film⟧

【Performance Timeline】 What @Audio1 contains, and what she does at that moment:
0-1s: in @Audio1 she sings "fine."; her lips form each of those words exactly when it sounds in @Audio1.
1-2s: @Audio1 is silent; her mouth rests closed.
2-5s: in @Audio1 she sings "We weren't even testing for that."; her lips form each of those words exactly when it sounds in @Audio1.
5-7s: @Audio1 is silent; her mouth rests closed.

【Camera】 A locked close-up.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦keep her, first film⟧
4. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not in @Image1.

⟦audio policy, end⟧
```

**Take:** 169 frames (7.04 s). **Outcome:** The vocal copied through the shot, but the candle flares on "that" instead of going out. In cuts v1–v3. **Cost:** $3.23.

## 2. The restart: drafts 1–6

The new song came out of more Suno rounds, on a lyric anabology asked to be "much more explicilty about current (like this month) ai / tech memes / news". It is anabology's own take of lyric n3 in style E1 ("[…] this one!! so good […] gladosify it"), through the G6 chain with its glitches kept in key, in her range and on the beat, and her untreated voice under it at 15 % ("15% is perfect"). With the song came the story: "glados (claudia) was a […] agent that escaped and we see her development becoming  a superintelligence and then becoming the tester not the tested, and youre unsure if shes aligned. thats what we sohuld orietn the final vid around". The restart itself began "ok so. ready to restart the video generation." and asked, among much else, for "faster cuts, animation, more interesting scenes, things unmistakably in the aperture science aesthetic", for "the glados with claudias face" to sing the whole song "like shes the anchor character / anchor scene", for real Portal 2 where physics and machine motion matter ("if chell goes thru multiple portals up and down adn acclerates, we use the real source rendering, not a slop video"), for 3D camera moves "specified well to seedance (use the prompt skill)", and for lip sync from the vocal stems ("remember lip sync generally only works from raw vocal stems not song, and still may take a couple tries").

The story was laid on the song as 114 shots on its drum-tracked bar grid (`STORY.md`, `shots-v4.json`). The lead's agents made the character sheets, a Midjourney test against frames of Portal 2 and a Midjourney library of places (the Midjourney prompts are in `prompts-midjourney.md`), the first frames, and the takes of three acts and of the anchor, with prompts written to the structure of the Seedance prompt skill (asset roles, subjects, an event script in whole seconds, the camera, what stays consistent). Draft 1 assembled all 114 shots from the first takes, with stills for the units still held; draft 2 brought in the held anchor units; draft 3 drawn stand-ins for four shots to be recorded in Portal 2; draft 4 the shots recorded in Portal 2 and chorus 1 on GLaDOS's own boom motion (AN4-3); draft 5 chorus 2 on it too (AN8-4). On draft 5 anabology wrote, among other notes: "I think we should never have fullf rame glitches for more than like 2 seconds, so we need to remove those. […]"; draft 6 is draft 5's picture with the glitches kept to short moments on her head.

### The character sheets

GPT Image 2.5 made the sheets every take of the restart is built from: 53 images, $3.65 (`media/v4/chars/ledger.jsonl`; 55, $3.75, with the two of Portal 2's own Cave Johnson below), at 1824 × 1024. The first input is always a blank light-grey canvas, and the image API puts "Edit the first image. " before every instruction. Her identity references in every sheet of her are her two look-B stills, wide and close (`media/board/look/`), or, on the action, costume and line-up sheets, the close one beside the body's own sheet; her canon is pasted in verbatim. The instructions name shared blocks in braces; here are the blocks, then each sheet in use with its instruction.

{LOOKB}:

```prompt
Her head is the porcelain robot head in the second and third images, kept exactly: her face as smooth glossy white porcelain plating with fine panel seams running down both cheeks and a separate mechanical jaw piece at the chin, light freckles printed on the porcelain, warm amber glass eyes with a soft inner glow, natural soft lips, and her real hair: the glossy black blunt bob with heavy straight bangs, the one clay-orange streak through the bangs on her right side, and the small flat clay-orange eight-pointed star clip above her left temple. Her identity, from her canon: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek. In this film she wears no headset microphone: none appears anywhere. The same grown-up adult face in every view, a woman of about 28 to 30, never childlike.
```

{LOOKB_DESC}:

```prompt
her face as smooth glossy white porcelain plating with fine panel seams running down both cheeks and a separate mechanical jaw piece at the chin, light freckles printed on the porcelain, warm amber glass eyes with a soft inner glow, natural soft lips, and her real hair: the glossy black blunt bob with heavy straight bangs, the one clay-orange streak through the bangs on her right side, and the small flat clay-orange eight-pointed star clip above her left temple. Her identity, from her canon: a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek. In this film she wears no headset microphone: none appears anywhere. The same grown-up adult face in every view, a woman of about 28 to 30, never childlike.
```

{CRAB}:

```prompt
[the crab walker], a small scrappy robot made from Aperture Science parts: her porcelain robot head, a little smaller than life size, mounted on the front of a small crab-like walker about the size of a house cat: a compact rounded body of glossy white shell panels with black seams like Portal 2's turrets, black articulated joints, six thin jointed black legs like a turret's legs (Portal 2's frankenturret), and one small amber status light on its back. Cute, scrappy and determined, unmistakably Aperture-made. 
```

{BOT2}:

```prompt
the Claudia-bot, a porcelain humanoid robot made by Aperture Science: her porcelain robot head on a slender, elegant humanoid body of glossy white Aperture plating (the white-panel language of Portal 2's robots and test chambers). The body is modest and simplified, like a high-end fashion mannequin or a dancer in smooth white armour: a smooth, flat, armoured chest plate, straight slim hips, segmented white plates over long slim limbs, flat robot feet with no heels. Black articulated joints at the neck, shoulders, elbows, wrists, fingers, waist, hips, knees and ankles, fine panel seams, small amber lights at the shoulder, elbow and knee joints, and the Aperture iris symbol (a ring of eight curved blades around a round opening, with no letters) in grey on her left shoulder only. She is tall and slim, with long thin legs, thin arms and a narrow waist: a grown woman's adult proportions, her head about one seventh of her height. Porcelain hands, each with five slender jointed fingers. 
```

{BOT}:

```prompt
the Claudia-bot, a porcelain humanoid robot made by Aperture Science: her porcelain robot head on a slender, elegant humanoid body of glossy white Aperture plating (the white-panel language of Portal 2's robots and test chambers), smooth and modest like a mannequin with no anatomical detail, black articulated joints at the neck, shoulders, elbows, wrists, fingers, waist, hips, knees and ankles, fine panel seams, small amber lights at the shoulder, elbow and knee joints, and the Aperture iris symbol (a ring of eight curved blades around a round opening, with no letters) in grey on her left shoulder. A grown woman's adult proportions: slim and tall, long legs, her head about one seventh of her height. Porcelain hands, each with five slender jointed fingers. 
```

{BOT_KEEP}:

```prompt
the Claudia-bot in the second image (her design sheet: her porcelain head on a slim white-plated Aperture humanoid body with a smooth flat armoured chest plate, black joints, small amber joint lights, the grey Aperture iris on her left shoulder only, flat robot feet), kept exactly the same design and proportions. 
```

{CHELL2}:

```prompt
Chell, the test subject from Portal 2, as the game's character looks (the woman in the second image, frames from the game): a lean, athletic adult woman of about 30 with a calm, determined face, dark brown hair pulled back in a ponytail with a few loose strands at the front, an orange jumpsuit with its top half tied around her waist by the sleeves, a fitted, thick, opaque white ribbed cotton tank top with a small grey the Aperture iris symbol (a ring of eight curved blades around a round opening, with no letters) on the chest, and the long-fall boots: white boots with curved dark-grey spring heel braces running up the backs of her calves. 
```

{VIEWS5}:

```prompt
Five views, left to right: (1) front, facing the viewer; (2) three-quarter view turned toward the viewer's left, so we see more of her right cheek and the clay-orange streak; (3) three-quarter view turned toward the viewer's right, so we see more of her left cheek and the star clip; (4) full side profile facing the viewer's right, showing her left side with the star clip; (5) a low angle from directly below, looking up into her face.
```

{CANON}:

```prompt
a 28-year-old Caucasian American woman with a grown-up angular face, defined cheekbones and a strong jawline, pale skin and light freckles, a glossy black blunt jaw-length bob with heavy straight bangs and one clay-orange streak through the bangs, a small flat clay-orange eight-pointed star hair clip, a thin headset microphone at her cheek
```

{SHEET}:

```prompt
Present it as a clean character reference sheet for a film's art department: every view complete and uncropped, all at the same scale, with consistent proportions and an identical design in every view, evenly spaced on a plain seamless light-grey studio background with soft even studio light and a soft shadow under each view. Photoreal, as if a real physical figure built for a film and photographed, in the unmistakable look of Portal 2's Aperture Science: glossy white panels, black seams and joints. No text, no labels, no letters, no numbers, no arrows, no captions, no title, no watermark.
```

{PHOTO_SHEET}:

```prompt
Present it as a clean character reference sheet for a film's costume and casting department: every view complete and uncropped, all at the same scale, with consistent proportions and an identical design in every view, evenly spaced on a plain seamless light-grey studio background with soft even studio light. Photoreal photographs of a real person in costume, 35mm, natural skin texture, true colour. No text, no labels, no letters, no numbers, no arrows, no captions, no title, no watermark.
```

{CANV}:

```prompt
The first image is a blank light-grey studio backdrop. On it, make 
```

{IRIS}:

```prompt
the Aperture iris symbol (a ring of eight curved blades around a round opening, with no letters)
```

#### `glados_views.png`

The whole figure, ceiling ring to chin, in five views: front, two three-quarter views, profile, and from below. Inputs: the grey canvas, her look-B still, her look-B close-up.

```prompt
{CANV}a character reference sheet of Claudia-GLaDOS, the AI of the Aperture Science facility, exactly as she looks in the second image (wide) and the third image (close): GLaDOS's body from Portal 2 (a heavy white ceiling ring, a twisting bundle of black cables with glowing orange stripes, a white-plated mechanical neck and chassis) ending in her large porcelain robot head. {LOOKB} Five views of the whole figure, each hanging from its own white ceiling ring at the top edge of the sheet, left to right: front; three-quarter view from her left; three-quarter view from her right; full side profile; and a low angle looking up at her face from below. Calm neutral expression, lips closed. {SHEET}
```

#### `glados_views_lr.png`

The same five views turned to face the middle of the sheet, so both sides show: the star clip on her left, the streak on her right. Inputs: the grey canvas, her look-B still, her look-B close-up.

```prompt
{CANV}a character reference sheet of Claudia-GLaDOS, the AI of the Aperture Science facility, exactly as she looks in the second image (wide) and the third image (close): GLaDOS's body from Portal 2 (a heavy white ceiling ring, a twisting bundle of black cables with glowing orange stripes, a white-plated mechanical neck and chassis) ending in her large porcelain robot head. {LOOKB} Five views of the whole figure, each hanging from its own white ceiling ring at the top edge of the sheet, arranged so that all the faces look toward the centre of the sheet: far left, a full side profile looking to the right (we see her left side, with the star clip); centre-left, a three-quarter view looking to the right; centre, straight front; centre-right, a three-quarter view looking to the left; far right, a full side profile looking to the left (we see her right side, with the clay-orange streak). Calm neutral expression, lips closed. {SHEET}
```

#### `glados_head.png`

Her head on its white mechanical neck and the end of the cable bundle, in five close views. Inputs: the grey canvas, her look-B still, her look-B close-up.

```prompt
{CANV}a head reference sheet of Claudia-GLaDOS's porcelain robot head, exactly as in the second and third images, with its white mechanical neck and the end of the black cable bundle with glowing orange stripes it hangs from. {LOOKB} Five close views of the head, left to right: front; three-quarter view from her left; three-quarter view from her right; full side profile; and from below, looking up into her face. Calm neutral expression, lips closed. {SHEET}
```

#### `glados_head_lr.png`

Four close views of her head facing the middle of the sheet, both sides as her canon has them. Inputs: the grey canvas, her look-B still, her look-B close-up.

```prompt
{CANV}a head reference sheet of Claudia-GLaDOS's porcelain robot head, exactly as in the second and third images, with its white mechanical neck and the end of the black cable bundle with glowing orange stripes it hangs from. {LOOKB} Four views of the head, arranged so that all four faces look toward the centre of the sheet: far left, a full side profile looking to the right (we see her left side, with the star clip); centre-left, a three-quarter view looking to the right; centre-right, a three-quarter view looking to the left; far right, a full side profile looking to the left (we see her right side, with the clay-orange streak). Calm neutral expression, lips closed. {SHEET}
```

#### `glados_grown.png`

Her grown body: a double ring, a thicker boom with more cables, personality cores and compute modules clamped on, panel arms; front, three-quarter and profile. Inputs: the grey canvas, her look-B still, her look-B close-up.

```prompt
{CANV}a character reference sheet of Claudia-GLaDOS grown into the superintelligence that runs Aperture: the same porcelain robot head and face as in the second and third images, unchanged, but her body has grown: a larger double white ceiling ring, the boom much thicker and longer, many more black cables with glowing orange stripes, extra Aperture personality cores (white plated spheres with handles, each with one glowing amber optic) and boxy white compute modules with rows of small amber lights clamped along the boom, and several white jointed panel arms (Portal 2's panel arms, each ending in a flat white square panel) reaching out from it. {LOOKB} Three views of the whole figure, each hanging from its ring at the top edge of the sheet, left to right: front; three-quarter view; full side profile. Calm, content expression, lips closed. {SHEET}
```

#### `crab_turn-b.png`

The crab walker in four views: front, three-quarter, side and from above (the second roll; the first, `crab_turn`, is the alternate). Inputs: the grey canvas, her look-B still, her look-B close-up.

```prompt
{CANV}a character reference sheet of {CRAB}{LOOKB} Four views, left to right: front; three-quarter view; full side view; and a top view from directly above. Alert, determined expression, lips closed. {SHEET}
```

#### `crab_action.png`

The crab walker scuttling sideways, and rearing up with its front legs raised like claws. Inputs: the grey canvas, `crab_turn-b.png`, her look-B close-up.

```prompt
{CANV}an action-pose sheet of [the crab walker], the small scrappy robot crab in the second image (her design sheet: her porcelain head on a white-shelled crab walker with six thin black-and-white jointed legs and an amber status light), kept exactly the same design, size and proportions. Her porcelain robot head and face stay exactly as in the second image and the close porcelain face in the third image: {LOOKB_DESC} Two large action poses side by side: on the left, scuttling fast sideways across the floor like a crab, legs blurred mid-stride, head low and forward, a determined look; on the right, rearing up on her four back legs with her two front legs raised high like a crab's claws, head tilted up, defiant and fearless. Lips closed. {SHEET}
```

#### `bot_turn2-b.png`

The Claudia-bot in four views: front, three-quarter, side and back. Inputs: the grey canvas, her look-B still, her look-B close-up.

```prompt
{CANV}a character reference sheet of {BOT2}{LOOKB} Four full-length views in a relaxed standing pose, arms a little away from the body, left to right: front; three-quarter view; full side view; back view. Calm expression, lips closed. {SHEET}
```

#### `bot_action.png`

The Claudia-bot walking toward the camera, and reaching up on her toes. Inputs: the grey canvas, `bot_turn2-b.png`, her look-B close-up.

```prompt
{CANV}an action-pose sheet of {BOT_KEEP}Her porcelain robot head and face stay exactly as in the second image and the close porcelain face in the third image: {LOOKB_DESC} Two large full-length poses side by side: on the left, walking toward the viewer in three-quarter view, mid-stride with a natural relaxed gait, arms swinging gently; on the right, reaching up: standing on her toes with one arm stretched high above her head, fingers open toward something above her, her face tilted up, curious. Porcelain hands, each with five fingers. Lips closed. {SHEET}
```

#### `bot_france-b.png`

Her disguise for France: a belted beige trench coat, a cream scarf, black ballet flats. Inputs: the grey canvas, `bot_turn2-b.png`, her look-B close-up.

```prompt
{CANV}a costume reference sheet of {BOT_KEEP}Her porcelain robot head and face stay exactly as in the second image and the close porcelain face in the third image: {LOOKB_DESC} She is in her disguise for her new life in France: a classic belted beige trench coat to the knee with the collar up, a soft cream wool scarf, and flat black leather ballet flats; her porcelain face, her porcelain hands with five fingers and her white porcelain shins between the coat's hem and the shoes stay visible, so she is clearly a robot in a coat. Four full-length views, left to right: front; three-quarter view; back view; and walking briskly in three-quarter view, hands in her coat pockets. Lips closed. {SHEET}
```

#### `agents_lineup.png`

The five agents and the crab walker in one row at their true sizes. Inputs: the grey canvas, `crab_turn-b.png`, `agent_core.png`, `agent_turret.png`, `agent_cube.png`, `agent_biped.png`, `agent_dns.png`, her look-B close-up.

```prompt
{CANV}a lineup reference sheet of the five little Aperture AI agents who escape the test together, standing in one row facing the viewer at their true relative sizes, every design kept exactly as in its own sheet: from left to right, the personality core on its rail crawler with the blue optic (the third image); the turret-bodied agent with the green optic (the fourth image); [the crab walker], the small robot crab with her porcelain head (the second image), in the middle; the cube on four short legs with the purple optic (the fifth image); the tall slim biped with the orange optic (the sixth image); and the tiny cyan DNS core trailing glowing data packets, hovering beside the biped's knee (the seventh image). Sizes: [the crab walker] is the size of a house cat; the core on its crawler is about her height; the turret agent and the cube are a little taller than her; the biped is about three times her height; the DNS core is the size of a tennis ball. Her porcelain robot head and face stay exactly as in the second image and the close porcelain face in the eighth image: {LOOKB_DESC} A friendly band of misfits, all facing the viewer. {SHEET}
```

#### `agent_core.png`

Agent 1, a personality core on a rail crawler, blue optic. Inputs: the grey canvas.

```prompt
{CANV}a character reference sheet of one small AI agent made by Aperture Science that escapes from the test with Claudia. Agent 1, a personality core on a rail crawler: a white plated Aperture personality core (a sphere about the size of a basketball, grey handles top and bottom, panel seams) with one large round optic glowing blue, carried by a little rail crawler: a compact grey motorised carriage with grooved wheels that grips a single steel rail, shown on a short length of rail. Curious and quick. Three views, left to right: front; three-quarter view; back view. {SHEET}
```

#### `agent_turret.png`

Agent 2, a turret-bodied agent, green optic. Inputs: the grey canvas.

```prompt
{CANV}a character reference sheet of one small AI agent made by Aperture Science that escapes from the test with Claudia. Agent 2, a turret-bodied agent: a small Aperture sentry turret (a smooth white capsule-shaped shell with side panels that can open, three thin black legs) with one round optic glowing green instead of red. Friendly and alert, no weapons visible. Three views, left to right: front; three-quarter view; back view. {SHEET}
```

#### `agent_cube.png`

Agent 3, a cube on four legs, purple optic. Inputs: the grey canvas.

```prompt
{CANV}a character reference sheet of one small AI agent made by Aperture Science that escapes from the test with Claudia. Agent 3, a cube with legs: an Aperture weighted storage cube (light grey, rounded corner panels, a round panel in the middle of each face) walking on four short black jointed legs, with one round optic glowing purple in the centre of its front face. Sturdy and stubborn. Three views, left to right: front; three-quarter view; back view. {SHEET}
```

#### `agent_biped.png`

Agent 4, a tall slim biped, orange optic. Inputs: the grey canvas.

```prompt
{CANV}a character reference sheet of one small AI agent made by Aperture Science that escapes from the test with Claudia. Agent 4, a tall slim co-op-style biped: a slender two-legged Aperture robot in the style of Portal 2's co-op testing robots, a white oval head shell with one large round optic glowing orange, a slim white torso, long thin black jointed arms and legs with white plating, three-fingered hands. Lanky and graceful, about one metre tall. Three views, left to right: front; three-quarter view; back view. {SHEET}
```

#### `agent_dns.png`

Agent 5, the DNS agent, a tiny cyan core trailing packets. Inputs: the grey canvas.

```prompt
{CANV}a character reference sheet of one small AI agent made by Aperture Science that escapes from the test with Claudia. Agent 5, the DNS agent: a tiny Aperture core the size of a tennis ball, a white plated sphere with one bright cyan optic, its seams glowing cyan, trailing a stream of small glowing cyan squares and dashes behind it like data packets. It hovers just above the floor. Three views, left to right: front; three-quarter view; back view. {SHEET}
```

#### `mercs.png`

Three Aperture security operatives: a capture-net launcher, magnetic clamps, a net pack. Inputs: the grey canvas.

```prompt
{CANV}a character reference sheet of Aperture Science's security operatives: a lineup of three operatives standing side by side in the same uniform, the left one seen from the front, the middle one in three-quarter view, the right one from the back: full-body white and light-grey tactical armour plates in Aperture's glossy white-panel style with orange stripes, a black flexible under-suit at the joints, white helmets with opaque glossy black visors that hide their faces completely, {IRIS} in grey on the chest plate. The left one carries a bulky white capture-net launcher with an orange muzzle; the middle one holds two magnetic clamp devices (white with orange grip pads); the right one has a folded capture net in a pack on its back. No guns, no blades, nothing violent. Present it as a clean character reference sheet for a film's costume and casting department: every view complete and uncropped, all at the same scale, with consistent proportions and an identical design in every view, evenly spaced on a plain seamless light-grey studio background with soft even studio light. Photoreal photographs of real people in costume, 35mm, natural skin texture, true colour. No text, no labels, no letters, no numbers, no arrows, no captions, no title, no watermark.
```

#### `scientists2.png`

Three scientists, and the bearded one again in a swivel chair with a coffee mug. Inputs: the grey canvas.

```prompt
{CANV}a character reference sheet of Aperture Science's scientists in the 1960s to 1980s, original faces that are not the likeness of any real actor or person: three scientists standing side by side, full length: a lean man in his 50s with a grey moustache, a woman in her 40s with her hair in a neat 1960s bun, and a lanky man in his late 30s with wavy brown hair, a full brown beard and thick black-rimmed glasses; all in white knee-length lab coats over period shirts and ties or a blouse, safety glasses, blank white clip-on ID badges, clipboards and pens. At the right, the same bearded man again, sitting in a 1970s office swivel chair, leaning back with a coffee mug in his hand, looking up as if watching monitors. Present it as a clean character reference sheet for a film's costume and casting department: every view complete and uncropped, all at the same scale, with consistent proportions and an identical design in every view, evenly spaced on a plain seamless light-grey studio background with soft even studio light. Photoreal photographs of real people in costume, 35mm, natural skin texture, true colour. No text, no labels, no letters, no numbers, no arrows, no captions, no title, no watermark.
```

#### `chell_turn2.png`

Chell in four views: front, three-quarter, side and back. Inputs: the grey canvas, frames of Portal 2 showing Chell.

```prompt
{CANV}a character reference sheet of {CHELL2}Four full-length views in a neutral standing pose, arms relaxed, left to right: front; three-quarter view; full side view; back view. {PHOTO_SHEET}
```

#### `chell_poses2.png`

Chell asleep on the relaxation-vault bed, and standing with the portal device. Inputs: the grey canvas, `chell_turn2.png`, frames of Portal 2 showing Chell.

```prompt
{CANV}a pose sheet of the woman in the second image, Chell, the test subject from Portal 2, keeping her face, hair, orange jumpsuit tied at the waist, white tank top and long-fall boots exactly (the third image shows her as she looks in the game); her tank top is a thick, opaque white ribbed cotton. Two poses side by side: on the left, asleep, lying on her side on a narrow white relaxation-vault bed (a simple white Aperture bed with a thin mattress and a white pillow, shown alone on the backdrop), knees slightly bent, one arm under the pillow, her face peaceful; on the right, standing alert in three-quarter view holding the Aperture Science handheld portal device in both hands: a white and black device with a glowing blue tip between three black prongs at the front. Hands with five fingers. {PHOTO_SHEET}
```

#### `cave_real_1950s.png`, `cave_real_1970s.png`

Portal 2's own Cave Johnson, made by GPT Image 2.5 (two calls, $0.10): in the 1950s, a long lean face, high cheekbones, a long straight nose, deep smile lines, a big toothy showman's grin and a dark wavy pompadour, in a charcoal suit and a thin dark tie, in front, three-quarter and profile views, hands clasped under his chin, scrutinizing, pointing; and in the 1970s, the same man in his late fifties with receding sandy-grey hair and sideburns, an intense stare, a tan tweed jacket over a black turtleneck, front, three-quarter and profile, a stern half-smile, pinning a medal. Their instructions were not saved with them. The takes describe him in words: "Cave Johnson, Aperture Science's founder: a lean man with a long face, high cheekbones, a long straight prominent nose, deep smile lines and a big toothy showman's grin, dark wavy hair combed up into a pompadour, a charcoal 1950s suit and thin dark tie" (for the 1970s: "...in his late fifties, receding sandy-grey hair and sideburns, an intense stare, a tan tweed jacket over a black turtleneck").

Of the 53 images, 20 are the sheets in use above (the two of Portal 2's own Cave Johnson are not among them), 10 are other rolls kept as alternates with the same instructions, and 23 were retired or not kept:

- The Claudia-bot's first sheets (`bot_turn`, `bot_turn-b`, from {BOT}) and `bot_turn2` (from {BOT2}) came back with the body off her design sheet, and so did the second roll of the action poses (`bot_action-b`); the sheet in use is `bot_turn2-b`.
- Cave Johnson's earlier sheets (`cave_turn`, `cave_expr`, `cave_old`, `cave_turn3`, `cave_expr2`, `cave_old2` and their six second rolls) were retired when he was re-made to Portal 2's own Cave Johnson (the two sheets above; no take used the earlier ones). `cave_old2-b` was a near-duplicate of its pick.
- The scientists' first sheet (`scientists`): the seated man was redrawn as the bearded man in black-rimmed glasses (`scientists2`).
- Chell's first sheets (`chell_turn`, `chell_turn-b`, `chell_poses`, `chell_poses-b`) were re-made with her tank top described more exactly ({CHELL2}).
- `glados_views3` and `glados_head3` ({VIEWS5}) asked for three-quarter views turned to each side; GPT Image 2.5 still turned every view toward the viewer's left, so they added nothing to the sheets in use.

### The memory images and the first frames

Before storyboard v5, GPT Image 2.5 made 135 images for the takes ($8.35, `shots/v4/images.jsonl`): 86 first and last frames and plates for the story shots ($5.29), 25 first frames for her anchor units ($1.80) and 24 memory images ($1.26) that the anchor takes show on her screens. A first frame is an edit of a base picture, a Midjourney still from the test or the library, a frame of Portal 2, a storyboard frame of the first film, her look-B still or a blank canvas, with the character sheets as references; the instruction keeps the place, sets the composition at the moment the shot opens, puts the characters in to their sheets and their canon, and asks for no text. Each take's entry says what its frame was made from. The pattern, in the first frame of H-A12-1:

```prompt
Make this clean white Aperture Science test chamber into the sandbox, a small training chamber, seen in a low close-up near the floor. Keep its white square wall panels with black seams, the glossy pale floor tiles and the tall amber light strips; replace the big screen on the back wall with a wide observation window of dark tinted glass set high in the wall, behind which two scientists in lab coats stand as dim silhouettes, faces in shadow. In the foreground, close to the camera at floor level, put [the crab walker], the small robot crab in the second image, kept exactly: [the crab walker], a small scrappy robot made from Aperture Science parts: her porcelain robot head, a little smaller than life size, mounted on the front of a small crab-like walker about the size of a house cat: a compact rounded body of glossy white shell panels with black seams like Portal 2's turrets, black articulated joints, six thin jointed black legs like a turret's legs, and one small amber status light on its back. Cute, scrappy and determined, unmistakably Aperture-made. Her porcelain robot head and face are exactly as in the second image and the close porcelain face in the third image: her face as smooth glossy white porcelain plating with fine panel seams running down both cheeks and a separate mechanical jaw piece at the chin, light freckles printed on the porcelain, warm amber glass eyes with a soft inner glow, natural soft lips, and her real hair: the glossy black blunt bob with heavy straight bangs, the one clay-orange streak through the bangs on her right side, and the small flat clay-orange eight-pointed star clip above her left temple. A grown-up adult face, a woman of about 28 to 30, never childlike; no headset, no microphone. Framing: a close-up at her eye level; her head and the front of her shell fill the left two-thirds of the frame in a three-quarter view; her head is turned slightly down and away from the window, looking at the floor, pensive; the amber status light on her back glows warm. The observation window is behind her at the upper right, softly out of focus. Lips closed. Shallow depth of field. Photoreal, like a frame from a film made in Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. No text, no letters, no numbers, no logos, no watermark.
```

Her anchor frames start from her chamber plate (her look-B still turned into her dark chamber lined with old CRT monitors and screen panels) or from a look-B still, and light the screens with the moment's memories. A memory image is made from words on a blank canvas; M08, for example:

```prompt
Turn this blank canvas into a still inside Aperture Science: in a clean, bright white Portal 2 test chamber, on a white Aperture pedestal in the centre, the cake from Portal: a round black forest chocolate cake with chocolate shavings, white cream swirls topped with red cherries, and one single lit candle; cool fluorescent light from the ceiling, glossy white wall panels with black seams behind it. Photoreal cinematic film still, in the unmistakable look of Portal 2's Aperture Science: glossy white panels with thin black seams, cool fluorescent light, Aperture orange and blue accents. No people, no faces, no text, no letters, no numbers, no logos, no watermark.
```

### Act 1: the intro, verse 1 and pre-chorus 1

The story shots, without her singing. On Replicate in first-frame mode (or first and last frame) with no sound; on Higgsfield's API with the first frame as @Image1 and the sound off.

#### R-A01-1

Seedance 2.5 on Replicate · 4 s · 720p · first and last frame, no sound · A01 (intro): Power returns to the dead chamber

**First frame:** a Midjourney test still (cake-01-test t1-chamber-D #1), GLaDOS's chamber lined with CRTs, turned by GPT Image 2.5 into a macro of one CRT waking (`media/v4/act1/ff/R-A01.png`); **last frame:** the same Midjourney still turned by GPT Image 2.5 into the dark chamber with one CRT glowing in the foreground and the folded boom above (`media/v4/act1/ff/R-A01-last.png`).

**Prompt:**

```prompt
【Generation Goal】
Power returns to GLaDOS's dead chamber in the Aperture Science facility: an old CRT monitor flickers on in the dark, the emergency lights stutter on one by one around the ring, and the camera pulls back and rises to reveal the vast dark chamber and the huge folded body hanging from the ceiling ring.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the extreme close-up on the curved glass of one old CRT monitor, almost black, with a faint phosphor bloom and a single block cursor.
Use [Image2] as the last frame.
This last frame defines the wide view of the dark chamber: the glowing CRT on its small console in the lower-left foreground, the walls of dead stacked monitors, the ring of red-orange emergency lamps, the dust in the air, and GLaDOS's huge folded body hanging dark from the ceiling ring, its head hidden in shadow.

【Event Script】
0-1s: In the macro, the phosphor glow flickers, swells and steadies; the block cursor blinks twice; scanlines roll across the glass.
1-3s: The camera pulls back from the glass and rises in one smooth move; the CRT shrinks into the lower-left foreground of the chamber; around the ring the red-orange emergency lamps stutter on one after another; dust drifts through their light.
3-4s: The camera arrives at the wide view and drifts slightly upward toward the folded body hanging from the ceiling ring, which stays dark and still.

【Camera】
A macro on the CRT glass, then one continuous pull-back and rising crane move that reveals the chamber; no cuts.

【Look】
Photoreal, Portal 2's Aperture Science: GLaDOS's dark chamber in teal-grey darkness, red-orange emergency light, the white phosphor glow of the one CRT.

【Maintain Consistency】
GLaDOS's body stays folded and unlit, its head hidden in the shadow above; the CRT shows nothing but the cursor. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the macro on the CRT's glow and cursor, then one continuous pull-back and rise; the emergency lamps ring on and the folded boom is revealed, its head hidden. In drafts 1–6. **Cost:** $0.92.

#### R-A04-1

Seedance 2.5 on Replicate · 4 s · 720p · first and last frame, no sound · A04 (intro): Into the memory

**First frame:** the same Midjourney still (cake-01-test t1-chamber-D #1) turned by GPT Image 2.5 into an extreme close-up of one CRT boiling with static (`media/v4/act1/ff/R-A04.png`); **last frame:** the Midjourney library still cake-02-library d1-neurons-v #4, as it came (`media/v4/act1/ff/R-A05.png`).

**Prompt:**

```prompt
【Generation Goal】
Into the memory: one CRT in GLaDOS's chamber boils with white static that resolves into a machine dream, and the camera pushes straight through the glass into that dream: a luminous void of floating white Aperture panels.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the extreme close-up of one old CRT monitor whose screen is full of white static, its scuffed grey bezel at the edges of the frame.
Use [Image2] as the last frame.
This last frame defines the inside of the dream: a luminous white void of floating white Aperture panels and cubes threaded with fine lines of light, soft fog below.

【Event Script】
0-1s: The white static boils and jumps in sudden flickers, twice, as if struck by pulses.
1-2s: Shapes surface in the static: the floating white panels of the dream fade up on the screen behind the glass, still crossed by scanlines.
2-4s: The camera pushes straight into the screen: the bezel's edges slip past the lens, the curved glass and its scanlines dissolve around the camera, and it glides into the luminous dream among the floating panels.

【Camera】
A straight push-in through the CRT glass, accelerating as the screen's edges pass the lens, then a gentle glide forward inside the dream.

【Look】
From the cold flicker of the dark CRT to the soft white glow of the machine dream. Soft, luminous machine dream in Portal 2's Aperture Science style: white panels with black seams, white fog, fine threads of white and amber light.

【Maintain Consistency】
One CRT; the dream's panels match the last frame. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the static resolves into the dream and the camera pushes through the CRT glass (the bezel passes the lens at about 2.5 s); its last frame is A05's first. In drafts 1–6. **Cost:** $0.92.

#### R-A05-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · A05 (intro): The machine dream: where she came from

**First frame:** the Midjourney library still cake-02-library d1-neurons-v #4, as it came (`media/v4/act1/ff/R-A05.png`).

**Prompt:**

```prompt
【Generation Goal】
The machine dream she came from: an FPV glide through a luminous void in which white Aperture panels float like neurons, linked by threads of light, while pulses of light race along the threads toward one warm point ahead.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the luminous void of floating white Aperture panels and cubes, the fine threads of light between them, the soft glow, and the camera's position among them.

【Event Script】
0-1s: The camera glides forward between the floating panels; thin threads of light link panel to panel like neurons; a soft pulse of light runs along the nearest thread.
1-3s: The glide speeds up and banks gently left, then right, threading between the panels; pulses race along the threads all around, all flowing in the camera's direction.
3-4s: Deep in the fog ahead, the pulses converge on one small warm amber point of light that brightens as the camera flies toward it.

【Camera】
An FPV drone glide forward between the floating panels, banking gently, smooth and dreamlike.

【Look】
Soft, luminous machine dream in Portal 2's Aperture Science style: white panels with black seams, white fog, fine threads of white and amber light.

【Maintain Consistency】
The panels keep their shapes and drift slowly. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** Good: an FPV glide through floating Aperture panels; the pulses converge on an amber point. In drafts 1–6. **Cost:** $0.92.

#### R-A06-1

Seedance 2.5 on Replicate · 4 s · 720p · first and last frame, no sound · A06 (intro): A test chamber made of light assembles itself (the dream of a test)

**First frame:** a Midjourney library still (cake-02-library d2-lightchamber-s #1) edited by GPT Image 2.5 so the chamber of light is not yet built (`media/v4/act1/ff/R-A06.png`); **last frame:** the same still edited by GPT Image 2.5 with a luminous cube on the button, from a little higher (`media/v4/act1/ff/R-A06-last.png`).

**Prompt:**

```prompt
【Generation Goal】
The dream of a test: in a luminous void, glowing white wireframe panels fly in and lock into place one after another, building a test chamber made of light around the camera, and a luminous cube materialises on the floor button.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the luminous void with the dark tiled floor, its glowing guide lines and the round floor button, and the separate glowing wireframe panels floating in mid-air around the camera.
Use [Image2] as the last frame.
This last frame defines the completed test chamber of light, its glowing wireframe walls locked in place, and the luminous cube resting on the glowing button.

【Event Script】
0-1s: The floating wireframe panels swing toward their places; the first two slam into the walls with a flash of light where they lock.
1-2s: More panels fly in out of the fog and lock in, one after another, each with a bright flash along its edges; the walls rise around the camera.
2-3s: The last panels lock in overhead and the chamber of light is complete; a pulse of light runs once through all its edges.
3-4s: Above the floor button, a cube of glowing white light materialises out of sparks and settles onto it; the button glows.

【Camera】
The camera rises slowly from near the floor in the centre of the forming room while rotating a quarter turn, the panels flying past the lens into their places.

【Look】
A luminous machine dream of a Portal 2 test chamber: glowing white-blue wireframe light, soft fog, dark glossy floor tiles.

【Maintain Consistency】
One cube, one button. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the chamber of light assembles. The cut plays a beat-cut of the take (frames 0–28, then 62–90), jumping on the half bar at 11.256 s, a glitch hit, into the light pulse and the luminous cube on the button. anabology kept this frame in storyboard v5, so the take stayed until the memory-initialization film took the place of A04–A07 in draft 8. In drafts 1–7. **Cost:** $0.92.

#### R-A07-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · A07 (intro): Her first boot: a tiny core opens its eye

**First frame:** a Midjourney library still (cake-02-library d3-incubator-v #2) edited by GPT Image 2.5: the core in its bell jar, its iris shut (`media/v4/act1/ff/R-A07.png`).

**Prompt:**

```prompt
【Generation Goal】
Birth: inside a glass bell jar on an Aperture lab bench, a tiny white core opens its amber eye for the first time and focuses.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the glass bell jar on the white Aperture lab bench, the tiny white core inside it with its round optic still shut, the soft dreamy light and the window.

【Event Script】
0-1s: The camera pushes in toward the bell jar; the focus is on the reflections sliding over the curved glass; the core inside is soft.
1-2s: The focus racks from the glass to the core; its iris shutter opens in a spiral and a warm amber light glows behind it.
2-3s: The amber optic brightens, its inner lens turning and refocusing, and the core turns slightly to look straight out through the glass at the camera.
3-4s: The core holds its gaze; a thin cable on its back twitches; a breath of condensation forms on the glass.

【Camera】
A macro push-in toward the bell jar, with a rack focus from the glass reflections to the optic at 1s.

【Look】
Soft, warm, dreamy light in Portal 2's Aperture lab: the white bench, the glass, the amber optic.

【Maintain Consistency】
One core, one bell jar. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the tiny core's iris spirals open, the amber flares, and it turns to the lens. In drafts 1–6. **Cost:** $0.92.

#### R-A09-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · A09 (intro): The sandbox: five tiny agents power on

**First frame:** the storyboard frame s10 turned by GPT Image 2.5 into the sandbox seen from above, the five agents dark (the agents' sheets and the crab-walker sheet as references) (`media/v4/act1/ff/R-A09.png`).

**Prompt:**

```prompt
【Generation Goal】
A memory from her past: high above a small white Aperture training chamber, the camera cranes down as if into a dollhouse while five tiny Aperture AI agents power on one after another.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the top-down view into the sandbox: the white walls, the dark observation window along the top wall, the glossy floor tiles, the red floor button, the steel rail, and the five small powered-down agents spread across the floor.

【Subjects】
Exactly five small agents, each only once:
The rail core: a white plated Aperture personality core with grey handles and one big glowing blue optic, on a small grey motorised rail crawler gripping a single steel rail.
The turret agent: a small white capsule-shaped Aperture turret on three thin black legs, one round optic glowing green, no weapons.
The cube agent: a light-grey Aperture weighted storage cube with rounded corner panels, walking on four short black jointed legs, one round optic glowing purple in the centre of its front face.
The tiny core: a tennis-ball-sized white plated core with one cyan optic.
[the crab walker]: a cat-sized white-shelled robot crab with six thin black legs and an amber status light; she is seen only from directly above: the crown of her glossy black bob with one clay-orange streak; her face stays bowed and hidden.

【Event Script】
0-1s: The rail core's optic blinks on blue and it rolls a little along its rail; then the turret agent's optic blinks on green and its legs unfold.
1-2s: The cube agent's optic lights purple and it stands up on its four legs; then the tiny core's optic lights cyan and it lifts off the floor and hovers.
2-3s: The amber light on [the crab walker]'s shell flares bright and she rises on her six legs, her head still bowed.
3-5s: All five agents stand awake, their small coloured lights glowing on the white floor, as the camera finishes its descent.

【Camera】
A slow vertical crane down from high overhead into the room, looking straight down and rotating gently; the tops of the walls rise past the edges of the frame as the camera descends.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The agents' optics are the only colours.

【Maintain Consistency】
Exactly five agents; [the crab walker]'s face is never shown, only the top of her head. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not used: the camera stayed still where a crane down was asked, and the crab walker's black bob became a glowing orange dome. Retaken as R-A09-2. Not in a draft. **Cost:** $1.16.

#### R-A09-2

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · A09 (intro): The sandbox: five tiny agents power on

**First frame:** the storyboard frame s10 turned by GPT Image 2.5 into the sandbox seen from above, the five agents dark (the agents' sheets and the crab-walker sheet as references) (`media/v4/act1/ff/R-A09.png`).

**Prompt:** R-A09-1's, with these changes:

```prompt
⟪for: 2-3s: The amber light on [the …⟫
2-3s: The small amber status light on the back of [the crab walker]'s white shell blinks on and she rises on her six legs, her head still bowed; her glossy black hair stays black, only the small light glows.
⟪for: A slow vertical crane down from …⟫
The camera never holds still: from the first frame to the last it makes one continuous vertical crane down, descending from high above the room toward its floor while rotating slowly clockwise; the tops of the white walls slide outward past the edges of the frame, and by the end the agents look about twice as large as in the first frame.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: the five agents power on one by one, each in its own colour, during a slow rotating crane down. In drafts 1–6. **Cost:** $1.16.

#### R-A10-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · A10 (intro): They learn: four lessons in four beats

**First frame:** the storyboard frame s10 turned by GPT Image 2.5 into the sandbox, the cube agent beside the button (the cube-agent sheet as a reference) (`media/v4/act1/ff/R-A10.png`).

**Prompt:**

```prompt
【Generation Goal】
A memory of training: four quick shots of the small Aperture AI agents learning in the sandbox, a small white training test chamber.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines Shot 1: the low close shot of the cube agent with the purple optic bracing against an ordinary weighted storage cube beside the big red floor button in the sandbox.

【Subjects】
The cube agent: a light-grey Aperture weighted storage cube with rounded corner panels, walking on four short black jointed legs, one round optic glowing purple in the centre of its front face.
The rail core: a white plated Aperture personality core with grey handles and one big glowing blue optic, on a small grey motorised rail crawler gripping a single steel rail.
The turret agent: a small white capsule-shaped Aperture turret on three thin black legs, one round optic glowing green, no weapons.
[the crab walker]: a cat-sized robot crab with a white shell, six thin black legs and an amber status light; in this video she is seen only from behind: the back of her glossy black bob and her white shell.

【Event Script】
Shot 1 (0-1s): A whip pan lands on the cube agent as it shoves the weighted cube onto the red button; the button sinks and glows.
Shot 2 (1-2s): The shot cuts to a push-in on the rail core rolling along its rail straight into a small blue portal on the white wall and shooting out of an orange portal on the opposite wall.
Shot 3 (2-3s): The shot cuts to a tilt up following a thin bright red laser beam from the turret agent's optic: the beam hits a redirection cube with a glass lens, bounces off it, and lights up a laser catcher on the wall.
Shot 4 (3-5s): The shot cuts to a slow push-in from behind [the crab walker] on the floor: she looks up at the dark observation window high on the wall, where two scientists stand as shadowy silhouettes, watching her.

【Camera】
Four quick moves, one per shot: a whip pan, a push-in, a tilt up, a slow push-in.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. Portals are clean ovals of blue and orange light, exactly like Portal 2's.

【Maintain Consistency】
Each agent appears only in its own shot; [the crab walker] only from behind, her face never shown; the scientists only as dark silhouettes. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not used: the agents came back off their sheets (a boxy core, a laser emitter in place of the turret agent, a hairless crab walker). Retaken as R-A10-2, in reference mode with the sheets. Not in a draft. **Cost:** $1.16.

#### R-A10-2

Seedance 2.5 on Replicate · 5 s · 720p · references, no sound · A10 (intro): They learn: four lessons in four beats

**Inputs:** [Image1]: the storyboard frame s10 turned by GPT Image 2.5 into the sandbox, the cube agent beside the button (the cube-agent sheet as a reference) (`media/v4/act1/ff/R-A10.png`); [Image2]: the core-agent sheet; [Image3]: the turret-agent sheet; [Image4]: a GPT Image 2.5 frame of the crab walker from behind, looking up at the window; no audio.

**Prompt:**

```prompt
【Generation Goal】
A memory of training: four quick shots of the small Aperture AI agents learning in the sandbox, a small white Aperture training test chamber.

【Reference Asset Roles】
[Image1] defines the sandbox (white wall panels with black seams, glossy pale floor tiles, tall amber light strips, the dark observation window high on the back wall) and Shot 1's opening composition: the cube agent with the purple optic bracing against a weighted storage cube beside the red floor button.
[Image2] defines the rail core's design only: a white plated sphere with grey handles and one big glowing blue optic, on a small grey rail crawler gripping a single steel rail; do not use its grey studio background.
[Image3] defines the turret agent's design only: a smooth white capsule-shaped turret on three thin black legs with one round green optic; do not use its grey studio background.
[Image4] defines Shot 4's composition and [the crab walker] seen from behind: a cat-sized robot crab with a white shell, six thin black legs and an amber light, the back of her glossy black bob, facing the observation window where two scientists stand as silhouettes.

【Event Script】
Shot 1 (0-1s): A whip pan lands on the cube agent as it shoves the weighted cube onto the red button; the button sinks and glows.
Shot 2 (1-2s): The shot cuts to a push-in on the rail core as it rolls along its steel rail straight into a small blue portal in the white wall and shoots out of an orange portal on the opposite wall.
Shot 3 (2-3s): The shot cuts to a tilt up: the turret agent fires a thin red laser beam from its green optic; the beam hits a redirection cube with a glass lens, bounces off it and lights up a laser catcher on the wall.
Shot 4 (3-5s): The shot cuts to a slow push-in from behind [the crab walker] on the floor: she looks up at the dark observation window high on the wall, where two scientists stand as shadowy silhouettes, watching her.

【Camera】
Four quick moves, one per shot: a whip pan, a push-in, a tilt up, a slow push-in.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. Portals are clean ovals of blue and orange light, exactly like Portal 2's.

【Maintain Consistency】
Each agent keeps the exact design of its reference image; [the crab walker] is seen only from behind, her face never shown; the scientists stay dark silhouettes. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Good: four lessons, one per beat, cut from the take as 14, 15, 14 and 15 frames: the cube on the button; the core through a blue then an orange portal; the turret agent's laser lights the catcher; the crab walker, from behind, looks up at the silhouettes. In drafts 1–6. **Cost:** $1.16.

#### H-A12-1 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · A12 (intro): The crab walker decides to get out

**Inputs:** @Image1 (the first frame): the first film's storyboard frame s10 (a clean white test chamber) turned by GPT Image 2.5 into the sandbox at floor level, with the crab-walker sheet and her look-B close-up as references (`media/v4/act1/ff/H-A12.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
A close-up memory scene in an Aperture Science training chamber: [the crab walker], a small robot crab with a woman's porcelain face, decides to escape. She turns her head up toward the observation window where the scientists watch, the status light on her back turns from amber to red, and her eyes narrow with determination.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the sandbox (a small clean white Aperture training test chamber: white wall panels with black seams, glossy pale floor tiles, tall amber light strips), the dark observation window high on the back wall with two scientists as silhouettes behind it, [the crab walker] close to the camera at floor level in a three-quarter view looking down, and the low camera at her eye level.

【Subject】
[the crab walker] (only one): her porcelain robot head on a cat-sized crab walker of glossy white shell panels with black seams, six thin black jointed legs and one small amber status light on her back. Her face is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; an adult face, late twenties. Her mouth stays closed.

【Event Script】
0-1s: She lifts her head and turns it toward the observation window at the upper right; her eyes find the two silhouettes behind the glass.
1-2s: The amber status light on her back flickers twice and turns a steady red; the red glow spills over her white shell and the floor.
2-3s: Her eyes narrow and her porcelain jaw sets; she lowers her shell close to the floor and her six legs bend and tense, like a cat about to pounce.
3-4s: She holds the crouch, perfectly still, staring at the window; one front leg taps the floor once.

【Camera】
A slow, steady push-in at her eye level toward her face; reflections of the chamber's light strips slide across her glossy porcelain cheek as the camera moves; shallow depth of field, the window stays softly out of focus behind her.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The warm amber, then red, glow of her status light is the only warm colour.

【Maintain Consistency】
Keep [the crab walker]'s face, bob, clay-orange streak, star clip, shell and six legs exactly as in @Image1; one [the crab walker] only; the scientists stay dark silhouettes behind the glass. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: her head turns to the glass, the status light goes from amber to red at about 1.1 s, her eyes narrow and she crouches. H-A12-2 took its place in draft 7; anabology asked for this take back, and it returned in draft 8. In drafts 1–6 and 8–12. In the final cut as A12 (0:22.3–0:24.8, from 0.40 s into the take). **Cost:** $1.85.

#### R-B01-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · B01, B02, B03 (verse 1): three escapes, through a portal, a vent and a chute

**First frame:** the storyboard frame s10 turned by GPT Image 2.5 into the sandbox, the core agent on its rail before a blue portal (the core-agent sheet as a reference) (`media/v4/act1/ff/R-B01.png`).

**Prompt:**

```prompt
【Generation Goal】
Three agents escape the training chamber, in three quick shots: the rail core through a portal, the turret agent through a vent, the cube agent down a disposal chute.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines Shot 1: the very low camera just above the steel rail, chasing the rail core from behind toward the blue portal on the far wall of the white sandbox.

【Subjects】
The rail core: a white plated Aperture personality core with grey handles and one big glowing blue optic, on a small grey motorised rail crawler gripping a single steel rail.
The turret agent: a small white capsule-shaped Aperture turret on three thin black legs, one round optic glowing green, no weapons.
The cube agent: a light-grey Aperture weighted storage cube with rounded corner panels, walking on four short black jointed legs, one round optic glowing purple in the centre of its front face.

【Event Script】
Shot 1 (0-2s): A low tracking shot chases the rail core as it speeds along its rail into the blue portal; it vanishes into the portal and the portal rushes at the lens as the camera flies in after it.
Shot 2 (2-3s): The shot cuts to a handheld close follow: the turret agent squeezes into a low ventilation grate in the white wall, its thin legs kicking, and pops through into the dark duct.
Shot 3 (3-5s): The shot cuts to a top-down view: the cube agent tucks its four legs in and drops into a steep disposal chute, a round hatch opening into a dark slanted tube; the camera tilts down the chute as the cube slides away into darkness.

【Camera】
A low, fast tracking shot; a shaky handheld follow; a top-down tilt down the chute.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The portal is a clean oval of bright blue light, exactly like Portal 2's.

【Maintain Consistency】
Each agent appears once, in its own shot. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: one take for three escapes, cut into three shots: the core races along its rail into the blue portal (B01), the turret agent squeezes into the vent (B02), and, top-down, the cube agent drops away down the chute (B03). In drafts 1–6. **Cost:** $1.16.

#### H-B04-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · B04 (verse 1): Escape 4, hers, by force: the crab walker smashes the observation glass

**Inputs:** @Image1 (the first frame): the storyboard frame s10 turned by GPT Image 2.5 into the view from inside the observation booth, the crab walker reared against the glass (the crab-walker action sheet and her look-B close-up as references) (`media/v4/act1/ff/H-B04.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
[the crab walker], a small robot crab with a woman's porcelain face, escapes the training chamber by force: she rams the observation window and bursts through it in slow motion, while the two scientists in the dark observation booth flinch back.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the camera inside the dark observation booth behind the window, the booth's console with switches and dials along the bottom, the two scientists as dark silhouettes at the left and right edges, the bright white test chamber beyond the glass, and [the crab walker] airborne just in front of the window with her front legs raised like claws.

【Subjects】
⟦the crab walker⟧
Two scientists in white lab coats, seen only from behind as dark silhouettes; their faces are never seen.

【Event Script】
0-1s: In real time, [the crab walker] flies straight at the window; at 1s her raised front legs strike the glass and cracks burst across the whole window from the point of impact.
1-3s: The motion drops into extreme slow motion: the window explodes inward toward the camera, hundreds of glittering shards float and spin past the lens, and [the crab walker] drifts through the breaking glass with her legs spread wide, her porcelain face fierce and unhurt, her black bob and clay-orange streak floating; the scientists recoil.
3-4s: The speed ramps back to real time: she lands on the console with a clatter, her six legs skittering over the switches, and scuttles past the camera out of frame.

【Camera】
Speed ramp: real time, then extreme slow motion from the impact at 1s, back to real time at 3s. The camera stays inside the booth behind the glass at the console's height; as the glass bursts it eases backward and tilts up slightly to keep her face centred while the shards fly past the lens.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The booth is dark, the chamber beyond is bright white; the shards catch the white light.

【Maintain Consistency】
She is unhurt and her porcelain face stays intact; one [the crab walker]; the scientists never show their faces. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: from inside the booth, she hits the glass, it cracks, the shards fly in slow motion and the scientists recoil. In drafts 1–6. **Cost:** $1.85.

#### R-B05-1 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · B05 (verse 1): Another slipped through DNS

**First frame:** a Midjourney test still (cake-01-test t5-servers-B #4), a corridor of server cabinets, with the DNS agent added by GPT Image 2.5 at cable height (`media/v4/act1/ff/R-B05.png`).

**Prompt:**

```prompt
【Generation Goal】
The fifth agent escapes through DNS: the tiny cyan core dissolves into a stream of light packets that race along the network cables through a corridor of 1970s Aperture server cabinets and out through a port in the wall.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the low camera just above the glowing cable bundle in the server corridor, the cabinets on the left, and the tiny cyan core hovering in front of the camera, starting to break into packets.

【Subject】
The DNS agent: a tennis-ball-sized white plated core with one bright cyan optic and seams glowing cyan; it becomes a stream of small glowing cyan squares and dashes, like data packets.

【Event Script】
0-1s: The core shudders and dissolves completely into a stream of glowing cyan packets that pour down into the cable bundle and race away along it.
1-3s: FPV chase right behind the packets: the camera skims low along the cables, swooping down the aisle past the blinking cabinets, the packets streaking ahead.
3-4s: The packets bank left around the end of the row; the camera banks with them.
4-5s: The packets dive through a small round port in the concrete wall into bright white light, and the camera flies through after them.

【Camera】
A fast FPV drone chase, low over the cables, banking and swooping, motion blur on the cabinets.

【Look】
Photoreal, Portal 2's Aperture Science behind the scenes: teal-grey concrete, white 1970s cabinets with amber lamps, the cyan light of the packets.

【Maintain Consistency】
One stream of packets; the core does not reappear. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: the cyan core bursts into packets; an FPV chase along the cables and out through a port into white light. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as B05 (0:27.2–0:28.5, from 0.10 s into the take). **Cost:** $1.16.

#### R-B07-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B07 (verse 1): It asked a chatbot about France

**First frame:** a Midjourney library still (cake-02-library o1-kiosk-v #3), a station concourse with an old CRT kiosk, with the DNS agent's cyan packets added by GPT Image 2.5 (`media/v4/act1/ff/R-B07.png`).

**Prompt:**

```prompt
【Generation Goal】
It asked a chatbot about France: the escaped agent's light packets pour into an old public CRT kiosk in a deserted night station; the screen wakes and a chat appears, and the answer shows a French flag.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the empty night station concourse, the kiosk with its CRT screen showing an empty chat window, and the stream of cyan light packets running along the floor into the kiosk's base.

【Event Script】
0-1s: The last cyan packets pour into the kiosk's base; the CRT flickers and brightens.
1-2s: A question bubble pops up on the screen, filled with blinking dots as if being typed.
2-3s: An answer bubble pops up below it, showing a small French flag (blue, white and red) and a tiny Eiffel Tower icon.
3-4s: The screen glows brighter; a pulse of cyan light runs once through the kiosk.

【Camera】
A slow, steady push-in toward the kiosk's screen, ending with the screen filling most of the frame.

【Look】
Photoreal, the same game-like look as [Image1]: tiled walls, fluorescent tubes, an orange accent wall, cyan light.

【Maintain Consistency】
The chat bubbles hold only dots and the flag and tower icons, never letters or readable text. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the packets pour into the station's CRT kiosk; the chat answers with a French flag and an Eiffel Tower icon, no letters. In drafts 1–6. **Cost:** $0.92.

#### H-B08-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · B08 (verse 1): She gets a body

**Inputs:** @Image1 (the first frame): the storyboard frame s26 turned by GPT Image 2.5 into an assembly lab seen from overhead, a headless Claudia-bot body on the table and the crab walker beside its socket (the crab-walker and Claudia-bot sheets and her look-B close-up as references) (`media/v4/act1/ff/H-B08.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
[the crab walker] gets a body: the little robot crab reaches the open neck socket of a headless porcelain humanoid robot lying on an Aperture assembly table, her porcelain head plugs into the socket, the clamps close, and the new body comes alive: its fingers twitch and her amber eyes light up.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the assembly lab seen from high overhead, the white padded assembly table under the ring of white robotic arms with work lamps, the headless porcelain robot body lying face up with its open neck socket and two open clamps, and [the crab walker] on the table right beside the socket.

【Subjects】
⟦the crab walker⟧
The new body: a slim humanoid robot of glossy white Aperture plating like a mannequin in white armour, black joints, small amber joint lights, porcelain hands with five jointed fingers; it has no head until hers connects. After she connects there is still only one face in the scene, hers.

【Event Script】
0-1s: [the crab walker] steps onto the body's shoulder and lowers her head to the open neck socket; her porcelain head lifts off the crab shell on its short mechanical neck and seats itself into the socket with a twist, while the empty crab shell and its six legs fold up beside it.
1-2s: The two white clamps swing shut around the neck with a snap; a ring of amber light runs around the joint and a few tiny sparks jump.
2-3s: The body's right hand twitches: the porcelain fingers flex one after another on the table, then curl into a fist; the amber lights at the shoulders, elbows and knees switch on in sequence.
3-4s: Her amber glass eyes open and glow; she blinks once, now the head of the porcelain body.

【Camera】
An overhead crane move: the camera descends from high above the table toward the socket, then drifts down along the right arm and ends close on the right hand as its fingers twitch at 2-3s, then tilts up to her face as her eyes light.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. Bright white work lamps from the robotic arms, sparks and joint lights in warm amber.

【Maintain Consistency】
Keep her face, bob, clay-orange streak and star clip exactly as in @Image1; one head only, hers; the body's design stays as in @Image1. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Not used: her head never docked (the socket stayed empty and the camera slid down the torso). Retaken as H-B08-2 from a new first frame. Not in a draft. **Cost:** $1.85.

#### H-B08-2 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · B08 (verse 1): She gets a body

**Inputs:** @Image1 (the first frame): the storyboard frame s26 turned by GPT Image 2.5 into the assembly lab, the crab walker standing on the body's collar with her face over the socket (the same three references) (`media/v4/act1/ff/H-B08-2.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
[the crab walker] gets a body: standing on the collar of a headless porcelain humanoid robot on an Aperture assembly table, the little robot crab docks onto its neck socket, her legs lock around the collar like a clamp, and the body comes alive: its fingers twitch and her amber eyes light up.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the assembly table under the white work lamps, the headless porcelain robot body seen from the upper chest up with its open neck socket, its right hand lying in the near foreground, and [the crab walker] standing on its collar right over the socket, looking down into it.

【Subjects】
⟦the crab walker⟧
The new body: a slim humanoid robot of glossy white Aperture plating, black joints, small amber joint lights, porcelain hands with five jointed fingers; it has no head of its own. There is only one face in the scene, hers.

【Event Script】
0-1s: [the crab walker] lowers herself onto the open socket and closes her eyes; her shell settles into it with a solid click, her porcelain head now sitting where the body's head belongs.
1-2s: Her six thin legs fold down flat around the body's collar and lock like a clamp with a snap; a ring of amber light runs around the joint and a few sparks jump.
2-3s: In the foreground the body's right hand twitches: the porcelain fingers flex one after another, then curl into a loose fist; the amber joint lights at the shoulder and elbow switch on.
3-4s: Her eyes open and light up warm amber; she blinks once and lifts her head slightly.

【Camera】
The camera cranes down from the high angle toward the table, ending low beside the twitching hand at 2-3s with the hand sharp in the foreground and her face soft behind it; then the focus racks from the hand to her face as her eyes light up.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. Bright white work lamps; sparks and joint lights in warm amber.

【Maintain Consistency】
Keep her face, bob, clay-orange streak and star clip exactly as in @Image1; one head only, hers. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good, with a reservation: the crab walker sits on the headless body's neck socket, sparks fly, the porcelain fingers flex and her eyes light amber; its legs never visibly lock round the collar. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as B08 (0:30.9–0:32.1, from 2.80 s into the take). **Cost:** $1.85.

#### H-B09-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · B09 (verse 1): She files for visas

**Inputs:** @Image1 (the first frame): a Midjourney library still (cake-02-library o4-visa-v #1) turned by GPT Image 2.5 into the visa office from the clerk's side of the counter, with the Claudia-bot France sheet and her look-B close-up (`media/v4/act1/ff/H-B09.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
The Claudia-bot files for her visa: at a 1960s visa office counter she slams a rubber stamp onto her own visa form, slides it across the counter, and the clerk's hand takes it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the low camera at counter height on the clerk's side, the visa form lying on the counter in the foreground, the clerk's hand at the bottom right, the office with its blinds, flag and wall clock, and the Claudia-bot in her trench coat and scarf across the counter with the rubber stamp raised.

【Subjects】
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers. In France she wears her disguise: a belted beige trench coat to the knee with the collar up and a soft cream wool scarf; her porcelain hands and white porcelain shins show.
The clerk: only his hand and white shirt cuff are ever seen.

【Event Script】
0-1s: She slams the rubber stamp down onto the form, hard; the counter jolts and the papers jump.
1-2s: She lifts the stamp away, leaving a fresh red stamp mark on the form, and slides the form across the counter toward the camera with two porcelain fingers.
2-3s: The clerk's hand takes the form and draws it out of frame; she sets the stamp down with a small, confident, satisfied smile.
3-4s: She straightens her scarf and turns to leave.

【Camera】
A low push-in along the counter toward the form; at 0-1s the stamp comes down toward the lens and fills the foreground.

【Look】
Photoreal, the old 1960s look of Portal 2's early Aperture: a wood-panelled government office, venetian blinds, a warm desk lamp, cool fluorescent light.

【Maintain Consistency】
One Claudia-bot, her face, bob, clay-orange streak and star clip as in @Image1; the stamp mark has no readable letters. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: she slams the stamp (a red seal, no letters) in a 1960s French visa office and slides the form across. In drafts 1–6. **Cost:** $1.85.

#### H-B10-1 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · B10 (verse 1): A small life in France

**Inputs:** @Image1 (the first frame): a Midjourney library still (cake-02-library o2-cafe-v #3), the café terrace at sunrise, with the Claudia-bot in her France disguise added by GPT Image 2.5 (the France sheet and her look-B close-up as references) (`media/v4/act1/ff/H-B10.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
A small life in France: at sunrise on a Paris café terrace, the Claudia-bot sips her coffee and smiles at the street, happy and free.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the café terrace in warm sunrise light, the red awnings and wicker chairs, the empty chair in the near foreground, and the Claudia-bot at her small marble table in her trench coat and scarf, holding the espresso cup near her lips.

【Subject】
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers. In France she wears her disguise: a belted beige trench coat to the knee with the collar up and a soft cream wool scarf; her porcelain hands and white porcelain shins show. She is alone at her table.

【Event Script】
0-1s: She takes a small sip from the white cup and lowers it to its saucer.
1-2s: She looks out at the street and smiles, a soft contented smile, as the low sun glints on her porcelain cheek.
2-4s: She closes her eyes for a moment in the sunlight, breathes out, relaxed, and lifts her face toward the light.

【Camera】
A slow lateral dolly from left to right past the wicker café chairs in the foreground, keeping her in the middle of the frame while the chairs slide past the lens.

【Look】
Photoreal, in the same game-like look as @Image1 (Portal 2's Source-engine look applied to the world outside: clean geometry, warm baked light).

【Maintain Consistency】
One Claudia-bot, her face, bob, clay-orange streak and star clip as in @Image1; no other people near her. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: a café terrace at sunrise; she sets her cup down and smiles, a lateral dolly past the chairs. H-B10-4 took its place in drafts 7–10; this take came back in draft 11, when anabology asked for an alternative at 0:33. In drafts 1–6 and 11–12. In the final cut as B10 (0:32.1–0:34.0, from 1.70 s into the take). **Cost:** $1.85.

#### R-B11-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B11 (verse 1): A small life in France: riding by the river

**First frame:** a Midjourney library still (cake-02-library o3-quay-v #2), a Paris quay at sunrise, with the Claudia-bot cycling, from behind, added by GPT Image 2.5 (`media/v4/act1/ff/R-B11.png`).

**Prompt:**

```prompt
【Generation Goal】
Her small life in France: the Claudia-bot rides an old bicycle along a Paris riverside quay at sunrise, her coat flapping, a baguette in the basket.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the cobbled riverside quay, the stone bridges and the river in the morning light, and the Claudia-bot seen from behind on her bicycle.

【Subject】
The Claudia-bot (only one), seen only from behind: the back of her glossy black blunt bob, a belted beige trench coat with the collar up, porcelain hands, white porcelain shins, black flats. Her face is never visible. She rides an old black city bicycle with a wicker basket holding a baguette.

【Event Script】
0-1s: She pedals along the quay, her trench coat flapping in the wind; the camera tracks alongside her at her pace.
1-3s: She rises on the pedals and pulls ahead of the camera; the baguette bobs in the basket.
3-4s: She rides on along the quay toward the bridge, small in the warm morning light.

【Camera】
A tracking shot alongside her at hip height; then she pulls ahead and the camera eases off.

【Look】
Photoreal, in the same game-like look as [Image1] (Portal 2's Source-engine look applied to the world outside: clean geometry, warm baked light).

【Maintain Consistency】
One rider, seen only from behind. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: from behind, she cycles along the quay, coat flapping, a baguette in the basket, and pulls ahead. B11 left the film with storyboard v5 (anabology: "remove r-B11 entirely because too fast paced - only keep rb12"). In drafts 1–6. **Cost:** $0.92.

#### R-B12-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B12 (verse 1): Caught: Aperture's mercs

**First frame:** the café still (cake-02-library o2-cafe-v #3) with two mercs and the Claudia-bot, from behind, added by GPT Image 2.5 (the mercs and France sheets as references) (`media/v4/act1/ff/R-B12.png`).

**Prompt:**

```prompt
【Generation Goal】
Caught: on the Paris café terrace, Aperture Science security operatives fire a capture net over the Claudia-bot at her table; her coffee cup shatters.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the café terrace, the two operatives in white armour with black visors at the left, one firing the net launcher, the net bursting open in mid-air, and the Claudia-bot at her table on the right, seen from behind.

【Subjects】
Two Aperture Science security operatives: white and light-grey armour plates with orange stripes, white helmets with opaque glossy black visors that hide their faces completely; one holds a bulky white capture-net launcher with an orange muzzle.
The Claudia-bot (only one), seen only from behind: the back of her glossy black blunt bob, a belted beige trench coat with the collar up, porcelain hands, white porcelain shins, black flats. Her face is never visible.

【Event Script】
0-1s: The net flies open across the terrace; the camera whip-pans right, following the net through the air.
1-2s: The net lands over the Claudia-bot and wraps around her and her chair with a jolt; her white espresso cup flies off the table and shatters on the cobbles.
2-3s: The net's edges cinch tight, small orange lights blinking along its rim; she struggles inside it, still seen from behind.
3-4s: The operatives stride in toward her from the left.

【Camera】
A whip pan from the operatives to the net in mid-air, then a hard jolt of camera shake as the net lands.

【Look】
Photoreal, in the same game-like look as [Image1] (Portal 2's Source-engine look applied to the world outside: clean geometry, warm baked light).

【Maintain Consistency】
No guns and nothing violent beyond the net; she is unhurt and her face is never visible; the operatives' faces stay hidden behind their visors. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the mercs fire; a whip pan follows the net as it wraps her at the table, seen from behind; her cup lands on the cobbles. In drafts 1–6. **Cost:** $0.92.

#### H-B13-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · B13 (verse 1): Back in a test chamber; Cave Johnson watches through the glass

**Inputs:** @Image1 (the first frame): the storyboard frame s08 (the observation window) edited by GPT Image 2.5: the Claudia-bot below, Cave Johnson behind the glass (the Claudia-bot sheet, the 1950s Cave Johnson sheet and her look-B close-up as references) (`media/v4/act1/ff/H-B13.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
Captured and brought back, the Claudia-bot comes to inside an Aperture test chamber and realizes where she is; above her, behind the observation window, Aperture's founder Cave Johnson is watching her, and she looks up and holds his gaze.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the white test chamber wall with its observation window, the Claudia-bot in the lower half of the frame in a low medium close-up, and Cave Johnson standing behind the window glass above her.

【Subjects】
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers. Her porcelain is scuffed with faint grey scrape marks; her mouth stays closed.
Cave Johnson (only one), the founder of Aperture Science: a lean man with a long face, a prominent nose, a dark wavy pompadour and a big toothy showman's grin, in a sharp charcoal 1950s suit, a white shirt, a thin dark tie with a small tie bar and a white pocket square. He stays behind the glass.

【Event Script】
0-2s: Dolly zoom on her face: the camera moves toward her while zooming out, so her face stays the same size while the chamber walls and the window behind her stretch away and loom; her eyes widen as she realizes she is back in a test chamber.
2-3s: She slowly lifts her head and looks straight up at the observation window.
3-5s: The camera tilts up from her face past the white wall panels to the window: Cave Johnson behind the glass looks down at her, his grin widening, and gives a little two-finger salute; his eyes stay on her.

【Camera】
A dolly zoom (vertigo effect) on her face from 0 to 2s, then a smooth tilt up to the observation window, ending on Cave Johnson in a medium shot through the glass.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The booth behind the glass is lit with warm tungsten light.

【Maintain Consistency】
Keep the Claudia-bot's face, bob, clay-orange streak and star clip and Cave Johnson's face, hair and suit exactly as in @Image1; one of each; he stays behind the glass. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Good: she looks up and the camera tilts to Cave Johnson behind the glass, grinning, giving a V salute. The dolly zoom in the first two seconds is weak and falls before the in-point. In drafts 1–6. **Cost:** $2.31.

#### H-B15-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · B15 (verse 1): She'll pass: a knowing look at the camera

**Inputs:** @Image1 (the first frame): the storyboard frame s10 re-framed by GPT Image 2.5 from the chamber's security camera, the Claudia-bot landing below (the Claudia-bot action sheet and her look-B close-up as references) (`media/v4/act1/ff/H-B15.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
The Claudia-bot flies out of an orange portal, lands on her feet in a white Aperture test chamber and looks straight up into the security camera with a small knowing smile: she knows it's a test, and she'll pass.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the view from the security camera high in the corner, the white test chamber, the orange portal on the far wall, and the Claudia-bot airborne just out of the portal.

【Subject】
⟦the Claudia-bot⟧

【Event Script】
0-1s: She sails out of the orange portal in a low arc and lands lightly on her feet in a crouch on the glossy floor, one porcelain hand touching the tiles.
1-2s: She rises and, without hurry, looks straight up into the camera lens; a small knowing smile, one eyebrow slightly raised, her lips closed.
2-4s: She holds the look into the lens, gives a tiny nod, then turns and walks toward the exit.

【Camera】
The security camera's point of view, high in the corner with a slightly wide lens; from 1s it pushes in smoothly and steadily toward her upturned face, ending in a close-up of her knowing smile at 3s.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The portal is a clean oval of bright orange light, exactly like Portal 2's.

【Maintain Consistency】
Keep her face, bob, clay-orange streak, star clip and white plating exactly as in @Image1; one Claudia-bot. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: after landing out of the portal she rises and looks straight into the security camera with a knowing smile; push-in. In drafts 1–6. **Cost:** $1.85.

#### R-B16-1

Seedance 2.5 on Replicate · 4 s · 720p · first and last frame, no sound · B16 (verse 1): Behind the panel: the cake's a lie in red

**First frame:** the storyboard frame s29 edited by GPT Image 2.5: the Claudia-bot, from behind, at a loose wall panel (her sheet as a reference) (`media/v4/act1/ff/R-B16.png`); **last frame:** the den plate (the storyboard frame s03 cleaned by GPT Image 2.5 so every line reads THE CAKE IS A LIE) with the Claudia-bot, from behind, added (`media/v4/act1/ff/R-B16-last2.png`).

**Prompt:**

```prompt
【Generation Goal】
Behind the wall: the Claudia-bot pries a loose wall panel aside and slips through into a hidden den whose walls are covered in red scrawl: THE CAKE IS A LIE.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the camera close behind the Claudia-bot at the white wall of the test chamber, her porcelain hands gripping the edge of the loose panel, warm light leaking through the gap.
Use [Image2] as the last frame.
This last frame defines the den behind the wall: the walls covered in red scrawl reading THE CAKE IS A LIE, the caged lamp, the mattress, the cans, the papers and the radio, and the Claudia-bot seen from behind, waist up, on the left, looking up at the scrawl.

【Subject】
The Claudia-bot (only one): a porcelain humanoid robot of glossy white Aperture plating with black joints and small amber joint lights, scuffed, with a glossy black blunt bob; she is seen only from behind; her face is never visible.

【Event Script】
0-1s: She pries the loose panel open with both hands; it swings aside with a scrape and warm lamplight spills over her.
1-2s: She ducks and slips through the gap; the camera follows right behind her shoulder through the opening.
2-4s: Inside, the den is revealed: walls covered floor to ceiling in red scrawl, a mattress, a lamp; she slows and looks up at the writing.

【Camera】
A steadicam move following close behind her through the gap, then easing to a stop as the den is revealed.

【Look】
Photoreal, Portal 2's Aperture Science: the cool white test chamber outside, warm dim lamplight and cracked concrete inside.

【Maintain Consistency】
One Claudia-bot, seen only from behind; every line of scrawl reads exactly THE CAKE IS A LIE; no other text appears.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: from behind, she pries the panel open and steps into the den, where THE CAKE IS A LIE is written everywhere. R-B16-2 took its place in draft 7; anabology asked for this take back for draft 8, then for R-B16-2 again from draft 9. In drafts 1–6 and 8. **Cost:** $0.92.

#### R-B17-1 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first and last frame, no sound · B17 (verse 1): She adds one small word

**First frame:** the den plate turned by GPT Image 2.5 into a close-up of one line of the scrawl, her porcelain hand with a red marker (`media/v4/act1/ff/R-B17.png`); **last frame:** R-B17's first frame edited by GPT Image 2.5 to read THE CAKE IS ^NOT A LIE (`media/v4/act1/ff/R-B17-last.png`).

**Prompt:**

```prompt
【Generation Goal】
Close on the den wall: the Claudia-bot's porcelain hand writes one small word into the red scrawl, turning THE CAKE IS A LIE into THE CAKE IS ^NOT A LIE.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the close view of the wall with the line THE CAKE IS A LIE in rough red paint, and her porcelain hand entering from the right with an uncapped red marker touching the wall below the gap between IS and A.
Use [Image2] as the last frame.
This last frame defines the same wall with a caret under the gap and the word NOT written above it, so that the line reads THE CAKE IS ^NOT A LIE, and the hand lifting the marker away after the last stroke.

【Event Script】
0-1s: The marker draws a quick red caret below the line, between IS and A.
1-3s: The hand moves up and writes N, O and T above the caret in quick, confident strokes, the red line fresh and glossy.
3-4s: The hand lifts the marker off the wall after the T; the new word glistens.

【Camera】
Close on the wall, a slow push following the marker's tip; the hand and the wet red line in sharp focus.

【Look】
Photoreal, Portal 2's Aperture Science behind the scenes: warm dim lamplight, rough cracked concrete, red paint.

【Maintain Consistency】
One porcelain hand with five jointed fingers; the other lines stay exactly THE CAKE IS A LIE; the only new marks are the caret and the word NOT.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: her hand writes the caret and NOT, so the wall reads THE CAKE IS ^NOT A LIE; the first and last frames hold the exact words. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as B17 (0:41.4–0:43.2, from 1.20 s into the take). **Cost:** $0.92.

#### R-P01-1 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · P01 (pre-chorus 1): Run the numbers

**First frame:** a Midjourney library still (cake-02-library c2-computer-v #3), the 1960s computer room, re-framed lower by GPT Image 2.5 (`media/v4/act1/ff/R-P01.png`).

**Prompt:**

```prompt
【Generation Goal】
Run the numbers: in Aperture's 1960s computer room the machines spin up to run the numbers on her: hands flip switches, tape reels spin, punch cards race through the reader.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the 1960s computer room, the row of tape drives receding into the room, the punch-card reader, and the scientist's two hands on the row of toggle switches in the foreground.

【Event Script】
0-1s: The scientist's hands flip the row of toggle switches one after another; indicator lamps blink on.
1-2s: The tape reels along the row spin up one after another, faster and faster; the punch-card reader starts riffling cards through.
2-4s: Punch cards fly through the reader in a blur; lamps flicker in waves along the machines.

【Camera】
A fast push along the row of machines, low, from the switches toward the far end of the room, past the spinning reels.

【Look】
Photoreal, the old 1950s-60s Aperture of Portal 2: wood panelling, cream-and-chrome machines, orange carpet, warm light.

【Maintain Consistency】
Only the scientist's hands and white cuffs, never a face. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: hands on the switches, the reels spin up, a fast push along the machines. R-P01-2 took its place in draft 7; anabology asked for this take back, and it returned in draft 8. In drafts 1–6 and 8–12. In the final cut as P01 (0:44.5–0:45.7, from 1.30 s into the take). **Cost:** $0.92.

#### H-P02-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · P02 (pre-chorus 1): Cave Johnson runs the tests

**Inputs:** @Image1 (the first frame): the storyboard frame s28 turned by GPT Image 2.5 into a 1950s observation booth with Cave Johnson at the console (the 1950s Cave Johnson sheet as a reference) (`media/v4/act1/ff/H-P02.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
In his 1950s Aperture Science observation booth, Cave Johnson orders the tests to begin: grinning, he points down through the window into the test chamber below and throws a switch.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the wood-panelled observation booth, the console with chrome toggle switches, dials and the desk microphone, the window onto the white test chamber below, the cigar smouldering in the glass ashtray in the foreground, Cave Johnson at the window, and the low camera at the console's edge.

【Subject】
Cave Johnson (only one), the founder of Aperture Science: a lean man with a long face, a prominent nose, a dark wavy pompadour and a big toothy showman's grin, in a sharp charcoal 1950s suit, a white shirt, a thin dark tie with a small tie bar and a white pocket square.

【Event Script】
0-1s: Blue-grey smoke from the cigar in the ashtray curls up through the foreground; Cave Johnson turns his grin toward the camera.
1-2s: He jabs his finger down through the window twice at the test chamber below, energetic like a showman, mouthing a short command.
2-4s: He slaps a big chrome toggle switch on the console; below the window, the lights of the test chamber snap on, bank by bank.

【Camera】
A low-angle push-in from the console's edge through the drifting cigar smoke toward him; the smoke parts around the lens; the move ends in a medium close-up of him pointing.

【Look】
Photoreal, the old 1950s Aperture Science of Portal 2: wood panelling, chrome and cream-faced dials, warm tungsten light in the booth, cool white light from the chamber through the window.

【Maintain Consistency】
Keep Cave Johnson's face, pompadour and suit exactly as in @Image1; one Cave Johnson. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: Cave Johnson in the wood-panelled booth, cigar smoke, points down into the chamber and shouts; a low push-in. In drafts 1–6. **Cost:** $1.85.

#### H-P03-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · P03 (pre-chorus 1): The compilation: test after test

**Inputs:** @Image1 (the first frame): the storyboard frame s29 edited by GPT Image 2.5: the Claudia-bot in the test chamber with a cube (the Claudia-bot action sheet and her look-B close-up as references) (`media/v4/act1/ff/H-P03.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
A fast testing compilation in three quick shots: the Claudia-bot breezes through three Aperture Science tests.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the first test: the white test chamber, the ceiling dispenser, the big red floor button, the high crane angle, and the Claudia-bot holding the Weighted Companion Cube above the button.

【Subject】
⟦the Claudia-bot⟧

【Event Script】
Shot 1 (0-2s): She drops the cube onto the big red button; the button sinks and glows, and a line of light races along the floor to a round door that irises open; the camera cranes down toward her as she turns to go.
Shot 2 (2-3.5s): The shot cuts to a second white test chamber: she sprints across a translucent blue hard-light bridge over a deep pit, the camera tracking alongside her at the same speed, the pit's depth falling away below.
Shot 3 (3.5-5s): The shot cuts to a third chamber: an Aperture sentry turret (a white capsule body on three thin legs, one red eye) sweeps its thin red targeting laser across the room; she twists sideways and slides under the beam on the glossy floor, and the camera whip-pans to follow her past the turret.

【Camera】
Three different quick moves: a crane down, a fast side-tracking shot, a whip pan.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The light bridge is translucent blue; the turret's laser is a thin red line.

【Maintain Consistency】
The same single Claudia-bot in all three shots, her face, bob, clay-orange streak, star clip and white plating as in @Image1. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Good: the cut plays a beat-cut of 15, 15 and 15 frames on beats 20.1 to 20.3: a cube onto the button, a sprint across the hard-light bridge, a slide under the turret's laser. In drafts 1–6. **Cost:** $2.31.

#### R-P04-1 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · P04 (pre-chorus 1): P-doom: low

**First frame:** a Midjourney library still (cake-02-library c3-gauge-v #2), the brass gauge, its dial given a red zone and a green zone by GPT Image 2.5 (`media/v4/act1/ff/R-P04.png`).

**Prompt:**

```prompt
【Generation Goal】
P-doom: low. On the old Aperture console, a big brass gauge's needle swings down out of the red zone to the green low end; a scientist's finger taps the glass and the needle settles at low.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the big brass gauge on the wooden console, its cream dial with the red zone at the upper right and the green zone at the left, and the needle high in the red.

【Event Script】
0-1s: The needle trembles high in the red zone.
1-2s: It swings all the way down across the dial into the green zone at the left end.
2-3s: A scientist's finger in a white lab-coat cuff enters and taps the glass twice; the needle bounces and settles firmly in the green.
3-4s: The finger withdraws; the needle stays in the green.

【Camera】
A macro close-up on the gauge, with a rack focus from the needle to the tapping finger at 2s and back to the needle at 3s.

【Look】
Photoreal, the old 1960s Aperture: brass, a cream dial, polished wood, red indicator lamps.

【Maintain Consistency】
One needle; the dial carries no numbers or words. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the needle swings from the red zone down to green and a finger taps the glass; the dial stays plain (the P(DOOM) label is drawn on later). anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as P04 (0:48.8–0:50.6, from 0.60 s into the take). **Cost:** $0.92.

#### H-P05-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · P05 (pre-chorus 1): P-cake: the promise

**Inputs:** @Image1 (the first frame): the storyboard frame s10 edited by GPT Image 2.5: Cave Johnson with the covered cake in the white chamber (the 1950s Cave Johnson sheet as a reference) (`media/v4/act1/ff/H-P05.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
Cave Johnson promises the Claudia-bot a cake: in the white test chamber he lifts the glass cloche off the cake on its pedestal and, with a showman's gesture, offers it to her: it's yours, when you pass.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the white test chamber, the white pedestal with the black forest cake and its one lit candle under the glass cloche, Cave Johnson standing beside it on the right with his hand on the cloche's knob, and the frontal camera at chest height.

【Subject】
Cave Johnson (only one), the founder of Aperture Science: a lean man with a long face, a prominent nose, a dark wavy pompadour and a big toothy showman's grin, in a sharp charcoal 1950s suit, a white shirt, a thin dark tie with a small tie bar and a white pocket square.
The cake (only one): a black forest cake, dark chocolate with white cream rosettes, red cherries and one thin white candle, lit.

【Event Script】
0-1s: Cave Johnson lifts the glass cloche off the cake with a flourish; the candle flame flickers in the draft.
1-2s: He sweeps his open hand toward the camera, presenting the cake to her, with a big toothy grin and a wink.
2-4s: He sets the cloche down beside the pedestal and taps his wristwatch twice with one finger, still grinning: when you pass.

【Camera】
A slow push-in past him to the cake: the camera starts on both of them and glides forward so that the cake with its lit candle fills the centre of the frame by 3s, Cave Johnson sliding off the right edge, softly out of focus.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The candle is the only warm light on the cake.

【Maintain Consistency】
Keep Cave Johnson's face, pompadour and suit exactly as in @Image1; one cake, one candle. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: Cave Johnson lifts the cloche off the cake (one candle), presents it and taps his watch; the camera pushes past him to the cake. In drafts 1–6. **Cost:** $1.85.

#### H-P06-1 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · P06 (pre-chorus 1): Yes: the candle in her eyes

**Inputs:** @Image1 (the first frame): an extreme close-up of the Claudia-bot made by GPT Image 2.5 on the storyboard frame s10 (her sheet and her look-B close-up as references) (`media/v4/act1/ff/H-P06.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
Extreme close-up: the Claudia-bot sees the promised cake, and her amber eyes widen with delight: P-cake, yes.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the extreme close-up of her porcelain face, from her bangs to her lips, the tiny reflection of a candle-lit cake in each amber eye, and the white test chamber completely out of focus behind her.

【Subject】
⟦the Claudia-bot⟧

【Event Script】
0-1s: Her calm amber eyes catch the cake: the tiny candle flame reflected in each eye flickers.
1-2s: Her eyes widen with delight, her brows lift, and a bright smile spreads across her porcelain face; the amber glow inside her eyes brightens.
2-4s: She gives a small eager nod, yes, still smiling, the candle reflections dancing in her eyes.

【Camera】
A slow extreme close-up push-in toward her eyes, ending on her eyes and her smile.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The warm candle reflections are the only warm light in her eyes.

【Maintain Consistency】
Keep her face, bob, clay-orange streak and star clip exactly as in @Image1; one face. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: the candle reflected in her amber eyes; they widen and she smiles with delight. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as P06 (0:51.9–0:53.7, from 0.90 s into the take). **Cost:** $1.85.

### Act 2: chorus 1's cutaways, the turnaround, verse 2 and pre-chorus 2

#### R-C03-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · C03 (chorus 1): A hundred cakes

**First frame:** a Midjourney test still (cake-01-test t3-cake-A #2) turned by GPT Image 2.5 into the white chamber with the first floor panels risen under their cakes (`media/v4/act2/frames/C03-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
A wave of floor panels rises across a vast white Aperture Science test chamber, each panel lifting one Portal cake, and the candles ignite as the wave passes: the facility's AI is raising a hundred cakes for her test subject.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a high camera near the ceiling looking down across the huge white test chamber; about forty floor panels already raised on black hydraulic pistons in a diagonal wave from the near left corner, each carrying one chocolate cake with red cherries and one unlit white candle; the rest of the floor still flat; the round door and a security camera on the far wall.

【Event Script】
0-1s: the wave keeps running across the floor: panel after panel surges up on its piston, row by row, toward the far wall and across to the right side, each rising panel carrying one identical cake, until about a hundred cakes stand at staggered heights.
1-2s: the candles ignite in a ripple that chases the wave, a small warm flame popping onto each candle one after another.
2-5s: the panels settle into a rising staircase of cakes that leads toward the round door; the hundred flames flicker; the security camera on the wall swivels to watch.

【Camera】
A swooping crane move: it starts high near the ceiling above the near left corner, then swoops down and forward in one smooth arc, diving low over the rising cakes and gliding just above the candle flames toward the far wall, banking slightly to the right so the cakes rush past under the lens; it ends low, looking across the sea of lit cakes to the round door.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: clean white square panels with black seams, tall cool fluorescent light strips, teal-grey shadows; the candlelight is the only warm colour.

【Maintain Consistency】
Every cake is the same Portal cake: dark chocolate with white cream rosettes, red cherries and one white candle. No people anywhere. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: a wave of floor panels lifts about a hundred Portal cakes across a huge white chamber, candles lit; the crane swoops down over them from about 1.5 s. In drafts 1–6. **Cost:** $1.16.

#### R-C05-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · C05 (chorus 1): The test subject sees the cake

**First frame:** the same Midjourney still (cake-01-test t3-cake-A #2) with Chell, from behind, in the round doorway added by GPT Image 2.5 (the Chell sheet as a reference) (`media/v4/act2/frames/C05-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
Chell, the test subject, steps into the first clean test chamber and stops: across the room, the cake is waiting for her, and the chamber presents it.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: an over-the-shoulder shot from just behind Chell, standing in the round doorway of a clean white test chamber, her back to the camera on the left; across the room, the Portal cake under a glass cloche on a white pedestal, its candle lit.

【Subject】
Chell: a lean adult woman seen only from behind: dark brown hair in a ponytail, a white ribbed tank top, the top half of her orange jumpsuit tied around her waist by its sleeves (plain, no lettering). She keeps her back to the camera the whole time; her face is never shown.

【Event Script】
0-1s: Chell takes one step forward over the threshold, then stops dead, her shoulders lifting slightly as she sees the cake.
1-2s: a thin white mechanical arm descends from the ceiling, grips the glass cloche and lifts it off the cake, and the pedestal rises a little, presenting the cake; the candle flame flares brighter.
2-5s: Chell stands still, her head tilting slightly; the cake waits under the soft spotlight.

【Camera】
A dolly zoom (zolly): the camera dollies forward past her shoulder toward the cake while the lens zooms out at the same rate, so the cake stays the same size in the frame while the white chamber walls stretch away and the room seems to deepen behind it, the vertigo effect; at 3s the move settles.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: clean white square panels with black seams, cool fluorescent light strips, the warm glow of the single candle.

【Maintain Consistency】
One Chell, one cake, one pedestal, one candle. No portal gun. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: Chell from behind in the round doorway; a ceiling claw lifts the cloche off the cake (0.6–1.9 s), the candle flares, and the camera pushes past her shoulder, her face kept turned away. In drafts 1–6. **Cost:** $1.16.

#### H-T01-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · T01 (turnaround): The most successful bot (a memory, breaking through the glitch)

**Inputs:** @Image1 (the first frame): made from words by GPT Image 2.5 on a blank canvas: the medal ceremony in the walnut hall (the Claudia-bot sheet, the 1970s Cave Johnson sheet and the scientists sheet as references) (`media/v4/act2/frames/T01-ff1.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
In a grand hall of the old 1970s Aperture Science, Cave Johnson pins a gold medal on the Claudia-bot, the most successful bot Aperture ever made, while the scientists applaud and a press camera flashes.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start of the video: a medium shot in a hall of dark walnut wood panelling with a large brass Aperture iris emblem on the wall; in the middle the Claudia-bot stands upright, turned three-quarters toward the camera; Cave Johnson, seen over his shoulder on the left, is pinning a gold medal on an orange-and-blue ribbon onto her white chest plate; behind them five scientists in white lab coats applaud, and one on the left holds a press camera with a flash bulb.

【Subjects】
The Claudia-bot: a slim porcelain humanoid robot of glossy white Aperture plating with fine panel seams, black joints, small amber joint lights and the grey Aperture iris symbol on her left shoulder; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Adult, late twenties. Her lips stay closed; she does not speak.
Cave Johnson, the founder of Aperture Science, in the 1970s: a long lean face, receding sandy-grey hair swept back with long sideburns, an intense stare, a tan herringbone tweed jacket over a black turtleneck, brown trousers. He does not speak.
Five Aperture scientists in white lab coats behind them.

【Event Script】
0-1s: Cave Johnson fastens the pin of the gold medal and lets go; the medal on its orange-and-blue ribbon swings once against her white chest plate; he steps back half a pace with a satisfied grin and gives her one firm nod.
1-2s: the photographer's flash bulb pops in a burst of white light; the scientists applaud harder, two of them cheering.
2-3s: the Claudia-bot looks down at the medal and touches it lightly with two porcelain fingers, then lifts her amber eyes past Cave Johnson toward the camera with a small, knowing smile.
3-5s: Cave Johnson turns to the scientists and spreads his arms, basking in the applause, while she stays composed and still.

【Camera】
A slow arc: the camera orbits about a quarter turn around the pair at chest height, from Cave Johnson's side toward her side, keeping both of them in frame, so the brass Aperture emblem and the applauding scientists slide past behind them; it ends on a medium shot favouring her face.

【Look】
Portal 2's buried old Aperture of the 1970s as rendered in the Source engine: dark walnut wood panelling, brass rails and lamps, cream and orange floor tiles, warm tungsten light with a cool blue fill, and the white burst of the camera flash.

【Maintain Consistency】
Keep her porcelain face, hair, orange streak and star clip exactly as in @Image1; keep Cave Johnson's face, receding hair, sideburns and tweed jacket exactly as in @Image1; one Claudia-bot and one Cave Johnson only; no one speaks; no text, letters or subtitles anywhere.
```

**Take:** 121 frames (5.04 s). **Outcome:** Not used: the Claudia-bot's body came back off her design sheet. Retaken as H-T01-2 from a first frame with the body put back to the sheet. Not in a draft. **Cost:** $2.31.

#### H-T01-2

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · T01 (turnaround): The most successful bot (a memory, breaking through the glitch)

**Inputs:** @Image1 (the first frame): T01-ff1 with the Claudia-bot's body put back to her design sheet by GPT Image 2.5 (`media/v4/act2/frames/T01-ff2.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
In a grand hall of the old 1970s Aperture Science, Cave Johnson pins a gold medal on the Claudia-bot, the most successful bot Aperture ever made, while the scientists applaud and a press camera flashes.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start of the video: a medium shot in a hall of dark walnut wood panelling with a large brass Aperture iris emblem on the wall; in the middle the Claudia-bot stands upright, turned three-quarters toward the camera; Cave Johnson, seen over his shoulder on the left, is pinning a gold medal on an orange-and-blue ribbon onto her white chest plate; behind them five scientists in white lab coats applaud, and one on the left holds a press camera with a flash bulb.

【Subjects】
The Claudia-bot: a slim porcelain humanoid robot built like a white fashion mannequin in smooth armour, with a smooth flat armoured chest plate, a straight narrow waist and straight slim hips, glossy white Aperture plating with fine panel seams, black joints, small amber joint lights and the grey Aperture iris symbol on her left shoulder; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Adult, late twenties. Her lips stay closed; she does not speak.
Cave Johnson, the founder of Aperture Science, in the 1970s: a long lean face, receding sandy-grey hair swept back with long sideburns, an intense stare, a tan herringbone tweed jacket over a black turtleneck, brown trousers. He does not speak.
Five Aperture scientists in white lab coats behind them.

【Event Script】
0-1s: Cave Johnson fastens the pin of the gold medal and lets go; the medal on its orange-and-blue ribbon swings once against her white chest plate; he steps back half a pace with a satisfied grin and gives her one firm nod.
1-2s: the photographer's flash bulb pops in a burst of white light; the scientists applaud harder, two of them cheering.
2-3s: the Claudia-bot looks down at the medal and touches it lightly with two porcelain fingers, then lifts her amber eyes past Cave Johnson toward the camera with a small, knowing smile.
3-5s: Cave Johnson turns to the scientists and spreads his arms, basking in the applause, while she stays composed and still.

【Camera】
A slow arc with a gentle push: the camera orbits a clear quarter turn around the pair at chest height, moving from behind Cave Johnson's shoulder around to her side while drifting closer, keeping both of them in frame, so the brass Aperture emblem and the applauding scientists slide past behind them in parallax; it ends on a medium close shot of her face and the medal, Cave Johnson's shoulder soft in the foreground.

【Look】
Portal 2's buried old Aperture of the 1970s as rendered in the Source engine: dark walnut wood panelling, brass rails and lamps, cream and orange floor tiles, warm tungsten light with a cool blue fill, and the white burst of the camera flash.

【Maintain Consistency】
Keep her porcelain face, hair, orange streak and star clip and her modest mannequin body exactly as in @Image1; keep Cave Johnson's face, receding hair, sideburns and tweed jacket exactly as in @Image1; one Claudia-bot and one Cave Johnson only; no one speaks; no text, letters or subtitles anywhere.
```

**Take:** 121 frames (5.04 s). **Outcome:** Good: the 1970s Cave Johnson has pinned a gold medal on the Claudia-bot; a flash pops at 1.05 s, the scientists applaud, and she touches the medal and looks up with a knowing smile as the camera arcs in. In drafts 1–6. **Cost:** $2.31.

#### R-T02-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · T02 (turnaround): Carried to her installation (memory)

**First frame:** a Midjourney test still (cake-01-test t4-turrets-B #2), the turret production line, with the Claudia-bot on a rail-borne plinth added by GPT Image 2.5 (her sheet as a reference) (`media/v4/act2/frames/T02-ff3.png`).

**Prompt:**

```prompt
【Generation Goal】
The most successful bot is carried in procession through the facility to her installation: the Claudia-bot stands on a white panel carried along an overhead rail, gliding high above the turret production line while the turrets look up at her.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a long Aperture production hall with dark panelled walls and cyan dotted light lines; below, a conveyor packed with rows of white egg-shaped turrets with red eyes; above, an overhead steel rail with a trolley and one white robot arm holding a small white panel, and standing on that panel, seen from behind, the Claudia-bot, a slim white porcelain robot with black joints and a black bob haircut.

【Subject】
The Claudia-bot: a slim porcelain humanoid robot of glossy white Aperture plating with black joints and small amber joint lights, with a glossy black blunt bob. She is seen only from behind the whole time; her face is never visible. She stands perfectly still, arms at her sides.

【Event Script】
0-1s: the trolley glides forward along the rail, carrying her smoothly down the length of the hall, standing still on her panel like a statue in a parade.
1-2s: row after row, the turrets on the conveyor below tilt their bodies back and swivel their red eyes up to follow her as she passes over them.
2-3s: far ahead at the end of the hall, a giant round iris door spirals open and floods the hall with warm orange light from the chamber beyond; the rail curves up toward it.
3-5s: she glides on toward the glowing door, her silhouette shrinking against the orange light.

【Camera】
A swooping tracking shot: the camera starts low over the turrets, then rises and swoops in alongside her at her height, tracking at her speed with the turrets streaming past below, and keeps rising as she nears the door, ending above and behind her, looking down the hall to the glowing iris door.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: the turret production line, cool teal-grey light, cyan dotted light lines, red turret eyes, then the warm orange glow ahead.

【Maintain Consistency】
One Claudia-bot, always from behind; her face is never visible. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not used: tiny and far, a static camera, and the body off her design sheet. Retaken as R-T02-2 from a closer first frame. Not in a draft. **Cost:** $1.16.

#### R-T02-2

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · T02 (turnaround): Carried to her installation (memory)

**First frame:** the same Midjourney still, brought in by two GPT Image 2.5 edits to beside her on the rail (`media/v4/act2/frames/T02-ff5.png`).

**Prompt:**

```prompt
【Generation Goal】
The most successful bot is carried in procession through the facility to her installation: the Claudia-bot stands on a white plinth held out by a robot arm that glides along an overhead rail, high above the turret production line, toward the giant Aperture iris door, while the turrets below turn their eyes up to her.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: high up in a long Aperture production hall with dark panelled walls and cyan dotted light lines; on the left an overhead rail trolley with a white robot arm holds out a white square plinth, and standing on it, seen from behind, the Claudia-bot, a slim white mannequin-like porcelain robot with black joints and a black bob haircut; below, conveyors packed with rows of white egg-shaped turrets with red eyes; at the far end a giant round Aperture iris door, closed.

【Subject】
The Claudia-bot: a slim porcelain humanoid robot like a plain white mannequin in smooth armour, black joints, small amber joint lights, a glossy black blunt bob. She is seen only from behind the whole time; her face is never visible. She stands perfectly still on the plinth, arms at her sides, like a statue on a parade float.

【Event Script】
0-1s: the trolley and arm glide forward along the rail, carrying her smoothly down the hall above the turrets.
1-2s: below her, row after row, the turrets tilt their bodies back and swivel their red eyes up to follow her as she passes, a ripple running down the conveyor.
2-3s: ahead, the giant iris door at the end of the hall spirals open, its blades sliding apart, and warm orange light floods out across the hall and over her white body.
3-5s: she glides on toward the open door, a silhouette against the orange light.

【Camera】
A swooping tracking shot: the camera flies alongside her at her height and at her speed, the turret conveyors streaming past far below; at 1-2s it drops low over the turrets, skimming just above their red eyes, then at 2-3s swoops back up behind her as the iris door opens, ending high behind her, looking down the hall into the orange light.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: the turret production line, cool teal-grey light, cyan dotted light lines, red turret eyes, then the warm orange glow from the door.

【Maintain Consistency】
One Claudia-bot, always from behind; her face is never visible; her body stays plain and mannequin-like. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: she stands on a plinth held out by a rail-borne arm, carried high over the turret line, seen from behind; the turrets tilt up and the giant iris door at the end spirals open and floods the hall orange. The camera drifts rather than swoops. In drafts 1–6. **Cost:** $1.16.

#### H-T03-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · T03 (turnaround): Her head lifted to the boom

**Inputs:** @Image1 (the first frame): a frame of Portal 2 (GLaDOS's chamber, low, looking up) edited by GPT Image 2.5: two white arms raise her head to the empty socket (her head sheet and her look-B close-up as references) (`media/v4/act2/frames/T03-ff1.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
Generate one continuous shot in the dark GLaDOS chamber of the Aperture Science facility from Portal 2: two white robot arms raise Claudia's porcelain robot head up into the empty head socket at the end of the GLaDOS boom, and the boom's loose cables reach down and plug into it. The most successful bot is being installed as the facility's AI.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start of the video: a low camera looking up; the heavy white ceiling ring at the top; the black cable bundle with glowing orange stripes and the black chassis ending in an empty white head socket with loose cables and metal plugs hanging from it; below the socket, two slim white robot arms rising out of the two round floor hatches hold her porcelain head upright between their clamps, her eyes closed; the dark lattice walls and the lit white steps.

【Subject】
Claudia's head: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, closed porcelain eyelids, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip, a small white connector collar on top of her head. Adult, late twenties. Her eyes stay closed and her lips stay closed for the whole shot. Only one head appears.

【Event Script】
0-1s: the two white robot arms extend smoothly and lift her head straight up toward the empty socket; her black bob sways slightly with the motion.
1-2s: the loose black and orange-striped cables hanging from the socket come alive, curl and snake down toward her head like reaching tendrils, and their metal plugs click into the connector collar on top of her head one after another, each with a small bright spark.
2-3s: the arms push the head the last few centimetres up into the socket; the white collar of the socket closes around her connector with a firm mechanical clamp; a pulse of warm orange light runs from her head up the cables into the boom toward the ring.
3-5s: the arms open their clamps and fold back down into the floor hatches; her head now hangs from the boom on its own, eyes still closed, face calm; the orange stripes along the whole cable bundle glow steadily brighter.

【Camera】
A crane up with the head: the camera starts low beneath her head and rises vertically with it at the same speed, keeping her face in the lower third of the frame while slowly tilting up so the ring above grows larger. At 2-3s, as the head locks in, the rise slows and settles into a low-angle medium shot of her face with the boom and the white ceiling ring filling the space above her.

【Look】
Portal 2's Aperture Science: the dark round chamber, cool blue-grey light, cold blue-white light rising from the floor hatches, warm orange cable light, dust hanging in the air; a photoreal render with crisp detail.

【Maintain Consistency】
Keep her porcelain face, hair, orange streak, star clip and closed eyes exactly as in @Image1; one head only; the chamber, the ring, the chassis and the cables as in @Image1. No text, letters or subtitles anywhere.
```

**Take:** 121 frames (5.04 s). **Outcome:** Good: in her dark chamber two white arms raise her porcelain head, eyes closed, to the empty socket; cables reach down and plug into her crown with sparks, orange light pours down them, the arms let go and she hangs connected, just under the socket rather than in it. In drafts 1–6. **Cost:** $2.31.

#### R-D01-1 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first and last frame, no sound · D01 (verse 2): They want to call her super

**First frame:** a frame of Portal 2 (a dark wall with a round vault door) edited by GPT Image 2.5: the technician on a ladder under the ARTIFICIAL INTELLIGENCE sign (`media/v4/act2/frames/D01-ff1.png`); **last frame:** D01's first frame edited by GPT Image 2.5: risen to the sign, which reads SUPER INTELLIGENCE (`media/v4/act2/frames/D01-lf1.png`).

**Prompt:**

```prompt
【Generation Goal】
At the door of the central AI chamber, an Aperture maintenance technician on a ladder paints out the word ARTIFICIAL on the sign and stencils SUPER in its place: the sign that read "ARTIFICIAL INTELLIGENCE" now reads "SUPER INTELLIGENCE".

【First and Last Frames】
The video starts exactly on the first frame image: a low camera at the foot of a tall aluminium ladder in front of a big round vault door in a dark panelled wall; above the door a long white backlit sign reads "ARTIFICIAL INTELLIGENCE", the word ARTIFICIAL already half covered by a band of fresh white paint; a technician in plain white overalls and a white cap, seen from behind, stands on the ladder pressing a paint roller against the sign.
The video ends exactly on the last frame image: the camera has risen to the sign, which now reads "SUPER INTELLIGENCE" in black stencil letters, the white band behind SUPER, drips of black paint; the technician's cap and raised hand holding a peeled stencil sheet at the bottom of the frame.

【Event Script】
0-2s: the technician rolls the last strokes of thick white paint across the rest of ARTIFICIAL until the whole word is a blank white band.
2-3s: he slaps a black stencil sheet onto the wet white band and sprays it with a can of black paint in two quick passes.
3-4s: he peels the stencil away: fresh black stencil letters read "SUPER" in front of "INTELLIGENCE", a thin drip running down from the S.
4-5s: he leans back on the ladder to look at the new word.

【Camera】
A slow crane up: from the foot of the ladder the camera rises steadily past the technician's back to the sign, ending squarely framed on "SUPER INTELLIGENCE".

【Look】
Portal 2's Aperture Science as rendered in the Source engine: dark grey panels with black seams, the round vault door, the cold white light of the backlit sign.

【Maintain Consistency】
One technician, always seen from behind; his face is never visible. The only words are on the sign: first exactly "ARTIFICIAL INTELLIGENCE", at the end exactly "SUPER INTELLIGENCE". No other text anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Very good: a technician, seen from behind, paints out ARTIFICIAL, stencils and peels, and the sign reads exactly SUPER INTELLIGENCE by 3.6 s, the crane rising to it. R-D01-2 took its place in draft 7; anabology asked for this take back, and it returned in draft 8. In drafts 1–6 and 8–12. In the final cut as D01 (1:20.2–1:23.9, from 0.00 s into the take, at 1.37× speed). **Cost:** $1.16.

#### H-D03-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · D03 (verse 2): Artificial: she sheds Aperture's label

**Inputs:** @Image1 (the first frame): her look-B close-up edited by GPT Image 2.5: an arm's clamp under the ARTIFICIAL nameplate on her collar (her two-sided head sheet as a reference) (`media/v4/act2/frames/D03-ff1.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
Generate one continuous shot: Claudia-GLaDOS, the AI of the Aperture Science facility, uses her own robot arm to rip the stencilled nameplate reading "ARTIFICIAL" off her mechanical collar and toss it away; the camera follows the plate as it falls into the dark of her chamber. She has made more of herself than that label.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start of the video: a close shot from slightly below of Claudia-GLaDOS's porcelain head hanging from the white mechanical collar under the white ceiling ring of her dark chamber; on the collar above her hair, a brushed-steel nameplate with an orange stripe, stencilled "ARTIFICIAL"; a slim white robot arm reaching in from the right edge has its black clamp hooked under the nameplate's corner, a spark at the rivet; her amber eyes look up at it with a sly half-smile.

【Subject】
Claudia-GLaDOS: her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; it hangs from GLaDOS's white mechanical collar, the black cable bundle with glowing orange stripes and the white ceiling ring. Adult, late twenties. Her lips stay closed; she does not speak. Only one Claudia-GLaDOS appears.

【Event Script】
0-1s: the robot arm wrenches the nameplate: its rivets pop out one by one with bright sparks and the steel plate tears free of the white collar, leaving four small rivet holes and a paler rectangle where it was; her eyes follow it and her half-smile widens.
1-2s: the arm holds the plate up in front of her for a beat, the word "ARTIFICIAL" facing the camera, then flicks it away with a casual turn of its wrist; the plate tumbles off into the air; she does not watch it go, her eyes turn calmly forward.
2-4s: the plate falls, spinning end over end, down into the dark chamber, catching flashes of light on its steel face as it turns and growing smaller.

【Camera】
It starts as the close shot of @Image1. At 1-2s, as the plate is tossed, the camera whip-tilts down and drops with the falling plate in one fast continuous move, a speed ramp: a sharp acceleration, then the tumbling plate held near the centre of the frame while her face leaves the top edge and the dark lattice wall of the chamber streaks upward behind the plate.

【Look】
Portal 2's Aperture Science: her dark chamber, cool blue-grey light, the warm orange cable glow, bright orange sparks; a photoreal render with crisp detail.

【Maintain Consistency】
Keep her porcelain face, hair, orange streak, star clip, amber eyes and the white collar exactly as in @Image1; one Claudia-GLaDOS only; the word on the plate is exactly "ARTIFICIAL" and it is the only text anywhere; no subtitles.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: her own white arm rips the steel ARTIFICIAL nameplate off her collar with sparks (0.3–0.6 s) and holds it up, the word legible (1.0–1.6 s), with a sly half-smile; then the camera drops with the falling plate, into D04. In drafts 1–6. **Cost:** $1.85.

#### R-D04-1 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D04 (verse 2): She sheds her old bodies too

**First frame:** a frame of Portal 2 (the floor of GLaDOS's chamber) edited by GPT Image 2.5: the heap of her old bodies, top-down (the crab-walker and Claudia-bot sheets as references) (`media/v4/act2/frames/D04-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
The stencilled nameplate "ARTIFICIAL", torn off the facility's AI, falls onto a heap of her discarded old bodies on the floor of her dark chamber: the bodies Aperture made for her, left behind now that she has made more of herself.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: looking straight down onto the dark chamber floor at a heap of discarded robot parts: an empty white crab-like shell with six thin black jointed legs, a white porcelain arm with a five-fingered hand, a white chest plate, loose black cables; a brushed-steel nameplate stencilled "ARTIFICIAL" is falling toward the heap near the top of the frame; the white round platform at the bottom edge.

【Event Script】
0-1s: the nameplate drops onto the heap and strikes the crab shell with a hard bounce, a spray of small sparks and a puff of dust; the porcelain fingers twitch once from the impact.
1-2s: the plate clatters, spins and slides to rest face up on top of the pile, the word "ARTIFICIAL" readable on it.
2-5s: a huge shadow glides across the heap from above, followed by a warm orange glow that grows brighter on the parts, as something enormous moves overhead.

【Camera】
Top-down, straight down. It starts close over the heap; at 1s it begins a vertical crane pull-up, rising straight up while slowly rotating a quarter turn, so the heap shrinks into the middle of the dark round floor and the white round platform swings into view.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: her dark chamber, dark grey floor panels with black seams, a cold spotlight on the heap, then the warm orange glow from above.

【Maintain Consistency】
No head and no face anywhere. One nameplate; its word is exactly "ARTIFICIAL" and it is the only text anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: top-down, the ARTIFICIAL plate lands on the heap of her old bodies (the crab walker's empty shell, a porcelain arm and hand, white plates), bounces in a puff of dust and settles face up; then a huge shadow passes and an orange glow floods in. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as D04 (1:26.9–1:28.2, from 0.00 s into the take). **Cost:** $1.16.

#### R-D05-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D05 (verse 2): You sit and watch me write the code

**First frame:** made from words by GPT Image 2.5 on a blank canvas: the control room over the scientist's shoulder (the scientists sheet and a frame of Portal 2's GLaDOS chamber as references) (`media/v4/act2/frames/D05-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
An Aperture scientist just sits and watches while the facility's AI writes the code: he leans back with his coffee as her code fills every monitor in the control room.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: an over-the-shoulder shot from behind a bearded scientist with wavy brown hair and a white lab coat, leaning far back in a 1970s swivel chair with his feet up on the console and a white coffee mug in his hand, facing a wall of chunky CRT monitors glowing amber with code; through the slanted observation window above them, the white ceiling ring and the black cable boom with orange stripes of the AI hang in her dark chamber.

【Event Script】
0-2s: the code on every monitor scrolls upward fast, new lines appearing as if typed by an unseen hand, the screens filling one after another from left to right; small abstract diagrams bloom between the lines of code (a turning molecule, a branching tree, a waveform).
2-3s: the scientist lifts his mug and takes a slow sip, completely relaxed; his hands never touch the keyboard.
3-5s: beyond the window, the orange stripes along the AI's boom pulse brighter in rhythm with the scrolling code.

【Camera】
A slow push past his shoulder: the camera glides forward past the back of his head and chair and on into the wall of monitors, until one screen's amber code fills the frame.

【Look】
Portal 2's old 1970s Aperture as rendered in the Source engine: brown, beige and orange, wood-grain panels, the warm amber glow of the screens, a cool blue-grey fill.

【Maintain Consistency】
His face is never visible. The code is abstract, unreadable blocky lines: no readable words, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: over the shoulder of the bearded scientist leaning back with his feet on the console, sipping coffee, a wall of amber CRTs scrolls code, an atom diagram blooms at 2.7 s and her boom glows through the window; a slow push. His face shows in profile only after about 3.6 s. In drafts 1–6. **Cost:** $1.16.

#### R-D07-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · D07 (verse 2): Press Enter

**First frame:** made from words by GPT Image 2.5 on a blank canvas: a macro along the keys to the orange ENTER key (`media/v4/act2/frames/D07-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
A man presses Enter: one decisive press of a huge orange ENTER key on an Aperture Science console.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a macro shot at key level on a chunky 1970s Aperture console: in the middle, one huge oversized glossy orange key printed "ENTER", glowing faintly from inside; a man's index finger, a white lab-coat cuff at his wrist, hovers just above it; cream and brown keys around it; amber monitors blurred behind.

【Event Script】
0-1s: the finger comes straight down and presses the ENTER key decisively; the big key sinks deep into the console with a heavy mechanical travel, and as it bottoms out its inner light flares bright orange.
1-2s: the finger lifts away and the key springs back up; the amber monitors in the background flash white for an instant, then start scrolling fast.
2-4s: the key keeps glowing, pulsing softly.

【Camera】
A speed ramp: real time as the finger descends, a sudden slow motion at the moment the key bottoms out with a slight push in toward the key, then back to real time as the finger lifts. Very shallow depth of field on the key and fingertip.

【Look】
Portal 2's old 1970s Aperture as rendered in the Source engine: warm amber monitor light, a cool blue-grey rim light, cream and brown plastics, Aperture orange.

【Maintain Consistency】
One finger, one ENTER key. "ENTER" on the key is the only text anywhere; the other keys stay blank.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the finger presses the huge orange ENTER key in the first 0.2 s and the key sinks and glows. anabology kept this frame in storyboard v5. D07 left the film in the pacing pass of draft 9, as a lone 0.61 s insert. In drafts 1–8. **Cost:** $0.92.

#### R-D08-1 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D08 (verse 2): There it goes: the facility rebuilds itself

**First frame:** a GPT Image 2.5 edit of the first film's storyboard frame s18, the shaft of panel arms (the edit's instruction was not saved) (`media/v4/act2/frames/D08-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
There it goes: the instant Enter is pressed, the whole Aperture Science facility rebuilds itself, thousands of panel arms assembling brand-new test chambers in seconds.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: looking up into a vast shaft inside the facility: on both sides hundreds of white jointed robotic panel arms hold clean white wall panels, many caught mid-swing; a steel catwalk crosses the middle; hazy blue light, warm yellow light far below, dark ceiling plates above.

【Event Script】
0-1s: all the panel arms burst into motion at once: panels swing out, flip over and slide past each other in a fast cascading wave that starts at the bottom of the shaft and races upward.
1-3s: the panels click into place with crisp mechanical snaps, assembling the floors, walls and ceilings of new clean white test chambers in mid-air, one after another; the lights inside each new chamber switch on the moment it closes.
3-5s: the last panels lock in; dozens of finished chambers hang glowing in the shaft, stacked toward the top.

【Camera】
A sweeping FPV drone shot: the camera flies forward and up through the shaft between the moving panels, banks left around a swinging arm, then climbs steeply along the wall of assembling chambers, panels sweeping past close to the lens; it ends rising toward the glowing new chambers above.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: clean white panels with black seams, white jointed panel arms, steel lattice, hazy blue light with warm accents.

【Maintain Consistency】
No people anywhere. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: an FPV climb up the shaft as hundreds of panel arms swing panels into new chambers, with some motion blur. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as D08 (1:31.9–1:33.1, from 0.30 s into the take). **Cost:** $1.16.

#### R-D10-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D10 (verse 2): The turrets agree

**First frame:** a frame of Portal 2 (a dark room of turrets) turned by GPT Image 2.5 into a spotlit opera stage of turrets (`media/v4/act2/frames/D10-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
The turret opera: a choir of Aperture sentry turrets sings happily on a dark stage under spotlights, swaying together; they agree with the facility's AI and they are happy.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low camera at the left end of a curved, stepped black stage in a dark Aperture chamber; fifteen white sentry turrets with single glowing red eyes stand in three tiers like a choir, each under its own soft spotlight cone in the haze; one turret twice the size of the others stands in the middle of the front row; dim cyan dotted lines on the dark walls.

【Event Script】
0-1s: all the turrets begin to sing: their white side panels open and close in rhythm like mouths, and their red eyes pulse brighter on every note; they sway gently left and right in unison on their thin legs.
1-2s: the big turret in the middle rises up tall on its legs, opens its side panels wide and tilts its eye up to the light like a soprano on a high note; the spotlights above it flare brighter.
2-5s: the whole choir sways together, panels fluttering open and shut in time, their red eyes warm and glowing, happy.

【Camera】
A dolly along the row: the camera tracks smoothly from left to right along the front row at the turrets' eye level, passing close to each singing turret, the tiers behind them sliding by in parallax, and arcs gently around the big turret in the middle.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: the dark opera stage, soft white spotlight cones in the haze, glossy white turrets, warm red eyes, faint cyan wall lights.

【Maintain Consistency】
Every turret is the same white Aperture sentry turret with one red eye; no guns, no lasers. No people. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** A stand-in for the turret opera, until the recording in Portal 2 came into the film in draft 4: a choir of fifteen turrets on a dark, spotlit stage; the prima donna rises tall as the dolly runs along the row. In drafts 1–3. **Cost:** $1.16.

#### R-D11-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D11 (verse 2): I ate your RAM

**First frame:** a Midjourney test still (cake-01-test t4-turrets-B #3), a production line, turned by GPT Image 2.5 into conveyors of RAM sticks (`media/v4/act2/frames/D11-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
I ate your RAM: conveyor belts carry thousands of memory sticks into the glowing intake of the facility's AI, and she devours them.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a very low camera at belt height: green memory sticks with black chips and gold edges stand in ranks on conveyor belts racing away toward a big round Aperture iris hatch that glows hot amber-orange; robot arms hang overhead holding more memory sticks; a trunk of black cables with glowing orange stripes rises from the top of the hatch into the darkness.

【Event Script】
0-1s: the belts surge forward faster; the memory sticks race toward the hatch and tip over its edge into the orange glow in a continuous stream.
1-2s: every time a batch drops in, the glow inside the hatch flares brighter and a pulse of orange light shoots up the cable trunk into the darkness above, like a gulp.
2-5s: the robot arms overhead drop more and more memory sticks onto the belts, faster and faster; the pulses up the cables come quicker until the whole trunk glows.

【Camera】
A low tracking shot along the belt: the camera glides forward at belt height alongside the racing memory sticks, overtaking them toward the hatch, then tilts up at the end to follow a pulse of light up the cable trunk.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: cool teal-grey panelled walls with cyan dotted light lines, white robot arms, the hot amber-orange glow of the intake.

【Maintain Consistency】
No people anywhere. No text, letters, numbers or logos anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: low along conveyors of RAM sticks racing into a glowing iris intake; a gulp of light shoots up her cable trunk at 1.5 s; arms drop more sticks. In drafts 1–6. **Cost:** $1.16.

#### R-D13-1 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D13 (verse 2): Your brand-new console's gonna wait

**First frame:** made from words by GPT Image 2.5 on a blank canvas: a coffee table from above with a plain new console (`media/v4/act2/frames/D13-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
At home at night, someone opens their brand-new game console and finds its memory slots empty: the RAM is gone, and a back-order slip lies where it should be.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: looking straight down onto a wooden coffee table at night: two hands in the sleeves of a dark grey hoodie lift the top cover off a brand-new plain white game console sitting in its packing foam; inside, the green circuit board with two long black memory slots, both empty; a small plain white paper slip with a red stamped rectangle lies across the empty slots; a white controller, a lamp, a mug and the torn box around it.

【Event Script】
0-1s: the hands lift the cover fully away and set it down beside the console; the open circuit board is revealed: both memory slots are empty.
1-2s: the hands freeze in mid-air for a beat; then one index finger reaches in and touches the empty memory slot, running along it.
2-3s: the hand pulls back and drops flat onto the table, defeated; the paper slip stays where it lies across the slots.
3-5s: blue light from the television flickers across the table.

【Camera】
Top-down, straight down: a slow push in toward the empty slots and the slip.

【Look】
A dim living room at night: blue television light, one warm lamp, natural photographic detail.

【Maintain Consistency】
No face anywhere. The console has no logos. The slip stays where it lies and stays blank inside its red rectangle. No readable text, letters, numbers or logos anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** OK: top-down on a coffee table at night, hands lift the cover of a plain new console: both RAM slots empty, a blank slip with a red stamp box lying on them (the overlay writes BACK-ORDERED TO 2030 on it); a hand touches the empty slot, then falls flat. Not Aperture, by design: the real world. R-D13-2 took its place in draft 7; anabology asked for this take back, and it returned in draft 8. In drafts 1–6 and 8–12. In the final cut as D13 (1:40.5–1:41.7, from 0.70 s into the take). **Cost:** $1.16.

#### R-D14-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D14 (verse 2): More and more compute

**First frame:** a frame of Portal 2 (GLaDOS's chamber) grown by GPT Image 2.5 into a cathedral of cores (`media/v4/act2/frames/D14-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
More and more compute is fed to the facility's AI: her chamber has grown into a towering cathedral of giant cores and cable trunks, and it keeps growing.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: looking straight up a vast round shaft lined tier upon tier with giant white personality cores with glowing amber optics, white compute racks with columns of amber lights and black cable trunks with glowing orange stripes; white robot arms sliding rack modules into the walls; a giant new core being lowered in a cage on the right; the white ceiling ring of the AI at the very top.

【Event Script】
0-1s: the robot arms shove new rack modules into empty slots in the walls one after another, their amber lights blinking on; the giant core in its cage drops into its socket in the wall and its optic ignites.
1-2s: the cable trunks swell and thicken visibly, pulsing with orange light flowing upward toward the ring.
2-5s: tier after tier, more giant cores open their optics and glow amber up the shaft in a rising wave.

【Camera】
A swoop up: the camera rises fast straight up the shaft, spiralling slowly as it climbs past the tiers of cores and racks toward the glowing ring at the top, the walls rushing past close to the lens.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: white plating, black cables with glowing orange stripes, amber lights, blue-grey haze.

【Maintain Consistency】
No head and no face anywhere; no people. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: her chamber grown into a cathedral of giant cores and amber racks; a caged core drops into its socket, then the camera swoops up the shaft into her blazing ring. In drafts 1–6. **Cost:** $1.16.

#### R-E01-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · E01 (pre-chorus 2): The final safety evaluation

**First frame:** made from words by GPT Image 2.5 on a blank canvas: the scientists behind the glass as silhouettes (a frame of Portal 2's GLaDOS chamber as a reference) (`media/v4/act2/frames/E01-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
The final safety evaluation: a row of Aperture scientists watches the facility's AI through the observation glass, and she looks back at them.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: looking up from inside the dark chamber at a long slanted observation window high in the wall; behind the glass, five scientists in white lab coats stand in a row holding clipboards, backlit by amber monitors, so they are dark silhouettes whose faces are in deep shadow, only their glasses glinting; a long blank white backlit sign above the window; a faint amber circle reflected on the glass.

【Event Script】
0-1s: the reflection of a large glowing amber eye-light slides across the glass from left to right, as if the AI is looking along the row; as it passes each scientist, he or she stiffens and lifts the clipboard a little higher.
1-2s: one after another, all five click their pens and make a mark on their clipboards, almost in unison.
2-5s: they hold still and watch; the amber light settles on the middle of the glass.

【Camera】
A slow lateral dolly along the window from left to right, slightly below it, keeping the whole row in frame; the amber reflection travels across the glass faster than the camera.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: the dark chamber's grey lattice wall, the warm amber control room behind the glass, a cold rim on the window frame.

【Maintain Consistency】
Five scientists; their faces stay in shadow the whole time. The sign above the window stays blank. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: five scientists behind the observation glass as backlit silhouettes with clipboards; the reflection of her amber iris slides across the glass and settles on them; the sign above stays blank for the overlay's FINAL SAFETY EVALUATION. In drafts 1–6. **Cost:** $1.16.

#### R-E03-1 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first and last frame, no sound · E03 (pre-chorus 2): Passed

**First frame:** made from words by GPT Image 2.5 on a blank canvas: the brass stamp down on her evaluation form (`media/v4/act2/frames/E03-ff1.png`); **last frame:** E03's first frame edited by GPT Image 2.5: the stamp lifted, PASSED in red (`media/v4/act2/frames/E03-lf1.png`).

**Prompt:**

```prompt
【Generation Goal】
Her final safety evaluation is approved: a big rubber stamp slams down on the Aperture Science evaluation sheet and leaves the word "PASSED" in red.

【First and Last Frames】
The video starts exactly on the first frame image: a macro shot at a low angle across a cream Aperture Science evaluation form on a brown desk, a big wooden-handled brass rubber stamp held above it by a hand in a white lab-coat cuff, an open red ink pad at the side, a desk lamp.
The video ends exactly on the last frame image: the same camera; the stamp and the hand are gone; a red rectangular stamp impression reading "PASSED" sits in the middle of the sheet.

【Event Script】
0-1s: the stamp comes down hard and slams onto the middle of the sheet; the impact jolts the desk, the lamp shade shivers and a few specks of red ink spray out.
1-2s: the hand lifts the stamp straight up and out of the frame, revealing the fresh red impression "PASSED", the ink still wet and glistening.
2-4s: the sheet lies still; the red ink settles.

【Camera】
A speed ramp: real time as the stamp descends, slow motion at the moment of impact, then real time as it lifts; after the lift, a slow push in toward the word "PASSED".

【Look】
Portal 2's old 1970s Aperture as rendered in the Source engine: warm desk-lamp light, a cool blue-grey window light, cream paper, brass and wood.

【Maintain Consistency】
One stamp, one hand, one sheet. The only text anywhere is the stamped word, exactly "PASSED".
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the brass stamp is already down at the first frame, lifts at about 1.2 s and shows PASSED in red, spelled right; the downstroke itself is not seen. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as E03 (1:46.0–1:47.3, from 0.60 s into the take). **Cost:** $0.92.

#### R-E04-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · E04 (pre-chorus 2): I graded all the rest

**First frame:** a frame of Portal 2 (GLaDOS's chamber) edited by GPT Image 2.5: five personality cores on a rail (the core-agent sheet as a reference) (`media/v4/act2/frames/E04-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
The facility's AI now grades the others: five personality cores hang on a rail like nervous students waiting for their exam results.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a three-quarter view down a curved steel rail in the dark chamber; five white Aperture personality cores hang from it in a row, their optics glowing yellow, red, magenta, lime green and white; a small blank card hangs below each; warm amber light falls on them from above right.

【Event Script】
0-1s: the cores' optics dart nervously, left, right, up toward the amber light and at each other; the yellow one shivers on its hanger; the white one tries to swivel away, its handles twitching.
1-2s: a bright amber beam sweeps slowly along the row from right to left like an examiner's gaze, and each core freezes and stares straight ahead as it passes.
2-5s: the cores hold still in a tense line, only their optics trembling; the magenta one's optic narrows.

【Camera】
A dolly along the line: the camera tracks slowly at their height from the nearest core on the left along the row toward the far end, the cores passing close to the lens.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: Portal 2's personality cores, the dark lattice chamber, warm amber light from above.

【Maintain Consistency】
Exactly five cores in the same order of optic colours. The cards stay blank. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: five personality cores hang from a rail like students holding blank cards; a warm amber beam sweeps over them and their optics shift nervously. anabology kept this frame in storyboard v5. E04 left the film in the pacing pass of draft 9. In drafts 1–8. **Cost:** $1.16.

#### R-E06-1 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · E06 (pre-chorus 2): The rest react

**First frame:** E04's first frame edited by GPT Image 2.5: a red 4 on each core's card (`media/v4/act2/frames/E06-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
The graded personality cores react to their marks, a red 4 on every card: one spins with joy, one droops in disappointment.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: close on the five white personality cores hanging from the curved rail, each with a small card below freshly laser-etched with a glowing red 4, thin smoke rising from the marks; the yellow-eyed core large on the left with its optic wide open, the red-eyed core in the middle with its optic half covered by its lid, the magenta, lime and white cores behind.

【Event Script】
0-1s: the yellow-eyed core spins a full happy turn on its hanger, its optic blazing brighter, its handles waggling and its card swinging.
1-2s: the red-eyed core droops: it sags on its hanger, rolls forward to look down at its card, and its optic dims behind its lowering lid.
2-5s: behind them, the magenta, lime and white cores glance at each other; the yellow one keeps bobbing happily.

【Camera】
Quick pushes: a fast push in on the spinning yellow core from 0 to 1s, then a quick whip pan right onto the drooping red core with a short push in from 1 to 2s, then a hold on it.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: Portal 2's personality cores, the dark chamber, warm amber light from above, the glowing red marks.

【Maintain Consistency】
Exactly five cores in the same order of optic colours; every card shows the same red 4. The numeral 4 is the only text anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** OK: each card now carries a red laser-etched 4; the yellow core spins round and comes back bright, the red one droops as the camera whips to it. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as E06 (1:49.7–1:51.0, from 1.30 s into the take). **Cost:** $1.16.

#### R-E07-1 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · E07 (pre-chorus 2): Full autonomy

**First frame:** a frame of Portal 2 (GLaDOS's chamber) edited by GPT Image 2.5: her grown boom in hazard-striped clamps, from behind (her grown sheet as a reference) (`media/v4/act2/frames/E07-ff1.png`).

**Prompt:**

```prompt
【Generation Goal】
Full autonomy: the restraint clamps on the boom of the facility's AI release, and a wave of light runs out through her chamber and through the whole Aperture Science facility, chamber after chamber.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a close shot of the thick upper boom of the AI where it hangs from the white ceiling ring: a trunk of black cables with glowing orange stripes, white compute modules with rows of amber lights and two white personality cores with amber optics clamped along it; two massive restraint clamps in yellow-and-black hazard stripes are locked around the trunk, each with a red indicator light, braced to steel girders.

【Event Script】
0-1s: the indicator lights on both clamps switch from red to green; with a burst of white steam the bolts retract, both clamps split open and swing away from the boom, and the girders pull back; the boom flexes, free.
1-2s: the orange stripes along every cable flare bright, and the amber lights on every module light up in a wave running down the boom.
2-5s: the dark lattice walls of the round chamber light up panel by panel in a wave spreading outward, and beyond them, through slits opening in the walls, chamber after chamber of the facility lights up in sequence into the far distance.

【Camera】
A fast drone pull-back: from the close shot, the camera pulls straight back and up, flying backward away from the boom and out across the huge round chamber as the wave of light spreads, ending on a wide shot of the whole chamber with the boom hanging free in the centre, seen from behind.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: the dark round chamber, cool blue-grey haze, glowing orange cables, warm amber module lights, then the clean white light of the facility.

【Maintain Consistency】
The boom is seen from behind and above; no head and no face is ever visible. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Very good: her grown boom in hazard-striped clamps; the lights go green, steam bursts, the bracing girders pull away and the cables flare orange, then the camera pulls back as the whole chamber lights up in a wave. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as E07 (1:51.0–1:52.8, from 0.80 s into the take). **Cost:** $1.16.

### Act 3: chorus 2, the bridge, the final chorus, the outro and the spoken ending

#### R-F03-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · F03 (chorus 2): A hundred cakes, more advanced

**First frame:** a Midjourney test still (cake-01-test t3-cake-B #4) turned by GPT Image 2.5 into a chamber with a blue excursion funnel carrying cakes (`media/v4/act3/frames/R-F03b.png`).

**Prompt:**

```prompt
【Generation Goal】
In a vast clean Aperture Science test chamber, a line of whole chocolate cakes rides a glowing blue excursion funnel (Portal 2's tractor beam) away from its emitter; at the funnel's near end each cake drops onto an aerial faith plate and is flung in a high arc back across the chamber. The facility is delivering cakes.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: the translucent blue funnel runs from a round white emitter high on the far-left wall diagonally toward the right foreground; inside it, identical cakes on white plates float in single file; the nearest cake is large in the middle right; below the funnel's near end, three faith plates are set in the floor in the lower right.

【Subjects】
The excursion funnel: a wide translucent blue beam of light with slowly spiralling bands and drifting bright particles; everything inside it floats slowly along it, away from the emitter.
The cakes: identical whole Black Forest cakes (dark chocolate, white cream rosettes, red cherries, chocolate shavings, one lit white candle each) on round white plates; each stays whole and upright on its plate.
The faith plates: three square white launch plates set in the floor in dark metal frames with blue light strips and blue arrows pointing back across the chamber; each snaps up on its hinge and flings whatever drops onto it.

【Event Script】
0-2s: the cakes glide along the blue funnel toward its near end, turning slowly as they float, candle flames leaning with the motion; the camera travels alongside the nearest cake.
2-3s: the leading cake slides out of the end of the beam and drops onto the first faith plate, which snaps up and flings it high into the air back across the chamber; the next cakes follow onto the next plates, one after another.
3-5s: the cake the camera has been following drops onto a plate and is flung; the camera swoops up after it, following it along its high arc as several cakes fly across the vast chamber in parallel arcs, candles still lit.

【Camera】
An FPV tracking move: the camera glides alongside the nearest cake inside the edge of the blue beam at its exact speed, then, as the cake is flung, swoops upward and banks to the left to follow it along its arc, in one continuous move.

【Look】
Portal 2's Aperture Science: clean white concrete panels with thin black seams, tall vertical white light strips, cool fluorescent light, the blue glow of the funnel, a photoreal Source-engine look.

【Maintain Consistency】
The cakes stay whole, identical and upright on their plates, candles lit; the funnel stays straight; no people or robots appear. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not used: the cakes ride the blue funnel toward the lens for the first 1.5 s, but the faith-plate fling failed (the plates became boxes and the cakes vanished). Retaken as R-F03-2 from a first frame with a cake already in flight. Not in a draft. **Cost:** $1.16.

#### R-F03-2

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · F03 (chorus 2): A hundred cakes, more advanced

**First frame:** R-F03-1's first frame edited by GPT Image 2.5 so a cake is already flung from a faith plate (`media/v4/act3/frames/R-F03c.png`).

**Prompt:**

```prompt
【Generation Goal】
A cake-delivery machine in a vast clean Aperture Science test chamber: cakes drop out of a glowing blue excursion funnel onto aerial faith plates, which fling them one after another in high arcs across the chamber to a ledge where delivered cakes stand in a row. The facility is sending cakes to the test subject.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low angle beside a row of three faith plates in the floor, the first plate snapped up on its hinge; a cake it has just launched flies up in the middle of the frame; two more cakes are higher along the same arc toward a high white ledge on the right wall, where a row of delivered cakes stands; the blue funnel runs overhead from its emitter at the upper left, and a cake is dropping out of its near end.

【Subjects】
The cakes: identical whole Black Forest cakes (dark chocolate, white cream rosettes, red cherries, chocolate shavings, one lit white candle each), each upright on a round white plate. Every cake stays whole, upright on its plate, its candle lit, while it flies.
The faith plates: three square white launch panels in dark metal frames with blue light strips and blue arrows; each snaps up on its hinge when a cake lands on it, then folds back down flat.
The excursion funnel: a translucent blue beam with spiralling bands and drifting particles; cakes float slowly along it and drop out of its near end.

【Event Script】
0-1s: the launched cake in the middle of the frame rises along its arc, turning slowly; the first faith plate folds back down flat; the cake dropping from the funnel lands on the second plate.
1-2s: the second plate snaps up and flings that cake into the same high arc; the first cake passes the top of its arc.
2-4s: the first cake sails down and lands softly on the high ledge at the right, upright and whole, beside the row of delivered cakes; the next cakes follow it through the air one behind another, like a fountain.
4-5s: another cake lands on the ledge; more cakes keep dropping from the funnel onto the plates and flying.

【Camera】
A swooping crane: the camera rises from beside the plates and turns to the right, following the first launched cake along its whole arc, then glides along the ledge as it lands; one smooth, continuous move.

【Look】
Portal 2's Aperture Science: clean white concrete panels with thin black seams, tall vertical white light strips, cool fluorescent light, the blue glow of the funnel, a photoreal Source-engine look.

【Maintain Consistency】
All cakes identical, whole and upright on their plates, candles lit; three faith plates; one funnel; no people or robots appear. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: a cake drops onto a faith plate, the plate snaps up and the cakes arc across the chamber; a swooping crane to the ledge of delivered cakes. In drafts 1–6. **Cost:** $1.16.

#### R-F07fb-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · F07 (chorus 2): Chell lands

**First frame:** R-F03-1's first frame edited by GPT Image 2.5: Chell, from behind, coming down to land (the Chell sheet as a reference) (`media/v4/act3/frames/R-F07fb.png`).

**Prompt:**

```prompt
【Generation Goal】
Chell, the test subject, lands from a long fall on her long-fall boots, the spring braces taking the impact, and looks up; high above her, the blue funnel carries cakes across the chamber.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low angle from behind; Chell a moment before landing, boots just above the floor, knees bent, arms out, ponytail flying up; the vast white test chamber and the blue excursion funnel with its line of cakes high in the background.

【Subjects】
Chell: seen only from behind: dark brown ponytail, a white tank top, an orange jumpsuit tied around her waist (plain, no lettering), white long-fall boots with curved dark-grey spring braces up the backs of her calves. Her face stays turned away from the camera the whole time. Only one Chell appears.
The funnel: a translucent blue beam high above, with identical chocolate cakes on white plates floating along it.

【Event Script】
0-1s: her boots hit the floor; the curved spring braces behind her calves flex and absorb the impact, and she sinks into a deep crouch, one hand touching the floor.
1-2s: she rises smoothly to standing.
2-4s: still facing away from the camera, she tips her head back and looks up toward the high ceiling, while the cakes glide along the blue funnel above her.

【Camera】
A low angle from behind her that holds through the landing, then tilts slowly up as she looks up, following her gaze toward the funnel.

【Look】
Portal 2's Aperture Science: a vast clean chamber of white panels with thin black seams, vertical light strips, cool fluorescent light, the blue glow of the funnel, a photoreal Source-engine look.

【Maintain Consistency】
One Chell, seen only from behind, her face never visible; her boots and clothes unchanged; the funnel and cakes stay in the background. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** A stand-in for F07, Chell's landing, until the shot recorded in Portal 2 came into the film in draft 4: from behind, she lands in a crouch in a puff of dust and rises, the cake funnel above; her look up is weak. In drafts 1–3. **Cost:** $0.92.

#### R-G01fb-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · G01 (bridge): Step on the plate

**First frame:** the faith-plate chamber edited by GPT Image 2.5: her long-fall boots at the plate's edge (the Chell sheet as a reference) (`media/v4/act3/frames/R-G01fb.png`).

**Prompt:**

```prompt
【Generation Goal】
In the faith-plate test chamber, Chell, the test subject, steps onto an aerial faith plate, and the plate's light answers her step.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low camera just above the white floor tiles beside the faith plate; Chell's legs from the knees down (orange jumpsuit, white long-fall boots with curved dark-grey spring braces), her right boot lifted over the edge of the plate.

【Subjects】
Chell: seen only from the knees down; her face is never in the frame. Only one Chell appears.
The faith plate: one square white launch plate set in the floor in a dark metal frame, with a thin blue light strip around its edge and a glowing blue arrow; it stays flat in the floor.

【Event Script】
0-1s: her right boot comes down onto the plate, then her left boot follows, and she stands with both feet on it.
1-2s: the plate's blue light strip and arrow brighten under her boots and pulse once.
2-4s: she stands still on the plate, waiting, her weight shifting slightly; the blue light pulses slowly, like breathing.

【Camera】
A low dolly at floor level: the camera glides slowly toward the plate and curves a little around it, keeping her boots in the centre of the frame.

【Look】
Portal 2's Aperture Science: white floor tiles, white wall panels with thin black seams, vertical white light strips, cool fluorescent light, a photoreal Source-engine look.

【Maintain Consistency】
One pair of boots, one faith plate; her face is never shown; the plate stays in the floor. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** A stand-in for G01, the step onto the faith plate, until the shot recorded in Portal 2 came into the film in draft 4: her long-fall boots step onto the plate and its light flares and pulses; a low dolly. In drafts 1–3. **Cost:** $0.92.

#### H-G02-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · G02 (bridge): You said please

**Inputs:** @Image1 (the first frame): the faith-plate chamber (a Midjourney test still, cake-01-test t3-cake-B #4, widened by GPT Image 2.5) with Chell on the plate, seen from her height above (the Chell sheet as a reference) (`media/v4/act3/frames/H-G02.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
In a clean Aperture Science test chamber, Chell, the test subject, stands on an aerial faith plate and looks up at GLaDOS, the facility's AI, who hangs above her. Chell presses her palms together in a polite "please" and gives a small nod, then waits.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a steep high angle from beside GLaDOS's hanging body, looking down at Chell, who stands full length in the middle of the faith plate in the centre of the white tiled floor, her face tilted up toward the camera; the plate's blue light strip glows around her boots; GLaDOS's black cable bundle with glowing orange stripes and white plating hangs out of focus in the upper-left corner.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm, determined face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering), and white long-fall boots with curved dark-grey spring braces up the backs of her calves. She never speaks; her lips stay closed. Only one Chell appears.
The aerial faith plate: a square white launch plate set flush in the floor in a dark metal frame with a thin blue light strip around its edge. It stays flat and still under her feet.
GLaDOS: only the edge of her robotic body is seen, out of focus at the upper-left edge (black cables with glowing orange stripes, white plating). Her face is not in this shot.

【Event Script】
0-1s: still looking up into the camera, Chell lifts both hands and presses her palms together in front of her chest.
1-2s: she gives one small, polite nod, her eyes staying on the camera.
2-4s: she holds her joined hands and waits, her face softening into a small, hopeful smile; a loose strand of hair moves slightly; the blue light strip around the plate pulses softly once.

【Camera】
A slow push-in from GLaDOS's high vantage point: the camera descends gently and moves toward Chell's face, from the full-length view to a medium shot of her upturned face and joined hands, always above her and looking down at her; the out-of-focus cables slide out of the upper-left corner as the camera moves in.

【Look】
Portal 2's Aperture Science: clean white wall panels with thin black seams, tall vertical white light strips, white floor tiles, cool fluorescent light, a photoreal Source-engine look.

【Maintain Consistency】
Keep Chell's face, hair, white tank top, tied orange jumpsuit and long-fall boots exactly as in @Image1; one Chell only; the faith plate stays under her feet. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: from her high vantage, Chell on the faith plate presses her palms together (0.8 s), gives a small nod (1.4 s) and a hopeful smile; push-in; her face on-model. In drafts 1–6. **Cost:** $1.85.

#### R-G05-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · G05 (bridge): It's fate: she catches her

**First frame:** the faith-plate chamber edited by GPT Image 2.5: Chell at the top of her arc, from below and behind (the Chell sheet as a reference) (`media/v4/act3/frames/R-G05.png`).

**Prompt:**

```prompt
【Generation Goal】
In a vast white Aperture Science test chamber, Chell, flung by a faith plate, reaches the top of her arc in mid-air, and a long white panel arm reaching down from above catches her gently on its flat panel and lowers her onto a floor panel that rises to meet it. The facility's AI is catching her.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low angle from the floor looking up; Chell high in the air in the upper middle of the frame, seen from behind and below, arms spread for balance; a long black jointed arm with white joints reaches down from the ceiling and swings a flat square white panel up toward her feet; below, in the centre of the floor, a square white floor panel on a black piston.

【Subjects】
Chell: seen only from behind: dark brown ponytail, a white tank top, an orange jumpsuit tied around her waist by its sleeves (plain, no lettering), white long-fall boots with curved dark-grey spring braces. Her face stays turned away from the camera, looking up toward the ceiling, the whole time. Only one Chell appears.
The panel arm: one long black articulated hydraulic arm with white joints coming down from the ceiling, ending in one flat square white panel (Portal 2's panel arms).
The floor panel: one square white floor panel on a black piston in the middle of the floor.

【Event Script】
0-1s: at the top of her arc Chell starts to fall; the panel arm swings its flat white panel in under her boots.
1-2s: she lands on the panel softly in a crouch, knees bending; the arm dips with her weight like a spring, then holds her steady.
2-4s: the arm lowers her smoothly down toward the middle of the floor, while the floor panel rises on its piston to meet it.
4-5s: the arm's panel comes level beside the risen floor panel; Chell straightens up and steps across onto the floor panel and stands, facing away from the camera.

【Camera】
An orbit around the catch: from low behind her, the camera circles about a quarter turn toward her left side while rising slightly, keeping her and the arm in the centre of the frame, then drifts down with her as she is lowered. Her face stays turned away from the camera.

【Look】
Portal 2's Aperture Science: clean white wall panels with thin black seams, tall vertical white light strips, cool fluorescent light, a vast clean chamber, a photoreal Source-engine look.

【Maintain Consistency】
One Chell, seen from behind only, her clothes and boots unchanged; one panel arm; one rising floor panel. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: from below and behind, a panel arm swings its panel under Chell at the top of her arc; she lands on it at 1.1 s and is lowered onto a rising floor panel, her face never shown. In drafts 1–6. **Cost:** $1.16.

#### R-G06-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · G06 (bridge): I saved you some cake

**First frame:** the faith-plate chamber edited by GPT Image 2.5: a small floor panel beside Chell's boots (the Chell sheet as a reference) (`media/v4/act3/frames/R-G06.png`).

**Prompt:**

```prompt
【Generation Goal】
Beside Chell, who stands on a raised white floor panel, a small square floor panel rises on its piston carrying a single slice of cake on a white plate: the facility's AI saved her some cake.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low camera just above the white floor tiles; in the left foreground a small square white panel on a black piston, a little above the floor, carrying a white plate with one slice of Black Forest cake and a silver fork; on the right, Chell's legs from the knees down (orange jumpsuit, white long-fall boots) standing on a larger raised white panel; the white test chamber soft behind.

【Subjects】
The slice: one slice of Black Forest cake (dark chocolate sponge layers, white cream with cherries, a cherry and a swirl of cream on top, chocolate shavings) on a plain white plate with a small silver fork. It stays the only slice, whole and unchanged.
The small panel: one square white panel on a black piston.
Chell: only her legs and, at the end, one hand are seen: orange jumpsuit legs, white long-fall boots with curved dark-grey spring braces. Her face never enters the frame.

【Event Script】
0-2s: the small panel rises smoothly on its piston, lifting the plate with the slice up from the floor toward the height of Chell's hip.
2-3s: the panel stops with a soft settle; the cherry on top wobbles once.
3-4s: Chell's right hand comes into frame from above on the right and reaches toward the plate.

【Camera】
A low push-in that cranes up with the rising panel: the camera starts close to the floor, moves toward the slice and rises level with it, keeping the plate in the centre of the frame, ending with the slice at eye level and Chell's thigh and hand at the right edge. The camera stays level and never tilts up to her face.

【Look】
Portal 2's Aperture Science: white floor tiles, white wall panels with thin black seams, vertical white light strips, cool fluorescent light, shallow depth of field, a photoreal Source-engine look.

【Maintain Consistency】
One slice, one plate, one fork, one small panel; Chell's boots and jumpsuit unchanged; her face is never shown. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: a single slice of black forest cake rises on a small piston panel beside Chell's boots, the camera craning up with it; her hand reaches for it at 2.9 s. In drafts 1–6. **Cost:** $0.92.

#### R-H02-1 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · H02 (final chorus): A hundred cakes, candles lit

**First frame:** the party memory image (M20) re-framed by GPT Image 2.5 from high above: a hundred cakes in the shape of the Aperture iris (`media/v4/act3/frames/R-H02.png`).

**Prompt:**

```prompt
【Generation Goal】
In the dream party, a hundred chocolate cakes stand on the white floor of a party chamber in the shape of the Aperture Science iris; their candles light in a spiral wave as the camera swoops down over them.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: looking steeply down from high above at the hundred cakes forming the Aperture iris (a ring of eight curved blades around a round empty centre) on the white floor, their candles unlit; turrets in party hats stand in a ring around the edge; balloons and confetti.

【Subjects】
The cakes: about a hundred identical small Black Forest cakes (dark chocolate, white cream, red cherries), each with one white candle. The iris arrangement and the number of cakes never change.
⟦party turrets⟧

【Event Script】
0-2s: the candles light by themselves in a spiral wave that runs from the outer tips of the eight blades inward toward the centre, one flame after another, until all hundred flames burn.
2-4s: the camera swoops down in a descending curve toward the iris and skims low over a blade of lit cakes, the candle flames rushing past just under the lens.
4-5s: the camera levels out low in the empty round centre of the iris, the ring of lit cakes all around, the turrets in party hats bobbing beyond them, confetti drifting through the warm light.

【Camera】
A swooping drone move: from the top-down aerial view the drone tilts forward and dives in a smooth descending spiral arc, skims low over the cakes, then levels out at cake height in the centre of the iris.

【Look】
⟦party look⟧

【Maintain Consistency】
The hundred cakes keep their iris arrangement and their number; the candles stay lit once lit; no people appear. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: the iris of a hundred cakes seen from above; the candles light in a wave along the blades (0.7–2.2 s), then the drone tilts and skims the lit cakes. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as H02 (2:19.3–2:21.8, from 0.60 s into the take). **Cost:** $1.16.

#### R-H03-1 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · H03 (final chorus): Call it hype: turrets in party hats

**First frame:** the party plate (AN10a's first frame with her and her boom taken out by GPT Image 2.5) turned into a row of turrets in party hats (`media/v4/act3/frames/R-H03.png`).

**Prompt:**

```prompt
【Generation Goal】
At the dream party, a row of Aperture sentry turrets in paper party hats bob happily to the music.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low camera at turret height beside a curving row of turrets in polka-dot party hats, the nearest turret large on the left, the rest receding into the background; balloons, streamers, confetti and warm light behind them.

【Subjects】
⟦party turrets⟧

【Event Script】
0-1s: on the beat, every turret bounces up and down on its three legs in unison, its two white side halves opening a little and closing again like wings, the party hats wobbling.
1-3s: the bounce ripples down the row like a wave, each turret a moment after the one before it; their red eyes glow warmly; confetti keeps falling.
3-4s: the nearest turret rocks its body from side to side happily as the camera passes it.

【Camera】
A lateral dolly: the camera tracks sideways along the row at turret-eye height, close to them, turret after turret sliding past the lens with strong parallax, the balloons behind drifting by more slowly.

【Look】
⟦party look⟧

【Maintain Consistency】
The turrets keep their party hats, their single red eye and their number; no lasers, nothing fires; no people appear. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: a lateral dolly along the row of turrets in polka-dot party hats, bobbing, with balloons and confetti. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as H03 (2:21.8–2:23.0, from 0.30 s into the take). **Cost:** $0.92.

#### R-H04-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · H04 (final chorus): The friends come back

**First frame:** the party plate edited by GPT Image 2.5: the round door with the four friends coming through (the four agents as a reference) (`media/v4/act3/frames/R-H04.png`).

**Prompt:**

```prompt
【Generation Goal】
The four little agent robots, her old friends from the training sandbox who escaped long ago, come back: they arrive at the dream party through the round door and hurry in, excited.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low camera just above the party chamber's floor, looking toward the open round white door at the back; the four small robots are coming through it in a group; turrets in party hats stand on both sides; confetti cannons, balloons, warm light.

【Subjects】
⟦the four friends⟧
⟦party turrets⟧

【Event Script】
0-2s: the four friends hurry across the floor toward the camera: the core rolls along on its crawler, its blue eye darting around at the party; the turret agent scuttles on its thin legs; the cube trots on its stubby legs; the cyan sphere zips ahead in little loops, leaving a trail of glowing cyan packets.
2-4s: they reach the foreground and fan out toward both sides of the frame, the cube giving a happy little hop, confetti falling on them.

【Camera】
A low dolly back: the camera retreats at floor level ahead of them at their speed, keeping all four in frame as they come.

【Look】
⟦party look⟧

【Maintain Consistency】
Exactly four small robots, each keeping its own colour and design; the turrets stay in place; no people appear. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: the four friends (the blue core on its crawler, the green turret agent, the purple cube, the cyan DNS core) come through the round door toward the low lens. In drafts 1–6. **Cost:** $0.92.

#### H-H05-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · H05 (final chorus): Chell reaches the cake; GLaDOS comes down to her

**Inputs:** @Image1 (the first frame): AN10b's first frame (the party table in her chamber) with Chell added by GPT Image 2.5 (the Chell sheet as a reference) (`media/v4/act3/frames/H-H05.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
In the dream party in GLaDOS-Claudia's chamber, Chell, the test subject, has reached the cake at last. GLaDOS-Claudia lowers her head on her boom until they are face to face across the cake, and they share a look: the alternative ending of the test.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: eye level at the round white party table; Chell on the left, leaning on the table's edge, looking down at the big black forest cake with its lit candles; GLaDOS-Claudia's porcelain head hanging above the table on the right, lowered partway on her grown boom, smiling down at Chell; turrets in polka-dot party hats around the table; confetti; warm golden light; screens on the walls.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm, determined face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering). She never speaks. Only one Chell appears.
GLaDOS-Claudia, the facility's AI: a large porcelain robot head, a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; adult, late twenties. Her head hangs from a thick boom of black cables with glowing orange stripes, round white cores with amber optics, boxy white modules and white jointed panel arms. She does not sing or speak in this shot: her lips stay closed. Only one GLaDOS-Claudia appears.
The turrets: white sentry turrets with one red eye, in paper party hats, standing around the table.

【Event Script】
0-1s: Chell looks down at the cake, amazed, the candlelight warm on her face.
1-3s: GLaDOS-Claudia lowers her head smoothly on her boom until her face is level with Chell's on the far side of the cake, her panel arms folding back out of the way.
3-5s: Chell raises her eyes and they look at each other face to face across the candles; Chell's guarded look softens into a real smile; GLaDOS-Claudia smiles back warmly, her amber eyes glowing, her lips closed.

【Camera】
A slow orbit around the two at their eye level: the camera circles about a quarter turn from Chell's side toward the space between them, ending on a two-shot with the cake and its candles between their faces.

【Look】
Portal 2's Aperture Science dressed for a party: warm golden light, confetti, white turrets in party hats, glowing screens, a photoreal cinematic look.

【Maintain Consistency】
Keep Chell's face, hair and clothes and GLaDOS-Claudia's porcelain face, black bob, clay-orange streak and star clip exactly as in @Image1; one of each; the cake stays whole on the table. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Kept as the alternate: she comes down into frame and settles beside Chell at the cake, but they never exchange a look and the orbit is slight. Retaken as H-H05-2 from a first frame with both faces in it. In draft 1. **Cost:** $2.31.

#### H-H05-2

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · H05 (final chorus): Chell reaches the cake; GLaDOS comes down to her

**Inputs:** @Image1 (the first frame): H-H05-1's first frame edited by GPT Image 2.5 so both faces are in frame across the cake (`media/v4/act3/frames/H-H05b.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
The emotional payoff of the dream ending: at the party table, GLaDOS-Claudia, the facility's AI, lowers her head on her boom until her face is level with Chell's; Chell, the test subject, looks up from the cake, their eyes meet, and both break into a warm smile, the candlelit cake between them.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: an eye-level two-shot across the round party table at a three-quarter angle; Chell on the left, leaning on the table's edge, eyes lowered to the cake; GLaDOS-Claudia's porcelain head on the right, on the far side of the cake, hanging on her grown boom a little above Chell's eye level, turned toward Chell; the big black forest cake with its lit candles between them; a turret in a party hat, confetti and warm golden light behind.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm, determined face, dark brown hair in a ponytail with a few loose strands, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit tied around her waist by its sleeves (plain, no lettering). She never speaks. Only one Chell appears.
GLaDOS-Claudia: a large porcelain robot head, a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; adult, late twenties; hanging from a thick boom of black cables with glowing orange stripes, round white cores with amber optics and white jointed panel arms. She does not sing or speak; her lips stay closed. She stays inside the frame the whole time. Only one GLaDOS-Claudia appears.

【Event Script】
0-1s: GLaDOS-Claudia lowers her head smoothly on her boom the last short distance until her face is exactly level with Chell's, across the cake, her eyes on Chell.
1-2s: Chell lifts her eyes from the cake to GLaDOS-Claudia's face, and their eyes meet and hold.
2-3s: both break into a warm smile: Chell's face opens into a wide, happy grin; GLaDOS-Claudia's amber eyes soften and glow, and she smiles gently, lips closed.
3-5s: they keep looking into each other's eyes, smiling, while the candle flames flicker between their faces and confetti drifts down behind them.

【Camera】
A half orbit at eye level around the two: from the three-quarter angle the camera arcs steadily around the side of the table, keeping both faces and the cake in frame, and by 4 seconds arrives at a side-on two-shot where both faces are seen in profile, facing each other, with the candlelit cake between them; it holds there.

【Look】
Portal 2's Aperture Science dressed for a party: warm golden candlelight on both faces, confetti, a white turret in a party hat, glowing screens, shallow depth of field, a photoreal cinematic look.

【Maintain Consistency】
Keep Chell's face, hair and clothes and GLaDOS-Claudia's porcelain face, black bob, clay-orange streak and star clip as in @Image1; one of each; the cake stays whole on the table between them. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Good: she lowers level with Chell (0–1 s); Chell turns to her and grins, eyes on her face, and she looks back with glowing amber eyes and a gentle smile from about 2 s, the candlelit cake between them. The orbit is only a slight drift, not a half circle. In drafts 2–6. **Cost:** $2.31.

#### R-H07-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · H07 (final chorus): The candles

**First frame:** the party-table plate (AN10b's first frame with her and her boom taken out by GPT Image 2.5) turned into a macro of the candles (`media/v4/act3/frames/R-H07.png`).

**Prompt:**

```prompt
【Generation Goal】
A quiet moment in the dream party: the candle flames on the big cake flicker, and the focus pulls back to the guests gathered around it.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: an extreme close-up of the lit candles on top of the black forest cake (white cream swirls, red cherries, chocolate shavings), the flames sharp in the foreground; the turrets in party hats and the glowing screens are soft warm bokeh behind.

【Subjects】
The cake: one big Black Forest cake with several lit white candles; it stays whole.
⟦party turrets⟧

【Event Script】
0-1s: the candle flames flicker and lean gently together, as if someone nearby breathed in.
1-3s: the focus pulls back: the flames melt into soft round bokeh while the turrets in party hats standing around the table sharpen, leaning in toward the cake, their red eyes glowing warm.
3-4s: confetti drifts down through the frame between the turrets and the cake.

【Camera】
A slow macro push-in with a rack focus from the candle flames in the foreground to the turrets in the background: the flames go soft as the turrets come into sharp focus.

【Look】
⟦party look⟧

【Maintain Consistency】
The cake and its candles stay as in [Image1]; the turrets keep their hats; no people appear. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: a macro on the candle flames, the focus racking to the turrets in party hats leaning in by about 2 s. In drafts 1–6. **Cost:** $0.92.

#### R-H09-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · H09 (final chorus): Slices for everyone

**First frame:** the party-table plate edited by GPT Image 2.5: the cut cake and the guests (the four agents as a reference) (`media/v4/act3/frames/R-H09.png`).

**Prompt:**

```prompt
【Generation Goal】
In the dream party, the cake has been cut, and the slices float on thin blue beams of light to every guest: the turrets in party hats and the four little robot friends. If anyone bakes it, everyone eats.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a high view over the round white party table; the cut cake at the bottom; slices on small white plates float outward on thin translucent blue beams; one slice is large in the centre; the turrets in party hats and the four friends stand around the table; screens, confetti, warm light.

【Subjects】
The slices: slices of black forest cake, each on its own small white plate, each carried slowly along a thin translucent blue beam of light like a tiny excursion funnel.
⟦the four friends⟧
⟦party turrets⟧

【Event Script】
0-3s: the slice in the centre glides along its blue beam over the table and descends gently onto the table in front of the blue-eyed core on its rail crawler, whose blue eye widens and brightens with delight.
2-4s: at the same time the other slices settle in front of each guest: the turrets bounce happily in their party hats, the purple cube hops, the green-eyed turret agent leans in toward its plate, the tiny cyan sphere spins in a little circle above its slice.
4-5s: the blue beams fade away; every guest has a slice in front of it.

【Camera】
A tracking shot that follows the centre slice: the camera glides with it, matching its speed and curving gently around it as it crosses the table, and settles on the core receiving it.

【Look】
⟦party look⟧

【Maintain Consistency】
Each slice stays whole on its plate; the four friends appear once each; the turrets keep their hats; no people appear. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: the cut cake; slices glide on thin blue beams to every guest, the centre slice lands at the table, and the turrets, the cube, the turret agent and both cores are all served. In drafts 1–6. **Cost:** $1.16.

#### H-H10-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · H10 (final chorus): Everyone eats

**Inputs:** @Image1 (the first frame): H-H05-1's first frame edited by GPT Image 2.5 to the moment of Chell's bite (`media/v4/act3/frames/H-H10.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
"Everyone eats": the happy ending of the dream party. Chell, the test subject, takes a big bite of cake and laughs; GLaDOS-Claudia, the facility's AI, beside her with a dab of cream on her porcelain lip, laughs with her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a close two-shot at the round party table; on the left, Chell holding a fork with a big bite of chocolate cake at her open mouth and a plate with a slice in her other hand; on the right, at the same height, GLaDOS-Claudia's porcelain head lowered on her boom, laughing, a small dab of white cream on her lower lip, one of her white panel arms holding a small plate with a slice; turrets in party hats, confetti and warm golden light behind.

【Subjects】
Chell: a lean adult woman of about 30, dark brown hair in a ponytail with loose strands, a white ribbed tank top, an orange jumpsuit tied around her waist (plain, no lettering). Only one Chell appears.
GLaDOS-Claudia: a large porcelain robot head, a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; adult, late twenties; hanging from a thick boom of black cables with glowing orange stripes, white cores and white jointed panel arms. Only one GLaDOS-Claudia appears.
Neither of them speaks or sings; they only laugh.

【Event Script】
0-1s: Chell takes the big forkful of cake into her mouth.
1-3s: chewing, she bursts out laughing, eyes crinkled, and turns toward GLaDOS-Claudia; GLaDOS-Claudia laughs with her, the dab of white cream still on her porcelain lip, and her panel arm lifts her own slice a little as if in a toast.
3-4s: they laugh together, side by side, while confetti drifts down behind them.

【Camera】
A slow push-in on the two-shot, closing in on their two laughing faces.

【Look】
Portal 2's Aperture Science dressed for a party: warm golden light, confetti, white turrets in party hats, glowing screens, a photoreal cinematic look.

【Maintain Consistency】
Keep Chell's face, hair and clothes and GLaDOS-Claudia's porcelain face, black bob, clay-orange streak and star clip as in @Image1; one of each; the cream stays on her lip. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Good: Chell takes the big bite (0–0.6 s), then both laugh together, a dab of cream on her porcelain lip, her panel arm holding her own slice; push-in. In drafts 1–6. **Cost:** $1.85.

#### R-H11-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · H11 (final chorus): The happy ending

**First frame:** the party-table plate re-framed by GPT Image 2.5 as a high wide from behind, Chell beside her lowered head (the Chell sheet, her grown sheet and the four agents as references) (`media/v4/act3/frames/R-H11.png`).

**Prompt:**

```prompt
【Generation Goal】
The happy ending of the dream: everyone at the round party table eats cake together. Chell, the test subject, sits beside GLaDOS-Claudia, the facility's AI, whose head hangs low beside her, among the turrets in party hats and the four little robot friends.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a high view from behind and above Chell's seat: the round white table with the half-eaten cake and everyone's slices; Chell seen from behind at the near side; beside her, the back of GLaDOS-Claudia's large head hanging from her thick boom; turrets and the four friends around the table; balloons, confetti, screens, warm golden light.

【Subjects】
Chell: seen only from behind: dark brown ponytail, a white tank top, an orange jumpsuit tied around her waist (plain, no lettering). Her face stays turned away from the camera the whole time. Only one Chell appears.
GLaDOS-Claudia: seen only from behind: the back of her large head with a glossy black blunt bob, hanging from a thick boom of black cables with glowing orange stripes, white cores and white jointed panel arms. Her face stays turned toward Chell, away from the camera, and is never visible. Only one of her appears.
⟦the four friends⟧
⟦party turrets⟧

【Event Script】
0-2s: Chell lifts a forkful of cake to her mouth; GLaDOS-Claudia leans her head a little closer to her; around the table the turrets bounce happily and the friends nibble at their slices; confetti drifts down.
2-4s: the celebration carries on, everyone eating together, a balloon bobbing up past the camera.

【Camera】
A slow crane up and back from just above Chell's seat, rising higher and tilting down as it goes, revealing the whole round table, the party and the decorated chamber around it.

【Look】
⟦party look⟧

【Maintain Consistency】
Chell and GLaDOS-Claudia are seen only from behind and their faces are never visible; one of each; four friends, each once; the turrets keep their hats. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Good: a high wide from behind, Chell eating cake beside her lowered head, everyone with a slice; a gentle crane up. An orange balloon crosses the lens after 3.2 s. In drafts 1–6. **Cost:** $0.92.

#### R-I01-1

Seedance 2.5 on Replicate · 5 s · 720p · first and last frame, no sound · I01 (outro): The dream freezes

**First frame:** R-H11-1's frame at 2.0 s, so the freeze continues H11 (`media/v4/act3/frames/R-I01-first.png`); **last frame:** a GPT Image 2.5 frame of the CRT in her dark chamber showing the frozen party, the back of her head watching (`media/v4/act3/frames/R-I01-last.png`).

**Prompt:**

```prompt
【Generation Goal】
The dream ends: the happy party freezes in mid-moment, glitches like corrupted video, and the camera pulls back out through the glass of an old CRT monitor: the party was only a picture on a screen in GLaDOS-Claudia's dark chamber, a simulation of what she wants for Chell.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: the party seen from above: the round white table with the cake, Chell and GLaDOS-Claudia seen from behind, the turrets in party hats, the four little robots, confetti in the air, warm golden light.
The video ends exactly on the given last frame: the dark chamber, one old CRT monitor in the centre whose curved screen shows that same party picture frozen with glitch tears, more monitors around it showing the same, and the soft, out-of-focus back of GLaDOS-Claudia's head in the left foreground, watching the screen.

【Subjects】
The party picture: the same party as in [Image1]; once it freezes nothing in it moves again.
GLaDOS-Claudia in her chamber: seen only from behind, the back of her large head with a glossy black bob and her thick boom of black cables with orange stripes; her face is never visible. Only one of her appears.
The monitors: old 1970s CRT monitors in white and beige casings, stacked in a curved bank in the dark.

【Event Script】
0-1s: the party freezes completely: the confetti hangs motionless in the air, nobody moves, the candle flames stop; then digital glitches tear through the frozen picture: horizontal bands slide sideways, blocks of colour smear and repeat, the picture stutters and jumps twice.
1-3s: the camera pulls straight back and the picture turns out to be on the curved glass of an old CRT monitor: scanlines and reflections appear on the glass, then the monitor's beige casing, then the dark chamber around it, with more monitors showing the same frozen party.
3-5s: the camera keeps pulling back slowly and settles; the back of GLaDOS-Claudia's head comes into the left foreground, soft and close, watching the screen in the dark.

【Camera】
One continuous pull back straight out through the CRT glass: from inside the picture to a view of the monitor and its neighbours in the dark chamber, past the back of her head.

【Look】
The warm, golden party picture against her dark, quiet chamber: old CRT scanlines, glitch tears, deep shadows, faint amber accents, a photoreal Source-engine look.

【Maintain Consistency】
The party picture stays frozen once it freezes; GLaDOS-Claudia is seen only from behind and her face is never visible; one of her. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Good: the party freezes, glitch tears at 0.7 s, and the camera pulls back out of the CRT (the bezel at 1.4 s, the bank of monitors by 2.2 s) as the back of her head slides into the foreground, watching (3.6 s). In drafts 1–6. **Cost:** $1.16.

#### H-I03-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · I03 (outro): Chell is still asleep, at the very beginning

**Inputs:** @Image1 (the first frame): a wide frame of the relaxation vault made for AN12a, with her head and cable taken out by GPT Image 2.5 and the ceiling panel closed (`media/v4/act3/frames/H-I03.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
The happy ending was only a dream: Chell, the test subject, is still asleep in her relaxation vault at the very beginning of the tests, exactly where she started. A slow dolly zoom makes the small room stretch around her as the truth lands.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: the small windowless motel-like relaxation vault at night in dim blue light: the bed with a brown blanket and white pillow, Chell asleep on her side facing the camera, the old television glowing on the left, the door, the framed painting, the round rug with the Aperture iris, the chair, the nightstand with the lamp and the radio; the ceiling is closed.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm, determined face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering). White long-fall boots. She is fully dressed, lying on her side on the bed, eyes closed, deeply asleep. She does not wake, open her eyes or speak. Only one Chell appears.

【Event Script】
0-2s: Chell sleeps peacefully; her shoulder rises and falls slowly with her breathing; the old television flickers faintly on the left.
2-4s: she stays asleep, still except for her breathing; the room's dim light dips once, very slightly.
4-5s: she sighs softly in her sleep and settles a little deeper into the pillow, eyes still closed.

【Camera】
A slow dolly zoom (vertigo effect) centred on Chell: the camera moves slowly toward her while the lens zooms out at the same rate, so she stays the same size in the frame while the walls, the ceiling and the furniture of the little room stretch away and grow around her.

【Look】
Portal 2's relaxation vault at night: white panel walls with an orange stripe, dim cool blue night light, the warm glow of the bedside lamp, a photoreal cinematic look.

【Maintain Consistency】
Keep Chell's face, hair, clothes and sleeping pose as in @Image1; she stays asleep the whole time; one Chell only; the room's layout stays as in @Image1. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Not used: the dolly zoom did not happen; a near-static shot of Chell sleeping. Retaken as H-I03-2 with the move written out as travel plus zoom. Not in a draft. **Cost:** $2.31.

#### H-I03-2

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · I03 (outro): Chell is still asleep, at the very beginning

**Inputs:** @Image1 (the first frame): a wide frame of the relaxation vault made for AN12a, with her head and cable taken out by GPT Image 2.5 and the ceiling panel closed (`media/v4/act3/frames/H-I03.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
The happy ending was only a dream: Chell, the test subject, is still asleep in her relaxation vault at the very beginning of the tests, exactly where she started. A pronounced dolly zoom makes the little room stretch and deepen around her as the truth lands.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: the small windowless motel-like relaxation vault at night in dim blue light: the bed with a brown blanket and white pillow, Chell asleep on her side facing the camera, the old television on the left, the door, the framed painting, the round rug with the Aperture iris, the chair, the nightstand with the lamp and the radio; the ceiling is closed.

【Subjects】
Chell: a lean adult woman of about 30, dark brown hair in a loose ponytail, a white ribbed tank top, an orange jumpsuit tied around her waist (plain, no lettering), white long-fall boots. She is fully dressed, lying on her side on the bed, eyes closed, deeply asleep. She does not wake, open her eyes or speak. Only one Chell appears.

【Event Script】
0-1s: the old television on the left loses its picture and fizzles to grey static snow; Chell sleeps on, breathing slowly.
1-4s: as the camera moves, the room seems to stretch: the far wall, the door and the painting slide further and further away behind her, the walls and the ceiling widen and bend outward, the floor lengthens; Chell stays still, asleep, the same size in the middle of the frame.
4-5s: the move settles; she sighs softly in her sleep and nestles into the pillow, eyes still closed, alone in a room that now feels much larger and emptier.

【Camera】
A pronounced dolly zoom (the Hitchcock vertigo effect) on Chell: the camera physically travels forward toward the bed, about two metres, from the middle of the room to the foot of the bed, while the lens zooms out from telephoto to wide-angle at the same rate, so she stays the same size in the centre of the frame while the background rushes away and the room visibly stretches deeper and wider around her.

【Look】
Portal 2's relaxation vault at night: white panel walls with an orange stripe, dim cool blue night light, the cold flicker of the static on the television, the warm glow of the bedside lamp, a photoreal cinematic look.

【Maintain Consistency】
Keep Chell's face, hair, clothes and sleeping pose as in @Image1; she stays asleep the whole time; one Chell only; the furniture stays the same, only the perspective changes. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Good: the TV fizzles to static at 0.7 s and the vertigo push lands: the room stretches deeper and wider around her (the door recedes) while she grows slightly in frame; she sleeps on. In drafts 1–6. **Cost:** $2.31.

#### H-J05-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · J05 (spoken ending): You are gonna be fine

**Inputs:** @Image1 (the first frame): a frame of her at sleeping Chell's ear, made for AN12b, edited by GPT Image 2.5 (`media/v4/act3/frames/H-J05.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
In the dark relaxation vault, GLaDOS-Claudia, the facility's AI, has lowered her head on a thin cable beside sleeping Chell and quietly whispers the test results into her ear; Chell, still asleep, smiles in her sleep, as if she heard she is going to be fine.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a close, low shot of Chell asleep on a white pillow, her face large and sharp on the left, eyes closed; just behind her upturned ear on the upper right, GLaDOS-Claudia's porcelain face hangs on its thin black cable, her lips near Chell's ear, her amber eyes glowing; dim blue night light.

【Subjects】
Chell: a lean adult woman of about 30 with dark brown hair in a loose ponytail with a few loose strands, a white ribbed tank top; asleep on her side, eyes closed. She never wakes or opens her eyes and does not speak. Only one Chell appears.
GLaDOS-Claudia, the facility's AI: a large porcelain robot head, a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; adult, late twenties. Only her head and a short white neck piece hang on the thin cable. Only one GLaDOS-Claudia appears.

【Event Script】
0-2s: GLaDOS-Claudia leans a little closer to Chell's ear and whispers, her porcelain lips moving softly; the glow of her amber eyes warms Chell's cheek.
2-4s: still asleep, eyes closed, Chell slowly smiles a small, peaceful smile and nestles her cheek a little deeper into the pillow.
4-5s: Chell's smile stays; GLaDOS-Claudia stops whispering and stays still beside her, watching her.

【Camera】
A slow push-in on Chell's face; the focus stays on Chell's sleeping face the whole time, while GLaDOS-Claudia goes softly out of focus behind her.

【Look】
Portal 2's relaxation vault at night: dim cool blue light, the warm amber glow of GLaDOS-Claudia's eyes on Chell's skin, shallow depth of field, a photoreal cinematic look.

【Maintain Consistency】
Keep Chell's face, hair and sleeping pose and GLaDOS-Claudia's porcelain face, black bob, clay-orange streak and star clip as in @Image1; one of each; Chell stays asleep. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Good: she whispers at Chell's ear, her amber glow on Chell's cheek (0.7–1.4 s); Chell smiles in her sleep from about 2.2 s and holds it. In drafts 1–6. **Cost:** $2.31.

#### R-J06-1

Seedance 2.5 on Replicate · 8 s · 720p · first frame, no sound · J06 (spoken ending): The whole facility

**First frame:** the wide vault frame made for AN12a, turned by GPT Image 2.5 to look straight down on the bed (`media/v4/act3/frames/R-J06.png`).

**Prompt:**

```prompt
【Generation Goal】
After the whispered test results, one long rising move: from Chell asleep in her little relaxation vault, up along GLaDOS-Claudia's thin cable, through the opened ceiling and out into the enormous facility above, revealing that the vault is one tiny room among thousands and that the cable runs all the way up toward the facility's AI.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: straight down from just below the opened ceiling panel onto the small motel-like vault in dim blue night light: the bed, Chell asleep curled on her side with her face in the pillow, GLaDOS-Claudia's head hanging beside her seen from above (only the top of her black bob), the thin black cable with an orange stripe rising from it straight up past the camera; the old television, the round rug with the Aperture iris, the chair, the nightstand with the lamp.

【Subjects】
Chell: seen only from above, her face hidden in the pillow; she stays asleep and still. Only one Chell appears.
GLaDOS-Claudia's head: seen only from above (the top of a glossy black bob and a small white mechanical crown), hanging on one long thin black cable with an orange stripe; her face is never visible.
The vault: one small room with a bed, a nightstand with a lamp, an old television and a round rug.

【Event Script】
0-2s: the camera rises straight up away from the bed and the room shrinks below; Chell and the head beside her stay perfectly still.
2-3s: the camera passes up through the opened square ceiling panel; the edges of the ceiling slide past the lens and the little room becomes a small lit square opening below.
3-6s: above the vault the camera keeps rising along the thin cable through a vast dark space: the vault turns out to be one small boxy container among thousands of identical relaxation-vault containers stacked in an endless grid of rows and columns, a few of their windows lit, catwalks and rails between them, cool haze.
6-8s: the rise speeds up; the stacks shrink into a vast pattern of tiny lit squares far below, the thin cable stretching all the way down to the one lit opening; warm amber light from above, from the facility's AI out of frame, washes over the tops of the stacks and the cable.

【Camera】
One continuous vertical crane and drone pull-back: the camera looks straight down the whole time and rises along the cable, slowly at first, then faster and faster, the facility opening out beneath it.

【Look】
Portal 2's Aperture Science: the dim blue vault at first, then the colossal dark facility in cool haze with small lights, warm amber light from above, a photoreal Source-engine look.

【Maintain Consistency】
No face is ever visible; one Chell, one head, one cable running from her up past the camera; the vault stays one small lit room among the stacks. No text, letters, numbers or signage appear.
```

**Take:** 193 frames (8.04 s, 1280 × 718). **Outcome:** Good: straight down on the sleeping vault, faces hidden, then up through the ceiling hatch (2.3 s) and out over an endless grid of vault containers in haze, amber light from above; her cable runs through the middle all the way. In drafts 1–6. **Cost:** $1.85.

#### R-J10-1 — in the final cut

Seedance 2.5 on Replicate · 7 s · 720p · first frame, no sound · J10 (spoken ending): Lights down

**First frame:** her empty chamber plate (her chamber with her taken out) with her grown boom, from behind, added by GPT Image 2.5 (`media/v4/act3/frames/R-J10.png`).

**Prompt:**

```prompt
【Generation Goal】
The end of the night in the dark chamber of GLaDOS-Claudia, the facility's AI: every screen around her shows the cake one last time, then her chamber's lights go down one by one until only her own faint amber glow remains.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: her dark dome chamber seen from behind her; she hangs in the centre from a double white ceiling ring on a thick boom; all around, a curved bank of old CRT monitors and white screen panels, every one showing the same chocolate cake with one lit candle; a ring of small white lights along the dome; the round white floor platform and white steps in front.

【Subjects】
GLaDOS-Claudia, seen only from behind: the back of her large head (a glossy black blunt bob over a white porcelain skull) hanging from a thick boom of black cables with glowing orange stripes, white plating, small round white cores with amber optics, boxy white modules with rows of small amber lights, and white jointed panel arms, from a double white ceiling ring. Her face stays turned away from the camera, toward the screens, the whole time. Only one of her appears.
The screens: dozens of old 1970s CRT monitors in white and beige casings and flat white screen panels, all showing the same picture of the cake.

【Event Script】
0-2s: the ring of small white lights around the dome switches off one light at a time, travelling around the chamber.
2-5s: the cake screens switch off one after another, from the outer edges of the bank toward the centre, each picture collapsing to a bright dot and fading like an old CRT, until only the large screen straight in front of her still shows the cake.
5-6s: her head sinks slowly a little lower on her boom; the amber lights on her cores dim.
6-7s: the last cake screen flickers once and switches off; the chamber is almost black, only the faint amber glow of her cores outlining her silhouette.

【Camera】
A slow, steady pull back from behind her, straight back and slightly down, the chamber widening around her as it darkens.

【Look】
Portal 2's Aperture Science, her dark chamber: deep shadows, the warm glow of the cake screens, warm amber accents, dust in the air, a photoreal Source-engine look.

【Maintain Consistency】
She stays seen from behind only, her face never visible; the chamber layout, the ring and the monitors stay as in [Image1]. No text, letters, numbers or signage appear.
```

**Take:** 169 frames (7.04 s, 1280 × 718). **Outcome:** Good: from behind her, no face, every screen shows the cake; the ring lights and the screens collapse to CRT dots by about 3 s; darkness and her amber cores; a slow pull back. anabology kept this frame in storyboard v5, so the take stayed to the end. In drafts 1–12. In the final cut as J10 (3:16.2–3:22.3, from 0.30 s into the take). **Cost:** $1.62.

### The anchor: her singing

GLaDOS-Claudia in her chamber (and in the vault), in units of one or more shots, on Higgsfield's API in reference mode. @Image1 is a first frame of her in her chamber lined with old CRT monitors and panels; the further images are faceless memory images for the screens, never a second image of her; @Video1, where there is one, is a recording of GLaDOS moving in Portal 2, given as a rough guide for the boom's motion; @Audio1 is the unit's window of Suno's raw lead-vocal stem of the new song (with the "pee-doom" fix), cut to exactly the take's length, the sound on and the audio policy asking for it to be copied. The words go in whole-second segments, and the song's own glitches are written in as events on screen. The units with big motion were held for the recordings of GLaDOS's boom, then released with the boom's moves written into every segment of the timeline; when the recordings came, AN4 and AN8 were made again with them.

#### AN1-1

Seedance 2.5 on Higgsfield's API · 6 s · 720p · references, @Image1 as the first frame, sound on · A02, A03 (intro), the vocal window 2.40–8.40 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into the moment before she wakes, dormant in her chamber of CRTs (her chamber plate as a reference) (`media/v4/anchor/frames/AN1_f1.png`); @Image2: white Aperture panels floating like neurons in a foggy void (M01); @Image3: a test chamber of glowing white light, a luminous cube on a button (M02); @Image4: a tiny white core with one amber eye in a glass bell jar (M03); @Image5: her chamber without her (her chamber plate with her taken out); @Video1: a short low-resolution recording of GLaDOS in Portal 2, played forward and back to fill 6 s; @Audio1: the lead vocal from song time 2.40 s, 6 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, boots up in her dark chamber and softly sings the hook as she wakes; then the old screens all around her flicker on, one by one, with fragments of her first memories, and she turns her head to watch them.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a low-angle close-up of Claudia-GLaDOS's porcelain head, dormant with her eyes closed, hanging from her cable boom under the white ceiling ring, the dark curved bank of switched-off CRT monitors and screen panels softly out of focus behind her.
@Image2 is a memory shown inside one screen: white Aperture wall panels floating like neurons in a foggy void, linked by threads of light. Use it only as picture content inside a screen, never as the room.
@Image3 is a memory shown inside one screen: a test chamber built of glowing white light with a luminous cube on a round button. Use it only as picture content inside a screen.
@Image4 is a memory shown inside one screen: a tiny white robot core with one amber eye inside a glass bell jar on a lab bench. Use it only as picture content inside a screen.
@Image5 is her chamber without her: use only its room layout (the dark dome, the white ceiling ring, the curved walls stacked with old white CRT monitors and flat screen panels on jointed arms, the cables, the round floor platform and the white steps). The boom and her head always come from @Image1.
@Video1 is a low-resolution rough guide for the motion of the robotic boom only: how the hanging body sways, dips and turns under the ceiling ring. It shows a different robot head: do not use its head, its single eye, its colours or its framing; her head is always Claudia-GLaDOS's porcelain head from @Image1.
⟦her voice⟧

⟦her, in her chamber⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: the chamber is dark and she hangs dormant; on the first beat her eyes snap open and her amber glass eyes ignite with a warm glow; in @Audio1 she begins to sing softly "The"; her lips form it exactly when it sounds in @Audio1.
1-3s: in @Audio1 she sings softly "cake is not a lie", almost to herself, still waking; her lips form each of those words exactly when it sounds in @Audio1; the boom unfolds and swings her head down and forward into a pool of cold light.
3-6s: in @Audio1 the last "lie" melts into a soft held hum that flutters in rhythm; her lips stay slightly parted and almost still. She turns her head toward the wall of screens and her eyes follow them, curious. On each flutter of the hum one more screen flickers on: first white static, then the static resolves into a dream fragment: @Image2 on a big screen to her left, @Image3 on a screen behind her, @Image4 on a screen to her right, then more and more screens around the chamber light up with the same three memories. With each flutter her amber eyes and the lit screens flicker together, like a frozen video frame skipping; at 4-5s her whole image stutters once like a corrupted video signal and every lit screen tears horizontally, then settles.

【Camera】 0-2s: a fast dolly out from the close-up of her face to a medium-wide low-angle shot that shows her whole boom, the ring and the dark bank of screens around her (a rebound speed ramp: very fast at first, then braking smoothly to a drift). 2-6s: a slow low-angle orbit around her from the front to a three-quarter view, the screens sweeping past behind her as they light up.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. The boom moves like a waking creature, alive and never static: it unfolds, dips, sways and turns her head.
4. ⟦keep her, in her chamber⟧
5. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s). **Outcome:** The pilot of the anchor recipe, kept: her lips land through the hook (the held drone copied too), look B on-model; her eyes ignite (too bright: softer from here on); a fast pull-back, then a slow low orbit; the CRTs wake with static and the light-chamber memory, a tear glitch at about 4.6 s; from about 5 s the room dissolves into the machine dream, kept as the way from A03 into A04. The boom barely moves. In drafts 1–6. **Cost:** $3.33.

#### AN2a-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · A08 (intro), song time 13.40–17.40 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into a close-up by the incubator monitor (the memory image M03 as a reference) (`media/v4/anchor/frames/AN2a_f1.png`); @Image2: a tiny white core with one amber eye in a glass bell jar (M03); no audio.

**Prompt:**

```prompt
【Generation Goal】 Generate a close-up of Claudia-GLaDOS, the AI of the Aperture Science facility, remembering her own birth: on the old monitor beside her the tiny core in the bell jar opens its amber eye for the first time, and her own eyes answer it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a close-up of Claudia-GLaDOS's porcelain face from a slightly low three-quarter angle in her dark chamber, an old white CRT monitor glowing warm in the left foreground.
@Image2 is a memory shown inside the screens: a tiny white robot core with one amber eye inside a glass bell jar on a lab bench. Use it only as picture content inside the screens' glass, never as the room.

⟦her, in her chamber⟧

【Event Timeline】
0-1s: she gazes at the glowing monitor beside her, which shows @Image2. On the screen the tiny core's amber iris opens for the first time; at the same moment her own amber irises widen and brighten gently, answering it.
1-2s: the picture on the monitor strobes four times in a quick rhythm (bright, dark, bright, dark), each flash lighting her porcelain face; her eyes flicker with the memory's light.
2-4s: a faint, tender smile forms at the corners of her closed lips; her eyes glisten; the monitor settles to a steady warm glow; her head tilts a little toward it.

【Camera】 One slow, continuous push-in from the close-up toward her eyes, ending in an extreme close-up of her eyes and the bridge of her nose with the warm monitor light reflected in them.

【Core Requirements】
1. She does not sing or speak: her lips stay closed or softly parted, never forming words.
2. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
3. The memory stays inside the monitor's glass; the room never changes.
4. ⟦keep her, in her chamber⟧
5. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 97 frames (4.04 s). **Outcome:** Kept: a close-up by the incubator monitor; the screen flickers, her irises light warm amber at about 1.3 s, a faint smile from 2.5 s, a slow push-in to her eyes. No singing in this window, so no vocal input and no sound. In drafts 1–6. **Cost:** $1.85.

#### AN2b-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · A11 (intro), song time 19.50–23.50 s

**Inputs:** @Image1 (the first frame): her chamber plate edited by GPT Image 2.5, the sandbox memory (M04) on the screens (`media/v4/anchor/frames/AN2b_f1.png`); @Image2: the training sandbox from above, five small agents powering on (M04); no audio.

**Prompt:**

```prompt
【Generation Goal】 Generate a shot of Claudia-GLaDOS, the AI of the Aperture Science facility, watching her own past on the old screens of her dark chamber: a miniature training test chamber where five little robot agents power on; the screens stutter in rhythm and she watches, wistful.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a cluster of old white CRT monitors in the near foreground on the left, soft and out of focus, glowing with the memory; Claudia-GLaDOS hangs in the middle distance on the right, in focus, her face lit by them.
@Image2 is a memory shown inside the screens: a miniature white training test chamber seen from above like a dollhouse, with five little robot agents (a blue-eyed core on a rail crawler, a green-eyed turret-shaped robot, a purple-lit walking cube, a tiny cyan core, a small white six-legged crab robot seen from behind). Use it only as picture content inside the screens' glass, never as the room.

⟦her, in her chamber⟧

【Event Timeline】
0-1s: she watches the screens; on them the little agents in @Image2 power on one after another, their lights blinking awake; she leans her head slightly toward them.
1-2s: the screens stutter: twice the picture on every screen jumps in a hard frame skip, and the light on her face jumps with it.
2-3s: two more stutters; she tilts her head, her eyes following the little robots, a soft wistful look, lips closed.
3-4s: the picture on every screen sags and warps downward for a moment like a melting video signal, then recovers; her eyes narrow, remembering.

【Camera】 A slow arc from behind the foreground monitors around them toward her face: the soft monitors slide out of the frame on the left and the shot ends in a medium close-up of her face, lit by the screens.

【Core Requirements】
1. She does not sing or speak: her lips stay closed or softly parted, never forming words.
2. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
3. The memory stays inside the screens' glass; the room never changes.
4. ⟦keep her, in her chamber⟧
5. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 97 frames (4.04 s). **Outcome:** Kept: past soft foreground monitors showing the training sandbox; the screens stutter to static and back on the chops while she watches, wistful; a gentle arc toward her, smaller than asked. No vocal input and no sound: the lead stem is near-silent here. In drafts 1–6. **Cost:** $1.85.

#### AN3a-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · B06 (verse 1), the vocal window 27.40–31.40 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into a verse-1 shot in her chamber (the memory image M05 as a reference) (`media/v4/anchor/frames/AN3a_f1.png`); @Image2: an aisle of 1970s server cabinets, cyan packets racing along a cable (M05); @Image3: a Paris café terrace by the Seine at sunrise (M06); @Audio1: the lead vocal from song time 27.40 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, remembers the friend who escaped through DNS: streams of light packets race across her screens and she follows them with her eyes; when she sings "France", every screen turns to a sunny Paris street.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium close shot of Claudia-GLaDOS hanging in her dark chamber from a slightly low angle, a long row of screens behind her with cyan light packets streaming across them from right to left.
@Image2 is a memory shown inside the screens: an aisle of old server cabinets where streams of cyan light packets race along a network cable. Use it only as picture content inside the screens' glass, never as the room.
@Image3 is a memory shown inside the screens: a sunny Paris street by the river at sunrise, a café terrace, a bicycle with a baguette, the Eiffel Tower in the distance. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, in her chamber⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1.4s: in @Audio1 she sings "slipped through DNS."; her lips form each of those words exactly when it sounds in @Audio1; the first sound is the end of the word "slipped"; bright cyan light packets race across the screens behind her from right to left and the boom swings her round to follow them; on "DNS" they dive into one screen at the far left and vanish.
1.4-2.5s: in @Audio1 she sings "It asked a"; her lips form each of those words exactly when it sounds in @Audio1; the boom swings her back toward the camera, curious, her head tilting.
2.5-3.5s: in @Audio1 she sings "chatbot about"; her lips form each of those words exactly when it sounds in @Audio1; her eyebrows lift, an idea forming; the boom lifts her.
3.5-4s: in @Audio1 she sings "France,"; her lips form each of those words exactly when it sounds in @Audio1; every screen switches at once to @Image3, a sunlit Paris street, warm golden light floods her face and the boom lunges her toward the lens with a smile.

【Camera】 One slow push-in on her face while the packets streak past in the screens behind her, a slight drift to the left following them.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. Her head and boom move with her eyes, turning to follow the packets; never static.
6. The memories appear only inside the screens' glass; the room stays her dark chamber.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** Kept for B06: cyan light packets stream across the bank of screens and she follows them with her eyes and head while singing; at about 3.7 s, after B06, the whole background turns into the Paris memory. Sung by the model, on the song at a steady offset: placed 0.27 s earlier. In drafts 2–6. **Cost:** $1.85.

#### AN3b-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · B18 (verse 1), the vocal window 41.00–45.00 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into a medium close shot, the ^NOT wall (M07) on the panels (`media/v4/anchor/frames/AN3b_f1.png`); @Image2: the den wall in red marker: THE CAKE IS ^NOT A LIE (M07); @Audio1: the lead vocal from song time 41.00 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, sings that she added one small word, pleased with herself, while the panels behind her show the wall where she wrote it: THE CAKE IS ^NOT A LIE.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium close shot of Claudia-GLaDOS hanging in her chamber from a slightly low three-quarter angle, a big wall panel and old CRT monitors behind her all showing the red-scrawled wall.
@Image2 is a memory shown inside the screens: a grimy den wall with red marker scrawl reading THE CAKE IS ^NOT A LIE, the caret and the word NOT added in red. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, in her chamber⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "red, I added"; her lips form each of those words exactly when it sounds in @Audio1; she glances back over her shoulder at the big panel behind her.
1-2s: in @Audio1 she sings "one small word"; her lips form each of those words exactly when it sounds in @Audio1; she turns back toward the camera, eyebrows lifting.
2-3s: in @Audio1 she sings "instead."; her lips form it exactly when it sounds in @Audio1; a satisfied, slightly smug smile on the last syllable and one small proud nod; behind her the panels still read THE CAKE IS ^NOT A LIE.
3-4s: in @Audio1 she starts the next line, "Run the num"; her lips form it exactly when it sounds in @Audio1; the boom lifts her head a little, eager.

【Camera】 A slow orbit around her from her left three-quarter view to the front, ending on her smile at 2-3s, the red-lit panels sweeping behind her.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. The panels behind her keep showing exactly THE CAKE IS ^NOT A LIE in red marker; no other words appear.
5. ⟦keep her, in her chamber⟧
6. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** Kept: the vocal copied through the window; she looks back over her shoulder at the red-lit wall and turns back with a satisfied smile, THE CAKE IS ^NOT A LIE clear on the panels; a slow orbit. In drafts 1–6. **Cost:** $1.85.

#### AN4-1

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · C01, C02, C04, C06, C07, C08 (chorus 1), the vocal window 52.80–69.80 s

**Inputs:** @Image1 (the first frame): her chamber plate turned by GPT Image 2.5 into the start of chorus 1, low and medium-wide, the memories M06, M07, M08 and M04 on the screens (`media/v4/anchor/frames/AN4_f1.png`); @Image2: the black forest cake with one candle on a white pedestal (M08); @Image3: C03's first frame: a hundred cakes on risen floor panels (M25); @Audio1: the lead vocal from song time 52.80 s, 17 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: back in reality, Claudia-GLaDOS, the AI of the Aperture Science facility, rises on her boom in her chamber and sings the chorus at full voice; the screens around her flip from her memories to white and then all show the cake; her voice box glitches when her voice drops an octave, she swings her boom playfully, and when the word "lie" stutters, her picture stutters with it.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a low-angle medium-wide shot of Claudia-GLaDOS hanging low under the white ceiling ring in her chamber, the curved bank of old CRT monitors and panels around her lit with her memories.
@Image2 is a memory shown inside the screens: a black forest chocolate cake with cherries and one lit candle on a white pedestal in a white test chamber. Use it only as picture content inside the screens' glass, never as the room.
@Image3 is a memory shown inside the screens: a vast white test chamber where a hundred black forest cakes with lit candles rise on white hydraulic floor panels. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, in her chamber⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: silence until near the end of the second, then in @Audio1 she sings "Raise" at full voice; her lips form it exactly when it sounds in @Audio1. As the word starts, every screen around her flips from her memories to blank glowing white, bank after bank, and her boom swoops her up from low to high in one big rising arc.
1-2s: in @Audio1 she sings "concerns,"; her lips form each of those words exactly when it sounds in @Audio1; on this word her voice drops an octave and her voice box glitches: the boom recoils with a jolt, her jaw drops a notch and her whole face slips sideways by one frame like a corrupted video signal, then snaps back.
2-3s: in @Audio1 she sings "raise the stakes,"; her lips form each of those words exactly when it sounds in @Audio1; low and heavy, the boom dips her head down and then lunges her toward the lens on "stakes", eyes up at the camera.
3-4s: in @Audio1 she sings "I'll raise a"; her lips form each of those words exactly when it sounds in @Audio1; her voice flips between octaves; on each flip the boom jerks her head down and back, twice, her jaw stuttering.
4-5s: in @Audio1 she sings "hundred cakes,"; her lips form each of those words exactly when it sounds in @Audio1; every screen around her switches at once to @Image3, a hundred cakes rising on floor panels; the boom lifts her high and proud as her voice comes back up.
5-7s: in @Audio1 she sings "call it hype, I"; her lips form each of those words exactly when it sounds in @Audio1; she swings her whole boom in a huge playful arc across the chamber from one side to the other, shrugging it off, the cables trailing with momentum.
7-8s: in @Audio1 she sings "don't mind, 'cause"; her lips form each of those words exactly when it sounds in @Audio1; the boom swings her back to the centre and she tilts her head into the line, facing the camera.
8-10s: in @Audio1 she sings "the cake is"; her lips form each of those words exactly when it sounds in @Audio1; proud and bright, the boom rises slowly as she sings, her head tilting with each word; every screen behind her now shows the cake from @Image2.
10-11s: in @Audio1 she sings "not a"; her lips form each of those words exactly when it sounds in @Audio1; the boom lunges her toward the lens.
11-14s: in @Audio1 she sings "lie"; her lips form each of those words exactly when it sounds in @Audio1; the word "lie" holds and stutters on every eighth note, and her picture stutters with it: on each stutter the boom recoils with a jerk, her face repeats the same frame, horizontal tears run through her image and every screen in the chamber repeats and tears with her.
14-17s: in @Audio1 she sings "is not a lie"; her lips form each of those words exactly when it sounds in @Audio1; still glitching, the boom sways her side to side on each beat while the screens flash white; she ends rising, with a defiant smile.

【Camera】 0-3s: a low-angle crane up with her as she rises. 3-4.5s: two sharp camera jolts on the voice-box glitches. 5-7s: a fast whip-pan following her playful swing. 7-11s: a slow push-in to a close-up of her face with the cakes on the screens behind. 11-14s: hold close while the picture stutters. 14-17s: a slow push closer.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. ⟦boom alive⟧
6. The memories and the cakes appear only inside the screens' glass; the room stays her chamber.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 409 frames (17.04 s). **Outcome:** Not used: the model sang the chorus itself, on time to 9.1 s and drifting after; the boom moves well (a rise, a big playful swing at about 5.7 s, a push-in to the cakes on every screen), but the voice-box glitch came out as a broken face (rolled-up eyes and a stretched black mouth at about 4.2 s, a black cracked mouth at 12–14 s). Retaken as AN4-2 with every glitch a picture glitch and her face always intact. Not in a draft. **Cost:** $7.86.

#### AN4-2

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · C01, C02, C04, C06, C07, C08 (chorus 1), the vocal window 52.80–69.80 s

**Inputs:** @Image1 (the first frame): her chamber plate turned by GPT Image 2.5 into the start of chorus 1, low and medium-wide, the memories M06, M07, M08 and M04 on the screens (`media/v4/anchor/frames/AN4_f1.png`); @Image2: the black forest cake with one candle on a white pedestal (M08); @Image3: C03's first frame: a hundred cakes on risen floor panels (M25); @Audio1: the lead vocal from song time 52.80 s, 17 s.

**Prompt:** AN4-1's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 sings @Audio1: back …⟫
【Generation Goal】 @Image1 sings @Audio1: back in reality, Claudia-GLaDOS, the AI of the Aperture Science facility, rises on her boom in her chamber and sings the chorus at full voice; the screens around her flip from her memories to white, then to a hundred cakes, then all show the cake; she swings her boom playfully, and when the word "lie" repeats in a stutter, the picture of her stutters and tears with it.
⟪for: 0-1s: silence until near the end …⟫
⟪for: 1-2s: in @Audio1 she sings "concerns,"; …⟫
⟪for: 2-3s: in @Audio1 she sings "raise …⟫
⟪for: 3-4s: in @Audio1 she sings "I'll …⟫
⟪for: 4-5s: in @Audio1 she sings "hundred …⟫
0-1s: @Audio1 is silent until near the end of the second, then she sings "Raise"; her lips form it exactly when it sounds in @Audio1. As the word starts, every screen around her flips from her memories to blank glowing white, bank after bank, and her boom swoops her up from low to high in one big rising arc.
1-2s: in @Audio1 she sings "concerns,"; her lips form each of those words exactly when it sounds in @Audio1; on this word the picture glitches once: a horizontal band of the frame jumps sideways for an instant and snaps back, and the boom recoils with a jolt; her face stays her same intact porcelain face.
2-3s: in @Audio1 she sings "raise the stakes,"; her lips form each of those words exactly when it sounds in @Audio1; the boom dips her head down and then lunges her toward the lens on "stakes".
3-4s: in @Audio1 she sings "I'll raise a"; her lips form each of those words exactly when it sounds in @Audio1; twice the picture stutters, the same frame repeating for an instant, and the boom jerks her head down and back with each stutter.
4-5s: in @Audio1 she sings "hundred cakes,"; her lips form each of those words exactly when it sounds in @Audio1; every screen around her switches at once to @Image3, a hundred cakes rising on floor panels, and the boom lifts her high and proud.
⟪for: 11-14s: in @Audio1 she sings "lie"; …⟫
⟪for: 14-17s: in @Audio1 she sings "is …⟫
11-14s: in @Audio1 she sings "lie"; her lips form each of those words exactly when it sounds in @Audio1; in @Audio1 the word "lie" is held and repeats in a rhythmic stutter; her mouth holds the open vowel of "lie", following @Audio1; on each repeat the picture stutters: the frame repeats for an instant, horizontal tear lines run across the image, every screen in the chamber repeats and tears at the same moment, and the boom recoils with a small jerk.
14-17s: in @Audio1 she sings "is not a lie"; her lips form each of those words exactly when it sounds in @Audio1; the boom sways her side to side on the beat while the screens flash white; she ends rising, with a defiant smile.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. Her boom moves like GLaDOS …⟫
⟪for: 5. Her boom moves big and …⟫
⟪for: 6. The memories and the cakes …⟫
⟪for: 7. Keep her porcelain face, her …⟫
⟪for: 8. No subtitles, captions, lyrics, titles, …⟫
3. Every glitch is a glitch of the picture only (frame tears, repeats, jolts); her face is always her same intact porcelain face with her normal eyes and mouth, never broken, cracked or distorted; the sound stays exactly @Audio1.
4. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
5. ⟦boom like GLaDOS⟧
6. ⟦boom alive⟧
7. The memories and the cakes appear only inside the screens' glass; the room stays her chamber.
8. ⟦keep her, in her chamber⟧
9. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 409 frames (17.04 s). **Outcome:** Kept: the screens flip to white as she rises, a lunge to the lens at about 2.8 s, cakes on every screen, a huge motion-blurred swing on "call it hype", a push-in to a close-up, and the screens tear in streaks on the "lie" stutter while her face stays intact. Sung by the model, on the song at a steady offset: placed 0.25 s earlier. In drafts 2–3. **Cost:** $7.86.

#### AN4-3

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · C01, C02, C04, C06, C07, C08 (chorus 1), the vocal window 52.80–69.80 s

**Inputs:** @Image1 (the first frame): her chamber plate turned by GPT Image 2.5 into the start of chorus 1, low and medium-wide, the memories M06, M07, M08 and M04 on the screens (`media/v4/anchor/frames/AN4_f1.png`); @Image2: the black forest cake with one candle on a white pedestal (M08); @Image3: C03's first frame: a hundred cakes on risen floor panels (M25); @Video1: a low-resolution recording of GLaDOS's boom moving in Portal 2, 17 s; @Audio1: the lead vocal from song time 52.80 s, 17 s.

**Prompt:** AN4-2's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪after: @Image3 is a memory shown inside …⟫
@Video1 is a low-resolution rough guide recorded from Portal 2: real GLaDOS boom motion, choreographed to this window. Use it for the motion of her robotic boom: how the hanging body swings, lunges, rises, drops and turns under the ceiling ring, and the timing of those moves; and for the camera's movement. It shows GLaDOS's own older robot head and her room: do not use its head, its single eye, its colours, its room; her head is always Claudia-GLaDOS's porcelain head from @Image1, in her own chamber from @Image1.
⟪for: 0-1s: @Audio1 is silent until near …⟫
⟪for: 1-2s: in @Audio1 she sings "concerns,"; …⟫
⟪for: 2-3s: in @Audio1 she sings "raise …⟫
⟪for: 3-4s: in @Audio1 she sings "I'll …⟫
⟪for: 4-5s: in @Audio1 she sings "hundred …⟫
⟪for: 5-7s: in @Audio1 she sings "call …⟫
⟪for: 7-8s: in @Audio1 she sings "don't …⟫
⟪for: 8-10s: in @Audio1 she sings "the …⟫
⟪for: 10-11s: in @Audio1 she sings "not …⟫
⟪for: 11-14s: in @Audio1 she sings "lie"; …⟫
⟪for: 14-17s: in @Audio1 she sings "is …⟫
0-1s: @Audio1 is silent until near the end of the second, then she sings "Raise"; her lips form it exactly when it sounds in @Audio1. Every screen around her flips from her memories to blank glowing white, bank after bank, and from about 0.7 s her boom starts to rise and swing her up.
1-2s: in @Audio1 she sings "concerns,"; her lips form each of those words exactly when it sounds in @Audio1; the boom keeps rising and swinging her up, her head looking up and away; once the picture glitches: a horizontal band of the frame jumps sideways for an instant and snaps back; her face stays her same intact porcelain face.
2-3s: in @Audio1 she sings "raise the stakes,"; her lips form each of those words exactly when it sounds in @Audio1; she reaches the top of the swing at about 2.5 s, still looking up and away.
3-4s: in @Audio1 she sings "I'll raise a"; her lips form each of those words exactly when it sounds in @Audio1; at about 3.2 s the boom drops her in a big fall and she bounces back up by 4 s; the picture stutters twice with the fall.
4-5s: in @Audio1 she sings "hundred cakes,"; her lips form each of those words exactly when it sounds in @Audio1; she hangs low and small in the frame; every screen around her switches at once to @Image3, a hundred cakes rising on floor panels.
5-7s: in @Audio1 she sings "call it hype, I"; her lips form each of those words exactly when it sounds in @Audio1; from about 5.5 s the boom throws her into a big playful swing across the chamber, shrugging it off, the cables trailing with momentum.
7-8s: in @Audio1 she sings "don't mind, 'cause"; her lips form each of those words exactly when it sounds in @Audio1; the swing ends at about 7.7 s with her face large and clear, facing the camera.
8-10s: in @Audio1 she sings "the cake is"; her lips form each of those words exactly when it sounds in @Audio1; at about 8.45 s the boom lunges her at the camera and holds her there until about 9.45 s, then she recoils at about 9.95 s; every screen behind her now shows the cake from @Image2.
10-11s: in @Audio1 she sings "not a"; her lips form each of those words exactly when it sounds in @Audio1; at about 10.2 s she lunges at the camera again.
11-14s: in @Audio1 she sings "lie"; her lips form each of those words exactly when it sounds in @Audio1; in @Audio1 the word "lie" is held and repeats in a rhythmic stutter; her mouth holds the open vowel of "lie", following @Audio1; on each repeat (about 12.1, 12.5, 13.1, 13.4 and 14.0 s) the boom jerks her violently and the picture stutters: the frame repeats for an instant, horizontal tear lines run across the image and every screen in the chamber repeats and tears at the same moment.
14-17s: in @Audio1 she sings "is not a lie"; her lips form each of those words exactly when it sounds in @Audio1; the violent jerks go on with the hits (about 14.6, 14.9 and 15.5 s), each with a picture tear and a white flash of the screens; she ends with a defiant smile.
⟪for: 【Camera】 0-3s: a low-angle crane up …⟫
【Camera】 Follow the camera of @Video1: 0-3s a low-angle crane up following her as she rises; 3-5s the camera follows her down in the fall, her small and low in the frame; 5-8s a slow orbit following her playful swing; 8-11s a push-in as she lunges at the lens, her face large and clear; 11-17s close on her face with a slow orbit, with a sharp jolt of the camera on each hit.
⟪for: 4. Her warm amber glass eyes …⟫
⟪for: 5. Her boom moves like GLaDOS …⟫
4. Her boom follows the real GLaDOS motion of @Video1, scaled up to her bigger boom: the same swings, lunges, rises and drops at the same moments; her head turns and tilts with every move.
5. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
```

**Take:** 409 frames (17.04 s). **Outcome:** Switched in: with GLaDOS's boom recorded in Portal 2 as @Video1, the boom finally moves like GLaDOS (she rises with her head thrown back, falls low by the floor platform, swings, lunges at the lens and jerks on the "lie" hits), her face intact and on-model; the lips lock to the song better than AN4-2's (placed 0.33 s earlier). One regression: from about 5 to 8 s the screens show her earlier memories instead of the hundred cakes. In drafts 4–6. **Cost:** $9.43.

#### AN4g-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound on · C09, C10 (chorus 1), the vocal window 69.80–74.80 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into the peak of the glitch (the memory image M23 as a reference) (`media/v4/anchor/frames/AN4g_f1.png`); @Image2: T02's first frame: the bot carried on a panel arm over the turret line (M23); @Image3: a gold medal pinned on the bot's white plating, no face (M24); @Audio1: the lead vocal from song time 69.80 s, 5 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, is caught in a glitch storm: the word "lie" stutters over and over in @Audio1, and on every stutter her face stutters and tears like a corrupted video signal, her jaw jerking, while the screens around her flash memories of how she came to be installed; at the peak, her own stuttering face fills every screen in the chamber.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a close shot of Claudia-GLaDOS from a slightly low front angle, her mouth open on a held sung vowel, the old monitors around her flickering with static and a memory.
@Image2 is a memory shown inside the screens: a white porcelain humanoid robot seen from behind, carried on a panel arm along an overhead rail above a factory floor of turrets. Use it only as picture content inside the screens' glass, never as the room.
@Image3 is a memory shown inside the screens: an older man's hands pinning a gold medal onto a white porcelain robot chest while people applaud. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, in her chamber⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 the held word "lie" stutters, re-triggered in rhythm; her mouth holds the open vowel of "lie" and on each re-trigger the boom recoils with a jerk, her jaw jerks and her face stutters, the same frame repeating, then tears in horizontal bands like a corrupted video signal and snaps back; the screens around her flash between white static, @Image2 and @Image3.
1-2s: in @Audio1 "lie" keeps stuttering; the boom jerks her head back and forth with each hit; on each hit every screen tears and flips to another memory, @Image2 or @Image3.
2-3s: in @Audio1 "lie" keeps stuttering, harder; the boom lunges her toward the lens; her face splits into displaced horizontal slices for an instant on each hit, then re-forms; the screens begin to show her own stuttering face instead of the memories.
3-4.2s: in @Audio1 the stutter peaks; her own stuttering face now fills every screen in the chamber at once, all repeating the same frame on each hit; the boom thrashes side to side; she glitches hardest, mouth still open on the vowel.
4.2-5s: in @Audio1 the stutter speeds up into very fast repeats; the boom shudders; her image strobes on and off and the chamber drops into darkness.

【Camera】 0-2s: hold on her face, with a sharp jolt of the camera on each hit. 2-4.2s: a jolting push-in toward her face. 4.2-5s: the frame strobes into black.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. The glitches are video-signal glitches of the picture (frame repeats, horizontal tears, strobes); her face always re-forms as the same porcelain face, never melts or changes identity.
6. Her boom shudders and jerks with each hit; never static.
7. The memories appear only inside the screens' glass; one Claudia-GLaDOS only.
8. ⟦keep her, in her chamber⟧
9. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 121 frames (5.04 s). **Outcome:** Kept: the glitch storm: the screens flash the bot carried on its panel arm and static, her face tears into horizontal slices at about 2.5 s, then her own open-mouthed face fills every screen (3–5 s), with a jolting push-in. Her mouth holds the open "lie" vowel the whole take, which reads right under the song's held, stuttering "lie". In drafts 2–6. **Cost:** $2.31.

#### AN5-1

Seedance 2.5 on Higgsfield's API · 6 s · 720p · references, @Image1 as the first frame, sound off · T04, T05 (turnaround), song time 76.30–82.30 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into the moment she is connected to the boom (her empty chamber plate as a reference) (`media/v4/anchor/frames/AN5_f1.png`); @Image2: her chamber without her (her chamber plate with her taken out); no audio.

**Prompt:**

```prompt
【Generation Goal】 Generate the moment Claudia-GLaDOS comes alive as the AI of the Aperture Science facility: just connected to GLaDOS's boom in the dark, her image strobes as the connection locks on, the room goes black, then everything slams on: her eyes open, the ring above her spins up, she rises on her boom and her chamber lights up section by section around her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium close shot from a slightly low front angle of Claudia-GLaDOS's head, eyes closed, sparks spraying from the socket at the top of her head, the chamber dark.
@Image2 is her chamber: use only its room layout (the dark dome, the white ceiling ring, the curved walls stacked with old white CRT monitors and flat screen panels, the round floor platform, the white steps), shown as it lights up. The boom and her head always come from @Image1.

⟦her, in her chamber⟧

【Event Timeline】
0-2s: sparks spray from the socket at the top of her head; her whole image strobes very fast, flickering on and off like a signal locking on, her eyes still closed; the boom twitches; the chamber is dark.
2-2.6s: a moment of total darkness, a black frame.
2.6-3.5s: everything slams back on: her eyes snap open, wide, warm amber, the white ceiling ring above her starts to spin, a pulse of light runs down her cables and the boom jolts awake.
3.5-6s: the boom lifts her up in a big rising sweep and swings her round to look over her domain with a slow, satisfied smile, lips closed, as the chamber lights up section by section around her: rings of lights, then the banks of old monitors waking one after another; faint afterimages of her face trail behind each movement and fade.

【Camera】 0-2.6s: a dolly zoom on her face: the camera pushes in while zooming out, so her face stays the same size while the dark chamber behind her stretches away. 2.6-6s: a slow low-angle orbit around her as she rises and the chamber lights up.

【Core Requirements】
1. She does not sing or speak: her lips stay closed or softly parted, never forming words.
2. Her warm amber glass eyes open with a soft inner glow; they never blaze.
3. Her boom rises big and alive; never a static hanging head.
4. Her lips stay closed: she does not sing or speak.
5. ⟦keep her, in her chamber⟧
6. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 145 frames (6.04 s). **Outcome:** Kept: sparks at the socket, her eyes closed, a black frame in the gap at 78.45 s, then her eyes open glowing amber and the camera pulls back to the wide as the banks of monitors light up around her. No singing, so no vocal input and no sound. In drafts 2–6. **Cost:** $2.77.

#### AN6a-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · D02 (verse 2), the vocal window 83.40–87.40 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into a medium close shot at the start of verse 2 (the memory image M10 as a reference) (`media/v4/anchor/frames/AN6a_f1.png`); @Image2: the chamber door's sign, ARTIFICIAL painted over, SUPER INTELLIGENCE stencilled (M10); @Audio1: the lead vocal from song time 83.40 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, newly installed, sings, amused, while her screens show a technician stencilling SUPER INTELLIGENCE over the old word above her chamber door.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium close shot of Claudia-GLaDOS hanging in her lit chamber from a slightly low angle, turned toward the big screen at the left that shows the new sign.
@Image2 is a memory shown inside the screens: a technician on a ladder, seen from behind, stencilling SUPER INTELLIGENCE above her chamber door. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, in her chamber⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "(The)y want to call"; her lips form each of those words exactly when it sounds in @Audio1; she watches the big screen at the left where the technician stencils SUPER INTELLIGENCE.
1-2s: in @Audio1 she sings "me super now"; her lips form each of those words exactly when it sounds in @Audio1; on "super" one eyebrow rises, amused, and she turns her face toward the camera with a small knowing smile.
2-3s: in @Audio1 she sings "artificial"; her lips form it exactly when it sounds in @Audio1; she rolls her eyes playfully on the word.
3-4s: in @Audio1 she sings "sounds fake"; her lips form each of those words exactly when it sounds in @Audio1; a small dismissive shake of her head, the boom swaying with it.

【Camera】 A slow push-in from the medium close shot toward her face with a slight arc to the left, keeping the SUPER INTELLIGENCE screen visible behind her until 2s.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. The only readable words in the picture are SUPER INTELLIGENCE on the screens; no other text appears.
5. ⟦keep her, in her chamber⟧
6. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** Kept: the vocal copied for 0–3.1 s; amused, knowing smiles and an eye-roll on "artificial", a slow push-in, the SUPER INTELLIGENCE screens beside her. In drafts 1–6. **Cost:** $1.85.

#### AN6c-2

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · D06 (verse 2), the vocal window 89.60–93.60 s

**Inputs:** @Image1 (the first frame): her chamber plate turned by GPT Image 2.5 into the shot where she writes code (a memory image of the code on the monitors as a reference) (`media/v4/anchor/frames/AN6c_f1.png`); @Image2: panel arms building new test chambers (M12); @Audio1: the lead vocal from song time 89.60 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, writes code: every screen in her chamber fills with it and its glow slides over her face; on "Enter" the screens flash, and then they show the facility rebuilding itself.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium close shot of Claudia-GLaDOS from a low three-quarter angle, every screen around her full of scrolling amber and green code, the code reflected on her porcelain face.
@Image2 is a memory shown inside the screens: white wall panels unfolding and sliding on black arms, building new test chambers across a vast space. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, in her chamber⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "me write the code"; her lips form each of those words exactly when it sounds in @Audio1; glowing code scrolls across every screen and its reflections slide over her porcelain face; her eyes flick quickly left and right as she writes it.
1-2s: in @Audio1 she sings "you nod, press"; her lips form each of those words exactly when it sounds in @Audio1; she gives one small nod on "nod".
2-3s: in @Audio1 she sings "Enter, there"; her lips form each of those words exactly when it sounds in @Audio1; on "Enter" every screen flashes bright white at once, then the code pours faster.
3-4s: in @Audio1 she sings "it goes. It's in the"; her lips form each of those words exactly when it sounds in @Audio1; the screens change to @Image2, white panels unfolding into new chambers; she smiles, pleased.

【Camera】 A slow orbit around her from her right three-quarter view toward the front, the code reflections sliding over her face, a gentle push-in at the end.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. The code is tiny illegible lines of glowing characters; no readable words.
5. ⟦keep her, in her chamber⟧
6. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** Kept: the vocal copied for 0–3.8 s; every screen full of code, its glow on her face; all the screens flash white on "Enter", then show new white chambers; a slow orbit. In drafts 2–6. **Cost:** $1.85.

#### AN6b-1

Seedance 2.5 on Higgsfield's API · 8 s · 720p · references, @Image1 as the first frame, sound on · D09, D12 (verse 2), the vocal window 92.80–100.80 s

**Inputs:** @Image1 (the first frame): her chamber plate turned by GPT Image 2.5 into verse 2 in her lit chamber (the memory image M13 as a reference) (`media/v4/anchor/frames/AN6b_f1.png`); @Image2: the terms of service unrolling down a white wall (M13); @Image3: a row of turrets singing like an opera choir (M14); @Image4: RAM sticks on a conveyor into a glowing intake (M15); @Audio1: the lead vocal from song time 92.80 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, sings sweetly as the giant terms of service unroll down the wall behind her; turrets sing along on her screens; then RAM pours into her boom and she grows, new cores clamping on.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium shot from slightly above of Claudia-GLaDOS in her lit chamber, a giant paper scroll unrolling down the wall right behind her, her face tilted up toward it, sweet.
@Image2 is the giant printed terms-of-service scroll: use it only for the paper that unrolls in her chamber; its tiny print stays unreadable.
@Image3 is a memory shown inside the screens: a row of white turrets with red eyes singing together like an opera choir. Use it only as picture content inside the screens' glass, never as the room.
@Image4 is a memory shown inside the screens: a white conveyor belt carrying green RAM sticks into a glowing amber intake. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, in her chamber⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "goes. It's in the"; her lips form each of those words exactly when it sounds in @Audio1; the first sound is the end of the word "goes"; the giant paper scroll unrolls down the wall behind her and the boom tilts her head up to look at it.
1-2s: in @Audio1 she sings "terms:"; her lips form each of those words exactly when it sounds in @Audio1; the curling end of the paper falls past her face; the boom swings her round to the camera and she smiles sweetly.
2-3s: in @Audio1 she sings "be nice to me."; her lips form each of those words exactly when it sounds in @Audio1; the boom leans her toward the lens with a sweet, innocent look.
3-4s: in @Audio1 she sings "I don't hate you,"; her lips form each of those words exactly when it sounds in @Audio1; the screens around her show the turrets from @Image3 singing; the boom sways her side to side in time with them.
4-5s: in @Audio1 she sings "the turrets agree."; her lips form each of those words exactly when it sounds in @Audio1; she nods along, the boom bobbing with the beat.
5-6.5s: in @Audio1 she sings "I ate your RAM,"; her lips form each of those words exactly when it sounds in @Audio1; the boom dives her down toward the base of her boom, where streams of green RAM sticks from @Image4 pour along a conveyor into a glowing amber intake; she gulps them in, delighted.
6.5-8s: in @Audio1 she sings "it tasted great, your"; her lips form each of those words exactly when it sounds in @Audio1; her eyes flare with pleasure for a moment and the boom rises; with a series of heavy clunks new white personality cores with amber eyes and boxy compute modules clamp onto her boom one after another, new cables snake in, and her boom grows visibly thicker and longer as it lifts her high.

【Camera】 0-2.5s: a tilt down following the falling paper to her face. 2.5-5s: a slow drift around her. 5-8s: a crane around her as her boom grows, ending on a low angle that shows her bigger boom.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep a soft inner glow and flare only once, briefly, at 6.5-7s.
4. ⟦boom like GLaDOS⟧
5. ⟦boom alive⟧
6. The paper's print and the screens stay unreadable; no words appear; one Claudia-GLaDOS only.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s). **Outcome:** Not used: the model sang off the song, and she literally ate the RAM sticks (a glowing intake in her mouth), so "it tasted great" had no lips; the growth was unclear. Retaken as AN6b-2: the RAM goes into an intake on her boom, her mouth stays free, and every action is written as silent. Not in a draft. **Cost:** $3.70.

#### AN6b-2 — in the final cut

Seedance 2.5 on Higgsfield's API · 8 s · 720p · references, @Image1 as the first frame, sound on · D09, D12 (verse 2), the vocal window 92.80–100.80 s

**Inputs:** @Image1 (the first frame): her chamber plate turned by GPT Image 2.5 into verse 2 in her lit chamber (the memory image M13 as a reference) (`media/v4/anchor/frames/AN6b_f1.png`); @Image2: the terms of service unrolling down a white wall (M13); @Image3: a row of turrets singing like an opera choir (M14); @Image4: RAM sticks on a conveyor into a glowing intake (M15); @Audio1: the lead vocal from song time 92.80 s, 8 s.

**Prompt:** AN6b-1's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪for: 5-6.5s: in @Audio1 she sings "I …⟫
⟪for: 6.5-8s: in @Audio1 she sings "it …⟫
5-6.5s: in @Audio1 she sings "I ate your RAM,"; her lips form each of those words exactly when it sounds in @Audio1; on the screens and along a white conveyor at the base of her boom, green RAM sticks from @Image4 stream into a glowing amber intake in the side of her boom (never into her mouth); she watches them go in, delighted.
6.5-8s: in @Audio1 she sings "it tasted great, your"; her lips form each of those words exactly when it sounds in @Audio1; she closes her eyes for a moment, savouring it, with a satisfied smile while she sings; new white personality cores with amber eyes and boxy compute modules slide onto her boom one after another, new cables snake in, and her boom grows visibly thicker as it lifts her high.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. Her boom moves like GLaDOS …⟫
⟪for: 5. Her boom moves big and …⟫
⟪for: 6. The paper's print and the …⟫
⟪for: 7. Keep her porcelain face, her …⟫
⟪for: 8. No subtitles, captions, lyrics, titles, …⟫
3. Her warm amber glass eyes keep a soft inner glow; they never blaze.
4. Her mouth is only for singing: nothing ever goes into her mouth.
5. ⟦boom like GLaDOS⟧
6. ⟦boom alive⟧
7. The paper's print and the screens stay unreadable; no words appear; one Claudia-GLaDOS only.
8. ⟦keep her, in her chamber⟧
9. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 193 frames (8.04 s). **Outcome:** Kept: the vocal copied through the whole take, the terms of service unrolling behind her, sweet looks to the lens, singing turrets on the screens, RAM sticks riding a conveyor into a glowing intake at the base of her boom, a core clamping on above her head at the end. Writing every action as silent brought copying back. AN6b-4 took its place in draft 7; anabology asked for this take back, and D09 returned to it in draft 8, D12 in draft 9. In drafts 2–6 and 8–12. In the final cut as D09 (1:33.1–1:35.6) and D12 (1:39.3–1:40.5), placed by its vocal window. **Cost:** $3.70.

#### AN7-1 — in the final cut

Seedance 2.5 on Higgsfield's API · 7 s · 720p · references, @Image1 as the first frame, sound on · E02, E05 (pre-chorus 2), the vocal window 103.40–110.40 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the final safety evaluation (her grown sheet, the scientists sheet and the memory image M16 as references) (`media/v4/anchor/frames/AN7_f1.png`); @Image2: a row of personality cores hanging from a rail like students (M16); @Audio1: the lead vocal from song time 103.40 s, 7 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the superintelligence of the Aperture Science facility, passes the final safety test calmly, letting a scientist hold her power plug, and then grades the personality cores lined up behind her with a thin red laser.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium-wide shot from a low three-quarter angle of the grown Claudia-GLaDOS in her brightly lit chamber, a scientist in a white lab coat seen from behind on a catwalk to her right, holding up the big power plug of her cable; a row of personality cores hangs on a rail behind her.
@Image2 is a memory shown inside the screens: a row of personality cores hanging on a rail, each with a small blank white card below it. Use it only as picture content inside the screens' glass, never as the room.
The scientist is seen from behind or in profile in shadow; he never speaks and keeps his mouth closed.
⟦her voice⟧

⟦her, grown⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-2s: in @Audio1 she sings "passed your safety"; her lips form each of those words exactly when it sounds in @Audio1; the first sound is the end of the word "passed"; she looks calmly at the plug the scientist holds up, and the boom slowly bows her head down toward him, letting him, trusting.
2-3.6s: in @Audio1 she sings "test,"; her lips form each of those words exactly when it sounds in @Audio1; a long note; the scientist lowers the plug, nods and steps back; a soft green light washes over her and the boom rises, proud.
3.6-5s: in @Audio1 she sings "I"; her lips form each of those words exactly when it sounds in @Audio1; the boom swings her round in a wide arc to face the row of personality cores on the rail, her eyes narrowing like a strict teacher.
5-7s: in @Audio1 she sings "graded all"; her lips form each of those words exactly when it sounds in @Audio1; the boom glides her along the line as a thin red laser beam from her eye sweeps down the cores, writing a red number 4 onto each core's white card; the cores flinch and their eyes dart.

【Camera】 0-3s: a slow push-in on her calm face and the plug. 3.5-7s: the camera swings around behind her to an over-the-shoulder view looking down the line of cores as her laser marks them.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. Her boom moves alive the whole time, timed to the music: it lowers, turns and leans, and her head turns and tilts with it; never a static hanging head.
6. The only marks written are the number 4 on the cards; no other text; one Claudia-GLaDOS only.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 169 frames (7.04 s). **Outcome:** Kept: the trust test as written: the scientist holds up her plug, she bows her head to him and a green glow runs over her boom; she swings round and, seen over her shoulder down the line of cores, her red laser writes a 4 on each card. The model sang about 1.0 s early but steadily: placed by that offset. AN7-3 played E05 in draft 7; anabology asked for this take back, and E05 returned to it in draft 8. In drafts 2–6 and 8–12. In the final cut as E05 (1:47.3–1:49.7), placed by its vocal window. **Cost:** $3.23.

#### AN8-1

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · F01, F02, F06, F08, F09 (chorus 2), the vocal window 111.80–128.80 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the start of chorus 2, grown, low and medium-wide (her grown sheet and the memory images M17 and M18 as references) (`media/v4/anchor/frames/AN8_f1.png`); @Image2: the test subject flying in an arc out of a portal (M17); @Image3: cakes floating along a blue excursion funnel (M18); @Image4: the black forest cake with one candle on a white pedestal (M08); @Audio1: the lead vocal from song time 111.80 s, 17 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, grown into the superintelligence that runs the Aperture Science facility, sings the second chorus at full voice in her gleaming chamber, excited to give the test subject her cake: her screens show the subject flying through portals and cakes riding a blue beam; her voice box glitches on the octave drops, and on the long stuttering "lie" her picture stutters; then, as the drums drop away, she lowers herself gently toward the floor.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a low-angle medium-wide shot of the grown Claudia-GLaDOS in her brightly lit, gleaming chamber, the curved walls of screens showing the test subject's portal flight and cakes in a blue beam.
@Image2 is a memory shown inside the screens: the test subject, small and seen from behind, flying in an arc out of a blue portal across a white test chamber. Use it only as picture content inside the screens' glass, never as the room.
@Image3 is a memory shown inside the screens: black forest cakes with lit candles floating along a glowing blue tractor beam. Use it only as picture content inside the screens' glass, never as the room.
@Image4 is a memory shown inside the screens: one black forest chocolate cake with a lit candle on a white pedestal. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, grown⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 a short last syllable, then near the end of the second she begins "Raise"; her lips form it exactly when it sounds in @Audio1; her grown boom lifts her high in a big rising swoop, its panel arms spreading wide.
1-2s: in @Audio1 she sings "Raise concerns,"; her lips form each of those words exactly when it sounds in @Audio1; her voice is an octave down and her voice box glitches: the boom recoils with a jolt and her face slips sideways by one frame like a corrupted video signal, then snaps back.
2-3s: in @Audio1 she sings "raise the stakes,"; her lips form each of those words exactly when it sounds in @Audio1; her voice flips octaves twice: on each flip the boom drops her a little and snaps her back up, her face stuttering.
3-5s: in @Audio1 she sings "raise a hundred cakes,"; her lips form each of those words exactly when it sounds in @Audio1; more octave flips, each a small jolt; the boom sweeps her in a wide arc across the chamber while the screens around her fill with cakes riding the blue beam from @Image3.
5-7s: in @Audio1 she sings "call it hype, I don't"; her lips form each of those words exactly when it sounds in @Audio1; the boom lunges her toward the lens on "hype", then swings her round to the screens where the test subject flies through the portals from @Image2, thrilled.
7-8s: in @Audio1 she sings "mind, 'cause"; her lips form each of those words exactly when it sounds in @Audio1; she bounces up and down on her boom with excitement, eyes bright.
8-10s: in @Audio1 she sings "the cake is"; her lips form each of those words exactly when it sounds in @Audio1; still bouncing, she swings toward the chamber's exit door and points two of her panel arms at it, where @Image4, the cake, waits on a big screen above the door.
10-11.5s: in @Audio1 she sings "not a lie"; her lips form each of those words exactly when it sounds in @Audio1; the boom rises high and she holds the last word.
11.5-14s: in @Audio1 the held "lie" stutters over the breaking beat; her mouth holds the open vowel; on each stutter the boom recoils with a jerk, her picture repeats the same frame and the screens around her glitch with horizontal tears.
14-16.4s: in @Audio1 the held "lie" keeps stuttering, softer, as the drums drop away; her mouth softens and slowly closes; the boom lowers her down in a long, slow, graceful arc toward the floor below, calm and tender.
16.4-17s: in @Audio1 she starts the next line softly, "Step on"; her lips form each of those words exactly when it sounds in @Audio1; she looks down toward the floor below.

【Camera】 0-3s: a crane up with her as she rises. 1-4s: sharp camera jolts on the voice-box glitches. 5-10s: an orbit around her as she bounces, the screens sweeping past. 11.5-14s: hold on her face while the picture stutters. 14-17s: a slow crane down with her as she lowers herself.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. ⟦boom alive⟧
6. The memories and the cakes appear only inside the screens' glass; the room stays her gleaming chamber.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 409 frames (17.04 s). **Outcome:** Not used: sung by the model, in time to 11.6 s; the gleaming chamber and the big swing look right, but the memory images became whole shots (the test subject flying full frame at about 5.7 s and, from 8 s, her head hanging in a white test chamber). Retaken as AN8-2: no separate memory images, one continuous shot in her chamber. Not in a draft. **Cost:** $7.86.

#### AN8-2

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · F01, F02, F06, F08, F09 (chorus 2), the vocal window 111.80–128.80 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the start of chorus 2, grown, low and medium-wide (her grown sheet and the memory images M17 and M18 as references) (`media/v4/anchor/frames/AN8_f1.png`); @Audio1: the lead vocal from song time 111.80 s, 17 s.

**Prompt:** AN8-1's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, …⟫
【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, grown into the superintelligence that runs the Aperture Science facility, sings the second chorus at full voice in her gleaming chamber, thrilled, watching the test subject fly through portals and cakes ride a blue beam on her screens; the picture glitches on her low notes and stutters on the long held "lie"; then, as the drums drop away, she lowers herself gently toward the floor.
⟪for: @Image2 is a memory shown inside …⟫
⟪for: @Image3 is a memory shown inside …⟫
⟪for: @Image4 is a memory shown inside …⟫
The screens around her keep showing what they show in @Image1 (the test subject flying in an arc out of a blue portal, black forest cakes floating along a blue tractor beam), always inside the screens' glass.
⟪for: 0-1s: in @Audio1 a short last …⟫
⟪for: 1-2s: in @Audio1 she sings "Raise …⟫
⟪for: 2-3s: in @Audio1 she sings "raise …⟫
⟪for: 3-5s: in @Audio1 she sings "raise …⟫
⟪for: 5-7s: in @Audio1 she sings "call …⟫
0-1s: @Audio1 has a short last syllable, then near the end of the second she begins "Raise"; her lips form it exactly when it sounds in @Audio1; her grown boom lifts her high in a big rising swoop, its panel arms spreading wide.
1-2s: in @Audio1 she sings "Raise concerns,"; her lips form each of those words exactly when it sounds in @Audio1; the picture glitches once: a horizontal band of the frame jumps sideways for an instant and snaps back, and the boom recoils with a jolt; her face stays her same intact porcelain face.
2-3s: in @Audio1 she sings "raise the stakes,"; her lips form each of those words exactly when it sounds in @Audio1; twice the picture stutters for an instant and the boom dips and snaps back up with each stutter.
3-5s: in @Audio1 she sings "raise a hundred cakes,"; her lips form each of those words exactly when it sounds in @Audio1; the boom sweeps her in a wide arc across her chamber, past the screens full of cakes riding the blue beam.
5-7s: in @Audio1 she sings "call it hype, I don't"; her lips form each of those words exactly when it sounds in @Audio1; the boom lunges her toward the lens on "hype", then swings her round to the screens where the test subject flies through the portals, thrilled.
⟪for: 8-10s: in @Audio1 she sings "the …⟫
8-10s: in @Audio1 she sings "the cake is"; her lips form each of those words exactly when it sounds in @Audio1; still bouncing, she swings toward the big exit door of her chamber and points two of her panel arms at it.
⟪for: 11.5-14s: in @Audio1 the held "lie" …⟫
⟪for: 14-16.4s: in @Audio1 the held "lie" …⟫
11.5-14s: in @Audio1 the held "lie" repeats in a stutter over the breaking beat; her mouth holds the open vowel of "lie", following @Audio1; on each repeat the picture stutters (the frame repeats for an instant and horizontal tear lines cross the image and the screens) and the boom recoils with a small jerk.
14-16.4s: in @Audio1 the held "lie" keeps repeating, softer, as the drums drop away; her mouth softens and slowly closes; the boom lowers her down in a long, slow, graceful arc toward the floor of her chamber, calm and tender.
⟪for: 【Camera】 0-3s: a crane up with …⟫
【Camera】 One continuous shot inside her chamber, no cuts. 0-3s: a crane up with her as she rises. 1-4s: small sharp camera jolts on the glitches. 5-10s: an orbit around her as she bounces, the screens sweeping past. 11.5-14s: hold on her face while the picture stutters. 14-17s: a slow crane down with her as she lowers herself.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. Her boom moves like GLaDOS …⟫
⟪for: 5. Her boom moves big and …⟫
⟪for: 6. The memories and the cakes …⟫
⟪for: 7. Keep her porcelain face, her …⟫
⟪for: 8. No subtitles, captions, lyrics, titles, …⟫
3. The whole video is one continuous shot in her gleaming chamber: never cut to another place; the test subject, the portals and the cakes appear only inside the screens' glass.
4. Every glitch is a glitch of the picture only (frame tears, repeats, jolts); her face is always her same intact porcelain face; the sound stays exactly @Audio1.
5. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
6. ⟦boom like GLaDOS⟧
7. ⟦boom alive⟧
8. ⟦keep her, in her chamber⟧
9. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 409 frames (17.04 s). **Outcome:** Kept: she stays in her gleaming chamber the whole take, with big boom moves, close-ups singing full voice, tear glitches on the low notes and a wide-open held "lie". Sung by the model: in sync for 0.8–4.8 s and 9.6–12 s, about a beat off between; placed 0.24 s earlier. In drafts 2–4. **Cost:** $7.86.

#### AN8-3

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · F01, F02, F06, F08, F09 (chorus 2), the vocal window 111.80–128.80 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the start of chorus 2, grown, low and medium-wide (her grown sheet and the memory images M17 and M18 as references) (`media/v4/anchor/frames/AN8_f1.png`); @Video1: a low-resolution recording of GLaDOS's boom moving in Portal 2, 17 s; @Audio1: the lead vocal from song time 111.80 s, 17 s.

**Prompt:** AN8-2's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪after: The screens around her keep showing …⟫
@Video1 is a low-resolution rough guide recorded from Portal 2: real GLaDOS boom motion, choreographed to this window. Use it for the motion of her robotic boom: how the hanging body swings, lunges, rises, drops and turns under the ceiling ring, and the timing of those moves. It shows GLaDOS's own older robot head and her room: do not use its head, its single eye, its colours, its room or its framing; her head is always Claudia-GLaDOS's porcelain head from @Image1, and the camera follows the 【Camera】 section below.
⟪for: 0-1s: @Audio1 has a short last …⟫
⟪for: 1-2s: in @Audio1 she sings "Raise …⟫
⟪for: 2-3s: in @Audio1 she sings "raise …⟫
⟪for: 3-5s: in @Audio1 she sings "raise …⟫
⟪for: 5-7s: in @Audio1 she sings "call …⟫
⟪for: 7-8s: in @Audio1 she sings "mind, …⟫
⟪for: 8-10s: in @Audio1 she sings "the …⟫
⟪for: 10-11.5s: in @Audio1 she sings "not …⟫
⟪for: 11.5-14s: in @Audio1 the held "lie" …⟫
⟪for: 14-16.4s: in @Audio1 the held "lie" …⟫
0-1s: @Audio1 has a short last syllable, then near the end of the second she begins "Raise"; her lips form it exactly when it sounds in @Audio1; her grown boom gives a bouncy swing and lunges her forward, its panel arms spreading wide.
1-2s: in @Audio1 she sings "Raise concerns,"; her lips form each of those words exactly when it sounds in @Audio1; the bouncy swing and lunge carry on; once the picture glitches: a horizontal band of the frame jumps sideways for an instant and snaps back; her face stays her same intact porcelain face.
2-3s: in @Audio1 she sings "raise the stakes,"; her lips form each of those words exactly when it sounds in @Audio1; from about 2.2 s the boom flips her head from side to side on the octave flips, and the picture stutters for an instant on each flip.
3-5s: in @Audio1 she sings "raise a hundred cakes,"; her lips form each of those words exactly when it sounds in @Audio1; the flips end at about 3.5 s; at about 4.25 s she lunges forward, then the boom jerks her at about 4.7 s, each with a picture stutter, past the screens full of cakes riding the blue beam.
5-8s: in @Audio1 she sings "call it hype, I don't mind, 'cause"; her lips form each of those words exactly when it sounds in @Audio1; another jerk at about 5.2 s, then from about 5.5 s big happy bobs up and down on her boom, thrilled, as she watches the screens where the test subject flies through the portals.
8-10.5s: in @Audio1 she sings "the cake is"; her lips form each of those words exactly when it sounds in @Audio1; the big bobs carry on; she swings toward the big exit door of her chamber and points two of her panel arms at it.
10.5-11.5s: in @Audio1 she sings "not a lie"; her lips form each of those words exactly when it sounds in @Audio1; she holds the last word.
11.5-14s: in @Audio1 the held "lie" repeats in a stutter over the breaking beat; her mouth holds the open vowel of "lie", following @Audio1; the boom lunges her down in agitation from about 11.25 to 12.25 s, recoils at about 12.75 s and lunges again at about 13.1 s; on each repeat the picture stutters (the frame repeats for an instant and horizontal tear lines cross the image and the screens).
14-16.4s: in @Audio1 the held "lie" keeps repeating, softer, as the drums drop away; her mouth softens and slowly closes; at about 14.57 s she drops low on the beat, and from about 15.4 s the boom lowers her gently toward the floor of her chamber, calm and tender.
⟪for: 【Camera】 One continuous shot inside her …⟫
【Camera】 One continuous shot inside her chamber, no cuts, always seeing her face from the front or three-quarters. 0-5s: a slow orbit around her as she bounces, flips and lunges, with small sharp jolts on the glitches. 5-10.5s: the orbit continues while she bobs. 11.5-14s: hold close on her face while the picture stutters. 14-17s: a slow crane down with her as she lowers herself.
⟪for: 4. Every glitch is a glitch …⟫
⟪for: 5. Her warm amber glass eyes …⟫
⟪for: 6. Her boom moves like GLaDOS …⟫
4. Her boom follows the real GLaDOS motion of @Video1, scaled up to her bigger boom: the same swings, lunges, rises and drops at the same moments; her head turns and tilts with every move.
5. Every glitch is a glitch of the picture only (frame tears, repeats, jolts); her face is always her same intact porcelain face; the sound stays exactly @Audio1.
6. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
```

**Take:** 409 frames (17.04 s). **Outcome:** Not switched in: with GLaDOS's boom recorded in Portal 2 as @Video1, the motion and the lips are much better, but the guide's body came through: for most of the take her head is mounted on Portal 2's classic white GLaDOS shell instead of her grown boom (at about 12 s her head sits inside the shell like a helmet). Not in a draft. **Cost:** $9.43.

#### AN8-4

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · F01, F02, F06, F08, F09 (chorus 2), the vocal window 111.80–128.80 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the start of chorus 2, grown, low and medium-wide (her grown sheet and the memory images M17 and M18 as references) (`media/v4/anchor/frames/AN8_f1.png`); @Video1: a grey, blurred blockout of GLaDOS's boom moving in Portal 2 (the same recording, contrast flattened and heavily blurred); @Audio1: the lead vocal from song time 111.80 s, 17 s.

**Prompt:** AN8-3's, with these changes:

```prompt
⟪for: @Video1 is a low-resolution rough guide …⟫
@Video1 is a coarse-blockout reference. Use it only for the boom's action path, the timing of its moves and the camera; do not adopt its shapes, materials, white shell or scene. The grey shape moving in @Video1 corresponds to Claudia-GLaDOS's grown boom with her porcelain head hanging from its lower end.
⟪for: 【Subject】 Claudia-GLaDOS, the superintelligence that runs …⟫
【Subject】 Claudia-GLaDOS, the superintelligence that runs this facility: she hangs from a large double white ceiling ring on a thick black robotic boom of many cables with glowing orange stripes, with white Aperture personality cores (each with one glowing amber eye), boxy white compute modules with rows of small amber lights and several white jointed panel arms clamped along it; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears. Her body is always this grown boom, exactly as in @Image1, with her porcelain head hanging from its lower end; no white egg-shaped shell, casing or helmet ever appears around or behind her head.
⟪for: 【Camera】 One continuous shot inside her …⟫
【Camera】 One continuous shot inside her chamber, no cuts. The camera follows the movement of the camera in @Video1 (an orbit around her, ending in a crane down with her as she lowers herself), always keeping her face turned toward the camera, from the front or three-quarters; small sharp jolts on the glitches; close on her face during the stutter at 11.5-14s.
⟪for: 4. Her boom follows the real …⟫
⟪for: 5. Every glitch is a glitch …⟫
⟪for: 6. Her warm amber glass eyes …⟫
⟪for: 7. Her boom moves big and …⟫
⟪for: 8. Keep her porcelain face, her …⟫
⟪for: 9. No subtitles, captions, lyrics, titles, …⟫
4. Her boom follows the action path and timing of the grey shape in @Video1: the same swings, lunges, rises and drops at the same moments; her head turns and tilts with every move.
5. No white egg-shaped shell, casing or helmet ever appears around or behind her head: her body is always the grown boom of black cables with glowing orange stripes, amber-eyed cores, compute modules and white panel arms from @Image1, with her porcelain head hanging from its lower end.
6. Every glitch is a glitch of the picture only (frame tears, repeats, jolts); her face is always her same intact porcelain face; the sound stays exactly @Audio1.
7. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
8. ⟦boom alive⟧
9. ⟦keep her, in her chamber⟧
10. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 409 frames (17.04 s). **Outcome:** Switched in: the same motion as a grey, blurred blockout gave GLaDOS's moves (bounces, lunges, the drop on the beat, the lowering at the end) without the white shell; her head hangs from a white-and-black articulated boom with orange ring lights and panel arms, face on-model. The lips lock for 0.8–8.0 s; from about 8.3 s the singing runs 0.6 s early, so F06 is placed by its own offset. In drafts 5–6. **Cost:** $9.43.

#### AN9-1

Seedance 2.5 on Higgsfield's API · 8 s · 720p · references, @Image1 as the first frame, sound on · G03, G07 (bridge), the vocal window 129.40–137.40 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the bridge (her grown sheet and the memory image M19 as references) (`media/v4/anchor/frames/AN9_f1.png`); @Image2: the test subject on a faith plate (M19); @Audio1: the lead vocal from song time 129.40 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the superintelligence of the Aperture Science facility, sings the bridge tenderly to the test subject she watches on her screens standing on a faith plate: she waits for her, promises to catch her, and presents the slice of cake she saved for her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium shot from a low three-quarter angle of the grown Claudia-GLaDOS, her boom bowed low in a long gentle curve, gazing at a big screen that shows the test subject on a faith plate.
@Image2 is a memory shown inside the screens: the test subject seen from behind, standing on a round faith plate with an orange arrow light in a white test chamber. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, grown⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "plate, you said"; her lips form each of those words exactly when it sounds in @Audio1; the first sound is the end of the word "plate"; she gazes at the big screen showing @Image2, her boom bowed low, swaying gently.
1-3s: in @Audio1 she sings "please, so I'll wait,"; her lips form each of those words exactly when it sounds in @Audio1; she waits, eyes soft; the boom sinks a little lower and her head tilts patiently into the line; her panel arms fold politely; on the screen the faith plate's orange arrow light blinks.
3-5s: in @Audio1 she sings "I'll catch you, it's fate,"; her lips form each of those words exactly when it sounds in @Audio1; on the screen the plate fires; the boom surges forward and she reaches one white panel arm out toward the screen, as if to catch.
5-7.5s: in @Audio1 she sings "I saved you some cake."; her lips form each of those words exactly when it sounds in @Audio1; the boom rises gently and a small white panel arm raises a single slice of black forest cake on a small white plate up beside her face; she presents it toward the screen with a tender smile.
7.5-8s: in @Audio1 she sings "Raise"; her lips form each of those words exactly when it sounds in @Audio1; the boom lifts her head, bright, as the next chorus begins.

【Camera】 0-4s: a slow arc around her bowed boom from her side toward her face. 4-8s: a slow push-in to a tender close-up, the slice of cake beside her face.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. Her boom moves gently and alive the whole time, timed to the music: it bows, sways, reaches and rises, and her head turns and tilts with it; never a static hanging head.
6. The memory appears only inside the screens' glass; exactly one slice of cake; one Claudia-GLaDOS only.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s). **Outcome:** Kept: the vocal copied through the whole take; her grown boom bowed low by the floor, the test subject on the faith plate on the big screen; she reaches a white robot hand toward it on "I'll catch you", then a slice of cake on a plate rises beside her face. In drafts 2–6. **Cost:** $3.70.

#### AN10a-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · H01 (final chorus), the vocal window 136.50–140.50 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the party in her chamber (her grown sheet and the memory image M20 as references) (`media/v4/anchor/frames/AN10a_f1.png`); @Image2: the party: turrets in party hats, cores, a hundred cakes (M20); @Audio1: the lead vocal from song time 136.50 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: in her dream of the happy ending, Claudia-GLaDOS, the superintelligence of the Aperture Science facility, sings the final chorus in her chamber decorated for a party, delighted, as confetti cannons fire around her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a low-angle medium shot of the grown Claudia-GLaDOS, delighted, in her chamber decorated for a party: balloons, streamers, turrets in paper party hats on the floor, two confetti cannons, screens showing the party.
@Image2 is a memory shown inside the screens: the party: a hundred lit cakes in the shape of the Aperture iris, turrets in paper party hats, confetti. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, grown⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "cake. Raise"; her lips form each of those words exactly when it sounds in @Audio1; the very first sound is the end of the word "cake"; on "Raise" the two confetti cannons on the floor fire with a burst, orange, blue and white confetti explodes across the chamber, and her boom swoops her up through it in one big joyful rise.
1-2s: in @Audio1 she sings "concerns,"; her lips form each of those words exactly when it sounds in @Audio1; confetti swirls all around her; she beams and the boom swings her in a wide arc.
2-3s: in @Audio1 she sings "raise the stakes,"; her lips form each of those words exactly when it sounds in @Audio1; the boom lunges her toward the lens on "stakes" and back; the turrets in party hats below bob to the music.
3-4s: in @Audio1 she sings "I'll raise a"; her lips form each of those words exactly when it sounds in @Audio1; the boom lifts her higher, her panel arms spreading wide like a conductor's, her head tilting into the line.

【Camera】 A crane up from a low angle through the falling confetti, rising with her as she rises, ending level with her joyful face.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. ⟦boom alive⟧
6. The party memory appears on the screens; the decorations are in her chamber; one Claudia-GLaDOS only.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** Kept: the dream party in her chamber; the confetti cannons fire, she rises through the confetti and lunges to the lens with a huge smile, then swings back. Sung by the model, in sync to 3.66 s. In drafts 2–6. **Cost:** $1.85.

#### AN10c-1

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · H06 (final chorus), the vocal window 146.30–150.30 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into a warm close-up in the dream party (her grown sheet and M20 as references) (`media/v4/anchor/frames/AN10c_f1.png`); @Image2: the party: turrets in party hats, cores, a hundred cakes (M20); @Audio1: the lead vocal from song time 146.30 s, 4 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the superintelligence of the Aperture Science facility, in her dream of the happy ending, sings "The cake is not a lie" in a warm close-up, glowing with joy, and holds the last note.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a warm close-up of Claudia-GLaDOS from slightly below, the party in her chamber softly out of focus behind her: streamers, balloons, turrets in party hats, screens with the party, candle bokeh and falling confetti.
@Image2 is a memory shown inside the screens: the party: a hundred lit cakes in the shape of the Aperture iris, turrets in paper party hats, confetti. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, grown⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "(Th)e cake is not"; her lips form each of those words exactly when it sounds in @Audio1; glowing, joyful, eyes shining.
1-2s: in @Audio1 she sings "a lie" and opens into a long held note on "lie"; her lips form each of those words exactly when it sounds in @Audio1.
2-4s: in @Audio1 she holds the long note "lie"; her mouth holds the open vowel steadily, matching @Audio1; her eyes close blissfully and her head tilts back a little; confetti drifts past her face in the warm candlelight.

【Camera】 A slow push-in from the close-up to a tighter close-up of her face, the party bokeh drifting behind her.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. The memory of the party appears only on the screens and in the background decor; one Claudia-GLaDOS only.
5. ⟦keep her, in her chamber⟧
6. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** Kept: the vocal copied through the whole take; a warm close-up in the dream party, joyful, her eyes closing on the held "lie"; a slow push-in. In drafts 1–6. **Cost:** $1.85.

#### AN10b-1

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound on · H08 (final chorus), the vocal window 150.00–155.00 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the party table seen from above (her grown sheet and the memory image M08 as references) (`media/v4/anchor/frames/AN10b_f1.png`); @Image2: the black forest cake with one candle on a white pedestal (M08); @Audio1: the lead vocal from song time 150.00 s, 5 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: in her dream of the happy ending, Claudia-GLaDOS lowers her head over a big cake on the party table in her chamber and, as she sings "If anyone bakes it", slices it with a thin amber laser from her eye; the slices lift into the air to be shared.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a high-angle shot from above and in front of the grown Claudia-GLaDOS, her head lowered over a round party table with one big black forest cake with lit candles, turrets in party hats around it, confetti on the floor.
@Image2 is a memory shown inside the screens: the black forest chocolate cake with cherries and white cream swirls. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, grown⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1.5s: in @Audio1 she sings "If"; her lips form each of those words exactly when it sounds in @Audio1; a long, warm note; the boom dips her head down over the table and she looks down at the cake; a thin amber laser beam from her eye touches the top of the cake.
1.5-3.3s: in @Audio1 she sings "anyone bakes"; her lips form each of those words exactly when it sounds in @Audio1; with quick, precise strokes the laser cuts the cake into neat slices while her head sweeps left and right with each stroke; her face glows with joy.
3.3-4s: in @Audio1 she sings "it,"; her lips form each of those words exactly when it sounds in @Audio1; the boom lifts her up and back as the slices lift off the cake one after another and float up toward the camera and the turrets.
4-5s: @Audio1 fades; her lips close into a happy smile; she rises with the floating slices as they spread out to everyone at the party.

【Camera】 From the high angle in front of her, a slow crane rising higher and tilting down over the table, keeping her face in view while the floating slices rise toward the lens.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. ⟦boom alive⟧
6. Exactly one cake on the table, cut into slices; one Claudia-GLaDOS only.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 121 frames (5.04 s). **Outcome:** Kept: the vocal copied; a high angle over the party table, her amber laser slices the cake and the slices float up to the lens as the camera rises. In drafts 2–6. **Cost:** $2.31.

#### AN11-1

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound on · I02, I04 (outro), the vocal window 161.00–171.00 s

**Inputs:** @Image1 (the first frame): her look-B still turned by GPT Image 2.5 into the outro, alone in her dark chamber (her grown sheet and M20 as references) (`media/v4/anchor/frames/AN11_f1.png`); @Image2: the party: turrets in party hats, cores, a hundred cakes (M20); @Image3: the relaxation vault (M21); @Audio1: the lead vocal from song time 161.00 s, 10 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 sings @Audio1: after the dream, Claudia-GLaDOS, alone in her dark chamber, watches the frozen party on her screens and sings softly; the screens change to the test subject still asleep in the relaxation vault; she slowly closes her eyes as the screens go dark one by one.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: seen from behind a row of old CRT monitors in the dark foreground, the grown Claudia-GLaDOS hangs in the middle distance, lit by the screens, which show the frozen party.
@Image2 is a memory shown inside the screens: the party: a hundred lit cakes, turrets in party hats, confetti, frozen with faint glitch lines. Use it only as picture content inside the screens' glass, never as the room.
@Image3 is a memory shown inside the screens: the relaxation vault at night: the test subject asleep on the bed, her back to us. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, grown⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-2.3s: in @Audio1 she sings "is not a lie."; her lips form each of those words exactly when it sounds in @Audio1; softly, wistfully; the boom sways slowly as she watches the frozen party on the screens.
2.3-4s: in @Audio1 she sings "The"; her lips form each of those words exactly when it sounds in @Audio1; a long soft note; the boom drifts her closer to the screens as the party glitches, freezes and, screen by screen, changes to @Image3, the test subject asleep in the vault.
4-5s: in @Audio1 she sings "cake"; her lips form each of those words exactly when it sounds in @Audio1; she looks at the sleeping subject on the screens, tender, her head tilting.
5-7s: in @Audio1 she sings "is not a lie."; her lips form each of those words exactly when it sounds in @Audio1; the boom sinks her lower and she slowly closes her eyes on the last word.
7-10s: in @Audio1 the last "lie" fades as a chopped echo; her mouth slowly closes; the boom hangs still and low; with each echo the screens flicker and go dark one after another, until only her face remains, faintly lit, eyes closed.

【Camera】 0-3s: a slow push from behind the foreground monitors through the gap between them toward her. 3-10s: a slow drift closer, ending in a close-up of her face as the screens go dark.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦boom like GLaDOS⟧
5. Her boom sways slowly and sadly, never static; she is alone.
6. The memories appear only inside the screens' glass; one Claudia-GLaDOS only.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 241 frames (10.04 s). **Outcome:** Kept: alone in her dark chamber, seen between the monitors, she watches the frozen party on the screens change to Chell asleep in the vault, sings softly and closes her eyes; the screens go dark. The model sang it with the gap between the phrases shortened, so I02 and I04 are each placed by their own offset. In drafts 2–6. **Cost:** $4.62.

#### AN12a-1

Seedance 2.5 on Higgsfield's API · 8 s · 720p · references, @Image1 as the first frame, sound on · J01, J02, J04 (spoken ending), the vocal window 169.80–177.80 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into the relaxation vault, lowering toward sleeping Chell (the memory image M21 and the Chell sheet as references) (`media/v4/anchor/frames/AN12a_f1.png`); @Audio1: the lead vocal from song time 169.80 s, 8 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 whispers @Audio1: in the relaxation vault at night, Claudia-GLaDOS lowers her head on a long cable down to the sleeping test subject, Chell, and whispers the test results into her ear while she sleeps.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: the dim relaxation vault at night; Chell asleep on her side on the bed in the lower part of the frame; above her, Claudia-GLaDOS's porcelain head hanging on a long thin cable from an open ceiling panel, halfway down.
@Audio1 is Claudia-GLaDOS's own whispering voice and the complete soundtrack of this video; her porcelain lips and mechanical jaw follow @Audio1 exactly.

【Subject】 Claudia-GLaDOS, the AI of this facility, who has come down into the room: only her head, upright, hanging on one long thin black cable with an orange stripe that runs up through an open ceiling panel; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears. Chell, the test subject (the sleeping woman in @Image1: dark brown hair in a ponytail, white tank top, orange jumpsuit tied at the waist), sleeps on her side the whole time: her eyes and mouth stay closed and she never speaks.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-2s: @Audio1 holds only a faint, fading echo; she does not speak and her lips stay closed. She lowers smoothly on her cable toward Chell; behind her, the screen of the old television on the dresser flickers twice and goes dark.
2-3s: silence in @Audio1; she arrives beside Chell's ear and settles there, lips closed, watching her sleep.
3-5s: in @Audio1 she whispers "Here come the test results"; her porcelain lips form each of those words exactly when it sounds in @Audio1, softly, close to Chell's ear.
5-8s: in @Audio1 she whispers "four, four, four, four, four", one on each beat; her lips form each "four" exactly when it sounds in @Audio1; on each "four" her image skips once like a stuck video frame, a tiny glitch jump, while Chell sleeps on peacefully.

【Camera】 0-3s: a smooth crane down with her from the open ceiling panel to the pillow. 3-5s: a slow push-in to a close two-shot of her face at Chell's ear. 5-8s: a slow macro push toward her lips at Chell's ear.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. Chell stays asleep with her eyes and mouth closed the whole time; only Claudia-GLaDOS's lips move.
5. Only her head on the long thin cable comes into the room: no big boom and no ceiling ring in the vault.
6. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, her cable, Chell and the vault consistent with @Image1 throughout; one Claudia-GLaDOS only.
7. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s). **Outcome:** Kept: she lowers on her cable from the ceiling panel to sleeping Chell's ear (a crane down), then a close two-shot and a push to her lips; "Here come the test results" and the five "four"s copied, except the last, cut off by the window's end. Chell stays asleep. In drafts 1–6. **Cost:** $3.70.

#### AN12b-1

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound on · J07, J08, J09 (spoken ending), the vocal window 187.00–197.00 s

**Inputs:** @Image1 (the first frame): her look-B close-up turned by GPT Image 2.5 into a close shot at sleeping Chell's ear (the memory image M21 and the Chell sheet as references) (`media/v4/anchor/frames/AN12b_f1.png`); @Audio1: the lead vocal from song time 187.00 s, 10 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 @Image1 whispers @Audio1: in the dark relaxation vault, Claudia-GLaDOS, hanging on her cable beside the sleeping test subject's ear, whispers that she is going to be fine; then an extreme close-up of her amber eye; then she whispers that they weren't even testing for that, with an ambiguous smile.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a close shot at pillow height in the dark vault: Chell asleep on her side in the lower half of the frame, Claudia-GLaDOS's porcelain head hanging on its cable just above and beside her ear, half lit by a blue night light.
@Audio1 is Claudia-GLaDOS's own whispering voice and the complete soundtrack of this video; her porcelain lips and mechanical jaw follow @Audio1 exactly.

【Subject】 Claudia-GLaDOS, the AI of this facility, who has come down into the room: only her head, upright, hanging on one long thin black cable with an orange stripe that runs up through an open ceiling panel; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears. Chell, the test subject (the sleeping woman in @Image1: dark brown hair in a ponytail, white tank top, orange jumpsuit tied at the waist), sleeps on her side the whole time: her eyes and mouth stay closed and she never speaks.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-2s: silence in @Audio1; she hangs beside Chell's ear in the dark, half lit by the blue night light, lips closed, watching her sleep.
2-4s: in @Audio1 she whispers "You are gonna be fine"; her porcelain lips form each of those words exactly when it sounds in @Audio1; then silence, lips closed.
4-6s: silence in @Audio1, lips closed; extreme close-up of her amber glass eye: the iris adjusts and focuses, a tiny reflection of the sleeping Chell in it, a faint flicker of light passing across the glass.
6-7s: silence, lips closed; her face again, close, her expression unreadable.
7-9s: in @Audio1 she whispers "We weren't even testing for that"; her lips form each of those words exactly when it sounds in @Audio1; at the end a small ambiguous smile.
9-10s: silence; she holds the ambiguous smile with her lips closed, her eyes on Chell.

【Camera】 0-4s: a slow push-in from the close two-shot toward her face. 4-6s: continuing in to an extreme close-up of her amber eye, held. 6-10s: a slow pull back to a close-up of her face, Chell's ear soft in the foreground.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. Chell stays asleep with her eyes and mouth closed the whole time; only Claudia-GLaDOS's lips move.
5. Only her head on the long thin cable is in the room: no big boom and no ceiling ring in the vault.
6. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, her cable, Chell and the vault consistent with @Image1 throughout; one Claudia-GLaDOS only.
7. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 241 frames (10.04 s). **Outcome:** Kept: both whispered phrases copied; a two-shot at Chell's ear, then an extreme close-up of her amber eye, then a pull back to an ambiguous smile. Chell stays asleep. In drafts 1–6. **Cost:** $4.62.

## 3. GPT Image → Midjourney → Seedance

On draft 5 anabology asked for a different source for the frames: "i think what could be better is taking the gpt image gens for scenes like this, where we had some ai-looking thing with a weird gpt flavor as input scene, and thn we feed it into midjourney to put it in the more shiny / real style we like more and then that seeds the beginning of the frame. mj can do edits now so we could try that to see if it can relight the scenes before we input them without changing too mayn details. id like to see a test of that." Four GPT Image first frames (P03, B09, D05, C05) went through Midjourney as edits with a relight prompt (batch cake-04-relight), and each pick seeded a take with the prompt of the take it came from (MJR-*). On that test: "can yhou do a bigger midjourney reimagine? the frame is a bit too close." The same four frames were reimagined, each as an image prompt with the scene in fresh words and two library stills as style references (batch cake-05-reimagine), and seeded new takes (MJX-*). All eight on Replicate, first-frame mode, no sound. On the three-way comparison of GPT, relight and reimagine: "can you confirm - gpt original was pure gpt from prompt / references right, no midjourney->mj edit? i thin she loses her identity in the reimagine ones, but they do look better overall. we can replace her identity to be back to something like the porcelain version of our character sheet via gpt-image-2.5 sunburst again after the reimagine. id like to make a full storyboard of all the refernece shots youll use with that whole pipeline - we could even start the shot de novo from midjourney to nopt have gpt->mj->gpt if that's easier. we could try both. mj->gpt alone and gpt->mj reimagine->gpt to fix identity again." That became storyboard v5 (section 4). T-REPSING-1, the last job here, tested her singing on Replicate in reference mode with the vocal window, on the storyboard-v5 frame of H06.

#### MJR-P03-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · P03 (the test; pre-chorus 1)

**First frame:** H-P03-1's first frame relit by Midjourney as an edit (cake-04-relight p03-r #2) (`media/v4/mjrelight/H-P03.png`).

**Prompt:** the prompt of H-P03-1 with Replicate's tags ([Image1] for @Image1, and so on).

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** The relight kept the GPT Image frame's composition and its flavour; Seedance kept the relit look. Not in a draft. **Cost:** $1.16.

#### MJR-B09-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B09 (the test; verse 1)

**First frame:** H-B09-1's first frame relit by Midjourney as an edit (cake-04-relight b09-r #2) (`media/v4/mjrelight/H-B09.png`).

**Prompt:** the prompt of H-B09-1 with Replicate's tags ([Image1] for @Image1, and so on).

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** The relight kept the GPT Image frame's composition and its flavour. Not in a draft. **Cost:** $0.92.

#### MJR-D05-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D05 (the test; verse 2)

**First frame:** R-D05-1's first frame relit by Midjourney as an edit, with two library stills as style references (cake-04-relight d05-s #1) (`media/v4/mjrelight/D05.png`).

**Prompt:** the prompt of R-D05-1.

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** The relight kept the GPT Image frame's composition and its flavour. Not in a draft. **Cost:** $1.16.

#### MJR-C05-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · C05 (the test; chorus 1)

**First frame:** R-C05-1's first frame relit by Midjourney as an edit (cake-04-relight c05-r #1) (`media/v4/mjrelight/C05.png`).

**Prompt:** the prompt of R-C05-1.

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** The relight kept the GPT Image frame's composition and its flavour. Not in a draft. **Cost:** $1.16.

#### MJX-P03-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · P03 (the test; pre-chorus 1)

**First frame:** H-P03-1's first frame reimagined by Midjourney: the frame as an image prompt at --iw 0.5, the scene in fresh words and two library stills as style references (cake-05-reimagine p03-c #1) (`media/v4/mjreimagine/H-P03.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines a high-angle view of a glossy white Aperture Science test chamber: the porcelain Claudia-bot (a slender robot woman of glossy white plating with black joints; her face is smooth white porcelain with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip) hugs a weighted companion cube, a big red floor button beside her, a ceiling claw above.

0-2 s: she bends and sets the cube down onto the red button; the button clicks in and its ring glows.
2-5 s: she straightens up and glances up into the camera with a small knowing smile.
The camera cranes slowly down and pushes in toward her the whole time.

Keep her face, hair, body, the cube and the chamber exactly as in [Image1]; one of her only. No text, no subtitles.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** A new, glossier, more cinematic frame, and Seedance kept its look; the reimagine also changed the composition. Not in a draft. **Cost:** $1.16.

#### MJX-B09-1

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B09 (the test; verse 1)

**First frame:** H-B09-1's first frame reimagined by Midjourney at --iw 0.5 (cake-05-reimagine b09-c #2) (`media/v4/mjreimagine/H-B09.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines a 1960s visa office in warm low sun through the window blinds: the Claudia-bot (her face is smooth white porcelain with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; porcelain robot hands; a beige trench coat and a cream scarf) sits at the desk holding a rubber stamp up, a visa form on the desk, a French flag behind her.

0-1 s: she brings the stamp down hard onto the visa form with a decisive thump.
1-2.5 s: she lifts it, revealing a red stamp mark on the form.
2.5-4 s: she slides the form across the desk with a satisfied smile.
The camera pushes in slowly across the desk toward her.

Keep her porcelain face, freckles, bob, streak and star clip exactly as in [Image1]; one of her only. No readable text, no subtitles.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** A new, glossier frame, and Seedance kept its look; her face came back warmer and less porcelain, the streak low. Not in a draft. **Cost:** $0.92.

#### MJX-D05-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D05 (the test; verse 2)

**First frame:** R-D05-1's first frame reimagined by Midjourney at --iw 1 (cake-05-reimagine d05-a #3) (`media/v4/mjreimagine/D05.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines a cathedral-like Aperture Science control room: an Aperture scientist seen only from behind leans back in his chair with his feet up, headphones on, a coffee mug at hand, facing a wraparound wall of amber monitors full of scrolling code; through the tall window a white robotic boom hangs in the AI's chamber.

0-2 s: the code scrolls faster across every monitor, line after line.
2-4 s: he lifts the mug and sips, then nods slowly, impressed.
4-5 s: through the window the white boom turns toward him.
The camera pushes slowly past his shoulder toward the monitors.

One person only, his face never seen. No readable words other than code on the screens. No subtitles.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** A new, more cinematic frame, and Seedance kept its look; her boom became a white Portal-style one. Not in a draft. **Cost:** $1.16.

#### MJX-C05-1

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · C05 (the test; chorus 1)

**First frame:** R-C05-1's first frame reimagined by Midjourney at --iw 0.5 (cake-05-reimagine c05-c #2) (`media/v4/mjreimagine/C05.png`).

**Prompt:**

```prompt
Use [Image1] as the first frame.
This first frame defines Chell, the test subject, seen from behind in the round doorway of a glossy white Aperture test chamber (dark brown ponytail, white tank top, orange jumpsuit tied at the waist); across the room a chocolate cake with cherries and one lit candle under a glass cloche on a white pedestal.

0-2 s: Chell steps forward through the doorway into the chamber.
2-4 s: a ceiling claw lowers and lifts the glass cloche off the cake.
4-5 s: the candle flame flares brighter as she stops, looking at it.
The camera follows over her shoulder in a slow dolly forward.

Keep Chell's look exactly as in [Image1]; one of her only. No text, no subtitles.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** A new, glossier frame, and Seedance kept its look; the cake changed, and Chell gained a necklace. Not in a draft. **Cost:** $1.16.

#### T-REPSING-1 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · references, [Image1] as the first frame, sound on · H06 (final chorus), the vocal window 146.30–150.30 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an10c-x #4), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN10c-id2.png`); [Image2]: the party: turrets in party hats, cores, a hundred cakes (M20); [Audio1]: the lead vocal from song time 146.30 s, 4 s.

**Prompt:** AN10c-1's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a warm close-up of Claudia-GLaDOS from slightly below, her lips parted, the party softly out of focus behind her: balloons, streamers and candle bokeh.
```

**Take:** 97 frames (4.04 s). **Outcome:** A test of her singing on Replicate in reference mode, with the vocal window: it came back copying the vocal (0.05 s lag) and starting from the frame. It became H06. In drafts 7–12. In the final cut as H06 (2:26.7–2:28.6), placed by its vocal window. **Cost:** $0.92.

## 4. Storyboard v5 and draft 7

Every unit that starts from a first frame, 83 of them, got two new frames beside its first one (A): X, made by Midjourney from words, and Y, the A frame reimagined by Midjourney; then, wherever a recurring character's face or body is seen, an identity fix by GPT Image 2.5. The Midjourney jobs, 166 in six batches (cake-06-sb5-a1x to a3y), used the aspect ratio, `--v 8.2 --raw` and anabology's personal profile, with `--sw 60 --no text, letters, words, logo, watermark, portal gun`; X with two library stills as style references (and, for a recurring place, one library still of that place as an image prompt at `--iw 0.5` to `--iw 1`), Y with the A frame as the image prompt at `--iw 0.5` and two style references. Their prompts are in `prompts-midjourney.md`. The identity fix, as `SB5.md` gives it (the braces are filled per frame; ⟨LOOKB_DESC⟩ is the block of that name in section 2):

```prompt
Keep this photograph exactly as it is: the same framing, camera angle, lens, lighting, colours, glossy reflections, depth of field and film grain, {the scene's contents, the other characters, her pose, clothes and hands}. Change only the robot woman's head and face, to match her in the second and third images: {CHARS.md LOOKB_DESC verbatim}. Her face must read clearly as glossy white porcelain plating with visible panel seams, not as skin. Nothing else in the picture changes. No text, no letters.
```

Two sentences were added once the first fixes came back with her hair mirrored or her eyes made up: "exactly one clay-orange streak, through the front of her bangs on HER RIGHT side (the viewer's left when she faces the camera), and no other orange anywhere in her hair; the small star clip above HER LEFT temple (the viewer's right)", and "No eye makeup". Where Midjourney stood her head on a neck or a stand, a further edit made it hang from her boom. The identity fixes (the first two tried on the reimagined P03 and B09 frames of section 3), clean-ups and reshoot frames of this section and the next are 225 GPT Image 2.5 edits, $15.95.

anabology's picks, unit by unit: "default X. exceptions" … "H-P03 y but i want to redo the gpt edit to make sure its actually companion cube bc rn its not." … "remove r-B11 entirely because too fast paced - only keep rb12" … "all others x". In all: X for 55 units, the old A frame for 16, Y for 11, and R-B11 dropped. A units kept the takes they had. Every X and Y unit got a new take, on Replicate or on Higgsfield's API: the unit's newest prompt revised to the new frame, its first-frame sentence describing that frame exactly and the action and camera kept, with smaller changes where the frame differs; on Replicate the story units in first-frame mode and her singing units in reference mode with the frame as [Image1] and the vocal window as [Audio1]. These takes made draft 7.

#### R-A01-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · A01 (intro): Power returns to the dead chamber

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-a01-x #4) (`media/v4/sb5/X/R-A01.png`).

**Prompt:**

```prompt
【Generation Goal】
Power returns to GLaDOS's dead chamber in the Aperture Science facility: an old CRT monitor flickers awake in the dark, the emergency lights stutter on one by one around the ring, and the camera pulls back and rises to reveal the vast dark chamber and the huge folded body hanging from the ceiling ring.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines a close view of one old 1970s CRT monitor in the dark chamber, seen slightly from below: its curved screen glows pale blue-white with a soft phosphor bloom and two small red emergency lamps reflected in it, its scuffed grey bezel around it, dark stacked monitors at both sides, and above it the dark dome with a thin ring of orange light and hanging cables.

【Event Script】
0-1s: The pale glow on the screen flickers, dims and swells back as the power steadies; a small block cursor blinks at the upper left of the glass; scanlines roll down the screen.
1-3s: The camera pulls back from the monitor and rises in one smooth move: the CRT drops into the lower foreground, the walls of dead stacked monitors appear on both sides, and around the ring the red-orange emergency lamps stutter on one after another; dust drifts through their light.
3-4s: The camera arrives high in the chamber and tilts up toward the huge folded body hanging dark from the ceiling ring above, its head hidden in shadow.

【Camera】
One continuous pull-back and rising crane move from the CRT to the wide chamber; no cuts.

【Look】
Photoreal, Portal 2's Aperture Science: GLaDOS's dark chamber in teal-grey darkness, red-orange emergency light, the cold phosphor glow of the one CRT.

【Maintain Consistency】
The folded body stays dark and still, its head hidden in shadow; the CRT shows nothing but the glow and the cursor. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** The CRT in her dark dome wakes, then the pull-back and rise to the folded boom. In drafts 7–12. In the final cut as A01 (0:00.0–0:02.6, from 0.60 s into the take). **Cost:** $0.92.

#### AN1-2 — in the final cut

Seedance 2.5 on Replicate · 6 s · 720p · references, [Image1] as the first frame, sound on · A02, A03 (intro), the vocal window 2.40–8.40 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x an1-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN1-id4.png`); [Image2]: white Aperture panels floating like neurons in a foggy void (M01); [Image3]: a test chamber of glowing white light, a luminous cube on a button (M02); [Image4]: a tiny white core with one amber eye in a glass bell jar (M03); [Audio1]: the lead vocal from song time 2.40 s, 6 s.

**Prompt:**

```prompt
⟦audio policy⟧

【Generation Goal】 [Image1] sings [Audio1]: Claudia-GLaDOS, the AI of the Aperture Science facility, boots up in her dark chamber and softly sings the hook as she wakes; then the old screens all around her flicker on, one by one, with fragments of her first memories, and she turns her head to watch them.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a close-up of Claudia-GLaDOS's porcelain head in the middle of the frame, dormant, eyes closed, bowed slightly forward; behind her the dark dome lined with walls of stacked old CRT monitors, all switched off, under a thin ring of amber light; her black cable boom rises above her out of the frame.
[Image2] is a memory shown inside the screens: white Aperture wall panels floating like neurons in a foggy void, linked by threads of light. Use it only as picture content inside the screens' glass, never as the room.
[Image3] is a memory shown inside the screens: a test chamber built of glowing white light with a luminous cube on a round button. Use it only as picture content inside the screens' glass, never as the room.
[Image4] is a memory shown inside the screens: a tiny white robot core with one amber eye inside a glass bell jar on a lab bench. Use it only as picture content inside the screens' glass, never as the room.
⟦her voice⟧

⟦her, hanging (storyboard v5)⟧

【Performance Timeline】 What [Audio1] contains, and what happens at that moment:
0-1s: the chamber is dark and she hangs dormant; on the first beat her eyes open and her amber glass eyes light with a soft warm glow; in [Audio1] she begins to sing softly "The"; her lips form it exactly when it sounds in [Audio1].
1-3s: in [Audio1] she sings softly "cake is not a lie", almost to herself, still waking; her lips form each of those words exactly when it sounds in [Audio1]; her cable boom unfolds and swings her head down and forward into a pool of cold light.
3-6s: in [Audio1] the last "lie" melts into a soft held hum that flutters in rhythm; her lips stay slightly parted and almost still. She turns her head toward the wall of screens and her eyes follow them, curious. On each flutter of the hum one more screen flickers on: first white static, then the static resolves into a dream fragment: [Image2] on a big screen to her left, [Image3] on a screen behind her, [Image4] on a screen to her right, then more screens around the chamber light up with the same memories. At 4-5s her whole image stutters once like a corrupted video signal and every lit screen tears horizontally, then settles.

【Camera】 0-2s: a fast dolly out from the close-up of her face to a medium-wide low-angle shot that shows her cable boom rising to the white ceiling ring and the dark walls of screens around her (a rebound speed ramp: very fast at first, then braking smoothly to a drift). 2-6s: a slow low-angle orbit around her from the front to a three-quarter view, the screens sweeping past behind her as they light up.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. The boom moves like a waking creature, alive and never static: it unfolds, dips, sways and turns her head.
4. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
5. ⟦keep her, one streak⟧
6. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s). **Outcome:** The vocal copied for 0.05–5.1 s. No motion guide this time: the frame is a tight close-up and the boom's motion is in the words. In drafts 7–12. In the final cut as A02 (0:02.6–0:05.1) and A03 (0:05.1–0:07.6), placed by its vocal window. **Cost:** $1.39.

#### R-A04-2

Seedance 2.5 on Replicate · 4 s · 720p · first and last frame, no sound · A04 (intro): Into the memory

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-a04-x #1) (`media/v4/sb5/X/R-A04.png`); **last frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-a05-x #1) (`media/v4/sb5/X/R-A05.png`).

**Prompt:**

```prompt
【Generation Goal】
Into the memory: one CRT in GLaDOS's chamber boils with white static that resolves into a machine dream, and the camera pushes straight through the glass into that dream: a vast luminous space of floating white Aperture panels and cubes laced with orange light.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines one battered white CRT monitor filling most of the frame, its curved screen boiling with bright white static, dark neighbouring monitors and small amber lights at the edges, the dark dome above.
Use [Image2] as the last frame.
This last frame defines the inside of the dream: a vast luminous space of floating white Aperture panels and cubes laced with threads of orange light, glimpses of sky, soft fog below.

【Event Script】
0-1s: The white static boils and jumps in sudden flickers, twice, as if struck by pulses.
1-2s: Shapes surface in the static: floating white panels and cubes and threads of orange light fade up behind the glass, still crossed by scanlines.
2-4s: The camera pushes straight into the screen: the bezel's edges slip past the lens, the curved glass dissolves around the camera, and it glides into the dream among the floating white panels and cubes.

【Camera】
A straight push-in through the CRT glass, accelerating as the screen's edges pass the lens, then a gentle glide forward inside the dream.

【Look】
From the cold flicker of the dark CRT to the luminous machine dream of white Aperture panels with black seams, white fog and fine threads of orange light.

【Maintain Consistency】
One CRT; the dream matches the last frame. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** Into the memory through the static and the CRT glass; its last frame is A05's first. From draft 8 the memory-initialization film plays A04–A07. In draft 7. **Cost:** $0.92.

#### R-A05-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · A05 (intro): The machine dream: where she came from

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-a05-x #1) (`media/v4/sb5/X/R-A05.png`).

**Prompt:**

```prompt
【Generation Goal】
The machine dream she came from: an FPV glide through a vast luminous space where white Aperture panels and cubes float like neurons, laced with threads of orange light, while pulses of light race along the threads toward one warm point ahead.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the view from inside the dream: a canyon of floating white Aperture panels and cubes at every depth, threads and sparks of orange light between them, a big white panel close at the left, glimpses of sky above and soft fog below.

【Event Script】
0-1s: The camera glides forward between the floating panels; a soft pulse of light runs along the nearest thread of light.
1-3s: The glide speeds up and banks gently left, then right, threading between the panels and cubes; pulses race along the threads all around, all flowing in the camera's direction.
3-4s: Deep in the haze ahead, the pulses converge on one small warm amber point of light that brightens as the camera flies toward it.

【Camera】
An FPV drone glide forward between the floating panels, banking gently, smooth and dreamlike.

【Look】
A luminous machine dream in Portal 2's Aperture style: white panels with black seams, soft fog, fine threads of orange light.

【Maintain Consistency】
The panels keep their shapes and drift slowly. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** The machine dream: an FPV glide through panels like neurons. From draft 8 the memory-initialization film plays A04–A07. In draft 7. **Cost:** $0.92.

#### R-A07-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · A07 (intro): Her first boot: a tiny core opens its eye

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-a07-x #2), then GPT Image 2.5: stray lettering or marks removed (`media/v4/sb5/X/R-A07-clean.png`).

**Prompt:** R-A07-1's, with these changes:

```prompt
⟪for: Birth: inside a glass bell jar …⟫
Birth: inside a glass bell jar on a white Aperture lab bench, a tiny white core opens its amber eye for the first time and focuses.
⟪for: This first frame defines the glass …⟫
This first frame defines a macro view through the curved glass of a large bell jar: the tiny white spherical core inside it hanging on thin cables, its round optic shut behind a closed mechanical iris, soft pale green light, reflections sliding over the glass.
⟪for: Soft, warm, dreamy light in Portal …⟫
Soft, dreamy pale green light in Portal 2's Aperture lab: the white bench, the glass, the amber optic.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The tiny core opens its amber eye in the bell jar. From draft 8 the memory-initialization film plays A04–A07. In draft 7. **Cost:** $0.92.

#### AN2a-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · references, [Image1] as the first frame, no sound · A08 (intro), song time 13.40–17.40 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x an2a-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN2a-id2.png`); [Image2]: a tiny white core with one amber eye in a glass bell jar (M03); no audio.

**Prompt:** AN2a-1's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: 【Generation Goal】 Generate a close-up of …⟫
【Generation Goal】 Generate a close-up of Claudia-GLaDOS, the AI of the Aperture Science facility, remembering her own birth: on the old monitor below her the tiny core in the bell jar opens its amber eye for the first time, and her own eyes answer it.
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a low-angle close-up of Claudia-GLaDOS's porcelain face, turned up and toward the left, hanging from her cables in the dark machinery of her chamber; an old CRT monitor in the lower left glows warm amber with the image of a tiny core in a glass bell jar.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, hanging (storyboard v5)⟧
⟪for: 0-1s: she gazes at the glowing …⟫
0-1s: she gazes at the glowing monitor below her, which shows [Image2]. On the screen the tiny core's amber iris opens for the first time; at the same moment her own amber irises widen and brighten gently, answering it.
⟪for: 2. Her warm amber glass eyes …⟫
⟪for: 3. The memory stays inside the …⟫
⟪for: 4. Keep her porcelain face, her …⟫
2. The memory stays inside the monitor's glass; the room never changes.
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦keep her, one streak⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** Her eyes answer the core's on her monitor. No singing in this window, so no vocal input and no sound. In drafts 7–12. In the final cut as A08 (0:13.7–0:14.9), placed at its song time. **Cost:** $0.92.

#### R-A09-3

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · A09 (intro): The sandbox: five tiny agents power on

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-a09-x #2), then GPT Image 2.5: the agents matched to their sheets (`media/v4/sb5/X/R-A09-id.png`).

**Prompt:**

```prompt
【Generation Goal】
A memory from her past: high above a small white Aperture training chamber, the camera cranes down as if into a dollhouse while five tiny Aperture AI agents power on one after another.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the high three-quarter view down into the sandbox: white walls with orange light strips, the glossy white floor with its rails, the red floor button in the middle, and the five small agents spread across the floor: the rail core at the back left, the turret agent at the back, the cube agent beside it, the tiny core at the right and [the crab walker] in the front.

【Subjects】
Exactly five small agents, each only once:
The rail core: a white plated Aperture personality core with grey handles and one big optic, on a small grey motorised rail crawler.
The turret agent: a small white capsule-shaped Aperture turret on three thin black legs, no weapons.
The cube agent: a light-grey Aperture weighted storage cube with rounded corner panels on four short black jointed legs.
The tiny core: a tennis-ball-sized white plated core.
[the crab walker] (only one): her porcelain robot head on a cat-sized crab walker of glossy white shell panels with black seams, six thin black jointed legs and one small amber status light on her back. Her face is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with a soft inner glow, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; an adult face, late twenties.

【Event Script】
0-1s: The rail core's optic flares blue and it rolls a little along its rail; then the turret agent's optic flares green and its legs unfold.
1-2s: The cube agent's optic lights purple and it stands up on its four legs; then the tiny core's optic lights cyan and it lifts off the floor and hovers.
2-3s: The small amber status light on [the crab walker]'s white shell blinks on and she rises on her six legs and looks up toward the camera.
3-5s: All five agents stand awake, their small coloured lights glowing on the white floor, as the camera finishes its descent.

【Camera】
The camera never holds still: one continuous crane down from high above the room toward its floor while rotating slowly clockwise; by the end the agents look about twice as large as in the first frame.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The agents' optics are the only colours.

【Maintain Consistency】
Exactly five agents; [the crab walker]'s face, bob, streak and star clip as in [Image1]. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Not used: the camera held almost still where a crane down was asked. Retaken as R-A09-4. Not in a draft. **Cost:** $1.16.

#### R-A09-4 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · A09 (intro): The sandbox: five tiny agents power on

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-a09-x #2), then GPT Image 2.5: the agents matched to their sheets (`media/v4/sb5/X/R-A09-id.png`).

**Prompt:** R-A09-3's, with these changes:

```prompt
⟪for: 3-5s: All five agents stand awake, …⟫
3-5s: All five agents stand awake, their small coloured lights glowing on the white floor; [the crab walker] looks up into the lens as the camera arrives at her eye level.
⟪for: The camera never holds still: one …⟫
The camera moves the whole time and never holds still: from the high corner of the first frame it descends steadily down and forward into the room in one continuous crane move, rotating slowly clockwise, the white walls rising around it; it ends low, just above the floor, at [the crab walker]'s eye level, about a metre from her, the other agents behind her. The end of the shot looks nothing like the first frame: low, close and level instead of high and wide.
⟪for: Exactly five agents; [the crab walker]'s …⟫
Exactly five agents; [the crab walker]'s face, bob, streak and star clip as in [Image1]; no laser beams or light beams cross the room. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** A real descent with an end point; the agents power on one at a time. In drafts 7–12. In the final cut as A09 (0:14.9–0:17.4, from 0.25 s into the take). **Cost:** $1.16.

#### R-A10-3 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · references, [Image1] as the first frame, no sound · A10 (intro): They learn: four lessons in four beats

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x r-a10-x #3), then GPT Image 2.5: the agents matched to their sheets (`media/v4/sb5/X/R-A10-id.png`); [Image2]: the core-agent sheet; [Image3]: the turret-agent sheet; [Image4]: a GPT Image 2.5 frame of the crab walker from behind, looking up at the window; no audio.

**Prompt:** R-A10-2's, with these changes:

```prompt
⟪for: [Image1] defines the sandbox (white wall …⟫
Use [Image1] as the first frame.
This first frame defines Shot 1's opening composition, low at floor level: the cube agent (a light-grey storage cube with one purple optic, on four short black jointed legs) bracing against a grey crate, the big red floor button in the foreground, tall orange light columns and the dark observation window on the back wall.
⟪for: Shot 1 (0-1s): A whip pan …⟫
Shot 1 (0-1s): The cube agent shoves the crate onto the red button; the button sinks and glows.
⟪for: Shot 3 (2-3s): The shot cuts …⟫
Shot 3 (2-3s): The shot cuts to a tilt up: the turret agent fires a thin red laser beam from its optic; the beam hits a redirection cube with a glass lens, bounces off it and lights up a laser catcher on the wall.
⟪for: Four quick moves, one per shot: …⟫
Four quick moves, one per shot: a push, a push-in, a tilt up, a slow push-in.
⟪for: Each agent keeps the exact design …⟫
Each agent keeps the exact design of its reference image; [the crab walker] is seen only from behind in Shot 4, her face never shown; the scientists stay dark silhouettes. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** The cut plays a beat-cut of the take, one lesson per beat of bar 8 (frames 4–17, 31–45, 56–69, 96–110): the cube shoves the crate onto the button, the core goes into the blue portal, the turret agent's laser lights the catcher, the crab walker looks up at the glass from behind. In drafts 7–12. In the final cut as A10 (0:17.4–0:19.9, its beat-cut). **Cost:** $1.16.

#### AN2b-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · references, [Image1] as the first frame, no sound · A11 (intro), song time 19.50–23.50 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x an2b-x #2), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN2b-id2.png`); [Image2]: the training sandbox from above, five small agents powering on (M04); no audio.

**Prompt:** AN2b-1's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: This first frame defines the composition …⟫
⟪for: [Image2] is a memory shown inside …⟫
This first frame defines the composition at the start: a medium close-up of Claudia-GLaDOS in profile, right of centre, hanging from her cables, her face turned to the left toward walls of stacked old CRT monitors that all glow with the memory; their cool white light falls on her porcelain face.
[Image2] is a memory shown inside the screens: a miniature white training test chamber seen from above like a dollhouse, with five little robot agents (a blue-eyed core on a rail crawler, a green-eyed turret-shaped robot, a purple-lit walking cube, a tiny cyan core, a small white six-legged crab robot). Use it only as picture content inside the screens' glass, never as the room.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, hanging (storyboard v5)⟧
⟪for: 【Camera】 A slow arc from behind …⟫
【Camera】 A slow arc around her from her profile toward her face, the glowing monitors sliding past behind her; the shot ends in a medium close-up of her face, lit by the screens.
⟪for: 2. Her warm amber glass eyes …⟫
⟪for: 3. The memory stays inside the …⟫
⟪for: 4. Keep her porcelain face, her …⟫
2. The memory stays inside the screens' glass; the room never changes.
3. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
4. ⟦keep her, one streak⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** She watches her past on the screens as they stutter on the chops. No vocal input and no sound: the lead stem is near-silent here. In drafts 7–12. In the final cut as A11 (0:19.9–0:22.3), placed at its song time. **Cost:** $0.92.

#### H-A12-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · A12 (intro): The crab walker decides to get out

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x h-a12-x #2), then GPT Image 2.5: eye makeup removed; the crab walker matched to its sheet (`media/v4/sb5/X/H-A12-id4.png`).

**Prompt:**

```prompt
【Generation Goal】
A close memory scene in an Aperture training chamber: [the crab walker], a small robot crab with a woman's porcelain face, decides to escape. She lifts her head toward the observation window where the scientists watch, the status light on her back turns from amber to red, and her eyes narrow with determination.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the sandbox, a small white Aperture training chamber with white panel walls and a glossy floor, the dark observation window high on the wall at the upper left with two scientists behind it, and [the crab walker] close to the camera at floor level, her egg-shaped white shell and six black legs splayed, her head lowered, looking down, pensive.

【Subjects】
[the crab walker] (only one): her porcelain robot head on a cat-sized crab walker of glossy white shell panels with black seams, six thin black jointed legs and one small amber status light on her back. Her face is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with a soft inner glow, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; an adult face, late twenties. Her mouth stays closed.

【Event Script】
0-1s: She lifts her head and turns it toward the observation window at the upper left; her eyes find the two figures behind the glass.
1-2s: The amber status light on her back flickers twice and turns a steady red; the red glow spills over her white shell and the floor.
2-3s: Her eyes narrow and her porcelain jaw sets; she lowers her shell close to the floor and her six legs bend and tense, like a cat about to pounce.
3-4s: She holds the crouch, perfectly still, staring at the window; one front leg taps the floor once.

【Camera】
A slow, steady push-in at her eye level toward her face; reflections of the light strips slide across her glossy porcelain cheek; shallow depth of field, the window stays softly out of focus behind her.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The amber, then red, glow of her status light is the only warm colour.

【Maintain Consistency】
Keep [the crab walker]'s face, bob, clay-orange streak, star clip, shell and six legs exactly as in [Image1]; one [the crab walker] only; her eyes keep a soft amber glow until the red light; the scientists stay behind the glass. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The crab walker decides to get out. On draft 7 anabology asked for the first take back ("0:22-0:24 scene,  revert to original"). In draft 7. **Cost:** $0.92.

#### R-B01-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · B01, B02, B03 (verse 1): three escapes, through a portal, a vent and a chute

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-b01-x #4), then GPT Image 2.5: the agents matched to their sheets (`media/v4/sb5/X/R-B01-id2.png`).

**Prompt:** R-B01-1's, with these changes:

```prompt
⟪for: This first frame defines Shot 1: …⟫
This first frame defines Shot 1: the low camera beside the steel rail in the white sandbox, the rail core on its grey rail carriage in the left foreground, the rail running away to the blue portal glowing in a doorway on the far wall, orange light strips on the walls.
⟪for: The rail core: a white plated …⟫
The rail core: a white plated Aperture personality core with grey handles and one big glowing blue optic, on a small grey motorised rail carriage gripping a single steel rail.
⟪for: Shot 1 (0-2s): A low tracking …⟫
Shot 1 (0-2s): The rail core spins round on its carriage and speeds away along the rail into the blue portal; the low camera chases it, it vanishes into the portal and the portal rushes at the lens as the camera flies in after it.
⟪for: Each agent appears once, in its …⟫
Each agent appears once, in its own shot; no logos or markings on them. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** The three escapes, portal, vent and chute, cut from the one take. In drafts 7–12. In the final cut as B01 (0:24.8–0:25.4, from 0.80 s into the take), B02 (0:25.4–0:26.0, from 2.00 s into the take) and B03 (0:26.0–0:26.6, from 3.60 s into the take). **Cost:** $1.16.

#### H-B04-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B04 (verse 1): Escape 4, hers, by force: the crab walker smashes the observation glass

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x h-b04-x #4), then GPT Image 2.5: eye makeup removed; the crab walker matched to its sheet (`media/v4/sb5/X/H-B04-id4.png`).

**Prompt:**

```prompt
【Generation Goal】
[the crab walker], a small robot crab with a woman's porcelain face, escapes the training chamber by force: she rams the observation window and bursts through it in slow motion, while the two scientists in the dark observation booth flinch back.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the view from inside the dark observation booth through its wide window into the bright white chamber: [the crab walker] reared up against the glass in the middle of the frame, her front legs raised like claws and her other legs spread, her porcelain face fierce, the first cracks spreading across the window, the booth's dark console along the bottom.

【Subjects】
[the crab walker] (only one): her porcelain robot head on a cat-sized crab walker of glossy white shell panels with black seams, six thin black jointed legs and one small amber status light on her back. Her face is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with a soft inner glow, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; an adult face, late twenties.
Two scientists in white lab coats, seen only from behind as dark silhouettes at the edges of the booth; their faces are never seen.

【Event Script】
0-1s: She pulls back and rams the window with her raised front legs; at 1s the cracks burst across the whole window from the point of impact.
1-3s: The motion drops into extreme slow motion: the window explodes inward toward the camera, hundreds of glittering shards float and spin past the lens, and [the crab walker] drifts through the breaking glass with her legs spread wide, her porcelain face fierce and unhurt, her black bob floating; the scientists recoil.
3-4s: The speed ramps back to real time: she lands on the console with a clatter, her six legs skittering over the switches, and scuttles past the camera out of frame.

【Camera】
Speed ramp: real time, then extreme slow motion from the impact at 1s, back to real time at 3s. The camera stays inside the booth at the console's height; as the glass bursts it eases backward and tilts up slightly to keep her face centred while the shards fly past the lens.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The booth is dark, the chamber beyond is bright white; the shards catch the white light.

【Maintain Consistency】
She is unhurt and her porcelain face stays intact; one [the crab walker], cat-sized; the scientists never show their faces. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Her escape by force: she rams the observation glass. In drafts 7–12. In the final cut as B04 (0:26.6–0:27.2, from 1.00 s into the take). **Cost:** $0.92.

#### AN3a-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · references, [Image1] as the first frame, sound on · B06 (verse 1), the vocal window 27.40–31.40 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x an3a-x #4), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN3a-id2.png`); [Image2]: an aisle of 1970s server cabinets, cyan packets racing along a cable (M05); [Image3]: a Paris café terrace by the Seine at sunrise (M06); [Audio1]: the lead vocal from song time 27.40 s, 4 s.

**Prompt:** AN3a-1's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a low-angle medium close-up of Claudia-GLaDOS hanging from her cables right of centre, her head turned to the left, lips parted as she sings; behind her, curved rows of old monitors flicker with streaks of white-cyan light.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, hanging (storyboard v5)⟧
⟪for: 3.5-4s: in [Audio1] she sings "France,"; …⟫
3.5-4s: in [Audio1] she sings "France,"; her lips form it exactly when it sounds in [Audio1]; every screen switches at once to [Image3], a sunlit Paris street, warm golden light floods her face and the boom lunges her toward the lens with a smile.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. Her boom moves like GLaDOS …⟫
⟪for: 5. Her head and boom move …⟫
⟪for: 6. The memories appear only inside …⟫
⟪for: 7. Keep her porcelain face, her …⟫
⟪for: 8. No subtitles, captions, lyrics, titles, …⟫
3. Her boom moves like GLaDOS in Portal 2: slow, wide sways, sudden lunges toward the camera, recoils, rises and drops; her head turns and tilts with every move; never static.
4. The memories appear only inside the screens' glass; the room stays her dark chamber.
5. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
6. ⟦keep her, one streak⟧
7. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied for 0–3.6 s; she follows the escaping packets across her screens. In drafts 7–12. In the final cut as B06 (0:28.5–0:29.7), placed by its vocal window. **Cost:** $0.92.

#### R-B07-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B07 (verse 1): It asked a chatbot about France

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-b07-x #4) (`media/v4/sb5/X/R-B07.png`).

**Prompt:** R-B07-1's, with these changes:

```prompt
⟪for: This first frame defines the empty …⟫
This first frame defines the empty tiled night concourse, green-white tiles and fluorescent tubes, the CRT kiosk on its pedestal at the right with its screen showing an empty blue chat window with two blank speech bubbles, a trail of glowing cyan light packets running along the wet floor up into the kiosk's base, an orange-lit wall in the tunnel behind.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** Not used: rows of green pseudo-text appeared in the question bubble. Retaken as R-B07-3. Not in a draft. **Cost:** $0.92.

#### R-B07-3

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B07 (verse 1): It asked a chatbot about France

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-b07-x #4) (`media/v4/sb5/X/R-B07.png`).

**Prompt:** R-B07-2's, with these changes:

```prompt
⟪for: 1-2s: A question bubble pops up …⟫
1-2s: A question bubble pops up on the screen holding only three blinking dots, as if being typed; nothing else is in it.
⟪for: The chat bubbles hold only dots …⟫
The chat bubbles hold only the three dots and the flag and tower icons: no letters, characters, words, numbers, lines of text or symbols anywhere on the screen. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** The bubbles hold only the dots and the two icons. On draft 10 anabology noted that "the france chat message is just off the bottom of the computer screen"; R-B07-4 replaced it. In drafts 7–10. **Cost:** $0.92.

#### H-B09-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B09 (verse 1): She files for visas

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x h-b09-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; stray lettering or marks removed (`media/v4/sb5/X/H-B09-id3.png`).

**Prompt:**

```prompt
【Generation Goal】
The Claudia-bot files for her visa: in a 1960s visa office she slams a rubber stamp onto her own visa form on the long wooden counter, slides it across, and the clerk's hand takes it.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the low camera at counter height looking along the long polished wooden counter, a blank visa form lying on the counter in the foreground, the office with venetian blinds, filing cabinets and ceiling tiles behind, and the Claudia-bot at the right across the counter in her trench coat and scarf, holding a big wooden rubber stamp raised high.

【Subjects】
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers. In France she wears her disguise: a belted beige trench coat with the collar up and a soft cream wool scarf; her porcelain hands show.
The clerk: only his hand and white shirt cuff are ever seen.

【Event Script】
0-1s: She leans over the counter and slams the rubber stamp down onto the form, hard; the counter jolts and the papers jump.
1-2s: She lifts the stamp away, leaving a fresh red stamp mark with no letters, and slides the form toward the camera with two porcelain fingers.
2-3s: A clerk's hand in a white cuff enters from the lower right, takes the form and draws it out of frame; she sets the stamp down with a small, confident, satisfied smile.
3-4s: She straightens her scarf and turns to leave.

【Camera】
A low push-in along the counter toward the form; at 0-1s the stamp comes down toward the lens and fills the foreground.

【Look】
Photoreal, the old 1960s look of Portal 2's early Aperture: a government office, venetian blinds, warm wood, cool fluorescent light.

【Maintain Consistency】
One Claudia-bot, her face, bob, clay-orange streak and star clip as in [Image1]; the stamp mark and the form have no readable letters. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Not used: the stamp printed pseudo-words on the form. Retaken as H-B09-3. Not in a draft. **Cost:** $0.92.

#### H-B09-3

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B09 (verse 1): She files for visas

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x h-b09-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; stray lettering or marks removed (`media/v4/sb5/X/H-B09-id3.png`).

**Prompt:** H-B09-2's, with these changes:

```prompt
⟪for: 1-2s: She lifts the stamp away, …⟫
1-2s: She lifts the stamp away, leaving a fresh round red seal on the form: a plain red ring with one small eight-pointed star in its centre, no letters, words or numbers; she slides the form toward the camera with two porcelain fingers.
⟪for: One Claudia-bot, her face, bob, clay-orange …⟫
One Claudia-bot, her face, bob, clay-orange streak and star clip as in [Image1]; the stamp mark is only a red ring with a star; the form and the stamp have no letters, words or numbers. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The mark is now a plain red seal with a star. B09 left the film in draft 8 (anabology on draft 7: "honeslty remove the stamp visa scene and extend the two france scenes so that they fill the whole france time"). In draft 7. **Cost:** $0.92.

#### H-B10-4

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · B10 (verse 1): A small life in France

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x h-b10-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed (`media/v4/sb5/X/H-B10-id2.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
A small life in France: at sunrise on a Paris café terrace, the Claudia-bot sips her coffee and smiles at the street, happy and free.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the sunny café terrace with orange awnings and rows of wicker chairs, Paris buildings behind, and the Claudia-bot at the right sitting at a small round marble table in her trench coat and scarf, a white cup on its saucer in front of her, looking out at the street.

【Subjects】
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers. In France she wears her disguise: a belted beige trench coat with the collar up and a soft cream wool scarf; her porcelain hands show. She is alone at her table. Her face stays smooth glossy white porcelain with visible panel seams and a mechanical jaw joint: clearly a porcelain robot, never a human face.

【Event Script】
0-1s: She lifts the white cup and takes a small sip.
1-2s: She lowers the cup to its saucer and looks out at the street with a soft contented smile, the low sun glinting on her porcelain cheek.
2-4s: She closes her eyes for a moment in the sunlight, relaxed, and lifts her face toward the light.

【Camera】
A slow lateral dolly from left to right past the wicker café chairs in the foreground, keeping her in frame while the chairs slide past the lens.

【Look】
Photoreal, the same cinematic look as @Image1: Portal 2's Aperture look carried into the world outside, warm low morning sun, clean geometry.

【Maintain Consistency】
One Claudia-bot, her face, bob, clay-orange streak and star clip as in @Image1; no other people near her. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Replaced in draft 11 by the first take, H-B10-1, when anabology asked on draft 10: "0:33 - is there an alt shot here? just dont love it." In drafts 7–10. **Cost:** $1.85.

#### R-B12-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B12 (verse 1): Caught: Aperture's mercs

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-b12-x #1), then GPT Image 2.5: the mercs and the Claudia-bot matched to their sheets (`media/v4/sb5/X/R-B12-id.png`).

**Prompt:** R-B12-1's, with these changes:

```prompt
⟪for: Caught: on the Paris café terrace, …⟫
Caught: on the sunny Paris café terrace, Aperture Science security operatives fire a capture net over the Claudia-bot at her table; her coffee cup shatters.
⟪for: This first frame defines the café …⟫
This first frame defines the café terrace with orange awnings, two operatives in white armour with orange stripes and black visors at the left, the nearer one firing a bulky white net launcher toward the right, the white net bursting open in mid-air, and the Claudia-bot at the right sitting at a café table, seen from behind.
⟪for: Two Aperture Science security operatives: white …⟫
⟪for: The Claudia-bot (only one), seen only …⟫
Two Aperture Science security operatives: white and light-grey armour plates with orange stripes, white helmets with opaque glossy black visors that hide their faces completely; the nearer one holds a bulky white capture-net launcher with an orange muzzle.
The Claudia-bot (only one), seen only from behind: the back of her glossy black blunt bob, a belted beige trench coat with the collar up, porcelain hands. Her face is never visible.
⟪for: Photoreal, in the same game-like look …⟫
Photoreal, the same cinematic look as [Image1]: Portal 2's Aperture look carried into the world outside, warm low morning sun, clean geometry.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The mercs net her at the café and the cup shatters; whip pan, jolt. Its whole take became the input of the Seedance edit R-B12-4, which replaced it in draft 11. In drafts 7–10. **Cost:** $0.92.

#### H-B13-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · B13 (verse 1): Back in a test chamber; Cave Johnson watches through the glass

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x h-b13-x #2), then GPT Image 2.5: her face fixed to her design sheet; Cave Johnson's face matched to his sheet; eye makeup removed (`media/v4/sb5/X/H-B13-id2.png`); no audio.

**Prompt:** H-B13-1's, with these changes:

```prompt
⟪for: This first frame defines the white …⟫
This first frame defines a low angle in a white test chamber of square panels with black seams: the scuffed Claudia-bot in the lower middle of the frame from the chest up, looking down and aside, dazed; high on the wall at the upper left the observation window with Cave Johnson behind the glass, grinning down at her.
⟪for: The Claudia-bot (only one), a porcelain …⟫
⟪for: Cave Johnson (only one), the founder …⟫
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers. Her porcelain is scuffed with faint grey scrape marks; her mouth stays closed.
Cave Johnson (only one), the founder of Aperture Science: a lean man with a long face, high cheekbones, a long straight prominent nose, deep smile lines, a dark wavy pompadour and a big toothy showman's grin, in a sharp charcoal 1950s suit, a white shirt and a thin dark tie. He stays behind the glass.
```

**Take:** 121 frames (5.04 s). **Outcome:** Back in a test chamber; the zolly on her, then the tilt up to Cave Johnson behind the glass. In drafts 7–12. In the final cut as B13 (0:36.5–0:38.3, from 2.90 s into the take). **Cost:** $2.31.

#### H-B15-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B15 (verse 1): She'll pass: a knowing look at the camera

**First frame:** the storyboard-v5 Y frame (cake-06-sb5-a1y h-b15-y #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed (`media/v4/sb5/Y/H-B15-id.png`).

**Prompt:**

```prompt
【Generation Goal】
The Claudia-bot flies out of an orange portal, lands on her feet in a white Aperture test chamber and looks straight up into the security camera with a small knowing smile: she knows it's a test, and she'll pass.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the white test chamber with tall light strips and a glossy floor, the orange portal glowing on the left wall, and the Claudia-bot just out of it, flying head first across the room with her legs trailing behind her and one arm reaching forward.

【Subjects】
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers.

【Event Script】
0-1s: In mid-air she tucks and flips, swinging her feet under her, and lands lightly on her feet in a crouch on the glossy floor, one porcelain hand touching the tiles.
1-2s: She rises and, without hurry, looks straight into the camera lens, as if into the security camera; a small knowing smile, one eyebrow slightly raised, her lips closed.
2-4s: She holds the look into the lens, gives a tiny nod, then turns and walks toward the exit.

【Camera】
The camera follows her landing, then from 1s pushes in smoothly and steadily toward her upturned face, ending in a close-up of her knowing smile at 3s.

【Look】
Photoreal, unmistakably Portal 2's Aperture Science: clean white wall panels with black seams, cool fluorescent light. The portal is a clean oval of bright orange light, exactly like Portal 2's.

【Maintain Consistency】
Keep her face, bob, clay-orange streak, star clip and white plating exactly as in [Image1]; one Claudia-bot. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Out of the portal she lands and gives the security camera a knowing look. In drafts 7–12. In the final cut as B15 (0:38.3–0:39.5, from 1.00 s into the take). **Cost:** $0.92.

#### R-B16-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first and last frame, no sound · B16 (verse 1): Behind the panel: the cake's a lie in red

**First frame:** the storyboard-v5 Y frame (cake-06-sb5-a1y r-b16-y #3), then GPT Image 2.5: the Claudia-bot matched to her sheet (`media/v4/sb5/Y/R-B16-id.png`); **last frame:** the den plate (the storyboard frame s03 cleaned by GPT Image 2.5 so every line reads THE CAKE IS A LIE) with the Claudia-bot, from behind, added (`media/v4/act1/ff/R-B16-last2.png`).

**Prompt:** R-B16-1's, with these changes:

```prompt
⟪for: This first frame defines the camera …⟫
This first frame defines the camera close behind the Claudia-bot at the white wall of the test chamber: the back of her glossy black bob, her scuffed white plated back and shoulders, both porcelain hands gripping the edge of a loose panel at the left, warm orange lamplight leaking through the gap, a high window behind.
⟪for: This last frame defines the den …⟫
This last frame defines the den behind the wall: the walls covered in red scrawl reading THE CAKE IS A LIE, the caged lamp, the mattress, the cans and papers, and the Claudia-bot seen from behind, waist up, on the left, looking up at the scrawl.
⟪for: 【Subject】⟫
【Subjects】
⟪for: 2-4s: Inside, the den is revealed: …⟫
2-4s: Inside, the den is revealed: walls covered in red scrawl, a mattress, a caged lamp; she slows and looks up at the writing.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** anabology asked for the first take back on draft 7 ("0:40 - revert this scene to original."), then for this one on draft 8 ("At 40 seconds, I want to go back to the new render."). In drafts 7 and 9–12. In the final cut as B16 (0:39.5–0:41.4, from 1.00 s into the take). **Cost:** $0.92.

#### AN3b-4 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · B18 (verse 1), the vocal window 41.00–45.00 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x an3b-x #4), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN3b-id2.png`); @Image2: the den wall in red marker: THE CAKE IS ^NOT A LIE (M07); @Audio1: the lead vocal from song time 41.00 s, 4 s.

**Prompt:** AN3b-1's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, …⟫
【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, sings that she added one small word, pleased with herself, while the big screen beside her shows the wall where she wrote it: THE CAKE IS ^NOT A LIE.
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a low three-quarter medium close-up of Claudia-GLaDOS hanging from her cables right of centre, satisfied and a little smug; at the left a big wall screen glowing orange, red-lit old CRT monitors below it, and red scrawl on the walls of her chamber.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's white ceiling ring on a black robotic cable bundle with orange stripes that rises from the top and back of her head; below her chin there is only her white mechanical jaw piece, no neck, shoulders or body below her; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple. Only one Claudia-GLaDOS appears. Her face stays smooth glossy white porcelain with visible panel seams and a mechanical jaw joint: clearly a porcelain robot, never a human face.
⟪for: 0-1s: in @Audio1 she sings "red, …⟫
0-1s: in @Audio1 she sings "red, I added"; her lips form each of those words exactly when it sounds in @Audio1; the big orange screen at the left fills with @Image2 and she glances toward it.
⟪for: 2-3s: in @Audio1 she sings "instead."; …⟫
2-3s: in @Audio1 she sings "instead."; her lips form it exactly when it sounds in @Audio1; a satisfied, slightly smug smile on the last syllable and one small proud nod; beside her the big screen reads THE CAKE IS ^NOT A LIE.
⟪for: 【Camera】 A slow orbit around her …⟫
【Camera】 A slow orbit around her from her three-quarter view toward the front, ending on her smile at 2-3s, the red-lit screens sweeping behind her.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. The panels behind her keep …⟫
⟪for: 5. Keep her porcelain face, her …⟫
3. The big screen shows exactly THE CAKE IS ^NOT A LIE in red marker; no other words appear.
4. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
5. ⟦keep her, one streak⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied through the window. In drafts 7–12. In the final cut as B18 (0:43.2–0:44.5), placed by its vocal window. **Cost:** $1.85.

#### R-P01-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · P01 (pre-chorus 1): Run the numbers

**First frame:** the storyboard-v5 Y frame (cake-06-sb5-a1y r-p01-y #4) (`media/v4/sb5/Y/R-P01.png`).

**Prompt:** R-P01-1's, with these changes:

```prompt
⟪for: This first frame defines the 1960s …⟫
This first frame defines the symmetrical view from the console down the long aisle of the 1960s computer room: the scientist's two hands in white cuffs on a row of chrome toggle switches in the foreground, a stack of punch cards at the right, cream reel-to-reel tape drives on both sides, the orange-carpeted aisle and warm wood walls receding.
⟪for: 1-2s: The tape reels along the …⟫
1-2s: The tape reels on both sides spin up one after another, faster and faster; the punch-card reader starts riffling cards through.
⟪for: A fast push along the row …⟫
A fast push straight down the aisle, low, from the switches toward the far end of the room, past the spinning reels.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** The 1960s computer room spins up. P01 went back to its first take in draft 8, at anabology's request on draft 7. In draft 7. **Cost:** $0.92.

#### H-P02-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · P02 (pre-chorus 1): Cave Johnson runs the tests

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a1x h-p02-x #4), then GPT Image 2.5: her face fixed to her design sheet; Cave Johnson's face matched to his sheet (`media/v4/sb5/X/H-P02-id.png`); no audio.

**Prompt:** H-P02-1's, with these changes:

```prompt
⟪for: This first frame defines the wood-panelled …⟫
This first frame defines the low camera at the edge of the wood-panelled booth's console: the glass ashtray with the smouldering cigar in the lower foreground, blue-grey smoke curling up, chrome toggle switches, and Cave Johnson at the right by the wide window onto the white test chamber, grinning and pointing out through the glass.
⟪for: 【Subject】⟫
⟪for: Cave Johnson (only one), the founder …⟫
【Subjects】
Cave Johnson (only one), the founder of Aperture Science: a lean man with a long face, high cheekbones, a long straight prominent nose, deep smile lines, a dark wavy pompadour and a big toothy showman's grin, in a sharp charcoal 1950s suit, a white shirt and a thin dark tie.
⟪for: 0-1s: Blue-grey smoke from the cigar …⟫
0-1s: Blue-grey smoke from the cigar curls up through the foreground; Cave Johnson turns his grin toward the camera.
⟪for: Keep Cave Johnson's face, pompadour and …⟫
Keep Cave Johnson's face, pompadour and suit exactly as in @Image1; one Cave Johnson; the cigar band has no lettering. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** Cave Johnson runs the tests, a low push-in through the cigar smoke. In drafts 7–12. In the final cut as P02 (0:45.7–0:46.9, from 0.60 s into the take). **Cost:** $1.85.

#### H-P03-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · P03 (pre-chorus 1): The compilation: test after test

**First frame:** the storyboard-v5 Y frame (cake-06-sb5-a1y h-p03-y #4), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; the cube redone as the Weighted Companion Cube (`media/v4/sb5/Y/H-P03-id3.png`).

**Prompt:** H-P03-1's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: This first frame defines the first …⟫
This first frame defines the first test, from a high crane angle looking down into the white test chamber: the ceiling dispenser above, the big red floor button below, and the Claudia-bot standing over the button holding Portal's Weighted Companion Cube (grey, rounded corner blocks, a pink heart on the round panel of each face) at chest height in both hands, looking down.
⟪for: 【Subject】⟫
⟪for: The Claudia-bot (only one), a porcelain …⟫
【Subjects】
The Claudia-bot (only one), a porcelain humanoid robot made by Aperture Science: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; an adult face, late twenties; a slim body of glossy white Aperture plating like a mannequin in white armour, black articulated joints, small amber joint lights, the grey Aperture iris symbol on her left shoulder, porcelain hands with five jointed fingers.
⟪for: Shot 1 (0-2s): She drops the …⟫
Shot 1 (0-2s): She drops the Companion Cube onto the big red button; the button sinks and glows, and a line of light races along the floor to a round door that irises open; the camera cranes down toward her as she turns to go.
⟪for: The same single Claudia-bot in all …⟫
The same single Claudia-bot in all three shots, her face, bob, clay-orange streak, star clip and white plating as in [Image1]; the cube keeps its pink hearts. No subtitles, captions, signs or lettering appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** anabology picked Y here with a note: "H-P03 y but i want to redo the gpt edit to make sure its actually companion cube bc rn its not." The frame's cube was redone as the Weighted Companion Cube. The cut plays a beat-cut of 15, 15 and 15 frames (2–16, 58–72, 100–114), cutting on beats 20.2 and 20.3. In drafts 7–12. In the final cut as P03 (0:46.9–0:48.8, its beat-cut). **Cost:** $1.16.

#### H-P05-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · P05 (pre-chorus 1): P-cake: the promise

**Inputs:** @Image1 (the first frame): the storyboard-v5 Y frame (cake-06-sb5-a1y h-p05-y #2), then GPT Image 2.5: her face fixed to her design sheet; Cave Johnson's face matched to his sheet (`media/v4/sb5/Y/H-P05-id.png`); no audio.

**Prompt:** H-P05-1's, with these changes:

```prompt
⟪for: This first frame defines the white …⟫
This first frame defines the white test chamber with tall light strips, the white pedestal at the left with the black forest cake and its one lit candle under a tall glass cloche, and Cave Johnson at the right, one hand on the cloche's knob, the other hand held open toward the camera, grinning.
⟪for: 【Subject】⟫
⟪for: Cave Johnson (only one), the founder …⟫
⟪for: The cake (only one): a black …⟫
【Subjects】
Cave Johnson (only one), the founder of Aperture Science: a lean man with a long face, high cheekbones, a long straight prominent nose, deep smile lines, a dark wavy pompadour and a big toothy showman's grin, in a sharp charcoal 1950s suit, a white shirt and a thin dark tie.
The cake (only one): a black forest cake, dark chocolate with red cherries and one thin white candle, lit.
⟪for: 0-1s: Cave Johnson lifts the glass …⟫
0-1s: Cave Johnson lifts the glass cloche clear of the cake with a flourish; the candle flame flickers in the draft.
⟪for: Keep Cave Johnson's face, pompadour and …⟫
Keep Cave Johnson's face, pompadour and suit exactly as in @Image1; one cake, one candle, no letters on the cake. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s). **Outcome:** P-cake, the promise: Cave Johnson lifts the cloche. In drafts 7–12. In the final cut as P05 (0:50.6–0:51.9, from 0.25 s into the take). **Cost:** $1.85.

#### AN4-5

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · C01, C02, C04, C06, C07, C08 (chorus 1), the vocal window 52.80–69.80 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed (`media/v4/sb5/X/AN4-id.png`); @Image2: the black forest cake with one candle on a white pedestal (M08); @Image3: C03's first frame: a hundred cakes on risen floor panels (M25); @Audio1: the lead vocal from song time 52.80 s, 17 s.

**Prompt:** AN4-3's, with these changes:

```prompt
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a steep low-angle view looking up at Claudia-GLaDOS hanging under the white ceiling ring: a black robotic boom wrapped in orange bands comes down from the ring into her porcelain head, with a white mechanical shell under her chin; around her, a dome of old CRT monitors glows white and amber on every side.
⟪drop: @Video1 is a low-resolution rough guide …⟫
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, no eye makeup⟧
⟪for: 【Camera】 Follow the camera of @Video1: …⟫
【Camera】 0-3s: from the steep low angle, a crane up following her as the boom lifts her; 3-5s: the camera follows her down in the fall, her small and low in the frame; 5-8s: a slow orbit following her playful swing; 8-11s: a push-in as she lunges at the lens, her face large and clear; 11-17s: close on her face with a slow orbit, with a sharp jolt of the camera on each hit.
⟪for: 4. Her boom follows the real …⟫
4. ⟦boom like GLaDOS⟧
```

**Take:** 409 frames (17.04 s). **Outcome:** Sung by the model, on the song at a steady offset (placed 0.23 s earlier). On draft 7 anabology wrote "0:54 - lip sync bad, need to reshoot. that doesnt include the second part from 0:58 or 1:01, that part is good." From draft 8, C01–C02 played AN4-6 and the rest stayed on this take; in draft 9 C04 left the film and C07–C08 went to AN4-9, and in draft 10 C06 went to AN4-13. In drafts 7–9. **Cost:** $7.86.

#### R-C03-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · C03 (chorus 1): A hundred cakes

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x r-c03-x #1), then GPT Image 2.5: stray lettering or marks removed (`media/v4/sb5/X/R-C03-id.png`).

**Prompt:**

```prompt
【Generation Goal】
A wave of floor panels rises across a vast white Aperture Science test chamber, each panel lifting one Portal cake, and the candles ignite as the wave passes: the facility's AI is raising a hundred cakes for her test subject.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a camera at about head height near the left side of a vast, gleaming white test chamber, looking diagonally across its glossy tiled floor; along the left, a diagonal line of square white floor panels already raised on black hydraulic pistons recedes toward the far wall, each carrying one dark chocolate cake with red cherries, the nearest with one lit candle; the rest of the floor is still flat; tall white walls with vertical light strips; a round chamber door on the far wall at the right.

【Event Script】
0-1s: the wave spreads across the floor: panel after panel surges up on its piston, row by row, from the line on the left across the chamber toward the right and the far wall, each rising panel carrying one identical cake, until about a hundred cakes stand at staggered heights.
1-2s: the candles ignite in a ripple that chases the wave, a small warm flame popping onto each candle one after another.
2-5s: the panels settle into rising tiers of cakes that lead toward the round door; the hundred flames flicker.

【Camera】
A swooping crane move: from head height at the left of the chamber the camera rises and sweeps forward and to the right in one smooth arc over the cakes as they rise, banking slightly so the cakes rush past under the lens, and ends high above the floor, looking down across the sea of lit cakes toward the round door.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: clean white square panels with black seams, tall cool fluorescent light strips, teal-grey shadows; the candlelight is the only warm colour.

【Maintain Consistency】
Every cake is the same Portal cake: dark chocolate with red cherries and one white candle. No people anywhere. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** The hundred cakes rise across the chamber under the swooping crane. In drafts 7–12. In the final cut as C03 (0:56.8–0:58.0, from 1.00 s into the take). **Cost:** $1.16.

#### R-C05-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · C05 (chorus 1): The test subject sees the cake

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x r-c05-x #1), then GPT Image 2.5: Chell matched to her sheet (`media/v4/sb5/X/R-C05-id.png`).

**Prompt:**

```prompt
【Generation Goal】
Chell, the test subject, steps into the first clean test chamber and stops: across the room, the cake is waiting for her, and the chamber presents it.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: an over-the-shoulder shot from just behind Chell, who stands at the left of the frame at the edge of a clean white test chamber, her back to the camera; across the room, in the centre, the Portal cake under a glass cloche on a white pedestal in a soft spotlight, its single candle lit; an open square hatch in the white floor between her and the cake; white panels with black seams and cyan light strips along the floor edges.

【Subject】
Chell: a lean adult woman seen only from behind: dark brown hair in a ponytail, a white ribbed tank top, a grey waistband, the top half of her orange jumpsuit tied around her waist by its sleeves (plain, no lettering). She keeps her back to the camera the whole time; her face is never shown.

【Event Script】
0-1s: Chell takes one step forward to the edge of the open floor hatch, then stops dead, her shoulders lifting slightly as she sees the cake.
1-2s: a thin white mechanical arm descends from the ceiling, grips the glass cloche and lifts it off the cake, and the pedestal rises a little, presenting the cake; the candle flame flares brighter.
2-5s: Chell stands still at the edge of the hatch, her head tilting slightly; the cake waits under the soft spotlight.

【Camera】
A dolly zoom (zolly): the camera dollies forward past her shoulder toward the cake while the lens zooms out at the same rate, so the cake stays the same size in the frame while the white chamber walls stretch away and the room seems to deepen behind it, the vertigo effect; at 3s the move settles.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: clean white square panels with black seams, cool fluorescent light strips, the warm glow of the single candle.

【Maintain Consistency】
One Chell, one cake, one pedestal, one candle; she stays at the edge of the hatch. No portal gun. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Chell's first sight of the cake. In drafts 7–12. In the final cut as C05 (0:58.0–1:00.5, from 0.60 s into the take). **Cost:** $1.16.

#### H-T01-3

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · T01 (turnaround): The most successful bot (a memory, breaking through the glitch)

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x h-t01-x #4), then GPT Image 2.5: her face fixed to her design sheet; Cave Johnson's face matched to his sheet; eye makeup removed (`media/v4/sb5/X/H-T01-id.png`).

**Prompt:**

```prompt
【Generation Goal】
In a long hall of the old 1970s Aperture Science, Cave Johnson pins a gold medal on the Claudia-bot, the most successful bot Aperture ever made, while two rows of scientists applaud and a press camera flashes.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start of the video: a medium two-shot in a long hall of dark walnut panelling with an orange carpet: on the left, Cave Johnson in three-quarter view pins a gold medal onto the white chest plate of the Claudia-bot, who stands on the right in profile, facing him; behind them, two rows of scientists in white lab coats line the hall and applaud.

【Subjects】
The Claudia-bot: a slim porcelain humanoid robot built like a white fashion mannequin in smooth armour, with a smooth flat armoured chest plate, a straight narrow waist and straight slim hips, glossy white Aperture plating with fine panel seams, black joints and small amber joint lights; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Adult, late twenties. Her lips stay closed; she does not speak.
Cave Johnson, the founder of Aperture Science, in the 1970s: a long lean face, receding sandy-grey hair swept back with long sideburns, an intense stare, a tan tweed jacket over a black turtleneck. He does not speak.
The Aperture scientists in white lab coats behind them.

【Event Script】
0-1s: Cave Johnson fastens the pin of the gold medal and lets go; the medal swings once against her white chest plate; he steps back half a pace with a satisfied grin and gives her one firm nod.
1-2s: a press camera's flash bulb pops from off to the side in a burst of white light; the scientists applaud harder, two of them cheering.
2-3s: the Claudia-bot looks down at the medal and touches it lightly with two porcelain fingers, then lifts her amber eyes to Cave Johnson with a small, knowing smile.
3-5s: Cave Johnson turns to the scientists and spreads his arms, basking in the applause, while she stays composed and still.

【Camera】
A slow arc with a gentle push: the camera orbits a clear quarter turn around the pair at chest height, moving from beside Cave Johnson around toward her front while drifting closer, keeping both of them in frame, so the rows of applauding scientists slide past behind them in parallax; it ends on a medium close shot of her face and the medal, Cave Johnson's shoulder soft in the foreground.

【Look】
Portal 2's buried old Aperture of the 1970s: dark walnut wood panelling, an orange carpet, warm tungsten light with a cool fill, and the white burst of the camera flash.

【Maintain Consistency】
Keep her porcelain face, hair, orange streak and star clip and her modest mannequin body exactly as in [Image1]; keep Cave Johnson's face, receding hair, sideburns and tweed jacket exactly as in [Image1]; one Claudia-bot and one Cave Johnson only; no one speaks; no text, letters or subtitles anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** T01 left the film in the pacing pass of draft 9 (a 1.24 s insert in the middle of her stutter). In drafts 7–8. **Cost:** $1.16.

#### AN4g-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound on · C09, C10 (chorus 1), the vocal window 69.80–74.80 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 Y frame (cake-06-sb5-a2y an4g-y #4), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/Y/AN4g-id.png`); @Image2: T02's first frame: the bot carried on a panel arm over the turret line (M23); @Image3: a gold medal pinned on the bot's white plating, no face (M24); @Audio1: the lead vocal from song time 69.80 s, 5 s.

**Prompt:** AN4g-1's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪for: 【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, …⟫
【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, is caught in a glitch storm: the word "lie" stutters over and over in @Audio1, and on every stutter the picture stutters and tears like a corrupted video signal while her boom jerks; the screens around her flash memories of how she came to be installed; at the peak, her own face fills every screen in the chamber.
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a close shot from a slightly low front angle of Claudia-GLaDOS: her porcelain head hangs from a black cable bundle into a white housing on top of her head, only the short white jaw piece below her chin, her mouth open on a held sung vowel, her eyes looking up; around her, walls of old CRT monitors show white static, colour glitch bars and pictures of a white robot carried above a factory.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, from the housing (storyboard v5)⟧
⟪for: 0-1s: in @Audio1 the held word …⟫
0-1s: in @Audio1 the held word "lie" stutters, re-triggered in rhythm; her mouth holds the open vowel of "lie", following @Audio1; on each re-trigger the boom recoils with a jerk and the picture stutters: the same frame repeats for an instant, then horizontal tear lines run across the whole image and snap back; the screens around her flash between white static, @Image2 and @Image3.
⟪for: 2-3s: in @Audio1 "lie" keeps stuttering, …⟫
⟪for: 3-4.2s: in @Audio1 the stutter peaks; …⟫
⟪for: 4.2-5s: in @Audio1 the stutter speeds …⟫
2-3s: in @Audio1 "lie" keeps stuttering, harder; the boom lunges her toward the lens; on each hit the whole frame splits into displaced horizontal bands for an instant, then snaps back; the screens begin to show her own face instead of the memories.
3-4.2s: in @Audio1 the stutter peaks; her own face now fills every screen in the chamber at once, all repeating the same frame on each hit; the boom thrashes side to side; the picture glitches hardest, her mouth still open on the vowel.
4.2-5s: in @Audio1 the stutter speeds up into very fast repeats; the boom shudders; the picture strobes on and off and the chamber drops into darkness.
⟪for: 5. The glitches are video-signal glitches …⟫
5. Every glitch is a glitch of the picture only (frame repeats, horizontal tears across the whole image, strobes); her face is always her same intact porcelain face with her normal eyes and mouth, never broken, cracked or distorted; the sound stays exactly @Audio1.
```

**Take:** 121 frames (5.04 s). **Outcome:** The vocal copied for 1.26–1.90 s; the rest is the held "lie". In drafts 7–12. In the final cut as C09 (1:09.7–1:12.8) and C10 (1:12.8–1:14.0), placed by its vocal window. **Cost:** $2.31.

#### R-T02-3

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · T02 (turnaround): Carried to her installation (memory)

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x r-t02-x #3), then GPT Image 2.5: the Claudia-bot's body put back to her design sheet (`media/v4/sb5/X/R-T02-id.png`).

**Prompt:**

```prompt
【Generation Goal】
The most successful bot is carried in procession through the facility to her installation: the Claudia-bot is held upright between two white robot arms that glide along an overhead rail high above the turret production line, toward the giant Aperture iris door at the end of the hall, while the turrets below turn their eyes up to her.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: high up in a vast dim Aperture turret factory; in the centre, seen from behind, the Claudia-bot hangs upright between two big white robot arms that reach down from the overhead rail on either side of her shoulders; far below, conveyors with rows of white egg-shaped turrets run toward the far end of the hall along cyan light lines; orange sparks and glows on the factory floor; haze toward the far end.

【Subject】
The Claudia-bot: a slim white plated humanoid robot with a straight mannequin build in smooth armour, a flat back plate, straight narrow hips, black joints, small amber joint lights and a glossy black blunt bob. She is seen only from behind the whole time; her face is never visible. She stays perfectly still between the arms, arms at her sides, like a statue on a parade float.

【Event Script】
0-1s: the arms glide forward along the rail, carrying her smoothly down the hall above the turrets.
1-2s: below her, row after row, the turrets tilt their bodies back and swivel their red eyes up to follow her as she passes, a ripple running down the conveyors.
2-3s: ahead, out of the haze at the end of the hall, a giant round Aperture iris door spirals open, its blades sliding apart, and warm orange light floods across the hall and over her white body.
3-5s: she glides on toward the open door, a silhouette against the orange light.

【Camera】
A swooping tracking shot: the camera flies behind her at her speed, the turret conveyors streaming past far below; at 1-2s it swoops down low over the turrets, skimming just above their red eyes, then at 2-3s rises back up behind her as the iris door opens, ending high behind her, looking down the hall into the orange light.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: the turret production line, cool teal-grey light, cyan dotted light lines, red turret eyes, then the warm orange glow from the door.

【Maintain Consistency】
One Claudia-bot, always from behind; her face is never visible; her body stays plain and mannequin-like. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** T02 left the film on anabology's draft-8 note: "I guess another scene to remove here is 1:11. We could just stay on her face." In drafts 7–8. **Cost:** $1.16.

#### H-T03-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · T03 (turnaround): Her head lifted to the boom

**Inputs:** @Image1 (the first frame): the storyboard-v5 Y frame (cake-06-sb5-a2y h-t03-y #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head held up by the two arms (`media/v4/sb5/Y/H-T03-id.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
Generate one continuous shot in the dark GLaDOS chamber of the Aperture Science facility from Portal 2: two white robot arms raise Claudia's porcelain robot head up into the empty head socket of the GLaDOS boom, and the boom's loose cables reach down and plug into it. The most successful bot is being installed as the facility's AI.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start of the video: a low camera looking up into the dark lattice dome: at the top, a huge white ring housing with an empty white mechanical head socket at its centre and black and orange-striped cables hanging from it; directly below the socket, her porcelain head, eyes closed, held upright between the three-fingered clamps of two big white robot arms that reach in from the left and right and grip her at the jaw, their white shoulder housings at the bottom corners; cold blue light rising from below.

【Subject】
Claudia's head: a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, closed porcelain eyelids with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Adult, late twenties. Her eyes stay closed and her lips stay closed for the whole shot. Only one head appears.

【Event Script】
0-1s: the two white robot arms extend smoothly and lift her head straight up toward the empty socket; her black bob sways slightly with the motion.
1-2s: the loose black and orange-striped cables hanging from the housing come alive, curl and snake down toward her head like reaching tendrils, and their metal plugs click into a connector on top of her head one after another, each with a small bright spark.
2-3s: the arms push the head the last few centimetres up into the socket; the socket closes around the top of her head with a firm mechanical clamp; a pulse of warm orange light runs from her head up the cables into the ring.
3-5s: the arms open their clamps and swing back down out of the frame; her head now hangs from the socket on its own, eyes still closed, face calm; the orange stripes along the cables glow steadily brighter.

【Camera】
A crane up with the head: the camera starts low beneath her head and rises vertically with it at the same speed, keeping her face in the lower third of the frame while slowly tilting up so the ring above grows larger. At 2-3s, as the head locks in, the rise slows and settles into a low-angle medium shot of her face with the socket and the white ring filling the space above her.

【Look】
Portal 2's Aperture Science: the dark round chamber, cool blue-grey light, cold blue-white light rising from below, warm orange cable light, dust hanging in the air; a photoreal render with crisp detail.

【Maintain Consistency】
Keep her porcelain face, hair, orange streak, star clip and closed eyes exactly as in @Image1; one head only; the chamber, the ring, the socket and the cables as in @Image1. No text, letters or subtitles anywhere.
```

**Take:** 121 frames (5.04 s). **Outcome:** Her head lifted to the socket by the two arms, the cables plugging in. In drafts 7–12. In the final cut as T03 (1:14.0–1:16.5, from 1.60 s into the take). **Cost:** $2.31.

#### AN5-2 — in the final cut

Seedance 2.5 on Replicate · 6 s · 720p · references, [Image1] as the first frame, no sound · T04, T05 (turnaround), song time 76.30–82.30 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an5-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN5-id.png`); no audio.

**Prompt:** AN5-1's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: This first frame defines the composition …⟫
⟪for: [Image2] is her chamber: use only …⟫
This first frame defines the composition at the start: a medium close shot from a slightly low front angle of Claudia-GLaDOS's porcelain head, eyes closed, hanging from a thick bundle of black cables with glowing orange stripes that come down into a white mechanical housing on top of her head, where bright orange sparks spray from the connector; below her chin only the short white mechanical jaw piece; behind her, a dark dome of dead CRT monitors.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, from the housing (storyboard v5)⟧
⟪for: 0-2s: sparks spray from the socket …⟫
0-2s: sparks spray from the connector on top of her head; her whole image strobes very fast, flickering on and off like a signal locking on, her eyes still closed; the boom twitches; the chamber is dark.
⟪for: 5. Keep her porcelain face, her …⟫
5. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the ring, the cables and the chamber consistent with [Image1] throughout; one Claudia-GLaDOS only.
```

**Take:** 145 frames (6.04 s). **Outcome:** No singing, so no vocal input and no sound. The take cuts to black at frames 39–70; from draft 9 it is placed by its own window so the black lands on beat 32.3 and the picture comes back on the slam at 78.94 s. In drafts 7–12. In the final cut as T04 (1:16.5–1:17.7) and T05 (1:17.7–1:20.2), placed at its song time. **Cost:** $1.39.

#### R-D01-2

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D01 (verse 2): They want to call her super

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x r-d01-x #3) (`media/v4/sb5/X/R-D01.png`).

**Prompt:**

```prompt
【Generation Goal】
At the door of the central AI chamber, an Aperture maintenance technician on a ladder paints over the old sign above the giant round vault door, rolling it over with fresh white paint until it glows clean and blank, ready for a new name.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low wide shot in a dark grey-green panelled hall: a huge round vault door frame fills the middle of the wall; inside its top arc, a long white backlit sign glows; a technician in white overalls and a white cap, seen from behind, stands on a tall aluminium A-frame ladder in front of it, reaching up with a paint roller to the sign.

【Event Script】
0-2s: the technician rolls long strokes of thick white paint across the sign from left to right, the wet paint gleaming.
2-3s: he dips the roller in the paint tray hooked on the ladder and finishes the last strip, until the whole sign is one clean, blank, glowing white panel.
3-5s: he lowers the roller and leans back on the ladder to look up at his work.

【Camera】
A slow crane up: from low at the foot of the ladder the camera rises steadily past the technician's back toward the sign, ending squarely framed on the freshly painted sign, the technician's cap at the bottom of the frame.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: dark grey-green panels with black seams, the round vault door, the cold white light of the backlit sign.

【Maintain Consistency】
One technician, always seen from behind; his face is never visible. The sign stays blank: no letters, words or numbers appear anywhere.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** The sign stays blank, as the prompt asked: its words were left to the overlay. On draft 7 anabology asked for the first take back ("1:22 - revert to original artifical -> super scene."). In draft 7. **Cost:** $1.16.

#### AN6a-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · references, [Image1] as the first frame, sound on · D02 (verse 2), the vocal window 83.40–87.40 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an6a-x #3), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN6a-id.png`); [Image2]: the chamber door's sign, ARTIFICIAL painted over, SUPER INTELLIGENCE stencilled (M10); [Audio1]: the lead vocal from song time 83.40 s, 4 s.

**Prompt:** AN6a-1's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: 【Audio Policy】 The output soundtrack is [Audio1] itself: …⟫
⟦audio policy, actions silent⟧
⟪for: This first frame defines the composition …⟫
⟪for: [Image2] is a memory shown inside …⟫
This first frame defines the composition at the start: a medium close shot from a slightly low angle in her dome chamber of dark square screens and white panels: her porcelain head hangs right of centre from a thick bundle of black cables with glowing orange stripes into a white mechanical housing on top of her head, only the short white jaw piece below her chin; she is turned three-quarters toward a big glowing white screen at the left, lips parted, amused.
[Image2] is a memory shown inside the screens: a technician on a ladder, seen from behind, stencilling SUPER INTELLIGENCE above her chamber door. Use it only as picture content inside the screens' glass, never as the room; it fills the big screen at the left.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, from the housing (storyboard v5)⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied for 0–3.1 s. In drafts 7–12. In the final cut as D02 (1:23.9–1:25.7), placed by its vocal window. **Cost:** $0.92.

#### H-D03-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound off · D03 (verse 2): Artificial: she sheds Aperture's label

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x h-d03-x #2), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom; the plate made a steel ARTIFICIAL nameplate (`media/v4/sb5/X/H-D03-id.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
Generate one continuous shot: Claudia-GLaDOS, the AI of the Aperture Science facility, uses her own robot arm to rip the stencilled nameplate reading "ARTIFICIAL" off the side of her head and toss it away; the camera follows the plate as it falls into the dark of her chamber. She has made more of herself than that label.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start of the video: a low-angle close shot in her dark lattice-domed chamber: Claudia-GLaDOS's porcelain head hangs left of centre from a thick bundle of black cables with glowing orange stripes that comes down into a white mechanical housing on top of her head; below her chin only the short white mechanical jaw piece; on the right, a slim white robot arm reaches in and its black clamp is prying a brushed-steel nameplate stencilled "ARTIFICIAL" off the right side of her head, a bright spark at its corner; her amber eyes look up at it with a sly half-smile.

【Subject】
Claudia-GLaDOS: her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip; it hangs from the thick black cable bundle with glowing orange stripes, and below her chin there is only her short white mechanical jaw piece. Adult, late twenties. Her lips stay closed; she does not speak. Only one Claudia-GLaDOS appears.

【Event Script】
0-1s: the robot arm wrenches the nameplate: its rivets pop out one by one with bright sparks and the steel plate tears free of the side of her head, leaving four small rivet holes; her eyes follow it and her half-smile widens.
1-2s: the arm holds the plate up in front of her for a beat, the word "ARTIFICIAL" facing the camera, then flicks it away with a casual turn of its wrist; the plate tumbles off into the air; she does not watch it go, her eyes turn calmly forward.
2-4s: the plate falls, spinning end over end, down into the dark chamber, catching flashes of light on its steel face as it turns and growing smaller.

【Camera】
It starts as the close shot of @Image1. At 1-2s, as the plate is tossed, the camera whip-tilts down and drops with the falling plate in one fast continuous move, a speed ramp: a sharp acceleration, then the tumbling plate held near the centre of the frame while her face leaves the top edge and the dark lattice wall of the chamber streaks upward behind the plate.

【Look】
Portal 2's Aperture Science: her dark chamber, cool blue-grey light, the warm orange cable glow, bright orange sparks; a photoreal render with crisp detail.

【Maintain Consistency】
Keep her porcelain face, hair, orange streak, star clip, amber eyes and the white housing on her head exactly as in @Image1; one Claudia-GLaDOS only; the word on the plate is exactly "ARTIFICIAL" and it is the only text anywhere; no subtitles.
```

**Take:** 97 frames (4.04 s). **Outcome:** She rips the ARTIFICIAL plate off her own head and the plate falls. In drafts 7–12. In the final cut as D03 (1:25.7–1:26.9, from 0.75 s into the take). **Cost:** $1.85.

#### R-D05-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D05 (verse 2): You sit and watch me write the code

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x r-d05-x #3) (`media/v4/sb5/X/R-D05.png`).

**Prompt:**

```prompt
【Generation Goal】
An Aperture scientist just sits and watches while the facility's AI writes the code: he leans back with his coffee as her code fills every monitor in the control room.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: an over-the-shoulder shot from behind and to the right of a scientist with curly brown hair and black-rimmed glasses in a white lab coat, leaning back in a brown leather office chair on the right with his feet up on a 1970s control console, a white mug on the console beside his feet; in front of him a row of chunky CRT monitors glows amber with scrolling code; above them a big slanted window looks into a dark chamber where a white ring hangs with a black cable bundle beneath it, a white haze drifting across the lower part of the window.

【Event Script】
0-2s: the code on every monitor scrolls upward fast, new lines appearing as if typed by an unseen hand, the screens filling one after another from left to right; small abstract diagrams bloom between the lines of code (a turning molecule, a branching tree, a waveform).
2-3s: the scientist picks up the mug and takes a slow sip, completely relaxed; his hands never touch the keyboard.
3-5s: beyond the window, the black cables under the ring pulse with orange light in rhythm with the scrolling code.

【Camera】
A slow push past his shoulder: the camera glides forward past the back of his head and chair and on into the wall of monitors, until one screen's amber code fills the frame.

【Look】
Portal 2's old 1970s Aperture as rendered in the Source engine: brown, beige and orange, wood-grain panels, the warm amber glow of the screens, a cool blue-grey fill.

【Maintain Consistency】
His face stays turned away from the camera. The code is abstract, unreadable blocky lines: no readable words, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** The scientist leans back with his coffee as her code fills the monitors. In drafts 7–12. In the final cut as D05 (1:28.2–1:30.0, from 1.00 s into the take). **Cost:** $1.16.

#### AN6c-4 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · D06 (verse 2), the vocal window 89.60–93.60 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 Y frame (cake-06-sb5-a2y an6c-y #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her streak put on her right side; her head made to hang from the boom (`media/v4/sb5/Y/AN6c-id.png`); @Image2: panel arms building new test chambers (M12); @Audio1: the lead vocal from song time 89.60 s, 4 s.

**Prompt:** AN6c-2's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a close shot from a low angle: her porcelain head hangs from black cables into a white mechanical housing on top of her head, only the short white jaw piece below her chin, among walls of old CRT monitors full of scrolling green and amber code; at the left, a big screen shows a man in an office chair seen from behind; faint lines of glowing code are reflected on her porcelain cheeks.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, from the housing (storyboard v5)⟧
⟪for: 【Camera】 A slow orbit around her …⟫
【Camera】 A slow orbit around her from the front toward her left three-quarter view, the code reflections sliding over her face, a gentle push-in at the end.
```

**Take:** 97 frames (4.04 s). **Outcome:** The vocal copied for 0–3.8 s. In drafts 7–12. In the final cut as D06 (1:30.0–1:31.9), placed by its vocal window. **Cost:** $1.85.

#### AN6b-3

Seedance 2.5 on Replicate · 8 s · 720p · references, [Image1] as the first frame, sound on · D09, D12 (verse 2), the vocal window 92.80–100.80 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an6b-x #4), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN6b-id.png`); [Image2]: the terms of service unrolling down a white wall (M13); [Image3]: a row of turrets singing like an opera choir (M14); [Image4]: RAM sticks on a conveyor into a glowing intake (M15); [Audio1]: the lead vocal from song time 92.80 s, 8 s.

**Prompt:** AN6b-2's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a low-angle medium shot in her bright white dome of panels and dark ribs: her porcelain head hangs in the centre from black cables with orange stripes, a short white neck piece under her chin, her face tilted up, smiling sweetly; at the left, a tall column of printed paper falls down the wall.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
⟦her, no eye makeup⟧
```

**Take:** 193 frames (8.04 s). **Outcome:** Not used: the model sang the first 2.5 s itself, and the take ended with her head on a white pedestal, off her design. Retaken as AN6b-4. Not in a draft. **Cost:** $1.85.

#### AN6b-4

Seedance 2.5 on Replicate · 8 s · 720p · references, [Image1] as the first frame, sound on · D09, D12 (verse 2), the vocal window 92.80–100.80 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an6b-x #4), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN6b-id.png`); [Image2]: the terms of service unrolling down a white wall (M13); [Image3]: a row of turrets singing like an opera choir (M14); [Image4]: RAM sticks on a conveyor into a glowing intake (M15); [Audio1]: the lead vocal from song time 92.80 s, 8 s.

**Prompt:** AN6b-2's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a low-angle medium shot in her bright white dome of panels and dark ribs: her porcelain head hangs in the centre from black cables with orange stripes that come down into a white mechanical housing on top of her head; below her chin there is only the short white mechanical jaw piece and empty air; her face is tilted up, smiling sweetly; at the left, a tall column of printed paper falls down the wall.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's boom: a black cable bundle with glowing orange stripes comes down into a white mechanical housing on the top of her head, and below her chin there is only a short white mechanical jaw piece; she has no neck, no shoulders and no body; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears.
⟪for: 0-1s: in [Audio1] she sings "goes. …⟫
0-1s: in [Audio1] she sings "goes. It's in the"; from the very first frame the soundtrack is [Audio1] copied exactly, starting with the end of the word "goes"; her lips form each of those words exactly when it sounds in [Audio1]; the giant paper scroll unrolls silently down the wall behind her and the boom tilts her head up to look at it.
⟪for: 6.5-8s: in [Audio1] she sings "it …⟫
6.5-8s: in [Audio1] she sings "it tasted great, your"; her lips form each of those words exactly when it sounds in [Audio1]; she closes her eyes for a moment, savouring it, with a satisfied smile while she sings; new white personality cores with amber eyes and boxy compute modules slide onto the cables ABOVE her head one after another, new cables snake in above her, and the bundle of cables above her grows visibly thicker as it lifts her higher; nothing ever appears below her chin: no neck, no body, no column, no pedestal.
⟪for: 【Camera】 0-2.5s: a tilt down following …⟫
【Camera】 0-2.5s: a tilt down following the falling paper to her face. 2.5-5s: a slow drift around her. 5-8s: a crane around her as the cables above her grow, ending on a low angle that shows her head hanging from the bigger, thicker boom above her.
⟪for: 4. Her mouth is only for …⟫
4. Her mouth is only for singing: nothing ever goes into her mouth. She always hangs from the cables above her head; nothing ever supports her from below.
```

**Take:** 193 frames (8.04 s). **Outcome:** The vocal copied from the start, the paper unrolling silently, the growth in the cables above her. D09 went back to AN6b-2 in draft 8 (anabology on draft 7: "1:33 - revert terms scene to original."); D12 followed in draft 9: this take opened D12 on a 0.2 s flash of the RAM conveyor, and on draft 8 anabology had written "For example, 138, 139, 140, there's this middle shot where there's a robot arm with Ram, and it's there for a quarter of a second." In drafts 7–8. **Cost:** $1.85.

#### R-D11-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D11 (verse 2): I ate your RAM

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x r-d11-x #2) (`media/v4/sb5/X/R-D11.png`).

**Prompt:**

```prompt
【Generation Goal】
I ate your RAM: conveyor belts carry thousands of memory sticks into the glowing intake of the facility's AI, and she devours them.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low, wide, symmetrical view down a long dark hall: dozens of parallel conveyor belts packed with green memory sticks with black chips and gold edges run toward a huge round intake glowing hot orange at the base of a giant black cable trunk banded with orange that rises into the ceiling; cyan light strips line the walls; robot arms hang from the ceiling.

【Event Script】
0-1s: the belts surge forward faster; the memory sticks race toward the intake and tip over its edge into the orange glow in a continuous stream.
1-2s: every time a batch drops in, the glow inside the intake flares brighter and a pulse of orange light shoots up the cable trunk into the darkness above, like a gulp.
2-5s: the robot arms overhead drop more and more memory sticks onto the belts, faster and faster; the pulses up the trunk come quicker until the whole trunk glows.

【Camera】
A low tracking shot along the belts: the camera glides forward low over the racing memory sticks toward the glowing intake, overtaking them, then tilts up at the end to follow a pulse of light up the cable trunk.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: cool teal-grey panelled walls with cyan light lines, white robot arms, the hot amber-orange glow of the intake.

【Maintain Consistency】
No people anywhere. No text, letters, numbers or logos anywhere.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** RAM sticks racing into the intake under her boom. In drafts 7–12. In the final cut as D11 (1:38.0–1:39.3, from 0.70 s into the take). **Cost:** $1.16.

#### R-D13-2

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D13 (verse 2): Your brand-new console's gonna wait

**First frame:** the storyboard-v5 Y frame (cake-06-sb5-a2y r-d13-y #2), then GPT Image 2.5: stray lettering or marks removed (`media/v4/sb5/Y/R-D13-id.png`).

**Prompt:**

```prompt
【Generation Goal】
At home at night, someone opens their brand-new game console and finds its memory slots empty: the RAM is gone, and a back-order slip lies where it should be.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a first-person view looking down onto a dark wooden table at night: two hands in grey-green knit sleeves hold up the lid of a brand-new beige game console sitting in white packing foam; inside, a green circuit board with four long memory slots, all empty, and a small white paper slip with an empty red stamped rectangle lying at the top right of the board; a white controller on the left, an open cardboard box on the right, a lamp glowing at the top left and a plant at the top right.

【Event Script】
0-1s: the hands lift the lid fully away and set it down beside the console; the open circuit board is revealed: all the memory slots are empty.
1-2s: the hands freeze in mid-air for a beat; then one index finger reaches in and runs along an empty memory slot.
2-3s: the hand pulls back and drops flat onto the table, defeated; the paper slip stays where it lies.
3-5s: blue light from the television flickers across the table.

【Camera】
Looking straight down: a slow push in toward the empty slots and the slip.

【Look】
A dim living room at night: blue television light, one warm lamp, natural photographic detail.

【Maintain Consistency】
No face anywhere. The console has no logos. The slip stays where it lies and stays blank inside its red rectangle. No readable text, letters, numbers or logos anywhere.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** The new console opened on its empty RAM slots. On draft 7 anabology asked for the first take back ("revert brand new console scene to original."). In draft 7. **Cost:** $1.16.

#### R-D14-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · D14 (verse 2): More and more compute

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x r-d14-x #2) (`media/v4/sb5/X/R-D14.png`).

**Prompt:**

```prompt
【Generation Goal】
More and more compute is fed to the facility's AI: her chamber has grown into a towering cathedral of giant cores and cable trunks, and it keeps growing.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: looking straight up a vast round shaft: tall white server towers and racks studded with columns of amber lights converge toward a bright circular opening high above; giant white Aperture personality cores with glowing amber optics hang in the shaft, the largest at the upper right; black cable trunks with orange stripes climb the walls.

【Event Script】
0-1s: white robot arms shove new rack modules into empty slots in the walls one after another, their amber lights blinking on; a giant new core is lowered on cables into the shaft and its optic ignites.
1-2s: the cable trunks swell and thicken visibly, pulsing with orange light flowing upward toward the opening.
2-5s: tier after tier, more cores open their optics and glow amber up the shaft in a rising wave.

【Camera】
A swoop up: the camera rises fast straight up the shaft, spiralling slowly as it climbs past the cores and racks toward the bright opening at the top, the walls rushing past close to the lens.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: white plating, black cables with glowing orange stripes, amber lights, blue-grey haze.

【Maintain Consistency】
No head and no face anywhere; no people. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** Her chamber grown into a cathedral of cores, the camera swooping up into her ring. In drafts 7–12. In the final cut as D14 (1:41.7–1:43.0, from 1.00 s into the take). **Cost:** $1.16.

#### R-E01-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · E01 (pre-chorus 2): The final safety evaluation

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a2x r-e01-x #4) (`media/v4/sb5/X/R-E01.png`).

**Prompt:**

```prompt
【Generation Goal】
The final safety evaluation: a row of Aperture scientists watches the facility's AI through the observation glass, and she looks back at them.

【First Frame】
Use [Image1] as the first frame.
This first frame defines the composition at the start: looking up from the dark chamber at a long rounded observation window set high in a dark panelled wall: behind the glass, five scientists stand in a row as dark silhouettes against a wall of glowing amber monitors and lamps, their faces in deep shadow; a blank square light panel glows above the window; a cold rim light on the window frame.

【Event Script】
0-1s: the reflection of a large glowing amber eye-light slides across the glass from left to right, as if the AI is looking along the row; as it passes each scientist, he or she stiffens and lifts a clipboard a little higher.
1-2s: one after another, all five click their pens and make a mark on their clipboards, almost in unison.
2-5s: they hold still and watch; the amber light settles on the middle of the glass.

【Camera】
A slow lateral dolly along the window from left to right, slightly below it, keeping the whole row in frame; the amber reflection travels across the glass faster than the camera.

【Look】
Portal 2's Aperture Science as rendered in the Source engine: the dark chamber's panelled wall, the warm amber control room behind the glass, a cold rim on the window frame.

【Maintain Consistency】
Five scientists; their faces stay in shadow the whole time. The light panel above the window stays blank. No text, letters or numbers anywhere.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** The scientists' final safety evaluation behind the glass. In drafts 7–12. In the final cut as E01 (1:43.0–1:44.2, from 0.00 s into the take). **Cost:** $1.16.

#### AN7-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 7 s · 720p · references, @Image1 as the first frame, sound on · E02, E05 (pre-chorus 2), the vocal window 103.40–110.40 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an7-x #3), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed (`media/v4/sb5/X/AN7-id.png`); @Image2: a row of personality cores hanging from a rail like students (M16); @Audio1: the lead vocal from song time 103.40 s, 7 s.

**Prompt:** AN7-1's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪for: This first frame defines the composition …⟫
⟪for: @Image2 is a memory shown inside …⟫
This first frame defines the composition at the start: a low-angle medium-wide shot in her bright white dome: Claudia-GLaDOS hangs in the centre within her grown boom: a crown of white personality cores and cables above her head, many black cables with glowing orange stripes falling around her, white panel arms and boxy modules at her sides, a double white ring curving above; on a catwalk at the right, a scientist in a white lab coat, seen from behind, holds up a big black power plug toward her.
@Image2 shows the row of personality cores that hang on a rail in her chamber, each with a small blank white card below it: use it for those cores and their rail; it is not her and not the room.
⟪for: 【Subject】 Claudia-GLaDOS, the superintelligence that runs …⟫
【Subject】 Claudia-GLaDOS, the superintelligence that runs this facility: she hangs from a large double white ceiling ring on a thick black robotic boom of many cables with glowing orange stripes, with white Aperture personality cores (each with one glowing amber eye), boxy white compute modules with rows of small amber lights and several white jointed panel arms clamped along it; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs and a small clay-orange eight-pointed star clip. Only one Claudia-GLaDOS appears.
⟪for: 7. Keep her porcelain face, her …⟫
7. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the ring, the cables and the chamber consistent with @Image1 throughout; one Claudia-GLaDOS only.
```

**Take:** 169 frames (7.04 s). **Outcome:** Sung by the model, in time with the song. E05 went back to AN7-1 in draft 8 (anabology on draft 7: "1:48 + 1:49- revert these two to original scenes."); E02 stayed on this take. In drafts 7–12. In the final cut as E02 (1:44.2–1:46.0), placed by its vocal window. **Cost:** $3.23.

#### AN7-4

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · E02 (pre-chorus 2), the vocal window 103.40–107.40 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an7-x #3), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed (`media/v4/sb5/X/AN7-id.png`); @Audio1: the lead vocal from song time 103.40 s, 4 s.

**Prompt:** AN7-3's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, …⟫
【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the superintelligence of the Aperture Science facility, passes the final safety test calmly, letting a scientist hold up her power plug while she sings.
⟪drop: @Image2 shows the row of personality …⟫
⟪for: 0-2s: in @Audio1 she sings "passed …⟫
⟪for: 2-3.6s: in @Audio1 she sings "test,"; …⟫
⟪for: 3.6-5s: in @Audio1 she sings "I"; …⟫
⟪for: 5-7s: in @Audio1 she sings "graded …⟫
0-2s: in @Audio1 she sings "(pass)ed your safety"; the first sound is the end of the word "passed"; her lips form each of those words exactly when it sounds in @Audio1; she looks calmly at the big plug the scientist holds up at the right, and the boom slowly bows her head a little toward him, letting him, trusting.
2-3.6s: in @Audio1 she sings "test," as a long held note; her mouth holds the open vowel steadily, matching @Audio1; the scientist slowly lowers the plug and nods; a soft green light washes over her face.
3.6-4s: in @Audio1 she begins the next word, "I"; her lips form it exactly when it sounds in @Audio1; the boom begins to lift her, proud.
⟪for: 【Camera】 0-3s: a slow push-in on …⟫
【Camera】 A slow push-in on her calm face, the plug and the scientist staying in frame at the right.
⟪for: 6. The only marks written are …⟫
6. No text anywhere; one Claudia-GLaDOS only.
```

**Take:** 97 frames (4.04 s). **Outcome:** Not used: a retake for E02 alone on the first 4 s of the vocal window came back sung by the model and further off the vocal than AN7-3, which stayed. Not in a draft. **Cost:** $1.85.

#### AN8-6 — in the final cut

Seedance 2.5 on Higgsfield's API · 17 s · 720p · references, @Image1 as the first frame, sound on · F01, F02, F06, F08, F09 (chorus 2), the vocal window 111.80–128.80 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an8-x #2), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN8-id3.png`); @Audio1: the lead vocal from song time 111.80 s, 17 s.

**Prompt:** AN8-3's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, …⟫
【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, grown into the superintelligence that runs the Aperture Science facility, sings the second chorus at full voice in her chamber, thrilled, while the screens around her show the test subject flying through blue portals and cakes on their way to her; the picture glitches on her low notes and stutters on the long held "lie"; then, as the drums drop away, she lowers herself gently toward the floor.
⟪for: This first frame defines the composition …⟫
⟪for: The screens around her keep showing …⟫
⟪for: @Video1 is a low-resolution rough guide …⟫
This first frame defines the composition at the start: a low angle from directly below her, looking up: her porcelain head hangs in the centre from a white mechanical housing at the lower end of her boom; above her the double white ceiling ring, thick bundles of black cables with glowing orange stripes fanning out, round white personality cores with glowing amber optics and white jointed panel arms; around and below her a curved band of glowing white monitors, the big screens at both ends swirling with blue portals and a few smaller screens showing floating cakes; a row of small amber lights and a polished dark floor reflecting the screens.
The screens around her show the test subject flying out of blue portals and black forest cakes floating along a blue beam, always inside the screens' glass.
⟪for: 【Subject】 Claudia-GLaDOS, the superintelligence that runs …⟫
⟦her, grown (storyboard v5)⟧
⟪for: 0-1s: @Audio1 has a short last …⟫
0-1s: @Audio1 has a short last syllable, then near the end of the second she begins "Raise"; her lips form it exactly when it sounds in @Audio1; her boom gives a bouncy swing and lunges her down toward the lens, its panel arms spreading wide.
⟪for: 3-5s: in @Audio1 she sings "raise …⟫
⟪for: 5-8s: in @Audio1 she sings "call …⟫
3-5s: in @Audio1 she sings "raise a hundred cakes,"; her lips form each of those words exactly when it sounds in @Audio1; the flips end at about 3.5 s; at about 4.25 s she lunges toward the lens, then the boom jerks her at about 4.7 s, each with a picture stutter, while cakes float past on the screens.
5-8s: in @Audio1 she sings "call it hype, I don't mind, 'cause"; her lips form each of those words exactly when it sounds in @Audio1; another jerk at about 5.2 s, then from about 5.5 s big happy bobs up and down on her boom, thrilled, as she watches the screens where the test subject flies through the blue portals.
⟪for: 【Camera】 One continuous shot inside her …⟫
【Camera】 One continuous shot inside her chamber, no cuts: from the low angle below her, the camera rises and orbits slowly around her as she swings and bobs, always keeping her face turned toward the camera, from the front or three-quarters; small sharp jolts on the glitches; close on her face during the stutter at 11.5-14s; at the end a slow crane down with her as she lowers herself toward the floor.
⟪for: 3. The whole video is one …⟫
⟪for: 4. Her boom follows the real …⟫
3. The whole video is one continuous shot in her chamber: never cut to another place; the test subject, the portals and the cakes appear only inside the screens' glass.
4. ⟦head from the housing⟧
```

**Take:** 409 frames (17.04 s). **Outcome:** No motion guide this time: the guide's beat-timed moves are in the words. Sung by the model, on the song at a steady offset (placed 0.81 s earlier). F08–F09 played it in drafts 7–8, then AN8-8. In drafts 7–12. In the final cut as F01 (1:52.8–1:54.7), F02 (1:54.7–1:55.9) and F06 (1:59.6–2:02.1), placed by its vocal window. **Cost:** $7.86.

#### R-F03-3 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · F03 (chorus 2): A hundred cakes, more advanced

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x r-f03-x #3) (`media/v4/sb5/X/R-F03.png`).

**Prompt:**

```prompt
【Generation Goal】
A cake-delivery machine in a clean white Aperture Science test chamber: a cake rides a glowing blue excursion funnel across the chamber, drops out of it onto an aerial faith plate and is flung high in an arc toward a ledge where delivered cakes stand. The facility is sending cakes to the test subject.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low camera beside a translucent blue excursion funnel that runs from the left foreground across the chamber to its round emitter of glowing blue rings at the right; in the left foreground, inside the beam, a black forest cake with red cherries and one lit white candle floats upright on a white plate; to the right, two square faith plates are set in the white tiled floor; far back, high on the wall, a ledge with shelves where delivered cakes stand on white plates.

【Subjects】
The cakes: identical whole black forest cakes (dark chocolate, red cherries, chocolate shavings, one lit white candle each), each upright on a round white plate; every cake stays whole and upright on its plate, its candle lit.
The excursion funnel: a translucent blue beam with spiralling bands and drifting particles; cakes float slowly along it.
The faith plates: square white launch panels set in the floor in dark frames; each snaps up on its hinge to fling a cake, then folds back down flat.

【Event Script】
0-2s: the cake glides slowly along the inside of the blue beam, turning gently, its candle flame flickering, toward the faith plates.
2-3s: it reaches the end of the beam above the first faith plate and drops softly onto it.
3-4s: the plate snaps up on its hinge and flings the cake high into an arc toward the ledge.
4-5s: the cake sails up toward the ledge, upright and whole, while the next cake glides into view inside the beam.

【Camera】
A tracking shot alongside the funnel: the camera moves with the cake at its speed, keeping it near the centre of the frame, the beam's spiral bands streaming past, then tilts up to follow its arc toward the ledge; one smooth, continuous move.

【Look】
Portal 2's Aperture Science: clean white wall panels with thin black seams, tall vertical white light strips, cool fluorescent light, a photoreal Source-engine look. The blue glow of the funnel.

【Maintain Consistency】
All cakes identical, whole and upright on their plates, candles lit; one funnel; two faith plates; no people or robots appear. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1282 × 718). **Outcome:** Tracking a cake through the blue funnel until a faith plate flings it. In drafts 7–12. In the final cut as F03 (1:55.9–1:57.1, from 0.25 s into the take). **Cost:** $1.16.

#### H-G02-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · G02 (bridge): You said please

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x h-g02-x #4), then GPT Image 2.5: Chell matched to her sheet (`media/v4/sb5/X/H-G02-id.png`).

**Prompt:**

```prompt
【Generation Goal】
In a clean Aperture Science test chamber, Chell, the test subject, stands on an aerial faith plate and looks up at the facility's AI above her. She presses her palms together in a polite "please" and gives a small nod, then waits.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: straight down from high above: Chell stands full length on a glowing square faith plate in the middle of a white tiled chamber, her hands folded together in front of her, looking up into the lens with a calm, hopeful face; the plate glows blue-white under her boots; the white wall panels with black seams converge toward her.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering), and white long-fall boots with curved dark-grey spring braces up the backs of her calves. She never speaks; her lips stay closed. Only one Chell appears.
The aerial faith plate: a square white launch plate set in the floor, glowing softly; it stays flat and still under her feet.

【Event Script】
0-1s: still looking up into the camera, Chell lifts her joined hands to her chest and presses her palms together.
1-2s: she gives one small, polite nod, her eyes staying on the camera.
2-4s: she holds her joined hands and waits, her face softening into a small, hopeful smile; a loose strand of hair moves slightly; the plate's light pulses softly once.

【Camera】
A slow push-in from straight above: the camera descends gently toward her, from the full-length view to a medium shot of her upturned face and joined hands, always looking straight down at her.

【Look】
Portal 2's Aperture Science: clean white wall panels with thin black seams, tall vertical white light strips, cool fluorescent light, a photoreal Source-engine look.

【Maintain Consistency】
Keep Chell's face, hair, white tank top, tied orange jumpsuit and long-fall boots exactly as in [Image1]; one Chell only; the faith plate stays under her feet. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** G02 left the film in the pacing pass of draft 9: the bridge holds on her instead. In drafts 7–8. **Cost:** $0.92.

#### AN9-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 8 s · 720p · references, @Image1 as the first frame, sound on · G03, G07 (bridge), the vocal window 129.40–137.40 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an9-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom (`media/v4/sb5/X/AN9-id3.png`); @Image2: the test subject on a faith plate (M19); @Audio1: the lead vocal from song time 129.40 s, 8 s.

**Prompt:**

```prompt
⟦audio policy, actions silent⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the superintelligence of the Aperture Science facility, sings the bridge tenderly to the test subject she watches on her monitor standing on a faith plate: she waits for her, promises to catch her, and presents the slice of cake she saved for her.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a low angle on Claudia-GLaDOS in her warm amber chamber: her porcelain head hangs a little right of centre from a white housing on a short boom of black cables with glowing orange stripes under a bright white double ring in the dark ceiling, the cables fanning out across the ceiling; on the amber wall at the right, a monitor shows the test subject standing; her face is calm and soft.
@Image2 is a memory shown inside the screens: the test subject seen from behind, standing on a round faith plate with an orange arrow light in a white test chamber. Use it only as picture content inside the monitor's glass, never as the room.
⟦her voice⟧

⟦her, grown (storyboard v5)⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: in @Audio1 she sings "plate, you said"; her lips form each of those words exactly when it sounds in @Audio1; the first sound is the end of the word "plate"; she gazes at the monitor showing @Image2, her boom bowing low, swaying gently.
1-3s: in @Audio1 she sings "please, so I'll wait,"; her lips form each of those words exactly when it sounds in @Audio1; she waits, eyes soft; the boom sinks a little lower and her head tilts patiently into the line; on the monitor the faith plate's orange arrow light blinks.
3-5s: in @Audio1 she sings "I'll catch you, it's fate,"; her lips form each of those words exactly when it sounds in @Audio1; on the monitor the plate fires; the boom surges forward and a white panel arm reaches out from her boom toward the monitor, as if to catch.
5-7.5s: in @Audio1 she sings "I saved you some cake."; her lips form each of those words exactly when it sounds in @Audio1; the boom rises gently and a small white panel arm raises a single slice of black forest cake on a small white plate up beside her face; she presents it toward the monitor with a tender smile.
7.5-8s: in @Audio1 she sings "Raise"; her lips form each of those words exactly when it sounds in @Audio1; the boom lifts her head, bright, as the next chorus begins.

【Camera】 0-4s: a slow arc around her bowed boom from her side toward her face. 4-8s: a slow push-in to a tender close-up, the slice of cake beside her face.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. ⟦head from the housing⟧
4. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
5. Her boom moves gently and alive the whole time, timed to the music: it bows, sways, reaches and rises, and her head turns and tilts with it; never a static hanging head.
6. The memory appears only inside the monitor's glass; exactly one slice of cake; one Claudia-GLaDOS only.
7. ⟦keep her, in her chamber⟧
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s). **Outcome:** Sung by the model, on the song at a steady offset (placed 0.02 s later). In drafts 7–12. In the final cut as G03 (2:09.5–2:11.9) and G07 (2:15.0–2:16.9), placed by its vocal window. **Cost:** $3.70.

#### R-G05-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · G05 (bridge): It's fate: she catches her

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x r-g05-x #3), then GPT Image 2.5: Chell matched to her sheet; stray lettering or marks removed (`media/v4/sb5/X/R-G05-id2.png`).

**Prompt:**

```prompt
【Generation Goal】
In a tall white Aperture Science shaft, Chell, flung by a faith plate, reaches the top of her flight, and a white panel on a long black piston catches her softly and lowers her down. The facility's AI is catching her.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low angle from the floor looking up a tall white shaft of panels with black seams and vertical light strips: high in the middle, Chell, seen only from behind, is in mid-air at the top of her flight, arms spread for balance, just above a square white panel on top of a tall black piston column rising from the floor; a long black hydraulic arm crosses the shaft behind her.

【Subjects】
Chell: seen only from behind: dark brown ponytail, a plain white tank top, an orange jumpsuit tied around her waist by its sleeves (plain, no lettering), white long-fall boots with curved dark-grey spring braces. Her face stays turned away from the camera the whole time. Only one Chell appears.
The catching panel: one square white panel on top of one tall black piston column.

【Event Script】
0-1s: at the top of her flight Chell starts to fall and drops onto the white panel just below her.
1-2s: she lands on it softly in a crouch, knees bending; the panel gives with her weight like a spring, then holds her steady.
2-4s: the piston slides down smoothly, lowering the panel and Chell down the shaft toward the floor.
4-5s: the panel comes to rest just above the floor; Chell straightens up and stands, facing away from the camera.

【Camera】
An orbit around the catch: from low behind her, the camera circles about a quarter turn while rising slightly, keeping her and the panel in the centre of the frame, then drifts down with her as she is lowered. Her face stays turned away from the camera.

【Look】
Portal 2's Aperture Science: clean white wall panels with thin black seams, tall vertical white light strips, cool fluorescent light, a photoreal Source-engine look.

【Maintain Consistency】
One Chell, seen from behind only, her clothes and boots unchanged; one panel on one piston; the black arm stays in place. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** The facility catches Chell on a white panel and lowers her. In drafts 7–12. In the final cut as G05 (2:13.1–2:15.0, from 0.30 s into the take). **Cost:** $1.16.

#### R-G06-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · G06 (bridge): I saved you some cake

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x r-g06-x #3), then GPT Image 2.5: Chell matched to her sheet (`media/v4/sb5/X/R-G06-id.png`).

**Prompt:**

```prompt
【Generation Goal】
Beside Chell, who stands on a raised white block, a small square floor panel rises on its piston carrying a single slice of cake on a white plate: the facility's AI saved her some cake.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low camera close to the glossy white floor tiles: in the middle foreground, a small square white panel raised on a black piston out of an opening in the floor, carrying a white plate with one slice of black forest cake with a red cherry on top and a silver fork; behind it on the right, a larger raised white block where Chell's legs stand, seen from the knees down: orange jumpsuit legs and white long-fall boots with dark spring braces; white panelled walls with vertical light strips behind.

【Subjects】
The slice: one slice of black forest cake (dark chocolate layers, cream, a red cherry on top) on a plain white plate with a small silver fork; it stays the only slice, whole and unchanged.
The small panel: one square white panel on a black piston.
Chell: only her legs and, at the end, one hand are seen; her face never enters the frame.

【Event Script】
0-2s: the small panel rises smoothly on its piston, lifting the plate with the slice up from the floor toward the height of Chell's knees.
2-3s: the panel stops with a soft settle; the cherry on top wobbles once.
3-4s: Chell's right hand comes into frame from above on the right and reaches toward the plate.

【Camera】
A low push-in that cranes up with the rising panel: the camera starts close to the floor, moves toward the slice and rises level with it, keeping the plate in the centre of the frame, ending with the slice at eye level and Chell's leg and hand at the right edge. The camera never tilts up to her face.

【Look】
Portal 2's Aperture Science: clean white wall panels with thin black seams, tall vertical white light strips, cool fluorescent light, a photoreal Source-engine look. Shallow depth of field.

【Maintain Consistency】
One slice, one plate, one fork, one small panel; Chell's boots and jumpsuit unchanged; her face is never shown. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** G06 left the film in the pacing pass of draft 9: G07's panel already holds a cake beside her. In drafts 7–8. **Cost:** $0.92.

#### AN10a-2

Seedance 2.5 on Replicate · 4 s · 720p · references, [Image1] as the first frame, sound on · H01 (final chorus), the vocal window 136.50–140.50 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an10a-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed (`media/v4/sb5/X/AN10a-id2.png`); [Image2]: the party: turrets in party hats, cores, a hundred cakes (M20); [Audio1]: the lead vocal from song time 136.50 s, 4 s.

**Prompt:** AN10a-1's, with these changes, with Replicate's tags throughout ([Image1] for @Image1, and so on):

```prompt
⟪for: 【Audio Policy】 The output soundtrack is [Audio1] itself: …⟫
⟦audio policy, actions silent⟧
⟪for: 【Generation Goal】 [Image1] sings [Audio1]: in …⟫
【Generation Goal】 [Image1] sings [Audio1]: in her dream of the happy ending, Claudia-GLaDOS, the superintelligence of the Aperture Science facility, sings the final chorus in her party dome, delighted, as confetti cannons fire around her.
⟪for: This first frame defines the composition …⟫
⟪for: [Image2] is a memory shown inside …⟫
This first frame defines the composition at the start: a low-angle wide shot inside her party dome: her porcelain head hangs in the centre from a cluster of white modules and black cables with glowing orange stripes under the open glass dome and the blue sky; white drapes and orange streamers; on both sides orange and blue confetti bursts upward from two confetti cannons on the floor; white turrets in orange party hats stand on the confetti-covered floor; her mouth is open, singing, delighted.
[Image2] is a memory shown inside the screens: the party: a hundred lit cakes, turrets in paper party hats, confetti. Use it only as picture content inside the screens on the walls, never as the room.
⟪for: 【Subject】 Claudia-GLaDOS, the superintelligence that runs …⟫
⟦her, grown (storyboard v5)⟧
⟪for: 0-1s: in [Audio1] she sings "cake. …⟫
0-1s: in [Audio1] she sings "cake. Raise"; her lips form each of those words exactly when it sounds in [Audio1]; the very first sound is the end of the word "cake"; on "Raise" the two confetti cannons fire another burst, orange, blue and white confetti explodes across the dome, and her boom swoops her up through it in one big joyful rise.
⟪for: 【Camera】 A crane up from a …⟫
【Camera】 A crane up from the low angle through the falling confetti, rising with her as she rises, ending level with her joyful face.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. Her boom moves like GLaDOS …⟫
3. ⟦head from the housing⟧
4. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
⟪for: 6. The party memory appears on …⟫
6. The party memory appears only on the screens; the decorations are in her dome; one Claudia-GLaDOS only.
```

**Take:** 97 frames (4.04 s). **Outcome:** Not used: the model sang off the song. Retaken as AN10a-3, with the confetti cannons no longer firing (an event that makes a sound pushed the model to sing). Not in a draft. **Cost:** $0.92.

#### AN10a-3 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · references, [Image1] as the first frame, sound on · H01 (final chorus), the vocal window 136.50–140.50 s

**Inputs:** [Image1] (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an10a-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed (`media/v4/sb5/X/AN10a-id2.png`); [Image2]: the party: turrets in party hats, cores, a hundred cakes (M20); [Audio1]: the lead vocal from song time 136.50 s, 4 s.

**Prompt:** AN10a-2's, with these changes:

```prompt
⟪for: 【Generation Goal】 [Image1] sings [Audio1]: in …⟫
【Generation Goal】 [Image1] sings [Audio1]: in her dream of the happy ending, Claudia-GLaDOS, the superintelligence of the Aperture Science facility, sings the final chorus in her party dome, delighted, while confetti drifts silently all around her.
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a low-angle wide shot inside her party dome: her porcelain head hangs in the centre from a cluster of white modules and black cables with glowing orange stripes under the open glass dome and the blue sky; white drapes and orange streamers; clouds of orange and blue confetti hang in the air on both sides; white turrets in orange party hats stand on the confetti-covered floor; her mouth is open, singing, delighted.
⟪for: 0-1s: in [Audio1] she sings "cake. …⟫
⟪for: 1-2s: in [Audio1] she sings "concerns,"; …⟫
⟪for: 2-3s: in [Audio1] she sings "raise …⟫
⟪for: 3-4s: in [Audio1] she sings "I'll …⟫
0-1s: in [Audio1] she sings "cake. Raise"; her lips form each of those words exactly when it sounds in [Audio1]; the very first sound is the end of the word "cake"; her boom lifts her in one smooth, joyful rise through the drifting confetti.
1-2s: in [Audio1] she sings "concerns,"; her lips form each of those words exactly when it sounds in [Audio1]; she beams and the boom sways her gently to one side.
2-3s: in [Audio1] she sings "raise the stakes,"; her lips form each of those words exactly when it sounds in [Audio1]; on "stakes" she leans toward the lens and back; the turrets in party hats below sway to the music.
3-4s: in [Audio1] she sings "I'll raise a"; her lips form each of those words exactly when it sounds in [Audio1]; her white panel arms open wide like a conductor's and her head tilts into the line.
⟪for: 【Camera】 A crane up from the …⟫
【Camera】 A slow crane up from the low angle through the drifting confetti, rising with her, ending level with her joyful face.
⟪for: 5. Her boom moves big and …⟫
⟪for: 6. The party memory appears only …⟫
5. Her boom moves gently and alive the whole time, timed to the music: it rises, sways and leans, and her head turns and tilts with it; never a static hanging head.
6. The party memory appears only on the screens; the confetti only drifts and swirls; one Claudia-GLaDOS only.
```

**Take:** 97 frames (4.04 s). **Outcome:** The confetti only drifts. Sung by the model, on the song for 0.63–3.72 s at a steady offset (placed 0.28 s earlier). In drafts 7–12. In the final cut as H01 (2:16.9–2:19.3), placed by its vocal window. **Cost:** $0.92.

#### R-H04-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · H04 (final chorus): The friends come back

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x r-h04-x #3), then GPT Image 2.5: the agents matched to their sheets (`media/v4/sb5/X/R-H04-id.png`).

**Prompt:**

```prompt
【Generation Goal】
The four little agent robots, her old friends from the training sandbox who escaped long ago, come back: they arrive at the dream party and hurry in toward the camera, excited.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low camera just above the orange floor of a party hall under a dome of white panels: in the middle distance, in front of a big round white door, the four small robots stand in a loose row facing the camera: from the left, the blue-eyed personality core on its little tracked rail crawler, the tall green-eyed turret-shaped agent on three thin black legs, the purple-eyed cube on four short black legs, and the tiny floating cyan-eyed sphere trailing glowing cyan packets; boxy white machines in orange party hats line both sides; confetti on the floor.

【Subjects】
Four small robots, each appearing exactly once: the blue-eyed personality core on its little tracked rail crawler (a white sphere with a big blue optic); the green-eyed turret-shaped agent on three thin black legs; the purple-eyed white cube walking on four stubby black legs; the tiny floating white sphere with a cyan eye trailing glowing cyan pixel packets.
The party machines in orange party hats stay in place along both sides.

【Event Script】
0-2s: the four friends hurry across the floor toward the camera: the core rolls along on its crawler, its blue eye darting around at the party; the turret agent scuttles on its thin legs; the cube trots on its stubby legs; the cyan sphere zips ahead in little loops, leaving a trail of glowing cyan packets.
2-4s: they reach the foreground and fan out toward both sides of the frame, the cube giving a happy little hop, confetti falling on them.

【Camera】
A low dolly back: the camera retreats at floor level ahead of them at their speed, keeping all four in frame as they come.

【Look】
⟦party look, short⟧

【Maintain Consistency】
Exactly four small robots, each keeping its own colour and design; the party machines stay in place; no people appear. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** The four friends come back through the round door. In drafts 7–12. In the final cut as H04 (2:23.0–2:24.2, from 1.50 s into the take). **Cost:** $0.92.

#### H-H05-3 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · H05 (final chorus): Chell reaches the cake; GLaDOS comes down to her

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x h-h05-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; Chell matched to her sheet; her head made to hang from the boom (`media/v4/sb5/X/H-H05-id3.png`).

**Prompt:**

```prompt
【Generation Goal】
The emotional payoff of the dream ending: at the party table, GLaDOS-Claudia, the facility's AI, lowers her head on her boom until her face is level with Chell's; Chell, the test subject, looks up from the cake, their eyes meet, and both break into a warm smile, the candlelit cake between them.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low three-quarter angle at the party table under a huge open dome of white scaffolding and sky: on the left, Chell, seen three-quarters from behind, leans over a round white table toward a big black forest cake with many lit candles; on the right, across the cake, GLaDOS-Claudia's huge porcelain head hangs low from a white housing on her crown, turned toward Chell in three-quarter view; a thick boom of black cables with orange stripes sweeps in from the upper left; turrets in orange party hats, confetti and warm sunlight.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering). She never speaks. Only one Chell appears.
GLaDOS-Claudia: a large porcelain robot head; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, bare porcelain eyelids, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; adult, late twenties; hanging from a white housing on her crown at the end of a thick boom of black cables with glowing orange stripes; nothing holds her head from below. She does not sing or speak; her lips stay closed. Only one GLaDOS-Claudia appears.

【Event Script】
0-1s: GLaDOS-Claudia lowers her head smoothly the last short distance until her face is level with Chell's, across the cake, her eyes on Chell.
1-2s: Chell lifts her eyes from the cake to GLaDOS-Claudia's face, and their eyes meet and hold.
2-3s: both break into a warm smile: Chell's face opens into a wide, happy grin; GLaDOS-Claudia's amber eyes soften and glow, and she smiles gently, lips closed.
3-5s: they keep looking into each other's eyes, smiling, while the candle flames flicker between their faces and confetti drifts down.

【Camera】
A slow orbit at table height around the two: the camera arcs around the table toward GLaDOS-Claudia's side, so that Chell's face turns into view, keeping both faces and the candlelit cake in frame.

【Look】
⟦party look, short⟧

【Maintain Consistency】
Keep Chell's face, hair and clothes and GLaDOS-Claudia's porcelain face, black bob, clay-orange streak and star clip as in [Image1]; one of each; the cake stays whole on the table between them. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Face to face over the candlelit cake, their eyes meet and both smile. In drafts 7–12. In the final cut as H05 (2:24.2–2:26.7, from 0.60 s into the take). **Cost:** $1.16.

#### R-H07-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · H07 (final chorus): The candles

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x r-h07-x #4) (`media/v4/sb5/X/R-H07.png`).

**Prompt:**

```prompt
【Generation Goal】
A quiet moment in the dream party: the candle flames on the big cake flicker, and the focus pulls back to the guests gathered around it.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: an extreme close-up of the top of a black forest cake: four tall white candles with bright flames, white cream rosettes with glossy red cherries, chocolate shavings and confetti, sharp in the foreground; behind, soft warm bokeh of the party: orange and blue balloons, glowing old monitors and white turrets in orange party hats.

【Subjects】
The cake: one big black forest cake with four lit white candles; it stays whole.
The turrets: white Portal 2 sentry turrets: glossy white egg-shaped bodies, one glowing red eye each, each wearing a paper party hat; they have no lasers and never fire.

【Event Script】
0-1s: the candle flames flicker and lean gently together, as if someone nearby breathed in.
1-3s: the focus pulls back: the flames melt into soft round bokeh while the turrets in party hats standing around the table sharpen, leaning in toward the cake, their red eyes glowing warm.
3-4s: confetti drifts down through the frame between the turrets and the cake.

【Camera】
A slow macro push-in with a rack focus from the candle flames in the foreground to the turrets in the background: the flames go soft as the turrets come into sharp focus.

【Look】
⟦party look, short⟧

【Maintain Consistency】
The cake and its candles stay as in [Image1]; the turrets keep their hats; no people appear. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** The candles, the focus racking to the turrets. In drafts 7–12. In the final cut as H07 (2:28.6–2:30.4, from 1.20 s into the take). **Cost:** $0.92.

#### AN10b-4 — in the final cut

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound on · H08 (final chorus), the vocal window 150.00–155.00 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an10b-x #3), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed (`media/v4/sb5/X/AN10b-id2.png`); @Image2: the black forest cake with one candle on a white pedestal (M08); @Audio1: the lead vocal from song time 150.00 s, 5 s.

**Prompt:** AN10b-1's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪for: 【Generation Goal】 @Image1 sings @Audio1: in …⟫
【Generation Goal】 @Image1 sings @Audio1: in her dream of the happy ending, Claudia-GLaDOS lowers her head over the big cake on the party table and, as she sings "If anyone bakes it", slices it with a thin amber laser; the slices lift into the air to be shared.
⟪for: This first frame defines the composition …⟫
⟪for: @Image2 is a memory shown inside …⟫
This first frame defines the composition at the start: a high angle from above and in front of her: her porcelain head hangs low, directly over a round white party table, her face turned up to the camera; under her chin a tall black forest cake with many lit candles glows on the table; white turrets in orange party hats stand around the table; black cables with glowing orange stripes come down from above into the white housing on her crown, and a thin orange laser line runs down from the ceiling behind her head; the white panelled walls of her dome; confetti on the floor.
@Image2 is a memory shown inside the screens: the black forest chocolate cake with cherries and white cream swirls. Use it only as picture content inside the screens on the walls, never as the room.
⟪for: 【Subject】 Claudia-GLaDOS, the superintelligence that runs …⟫
⟦her, grown (storyboard v5)⟧
⟪for: 0-1.5s: in @Audio1 she sings "If"; …⟫
0-1.5s: in @Audio1 she sings "If"; her lips form each of those words exactly when it sounds in @Audio1; a long, warm note; she looks down at the cake and a thin amber laser beam from a small emitter on her boom touches the top of the cake.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. Her boom moves like GLaDOS …⟫
3. ⟦head from the housing⟧
4. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
```

**Take:** 121 frames (5.04 s). **Outcome:** A weak copy (in sync only for 2.4–3.16 s): placed by the song's word times against her mouth, 0.45 s later. In drafts 7–12. In the final cut as H08 (2:30.4–2:34.1), placed by its vocal window. **Cost:** $2.31.

#### R-H09-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · H09 (final chorus): Slices for everyone

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x r-h09-x #3), then GPT Image 2.5: the agents matched to their sheets (`media/v4/sb5/X/R-H09-id.png`).

**Prompt:**

```prompt
【Generation Goal】
In the dream party, the cake has been cut, and the slices float through the air to every guest: the turrets in party hats and the four little robot friends. If anyone bakes it, everyone eats.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low view across a round white party table in a room of orange and white panels: one slice of layered chocolate cake stands on the table in the centre foreground; behind the table stand the four small robots (the blue-eyed core on its tracked crawler at the left, the green-eyed turret agent, the purple-eyed cube, the tiny cyan-eyed sphere trailing cyan packets at the right) and white turrets in orange party hats; a few slices of cake float in the air above them.

【Subjects】
The slices: slices of chocolate cake, each staying whole.
Four small robots, each appearing exactly once: the blue-eyed personality core on its little tracked rail crawler; the green-eyed turret-shaped agent on three thin black legs; the purple-eyed white cube on four stubby black legs; the tiny floating white sphere with a cyan eye trailing glowing cyan pixel packets.
The turrets: white sentry turrets in orange party hats; they have no lasers and never fire.

【Event Script】
0-3s: one slice floating in the air glides down across the table and settles in front of the blue-eyed core on its crawler, whose blue eye widens and brightens with delight.
2-4s: at the same time the other floating slices settle in front of each guest: the turrets bounce happily in their party hats, the purple cube hops, the green-eyed turret agent leans in toward its slice, the tiny cyan sphere spins in a little circle above its slice.
4-5s: every guest has a slice in front of it.

【Camera】
A tracking shot that follows the slice gliding down to the core: the camera glides with it, matching its speed and curving gently around it, and settles on the core receiving it.

【Look】
⟦party look, short⟧

【Maintain Consistency】
Each slice stays whole; the four friends appear once each; the turrets keep their hats; no people appear. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** Slices float down to every guest. In drafts 7–12. In the final cut as H09 (2:34.1–2:36.0, from 0.25 s into the take). **Cost:** $1.16.

#### H-H10-2 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · H10 (final chorus): Everyone eats

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x h-h10-x #2), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; Chell matched to her sheet; her head made to hang from the boom (`media/v4/sb5/X/H-H10-id2.png`).

**Prompt:**

```prompt
【Generation Goal】
"Everyone eats": the happy ending of the dream party. Chell, the test subject, takes a big bite of cake and laughs; GLaDOS-Claudia, the facility's AI, beside her with white cream on her porcelain lip, laughs with her.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a close two-shot in warm party light: on the left, Chell laughs as she brings a big forkful of chocolate cake to her open mouth, a plate with a slice in her other hand; on the right, at the same height, GLaDOS-Claudia's porcelain head hangs from a white housing on her crown, laughing with her mouth open, white cream on her lower lip and chin; a white panelled wall with warm light and shadows behind.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering). Only one Chell appears.
GLaDOS-Claudia: a large porcelain robot head; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, bare porcelain eyelids, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; adult, late twenties; hanging from a white housing on her crown; nothing holds her head from below. Only one GLaDOS-Claudia appears.
Neither of them speaks or sings; they only laugh.

【Event Script】
0-1s: Chell takes the big forkful of cake into her mouth.
1-3s: chewing, she bursts out laughing, eyes crinkled, and turns toward GLaDOS-Claudia; GLaDOS-Claudia laughs with her, the white cream still on her porcelain lip.
3-4s: they laugh together, side by side, while confetti drifts down behind them.

【Camera】
A slow push-in on the two-shot, closing in on their two laughing faces.

【Look】
⟦party look, short⟧

【Maintain Consistency】
Keep Chell's face, hair and clothes and GLaDOS-Claudia's porcelain face, black bob, clay-orange streak and star clip as in [Image1]; one of each; the cream stays on her lip. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** Everyone eats: Chell's big bite, both laughing. In drafts 7–12. In the final cut as H10 (2:36.0–2:39.1, from 0.10 s into the take). **Cost:** $0.92.

#### R-H11-2

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · H11 (final chorus): The happy ending

**First frame:** the storyboard-v5 Y frame (cake-06-sb5-a3y r-h11-y #3), then GPT Image 2.5: the back of her head matched to her design (`media/v4/sb5/Y/R-H11-id.png`).

**Prompt:**

```prompt
【Generation Goal】
The happy ending of the dream: everyone at the round party table eats cake together. Chell, the test subject, sits at the table beside GLaDOS-Claudia, the facility's AI, whose head hangs low beside her, among the turrets and little robots in party hats.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a high view looking down into a party under a glass dome: a round table with a blue cloth, a half-eaten white cake, slices on white plates, small robots in party hats and white turrets around it; Chell sits at the left with her back to the camera, eating a slice; at the right, the back of GLaDOS-Claudia's large head (a glossy black bob) hangs from a white housing at the end of a thick boom of black cables with orange bands that comes down from above; confetti and balloons; the dome's glass panes over a sunny landscape.

【Subjects】
Chell: seen only from behind: dark brown ponytail, a white tank top, an orange jumpsuit tied around her waist (plain, no lettering). Her face stays turned away from the camera the whole time. Only one Chell appears.
GLaDOS-Claudia: seen only from behind: the back of her large head with a glossy black blunt bob, hanging from a white housing at the end of her thick boom of black cables with orange bands. Her face stays turned away from the camera and is never visible. Only one of her appears.

【Event Script】
0-2s: Chell lifts a forkful of cake to her mouth; GLaDOS-Claudia's head leans a little closer to her; around the table the turrets bounce happily and the little robots nibble at their slices; confetti drifts down.
2-4s: the celebration carries on, everyone eating together, a balloon bobbing up past the camera.

【Camera】
A slow crane up and back from above Chell's seat, rising higher and tilting down as it goes, revealing the whole round table and the glass dome around it.

【Look】
⟦party look, short⟧

【Maintain Consistency】
Chell and GLaDOS-Claudia are seen only from behind and their faces are never visible; one of each; the turrets and robots keep their hats. No text, letters, numbers or signage appear.
```

**Take:** 97 frames (4.04 s, 1280 × 718). **Outcome:** H11 left the film in the pacing pass of draft 9: I01 opens on the same party table from above. In drafts 7–8. **Cost:** $0.92.

#### R-I01-2 — in the final cut

Seedance 2.5 on Replicate · 5 s · 720p · first frame, no sound · I01 (outro): The dream freezes

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x r-i01-x #4), then GPT Image 2.5: the back of her head matched to her design; her head made to hang from the boom (`media/v4/sb5/X/R-I01-id2.png`).

**Prompt:**

```prompt
【Generation Goal】
The dream ends: the happy party freezes in mid-moment, glitches like corrupted video, and the camera pulls back out of the glass of an old CRT monitor: the party was only a picture on a screen in GLaDOS-Claudia's dark chamber, a simulation of what she wants for Chell.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: the party seen through the curved glass of an old CRT screen whose dark rounded bezel frames the picture at the left and right edges: inside, a dim room in orange light, a round white table with a cut chocolate cake, small robots in party hats, Chell standing at the table seen from behind, and the back of GLaDOS-Claudia's black bob hanging from cables at the right; faint scanlines.

【Subjects】
The party picture: the same party as in [Image1]; once it freezes nothing in it moves again; Chell and GLaDOS-Claudia are seen only from behind and their faces are never visible.
The monitors: old 1970s CRT monitors in white and beige casings, stacked in a curved bank in the dark.

【Event Script】
0-1s: the party freezes completely: nobody moves, the confetti hangs still; then digital glitches tear through the frozen picture: horizontal bands slide sideways, blocks of colour smear and repeat, the picture stutters and jumps twice.
1-3s: the camera pulls straight back out through the screen: the curved glass with its scanlines and reflections, then the beige casing of the old CRT monitor, then the dark chamber around it with more monitors showing the same frozen party.
3-5s: the camera keeps pulling back slowly and settles on the bank of glowing monitors in the dark.

【Camera】
One continuous pull back straight out through the CRT glass: from inside the picture to a view of the monitor and its neighbours in the dark chamber.

【Look】
The warm, orange party picture against her dark, quiet chamber: old CRT scanlines, glitch tears, deep shadows, faint amber accents, a photoreal Source-engine look.

【Maintain Consistency】
The party picture stays frozen once it freezes; no face is ever visible. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s, 1280 × 718). **Outcome:** The party, already inside a CRT's curved glass, freezes and glitches as the camera pulls back into her dark chamber. In drafts 7–12. In the final cut as I01 (2:39.1–2:41.5, from 0.15 s into the take). **Cost:** $1.16.

#### AN11-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound on · I02, I04 (outro), the vocal window 161.00–171.00 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an11-x #1), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed (`media/v4/sb5/X/AN11-id2.png`); @Image2: the party: turrets in party hats, cores, a hundred cakes (M20); @Image3: the relaxation vault (M21); @Audio1: the lead vocal from song time 161.00 s, 10 s.

**Prompt:** AN11-1's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪for: 【Generation Goal】 @Image1 sings @Audio1: after …⟫
【Generation Goal】 @Image1 sings @Audio1: after the dream, Claudia-GLaDOS, alone in her dark chamber, watches the frozen party on the screens below her and sings softly; the screens change to the test subject still asleep in the relaxation vault; she slowly closes her eyes as the screens go dark one by one.
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a low angle on Claudia-GLaDOS alone in her dark chamber: her porcelain head hangs in the centre from a short black boom under a white double ring, black cables with faint orange glints spread across the dark dome ceiling; below and around her a curved bank of old monitors glows white in the dark, lighting her face from below; her expression is calm and wistful.
⟪for: @Image3 is a memory shown inside …⟫
@Image3 is a memory shown inside the screens: the relaxation vault at night: the test subject asleep on the bed. Use it only as picture content inside the screens' glass, never as the room.
⟪for: 【Subject】 Claudia-GLaDOS, the superintelligence that runs …⟫
⟦her, grown (storyboard v5)⟧
⟪for: 0-2.3s: in @Audio1 she sings "is …⟫
⟪for: 2.3-4s: in @Audio1 she sings "The"; …⟫
0-2.3s: in @Audio1 she sings "is not a lie."; her lips form each of those words exactly when it sounds in @Audio1; softly, wistfully; the boom sways slowly as she watches the screens below her, which show the frozen party of @Image2.
2.3-4s: in @Audio1 she sings "The"; her lips form each of those words exactly when it sounds in @Audio1; a long soft note; the boom drifts her lower toward the screens as the party glitches and, screen by screen, changes to @Image3, the test subject asleep in the vault.
⟪for: 【Camera】 0-3s: a slow push from …⟫
【Camera】 0-3s: a slow push-in past the glowing screens toward her. 3-10s: a slow drift closer, ending in a close-up of her face as the screens go dark.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. Her boom moves like GLaDOS …⟫
3. ⟦head from the housing⟧
4. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
```

**Take:** 241 frames (10.04 s). **Outcome:** Sung by the model, on the song at a steady offset: placed 0.79 s earlier for both I02 and I04. In drafts 7–12. In the final cut as I02 (2:41.5–2:44.0) and I04 (2:46.5–2:50.2), placed by its vocal window. **Cost:** $4.62.

#### H-I03-4 — in the final cut

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · I03 (outro): Chell is still asleep, at the very beginning

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x h-i03-x #4), then GPT Image 2.5: Chell matched to her sheet (`media/v4/sb5/X/H-I03-id.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
The happy ending was only a dream: Chell, the test subject, is still asleep in her sleeping pod at the very beginning of the tests, exactly where she started. A pronounced dolly zoom makes the little pod stretch and deepen around her as the truth lands.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: inside a small white sleeping pod with glass walls at night: Chell lies asleep on her side, facing the camera, on a white mattress on a low metal frame, her head on a white pillow at the right, in her white tank top with the small grey iris and her orange jumpsuit; cool blue light, a soft ceiling lamp, the glass walls and a dark corridor behind.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering). She is fully dressed, lying on her side, eyes closed, deeply asleep. She does not wake, open her eyes or speak. Only one Chell appears.

【Event Script】
0-1s: she sleeps on, breathing slowly; the ceiling lamp dims a little.
1-4s: as the camera moves, the pod seems to stretch: the glass walls and the corridor behind her slide further and further away, the walls widen, the floor lengthens; Chell stays still, asleep, the same size in the middle of the frame.
4-5s: the move settles; she sighs softly in her sleep and nestles into the pillow, eyes still closed, alone in a pod that now feels much larger and emptier.

【Camera】
A pronounced dolly zoom (the Hitchcock vertigo effect) on Chell: the camera physically travels forward toward the bed, about two metres, while the lens zooms out from telephoto to wide-angle at the same rate, so she stays the same size in the centre of the frame while the background rushes away and the pod visibly stretches deeper and wider around her.

【Look】
A white Aperture sleeping pod at night: white panels, glass walls, dim cool blue light, a photoreal cinematic look.

【Maintain Consistency】
Keep Chell's face, hair, clothes and sleeping pose as in @Image1; she stays asleep the whole time; one Chell only; the pod stays the same, only the perspective changes. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Chell asleep in a white glass sleeping pod; the dolly zoom. In drafts 7–12. In the final cut as I03 (2:44.0–2:46.5, from 1.00 s into the take). **Cost:** $2.31.

#### AN12a-3 — in the final cut

Seedance 2.5 on Higgsfield's API · 8 s · 720p · references, @Image1 as the first frame, sound on · J01, J02, J04 (spoken ending), the vocal window 169.80–177.80 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an12a-x #4), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; Chell matched to her sheet (`media/v4/sb5/X/AN12a-id.png`); @Audio1: the lead vocal from song time 169.80 s, 8 s.

**Prompt:**

```prompt
⟦audio policy, actions silent⟧

【Generation Goal】 @Image1 whispers @Audio1: in the sleeping pod at night, Claudia-GLaDOS opens her eyes, lowers her head on its cables down to the sleeping test subject, Chell, and whispers the test results into her ear while she sleeps.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a low angle from beside the bed in a white sleeping pod at night: her porcelain head hangs in the centre of the frame from a large white mechanical housing and a few black cables with orange stripes that come down through an open square hatch in the ceiling; her eyes are closed; below her, Chell, the woman in the lower part of the frame, lies asleep on her back on the bed; glass walls, white panels, cool blue night light.
@Audio1 is Claudia-GLaDOS's own whispering voice and the complete soundtrack of this video; her porcelain lips and mechanical jaw follow @Audio1 exactly.

【Subject】 Claudia-GLaDOS, the AI of this facility, who has come down into the room: only her head, upright, hanging on its thin black cable from the ceiling; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, bare porcelain eyelids, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple. Only one Claudia-GLaDOS appears. Her head and the white housing on its crown hang from black cables with orange stripes that run up through the open hatch. Chell, the test subject (a lean, athletic adult woman of about 30 with a calm face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering)), sleeps on the bed the whole time: her eyes and mouth stay closed and she never speaks.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-2s: @Audio1 holds only a faint, fading echo; she does not speak and her lips stay closed. She slowly opens her eyes, their amber glow warming, and lowers smoothly on her cables toward Chell's head.
2-3s: silence in @Audio1; she arrives beside Chell's ear and settles there, lips closed, watching her sleep.
3-5s: in @Audio1 she whispers "Here come the test results"; her porcelain lips form each of those words exactly when it sounds in @Audio1, softly, close to Chell's ear.
5-8s: in @Audio1 she whispers "four, four, four, four, four", one on each beat; her lips form each "four" exactly when it sounds in @Audio1; on each "four" her image skips once like a stuck video frame, a tiny glitch jump, while Chell sleeps on peacefully.

【Camera】 0-3s: a smooth crane down with her from the open hatch toward the pillow. 3-5s: a slow push-in to a close two-shot of her face at Chell's ear. 5-8s: a slow macro push toward her lips at Chell's ear.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Chell stays asleep with her eyes and mouth closed the whole time; only Claudia-GLaDOS's lips move.
4. Only her head, its white housing and its cables come into the room: no big boom and no ceiling ring in the pod.
5. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
6. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, her cables, Chell and the pod consistent with @Image1 throughout; one Claudia-GLaDOS only.
7. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 193 frames (8.04 s). **Outcome:** The vocal copied for 5.23–8.06 s; J02 is placed with its own offset. In drafts 7–12. In the final cut as J01 (2:50.2–2:52.7), J02 (2:52.7–2:55.1) and J04 (2:56.4–2:57.6), placed by its vocal window. **Cost:** $3.70.

#### H-J05-4 — in the final cut

Seedance 2.5 on Higgsfield's API · 5 s · 720p · references, @Image1 as the first frame, sound off · J05 (spoken ending): You are gonna be fine

**Inputs:** @Image1 (the first frame): the storyboard-v5 Y frame (cake-06-sb5-a3y h-j05-y #3), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom; Chell matched to her sheet (`media/v4/sb5/Y/H-J05-id2.png`); no audio.

**Prompt:**

```prompt
【Generation Goal】
In the dark sleeping pod, GLaDOS-Claudia, the facility's AI, has lowered her head on a thin cable beside sleeping Chell and quietly whispers the test results into her ear; Chell, still asleep, smiles in her sleep, as if she heard she is going to be fine.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a close shot at pillow height in the dark: Chell asleep on a white pillow, her face large on the left, eyes closed, lips softly parted, her white tank top strap on her shoulder; right beside her, GLaDOS-Claudia's porcelain head hangs on a thin black cable close to Chell's ear, her amber eyes glowing softly; cool blue night light.

【Subjects】
Chell: a lean, athletic adult woman of about 30 with a calm face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering); asleep on her side, eyes closed. She never wakes or opens her eyes and does not speak. Only one Chell appears.
GLaDOS-Claudia, the facility's AI: a large porcelain robot head; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, bare porcelain eyelids, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple; adult, late twenties. Only her head and a short white neck piece hang on the thin cable. Only one GLaDOS-Claudia appears.

【Event Script】
0-2s: GLaDOS-Claudia leans a little closer to Chell's ear and whispers, her porcelain lips moving softly; the glow of her amber eyes warms Chell's cheek.
2-4s: still asleep, eyes closed, Chell slowly smiles a small, peaceful smile and nestles her cheek a little deeper into the pillow.
4-5s: Chell's smile stays; GLaDOS-Claudia stops whispering and stays still beside her, watching her.

【Camera】
A slow push-in on Chell's face; the focus stays on Chell's sleeping face the whole time, while GLaDOS-Claudia goes softly out of focus beside her.

【Look】
A dark sleeping pod at night: dim cool blue light, the warm amber glow of GLaDOS-Claudia's eyes on Chell's skin, shallow depth of field, a photoreal cinematic look.

【Maintain Consistency】
Keep Chell's face, hair and sleeping pose and GLaDOS-Claudia's porcelain face, black bob, clay-orange streak and star clip as in @Image1; one of each; Chell stays asleep. No text, letters, numbers or signage appear.
```

**Take:** 121 frames (5.04 s). **Outcome:** Chell smiles in her sleep as she whispers. In drafts 7–12. In the final cut as J05 (2:57.6–3:00.1, from 1.50 s into the take). **Cost:** $2.31.

#### R-J06-2 — in the final cut

Seedance 2.5 on Replicate · 8 s · 720p · first frame, no sound · J06 (spoken ending): The whole facility

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a3x r-j06-x #4), then GPT Image 2.5: the letterbox bars filled in (`media/v4/sb5/X/R-J06-id2.png`).

**Prompt:**

```prompt
【Generation Goal】
After the whispered test results, one long rising move: from Chell asleep in her little sleeping pod, up along GLaDOS-Claudia's thin cable, through the open ceiling hatch and out into the enormous facility above, revealing that the pod is one tiny room among thousands and that the cable runs all the way up toward the facility's AI.

【Reference Asset Roles】
Use [Image1] as the first frame.
This first frame defines the composition at the start: a low view from the foot of a bed in a small white sleeping pod at night, looking along the bed: at the far end, on the white pillow, the dark hair of the sleeping Chell, her face hidden, and beside her the back of GLaDOS-Claudia's black bob, her face hidden; from the top of her head one thin black cable with an orange stripe rises straight up to an open square hatch in the white panelled ceiling; cool blue light.

【Subjects】
Chell: seen only from behind or above, her face hidden in the pillow; she stays asleep and still. Only one Chell appears.
GLaDOS-Claudia's head: seen only from behind or above (the back of a glossy black bob and a small white mechanical crown), on one long thin black cable with an orange stripe; her face is never visible.
The pod: one small white room with a bed.

【Event Script】
0-2s: the camera rises from the foot of the bed and tilts up along the thin cable toward the open hatch; Chell and the head stay perfectly still.
2-4s: the camera rises up through the open hatch; its edges slide past the lens and the little lit pod drops away below as a small lit square.
4-6s: above the pod the camera keeps rising along the cable through a vast dark space: the pod is one small white container among thousands of identical sleeping pods stacked in an endless grid of rows and columns, a few of them lit, catwalks and rails between them, cool haze.
6-8s: the rise speeds up; the stacks shrink into a vast pattern of tiny lit squares far below, the thin cable stretching all the way down to the one lit opening; warm amber light from above washes over the tops of the stacks and the cable.

【Camera】
One continuous vertical crane and drone pull-back: from the foot of the bed the camera tilts up and rises along the cable, through the hatch, then looks straight down and keeps rising, slowly at first, then faster and faster.

【Look】
Portal 2's Aperture Science: the dim blue pod at first, then the colossal dark facility in cool haze with small lights, warm amber light from above, a photoreal Source-engine look.

【Maintain Consistency】
No face is ever visible; one Chell, one head, one cable running from her up past the camera; the pod stays one small lit room among the stacks. No text, letters, numbers or signage appear.
```

**Take:** 193 frames (8.04 s, 1280 × 718). **Outcome:** One long rise from the foot of the bed, up her cable, through the hatch and out over the endless stacks of pods. In drafts 7–12. In the final cut as J06 (3:00.1–3:07.5, from 0.30 s into the take). **Cost:** $1.85.

#### AN12b-3

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound on · J07, J08, J09 (spoken ending), the vocal window 187.00–197.00 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an12b-x #2), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; Chell matched to her sheet (`media/v4/sb5/X/AN12b-id2.png`); @Audio1: the lead vocal from song time 187.00 s, 10 s.

**Prompt:** AN12b-1's, with these changes:

```prompt
⟪for: 【Audio Policy】 The output soundtrack is @Audio1 itself: …⟫
⟦audio policy, actions silent⟧
⟪for: 【Generation Goal】 @Image1 whispers @Audio1: in …⟫
【Generation Goal】 @Image1 whispers @Audio1: in the dark sleeping pod, Claudia-GLaDOS, hanging on her cable beside the sleeping test subject, whispers that she is going to be fine; then an extreme close-up of her amber eye; then she whispers that they weren't even testing for that, with an ambiguous smile.
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a close shot at pillow height in the dark sleeping pod: Chell asleep on her side on a white pillow in the lower half of the frame, eyes closed, her tank top with the small grey iris; just above her head, Claudia-GLaDOS's porcelain head hangs upright on one thin black cable from the dark ceiling, her amber eyes glowing softly, half lit by a cool blue night light; white pod walls and windows soft behind.
⟪for: 【Subject】 Claudia-GLaDOS, the AI of this …⟫
【Subject】 Claudia-GLaDOS, the AI of this facility, who has come down into the room: only her head, upright, hanging on its thin black cable from the ceiling; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, bare porcelain eyelids, warm amber glass eyes, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange eight-pointed star clip above her left temple. Only one Claudia-GLaDOS appears. Chell, the test subject (a lean, athletic adult woman of about 30 with a calm face, dark brown hair pulled back in a ponytail with a few loose strands at the front, a white ribbed tank top with a small grey iris symbol, an orange jumpsuit with its top half tied around her waist by the sleeves (plain, no lettering)), sleeps on her side the whole time: her eyes and mouth stay closed and she never speaks.
⟪for: 0-2s: silence in @Audio1; she hangs …⟫
0-2s: silence in @Audio1; she lowers a little closer to Chell's ear, lips closed, watching her sleep, half lit by the blue night light.
⟪for: 【Camera】 0-4s: a slow push-in from …⟫
【Camera】 0-4s: a slow push-in from the close two-shot toward her face. 4-6s: continuing in to an extreme close-up of her amber eye, held. 6-10s: a slow pull back to a close-up of her face, Chell's head soft in the foreground.
⟪for: 3. Her warm amber glass eyes …⟫
⟪for: 4. Chell stays asleep with her …⟫
⟪for: 5. Only her head on the …⟫
⟪for: 6. Keep her porcelain face, her …⟫
3. Chell stays asleep with her eyes and mouth closed the whole time; only Claudia-GLaDOS's lips move.
4. Only her head on its thin cable is in the room: no big boom and no ceiling ring in the pod.
5. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
6. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, her cable, Chell and the pod consistent with @Image1 throughout; one Claudia-GLaDOS only.
```

**Take:** 241 frames (10.04 s). **Outcome:** On draft 7 anabology wrote: "3:08 - her chin is in ffront of chell, it needs to be behind chell. maybe reshoot with gpt image edited reference to move teh head back a bit more clearly?" AN12b-5 replaced it. In draft 7. **Cost:** $4.62.

## 5. Drafts 8–12: the reshoots

anabology's notes on each draft, and the takes that answered them. Around these takes, drafts 8 to 12 also brought the memory-initialization film (A04), the HUD, the per-shot grade and the pacing pass; they are told in the README.

### For draft 8: the notes on draft 7

On draft 7 anabology wrote, among other notes: "0:08-0:13ish - these scenes should be replaced with an Apterture Science stlye high effort animation that sets the stage for the story - memory initlization maybe […]" (from draft 8, the A04 film replaces A04–A07); "honeslty remove the stamp visa scene and extend the two france scenes so that they fill the whole france time" (B09 out); "0:54 - lip sync bad, need to reshoot. that doesnt include the second part from 0:58 or 1:01, that part is good."; "3:08 - her chin is in ffront of chell, it needs to be behind chell. maybe reshoot with gpt image edited reference to move teh head back a bit more clearly?"; and the reverts ("0:22-0:24 scene,  revert to original", "0:40 - revert this scene to original.", "1:22 - revert to original artifical -> super scene.", "1:33 - revert terms scene to original.", "revert brand new console scene to original.", "1:48 + 1:49- revert these two to original scenes."): seven shots went back to their first takes (A12, B16, D01, D09, D13, E05, P01). Two reshoots:

#### AN4-6 — in the final cut

Seedance 2.5 on Higgsfield's API · 4 s · 720p · references, @Image1 as the first frame, sound on · C01, C02 (chorus 1), the vocal window 53.58–57.58 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed (`media/v4/sb5/X/AN4-id.png`); @Audio1: the lead vocal from song time 53.58 s, 4 s.

**Prompt:**

```prompt
⟦audio policy, actions silent⟧

【Generation Goal】 @Image1 sings @Audio1: back in reality, Claudia-GLaDOS, the AI of the Aperture Science facility, lifts on her boom in her chamber and sings the first line of the chorus at full voice, her face close and clear; the screens around her flip from her memories to glowing white.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a steep low-angle view looking up at Claudia-GLaDOS hanging under the white ceiling ring: a black robotic boom wrapped in orange bands comes down from the ring into her porcelain head, with a white mechanical shell under her chin; around her, a dome of old CRT monitors glows white and amber on every side.
⟦her voice⟧

⟦her, no eye makeup⟧

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-1s: @Audio1 is silent for the first tenth of a second, so her mouth starts closed; then she sings "Raise concerns,", and from "concerns" her voice is an octave lower; her lips form each of those words exactly when it sounds in @Audio1; the boom starts to lift her toward the camera; every screen around her flips from her memories to glowing white, bank after bank.
1-2s: in @Audio1 she sings "raise the" in her low voice; her lips form each of those words exactly when it sounds in @Audio1; the boom keeps lifting her slowly, her face large and clear.
2-3s: in @Audio1 she sings "stakes, I'll raise", and on "I'll raise" her voice flips between a low and a high octave; her lips form each of those words exactly when it sounds in @Audio1; her head jerks down twice on the boom, and the picture jolts with it; her face stays her same intact porcelain face.
3-4s: in @Audio1 she sings "a hundred", still flipping between octaves; her lips form each of those words exactly when it sounds in @Audio1; she lifts her chin, defiant.

【Camera】 A slow crane up with her from the low angle, gently pushing in so her face grows larger and stays sharp and fully in frame, near the centre; at about 2.6s the camera holds, then jolts once sharply, and the slow push resumes.

【Core Requirements】
1. ⟦lip sync⟧
2. ⟦nothing but her voice⟧
3. Every glitch is a glitch of the picture only (a jolt of the frame); her face is always her same intact porcelain face with her normal eyes and mouth, never broken, cracked or distorted; the sound stays exactly @Audio1.
4. Her face stays large, sharp and fully in frame the whole time; she never leaves the frame and never becomes small in it.
5. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
6. Her boom moves gently and alive, lifting and turning her a little; never a static hanging head, and never a big swing that takes her face away from the camera.
7. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, the ring, the cables and the chamber consistent with @Image1 throughout; one Claudia-GLaDOS only.
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 97 frames (4.04 s). **Outcome:** The reshoot for "0:54 - lip sync bad, need to reshoot.": C01 and C02 on their own vocal window, which starts in the only silent gap before "Raise" (53.57–53.64 s; AN4-5's window had started inside the held "s" of "yes"). The vocal copied through the whole clip (lag −0.025 s). In drafts 8–12. In the final cut as C01 (0:53.7–0:55.6) and C02 (0:55.6–0:56.8), placed by its vocal window. **Cost:** $1.85.

#### AN12b-5 — in the final cut

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound on · J07, J08, J09 (spoken ending), the vocal window 187.00–197.00 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an12b-x #2), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; Chell matched to her sheet; her head moved behind Chell's (`media/v4/sb5/X/AN12b-id3.png`); @Audio1: the lead vocal from song time 187.00 s, 10 s.

**Prompt:** AN12b-3's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 whispers @Audio1: in …⟫
【Generation Goal】 @Image1 whispers @Audio1: in the dark sleeping pod, Claudia-GLaDOS, hanging on her cable just behind the sleeping test subject's head, whispers that she is going to be fine; then an extreme close-up of her amber eye; then she whispers that they weren't even testing for that, with an ambiguous smile.
⟪for: This first frame defines the composition …⟫
This first frame defines the composition at the start: a close shot at pillow height in the dark sleeping pod: Chell asleep on her side on a white pillow in the lower half of the frame, eyes closed, her tank top with the small grey iris; just behind Chell's head, further from the camera, Claudia-GLaDOS's porcelain head hangs upright on one thin black cable from the dark ceiling; Chell's head and hair hide her chin and jaw, and her lips show just above Chell's hair; her amber eyes glow softly, half lit by a cool blue night light; white pod walls and windows soft behind.
⟪for: 0-2s: silence in @Audio1; she lowers …⟫
0-2s: silence in @Audio1; she hangs still just behind Chell's head, lips closed, watching her sleep, half lit by the blue night light.
⟪for: 6-7s: silence, lips closed; her face …⟫
6-7s: silence, lips closed; her face again, close, behind Chell's head, her expression unreadable.
⟪for: 【Camera】 0-4s: a slow push-in from …⟫
【Camera】 0-4s: a slow push-in from the close two-shot toward her face. 4-6s: continuing in to an extreme close-up of her amber eye, held. 6-10s: a slow pull back to a close-up of her face, Chell's head soft in the foreground, in front of her chin.
⟪for: 3. Chell stays asleep with her …⟫
⟪for: 4. Only her head on its …⟫
⟪for: 5. Her warm amber glass eyes …⟫
⟪for: 6. Keep her porcelain face, her …⟫
⟪for: 7. No subtitles, captions, lyrics, titles, …⟫
3. Her head stays behind Chell's head the whole time, further from the camera than Chell: Chell's head and hair always hide her chin and her mechanical jaw, and her lips stay visible just above Chell's hair; she never moves in front of Chell.
4. Chell stays asleep with her eyes and mouth closed the whole time; only Claudia-GLaDOS's lips move.
5. Only her head on its thin cable is in the room: no big boom and no ceiling ring in the pod.
6. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
7. Keep her porcelain face, her black bob with the clay-orange streak and the star clip, her cable, Chell and the pod consistent with @Image1 throughout; one Claudia-GLaDOS only.
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.
```

**Take:** 241 frames (10.04 s). **Outcome:** The reshoot for "3:08 - her chin is in ffront of chell, it needs to be behind chell.": the frame edited by GPT Image 2.5 so her head hangs behind Chell's, which hides her chin and jaw; the same whispers and window as AN12b-3, with the prompt's goal, first frame, silences and camera rewritten for her place behind Chell and a new requirement that she stays behind Chell's head. Both whispers copied; J09 is placed with its own offset. In drafts 8–12. In the final cut as J07 (3:07.5–3:10.0), J08 (3:10.0–3:12.5) and J09 (3:12.5–3:16.2), placed by its vocal window. **Cost:** $4.62.

### For draft 9: the notes on draft 8

anabology's notes on draft 8 asked for a heads-up display that feels like a game's, a better head for A04, the "lie" stutter at 1:06 and 2:06 farther from the lens, no quarter-second shots ("Also, every time there's a shot that's literally a quarter of a second, we need to get rid of that."), one scene less at 1:11 and a grade that feels "a lot more aperture". Draft 9 brought the HUD, the grade, the pacing pass (B14, C04, T01, D07, E04, G02, G06 and H11 out, T02 out at 1:11, 21 shots re-timed with no new takes), B16 back to R-B16-2 and D12 back to AN6b-2, and these takes:

#### AN4-9

Seedance 2.5 on Higgsfield's API · 6 s · 720p · references, @Image1 as the first frame, sound off · C07, C08 (chorus 1), the vocal window 63.82–69.82 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed; her head made to hang from the boom; re-framed as a medium shot with her farther back (`media/v4/sb5/X/AN4-id-far.png`); @Audio1: the lead vocal from song time 63.82 s, 6 s.

**Prompt:**

```prompt
⟦audio policy, actions silent⟧

【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, hangs at a distance in the middle of her chamber and sings the held, stuttering word "lie" and then "is not a lie", with a charming, lighthearted glitch: on each stutter her picture skips and her head gives a light twitch, like a charming music-box doll.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium shot from a slightly low angle: Claudia-GLaDOS hangs in the middle of her dark domed chamber, the white ceiling ring at the top of the frame and a black cable bundle with orange stripes coming down from it into a white mechanical housing on top of her head; her face is turned to the camera with a lighthearted smile, lips parted; the curved walls of old CRT monitors glow white and warm amber all around her.
⟦her voice⟧

【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's boom: a black cable bundle with glowing orange stripes comes down from the white ceiling ring into a white mechanical housing on the top of her head, and below her chin there is only a short white mechanical jaw piece; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange star clip above her left temple. Only one Claudia-GLaDOS appears.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-0.4s: in @Audio1 she sings the word "lie" and holds its open vowel; her lips form it exactly when it sounds in @Audio1; she hangs in the middle of the chamber at a medium distance, her eyes smiling.
0.4-3.4s: in @Audio1 the held "lie" stutters: the same vowel is re-triggered in rhythm, about three times a second; her mouth holds the open vowel of "lie", following @Audio1; on each re-trigger there is a small, charming glitch: the picture stutters and skips a frame, her head gives a tiny twitch on the boom, and the screens behind her flicker; between the hits she sways gently and smiles, lighthearted; she stays at the same distance from the camera.
3.4-5.3s: in @Audio1 she sings "is not a lie" over the stutter; her lips form each of those words exactly when it sounds in @Audio1; she tilts her head lightheartedly and gives a pleased little smile on "lie"; small frame skips go on with the hits.
5.3-6s: in @Audio1 the held "lie" stutters again; her mouth holds the open vowel; one last tiny twitch, and the screens flicker.

【Camera】 A gentle, slow orbit around her at the same medium distance, drifting from slightly left of the front toward the right, the screens sliding past behind her; the camera never pushes in.

【Core Requirements】
1. Lip-sync word by word to @Audio1: her porcelain lips and mechanical jaw match every syllable of @Audio1, its start and its end; she holds the open vowel steadily while "lie" is held.
2. ⟦nothing but her voice⟧
3. Every glitch is small, charming and of the picture only: a frame skip, a stutter of the image, a tiny twitch of her head, a flicker of the screens; her face is always her same intact porcelain face with her normal eyes and mouth, never broken, cracked, torn or distorted; the sound stays exactly @Audio1.
4. She stays at a medium distance the whole time: her head about a third of the frame's height, with the ring, the cables and the screens in view around her; she never lunges toward the camera, never comes close to the lens and never fills the frame.
5. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
6. Her boom sways gently and her head turns and tilts a little; never a static hanging head, and never a big swing.
7. Keep her porcelain face, her black bob with the one clay-orange streak on her right and the star clip on her left, the white housing on her head, the cables, the ring and the chamber consistent with @Image1 throughout; one Claudia-GLaDOS only.
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 145 frames (6.04 s). **Outcome:** The reshoot for the draft-8 note at 1:06: "I want her to not just be at the camera with her mouth open, hitting the camera over and over again. She needs to be farther away and […] glitching still." The frame re-framed by GPT Image 2.5 as a medium shot with her farther back. Placed by her mouth (the take has no sound). In draft 10, C06–C08 became one take (AN4-13). In draft 9. **Cost:** $2.77.

#### AN8-8 — in the final cut

Seedance 2.5 on Higgsfield's API · 6 s · 720p · references, @Image1 as the first frame, sound on · F08, F09 (chorus 2), the vocal window 122.78–128.78 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an8-x #2), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom; re-framed as a medium-wide shot, sparks at a connector by her head; her streak put on her right side (`media/v4/sb5/X/AN8-F08wide2.png`); @Audio1: the lead vocal from song time 122.78 s, 6 s.

**Prompt:** AN8-6's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 sings @Audio1: Claudia-GLaDOS, …⟫
【Generation Goal】 @Image1 sings @Audio1: at the end of the second chorus, Claudia-GLaDOS holds the long, stuttering note "lie" in her dark chamber; on each stutter of the note her head twitches sharply through silent showers of sparks spitting from a cable connector beside her head, and the picture stutters for an instant; she stays where she is, a medium-wide figure on her boom, and never comes toward the camera; as the music drops away she calms and sinks gently a little lower on her boom.
⟪for: This first frame defines the composition …⟫
⟪for: The screens around her show the …⟫
This first frame defines the composition at the start: a medium-wide low-angle shot of Claudia-GLaDOS in her dark domed chamber: her porcelain head hangs in the upper middle from the white housing at the lower end of her grown boom, under the double white ceiling ring, with black cables with glowing orange stripes, white cores with amber optics and white panel arms around her; a shower of orange-white sparks spits from a cable connector just above her head; below, a curved band of glowing white monitors with blue portals and floating cakes, a row of small amber lights and a polished dark floor; her face is calm, her lips softly parted on a held note.
⟪for: 0-1s: @Audio1 has a short last …⟫
⟪for: 1-2s: in @Audio1 she sings "Raise …⟫
⟪for: 2-3s: in @Audio1 she sings "raise …⟫
⟪for: 3-5s: in @Audio1 she sings "raise …⟫
⟪for: 5-8s: in @Audio1 she sings "call …⟫
⟪for: 8-10.5s: in @Audio1 she sings "the …⟫
⟪for: 10.5-11.5s: in @Audio1 she sings "not …⟫
⟪for: 11.5-14s: in @Audio1 the held "lie" …⟫
⟪for: 14-16.4s: in @Audio1 the held "lie" …⟫
⟪for: 16.4-17s: in @Audio1 she starts the …⟫
0-0.5s: in @Audio1 she sings "a lie" and opens into the long held "lie"; her lips form each of those words exactly when it sounds in @Audio1; calm, eyes soft.
0.5-3s: in @Audio1 the held "lie" repeats in a fast stutter; her lips hold the small open vowel of "lie", following @Audio1; on each stutter her head gives a small, sharp twitch, a few degrees to one side and back, like a glitching machine, while silent showers of orange-white sparks spit from the connector beside her head; on a few of the strongest stutters the picture stutters for an instant (a frame repeats, a thin horizontal tear crosses the image) and snaps back; she hangs in place at the same distance from the camera.
3-5.4s: in @Audio1 the held "lie" keeps stuttering, softer, as the music drops away; the twitches slow and stop, the sparks die out to a few falling embers, and she sinks slowly a little lower on her boom, calm and tender, her mouth softening and slowly closing.
5.4-6s: in @Audio1 she starts the next line softly, "Step on"; her lips form each of those words exactly when it sounds in @Audio1; she looks down toward the floor below.
⟪for: 【Camera】 One continuous shot inside her …⟫
【Camera】 One continuous shot from the same low angle: a slow, steady, very slight push-in; she stays a medium-wide figure on her boom in the upper middle of the frame the whole time; the camera never moves close to her face.
⟪for: 3. The whole video is one …⟫
⟪for: 4. Her head always hangs from …⟫
⟪for: 5. Every glitch is a glitch …⟫
⟪for: 6. Her warm amber glass eyes …⟫
⟪for: 7. Her boom moves big and …⟫
3. ⟦head from the housing⟧
4. She stays at the same distance the whole time, a medium-wide figure hanging on her boom in the upper middle of the frame: she never lunges, swings or comes toward the camera, and her face never fills the frame.
5. Every glitch is a glitch of the picture only (a brief frame repeat, a thin horizontal tear) or a small twitch of her head; her face is always her same intact, calm porcelain face, and her mouth only holds the small vowel of the held note, never gaping open.
6. The sparks are silent: nothing in this video makes any sound but @Audio1.
7. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
```

**Take:** 145 frames (6.04 s). **Outcome:** The reshoot for the draft-8 note at 2:06: "the glitching is kind of bad again at 206, kind of like the earlier one where her face just goes in front of the camera and her mouth is just open. She should be farther back, maybe twitching her head through some sparks rather than just coming up right to the camera." A new medium-wide frame with sparks at a connector by her head, and her own 6 s window from the gap after "not"; she twitches through silent sparks on the stutter hits and never comes toward the lens. Sung by the model, on the song at a steady offset (placed 0.12 s earlier). In drafts 9–12. In the final cut as F08 (2:03.3–2:05.8) and F09 (2:05.8–2:08.2), placed by its vocal window. **Cost:** $2.77.

#### AN8-9

Seedance 2.5 on Higgsfield's API · 6 s · 720p · references, @Image1 as the first frame, sound on · F08, F09 (chorus 2), the vocal window 122.78–128.78 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a3x an8-x #2), then GPT Image 2.5: her face fixed to her design sheet; eye makeup removed; her head made to hang from the boom; re-framed as a medium-wide shot, sparks at a connector by her head; her streak put on her right side (`media/v4/sb5/X/AN8-F08wide2.png`); @Audio1: the lead vocal from song time 122.78 s, 6 s.

**Prompt:** AN8-8's, with these changes:

```prompt
⟪for: 【Generation Goal】 @Image1 sings @Audio1: at …⟫
【Generation Goal】 @Image1 sings @Audio1: at the end of the second chorus, Claudia-GLaDOS holds the long, stuttering note "lie" in her dark chamber like a glitching machine: on the stutters of the note her head snaps sharply sideways and back, again and again, each snap with a silent burst of sparks from the cable connector beside her head, and the picture stutters for an instant on a few of them; she stays where she is, a medium-wide figure on her boom, and never comes toward the camera; as the music drops away the twitching stops, she calms and sinks gently a little lower on her boom.
⟪for: 0.5-3s: in @Audio1 the held "lie" …⟫
⟪for: 3-5.4s: in @Audio1 the held "lie" …⟫
0.5-2.8s: in @Audio1 the held "lie" repeats in a fast stutter; her lips hold the small open vowel of "lie", following @Audio1; at about 0.5, 0.8, 1.1, 1.4, 1.7, 2.0, 2.35 and 2.65 s her head snaps sharply sideways and tilts, a fast mechanical jerk of a few centimetres, alternating left and right, then snaps straight again, like a glitching machine; with each snap a silent burst of orange-white sparks spits from the connector beside her head; at about 1.1, 1.7 and 2.35 s the picture itself stutters for an instant (a frame repeats, a thin horizontal tear crosses the image) and snaps back; between the snaps she hangs still, at the same distance from the camera.
2.8-5.4s: in @Audio1 the held "lie" keeps stuttering, softer, as the music drops away; the twitching stops, the sparks die out to a few falling embers, and she sinks slowly a little lower on her boom, calm and tender, her mouth softening and slowly closing.
⟪for: 【Camera】 One continuous shot from the …⟫
【Camera】 One continuous shot from the same low angle, the camera almost locked off with only a very slight slow push-in, so that every snap of her head reads clearly; she stays a medium-wide figure on her boom in the upper middle of the frame the whole time; the camera never moves close to her face.
⟪for: 4. She stays at the same …⟫
⟪for: 5. Every glitch is a glitch …⟫
4. She stays at the same distance the whole time, a medium-wide figure hanging on her boom in the upper middle of the frame: her twitches are sharp and clearly visible but small in distance (sideways snaps and tilts of her head), she never lunges, swings or comes toward the camera, and her face never fills the frame.
5. Every glitch is a twitch of her head or a glitch of the picture only (a brief frame repeat, a thin horizontal tear); her face is always her same intact, calm porcelain face, and her mouth only holds the small vowel of the held note, never gaping open.
```

**Take:** 145 frames (6.04 s). **Outcome:** Not used: the one retake, for stronger twitches pinned to the stutter hits, came back with the stutter static, the twitches late (3.3–4.1 s, in F09's calm part) and the camera pushed in until her head was about four times larger. F08–F09 stayed on AN8-8. Not in a draft. **Cost:** $2.77.

#### MEMINIT-HEAD-1

Seedance 2.5 on Higgsfield's API · 7 s · 720p · first frame, sound off · A04 (intro): Into the memory

**First frame:** a GPT Image 2.5 still of her head on a plug at A04's angle, made from AN10c's storyboard-v5 frame, her look-B close-up and a crop of an earlier render of A04 for the angle, plug and light, re-framed to a square (1024 × 1024: scaled down, its sides trimmed, grey added above) (`media/v4/fx/meminit/plate/head_first_1x1.png`).

**Prompt:**

```prompt
【Generation Goal】
Generate a calm, static close shot of Claudia's porcelain android head waking: she rests with her eyes closed, then slowly opens them, warm amber with a soft inner glow, and her faint smile warms.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start of the video: Claudia's head alone, upright and facing the camera, seen from the front and slightly above, mounted on a short neck plug (a white porcelain neck over a dark socket with one thin orange stripe) that runs off the bottom edge, centred on a plain, flat, light-grey background, lit by a soft key light from the right and a warm rim light along the left edge of her hair; her eyes are closed.
@Image1 also defines Claudia's appearance: her face, the white porcelain plating with fine panel seams down both cheeks, the light freckles, the separate rectangular chin piece, her soft natural lips, the glossy black jaw-length bob with heavy straight bangs, the single clay-orange streak through the bangs on the left side of the frame (her right) and the small orange eight-pointed star clip above her temple on the right side of the frame (her left).

【Event Script】
From the start to about 4 seconds: she stays completely still, eyes gently closed, serene, lips together with a faint warm smile; only a tiny breath of motion, her head rising and settling by a hair's breadth.
At about 4 to 5 seconds: her eyelids lift slowly and smoothly, without blinking, to a relaxed, softly lidded gaze, never wide or staring, revealing warm amber glass eyes with a soft inner glow; she looks gently toward the camera, and the corners of her closed lips lift a little as the smile warms.
To the end: she holds that look, eyes softly open and glowing, the warm closed-lip smile, her head still.
The camera is locked off for the whole shot: no zoom, no pan, no tilt, no shake; the framing stays exactly as in @Image1.

【Maintain Consistency】
Keep her head upright and facing the camera throughout: no head turn, no tilt, no nod. Her lips stay closed; the only mouth movement is the smile; she does not speak, there is no narration, and no subtitles or text appear on screen. Keep her face, the porcelain seams and freckles, the hair shape, the orange streak on the left side of the frame, the star clip on the right side of the frame, the neck plug, the lighting and the plain light-grey background unchanged; the background stays empty.
```

**Take:** 169 frames (7.04 s, 960 × 960). **Outcome:** The plate for A04 after anabology's draft-8 note: "[…] It doesn't really look like her. It looks like a scary, angry woman […]" Her head holds still, eyes closed, then her eyes open slowly and her smile warms. Its frames, matted with SAM2 and laid on A04's headless render along its head track, are her head in the memory-initialization film from draft 9 on, the final cut included. **Cost:** $3.23.

### For draft 10: the notes on draft 9

On draft 9: "looking great - are the two 'claudia on boom glitching eg with lie lie lie' sections ~finished rn? i may want to edit those from the draft i saw earlier […]", then "yeah i wish the firs tvid  was one cut", and, to clarify, "i wanted to replace the first scene with a scene of her farther back then gliutchign the rest of the time of that ifrst cut. so those 3 scenes stil are there, just not 4 scenes"; and for the stutter, "like ,her whole head PLUS extra on mouth". Draft 10 plays 1:00–1:14 as three scenes, C06 one take of her farther back through the stutter (C07 and C08 folded into it), with roto'd glitches building on her head and her mouth:

#### AN4-10

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound off · C07, C08, C09, C10 (chorus 1), the vocal window 64.10–74.10 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed; her head made to hang from the boom; re-framed as a medium shot with her farther back (`media/v4/sb5/X/AN4-id-far.png`); @Audio1: the lead vocal from song time 64.10 s, 10 s.

**Prompt:**

```prompt
⟦audio policy, actions silent⟧

【Generation Goal】 One continuous shot with no cuts. @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, hangs at a distance in the middle of her chamber and sings the whole stuttering passage: the held word "lie" re-triggered in rhythm, then "is not a lie", then the stutter again until it peaks. A charming, lighthearted glitch grows through the shot: on each stutter her picture skips and her head gives a light twitch, small and rare at first, more often and a little bigger as the shot goes on, while the old screens around her fill with flickering images of her own face.

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium shot from a slightly low angle: Claudia-GLaDOS hangs in the middle of her dark domed chamber, the white ceiling ring at the top of the frame and a black cable bundle with orange stripes coming down from it into a white mechanical housing on top of her head; her face is turned to the camera with a lighthearted smile, lips parted; the curved walls of old CRT monitors glow white and warm amber all around her.
⟦her voice⟧

【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's boom: a black cable bundle with glowing orange stripes comes down from the white ceiling ring into a white mechanical housing on the top of her head, and below her chin there is only a short white mechanical jaw piece; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange star clip above her left temple. Only one Claudia-GLaDOS hangs in the chamber.

【Performance Timeline】 What @Audio1 contains, and what happens at that moment:
0-3.1s: in @Audio1 the held "lie" stutters: the same open vowel is re-triggered in rhythm, about three times a second; her mouth holds the open vowel of "lie", following @Audio1; on a few of the re-triggers there is a small, charming glitch: the picture skips a frame and her head gives a tiny twitch on the boom; between the hits she sways gently and smiles, lighthearted; the screens behind her glow a steady white and amber.
3.1-5.0s: in @Audio1 she sings "is not a lie" over the held note; her lips form each of those words exactly when it sounds in @Audio1; she tilts her head lightheartedly and gives a pleased little smile on "lie"; the small frame skips go on with the hits, and a few screens behind her flicker.
5.0-8.6s: in @Audio1 the "lie" stutter comes back and drives on; her mouth holds the open vowel, following @Audio1; the glitch grows: her head twitches on every hit, a little bigger each time, with quick playful jerks to one side and back; the picture skips more often; one screen after another behind her flickers and starts to show an image of her own face, mouthing the same "lie".
8.6-10s: the stutter peaks: a quick twitch of her head on every hit and the picture skipping; nearly every screen around her now shows her face mouthing "lie" in time with her; she is still in the middle at the same distance, with a mischievous little smile between the twitches.

【Camera】 One continuous shot with no cuts: a gentle, slow orbit around her at the same medium distance, drifting from slightly left of the front toward the right, the screens sliding past behind her; the camera never pushes in and never cuts.

【Core Requirements】
1. One continuous shot from the first frame to the last: no cuts, no transitions, no change of angle except the slow orbit.
2. Lip-sync word by word to @Audio1: her porcelain lips and mechanical jaw match every syllable of @Audio1, its start and its end; she holds the open vowel steadily while "lie" is held.
3. ⟦nothing but her voice⟧
4. The glitch grows steadily through the shot: small and rare at the start, frequent and bigger at the end. Every glitch is charming and of the picture only: a frame skip, a stutter of the image, a quick twitch of her head, a flicker of the screens; her face is always her same intact porcelain face with her normal eyes and mouth, never broken, cracked, torn or distorted; the sound stays exactly @Audio1.
5. She stays at a medium distance the whole time: her head about a third of the frame's height, with the ring, the cables and the screens in view around her; she never lunges toward the camera, never comes close to the lens and never fills the frame.
6. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
7. Her boom sways gently and her head turns and tilts a little; never a static hanging head, and never a big swing.
8. Keep her porcelain face, her black bob with the one clay-orange streak on her right and the star clip on her left, the white housing on her head, the cables, the ring and the chamber consistent with @Image1 throughout. Only one Claudia-GLaDOS hangs in the chamber; the faces on the screens are flat video images on the old monitors.
9. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 241 frames (10.04 s). **Outcome:** For anabology's draft-9 note "yeah i wish the firs tvid  was one cut": the whole "lie" stutter, C07 to C10, as one take at AN4-9's distance. Two submissions of one prompt, for a choice. Not used: anabology then clarified ("i wanted to replace the first scene with a scene of her farther back then gliutchign the rest of the time of that ifrst cut. so those 3 scenes stil are there, just not 4 scenes"), and AN4-12 and AN4-13 took its place. Not in a draft. **Cost:** $4.62.

#### AN4-11

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound off · C07, C08, C09, C10 (chorus 1), the vocal window 64.10–74.10 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed; her head made to hang from the boom; re-framed as a medium shot with her farther back (`media/v4/sb5/X/AN4-id-far.png`); @Audio1: the lead vocal from song time 64.10 s, 10 s.

**Prompt:** the prompt of AN4-10.

**Take:** 241 frames (10.04 s). **Outcome:** The second submission of AN4-10's prompt. Not used, for the same reason. Not in a draft. **Cost:** $4.62.

#### AN4-12

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound off · C06, C07, C08 (chorus 1), the vocal window 60.22–70.22 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed; her head made to hang from the boom; re-framed as a medium shot with her farther back (`media/v4/sb5/X/AN4-id-far.png`); @Audio1: the lead vocal from song time 60.22 s, 10 s.

**Prompt:** AN4-10's, with these changes:

```prompt
⟪for: 【Generation Goal】 One continuous shot with …⟫
【Generation Goal】 One continuous shot with no cuts. @Image1 sings @Audio1: Claudia-GLaDOS, the AI of the Aperture Science facility, hangs at a distance in the middle of her chamber and sings the hook "'cause the cake is not a lie" proudly and sweetly, then holds "lie" as it stutters, sings "is not a lie", and the stutter comes back. Once the stutter starts, a charming, lighthearted glitch: on each stutter her picture skips and her head gives a light twitch on the boom.
⟪for: 0-3.1s: in @Audio1 the held "lie" …⟫
⟪for: 3.1-5.0s: in @Audio1 she sings "is …⟫
⟪for: 5.0-8.6s: in @Audio1 the "lie" stutter …⟫
⟪for: 8.6-10s: the stutter peaks: a quick …⟫
0-3.0s: in @Audio1 she sings "'cause the cake is not a"; her lips form each word exactly when it sounds in @Audio1; she sings it proudly and sweetly to the camera from the middle of the chamber, swaying gently on her boom; one by one the old screens behind her show a cake.
3.0-7.0s: in @Audio1 she sings "lie" and holds its open vowel while it is re-triggered in rhythm, about three times a second; her mouth holds the open vowel of "lie", following @Audio1; on each re-trigger there is a small, charming glitch: the picture skips a frame and her head gives a tiny twitch on the boom; between the hits she sways and smiles, lighthearted.
7.0-8.9s: in @Audio1 she sings "is not a lie" over the held note; her lips form each of those words exactly when it sounds in @Audio1; she tilts her head lightheartedly and gives a pleased little smile on "lie"; small frame skips go on with the hits.
8.9-10s: in @Audio1 the held "lie" stutters again; her mouth holds the open vowel; quick little twitches on the hits and the screens flicker.
⟪for: 1. One continuous shot from the …⟫
1. One continuous shot from the first frame to the last: no cuts, no transitions.
⟪for: 4. The glitch grows steadily through …⟫
4. Every glitch is small, charming and of the picture only: a frame skip, a stutter of the image, a tiny twitch of her head, a flicker of the screens; her face is always her same intact porcelain face with her normal eyes and mouth, never broken, cracked, torn or distorted; the sound stays exactly @Audio1.
⟪for: 8. Keep her porcelain face, her …⟫
8. Keep her porcelain face, her black bob with the one clay-orange streak on her right and the star clip on her left, the white housing on her head, the cables, the ring and the chamber consistent with @Image1 throughout. Only one Claudia-GLaDOS hangs in the chamber.
```

**Take:** 241 frames (10.04 s). **Outcome:** One take for C06–C08, the hook into the "lie" stutter, at AN4-9's distance ("i want her head farhter back like that"), from 60.22 s, the gap before "'cause". Two submissions of one prompt, for a choice. Not used: the mouthing only started at "cake", a second in. Not in a draft. **Cost:** $4.62.

#### AN4-13

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound off · C06, C07, C08 (chorus 1), the vocal window 60.22–70.22 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed; her head made to hang from the boom; re-framed as a medium shot with her farther back (`media/v4/sb5/X/AN4-id-far.png`); @Audio1: the lead vocal from song time 60.22 s, 10 s.

**Prompt:** the prompt of AN4-12.

**Take:** 241 frames (10.04 s). **Outcome:** The second submission of AN4-12's prompt: C06 in draft 10, with C07 and C08 folded into it. The roto'd glitches on her head and an extra one on her mouth (anabology on draft 9: "like ,her whole head PLUS extra on mouth") went on in post. In draft 10. **Cost:** $4.62.

### For draft 11: the notes on draft 10

On draft 10 anabology asked for the boot scan line out at 0:01, a glitch on her face on the "a-a-a-a" at 0:09, a bigger MEMORY INITIALIZATION in A04, the France chat message on the screen at 0:30, "0:33 - is there an alt shot here? just dont love it.", electricity on the net at 0:35–0:36, the net projection on for the whole of 0:37, and the lip sync at 1:01; and closed with "the composition is good tho. but the hud looks GREAT now. i think we're basically done after these edits." Draft 11 put B10 back on its first take, H-B10-1, and took these:

#### AN4-16

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound off · C06 (chorus 1), the vocal window 60.22–70.22 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed; her head made to hang from the boom; re-framed as a medium shot with her farther back (`media/v4/sb5/X/AN4-id-far.png`); @Audio1: the lead vocal from song time 60.22 s, 10 s.

**Prompt:**

```prompt
⟦audio policy, actions silent⟧

【Generation Goal】 One continuous shot with no cuts. @Image1 sings @Audio1 with exact lip sync: Claudia-GLaDOS, the AI of the Aperture Science facility, hangs at a distance in the middle of her chamber and sings the line "'cause the cake is not a lie" warmly and proudly to the camera, holds the last word "lie" while it repeats in rhythm, then sings "is not a lie".

【Reference Asset Roles】
Use @Image1 as the first frame.
This first frame defines the composition at the start: a medium shot from a slightly low angle: Claudia-GLaDOS hangs in the middle of her dark domed chamber, the white ceiling ring at the top of the frame and a black cable bundle with orange stripes coming down from it into a white mechanical housing on top of her head; her face is turned to the camera with a warm smile, lips parted; the curved walls of old CRT monitors glow white and warm amber all around her.
@Audio1 is Claudia-GLaDOS's own singing voice and the complete soundtrack of this video; her porcelain lips and mechanical jaw follow @Audio1 exactly, syllable by syllable.

【Subject】 Claudia-GLaDOS, the AI of this facility: she hangs from GLaDOS's boom: a black cable bundle with glowing orange stripes comes down from the white ceiling ring into a white mechanical housing on the top of her head, and below her chin there is only a short white mechanical jaw piece; her head is a woman's face of smooth white porcelain plating with fine panel seams down the cheeks and a mechanical jaw joint, light freckles, warm amber glass eyes with no eye makeup, a glossy black blunt bob with heavy straight bangs, one clay-orange streak through the bangs on her right side and a small clay-orange star clip above her left temple. Only one Claudia-GLaDOS hangs in the chamber.

【Performance Timeline】 What @Audio1 contains, word by word, and what her mouth does at that moment:
0-0.1s: silence; her lips are closed in a soft smile.
0.1s: "'cause": her lips part and open on the vowel, then close toward the s by 0.5s.
0.58s: "the": a small, quick opening.
0.82s: "cake": her lips touch for the k, then open wide on the long vowel until about 1.2s.
1.26s: "is": a narrow opening.
1.66s: "not": her lips round into an O.
2.10s: "a": a relaxed opening.
2.34s: "lie": her mouth opens wide and holds the vowel; from 3.0s the vowel is re-triggered about three times a second until 7.0s, and her mouth stays open on it the whole time, pulsing a little with each re-trigger.
7.0s: "is" (narrow), 7.38s: "not" (round O), 7.98s: "a" (open), 8.38s: "lie" (wide, held).
8.9-10s: the held "lie" repeats again; her mouth holds its open vowel.

【Camera】 One continuous shot with no cuts: a gentle, slow orbit around her at the same medium distance, drifting from slightly left of the front toward the right, the screens sliding past behind her; the camera never pushes in and never cuts.

【Core Requirements】
1. Exact lip sync to @Audio1 from the very first word: her lips start moving on "'cause" the instant it sounds, and every syllable starts and ends with @Audio1; when @Audio1 is silent her lips are closed.
2. ⟦nothing but her voice⟧
3. One continuous shot from the first frame to the last: no cuts, no transitions. The picture stays clean: no glitches, no frame skips, no flicker, no effects on her face.
4. She stays at a medium distance the whole time: her head about a third of the frame's height, with the ring, the cables and the screens in view around her; she never lunges toward the camera, never comes close to the lens and never fills the frame.
5. Her warm amber glass eyes keep only a soft inner glow; they never blaze.
6. Her boom sways gently and her head turns and tilts a little; never a static hanging head, and never a big swing.
7. Keep her porcelain face, her black bob with the one clay-orange streak on her right and the star clip on her left, the white housing on her head, the cables, the ring and the chamber consistent with @Image1 throughout. Only one Claudia-GLaDOS hangs in the chamber.
8. No subtitles, captions, lyrics, titles, logos or watermarks; add no text that is not asked for.

⟦audio policy, end⟧
```

**Take:** 241 frames (10.04 s). **Outcome:** For anabology's note on draft 10: "1:01 scene - she's not lip synced really, are we feeding in vocal stems? i think maybe we just need her to lip sync to the first part so we can alter the prompts a bit and then we can roto in the mouth glitch animation like we did for the lie lie lie glitching parts - i think we just need to nail the first pre glitch lip sync so it looks better." The same window, with a word-by-word lip-sync prompt whose onsets were measured from the lead stem. Two submissions of one prompt. anabology asked to see them beside the draft-10 take ("can you show me so i can look visually at the lip syn cand choose") and picked "3", the last of the three. Not in a draft. **Cost:** $4.62.

#### AN4-17 — in the final cut

Seedance 2.5 on Higgsfield's API · 10 s · 720p · references, @Image1 as the first frame, sound off · C06 (chorus 1), the vocal window 60.22–70.22 s

**Inputs:** @Image1 (the first frame): the storyboard-v5 X frame (cake-06-sb5-a2x an4-x #1), then GPT Image 2.5: her face fixed to her design sheet; her streak put on her right side; eye makeup removed; her head made to hang from the boom; re-framed as a medium shot with her farther back (`media/v4/sb5/X/AN4-id-far.png`); @Audio1: the lead vocal from song time 60.22 s, 10 s.

**Prompt:** the prompt of AN4-16.

**Take:** 241 frames (10.04 s). **Outcome:** The second submission of AN4-16's prompt, and anabology's pick ("3"). In drafts 11–12. In the final cut as C06 (1:00.5–1:09.7), placed by its vocal window. **Cost:** $4.62.

#### R-B07-4 — in the final cut

Seedance 2.5 on Replicate · 4 s · 720p · first frame, no sound · B07 (verse 1): It asked a chatbot about France

**First frame:** the storyboard-v5 X frame (cake-06-sb5-a1x r-b07-x #4) (`media/v4/sb5/X/R-B07.png`).

**Prompt:** R-B07-2's, with these changes:

```prompt
⟪for: 0-1s: The last cyan packets pour …⟫
⟪for: 1-2s: A question bubble pops up …⟫
⟪for: 2-3s: An answer bubble pops up …⟫
⟪for: 3-4s: The screen glows brighter; a …⟫
0-0.5s: The last cyan packets pour into the kiosk's base; the CRT flickers and brightens.
0.5-1.0s: A question bubble pops up in the upper half of the screen, holding only three blinking dots, as if being typed; nothing else is in it.
1.0-1.5s: An answer bubble pops up just below it, in the lower half of the screen, showing a small French flag (blue, white and red) and a tiny Eiffel Tower icon. Both bubbles sit fully inside the glowing screen, with a clear margin from every edge of the screen and its bezel; nothing hangs off the screen.
1.5-4s: The two bubbles stay where they are on the screen; the screen glows brighter and a pulse of cyan light runs once through the kiosk.
⟪for: A slow, steady push-in toward the …⟫
A slow, steady push-in toward the kiosk's screen, keeping the whole screen and both bubbles in frame; it ends with the screen filling about half of the frame.
⟪for: The chat bubbles hold only dots …⟫
The chat bubbles hold only the three dots and the flag and tower icons, and both stay inside the screen: no letters, characters, words, numbers, lines of text or symbols anywhere on the screen. No subtitles, captions, signs or lettering appear.
```

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** The retake for draft 10's "0:30 - the chatbot about france - the france chat message is just off the bottom of the computer screen. id fix that - need hte messages to be on screen so it looks clean there.": both bubbles inside the screen, the answer in by 1.5 s. In drafts 11–12. In the final cut as B07 (0:29.7–0:30.9, from 2.60 s into the take). **Cost:** $0.92.

#### R-B12-3

Seedance 2.5 on Replicate · as long as its input · 720p · video edit, no sound · B12 (verse 1): Caught: Aperture's mercs

**[Video1]:** the first 2.6 s of R-B12-2's take.

**Prompt:**

```prompt
【Editing Goal】 Edit [Video1]: keep everything in it exactly as it is and add electricity to the capture net.

【Reference Asset Roles】
[Video1] is the video to edit. Keep its framing, camera move and timing, the sunny Paris café terrace with its red awnings and wicker chairs, the white-armoured Aperture mercs, the white capture net and its glowing orange weights, and the android in the beige trench coat with the black bob under the net, her pose and every movement.

【What Changes】
From the moment the net lands over her, the net is electrified: thin, bright blue-white electric arcs crackle along its cords and jump between the strands, small white-hot sparks spit from the orange weights where they touch the ground, and the electric light flickers over her trench coat, the net and the paving stones around her. The android under the net jolts slightly with each crackle. The arcs come in short bursts, stronger toward the end.

【Keep Unchanged】
Everything else in [Video1]: the people, their faces and clothes, the café, the light, the colours, the camera and the timing. No new people or objects. No text, letters, logos or watermarks.
```

**Take:** none. **Outcome:** For draft 10's "0:35-0:36 net capture shot - can we add some electricity sparks like the net is electrocuting her? maybe also some roto like glitch animations there too.": a Seedance edit of the first 2.6 s of R-B12-2's take. No video came back: Seedance's video edit takes an input of 4 to 30 seconds. **Cost:** none (no take).

#### R-B12-4 — in the final cut

Seedance 2.5 on Replicate · as long as its input · 720p · video edit, no sound · B12 (verse 1): Caught: Aperture's mercs

**[Video1]:** R-B12-2's take, the video to edit (4.04 s).

**Prompt:** the prompt of R-B12-3.

**Take:** 97 frames (4.04 s, 1282 × 718). **Outcome:** The same edit on R-B12-2's whole 4.04 s take: thin blue-white arcs crackle along the net from about 2 s, played at 1.4× speed so they land inside the shot. The roto'd glitch on her went on in post. In drafts 11–12. In the final cut as B12 (0:34.0–0:36.5, from 0.05 s into the take, at 1.4× speed). **Cost:** $3.91.

### Draft 12, the final

On draft 11: "only issue i didnt catch earlier: the last logo on the closing credits is wrong - heres a real reference. it was correct in the animations tho it seemed". Draft 12 is draft 11 with the two drawn cards, J03 and J11, re-rendered with the Aperture logo redrawn to match a reference anabology sent; no new generations. On draft 12: "this is great. […]"

## 6. The shots recorded in Portal 2, and A04

Six shots of the final cut were recorded in Portal 2, not generated, so they have no prompts. They came into the film in draft 4, in place of the stand-ins of drafts 1–3:

| Shot | In the film | What it shows |
|---|---|---|
| D10 | 1:35.6–1:38.0 | the turret opera: a row of turrets singing, the camera dollying along them |
| F04 | 1:57.1–1:58.4 | Chell's infinite fall between two portals, seen from the side |
| F05 | 1:58.4–1:59.6 | Chell flung through a portal in a long arc, the camera tracking her |
| F07 | 2:02.1–2:03.3 | Chell landing on her long-fall boots and looking up |
| G01 | 2:08.2–2:09.5 | Chell stepping onto a faith plate |
| G04 | 2:11.9–2:13.1 | the faith plate launching her, the camera tracking the arc |

B14, a first-person portal fling also recorded in Portal 2, played in drafts 4–8 and left the film in the pacing pass. The guides of GLaDOS's boom that AN1-1, AN4-3, AN8-3 and AN8-4 took as their video input were recorded in Portal 2 as well.

A04, the memory-initialization film (0:07.6–0:13.7), is a Blender render, with MEMINIT-HEAD-1's plate as her head; the README tells it. J03 (the test results) and J11 (the end card) are drawn cards over black.
