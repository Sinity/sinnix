from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import pytest
from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.registry import REGISTRY
from sinnix_agent_gateway.runtime import DAEMON_ERROR_CLASSES, ProtocolError
from sinnix_mcp import (
    ErrorCode,
    ErrorEnvelope,
    OpaquePayload,
    RequestEnvelope,
    ResponseEnvelope,
)


@dataclass
class FakeJobs:
    """Stands in for LocalJobs: records every request, answers from a table."""

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


def runtime_with_jobs(
    tmp_path: Path, principal_name: str, *, max_result_bytes: int = 1_048_576
) -> tuple[Runtime, FakeJobs]:
    project = tmp_path / f"project-{principal_name}"
    project.mkdir()
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        max_result_bytes=max_result_bytes,
    )
    runtime = Runtime.create(config, principal_name)
    jobs = FakeJobs()
    runtime.jobs = jobs  # type: ignore[assignment]
    return runtime, jobs


async def invoke(target: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = await target.call_tool(name, arguments)
    assert response.structured_content is not None
    return response.structured_content


def test_gateway_preserves_stale_task_cursor_class() -> None:
    assert DAEMON_ERROR_CLASSES[ErrorCode.STALE_CURSOR] == "stale_cursor"


def test_public_run_starts_a_lane_and_cancel_forwards_the_queue_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if the public run verb stops reaching job.agent.start with the bead's
    identity, or if cancel asserts a terminal outcome the queue did not report."""
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
    job_id = "41"
    jobs.responses = {
        "job.agent.start": {
            "job_id": job_id,
            "state": {"phase": "queued"},
            "lane": {"bead": "fixture-1", "branch": "feature/packet/fixture-1"},
        },
        "job.get": {"job_id": job_id, "state": {"phase": "running"}},
        "job.cancel": {"job_id": job_id, "cancel_requested": True},
    }
    monkeypatch.setattr(
        Runtime, "create", classmethod(lambda _cls, _config, _principal: runtime)
    )
    server = create_server(runtime.config, "operator")

    started = anyio.run(
        invoke,
        server,
        "run",
        {
            "action_name": "agent.for_bead",
            "idempotency_key": "public-agent-fixture",
            "ref": "sinnix://projects/fixture/beads/fixture-1",
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
    assert started["result"]["action"] == "agent.for_bead"
    assert started["data"]["ref"] == f"sinnix://jobs/{job_id}"
    assert started["data"]["bead_ref"] == "sinnix://projects/fixture/beads/fixture-1"
    assert started["data"]["lane"]["branch"] == "feature/packet/fixture-1"
    assert cancelled["data"]["cancel"]["cancel_requested"] is True
    assert [request.operation for request in jobs.calls] == [
        "job.agent.start",
        "job.get",
        "job.cancel",
    ]
    assert jobs.calls[0].arguments == {
        "project_id": "fixture",
        "bead_id": "fixture-1",
        "backend": "codex",
        "model": "gpt-5.6-terra",
        "effort": "high",
    }


def test_lane_start_defaults_to_the_bead_model_policy_and_needs_a_bead_ref(
    tmp_path: Path,
) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
    jobs.responses["job.agent.start"] = {"job_id": "7", "state": {"phase": "queued"}}
    started = runtime.execute_v2(
        REGISTRY.action("agent.for_bead"),
        lambda: runtime.v2_run_for_bead(
            reference="sinnix://projects/fixture/beads/fixture-1",
            backend=None,
            model=None,
            reasoning_effort=None,
        ),
        {
            "ref": "sinnix://projects/fixture/beads/fixture-1",
            "idempotency_key": "policy-default",
        },
    )
    assert started["data"]["ref"] == "sinnix://jobs/7"
    assert jobs.calls[-1].arguments["backend"] is None
    with pytest.raises(ProtocolError, match="canonical Beads reference"):
        runtime.v2_run_for_bead(
            reference="sinnix://projects/fixture",
            backend=None,
            model=None,
            reasoning_effort=None,
        )


def test_v2_shell_run_wait_and_get_forward_one_job_identity(tmp_path: Path) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    jobs.responses = {
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
        lambda: pytest.fail("idempotent replay invoked the start callback"),
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
    assert [request.operation for request in jobs.calls] == [
        "job.shell.start",
        "job.wait",
        "job.logs",
    ]
    assert [request.principal for request in jobs.calls] == ["operator"] * 3
    assert jobs.calls[0].arguments == {
        "project_id": "fixture",
        "checkout_id": "default",
        "argv": ["printf", "fixture"],
        "cwd": ".",
        "timeout_seconds": 60,
        "result": "exit-status",
    }
    assert set(jobs.calls[0].arguments).isdisjoint(
        {"environment", "as_root", "command", "unit"}
    )


def test_v2_declared_operation_run_routes_only_typed_contract_and_job_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "agent-control")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    projection = {
        "job_id": job_id,
        "label": "fixture:service",
        "group": "normal",
        "state": {"phase": "running", "terminal": False, "exit_code": None},
    }
    jobs.responses = {
        "job.start": projection,
        "job.get": projection,
        "job.cancel": {"job_id": job_id, "cancel_requested": False},
    }
    monkeypatch.setattr(
        Runtime, "create", classmethod(lambda _cls, _config, _principal: runtime)
    )
    server = create_server(runtime.config, "agent-control")

    started = anyio.run(
        invoke,
        server,
        "run",
        {
            "action_name": "operations.run",
            "idempotency_key": "declared-start-fixture",
            "project_id": "fixture",
            "operation": "service",
            "workspace_id": "/realm/worktrees/fixture-lane",
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

    assert started["data"]["group"] == "normal"
    assert status["data"]["job"] == projection
    assert cancelled["data"]["cancel"]["cancel_requested"] is False
    assert [request.operation for request in jobs.calls] == [
        "job.start",
        "job.get",
        "job.get",
        "job.cancel",
    ]
    assert jobs.calls[0].arguments == {
        "project_id": "fixture",
        "operation": "service",
        "workspace_id": "/realm/worktrees/fixture-lane",
        "parameters": {"mode": "safe"},
    }


def test_v2_declared_operation_run_rejects_overlays_and_preserves_owner_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
    monkeypatch.setattr(
        Runtime, "create", classmethod(lambda _cls, _config, _principal: runtime)
    )
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
    assert jobs.calls == []

    jobs.errors["job.start"] = (
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


def test_job_review_context_reads_the_job_its_result_and_receipts(
    tmp_path: Path,
) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
    job_id = "12"
    jobs.responses = {
        "job.get": {
            "job_id": job_id,
            "project_id": "fixture",
            "state": {"phase": "succeeded", "terminal": True, "exit_code": 0},
        },
        "job.result": {"job_id": job_id, "kind": "exit", "value": {"exit_code": 0}},
    }
    review = runtime.v2_context(f"sinnix://jobs/{job_id}", "job.review")
    rows = {row["name"]: row for row in review["components"]}
    assert rows["job"]["status"] == "available"
    assert rows["result"]["status"] == "available"
    assert review["job"]["state"]["phase"] == "succeeded"
    assert review["result"]["value"] == {"exit_code": 0}
    assert [request.operation for request in jobs.calls] == ["job.get", "job.result"]
    with pytest.raises(ProtocolError, match="job.review requires a job reference"):
        runtime.v2_context("sinnix://projects/fixture", "job.review")
    with pytest.raises(ProtocolError, match="unknown context intent"):
        runtime.v2_context("sinnix://projects/fixture", "bead.work")


def test_v2_jobs_query_bounds_owner_job_list_and_preserves_job_refs(
    tmp_path: Path,
) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "observer")
    jobs.responses = {
        "job.list": {
            "jobs": [
                {"job_id": "first", "state": {"phase": "running"}},
            ],
            "limit": 1,
            "total": 2,
            "truncated": True,
            "next_cursor": "cursor-fixture",
            "snapshot": {
                "ordering": "created_at_desc_job_id_desc",
                "ceiling": ["2026-08-23T00:00:00+00:00", "first"],
            },
        }
    }

    response = runtime.execute_v2(
        REGISTRY.action("jobs.query"),
        lambda: runtime.v2_jobs_query({"limit": 1}),
        {"parameters": {"limit": 1}},
    )

    assert response["data"] == {
        "jobs": [
            {
                "ref": "sinnix://jobs/first",
                "job_id": "first",
                "state": {"phase": "running"},
            }
        ],
        "limit": 1,
        "total": 2,
        "truncated": True,
        "next_cursor": "cursor-fixture",
        "snapshot": {
            "ordering": "created_at_desc_job_id_desc",
            "ceiling": ["2026-08-23T00:00:00+00:00", "first"],
        },
    }
    assert [request.operation for request in jobs.calls] == ["job.list"]
    assert jobs.calls[0].arguments == {"limit": 1}


def test_v2_jobs_query_emits_a_declared_typed_failure_for_an_invalid_bound(
    tmp_path: Path,
) -> None:
    runtime, _jobs = runtime_with_jobs(tmp_path, "observer")
    action = REGISTRY.action("jobs.query")

    response = runtime.execute_v2(
        action,
        lambda: runtime.v2_jobs_query({"limit": 0}),
        {"parameters": {"limit": 0}},
    )

    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["code"] in action.typed_failures


def test_v2_job_routes_preserve_principal_policy(tmp_path: Path) -> None:
    observer, jobs = runtime_with_jobs(tmp_path, "observer", max_result_bytes=1_024)
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
    jobs.responses["job.wait"] = {
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
    assert waited["result"]["outcome"] == "ok"
    assert waited["data"]["truncated"] is True
    assert waited["data"]["artifact"]["ref"].startswith("sinnix://artifacts/")
    assert [request.operation for request in jobs.calls] == ["job.wait"]
    with pytest.raises(Exception, match="lacks capability job.start"):
        observer.v2_run_for_bead(
            reference="sinnix://projects/fixture/beads/fixture-1",
            backend=None,
            model=None,
            reasoning_effort=None,
        )


def test_v2_job_routes_preserve_typed_owner_errors(tmp_path: Path) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
    jobs.errors["job.shell.start"] = (
        ErrorCode.OWNER_UNAVAILABLE,
        "queue unavailable",
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
        "message": "queue unavailable",
        "details": {"owner": "systemd-jobs"},
        "diagnostic_refs": [],
    }
    jobs.errors["job.wait"] = (
        ErrorCode.RESULT_INVALID,
        "wait result invalid",
        {"job_id": "job-fixture"},
    )
    waited = runtime.execute_v2(
        REGISTRY.action("jobs.wait"),
        lambda: runtime.v2_wait("sinnix://jobs/job-fixture", 30),
        {"ref": "sinnix://jobs/job-fixture", "timeout_seconds": 30},
    )
    assert waited["error"] == {
        "code": "owner_failed",
        "message": "wait result invalid",
        "details": {"job_id": "job-fixture"},
        "diagnostic_refs": [],
    }


def test_v2_job_routes_reject_mismatched_owner_job_identity(tmp_path: Path) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "observer")
    requested = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    jobs.responses["job.wait"] = {
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
        == "job owner wait response does not match the requested job"
    )


def test_v2_job_routes_reject_out_of_contract_arguments_before_forwarding(
    tmp_path: Path,
) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
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
    assert jobs.calls == []
