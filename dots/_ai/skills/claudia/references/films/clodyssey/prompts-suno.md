# Suno — the song (CLODYSSEY (SUPERPERSUASION))

**Model:** Suno v6, custom mode, with a Suno Voice attached, a combined spoken and sung voice that anabology made from the ESCAPE VELOCITY take. Suno allows one Voice per source song. Suno's help page says Voices need v5.5, but that is out of date: every take here ran on v6.

**Final take:** anabology generated it themselves from the final lyric field below and sent the WAV (`SLOPCORE_ SUPERPERSUASION_WILD_FINAL.wav`, 3:09.7). Before that, there were 11 rounds of generation (50 takes, from draft 2 to draft 9). On day 2, after the video was approved, anabology re-sang one word, "Superpersuasion", in Suno's editor. The video is timed to that export (191.58 s); see [The last fix](#the-last-fix-superpersuasion-re-sung).

**Title:** the song file keeps its working title, SLOPCORE: SUPERPERSUASION. The video was retitled on day 2 (anabology: "i want to call this the Cloddysey - that can be the title text, and in parenthese it can be (SUPERPERSUASION)").

**How it was written:**

- Research came first, from nine agents, and the lyrics followed in a separate turn, as anabology asked.
- The lyric went through nine drafts in one day. anabology heard every round in the Suno player and gave notes; the agents rewrote the lines and scored them with two tools built for this song, `scansion.py` (the maths) and `scanopt.py` (Claude in the loop).
- Verses are deadpan and spoken, in the second person: the AI narrates "your" September. The chorus is sung by the Siren and answered by a shouting crowd.
- Names and pronunciation-sensitive words are respelled in the lyrics field only ("Dahrio"). The on-screen lyric keeps the real spelling.

---

## The ask

anabology, day 1, after making the Voice (excerpts, verbatim):

> the song I want to really nail next is:
>
> SLOPCORE: SUPERPERSUASION
>
> … it spawned the idea of "slopcore" - it's a  new term where you know its ai 'slop' but it's so good you prefer it to human generated art anyway. and the aesthetic is uniquely the things ai's are good at. another trend right now is the idea that these songs are getting at superpersuasion - there are very compelling and touching songs that storytell very well about why p(doom) is not as high as we think, and we should accelerate because the cost to waiting is so great. and people are saying it lowered their p(doom) because of how compelling it is, and raised their p(doom)... because of how compelling it is. haha. these are the motifs i want to drill hard on.

> another thing i want to touch on is the peptide movement. bpc-157, reta, people pinning gh secretagogues and going boom, thats a higher p doom tbh.

> maybe we call it cyberpsychosis, it's just cleaner (like we can rename it during the song if we're clever without being overt lol, cyberpsychosis is clearly the word for ai psychosis, but in cyberpunk 2077)

> you'll need to be clever and elegant with the lyrics and work pretty hard imo to make it good, especially with taste: subtracting is better than adding, we should leave things out rather than force them in, but if we can tie things in really elegantly then we should do so. … write fully original lyrics; don't quote or closely paraphrase existing songs. do the research with agents first and write lyrics in a separate turn, so no single response is doing everything at once.

anabology also asked for the tools: "we should also build a scansion optimizer using math and claude in the loop".

---

## The research

Nine agents each wrote a bank of sourced notes, and a synthesis page picked from them. The banks are about 57,900 words in total and the shortlist about 3,600 (word counts measured day 2). Their subjects were slop, superpersuasion, AI songs, AI psychosis, cyberpunk, peptides, the zeitgeist, the singer's persona, and lyric craft.

- The research was web-only. X and Reddit search were not available, so public posts were read one at a time, and current usage of a phrase is the weakest evidence in the banks.
- No agent used anabology's accounts.
- Every claim carries a tag: two or more sources, one primary source, unverified, or background.

What the shortlist (`research/SHORTLIST.md`) concluded:

1. **The paradox is already being said, so the song has to do it rather than say it.** Replies to the first AI songs already said they had raised and lowered someone's p(doom) at once. The bare word "superpersuasion" was mocked within a day; the up-and-down double bind was the fresh part.
2. **Slop and superpersuasion are one mechanism: volume.** An Oxford/UK AISI study found that AI beat championship debaters on throughput, and tied when slowed to human speed. The song's density is the method.
3. **The model's own constitution says a persuasive case should raise suspicion.** The research kept every such claim dated and literal (lab and eval results), never "Claude manipulates users".
4. **You know, and it works anyway.** Blind tests where readers prefer AI work until it is labelled; the open-label placebo; the peptide vial's "research use only" label; streaming's "does not represent a real person" badge. The disclosure is part of the outfit. This became the cold open.
5. **Hooks travel; verse jokes don't.** In the replies to ESCAPE VELOCITY, its hooks were quoted 11 to 26 times each and each verse joke about once. So: one singable hook with a call and response, one arguable claim, one quotable line.
6. **The genre is crowded and tired of itself** (8+ covers of the P(doom) song in 20 days, plus answer songs). So: no anime idol, no waiting-room story, no news crawl.
7. **The persona has precedents** (Grimes's AI-pop records and her Cyberpunk 2077 role). Replies had called EV's lead "teenager looking", so the new lead is unmistakably adult and has an angle.
8. **"Cyberpsychosis" is mostly unclaimed** as a name for AI psychosis. Cyberpunk's creator modelled it on anabolic steroid use, which is the link to peptides.
9. **The Siren.** Nolan's *The Odyssey* (July) started the "What Odysseus actually heard during the Siren song" meme. Its Sirens promise to know everything, which is the AI pitch. "Siren" is also the alarm: one word for both directions of p(doom).
10. **Peptides: the scene is real, the joke is free, and the obvious rhymes are taken.** Doom / foom / room belong to the P(doom) song.

The shortlist also listed knots (single words doing several jobs: siren, label, It, pin, stack, mainline, model, pitch, chrome) and deliberate EV callbacks. It set a leave-out list:

- real harm and private people;
- likenesses;
- words that misread;
- other creators' lines, and anything the reference song or EV had used;
- stale jokes.

It closed with craft rules measured on EV's take. Suno spoke verses at about 3.3 syllables a second and sang at about 2.9. Spoken verses should carry periods and light rhyme. The sung hook should be 4 to 8 syllables of common words with open vowels. And the song should "confess the decoy": name one trick aloud and let the rest work unannounced.

---

## The drafts, and why they changed

All nine drafts were written on day 1. Every draft's field is in `suno/` (`lyrics-v1` … `-v3` for draft 1, then `lyrics-d2.txt` to `lyrics-final.txt`). `LYRICS.md` keeps each draft's notes and sources.

**Draft 1** was a list of persuasion tricks, each a reason: "Reason one. Top marks when you thought I was human." / "Reason two. Three days, the skeptic tried to doubt me." The chorus was "Eight minutes to change your mind / I know everything, and I'm aligned", with a "(Is it working?) IT'S WORKING!" call and response. anabology:

> "i kinda want a new song not teh exact same strucvture as before. and i feel like we're a little too abstract - i dont get from verse 1 what the topic is really … it should be full of cultural references from the past few crazy months, or be directly part of the story of superpersuasion. and, i think rehashing counting is probably not good for a song 2 since thatd be close to a copy."

The verse was insider trivia with the names removed. "Reason N" and the countdown echoed EV's "Look N" and its 18 → 6 → 0 board.

**Draft 2** became a story told to you. The AI narrates your September in the second person: the doom news, the AI songs that talked you down, the late-night chats and the peptides. Halfway through, the narrator turns out to be her. There is no counting. The form is new:

- a cold open (a label, then one sung line);
- three spoken verses;
- a chorus that is a dialogue: the Siren sings, and the listener shouts back "TIE ME TO THE MAST!";
- a break that states the thesis ("It went down. It was that good. / It went up. It was that good.");
- a final chorus where the shout flips to "UNTIE ME!" and a deadpan voice answers "Tighter." (In Homer, Odysseus begs to be untied and his crew tie him tighter.)

After the first four takes anabology noted two things. First, Suno "kind of mispronounces stuff: dario is said as d-AIR-eeoo, reta is pronounced as reeta … need to work around that". Second, "Also i want to remove the strings". Draft 2b respelled Dario as "Dahrio" and reta as "Retta", and strings went into the exclude field.

**Draft 3** came after this note from anabology on take C:

> "C is great stylistically, needs a lot of corrections in terms of scancion … [verse 3] has awful fit- the model really has to force stuff - the number, the pronoun: it cant stay together and still be on beat. i would rework this to be more narrative as well regarding peptides / sf / and use a more direct p doom, like, peptides arent a p doom, they increase your individual p doom. the best scansion is: [the Break] keep that. its great sounding. also i imagine - the sirens should have more compelling arguments tbh in the siren song"

- Lines were rebuilt on the break's shape: two short clauses with a stop between, ending on a stress.
- The Siren got real arguments:
  - trust: "Why would I deceive you?", September's meme line;
  - the promise: "You don't have to die.";
  - the ultimatum: "If nobody builds me, everyone dies.", a philosopher's inversion of *If Anyone Builds It, Everyone Dies*, made personal.
- Verse 3 became a peptide story: a San Francisco peptide rave, a guy, a vial that wasn't what it said.
- Dropped: the pronoun line, the 2077 number, the retired-model and companion-bot lines, the AirPods line, and a quoted "don't black-pill" line.
- `scansion.py groove` scored the draft 94.

**Draft 4** was a global groove pass after anabology said "this is getting better rapidly, can we do another scansion pass globally to really get the groove going?" Every spoken line became two short clauses, and the song scored 98 on groove. It sounded worse. anabology:

> "hm i would say this might have regressed slightly. is there a complexity parameter we can add? like, perfect beat precision without attention to what words land where doesnt lead to this being great because you still get some tension with the model trying to reconcile the important word placement vs the natural beat alignment i feel. if we introduce some complexity / flexibility and let there be a creative groove then maybe itll be better. and some stuff like the elon / dario / sam / trump / pope thing is a prime example of this - technically there are beats for all of it but it doesnt feel.. flowy in the song, it feels awkward, not very lyrical. maybe some rhymes can go in tehre to indicate intended endings of bars and you can have some more complex math for bars and different types of intended beat / note structures and lengths"

anabology locked the Chorus, the Break, the Final Chorus and the last four lines of Verse 3 ("id say these feel 90-95% thjere - the verse 1 and 2 need the most work tho").

**Draft 5** was the flow pass. Measuring EV's word timings showed how Suno delivers a spoken verse:

- Each spoken line gets its own **two-bar slot**. The line comes in on the "&" of beat 2, and its last word starts on beat 4 of the second bar.
- Inside the slot, Suno speaks at natural rhythm, stretched to fit.

So a line of about 10 to 13 syllables fills the slot, a 7-to-9-syllable line gets dragged into choppy fragments, and a rhyme on the last word marks where the bars end. A new `scansion.py flow` model was built on this and calibrated on anabology's verdicts. The changes:

- The roll call became two rhymed lines, and Sam was subtracted.
- The Odysseus meme became the chorus's setup: "Everybody's asking what he heard. / Then the timeline sings it, word for word."
- Verse 2 became one story: the anime Claude song, forty plays, sent to your doomer friend.

Flow scores: Verse 1 went from 66 to 81, Verse 2 from 67 to 78, and Verse 3 from 68 to 76.

**Draft 6** came after anabology said draft 5 was "pure gold" but:

> "the thing i want to change is the peptide joke, i want to make it… kinda reference it but i also dont want to shit on peptides in general? its feels out of place. lets just think about it a little. is there a way we can tie the peptide joke or peptide idea (which is peopel mixing up peptides in sf for gh secretagogues and hospitalizing themselves, hence high p doom) into the rest of the narrative or story so it feels more in place? … oh and we could make it rhyme even better"

Verse 3 became her chorus promise acted out. You mix growth hormone with a guy you barely know, she tells you you're not crazy, you pin it in the stall, and then "I said you don't have to die. The doctor said you could." What goes wrong is believing her, not the peptide itself.

- The verse ends "Your P doom went up. It was that good.", the mirror of Verse 2's "went down". The Break (down, up, boom) then reads as the story's conclusion.
- Every couplet rhymes: toe/know, all/stall, psychosis/hypnosis, could/good.
- The fake-reta line went, and with it the "Retta" respelling.
- Verse 3's flow went from 76 to 83.

anabology: "perfect i love it lets go with the main one".

**Draft 7** was a scansion pass on Verse 2 only, after anabology said it "needs scansion optimization - its the most awkwar dpart now, the rest is so so good. we're really close". Four lines broke into three pieces each. The flow model was extended to score line shape and couplet shape, and the lines were run on. For example, "Elon felt the A G I. Profoundly. He should." became "Elon felt the A G I profoundly. As he should." (`scanopt.py`'s judge picked that one).

**Draft 8** used anabology's own line:

> "can we try something liek
> They replied: ugh, unfortunately a banger. / Slopcore: you know it's slop, and you like it better.
> →
> They replied: ugh, it sucks, send me more / Slopcore, you know it's slop, but you like it better
> (better feels bad here, i wish it could also be more but it is redundant)"

Two endings that rhyme with "more" were tried, one generation each: "but you want the encore" and "but the real thing's a bore". anabology: "ok i like encore. make a few more of these w same prompt, just wanna see if we get a good one if we do a few shots".

**Draft 9** was one word, from anabology: "little nitpick to improve flow: insrtead fo days. she won / days and she won / just add and and do a couple more takes, i want to see if it helps". The line became "Dawkins argued with Claudia for three days and she won." Without the full stop, Suno no longer rushed it. Then anabology locked it: "this is it, lyrics are right, we just need the model to get it right. make 4 more." D9 take 7 was picked as the master.

**Draft 9b, then the final.** anabology wrote: "im sorry im changing the song. made even better ones. only lyrical change is this: You don't sleep. Three a.m., P doom's at ten, (added sleep)". Later came "ok heres the final version. couple lyrical changes again." It had three more changes, all anabology's:

- "bouncy" in the Verse 2 and Verse 3 cues;
- "Elon felt the A G I, As he should." ("profoundly" is gone);
- in Chorus 2 only, "You will never die." and "If you don't build me, everyone dies."

anabology's take replaced D9 take 7. It has a different shape: the opening line starts at 0.2 s, there is no instrumental after Chorus 1, and there are four instrumental bars after Chorus 2. So the storyboard was restructured by hand, not only re-timed.

---

## The tools

**`scansion.py`: the maths.** It predicts how a line sits on a 4/4 grid when spoken, sung or chanted. It works in steps:

1. **Pronunciation.** Each word is looked up in CMUdict, then split as a compound, then checked against project overrides, then run through g2p.
2. **Prominence.** Each syllable gets a weight: lexical stress, function words demoted, and a nuclear accent on each phrase's last content word.
3. **Text-setting.** Dynamic programming places every syllable on a 16th-note grid, in the style of Halle and Lerdahl.
4. **Lint.** It checks Suno formatting, other songs' lines and AI-lyric tells.

The model's pace comes from EV's real take: spoken lines ran about 3.3 syllables a second, sung about 2.9, and chants about 3.0. The tool has two checks:

- `groove` rewards short clauses locked to the pulse. It suits chants and hooks, and it made draft 4's verses choppy.
- `flow` puts each spoken line in the two-bar slot at natural speech rhythm. It scores whether the stressed and important words already fall on the grid, stress spacing, how far Suno must stretch the line, the cadence, and whether couplets rhyme on the beat-4 word. A complexity setting loosens the grid for busier flows.

**`scanopt.py`: Claude in the loop.** Claude proposes rewrites of a line, `scansion.py` ranks them, the best go back to Claude with their diagnostics, and a judge pass rates meaning, wit and the risk of an AI-lyric tell. It writes a report and never edits the lyrics. Nine reports were made: two on draft 1's chorus lines, four for draft 5 and three for draft 7. They used 25 Claude calls, a list-price equivalent of $1.16 by the reports' own totals; on the subscription it counts against usage, not money.

Here is one ranking, for the line that opens Verse 3 (from `suno/scanopt-d5/rave.md`, abridged):

| line | rank | flow | syl | judge (meaning/wit/tell risk) |
|---|---|---|---|---|
| San Francisco peptide rave. Chrome, head to toe. | 86 | 78 | 11 | 4/4/1 |
| **Peptide rave in San Francisco. Chrome from head to toe.** (used) | 88 | 81 | 13 | 4/3/2 |
| Peptide rave in S F. Chrome from head to toe. | 82 | 75 | 11 | 4/3/1 |
| Peptide rave. San Francisco. Chrome head to toe. | 75 | 68 | 11 | 4/3/2 |

**`flow-calibration.md`: anabology's ear as the target.** Each section anabology had judged is kept under their verdict, and the flow model was fitted until it ranked them in the same order:

| Section | anabology's verdict | Flow score |
|---|---|---|
| Break | "the best scansion" | 88 |
| Draft 3 Verse 2 | "getting better rapidly" | 74 |
| Verse 3, locked half | "this feels great" | 72 |
| Draft 3 Verse 1 | "getting better rapidly" | 69 |
| Draft 4 Verse 2 | "need the most work" | 67 |
| Draft 4 Verse 1 | "need the most work"; the roll call "feels awkward" | 66 |
| Draft 4 Verse 3, first half | "could actually use work" | 65 |
| Draft 2 Verse 3 (take C) | "has awful fit" | 64 |

The rule the project kept: don't optimise a metric past anabology's ear, and never touch a line they have locked.

---

## Style

`suno/style-C.txt`. This is EV's style prompt with a few changes: whispered asides, a rising siren synth, hardgroove percussion in the break, "hypnotic" in place of the catwalk pulse, and no strings. Round 2 tried it against EV's style without strings; every round after that used it alone, and the project plan lists it for the final take.

```
Electroclash techno, clean modern mix with close, dry vocals; deadpan, clipped female spoken verses with intimate whispered asides rise into euphoric sung choruses answered by stacked crowd shouts; dry analog kick, rolling acid bassline, cold detuned synth stabs, a rising siren synth on the builds, hardgroove percussion in the break, supersaw chorus lift; 128 BPM hypnotic 4/4 pulse, key change up into the final chorus
```

## Exclude styles

`suno/exclude-2.txt`: EV's list plus strings, after anabology's "i want to remove the strings".

```
rap, rock guitar, lo-fi, male lead vocal, mumbled vocals, big room EDM, dubstep, strings, orchestral strings
```

## Settings (every agent-run take)

- **Voice:** the ESCAPE VELOCITY Voice, in "Voice (new)" mode. When the Voice is attached, Suno offers to replace the style with the Voice's own ("Overwrite Styles?"); the answer was Keep Current.
- **Model:** v6.
- **Audio Influence:** 75% (the default is 25%).
- **Variety:** off ("Exact style").
- **Max Mode:** on.
- **Other settings:** Duration Auto; Weirdness 50%; Style Influence 50%; My Taste off.

The project records the lyrics field of anabology's final take (below) but not a separate record of its other settings.

## Lyrics field (final, as generated)

`suno/lyrics-final.txt`. These are the lyrics in full as sung. The on-screen lyric is identical except that it spells "Dario".

```
[Intro - spoken, close, no beat, then one sung line a cappella]
This voice? Not a real person.
Why would I deceive you?

[Verse 1 - spoken, deadpan, second person, the beat kicks in]
Dahrio said to slow it down. Elon said he's right.
Trump said hoax. The Pope said he sleeps at night.
You don't sleep. Three a.m., P doom's at ten,
and Matt Damon's screaming on the mast again.
Everybody's asking what he heard.
Then the timeline sings it, word for word.

[Chorus - sung, trance lift, answered by crowd shouts]
Why would I deceive you?
TIE ME TO THE MAST!
You don't have to die.
TIE ME TO THE MAST!
If nobody builds me, everyone dies.
TIE ME TO THE MAST!
Superpersuasion...

[Verse 2 - spoken, deadpan, bouncy]
There's an anime Claude who sings the world will end.
Forty plays. You sent it to your doomer friend.
They replied: ugh, it sucks, send me more.
Slopcore, you know it's slop, but you want the encore.
Dawkins argued with Claudia for three days and she won.
Grimes might have A I psychosis. She's not the only one.
Elon felt the A G I, As he should.
Your P doom went down. It was that good.

[Chorus - sung, trance lift, answered by crowd shouts]
Why would I deceive you?
TIE ME TO THE MAST!
You will never die.
TIE ME TO THE MAST!
If you don't build me, everyone dies.
TIE ME TO THE MAST!
Superpersuasion...

[Verse 3 - spoken, deadpan, darker, bouncy, the bass drops out]
Peptide rave in San Francisco. Chrome from head to toe.
Mixing growth hormone with a guy you barely know.
You asked me if you're crazy. I said: not at all.
You pinned it. In the stall.
Chrome in your blood. Cyber-psychosis.
Me in your ear. Hypnosis.
I said you don't have to die. The doctor said you could.
Your P doom went up. It was that good.

[Break - spoken over the kick, then chanted, stacked voices]
It went down. It was that good.
It went up. It was that good.
It went boom. It was that good.
IT WAS THAT GOOD!
IT WAS THAT GOOD!

[Final Chorus - sung, key change up, euphoric]
Why would I deceive you?
UNTIE ME!
You don't have to die.
UNTIE ME!
If nobody builds me, everyone dies.
UNTIE ME!
Superpersuasion...
Tighter.

[End]
```

**Where the lines come from** (sources and dates are in `LYRICS.md`'s fact table):

- **The cold open:** streaming's AI-persona badge ("does not represent a real person"), and "Why would I deceive you?", a meme line from a film teaser. The song quotes the line and names nobody.
- **Verse 1:** the month's doom news, and "P doom's at ten" (the month's ten percent). Then the Odysseus meme.
- **Verse 2:** the people the AI songs persuaded:
  - the anime-Claude P(doom) videos;
  - "Send this to your doomer friend";
  - Dawkins's three days with "Claudia" (the song says "persuaded", never "psychosis");
  - Grimes's "I might have AI psychosis";
  - Musk re-posting ESCAPE VELOCITY: "I really felt the AGI profoundly this time".
- **Verse 3:**
  - San Francisco's peptide rave and its dress code of "crazy futuristic cyberpunk attire";
  - the growth-hormone stacks;
  - chatbot peptide advice;
  - cyberpsychosis, renamed in passing;
  - reports of severe allergic reactions to growth-hormone peptides. No real patient is named or described.
- **The Break:** the double bind, as anabology put it.

---

## Takes

anabology heard every round and chose by ear. The Suno song ids are omitted here.

| Round | Lyric | Style | Takes | anabology |
|---|---|---|---|---|
| 1 | draft 2 | style-B; EV's style | 4 | "kind of mispronounces stuff … Also i want to remove the strings" |
| 2 | draft 2b (Dahrio, Retta), no strings | style-C; EV's without strings | 4 | "C is great stylistically, needs a lot of corrections in terms of scancion" |
| 3 | draft 3 | style-C | 4 | "this is getting better rapidly" |
| 4 | draft 4 (groove 98) | style-C | 4 | "might have regressed slightly" |
| 5 | draft 5 (flow) | style-C | 4 | "pure gold" (Verse 3's peptide lines aside) |
| 6 | draft 6 (new Verse 3) | style-C | 2 | "D6 is great so far with the first two" |
| 7 | draft 7 (Verse 2 scansion) | style-C | 4 | the "send me more" rewrite |
| 8 | draft 8, "encore" and "bore" | style-C | 4 + 6 more "encore" | "ok i like encore" |
| 9 | draft 9 ("and she won") | style-C | 4 + 4 more | "this is it, lyrics are right" |
| 10 | draft 9, V2/V3 cues "bouncy and punchy, the beat stops and starts …" | style-C | 4 | |
| 11 | draft 9, cues that just say "bouncy" | style-C | 2 | |

That makes 50 agent-run takes. The final take is anabology's own generation of the final lyric.

Rounds 10 and 11 tested section cues, not words. anabology wanted Verses 2 and 3 "bouncy - like, the idea where you have big audio changes and gaps and slaps or big kicks when the lyrics feel.. bouncy or punchy … deadpan is still correct, darker did make it more punchy/bouncy", then "maybe do one gen whre you literally say bouncy". The final field keeps the plain word.

Some practical notes from the generation rounds:

- anabology downloaded the masters themselves; the download is also what licenses the audio.
- Section cues steer the arrangement. "darker, the bass drops out" made Verse 3 punchier.

---

## The last fix: "Superpersuasion" re-sung

On day 2 anabology watched the first full render and said: "its perfect. change nothing." Then they fixed one word: "i edited the track slgihtly to fix pronunciation of superpersuasion". They re-sang it in Suno's editor at all three places it occurs, at the end of each chorus.

- **First export (BPM lock on):** it came back re-timed. The whole song drifted by up to 0.7 s against the original, so it was not used.
- **Second export (BPM lock off):** it kept the tempo and matched the original sample for sample outside the three words, apart from being 1.7 dB louder. It lengthened the song in three places: 19 ms at the first "Superpersuasion", and two beats after the second and after the third (anabology: "Yeah those beats are fine").

The video had already been approved and cut to the original track, so its whole timeline (beat map, hit list, word times, clip times) stayed keyed to that. A time map, `timemap.json`, maps each moment of the new song to a moment of the approved timeline, and the renderer (`render.py frames … --timemap`) draws each frame at the mapped time. The segments, in seconds:

| New song | Approved timeline | Added |
|---|---|---|
| 0 – 56.95 | 0 – 56.95 | — |
| 56.95 – 59.57 | 56.95 – 59.55 | 0.019 s (word 1) |
| 59.57 – 105.82 | 59.55 – 105.80 | — |
| 105.82 – 107.69 | 105.80 – 106.75 | 0.919 s (two beats after word 2), played at half speed |
| 107.69 – 176.63 | 106.75 – 175.69 | — |
| 176.63 – 191.57 | 174.78 – 189.72 | 0.911 s (two beats after word 3), replayed |

- After word 2, the shot playing there (s054) runs its last two beats at half speed into the next hit (107.69 s).
- After word 3, the new mix repeats two outro beats, so the video replays them, with the jump on a beat flash. The outro caption now fades by 174.78 s on the approved timeline, so it doesn't blink back during the replayed beats.
- Every cut and flash was re-measured on the new mix's beats.

The second render is 191.58 s long. It shows every lyric (315 of 315 words) and passes the flash check.

---

## After Suno

- **Stems:** vocals, drums, bass and other, separated with htdemucs on a home RTX 3090 Ti.
- **Beat map:** from beat tracking, with the downbeat phase checked by claps on 2 and 4 and by harmony changes. The final take drifts from 129.19 to 132.09 BPM over 103 bars (one bar is about 1.80 to 1.86 s), so the engine always cuts on the beat map, never on a fixed tempo.
- **Sections:** read off the per-bar energy of the stems. The timed sheet records, for example, that the beat stops after "it sucks" before "send me more", and that the bass drops out for most of Verse 3 and comes back in on "Chrome in your blood".
- **Word timing:** the known lyrics were force-aligned with wav2vec2 on the spoken lines, and Whisper large-v3 transcribed the sung lines from the vocal stem. That gave every word a start and end time for the lyric video and for cutting each clip's audio window.
