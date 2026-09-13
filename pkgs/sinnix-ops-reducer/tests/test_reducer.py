from __future__ import annotations

import json
from pathlib import Path

from sinnix_ops_reducer.reducer import Reducer


def test_healthy_stale_missing_and_malformed_sources_are_distinct(
    tmp_path: Path,
) -> None:
    values = [
        {"report": 1},
        RuntimeError("stale"),
        RuntimeError("missing"),
        "malformed",
    ]

    def source():
        value = values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    reducer = Reducer(tmp_path / "status.json", tmp_path / "token", source)
    healthy = reducer.refresh()
    stale = reducer.refresh()
    missing = reducer.refresh()
    malformed = reducer.refresh()
    assert healthy["sources"]["sinnix-observe"]["status"] == "healthy"
    assert healthy["state"]["agentctl"] == {
        "groups": {},
        "jobs": [],
        "truncated": False,
    }
    assert stale["sources"]["sinnix-observe"]["status"] == "unavailable"
    assert missing["sources"]["sinnix-observe"]["degradation"] == "missing"
    assert (
        malformed["sources"]["sinnix-observe"]["degradation"]
        == "collector returned a non-object"
    )
    assert json.loads((tmp_path / "status.json").read_text())["sequence"] == 4
    assert [event["status"] for event in reducer.events] == ["healthy", "unavailable"]


def test_sequence_persists_and_events_are_bounded(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {},
        state_path,
    )
    reducer.refresh()
    assert json.loads(state_path.read_text())["sequence"] == 1
    resumed = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {},
        state_path,
    )
    assert resumed.sequence == 1
    resumed.refresh()
    assert resumed.sequence == 2
    assert resumed.events_since(0)[0]["sequence"] == 2


def test_agentctl_failure_degrades_only_the_job_source(tmp_path: Path) -> None:
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {"report": 1},
        agent_jobs_source=lambda: (_ for _ in ()).throw(
            RuntimeError("socket unavailable")
        ),
    )
    snapshot = reducer.refresh()
    assert snapshot["sources"]["sinnix-observe"]["status"] == "healthy"
    assert snapshot["sources"]["agentctl"] == {
        "status": "unavailable",
        "source": "agentctl",
        "observed_at": snapshot["observed_at"],
        "freshness": "unknown",
        "degradation": "socket unavailable",
    }
    assert snapshot["state"]["agentctl"] == {
        "groups": {},
        "jobs": [],
        "truncated": False,
    }


def test_job_plane_survives_into_reducer_state(tmp_path: Path) -> None:
    jobs = [
        {"job_id": number, "label": "p:op", "phase": "running"} for number in range(100)
    ]
    groups = {"agent": {"status": "Paused", "parallel": 4, "running": 1, "queued": 2}}
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {"report": 1},
        agent_jobs_source=lambda: {"groups": groups, "jobs": jobs, "truncated": True},
    )

    snapshot = reducer.refresh()

    assert snapshot["state"]["agentctl"] == {
        "groups": groups,
        "jobs": jobs,
        "truncated": True,
    }
    # A payload without groups is not a job-plane snapshot: the source
    # degrades rather than publishing half of one.
    partial = Reducer(
        tmp_path / "status2.json",
        tmp_path / "token",
        lambda: {"report": 1},
        agent_jobs_source=lambda: {"jobs": jobs, "truncated": False},
    ).refresh()
    assert partial["sources"]["agentctl"]["status"] == "unavailable"


def test_failed_observe_preserves_jobs_desktop_and_last_good_pressure(tmp_path):
    values = [{"live_pressure": {"memory": 12}}, RuntimeError("observer failed")]

    def source():
        value = values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    jobs = {"jobs": [{"job_id": 7}], "groups": {}, "truncated": False}
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        source,
        agent_jobs_source=lambda: jobs,
    )
    first = reducer.refresh()
    second = reducer.refresh()
    assert second["state"]["agentctl"] == jobs
    assert second["sections"]["agentctl"]["available"] is True
    assert second["state"]["hyprland_automation"] is not None
    assert second["state"]["live_pressure"] == {"memory": 12}
    assert second["sections"]["live_pressure"]["available"] is False
    assert (
        second["sections"]["live_pressure"]["observed_at"]
        == first["sections"]["live_pressure"]["observed_at"]
    )


def test_detailed_sections_only_run_on_request_and_keep_partial_health(tmp_path):
    calls = []

    def detail(section):
        calls.append(section)
        return {"generated_at": "fixture-time", "storage": {"mounts": []}}

    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {
            "live_pressure": {"memory": 12},
            "sections": {
                "systemd_units": {
                    "available": False,
                    "observed_at": None,
                    "degradation": "manager down",
                }
            },
        },
        section_source=detail,
    )
    snapshot = reducer.refresh()
    assert snapshot["sections"]["live_pressure"]["available"] is True
    assert snapshot["sections"]["systemd_units"]["available"] is False
    assert calls == []
    assert reducer.page_snapshot(("storage",))["state"]["storage"] == {"mounts": []}
    assert calls == ["storage"]
    assert "storage" not in reducer.snapshot()["state"]
