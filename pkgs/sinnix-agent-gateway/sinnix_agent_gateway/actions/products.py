"""Bounded presentations of analytical products supplied by their owners."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal, Mapping

import anyio
from pydantic import Field, model_validator

from ..action import Action, Example, RequestControls
from ..contracts import VerbFamily
from ..locators import ProjectLocator, project_ref
from ..mcp_broker import McpBrokerError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime


# Owner outcomes distinguish complete empty results from unavailable evidence.
Availability = Literal["available", "degraded", "empty", "unavailable"]

#: The owner outcome tokens that mean the owner produced no valid answer.
UNAVAILABLE_OUTCOMES = frozenset({"error", "not_found", "unavailable", "unsupported"})
#: Owner outcome token -> the availability the gateway reports for it. An
#: outcome the gateway does not know is not silently `available`: it falls to
#: the unavailability tests below and then to `available` only if none fire.
OUTCOME_AVAILABILITY: dict[str, Availability] = {
    "ok": "available",
    "success": "available",
    "degraded": "degraded",
    "partial": "degraded",
    "empty": "empty",
}


def _component_failures(data: Mapping[str, Any]) -> dict[str, str]:
    """Preserve named component gaps from the owner product or its result."""
    for holder in (data, data.get("result"), data.get("preamble")):
        if not isinstance(holder, Mapping):
            continue
        failures = holder.get("component_failures")
        if isinstance(failures, Mapping) and failures:
            return {str(key): str(value) for key, value in failures.items()}
    return {}


class OwnerProduct(GatewayModel):
    owner: str
    availability: Availability
    data: dict[str, Any] | None = None
    reason: str | None = None
    source_ref: str
    owner_metadata: dict[str, Any] | None = None
    # The owner's own per-component gap names, preserved verbatim. Empty when
    # the owner named none.
    component_failures: dict[str, str] = Field(default_factory=dict)


async def owner_product(
    runtime: Runtime,
    owner: str,
    tool: str,
    arguments: dict[str, Any],
    *,
    deadline_at: float | None = None,
) -> OwnerProduct:
    source_ref = f"sinnix://mcp/{owner}/tools/{tool}"
    try:
        response = await runtime.mcp_broker.owner_result(
            owner,
            tool,
            arguments,
            write=False,
            deadline_at=deadline_at,
        )
    except McpBrokerError as exc:
        return OwnerProduct(
            owner=owner,
            availability="unavailable",
            reason=str(exc),
            source_ref=source_ref,
        )
    if not isinstance(response, dict) or response.get("isError"):
        return OwnerProduct(
            owner=owner,
            availability="unavailable",
            reason="Owner returned an error.",
            source_ref=source_ref,
        )
    data = response.get("structuredContent")
    if (
        isinstance(data, dict)
        and set(data) == {"result"}
        and isinstance(data["result"], str)
    ):
        try:
            data = json.loads(data["result"])
        except ValueError:
            data = None
    if data is None:
        for item in response.get("content", []):
            if item.get("type") == "text":
                try:
                    data = json.loads(item["text"])
                except (ValueError, KeyError):
                    continue
                break
    if not isinstance(data, dict):
        return OwnerProduct(
            owner=owner,
            availability="unavailable",
            reason="Owner returned no structured analytical product.",
            source_ref=source_ref,
        )
    owner_metadata = None
    if data.get("ok") is True and isinstance(data.get("data"), dict):
        owner_metadata = data.get("meta")
        data = data["data"]
    outcome = data.get("outcome")
    outcome_reason: str | None = None
    if isinstance(data.get("result"), dict):
        outcome = data["result"].get("outcome", outcome)
    if isinstance(outcome, dict):
        reason = outcome.get("reason")
        outcome_reason = str(reason) if reason else None
        outcome = outcome.get("state")
    failures = _component_failures(data)
    if (
        outcome in UNAVAILABLE_OUTCOMES
        or data.get("ok") is False
        or data.get("status") == "error"
        or data.get("available") is False
        or data.get("availability") == "unavailable"
    ):
        return OwnerProduct(
            owner=owner,
            availability="unavailable",
            data=data,
            reason=str(
                data.get("reason")
                or data.get("message")
                or data.get("error")
                or outcome_reason
                or f"Owner outcome: {outcome}"
            ),
            source_ref=source_ref,
            owner_metadata=owner_metadata,
            component_failures=failures,
        )
    # An outcome the owner declared is carried through as the owner decided
    # it. The gateway never infers one from the shape of the payload: reading
    # `empty` off an absent row set is what makes a broken owner surface
    # indistinguishable from an owner whose scope really holds nothing.
    availability = OUTCOME_AVAILABILITY.get(str(outcome), "available")
    if failures and availability != "unavailable":
        # Named component failures are named gaps, whether or not this owner's
        # payload carries a terminal outcome at all -- and a gap outranks
        # `empty`, so a scope that found nothing behind a failed component is
        # reported as gap-shaped rather than as an authoritative nothing.
        availability = "degraded"
    reason = outcome_reason
    if availability == "degraded" and not reason and failures:
        reason = "; ".join(
            f"{name}: {detail}" for name, detail in sorted(failures.items())
        )
    return OwnerProduct(
        owner=owner,
        availability=availability,
        data=data,
        reason=reason,
        source_ref=source_ref,
        owner_metadata=owner_metadata,
        component_failures=failures,
    )


class HistoricalSelector(GatewayModel):
    revision: str | None = Field(default=None, min_length=1, max_length=512)
    timestamp: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def exactly_one(self) -> HistoricalSelector:
        if (self.revision is None) == (self.timestamp is None):
            raise ValueError("select exactly one revision or timestamp")
        return self

    def owner_value(self) -> str:
        return self.revision or self.timestamp or ""


class CampaignInput(RequestControls):
    project: ProjectLocator
    roots: list[str] = Field(min_length=1, max_length=100)
    relation: Literal["blocks", "parent-child"] = "blocks"
    direction: Literal["prerequisites", "dependents"] = "prerequisites"
    max_nodes: int = Field(default=500, ge=1, le=1000)
    max_depth: int = Field(default=50, ge=1, le=100)
    at: HistoricalSelector | None = None
    baseline: HistoricalSelector | None = None
    refresh_id: str | None = Field(default=None, min_length=1, max_length=512)


class CampaignResult(GatewayModel):
    projection_version: int = 2
    project: str
    product: OwnerProduct
    next_actions: list[str] = Field(
        default_factory=lambda: [
            "beads.get",
            "beads.query",
            "mcp.tools",
            "context.compose",
        ]
    )


async def _campaign(runtime: Runtime, inp: CampaignInput) -> CampaignResult:
    from .contexts import _resolve_project

    project = await anyio.to_thread.run_sync(_resolve_project, runtime, inp.project)
    from ..beads import BeadsError
    from ..contexts import source_revision
    from ..results import ProtocolError

    if inp.refresh_id is not None:
        raise ProtocolError(
            "unsupported_capability",
            "Native campaign evidence reads owners directly; refresh generations are unsupported",
        )
    components: dict[str, Any] = {}
    failures: dict[str, str] = {}
    for name, selector in (("tasks", inp.at), ("baseline", inp.baseline)):
        if name == "baseline" and selector is None:
            continue
        try:
            value = await anyio.to_thread.run_sync(
                lambda selector=selector: runtime.beads.campaign_closure(
                    project,
                    inp.roots,
                    at=selector.owner_value() if selector else None,
                    relation=inp.relation,
                    direction=inp.direction,
                    max_nodes=inp.max_nodes,
                    max_depth=inp.max_depth,
                )
            )
        except BeadsError as exc:
            components[name] = {"status": "unavailable", "reason": str(exc)}
            failures[name] = str(exc)
            continue
        owner = value["owner_product"]
        complete = (owner.get("closure") or {}).get("complete") is True
        components[name] = {
            "status": "available" if complete else "degraded",
            "source_ref": f"{project_ref(project)}/task-authority",
            "source_revision": owner.get("revision"),
            "coverage": {
                "complete": complete,
                "scope": "explicit roots and native closure",
            },
            "data": value,
        }
        if not complete:
            failures[name] = (
                "Native closure is incomplete; an exact campaign denominator is unknown"
            )
    # AgentCTL has a current bounded observation, not an as-of task-history API.
    if inp.at is not None or inp.baseline is not None:
        components["agentctl"] = {
            "status": "unavailable",
            "coverage": {"complete": False, "scope": "historical job evidence"},
            "reason": "AgentCTL does not supply an as-of job observation for task revisions",
        }
        failures["agentctl"] = components["agentctl"]["reason"]
    else:
        try:
            page = await anyio.to_thread.run_sync(
                lambda: runtime._job("job.list", {"project_id": project, "limit": 20})
            )
            components["agentctl"] = {
                "status": "degraded" if page.get("truncated") else "available",
                "source_ref": "sinnix://gateway/actions/jobs.list",
                "source_revision": source_revision(page),
                "revision_kind": "observation",
                "coverage": {
                    "complete": not bool(page.get("truncated")),
                    "scope": "current retained project jobs",
                },
                "data": page,
            }
            if page.get("truncated"):
                failures["agentctl"] = (
                    "Retained job page is bounded; follow the native cursor"
                )
        except (ProtocolError, OSError) as exc:
            components["agentctl"] = {"status": "unavailable", "reason": str(exc)}
            failures["agentctl"] = str(exc)
    data = {
        "schema": "sinnix.native-campaign.v1",
        "roots": inp.roots,
        "components": components,
        "delivery": {
            "state": "unknown",
            "reason": "Task closure and job success do not independently verify delivery",
        },
        "acceptance": {
            "state": "unknown",
            "reason": "No independent acceptance assessment is supplied by these owners",
        },
        "scope_delta": {
            "state": "unknown",
            "reason": "Native observations are retained separately; no historical completeness is inferred",
        },
    }
    product = OwnerProduct(
        owner="beads",
        availability=(
            "degraded"
            if any(c["status"] != "unavailable" for c in components.values())
            else "unavailable"
        ),
        data=data,
        source_ref=f"{project_ref(project)}/task-authority",
        reason="Closure and retained job evidence are observations; delivery and acceptance remain unknown",
        component_failures=failures,
    )
    return CampaignResult(project=project, product=product)


ACTIONS = (
    Action(
        name="campaign.progress",
        family=VerbFamily.QUERY,
        owner="beads",
        summary="Read explicit campaign closure and retained job evidence without inferring delivery or acceptance.",
        Input=CampaignInput,
        Output=CampaignResult,
        handler=_campaign,
        resource_kinds=("project", "bead"),
        next_actions=("beads.query", "beads.get", "context.compose"),
        documentation="Task closure, verified delivery and acceptance remain separate. Missing evidence is unknown; bounded closure cannot establish an exact denominator. Historical task state is read at its resolved owner revision.",
        examples=(
            Example(
                title="Campaign evidence",
                input={"project": {"project": "sinnix"}, "roots": ["sinnix-1"]},
            ),
        ),
    ),
)
