"""The gateway's own surface: status and the one catalog search."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..action import ALL_PRINCIPALS, Action, Example, RequestControls
from ..capabilities import Capability
from ..catalog import search_rows
from ..contracts import VerbFamily
from ..schemas import GatewayModel

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
    catalog_hash = action_set.catalog_hash(runtime.principal_name)
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
    truncated: bool = False


async def _catalog(runtime: Runtime, inp: CatalogInput) -> Catalog:
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
    mcp_tools: list[dict[str, Any]] = []
    unavailable: list[str] = []
    if inp.include_mcp_tools and Capability.MCP_READ in runtime.principal.capabilities:
        try:
            broker = await runtime.mcp_broker.catalog()
        except Exception as exc:  # broker failures are catalog gaps, not errors
            unavailable.append(f"mcp: {type(exc).__name__}")
            broker = {"servers": []}
        for server in broker.get("servers", []):
            if server.get("availability") != "available":
                unavailable.append(f"mcp.{server.get('name')}")
                continue
            for tool in server.get("tools", []):
                mcp_tools.append(
                    {
                        "ref": tool.get("ref")
                        or f"sinnix://mcp/{server['name']}/tools/{tool.get('name')}",
                        "server": server["name"],
                        "name": tool.get("name", ""),
                        "description": tool.get("description"),
                        "effect": tool.get("effect"),
                        "invoke": "mcp.call"
                        if tool.get("effect", "read") == "read"
                        else "mcp.change",
                    }
                )
        mcp_tools = search_rows(mcp_tools, inp.query, ("server", "name", "description"))
        if inp.query is None:
            mcp_tools = []
    total = len(selected) + len(resources) + len(mcp_tools)
    return Catalog(
        revision=action_set.REVISION,
        catalog_sha256=action_set.catalog_hash(runtime.principal_name),
        actions=[
            CatalogAction(**{k: v for k, v in row.items() if k != "documentation"})
            for row in selected[: inp.limit]
        ],
        resources=[CatalogResource(**row) for row in resources[: inp.limit]],
        mcp_tools=[CatalogMcpTool(**row) for row in mcp_tools[: inp.limit]],
        mcp_unavailable=unavailable,
        truncated=total > inp.limit,
    )


ACTIONS: tuple[Action, ...] = (
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
