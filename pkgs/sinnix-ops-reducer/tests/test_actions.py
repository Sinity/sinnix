from __future__ import annotations

import json
from pathlib import Path

import pytest

from sinnix_ops_reducer.actions import ActionError, ActionService, validate_request
from sinnix_ops_reducer.reducer import Reducer


def inventory(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "sinnix-runtime-inventory-v1",
                "surfaces": {
                    "safe": {
                        "unit": "safe.service",
                        "manager": "user",
                "observe": {"restartable": True},
                        "effectiveResources": {"CPUWeight": 5},
                    },
                    "fixed": {
                        "unit": "fixed.service",
                        "manager": "user",
                        "observe": {"restartable": False},
                    },
                },
            }
        )
    )


def request(
    action: str, target: dict[str, str], revision: int = 1, key: str = "k1"
) -> dict:
    return {
        "action": action,
        "target": target,
        "expected_revision": revision,
        "idempotency_key": key,
        "operator_reason": "test fixture",
        "parameters": {},
    }


def test_action_fixtures_are_attested_and_idempotent_across_restart(
    tmp_path: Path,
) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    state = {
        "jobs": [
            {
                "job_id": "job-1",
                "schema_version": 3,
                "worktree": "/realm/worktrees/job-1",
                "launcher": {
                    "pid": 123,
                    "proc_start": "1",
                    "scope_unit": "job.scope",
                    "cgroup": "/job",
                },
            }
        ]
    }
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: state,
        tmp_path / "reducer.json",
    )
    reducer.refresh()
    calls: list[str] = []

    def adapter(value, resolved):
        calls.append(value["action"])
        return {"name": value["action"], "status": "fixture"}

    receipts = tmp_path / "receipts.json"
    actions = ActionService(reducer.snapshot, inventory_path, receipts, adapter=adapter)
    first = actions.execute(request("focus", {"job_id": "job-1"}))
    assert first["schema"] == "sinnix-ops-action-v1"
    assert actions.execute(request("focus", {"job_id": "job-1"})) == first
    assert calls == ["focus"]
    for action, target, key in [
        ("interrupt", {"job_id": "job-1"}, "k2"),
        ("freeze", {"unit": "safe"}, "k3"),
        ("thaw", {"unit": "safe"}, "k4"),
        ("reset_policy", {"unit": "safe"}, "k5"),
        ("heavy_lease", {"unit": "safe"}, "k6"),
        ("restart", {"unit": "safe"}, "k7"),
    ]:
        assert (
            actions.execute(request(action, target, key=key))["adapter"]["status"]
            == "fixture"
        )
    resumed = ActionService(reducer.snapshot, inventory_path, receipts, adapter=adapter)
    assert resumed.lookup("k1") == first


def test_action_rejects_unknown_pid_stale_revision_and_unsafe_unit(
    tmp_path: Path,
) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
    )
    reducer.refresh()
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        adapter=lambda *_: {},
    )
    with pytest.raises(ActionError):
        validate_request(
            {
                "action": "restart",
                "target": {"pid": "123"},
                "expected_revision": 1,
                "idempotency_key": "x",
                "operator_reason": "x",
            }
        )
    with pytest.raises(ActionError, match="stale"):
        actions.execute(request("restart", {"unit": "safe"}, revision=0))
    with pytest.raises(ActionError, match="restartable"):
        actions.execute(request("restart", {"unit": "fixed"}, key="fixed"))
    actions.execute(request("restart", {"unit": "safe"}, key="fixed-safe"))
    with pytest.raises(ActionError, match="another request"):
        actions.execute(request("reset_policy", {"unit": "safe"}, key="fixed"))


def test_policy_properties_and_rebuild_override_are_enumerated(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    reducer = Reducer(tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []})
    reducer.refresh()
    calls = []
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        adapter=lambda value, _resolved: calls.append(value) or {"status": "accepted"},
    )
    assert actions.execute(request("set_policy", {"unit": "safe"}, key="policy") | {
        "parameters": {"property": "CPUWeight", "value": "10"}
    })["adapter"]["status"] == "accepted"
    with pytest.raises(ActionError, match="unsupported runtime policy"):
        actions.execute(request("set_policy", {"unit": "safe"}, key="bad") | {
            "parameters": {"property": "Slice", "value": "app.slice"}
        })
    assert actions.execute(request("rebuild_override", {"unit": "safe"}, key="override") | {
        "parameters": {"name": "cores", "value": "8"}
    })["adapter"]["status"] == "accepted"


def test_valid_rejected_action_leaves_a_receipt(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    reducer = Reducer(tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []})
    reducer.refresh()
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        adapter=lambda *_: {},
    )
    with pytest.raises(ActionError, match="not in the inventory"):
        actions.execute(request("thaw", {"unit": "missing.service"}, key="rejected"))
    receipt = actions.lookup("rejected")
    assert receipt is not None
    assert receipt["status"] == "rejected"
