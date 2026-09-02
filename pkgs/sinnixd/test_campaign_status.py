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


def test_status_infers_the_single_coordinator_label_and_digests_admission() -> None:
    result = build_campaign_status(
        "sinnix",
        [job("run", "sinnix", "running", terminal=False)],
        CampaignBoard(),
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
    assert result["coordinator_label"] == "desk"
    assert result["admission"]["head_of_queue"]["job_id"] == "queue"
    assert result["admission"]["budget"]["normal"] == {
        "budget_bytes": 80,
        "occupied": 1,
    }


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
