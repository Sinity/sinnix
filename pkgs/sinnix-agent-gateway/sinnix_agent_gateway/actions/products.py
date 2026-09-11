"""Bounded presentations of analytical products supplied by their owners."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal

import anyio
from pydantic import Field, model_validator

from ..action import OBSERVER_OPERATOR, Action, Example, RequestControls
from ..capabilities import Capability, PolicyError
from ..contracts import VerbFamily
from ..locators import ProjectLocator, bead_ref
from ..mcp_broker import McpBrokerError
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime


class OwnerProduct(GatewayModel):
    owner: str
    availability: Literal["available", "unavailable"]
    data: dict[str, Any] | None = None
    reason: str | None = None
    source_ref: str
    owner_metadata: dict[str, Any] | None = None


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
        result = await runtime.mcp_broker.call(
            owner,
            tool,
            arguments,
            write=False,
            deadline_at=deadline_at,
        )
    except PolicyError:
        raise
    except McpBrokerError as exc:
        return OwnerProduct(
            owner=owner,
            availability="unavailable",
            reason=str(exc),
            source_ref=source_ref,
        )
    response = result.get("response")
    if not isinstance(response, dict) or response.get("isError"):
        return OwnerProduct(
            owner=owner,
            availability="unavailable",
            reason="Owner returned an error or an artifact beyond the inline bound.",
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
    if isinstance(data.get("result"), dict):
        outcome = data["result"].get("outcome", outcome)
    if isinstance(outcome, dict):
        outcome = outcome.get("state")
    if (
        outcome in {"error", "not_found", "unavailable", "unsupported"}
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
                or f"Owner outcome: {outcome}"
            ),
            source_ref=source_ref,
            owner_metadata=owner_metadata,
        )
    return OwnerProduct(
        owner=owner,
        availability="available",
        data=data,
        source_ref=source_ref,
        owner_metadata=owner_metadata,
    )


class OrchestrationInput(RequestControls):
    session_refs: list[str] = Field(min_length=1, max_length=20)


class OrchestrationResult(GatewayModel):
    projection_version: int = 1
    sessions: list[OwnerProduct]
    affordances: list[str] = Field(
        default_factory=lambda: ["sessions.query", "context.compose"]
    )


async def _orchestration(
    runtime: Runtime, inp: OrchestrationInput
) -> OrchestrationResult:
    runtime.principal.require(Capability.SESSION_READ)
    sessions = []
    for reference in dict.fromkeys(inp.session_refs):
        if not reference.startswith("session:") or len(reference) > 8192:
            raise ProtocolError(
                "invalid_request",
                "session_refs must contain canonical Polylogue session: references",
            )
        sessions.append(
            await owner_product(
                runtime,
                "polylogue",
                "get",
                {"ref": reference, "projection": "orchestration"},
                deadline_at=inp.deadline_at,
            )
        )
    return OrchestrationResult(sessions=sessions)


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
    at: HistoricalSelector | None = None
    baseline: HistoricalSelector | None = None
    relation: Literal["blocks", "parent-child"] = "blocks"
    direction: Literal["prerequisites", "dependents"] = "prerequisites"
    max_nodes: int = Field(default=500, ge=1, le=1000)
    max_depth: int = Field(default=50, ge=1, le=100)
    refresh_id: str | None = None


class CampaignResult(GatewayModel):
    projection_version: int = 1
    project: str
    closure: dict[str, Any]
    baseline: dict[str, Any] | None = None
    scope_delta: dict[str, Any] | None = None
    scope_accounting: OwnerProduct | None = None
    evidence: OwnerProduct
    affordances: list[str] = Field(
        default_factory=lambda: [
            "beads.get",
            "beads.query",
            "sessions.orchestration",
            "context.compose",
        ]
    )


async def _campaign(runtime: Runtime, inp: CampaignInput) -> CampaignResult:
    project = inp.project.resolve(runtime)
    runtime.projects._project(project)
    closure_reader = getattr(runtime.beads, "campaign_closure", None)
    if closure_reader is None:
        raise ProtocolError(
            "unavailable", "Beads owner has no campaign closure capability"
        )

    def read(at: HistoricalSelector | None) -> dict[str, Any]:
        return closure_reader(
            project_id=project,
            roots=inp.roots,
            at=at.owner_value() if at else None,
            relation=inp.relation,
            direction=inp.direction,
            max_nodes=inp.max_nodes,
            max_depth=inp.max_depth,
        )

    closure = await anyio.to_thread.run_sync(lambda: read(inp.at))
    baseline = (
        await anyio.to_thread.run_sync(lambda: read(inp.baseline))
        if inp.baseline is not None
        else None
    )
    delta = None
    if baseline is not None:
        before = {str(row["id"]): row for row in baseline.get("nodes", [])}
        after = {str(row["id"]): row for row in closure.get("nodes", [])}
        retained = sorted(before.keys() & after.keys())
        delta = {
            "added": sorted(after.keys() - before.keys()),
            "removed": sorted(before.keys() - after.keys()),
            "retained": retained,
            "closed": [
                key
                for key in retained
                if before[key].get("status") != "closed"
                and after[key].get("status") == "closed"
            ],
            "reopened": [
                key
                for key in retained
                if before[key].get("status") == "closed"
                and after[key].get("status") != "closed"
            ],
            "complete": baseline.get("complete") is True
            and closure.get("complete") is True,
        }
    references = [
        row.get("ref") or bead_ref(project, str(row["id"]))
        for row in closure.get("nodes", [])
    ]
    evidence = await owner_product(
        runtime,
        "lynchpin",
        "lynchpin_project",
        {
            "action": "campaign_evidence",
            "project": project,
            "bead_refs": references,
            "task_snapshot": closure,
            **({"refresh_id": inp.refresh_id} if inp.refresh_id else {}),
        },
        deadline_at=inp.deadline_at,
    )
    accounting = (
        await owner_product(
            runtime,
            "lynchpin",
            "lynchpin_project",
            {
                "action": "campaign_scope_delta",
                "project": project,
                "task_snapshot": closure,
                "baseline_snapshot": baseline,
                **({"refresh_id": inp.refresh_id} if inp.refresh_id else {}),
            },
            deadline_at=inp.deadline_at,
        )
        if baseline is not None
        else None
    )
    return CampaignResult(
        project=project,
        closure=closure,
        baseline=baseline,
        scope_delta=delta,
        scope_accounting=accounting,
        evidence=evidence,
    )


ACTIONS = (
    Action(
        name="campaign.progress",
        family=VerbFamily.QUERY,
        owner="beads+lynchpin",
        summary="Compare explicit campaign closure and historical scope with owner-backed delivery and acceptance evidence.",
        Input=CampaignInput,
        Output=CampaignResult,
        handler=_campaign,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("project", "bead"),
        affordances=("beads.query", "beads.get", "context.compose"),
        documentation="Task closure, verified delivery and acceptance remain separate. Missing evidence is unknown; bounded closure cannot establish an exact denominator. Historical task state is read at its resolved owner revision.",
        examples=(
            Example(
                title="Campaign evidence",
                input={"project": {"project": "sinnix"}, "roots": ["sinnix-1"]},
            ),
        ),
    ),
    Action(
        name="sessions.orchestration",
        family=VerbFamily.QUERY,
        owner="polylogue",
        summary="Read structured session topology, launches, observed model segments and usage from Polylogue.",
        Input=OrchestrationInput,
        Output=OrchestrationResult,
        handler=_orchestration,
        principals=OBSERVER_OPERATOR,
        resource_kinds=("session",),
        affordances=("sessions.query", "context.compose"),
        documentation="Native parent, model and token fields remain unknown when absent from stored evidence. Each owner product retains its coverage, provenance and ingestion watermark.",
        examples=(
            Example(
                title="Session orchestration",
                input={"session_refs": ["session:example"]},
            ),
        ),
    ),
)
