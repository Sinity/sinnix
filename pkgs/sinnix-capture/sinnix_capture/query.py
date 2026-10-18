"""Query surface over sidecar indexes: per-lane deltas since a timestamp.

Reads only the small ``{lane}-index.jsonl`` sidecar (never the payload
files), so enrichment consumers can poll every lane cheaply without
per-lane glue. With no complete index rows, nonempty retained payload files
make the query fail rather than report a measured zero. This check reads only
file metadata; payload contents remain untouched.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from sinnix_lib.layout import ACTIVITY_LANES, capture_lane_path


def _directory_present(path: Path, *, declared: bool = False) -> bool:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        if declared:
            try:
                path.lstat()
            except FileNotFoundError:
                return False
            # A declared entrance exists but its target cannot be resolved.
            raise
        return False
    if declared and not S_ISDIR(mode):
        raise NotADirectoryError(f"declared capture source is not a directory: {path}")
    return S_ISDIR(mode)


def discover_lanes(capture_root: Path | str) -> list[str]:
    root = Path(capture_root)
    if not _directory_present(root, declared=True):
        return []
    # Known physical homes may be nested; do not expose medium containers as lanes.
    containers = {relative.split("/")[0] for relative in ACTIVITY_LANES.values()}
    known = {
        lane for lane in ACTIVITY_LANES
        if _directory_present(capture_lane_path(root, lane), declared=True)
    }
    custom = {p.name for p in root.iterdir() if _directory_present(p) and p.name not in containers}
    return sorted(known | custom)


def _has_retained_payload(lane_dir: Path, lane: str) -> bool:
    try:
        entries = os.scandir(lane_dir)
    except FileNotFoundError:
        return False
    with entries:
        for entry in entries:
            path = Path(entry.path)
            if not path.match(f"{lane}-[0-9]*.jsonl"):
                continue
            metadata = entry.stat()
            if not S_ISREG(metadata.st_mode):
                raise ValueError(f"capture payload is not a regular file: {path}")
            if metadata.st_size:
                return True
    return False


def _valid_timestamp(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def lane_delta(capture_root: Path | str, lane: str, since_ts: float = 0.0) -> dict:
    if not _valid_timestamp(since_ts):
        raise ValueError("capture query since timestamp must be finite and numeric")
    index_path = capture_lane_path(capture_root, lane) / f"{lane}-index.jsonl"
    records_since = 0
    newest_ts: float | None = None
    gap_records = 0
    prev_seq: int | None = None

    try:
        fd = os.open(index_path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        # An absent lane/index is legitimate. An existing broken entrance is
        # unavailable, and must not become a measured zero.
        _directory_present(Path(capture_root), declared=True)
        _directory_present(index_path.parent, declared=True)
        try:
            index_path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise
        handle = None
    else:
        try:
            if not S_ISREG(os.fstat(fd).st_mode):
                raise ValueError(f"capture index is not a regular file: {index_path}")
            handle = os.fdopen(fd, "rb")
        except BaseException:
            os.close(fd)
            raise
    if handle is not None:
        with handle:
            for line in handle:
                if not line.endswith(b"\n"):
                    # An interrupted append can leave only the last line
                    # incomplete. A terminated malformed line still raises.
                    break
                entry = json.loads(line)
                if not isinstance(entry, dict) or not {"ts", "seq"} <= entry.keys():
                    raise ValueError(f"capture index record lacks timestamp/sequence: {index_path}")
                ts = entry["ts"]
                seq = entry["seq"]
                if not _valid_timestamp(ts):
                    raise ValueError(f"capture index timestamp must be finite and numeric: {index_path}")
                if type(seq) is not int or seq < 1 or (prev_seq is not None and seq <= prev_seq):
                    raise ValueError(f"capture index sequences must be positive and strictly increasing: {index_path}")
                if newest_ts is None or ts > newest_ts:
                    newest_ts = ts
                if ts >= since_ts:
                    records_since += 1
                if prev_seq is not None and seq - prev_seq > 1:
                    gap_records += seq - prev_seq - 1
                prev_seq = seq

    if newest_ts is None and _has_retained_payload(index_path.parent, lane):
        raise ValueError(f"capture index has no complete records for retained payloads: {index_path}")

    return {
        "lane": lane,
        "records_since": records_since,
        "newest_ts": newest_ts,
        "gap_records": gap_records,
    }


def query(
    capture_root: Path | str, since_ts: float = 0.0, lanes: list[str] | None = None
) -> list[dict]:
    if not _valid_timestamp(since_ts):
        raise ValueError("capture query since timestamp must be finite and numeric")
    lanes = lanes if lanes is not None else discover_lanes(capture_root)
    return [lane_delta(capture_root, lane, since_ts) for lane in lanes]
