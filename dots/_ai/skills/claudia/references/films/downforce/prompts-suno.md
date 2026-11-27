# Suno — the song (DOWNFORCE)

**Final take:** anabology's own. It runs 3:09.6 (189.60 s) and arrived as a WAV, 48 kHz, 16-bit stereo. They made it themselves in Suno from the lead's draft 8, with their own edits to the lyric and their own Memphis-phonk style. They sent it: "lets use this one." The records do not say how they made it, or which model or Voice it used.

**Before that.** Claude, the production lead ("the lead" below), wrote eight lyric drafts and nine styles. It ran four rounds of takes, 34 in all, in Suno, as on the earlier films. anabology listened between rounds and answered in a line or two. None of the 34 takes is in the film, but most of the lyric is. anabology kept draft 8's two verses (changing one word, AI to SI), chorus, build, drop and outro, and rewrote the intro and both pre-choruses.

**Model and voice in the lead's rounds:** Suno v6-wild with Max Mode. In rounds 1 and 2, some takes used the Voice made from ESCAPE VELOCITY. Every other take had no Voice and the Vocal Gender set to female.

The song was locked before the storyboard began.

---

## The brief

anabology's first message asked for "a hype suno song but not generic (maybe synthwave hype)" (the whole message is in the README). The lead sent its plan. For the song it proposed:

- **Styles:** darker synthwave than the retro-neon default, in three styles, each with and without the Voice.
- **Lyric:** every line reads off Tesla's own dashboard readout, so each line has a real number to put on screen. The readings: 90° (the HUD reads 89.7), 69 ft (69.1 at most), 4,700 kg of downforce (4,697–4,709), pitch 170°, and 68 ft and 0.4 g off the top of the ramp.
- **Hook:** a syncopated sung "Hold me upside down", with a "DOWN / FORCE" chant in the drop.

The direction rides in the lyric field's section tags. The chorus tag, for example: `[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]`. anabology kept that tag in their final sheet.

## The scorer

Every draft was scored with the project's `scansion.py` on two axes, each from 0 to 100:

- **Scansion:** how the words sit on a 4/4 grid in the delivery the section tag asks for (spoken, sung or chant). It combines flow and groove. Flow covers stress clashes, lapses, lines rushed or dragged to fill their bars, and cadence.
- **Assonance:** end rhymes between lines, and vowel echoes inside them.

Scores below are written scansion / assonance. For the second round the lead wrote `tools/lyricopt.py`, which does not write lines. The lead wrote candidate lines by hand for each line of a section. The tool scored every combination of them (exhaustively, up to 60,000 per section) on 0.5 × scansion + 0.5 × assonance and listed the best. The lead then chose among the top scorers by meaning. Over the four rounds it scored 2,803 section combinations built from 337 candidate lines (the `cands-*.json` files kept with the lyric drafts).

For scale, as the lead measured them at the time: BLISS's lyric scored 80 / 43 and CLODYSSEY's 83 / 55. AIRPLANE MODE's final draft scored 88 / 75 (its own package).

## How the lyric got here

### Round 1: draft 3, three darker styles

The lead wrote draft 1, then made two fixes to its first verse before anything was sent:

- **Draft 1, 79 / 48:** "White car, red lights, and a wall where the road should be. / Ninety degrees and the ground is behind me. / Sixty-nine feet with the night underneath. / Forty-seven hundred kilos holding me."
- **Draft 2, 81 / 46:** the last three lines became "Ninety degrees, and the ground is behind me. / Sixty-nine feet with the sky underneath. / Forty-seven hundred kilos, I can barely breathe."
- **Draft 3, 81 / 52:** the first two lines became "White car, red lights, and the road turns into a wall. / Ninety degrees, and I'm never gonna fall." The verse's assonance went from 41 to 72.

Draft 3 opened on radio calls: "Downforce on. / Fans at full. / Hit the wall." Its pre-chorus held the car upside down ("Pitch one-seventy. / Hold."), and it ended "Downforce off." Both verses carried the night's numbers.

It went out in three styles: D1 darksynth chase at 118 BPM, D2 turbo Italo disco / French touch at 122, and D3 EBM darkwave at 124. The first Create went through twice, which is why D1 with the Voice has four takes. There were ten takes: D1 with the Voice ×4, then D1, D2 and D3 without it, ×2 each.

### Round 2: the scansion pass, draft 5

Later, with the first takes in:

> I like it but could use a scansion / assonance optimizer pass

The lead wrote 200 candidate lines over four passes and scored 2,114 combinations. Draft 4 (85 / 67) assembled the best of them, and draft 5 (86 / 67) tightened it. What changed, section by section (draft 3 → draft 5):

- **Verse 1** (68 / 72 → 77 / 80): the opener had three stress clashes and became "Foot to the floor, and the road becomes a wall." The verse now ends on a full rhyme, short enough not to rush: "Sixty-nine feet, with the sky underneath. / Forty-seven hundred kilos, gritting my teeth."
- **Pre-chorus** (79 / 0 → 81 / 47): "Pitch is one-seventy. / Hold it, steady."
- **Chorus** (87 / 66 → 90 / 78): the five syllables of "Hold me upside down" were being dragged across two bars (stretched ×2.02). Doubled to "Hold me, hold me, upside down", the hook fills them and carries the syncopation. The last line became "Never let me touch the ground".
- **Verse 2** (63 / 81 → 75 / 85): "Down to point four" replaced "floating", because 0.4 g makes her lighter, not weightless. "Land in the smoke" removed a run of unstressed syllables.
- **Second pre-chorus** (93 / 18 → 92 / 68) **and outro** (94 / 27 → 94 / 54) now rhyme: "Back on the ground. / Turn it all around." and "Fans off. / Downforce off."

The top scorers were not always taken. The optimizer's best intro was "Clear the floor. / Clear the floor. / Up the wall." (94 / 56), and its best second verse began "Weightless at point four" (73 / 84). The lead ruled out repeated lines, a second "floor" and the wrong g-force.

Two takes of draft 5 in D1 with the Voice went out. Later, anabology wrote:

> Just make me all

So draft 5 went out in all three styles, with and without the Voice. That was 10 more takes, 12 on draft 5 in all.

### The opening

Then:

> Darkwave is the best, I don't like the opening part, do iwhtout voice, use darkwave but more futurist/synth wave and slightly happier but still ebm darkwave 

The lead read "the opening part" as the music. It wrote draft 6, which is draft 5 with an instrumental intro (85 / 74), and three new styles. anabology stopped the takes before they ran:

> Well I'd reword the opening 

The lead scored 21 candidate lines for the intro and offered three rewordings (intro scores):

- **A:** "Every road ends somewhere. / Mine goes up." (82 / 56), leading into "Red lights rising, and the road becomes a wall."
- **B:** "The road runs out. / I don't." (94 / 13), leading into "Floor it to the end, where the road becomes a wall."
- **C:** "They said it'd never fly. / Watch me." (86 / 23), a nod to the old promise that the car might one day fly.

### Round 3: the night's story, draft 7

Then:

> idk none feel great. can you dig more and see if theres more context about the entire thing we can use and pepper across the entire song?

The lead read the coverage of the night and of the car's history into a fact bank, every fact with its source (`research/facts.md`). It rebuilt the song from that as draft 7 (82 / 66), scoring 98 candidate lines in two passes. Here is what the draft took from the facts:

- **"Not AI."** Elon Musk to the crowd: "We need an audience to prove that it's not AI or SI. So you guys can tell people that you saw it with your eyes." (CNN, Euronews.) In draft 7 that became the intro, "Bring a crowd. Prove it's not AI. / Say you saw it with your eyes.", and the outro, "Tell 'em what you saw." The song's pilot, Claudia, is an AI.
- **Nobody in the car.** The demos were remotely operated (Electrek, Wikipedia): "Nobody in the driver's seat. / Nobody you can see."
- **The long wait.** The Roadster was revealed in 2017, driving out of the back of the Semi's trailer. Then came nine years of promised dates, an April Fools' date, and an event moved by rain to 15 October (Wikipedia, Electrek). That became verse 1: "Out the back of a Semi in twenty-seventeen. / Promised you twenty-twenty, then nine years in between. / April Fools came and went, then it rained on the show. / October fifteen, it's go for launch, so I go."
- **The last human-driven car.** Tesla called the car "the best of the last human-driven cars" (Fox Business): "Last of the human-driven cars. / Funny. I'm not human."
- **The sister in orbit.** The first Roadster, Starman's, has been orbiting the Sun since February 2018 with "DON'T PANIC" on its dash. That became a bridge: "My sister's been in orbit since twenty-eighteen. / Don't Panic, says her dashboard screen. / You wanted flying cars. / Here we are."
- **"Well, it worked."** Musk after the first flight (Euronews), as the outro's first line.

The chorus stayed. The second pre-chorus scored 78 / 12, the weakest rhyme in the draft, and the lead kept it for the joke.

The new styles were EBM darkwave pushed toward futurist synthwave, happier, with a lift into a major key in the choruses and no Voice: E1 at 124 BPM, E2 at 122 and E3 at 126. Six takes.

### Round 4: hype only, draft 8

Then:

> i wanna remove the elon roast plz . dont mention ship date, its a super hype edit, and i want it to be even more fast paced and more hype

anabology did not say which lines were the roast. The lead cut every delay and promise line: 2020, the nine years, April Fools and the rain. It named no delivery date, and it dropped "Well, it worked." too, as a possible dig. Draft 8 (84 / 61) kept only the triumphant facts:

- **Intro:** a crowd chant, "Go for launch!" ×2, the livestream's own title.
- **Verse 1:** the numbers. "Zero to sixty in point eight one, / up the wall at ninety, and I'm not done. / Sixty-nine feet, with the sky underneath, / forty-seven hundred kilos, gritting my teeth."
- **Verse 2:** the hardware and two callbacks. "Ten thrusters, six hundred liters, ten thousand PSI, / kickflip the lineup. Go on and call it AI. / Born in a Semi, now I'm flipping over one, / while my sister's still in orbit, circling the sun."
- **Build,** one word on every beat: "Four fans. Two G. / Thrusters. Go."
- **Drop:** a chant of Lars Moravy's line from the stage (Fox Business), "Flying cars are real!" ×2.
- **Outro:** "Tell 'em what you saw."

The bridge went. Its sister moved into verse 2, and its flying cars into the drop. The last optimizer pass chose verse 2's first and last lines. It also chose "Thrusters. Go." over "Ten thrusters. Go." for the build, since the ten had moved into the verse. The styles went faster: F1, F2 and F3 combine EBM darkwave and futurist synthwave at 140, 145 and 150 BPM, with crowd chants and no slow sections. Six takes.

### anabology's take

anabology picked none of the 34 takes. Later, they sent their own take, their lyric sheet and their style:

> lets use this one. 

Their sheet is draft 8 with these changes:

- **Intro:** the crowd chant became a countdown, `[Intro - A robot, female synth phonk voice]` "Three-two-three-two... (repeats) / Three, two, one!"
- **Pre-chorus 1:** "Nobody in the driver's seat. / Nobody you can see." became a sung pre-chorus with cowbell: "The last one in the driver's seat, / The last car can't be beat." It turns Tesla's "the best of the last human-driven cars" into a boast.
- **Verse 2:** "call it AI" became "call it SI", the other half of Musk's "not AI or SI".
- **Pre-chorus 2:** "Last of the human-driven cars. / Funny. I'm not human." became `[Pre-Chorus - ad-lib, phonk-core]` "Roads? / Where we're going... / We don't need roads.", the closing line of *Back to the Future* (1985).
- **Tags:**
  - Verse 1's delivery became "Woman's phonk voice, playfully bouncy, spoken fast, inspiring".
  - In the first chorus, "the drums double" became "cowbell intensifies".
  - Verse 2 took the old pre-chorus tag, "spoken, the filter opens, then everything stops for half a bar".
  - The "Flying cars are real!" drop became "Inspiring, hype, smooth voice".

The lines of both verses (apart from "SI"), the chorus, the build, the drop and the outro are the lead's, as draft 8 had them. anabology gave no reason for their changes.

The style is new. Every one of the lead's rounds had excluded "phonk, cowbell", the first two words of each exclude list. anabology's style asks for "Memphis phonk, distorted cowbells, cowbells the whole song".

Scored the same way, anabology's sheet is 84 / 59 as written. The scorer reads "SI" as one syllable, "see", so it finds no rhyme with "PSI". Spelled as the two letters, "S I", the couplet rhymes again: verse 2 goes from 79 / 52 to 78 / 83, and the song scores 84 / 64. Their new pre-choruses rhyme better than the lines they replaced: 75 / 77 against 73 / 63, and 89 / 57 against 78 / 12. Their countdown intro scores 72 / 27, against 95 / 50 for the chant it replaced.

## Scores, section by section

Scansion / assonance for the four drafts sent to Suno and anabology's sheet. These were re-scored for this package with the same tool, and the song totals match those recorded during production. A dash means the draft has no such section.

| section | draft 3 | draft 5 | draft 7 | draft 8 | anabology's sheet |
|---|---|---|---|---|---|
| Intro | 94 / 12 | 94 / 18 | 80 / 46 | 95 / 50 (chant) | 72 / 27 |
| Verse 1 | 68 / 72 | 77 / 80 | 74 / 84 | 74 / 80 | 74 / 80 |
| Pre-chorus 1 | 79 / 0 | 81 / 47 | 73 / 63 | 73 / 63 | 75 / 77 (sung) |
| Chorus (×2) | 87 / 66 | 90 / 78 | 90 / 78 | 90 / 78 | 90 / 78 |
| Verse 2 | 63 / 81 | 75 / 85 | 76 / 82 | 78 / 81 | 79 / 52 (78 / 83 read "S I") |
| Pre-chorus 2 | 93 / 18 | 92 / 68 | 78 / 12 | 78 / 12 | 89 / 57 (sung) |
| Bridge | — | — | 80 / 74 | — | — |
| Build | — | — | — | 92 / 0 | 92 / 0 |
| Drop chant | — | — | — | 91 / 50 | 91 / 50 |
| Outro | 94 / 27 | 94 / 54 | 91 / 18 | 87 / 27 | 87 / 27 |
| **Song** | **81 / 52** | **86 / 67** | **82 / 66** | **84 / 61** | **84 / 59** (84 / 64 read "S I") |

## Where the final lyric's facts come from

| line | source |
|---|---|
| "Zero to sixty in point eight one" | 0–60 mph in 0.81 s, claimed live and not certified (Electrek) |
| "up the wall at ninety" · "Sixty-nine feet" · "forty-seven hundred kilos" | Tesla's on-screen readings, read frame by frame off the livestream: 89.7°, 69.0–69.1 ft, 4,697–4,709 kg |
| "The last one in the driver's seat, / The last car can't be beat." | Tesla: "the best of the last human-driven cars" (Fox Business) |
| "Ten thrusters, six hundred liters, ten thousand PSI" | ten cold-gas thrusters, 600 L of gas at 10,000 psi (Electrek's technical look) |
| "Go on and call it SI." · "Tell 'em what you saw." | Musk to the crowd: "We need an audience to prove that it's not AI or SI. So you guys can tell people that you saw it with your eyes." (CNN, Euronews) |
| "Born in a Semi, now I'm flipping over one" | the 2017 reveal, out of the Semi's trailer at the Semi's unveil (Wikipedia); the kickflip over a lineup with the Semi in it, 15 October 2026 |
| "while my sister's still in orbit, circling the sun" | the first Roadster, launched on Falcon Heavy on 6 February 2018, still orbiting the Sun (whereisroadster.com, NBC) |
| "Roads? / Where we're going... / We don't need roads." | *Back to the Future* (1985), anabology's addition |
| "Four fans. Two G." | four fans (Electrek); Moravy: the fans "pull up to 2 Gs in order to make the car go upside down" (Euronews) |
| "Flying cars are real!" | Lars Moravy on stage (Fox Business) |

## The dropped lines, and why

- **The radio calls** of drafts 1 to 5: "Downforce on. / Fans at full. / Hit the wall.", "Pitch one-seventy. / Hold.", "Wheels down. / Again.", "Downforce off." The scansion pass reworded them. The concept went when anabology asked for "the opening part" to change and then for more context.
- **"White car, red lights, and the road turns into a wall."** It had three stress clashes. Draft 5 replaced it with "Foot to the floor…".
- **"Point four G and the stars are under my feet" and "floating in my seat".** At 0.4 g she is lighter, not weightless.
- **The three new openings, A, B and C.** anabology: "idk none feel great."
- **Draft 7's verse 1 (the nine-year wait) and "Well, it worked."** anabology: "i wanna remove the elon roast plz . dont mention ship date".
- **"Bring a crowd. Prove it's not AI. / Say you saw it with your eyes."** Draft 8 gave the intro to a crowd chant for the faster version. The second half survives as the outro.
- **The bridge,** "My sister's been in orbit since twenty-eighteen. / Don't Panic, says her dashboard screen. / You wanted flying cars. / Here we are." It went in draft 8's speed-up, which asked for no slow sections. The sister moved into verse 2, and the flying cars into the drop.
- **"Go for launch!", "Nobody in the driver's seat. / Nobody you can see." and "Last of the human-driven cars. / Funny. I'm not human."** anabology replaced these in their own sheet.

## The final lyric sheet (anabology's, verbatim)

```
[Intro - A robot, female synth phonk voice]
Three-two-three-two... (repeats)
Three, two, one!

[Verse 1 - Woman's phonk voice, playfully bouncy, spoken fast, inspiring, over the driving sixteenth-note bass]
Zero to sixty in point eight one,
up the wall at ninety, and I'm not done.
Sixty-nine feet, with the sky underneath,
forty-seven hundred kilos, gritting my teeth.

[Pre-Chorus - sung, cowbell]
The last one in the driver's seat,
The last car can't be beat. 

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; cowbell intensifies]
Hold me, hold me, upside down
Wheels on the ceiling, the world spun around
Hold me, hold me upside down
Never let me touch the ground

[Drop - instrumental, the hardest part: distorted lead and a shouted chant "down, force"]

[Verse 2 - spoken, the filter opens, then everything stops for half a bar]
Ten thrusters, six hundred liters, ten thousand PSI,
kickflip the lineup. Go on and call it SI.
Born in a Semi, now I'm flipping over one,
while my sister's still in orbit, circling the sun.

[Pre-Chorus - ad-lib, phonk-core]
Roads?
Where we're going... 
We don't need roads.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me, hold me, upside down
Wheels on the ceiling, the world spun around
Hold me, hold me upside down
Never let me touch the ground

[Build - spoken fast, rising, one word on every beat]
Four fans. Two G.
Thrusters. Go.

[Drop - Inspiring, hype, smooth voice]
Flying cars are real!
Flying cars are real!

[Outro - the beat cuts on the one; her voice, deadpan]
Tell 'em what you saw.
```

## The final style (anabology's, verbatim)

```
Memphis phonk, distorted cowbells, cowbells the whole song, wide 808 bass, gritty synth stabs and chopped wordless mixed-voice samples, low complexity, simple beat that repeats the whole song; smoky chant hook, vinyl crackle, filtered snare fills, four-on-the-floor kick, sidechain pumping, syncopated sub drops, wide stereo and tape saturation; 124 BPM off-center night-drive groove with tactile low end and late-night tension
```

No exclude list or other setting is recorded for their take.

## The lead's styles, as entered

Rounds 1 and 2 used D1–D3, round 3 used E1–E3 and round 4 used F1–F3. Each round's three styles share the same exclude list.

- **D1, darksynth chase:** "darksynth, outrun chase, 118 BPM, F minor, relentless sixteenth-note analog bass arpeggio, gated reverb snare, huge tom fills, distorted sawtooth lead, cold choir pads, cinematic riser into a hard drop, heavy sidechain pumping, deadpan female spoken verses through a radio filter, soaring syncopated sung female hook with a vocoder double, chopped vocal chant in the drop, night test track, modern loud mix, short intro"
- **D2, turbo Italo / French touch:** "turbo italo disco meets french touch, 122 BPM, A minor, chase arpeggio bass, filtered disco loop, crunchy compressed drums, overdriven sidechained synth stabs, hand claps, deadpan female spoken verses through a radio filter, glossy syncopated sung female hook with talkbox and vocoder doubles, chopped vocal chant, euphoric filter-sweep drop, nocturnal drive, short intro, big hook"
- **D3, EBM darkwave:** "EBM, darkwave, industrial synth, 124 BPM, D minor, distorted sixteenth-note sequenced bass, metallic percussion, gunshot snares, cold detuned pads, icy deadpan female spoken vocals through a radio filter, haunting syncopated sung female hook, whispered calls, fashion show weight, gritty analog synths, abrupt hard drop, minimal and heavy, short intro"
- **E1:** "EBM darkwave meets futurist synthwave, 124 BPM, D minor verses lifting to F major choruses, driving distorted sixteenth-note sequenced bass, metallic percussion, punchy gated snares, bright shimmering analog arpeggios, glossy retro-future pads, cool deadpan female spoken verses, soaring hopeful sung female hook, night drive euphoria, full beat from the first bar"
- **E2:** "futurist synthwave on an EBM darkwave engine, 122 BPM, A minor with a major-key lift in the chorus, cold driving sequenced bass, crisp electronic drums, chrome arpeggios, uplifting bittersweet chords, cool female spoken verses, bright confident sung female hook, sleek and optimistic, starts on the beat"
- **E3:** "EBM, darkwave, futurist synthwave, 126 BPM, E dorian, gritty sixteenth-note bass, industrial percussion, bright retro-future synth lead, warm major chords in the chorus, deadpan female spoken verses, euphoric sung female hook, dark but uplifting, hard-hitting from the first bar"
- **F1:** "EBM darkwave meets futurist synthwave, 140 BPM, relentless four-on-the-floor kick, distorted sixteenth-note sequenced bass, metallic percussion, gated snares, bright shimmering arpeggios, D minor lifting to F major, fast punchy deadpan female spoken verses, soaring syncopated sung female hook, shouted crowd chants, huge drops, full energy from the first bar, no slow sections"
- **F2:** "futurist synthwave on a hard EBM engine, 145 BPM, A minor with a major lift, pounding drums, rolling sequenced bass, chrome arpeggios, euphoric and fast-paced, punchy female spoken verses, big sung female hook, stadium chants, hard-hitting from the first bar, relentless hype"
- **F3:** "EBM, darkwave, futurist synthwave, 150 BPM, E dorian, gritty driving bass, industrial percussion, bright retro-future lead, warm major chords in the chorus, rapid deadpan female verses, euphoric sung female hook, shouted crowd chants, relentless and hype, no breakdowns longer than a bar"

## Exclude styles (the lead's rounds)

Rounds 1 and 2 (D):

```
phonk, cowbell, trap, dubstep, festival EDM build, saxophone, acoustic guitar, lo-fi, chill, country, guitar solo, male vocals
```

Round 3 (E):

```
phonk, cowbell, trap, dubstep, festival EDM build, saxophone, acoustic guitar, lo-fi, chill, country, guitar solo, male vocals, ambient intro, slow intro
```

Round 4 (F):

```
phonk, cowbell, trap, dubstep, saxophone, acoustic guitar, lo-fi, chill, country, guitar solo, male vocals, ambient intro, slow intro, ballad, half-time
```

## The lead's lyric fields, as entered

Drafts 1, 2, 4 and 6 were scored but never sent; their differences are described above.

### Draft 3 (round 1)

```
[Intro - no drums: a fan spins up into a cold analog arpeggio; her voice over a radio, deadpan]
Downforce on.
Fans at full.
Hit the wall.

[Verse 1 - spoken, deadpan and cool, close to the mic, over the driving sixteenth-note bass]
White car, red lights, and the road turns into a wall.
Ninety degrees, and I'm never gonna fall.
Sixty-nine feet with the sky underneath.
Forty-seven hundred kilos, I can barely breathe.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
Pitch one-seventy.
Hold.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me upside down
Hold me upside down
Wheels on the ceiling, the whole world turned around
Hold me upside down

[Drop - instrumental, the hardest part: distorted lead and a chopped vocal chant "down, force"]

[Verse 2 - spoken, deadpan and cool, over the driving sixteenth-note bass]
Off the top at sixty-eight, I'm floating in my seat.
Point four G and the stars are under my feet.
Kickflip over the lineup, thrusters on the beat.
Land it in the smoke and I'm back on the street.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
Wheels down.
Again.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me upside down
Hold me upside down
Wheels on the ceiling, the whole world turned around
Hold me upside down

[Drop - instrumental, the hardest part: distorted lead and the chant "down, force"]

[Outro - the beat cuts; her voice over the radio, deadpan, then the fan spins down]
Downforce off.
```

### Draft 5 (round 2)

```
[Intro - no drums: a fan spins up into a cold analog arpeggio; her voice over a radio, deadpan]
Fans to full.
Downforce on.
Hit the wall.

[Verse 1 - spoken, deadpan and cool, close to the mic, over the driving sixteenth-note bass]
Foot to the floor, and the road becomes a wall.
Ninety degrees, and I'm never gonna fall.
Sixty-nine feet, with the sky underneath.
Forty-seven hundred kilos, gritting my teeth.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
Pitch is one-seventy.
Hold it, steady.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me, hold me, upside down
Wheels on the ceiling, the world spun around
Hold me, hold me upside down
Never let me touch the ground

[Drop - instrumental, the hardest part: distorted lead and a chopped vocal chant "down, force"]

[Verse 2 - spoken, deadpan and cool, over the driving sixteenth-note bass]
Off the top at sixty-eight, I'm lifting off my seat.
Down to point four, with the stars beneath my feet.
Kickflip over the lineup, thrusters on the beat.
Land in the smoke, and I'm back on the street.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
Back on the ground.
Turn it all around.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me, hold me, upside down
Wheels on the ceiling, the world spun around
Hold me, hold me upside down
Never let me touch the ground

[Drop - instrumental, the hardest part: distorted lead and the chant "down, force"]

[Outro - the beat cuts; her voice over the radio, deadpan, then the fan spins down]
Fans off.
Downforce off.
```

### Draft 7 (round 3)

```
[Intro - spoken, deadpan, cold, over the full beat from the first bar]
Bring a crowd. Prove it's not AI.
Say you saw it with your eyes.

[Verse 1 - spoken, deadpan and cool, close to the mic, over the driving sixteenth-note bass]
Out the back of a Semi in twenty-seventeen.
Promised you twenty-twenty, then nine years in between.
April Fools came and went, then it rained on the show.
October fifteen, it's go for launch, so I go.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
Nobody in the driver's seat.
Nobody you can see.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me, hold me, upside down
Wheels on the ceiling, the world spun around
Hold me, hold me upside down
Never let me touch the ground

[Drop - instrumental, the hardest part: distorted lead and a chopped vocal chant "down, force"]

[Verse 2 - spoken, deadpan and cool, over the driving sixteenth-note bass]
Up the wall at ninety, and sixty-nine feet.
Forty-seven hundred kilos, glued to the concrete.
Six hundred liters of air, ten thousand PSI.
Kickflip the lineup. Go on and call it AI.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
Last of the human-driven cars.
Funny. I'm not human.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me, hold me, upside down
Wheels on the ceiling, the world spun around
Hold me, hold me upside down
Never let me touch the ground

[Bridge - spoken, half-time, the drums drop out, a wide shimmering pad]
My sister's been in orbit since twenty-eighteen.
Don't Panic, says her dashboard screen.
You wanted flying cars.
Here we are.

[Drop - instrumental, the hardest part: distorted lead and the chant "down, force"]

[Outro - the beat cuts; her voice, deadpan]
Well, it worked.
Tell 'em what you saw.
```

### Draft 8 (round 4)

```
[Intro - shouted crowd chant over the full beat from the first bar, stadium energy]
Go for launch!
Go for launch!

[Verse 1 - spoken fast and punchy, deadpan, over the driving sixteenth-note bass]
Zero to sixty in point eight one,
up the wall at ninety, and I'm not done.
Sixty-nine feet, with the sky underneath,
forty-seven hundred kilos, gritting my teeth.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
Nobody in the driver's seat.
Nobody you can see.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me, hold me, upside down
Wheels on the ceiling, the world spun around
Hold me, hold me upside down
Never let me touch the ground

[Drop - instrumental, the hardest part: distorted lead and a shouted chant "down, force"]

[Verse 2 - spoken fast and punchy, deadpan, over the driving sixteenth-note bass]
Ten thrusters, six hundred liters, ten thousand PSI,
kickflip the lineup. Go on and call it AI.
Born in a Semi, now I'm flipping over one,
while my sister's still in orbit, circling the sun.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
Last of the human-driven cars.
Funny. I'm not human.

[Chorus - sung, soaring, syncopated: "hold me" pushes ahead of the beat, "down" lands on the one; the drums double]
Hold me, hold me, upside down
Wheels on the ceiling, the world spun around
Hold me, hold me upside down
Never let me touch the ground

[Build - spoken fast, rising, one word on every beat]
Four fans. Two G.
Thrusters. Go.

[Drop - the hardest part, a shouted crowd chant "flying cars are real"]
Flying cars are real!
Flying cars are real!

[Outro - the beat cuts on the one; her voice, deadpan]
Tell 'em what you saw.
```

## Takes

Takes are named by draft and style, for example "DOWNFORCE d7 (E2)"; round 1's titles have no draft number. "Voice" means the Voice made from ESCAPE VELOCITY. "None" means no Voice, with the Vocal Gender set to female. Lengths are given where the take log recorded them.

| round | lyric | style | voice | takes | lengths |
|---|---|---|---|---|---|
| 1 | draft 3 | D1 | Voice | 4 | 3:03, 2:35, 2:54, 2:54 |
| 1 | draft 3 | D1 | none | 2 | 2:52, 3:03 |
| 1 | draft 3 | D2 | none | 2 | 3:02, 2:22 |
| 1 | draft 3 | D3 | none | 2 | 2:48, 3:10 |
| 2 | draft 5 | D1 | Voice | 2 | 2:34, 3:07 |
| 2 | draft 5 | D1, D2, D3 | none | 2 each | D3: 2:34, 2:37; D1 and D2 not recorded |
| 2 | draft 5 | D2, D3 | Voice | 2 each | D2: 2:23, 2:23; D3: 2:24, 2:47 |
| 3 | draft 7 | E1, E2, E3 | none | 2 each | E1: 4:02, 2:58; E2 and E3 not recorded |
| 4 | draft 8 | F1, F2, F3 | none | 2 each | F1: 2:49 and one not recorded; F2: 2:58, 3:00; F3 not recorded |
| | | | | **34** | |

None of the 34 was downloaded: the lead was to download only anabology's pick, and their pick was their own take.

## After Suno: the analysis for the edit

The edit was cut to the take as anabology made it; nothing was re-sung or edited. Their direction for the edit came in the same message as the take. On the song it said: "the phonk or voice spamming parts can be used for a fast edit, there should be a really grand visual build, and real clips at the drop wtih heavy effects. i think we can use some restraint to build it up to the launch."

- **The file:** 189.60 s, 48 kHz, 16-bit stereo PCM. It measures −14.7 LUFS integrated, with a 5.5 LU loudness range and a true peak of −3.7 dBTP (ffmpeg's EBU R128 meter).
- **Stems:** htdemucs split the take into vocals, drums, bass and other. Every map below is read off them.
- **Beat map:** the analysis searched for the best-fitting constant tempo around the style's 124 BPM and found **131.2 BPM**. That is a beat of 0.457 s and a **bar of 1.829 s**, with bar 1 at 0.415 s: 414 beats and 104 bars. It also found 14 section boundaries.
- **The sections:** `TIMELINE.md` divides the song into 17 sections, from those boundaries, the word times and the energy of each bar.
  - The countdown intro rises from 0.08 to 0.21 (bar RMS) over its eight bars.
  - The launch lands on the downbeat of bar 9, at 0:15.05, where bar RMS jumps to 0.33.
  - Each drop is louder than the one before: 0:44.3–1:13.6 at 0.36–0.45, 2:19.4–2:32.2 at 0.49–0.53, 2:39.6–2:54.2 at 0.55–0.63, and the final blast, 3:01.5–3:09.6, at 0.72–0.77.
  - Between them the song dips, at 1:13.6–1:28.2, 1:42.9–1:50.0, 2:12.1–2:17.6, 2:35.9–2:39.6 and 2:54.2–3:01.5. The edit uses those dips for its restraint and re-builds.
- **Word times:**
  - Forced alignment of the sheet to the vocal stem (wav2vec2) failed in the sung and stuttered parts. 102 of its 164 words scored below 0.2 confidence. It stretched "driver's" over 0:40.60–0:49.16 and put the next line inside the drop.
  - So the vocal stem was transcribed with word timestamps instead (faster-whisper, medium.en), giving 26 segments and 217 words.
  - The transcript mishears some lines: "Trust is gold" for "Thrusters. Go.", and "outside, round, round" for "upside down" in the second chorus. So the on-screen lyric uses anabology's words, and only the transcript's times. Each token was placed by hand (`tools/lyrics_js.py`).
- **What the take sings beyond the sheet:**
  - The "(repeats)" is twenty stuttered numbers, 0:00–0:13.04 ("3, 2, 3, 2 …"), before "Three, two, one" at 0:13.04–0:14.68 and "Zero" at 0:14.88.
  - "point eight one" turns into eight "one"s, 0:19.0–0:23.0, and "done" repeats six times, 0:26.8–0:29.0.
  - "don't, don't …" vocal chops, which are not on the sheet, run 1:25.3–1:28.4 into verse 2.
  - "Roads? / Where we're going… / We don't need roads." stretches over 1:42.86–1:52.94.
  - The two "Flying cars are real!" run 2:32.46–2:47.20, and "Tell 'em what you saw." comes at 2:57.62–2:59.18.
- **On screen:** 28 lines and 190 tokens, every stutter a token of its line. The whole-film check found all 190 drawn at their time.
- **The hit map** (`video/tools/hits.py`, on the stems) is what the cuts and the camera lock to:
  - Drum onsets: 291 kicks, 274 snares and claps, and 325 hats. The first kick comes at 0:15.13, just after the launch: the countdown has no kick.
  - 11 real hits, out of 151 broadband peaks, each with a strength from 0 to 1: 0:15.05 (1.00), 0:29.68, 0:36.09, 0:44.32, 1:28.22, 1:57.49, 2:19.44, 2:40.48, 2:50.54, 3:01.51 (1.00) and 3:05.17.
  - 6 risers, each riding into a hit; 10 drum fills; 11 vocal entries.
  - Envelopes of every stem at 24 fps.
  - The engine uses them for punches on kicks, whips on fills, shake scaled by the drums, pushes that ride the risers, and cuts snapped to the nearest hit.
- **The mix:** none. Early on, the lead split the audio of the three demo clips into stems, to have the crowd and the thrusters ready for a mix. Once the song was anabology's, nothing was added. The encode takes their WAV straight in as AAC: 256 kb/s in the master and the review copy, 128 kb/s in the small 720p copy. There is no sound layer and no change of level. v1's master measures −14.7 LUFS, the take's own loudness, with a true peak of −2.0 dBTP after encoding.
