from __future__ import annotations

import copy
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


def fake_unit_state_prober(unit: str, manager: str) -> dict[str, str]:
    """Stand-in for ActionService._live_unit_state_prober so receipt tests
    never shell out to the live systemd manager for a fixture unit."""
    return {"LoadState": "loaded", "ActiveState": "active", "SubState": "running"}


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
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        receipts,
        adapter=adapter,
        unit_state_prober=fake_unit_state_prober,
    )
    first = actions.execute(request("focus", {"job_id": "job-1"}))
    assert first["schema"] == "sinnix-ops-action-v1"
    assert actions.execute(request("focus", {"job_id": "job-1"})) == first
    assert calls == ["focus"]
    for action, target, key in [
        ("interrupt", {"job_id": "job-1"}, "k2"),
        ("freeze", {"unit": "safe"}, "k3"),
        ("thaw", {"unit": "safe"}, "k4"),
        ("reset_policy", {"unit": "safe"}, "k5"),
        ("restart", {"unit": "safe"}, "k7"),
        ("start", {"unit": "safe"}, "k8"),
        ("stop", {"unit": "safe"}, "k9"),
    ]:
        assert (
            actions.execute(request(action, target, key=key))["adapter"]["status"]
            == "fixture"
        )
    resumed = ActionService(
        reducer.snapshot,
        inventory_path,
        receipts,
        adapter=adapter,
        unit_state_prober=fake_unit_state_prober,
    )
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
        unit_state_prober=fake_unit_state_prober,
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
    # Lifecycle verbs share restart's admission gate and take no parameters,
    # and they refuse attested-job targets the way every unit verb does.
    for action in ("start", "stop"):
        with pytest.raises(ActionError, match="restartable"):
            actions.execute(request(action, {"unit": "fixed"}, key=f"{action}-fixed"))
        with pytest.raises(ActionError, match="does not accept parameters"):
            validate_request(
                {
                    **request(action, {"unit": "safe"}, key=f"{action}-params"),
                    "parameters": {"mode": "graceful"},
                }
            )
        with pytest.raises(ActionError, match="focus and interrupt"):
            validate_request(request(action, {"job_id": "job-1"}, key=f"{action}-job"))


def test_policy_properties_and_rebuild_override_are_enumerated(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
    )
    reducer.refresh()
    calls = []
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        adapter=lambda value, _resolved: calls.append(value) or {"status": "accepted"},
        unit_state_prober=fake_unit_state_prober,
    )
    assert (
        actions.execute(
            request("set_policy", {"unit": "safe"}, key="policy")
            | {"parameters": {"property": "CPUWeight", "value": "10"}}
        )["adapter"]["status"]
        == "accepted"
    )
    with pytest.raises(ActionError, match="unsupported runtime policy"):
        actions.execute(
            request("set_policy", {"unit": "safe"}, key="bad")
            | {"parameters": {"property": "Slice", "value": "app.slice"}}
        )
    assert (
        actions.execute(
            request("rebuild_override", {"unit": "safe"}, key="override")
            | {"parameters": {"name": "cores", "value": "8"}}
        )["adapter"]["status"]
        == "accepted"
    )


def test_valid_rejected_action_leaves_a_receipt(tmp_path: Path) -> None:
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
        unit_state_prober=fake_unit_state_prober,
    )
    with pytest.raises(ActionError, match="not in the inventory"):
        actions.execute(request("thaw", {"unit": "missing.service"}, key="rejected"))
    receipt = actions.lookup("rejected")
    assert receipt is not None
    assert receipt["status"] == "rejected"


def test_orphan_reap_requires_two_identical_cold_observations(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    job = {
        "job_id": "orphan-1",
        "schema_version": 3,
        "worktree": "/realm/worktrees/orphan-1",
        "launcher": {
            "pid": 123,
            "proc_start": "1",
            "scope_unit": "orphan.scope",
            "cgroup": "/orphan",
        },
    }
    observation = {
        "job_id": "orphan-1",
        "identity_revision": "rev-1",
        "orphaned": True,
        "workload": {"class": "sacrificial"},
        "coldness": {"candidate": True},
    }
    source_report = {"agent_gateway": {"jobs": [job], "orphaned_jobs": [observation]}}
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: copy.deepcopy(source_report),
        tmp_path / "reducer.json",
    )
    reducer.refresh()
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        adapter=lambda *_: {"status": "fixture-reaped"},
        unit_state_prober=fake_unit_state_prober,
    )
    reap_request = request(
        "interrupt", {"job_id": "orphan-1"}, key="reap-before-second"
    ) | {"parameters": {"orphan_reap": True}}
    with pytest.raises(ActionError, match="two identical"):
        actions.execute(reap_request)
    reducer.refresh()
    accepted = actions.execute(
        request(
            "interrupt", {"job_id": "orphan-1"}, revision=2, key="reap-after-second"
        )
        | {"parameters": {"orphan_reap": True}}
    )
    assert accepted["adapter"]["status"] == "fixture-reaped"
    assert (
        accepted["preconditions"]["resolved"]["orphan"]["policy"]["observation_count"]
        == 2
    )


def test_scope_targets_admit_only_name_shaped_live_units_and_only_stop(
    tmp_path: Path,
) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
    )
    reducer.refresh()
    live_units = {"sinnix-build-cargo-test-1786566375240889502-2296063.scope": "user"}
    commands: list[list[str]] = []

    def adapter(value, resolved):
        commands.append(value["action"])
        return {"status": "fixture", "manager": resolved.get("manager")}

    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        adapter=adapter,
        scope_prober=lambda unit: live_units.get(unit),
        unit_state_prober=fake_unit_state_prober,
    )
    # A name that does not match the sinnix-scope launcher convention at all.
    with pytest.raises(ActionError, match="does not match"):
        actions.execute(
            request("stop", {"scope": "some-other-unit.service"}, key="bad-shape")
        )
    # Name-shaped but not actually live (probe returns None) -- name alone is
    # not trust.
    with pytest.raises(ActionError, match="not a live"):
        actions.execute(
            request(
                "stop",
                {"scope": "sinnix-build-cargo-1-2.scope"},
                key="not-live",
            )
        )
    # Only "stop" is permitted on a scope target.
    with pytest.raises(ActionError, match="only support stop"):
        validate_request(
            request(
                "restart",
                {"scope": "sinnix-build-cargo-test-1786566375240889502-2296063.scope"},
                key="wrong-verb",
            )
        )
    # A genuinely live, name-shaped scope is admitted and stopped.
    accepted = actions.execute(
        request(
            "stop",
            {"scope": "sinnix-build-cargo-test-1786566375240889502-2296063.scope"},
            key="stop-scope",
        )
    )
    assert accepted["adapter"]["manager"] == "user"
    # previous_state/resulting_state carry the scope's own {kind, unit,
    # manager, systemd} shape, not the resolved orphan/job dict from
    # unrelated targets.
    assert accepted["previous_state"] == {
        "kind": "scope",
        "unit": "sinnix-build-cargo-test-1786566375240889502-2296063.scope",
        "manager": "user",
        "systemd": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
        },
    }
    assert accepted["resulting_state"] == accepted["previous_state"]
    assert commands == ["stop"]
    # Targeting both a unit and a scope at once is rejected at validation.
    with pytest.raises(ActionError, match="exactly one"):
        validate_request(
            {
                "action": "stop",
                "target": {"unit": "safe", "scope": "sinnix-build-cargo-1-2.scope"},
                "expected_revision": 1,
                "idempotency_key": "both",
                "operator_reason": "x",
                "parameters": {},
            }
        )


def test_receipt_size_stays_bounded_by_the_resolved_target_not_the_estate(
    tmp_path: Path,
) -> None:
    """sinnix-rd69: a stop-scope receipt used to embed the ENTIRE reducer
    snapshot (every agent-gateway job's full lifecycle history, per-process
    chrome IO, blocked tasks) twice over, in previous_state and
    resulting_state, because both copied `snapshot["state"]` wholesale. A
    live receipt measured 25KB+ for a single-scope action. previous_state
    and resulting_state must be trimmed to the resolved target's own state;
    reverting `_target_state` to `lambda resolved: snapshot.get("state")`
    (the pre-fix behavior) blows the bound below."""
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    # An oversized state report standing in for the live estate: many
    # unrelated jobs with bulky per-process telemetry, none of them the
    # action's own target.
    bloat_jobs = [
        {
            "job_id": f"unrelated-{i}",
            "schema_version": 3,
            "worktree": f"/realm/worktrees/unrelated-{i}",
            "launcher": {
                "pid": 1000 + i,
                "proc_start": "1",
                "scope_unit": f"unrelated-{i}.scope",
                "cgroup": f"/unrelated-{i}",
            },
            "history": ["x" * 200] * 20,
        }
        for i in range(50)
    ]
    state = {
        "jobs": bloat_jobs,
        "agent_gateway": {"jobs": bloat_jobs, "orphaned_jobs": []},
        "chrome": {"processes": [{"pid": i, "io": "y" * 500} for i in range(50)]},
    }
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: state,
        tmp_path / "reducer.json",
    )
    reducer.refresh()
    assert len(json.dumps(reducer.snapshot()["state"])) > 20_000, (
        "fixture must reproduce the estate-sized snapshot the bug embedded"
    )
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        adapter=lambda *_: {"status": "accepted"},
        unit_state_prober=fake_unit_state_prober,
    )
    receipt = actions.execute(request("restart", {"unit": "safe"}, key="bounded"))
    serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    assert len(serialized) < 4096, (
        f"receipt grew to {len(serialized)} bytes -- previous_state/"
        "resulting_state must stay scoped to the resolved target, not the "
        "whole reducer snapshot"
    )
    # The full pre-action snapshot is not lost -- its sequence number stays
    # on the receipt so it is reachable via the snapshot store separately.
    assert receipt["preconditions"]["revision"] == reducer.sequence


def test_scope_pattern_matches_live_identity_shape():
    """Live scopes carry the command-identity segment since 2026-08-13; the
    pattern without it admitted nothing for five days. Mutation: dropping the
    identity group from SCOPE_UNIT_PATTERN fails the first assert."""
    from sinnix_ops_reducer.actions import SCOPE_UNIT_PATTERN

    assert SCOPE_UNIT_PATTERN.match("sinnix-build-cargo-test-1786566375240889502-2296063.scope")
    assert SCOPE_UNIT_PATTERN.match("sinnix-nix-build-nix-1-2.scope")
    assert not SCOPE_UNIT_PATTERN.match("sinnix-build-1786566375240889502-2296063.scope")
    assert not SCOPE_UNIT_PATTERN.match("sinnix-evil-x-1-2.scope")
