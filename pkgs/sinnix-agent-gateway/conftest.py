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
