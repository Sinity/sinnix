from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest
import sinnixd.jobs as jobs_module
from sinnixd.jobs import (
    SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    GenericJobs,
    GenericJobSpec,
    GenericJobStore,
    JobResultError,
    SystemdJobError,
    SystemdJobTimeout,
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
    return GenericJobs(
        systemd, GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.1
    )


def test_observation_timeout_remains_retryable_until_systemd_recovers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: timing out `systemctl show` must not terminalize a still-active unit."""
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "sinnixd.jobs.TerminalEvents.wait_terminal",
        lambda self, job_ids, seconds: (
            clock.__setitem__(0, clock[0] + seconds),
            False,
        )[1],
    )
    systemd = FakeSystemdJobs(show_unavailable=True)
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

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


def test_repeated_wait_deadline_preserves_authoritatively_running_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: persisting the deadline-bound observation error would replace running with unknown."""
    clock = [0.0]

    class FirstLiveThenDeadlineExpires(FakeSystemdJobs):
        calls = 0

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            self.calls += 1
            if self.calls == 1:
                clock[0] = 1.0
                return super().show(unit, timeout_seconds=timeout_seconds)
            if self.calls == 2:
                clock[0] = 1.0
                raise SystemdJobTimeout("wait deadline exhausted")
            return super().show(unit, timeout_seconds=timeout_seconds)

    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    systemd = FirstLiveThenDeadlineExpires()
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    first = jobs.wait(started["job_id"], timeout_seconds=1)
    clock[0] = 0.0
    second = jobs.wait(started["job_id"], timeout_seconds=1)
    durable = jobs.store.load(started["job_id"])
    current = jobs.get(started["job_id"])
    listed = jobs.list()["jobs"]

    assert first["state"]["phase"] == "running"
    assert first["wait_timed_out"]
    assert second["state"]["phase"] == "running"
    assert second["wait_timed_out"]
    assert durable.state["phase"] == "running"
    assert current["state"]["phase"] == "running"
    assert [job["state"]["phase"] for job in listed] == ["running"]


def test_wait_deadline_persists_non_timeout_observation_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: a deadline must not retain running after a non-timeout systemd failure."""
    clock = [0.0]

    class FirstLiveThenUnavailable(FakeSystemdJobs):
        calls = 0

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            self.calls += 1
            clock[0] = 1.0
            if self.calls == 1:
                return super().show(unit, timeout_seconds=timeout_seconds)
            raise SystemdJobError("systemctl is unavailable")

    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    systemd = FirstLiveThenUnavailable()
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    first = jobs.wait(started["job_id"], timeout_seconds=1)
    clock[0] = 0.0
    failed = jobs.wait(started["job_id"], timeout_seconds=1)
    durable = jobs.store.load(started["job_id"])

    assert first["state"]["phase"] == "running"
    assert first["wait_timed_out"]
    assert failed["state"]["phase"] == "observation-unknown"
    assert not failed["state"]["terminal"]
    assert failed["wait_timed_out"]
    assert durable.state["phase"] == "observation-unknown"


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
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    terminal = jobs.cancel(started["job_id"])
    record = jobs.store.load(started["job_id"])

    assert systemd.stopped == [started["unit"]]
    assert record.cancel_stop_acknowledged_at is not None
    assert terminal["state"]["phase"] == expected
    assert terminal["state"]["terminal"]


def test_stop_timeout_then_collected_unit_reconciles_after_restart(
    tmp_path: Path,
) -> None:
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
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

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
    restarted = GenericJobs(
        systemd, GenericJobStore(jobs.store.root), wait_poll_seconds=0.1
    )

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


def test_collected_cancel_without_ack_terminalizes_after_reconciliation_grace(
    tmp_path: Path,
) -> None:
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "not-found",
            "ActiveState": "inactive",
            "InvocationID": "",
            "Result": "success",
            "ExecMainStatus": "0",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.load(started["job_id"])
    jobs.store.save(
        replace(
            jobs._with_cancel_intent(record, "fixture-invocation"),
            cancel_requested_at="2000-01-01T00:00:00+00:00",
        )
    )

    terminal = jobs.get(started["job_id"])
    restarted = GenericJobs(
        systemd, GenericJobStore(jobs.store.root), wait_poll_seconds=0.1
    )

    assert terminal["state"]["phase"] == "outcome-unknown"
    assert terminal["state"]["terminal"]
    assert (
        terminal["state"]["outcome_evidence"]
        == "unit-collected-after-cancellation-grace"
    )
    assert restarted.get(started["job_id"])["state"] == terminal["state"]


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
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    terminal = jobs.get(started["job_id"])

    assert terminal["state"]["phase"] == expected
    assert terminal["state"]["terminal"]


def test_list_reconciles_queued_job_with_disposed_checkout(
    tmp_path: Path,
) -> None:
    """A disposed checkout is one terminal row, not a failed job-list query."""
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    missing_checkout = {
        "project_id": "fixture",
        "project_path": str(tmp_path / "project"),
        "checkout_id": "worktree-disposed",
        "path": str(tmp_path / "disposed"),
        "git_common_dir": str(tmp_path / "project" / ".git"),
        "head": "a" * 40,
    }
    record = jobs.store.create(
        GenericJobSpec(
            kind="declared-operation",
            command=("fixture",),
            working_directory=missing_checkout["path"],
            environment={},
            project_id="fixture",
            operation="check",
            parameter_digest="0" * 64,
            checkout=missing_checkout,
        ),
        "00000000-0000-4000-8000-000000000001",
    )
    jobs.store.write_declared_launch(record.job_id, record.spec.command, {})
    jobs.store.save(
        jobs._with_state(
            record,
            {"phase": "queued", "terminal": False, "observed_at": "now"},
        )
    )

    listed = jobs.list(project_id="fixture")

    assert len(listed["jobs"]) == 1
    job = listed["jobs"][0]
    assert job["state"]["phase"] == "checkout-missing"
    assert job["state"]["terminal"]
    assert job["checkout_status"] == {
        "state": "missing",
        "path": missing_checkout["path"],
    }
    assert jobs.store.load(record.job_id).state["phase"] == "checkout-missing"


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


def test_collected_exit_status_job_uses_capture_completion_marker(
    tmp_path: Path,
) -> None:
    """A successful short command remains succeeded after systemd collects its unit."""
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "not-found",
            "ActiveState": "inactive",
            "InvocationID": "",
            "Result": "success",
            "ExecMainCode": "0",
            "ExecMainStatus": "0",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.load(started["job_id"])
    record.log_path.with_suffix(".complete").touch(mode=0o600)

    terminal = jobs.get(started["job_id"])

    assert terminal["state"]["phase"] == "succeeded"
    assert terminal["state"]["terminal"]
    assert terminal["state"]["result_evidence"] == "completed"


def test_terminal_capture_records_resources_at_the_observed_cgroup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: terminal state retains cgroup counters and memory pressure, not only phase."""
    cgroup = tmp_path / "user.slice" / "job.scope"
    cgroup.mkdir(parents=True)
    (cgroup / "memory.pressure").write_text("some avg10=1.00 avg60=2.00\n")
    monkeypatch.setattr(jobs_module, "CGROUP_ROOT", tmp_path)
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "exit-code",
            "ExecMainStatus": "1",
            "ControlGroup": "/user.slice/job.scope",
            "CPUUsageNSec": "1234",
            "IOReadBytes": "5678",
            "IOWriteBytes": "9012",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    terminal = jobs.get(started["job_id"])

    assert terminal["state"]["systemd"]["CPUUsageNSec"] == "1234"
    assert terminal["state"]["resources"] == {
        "cpu_usage_nsec": 1234,
        "io_read_bytes": 5678,
        "io_write_bytes": 9012,
        "memory_pressure": "some avg10=1.00 avg60=2.00\n",
    }


def test_host_pressure_reads_the_nested_managed_work_slice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    uid = jobs_module.os.getuid()
    managed = (
        tmp_path
        / "user.slice"
        / f"user-{uid}.slice"
        / f"user@{uid}.service"
        / "sinnixd.slice"
        / "sinnixd-work.slice"
    )
    managed.mkdir(parents=True)
    (managed / "memory.current").write_text("123456\n")
    monkeypatch.setattr(jobs_module, "CGROUP_ROOT", tmp_path)

    pressure = jobs_module.host_pressure()

    assert pressure["managed_memory_bytes"] == 123456.0


def test_terminal_capture_records_explicit_backend_usage_fields(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: terminal capture persists labeled backend totals and model in the job record."""
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.load(started["job_id"])
    record.log_path.write_text(
        '{"usage":{"input_tokens":1234,"output_tokens":567,"cache_read_input_tokens":89,"model":"claude-sonnet"}}\n'
    )

    terminal = jobs.get(started["job_id"])

    assert terminal["state"]["usage"] == {
        "input_tokens": 1234,
        "output_tokens": 567,
        "cached_tokens": 89,
        "model": "claude-sonnet",
    }


def test_terminal_capture_leaves_unparseable_usage_as_null(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: unrelated log numbers never become guessed token totals."""
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.load(started["job_id"])
    record.log_path.write_text("completed 1234 requests in 567 ms\n")

    terminal = jobs.get(started["job_id"])

    assert terminal["state"]["usage"] == {
        "input_tokens": None,
        "output_tokens": None,
        "cached_tokens": None,
        "model": None,
    }


def test_timeout_preserves_dirty_agent_work_and_writes_handoff(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: timeout terminalization must leave a WIP commit and machine handoff."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    subprocess.run(["git", "init", "--quiet", str(checkout)], check=True)
    subprocess.run(
        ["git", "-C", str(checkout), "config", "user.name", "Fixture"], check=True
    )
    subprocess.run(
        ["git", "-C", str(checkout), "config", "user.email", "fixture@example.test"],
        check=True,
    )
    (checkout / "tracked.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(checkout), "add", "tracked.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(checkout), "commit", "--quiet", "-m", "base"], check=True
    )
    monkeypatch.setattr(
        jobs_module, "revalidate_registered_checkout", lambda _: checkout
    )
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "timeout",
            "ExecMainStatus": "1",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    identity = {
        "project_id": "fixture",
        "project_path": str(checkout),
        "checkout_id": "lane",
        "path": str(checkout),
        "git_common_dir": str(checkout / ".git"),
        "head": subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
    }
    started = jobs.start(
        GenericJobSpec(
            kind="attested-agent",
            command=("fixture-agent",),
            working_directory=str(checkout),
            environment={},
            timeout_seconds=60,
            principal="agent-control",
            checkout=identity,
            result_kind="last-message",
        )
    )
    record = jobs.store.load(started["job_id"])
    record.log_path.write_text("\n".join(f"log-{index}" for index in range(120)))
    (checkout / "wip.txt").write_text("preserve me\n")

    terminal = jobs.get(started["job_id"])

    assert terminal["state"]["phase"] == "timed_out"
    assert terminal["state"]["timeout_wip"]["wip_commit"]
    assert not subprocess.run(
        ["git", "-C", str(checkout), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    subject = subprocess.run(
        ["git", "-C", str(checkout), "log", "-1", "--format=%s"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert subject == f"wip: preserved at timeout {started['job_id']}"
    handoff = json.loads(record.handoff_path.read_text())
    assert handoff["job_id"] == started["job_id"]
    assert handoff["log_tail"] == [f"log-{index}" for index in range(20, 120)]


@pytest.mark.parametrize(
    ("state", "expected_message"),
    [
        (
            {
                "phase": "outcome-unknown",
                "terminal": True,
                "systemd": {
                    "LoadState": "not-found",
                    "ExecMainStatus": "0",
                    "Result": "success",
                },
            },
            "unavailable",
        ),
        (
            {
                "phase": "missing",
                "terminal": True,
                "systemd": {
                    "LoadState": "not-found",
                    "ExecMainStatus": "0",
                    "Result": "success",
                },
            },
            "unavailable",
        ),
        (
            {
                "phase": "launch-failed",
                "terminal": True,
                "systemd": {
                    "LoadState": "not-found",
                    "ExecMainStatus": "0",
                    "Result": "success",
                },
            },
            "unavailable",
        ),
        (
            {
                "phase": "launch-failed",
                "terminal": True,
                "launch_evidence": "not-started",
            },
            "unavailable",
        ),
    ],
)
def test_exit_result_rejects_default_success_without_authoritative_completion(
    tmp_path: Path, state: dict[str, object], expected_message: str
) -> None:
    """The result route must not promote systemd's absent-unit default status to success."""
    jobs = generic_jobs(tmp_path, FakeSystemdJobs())
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.load(started["job_id"])
    jobs.store.save(jobs._with_state(record, state))

    with pytest.raises(JobResultError, match=expected_message):
        jobs.result(started["job_id"])


@pytest.mark.parametrize(
    ("properties", "expected"),
    [
        (
            {
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "Result": "success",
                "ExecMainStatus": "0",
            },
            {"code": 0, "result": "success"},
        ),
        (
            {
                "LoadState": "loaded",
                "ActiveState": "failed",
                "Result": "exit-code",
                "ExecMainStatus": "7",
            },
            {"code": 7, "result": "exit-code"},
        ),
        (
            {
                "LoadState": "loaded",
                "ActiveState": "failed",
                "Result": "timeout",
                "ExecMainStatus": "1",
            },
            {"code": 1, "result": "timeout"},
        ),
        (
            {
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "Result": "signal",
                "ExecMainStatus": "15",
            },
            {"code": 15, "result": "signal"},
        ),
    ],
)
def test_exit_result_preserves_authoritative_observed_outcomes(
    tmp_path: Path, properties: dict[str, str], expected: dict[str, object]
) -> None:
    """Exact loaded systemd outcomes remain the public exit result."""
    systemd = FakeSystemdJobs(properties=properties)
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    assert jobs.result(started["job_id"])["value"] == expected


def test_schema_v3_native_success_reconciles_after_restart_without_exec_main_status(
    tmp_path: Path,
) -> None:
    """Evidence harness: a retained inactive unit must retain schema-v3 native completion evidence."""
    job_id = "74e64cb4-282e-4b27-b4b1-af052b268161"
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "SubState": "dead",
            "Result": "success",
        }
    )
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start(
        GenericJobSpec(
            kind="attested-agent",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            principal="agent-control",
            checkout={
                "project_id": "fixture",
                "project_path": str(tmp_path),
                "checkout_id": "default",
                "path": str(tmp_path),
                "git_common_dir": str(tmp_path / ".git"),
                "head": "a" * 40,
            },
            result_kind="last-message",
        ),
        job_id,
    )
    record_path = tmp_path / "state" / "jobs" / f"{job_id}.json"
    record = jobs.store.load(started["job_id"])
    assert record.result_path is not None
    record.result_path.write_text("native-agent-result")
    legacy = record.to_dict()
    legacy["schema_version"] = 3
    legacy["state"] = {
        "phase": "running",
        "terminal": False,
        "lifecycle": "succeeded",
        "exit_status": 0,
        "observed_at": "2026-08-23T08:58:52+00:00",
    }
    record_path.write_text(json.dumps(legacy))

    restarted = GenericJobs(
        systemd, GenericJobStore(jobs.store.root), wait_poll_seconds=0.1
    )
    reconciled = restarted.get(job_id)

    assert reconciled["state"]["phase"] == "succeeded"
    assert reconciled["state"]["terminal"]
    assert reconciled["state"]["result_evidence"] == "native-v3"
    assert restarted.result(job_id)["content"] == "native-agent-result"


@pytest.mark.parametrize("artifact", ("log", "result"))
def test_malformed_artifacts_fail_closed_without_exposing_private_paths(
    tmp_path: Path, artifact: str
) -> None:
    """Evidence harness: a malformed durable artifact must not expose its path through retrieval."""
    jobs = generic_jobs(tmp_path, FakeSystemdJobs())
    started = jobs.start(
        GenericJobSpec(
            kind="foreground-command",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            result_kind="last-message",
        )
    )
    record = jobs.store.load(started["job_id"])
    path = record.log_path if artifact == "log" else record.result_path
    assert path is not None
    path.unlink(missing_ok=True)
    path.mkdir()

    with pytest.raises(JobResultError) as error:
        if artifact == "log":
            jobs.logs(started["job_id"])
        else:
            jobs.result(started["job_id"])

    assert str(path) not in str(error.value)


def test_log_reader_passes_the_requested_bounded_range_to_the_safe_artifact_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: log offsets must seek before reading instead of expanding the read bound."""
    jobs = generic_jobs(tmp_path, FakeSystemdJobs())
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    observed: list[tuple[int, int]] = []

    def read_window(path: Path, max_bytes: int, *, offset: int = 0) -> bytes:
        observed.append((offset, max_bytes))
        assert path == jobs.store.load(started["job_id"]).log_path
        return b"range"

    monkeypatch.setattr("sinnixd.jobs._read_private_artifact", read_window)

    log = jobs.logs(started["job_id"], offset=4096, max_bytes=5)

    assert observed == [(4096, 5)]
    assert log["content"] == "range"


def test_notify_exit_wakes_a_blocked_wait_before_its_fallback_poll(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: without the event plane this wait sleeps its full fallback slice."""
    import threading
    import time as real_time

    systemd = FakeSystemdJobs()
    jobs = GenericJobs(
        systemd, GenericJobStore(tmp_path / "state"), wait_poll_seconds=30.0
    )
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    results: dict[str, object] = {}

    def wait() -> None:
        results["status"] = jobs.wait(started["job_id"], timeout_seconds=30)

    waiter = threading.Thread(target=wait)
    waiter.start()
    real_time.sleep(0.2)
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    before = real_time.monotonic()
    jobs.notify_exit(started["job_id"])
    waiter.join(timeout=5)
    elapsed = real_time.monotonic() - before

    assert not waiter.is_alive()
    status = results["status"]
    assert status["state"]["phase"] == "succeeded"
    assert status["state"]["terminal"]
    assert elapsed < 5


def test_notify_exit_requires_a_known_job(tmp_path: Path) -> None:
    from uuid import uuid4

    from sinnixd.jobs import JobRecordError

    jobs = GenericJobs(FakeSystemdJobs(), GenericJobStore(tmp_path / "state"))

    with pytest.raises(ValueError, match="job_id must be a UUID"):
        jobs.notify_exit("not-a-job")
    with pytest.raises(JobRecordError, match="unknown job"):
        jobs.notify_exit(str(uuid4()))


def test_wait_any_returns_the_first_terminal_job(tmp_path: Path) -> None:
    """Anti-vacuity: returning the still-running sibling would misreport completion."""

    terminal_properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }

    @dataclass
    class PerUnitSystemd(FakeSystemdJobs):
        terminal_units: set[str] = field(default_factory=set)

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            if unit in self.terminal_units:
                return dict(terminal_properties)
            return super().show(unit, timeout_seconds=timeout_seconds)

    systemd = PerUnitSystemd()
    jobs = GenericJobs(systemd, GenericJobStore(tmp_path / "state"))
    running = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    finished = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    systemd.terminal_units.add(finished["unit"])

    completed = jobs.wait_any(
        (running["job_id"], finished["job_id"]), timeout_seconds=5
    )

    assert completed["completed_job_id"] == finished["job_id"]
    assert completed["job_id"] == finished["job_id"]
    assert completed["state"]["terminal"]


def test_wait_any_times_out_with_a_bounded_phase_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clock = [0.0]
    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "sinnixd.jobs.TerminalEvents.wait_terminal",
        lambda self, job_ids, seconds: (
            clock.__setitem__(0, clock[0] + seconds),
            False,
        )[1],
    )
    jobs = GenericJobs(FakeSystemdJobs(), GenericJobStore(tmp_path / "state"))
    first = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    second = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    timed_out = jobs.wait_any((first["job_id"], second["job_id"]), timeout_seconds=1)

    assert timed_out["wait_timed_out"]
    assert timed_out["jobs"] == {
        first["job_id"]: "running",
        second["job_id"]: "running",
    }


def test_wait_any_rejects_duplicate_and_oversized_id_sets(tmp_path: Path) -> None:
    from uuid import uuid4

    jobs = GenericJobs(FakeSystemdJobs(), GenericJobStore(tmp_path / "state"))
    duplicate = str(uuid4())

    with pytest.raises(ValueError, match="distinct job ids"):
        jobs.wait_any((duplicate, duplicate), timeout_seconds=1)
    with pytest.raises(ValueError, match="distinct job ids"):
        jobs.wait_any(tuple(str(uuid4()) for _ in range(33)), timeout_seconds=1)
    with pytest.raises(ValueError, match="distinct job ids"):
        jobs.wait_any((), timeout_seconds=1)


def test_running_reobservation_skips_the_durable_rewrite(tmp_path: Path) -> None:
    """Anti-vacuity: rewriting an unchanged running state fsyncs per poll for nothing."""
    jobs = GenericJobs(FakeSystemdJobs(), GenericJobStore(tmp_path / "state"))
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record_path = tmp_path / "state" / "jobs" / f"{started['job_id']}.json"

    first = jobs.get(started["job_id"])
    stable = record_path.read_bytes()
    stat_before = record_path.stat().st_mtime_ns
    second = jobs.get(started["job_id"])

    assert first["state"]["phase"] == "running"
    assert second["state"]["phase"] == "running"
    assert record_path.read_bytes() == stable
    assert record_path.stat().st_mtime_ns == stat_before


def test_capture_notifies_the_daemon_socket_for_every_exit_code(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a failed command must wake waiters too, not only successes."""
    import socket as socket_module
    import struct
    import threading

    received: list[dict[str, object]] = []
    socket_path = tmp_path / "sinnixd.sock"
    listener = socket_module.socket(socket_module.AF_UNIX, socket_module.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen()

    def accept_frames() -> None:
        for _ in range(2):
            connection, _address = listener.accept()
            with connection:
                length = struct.unpack("!I", connection.recv(4))[0]
                received.append(json.loads(connection.recv(length)))

    thread = threading.Thread(target=accept_frames)
    thread.start()
    for exit_code in (0, 7):
        log_path = tmp_path / f"capture-notify-{exit_code}.log"
        log_path.touch(mode=0o600)
        returned = capture_main(
            (
                "--log-path",
                str(log_path),
                "--overflow-path",
                str(log_path.with_suffix(".overflow")),
                "--max-bytes",
                "64",
                "--notify-socket",
                str(socket_path),
                "--notify-job-id",
                "74e64cb4-282e-4b27-b4b1-af052b268161",
                "--",
                "/bin/sh",
                "-c",
                f"exit {exit_code}",
            )
        )
        assert returned == exit_code
    thread.join(timeout=5)
    listener.close()

    assert not thread.is_alive()
    operations = [frame["params"]["operation"] for frame in received]
    exit_codes = [frame["params"]["arguments"]["exit_code"] for frame in received]
    assert operations == ["job.notify-exit", "job.notify-exit"]
    assert exit_codes == [0, 7]


def test_capture_exit_code_survives_an_unreachable_notify_socket(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "capture-unreachable.log"
    log_path.touch(mode=0o600)

    returned = capture_main(
        (
            "--log-path",
            str(log_path),
            "--overflow-path",
            str(log_path.with_suffix(".overflow")),
            "--max-bytes",
            "64",
            "--notify-socket",
            str(tmp_path / "absent.sock"),
            "--notify-job-id",
            "74e64cb4-282e-4b27-b4b1-af052b268161",
            "--",
            "/bin/sh",
            "-c",
            "exit 0",
        )
    )

    assert returned == 0
    assert log_path.with_suffix(".complete").exists()


def test_job_list_filters_by_kind(tmp_path: Path) -> None:
    jobs = GenericJobs(FakeSystemdJobs(), GenericJobStore(tmp_path / "state"))
    foreground = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    agent = jobs.start(
        GenericJobSpec(
            kind="attested-agent",
            command=("fixture",),
            working_directory=str(tmp_path),
            environment={},
            principal="agent-control",
            checkout={
                "project_id": "fixture",
                "project_path": str(tmp_path),
                "checkout_id": "default",
                "path": str(tmp_path),
                "git_common_dir": str(tmp_path / ".git"),
                "head": "a" * 40,
            },
            result_kind="last-message",
        )
    )

    agents_only = jobs.list(kinds=("attested-agent",))
    both = jobs.list()

    assert [job["job_id"] for job in agents_only["jobs"]] == [agent["job_id"]]
    assert agents_only["query"]["kinds"] == ["attested-agent"]
    assert {job["job_id"] for job in both["jobs"]} == {
        foreground["job_id"],
        agent["job_id"],
    }


def test_terminal_records_past_retention_archive_but_stay_loadable(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: without retention, store.list parses every historical record forever."""
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
        }
    )
    jobs = GenericJobs(systemd, GenericJobStore(tmp_path / "state"))
    old = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    fresh = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    assert jobs.get(old["job_id"])["state"]["terminal"]
    assert jobs.get(fresh["job_id"])["state"]["terminal"]
    record = jobs.store.load(old["job_id"])
    jobs.store.save(
        jobs._with_state(
            record, {**record.state, "observed_at": "2020-01-01T00:00:00+00:00"}
        )
    )

    restarted = GenericJobs(
        systemd, GenericJobStore(jobs.store.root), record_retention_days=14
    )

    listed = {job["job_id"] for job in restarted.list()["jobs"]}
    assert listed == {fresh["job_id"]}
    archived = restarted.store.load(old["job_id"])
    assert archived.state["terminal"]
    assert (jobs.store.root / "jobs-archive" / f"{old['job_id']}.json").exists()


def test_retention_never_touches_live_or_undated_records(tmp_path: Path) -> None:
    jobs = GenericJobs(FakeSystemdJobs(), GenericJobStore(tmp_path / "state"))
    running = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    record = jobs.store.load(running["job_id"])
    jobs.store.save(
        jobs._with_state(
            record, {**record.state, "observed_at": "2020-01-01T00:00:00+00:00"}
        )
    )

    moved = jobs.store.prune_terminal_records(retention_days=14)

    assert moved == 0
    assert (tmp_path / "state" / "jobs" / f"{running['job_id']}.json").exists()


def test_terminal_transition_spools_exactly_one_event_line(tmp_path: Path) -> None:
    """Anti-vacuity: spooling per observation would duplicate lines on every get."""
    spool = tmp_path / "events" / "events.jsonl"
    systemd = FakeSystemdJobs()
    jobs = GenericJobs(
        systemd, GenericJobStore(tmp_path / "state"), event_spool_path=spool
    )
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    assert jobs.get(started["job_id"])["state"]["phase"] == "running"
    assert not spool.exists()

    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    assert jobs.get(started["job_id"])["state"]["terminal"]
    jobs.get(started["job_id"])
    jobs.list()

    lines = [json.loads(line) for line in spool.read_text().splitlines()]
    assert len(lines) == 1
    assert lines[0]["job_id"] == started["job_id"]
    assert lines[0]["kind"] == "foreground-command"
    assert lines[0]["phase"] == "succeeded"
    assert lines[0]["completed_at"]


def test_terminal_event_carries_coordinator_label_from_job_spec(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"
    systemd = FakeSystemdJobs()
    jobs = GenericJobs(
        systemd, GenericJobStore(tmp_path / "state"), event_spool_path=spool
    )
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={},
    )
    record = jobs.store.load(started["job_id"])
    jobs.store.save(
        replace(
            record,
            spec=replace(record.spec, contract={"coordinator_label": "wave-a"}),
        )
    )
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }

    assert jobs.get(started["job_id"])["state"]["terminal"]
    event = json.loads(spool.read_text().splitlines()[0])
    assert event["coordinator_label"] == "wave-a"


def test_restart_reobservation_of_old_terminal_records_does_not_respool(
    tmp_path: Path,
) -> None:
    spool = tmp_path / "events.jsonl"
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
        }
    )
    jobs = GenericJobs(
        systemd, GenericJobStore(tmp_path / "state"), event_spool_path=spool
    )
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )
    assert jobs.get(started["job_id"])["state"]["terminal"]
    assert len(spool.read_text().splitlines()) == 1

    restarted = GenericJobs(
        systemd, GenericJobStore(jobs.store.root), event_spool_path=spool
    )
    restarted.get(started["job_id"])
    restarted.list()

    assert len(spool.read_text().splitlines()) == 1


def test_spool_failure_never_breaks_the_job_route(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    systemd = FakeSystemdJobs(
        properties={
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
        }
    )
    jobs = GenericJobs(
        systemd,
        GenericJobStore(tmp_path / "state"),
        event_spool_path=blocked / "events.jsonl",
    )
    started = jobs.start_foreground(
        command=("fixture",), working_directory=str(tmp_path), environment={}
    )

    assert jobs.get(started["job_id"])["state"]["terminal"]
