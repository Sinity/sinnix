"""Always-on PipeWire audio capture: every source, plus the sink monitor.

Shape of the lane:
  - One channel per live capture source, supervised dynamically as devices
    come and go (sources.py), minus a configured blacklist; plus the single
    `sink-monitor` channel that follows the default sink
    (segment.CHANNEL_PROFILES). There is no "the microphone" channel: a
    single-device channel silently records the wrong device the moment the
    device it picked is unplugged. Node/port/link attribution comes from a
    `pw-mon` topology stream (topology.py).
  - Opus IS the raw/archive tier (see segment.py's module docstring). There is
    no separate lossless intermediate.
  - Always-on, every channel, from first enablement. VAD is index-only and
    never a gate: the recorder unit has zero dependency on any VAD
    library/model/binary (indexer.py's torch/silero-vad imports are deferred
    into functions the recorder never calls). Explicit `pause` writes a gap
    record instead of stopping the recorder -- see pause.py's module docstring
    for why that is a load-bearing invariant, not a preference.
  - Low-latency dual-use via a raw-PCM SEQPACKET tee off whichever source
    is PipeWire's current default (tee.py), drop-on-slow-reader, so archive
    liveness never depends on a consumer being attached.
  - Silero VAD (pinned to v6, see indexer.py) for speech-span indexing, with
    the JSONL index written through the shared sinnix_capture.writer envelope
    format.

Out of scope for this package: bulk transcription runs on the shared STT hub
and consumes the speech spans + raw_ref pointers indexer.py emits; pyannote
diarization and a speaker-embedding registry are not implemented. Transcript
and diarization output belongs under /realm/data/derived/audio/ (regenerable,
borg-excluded), never under captures/.
"""
