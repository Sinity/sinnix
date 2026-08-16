"""Searchability index over the raw Opus archive -- Silero VAD v6, index-only.

Structural invariant, non-negotiable: this
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

Each envelope also carries how much audio the segment actually contained.
That number is free here -- step 2 already decodes the whole segment, so the
sample count is in hand and was previously thrown away -- and it is the one
measurement that would have caught sinnix-500c. That bug collapsed every
hourly segment to ~37.5s of real audio for days while the units stayed
active, the files kept appearing on schedule, and the freshness budget stayed
satisfied; nothing in the estate compared a segment's *content* against the
wall-clock window it covered, so nothing alarmed. Recording `decoded_seconds`
and `coverage` per segment is what makes that class of silent shortfall
visible to a consumer at all.
"""

from __future__ import annotations

import calendar
import json
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .segment import hour_bucket_start

INDEX_LANE = "audio-index"
VAD_SAMPLE_RATE = 16000

#: s16le mono -- two bytes per sample.
_BYTES_PER_SAMPLE = 2

#: A mid-hour restart writes `...-p2-<stamp>.opus`. The stamp is still the
#: hour bucket, so such a file's real open time is unknown from its name.
_PART_SUFFIX_RE = re.compile(r"-p\d+-\d{8}T\d{6}Z\.opus$")


@dataclass(frozen=True)
class SpeechSpan:
    start: float
    end: float


def discover_channels(capture_root: Path) -> list[str]:
    """Channel directories under `<capture_root>/audio/` worth indexing.

    Per-device channels are created at runtime as devices appear, so the
    set cannot be a fixed list. Matching is restricted to the shapes this
    package writes -- `src-*` and `snk-*`, plus `mic` and `sink-monitor`
    from before capture went per-device -- so that neighbouring
    directories in the lake (`legacy/`, `archive/`, `raw/`) are never
    walked.
    """
    audio_dir = Path(capture_root) / "audio"
    if not audio_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in audio_dir.iterdir()
        if p.is_dir()
        and (p.name in ("mic", "sink-monitor") or p.name.startswith(("src-", "snk-")))
    )


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


def decoded_seconds_from_pcm(pcm: bytes) -> float:
    """How much audio the segment actually held, from the decode step's own output."""
    return len(pcm) / _BYTES_PER_SAMPLE / VAD_SAMPLE_RATE


def observed_span_seconds(segment_path: Path, segment_start: float) -> float | None:
    """The wall-clock window a closed segment covered, or None when unknowable.

    A segment's mtime is when its muxer closed, so `mtime - start` is the
    window it was open for -- the honest denominator for coverage, and one
    that stays correct for the final segment of a lane as well as full hours.

    None for a `-pN` part file: its stamp is the hour bucket rather than the
    moment the recorder restarted, so the span would be overstated and the
    coverage would read as a shortfall that never happened. Reporting nothing
    beats reporting a number that is wrong in the alarming direction.
    """
    if _PART_SUFFIX_RE.search(segment_path.name):
        return None
    try:
        span = segment_path.stat().st_mtime - segment_start
    except OSError:
        return None
    return span if span > 0 else None


def build_index_payload(
    *,
    channel: str,
    segment_path: Path,
    segment_start: float,
    speech_spans: list[SpeechSpan],
    decoded_seconds: float | None = None,
    span_seconds: float | None = None,
) -> dict:
    """Pure payload builder -- speech_spans is injected so this is testable
    without a live VAD model."""
    payload = {
        "kind": "speech-index",
        "channel": channel,
        "segment": segment_path.name,
        "segment_start": segment_start,
        "speech_spans": [
            {"start": segment_start + span.start, "end": segment_start + span.end}
            for span in speech_spans
        ],
    }
    if decoded_seconds is not None:
        payload["decoded_seconds"] = round(decoded_seconds, 1)
        # Coverage only when there is a defensible denominator. An absent
        # field says "not measured"; a fabricated one would say "measured
        # and fine", which is the failure mode this whole field exists for.
        if span_seconds:
            payload["span_seconds"] = round(span_seconds, 1)
            payload["coverage"] = round(decoded_seconds / span_seconds, 4)
    return payload


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


def already_indexed_refs(capture_root: Path, *, since_ts: float) -> set[str]:
    """Segment paths this lane has already written an envelope for.

    The lookback window is NOT a de-duplication mechanism, and treating it as
    one is an arithmetic trap: the timer fires hourly while the default
    lookback is 26 hours (deliberately, so a missed run still catches up), so
    every pass re-decoded and re-VADed the same ~26 hours of audio. On
    2026-08-16 that produced 4481 records covering 431 distinct segments --
    roughly ten duplicates each -- and a pass took ~66 minutes, so the next
    hourly trigger arrived before the previous one finished and the service
    sat permanently `activating`, burning a core on work it had already done
    and holding up home-manager activation behind it.

    Idempotence belongs here rather than in the window: with it, the 26h
    lookback goes back to meaning what it says (catch up after a missed run)
    and costs a directory scan instead of a re-decode.

    Only the lane files that can overlap the window are read, so this stays
    cheap as the lane grows.
    """
    lane_dir = Path(capture_root) / INDEX_LANE
    if not lane_dir.is_dir():
        return set()
    # One day of slack on each side: segments are bucketed by their own start
    # hour in UTC, and a pass near a day boundary writes into the neighbouring
    # file.
    first_day = time.gmtime(since_ts - 86400)
    days = set()
    day = calendar.timegm(first_day)
    now = time.time() + 86400
    while day <= now:
        days.add(time.strftime("%Y%m%d", time.gmtime(day)))
        day += 86400

    refs: set[str] = set()
    for name in sorted(days):
        path = lane_dir / f"{INDEX_LANE}-{name}.jsonl"
        try:
            with open(path) as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ref = json.loads(line).get("raw_ref")
                    except json.JSONDecodeError:
                        # A torn final line from a killed writer is not a
                        # reason to re-index the whole window.
                        continue
                    if ref:
                        refs.add(ref)
        except FileNotFoundError:
            continue
    return refs


def run_index_pass(
    *,
    capture_root: Path,
    channels: tuple[str, ...] | None = None,
    since_ts: float,
    ffmpeg_bin: str = "ffmpeg",
    writer_factory=None,
) -> int:
    """Live entry point (`sinnix-audio-capture index`). Returns the number
    of segments indexed. `channels=None` indexes every channel directory
    currently present."""
    from sinnix_capture.writer import CaptureWriter

    if writer_factory is None:
        writer_factory = lambda: CaptureWriter(capture_root, INDEX_LANE)  # noqa: E731

    if channels is None:
        channels = tuple(discover_channels(capture_root))
    seen = already_indexed_refs(Path(capture_root), since_ts=since_ts)
    writer = writer_factory()
    model = _load_model()
    indexed = 0
    for channel in channels:
        channel_dir = Path(capture_root) / "audio" / channel
        for segment_path in list_segments(channel_dir, since_ts=since_ts):
            # raw_ref is written as str(segment_path) below; compare on the
            # same string so a pass never re-decodes what it already recorded.
            if str(segment_path) in seen:
                continue
            pcm = decode_to_pcm16k_mono(ffmpeg_bin, segment_path)
            spans = _speech_spans_for_segment(model, pcm)
            segment_start = segment_start_ts(segment_path)
            payload = build_index_payload(
                channel=channel,
                segment_path=segment_path,
                segment_start=segment_start,
                speech_spans=spans,
                decoded_seconds=decoded_seconds_from_pcm(pcm),
                span_seconds=observed_span_seconds(segment_path, segment_start),
            )
            writer.write(payload, raw_ref=str(segment_path))
            indexed += 1
    return indexed
