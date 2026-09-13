from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def source_revision(value: Any) -> str:
    """Return a stable revision for an owner observation.

    The gateway does not assign semantic revisions to owners. When an owner
    gives us no revision, this digest identifies exactly the bounded value we
    observed and is marked as an observation revision in the context output.
    """

    return hashlib.sha256(_canonical(value)).hexdigest()


class ContextSnapshotStore:
    """Read historical context snapshots without rewriting or evicting them."""

    def __init__(self, state_dir: Path, principal: str) -> None:
        self.root = state_dir / "contexts" / principal

    @staticmethod
    def _snapshot_id(snapshot: Mapping[str, Any]) -> str:
        body = {key: value for key, value in snapshot.items() if key != "snapshot_ref"}
        components = body.get("components")
        if isinstance(components, list):
            body["components"] = [
                (
                    {**component, "snapshot_ref": "pending"}
                    if isinstance(component, Mapping)
                    else component
                )
                for component in components
            ]
        return source_revision(body)

    def get(self, snapshot_id: str) -> dict[str, Any]:
        if len(snapshot_id) != 64 or any(
            char not in "0123456789abcdef" for char in snapshot_id
        ):
            raise KeyError(snapshot_id)
        path = self.root / f"{snapshot_id}.json"
        try:
            snapshot = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise KeyError(snapshot_id) from exc
        if not isinstance(snapshot, dict) or self._snapshot_id(snapshot) != snapshot_id:
            raise KeyError(snapshot_id)
        return snapshot
