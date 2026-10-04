"""Explicit no-deadline operations retain the existing runner and cancellation owners."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentctl import landing, run
from agentctl.limits import valid_timeout_seconds
from agentctl.projects import load_project_adapter
from conftest import write_project
from test_run import write_launch


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
    clock = iter([0.0, 10000.0, 20000.0, 30000.0])
    monkeypatch.setattr(run.time, "monotonic", lambda: next(clock))
    assert run._wait_for_unit("fixture.service", 0) == {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
    }


def test_landing_no_deadline_reuses_live_job_until_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    views = iter(
        [
            {
                "job_id": 17,
                "terminal": False,
                "phase": "running",
                "started_at": "2000-01-01T00:00:00Z",
            },
            {"job_id": 17, "terminal": True, "phase": "done"},
        ]
    )
    calls = []

    def wait(job_id: int, **kwargs: object) -> dict[str, object]:
        calls.append(job_id)
        return next(views)

    monkeypatch.setattr(landing.launch, "wait", wait)
    monkeypatch.setattr(landing.pueue, "tasks", lambda: [])
    monkeypatch.setattr(landing.launch, "find_task", lambda *args: None)
    assert landing._await_verification("fixture", 17, "same-job", 0)["terminal"] is True
    assert calls == [17, 17]


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
