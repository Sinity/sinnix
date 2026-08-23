from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import pytest
from sinnix_mcp import RequestEnvelope

from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.jobs import JobError, JobService
from sinnix_agent_gateway.registry import REGISTRY
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
    errors: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __call__(self, _socket: Path, request: RequestEnvelope) -> dict[str, Any]:
        self.calls.append(request)
        error = self.errors.get(request.operation)
        if error is not None:
            return {
                "schema": 1,
                "request_id": request.request_id,
                "correlation_id": request.correlation_id,
                "owner": "systemd-jobs",
                "ok": False,
                "source_bindings": [],
                "receipt_ref": None,
                "error": error,
            }
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


def job_service(
    tmp_path: Path, principal_name: str, *, max_result_bytes: int = 1_048_576
) -> tuple[JobService, FakeSinnixd]:
    checkout = tmp_path / f"checkout-{principal_name}"
    initialize_checkout(checkout)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        sinnixd_socket=tmp_path / "sinnixd.sock",
        projects={"fixture": ProjectConfig(project_id="fixture", path=checkout)},
        max_result_bytes=max_result_bytes,
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
        "job.wait": {"job_id": "one", "state": {"phase": "succeeded"}},
        "job.logs": {"job_id": "one", "content": "log"},
        "job.result": {"job_id": "one", "content": "result"},
        "job.cancel": {"job_id": "one", "cancel_requested": True},
    }

    assert jobs.list(1) == {"jobs": [{"job_id": "one"}]}
    assert jobs.status("one")["state"]["phase"] == "running"
    assert jobs.wait("one", timeout_seconds=30)["state"]["phase"] == "succeeded"
    assert jobs.read_output("one", "log", 4, 32)["content"] == "log"
    assert jobs.read_output("one", "result", 0, 32)["content"] == "result"
    assert jobs.cancel("one")["cancel_requested"] is True
    assert [request.operation for request in daemon.calls] == [
        "job.list",
        "job.get",
        "job.wait",
        "job.logs",
        "job.result",
        "job.cancel",
    ]
    assert daemon.calls[2].arguments == {"job_id": "one", "timeout_seconds": 30}
    assert daemon.calls[3].arguments == {"job_id": "one", "offset": 4, "max_bytes": 32}
    assert daemon.calls[4].arguments == {"job_id": "one", "max_bytes": 32}


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


def runtime_with_daemon(
    tmp_path: Path, principal_name: str, *, max_result_bytes: int = 1_048_576
) -> tuple[Runtime, FakeSinnixd]:
    jobs, daemon = job_service(
        tmp_path, principal_name, max_result_bytes=max_result_bytes
    )
    runtime = Runtime.create(jobs.config, principal_name)
    runtime.jobs.transport = daemon
    return runtime, daemon


def test_public_v2_job_verbs_dispatch_catalog_bound_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "agent-control")
    operator_runtime, operator_daemon = runtime_with_daemon(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses = {
        "job.agent.start": {"job_id": job_id, "state": {"phase": "running"}},
        "job.get": {"job_id": job_id, "state": {"phase": "running"}},
        "job.cancel": {
            "job_id": job_id,
            "cancel_requested": False,
            "state": {"phase": "running"},
        },
    }
    monkeypatch.setattr(
        Runtime,
        "create",
        classmethod(
            lambda _cls, _config, principal_name: {
                "agent-control": runtime,
                "operator": operator_runtime,
            }[principal_name]
        ),
    )
    server = create_server(runtime.config, "agent-control")
    operator_server = create_server(operator_runtime.config, "operator")

    async def invoke(
        target: Any, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        response = await target.call_tool(name, arguments)
        assert response.structured_content is not None
        return response.structured_content

    started = anyio.run(
        invoke,
        server,
        "run",
        {
            "action_name": "agents.run",
            "idempotency_key": "public-agent-fixture",
            "project_id": "fixture",
            "prompt": "inspect fixture",
            "backend": "codex",
            "model": "gpt-5.6-terra",
            "reasoning_effort": "high",
        },
    )
    cancelled = anyio.run(
        invoke,
        server,
        "operate",
        {
            "action_name": "jobs.cancel",
            "idempotency_key": "public-cancel-fixture",
            "ref": f"sinnix://jobs/{job_id}",
            "preconditions": {"expected_phase": "running"},
        },
    )
    rejected = anyio.run(
        invoke,
        operator_server,
        "run",
        {
            "action_name": "agents.run",
            "idempotency_key": "public-agent-denied",
            "project_id": "fixture",
            "prompt": "must not launch",
            "backend": "codex",
            "model": "gpt-5.6-terra",
            "reasoning_effort": "high",
        },
    )

    assert started["result"]["action"] == "agents.run"
    assert started["data"]["ref"] == f"sinnix://jobs/{job_id}"
    assert cancelled["result"]["action"] == "jobs.cancel"
    assert cancelled["data"]["cancel"]["cancel_requested"] is False
    assert rejected["error"]["code"] == "policy_denied"
    assert operator_daemon.calls == []
    assert [request.operation for request in daemon.calls] == [
        "job.agent.start",
        "job.get",
        "job.cancel",
    ]


def test_v2_run_and_wait_forward_the_same_daemon_job_identity(tmp_path: Path) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses = {
        "job.shell.start": {"job_id": job_id, "state": {"phase": "running"}},
        "job.wait": {"job_id": job_id, "state": {"phase": "succeeded"}},
        "job.logs": {"job_id": job_id, "content": "fixture output"},
    }

    run_action = REGISTRY.action("shell.run")
    run_request = {
        "project_id": "fixture",
        "checkout_id": "default",
        "argv": ["printf", "fixture"],
        "cwd": ".",
        "timeout_seconds": 60,
        "idempotency_key": "run-fixture",
    }
    started = runtime.execute_v2(
        run_action,
        lambda: runtime.v2_run_shell(
            project_id="fixture",
            checkout_id="default",
            argv=["printf", "fixture"],
            cwd=".",
            timeout_seconds=60,
        ),
        run_request,
    )
    replayed = runtime.execute_v2(
        run_action,
        lambda: pytest.fail("idempotent replay invoked the daemon start callback"),
        run_request,
    )
    waited = runtime.execute_v2(
        REGISTRY.action("jobs.wait"),
        lambda: runtime.v2_wait(started["data"]["ref"], 30),
        {"ref": started["data"]["ref"], "timeout_seconds": 30},
    )
    output = runtime.execute_v2(
        REGISTRY.action("resources.get"),
        lambda: runtime.v2_get(started["data"]["ref"], "log", 0, 64_000),
        {"ref": started["data"]["ref"], "projection": "log", "max_bytes": 64_000},
    )

    assert started["result"]["outcome"] == "ok"
    assert started["data"]["job_id"] == job_id
    assert started["data"]["ref"] == f"sinnix://jobs/{job_id}"
    assert replayed == started
    assert waited["result"]["outcome"] == "ok"
    assert waited["data"]["job_id"] == job_id
    assert waited["data"]["ref"] == started["data"]["ref"]
    assert output["data"] == {
        "ref": started["data"]["ref"],
        "kind": "job",
        "projection": "log",
        "job": {"job_id": job_id, "content": "fixture output"},
    }
    assert [request.operation for request in daemon.calls] == [
        "job.shell.start",
        "job.wait",
        "job.logs",
    ]
    assert [request.principal for request in daemon.calls] == [
        "operator",
        "operator",
        "operator",
    ]
    assert daemon.calls[0].arguments == {
        "project_id": "fixture",
        "checkout_id": "default",
        "argv": ["printf", "fixture"],
        "cwd": ".",
        "timeout_seconds": 60,
        "result": "exit-status",
    }
    assert daemon.calls[1].arguments == {"job_id": job_id, "timeout_seconds": 30}
    assert daemon.calls[2].arguments == {"job_id": job_id, "offset": 0, "max_bytes": 64_000}
    assert set(daemon.calls[0].arguments).isdisjoint(
        {"environment", "as_root", "command", "unit"}
    )


def test_v2_agent_run_and_job_cancel_preserve_typed_owner_truth(tmp_path: Path) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "agent-control")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses = {
        "job.agent.start": {"job_id": job_id, "state": {"phase": "running"}},
        "job.get": {"job_id": job_id, "state": {"phase": "running"}},
        "job.cancel": {"job_id": job_id, "cancel_requested": False, "state": {"phase": "running"}},
    }
    request = {
        "project_id": "fixture",
        "prompt": "inspect fixture",
        "backend": "codex",
        "model": "gpt-5.6-terra",
        "reasoning_effort": "high",
        "idempotency_key": "agent-fixture",
    }

    started = runtime.execute_v2(
        REGISTRY.action("agents.run"),
        lambda: runtime.v2_run_agent(
            project_id="fixture",
            checkout_id=None,
            prompt="inspect fixture",
            backend="codex",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            timeout_seconds=14_400,
            credential_profile="subscription",
        ),
        request,
    )
    replayed = runtime.execute_v2(
        REGISTRY.action("agents.run"),
        lambda: pytest.fail("idempotent replay invoked the daemon agent callback"),
        request,
    )
    cancel = runtime.execute_v2(
        REGISTRY.action("jobs.cancel"),
        lambda: runtime.v2_cancel_job(
            reference=started["data"]["ref"],
            preconditions={"expected_phase": "running"},
        ),
        {
            "ref": started["data"]["ref"],
            "preconditions": {"expected_phase": "running"},
            "idempotency_key": "cancel-fixture",
        },
    )

    assert replayed == started
    assert started["data"]["ref"] == f"sinnix://jobs/{job_id}"
    assert cancel["data"]["ref"] == f"sinnix://jobs/{job_id}"
    assert cancel["data"]["previous_state"]["state"]["phase"] == "running"
    assert cancel["data"]["cancel"]["cancel_requested"] is False
    assert [call.operation for call in daemon.calls] == [
        "job.agent.start",
        "job.get",
        "job.cancel",
    ]
    assert daemon.calls[0].arguments == {
        "project_id": "fixture",
        "checkout_id": "default",
        "prompt": "inspect fixture",
        "backend": "codex",
        "model": "gpt-5.6-terra",
        "effort": "high",
        "credential_profile": "subscription",
        "timeout_seconds": 14_400,
        "result": "last-message",
    }
    assert daemon.calls[2].arguments == {"job_id": job_id}


def test_v2_run_and_wait_preserve_typed_daemon_errors(tmp_path: Path) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.errors = {
        "job.shell.start": {
            "code": "OWNER_UNAVAILABLE",
            "message": "daemon start unavailable",
            "details": {"owner": "systemd-jobs"},
        },
        "job.wait": {
            "code": "RESULT_INVALID",
            "message": "daemon wait result invalid",
            "details": {"job_id": job_id},
        },
    }

    started = runtime.execute_v2(
        REGISTRY.action("shell.run"),
        lambda: runtime.v2_run_shell(
            project_id="fixture",
            checkout_id="default",
            argv=["true"],
            cwd=".",
            timeout_seconds=60,
        ),
        {
            "project_id": "fixture",
            "checkout_id": "default",
            "argv": ["true"],
            "idempotency_key": "run-error-fixture",
        },
    )
    waited = runtime.execute_v2(
        REGISTRY.action("jobs.wait"),
        lambda: runtime.v2_wait(f"sinnix://jobs/{job_id}", 30),
        {"ref": f"sinnix://jobs/{job_id}", "timeout_seconds": 30},
    )

    assert started["error"] == {
        "code": "unavailable",
        "message": "daemon start unavailable",
        "details": {"owner": "systemd-jobs"},
        "diagnostic_refs": [],
    }
    assert waited["error"] == {
        "code": "owner_failed",
        "message": "daemon wait result invalid",
        "details": {"job_id": job_id},
        "diagnostic_refs": [],
    }
    assert [request.operation for request in daemon.calls] == [
        "job.shell.start",
        "job.wait",
    ]


def test_v2_wait_rejects_a_different_daemon_job_identity(tmp_path: Path) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "observer")
    requested = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses["job.wait"] = {
        "job_id": "44bca584-51fb-4cf9-bf38-9ea31b8135ba",
        "state": {"phase": "succeeded"},
    }

    response = runtime.execute_v2(
        REGISTRY.action("jobs.wait"),
        lambda: runtime.v2_wait(f"sinnix://jobs/{requested}", 30),
        {"ref": f"sinnix://jobs/{requested}", "timeout_seconds": 30},
    )

    assert response["error"]["code"] == "owner_failed"
    assert response["error"]["message"] == (
        "sinnixd wait response does not match the requested job"
    )
    assert daemon.calls[-1].arguments == {
        "job_id": requested,
        "timeout_seconds": 30,
    }


def test_v2_run_authority_and_wait_result_bound_fail_closed(tmp_path: Path) -> None:
    observer, daemon = runtime_with_daemon(
        tmp_path, "observer", max_result_bytes=1_024
    )
    run_denied = observer.execute_v2(
        REGISTRY.action("shell.run"),
        lambda: observer.v2_run_shell(
            project_id="fixture",
            checkout_id="default",
            argv=["true"],
            cwd=".",
            timeout_seconds=60,
        ),
        {
            "project_id": "fixture",
            "checkout_id": "default",
            "argv": ["true"],
            "idempotency_key": "observer-run-denied",
        },
    )
    assert run_denied["error"]["code"] == "policy_denied"
    assert daemon.calls == []

    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses["job.wait"] = {
        "job_id": job_id,
        "state": {"phase": "running", "detail": "x" * 2_000},
    }
    oversized = observer.execute_v2(
        REGISTRY.action("jobs.wait"),
        lambda: observer.v2_wait(f"sinnix://jobs/{job_id}", 30),
        {"ref": f"sinnix://jobs/{job_id}", "timeout_seconds": 30},
    )

    assert oversized["error"]["code"] == "response_bound"
    assert daemon.calls[-1].operation == "job.wait"
    assert daemon.calls[-1].principal == "observer"


def test_v2_run_and_wait_reject_out_of_contract_arguments_before_forwarding(
    tmp_path: Path,
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")

    invalid_run = runtime.execute_v2(
        REGISTRY.action("shell.run"),
        lambda: runtime.v2_run_shell(
            project_id="fixture",
            checkout_id="default",
            argv=["true"],
            cwd=".",
            timeout_seconds=3_601,
        ),
        {
            "project_id": "fixture",
            "checkout_id": "default",
            "argv": ["true"],
            "idempotency_key": "invalid-run-timeout",
        },
    )
    invalid_wait = runtime.execute_v2(
        REGISTRY.action("jobs.wait"),
        lambda: runtime.v2_wait("sinnix://jobs/job-fixture", 301),
        {"ref": "sinnix://jobs/job-fixture", "timeout_seconds": 301},
    )

    assert invalid_run["error"]["code"] == "invalid_request"
    assert invalid_wait["error"]["code"] == "invalid_request"
    assert daemon.calls == []
