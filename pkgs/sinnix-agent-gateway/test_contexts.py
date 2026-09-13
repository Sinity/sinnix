"""Historical context integrity remains supported after owner composition migration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sinnix_agent_gateway.contexts import ContextSnapshotStore


def historical_context() -> dict:
    value = {
        "schema": "sinnix.gateway-context.v1",
        "intent": "project.orientation",
        "target_ref": "sinnix://projects/fixture",
        "components": [
            {
                "name": "project",
                "status": "available",
                "data": {"head": "a"},
                "source_revision": "a",
                "snapshot_ref": "pending",
            }
        ],
        "component_plan": [],
        "total_budget_bytes": 48000,
    }
    reference = "sinnix://contexts/" + ContextSnapshotStore._snapshot_id(value)
    value["snapshot_ref"] = reference
    value["components"][0]["snapshot_ref"] = reference
    return value


def test_context_snapshot_survives_store_recreation_and_rejects_tampering(
    tmp_path: Path,
):
    snapshot = historical_context()
    snapshot_id = snapshot["snapshot_ref"].rsplit("/", 1)[1]
    path = tmp_path / "contexts" / "observer" / f"{snapshot_id}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(snapshot, separators=(",", ":")))
    assert ContextSnapshotStore(tmp_path, "observer").get(snapshot_id) == snapshot
    path.write_text(path.read_text().replace('"head":"a"', '"head":"b"'))
    with pytest.raises(KeyError):
        ContextSnapshotStore(tmp_path, "observer").get(snapshot_id)
