from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from sinnix_mcp import RequestEnvelope

from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.jobs import JobError, JobService
from sinnix_agent_gateway.schemas import AgentLaunchRequest


def initialize_checkout(path: Path) -> None:
    path.mkdir()
    (path / "fixture.txt").write_text("fixture\n")
    for command in (
        ("git", "init", "--quiet", str(path)),
        ("git", "-C", str(path), "add", "."),
        (
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        ),
    ):
        subprocess.run(command, check=True)


@dataclass
class FakeSinnixd:
    calls: list[RequestEnvelope] = field(default_factory=list)
    responses: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __call__(self, _socket: Path, request: RequestEnvelope) -> dict[str, Any]:
        self.calls.append(request)
        payload = self.responses.get(request.operation, {"job_id": "job-fixture"})
        return {
            "schema": 1,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "owner": "systemd-jobs",
            "ok": True,
            "source_bindings": [],
            "receipt_ref": None,
            "payload": {"kind": "inline", "value": payload},
        }


def job_service(tmp_path: Path, principal_name: str) -> tuple[JobService, FakeSinnixd]:
    checkout = tmp_path / f"checkout-{principal_name}"
    initialize_checkout(checkout)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        sinnixd_socket=tmp_path / "sinnixd.sock",
        projects={"fixture": ProjectConfig(project_id="fixture", path=checkout)},
    )
    daemon = FakeSinnixd()
    return JobService(config, Principal.for_name(principal_name), transport=daemon), daemon


def test_agent_binding_forwards_only_the_typed_contract(tmp_path: Path) -> None:
    jobs, daemon = job_service(tmp_path, "agent-control")

    response = jobs.launch_agent(
        AgentLaunchRequest(
            project_id="fixture",
            prompt="implement fixture",
            backend="codex",
            model="gpt-5.6-terra",
            reasoning_effort="high",
        )
    )

    request = daemon.calls[-1]
    assert response == {"job_id": "job-fixture"}
    assert request.operation == "job.agent.start"
    assert request.owner == "systemd-jobs"
    assert request.principal == "agent-control"
    assert request.arguments == {
        "project_id": "fixture",
        "checkout_id": "default",
        "prompt": "implement fixture",
        "backend": "codex",
        "model": "gpt-5.6-terra",
        "effort": "high",
        "credential_profile": "subscription",
        "timeout_seconds": 14_400,
        "result": "last-message",
    }
    assert "environment" not in request.arguments
    assert "command" not in request.arguments


def test_operator_shell_binding_has_no_root_or_environment_escape_hatch(tmp_path: Path) -> None:
    jobs, daemon = job_service(tmp_path, "operator")

    jobs.start_shell(
        project_id="fixture",
        checkout_id="default",
        argv=["printf", "fixture"],
        cwd=".",
        timeout_seconds=60,
    )

    request = daemon.calls[-1]
    assert request.operation == "job.shell.start"
    assert request.owner == "systemd-jobs"
    assert request.principal == "operator"
    assert request.arguments == {
        "project_id": "fixture",
        "checkout_id": "default",
        "argv": ["printf", "fixture"],
        "cwd": ".",
        "timeout_seconds": 60,
        "result": "exit-status",
    }
    assert set(request.arguments).isdisjoint({"environment", "as_root", "command", "unit"})


def test_gateway_principal_gates_typed_job_starts(tmp_path: Path) -> None:
    observer, _daemon = job_service(tmp_path, "observer")
    operator, _daemon = job_service(tmp_path, "operator")

    with pytest.raises(PolicyError, match="shell.run"):
        observer.start_shell(
            project_id="fixture",
            checkout_id="default",
            argv=["true"],
            cwd=".",
            timeout_seconds=60,
        )
    with pytest.raises(JobError, match="agent-control"):
        operator.launch_agent(
            AgentLaunchRequest(
                project_id="fixture",
                prompt="fixture",
                backend="codex",
                model="gpt-5.6-terra",
                reasoning_effort="high",
            )
        )


def test_job_lifecycle_and_bounded_artifact_calls_map_to_sinnixd(tmp_path: Path) -> None:
    jobs, daemon = job_service(tmp_path, "agent-control")
    daemon.responses = {
        "job.list": {"jobs": [{"job_id": "one"}, {"job_id": "two"}]},
        "job.get": {"job_id": "one", "state": {"phase": "running"}},
        "job.logs": {"job_id": "one", "content": "log"},
        "job.result": {"job_id": "one", "content": "result"},
        "job.cancel": {"job_id": "one", "cancel_requested": True},
    }

    assert jobs.list(1) == {"jobs": [{"job_id": "one"}]}
    assert jobs.status("one")["state"]["phase"] == "running"
    assert jobs.read_output("one", "log", 4, 32)["content"] == "log"
    assert jobs.read_output("one", "result", 0, 32)["content"] == "result"
    assert jobs.cancel("one")["cancel_requested"] is True
    assert [request.operation for request in daemon.calls] == [
        "job.list",
        "job.get",
        "job.logs",
        "job.result",
        "job.cancel",
    ]
    assert daemon.calls[2].arguments == {"job_id": "one", "offset": 4, "max_bytes": 32}
    assert daemon.calls[3].arguments == {"job_id": "one", "max_bytes": 32}


@pytest.mark.parametrize(
    "response",
    [
        {"owner": "wrong-owner", "ok": True, "payload": {"kind": "inline", "value": {}}},
        {"owner": "systemd-jobs", "ok": True, "payload": {"kind": "opaque"}},
        {"owner": "systemd-jobs", "ok": False, "error": {"message": "typed rejection"}},
    ],
)
def test_malformed_or_rejected_daemon_responses_fail_closed(
    tmp_path: Path, response: dict[str, Any]
) -> None:
    jobs, _daemon = job_service(tmp_path, "agent-control")

    def malformed(_socket: Path, request: RequestEnvelope) -> dict[str, Any]:
        return {
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            **response,
        }

    jobs.transport = malformed
    with pytest.raises(JobError):
        jobs.status("one")
