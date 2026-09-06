"""The published shape is the only accepted shape, and a wrong one says so.

A connector that nests a request under `parameters`, or sends a locator's own
fields at the top level, must get one typed refusal naming the accepted
envelope — never a silent misroute and never an untyped crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.types import CallToolResult
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.actions import beads, jobs
from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_mcp import OpaquePayload, RequestEnvelope, ResponseEnvelope

OWNED = (*jobs.ACTIONS, *beads.ACTIONS)

JOB = {
    "job_id": "41",
    "label": "fixture:check",
    "project_id": "fixture",
    "state": {"phase": "succeeded", "terminal": True, "exit_code": 0},
}


@dataclass
class FakeJobs:
    calls: list[RequestEnvelope] = field(default_factory=list)

    def dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        self.calls.append(request)
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner="systemd-jobs",
            payload=OpaquePayload.bounded({**JOB, "timed_out": False}),
        )


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    project = tmp_path / "project"
    project.mkdir()
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
    )
    runtime = Runtime.create(config, "operator")
    runtime.jobs = FakeJobs()  # type: ignore[assignment]
    monkeypatch.setattr(Runtime, "create", classmethod(lambda _c, _g, _p: runtime))
    monkeypatch.setattr(
        server_module,
        "visible_actions",
        lambda name: tuple(a for a in OWNED if name in a.principals),
    )
    return create_server(config, "operator")


def call(server: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def invoke() -> Any:
        return await server.call_tool(name, arguments)

    result = anyio.run(invoke)
    if isinstance(result, CallToolResult):
        assert result.structured_content is not None
        return result.structured_content
    return result


def refusal(server: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = call(server, name, arguments)
    assert response["result"]["outcome"] != "ok", response
    error = response["error"]
    assert error["code"] == "invalid_request", error
    return error


# The shapes a cold connector session actually sent instead of the published one.
MISROUTES: tuple[tuple[str, dict[str, Any], str], ...] = (
    ("jobs.wait", {"parameters": {"target": {"job_id": 41}}}, "target"),
    ("jobs.wait", {"job_id": 41}, "target"),
    ("beads.get", {"parameters": {"target": {"id": "fixture-1"}}}, "target"),
    ("beads.get", {"id": "fixture-1"}, "target"),
    ("beads.get", {"bead": {"id": "fixture-1"}}, "target"),
)


@pytest.mark.parametrize(("action", "arguments", "field_name"), MISROUTES)
def test_a_misrouted_argument_shape_is_refused_and_names_the_accepted_one(
    server: Any, action: str, arguments: dict[str, Any], field_name: str
) -> None:
    error = refusal(server, action, arguments)
    assert field_name in {problem["field"] for problem in error["details"]["problems"]}
    assert "target" in error["details"]["accepted_fields"]
    assert "target" in error["details"]["example"]
    assert action in error["message"]


def test_the_catalogued_shape_reaches_the_owner(server: Any) -> None:
    """The counterpart of every refusal above: the published shape works.

    A key the schema does not declare is dropped before the handler, so the
    payload is read from the declared fields or not at all.
    """
    waited = call(server, "jobs.wait", {"target": {"job_id": 41}})
    assert waited["result"]["outcome"] == "ok", waited
    assert waited["data"]["job_id"] == 41 and waited["data"]["outcome"] == "terminal"

    decorated = call(
        server, "jobs.wait", {"target": {"job_id": 41}, "parameters": {"job_id": 9}}
    )
    assert decorated["result"]["outcome"] == "ok", decorated
    assert decorated["data"]["job_id"] == 41


def test_every_action_example_is_the_shape_its_schema_publishes(server: Any) -> None:
    """Red if a catalogued example would itself be refused as a misroute."""
    for action in OWNED:
        for example in action.examples:
            assert set(example.input) <= set(action.Input.model_fields), action.name
            action.Input.model_validate(example.input)
