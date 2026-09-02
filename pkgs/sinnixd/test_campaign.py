from __future__ import annotations

from sinnixd.campaign import (
    CampaignLane,
    build_schedule,
    dedupe_lanes,
    runnable_groups,
)


def lane(group: str, *keys: str, beads: tuple[str, ...] | None = None) -> CampaignLane:
    return CampaignLane(
        group,
        beads or (group,),
        keys,
        f"packet-{group}",
        f"feature/{group}",
        {"group": group},
    )


def test_dedupe_compiled_beads_into_one_group_lane() -> None:
    first = lane("leader", "parser", beads=("leader", "member"))
    assert dedupe_lanes([first, first]) == (first,)


def test_key_dag_is_deterministic_and_keeps_disjoint_roots() -> None:
    schedule = build_schedule(
        [lane("b", "shared"), lane("a", "shared"), lane("free", "other")]
    )

    assert schedule.node_ids() == ("a", "b", "free")
    assert schedule.edges == (("a", "b"),)


def test_active_workspace_and_bead_are_typed_skips() -> None:
    schedule = build_schedule(
        [lane("workspace"), lane("bead", beads=("bead", "member"))],
        active_workspace_names={"packet-workspace"},
        active_bead_ids={"member"},
    )

    assert [skip.code for skip in schedule.skipped] == [
        "active-bead",
        "active-workspace",
    ]
    assert schedule.lanes == ()


def test_running_lane_key_overlap_is_a_typed_skip_with_keys() -> None:
    schedule = build_schedule(
        [lane("candidate", "module:polylogue.cost", "table:jobs")],
        active_conflict_keys={"table:jobs"},
    )

    assert schedule.lanes == ()
    assert schedule.skipped[0].code == "conflict-key-overlap"
    assert "table:jobs" in schedule.skipped[0].reason


def test_distinct_files_in_one_test_tree_are_not_serialized() -> None:
    from sinnixd.packets import infer_conflict_keys

    first = infer_conflict_keys("Fix tests/unit/test_pipeline.py")
    second = infer_conflict_keys("Fix tests/unit/test_lineage.py")
    schedule = build_schedule(
        [lane("pipeline", *first), lane("lineage", *second)],
        active_conflict_keys=set(first),
    )

    assert schedule.node_ids() == ("lineage",)
    assert schedule.skipped[0].group == "pipeline"
    assert schedule.skipped[0].code == "conflict-key-overlap"


def test_failed_predecessor_frees_key_for_next_lane() -> None:
    schedule = build_schedule([lane("a", "shared"), lane("b", "shared")])
    assert runnable_groups(schedule, {"a": {"terminal": True, "phase": "failed"}}) == (
        "b",
    )


def test_a_wave_drained_by_provisioning_names_provisioning() -> None:
    """A wave whose every lane failed to provision must not report a conflict.

    Reporting `conflict-key-overlap` with an empty overlap sends the reader
    looking for a running lane that does not exist.
    """
    import pytest
    from sinnixd.campaign import CampaignRunner, CampaignSchedule, WaveDrainedError
    from sinnixd.workspaces import WorkspaceError

    class FakeJobs:
        def __init__(self) -> None:
            self.events: list[dict[str, object]] = []

        def spool_event(self, event: dict[str, object]) -> None:
            self.events.append(event)

    runner = CampaignRunner(
        projects=None, jobs=FakeJobs(), workspaces=None, plans=None, native_runner=None
    )
    only = lane("solo", "table:jobs")
    schedule = CampaignSchedule((only,), (), ())

    def submit(*_args: object, **_kwargs: object) -> dict[str, object]:
        runner._provisioning = only.group
        raise WorkspaceError("uv sync failed")

    runner._submit_plan = submit  # type: ignore[method-assign]

    with pytest.raises(WaveDrainedError) as raised:
        runner._submit_tolerating_conflicts(
            schedule, "fixture", lambda **_kwargs: "job", "wave-1"
        )

    assert "uv sync failed" in str(raised.value)


def test_leftover_worktree_blocks_only_while_an_agent_holds_it() -> None:
    """An unheld leftover worktree is resumed, not a lock on its bead.

    Anti-vacuity: treating every registered workspace as active parked 26 of
    the polylogue frontier's beads (2026-09-01), every P0 among them, behind
    worktrees their killed lanes left behind.
    """
    from types import SimpleNamespace

    from sinnixd.campaign import held_workspace_names

    existing = {
        "packet-a": SimpleNamespace(workspace_id="worktree-a"),
        "packet-b": SimpleNamespace(workspace_id="worktree-b"),
    }
    assert held_workspace_names(existing, {"worktree-a"}) == {"packet-a"}
    assert held_workspace_names(existing, set()) == set()


def test_frontier_orders_by_priority_before_id() -> None:
    from sinnixd.campaign import frontier_order

    rows = [
        {"id": "p-aaa", "priority": 2},
        {"id": "p-zzz", "priority": 0},
        {"id": "p-mmm"},
    ]
    assert [row["id"] for row in sorted(rows, key=frontier_order)] == [
        "p-zzz",
        "p-aaa",
        "p-mmm",
    ]
    # Anti-vacuity: ordering by id alone spends a wave limit on the lowest
    # ids and never reaches the P0 work.


def test_launch_claims_beads_and_reports_the_ones_it_could_not() -> None:
    """A launched lane's bead leaves the frontier until merge or release.

    Anti-vacuity: without the claim, refill relaunched polylogue-0cm7m one
    minute after its first lane succeeded, while that result was still with
    an integrator (2026-09-01 21:28Z).
    """
    import subprocess
    from pathlib import Path

    from sinnixd.campaign import claim_beads

    calls: list[list[str]] = []

    def run(argv, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(argv)
        code = 1 if argv[2] == "p-bad" else 0
        return subprocess.CompletedProcess(argv, code, "", "refused")

    failed = claim_beads(Path("/repo"), ["p-ok", "p-bad"], run=run)

    assert failed == ["p-bad"]
    assert calls[0][:6] == ["bd", "update", "p-ok", "-s", "in_progress", "-a"]
