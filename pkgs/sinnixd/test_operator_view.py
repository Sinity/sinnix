from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sinnixd.operator_view import checks, load_jobs, render_lane_log, render_overview

NOW = datetime(2026, 9, 2, 16, 0, tzinfo=UTC)


def _job(
    job_id: str,
    operation: str,
    phase: str,
    workspace: str,
    minutes_ago: int,
    *,
    terminal: bool = False,
) -> dict:
    created = (NOW - timedelta(minutes=minutes_ago)).isoformat()
    return {
        "job_id": job_id,
        "created_at": created,
        "spec": {
            "project_id": "polylogue",
            "kind": "declared-operation",
            "operation": operation,
            "checkout": {"path": f"/realm/worktrees/{workspace}"},
        },
        "state": {
            "phase": phase,
            "terminal": terminal,
            "observed_at": NOW.isoformat(),
            "blocked_by": ["pool-workers"],
        },
    }


STATUS = {
    "project_id": "polylogue",
    "master_corpus": {
        "green": False,
        "red": 398,
        "passed": 20654,
        "head": "966b7e0fb065",
        "finished_at": (NOW - timedelta(minutes=10)).isoformat(),
        "job_id": "4f98e6cc",
    },
    "lanes_next": [
        {
            "workspace": "packet-polylogue-a",
            "bead": "polylogue-a",
            "next": {"kind": "park", "reason": "CI red on the PR"},
            "pr": {"number": 7, "verdict": "ci-red"},
            "receipt": {"flags": ["FLAG: x"]},
        },
        {
            "workspace": "packet-polylogue-b",
            "bead": "polylogue-b",
            "next": {"kind": "verify", "reason": "no receipt at head"},
        },
        {
            "workspace": "packet-polylogue-c",
            "bead": None,
            "next": {"kind": "idle", "reason": "dormant workspace"},
        },
    ],
    "errors": [],
}


def test_checks_name_every_stuck_thing_and_nothing_else() -> None:
    """Anti-vacuity: each check has one fixture that trips it and one that does not."""
    jobs = [
        _job("11111111", "verify_affected", "queued", "packet-polylogue-b", 25),
        _job("22222222", "harvest", "running", "packet-polylogue-a", 45),
        _job("33333333", "verify_quick", "running", "packet-polylogue-a", 3),
    ]
    problems = checks(STATUS, jobs, now=NOW)
    assert any("master corpus is RED: 398" in p for p in problems)
    assert any("verify_affected packet-polylogue-b queued 25m" in p for p in problems)
    assert any("harvest packet-polylogue-a running 45m" in p for p in problems)
    assert not any("verify_quick" in p for p in problems)
    assert any("packet-polylogue-a PARKED" in p for p in problems)
    quiet = checks(
        {
            **STATUS,
            "master_corpus": {
                "green": True,
                "red": 0,
                "passed": 1,
                "head": "x",
                "finished_at": NOW.isoformat(),
            },
            "lanes_next": [],
        },
        [],
        now=NOW,
    )
    assert quiet == []


def test_overview_orders_lanes_by_urgency_and_hides_idle() -> None:
    text = render_overview(STATUS, [], now=NOW)
    assert text.index("packet-polylogue-a") < text.index("packet-polylogue-b")
    assert "1 idle/done: packet-polylogue-c" in text
    assert "PR 7 ci-red 1 flags" in text
    ghost = _job("99999999", "harvest", "capacity", "packet-polylogue-old", 60 * 48)
    text = render_overview(STATUS, [ghost], now=NOW)
    assert "0 active, 1 ghosts older than a day" in text


def test_lane_log_lists_jobs_and_events_in_time_order(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"
    spool.write_text(
        json.dumps(
            {
                "kind": "dispatch",
                "emitted_at": (NOW - timedelta(minutes=30)).isoformat(),
                "workspace": "packet-polylogue-a",
                "action": "verify",
                "reason": "no receipt at head",
            }
        )
        + "\n"
    )
    jobs = [
        _job(
            "22222222",
            "verify_affected",
            "succeeded",
            "packet-polylogue-a",
            29,
            terminal=True,
        ),
        _job("44444444", "harvest", "running", "packet-polylogue-a", 5),
        _job("55555555", "harvest", "running", "packet-polylogue-zzz", 5),
    ]
    text = render_lane_log("packet-polylogue-a", STATUS, jobs, spool, now=NOW)
    assert "next: park — CI red on the PR" in text
    body = text.split("== timeline")[1]
    assert (
        body.index("dispatch") < body.index("verify_affected") < body.index("harvest")
    )
    assert "zzz" not in text and "… running for 5m" in text


def test_load_jobs_filters_by_project(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(
        json.dumps(_job("a", "harvest", "running", "w", 1))
    )
    other = _job("b", "harvest", "running", "w", 1)
    other["spec"]["project_id"] = "sinex"
    (tmp_path / "b.json").write_text(json.dumps(other))
    (tmp_path / "c.json").write_text("{not json")
    assert [j["job_id"] for j in load_jobs(tmp_path, "polylogue")] == ["a"]
