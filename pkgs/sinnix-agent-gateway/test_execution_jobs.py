from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from sinnix_agent_gateway.actions import BY_NAME as ACTIONS
from sinnix_agent_gateway.app import Runtime
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
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


def test_lane_start_defaults_to_the_bead_model_policy_and_needs_a_bead_ref(
    tmp_path: Path,
) -> None:
    runtime, jobs = runtime_with_jobs(tmp_path, "operator")
    jobs.responses["job.agent.start"] = {"job_id": "7", "state": {"phase": "queued"}}
    started = runtime.execute_v2(
        ACTIONS["agent.for_bead"],
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
