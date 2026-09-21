"""Bounded presentations of analytical products supplied by their owners."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal, Mapping, Sequence

from pydantic import Field, model_validator

from ..action import OBSERVER_OPERATOR, Action, Example, RequestControls
from ..capabilities import Capability, PolicyError
from ..contracts import VerbFamily
from ..generated_lynchpin_inputs import CampaignInput as OwnerCampaignInput
from ..locators import ProjectLocator
from ..mcp_broker import McpBrokerError
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime


#: What the gateway can say about one owner's product. The four states are
#: the owner's own terminal-outcome vocabulary, not a gateway invention:
#: Polylogue decides {ok, empty, degraded, error} once at its operation
#: boundary, and `degraded` deliberately outranks `empty` so that zero rows
#: behind a named gap is never reported as an empty scope. Collapsing the
#: middle two into `available` here erases exactly the distinction that
#: contract exists to preserve -- it manufactures an authoritative "nothing
#: to report" out of an answer the owner said was gap-shaped.
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
#: Worst-first, for composing several products into one.
_AVAILABILITY_RANK = ("unavailable", "degraded", "empty", "available")


def combine_availability(parts: Sequence[Availability]) -> Availability:
    """The availability of an envelope that holds several owner products.

    This mirrors the owners' own rule rather than inventing a second one: a
    composite is only as honest as its worst part, so one part behind a named
    gap makes the whole answer `degraded` even though the others carried real
    data. `empty` survives only when every part completed over its scope and
    found nothing, and `unavailable` only when nothing could answer at all.
    """
    states = set(parts)
    if not states:
        return "empty"
    if states == {"unavailable"}:
        return "unavailable"
    if states & {"unavailable", "degraded"}:
        return "degraded"
    if states == {"empty"}:
        return "empty"
    return "available"


def _component_failures(data: Mapping[str, Any]) -> dict[str, str]:
    """The owner's per-component gap names, from the product or its result.

    An owner that reports no terminal outcome can still name which of its
    components failed (Polylogue's ContextPreamble carries
    ``component_failures`` and no outcome field at all). Those names are the
    only gap signal such a payload has, and dropping them is how a context
    answer assembled from a failed lineage lookup reached a caller labelled
    "ok + available".
    """
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
    except PolicyError:
        raise
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
                "query",
                {
                    "projection": "session-operations",
                    "session_operation": {
                        "operation": "sessions.orchestration",
                        "ref": reference,
                    },
                },
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


class CampaignInput(RequestControls, OwnerCampaignInput):
    project: ProjectLocator
    at: HistoricalSelector | None = None
    baseline: HistoricalSelector | None = None


class CampaignResult(GatewayModel):
    projection_version: int = 2
    project: str
    product: OwnerProduct
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
    runtime.principal.require(Capability.TASK_READ)
    product = await owner_product(
        runtime,
        "lynchpin",
        "lynchpin_project",
        {
            "action": "campaign_progress",
            "project": project,
            "roots": inp.roots,
            "at": inp.at.owner_value() if inp.at else None,
            "baseline": inp.baseline.owner_value() if inp.baseline else None,
            "relation": inp.relation,
            "direction": inp.direction,
            "max_nodes": inp.max_nodes,
            "max_depth": inp.max_depth,
            **({"refresh_id": inp.refresh_id} if inp.refresh_id else {}),
        },
        deadline_at=inp.deadline_at,
    )
    return CampaignResult(project=project, product=product)


ACTIONS = (
    Action(
        name="campaign.progress",
        family=VerbFamily.QUERY,
        owner="lynchpin",
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
        resource_kinds=(),
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
