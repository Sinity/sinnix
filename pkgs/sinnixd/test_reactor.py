from __future__ import annotations

import json
from pathlib import Path

import pytest
from sinnixd.reactor import CampaignReactor


class FakeBeadReleaser:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def release(self, bead_id: str, *, cwd: Path) -> tuple[bool, str | None]:
        self.calls.append((bead_id, cwd))
        return True, None


def test_under_filled_fleet_refills_on_the_keeper_tick_leaves_only(
    tmp_path: Path, monkeypatch
) -> None:
    """An under-filled fleet replenishes itself on the keeper tick — most
    lane exits (slices, rejections, timeouts) close no bead, and the old
    bead-close-only trigger starved the pool. Epic/milestone containers are
    never dispatched as lanes. Anti-vacuity: reverting the keeper-tick call
    leaves the dispatcher uncalled; dropping the container filter selects
    the epic."""
    import sinnixd.reactor as reactor_module

    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    project_root = tmp_path / "project"
    project_root.mkdir()
    dispatched: list[tuple[str, tuple[str, ...]]] = []
    reactor = CampaignReactor(
        spool,
        board_path,
        tmp_path / "reactor",
        project_roots={"polylogue": project_root},
        jobs_state_dir=tmp_path / "jobs",
        min_active_lanes=10,
        refill_width_target=12,
        refill_dispatcher=lambda project, beads: dispatched.append(
            (project, tuple(beads))
        ),
    )
    monkeypatch.setattr(
        reactor_module,
        "_active_lane_count",
        lambda *a, **k: reactor_module._ActiveLaneCount(1, 0),
    )

    class Reader:
        def ready(self):
            return [
                {"id": "polylogue-epic", "issue_type": "epic"},
                {"id": "polylogue-leaf", "issue_type": "task"},
            ]

    class Snapshot:
        def __init__(self, bead_id):
            self.group = bead_id
            self.bead_ids = (bead_id,)

            class Dimensions:
                conflict_keys = (f"file:{bead_id}",)

            self.dimensions = Dimensions()

    monkeypatch.setattr(reactor_module, "SubprocessBdReader", lambda root: Reader())
    monkeypatch.setattr(
        reactor_module.PacketConfig, "load", staticmethod(lambda root: object())
    )
    monkeypatch.setattr(
        reactor_module,
        "compile_launch_snapshot",
        lambda bead_id, **kw: Snapshot(bead_id),
    )
    monkeypatch.setattr(reactor_module, "_judgment_reason", lambda row, snap: None)

    reactor.run_once()

    assert dispatched, "keeper tick did not refill an under-filled fleet"
    project, beads = dispatched[0]
    assert project == "polylogue"
    assert "polylogue-leaf" in beads
    assert "polylogue-epic" not in beads


def test_a_failed_refill_wave_backs_off_like_a_launched_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: without the backoff a wave that fails on one bad packet
    is retried on every tick (one attempt per minute, 2026-09-01 22:23Z)."""
    import subprocess

    from sinnixd import reactor as reactor_module

    spool = tmp_path / "events.jsonl"
    project_root = tmp_path / "project"
    project_root.mkdir()

    def failing_dispatch(project: str, beads: tuple[str, ...]) -> None:
        raise subprocess.CalledProcessError(1, ["agentctl", "campaign", "run"])

    reactor = CampaignReactor(
        spool,
        tmp_path / "campaign-board.json",
        tmp_path / "reactor",
        project_roots={"polylogue": project_root},
        jobs_state_dir=tmp_path / "jobs",
        min_active_lanes=10,
        refill_width_target=12,
        refill_spacing_seconds=300,
        refill_dispatcher=failing_dispatch,
    )
    monkeypatch.setattr(
        reactor_module, "_active_lane_count", lambda *a, **k: reactor_module._ActiveLaneCount(1, 0)
    )

    class Reader:
        def ready(self):
            return [{"id": "polylogue-leaf", "issue_type": "task"}]

    class Snapshot:
        def __init__(self, bead_id):
            self.group = bead_id
            self.bead_ids = (bead_id,)

            class Dimensions:
                conflict_keys = (f"file:{bead_id}",)

            self.dimensions = Dimensions()

    monkeypatch.setattr(reactor_module, "SubprocessBdReader", lambda root: Reader())
    monkeypatch.setattr(reactor_module.PacketConfig, "load", staticmethod(lambda root: object()))
    monkeypatch.setattr(reactor_module, "compile_launch_snapshot", lambda bead_id, **kw: Snapshot(bead_id))
    monkeypatch.setattr(reactor_module, "_judgment_reason", lambda row, snap: None)

    reactor.run_once()

    record = reactor._board.keeper.get("refill:polylogue")
    assert record is not None and record["backoff_seconds"] >= 300
    assert any("refill polylogue" in e["message"] for e in reactor._board.errors)


def test_reconcile_releases_claims_whose_lane_died_unseen(tmp_path: Path) -> None:
    """Anti-vacuity: a claim released only from a terminal event the reactor
    saw stays parked after a reactor outage during a wave."""
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    for name, bead, phase, created in (
        ("dead", "polylogue-d1", "cancelled", "2026-09-01T21:00:00+00:00"),
        ("live", "polylogue-l1", "running", "2026-09-01T21:00:00+00:00"),
        ("done", "polylogue-s1", "succeeded", "2026-09-01T21:00:00+00:00"),
    ):
        (jobs / f"{name}.json").write_text(
            json.dumps(
                {
                    "job_id": name,
                    "created_at": created,
                    "spec": {
                        "kind": "attested-agent",
                        "contract": {"parameters": {"campaign": {"bead_ids": [bead]}}},
                    },
                    "state": {"phase": phase},
                }
            )
        )
    releaser = FakeBeadReleaser()
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        jobs_state_dir=jobs,
        project_roots={"polylogue": tmp_path / "repo"},
        bead_releaser=releaser,
    )

    class Reader:
        def list(self):
            return [
                {"id": "polylogue-d1", "status": "in_progress", "assignee": "campaign"},
                {"id": "polylogue-l1", "status": "in_progress", "assignee": "campaign"},
                {"id": "polylogue-s1", "status": "in_progress", "assignee": "campaign"},
                {"id": "polylogue-o1", "status": "in_progress", "assignee": "sinity"},
            ]

    reactor._reconcile_claims("polylogue", tmp_path / "repo", Reader())

    assert releaser.calls == [("polylogue-d1", tmp_path / "repo")]


def test_refill_waits_for_a_pending_corpus_run(tmp_path: Path) -> None:
    """Anti-vacuity: lanes launched beside the corpus run turned its
    failures into load noise (2026-09-02)."""
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "corpus.json").write_text(
        json.dumps(
            {
                "job_id": "corpus",
                "spec": {"kind": "declared-operation", "operation": "verify_all", "project_id": "polylogue"},
                "state": {"phase": "queued", "terminal": False},
            }
        )
    )
    launched: list[str] = []
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        jobs_state_dir=jobs,
        project_roots={"polylogue": tmp_path / "repo"},
        refill_width_target=2,
        refill_dispatcher=lambda project, beads: launched.append(project),
    )

    reactor._dispatch_refill("polylogue")
    assert launched == []

    (jobs / "corpus.json").write_text(
        json.dumps(
            {
                "job_id": "corpus",
                "spec": {"kind": "declared-operation", "operation": "verify_all", "project_id": "polylogue"},
                "state": {"phase": "succeeded", "terminal": True},
            }
        )
    )
    assert reactor._corpus_pending("polylogue") is False


def _lane_facts(**overrides: object) -> object:
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
            packet_id="harvest-" + "0" * 32, head="h" * 40, flags=(), flagged=False, authorized=False,
            verification="from-job", bead="polylogue-9", created_at="",
        )
    if overrides.pop("flagged_receipt", False):
        base["receipt"] = Receipt(
            packet_id="harvest-" + "1" * 32, head="h" * 40, flags=("FLAG: production definitions removed: f",),
            flagged=True, authorized=False, verification="from-job", bead="polylogue-9", created_at="",
        )
    base.update(overrides)
    return LaneFacts(**base)  # type: ignore[arg-type]


def test_the_reactor_advances_each_lane_from_its_facts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: with keyed reactions an unforeseen edge (master moving
    again, a lane writing no text) stalled until a new key existed; here the
    same facts always produce the same action and nothing is remembered."""
    calls: list[tuple[str, ...]] = []
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        jobs_state_dir=tmp_path / "state" / "jobs",
        project_roots={"polylogue": tmp_path / "repo"},
        verify_dispatcher=lambda p, w: calls.append(("verify", w)) or "v-job",
        harvest_dispatcher=lambda p, w, ref: calls.append(("harvest", w, ref)),
        integration_dispatcher=lambda p, w, label: calls.append(("agent", w, label)),
    )
    monkeypatch.setattr(CampaignReactor, "_publish", lambda self, p, w, receipt, affected_job="": calls.append(("publish", w, receipt)))
    monkeypatch.setattr(CampaignReactor, "_repo_slug", lambda self, project: "o/r")
    monkeypatch.setattr(CampaignReactor, "_closed_beads", lambda self, project, root: ())
    from sinnixd.lane_facts import Pull

    scenarios = [
        (_lane_facts(), ("verify", "packet-p-9")),
        (_lane_facts(verify_job=("vvvvvvvv-1", "succeeded")), ("harvest", "packet-p-9", "vvvvvvvv-1")),
        (_lane_facts(clean_receipt=True), ("publish", "packet-p-9", "harvest-" + "0" * 32)),
        (_lane_facts(flagged_receipt=True), ("agent", "packet-p-9", "integrator")),
        (_lane_facts(clean_receipt=True, pull=Pull(number=7, head="h" * 40, verdict="conflict", findings=0)), ("agent", "packet-p-9", "rebase")),
        (_lane_facts(clean_receipt=True, pull=Pull(number=7, head="h" * 40, verdict="findings", findings=2)), ("agent", "packet-p-9", "review-fix")),
    ]
    for facts, expected in scenarios:
        calls.clear()
        monkeypatch.setattr("sinnixd.lane_facts.collect", lambda *a, _facts=facts, **k: [_facts])
        monkeypatch.setattr("sinnixd.lane_facts.latest_sweep_pulls", lambda root: {})
        reactor._advance_lanes("polylogue")
        assert calls == [expected], expected

    # Held or busy lanes are left alone; a parked lane is recorded once per head.
    calls.clear()
    monkeypatch.setattr("sinnixd.lane_facts.collect", lambda *a, **k: [_lane_facts(holder="integrator", clean_receipt=True)])
    reactor._advance_lanes("polylogue")
    assert calls == []
    parked = _lane_facts(flagged_receipt=True, integrators_at_head=("integrator",))
    monkeypatch.setattr("sinnixd.lane_facts.collect", lambda *a, **k: [parked])
    reactor._advance_lanes("polylogue")
    reactor._advance_lanes("polylogue")
    judged = [key for key in reactor._board.keeper if key.startswith("judged:")]
    assert judged == ["judged:packet-p-9:" + "h" * 12]
    assert calls == []


def test_a_retry_action_re_dispatches_the_lane_job_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: without the retry branch the action only spooled an
    event, and two interrupted workspaces emitted 65 no-op dispatches each in
    three days (2026-09-02)."""
    retried: list[str] = []
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        jobs_state_dir=tmp_path / "state" / "jobs",
        project_roots={"polylogue": tmp_path / "repo"},
        retry_dispatcher=retried.append,
    )
    monkeypatch.setattr(CampaignReactor, "_closed_beads", lambda self, project, root: ())
    facts = _lane_facts(lane_phase="timed_out", lane_job="job-77")
    monkeypatch.setattr("sinnixd.lane_facts.collect", lambda *a, _facts=facts, **k: [_facts])
    monkeypatch.setattr("sinnixd.lane_facts.latest_sweep_pulls", lambda root: {})

    reactor._advance_lanes("polylogue")
    reactor._advance_lanes("polylogue")

    assert retried == ["job-77"]
