"""One declared table of the reducer's persistence stores.

Five accreted shapes reduce to three writer contracts:

  * "atomic-doc" -- a whole-file overwrite, or a locked read-modify-write, via
    ``sinnix_lib.atomic_json``: no history, the latest write is the whole
    truth. The status snapshot (overwritten every ``refresh()``, decided to
    stay that way -- see ``reducer.Reducer.refresh``), the reducer's own
    sequence state, the auth token, and health.py's
    per-key confirm-2 state document all take this shape.
  * "ledger" -- append-only JSONL via ``sinnix_lib.ledger``, read back into an
    in-memory index folded once at start: the action receipts store (one line
    per receipt, replacing a dict rewritten whole on every action -- see
    ``actions.ActionService``) and health.py's transition ledger.
  * "spool" -- feedback.py's per-UTC-day annotation spool. It predates this
    table and deliberately keeps its own hand-written envelope (see
    ``feedback.py``'s module docstring): it is a stable contract external
    readers already parse off disk, not an internal ledger this table gets to
    reshape.

``StateLayer`` resolves the per-instance stores -- the runtime root, the state
directory, and the feedback directory are all CLI flags -- exactly once, in
``cli.py``'s ``main()``. health.py's two stores are process-wide constants
(``runtime_dir()``-anchored, no per-instance parameter), so they keep their
own accessors (``health.state_path``, ``health.ledger_path``) rather than
being duplicated here; ``StateLayer.stores()`` calls back into them so the
whole table can still be listed from one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Shape = Literal["atomic-doc", "ledger", "spool"]


@dataclass(frozen=True)
class Store:
    name: str
    path: Path
    shape: Shape
    writer: str


@dataclass(frozen=True)
class StateLayer:
    """The reducer-instance-parameterized stores, resolved once from the
    CLI's ``--runtime-dir``/``--state-dir``/``--feedback-dir`` flags."""

    snapshot_path: Path
    token_path: Path
    reducer_state_path: Path
    receipts_path: Path
    feedback_spool_dir: Path

    @property
    def receipts_ledger_path(self) -> Path:
        """The append-only replacement for ``receipts_path``'s dict-JSON.

        Derived, not configured: same directory, same stem, ``.jsonl``
        instead of ``.json``, so the legacy whole-file dict and its ledger
        replacement can never collide on one filename. ``receipts_path``
        itself is never written again once the ledger exists -- see
        ``actions.ActionService._migrate_legacy_receipts``.
        """
        return self.receipts_path.with_name(self.receipts_path.stem + ".jsonl")

    def stores(self) -> list[Store]:
        from . import health  # local: avoids a health<->state import cycle

        return [
            Store(
                "snapshot",
                self.snapshot_path,
                "atomic-doc",
                "reducer.Reducer.refresh",
            ),
            Store("token", self.token_path, "atomic-doc", "server.ensure_token"),
            Store(
                "reducer_state",
                self.reducer_state_path,
                "atomic-doc",
                "reducer.Reducer._save_sequence",
            ),
            Store(
                "action_receipts_legacy",
                self.receipts_path,
                "atomic-doc",
                "actions.ActionService (retired 2026-08-18; read-once at migration, "
                "never written again)",
            ),
            Store(
                "action_receipts",
                self.receipts_ledger_path,
                "ledger",
                "actions.ActionService.execute",
            ),
            Store(
                "health_state",
                health.state_path(),
                "atomic-doc",
                "health.Emitter.emit",
            ),
            Store(
                "health_ledger",
                health.ledger_path(),
                "ledger",
                "health.Emitter.emit",
            ),
            Store(
                "feedback_spool",
                self.feedback_spool_dir,
                "spool",
                "feedback.FeedbackSpool.append",
            ),
        ]

    @classmethod
    def build(
        cls, *, runtime_root: Path, state_dir: Path, feedback_dir: Path
    ) -> "StateLayer":
        return cls(
            snapshot_path=runtime_root / "status.json",
            token_path=runtime_root / "ops.token",
            reducer_state_path=state_dir / "reducer.json",
            receipts_path=state_dir / "action-receipts.json",
            feedback_spool_dir=feedback_dir,
        )
