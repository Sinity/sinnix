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
        runner._submit_tolerating_provisioning_failures(
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


def _lane_facts(**overrides: object):
    from sinnixd.lane_facts import LaneFacts, Receipt

    base: dict[str, object] = {
        "name": "packet-p-9",
        "checkout_id": "worktree-abc",
        "project": "polylogue",
        "branch": "feature/packet/polylogue-9",
        "bead": "polylogue-9",
        "head": "h" * 40,
        "pushed_head": "h" * 40,
        "master_head": "m" * 40,
        "holder": None,
        "running_ops": (),
        "lane_phase": "succeeded",
        "receipt": None,
        "pull": None,
    }
    if overrides.pop("clean_receipt", False):
        base["receipt"] = Receipt(
            packet_id="harvest-" + "0" * 32,
            head="h" * 40,
            flags=(),
            flagged=False,
            authorized=False,
            verification="from-job",
            bead="polylogue-9",
            created_at="",
        )
    if overrides.pop("flagged_receipt", False):
        base["receipt"] = Receipt(
            packet_id="harvest-" + "1" * 32,
            head="h" * 40,
            flags=("FLAG: production definitions removed: f",),
            flagged=True,
            authorized=False,
            verification="from-job",
            bead="polylogue-9",
            created_at="",
        )
    base.update(overrides)
    return LaneFacts(**base)  # type: ignore[arg-type]


def _runner(tmp_path):  # type: ignore[no-untyped-def]
    from types import SimpleNamespace

    from sinnixd.campaign import CampaignRunner

    class Projects:
        def get(self, project_id: str) -> object:
            return SimpleNamespace(root=tmp_path, project_id=project_id)

    class Jobs:
        store = SimpleNamespace(root=tmp_path)

    return CampaignRunner(
        projects=Projects(),
        jobs=Jobs(),
        workspaces=None,
        plans=None,
        native_runner=None,
    )


def test_advance_dispatches_each_lanes_next_action(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """One call per lane, from the same facts `campaign view` reads.

    Anti-vacuity: dropping a branch of `_dispatch` leaves that scenario's
    lane out of `dispatched`, caught by the per-scenario assertion below.
    """
    from sinnixd.lane_facts import Pull

    runner = _runner(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        runner,
        "_dispatch_declared",
        lambda project_id, project, facts, operation, parameters: (
            calls.append((operation, facts.name)) or "job-1"
        ),
    )
    monkeypatch.setattr(
        runner,
        "_dispatch_publish",
        lambda project_id, project, facts: (
            calls.append(("publish", facts.name)) or "job-1"
        ),
    )
    monkeypatch.setattr(
        runner,
        "_launch_agent",
        lambda project_id, facts, prompt, *, label: (
            calls.append((label, facts.name)) or "job-1"
        ),
    )
    monkeypatch.setattr(
        runner,
        "_dispatch_retry",
        lambda facts: calls.append(("retry", facts.name)) or "job-1",
    )
    monkeypatch.setattr(runner, "_repo_slug", staticmethod(lambda root: "o/r"))
    monkeypatch.setattr("sinnixd.lane_facts.closed_bead_ids", lambda root, **k: ())
    monkeypatch.setattr("sinnixd.lane_facts.latest_sweep_pulls", lambda root: {})

    scenarios = [
        (_lane_facts(), ("verify_affected", "packet-p-9")),
        (
            _lane_facts(verify_job=("vvvvvvvv-1", "succeeded")),
            ("harvest", "packet-p-9"),
        ),
        (_lane_facts(flagged_receipt=True), ("integrator", "packet-p-9")),
        (
            _lane_facts(
                clean_receipt=True,
                pull=Pull(number=7, head="h" * 40, verdict="conflict", findings=0),
            ),
            ("rebase", "packet-p-9"),
        ),
        (
            _lane_facts(
                clean_receipt=True,
                pull=Pull(number=7, head="h" * 40, verdict="findings", findings=2),
            ),
            ("review-fix", "packet-p-9"),
        ),
        (
            _lane_facts(lane_phase="timed_out", receipt=None, lane_job="job-77"),
            ("retry", "packet-p-9"),
        ),
    ]
    for facts, expected in scenarios:
        calls.clear()
        monkeypatch.setattr(
            "sinnixd.lane_facts.collect", lambda *a, _facts=facts, **k: [_facts]
        )
        result = runner.advance("polylogue")
        assert calls == [expected], expected
        assert len(result["dispatched"]) == 1
        assert result["dispatched"][0]["workspace"] == "packet-p-9"
        assert result["dispatched"][0]["job_id"] == "job-1"
        assert result["skipped"] == []


def test_advance_reports_undispatchable_actions_as_skipped(
    tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """Anti-vacuity: a wait/idle/park action must never reach a dispatcher —
    routing it through `_dispatch` would raise for lack of a matching branch."""
    runner = _runner(tmp_path)
    monkeypatch.setattr("sinnixd.lane_facts.closed_bead_ids", lambda root, **k: ())
    monkeypatch.setattr("sinnixd.lane_facts.latest_sweep_pulls", lambda root: {})
    monkeypatch.setattr(
        "sinnixd.lane_facts.collect",
        lambda *a, **k: [_lane_facts(holder="integrator", clean_receipt=True)],
    )

    result = runner.advance("polylogue")

    assert result["dispatched"] == []
    assert result["skipped"] == [
        {
            "workspace": "packet-p-9",
            "action": "wait",
            "reason": "held by integrator",
        }
    ]


def test_a_dispatch_refusal_is_reported_not_raised(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Anti-vacuity: without the catch, one lane's refused dispatch would
    abort every other lane's turn in the same call."""
    runner = _runner(tmp_path)
    monkeypatch.setattr("sinnixd.lane_facts.closed_bead_ids", lambda root, **k: ())
    monkeypatch.setattr("sinnixd.lane_facts.latest_sweep_pulls", lambda root: {})
    monkeypatch.setattr("sinnixd.lane_facts.collect", lambda *a, **k: [_lane_facts()])

    def refuse(*args: object, **kwargs: object) -> str | None:
        raise ValueError("no matching workspace registered")

    monkeypatch.setattr(runner, "_dispatch_declared", refuse)

    result = runner.advance("polylogue")

    assert result["dispatched"] == []
    assert result["skipped"] == [
        {
            "workspace": "packet-p-9",
            "action": "verify",
            "reason": "no matching workspace registered",
        }
    ]


def test_dispatch_retry_needs_a_lane_job() -> None:
    """Anti-vacuity: without the guard a lane with no job to retry raises
    inside `retry_agent` instead of reporting nothing to dispatch."""
    from sinnixd.campaign import CampaignRunner

    runner = CampaignRunner(
        projects=None, jobs=None, workspaces=None, plans=None, native_runner=None
    )
    assert runner._dispatch_retry(_lane_facts(lane_job=None)) is None


def test_dispatch_publish_requires_lane_publication_text(tmp_path) -> None:
    """The worker contract requires the lane to write its own publication
    text; a lane that skipped it must not be published under text nobody
    wrote.

    Anti-vacuity: removing the file check publishes an unstaffed worktree's
    stale `.lane/title`.
    """
    from sinnixd.campaign import CampaignRunner

    runner = CampaignRunner(
        projects=None, jobs=None, workspaces=None, plans=None, native_runner=None
    )
    facts = _lane_facts(clean_receipt=True)
    assert runner._dispatch_publish("polylogue", None, facts) is None


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
