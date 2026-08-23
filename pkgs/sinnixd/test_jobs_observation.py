from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from sinnixd.jobs import (
    SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    GenericJobSpec,
    GenericJobStore,
    GenericJobs,
    SystemdJobError,
    capture_main,
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


def test_stop_timeout_then_collected_unit_reconciles_after_restart(tmp_path: Path) -> None:
    """Anti-vacuity: not-found defaults must not turn persisted cancel uncertainty into success."""
    class StopTimesOutThenCollects(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            self.properties = {
                "LoadState": "not-found",
                "ActiveState": "inactive",
                "SubState": "dead",
                "InvocationID": "",
                "Result": "success",
                "ExecMainCode": "0",
                "ExecMainStatus": "0",
            }
            raise SystemdJobError("systemd command timed out")

    systemd = StopTimesOutThenCollects()
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})

    with pytest.raises(SystemdJobError, match="timed out"):
        jobs.cancel(started["job_id"])
    uncertain = jobs.get(started["job_id"])
    persisted = jobs.store.load(started["job_id"])

    assert uncertain["state"]["phase"] == "outcome-unknown"
    assert not uncertain["state"]["terminal"]
    assert uncertain["state"]["cancellation"]["invocation_id"] == "fixture-invocation"
    assert persisted.cancel_requested_at is not None
    assert persisted.cancel_stop_acknowledged_at is None

    legacy_false_success = jobs._with_state(
        persisted,
        {
            "phase": "succeeded",
            "terminal": True,
            "systemd": dict(systemd.properties),
            "observed_at": "2026-08-23T08:58:52+00:00",
        },
    )
    jobs.store.save(legacy_false_success)
    restarted = GenericJobs(systemd, GenericJobStore(jobs.store.root), wait_poll_seconds=0.1)

    repaired = restarted.get(started["job_id"])
    assert repaired["state"]["phase"] == "outcome-unknown"
    assert not repaired["state"]["terminal"]

    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "InvocationID": "fixture-invocation",
        "Result": "signal",
        "ExecMainStatus": "15",
    }
    cancelled = restarted.get(started["job_id"])
    assert cancelled["state"]["phase"] == "cancelled"
    assert cancelled["state"]["terminal"]


@pytest.mark.parametrize(
    ("properties", "expected"),
    [
        (
            {
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "InvocationID": "natural-success",
                "Result": "success",
                "ExecMainStatus": "0",
            },
            "succeeded",
        ),
        (
            {
                "LoadState": "not-found",
                "ActiveState": "inactive",
                "InvocationID": "",
                "Result": "success",
                "ExecMainCode": "0",
                "ExecMainStatus": "0",
            },
            "missing",
        ),
    ],
)
def test_natural_success_requires_a_loaded_systemd_result(
    tmp_path: Path, properties: dict[str, str], expected: str
) -> None:
    systemd = FakeSystemdJobs(properties=properties)
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})

    terminal = jobs.get(started["job_id"])

    assert terminal["state"]["phase"] == expected
    assert terminal["state"]["terminal"]


@pytest.mark.parametrize(
    ("content", "completed", "expected"),
    [
        (b"", False, "outcome-unknown"),
        (b'{"receipt":"complete"}', False, "outcome-unknown"),
        (b"not-json", True, "outcome-unknown"),
        (b'{"receipt":"complete"}', True, "succeeded"),
    ],
)
def test_collected_typed_job_requires_authoritative_semantic_result(
    tmp_path: Path, content: bytes, completed: bool, expected: str
) -> None:
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            result_kind="json",
        )
    )
    record = jobs.store.load(started["job_id"])
    assert record.result_path is not None
    record.result_path.write_bytes(content)
    if completed:
        record.log_path.with_suffix(".complete").touch(mode=0o600)
    jobs.store.save(jobs._with_cancel_intent(record, "fixture-invocation"))
    systemd.properties = {
        "LoadState": "not-found",
        "ActiveState": "inactive",
        "InvocationID": "",
        "Result": "success",
        "ExecMainStatus": "0",
    }

    reconciled = jobs.get(started["job_id"])

    assert reconciled["state"]["phase"] == expected
    assert reconciled["state"]["terminal"] is (expected == "succeeded")
    if expected == "succeeded":
        assert reconciled["state"]["result_evidence"] == "completed"


@pytest.mark.parametrize(("exit_code", "completed"), [(0, True), (1, False)])
def test_capture_completion_marker_requires_zero_exit(
    tmp_path: Path, exit_code: int, completed: bool
) -> None:
    log_path = tmp_path / f"capture-{exit_code}.log"
    log_path.touch(mode=0o600)

    returned = capture_main(
        (
            "--log-path",
            str(log_path),
            "--overflow-path",
            str(log_path.with_suffix(".overflow")),
            "--max-bytes",
            "64",
            "--",
            "/bin/sh",
            "-c",
            f"printf captured; exit {exit_code}",
        )
    )

    assert returned == exit_code
    assert log_path.with_suffix(".complete").exists() is completed
