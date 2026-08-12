"""Query surface over sidecar indexes: per-lane deltas since a timestamp.

Reads only the small ``{lane}-index.jsonl`` sidecar (never the payload
files), so enrichment consumers can poll every lane cheaply without
per-lane glue.
"""

from __future__ import annotations

import json
from pathlib import Path


def discover_lanes(capture_root: Path | str) -> list[str]:
    root = Path(capture_root)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def lane_delta(capture_root: Path | str, lane: str, since_ts: float = 0.0) -> dict:
    index_path = Path(capture_root) / lane / f"{lane}-index.jsonl"
    records_since = 0
    newest_ts: float | None = None
    gap_records = 0
    prev_seq: int | None = None

    if index_path.exists():
        with open(index_path) as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                entry = json.loads(raw_line)
                ts = entry["ts"]
                seq = entry["seq"]
                if newest_ts is None or ts > newest_ts:
                    newest_ts = ts
                if ts >= since_ts:
                    records_since += 1
                if prev_seq is not None and seq - prev_seq > 1:
                    gap_records += seq - prev_seq - 1
                prev_seq = seq

    return {
        "lane": lane,
        "records_since": records_since,
        "newest_ts": newest_ts,
        "gap_records": gap_records,
    }


def query(capture_root: Path | str, since_ts: float = 0.0, lanes: list[str] | None = None) -> list[dict]:
    lanes = lanes if lanes is not None else discover_lanes(capture_root)
    return [lane_delta(capture_root, lane, since_ts) for lane in lanes]
