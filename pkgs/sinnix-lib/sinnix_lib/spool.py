"""The spool: a durable inbox with exactly-once processing.

The shape sinnix kept rebuilding: producers drop files into a directory;
a consumer must process each exactly once, survive crashes mid-item, and
tolerate the same item arriving twice (a drain can legitimately redeliver).
Instances before this module: the phone outbox/intents (send_token ledger),
elicit's feedback spool, hub-feedback, the vacuity-judge queue, the
enrichment dump loop.

Design:
- Claim is rename into ``work/`` — atomic on one filesystem, so two
  consumers cannot claim the same item and a crashed consumer leaves its
  item visibly parked in ``work/`` rather than half-processed in place.
- Done is rename into ``done/`` (kept, not deleted: spool items are cheap
  and history answers questions; the owner may tier them later) or, for
  spools whose contract is delete-after-ack, removal by the callback's
  owner after its own durable ack.
- Duplicate suppression is by token: the caller derives a token from the
  item (filename, or a field inside it); processed tokens live in a JSONL
  ledger and a repeat is a no-op that still counts as success — the phone
  dispatcher's send_token contract, generalized.
- Failure parks the item in ``failed/`` with a sidecar ``.error`` file;
  retry is explicit (move back to the inbox), never automatic-unbounded.

No daemon here: the consumer is whoever calls :func:`drain` — a systemd
path unit's oneshot, a daemon's watcher thread, or a timer fallback.
"""

from __future__ import annotations

import os
import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .ledger import append_jsonl, iter_jsonl, utc_ts
from .lock import LockBusy, flock


@dataclass
class Spool:
    root: Path
    subdirs: tuple[str, ...] = ("work", "done", "failed")
    token_ledger_name: str = "processed-tokens.jsonl"
    seen: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        for sub in self.subdirs:
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self.seen = {
            rec["token"]
            for rec in iter_jsonl(self.root / self.token_ledger_name)
            if isinstance(rec, dict) and "token" in rec
        }

    # -- producer side ----------------------------------------------------
    def submit(self, name: str, data: bytes) -> Path:
        """Durably add an item: tmp-write then rename into the inbox."""
        final = self.root / name
        tmp = final.with_name(final.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, final)
        return final

    # -- consumer side ----------------------------------------------------
    def pending(self) -> Iterable[Path]:
        return sorted(
            p
            for p in self.root.iterdir()
            if p.is_file()
            and not p.name.endswith(".part")
            and p.name != self.token_ledger_name
            and not p.name.endswith(".lock")
        )

    def drain(
        self,
        process: Callable[[Path], None],
        *,
        token_for: Callable[[Path], str] = lambda p: p.name,
        keep_done: bool = True,
    ) -> dict[str, int]:
        """Process every pending item exactly once; returns counters.

        Single-drainer at a time (flock on the root); a concurrent drain
        returns immediately with everything counted as skipped_busy rather
        than blocking — the other drainer will get them.
        """
        counts = {"processed": 0, "duplicate": 0, "failed": 0, "skipped_busy": 0}
        try:
            ctx = flock(self.root / ".drain.lock", blocking=False)
            ctx.__enter__()
        except LockBusy:
            counts["skipped_busy"] = len(list(self.pending()))
            return counts
        try:
            for item in self.pending():
                token = token_for(item)
                if token in self.seen:
                    counts["duplicate"] += 1
                    self._finish(item, keep_done)
                    continue
                claimed = self.root / "work" / item.name
                try:
                    os.replace(item, claimed)
                except FileNotFoundError:
                    continue  # raced a producer replay; the survivor wins
                try:
                    process(claimed)
                except Exception:
                    failed = self.root / "failed" / item.name
                    os.replace(claimed, failed)
                    failed.with_name(failed.name + ".error").write_text(
                        traceback.format_exc(), encoding="utf-8"
                    )
                    counts["failed"] += 1
                    continue
                self._record(token)
                self._finish(claimed, keep_done)
                counts["processed"] += 1
        finally:
            ctx.__exit__(None, None, None)
        return counts

    def _record(self, token: str) -> None:
        append_jsonl(self.root / self.token_ledger_name, {"token": token, "ts": utc_ts()})
        self.seen.add(token)

    def _finish(self, item: Path, keep_done: bool) -> None:
        if keep_done:
            os.replace(item, self.root / "done" / item.name)
        else:
            item.unlink(missing_ok=True)
