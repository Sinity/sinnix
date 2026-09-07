"""Helpers shared by the gateway suites.

`call`/`ok`/`error` drive a built server the way an MCP client does: one
`call_tool` per invocation, unwrapping the structured content a typed action
returns. Suites that exercise a bare action against a `Runtime`, rather than a
server, keep their own differently-shaped helper.

Nothing here imports the production source-availability tables: the reasons in
`assert_unavailable_upstreams` are the wire strings a caller reads, and
asserting them against the module that emits them would prove nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import anyio
from mcp.types import CallToolResult


def call(server: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def invoke() -> Any:
        return await server.call_tool(name, arguments)

    result = anyio.run(invoke)
    if isinstance(result, CallToolResult):
        assert result.structured_content is not None
        return result.structured_content
    return result


def ok(server: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = call(server, name, arguments)
    assert response["result"]["outcome"] == "ok", response
    return response["data"]


def error(server: Any, name: str, arguments: dict[str, Any]) -> str:
    response = call(server, name, arguments)
    assert response["result"]["outcome"] != "ok", response
    return response["error"]["code"]


def assert_unavailable_upstreams(sources: list[dict[str, Any]]) -> None:
    unavailable = {
        row["source"]: row for row in sources if row["availability"] == "unavailable"
    }
    assert (
        unavailable["polylogue"]["reason"]
        == "upstream is intentionally unavailable on this host"
    )
    assert (
        unavailable["sinex"]["reason"]
        == "upstream is intentionally unavailable on this host"
    )
    assert (
        unavailable["lynchpin"]["reason"]
        == "no gateway semantic adapter is registered yet"
    )


@dataclass(frozen=True)
class JobCall:
    operation: str
    arguments: dict[str, Any]


@dataclass
class DirectJobs:
    """Typed owner double matching LocalJobs' direct operation methods."""

    default: dict[str, Any] = field(default_factory=lambda: {"job_id": "41"})
    calls: list[JobCall] = field(default_factory=list)
    responses: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, tuple[Any, ...]] = field(default_factory=dict)

    _operations = {
        "start": "job.start",
        "get": "job.get",
        "wait": "job.wait",
        "logs": "job.logs",
        "result": "job.result",
        "cancel": "job.cancel",
        "list": "job.list",
        "retry": "job.retry",
        "clean": "job.clean",
        "shell_start": "job.shell.start",
        "batch_list": "batch.list",
        "batch_start": "batch.start",
        "batch_status": "batch.status",
        "batch_land": "batch.land",
        "batch_resume": "batch.resume",
    }

    def __getattr__(self, name: str) -> Any:
        operation = self._operations.get(name)
        if operation is None:
            raise AttributeError(name)

        def call(**arguments: Any) -> dict[str, Any]:
            self.calls.append(JobCall(operation, dict(arguments)))
            error = self.errors.get(operation)
            if error is not None:
                from sinnix_agent_gateway.execution import JobOwnerError

                code, message, *details = error
                raise JobOwnerError(code, message, details[0] if details else {})
            answer = self.responses.get(operation, self.default)
            return answer(dict(arguments)) if callable(answer) else answer

        return call
