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

    def _highest_indexed_seq(self) -> int:
        """Largest seq the sidecar index has actually seen.

        The recovery authority when the counter file is unreadable. Falling
        back to 0 instead would restart the sequence and hand out numbers
        already on disk, which is precisely what the counter exists to
        prevent -- a duplicate seq is indistinguishable from a replayed
        record downstream.
        """
        highest = 0
        try:
            with open(self._index_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        seq = int(json.loads(line)["seq"])
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        continue
                    highest = max(highest, seq)
        except FileNotFoundError:
            # No index yet: 0 is the correct starting point.
            return 0
        except OSError:
            # The index exists but cannot be read (permissions, EIO). Returning
            # 0 here would do exactly what this function exists to prevent:
            # restart the sequence over numbers already on disk. Fail instead.
            raise
        return highest

    def _read_seq(self) -> int:
        """Current counter, repaired from the index if it is unusable.

        The counter file can legitimately be found empty: a process killed
        between truncating and writing it (a systemd restart during
        activation, say) leaves a zero-byte file, and every subsequent write
        then died on int('') -- which bricked the lane, because
        Restart=on-failure turned it into a start-limit-hit that no longer
        starts at all.
        """
        try:
            text = self._seq_path.read_text().strip()
        except (OSError, ValueError):
            return self._highest_indexed_seq()
        if not text:
            return self._highest_indexed_seq()
        try:
            return int(text)
        except ValueError:
            return self._highest_indexed_seq()

    def _next_seq(self) -> int:
        with open(self._seq_lock_path, "a+") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            try:
                seq = self._read_seq() + 1
                # Written through a temp file and renamed: a rename is atomic,
                # so a reader (or a killed writer) never observes a truncated
                # counter, which is how this file went empty in the first place.
                tmp_path = self._seq_path.with_suffix(".seq.tmp")
                tmp_path.write_text(str(seq))
                os.replace(tmp_path, self._seq_path)
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
