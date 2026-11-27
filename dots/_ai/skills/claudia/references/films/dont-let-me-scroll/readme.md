# How DON'T LET ME SCROLL was made

**DON'T LET ME SCROLL** is a 2:37.8 music video, the sixth Claudia film after ESCAPE VELOCITY, CLODYSSEY, BLISS, AIRPLANE MODE and DOWNFORCE. It is cut to anabology's own song: a UK garage 2-step track at 133.39 BPM with an all-female vocoder vocal, 2:40.8 long; the final cut starts at the song's 0:03 with a 2-second audio fade-in. The song is one night of doomscrolling: X, a reel stolen from Pinterest, Alexander Graham Bell, every app blocked but LinkedIn, Chrome and the stocks, three choruses of "Don't let me scroll", and an extended ending that sings "Don't sell my soul" and "Be free". The look is ACID FEED: the acid-blur moodboard taken a hundred times further and moved inside a phone, with BLISS as the template. The world is the phone's own interface rebuilt in code (X, Instagram Reels, Pinterest, Screen Time, LinkedIn, Chrome, Stocks, the Dynamic Island, the lock screen, Bell's 1876 telephone patent), and Claudia is rotoscoped into it. She never sings. The phone does: the Dynamic Island carries the vocoder as a waveform, while she scrolls, swipes, taps and dances on the beat, and every sung word is drawn on a real surface in the scene at the moment it is sung. Blur is speed and sharpness is attention: what she scrolls past smears by its real scroll velocity, and the acid colour is real thin-film interference, stirred by her dance. At the end she leaves the phone for a world without one, in a single shot up a staircase on a wall painted as sky to a lit door.

It was made in about 25 hours of wall-clock time in October 2026, from anabology's first message to the final. v1 went out and anabology sent notes on it; v2 and v3 followed, and anabology gave the go for the final render: "ok cool both look fixed! B is good. slice those in and render and we're good!"

- **anabology** directed. They wrote and made the song and its lyric (the Suno take is theirs), asked for the look to come from the moodboards, set the brief for the 100× acid blur and the stocks moment, and picked the wardrobes, the plates they corrected, the new looks, the phone-free world and the face reference. They sent notes on every version and approved the final. That is 43 messages in all, 39 of them up to the go for the final render.
- **Claude** (Anthropic's model, running in Claude Code) was the production lead. It proposed ACID FEED and wrote the plan, the story, the storyboard and the kit's contract. It wrote every Midjourney, Wan and Seedance prompt, screened the plates, and built the take pipeline (the roto queue and the beat warps). It judged every take, aligned the outfit swaps, spliced the re-lights into the cut, and made the renders, the checks and the deliveries.
- **Claude agents** built the kit (five builders), animated the nine chapters (an animator per chapter, with its own art-director passes) and did the v2 rebuilds: 32 agent launches in all.
- **Tools:** Midjourney made her plates, the feed's pictures and its moving loops. Wan 3.0 and Seedance 2.5, through Higgsfield's API, made her takes: Wan the gestures and the bedroom, Seedance the dances that had to land on the beat and the escape. Seedance also re-dressed and re-lit, and Wan re-lit and repaired finished shots. BiRefNet cut her out of the takes and OpenCV carried the cut-outs between keyframes. Suno made the song (anabology's own take). A custom JavaScript engine with a kit made for this film, ACID FEED, draws the world: scroll physics, thin film, the phone's interface.


Times written as 0:55 are times in the song. v1 and v2 start at the song's 0:00; the main v3 cut and the final start at its 0:03, so anabology's notes on those two read 3 seconds earlier than the song (a v3 test cut from 7.5 s also went out). Where it matters, the shot (S01–S35) is given too.

---

## The spark

anabology's first message, with a first take of the song attached (2:12.8):

> yo - i wrote this song:
>
> [Verse 1]
> I scroll on X, to see, hopefully,
> The posts that give me Ecstasy
> The big man in Texas: E,
> He runs Space X, for free
>
> [Chorus]
> Don't let me scrolll
> You keep asking me to go
> But I have to scroll
> Don't let me scroll
>
> [Verse 2]
> Another reel on Instagram,
> It's stolen from pintrest, fam
> They call me Alexander Graham
> Bell, on my phone like damn
>
> [Chorus] …
>
> [Verse 2]
> All the apps are blocked,
> Now LinkedIn just rocks,
> Google Chrome, on my Phone
> Checking on some stocks
> They put reels on LinkedIn
> I should feel more Locked In
>
> [Chorus] …
>
> can you explore […] and the previous music video projects, our moodboards/design styles we made, and suggest a visual style from this video from our styles we made?

(The full sheet, with all three choruses, is in [prompts-suno.md](https://claudia.gallery/record/dont-let-me-scroll/prompts-suno/).) Two agents surveyed the library: one the 28 named moodboards, the Are.na picks and the approved faces, the other every earlier film's look and anabology's verdicts on it. The first reported that only two boards had ever been approved. anabology wrote back: "remove the approved/not approved distinction, all moodboards are up for grabs."

Later, the lead proposed **ACID FEED**: "BLISS's approach applied to a phone: the lyrics live on real app surfaces, the way BLISS lived inside XP. acid-blur sets the motion and hyperbloom sets the light." The acid-blur board is colour smeared by motion under small sharp type, which is what a feed looks like mid-flick. Each part of the lyric had a surface: the verse on an X post in dark mode, the reel with the Pinterest watermark burned in, the Screen Time limit sheet, LinkedIn, a Chrome stock ticker. Two alternatives came with it: a risograph feed after anabology's favourite AI video, and the clean look of CLODYSSEY. (The same message read the first take as about 89 BPM. That was wrong; see step 1.)

Later, anabology sent the final song, "an extended verison with better ending (title: Don't Let Me Scroll)", 2:40.8, and the brief:

> acid blur is great. what's the 100x version we can do with acid blur? bliss was amazing because we used so much movement from midjoruney, such great roto, so many interactions between code and the characters. thats really what i want - an environment made of code that FEELS ALIVE. and we can do this! its a good song for that. Claudia acid-blur, she's scrolling, she's not really singing in this, we're just following her story and its lively, she may dance. but on beat. and we have amazing code-generated environments that top tier motion designers would be jealous of. the one thing: when shes scrolling stocks on her phone, i wanna see her look at her phone and its a small stock on the screen: [a stock with her name] and its pumping/crashing/pumping. but yes acid feed and i want you to take teh creative reigns - but know we learned a LOT making Bliss and that should be the best template. Be extremely creative, try really hard, i believe in u. We can use Wan 3.0 for vids for a bit cheaper than Seedance 2.5 - default to Wan and if it doesnt work well then use Seedance for tricky scenes.

Then: "oh and the stock thing: have tsla spacex then claudia as the stocks". So the stocks she scrolls are TSLA, then SPACEX, then a made-up stock with her name.

Later, the lead answered with the 100× version, in five rules taken from physics rather than from a filter:

- **Smear is scroll velocity.** Everything she scrolls past smears vertically by its real on-screen speed, using the phone's own scroll physics: momentum decaying at 0.998 per millisecond, the rubber band at the ends, the paging springs. What catches her eye slows down and snaps sharp. This is the moodboard's MOD poster, its vertical streaks.
- **Colour is thin-film interference.** The acid colour is the physics of a soap film or an oil slick: magenta, gold, green and blue bands that exist only where something moves, stirred by her dance and her taps. This is the board's Macao poster, an iridescent ribbon seen through black pill-shaped slots.
- **Shape is the phone's own geometry:** the Dynamic Island's pill, the banners, the icon grid. No invented ornaments.
- **She is rear-curtain flash photography:** sharp, with colour trails behind her.
- **Type is soft and huge against sharp and tiny:** Nimbus Sans Bold for display, IBM Plex Mono for the small tags, the real apps' faces for the interface.

The same message carried a story draft (one night, 11:58 PM to sunrise, the feed spilling out of the phone into the room) and a look test of four night wardrobes: A white silk-satin pyjamas, B iridescent satin, C an acid-green mohair sweater, D black. The lead recommended A for the whole night. Five agents were already building the kit. Later, anabology answered:

> hmm sure i lets just use all 4 tbh but i want roto and most the environments to be code generated? because shes in the code, shes in the world made by the phone. btw the styles of the song if it helps:

Their style text followed (verbatim in [prompts-suno.md](https://claudia.gallery/record/dont-let-me-scroll/prompts-suno/)): bass-forward UK garage, swung 2-step drums, a wobbling sub bass, chopped vocal one-shots on the offbeats, "all vocals female vocoder". The 2-step in that text showed the lead its tempo reading was wrong (step 1). Later, it sent the second story draft. The real bedroom only frames the film. In between, she is matted into the world the phone makes, and the feed dresses her: A in the bedroom, and each refresh inside the phone re-skins her into B, C or D. The phone sings and she never lip-syncs. The song's biggest hit is the final drop at 2:00.67, so the extended ending became the climax. It asked anabology to confirm the four lines of that ending the transcription could not be sure of: "Don't let me scroll" at about 2:09, "Don't sell my soul" at 2:17, "Be free" at 2:20 and "I scroll on X" at 2:39. anabology: "yeah sounds right".

## The film, chapter by chapter

The final cut, in song time (the cut itself opens at 0:03). Four looks dress her: in v1 they were A to D; v2 replaced the pyjamas with E (an oversized white "morning after" shirt over skirts) and F (a red coat dress with a white collar and a red beret), and kept C and D.

| | Song time | What happens |
|---|---|---|
| 01 The hook | 0:00–0:14.51 | One living poster in the grammar of 0:55: soft grey paper, black pills that open like eyelids onto her eyes and onto the phone glowing under her hand (the bedroom take, re-lit). "11:58 PM" stands on the right edge, with X marks in the top corners and a scroll-down chevron after the Macao poster. On the pad stabs DON'T / LET / ME / SCROLL slide in as word pills, a ribbon of film running through them. The lock screen wakes inside the pills on a soap-bubble wallpaper, the Dynamic Island drops "26 new posts in For you", and the count rolls on to 28 on the two vocal chops. Her face, lit by the screen, rises into the pills as she scrolls; on the first kick the pills open and her face is whole for a beat. "I" lands at the bottom left as it is sung, and the island swallows the frame into chapter 02. Both bedroom takes play at their own speed. |
| 02 X to see | 0:14.51–0:30.71 | Look E, with a lavender pleated skirt. The camera falls out of the island beside a giant dark-glass X screen. She stands on the right third and swipes the feed with her palm: the feed is locked to her hand, then coasts on iOS momentum. Her post, "I scroll on X, to see, hopefully,", carries a designed acid-blur poster (FOR YOU, thin film streaked by the real scroll speed) where v1 had a moon photograph. On the hit she double-taps the next post in the air, X's like burst comes off her fingertip, and the film's first colour blooms out of it. X — TA — SEE land as paper pills and merge into ECSTASY on her clap. At dusk a colossal white E rises out of the glass in jolts and locks on "E,"; a Seedance re-light turned the passage into a glass E under a thin-film sky. She spins between two posts, "for free" is a $0.00 tag swinging on a string, and the page is pulled down into the refresh on "Don't let me scroll". |
| 03 The river | 0:30.71–0:58.59 | The refresh re-dresses her (the shirt over a white satin skirt) in a room made of the feed: reels, pins and posts pour over the walls and the ceiling, re-lit by Seedance as a real room. "You keep asking me to go" is the body text of Screen Time's limit sheet, a frosted-glass slab the height of a building rising behind her. On "But I have to scroll" she pushes the car-sized Ignore Limit pill until it gives way; Wan re-lit the shot, completed her back foot and held her face to the reference. In the tunnel the feed is seen up its scroll axis and she dances in a black pleated skirt with trails of film light. The stutter, "don't, don't let let me scroll", re-triggers her take on each chop, so her move repeats as the voice repeats, and the words stamp beside her. Then 0:55: grey paper, black pills budding out of the island in the Macao poster's rows, her own film inside them, and she dances between them. The island swallows the frame. |
| 04 Reels | 0:58.59–1:13.89 | Look C. The reel launches out of the island and she stands inside it, a reel the size of a wall, paging on the kicks. "It's stolen from Pinterest, fam": the reel flies down a nave of pins to the same picture hanging as a pin, a hairline and MATCH 98% join them, and the Pinterest watermark stamps onto the reel. "They call me Alexander Graham": a close-up of her on a vintage receiver while Bell's 1876 patent drawing (sheet 2, Fig. 7) draws itself on planes around her head, the cone at her receiver, the current on the wire following the vocal, the signature writing itself on "Alexander Graham". "Bell, on my phone like damn": the lock screen's clock as glass digits holding a draining soap film, the bell drops out of the island and swings, and the buzz floods the phone on "damn". |
| 05 Wind down | 1:13.89–1:28.28 | The breakdown. The world dims, Wind Down's moon rises, and she lies sleepy on the glass, her face on the right third and the clock skyline on the left. Wan re-lit the shot as a real dark bedroom, removed a stray foot and, with the face reference, slimmed her face. Two taps on the fill wake the world for the re-drop. She dances inside a reel standing like a doorway, hearts thrown off her moving edges, the like count rolling. Then a new dance on the right third, with the feed as a column on the left whose posts carry BUT / I / HAVE / TO / SCROLL as she spins (Wan completed her sleeves). |
| 06 Locked in | 1:28.28–1:40.87 | Look D. A canyon of app icons greys out in Downtime's wave of hourglasses as she walks; LinkedIn stays lit and she shrugs on the blazer. There is no phone in her hand. Behind a giant Liquid Glass screen she types "stocks" into Chrome and swipes TSLA, SPACEX, then a made-up stock with her name, which pumps, crashes and pumps under her fingertip while the world's light goes green, red, green. Wan re-lit the shot with the face reference, and the interface was put back pixel for pixel. The LinkedIn banner grows into a glass atrium of reels, Seedance's replacement for a flat blue background. The lock screen's 4:13 stands as ray-traced liquid glass, and a padlock shackle closes round the frame on "Locked In". |
| 07 Overdrive | 1:40.87–1:57.07 | Notifications rain from the island and pile up around her as glass slabs, re-lit with the digits, while the clock races. 5 %, then Low Power. On the re-drop: KEEP / ASKING / ME / GO as word pills with her film, and her hardest dance. The tunnel at 1 %, the scroll slowing like a dying motor; her last flick, the freeze, and the power cut on the bass drop. The dead-battery icon. |
| 08 Be free | 1:57.07–2:25.85 | Look F. Her face in the dead phone's black glass; on a vocal chop the glass contracts to a pill round her eyes and rises into the island, uncovering the paper. The final drop (2:00.67, the song's biggest hit): she explodes out of a crouch, and three pills slam in carrying her other selves, dancing (the white shirt and black skirt, the green mohair, the black). They peel away on the bars; Wan completed her hands in the jump. The island sings DON'T / LET / ME as word pills while her arms rise into it. SCROLL is a masthead of letter windows with her film rising into them (Wan, with the face reference). "Don't sell my soul" is Facebook's tracking prompt, floating beside her; she taps Ask App Not to Track on "soul". BE / FREE flank the island, the pills build a staircase, and the island opens like an eyelid into a window of painted sky. |
| 09 The escape | 2:25.85–2:40.80 | The camera pushes through that window into its light, and a world without phones resolves out of it: a calm sea, a vast wall painted as sky, a white staircase climbing it to a small lit door. One Seedance shot plays at its own speed. She climbs as the camera zooms toward the door and looks back on "I". "I SCROLL ON X" is painted on the plaster beside the door, tracked to the wall, with the X cut through it and lit from behind. She steps into the light, and the film ends in it. |

## The stack

| Role | Tool | How it was used |
|---|---|---|
| Director | anabology | The song and its lyric, the ask to draw the look from the moodboards, the brief for the 100× acid blur and the stocks moment, the picks (wardrobes, a corrected plate, the new looks, the shirt, the world, the face reference), three rounds of notes, the approval |
| Production lead | Claude (Claude Code, Opus 5.5) | ACID FEED, the plan and the story, the storyboard, the kit's contract, every Midjourney, Wan and Seedance prompt, the plate screen, the take pipeline (roto queue, beat warps), every take's verdict, the swap alignment, the re-light splices, renders, checks and deliveries |
| Agents | Claude agents (Opus 5.5) | 32 launches: two surveys (the moodboards, the earlier films), five kit builders, 15 chapter-animator launches for v1 (nine chapters; six launches interrupted and relaunched), and 10 for v2 (the Apple-precise interface, the fixes, the call sites, the hook, chapters 02, 03, 05–06, 08 twice and 09) |
| Art department | **Midjourney v8.2** `--raw --hd` with anabology's personal profile | 130 prompts in 7 batches, 516 images: the look test, her plates, the feed's pictures, the v2 looks, worlds and actions. 40 Animate submissions gave 22 moving loops for the feed. |
| Her takes | **Wan 3.0** on Higgsfield's API (image-to-video) | 38 takes from Midjourney first frames: her gestures and the bedroom in v1, the swipe, the double-tap and the red-look takes in v2 |
| Dances, swaps, re-lights | **Seedance 2.5** on Higgsfield's API (reference-to-video, video-edit) | 13 reference-to-video takes: 12 dances from a first frame and the shot's instrumental, and the escape from a first frame and a still of her look; 26 video edits: 16 outfit swaps, 9 re-lights, 1 face edit |
| Repairs | **Wan 3.0** reference-to-video | 10 passes over finished shots: re-lit, limbs completed, a stray foot removed, her face held to a reference |
| Song | **Suno** | anabology's own take; the records do not say how it was made |
| Roto | **BiRefNet** (rembg) and **OpenCV** | BiRefNet general-lite on every third frame, OpenCV DIS optical flow carrying the cut-out between, on the render box's CPUs |
| Analysis | htdemucs, Whisper, ffmpeg | Stems, the beat and hit maps, word times, loudness, encodes |
| Motion design | A custom JavaScript engine and the ACID FEED kit | 9 chapter files, 35 scenes, on 12 kit modules; every frame is a pure function of song time |
| Render | Headless Chromium on a render box | 3,859 frames at 1920×1080, 24 fps, for each full version; the final cut is 3,787 of them |

## v1: how it was made

1. **The song and the grid.** anabology's extended take is 160.80 s of 48 kHz, 16-bit stereo. The analysis split it into stems (htdemucs) and read beats, sections and words. Its first tempo was 89 BPM. anabology's style text said 2-step, so the lead checked the kick spacing: the song runs at 133.39 BPM, and 89 had been a lock onto two-thirds of the tempo. One constant grid fits the whole song: a bar of 1.79922 s from 0.118 s, 358 beats and 90 bars, phrases of eight bars from bar 1, drops at bars 17, 43 and 59, and the biggest hit at bar 67 (2:00.67). A hit map gives the cuts and the camera something to lock to: 327 kicks, 241 snares and claps, 543 hats, 17 impacts, 19 risers and 12 vocal entries. Word times come from Whisper (large-v3 and medium) on the vocal stem with the line windows set by hand: 31 lines and 148 words. The vocoder blurred the ending, where Whisper heard "don't let me go"; anabology confirmed the words (above).
2. **The kit.** Before any plate was made, the lead wrote the kit's contract (`engine/af/AF.md`). Five agents built it in parallel: A the scroll physics, the smear and the feed; B1 the phone's system interface; B2 the apps; C the thin film; D the ticker, Bell's drawing, the light and the clock. Its rules: every frame a pure function of song time, deterministic noise, software canvases, no flash inside a scene, real references, the phone called "the phone" and never drawn with a logo. Eight systems came out of it:
   - **The feed**, with its card worlds: a glass floor, a column, a river, a tunnel, a wall.
   - **The film:** thin film in a soap film of index 1.33, 0 to 1,500 nm thick, through the CIE 1931 observer and D65 into sRGB, checked against an independent colour-science table. It runs as a stable-fluids simulation (Stam 1999, with vorticity confinement) whose dye is the film's thickness, stirred by her mattes. The bakes are deterministic: the same input gives the same bytes.
   - **The island:** the Dynamic Island, which breathes, morphs into banners and sings.
   - **The wall:** the home screen as architecture, greying under Downtime.
   - **The ticker:** seeded price processes on the beats. Her stock pumps 160 %, crashes 58 % and pumps 240 %.
   - **The bell:** Bell's 1876 patent drawing (US 174,465) traced into strokes that draw themselves, and the notification bell swinging as a real pendulum.
   - **The light:** the screen as the light on her.
   - **The clock:** the status bar as the story's clock, 11:58 PM to dawn, the battery from 100 % to dead.

   All five builders were done.
3. **The storyboard.** Draft 1 went to anabology: 35 shots on the bar grid, all 31 lines on a surface, and 37 takes. R takes are the real bedroom. P takes are her alone on a plain grey backdrop, to be rotoscoped into the code world. G takes are the three ghosts of the final drop. The looks follow the story: A in the bedroom, B for chorus 1, C for verse 2 and chorus 2, D and the blazer for verse 3.
4. **Midjourney.** The look test ran. The performance plates followed: 38 prompts, her full length on mid-grey at 9:16 for clean roto, and the bedroom at 16:9. The feed's pictures ran: 54 prompts of X photographs, reels, pins, LinkedIn pictures and acid-blur photographs. The lead screened all 152 plates for face, age and anatomy, picked one per take and showed each pick large beside its three alternates. It took out a plate where a stranger's hand held a blade. anabology: "looks good - these all will be roto'd and put in code generated envs right? p24 s24 pick has 3 arms lol. need to check those. chose 24-4 instead. go ahead tho". The lead's screen had run on thumbnails about 230 px tall. From then on every pick was checked at 800 px or more. Midjourney Animate turned 22 of the feed's pictures into moving loops. See [prompts-midjourney.md](https://claudia.gallery/record/dont-let-me-scroll/prompts-midjourney/).
5. **The takes.** Wan first, as anabology asked. The prompt book (37 takes, $39.80 at list) went to anabology with the plates. A three-take pilot went out ($3.20). Her identity held, and the stocks shot came back with a flat green screen her thumb crossed, ready to key. Wan's dance was weak: it held the first pose, reset, then shuffled. One Seedance take that heard the song went straight into a real two-step. In it, @Audio1 is the shot's own window of the instrumental (drums, bass and the rest, no vocal), used "for rhythm and timing only". So the nine dances that had to land on the beat went to Seedance, and the 25 other takes to Wan. Seedance's output filter blocked the drop dance in white satin twice ("The generated result was blocked by content safety checks"). Both runs were refunded and Wan made it. The runner refuses a job that would pass its cap at list price: at $40 it stopped ten Wan jobs, which went out again under a $75 cap. All 38 takes were in: $60.00 at list, $52.60 after the two refunds. See [prompts-video.md](https://claudia.gallery/record/dont-let-me-scroll/prompts-video/).
6. **Roto on a CPU box.** No GPU was available for the mattes, so BiRefNet ran on the render box's CPUs, at about 4.6 s a frame; 38 takes would have taken about a day. The roto tool was rewritten to run BiRefNet general-lite only on every third frame and the last. Dense optical flow (OpenCV's DIS, on a half-size grey copy) carries the matte from the two neighbouring keyframes, blended by distance, and a light temporal filter calms the edges where the picture barely changed. That ran at about 1.6 s a frame, three times faster, or one take every four to five minutes, through a queue that worked in chapter order. Hair edges and the headset cable survived it.
7. **Beat warps.** `tools/beatwarp.py` finds each take's motion accents and maps them onto the 133.39 BPM grid with a piecewise-linear map from song time to take time, so her steps land on the kicks. In v1 the map could run a take between 0.7× and 1.45×. Five to eight accents per shot landed on beats. The slowdowns became anabology's second note.
8. **Nine chapters, by agents.** Each chapter was one file and one animator agent, working from a shared brief (`wf/CHAPTER-BRIEF.md`) with these rules:
   - every sung word on a real surface at its time;
   - the lyric as part of the composition, never karaoke;
   - linger rather than cut;
   - the camera locked to the kicks, stabs, chops and risers;
   - no flash inside a scene;
   - real references and real maths;
   - blur is speed;
   - her on screen 70 % of the time, never painted over, in her native colour.

   Each animator did at least two art-director passes of its own (contact sheets, 100 % crops, an MP4 with the song), ran the checks and kept a notes file. Six launches were interrupted and relaunched; the notes files let each new agent pick up where the last had stopped. The chapters landed one after another, 01 first and 08 last. Some of their finds became rules for the whole film:
   - Chapter 07 found that a 2D canvas made without the software flag pushed the frame onto the GPU, so later frames drew their edges differently. Every canvas in the film became software-backed.
   - Chapter 03's tunnel strobed (below).
9. **The checks.**
   - **Lyrics:** 148 of 148 words on screen at their time.
   - **History:** frames rendered out of order matched to the pixel on four pairs across chapters.
   - **Flashes:** 7, at most 1 in any second against a limit of 3.
   - **Strobes:** a scan of every 120-px cell (`tools/flicker.py`) found the tunnel at 0:43–0:46, where 29 of 144 cells alternated light and dark for nine frames. The near cards were swapping bright and dark every frame, and only the largest cards were smeared, so cards flipped between streaked and sharp. The near cards now fade hard, every card smears and the scroll is capped near 5,600 pt/s.
   - **Seams:** the seam sheet caught a one-frame dark blink at the cut from chapter 08 to 09, a frame an earlier render had left behind.

   The first 30 seconds went to anabology.
10. **v1** went out: 3,859 frames at 1920×1080, 24 fps, a 211 MB master, a review copy and a 720p copy. The lead's own list for the next version: her small in three wide shots, the SCROLL shot gentle because the take's arm sweeps were slow, and "I scroll" sung while she was still turning. Generation had cost $60.00 at list.

## The notes on v1

anabology's notes came, in one message, verbatim:

> ok pretty cool but a lot to change. we can do reshoots with seedance to make stuff better or mj reshoots then wan again as well.
> 1- opening shot with phone - the phone is like double layered, looks weird.
> 2- the clip where she looks on her phone at 8 seconds, never slow these down. you lowered the framerate for no reason, just looks bad. theres no compelling intro or story here, the opening should already introduce part of the story. i would maybe say uise the moodboard at the intro creatively to start so its immediately compelling. we always need a hook.
>
> 0:15 - roto is mid, also, i think compositionally this is not great. i think a lot of these shots could use new visual compoisitons - the elements you chose are usually GREAT, what is nto great is where she is placed in the screen. it should be like photography, i feel weird looking at a clipped off  the edge ost and a claudia in the middle bottom of the screen. please rework visual composition adn layout of basically most of teh scenes here. id love to see her interacting with the environment for example - what i think would be cooler here would be her a little bit bigger, the moon post replaced with some acid blur themed pic design post, and shes happy and playful and scrolls the actual post - instead of looking down at her phone. she could reach over and scroll up with her arm and thats what we roto and make her interact w the actual environment and post.
> 0:19 - same thing - its just a post overlaid infront of her. need some sort of interaction rather than her looking down at her phone. she's immersed in the scrolling.
> 0:24 - yeah this E and the scene layout is not good still... ya know, i would even give the entire rendered scene you made here to seedance and tell ti to video edit and fill out the environment lushly. this could be a good way of remaking scenes - maybe you can try this first and show me. you could  give it the entire E scene, tell it to move the tweets inward, fill the environment with beautiful glass acidblur lighting, reredner the E to be a better mateiral. I think that would work well. but ideally we use seedance mostly for re-texturing adn cleaning, and we do the recomposition ourself with animation. seedance is wonderful for mastering an animated prompt - load the skill for it, you will describe in real depth.
> 0:26 dont love her pose here. doing some weird stretch with stubby legs. also the E is broken now - the upper line overlaps infront of the top line on the E. hnestly i would give her a more feminine outfit by this point too, shes in scroll /dreamworld and should look like it.
> 0:34 i like this scene, but agian yeah i woul dprefer some skirt outfit by this point. her dance is nice, but would change outfit. and again, maybe give to seedance to light the scene with ray tracing and beautiful lighting as if it's a real room. 0:38 has another layering issue - the time limit is behind some scenes and infront of others. the left tiktok scene that looks like it should be behind is in front.
> 0:44 yeah the animation of her with the afterimages is cut off on the right and left - like why have a bounding box?
> and yes... no more silver pajamas by this point please. dont like for rest of vid.
> 0:55 LOVE THIS. THis is the best part. more like this!!!! the opening should be on this tier. outfit again should change but the animation and style is SO good.
> 0:58 ok great her outfit is changed. this is a better outfit, but dont use this earlier.
> 1:10 - 1:17  shots - composition again, its good assets but not a nice rule of thirds or photography like feel.
> 1:24 - would do a differnet dance
> 1:28 -  the app notification shade is too small for the text, there is all this text on it and it just overlaps with the edges and has no proper margins. same with 1:32 on / 1:36.
> 1:34/1:35 - her phone is slop - the back of her phone is used as the screen, its silly. she shouldnt really be looking down on her phone, she should be immersed in a world and the screen of her phone should be large on the screen and she interacts with it, rather than a literal phone. it feels bd to look at someone scrolling, especially when the model picked the ... back of the phone.. not even the screen.. to overlay the screen on.
> 1:40 - another prime exmaple of a seedance re-light: relight the scene adn the numbers/letters to be ray traced liquid glass with chromatic aberration and prismatic effects, rather than your crude renderings. same w the next scene.
> 1:46 - LOVE THIS!
> 1:55 love the last 10 seconds but again the notif shade is not rendered how apple would do it. rounded corners not mathematically precise, margins weird. colors not perfect (relight or remake to be more liquid glass).
> 2:00 no more silver pj's. at this point the same acid blur effect is old, id change it to more moodboard geometry inspo.
> the moodboard geometry inspo at 0:55 is so good, that could be the entire end.
> i think the waking uip and plugging in phone at the end is boring. she should enter a world with no phones, like escaping the truman show. it should be grand, art house, almost like wes anderson.
> 2:40 same thing - liquid glass not great, margins bad. fix then probably re-light.
>
> get to some seedance re-ligiht samples on the places where we can just re-light without recomp and kick off all the reanimation / recomp / etc edits on our side before we re-light the rest.

What the times pointed at, in v1:
- 0:08 was the bedroom take, mapped by hand at about half speed.
- 1:34 was the stocks shot. The green surface Wan had drawn was the back of a phone, and v1 had tracked the screen onto it.
- 0:55 was chapter 03's last shot, her on grey paper among black pills with her film inside them. 1:46 was chapter 07's word pills.

Those two loved shots became the bar for the rest.

## v2: how it was made

11. **The plan** (`wf/V2-PLAN.md`). The two shots anabology loved share one grammar: pills (the Dynamic Island's shape), thin film, bold Nimbus type, and her big and sharp. v2 moves the film toward it and away from rooms crowded with cards. Its rules for every shot:
    - Compose like photography: rule of thirds, her big, every card fully inside the frame with margins.
    - She touches the world and never looks down at a phone; when the phone's screen matters it is large in the world and she works it with her hands.
    - Never slow a take.
    - The interface is Apple-precise: continuous corners, real margins, text that fits its platter, iOS 26 Liquid Glass.
    - Re-light with Seedance only once a shot's composition is final.
    - New outfits after the bedroom.
12. **Seedance re-light samples.** Four Seedance video edits of v1's own frames went out ($47.81), written with Seedance's prompt skill as anabology asked:
    - **The lock screen's digits** came back as thick liquid glass with prismatic fringes, the interface type still crisp.
    - **The E** became one solid glass letter, which also fixed its broken top bar, but the posts did not move inward. Seedance re-textures; it does not recompose.
    - **The river's** re-light was too subtle.
    - **An outfit test** re-dressed her in a skirt with her face and her dance intact. That made re-dressing the old takes possible instead of reshooting them.

    anabology: "oh yeah the relighjts are great. but yeah... you missed on these relights the change of the outfit / poses / margin so kinda a waste on the excess ones. but yes lets do reshoots after all the fixes." The order became fixes, then reshoots, then re-lights.
13. **Four agents at once**, launched, then a fifth:
    - **The kit's interface, Apple-precise.** The agent measured Apple's own iOS 26 screenshots: a notification platter inset 13.5 pt with continuous corners of radius 24 and 8-pt gaps, the tracking alert 320 pt wide with radius 33, and the Dynamic Island's sizes from Apple's design guidelines. Corners follow the continuous curve of iOS (PaintCode's published constants), platters grow to fit their text, and a Liquid Glass shader refracts the scene behind each platter. The island stopped slicing its text as it collapsed ("Graham" at 1:10).
    - **The fixes.** The E became one extruded outline, so no bar can draw over another. The posts sit inside the frame. The limit sheet is layered by its own plane. The trails have no bounding box. 1:10–1:17 sit on thirds.
    - **A new opening hook** in the 0:55 grammar.
    - **The final drop** rebuilt in the same geometry.
    - Later, a fifth agent updated seven call sites in the chapters for the new interface, among them a double ring at 1:55.
14. **Never slow.** The fixes agent found the cause of "you lowered the framerate": in v1, every take the beat warps timed had stretches at 0.70–0.89×, not just the one at 0:08. One chapter's own map fell to 0.53×. The beat-warp tool now has a floor of 1.0 (its range is 1.0–1.45×), all 28 warps were regenerated, and the six shots longer than their takes were flagged. The stutter shot became a sampler: the take plays at exactly 1× between triggers, each vocal chop re-triggers a cue point, and a repeated syllable re-triggers the same cue. No frame is held or slowed.
15. **Wardrobe.** The v2 looks ran in Midjourney as ten prompts: three dream-world looks for 0:14–0:58, three escape looks, and four worlds without phones. The lead screened them. Three images read young; the mustard pinafore with knee socks read young overall; the mountain hotel was too literal a copy of a famous film's hotel, with garbled lettering on its front. Later, anabology wrote "can you show me exactly what i need to pick? sorry its far back in convo history", and:

    > dream outfit: e2 pink 2 is the only one of all 12 that looks good there. f3 red 2 is eprfect. . you can use mustard and pink for the earlier ones to replace the e1/e3 if you needed more shotsthan just e2 pink 2. w4 exit 1 feels best, if we did a zoom in shot.

    Then: "ok sweet. try to get this to a final version asap now - dont rush it but do the re-lights and apply all the edits and re-gens with new outfit. we dont need excessive 'reviewers' after, ill stay in the loop and can do a visual review faster and more comprehensively than an opus reviewr can do it." Later, the dream look changed: "wai ti dont like the reference. can you make her have like a white oversized button down shirt like 'morning after' look" and "still with a skirt". Three skirts went to Midjourney, and anabology picked "s1 1 and 3, s2 2, s3 1 and 2". The lead laid them out as a progression with the white shirt as the constant:
    - lavender pleated for the X world (0:14–0:30);
    - white satin for the river (0:30–0:43);
    - black pleated for the tunnel through the 0:55 pills (0:43–0:58), and for her dream-self ghost in the final drop.

    The red coat dress (f3-red-2) dresses the final drop and the escape. C (from 0:58, as anabology asked) and D stay.
16. **Outfit swaps with Seedance.** `tools/swapfit.py` re-dresses an existing take with a Seedance video edit. The take, her on grey before any roto, is @Video1, "the sole editing master" of her face, body, every movement and the timing. The picked outfit still is @Image1, "used only for the outfit". Eight swaps into the pink look went out ($64.08) and were dropped when the look changed. Eight into the shirt went out ($64.08) and became the picks: same face, the moves intact. Putting them back on the old timelines took a discovery.
    - Seedance returns an edit at 24 fps with the whole motion uniformly rescaled to its own quantised length. A 5.0 s 1080p Wan take (150 frames at 30 fps) came back as 113 frames, 4.709 s; the 720p Seedance takes came back at their own 121 frames.
    - The first alignment fitted her silhouette's centre and read a missing head: the first 0.36–0.5 s gone and the rest running 4–6 % fast. It was the new skirt changing her outline.
    - `tools/swapalign.py` now maps the edit back by the ratio of the two lengths with no offset. It checks the fit on her hair, the glossy black in the top 40 % of the frame, which no outfit changes: correlations from 0.71 to 0.998 across the eight.
    - One swap had already gone in aligned wrong, the 0:55 shot, with a frozen half-second at its start. It was re-aligned.
17. **New takes, for her hands.** Midjourney made her actions in the new looks; see the Midjourney record for the image prompts. Then the takes:
    - **For chapters 05, 06 and 08:** a new dance for 1:24 on Seedance, with the instrumental; the stocks swipe on Wan; the red-look drop dance on Seedance; and four red-look gestures on Wan.
    - **The stocks swipe** came back with a floating holographic glass panel where the invisible screen should be. It was made again with "nothing is visible in the air: no screen, no panel, no glass, no hologram, no light, no interface, her hands move through empty space".
    - **The lavender takes:** the swipe (Wan, 6 s) and the spin (Seedance, on the song from 0:26.10). In the spin the white shorts under the skirt show for a few frames, which reads as an ordinary skirt spin; it was kept.
    - **The double-tap** was refused: Higgsfield returned status "nsfw" and refunded it. Its first frame had her leaning toward the camera, pointing at the lens. It was restaged upright, from the swipe's still: "She looks up at a giant screen above her, delighted … she points her raised index finger up at one spot on it … she taps that spot twice in the air with her fingertip". That also follows on from the swipe before it.
    - **The red-look chapter.** On the chapter cut with these takes, anabology wrote: "bodyslop at 0:12 - her feet /legs are backwards lol. need different ref . roto could be better on shoe at 0:18. otherwise great". Three of the four Midjourney stills of that turn have backwards legs. The take was made again from the one still whose knees and feet face forward ($1.00). The shoe's take was rotoscoped again with BiRefNet's full general model, which recovered a motion-blurred back shoe the lite model had lost.
18. **The ending.** The escape is one Seedance shot (15 s at 1080p, $17.06). anabology's world, w4-exit-1, is the first frame; f3-red-2 gives only her look. The script is timed in whole seconds: she climbs the white staircase, the camera zooms toward the door, she reaches the top, looks back over her shoulder at 13–15 s, and steps through. An agent built it into chapter 09:
    - The take is frame-locked at 1×: song frame n shows take frame n − 3499.
    - The last line is painted on the plaster beside the door and tracked with OpenCV: Shi–Tomasi corners on the plaster only, pyramidal Lucas–Kanade with a forward-backward check, a RANSAC homography per frame. It drifts 0.5 px or less under the sign.
    - The X is cut through the wall and lit from behind.
    - The film ends in the light, where v1 had looped back to its first frame.

    Later, anabology asked: "also why does the ending in ch9 you showed me have her walking out a door at the start of the clip and then in a different place walking out a second door? thats redundant". Chapter 08 had ended on the Dynamic Island dripping into an arched EXIT door. Now it has no door, no sign and no look-back. The island opens like an eyelid into a pill-shaped window of painted sky in w4's colours, its light right behind her head. Chapter 09 pushes through that window into the light. The w4 door is the film's only door, and her look back on "I" its only look-back.
19. **The chapters rebuilt.** Agents rebuilt chapter 08 in the red look and chapters 05 and 06: the new dance, and the stocks scene with no phone in her hand. She works a giant Liquid Glass screen from behind, the app keyed in take time so it stays on her fingertips. Chapter 03 put the shirt through the river, re-baked the film from her new silhouette and set her palms on the Ignore Limit pill. Chapter 02 did the swipe, the double-tap, the E and the spin, with the moon post replaced by a designed poster. As anabology asked, each did one thorough pass with its own art-director check.
20. **Re-lights spliced into the final frames.** `tools/splice.py` handles every re-light the same way:
    - It cuts the source from the render box's own frames of the cut: 24 fps, rounded up to 4n+1 frames with real frames after the window, and never fewer than 89. A source of 4n+1 frames came back frame for frame in four of the five re-lights that used one.
    - It writes the delivered clip back over exactly those frames: window frame k takes re-lit frame round(k·(nr − 1)/(ns − 1)), which absorbs any rescale. The originals are kept.
    - Keep-rectangles hold the original pixels where the edit should not touch them.

    The re-lights:
    - **The hook's bedroom take** ($11.42; 121 frames in, 121 out). The lead judged it darker and a touch softer than the original and kept the original. anabology: "the first re-light is behind the animation thought right?  like, weonly see that scene behind the hyperbloom starting animation right? can we see how it looks w/ vs w/o the relight?" Side by side in the pills, the cooler screen light read better. anabology: "New better."
    - **The river**, as a real room lit by its own screens. Its type came out "a touch softer, still clean and legible".
    - **The lock-screen digits and the rain**, as ray-traced liquid glass with chromatic fringes. Seedance smeared the Reminders notification, so the original card was put back, its rectangle tracked frame by frame over 48 frames.
    - **The blue beat.** Later, anabology asked: "whats that blue background scene? is that gonna be painted in by higgsfiled like, is all s22 gonna be re-imagined?" It was a 1.2-second bridge of flat LinkedIn blue. Then: "ya re-imagine - you can totally replace backgrounds with seedance btw. but yeah sounds good relight it". Seedance replaced the flat blue with a glass atrium of tall reel screens and a polished floor, and kept her, the reel card and the interface.
    - **The E**. It came back bold: the dusk sky a thin-film swirl, the E a puffy liquid-glass letter. The lead kept it, sent the comparison and offered the plain render back.
21. **v2** went out. Its checks: 148 of 148 words on screen at their time, six pairs across chapters matching to the pixel, and 6 flashes with at most 1 in any second. The strobe scan flagged only the known swipes and whips. The ledger stood at $336.00 at list.

## v3 and the final

22. **The last notes**, verbatim (song times):

    > last changes: need a new pose/ reshoot for 1:14 - get rid of her foot lol. you could maybe just throw the entire clip thru Wan 3.0 (with your edits and stuff) and specify to remove the foot so you dont have to re-edit. and have it relight at the same time. second, at the end, where its don't sell my soul, i want to cahnge the dont track to facebook from x notification instead, since they have a bigger rep for selling your soul. 0:40 - the cutout of her - she loses her right foot. similar cutout issue at 2:13ish for that scene with her hands going off the edges of her bounding box. if that s just all the video model gave us before, thats totally fine, we don't need to re-edit - again we can just try with Wan 3.0 to relight the scene and tell it to make sure her hands are not cut off / she has full bodyparts / to restore the hands / feet that disappear, and then we get an enhanced scene quickly w low effort. 0:45 - the pause at dont let me scroll  - id rather there be no pause here, she should continuosuly dance, the 0:51 entire screen shaking with her shoulder bumps is wayyyy too much, need to done that down by 90%. otherwise this is sick and amazing and you should be proud - try to attack all the rest of these efficiently and quickly so we can get it out […]

    Then: "wait wait lol 3.0 with the foot removed noooo it needs to come back", "all your roto cutouts have blurred bounding boxes it seems and sometimes her limbs go outside of them and just disappear at the boxes edge" and "ohh wait nvm i go tmixed up. 1:14 is yes remove it". The takes are 9:16 clips. Where her hands or feet leave a clip's own frame, the shots had faded them out at that edge. That is the blurred box, and why limbs vanished.
23. **Wan 3.0 relight-and-repair.** anabology's method: hand the whole finished shot to Wan as Video 1, and ask for the same shot "physically lit and photographic", every element in place and in time, with the body repaired. Five shots went out, $11.20 at list:
    - 1:14 (S17), "Remove the stray bare foot and leg that appear beside her";
    - 0:40 (S10), her back foot restored;
    - 2:13 (S30), her hands completed;
    - two more the lead found: the 1:24 spin (S19, her sleeves) and the 2:00 jump (S28, her hands).

    Wan keeps the length of its input, so each source was padded to a whole number of seconds with its last frame held. It shifted the colour of every shot: the warm grey paper of S30 came back darker and blue-grey, its mean level down from about 172 to about 113, red falling furthest. `tools/colormatch.py` maps each re-light back with one per-channel gain and offset for the whole shot, measured across its frames so it cannot flicker; S30 came back to about 168. Then each was spliced in.
24. **The rest of v3.**
    - The pause at 0:45 (S11) was a one-beat freeze on the hit, because the take ran 0.4 s short at 1×. It is gone: she dances straight through, and near the end of the shot a two-beat loop (0.917 s, from 4.92 s back to 4.00 s of the take) joins at a point where her pose repeats.
    - The shoulder-bump shake (S12) dropped by 90 %.
    - The tracking prompt now reads "Allow 'Facebook' to track your activity…", with a Facebook icon added to the kit.
    - Later, anabology asked for a cut that starts at 0:03 with an audio fade-in, and a second one "as a test" from the clock coming up after the title, at 7.5 s. Both went out (2:37.8 and 2:33.3).
    - Later came "also these relights look sick, great job", and "can you make the audio fade in 1 second longer?". The fade became 2 s; only the audio was re-encoded.
25. **Notes on v3** (these times are in the cut from 0:03, add 3 s for the song):

    > at 0:49 the shoulder bumps are still super intense. like the entire top and bottom parts of the frame go black, interpreted as massive jitter. would remove that - like make the tops keep color or just remove the massive sliding of the reels. 1:11 and 0:36 reshoots lose her face consistency - can you feed in a good face ref? show me the ref rq first before we reshoot and then we give teh same prompt but then add like @image3 is the face of the model or whatever. its too fat in 1:11 and looks off in the 0:36. did we relight the 1:29 scene? thats the only other place where her face gets lost again - so we could use a face ref there too. i like from 0:03 so let's keep that one.  oh also sorry cratch that her face is a bit wrong at the re-lit 2:13 scene as well. so we'll need to fix that too with a face ref. id just re-do the relighting with the face ref added from the original scene rather than rerunning the generated ai scene into it again. ok and after that promise we're done

    - **The face reference.** The lead showed three candidates:
      1. DOWNFORCE's identity portrait, cropped to her face and hair so the racing suit could not bleed into the outfits;
      2. a frame of the re-lit bedroom take;
      3. a crop of a red-look Midjourney still.

      anabology: "face 1 is best pic there". Four Wan passes went out at once ($8.00): S17, S10 and S30 with the same prompts from their original renders, and S21, the stocks scene, which had never been re-lit. Each added Image 1 as "the face of the woman … Image 1 is only a reference for her face; it is never shown as a shot". In S21 the interface and the status bar were kept from the original render.
    - **The jitter.** In S12 the reels had paged a full screen on every vocal chop, which smeared the walls into black bands. They no longer page; the kicks and her landings nudge the room by 15 % of what they did. The stamps' shudder was cut to a quarter.

    A final cut went out.
26. **The black lines.** Then: "at 0:49 theres still these black vertical lines that appear now during the entire shoulder bump thing - remove those and we're golden.  1:11 her face is still too fat." The lead first took the lines for the gaps between the reel columns, visible now that the walls stood still. anabology: "no ur wrong", then "they appear occasionally, look at more framers, the spaz out. also show me s12 and 1:11 final before u render the final video thist ime". A scan of every frame of S12 against the median of its neighbours found dark columns on every 8th frame. One of the eight render workers had drawn its share of S12 from a stale camera state. Rendered fresh, one of those moments differed from that worker's frame by 21.5 levels on average and from its good neighbour by 4.0. The worker's 16 frames of S12 were rendered again. Then all 3,859 frames of the film were scanned for single-frame outliers at two thresholds, and none were left.
27. **The full face.** At 1:11 the fullness came from the take's pose: her chin is tucked into the sweater's collar, and a face reference alone could not change that. Two fixes went out from the original render:
    - **A**, a Seedance edit toward the reference ($9.10). It barely moved her face.
    - **B**, Wan with the reference and an explicit face ($1.60): "her face is slim and angular, never round or full: slim cheeks, defined cheekbones and jaw, a slender neck, and her chin lifts slightly out of the sweater collar so her jawline shows". It was the slimmest, and the closest to the reference.

    Both previews went to anabology. Then: "ok cool both look fixed! B is good. slice those in and render and we're good!"
28. **The final** went out. It starts at the song's 0:03, with the audio fading in over 2 s. It is 3,787 frames, 157.79 s, at 1920×1080 and 24 fps: H.264 High tagged BT.709, with AAC at 48 kHz stereo. The master is 185 MB, alongside a review copy. The audio measures −15.2 LUFS integrated, the song's own loudness, with a true peak of −3.0 dBTP. Every sung word is on screen at its time, 148 of 148. The flash check found 6 flashes, at most 1 in any second against a limit of 3. The Higgsfield ledger closed at $355.50 at list. It left out the ten Wan passes' input video, which Higgsfield's estimate prices per second; with it, the list price came to $365.90.

## What worked, in short

- **The loved shot as the grammar.** anabology loved two shots, 0:55 and 1:46. Named as one grammar (pills, thin film, bold type, her big and sharp), they rebuilt the opening and the whole final drop.
- **The world as a tool.** As with BLISS, the world is a hand-built kit, not a filter. Every frame is a pure function of time. The scroll is iOS's physics and the colour is thin-film optics. The interface was measured off Apple's own screenshots.
- **Seedance for the beat.** Given the shot's instrumental as @Audio1, Seedance's dances started on the beat; Wan's reset and shuffled.
- **Re-dressing instead of reshooting.** Sixteen Seedance edits re-dressed eight takes (eight of them in a look that was then dropped). The face and every move held, and aligned by the length ratio, every chapter timing still fitted.
- **Re-lights spliced into the cut's own frames.** Cut from the cut, put back frame for frame, with the interface kept where the edit softened it. The Seedance re-lights became the film's ray-traced glass, a real-room river and a new background, without recomposing anything.
- **Judging in context.** The bedroom re-light looked worse on its own and better behind the pills. anabology judged it where it plays.
- **anabology's Wan method.** Five finished shots went back through Wan with the repair written into the prompt: limbs completed, a foot removed, the light made physical. It cost $11.20 at list.
- **Showing before rendering.** On the last round anabology asked to see S12 and 1:11 before the final render. One preview of each closed it.

## What didn't

- **Slowed takes.** v1's warps ran nearly every take below 1× somewhere, as slow as 0.53× in one chapter's own map and about 0.51× for the bedroom take at 0:08. anabology: "never slow these down. you lowered the framerate for no reason, just looks bad."
- **Composition.** v1 put her small at the bottom centre with posts clipped at the frame's edge. Most of the film was recomposed on thirds.
- **The phone in her hand.** The stocks take's green screen was the back of a phone, and v1 tracked the screen onto it. v2 has no phone in her hand.
- **The take's frame as a box.** Limbs that left a 9:16 take were faded at its edge, so hands and feet vanished at a "blurred bounding box". Wan completed them in five shots. Wider takes would have prevented it.
- **Midjourney anatomy.** A plate with three arms (anabology caught it), three of four stills of one turn with backwards legs (anabology caught the take), a stranger's hand holding a blade (the lead's screen).
- **Refusals.** Seedance blocked the white-satin drop dance twice; Higgsfield refused the leaning double-tap once. All three were refunded.
- **Wan's inventions.** A floating glass panel in the stocks swipe. Focus brackets drawn round her fingertip on the empty-air version, keyed out. Falling objects in one v1 take, a green yo-yo landing on her toes among them. A stool seat appearing under her in another.
- **Spend that never reached the screen.** The four re-light samples ($47.81) were made before the outfits and compositions changed; anabology: "kinda a waste on the excess ones". The eight pink swaps ($64.08) were dropped when the look changed. Five more passes were replaced by face-reference versions or not picked ($16.30). In all, $148.10 of the $357.51 spent after refunds went to takes the final does not show; $16.51 of that was v1 takes that played in v1.
- **Two doors.** The new ending first ran an EXIT door into the w4 door: "thats redundant".
- **Alignment by outline.** The first swap was aligned on her silhouette, which the new skirt had changed, and one shot went in with a frozen half-second.
- **A stale render worker.** One of eight workers drew every 8th frame of S12 from an old camera state. It took anabology's eye ("they appear occasionally, look at more framers, the spaz out") and a scan to find it.
- **Memory on a shared render box.** Each roto of a 1080p take held about 12.5 GB under the matting library's default memory arena. With chapter renders on the same box, rotos were killed for lack of memory. One died behind a `| tail` and looked like success.
- **Small things.** One Midjourney still of the twelve new actions never came back (the look-back, which the escape shot already had). A second Animate run of nine feed pictures returned nothing. The first write of the shirt batch ran past 600 characters and had to be shortened.
- **Interruptions.** Six chapter-animator launches were interrupted and relaunched. Their notes files kept the work.

## Lessons

**Seedance 2.5 video edits**
- An edit rescales the whole motion uniformly to its own quantised length. A 5.0 s source at 1080p (150 frames at 30 fps) came back as 113 frames at 24 fps, 4.709 s; 0.942 of the original. Align by the ratio of the lengths, not by an offset.
- A 24 fps source of 4n+1 frames came back frame for frame in four of five re-lights: 121, 89, 89 and 161 frames. The fifth, 189 frames, came back as 185.
- No edit came back shorter than 89 frames (3.709 s). A 79-frame source returned 89 frames, and so did a 96-frame one.
- Check an alignment on something the edit does not change: her hair, not the outline the new skirt changed. On the hair the eight swaps correlated at 0.71 to 0.998.
- A re-light softens small type ("a touch softer, still clean and legible") and can smear a card outright. Keep the original pixels for the interface: rectangles, tracked per frame when the card moves.
- Seedance re-textures and re-lights; it does not recompose. Asked to move two posts inward, it kept them where they were.

**Wan 3.0 reference-to-video**
- It keeps the layout, the timing and the length of its input video, so a finished shot can be re-lit and repaired and spliced straight back. Pad the source to whole seconds with its last frame.
- It shifts colour, and not by the same amount twice. Bright paper scenes came back much darker and cooler (S30's mean level from about 172 to about 113, and to about 111 on the second pass); dark scenes came back brighter (S19's from about 34 to about 53). One global per-channel match per shot puts it back without flicker.
- Do not trust it with small type either: the stocks interface was put back from the original render.
- A face reference fixes identity, not pose. At 1:11 the face stayed full until the prompt lifted her chin out of the collar.

**Production**
- The matting library's CPU memory arena made each 1080p roto hold about 12.5 GB; without it, 1.3 GB.
- A roto run over ssh behind `| tail` hid a kill for lack of memory. The take tool now counts the mattes and fails loudly.
- Beat warps are floored at 1×. A take may run faster to land a step on the beat, never slower.
- Check finals for single-frame outliers. A worker with stale state produced 16 bad frames that every other check passed.
- Re-render a changed chapter padded by a frame on each side, and check every cut on a seam sheet: a boundary frame rendered by the neighbour's old code left a one-frame blink.
- Make every 2D canvas software-backed. A worker crosses chapters, and one canvas promoted to the GPU makes every later frame history-dependent.
- Scan every full render for strobes cell by cell. The flash check passed a tunnel that strobed.
- Check a tempo against the genre and the kick spacing before any timing work: 89 BPM was two-thirds of 133.39.
- Check every Midjourney pick at 800 px or more for limbs before spending on it. Keep prompts to 600 characters.

## Numbers

| | |
|---|---|
| Song | 2:40.8 (160.80 s), anabology's own Suno take · UK garage 2-step, 133.39 BPM, G minor, female vocoder · 358 beats, 90 bars · 31 lines, 148 words · −15.2 LUFS integrated, −3.0 dBTP · the final cut from 0:03, 2 s fade-in, 2:37.8 |
| Edit | 9 chapters, 35 scenes · 148 of 148 words on screen at their time (v1, v2 and the final) · 3,859 frames per full version, 3,787 in the final cut, 1920×1080 at 24 fps · flash check: 6 flashes, at most 1 a second (limit 3) · 0 single-frame outliers in 3,859 frames after the fix |
| Midjourney | 130 prompts in 7 batches · 129 jobs delivered, 516 images (3.41 GB) · 40 Animate submissions, 22 loops (44 clips, 406 MB) · 110 images became first frames, references or feed pictures; 39 of the first frames and references reach the final through a take (the feed's 54 pictures not counted; two more, P05 and P21, are her avatar) |
| Wan 3.0 | 49 submissions, 1 refused and refunded · 48 takes (38 image-to-video, 10 reference-to-video passes) · 264 s generated, and 52 s of input video in the ten passes · $64.20 at list, $63.20 after the refund |
| Seedance 2.5 | 41 submissions, 2 refused and refunded · 39 takes (13 reference-to-video, 26 video edits) · 212 s requested · $301.70 at list, $294.31 after the refunds |
| Generation, all | 90 submissions, 87 takes · $365.90 at list, $357.51 after refunds of $8.40 (list prices throughout; the runner's ledger, which left out the Wan passes' input video, came to $355.50) · by round: v1 takes $60.00, re-light samples $47.81, pink swaps $64.08 (dropped), the escape $17.06, v2 takes $20.38, white-shirt swaps $64.08, the bedroom re-light $11.42, v2 re-lights $51.18, v3 Wan repairs $11.20, face-reference passes $8.00, the last 1:11 fixes $10.70 (the parts are rounded to the cent; their exact sum is $365.90) |
| Takes in the cuts | v1: 37 of v1's 38 takes · the final: 33 takes' own frames, and 21 more under a swap or a re-light; 54 of 87 |
| Code | 9 chapter files, 6,784 lines · the kit: 12 modules, 6,462 lines (and 3 core modules, 597 lines, from AIRPLANE MODE) · 25 project tools in Python, 2,753 lines |
| Agents | 32 launches: 2 surveys, 5 kit builders, 15 chapter launches for v1 (6 of them relaunches after interruptions), 10 for v2 |
| Time | ~25 h 24 min from the first message to the final · 43 messages from anabology, 39 up to the go |
| Claude tokens | not measured for this package |

Where each number comes from:
- The song: the WAV itself (ffprobe; ffmpeg's EBU R128 meter), the beat map, the hit map and the timed words (`media/audio/`).
- The frames and the final cut: ffprobe on the masters; the flash checks' reports.
- Midjourney: the prompt records and the images and loops.
- Wan and Seedance: the spend ledger (`shots/ledger-hf.jsonl`, list price at submission, a line per refund) and the job files (`shots/*.json`).
  - The ledger prices Wan at $0.20 per generated second at 1080p, as Higgsfield's estimate states it.
  - It prices Seedance at $1.1372 a second at 1080p and $0.4622 at 720p, counting an edit's input seconds too.
  - For the ten Wan passes that took a video, the ledger counted only the generated seconds. Higgsfield's estimate (as the runner records it) prices a Wan input video per second too, so the figures here add those 52 s ($10.40), as DOWNFORCE's package did.
  - What was actually charged is not recorded.
- Takes in the cuts: the chapter files of each version, the pick files, and the splice commands of the final.
- Code: line counts of the chapter, kit and tool files.
- Agents: the agent launches in the production conversation.
- Times and messages: the production conversation, measured from anabology's first message. Three of the 43 messages are about the production's tools rather than the film and are not quoted; the four after the go asked the style's name, a thumbnail and this package.

The dollar figures are rounded to the cent.



## Files in this folder

- [prompts-midjourney.md](https://claudia.gallery/record/dont-let-me-scroll/prompts-midjourney/): all 130 Midjourney prompts by batch, what each pick became, the Animate loops, and the images screened out.
- [prompts-video.md](https://claudia.gallery/record/dont-let-me-scroll/prompts-video/): every Wan and Seedance job in production order, with its inputs, prompt, takes, what it did, whether it reached v1 and the final, and its price; the house preambles; the swap and re-light methods.
- [prompts-suno.md](https://claudia.gallery/record/dont-let-me-scroll/prompts-suno/): the song's record: anabology's lyric and style as they sent them, the two takes, the lyric as sung with its times, and the analysis for the edit.


