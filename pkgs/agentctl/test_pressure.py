"""Pressure ticks read paused and running groups from pueue on every pass."""

import json
from pathlib import Path

import pytest
from agentctl import pressure as pressure_pause

ORDER = pressure_pause.CLOSE_ORDER["memory"]
QUIET = {
    "io_full_avg10": 0.0,
    "io_full_avg60": 0.0,
    "memory_full_avg10": 0.0,
    "memory_full_avg60": 0.0,
}


def _tick(monkeypatch, pressure, groups, spool=None):
    calls = []
    monkeypatch.setattr(pressure_pause, "read_pressure", lambda _root: pressure)
    monkeypatch.setattr(pressure_pause.pueue, "groups_status", lambda: groups)
    monkeypatch.setattr(
        pressure_pause.pueue, "pause", lambda group: calls.append(("pause", group))
    )
    monkeypatch.setattr(
        pressure_pause.pueue, "resume", lambda group: calls.append(("resume", group))
    )
    result = pressure_pause.tick(spool=spool, pressure_root=Path("unused"))
    return result, calls


def _groups(**states: str) -> dict[str, str]:
    groups = dict.fromkeys(("agent", *ORDER), "Running")
    groups.update({name.replace("_", "-"): state for name, state in states.items()})
    return groups


@pytest.mark.parametrize("io", [26.0, 80.0])
def test_io_pressure_is_observation_without_blanket_admission_veto(monkeypatch, io):
    result, calls = _tick(
        monkeypatch,
        {**QUIET, "io_full_avg10": io, "io_full_avg60": io},
        _groups(),
    )
    assert calls == []
    assert result["action"] == "clear"
    assert result["io_full_avg60"] == io
    assert result["frozen"] == [] and result["signal"] is None


def test_a_pause_stays_closed_while_memory_is_unknown(monkeypatch):
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg10": 30.0, "io_full_avg60": 30.0},
        _groups(bulk="Paused"),
    )
    assert calls == []
    assert result["action"] == "unknown-pressure"


def test_a_paused_group_reopens_on_memory_recovery_in_close_order(monkeypatch):
    result, calls = _tick(
        monkeypatch,
        {**QUIET, "io_full_avg60": 30.0, "memory_full_avg10": 1.0},
        _groups(pytest="Paused", bulk="Paused"),
    )
    assert calls == [("resume", "pytest")]
    assert result["action"] == "opened" and result["group"] == "pytest"


def test_zero_avg10_is_current_recovery_not_a_stale_avg60_fallback(monkeypatch):
    """Zero is valid PSI, so it must not select the older high average."""
    result, calls = _tick(
        monkeypatch,
        {**QUIET, "io_full_avg60": 30.0, "memory_full_avg60": 30.0},
        _groups(pytest="Paused"),
    )
    assert calls == [("resume", "pytest")]
    assert result["action"] == "opened"


def test_a_group_outside_the_close_order_is_never_resumed(monkeypatch):
    result, calls = _tick(monkeypatch, QUIET, _groups(agent="Paused"))
    assert calls == []
    assert result["action"] == "clear" and result["frozen"] == []


def test_memory_closure_stays_until_memory_below_hysteresis(monkeypatch) -> None:
    result, calls = _tick(
        monkeypatch,
        {**QUIET, "memory_full_avg10": 15.0, "memory_full_avg60": 15.0},
        _groups(pytest="Paused"),
    )
    assert calls == []
    assert result["action"] == "hold" and result["frozen"] == ["pytest"]


def test_memory_pressure_closes_the_first_running_group_of_the_order(
    monkeypatch,
) -> None:
    result, calls = _tick(
        monkeypatch,
        {**QUIET, "memory_full_avg10": 30.0, "memory_full_avg60": 30.0},
        _groups(pytest_heavy="Paused"),
    )
    assert calls == [("pause", "pytest")]
    assert result["action"] == "closed" and result["group"] == "pytest"


def test_memory_closure_continues_through_the_order_and_keeps_agent_admissible(
    monkeypatch,
) -> None:
    pressure = {**QUIET, "memory_full_avg10": 30.0, "memory_full_avg60": 30.0}
    result, calls = _tick(
        monkeypatch, pressure, _groups(pytest_heavy="Paused", pytest="Paused")
    )
    assert calls == [("pause", "normal")]
    assert result["signal"] == "memory"
    closed = dict.fromkeys(ORDER, "Paused")
    result, calls = _tick(monkeypatch, pressure, {"agent": "Running", **closed})
    assert calls == []
    assert result["action"] == "hold"


def test_a_pressure_event_names_its_action_and_group(monkeypatch, tmp_path) -> None:
    spool = tmp_path / "events.jsonl"
    _tick(
        monkeypatch,
        {**QUIET, "memory_full_avg10": 30.0, "memory_full_avg60": 30.0},
        _groups(),
        spool=spool,
    )
    events = [json.loads(line) for line in spool.read_text().splitlines()]
    assert [(e["kind"], e["group"], e["action"]) for e in events] == [
        ("pressure", "pytest-heavy", "closed")
    ]


@pytest.mark.parametrize("event_loss", ["truncation", "missing", "append_failure"])
def test_the_queue_alone_decides_reopening(monkeypatch, tmp_path, event_loss) -> None:
    """Breaks if reopening depends on anything but pueue's group state."""
    spool = tmp_path / "events.jsonl"
    if event_loss == "append_failure":

        def unavailable(*_args, **_kwargs):
            raise OSError("synthetic unavailable event store")

        monkeypatch.setattr(pressure_pause, "append_jsonl", unavailable)
    groups = _groups()
    result, calls = _tick(
        monkeypatch,
        {**QUIET, "memory_full_avg10": 30.0, "memory_full_avg60": 30.0},
        groups,
        spool=spool,
    )
    assert calls == [("pause", "pytest-heavy")]
    if event_loss == "truncation":
        spool.write_text("")
    elif event_loss == "missing":
        spool.unlink(missing_ok=True)
    groups["pytest-heavy"] = "Paused"
    result, calls = _tick(monkeypatch, QUIET, groups, spool=spool)
    assert calls == [("resume", "pytest-heavy")]
    assert result["action"] == "opened"


def test_pressure_append_keeps_compact_jsonl_record(tmp_path) -> None:
    spool = tmp_path / "events.jsonl"

    record = pressure_pause._append(spool, {"action": "closed", "group": "agent"})

    assert json.loads(spool.read_text(encoding="utf-8")) == record
    assert spool.read_text(encoding="utf-8").endswith("\n")


def test_whole_tick_deadline_interrupts_a_blocked_queue(monkeypatch):
    import signal
    import time

    monkeypatch.setattr(pressure_pause, "TICK_TIMEOUT_SECONDS", 0.05)

    def stalled():
        time.sleep(1)
        pytest.fail("deadline did not interrupt the stall")

    monkeypatch.setattr(
        pressure_pause,
        "_tick",
        lambda **kwargs: stalled(),
    )
    previous = signal.getsignal(signal.SIGALRM)
    result = pressure_pause.tick(spool=None)
    assert result == {
        "action": "unavailable",
        "error": "pressure tick deadline exceeded",
    }
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0, 0)
