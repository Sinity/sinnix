"""Explicit no-deadline operations retain the existing runner and cancellation owners."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentctl import run
from agentctl.limits import valid_timeout_seconds
from agentctl.projects import load_project_adapter
from conftest import write_project
from test_run import outcome_of, user_manager, write_launch


def test_declared_no_deadline_reaches_foreground_runner(tmp_path: Path) -> None:
    root = write_project(tmp_path / "project")
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + '\n[operations.streaming]\ndescription="stream"\nexec=["true"]\ntimeout_seconds=0\n'
    )
    assert load_project_adapter(root).operation("streaming").timeout_seconds == 0
    assert valid_timeout_seconds(0, kind="declared-operation")
    assert not valid_timeout_seconds(0, kind="agent")
    assert not valid_timeout_seconds(False, kind="declared-operation")
    launch = write_launch(tmp_path, kind="declared-operation", timeout_seconds=0)
    assert run.main([str(launch)]) == 0
    payload = json.loads(launch.read_text())
    command = run._service_command(
        payload,
        unit="fixture.service",
        pool="normal",
        description="fixture",
        argv=["true"],
        environment={},
        stdout=tmp_path / "out",
        log_path=tmp_path / "log",
    )
    assert "RuntimeMaxSec=infinity" in command


def test_no_deadline_wait_requires_actual_terminal_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations = iter(
        [
            None,
            {"LoadState": "loaded", "ActiveState": "active"},
            {"LoadState": "loaded", "ActiveState": "inactive", "Result": "success"},
        ]
    )
    monkeypatch.setattr(run, "_unit_snapshot", lambda unit: next(observations))
    monkeypatch.setattr(run.time, "sleep", lambda delay: None)
    assert run._wait_for_unit("fixture.service") == {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
    }


@pytest.mark.parametrize("already_exited", [False, True])
def test_foreground_no_deadline_cancellation_settles_original_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, already_exited: bool
) -> None:
    waits = []
    killed = []

    class Process:
        pid = 42

        def wait(self, timeout: float | None = None) -> int:
            waits.append(timeout)
            if len(waits) == 1:
                raise KeyboardInterrupt()
            return 0

        def poll(self) -> None:
            return None

    monkeypatch.setattr(run.subprocess, "Popen", lambda *args, **kwargs: Process())

    def kill(pid: int, sig: int) -> None:
        killed.append(pid)
        if already_exited:
            raise ProcessLookupError()

    monkeypatch.setattr(run.os, "killpg", kill)
    with pytest.raises(KeyboardInterrupt):
        run._run_bare(
            ["true"],
            {"working_directory": str(tmp_path), "timeout_seconds": 0},
            {},
            None,
            None,
        )
    assert waits == [None, None]
    assert killed == [42]


def test_actual_native_timeout_keeps_its_stop_grace_and_terminal_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_pueue
) -> None:
    user_manager()
    monkeypatch.setenv("PUEUE_GROUP", "fixture")
    done, release, stopping = (
        tmp_path / "done",
        tmp_path / "release",
        tmp_path / "stopping",
    )
    code = (
        "import signal,time;from pathlib import Path;"
        f"release=Path({str(release)!r});done=Path({str(done)!r});stopping=Path({str(stopping)!r});"
        "signal.signal(signal.SIGTERM,lambda *_:stopping.write_text('native timeout'));"
        "exec('while not release.exists(): time.sleep(0.01)');"
        "done.write_text('completed during native stop grace')"
    )
    launch = write_launch(
        tmp_path, timeout_seconds=1, argv=[sys.executable, "-c", code]
    )
    unit = run.unit_for(launch, "fixture")
    original_snapshot, original_control = run._unit_snapshot, run._systemctl
    original_command = run._service_command
    state = {"offset": 0.0, "stopping": 0}

    def service_command(*args, **kwargs):
        command = original_command(*args, **kwargs)
        at = command.index("--")
        # Bound only this test's native grace so a regression still settles
        # its own child promptly. The systemd runtime limit remains one second.
        return command[:at] + ["-p", "TimeoutStopSec=2"] + command[at:]

    def snapshot(name):
        properties = original_snapshot(name)
        if properties and properties.get("ActiveState") == "deactivating":
            state["offset"] += 60
            state["stopping"] += 1
            if state["stopping"] == 2:
                release.write_text("continue")
        return properties

    monkeypatch.setattr(run, "_service_command", service_command)
    monkeypatch.setattr(run, "_unit_snapshot", snapshot)
    monkeypatch.setattr(
        run,
        "time",
        SimpleNamespace(
            monotonic=lambda: time.monotonic() + state["offset"],
            sleep=lambda delay: time.sleep(min(delay, 0.02)),
            time_ns=time.time_ns,
            strftime=time.strftime,
            gmtime=time.gmtime,
        ),
    )
    try:
        assert run.main([str(launch)]) == run.TIMEOUT_EXIT_CODE
        assert stopping.read_text() == "native timeout"
        assert done.read_text() == "completed during native stop grace"
        assert state["stopping"] >= 2
        assert outcome_of(tmp_path)["systemd_result"] == "timeout"
    finally:
        original_control("stop", unit)
        original_control("reset-failed", unit)
