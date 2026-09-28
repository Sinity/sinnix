"""Shared writer every capture lane uses to append sinnix-capture-v1 records.

Layout under ``{capture_root}/{lane}/``:

- ``{lane}-{YYYYMMDD}.jsonl`` -- one daily-rotated file of full envelopes.
- ``{lane}-index.jsonl`` -- sidecar index, one small ``{ts, seq, file}``
  record per write, read by the query surface (query.py) so lane-delta
  queries never have to scan the (potentially large) payload files.
- ``{lane}.seq`` -- persisted monotonic sequence counter, guarded by
  ``{lane}.seq.lock`` so restarts don't reuse a seq number.
- ``{lane}-{YYYYMMDD}.jsonl.hw`` -- high-water sidecar of a daily file: one
  fixed-width ``HW_FORMAT`` line per record, holding the byte offset where
  that record ends and the largest ``ts`` of every record up to it. ``ts``
  is caller-supplied and need not be ordered, but the high water is, so a
  reader binary-searches it to skip a prefix that cannot hold its window.
  A daily file that predates its sidecar never gets one.
"""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

from sinnix_lib import ledger
from sinnix_lib.atomic import atomic_publish
from sinnix_lib.lock import flock

from .envelope import build_envelope

# Readers (the gateway's activity query) parse this exact width; keep in step.
HW_FORMAT = "{:020d} {:032.9f}\n"
HW_WIDTH = len(HW_FORMAT.format(0, 0.0))


def _last_high_water(sidecar: Path) -> tuple[int, float] | None:
    """Last complete checkpoint, dropping a torn trailing write."""
    try:
        size = sidecar.stat().st_size
    except FileNotFoundError:
        return None
    whole = size - size % HW_WIDTH
    if whole != size:
        os.truncate(sidecar, whole)
    if whole == 0:
        return None
    with sidecar.open("rb") as handle:
        handle.seek(whole - HW_WIDTH)
        offset, high = handle.read(HW_WIDTH).split()
    return int(offset), float(high)


def _max_ts(path: Path, start: int, end: int) -> float:
    """Largest ts among records in ``path[start:end]`` (an unindexed tail)."""
    high = float("-inf")
    with path.open("rb") as handle:
        handle.seek(start)
        for raw in handle.read(end - start).splitlines():
            try:
                ts = json.loads(raw).get("ts")
            except (ValueError, AttributeError):
                continue
            if isinstance(ts, (int, float)) and not isinstance(ts, bool):
                high = max(high, float(ts))
    return high


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
        self._append_lock_path = self.lane_dir / f"{lane}.append.lock"

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
        with flock(self._seq_lock_path):
            seq = self._read_seq() + 1
            # The counter governs cross-process sequence allocation, so its
            # replacement and directory entry are durable before releasing
            # the lock. Readers see either complete generation of the value.
            atomic_publish(self._seq_path, str(seq).encode(), fsync=True, mode=0o600)
            return seq

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
        self._append_with_high_water(record_path, envelope, ts)
        index_entry = {"ts": ts, "seq": seq, "file": record_path.name}
        ledger.append_jsonl(self._index_path, index_entry, fsync=True)
        return envelope

    def _append_with_high_water(self, path: Path, envelope: dict, ts: float) -> None:
        sidecar = path.with_name(path.name + ".hw")
        with flock(self._append_lock_path):
            try:
                before = path.stat().st_size
            except FileNotFoundError:
                before = 0
            last = _last_high_water(sidecar)
            if last is None and before:
                # The file predates its sidecar: an index starting here would
                # misstate the unindexed prefix, so this day stays unindexed.
                ledger.append_jsonl(path, envelope, fsync=True)
                return
            offset, high = last if last is not None else (0, float("-inf"))
            if offset < before:
                # A record landed without its checkpoint (a crash between the
                # two appends); fold its ts in before indexing past it.
                high = max(high, _max_ts(path, offset, before))
            ledger.append_jsonl(path, envelope, fsync=True)
            end = path.stat().st_size
            fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, HW_FORMAT.format(end, max(high, ts)).encode())
                os.fsync(fd)
            finally:
                os.close(fd)
