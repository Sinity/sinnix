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


def test_unattributed_legacy_pause_is_not_reopened_until_all_signals_are_quiet(
    monkeypatch, tmp_path
) -> None:
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

    assert calls == []
    assert result["action"] == "hold"


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


def test_zero_avg10_is_current_recovery_not_a_stale_avg60_fallback(
    monkeypatch, tmp_path
) -> None:
    """Zero is valid PSI, so it must not select the older high average."""
    result, calls = _tick(
        monkeypatch,
        {
            "io_full_avg10": 0.0,
            "io_full_avg60": 30.0,
            "memory_full_avg10": 1.0,
            "memory_full_avg60": 1.0,
        },
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=_spool(tmp_path, _ours("pytest")),
    )

    assert calls == [("resume", "pytest")]
    assert result["action"] == "opened"


def test_checkpoint_round_trips_nonempty_legacy_holds(tmp_path) -> None:
    spool = tmp_path / "events.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    held = {
        "kind": "pool-hold",
        "action": "held",
        "task_id": 7,
        "held_at": "2026-09-11T03:17:00Z",
    }
    spool.write_text(json.dumps(held) + "\n")

    written = backpressure.event_state(spool, checkpoint=checkpoint)
    restored = backpressure.event_state(None, checkpoint=checkpoint)

    assert written.legacy_holds == {7: held}
    assert restored.legacy_holds == {7: held}


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

    assert calls == [("pause", "pytest")]
    assert result["group"] == "pytest"


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


def test_a_group_seen_running_after_our_pause_is_released_and_an_operator_repause_holds(
    monkeypatch, tmp_path
) -> None:
    """`pueue start -g X` by the operator after our pause, then their own
    `pueue pause -g X`: the second pause is theirs and stays."""
    spool = _spool(tmp_path, _ours("pytest"))
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 1.0, "memory_full_avg60": 1.0},
        {
            "agent": "Running",
            "pytest": "Running",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=spool,
    )
    assert calls == [] and result["action"] == "hold"
    events = [json.loads(line) for line in spool.read_text().splitlines()]
    assert [(e["action"], e["group"]) for e in events] == [
        ("closed", "pytest"),
        ("released", "pytest"),
    ]
    assert backpressure.paused_by_us(spool) == set()

    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 1.0, "memory_full_avg60": 1.0},
        {
            "agent": "Running",
            "pytest": "Paused",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=spool,
    )
    assert calls == [] and result["action"] == "hold"


def test_io_pressure_keeps_focused_tests_admissible(monkeypatch) -> None:
    """A long reader must not close the bounded test pool after closing bulk."""
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 60.0, "memory_full_avg60": 1.0},
        {"pytest": "Paused", "bulk": "Paused", "pytest-quick": "Running"},
    )
    assert calls == []
    assert result["action"] == "hold"


def test_old_io_pause_reopens_focused_tests_during_io_pressure(
    monkeypatch, tmp_path
) -> None:
    """The policy upgrade releases its own existing I/O-only closure."""
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 60.0, "memory_full_avg60": 1.0},
        {"pytest": "Paused", "bulk": "Paused", "pytest-quick": "Paused"},
        spool=_spool(tmp_path, _ours("pytest-quick")),
    )
    assert calls == []
    assert result["action"] == "hold"


def test_memory_pressure_still_closes_focused_tests(monkeypatch) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 60.0, "memory_full_avg60": 30.0},
        {
            "pytest": "Paused",
            "normal": "Paused",
            "bulk": "Paused",
            "pytest-quick": "Running",
        },
    )
    assert calls == [("pause", "pytest-quick")]
    assert result["action"] == "closed"


def test_operator_focused_test_pause_is_preserved_under_io_pressure(
    monkeypatch, tmp_path
) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 60.0, "memory_full_avg60": 1.0},
        {"pytest": "Paused", "bulk": "Paused", "pytest-quick": "Paused"},
        spool=_spool(
            tmp_path, {"action": "closed", "group": "pytest-quick", "owner": "operator"}
        ),
    )
    assert calls == []
    assert result["action"] == "hold"
