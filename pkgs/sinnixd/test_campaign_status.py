from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sinnixd.campaign_status import build_campaign_status
from sinnixd.reactor import CampaignBoard


def job(
    job_id: str, project: str, phase: str, *, terminal: bool, label: str = "desk"
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "created_at": "2026-08-31T10:00:00+00:00",
        "spec": {
            "project_id": project,
            "checkout": {"path": f"/realm/worktrees/{job_id}"},
            "contract": {
                "coordinator_label": label,
                "parameters": {
                    "campaign": {"group": job_id, "bead_ids": [f"{project}-b1"]}
                },
            },
        },
        "state": {
            "phase": phase,
            "terminal": terminal,
            "admission": {"blocked_by": ["exclusive-key"]},
            "terminal_reason": "provider stopped the lane",
        },
    }


def test_status_groups_lanes_and_includes_same_label_across_projects() -> None:
    board = CampaignBoard()
    board.judgment_queue = [{"workspace": "packet-sinnix-b1", "owner": "coordinator"}]
    result = build_campaign_status(
        "sinnix",
        [
            job("run", "sinnix", "running", terminal=False),
            job("queue", "sinnix", "queued", terminal=False),
            job("wedged", "sinnix", "failed", terminal=True),
            job("other", "polylogue", "running", terminal=False),
            job(
                "different", "polylogue", "running", terminal=False, label="other-desk"
            ),
        ],
        board,
        {
            "host": {"budget_memory_bytes": 100, "occupied_memory_bytes": 40},
            "pools": {"normal": {"memory_budget_bytes": 80, "holders": [{}]}},
            "queue": [
                {
                    "job_id": "queue",
                    "pool": "normal",
                    "blocked_by": ["exclusive-key"],
                    "position": 1,
                }
            ],
        },
    )
    assert result["schema"] == "sinnix.agentctl.campaign-status.v1"
    assert [row["job_id"] for row in result["lanes"]["running"]] == ["run", "other"]
    assert result["lanes"]["queued"][0]["blocked_by"] == ["exclusive-key"]
    assert result["lanes"]["wedged"][0]["cause"] == "provider stopped the lane"
    assert result["harvest"]["queue_depth"] == 1
    assert result["admission"]["head_of_queue"]["job_id"] == "queue"


def test_status_drops_aged_errors_and_bounds_error_page() -> None:
    board = CampaignBoard()
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    board.errors = [
        {"offset": "1", "message": "old", "at": (now - timedelta(days=2)).isoformat()},
        {
            "offset": "2",
            "message": "fresh",
            "at": (now - timedelta(hours=1)).isoformat(),
        },
    ]
    result = build_campaign_status("sinnix", [], board, {}, now=now)
    assert [item["message"] for item in result["errors"]] == ["fresh"]
