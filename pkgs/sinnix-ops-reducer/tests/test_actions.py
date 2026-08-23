from __future__ import annotations

import json
import signal
import subprocess
import sys
from pathlib import Path

import pytest
from sinnix_ops_reducer.actions import (
    ActionError,
    ActionService,
    process_admitted_slices,
    validate_request,
)
from sinnix_ops_reducer.agent_jobs import AgentCtlError
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


class FakeAgentJobs:
    def __init__(self, jobs: list[dict]) -> None:
        self.jobs = {str(job["job_id"]): job for job in jobs}
        self.cancelled: list[str] = []

    def get(self, job_id: str) -> dict:
        try:
            return self.jobs[job_id]
        except KeyError as error:
            raise AgentCtlError("unknown job") from error

    def cancel(self, job_id: str) -> dict:
        job = self.get(job_id)
        self.cancelled.append(job_id)
        return job | {
            "state": {
                "phase": "cancelled",
                "terminal": True,
                "observed_at": "2026-08-23T10:00:00Z",
                "cancellation": {"stop_acknowledged_at": "2026-08-23T10:00:00Z"},
            },
            "cancel_requested": True,
            "already_terminal": False,
        }


def test_action_fixtures_are_attested_and_idempotent_across_restart(
    tmp_path: Path,
) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    job = {
        "job_id": "job-1",
        "kind": "attested-agent",
        "project_id": "sinnix",
        "checkout": {"checkout_id": "default", "path": "/realm/project/sinnix"},
        "contract": {"backend": "codex", "model": "fixture", "effort": "high"},
        "state": {"phase": "running", "terminal": False},
    }
    state = {"jobs": [job]}
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
        agent_jobs=FakeAgentJobs([job]),
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


def test_park_requires_a_bounded_deadline(tmp_path: Path) -> None:
    """The hub's park button posts `deadline_seconds` explicitly (it prompts
    the operator for it) precisely because this verb refuses to run without
    one -- a parked unit must have a scheduled thaw, never an indefinite
    freeze an operator forgot about."""
    base = request("park", {"unit": "safe"}, key="park-missing")
    with pytest.raises(ActionError, match="deadline_seconds"):
        validate_request(base)
    with pytest.raises(ActionError, match="between 1 and 86400"):
        validate_request({**base, "parameters": {"deadline_seconds": 0}})
    with pytest.raises(ActionError, match="between 1 and 86400"):
        validate_request({**base, "parameters": {"deadline_seconds": 86401}})
    validated = validate_request({**base, "parameters": {"deadline_seconds": 600}})
    assert validated["parameters"] == {"deadline_seconds": 600}

    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
    )
    reducer.refresh()
    calls: list[dict] = []
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        adapter=lambda value, _resolved: calls.append(value) or {"status": "fixture"},
        unit_state_prober=fake_unit_state_prober,
    )
    receipt = actions.execute(
        request("park", {"unit": "safe"}, key="park-ok")
        | {"parameters": {"deadline_seconds": 600}}
    )
    assert receipt["adapter"]["status"] == "fixture"
    assert calls[0]["parameters"] == {"deadline_seconds": 600}


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


def test_interrupt_uses_agentctl_and_records_its_cancellation_truth(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    job = {
        "job_id": "job-1",
        "kind": "attested-agent",
        "project_id": "sinnix",
        "checkout": {"checkout_id": "default", "path": "/realm/project/sinnix"},
        "contract": {"backend": "codex", "model": "fixture", "effort": "high"},
        "state": {"phase": "running", "terminal": False},
    }
    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
    )
    reducer.refresh()
    agent_jobs = FakeAgentJobs([job])
    actions = ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        agent_jobs=agent_jobs,
        unit_state_prober=fake_unit_state_prober,
    )
    receipt = actions.execute(request("interrupt", {"job_id": "job-1"}))
    assert agent_jobs.cancelled == ["job-1"]
    assert receipt["adapter"]["job"]["cancel_requested"] is True
    assert receipt["resulting_state"]["job"]["state"]["phase"] == "cancelled"

    with pytest.raises(ActionError, match="attested agent"):
        ActionService(
            reducer.snapshot,
            inventory_path,
            tmp_path / "other-receipts.json",
            agent_jobs=FakeAgentJobs([job | {"kind": "declared-operation"}]),
            unit_state_prober=fake_unit_state_prober,
        ).execute(request("interrupt", {"job_id": "job-1"}, key="declared"))


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


def test_receipt_size_stays_bounded_by_the_resolved_target_not_the_system(
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
    # An oversized state report standing in for the live system: many
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
        "fixture must reproduce the system-sized snapshot the bug embedded"
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


def test_receipts_append_prior_lines_never_rewritten(tmp_path: Path) -> None:
    """Two accepted actions must cost one appended line each, not a whole-store
    rewrite. Mutation: reverting execute() to `atomic_json(self.receipts_path,
    self.receipts)` fails the prefix-stability assert below, because the
    dict-rewrite serializes both receipts into file 1's own bytes on the very
    first write."""
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
        adapter=lambda *_: {"status": "accepted"},
        unit_state_prober=fake_unit_state_prober,
    )
    ledger = actions.receipts_ledger_path
    assert ledger.name == "receipts.jsonl"

    actions.execute(request("restart", {"unit": "safe"}, key="k1"))
    after_first = ledger.read_bytes()
    # Marker line + one receipt line.
    assert len(after_first.splitlines()) == 2

    actions.execute(request("restart", {"unit": "safe"}, key="k2"))
    after_second = ledger.read_bytes()
    assert len(after_second.splitlines()) == 3
    # Append-only: everything written for the first action is byte-identical
    # in the file after the second action, not re-serialized alongside it.
    assert after_second[: len(after_first)] == after_first
    # The legacy whole-file store was never created or touched.
    assert not (tmp_path / "receipts.json").exists()


def test_receipts_migration_folds_legacy_dict_exactly_once(tmp_path: Path) -> None:
    """A pre-existing whole-file receipts dict is folded into the ledger on
    first start and left untouched; a second start (a restart) must not
    re-fold it. Mutation: dropping the `if self.receipts_ledger_path.exists():
    return` guard fails the second-instance line-count assert with a doubled
    ledger."""
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    legacy_path = tmp_path / "receipts.json"
    legacy = {
        "old-1": {"idempotency_key": "old-1", "status": "accepted"},
        "old-2": {"idempotency_key": "old-2", "status": "rejected"},
    }
    legacy_path.write_text(json.dumps(legacy))
    legacy_bytes_before = legacy_path.read_bytes()

    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
    )
    reducer.refresh()

    first = ActionService(
        reducer.snapshot,
        inventory_path,
        legacy_path,
        adapter=lambda *_: {"status": "accepted"},
        unit_state_prober=fake_unit_state_prober,
    )
    ledger = first.receipts_ledger_path
    lines_after_first_start = ledger.read_text(encoding="utf-8").splitlines()
    # One migration marker + the two folded legacy receipts.
    assert len(lines_after_first_start) == 3
    assert first.lookup("old-1") == legacy["old-1"]
    assert first.lookup("old-2") == legacy["old-2"]

    second = ActionService(
        reducer.snapshot,
        inventory_path,
        legacy_path,
        adapter=lambda *_: {"status": "accepted"},
        unit_state_prober=fake_unit_state_prober,
    )
    lines_after_second_start = ledger.read_text(encoding="utf-8").splitlines()
    assert lines_after_second_start == lines_after_first_start
    assert second.lookup("old-1") == legacy["old-1"]
    # The legacy file is read-only to the migration: never rewritten, never
    # deleted.
    assert legacy_path.read_bytes() == legacy_bytes_before


def test_receipts_replay_after_restart_reads_the_ledger(tmp_path: Path) -> None:
    """A fresh ActionService pointed at the same receipts_path after a
    restart must answer idempotency lookups from the ledger it wrote, not
    from in-memory state that died with the old process. Mutation: skipping
    the migration/index-fold in `_load_receipts` (returning `{}` instead)
    fails the `resumed.lookup` assert."""
    inventory_path = tmp_path / "inventory.json"
    inventory(inventory_path)
    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
    )
    reducer.refresh()
    receipts_path = tmp_path / "receipts.json"
    original = ActionService(
        reducer.snapshot,
        inventory_path,
        receipts_path,
        adapter=lambda *_: {"status": "accepted"},
        unit_state_prober=fake_unit_state_prober,
    )
    written = original.execute(request("restart", {"unit": "safe"}, key="k1"))

    resumed = ActionService(
        reducer.snapshot,
        inventory_path,
        receipts_path,
        adapter=lambda *_: {"status": "accepted"},
        unit_state_prober=fake_unit_state_prober,
    )
    assert resumed.lookup("k1") == written
    # Replay must hit the cached receipt, not re-invoke the adapter.
    calls: list[str] = []
    resumed.adapter = lambda *_: calls.append("adapter-called") or {"status": "x"}
    assert resumed.execute(request("restart", {"unit": "safe"}, key="k1")) == written
    assert calls == []


def test_scope_pattern_matches_live_identity_shape():
    """Live scopes carry the command-identity segment since 2026-08-13; the
    pattern without it admitted nothing for five days. Mutation: dropping the
    identity group from SCOPE_UNIT_PATTERN fails the first assert."""
    from sinnix_ops_reducer.actions import SCOPE_UNIT_PATTERN

    assert SCOPE_UNIT_PATTERN.match(
        "sinnix-build-cargo-test-1786566375240889502-2296063.scope"
    )
    assert SCOPE_UNIT_PATTERN.match("sinnix-nix-build-nix-1-2.scope")
    assert not SCOPE_UNIT_PATTERN.match(
        "sinnix-build-1786566375240889502-2296063.scope"
    )
    assert not SCOPE_UNIT_PATTERN.match("sinnix-evil-x-1-2.scope")


# --------------------------------------------------------------------------
# process targets (sinnix-mble): {"process": {"pid": N, "start_ticks": M}},
# accepting only stop, admitted by live cgroup membership.
# --------------------------------------------------------------------------


def inventory_with_sacrificial_slice(path: Path) -> None:
    """A runtime inventory carrying one sacrificial (ManagedOOMMemoryPressure
    = kill) slice, background.slice, alongside the two surfaces every other
    fixture in this file uses -- so the same file can drive both the
    unit-target and the process-target tests."""
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
                },
                "slices": {
                    "system": {"system-critical": {"CPUWeight": 400}},
                    "user": {
                        "agent": {"CPUWeight": 400},
                        "background": {
                            "ManagedOOMMemoryPressure": "kill",
                            "MemoryHigh": "2G",
                        },
                        "gpu-runtime": {"MemoryHigh": "8G"},
                    },
                },
            }
        )
    )


def make_process_actions(
    tmp_path: Path,
    process_prober,
    *,
    inventory_writer=inventory_with_sacrificial_slice,
    self_pid: int | None = -1,
    process_stop_grace_seconds: float = 0.05,
    signaler=None,
    sleeper=None,
    clock=None,
) -> ActionService:
    inventory_path = tmp_path / "inventory.json"
    inventory_writer(inventory_path)
    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
    )
    reducer.refresh()
    kwargs: dict = {
        "adapter": None,
        "unit_state_prober": fake_unit_state_prober,
        "process_prober": process_prober,
        "self_pid": self_pid,
        "process_stop_grace_seconds": process_stop_grace_seconds,
    }
    if signaler is not None:
        kwargs["signaler"] = signaler
    if sleeper is not None:
        kwargs["sleeper"] = sleeper
    if clock is not None:
        kwargs["clock"] = clock
    return ActionService(
        reducer.snapshot,
        inventory_path,
        tmp_path / "receipts.json",
        **kwargs,
    )


def test_process_target_shape_is_validated_and_restricted_to_stop() -> None:
    """Mutation: drop the pid/start_ticks type or bound checks and a string
    pid or a negative start_ticks reaches the resolver; drop the verb
    restriction and `restart` on a process target reaches the adapter."""
    with pytest.raises(ActionError, match="pid and start_ticks"):
        validate_request(
            request("stop", {"process": {"pid": 100}}, key="missing-field")
        )
    with pytest.raises(ActionError, match="greater than 1"):
        validate_request(
            request(
                "stop",
                {"process": {"pid": 1, "start_ticks": 5}},
                key="pid-one",
            )
        )
    with pytest.raises(ActionError, match="greater than 1"):
        validate_request(
            request(
                "stop",
                {"process": {"pid": "123", "start_ticks": 5}},
                key="pid-string",
            )
        )
    with pytest.raises(ActionError, match="non-negative integer"):
        validate_request(
            request(
                "stop",
                {"process": {"pid": 123, "start_ticks": -1}},
                key="negative-ticks",
            )
        )
    with pytest.raises(ActionError, match="only support stop"):
        validate_request(
            request(
                "restart",
                {"process": {"pid": 123, "start_ticks": 5}},
                key="wrong-verb",
            )
        )
    with pytest.raises(ActionError, match="exactly one"):
        validate_request(
            {
                "action": "stop",
                "target": {"unit": "safe", "process": {"pid": 123, "start_ticks": 5}},
                "expected_revision": 1,
                "idempotency_key": "both",
                "operator_reason": "x",
                "parameters": {},
            }
        )
    # A well-shaped request validates cleanly; whether it is admitted is a
    # question for execute(), not validate_request().
    validated = validate_request(
        request("stop", {"process": {"pid": 123, "start_ticks": 987654}}, key="ok")
    )
    assert validated["target"] == {"process": {"pid": 123, "start_ticks": 987654}}


def test_process_stop_refuses_a_start_ticks_mismatch_or_a_dead_pid(
    tmp_path: Path,
) -> None:
    """The start_ticks pin is checked against a live prober at execution
    time, not trusted from the request. Mutation: compare only the pid and a
    reused pid is silently retargeted; skip the not-found case and a pid
    that has already exited reads as an ordinary admission refusal instead
    of a distinct 404.
    """

    def prober(pid: int):
        if pid == 200:
            # Live, but a DIFFERENT start_ticks than the caller observed --
            # the pid was reused by an unrelated process.
            return (999999, "sinnix-agent-x-1-2.scope", "agent.slice")
        return None  # pid 300: no such process at all

    actions = make_process_actions(tmp_path, prober)
    with pytest.raises(ActionError, match="reused"):
        actions.execute(
            request(
                "stop",
                {"process": {"pid": 200, "start_ticks": 111111}},
                key="mismatch",
            )
        )
    assert actions.lookup("mismatch")["status"] == "rejected"
    with pytest.raises(ActionError, match="does not exist"):
        actions.execute(
            request(
                "stop",
                {"process": {"pid": 300, "start_ticks": 1}},
                key="gone",
            )
        )


def test_process_stop_admission_is_by_cgroup_membership_not_name(
    tmp_path: Path,
) -> None:
    """Every non-negotiable in the design: agent.slice and build.slice admit
    unconditionally, a slice the inventory marks sacrificial (background,
    here) admits too, an unrelated slice (gpu-runtime, present in the
    inventory but never marked sacrificial) is refused, a process with no
    slice at all (a PID 1 direct child, e.g. init.scope) is refused, and the
    reducer's own pid is refused regardless of which slice it is in.

    Mutation: admit by process/command name instead of cgroup and a process
    named `rg` outside every admitted slice would be accepted; drop the
    self-pid check and the reducer could target itself.
    """
    slice_by_pid = {
        401: "agent.slice",
        402: "build.slice",
        403: "background.slice",  # sacrificial per inventory_with_sacrificial_slice
        404: "gpu-runtime.slice",  # in the inventory, never marked sacrificial
        405: "",  # PID 1 direct child: no slice segment at all
        406: "agent.slice",  # would admit, but this pid IS the reducer itself
    }

    def prober(pid: int):
        if pid not in slice_by_pid:
            return None
        return (77, "unit.scope", slice_by_pid[pid])

    actions = make_process_actions(tmp_path, prober, self_pid=406)

    def stop(pid: int, key: str) -> dict:
        return actions.execute(
            request("stop", {"process": {"pid": pid, "start_ticks": 77}}, key=key)
        )

    assert stop(401, "agent")["preconditions"]["resolved"]["slice_unit"] == (
        "agent.slice"
    )
    assert stop(402, "build")["preconditions"]["resolved"]["slice_unit"] == (
        "build.slice"
    )
    assert stop(403, "sacrificial")["preconditions"]["resolved"]["slice_unit"] == (
        "background.slice"
    )
    with pytest.raises(ActionError, match="not in an admitted cgroup"):
        stop(404, "gpu-runtime-refused")
    with pytest.raises(ActionError, match="not in an admitted cgroup"):
        stop(405, "pid1-child-refused")
    with pytest.raises(ActionError, match="own process"):
        stop(406, "self-refused")


def test_process_admitted_slices_matches_the_action_services_own_admission(
    tmp_path: Path,
) -> None:
    """The page-facing helper (`process_admitted_slices`, imported by
    pages/pressure.py) must compute exactly what the resolver enforces, or
    the hub can offer a button the API answers 403 to.

    Mutation: let the two computations diverge (e.g. the page hardcodes a
    slice list) and this equality fails the moment the inventory's
    sacrificial markers change.
    """
    inventory_path = tmp_path / "inventory.json"
    inventory_with_sacrificial_slice(inventory_path)
    inventory = json.loads(inventory_path.read_text())
    assert process_admitted_slices(inventory) == {
        "agent.slice",
        "build.slice",
        "background.slice",
    }


def test_process_stop_sends_sigterm_then_escalates_to_sigkill_after_grace(
    tmp_path: Path,
) -> None:
    """Reversible-first, bounded escalation: SIGTERM immediately, SIGKILL
    only if the same identity is still alive once the grace window elapses.
    Deterministic and fast -- clock/sleeper/process_prober are all fakes, so
    no wall-clock sleep and no real process is involved here (see the
    following test for that).

    Mutation: send SIGKILL first, or never escalate at all, and the signal
    sequence recorded below stops matching.
    """
    signals: list[tuple[int, int]] = []
    ticks = {"now": 0.0}
    # The process never exits (process_prober always reports the same
    # start_ticks alive) until enough fake time has elapsed that the poll
    # loop's own deadline check ends it -- this is what forces escalation.
    calls = {"n": 0}

    def prober(pid: int):
        calls["n"] += 1
        return (55, "unit.scope", "agent.slice")

    def signaler(pid: int, sig: int) -> None:
        signals.append((pid, sig))

    def clock() -> float:
        return ticks["now"]

    def sleeper(seconds: float) -> None:
        ticks["now"] += seconds

    actions = make_process_actions(
        tmp_path,
        prober,
        process_stop_grace_seconds=0.2,
        signaler=signaler,
        sleeper=sleeper,
        clock=clock,
    )
    receipt = actions.execute(
        request("stop", {"process": {"pid": 501, "start_ticks": 55}}, key="escalate")
    )
    assert signals == [(501, signal.SIGTERM), (501, signal.SIGKILL)]
    assert receipt["adapter"]["signal"] == "SIGKILL"
    assert receipt["adapter"]["grace_seconds"] == 0.2
    assert calls["n"] > 0


def test_process_stop_does_not_escalate_once_the_process_exits(
    tmp_path: Path,
) -> None:
    """The common case: SIGTERM alone is enough, and the grace window is not
    spent waiting once the process is gone.

    Mutation: always escalate regardless of liveness and a rg that exits
    cleanly on SIGTERM would still take a needless SIGKILL.
    """
    signals: list[tuple[int, int]] = []
    state = {"alive": True}

    def prober(pid: int):
        if not state["alive"]:
            return None
        return (55, "unit.scope", "agent.slice")

    def signaler(pid: int, sig: int) -> None:
        signals.append((pid, sig))
        if sig == signal.SIGTERM:
            state["alive"] = False

    actions = make_process_actions(
        tmp_path,
        prober,
        process_stop_grace_seconds=5.0,
        signaler=signaler,
        sleeper=lambda seconds: None,
        clock=lambda: 0.0,
    )
    receipt = actions.execute(
        request("stop", {"process": {"pid": 502, "start_ticks": 55}}, key="clean-exit")
    )
    assert signals == [(502, signal.SIGTERM)]
    assert receipt["adapter"]["signal"] == "SIGTERM"


def test_process_stop_kills_a_real_process(tmp_path: Path) -> None:
    """The production route, end to end: a real subprocess, the real
    /proc-reading prober, and the real os.kill signaler -- not a fake for
    any of the three. Proves the stop verb actually terminates the process
    it targets, not merely that the bookkeeping around a fake signaler is
    correct.

    Mutation: swap `self.signaler(pid, signal.SIGKILL)` for a no-op (or for
    SIGSTOP) and this test hangs until the surrounding pytest timeout, or
    the final `proc.wait` never returns 0 alive processes.
    """
    from sinnix_ops_reducer.actions import ActionService

    # Ignores SIGTERM so the escalation path is exercised for real; exits
    # promptly on SIGKILL because that signal cannot be caught or ignored.
    # Prints and flushes a line only once the handler is installed, and the
    # test blocks on reading it -- without this handshake the SIGTERM can
    # race the child's own startup and kill it before SIG_IGN is in place,
    # which flips this from an escalation test into a flaky SIGTERM test.
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, sys, time; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "print('ready', flush=True); "
            "time.sleep(30)",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "ready"

        stat_text = Path(f"/proc/{proc.pid}/stat").read_text(encoding="utf-8")
        start_ticks = int(stat_text.rpartition(")")[2].split()[19])

        inventory_path = tmp_path / "inventory.json"
        inventory_with_sacrificial_slice(inventory_path)
        reducer = Reducer(
            tmp_path / "status.json", tmp_path / "token", lambda: {"jobs": []}
        )
        reducer.refresh()
        actions = ActionService(
            reducer.snapshot,
            inventory_path,
            tmp_path / "receipts.json",
            unit_state_prober=fake_unit_state_prober,
            self_pid=-1,
            process_stop_grace_seconds=0.3,
        )
        # The real _live_process_prober, reading this real process's real
        # /proc entry, confirms the identity before the stop is even sent.
        live = actions.process_prober(proc.pid)
        assert live is not None
        assert live[0] == start_ticks

        result = actions._stop_process({"pid": proc.pid, "start_ticks": start_ticks})
        assert result["signal"] == "SIGKILL"

        returncode = proc.wait(timeout=5)
        # A process killed by a signal reports -signal on POSIX.
        assert returncode == -signal.SIGKILL
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
