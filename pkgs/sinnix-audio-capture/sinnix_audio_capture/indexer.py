"""Searchability index over the raw Opus archive -- Silero VAD v6, index-only.

Structural invariant (sinnix-nm7 supersession note, non-negotiable): this
module is imported and run *only* by the timer-driven
`sinnix-audio-index.service`, never by the recorder units. The recorder's
ExecStart chain has zero dependency on this module or on silero-vad/torch;
if VAD is broken or the model fails to load, the archive keeps recording
and only the index (searchability) degrades.

Each pass:
  1. Lists `*.opus` segments (skipping `*.opus.partial` -- still being
     written, see segment.py) under a channel's directory that are newer
     than `since_ts` (the timer's own lookback window).
  2. Decodes each to 16kHz mono PCM via ffmpeg (Silero VAD only supports
     8kHz/16kHz) -- this is a read-only decode for analysis, it never
     touches the raw Opus file.
  3. Runs Silero VAD's `get_speech_timestamps` to get speech spans in
     seconds relative to the segment start.
  4. Writes one `sinnix-capture-v1` envelope per segment to the
     `audio-index` lane via the shared sinnix_capture writer, with speech
     spans converted to absolute Unix timestamps (segment_start_ts +
     relative-seconds) plus a `raw_ref` pointing at the segment file --
     the index never replaces or duplicates the raw audio, only points at
     it (capture-lake convention).
"""

from __future__ import annotations

import calendar
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .segment import hour_bucket_start

INDEX_LANE = "audio-index"
VAD_SAMPLE_RATE = 16000


@dataclass(frozen=True)
class SpeechSpan:
    start: float
    end: float


def list_segments(channel_dir: Path, *, since_ts: float) -> list[Path]:
    """Real (non-`.partial`) segments modified at/after since_ts, oldest
    first -- so a crashed indexer resumes roughly where it left off."""
    if not channel_dir.is_dir():
        return []
    candidates = [
        p
        for p in channel_dir.glob("audio-*.opus")
        if p.is_file() and p.suffix == ".opus" and p.stat().st_mtime >= since_ts
    ]
    return sorted(candidates, key=lambda p: p.stat().st_mtime)


def segment_start_ts(path: Path) -> float:
    """Recover the segment's wall-clock start from its filename (see
    segment.segment_filename); falls back to hour_bucket_start(mtime) for
    anything that doesn't parse, so a foreign/renamed file doesn't crash
    the indexer pass."""
    stem = path.stem  # "audio-<channel>-<YYYYMMDDTHH0000Z>"
    stamp = stem.rsplit("-", 1)[-1]
    try:
        # The stamp is UTC wall time (segment.segment_filename formats it via
        # time.gmtime), so decode with calendar.timegm, not time.mktime
        # (which would reinterpret it as local time).
        tm = time.strptime(stamp, "%Y%m%dT%H0000Z")
        return float(calendar.timegm(tm))
    except ValueError:
        return hour_bucket_start(path.stat().st_mtime)


def decode_to_pcm16k_mono(
    ffmpeg_bin: str,
    opus_path: Path,
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> bytes:
    """Decode a segment to raw s16le mono 16kHz PCM for VAD analysis only."""
    result = run(
        [
            ffmpeg_bin,
            "-v",
            "error",
            "-i",
            str(opus_path),
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            str(VAD_SAMPLE_RATE),
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return result.stdout


def build_index_payload(
    *,
    channel: str,
    segment_path: Path,
    segment_start: float,
    speech_spans: list[SpeechSpan],
) -> dict:
    """Pure payload builder -- speech_spans is injected so this is testable
    without a live VAD model."""
    return {
        "kind": "speech-index",
        "channel": channel,
        "segment": segment_path.name,
        "segment_start": segment_start,
        "speech_spans": [
            {"start": segment_start + span.start, "end": segment_start + span.end}
            for span in speech_spans
        ],
    }


def _load_model():
    # Deferred: torch/torchaudio only get imported when a real index pass
    # runs, never at module import time (recorder units never import this
    # module at all; the indexer service does, but tests exercising
    # list_segments/build_index_payload/etc. never call this function).
    from silero_vad import load_silero_vad

    return load_silero_vad()


def _speech_spans_for_segment(model, pcm16_bytes: bytes) -> list[SpeechSpan]:
    import torch
    from silero_vad import get_speech_timestamps

    audio = (
        torch.frombuffer(bytearray(pcm16_bytes), dtype=torch.int16).float() / 32768.0
    )
    timestamps = get_speech_timestamps(
        audio, model, sampling_rate=VAD_SAMPLE_RATE, return_seconds=True
    )
    return [
        SpeechSpan(start=float(t["start"]), end=float(t["end"])) for t in timestamps
    ]


def run_index_pass(
    *,
    capture_root: Path,
    channels: tuple[str, ...] = ("mic", "sink-monitor"),
    since_ts: float,
    ffmpeg_bin: str = "ffmpeg",
    writer_factory=None,
) -> int:
    """Live entry point (`sinnix-audio-capture index`). Returns the number
    of segments indexed."""
    from sinnix_capture.writer import CaptureWriter

    if writer_factory is None:
        writer_factory = lambda: CaptureWriter(capture_root, INDEX_LANE)  # noqa: E731

    writer = writer_factory()
    model = _load_model()
    indexed = 0
    for channel in channels:
        channel_dir = Path(capture_root) / "audio" / channel
        for segment_path in list_segments(channel_dir, since_ts=since_ts):
            pcm = decode_to_pcm16k_mono(ffmpeg_bin, segment_path)
            spans = _speech_spans_for_segment(model, pcm)
            payload = build_index_payload(
                channel=channel,
                segment_path=segment_path,
                segment_start=segment_start_ts(segment_path),
                speech_spans=spans,
            )
            writer.write(payload, raw_ref=str(segment_path))
            indexed += 1
    return indexed
