"""Brokered MCP: server health, the admitted tool catalog, read calls and write calls."""

from __future__ import annotations

import asyncio
import functools
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

import anyio
from pydantic import Field, ValidationError

from ..action import (
    OBSERVER_OPERATOR,
    OPERATOR_ONLY,
    Action,
    ActionResult,
    Example,
    MutationControls,
    RequestControls,
)
from ..capabilities import Capability
from ..catalog import search_rows
from ..contracts import EffectMode, VerbFamily
from ..locators import ARTIFACT_REF_PREFIX, McpToolLocator
from ..mcp_broker import (
    McpBrokerDeadlineError,
    McpBrokerError,
    McpBrokerTimeoutError,
    McpEnvironmentError,
)
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime


class ServerRow(GatewayModel):
    name: str
    description: str | None = None
    transport: str | None = None
    tier: str | None = None
    brokered: bool
    availability: Literal["available", "unavailable"]
    failure_class: str | None = None
    reason: str | None = None
    tool_count: int | None = None
    read_only_tool_count: int | None = None
    latency_ms: int | None = Field(
        default=None, description="Wall time of initialize + tools/list."
    )
    probed_at: str | None = None
    last_successful_probe: str | None = Field(
        default=None,
        description="probed_at when this probe succeeded; no probe history is kept.",
    )
    diagnostic_artifact_ref: str | None = Field(
        default=None,
        description="Captured upstream stderr when the probe failed or timed out.",
    )
    tools_truncated: bool = False


class ServersInput(RequestControls):
    servers: list[str] = Field(
        default_factory=list,
        max_length=32,
        description="Probe only these configured servers; empty probes all.",
    )


class Servers(GatewayModel):
    servers: list[ServerRow]
    affordances: list[str] = Field(default_factory=list)


def _server_row(
    name: str, probe: dict[str, Any], latency_ms: int | None, probed_at: str
) -> ServerRow:
    artifact_id = probe.get("diagnostic_artifact_id")
    return ServerRow(
        name=name,
        description=probe.get("description"),
        transport=probe.get("transport"),
        tier=probe.get("tier"),
        brokered=bool(probe.get("brokered")),
        availability=probe.get("availability", "unavailable"),
        failure_class=probe.get("failure_class"),
        reason=probe.get("reason"),
        tool_count=probe.get("tool_count"),
        read_only_tool_count=probe.get("read_only_tool_count"),
        latency_ms=latency_ms,
        probed_at=probed_at,
        last_successful_probe=probed_at
        if probe.get("availability") == "available"
        else None,
        diagnostic_artifact_ref=f"{ARTIFACT_REF_PREFIX}{artifact_id}"
        if isinstance(artifact_id, str)
        else None,
        tools_truncated=bool(probe.get("tools_truncated")),
    )


async def _servers(runtime: Runtime, inp: ServersInput) -> Servers:
    runtime.principal.require(Capability.MCP_READ)
    configured = runtime.config.mcp_broker_servers
    unknown = sorted(set(inp.servers) - set(configured))
    if unknown:
        raise ProtocolError(
            "not_found", "MCP server is not configured", details={"unknown": unknown}
        )
    names = sorted(inp.servers or configured)

    async def timed(name: str) -> ServerRow:
        started = time.monotonic()
        probed_at = datetime.now(tz=timezone.utc).isoformat()
        row = configured[name]
        probe = (
            await runtime.mcp_broker._catalog_server(name, row)
            if isinstance(row, dict)
            else {"availability": "unavailable", "reason": "malformed configuration"}
        )
        return _server_row(
            name,
            probe,
            int((time.monotonic() - started) * 1000) if probe.get("brokered") else None,
            probed_at,
        )

    rows = await asyncio.gather(*(timed(name) for name in names))
    return Servers(
        servers=list(rows), affordances=["mcp.tools", "mcp.call", "artifacts.read"]
    )


# ----------------------------------------------------------------------- tools


class ToolRow(GatewayModel):
    ref: str
    server: str
    name: str
    description: str | None = None
    effect: Literal["read", "change"]
    input_schema: dict[str, Any]
    input_schema_artifact: dict[str, Any] | None = None
    input_schema_bytes: int | None = None


class ToolsInput(RequestControls):
    server: str | None = Field(default=None, max_length=128)
    text: str | None = Field(
        default=None,
        max_length=512,
        description="Terms matched against name, description and server.",
    )
    effect: Literal["any", "read", "change"] = "any"
    include_schema: bool = True
    limit: int = Field(default=200, ge=1, le=2_000)


class Tools(GatewayModel):
    tools: list[ToolRow]
    total: int
    truncated: bool
    servers_unavailable: dict[str, str] = Field(
        default_factory=dict,
        description="Server name to reason for servers that disclosed no tools.",
    )
    catalog_artifact: dict[str, Any] | None = None
    affordances: list[str] = Field(default_factory=list)


async def _tools(runtime: Runtime, inp: ToolsInput) -> Tools:
    try:
        catalog = await runtime.mcp_broker.catalog()
    except McpBrokerError as exc:
        raise ProtocolError("unavailable", str(exc)) from exc
    rows: list[dict[str, Any]] = []
    unavailable: dict[str, str] = {}
    for server in catalog.get("servers", []):
        if inp.server is not None and server.get("name") != inp.server:
            continue
        if server.get("availability") != "available":
            unavailable[server["name"]] = (
                server.get("reason") or server.get("failure_class") or "unavailable"
            )
            continue
        for tool in server.get("tools", []):
            rows.append({**tool, "server": server["name"]})
    if inp.effect != "any":
        rows = [row for row in rows if row["effect"] == inp.effect]
    rows = search_rows(rows, inp.text, ("name", "description", "server"))
    typed = [
        ToolRow.model_validate(
            dict(row)
            if inp.include_schema
            else {**row, "input_schema": {}, "input_schema_artifact": None}
        )
        for row in rows[: inp.limit]
    ]
    return Tools(
        tools=typed,
        total=len(rows),
        truncated=len(rows) > inp.limit or bool(catalog.get("truncated")),
        servers_unavailable=unavailable,
        catalog_artifact=catalog.get("catalog_artifact"),
        affordances=["mcp.call", "mcp.change", "mcp.servers"],
    )


# ------------------------------------------------------------------ call/change


class CallInput(RequestControls):
    target: McpToolLocator
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments matching the tool's input_schema from mcp.tools.",
    )


class ChangeInput(MutationControls):
    target: McpToolLocator
    arguments: dict[str, Any] = Field(default_factory=dict)


class CallResult(GatewayModel):
    ref: str
    server: str
    tool: str
    mode: Literal["read", "write"]
    response: dict[str, Any] | None = None
    truncated: bool
    artifact: dict[str, Any] | None = None
    artifact_id: str | None = None
    affordances: list[str] = Field(default_factory=list)


_SELF_SERVER_NAMES = frozenset({"sinnix-agent-gateway", "sinnix-gateway"})


async def _invoke_self(
    runtime: Runtime,
    *,
    server: str,
    tool: str,
    ref: str,
    arguments: dict[str, Any],
    write: bool,
) -> CallResult | ActionResult:
    """Route the model's common self-broker spelling to a direct read tool.

    ChatGPT can discover the gateway through ``gateway.catalog`` and then
    incorrectly treat its own action set as a brokered upstream.  Preserve
    the direct tool's validation, audit receipt and content blocks rather
    than returning a misleading missing-server error.  Mutation remains
    direct-only, so this alias cannot widen write authority.
    """
    # Imported lazily because this module is one member of actions.__init__.
    from ..actions import BY_NAME as actions_by_name

    action = actions_by_name.get(tool)
    if action is None:
        raise ProtocolError(
            "not_found", "gateway action is not configured", details={"tool": tool}
        )
    if write or action.effect is not EffectMode.READ or action.name.startswith("mcp."):
        raise ProtocolError(
            "invalid_request",
            "self-broker routing supports direct read actions only; invoke changes by their action name",
            details={"tool": tool},
        )
    if runtime.principal_name not in action.principals:
        raise ProtocolError(
            "policy_denied", "principal cannot invoke the requested gateway action"
        )
    try:
        request_input = action.Input.model_validate(dict(arguments))
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "request"
        raise ProtocolError(
            "invalid_request", f"{location}: {first.get('msg')}"
        ) from exc

    blocks: list[Any] = []

    async def callback() -> Any:
        if action.is_async:
            raw = await action.handler(runtime, request_input)
        else:
            raw = await anyio.to_thread.run_sync(
                functools.partial(action.handler, runtime, request_input)
            )
        if isinstance(raw, ActionResult):
            blocks.extend(raw.blocks)
            raw = raw.data
        try:
            return action.Output.model_validate(raw).model_dump(
                mode="json", by_alias=True
            )
        except ValidationError as exc:
            raise ProtocolError(
                "owner_failed",
                "owner result does not match the declared output",
                details={"problems": exc.errors(include_url=False)[:8]},
            ) from exc

    nested = await runtime.execute_v2_async(
        action, callback, request_input.model_dump(mode="json")
    )
    if nested["result"]["outcome"] != "ok":
        error = nested["error"] or {}
        raise ProtocolError(
            error.get("code", "owner_failed"),
            error.get("message", "gateway action failed"),
            details=error.get("details", {}),
        )
    result = CallResult(
        ref=ref,
        server=server,
        tool=tool,
        mode="read",
        response=nested["data"],
        truncated=False,
        affordances=[tool],
    )
    return ActionResult(result, blocks=blocks) if blocks else result


async def _invoke(
    runtime: Runtime,
    target: McpToolLocator,
    arguments: dict[str, Any],
    *,
    write: bool,
    deadline_at: float | None = None,
) -> CallResult:
    server, tool, ref = target.resolve()
    if server in _SELF_SERVER_NAMES:
        return await _invoke_self(
            runtime,
            server=server,
            tool=tool,
            ref=ref,
            arguments=arguments,
            write=write,
        )
    if server not in runtime.config.mcp_broker_servers:
        raise ProtocolError(
            "not_found", "MCP server is not configured", details={"server": server}
        )
    try:
        result = await runtime.mcp_broker.call(
            server, tool, dict(arguments), write=write, deadline_at=deadline_at
        )
    except McpEnvironmentError as exc:
        raise ProtocolError("unavailable", str(exc)) from exc
    except McpBrokerDeadlineError as exc:
        raise ProtocolError("deadline", str(exc)) from exc
    except McpBrokerTimeoutError as exc:
        raise ProtocolError("unavailable", str(exc)) from exc
    except McpBrokerError as exc:
        message = str(exc)
        if "does not expose tool" in message:
            raise ProtocolError("not_found", message) from exc
        if "unavailable" in message:
            raise ProtocolError("unavailable", message) from exc
        raise ProtocolError("invalid_request", message) from exc
    return CallResult(
        ref=ref,
        **result,
        affordances=["artifacts.read", "mcp.tools"]
        if result.get("truncated")
        else ["mcp.tools"],
    )


async def _call(runtime: Runtime, inp: CallInput) -> CallResult:
    return await _invoke(
        runtime,
        inp.target,
        inp.arguments,
        write=False,
        deadline_at=inp.deadline_at,
    )


async def _change(runtime: Runtime, inp: ChangeInput) -> CallResult:
    return await _invoke(
        runtime,
        inp.target,
        inp.arguments,
        write=True,
        deadline_at=inp.deadline_at,
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="mcp.servers",
        family=VerbFamily.STATUS,
        owner="mcp-broker",
        summary="Probe brokered MCP servers: availability, failure class, latency, tool counts, diagnostic artifact on timeout.",
        Input=ServersInput,
        Output=Servers,
        handler=_servers,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("mcp_tool",),
        affordances=("mcp.tools", "mcp.call", "artifacts.read"),
        aliases=(
            "mcp health",
            "is polylogue mcp up",
            "upstream servers",
            "broker status",
        ),
        documentation="Each probe runs initialize + tools/list within the configured call timeout, capped at 30 seconds; the observer process uses the same bound. A timeout stores the upstream stderr as an artifact and returns its ref.",
        examples=(
            Example(title="Probe one server", input={"servers": ["polylogue"]}),
            Example(title="Probe all", input={}),
        ),
    ),
    Action(
        name="mcp.tools",
        family=VerbFamily.CATALOG,
        owner="mcp-broker",
        summary="Catalog of every admitted upstream tool with its namespaced ref, input schema and read/change effect.",
        Input=ToolsInput,
        Output=Tools,
        handler=_tools,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("mcp_tool",),
        affordances=("mcp.call", "mcp.change", "mcp.servers"),
        aliases=("list mcp tools", "upstream tools", "tool schema"),
        examples=(
            Example(
                title="Read tools mentioning search",
                input={"text": "search", "effect": "read"},
            ),
        ),
    ),
    Action(
        name="mcp.call",
        family=VerbFamily.QUERY,
        owner="mcp-broker",
        summary="Invoke an upstream read admitted by owner annotation or trusted registry selectors.",
        Input=CallInput,
        Output=CallResult,
        handler=_call,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("mcp_tool",),
        affordances=("mcp.tools", "artifacts.read"),
        aliases=("call mcp tool", "query upstream", "polylogue search"),
        documentation="Reads require an owner read-only annotation or an exact match to trusted registry selectors. Other requests require mcp.change (operator only). A target using server=sinnix-agent-gateway is routed to the named direct read action, preserving its native content blocks; changes stay direct-only.",
        examples=(
            Example(
                title="Call by server and tool",
                input={
                    "target": {"server": "polylogue", "tool": "search"},
                    "arguments": {"query": "gateway"},
                },
            ),
        ),
    ),
    Action(
        name="mcp.change",
        family=VerbFamily.CHANGE,
        owner="mcp-broker",
        summary="Invoke an upstream request not admitted as read-only by annotation or trusted registry selectors.",
        Input=ChangeInput,
        Output=CallResult,
        handler=_change,
        principals=OPERATOR_ONLY,
        resource_kinds=("mcp_tool",),
        affordances=("mcp.tools", "artifacts.read", "audit.receipt"),
        aliases=("write mcp tool", "mutate upstream", "refresh"),
        examples=(
            Example(
                title="Call a write tool",
                input={
                    "target": {"ref": "sinnix://mcp/lynchpin/tools/refresh"},
                    "arguments": {},
                    "idempotency_key": "mcp-refresh-example",
                },
            ),
        ),
    ),
)
