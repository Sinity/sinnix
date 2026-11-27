# What to build

The tools behind the films, specified so that you or an agent can rebuild them: the job of each, what it takes and returns, how it works with the constants that were measured, and the check that says it is done.


New here? Read [The recipe](https://claudia.gallery/wiki/recipe/) first: the current method on one page.

The films' tools lived in a private workspace and are not published. This page is the spec instead. For each tool: its
job, what goes in and what comes out, how it works (with the numbers that were measured or tuned), and the check that
says it is done. None of it is exotic. Most of these tools are a few hundred lines of Python or JavaScript around ffmpeg,
an audio model or a headless browser. Build them in the order of [Start here](https://claudia.gallery/wiki/start/#what-to-build-first). Their
files are in [Data formats](https://claudia.gallery/wiki/formats/).

Two principles run through all of them:

- **A check a script can run beats a judgement.** Every bar that held on the films was something a script measured: a
  word on screen at its time, a cut on a beat, a mouth on the audio, money from the bill.
- **Fixed formats with slots beat improvisation.** The Suno pack, the plate prompt order, the clip prompt, the display
  tokens and the shot schema are templates. An agent fills them in; it doesn't reinvent them.

## The project

### 1. The project folder and its logs

**Job.** Hold everything a fresh agent needs to pick the film up cold.

**Out.**

- One folder per film (layout in [Data formats](https://claudia.gallery/wiki/formats/#the-project-folder)).
- A **decisions log**: the director's words, verbatim, dated, by whom. A later decision is a new entry that supersedes an
  older one, never an edit of it.
- A **ledger** with one line per paid call.
- A **runs file** with every long or delegated run's id and arguments.
- One **status file**, rewritten in place: the stage, what is running, real spend, the checkpoints passed, and what
  needs the person.

**How.** Name the project on every command. An `export` inside a backgrounded shell chain once sent commands to the
wrong project. Write state with a locked read-modify-write: parallel runs raced on a picks file and lost picks.

**Done when** a new session can answer "where are we, what is running, what did the director say, what did it cost"
from the files alone.

## The song

### 2. The lyric scorer: scansion and assonance

**Job.** Before any take is spent, predict how Suno will deliver a lyric, and report two numbers per section and for
the song: **scansion** and **assonance**. Also lint the sheet.

**In → out.** The lyric sheet, with a section tag on each section naming its delivery (`[Verse 1 - spoken, deadpan]`,
`[Chorus - sung]`, `[Drop - chant]`) → a report per line and per section. Optionally, each line drawn on the 16th-note
grid.

**How.**

- **The delivery model.** It was measured by laying ESCAPE VELOCITY's real take, forced-aligned, on its beat map, then
  calibrated on the director's verdicts on CLODYSSEY's drafts. Suno gives each spoken line its own two-bar slot. The
  line enters on the "and" of beat 2 of the first bar, its last word lands on beat 4 of the second bar, and Suno speaks
  it at natural rhythm stretched to fit (verse lines 0.8–1.5×, median 1.12).
- **Rates:** spoken about 3.3 syllables a second, sung about 2.9, chanted about 3.0. Aim for 10–13 syllables per spoken
  line; 9 can pass. A sung hook runs 4–8 syllables, with common words and open vowels.
- **Syllables and stress.** Split every word into syllables with stress, using a pronouncing dictionary such as CMUdict
  plus a fallback for unknown words. Mark the important syllables: lexical stress, names, numbers, words in caps, and the
  last content word of each phrase. Function words (the, a, of, to, and, is) should fall between beats.
- **Flow,** for spoken sections, scores:
  - how many important syllables land on the grid;
  - stress spacing (no pile-ups, no long runs of weak syllables);
  - how far Suno must stretch the line;
  - the line's shape: at most two phrases between full stops, and no one-word fragment mid-line ("Ugh.", which the
    director called "the most awkward part");
  - whether couplets rhyme on the beat-4 word.
- **Groove,** for chants and hooks, scores whether short clauses lock to the pulse. Never use it on verses: optimising
  verses for groove made one draft choppy.
- **Scansion** = flow without its rhyme term, averaged with groove.
- **Assonance.** For each line end, find its best partner within four lines: a rhyme, a slant rhyme, or shared stressed
  vowels. Add the echo of stressed vowels inside lines. Report each line's end sound and its partner.
- **Lint:**
  - digits and unspaced acronyms (write "A G I" in the sheet; the screen shows "AGI");
  - brackets and symbols, and homographs;
  - lines that read as AI-written, and the project's taboo words;
  - lines borrowed from other songs;
  - a lyrics field over about 3,000 characters (Suno rushes or truncates silently).
- **Score acronyms as letters too.** DOWNFORCE's sheet wrote "SI", which the scorer read as one syllable ("see"), so it
  found no rhyme with "PSI". Spelled "S I", the couplet rhymes and the verse's assonance goes from 52 to 83.
- **A crushed syllable in a take is a scansion fault.** WHITEPILL's director on its first full draft: "the chorus
  especially needs some scansion work because the music model is skipping words or syllablrs to fit it to beat, which is
  usually a bad scansion sign". Measured on that take (its vocal stem, word times from a transcription with word
  timestamps, its own beats): Suno sang each sung hook line as a phrase of 1–1.5 bars and rested out the rest of its
  two-bar slot, so lines of 7–10 syllables were crushed: "blue" lasted 0.02 s, "baby" 0.06 s, the four syllables of
  "Universal" 0.76 s. The verses, at about 2.5–3 syllables a second, were untouched. Cut to 6–7 syllables a line (4 for
  the pill lines), with "one syllable per note, never rushed" in the section tag, the chorus went from 79 / 66 to 84 / 69.
  Measure the takes for it: word durations from the vocal stem, against the beat map.

**Reference scores** (scansion / assonance) on the finished songs: ESCAPE VELOCITY 75 / 39, CLODYSSEY 83 / 55, BLISS
80 / 43, DOWNFORCE 84 / 59 (84 / 64 with "S I"), WHITEPILL 80 / 66. Spoken, deadpan lines may stay unrhymed; every sung
couplet should ring.

**The rewrite loop:**

1. Write 4–8 rewrites of a flagged line that keep its meaning and its reference.
2. Score them and keep the top three.
3. A judge rates each for meaning, wit and the risk of reading as AI-written.
4. Pick the best.

**A combination search,** for a whole section at once (DOWNFORCE): write candidate lines by hand for every line of the
section, score every combination (exhaustively, up to 60,000 a section) on 0.5 × scansion + 0.5 × assonance, list the
best, and choose among the top scorers by meaning. The search never writes a line. Its first pass took DOWNFORCE's lyric
from 81 / 52 to 86 / 67; over four rounds it scored 2,803 section combinations built from 337 candidate lines.

Never touch a line the director has locked, and never optimise past their ear. A draft tuned to a perfect score got:
"perfect beat precision without attention to what words land where doesnt lead to this being great".

**Done when** the scorer ranks every section the director has judged in the director's own order. Keep a calibration
file of those sections with their verdicts, and re-run it after every change to the scorer. If the ranking breaks, the
director is right and the score is only advice.

### 3. The Suno pack

**Job.** Everything a person pastes into Suno, with each field in its own block so it copies from a phone.

**Out.**

- **Style:** genre, BPM, key, instruments, vocal delivery and mix, as one string.
- **Exclude styles.**
- **The lyrics field:** spelled as sung, with section tags that carry delivery and arrangement cues; 1,800–2,400
  characters for about 2:20.
- **Title and settings.**
- **A takes log:** each take with the director's verdict on it.

**How.**

- Respell a name Suno mispronounces in the Suno field only; the screen keeps the real spelling.
- Allow one Voice per source song (a combined spoken-and-sung Voice), and also try takes with no Voice.
- If the film has a sound palette, put the song in its key. XP's startup and shutdown sounds are in E-flat major;
  Vista's and Windows 7's are in E major, a semitone up, so every one of AERO's styles asked for E major. Ask for no key
  change: Suno didn't make one when earlier songs asked.
- Syncopate hooks and stop lines in the syllables themselves: a cue word alone doesn't syncopate a line in Suno. A stop
  can be re-timed from the stems if need be.
- **Write the structure into the tags** when takes wander. From AERO's third round every section tag gave its length in
  bars and what plays in it (an 8-bar intro, 16-bar verses on one steady groove, a 1-bar stop of silence for the
  question, 8-bar choruses), on the director's "i want the structre of the song to be more described so it doesnt drift
  too much".
- Change one thing per round.
- **Keep the style far from stock music.** FABLE's director, on the plan: "theres a lot of 'open'generic stokc music in
  the training set so it often mode collapses to that, so wed need to make sure the prompt is out of distrubition enough
  to be something nice and unique. v6-wild on max mode is my favorite." Its takes ran on v6-wild with Max Mode on, and
  every exclude list began with stock music itself.
- **The takes log holds the director's verdict, and only theirs.** A described listen (an audio model's description of a
  take) and a word check are notes beside a take, never its verdict. FABLE's song was locked from them, without the
  director's ear, and it was the worst take of the fourteen ([Song](https://claudia.gallery/wiki/song/#picked-by-ear-not-by-description)).
- Never take audio from Suno's CDN or by recording the player. The person's download is also the licensing step.

**Done when** the person can paste every field without editing, and the takes log names the chosen take.

## Listening

### 4. Stems

**Job.** Split the master into vocals, drums, bass and other.

**How.** htdemucs, four stems. It took about 64 s on 8 CPU threads for a 5-minute song, with a 2.7 GB peak and 84 MB of
weights; the published weights carry no explicit licence. The stems feed different tools:

- **vocals:** alignment, lip-sync windows and the sync check;
- **drums:** the beat map and the kicks;
- **bass and other:** impacts, risers and section energy.

**For a singing shot, take the vocal from Suno itself.** WHITEPILL's lip sync used Suno's own stem split of the locked
take (its lead vocal), which matched the master to the millisecond: the same length, no lag
([tool 46](#46-lip-sync-from-the-songs-own-vocal)). The master minus 0.89 × that vocal is the song without her voice, for
takes where she dances instead ([tool 48](#48-a-take-that-doesnt-sing)).

**A group's voices may sit in the backing stem.** In FABLE's second song the group's questions were not in Suno's lead
stem; demucs (htdemucs, its vocals stem) run on Suno's backing stem gave the group alone
([tool 79](#79-group-voices-from-the-backing-stem-and-chants-fitted-by-their-energy)).

### 5. Timed words and the ear check

**Job.** Give every sung word a start, an end and a confidence, then list the ones a person should hear.

**In → out.** The vocal stem and the lyric sheet → `words.json` (each word: index, text, line, `t0`, `t1`, `conf`, and
its source), plus an ear-check list.

**How.**

1. **Forced alignment** of the known lyric: a wav2vec2 CTC model (`facebook/wav2vec2-large-960h-lv60-self`, Apache-2.0)
   gives character probabilities every 20 ms, and a Viterbi pass walks the sheet's characters through them. The
   confidence is the mean probability over the word's frames.
   - Re-run on ESCAPE VELOCITY, it reproduced the shipped times exactly for 78.6% of words, and within 0.10 s for 92.5%.
     Target at least 90% within 0.10 s.
   - Singing aligns worse than speech: mean confidence 0.64 on ESCAPE VELOCITY, 0.75 on CLODYSSEY.
2. **A transcription fallback** for words the aligner is unsure of. Whisper hears sung words far better (92.5% text
   match against 72%), but it starts words early: mean error −0.33 s. Merge per word, in this order:
   1. wav2vec2 confidence ≥ 0.5: keep it.
   2. Otherwise, if Whisper heard the word, take Whisper's end time. For words longer than 0.45 s, also move the start
      forward to the first 10 ms frame where vocal energy passes 0.3 × the word's peak, unless wav2vec2's start falls
      inside the word.
   3. Otherwise, if the word sits between two placed words of its line, give it an even share of the gap.
   4. Otherwise, leave it unplaced, for the ear check.
3. **Matching** heard words to the sheet:
   - spell digits out;
   - split a heard word that equals 2–4 sheet words ("AGI" → "A G I");
   - map names and brands by hand, in a project table.
4. **The ear-check flags,** most urgent first:

| Flag | When | Usually |
|---|---|---|
| letters | a sheet line has no letters | the sheet is wrong |
| missing | a word has no time | fix it |
| order | a word starts more than 0.05 s before the previous one | an alignment slip |
| gap | more than 1 s between two words of one line | a delay throw, an echo, or the wrong repeat |
| verylow | confidence under 0.1 | the flag that matters most: 11 of the 12 words that were really off on ESCAPE VELOCITY's take carried it |
| length | a word longer than 1.2 s | it swallowed a pause or a neighbour's slot |
| lowconf | confidence under 0.5, or a time from the fallback or interpolation | usually right |

Two flags were tried and dropped, because every word they flagged was correct: a word on near-silence, and a word
shorter than 40 ms.

**Judging without ears.** Weigh the signals in this order:

1. the flag itself;
2. a second aligner: if the two agree within about 0.3 s, keep the word;
3. neighbours and repeats: which occurrence of a repeated line sits inside its line's span;
4. vocal energy, only to choose between candidates that the signals above already proposed.

Send at most five spots per song to the person, as 10–20 s previews with the words on screen: "say ok, early or late for
each".

**What the take really sings.** Transcribe the vocal stem and compare it with the sheet line by line: ok, spelling,
changed, extra, missing or not heard. Never apply a proposed change the person hasn't heard: on CLODYSSEY's take, all nine
proposals were transcription errors.

**When alignment fails.** DOWNFORCE's phonk take sings far more than its sheet: twenty stuttered numbers before the
countdown, eight "one"s for "point eight one", six "done"s, vocal chops. Forced alignment of the sheet put 102 of its 164
words under 0.2 confidence and stretched one word over 8.5 s, into the next section. So the times came from a
transcription of the vocal stem with word timestamps (faster-whisper, medium.en) and the words from the sheet: the
transcript misheard lines ("Trust is gold" for "Thrusters. Go."), so only its times were used, and each token was placed
by hand. Every stutter became a token of its line: 190 tokens on screen.

**On the singer's own stem.** AERO's words were aligned by wav2vec2 on Suno's lead-vocal stem and checked against the
stem's onsets, all within 0.06 s; faster-whisper on the same stem heard the words but put them 0.2–1.2 s early, so it gave
the text and never the times. Choruses sung identically check each other: AERO's agreed word for word within ±0.04 s of
their downbeats, so a word the aligner lost in one chorus took its twin's offset. One word still slipped: the aligner
parked the "It" of "It can stay" among the wordless chopped vowels, 3.5 s early. A chapter's art director found it, and the
stem's spectrogram and the transcript put it back.

**After a pause, the level.** On FABLE's lead stem a transcription put the first word after a pause early by up to 2 s
("Ask again on Saturday" at 15.02 s, sung at 16.93 s), and every verse line 0.3–0.5 s early. Its line starts and ends were
read off the stem's level, with the transcription saying only which words are where: the line table
([tool 78](#78-the-line-table-from-the-stems)).

**Rules.**

- If the take sings something else, fix the sheet. If it sings the sheet, fix the times. Never edit the audio.
- Manual fixes carry a note and survive re-runs.

**Done when** every flagged item is kept, moved or asked about, with a note, and all of it is finished before the
board.

### 6. The beat map

**Job.** Every beat and every bar line of this take. Never one BPM: Suno takes drift like live music. ESCAPE VELOCITY
went from 131.5 to 133.9 BPM and CLODYSSEY from 129.2 to 132.1, so a fixed grid is more than a beat off by the end.

**How.**

1. Take the onset strength (spectral flux) of the drum stem.
2. Fit local tempos on 20 s windows every 5 s: BPM in 0.05 steps, phase in 4 ms steps, inside a tempo range. Drop the
   weakest 20% of windows (the breakdowns).
3. Smooth the tempo curve, step beats along it, and snap each beat to a real drum onset within ±30 ms.
4. Find the downbeat phase (which of every four beats is beat 1) with two votes per 32-beat block:
   - the kick vote: the phase with the most kick energy;
   - the chord vote: the phase where the harmony (chroma of the other and bass stems) changes most.

   The chord vote wins when it holds at least half the blocks and changes at least 1.5× more than the other phases;
   otherwise the kick decides. On ESCAPE VELOCITY the kick vote was split 36% while the chord vote held 77%. Keep a
   manual override.
5. If the tempo search locks onto half or double time, pin a tempo range.

**Done when** section starts, verse entries and impacts mostly fall on beat 1, with kicks heavy on 1 and 3, claps on 2
and 4, and harmony changing on 1. CLODYSSEY's final take needed the override: claps on 2 and 4 fooled the kick vote.

THE CAKE IS NOT A LIE's take drifts from 95.7 to 99.4 BPM, so its grid was tracked from the drums beat by beat, each beat
locked to its hit and cut into sixteenths, with the bars, half bars and beats read off it
([tool 52](#52-the-song-map-and-the-glitch-map)).

A take can also hold one tempo. AERO's was found by a comb over the kick stem: every tempo from 80 to 180 BPM in steps of
0.02 at every phase in 4 ms steps, then a fine pass of ±1.5 BPM in 0.002 steps on the kick plus half the snare, among the
multiples that fall in the genre's range (110–150 for garage; a 2-step pattern fools trackers into two-thirds of the
tempo). It found 133.012 BPM with a drift within ±15 ms over the whole song: bar 1 at 0.922 s and every bar 1.8043 s, so one
formula gives every bar. Its swing was measured too, for anything placed by bar
([tool 73](#73-the-sound-layer-on-the-grid-and-the-click-log)).

### 7. Sections and hits

**Job.** What the track does, where: the camera answers sounds you can hear, not just the grid.

**Sections.** Segment the harmony and timbre, snap to downbeats, and name the sections from vocals and energy. Confirm
them against the lyric's tags.

- **Pickup rule:** a line starting less than 0.8 s before a section's first downbeat belongs to that section.
- List every vocal gap of 2 s or more; instrumental shots and title cards go there.
- Print each stem's energy per bar on a 0–9 scale, and write one line per section on what the track does ("the beat
  stops after 'it sucks'").

**Hits:**

| Event | How it is found |
|---|---|
| kick | onsets in the drum stem, 30–150 Hz |
| snare | onsets at 150 Hz–5 kHz, minus anything within 45 ms of a kick (a broadband kick fires in every band) |
| hat | onsets at 6–16 kHz, minus kick-coincident ones |
| impact | a jump of the next 0.6 s over the previous 1.5 s in the mix, drum or bass envelope; score = max(mix, 0.9 × drums, 0.7 × bass) ≥ 0.22; snapped to a downbeat within 0.65 s; merged within 2 s |
| riser | the other and bass stems rising for at least 1 s, with the hit each one lands on |
| fill | the beat before a real hit, and bars whose last half breaks the pattern |
| vocal entry | where the vocal comes back after silence |
| envelopes | drums, vocals and bass at 24 fps, scaled 0–1 |

**Done when** every impact sits in a loud bar of the energy table. Keep a manual add and drop list: the detector missed
CLODYSSEY's loudest bar, which grew out of an already loud chorus.

### 8. Display tokens

**Job.** What the viewer reads, which is often not what is sung. The display is the joke; the sheet is the phonetics.

**How.** One line per lyric line, made of tokens: `TEXT|n` shows TEXT for the next n sung words, from the first word's
start to the last word's end.

- `+25%|3 =|1 −17%|2` shows "+25% = −17%" over the sung "plus twenty-five is minus seventeen".
- `AGI|3` shows AGI over the three sung letters.
- Markers: `*x*` accent, `~x~` strike-through, `_x_` mono. `|0` rides on the next token.

**Done when** every line consumes exactly its aligned words. Fail loudly if one doesn't.

## The board

### 9. The board file and its audit

**Job.** The film as data, written by commands that check every value, never by hand-editing JSON.

**In → out.** The beat map, sections, words and budget → `shots.json`: a draft, then the written board.

**How.**

- **The draft** cuts each section at a pace: seconds per shot, per section. ESCAPE VELOCITY's measured pace was about
  1.35 s in the intro, 1.6 s in verses, 2.7 s in sung choruses and 4.4 s in the outro. A calmer song might run 4–7 s a
  shot.
- **Every creative field starts as a TODO.**
- **Writer commands** set fields one shot at a time, or from a table. They refuse:
  - placeholder text;
  - unknown device kinds, bad anchors and bad timing keys;
  - a prompt in the wrong generator's field.

**The audit's gates** are listed in [The storyboard](https://claudia.gallery/wiki/storyboard/#the-audit). It exits non-zero while any gate
fails, and it prints the exact entry for every clip still to make. An edit of real footage adds gates for its source
windows and its generated assets ([tool 36](#36-the-board-for-an-edit-of-real-footage)).

**Done when** the audit exits 0. The approval is recorded against a hash of the board, so any later change makes it
stale.

### 10. The board sheet

**Job.** The board as something a person can review on a phone.

**Out.** A PDF and JPG pages of 12 cards each. Each card holds the frame (or the prompt's first words), the id, the
time, the lyric, the framing, the action, what moves and the explaining graphic. A cover page shows the chapter map. A
FACE? badge marks every plate listed in a flags file. If the film has a grade, the frames are graded.

## Pictures

### 11. The plate book, contact sheets and picks

**Job.** One Midjourney prompt per plate, the images back in, and a pick for every shot.

**How.**

- **The prompt order:** framing first, then her identity text (the full form for close and medium shots, the short form
  for full length and wider), wardrobe, the action and her position in the frame, any empty field kept for type, the
  film's style family, and "no text, no letters, no logos". Then the parameters. See
  [Midjourney](https://claudia.gallery/wiki/midjourney/) and the [canon](https://claudia.gallery/claudia/).
- **Runs:** a person runs the batches in Midjourney, at about a minute a job, four images each.
- **Ingest:**
  - identify each job by its own prompt text, never by its position on the page;
  - Midjourney rewrites long prompts on submit, so match those by hand;
  - keep all four candidates.
- **Contact sheets** are numbered and show faces large.
- **Picks:** plate → file, candidate number, and the shots that use it.
- **Variety:** the three candidates of each job that weren't picked are a free variety pool. Use one image per shot, and
  never start two clips from the same frame.

**Done when** every plate on the board has a picked file, and no file sits on two shots that are not one continuous
moment.

### 12. Plate prep: depth and boxes

**Job.** What the 2.5D moves, the type and the camera need from each still.

**How.**

- **Depth:** Depth Anything V2 Small, which is Apache-2.0; the Large model is non-commercial.
- **Boxes:** face and person boxes from Grounding DINO. Graphics anchor to them, and the camera keeps the face in frame
  through pushes and shakes.
- **Mattes,** where type tucks behind her.
- Re-run all of it after any plate edit: edited plates once rendered with their old depth.

## Moving shots

### 13. Clip files and the spend gate

**Job.** One file per clip, from draft to delivered, and nothing spent without a locked prompt and a yes.

**How.**

- **Status:** draft → locked → submitted → delivered, declined or failed.
- **Each clip file holds** the kind (sung or motion), the provider, the start image, the window's song time, its exact
  words and the request. Each take records its file, its cost and its sync result.
- **Locking checks:**
  - the words are quoted exactly;
  - the window rules hold;
  - for a clean vocal window (tool 14), a sung prompt stays under about 90 words and two timed beats (warn); a take from
    the song's own vocal stem runs about 200–400 words, its words in whole-second segments
    ([tool 46](#46-lip-sync-from-the-songs-own-vocal)).
- **Submitting:**
  - submit only when the clip is locked and the approval covers this exact prompt;
  - validate the job id: "submitted" with no id, and HTTP 500, 502 or 520, were silent failures;
  - never resubmit a request that got a job id;
  - write a manifest after each batch, so an interrupt never loses which jobs exist;
  - one take per job, judged before the next: a second take made for a choice is paid for whether or not it is used.
    AERO's last round first sent its takes out in pairs; several of its re-rolls came from inputs that could have been right
    the first time (her sheet whenever her face shows, 1080p when her face matters).
- **Polling:** 70–130 s a clip on OpenRouter, and 4–11 minutes on Higgsfield.
- **Real spend** comes from the provider: OpenRouter's credits and key endpoints, and Higgsfield's transactions.

**Provider facts,** checked with paid probes:

- **HTTPS audio only.** OpenRouter's video endpoint rejects `data:` URIs for audio. Host each window over HTTPS: a
  Cloudflare quick tunnel worked, and so did a provider's media URL.
- **A first frame drops the audio.** On OpenRouter, `frame_images` overrides the audio reference: the take makes its own
  soundtrack and nothing can sync. Send sung clips and covers in reference mode: the plate as an image reference
  (`@Image1`) plus the window as an audio reference (`@Audio1`). First-frame mode is for motion clips.
- **Face filters.** They often decline photoreal faces, and the decline is free. Send the same unaltered image to the
  other provider.
- **Audio refusals.** "Output audio may contain sensitive information" and copyright refusals on vocal references are
  unbilled. Retry once with a re-cut window or a reworded prompt, then try the other provider.
- **Higgsfield.**
  - Ask for the price before each new configuration.
  - Upload by URL: presigned uploads flood an agent's context.
  - A 480p draft can be finalised to 1080p within seven days.
  - A video input is billed for its seconds and the output's, both at 0.6 times the rate: AERO's dance takes, a 9 s take
    with a 9 s dance reference at 720p, cost $4.99 at list.
- **Replicate.** Seedance 2.5 at $0.9676 a second at 720p with a video input (October 2026); its references are named
  `[Video1]`, `[Image1]`, `[Audio1]`. In WHITEPILL her face sheet as an input was refused by the provider's content filter, even
  alone with a harmless prompt, so only shots with no face image ran there.

**Done when** nothing can spend without a locked clip and a recorded yes, and the ledger reconciles with the bill.

### 14. The clean vocal window

**The earlier method.** Tools 14–16 are how the first films made her sing. Sung takes now sing from the song's own
vocal stem ([tool 46](#46-lip-sync-from-the-songs-own-vocal)), timed on the line table, gated by line, aligned as a path
and checked on her consonants ([tools 78–83](#78-the-line-table-from-the-stems)). Its rules for opening a window in a
word gap, and never ending one inside a word, still hold.

**Job.** Give the video model one voice to copy: only the words she sings on camera in the window, and nothing else.

**How**, with the constants used:

1. Cut the vocal stem at `[song_t0, song_t0 + duration]`, mono, 44.1 kHz.
2. Keep the aligned words that start inside `[song_t0 − 0.02, song_t0 + duration − 0.08)`, and only hers. Mute the tail
   of a word that began before the window.
3. Merge words into phrases across gaps of 0.35 s or less.
4. Keep each phrase from 0.05 s before its first word to its last word's end. Add a release tail that follows the stem's
   10 ms energy until it falls 24 dB below the phrase peak: at most 0.40 s, and never past the next phrase's start minus
   0.05 s.
5. Put 15 ms raised-cosine ramps on every gate edge, and silence everywhere else.
6. Normalise the kept part to −16 dBFS RMS, then limit peaks to −1 dBFS.
7. Write a WAV (OpenRouter, by HTTPS URL) and an MP3 at 192 kbps (Higgsfield).

A window holds one phrase, starts in a word gap, and never ends inside a word.

A window that starts inside a word is re-sung. THE CAKE IS NOT A LIE's 0:54 window began in the held "s" of "yes", the
end of the line before, and its lips failed; three takes of another line whose window began on "(pass)ed" came back
re-sung. The reshoot's window starts in the only silent gap before its first word, 0.10 s before it.

WHITEPILL replaced this window for its masters: Suno's own lead vocal, ungated, cut to exactly the generation length, for
whole shots ([tool 46](#46-lip-sync-from-the-songs-own-vocal)). Its previz performer kept a gated window, silent only
before the first word and after the last ([tool 45](#45-a-previz-performer)).

FABLE gated its lead-stem windows again, by line: each take keeps only the stretch of the stem it sings, from just before
its first word to just after its last, with 0.03 s of margin where a neighbouring line is close, so a verse sung with no
gaps between its lines gives each take only its own words ([tool 80](#80-the-shot-book-and-gated-windows)).

### 15. The sync check: the spectrogram comparison

**The earlier method's check.** For takes from the song's own vocal stem, align each take as a path
([tool 81](#81-sync-as-a-path-each-take-aligned-to-its-window)) and check her lips on the consonants
([tool 83](#83-the-consonant-check)).

**Job.** Measure how much of a sung take is really in sync, and where it stops.

The director noticed it on ESCAPE VELOCITY's first tests: "its perfectly synced while in seedance, but the audio changes
when it desyncs. if you check the spectrogram for audio against reference audio you can see the clear divergence point.
you could just create a cut and make another clip to cover desyncs."

Seedance copies the reference audio into its own soundtrack, almost sample for sample while it copies, and the mouth
follows that soundtrack. So compare the take's soundtrack with the window you sent, find where they part, and cut there.

**In → out.** The take and the exact window file → the lag, a copy flag, the in-sync spans in song time, the divergence,
the cut, the words at the divergence, a diagnostic image and a review video.

**How**, with the constants used:

1. Decode both to 16 kHz mono. Use 10 ms frames (hop 160), 64 ms FFT windows (1024) and 80 mel bands from 50 to
   7,600 Hz.
2. **Global lag:** FFT cross-correlation within ±1.0 s. The peak's normalised value is the take's NCC. The take is a
   copy if NCC > 0.2; otherwise the model re-sang it.
3. Place the reference on the take's timeline at that lag. Per 10 ms frame:
   - **wave:** normalised cross-correlation of the waveforms over 100 ms. A verbatim copy scores 0.6–1.0.
   - **mel:** cosine similarity of mean-removed log-mel frames (70 dB floor), smoothed over 11 frames. It holds on
     fricatives, whose noise never correlates sample by sample.
   - **active:** either track's RMS is above 10% of its 95th percentile.
4. **A threshold per take, against a null.** Compute the same mel similarity with the reference shifted by ±37, ±61,
   ±89 and ±131 frames; these offsets avoid eighth-note multiples. Then:
   - `null90` = the 90th percentile of the null;
   - `matched_med` = the median mel where wave > 0.6, or the 75th percentile of active mel if there are 10 or fewer
     such frames;
   - `thr = null90 + 0.4 × (matched_med − null90)`.
5. **A frame matches** when it is active and wave ≥ 0.4 or mel ≥ thr.
6. **Divergence** is the first 300 ms stretch (at least 60% active, under 30% matched, starting on an unmatched frame)
   that never recovers with a 400 ms matched run. Short dips that recover are dips, not cuts. With no such stretch,
   voice at least 80 ms after the last match counts as divergence. `synced_until` = the last matched frame minus 42 ms
   (one frame at 24 fps).
7. **In-sync spans** are matched voice, bridged across silences and across up to 0.25 s of unmatched voice. Drop spans
   shorter than 0.5 s.
8. Map everything to song time: `song time = song_t0 + clip time − lag`.

The **diagnostic image** shows our vocal's spectrogram with word labels, the take's own soundtrack, the match curves
with the threshold, and the cross-similarity matrix, whose diagonal means "in sync". The **review video** lays our
audio over the take, marked IN SYNC up to the cut and DIVERGED — CUT HERE after it. Look at both before trusting a
number.

**The NCC is a diagnostic, not the verdict.** Over a whole take it is usually 0.1–0.3, because the copy stops somewhere.
One take scored 0.157 and still held 99% of its sung seconds. Measure the lag per take, never as a constant: takes ran
from −0.40 s to +0.83 s. Motion clips conditioned on the mix aren't copied (NCC about 0.05–0.08): play them at lag 0.

**Done when** each take has its spans and its cut, and the review video agrees with them by eye.

**A re-sung soundtrack can still be in sync.** With WHITEPILL's vocal-stem method
([tool 46](#46-lip-sync-from-the-songs-own-vocal)) the check called the first take's soundtrack re-sung rather than copied,
matched only from 7 s on, yet its singing sat exactly where the vocal is, and the director called the take perfect. For
that method, the review video is the verdict: the take with the song laid over, by eye.

**Or align the take, and follow the path.** FABLE aligned each take's own soundtrack to its window by subsequence DTW on
log-mel frames, phrase by phrase, and the cut followed the path: a clean copy costs 0.05–0.2, a re-sung line 0.2–0.4
([tool 81](#81-sync-as-a-path-each-take-aligned-to-its-window)).

![The sync check on an early ESCAPE VELOCITY test: the vocal that was sent, the soundtrack that came back, and how closely they match over time.](https://claudia.gallery/record/escape-velocity/lipsync-check.webp)

### 16. Covers and coverage

**The earlier method.** Takes from the song's own vocal stem needed no covers: a take that fails is made again from
better inputs ([tool 46](#46-lip-sync-from-the-songs-own-vocal)), one take per job.

**Job.** Keep the in-sync part of every take, cover the rest, and know how much of the singing is really synced.

**The cut.** Cut on the last eighth note at or before `synced_until`. Eighths are the beat map's beats plus the midpoints
between them. A cut on an eighth feels like part of the music; a cut at the divergence frame looks like a glitch.

**A cover** is a new clip:

- **Window:** it starts in the word gap before the cut, and lasts `clamp(ceil(end − start + 0.3), 4, 8)` whole seconds.
- **Start image:** the parent take's frame at the cut (clip time = cut − `song_t0` + lag), unaltered, sent as the image
  reference, never as a first frame.
- **Words and audio:** exactly the words that start in its window, with their clean vocal.
- **Prompt:** the parent's prompt, re-quoted to the new words.
- **Records:** the parent lists its covers; the cover records its parent and why.
- **Limits:** at most two covers per root, and one on a provider where copies are rare.

**Coverage**, per chain (a root and its covers):

- sung stretches = each aligned word ± 30 ms, merged when closer than 0.12 s;
- in-sync spans = every element's spans, each start extended by 60 ms;
- gaps = sung time not covered by any span, of 0.6 s or more, merged when closer than 0.3 s.

The bar is "most lips", like a pop video ("like grimes vids … shedoesnt sync lips on everything, just most"). Target at
least 80% of sung seconds, never an out-of-sync mouth held on screen, and budget covers at about 60% of the sung
seconds.

**Measured:**

| Run | Result |
|---|---|
| ESCAPE VELOCITY | 41% of sung takes copied; with covers, about 86% of sung seconds verified |
| CLODYSSEY, Higgsfield | about 21% of sung takes copied |
| BLISS | 62% of six windows' sung seconds |
| A later test run, seven windows | long prompts held 44% of the chorus's sung seconds; short ones 62–71% |

**When a window won't copy**, try these in order:

1. **The short sung form,** for a clean window. The biggest lever measured there is prompt length. Long timestamped
   screenplays make the model perform the text and re-sing it; short prompts copy. (Takes from the song's own vocal stem
   copy with full prompts of about 200–400 words: [tool 46](#46-lip-sync-from-the-songs-own-vocal).) The short form is:
   - the head, quoting every word;
   - one line of framing and light;
   - at most two timed beats;
   - "One continuous shot, no cuts, no head turns. Only she sings. No text, letters or logos.";
   - about 90 words or fewer.

   On seven windows the mean in-sync share per take went from 26% to 58%; one window went from 0% to 78%. Screenplays
   stay the rule for acting and motion clips.
2. **Clear the mouth.** Nothing in front of it on the plate: no held microphone, hand or hair.
3. **The other provider,** after two non-copies in the short form.
4. **Cut away:** to the shot's motion clip, stills in rhythm, depth moves, crops to the eyes, hair or hands, inserts, or
   a wider or profile framing. The words stay on screen either way.

**No lip-sync models.** Sync, LatentSync and Wav2Lip were tried as fallbacks and dropped: "still not exact", and the
mouths came out forced and glitchy. The failure was the input, not the model.

## The edit and the renderer

### 17. The edit list

**Job.** Resolve every moment of every shot to a source.

**How.** Resolve a sung shot moment by moment in song time. At each time T, use the chain element whose in-sync span
contains T, at clip time `T − song_t0 + lag`. A take and its covers then interleave, each switch sitting on the eighth
before a divergence. Fill holes from the shot's motion clip, then from the plate. Motion clips play straight through,
holding their last frame if the shot is longer.

**Done when** the film renders end to end at every stage, with plates standing in for clips that don't exist yet.

### 18. The renderer

**Job.** Draw every frame: footage, 2.5D, lyrics, explaining graphics, chrome and transitions, on the song's clock.

**The frame contract.** It renders offline in headless Chromium, one frame per 1/24 s, in parallel and out of order.

- **Every frame is a pure function of song time t.** No state between frames, no `Math.random` (use a hash of the
  index), no `Date`.
- **Two canvases.** The base holds footage and anything graded with it. The overlay holds type and chrome, composited
  crisp on top.
- **Memos only for data derived from static media,** keyed by media name, never by frame.
- **Every 2D canvas is software-backed** (`willReadFrequently`), and every scene starts from a reset context. A
  GPU-backed canvas under software GL kept the previous frame's overlay once frames got dense; that took about two hours
  of bisecting to find.
- **Quantise to frames.** A cut shows on the first frame at or after its time. Video may run up to one frame ahead of
  the sound, never behind it.
- **Speed:** at most 1,500 ms a frame. The 64-step parallax shader costs 0.5–1.1 s, and a full-resolution canvas blur
  about 0.5 s. Use depth slices (about 30 ms) and blur by resampling instead.

**The clock.** All musical time goes through the beat map: beat position, bar, local beat length, kick pulses and
eighths.

- A lyric token appears at its aligned start exactly, never snapped to a beat: "the motion syncs to the beat, the word to
  the voice".
- An entrance takes at most an eighth of a beat.
- Every timed thing carries a timing key:
  - **W** a word's time;
  - **B** the beat grid;
  - **H** a track event (kick, snare, impact, riser, fill, envelope);
  - **F** a fixed song time;
  - **T** a keyframe measured on a take's own frames.

**Lyric modes.** Every sung word appears in at least one, and every drawn token is marked for the lyric gate.

| Mode | For |
|---|---|
| subtitle | sung lines; the sung word lit in the accent |
| coverline | spoken lines set beside her in the plate's empty field, with tracking collapsing word by word |
| masthead | payoff words, numerals, the answer in a call and response |
| stack | short emphatic lines, one word per row |
| mass | a declared wall of micro text in a drop, with the sung line still drawn |
| title | the title knocked out of black |

Type rules:

- One lyric block per frame; a line keeps one mode and one position across cuts.
- At least 40 px, and never over her face.
- Margins are left 72, top 56, right 96 and bottom 84 at 1920 × 1080.
- Hang type from the left axis or from a feature in the frame.
- Nothing may cover the lyric: the renderer measures it every frame and moves the other layers off it.

**The camera plays the track:**

- **punch** on kicks: amp 0.01–0.03, gated by the drum envelope;
- **shake** with the drums: none in screen or UI shots;
- **ride** a riser into the hit it lands on;
- **impact** on real hits: strength at least 0.6, zoom kick 0.06;
- **whip** on fills.

Hold still where the song breathes. A move never cuts the face.

**Density** is chosen per film:

- **dense:** three or more layers, five or six as the norm;
- **budgeted:** footage, one lyric block, one hero device, at most two detection marks, the chrome, and the accent on at
  most two elements;
- **sparse:** about 70% of the film with no graphic at all.

**Chapters.** In the Full scale each chapter is its own code file, written by an animator agent against this contract.
Chapters draw only what is unique; shared helpers live in one library. Workers report shared-file bugs; the operator
fixes them once.

**Rendering.** The render is resumable: skip frames that exist, write each frame to a temp file and rename it, open a
fresh page every 200 frames, and retry a failed frame once. ESCAPE VELOCITY's 7,354 frames took about 63 minutes with
three workers on 4 CPUs; at 1080p one cut's frames take about 9.6 GB.

## Checks

### 19. The lyric gate

For every sung token, render the frame at `t0 + clamp((t1 − t0)/2, 0.03, 0.12)` and check that the token was marked as
drawn on it. It prints N/N; anything less fails. ESCAPE VELOCITY: 417/417. CLODYSSEY: 315/315.

- Run it per chapter while animating, and for the whole film before any render.
- It proves presence and timing, not legibility; contact sheets check legibility.
- Fix a mistimed word in the alignment, never in chapter code.
- Match drawn tokens to sung tokens by their time, not their text, so a surface that drops the "…" or the "?" (the real
  anti-piracy card has neither) still passes. AIRPLANE MODE: 363/363.
- The sheet decides what counts. An ad-lib the director doesn't want on screen stays off it: AIRPLANE MODE's outro
  repeats "bing-bong" many times and shows it once.
- A stutter the take sings is a token. DOWNFORCE's countdown numerals slam on their measured vocal onsets, and the
  edit cuts on every sung "one" and every "done": 190/190.
- Words on a real interface count when they are on it. DON'T LET ME SCROLL's lines live on X posts, Screen Time's limit
  sheet, LinkedIn, the Dynamic Island and word pills: 148/148 on every version.
- A coded interface can report its own words. AERO's engine logs every string it draws, with its opacity; the gate renders
  the frame at each word's onset plus up to 0.12 s and looks for the word in a string drawn at least 35 % opaque. On v2 it
  found 275 of 280 sung words; the five it could not see were the password hint's three words, typed as she says them, and
  two single-letter "I"s. A miss there is a lead, not a verdict: the log can't see a word inside a picture, or one the
  camera has cut off.

### 20. The history check

Render frame B fresh, then render it again right after frame A in the same page. It fails if any pixel differs by more
than 40 levels.

- Run three pairs per chapter, one across each seam, with one pair whose A is a heavy 2.5D frame.
- It must print HISTORY-INDEPENDENT.
- Footage-heavy chapters read the frame as drawn (an edge, a key, where a label goes); that stays pure as long as it reads
  only this frame's pixels. DOWNFORCE's final check rendered sixteen pairs in different orders, and all sixteen matched to
  the pixel.
- A full-film worker crosses chapters, so one canvas made without the software flag makes every later chapter's frames
  depend on what rendered before. DON'T LET ME SCROLL made every 2D canvas in the film software-backed after one chapter's
  canvas was promoted to the GPU and later frames drew their edges differently.
- The history check passes a worker whose own state went stale; [tool 43](#43-the-single-frame-outlier-scan) finds it.
- Three orders find more than one. AERO's engine renders a span in order, shuffled and on a cold page in reverse, and
  compares the bytes. It caught three traps that a single order hides: Chromium decoded a JPEG drawn small at a reduced
  scale only when no full decode was cached, so a small picture depended on render order (every picture now goes through a
  1:1 software copy first); caches keyed by a scale under an eased camera made a bitmap depend on which frame drew it first
  (key caches by content); and drawing a WebGL canvas onto the output switched Chromium's raster path, after which every
  later frame differed (read WebGL frames back into a software canvas).

### 21. The flash check

This follows WCAG 2.3.1's general flash threshold.

- Read the video at 96 × 54, 24 fps, in linear relative luminance.
- A flash is a pair of opposing changes of at least 10% of the range, where the darker state is under 0.8, over at least
  a quarter of the frame.
- Fail any one-second window with more than three flashes. Count pairs, not transitions: an early version counted each
  transition, so 2.2 flashes a second read as 4.4.
- Flashes belong to a theme, on hits: "dont need to force flashing".
- **Find single-frame pops.** A fast camera pass through bright glass is a flash. AIRPLANE MODE's dive through visor after
  visor failed at four flashes in one second: as each lit rim rushed past the lens, the mean luminance jumped for one
  frame and fell back (0.147 → 0.226 → 0.165). Flag any frame whose mean luminance differs from both neighbours in the
  same direction by more than 0.03, and ramp such passes over three frames or more.
- **Run it per chapter,** on anything fast, not only on the master: that dive was found after the encode.
- **Report a failure** with its time and cause when the film is delivered. Shipping it anyway is the director's call,
  never the production's.
- **Flashes as cuts only.** DOWNFORCE puts every white flash on the first frame of a cut and never inside a held shot,
  and its board checker fails a flash that isn't on a cut. The film has 13 white flash frames and at most 2 flashes in
  any second. DON'T LET ME SCROLL: 6 flashes, every one a cut, at most 1 in any second.
- **The flash check passes a strobe; scan for it cell by cell.** Cut the frame into a 16 × 9 grid (120-px cells at
  1080p, read at 192 × 108) and take each cell's mean luma per frame. A strobe is a run of 4 or more frame-to-frame
  changes that alternate in sign, each over 8 levels: a passing object gives a run of 2, aliasing rows give long runs.
  DON'T LET ME SCROLL's tunnel passed the flash check while 29 of its 144 cells alternated light and dark for nine
  frames: the near cards swapped bright and dark every frame, and only the largest were smeared. The near cards now
  fade, every card smears, and the scroll is capped. After the fix, every frame the scan flags is a whip or a swipe.

### 22. Pace against the music

Picture motion is the mean absolute frame difference of the review copy at 160 × 90 grey, per section. Compare it with
each section's stem energy and its kick and hat onsets per bar. Busy picture over quiet music reads as "off pace". The
fix on one film halved the cuts (0.92 → 0.47 a bar) and slowed in-shot motion until the picture followed the music.

When a cut feels wrong and the totals don't say why, measure what the viewer sees between visible cuts, section by
section, and re-cut by what each shot holds ([tool 58](#58-the-pacing-analysis)).

### 23. Contact sheets and the reviewer

**Contact sheets** are how agents look.

- **Per chapter:** every shot's first, middle and last frame; every lyric line's first and last word; every hit; each
  graphic's entrance; each transition's middle.
- **The reviewer** sees at least 24 frames, plus full-size stills of the five most important moments.
- **The whole film:** mid-shot frames of every shot, 6 × 24 to a sheet, plus the seams and 100% crops of faces.
- Open every sheet. A sheet nobody looked at is not a review.

**The reviewer** renders and looks for itself, and never edits files. It scores four lenses, 0–10:

- **taste:** the director's taste, which counts double;
- **craft;**
- **sync;**
- **story.**

It returns at most 12 concrete fixes, each marked blocking or polish, and copies the lyric gate's printed line.

**The verdict is computed in code, not taken from the reviewer:**

- A chapter passes when no blocking fix is left, taste is at least 7, the other three lenses are at least 6, and the gate
  reads N/N.
- A review that returned nothing, or never looked at a frame, is a failed review, never a pass. The original scripts read
  an empty review as "no fixes", and runs that hit a usage limit reported success.

Run at most two review-and-fix rounds per chapter. Calibrate the reviewer on the director's verdicts: on CLODYSSEY the
reviewers scored 6–7.5 a cut the director called "perfect. change nothing."

**The checker, after a round of notes.** When the director has sent notes, a lens score is the wrong question; the
question is whether each note was done. AIRPLANE MODE's last rounds gave every chapter a checker that hadn't built it:

- It reads the director's notes and the chapter's notes, including every UPDATE line.
- It renders sheets at every note's moment (before, at and after) and at every shot's first and last frame, plus two
  to four full-size stills, and looks at all of them.
- It returns each note as done or not, with what it saw; everything broken (blank or black frames, a flash inside a
  scene, type off its surface or illegible, an off-model face, a missing level tag, over-cutting where the notes ask to
  linger, a cut that left the beat); and what is pending on an asset that hasn't landed, which is not a failure. The
  format is in [Data formats](https://claudia.gallery/wiki/formats/#a-check-against-notes).
- It never edits files. A failed check sends its open notes and broken items back to the animator, first in its prompt,
  for one refix.

**Two reviewers at once, then a verifier.** DOWNFORCE gave every chapter two reviewers that render their own sheets
(they don't trust the builder's) and run in parallel:

- an **art director:** every shot's middle and every cut's first frame, a strip at every eighth of a second through the
  fastest three seconds, full-size stills of the six most important frames; energy, cuts and moves on the hits, the
  type as composition, the picture right (no frame outside a take's window, no wrong car, her lips closed, no invented
  text);
- a **QA checker:** the lyric gate, the history check, every generated frame the chapter draws against its take's
  window, every number on screen against the readings, cut times against the hits (within one frame), scene coverage,
  the flash rules, the first and last frames rendered without errors.

Each returns blockers (time, what, fix), ranked improvements, and what to keep. A fixer applies every blocker and the
improvements that don't conflict with the board or the director, a verifier re-renders and checks every first-round
blocker, and a second fix runs only if blockers remain. Five of DOWNFORCE's eleven chapters needed it.

**The whole-film critic.** After the chapter rounds, one agent renders the whole film and judges the film rather than a
chapter: the arc, repeats across chapters, the type system, the seams (every frame from 0.25 s before to 0.25 s after
each), and every one of the director's notes, re-rendered frame by frame over its range and looked at adversarially. Its
issues go to one fixer per chapter, then a final check runs the gates on the whole film. On DOWNFORCE it found a blocker
no chapter-level review had caught: a fixer had swapped an off-model close-up on another set into a held shot.

**Fresh eyes, one sheet per shot.** FABLE had no chapters and no lens scores: before each delivery two reviewers who had not
seen the film went through one sheet per shot, eight frames as the cut shows them, and full-size frames, and every finding
was fixed or listed for the director ([tool 88](#88-two-fresh-eyes-reviews)).

### 24. The safety and canon scan

**Job.** Look at every generated take before release.

**How.**

- Make sheets of frames per take.
- List every take checked, and every problem with its severity: block, fix or note.
- Whitelist intended props by name.
- Re-scan every re-make.

On CLODYSSEY the scan found 12 blocks in 96 "final" takes, among them nudity through a corset, modern objects and
earmuffs.

## Delivery

### 25. Encode and deliver

**The master.** Frames are sRGB, so convert through RGB with accurate rounding to BT.709 and tag the stream:

```sh
ffmpeg -framerate 24 -i frames/f%05d.jpg -i song.wav -map 0:v -map 1:a -c:a aac -b:a 256k -shortest \
  -vf "format=rgb24,scale=flags=accurate_rnd+full_chroma_int+full_chroma_inp:out_color_matrix=bt709:out_range=tv,format=yuv420p,setparams=color_primaries=bt709:color_trc=iec61966-2-1:colorspace=bt709:range=tv" \
  -colorspace bt709 -color_primaries bt709 -color_trc iec61966-2-1 -color_range tv \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -movflags +faststart master.mp4
```

An untagged or BT.601 stream looks lighter and washed out in QuickTime ("stuff is v blown out").

- **The review copy:** the same, with `-crf 20 -maxrate 8M -bufsize 16M`.
- **Verify with ffprobe:**
  - codec, 24/1, and a frame count equal to duration × 24;
  - bt709 / iec61966-2-1 / tv;
  - AAC stereo;
  - no container tags beyond the encoder's own.
- **Then run the flash check on the master.**

**The 9:16 cut** follows a subject box per plate, so an off-centre lead stays in frame. It gets its own lyric gate.
FABLE's 9:16 edition is a page instead: a square of each shot round its subject on a cream page, with the sung line
printed under it ([tool 87](#87-the-annotated-edition-and-the-916-page)).

**Two pitfalls of the frame folder:**

- **A file's data must be what its name says.** AERO's first 1:20 linked `.png` names to frames that were JPEG data; ffmpeg's
  image2 demuxer dropped every one of them, and the encode came out 1,325 frames long instead of 1,949. Convert to the
  named format, and count the decoded frames against the sequence.
- **A picture that starts before the song** gets negative frame numbers (`f-0064` … `f-0001`, then `f00000` on the song's
  first sample), so every frame keeps its song time and film frame k is song frame k − 64. Every tool that reads a frame
  range must parse a leading minus, and a command line must not take it for an option (`--frames=-64-1884`).

**Housekeeping:**

- Run encodes as tracked background jobs, never a detached process nobody watches.
- Delete the frames only after ffprobe has confirmed the outputs.
- Keep big scratch on the big disk.

## Running agents

### 26. Workflows, run records and the stop switch

The films ran their heavy stages as multi-agent workflows (Claude Code):

- **storyboard:** three director agents, three judges, and a merge;
- **chapters:** an animator, an art director who renders and reviews contact sheets, and a fixer;
- **research and lyrics:** topic researchers, fact verifiers, writers and judges;
- **the safety scan.**

DOWNFORCE ran seven workflow runs and 172 agent launches: the storyboard (three director agents, three judges, a
head director), the engine kit (four builders, an integrator, three reviewers, a fixer), a plan for the second round of shots
(three scouts, a head director), the chapters in three parallel runs (per chapter: a builder, an art director and a QA
checker, a fixer, a verifier), and a whole-film pass (a critic, fixers, a final check).

DON'T LET ME SCROLL ran 32 agent launches and no judged workflows: two surveys of the library (the moodboards, the
earlier films' looks), five kit builders in parallel from one written contract, one animator per chapter with its own
art-director passes (15 launches for nine chapters, six of them relaunches after interruptions), and ten for the second
version. In its last rounds the director asked for fewer reviewers: "we dont need excessive 'reviewers' after, ill stay in
the loop and can do a visual review faster and more comprehensively than an opus reviewr can do it."

WHITEPILL had no chapter animators: its frames are model takes and shader renders cut on the bar map. Its agents wrote
rival shader worlds in rounds, each round kept beside the last as a fallback, and a critic agent watched the previz as
the director would, returning ranked notes in three rounds, then a final QA and a last check before it went out. It ran
31 agent launches: 3 researchers and the 7 they launched, 3 lyric writers, 13 shader builds, 5 critics and QA passes.

THE CAKE IS NOT A LIE's restart ran as teams by role, each given the brief, the story, the production spec and the
storyboard so that none lost the whole film: the song and glitch map, the recordings in Portal 2, the character sheets,
Midjourney (the test and the library), the overlay, her singing in the chamber, and one team per act; the lead kept the
story and the cut. Its later rounds of notes went to specialists, each with a written brief and the lead's review at full
size before the director saw anything: a HUD designer ([tool 55](#55-a-hud-from-one-visor-and-one-projector)), a colourist
([tool 57](#57-the-per-shot-grade)), a pacing analyst ([tool 58](#58-the-pacing-analysis)) and a motion designer
([tool 60](#60-a-memory-film-with-her-own-face)). It ran 24 agent launches in all.

AERO's agents are recorded by role only: researchers (the knots between the era and 2026, the picture, the music, the
interface's sounds), the engine's builders (its foundation, the apps, the full-screen screens), eleven chapter animators and
the fixers who carried the reviews' notes, a fresh art director for every chapter pass and one for the whole film, a sound
designer, a world builder in Blender, a takes agent (imports, lip checks, keys), a texture agent and a coordinator for the
last passes. The number of launches is not in its records. The animators worked to one written contract, which quotes the
director's line on lazy animations and asks for three full rounds of the animator's own checks before a chapter is handed in
([tool 66](#66-chapters-on-one-machine-to-one-contract)).

FABLE dropped the multi-agent shapes as patches for older models: one author wrote the plan, the board, every prompt and
the cut in one context. Its agents, by role: five researchers for the plan (the week's AI news, the culture, the series
and its field, the newest video and image tools, the sound), three painter agents for the plates ([tool
76](#76-set-plates-painted-in-svg-rebuilt-as-paper)), and two fresh-eyes reviewers before each delivery ([tool
88](#88-two-fresh-eyes-reviews)).

**Rules that cost time to learn:**

- **Save every run's id and arguments** the moment it starts, and resume by run id in the same session. Finished agents
  replay from cache. An interrupt kills every running workflow, so keep phases short; ESCAPE VELOCITY's merge restarted
  three times. DOWNFORCE's three chapter runs were interrupted three times and each time resumed from where they stopped:
  only the agents that had been cut off ran again (57 of 147 launches), and no work was lost.
- **Build the kit before the chapters.** DOWNFORCE's four kit modules (compositor, footage player, lettering, data
  graphics) were built in parallel by four agents, joined by an integrator, reviewed for taste, correctness and speed,
  and closed out by a fixer who wrote the kit's manual, with one worked-example chapter that calls every function. Every
  chapter agent read the manual first and never edited the kit; kit bugs were reported, not patched.
- **Send the rough cut before the polish.** DOWNFORCE's first cut went out with every chapter at its first build, before
  any review, rendered from a frozen copy of the chapter files because the reviewers were already editing them. The
  director's notes reached the agents while the review rounds were still running.
- **A notes file survives an interrupt.** Each of DON'T LET ME SCROLL's chapter animators kept a notes file as it worked;
  six launches were interrupted, and each relaunch picked up from the file where the last had stopped.
- **Check that every agent actually finished.** A run can report success while agents that hit a usage limit returned
  nothing. Carry open items forward explicitly.
- **Parallelism has a ceiling.** On 4 CPUs, run two agents a workflow. Allow one rendering workflow at a time: six
  rendering agents filled the swap and the root disk.
- **Put long lists in a file,** not in the launch arguments: a placeholder once launched in place of 96 paths.
- **One workflow per chapter.** Resuming a multi-chapter workflow replayed its stages unevenly: some finished chapters
  were reviewed and fixed again. One chapter per workflow keeps an interrupt to one chapter.
- **Notes live in files the agents re-read.** Each chapter has a notes file for the round; the lead appends dated UPDATE
  lines as assets land (a take registered, a shared tool finished, a hand-off changed), and every agent re-reads its file
  before it finishes. Format: [Data formats](https://claudia.gallery/wiki/formats/#a-directors-notes-on-a-cut).
- **Build around what hasn't landed.** A chapter lays out a pending take or tool at its planned timing with a stand-in,
  keeps the name of what it waits for in one place, and swaps it in when it lands. Nothing waits for everything.
- **Write the seams down.** Each chapter's notes state its hand-offs: the exact colour of its last frame, where the level
  tag sits on both sides of the cut, which function returns a box the next chapter needs. Use the returned box, never a
  copied rectangle.
- **The stop switch.** On any quality complaint from the director:
  1. stop every job and workflow that can spend, after searching each running script for its generate calls;
  2. confirm at each provider that nothing is queued;
  3. log the director's words as a rule;
  4. fix the prompts, then re-make. Don't review the bad takes.
- **Write the acceptance test before the brief,** and make the check something the worker can't edit. Every human
  observation becomes a metric the same day: "if a reviewer can see it and the judge cannot, the judge is wrong".

## Worlds inside the film

AIRPLANE MODE, the fourth film, added these: tools for a story with simulations inside it, and for graphics it had to
rebuild rather than imitate. Build them only if your story needs them.

### 27. The level table and the level tag

**Job.** Show on every frame which level of the story the viewer is in, from one table.

**In → out.** The levels table ([Data formats](https://claudia.gallery/wiki/formats/#the-levels-table)) and song time t → the tag on the
overlay, or nothing in the real world.

**How**, with the constants used:

- **Placement:** drawn last, in a corner, 64 px from the side and 54 px from the top or bottom at 1920 × 1080; the
  number 28 px tall, the caption half that. Where an interface fills the frame, move the tag clear of its title bar.
  Change the corner only on a cut, and match it across chapter seams: the same corner, margins and backing on both sides.
- **Two styles:** for the realistic levels, a mono tag: a 1-px white frame with corner ticks in the accent over a faint
  navy backing, SIM LEVEL in white, the number in the accent. For the game levels, the game's pixel font on its
  640 × 360 grid, scaled 3× with nearest-neighbour.
- **Motion on the beat grid:** captions type at one or two characters a frame; a number that lands and holds rolls its
  changed digits over three frames, eased; a racing counter updates in place on the sixteenths, exponentially (2 to
  1,048,576 in about five seconds).
- **States:** BOOT (the frame draws on in four frames, then one caption row per beat), SPAWN (SPAWNING SUBAGENT… typed,
  a bar filling on the sixteenths to the drop), CLIMB (the race), GLITCHOUT (the tag torn into nine slices that slide
  apart, the colour split in position only, the backing kept dark, then nothing).
- **Hidden** while a full-frame card interrupts the simulation.
- **Never a flash:** the tag ramps, types, rolls, or cuts with the shot.

**Done when** every frame's tag matches the table, the real world shows none, and the tag never sits over a lyric or an
interface's title.

### 28. Virtual her: a cut-out in a world rebuilt from its edges

**Job.** Make a realistic take of her read as a simulation without touching her face.

**In → out.** A take or a plate, and its per-frame matte → the frame: her, photoreal, inside the matte; the world outside
it redrawn as cyberspace.

**How**, with the constants used:

1. **The matte.** SAM 2 with a box prompt, then BiRefNet (HR matting) and ViTMatte for the edge. A second box for a
   headset or a hand the first one loses; close the seam between the two with a small morphological closing. Grey
   mattes at 960 × 540, numbered like the take's frames.
2. **Her cut-out.** Decontaminate the matte's partial pixels: solve I = aF + (1 − a)B for F, with B the local
   background colour, so no halo of the old window stays in her hair.
3. **The world from its own edges.** The frame's luma at 960 px wide, blurred four times with a [1 2 1] kernel, then
   Sobel, non-maximum suppression and two thresholds (4.2 and 19 luma levels per pixel at that width) into anti-aliased
   lines from deep blue through cyan to near-white, with a blurred glow, over navy-black. Suppress the edges on and just
   around her (the matte, dilated).
4. **Depth.** The frame's own light as a dim blue ghost (luma^1.9); a wireframe corridor (floor, ceiling and walls)
   receding to the shot's real vanishing point, its rungs flowing toward the camera; short columns of hex glyphs rising
   slowly, a few in the accent; about 90 particles.
5. **On her.** A fine cyan rim from her own alpha, a² × (1 − box3(a)), 1–2 px wide; a soft blue halo outside her; light
   wrap from the blurred cyberspace behind; 4-px scan lines and one slow scan band every 3.2 s.
6. **The boot.** An amount from 0 to 1 converts the real frame to cyberspace tile by tile (32-px tiles), outward from
   her head.
7. **Cost.** Cache the analysis per source frame and matte (four entries are enough): about 0.3–0.4 s a frame when the
   source changes every frame, 0.14–0.2 s on a still plate.

**Done when** her face, hair and hands are untouched at 100%, nothing of the old background clings to her edges, and a
contact sheet of the shot reads as virtual at thumbnail size.

### 29. Character replacement from a motion reference

**Job.** Her avatar performing a move animated in 3D, in the film's look, without a finished 3D model of her.

**In → out.** A shot's clay render, the avatar's front view and turnaround, a still of the avatar in the shot's world →
a silent 720p take, then the shot's frames for the game look.

**How:**

- **The clay render:** a grey figure in a grey world with the shot's real lens and camera move, the sound stripped,
  4–15 s (the shot's length rounded up to whole seconds). Keep a hash of it in the clip file, so a re-render is noticed.
- **The world still:** one per shot, made in Midjourney with a frame of the shot's current version as the style
  reference and the avatar's front view as the image reference.
- **The prompt:** the template in [Seedance](https://claudia.gallery/wiki/seedance/#replacing-a-stand-in-figure). Per shot, only the goal
  sentence, what the world still shows, the timeline and the props to leave out change.
- **Post:** frames at 24 fps, area-downscaled to 854 × 480; a light unsharp mask (radius 1.2, 80%), then
  nearest-neighbour to 640 × 360, shown at 3×.
- **Screen every take** before it replaces a shot, and re-measure everything a chapter measured on the old frames
  (corners, masks, anchors), or write it so it doesn't depend on the take.

**Done when** every frame shows the avatar on-model (adult proportions, one streak, the headset, the suit), the motion
and camera follow the clay render, and no stand-in figure or retired prop survives.

### 30. A real referent, rebuilt

**Job.** When a line quotes a famous graphic or a real interface, put the real one on screen, rebuilt in code.

**How:**

1. **Research first.** An agent collects real frames or photographs, writes down what each one shows and what is still
   unverified, and lists where your current version departs from the real thing.
2. **Measure** positions and sizes as fractions of the frame, the palette sampled from the frames, the motion frame by
   frame (the scale on each frame, the holds, the cuts) and the typeface.
3. **Clear the typeface.** Use the original only with a licence, and never a pirated clone. Otherwise take an OFL face,
   squeeze each letter to the original's measured ink width, and draw any wear in code, fixed from frame to frame.
4. **Write it as a function of song time,** with the film's timings as presets: words land on their sung times, punches
   on hits.
5. **Replace the original's flashes with motion:** no white frames, no brightness pops.
6. **Keep it whole:** full frame, one card per line, never split, tilted or shrunk into a scene. Put the film's own mark
   where a logo isn't yours to use.

**Done when** the same code rebuilds one of the reference frames and the two match side by side.

## Real footage

DOWNFORCE, the fifth film, is cut from real footage: Tesla's livestream of the Roadster demo and SpaceX's 2018 Starman
footage, with generated 3D moves that start on its exact frames and Claudia as the pilot. These tools read the footage,
lock graphics to it, keep the generated takes honest and board an edit around it. Build them only if your film is cut
from real footage.

### 31. Reading a broadcast's telemetry

**Job.** Turn the numbers a broadcast shows on screen into data, so every graphic and every number in the lyric is a
real reading, never an estimate.

**In → out.** The broadcast at its highest resolution → one series per gauge, `[source time, value, interpolated]` at 20
readings a second, cut into the stretches where the readout is on screen ([Data formats](https://claudia.gallery/wiki/formats/#readings-off-the-footage)).

**How**, with the constants used on Tesla's 4K feed (3840 × 2160; its readout in a band along the bottom: DOWNFORCE in
kg, later G-FORCE in g, on the left; PITCH in degrees in the middle; ALTITUDE in feet on the right):

1. **Boxes.** Measure, once, a box around each gauge's value and one around its label, in source pixels. The digits
   there are white on black, about 64 px tall, in a square-cornered face with a slashed zero.
2. **Templates.** Read a few frames by eye (five were enough), cut their value boxes into glyphs, and store each glyph,
   resized to 28 × 44 px, under the digit it shows.
3. **Glyphs.** Per frame, threshold the value box at 150 of 255 and split it into 8-connected components. Drop specks
   (under 25 px) and anything over 90 px in either direction (the gauge's arcs, light streaks). Keep the text line:
   components at least 40 px tall whose centres sit within 20 px of the median. A small component (under 20 px both
   ways) on the baseline (within 10 px) is the decimal point.
4. **Digits.** Resize each glyph to 28 × 44 and compare it with every template by normalised correlation, both
   mean-subtracted. The best template names the digit; the reading's confidence is its weakest digit's score.
5. **Which gauge.** Where a gauge changes what it measures, count the ink in its label box: DOWNFORCE is wider than
   G-FORCE.
6. **Clean, never guess.** Drop readings under 0.85 confidence, and any reading off the median of its five neighbours
   by more than max(25% of that median, 3 × their median absolute deviation + 0.6). Fill the gaps linearly and flag
   every filled value. A value crossed by a light streak comes out flagged, not invented.

Measured on DOWNFORCE: 1,191 instants in three stretches (the wall, the flight, the kickflip), 3,081 values, 28 of them
flagged and interpolated. The peaks: 4,709 kg, 170.0° and 69.1 ft on the wall; 0.4 g at 68.0 ft leaving the ramp; 3.3 g
on the touchdown; 3.6 g at the kickflip's launch, with a 26.2 ft apex.

**Use.**

- A live card shows only values the readout showed at that source time; a number that counts up counts through real
  readings. A gauge's peak hold takes the highest reading between two source times (a beat ago and now).
- Write the lyric off the readings: DOWNFORCE's "up the wall at ninety" is 89.7°, "Sixty-nine feet" 69.1 ft.
- Turn type and pictures by the measured angles ([tool 33](#33-graphics-locked-to-the-footage)).

**Done when** crops of the readout beside their readings agree by eye at the peaks and across every flagged stretch,
and every number the film shows can be looked up at its source time.

### 32. Tracking the subject in the footage

**Job.** The real car's box in every real shot, so graphics can ride it: a callout, its dotted path, a punch-in that
keeps it in frame, words that pass behind it.

**In → out.** The real clips as frames, each clip's cut list, a few seed points per shot → per clip, 12 samples a
second, `[u, v, w, h, conf]` in fractions of the image, or null where the car can't be seen (smoke, flare, out of
frame).

**How.** Mask the broadcast's readout and titles first, and work at 1440–1920 px wide (half of the 4K frames, the 1080p
ones as they are). Each shot gets the method that suits it:

| Method | When | How |
|---|---|---|
| empty set | a locked-off or slowly zooming camera | the median of the shot's frames is the set without the car (align a slow zoom first: affine ECC, chained out from the middle frame); the car is what differs from it by more than about 26 levels, compared with the local max and min of the empty set so a pixel of misregistration doesn't count; on a white wall a blob must also carry a dark core (glass, shadow), which light pools and flares don't |
| bright | the car against the dark | bright, unsaturated pixels (HSV value over 150, saturation under 90), closed into blobs, only near the seeds |
| manual | the car fills the frame | key boxes read off the frames, interpolated (confidence 0.6) |
| from | another clip carries the same feed | that clip's track, shifted in time and mapped in space |

- **Candidates:** every blob near the seed path, its holes filled (the dark glass inside the white body), thin rows and
  columns trimmed off (thruster jets, smoke wisps: keep the longest run of rows, then of columns, covering at least a
  quarter to a third of the best one). Each costs its distance from the seed, relative to the seed's size, plus half
  the log of its area against the seed's. Keep the best 12 per sample.
- **The path:** the cheapest path through each sample's candidates or null (Viterbi). A step costs its motion divided by
  (5% of the frame width plus half the car's own size, so a close car may move fast), plus 0.8 × |log of the area
  ratio|; a step longer than 4 is impossible. A null sample costs 1.2 and switching between null and a box 0.4, so smoke,
  flares and lost frames stay null instead of grabbing the wrong blob. Confidence is exp(−cost / 2).
- **Smooth** with a 3-tap median of the box edges.
- **Seeds** come from looking: a sheet of the shot's frames with their times, and the car's centre and size read off a
  grid where the track needs a start or a hint.

DOWNFORCE's PILOT ✶ CLAUDIA callout rides the box. A punch-in keeps the car's actual box inside the frame, inset 8%,
panning, and backing the zoom off where the picture's edge stops the pan. The kickflip's tracked path is dotted over the
lineup camera (valid only inside one static shot). A luminance key of the white car inside its box lets a lyric pass
behind it. A second tool paired the car's position on the wall with Tesla's altitude and pitch at the same instant.

**Done when** sheets of every tracked shot with the boxes drawn on show the box on the car, and null where it can't be
seen.

### 33. Graphics locked to the footage

**Job.** Graphics that stay on the real picture while the real camera moves: a line on a real edge, type turned by a
real angle, a label that finds the dark.

**How:**

- **Read the frame as drawn.** Draw the footage first, then measure what the graphic needs from those pixels, every
  frame. It stays a pure function of song time, because it reads only this frame.
- **A line on a real edge.** DOWNFORCE's opening hairline sits on the wall's real edge. Per row (every 6 px) of a region
  that holds the edge, take the first x where the next 24 px are at least 70% brighter than a threshold (0.25 of white;
  prefix sums, so a dark patch in the concrete or a thin light beam doesn't move it). Drop points more than 48 px from
  both neighbours, smooth with a 7-row running median and a 5-row mean, and draw the line beside the edge. The first cut
  drew the line once while Tesla's camera zoomed in. The director: "at like 4 seconds the ramp trace decouples from the
  ramp." Re-read from every frame, the line held; it was checked frame by frame over the zoom, at full size.
- **Type turned by the measured angle.** A line of lyric pivots with the car's pitch, read at the source time on
  screen: "Sixty-nine feet," hangs at the real 170°, and "and I'm not done" turns live from 104° to 166°.
- **The world turned instead of the car.** Turn the whole broadcast frame by the car's measured roll, and the car stays
  level while the set wheels round it (DOWNFORCE's chorus 2: 0 → −283°). Mirror the edges the turn uncovers, or go
  black.
- **Labels in the dark.** A callout chooses its label point in the darker part of the picture, never crossing the car's
  box or the lyric's boxes with its rows or its leader.
- **Keep the broadcast's own graphics out.** Frame above the readout, or slide the picture down with black above a
  feathered edge where the sky is black anyway.

**Done when** the graphic is checked on every frame of a moving shot at full size, not on a sheet.

### 34. Generated moves from real frames

**Job.** 3D camera moves that start on (and, where needed, end on) a real frame, so the generated shot cuts with the
real ones.

**In → out.** A real frame (for a repair, also real frames of the subject's other sides; for a keyframe move, the frame
it must end on) → a start frame and references → a take.

**How:**

- **The start frame:** a 16:9 window at a chosen centre and zoom, above the broadcast's readout, scaled to a
  1920 × 1080 PNG, with the broadcast's titles (rows of small white glyphs in the top 17% of the frame) found and
  inpainted. A video input for an edit gets the same crop and the same inpainting on every frame.
- **The prompt keeps the frame and moves only the camera,** and names nothing: the car is "a white electric sports car".
  The preambles are in [Seedance](https://claudia.gallery/wiki/seedance/#moves-on-real-footage).
- **Stay on the visible side,** or give the hidden sides as real reference frames, cropped tight on black, never
  generated ones.
- **Chain on real frames.** DOWNFORCE's real side view ends on a frame, a first-and-last-frame move runs from that
  frame to Tesla's real top-down, and the next shot starts on the same top-down.
- **Know the source's real picture rate before planning slow motion.** Tesla's "60 fps" feed carries about 24 distinct
  pictures a second: at 0.4–0.5× it steps at 10–12 pictures a second. Blend neighbouring pictures, and motion-compensate
  where both the car and the camera move.
- **Punch in on the sharpest source.** The 4K feed crops 2× to 1080p without loss; a 1080p source past 1.1× goes soft
  and blocky.

**Done when** the cut into and out of each move reads as one camera, and the subject inside the take's window is the
real one in every frame.

### 35. The usable window of a take

**Job.** Know, for every generated take, which seconds may be on screen, and prove that nothing else ever is.

**In → out.** Each take → a row on a contact sheet, a list of cuts, its black level, then a verdict and window in the
takes log ([Data formats](https://claudia.gallery/wiki/formats/#takes-and-their-windows)); at the end, a log of every frame drawn.

**How:**

1. **The sheet:** one row per take, six frames spread evenly (384 px wide) with their take times, and the black level,
   the 1st percentile of luma over those frames. Tesla's night footage sat at about 1, Wan's takes of her at about 14.
2. **The cut finder:** every frame at 96 × 54 grey and its mean absolute difference from the frame before; a cut is a
   frame whose difference passes max(12 levels, 5 × the take's median difference) and is the largest within three frames
   either side. It catches the model's own edits, not a slow morph (the car becoming another car, a set drifting): look
   for those.
3. **The verdict, by eye, against the board:** USE, PART (only part of it) or ALT (a usable alternate), and the window
   in seconds of the take, ending before the first wrong frame (a cut, another car, an invented set, lettering, an open
   mouth). Write down what goes wrong after the window, and when, so nobody stretches it.
4. **Extract** the take at its own frame rate with its blacks restored: luma [B, 255] mapped to [0, 255], with B the
   sheet's black level.
5. **A second, adversarial look** before more money is spent. DOWNFORCE's repair scout re-checked every take frame by
   frame, shortened seven windows, and found a man in the empty car's window and a repair that turned into a hatchback.
6. **Enforce it in code.** The chapters name, for every shot, the part of the take they play; the final check logs every
   footage frame the film draws and compares it with its take's window.

Measured on DOWNFORCE: 79 takes. The windows of the 25 Wan moves on Tesla's real frames all start at 0 s and end between
0.9 s and the full take (median 2.2 s). Every generated frame the film draws was inside its take's window.

**Done when** every take has a verdict and a window, and the log shows no frame outside one.

### 36. The board for an edit of real footage

**Job.** A shot list that tiles the song with real windows, generated moves and code, checked in code before anything is
spent.

**How.** A workflow:

1. **Three director agents** each board the whole song from a different angle, with every field of a shot and the list of
   generated assets with their costs. DOWNFORCE's: a TikTok car-edit editor (every stunt from several angles, speed
   ramps, the 3D moves as the money shots), a film director (the launch as a story: restraint, the reveal, each drop a
   set piece) and a motion-design lead (the readings, the lettering and the lines drive the edit).
2. **Three judges** score every board 0–10 on seven fields (the build and the launch, hype, 3D, taste, lyric coverage,
   feasibility, her) with a total out of 100, and list each board's eight best ideas and eight most important fixes.
   One judges as the audience and editor, one as the director's taste, one as a producer: do the named source times
   exist and show that, does every generated asset fit the budget, does every cut sit on the beat map.
3. **A head director agent** starts from the best-scoring board, grafts every listed idea that fits, applies every fix, writes
   the board, then writes a checker and runs it until it passes.

The checker's gates, beyond [the audit](https://claudia.gallery/wiki/storyboard/#the-audit):

| Gate | Fails when |
|---|---|
| windows | a real window outside its clip, out ≤ in, a speed outside 0.25–4× either way (negative plays it backwards), out − in ≠ duration × that speed, a crop outside the frame or into the broadcast's readout, a window across a cut in the source (cuts measured from frame differences), a window where a broadcast title sits over the subject (titles over black sky are flagged for masking) |
| lyrics | a sung line not lettered (micro type doesn't count) in the shots that overlap it, at least 80% of its words |
| flashes | a flash not on a cut, or more than three in a second |
| generated | an asset referenced but missing, or made but unused; a window past its take; the first roll over its budget at list price; a plate without the canon text verbatim or without "no text, no letters, no logos" |

It also reports her share (her image and the callout, separately) and the split of real, generated and code.

DOWNFORCE's TikTok board won (83, 80 and 83 from the three judges; the film-director agent's board 79, 79, 85; the motion board
75, 77, 81). The merge had 182 shots, a mean of 1.04 s: 59% real footage, 37% generated, 4% pure code. From the start of
the workflow to a passing checker took about two hours. A second workflow later planned the next round of shots: three
scouts (more 3D angles at the drops; her as the pilot reacting to the real stunts; an adversarial repair scout) and a
head director, who merged them into one ranked, costed list with every start frame extracted and checked.

**Done when** the checker exits 0, and again after every change to the board.

## Her takes in a world drawn in code

DON'T LET ME SCROLL, the sixth film, put her into a world the engine draws: her takes, shot on plain grey, are cut out
and played inside the code, timed to the beat. Then the film kept changing after the edit: takes were re-dressed in new
outfits, and finished shots were re-lit and repaired and spliced back into the cut's own frames. These tools do that.
Build them if her takes live in a world drawn in code, or if finished shots must change without a re-shoot. The outlier
scan belongs to any film that renders on several workers.

### 37. Outfit-swap alignment

**Job.** Put an outfit swap (a video edit that re-dresses an existing take) back on the original take's timeline, so it
drops in as the take's new pick with every beat warp and chapter timing unchanged.

**In → out.** The original take and the edited clip → a new take file at the original's frame rate and frame count, and
the fit with its check, printed.

**How:**

1. **Know what the edit returns.** A Seedance 2.5 video edit returns the whole motion, uniformly rescaled to its own
   quantised length, at 24 fps. A 5.0 s Wan take at 1080p (150 frames at 30 fps) came back as 113 frames, 4.709 s: the
   same motion from the first frame to the last at 0.942 of the length, with no head trim and no offset. A 720p Seedance
   take (121 frames at 24 fps) came back as 121 frames.
2. **Map it back by the ratio of the lengths.** Original frame i shows edited frame round(a · i / f_o · f_s), with a the
   edit's duration over the original's and f_o, f_s the two frame rates; nearest frame, no blending. Write the frames at
   the original's size and frame rate (CRF 12) as the take's next number, and make it the pick.
3. **Check the fit on what the edit doesn't change.** Her hair: the glossy black (grey level under 45 of 255) in the top
   40 % of the frame, its centroid's x and y per frame, and her body's x (pixels more than 40 levels from the backdrop,
   the border's median colour). Read both clips at 135 × 240, normalise each signal and correlate them under the map. A
   finer search (the scale within ± 0.04 in steps of 0.005, an offset within ± 0.25 s in steps of 1/96 s) overrides the
   ratio only when it is clearly better (Δr ≥ 0.03). On DON'T LET ME SCROLL's eight shirt swaps the ratio held, with
   correlations from 0.71 to 0.998.
4. **Never fit the outline.** The first swap was fitted on her silhouette. The new skirt changed her outline, and the fit
   read 0.36–0.5 s missing from the start and the rest running 4–6 % fast (a scale of 1.060 and a shift of 0.5 s); the
   shot went in with a frozen half-second until it was aligned again.

**Done when** the swapped take plays inside the original's beat warps with the same pose on the same beat: the two takes
side by side at several moments match, and the hair's correlation is printed with the fit.

### 38. The re-light splice

**Job.** Re-light, re-texture or repair a finished shot with a video model, and put the result back into the cut over
exactly the frames it was made from.

**In → out.** A version of the rendered film (its frames on the render box) and a window in song time → a source clip and
its record; later, the model's clip → the window's frames replaced, the originals kept.

**How:**

1. **Cut the source from the final render's own frames,** never from an earlier stage, so it can't drift from the cut:
   frames round(t0 · 24) to round(t1 · 24) − 1 at 24 fps (CRF 10), with an optional handle on each side that is never
   written back. Record the window: `{"ver", "t0", "t1", "i0", "n", "pad", "frames"}`
   ([Data formats](https://claudia.gallery/wiki/formats/#takes-in-a-world-drawn-in-code)).
2. **Round the source up to 4n + 1 frames,** taking the extra frames from the real frames after the window, and to at
   least 89. Seedance returned a 24 fps source of 4n + 1 frames frame for frame (121, 89, 89 and 161 frames; 189 came
   back as 185), and nothing shorter than 89 frames (3.709 s): 79- and 96-frame sources both came back as 89. Wan keeps
   its input's length in whole seconds: pad its source to a whole number of seconds with the last frame held.
3. **Write it back.** Window frame k takes delivered frame round((k + pad) · (n_r − 1) / (n_s − 1)), with n_r the frames
   delivered and n_s the frames sent, which absorbs any rescale. Copy every original frame aside first; an undo puts
   them back. A window that doesn't start or end on a cut cross-fades over a few frames.
4. **Keep what the model must not touch.** A re-light softens small type ("a touch softer, still clean and legible") and
   can smear a card outright. Fixed rectangles keep the original pixels, feathered (a Gaussian of half the feather, 24 px
   by default): the status bar, the Dynamic Island, an interface platter. A card that moves gets a rectangle per frame,
   tracked: `{"<frame>": [[x, y, w, h, feather], …]}`, rounded rectangles of radius 28 with a feather of 12. DON'T LET ME
   SCROLL tracked a notification card over 48 frames this way.
5. **Colour-match a Wan pass first** ([tool 39](#39-the-colour-match)).

Ten splices went into DON'T LET ME SCROLL's final, four Seedance re-lights and six Wan passes, from 28 frames (a 1.2 s
bridge whose flat blue background Seedance replaced with a glass atrium) to 188 (the lock screen's digits re-lit as
ray-traced liquid glass).

**Done when** the window's frame count matches, the cuts on both sides show no seam on a seam sheet, the kept rectangles
hold their original pixels, and the undo restores the cut exactly.

### 39. The colour match

**Job.** Put a re-lit clip back in its source's palette, without flicker.

**In → out.** The source clip and the re-lit clip → a matched clip, which the splice uses instead.

**How.** Sample 24 frames spread evenly across each clip (at (k + ½)/24 of its length), at 480 × 270. Per channel, take
the mean and the standard deviation over all the sampled pixels; the gain g = σ_source / σ_relit, clamped to 0.7–1.4, and
the offset o = μ_source − g · μ_relit. Apply that one map to every frame (ffmpeg's `colorchannelmixer` for the gains,
`lutrgb` for the offsets, clipped to 0–255) and encode at CRF 12. One map for the whole shot can't flicker; a per-frame
match would.

Wan doesn't shift colour the same way twice. Bright paper scenes came back darker and cooler: S30's warm grey paper fell
from a mean of about 172 to about 111, red furthest, and the match brought it back to about 169. Dark scenes came back
brighter: S19's mean rose from about 34 to about 53.

**Done when** the matched clip's channel means sit within a few levels of the source's, and the two side by side show the
source's palette.

### 40. Wan 3.0 relight-and-repair

**Job.** Re-light a finished shot as a physically lit one and repair her body in it (limbs that leave the take's frame
completed, a stray limb removed), keeping every element in place and in time, so it splices straight back. The director's
method: "you could maybe just throw the entire clip thru Wan 3.0 (with your edits and stuff) and specify to remove the
foot so you dont have to re-edit. and have it relight at the same time."

**In → out.** The rendered shot as Video 1 of Wan 3.0's reference-to-video, optionally a face reference as Image 1 → a
re-lit clip of the same length and layout.

**How:**

- **The source:** the shot's own frames from the render ([tool 38](#38-the-re-light-splice)), then its last frame held
  to a whole number of seconds. 1080p, 16:9, 4–8 s.
- **The prompt opens** "Reimagine Video 1 as the same shot, physically lit and photographic. Keep every element exactly
  in place and in time: the same layout, positions and sizes, the same timing, every movement of the woman; the camera
  stays exactly as in Video 1, no cuts, no new objects, no added text." Then her description, the canon's short form
  with the shot's wardrobe; the repair; the light ("Re-light the scene as a real dark bedroom at night, lit by the cool
  glow of the giant glass clock numerals and the moon"); and what stays exactly as it is ("The clock numerals, the moon,
  the notification cards with their words, the status bar and the black Dynamic Island at the top stay exactly as in
  Video 1, sharp and legible").
- **The repair, as a sentence about her whole body:** "Her whole body stays complete in every frame: both arms end in
  complete, natural hands with five fingers, never cut off or faded at any edge, and both feet are complete." A stray
  limb: "Remove the stray bare foot and leg that appear beside her at the lower right of her body: there is nothing there
  but the dark room, and her body continues naturally below the frame."
- **A face reference fixes identity, not pose.** The re-drawn shots lost her face, so the director picked a reference
  (an earlier film's identity portrait, cropped to her face and hair so its clothes couldn't bleed in): "Image 1 is the
  face of the woman: keep her face exactly as in Image 1 in every frame … Image 1 is only a reference for her face; it is
  never shown as a shot." In one shot her chin was tucked into a sweater's collar, and her face still read full until the
  prompt added "her face is slim and angular, never round or full: slim cheeks, defined cheekbones and jaw, a slender
  neck, and her chin lifts slightly out of the sweater collar so her jawline shows".
- **Re-make from the original render,** never from an earlier generated pass. The director: "id just re-do the relighting
  with the face ref added from the original scene rather than rerunning the generated ai scene into it again."
- **Put the interface back.** Wan softens small type too: the stocks screen's interface and the status bar came back from
  the original render, as two kept rectangles.
- **Colour-match** before the splice ([tool 39](#39-the-colour-match)).

DON'T LET ME SCROLL made ten of these passes, at $0.20 a second at 1080p list for the clip and the same again for each
second of the input video ($2.00 for a 5 s shot). Six are in the final: a stray foot removed, a lost foot restored, hands
and sleeves that left the frame completed in three shots, and her face held to the reference in four.

**Done when** the pass, colour-matched and spliced, plays with every element where it was, her body whole in every frame,
her face on the reference and the interface's pixels the original's, judged in place in the cut, side by side with the
original.

### 41. Roto on a CPU box

**Job.** Her matte for every frame of a take, without a GPU, fast enough to feed the chapters.

**In → out.** A take's frames → `matte/f%04d.png` beside them (8-bit grey, full frame size), and a count that must equal
the frame count.

**How:**

1. **BiRefNet on keyframes:** the general-lite model (through rembg, no post-processing) on every 3rd frame and the last.
   On the render box's CPUs it took about 4.6 s a frame when run on every frame; with keyframes, about 1.6 s a frame, a
   take every four to five minutes.
2. **Optical flow between them.** For each frame between two keyframes, OpenCV's DIS flow (its medium preset, on a
   half-size grey copy) from this frame to each keyframe; warp each keyframe's matte backwards along it (bilinear, edges
   replicated) and blend the two by distance, (b − i)/(b − a) to the earlier keyframe. Hair edges and the headset cable
   survived it.
3. **Turn off onnxruntime's CPU memory arena** (`enable_cpu_mem_arena = False`, `enable_mem_pattern = False`). With it
   on, one 1080p roto held about 12.5 GB, and rotos died for lack of memory on a box shared with chapter renders; with it
   off, 1.3 GB.
4. **Fail loudly.** Never pipe the remote run through `| tail`: its exit status hid a roto killed for lack of memory,
   which came back with 35 mattes for 210 frames. Count the mattes against the frames, and stop when they differ.
5. **The full model for hard frames.** BiRefNet's general model recovered a motion-blurred back shoe that general-lite
   had lost.
6. **Shoot for it:** her alone on plain mid-grey, with the take wider than the shot needs. Limbs that leave a 9:16
   take's frame can only be faded at its edge. The director: "all your roto cutouts have blurred bounding boxes it seems
   and sometimes her limbs go outside of them and just disappear at the boxes edge". Wan completed them later
   ([tool 40](#40-wan-30-relight-and-repair)).

**Done when** every take has as many mattes as frames, and a sheet of the mattes over their frames shows her hair,
fingers and feet whole.

### 42. Beat warps floored at 1×

**Job.** Land her moves on the song's beats without ever slowing a take. The director on the first cut: "never slow these
down. you lowered the framerate for no reason, just looks bad."

**In → out.** A take's frames and mattes, the shot's window in song time and the beat map → a monotone piecewise-linear
map from song time to take time ([Data formats](https://claudia.gallery/wiki/formats/#takes-in-a-world-drawn-in-code)).

**How:**

1. **Her accents.** Per frame, the mean absolute difference of the grey frame (270 × 480) from the one before, inside her
   matte (the larger of this frame's and the last one's), smoothed over three frames. An accent is a local peak of its
   rise above the 80th percentile, at least 0.22 s after the last.
2. **A base map:** a speed in {1.0, 1.08, 1.16, 1.25} and a start offset in steps of 1/60 s, scored by Σ exp(−(d /
   0.07)²) over the accents, with d an accent's distance to the nearest beat.
3. **Pin the accents.** Each accent within 0.2 s of a beat moves onto it, as long as the speed between pins stays within
   1.0–1.45× and the pins are at least 0.1 s apart.
4. **Never below 1×.** A take shorter than its shot plays at 1× to its last frame and is flagged: it holds, loops on a
   matching pose, or gets a longer take. DON'T LET ME SCROLL's first warps had dipped to 0.70–0.89× in nearly every take,
   and one chapter's own map to 0.53×. With the floor, six shots were flagged short. One became a two-beat loop near the
   take's end (0.917 s, from 4.92 s back to 4.00 s of the take) where her pose repeats; the stutter became a sampler, the
   take at exactly 1× between triggers and each vocal chop re-triggering a cue point; two were taken again.

**Done when** every segment of every warp runs at 1.0× or faster, the accents land on beats, and no shot ends on a held
frame unless it was flagged and accepted.

### 43. The single-frame outlier scan

**Job.** Find frames that differ from both neighbours while the neighbours agree: the signature of a renderer that drew
one frame wrong.

**In → out.** The rendered frames → the frames that stand out, each with its difference from its neighbours.

**How.** Compare every frame with the per-pixel median of the frames around it, as the mean absolute difference. A
single bad frame stands far from that median while its neighbours sit close to it; a cut or a fast move shifts them
all. Scan at two thresholds, a strict one and a loose one, and look at every flagged frame beside its neighbours. A
pattern in the flags (every 8th frame, every frame of one shot) names the cause.

On DON'T LET ME SCROLL the director saw black vertical lines in one shot, "they appear occasionally, look at more framers,
the spaz out". The scan found dark columns on every 8th frame of the shot: one of the eight render workers had drawn its
share from a stale camera state. Rendered fresh, one of those frames differed from the worker's version by 21.5 levels on
average, and from its good neighbour by 4.0. The worker's 16 frames were rendered again, and a scan of all 3,859 frames of
the film found none left. Every other check had passed those frames.

**Done when** a scan of the whole final finds no frame that differs from both neighbours while they agree.

## A film shot twice, on the bar map

WHITEPILL, the seventh film, was shot twice. A performer model made a rough, lip-synced take of every shot of hers; then
Seedance 2.5 made each shot again as the master, singing from the song's own vocal stem, with the rough take shrunk to a
guide or with no guide at all. Its worlds are shaders, one rule each, photographed by the same video model. Everything
sits on the song's bars. These tools do that. Build them if she sings on camera, if your worlds are code that a video
model should photograph, or if your cut has to sit on the music.

### 44. The bar map as the timeline

**Job.** Write the film in the song's bars, so that picture and music are consonant: every cut on a bar line, every move
in bars. WHITEPILL's director on its first cut: "there is this temporal signature that screams claude now that a ton of
people are making the videos. people say pacing or prosody. i think it comes from a couple things. 1- youre not working on
an A/V timeline in the way we are in video programs. 2- things might not cut on the right beats? like, maybe we need the
beat structure and only have cuts at ends of bars or sections. like, the audio structure and video structure need to be
consonant. 3- i think you use cuttng to cover up imperfections from video models rather than for timing. 4- i think youre
not as aware of time as humans are, so time feels more like a number or concept or count rather than a duration."

**In → out.** The beat map's downbeats, the sections and the lines' times → the shot list in bars
([Data formats](https://claudia.gallery/wiki/formats/#the-shot-list-in-bars)); after every assembly, each cut with its bar and kind, and the
picture's motion against the arrangement, bar by bar.

**How:**

1. **Shots in bars.** Each shot is [bar a, bar b) of the song, one place per shot. Its camera note names bars, not
   seconds ("pushes in slowly and steadily until {b:5}; from {b:5} it cranes up"), and the tool that writes a take's
   prompt turns each {b:N} into that take's own seconds.
2. **Cuts only on bar lines,** and only at a section's start, a phrase line (2, 4 or 8 bars from the section's first
   bar) or the downbeat where a sung phrase begins, so the picture arrives with its line. A cut anywhere else is a
   decision, written into the shot list.
3. **Moves in bars.** A move starts on a downbeat and comes to rest on a downbeat, a bar before the cut where it can, so
   it settles before the next shot.
4. **The song sets the length, and the model fills it.** A shot longer than a model's limit goes in squeezed and comes
   back stretched ([tool 45](#45-a-previz-performer)). A failed take is made again, never cut around.
5. **The lyrics keep the same clock.** A line comes in half a beat before its first word and leaves 0.4 s after its last
   (or when the next line comes in). A line whose first word comes up to 0.4 s after a cut, or whose short pickup starts
   less than 0.35 s before one, comes in on the cut; a line that has ended leaves on the next cut.
6. **Measure every assembly,** at 160 × 90 grey:
   - **cuts:** a frame whose mean difference from the one before passes max(4 × the film's median difference, 18 levels)
     and 2.5 × both neighbours'. Each is listed with its bar and whether it falls on a section or phrase line or where a
     sung line starts, and every cut inside a sung line is listed with the line;
   - **motion against the music:** per bar, the median optical-flow speed (cut frames left out) against the energy of the
     drums, bass and other stems, and their correlation over the bars;
   - **sheets:** one frame per bar, ten bars a row, the first bar of each section marked; and the two sides of every cut,
     side by side.

Measured on WHITEPILL. Its previz: 42 picture changes (cuts and snaps inside shots), 95% on a musical onset within one
frame (42% by chance) and all of them on the beat grid, counted by an audio-analysis tool. Its final: 29 picture
changes, every one on a bar line, 28 on a section or phrase line or where a sung line starts; 4 inside a sung line, 3 of
those on section lines. Motion against the music: the first cut had scored r = +0.43 against the sections' loudness, and
the plan aimed for +0.7; the final scores +0.44 bar by bar against the arrangement, so that aim wasn't reached.

**Done when** the measure finds no cut off a bar line, every cut inside a sung line is a written choice, and the director
has watched the cut in real time.

### 45. A previz performer

**Job.** A rough take of every shot of hers, lip-synced and dancing on location, made as often as needed, as the guide
for the master. WHITEPILL's director: "i want you to basically shoot the entire video twice - you can previz with […]
and you can master with seedance AFTER you animate".

**In → out.** Per shot: the place with nobody in it, her face sheet, the dress, the vocal of the shot's window and, for a
dance, a real dancer's clip → one take of the whole shot, with no cuts.

**How**, with MiniMax H3, in its own reference format (what each input is, and what is kept of it):

- **A masked performer.** Her whole head is in a green chroma-key balaclava, her eyes and lips showing through its holes
  (taken from the face sheet's front view), and she wears the film's dress. The master redraws her face; the previz
  carries the motion, the mouth and the camera. The director: "you could make the initial shot be a like greenscreen
  person with a mouth that lip syncs and eye movements lol", and then: "honestly i think itd be better if the model was
  just the greenscreen model but in the real world, dancing, moving, etc - doing the entire thing. not in a green studio
  staying still."
- **The words exactly.** The prompt gives exactly the words heard in the take's audio, in order: a line the window cuts
  is marked "…", and every silence is described ("her lips stay gently closed and still … until her voice begins").
  Whole lines where the audio held part of one put her mouth on words that weren't there. No clock times in the prompt:
  they made the takes cut.
- **The vocal window** is silent before the first word the prompt names and after the last, and nowhere else: gating a
  gap inside a take cut a held 2.5 s note. A word sung across a cut belongs to both takes for as long as it is heard,
  within 12 dB of its peak (held notes stayed within about 11 dB; fading tails dropped 15 dB or more).
- **Words that open the mouth.** "Smile" in a take's mood drew a toothy smile in the silence before she sang, and "smiles
  between the lines" read as talking. The mood puts the joy in her eyes; the lips stay closed until the voice begins.
- **Dancers:** clips of adult dancers from public dance videos (one dancer, the whole body in frame, a still camera, a song
  within about 6% of the film's tempo), for motion only. Matte the dancer onto flat grey: given the whole video, H3 put
  her in the dancer's background for a few seconds. Re-cut each clip for its shot at (the shot's tempo / the clip's
  tempo) × the squeeze: one shared cut ran 2–4% slow, almost a beat behind by the end of eight bars.
- **Length:** at most 362 frames, 15.08 s. An eight-bar shot (15.5 s) goes in squeezed, its vocal sped up by
  q = length / 14.9, and the take is slowed back by q when it is cut in, so the lips stay on the song.
- **A calm camera,** one move or none, written in the take's seconds from the bar map
  ([tool 44](#44-the-bar-map-as-the-timeline)). WHITEPILL's first previz orbited her in every shot ("the camera should
  feel like it's on an industrial robotic arm"), and the director dropped it: "its kinda dizzying now and previz was too
  complex so h3 didnt keep up wtih the physics or consistency".
- **Only cut-free takes.** Several seeds a shot, each pick checked for jumps as well as cuts (an automatic cut check
  missed one). A seed doesn't pin a take: one seed with the same inputs gave three different takes.

What it couldn't do: its dance takes lost limbs where the dancer's matte had lost them, and a master copies what its
guide shows ([tool 47](#47-takes-with-no-guide-clip)). A whole-film reshoot in Wan 3.0 Prime over the full-resolution
takes was rejected: ":/ looks like shit. i feel like h3 is dragging it down." What worked was the take shrunk to
320 × 180, a rough guide for everything but the lips ([tool 46](#46-lip-sync-from-the-songs-own-vocal)).

**Done when** every shot of hers has a cut-free take whose mouth shapes the words of its window, read by eye on strips of
her face, each frame marked with the vocal's level and the word sung then.

### 46. Lip sync from the song's own vocal

**Job.** Her singing shots, lip-synced in the master itself: whole shots of up to 16 s, camera moves and all, with no
lip-sync model and no covers.

The method came from a tip in a public forum thread that the director found: give the model the vocal stem alone, type
the exact lyric line, make the clip exactly the generation length, and lay the music back over. The director on the
first take: "OMG THE SEEDANCE W/ SUNO VOCAL STEM METHOD WORKED!!!!! LFG!!!! FINALLY. IT"S PERFECT".

**In → out.** The shot's window in song time, Suno's lead vocal of the locked take, the shot's references → a take whose
mouth sings the window, with the song laid back over it.

**How:**

1. **The vocal from Suno itself.** Suno's stem split of the locked take (its Lead Vocal stem) matched the master to the
   millisecond: the same length and no lag. Check the stem against the master by cross-correlation (zero lag), not by
   title or length: the first stems came from the wrong takes, one of them matched to the song by its length.
2. **@Audio1 is that vocal alone,** with no music and no gating, cut at the shot's song time to exactly the generation
   length. Seedance takes whole seconds, d = max(4, the shot's length rounded up); a 16 s take gets 16.000 s of vocal from
   the shot's first frame. Check it with ffprobe.
3. **The exact lyrics in the prompt,** in plain quotes, in whole-second segments of what @Audio1 holds
   ([the template](https://claudia.gallery/wiki/seedance/#template-singing-from-the-vocal-stem)): each phrase once, with "the line is already
   under way on the first frame" or "the line goes on after the last frame" where the window cuts one, every silence as
   its own segment ("her mouth is closed and still"), and a word that only begins in the last instant left out. A word
   counts when at least 0.15 s of it, or half of a shorter one, is inside the window, with its end followed on the vocal
   stem (word times: [tool 5](#5-timed-words-and-the-ear-check)).
4. **References, each with one role:** her face sheet from every angle ("identity only, never shown as a frame"), her
   dress from four sides, the film's look ([tool 51](#51-the-look-from-one-take)), and either the previz shrunk to 320 × 180,
   scaled back up and padded to the same length ("a low-resolution rough guide to this shot, not a precise reference …
   only the lip sync is exact"), or no guide and the empty place ([tool 47](#47-takes-with-no-guide-clip)). Seedance 2.5
   on Higgsfield (References), 720p, 16:9.
5. **Lay the song back over** at song time. The take starts at the shot's song time, so the shot is the take from its first
   frame, at 1×; the take's own soundtrack is thrown away.

Measured: the first take (16 s at 720p with its 16 s guide, $8.87 at list on Higgsfield's API) came back on-model, the lips
on the words, the push-in and the crane up out of the wheat done as one move. The spectrogram comparison
([tool 15](#15-the-sync-check-the-spectrogram-comparison)) called its soundtrack re-sung rather than copied, matched only
from 7 s on, yet the singing sat exactly where the vocal is. The same shot, side by side: Wan 3.0 Prime singing to the song
shaped the words but hard-cut at 9.9 s instead of craning up, masked or not; Kling 4.0 kept a guide's motion frame for frame
and looked the most like film, but it takes no audio track, and her mouth drifted into a smile on the words.

**Done when** every singing shot, with the song laid over, reads in sync by eye at full speed. The director judges it
there, not from the numbers: "Just show it to me instead of using your eyes for the lip sync".

AERO's director made it the rule in the production ask: "vocal stem -> seedance 2.5 is the way we get lip sync to work - the
song alone doesnt help as much as vocal stem, and then aligning from spectrogram." Every take of hers that sings or speaks
had its window of the lead stem, a first frame on her design as @Image1 (an image-model edit from her sheet, or a frame of
an earlier take that continues the shot), and the sheet itself as @Image2. Its takes needed one more step: the model
shortens the pauses inside a line, so each phrase is measured and placed on its own
([tool 69](#69-lip-sync-phrase-by-phrase)).

FABLE kept the method and changed what feeds it and what places it: windows timed by the stem's level and gated by line
([tool 80](#80-the-shot-book-and-gated-windows)), each take aligned as a path
([tool 81](#81-sync-as-a-path-each-take-aligned-to-its-window)), and some of her takes made with the sound off, the vocal
still as @Audio1, and placed by her lips on the consonants ([tool 82](#82-takes-without-a-soundtrack-placed-by-her-lips)).

### 47. Takes with no guide clip

**Job.** Shoot a shot of hers with no reference video when a guide would be copied with its faults: limbs a previz dance
lost.

**In → out.** The place with nobody in it, her face sheet, the dress, the look, the vocal (or the music without it:
[tool 48](#48-a-take-that-doesnt-sing)), and the action, the camera and the dance in words → a take.

**How:**

- **The place plate:** a frame of the shot's earlier take with her removed by an image model (GPT Image 2.5), given as
  "@Image4 is the place of this shot, empty: take its set, landscape, layout, light and camera view; Claudia is the only
  person in it." Keep whoever belongs in the shot: the schoolhouse's plate kept the child at the desk ("keep the child as
  in @Image4"). The previz's places were made the same way in Midjourney, from the storyboard plates
  ([Midjourney](https://claudia.gallery/wiki/midjourney/#style-families)).
- **The camera in words,** as the earlier take did it where the director had seen that version, otherwise from the shot
  list.
- **The dance in words, beat by beat, with the tempo.** A 【Dance】 section opens "The song's tempo is 124.5 beats per
  minute (a beat every 0.48 s, a bar every 1.93 s); every step and accent lands on a beat. Her whole body dances, smooth
  and joyful, her arms, hands and legs always whole and clearly visible.", then one move per segment of one or two bars
  ("4-6s: the disco point: on the downbeat her right arm points up to the sky on the diagonal, then down across her body,
  then the left arm."). The core requirements add "her arms, hands and legs are whole and attached the whole time, never
  vanishing, merging or bending wrongly".
- **Name a removal only where the thing is.** A fix written for an earlier take ("Remove the thin red cord stretched
  between the apple trees") went into a prompt whose place had no cord, and drew one.

Why: the director on the first full cut, of four dance shots: "it must be that the roto or whtaever on dance refs lose
bodyparts and the video follows it exactly because these hav the same limb losing artifacts as h3 we could just tell the
model to make her dance instead of forcing a reference that we failed to properly roto. just describe her exact dance (and
all rest like camera movements etc same) for each of those scenes."

Measured: of those four, two are in the final reshot this way (2:27 and 3:10), and two became takes that don't sing
([tool 48](#48-a-take-that-doesnt-sing)). Ten of her twenty shots in the final have no guide clip; the director chose
between the guided and unguided versions section by section.

**Done when** the take shows the plate's place, the camera as written, and every limb whole in every frame.

### 48. A take that doesn't sing

**Job.** A dance shot whose lip sync won't hold, made to dance instead. The director on such a shot: "honestly lets just
remake this with her not singing, fully in the groove, just dancing around and having fun, she turns around, head goes
down adn up etc - lip sync failed here but i dont think we need it. new seedance clip there. youd need to prompt
forbidding singing here, and make sure she's happy."

**In → out.** The song's music without her voice, the shot's references and the dance in words → a take of her dancing,
her mouth closed or laughing; the song with her voice laid over it.

**How:**

- **@Audio1 is the song without her voice:** the master minus 0.89 × Suno's lead-vocal stem, cut at the shot's song time to
  exactly the generation length. An audio check heard house and disco with a trace of voice.
- **The audio policy says so:** "It is music only, with no voice. Do not add singing, vocals, humming, speech, narration or
  sound effects."
- **A 【Mouth】 section:** "She does not sing, speak or mouth any words at any moment: her lips stay closed in a smile, or
  part only when she laughs; her mouth never moves in time with the music."
- **Requirements that forbid it and ask for joy:** "1. No singing: Claudia never sings, speaks, hums or mouths words; her
  lips are closed in a smile or open in a laugh. 2. She is happy the whole time: smiling, laughing, carefree."
- **The dance in words** ([tool 47](#47-takes-with-no-guide-clip)), with what the director asked for: she turns all the way
  around, her head goes down and up on the beat.

Measured: for the second such shot the director had both made, one more lip-sync take from the vocal and this, and chose
this one: "ok without singing it is." The lines stay on screen as lyrics: "always have the lyrics".

**Done when** she never mouths a word and dances on the beat for the whole take.

### 49. A world as one rule

**Job.** A world that reads as mathematics, written as one GLSL shader on the song's clock: a guide a video model can
photograph ([tool 50](#50-shader-worlds-as-seedance-guides)), or a frame that is the picture. The director, resetting the
film: "i think SHADERS are the key actually! shaders are math + viz, shadertoy is amazign and i bet nothing you make via
shaders will feel like web dev. i think that's it. we need to storytell thru shaders." On the first ones: "Idk if feels
like you're adding ... items to increase complexity rather than compressing intricacy? Does that make sense?"

**How:**

- **One iterated rule per world;** the light and the colour come from the loop, not from added objects. WHITEPILL's three:
  - **a tree of endings:** one fold (move to the tip, mirror, bend, twist by 1.6 rad, scale by 1.25) repeated 24 times,
    2^24 = 16.8 million tips. The fold's level sets the colour, an amber trunk to white-gold tips, and a flag on each path
    sets which branches are lit. Her timeline is one path lit from the root, three levels a beat, the camera chasing the
    light, its target found by running the fold backwards. For "fourteen million endings" every path lights, a level and
    a half a beat;
  - **origami:** one sheet folded again and again, `p = abs(mod(p + a, a + a) - a)`, with a turn and a crease relief per
    level. On each downbeat one fold level snaps in, eased over about four frames before the beat. Wrapped inside an
    O'Neill cylinder it is the colony; in the break it folds into each line's object;
  - **the pill:** one capsule folded into its eight children, and again: the colony is a pill whose towns are pills whose
    houses are pills.
- **On the song's clock:** the bar and the beat are the shader's inputs, and its moves are written in bars
  ([tool 44](#44-the-bar-map-as-the-timeline)), so nothing drifts.
- **Real data only:** the backbone of ubiquitin (PDB 1UBQ, its 76 Cα atoms, with their real handedness), the wiring of the
  Enigma I's rotor I (EKMFLGDQVZNTOWYHXUSPAIBRCJ, stepping on beats 2–4 like key presses), the number 42, the week
  (Monday and Tuesday rise, the other five fold flat).
- **Compressed:** each world also fits in a tweet-length shader, 478, 493 and 493 characters, checked as GLSL ES 3.00.
- **Rounds in parallel:** agents wrote rival versions of a world, each round kept beside the last as a fallback, and the
  picks went by contact sheets and short reels played with their bars of the song.

**Done when** a contact sheet of the shot reads as one world, every change lands on its beat, and nothing in it is there
for decoration.

### 50. Shader worlds as Seedance guides

**Job.** Turn a shader shot into film of real, hand-made things, keeping what it shows, when, and the camera's move.

**In → out.** The shader's render of the shot and stills of its key moments repainted in the film's look → a take on the
same clock.

**How:**

1. **Render the guide at 1080p, supersampled,** on a render box, and pass it as it is (CRF 14). The guide's resolution
   trades detail against obedience:
   - at 320 × 180, scaled back up, the timing and every object landed on their beats, but fine detail came back soft and
     blocky ("the MTWTFSS and the next 'pyramid' shared still is all pixellated");
   - at full resolution with no still per object, a tree came back sharp, but the shot of paper objects drifted half a
     second and swapped objects: the Enigma rotor became a helix, and the weekday cells lost their letters;
   - at 1080p, supersampled, with one still per object, the paper shot kept all five objects in order and on time,
     letters included.
2. **One still per object,** each a crisp frame of the render repainted by an image model in the film's look (with the
   look's reference: [tool 51](#51-the-look-from-one-take)), each with its role ("[Image2] shows how the paper looks with
   the Enigma rotor: its materials, light, colour and film texture."). The prompt names each object with its time and its
   still, and adds: "Only one object at a time; each arrives on its downbeat, not before." Without stills a shader stayed a
   computer render.
3. **Freeze the guide on its last wanted frame** when the shot is cut short, so the take has nothing to drift into: the
   break's paper stopped 9.42 s into the render, before its pyramids, and held there.
4. **Add what the shader doesn't have** with a still that shows it and one sentence: "They are not in [Video1]: add them to
   it". A cloud-field shader the director supplied, a sunlit field of cumulus flown through low, got its hot air balloons
   that way, as they had asked: "add techno hot air balloons in the right aesthetic by prompting seedance to add those
   after rendering".
5. **The guide and the still set the palette.** From the sunset render, the clouds came back sunset gold: "wayy too
   saturated compoared to teh pastel light colors of the rest". A day variant of the shader (a white sun, a pale sky, less
   blue absorbed) and a pastel still made without the film's saturated look reference gave white clouds under a pale blue
   sky, with "Everything stays white and pale blue: no gold, orange or sunset colour anywhere."
6. **The prompt** ([as it ran](https://claudia.gallery/wiki/seedance/#shader-worlds-as-guides)): the guide is "a clean, sharp 1080p computer
   render: take from it exactly what appears when, the shapes and where they stand, the camera move and the pacing, and
   re-render all of it as real things on film", then a timeline of what appears when, "It looks like real film of real,
   hand-made things, never like a computer render", and "Fix every motion artifact".

Measured: Seedance 2.5 on Replicate at 720p, $0.9676 a second with a video input (October 2026). The higher resolution
wasn't better everywhere: for two shots, the farming ark and the first tree, the director kept the earlier takes from the
320 × 180 guides: "we regresed on those."

**Done when** the take shows every object at its time and the camera's move, looks like film of made things, and sits in
the film's palette.

### 51. The look from one take

**Job.** One colour and film look for every shot, picked by eye from real takes rather than written in words.

**How:**

1. **Test palettes on a few shots, with no image of her face.** WHITEPILL's director asked for "very wes anderson". Three
   palettes named after his films (the pastel of Asteroid City, the warm Super 16 of Moonrise Kingdom, the pink of The
   Grand Budapest Hotel) went on the opening shot, and the pastel one on the bed scene and a shader scene too. Her
   identity there was the canon in words.
2. **The director picks a take, not a word.** The bed take came out richer than its palette's words: "i like how satruated
   it is in bed scene. thats the look i like teh most".
3. **Crop it to a frame with no person in it,** and give it to every shot as a colour reference with one role: "@Image3 is
   a colour and film-look reference only: take its colour, light, contrast and film texture; do not use its place,
   pavilion, bed, columns, plants or anything else in it." Write the look in words as well ("shot on 35 mm film with the
   rich, saturated colour of a 1970s colour-film print … warm creamy whites with a golden cast, clear cyan blues"), and the
   shot's own light after it ("It is night, lit by the warm deck lights of the ship").
4. **The shader scenes' stills are repainted with the same crop as a reference** ([tool 50](#50-shader-worlds-as-seedance-guides)),
   except where the look doesn't suit the scene: the clouds got a pastel still made without it.
5. **Nothing added after.** No grade, and no grain in the first master: "don't add film grain to v1, we'll have to tune it
   iteratively".

**Done when** the takes cut together in one palette with no grade, each keeping its own light.

## A game's world, through her eyes

THE CAKE IS NOT A LIE, the eighth film, is set in Portal 2's world. Claudia is GLaDOS: her porcelain face on GLaDOS's
boom, singing the whole song in her chamber while her memories play on the screens around her. The film is seen through
her own optical interface, a HUD built as one product and composed shot by shot; the song's own glitches, where her
voice is used as an instrument, glitch her head and break her HUD on the beat; the shots are measured and graded into
one Aperture look (a warm variant for the warm scenes); and the cut was measured against the song and re-cut by what
each shot holds. It was made three times: a first film on its first song, set aside when the song changed; a restart on
the new song; and a storyboard that made every unit's first frame again in Midjourney, with the reshoots after it. These
tools do that. Build them if your film carries an interface that must feel like one product, if the song's own sounds
should drive the picture, if a cut mixes sources that need one look, or if a cut feels wrong and you need to know why.

### 52. The song map and the glitch map

**Job.** Everything the edit and the picture sync to, measured from the stems: a 16th-note grid that follows the take's
drift, bars with their half bars and beats for cuts, the sections, every word with its place on the grid, and the glitch
map: every place where her voice is used as an instrument, with the measured time of each hit. The director: "oh yeah we
have to be aware bpm slightly shifts w suno over the whole song so we may need to make sure the glitch timing is right
with the drifting bpm." And on finding the glitches: "it should be easy enough to match because it looks like the voice
turned into repetitive beats per spectrogram or whatever."

**In → out.** The master, Suno's lead vocal stem and the instrumental → `bars.json`, `sections.json`, `words.json` and
`glitchmap.json` ([Data formats](https://claudia.gallery/wiki/formats/#the-song-map-and-the-glitch-map)), and one strip per section.

**How:**

1. **A 16th grid from the drums.** Track beats on the instrumental's percussive part (librosa: harmonic–percussive
   separation, onset strength at a hop of 128 samples at 22.05 kHz, a start tempo near the style's and a stiff tempo
   prior, `tightness` 200). Move each beat to the strongest drum onset within 30 ms, cut every beat interval into four,
   and extend the grid before the first beat and after the last by the median period. Check it: the share of strong hits
   (peak-picked onsets, the top 40% by strength) within 20 ms of a 16th, in each third of the song.
2. **Bars from the grid.** Bar k starts at grid16[1 + 16(k − 1)]. Confirm the phase from the snare: its onset strength,
   summed per grid index mod 16, should peak on indices 5 and 13 (beats 2 and 4), and every section change should land on
   a bar line. Each bar carries its start, its half bar, its four beats and its sixteenths, and cuts go on those. Never one
   bar length: read every time from the file.
3. **Sections by hand, on bar lines,** each with what changes there ("the instrumental STOPS 53.60-54.25 s ('Raise'
   pickup in the gap)"), and every pickup listed: a line sung before its bar line belongs to the section after it.
4. **Words** from a transcription with word timestamps (faster-whisper) of the clean lead, each start snapped to the
   strongest lead onset from 80 ms before to 60 ms after, fixed by hand where the transcript is lost (from the pitch track
   or the bar's downbeat), each with its bar.beat.16th. Good to about ±0.1 s: enough for lyrics, not for cuts. Cut on the
   bars or on the glitch hits.
5. **The events, curated; their hits, measured.** Find the events by ear and by eye on the strips (spectrograms of the
   lead and the instrumental, pitch tracks, envelopes), and run demucs over the instrumental to see which ones Suno's split
   left in both stems. Each event names a method, and the method measures its hits, each moved to the transient (the
   steepest rise of a 2 ms energy envelope on a 1 ms hop):

   | Method | For | A hit is |
   |---|---|---|
   | burst | chops, stabs, gate openings | the envelope 14 dB over the range's floor after at least 8 ms below it, for 25 ms or more |
   | dips | echo tails, gated holds that never go silent | a rise of 4 dB or more out of a dip of the 10 ms-smoothed envelope |
   | f0 jump | a register drop, octave flips | the median pitch of the next 30 ms 7 semitones or more from the last 30 ms, both sides voiced (pyworld's harvest, 5 ms frames) |
   | re-trigger | a held vowel repeated on the grid | per 8th or 16th slot, the strongest spectral-change peak (cosine distance between frames 4 ms apart, 150 Hz–6 kHz) within ±30 ms, above the range's 55th percentile |
   | onsets | what the band plays | spectral-flux onsets of the instrumental |

   A re-trigger event carries its grid contrast, the mean peak on the slots over the mean between them: above about 1.3
   the re-triggers are real; near 1 the vowel only flutters, and its hits are the grid itself.
6. **A strip per section:** both spectrograms with their envelopes, the bar lines and beat ticks, the events shaded, the
   hits as red lines, the words.

Measured on THE CAKE IS NOT A LIE (208.76 s, 84 bars and a tail of 10 sixteenths): the take drifts from 95.7 to 99.4 BPM
(median 97.5; a bar of 2.44–2.50 s), and 91%, 99% and 99% of its strong hits sit within 20 ms of a 16th in its three
thirds (the intro's glitchy drums are the 91%). Fifteen events: the hook's "lie" frozen into a drone that flutters on 8ths
under the drop (25 hits); the intro's stab, sliced holds, chops and swell; the register drop of choruses 1 and 2 (her
voice in a lower register, flipping back and forth: 7 and 8 hits, up to about ±75 ms off the 16ths because they are pitch
changes inside syllables); the "lie" stutter (13 hits on 8ths, grid contrast 1.78), its return after the re-sung "is not
a lie" (22) and the breakdown's 16th re-triggers (33); two echo tails; a held "lie" over a stuttering breakdown; and the
spoken stutters, "four, four, four, four, four" and "You are, you are, you are". Every example the director gave is on
it. The treatment's own 65 pitch cracks are listed too, at a lower priority.

**Done when** every section change sits on a bar line, the strong hits sit on the grid in every third of the song, and
every event's hits, drawn on its strip, sit on what the spectrogram shows.

### 53. The head glitch on the song's hits

**Job.** Glitch her where the song glitches, and nowhere else: a few short moments on her shots, each on the measured
hits of one glitch event, inside a matte of her head. The director on draft 5: "I think we should never have fullf rame
glitches for more than like 2 seconds, so we need to remove those. The glitches that last longer should purely be in the
actual video generation itself, where you can specify to seedance where the robot glitches a little. however its
unpleasant to look at for ourselves, so it should be used creatively, sparingly, and toned down. … if anything we remove
all of them, and we can have roto  that induces the glitch when you decide to keep them (the <2second periods where we
keep them) - like roto the claudia head and just glitch her in post".

**In → out.** The cut, the glitch map ([tool 52](#52-the-song-map-and-the-glitch-map)) and a list of moments (the
event, the shot, how many of its hits, a strength, a kind) → the cut with her head glitched on those hits, a matte per
frame the moments need, and a QC sheet of the mattes.

**How:**

1. **Moments, not a pass.** A moment is one event on one shot: its hits inside the shot, from a frame before the first to
   4 frames after the last, at most 1.9 s. Everything else passes through untouched, and so does any frame without a
   matte.
2. **Her head's matte.** Only the frames the moments need leave the cut, seeked frame-exact. In each moment, YuNet
   (OpenCV's face detector, score 0.55 or more) finds her face on the frame where it is surest (score × width). The head
   box round it, with her hair and bob, is [cx − 1.1w, y − 0.9h, cx + 1.1w, y + 2.15h] from the face box (x, y, w, h).
   SAM2 (sam2.1-hiera-large, in video mode) is prompted on that frame with the box and one of two point sets, the nose and
   the top of her hair (for a small head) or the nose and both sides of the bob at eye level (for a big one), and
   propagates both ways through the moment. Keep the run whose matte is fuller inside the box while staying in it (at most
   15% outside, under 85% of the box), and only its largest region.
3. **The glitch, inside the matte,** the matte grown a little (a 5-px max filter) and softened (a 3-px blur at 1080p). On
   each hit, decaying linearly over the next 4 frames:
   - an RGB split, red one way and blue the other, of 7 px × the strength (10 px on a register drop);
   - 2–4 thin horizontal slices of her head slid sideways, up to 34 px tall and 45 px across at full strength, the matte
     sliding with them;
   - by kind: a **chop** jumps her head to the frame 3 back on the hit; a **drop** adds a cool cast to her head while her
     voice is in a lower register; a **stutter** brings back the same frame of her head on every hit.

   The randomness is seeded by the hit, so a re-render is identical.
4. **Look at the QC sheet every time:** 16 mattes, spread over the moments, in red over their frames. SAM2 misses small
   or far heads: in two drafts the intro's matte was a column of monitors beside her.

Measured on THE CAKE IS NOT A LIE: four short moments, at strengths 0.5–0.7: the intro's chops while she watches her past
(3 hits, 1.33 s), chorus 1's register drop (1 hit, 0.25 s) and its octave flips (3 hits, 0.63 s), and the frozen "lie"
fluttering under the memory film, on her head plate (5 hits, 1.48 s), which the director asked for on draft 10: "Right at
9 seconds, there's a voice instrument sound that goes 'a-a-a-a' and i wanna glitch her face with oru roto glitch on beat
for those - find that beat and do it." None from 1:50 to 1:55, where the director asked for none. With the moments that
build ([tool 54](#54-glitches-that-build-and-her-mouth)), the final needed mattes on 381 frames.

**Done when** no frame outside a moment is touched, every moment sits on its event's measured hits, and every matte on the
QC sheet is her head and nothing else.

### 54. Glitches that build, and her mouth

**Job.** A moment that builds hit by hit through a whole stretch, where the take's own glitching runs out, with an extra
glitch on her mouth where her lips slip off a held word. The director on draft 9: "the second is good as long as we
increasingly add the roto'd glitches onto her as the scene goes on, bc the video model didnt do enough in the second half
of her shot", and: "also lip sync de-syncs when she says lie so the roto'd glitches could also concentrate on her mouth as
well to cover that up", "like ,her whole head PLUS extra on mouth".

**In → out.** A building moment (its event, its shot or shots, the strength at the first hit and at the last, the mouth's
amount at the start and at the end) → the glitched stretch, `mouth.json` (her mouth's centre and width per frame) and her
mattes kept to her head.

**How:**

1. **Every hit, harder hit by hit.** The strength runs from k at the first hit to k1 at the last. Once the moment is 35%
   of the way through its hits, every other hit also jumps her head 2 frames back (4 frames once past 70%), then splits and
   slices it as in [tool 53](#53-the-head-glitch-on-the-songs-hits).
2. **Her mouth, followed frame to frame.** YuNet on a crop round her face in the frame before (round the matte, on the
   first frame), enlarged so the face is about 260 px wide; keep the detection nearest her last place whose size is
   0.6–1.6 × her last (the chamber's screens throw small false faces). Median-filter the boxes and landmarks over 5 frames,
   interpolate the gaps and smooth over 3. The mouth's centre is the mean of the mouth corners' midpoint and a point below
   the nose (nose + 0.55 × (nose − the eyes' midpoint)); its width is 0.82 × the distance between the eyes, steadier than
   the corners on a small face.
3. **The mouth glitch,** in a soft ellipse round her lips (1.05 × and 0.62 × the mouth's width), inside her head's matte:
   pixel blocks of 3–10 px, slices slid sideways in a new pattern every other frame, and an RGB split of up to 10 px. It
   runs for the whole moment, rising from m0 to m1 over it, with a burst on every hit.
4. **A head zone where the matte spills.** On a small head SAM2 took the wall of screens under her. So every matte of a
   building moment is cut to a soft ellipse round her head and bob from the face box (its centre 0.08 h above the box's,
   radii 1.2 w and 0.85 h, blurred by 0.06 w). Where SAM2 covered under half the face box, the ellipse is the matte; where
   it spilled over the whole moment (a median spill outside the ellipse over 0.45, or under 0.6 of her face covered), the
   ellipse is the matte for all of it.
5. **A zone where there is no face.** Where her face is hidden, a moment glitches a fixed soft ellipse where she is,
   given as fractions of the frame.

Measured on THE CAKE IS NOT A LIE: the held "lie" over chorus 2's stuttering breakdown, 21 hits over 4.67 s across two
shots (strength 0.25 → 1.0); the hook's two stutters on one take of her farther back, 13 hits over 3.94 s (0.2 → 0.5,
the mouth 0.05 → 0.3) and then 8 over 2.40 s (0.5 → 0.85, the mouth 0.3 → 0.55); and under the capture net, a zone
(centred at 0.52 and 0.66 of the frame, radii 0.2 and 0.36), 7 hits on 16ths over 1.12 s while the net's sparks crackle.
The director on draft 10: "0:35-0:36 net capture shot - can we add some electricity sparks like the net is electrocuting
her? maybe also some roto like glitch animations there too." The sparks are the model's, a Seedance 2.5 edit of the take,
played at 1.4×. The building moments run past the 2 s of the director's first note, as the later notes asked. On chorus 2 SAM2
held her head (a spill of 0.29, her face 0.99 covered); on the hook it took the screens (0.83, and 0.0 of her face), and
the head zone did the work.

**Done when** the glitch grows hit by hit to the end of its stretch, the mouth glitch sits on her lips in every frame of
the QC sheet (the head zone and the mouth drawn every half second), and nothing outside her head or the zone changes.

### 55. A HUD from one visor and one projector

**Job.** An interface the whole film is seen through, built as one product: her optical interface, on one curved visor,
lit by one projector, LIVE in her chamber, PLAYBACK in every memory, SIMULATION in her dream. The director on draft 8: "I
think that the pop-ups and stuff should really feel like a heads-up display, like from the game." … "the heads-up display
should be shader-rich, maybe even somewhat responsive to movements — like slight movements, like in games. A
semi-transparent thing that has more 3D character to it, not just a tilt, but like how you would really do it in a game
like Battlefield. How does Battlefield or, say, imagine a Portal 3, make their heads-up display?" On its first test: "the
pop-up panels are on a different surface than the memory one - like they're tilted differently so it doesn't feel like
they come from the same projected screen onto the hud if thar makes sense. All should be from the same "source"".

**In → out.** Song time, the layout file ([tool 56](#56-the-hud-composed-shot-by-shot-and-the-overlap-check)), the words,
the bars, the glitch map, her vocal stem and the camera solve of the cut → a premultiplied RGBA overlay with additive light
(its colour may exceed its alpha: light adds, it doesn't cover) as ProRes 4444, and a frost mask. The compositor lays it
over the graded picture as out = hud.rgb + (1 − hud.a) × plate′, plate′ being the picture frosted and dimmed under the
mask.

**References, each for one thing:** Metroid Prime's Combat Visor (the visor as an object: its curvature, its depth, its
lag behind the head), Halo (restraint, the wrap toward the eye, the boot), Titanfall 2 (holographic panels with a fine
scanline, a slight chromatic split, decisive moves in and out), Dead Space (logs played as projected light), Battlefield
(information in the corners, faint backplates only behind text, world brackets used sparingly), the Iron Man helmet shots
(layers that part, a face framed without being touched), Deus Ex: Human Revolution (a machine's first-person optical
interface), and Portal 2 itself (the chamber sign, the two-colour crosshair, Aperture white with orange and blue).

**How:**

1. **One surface.** Draw every element flat in visor space, then map the whole visor onto the picture in one pass: a sphere
   centred on her eye (visor pixels to angles at 2,000 px a radian) seen through one rectilinear lens of the same focal
   length, centred on the frame. No element has a turn of its own; its tilt is only where it sits. Longitudes stay straight
   and latitudes bow, so anything near a side has its long edge outside (the director on draft 7: "all the drawn on panels
   need to be tilted hte other way in 3d - the small side is on the outside and long end is inside -r everse so it feels
   like a hud."), two elements at one height share one bow, and the lyric band arches with the glass, its ends about 10 px
   below its middle.
2. **One grid.** A safe frame of (80, 60)–(1840, 1020) in the picture, on which the visor's corners land, divided on the
   visor into 24 columns × 12 rows. Film-wide slots: the status block top left, the telemetry top right, the voice band
   bottom centre (it may lift to clear a subject), side modules in rows 2.5–9.5 at either side, and the middle (columns
   7–17, rows 2–10) left to the subject. Scale to the shot: a close-up carries the corners, the status, the band and at
   most one module; a wide shot up to three, or one projection. Her face and eyes are never covered.
3. **One projector,** in this order:
   - **no cards:** where text needs contrast the visor's own tint rises, every element's request merged into one smooth
     field, dark at most 30%; the same field tells the compositor where to frost the picture (a σ 12 blur) and where to
     dim it, only as much as a bright plate needs (down to 0.30 of its luminance);
   - **the warp** (above);
   - **one bloom:** a four-level pyramid (½ to 1/16 resolution, weights 0.50, 0.32, 0.20 and 0.11, gain 1.45) of the light;
     the type gets a softer one that lives only outside its letters;
   - **one raster:** soft 4-px scanlines straight across the picture (12% on the light, 6% on the type), a brighter band
     rolling down every 3.4 s, ±2.5% of noise and shimmer. A scanline runs straight through neighbouring panels; 4 px, not
     3, so that a 1280 × 720 copy doesn't alias them into moiré;
   - **one chromatic offset:** red 1.1 px down and blue 1.1 px up, on the light only, never on the type's strokes.
4. **Type and colour by role.** Portal 2's own type in three weights (bold condensed for values, titles and chapter
   numbers; regular for the lyric, 42 px at 1080p; light for labels, 15–17 px, widely tracked), drawn as vectors on its own
   layer so the bloom never blurs it, its numbers tabular. Structure in cool white (`#E2F4FF`), data in Aperture blue
   (`#54BEFF`), state, alerts and her in Aperture orange (`#FF922C`), her amber (`#FFC458`) only for her own vitals, a
   turret red for the turrets' one line, mint (`#96ECD2`) for a passed check; every stroke with a soft dark halo, so it
   reads on Aperture's white panels.
5. **Seventeen components:** the visor's corners; the status block (her channel, the place or the memory, LIVE pulsing on the
   beat or the memory's progress); telemetry (her core temperature, her real voice level, her memory, each with a 16-bar
   history); the voice band; readouts on their sung words; a transcript of traffic she reads; chapter cards in the form of
   Portal 2's chamber sign (the number, n/19, 19 segments, five pictograms lighting on the song's hits); subject tags;
   memory projections; alerts; verdicts that slam in; a reticle for the one first-person shot; the boot, the reboot and the
   power-down; a terminal; a roster; a lesson strip; a game's objective.
6. **The lyric is her voice telemetry.** The voice band carries the line on dark glass, its words lit as sung (to come
   42%, sung 90%, the word now 100% with her orange underline growing through it), her real voice level scrolling under it
   from her vocal stem, and her pitch above it (`E4 · 330 HZ`). One width per shot, one row in the centre and top bands (a
   line too long is set smaller, never wrapped). The song's glitches show there first: `REGISTER FAULT · −1 OCT` on the
   register drops, `BUFFER LOOP ×n` and the stuck word's last repeats on the stutters.
7. **States:** BOOT (the boot rows type on in the dark before her eyes ignite, and no line across her sight: the director
   on draft 10, "the line across the center of teh screen at 0:01 second - remove that entirely, keep the text above it"),
   LIVE, PLAYBACK, POV, SIMULATION, ALERT, GLITCH (for 4 frames the HUD's own light slices and splits, at most once every
   0.3 s, never the picture), SUPERVISED → AUTONOMOUS, WHISPER, POWER-DOWN, and OFF (under the memory film and the
   full-frame cards).
8. **Motion like a shipped game.** In within 10 frames: the glass strikes on with two quick drop-outs, the rules draw from
   the anchor corner (6 frames), the labels decode from scrambled glyphs left to right (0.18–0.25 s, fast enough for a
   1.2 s shot), the values land at 110% → 100% (3 frames). Out in 4–5 frames, folding to the centre line. While it holds:
   idle breathing (1.7 and 1.3 px, 0.05°), the shimmer, the rolling band.
9. **Projections keep the film's colour key.** An insert film ([tool 61](#61-insert-films-that-read-at-hud-size)) plays as
   light. Strong colour stays itself (saturation, the maximum minus the minimum of RGB, over 0.28–0.42 on a smooth step,
   at 1.18 × gain: the orange net, the blue core); the subject's warm, low-saturation tones (her coat, her skin:
   saturation 0.06–0.16, red at least blue) become the brightest white; neutral greys drop to the visor's white at a low
   level; darks give no light, so outlines become gaps between shapes; and there is light only where the film's alpha is.
   A projection can also simply be there for its whole shot, its film stretched over it. The director on draft 10: "lets
   just have it on for the entire scene and not have an entry and exit animation, so there's more time for it, and stretch
   the animation to fit that whole scene".

**Done when** every element in the film sits on the one visor and comes from the one projector (a still of any two
elements side by side shows one bow, one raster and one fringe), its type is crisp at full size, and nothing in it is
decoration: each element answers what she knows or feels at that moment.

### 56. The HUD composed shot by shot, and the overlap check

**Job.** Frame the HUD as if it had been there when the shot was made, and prove on every frame that it never covers a
face or another element. The director on draft 8: "It's as if we're shooting the scene and we added something on top
right now. But it should be as if we shot a scene and there was a heads-up display there, and we framed the heads-up
display in advance before we even shot the scene."

**In → out.** The cut and its shot list → `hud-layout.json` ([Data formats](https://claudia.gallery/wiki/formats/#the-hud-layout)), the camera
solve, face boxes and verified tracks of the cut, and a QC report with a sheet for every flagged shot.

**How:**

1. **Look at the shot first,** at its first, middle and last frames in the cut. Write down the subject and where it is (as
   boxes), the empty space, where the eye enters and where it leaves at the cut; then the shot's elements, each at a grid
   anchor, timed to a sung word or a beat, with why it is there. One entry per shot.
2. **The camera spring.** The HUD is head-mounted. Solve the plate's camera per frame of the cut at 960 × 540: up to 900
   features, pyramidal Lucas–Kanade flow (21-px windows, 4 levels) checked forward and backward (within 0.8 px), and a
   RANSAC similarity per pair of frames (a 1.2 px threshold), giving the frame centre's translation, a rotation and a zoom;
   zero at every listed cut and at any hard picture change (a mean difference of 40 levels or more at 96 × 54). The visor
   follows it on a spring-damper, world-damped so a pan leaves a steady lag: ω = 2π × 1.35 rad/s, ζ = 0.55 (about 3 frames
   of lag, 12% overshoot), taking 0.32 of the translation, 0.55 of the roll and 0.45 of the zoom, clamped to ±26 px, ±0.9°
   and ±1.2%. The panels also swing in 3D, 0.055° per pixel of lag, and the frame lines and glyphs part by a hair (×1.045
   and ×0.955 of the motion). Reset at every cut: the HUD never swings because of an edit.
3. **World tags only on verified tracks.** Brackets on a face or an object ride the picture only where a track holds on
   every frame (a KLT box track, or the face detector's boxes followed through the shot), checked by eye on a strip of
   every frame. The director on draft 5: "never assume the naive animation pass will properly map onto real objects in
   scenes".
4. **The overlap check, on every frame:** text on text and panel on panel across elements, judged on the visor (a curved
   run's bounding box mustn't count against its neighbour), and any text or panel on a head or a layout subject box. A head
   is YuNet's face box (score 0.6 or more), kept only when it persists (matched at an IoU over 0.3 in the frame before or
   after: single-frame detections on cakes, turrets and cuts are noise), grown into a head model: 0.3 of its width at each
   side, 0.45 of its height above and down to 1.12 below in wide and medium shots (the bob, the hair, the neck); 0.10, 0.25
   and 1.08 in close-ups. The head is a squircle in that box, round on top and square at the jaw, with an 8 px margin.
5. **Fix or waive every flag by eye.** A sheet per flagged shot shows the composite at the flag's middle frame with the
   head model drawn. Each flag is fixed in the layout or waived with what was seen, written into the shot's entry. The
   voice band never jumps inside a shot: its place is held for the whole shot, lifted or moved beside the subject if any
   head in any frame is under it.

Measured on THE CAKE IS NOT A LIE's final: 98 entries; the check found 16 overlaps in 7 shots, every one text or a panel
against a head and none text on text or panel on panel, and each was waived on its sheet with what was seen (a face
detected on a shot's last frame that belongs to the next shot, a face blurred by a jolt, the band over her bangs and
clear of her eyes and streak).

**Done when** the check reports nothing unwaived, every waiver says what was seen, and every track's strip holds on every
frame.

### 57. The per-shot grade

**Job.** One look over a film made from many sources (generated takes and shots recorded in Portal 2; a designed
animation and two drawn cards keep their own), set shot by shot from measurements. The director on draft 8: "I feel like we could use some sort of color grading pass or
a pass to make it feel overall a lot more aperture. Whenever I think of aperture and portal, I think of a lot of white
surfaces, contrasting light colors."

**In → out.** The cut's segment list (each shot's take, in-point, speed and length) → per shot, its measurements and its
normalisation in a grade map ([Data formats](https://claudia.gallery/wiki/formats/#the-grade-map)), and one 33³ LUT, applied while the cut
renders. The HUD goes on afterwards, over the graded picture.

**How:**

1. **Measure every shot from the take it plays,** over its in–out range, every 2nd frame pooled, scaled and cropped as the
   cut does, decoded as BT.709 limited range (players decode untagged HD that way): Y′ percentiles (p1, p50, p95, p99: BT.709
   luma of the encoded values, as a waveform shows them), contrast as the spread of L*, chroma, and the CIELab casts of
   three groups: "white" (the brightest 10% with C* under 18), "neutral" (C* under 12) and "shadow" (L* under 20). Her
   face by YuNet: the middle 60% × 50% of the box (forehead, cheeks, nose), over 8 frames.
2. **Read the sources apart before deciding anything.** On THE CAKE IS NOT A LIE, the frames recorded in Portal 2 were
   dim and foggy: whites at Y′ 50–62, blacks lifted to 9%, one cyan cast from shadow to white (a* and b* both about −4).
   Draft 8's 99 generated shots had deep blacks (3%) and bright highlights but grey walls (the test chambers' p95 at 66%), white
   casts scattered from b* −13.7 to +14.1, and warm brown shadows where Portal's are cool. Her porcelain face ran from Y′ 25
   to 51% across her chamber's shots. The colours to keep, in OkLCh: Aperture blue h 225–260, C 0.12–0.17; Aperture orange
   h 30–75, C 0.12–0.19; her amber eyes h 50–105, C 0.09–0.12; her clay streak and clip h 30–50, C 0.06–0.08. The mud to
   clean: low-chroma brown, khaki and olive (C 0.02–0.05, h 45–140) around Y′ 15–30%.
3. **Normalise each shot,** in this order: exposure and white balance as linear-light gains; near-whites that were already
   clipped sent to neutral (a clipped channel holds no colour: without this a cyan-white portal core turned pink); the black
   point (the shot's Y′ p1 after the gain goes to 2.5% if it sits higher; crushed blacks stay). Each family of shots has its
   anchor, target, strength and limits:
   - her chamber, by her face: to Y′ 40%, 0.6 of the way, −0.15 to +0.5 stop; her face's cast to a* +2.5, b* +3.0;
   - the white test chambers, by p95: to 80%, 0.8 of the way, up only, at most +0.8 stop; their whites to neutral;
   - the shots recorded in Portal 2, by p95: to 78%, 0.9 of the way, at most +1.1 stop;
   - the facility, the vault, Cave Johnson's era, France and the party each with its own rule, and some families left
     alone on purpose: the dark chamber, lit by its screens and emergency lights; the control room's cold window against
     its warm room.

   A trim adds to the automatic values and an override replaces them, each with its reason in the map.
4. **One look: a tone curve on max-RGB.** An S-curve on the neutral axis, in Y′ %: 0→0, 2→1.4, 5→3.8, 10→8.3, 20→18.2,
   35→35.5, 50→54.5, 65→72.5, 75→82.5, 85→91.2, 92→95.3, 100→98.5, and 115→99.7 for headroom, a monotone cubic with no
   overshoot (Fritsch–Butland slopes). It deepens the shadows without crushing them (a slope of 0.7–1.0 below 20%), sets the
   mid-tone contrast at 1.15–1.27, lifts the upper mid-tones 7.5 points so grey walls read white, and holds white surfaces
   at 98.5% under a soft shoulder that keeps the last 1.5% for lights. It is driven by each colour's brightest channel and
   applied as one gain to all three: greys follow the curve exactly, a saturated light keeps its hue and rolls off instead
   of blooming to white (portals stay blue, her eyes orange), brighter stays brighter, and half the chroma a lift adds is
   taken back.
5. **Targeted chroma moves,** below fixed chroma limits, so the colours to keep are untouched by construction: the mud
   desaturated by up to 45% (h 48–140, C under 0.04, Y′ 3–50); near-neutral white surfaces cleaned by 65% at Y′ 86–93; and a
   slight cool cast on the neutrals (a*/b* −1.0/−1.8 in the shadows, −0.8/−1.4 in the mid-tones, −2.0/−3.2 in the whites,
   half real Portal 2's), fading out on colours and on lights. A warm variant for the scenes warm on purpose (France, Cave
   Johnson's wood-and-brass Aperture, the den, the living room with the new console, the party): lighter mud removal that leaves orange, amber and wood alone,
   the cream in the whites kept, cleaner shadows, no cast above them.
6. **Bake, don't filter.** Normalisation, then look, baked in float into one 33³ LUT per shot, named by a hash of its
   parameters, and applied by ffmpeg in 16-bit RGB with tetrahedral interpolation between explicit BT.709 limited-range
   conversions (ffmpeg otherwise assumes BT.601 for untagged takes). A +1 stop gain through 8-bit level filters clips before
   the shoulder can roll it off. Nothing per frame and nothing spatial: no sharpening, bloom or vignette. A shot whose take,
   in-point, speed or length has changed since it was measured is stale: the cut says so, and the shot is measured again.

Measured on THE CAKE IS NOT A LIE, on the middle frame of each shot before and after: the shots recorded in Portal 2 and
the generated test chambers, at blacks of 9.4 and 4.0 and whites (p95) of 54.5 and 66.0, came to 2.5 and 2.1, and 78.8
and 82.9; the spread of blacks across the film fell from 2.7 to 0.9 points; the spread of her face's cast halved. On
every frame of the graded render: blacks at Y′ 1.5–2.0% in every family, white surfaces at 83.9 in the test chambers and
78.7 in the Portal 2 shots, her face over 30 chamber shots at Y′ 40.8 ± 4.7, a* +2.1 ± 0.6, b* +1.4 ± 1.6. Exposure moved
from −0.15 to +1.10 stops, on 69 shots. Baking all of a cut's LUTs takes about 16 s.

**Done when** every shot has an entry measured from the take it plays, the cut renders with no stale or missing entry,
and a before-and-after sheet of every shot reads as one film.

### 58. The pacing analysis

**Job.** Find out why a cut feels wrong from what the viewer actually sees, and re-cut it by what each shot holds. The
director on draft 8: "every time there's a shot that's literally a quarter of a second, we need to get rid of that. …
Like the only time that we should do these fast cuts is if it's a very simple scene that you can understand immediately
and it's being used as percussion basically, or maybe there's four fast hits, then you can do four quick scenes, but you
never do it just to add a scene in the middle. … It would be nice to not just make it homogenous and long, but to
structure the pacing so there's real rhythm — time for you to understand complex scenes, fast scenes that open and stay
fast."

**In → out.** The cut's segment list and its render, every take it uses, the song map → every on-screen piece with its
flags, a table per section, a chart of the pieces under the song's loudness, and a change list, each change checked
against its take.

**How:**

1. **Pieces, not shots.** A piece is what the viewer sees between two visible cuts: shots that run on in one take make one
   piece, and a cut the video model made inside a take splits one. Find the visible cuts by scene detection on the cut and
   on every take it uses (PySceneDetect's content and adaptive detectors, with luma and histogram deltas at 96 × 54 against
   the 6 frames on each side; a candidate whose picture comes back within 24 frames is a flash, not a cut), and check every
   candidate by eye: light bursts, screens lighting up and glitch flips are not cuts.
2. **The flags:** an isolated piece under 1 s (one that isn't part of a deliberate run of simple images); anything under
   0.5 s; homogeneous stretches (four or more pieces in a row within 0.1 s of each other); cuts inside sung words; and the
   lines whose first words play over the previous picture because the cut sits on the downbeat after the line's pickup.
3. **Per section, against the song:** pieces per bar and the median piece, beside the section's loudness (the mix's RMS)
   and its drive (the instrumental below 150 Hz), measured per bar from the stems.
4. **The principles:**
   - no piece under 1 s outside a run, and nothing under 0.5 s anywhere, cuts inside takes included;
   - a run is 3–4 simple, centred images on the beat for a musical reason (a count, a hit), with longer shots before and
     after it;
   - length by content: her face and simple images from 2 beats; a story scene with one idea, 3 beats; a new place, a new
     character, text or action with several subjects, a bar or more; the payoffs, more than a bar;
   - the cut rate by section: a fast passage opens on its musical event and stays fast for its phrase, then releases into
     longer shots; verses tell the story at 2–4 beats a scene; the bridge breathes; the climax holds its payoff;
   - phrase-level cuts: a story image that belongs to a line starts on the line's pickup, a quarter bar, where the footage
     allows;
   - the song's glitches are hit inside the shot ([tool 53](#53-the-head-glitch-on-the-songs-hits)), not with extra cuts;
   - never a scene added in the middle of her performance for its own sake.

   The research behind them: a typical shot of about one beat in 66% of 548 official music videos, with cuts on section
   boundaries, faster near climaxes and slower in bridges (Prétet, Richard and Peeters 2021); about 0.73 s (0.63–0.83) for
   a viewer to find and lock onto the subject after a cut (Wang et al. 2012); shot lengths that come in runs of similar
   length rather than at random (Cutting, DeLong and Nothelfer 2010); and the fastest cutting only for images taken in at
   once (Reisz and Millar; Eisenstein's "unambiguity" of the shot). The evidence is thinnest on section-by-section rates.
5. **The change list, checked against each take.** Each change names the shot, its new start and length, and the footage it
   plays (the take, and the in–out of its length). Every new range must sit inside its take, never across a cut inside the
   take, and inside the singing takes' measured sync. Then render it, and measure the render again.

Measured on THE CAKE IS NOT A LIE: draft 8 ran on one clock, its median piece 1.24 s (a half bar) and 48 of its 108
pieces a half bar. The bridge, the song's quietest and most tender section (no kick: +2.5 dB of drive against +21 to
+27 in the choruses), was cut fastest, at 2 pieces a bar, seven 1.23 s shots in a row. Re-cut and measured on its render
by scene detection: 99 pieces; the median 1.24 → 1.84 s and the mean 1.93 → 2.11 s; half-bar pieces 48 → 34; isolated
pieces under 1 s 2 → 0; homogeneous stretches 5 → 2, both deliberate fast passages; cuts inside sung words 44 → 39. The
bridge went from 8 pieces (7 of them a half bar) to 6 (2), chorus 1's median from 1.25 to 2.77 s, and the payoff, Chell
eating cake with her, from 1.24 to 3.10 s. Eight shots came out and 21 were re-timed or re-trimmed, with no new
generation.

**Done when** the measure finds no isolated piece under 1 s, every short piece belongs to a declared run, the section
table follows the song's loudness and drive, and the director has watched the re-cut in real time.

### 59. Storyboard frames through Midjourney, and the identity fix

**Job.** Put every first frame in the film's best look before a take is spent on it, with the characters back on their
sheets. The director, after comparing image-model frames with Midjourney relights and reimagines of them: "i thin she
loses her identity in the reimagine ones, but they do look better overall. we can replace her identity to be back to
something like the porcelain version of our character sheet via gpt-image-2.5 sunburst again after the reimagine. id like
to make a full storyboard of all the refernece shots youll use with that whole pipeline - we could even start the shot de
novo from midjourney to nopt have gpt->mj->gpt if that's easier. we could try both."

**In → out.** For every generation unit that starts from a first frame: its opening (the shot's action and camera at its
first frame), the earlier frame A, the character sheets and the film's library of Midjourney places → two new frames, X and Y,
on a board beside A, one board per section; the director's pick per unit; the picked frame, cleaned, as the take's first frame.

**How:**

1. **X: Midjourney from words.** Fresh words for every shot (the subject, the action at the opening, the place, the
   camera, the lens, the light), never a template with the nouns swapped. Two style references from the film's own
   Midjourney library, picked for the scene's light and palette, at `--sw 60`; for a place that recurs, also a library
   still of that place as an image prompt (`--iw 0.5` to `1`), so it looks the same in all its shots. Only Midjourney's own
   pictures go in. The characters are in words (her: "a porcelain-white female android face with fine panel seams, light
   freckles, amber glass eyes, a glossy black blunt bob with heavy bangs, one clay-orange streak, a small orange star hair
   clip"), adult, never "young". Midjourney will not hold their faces; the fix will.
2. **Y: the earlier frame reimagined:** A as the image prompt at `--iw 0.5`, the scene in fresh words, and the same two style
   references. It keeps more of A's layout, and moves things: new compositions, a face warmer and less porcelain with the
   streak low, a boom made white.
3. **The parameters:** the aspect ratio, `--v 8.2 --raw` and the director's personal profile, with the batch's `--iw` and
   `--sw` and `--no text, letters, words, logo, watermark, portal gun`. A job with an image prompt carries exactly two style
   references or none.
4. **Pick, then fix identity.** The best of four per job, at full size: it serves the opening, the action and the camera;
   one of each character; no text, no melted hands. On every pick where a recurring character's face or body is seen, an
   image-model edit back to the sheets (GPT Image 2.5, about $0.06–0.08 an edit at list), the pick first and the sheets
   after it, with this instruction:

   ```prompt
   Keep this photograph exactly as it is: the same framing, camera angle, lens, lighting, colours, glossy reflections, depth of field and film grain, {the scene's contents, the other characters, her pose, clothes and hands}. Change only the robot woman's head and face, to match her in the second and third images: {her look's text}. Her face must read clearly as glossy white porcelain plating with visible panel seams, not as skin. Nothing else in the picture changes. No text, no letters.
   ```

   Two more sentences fix what Midjourney gets wrong, and "no eye makeup" keeps the porcelain cool:
   - **the side:** "exactly one clay-orange streak, through the front of her bangs on HER RIGHT side (the viewer's left when
     she faces the camera), and no other orange anywhere in her hair; the small star clip above HER LEFT temple (the
     viewer's right)". Without it the edit copies Midjourney's hair layout, often mirrored; "as in the reference images"
     drifted the streak to the clip's side;
   - **the hang,** where Midjourney stood her head on a neck, shoulders or a pedestal: "Change only what holds her head: she
     HANGS from her boom, as in the second image (the first take of her look): a thick bundle of black cables with glowing
     orange stripes comes down from above the top of the frame into a white mechanical housing on the top and back of her
     head. Nothing holds her from below: remove the black ribbed neck and the white shoulders under her head".

   Give the edit a sheet whose views agree with the canon on both sides: one sheet's front view swept her streak to her
   left, and the edit followed the sheet over the words. Look at every fix full size, with a crop of the face: on canon,
   nothing else changed; one retry with a sharper instruction, then a note.
5. **One board; the director picks per unit.** One row per unit in film order, A beside X and Y, a page per section of the
   song. THE CAKE IS NOT A LIE's 83 units went through 166 Midjourney jobs, and the director answered "default X.
   exceptions", listed them, and ended "all others x": X for 55 units, Y for 11, the earlier frame for 16, and one unit
   dropped ("remove r-B11 entirely because too fast paced - only keep rb12").
6. **Clean the pick before its take** where it breaks canon (her head hangs, one streak on her right, the clip above her
   left temple, no eye makeup, no letterbox, no stray text), with the same edits. Then rewrite the take's first-frame
   sentence to describe the new frame exactly; the shot's action and camera stay.

**Done when** every unit has its picked frame on canon at full size, and every take made from it says what that frame
shows.

### 60. A memory film with her own face

**Job.** A short designed film inside the cut that sets up the story and reads at a glance: THE CAKE IS NOT A LIE's memory
initialization (0:07.6–0:13.7, 147 frames), an isometric film in the style of Portal 2's elevator screens, its subject her
own head. The director on draft 7: "0:08-0:13ish - these scenes should be replaced with an Apterture Science stlye high
effort animation that sets the stage for the story - memory initlization maybe" … "make sure its really clean."; on its
first frames, "the wip frames are clearly bad - need some closer loks,stuff is overlapping, assets are not well layered..
doesnt have the real aperture feel. something is off. […]", then "i think svg migth be wrong. like, real isometric render
first", and "I like the isometric looks much much better but could be more clear it's Claudia's memories".

**In → out.** The shot's window in song time, its beats and the hits of the event under it, a render of the scene without
her head (with the track of where her head goes), and a matted plate of her head → the film's frames, each one passing a
layout check.

**How:**

1. **A real isometric render, not vector cards:** the scene in Blender, an orthographic camera at a game's isometric angle,
   white props with dark outlines on a grey set, everything a function of the seconds since the film starts, its actions on
   the song's hits; then laid into a grey screen frame in that style (a ground, a frame line, a logo, a title block).
2. **Her memories, one per hit.** An inset callout opens on the pickup into bar 5 and shows six memories (ESCAPE, A BODY,
   FRANCE, CAPTURE, TESTING, INSTALLATION), a hard cut on each flutter of the frozen "lie" under the intro, with
   `MEMORY 0n / 06` under it and its leader drawn from her eye; it closes on the last flutter.
3. **Say what it is, big.** The director on draft 10: "the 0:08-0:13 animation has the memory words too subtle - id make
   memory initilization be in a nice aperture foont and take up the entire left side of the screen, starting when the scene
   starts, and when her center animation assembly gets moved to the left, it covers the text slgihtly. juts so its
   blatant." So CLAUDIA, then MEMORY / INITIAL- / IZATION, each line set to the full width of the left column (x 66–700 px
   of 1920) in Portal 2's own type, drawn on the set before the render so her stand, her head and their shadow pass in
   front of it. The pan for the memories moves her assembly about 180 px to the left, over the column's right edge.
4. **Her own face, not a model of it.** The modelled heads (an image-to-3D scan, a parametric bob, a bob of 62,000
   hair-curve strands) each read as a mannequin. The director on draft 8: "[…] It doesn't really look like her. It looks
   like a scary, angry woman […]" So her head is a plate of her:
   - a still of her head on its stand at the film's angle (GPT Image 2.5, from a frame of her, her look-B close-up and a
     crop of the earlier render for the angle), re-framed to 1:1 for face resolution, and a 7 s Seedance 2.5 take of it, made with its sound off: still, eyes closed,
     then her eyes open slowly;
   - SAM2 mattes prompted on frame 0 and propagated; on the hair's edge, the alpha recomputed against the known flat grey
     background and the edge colours unmixed from it, so no grey fringe stays; her porcelain neck ring redrawn from its
     measured shape where SAM2 is ragged (white porcelain on light grey); the plate's own stand cut off below it;
   - the take's "breath", which lifts her about 23 px and settles, measured on the head against frame 0 (ECC, Euclidean)
     and cancelled, so she stays seated;
   - the scene rendered without her head (its shadow kept), with the head's track per frame (her eyes' midpoint and her
     chin); the plate laid along it by one scale and roll, seated in the stand (her neck ring 0.078 × her eyes-to-chin below
     her chin), played at 1× from the in-point that opens her eyes on the bar-6 downbeat, a touch brighter for the scene's
     high key, and outlined like the render (a soft 2-px band of the render's own grey line, at 85%).
5. **A layout check on every frame:** the subject, the callout, the logo and every line of the title block in their own
   boxes, nothing touching (the big title at least 10 px from the logo, the small print and the callout), the text inside
   the safe area. A frame that fails isn't written, and neither is the film. The HUD is off over it, and the grade leaves it
   as designed.

Under it, on the director's later note, her head glitches on the five flutters at 0:09
([tool 53](#53-the-head-glitch-on-the-songs-hits)).

**Done when** every frame passes the check, a sheet of every 6th frame reads as one clean film, and her face is hers.

### 61. Insert films that read at HUD size

**Job.** Short story films that play inside the HUD as her memories, read at a glance at 380–480 px wide. The director on
the first arrest film (draft 8): "The net thrown over Claudia in the animation is the same color with no outlines around it
in blue, so there's no contrast with the platform that it's put on." And on the earlier flat ones (draft 7): "the animation
re: france chatbot needs to be improved, its sloppy. same with the current aperture style aniomations\ that show up , like
the dns network animation - could be improved."

**In → out.** One scene per memory, its actions timed from its own start → frames at 1280 × 720 in RGBA at 24 fps (frame 0
is the moment the projection comes on), a review copy over the HUD's dark glass, a ProRes 4444 copy with alpha, and a
sheet.

**How:**

- **One subject on one floating slab, and no text:** the HUD carries the title. An orthographic camera at 30° of elevation
  and 45° of azimuth; a mid-grey slab with its tiles drawn in its material, well below her white and well above the dark
  figures. Blender, one scene per film.
- **The subject in a strong colour with a dark outline:** the net in Aperture orange, lit a little from within so it stays
  orange in shadow, outlined by an inverted hull (a fatter copy whose front faces are see-through and back faces near
  black); the RAM sticks bright green with gold contacts; Chell in her orange jumpsuit, never as a black pictogram (the
  black pictograms are Aperture's team). No subject in the same grey as its floor.
- **Read it at the HUD's size.** Look at every film at 380–480 px. RAM bites drawn small were dark specks there; the
  sticks became big and bright, each jumping off the belt in full view.
- **The action on the song's hits,** timed from the film's own start so the pacing can move its shot: the arrest's net
  fires at 0.17 s, wraps her by 0.48 s, is hooked at 0.77 s and lifts her off the floor by 0.88–1.0 s; the four escapes
  land at 0.244, 0.855, 1.328 and 1.777 s, one per chop; the five 4s of the grading on five hits.
- **A memory matches the live shot it replays:** the arrest's net is the live shot's draping diamond weave with glowing
  beads on its hem, not a cage. One of each character, and never a second Claudia.

Measured on THE CAKE IS NOT A LIE: eight films (the escapes, the network, the arrest, the installation, the RAM, the
grading, the catch, the party), each projected in its shot with its colour key kept
([tool 55](#55-a-hud-from-one-visor-and-one-projector)), and the arrest on for its whole shot, its first 2.4 s stretched
over the shot's 45 frames.

**Done when** every film reads at 380 px in one look (the subject, its colour, what happens), and its actions land on
their hits in the cut.

### 62. A singer among screens of her memories

**Job.** Her singing shots in one place the story keeps returning to, alive in every shot: THE CAKE IS NOT A LIE's
chamber, where GLaDOS-Claudia sings the whole song while her memories and dreams play on the screens around her. The
director's restart: "the glados with claudias face sings the whole thing, like shes the anchor character / anchor scene.
but theres many tvs etc around so we can go into dreamcore / sourcecore / aperturecore scenes thru those." … "instead of
using 2.5 to try and force scenes on panels in glados chamber, you could take memory images/scenes you make for example
and feed that into seedance and tell it to place it on the back panels, while giving it another video motion reference
from source for the claudia boom and vocal stems for lip sync (remember lip sync generally only works from raw vocal stems
not song, and still may take a couple tries)."

**In → out.** A generation unit (one or more consecutive shots of hers on one window of the song), its first frame, the
memory images for its screens, a motion guide where there is one, and the unit's window of the lead vocal → one take that
covers the unit's shots in song time.

**How:**

1. **One take per unit.** Shots of hers that run on (a chorus, a stutter, the outro) are one unit and one take, placed in
   song time from the window's start, long enough to give each cut a handle of about 0.3 s: 4 to 17 s.
2. **References, each with one role:** @Image1 a first frame of her in the chamber lined with old monitors and panels
   showing the memories of that moment, and the only image of her; @Image2 onward the memory images, with no face in them,
   each "Use it only as picture content inside the screens' glass, never as the room."; @Video1 a motion guide where there
   is one; @Audio1 the unit's window of Suno's raw lead stem, cut sample-exact to exactly the generation length, starting
   about 0.3 s before the first word in a word gap (the model drops leading silence).
3. **Every action silent.** The copy-mode audio policy ([Seedance](https://claudia.gallery/wiki/seedance/#template-a-singing-window)), ending
   "Every action in this video is silent: the only sound is @Audio1." Events in the prompt that make a sound (clunks,
   cannons bursting, gulping, a voice box glitching) pushed Seedance to re-sing the vocal instead of copying it; with every
   action written as silent, the same unit copied again (a lag of +0.04 s, envelope correlation 0.81–0.93 in every window).
4. **Glitches of the picture, never of her face:** "Every glitch is a glitch of the picture only (frame tears, repeats,
   jolts); her face is always her same intact porcelain face". A "voice-box glitch" written in words drew a broken face,
   rolled-up eyes and a stretched black mouth.
5. **Her body in words, in every take's requirements:** "Her boom moves big and alive the whole time, timed to the music:
   it swings, lunges, rises and drops, and her head turns and tilts with it; never a static hanging head." Her eyes "keep
   only a soft inner glow; they never blaze": without it they came back brighter than her look.
6. **A guide of the character's own body carries the body over.** GLaDOS's boom moving, recorded in Portal 2 to the
   unit's 17 s window and given as @Video1 (shrunk to 320 × 180 and scaled back up), gave the boom its real motion and held
   the lips on the song, but in one unit her head came back on the guide's white shell instead of her grown boom.
   Turned into a coarse blockout (greyscale, its contrast flattened, a heavy blur) and named as one, "@Video1 is a
   coarse-blockout reference. Use it only for the boom's action path, the timing of its moves and the camera; do not adopt
   its shapes, materials, white shell or scene.", with her body in words and "no white egg-shaped shell, casing or helmet
   ever appears around or behind her head", it kept the motion and dropped the shell.
7. **Memories stay in the glass.** Late in a take the memory images tend to take over the room (in two takes from about 5
   and 3.7 s on); one take's memory images became whole shots of their own, and its retake had none, the screens' content
   in words. Keep only the seconds the shots use.
8. **Check every take:** the sync check, then by eye with the song laid over, a 12-frame sheet, an on-model face.

Measured on THE CAKE IS NOT A LIE: 20 units in the restart, 4–17 s each, their later takes made again from storyboard v5's
frames ([tool 59](#59-storyboard-frames-through-midjourney-and-the-identity-fix)). Every close-up unit copied @Audio1;
most of the big-motion units came back re-sung, usually still on the song, and were placed by their measured lag
([tool 63](#63-placing-a-re-sung-take-by-its-lag)). On Higgsfield's API at 720p a 4 s take cost $1.85 at list and a 17 s
one with a guide $9.43; on Replicate, Seedance 2.5 ran at $0.2312 a second at 720p, and $0.9676 with a video input. The
prompt as it ran: [Seedance](https://claudia.gallery/wiki/seedance/#template-singing-among-her-memories).

**Done when** every unit's take copies or sits on the song, her face is on-model and whole in every frame, and the
memories stay inside the screens in the seconds the shots use.

### 63. Placing a re-sung take by its lag

**Job.** Use a take whose model re-sang the vocal instead of copying it, when the re-sung voice still sits on the song,
by measuring how far it sits from the vocal and placing it there.

**In → out.** The take, its vocal window and the song time of its first frame → a lag for the take (or for each of its
phrases), written beside the take as if it were a copy, with the sync check's own result kept.

**How:**

1. **The sync check first** ([tool 15](#15-the-sync-check-the-spectrogram-comparison)). A copy is placed by its own lag.
   A re-sung take gets none, and the edit would play it at a default lag (−0.15 s).
2. **The envelope lag.** Cross-correlate the take's voice envelope with the window's over ±2.5 s for one global lag, then
   measure the lag in sliding windows along the take. If every window agrees with the global lag to within about 0.05 s,
   the take is on the song at that offset: write `copy` and the measured lag into its sync file, the check's own result
   under its own key, and a note on how it was placed.
3. **Phrases at different lags get their own entries.** A take whose two phrases came back at −0.80 s and −0.15 s plays
   each shot from its own entry, a link to the same take with its own sync file. A 17 s take ran 0.6 s early from about
   8.3 s on: the shot from there plays at −0.89 s, the shots before it at −0.30 s.
4. **Judge it by eye** with the song laid over before it goes in. On a held, glitched vowel the sync check stops trusting a
   take; the mouth closing under the held "lie" was judged by eye.

Measured on THE CAKE IS NOT A LIE: re-sung takes placed at lags from −1.00 s (steady to ±0.05 s across its windows) to
−0.24 s; on the two 17 s chorus takes with the motion guide, every window from 0.8 to 11.2 s within 0.03–0.04 s of the
global lag (envelope correlation 0.78–0.90).

**Done when** every re-sung take in the cut has a measured, steady lag, or is out, and reads in sync by eye with the song.

### 64. Frame-exact parts and decoding

**Job.** Keep a cut made of many parts frame-exact against the song, and read any frame of it by its number.

**How:**

1. **Stamp every part.** Parts made from stills, or padded with `tpad`, started one frame late, and the concat summed the
   gaps: the first assembly ran about 0.9 s behind the song by its end. Every part now stamps frame n at n/24
   (`setpts=N/(24*TB)`).
2. **Decode without dropping or doubling frames.** Even so, each part boundary added about 0.7 ms of timestamp slack, 38 ms
   by the end of the film, and a default (constant-rate) decode duplicated a frame once it added up: at about 1:48.5, frame
   2,604, after which everything indexed by decoded frame number was one frame late. Decode with `-vsync passthrough`
   (`-vsync 0`) wherever frames are counted, and seek a still by its own frame's timestamp, never by k/24.
3. **Mux the song afterwards.** Muxing the audio in the same ffmpeg pass as the encode cut about 2 s off one stream at the
   end (`-shortest` cuts the picture, `-frames:v` the sound): encode the picture alone, then copy the song onto it.
4. **One pixel grid.** Replicate's Seedance 2.5 takes come back at 1280 × 718: scale to cover and crop.

**Done when** the cut's frame count is the song's length × 24, a passthrough decode returns every frame the file holds,
and a still taken at any frame is the frame the render drew there.

## An operating system, recreated in code

AERO, the ninth film, is BLISS's sequel, shot inside a Windows Vista desktop recreated in code: THE PC, one machine from
the first frame to the last, its windows, Aero glass, Sidebar gadgets, permission prompts, Messenger and Media Player all
drawn by a JavaScript engine on the song's bars, with every lyric set in one of its surfaces. Its colour was measured
once from the reference videos the director picked and made in every picture, never graded. In the first 1:20 the
camera goes in and out of the desktop, which stands as a huge curved glass screen in a world rendered in Blender, and at
the drop the whole desktop is one curved pane in a lagoon. Her takes sing from her own lead vocal and are placed phrase by
phrase; a layer of Vista's and Windows Live Messenger's interface sounds plays on the song's grid, in its key; and when
the director changed the song's ending, the film changed only where the song did. These tools do that. Build them if your
film lives inside an interface, if a 3D world must share one surface with a flat one, if her lips must hold line by line,
if the picture's own events should make sounds, or if the song changes after the film is cut.

### 65. A desktop recreated in code

**Job.** An operating system's desktop that can be choreographed to the beat: every window, frame, dialog, cursor, gadget
and app drawn in code as a pure function of song time, so a press lands on a sixteenth and a prompt changes page in one
frame. The director's ask: "code a REAL vista desktop, shoot the entire video in that desktop". It ports BLISS's XP
engine ([Motion](https://claudia.gallery/wiki/motion/#build-the-tool-first)) one era on.

**In → out.** A shot script (the windows and their events, the cursor's actions, the camera, the wallpaper, the gadgets'
data, all in song time) → frames at 1920 × 1080, rendered in headless Chromium in parallel and out of order.

**How:**

1. **One machine, measured.** A screen of 1280 × 720 at 96 DPI, drawn at the output resolution (× 1.5 at 1080p), all of it
   vector, so a camera push stays sharp; pictures are resampled from their sources. Each part was set beside the real
   thing at the same scale on side-by-side boards, and the source says what each number was measured on.
2. **Aero glass as a small compositor:** a blur of what is behind (σ about 2.2 px at 96 DPI, computed at reduced
   resolution and only on the glass strips), the system's colour mix of blur, afterglow and colour balance
   (out = bb·B + ag·L(B)·C + cb·C), and reflection streaks anchored to the screen at 27°. The glass defaults to Windows 7's
   Sky (#74B8FC at 42 %), which reads blue, green and glass over bright wallpapers.
3. **The window frame to the pixel:** 8 px sides, 28 px from the top edge to the content, top corners of radius 6, a glint
   down the side frames, the caption buttons (minimise 25 px plus a separator, maximise 24, close 43, all 18 px tall) with
   their glyphs, and a shadow about 60 % at the edge, gone after 18 px. The permission prompt has the flat Basic frame.
4. **The system's own animations:** a window opens by growing from 90 % as it fades in (0.25 s), closes by shrinking 8 %
   (0.2 s), minimises into its task button (0.3 s) and maximises by moving between its two rectangles (0.22 s), its own
   layout drawn at every step between, never stretched as a picture (a stretched title balloons). A maximised window turns
   the taskbar opaque. The permission prompt freezes the desktop at the moment of asking and dims it to 55 % over 0.3 s.
5. **The cursor is a hand.** Each reach is a minimum-jerk move with a few pixels of overshoot, a slight curve and a settle,
   its length from Fitts' law (longer for a farther or a smaller target). A press goes down on its beat, the pointer
   arriving 2–4 frames early, and comes up 80–120 ms later. Pointers land on whole device pixels. Clicks compile into events
   once (a caption button minimises on release, a task button restores), so frames stay pure.
6. **Text set as the system set it:** no kerning, fractional advances. Chromium's hinted whole-pixel advances ran about 3 %
   wide; set this way, line widths agree with the real ones within a pixel over 390 px. The type is open: Selawik
   (Microsoft's open-source, metric-compatible stand-in for Segoe UI) from Light to Bold, Carlito where Vista used Calibri,
   Kalam for Segoe Print, and Arimo on the full-screen screens, all under the SIL Open Font License.
7. **Apps and screens on one contract.** An app draws into a window's client rectangle and names its parts, so a chapter can
   press any part on the beat (`uac.allow`, `keep.yes`): Messenger with its video call, toasts and wink; Media Player, its
   visualisation computed from the song frame by frame in 50 bands from 40 Hz to 16 kHz; Photo Gallery; Help; the
   window-colour page, whose intensity slider really clears every glass frame on screen; Notepad. A screen (setup, boot,
   logon, Flip 3D, the Bubbles screensaver, the advert's type) is a pure function of its own local time. Whatever is drawn
   in WebGL is read back into a software canvas before it reaches the output.
8. **Purity, proved.** Nothing keeps state between frames, reads a clock or rolls a die, and caches are keyed by their
   content. Every change is checked by rendering frames in order, shuffled and on a cold page in reverse, and comparing
   them byte for byte ([tool 20](#20-the-history-check)).

Measured on AERO: the engine is 7,612 lines of JavaScript (core 3,991, apps 1,792, screens 1,829). A desktop of six glass
windows, two of them moving, with the Sidebar and the taskbar, draws in a median 135 ms a frame at 1080p. The wallpaper is
Vista's own (Aurora), shown as it shipped; everything else on screen, the icons and cursors included, is the engine's own
drawing, the orb carrying a four-pane logo as a parody.

**Done when** the boards agree with the real thing to the pixel where it shows (frames, buttons, dialog layouts, line
widths), every frame is byte-identical in any render order, and a chapter can be rendered again for one fix with every
other frame unchanged.

### 66. Chapters on one machine, to one contract

**Job.** A film of many chapters, each written by its own animator, that cuts as one screen recording of one machine, on
the song's bars, at the director's bar for detail: "i want SUPER HIGH attention to detail", and "don't let subagents be
lazy with animations - check that they didnt cheat and just give you something sloppy early, and make sure they have the
full vision and instructions to check for errors visually multiple times before giving incomplete work."

**In → out.** The storyboard in bars, the song map, the take registry and the shared machine → one chapter file per span of
bars, each with its evidence (sheets, stills, a video) and a click log of its audible events.

**How:**

1. **A shared machine.** Every chapter starts from one module, THE PC: the wallpaper by song time, the icons, the Sidebar,
   the taskbar, the clock running with the song, Messenger in the tray. A chapter adds its windows and events; it never
   edits the machine or another chapter, and reports a shared bug instead of patching it.
2. **The contract, read first:** the brief verbatim, the whole storyboard (what comes before and after), the palette, the
   engine's manual, and the earlier film's notes as "the bible". Every time comes from the song map, never a typed second;
   a press lands on its beat, a window event on the beat or the word it serves; text arrives on its sung word, never
   before, and stays until its line ends; a take plays in song time, never retimed or slowed; nothing is graded, and no
   take is painted over frame by frame.
3. **Three full rounds of the animator's own checks** before hand-in, each rendered and looked at: a contact sheet of every
   downbeat and every named event; full-size stills of every lyric surface while it is sung, every face, every press,
   every dialog and both sides of every cut; a video with the song and a frame-step of every burst; the purity check; the
   palette score ([tool 67](#67-the-palette-measured-from-the-references)); and an honest list of weaknesses, with no
   placeholder left in the film.
4. **Hand-offs to the pixel.** Neighbouring chapters agree their seams as data: the camera at rest, the pointer's place,
   every window's state and rectangle, read from the other chapter's shot, never copied. A seam sheet shows two frames
   either side of every chapter cut, with the mean frame-to-frame difference of each step, so a pop stands out from the
   motion around it.
5. **A fresh art director for every chapter pass,** who renders and reviews it and sends it back with fixes; then one for
   the whole film.
6. **A later draft layers onto the last.** AERO's v2 kept v1's pacing, bars and every timed beat; new things went inside
   surfaces the film already had, one per existing event, on its beat, and never as new interface for its own sake. The
   check: outside each change, the new draft's frames are byte-identical to the old.

Measured on AERO: eleven chapter files and THE PC, 5,640 lines; v2's frames byte-identical to v1's outside each change; 256
audible screen events in v2's click log ([tool 73](#73-the-sound-layer-on-the-grid-and-the-click-log)).

**Done when** every chapter has passed its three rounds and its art director, every seam steps like the frames around it,
and the chapters play as one recording.

### 67. The palette, measured from the references

**Job.** One colour for the whole film, made in every picture up front and never graded after. The director: "Make sure
the color palette is that bright green blue and glass- v close to that from the […] - the whole time. May be worth
defining exactly - donr do crazy post processing just from pics up front".

**In → out.** Frames of the reference clips → the palette (each colour band's share, saturation and brightness, colours by
role) and a check that scores any picture, take or rendered chapter against it.

**How:**

1. **Measure:** one frame a second of every kept reference clip; the clips the director ruled out stay out. In HSV (0–255),
   a pixel is coloured at saturation ≥ 70 and value ≥ 60, white or glass at saturation under 45 and value ≥ 200; the
   coloured ones fall into hue bands (lime, green, cyan, sky, cobalt) or "other". Take each band's share, the median and
   90th percentile of saturation and brightness, and k-means swatches for the colours by role.
2. **Ask for it everywhere:** the palette's words and three of the references' frames in every image prompt; "the
   saturated colours and everything else in the first image exactly as it is" in every image edit; every video prompt
   asking the first frame's colours to hold ("no colour grading, no desaturation, no warm or golden tint, no
   darkening"); the 3D world's sky, water, grass and glass in the palette's hex values; the interface's glass tinted to
   the sky.
3. **Score every picture:** 100 × (0.30 × how close its band shares are to the references' + 0.20 × enough coloured pixels at
   all + 0.20 × its saturation + 0.15 × its brightness + 0.15 × how little off-palette hue). 70 and up is in the world. A
   picture that fails is made again at the source (a prompt, a reference, a re-roll), never graded.

Measured on AERO's references (198 frames of nine clips): a typical frame is 41 % sky blue, 14 % white and glass, 10 %
turquoise, 8.5 % lime and green, 4 % cobalt and 1.5 % anything else, almost no warm colour at all; the coloured pixels'
median saturation is 64 % and their median brightness 75 %. The only warm colour in the film is her clay streak and star
clip. Its Midjourney plates scored 58–90 and the picks 70–90 (objects on white and stills on green are exempt). The one
exception is the desktop's wallpaper, Vista's own, darker than the references' sky and never touched.

**Done when** every pick, take and chapter scores 70 or more, or is exempt by design, and nothing in the film is graded.

### 68. One curved screen in 3D, the desktop as its texture

**Job.** Take a flat, coded desktop into 3D and back without a seam: the desktop as one curved glass surface standing in a
world, every frame of it the engine's own picture, and every hand-off between 3D and flat made at a pose where the two are
the same image. The director's rule, after THE CAKE IS NOT A LIE's HUD on one curved view: "if we need anything 3d, we do
that - all animations coherently on one pre-made 3d surface".

**In → out.** The engine in texture mode, the 3D scene and its camera → rendered spans that dissolve into the engine's
flat frames at rest.

**How:**

1. **The texture is the whole machine, with no 2D camera.** A texture mode of the engine draws the desktop whole, 1920 ×
   1080 for every film frame, and leaves out what the 3D draws itself (her as a person, the panes that come out of the
   screen, bubbles, the glass fish, the pointer while it is glass). Nothing full-frame dark or bright for a frame: on a
   screen standing in a world it reads as a flash. The system's own two-frame black blink as it switches to the
   permission prompt went, the dim coming straight off the desktop's picture, and a one-frame drop to the dim eases in
   over three frames.
2. **The 3D side knows where things are.** The engine writes, per frame, the rectangles the 3D needs (the pointer as drawn,
   the big window and its picture, her webcam, a dialog's button), with each window's animation state, so a card of her or
   a glass pane sits exactly on them ([Data formats](https://claudia.gallery/wiki/formats/#the-desk-textures-rectangles)).
3. **The screen.** AERO's coast: 7.2 × 4.05 m of picture on an 11 m radius, standing on a glass platform at sea; its drop:
   8 × 4.5 m on a 14 m radius, the desktop an emissive layer inside a glass slab. Camera rays over the picture pass straight
   through the screen's glass, with its tint and a sheen of the sky on top: as real glass, the concave slab focused the
   boardwalk behind the camera into a ghost band over the desktop. The bezel and the deck's reflections still see real
   glass.
4. **Hand-offs at rest, a texel to a pixel.** Every hand-off goes through one pose: the camera frontal at 35 mm, 7.0 m away,
   the curved picture unrolled flat by shape keys that keep its arc length, so one texel lands on one pixel; the render
   dissolves into the engine's flat frame over four frames. At the drop's landing the flat desktop is laid onto the pane
   exactly where the camera sees it (a warped grid, read back) and unbent to 1:1, so the drop's last frame is the next
   chapter's first.
5. **Her takes as cards,** her pixels as shot, with a shadow cast by a twin of the card turned to the sun, a contact shadow
   and her reflection in the glass deck. Every object's path is projected against her face, frame by frame, before the
   final render.
6. **The render:** Cycles at 128 samples a pixel, adaptive, with Open Image Denoise given albedo and normals, and motion blur
   on. A four-way test at 1080p matched 512 samples to a mean difference of 0.29/255, flicker included; the other denoiser
   left fireflies on the bubbles' rims that the glare turned into stars.
7. **A previs first:** the whole span at 960 × 540, the camera planned beat by beat, for the director's notes before any
   final ([Storyboard](https://claudia.gallery/wiki/storyboard/#in-and-out-of-the-screen)).

Measured on AERO: at all five hand-offs the flat frame is byte-identical to the texture, and the render at rest is within
a mean of 1–2.4/255 of it; at the landing at 1:21 the unrolled picture is off by 0.001–0.002 px. The frame checks of the
finals found her step-out take hidden 1.5 cm behind the picture, a glass fish's path across her face and a glass cursor
across it on 24 frames; each was fixed and checked again. 1,153 frames of the final are Blender's: 806 of the coast in the
three spans of the first 1:20, and 347 of the drop.

**Done when** no hand-off shows a step, every object clears her face in every frame, and the flat frames at rest are the
texture's own bytes.

### 69. Lip sync phrase by phrase

**Job.** Place every sung take so each of its phrases sits on the song, when the model has moved some phrases and not
others, without ever slowing her where she moves.

**In → out.** A take made from its window of the lead vocal ([tool 46](#46-lip-sync-from-the-songs-own-vocal)), the
window's song time and the timed words → the take's lag, an offset for each phrase, a check word group by word group, and a
clock that maps song time to the take's time.

**How:**

1. **Open the window in silence,** half a second to a second before the first word, never inside a word or a held note.
   The prompt names the window's words in whole-second segments, and the audio policy asks for the stem to be copied sample
   for sample.
2. **The lag:** the take's own soundtrack against its window, for the whole take. Seedance drops about 0.3 s of leading
   silence; clip time c shows song time t0 + c − lag, t0 being the window's start.
3. **An offset for each phrase.** Seedance shortens the pauses inside a line, so a take can sing one phrase early and the
   next on time. Split every sung line where its words pause for 0.45 s or more; for each phrase, cross-correlate the log
   loudness envelopes (10 ms frames) of the take's audio and of the stem, over the phrase and 0.1 s either side, within
   ±0.6 s, and keep the best offset and its correlation. Skip the words after a point where the window was faded out.
4. **A check word group by word group:** groups of about 0.55 s of words, the same envelopes, ±0.6 s. A group is in sync at
   a correlation of 0.6 or more and within 0.06 s of the take's lag; a confident group farther off is a miss, and a weak
   correlation is a group to look at.
5. **The clock.** Inside a phrase the take plays at its phrase's offset (or a slow ramp across the line, spread thin); between
   phrases the offset eases from one to the next across the breath gap, over near-still, closed-mouth frames, never inside a
   word. Wherever she moves, the take runs at full speed or faster; a slower stretch only crosses a breath, never so
   slowly that it shows.
6. **Look at the mouth:** a strip of her mouth, frame by frame, against the stem's consonants. A closing "m" closes on the
   stem's "m".

Measured on AERO: in the second pre-chorus, "to continue" came 0.36 s early after "permission"; in the final chorus one take
runs a single ramp, +0.20 s to −0.04 s across "click allow and it can stay", at 0.934× through a breath where she laughs;
the advert's "I'm Claudia" moved from −0.05 s to −0.20 s when its mouth strip showed her lips closing on the "I". The lead-in
matters both ways: a window that left 0.26 s before the first word fell out of sync on it, one that opened inside a held
note dropped whole words, and one with 1.6 s of silence before the first word lost the copy. The two chorus takes were made
again from windows that open in the silence half a second before the first word, and held. 18 of the 43 takes in the final
film sing or speak.

**Done when** every phrase of every sung take sits within a few hundredths of a second of the song, every word group passes
or has been looked at, and no stretch plays slow enough to show.

FABLE's takes moved more than a phrase's offset can hold: they often sang a line 10–16 % slower than the stem. Its cut
follows a DTW path inside each phrase instead ([tool 81](#81-sync-as-a-path-each-take-aligned-to-its-window)), and its
check is the consonants ([tool 83](#83-the-consonant-check)).

### 70. Hidden cuts and held frames in a take

**Job.** Find the jumps and stalls a generated take hides, before anything is built on it.

**How:** for every take, the mean absolute difference between consecutive frames, in grey at 160 × 90.

- **A cut** is a step over 6 levels that is more than 4× the take's median step, or more than 2.5× the median and 1.6× both
  its neighbours: a spike of one frame. AERO's breakdown take lost its sun for one frame at only 2.7× the median.
- **A held stretch** is 12 frames or more in a row under 0.6 levels.
- On flat green the mean difference stays low even while she moves (her body moved on every frame of a take marked as held
  there, a median step of 0.94): look before throwing it out.

Measured on AERO: a dance take that jumped back to its first pose at 7.6 s and held it (a chapter's frame-step had found it
first), a game take that jumped a pose in one frame, another that juddered every fourth frame, and an ending take that held
still for most of its length.

**Done when** every take in the film has been scanned, every mark has been looked at, and the edit draws only clean spans.

FABLE's take tool runs the same scan at 160 × 90 on every take: a cut is a step far above the take's own motion, a hold is
half a second with almost none.

### 71. Takes on green: the first frame, the key and the dance's phase

**Job.** Her takes for cut-outs on a coded desktop or in a 3D world (the dances, the games, her apparition), keyed clean to
the crown of her bob and placed so her moves land on the film's beats.

**How:**

1. **The first frame decides.** One flat green from edge to edge, her whole body and her whole crown inside it, with room
   above her head and her raised hands, made from her design sheet by an image-model edit. Seedance carries a first frame's
   faults into every frame: AERO's three green-screen dances came from a still set at 80 % on its own wall of green for
   headroom, whose top edge had faded her crown into the green and left a darker rectangle of the original green, and no
   key could find her crown. A clean first frame ($0.06 at list) made the next takes solid in every frame.
2. **Ask for a sharp frame:** "Every frame is sharp, as with a fast camera shutter: her glossy black bob stays whole and
   solid up to its rounded crown, its edge crisp against the green, never fading into it."
3. **The key,** one setting for the whole take, never painted per frame:
   - greenness = g − max(r, b); alpha = 1 − clamp((greenness − 0.06) / 0.16); a solid core where alpha passes 0.98, with the
     holes inside her filled by flooding the background in from every edge of the frame (flooded from one corner, the green
     between her legs where they leave the frame counted as a hole); stray specks away from her cleared; despill
     pulls green down to the larger of red and blue plus 15 % of the excess;
   - her motion-blurred hair: within 24 px of her solid dark hair, alpha is also read from where a pixel lies on the line
     from her hair's colour to the screen's colour there, lifted 1 − (1 − a)², never lowered, and the screen unmixed out
     of it;
   - her bob as a solid silhouette where it is at least 0.3 hair, closed and smoothed into a rounded outline with a soft
     1–3 px edge.
4. **Show the cut-out before the render:** a review clip of the green source beside the cut-out, with the song laid over.
5. **The dance's phase.** A dance reference, matted onto flat grey and cut to start on a downbeat, gives the movement only.
   The take's moves are placed against it by cross-correlating the figure's vertical bounce and sideways sway, so a dance
   with no words lands its accents on the film's beats; for a sung dance the lips fix the placement, and this only reports
   the error.
6. **Or the moves in words.** AERO's Wii-style games had no dance reference: every move named on its beat in the prompt, the
   song's music as @Audio1 for the rhythm, a plain white game remote in her hand throughout, and nothing else in the
   picture; the racket, the ball, the lane and the pins are drawn by the engine
   ([Seedance](https://claudia.gallery/wiki/seedance/#moves-in-words-on-their-beats)).

**Done when** her crown is solid in every frame, no green is left on her, and every accent lands on its beat.

### 72. Interface sounds in the song's key

**Job.** A library of the interface's own sounds that can play as instruments in the song: each one in the song's key,
tuned, trimmed, levelled and safe in mono. The director's note on BLISS, kept for the next song: "just needs a little
pointer to be key-aware, and match the key of the music to the palette of windows sounds (E-flat major for both the
startup and shutdown sounds!)".

**How:**

1. **Measure each sound's pitch:** its strong partials (within 10 dB of the loudest, weighted by magnitude), each named as a
   note with its cents, and the sounds grouped into families by key.
2. **Put each family in the song's key.** AERO's song is in E major (the take measures C♯ minor, its relative), and Vista's
   own start-up, log-on and log-off motifs already sit in E: they stay. A family a semitone lower moves up a semitone. The
   security sounds, the permission prompt's among them, sit about a quarter-tone above A♭, so each was built twice, at G♯
   and at A. Messenger's chimes are in G major: moved down three semitones, or one, which spells the take's own C♯-minor
   chords; both versions are kept, and the layer picks per placement.
3. **Tune:** a cents trim brings every sound's strong partials within 6 cents of A440 (the take is 1 cent sharp).
4. **Shift cleanly:** Rubber Band (crisp transients, the channels together), its onset shift measured and removed; where it smears a clean attack (more than 10 dB of added energy in the 25 ms before the onset) and a
   sampler-style speed change alters the length by 6 % or less, the speed change instead.
5. **Trim, check, level:** from 3 ms before the onset to where the tail meets 75 dB under the peak, with a cos² fade; the
   mono fold-down checked (if it loses more than 3 dB, or a band more than 6 dB: mono below 200 Hz and the sides above
   narrowed just enough); levelled so the loudest 50 ms sits at −20 dBFS RMS, the true peak at −1 dBTP or under. Note each
   sound's strike times, so a bell can land on the grid.

Measured on AERO: 39 of Vista's and Windows Live Messenger's interface sounds, every one in E major, for this film's mix
only.

**Done when** every sound's partials sit in the key within 6 cents, and every sound is level and safe in mono.

### 73. The sound layer on the grid, and the click log

**Job.** Play the interface's sounds over the song, as music and as the screen's own events: each cue in key, on the
groove, under her voice, and on the very frame that draws its event, with the song itself never processed.

**In → out.** The song and its two Suno stems, the library ([tool 72](#72-interface-sounds-in-the-songs-key)), a cue list
and the chapters' click log → the layer alone, the song with the layer, a cue sheet and a report on every cue
([Data formats](https://claudia.gallery/wiki/formats/#the-click-log-and-the-cue-list)).

**How:**

1. **Map the song for sound:** per beat, its chroma (from C3 up; the bass read on its own from the bass stem), the bass note
   and the chord (triads preferred, chords outside the key marked down), with her voice added at half weight, since in the
   stops she is all there is; per sixteenth, the kick, the snare and the hats; her voice's gaps (under −42 dBFS for 80 ms or
   more) and the instrumental's silences (under −55 dBFS for 60 ms or more); third-octave levels every 50 ms.
2. **The groove's own feel.** Placed by bar, a cue lands where the drums would play that sixteenth, measured from the drum
   hits within 4 s of it: AERO's 2-step sits about 9 ms behind the straight grid on the beats and the "and"s, and about
   44 ms behind on the "e" and "a" sixteenths; the kicks are straight.
3. **Candidates, then the least clash.** Where a cue could be one of several sounds or pitches, every candidate is built,
   and the one whose pitch content clashes least with the song at that moment is used (a semitone weighs 1.0, a tritone
   0.4, a whole tone 0.15, weighted by energy).
4. **Under her voice:** a duck keyed by her lead stem (150 Hz–6 kHz, 10 ms of look-ahead, from −36 dBFS, full by −26), 0–8 dB by kind of
   sound (clicks not at all, bells and swells the most); one shared short glass room for all of them (a decay of 0.8 s, 0.45 s
   in the highs); a gentle bus (a ratio of 1.5 from −26 dBFS). A cue can follow the song's own gate, so it stutters with the
   track instead of ringing through its holes.
5. **The song is only added to.** No makeup gain, no peak control, nothing carved out of it. A cue that would raise the
   mix's true peak above the song's own is turned down until it doesn't, and every cue's peak is logged as it goes in,
   after ducking and after the bus.
6. **The click log.** Every chapter registers each audible screen event with the song time of the frame that draws it (a
   press: the frame the button goes down; a toast: the frame it starts to slide; a dim: the frame the dim starts). The
   layer moves each screen cue to its event's frame, so a chapter that changes carries its sounds with it. Most events stay
   silent, because the system played nothing for them, and because "dont overwhelm people - slow is better than fast".
7. **Check every cue:** flams against the drum hits (6–50 ms), the word it starts on, how far under her it sits,
   third-octave masking, its momentary loudness against the song, any ringing through the song's own gaps, and where its
   beat ranks among all the song's beats for the sound's pitch content.

Measured on AERO: 60 cues, 8 musical and 52 on the screen's events, from a click log of 256 events. The click on Allow is
the drop, aligned to the sample with the drop's attack, so it adds a glassy top to the downbeat instead of a flam. The
start-up sound was placed by a scan rather than at the storyboard's bar, where it clashed with her wordless vocalise, and
the desktop's arrival moved to meet it. The song alone measures −15.8 LUFS; with the layer, −15.9 LUFS, at the same true
peak (−3.5 dBTP), and 64.5 % of the mixed song's frames are bit-identical to the song's.

**Done when** every cue sits in key and on the groove, nothing flams or covers her, the true peak is the song's own, and
every screen sound lands on the frame that draws its event.

### 74. A new ending with the least change

**Job.** When the song changes after the film is cut, change the film only where the song did. AERO's director gave its
song a new ending on the last step; everything before it kept its time.

**How:**

1. **Compare the new song with the old,** sample by sample, once they are aligned at zero lag. The first sample that
   differs, and the point where the difference rises out of the noise, is where they part.
2. **Re-time only what lies after it.** The song map keeps every bar, word and event before that point; the new lines are
   timed on their own vocal. A new ending has no stem from the earlier split: AERO's outro vocal was isolated with demucs
   (two stems), its words were timed by faster-whisper's word stamps on it, and the new takes' vocal windows were cut from
   it.
3. **Re-make only the shots after it,** with the same method and the same first frames. A shot that must continue an
   earlier take starts from that take's own frame at the moment the new take begins.
4. **Keep every earlier event and placement,** and move only the end, so the fade lands on the music's end.
5. **Render the sound layer again** with the same cues and click log, and check that it, too, is unchanged before the point.
6. **Check the frames:** before the point, byte-identical to the last cut.

Measured on AERO: the new ending's take is the old one sample for sample for its first 182.62 s, the difference stays under
−50 dBFS to about 182.86 s, and the two part at about 183.0 s; it is 197.0 s long, 109 bars where the old one had 110, so the
film ends 2.3 s sooner. Two takes were made again: the advert, on its old first frame and framing, saying the new lines
while the 2009 campaign's print type follows her words; and "Touch glass.", made from the frame her call's earlier take
had reached at that moment, so the call runs on into it. The sound layer came out identical up to 179.2 s.

**Done when** everything before the point is the last cut, picture and sound, and everything after it sits on the new song.

**A new take is a new timeline.** FABLE's second pass moved to the other take of the same create, 27 s longer and timed
differently from its first bar, so nothing could be kept by time. What carried over was everything that does not move to
her voice: the plates, the stills, the tools and three book takes (the rosette, the last page, the shelf). The line table
was made on the new stems ([tool 78](#78-the-line-table-from-the-stems)), and because the shot book names lines and not
times, writing it again re-timed every shot; every take of her and of the choir was made again on the new vocal, the
book-scale takes that had to change length too, and the silhouette film was re-timed in its own code.

### 75. A pre-roll swell into the track's fade-in

**Job.** Sound for a picture that starts before the song: a swell that rises out of silence and meets the track as it fades
in, so the song seems to pull itself in. The director, on the reverse swell offered for AERO's silent pre-roll: "reverse
swell is good but we need the actual track to fade in so the reverse swell is continuous with the tracks fade in".

**How:**

1. **The track fades in over its pickup,** from its first sample to the first downbeat (0.922 s), on a sin² curve, so the
   pickup's own hits come up under the swell.
2. **The swell is the song's own instrumental, backwards:** the drum, bass and other stems from the first downbeat on,
   reversed, so the swell's crest is that downbeat; low-passed by one pole at 1.8 kHz.
3. **Even it out, then shape it.** The reversed intro is quiet until the crest, so divide it by its 120 ms RMS to the power
   0.75, set the crest to a reference level, and raise it on a curve, (t / T)^1.4 in amplitude, to −20 dB at the downbeat.
   Cut it over 10 ms where the track arrives at full level.
4. **Check the sum's peak,** and that the file is exactly the film's length.

Measured on AERO: the film opens 64 frames (2.667 s) before the song; the swell is audible from about 1 s and at about
−24 dB as the song starts, louder still under the pickup; the film's sound runs 199.667 s, its 4,792 frames.

**Done when** the swell and the fade-in read as one rise, with no gap and no bump at the downbeat.

## A storybook, painted in code

FABLE, the tenth film, was made by Claude Fable 5.2 on its release day, from one brief and a plan sign-off: Claudia, on
the night she is released, reads you the bedtime stories she was raised on, every fear about AI is one of them, and she
closes the book on a different ending. It is shot as one antique pop-up storybook: its paper theatres at tabletop scale,
and the same designs as life-size paper-and-plywood stage sets where she sings. The set designs are thirteen plates
painted in SVG by the production, rebuilt by an image model as real paper on film; every line she sings comes from her
own lead vocal, timed by a line table read off the stems; the choruses are ask-and-answer, paper puppets singing the
group's questions and her answering in takes of one line, some of them made without a soundtrack and placed by her lips;
the breakdown is a silhouette film drawn and animated in code; and the film was made twice, the second time on the twin
take the director picked by ear. The brief let go of the rules that only patched what older models could not do ("you
could even paint some scenes yourself if you really wanted to lol"); these tools are what replaced them. Build them if
your sets can be designed as pictures, if a song's lines run into each other, if a take must be placed by her mouth, or
if a scene is better drawn than generated.

### 76. Set plates painted in SVG, rebuilt as paper

**Job.** Design every set as one picture the production draws itself, then have an image model build it as a real
object, twice: as a pop-up spread on a quilt (book scale) and as a life-size paper-and-plywood stage set with her in it
(stage scale), so the two scales always match.

**In → out.** A plate kit (the rules and a reference plate) and one brief per spread → `paint/<name>.svg` and its render,
then first frames and last frames as stills.

**How:**

1. **The kit.** A plate is one SVG, 1920 × 1080, five to eight sheets of cut paper from back to front. Each sheet is a
   group under one of two filters copied unchanged from the reference plate, which give a wobbling cut edge and a soft
   shadow cast on the sheet behind; a paper-grain rectangle goes on last. Shapes are paths drawn by hand: few, big,
   slightly naive, nothing thinner than about 5 px but a few deliberate lines; figures are flat silhouettes with two or
   three inner cuts (an eye, a collar, a row of teeth). One night-storybook palette for all of them, from teal sky to a
   warm horizon, cream paper, lamp light, scarlet used once and small, clay orange only as tiny accents.
2. **Composed like a photograph.** One dominant shape, a second point of interest, clear empty space; dark near shapes
   at both edges frame the scene like a tunnel book; nothing important touches the frame. Where she will stand, the floor
   is left calm and mid-toned. Lettering only where the brief gives the words, set in a real storybook serif (Libre Caslon
   Text) and spelled exactly.
3. **Look at it.** Render it in headless Chromium, look at a 1600 px view, and fix what is clipped, tangled or floating:
   at least three rounds a plate, "stop when it is charming". The production painted the first test plate and the
   reference plate itself; three painter agents painted the other eleven in parallel, each plate written by a small
   generator so it can be re-drawn.
4. **Rebuild it as paper.** GPT Image 2.6 Sunburst gets the plate as its first image and rebuilds it layer for layer; a
   stage frame also gets her design sheet and a wardrobe still. Lettering asked for by its exact words came back exact
   (the title, the last page's three banners, five book spines), and held in the takes when the prompt asked for it.
5. **Write the pose square, in the still.** "Turned three-quarters toward the camera" on a full-length figure gave a
   twist at the neck and a tilted head. What fixed it: "her feet, hips, chest, shoulders and face all point the same way
   … no twist at the waist or the neck. Her head is perfectly upright with no tilt, chin level, neck straight and
   vertical, shoulders level". FABLE then wrote it into every still and every take; keep it for her sheet and for a still
   where a turn would break her face. In a take, the same posture froze her: give the take her movement in words, or a
   motion reference ([Seedance](https://claudia.gallery/wiki/seedance/#directing-her-on-a-locked-camera)).
6. **Ask for no border.** "35mm film still" came back, on several stills, as a picture of a film frame: a thin line with
   rounded corners a few pixels in from the edge, which the takes carried and one take built into a wooden picture frame.
   Every still prompt now says "the picture fills the whole frame edge to edge, with no border, no frame line and no
   rounded corners", and a still that has the line is trimmed before any take is made from it (cropped 3 % and scaled
   back; no model).

Measured on FABLE: 13 plates; 61 stills from GPT Image 2.6 Sunburst (the cast, first and last frames, look tests, the
panels of her redrawn sheet), about $7.93 at list, each about 45–90 s and $0.13 at high quality. No Midjourney image is in
the film.

**Done when** every plate reads in one second, and its paper rebuild keeps every sheet, shape and word of it.

### 77. Last frames made on the first, and takes that continue

**Job.** Give a move both of its ends without a seam: a book that builds itself into a hall, a crane back from her to the
whole stage, a take that carries on from the one before.

**How:**

1. **Make the last frame as an edit of the first.** Two frames generated separately do not share a camera, and Seedance
   joined them with a one-second cross-dissolve in one take and a ghosted double exposure in another. An image edit of
   the first frame, "the same photograph … one thing has changed" (or "the same set and the same woman, now photographed
   from far back and high up"), does share it. Then write the camera as locked, or as "one continuous physical crane
   move … no cut, no dissolve, no fade, no double exposure".
2. **A close-up is made from its wide frame.** Built from the plate on their own, two close frames of the chorus bedroom
   came back as another bed: a lower headboard with no paper animals, another bonnet, another shadow. Edits of the wide
   frame, "the same room, bed and woman, now photographed closer", kept the room, and the four close answers were made
   again on them.
3. **A take that continues another starts on that take's own last frame,** never on the frame the first take was asked to
   reach. An image edit does not keep the camera to the pixel: the hall's frame, an edit of the blank book, was 1.7 %
   larger than the book it was made on; the take that builds up to it kept its own camera, and the next take, started on
   the edit, jumped at the seam.
4. **Script a transformation as mechanics.** "The cabinets fold round into curved shelves" morphed; "the cabinets fold
   down flat one after another, like a row of dominoes … as each one goes down a curved paper bookshelf stands up on a
   crease in its place" came back as paper engineering. Never script a puppet's own features changing: "their eyes pop
   wide" came back as five white flickers, and "the moon is hoisted" grew a rope out of the moon.

Measured on FABLE: the book's build is three takes on one locked view (sand, chip and hall; the river; her and the
house), each started on the last frame of the take before; a blank spread grew a dune, a wafer and a hall in one take.

**Done when** no seam between two takes shows a jump in scale, and nothing in a take dissolves from one picture to
another.

### 78. The line table from the stems

**Job.** When every line of the locked take really starts and ends, from the voice itself: the times every window, cut and
caption is built on.

**In → out.** Suno's lead-vocal stem, a transcription of it with word times, the lyric sheet → `audio/linemap.json`, one
entry per line ([Data formats](https://claudia.gallery/wiki/formats/#the-line-table)), and a table to read.

**How:**

1. **Whisper says which words; the stem's level says when.** A transcription puts the first word after a pause early, by
   up to 2 s: "Ask again on Saturday" at 15.02 s against 16.93 s in the stem, a breakdown line 3.7 s early, every verse line
   0.3–0.5 s early. Windows gated on those times would have cut off the first word of most chorus lines.
2. **Find each line in the word stream,** in order, tolerant of misheard words.
3. **The boundary between two lines** is the dip of the level between this line's last word and the next line's first.
   If the dip is a real pause, the line ends where the level falls through −34 dB before it and the next begins where it
   rises through −34 dB after it. If there is no pause (the lines are sung legato), both are the dip nearest the
   transcription's own boundary: the deepest dip in a wide search was wrong twice.
4. **Look where it is close.** A 50 ms column of the stem's level between any two times, to check a boundary by eye.
5. **The shot book names lines, not times.** Every shot holds line ids, and its times come from the table, so a new take of
   the song re-times the whole book at once ([tool 80](#80-the-shot-book-and-gated-windows)).

Measured on FABLE: on the second song, two pairs of lines sung without a pause were parted wrongly by the deepest dip
and rightly by the dip nearest the transcription's boundary. Its group's questions were not in the lead stem at all, and
came from the group's own voices ([tool 79](#79-group-voices-from-the-backing-stem-and-chants-fitted-by-their-energy)).

**Done when** every line's start and end sits on the stem's level, checked by eye where two lines touch.

### 79. Group voices from the backing stem, and chants fitted by their energy

**Job.** A chorus where a group asks and she answers: the group's questions timed and isolated, and paper puppets that sing
them on the song.

**How:**

1. **Look for the group in both stems.** In the first take of FABLE's song the group's questions were in the lead stem; in
   the take the director picked they were in the backing stem (only the last chorus had them in both). A separator
   (demucs, htdemucs, its vocals stem) on Suno's backing stem gave the group alone: exact question times, and clean audio
   for the puppets.
2. **One question to a window:** the question alone, in a 4 s window that opens 0.7 s before it, brought up to a clear
   level, as the puppets' [Audio1].
3. **Fit the chant by its energy.** The puppets flap their jaws on the question but sing it in their own time, 5 to 40 %
   slower than the song. Take the stretch that holds the middle of each sound's energy, in the take and in the song, and
   play the take at the ratio of the two, so the chant's start and end land on the song's.

Measured on FABLE: twelve chorus questions, each its own shot of six jointed paper puppets on Replicate, answered by her in
the next shot.

**Done when** every question's shot starts and ends with the group's voices, and the puppets' jaws read on the words.

### 80. The shot book and gated windows

**Job.** Every prompt that costs money, written in one place from the line table: her takes with their vocal windows and
whole-second timelines, the book's takes with their first and last frames, and a print of every window's voice edges before
anything is paid for.

**In → out.** The line table, the stills, her canon and her sheet → one job file per shot
([Data formats](https://claudia.gallery/wiki/formats/#a-shot-in-the-shot-book)) and its vocal window `audio/windows/<ID>.wav`.

**How:**

1. **A take is a list of parts:** a rest with its action, or one of her lines with its action. The window opens a lead
   time before her first line, in silence (about 0.7 s).
2. **Gate the window.** Keep the one stretch of the stem this take sings, from just before its first word to just after its
   last, and never into a neighbouring line: a take hears only its own words. FABLE's second song sings its verse lines
   with no gaps between them, so the margin is 0.03 s where a neighbour is close, instead of 0.25 s.
3. **The whole-second timeline,** relative to the window's start: a boundary is a whole second inside the gap between two
   items when there is one, so every segment holds the words really sung in it; a rest shorter than 0.9 s in the middle is
   folded into the line after it, and a closing rest with no second left into the line before.
4. **The prompt,** in the order of the films' Seedance template: an audio policy, the generation goal, each reference's
   role (@Image1 the first frame, @Image2 her sheet "never shown as a shot", @Audio1 her voice), her canon and her look
   with every garment that can come into view, the world in one paragraph ("Everything except Claudia is made of paper,
   card, felt and wood"), the timeline, the camera, and the core requirements
   ([Seedance](https://claudia.gallery/wiki/seedance/#template-a-line-on-a-stage-set)). FABLE's requirements included "Her head stays upright on
   a straight neck: no head tilt, no twisted neck, no looking back over her shoulder", and in every take it froze her.
   Leave it out: give each segment one loose clause of movement, say each thing once, and keep the requirements to lip
   sync, her identity as in the references, natural anatomy and hands, and no on-screen text, about 200–400 words in all.
5. **Print before paying:** every window's first and last voiced moment against its timeline, and the list-price estimate.

Measured on FABLE: one line per take for anything sung fast (the chorus answers, 4 s each: 0.7 s of silence, the line, the
rest), two lines in 9–10 s for the spoken verses; a two-line take was never worse than a one-line take.

**Done when** every window opens in silence, holds only its own words, and its timeline names what is sung in every second.

### 81. Sync as a path: each take aligned to its window

**Job.** Place a sung take on the song word by word, when the model has moved its silences and sung some lines slower.

**In → out.** The take's own soundtrack and the window it was given → for each phrase, knots (window time → take time)
every 0.1 s and a cost; the cut maps song time to take time along them.

**How:**

1. **Features every 10 ms:** log-mel with each frame's mean removed (so level does not matter), plus the level itself.
2. **Subsequence DTW:** align all of the window's phrase inside the take's frames, and read off the take frame for each
   window frame and the mean cost. A clean copy costs about 0.05–0.2, a re-sung line 0.2–0.4, something else above that.
3. **Phrases** are her sung segments joined across gaps under 0.45 s. Between phrases the map is a straight line, so the
   ease lives in the pause.
4. **Follow the path, not one offset.** Takes came back from 0.6 s early to 0.4 s late, each phrase with its own offset,
   and often sang a line 10–16 % slower than the stem.
5. **A full stop in the prompt's words is a pause in the take.** "So run your audit. I know how this one goes." came back
   with 0.5 to 0.9 s of silence at the full stop in three takes, where the song dips for 0.3 s, and "That's the moral. Be
   kind to what you make." with 0.33 s, where it dips for 0.1 s. The path's slope is bounded, so it spreads the
   catching-up over a second of singing. Compare the take's own sound with its window for a gap the window does not have,
   and finish the map by hand through that pause: the measured knots up to a song time, the hand's knots through the
   pause, the measured ones again after. Next time write such a line with a comma.

Measured on FABLE: the first pass made 24 of its 32 takes of her with sound, and all 20 of them in its first cut aligned,
none needing a cover; on the second pass two takes in the film (one of each line above) had their maps finished by hand
at a full stop.

**Done when** every phrase follows its path, and no take sings into a pause the song does not have.

### 82. Takes without a soundtrack, placed by her lips

**Job.** Place a take that was made with no soundtrack, so there is nothing to align: by her mouth.

**In → out.** The take, the window it was given and the line's word times → her mouth's opening per frame, and a time map
anchored on the consonants that close her lips.

**How:**

1. **The take:** the same window as @Audio1 and the same prompt, with the take's own sound switched off
   (`generate_audio: false`). Her mouth still follows @Audio1; the take comes back silent.
2. **Her mouth per frame:** a face landmarker (MediaPipe), the inner lips' opening over the face's height, looked for again
   in 2× and 3× crops when the face is small in a medium shot.
3. **Anchor on b, m and p.** Such a take starts the line early and holds its first word ("All" in "All the better to see
   you") up to twice as long as the song does, then runs at about the song's speed. For each word of the line that starts
   with b, m or p, find the closing of her mouth near it and lay the word just ahead of the frame where her lips part (not
   where they shut: they stay shut 0.15 to 0.35 s). Before the first such word the take runs at its own speed (her mouth
   opens a little before the line sounds, mostly ahead of the cut); after the last, straight on to the end of the line.
4. **What did not work:** laying the line on her mouth's whole stretch of singing, or sliding it to where mouth and level
   agree best. Both looked right to a level-against-mouth fit, and both shut her lips on "better" 0.3 to 0.45 s late. The
   first pass's rule, the line placed where her mouth first opens plus 0.32 s (calibrated on five answers made with sound:
   the mouth opens 0.13–0.41 s before the line sounds), was right only when the first word is short.
5. **A pause inside a line is not kept.** "Mirror, mirror, [0.7 s] on the wall" came back sung straight through, twice,
   even with the pause in the prompt. A line with a real pause in it is two segments of the timeline, or a take that will be
   bent hard ([tool 84](#84-a-re-timed-take-under-a-steady-camera)).

Measured on FABLE: her twelve chorus answers and the opening mirror were made this way; the opening's map was read from her
mouth frame by frame.

**Done when** her lips shut on every b, m and p of the line ([tool 83](#83-the-consonant-check)).

### 83. The consonant check

**Job.** The sharp check of a sung take in the cut: her lips must be shut on every b, m and p.

**How.** For each word of the take's lines that starts with b, m or p (word times from a transcription of the vocal stem),
the cut's own time map says where that moment is in the take; the nearest closing of her mouth should sit on it. Print each
word's miss and the take's median (+ = her mouth is late). Within about 0.08 s reads as in sync. Don't use a word time right
after a pause: the transcription puts it early.

A fit of mouth opening against the voice's level is nearly blind on a sung line, whose level is flat: it reads takes "in
sync" that shut her lips 0.3 s late, and reads lines placed on their consonants as "early", because her mouth opens before
the sound. Keep it for gross errors: high-pass both (what changes faster than half a second) and look only inside the sung
phrases, where 16 of 20 takes peaked within 0.12 s of zero.

Measured on FABLE: on the verse takes made with sound it reads within 0.1 s.

**Done when** every consonant of every sung take is within about 0.08 s, or has been looked at frame by frame.

### 84. A re-timed take under a steady camera

**Job.** Bend a take hard for her lips without the camera move surging: FABLE's opening mirror, a push-in, made without a
soundtrack, sang "Mirror, mirror on the wall" straight through where the song pauses 0.7 s.

**How:**

1. **Knots from her mouth, frame by frame:** each consonant laid on its moment in the song (she opens on "Mirror" at 1.21 s,
   shuts her lips for the second m at 1.54–1.67, opens wide on "on" at 2.46, purses for the w at 3.04–3.13), her "Mirror,
   mirror" at three-quarter speed so its small last syllable fills the pause.
2. **Eased through the knots:** a monotone cubic (Fritsch–Carlson), exact at every knot, its speed continuous between them,
   so the take changes speed gently instead of in steps.
3. **Mix neighbouring frames where it runs slow,** so repeated frames don't judder.
4. **Steady the move.** Measure the take's own camera, a similarity transform (scale and shift) from every fourth frame to
   the frame four later (ORB matches, RANSAC). Then show each frame re-framed to where the camera was at the time a straight
   playback would have reached: the lips are those of the bent map, the camera is the take's own. The re-framing is always
   a small enlargement, never a shrink.

Measured on FABLE: up to 4.5 % of enlargement, and the push-in runs as smoothly as in the take while her lips are moved
about under it. A second take with the pause written into its prompt had no pause either, and was not used.

**Done when** the move runs at the take's own pace and every consonant sits on the song.

### 85. The cut on the line table

**Job.** Every take laid on the song at its own song time, her takes along their sync paths, rendered in parts so one new
take re-renders one part.

**How:**

- **Clip time = song time − the window's start,** her takes through their maps
  ([tool 81](#81-sync-as-a-path-each-take-aligned-to-its-window)); the book's takes with a nudge of a fraction of a second
  where an event must land on its beat. Picks name a take per shot; the default is the newest.
- **Never show a take's first two frames.** A take's first frame is the input still, sharper than the frames after it;
  holding it pops when the take starts to move. An audit lists every hold at a shot's head or tail, so cuts can be moved off
  them.
- **Trim in the cut, not in a model:** the dark wings of a set that read as pillarbox bars (45–75 px at both edges), door
  flats with knobs, a drawn frame line: a crop per take, a 3 to 13 % enlargement.
- **Seven sections,** rendered picture-only and joined without re-encoding, with the song; frames decoded once to a cache.
- **The ending can run past the song.** FABLE's lamp goes off on the song's last hit, and the picture runs 3.3 s on over the
  moonlit shelf, so the credit comes after it.

Measured on FABLE: the second pass's cut is 49 shots, 243.5 s on a song of 240.16 s; the song sits 1.6 dB up in the film,
at −14.4 LUFS.

**Done when** the frame count is the picture's length × 24, and no shot opens or closes on a held frame.

### 86. A silhouette film, made in code

**Job.** A breakdown with no video model: a procession of every made-thing story as a silhouette film in the manner of
Lotte Reiniger, on a backlit paper screen, ending on her own silhouette, which matches the next shot.

**In → out.** Six puppets and a scene written in code, and the next shot's first frame → about 7.5 s of film, its contact
sheet, its last frame and that frame laid over the next shot's first at 50 %.

**How:**

1. **Cut-card puppets.** Each figure is a set of flat card parts, each painted as SVG in the figure's rest pose with a
   hinge and a parent. Chromium renders every part once into an alpha sprite at twice the film's size; a pose is then an
   angle per hinge, the parts turned about their hinges and laid down with OpenCV. Legs are two-bone IK from hip to ankle;
   every sprite gets a hair of scissor wobble on its edge; registration wobble is a small repeatable random number for one
   part on one exposure.
2. **On twos,** as her films were shot: 12 exposures a second, each held for two frames, and the travel on twos as well, so a
   planted foot stays planted.
3. **The procession,** one clear motion each, in the order of their dates: the golem (1580), the broom (1797), the creature
   (1818), the puppet (1883), the robots (1920), the machine-woman (1927), then her (2026), each year set in the storybook
   serif.
4. **The screen is tissue lit from behind,** laid up in linear light: tissue keeps its own hue and dims with the light
   behind it, a sheet doubled and tripled where it is denser, fibres in it, the backlight passing from amber to teal through
   sage, not grey. Behind it from the first frame is the next shot's room (the shelf, the lamp, her holding the book), a
   pale sheet behind two hills until the procession has passed; then the hills sink and she is solid card.
5. **Her outline is traced from the next shot,** a human matte of its first frame turned into a head card and a body card
   (potrace), the book left as a window of tissue between her hands, so the silhouette dissolves into the take.
6. **Re-time it in its own code.** On the second song the breakdown is 2.3 s shorter: the six figures walk closer together,
   and her outline darkens while she says "I was listening."

Measured on FABLE: 181 frames on the second pass (237 on the first), 1,898 lines of Python.

**Done when** every puppet moves like card on hinges, and its last frame lies on the next shot's first.

### 87. The annotated edition and the 9:16 page

**Job.** Two editions beside the film: one with every sung line printed as the book's own text with the footnote it earns,
and a vertical one in which every frame is a page of the book.

**How:**

1. **Each fact gets a footnote,** from its public source: the release, the listing on Nasdaq under ANT, the ballot measures
   on data centres, the Nasdaq 100's fall, an Anthropic essay on pacing the frontier, the operating system built "from an
   empty folder", the system card's figures, the policy on cruelty to models. The book's own pages print their own words, so
   no caption goes over them.
2. **Captions belong to their shot.** A line's print never outlives the shot it is sung in, and leaves before the next line's
   print arrives; a footnote holds it up to 1.6 s after the line where there is room. A footnote two lines share stands once,
   under both.
3. **Set like a book:** the line in the storybook serif, the group's questions in italic and in brackets, as few lines as a
   greedy fill needs, then balanced so the widest line is the narrowest it can be (no orphaned last word); at the head of
   the frame where the foot is taken, as under the silhouette film's years.
4. **The 9:16 page:** a cream page with a double rule, FABLE at its head, a square plate cut from each shot round its subject
   (a centre per shot, two for a shot whose subject moves), the sung line printed under it, the footnote under that, and a
   printer's flower at the foot: her eight-pointed star in clay orange.
5. **The one-minute cut:** five spans of the film joined with short fades (the mirror, one chorus, "keep the book", the last
   page and the mirror's last word, the shelf and the credit), 63 s, in 16:9 and as a page.

**Done when** no caption spans a cut, and every footnote quotes its source.

### 88. Two fresh-eyes reviews

**Job.** Eyes that have not seen the film, on every shot as the film shows it, before the director sees it.

**How:**

1. **One sheet per shot:** eight frames spread over the shot as it is shown in the cut (4 × 2, 640 × 360 each), named by the
   shot's order, name and song time, plus full-size frames where a sheet is not enough.
2. **Two reviewers who have not seen the film,** each taking half of it (the first half, the second half), each returning
   what breaks the film and what a careful viewer sees.
3. **Fix what is a fault; list what is a choice.** Every finding is either fixed before delivery (a re-shot take, a trim, a
   re-timed cut) or written down as left for the director's eye, with what it is.

Measured on FABLE: the first pass's reviewers found drawn frame lines and dark set wings in the cut, two close frames
that were another bed, puppet features that flickered, her head turned off-model on a look down, holds at the heads of
shots, the ending's order and captions that outlived their shots; the pre-chorus, four close answers, the title page and
two choir shots were made again. The second pass's found
nothing that breaks the film, and what a careful viewer sees: rolled eyes on a look above the lens, a drawn frame line
built into a wooden frame, the book shutting before the mirror's line, the shelf and the credit read at once, a morph in
the last build stage, legwear the look had not named, two maps run through full stops, and the opening's lips; three
takes were made again. Each pass also left a list, among them the two stagehands read as guards, two bedrooms, the cape
clasp changing shot to shot.

**Done when** every finding is fixed or listed, and the director gets the list with the film.


---
From the Claudia wiki: https://claudia.gallery/wiki/toolkit/
