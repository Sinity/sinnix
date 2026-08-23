from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from sinnixd.jobs import (
    SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    GenericJobStore,
    GenericJobs,
    SystemdJobError,
)


@dataclass
class FakeSystemdJobs:
    properties: dict[str, str] = field(
        default_factory=lambda: {
            "LoadState": "loaded",
            "ActiveState": "active",
            "InvocationID": "fixture-invocation",
            "Result": "success",
        }
    )
    show_unavailable: bool = False
    stopped: list[str] = field(default_factory=list)

    def start(self, **_kwargs: object) -> None:
        return None

    def show(
        self,
        _unit: str,
        *,
        timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ) -> dict[str, str]:
        assert 0 < timeout_seconds <= SYSTEMD_COMMAND_TIMEOUT_SECONDS
        if self.show_unavailable:
            raise SystemdJobError("fixture transport detail must not persist")
        return self.properties

    def stop(self, unit: str) -> None:
        self.stopped.append(unit)


def generic_jobs(tmp_path: Path, systemd: FakeSystemdJobs) -> GenericJobs:
    return GenericJobs(systemd, GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.1)


def test_observation_timeout_remains_retryable_until_systemd_recovers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: timing out `systemctl show` must not terminalize a still-active unit."""
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "sinnixd.jobs.time.sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    systemd = FakeSystemdJobs(show_unavailable=True)
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})

    unknown = jobs.get(started["job_id"])
    persisted = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()
    waited = jobs.wait(started["job_id"], timeout_seconds=1)

    assert unknown["state"]["phase"] == "observation-unknown"
    assert not unknown["state"]["terminal"]
    assert unknown["state"]["error"] == {"code": "systemd-job-error"}
    assert '"terminal": false' in persisted
    assert "fixture transport detail must not persist" not in persisted
    assert waited["state"]["phase"] == "observation-unknown"
    assert not waited["state"]["terminal"]
    assert waited["wait_timed_out"]
    assert clock[0] == 1.0

    systemd.show_unavailable = False
    running = jobs.get(started["job_id"])
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    succeeded = jobs.wait(started["job_id"], timeout_seconds=1)

    assert running["state"]["phase"] == "running"
    assert not running["state"]["terminal"]
    assert succeeded["state"]["phase"] == "succeeded"
    assert succeeded["state"]["terminal"]


@pytest.mark.parametrize(
    ("result", "status", "expected"),
    [("signal", "15", "cancelled"), ("success", "0", "succeeded")],
)
def test_cancel_reconciles_the_systemd_semantic_terminal_result(
    tmp_path: Path, result: str, status: str, expected: str
) -> None:
    """Anti-vacuity: a stop request must not override systemd's observed terminal result."""
    class TerminalOnStop(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            self.properties = {
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "InvocationID": "fixture-invocation",
                "Result": result,
                "ExecMainStatus": status,
            }

    systemd = TerminalOnStop()
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})

    terminal = jobs.cancel(started["job_id"])
    record = jobs.store.load(started["job_id"])

    assert systemd.stopped == [started["unit"]]
    assert record.cancel_stop_acknowledged_at is not None
    assert terminal["state"]["phase"] == expected
    assert terminal["state"]["terminal"]
