import json
import tracemalloc
from pathlib import Path

import pytest
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


@pytest.mark.parametrize("io_avg10,io_avg60", [(0.0, 0.0), (30.0, 15.0)])
def test_no_paused_groups_below_closure_threshold_reports_clear(
    monkeypatch, io_avg10, io_avg60
) -> None:
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg10": io_avg10, "io_full_avg60": io_avg60,
         "memory_full_avg10": 0.0, "memory_full_avg60": 0.0},
        {name: "Running" for name in backpressure.MANAGED_GROUPS},
    )
    assert calls == []
    assert result["action"] == "clear"
    assert result["frozen"] == [] and result["signal"] is None


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


def test_backpressure_replay_memory_does_not_scale_with_retained_history(tmp_path):
    spool = tmp_path / "events.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    event = {"kind": "backpressure", "action": "closed", "group": "bulk",
             "owner": "agentctl", "signal": "io", "detail": "x" * 200}
    line = json.dumps(event) + "\n"
    with spool.open("w") as stream:
        for _ in range(20000):
            stream.write(line)
    tracemalloc.start()
    try:
        state = backpressure.event_state(spool, checkpoint=checkpoint)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert state.ours() == {"bulk"}
    assert state.cursor["offset"] == spool.stat().st_size
    assert peak < 2 * 1024 * 1024


def test_backpressure_replay_leaves_partial_record_for_next_read(tmp_path):
    spool = tmp_path / "events.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    closed = json.dumps({"kind": "backpressure", **_ours("bulk")}).encode() + b"\n"
    opened = json.dumps({"kind": "backpressure", "action": "opened", "group": "bulk"}).encode()
    prefix = closed + b"not-json\n\xff\n"
    spool.write_bytes(prefix + opened[:-4])
    first = backpressure.event_state(spool, checkpoint=checkpoint)
    assert first.ours() == {"bulk"}
    assert first.cursor["offset"] == len(prefix)
    with spool.open("ab") as stream:
        stream.write(opened[-4:] + b"\n")
    second = backpressure.event_state(spool, checkpoint=checkpoint)
    assert second.ours() == set()
    assert second.cursor["offset"] == spool.stat().st_size


def test_backpressure_replay_read_failure_retains_previous_projection(monkeypatch, tmp_path):
    spool = _spool(tmp_path, _ours("pytest"))
    checkpoint = tmp_path / "checkpoint.json"
    previous = backpressure.event_state(spool, checkpoint=checkpoint)
    with spool.open("ab") as stream:
        stream.write((json.dumps({"kind": "backpressure", **_ours("bulk")}) + "\n").encode())
        stream.write((json.dumps({"kind": "backpressure", "action": "opened", "group": "pytest"}) + "\n").encode())
    saved_checkpoint = checkpoint.read_bytes()
    original_open = Path.open

    class FailingRead:
        def __init__(self, handle):
            self.handle = handle
            self.reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.handle.close()

        def fileno(self):
            return self.handle.fileno()

        def seek(self, offset):
            return self.handle.seek(offset)

        def readline(self, limit):
            self.reads += 1
            if self.reads == 2:
                raise OSError("synthetic read failure")
            return self.handle.readline(limit)

    def open_with_failure(path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        return FailingRead(handle) if path == spool and args == ("rb",) else handle

    with monkeypatch.context() as patching:
        patching.setattr(Path, "open", open_with_failure)
        failed = backpressure.event_state(spool, checkpoint=checkpoint)
    assert failed == previous
    assert checkpoint.read_bytes() == saved_checkpoint
    recovered = backpressure.event_state(spool, checkpoint=checkpoint)
    assert recovered.ours() == {"bulk"}
    assert recovered.cursor["offset"] == spool.stat().st_size


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


def test_malformed_checkpoint_recovers_to_empty_state(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text("{not-json", encoding="utf-8")

    state = backpressure.event_state(None, checkpoint=checkpoint)

    assert state.pauses == {}
    assert state.legacy_holds == {}
    assert state.cursor is None


def test_backpressure_append_keeps_compact_jsonl_record(tmp_path) -> None:
    spool = tmp_path / "events.jsonl"

    record = backpressure._append(spool, {"action": "closed", "group": "agent"})

    assert json.loads(spool.read_text(encoding="utf-8")) == record
    assert spool.read_text(encoding="utf-8").endswith("\n")


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


def test_signal_transition_keeps_group_closed_while_new_signal_still_requires_it(
    monkeypatch, tmp_path
) -> None:
    """An I/O pause cannot reopen pytest-heavy after memory becomes active."""
    result, calls = _tick(
        monkeypatch,
        {
            "io_full_avg10": 1.0,
            "io_full_avg60": 1.0,
            "memory_full_avg10": 30.0,
            "memory_full_avg60": 30.0,
        },
        {
            "agent": "Running",
            "pytest-heavy": "Paused",
            "pytest": "Running",
            "normal": "Running",
            "bulk": "Running",
        },
        spool=_spool(tmp_path, {**_ours("pytest-heavy"), "signal": "io"}),
    )

    assert calls == [("pause", "pytest")]
    assert result["action"] == "closed"
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
    assert calls == [] and result["action"] == "clear"
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


def test_old_io_pause_waits_for_its_closing_signal_to_recover(
    monkeypatch, tmp_path
) -> None:
    """Changing eligibility does not prove the recorded closing signal recovered."""
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


def test_tick_retires_tracked_holds_whose_task_pueue_no_longer_knows(
    monkeypatch, tmp_path
) -> None:
    """A held task removed by `pueue clean` emits no release event of its own."""
    spool = tmp_path / "events.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    spool.write_text(
        json.dumps(
            {
                "kind": "pool-hold",
                "action": "held",
                "task_id": 847,
                "held_at": "2026-09-11T15:37:39+00:00",
            }
        )
        + "\n"
    )
    monkeypatch.setattr(
        backpressure, "read_pressure", lambda _root: {"io_full_avg60": 1.0}
    )
    monkeypatch.setattr(
        backpressure.pueue, "groups_status", lambda: {"agent": "Running"}
    )
    monkeypatch.setattr(backpressure.pueue, "tasks", lambda: {})

    backpressure.tick(spool=spool, checkpoint=checkpoint, pressure_root=Path("unused"))

    assert backpressure.event_state(None, checkpoint=checkpoint).legacy_holds == {}
    retired = [
        json.loads(line)
        for line in spool.read_text().splitlines()
        if json.loads(line).get("action") == "retired"
    ]
    assert [event["task_id"] for event in retired] == [847]
    assert retired[0]["reason"] == "task-absent-from-pueue"


def test_tick_keeps_a_hold_whose_task_is_still_queued(monkeypatch, tmp_path) -> None:
    spool = tmp_path / "events.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    held = {"kind": "pool-hold", "action": "held", "task_id": 847}
    spool.write_text(json.dumps(held) + "\n")
    monkeypatch.setattr(
        backpressure, "read_pressure", lambda _root: {"io_full_avg60": 1.0}
    )
    monkeypatch.setattr(
        backpressure.pueue, "groups_status", lambda: {"agent": "Running"}
    )
    monkeypatch.setattr(backpressure.pueue, "tasks", lambda: {847: object()})

    backpressure.tick(spool=spool, checkpoint=checkpoint, pressure_root=Path("unused"))

    assert set(backpressure.event_state(None, checkpoint=checkpoint).legacy_holds) == {
        847
    }


@pytest.mark.parametrize(
    "event_loss", ["rotation", "truncation", "missing", "append_failure"]
)
def test_owned_pause_reopens_after_event_loss(
    monkeypatch, tmp_path, event_loss
) -> None:
    spool = _spool(tmp_path)
    groups = {
        "agent": "Running",
        "pytest": "Running",
        "normal": "Running",
        "bulk": "Running",
    }
    if event_loss == "append_failure":

        def unavailable(*_args, **_kwargs):
            raise OSError("synthetic unavailable event store")

        monkeypatch.setattr(backpressure, "append_jsonl", unavailable)
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 30.0, "memory_full_avg60": 1.0},
        groups,
        spool=spool,
    )
    assert calls == [("pause", "pytest")]
    assert result["action"] == "closed"
    if event_loss == "rotation":
        spool.rename(tmp_path / "previous.jsonl")
        spool.write_text("")
    elif event_loss == "truncation":
        spool.write_text("")
    elif event_loss == "missing":
        spool.unlink()
    groups["pytest"] = "Paused"
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 1.0, "memory_full_avg60": 1.0},
        groups,
        spool=spool,
    )
    assert calls == [("resume", "pytest")]
    assert result["action"] == "opened"
    assert backpressure.paused_by_us(spool) == set()
