"""Shared writer every capture lane uses to append sinnix-capture-v1 records.

Layout under ``{capture_root}/{lane}/``:

- ``{lane}-{YYYYMMDD}.jsonl`` -- one daily-rotated file of full envelopes.
- ``{lane}-index.jsonl`` -- sidecar index, one small ``{ts, seq, file}``
  record per write, read by the query surface (query.py) so lane-delta
  queries never have to scan the (potentially large) payload files.
- ``{lane}.seq`` -- persisted monotonic sequence counter, guarded by
  ``{lane}.seq.lock`` so restarts don't reuse a seq number. Its first write
  publishes the name durably; later reservations append and sync one line.
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
        """Last complete counter line, or retained evidence if unavailable."""
        try:
            with self._seq_path.open("rb") as handle:
                end = handle.seek(0, 2)
                if not end:
                    return self._highest_retained_seq()
                if self._byte_at(handle, end - 1) == b"\n":
                    end -= 1
                else:
                    # Old counters have one integer without a newline.
                    handle.seek(0)
                    prefix = handle.readline()
                    if b"\n" not in prefix:
                        try:
                            return int(prefix)
                        except ValueError:
                            pass
                    while end and self._byte_at(handle, end - 1) != b"\n":
                        end -= 1
                    if not end:
                        return self._highest_retained_seq()
                    end -= 1
                start = end
                while start and self._byte_at(handle, start - 1) != b"\n":
                    start -= 1
                handle.seek(start)
                return int(handle.read(end - start))
        except FileNotFoundError:
            return self._highest_retained_seq()
        except ValueError:
            return self._highest_retained_seq()

    def _highest_retained_seq(self) -> int:
        highest = self._highest_indexed_seq()
        for path in self.lane_dir.glob(f"{self.lane}-[0-9]*.jsonl"):
            for record in self._payload_records(path):
                highest = max(highest, int(record["seq"]))
        return highest

    @staticmethod
    def _payload_records(path: Path):
        with path.open("rb") as handle:
            for line in handle:
                if not line.endswith(b"\n"):
                    break
                yield json.loads(line)

    def _next_seq(self) -> int:
        seq = self._read_seq() + 1
        try:
            with self._seq_path.open("rb") as handle:
                end = handle.seek(0, 2)
                legacy = not end or self._byte_at(handle, end - 1) != b"\n"
        except FileNotFoundError:
            legacy = True
        if legacy:
            # First publication or conversion of a single-number counter.
            atomic_publish(self._seq_path, f"{seq}\n".encode(), fsync=True, mode=0o600)
        else:
            # The counter name is already durable. One append sync reserves
            # the number before payload work; a later failure leaves a gap.
            fd = os.open(self._seq_path, os.O_WRONLY | os.O_APPEND)
            try:
                data = f"{seq}\n".encode()
                offset = 0
                while offset < len(data):
                    written = os.write(fd, data[offset:])
                    if written <= 0:
                        raise OSError("sequence append wrote no bytes")
                    offset += written
                os.fsync(fd)
            finally:
                os.close(fd)
        return seq

    def _last_indexed_seq(self) -> int:
        """Read the final complete index entry without scanning the sidecar."""
        try:
            with self._index_path.open("rb") as handle:
                end = handle.seek(0, 2)
                while end and self._byte_at(handle, end - 1) != b"\n":
                    end -= 1
                if not end:
                    return 0
                start = end - 1
                while start and self._byte_at(handle, start - 1) != b"\n":
                    start -= 1
                handle.seek(start)
                return int(json.loads(handle.read(end - start))["seq"])
        except FileNotFoundError:
            return 0

    @staticmethod
    def _byte_at(handle, offset: int) -> bytes:
        handle.seek(offset)
        return handle.read(1)

    def _recover_unindexed(self) -> None:
        """Publish retained payloads left by an interrupted index append."""
        counter = self._read_seq()
        last = self._last_indexed_seq()
        if last >= counter:
            return
        missing = []
        for path in sorted(self.lane_dir.glob(f"{self.lane}-[0-9]*.jsonl")):
            for record in self._payload_records(path):
                seq = record["seq"]
                if last < seq <= counter:
                    missing.append(
                        (seq, {"ts": record["ts"], "seq": seq, "file": path.name})
                    )
        for _, entry in sorted(missing):
            ledger.append_jsonl(self._index_path, entry, fsync=True)

    def _record_path(self, ts: float) -> Path:
        day = time.strftime("%Y%m%d", time.gmtime(ts))
        return self.lane_dir / f"{self.lane}-{day}.jsonl"

    def write(
        self, payload: dict, raw_ref: str | None = None, ts: float | None = None
    ) -> dict:
        ts = time.time() if ts is None else ts
        with flock(self._seq_lock_path):
            self._recover_unindexed()
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
            ledger.append_jsonl(record_path, envelope, fsync=True)
            index_entry = {"ts": ts, "seq": seq, "file": record_path.name}
            ledger.append_jsonl(self._index_path, index_entry, fsync=True)
            return envelope
