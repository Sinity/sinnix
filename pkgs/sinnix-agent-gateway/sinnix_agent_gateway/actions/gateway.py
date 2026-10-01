"""The gateway's own surface: status and the one catalog search."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Literal

import anyio
from pydantic import BaseModel, ConfigDict, Field

from ..action import ALL_PRINCIPALS, Action, Example, MutationControls, RequestControls
from ..capabilities import Capability
from ..catalog import search_rows
from ..contracts import VerbFamily
from ..schemas import GatewayModel
from ..results import ProtocolError

if TYPE_CHECKING:
    from ..runtime import Runtime

FAMILIES = Literal[
    "status",
    "catalog",
    "query",
    "get",
    "context",
    "events",
    "wait",
    "change",
    "operate",
    "run",
]


class GatewayStatus(BaseModel):
    """Owner-shaped status: keys are the observe service's, kept open."""

    model_config = ConfigDict(extra="allow")

    principal: str
    route_preflight: dict[str, Any]


class StatusInput(RequestControls):
    pass


async def _status(runtime: Runtime, inp: StatusInput) -> GatewayStatus:
    from .. import actions as action_set

    manifest = await runtime.tool_manifest()
    # Hashing the catalog serializes every schema; off the event loop.
    catalog_hash = await anyio.to_thread.run_sync(
        action_set.catalog_hash, runtime.principal_name
    )
    status = await runtime.gateway_status(
        runtime.principal_contract_hash(),
        manifest["sha256"],
        catalog_hash,
        action_set.REVISION,
    )
    status["tool_count"] = len(manifest["tools"])
    return GatewayStatus.model_validate(status)


class CatalogInput(RequestControls):
    query: str | None = Field(
        default=None,
        max_length=256,
        description="Free text matched against names, summaries, aliases, owners and resource kinds.",
    )
    family: FAMILIES | None = None
    domain: str | None = Field(default=None, max_length=64)
    resource_kind: str | None = Field(default=None, max_length=64)
    include_schemas: bool = Field(
        default=False, description="Attach each action's input schema (large)."
    )
    include_mcp_tools: bool = Field(
        default=True, description="Also search brokered MCP server tools."
    )
    limit: int = Field(default=50, ge=1, le=500)


class CatalogAction(GatewayModel):
    name: str
    family: str
    domain: str
    owner: str
    summary: str
    aliases: list[str]
    affordances: list[str]
    resource_kinds: list[str]
    principals: list[str]
    effect: str
    example: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None


class CatalogResource(GatewayModel):
    kind: str
    owner: str
    ref_template: str
    actions: list[str]


class CatalogMcpTool(GatewayModel):
    ref: str
    server: str
    name: str
    description: str | None = None
    effect: str | None = None
    invoke: str


class Catalog(GatewayModel):
    revision: str
    catalog_sha256: str
    actions: list[CatalogAction]
    resources: list[CatalogResource]
    mcp_tools: list[CatalogMcpTool] = Field(default_factory=list)
    mcp_unavailable: list[str] = Field(default_factory=list)
    mcp_coverage_incomplete: dict[str, str] = Field(default_factory=dict)
    mcp_catalog_truncated: bool = False
    mcp_catalog_artifact: dict[str, Any] | None = None
    truncated: bool = False


class DescribeInput(RequestControls):
    action: str = Field(min_length=1, max_length=256)


class Description(GatewayModel):
    action: dict[str, Any]
    structural_sha256: str


async def _describe(runtime: Runtime, inp: DescribeInput) -> Description:
    from .. import actions as action_set

    action = action_set.BY_NAME.get(inp.action)
    if action is None or runtime.principal_name not in action.principals:
        raise ProtocolError("not_found", "action is not visible to this principal")
    row = action.catalog_row()
    digest = hashlib.sha256(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return Description(action=row, structural_sha256=digest)


class ReadInput(RequestControls):
    action: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict)


class EffectInput(MutationControls):
    action: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict)


class Dispatched(GatewayModel):
    """The tool wrapper returns the selected action's native envelope instead."""


def _dispatch_only(_runtime: Runtime, _inp: ReadInput | EffectInput) -> Dispatched:
    raise ProtocolError(
        "invalid_request", "core dispatch requires the action tool wrapper"
    )


def _action_matches(
    runtime: Runtime, inp: CatalogInput
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """The matching action and resource rows and the catalog digest.

    Pure CPU over every action's schema, so it runs in a worker thread.
    """
    from .. import actions as action_set

    rows = []
    for action in action_set.visible(runtime.principal_name):
        if inp.family and action.family.value != inp.family:
            continue
        if inp.domain and action.domain != inp.domain:
            continue
        if inp.resource_kind and inp.resource_kind not in action.resource_kinds:
            continue
        rows.append(
            {
                "name": action.name,
                "family": action.family.value,
                "domain": action.domain,
                "owner": action.owner,
                "summary": action.summary,
                "documentation": action.documentation,
                "aliases": list(action.aliases),
                "affordances": list(action.affordances),
                "resource_kinds": list(action.resource_kinds),
                "principals": sorted(action.principals),
                "effect": action.effect.value,
                "example": action.examples[0].input if action.examples else None,
                "input_schema": action.input_schema() if inp.include_schemas else None,
            }
        )
    fields = (
        "name",
        "family",
        "domain",
        "owner",
        "summary",
        "documentation",
        "aliases",
        "affordances",
        "resource_kinds",
    )
    selected = search_rows(rows, inp.query, fields)
    resources = action_set.resource_rows(runtime.principal_name)
    resources = search_rows(resources, inp.query, ("kind", "owner", "actions"))
    return selected, resources, action_set.catalog_hash(runtime.principal_name)


async def _catalog(runtime: Runtime, inp: CatalogInput) -> Catalog:
    from .. import actions as action_set

    selected, resources, catalog_sha256 = await anyio.to_thread.run_sync(
        _action_matches, runtime, inp
    )
    mcp_tools: list[dict[str, Any]] = []
    unavailable: list[str] = []
    incomplete: dict[str, str] = {}
    mcp_catalog_truncated = False
    catalog_artifact: dict[str, Any] | None = None
    if (
        inp.include_mcp_tools
        and (inp.query or "").strip()
        and Capability.MCP_READ in runtime.principal.capabilities
    ):
        try:
            broker = await runtime.mcp_broker.catalog(bounded=False)
        except Exception as exc:  # broker failures are catalog gaps, not errors
            unavailable.append(f"mcp: {type(exc).__name__}")
            broker = {"servers": []}
        mcp_catalog_truncated = bool(broker.get("truncated"))
        catalog_artifact = broker.get("catalog_artifact")
        for server in broker.get("servers", []):
            if server.get("availability") != "available":
                unavailable.append(f"mcp.{server.get('name')}")
                continue
            if server.get("coverage_complete") is False:
                incomplete[server["name"]] = (
                    server.get("reason") or "incomplete tools/list"
                )
            for tool in server.get("tools", []):
                mcp_tools.append(
                    {
                        "ref": tool.get("ref")
                        or f"sinnix://mcp/{server['name']}/tools/{tool.get('name')}",
                        "server": server["name"],
                        "name": tool.get("name", ""),
                        "description": tool.get("description"),
                        "effect": tool.get("effect"),
                        "invoke": (
                            "mcp.call"
                            if tool.get("effect", "read") == "read"
                            else "mcp.change"
                        ),
                    }
                )
        mcp_tools = search_rows(mcp_tools, inp.query, ("server", "name", "description"))
    total = len(selected) + len(resources) + len(mcp_tools)
    return Catalog(
        revision=action_set.REVISION,
        catalog_sha256=catalog_sha256,
        actions=[
            CatalogAction(**{k: v for k, v in row.items() if k != "documentation"})
            for row in selected[: inp.limit]
        ],
        resources=[CatalogResource(**row) for row in resources[: inp.limit]],
        mcp_tools=[CatalogMcpTool(**row) for row in mcp_tools[: inp.limit]],
        mcp_unavailable=unavailable,
        mcp_coverage_incomplete=incomplete,
        mcp_catalog_truncated=mcp_catalog_truncated,
        mcp_catalog_artifact=catalog_artifact,
        truncated=total > inp.limit or bool(incomplete),
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="gateway.describe",
        family=VerbFamily.GET,
        owner="gateway",
        summary="Describe one exact visible action and its structural schema hash.",
        Input=DescribeInput,
        Output=Description,
        handler=_describe,
        principals=ALL_PRINCIPALS,
        examples=(Example(title="Describe", input={"action": "files.read"}),),
    ),
    Action(
        name="gateway.read",
        family=VerbFamily.GET,
        owner="gateway",
        summary="Invoke one exact authorized read action with its native result.",
        Input=ReadInput,
        Output=Dispatched,
        handler=_dispatch_only,
        principals=ALL_PRINCIPALS,
        documentation="Pass the exact action name and its ordinary input in arguments. The response is the selected action's native envelope and content blocks.",
        examples=(
            Example(title="Read", input={"action": "projects.list", "arguments": {}}),
        ),
    ),
    Action(
        name="gateway.change",
        family=VerbFamily.CHANGE,
        owner="gateway",
        summary="Invoke one exact authorized change or operate action with its native receipt.",
        Input=EffectInput,
        Output=Dispatched,
        handler=_dispatch_only,
        principals=ALL_PRINCIPALS,
        documentation="Pass controls at the top level and ordinary action input in arguments. The response is the selected action's native envelope and receipt. Change and operate effects are admitted.",
        examples=(
            Example(
                title="Change",
                input={
                    "action": "files.change",
                    "arguments": {},
                    "idempotency_key": "example",
                },
            ),
        ),
    ),
    Action(
        name="gateway.run",
        family=VerbFamily.RUN,
        owner="gateway",
        summary="Invoke one exact authorized run action with its native receipt.",
        Input=EffectInput,
        Output=Dispatched,
        handler=_dispatch_only,
        principals=ALL_PRINCIPALS,
        documentation="Pass controls at the top level and ordinary action input in arguments. The response is the selected action's native envelope and receipt.",
        examples=(
            Example(
                title="Run",
                input={
                    "action": "operations.run",
                    "arguments": {},
                    "idempotency_key": "example",
                },
            ),
        ),
    ),
    Action(
        name="gateway.status",
        family=VerbFamily.STATUS,
        owner="gateway",
        summary="Report the principal, contract hashes, tool count and per-route availability.",
        Input=StatusInput,
        Output=GatewayStatus,
        handler=_status,
        principals=ALL_PRINCIPALS,
        affordances=("gateway.catalog",),
        aliases=("health", "ready", "capabilities", "what can you do"),
        examples=(Example(title="Status", input={}),),
    ),
    Action(
        name="gateway.catalog",
        family=VerbFamily.CATALOG,
        owner="gateway",
        summary="Find actions, resources and brokered MCP tools by plain words.",
        Input=CatalogInput,
        Output=Catalog,
        handler=_catalog,
        principals=ALL_PRINCIPALS,
        affordances=("gateway.status",),
        aliases=("search tools", "discover", "help", "list actions", "which tool"),
        documentation="Every action is also an MCP tool with its full schema in tools/list; the catalog adds aliases, affordances, resource kinds and the brokered MCP tool inventory (lynchpin, sinex, polylogue).",
        examples=(
            Example(title="Screenshot capability", input={"query": "screenshot"}),
            Example(title="Lynchpin tools", input={"query": "lynchpin"}),
        ),
    ),
)
