from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import pytest

from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.registry import REGISTRY
from sinnix_mcp import (
    ErrorCode,
    ErrorEnvelope,
    OpaquePayload,
    RequestEnvelope,
    ResponseEnvelope,
)


@dataclass
class FakeSinnixd:
    calls: list[RequestEnvelope] = field(default_factory=list)
    responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: dict[str, tuple[ErrorCode, str, dict[str, Any]]] = field(
        default_factory=dict
    )

    def dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        self.calls.append(request)
        error = self.errors.get(request.operation)
        if error is not None:
            code, message, details = error
            return ResponseEnvelope(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                owner="systemd-jobs",
                error=ErrorEnvelope(code, message, OpaquePayload.bounded(details)),
            )
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner="systemd-jobs",
            payload=OpaquePayload.bounded(
                self.responses.get(request.operation, {"job_id": "job-fixture"})
            ),
        )


def runtime_with_daemon(
    tmp_path: Path, principal_name: str, *, max_result_bytes: int = 1_048_576
) -> tuple[Runtime, FakeSinnixd]:
    project = tmp_path / f"project-{principal_name}"
    project.mkdir()
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        sinnixd_socket=tmp_path / "sinnixd.sock",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        max_result_bytes=max_result_bytes,
    )
    runtime = Runtime.create(config, principal_name)
    daemon = FakeSinnixd()
    runtime.sinnixd = daemon  # type: ignore[assignment]
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
        "job.cancel": {"job_id": job_id, "cancel_requested": False},
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


def test_v2_shell_run_wait_and_get_forward_one_daemon_job_identity(
    tmp_path: Path,
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses = {
        "job.shell.start": {"job_id": job_id, "state": {"phase": "running"}},
        "job.wait": {"job_id": job_id, "state": {"phase": "succeeded"}},
        "job.logs": {"job_id": job_id, "content": "fixture output"},
    }
    run_request = {
        "project_id": "fixture",
        "checkout_id": "default",
        "argv": ["printf", "fixture"],
        "cwd": ".",
        "timeout_seconds": 60,
        "idempotency_key": "run-fixture",
    }
    started = runtime.execute_v2(
        REGISTRY.action("shell.run"),
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
        REGISTRY.action("shell.run"),
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

    assert started["data"]["ref"] == f"sinnix://jobs/{job_id}"
    assert replayed == started
    assert waited["data"]["ref"] == started["data"]["ref"]
    assert output["data"]["job"] == {"job_id": job_id, "content": "fixture output"}
    assert [request.operation for request in daemon.calls] == [
        "job.shell.start",
        "job.wait",
        "job.logs",
    ]
    assert [request.principal for request in daemon.calls] == ["operator"] * 3
    assert daemon.calls[0].arguments == {
        "project_id": "fixture",
        "checkout_id": "default",
        "argv": ["printf", "fixture"],
        "cwd": ".",
        "timeout_seconds": 60,
        "result": "exit-status",
    }
    assert set(daemon.calls[0].arguments).isdisjoint(
        {"environment", "as_root", "command", "unit"}
    )


def test_v2_job_summary_preserves_daemon_service_lease_metadata(tmp_path: Path) -> None:
    """Anti-vacuity: Gateway job reads must expose the daemon lease rather than inventing a second service API."""
    runtime, daemon = runtime_with_daemon(tmp_path, "observer")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses["job.get"] = {
        "job_id": job_id,
        "state": {"phase": "running"},
        "lease": {
            "id": job_id,
            "host": "127.0.0.1",
            "readiness": "project-command",
            "lifetime": "job",
            "state": "active",
            "ports": [{"name": "http", "environment": "FIXTURE_HTTP_PORT", "port": 41000}],
        },
    }

    summary = runtime.v2_get(f"sinnix://jobs/{job_id}", "summary", 0, 64_000)

    assert summary["job"]["lease"]["ports"][0]["port"] == 41000
    assert [request.operation for request in daemon.calls] == ["job.get"]


def test_v2_declared_operation_run_routes_only_typed_contract_and_job_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "agent-control")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    projection = {
        "job_id": job_id,
        "state": {"phase": "running"},
        "lease": {
            "id": job_id,
            "host": "127.0.0.1",
            "readiness": "project-command",
            "lifetime": "job",
            "state": "active",
            "ports": [{"name": "http", "environment": "FIXTURE_HTTP_PORT", "port": 41000}],
        },
    }
    daemon.responses = {"job.start": projection, "job.get": projection, "job.cancel": {"job_id": job_id, "cancel_requested": False}}
    monkeypatch.setattr(Runtime, "create", classmethod(lambda _cls, _config, _principal: runtime))
    server = create_server(runtime.config, "agent-control")

    async def invoke(target: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = await target.call_tool(name, arguments)
        assert response.structured_content is not None
        return response.structured_content

    started = anyio.run(
        invoke,
        server,
        "run",
        {
            "action_name": "operations.run",
            "idempotency_key": "declared-start-fixture",
            "project_id": "fixture",
            "operation": "service",
            "workspace_id": "workspace-fixture",
            "parameters": {"mode": "safe"},
        },
    )
    status = anyio.run(invoke, server, "get", {"ref": started["data"]["ref"]})
    cancelled = anyio.run(
        invoke,
        server,
        "operate",
        {
            "action_name": "jobs.cancel",
            "ref": started["data"]["ref"],
            "idempotency_key": "declared-cancel-fixture",
            "preconditions": {"expected_phase": "running"},
        },
    )

    assert started["data"]["lease"]["ports"][0]["port"] == 41000
    assert status["data"]["job"]["lease"] == projection["lease"]
    assert cancelled["data"]["cancel"]["cancel_requested"] is False
    assert [request.operation for request in daemon.calls] == ["job.start", "job.get", "job.get", "job.cancel"]
    assert daemon.calls[0].arguments == {
        "project_id": "fixture",
        "operation": "service",
        "workspace_id": "workspace-fixture",
        "parameters": {"mode": "safe"},
    }


def test_v2_declared_operation_run_rejects_overlays_and_preserves_daemon_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    monkeypatch.setattr(Runtime, "create", classmethod(lambda _cls, _config, _principal: runtime))
    server = create_server(runtime.config, "operator")

    async def reject_overlay() -> dict[str, Any]:
        response = await server.call_tool(
            "run",
            {
                "action_name": "operations.run",
                "idempotency_key": "declared-overlay-fixture",
                "project_id": "fixture",
                "operation": "service",
                "argv": ["untrusted-command"],
                "checkout_id": "untrusted-checkout",
            },
        )
        assert response.structured_content is not None
        return response.structured_content

    rejected = anyio.run(reject_overlay)
    assert rejected["error"]["code"] == "invalid_request"
    assert daemon.calls == []

    daemon.errors["job.start"] = (
        ErrorCode.OWNER_UNAVAILABLE,
        "declared start unavailable",
        {"owner": "systemd-jobs"},
    )
    failed = runtime.execute_v2(
        REGISTRY.action("operations.run"),
        lambda: runtime.v2_run_declared_operation(
            project_id="fixture", operation="service", workspace_id=None, parameters={}
        ),
        {
            "project_id": "fixture",
            "operation": "service",
            "parameters": {},
            "idempotency_key": "declared-error-fixture",
        },
    )
    assert failed["error"] == {
        "code": "unavailable",
        "message": "declared start unavailable",
        "details": {"owner": "systemd-jobs"},
        "diagnostic_refs": [],
    }


def test_v2_agent_run_and_cancel_preserve_daemon_cancellation_truth(
    tmp_path: Path,
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "agent-control")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses = {
        "job.agent.start": {"job_id": job_id, "state": {"phase": "running"}},
        "job.get": {"job_id": job_id, "state": {"phase": "running"}},
        "job.cancel": {"job_id": job_id, "cancel_requested": False},
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
        {
            "project_id": "fixture",
            "prompt": "inspect fixture",
            "backend": "codex",
            "model": "gpt-5.6-terra",
            "reasoning_effort": "high",
            "idempotency_key": "agent-fixture",
        },
    )
    cancelled = runtime.execute_v2(
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

    assert cancelled["data"]["cancel"]["cancel_requested"] is False
    assert [request.operation for request in daemon.calls] == [
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


def test_v2_job_routes_preserve_principal_policy(tmp_path: Path) -> None:
    observer, daemon = runtime_with_daemon(
        tmp_path, "observer", max_result_bytes=1_024
    )
    denied = observer.execute_v2(
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
    daemon.responses["job.wait"] = {
        "job_id": "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c",
        "state": {"phase": "running", "detail": "x" * 2_000},
    }
    waited = observer.execute_v2(
        REGISTRY.action("jobs.wait"),
        lambda: observer.v2_wait(
            "sinnix://jobs/3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c", 30
        ),
        {
            "ref": "sinnix://jobs/3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c",
            "timeout_seconds": 30,
        },
    )

    assert denied["error"]["code"] == "policy_denied"
    assert waited["error"]["code"] == "response_bound"
    assert [request.operation for request in daemon.calls] == ["job.wait"]


def test_v2_job_routes_preserve_typed_daemon_errors(tmp_path: Path) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    daemon.errors["job.shell.start"] = (
        ErrorCode.OWNER_UNAVAILABLE,
        "daemon start unavailable",
        {"owner": "systemd-jobs"},
    )
    response = runtime.execute_v2(
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

    assert response["error"] == {
        "code": "unavailable",
        "message": "daemon start unavailable",
        "details": {"owner": "systemd-jobs"},
        "diagnostic_refs": [],
    }
    daemon.errors["job.wait"] = (
        ErrorCode.RESULT_INVALID,
        "daemon wait result invalid",
        {"job_id": "job-fixture"},
    )
    waited = runtime.execute_v2(
        REGISTRY.action("jobs.wait"),
        lambda: runtime.v2_wait("sinnix://jobs/job-fixture", 30),
        {"ref": "sinnix://jobs/job-fixture", "timeout_seconds": 30},
    )
    assert waited["error"] == {
        "code": "owner_failed",
        "message": "daemon wait result invalid",
        "details": {"job_id": "job-fixture"},
        "diagnostic_refs": [],
    }


def test_v2_job_routes_reject_mismatched_daemon_job_identity(tmp_path: Path) -> None:
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
    assert (
        response["error"]["message"]
        == "sinnixd wait response does not match the requested job"
    )


def test_v2_job_routes_reject_out_of_contract_arguments_before_forwarding(
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
