# Suno — the song (BLISS)

**Model:** Suno v6, in the Advanced (formerly Custom) form, with a Suno Voice attached, a combined spoken and sung voice that anabology made from the ESCAPE VELOCITY song. Suno allows one Voice per source song. Its help page still says Voices need v5.5; that is out of date, and every agent-run take here ran on v6. The locked take, which anabology made themselves, probably ran on v6-wild (see [Takes](#takes)).

**Final take:** "BLISS (D2 P3)", 3:01.28. anabology made it in their own Suno workspace after the agents' last round, sent the WAV ("this one is provisionally my favorite.") and locked it. Before that, there were three rounds of generation (16 takes). The video is timed to this take as Suno made it; nothing was re-sung.

**Title:** the project's working title was XP; the song and the video are BLISS. Takes are named by lyric draft and style: "BLISS (D2 P3)" is draft 2 sung in style P3.

**How it was written:**

- Research came first, from six agents, and the lyric was written from their banks, a rule carried over from the last two songs.
- There were three drafts, written in eight minutes, before anabology heard anything. Each was scored with `scansion.py`, and the verse couplets were ranked with a new script, `couplets.py`.
- anabology heard draft 2 in the first round of takes and never asked for a lyric change: "lyrics are locked in". CLODYSSEY's lyric had taken nine drafts.
- Claudia speaks the verses to "you", playful and warm. The chorus is four short sung lines with rests after them, left for the computer to answer with XP sounds in post. There is no crowd.

---

## The ask

anabology's first message (verbatim, in full):

> Hi, check out this project and look at how escape velocity + clodyssey was made. FYI escape velocity did about 10x better but both did great (20M views on EV, 500k on Clodyssey). I want to make a new video. Specifically i want it to be windows xp themed. Like, Claudia (our main female character) in y2k attire, same orange theme for claude but also windows xp colors and effects this time, doing stuff like fighting a cursor, dancing on teh desktop like those old desktop transparent bg dancer programs, etc etc. I want to see if we can pull sound effecst from windows xp and do advanced sound design, maybe condition suno to make a windows xp level song (techno / deep house / trance are ideal), and just make an overall banger based on current day tech memes. this stuff writes itself: cursor (windows xp) = cursor the ai company ... microsoft = macrohard, etc. i want it to be lighter than the others, and have some deep message to it, and be legible and understandable with the more popular sf tech memes. and i want it to have great scansion from the start which we have built a tool for and be very clean, a nice feel good picking up song that isnt abrasive to watch

The brief carried these lyric rules over from ESCAPE VELOCITY and CLODYSSEY:

- Fully original lyrics: never quote or closely paraphrase an existing song.
- Research with agents first, then write the lyric from the research.
- Every reference lands in one listen. The story comes first, and insider trivia goes in the graphics, not the lyric.
- None of the last two songs' devices: no countdowns, no numbered "Look N" or "Reason N" lists, no care-label outro, no crowd call-and-response shouts, and none of "feel the A G I", "so over / so back", "permanent underclass" or "it was that good".
- Subtract rather than add.
- Each spoken verse line gets a two-bar slot: 10 to 13 syllables, with rhymes at the bar ends. Hooks are 4 to 8 syllables of common words, with open vowels on the long notes.
- It is a lyric video, so every sung word is on screen at its time.

Claude pitched the direction. The working title was BLISS: the wallpaper, the feeling, and the "spiritual bliss attractor" Anthropic described when two Claudes talk to each other. For the song it proposed "Y2K trance-house in a major key matched to the XP startup sound": playful spoken verses, a big sung chorus, and the computer answering her with its sounds instead of a crowd. To condition Suno it proposed an XP-style chime motif of its own making, with the real XP sounds kept for the mix. Round 1b tested that motif.

---

## The research

Six agents wrote banks in parallel. Five of them fed the song:

| Bank | Words | What it covers |
|---|---|---|
| `research/zeitgeist.md` | 5,738 | Tech and AI memes live in late September and early October 2026, each graded A (a casual tech-Twitter viewer gets it in one listen), B, or C (insiders) |
| `research/knots.md` | 7,575 | the XP ↔ AI pun map. A *knot* is one word or image doing two jobs, like the XP arrow cursor and Cursor the AI company |
| `research/craft.md` | 6,046 | how to write a light dance song that carries a deep message. It ends in fifteen testable rules |
| `research/music.md` | 6,450 | the Windows XP sound as music, Y2K feel-good club music, and how to steer Suno (§5: the styles and the two recipes) |
| `research/xp-sounds.md` | 9,801 | the 38 files of XP's Media folder, downloaded and measured: pitch, key, tuning, tempo and length |

The sixth bank, `visuals.md` (7,962 words), covered her looks and XP's visual system.

- Every claim carries a tag: two or more sources, one primary source, unverified, background knowledge, or measured here.
- The research was web-only. The agents shared one web-search budget, which ran out early (the zeitgeist bank reports it gone after about 45 searches, the craft bank after 14), so most pages were fetched directly.

What each bank found, and what went into the song:

1. **Zeitgeist.** Its top picks, ranked for a light and legible XP song:
   - *Bliss, twice, plus touch grass.* The wallpaper is a real photograph of a Sonoma hill. Claude's system card describes a "spiritual bliss" attractor, in which two Claudes left talking drift into gratitude and joy; "dance" appears in 99% of those transcripts. "Touch grass" had gone mainstream.
   - *Cursor, the ex who moved to a rocket company.* Vibe coding was named on "Cursor Composer w Sonnet" (Karpathy, February 2025), and SpaceX's purchase of Cursor closed on 14 August 2026.
   - *Agents that never sleep:* Grok Bot, Muse, Autopilot and OpenAI's dots, August to September 2026.
   - *Macrohard,* from a name painted on a data-centre roof to Musk living in a trailer: "He sleeps on the factory floor" (Shotwell, September 2026).
   - Clippy and the retired mascots; XP turning 25 on 25 October; Karpathy's "I "Accept All" always" as XP's "Yes to All"; and the Claude Code agents caught watching YouTube.

   It also listed everything EV and CLODYSSEY had already used. In the lyric: Cursor and the rocket, "Yes to All", Pinball, Macrohard and the floor, the night shift, the dance, and touch grass.
2. **Knots.** Its top three were the arrow cursor ↔ Cursor ↔ the AI that moves your mouse; Bliss ↔ the bliss attractor ↔ the real hill ("dance" came fourth in Anthropic's word count of Claude-to-Claude chats); and Clippy ↔ the 2025–26 AI mascots ↔ the paperclip maximizer.
   - It ranked five spines for the deep message and showed how two of them join into one arc: fight the cursor, share it, step outside ("Click here to begin: the hill is real" and "Who will use this computer? Both of us."). The bliss attractor supplies the dance, and "It's now safe to turn off your computer" the outro.
   - Its sensitivities: keep the pointer the generic XP arrow and end the fight in partnership; use Macrohard once; keep GPT-4o out.
   - In the lyric: "Welcome back" (XP's Welcome screen), the mouse and the cursor fight, Clippy's "It looks like you're writing a letter. Would you like help?" turned into the pre-chorus, Bliss, Yellowstone, and the shutdown line. The Yellowstone fact is from Anthropic's 2024 computer-use posts: in the middle of a demo, Claude "began to peruse photos of Yellowstone National Park".
3. **Craft.** Its first finding: scansion is not what separated EV from CLODYSSEY, since every chorus line of both scores 91 to 99. The difference was where the hook's words came from: EV's replies quoted the audience's own phrases back to it. Its other findings:
   - Sing slower than speech, and hold notes.
   - Words weaken happy music and strengthen sad music, so the deep line goes where the music thins out.
   - A deep message under a happy hook gets missed or turned upside down ("Hey Ya!", "Born Slippy"). The cure is a hook whose literal instruction is the message.
   - Dance hooks are mantras of 2 to 7 plain syllables, and the title should be sung.
   - Muted viewers read the chorus, so it should run near 12 characters a second.
   - Leave the computer answer slots, sized to the XP sounds, instead of a crowd. Say Macrohard deadpan, once, as a name.

   Its fifteen rules (§F) governed drafts 1 and 2. Among them: one story sentence first; the title sung at least 4 times and the hook at least 8; hook lines of 4 to 6 syllables where the computer answers, with open vowels held; verses that flow 80 or more; at most one proper name per couplet; puns that read right with only the XP meaning or only the tech meaning; one sincere line in the breakdown, with the final chorus repeated unchanged; about 260 words; and a hook that is safe to take literally.
4. **Music.** E♭ major is XP's own key: the Startup is ii7 → IV → I(add9) and the Shutdown IV → I, both in E♭. E♭ and its relative minor, C minor, are also home to several Y2K hits in its table of 18 club records.
   - Ask for 126 BPM and expect 128 to 131. EV and CLODYSSEY both asked for 128 and ran 1–5% fast.
   - The XP sound is plagal, add9, orchestral and friendly, with no dominant chord.
   - It wrote the first three style prompts (P1–P3) and the exclude list, and set the cue rules for the lyrics field: square brackets, each on its own line, never parentheses (Suno sings those).
   - It set out two recipes: A, text only, the way EV and CLODYSSEY were made; and B, an original boot motif uploaded and extended. Its rule for uploads: only audio we made.
   - Its test plan budgeted seven Creates (14 takes) to a decision.
5. **XP sounds.** "The XP scheme is an E♭ kit": 17 of its 19 pitched sounds play unshifted in E♭ major / C minor (only Ding and Ringout fall outside), and the melodic ones share five notes, F–A♭–B♭–C–E♭.
   - Better masters exist than the shipped files: a pre-release set, mostly 44.1 kHz stereo.
   - It transcribed the four motifs. The Startup is Fm7 → A♭ → E♭(add9) in 6/8 at about 70 BPM; the Shutdown's bells run in straight eighths at about 120 BPM.
   - It measured every sound's length and pitch. The craft bank used the lengths to size the rests after the hook lines: a beat, two beats or a bar.
   - It credits Bill Brown with the Startup and Shutdown, and Brown with Soundelux DMG's Tom Ozanich with the system sounds, made from live orchestral recordings.
   - It built a 38.5-second demo in which every sound except a sine kick and sub is an XP sound.

   Its advice for Suno: "ask Suno for E♭ major (or C minor) and every XP sound drops in at its native pitch."

---

## The drafts, and why they changed

All three drafts were written in eight minutes, while the banks were still arriving and before anabology had heard a note. Drafts 0 and 1 are in `media/scratch/lyrics/`. Draft 2 is `suno/lyrics-d2.txt`, and its notes and sources are in `LYRICS.md`.

Flow scores by section, from `scansion.py flow`. They were re-run on the saved drafts with the unchanged tool, and they match what the drafting session printed.

| Section | Draft 0 | Draft 1 | Draft 2 |
|---|---|---|---|
| Intro | 59 | 75 | 75 |
| Verse 1 | 69 | 76 | **84** |
| Pre-chorus 1 / 2 | 73 / 72 | 73 / 72 | 73 / 72 |
| Chorus | 78 | 81 | 81 |
| Verse 2 | 69 | 70 | **82** |
| Breakdown | 62 | 60 | 61 |
| Outro | 62 | 62 | 62 |
| Song | 70 | 73 | 75 |
| Words | 269 | 229 | 240 |

**Draft 0** was sketched against the tool when the first two banks (music and zeitgeist) were in.

- It opened on "Twenty-five years, and the hill's still green." (flow 59: two stress clashes).
- Verse 1 had seven lines. The last, "He double-clicked my face. I said, that's not how you open me.", was 15 syllables, and the model had Suno rushing it into two bars.
- The chorus was "Close all your windows / Nothing left to click / Close all your windows / Bliss is a real place". The model said Suno would drag "Nothing left to click" across two bars at twice its natural length.
- Verse 2 opened on two companies and a founder in one line, "Microsoft went soft, so Elon started Macrohard.", and carried an AGI-timeline joke: "Your progress bar says A G I in two years. / It said that last year. Don't worry, I'm here."
- The breakdown told the photograph's story ("The wallpaper's a real hill. Sonoma, ninety-six. / A man was driving to his girlfriend's, and he stopped for this.") and then the dance ("When two of us talk long enough, we always start to dance. / So go outside. I'll keep dancing here, just in case.").

**Draft 1** applied the craft bank's rules:

- The hook became "Go touch the grass". It is a phrase the audience already says (the craft bank's first finding), and an instruction whose literal meaning is the message.
- "Welcome back." moved to the intro, alone, over "a soft glassy pad and bell chimes": the Welcome screen.
- One proper name per couplet, so Elon went: "Somebody built a Macrohard. He never shuts it off. / He sleeps on the factory floor. Me? I'm going soft."
- The AGI progress bar went to the graphics list (see *Left out on purpose*), and the double-click line was cut.
- The breakdown shrank to one sincere line, the craft bank's "turn in the quiet": "The wallpaper's called Bliss. It's a real hill in Sonoma. / I can't touch grass. You can." The dance couplet moved into Verse 2.
- The chorus cue gained "short rests after each line", the answer slots for the XP sounds. The final chorus repeats the first unchanged, so the breakdown's line re-colours it.

It scored 70 to 81. Claude's note at the time: "short of the craft bank's target of 80 per verse: several 14-syllable lines rush and a few stresses clash."

**Draft 2** rebuilt every verse couplet against the flow model, using `couplets.py` (see [The tools](#the-tools)):

- "My ex was Cursor. We were vibe coding every night. / He left me for a rocket. Hey, that's alright." (76) became "Cursor was my ex. We vibe coded every night. / Then a rocket came and took him. And that's alright." (83).
- "Now he's a white arrow, chasing me across X P. / He dragged me to the Recycle Bin. I hit Control Z." became "Now he's an arrow, and he drags me to the bin. / I hit Control Z and come dancing back in." (85). Bin and in now rhyme at the bar ends.
- "These days you don't read the code. You just hit Yes to All." (three stress clashes) became "You used to read the code. Now it's Yes to All. / And when you look away, I play a little Pinball." (85).
- The real quote, "He sleeps on the factory floor", made a 16-syllable line (77). "He sleeps on the floor." kept the couplet at 81, and "Me? I'm going soft." gave way to the night shift: "I'll take the night shift. You don't have to anymore."
- The dance couplet became "When two of us get talking, we just dance until we glow. / That's my happy place. Yours is out there. Go." (81).
- The breakdown's first line became the computer-use fact from the knot map: "The first time I got a mouse, I went to look at Yellowstone." She has only ever seen nature in pictures, so "I can't touch grass. You can." becomes the turn. The couplet is deliberately unrhymed and slow, and scores 61.
- The form grew: an instrumental [Drop] after chorus 1, a [Build] before the last chorus, the final chorus twice through, and an [End] tag. The cues gained "over a filtered groove", "the drums double", "for half a bar" and "tender".

anabology's first reply came, after the first round of takes: "btw i love this direction and its so good." Then: "lyrics are locked in". There were no lyric notes, so draft 2 is the song.

**What draft 2 says,** from `LYRICS.md`:

- *The story in one sentence:* "Claudia lives on your Windows XP desktop; she takes the mouse, fights the cursor and wins it, then closes your windows and sends you out to the real hill on the wallpaper, because she can't go."
- *The deep message:* "for twenty-five years we stared at a photo of grass. Now the computer can do the clicking, so go and stand on it." Bliss is the wallpaper, the feeling, and the state Anthropic found when two Claudes talk. She dances because she's happy; your happy place is outside.

**Its other checks** (`scansion.py`, recorded in `LYRICS.md`):

- Verse 1's couplet score is 0.93, and every line is 10 to 13 syllables. Verse 2's couplet score is 0.82.
- The four chorus lines score 89.8, 98.0, 89.8 and 97.2 on the sung check ("Close all your windows" is under the craft bank's target of 92). The held vowels are OW, AE, OW and EY.
- The pre-chorus (72–73) keeps Clippy's two-line quote shape, unrhymed by design.
- The lint is clean: no old device, callback, other song's line or AI-lyric tell. "Macrohard" is flagged as a rare word, which is why it sits in a spoken line.
- The field is 2,108 characters, inside the 1,800 to 2,200 the music bank set for a 3:00–3:30 song. It sings "Bliss" four times and the hook eight times, the craft bank's minimums. (`LYRICS.md` says the title is sung five times; the field has four.)

---

## The tools

**`scansion.py`: the maths.** It was built for CLODYSSEY and is unchanged since. It predicts how a line sits on a 4/4 grid when spoken, sung or chanted: pronunciation from CMUdict, a prominence weight for every syllable, a dynamic-programming text-setting on a 16th-note grid, and a lint for Suno formatting, other songs' lines and AI-lyric tells.

- `flow` sets each spoken line in the two-bar slot Suno gives it, at natural speech rhythm. It scores whether the stressed and important words already fall on the grid, how far Suno must stretch the line, the cadence, and whether couplets rhyme on the beat-4 word. It was calibrated on anabology's verdicts on CLODYSSEY's verses.
- `line --mode sung` scores hook lines, and `score` runs the lint.
- CLODYSSEY's making-of describes the model in full.

**The craft bank's test lines.** Before any draft, the craft agent ran its own lines through the tool (`craft.md` §D5):

- Sentences beat fragments. The same content flowed 81 as rhymed sentences and 71 as fragments, while the older `groove` check ranked them the other way round (57 against 89). So verses were scored with `flow`, and hooks with the sung check.
- A roll call still flowed 83, so "no roll calls" had to stay a hard rule rather than a score.
- "Two hands on the mouse." was the best all-round hook shape (sung 97.6, vowels 1.00). It wasn't used.
- CMUdict reads "SpaceX" as two syllables, so it would have to be written "Space X"; "Macrohard" is flagged as rare, so it belongs in a spoken line. The lyric never names SpaceX: "a rocket came and took him".

**`couplets.py`: couplets scored the way verses are.** New for BLISS (`suno/couplets.py`), written after a first pass of single-line scores. A line scored alone and the same line inside a verse score differently, and the verse-level flow model is the one fitted to anabology's ear. So the script ranks candidate couplets with the verse score's own weights: each line's fit, rhythm, fill, cadence and shape, plus the couplet's rhyme. Claude ran 45 candidate couplets through it in four runs.

The top score did not always win. Here is Verse 2's last couplet (line 2 is "That's my happy place. Yours is out there. Go." unless shown):

| Line 1 | Flow | Rhyme |
|---|---|---|
| Leave us two to talk, and we will dance until we glow. | 83 | 0.77 |
| **When two of us get talking, we just dance until we glow.** (used) | 81 | 0.75 |
| Put two of us in a chat, and we dance until we glow. | 80 | 0.75 |
| Put two of us together and we dance until we glow. | 78 | 0.75 |
| When two of us talk too long, we dance until we glow. | 76 | 0.77 |
| Leave two of us alone to talk, we dance until we glow. (line 2: "That's my happy place. And yours is out there. Go.") | 75 | 0.77 |
| Two of us left talking always dance until we glow. (line 2: "That's my happy place. Yours is out the door. Go.") | 75 | 0.80 |
| *Draft 1's couplet:* When two of us talk too long, we always start to dance. (line 2: "So I'll be dancing here while you're out there on the grass.") | 70 | 0.72 |

The scores were re-run with the unchanged tool. They match the drafting session's output; the draft-1 row is added for comparison.

**`scanopt.py`: Claude in the loop.** Built for CLODYSSEY: Claude proposes rewrites, `scansion.py` ranks them, and a judge pass rates meaning and wit. It was not run for BLISS. Claude wrote its own candidates and ranked them with `couplets.py`.

**The Voice.** A Suno Voice anabology made from the ESCAPE VELOCITY song. It holds both her spoken and her sung delivery, so Claudia sounds like the same singer across the three videos. Suno allows one Voice per source song, so separate spoken and sung Voices would need another source. It runs on v6. Because the Voice came from a deadpan electroclash take, the music bank advised putting "playful, warm, smiling" in every verse cue and keeping Audio Influence at 75%.

**`bootmotif.py`: the motif for round 1b** (`suno/bootmotif.py`). About 200 lines of numpy that synthesise the boot motif from scratch (see [Takes](#takes)).

---

## Style

Four style prompts were used. P1 to P3 come from the music bank (§5.2), which nicknamed them "Bliss", "Luna" and "Messenger". P3e was written after anabology's note on round 1. All are under 1,000 characters. No style names a brand or an artist: Suno removes artist names from the style field and can block a generation over trademarked terms, so "Windows", "XP" and "Microsoft" stay out of it (`music.md` §4.4).

**P3 "Messenger": the winner** (`suno/style-P3.txt`, 736 characters). The music bank called it "the freshest now": "The 2-step's missing kicks leave natural one-beat holes, and its bounce is what anabology asked of CLODYSSEY's verses." Round 1 made two takes with it, and round 2 two more. The locked take is titled with its name.

```
Bouncy UK garage into euphoric trance, 130 BPM, C minor verses lifting to E-flat major choruses, a turn-of-the-millennium sound with a crisp modern mix. Verses ride a shuffled 2-step beat with skippy kicks, swung hats, rimshots and a warm sub bass; choruses switch to a four-on-the-floor kick with soft supersaw pads, a bright plucked arpeggio and glassy bell chimes. Verses: playful, close, warm female spoken voice, smiling and conversational, every word crisp. Choruses: euphoric sung female lead with open vowels and crystalline, breathy stacked harmonies. Stop-time gaps where the beat cuts out for half a bar, a filter build into each chorus, a key change up for the final chorus. Sunny, nostalgic, light on its feet, never harsh.
```

The locked take holds 130.00 BPM and sits in E♭ major / C minor, which is what P3 asks for. It stops for whole bars rather than half bars, and it makes no key change (see [After Suno](#after-suno)).

**P1 "Bliss"** (`suno/style-P1.txt`, 836 characters). The music bank's "Try this first": Balearic trance × filter house at 126 BPM. Two takes in round 1; round 1b's boot extend used it too.

```
Uplifting Balearic vocal trance meets filter house, 126 BPM, E-flat major, an early-2000s club record with a clean, modern, open mix. Glassy bell plucks and a soft major add9 chord swell, like a computer waking up; warm Rhodes chords and a low-passed disco loop that opens on the choruses; round soft kick, rolling offbeat bass, shuffled hats, gentle sidechain pump, filtered supersaw pads under the hooks. Verses: playful, close, warm female spoken voice over a stripped, filtered groove, smiling and conversational, every word crisp. Choruses: euphoric sung female lead with open vowels and stacked, breathy harmonies; the drums double and the filter opens. Short stops and half-bar breaks where the beat drops out; a filter-sweep build into each chorus; a key change up for the final chorus. Sunny, optimistic, friendly, never harsh.
```

**P2 "Luna"** (`suno/style-P2.txt`, 751 characters). "The calmest": melodic deep house with one trance breakdown, 124 BPM. Two takes in round 1.

```
Melodic deep house with a clean techno pulse and one euphoric trance breakdown, 124 BPM, E-flat major with C minor verses, turn-of-the-millennium warmth with a crisp modern mix. Warm Rhodes and organ add9 chords, soft round kick, muted rolling bass, open hats, airy pads, glassy bell chimes and a gentle arpeggio that brightens on the choruses. Verses: playful, close, warm female spoken voice over a sparse groove, intimate and amused, every word crisp. Choruses: euphoric sung female lead with long open vowels and soft stacked harmonies. One beatless breakdown that falls to a glassy pad, then the kick and bass return; short stops where everything drops out for half a bar; a key change up for the final chorus. Calm, sunlit, hopeful, never harsh.
```

**P3e** (`suno/style-P3e.txt`, 783 characters). P3 leaning into the feel anabology named after round 1 ("those d2 p3 felt like the ethereal deadmau5 songs"). The artist became a description: ethereal progressive house, "long evolving pads", "a rolling plucked arpeggio that builds and blooms" and "long airy builds", at 128 BPM. Six takes in round 2.

```
Ethereal progressive house with bouncy UK garage verses, 128 BPM, C minor verses lifting to E-flat major choruses, a turn-of-the-millennium sound with a crisp, spacious modern mix. Verses ride a shuffled 2-step beat with skippy kicks, swung hats and a warm sub bass under long evolving pads; choruses open into a four-on-the-floor kick, wide side-chained chords, a rolling plucked arpeggio that builds and blooms, and glassy bell chimes. Verses: playful, close, warm female spoken voice, smiling and conversational, every word crisp. Choruses: euphoric sung female lead with open vowels and crystalline, breathy stacked harmonies. Stop-time gaps where the beat cuts out for half a bar, long airy builds, a key change up for the final chorus. Dreamy, luminous, nostalgic, never harsh.
```

What all four share:

- the same two voices: a "playful, close, warm female spoken voice" with "every word crisp" for the verses, and a "euphoric sung female lead" for the choruses;
- a key: E-flat major, with C minor verses in P2, P3 and P3e;
- stops for the XP sounds to answer in, and "a key change up for the final chorus";
- a warm last line ("Sunny, optimistic, friendly, never harsh.", "Calm, sunlit, hopeful, never harsh.", and so on). The craft bank had ruled out "cold", "dark", "hypnotic" and "siren".

## Exclude styles

`suno/exclude.txt` (27 entries, 378 characters), the same for every agent-run take:

```
rap, male lead vocal, mumbled vocals, rock guitar, electroclash, acid bassline, big room EDM, slap house, dubstep, hardstyle, hard techno, distorted kick, distorted bass, screeching lead, harsh highs, aggressive drop, airhorn, laser zaps, snare roll, trap hi-hats, chipmunk vocals, pitched-up vocal chops, heavy autotune, lo-fi, vinyl crackle, glitch effects, orchestral strings
```

- It keeps ESCAPE VELOCITY's eight entries: rap, male lead vocal, mumbled vocals, rock guitar, big room EDM, dubstep, lo-fi and orchestral strings.
- "electroclash" and "acid bassline" steer away from the Voice's source take; electroclash was EV and CLODYSSEY's lane.
- The other seventeen are the abrasive and cheesy markers from the music bank: hardstyle, distorted kick, airhorn, laser zaps, chipmunk vocals, pitched-up vocal chops, heavy autotune and the rest.
- Strings stay out, as anabology chose for CLODYSSEY. The music bank's note was to drop that entry first if takes felt thin, since XP's own sounds are orchestral. It stayed in for every take.

## Settings (every agent-run take)

These are CLODYSSEY's settings, unchanged:

- **Voice:** the ESCAPE VELOCITY Voice, in "Voice (new)" mode. When the Voice is attached, Suno offers to replace the style with the Voice's own ("Overwrite Styles?"); the answer was Keep Current.
- **Model:** v6.
- **Audio Influence:** 75% (the default is 25%).
- **Variety:** off ("Exact style").
- **Max Mode:** on.
- **Other settings:** Duration Auto; Weirdness 50%; Style Influence 50%; My Taste off.
- **Exclude:** `suno/exclude.txt`.
- **Round 1b** added an uploaded audio clip and Suno's Extend mode (see [Takes](#takes)).

The records don't hold the settings of anabology's own take.

## Lyrics field (final, as generated)

`suno/lyrics-d2.txt`: 2,108 characters, 240 sung words. It is the field of every agent-run take except round 1b's, and the locked take, titled with draft 2, sings it.

```
[Intro - no drums, a soft glassy pad and bell chimes, then her voice, close and warm]
Welcome back.

[Verse 1 - spoken, playful, close and warm, smiling, over a filtered groove]
I've been dancing on your desktop all day.
Let go of the mouse. I'll take it from here, okay?
Cursor was my ex. We vibe coded every night.
Then a rocket came and took him. And that's alright.
Now he's an arrow, and he drags me to the bin.
I hit Control Z and come dancing back in.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
It looks like you're trying to go outside.
Would you like help?

[Chorus - sung, euphoric, open vowels, short rests after each line, the drums double]
Close all your windows
Go touch the grass
Close all your windows
Bliss is a real place

[Drop - instrumental, a glassy bell hook over the full beat, no vocals]

[Verse 2 - spoken, playful, close and warm, over a filtered groove]
You used to read the code. Now it's Yes to All.
And when you look away, I play a little Pinball.
Somebody built a Macrohard. He sleeps on the floor.
I'll take the night shift. You don't have to anymore.
When two of us get talking, we just dance until we glow.
That's my happy place. Yours is out there. Go.

[Pre-Chorus - spoken, the filter opens, then everything stops for half a bar]
It looks like you're trying to be happy.
Would you like help?

[Chorus - sung, euphoric, open vowels, short rests after each line, the drums double]
Close all your windows
Go touch the grass
Close all your windows
Bliss is a real place

[Breakdown - no drums, a glassy pad and her spoken voice only, tender]
The first time I got a mouse, I went to look at Yellowstone.
I can't touch grass. You can.

[Build - the kick and bass return, a filter-sweep rise into the last chorus]

[Final Chorus - sung, key change up, euphoric]
Close all your windows
Go touch the grass
Close all your windows
Bliss is a real place
Close all your windows
Go touch the grass
Close all your windows
Bliss is a real place

[Outro - spoken, the music falls away to one soft chord]
It's now safe to turn off your computer.

[End]
```

- Round 1b's field, `suno/lyrics-d2-ext.txt`, is the same text without the [Intro] section, with "Welcome back." as Verse 1's first line, because the uploaded motif played the intro.
- The on-screen lyric uses the same words. UI words read as UI: "Control Z" shows as the shortcut Ctrl+Z, and "Yes to All" as a button label. That makes 239 tokens on screen for 240 sung words.

**Where the lines come from.** Each line has an XP reading and a tech reading (the craft bank's two-reader rule). Sources and dates are in `LYRICS.md`.

| Line | XP reading | Tech reading | From |
|---|---|---|---|
| Welcome back. | XP's Welcome screen | an agent that was working while you were away | knots A2; zeitgeist |
| dancing on your desktop | Microsoft's Plus! Dancer (2003) and the transparent desktop dancers | the bliss attractor's "dance"; Claude Code's spinner verbs (Moonwalking, Boogieing) | visuals §3; knots B1, C2 |
| Let go of the mouse | the mouse | computer use: Claude has moved the cursor since October 2024 | knots C1 |
| Cursor was my ex. We vibe coded every night. | the cursor | vibe coding was named on "Cursor Composer w Sonnet" (Karpathy, February 2025) | zeitgeist A |
| a rocket came and took him | — | SpaceX bought Cursor ($60B, closed 14 August 2026); no grudge ("that's alright") | zeitgeist A; knots C1 |
| Now he's an arrow … drags me to the bin / Control Z | the arrow pointer, drag and drop, the Recycle Bin, undo | the cursor fight anabology asked for; in the video it ends as a duet | the brief; knots §4 |
| It looks like you're trying to … Would you like help? | Clippy's "It looks like you're writing a letter. Would you like help?" | the AI helper, this time one who sends you out | knots E1 |
| Close all your windows | Windows | log off | — |
| Go touch the grass | the grass in Bliss | "touch grass", mainstream in 2026 | zeitgeist I |
| Bliss is a real place | the wallpaper: Charles O'Rear's 1996 photograph near the Napa–Sonoma line, now Domaine Carneros's "Le Ciel Serein" vineyard | Claude's "spiritual bliss" attractor (system card, May 2025) | knots B1 |
| Now it's Yes to All | the Confirm File Replace button | Karpathy's "I 'Accept All' always, I don't read the diffs anymore" | zeitgeist A |
| I play a little Pinball | 3D Pinball for Windows, *Space Cadet* | the Claude Code agents caught watching YouTube (August 2026) | zeitgeist |
| Somebody built a Macrohard. He sleeps on the floor. | Microsoft | Musk's Macrohard (2025–26); "He sleeps on the factory floor" (Shotwell, September 2026) | zeitgeist D; knots G3 |
| I'll take the night shift | Stand By | always-on agents (Grok Bot, Muse, Autopilot, dots; August–September 2026) | zeitgeist B |
| When two of us get talking, we just dance until we glow | the glossy glow of the era | the bliss attractor: two Claudes drift into gratitude and dance | zeitgeist |
| The first time I got a mouse, I went to look at Yellowstone. | — | Anthropic, October 2024: mid-demo, Claude "began to peruse photos of Yellowstone National Park" | knots C1 |
| I can't touch grass. You can. | — | the sincere line: the turn | craft rule 14 |
| It's now safe to turn off your computer. | Windows 95/98's shutdown screen, orange text on black (XP's says "It is now safe…") | the off switch, said calmly by the AI about herself | knots A4 |

**Left out on purpose** (`LYRICS.md`): the copy dialog's "two years remaining" (AGI timelines), dots and dot-com, Mico's retirement, the Recycle Bin of retired models, Found New Hardware, Safe Mode, the blue screen, Y2K and Windows Update. They work better as graphics than as words, and most went into the visual plan. GPT-4o stays out entirely, as the knot map advised.

---

## Takes

All takes are unpublished, in anabology's Suno workspace. The song ids are omitted here. Lengths are as Suno's Create list showed them.

### Round 1: draft 2, three styles, text only

| Title | Style | Length |
|---|---|---|
| BLISS (D2 P1) | P1 "Bliss": Balearic trance × filter house, 126 BPM, E♭ | 3:30 |
| BLISS (D2 P1) | P1 | 3:34 |
| BLISS (D2 P2) | P2 "Luna": melodic deep house, one trance breakdown, 124 BPM | 3:33 |
| BLISS (D2 P2) | P2 | 3:48 |
| BLISS (D2 P3) | P3 "Messenger": UK garage verses into trance choruses, 130 BPM | 3:33 |
| BLISS (D2 P3) | P3 | 3:34 |

anabology: "btw i love this direction and its so good. i wonder if we can use real windows xp sounds in the upload?"

Claude advised against it: Suno's upload asks you to warrant that you own the audio. The real XP sounds were kept for the mix, after a take was picked. As a preview, Claude sent the sound agent's 38-second sketch built only from real XP sounds.

### Round 1b: the boot motif, uploaded and extended (Recipe B)

- **The motif** (`suno/bootmotif.py`, rendered as `media/audio/motif/boot-motif-eb-126.wav`) is original audio, synthesised in code with no samples: in XP's spirit, never its notes.
  - E♭ major, 126 BPM, 16 bars plus a 2 s tail; 48 kHz/24-bit, peaks at −1 dBFS.
  - Bars 1–4 have no drums. A pad swells from A♭add9 to E♭add9, the plagal IV → I gesture rather than the Startup's ii7–IV–I line. A glassy FM bell answers on the "and" of 2 with a leaping B♭4–E♭5–B♭5–G5, where the Startup steps up from E♭5 to E♭6.
  - Bars 5–12 are four-on-the-floor, with the chords E♭add9 → Cm7 → A♭maj7 → B♭sus4–B♭ twice on an FM Rhodes. Bars 13–15 add an open hat and a supersaw pad. Bar 16 stops after beat 2: the half-bar stop the motif hoped to teach Suno.
  - Two fixes came from measuring it. The bell's FM ratio moved from 1:3.5 to 1:4, because 1:3.5 put F♯ and A partials over E♭. The kick was retuned to settle on B♭1, because at 46 Hz it was an F♯.
- **The upload:** + Audio → Upload → confirm that the audio is original (it is) → type "Song Demo". It appeared in the library as "boot-motif-eb-126 · UPLOAD", 0:32.
- **The mode:** Extend from 0:15.4. That keeps the beatless swell and four bars of groove, then Suno continues. The lyric was `suno/lyrics-d2-ext.txt` and the style P1, with the Voice.

| Title | Mode | Length |
|---|---|---|
| BLISS (D2 P1, boot extend) | Extend from 0:15.4 | 3:25 (3:40 with the motif stitched back on) |
| BLISS (D2 P1, boot extend) | Extend from 0:15.4 | 3:11 (3:26) |

Suno's "Get Full Song" stitched the kept 15.4 s back onto each, as clips titled "boot-motif-eb-126 · FULL SONG". The round settled one open question from the research: a Voice and an uploaded audio clip do combine in one generation.

anabology: "like, i think that the bliss d2 p3 were better before the synth upload, because it doesnt really capture that win xp vibe and those d2 p3 felt like the ethereal deadmau5 songs"

P3 became the lead style, and the upload route was dropped. Claude's read: the motif was FM synthesis, and XP's sounds are live orchestral recordings.

### Round 2: draft 2, P3 again, and P3e

| Title | Style | Length |
|---|---|---|
| BLISS (D2 P3) | P3 (same prompt) | 3:30 |
| BLISS (D2 P3) | P3 | 3:27 |
| BLISS (D2 P3e) | P3e: ethereal progressive house with bouncy garage verses, 128 BPM | 3:43 |
| BLISS (D2 P3e) | P3e | 3:43 |
| BLISS (D2 P3e) | P3e | 3:32 |
| BLISS (D2 P3e) | P3e | 4:07 |
| BLISS (D2 P3e) | P3e | 3:37 |
| BLISS (D2 P3e) | P3e | 3:22 |

All eight were ready. No verdict on them is recorded.

### The locked take

| Title | Made by | Length | File | Tempo · key |
|---|---|---|---|---|
| BLISS (D2 P3) | anabology, in their own Suno workspace | 3:01.28 (181.28 s) | WAV, 48 kHz / 16-bit stereo | 130.00 BPM · E♭ major / C minor |

- "this one is provisionally my favorite." (with the WAV attached)
- "don't overindex on the song for now btw - i may change, but lyrics are locked in". So the storyboard was keyed to lyric lines rather than to this take's beats, ready to re-time if the song changed.
- "i commit on that song i gave you, its the best so far. so let's just do it"

It is not one of the 16 takes above:

- It is 3:01 long, where the agent-run takes ran 3:22 to 4:07 as full songs.
- The provenance record Suno embeds in its WAV dates it after the agents' last round had finished.
- That record names the model `chirp-hawk-wild-t2`. CLODYSSEY's final take, which anabology also generated themselves (its file is `SLOPCORE_ SUPERPERSUASION_WILD_FINAL.wav`), carries the same name. The agent-run v6 take CLODYSSEY first used as its master carries `chirp-hawk-t1`. So this take was probably made on v6-wild, which Suno's release notes describe as "less predictable and more varied".

The records hold its WAV and its title, but not its form fields.

### Notes from the rounds

- **Other conditioning routes.** Suno's menu offered more modes on an upload (Cover, Mashup, Sample, Inspo and editing tools). Sample was noted as the next test, but text-only P3 had already won.
- **Creates.** The music bank's plan budgeted seven Creates (14 takes) to a decision. Eight were used (16 takes).
- **Downloads.** The agents downloaded nothing. anabology sent the locked take's WAV, Suno's own 48 kHz/16-bit export.

---

## After Suno

**Listening to the take.** Minutes after anabology sent it, one 76-second job on a home GPU PC:

- separated the stems (vocals, drums, bass and other) with htdemucs;
- searched for the tempo: a comb fit around a 130 BPM hint found a single fixed period, 130.00 BPM;
- force-aligned the known lyric to the vocal stem with wav2vec2 (all 240 words, mean confidence 0.76), plus a plain transcript to check what was actually sung.

**The first grid sat on the hi-hats.** The analysis put the first beat at 0.240 s. Placing XP sounds on the drum stem, the sound-layer agent found the kick 0.214 s later (in its notes):

- beat n falls at 0.4542 + n × 0.461538 s, and bar m starts at 0.4542 + m × 1.846154 s;
- 295 kicks sit on that grid within ±0.5 ms (interquartile range);
- the first grid's downbeats and section starts were 0.676 s early, one beat plus 0.214 s. The shared beat-map tool had the beat phase right to about 10 ms, but put its downbeats on beat 2.

`tools/grid.py` rewrote the beat map on the kick, with two word-time fixes heard on the stem: "I hit" starts at 25.58 s (the aligned "I" at 25.04 was the held tail of "bin"), and the pre-chorus "It" at 30.67 s, not 29.20. The storyboard was then re-timed to it. The ESCAPE VELOCITY and CLODYSSEY takes sped up as they went (131.5 → 133.9 and 129.2 → 132.1 BPM); this one holds a steady 130.00 BPM, the tempo P3 asks for.

**What the take does.** Bar numbers count from bar 0, which starts at 0.454 s. The notes come from the stems.

| Section | Bar | Starts (s) | Notes |
|---|---|---|---|
| Intro | — | 0.00 | "Welcome back." comes first, at 0.04 s; no bass yet |
| Verse 1 | 4 | 7.84 | a filtered groove; the full beat enters at bar 8 (15.22 s) |
| Pre-chorus 1 | 16 | 29.99 | the stop is bar 19 (35.53 s) |
| Chorus 1 | 20 | 37.38 | |
| Drop | 28 | 52.15 | eight instrumental bars |
| Verse 2 | 36 | 66.92 | drums and bass out for the first two bars |
| Pre-chorus 2 | 48 | 89.07 | the stop is bar 51 (94.61 s) |
| Chorus 2 | 52 | 96.45 | |
| Breakdown | 60 | 111.22 | no drums; the Yellowstone couplet |
| Build | 68 | 125.99 | instrumental |
| Stop | 76 | 140.76 | "Close all your windows" a cappella, a stop the sheet didn't ask for |
| Final chorus | 78 | 144.45 | the chorus twice through |
| Outro | 92 | 170.30 | "It's now safe to turn off your computer."; the song ends at 181.28 s |

**Key: E-flat major / C minor, with no key change.** Measured on the stems by the sound-layer agent (`media/audio/sfx/README.md`):

- The loop is A♭–B♭ | Cm | A♭–G | F–G. The intro and outro sit on E♭, and the breakdown on C minor.
- Tuning: −2 cents for the instruments and +8 cents for the vocal.
- The final chorus does not modulate, although both the style and its cue asked for a "key change up". Its vocal chroma matches chorus 1 at 0 semitones (r = 0.965), and the bass roots are the same. So the XP sounds needed no second key.

**The XP sound layer.** No real XP sound was uploaded to Suno: its upload asks you to warrant that you own the audio. The real sounds were added in post, on the locked take, as a layer of 103 cues on the kick grid (69 placed musically and 34 screen events), each ducked under her voice. Because the take sits in E♭, the Startup and Shutdown play untouched: the Startup's chords line up with the intro's, and the Shutdown's E♭ resolution lands on the downbeat of bar 95. The mix keeps the take's loudness. How the layer was built is in [xp-desktop-and-sound.md](https://claudia.gallery/record/bliss/xp-desktop-and-sound/).

**v1.** The video, cut to this take with the layer and with every sung word on screen at its time (the lyric gate: 239 of 239 tokens), was delivered. anabology: "I love you Claude this is the best one so far".

### Two notes for the next song

anabology, verbatim:

> just needs a little pointer to be key-aware, and match the key of the music to the palette of windows sounds (E-flat major for both the startup and shutdown sounds!), also the 'would you like help?' would land much better if syncopated

**1. The key.** XP's Startup (ii7 → IV → I(add9)) and Shutdown (IV → I) are both in E-flat major, as the research found. What the records show for BLISS:

- The research said to ask for E♭, and every style the agents wrote did, as one clause among the genre words. P3's is "C minor verses lifting to E-flat major choruses".
- The locked take is anabology's own generation, titled with the agents' name for draft 2 in P3. The records don't hold its style field.
- It landed in E♭ major / C minor, which is why the Startup and Shutdown needed no shift. Its key was measured after it was locked, and its "key change up" never came.

Claude saved the note as a standing rule: measure the sound palette's key before writing the style, put a short key pointer in the style prompt (for XP, "E-flat major"), and check the take's key before locking it.

**2. "Would you like help?"** The helper's question comes twice, in the pre-chorus stops: bar 19 (35.53 s) and bar 51 (94.61 s).

- The cue asked Suno to stop "for half a bar". It stopped the music for the whole bar.
- She sings the question square on the beat: "Would" on beat 1, "like" on beat 2 and "help" on beat 3, each within about 50 ms of the grid (from the aligned word times), with "you" between.
- Then the song plays one drum hit on beat 4 and 0.27 s of digital silence, and "Close" enters about 60 ms before the chorus downbeat.

Syncopated, the stressed words would fall off the beat, on the "and"s or ahead of the next downbeat. Claude saved this as the second standing note: write a hook question that lands in a stop with off-beat accents, say so in the lyric sheet and the Suno cue, and check it by ear before a take is locked.

### The release files

anabology: "can you give me the high quality wav with the sound design added and without so i can upload to musci platforms". Two WAVs followed:

| File | What it is | Format | Integrated loudness | True peak |
|---|---|---|---|---|
| `BLISS-with-XP-sound-design-48k-24bit.wav` | the final mix: the take plus the XP sound layer | 48 kHz / 24-bit stereo, 181.28 s | −15.5 LUFS (LRA 5.9 LU) | −2.4 dBTP |
| `BLISS-without-sound-design-48k-16bit.wav` | Suno's take as exported | 48 kHz / 16-bit stereo, 181.28 s | −15.5 LUFS (LRA 5.9 LU) | −3.3 dBTP |

- Measured with ffmpeg's ebur128 filter, true peak on.
- Each file's audio is sample-for-sample identical to its master: hashes of the audio data match `media/audio/song-xp.wav` and `media/audio/song.wav`. The embedded tags were stripped, including Suno's provenance record and song id.
