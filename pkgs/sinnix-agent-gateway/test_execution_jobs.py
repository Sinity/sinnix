from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import anyio
import pytest

from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.registry import REGISTRY
from sinnix_agent_gateway.runtime import ProtocolError
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
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses = {
        "job.agent.start": {"job_id": job_id, "state": {"phase": "running"}},
        "job.get": {"job_id": job_id, "state": {"phase": "running"}},
        "job.cancel": {"job_id": job_id, "cancel_requested": False},
    }
    monkeypatch.setattr(
        Runtime,
        "create",
        classmethod(lambda _cls, _config, _principal_name: runtime),
    )
    monkeypatch.setattr(
        runtime.beads,
        "get",
        lambda _project, _bead, **_kwargs: {
            "ref": "sinnix://projects/fixture/beads/fixture-1",
            "task_revision": "a" * 64,
            "etag": "b" * 64,
            "fields": {"title": "fixture", "status": "open"},
        },
    )
    claim_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        runtime.beads,
        "change",
        lambda _project, operation, parameters, **kwargs: claim_calls.append(
            {"operation": operation, "parameters": parameters, **kwargs}
        )
        or {
            "after": {
                "ref": "sinnix://projects/fixture/beads/fixture-1",
                "task_revision": "c" * 64,
                "etag": "d" * 64,
                "fields": {"title": "fixture", "status": "in_progress"},
            },
            "owner_route": "beads.change",
            "before_revision": "a" * 64,
            "after_revision": "c" * 64,
            "owner_history_ref": "sinnix://projects/fixture/beads/fixture-1/history/claim",
        },
    )
    monkeypatch.setattr(
        runtime.projects,
        "checkout",
        lambda _project, _checkout: {"checkout": {"checkout_id": "default", "head": "c" * 40}},
    )
    server = create_server(runtime.config, "operator")

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
            "action_name": "agent.for_bead",
            "idempotency_key": "public-agent-fixture",
            "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
            "ref": "sinnix://projects/fixture/beads/fixture-1",
            "checkout_id": "default",
            "claim_mode": "claim",
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
    assert started["data"]["claim_ref"] == "sinnix://projects/fixture/beads/fixture-1/claims/" + "d" * 64
    assert started["data"]["atomicity"] == "native_claim_then_daemon_launch"
    assert cancelled["result"]["action"] == "jobs.cancel"
    assert cancelled["data"]["cancel"]["cancel_requested"] is False
    assert [request.operation for request in daemon.calls] == [
        "job.agent.start",
        "job.get",
        "job.cancel",
    ]
    assert daemon.calls[0].principal == "agent-control"
    assert daemon.calls[0].arguments["timeout_seconds"] == 3_600
    assert daemon.calls[0].arguments["bead_binding"] == {
        "bead_ref": "sinnix://projects/fixture/beads/fixture-1",
        "project_ref": "sinnix://projects/fixture",
        "checkout_ref": "sinnix://projects/fixture/checkouts/default",
        "task_revision": "c" * 64,
        "task_etag": "d" * 64,
        "claim_ref": "sinnix://projects/fixture/beads/fixture-1/claims/" + "d" * 64,
        "claim_receipt": {
            "ref": "sinnix://projects/fixture/beads/fixture-1/claims/" + "d" * 64,
            "owner_route": "beads.change",
            "before_revision": "a" * 64,
            "after_revision": "c" * 64,
            "owner_history_ref": "sinnix://projects/fixture/beads/fixture-1/history/claim",
        },
        "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
        "assignment_ref": None,
    }
    assert claim_calls == [{
        "operation": "claim",
        "parameters": {"id": "fixture-1"},
        "preconditions": {"expected_task_revision": "a" * 64, "expected_etag": "b" * 64},
    }]


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


def test_v2_bead_agent_run_and_cancel_preserve_daemon_cancellation_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    daemon.responses = {
        "job.agent.start": {"job_id": job_id, "state": {"phase": "running"}},
        "job.get": {"job_id": job_id, "state": {"phase": "running"}},
        "job.cancel": {"job_id": job_id, "cancel_requested": False},
    }
    monkeypatch.setattr(
        runtime.beads,
        "get",
        lambda _project, _bead, **_kwargs: {
            "ref": "sinnix://projects/fixture/beads/fixture-1",
            "task_revision": "a" * 64,
            "etag": "b" * 64,
            "fields": {"title": "fixture", "status": "open"},
        },
    )
    monkeypatch.setattr(
        runtime.projects,
        "checkout",
        lambda _project, _checkout: {"checkout": {"checkout_id": "default", "head": "c" * 40}},
    )
    started = runtime.execute_v2(
        REGISTRY.action("agent.for_bead"),
        lambda: runtime.v2_run_for_bead(
            reference="sinnix://projects/fixture/beads/fixture-1",
            checkout_id="default",
            claim_mode="none",
            assignment_ref=None,
            instructions=None,
            backend="codex",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            timeout_seconds=3_600,
            credential_profile="subscription",
            request_id="2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
        ),
        {
            "ref": "sinnix://projects/fixture/beads/fixture-1",
            "checkout_id": "default",
            "backend": "codex",
            "model": "gpt-5.6-terra",
            "reasoning_effort": "high",
            "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
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
    assert daemon.calls[0].arguments["bead_binding"]["assignment_ref"] is None


def test_claimed_bead_launch_failure_is_partial_completion_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    monkeypatch.setattr(
        runtime.beads,
        "get",
        lambda _project, _bead, **_kwargs: {
            "ref": "sinnix://projects/fixture/beads/fixture-1",
            "task_revision": "a" * 64,
            "etag": "b" * 64,
        },
    )
    monkeypatch.setattr(
        runtime.projects,
        "checkout",
        lambda _project, _checkout: {"checkout": {"checkout_id": "default", "head": "c" * 40}},
    )
    monkeypatch.setattr(
        runtime.beads,
        "change",
        lambda *_args, **_kwargs: {
            "after": {
                "ref": "sinnix://projects/fixture/beads/fixture-1",
                "task_revision": "c" * 64,
                "etag": "d" * 64,
            },
            "owner_route": "beads.change",
        },
    )
    daemon.responses["job.agent.start"] = {
        "job_id": "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c",
        "state": {"phase": "launch-failed"},
    }
    request = {
        "ref": "sinnix://projects/fixture/beads/fixture-1",
        "checkout_id": "default",
        "backend": "codex",
        "model": "gpt-5.6-terra",
        "reasoning_effort": "high",
        "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
        "idempotency_key": "claim-launch-failure",
    }
    first = runtime.execute_v2(
        REGISTRY.action("agent.for_bead"),
        lambda: runtime.v2_run_for_bead(
            reference=request["ref"], checkout_id="default", claim_mode="claim",
            assignment_ref=None, instructions=None, backend="codex", model="gpt-5.6-terra",
            reasoning_effort="high", timeout_seconds=3_600,
            credential_profile="subscription", request_id=request["request_id"],
        ),
        request,
    )
    replay = runtime.execute_v2(
        REGISTRY.action("agent.for_bead"),
        lambda: pytest.fail("idempotent retry launched a second agent"),
        request,
    )

    assert first["error"]["code"] == "partial_completion"
    assert first["error"]["details"]["claim_ref"].endswith("/claims/" + "d" * 64)
    assert replay == first
    assert [request.operation for request in daemon.calls] == ["job.agent.start"]


def test_bead_review_and_evidence_close_require_bound_successful_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    bead = {"ref": "sinnix://projects/fixture/beads/fixture-1", "task_revision": "a" * 64, "etag": "b" * 64, "fields": {"title": "fixture", "status": "open"}}
    binding = {"bead_ref": bead["ref"], "project_ref": "sinnix://projects/fixture", "checkout_ref": "sinnix://projects/fixture/checkouts/default", "task_revision": "z" * 64, "task_etag": "y" * 64, "claim_ref": None, "claim_receipt": None, "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b", "assignment_ref": None}
    daemon.responses["job.get"] = {"job_id": job_id, "state": {"phase": "succeeded"}, "checkout": {"checkout_id": "default", "head": "c" * 40}, "contract": {"bead_binding": binding}, "artifacts": {"result": {"ref": f"sinnix://jobs/{job_id}/artifacts/result", "kind": "last-message"}}}
    daemon.responses["job.result"] = {"job_id": job_id, "kind": "last-message", "content": "untrusted prose", "truncated": False, "artifact": {"ref": f"sinnix://jobs/{job_id}/artifacts/result", "kind": "last-message"}}
    monkeypatch.setattr(runtime.beads, "get", lambda *_args, **_kwargs: bead)
    changes: list[dict[str, Any]] = []
    monkeypatch.setattr(runtime.beads, "change", lambda _project, operation, parameters, **kwargs: changes.append({"operation": operation, "parameters": parameters, **kwargs}) or {"after": bead})
    monkeypatch.setattr(runtime.projects, "checkout", lambda *_args: {"checkout": {"checkout_id": "default", "head": "d" * 40}})
    monkeypatch.setattr(runtime.projects, "summary", lambda *_args: {"head": "d" * 40})
    monkeypatch.setattr(runtime.projects, "commit_range", lambda *_args, **_kwargs: {"base_revision": "c" * 40, "head_revision": "d" * 40, "range": f"{'c' * 40}..{'d' * 40}", "relation": "base_is_ancestor", "merge_base": "c" * 40, "diff": "fixture diff", "truncated": False})

    review = runtime.v2_context(bead["ref"], "bead.review", f"sinnix://jobs/{job_id}")
    with pytest.raises(ProtocolError, match="current checkout"):
        runtime.v2_beads_change(reference=bead["ref"], operation="close_with_evidence", parameters={"verdict": "accepted", "residuals": [], "evidence_refs": [f"sinnix://jobs/{job_id}", f"sinnix://jobs/{job_id}/artifacts/result"], "job_ref": f"sinnix://jobs/{job_id}", "code_revision": "c" * 40, "task_revision": "a" * 64, "task_etag": "b" * 64}, preconditions=None)
    closed = runtime.v2_beads_change(reference=bead["ref"], operation="close_with_evidence", parameters={"verdict": "accepted", "residuals": [], "evidence_refs": [f"sinnix://jobs/{job_id}", f"sinnix://jobs/{job_id}/artifacts/result"], "job_ref": f"sinnix://jobs/{job_id}", "code_revision": "d" * 40, "task_revision": "a" * 64, "task_etag": "b" * 64}, preconditions=None)

    assert review["revision_mismatch"] == {"task_revision": True, "task_etag": True, "code_revision": True}
    assert review["checkout"]["commit_range"]["range"] == f"{'c' * 40}..{'d' * 40}"
    assert review["evidence"]["result"]["availability"] == "available"
    assert review["evidence"]["tests"]["availability"] == "unavailable"
    assert closed["closure"]["launch_task_revision"] == "z" * 64
    assert changes[0]["operation"] == "close"
    assert json.loads(changes[0]["parameters"]["reason"])["code_revision"] == "d" * 40

    daemon.responses["job.get"] = {**daemon.responses["job.get"], "state": {"phase": "cancelled"}}
    with pytest.raises(ProtocolError, match="cannot close"):
        runtime.v2_beads_change(reference=bead["ref"], operation="close_with_evidence", parameters={"verdict": "accepted", "residuals": [], "evidence_refs": [f"sinnix://jobs/{job_id}"], "job_ref": f"sinnix://jobs/{job_id}", "code_revision": "d" * 40, "task_revision": "a" * 64, "task_etag": "b" * 64}, preconditions=None)


def test_bead_review_exposes_exact_range_and_absent_result_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "operator")
    job_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    bead = {"ref": "sinnix://projects/fixture/beads/fixture-1", "task_revision": "a" * 64, "etag": "b" * 64}
    binding = {"bead_ref": bead["ref"], "project_ref": "sinnix://projects/fixture", "checkout_ref": "sinnix://projects/fixture/checkouts/default", "task_revision": "a" * 64, "task_etag": "b" * 64, "claim_ref": None, "claim_receipt": None, "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b", "assignment_ref": None}
    daemon.responses["job.get"] = {"job_id": job_id, "state": {"phase": "succeeded"}, "checkout": {"checkout_id": "default", "head": "c" * 40}, "contract": {"bead_binding": binding}, "artifacts": {"result": None}}
    monkeypatch.setattr(runtime.beads, "get", lambda *_args, **_kwargs: bead)
    monkeypatch.setattr(runtime.projects, "checkout", lambda *_args: {"checkout": {"checkout_id": "default", "head": "d" * 40}})
    monkeypatch.setattr(runtime.projects, "commit_range", lambda *_args, **_kwargs: {"base_revision": "c" * 40, "head_revision": "d" * 40, "range": f"{'c' * 40}..{'d' * 40}", "relation": "base_is_ancestor", "merge_base": "c" * 40, "diff": "exact fixture diff", "truncated": False})

    review = runtime.v2_context(bead["ref"], "bead.review", f"sinnix://jobs/{job_id}")

    assert review["checkout"]["commit_range"] == {
        "base_revision": "c" * 40,
        "head_revision": "d" * 40,
        "range": f"{'c' * 40}..{'d' * 40}",
        "relation": "base_is_ancestor",
        "merge_base": "c" * 40,
        "diff": "exact fixture diff",
        "truncated": False,
    }
    assert review["evidence"] == {
        "result": {"availability": "unavailable", "reason": "job declares no result artifact"},
        "tests": {"availability": "unavailable", "reason": "bead-bound attested-agent jobs declare no structured test result"},
    }
    assert "tests_and_artifacts" not in review
    assert [request.operation for request in daemon.calls] == ["job.get"]


def test_agent_control_bead_scope_requires_matching_current_assignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "agent-control")
    assignment_id = "3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
    assignment_ref = f"sinnix://jobs/{assignment_id}"
    bead = {"ref": "sinnix://projects/fixture/beads/fixture-1", "task_revision": "a" * 64, "etag": "b" * 64, "fields": {"title": "assigned"}}
    binding = {"bead_ref": bead["ref"], "project_ref": "sinnix://projects/fixture", "checkout_ref": "sinnix://projects/fixture/checkouts/default", "task_revision": "a" * 64, "task_etag": "b" * 64, "claim_ref": None, "claim_receipt": None, "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b", "assignment_ref": None}
    daemon.responses["job.get"] = {"job_id": assignment_id, "principal": "agent-control", "state": {"phase": "running"}, "checkout": {"checkout_id": "default", "head": "c" * 40}, "contract": {"bead_binding": binding}, "artifacts": {"result": None}}
    daemon.responses["job.agent.start"] = {"job_id": "4a42f848-9057-4cef-9d27-80a022c0e16f", "state": {"phase": "running"}}
    monkeypatch.setattr(runtime.beads, "get", lambda *_args, **_kwargs: bead)
    monkeypatch.setattr(runtime.projects, "checkout", lambda *_args: {"checkout": {"checkout_id": "default", "head": "c" * 40}})
    monkeypatch.setattr(runtime.projects, "summary", lambda *_args: {"head": "c" * 40})

    context = runtime.v2_context(bead["ref"], "bead.work", assignment_ref)
    started = runtime.v2_run_for_bead(
        reference=bead["ref"], checkout_id="default", claim_mode="none", assignment_ref=assignment_ref,
        instructions="private launch instruction", backend="codex", model="gpt-5.6-terra",
        reasoning_effort="high", timeout_seconds=60, credential_profile="subscription",
        request_id="4a42f848-9057-4cef-9d27-80a022c0e16f",
    )

    assert context["assignment"]["ref"] == assignment_ref
    assert started["assignment_ref"] == assignment_ref
    assert daemon.calls[-1].principal == "agent-control"
    assert daemon.calls[-1].arguments["bead_binding"]["assignment_ref"] == assignment_ref
    assert "private launch instruction" not in daemon.calls[-1].arguments["bead_binding"].values()

    foreign = {**binding, "bead_ref": "sinnix://projects/fixture/beads/fixture-2"}
    daemon.responses["job.get"] = {**daemon.responses["job.get"], "contract": {"bead_binding": foreign}}
    with pytest.raises(ProtocolError, match="not the requested"):
        runtime.v2_context(bead["ref"], "bead.work", assignment_ref)

    stale = {**binding, "task_etag": "d" * 64}
    daemon.responses["job.get"] = {**daemon.responses["job.get"], "contract": {"bead_binding": stale}}
    with pytest.raises(ProtocolError, match="stale"):
        runtime.v2_run_for_bead(
            reference=bead["ref"], checkout_id="default", claim_mode="none", assignment_ref=assignment_ref,
            instructions=None, backend="codex", model="gpt-5.6-terra", reasoning_effort="high",
            timeout_seconds=60, credential_profile="subscription", request_id="4a42f848-9057-4cef-9d27-80a022c0e16f",
        )

    with pytest.raises(ProtocolError, match="requires an assignment"):
        runtime.v2_run_for_bead(
            reference=bead["ref"], checkout_id="default", claim_mode="none", assignment_ref=None,
            instructions=None, backend="codex", model="gpt-5.6-terra", reasoning_effort="high",
            timeout_seconds=60, credential_profile="subscription", request_id="4a42f848-9057-4cef-9d27-80a022c0e16f",
        )


def test_v2_jobs_query_bounds_daemon_job_list_and_preserves_job_refs(tmp_path: Path) -> None:
    runtime, daemon = runtime_with_daemon(tmp_path, "observer")
    daemon.responses = {
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
    assert [request.operation for request in daemon.calls] == ["job.list"]
    assert daemon.calls[0].arguments == {"limit": 1}


def test_v2_jobs_query_emits_a_declared_typed_failure_for_an_invalid_bound(
    tmp_path: Path,
) -> None:
    runtime, _daemon = runtime_with_daemon(tmp_path, "observer")
    action = REGISTRY.action("jobs.query")

    response = runtime.execute_v2(
        action,
        lambda: runtime.v2_jobs_query({"limit": 0}),
        {"parameters": {"limit": 0}},
    )

    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["code"] in action.typed_failures


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
