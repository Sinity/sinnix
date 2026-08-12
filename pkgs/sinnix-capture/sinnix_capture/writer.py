"""Shared writer every capture lane uses to append sinnix-capture-v1 records.

Layout under ``{capture_root}/{lane}/``:

- ``{lane}-{YYYYMMDD}.jsonl`` -- one daily-rotated file of full envelopes.
- ``{lane}-index.jsonl`` -- sidecar index, one small ``{ts, seq, file}``
  record per write, read by the query surface (query.py) so lane-delta
  queries never have to scan the (potentially large) payload files.
- ``{lane}.seq`` -- persisted monotonic sequence counter, guarded by
  ``{lane}.seq.lock`` so restarts don't reuse a seq number.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import time
from pathlib import Path

from .envelope import build_envelope


def _atomic_append(path: Path, line: str) -> None:
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class CaptureWriter:
    def __init__(
        self, capture_root: Path | str, lane: str, host: str | None = None
    ) -> None:
        self.lane = lane
        self.host = host or socket.gethostname()
        self.lane_dir = Path(capture_root) / lane
        self.lane_dir.mkdir(parents=True, exist_ok=True)
        self._seq_path = self.lane_dir / f"{lane}.seq"
        self._seq_lock_path = self.lane_dir / f"{lane}.seq.lock"
        self._index_path = self.lane_dir / f"{lane}-index.jsonl"

    def _next_seq(self) -> int:
        with open(self._seq_lock_path, "a+") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            try:
                current = (
                    int(self._seq_path.read_text().strip())
                    if self._seq_path.exists()
                    else 0
                )
                seq = current + 1
                self._seq_path.write_text(str(seq))
                return seq
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)

    def _record_path(self, ts: float) -> Path:
        day = time.strftime("%Y%m%d", time.gmtime(ts))
        return self.lane_dir / f"{self.lane}-{day}.jsonl"

    def write(
        self, payload: dict, raw_ref: str | None = None, ts: float | None = None
    ) -> dict:
        ts = time.time() if ts is None else ts
        seq = self._next_seq()
        envelope = build_envelope(
            lane=self.lane,
            ts=ts,
            host=self.host,
            seq=seq,
            payload=payload,
            raw_ref=raw_ref,
        )
        record_path = self._record_path(ts)
        _atomic_append(record_path, json.dumps(envelope, sort_keys=True) + "\n")
        index_entry = {"ts": ts, "seq": seq, "file": record_path.name}
        _atomic_append(self._index_path, json.dumps(index_entry, sort_keys=True) + "\n")
        return envelope
