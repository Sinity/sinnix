from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import pytest
from sinnix_agent_gateway.actions import BY_NAME as ACTIONS
from sinnix_agent_gateway.app import Runtime
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.registry import REGISTRY
from sinnix_agent_gateway.runtime import (
    DAEMON_ERROR_CLASSES,
    RESOURCE_READERS,
    ProtocolError,
)
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


def test_v2_get_reads_a_canonical_ref_through_the_action_that_owns_the_kind(
    tmp_path: Path,
) -> None:
    """Red if `resources/read` of a canonical ref has no reader behind it.

    The server registers a template per readable kind; a kind whose reader is
    missing answered every read with an AttributeError instead of data.
    """
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
    jobs.responses["job.get"] = {
        "job_id": "7",
        "label": "fixture:check",
        "project_id": "fixture",
        "state": {"phase": "succeeded", "terminal": True, "exit_code": 0},
    }

    payload = anyio.run(lambda: runtime.v2_get("sinnix://jobs/7"))

    assert payload["kind"] == "job" and payload["action"] == "jobs.get"
    assert payload["ref"] == "sinnix://jobs/7"
    assert payload["data"]["ref"] == "sinnix://jobs/7"
    assert payload["data"]["state"]["phase"] == "succeeded"
    assert jobs.calls[-1].operation == "job.get"

    with pytest.raises(ProtocolError, match="canonical resource was not found"):
        anyio.run(lambda: runtime.v2_get("sinnix://nope/1"))
    with pytest.raises(ProtocolError, match="no single-ref reader"):
        anyio.run(lambda: runtime.v2_get("sinnix://sessions/claude/abc"))


def test_every_published_resource_template_has_a_reader(tmp_path: Path) -> None:
    """Red if a kind is advertised as a template the gateway cannot read."""
    for kind, (name, _arguments) in RESOURCE_READERS.items():
        assert REGISTRY.resource(kind)
        assert name in ACTIONS, f"{kind} names an action that does not exist"
