# Speech

The estate's speech-to-text stack: one engine, one hub, three lanes into it.

## What it is

**Parakeet TDT 0.6B v3** (int8 ONNX) through **sherpa-onnx**, with **Silero
VAD v6** in front and sherpa's **pyannote-segmentation** diarizer beside it.
All of it runs on the CPU. `modules/services/stt.nix` serves the hub;
`scripts/sinnix-stt` is the engine, the batch pass and the CLI.

This replaced whisper.cpp, which is deleted rather than kept as a fallback —
the operator's decision, recorded in `sinnix-mke` on 2026-08-11 and repeated in
`sinnix-uyvt.1`, whose title is literally "the good engine (**not whisper**)".

## Why not whisper

Three reasons, all measured on this host rather than taken from a model card.

**Quality.** 6.32 WER across 25 European languages including Polish, against
whisper `base.en`'s English-only. Verified on the operator's own ambient
capture, not on a fixture: a Polish utterance in an overnight chunk came back
correct. `base.en` could not have produced it at all.

**No silence hallucination.** whisper famously invents "Thank you." over a
quiet room. Over a lane that records all night, that does not produce a bad
transcript — it produces a diary of things nobody said, indistinguishable from
a real one. Of 40 consecutive ambient chunks, exactly one contained speech
(5.4 seconds); the other 39 produced nothing at all.

**Speed, and what it changed.** RTF 0.113 on dense speech; RTF 0.002 over a
VAD-gated 300 s ambient chunk — 0.74 seconds to process five minutes of audio,
and about ten seconds for an hour. Forty real chunks, 3.3 hours of audio, took
70 seconds wall.

That last number changed a design decision rather than merely being pleasant.
`sinnix-mke` budgeted ~1.5 GB of VRAM and put the engine in the shared
`gpu-inference` admission mesh, where a transcription and a resident LLM
exclude each other. The measurement says the engine needs no GPU at all, so it
sits **outside** that mesh: transcription is always available, and never queues
behind the model tier. The runtime test that used to assert mutual exclusion
now asserts the opposite, because staying out of the mesh is the property worth
protecting.

## The VAD gate

Silero finds the speech regions and only those reach the recogniser. That is
what makes an always-on lane affordable — a mostly-silent day costs seconds
instead of hours — and it is why the archive lane is worth keeping at all.

Every record carries `speech_seconds` against `audio_seconds`, so **silence is
measured rather than assumed**. "Nobody said anything in this hour" is a
finding with a number behind it, not a gap where a transcript should be.

## Using it

```
sinnix stt lanes                 # which audio lanes this host has, and which a pass takes
sinnix stt transcribe FILE...    # one or more files to JSON
sinnix stt lake [--lane N]       # transcribe whatever landed and has not been seen
sinnix stt diarize FILE          # who spoke when
sinnix stt models                # fetch or verify the model set
```

The hub answers the OpenAI audio API on `127.0.0.1:8090`, which is the same
interface and the same port whisper.cpp served. No client changed when the
engine did:

```
curl -F file=@clip.wav -F model=parakeet-tdt-0.6b-v3 \
     http://127.0.0.1:8090/v1/audio/transcriptions
```

It is socket-activated behind `stt-proxy`, and still is even without a GPU to
release: the encoder is 650 MB of resident RSS that a mostly-idle service has
no business holding. The idle window is 300 s rather than the GPU services'
30 s, because nothing scarce is being held and reloading the encoder between
the turns of one conversation would be the only real cost.

## Lanes

Discovered from disk, not hard-coded — the desktop capture root holds three
generations at once and only one is live:

| Lane | Path | In a default pass |
| --- | --- | --- |
| `phone` | `captures/phone/ambient` | yes |
| `voice` | `captures/phone/estate/outbox` | yes |
| `src-*` | `captures/audio/src-…` (microphones) | yes |
| `snk-*` | `captures/audio/snk-…` (what the machine played) | no |
| — | `captures/audio/{mic,sink-monitor}` | retired 2026-08-13 |
| — | `captures/audio/legacy` | retired 2026-05-21 |

Sinks are excluded by default deliberately. A source lane is a recording of a
room, which is what this program is about; a sink lane is everything the
machine *played*, so transcribing it by default would fill the corpus with the
scripts of every video watched. They remain available by name.

**Undecodable files are carried as findings, not errors.** 27 of 464 lake
chunks have no stream at all — recorders killed before their muxer wrote a
header — and a batch that raised on the first one would never reach the rest.
They are recorded with `undecodable: true` and a reason.

## The always-on speech lane

`sinnix-phone-receiver` (port 8940, tailnet only) accepts newline-delimited
JSON from the phone. A `speech` line carries base64 PCM, and three things
happen to it in an order that is the design:

1. **The audio is written to the lake first.** Raw audio can be re-transcribed
   by a better engine, re-diarized, or attributed to a speaker once enrollment
   is trustworthy. A transcript cannot be un-lost. If the later steps fail, the
   recording survives them.
2. **It is transcribed inline** through the hub, not by a later batch pass,
   because the point of this lane is that speaking reaches prime *now*.
3. **The transcript is written to the capture lane** as an envelope joinable
   with everything else the phone sends.

The phone's VAD decides what is speech and streams only that — on **any**
network, with no wifi or charging gate. Those gates belong to the bulk archive
drain, where the concern is metered data for gigabytes of audio; an utterance
is kilobytes and the whole point is that it works when you walk away.

## What this lane deliberately does not do

**It does not dispatch agents.** An always-on microphone that can drive agents
is an open command channel for anyone in the room, on a speakerphone, or on a
television — `sinnix-7oly`'s problem statement, and the operator's own framing:
a random person nearby suddenly saying something should not be treated as the
operator issuing a command.

The mechanism that would filter that is speaker conditioning, and the
distinction matters: this is a **noise filter, not an authenticator**. Voice is
not a strong authenticator and the estate can synthesise the operator's own
voice locally, so treating a voiceprint as authorisation would be theatre. The
question it answers is only *whether an utterance is a command at all*.

`scripts/sinnix-speaker-verify` exists (ECAPA-TDNN via speechbrain) and is
**verified functional but measured NOT discriminative**: a different-source
clip scored 0.991 against a same-speaker clip's 0.986. Raw cosine similarity on
ECAPA embeddings is known to be poorly calibrated without AS-norm/cohort score
normalisation. Until that is fixed and shown to separate on a held-out cohort,
the lane listens and records, and the phone's deliberate push-to-talk verb
remains the way to actually ask for something.

Shipping the channel ungated because the gate is nearly ready is how an estate
acquires a voice-activated foot-gun.

## Diarization

`sherpa-onnx-offline-speaker-diarization` — pyannote segmentation plus a
titanet speaker embedding, both ONNX, both CPU. It produces speaker *turns*
(`spk0`, `spk1`), not names.

Enrollment — "is this the operator?" — is deliberately kept separate rather
than fused into the transcript. The raw audio is retained, so identity can be
recomputed at any time, and a labelling mistake baked into a transcript would
be much harder to undo than one recomputed on demand.

## Models

~690 MB under `/realm/media/model/sherpa`, fetched by `sinnix stt models` and
verified on every service start. Weights are not source and do not belong in
the Nix store; the estate already keeps model files under `/realm/media/model`.

| Model | Size | Role |
| --- | --- | --- |
| `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` | 465 MB | recognition |
| `nemo_en_titanet_small.onnx` | 38 MB | speaker embedding |
| `sherpa-onnx-pyannote-segmentation-3-0` | 7 MB | speaker segmentation |
| `silero_vad.onnx` | 2 MB | voice activity |

An earlier attempt at Parakeet went through a NeMo pip venv and left 5.5 GB of
torch and CUDA wheels under `/realm/media/model/parakeet` with no model weights
in it and no service ever built. That is what the packaged route replaced, and
the venv is gone.

## Still open

- **Voxtral Transcribe 2** as a streaming engine (`sinnix-mke`) — the
  always-on lane currently sends discrete VAD regions rather than a continuous
  stream, which is enough for utterances and not for live dictation. llama.cpp
  has voxtral audio support and the existing `llama-cpp` service is the natural
  host.
- **Semantic end-of-turn** (LiveKit turn-detector, pipecat smart-turn v2) —
  needed before a conversation, as opposed to an utterance, is the unit.
- **AS-norm on the speaker verifier**, which is what gates the command channel.
- The desktop **ASR tee** (`%t/sinnix/audio/asr.pcm`, pointed at the Yeti) is
  live and still has no consumer — that is the socket a streaming engine would
  attach to.
