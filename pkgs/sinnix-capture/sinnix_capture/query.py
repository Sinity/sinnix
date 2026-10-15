"""Query surface over sidecar indexes: per-lane deltas since a timestamp.

Reads only the small ``{lane}-index.jsonl`` sidecar (never the payload
files), so enrichment consumers can poll every lane cheaply without
per-lane glue.
"""

from __future__ import annotations

import json
from pathlib import Path
from stat import S_ISDIR

from sinnix_lib.layout import ACTIVITY_LANES, capture_lane_path


def _directory_present(path: Path) -> bool:
    try:
        return S_ISDIR(path.stat().st_mode)
    except FileNotFoundError:
        return False


def discover_lanes(capture_root: Path | str) -> list[str]:
    root = Path(capture_root)
    try:
        mode = root.stat().st_mode
    except FileNotFoundError:
        return []
    if not S_ISDIR(mode):
        raise NotADirectoryError(f"capture root is not a directory: {root}")
    # Known physical homes may be nested; do not expose medium containers as lanes.
    containers = {relative.split("/")[0] for relative in ACTIVITY_LANES.values()}
    known = {lane for lane in ACTIVITY_LANES if _directory_present(capture_lane_path(root, lane))}
    custom = {p.name for p in root.iterdir() if _directory_present(p) and p.name not in containers}
    return sorted(known | custom)


def lane_delta(capture_root: Path | str, lane: str, since_ts: float = 0.0) -> dict:
    index_path = capture_lane_path(capture_root, lane) / f"{lane}-index.jsonl"
    records_since = 0
    newest_ts: float | None = None
    gap_records = 0
    prev_seq: int | None = None

    try:
        handle = index_path.open("rb")
    except FileNotFoundError:
        handle = None
    if handle is not None:
        with handle:
            for line in handle:
                if not line.endswith(b"\n"):
                    # An interrupted append can leave only the last line
                    # incomplete. A terminated malformed line still raises.
                    break
                entry = json.loads(line)
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


def query(
    capture_root: Path | str, since_ts: float = 0.0, lanes: list[str] | None = None
) -> list[dict]:
    lanes = lanes if lanes is not None else discover_lanes(capture_root)
    return [lane_delta(capture_root, lane, since_ts) for lane in lanes]
