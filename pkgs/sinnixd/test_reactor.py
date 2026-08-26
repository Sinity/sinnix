from __future__ import annotations

import json
from pathlib import Path

from sinnixd.reactor import CampaignBoard, CampaignReactor, PullRequestRecord, event_main


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


def test_failure_event_reaches_the_shared_spool(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"

    assert event_main(
        [
            "--event-spool",
            str(spool),
            "--unit",
            "sinnixd-reactor.service",
            "--result",
            "exit-code",
        ]
    ) == 0

    event = json.loads(spool.read_text().strip())
    assert event["schema_version"] == 1
    assert event["kind"] == "service_failure"
    assert event["unit"] == "sinnixd-reactor.service"
    assert event["result"] == "exit-code"
    assert event["event_id"]
