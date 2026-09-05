import json
from pathlib import Path

from agentctl import backpressure


def _spool(tmp_path: Path, *events: dict) -> Path:
    spool = tmp_path / "events.jsonl"
    spool.write_text(
        "".join(
            json.dumps({"kind": "backpressure", **event}) + "\n" for event in events
        )
    )
    return spool


def _tick(monkeypatch, pressure, groups, spool=None):
    calls = []
    monkeypatch.setattr(backpressure, "read_pressure", lambda _root: pressure)
    monkeypatch.setattr(backpressure.pueue, "groups_status", lambda: groups)
    monkeypatch.setattr(
        backpressure.pueue, "pause", lambda group: calls.append(("pause", group))
    )
    monkeypatch.setattr(
        backpressure.pueue, "resume", lambda group: calls.append(("resume", group))
    )
    result = backpressure.tick(spool=spool, pressure_root=Path("unused"))
    return result, calls


def _ours(group: str) -> dict:
    return {"action": "closed", "group": group, "owner": backpressure.OWNER}


def test_agent_admission_reopens_under_pressure(monkeypatch, tmp_path) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 15.22, "memory_full_avg60": 1.92},
        {
            "agent": "Paused",
            "pytest": "Running",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=_spool(tmp_path, _ours("agent")),
    )

    assert calls == [("resume", "agent")]
    assert result["action"] == "opened"


def test_io_closure_stays_until_io_below_hysteresis(monkeypatch) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 15.0, "memory_full_avg60": 1.0},
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Running",
        },
    )

    assert calls == []
    assert result["action"] == "hold"


def test_io_closure_reopens_when_current_pressure_recovers(
    monkeypatch, tmp_path
) -> None:
    result, calls = _tick(
        monkeypatch,
        {
            "io_full_avg10": 2.0,
            "io_full_avg60": 30.0,
            "memory_full_avg10": 1.0,
            "memory_full_avg60": 1.0,
        },
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Paused",
        },
        spool=_spool(tmp_path, _ours("pytest"), _ours("bulk")),
    )

    assert calls == [("resume", "pytest")]
    assert result["action"] == "opened"


def test_memory_closure_stays_until_memory_below_hysteresis(monkeypatch) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 1.0, "memory_full_avg60": 15.0},
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Running",
        },
    )

    assert calls == []
    assert result["action"] == "hold"


def test_signal_transition_reopens_excluded_group_before_closing_another(
    monkeypatch, tmp_path
) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 30.0, "memory_full_avg60": 1.0},
        {
            "agent": "Paused",
            "pytest": "Running",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=_spool(tmp_path, _ours("agent")),
    )

    assert calls == [("resume", "agent")]
    assert result["group"] == "agent"


def test_pressure_closes_admission_without_stopping_tasks(monkeypatch) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 30.0, "memory_full_avg60": 1.0},
        {
            "agent": "Running",
            "pytest": "Running",
            "normal": "Running",
            "bulk": "Running",
        },
    )

    assert calls == [("pause", "pytest")]
    assert result["action"] == "closed"


def test_io_pressure_keeps_normal_admissible_after_pytest_is_paused(
    monkeypatch,
) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 30.0, "memory_full_avg60": 1.0},
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Running",
        },
    )

    assert calls == [("pause", "bulk")]
    assert result["action"] == "closed"


def test_memory_pressure_keeps_agent_admissible(monkeypatch) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 1.0, "memory_full_avg60": 30.0},
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Running",
        },
    )

    assert calls == [("pause", "normal")]
    assert result["action"] == "closed"


def test_memory_closure_continues_after_io_targets_are_closed(monkeypatch) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 30.0, "memory_full_avg60": 30.0},
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Paused",
        },
    )

    assert calls == [("pause", "normal")]
    assert result["signal"] == "io+memory"


def test_a_pause_event_names_its_owner_and_group(monkeypatch, tmp_path) -> None:
    spool = tmp_path / "events.jsonl"
    _tick(
        monkeypatch,
        {"io_full_avg60": 30.0, "memory_full_avg60": 1.0},
        {
            "agent": "Running",
            "pytest": "Running",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=spool,
    )

    events = [json.loads(line) for line in spool.read_text().splitlines()]
    assert [(e["owner"], e["group"], e["action"]) for e in events] == [
        ("agentctl", "pytest", "closed")
    ]


def test_an_operator_pause_is_not_resumed(monkeypatch, tmp_path) -> None:
    """`pueue pause -g agent` by hand leaves no event of ours; it stays paused."""
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 1.0, "memory_full_avg60": 1.0},
        {"agent": "Paused", "pytest": "Paused", "normal": "Running", "bulk": "Running"},
        spool=_spool(tmp_path, _ours("pytest")),
    )

    assert calls == [("resume", "pytest")]
    assert result["group"] == "pytest"

    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 1.0, "memory_full_avg60": 1.0},
        {
            "agent": "Paused",
            "pytest": "Running",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=_spool(
            tmp_path,
            _ours("pytest"),
            {"action": "opened", "group": "pytest", "owner": "agentctl"},
        ),
    )
    assert calls == []
    assert result["action"] == "hold"


def test_a_pause_someone_else_recorded_after_ours_is_theirs(
    monkeypatch, tmp_path
) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 1.0, "memory_full_avg60": 1.0},
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=_spool(
            tmp_path,
            _ours("pytest"),
            {"action": "opened", "group": "pytest", "owner": "agentctl"},
            {"action": "closed", "group": "pytest", "owner": "operator"},
        ),
    )

    assert calls == []
    assert result["action"] == "hold"
