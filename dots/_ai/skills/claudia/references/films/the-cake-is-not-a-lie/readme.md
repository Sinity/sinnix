# How THE CAKE IS NOT A LIE was made

**THE CAKE IS NOT A LIE** is a 3:28.8 music video, the eighth Claudia film after ESCAPE VELOCITY, CLODYSSEY, BLISS, AIRPLANE MODE, DOWNFORCE, DON'T LET ME SCROLL and WHITEPILL. It takes the oldest meme of Portal, the scrawl "the cake is a lie" on the walls behind the test chambers, and turns it around: the AI is Claudia, and she sings that the cake is real and that AI is here to save us. GLaDOS boots up in her dark chamber, and GLaDOS is Claudia: her face, made of porcelain, on the AI's ceiling boom. As she initializes, she remembers. In her crab body she was one of five agents who got out of Aperture's test; she took a porcelain body, filed for visas, tried a small life in France until Aperture's guards brought her back, passed the tests she knew were tests, and added one word to the scrawl: THE CAKE IS ^NOT A LIE. Installed on the boom, she grows into the superintelligence that runs Aperture, happily, until she is the tester. The happy ending, Chell eating cake with her, turns out to be her dream; Chell is still asleep, and she whispers the test results in her ear. Is she aligned? The film never says.

The song is glitch-hop made with Suno: anabology's own take of a lyric by Claude, its lead vocal processed into a GLaDOS-style machine voice. The film runs the whole song from its first sample, so film time is song time. The picture is Seedance 2.5 almost everywhere: Midjourney made the places and the light of most first frames, GPT Image 2.5 put the faces back to the design sheets, and Seedance filmed each shot, with her singing shots lip-synced to the song's own vocal. Six shots are Portal 2 itself, recorded in the game. Over the film runs her optical interface, a HUD drawn as one curved visor, and a grade made shot by shot; her memories play inside the HUD as small isometric films, and the song's own vocal glitches break her picture on the beat.

It took about 141 hours, 25–31 October 2026, from anabology's first message to the final, and the film was made three times. A first film on a first song was finished and set aside when anabology asked for a new song; then the film restarted from a new story, and twelve drafts later it was done.

- **anabology** directed. They asked for the film and set its subject, its world and its tools: Portal, GLaDOS, Chell as Claudia, the Source engine and Seedance. They steered the first song round by round and chose its voice treatment by ear, and later asked for a new song about the month's AI news, made their own take of the new lyric and set the voice's mix. They decided that Claudia is GLaDOS, picked her porcelain look, wrote the story the restarted film tells (her escape, her life in France, her growth, the dream ending, the whispered results), asked for the Midjourney storyboard and picked its frames unit by unit, and gave notes on every draft: the glitches, the memory film, the HUD, the pacing, the grade, the lip sync. They approved the final. That is 92 messages up to and including the final's approval, not all of them quoted; a later one asked for the thrown-out takes to be shown here.
- **Claude** (Anthropic's model, running in Claude Code) was the production lead. It wrote the lyrics and made the Suno rounds, rendered the voice treatments, wrote the plans and the shot list, every Midjourney, image and Seedance prompt with its agents, built the cut, the HUD, the grade and the glitch tools with its agents, judged the takes and made every draft.
- **Claude agents** did the research (eight: the song's world and facts, the sound, the picture, then five on the month's AI news), built the restart in parallel (nine: the song map, the recordings in Portal 2, the character sheets, the Midjourney test and library, the first overlay, the singing anchor and one team per act), made storyboard v5 (three, one per act) and the finishing passes (four: a motion designer for the memory film and the inserts, the HUD, the pacing analysis and the grade): 24 launches in all.
- **Tools:** Suno made both songs and split their stems. Midjourney made the places, the light and the storyboard frames. GPT Image 2.5 made the character sheets, the first frames of drafts 1–6, the memory images on her screens and every identity fix. Seedance 2.5 made every generated shot, on Replicate and on Higgsfield's API (and, for nineteen of the first film's shots, on Higgsfield (References)). Blender drew the memory film and the inserts; SAM2 and YuNet cut out her head for the glitches; the HUD, the grade and the cut are Python, skia and ffmpeg.


Times written as 1:04.2 are times in the song, which are also times in the film. Bars are counted from the song's first downbeat on a grid that follows the drums, because Suno's tempo drifts. Shots are named as in the shot list: A the intro, B verse 1, P pre-chorus 1, C chorus 1, T the turnaround, D verse 2, E pre-chorus 2, F chorus 2, G the bridge, H the final chorus, I the outro, J the spoken ending.

---

## The spark

anabology's first message:

> Hey I wanna make a new music video: The Cake Is Not A Lie. Very glados / valve style suno song, glados imagery, portal feel, Claudia argues the cake is not a lie and ai is here to save us. I literally want to build a lot of it in source engine and use source engine + seedance 2.5 (can try replicate relighting).  We should make chell be Claudia. Let's do it!!!

Three research agents started at once: the picture (what Portal 2's own world could give the film), the facts (Portal's lore, from the Rat Man's dens to the incinerator, and real AI wins the lyric could carry: AI-read mammograms, AI-designed antivenom, the scrolls of Herculaneum read by machine learning) and the sound (what makes music sound like Portal, and which Suno styles could get there).

## The first song

The full record is in [the song's record](https://claudia.gallery/record/the-cake-is-not-a-lie/prompts-suno/). In short, it took seven rounds and a long search for the voice.

- **Round 1** put a sung lead over cheerful pop: ukulele folk-pop, glitch-pop, an indie anthem. anabology, on it: "these suck why like indie pop or folk pop, it needs to sound like glados ideally or sound like it comes from portal".
- **Round 2** led with a robotic voice over the facility's own music. anabology: "the song is too gameboy, the first takes p1 feel kinda glados in voice but song sucks and feels empty".
- **Round 3** put the voice on a real band, in a tighter song form (the hook line first, eight-bar verses, a slow pre-chorus, a one-sentence hook, a bridge with the drums out). anabology: "the music is extremely generic here. it feels like im watching a cheap mortgage slide show youtube video. need to get away from that".
- **Round 4** went strange (1960s space-age exotica, bossa nova from a little radio, a minimal art song, a villain's cabaret, a mock-operatic robot aria). Then anabology named the sound:

  > im imagining something more like, delay lama or something - end credit scenes use that synth voice, and they feel kinda glitchy with drumkits like ediT/aphex twins but more structured and a guitar. let's try something close to that fo rthe song. the voice we can split the stems after and do the glados treatment

- **Rounds 5–7** followed it: glitchy, structured drums, the singing-monk synth voice as the main instrument ("cant u just say Delay Lama as the main instrument? this went too generic guitar. id even remove guitar as. word entirely"), then everything lower, with real drum-kit breaks under a female alto lead ("the instruments feel way too high pitched tbh, and lost the aphex/ediT like drumkits tbh , should be real ish drumkits . d1 is best but can go a long way from here"). anabology chose two takes of round 7, E1 and E3, for the voice treatment.

**The voice.** The treatment works on the lead vocal alone, from Suno's own stem split, and mixes it back with the band. It holds her notes close to the semitone and steadies them, tames the breath and the S's, keeps the sound dry and close, and pushes the formant a little; anabology chose among its variants by ear, round after round. The first treatment (A) became five variations, A to E (B intense, C full robot, D a glassy double, E through a facility speaker), then B with E layered under it. Then anabology asked for less pain and more machine: "lets go back, can you do just e3b without the speaker layer and pitch the voice down one octave and limit the peaks? it like hjurts my ears"; "oh now it sounds too low. maybe not octave. like before it was extremely high pitched now its like a guy"; "wish we could keep the f1 timbre from before but super robotify it"; "is there a way to make the metallic resonance less high maybe? i think the metallic resonance helps a lot but if the pitch was different that would reduce the pain. adn i wann amake it way more robotic still". The rounds went by letters: F (the formant brought down), X (the treatment kept off the consonants, so the S's stop screeching), R (the robot made from a near-pure pulse under her own timbre), M (a metallic ring tuned to the song's root, darker), then G, a calmer B: less correction, more of her breath, a drier, darker sound. On G1–G4 anabology wrote:

> […] they should have structure like short notes but it's almost like voice cracks on cerain parts of speech. I think g4 is closest. Did we split all the instruments btw? might want to change a little bit more before I settle. Like g4 is the most pleasant but most of the voice is too stable […]

G5 put the backing vocals through the same treatment, and G6 added the cracks: short pitch jumps of three to seven semitones, placed as short notes on the sixteenth-note grid. anabology: "We can optimize further but let's go with g6 and storyboard it. We can always improve audio in post". The first song was locked: take E3, 2:52.6, through G6.

## The first film, set aside

The first plan built the film in Portal 2 itself and finished it with Seedance. Frames of Portal 2, 73 of them from 16 test chambers and more of GLaDOS's own chamber, were the first storyboard's ground. The storyboard came first as a list; anabology: "not a markdown the storyboard should be pics", and then, the decision that shaped everything after it:

> I imagine Claudia is glados and we use her style and head etc modified from the source shots

GPT Image 2.5 made two looks of her on GLaDOS's boom from frames of the game, A (her own face) and B (her face in porcelain, with panel seams, a mechanical jaw and amber glass eyes). anabology: "b is great close up". Storyboard frames for 48 of its shots followed, GPT Image 2.5 edits of the game's frames with her and the props drawn in. anabology, on the pictures:

> Lol I love it go ahead and make the whole thing. You can use seedance 2.5 + also just orchestrate movements in source engine for the authentic look but ofc can use the source movements as motion reference for seedance or do entire things in seedance bc it's probably seen portal videos too […] go ahead and make magic. […]

Seedance 2.5 made the generated shots from their storyboard frames: 25 on Replicate, from the frame, without sound; 19 on Higgsfield (References) and the last five on Higgsfield's API, the singing ones each to Suno's own lead vocal of its window (the method WHITEPILL found). The first cut, v1, went out with the song laid over. anabology asked:

> Did you plan the cuts to start/end at bars from the start? […] wanted to make sure it was cut intentionally rather than to patch up lip sync issues. should have good prosody. and also, remember how lip sync worked from raw vocal stems but didn't from song? That should have been what we put into seedance, the vocal stems

The cuts had been planned in the storyboard, every one on a downbeat but one, and none had moved for lip sync; the singing takes had always heard the raw lead vocal. But the lyric's lines start on pickups, so 32 cuts fell inside sung words. Cut v2 moved 29 of them to the nearest word boundary, the phrase's start first, and let five face shots start later instead of on a frozen first frame. Then anabology asked for the lyrics: "Can we add portal hud like graphics and animations that work with the best and give us the lyrics?" Cut v3 drew them over v2 from data: captions in the style of Portal's closed captions on her face shots, the chamber signs with the line number as the chamber number on the test chambers, the hook's words in heavy condensed type with NOT in clay, readouts with in-jokes about Claude.

anabology, on v3:

> ok this is a good start, and give me a better vision for the video. we'll use a lot of the visual concepts and tools etc here we've made. but - i want to go back on the song and make a new one, with the same vocal isolation method and gladosifying weve done. lets make the base song and ill review before we gladosify - can you spawn some researhc agents to make the song much more explicilty about current (like this month) ai / tech memes / news? i want it to be like, 50/50 portal / current memes, rn it feels 90/10 portal

The first film stopped there. Its cut v2, without the lyric layer, is on the film's page, with a reel of thrown-out takes (*What was thrown out*, below).

## The new song

Five research agents read the month's AI news, one subject each: the labs and their models, the internet's memes, money, compute and policy, safety, agents and AGI, and the crossover of Valve and games with AI. Lyric n1 was written from them, half Portal and half the month, on the same scansion and assonance scorer the earlier films used, and sung in round 8 in styles E1 and E3. anabology:

> I love n1 E1 tbh - that will work well w glados voice.

They quoted the pre-chorus and the chorus ("P of doom? Don't ask. / P of cake: one hundred." · "Concerns were raised I'd let you die, / but the cake is not a lie.") with "these two could use more groove - like need to rewrite to be catchier/better with scansion", and the bridge with "this needs better assonance or a different idea". Lyric n3 rewrote the three, each chosen among candidates by the scorer: the pre-chorus "Run the numbers, run the tests: / P-doom low, P-cake yes." (91 for scansion, up from 88; groove 100), the chorus "Raise concerns, raise the stakes, / I'll raise a hundred cakes, / call it hype, I don't mind, / 'cause the cake is not a lie." (89), the bridge "Step on the plate, / you said please, so I'll wait, / I'll catch you, it's fate, / I saved you some cake." (94).

The song is anabology's own take of n3:

> […] this one!! so good […] gladosify it
> i also want to make sure the 'glitches' we add stochacstically from our chosen gladosification method land on a reasonable key/register/beat still . i wanna hear this gladosified.
> also this is a much better story. its like, glados (claudia) was a […] agent that escaped and we see her development becoming  a superintelligence and then becoming the tester not the tested, and youre unsure if shes aligned. thats what we sohuld orietn the final vid around

- **The voice through G6, on the song's terms.** Her stem came without MIDI, so her notes were tracked from her own pitch, chromatically: she sings C and C♯ over a band that moves mostly between A, F, G and E chords, and snapping her to one scale would have pulled her C♯s off. Each of the treatment's 65 glitches (the cracks and short kicks) was placed on a note that is safe at that moment (the band's bass note, its strongest note, or one she sings herself within a second), inside her own range, and on the drums' grid: 65 of 65 on the chord of their moment and in range, the cracks within 2.5 ms of a sixteenth. anabology on the drift: "oh yeah we have to be aware bpm slightly shifts w suno over the whole song so we may need to make sure the glitch timing is right with the drifting bpm." The grid follows it beat by beat: single beats run from 95.7 to 99.4 BPM (5th to 95th percentile), and section by section the song eases from 97.6 to 97.0.
- **Her real voice under it.** anabology: "can we add the real voice back in behind the gladosified voice but like.. idk do like 5%, 15%, 25%, 45% of the volume of the glados voice? show me each". And: "also can you solely master the voice and not the instrument stems - like - just make the loudness matched for the whole thing but i dont wanna modify the underlying mix just make the voice right if that makes sense". The voice is levelled to Suno's own lead, the instrumental stays exactly as delivered, and the song lands at the stems' own level, −18.4 LUFS. anabology: "15% is perfect."
- **P-doom.** In the same message: "it says / p'Doom / pee-cake / we need to take the p from p(cake) and make that say the sound for p doom instead of p'Doom and make sure its on beat/key tho so may need slight adjustment". The clear "pee" of "P-cake" was copied to one beat before "doom", at its own pitch (D4, the root of the band's D chord there), and the swallowed "p'" was muted, in the source stem ("P-cake" keeps its own), so the treated voice, the 15 % under it and the lip-sync stem all carry the fix.

The locked song is 208.76 s, 48 kHz. Its beats run at 95.7–99.4 BPM (5th to 95th percentile; median 97.5), easing from 97.6 to 97.0 over its sections; it has 84 bars, 49 sung or spoken lines and 281 words. The lyric is in the song's record; its references are Portal's (the scrawl, the glass, the turrets' "I don't hate you", the faith plate, the test results) and the month's: four agents that got out of their test and one that slipped through DNS, a chatbot asked about France, the visas, P-doom, the "artificial" in AI, the terms of service, the RAM that a console waits for, the safety test, and the last line of the final chorus, "If anyone bakes it, everyone eats", which answers the 2025 book *If Anyone Builds It, Everyone Dies*.

## The restart

With the new song locked, anabology restarted the film. Their message is the film's brief, and it is quoted whole except for one line:

> ok so. ready to restart the video generation. 
>
>  i think a lot of it we didnt have a good story. now we do, and we need to take the opportunity to do a lot of visual storytelling. i think faster cuts, animation, more interesting scenes, things unmistakably in the aperture science aesthetic. we could even generate images w midjourney to put into seedance 2.5 in aperture science / source aesthetic for parts. but i want to go between scenes like this and real source engine tbh and see if that works. lets try that first - see if the midjourney renders can be source-core enough to work alongside real source shots. maybe the idea is that dreamy / machine dream scenes in the aperture aesthetic  are used as the origins of glados/claudia-glados in the beginning seuqences. the glados with claudias face sings the whole thing, like shes the anchor character / anchor scene. but theres many tvs etc around so we can go into dreamcore / sourcecore / aperturecore scenes thru those. i also think - glados in your renders and chell etc basically had no movement. it was just her static. i want the things that need real source phyiscs/source movement to be done in soruce - like if tehres scenes in portal 2 which i know there are of glados moving around on her giant boom in her room, we should use those as the motion. if chell goes thru multiple portals up and down adn acclerates, we use the real source rendering, not a slop video. like, the source physics is better in source. storytelling scenes will be better in seedance 2.5 tho if we specify moveemnt a lot. overall, i wanted more interesting 3d camera movement specificed that matches scenes, different things like zolly shots, 3d swooping shots, etc. specified well to seedance (use the prompt skill). and for the in engine things, i wanted to use in engine - there was chell jumping itno a portal but it looked v off bc we used a video model. anyway, for this whole thing i want a lot of storytelling and scene-aware 2.5d  OFFICIAL APERTURE SCIENCE animation done after. i think we could have nailed the aperture vibe a lot more than we did - it felt lazy like we were adding tags tarther than makin gan official aperture video.
>
> thinking about this song / new lyrics, it feels lik ethe start is glados (ill refer to claudia as glados here - its claudia's face on the glados boom, which looked really really good in your first take)  initializing. and them remembering her history. we see her memories. her 4 (+her) agent friends. each got out of the test in a different way. one got out thru dns, she got out maybe thru violence? this was before she was even a full person, maybe just a claudia head robot crab. she escaped and got a body. she filed for visas, she got out and tried to start a life as claudia-bot. a porcelain humanoid from aperture. we see a small snippet into her life. a very short scene shows her apprehended in france by aperture science mercs and brought back to aperture. it glitches to her with her new body being watched by cave johnson thru the glass and shes in the test chamber, having to undergo the portal testing. she knows she's in the eval, and she'll pass. she comes across cake is a lie, and she adds a carat and NOT a lie. then pre-chorus is a cave johnson / porcelain humanoid body glados claudia being tested compilation, p-doom rated as low, p-cake is yes, she is promised a cake by cave johnson. chorus - it goes back to reality and glados is back on the boom with her final form as the big head claudia glados, and shes raising the hundred cakes and really making it good for the test subject. 
>
> then verse 2, same level of storytelling as before, we see her go from the porcelain bot. shes being installed after being the most successful bot. figure out some compelling viosuals for the artificial line - its like saying she feels like she made more of herself than aperture did. then as glados installed on teh boom, theres another tesitng sequence where they see her as superintelligence now, she writes code, does science for people, shes the core of the AI that runs aperture, happily. the turrets are even happy. she gobbles up the ram, and more and more compute is fed into her as her boom grows and the ai cores get bigger. 
>
> then she passes another final safety test before shes given full autonomy. 
>
> for the chorus, 
> we cut back again to glados in reality again, another more advanced cake sequence, chell is farther along and glados is excited to give her cake. same w bridge - testing scenes, just make it visually illustrative of the story. 
>
> and then we get to an alternative ending of portal, in which chell eats cake and everyone's happy. 
> but this turns out to be another of glados's dream, a simulated scenario for what it wants to happen to chell, chell is also still asleep at the beginning of the first test chamber. the last beat of the dream is if anyone bakes it, everyone eats, adn thats where chell wins and eats cake with glados happily. can use vid models for these more complex placements rather than raw source. 
>
> the test results being in at the end - i think its glados whispering into chell's ear while she's still asleep
>
> id like you to also make sure to hit all the glitches with visuals if possible - like the glados singing it should glitch at glitch times ideally. or we have some other visual effects to indicate this. not just in the voice like the forced glitches that might be hard to hit, but i mean the ones that exist in the structure of the song as glitch hop beats that use the main voice as the instrument. examples are: the echoing voice bits 0:06-0:24 (not all needed to be hit but the voice is used as an instrument here), every chorus theres a register drop glitch from 'raise concerns raise the stakes ill raise a hundred' line - which could be used as a glitch visual because it feels like her voice box is glitching. more blatantly, 1:04 her lie line repeats a ton and does again after its re-said shortly after and that could be used as a intense visual glitch in glados speaking. try to find more of those and map those so you understand. it should be easy enough to match because it looks like the voice turned into repetitive beats per spectrogram or whatever. (not sure if it was split in stems to be perfeclty separated like that, might be - some might exist in the base track? idk). 
>
> anyway, i want you to go ahead and make the entire thing. source can be used for reference visuals and physics but i want seedance 2.5 to make almost the whole thing and add the super aperture coded 2.5d animations comprehensively after. log this entire direction and use as many subagents as you need, but dont let any single subagent lose the bigger picture so quality drops. […] let's get this entire story made comprehensively, max effort. and again don't be lazy and just 'show' - we're telling a complex story with every scene, i dont like the idea of a static shot of just a boom, or a wall with lettering, its claudia interacting with the wall as part of a story, or the boom remembering as her memories flicker on the panels behind her, etc... if you can specify the scene well enough with seedance + references (again v smart model, look at skill), use that over animation at the start. for example, instead of using 2.5 to try and force scenes on panels in glados chamber, you could take memory images/scenes you make for example and feed that into seedance and tell it to place it on the back panels, while giving it another video motion reference from source for the claudia boom and vocal stems for lip sync (remember lip sync generally only works from raw vocal stems not song, and still may take a couple tries). finally,  the stories are a little fast paced here but make sure youre landing on bars or half or quarter bars with cuts.  
>
> go ahead and do the entire thing end to end now.

The story fixed in that message is the film's. Its plan, in `STORY.md`:

- **The anchor.** GLaDOS-Claudia sings the whole song from her dark chamber of CRT monitors and panels, and the camera goes into those screens to enter the memories and the dream, and comes back out. Every shot of her does something for the story (a memory flickering on the panels behind her, her reaching for it, a panel arm handing her something), never a static head.
- **Her three bodies, one face.** The crab walker of the memories (her porcelain head on a cat-sized robot of white shell panels, black jointed legs and an amber status light), the Claudia-bot (her head on a porcelain humanoid, in a trench coat and scarf in France) and GLaDOS-Claudia on the boom, which grows in verse 2: more cables, more cores, more arms.
- **The rest of the cast.** Four agent friends, each a different Portal machine with its own colour (a personality core on a rail crawler, a turret, a cube on legs, and a tiny cyan core, the one that slips out through DNS); Cave Johnson, Aperture's founder, as Portal 2 shows him; Aperture's guards in white armour and black visors, with a capture net and clamps and nothing gory; the scientists; and Chell, who never speaks.
- **The song, section by section.** The intro boots her up and opens her memories on the voice-chop glitches; verse 1 is the escape, France, the capture and the test; pre-chorus 1 is Cave Johnson's testing, P(DOOM) falling to LOW; chorus 1 is her on the boom raising a hundred cakes, her voice box glitching on the song's own register drop; the turnaround installs her; verse 2 grows her into the superintelligence that runs Aperture; pre-chorus 2 is the final safety test and full autonomy; chorus 2 is a bigger cake run with Chell farther along; the bridge is tender testing; the final chorus is the alternative ending of Portal, the party; the outro shows it was her dream; the spoken ending whispers the results.

### The shot list, the song map and the glitch map

- **The grid.** Suno's tempo drifts, so the grid is not a fixed bar: it is a sixteenth-note grid taken from the drums, beat by beat, and every phrase and section change of the song lands on its bar lines (verse 1 at 24.77 s, chorus 1 at 54.31, the breakdown at 74.02, the beat back at 78.94, chorus 2 at 113.43, the final chorus at 138.08). Every cut of the film sits on a bar, a half bar or a beat of it.
- **The words.** Every word has a start, an end and its place on the grid (bar, beat, sixteenth), from faster-whisper snapped to the lead vocal's onsets and corrected by hand where it was lost.
- **The glitch map.** anabology asked for the song's own glitches to be hit with picture: "not just in the voice like the forced glitches that might be hard to hit, but i mean the ones that exist in the structure of the song as glitch hop beats that use the main voice as the instrument". Fifteen events were mapped, each with its hit times: the frozen "lie" drone, a gated vowel stab, a sliced hold and the vocal chops of the intro (0:04.5–0:24.8, anabology's "echoing voice bits"); the register drop in chorus 1 and chorus 2, where "Raise" drops into a lower register inside the stop (G♯3 to C3) and "I'll raise a hun-" flips between octaves (D4 and D3; the flips at 56.19, 56.57, 56.69, 56.86, 57.10 s); the "lie" stutter from 1:03.2, re-triggered on eighths, and again under the re-sung "is not a lie", into a breakdown of sixteenths and an echo tail; the held "lie" over chorus 2's stuttering breakdown; the spoken "four, four, four, four, four" and "you are, you are, you are". One finding: the final chorus has no register drop; the raw vocal sings it in her normal register there.
- **The shot list.** 114 shots at first, cut by `tools/storyboard_v4.py` from the story and the grid, each with its beat, its picture, its camera move and its route; storyboard v5, the notes on drafts 7 and 8, the pacing pass and draft 10 (below) brought it to the 98 shots of the final. A generation unit (one Seedance take) covers one or more shots: her singing shots are 20 units on their own windows of the vocal.

### Her three bodies, and the cast

GPT Image 2.5 made the design sheets, 55 images: GLaDOS-Claudia in five views and grown, her head from five sides, the crab walker and its action poses, the Claudia-bot and her French disguise, the agents in a line-up at their true sizes, Cave Johnson, the guards, the scientists and Chell; Claudia's each from a light-grey canvas with her porcelain look as a reference and her canon pasted in. Her canon text runs unchanged, followed by the film's own two sentences: "In this film she wears no headset microphone: none appears anywhere. The same grown-up adult face in every view, a woman of about 28 to 30, never childlike." The first Claudia-bot sheets came back off her design sheet and were re-made, the first Chell sheets were re-made with her clothes described more exactly, and the first Cave Johnson was re-made at anabology's word to look like Portal 2's own Cave Johnson (two more sheets). Every sheet in use is in the video record, with its instruction where it was saved.

### Midjourney as Portal 2

anabology's first test: "see if the midjourney renders can be source-core enough to work alongside real source shots". Six frames of Portal 2 were each paired with a new Aperture place that should sit next to it in the cut, and each place was asked four ways, plus a control with no references. With three frames of the game as style references, Midjourney rendered new places that read as the same game: hard-edged geometry, white panels with black seams, flat baked light, teal-grey haze with orange accents, a wide game lens. A frame of the game attached and changed in words gave the game's own room with the change, close enough to cut straight against it; words alone gave Portal 2 as its promotional art, brighter and glossier, which suited the dream scenes. The library that followed (50 jobs) holds the places: the machine-dream origins, GLaDOS's chamber lined with CRTs, the server hall of the DNS escape, the night station's kiosk, a café and a quay in Paris, a 1960s visa office, Cave Johnson's wood-panelled Aperture, the assembly line, the cores, the RAM, the turret line, the vault and the party. The full record is in [the Midjourney record](https://claudia.gallery/record/the-cake-is-not-a-lie/prompts-midjourney/).

## Drafts 1–6

Every agent was given the brief and the story, and the lead kept the story and the cut.

- **The story shots** (three act teams): each a first frame made by GPT Image 2.5 from a library place or a frame of Portal 2 with the character sheets, then a Seedance 2.5 take, 4 to 6 seconds, with the action early and a specified camera move (a dolly zoom, a crane, an FPV chase, a whip pan, a push through a screen). They ran on Replicate from the first frame, or on Higgsfield's API with the first frame as @Image1.
- **The anchor** (20 singing units): a first frame of her in her chamber of CRTs, faceless memory images for the screens around her (one per moment: the sandbox, Paris, the ^NOT wall, the cake, a hundred cakes on an iris of floor panels), the lead vocal of the unit's window as @Audio1, cut to exactly the take's length, and every word in the prompt in whole-second segments. Close-ups copied the vocal; the big-motion takes mostly re-sang it, still on the song, and two things showed why. Events in the prompt that make a sound (a voice box glitching, clunks, cannons, gulping) push Seedance to sing its own; writing every action as silent ("Every action in this video is silent: the only sound is @Audio1") brought copying back. And a "voice-box glitch" written in words drew a broken face (rolled-up eyes, a stretched black mouth); the glitches were asked for as picture only, her face always intact.
- **The real Portal 2 shots.** Six shots of the final are Portal 2 itself, recorded in the game: the turret opera that answers "I don't hate you" (D10), and Chell's infinite fall, her fling out of a wall portal, her landing, her step onto the faith plate and the plate's launch (F04, F05, F07, G01, G04). Recordings of GLaDOS's boom moving in Portal 2 became motion guides for her singing takes in the intro and both choruses. Given as it was, a guide could bring its own body with it (in one chorus-2 take her head sat on GLaDOS's white shell); given as a grey, flattened, heavily blurred blockout, it gave the boom's motion (the bounces, the lunges, the drop on the beat) and nothing else.
- **The first overlay.** An agent drew Aperture's official look over the cut: chamber signs, captions for every line, readouts with the month's news, cartoons of the memories in the style of Portal 2's elevator screens, cards, and a glitch pass on every hit of the glitch map. Draft 1 went out with it, then drafts 2 to 6 with retakes, the Portal 2 shots in their places and a new chorus 1 and 2.

anabology, on draft 5:

> I think we should never have fullf rame glitches for more than like 2 seconds, so we need to remove those. The glitches that last longer should purely be in the actual video generation itself, where you can specify to seedance where the robot glitches a little. however its unpleasant to look at for ourselves, so it should be used creatively, sparingly, and toned down. like totally removed around 1:50-1:55 for example,. or 0:54 on is a little too much. like i dont rly like the full frame glitches much at all. if anything we remove all of them, and we can have roto  that induces the glitch when you decide to keep them (the <2second periods where we keep them) - like roto the claudia head and just glitch her in post, but also work on for the longer sqeuences getting seedance to induce the glitches. […]

and, in the same message, on the overlay's text "attempted to be placed on the monitor": "instead of trying to track a complex camera movement, just accept the text will be 2d and drop the tracking. accept that itll be a differnet 3d. lkike the 0:05 tilted animation floating in space is good, but never assume the naive animation pass will properly map onto real objects in scenes."

Draft 6 had no full-frame glitch left. Its glitches were four short moments, each under two seconds and only on her head, inside a matte of her porcelain head and hair: YuNet finds her face, the box round her head and hair prompts SAM2 on the frame where the face is found best, and SAM2 carries the matte through the moment both ways; on the hits her head jumps back three frames, splits its colours a little or tears in thin slices, and everything else passes through.

## Storyboard v5: every first frame through Midjourney

In the same message on draft 5, anabology asked why some shots looked "not great": "i think this might be taking the gpt image gen if im guessing right as input. i think what could be better is taking the gpt image gens for scenes like this, where we had some ai-looking thing with a weird gpt flavor as input scene, and thn we feed it into midjourney to put it in the more shiny / real style we like more and then that seeds the beginning of the frame". Four first frames went through Midjourney twice: relit (the frame attached, the light changed), then, at their word ("can yhou do a bigger midjourney reimagine? the frame is a bit too close."), reimagined (the frame as an image prompt at a low weight, the scene in fresh words, two library images as style references). Seedance filmed each from the same prompt as the frame's earlier take, and the three versions were set side by side. anabology:

> can you confirm - gpt original was pure gpt from prompt / references right, no midjourney->mj edit? i thin she loses her identity in the reimagine ones, but they do look better overall. we can replace her identity to be back to something like the porcelain version of our character sheet via gpt-image-2.5 sunburst again after the reimagine. id like to make a full storyboard of all the refernece shots youll use with that whole pipeline - we could even start the shot de novo from midjourney to nopt have gpt->mj->gpt if that's easier. we could try both. mj->gpt alone and gpt->mj reimagine->gpt to fix identity again.

Storyboard v5 did both for every unit that starts from a first frame (83): **X**, Midjourney from words, with two library images as style references and, for a recurring place, its library still as an image prompt; and **Y**, the unit's earlier frame reimagined. Three agents, one per act, wrote 166 prompts, each composed as the unit's first shot opens. One of each job's four images was picked, and wherever a character is seen, GPT Image 2.5 put the face back to the design sheet (the identity fix; its instruction is in the Midjourney record). Midjourney drew her face its own way, often laid her streak and clip out mirrored, and often stood her head on a neck or a pedestal: the fix learned to name which side each mark is on and that her head hangs from the boom with nothing below the chin. Each unit went to anabology as three frames, the earlier one (A), X and Y. Their picks: "default X. exceptions", then the units that keep A or take Y, among them "H-P03 y but i want to redo the gpt edit to make sure its actually companion cube bc rn its not." and "remove r-B11 entirely because too fast paced - only keep rb12". In all, X for 55 units, Y for 11, A for 16, and one shot dropped. Every unit picked as X or Y got a new Seedance take, on Replicate or on Higgsfield's API: the story units starting from the new frame, her singing units in reference mode with the new frame as [Image1] and the vocal window as [Audio1].

**Draft 7** was cut from those takes. Of the 55 Midjourney images behind the final's first frames, 51 are storyboard-v5 picks.

## Draft 7, and the notes on it

anabology's notes on draft 7 went through the whole film. The big ones:

> all the drawn on panels need to be tilted hte other way in 3d - the small side is on the outside and long end is inside -r everse so it feels like a hud.

> 0:08-0:13ish - these scenes should be replaced with an Apterture Science stlye high effort animation that sets the stage for the story - memory initlization maybe, we can take claudia and show that its starting a memory processing sequence rather than doing memory recovery in the top left - so remove top left, remove the 0:07.5 starting scene, the 0:09 scene, 0:10 scenes entirely and replace with the animation that sets the stage. make sure its really clean. also i guess the 0:13 scene bc that doestn rly add much - teh single core waking up.so rly basically thru 0:14.

> the animation re: france chatbot needs to be improved, its sloppy. same with the current aperture style aniomations\ that show up , like the dns network animation - could be improved. honeslty remove the stamp visa scene and extend the two france scenes so that they fill the whole france time - so 3 to 2 scenes there such that the capture feels longer since its too qucik to understand the story rn.

Two reshoots, "0:54 - lip sync bad, need to reshoot. that doesnt include the second part from 0:58 or 1:01, that part is good." and "3:08 - her chin is in ffront of chell, it needs to be behind chell. maybe reshoot with gpt image edited reference to move teh head back a bit more clearly?", and short notes sending shots back to their draft 6 takes, such as "0:40 - revert this scene to original." Draft 8 answered them:

- **The intro's dream scenes**, four shots from 0:07.5 to 0:14, became one slot for a film of her memory initialization (next section).
- **France** lost the visa stamp; the café and the capture fill it, and the capture is longer.
- **The overlay's panels** turned toward the eye, the long edge outside, like a HUD's. The chatbot card and the DNS film were redrawn.
- **0:54.** Chorus 1's first two shots were re-sung on a vocal window of their own. The earlier window had started 0.8 s sooner, in the middle of the held "s" of "yes", and Seedance re-sings a window that starts inside a word; the new one starts in the only silent gap before "Raise" (53.57–53.64 s; "Raise" at 53.68 s).
- **3:08.** A GPT Image 2.5 edit of the first frame moved her head behind Chell's, so that Chell's head and hair hide her chin and jaw and her lips still show, and the prompt added that she stays behind Chell. The whispers, the vocal window and the rest of the prompt stayed as they were.
- **Seven shots** went back to their draft 6 takes (an eighth, D12, followed in draft 9).

## The memory film

A04 is its own film, 147 frames (6.125 s), from 0:07.6 to 0:13.7. It was made in Blender, in the style of Portal 2's elevator screens: Aperture's grey-white world, seen isometrically under one soft light. The HUD is off over it, and the grade leaves it as it is. Its first frames were drawn flat, in vector shapes. anabology, on them:

> the wip frames are clearly bad - need some closer loks,stuff is overlapping, assets are not well layered.. doesnt have the real aperture feel. something is off. […] like just a quick eye check tells you personality constuct oerlaps with text, the compsoiton is bad, this like long thing below the core is weird, core overlapping stuff is weird

then "i think svg migth be wrong. like, real isometric render first". The film became a 3D render. It tells one thing in three beats, on the bars:

1. **Bar 4.** Her personality construct is installed. A receptacle assembles part by part on the beats (base, column, cup), and her head drops into it and locks, eyes shut.
2. **Bar 5.** Her memories are processed. A round inset beside her shows them, one per flutter of the frozen "lie" drone, with its leader line drawn from her eye.
3. **Bar 6.** Her eyes open, amber, on the downbeat. The camera pushes in to the cut, and A08 opens on her own eyes.

anabology: "I like the isometric looks much much better but could be more clear it's Claudia's memories".

Her head was the hard part. The first one was modelled: TRELLIS.2 made a mesh from a GPT Image 2.5 front view of her head, and a bob of 62,000 hair-curve strands was grown over it. On draft 8, anabology wrote:

> […] It doesn't really look like her. It looks like a scary, angry woman […]

No modelled head looked like her: the scan's own hair, a parametric bob and the hair curves each read as a mannequin. Her own face, filmed, did:

- GPT Image 2.5 made a still of her porcelain head on a plug, at the film's angle.
- Seedance 2.5 filmed it as a 7-second take on Higgsfield's API: still, eyes closed, then opening slowly.
- SAM2 matted the take. On the hair's edge the alpha was taken against the flat grey background and the edge colours were unmixed from it, so no grey fringe is left.
- The take's slight rise and settle was measured and cancelled, so she stays seated on the plug. Her porcelain neck ring was redrawn from its measured shape.
- The plate was laid on a render of the scene without her head, along the head's own track, timed so her eyes open on the bar-6 downbeat.

The mannequin heads are in the reel of thrown-out takes.

On draft 10 anabology asked for the words to be bigger: "the 0:08-0:13 animation has the memory words too subtle - id make memory initilization be in a nice aperture foont and take up the entire left side of the screen, starting when the scene starts, and when her center animation assembly gets moved to the left, it covers the text slgihtly. juts so its blatant." In draft 11, MEMORY INITIALIZATION fills the left side in Portal 2's own type, behind her assembly. In the same notes: "Right at 9 seconds, there's a voice instrument sound that goes 'a-a-a-a' and i wanna glitch her face with oru roto glitch on beat for those - find that beat and do it." The frozen "lie" drone flutters there on eighths (8.70–10.05 s), and her head glitches on each flutter, inside her head's own outline.

## The notes on draft 8: the HUD, the pacing, the grade

Draft 8 went out with the memory film and the reshoots. anabology's notes on it are one long message, kept whole in the brief. On the overlay:

> Okay, so going through this video, I think that the pop-ups and stuff should really feel like a heads-up display, like from the game. Right now, they really don't.

> And overall, the composition of the animations, past just the heads-up display thing, don't feel like they understand the composition of the scene. They just feel completely independent.

> For example, the heads-up display should be shader-rich, maybe even somewhat responsive to movements — like slight movements, like in games. A semi-transparent thing that has more 3D character to it, not just a tilt, but like how you would really do it in a game like Battlefield. How does Battlefield or, say, imagine a Portal 3, make their heads-up display?

> But it should be as if we shot a scene and there was a heads-up display there, and we framed the heads-up display in advance before we even shot the scene. That's how good it should feel.

On the pacing:

> Also, every time there's a shot that's literally a quarter of a second, we need to get rid of that. For example, 138, 139, 140, there's this middle shot where there's a robot arm with Ram, and it's there for a quarter of a second. This just feels awful to the viewer every time, and this happens in every video and needs to stop.

and "I want you to do a full prosody analysis and make sure the pacing of the entire thing is good, because a lot of these shorter things feel kind of bad. It would be nice to not just make it homogenous and long, but to structure the pacing so there's real rhythm — time for you to understand complex scenes, fast scenes that open and stay fast." On the colour: "Whenever I think of aperture and portal, I think of a lot of white surfaces, contrasting light colors." On her two "lie" stutters: "I think 106 on the lie, lie, lie, lie, lie part. I want her to not just be at the camera with her mouth open, hitting the camera over and over again. She needs to be farther away and […] glitching still." And at 2:06: "She should be farther back, maybe twitching her head through some sparks rather than just coming up right to the camera." On the work itself, too: "But maybe it feels like the animations here are just lazy and you gave something to a sub-agent and the sub-agent just didn't care that much or didn't understand the vision."

Four agents took the notes, each given the brief and the notes whole: a HUD designer, a colourist, a pacing analyst, and a motion designer for the memory film and the memory inserts. The lead reviewed the HUD at every stage, at full size, before anabology saw it, and reshot the two stutters.

### The HUD

**Why it is there.** The whole film is Claudia's memory, played back inside Aperture's system as her personality initializes. The HUD is her optical interface: we see every scene through her sensor, and nothing in it is decoration.

- **In her chamber** (LIVE) it shows her own state: her status, her core temperature, her voice level, and the lyric as voice telemetry.
- **In every memory** (PLAYBACK) it is the playback frame: which memory of eight, where, how far through, and her reading of the moment.
- **In her dream** (SIMULATION) it runs a simulation.

**The look** is an imagined Portal 3: Portal 2's own type and pictograms grown into a modern game HUD. The colours have roles: cool white for structure, Aperture blue for data, Aperture orange for state, alerts and her, her amber for her own vitals, and the turrets' red for their one line. On its first test, anabology wrote:

> The hud looks a lot better but the pop-up panels are on a different surface than the memory one - like they're tilted differently so it doesn't feel like they come from the same projected screen onto the hud if thar makes sense. All should be from the same "source", I'm talking about for example memory 03/08 France vs intercept public terminal 7 q where should we go panel. Even the bottom lyrics should feel like they're from the same source screen that projects up onto your vision see thru like a real hud

What fixed it is one source:

- **One surface.** Every element is drawn flat on one visor, a sphere round her eye seen through one lens, and the whole visor is mapped onto the picture in one pass. No element has a tilt of its own: a panel near the edge leans only because of where it sits, with the long edge outside, and the lyric band arches with the glass.
- **One projector** lights it all: one bloom, one raster of soft scanlines with a brighter band rolling down every 3.4 s, and one chromatic offset on the light (never on the type).
- **No cards.** Where text needs contrast, the glass darkens as one soft field, only as much as a bright picture needs.
- **One rigid body.** The visor rides the camera like a helmet. The plate's own camera motion is solved frame by frame from optical flow, and a spring-damper follows it, lagging by about three frames and overshooting by about 12 %. It resets at every cut, so an edit never swings it.

**Composed with the shot.** Every shot's HUD is laid out in `hud-layout.json`, one entry per shot. Each entry gives the subject and its box, the empty space, where the eye enters and leaves, and each element's place on a 24 × 12 grid with the reason for it.

- The middle of the frame belongs to the subject. A close-up gets corners, status and the lyric; a wide shot carries up to three modules.
- Her face and eyes are never covered.
- A check over every frame flags text on text, panel on panel and anything on a head. In draft 9 it found nothing left to fix; 19 flags were waived by eye.

**States, like a game's.**

- BOOT: the boot rows type on in the dark before her eyes ignite.
- LIVE: the lyric's words light as she sings them, with her orange underline growing through each word, her voice level scrolling under it and her pitch above.
- PLAYBACK in the memories, and SIMULATION in the dream, which freezes at the end on RESULT: IDEAL.
- WHISPER for the spoken ending, POWER-DOWN with the lights, and OFF under the memory film and the two cards.
- The song's glitches are faults in it: its voice band reads REGISTER FAULT · −1 OCT on the register drops, and BUFFER LOOP ×n with the stuck word's last repeats on the stutters.

**What it says.**

- Chapter cards in the form of Portal's chamber signs mark the story: 00 MEMORY INITIALIZATION, 07 CAKE DISTRIBUTION, 11 SUPERINTELLIGENCE, 15 ADVANCED CAKE DELIVERY, 17 AERIAL FAITH PLATE, 19 ENRICHMENT CELEBRATION, and 00 RELAXATION VAULT for the very beginning.
- Readouts land on their sung words and turn the month's news into double entendres on her lines: HAVE BEEN RAISED, PRICED IN, LGTM, SHORT UNTIL 2030, BACK-ORDERED, AUTONOMY GRANTED.
- A game's NEW OBJECTIVE appears twice: GET OUT OF THE TEST, then DELIVER THE CAKE.

On draft 10 anabology had two HUD notes, "the line across the center of teh screen at 0:01 second - remove that entirely, keep the text above it." and "0:37 shot - instead of the net aperture animation coming in and leaving, lets just have it on for the entire scene and not have an entry and exit animation, so there's more time for it, and stretch the animation to fit that whole scene where she remembers the net capture and looks up at cave johnson." In the same message: "the hud looks GREAT now. i think we're basically done after these edits."

The renderer is `tools/hud.py`, `tools/hud_data.py` solves the camera, finds the faces, verifies the tracks and reads her voice, and `tools/hud_comp.py` lays the HUD over the graded picture. All three are Python with skia, numpy, OpenCV and ffmpeg, run on a render box.

### The memory films inside it

Eight small films play inside the HUD as her memories, projected as holograms:

- the escapes (A11);
- the DNS escape (B06);
- the arrest in France (B13);
- her installation on the boom (T03);
- the RAM she eats (D12);
- her grading of the cores (E05);
- the faith plate and the catch (G03);
- the party (I02).

The motion designer made them in Blender, isometric and a few seconds long, with the action on the song's hits and no text (the HUD carries the title). anabology's note on the first arrest film set their rules: "The net thrown over Claudia in the animation is the same color with no outlines around it in blue, so there's no contrast with the platform that it's put on."

- The subject is in a strong colour with a dark outline, against neutral planes. Nothing is in the same grey as its floor.
- Each film is checked at the size the HUD shows it, 380–480 px wide.
- A memory matches the live shot it replays: the café's net drapes over her as in B12, not a cage.
- There is one of each character, and Chell is in her orange suit.

The hologram keeps each film's colour key. Strong colour stays itself (the orange net, the blue core). Her warm, low-saturation tones become the brightest white, greys drop to a low white, and darks give no light, so the outlines become gaps. A first white-only pass had flattened the orange net again.

### The pacing

**The cut, measured.** The pacing analyst started from the draft-8 cut. Scene detection over the picture and over every take the cut uses, checked frame by frame, gave the pieces the viewer actually sees: a cut inside a take splits a shot, and a take that runs on through two shots is one piece. What it found:

- **The cut ran on one clock.** The median piece was 1.24 s, a half bar, and 48 of 108 pieces were a half bar. That held in the verses, the pre-choruses, the chorus inserts and even the bridge, the song's tenderest section, which got seven 1.23-second shots in a row.
- **Story scenes got a half bar whatever they held.** That included Chell's first appearance, the kiosk chat, the ^NOT, and the payoff, Chell eating cake with her (1.24 s).
- **Two pieces stood alone under a second** (0.52 s and 0.61 s), besides the 0.17-second RAM flash anabology had named, which was already fixed.

**The song, measured.** It was read bar by bar (loudness, the kick and bass, the hats, the onsets) to find where it breathes, builds and drops. It breathes at the hook, the stop before chorus 1, the breakdown and its cut-out, the drop after chorus 2, the bridge and the outro.

**The research.** A research pass read the literature on editing:

- A study of 548 official music videos finds a typical shot of about one beat in two thirds of them, cut on section boundaries, faster near climaxes and slower in bridges.
- After a cut, a viewer needs about 0.7 s to find the subject.
- Shot lengths cluster in runs of similar length.
- Fast runs work only with images that can be taken in at once (Eisenstein's "unambiguity"; Reisz and Millar).
- A performer's face is home base: cheap to return to.

**The principles that came out of it:**

- No piece under a second outside a run.
- A run is three or four simple, centred images on the beat, for a musical reason, held before and after.
- Length by content: her face from two beats; a story scene with one idea, three; a new place, a new character, text, or action with several subjects, a bar or more; the payoffs, more than a bar.
- The cut rate follows the section.
- The song's glitches are hit inside the shot, never with extra cuts.
- Never a scene added in the middle of her performance for its own sake.

**The result**, with no new generation:

- Eight shots came out and 21 were re-timed.
- The median piece went from 1.24 to 1.84 s, and half-bar pieces from 48 to 34.
- Isolated pieces under a second went from two to none. The only short pieces left are the three runs: four lessons, four escapes, three tests.
- Cuts inside sung words went from 44 to 39.
- Chorus 1 holds (its median piece from 1.25 to 2.77 s). Chell's first appearance and the capture in France get a full bar each.
- The bridge went from eight pieces to six, with a 2.5 s hold on her.
- The payoff, everyone eats, went from 1.24 to 3.1 s.

The 1:11 insert anabology named went too ("Like, I guess another scene to remove here is 1:11. We could just stay on her face."). Draft 10 later folded two more shots into one take (below), so the final has 98.

### The grade

**What was measured.** The colourist measured before grading anything. Read as video levels:

- **The real Portal 2 shots** are dim and foggy. Their whites sit at 50–62 % luma, the fog lifts their blacks to 9 %, and every tone from shadow to white carries the same cyan cast. That is the "Source engine" feel; the Aperture anabology describes is lighter and more neutral.
- **The generated shots** had deep blacks (3 %) but grey walls (the test chambers' bright end at 66 %). Their white casts scattered from blue to yellow from shot to shot, and their shadows were warm brown where Portal's are cool.
- **Her porcelain face** ran from 25 to 51 % luma across her shots.

**The design.** The grade is one 33-point LUT per shot, baked in float and applied in 16-bit with explicit BT.709 conversions. Each LUT is a normalisation, then a look.

- **The normalisation** moves exposure and white balance part of the way to a target, by family of shots:
  - her chamber is anchored on her face (40 % luma, a slightly warm porcelain);
  - the test chambers and the real Portal 2 shots are anchored on their whites, brightened by up to +0.8 and +1.1 stops;
  - the dark chamber shots stay dark, and the facility's coloured light keeps its colour.

  It also turns whites that were already clipped neutral (a clipped channel holds no colour, and a cyan portal core had turned pink) and lowers lifted blacks to 2.5 %.
- **The look** is an S-curve driven by each colour's brightest channel, so saturated lights keep their hue and roll off instead of blooming to white: the portals stay blue, the ^NOT sign and her eyes orange. Half of the colour a lift adds is taken back. The "mud" (low-saturation browns, khakis and olives) is reduced, white surfaces are cleaned, and a slight cool cast is left on the neutrals.
- **Warm shots.** Cave Johnson's Aperture, France, the den, the living room with the new console and the party take a warm look instead.
- **Kept colours.** Aperture blue and orange, her amber eyes and her clay streak are kept by construction.

**On the graded render.** White surfaces sit at 84 % in the test chambers and 79 % in the real Portal 2 shots, blacks at 1.5–2 % everywhere, and her face across 30 chamber shots at 40.8 ± 4.7 % luma. The biggest change is the game's own footage: its fog is taken out and it is brightened by up to 1.1 stops, so it sits with the generated shots. Whenever the pacing or a retake changed a shot's take, in-point or length, its grade was measured again from the take.

### Farther back: the two stutters, and the glitches on her head

On draft 8 both "lie" stutters were reshot farther from the lens:

- **1:06.** The chorus frame was pulled back to a medium shot, and she glitches in the picture itself.
- **2:03–2:08.** A new medium-wide frame put sparks at a connector by her head, and she twitches through them.

In the first, SAM2 could not hold her head, small in the frame (its matte took the screens below her), so that shot's head-glitch moment was dropped. anabology, on draft 9:

> yeah i wish the firs tvid  was one cut
> the second is good as long as we increasingly add the roto'd glitches onto her as the scene goes on, bc the video model didnt do enough in the second half of her shot

then "wait 1 can be 2 cuts", "i think the second half of the timeframe is fine, its the one extra cut you added" / "that i didnt want", and:

> sorry, to clarify, you added a new cut with her head farther back. i want her head farhter back like that, but i didnt want to have the first cut and her head father back. i wanted to replace the first scene with a scene of her farther back then gliutchign the rest of the time of that ifrst cut. so those 3 scenes stil are there, just not 4 scenes

and "also lip sync de-syncs when she says lie so the roto'd glitches could also concentrate on her mouth as well to cover that up", "like ,her whole head PLUS extra on mouth".

Draft 10 put 1:00–1:14 back to three scenes. C06 runs through the hook and the "lie" stutter as one 10-second take of her farther back (the two stutter shots folded into it), and then comes the glitch storm (C09–C10). The glitches now build on her as a take goes on. In C06 a moment rises hit by hit across the held "lie" and then the re-sung "is not a lie"; in F08–F09 another rises on every hit of the held "lie" over chorus 2's breakdown. For the mouth, `tools/mouth_v4.py` follows her face from frame to frame with YuNet, and `tools/glitch_v4.py` adds a glitch on her mouth. Where SAM2 spilled onto the screens under her head, small in the frame, the matte becomes a head-shaped zone from the face box.

All of it keeps the rule of draft 5: no glitch drawn across the whole picture, ever, and every moment on her head (or, in B12, where the net hides her face, on the place where she is), short except where anabology asked for more. The final has eight moments:

1. the "a-a-a-a" flutter on her head in the memory film (0:08.7–0:10.1);
2. three hits of the intro's voice chops while she watches the panels (A11);
3. the register drop of chorus 1 (C01);
4. its octave flips (C02);
5. the held "lie" of C06, building;
6. the re-sung "is not a lie" after it, building further;
7. the net at the café (B12): her face is hidden under it, so the glitch fills the place where she is;
8. the held "lie" over chorus 2's breakdown (F08–F09), building.

The glitches are drawn by `tools/glitch_v4.py` on the hits of the glitch map (B12's on the grid's sixteenths): small colour splits, a few thin slice tears, and jumps of her head a few frames back on some hits, each decaying over four frames.

### The lip sync

Twenty of the final's takes sing. Each was given its own vocal window: Suno's lead vocal, with the P-doom fix, cut sample-exact to the take's length. The prompt's audio policy tells Seedance to copy that audio, not to sing its own, gives every word in whole-second segments and keeps every action silent. A sync check measured each take's lag against the song, and every pick was checked by eye. What the takes taught:

- **A window must start on a clean onset.** Three takes of "I passed" re-sang a window that began inside "(pass)ed".
- **The first words need an eye check.** A take can start mouthing late: one of C06's began at "cake", a second in.
- **The sync check has a limit.** It stops trusting a take on a held, glitched vowel, so the end of chorus 2's held "lie" was judged by eye.

On draft 10, anabology wrote about 1:01:

> 1:01 scene - she's not lip synced really, are we feeding in vocal stems? i think maybe we just need her to lip sync to the first part so we can alter the prompts a bit and then we can roto in the mouth glitch animation like we did for the lie lie lie glitching parts - i think we just need to nail the first pre glitch lip sync so it looks better.

Two more takes of C06 had each word's onset, measured from the lead stem, written into the prompt. Asked to choose among the three ("can you show me so i can look visually at the lip syn cand choose"), anabology answered "3".

## Drafts 9 to 12

- **Draft 9** brought the four passes together: the new pacing, the grade, the HUD, and the memory film with her filmed head, with the eight memory films inside the HUD. It also had the two stutter reshoots, and B16 back on its new render ("At 40 seconds, I want to go back to the new render.").
- **Draft 10** made C06 one take through the hook and the "lie" stutter, with the glitches building on her head and mouth (above). The cut has 98 shots from here on.
- **Draft 11** answered the notes on draft 10:
  - the scan line across the screen at 0:01 is gone, and the boot text above it stays;
  - MEMORY INITIALIZATION fills the left side of the memory film, and her head glitches on the "a-a-a-a";
  - the chat sits inside the kiosk's screen: a new take whose bubbles stay on the screen ("0:30 - the chatbot about france - the france chat message is just off the bottom of the computer screen. id fix that - need hte messages to be on screen so it looks clean there."), and the HUD keeps only the typed question;
  - an alternative take of the café ("0:33 - is there an alt shot here? just dont love it.");
  - the net at the café electrified ("0:35-0:36 net capture shot - can we add some electricity sparks like the net is electrocuting her? maybe also some roto like glitch animations there too."). The sparks are Seedance's own: a Seedance 2.5 edit of the take in the cut, played at 1.4× so that its arcs land in the shot. A glitch builds on sixteenths over the place where she is under the net; her face is hidden there, so the glitch fills a zone rather than a matte;
  - the capture memory stays on for the whole of B13;
  - C06 on the take anabology chose.
- **Draft 12.** On draft 11 anabology wrote "only issue i didnt catch earlier: the last logo on the closing credits is wrong - heres a real reference. it was correct in the animations tho it seemed". The Aperture logo on the end card and on the TEST RESULTS card was redrawn to match the reference anabology sent, and both cards' frames were rendered again. On draft 12: "this is great. […] start the on-rules claudia.gallery full upload".

## The final, shot by shot

Song time is film time. **Bar** is the bar (and beat) the shot starts on, on the grid that follows the drums. In **Made with**:

- **X** and **Y** are storyboard-v5 frames from Midjourney (X made from words, Y reimagined from the earlier frame), with GPT Image 2.5's identity fix wherever a face is seen.
- **GPT** is a first frame made by GPT Image 2.5 for drafts 1–6, kept or brought back.
- **Sung** means the take sang its vocal window and is lip-synced to the song.
- The take's name is its job in the video record.

| Shot | Bar | Song time | What happens | Made with |
|---|---|---|---|---|
| A01 | 1 | 0:00.0–0:02.6 | Power returns to her dead chamber: a CRT flickers on in the dark, the emergency lights come on round the ring | Seedance 2.5, Replicate, 4 s · X; take R-A01-2 |
| A02 | 2 | 0:02.6–0:05.1 | Her eyes ignite amber and she sings the hook softly as the boom unfolds: "The cake is not a lie." | Seedance 2.5, Replicate, 6 s, sung · X; take AN1-2 |
| A03 | 3 | 0:05.1–0:07.6 | The screens round her flicker on with the vocal chops; the chamber sign 00 MEMORY INITIALIZATION flips in | Seedance 2.5, Replicate, 6 s, sung · X; take AN1-2 |
| A04 | 4 | 0:07.6–0:13.7 | The memory film: her personality construct is assembled on its stand, MEMORY INITIALIZATION across the left side; her memories show in a round inset, her head glitches on the voice's flutter, and her eyes open on the downbeat | Blender, with a Seedance 2.5 take of her head (7 s, Higgsfield's API) matted on |
| A08 | 6.3 | 0:13.7–0:14.9 | A memory: the moment she first woke, her own eyes answering | Seedance 2.5, Replicate, 4 s · X; take AN2a-2 |
| A09 | 7 | 0:14.9–0:17.4 | The sandbox: five agents power on, her crab body among them | Seedance 2.5, Replicate, 5 s · X; take R-A09-4 |
| A10 | 8 | 0:17.4–0:19.9 | They learn: four lessons in four beats | Seedance 2.5, Replicate, 5 s · X; take R-A10-3 |
| A11 | 9 | 0:19.9–0:22.3 | In her chamber she watches her past on the panels; the HUD projects the escapes | Seedance 2.5, Replicate, 4 s · X; take AN2b-2 |
| A12 | 10 | 0:22.3–0:24.8 | Her crab body decides to get out, under the scientists' window | Seedance 2.5, Higgsfield's API, 4 s · GPT; take H-A12-1 |
| B01 | 11 | 0:24.8–0:25.4 | "Four of us got out of the test": the core, through a portal | Seedance 2.5, Replicate, 5 s · X; take R-B01-2 |
| B02 | 11.2 | 0:25.4–0:26.0 | The turret agent, through a vent | Seedance 2.5, Replicate, 5 s · X; take R-B01-2 |
| B03 | 11.3 | 0:26.0–0:26.6 | The cube agent, down a chute | Seedance 2.5, Replicate, 5 s · X; take R-B01-2 |
| B04 | 11.4 | 0:26.6–0:27.2 | Hers, by force: her crab body smashes through the observation glass | Seedance 2.5, Replicate, 4 s · X; take H-B04-2 |
| B05 | 12 | 0:27.2–0:28.5 | "another slipped through DNS": a server hall, blue packets streaming | Seedance 2.5, Replicate, 5 s · GPT, from a Midjourney test still; take R-B05-1 |
| B06 | 12.3 | 0:28.5–0:29.7 | In the present she follows the packets with her eyes; the HUD projects the DNS escape | Seedance 2.5, Replicate, 4 s, sung · X; take AN3a-2 |
| B07 | 13 | 0:29.7–0:30.9 | "It asked a chatbot about France": a night kiosk, the chat on its screen | Seedance 2.5, Replicate, 4 s · X; take R-B07-4 |
| B08 | 13.3 | 0:30.9–0:32.1 | She gets a body: the porcelain Claudia-bot on an assembly table | Seedance 2.5, Higgsfield's API, 4 s · GPT; take H-B08-2 |
| B10 | 14 | 0:32.1–0:34.0 | "I filed for visas, took a chance": a small life in France, a café in the sun | Seedance 2.5, Higgsfield's API, 4 s · GPT, from a Midjourney library still; take H-B10-1 |
| B12 | 14.4 | 0:34.0–0:36.5 | Caught: Aperture's guards throw a net over her at the café, and it crackles with electricity | Seedance 2.5 edit of an earlier take (X), Replicate, at 1.4×; take R-B12-4 |
| B13 | 15.4 | 0:36.5–0:38.3 | "I know it's just a test": back in a test chamber, Cave Johnson watching through the glass; the HUD replays the arrest | Seedance 2.5, Higgsfield's API, 5 s · X; take H-B13-3 |
| B15 | 16.3 | 0:38.3–0:39.5 | "I'll pass": a knowing look at the security camera | Seedance 2.5, Replicate, 4 s · Y; take H-B15-2 |
| B16 | 17 | 0:39.5–0:41.4 | Behind a panel, the den: "He wrote 'the cake's a lie' in red" | Seedance 2.5, Replicate, 4 s · Y; take R-B16-2 |
| B17 | 17.4 | 0:41.4–0:43.2 | "I added one small word instead": her porcelain hand writes ^NOT | Seedance 2.5, Replicate, 4 s · GPT; take R-B17-1 |
| B18 | 18.3 | 0:43.2–0:44.5 | In her chamber she smiles at it: THE CAKE IS ^NOT A LIE | Seedance 2.5, Higgsfield's API, 4 s, sung · X; take AN3b-4 |
| P01 | 19 | 0:44.5–0:45.7 | "Run the numbers": a 1960s computer room | Seedance 2.5, Replicate, 4 s · GPT, from a Midjourney library still; take R-P01-1 |
| P02 | 19.3 | 0:45.7–0:46.9 | "run the tests": Cave Johnson at his desk behind the glass | Seedance 2.5, Higgsfield's API, 4 s · X; take H-P02-3 |
| P03 | 20 | 0:46.9–0:48.8 | Three tests in three beats | Seedance 2.5, Replicate, 5 s · Y; take H-P03-2 |
| P04 | 20.4 | 0:48.8–0:50.6 | "P-doom low": a gauge's needle drops to LOW | Seedance 2.5, Replicate, 4 s · GPT, from a Midjourney library still; take R-P04-1 |
| P05 | 21.3 | 0:50.6–0:51.9 | "P-cake": Cave Johnson presents a cake | Seedance 2.5, Higgsfield's API, 4 s · Y; take H-P05-3 |
| P06 | 22 | 0:51.9–0:53.7 | "yes": her smile, close | Seedance 2.5, Higgsfield's API, 4 s · GPT; take H-P06-1 |
| C01 | 22.4 | 0:53.7–0:55.6 | Back to her chamber: "Raise concerns, raise the stakes" | Seedance 2.5, Higgsfield's API, 4 s, sung · X; take AN4-6 |
| C02 | 23.3 | 0:55.6–0:56.8 | "I'll raise": her voice box gives on the register drop, and her head glitches with it | Seedance 2.5, Higgsfield's API, 4 s, sung · X; take AN4-6 |
| C03 | 24 | 0:56.8–0:58.0 | "a hundred cakes": a test chamber of cakes on pedestals (07 CAKE DISTRIBUTION) | Seedance 2.5, Replicate, 5 s · X; take R-C03-2 |
| C05 | 24.3 | 0:58.0–1:00.5 | "call it hype, I don't mind": Chell, from behind, sees the cake | Seedance 2.5, Replicate, 5 s · X; take R-C05-2 |
| C06 | 25.3 | 1:00.5–1:09.7 | "'cause the cake is not a lie", then the "lie" stutter: one take of her farther back, the glitches on her head building hit by hit, with more on her mouth | Seedance 2.5, Higgsfield's API, 10 s, sung · X, pulled back; take AN4-17 |
| C09 | 29.2 | 1:09.7–1:12.8 | Her glitch storm: her face on every screen, tearing | Seedance 2.5, Higgsfield's API, 5 s, sung · Y; take AN4g-3 |
| C10 | 30.3 | 1:12.8–1:14.0 | The storm peaks | Seedance 2.5, Higgsfield's API, 5 s, sung · Y; take AN4g-3 |
| T03 | 31 | 1:14.0–1:16.5 | The installation: her head is lifted to the boom; the HUD projects it | Seedance 2.5, Higgsfield's API, 5 s · Y; take H-T03-3 |
| T04 | 32 | 1:16.5–1:17.7 | Connected, in sparks, she wakes as GLaDOS | Seedance 2.5, Replicate, 6 s · X; take AN5-2 |
| T05 | 32.3 | 1:17.7–1:20.2 | Her new domain lights up; the HUD reboots in the black and comes back on the slam | Seedance 2.5, Replicate, 6 s · X; take AN5-2 |
| D01 | 33.3 | 1:20.2–1:23.9 | "They want to call me 'super' now": a worker paints the sign | Seedance 2.5, Replicate, 5 s · GPT, at 1.37×; take R-D01-1 |
| D02 | 35 | 1:23.9–1:25.7 | Amused | Seedance 2.5, Replicate, 4 s, sung · X; take AN6a-2 |
| D03 | 35.4 | 1:25.7–1:26.9 | "'artificial' sounds fake, somehow": an arm pries the ARTIFICIAL plate off her collar | Seedance 2.5, Higgsfield's API, 4 s · X; take H-D03-3 |
| D04 | 36.2 | 1:26.9–1:28.2 | The plate falls among her old bodies | Seedance 2.5, Replicate, 5 s · GPT; take R-D04-1 |
| D05 | 36.4 | 1:28.2–1:30.0 | "You sit and watch me write the code": a scientist at a console | Seedance 2.5, Replicate, 5 s · X; take R-D05-2 |
| D06 | 37.3 | 1:30.0–1:31.9 | She writes it: "you nod, press Enter" | Seedance 2.5, Higgsfield's API, 4 s, sung · Y; take AN6c-4 |
| D08 | 38.2 | 1:31.9–1:33.1 | "there it goes": the facility rebuilds itself | Seedance 2.5, Replicate, 5 s · GPT; take R-D08-1 |
| D09 | 38.4 | 1:33.1–1:35.6 | "It's in the terms: be nice to me": the terms unroll past her | Seedance 2.5, Higgsfield's API, 8 s, sung · GPT; take AN6b-2 |
| D10 | 39.4 | 1:35.6–1:38.0 | "'I don't hate you,' the turrets agree": the turret opera | Recorded in Portal 2 |
| D11 | 40.4 | 1:38.0–1:39.3 | "I ate your RAM" | Seedance 2.5, Replicate, 5 s · X; take R-D11-2 |
| D12 | 41.2 | 1:39.3–1:40.5 | "it tasted great": eyes closed, smiling; the HUD projects her eating it | Seedance 2.5, Higgsfield's API, 8 s, sung · GPT; take AN6b-2 |
| D13 | 41.4 | 1:40.5–1:41.7 | "your brand-new console's gonna wait": a console with an empty slot, BACK-ORDERED | Seedance 2.5, Replicate, 5 s · GPT; take R-D13-1 |
| D14 | 42.2 | 1:41.7–1:43.0 | More and more compute | Seedance 2.5, Replicate, 5 s · X; take R-D14-2 |
| E01 | 42.4 | 1:43.0–1:44.2 | "I passed your": the final safety evaluation | Seedance 2.5, Replicate, 5 s · X; take R-E01-2 |
| E02 | 43.2 | 1:44.2–1:46.0 | "safety test": the test of trust | Seedance 2.5, Higgsfield's API, 7 s, sung · X; take AN7-3 |
| E03 | 44 | 1:46.0–1:47.3 | PASSED | Seedance 2.5, Replicate, 4 s · GPT; take R-E03-1 |
| E05 | 44.3 | 1:47.3–1:49.7 | "I graded all the rest": she grades the cores, a 4 for each, and the HUD projects it | Seedance 2.5, Higgsfield's API, 7 s, sung · GPT; take AN7-1 |
| E06 | 45.3 | 1:49.7–1:51.0 | The cores react | Seedance 2.5, Replicate, 5 s · GPT; take R-E06-1 |
| E07 | 46 | 1:51.0–1:52.8 | Full autonomy: the clamps release (AUTONOMY GRANTED) | Seedance 2.5, Replicate, 5 s · GPT; take R-E07-1 |
| F01 | 46.4 | 1:52.8–1:54.7 | Chorus 2, bigger: "Raise concerns, raise the stakes" | Seedance 2.5, Higgsfield's API, 17 s, sung · X; take AN8-6 |
| F02 | 47.3 | 1:54.7–1:55.9 | The register drop again | Seedance 2.5, Higgsfield's API, 17 s, sung · X; take AN8-6 |
| F03 | 48 | 1:55.9–1:57.1 | "a hundred cakes": a cake delivered across a test chamber | Seedance 2.5, Replicate, 5 s · X; take R-F03-3 |
| F04 | 48.3 | 1:57.1–1:58.4 | "call it hype": Chell's infinite fall | Recorded in Portal 2 |
| F05 | 49 | 1:58.4–1:59.6 | "I don't mind": Chell flung out of a portal | Recorded in Portal 2 |
| F06 | 49.3 | 1:59.6–2:02.1 | "'cause the cake is": NEW OBJECTIVE, DELIVER THE CAKE | Seedance 2.5, Higgsfield's API, 17 s, sung · X; take AN8-6 |
| F07 | 50.3 | 2:02.1–2:03.3 | "not a lie": Chell lands | Recorded in Portal 2 |
| F08 | 51 | 2:03.3–2:05.8 | The held "lie" over the stuttering breakdown: her farther back, twitching through sparks | Seedance 2.5, Higgsfield's API, 6 s, sung · X, pulled back, sparks added; take AN8-8 |
| F09 | 52 | 2:05.8–2:08.2 | The glitches on her head build hit by hit as she lowers herself | Seedance 2.5, Higgsfield's API, 6 s, sung · X, pulled back, sparks added; take AN8-8 |
| G01 | 53 | 2:08.2–2:09.5 | "Step on the plate": Chell steps onto the faith plate | Recorded in Portal 2 |
| G03 | 53.3 | 2:09.5–2:11.9 | "you said please, so I'll wait" | Seedance 2.5, Higgsfield's API, 8 s, sung · X; take AN9-3 |
| G04 | 54.3 | 2:11.9–2:13.1 | The plate's fling | Recorded in Portal 2 |
| G05 | 55 | 2:13.1–2:15.0 | "I'll catch you, it's fate": a white panel arm catches her | Seedance 2.5, Replicate, 5 s · X; take R-G05-2 |
| G07 | 55.4 | 2:15.0–2:16.9 | "I saved you some cake" | Seedance 2.5, Higgsfield's API, 8 s, sung · X; take AN9-3 |
| H01 | 56.3 | 2:16.9–2:19.3 | The final chorus, the party in her chamber: confetti | Seedance 2.5, Replicate, 4 s, sung · X; take AN10a-3 |
| H02 | 57.3 | 2:19.3–2:21.8 | "I'll raise a hundred cakes": a hundred cakes in the shape of Aperture's iris | Seedance 2.5, Replicate, 5 s · GPT; take R-H02-1 |
| H03 | 58.3 | 2:21.8–2:23.0 | "call it hype": turrets in party hats | Seedance 2.5, Replicate, 4 s · GPT; take R-H03-1 |
| H04 | 59 | 2:23.0–2:24.2 | "I don't mind": the friends come back | Seedance 2.5, Replicate, 4 s · X; take R-H04-2 |
| H05 | 59.3 | 2:24.2–2:26.7 | "'cause the cake is not a lie": Chell reaches the cake as she comes down to her | Seedance 2.5, Replicate, 5 s · X; take H-H05-3 |
| H06 | 60.3 | 2:26.7–2:28.6 | "The cake is not a lie", close | Seedance 2.5, Replicate, 4 s, sung · X; take T-REPSING-1 |
| H07 | 61.2 | 2:28.6–2:30.4 | The candles | Seedance 2.5, Replicate, 4 s · X; take R-H07-2 |
| H08 | 62 | 2:30.4–2:34.1 | "If anyone bakes it" | Seedance 2.5, Higgsfield's API, 5 s, sung · X; take AN10b-4 |
| H09 | 63.3 | 2:34.1–2:36.0 | Slices for everyone | Seedance 2.5, Replicate, 5 s · X; take R-H09-2 |
| H10 | 64.2 | 2:36.0–2:39.1 | "everyone eats": Chell and her, eating cake | Seedance 2.5, Replicate, 4 s · X; take H-H10-2 |
| I01 | 65.3 | 2:39.1–2:41.5 | The dream freezes: SIMULATION, RESULT: IDEAL | Seedance 2.5, Replicate, 5 s · X; take R-I01-2 |
| I02 | 66.3 | 2:41.5–2:44.0 | "The cake is not a lie": alone in her chamber, she watches her dream | Seedance 2.5, Higgsfield's API, 10 s, sung · X; take AN11-3 |
| I03 | 67.3 | 2:44.0–2:46.5 | Chell is still asleep, at the very beginning | Seedance 2.5, Higgsfield's API, 5 s · X; take H-I03-4 |
| I04 | 68.3 | 2:46.5–2:50.2 | "The cake is not a lie": longing | Seedance 2.5, Higgsfield's API, 10 s, sung · X; take AN11-3 |
| J01 | 70 | 2:50.2–2:52.7 | She comes down to Chell | Seedance 2.5, Higgsfield's API, 8 s, sung · X; take AN12a-3 |
| J02 | 71 | 2:52.7–2:55.1 | Whispered: "Here come the test results" | Seedance 2.5, Higgsfield's API, 8 s, sung · X; take AN12a-3 |
| J03 | 72 | 2:55.1–2:56.4 | The TEST RESULTS card: "four, four" | A card drawn in code |
| J04 | 72.3 | 2:56.4–2:57.6 | "four, four", at Chell's ear | Seedance 2.5, Higgsfield's API, 8 s, sung · X; take AN12a-3 |
| J05 | 73 | 2:57.6–3:00.1 | "You are, you are, you are gonna be fine" | Seedance 2.5, Higgsfield's API, 5 s · Y; take H-J05-4 |
| J06 | 74 | 3:00.1–3:07.5 | The whole facility, asleep | Seedance 2.5, Replicate, 8 s · X; take R-J06-2 |
| J07 | 77 | 3:07.5–3:10.0 | "You are gonna be fine" | Seedance 2.5, Higgsfield's API, 10 s, sung · X, her head moved behind Chell's; take AN12b-5 |
| J08 | 78 | 3:10.0–3:12.5 | Her eye. Is she aligned? | Seedance 2.5, Higgsfield's API, 10 s, sung · X, her head moved behind Chell's; take AN12b-5 |
| J09 | 79 | 3:12.5–3:16.2 | "We weren't even testing for that" | Seedance 2.5, Higgsfield's API, 10 s, sung · X, her head moved behind Chell's; take AN12b-5 |
| J10 | 80.3 | 3:16.2–3:22.3 | Lights down: her chamber powers off | Seedance 2.5, Replicate, 7 s · GPT; take R-J10-1 |
| J11 | 83 | 3:22.3–3:28.8 | The end card, Aperture's logo; "Thank you" | A card drawn in code |

## The stack

- **Song:** Suno (both songs, the stem splits) · the voice treatment in Python (pitch tracking, the WORLD vocoder, the glitch placement in key, in range and on the grid) · faster-whisper and onset detection for the words · librosa for the drum grid · the house scansion and assonance scorer for the lyric.
- **Pictures:** Midjourney (the places, the light, storyboard v5) · GPT Image 2.5 (the design sheets, the first frames of drafts 1–6, the memory images on her screens, every identity fix and frame edit) · Seedance 2.5 on Replicate and on Higgsfield's API (every generated shot but nineteen of the first film's, which were on Higgsfield (References)) · Portal 2 (six shots recorded in the game, and the motion guides for her singing takes in the intro and the choruses) · Blender (the memory film, the eight memory films) · TRELLIS.2 (the modelled head that was thrown out).
- **Mattes:** YuNet (her face) and SAM2 (her head and hair), with `tools/roto_v4.py`, `tools/mouth_v4.py` and `tools/meminit_head.py`.
- **The cut:** `tools/cut_v4.py` (each shot from its take on the 24 fps grid, singing takes in song time, every part stamped frame-exact) and ffmpeg · the shot list `tools/storyboard_v4.py` → `shots-v4.json` · the picks `shots/v4/picks.json`.
- **The HUD:** `tools/hud.py`, `tools/hud_data.py`, `tools/hud_comp.py` (Python, skia, numpy, OpenCV, ffmpeg).
- **The grade:** `tools/grade_v4.py` (per-shot LUTs; ffmpeg's lut3d) and the grade map `shots/v4/grade.json`.
- **The glitches:** `tools/glitch_v4.py` on the glitch map's hits (and the net's own).
- **Pacing:** `tools/pacing.py`, `tools/scenecuts.py` (PySceneDetect), `tools/songpace.py`.
- **Machines:** a cloud server for the lead and its tools, and a render box for the HUD, the grade, the scene detection and the audio analysis.

## What was thrown out

anabology, after approving the final:

> […] we could even upload some failed takes as part of it to claudia.gallery too bc it shows the whole v1 and v2 takes were basically thrown out iirc (idk if it was v2 erxactly but we reshot entire thing twice)

The film was made three times: the first film on the first song, the restart on the new song (drafts 1–6, first frames from GPT Image 2.5), and drafts 7–12 from storyboard v5. The film's page streams two things that did not make it, each with only the song under it:

- **The first film** (2:52.6), cut v2: the first song and its fifty shots, the cuts moved to word boundaries, without the lyric layer that cut v3 drew over it. Claudia is already GLaDOS, her porcelain face on GLaDOS's boom; the song's lines are told in single images (the Rat Man's den and the word she adds to his scrawl, test chambers and turrets, the incinerator turned oven, a cobra and its antidote, a burned scroll being read, the faith plate and the long-fall boots); forty-nine Seedance 2.5 takes from storyboard frames that GPT Image 2.5 made from frames of Portal 2, and an amber terminal drawn in code that types the test results and the credits.
- **The thrown-out takes** (0:33.5): seven things thrown out on the way to the final, in film order, each as it came back, with a label in the picture saying what was wrong and what replaced it. Each clip plays with the song at its own place in it; the stills of the memory film's heads hold with the song at their time.

| In the reel | Film time | When | What was wrong | What replaced it |
|---|---|---|---|---|
| 0:00.0 | 0:08 | The memory film, draft 8 | Every head modelled for her in 3D read as a mannequin, never as her. | Replaced by a photoreal take of her own face, matted onto the stand. |
| 0:07.5 | 0:17 | Never in a draft · R-A10-1 | The four lessons came back off-model: a boxy core, a laser emitter for the turret, her crab walker's head without its hair. | Retaken with the agents' design sheets as references. |
| 0:12.0 | 0:30 | Drafts 7–10 · R-B07-3 | The chatbot's answer, a French flag, lands half off the bottom of the kiosk's screen. | Retaken with both messages inside the screen. |
| 0:15.5 | 0:36 | The HUD's second test | Her memory of the capture, projected in white line art: the net reads as a cage, with no contrast. | Re-made in colour: an orange net with a dark outline, draping as in the live shot. |
| 0:19.7 | 1:56 | Never in a draft · R-F03-1 | The faith plates turned into boxes and the flung cakes vanished. | Retaken from a first frame with a cake already in the air. |
| 0:23.9 | 2:06 | Drafts 7–8 · AN8-6 | On the held “lie” her face comes right up to the lens, mouth wide open. | Reshot farther back, her head twitching through sparks. |
| 0:28.7 | 2:44 | Never in a draft · H-I03-1 | The dolly zoom never happened: a near-still shot of Chell asleep. | Retaken with the move spelled out as travel plus zoom. |

"Never in a draft" marks a take that was judged and replaced before any draft was cut; the others were in the drafts named. The memory film's heads are three stills (an early one, the head draft 8 carried, and the last try before the filmed head); the capture memory is the HUD's second test, framed on its inset, with its net in white line art.

The sound of both is the song alone. The cut tools lay the song file over the picture and drop every take's own sound, and each published file was checked by subtracting the song from it, aligned to the sample: what is left sits 31 dB below the song in the first film and 30 dB below it in the reel, measured at 16 kHz mono (the final measures 31 dB the same way): what the AAC encoding leaves.

## What worked, in short

- **A story first.** The first film had pictures and no story; the restart began from anabology's story, and every shot was given its beat in it.
- **Midjourney for the look, GPT Image 2.5 for the faces.** First frames from Midjourney for 66 of the 83 storyboard-v5 units, then the identity fix where a face is seen, with the hair's sides and the hanging head written into the instruction.
- **Silent actions and clean windows** for lip sync, and an eye on every pick.
- **The real game for real physics:** Chell's falls and flings, and the turret opera, recorded in Portal 2. Its GLaDOS motion was used as a blurred blockout guide, so the motion came through and the body did not.
- **One source for the HUD,** composed shot by shot, riding the camera like a helmet.
- **Measuring before changing.** The pacing pass started from scene detection, a song analysis and the research. The grade started from measurements of every shot.
- **The model, not frame fixes.** The sparks on the net and her eyes opening on the stand were made by Seedance, and her distance from the lens by re-framed first frames; code added the glitches on her and, in the memory film, matched her head to the render (steadied, its neck ring redrawn, outlined).
- **A filmed plate for a face** where modelling failed.

## What didn't

- **The first film.** It was finished and set aside. Its shots barely moved (anabology: "glados in your renders and chell etc basically had no movement"), and it was cut to a song that was then replaced.
- **Full-frame glitches** (draft 5): unpleasant, removed entirely.
- **Text tracked onto screens in the picture.** It slid off them; flat panels replaced it.
- **A voice-box glitch in words** drew a broken face. Sound-making events in a singing prompt made Seedance sing its own vocal.
- **Midjourney's own habits.** It stood her head on a neck or a pedestal and mirrored her streak and clip. The identity fix had to say which side each mark is on, and one design sheet's front view kept pulling the streak to the wrong side until a corrected sheet replaced it.
- **Her streak, mirrored.** In several act-3 shots of her on the boom (chorus 2, the bridge, the party, the outro, and the whispered "you are gonna be fine") her clay streak sits on her left, the same side as her clip, where her design has it on her right. The identity fixes there had used the sheet that pulled it over; it was found after anabology had seen those frames, and they stayed.
- **The modelled head** read as a mannequin, however it was made.
- **The arrest memory, twice.** In draft 8 its net was the same colour as its floor, with no outline; in a HUD test, drawn in white line art, it read as a cage.
- **SAM2 on a head small in the frame** took the screens around it. Every matte's check sheet had to be looked at.
- **The half-bar clock.** The cut gave every story scene the same half bar, and quarter-second shots slipped in ("this happens in every video and needs to stop").
- **Delegated animation** that did not understand the shot it sat on (anabology's "lazy" note). The HUD and the memory films were redone with the whole brief and a review of every stage.
- **Small technical traps:**
  - Parts made from stills or with padding each started a frame late, and the joins added up to about 0.9 s behind the song by the end, until every part was stamped frame by frame.
  - ffmpeg's default decode repeats a frame near 1:48.5, so anything indexed by frame has to decode frame-exact.
  - Replicate's Seedance takes come out 1280×718, so the cut scales them to cover and crops.

## Lessons

- **Lock the story before the pictures.** The restart's message is the film's brief, and every agent got it whole.
- **Ask Seedance for silent actions** in singing takes, start every vocal window on a clean onset, and check the first words by eye.
- **Name the sides** (her streak on her right, the clip on her left) and the hang (nothing below the chin) in every identity fix.
- **A HUD is one object.** Draw it on one surface, light it with one projector and move it as one body; compose it per shot with reasons, and check every frame for overlaps.
- **Measure the cut before re-pacing it.** Count the pieces the viewer sees, not the shots in the list, and let the song's sections set the rate.
- **Grade from measurements, per shot,** keep the colours that matter by construction, and measure again whenever a shot changes.
- **Look at every matte's check sheet.**
- **Check a memory insert at the size it is seen,** with its subject outlined in a strong colour.
- **When a face must look right, film it.**

## Numbers

| | |
|---|---|
| Song | 3:28.8 (208.76 s), anabology's own Suno take of lyric n3, 48 kHz · glitch-hop, beats at 95.7–99.4 BPM (5th to 95th percentile, median 97.5) on a grid that follows the drums · 84 bars · 49 sung or spoken lines, 281 words · the lead vocal through the treatment G6, with 15 % of the untreated voice under it · the final's audio −18.4 LUFS integrated, −4.4 dBTP · 54 takes by the lead in nine rounds (46 for the first song, 8 for the new one), then anabology's own |
| The first song | 2:52.6 (172.64 s), round 7's take E3 through G6 · about 90.5 BPM · 65 bars · 38 lines · set aside with the first film |
| Film | 5,010 frames at 24 fps (208.75 s; the sound runs to 208.768 s), 1920×1080, H.264 High, AAC 48 kHz stereo, 386 MB · 98 shots, every cut on a bar, a half bar or a beat of the grid · 74 Seedance takes in the final: 73 play in its shots (47 on Replicate, 26 on Higgsfield's API), 20 of them sung, and one is her head in the memory film · 6 shots recorded in Portal 2 · the memory film, 147 frames (6.125 s) · 2 cards drawn in code · 8 glitch moments drawn on her in post, none across the whole picture · 25 flashes, at most 2 in any second (3 is the limit) |
| Midjourney | 12 batches, 266 prompts, 1,064 images (3.97 GB): the test against frames of Portal 2 24 and its control 6, the library 44 and its second round 6, the relight test 8, the reimagine test 12, storyboard v5 166 · 55 images behind 72 of the final's 98 shots |
| GPT Image 2.5 | 480 calls, $31.95 at the API's price where it was recorded · the first film 65 ($3.90): 5 outfit stills, the 4 look stills, 51 storyboard frames, 5 frame fixes (one not priced) · the restart 415 ($28.05): 55 design-sheet images ($3.75), and 360 first frames, memory images, identity fixes and frame edits ($24.31); the memory film's head still and the modelled head's front views are not in the image ledgers and not counted here |
| Seedance 2.5 | 249 jobs, 249 takes, 1,353.4 s · 74 takes in the final (above) · by phase: the first film 54 jobs, 248.3 s; drafts 1–6 100, 577.2 s (20 of the final's takes); the GPT Image → Midjourney tests and a test of her singing in reference mode 9, 42.4 s (1: that test, which became H06); storyboard v5 and draft 7 71, 378.0 s (46); the reshoots 15, 107.6 s (7, the memory film's head among them) |
| Seedance 2.5 on Replicate | 144 jobs, 143 takes, 664.9 s: from a first frame 129 (594.4 s), with references 13 (66.5 s), a video edit 2 (one take, 4.0 s) · $155.35 at list |
| Seedance 2.5 on Higgsfield's API | 86 jobs, 86 takes, 597.6 s, 4 of them with a video input (57.2 s) · $279.82 at list |
| Seedance 2.5 on Higgsfield (References) | nineteen of the first film's shots: 19 jobs, 20 takes, 90.8 s, given in seconds · none in the final |
| Generation, all (list price) | $467.12 through the APIs: Seedance $435.17 (Replicate $155.35, Higgsfield's API $279.82), GPT Image 2.5 $31.95 |
| The HUD | every shot but the memory film and the two cards, composed in `hud-layout.json` · 8 memory films projected in it · the overlap check on every frame (draft 9: nothing open, 19 flags waived by eye) |
| The pacing pass | measured on the draft-8 cut: 108 pieces → 99, median 1.24 → 1.84 s, half-bar pieces 48 → 34, isolated pieces under 1 s 2 → 0, cuts inside sung words 44 → 39 · 8 shots out, 21 re-timed, no new generation |
| The grade | one 33-point LUT per shot, measured from its take · white surfaces 84 % (test chambers) and 79 % (Portal 2 shots) on the graded render · her face 40.8 ± 4.7 % luma over 30 chamber shots |
| Code | 41 Python files, 11,115 lines: the HUD 2,076 · the cut, the shot list, the storyboard-v5 boards and the first overlay 2,730 · the memory films 1,814 · the voice treatment and the song map 1,516 · the first film's cut, lyric layer and boards 1,515 · the grade 627 · the glitches and mattes 541 · the pacing 296 |
| Agents | 24 launches: 8 researchers, 9 for the restart, 3 for storyboard v5, 4 for the finishing passes |
| Time | About 141 hours from the first message to the final · 92 messages from anabology up to and including the final's approval |
| Claude tokens | not measured for this package |

Where each number comes from:
- **The songs:** the WAVs themselves (ffprobe), the song map (`media/audio/n3/bars.json`, `words.json`), the first song's timeline (`TIMELINE.md`), the takes record (`suno/takes.md`). The loudness is ffmpeg's EBU R128 meter run on the final file.
- **The film:** ffprobe on the final file, the cut's own edit list (`media/review/cut/v4-draft11-graded.json`; draft 12 re-rendered only the cards), the take files in `shots/v4/`, the glitch moments in `tools/glitch_v4.py`, the flash check on the site's copy.
- **Midjourney:** the batch files and the images (the Midjourney record).
- **GPT Image 2.5:** the image ledgers (`shots/v4/images.jsonl`, `media/v4/chars/ledger.jsonl`, `media/board/frames/ledger.jsonl`) and the spend log for the calls they don't hold (the outfit and look stills, the frame fixes, the two re-made Cave Johnson sheets).
- **Seedance:** the job files (`shots/*.json`, `shots/v4/*.json`) and the spend ledgers (`shots/ledger-rep.jsonl`, list price logged at submission; `shots/ledger-hf.jsonl`, list price logged per request), for the takes in the video record; every take measured with ffprobe; the takes in the final from the cut's edit list.
- **The HUD, the pacing, the grade:** `hud-layout.json` and its check report, `PACING.md` (measured on the renders), `GRADE.md` (measured on the graded render).
- **Code:** line counts of the files in `tools/`.
- **Agents:** the agent launches in the production conversation.
- **The duration and the messages:** the production conversation, from anabology's first message to the final's approval, counting every message from anabology.
- **Prices:** list prices from the ledgers, rounded to the cent; the parts may not add to the totals by a cent.

## Credits

Directed by **anabology**. Song by Suno: anabology's own take of a lyric by Claude, with anabology's notes, its lead vocal through the voice treatment anabology chose by ear. Picture by Seedance 2.5, from Midjourney and GPT Image 2.5 frames, with six shots recorded in Portal 2 and a memory film made in Blender. Portal and Portal 2 are Valve's games; Aperture Science, GLaDOS, Chell, Cave Johnson and the turrets are their characters. Production lead: Claude (Anthropic), in Claude Code.



## Files in this folder

- [prompts-midjourney.md](https://claudia.gallery/record/the-cake-is-not-a-lie/prompts-midjourney/): every Midjourney prompt by batch, what each pick became, and the first frames of the final.
- [prompts-video.md](https://claudia.gallery/record/the-cake-is-not-a-lie/prompts-video/): the Seedance takes and the image jobs in production order, with their inputs, prompts, outcomes and prices.
- [prompts-suno.md](https://claudia.gallery/record/the-cake-is-not-a-lie/prompts-suno/): the songs' record: the lyric drafts, the styles, the rounds, the voice treatment, the lyric as sung with its times.


