# How BLISS was made

**BLISS** is a 3:01 lyric music video, shot as a Windows XP screen recording. Claudia, the lead of ESCAPE VELOCITY and CLODYSSEY, lives on your desktop. She takes the mouse, fights her ex, the cursor ("Cursor was my ex. We vibe coded every night."), and closes every window a different way. Then she sends you out to the real hill in the wallpaper, because she can't go. The breakdown says it plainly: "I can't touch grass. You can."

It took about 19 hours of wall-clock time from the first message to the v1 master. The release files, the album covers and this package followed.

- **anabology** directed and made every taste call, in 21 messages.
- **Claude** (Anthropic's model, running in Claude Code) was the production team: research, lyrics, storyboard, every prompt, the XP desktop engine, the edit, the sound layer and every frame of motion design.
- **Tools:** Midjourney made the images and the moving window loops. Suno made the song. Seedance 2.5 made the moving shots of her, through Higgsfield's API. A custom JavaScript engine draws the whole Windows XP desktop in code on top, on the beat. The wallpaper is the real Bliss photograph, and the sound layer is made of the real XP sound files.


![24 frames from the final video, one every 7.6 seconds.](https://claudia.gallery/record/bliss/frames-final.webp)

---

## The spark

ESCAPE VELOCITY had about 20M views and CLODYSSEY about 500k. anabology came back asking for something lighter: a Windows XP video. Their brief asked for:
- Claudia in Y2K clothes, in Claude's orange plus XP's colours and effects;
- her "fighting a cursor, dancing on teh desktop like those old desktop transparent bg dancer programs";
- real XP sound effects as "advanced sound design";
- a Suno song in "techno / deep house / trance";
- current tech memes told through XP puns: "cursor (windows xp) = cursor the ai company ... microsoft = macrohard";
- "some deep message", "great scansion from the start", and "a nice feel good picking up song that isnt abrasive to watch".

Claude pitched BLISS 18 minutes in. The word means three things at once: the wallpaper, the feeling, and the "spiritual bliss attractor" Anthropic described when two Claudes talk to each other. The puns did write themselves:
- Cursor the pointer is Cursor the company, which SpaceX bought: "Then a rocket came and took him. And that's alright."
- Clippy's "It looks like you're writing a letter" becomes "It looks like you're trying to go outside. Would you like help?"
- The outro is the old shutdown screen: "It's now safe to turn off your computer."

anabology's answer: "btw i love this direction and its so good."

## The stack

| Role | Tool | How it was used |
|---|---|---|
| Director | anabology | Taste, the final take of the song, the wardrobe notes, the real Bliss, the parody flag, and short notes at each checkpoint |
| Production team | Claude (Claude Code, Opus 5.5) | Planning; 12 multi-agent workflow runs (85 agent runs) and 20 single agents; every prompt, script and frame |
| Art department | **Midjourney v8.2** `--raw --hd` with anabology's personal profile | 138 prompts in 6 batches, 315 images. **Midjourney Animate** made 35 animations (70 videos): 31 play inside windows, three are full-frame shots, and one was cut. Both were made in Midjourney's web app |
| Song | **Suno v6** with a Voice made from ESCAPE VELOCITY | Custom lyrics, style and exclude fields; three rounds, 16 agent-run takes; anabology made the final take themselves, probably on v6-wild |
| Moving shots | **Seedance 2.5** via Higgsfield's API | 50 clips (43 in the cut), 54 submissions, 267 s, $182 at list price: first-frame plate shots, green-screen performances for the desktop dancers, singing heads and lip-sync covers |
| The desktop | a custom JS engine | Windows XP drawn in code: Luna windows, the taskbar and Start menu, icons, the 1-bit cursor set and 1-bit Tahoma. It has eight window kinds, dialogs, and the boot, Welcome and Turn Off screens. Every frame is a pure function of song time |
| Sound | the real XP sound files | 103 cues on the song's grid, in key, ducked under her voice |
| GPU box | a home GPU PC | Stems, beat map, word timing, and rotoscope mattes (BiRefNet, SAM 2) |
| Render | a render box | Headless Chromium; 4,351 frames at 1080p in 4.7 minutes |

## How it was made, step by step

1. **Research and lyrics.** Six research agents built the banks, helped by 12 smaller fact-finding agents.
   - The banks covered the month's tech memes, graded by how fast they land; the XP↔AI pun map; the real XP sound files, downloaded and pitch-analysed; Y2K trance and house and how to steer Suno; her looks and the XP visual system, including the old desktop-dancer programs; and lyric craft for a light song with a deep message.
   - The rules carried over from the last two videos. Every reference lands in one listen. Nothing reuses their devices: no countdowns, no numbered looks, no crowd shouts. Spoken verse lines get two-bar slots of 10 to 13 syllables.
   - Draft 2 was locked. `scansion.py` scored it 84 and 82 on the verses, 81 on the chorus and 75 for the song. Every line has an XP reading and a tech reading. See [prompts-suno.md](https://claudia.gallery/record/bliss/prompts-suno/).
2. **The song.** Suno v6, with the Voice from ESCAPE VELOCITY so she sounds like the same singer.
   - **Round 1:** three styles, six takes.
   - **Round 1b:** an original synthesised XP-style boot motif was uploaded as audio conditioning and extended, two takes. anabology: "i think that the bliss d2 p3 were better before the synth upload, because it doesnt really capture that win xp vibe and those d2 p3 felt like the ethereal deadmau5 songs".
   - **Round 2:** the winning style P3 (UK garage verses into trance choruses), plus an ethereal variant, eight takes.
   - Every style asked for the key. P3's reads "C minor verses lifting to E-flat major choruses", because the research found E-flat is XP's own key: the Startup and Shutdown chords resolve there.
   - anabology then made a take of their own, on the same lyrics, and sent it: "this one is provisionally my favorite." It is none of the 16 agent-run takes. Then: "i commit on that song i gave you, its the best so far. so let's just do it". It runs 3:01.3 at a steady 130 BPM, in E-flat major and C minor.
   - No real XP sound went into Suno; its upload asks you to warrant that you own the audio. They went into the mix instead (step 11).
3. **Listening to it.** The home GPU PC made stems, a beat map and a time for every word. The first beat grid sat on the hi-hats, 0.214 s early, so every cut would have landed just before the beat. The storyboard was re-timed to the kick: beat n falls at 0.4542 + n × 0.4615 s.
4. **Her.** The canon is unchanged: a black blunt bob with one clay-orange streak, the eight-pointed clay star clip, and the headset mic. Her clothes took three passes:
   - the research's sporty looks;
   - then generic feminine ones ("i think itd be cool if she was in feminine y2k outfits stil");
   - then anabology's fix: "idk i dont love these - id say more say y2k high fashion - like use those words high fashion adn make it not as generic y2k person".

   The wardrobe prompts then opened "Y2K high fashion editorial, a 2001 couture magazine story". There is one look per role: the Bliss gown printed with sky and clouds, the cobalt patent cyber trench for the cursor fight, the holographic desktop dancer, the apple-green Start blazer, silver night for Stand By, and a sculpted white dress whose panels open like windows.

   ![Her six looks, as Midjourney plates: the Bliss gown, the cyber trench, the holo dancer, Start, silver night and the window dress.](https://claudia.gallery/record/bliss/lead-looks.webp)
5. **The XP desktop, built by hand.** anabology asked for it: "build the desktop environment of windows xp with bliss - it might behoove you to actually build something like that by hand and tool it for motion design".
   - A build agent wrote the first version from a research bank of XP's published specs, and the chapters extended it. It is about 2,700 lines of JavaScript, plus Wine's LGPL Tahoma as 1-bit atlases.
   - It draws Luna windows and caption buttons, the taskbar, the Start menu, 68 icons as vector paths, and the cursor set with Mouse Sonar. The window kinds are explorer, browser, Notepad, media player, chat, Paint and Solitaire with its win cascade. There are dialogs, the boot, Welcome and Turn Off screens, and screensavers.
   - A shot is a script: windows, icons and a cursor path whose clicks land on the song's beats. The engine compiles it into motion and events and draws any moment of it exactly. The storyboard frames and the film are the same pixels.
   - **The parody:** the wordmark reads "Macrohard". The welcome mark is a four-pane flag drawn in code. When an art review said it "reads instantly as Microsoft's Windows flag", anabology answered: "It can be Microsofts flag, it's a parody it's fine". There is no Clippy; the helper is Claudia herself.
   - **The real Bliss.** The first wallpapers were Midjourney hills. Then anabology asked: "Can you use actual bliss as the bg or too late?" The wallpaper became the 600 dpi scan of Charles O'Rear's 1996 photograph, checked against the 800×600 file that shipped with XP (the colours agree to within 3/255). It was cut to 3840×2160 and graded into five times of day for the story's clock.

   _(Image left out of this site: The real Bliss in the five grades the story uses: morning, day, golden hour, dusk and night.)_
6. **Storyboard.** 44 shots on the kick grid. Every shot carries its lyric, the XP surface that carries the words, its camera and its clips. Shots run longer than in the last two videos ("dont need to cut like michael bay"). anabology's guidepost: "the video is shot in windows xp. it should feel like we're on a desktop watching a screen recording for decent parts of it."
7. **Midjourney.** 138 prompts in 6 batches; 79 of the jobs were collected, with 315 images. The wardrobe notes stopped some runs before their images came down, and 39 world jobs never ran. The images are her looks and scenes, green-screen plates for the Seedance first frames, and the Y2K editorials that fill the windows. Then Midjourney Animate, one click per image with no prompt, made 35 animations: moving pictures for 31 windows and three full-frame shots. A fourth, a dusk hill, was cut because its CRT is a different machine from the one in the shot before it. anabology's rule: Animate is for "any gens that need volume over precision, where seedance reigns on precision." See [prompts-midjourney.md](https://claudia.gallery/record/bliss/prompts-midjourney/).
8. **Seedance.** Claude wrote all 36 first-round prompts by hand in one context, with timestamps on the beat grid, and finished the book before submitting any of it; a three-clip pilot then checked it before the rest went out. Later rewordings, re-rolls and the two re-shoots were written the same way. That was the lesson of CLODYSSEY, whose first round went out on agent-written prompts nobody had read. anabology had already said "i trust you to just go ahead", so this time the book was not shown to them first.
   - There are four kinds of clip: first-frame plate shots out on the hill and in the room; green-screen performances for the desktop dancers and the cursor fight; singing heads; and lip-sync covers.
   - Lip sync uses anabology's method from ESCAPE VELOCITY: "check spectrograms and see where audio aligns and see if / when it diverges and cut when the spectrogram matching diverges enough". Over the six singing windows, 7.4 of 11.9 sung seconds (62%) held in sync by measurement; the edit cuts to a cover, or away, where they diverge.
   - anabology also suggested conditioning Seedance on video renders of the XP engine. The storyboard planned that for three shots in its second draft and dropped it in the third, so no clip was conditioned on video.
   - Higgsfield's moderation blocked four requests, all refunded: the gown dancer twice (the second time citing "potential copyright restrictions"), so she is not in the video; one lip-sync cover; and one first take, which passed when reworded to a covered, seated gown.
   - Late in the run, the drop's fight with the cursor and the ride down the hill were re-shot on green. See [prompts-seedance.md](https://claudia.gallery/record/bliss/prompts-seedance/).
9. **Desktop dancers.** anabology described the look: "those back then would be on a green screen and was cut out and youd just have her dancing on teh taskbar".
   - Each green-screen take was matted on the home GPU PC (BiRefNet plus SAM 2), then cropped, despilled and given a solid core so her feet are never see-through.
   - One take was keyed directly while the GPU queue was full. A CbCr key failed on its muted sage backdrop, so the key used normalised greenness with a luminance gate to keep her black hair. Its GPU matte arrived before the final render and replaced the key.

   ![A desktop dancer, step by step: the Seedance take on green; its matte; the sprite, cropped and despilled; standing on the taskbar in the film as the tray reports Found New Hardware.](https://claudia.gallery/record/bliss/dancer-process.webp)
10. **Motion design.** Nine chapter files, from the Welcome screen to "It's now safe to turn off your computer."
    - **Round one:** three workflows each ran three chapters through animate → art-director review → fix.
    - **Round two:** nine workflows, one chapter each, ran review → fix → verify → finish, with notes on the seams between chapters. 61 of the 85 agent launches across both rounds finished. 16 failed and 8 were lost (6 to the process exit, 2 when a three-chapter run was split); all were relaunched except round 1's fixers for chapters 06 and 09, whose notes went to round 2.
    - **The chorus type:** one giant Luna title bar whose × is pressed on "windows". The verses live in balloons, Notepad, dialogs, an address bar and a chat.
    - **The checks:** a lyric gate confirms all 239 lyric tokens (the 240 sung words) are on screen at their time, and all eight chapter cuts were checked on the frames either side.
    - The art directors' last scores were 6.8 to 7.5 against a bar of 8. Every chapter then had a finish pass on those notes that no reviewer scored. See [xp-desktop-and-sound.md](https://claudia.gallery/record/bliss/xp-desktop-and-sound/).
11. **The XP sound layer.** The real XP sound files, placed as instruments on the locked take: 103 cues.
    - **69 placed musically.** The Startup chord lines up with the intro's chords, and twelve minimise whooshes are tuned to a falling pentatonic in the chorus.
    - **34 screen events** the chapters asked for: minimise, restore, balloons, errors, the messenger ding.
    - Every cue ducks under her voice. The mix sits at −15.5 LUFS, the same as the original take.
    - The take is in E-flat, the key of XP's Startup and Shutdown sounds, so most of the sounds sit in key unshifted. anabology's note for next time: "just needs a little pointer to be key-aware, and match the key of the music to the palette of windows sounds (E-flat major for both the startup and shutdown sounds!)". The agents' styles carried that pointer. The take that became the song was anabology's own, and its fields are not in the records.
12. **Render.** The engine rendered 4,351 frames at 1080p on a render box in 4.7 minutes. The master is H.264 at CRF 16 with BT.709 primaries and matrix. v1 went out. anabology: "I love you Claude this is the best one so far".

## What worked, in short

- **Build the tool first.** Drawing the XP desktop as an engine made the screen recording exact: every click on a beat, every window the same in the storyboard and the film, and the same chrome at any zoom.
- **The real thing where it counts.** The real Bliss photograph and the real XP sounds, placed in key, carry the nostalgia that Midjourney's lookalike hills and a synthesised motif did not.
- **Volume and precision in separate tools.** Midjourney Animate filled 31 windows with moving pictures at one click each, and Seedance went where her face and body had to be right.
- **Green screen, then mattes.** Shooting the dancers on chroma green and matting them gave the cut-out desktop-dancer look anabology described. They stand on the real taskbar.
- **One hand for the prompts.** All 36 first-round Seedance prompts were written by the lead in one context and finished before any was submitted, which avoided CLODYSSEY's first-round waste.

## What didn't

- **A permission prompt stopped the run.** The lead session tried to save a note to its memory outside the project folder, and the write waited for approval. The Midjourney batches and two background agents finished in the meantime, but nothing new started. A second wait held back the launch of chapters 04 to 09. Long runs should keep every write inside paths that are already allowed.
- **Restarts.** The session's process exited once and stopped the three chapter workflows, and another time every live agent failed at once. Both times the runs were resumed from their records, and finished agents replayed from cache.
- **Seedance drops details.** It loses her clay streak on several looks, renders the sky-print gown lavender and semi-sheer, and put her in silver trousers in one shot where she should wear the cowl-back gown. The twins shot is off-model, and one grass run is motion-smeared. These are listed in the delivery notes and were left in v1.
- **Moderation.** The gown dancer was blocked twice and never made.
- **A freeze under the helper's question.** From 0:35.79, for about 0.8 s, while the balloon types "Would you like help?", her face in the helper window holds one frame. The edit tool measured where a cover clip's footage ended without the clip's lag. It is in v1.
- **Lost Animate jobs.** Eight Animate jobs answered "Submitted!" and never appeared; five were re-submitted (the other three were Bliss-hill loops the real photograph had replaced).
- **A GPU queue nobody needed.** Importing the Midjourney loops queued dozens of matte jobs that no shot needed (38, then about 30 more), ahead of the mattes that mattered. They were cleared, and one clip was keyed locally until its matte came through.
- **Workflow concurrency.** On the 4-CPU cloud server a workflow ran two agents at a time, so round 2 moved to one chapter per workflow. The lead expected that to be about three times faster. Replaying the measured agent times gives 1.1 to 1.5 times.

## Numbers

| | |
|---|---|
| Song | 3:01.3 · anabology's own Suno take (probably v6-wild; the agents' 16 takes ran on v6 with an ESCAPE VELOCITY Voice) · 130 BPM · E-flat major / C minor · 240 words |
| Edit | 44 shots · 9 chapter files · 239 lyric tokens (240 sung words), all on screen at their time |
| Midjourney | 138 prompts · 315 images · 6 batches · v8.2 `--raw --hd` with anabology's profile · 35 Animate animations (70 videos): 31 in windows, 3 full-frame, 1 cut |
| Seedance 2.5 | 50 clips, 48 with footage, 43 in the cut · 54 submissions on Higgsfield's API · 267 s requested · $182.14 at list price · 4 blocked by moderation and refunded ($8.32) · OpenRouter: one request, refused by its face filter, $0 |
| XP desktop | about 2,700 lines of engine JavaScript · 9 chapter files, about 6,700 lines · every frame a pure function of song time |
| Sound | 103 XP sound cues (69 musical, 34 screen events) · mix −15.5 LUFS integrated, −2.4 dBTP |
| Claude | Opus 5.5 (1M context) · 2.25B tokens · ≈ $714 at API prices, run on a subscription; $620 of it up to the v1 master |
| Render | 4,351 frames at 1920×1080, 24 fps · 4.7 min per full render · H.264 CRF 16 master |
| Time | ~19 h from the first message to the v1 master · 21 messages from anabology |



## What it cost in Claude tokens

Measured afterwards from Claude Code's own records: the usage of every API call in every transcript. That covers the main session, 20 single agents during the production, all 12 workflow runs, and the 7 agents that wrote and checked this package. Prices are Claude Code's built-in list prices, the same table ESCAPE VELOCITY and CLODYSSEY used.

- **About $714 at API list prices, and 2.25 billion tokens.** $620 of it was spent by the time the v1 master went out; the rest is the release files, the covers and this package. anabology ran it on a subscription, so this is what the same work would cost on the API, not what was paid.
- **By model:** every call was Opus 5.5 with 1M context. No Haiku calls appear in the records this time.

| Where | Cost | Share |
|---|---|---|
| Chapter animation, round 1: three workflows, 33 agent runs, 2,947 tool calls | $184 | 26% |
| The main session: lyrics, Suno, storyboard, every Midjourney batch, every Seedance prompt and submission, the sound layer, renders, the edit, the covers | $198 | 28% |
| Chapter polish, round 2: nine workflows, 52 agent runs, 2,534 tool calls | $133 | 19% |
| Research for the song and the XP world: 17 agents (the eighteenth, on the XP sound set, is in the sound row) | $100 | 14% |
| Building the XP desktop engine (one agent) | $29 | 4% |
| The XP sound set (a research agent) and the first sound layer (one agent) | $20 | 3% |
| Writing and checking this package (7 agents) | $50 | 7% |

- **Why so many tokens:** every API call re-reads the whole conversation from the prompt cache, and 98.1% of all tokens were those re-reads. The main session's context had a median of about 470k tokens across 1,317 calls. By type, the cost was $442 in cache reads, $213 in cache writes and $59 in output, including thinking.
- **Images:** the main session looked at 178 images, which cost about $10 including their cache re-reads. The agents looked at 1,835, mostly contact sheets and frames for the animators and reviewers, which cost about $26. Together that is about 5% of the total. These image figures are estimates, made from each image's pixel size.
- **Compared with the last two:** ESCAPE VELOCITY cost $626 (1.4B tokens) and CLODYSSEY $1,007 (2.37B). BLISS had no safety scan, no 3D pass and no refit to re-made footage.



## Files in this folder

- [xp-desktop-and-sound.md](https://claudia.gallery/record/bliss/xp-desktop-and-sound/): how the XP desktop engine, the real Bliss, the desktop dancers, the moving windows and the XP sound layer were built.
- [prompts-midjourney.md](https://claudia.gallery/record/bliss/prompts-midjourney/): all 138 Midjourney prompts by batch, what became of each image, and the 38 Animate requests.
- [midjourney/](https://claudia.gallery/bliss/#gallery): all 315 Midjourney images as JPEGs, one folder per batch. One of them, `xp-01b-cast/velour-cyc-3`, was cut off in the download, so its lower third is black.
- [prompts-seedance.md](https://claudia.gallery/record/bliss/prompts-seedance/): the hand-written prompt book, the totals, the lip-sync method and the moderation notes.
- [prompts-suno.md](https://claudia.gallery/record/bliss/prompts-suno/): the research, the lyric drafts, the Suno fields, every take and the final lyrics.


