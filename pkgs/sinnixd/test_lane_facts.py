from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sinnixd.lane_facts import (
    LaneFacts,
    Pull,
    Receipt,
    advance,
    collect,
    derived_checkout_id,
    lane_view,
    pulls_from_sweep_actions,
)


def _facts(**overrides: object) -> LaneFacts:
    base: dict[str, object] = {
        "name": "packet-p-1",
        "checkout_id": "worktree-abc",
        "project": "polylogue",
        "branch": "feature/packet/polylogue-1",
        "bead": "polylogue-1",
        "head": "h" * 40,
        "pushed_head": "h" * 40,
        "master_head": "m" * 40,
        "holder": None,
        "running_ops": (),
        "lane_phase": "succeeded",
        "receipt": None,
        "pull": None,
    }
    base.update(overrides)
    return LaneFacts(**base)  # type: ignore[arg-type]


def _receipt(**overrides: object) -> Receipt:
    base: dict[str, object] = {
        "packet_id": "harvest-" + "0" * 32,
        "head": "h" * 40,
        "flags": (),
        "flagged": False,
        "authorized": False,
        "verification": "tests-run",
        "bead": "polylogue-1",
        "created_at": "2026-09-02T10:00:00+00:00",
    }
    base.update(overrides)
    return Receipt(**base)  # type: ignore[arg-type]


def test_dormant_workspaces_are_left_alone() -> None:
    """Anti-vacuity: the first fact-driven tick verified dozens of
    abandoned worktrees."""
    from datetime import UTC, datetime

    now = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    old = _facts(lane_finished_at="2026-08-20T00:00:00+00:00")
    assert advance(old, now=now).kind == "idle"
    fresh = _facts(lane_finished_at="2026-09-02T10:00:00+00:00")
    assert advance(fresh, now=now).kind == "verify"
    with_pull = _facts(lane_finished_at="2026-08-20T00:00:00+00:00", receipt=_receipt(), pull=Pull(number=1, head="h" * 40, verdict="wait", findings=0))
    assert advance(with_pull, now=now).kind == "await-sweep"


def test_advance_orders_facts_before_actions() -> None:
    """Anti-vacuity: each branch names the fact that decides it; reorder
    two of them and the wrong action wins."""
    assert advance(_facts(holder="integrator")).kind == "wait"
    assert advance(_facts(running_ops=("harvest",))).kind == "wait"
    assert advance(_facts(lane_phase="running")).kind == "wait"
    assert advance(_facts(lane_phase=None)).kind == "idle"
    assert advance(_facts(bead_closed=True, clean_receipt=True) if False else _facts(bead_closed=True)).kind == "done"
    assert advance(_facts(lane_phase="cancelled")).kind == "retry"
    assert advance(_facts()).kind == "verify"
    assert advance(_facts(verify_job=("v", "succeeded"))).kind == "harvest"
    assert advance(_facts(verify_job=("v", "failed"))).kind == "park"
    assert advance(_facts(verify_job=("v", "succeeded"), harvest_at_head=("j", "failed"))).kind == "park"
    assert advance(_facts(receipt=_receipt(), published_at_head=True)).kind == "await-sweep"
    # A red quick gate at this head parks instead of publishing every tick.
    assert advance(_facts(receipt=_receipt(), quick_at_head=("q", "failed"))).kind == "park"
    assert advance(_facts(receipt=_receipt(head="x" * 40))).kind == "verify"
    assert advance(_facts(receipt=_receipt())).kind == "publish"
    flagged = _receipt(flags=("FLAG: production definitions removed: f",), flagged=True)
    assert advance(_facts(receipt=flagged)).kind == "integrate"
    assert advance(_facts(receipt=flagged, integrators_at_head=("integrator",))).kind == "park"
    authorized = _receipt(flags=("FLAG: x",), flagged=True, authorized=True)
    assert advance(_facts(receipt=authorized)).kind == "publish"
    static = _receipt(verification="static-only")
    assert advance(_facts(receipt=static)).kind == "rebase"
    pull = Pull(number=7, head="h" * 40, verdict="conflict", findings=0)
    assert advance(_facts(receipt=_receipt(), pull=pull)).kind == "rebase"
    assert advance(_facts(receipt=_receipt(), pull=pull, integrators_at_head=("rebase",))).kind == "park"
    findings = Pull(number=7, head="h" * 40, verdict="findings", findings=2)
    assert advance(_facts(receipt=_receipt(), pull=findings)).kind == "review-fix"
    answered = Pull(number=7, head="h" * 40, verdict="findings", findings=2, answered_rounds=2)
    assert advance(_facts(receipt=_receipt(), pull=answered)).kind == "await-sweep"
    clean = Pull(number=7, head="h" * 40, verdict="wait", findings=0)
    assert advance(_facts(receipt=_receipt(), pull=clean)).kind == "await-sweep"
    moved = Pull(number=7, head="o" * 40, verdict="findings", findings=1)
    assert advance(_facts(receipt=_receipt(), pull=moved, pushed_head="o" * 40)).kind == "publish"


def test_collect_reads_the_daemon_state(tmp_path: Path) -> None:
    state = tmp_path / "state"
    worktree = tmp_path / "packet-p-1"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "feature/packet/polylogue-1", str(worktree)], check=True)
    subprocess.run(
        ["git", "-C", str(worktree), "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "seed"],
        check=True,
    )
    head = subprocess.run(["git", "-C", str(worktree), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    checkout_id = derived_checkout_id(str(worktree))
    (state / "workspaces").mkdir(parents=True)
    (state / "workspaces" / "index.json").write_text(
        json.dumps({"workspaces": [{"name": "packet-p-1", "path": str(worktree), "project_id": "polylogue", "branch": "feature/packet/polylogue-1"}]})
    )
    (state / "jobs").mkdir()
    (state / "jobs" / "lane.json").write_text(
        json.dumps(
            {
                "job_id": "lane",
                "created_at": "2026-09-02T10:00:00+00:00",
                "spec": {
                    "kind": "attested-agent",
                    "checkout": {"checkout_id": checkout_id, "head": head},
                    "contract": {"parameters": {"campaign": {"bead_ids": ["polylogue-1"]}}},
                },
                "state": {"phase": "succeeded", "terminal": True},
            }
        )
    )
    (state / "jobs" / "harvest.json").write_text(
        json.dumps(
            {
                "job_id": "harvest",
                "created_at": "2026-09-02T10:05:00+00:00",
                "spec": {"kind": "declared-operation", "operation": "harvest", "checkout": {"checkout_id": checkout_id, "head": head}},
                "state": {"phase": "running", "terminal": False},
            }
        )
    )
    (state / "results").mkdir()
    (state / "results" / "published.result").write_text(json.dumps({"value": {"outcome": "HARVEST_OK", "phase": "published"}}))
    (state / "jobs" / "authorize.json").write_text(
        json.dumps(
            {
                "job_id": "authorize",
                "created_at": "2026-09-02T10:06:00+00:00",
                "spec": {"kind": "declared-operation", "operation": "harvest", "checkout": {"checkout_id": checkout_id, "head": head}},
                "state": {"phase": "succeeded", "terminal": True},
                "artifacts": {"result": str(state / "results" / "published.result")},
            }
        )
    )
    (state / "harvest-packets").mkdir()
    (state / "harvest-packets" / ("harvest-" + "1" * 32 + ".json")).write_text(
        json.dumps({"packet_id": "harvest-" + "1" * 32, "workspace_id": checkout_id, "head": head, "redflags": [], "redflag_status": 0, "bead_id": "polylogue-1"})
    )

    facts = collect("polylogue", state_root=state, master_head="m" * 40)

    assert len(facts) == 1
    lane = facts[0]
    assert lane.head == head and lane.bead == "polylogue-1" and lane.lane_phase == "succeeded"
    assert lane.running_ops == ("harvest",)
    assert lane.receipt is not None and lane.receipt.head == head
    assert lane.published_at_head is True
    view = lane_view(lane)
    assert view["next"] == {"kind": "wait", "reason": "running: harvest"}


def test_pulls_from_sweep_actions_key_on_receipt() -> None:
    pulls = pulls_from_sweep_actions(
        [{"pr": 41, "head": "h" * 40, "verdict": "findings", "findings": 2, "receipt": "harvest-" + "0" * 32}, {"pr": 42, "head": "x"}]
    )
    assert pulls == {"harvest-" + "0" * 32: Pull(number=41, head="h" * 40, verdict="findings", findings=2)}
