from __future__ import annotations

import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sinnix_mcp import RequestEnvelope

from sinnixd.api import UnixSocketServer, call, receive_frame, send_frame
from sinnixd.jobs import DeclaredProjectJobs, UserSystemdJobs
from sinnixd.projects import ProjectCatalog
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
    ) -> None:
        self.started.append(
            {
                "unit": unit,
                "command": command,
                "working_directory": working_directory,
                "environment": environment,
                "timeout_seconds": timeout_seconds,
            }
        )

    def show(self, unit: str) -> dict[str, str]:
        assert unit.startswith("sinnixd-job-")
        return self.properties

    def stop(self, unit: str) -> None:
        self.stopped.append(unit)


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


def test_user_systemd_jobs_starts_a_retained_service_with_declared_boundary(monkeypatch) -> None:
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


def test_declared_project_job_is_owned_by_a_transient_service(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs()
    service = SinnixdService(
        ProjectCatalog([tmp_path]),
        jobs=DeclaredProjectJobs(systemd, timeout_seconds=123),
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
    assert launch["command"] == ["fixture-env", "--command", "fixture-check"]
    assert len(systemd.started) == 1
    assert systemd.started[0]["working_directory"] == str(tmp_path.resolve())
    assert systemd.started[0]["timeout_seconds"] == 123
    assert systemd.started[0]["environment"]["SINNIXD_JOB_ID"] == launch["job_id"]
    assert systemd.started[0]["environment"]["SINNIXD_OPERATION"] == "check"

    status = service.dispatch(
        request("job.status", "systemd-jobs", {"job_id": launch["job_id"]})
    )
    cancelled = service.dispatch(
        request("job.cancel", "systemd-jobs", {"job_id": launch["job_id"]})
    )

    assert status.ok
    assert status.payload is not None
    assert status.payload.inline["systemd"]["MainPID"] == "42"
    assert cancelled.ok
    assert systemd.stopped == [launch["unit"]]


def test_declared_project_job_status_rejects_an_unloaded_unit(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    systemd = FakeSystemdJobs(properties={"LoadState": "not-found", "ActiveState": "inactive"})
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=DeclaredProjectJobs(systemd))

    response = service.dispatch(
        request("job.status", "systemd-jobs", {"job_id": str(uuid4())})
    )

    assert not response.ok
    assert response.owner == "systemd-jobs"
    assert response.error is not None
    assert response.error.code.value == "OPERATION_FAILED"
    assert "not loaded" in response.error.message


def test_declared_project_job_rejects_arbitrary_execution(tmp_path: Path) -> None:
    write_adapter(tmp_path)
    service = SinnixdService(ProjectCatalog([tmp_path]), jobs=DeclaredProjectJobs(FakeSystemdJobs()))

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


def test_unix_socket_server_round_trips_the_common_envelope(tmp_path: Path) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    service = SinnixdService(ProjectCatalog([tmp_path / "project"]))
    server = UnixSocketServer(socket_path, service)
    thread = threading.Thread(target=server.serve_once, daemon=True)
    thread.start()
    for _ in range(100):
        if socket_path.exists():
            break
        threading.Event().wait(0.01)

    response = call(socket_path, request("runtime.status", "sinnixd"))
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert response["ok"]
    assert response["payload"]["value"]["projects"] == 1


def test_unix_socket_server_returns_json_rpc_errors_without_crashing(tmp_path: Path) -> None:
    write_adapter(tmp_path / "project")
    socket_path = tmp_path / "sinnixd.sock"
    server = UnixSocketServer(socket_path, SinnixdService(ProjectCatalog([tmp_path / "project"])))
    thread = threading.Thread(target=server.serve_once, daemon=True)
    thread.start()
    for _ in range(100):
        if socket_path.exists():
            break
        threading.Event().wait(0.01)

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
    thread = threading.Thread(target=server.serve_forever, args=(stop_event,), daemon=True)
    thread.start()
    for _ in range(100):
        if socket_path.exists():
            break
        threading.Event().wait(0.01)

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
