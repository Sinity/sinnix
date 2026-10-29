"""Jobs over pueue: the launch input, the label, the artifacts, and the reads."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import subprocess
import threading
from dataclasses import replace
from pathlib import Path
from typing import Callable

import pytest
from agentctl import artifacts, job_queries, launch, pueue
from agentctl import run as run_module
from agentctl.config import Config, load_config
from agentctl.job_queries import JobError
from agentctl.launch_input import write_input
from agentctl.projects import load_project_adapter
from agentctl.pueue import PueueError, PueueGroupError, Task
from agentctl.run import (
    CANCELLED_EXIT_CODE,
    REFUSED_EXIT_CODE,
    SLOT_OCCUPIED_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    VANISHED_EXIT_CODE,
    cancel_marker_for,
    outcome_path_for,
    unit_for,
)
from agentctl.run import (
    main as run_main,
)
from conftest import FakePueue, begin_attempt, read_launch


def test_declared_operation_limits_reach_its_queued_launch(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    descriptor = project_root / ".agentctl/project.toml"
    limits = ["MemoryMax=3G", "IOReadBandwidthMax=/realm 20M"]
    descriptor.write_text(
        descriptor.read_text().replace(
            'exec = ["fixture-verify"]',
            'exec = ["fixture-verify"]\nunit_properties=' + json.dumps(limits),
        )
    )
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("verify"))
    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["unit_properties"] == limits


def test_invalid_launch_input_preserves_existing_private_bytes(tmp_path: Path) -> None:
    path = tmp_path / "launch.json"
    path.write_bytes(b"original")
    path.chmod(0o644)

    with pytest.raises(TypeError):
        write_input(path, {"invalid": object()})

    assert path.read_bytes() == b"original"
    assert path.stat().st_mode & 0o777 == 0o644
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_start_writes_the_launch_input_and_queues_the_wrapper_in_the_pool(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """Breaks if the argv, pool, label or artifact paths stop coming from the descriptor."""
    project = load_project_adapter(project_root)

    started = launch.start_operation(config, project, project.operation("verify"))

    added = fake_pueue.added[0]
    assert added["group"] == "pytest"
    assert added["label"] == "fixture:verify"
    assert added["command"][0] == "agentctl-run"
    assert added["working_directory"] == project_root
    assert read_launch(config, fake_pueue.task(started["task_id"]))[
        "project_root"
    ] == str(project_root)
    input_path = Path(added["command"][1])
    assert input_path.stat().st_mode & 0o777 == 0o600
    written = json.loads(input_path.read_text())
    assert written["argv"] == ["env", "fixture-verify"]
    assert written["timeout_seconds"] == 120
    assert written["pool"] == "pytest"
    assert job_queries.unit_of(fake_pueue.task(1)) == unit_for(input_path, "pytest")
    assert written["result_kind"] == "json"
    assert written["result_path"].endswith(".result")
    assert written["event_spool_path"] == str(config.event_spool)
    assert written["environment"]["GIT_OPTIONAL_LOCKS"] == "0"
    assert "PATH" in written["environment"]
    assert started["task_id"] == 1
    assert started["phase"] == "running"
    assert started["project"] == "fixture"
    assert started["operation"] == "verify"
    assert started["kind"] == "declared-operation"


def test_operation_started_by_an_agent_preserves_its_routing_principal(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTCTL_PRINCIPAL", "agent-control")
    monkeypatch.setenv("AGENTCTL_LANE_BEAD", "fx-1")
    project = load_project_adapter(project_root)

    started = launch.start_operation(config, project, project.operation("check"))

    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["environment"]["AGENTCTL_PRINCIPAL"] == "agent-control"
    assert written["environment"]["AGENTCTL_LANE_BEAD"] == "fx-1"


def test_extra_argv_is_appended_after_the_declared_exec(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)

    started = launch.start_operation(
        config, project, project.operation("check"), extra_argv=("--apply",)
    )

    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["argv"] == ["env", "true", "--apply"]


def test_an_argument_requiring_operation_is_refused_without_supplied_argv(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exec = ["true"]',
            'exec = ["true"]\narguments = "required"',
        )
    )
    project = load_project_adapter(project_root)
    with pytest.raises(JobError, match='arguments = "required"'):
        launch.start_operation(config, project, project.operation("check"))
    with pytest.raises(JobError, match='arguments = "required"'):
        launch.start_operation(
            config, project, project.operation("check"), extra_argv=(" ",)
        )
    started = launch.start_operation(
        config, project, project.operation("check"), extra_argv=("--sel",)
    )
    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["argv"] == ["env", "true", "--sel"]


def test_cached_operation_reuses_an_active_and_completed_exact_receipt(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            '[operations.verify]\ndescription = "Fixture typed verification"',
            '[operations.verify]\ndescription = "Fixture typed verification"\ncache = "tree+environment"',
        )
    )
    monkeypatch.setattr(
        launch,
        "_git",
        lambda path, *arguments: {
            ("rev-parse", "HEAD"): "a" * 40,
            ("rev-parse", "HEAD^{tree}"): "b" * 40,
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
        }[arguments],
    )
    project = load_project_adapter(project_root)

    first = launch.start_operation(config, project, project.operation("verify"))
    second = launch.start_operation(config, project, project.operation("verify"))
    fake_pueue.succeed(first["task_id"])
    _write_execution_attempt(
        config, fake_pueue.task(first["task_id"]), "a" * 40, "b" * 40
    )
    third = launch.start_operation(config, project, project.operation("verify"))

    assert len(fake_pueue.added) == 1
    assert second["task_id"] == first["task_id"]
    assert third["task_id"] == first["task_id"]
    assert second["reused"] is True and third["reused"] is True
    written = read_launch(config, fake_pueue.task(first["task_id"]))
    assert written["tree_receipt"] == {
        "head": "a" * 40,
        "tree": "b" * 40,
        "dirty": False,
    }
    assert written["environment_receipt"]["digest"].startswith("sha256:")


def _write_execution_attempt(config: Config, task: Task, head: str, tree: str) -> None:
    launch_input = read_launch(config, task)
    input_path = job_queries.launch_input_path(task)
    assert input_path is not None
    attempt_dir = artifacts.root_for(Path(launch_input["log_path"])) / "1"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "attempt.json").write_text(
        json.dumps({"attempt": 1, "launch_input": str(input_path)})
    )
    observation = {
        "status": "observed",
        "head": head,
        "tree": tree,
        "dirty": False,
    }
    environment_identity = hashlib.sha256(
        json.dumps(launch_input["environment"], sort_keys=True).encode()
    ).hexdigest()
    (attempt_dir / "output.outcome").write_text(
        json.dumps(
            {
                "attempt": 1,
                "outcome": "success",
                "execution_receipt": {
                    "binding": "unchanged_endpoints",
                    "start": observation,
                    "end": observation,
                },
                "execution_evidence": {
                    "environment_identity": environment_identity,
                },
            }
        )
    )


def test_cached_operation_retries_success_that_executed_on_another_tree(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            '[operations.verify]\ndescription = "Fixture typed verification"',
            '[operations.verify]\ndescription = "Fixture typed verification"\ncache = "tree+environment"',
        )
    )
    state = {"head": "a" * 40, "tree": "b" * 40}
    monkeypatch.setattr(
        launch,
        "_git",
        lambda path, *arguments: (
            state["head"]
            if arguments == ("rev-parse", "HEAD")
            else state["tree"]
            if arguments == ("rev-parse", "HEAD^{tree}")
            else ""
        ),
    )
    project = load_project_adapter(project_root)
    first = launch.start_operation(config, project, project.operation("verify"))
    fake_pueue.succeed(first["task_id"])
    _write_execution_attempt(
        config, fake_pueue.task(first["task_id"]), "c" * 40, "d" * 40
    )
    attempted = launch.successful_cached_attempt(
        config,
        fake_pueue.task(first["task_id"]),
        {"head": "a" * 40, "tree": "b" * 40, "dirty": False},
        None,
    )
    assert attempted is None
    # The checkout returns to A before the request. Enqueue identity still
    # matches, but the pinned attempt proves it actually ran on C.
    state.update(head="a" * 40, tree="b" * 40)

    retried = launch.start_operation(config, project, project.operation("verify"))

    assert retried["task_id"] != first["task_id"]
    assert len(fake_pueue.added) == 2
    assert fake_pueue.task(first["task_id"]).succeeded
    assert read_launch(config, fake_pueue.task(first["task_id"]))["tree_receipt"] == {
        "head": "a" * 40,
        "tree": "b" * 40,
        "dirty": False,
    }


def test_a_default_checkout_operation_refuses_a_worktree(
    fake_pueue: FakePueue, config: Config, project_root: Path, tmp_path: Path
) -> None:
    """The corpus run belongs to the master boundary; a lane cannot start it."""
    project = load_project_adapter(project_root)
    worktree = tmp_path / "worktrees" / "fixture-lane"
    worktree.mkdir(parents=True)

    with pytest.raises(JobError, match="main checkout"):
        launch.start_operation(
            config, project, project.operation("nightly"), workspace=worktree
        )
    assert fake_pueue.added == []


def test_an_unknown_pool_is_a_typed_refusal_and_leaves_no_input_behind(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    fake_pueue.groups.pop("pytest")

    with pytest.raises(PueueGroupError):
        launch.start_operation(config, project, project.operation("verify"))

    assert list(config.inputs_dir.glob("*")) == []


@pytest.mark.parametrize("running", [False, True])
def test_active_tasks_name_an_operation_queued_or_running(
    fake_pueue: FakePueue, config: Config, project_root: Path, running: bool
) -> None:
    """What `job start --if-idle` reads to skip a timer's launch."""
    project = load_project_adapter(project_root)
    operation = project.operation("check")

    first = launch.start_operation(config, project, operation)
    if running:
        fake_pueue.running(first["task_id"])
    else:
        fake_pueue.queue(first["task_id"])
    assert launch.active_tasks(project, operation) == [first["task_id"]]
    fake_pueue.succeed(first["task_id"])
    assert launch.active_tasks(project, operation) == []


def test_phases_come_from_pueue_results_and_the_wrapper_exit_codes(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    ids = [
        launch.start_operation(config, project, project.operation("check"))["task_id"]
        for _ in range(9)
    ]
    fake_pueue.succeed(ids[0])
    fake_pueue.fail(ids[1], exit_code=3)
    fake_pueue.fail(ids[2], exit_code=TIMEOUT_EXIT_CODE)
    fake_pueue.fail(ids[3], exit_code=REFUSED_EXIT_CODE)
    fake_pueue.kill_directly(ids[4])
    fake_pueue.queue(ids[5])
    fake_pueue.fail(ids[6], exit_code=CANCELLED_EXIT_CODE)
    fake_pueue.fail(ids[7], exit_code=VANISHED_EXIT_CODE)
    fake_pueue.fail(ids[8], exit_code=SLOT_OCCUPIED_EXIT_CODE)

    phases = [job_queries.get_job(task_id)["phase"] for task_id in ids]

    assert phases == [
        "succeeded",
        "failed",
        "timeout",
        "refused",
        "cancelled",
        "queued",
        "cancelled",
        "vanished",
        "slot_occupied",
    ]


def test_logs_and_result_are_read_by_the_job_id_in_the_task_command(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """No ledger maps task ids to artifacts; the task's own command line does."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("verify"))
    written = read_launch(config, fake_pueue.task(started["task_id"]))
    artifacts.begin(written, "fixture-input")
    Path(written["log_path"]).write_text("ran\n")
    Path(written["result_path"]).write_text('{"passed": 3}')
    outcome_path_for(written["log_path"]).write_text('{"outcome": "success"}')
    fake_pueue.set_log(started["task_id"], "wrapper stderr")
    fake_pueue.succeed(started["task_id"])

    assert "ran" in job_queries.logs(config, started["task_id"])
    assert "wrapper stderr" in job_queries.logs(config, started["task_id"])
    outcome = job_queries.result(config, started["task_id"])
    assert outcome["kind"] == "artifact"
    assert outcome["value"] == {"passed": 3}
    assert outcome["phase"] == "succeeded"
    assert outcome["outcome"] == {"outcome": "success"}


def test_result_of_an_exit_operation_is_the_status_alone(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.succeed(started["task_id"])

    outcome = job_queries.result(config, started["task_id"])

    assert outcome["kind"] == "exit" and outcome["value"] is None
    assert outcome["exit_code"] == 0


def test_result_of_an_exit_operation_keeps_the_wrapper_execution_receipt(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(started["task_id"])
    written = read_launch(config, task)
    artifacts.begin(written, "fixture-input")
    outcome_path_for(written["log_path"]).write_text(
        json.dumps(
            {
                "outcome": "success",
                "exit_code": 0,
                "execution_receipt": {"binding": "unchanged_endpoints"},
            }
        )
    )
    fake_pueue.succeed(started["task_id"])

    result = job_queries.result(config, started["task_id"])

    assert result["kind"] == "exit"
    assert result["outcome"]["execution_receipt"]["binding"] == "unchanged_endpoints"


def test_cancel_marks_then_stops_the_unit_then_kills_the_task(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    recording_systemctl: Callable[[], list[list[str]]],
) -> None:
    """`systemctl stop` ends the wrapper's wait with a success status, so the
    marker written before it is the only record that this was a cancel."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(started["task_id"])
    unit = job_queries.unit_of(task)
    marker = cancel_marker_for(read_launch(config, task)["log_path"])

    cancelled = launch.cancel(config, started["task_id"], settle_seconds=0)

    assert marker.exists()
    assert fake_pueue.killed == [started["task_id"]]
    calls = recording_systemctl()
    assert ["systemctl", "--user", "stop", unit] in calls
    assert ["systemctl", "--user", "show", "-p", "LoadState,ActiveState", unit] in calls
    assert cancelled["state"] == "unresolved"
    assert cancelled["unresolved"] is True
    assert cancelled["unit"] == unit
    assert cancelled["phase"] == "cancelled"


def test_running_cancel_records_request_before_stopping_and_keeps_retry_identity(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    recording_systemctl: Callable[[], list[list[str]]],
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(started["task_id"])
    document = read_launch(config, task)
    first = artifacts.begin(document, str(job_queries.launch_input_path(task)))

    cancelled = launch.cancel(
        config,
        started["task_id"],
        actor="fixture-worker",
        reason="stop requested",
        settle_seconds=0,
    )
    request = json.loads(
        artifacts.cancellation_path(Path(document["log_path"]), 1).read_text()
    )
    assert (
        request["actor"] == "fixture-worker" and request["reason"] == "stop requested"
    )
    assert request["uid"] == os.getuid() and request["attempt"] == 1
    assert request["requested_at"]
    assert cancelled["cancellation"] == request
    assert cancelled["already_terminal"] is False
    assert (
        job_queries.get_job(started["task_id"], config, attempt=1)["cancellation"]
        == request
    )

    outcome = Path(first["log_path"]).with_name("output.outcome")
    outcome.write_text(json.dumps({"outcome": "cancelled", "exit_code": 130}))
    fake_pueue.restart(started["task_id"])
    fake_pueue.running(started["task_id"])
    fake_pueue._set(started["task_id"], started_at="2026-09-03T08:00:02+00:00")
    second = artifacts.begin(document, str(job_queries.launch_input_path(task)))
    assert second["attempt"] == 2
    launch.cancel(
        config,
        started["task_id"],
        actor="fixture-reviewer",
        reason="second request",
        settle_seconds=0,
    )
    assert (
        job_queries.get_job(started["task_id"], config, attempt=1)["cancellation"]
        == request
    )
    assert (
        job_queries.get_job(started["task_id"], config, attempt=2)["cancellation"][
            "actor"
        ]
        == "fixture-reviewer"
    )


def test_cancel_refuses_to_stop_when_request_evidence_cannot_be_written(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    recording_systemctl: Callable[[], list[list[str]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    original = launch.write_input

    def deny_request(path: Path, document: object) -> None:
        if path.name.endswith(".cancel-request.json"):
            raise PermissionError("fixture request storage denied")
        original(path, document)

    monkeypatch.setattr(launch, "write_input", deny_request)
    with pytest.raises(JobError, match="cannot record cancellation requester"):
        launch.cancel(
            config,
            started["task_id"],
            actor="fixture-worker",
            reason="stop requested",
            settle_seconds=0,
        )
    assert not fake_pueue.killed
    assert not any("stop" in call for call in recording_systemctl())


def test_default_cancel_actor_uses_os_identity_not_user_environment(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(started["task_id"])
    monkeypatch.setenv("USER", "unverified-label")
    cancelled = launch.cancel(config, started["task_id"])
    assert cancelled["cancellation"]["actor"] == pwd.getpwuid(os.getuid()).pw_name
    assert cancelled["cancellation"]["reason"] is None
    assert (
        job_queries.get_job(started["task_id"], config, started["job_id"])[
            "cancellation"
        ]
        == cancelled["cancellation"]
    )


def test_cancel_request_round_trips_the_declared_unicode_limit(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(started["task_id"])
    reason = "\U0001f642" * 4096
    cancelled = launch.cancel(
        config, started["task_id"], actor="fixture-worker", reason=reason
    )
    observed = job_queries.get_job(started["task_id"], config, started["job_id"])
    assert observed["cancellation"]["reason"] == reason
    assert observed["cancellation"] == cancelled["cancellation"]
    assert observed["attempt_count"] == 0


def test_cancel_waits_for_inflight_service_creation_then_stops_unit(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation serializes with systemd admission and reports unknown state."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(started["task_id"])
    written = read_launch(config, task)
    marker = cancel_marker_for(written["log_path"])
    artifacts.root_for(Path(written["log_path"])).mkdir(parents=True)
    unit = job_queries.unit_of(task)
    admission_entered = threading.Event()
    allow_admission = threading.Event()
    cancel_lock_attempted = threading.Event()
    cancel_finished = threading.Event()
    sequence: list[str] = []
    stopped_units: list[str] = []
    cancellation: list[dict[str, object]] = []
    errors: list[BaseException] = []
    real_flock = fcntl.flock

    def observed_flock(fd: int, operation: int) -> None:
        if (
            operation == fcntl.LOCK_EX
            and threading.current_thread().name == "cancel-inflight-service"
        ):
            cancel_lock_attempted.set()
        real_flock(fd, operation)

    def fake_run(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv[0] == "systemd-run":
            admission_entered.set()
            if not allow_admission.wait(5):
                raise AssertionError("test did not release the admission barrier")
            sequence.append("admitted")
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv[:3] == ["systemctl", "--user", "stop"]:
            sequence.append("stop")
            stopped_units.append(argv[3])
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv[:3] == ["systemctl", "--user", "show"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="unavailable")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(fcntl, "flock", observed_flock)
    monkeypatch.setattr(run_module.subprocess, "run", fake_run)

    def start_service() -> None:
        try:
            client = run_module._start_service(
                ["systemd-run", "--quiet"], marker, 1, None
            )
            assert client is not None and client.returncode == 0
        except BaseException as error:
            errors.append(error)

    def cancel() -> None:
        try:
            cancellation.append(
                launch.cancel(config, started["task_id"], settle_seconds=0)
            )
        except BaseException as error:
            errors.append(error)
        finally:
            cancel_finished.set()

    runner = threading.Thread(target=start_service, name="service-admission")
    canceller = threading.Thread(target=cancel, name="cancel-inflight-service")
    runner.start()
    assert admission_entered.wait(5), errors
    canceller.start()
    assert cancel_lock_attempted.wait(5)
    assert not marker.exists()
    assert sequence == []
    assert not cancel_finished.is_set()

    allow_admission.set()
    runner.join(5)
    canceller.join(5)

    assert not runner.is_alive() and not canceller.is_alive()
    assert errors == []
    assert sequence == ["admitted", "stop"]
    assert stopped_units == [unit]
    assert json.loads(marker.read_text()) == {"attempt": 1}
    assert fake_pueue.killed == [started["task_id"]]
    assert cancellation[0]["state"] == "incomplete"
    assert cancellation[0]["unresolved"] is True


def test_cancel_fails_when_the_unit_is_still_active_afterwards(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "live-systemctl"
    directory.mkdir()
    (directory / "systemctl").write_text("#!/bin/sh\nexit 0\n")
    (directory / "systemctl").chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))

    cancelled = launch.cancel(config, started["task_id"], settle_seconds=0)

    assert cancelled["state"] == "incomplete"
    assert cancelled["unresolved"] is True


@pytest.mark.parametrize(
    ("properties", "expected"),
    [
        ("LoadState=not-found\n", "stopped"),
        ("LoadState=loaded\nActiveState=inactive\n", "stopped"),
        ("LoadState=loaded\nActiveState=active\n", "failed"),
        ("", "unresolved"),
    ],
)
def test_cancel_unit_state_requires_observed_inactivity(
    monkeypatch: pytest.MonkeyPatch, properties: str, expected: str
) -> None:
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout=properties
        ),
    )

    assert launch._unit_state("fixture.service") == expected


def test_cancel_lets_the_wrapper_record_the_outcome_before_any_kill(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    recording_systemctl: Callable[[], list[list[str]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stopping the unit ends the wrapper's wait; it records `cancelled`,
    consumes the marker and exits. Killing it first would lose the record."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task_id = started["task_id"]
    task = fake_pueue.task(task_id)
    log = Path(read_launch(config, task)["log_path"])
    marker = cancel_marker_for(log)
    polls: list[int] = []
    real_task = fake_pueue.task

    def wrapper_exits_on_third_poll(asked: int) -> Task | None:
        # Polls: the cancel's own read, one after the stop, one after a sleep.
        polls.append(asked)
        if len(polls) == 3:
            assert marker.exists(), "the marker must precede the stop"
            outcome_path_for(log).parent.mkdir(parents=True, exist_ok=True)
            outcome_path_for(log).write_text(
                json.dumps({"outcome": "cancelled", "exit_code": 130})
            )
            marker.unlink()
            fake_pueue.fail(task_id, exit_code=CANCELLED_EXIT_CODE)
        return real_task(asked)

    monkeypatch.setattr(launch.pueue, "task", wrapper_exits_on_third_poll)
    slept: list[float] = []

    cancelled = launch.cancel(
        config, task_id, settle_seconds=15, sleep=lambda seconds: slept.append(seconds)
    )

    assert fake_pueue.killed == []
    assert slept == [launch.CANCEL_POLL_SECONDS]
    assert not marker.exists()
    assert cancelled["phase"] == "cancelled" and cancelled["state"] == "unresolved"
    assert cancelled["outcome"] == {"outcome": "cancelled", "exit_code": 130}
    stop = ["systemctl", "--user", "stop", job_queries.unit_of(task)]
    assert stop in recording_systemctl()


def test_cancel_kills_a_wrapper_that_does_not_settle_in_time(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    recording_systemctl: Callable[[], list[list[str]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    clock = iter([0.0, 0.0, 20.0, 20.0])
    monkeypatch.setattr(launch.time, "monotonic", lambda: next(clock))
    slept: list[float] = []

    cancelled = launch.cancel(
        config, started["task_id"], settle_seconds=1, sleep=slept.append
    )

    assert slept == [launch.CANCEL_POLL_SECONDS]
    assert fake_pueue.killed == [started["task_id"]]
    assert cancelled["phase"] == "cancelled" and "outcome" not in cancelled


def test_the_launch_input_records_the_task_id_pueue_assigned(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["queue_task_id"] == started["task_id"]


def test_clean_finds_a_task_pueue_forgot_by_its_launch_input(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("verify"))
    task = fake_pueue.task(started["task_id"])
    written = read_launch(config, task)
    for key in ("log_path", "result_path"):
        Path(written[key]).parent.mkdir(parents=True, exist_ok=True)
        Path(written[key]).write_text("x")
    input_path = job_queries.launch_input_path(task)
    fake_pueue.remove([started["task_id"]])

    cleaned = launch.clean(config, started["task_id"], started["job_id"])

    assert cleaned["cleaned"] and cleaned["task_id"] == started["task_id"]
    assert cleaned["removed"] == []
    assert input_path.exists()
    assert Path(written["log_path"]).read_text() == "x"
    assert Path(written["result_path"]).read_text() == "x"
    assert launch.clean(config, started["task_id"], started["job_id"])["retained"]


def test_clean_leaves_the_launch_input_of_a_job_the_queue_moved(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """A vacant id is no evidence that the job written there is gone.

    Anti-vacuity: selecting the input by the id it recorded deletes a queued
    job's own launch input, and that job then fails with an unusable launch
    file when the queue reaches it.
    """
    project = load_project_adapter(project_root)
    survivor = launch.start_operation(config, project, project.operation("verify"))
    doomed = launch.start_operation(config, project, project.operation("verify"))
    fake_pueue.queue(survivor["task_id"])
    fake_pueue.queue(doomed["task_id"])
    written = read_launch(config, fake_pueue.task(survivor["task_id"]))
    assert written["queue_task_id"] == survivor["task_id"]
    survivor_input = config.inputs_dir / f"{survivor['job_id']}.json"

    # The operator prioritises the queue, then drops the other job, leaving
    # the id the survivor recorded vacant while the survivor is still queued.
    fake_pueue.switch(survivor["task_id"], doomed["task_id"])
    vacated = survivor["task_id"]
    fake_pueue.remove([vacated])

    with pytest.raises(JobError, match="pueue has no task"):
        launch.clean(config, vacated)

    assert survivor_input.exists(), "the queued job lost its own launch input"
    assert job_queries.get_job(doomed["task_id"])["job_id"] == survivor["job_id"]


def test_clean_by_reference_removes_only_the_named_queue_entry(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """A job_id names one job's artifacts wherever the queue put the job."""
    project = load_project_adapter(project_root)
    first = launch.start_operation(config, project, project.operation("verify"))
    second = launch.start_operation(config, project, project.operation("verify"))
    fake_pueue.queue(first["task_id"])
    fake_pueue.queue(second["task_id"])
    fake_pueue.switch(first["task_id"], second["task_id"])
    fake_pueue.succeed(second["task_id"])

    cleaned = launch.clean(config, first["task_id"], first["job_id"])

    assert cleaned["job_id"] == first["job_id"]
    assert (config.inputs_dir / f"{first['job_id']}.json").exists()
    assert (config.inputs_dir / f"{second['job_id']}.json").exists()
    assert fake_pueue.removed == [second["task_id"]]


def test_clean_refuses_a_reference_that_is_not_one(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """The job_id names a file under inputs/, so it is never a path."""
    with pytest.raises(JobError, match="is not a job id"):
        launch.clean(config, 1, "../../etc/passwd")


def test_a_read_by_reference_answers_about_that_job_after_a_reorder(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """Status, result, log and cancellation follow the job, not the position.

    Anti-vacuity: the same calls without the job_id answer about whatever
    the switch moved to that id, which the sibling test pins.
    """
    project = load_project_adapter(project_root)
    first = launch.start_operation(config, project, project.operation("verify"))
    second = launch.start_operation(config, project, project.operation("verify"))
    fake_pueue.queue(first["task_id"])
    fake_pueue.queue(second["task_id"])
    for job, ran in ((first, "first"), (second, "second")):
        begin_attempt(config, job["job_id"])
        (config.jobs_dir / f"{job['job_id']}.outcome").write_text(
            json.dumps({"outcome": "success", "exit_code": 0})
        )
        (config.jobs_dir / f"{job['job_id']}.log").write_text(f"{ran} log\n")
        (config.jobs_dir / f"{job['job_id']}.result").write_text(
            json.dumps({"ran": ran})
        )

    fake_pueue.switch(first["task_id"], second["task_id"])

    asked = first["task_id"]
    job_id = first["job_id"]
    moved = job_queries.get_job(asked, config, job_id)
    assert (moved["job_id"], moved["task_id"]) == (job_id, second["task_id"])
    assert job_queries.result(config, asked, job_id)["value"] == {"ran": "first"}
    assert job_queries.logs(config, asked, job_id).strip() == "first log"

    cancelled = launch.cancel(config, asked, job_id=job_id)

    assert cancelled["job_id"] == job_id
    assert fake_pueue.removed == [second["task_id"]], (
        "the cancel dropped the task at the id it was handed, not its own job"
    )
    assert (config.jobs_dir / f"{second['job_id']}.log").exists()


def test_a_retained_reference_remains_readable_after_the_queue_forgets_it(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.remove([started["task_id"]])

    view = job_queries.get_job(started["task_id"], config, started["job_id"])
    assert view["queue_present"] is False
    assert view["job_id"] == started["job_id"]


def test_clean_removes_a_terminal_queue_task_and_retains_its_evidence(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("verify"))
    task = fake_pueue.task(started["task_id"])
    written = read_launch(config, task)
    log = Path(written["log_path"])
    log.parent.mkdir(parents=True, exist_ok=True)
    artifacts = [
        log,
        Path(written["result_path"]),
        cancel_marker_for(log),
        outcome_path_for(log),
        job_queries.launch_input_path(task),
    ]
    for path in artifacts:
        path.write_text("x")

    with pytest.raises(JobError, match="still running"):
        launch.clean(config, started["task_id"])
    fake_pueue.succeed(started["task_id"])
    cleaned = launch.clean(config, started["task_id"])

    assert cleaned["cleaned"] is True
    assert not cancel_marker_for(log).exists()
    assert all(path.exists() for path in artifacts if path != cancel_marker_for(log))
    assert fake_pueue.removed == [started["task_id"]]


def test_clean_all_terminal_leaves_running_and_foreign_tasks_alone(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    done = launch.start_operation(config, project, project.operation("check"))
    running = launch.start_operation(config, project, project.operation("check"))
    foreign = fake_pueue.add(
        group="normal",
        label="other:x",
        command=("true",),
        working_directory=project_root,
    )
    fake_pueue.succeed(done["task_id"])
    fake_pueue.succeed(foreign)

    cleaned = launch.clean_terminal(config)

    assert [row["task_id"] for row in cleaned] == [done["task_id"]]
    assert fake_pueue.task(running["task_id"]) is not None
    assert fake_pueue.task(foreign) is not None


def test_a_binding_is_stored_in_the_launch_input_and_read_back_on_get(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.enqueue(
        config,
        project=project,
        operation="check",
        label="fixture:check",
        group="normal",
        argv=["true"],
        working_directory=project_root,
        timeout_seconds=10,
        result_kind="exit",
        environment={"PATH": os.environ["PATH"]},
        binding={"beads": ["fx-1", "fx-2"], "run_id": "run-7"},
    )

    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["binding"] == {"beads": ["fx-1", "fx-2"], "run_id": "run-7"}
    assert (
        job_queries.get_job(started["task_id"], config)["binding"] == written["binding"]
    )
    assert "binding" not in job_queries.get_job(started["task_id"])


def test_enqueue_preserves_a_pending_launch_after_an_uncertain_add(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    fake_pueue.fail_add = True
    pending: list[str] = []

    with pytest.raises(launch.EnqueueUncertain) as raised:
        launch.enqueue(
            config,
            project=project,
            operation="check",
            label="fixture:check",
            group="normal",
            argv=["true"],
            working_directory=project_root,
            timeout_seconds=10,
            result_kind="exit",
            environment={"PATH": os.environ["PATH"]},
            job_id="recovery-pending",
            before_enqueue=pending.append,
        )

    assert pending == ["recovery-pending"]
    assert raised.value.job_id == "recovery-pending"
    assert "fixture pueue add failed" in str(raised.value)
    assert (config.inputs_dir / "recovery-pending.json").is_file()


def test_a_declared_scratch_tier_reaches_the_launch_input_and_job_get(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper is told which directory to own, and `job get` shows what it cost."""
    monkeypatch.setenv("AGENTCTL_NVME_SCRATCH_ROOT", str(tmp_path / "nvme"))
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text() + '\n[operations.heavy]\ndescription = "Fixture heavy"\n'
        'exec = ["fixture-heavy"]\npool = "bulk"\nresult = "exit"\nscratch = "nvme"\n'
    )
    project = load_project_adapter(project_root)

    started = launch.start_operation(config, project, project.operation("heavy"))

    written = read_launch(config, fake_pueue.task(started["task_id"]))
    job_id = Path(fake_pueue.added[0]["command"][1]).stem
    assert written["scratch"] == {
        "kind": "nvme",
        "path": str(tmp_path / "nvme" / job_id),
    }
    plain = launch.start_operation(config, project, project.operation("check"))
    assert "scratch" not in read_launch(config, fake_pueue.task(plain["task_id"]))

    artifacts.begin(written, "fixture-input")
    outcome = outcome_path_for(written["log_path"])
    outcome.write_text(
        json.dumps(
            {
                "outcome": "success",
                "exit_code": 0,
                "scratch": {
                    "kind": "nvme",
                    "path": written["scratch"]["path"],
                    "bytes": 2048,
                    "files": 3,
                    "truncated": False,
                },
            }
        )
    )
    fake_pueue.succeed(started["task_id"])

    document = job_queries.get_job(started["task_id"], config)
    assert document["scratch"]["bytes"] == 2048 and document["scratch"]["files"] == 3
    assert "scratch" not in job_queries.get_job(plain["task_id"], config)


def test_cancelling_a_queued_task_drops_it_out_of_the_queue(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """A task that never started has no process, and pueue refuses to kill it.

    Anti-vacuity: the refusal leaves the task queued, so a cancel that only
    kills reports failure and the task runs a minute later regardless.
    """
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(started["task_id"])

    input_path = job_queries.launch_input_path(fake_pueue.task(started["task_id"]))
    assert input_path is not None and input_path.exists()

    cancelled = launch.cancel(config, started["task_id"])

    assert fake_pueue.removed == [started["task_id"]]
    assert fake_pueue.task(started["task_id"]) is None
    assert cancelled["state"] == "removed"
    assert cancelled["phase"] == "cancelled" and cancelled["terminal"] is True
    assert cancelled["started"] is False
    assert cancelled["disposition"] == {
        "outcome": "cancelled",
        "started": False,
    }
    assert cancelled["removed"] == []
    assert input_path.exists()
    first = job_queries.get_job(started["task_id"], config, started["job_id"])
    second = job_queries.get_job(started["task_id"], config, started["job_id"])
    restarted = job_queries.get_job(
        started["task_id"],
        Config(
            project_roots=config.project_roots,
            event_spool=config.event_spool,
            state_dir=config.state_dir,
            agentctl_executable=config.agentctl_executable,
        ),
        started["job_id"],
    )
    for document in (first, second, restarted):
        assert document["phase"] == "cancelled"
        assert document["started"] is False
        assert document["disposition"] == {
            "outcome": "cancelled",
            "started": False,
        }
        assert document["queue_present"] is False
    assert input_path in list(config.inputs_dir.iterdir())


def test_cancelling_a_queued_retry_keeps_the_previous_attempt_and_its_output(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """Latest disposition is cancelled/not-started; attempt 1 stays readable."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("verify"))
    written = read_launch(config, fake_pueue.task(started["task_id"]))
    artifacts.begin(written, "fixture-input")
    Path(written["log_path"]).write_text("first-attempt-log\n")
    Path(written["result_path"]).write_text('{"passed": 4}')
    outcome_path_for(written["log_path"]).write_text(
        json.dumps({"outcome": "success", "exit_code": 0})
    )
    fake_pueue.succeed(started["task_id"])
    original_log = Path(written["log_path"]).read_bytes()
    original_result = Path(written["result_path"]).read_bytes()

    retried = launch.retry(config, started["task_id"], started["job_id"])
    assert retried["phase"] == "queued"
    cancelled = launch.cancel(config, started["task_id"], job_id=started["job_id"])

    assert cancelled["phase"] == "cancelled" and cancelled["started"] is False
    latest = job_queries.get_job(started["task_id"], config, started["job_id"])
    assert latest["phase"] == "cancelled" and latest["started"] is False
    previous = job_queries.get_job(
        started["task_id"], config, started["job_id"], attempt=1
    )
    assert previous["outcome"]["outcome"] == "success"
    assert previous["artifacts"]["result"]
    page = job_queries.result(config, started["task_id"], started["job_id"], attempt=1)
    assert page["value"] == {"passed": 4}
    assert Path(written["log_path"]).read_bytes() == original_log
    assert Path(written["result_path"]).read_bytes() == original_result


def test_get_job_keeps_first_attempt_allocation_out_of_its_selected_view(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first view has no attempt, even if allocation finishes before outcome reading."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(started["task_id"])
    document = read_launch(config, task)
    input_path = job_queries.launch_input_path(task)
    assert input_path is not None

    original_view = job_queries.artifact_view
    views = 0

    def allocate_after_view(
        config: Config, task: Task, attempt: int | None = None
    ) -> dict:
        nonlocal views
        view = original_view(config, task, attempt)
        views += 1
        if views == 1:
            assert view["attempt"] == 0 and view["artifacts"] == {}
            allocated = artifacts.begin(document, str(input_path))
            Path(allocated["log_path"]).write_text("attempt one\n")
            outcome_path_for(allocated["log_path"]).write_text(
                json.dumps({"outcome": "success", "exit_code": 0})
            )
        return view

    monkeypatch.setattr(job_queries, "artifact_view", allocate_after_view)
    first = job_queries.get_job(started["task_id"], config, started["job_id"])
    assert views == 1
    assert first["attempt"] == 0
    assert first["attempts"] == [] and first["attempt_count"] == 0
    assert first["artifacts"] == {} and "outcome" not in first
    assert first["phase"] == "running"

    second = job_queries.get_job(started["task_id"], config, started["job_id"])
    assert second["attempt"] == 1 and second["attempt_count"] == 1
    assert second["outcome"] == {"outcome": "success", "exit_code": 0}
    assert second["phase"] == "running"
    with pytest.raises(JobError, match="has no attempt 0"):
        job_queries.get_job(started["task_id"], config, started["job_id"], attempt=0)


def test_result_keeps_first_attempt_allocation_out_of_its_selected_view(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("verify"))
    task = fake_pueue.task(started["task_id"])
    document = read_launch(config, task)
    input_path = job_queries.launch_input_path(task)
    assert input_path is not None

    original_view = job_queries.artifact_view
    views = 0

    def allocate_after_view(
        config: Config, task: Task, attempt: int | None = None
    ) -> dict:
        nonlocal views
        view = original_view(config, task, attempt)
        views += 1
        if views == 1:
            assert view["attempt"] == 0 and view["artifacts"] == {}
            allocated = artifacts.begin(document, str(input_path))
            Path(allocated["result_path"]).write_text('{"passed": 4}')
        return view

    monkeypatch.setattr(job_queries, "artifact_view", allocate_after_view)
    first = job_queries.result(config, started["task_id"], started["job_id"])
    assert views == 1
    assert first["attempt"] == first["page"]["attempt"] == 0
    assert first["attempt_count"] == 0 and first["page"]["available"] is False
    assert first["value"] is None and first["kind"] == "exit"

    second = job_queries.result(config, started["task_id"], started["job_id"])
    assert second["attempt"] == second["page"]["attempt"] == 1
    assert second["value"] == {"passed": 4}


def test_cancel_racing_runner_start_does_not_fabricate_not_started(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """Anti-vacuity: an allocated attempt with no outcome is a start, even if
    pueue still reports the task as queued."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(started["task_id"])
    document = read_launch(config, fake_pueue.task(started["task_id"]))
    input_path = job_queries.launch_input_path(fake_pueue.task(started["task_id"]))
    assert input_path is not None
    artifacts.begin(document, str(input_path))

    cancelled = launch.cancel(config, started["task_id"], job_id=started["job_id"])

    assert cancelled.get("started") is not False
    assert cancelled["phase"] == "unresolved"
    assert cancelled["disposition"]["unresolved"] is True


def test_cancel_start_race_targets_the_attempt_allocated_after_it(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    recording_systemctl: Callable[[], list[list[str]]],
    tmp_path: Path,
) -> None:
    """Pre-allocation cancellation is preserved when pueue starts under its lock."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task_id = started["task_id"]
    fake_pueue.queue(task_id)
    original_task = fake_pueue.task
    raced = False

    def task_after_runner_start(asked: int) -> Task | None:
        nonlocal raced
        if asked == task_id and not raced:
            raced = True
            queued = original_task(asked)
            assert queued is not None
            fake_pueue._tasks[asked] = replace(
                queued,
                status="Running",
                started_at="2026-09-27T00:00:00+00:00",
            )
        return original_task(asked)

    monkeypatch.setattr(launch.pueue, "task", task_after_runner_start)
    cancelled = launch.cancel(
        config, task_id, job_id=started["job_id"], settle_seconds=0
    )

    document = read_launch(config, original_task(task_id))
    marker = cancel_marker_for(document["log_path"])
    assert json.loads(marker.read_text()) == {"attempt": 1}
    assert cancelled["phase"] == "cancelled"
    assert original_task(task_id).terminal

    side_effect = tmp_path / "cancelled-runner-side-effect"
    document["argv"] = ["sh", "-c", f"touch {side_effect}"]
    write_input(job_queries.launch_input_path(original_task(task_id)), document)
    monkeypatch.setattr("agentctl.run.unit_pool", lambda _pool: None)

    assert (
        run_main([str(job_queries.launch_input_path(original_task(task_id)))])
        == CANCELLED_EXIT_CODE
    )
    assert not side_effect.exists()
    assert [
        "systemctl",
        "--user",
        "stop",
        job_queries.unit_of(original_task(task_id)),
    ] in recording_systemctl()


def test_a_task_whose_launch_input_agentctl_did_not_write_names_its_own_scope(
    fake_pueue: FakePueue,
    config: Config,
    tmp_path: Path,
    recording_systemctl: Callable[[], list[list[str]]],
) -> None:
    """A repository may queue the wrapper with its own launch input.

    Anti-vacuity: such an input sits in that checkout, not under the state
    directory, and a reap that looks only there reaches nothing at all.
    """
    foreign = tmp_path / "checkout" / ".cache" / "verify" / "pytest-slot-42.json"
    foreign.parent.mkdir(parents=True)
    foreign.write_text(json.dumps({"log_path": str(foreign.parent / "slot.log")}))
    task_id = fake_pueue.add(
        group="pytest",
        label="polylogue:test:42",
        command=("/run/current-system/sw/bin/agentctl-run", str(foreign)),
        working_directory=tmp_path / "checkout",
    )

    cancelled = launch.cancel(config, task_id)

    unit = unit_for(foreign, "pytest")
    assert ["systemctl", "--user", "stop", unit] in recording_systemctl()
    assert cancelled["unit"] == unit
    assert cancel_marker_for(foreign.parent / "slot.log").exists()


def test_a_command_that_only_mentions_the_wrapper_owns_no_scope_and_no_artifacts(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    tmp_path: Path,
    recording_systemctl: Callable[[], list[list[str]]],
) -> None:
    """Ownership is what a task runs, not what its command line contains.

    Anti-vacuity: this command carries the wrapper's name and a real launch
    input path, so reading the command as text hands an unrelated task another
    task's scope to stop and another task's log to print.
    """
    project = load_project_adapter(project_root)
    victim = launch.start_operation(config, project, project.operation("check"))
    borrowed = job_queries.launch_input_path(fake_pueue.task(victim["task_id"]))
    task_id = fake_pueue.add(
        group="pytest",
        label="other:report:1",
        command=("sh", "-c", f"echo agentctl-run {borrowed}"),
        working_directory=tmp_path,
    )
    task = fake_pueue.task(task_id)

    assert job_queries.launch_input_path(task) is None
    assert job_queries.unit_of(task) is None
    cancelled = launch.cancel(config, task_id)

    assert cancelled["unit"] is None
    assert [call for call in recording_systemctl() if "stop" in call] == []


def test_an_artifact_outside_the_task_own_directories_is_not_published(
    fake_pueue: FakePueue, config: Config, tmp_path: Path
) -> None:
    """A launch input names its own artifact paths, and only its own.

    Anti-vacuity: `job logs` prints what the input declares, so an input naming
    a file in another tree publishes that file to whoever asks for the log.
    """
    private = tmp_path / "elsewhere" / "credentials"
    private.parent.mkdir(parents=True)
    private.write_text("secret material")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    outside = checkout / "outside.json"
    outside.write_text(json.dumps({"log_path": str(private)}))
    reachable = checkout / "reachable.json"
    reachable.write_text(json.dumps({"log_path": str(checkout / "own.log")}))
    (checkout / "own.log").write_text("this task's own output\n")

    tasks = {
        name: fake_pueue.add(
            group="pytest",
            label=f"polylogue:test:{name}",
            command=("agentctl-run", str(path)),
            working_directory=checkout,
        )
        for name, path in (("outside", outside), ("reachable", reachable))
    }
    for task_id in tasks.values():
        fake_pueue.set_log(task_id, "wrapper stderr")

    assert job_queries.logs(config, tasks["outside"]) == "wrapper stderr"
    assert "secret material" not in job_queries.logs(config, tasks["outside"])
    # The same rule must publish the artifacts a task really does own.
    assert "this task's own output" in job_queries.logs(config, tasks["reachable"])


def test_get_job_does_not_read_outcome_beside_an_outside_log_symlink(
    fake_pueue: FakePueue, config: Config, tmp_path: Path
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    owned_log = checkout / "owned.log"
    owned_log.write_text("owned output\n")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    outside_log = outside / "linked.log"
    outside_log.symlink_to(owned_log)
    outcome_path_for(outside_log).write_text('{"outcome": "failed", "exit_code": 7}')
    launch_input = checkout / "external.json"
    launch_input.write_text(json.dumps({"log_path": str(outside_log)}))
    task_id = fake_pueue.add(
        group="pytest",
        label="polylogue:test:linked",
        command=("agentctl-run", str(launch_input)),
        working_directory=checkout,
    )

    detail = job_queries.get_job(task_id, config)

    assert "outcome" not in detail


def test_an_artifact_that_is_not_a_regular_file_is_refused_without_blocking(
    tmp_path: Path,
) -> None:
    """A read bounded by the caller, on a file that cannot block it.

    Anti-vacuity: opening a fifo with no writer blocks until one appears, and
    reading a whole file to slice it afterwards is bounded by nothing.
    """
    fifo = tmp_path / "log"
    os.mkfifo(fifo)
    regular = tmp_path / "regular"
    regular.write_bytes(b"x" * 4096)

    assert job_queries.read_bounded(fifo, 64) is None
    assert job_queries.read_bounded(tmp_path, 64) is None
    assert job_queries.read_bounded(tmp_path / "absent", 64) is None
    assert job_queries.read_bounded(regular, 64) == b"x" * 64


def test_retry_is_pueue_restart_and_only_for_terminal_tasks(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))

    with pytest.raises(JobError, match="still running"):
        launch.retry(config, started["task_id"])
    fake_pueue.fail(started["task_id"], exit_code=1)
    retried = launch.retry(config, started["task_id"])

    assert fake_pueue.restarted == [started["task_id"]]
    assert retried["phase"] == "queued"


def test_wait_returns_the_terminal_view_and_reports_a_timeout_as_such(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.finish_when_waited(started["task_id"], lambda fake: fake.succeed(1))

    waited = job_queries.wait(started["task_id"], timeout_seconds=5)
    assert waited["phase"] == "succeeded"

    second = launch.start_operation(config, project, project.operation("check"))
    timed_out = job_queries.wait(second["task_id"], timeout_seconds=1)
    assert timed_out["wait_timed_out"] is True
    assert timed_out["phase"] == "running"


def test_a_wait_follows_its_job_when_the_queue_reorders_beneath_it(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """`pueue switch` exchanges two task ids, and a wait must follow its job.

    Anti-vacuity: a wait bound to the id blocks on whatever the switch moved
    there, and reports that stranger's outcome as its own.
    """
    project = load_project_adapter(project_root)
    other = launch.start_operation(config, project, project.operation("check"))
    own = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(other["task_id"])
    fake_pueue.queue(own["task_id"])

    def reorder(fake: FakePueue) -> None:
        """The operator reorders the queue while the caller is blocked."""
        fake.switch(other["task_id"], own["task_id"])
        # The waited job is at the other's id now, and finishes there.
        fake.succeed(other["task_id"])

    fake_pueue.finish_when_waited(own["task_id"], reorder)

    waited = job_queries.wait(own["task_id"], timeout_seconds=30, job_id=own["job_id"])

    assert waited["job_id"] == own["job_id"]
    assert (waited["task_id"], waited["phase"]) == (other["task_id"], "succeeded")
    # Blocked once on the id it started with, never on the task moved there.
    assert fake_pueue.waited == [own["task_id"]]
    assert job_queries.get_job(own["task_id"])["job_id"] == other["job_id"]


def test_a_wait_finds_the_job_the_queue_moved_before_the_wait_began(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """The job_id the caller started with names its job; the id may not.

    Anti-vacuity: reading the job out of the id at entry waits for the task
    the switch left there, which is never this caller's.
    """
    project = load_project_adapter(project_root)
    other = launch.start_operation(config, project, project.operation("check"))
    own = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(other["task_id"])
    fake_pueue.queue(own["task_id"])
    fake_pueue.switch(other["task_id"], own["task_id"])
    fake_pueue.succeed(other["task_id"])

    waited = job_queries.wait(own["task_id"], timeout_seconds=30, job_id=own["job_id"])

    assert (waited["job_id"], waited["phase"]) == (own["job_id"], "succeeded")
    assert fake_pueue.waited == []


@pytest.mark.parametrize("move_again", [False, True])
def test_wait_keeps_relocated_hint_without_repeating_reference_scans(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    move_again: bool,
) -> None:
    project = load_project_adapter(project_root)
    first = launch.start_operation(config, project, project.operation("check"))
    second = launch.start_operation(config, project, project.operation("check"))
    own = launch.start_operation(config, project, project.operation("check"))
    for job in (first, second, own):
        fake_pueue.queue(job["task_id"])
    fake_pueue.switch(first["task_id"], own["task_id"])
    scans = []

    def lookup(fragment):
        scans.append(fragment)
        return fake_pueue.tasks_by_command(fragment)

    monkeypatch.setattr(pueue, "tasks_by_command", lookup)
    current = first["task_id"]
    rounds = 0

    def advance(fake):
        nonlocal current, rounds
        rounds += 1
        if rounds == 1 and move_again:
            fake.switch(current, second["task_id"])
            current = second["task_id"]
        if rounds == 3:
            fake.succeed(current)
        else:
            fake.finish_when_waited(current, advance)

    fake_pueue.finish_when_waited(current, advance)
    result = job_queries.wait(own["task_id"], job_id=own["job_id"], timeout_seconds=60)
    assert result["job_id"] == own["job_id"]
    assert (result["task_id"], result["phase"]) == (current, "succeeded")
    assert len(scans) == (2 if move_again else 1)
    assert set(scans) == {own["job_id"] + ".json"}
    assert len(fake_pueue.waited) == 3
    for stranger in (first, second):
        task = job_queries.find_task(
            fake_pueue.tasks(), stranger["task_id"], stranger["job_id"]
        )
        assert task is not None and task.status == "Queued"


def test_every_read_by_task_id_answers_about_the_job_that_id_now_holds(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """Status, result, log and cancellation move with the queue, together."""
    project = load_project_adapter(project_root)
    first = launch.start_operation(config, project, project.operation("verify"))
    second = launch.start_operation(config, project, project.operation("verify"))
    fake_pueue.queue(first["task_id"])
    fake_pueue.queue(second["task_id"])
    for job, ran in ((first, "first"), (second, "second")):
        begin_attempt(config, job["job_id"])
        (config.jobs_dir / f"{job['job_id']}.outcome").write_text(
            json.dumps({"outcome": "success", "exit_code": 0})
        )
        (config.jobs_dir / f"{job['job_id']}.log").write_text(f"{ran} log\n")
        (config.jobs_dir / f"{job['job_id']}.result").write_text(
            json.dumps({"ran": ran})
        )

    fake_pueue.switch(first["task_id"], second["task_id"])

    moved = first["task_id"]
    assert job_queries.get_job(moved, config)["job_id"] == second["job_id"]
    assert job_queries.result(config, moved)["value"] == {"ran": "second"}
    assert job_queries.logs(config, moved).strip() == "second log"
    cancelled = launch.cancel(config, moved)
    assert cancelled["job_id"] == second["job_id"]
    assert cancelled["removed"] == []
    assert (config.jobs_dir / f"{second['job_id']}.log").read_text() == "second log\n"
    assert (config.inputs_dir / f"{second['job_id']}.json").exists()
    assert (config.jobs_dir / f"{first['job_id']}.log").exists()


def test_list_filters_by_project_prefix(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    launch.start_operation(config, project, project.operation("check"))
    fake_pueue.add(
        group="normal",
        label="other:check",
        command=("true",),
        working_directory=project_root,
    )

    assert [row["label"] for row in job_queries.list_jobs("fixture")] == [
        "fixture:check"
    ]
    assert len(job_queries.list_jobs()) == 2


def test_snapshot_projects_a_large_terminal_history_without_reading_artifacts(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminal_history = {
        str(number): {
            "id": number,
            "label": "fixture:history:" + "x" * 300,
            "group": "normal",
            "path": "/realm/project/fixture",
            "command": "x" * 240,
            "dependencies": [],
            "status": {"Done": {"result": "Success"}},
        }
        for number in range(5_000)
    }
    document = {
        "groups": {
            "agent": {"status": "Running", "parallel_tasks": 2},
            "normal": {"status": "Running", "parallel_tasks": 1},
        },
        "tasks": {
            **terminal_history,
            "6001": {
                "id": 6001,
                "label": "fixture:worker:run",
                "group": "agent",
                "path": "/realm/project/fixture",
                "dependencies": [],
                "status": {"Running": {}},
            },
        },
    }
    payload = json.dumps(document)
    assert len(payload.encode()) > 1_048_576
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        pueue,
        "_run",
        lambda arguments, **_kwargs: calls.append(tuple(arguments)) or payload,
    )

    snapshot = job_queries.snapshot_jobs(2)

    assert calls == [("status", "--json")]
    assert [row["task_id"] for row in snapshot["jobs"]] == [6001, 4999]
    assert snapshot["groups"]["agent"]["running"] == 1
    assert snapshot["groups"]["normal"]["terminal"] == 5_000
    assert snapshot["omitted"] == {"total": 4_999, "active": 0, "terminal": 4_999}
    assert snapshot["jobs"][1]["shortened"] == ["label", "operation"]
    assert len(json.dumps(snapshot).encode()) <= 1_048_576


def test_every_queued_task_carries_the_config_the_launch_was_started_with(
    fake_pueue: FakePueue,
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested AgentCTL calls must retain the operation's config and state namespace."""
    location = tmp_path / "agentctl.json"
    location.write_text(
        json.dumps(
            {
                "project_roots": [str(project_root)],
                "state_dir": str(tmp_path / "state"),
                "event_spool": str(tmp_path / "events.jsonl"),
            }
        )
    )
    monkeypatch.setenv("AGENTCTL_CONFIG", str(location))
    config = load_config()
    assert config.config_path == location
    project = config.catalog().get("fixture")

    started = launch.start_operation(config, project, project.operation("check"))

    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["environment"]["AGENTCTL_CONFIG"] == str(location)


def test_a_declared_admission_envelope_reaches_the_job_and_its_command(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """The declared side of the comparison a sizing receipt already measures.
    Breaks if the envelope stops being carried: the workload has no declared
    number to read, and the job record says nothing about what was expected."""
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text()
        + '\n[operations.corpus]\ndescription = "Fixture corpus"\n'
        + 'exec = ["fixture-corpus"]\npool = "bulk"\n'
        + "admission = { memory_mib = 12288 }\n"
    )
    project = load_project_adapter(project_root)

    started = launch.start_operation(config, project, project.operation("corpus"))

    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["admission"] == {"memory_mib": 12288}
    assert written["environment"]["AGENTCTL_ADMISSION_MEMORY_MIB"] == "12288"
    # A declaration, not a limit: it must not become a unit memory bound.
    assert not any(
        item.startswith("Memory") for item in written.get("unit_properties", [])
    )


def test_wait_rechecks_terminal_state_at_observer_timeout(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))

    def wait(task_id: int, *, timeout_seconds: float) -> None:
        fake_pueue.succeed(task_id)
        raise pueue.PueueTimeout("observer expired as the task finished")

    monkeypatch.setattr(pueue, "wait", wait)
    observed = job_queries.wait(started["task_id"], timeout_seconds=5)
    assert observed["phase"] == "succeeded"
    assert "wait_timed_out" not in observed


@pytest.mark.parametrize(
    "declared,unset,expected",
    [
        ((), (), "/current/fixture"),
        ((("FIXTURE_ROOT", "/custom/fixture"),), (), "/custom/fixture"),
        ((), ("FIXTURE_ROOT",), None),
    ],
)
def test_queued_environment_uses_current_host_roots_without_losing_explicit_overrides(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    declared: tuple,
    unset: tuple,
    expected: str | None,
) -> None:
    monkeypatch.setenv("FIXTURE_ROOT", "/retired/fixture")
    project = load_project_adapter(project_root)
    project = replace(
        project,
        environment=replace(
            project.environment,
            inherit=("PATH", "FIXTURE_ROOT"),
            declared=declared,
            unset=unset,
        ),
    )
    config = replace(
        config,
        inherited_environment={
            "FIXTURE_ROOT": "/current/fixture",
            "NOT_INHERITED": "must-not-leak",
        },
    )
    started = launch.start_operation(config, project, project.operation("verify"))
    env = read_launch(config, fake_pueue.task(started["task_id"]))["environment"]
    assert env.get("FIXTURE_ROOT") == expected
    assert "NOT_INHERITED" not in env


def test_wait_retained_cancelled_launch_does_not_follow_reused_id(
    fake_pueue, config, project_root
):
    project = load_project_adapter(project_root)
    own = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(own["task_id"])
    launch.cancel(config, own["task_id"], job_id=own["job_id"])
    fake_pueue.next_id = own["task_id"]
    other = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.succeed(other["task_id"])
    observed = job_queries.wait(
        own["task_id"], timeout_seconds=5, job_id=own["job_id"], config=config
    )
    assert observed["phase"] == "cancelled" and observed["terminal"] is True
    assert observed["job_id"] == own["job_id"] and observed["queue_present"] is False
    assert observed["exit_code"] == CANCELLED_EXIT_CODE
    assert fake_pueue.waited == []


@pytest.mark.parametrize("owner_error", [False, True])
def test_wait_retained_cancellation_during_observation(
    fake_pueue, config, project_root, owner_error
):
    project = load_project_adapter(project_root)
    own = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(own["task_id"])

    def cancel_then_reuse(fake):
        launch.cancel(config, own["task_id"], job_id=own["job_id"])
        fake.next_id = own["task_id"]
        launch.start_operation(config, project, project.operation("check"))
        if owner_error:
            raise PueueError("fixture removed during wait")

    fake_pueue.finish_when_waited(own["task_id"], cancel_then_reuse)
    # No explicit job_id: a wait must retain the identity it first saw.
    observed = job_queries.wait(own["task_id"], timeout_seconds=5, config=config)
    assert observed["phase"] == "cancelled" and observed["terminal"] is True
    assert observed["job_id"] == own["job_id"] and not observed.get("wait_timed_out")
    assert fake_pueue.waited == [own["task_id"]]


@pytest.mark.parametrize("request_only", [False, True])
def test_wait_retained_unverified_launch_is_not_terminal(
    fake_pueue, config, project_root, request_only
):
    project = load_project_adapter(project_root)
    own = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(own["task_id"])
    if request_only:
        launch._write_disposition(
            config, task, {"outcome": "cancelled", "unresolved": True, "started": True}
        )
    fake_pueue.remove([own["task_id"]])
    assert (
        job_queries.get_job(own["task_id"], config, own["job_id"])["terminal"] is False
    )
    with pytest.raises(JobError, match="no verified terminal"):
        job_queries.wait(
            own["task_id"], timeout_seconds=5, job_id=own["job_id"], config=config
        )
    assert fake_pueue.waited == []


@pytest.mark.parametrize("marker", ["kind", "binding", "operation", "label"])
def test_retry_preserves_retired_executor_history_without_restarting(
    fake_pueue, config, project_root, marker
):
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task_id, job_id = started["task_id"], started["job_id"]
    fake_pueue.fail(task_id, exit_code=1)
    task = fake_pueue.task(task_id)
    path = job_queries.launch_input_path(task)
    value = read_launch(config, task)
    if marker == "kind":
        value[marker] = "attested-agent"
    elif marker == "binding":
        value[marker] = {"run_id": "fixture-run", "attempt": 1}
    elif marker == "operation":
        value[marker] = "land:fixture-run"
    else:
        fake_pueue._tasks[task_id] = replace(task, label="fixture:land:fixture-run")
    path.write_text(json.dumps(value))
    original = path.read_bytes()
    with pytest.raises(JobError, match="history-only"):
        launch.retry(config, task_id, job_id)
    assert fake_pueue.restarted == []
    assert path.read_bytes() == original
    assert job_queries.get_job(task_id, config, job_id)["phase"] == "failed"


@pytest.mark.parametrize(
    "stop_error",
    [None, PermissionError("fixture"), subprocess.TimeoutExpired("systemctl", 1)],
)
def test_cancel_retains_privileged_members_until_cgroup_drains(
    fake_pueue, config, project_root, tmp_path, monkeypatch, stop_error
):
    from agentctl import cgroups, worktree_cleanup

    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(started["task_id"])
    root = tmp_path / "cgroups"
    group = root / "fixture.service"
    group.mkdir(parents=True)
    members = group / "cgroup.procs"
    members.write_text("12345\n")
    monkeypatch.setattr(cgroups, "CGROUP_ROOT", root)
    monkeypatch.setattr(cgroups, "unit_cgroup", lambda _unit: "/fixture.service")
    monkeypatch.setattr(launch, "_unit_state", lambda _unit: "stopped")

    original_run = launch.subprocess.run

    def stop(_unit):
        if stop_error:
            # Exercise the actual stop helper's permission/timeout handling.
            monkeypatch.setattr(
                launch.subprocess,
                "run",
                lambda *a, **k: (_ for _ in ()).throw(stop_error),
            )
            original_stop(_unit)

    original_stop = launch._stop_unit
    monkeypatch.setattr(launch, "_stop_unit", stop)
    cancelled = launch.cancel(
        config, task.task_id, job_id=started["job_id"], settle_seconds=0
    )
    assert cancelled["state"] == "incomplete"
    assert cancelled["terminal"] is False
    assert cancelled["cgroup_observation"]["pids"] == [12345]
    assert job_queries.get_job(task.task_id, config)["terminal"] is False
    waited = job_queries.wait(task.task_id, config=config, timeout_seconds=0)
    assert waited["terminal"] is False and waited["wait_timed_out"] is True
    assert launch.cancel(config, task.task_id)["state"] == "incomplete"
    for action in (launch.retry, launch.clean):
        with pytest.raises(JobError, match="cancellation incomplete"):
            action(config, task.task_id, started["job_id"])
    assert fake_pueue.restarted == []
    # The checkout guard must work even after the pueue entry disappears.
    kept = worktree_cleanup._drop_branch(
        config,
        project,
        "fixture-branch",
        base="unused",
        recorded_path=project_root,
        registry=[],
    )
    assert kept == "worktree kept; job cancellation incomplete"
    members.write_text("")
    assert (
        job_queries.get_job(task.task_id, config).get("cancellation_incomplete")
        is not True
    )
    # Identity is retained; retry is permitted only after actual drain.
    monkeypatch.setattr(launch.subprocess, "run", original_run)
    retried = launch.retry(config, task.task_id, started["job_id"])
    assert retried["job_id"] == started["job_id"]
    members.write_text("67890\n")
    assert job_queries.get_job(task.task_id, config)["phase"] != "cancelled"
    assert (
        job_queries.get_job(task.task_id, config).get("cancellation_incomplete")
        is not True
    )


@pytest.mark.parametrize(
    "contents, expected",
    [("", "empty"), ("42\n", "populated"), ("invalid\n", "unresolved")],
)
def test_cgroup_observation_includes_children_and_missing_groups(
    tmp_path, monkeypatch, contents, expected
):
    from agentctl import cgroups

    group = tmp_path / "fixture.service"
    child = group / "child"
    child.mkdir(parents=True)
    (group / "cgroup.procs").write_text("")
    (child / "cgroup.procs").write_text(contents)
    monkeypatch.setattr(cgroups, "CGROUP_ROOT", tmp_path)
    monkeypatch.setattr(cgroups, "unit_cgroup", lambda _unit: "/fixture.service")
    assert cgroups.observe("fixture.service")["status"] == expected
    assert cgroups.observe("fixture.service", "/missing.service")["status"] == "empty"


def test_unreadable_cgroup_is_not_empty(tmp_path, monkeypatch):
    from agentctl import cgroups

    group = tmp_path / "fixture.service"
    group.mkdir()
    (group / "cgroup.procs").write_text("42\n")
    read_text = Path.read_text

    def unreadable(path, *args, **kwargs):
        if path == group / "cgroup.procs":
            raise PermissionError("synthetic cgroup permission failure")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(cgroups, "CGROUP_ROOT", tmp_path)
    monkeypatch.setattr(Path, "read_text", unreadable)
    observed = cgroups.observe("fixture.service", "/fixture.service")
    assert observed["status"] == "unresolved"
    assert (
        cgroups.cancellation_obstacle({"cancellation_incomplete": True, **observed})
        is not None
    )


def test_native_cleanup_retains_incomplete_job_after_queue_removal(
    fake_pueue, config, project_root, tmp_path, monkeypatch
):
    from agentctl import cgroups, native_worktrees

    project = load_project_adapter(project_root)
    workspace = tmp_path / "checkout"
    workspace.mkdir()
    started = launch.start_operation(
        config,
        project,
        replace(project.operation("check"), checkout="any"),
        workspace=workspace,
    )
    group = tmp_path / "fixture.service"
    group.mkdir()
    members = group / "cgroup.procs"
    members.write_text("42\n")
    monkeypatch.setattr(cgroups, "CGROUP_ROOT", tmp_path)
    monkeypatch.setattr(cgroups, "unit_cgroup", lambda unit: "/fixture.service")
    monkeypatch.setattr(launch, "_unit_state", lambda unit: "stopped")
    monkeypatch.setattr(launch, "_stop_unit", lambda unit: None)
    launch.cancel(config, started["task_id"], settle_seconds=0)
    assert native_worktrees._owners(config, project, {})[workspace]["terminal"] is False
    members.write_text("")
    assert native_worktrees._owners(config, project, {})[workspace]["terminal"] is True


@pytest.mark.parametrize("key", [None, "fixture-remote-launch"])
def test_operation_binding_persists_original_run_on_replay(
    fake_pueue: FakePueue, config: Config, project_root: Path, key
) -> None:
    project = load_project_adapter(project_root)
    binding = {
        "remote_run_id": "wfr_fixture",
        "actor": "sinnix-gateway:operator:wfr_fixture",
    }
    started = launch.start_operation(
        config,
        project,
        project.operation("verify"),
        binding=binding,
        idempotency_key=key,
    )
    written = read_launch(config, fake_pueue.task(started["task_id"]))
    assert written["binding"] == binding
    if key:
        replay = launch.start_operation(
            config,
            project,
            project.operation("verify"),
            binding={"remote_run_id": "wfr_other"},
            idempotency_key=key,
        )
        assert replay["job_id"] == started["job_id"]
        assert (
            read_launch(config, fake_pueue.task(started["task_id"]))["binding"]
            == binding
        )


@pytest.mark.parametrize("terminal", [False, True])
def test_retained_unit_custody_survives_launcher_death_without_cancel_request(
    fake_pueue, config, project_root, tmp_path, monkeypatch, terminal
):
    from agentctl import cgroups

    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task_id, job_id = started["task_id"], started["job_id"]
    task = fake_pueue.task(task_id)
    group = tmp_path / "fixture.service"
    group.mkdir()
    members = group / "cgroup.procs"
    members.write_text("12345\n")
    monkeypatch.setattr(cgroups, "CGROUP_ROOT", tmp_path)
    launch._write_disposition(
        config,
        task,
        {"unit": "fixture.service", "cgroup": "/fixture.service", "attempt": 1},
    )
    if terminal:
        fake_pueue.kill_directly(task_id)
    view = job_queries.get_job(task_id, config, job_id)
    if not terminal:
        assert view["phase"] == "running"
        assert not view.get("cancellation_incomplete")
        return
    assert view["terminal"] is False and view["phase"] == "unresolved"
    assert view["cgroup_observation"]["pids"] == [12345]
    waited = job_queries.wait(task_id, config=config, job_id=job_id, timeout_seconds=0)
    assert waited["terminal"] is False and waited["wait_timed_out"] is True
    for action in (launch.retry, launch.clean):
        with pytest.raises(JobError, match="cancellation incomplete"):
            action(config, task_id, job_id)
    members.write_text("")
    assert job_queries.get_job(task_id, config, job_id)["terminal"] is True
    retried = launch.retry(config, task_id, job_id)
    assert retried["job_id"] == job_id


@pytest.mark.parametrize("parent", [None, ""])
def test_planned_cgroup_covers_inactive_slices(tmp_path, monkeypatch, parent):
    from agentctl import cgroups

    monkeypatch.setattr(
        cgroups,
        "unit_cgroup",
        lambda name: "/fixture-user" if name == "-.slice" else parent,
    )
    assert cgroups.planned_unit_cgroup(
        "fixture.service", "agent-ctl-pytest-quick.slice"
    ) == (
        "/fixture-user/agent.slice/agent-ctl.slice/agent-ctl-pytest.slice/"
        "agent-ctl-pytest-quick.slice/fixture.service"
    )
    monkeypatch.setattr(cgroups, "unit_cgroup", lambda _: None)
    assert (
        cgroups.planned_unit_cgroup("fixture.service", "agent-ctl-normal.slice") is None
    )
    assert (
        cgroups.cancellation_obstacle(
            {
                "unit": "fixture.service",
                "cgroup": None,
                "attempt": 1,
            }
        )["status"]
        == "unresolved"
    )
