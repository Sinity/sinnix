from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import sinnixd.jobs as jobs_module
from sinnix_mcp import OpaquePayload, RequestEnvelope, ResponseEnvelope, SinnixRef, SourceBinding
from sinnix_mcp.execution import EnvironmentProfile, ExecutionResult

from sinnixd.api import UnixSocketServer, call, receive_frame, send_frame
from sinnixd.environment import build_environment
from sinnixd.delivery import DeliveryError, GitHubDelivery
from sinnixd.jobs import (
    MAX_LOG_ARTIFACT_BYTES,
    SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    GenericJobSpec,
    GenericJobStore,
    GenericJobs,
    SystemdJobError,
    UserSystemdJobs,
    capture_executable,
    capture_main,
)
from sinnixd.owner_adapters import DeclaredOwnerAdapters, OwnerAdapterError
from sinnixd.projects import ProjectCatalog, ProjectConfigError, parse_worktree_records
from sinnixd.runner import RunnerError, _revalidate_checkout
from sinnixd.service import SinnixdService
from sinnixd.workspaces import GitWorkspaces, WorkspaceStore


def write_adapter(root: Path) -> None:
    (root / "modules").mkdir(parents=True)
    (root / "flake.nix").write_text("{}")
    (root / ".agentctl").mkdir()
    (root / ".agentctl" / "project.toml").write_text(
        f"""schema = 1

[project]
id = "fixture"
display_name = "Fixture"
root_markers = ["flake.nix", "modules"]

[environment]
kind = "fixture"
command = ["fixture-env", "--command"]
inherit = ["HOME"]
unset = ["PYTHONPATH"]

[workspace]
provider = "git-worktree"
root = "{root / 'worktrees'}"
default_base = "origin/master"
identity_check = ["git", "diff", "--quiet"]
checkpoint_untracked = true
verification_operations = ["check"]

[conflicts]
exact_files = ["fixture.lock"]
generated_surfaces = ["generated.json"]
semantic_slots = ["fixture-registry"]

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


def request(
    operation: str, owner: str, arguments: dict[str, object] | None = None, principal: str = "test"
) -> RequestEnvelope:
    return RequestEnvelope(
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
        operation=operation,
        owner=owner,
        principal=principal,
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

    def show(
        self,
        unit: str,
        *,
        timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ) -> dict[str, str]:
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


def initialize_git_checkout(root: Path) -> None:
    for arguments in (
        ("git", "init", "--quiet", str(root)),
        ("git", "-C", str(root), "add", "."),
        ("git", "-C", str(root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "fixture"),
    ):
        subprocess.run(arguments, check=True)
    subprocess.run(
        ["git", "-C", str(root), "update-ref", "refs/remotes/origin/master", "HEAD"], check=True
    )


def test_worktree_porcelain_parser_accepts_flags_and_rejects_unknown_shapes() -> None:
    parsed = parse_worktree_records(
        "worktree /repo\nHEAD " + "a" * 40 + "\ndetached\nlocked operator reason\nprunable stale\n\n"
    )

    assert parsed == (
        {
            "worktree": "/repo",
            "HEAD": "a" * 40,
            "detached": "",
            "locked": "operator reason",
            "prunable": "stale",
        },
    )
    with pytest.raises(ProjectConfigError):
        parse_worktree_records("worktree /repo\nunknown value\n\n")


def native_runner(path: Path) -> None:
    path.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "last= prompt=\n"
        "if [ -n \"${RUNNER_ARGS:-}\" ]; then printf '%s\\n' \"$@\" > \"$RUNNER_ARGS\"; fi\n"
        "while [ $# -gt 0 ]; do\n"
        "  case $1 in --last-file) last=$2; shift 2 ;; --prompt-file) prompt=$2; shift 2 ;; *) shift ;; esac\n"
        "done\n"
        "test -f \"$prompt\"\n"
        "printf native-fixture-result > \"$last\"\n"
        "printf native-fixture-log\n"
    )
    path.chmod(0o700)


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
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(args, **kwargs):
        calls.append((list(args), kwargs))
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

    assert [args for args, _kwargs in calls] == [
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
    assert calls[0][1] == {
        "check": True,
        "capture_output": True,
        "text": True,
        "timeout": SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    }


def test_user_systemd_calls_use_finite_timeouts_and_redact_timeout_details(
    monkeypatch, tmp_path: Path
) -> None:
    """Anti-vacuity: omitting subprocess timeouts leaves a control worker held by a stuck user manager."""
    calls: list[dict[str, object]] = []

    def fake_run(args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stdout="LoadState=loaded\nActiveState=active\n")

    monkeypatch.setattr("sinnixd.jobs.subprocess.run", fake_run)
    systemd = UserSystemdJobs()
    systemd.start(
        unit="sinnixd-job-00000000-0000-0000-0000-000000000001.service",
        command=("fixture",),
        working_directory=str(tmp_path),
        environment={},
        timeout_seconds=1,
        log_path=tmp_path / "job.log",
    )
    systemd.show("sinnixd-job-00000000-0000-0000-0000-000000000001.service")
    systemd.stop("sinnixd-job-00000000-0000-0000-0000-000000000001.service")

    assert [call["timeout"] for call in calls] == [
        SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ]

    secret = "timeout-command-detail-must-not-escape"

    def timed_out(args, **kwargs):
        raise subprocess.TimeoutExpired([*args, secret], kwargs["timeout"])

    monkeypatch.setattr("sinnixd.jobs.subprocess.run", timed_out)
    with pytest.raises(SystemdJobError) as error:
        systemd.show("sinnixd-job-00000000-0000-0000-0000-000000000001.service")
    assert str(error.value) == "systemd command timed out"
    assert secret not in str(error.value)


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


def test_workspace_create_is_git_derived_durable_and_restart_safe(tmp_path: Path) -> None:
    """Anti-vacuity: create must reach Git worktree authority and survive service restart."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)

    created = service.dispatch(
        request(
            "workspace.create",
            "git-workspaces",
            {
                "project_id": "fixture",
                "name": "fixture-lane",
                "branch": "feature/fixture-lane",
                "base": "HEAD",
            },
            "agent-control",
        )
    )

    assert created.ok and created.payload is not None
    workspace = created.payload.inline
    assert workspace["state"] == "available"
    assert workspace["current_branch"] == "feature/fixture-lane"
    assert workspace["identity_matches"]
    assert workspace["managed"]
    assert Path(workspace["path"]).is_dir()
    porcelain = subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert f"worktree {workspace['path']}" in porcelain

    restarted = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    recovered = restarted.dispatch(
        request("workspace.get", "git-workspaces", {"workspace_id": workspace["workspace_id"]})
    )
    assert recovered.ok and recovered.payload is not None
    assert recovered.payload.inline["head"] == workspace["head"]
    assert recovered.payload.inline["checkout_id"].startswith("worktree-")


def test_workspace_adopt_uses_existing_linked_checkout_without_claiming_creation(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    linked = tmp_path / "external-linked"
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "add", "-b", "feature/adopted", str(linked), "HEAD"],
        check=True,
        capture_output=True,
    )
    catalog = ProjectCatalog([tmp_path])
    checkout = next(item for item in catalog.checkouts("fixture") if item.path == linked)
    service = SinnixdService(catalog, jobs=generic_jobs(tmp_path))

    adopted = service.dispatch(
        request(
            "workspace.adopt",
            "git-workspaces",
            {"project_id": "fixture", "checkout_id": checkout.checkout_id, "name": "adopted-lane"},
            "operator",
        )
    )

    assert adopted.ok and adopted.payload is not None
    assert adopted.payload.inline["path"] == str(linked)
    assert not adopted.payload.inline["managed"]
    assert adopted.payload.inline["current_branch"] == "feature/adopted"


def test_workspace_mutations_reject_weak_principals_paths_refs_and_duplicates(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    arguments = {
        "project_id": "fixture",
        "name": "safe-lane",
        "branch": "feature/safe-lane",
        "base": "HEAD",
    }

    weak = service.dispatch(request("workspace.create", "git-workspaces", arguments, "observer"))
    escaped = service.dispatch(
        request("workspace.create", "git-workspaces", {**arguments, "name": "../escape"}, "agent-control")
    )
    invalid_ref = service.dispatch(
        request("workspace.create", "git-workspaces", {**arguments, "base": "missing-ref"}, "agent-control")
    )
    created = service.dispatch(request("workspace.create", "git-workspaces", arguments, "agent-control"))
    duplicate = service.dispatch(request("workspace.create", "git-workspaces", arguments, "agent-control"))
    adopt_root = service.dispatch(
        request(
            "workspace.adopt",
            "git-workspaces",
            {"project_id": "fixture", "checkout_id": "default", "name": "root"},
            "operator",
        )
    )

    assert created.ok
    for response in (weak, escaped, invalid_ref, duplicate, adopt_root):
        assert response.error is not None
        assert response.error.code.value == "INVALID_ARGUMENT"


def test_workspace_status_exposes_branch_drift_and_dirty_state(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture", name="drift-lane", branch="feature/drift-lane", base="HEAD"
    )
    path = Path(created["path"])
    (path / "untracked.txt").write_text("operator work\n")
    subprocess.run(["git", "-C", str(path), "switch", "--detach"], check=True, capture_output=True)

    observed = service.workspaces.get(created["workspace_id"])

    assert observed["state"] == "missing"
    assert observed["dirty"] is None
    assert not observed["identity_matches"]


def test_workspace_reap_forgets_missing_and_removes_only_clean_contained_managed_worktrees(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    missing = service.workspaces.create(
        project_id="fixture", name="missing-lane", branch="feature/missing-lane", base="HEAD"
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "remove", missing["path"]],
        check=True,
        capture_output=True,
    )

    forgotten = service.dispatch(
        request(
            "workspace.reap",
            "git-workspaces",
            {"workspace_id": missing["workspace_id"]},
            "operator",
        )
    )
    clean = service.workspaces.create(
        project_id="fixture", name="clean-lane", branch="feature/clean-lane", base="HEAD"
    )
    reaped = service.workspaces.reap(clean["workspace_id"])

    assert forgotten.ok and forgotten.payload is not None
    assert forgotten.payload.inline["relationship_only"]
    assert reaped["reaped"] and not reaped["relationship_only"]
    assert not Path(clean["path"]).exists()
    assert service.workspaces.list("fixture") == {"workspaces": []}


def test_delivery_rejects_pending_hosted_checks() -> None:
    assert not GitHubDelivery._checks_pass(
        [{"__typename": "StatusContext", "context": "ci", "state": "PENDING"}]
    )
    assert GitHubDelivery._checks_pass(
        [
            {"__typename": "StatusContext", "context": "ci", "state": "SUCCESS"},
            {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "NEUTRAL"},
        ]
    )


def test_workspace_reap_preserves_dirty_divergent_and_adopted_worktrees(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    dirty = service.workspaces.create(
        project_id="fixture", name="dirty-lane", branch="feature/dirty-lane", base="HEAD"
    )
    dirty_path = Path(dirty["path"])
    (dirty_path / "operator.txt").write_text("preserve\n")
    divergent = service.workspaces.create(
        project_id="fixture", name="divergent-lane", branch="feature/divergent-lane", base="HEAD"
    )
    divergent_path = Path(divergent["path"])
    (divergent_path / "committed.txt").write_text("unique\n")
    subprocess.run(["git", "-C", str(divergent_path), "add", "committed.txt"], check=True)
    subprocess.run(
        [
            "git", "-C", str(divergent_path), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "--quiet", "-m", "diverge",
        ],
        check=True,
    )
    external = tmp_path / "external-reap"
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "add", "-b", "feature/external-reap", str(external), "HEAD"],
        check=True,
        capture_output=True,
    )
    checkout = next(item for item in service.projects.checkouts("fixture") if item.path == external)
    adopted = service.workspaces.adopt(project_id="fixture", checkout_id=checkout.checkout_id, name="adopted-reap")

    for workspace_id in (dirty["workspace_id"], divergent["workspace_id"], adopted["workspace_id"]):
        with pytest.raises(ValueError):
            service.workspaces.reap(workspace_id)

    assert (dirty_path / "operator.txt").read_text() == "preserve\n"
    assert divergent_path.is_dir()
    assert external.is_dir()


def test_workspace_checkpoint_restore_round_trips_index_worktree_and_untracked_state(tmp_path: Path) -> None:
    """Anti-vacuity: dropping any artifact loses one of the three asserted Git states."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture", name="checkpoint-lane", branch="feature/checkpoint-lane", base="HEAD"
    )
    path = Path(created["path"])
    (path / "flake.nix").write_text('{"staged": true}\n')
    subprocess.run(["git", "-C", str(path), "add", "flake.nix"], check=True)
    with (path / "flake.nix").open("a") as handle:
        handle.write("unstaged\n")
    (path / "untracked.txt").write_text("untracked payload\n")

    checkpoint = service.workspaces.checkpoint(created["workspace_id"])
    subprocess.run(["git", "-C", str(path), "reset", "--hard", "HEAD"], check=True, capture_output=True)
    (path / "untracked.txt").unlink()
    restored = service.workspaces.restore(created["workspace_id"], checkpoint["checkpoint_id"])

    assert restored["restored"]
    assert (path / "flake.nix").read_text() == '{"staged": true}\nunstaged\n'
    assert (path / "untracked.txt").read_text() == "untracked payload\n"
    assert "staged" in subprocess.run(
        ["git", "-C", str(path), "diff", "--cached"], check=True, capture_output=True, text=True
    ).stdout
    assert "unstaged" in subprocess.run(
        ["git", "-C", str(path), "diff"], check=True, capture_output=True, text=True
    ).stdout


def test_workspace_restore_rejects_dirty_or_stale_head_targets(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture", name="restore-guards", branch="feature/restore-guards", base="HEAD"
    )
    path = Path(created["path"])
    (path / "untracked.txt").write_text("checkpoint\n")
    checkpoint = service.workspaces.checkpoint(created["workspace_id"])

    with pytest.raises(ValueError, match="clean workspace"):
        service.workspaces.restore(created["workspace_id"], checkpoint["checkpoint_id"])

    (path / "untracked.txt").unlink()
    (path / "advance.txt").write_text("advance\n")
    subprocess.run(["git", "-C", str(path), "add", "advance.txt"], check=True)
    subprocess.run(
        [
            "git", "-C", str(path), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "--quiet", "-m", "advance",
        ],
        check=True,
    )
    with pytest.raises(ValueError, match="source HEAD"):
        service.workspaces.restore(created["workspace_id"], checkpoint["checkpoint_id"])


def test_workspace_recover_recreates_missing_exact_head_and_restores_checkpoint(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    created = service.workspaces.create(
        project_id="fixture", name="recover-lane", branch="feature/recover-lane", base="HEAD"
    )
    path = Path(created["path"])
    (path / "flake.nix").write_text('{"recovered": true}\n')
    subprocess.run(["git", "-C", str(path), "add", "flake.nix"], check=True)
    (path / "untracked.txt").write_text("preserved\n")
    checkpoint = service.workspaces.checkpoint(created["workspace_id"])
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "remove", "--force", str(path)],
        check=True,
    )

    recovered = service.workspaces.recover(created["workspace_id"], checkpoint["checkpoint_id"])

    assert recovered["recovered"] and recovered["path"] == str(path)
    assert (path / "flake.nix").read_text() == '{"recovered": true}\n'
    assert (path / "untracked.txt").read_text() == "preserved\n"
    assert "recovered" in subprocess.run(
        ["git", "-C", str(path), "diff", "--cached"], check=True, capture_output=True, text=True
    ).stdout


def test_workspace_stack_restacks_child_onto_parent_and_survives_restart(tmp_path: Path) -> None:
    """Anti-vacuity: the durable parent edge drives a real Git rebase after restart."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "fixture@example.test"], check=True)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    parent = service.workspaces.create(
        project_id="fixture", name="parent-lane", branch="feature/parent", base="HEAD"
    )
    child = service.workspaces.stack(
        parent_workspace_id=parent["workspace_id"], name="child-lane", branch="feature/child"
    )
    parent_path = Path(parent["path"])
    child_path = Path(child["path"])
    (child_path / "child.txt").write_text("child\n")
    subprocess.run(["git", "-C", str(child_path), "add", "child.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(child_path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "child"],
        check=True,
    )
    child_before = subprocess.run(
        ["git", "-C", str(child_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    (parent_path / "parent.txt").write_text("parent\n")
    subprocess.run(["git", "-C", str(parent_path), "add", "parent.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(parent_path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "parent"],
        check=True,
    )

    restarted = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    result = restarted.workspaces.restack(child["workspace_id"])

    assert result["restacked"] and result["before_head"] == child_before
    assert result["parent_workspace_id"] == parent["workspace_id"]
    assert result["head"] != child_before
    assert (child_path / "parent.txt").read_text() == "parent\n"
    with pytest.raises(ValueError, match="stacked children"):
        restarted.workspaces.reap(parent["workspace_id"])


def test_workspace_restack_reports_declared_collision_without_mutating_child(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path))
    parent = service.workspaces.create(
        project_id="fixture", name="collision-parent", branch="feature/collision-parent", base="HEAD"
    )
    child = service.workspaces.stack(
        parent_workspace_id=parent["workspace_id"], name="collision-child", branch="feature/collision-child"
    )
    for workspace, content, message in ((parent, "parent\n", "parent lock"), (child, "child\n", "child lock")):
        path = Path(workspace["path"])
        (path / "fixture.lock").write_text(content)
        subprocess.run(["git", "-C", str(path), "add", "fixture.lock"], check=True)
        subprocess.run(
            ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", message],
            check=True,
        )
    child_head = subprocess.run(
        ["git", "-C", child["path"], "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()

    result = service.workspaces.restack(child["workspace_id"])

    assert not result["restacked"]
    assert result["collisions"] == [{"path": "fixture.lock", "class": "exact-file"}]
    assert subprocess.run(
        ["git", "-C", child["path"], "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip() == child_head


def test_declared_job_binds_workspace_and_exact_head(tmp_path: Path) -> None:
    """Anti-vacuity: workspace verification launches in that checkout and persists its HEAD."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    jobs = generic_jobs(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture", name="verify-lane", branch="feature/verify-lane", base="HEAD"
    )

    started = service.dispatch(
        request(
            "job.start",
            "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "workspace_id": workspace["workspace_id"]},
        )
    )

    assert started.ok and started.payload is not None
    record = jobs.store.load(started.payload.inline["job_id"])
    assert record.spec.working_directory == workspace["path"]
    assert record.spec.checkout is not None
    assert record.spec.checkout["checkout_id"] == workspace["checkout_id"]
    assert record.spec.checkout["head"] == workspace["head"]


def test_exact_head_verified_workspace_publishes_lands_and_finishes_without_a_pr_ledger(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    systemd = FakeSystemdJobs()
    jobs = generic_jobs(tmp_path, systemd)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=jobs)
    workspace = service.workspaces.create(
        project_id="fixture", name="delivery-lane", branch="feature/delivery", base="HEAD"
    )
    path = Path(workspace["path"])
    (path / "delivery.txt").write_text("deliver\n")
    subprocess.run(["git", "-C", str(path), "add", "delivery.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "delivery"],
        check=True,
    )
    workspace = service.workspaces.get(workspace["workspace_id"])
    started = service.dispatch(
        request(
            "job.start", "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "workspace_id": workspace["workspace_id"]},
        )
    )
    assert started.ok and started.payload is not None
    job_id = started.payload.inline["job_id"]
    systemd.properties = {"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    calls: list[list[str]] = []
    merged = False
    created = False

    def fake_run(argv, **_kwargs):
        nonlocal created, merged
        command = list(argv)
        calls.append(command)
        if command[:3] == ["gh", "pr", "merge"]:
            merged = True
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ["gh", "pr", "create"]:
            created = True
            return subprocess.CompletedProcess(command, 0, "https://github.test/example/pull/17\n", "")
        if command[:3] == ["gh", "pr", "view"]:
            if command[-1] == "url":
                return subprocess.CompletedProcess(
                    command, 0 if created else 1, json.dumps({"url": "https://github.test/example/pull/17"}), "missing"
                )
            payload = {
                "number": 17,
                "url": "https://github.test/example/pull/17",
                "state": "MERGED" if merged else "OPEN",
                "isDraft": False,
                "mergeStateStatus": "CLEAN",
                "headRefOid": workspace["head"],
                "baseRefName": "master",
                "statusCheckRollup": [],
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        return subprocess.CompletedProcess(command, 0, "https://github.test/example/pull/17\n", "")

    delivery = GitHubDelivery(service.projects, service.workspaces, jobs, run=fake_run)
    (path / "late.txt").write_text("late change\n")
    subprocess.run(["git", "-C", str(path), "add", "late.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "late"],
        check=True,
    )
    workspace = service.workspaces.get(workspace["workspace_id"])
    with pytest.raises(DeliveryError, match="exact HEAD"):
        delivery.publish(workspace["workspace_id"], job_id, "Stale", "must not publish")
    assert calls == []
    replacement = service.dispatch(
        request(
            "job.start", "systemd-jobs",
            {"project_id": "fixture", "operation": "check", "workspace_id": workspace["workspace_id"]},
        )
    )
    assert replacement.ok and replacement.payload is not None
    job_id = replacement.payload.inline["job_id"]
    published = delivery.publish(workspace["workspace_id"], job_id, "Deliver fixture", "Verified body")
    reconciled = delivery.publish(workspace["workspace_id"], job_id, "Deliver fixture", "Verified body")
    landed = delivery.land(workspace["workspace_id"], job_id)
    finished = delivery.finish(workspace["workspace_id"])

    assert published["published"] and published["created"]
    assert reconciled["published"] and not reconciled["created"]
    assert landed["landed"] and finished["finished"]
    assert any(command[-7:-4] == ["git", "-C", str(path)] and "push" in command for command in calls)
    assert any(command[:3] == ["gh", "pr", "create"] for command in calls)
    assert any(command[:3] == ["gh", "pr", "merge"] for command in calls)
    assert not path.exists()
    assert sum(command[:3] == ["gh", "pr", "create"] for command in calls) == 1
    assert service.workspaces.list("fixture") == {"workspaces": []}


def test_typed_shell_and_agent_contracts_share_generic_job_lifecycle(tmp_path: Path) -> None:
    """Anti-vacuity: typed contracts must reach GenericJobs, not a second controller."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    systemd = FakeSystemdJobs(
        properties={"LoadState": "loaded", "ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    )
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd), native_runner=runner)

    shell = service.dispatch(
        request(
            "job.shell.start",
            "systemd-jobs",
            {"project_id": "fixture", "checkout_id": "default", "argv": ["printf", "shell-secret"], "cwd": ".", "timeout_seconds": 60, "result": "exit-status"},
            "operator",
        )
    )
    agent = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {"project_id": "fixture", "checkout_id": "default", "prompt": "private prompt", "backend": "codex", "model": "fixture", "effort": "high", "credential_profile": "subscription", "timeout_seconds": 60, "result": "last-message"},
            "agent-control",
        )
    )

    assert shell.ok and agent.ok
    assert shell.payload is not None and agent.payload is not None
    shell_job = shell.payload.inline
    agent_job = agent.payload.inline
    assert shell_job["kind"] == "operator-shell"
    assert shell_job["principal"] == "operator"
    assert shell_job["contract"]["argv"]["executable"] == "printf"
    assert agent_job["kind"] == "attested-agent"
    assert agent_job["principal"] == "agent-control"
    assert agent_job["contract"]["backend"] == "codex"
    assert agent_job["artifacts"]["result"]["max_bytes"] == 64_000
    persisted = (tmp_path / "state" / "jobs" / f"{agent_job['job_id']}.json").read_text()
    assert "private prompt" not in persisted
    assert "shell-secret" not in persisted
    assert len(systemd.started) == 2
    assert all(start["unit"].startswith("sinnixd-job-") for start in systemd.started)
    restarted = GenericJobs(systemd, service.jobs.store, wait_poll_seconds=0.001)
    assert {job["job_id"] for job in restarted.list()["jobs"]} == {shell_job["job_id"], agent_job["job_id"]}


def test_typed_contracts_refuse_spoofed_principals_checkout_backend_environment_and_results(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path), native_runner=runner)
    shell_arguments = {
        "project_id": "fixture", "checkout_id": "default", "argv": ["true"], "cwd": ".", "timeout_seconds": 60, "result": "exit-status"
    }
    agent_arguments = {
        "project_id": "fixture", "checkout_id": "default", "prompt": "prompt", "backend": "codex", "model": "fixture", "effort": "high", "credential_profile": "subscription", "timeout_seconds": 60, "result": "last-message"
    }
    invalid_principal = service.dispatch(request("job.shell.start", "systemd-jobs", shell_arguments, "observer"))
    invalid_checkout = service.dispatch(request("job.shell.start", "systemd-jobs", {**shell_arguments, "checkout_id": "absent"}, "operator"))
    invalid_backend = service.dispatch(request("job.agent.start", "systemd-jobs", {**agent_arguments, "backend": "unknown"}, "agent-control"))
    invalid_environment = service.dispatch(request("job.shell.start", "systemd-jobs", {**shell_arguments, "environment": {"SINNIXD_JOB_ID": "spoof"}}, "operator"))
    invalid_result = service.dispatch(request("job.agent.start", "systemd-jobs", {**agent_arguments, "result": "exit-status"}, "agent-control"))

    for response in (invalid_principal, invalid_checkout, invalid_backend, invalid_environment, invalid_result):
        assert response.error is not None
        assert response.error.code.value == "INVALID_ARGUMENT"


def test_failed_agent_launch_removes_private_prompt_and_contract_input(tmp_path: Path) -> None:
    """Anti-vacuity: a rejected launch cannot leave prompt material in durable state."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    class ConfirmedAbsent(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            raise SystemdJobError("fixture launch rejected")

    systemd = ConfirmedAbsent(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=generic_jobs(tmp_path, systemd), native_runner=runner)

    response = service.dispatch(
        request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "prompt": "private prompt removed after launch failure",
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "timeout_seconds": 60,
                "result": "last-message",
            },
            "agent-control",
        )
    )

    assert response.ok
    assert response.payload is not None
    assert response.payload.inline["state"]["phase"] == "launch-failed"
    assert not list((tmp_path / "state" / "inputs").iterdir())


def test_runner_rejects_changed_or_unregistered_checkout_identities(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    checkout = ProjectCatalog([tmp_path]).checkout("fixture", "default").to_dict()

    for changed in (
        {**checkout, "git_common_dir": str(tmp_path / "other-common-dir")},
        {**checkout, "head": "0" * 40},
        {**checkout, "project_path": str(tmp_path / "unregistered-project")},
    ):
        with pytest.raises(RunnerError):
            _revalidate_checkout(changed)

    symlink = tmp_path.parent / f"{tmp_path.name}-symlink"
    symlink.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RunnerError):
        _revalidate_checkout({**checkout, "path": str(symlink)})


def test_agent_runner_revalidates_checkout_and_writes_a_bounded_result_fixture(tmp_path: Path) -> None:
    """Anti-vacuity: the native runner only executes after Git identity and env checks pass."""
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    catalog = ProjectCatalog([tmp_path])
    checkout = catalog.checkout("fixture", "default")
    state = tmp_path / "state"
    inputs = state / "inputs"
    results = state / "results"
    native_state = state / "native"
    runner_arguments = state / "native-runner.args"
    inputs.mkdir(parents=True)
    results.mkdir()
    prompt = inputs / "fixture.prompt"
    prompt.write_text("private fixture prompt")
    payload = {
        "schema_version": 1,
        "job_id": "11111111-1111-1111-1111-111111111111",
        "kind": "attested-agent",
        "principal": "agent-control",
        "checkout": checkout.to_dict(),
        "backend": "codex",
        "model": "fixture",
        "effort": "high",
        "credential_profile": "subscription",
        "prompt_path": str(prompt),
        "result_path": str(results / "fixture.result"),
    }
    input_path = inputs / "fixture.json"
    input_path.write_text(json.dumps(payload))
    environment = {
        **os.environ,
        "SINNIXD_JOB_ID": payload["job_id"],
        "SINNIXD_PROJECT_ID": "fixture",
        "SINNIXD_CHECKOUT_ID": "default",
        "SINNIXD_PRINCIPAL": "agent-control",
        "SINNIXD_TIMEOUT_SECONDS": "60",
        "RUNNER_ARGS": str(runner_arguments),
    }
    result = subprocess.run(
        [sys.executable, "-m", "sinnixd.runner", "--input", str(input_path), "--job-id", payload["job_id"], "--unit", f"sinnixd-job-{payload['job_id']}.service", "--native-runner", str(runner), "--native-state-dir", str(native_state), "--state-root", str(state)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (results / "fixture.result").read_text() == "native-fixture-result"
    assert not prompt.exists()
    assert not input_path.exists()
    handoff = runner_arguments.read_text().splitlines()
    assert handoff[handoff.index("--registered-project") + 1] == str(
        checkout.project_path
    )
    assert handoff[handoff.index("--expected-git-common-dir") + 1] == str(checkout.git_common_dir)
    assert handoff[handoff.index("--workdir") + 1] == str(checkout.path)


def test_runner_rejects_forged_sinnix_environment(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    initialize_git_checkout(tmp_path)
    runner = tmp_path / "native-runner"
    native_runner(runner)
    checkout = ProjectCatalog([tmp_path]).checkout("fixture", "default")
    state = tmp_path / "state"
    inputs = state / "inputs"
    inputs.mkdir(parents=True)
    prompt = inputs / "fixture.prompt"
    prompt.write_text("private fixture prompt")
    job_id = "11111111-1111-1111-1111-111111111111"
    input_path = inputs / "fixture.json"
    input_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "job_id": job_id,
                "kind": "attested-agent",
                "principal": "agent-control",
                "checkout": checkout.to_dict(),
                "backend": "codex",
                "model": "fixture",
                "effort": "high",
                "credential_profile": "subscription",
                "prompt_path": str(prompt),
                "result_path": str(state / "results" / "fixture.result"),
            }
        )
    )
    environment = {
        **os.environ,
        "SINNIXD_JOB_ID": job_id,
        "SINNIXD_PROJECT_ID": "fixture",
        "SINNIXD_CHECKOUT_ID": "default",
        "SINNIXD_PRINCIPAL": "agent-control",
        "SINNIXD_TIMEOUT_SECONDS": "60",
        "SINNIXD_FORGED": "identity-overlay",
    }

    result = subprocess.run(
        [sys.executable, "-m", "sinnixd.runner", "--input", str(input_path), "--job-id", job_id, "--unit", f"sinnixd-job-{job_id}.service", "--native-runner", str(runner), "--native-state-dir", str(state / "native"), "--state-root", str(state)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "untrusted SINNIX identity" in result.stderr


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
        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
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

    result = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    record = jobs.store.load(result["job_id"])
    persisted = (tmp_path / "state" / "jobs" / f"{record.job_id}.json").read_text()
    assert result["unit"] == record.unit
    assert result["state"]["phase"] == "launch-failed"
    assert record.state["phase"] == "launch-failed"
    assert record.state["error"] == {"code": "systemd-job-error"}
    assert secret not in persisted


@pytest.mark.parametrize("mode", ("lost", "launch-failed"))
def test_terminal_systemd_errors_persist_only_stable_codes(tmp_path: Path, mode: str) -> None:
    """Anti-vacuity: persisting a SystemdJobError message writes this fixture secret to disk."""
    secret = "systemd-error-secret-do-not-persist"

    class FailingShow(FakeSystemdJobs):
        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            raise SystemdJobError(secret)

    class FailingStart(FakeSystemdJobs):
        def start(self, **kwargs) -> None:
            raise SystemdJobError(secret)

    jobs = generic_jobs(
        tmp_path,
        FailingShow() if mode == "lost" else FailingStart(properties={"LoadState": "not-found", "ActiveState": "inactive"}),
    )
    if mode == "launch-failed":
        status = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    else:
        started = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
        status = jobs.get(started["job_id"])

    persisted = (tmp_path / "state" / "jobs" / f"{status['job_id']}.json").read_text()

    assert status["state"]["phase"] == mode
    assert status["state"]["error"] == {"code": "systemd-job-error"}
    assert secret not in persisted
    assert '"message"' not in persisted


def test_launch_unknown_reconciles_to_observed_success_through_get_and_wait(tmp_path: Path) -> None:
    """Anti-vacuity: launch uncertainty must retain its identity until systemd later answers."""
    class ReplyAndFirstShowLost(FakeSystemdJobs):
        show_is_unavailable = True

        def start(self, **kwargs) -> None:
            self.started.append(dict(kwargs))
            raise SystemdJobError("reply unavailable")

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            if self.show_is_unavailable:
                raise SystemdJobError("manager unavailable")
            return super().show(unit, timeout_seconds=timeout_seconds)

    systemd = ReplyAndFirstShowLost()
    jobs = generic_jobs(tmp_path, systemd)
    uncertain = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    persisted = jobs.store.load(uncertain["job_id"])

    assert uncertain["unit"] == persisted.unit
    assert uncertain["state"]["phase"] == "launch-unknown"
    assert uncertain["state"]["error"] == {"code": "systemd-job-error"}
    assert not uncertain["state"]["terminal"]

    systemd.show_is_unavailable = False
    systemd.properties = {"LoadState": "loaded", "ActiveState": "active", "Result": "success"}
    running = jobs.get(uncertain["job_id"])
    systemd.properties = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    succeeded = jobs.wait(uncertain["job_id"], timeout_seconds=1)

    assert running["job_id"] == uncertain["job_id"]
    assert running["unit"] == uncertain["unit"]
    assert running["state"]["phase"] == "running"
    assert succeeded["job_id"] == uncertain["job_id"]
    assert succeeded["state"]["phase"] == "succeeded"


def test_launch_unknown_reconciles_to_launch_failed_when_systemd_confirms_absence(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: unavailable reconciliation must not relabel confirmed absence as ordinary missing."""
    class ReplyAndFirstShowLost(FakeSystemdJobs):
        show_is_unavailable = True

        def start(self, **kwargs) -> None:
            raise SystemdJobError("reply unavailable")

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            if self.show_is_unavailable:
                raise SystemdJobError("manager unavailable")
            return super().show(unit, timeout_seconds=timeout_seconds)

    systemd = ReplyAndFirstShowLost()
    jobs = generic_jobs(tmp_path, systemd)
    uncertain = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    systemd.show_is_unavailable = False
    systemd.properties = {"LoadState": "not-found", "ActiveState": "inactive"}

    failed = jobs.get(uncertain["job_id"])

    assert failed["job_id"] == uncertain["job_id"]
    assert failed["unit"] == uncertain["unit"]
    assert failed["state"]["phase"] == "launch-failed"
    assert failed["state"]["terminal"]


def test_launch_unknown_cancel_reconciles_the_same_job_id(tmp_path: Path) -> None:
    """Anti-vacuity: cancellation must operate on the durable uncertain launch record."""
    class ReplyAndFirstShowLost(FakeSystemdJobs):
        show_is_unavailable = True

        def start(self, **kwargs) -> None:
            raise SystemdJobError("reply unavailable")

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            if self.show_is_unavailable:
                raise SystemdJobError("manager unavailable")
            return super().show(unit, timeout_seconds=timeout_seconds)

    systemd = ReplyAndFirstShowLost(
        properties={"LoadState": "loaded", "ActiveState": "active", "InvocationID": "fixture-invocation"}
    )
    jobs = generic_jobs(tmp_path, systemd)
    uncertain = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    systemd.show_is_unavailable = False

    cancelled = jobs.cancel(uncertain["job_id"])

    assert systemd.stopped == [uncertain["unit"]]
    assert cancelled["job_id"] == uncertain["job_id"]
    assert cancelled["unit"] == uncertain["unit"]
    assert cancelled["state"]["phase"] == "cancelled"


def test_job_wait_caps_manager_calls_at_its_remaining_deadline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a blocked manager call must consume at most the wait's remaining budget."""
    clock = [0.0]

    class UnavailableSystemd(FakeSystemdJobs):
        timeouts: list[float] = []

        def start(self, **kwargs) -> None:
            raise SystemdJobError("reply unavailable")

        def show(
            self,
            unit: str,
            *,
            timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        ) -> dict[str, str]:
            self.timeouts.append(timeout_seconds)
            clock[0] += timeout_seconds
            raise SystemdJobError("manager unavailable")

    monkeypatch.setattr("sinnixd.jobs.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("sinnixd.jobs.time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    systemd = UnavailableSystemd()
    jobs = GenericJobs(systemd, GenericJobStore(tmp_path / "state"), wait_poll_seconds=0.1)
    uncertain = jobs.start_foreground(command=("fixture",), working_directory=str(tmp_path), environment={})
    systemd.timeouts.clear()
    clock[0] = 0.0

    timed_out = jobs.wait(uncertain["job_id"], timeout_seconds=1)

    assert timed_out["job_id"] == uncertain["job_id"]
    assert timed_out["state"]["phase"] == "launch-unknown"
    assert timed_out["wait_timed_out"]
    assert systemd.timeouts
    assert all(0 < timeout <= SYSTEMD_COMMAND_TIMEOUT_SECONDS for timeout in systemd.timeouts)
    assert clock[0] == 1.0


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
    assert profile.route.environment_profile is EnvironmentProfile.USER_BUS
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
