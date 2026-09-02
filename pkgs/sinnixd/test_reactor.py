from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sinnixd.reactor import (
    CampaignBoard,
    CampaignReactor,
    LaneRecord,
    PullRequestRecord,
    _now,
    event_main,
)


class FakeBeadCloser:
    def __init__(self, result: tuple[bool, str | None] = (True, None)) -> None:
        self.result = result
        self.calls: list[tuple[str, str, Path]] = []

    def close(self, bead_id: str, reason: str, *, cwd: Path) -> tuple[bool, str | None]:
        self.calls.append((bead_id, reason, cwd))
        return self.result


def append(path: Path, event: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def lane_event(job_id: str = "lane-1") -> dict[str, object]:
    return {
        "kind": "attested-agent",
        "job_id": job_id,
        "project": "polylogue",
        "phase": "succeeded",
        "completed_at": "2026-08-26T12:00:00+00:00",
        "checkout": {"path": f"/realm/worktrees/{job_id}"},
    }


def test_lane_success_is_externalized_as_review_ready_and_is_idempotent(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a failed success reaction must not wake review from board state."""
    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    closer = FakeBeadCloser()
    reactor = CampaignReactor(
        spool, board_path, tmp_path / "reactor", bead_closer=closer
    )
    append(spool, lane_event())

    assert reactor.run_once() == 1
    # The first drain emits one keeper event; the second drain consumes that
    # already-emitted advisory but must not emit another one.
    assert reactor.run_once() == 1

    board = json.loads(board_path.read_text())
    assert board["schema_version"] == 1
    assert board["lanes"]["lane-1"]["review_ready"] is True
    assert board["lanes"]["lane-1"]["checkout"]["path"] == "/realm/worktrees/lane-1"
    assert (
        len(
            [
                line
                for line in spool.read_text().splitlines()
                if '"kind":"keeper"' in line
            ]
        )
        == 1
    )


def test_merge_reaction_closes_from_immutable_decision_receipt(tmp_path: Path) -> None:
    """Anti-vacuity: changing a reason file after the event cannot change the close argument."""
    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    project_root = tmp_path / "polylogue"
    project_root.mkdir()
    closer = FakeBeadCloser()
    reactor = CampaignReactor(
        spool,
        board_path,
        tmp_path / "reactor",
        project_roots={"polylogue": project_root},
        bead_closer=closer,
    )
    append(
        spool,
        {
            "schema_version": 1,
            "kind": "merge_close",
            "repo": "Sinity/polylogue",
            "pr": "42",
            "state": "MERGED",
            "decision_receipt": {
                "receipt_id": "receipt-42",
                "bead_id": "polylogue-abc",
                "reason": "landed by verified reactor test",
            },
        },
    )

    assert reactor.run_once() == 1
    assert closer.calls == [
        ("polylogue-abc", "landed by verified reactor test", project_root)
    ]
    board = CampaignBoard.load(board_path)
    pr = board.prs["Sinity/polylogue#42"]
    assert isinstance(pr, PullRequestRecord)
    assert pr.bead_close_status == "closed"
    assert pr.decision_receipt["receipt_id"] == "receipt-42"


def test_merge_reaction_uses_needs_merge_receipt_when_merge_event_has_none(
    tmp_path: Path,
) -> None:
    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    project_root = tmp_path / "polylogue"
    project_root.mkdir()
    closer = FakeBeadCloser()
    reactor = CampaignReactor(
        spool,
        board_path,
        tmp_path / "reactor",
        project_roots={"polylogue": project_root},
        bead_closer=closer,
    )
    append(
        spool,
        {
            "kind": "needs-merge",
            "repo": "Sinity/polylogue",
            "project": "polylogue",
            "pr": "43",
            "state": "NEEDS-MERGE",
            "decision_receipt": {
                "receipt_id": "receipt-43",
                "bead_id": "polylogue-abc",
                "reason": "merged by reactor",
            },
        },
    )
    append(
        spool,
        {
            "kind": "merge_close",
            "repo": "Sinity/polylogue",
            "project": "polylogue",
            "pr": "43",
            "state": "MERGED",
        },
    )

    assert reactor.run_once() == 2
    assert closer.calls == [("polylogue-abc", "merged by reactor", project_root)]
    assert (
        CampaignBoard.load(board_path).prs["Sinity/polylogue#43"].bead_close_status
        == "closed"
    )


def test_merged_without_receipt_is_actionable_and_keeper_backoff_is_bounded(
    tmp_path: Path,
) -> None:
    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    reactor = CampaignReactor(
        spool,
        board_path,
        tmp_path / "reactor",
        keeper_backoff_seconds=2,
        max_keeper_backoff_seconds=3,
    )
    append(
        spool,
        {
            "kind": "merge_close",
            "repo": "Sinity/polylogue",
            "pr": "7",
            "state": "MERGED",
        },
    )

    reactor.run_once()
    first_keeper_count = sum(
        '"kind":"keeper"' in line for line in spool.read_text().splitlines()
    )
    reactor.run_once()
    second_keeper_count = sum(
        '"kind":"keeper"' in line for line in spool.read_text().splitlines()
    )

    assert first_keeper_count == 1
    assert second_keeper_count == 1
    board = CampaignBoard.load(board_path)
    assert board.prs["Sinity/polylogue#7"].bead_close_status == "missing-receipt"
    assert board.keeper["bead-close"]["backoff_seconds"] == 3


def test_old_open_pr_emits_needs_merge_with_checks_and_auto_merge_state(
    tmp_path: Path,
) -> None:
    spool = tmp_path / "events.jsonl"
    reactor = CampaignReactor(
        spool,
        tmp_path / "campaign-board.json",
        tmp_path / "reactor",
        pr_age_threshold_seconds=60,
    )
    append(
        spool,
        {
            "kind": "merge_close",
            "repo": "Sinity/polylogue",
            "pr": "4447",
            "state": "OPEN",
            "opened_at": "2026-08-30T18:00:00+00:00",
            "check_states": ["ci/failing", "lint/queued"],
            "auto_merge": False,
        },
    )

    reactor.run_once()
    events = [json.loads(line) for line in spool.read_text().splitlines()]
    keeper = [event for event in events if event.get("kind") == "keeper"]

    assert len(keeper) == 1
    assert keeper[0]["reasons"] == ["needs-merge"]
    assert keeper[0]["actions"] == [
        "needs-merge Sinity/polylogue#4447 checks=ci/failing,lint/queued auto-merge=unarmed"
    ]


def test_recent_open_pr_does_not_emit_needs_merge(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"
    reactor = CampaignReactor(
        spool,
        tmp_path / "campaign-board.json",
        tmp_path / "reactor",
        pr_age_threshold_seconds=60 * 60,
    )
    append(
        spool,
        {
            "kind": "merge_close",
            "repo": "Sinity/polylogue",
            "pr": "4448",
            "state": "OPEN",
            "opened_at": "2999-01-01T00:00:00+00:00",
            "check_states": [],
            "auto_merge": True,
        },
    )

    reactor.run_once()

    assert '"kind":"keeper"' not in spool.read_text()


def test_malformed_spool_line_is_recorded_and_does_not_block_following_events(
    tmp_path: Path,
) -> None:
    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    reactor = CampaignReactor(spool, board_path, tmp_path / "reactor")
    spool.write_text("not-json\n")
    append(spool, lane_event("lane-2"))

    assert reactor.run_once() == 2

    board = CampaignBoard.load(board_path)
    assert board.errors[0]["offset"] == "0"
    assert board.lanes["lane-2"].review_ready


def test_lane_terminal_accepts_a_checkout_id_string(tmp_path: Path) -> None:
    """Lane terminals name their checkout by id, not as an object.

    Anti-vacuity: requiring a Mapping raises on every real lane terminal, which
    is how review-ready stopped being set for any lane at all.
    """
    record = LaneRecord.from_event(
        {
            "kind": "attested-agent",
            "job_id": "job-1",
            "project": "polylogue",
            "phase": "succeeded",
            "checkout": "worktree-e6db0b7b054333fd",
        },
        updated_at="2026-08-27T00:00:00+00:00",
    )

    assert record.review_ready is True
    assert record.checkout == {"checkout_id": "worktree-e6db0b7b054333fd"}


def test_workspace_resolves_from_the_durable_job_record(tmp_path: Path) -> None:
    """The path lives in the job record when the event carried only an id.

    Anti-vacuity: dropping the record lookup returns "" and no review is ever
    dispatched for a lane terminal.
    """
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "job-1.json").write_text(
        json.dumps({"checkout": {"path": "/realm/worktrees/packet-polylogue-wxyz"}})
    )
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        jobs_state_dir=jobs,
    )
    record = LaneRecord(
        job_id="job-1",
        project="polylogue",
        phase="succeeded",
        checkout={"checkout_id": "worktree-abc"},
        completed_at=None,
        review_ready=True,
        updated_at="2026-08-27T00:00:00+00:00",
    )

    assert reactor._workspace_for(record) == "packet-polylogue-wxyz"


def test_verify_all_failure_streak_alerts_once_and_preserves_typed_reasons(
    tmp_path: Path,
) -> None:
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    phases = ("failed", "cancelled", "timed_out")
    for index, phase in enumerate(phases):
        state: dict[str, object] = {
            "phase": phase,
            "terminal": True,
            "observed_at": f"2026-08-2{index + 7}T00:00:00+00:00",
        }
        if phase == "cancelled":
            state["cancellation"] = {
                "reason": "operator-request",
                "invocation_id": "invocation-2",
            }
        (jobs / f"verify-{index}.json").write_text(
            json.dumps(
                {
                    "job_id": f"verify-{index}",
                    "created_at": f"2026-08-2{index + 7}T00:00:00+00:00",
                    "spec": {
                        "kind": "declared-operation",
                        "project_id": "polylogue",
                        "operation": "verify_all",
                    },
                    "state": state,
                }
            )
        )
    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    reactor = CampaignReactor(
        spool,
        board_path,
        tmp_path / "reactor",
        jobs_state_dir=jobs,
    )

    reactor.run_once()
    events = [json.loads(line) for line in spool.read_text().splitlines()]
    alerts = [event for event in events if event.get("kind") == "corpus-health-alert"]
    assert len(alerts) == 1
    assert alerts[0]["consecutive_failures"] == 3
    assert [item["phase"] for item in alerts[0]["failures"]] == list(phases)
    assert alerts[0]["failures"][1]["cancellation"]["reason"] == "operator-request"
    board = CampaignBoard.load(board_path)
    assert board.corpus_health["status"] == "alerting"
    assert board.corpus_health["alert_event_id"] == alerts[0]["event_id"]

    reactor.run_once()
    events = [json.loads(line) for line in spool.read_text().splitlines()]
    assert (
        len([event for event in events if event.get("kind") == "corpus-health-alert"])
        == 1
    )

    (jobs / "verify-success.json").write_text(
        json.dumps(
            {
                "job_id": "verify-success",
                "created_at": "2026-08-30T00:00:00+00:00",
                "spec": {
                    "kind": "declared-operation",
                    "project_id": "polylogue",
                    "operation": "verify_all",
                },
                "state": {"phase": "succeeded", "terminal": True},
            }
        )
    )
    reactor.run_once()
    assert CampaignBoard.load(board_path).corpus_health["status"] == "healthy"


class FakeBeadReleaser:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def release(self, bead_id: str, *, cwd: Path) -> tuple[bool, str | None]:
        self.calls.append((bead_id, cwd))
        return True, None


def test_interrupted_lane_releases_its_claimed_beads(tmp_path: Path) -> None:
    """A lane that never reached a result must not keep its bead parked.

    Anti-vacuity: without the release a cancelled lane's bead stays
    in_progress under the campaign's claim and no later wave can take it.
    """
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "lane-9.json").write_text(
        json.dumps(
            {
                "job_id": "lane-9",
                "spec": {
                    "kind": "attested-agent",
                    "contract": {
                        "parameters": {"campaign": {"bead_ids": ["polylogue-q1"]}}
                    },
                },
            }
        )
    )
    releaser = FakeBeadReleaser()
    spool = tmp_path / "events.jsonl"
    reactor = CampaignReactor(
        event_spool=spool,
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        jobs_state_dir=jobs,
        project_roots={"polylogue": tmp_path / "repo"},
        bead_releaser=releaser,
        retry_dispatcher=lambda _job: None,
    )
    append(
        spool,
        {
            "kind": "attested-agent",
            "job_id": "lane-9",
            "project": "polylogue",
            "phase": "cancelled",
            "reason": "operator-cancel",
            "completed_at": "2026-09-01T21:00:00+00:00",
            "checkout": {"checkout_id": "worktree-q"},
        },
    )

    reactor.run_once()

    assert releaser.calls == [("polylogue-q1", tmp_path / "repo")]


class FakeBeadParker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def park(self, bead_id: str, note: str, *, cwd: Path) -> tuple[bool, str | None]:
        self.calls.append((bead_id, note))
        return True, None


def test_heavy_operation_is_deferred_while_a_lane_is_active(tmp_path: Path) -> None:
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "lane.json").write_text(
        json.dumps(
            {
                "spec": {"kind": "attested-agent", "project_id": "polylogue"},
                "state": {"phase": "running", "terminal": False},
            }
        )
    )
    calls: list[tuple[str, str, dict[str, object]]] = []
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        jobs_state_dir=jobs,
        operation_dispatcher=lambda project, operation, parameters: calls.append(
            (project, operation, dict(parameters))
        ),
    )
    append(
        tmp_path / "events.jsonl",
        {
            "kind": "operation-request",
            "request_id": "verify-1",
            "project": "polylogue",
            "operation": "verify_all",
            "parameters": {"mode": "full"},
            "requested_at": "2026-08-31T00:00:00+00:00",
        },
    )

    assert reactor.run_once() == 1
    assert calls == []
    board = CampaignBoard.load(tmp_path / "board.json")
    assert board.pending_operations["verify-1"]["active_lanes"] == 1
    assert "active lanes 1" in board.pending_operations["verify-1"]["last_reason"]
    assert board.keeper["operation:verify-1"]
    assert "cancel" not in (tmp_path / "events.jsonl").read_text().lower()


def test_deferred_heavy_operation_dispatches_after_gate_clears(tmp_path: Path) -> None:
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    lane = jobs / "lane.json"
    lane.write_text(
        json.dumps(
            {
                "spec": {"kind": "attested-agent", "project_id": "polylogue"},
                "state": {"phase": "running", "terminal": False},
            }
        )
    )
    calls: list[tuple[str, str, dict[str, object]]] = []
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        jobs_state_dir=jobs,
        operation_dispatcher=lambda project, operation, parameters: calls.append(
            (project, operation, dict(parameters))
        ),
    )
    append(
        tmp_path / "events.jsonl",
        {
            "kind": "operation-request",
            "request_id": "verify-2",
            "project": "polylogue",
            "operation": "rehearsal",
            "parameters": {},
        },
    )
    reactor.run_once()
    assert calls == []

    lane.write_text(
        json.dumps(
            {
                "spec": {"kind": "attested-agent", "project_id": "polylogue"},
                "state": {"phase": "succeeded", "terminal": True},
            }
        )
    )
    reactor._board.keeper["operation:verify-2"]["next_eligible_at"] = (
        "2026-08-30T00:00:00+00:00"
    )

    assert reactor.run_once() == 1
    assert calls == [("polylogue", "rehearsal", {})]
    board = CampaignBoard.load(tmp_path / "board.json")
    assert "verify-2" not in board.pending_operations


def test_interrupted_lane_is_retried_exactly_once(tmp_path: Path) -> None:
    """A cancelled lane re-dispatches from its preserved prompt, once."""
    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    retried: list[str] = []
    reactor = CampaignReactor(
        spool,
        board_path,
        tmp_path / "reactor",
        bead_closer=FakeBeadCloser(),
        retry_dispatcher=retried.append,
    )
    event = {
        "kind": "attested-agent",
        "job_id": "lane-cancelled-1",
        "project": "polylogue",
        "phase": "cancelled",
        "checkout": "worktree-0000000000000001",
    }
    append(spool, event)
    append(spool, event)
    reactor.run_once()
    assert retried == ["lane-cancelled-1"]


def test_closed_bead_disposes_its_packet_workspace(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"
    board_path = tmp_path / "campaign-board.json"
    disposed: list[str] = []
    reactor = CampaignReactor(
        spool,
        board_path,
        tmp_path / "reactor",
        bead_closer=FakeBeadCloser(),
        dispose_dispatcher=disposed.append,
    )
    append(
        spool,
        {
            "kind": "merge_close",
            "repo": "Sinity/polylogue",
            "pr": "77",
            "state": "MERGED",
            "bead_closed": True,
            "project": "polylogue",
            "decision_receipt": {"bead_id": "polylogue-zzz9", "reason": "done"},
        },
    )
    reactor.run_once()
    assert disposed == ["packet-polylogue-zzz9"]


def test_failure_event_reaches_the_shared_spool(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"

    assert (
        event_main(
            [
                "--event-spool",
                str(spool),
                "--unit",
                "sinnixd-reactor.service",
                "--result",
                "exit-code",
            ]
        )
        == 0
    )

    event = json.loads(spool.read_text().strip())
    assert event["schema_version"] == 1
    assert event["kind"] == "service_failure"
    assert event["unit"] == "sinnixd-reactor.service"
    assert event["result"] == "exit-code"
    assert event["event_id"]


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
    # One terminal lane on the board, one active job: under-filled.
    append(
        spool,
        {
            "kind": "attested-agent",
            "job_id": "lane-1",
            "project": "polylogue",
            "phase": "succeeded",
        },
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
    append(
        spool,
        {"kind": "attested-agent", "job_id": "lane-1", "project": "polylogue", "phase": "succeeded"},
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
            verification="tests-run", bead="polylogue-9", created_at="",
        )
    if overrides.pop("flagged_receipt", False):
        base["receipt"] = Receipt(
            packet_id="harvest-" + "1" * 32, head="h" * 40, flags=("FLAG: production definitions removed: f",),
            flagged=True, authorized=False, verification="tests-run", bead="polylogue-9", created_at="",
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
    monkeypatch.setattr(CampaignReactor, "_publish", lambda self, p, w, receipt: calls.append(("publish", w, receipt)))
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
        monkeypatch.setattr("sinnixd.lane_facts.collect", lambda *a, **k: [facts])
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
