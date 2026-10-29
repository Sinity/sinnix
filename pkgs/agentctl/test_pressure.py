import json
import tracemalloc
from pathlib import Path

import pytest
from agentctl import pressure as pressure_pause


def _spool(tmp_path: Path, *events: dict) -> Path:
    spool = tmp_path / "events.jsonl"
    spool.write_text(
        "".join(json.dumps({"kind": "pressure", **event}) + "\n" for event in events)
    )
    return spool


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


def _ours(group: str) -> dict:
    return {"action": "closed", "group": group, "owner": pressure_pause.OWNER}


@pytest.mark.parametrize("io", [26.0, 80.0])
def test_io_pressure_is_observation_without_blanket_admission_veto(monkeypatch, io):
    result, calls = _tick(
        monkeypatch,
        {
            "io_full_avg10": io,
            "io_full_avg60": io,
            "memory_full_avg10": 0.0,
            "memory_full_avg60": 0.0,
        },
        dict.fromkeys(pressure_pause.MANAGED_GROUPS, "Running"),
    )
    assert calls == []
    assert result["action"] == "clear"
    assert result["io_full_avg60"] == io


def test_owned_io_pause_releases_without_waiting_for_disk_idle(monkeypatch, tmp_path):
    result, calls = _tick(
        monkeypatch,
        {
            "io_full_avg10": 30.0,
            "io_full_avg60": 30.0,
            "memory_full_avg10": 0.0,
            "memory_full_avg60": 0.0,
        },
        {
            name: "Paused" if name == "bulk" else "Running"
            for name in pressure_pause.MANAGED_GROUPS
        },
        spool=_spool(tmp_path, {**_ours("bulk"), "signal": "io"}),
    )
    assert calls == [("resume", "bulk")]
    assert result["action"] == "opened"


def test_io_pause_stays_closed_when_memory_is_unknown(monkeypatch, tmp_path):
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg10": 30.0, "io_full_avg60": 30.0},
        {"bulk": "Paused"},
        spool=_spool(tmp_path, {**_ours("bulk"), "signal": "io"}),
    )
    assert calls == []
    assert result["action"] == "unknown-pressure"


@pytest.mark.parametrize("io_avg10,io_avg60", [(0.0, 0.0), (30.0, 15.0)])
def test_no_paused_groups_below_closure_threshold_reports_clear(
    monkeypatch, io_avg10, io_avg60
) -> None:
    result, calls = _tick(
        monkeypatch,
        {
            "io_full_avg10": io_avg10,
            "io_full_avg60": io_avg60,
            "memory_full_avg10": 0.0,
            "memory_full_avg60": 0.0,
        },
        dict.fromkeys(pressure_pause.MANAGED_GROUPS, "Running"),
    )
    assert calls == []
    assert result["action"] == "clear"
    assert result["frozen"] == [] and result["signal"] is None


def test_owned_pause_without_signal_recovers_on_memory_even_with_busy_io(
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

    assert calls == [("resume", "agent")]
    assert result["action"] == "opened"


def test_unowned_pause_is_preserved_with_busy_io(monkeypatch) -> None:
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


def test_owned_pause_reopens_on_memory_recovery(monkeypatch, tmp_path) -> None:
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
            "memory_full_avg10": 0.0,
            "memory_full_avg60": 30.0,
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


def test_pressure_replay_memory_does_not_scale_with_retained_history(tmp_path):
    spool = tmp_path / "events.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    event = {
        "kind": "pressure",
        "action": "closed",
        "group": "bulk",
        "owner": "agentctl",
        "signal": "io",
        "detail": "x" * 200,
    }
    line = json.dumps(event) + "\n"
    with spool.open("w") as stream:
        for _ in range(20000):
            stream.write(line)
    tracemalloc.start()
    try:
        state = pressure_pause.event_state(spool, checkpoint=checkpoint)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert state.ours() == {"bulk"}
    assert state.cursor["offset"] == spool.stat().st_size
    assert peak < 2 * 1024 * 1024


def test_pressure_replay_leaves_partial_record_for_next_read(tmp_path):
    spool = tmp_path / "events.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    closed = json.dumps({"kind": "pressure", **_ours("bulk")}).encode() + b"\n"
    opened = json.dumps(
        {"kind": "pressure", "action": "opened", "group": "bulk"}
    ).encode()
    prefix = closed + b"not-json\n\xff\n"
    spool.write_bytes(prefix + opened[:-4])
    first = pressure_pause.event_state(spool, checkpoint=checkpoint)
    assert first.ours() == {"bulk"}
    assert first.cursor["offset"] == len(prefix)
    with spool.open("ab") as stream:
        stream.write(opened[-4:] + b"\n")
    second = pressure_pause.event_state(spool, checkpoint=checkpoint)
    assert second.ours() == set()
    assert second.cursor["offset"] == spool.stat().st_size


def test_pressure_replay_read_failure_retains_previous_projection(
    monkeypatch, tmp_path
):
    spool = _spool(tmp_path, _ours("pytest"))
    checkpoint = tmp_path / "checkpoint.json"
    previous = pressure_pause.event_state(spool, checkpoint=checkpoint)
    with spool.open("ab") as stream:
        stream.write(
            (json.dumps({"kind": "pressure", **_ours("bulk")}) + "\n").encode()
        )
        stream.write(
            (
                json.dumps({"kind": "pressure", "action": "opened", "group": "pytest"})
                + "\n"
            ).encode()
        )
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
        failed = pressure_pause.event_state(spool, checkpoint=checkpoint)
    assert failed == previous
    assert checkpoint.read_bytes() == saved_checkpoint
    recovered = pressure_pause.event_state(spool, checkpoint=checkpoint)
    assert recovered.ours() == {"bulk"}
    assert recovered.cursor["offset"] == spool.stat().st_size


@pytest.mark.parametrize("stage", ["read", "decode", "apply"])
@pytest.mark.parametrize("rotate", [False, True])
def test_deadline_replay_resumes_only_completed_records(
    monkeypatch, tmp_path, stage, rotate
):
    spool = tmp_path / "events.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    first = (
        json.dumps(
            {"kind": "pressure", **_ours("bulk"), "detail": "α"}, ensure_ascii=False
        )
        + "\n"
    ).encode()
    second = (
        json.dumps({"kind": "pressure", "action": "opened", "group": "bulk"}) + "\n"
    ).encode()
    spool.write_bytes(first + second)
    original_open = Path.open
    original_loads = json.loads
    original_apply = pressure_pause.SpoolState.apply
    interrupted = True
    seeks = []
    groups_calls = []
    holds_calls = []

    class ReplayRead:
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
            seeks.append(offset)
            return self.handle.seek(offset)

        def readline(self, limit):
            self.reads += 1
            if interrupted and stage == "read" and self.reads == 2:
                raise pressure_pause.TickDeadline("synthetic replay deadline")
            return self.handle.readline(limit)

    def open_replay(path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        return ReplayRead(handle) if path == spool and args == ("rb",) else handle

    def decode(raw, *args, **kwargs):
        value = original_loads(raw, *args, **kwargs)
        if interrupted and stage == "decode" and value.get("action") == "opened":
            raise pressure_pause.TickDeadline("synthetic replay deadline")
        return value

    def apply(state, event):
        original_apply(state, event)
        if interrupted and stage == "apply" and event.get("action") == "opened":
            raise pressure_pause.TickDeadline("synthetic replay deadline")

    def groups():
        groups_calls.append(True)
        return {"bulk": "Paused", "normal": "Paused"}

    def release_holds():
        holds_calls.append(True)
        return {"released": [], "waiting": []}

    monkeypatch.setattr(Path, "open", open_replay)
    monkeypatch.setattr(pressure_pause.json, "loads", decode)
    monkeypatch.setattr(pressure_pause.SpoolState, "apply", apply)
    monkeypatch.setattr(
        pressure_pause,
        "read_pressure",
        lambda _: dict.fromkeys(
            [
                "io_full_avg10",
                "io_full_avg60",
                "memory_full_avg10",
                "memory_full_avg60",
            ],
            0.0,
        ),
    )
    monkeypatch.setattr(pressure_pause.pueue, "groups_status", groups)
    monkeypatch.setattr(
        pressure_pause.pueue, "pause", lambda _: pytest.fail("unexpected pause")
    )
    monkeypatch.setattr(
        pressure_pause.pueue, "resume", lambda _: pytest.fail("unowned pause resumed")
    )
    decision = pressure_pause.tick(
        spool=spool, checkpoint=checkpoint, release_holds=release_holds
    )
    assert decision == {"action": "unavailable", "error": "synthetic replay deadline"}
    assert groups_calls == holds_calls == []
    saved = original_loads(checkpoint.read_text())
    assert saved["cursor"] == {
        "device": spool.stat().st_dev,
        "inode": spool.stat().st_ino,
        "offset": len(first),
    }
    assert saved["pauses"] == {"bulk": {"owner": "agentctl", "signals": []}}

    interrupted = False
    if rotate:
        replacement = tmp_path / "replacement.jsonl"
        replacement.write_bytes(first + second)
        replacement.replace(spool)
    decision = pressure_pause.tick(
        spool=spool, checkpoint=checkpoint, release_holds=release_holds
    )
    assert decision["action"] in {"hold", "clear"}
    assert groups_calls == holds_calls == [True]
    assert seeks == [0, 0 if rotate else len(first)]
    saved = original_loads(checkpoint.read_text())
    assert saved["cursor"] == {
        "device": spool.stat().st_dev,
        "inode": spool.stat().st_ino,
        "offset": len(first) + len(second),
    }
    assert saved["pauses"] == {}


def test_malformed_checkpoint_recovers_to_empty_state(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text("{not-json", encoding="utf-8")

    state = pressure_pause.event_state(None, checkpoint=checkpoint)

    assert state.pauses == {}
    assert state.cursor is None


def test_pressure_append_keeps_compact_jsonl_record(tmp_path) -> None:
    spool = tmp_path / "events.jsonl"

    record = pressure_pause._append(spool, {"action": "closed", "group": "agent"})

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

    assert calls == [("resume", "agent")]
    assert result["group"] == "agent"


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
        {"io_full_avg60": 30.0, "memory_full_avg60": 30.0},
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

    assert calls == []
    assert result["action"] == "hold"


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
    assert result["signal"] == "memory"


def test_a_pause_event_names_its_owner_and_group(monkeypatch, tmp_path) -> None:
    spool = tmp_path / "events.jsonl"
    _tick(
        monkeypatch,
        {"io_full_avg60": 30.0, "memory_full_avg60": 30.0},
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
    assert pressure_pause.paused_by_us(spool) == set()

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


def test_owned_pause_recovers_on_memory_with_busy_io(monkeypatch, tmp_path) -> None:
    """Retired I/O rules do not keep an owned pause closed."""
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 60.0, "memory_full_avg60": 1.0},
        {"pytest": "Paused", "bulk": "Paused", "pytest-quick": "Paused"},
        spool=_spool(tmp_path, _ours("pytest-quick")),
    )
    assert calls == [("resume", "pytest-quick")]
    assert result["action"] == "opened"


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

        monkeypatch.setattr(pressure_pause, "append_jsonl", unavailable)
    result, calls = _tick(
        monkeypatch,
        {"io_full_avg60": 30.0, "memory_full_avg60": 30.0},
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
    assert pressure_pause.paused_by_us(spool) == set()


@pytest.mark.parametrize(
    "psi,headroom,width,expected",
    [
        (0, 2048, 2, 3),
        (0, 1024, 3, 2),
        (11, 9999, 3, 2),
        (0, 9999, 8, 8),
        (11, 0, 1, 1),
        (None, 9999, 2, 2),
    ],
)
def test_adaptive_width_respects_pressure_headroom_floor_and_ceiling(
    monkeypatch, tmp_path, psi, headroom, width, expected
):
    from agentctl.config import AdaptivePool, PoolPolicy

    calls = []
    monkeypatch.setattr(pressure_pause.pueue, "groups", lambda: {"pytest-quick": width})
    monkeypatch.setattr(
        pressure_pause.pueue,
        "set_parallel",
        lambda group, count: calls.append((group, count)),
    )
    monkeypatch.setattr(pressure_pause, "slice_headroom", lambda unit: headroom)
    spool = tmp_path / "events.jsonl"
    pressure_pause.adaptive_widths(
        {"pytest-quick": PoolPolicy(8, adaptive=AdaptivePool(1, 1024, "quick.slice"))},
        {"pytest-quick": "Running"},
        {"memory_full_avg10": psi, "memory_full_avg60": psi},
        spool,
    )
    assert calls == ([] if width == expected else [("pytest-quick", expected)])
    if calls:
        event = json.loads(spool.read_text())
        assert (
            event["action"] == "resized"
            and event["from"] == width
            and event["to"] == expected
        )
    else:
        assert not spool.exists()


def test_headroom_uses_ancestor_bounds_without_reading_cgroup_root(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        pressure_pause.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout="/parent/quick\n"),
    )
    parent = tmp_path / "parent"
    quick = parent / "quick"
    quick.mkdir(parents=True)
    for node, used, high, maximum in [
        (parent, 80, "max", "100"),
        (quick, 5, "50", "100"),
    ]:
        (node / "memory.current").write_text(str(used))
        (node / "memory.high").write_text(high)
        (node / "memory.max").write_text(maximum)
    assert pressure_pause.slice_headroom("quick.slice", tmp_path) == 20
    (parent / "memory.current").unlink()
    with pytest.raises(OSError):
        pressure_pause.slice_headroom("quick.slice", tmp_path)


def test_adaptive_width_does_not_touch_operator_pause_or_unknown_accounting(
    monkeypatch, tmp_path
):
    from agentctl.config import AdaptivePool, PoolPolicy

    monkeypatch.setattr(pressure_pause.pueue, "groups", lambda: {"quick": 4})

    def forbidden(*args):
        raise AssertionError("width changed")

    monkeypatch.setattr(pressure_pause.pueue, "set_parallel", forbidden)
    monkeypatch.setattr(pressure_pause, "slice_headroom", forbidden)
    policy = {"quick": PoolPolicy(8, adaptive=AdaptivePool(1, 1024, "quick.slice"))}
    assert (
        pressure_pause.adaptive_widths(
            policy, {"quick": "Paused"}, {}, tmp_path / "events.jsonl"
        )[0]["status"]
        == "not-running"
    )

    def missing(*args):
        raise FileNotFoundError("missing accounting")

    monkeypatch.setattr(pressure_pause, "slice_headroom", missing)
    assert (
        pressure_pause.adaptive_widths(
            policy, {"quick": "Running"}, {}, tmp_path / "events.jsonl"
        )[0]["status"]
        == "unavailable"
    )


@pytest.mark.parametrize("stage", ["tick", "holds"])
def test_whole_tick_deadline_includes_hold_release(monkeypatch, stage):
    import signal
    import time

    monkeypatch.setattr(pressure_pause, "TICK_TIMEOUT_SECONDS", 0.05)

    def stalled():
        time.sleep(1)
        pytest.fail("deadline did not interrupt the stall")

    monkeypatch.setattr(
        pressure_pause,
        "_tick",
        lambda **kwargs: stalled() if stage == "tick" else {"action": "clear"},
    )
    previous = signal.getsignal(signal.SIGALRM)
    result = pressure_pause.tick(spool=None, release_holds=stalled)
    assert result == {
        "action": "unavailable",
        "error": "pressure tick deadline exceeded",
    }
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0, 0)


def test_tick_stages_share_one_budget(monkeypatch):
    import time

    monkeypatch.setattr(pressure_pause, "TICK_TIMEOUT_SECONDS", 0.05)

    def decide(**kwargs):
        time.sleep(0.03)
        return {"action": "clear"}

    def release():
        time.sleep(0.03)
        return {"released": [], "waiting": []}

    monkeypatch.setattr(pressure_pause, "_tick", decide)
    assert (
        pressure_pause.tick(spool=None, release_holds=release)["action"]
        == "unavailable"
    )
