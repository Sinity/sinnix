"""Append-only comparisons + items store, one directory per ranking domain.

Adapted from an earlier ranker store (append-only comparisons.jsonl with
tombstone deletes) and generalized: items are opaque {id, label, meta} instead
of Stash scenes, and comparisons carry the doc's generic schema (kind, set,
winner, weight, context) instead of ranker-4wise's user4/pair split.

Comparisons are raw behavioral capture data (estate no-retention-limits
doctrine) -- never pruned, only tombstoned by an explicit delete record so
undo/audit stays possible. Derived fits belong elsewhere (a separate
directory), never mixed into this file, so a full refit from raw comparisons
is always reproducible.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sinnix_lib.ledger import utc_ts

VALID_KINDS = {"pair", "choice-set", "skip", "incomparable"}


@dataclass
class LogReplay:
    """An append-only judgment log, replayed.

    `live` is what a fit may use. `seen_ids` is every record id the file has
    ever carried, tombstoned ones included, and is what a drain must dedup
    against: a record the operator undid is still one this log has seen, and
    deduping against `live` re-imports it on every drain.
    """

    live: list[dict] = field(default_factory=list)
    seen_ids: set[str] = field(default_factory=set)
    tombstoned: set[str] = field(default_factory=set)


def read_log(path: str | Path) -> LogReplay:
    path = Path(path)
    rows: list[dict] = []
    replay = LogReplay()
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if "delete" in rec:
                replay.tombstoned.add(rec["delete"])
            else:
                rows.append(rec)
                replay.seen_ids.add(rec.get("id"))
    replay.live = [r for r in rows if r.get("id") not in replay.tombstoned]
    return replay


def append_log(path: str | Path, record: dict) -> str:
    """One record appended, with the id and timestamp every log entry carries."""
    path = Path(path)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("at", utc_ts())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record["id"]


@dataclass
class Comparison:
    id: str
    at: str
    kind: str
    set: list[str]
    winner: str | None = None
    weight: float = 1.0
    context: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Comparison":
        return cls(
            id=d["id"],
            at=d["at"],
            kind=d["kind"],
            set=[str(x) for x in d["set"]],
            winner=(str(d["winner"]) if d.get("winner") is not None else None),
            weight=float(d.get("weight", 1.0)),
            context=d.get("context"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "at": self.at,
            "kind": self.kind,
            "set": self.set,
            "winner": self.winner,
            "weight": self.weight,
            "context": self.context,
        }


@dataclass
class Item:
    id: str
    label: str
    meta: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(
            id=str(d["id"]),
            label=d.get("label", str(d["id"])),
            meta=d.get("meta", {}) or {},
        )

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "meta": self.meta}


class Store:
    """One domain's comparisons.jsonl (append-only + tombstones) + items.jsonl
    (append-only registry, last write per id wins on replay)."""

    def __init__(self, domain_dir: str | Path):
        self.domain_dir = Path(domain_dir)
        self.comparisons_path = self.domain_dir / "comparisons.jsonl"
        self.items_path = self.domain_dir / "items.jsonl"

    # -- items -------------------------------------------------------------
    def load_items(self) -> dict[str, Item]:
        items: dict[str, Item] = {}
        if self.items_path.exists():
            for line in self.items_path.read_text().splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                items[str(rec["id"])] = Item.from_dict(rec)
        return items

    def add_items(self, items: list[Item]) -> int:
        if not items:
            return 0
        self.domain_dir.mkdir(parents=True, exist_ok=True)
        with self.items_path.open("a") as f:
            for it in items:
                f.write(json.dumps(it.to_dict(), sort_keys=True) + "\n")
        return len(items)

    # -- comparisons ---------------------------------------------------------
    def load_comparisons(self) -> list[Comparison]:
        return [
            Comparison.from_dict(rec) for rec in read_log(self.comparisons_path).live
        ]

    def _append_raw(self, record: dict) -> str:
        return append_log(self.comparisons_path, record)

    def record_comparison(
        self,
        set_ids: list[str],
        winner: str | None,
        kind: str = "pair",
        weight: float = 1.0,
        context: str | None = None,
    ) -> str:
        if kind not in VALID_KINDS:
            raise ValueError(f"unknown comparison kind: {kind!r}")
        return self._append_raw(
            {
                "kind": kind,
                "set": [str(x) for x in set_ids],
                "winner": (str(winner) if winner is not None else None),
                "weight": weight,
                "context": context,
            }
        )

    def undo(self, comparison_id: str) -> None:
        self._append_raw({"delete": comparison_id})
