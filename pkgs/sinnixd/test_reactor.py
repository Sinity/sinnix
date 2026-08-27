from __future__ import annotations

import json
from pathlib import Path

from sinnixd.reactor import (
    CampaignBoard,
    CampaignReactor,
    LaneRecord,
    PullRequestRecord,
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


def test_review_dispatch_uses_the_checkout_path_as_the_workspace(
    tmp_path: Path,
) -> None:
    """A lane checkout has no name field; the workspace is its directory.

    Anti-vacuity: reading a "name" key instead leaves calls empty, which is how
    auto-review silently did nothing for every lane.
    """
    calls: list[tuple[str, str]] = []
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        review_dispatcher=lambda project, workspace: calls.append((project, workspace)),
    )
    record = LaneRecord(
        job_id="job-1",
        project="polylogue",
        phase="succeeded",
        checkout={"path": "/realm/worktrees/packet-polylogue-abcd"},
        completed_at=None,
        review_ready=True,
        updated_at="2026-08-27T00:00:00+00:00",
    )

    reactor._dispatch_review(record)
    reactor._dispatch_review(record)

    assert calls == [("polylogue", "packet-polylogue-abcd")]


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


def test_keeper_prune_keeps_records_of_dispatched_work(tmp_path: Path) -> None:
    """A dispatched-review record must outlive the keeper's pending-action prune.

    Anti-vacuity: pruning every non-refill key deletes the dedupe entry on the
    next tick, so the same lane is reviewed again on each restart.
    """
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
    )
    reactor._board.keeper["review:job-1"] = {
        "emitted_at": "2026-08-27T00:00:00+00:00",
        "backoff_seconds": 0,
        "next_eligible_at": "2026-08-27T00:00:00+00:00",
    }
    reactor._board.keeper["stale-action"] = {
        "emitted_at": "2026-08-27T00:00:00+00:00",
        "backoff_seconds": 0,
        "next_eligible_at": "2026-08-27T00:00:00+00:00",
    }

    reactor._emit_keeper()

    assert "review:job-1" in reactor._board.keeper
    assert "stale-action" not in reactor._board.keeper


def test_completed_review_dispatches_one_integrator(tmp_path: Path) -> None:
    """Judging a reviewed lane fans out instead of queueing on a coordinator.

    Anti-vacuity: dropping the keeper record dispatches a second integrator for
    the same review, and dropping the reaction dispatches none.
    """
    calls: list[tuple[str, str, str]] = []
    reactor = CampaignReactor(
        event_spool=tmp_path / "events.jsonl",
        board_path=tmp_path / "board.json",
        state_dir=tmp_path / "state",
        project_roots={"polylogue": tmp_path / "repo"},
        integration_dispatcher=lambda p, w, r: calls.append((p, w, r)),
    )
    event = {
        "kind": "harvest",
        "transition": "review-required",
        "project": "polylogue",
        "workspace_id": "worktree-abc",
        "receipt_ref": "sinnix://harvest/harvest-" + "0" * 32,
        "job_id": "job-9",
    }

    reactor._dispatch_integration(event)
    reactor._dispatch_integration(event)

    assert calls == [
        ("polylogue", "worktree-abc", "sinnix://harvest/harvest-" + "0" * 32)
    ]
