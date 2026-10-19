# Speech

Speech-to-text is **Parakeet TDT 0.6B v3** (int8 ONNX) through **sherpa-onnx**,
with **Silero VAD v6** in front and sherpa's pyannote diarizer beside it, all on
the CPU. `scripts/sinnix-stt` is the engine and CLI; `modules/services/stt.nix`
serves it. Whisper was removed (bead `sinnix-mke`): Parakeet handles Polish,
does not invent text over silence, and is fast enough (an hour of mostly quiet
audio in about ten seconds) that it needs no GPU and never waits behind the
local LLMs.

## Using it

```text
sinnix stt lanes                 # audio lanes on this host, and which a pass takes
sinnix stt transcribe FILE...    # files to JSON
sinnix stt recordings [--lane N] # transcribe new recordings in the capture lanes
sinnix stt diarize FILE          # who spoke when
sinnix stt models                # fetch or verify the models
```

The service speaks the OpenAI audio API on `127.0.0.1:8090`:

```bash
curl -F file=@clip.wav -F model=parakeet-tdt-0.6b-v3 \
     http://127.0.0.1:8090/v1/audio/transcriptions
```

It starts on the first connection and exits after 300 s idle, so the 650 MB
encoder is not held by an idle service. Browser requests (an `Origin` or
Fetch-Metadata header) are refused.

The VAD passes only speech to the recogniser, and every record carries
`speech_seconds` next to `audio_seconds`, so silence is measured, not
assumed. Files with no decodable stream are recorded as `undecodable: true`
with a reason instead of failing the pass.

## Lanes

Found on disk, not hard-coded:

| Lane    | Path                                             | In a default pass |
| ------- | ------------------------------------------------ | ----------------- |
| `phone` | `captures/phone/ambient`                         | yes               |
| `voice` | `captures/phone/outbox`                          | yes               |
| `src-*` | `captures/audio/src-…` (microphones)             | yes               |
| `snk-*` | `captures/audio/snk-…` (what the machine played) | no                |

Sink lanes are skipped by default because they hold whatever the machine
played (videos, calls); they can be named explicitly.

## The always-on speech lane

The phone's VAD streams speech segments to `sinnix-phone-dispatcher` (port 8940,
tailnet only) on any network. The dispatcher writes the audio to the capture
store first, then transcribes it through the hub, then writes the transcript as
a capture envelope, so a failed transcription never loses the recording. The
lane is on by default and restarts with the phone app.

It never dispatches agents: an always-on microphone would take commands from
anyone in the room or on a TV. Commands go through the phone's push-to-talk
action. A speaker-match filter could later decide whether an utterance is
meant as a command at all (a noise filter, not authentication); none exists
yet.

## Diarization

`sinnix stt diarize` produces speaker turns (`spk0`, `spk1`), not names. It
also reports whether the result is believable: the speaker count must be
supported by the amount of speech the VAD found (roughly three seconds per
voice). Without that check, a mostly silent chunk can come back as seventeen
"speakers".

## Review transcription

For recordings that need a careful transcript, `scripts/sinnix-stt-review`
sends the named files to ElevenLabs Scribe v2 with an explicit language
(`pol` by default), speaker diarization and word timestamps. This uploads the
audio and spends account credits.

```bash
agentctl job start sinnix transcribe_review -- \
  --api-key-file /path/to/private/elevenlabs-key \
  --output-dir /path/to/private/transcription-output recording.m4a
```

The output directory keeps the raw API responses, source hashes, settings,
`transcript.md`, and two review lists: words with log probability below -1,
and words lasting over two seconds (often stretched timestamps). These are
heuristics, not calibrated error rates. Rerunning the same command reuses
finished responses. Scribe was chosen because it supports Polish together with
word timestamps; Voxtral Transcribe 2 does not list Polish.

## Models

About 690 MB under `/realm/library/model/sherpa`, fetched and verified by
`sinnix stt models` and checked at every service start.

| Model                                        | Size   | Role                 |
| -------------------------------------------- | ------ | -------------------- |
| `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` | 465 MB | recognition          |
| `nemo_en_titanet_small.onnx`                 | 38 MB  | speaker embedding    |
| `sherpa-onnx-pyannote-segmentation-3-0`      | 7 MB   | speaker segmentation |
| `silero_vad.onnx`                            | 2 MB   | voice activity       |

## Open

- A streaming engine (Voxtral Transcribe 2 through llama.cpp) for live
  dictation; the phone lane sends discrete segments today (`sinnix-mke`).
- End-of-turn detection, needed before a conversation rather than an utterance
  can be the unit.
- The desktop ASR tee (`%t/sinnix/audio/asr.pcm`) is live but has no consumer
  yet; a streaming engine would attach there.
