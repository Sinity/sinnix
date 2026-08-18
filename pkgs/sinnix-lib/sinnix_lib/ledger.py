"""JSONL ledgers and the sinnix receipt schema.

A ledger line's atomicity requirement is one line, not read-modify-write:
a single ``write(2)`` on an ``O_APPEND`` fd does not interleave for sane
line sizes, so appends need no lock. Nine-plus scripts each carried their
own version of this; the receipt shape (``run_id``/``operation_kind``/
``state``/``ts``) existed in at least three dialects (borg integrity
receipts, drill records, drain receipts) — this is the one schema new
emissions use.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any


def utc_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def append_jsonl(
    path: Path | str,
    record: Mapping[str, Any],
    *,
    mode: int = 0o644,
    fsync: bool = False,
) -> None:
    """Append *record* as one compact JSON line, creating parents.

    ``fsync=True`` forces the line to disk before returning, for lanes where
    losing an unflushed append to a crash is not acceptable (the capture
    writer fsyncs every record and index line for exactly this reason).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, mode)
    try:
        os.write(fd, line.encode("utf-8"))
        if fsync:
            os.fsync(fd)
    finally:
        os.close(fd)


def iter_jsonl(path: Path | str) -> Iterator[Any]:
    """Parsed records of a JSONL file; skips torn/blank lines silently
    (a producer killed mid-append leaves at most one torn tail line, and a
    reader that dies on it converts a one-line loss into a whole-ledger
    outage)."""
    p = Path(path)
    try:
        fh = p.open(encoding="utf-8")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def receipt(
    operation_kind: str,
    state: str,
    *,
    run_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """The sinnix receipt: {run_id, operation_kind, state, ts, **extra}.

    *state* is by convention one of running/completed/failed/skipped.
    ``run_id`` defaults to the systemd invocation id when present, so a
    receipt written by a unit is joinable against the journal for free.
    """
    return {
        "run_id": run_id
        or os.environ.get("INVOCATION_ID")
        or f"{operation_kind}-{int(time.time())}",
        "operation_kind": operation_kind,
        "state": state,
        "ts": utc_ts(),
        **extra,
    }
