from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import sinnixd.jobs as jobs_module
from sinnix_mcp import OpaquePayload, RequestEnvelope, ResponseEnvelope, SinnixRef, SourceBinding
from sinnix_mcp.execution import ExecutionResult

from sinnixd.api import UnixSocketServer, call, receive_frame, send_frame
from sinnixd.environment import build_environment
from sinnixd.jobs import (
    MAX_LOG_ARTIFACT_BYTES,
    GenericJobSpec,
    GenericJobStore,
    GenericJobs,
    SystemdJobError,
    UserSystemdJobs,
    capture_executable,
    capture_main,
)
from sinnixd.owner_adapters import DeclaredOwnerAdapters, OwnerAdapterError
from sinnixd.projects import ProjectCatalog, ProjectConfigError
from sinnixd.service import SinnixdService


def write_adapter(root: Path) -> None:
    (root / "modules").mkdir(parents=True)
    (root / "flake.nix").write_text("{}")
    (root / ".agentctl").mkdir()
    (root / ".agentctl" / "project.toml").write_text(
        """schema = 1

[project]
id = "fixture"
display_name = "Fixture"
root_markers = ["flake.nix", "modules"]

[environment]
kind = "fixture"
command = ["fixture-env", "--command"]
inherit = ["HOME"]
unset = ["PYTHONPATH"]

[operations.check]
description = "Run fixture checks"
exec = ["fixture-check"]
pool = "normal"
result = "exit"
cache = "tree+environment"
exclusive_keys = ["fixture:check"]
"""
    )


def write_owner_adapter(root: Path) -> None:
    write_adapter(root)
    descriptor = root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + """
[owner_adapters.polylogue_archive]
namespace = "polylogue.archive"
owner = "polylogue-archive"
authority = "owner"
lifecycle = "read_only"
protocol_versions = [1]
source_scoped = true
source_ref = "sinnix://polylogue/archive"
exec = ["polylogue-agentctl-adapter"]
documentation = "Bounded Polylogue archive status."
"""
    )


def request(operation: str, owner: str, arguments: dict[str, object] | None = None) -> RequestEnvelope:
    return RequestEnvelope(
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
        operation=operation,
        owner=owner,
        principal="test",
        arguments=arguments or {},
    )


@dataclass
class FakeSystemdJobs:
    started: list[dict[str, object]] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    properties: dict[str, str] = field(
        default_factory=lambda: {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
            "MainPID": "42",
            "Result": "success",
        }
    )

    def start(
        self,
        *,
        unit: str,
        command: tuple[str, ...],
        working_directory: str,
        environment: dict[str, str],
        timeout_seconds: int,
        log_path: Path,
    ) -> None:
        self.started.append(
            {
                "unit": unit,
                "command": command,
                "working_directory": working_directory,
                "environment": environment,
                "timeout_seconds": timeout_seconds,
                "log_path": log_path,
            }
        )

    def show(self, unit: str) -> dict[str, str]:
        assert unit.startswith("sinnixd-job-")
        return self.properties

    def stop(self, unit: str) -> None:
        self.stopped.append(unit)
        self.properties = {
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "signal",
            "ExecMainCode": "killed",
            "ExecMainStatus": "15",
            "InvocationID": self.properties.get("InvocationID", "fixture-invocation"),
        }


def generic_jobs(tmp_path: Path, systemd: FakeSystemdJobs | None = None) -> GenericJobs:
    return GenericJobs(systemd or FakeSystemdJobs(), GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.001)


@dataclass
class FakeOwnerAdapters:
    response: ResponseEnvelope
    calls: list[dict[str, object]] = field(default_factory=list)

    def call(self, *, project, adapter, request) -> ResponseEnvelope:
        self.calls.append({"project": project, "adapter": adapter, "request": request})
        return self.response


@dataclass
class FakeExecution:
    result: ExecutionResult
    calls: list[tuple[tuple[str, ...], object]] = field(default_factory=list)

    def run(self, command, profile) -> ExecutionResult:
        self.calls.append((tuple(command), profile))
        return self.result


def start_server(
    server: UnixSocketServer,
    *,
    once: bool = False,
    stop_event: threading.Event | None = None,
) -> threading.Thread:
    ready = threading.Event()
    server.ready_event = ready
    target = server.serve_once if once else server.serve_forever
    args = () if once or stop_event is None else (stop_event,)
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    assert ready.wait(1), "Unix socket server did not begin listening"
    return thread


def test_project_catalog_is_explicit_and_operation_catalog_is_bounded(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]))

    response = service.dispatch(request("project.operations", "project-adapters", {"project_id": "fixture"}))

    assert response.ok
    assert response.payload is not None
    assert response.payload.to_dict() == {
        "kind": "inline",
        "value": {
            "project_id": "fixture",
            "operations": [
                {
                    "name": "check",
                    "description": "Run fixture checks",
                    "command": ["fixture-check"],
                    "pool": "normal",
                    "result": "exit",
                    "cache": "tree+environment",
                    "exclusive_keys": ["fixture:check"],
                }
            ],
        },
    }


def test_owner_mismatch_is_a_typed_error(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]))

    response = service.dispatch(request("project.list", "wrong-owner"))

    assert not response.ok
    assert response.owner == "project-adapters"
    assert response.error is not None
    assert response.error.code.value == "AUTHORITY_MISMATCH"

    missing = service.dispatch(
        request("project.get", "project-adapters", {"project_id": "missing"})
    )

    assert not missing.ok
    assert missing.owner == "project-adapters"
    assert missing.error is not None
    assert missing.error.code.value == "INVALID_ARGUMENT"


def test_user_systemd_jobs_starts_a_retained_service_with_log_boundary(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(list(args))
        return SimpleNamespace(stdout="")

    monkeypatch.setattr("sinnixd.jobs.subprocess.run", fake_run)

    UserSystemdJobs().start(
        unit="sinnixd-job-00000000-0000-0000-0000-000000000001.service",
        command=("nix", "develop", "--command", "lint"),
        working_directory="/work/project",
        environment={"HOME": "/home/sinity", "SINNIXD_JOB_ID": "job"},
        timeout_seconds=123,
        log_path=tmp_path / "job.log",
    )

    assert calls == [
        [
            "systemd-run",
            "--user",
            "--quiet",
            "--unit=sinnixd-job-00000000-0000-0000-0000-000000000001.service",
            "--slice=agent.slice",
            "--property=WorkingDirectory=/work/project",
            "--property=RuntimeMaxSec=123s",
            "--property=StandardOutput=journal",
            "--property=StandardError=journal",
            "--",
            str(capture_executable()),
            "--log-path",
            str(tmp_path / "job.log"),
            "--overflow-path",
            str(tmp_path / "job.overflow"),
            "--max-bytes",
            str(MAX_LOG_ARTIFACT_BYTES),
            "--",
            "/run/current-system/sw/bin/env",
            "-i",
            "HOME=/home/sinity",
            "SINNIXD_JOB_ID=job",
            "nix",
            "develop",
            "--command",
            "lint",
        ]
    ]


def test_user_systemd_os_error_reconciles_without_persisting_raw_error(monkeypatch, tmp_path: Path) -> None:
    """Anti-vacuity: raw subprocess OSErrors must enter the systemd reconciliation path."""
    secret = "systemd-run-os-error-do-not-persist"
    calls: list[str] = []

    def fake_run(args, **_kwargs):
        calls.append(args[0])
        if args[0] == "systemd-run":
            raise OSError(secret)
        return SimpleNamespace(stdout="LoadState=loaded\nActiveState=active\nResult=success\n")

    monkeypatch.setattr("sinnixd.jobs.subprocess.run", fake_run)
    jobs = GenericJobs(UserSystemdJobs(), GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.001)

    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    persisted = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()

    assert calls == ["systemd-run", "systemctl"]
    assert started["state"]["phase"] == "running"
    assert secret not in persisted


def test_declared_and_foreground_jobs_share_the_generic_route(tmp_path: Path) -> None:
    """Anti-vacuity: deleting GenericJobs.start makes both launch assertions fail."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=generic_jobs(tmp_path, systemd),
    )

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check"},
        )
    )

    assert started.ok
    assert started.payload is not None
    launch = started.payload.inline
    assert launch["unit"].startswith("sinnixd-job-")
    assert launch["unit"].endswith(".service")
    assert launch["kind"] == "declared-operation"
    assert len(systemd.started) == 1
    assert systemd.started[0]["working_directory"] == str(tmp_path.resolve())
    assert systemd.started[0]["timeout_seconds"] == 3_600
    assert systemd.started[0]["environment"]["SINNIXD_JOB_ID"] == launch["job_id"]
    assert systemd.started[0]["environment"]["SINNIXD_OPERATION"] == "check"

    foreground = service.start_foreground(
        command=("fixture-foreground",),
        working_directory=str(tmp_path),
        environment={"EMPTY": ""},
        timeout_seconds=123,
    )
    assert foreground["kind"] == "foreground-command"
    assert len(systemd.started) == 2
    assert systemd.started[0]["command"] == ("fixture-env", "--command", "fixture-check")
    assert systemd.started[1]["command"] == ("fixture-foreground",)
    foreground_record = service.jobs.store.load(foreground["job_id"])
    assert foreground_record.spec.to_dict()["environment_keys"] == ["EMPTY", "SINNIXD_JOB_ID"]

    status = service.dispatch(request("job.get", "systemd-jobs", {"job_id": launch["job_id"]}))
    cancelled = service.dispatch(
        request("job.cancel", "systemd-jobs", {"job_id": launch["job_id"]})
    )

    assert status.ok
    assert status.payload is not None
    assert status.payload.inline["state"]["systemd"]["MainPID"] == "42"
    assert cancelled.ok
    assert systemd.stopped == [launch["unit"]]


def test_job_reconciliation_marks_missing_units_without_daemon_owned_state(tmp_path: Path) -> None:
    """Anti-vacuity: deleting GenericJobs.get's systemd.show call loses the missing phase."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))

    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}))
    assert started.payload is not None

    response = service.dispatch(request("job.get", "systemd-jobs", {"job_id": started.payload.inline["job_id"]}))

    assert response.ok
    assert response.payload is not None
    assert response.payload.inline["state"]["phase"] == "missing"
    assert response.payload.inline["state"]["terminal"]


def test_declared_project_job_rejects_arbitrary_execution(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))

    wrong_owner = service.dispatch(
        request(
            "job.start",
            "wrong-owner",
            {"project_id": "fixture", "operation": "check"},
        )
    )
    unknown_operation = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "shell"},
        )
    )
    direct_argv = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "argv": ["id"]},
        )
    )

    assert wrong_owner.error is not None
    assert wrong_owner.error.code.value == "AUTHORITY_MISMATCH"
    assert wrong_owner.owner == "systemd-jobs"
    assert unknown_operation.error is not None
    assert unknown_operation.error.code.value == "INVALID_ARGUMENT"
    assert direct_argv.error is not None
    assert direct_argv.error.code.value == "INVALID_ARGUMENT"


def test_environment_builder_keeps_empty_values_distinct_from_unset() -> None:
    """Anti-vacuity: replacing membership checks with truthiness drops the empty EMPTY value."""
    environment = build_environment(
        inherit=("EMPTY", "PRESENT", "MISSING", "REMOVED"),
        unset=("REMOVED",),
        source={"PATH": "", "EMPTY": "", "PRESENT": "value", "REMOVED": "secret"},
    )

    assert environment == {"PATH": "", "EMPTY": "", "PRESENT": "value"}


@pytest.mark.parametrize(
    ("properties", "expected"),
    [
        ({"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}, "succeeded"),
        ({"LoadState": "loaded", "ActiveState": "inactive", "Result": "timeout", "ExecMainStatus": "9"}, "timed_out"),
        ({"LoadState": "loaded", "ActiveState": "failed", "Result": "exit-code", "ExecMainStatus": "1"}, "failed"),
    ],
)
def test_terminal_result_classification_comes_from_systemd(
    tmp_path: Path, properties: dict[str, str], expected: str
) -> None:
    """Anti-vacuity: deleting GenericJobs._classify breaks the terminal phase assertion."""
    systemd = FakeSystemdJobs(properties=properties)
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )

    status = jobs.get(started["job_id"])

    assert status["state"]["phase"] == expected
    assert status["state"]["terminal"]


def test_logs_are_bounded_and_restart_reconciles_the_same_record(tmp_path: Path) -> None:
    """Anti-vacuity: deleting the persisted record or GenericJobs.logs breaks restart reads."""
    systemd = FakeSystemdJobs(
        properties={"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    )
    jobs = generic_jobs(tmp_path, systemd)
    started = jobs.start_foreground(
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={"PATH": ""},
    )
    record = jobs.store.load(started["job_id"])
    record.log_path.write_text("0123456789")

    log = jobs.logs(started["job_id"], offset=2, max_bytes=4)
    restarted = GenericJobs(systemd, jobs.store, wait_poll_seconds=0.001)
    listed = restarted.list()
    waited = restarted.wait(started["job_id"], timeout_seconds=1)

    assert log == {
        "job_id": started["job_id"],
        "offset": 2,
        "content": "2345",
        "next_offset": 6,
        "truncated": True,
        "artifact_truncated": False,
    }
    assert [job["job_id"] for job in listed["jobs"]] == [started["job_id"]]
    assert waited["state"]["phase"] == "succeeded"


def test_capture_caps_persistent_artifacts_and_reports_producer_overflow(tmp_path: Path) -> None:
    """Anti-vacuity: delayed marker writes fail while the producer is still running."""
    log_path = tmp_path / "overflow.log"
    overflow_path = tmp_path / "overflow.overflow"
    result: dict[str, int] = {}
    producer = ("/bin/sh", "-c", "printf 012345; sleep 1")

    thread = threading.Thread(
        target=lambda: result.setdefault(
            "exit_code",
            capture_main(("--log-path", str(log_path), "--overflow-path", str(overflow_path), "--max-bytes", "4", "--", *producer)),
        ),
        daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 0.5
    while not overflow_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert overflow_path.exists()
    assert thread.is_alive()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert result["exit_code"] == 0
    assert log_path.stat().st_size == 4

    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = jobs.store.load(started["job_id"])
    record.log_path.write_bytes(b"0123")
    record.log_path.with_suffix(".overflow").touch()
    log = jobs.logs(started["job_id"], offset=2, max_bytes=2)
    assert log["content"] == "23"
    assert log["next_offset"] == 4
    assert not log["truncated"]
    assert log["artifact_truncated"]


def test_logs_report_marker_created_during_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anti-vacuity: sampling overflow before reading misses this interleaving."""
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = jobs.store.load(started["job_id"])
    record.log_path.write_bytes(b"0123")
    overflow_path = record.log_path.with_suffix(".overflow")
    original_open = Path.open

    def interleaving_open(path: Path, *args: object, **kwargs: object):
        handle = original_open(path, *args, **kwargs)
        if path != record.log_path or args != ("rb",):
            return handle

        class MarkerAfterRead:
            def __enter__(self) -> MarkerAfterRead:
                return self

            def __exit__(self, *unused: object) -> None:
                handle.close()

            def seek(self, *args: object) -> int:
                return handle.seek(*args)

            def read(self, *args: object) -> bytes:
                content = handle.read(*args)
                overflow_path.touch()
                return content

        return MarkerAfterRead()

    monkeypatch.setattr(Path, "open", interleaving_open)

    log = jobs.logs(started["job_id"], max_bytes=4)

    assert log["content"] == "0123"
    assert log["artifact_truncated"]


def test_foreground_specs_redact_argv_and_environment_from_disk(tmp_path: Path) -> None:
    """Anti-vacuity: serializing the launch command or environment exposes this fixture secret."""
    secret_argv = "argv-secret-do-not-persist"
    secret_env = "env-secret-do-not-persist"
    jobs = generic_jobs(tmp_path)
    started = jobs.start_foreground(
        command=("fixture", secret_argv),
        working_directory=str(tmp_path),
        environment={"SECRET": secret_env},
    )
    raw = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()
    persisted = json.loads(raw)
    assert secret_argv not in raw
    assert secret_env not in raw
    assert persisted["spec"]["command"]["display"] == "synthetic foreground command"
    assert len(persisted["spec"]["command"]["digest"]) == 64


def test_job_store_fsyncs_parent_after_replacing_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Anti-vacuity: a file fsync before rename cannot make the renamed entry crash-durable."""
    store = GenericJobStore(tmp_path / "state")
    record = store.create(
        GenericJobSpec(kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={}),
        "00000000-0000-0000-0000-000000000001",
    )
    directory_fd = 10_000
    events: list[tuple[str, object]] = []
    original_open = os.open
    original_close = os.close
    original_replace = os.replace

    def tracked_open(path, flags, *args):
        if flags & os.O_DIRECTORY:
            events.append(("open-directory", Path(path)))
            return directory_fd
        return original_open(path, flags, *args)

    def tracked_fsync(descriptor: int) -> None:
        events.append(("fsync-directory" if descriptor == directory_fd else "fsync-file", descriptor))

    def tracked_close(descriptor: int) -> None:
        if descriptor == directory_fd:
            events.append(("close-directory", descriptor))
            return
        original_close(descriptor)

    def tracked_replace(source, destination) -> None:
        events.append(("replace", Path(destination)))
        original_replace(source, destination)

    monkeypatch.setattr("sinnixd.jobs.os.open", tracked_open)
    monkeypatch.setattr("sinnixd.jobs.os.fsync", tracked_fsync)
    monkeypatch.setattr("sinnixd.jobs.os.close", tracked_close)
    monkeypatch.setattr("sinnixd.jobs.os.replace", tracked_replace)

    store.save(record)

    replace_index = events.index(("replace", store.records_root / f"{record.job_id}.json"))
    file_fsync_index = next(index for index, event in enumerate(events) if event[0] == "fsync-file")
    directory_fsync_index = events.index(("fsync-directory", directory_fd))
    assert file_fsync_index < replace_index < directory_fsync_index
    assert events[directory_fsync_index - 1] == ("open-directory", store.records_root)


def test_job_store_fsyncs_parents_when_creating_state_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Anti-vacuity: mkdir alone can lose a newly established state hierarchy after a crash."""
    synchronized: list[Path] = []
    original_fsync_directory = jobs_module._fsync_directory

    def tracked_fsync_directory(path: Path) -> None:
        synchronized.append(path)
        original_fsync_directory(path)

    monkeypatch.setattr("sinnixd.jobs._fsync_directory", tracked_fsync_directory)
    store = GenericJobStore(tmp_path / "state")

    store.create(
        GenericJobSpec(kind="foreground-command", command=("fixture",), working_directory=str(tmp_path), environment={}),
        "00000000-0000-0000-0000-000000000002",
    )

    assert synchronized == [tmp_path, store.root, store.root, store.logs_root, store.records_root]


@pytest.mark.parametrize(
    ("mode", "properties", "expected"),
    [
        ("missing", {"LoadState": "not-found", "ActiveState": "inactive"}, "missing"),
        ("lost", None, "lost"),
    ],
)
def test_nonterminal_absence_and_launch_failure_are_distinct_terminal_outcomes(
    tmp_path: Path, mode: str, properties: dict[str, str] | None, expected: str
) -> None:
    """Anti-vacuity: post-launch loss, missing units, and launch failures have distinct terminal records."""
    class FailingShow(FakeSystemdJobs):
        def show(self, unit: str) -> dict[str, str]:
            raise SystemdJobError("manager unavailable")

    systemd: FakeSystemdJobs = FailingShow() if mode == "lost" else FakeSystemdJobs(properties=properties or {})
    jobs = generic_jobs(tmp_path, systemd)
    status = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    status = jobs.get(status["job_id"])
    cancelled = jobs.cancel(status["job_id"])
    waited = jobs.wait(status["job_id"], timeout_seconds=1)
    assert status["state"]["phase"] == expected
    assert status["state"]["terminal"]
    assert cancelled["already_terminal"]
    assert not systemd.stopped
    assert waited["state"]["phase"] == expected


def test_start_returns_systemd_state_when_accepted_reply_is_lost(tmp_path: Path) -> None:
    """Anti-vacuity: an accepted transient unit must not become launch-failed when its reply is lost."""
    secret = "accepted-but-reply-lost"

    class ReplyLostAfterAccept(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            self.started.append(dict(kwargs))
            raise SystemdJobError(secret)

    jobs = generic_jobs(tmp_path, ReplyLostAfterAccept())

    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    persisted = (tmp_path / "state" / "jobs" / f"{started['job_id']}.json").read_text()

    assert started["state"]["phase"] == "running"
    assert started["state"]["systemd"]["LoadState"] == "loaded"
    assert secret not in persisted


def test_start_persists_launch_failed_only_when_systemd_confirms_absence(tmp_path: Path) -> None:
    """Anti-vacuity: a launch error alone is insufficient evidence that systemd rejected the unit."""
    secret = "confirmed-absent-launch-error"

    class ConfirmedAbsent(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            raise SystemdJobError(secret)

    jobs = generic_jobs(tmp_path, ConfirmedAbsent(properties={"LoadState": "not-found", "ActiveState": "inactive"}))

    with pytest.raises(SystemdJobError, match=secret):
        jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})

    record = jobs.store.list()[0]
    persisted = (tmp_path / "state" / "jobs" / f"{record.job_id}.json").read_text()
    assert record.state["phase"] == "launch-failed"
    assert record.state["error"] == {"code": "systemd-job-error"}
    assert secret not in persisted


@pytest.mark.parametrize("mode", ("lost", "launch-failed"))
def test_terminal_systemd_errors_persist_only_stable_codes(tmp_path: Path, mode: str) -> None:
    """Anti-vacuity: persisting a SystemdJobError message writes this fixture secret to disk."""
    secret = "systemd-error-secret-do-not-persist"

    class FailingShow(FakeSystemdJobs):
        def show(self, unit: str) -> dict[str, str]:
            raise SystemdJobError(secret)

    class FailingStart(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            raise SystemdJobError(secret)

    jobs = generic_jobs(
        tmp_path,
        FailingShow() if mode == "lost" else FailingStart(properties={"LoadState": "not-found", "ActiveState": "inactive"}),
    )
    if mode == "launch-failed":
        with pytest.raises(SystemdJobError, match=secret):
            jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
        record = jobs.store.list()[0]
        status = jobs.get(record.job_id)
    else:
        started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
        status = jobs.get(started["job_id"])

    persisted = (tmp_path / "state" / "jobs" / f"{status['job_id']}.json").read_text()

    assert status["state"]["phase"] == mode
    assert status["state"]["error"] == {"code": "systemd-job-error"}
    assert secret not in persisted
    assert '"message"' not in persisted


@pytest.mark.parametrize(
    ("terminal", "expected"),
    [
        ({"Result": "success", "ExecMainStatus": "0"}, "succeeded"),
        ({"Result": "exit-code", "ExecMainStatus": "1"}, "failed"),
        ({"Result": "timeout", "ExecMainStatus": "9"}, "timed_out"),
        ({"Result": "signal", "ExecMainStatus": "15", "InvocationID": "different-invocation"}, "failed"),
    ],
)
def test_cancel_persists_intent_and_preserves_systemd_exit_races(
    tmp_path: Path, terminal: dict[str, str], expected: str
) -> None:
    """Anti-vacuity: intent-only cancellation would relabel these terminal systemd results."""
    class TerminalDuringStop(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            self.properties = {
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "InvocationID": "fixture-invocation",
                **terminal,
            }

    class StopFails(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            raise SystemdJobError("stop interrupted")

    terminal_jobs = generic_jobs(
        tmp_path / expected,
        TerminalDuringStop(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}),
    )
    started = terminal_jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    cancelled = terminal_jobs.cancel(started["job_id"])
    assert cancelled["state"]["phase"] == expected
    assert terminal_jobs.store.load(started["job_id"]).cancel_stop_acknowledged_at is not None

    crashing = generic_jobs(tmp_path / "crash", StopFails(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}))
    started = crashing.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    with pytest.raises(SystemdJobError):
        crashing.cancel(started["job_id"])
    record = crashing.store.load(started["job_id"])
    assert record.cancel_requested_at is not None
    assert record.cancel_requested_invocation_id == "fixture-invocation"


def test_cancelled_missing_unit_requires_durable_stop_acknowledgement(tmp_path: Path) -> None:
    """Anti-vacuity: cancellation intent alone must leave an absent unit as missing."""
    class CollectedDuringStop(FakeSystemdJobs):
        def stop(self, unit: str) -> None:
            self.stopped.append(unit)
            self.properties = {"LoadState": "not-found", "ActiveState": "inactive"}

    systemd = CollectedDuringStop(
        properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}
    )
    jobs = generic_jobs(tmp_path / "acknowledged", systemd)
    started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    cancelled = jobs.cancel(started["job_id"])
    assert cancelled["state"]["phase"] == "cancelled"
    assert cancelled["state"]["cancellation"]["invocation_id"] == "fixture-invocation"

    missing_systemd = FakeSystemdJobs(
        properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}
    )
    missing_jobs = generic_jobs(tmp_path / "intent-only", missing_systemd)
    started = missing_jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = missing_jobs.store.load(started["job_id"])
    missing_jobs.store.save(missing_jobs._with_cancel_intent(record, "fixture-invocation"))
    missing_systemd.properties = {"LoadState": "not-found", "ActiveState": "inactive"}
    assert missing_jobs.get(started["job_id"])["state"]["phase"] == "missing"

    class CrashAfterStopStore(GenericJobStore):
        crash_on_acknowledgement: bool = False

        def save(self, record) -> None:
            if self.crash_on_acknowledgement and record.cancel_stop_acknowledged_at is not None:
                raise OSError("simulated daemon crash after systemd stop")
            super().save(record)

    crashing_systemd = CollectedDuringStop(
        properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}
    )
    crashing_store = CrashAfterStopStore(tmp_path / "ack-crash" / "state")
    crashing_jobs = GenericJobs(crashing_systemd, crashing_store, wait_poll_seconds=0.001)
    started = crashing_jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    crashing_store.crash_on_acknowledgement = True
    with pytest.raises(OSError, match="simulated daemon crash"):
        crashing_jobs.cancel(started["job_id"])
    persisted = crashing_store.load(started["job_id"])
    assert persisted.cancel_requested_at is not None
    assert persisted.cancel_stop_acknowledged_at is None
    assert crashing_jobs.get(started["job_id"])["state"]["phase"] == "missing"


def test_unix_socket_wait_saturation_reserves_cancel_get_logs_and_start(tmp_path: Path) -> None:
    """Anti-vacuity: running waits on control workers blocks socket RPCs at full wait capacity."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"})
    jobs = generic_jobs(tmp_path, systemd)
    wait_started = threading.Event()
    release_waits = threading.Event()
    wait_lock = threading.Lock()
    active_waits = 0

    def blocking_wait(job_id: str, timeout_seconds: int = 30) -> dict[str, object]:
        nonlocal active_waits
        with wait_lock:
            active_waits += 1
            if active_waits == server.wait_worker_count:
                wait_started.set()
        assert release_waits.wait(timeout=2)
        return jobs.get(job_id)

    jobs.wait = blocking_wait  # type: ignore[method-assign]
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    socket_path = tmp_path / "sinnixd.sock"
    stop_event = threading.Event()
    server = UnixSocketServer(socket_path, service, max_workers=8)
    thread = start_server(server, stop_event=stop_event)
    started = call(socket_path, request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}))
    job_id = started["payload"]["value"]["job_id"]
    wait_results: list[dict[str, object]] = []
    wait_errors: list[Exception] = []

    def run_wait() -> None:
        try:
            wait_results.append(call(socket_path, request("job.wait", "systemd-jobs", {"job_id": job_id, "timeout_seconds": 2})))
        except Exception as error:
            wait_errors.append(error)

    waiters = [threading.Thread(target=run_wait, daemon=True) for _ in range(server.wait_worker_count)]
    for waiter in waiters:
        waiter.start()
    assert wait_started.wait(timeout=1)
    response = call(socket_path, request("job.cancel", "systemd-jobs", {"job_id": job_id}))
    get = call(socket_path, request("job.get", "systemd-jobs", {"job_id": job_id}))
    logs = call(socket_path, request("job.logs", "systemd-jobs", {"job_id": job_id, "max_bytes": 1}))
    next_job = call(socket_path, request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}))
    release_waits.set()
    for waiter in waiters:
        waiter.join(timeout=1)
    stop_event.set()
    thread.join(timeout=1)
    assert response["ok"] and get["ok"] and logs["ok"]
    assert next_job["ok"]
    assert next_job["payload"]["value"]["job_id"] != job_id
    assert not wait_errors
    assert all(not waiter.is_alive() for waiter in waiters)
    assert len(wait_results) == server.wait_worker_count
    assert all(result["payload"]["value"]["state"]["phase"] == "cancelled" for result in wait_results)


def test_job_rpc_get_list_wait_logs_and_cancel_share_one_record(tmp_path: Path) -> None:
    """Anti-vacuity: deleting any RPC route prevents its shared job ID from resolving."""
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(
        properties={"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd))
    started = service.dispatch(request("job.start", "systemd-jobs", {"project_id": "fixture", "operation": "check"}))
    assert started.payload is not None
    job_id = started.payload.inline["job_id"]

    get = service.dispatch(request("job.get", "systemd-jobs", {"job_id": job_id}))
    listed = service.dispatch(request("job.list", "systemd-jobs"))
    waited = service.dispatch(request("job.wait", "systemd-jobs", {"job_id": job_id, "timeout_seconds": 1}))
    logs = service.dispatch(request("job.logs", "systemd-jobs", {"job_id": job_id, "max_bytes": 10}))
    cancelled = service.dispatch(request("job.cancel", "systemd-jobs", {"job_id": job_id}))

    assert all(response.ok for response in (get, listed, waited, logs, cancelled))
    assert listed.payload is not None
    assert listed.payload.inline["jobs"][0]["job_id"] == job_id
    assert cancelled.payload is not None
    assert cancelled.payload.inline["already_terminal"]


def test_real_user_systemd_service_cgroup_cancels_descendants(tmp_path: Path) -> None:
    """Anti-vacuity: this enters systemd-run/systemctl; replacing the launcher with a subprocess leaves the child alive."""
    if shutil.which("systemd-run") is None or shutil.which("systemctl") is None:
        pytest.skip("systemd user tools are unavailable")
    manager = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True, check=False)
    if manager.returncode != 0:
        pytest.skip("a usable user systemd manager is unavailable")

    child_pid = tmp_path / "child.pid"
    script = tmp_path / "spawn-child.sh"
    script.write_text("#!/bin/sh\nsleep 30 &\necho $! > \"$1\"\necho lifecycle-output\nwait\n")
    script.chmod(0o700)
    jobs = GenericJobs(UserSystemdJobs(), GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.05)
    started: dict[str, object] | None = None
    try:
        started = jobs.start_foreground(
            command=("/bin/sh", str(script), str(child_pid)),
            working_directory=str(tmp_path),
            environment=build_environment(source=os.environ),
            timeout_seconds=60,
        )
        deadline = time.monotonic() + 5
        while not child_pid.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert child_pid.exists()
        status = jobs.get(str(started["job_id"]))
        assert status["state"]["systemd"]["ControlGroup"].endswith(str(started["unit"]))

        cancelled = jobs.cancel(str(started["job_id"]))
        terminal = jobs.wait(str(started["job_id"]), timeout_seconds=5)
        pid = int(child_pid.read_text().strip())
        assert cancelled["cancel_requested"]
        assert terminal["state"]["phase"] == "cancelled"
        assert not Path(f"/proc/{pid}").exists()
    finally:
        if started is not None:
            try:
                UserSystemdJobs().stop(str(started["unit"]))
            except SystemdJobError:
                pass


def test_source_scoped_owner_adapter_is_registered_and_forwards_exact_response(tmp_path: Path) -> None:
    write_owner_adapter(tmp_path)
    source = SourceBinding(
        source_ref=SinnixRef.parse("sinnix://polylogue/archive"),
        generation="fixture-generation",
        root_digest="sha256:" + "1" * 64,
    )
    request_value = request(
        "polylogue.archive.status",
        "polylogue-archive",
        {"scope": "archive"},
    )
    owner_response = ResponseEnvelope(
        request_id=request_value.request_id,
        correlation_id=request_value.correlation_id,
        owner="polylogue-archive",
        payload=OpaquePayload.bounded({"archive": {"sessions": 2}}),
        source_bindings=(source,),
    )
    adapters = FakeOwnerAdapters(owner_response)
    service = SinnixdService(ProjectCatalog([tmp_path]), owner_adapters=adapters)

    response = service.dispatch(request_value)

    assert response == owner_response
    assert service.owners.resolve("polylogue.archive.status").source_scoped
    assert adapters.calls[0]["adapter"].source_ref == source.source_ref
    assert adapters.calls[0]["project"].project_id == "fixture"

    wrong_owner = service.dispatch(
        request("polylogue.archive.status", "wrong-owner", {"scope": "archive"})
    )
    assert wrong_owner.error is not None
    assert wrong_owner.error.code.value == "AUTHORITY_MISMATCH"


def test_owner_adapters_reject_duplicate_authority_namespaces(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_owner_adapter(first)
    write_owner_adapter(second)
    descriptor = second / ".agentctl" / "project.toml"
    descriptor.write_text(descriptor.read_text().replace('id = "fixture"', 'id = "second"'))

    with pytest.raises(ProjectConfigError, match="duplicate owner namespace"):
        SinnixdService(ProjectCatalog([first, second]))


def test_declared_owner_adapter_runs_fixed_command_and_enforces_source_binding(tmp_path: Path) -> None:
    write_owner_adapter(tmp_path)
    project, adapter = ProjectCatalog([tmp_path]).owner_adapter("polylogue.archive.status")
    source = SourceBinding(
        source_ref=SinnixRef.parse("sinnix://polylogue/archive"),
        generation="fixture-generation",
        root_digest="sha256:" + "2" * 64,
    )
    request_value = request(
        "polylogue.archive.status",
        "polylogue-archive",
        {"scope": "archive", "expected_source_binding": source.to_dict()},
    )
    response = ResponseEnvelope(
        request_id=request_value.request_id,
        correlation_id=request_value.correlation_id,
        owner="polylogue-archive",
        payload=OpaquePayload.bounded({"archive": {"sessions": 2}}),
        source_bindings=(source,),
    )
    execution = FakeExecution(
        ExecutionResult(
            command=(),
            exit_status=0,
            stdout=json.dumps(response.to_dict()).encode(),
            stderr=b"",
        )
    )

    result = DeclaredOwnerAdapters(execution).call(
        project=project,
        adapter=adapter,
        request=request_value,
    )

    command, profile = execution.calls[0]
    forwarded = json.loads(profile.stdin_bytes)
    assert result == response
    assert command[:7] == (
        "/run/current-system/sw/bin/systemd-run",
        "--user",
        "--quiet",
        "--collect",
        "--wait",
        "--pipe",
        f"--unit=sinnixd-owner-{request_value.request_id}.service",
    )
    assert command[-3:] == ("fixture-env", "--command", "polylogue-agentctl-adapter")
    assert forwarded["arguments"] == {"scope": "archive"}

    wrong_precondition = request(
        "polylogue.archive.status",
        "polylogue-archive",
        {
            "scope": "archive",
            "expected_source_binding": {
                **source.to_dict(),
                "source_ref": "sinnix://polylogue/other",
            },
        },
    )
    with pytest.raises(OwnerAdapterError, match="different source"):
        DeclaredOwnerAdapters(execution).call(
            project=project,
            adapter=adapter,
            request=wrong_precondition,
        )
    assert len(execution.calls) == 1

    wrong_source = ResponseEnvelope(
        request_id=request_value.request_id,
        correlation_id=request_value.correlation_id,
        owner="polylogue-archive",
        payload=OpaquePayload.bounded({"archive": {"sessions": 2}}),
        source_bindings=(
            SourceBinding(
                source_ref=SinnixRef.parse("sinnix://polylogue/other"),
                generation=source.generation,
                root_digest=source.root_digest,
            ),
        ),
    )
    execution.result = ExecutionResult(
        command=(),
        exit_status=0,
        stdout=json.dumps(wrong_source.to_dict()).encode(),
        stderr=b"",
    )
    with pytest.raises(OwnerAdapterError, match="wrong source"):
        DeclaredOwnerAdapters(execution).call(
            project=project,
            adapter=adapter,
            request=request_value,
        )


def test_unix_socket_server_round_trips_the_common_envelope(tmp_path: Path) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    service = SinnixdService(ProjectCatalog([tmp_path / "project"]))
    server = UnixSocketServer(socket_path, service)
    thread = start_server(server, once=True)

    response = call(socket_path, request("runtime.status", "sinnixd"))
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert response["ok"]
    assert response["payload"]["value"]["projects"] == 1


def test_unix_socket_server_returns_json_rpc_errors_without_crashing(tmp_path: Path) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    server = UnixSocketServer(socket_path, SinnixdService(ProjectCatalog([tmp_path / "project"])))
    thread = start_server(server, once=True)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(socket_path))
        send_frame(
            connection,
            {
                "jsonrpc": "2.0",
                "id": "not-a-request-id",
                "method": "wrong-method",
                "params": {},
            },
        )
        response = receive_frame(connection)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert response == {
        "jsonrpc": "2.0",
        "id": "not-a-request-id",
        "error": {
            "code": -32600,
            "message": "request must be a JSON-RPC 2.0 dispatch call",
        },
    }


def test_unix_socket_server_continues_after_malformed_and_stalled_clients(tmp_path: Path) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    server = UnixSocketServer(
        socket_path,
        SinnixdService(ProjectCatalog([tmp_path / "project"])),
        connection_timeout_seconds=0.05,
    )
    stop_event = threading.Event()
    thread = start_server(server, stop_event=stop_event)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(socket_path))
        connection.sendall(b"\x00\x00")
        threading.Event().wait(0.1)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(socket_path))
        send_frame(
            connection,
            {
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "method": "dispatch",
                "params": {
                    "schema": 1,
                    "request_id": str(uuid4()),
                    "correlation_id": str(uuid4()),
                    "operation": "project.list",
                    "owner": "project-adapters",
                    "principal": "test",
                    "arguments": [["project_id", "fixture"]],
                    "idempotency_key": None,
                },
            },
        )
        malformed = receive_frame(connection)

    assert malformed["error"]["code"] == -32600
    assert malformed["error"]["message"] == "arguments must be an object"

    response = call(socket_path, request("runtime.status", "sinnixd"))
    stop_event.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert response["ok"]
