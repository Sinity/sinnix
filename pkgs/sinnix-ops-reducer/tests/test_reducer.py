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
    assert healthy["state"]["agentctl"] == {"jobs": [], "truncated": False}
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
        agent_jobs_source=lambda: (_ for _ in ()).throw(RuntimeError("socket unavailable")),
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
    assert snapshot["state"]["agentctl"] == {"jobs": [], "truncated": False}
