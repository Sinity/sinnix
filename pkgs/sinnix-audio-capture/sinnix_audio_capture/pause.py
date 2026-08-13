"""`sinnix-audio-capture pause <duration>` -- explicit gap records.

The recorder keeps running; `pause` only writes an index annotation. That
follows from two non-negotiable invariants of this design:

  - "always-on, BOTH channels, from first enablement... the recorder unit
    must have ZERO dependency on any VAD library/model/binary" -- pause
    stopping the recorder would mean either (a) the pause CLI reaching into
    systemd to stop/start the templated recorder units, which is exactly
    the kind of external control-plane dependency the recorder is supposed
    to be free of, plus real races against in-flight hour segments, or
    (b) inventing a second, separate gating mechanism nobody asked for.
  - "holes in the archive must always be describable, never silent" --
    genuinely stopping still produces a hole; only the *description* would
    exist, not the audio. Keeping the recorder running and writing a gap
    record means the archive has no hole at all, and the index still
    carries the operator's stated reason for wanting that interval treated
    as intentionally uninteresting (e.g. excluded from future transcription
    passes) -- strictly more information for the same mechanism.

Gap records land in the same `audio-index` lane the VAD indexer writes to
(kind="gap" vs kind="speech-index"), so anything reading the index sees a
single merged timeline of speech spans and intentional gaps.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from .indexer import INDEX_LANE

_DURATION_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?P<unit>[smh]?)$")
_UNIT_SECONDS = {"s": 1.0, "m": 60.0, "h": 3600.0, "": 1.0}


def parse_duration(text: str) -> float:
    """ "30", "30s", "5m", "2h" -> seconds. Bare numbers are seconds."""
    match = _DURATION_RE.match(text.strip())
    if match is None:
        raise ValueError(
            f"invalid duration: {text!r} (expected e.g. '30s', '5m', '2h', or a bare number of seconds)"
        )
    return float(match.group("value")) * _UNIT_SECONDS[match.group("unit")]


def build_gap_payload(*, start_ts: float, end_ts: float, reason: str | None) -> dict:
    return {
        "kind": "gap",
        "start": start_ts,
        "end": end_ts,
        "reason": reason,
    }


def write_gap_record(
    *,
    capture_root: Path,
    duration_seconds: float,
    reason: str | None,
    now_fn=time.time,
    writer_factory=None,
) -> dict:
    from sinnix_capture.writer import CaptureWriter

    if writer_factory is None:
        writer_factory = lambda: CaptureWriter(capture_root, INDEX_LANE)  # noqa: E731

    start_ts = now_fn()
    end_ts = start_ts + duration_seconds
    payload = build_gap_payload(start_ts=start_ts, end_ts=end_ts, reason=reason)
    writer = writer_factory()
    return writer.write(payload)
