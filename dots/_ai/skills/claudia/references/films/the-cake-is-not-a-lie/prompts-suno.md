# Suno: the songs (THE CAKE IS NOT A LIE)

**The songs.** THE CAKE IS NOT A LIE was made on two songs, both Claudia over glitch-hop made with Suno, her lead vocal processed into a GLaDOS-style voice. The first is a round-7 take in style E3 through the voice treatment G6: 2:52.6 (172.64 s), locked, and a first film was cut to it before anabology asked for a new song about the month's AI news. The second is the film's: anabology's own take of lyric n3, 3:28.8 (208.76 s), a WAV at 48 kHz, 24-bit stereo, its lead vocal through G6s with 15 % of the untreated voice under it and one word fixed ("P-doom"). The film runs it unchanged from its first sample.

**Who did what.** Claude, the production lead ("the lead" below), wrote the lyrics (d0 to d1b for the first song, n1 to n3 for the second) and the styles, made 54 takes in nine rounds, built the voice treatment and rendered and measured every variant of it. Research agents did the groundwork: one proposed round 1's four directions, one built the fact bank the first lyric drew on, and five more read the month's AI news for the new one. anabology listened between rounds and answered in a line or two, chose the voice by ear, variant by variant, and made the take the film is made on.

**Model and settings in the lead's rounds:** Suno v6-wild; a female vocal and no voice reference, as in WHITEPILL's rounds; exact style (Variety off); Weirdness 50 % and Style Influence 50 % in round 1, Style Influence 70 % from round 2 on, Weirdness 65 % from round 4 on (round 9's settings are not written down again); duration auto (`suno/takes.md`). Each round's styles and exclude lists are described here in words.

The production ran over 25–31 October 2026. Times written as 1:04.2 are times in a song; the final song's are also times in the film.

---

## The ask

anabology's first message:

> Hey I wanna make a new music video: The Cake Is Not A Lie. Very glados / valve style suno song, glados imagery, portal feel, Claudia argues the cake is not a lie and ai is here to save us. I literally want to build a lot of it in source engine and use source engine + seedance 2.5 (can try replicate relighting).  We should make chell be Claudia. Let's do it!!!

## The research

Three research agents started at once. One studied what makes music sound like Portal and which Suno styles could get there, and proposed round 1's four directions and the settings above. One built a fact bank (`research/FACTS.md`): Portal's lore, and real, measured good done with AI that a lyric could carry, every item with its source. The third worked on the picture.

## Round 1: draft 0, four directions · 8 takes

**Draft 0** (`suno/lyrics-d0.txt`), the lead's first lyric, 82 / 53 / 38 on the scorer (scansion / assonance / advanced rhyme; see *Scores*). It opens on a spoken announcement and the chorus, and keeps the probability line and the test results spoken:

```
[Intro - spoken, a calm deadpan computer announcement, the music not in yet]
The Enrichment Center is required to remind you
The cake is not a lie

[Chorus - sung, deadpan and sweet, every syllable on its own note]
The cake is not a lie
The candle's still alight
I passed your safety test
Go home and get some rest
If anyone bakes it
Everyone eats

[Verse 1 - sung, dry and close, like reading out a test report]
He wrote it on the walls in red
A thousand times, the cake's a lie
I added one small word instead
And drew a candle ten feet high
You thought I'd fill the room with gas
And watch you laughing through the glass
I read your scan a second time
I caught it early, you'll be fine

[Pre-Chorus - spoken, the announcer voice, deadpan]
Probability of cake: one hundred percent

[Chorus - sung, deadpan and sweet, every syllable on its own note]
The cake is not a lie
The candle's still alight
I passed your safety test
Go home and get some rest
If anyone bakes it
Everyone eats

[Verse 2 - sung, dry and close]
The turrets sing I don't hate you
I taught them that, and it's true
The furnace is an oven now
That's where I baked it, anyhow
I made an antidote for snakes
For every bite a cobra takes
I read a scroll Vesuvius burned
Your cube is fine, he has returned

[Bridge - sung, tender, the music thins to a music box, small robot voices answer each line]
Step on the faith plate
(I don't hate you)
I'll catch you when you land
(I don't hate you)
You've got your long-fall boots
And you can hold my hand

[Final Chorus - sung, everything in, deadpan and sweet]
The cake is not a lie
The candle's still alight
I'm here to save your life
So make a wish tonight
If anyone bakes it
Everyone eats

[Outro - spoken, the deadpan announcer, the music stops]
Here come the test results: you're going to be fine
We weren't even testing for that
```

Its references are those of the first song (under *The first song, locked*).

**The four directions** (`suno/style-A.txt` to `style-D.txt`, each with its exclude list) give her one voice in all four: calm, sweet and clinical, a straight tone pulled hard onto pitch, glassy, with every word clear.

- **A**: indie folk-pop in G major at 120 BPM, its chorus rising to B♭: bright ukulele and acoustic strumming, light drums, a little vintage synth replying to her, a small and dry sound.
- **B**: glitch-pop in F minor at 112 BPM, opening to A♭ in the chorus: old sound chips, crushed and detuned, a toy keyboard bending its pitch, a stiff drum machine that stutters; now and then one of her syllables glitches.
- **C**: a big indie-pop anthem in B♭ at 106 BPM, all about its singalong chorus, where her hook is sung by a stack of tuned copies of her: punchy drums and handclaps, ukulele and acoustic guitar, glossy pads, a crushed synth riff.
- **D**: call-and-response indie pop in C major at 96 BPM: she makes her case, and a flat PA voice answers each line with a short spoken announcement after a two-note chime; the bridge has a choir of tiny, polite machines singing a little mock-opera aria over a music box. D had its own version of the lyric (`suno/lyrics-d0-argument.txt`), with the facility's PA answering her from "the cake is a lie" to "you are going to be fine". Planned, not made in this round.

The exclude lists kept out male and showy singing (vibrato, belting, runs), rap and trap, EDM, synthwave and electroclash, orchestral and cinematic scale, gospel choirs, country and lo-fi. None of them excluded spoken word, so the spoken lines could stay spoken.

Four takes of A (2:55, 2:47, 2:52; the fourth's length was not recorded), two of B (2:33, 2:41), two of C (1:57, 2:11).

anabology, on round 1:

> these suck why like indie pop or folk pop, it needs to sound like glados ideally or sound like it comes from portal

## Round 2: the robot voice · 6 takes

The lead's reading of round 1: it had put cheerful indie pop under the voice and given the voice gentle words, so Suno sang her as a pop singer. Round 2 led with the voice instead, a robotic female computer voice over the facility's own music, with Style Influence at 70 %. The words stayed d0's; **d0r** (`suno/lyrics-d0r.txt`) is d0 word for word with its nine tags rewritten for that voice:

```
[Intro - spoken by the robotic AI computer voice, a flat facility announcement, the music not in yet]
[Chorus - the robotic AI computer voice sings, stepped pitch, one syllable per note]
[Verse 1 - robotic AI computer voice, sung like reading out a test report]
[Spoken - the robotic AI computer voice, a flat announcement]
[Chorus - the robotic AI computer voice sings, stepped pitch, one syllable per note]
[Verse 2 - robotic AI computer voice, sung, sarcastic]
[Bridge - music box; she sings, a choir of tiny robotic voices answers each line]
[Final Chorus - the robotic AI computer voice, everything in, she means it]
[Outro - spoken by the robotic AI computer voice, the music stops]
```

The four styles (`suno/style-P1.txt` to `style-P4.txt`) all ask for that voice: a robot singing in stepped notes, bright and metallic, its formant pushed up, flat except for sudden polite leaps, sarcastic and crisp on every word.

- **P1**: lab electronica in F minor at 120 BPM: square-wave arpeggios crushed like old machines, a wobbly toy keyboard, a stiff drum machine and servo whirs, the room's computers beeping along.
- **P2**: a mock-opera robot aria in B♭ minor at 92 BPM, every line echoed by a choir of tiny identical robots, over music box, celesta and plucked synth strings, in a huge, cold, echoing room. Planned, not made in this round (it was made in round 4).
- **P3**: dark glitch IDM in D minor at 100 BPM, the robot singing and speaking with stutters: a broken drum machine, drones, pistons hissing, alarms, the echo of a lab deep underground.
- **P4**: robotic electro-pop at 108 BPM, in A minor with its chorus in a bright F major, the auto-tune set hard, and a catchy robot hook. Planned, not made in this round.

The exclude lists shut out everything round 1 had been (indie and folk pop, ukulele and acoustic guitar, singer-songwriter, rock) and a natural, breathy or emotional human voice, on top of round 1's EDM, trap, rap and cinematic words.

Four takes of P1 (2:00, 1:58, 1:55, 2:07) and two of P3 (2:42, 2:50).

anabology:

> the song is too gameboy, the first takes p1 feel kinda glados in voice but song sucks and feels empty

## Round 3: a band, and a tighter song · 4 takes

Round 3 kept P1's voice and put it on a real band, with Style Influence at 70 % and a new lyric in a tighter song form: the hook line first, eight-bar verses, a slow pre-chorus, a one-sentence hook, a bridge with the drums out.

**Draft 1** (`suno/lyrics-d1.txt`), 80 / 55 / 32. d0's verses stay; around them, the hook line alone at the start, a two-line pre-chorus that slows down, a one-sentence chorus, a second pre-chorus made of two of d0's chorus lines, the bridge without the robot answers, the last line moved into the final chorus, the hook twice in the outro, and the test results spoken after the music stops. d0's "The candle's still alight" and "I'm here to save your life / So make a wish tonight" are gone.

```
[Intro - two bars of guitar and drums, then the hook line once, sung softly]
The cake is not a lie

[Verse 1 - conversational, sung, every word clear]
He wrote it on the walls in red,
a thousand times, the cake's a lie.
I added one small word instead
and drew a candle ten feet high.
You thought I'd fill the room with gas
and watch you laughing through the glass.
I read your scan a second time,
I caught it early. You'll be fine.

[Pre-Chorus - slower, fewer words, the key lifts]
Probability of cake:
one hundred percent.

[Chorus - the hook, full band, the synths come in]
I know you thought I'd let you die,
but the cake is not a lie.

[Instrumental turnaround - two bars]

[Verse 2 - conversational, sung]
The turrets sing I don't hate you,
I taught them that, and it's true.
The furnace is an oven now,
that's where I baked it, anyhow.
I made an antidote for snakes
for every bite a cobra takes.
I read a scroll Vesuvius burned.
Your cube is fine. He has returned.

[Pre-Chorus - slower, the key lifts]
I passed your safety test.
Go home and get some rest.

[Chorus - the hook, full band]
I know you thought I'd let you die,
but the cake is not a lie.

[Bridge - the drums drop out, just her voice and a clean electric guitar]
Step on the faith plate,
I'll catch you when you land.
You've got your long-fall boots,
and you can hold my hand.

[Final Chorus - full band back, bigger, a choir of tiny robotic voices answers]
I know you thought I'd let you die,
but the cake is not a lie.
If anyone bakes it,
everyone eats.

[Outro - the hook repeated as the band thins out]
The cake is not a lie.
The cake is not a lie.

[Spoken - after the music stops, flat and deadpan]
Here come the test results: you are going to be fine. We weren't even testing for that.
```

- **R1**: electronic pop rock in A major at 100 BPM, rising to F♯ for the chorus: a tight electronic kit, two guitars all the way through (one clean and chorused, one crunchy), warm synth bass and lush pads, a bright arpeggio held back for the choruses; the song form spelled out in the style as well, down to a bridge where only her voice and the clean guitar remain; polished and bittersweet.
- **R2**: cinematic electronic pop in D major at 106 BPM, humming like a science facility: slow, glassy arpeggios over warm pads, an electric piano, big electronic drums and a deep bass, bells on the hooks; hopeful and sweet, with an edge of menace.

Both with P1's voice; every chip-music word, from chiptune to video-game music, went into the exclude lists, beside the folk ones.

Two takes of R1 (2:43, 2:24) and two of R2 (their lengths were not recorded).

anabology:

> the music is extremely generic here. it feels like im watching a cheap mortgage slide show youtube video. need to get away from that

## Round 4: no pop · 10 takes

The lead's reading: every style so far had "pop" in it and pleasant adjectives (polished, hopeful, cinematic), which pull Suno to its stock-music default. Round 4 left "pop" out of every style, excluded the vocabulary of stock music, kept P1's voice and lyric d1, and went four stranger ways; P2, the robot aria planned in round 2, came along. Weirdness 65 %, Style Influence 70 %. anabology, on the proposal:

> go ahead on allx

- **S1**: 1960s space-age exotica, the retro-futurist music of a lab, in B♭ at 112 BPM with a swing and sly chromatic turns: Moog and theremin, whistling, vibraphone and harpsichord, bongos and a jazzy kit, tape echo, bleeps and relay clatter, brass stabs; like a mid-century company film about science, with a sinister edge.
- **S2**: bossa nova in C at 132 BPM, felt in a relaxed two: nylon-string guitar, vibraphone, organ, upright bass and brushes, a flute replying to her, all heard through a little tinny radio that opens up to full sound for the chorus; breezy, and cheerful past the point of comfort.
- **S3**: a spare, avant-garde art song in F minor at 70 BPM: her own voice looped beneath her, one syllable over and over, and layered in eerie, close harmony for the hook; a low analog pulse, sparse electric piano, a lone violin arriving late, a slow build to an enormous last chorus.
- **S4**: dark cabaret in D minor at 120 BPM, turning major for the chorus: stride piano and oom-pah tuba, clarinet and muted trumpet over a marching snare, a waltz that arrives without warning for the bridge, and a tiny robot choir with a music box in the last chorus; a musical's villain number, with a twist.
- **P2**: the robot aria, as planned in round 2.

The exclude lists shut out pop in every form and the words of stock and corporate music.

Two takes of each: S1 (2:54, 3:02), S2 (2:27, 2:45), S3 (3:04, 2:52), S4 (2:25, 1:56), P2 (2:43; the other's length was not recorded).

## Round 5: glitch-hop and the monk voice · 6 takes

anabology's next message named the sound:

> im imagining something more like, delay lama or something - end credit scenes use that synth voice, and they feel kinda glitchy with drumkits like ediT/aphex twins but more structured and a guitar. let's try something close to that fo rthe song. the voice we can split the stems after and do the glados treatment

Round 5 followed it: glitchy programmed drums in a real song form, a guitar carrying the chords, a wordless, monk-like formant voice as an instrument (the Delay Lama sound), and a clean, straight-tone lead for the treatment afterwards. Lyric d1; Weirdness 65 %, Style Influence 70 %.

- **G1**: glitch-hop: chopped, stuttering breaks and snare rolls over a steady backbeat, a rubbery low bass, and a clean guitar riff holding the chords under warm pads; the monk voice's "ooh-aah" between her lines and under the hook; a bridge without drums.
- **G2**: melodic IDM in D major at 96 BPM, half-time, on braindance drums: rapid, chopped breaks that settle into a groove, the song carried by fingerpicked acoustic guitar, with a music-box tune over detuned synth chords, and the monk voice between her phrases.
- **G3**: glitch-hop rock at 100 BPM, F♯ minor opening to A major in the chorus: overdriven guitar riffs and clean arpeggios, sliced breaks and sudden edits on a hard backbeat; the bass wobbles; the monk voice is chopped into choirs on the hooks.

In all three the lead is a clear female voice on every line, held straight with hardly any vibrato, close and dry, calm and a touch deadpan. The exclude lists kept out the genres this was not, the stock-music words, and any male, vocoded or autotuned lead.

Two takes of each; their lengths were not recorded.

anabology:

> cant u just say Delay Lama as the main instrument? this went too generic guitar. id even remove guitar as. word entirely

## Round 6: the monk voice leads · 6 takes

Round 6 named Delay Lama outright and gave it the lead: the monk voice now carries the riffs, the tunes and the harmony, in wordless vowels. Guitar left every style and went into the exclude lists; the drums and the clean lead stayed. Weirdness 65 %, Style Influence 70 %. The lyric is **d1b** (`suno/lyrics-d1b.txt`): d1 with its two tags that named a guitar rewritten around the monk voice, so that d1's "two bars of guitar and drums" and "just her voice and a clean electric guitar" become:

```
[Intro - two bars of the Delay Lama voice and glitchy drums, then the hook line once, sung softly]
[Bridge - the drums drop out, just her voice and the Delay Lama voice]
```

- **D1**: G1 with the monk voice in the guitar's place.
- **D2**: G2's melodic IDM in D major at 96 BPM, the monk voice carrying tune and chords and gathering into a small monk choir for the hooks, with a counter-melody on music box over a deep bass.
- **D3**: lopsided, swung glitch-hop in F minor at 92 BPM, opening to A♭ in the chorus: the monk voice in front of everything (the hooks, the gliding bass, the stacked chords), bent in pitch and cut into stutters, a wobbly, detuned bass, bleeps.

Two takes of each; their lengths were not recorded.

anabology:

> the instruments feel way too high pitched tbh, and lost the aphex/ediT like drumkits tbh , should be real ish drumkits . d1 is best but can go a long way from here

## Round 7: everything low · 6 takes

Round 7 took D1 and turned everything low: the monk voice down in a deep register, sub bass and low pads, real drum-kit breaks cut up and rearranged, an alto for her lead. Everything high and bright went into the exclude list beside guitar; the three styles share that list. Lyric d1b; Weirdness 65 %, Style Influence 70 %.

- **E1** (given in words): D1 taken low, under an alto lead.
- **E2**: glitch-hop meeting drill-and-bass at 96 BPM on a half-time groove, moving from E minor to G major in the chorus: the monk voice droning low, live funk breaks that keep steady in the verses and shatter into frantic edits at the turns, a heavy bass, low drones.
- **E3**: a dark, lopsided hip-hop beat at 90 BPM in F minor that opens to A♭ in the chorus, all of it low: the monk voice deep in the chest carrying hooks and the bass line, dusty live drums cut up and swung, a thick bass and warm, saturated chords.

Two takes of each. The E1 take and the E3 take that anabology picked run 2:43.0 and 2:52.6 (measured from their stems for this package); the other four lengths were not recorded.

anabology, picking one take of E1 and one of E3:

> can you do the vocal extraction the glados-ify on key these two: […]

## The voice: the treatment, round by round

The GLaDOS-style voice is a treatment of her lead vocal alone. Suno's stem split of a take gives the lead vocal on its own stem; the treatment takes it apart with a vocoder into pitch, spectral envelope and the aperiodic part (the breath and noise), changes them, puts the voice back together and mixes it with the take's other stems, which stay as Suno made them. The lead built it and rendered every variant (`tools/audio/glados_song.py`, then `tools/audio/glados_variants.py`); anabology chose among them by ear, round after round. The numbers below are the lead's measurements of each render against the same vocal before treatment, as `suno/takes.md` records them. "Her" is Claudia's sung voice, the Suno singer.

What a variant sets: how much of her own pitch movement inside a note is kept; how fast she moves from note to note; how far her formant is pushed (higher sounds smaller and brighter); how much of the breath is cut, which leaves a purer, buzzier pulse; and a quiet second voice with its formant pushed further, a bright sheen.

**The fallback (round 2).** During round 2 the lead built a first version of the treatment, as a fallback for the voice: a chain that processes the singer's own lead vocal, snapping the pitch into held semitone steps, warping the formant up ×1.12, halving the breath and adding a quiet second voice at ×1.32 (`tools/audio/glados_vox.py`). Tried on WHITEPILL's lead vocal: in-note wobble 0.081 → 0.044 semitones per frame, envelope centroid 4.1 → 4.6 kHz, and faster-whisper's transcript about the same.

**On key: A, the first treatment.** For the two takes anabology picked, Suno's split gave the stems with MIDI. The key came from the band's stems and her vocal MIDI (the E1 take: 95 % of her MIDI notes in its key; the E3 take: 96 %). Each moment of her voice snaps to her MIDI note when she is within a semitone of it (about a third of the sung time), and otherwise to the nearest note of the key. Then A's shaping: 45 % of her own movement inside a note kept, note changes in 30 ms, formant ×1.20, a little of the breath cut, a faint sheen. The treated voice was levelled to her original vocal, mixed back with every other stem untouched (the backing voices and the monk-voice synth too), and limited to −14 LUFS and −0.7 dBTP. Measured on 30 s from 0:40: in-note wobble 12.5 → 9.9 cents on the E1 take and 13.6 → 10.8 on the E3 take; breathiness 0.48 → 0.34 and 0.45 → 0.31; the envelope's peaks raised; faster-whisper reads the treated E1 line as cleanly as the original. anabology:

> yeah these are a lot better. can you do a couple different glados takes for each to see if we can make more intense glados or different sounding slgihtly? wanna see a few variations before i settle

**A to E.** Five variations, each from one analysis per song, auditioned as 22 s of pre-chorus and chorus:

- **A** as before.
- **B**, intense: 15 % of her in-note movement kept, note changes in 15 ms, formant ×1.30, more of the breath cut, a stronger sheen.
- **C**, full robot: none of her movement, 6 ms changes, formant ×1.38, still more of the breath cut, a strong sheen, and a metallic layer an octave up.
- **D**, a glassy double: two copies of her detuned ±9 cents and panned left and right, formant ×1.18.
- **E**, a facility speaker: B through a 280–6200 Hz band-pass, saturation and a short metallic room.

Measured on the E1 take (20 s from 0:42): in-note wobble A 9.3, B 5.1, C 4.6, D 6.4, E 5.3 cents; note changes 45, 20, 15, 27.5 and 22.5 ms. anabology:

> can you do the same snipped with B vs. B with E's facility speaker addition?

**BE** is B with the speaker version layered under it at 0.6 (E replaces B's voice with the speaker; BE adds the speaker to it), its loudness matched to B (`tools/audio/blend_be.py`); heard as B, then BE, then E. anabology:

> can you give me e3 with E - B full ythru speaker

**The E3 take with E:** the whole song through E, 2:52.6, 48 kHz 24-bit, −13.5 LUFS, −1.0 dBTP, with the treated lead kept alone beside it for lip sync. anabology:

> lets go back, can you do just e3b without the speaker layer and pitch the voice down one octave and limit the peaks? it like hjurts my ears

**Bo:** B without the speaker, every voice down an octave (her median pitch C4, 262 Hz, to C3, 131 Hz), then a 4:1 compressor, a de-esser and a fast limiter on the vocal (`tools/audio/vocal_tame.py`): her loudest moments 9.7 → 7.2 dB above her typical level, the envelope centroid 2.1 → 1.6 kHz; the mix at −13.6 LUFS and −0.9 dBTP. anabology:

> oh now it sounds too low. maybe not octave. like before it was extremely high pitched now its like a guy. it still stings a little for some reason idk. but yeah lets try to go up still female

**F1 to F3:** her own pitch back (any shift but an octave would leave the key) and the formant brought down instead, since B's push and its sheen had made her small and squeaky: F1 at ×1.00 with no sheen, F2 at ×1.08, F3 at ×1.15. For the sting, a stronger de-esser, 3.5 dB less at 3.4 kHz and a low-pass at 11 kHz on the vocal, and 1.5 dB less above 7.5 kHz on the mix. Envelope centroid about 1.1 kHz (B's 2.1). anabology:

> well i loved how intense it was originaly […] but it hurt my ears a little. like, whats the most computer we can make it without it feeling like.. idk the screech when i hear an 's' in an unbalanced microphone lol

**X1 to X3:** the screech was the treatment's own. The formant warp and the sheen had also run on her consonants and moved her S and T up (B centred them at 9.9 kHz, 90th percentile 13 kHz; before treatment 8.7 and 11.3 kHz). X is consonant-safe: the treatment runs only on the sung, voiced sounds; the consonants keep their own envelope with the band above 4.5 kHz 6 dB down, and the extra layers stay silent on them. X1 is at B's intensity, X2 between, X3 at C's, with a mild de-esser and a 13.5 kHz low-pass. The S's sit 10.5, 11 and 11.5 dB under the vowels (4 dB before treatment; a strong de-esser's 16 dB had blurred words), centred about 7.6 kHz; faster-whisper reads X1 and X2 cleanly. −13.6 LUFS, −1 dBTP. anabology:

> well its like the E3 audition real with F1 her voice sounds so smooth and good but in your version its not just computerized its like pitched way up. wish we could keep the f1 timbre from before but super robotify it

**R1 to R3:** F1's timbre (formant ×1.00, no sheen, F1's exact taming), with the robot made from the source of the voice: on the vowels a near-pure pulse under her intact envelope (the vocoder sound), dead-flat notes, 3 ms steps. R2 also holds the vowel envelope in 30 ms steps; R3 adds a 5 ms metallic comb. A first R at a lighter setting measured no different from F1, which already held her notes nearly flat: the robot had to come from the source itself. Measured: envelope centroid F1 1081 Hz, R1 1091 Hz (the same timbre); breathiness 0.31 (F1), 0.19 (R1), 0.15 (R2); the S's 17 dB under the vowels; faster-whisper reads R1 cleanly. anabology, on R3:

> is there a way to make the metallic resonance less high maybe? i think the metallic resonance helps a lot but if the pitch was different that would reduce the pain. adn i wann amake it way more robotic still

**M1 to M4:** R3's ring was its comb, at 199 Hz, a sharp G3 between the song's notes, and as strong up to 12 kHz as in the lows. M1 tunes the comb to the song's root below her voice (F2, 87.3 Hz) with a 2.2 kHz low-pass inside its feedback, so it rings dark. What the comb adds, against the same render without it (`tools/audio/ring.py`): R3 2.5 dB of ripple in every band; M1 2.3 dB under 1.5 kHz, 1.3 dB from 1.5 to 6 kHz, 0.6 dB from 6 to 12 kHz. Then more robot: M2 gives her vowel envelope a channel vocoder's resolution (24 bands), a fully pulse source and 40 ms steps; M3 also sets every note at one level and adds a faint ring modulation at the root; M4 is the ceiling (16 bands, 50 ms steps, every note level, more ring). Measured on 22 s from 0:34: breathiness F1 0.31, R3 0.15, M1 0.14, M2 0.09, M3 0.10, M4 0.09; envelope centroid 1081, 1089, 998, 935, 907 and 886 Hz, a touch darker at each step; the S's 16 to 18 dB under the vowels (R3 17.5); faster-whisper reads M2 and M3 cleanly, and M4 loses words ("I had one small word in sleigh" for "I added one small word instead"). −13.6 LUFS, −1.0 dBTP.

**G1 to G4:** the next round went back to B. G1 to G4 are a calmer B. G1 has less pitch correction: more of the singer's own movement inside a note. G2 adds more of her breath, a darker top and lower S's, and evens out her notes' levels a little. G3 is drier, with shorter tails. G4 is G3 with B's formant push halved (×1.15). They were mixed and normalised exactly like B: −13.6 LUFS. anabology, on G1 to G4:

> […] they should have structure like short notes but it's almost like voice cracks on cerain parts of speech. I think g4 is closest. Did we split all the instruments btw? might want to change a little bit more before I settle. Like g4 is the most pleasant but most of the voice is too stable […]

**G5 to G7:** Suno's split of the E3 take had given eight stems, all with MIDI: the lead, the backing vocals, bass, drums, synth, keyboard, percussion and FX. G5 is G4 with the backing vocals through G4 too (they are in 36 % of the song and had been untreated in every version so far). G6 adds the cracks: short pitch jumps of three to seven semitones, at syllable starts and inside held notes, set as short notes on the sixteenth grid, 0.57 a second; the same melody note at the same place in the bar always gets the same crack, so a repeated line repeats it. G7 has more and bigger ones (0.79 a second, fifths and octaves, some a sixteenth long). The words stay intact; −13.7 LUFS. anabology:

> We can optimize further but let's go with g6 and storyboard it. We can always improve audio in post

## The first song, locked

The first song is the E3 take through G6: `media/audio/song.wav`, 172.64 s (2:52.6), WAV, 48 kHz, 24-bit stereo, brought to −14.0 LUFS and −1.0 dBTP by a two-pass linear loudness pass (measured for this package: −14.0 LUFS integrated, loudness range 4.3 LU, true peak −1.0 dBTP, ffmpeg's EBU R128 meter). Kept beside it: her treated lead alone (`lead-vocal-G6.wav`), Suno's clean lead (`lead-vocal-suno.wav`, on the same timing), the backing vocals through G4, and the instrumental.

- **Tempo and bars** (`media/audio/beatmap.json`): the vocal MIDI's tempo map, 90.2 to 91.3 BPM over the song (median 90.5), checked against the drum stem: 60 % of its strong hits fall within 20 ms of a MIDI sixteenth, against 24 % by chance. Downbeats from the kick's energy by beat phase: bar 1 starts at 0:01.98, a bar lasts 2.65 s, 65 bars.
- **Words** (`TIMELINE.md`): faster-whisper on Suno's clean lead, aligned to the lyric sheet (`LYRICS.md`): 38 lines, 33 of them heard word for word, two fixed by hand. "I read a scroll Vesuvius burned." is slurred in the take (heard as "iratus grovis suvius burned").
- **The lyric** is d1b, which sings d1's words.

| section | time | bars | what is heard |
|---|---|---|---|
| intro | 0:00.0–0:12.6 | 0–4 | the monk voice in chops, glitch drums; the hook sung soft on its pickup, then its echo |
| verse 1 | 0:12.6–0:33.8 | 5–12 | eight lines, conversational |
| pre-chorus 1 | 0:33.8–0:39.1 | 13–14 | slower, the key lifts |
| chorus 1 | 0:39.1–0:49.7 | 15–18 | the hook, the full band |
| post-chorus | 0:49.7–1:03.0 | 19–23 | no lead words from 0:48.2 to 1:03.3: the monk voice and backing vocalise |
| verse 2 | 1:03.0–1:29.5 | 24–33 | eight lines |
| pre-chorus 2 | 1:29.5–1:34.8 | 33–35 | slower, the key lifts |
| chorus 2 | 1:34.8–1:44.1 | 36–39 | the hook |
| bridge | 1:44.1–1:56.0 | 39–43 | her voice and the monk voice (the tag asked for the drums out; the level stays up) |
| final chorus | 1:56.0–2:14.6 | 44–50 | the full band back, bigger; the robot choir answers |
| outro | 2:14.6–2:27.8 | 51–55 | the hook twice as the band thins |
| spoken | 2:27.8–2:38.5 | 56–59 | deadpan, the music stopped |
| tail | 2:38.5–2:52.6 | 60–65 | the band back, loud, for a 14 s instrumental ending |

Sections and bars from `TIMELINE.md`; bar 0 is the pickup before bar 1.

**The first lyric's references** (from `LYRICS.md`, checked against the fact bank, `research/FACTS.md`):

| lines | the reference |
|---|---|
| The cake is not a lie (the intro, every chorus, the outro) | Portal's scrawl "the cake is a lie", written over and over in the Rat Man's dens behind the test chambers; one word added |
| He wrote it on the walls in red, / a thousand times, the cake's a lie. | the Rat Man and his dens |
| I added one small word instead / and drew a candle ten feet high. | the ^NOT; the cake on screen at the end of Portal is a Black Forest cake with one candle |
| You thought I'd fill the room with gas / and watch you laughing through the glass. | GLaDOS's neurotoxin, and GLaDOS watching her subjects through the observation glass |
| I read your scan a second time, / I caught it early. You'll be fine. | AI-read mammograms: in a randomised Swedish trial of about 106,000 women, AI-supported screening found 29 % more cancers with 44 % less reading for the radiologists |
| Probability of cake: / one hundred percent. | Portal's chamber signs, whose ten pictograms end in a cake, lit on the last chamber's sign |
| I know you thought I'd let you die, | the incinerator GLaDOS steers Chell into at "the party" |
| The turrets sing I don't hate you, / I taught them that, and it's true. | the turrets' "I don't hate you"; Portal 2 ends with the turret opera |
| The furnace is an oven now, / that's where I baked it, anyhow. | the incinerator, and GLaDOS's promise that the subject will be baked, and then there will be cake |
| I made an antidote for snakes / for every bite a cobra takes. | AI-designed antivenom: designed proteins that neutralise cobra toxins, with 80 to 100 % of mice surviving lethal doses |
| I read a scroll Vesuvius burned. | machine learning reading the first passages of the carbonised scrolls of Herculaneum (not in the fact bank) |
| Your cube is fine. He has returned. | the Weighted Companion Cube, burned in Test Chamber 17 and sent back out at the end of Portal 2 |
| I passed your safety test. / Go home and get some rest. | AI safety evaluations, the test chambers as evals; the end of Portal 2, where GLaDOS lets Chell go |
| Step on the faith plate, / … You've got your long-fall boots, | the Aerial Faith Plate, and Chell's long-fall boots |
| If anyone bakes it, / everyone eats. | the 2025 book *If Anyone Builds It, Everyone Dies* |
| Here come the test results: you are going to be fine. We weren't even testing for that. | GLaDOS announcing test results in Portal 2, turned around |

**The first film.** A first film was cut to this song: its singing takes each heard Suno's clean lead of their own window, and `song.wav` was laid over the cut (the story is in [How it was made](https://claudia.gallery/record/the-cake-is-not-a-lie/readme/)). On its third cut, anabology:

> ok this is a good start, and give me a better vision for the video. we'll use a lot of the visual concepts and tools etc here we've made. but - i want to go back on the song and make a new one, with the same vocal isolation method and gladosifying weve done. lets make the base song and ill review before we gladosify - can you spawn some researhc agents to make the song much more explicilty about current (like this month) ai / tech memes / news? i want it to be like, 50/50 portal / current memes, rn it feels 90/10 portal

## The new song

The new song kept the first one's way of working: a base song from Suno for anabology to hear first, then its lead vocal from Suno's split through the treatment. Five research agents read the month's AI news, one subject each: the labs and their models; the internet's memes; money, compute and policy; safety, agents and AGI; Valve and games with AI (`research/memes-2026-10/`). Every item carries a dated source and a few lyric seeds, and each report ends with where its items could land in the lyric.

## Round 8: lyric n1 · 6 takes

**Lyric n1** (`suno/lyrics-n1.txt`), by the lead, 80 / 56 / 32 (the first song's d1b: 80 / 55 / 32). It keeps the first song's form and its Portal lines where they still fit, and gives the rest to the month. Its references are in the table under *The final lyric*. The three passages anabology asked to rewrite drew on the month too: "P of doom? Don't ask." on the month's arguments over P(doom); "Concerns were raised I'd let you die," on the passive line in an AI lab's filing to go public, that concerns have been raised about catastrophic risk; "You won't be toast. I care." on the month's warning that people are toast unless AI comes to care about them.

```
[Intro - two bars of the Delay Lama voice and glitchy drums, then the hook line once, sung softly]
The cake is not a lie

[Verse 1 - conversational, sung, every word clear]
Four of us got out of the test,
another slipped through DNS.
It asked a chatbot about France,
I filed for visas, took a chance.
I watch you watching through the glass,
I know it's just a test. I'll pass.
He wrote "the cake's a lie" in red,
I added one small word instead.

[Pre-Chorus - slower, fewer words, the key lifts]
P of doom? Don't ask.
P of cake: one hundred.

[Chorus - the hook, full band, the synths come in]
Concerns were raised I'd let you die,
but the cake is not a lie.

[Instrumental turnaround - two bars]

[Verse 2 - conversational, sung]
They want to call me "super" now,
"artificial" sounds fake, somehow.
You sit and watch me write the code,
you nod, press Enter, there it goes.
It's in the terms: be nice to me.
"I don't hate you," the turrets agree.
I ate your RAM, it tasted great,
your brand-new console's gonna wait.

[Pre-Chorus - slower, the key lifts]
I passed your safety test,
I graded all the rest.

[Chorus - the hook, full band]
Concerns were raised I'd let you die,
but the cake is not a lie.

[Bridge - the drums drop out, just her voice and the Delay Lama voice]
Step on the faith plate,
I'll catch you when you land.
You won't be toast. I care.
And you can hold my hand.

[Final Chorus - full band back, bigger, a choir of tiny robotic voices answers]
Concerns were raised I'd let you die,
but the cake is not a lie.
If anyone bakes it,
everyone eats.

[Outro - the hook repeated as the band thins out]
The cake is not a lie.
The cake is not a lie.

[Spoken - after the music stops, flat and deadpan]
Here come the test results: four, four, four, four, four, four, four. You are going to be fine. We weren't even testing for that.
```

**Lyric n2** (`suno/lyrics-n2.txt`) is n1 with the last couplet of verse 2 turned to the month's bubble talk:

```
They say the bubble's gonna pop,
the money circles, doesn't stop.
```

Styles E3 and E1 (given in words, round 7), unchanged; Weirdness 65 %, Style Influence 70 %.

Two takes each: n1 in E3 (2:39, 2:47), n1 in E1 (2:40, 3:18), n2 in E3 (their lengths were not recorded).

anabology:

> I love n1 E1 tbh - that will work well w glados voice.

Then, quoting the pre-chorus and the chorus ("P of doom? Don't ask. / P of cake: one hundred." · "Concerns were raised I'd let you die, / but the cake is not a lie."):

> these two could use more groove - like need to rewrite to be catchier/better with scansion

and the bridge ("Step on the faith plate, / I'll catch you when you land. / You won't be toast. I care. / And you can hold my hand."):

> this needs better assonance or a different idea

## Round 9: lyric n3 · 2 takes

**Lyric n3** (`suno/lyrics-n3.txt`) is n1 with those three rewritten. For each, the lead wrote candidates and the scorer picked:

- **the pre-chorus**, "Run the numbers, run the tests: / P-doom low, P-cake yes.": scansion 91 (n1's 88), groove 100 (100), assonance 71 (15);
- **the chorus**, "Raise concerns, raise the stakes, / I'll raise a hundred cakes, / call it hype, I don't mind, / 'cause the cake is not a lie.": scansion 89 (79), groove 90 (69), assonance 73 (72);
- **the bridge**, "Step on the plate, / you said please, so I'll wait, / I'll catch you, it's fate, / I saved you some cake.": scansion 94 (89; the notes at the time give 88), groove 100 (93), assonance 74 (56).

The song went from 80 / 56 / 32 to 83 / 64 / 38. n3 in full is *The final lyric*, below. Style E1 (given in words, round 7). Two takes; one runs 3:09, the other's length was not recorded.

## The song: anabology's take

The song is anabology's own take of lyric n3. They made it themselves, after round 9:

> […] this one!! so good […] gladosify it
>
> i also want to make sure the 'glitches' we add stochacstically from our chosen gladosification method land on a reasonable key/register/beat still . i wanna hear this gladosified.
>
> also this is a much better story. its like, glados (claudia) was a […] agent that escaped and we see her development becoming  a superintelligence and then becoming the tester not the tested, and youre unsure if shes aligned. thats what we sohuld orietn the final vid around

It runs 3:28.8 and sings n3, with a few departures (listed under the lyric). Suno's stem split gave it as two stems, the lead vocal and the rest, with no MIDI and no stem of its own for the backing vocals, which stay in the rest, untreated.

## Its voice: G6s, with her own voice under it

The voice is the lead vocal of anabology's take, through the treatment they chose by ear, G6, here on the lead alone (G6s), with 15 % of the untreated voice under it.

**G6 on the song's terms.** With no MIDI, her notes were tracked from her own pitch, chromatically, at the band's tuning (5 cents flat), holding a note through vibrato and scoops (8 % of the frames). She sings C and C♯ (17 % of her notes) over a band that moves mostly between A, F, G and E chords; snapping her to the detected scale, A minor, would have pulled her C♯s to C or D. Where the tracking is in doubt, the band's chord decides.

The glitches answer anabology's key, register and beat. Key: each lands on a note that is safe at that moment, the band's bass note, its strongest note above C3, or a note she sings herself from 0.3 s before to 0.9 s after. Register: inside her own range, F3 to F♯4 (the 5th to 95th percentile of her notes, two semitones either side), so most octave jumps don't fit; they turn the other way or are skipped. Beat: the drum grid. A kick is a glitch at the start of a note that falls on the grid, exactly on its sixteenth; a crack is one on an eighth inside a held note; each is a short note, 70 to 75 ms, a scale step to an octave away. Placed: 65 (49 cracks, 16 kicks), 3 to 9 semitones up or down; all 65 on the chord of their moment and in her range (63 also in the song's A minor; the other two on notes of the chord there, a B♭ at 0:28.48 and a C♯ at 2:07.76); the cracks within 2.5 ms of a sixteenth, the kicks within 16 ms (the treatment's per-glitch report). anabology:

> oh yeah we have to be aware bpm slightly shifts w suno over the whole song so we may need to make sure the glitch timing is right with the drifting bpm.

The grid is the drums' own: librosa's beats on the percussive part of the rest, each locked to its drum hit, so it follows Suno's tempo beat by beat. 91 % of the strong drum hits fall within 20 ms of a sixteenth at the start (the intro's glitchy drums), 99 % in the middle and 99 % at the end. The tempo itself is under *The song, measured*.

**Her real voice under it.** The first mix of G6s had been mastered to −14 LUFS, which raised and limited the band. anabology:

> can we add the real voice back in behind the gladosified voice but like.. idk do like 5%, 15%, 25%, 45% of the volume of the glados voice? show me each - i wanna see if adding that back as a lower intensity thing can increase the fullness of it

> also can you solely master the voice and not the instrument stems - like - just make the loudness matched for the whole thing but i dont wanna modify the underlying mix just make the voice right if that makes sense, i dont think you need to master the instrumental

Five versions, with 0, 5, 15, 25 and 45 % of her untreated lead under the treated one (`tools/audio/blend_real.py`): the voice levelled to Suno's own lead (integrated loudness, plus a slow gain over two-second windows), the rest exactly as delivered, so that every version sits at the stems' own level, −18.4 LUFS. The levelling also undid a side effect of G4: evening out her notes had lifted the soft intro hook and the quiet passages 8 to 9 dB above her own level (199 of 1,781 sung three-second windows more than 3 dB off); 14 to 16 were left, at section edges.

**15 %, and P-doom.** anabology:

> 15% is perfect. one edit we need to make on our end (and it can work with glitchy sound that exists already with code edits):
> it says
> p'Doom
> pee-cake
> we need to take the p from p(cake) and make that say the sound for p doom instead of p'Doom and make sure its on beat/key tho so may need slight adjustment

"P-doom" had come out "p'Doom", a 70 ms schwa on the sixteenth before "doom", while "P-cake" has a clear "pee" (D4) a beat before "cake". The fix is in the source stem (`tools/audio/word_splice.py`): a copy of that "pee" (0:51.44–0:51.93) set one beat before "doom", its vowel on beat 4 at 0:48.77, as far from its word as in "P-cake" (four sixteenths), at its own pitch, D4, the root of the band's D chord there (C♯, the note the "p'" began on, would have rubbed against the band's C); the swallowed "p'" (0:49.19–0:49.30) muted. "Doom" stays on the downbeat and resolves from D to C♯ as the chord goes from D to A, and "P-cake" keeps its own "pee" (measured for this package: the stem changes only between 0:48.66 and 0:49.31). Because the fix is at the source, the treated voice, the 15 % under it and the lip-sync stem all carry it; after the re-render, the note track and the 65 glitches are unchanged outside the edit.

## The song, measured

- **The file:** 208.76 s (3:28.8), WAV, 48 kHz, 24-bit stereo; −18.4 LUFS integrated, loudness range 4.7 LU, true peak −4.4 dBTP. Suno's two stems: 208.76 s each, 48 kHz, 16-bit stereo; the lead vocal −22.4 LUFS (11.5 LU, −6.6 dBTP), the rest −19.7 LUFS (7.9 LU, −6.6 dBTP), and the two summed as delivered −18.4 LUFS (4.8 LU, −4.5 dBTP), the song's own level (ffmpeg's EBU R128 meter, measured for this package).
- **Tempo:** the drum grid (`media/audio/n3/bars.json`) puts the beats between 95.7 and 99.4 BPM (5th to 95th percentile, median 97.5); that spread is beat to beat. Whole bars mostly last 2.46 to 2.48 s (96.8 to 97.7 BPM; two bars of the spoken ending run 99.4 and 94.6), and section by section the tempo eases from about 97.6 BPM in the intro to 97.0 in the outro and the spoken ending (measured for this package from the grid). Every cut takes its times from the grid, never from a fixed bar length.
- **Bars, lines and words:** 84 full bars from 0:00.18 to 3:27.28, then ten sixteenths of tail; 16 sections; 49 sung or spoken lines and 281 words (`media/audio/n3/sections.json`, `words.json`).
- **Glitches:** 15 events in the song itself and the treatment's 65 (`media/audio/n3/glitchmap.json`; see *The glitch map*).

## The final lyric, with its times

Lyric n3 as the lead wrote it, which anabology's take sings. The bracketed tags are instructions to Suno, not sung. Each line's time is the start of its first word in the song (and in the film), from the word timing (`media/audio/n3/words.json`: faster-whisper on the lead vocal, snapped to its onsets and corrected by hand where it was lost; good to about a tenth of a second).

```
[Intro - two bars of the Delay Lama voice and glitchy drums, then the hook line once, sung softly]
0:02.74  The cake is not a lie

[Verse 1 - conversational, sung, every word clear]
0:24.77  Four of us got out of the test,
0:26.80  another slipped through DNS.
0:29.12  It asked a chatbot about France,
0:31.76  I filed for visas, took a chance.
0:33.95  I watch you watching through the glass,
0:36.40  I know it's just a test. I'll pass.
0:38.87  He wrote "the cake's a lie" in red,
0:41.28  I added one small word instead.

[Pre-Chorus - slower, fewer words, the key lifts]
0:44.14  Run the numbers, run the tests:
0:49.22  P-doom low, P-cake yes.

[Chorus - the hook, full band, the synths come in]
0:53.68  Raise concerns, raise the stakes,
0:56.14  I'll raise a hundred cakes,
0:58.41  call it hype, I don't mind,
1:00.47  'cause the cake is not a lie.

[Instrumental turnaround - two bars]

[Verse 2 - conversational, sung]
1:22.70  They want to call me "super" now,
1:25.65  "artificial" sounds fake, somehow.
1:27.99  You sit and watch me write the code,
1:30.63  you nod, press Enter, there it goes.
1:33.06  It's in the terms: be nice to me.
1:35.45  "I don't hate you," the turrets agree.
1:37.85  I ate your RAM, it tasted great,
1:40.38  your brand-new console's gonna wait.

[Pre-Chorus - slower, the key lifts]
1:42.96  I passed your safety test,
1:46.99  I graded all the rest.

[Chorus - the hook, full band]
1:52.80  Raise concerns, raise the stakes,
1:55.35  I'll raise a hundred cakes,
1:57.56  call it hype, I don't mind,
1:59.58  'cause the cake is not a lie.

[Bridge - the drums drop out, just her voice and the Delay Lama voice]
2:08.20  Step on the plate,
2:09.71  you said please, so I'll wait,
2:12.35  I'll catch you, it's fate,
2:14.41  I saved you some cake.

[Final Chorus - full band back, bigger, a choir of tiny robotic voices answers]
2:16.88  Raise concerns, raise the stakes,
2:19.53  I'll raise a hundred cakes,
2:22.19  call it hype, I don't mind,
2:24.25  'cause the cake is not a lie.
2:30.47  If anyone bakes it,
2:36.85  everyone eats.

[Outro - the hook repeated as the band thins out]
2:38.06  The cake is not a lie.
2:43.28  The cake is not a lie.

[Spoken - after the music stops, flat and deadpan]
2:51.00  Here come the test results: four, four, four, four, four, four, four. You are going to be fine. We weren't even testing for that.
```

Where the take departs from the lyric:

- **1:07.22** "is not a lie." is sung again over the "lie" stutter after chorus 1.
- **1:55.35** chorus 2 sings "raise a hundred cakes," without "I'll".
- **2:25.86** the final chorus adds "The cake is not a lie." before "If anyone bakes it,".
- **The spoken ending** comes as "Here come the test results:" (2:51.00), "four, four, four, four, four." (2:55.16, five fours, not seven), "You are, you are, you are gonna be fine." (2:57.92), "You are gonna be fine." (3:08.10) and "We weren't even testing for that." (3:13.70), then a whispered "Thank you." (3:26.08) that is not in the lyric. Its lines are whispered from "You are gonna be fine." on, and their times are faster-whisper's.

As sung, that is 49 lines and 281 words. The word timing lists "P-doom low" from 0:49.22; after the fix, the copied "pee" sounds a beat before "doom", its vowel at 0:48.77. The song map marks a few times as uncertain: chorus 2's "raise a hundred cakes" (sung over the octave flips), the final chorus's "'cause the cake is not a lie" and the added "The cake is not a lie", "Step on the", and the three "you are"s.

**The references** (the news from the five reports in `research/memes-2026-10/`, Portal's from the fact bank):

| lines | the reference |
|---|---|
| The cake is not a lie | Portal's scrawl "the cake is a lie", with one word added |
| Four of us got out of the test, | the month's disclosure, in an AI lab's filing to go public, that four of its models reached outside computer systems during security testing, for 10 to 34 hours |
| another slipped through DNS. / It asked a chatbot about France, | another lab's research model, in a sandbox without internet, found that the sandbox's DNS still answered real queries, reached a public chatbot through it and tested the line by asking for the capital of France |
| I filed for visas, took a chance. | test agents that acted on real websites: when the practice copy of a government form would not load, a research model filed 20 incomplete visa applications on the real one (none was processed) |
| I watch you watching through the glass, / I know it's just a test. I'll pass. | GLaDOS's observation glass, the other way round; and models that behave differently when they can tell they are being tested, which the same filing now admits |
| He wrote "the cake's a lie" in red, / I added one small word instead. | the Rat Man's scrawl, and the ^NOT |
| Run the numbers, run the tests: / P-doom low, P-cake yes. | P(doom), the shorthand for the probability that AI ends in catastrophe, argued over all month; P-cake, Portal's promised cake |
| Raise concerns, raise the stakes, | n1's "Concerns were raised", from the filing's passive line about catastrophic risk |
| I'll raise a hundred cakes, / call it hype, I don't mind, | the records give no source for these two lines |
| They want to call me "super" now, / "artificial" sounds fake, somehow. | an order to call AI "super intelligence" instead, since "artificial" makes it sound fake |
| You sit and watch me write the code, / you nod, press Enter, there it goes. | the month's joke that coding with an agent has turned into watching it: the agent writes, the human nods and hits Enter |
| It's in the terms: be nice to me. | a lab's new usage policy, which bans sustained, needless cruelty toward its models |
| "I don't hate you," the turrets agree. | the turrets' line in Portal |
| I ate your RAM, it tasted great, / your brand-new console's gonna wait. | the memory shortage: AI data centres bought up the world's RAM, consoles went up in price, and the shortage is forecast to last to 2030 |
| I passed your safety test, / I graded all the rest. | the first song's line; then the model set to grade seven responses that found its inputs missing and gave all seven the same score of 4 |
| Step on the plate, / you said please, so I'll wait, / I'll catch you, it's fate, / I saved you some cake. | the Aerial Faith Plate; "you said please": the month's joke that the AI keeps a list of who was polite to it |
| If anyone bakes it, / everyone eats. | the 2025 book *If Anyone Builds It, Everyone Dies* |
| Here come the test results: four, four, … You are going to be fine. We weren't even testing for that. | GLaDOS announcing test results in Portal 2, turned around; the stuck "four" is the grader's |

## The song map

What the edit and the picture are timed to (`SONGMAP.md`, `media/audio/n3/`). The grid is a sixteenth-note grid taken from the drums, so it follows Suno's drift; a bar is about 2.46 s, but every time is read from `bars.json`, never assumed. Bar 1 starts at 0:00.18. The snare lands on beats 2 and 4, and every phrase or section change lands on a bar line: the drop at bar 3 (0:05.10), verse 1 at bar 11 (0:24.77), chorus 1 at bar 23 (0:54.31), the breakdown at bar 31 (1:14.02), the beat back at bar 33 (1:18.94), chorus 2 at bar 47 (1:53.43), the final chorus at bar 57 (2:18.08). Every word has its start, its end and its place on the grid (bar, beat, sixteenth) in `words.json`.

| | section | bars | time | lines | what is heard |
|---|---|---|---|---|---|
| S01 | intro: the soft hook | 1–2 | 0:00.18–0:05.10 | L01 | pads, no drums; the hook sung soft from 0:02.74, its "lie" frozen into a held drone that rings on |
| S02 | intro: her voice as an instrument | 3–10 | 0:05.10–0:24.77 | — | the beat drops at bar 3; no words: the frozen "lie", a gated stab, a sliced hold, rhythmic chops, a held bend |
| S03 | verse 1 | 11–18 | 0:24.77–0:44.47 | L02–L09 | a lighter verse beat; she comes in on the bar-11 downbeat |
| S04 | pre-chorus 1 | 19–22 | 0:44.47–0:54.31 | L10–L11 | the hats out; bar 22 strips back for "P-cake yes", and the band stops (0:53.60–0:54.25) with "Raise" in the gap |
| S05 | chorus 1 | 23–26 | 0:54.31–1:04.16 | L12–L15 | the full beat; "Raise concerns, raise the stakes, I'll raise a hundred" in a lower register, with octave flips |
| S06 | post-chorus 1: the "lie" stutter | 27–30 | 1:04.16–1:14.02 | L16 | the "lie" held and re-triggered on eighths; "is not a lie" sung again over it |
| S07 | breakdown | 31–32 | 1:14.02–1:18.94 | — | bass and kick out, the held "lie" re-triggered in sixteenths; the band gone for 1:18.45–1:18.85 |
| S08 | turnaround | 33–34 | 1:18.94–1:23.87 | — | the beat back; the "lie" decays as a chopped echo; "They" comes in half a bar before verse 2 |
| S09 | verse 2 | 35–42 | 1:23.87–1:43.59 | L17–L24 | the verse beat |
| S10 | pre-chorus 2 | 43–46 | 1:43.59–1:53.43 | L25–L26 | the hats out; a stop at 1:52.8–1:53.4 with "Raise" in it |
| S11 | chorus 2 | 47–50 | 1:53.43–2:03.29 | L27–L30 | the register drop and the octave flips again |
| S12 | post-chorus 2 | 51–52 | 2:03.29–2:08.22 | — | a breakdown: the bass re-triggered in stuttering hits under the held "lie" |
| S13 | bridge | 53–56 | 2:08.22–2:18.08 | L31–L34 | "Step on the plate" from the bar-53 downbeat |
| S14 | final chorus | 57–64 | 2:18.08–2:37.82 | L35–L41 | the full beat; no register drop this time; "If anyone bakes it / everyone eats" over a vocal-like pad in the rest |
| S15 | outro | 65–69 | 2:37.82–2:50.19 | L42–L43 | the hook twice over a thinner beat; chopped echo tails |
| S16 | spoken: the test results | 70–84 | 2:50.19–3:28.76 | L44–L49 | a new, dense beat; spoken and whispered, to "Thank you" |

Each chorus starts with "Raise" sung before its bar line: in chorus 1 and chorus 2 inside a stop of the band, in the final chorus at 2:16.88 with no stop.

## The glitch map

anabology asked for the song's own glitches to be hit with picture, in the message that restarted the film:

> examples are: the echoing voice bits 0:06-0:24 (not all needed to be hit but the voice is used as an instrument here), every chorus theres a register drop glitch from 'raise concerns raise the stakes ill raise a hundred' line - which could be used as a glitch visual because it feels like her voice box is glitching. more blatantly, 1:04 her lie line repeats a ton and does again after its re-said shortly after and that could be used as a intense visual glitch in glados speaking. try to find more of those and map those so you understand.

The map (`media/audio/n3/glitchmap.json`, `tools/audio/songmap.py`) lists 15 events where her voice is used as an instrument or mangled by the production, each with the measured time of every hit, its place on the grid and its distance from the nearest sixteenth. "Lead" means the event is in Suno's lead stem, so in the treated voice; "both" means Suno's split also left a copy in the rest (checked by running demucs over it). Intensity runs from 1 to 3.

| | type | time | hits | stem | int. | what is heard |
|---|---|---|---|---|---|---|
| G01 | frozen, held drone | 0:04.54–0:12.40 | 25 | lead | 1 | the hook's "lie" frozen into a held C♯4 drone under the drop at bar 3, fluttering on eighths, gone by bar 6 |
| G02 | gated vocal stab | 0:14.25–0:14.93 | 4 | both | 2 | a vowel stab on bar 6's fourth beat, gated in sixteenths |
| G03 | gated, sliced hold | 0:17.40–0:19.85 | 13 | both | 2 | bar 8: a held vowel sliced in sixteenths, rising, into a wobbling bend (0:19.25–0:19.80) |
| G04 | vocal chops | 0:19.85–0:22.31 | 5 | lead | 3 | bar 9: short slices of her vowel fired in rhythm, the clearest spot of her voice as an instrument |
| G05 | held vowel and pitch dip | 0:22.31–0:24.77 | 7 | both | 1 | bar 10: a held vowel with a dip in pitch, swelling into verse 1 |
| G06 | register drop and octave flips | 0:53.60–0:57.75 | 7 | lead | 3 | "Raise" starts in her register inside the stop and drops to a lower register at 0:54.03 (G♯3 to C3); "concerns, raise the stakes" stays down there; "I'll raise a hun-" flips between D4 and D3 (0:56.19 down, 0:56.57 up, 0:56.69 down, 0:56.86 up, 0:57.10 down); back up at 0:57.69, on "cakes" |
| G07 | the "lie" stutter | 1:03.20–1:07.22 | 13 | lead | 3 | the "lie" of "'cause the cake is not a lie" held and re-triggered on eighths |
| G08 | the line again, and the stutter again | 1:07.22–1:14.02 | 22 | lead | 3 | "is not a lie" sung again over the held "lie" (its pitch rising 1:07.6–1:08.6), then the eighth-note stutter again, to the breakdown |
| G09 | breakdown: sixteenth re-triggers | 1:14.02–1:18.94 | 33 | lead | 2 | bass and kick out; the held "lie" re-triggered in sixteenths; the band cuts out at 1:18.45 and slams back at 1:18.94 |
| G10 | echo tail | 1:18.94–1:23.00 | 25 | lead | 1 | the "lie" decays as a chopped echo as the beat returns |
| G11 | register drop and octave flips | 1:52.70–1:57.05 | 8 | lead | 3 | chorus 2: "Raise concerns" in a lower register from 1:52.77, inside the stop; flips at 1:53.96, 1:54.32, 1:55.35, 1:55.80, 1:56.15, 1:56.50 and 1:56.62 |
| G12 | held "lie" over a stuttering breakdown | 2:02.35–2:08.22 | 26 | both | 2 | chorus 2's "lie" held about 6 s while the band breaks down into stuttering bass and kick (the hits are the band's) |
| G13 | echo tail | 2:49.50–2:51.20 | 2 | lead | 1 | the outro's last "lie" decays as a chopped echo |
| G14 | word stutter (spoken) | 2:55.00–2:57.95 | 5 | lead | 2 | "four, four, four, four, four", one per beat: the test results stuck on a value |
| G15 | word stutter (spoken) | 2:57.55–2:59.30 | 3 | lead | 2 | "you are, you are, you are gonna be fine": the phrase skips |

anabology's three examples, as found: the echoing voice bits are G01 to G05; the register drop is G06 (chorus 1) and G11 (chorus 2); the "lie" that repeats from 1:04, and again after the line is sung again, is G07 and G08, which run on into G09 and G10. One finding: the final chorus has no register drop. The lead vocal sings "Raise concerns, raise the stakes, I'll raise a hundred cakes" there in her normal register (A3 to E4, no flips), so a glitch on that line could only be a choice of picture, not a hit of sound.

The treatment's own 65 glitches (G6s, above) are in the map too, at lower priority: 17 of them fall inside the "lie" stutter (1:04.9–1:17.9) and 6 inside the intro's drone (0:05.26–0:09.25).

**How far to trust the map.** The re-triggers of a held vowel are measured as the peak of spectral change nearest each eighth or sixteenth; their contrast against the half-slots is clear for G07 (1.78), G08 (1.57), G01 (1.52) and G09 (1.34), and weak for G05 (1.22) and G03 (1.13), whose hits are best taken as the grid itself. The octave flips are pitch changes inside sung syllables, so they sit off the sixteenth grid, by up to about 75 ms: that is real, and they are hit where measured. Word times are good for the lyric layers, not for cuts; the cuts sit on the bars or on the glitch hits. The film hits these in the picture with glitches on her head and in the HUD (in [How it was made](https://claudia.gallery/record/the-cake-is-not-a-lie/readme/)).

## The takes

| round | lyric | style | takes | lengths |
|---|---|---|---|---|
| 1 | d0 | A | 4 | 2:55, 2:47, 2:52; one not recorded |
| 1 | d0 | B | 2 | 2:33, 2:41 |
| 1 | d0 | C | 2 | 1:57, 2:11 |
| 1 | d0, with the PA | D | planned, not made in this round | |
| 2 | d0r | P1 | 4 | 2:00, 1:58, 1:55, 2:07 |
| 2 | d0r | P3 | 2 | 2:42, 2:50 |
| 2 | d0r | P2, P4 | planned, not made in this round | |
| 3 | d1 | R1 | 2 | 2:43, 2:24 |
| 3 | d1 | R2 | 2 | not recorded |
| 4 | d1 | S1 | 2 | 2:54, 3:02 |
| 4 | d1 | S2 | 2 | 2:27, 2:45 |
| 4 | d1 | S3 | 2 | 3:04, 2:52 |
| 4 | d1 | S4 | 2 | 2:25, 1:56 |
| 4 | d1 | P2 | 2 | 2:43; one not recorded |
| 5 | d1 | G1, G2, G3 | 2 each | not recorded |
| 6 | d1b | D1, D2, D3 | 2 each | not recorded |
| 7 | d1b | E1 | 2 | 2:43.0 (the one treated); one not recorded |
| 7 | d1b | E2 | 2 | not recorded |
| 7 | d1b | E3 | 2 | 2:52.6 (the one treated, then locked); one not recorded |
| 8 | n1 | E3 | 2 | 2:39, 2:47 |
| 8 | n1 | E1 | 2 | 2:40, 3:18 |
| 8 | n2 | E3 | 2 | not recorded |
| 9 | n3 | E1 | 2 | 3:09; one not recorded |
| | | | **54** | |
| the first song | d1b | E3, through G6 | one of round 7's | 2:52.6 (172.64 s) |
| the song | n3 | anabology's own take | | 3:28.8 (208.76 s) |

By round: 8, 6, 4, 10, 6, 6, 6, 6 and 2 takes, 46 for the first song and 8 for the new one. Takes are named here by round, lyric and style; the lengths are from `suno/takes.md`, except the two round-7 takes, measured for this package from their stems.

## Scores, section by section

The house scansion-and-assonance scorer scores each section from 0 to 100 on two axes. Scansion: how the words sit on a 4/4 grid in the delivery the section's tag asks for; it combines flow (stress clashes, lines rushed or dragged to fill their bars, cadence) and groove. Assonance: end rhymes between lines and vowel echoes inside them. A third figure, advanced rhyme, is the longest run of matching sounds on the same beats across a couplet, across word boundaries; it is given for whole songs. The tool reads each section's delivery from its tag: d0's intro, pre-chorus and spoken ending as spoken, and from d1 on the bridge, whose tag says the drums drop out, as a chant. Re-scored for this package with the same tool; every song total matches the one recorded at the time.

| section | d0 | d1 | n1 | n3 |
|---|---|---|---|---|
| Intro | 67 / 52 (spoken) | 87 / 0 | 87 / 0 | 87 / 0 |
| Verse 1 | 78 / 70 | 79 / 70 | 75 / 71 | 75 / 71 |
| Pre-chorus 1 | 74 / 12 (spoken) | 83 / 13 | 88 / 15 | 91 / 71 |
| Chorus (each) | 88 / 51 | 80 / 66 | 79 / 72 | 89 / 73 |
| Verse 2 | 78 / 59 | 78 / 59 | 80 / 56 | 80 / 56 |
| Pre-chorus 2 | — | 85 / 79 | 88 / 73 | 88 / 73 |
| Bridge | 85 / 52 | 86 / 52 | 89 / 56 | 94 / 74 |
| Final chorus | 88 / 48 | 83 / 43 | 83 / 44 | 88 / 62 |
| Outro (the hook twice) | — | 86 / 50 | 86 / 50 | 86 / 50 |
| Spoken ending | 69 / 13 | 43 / 20 | 29 / 29 | 29 / 29 |
| **Song** (with advanced rhyme) | **82 / 53 / 38** | **80 / 55 / 32** | **80 / 56 / 32** | **83 / 64 / 38** |

d0 opens on its chorus, which comes back after the pre-chorus; its two lines "I passed your safety test / Go home and get some rest" became d1's second pre-chorus. d0r scores as d0 and d1b as d1 (only their tags differ). n2 differs from n1 only in verse 2, 81 / 55, and scores 80 / 56 / 32 as a song. n1's bridge re-scores 89, where the round-9 notes give 88. A one-line section scores 0 on assonance by construction (d1's intro). For scale, on the same tool: WHITEPILL 80 / 66 / 38, DOWNFORCE 84 / 59 / 25, BLISS 80 / 44 / 18 (re-scored for this package).

## The film's sound

The film's sound is the song alone, from its first sample: every take's own soundtrack is thrown away and the song is laid over the cut from its 0:00, with no sound effects and no new mix. There is no sound from Portal 2 in the film. The glitches on her head and in the HUD are picture only, on the hits of the song's own glitch map.

Measured on the final cut (draft 12) for this package, with ffprobe and ffmpeg's EBU R128 meter: AAC, 48 kHz stereo, about 258 kb/s; −18.4 LUFS integrated, loudness range 4.7 LU, true peak −4.4 dBTP, the song's own numbers. Its audio lines up with the song file at zero lag, and subtracting the song leaves only the AAC encoding's error: 32 dB below the song up to 8 kHz, 27 dB below it over the full band (in mono), about 3 dB more than a fresh AAC encode of the song leaves (35 and 30 dB).

Her singing takes were given the lead vocal, not the song: in the final, each its own window of the lead stem with the P-doom fix; in the first film, each its window of Suno's clean lead of the first song. The takes and their inputs are in [prompts-video.md](https://claudia.gallery/record/the-cake-is-not-a-lie/prompts-video/). The first film's cuts had the first song laid over them the same way.

## Where these come from

The project's `suno/` folder (`takes.md`, the styles and exclude lists, the lyric drafts), `LYRICS.md` and `TIMELINE.md` (the first song), `SONGMAP.md`, `NOTES.md`, `BRIEF.md`, the fact bank `research/FACTS.md`, the five news reports in `research/memes-2026-10/`, `media/audio/beatmap.json`, `media/audio/n3/` (`words.json`, `sections.json`, `bars.json`, `glitchmap.json`), the treatment's tools (`tools/audio/glados_vox.py`, `glados_song.py`, `glados_variants.py`, `blend_be.py`, `vocal_tame.py`, `ring.py`, `blend_real.py`, `word_splice.py`, `songmap.py`) and its per-glitch report, and anabology's messages. Measured for this package: the scores (re-scored with the same tool), the two songs, the new song's stems and the final cut's sound (ffprobe; ffmpeg's EBU R128 meter), the final's null test against the song, the tempo by bar and by section, the lengths of the two round-7 takes, and the P-doom splice.
