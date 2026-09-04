from pathlib import Path

from sinnixd import backpressure


def test_io_pressure_drains_pytest_without_pausing_agents(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        backpressure, "read_pressure", lambda _root: {"io_full_avg60": 30.0}
    )
    monkeypatch.setattr(
        backpressure.pueue,
        "groups_status",
        lambda: {"agent": "Running", "pytest": "Running", "normal": "Running"},
    )
    monkeypatch.setattr(backpressure.pueue, "pause", calls.append)

    result = backpressure.tick(spool=None, pressure_root=Path("unused"))

    assert calls == ["pytest"]
    assert result["group"] == "pytest"


def test_memory_pressure_closes_agent_admission_first(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        backpressure, "read_pressure", lambda _root: {"memory_full_avg60": 30.0}
    )
    monkeypatch.setattr(
        backpressure.pueue,
        "groups_status",
        lambda: {"agent": "Running", "pytest": "Running", "normal": "Running"},
    )
    monkeypatch.setattr(backpressure.pueue, "pause", calls.append)

    result = backpressure.tick(spool=None, pressure_root=Path("unused"))

    assert calls == ["agent"]
    assert result["group"] == "agent"
