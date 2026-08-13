"""Always-on PipeWire audio capture: every source and every sink.

Shape of the lane:
  - One channel per live device -- capture sources directly, playback sinks
    through their monitor ports -- supervised dynamically as devices come
    and go (devices.py), minus a configured blacklist. There is no "the
    microphone" and no "the output" channel: a channel bound to a role
    silently records the wrong device the moment the desktop's default
    moves, which is how an unplugged mic became hours of a dead line-in and
    how playback through Bluetooth headphones went unrecorded.
    Node/port/link attribution comes from a `pw-mon` topology stream
    (topology.py).
  - Opus IS the raw/archive tier (see segment.py's module docstring). There is
    no separate lossless intermediate.
  - Always-on, every device, from first enablement. VAD is index-only and
    never a gate: the recorder unit has zero dependency on any VAD
    library/model/binary (indexer.py's torch/silero-vad imports are deferred
    into functions the recorder never calls). Explicit `pause` writes a gap
    record instead of stopping the recorder -- see pause.py's module docstring
    for why that is a load-bearing invariant, not a preference.
  - Low-latency dual-use via a raw-PCM SEQPACKET tee off ONE nominated
    capture source (tee.py), drop-on-slow-reader, so archive liveness never
    depends on a consumer being attached. Transcription targets one device
    by configuration; capture targets all of them. Keeping those separate
    is what stops the ASR choice from becoming a privileged "primary"
    channel.
  - Silero VAD (pinned to v6, see indexer.py) for speech-span indexing, with
    the JSONL index written through the shared sinnix_capture.writer envelope
    format.

Out of scope for this package: bulk transcription runs on the shared STT hub
and consumes the speech spans + raw_ref pointers indexer.py emits; pyannote
diarization and a speaker-embedding registry are not implemented. Transcript
and diarization output belongs under /realm/data/derived/audio/ (regenerable,
borg-excluded), never under captures/.
"""
