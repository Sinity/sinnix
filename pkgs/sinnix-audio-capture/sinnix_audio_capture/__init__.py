"""Always-on dual-channel PipeWire audio capture (sinnix-nm7).

Agreements kept vs. the bead's original sketch:
  - Silero VAD (now pinned to v6 -- see indexer.py) for speech-span indexing.
  - Bulk transcription via the shared sinnix-mke STT hub (Parakeet), not
    baked into this package -- indexer.py only produces speech spans +
    raw_ref pointers for a downstream transcription pass to consume.
  - pyannote nightly diarization and a speaker-embedding registry are later
    phases of the same bead, not implemented here.
  - JSONL index via the shared sinnix_capture.writer envelope format.

Departures (2026-08-12 design supersession, recorded on sinnix-nm7):
  - Two canonical channels only (`mic`, `sink-monitor` -- see
    segment.CHANNEL_PROFILES), not per-PipeWire-node capture. A `pw-mon`
    topology stream (topology.py) covers node/port/link attribution instead;
    a per-node "captureNodes" escalation hatch is deferred, not built here.
  - Opus IS the raw/archive tier (see segment.py's module docstring) -- no
    separate lossless intermediate.
  - Always-on, both channels, from first enablement. VAD is index-only and
    never a gate: the recorder unit has zero dependency on any VAD
    library/model/binary (indexer.py's torch/silero-vad imports are deferred
    into functions the recorder never calls). Explicit `pause` writes a gap
    record instead of stopping the recorder (see pause.py's module
    docstring for why that's the load-bearing invariant, not a preference).
  - Low-latency dual-use via a raw-PCM SEQPACKET tee off the mic channel
    (tee.py), drop-on-slow-reader, so archive liveness never depends on a
    consumer being attached.
  - Transcripts/diarization output is scoped to land under
    /realm/data/derived/audio/ (regenerable, borg-excluded), never under
    captures/ -- not yet implemented in this package (see above).

Legacy migration note: this package supersedes the older always-on capture
lane in `modules/features/desktop/audio-capture.nix` (the
`sinnix-audio-daemon` + `sinnix-asr-server` scripts: WebRTC-VAD utterance
segmentation gating a cloud-ASR upload). That module remains the live,
default-on capture path on sinnix-prime as of this change -- cutover
(disabling the legacy feature, wiring `sinnix.services.<name>` surfaces +
persistence for `record`/`topology`/`index`/`pause`, and retiring the two
legacy scripts per the no-alias rule) is NixOS-module-level work out of
scope for this Python-package implementation pass and is tracked on
sinnix-nm7, not duplicated here.
"""
