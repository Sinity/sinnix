"""Composed, budgeted context for one intent: orientation, triage, job review, incident."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Mapping

import anyio
from pydantic import Field, TypeAdapter, model_validator

from ..action import Action, Example, RequestControls
from ..contracts import VerbFamily
from ..locators import JobLocator, ProjectLocator, project_ref
from ..payloads import canonical_size
from ..results import ProtocolError
from ..schemas import GatewayModel
from .products import Availability, HistoricalSelector, combine_availability

if TYPE_CHECKING:
    from ..runtime import Runtime

Intent = Literal[
    "project.overview",
    "project.triage",
    "job.review",
    "incident",
    "campaign.progress",
    "session.orchestration",
    "verification.regression",
    "project.trajectory",
]


class ComposeInput(RequestControls):
    intent: Intent
    project: ProjectLocator | None = Field(
        default=None,
        description="Required for project.overview, project.triage and incident.",
    )
    job: JobLocator | None = Field(default=None, description="Required for job.review.")
    roots: list[str] = Field(default_factory=list, max_length=100)
    session_refs: list[str] = Field(default_factory=list, max_length=20)
    at: HistoricalSelector | None = None
    baseline: HistoricalSelector | None = None
    refresh_id: str | None = None

    @model_validator(mode="after")
    def target_matches_intent(self) -> ComposeInput:
        wants_job = self.intent == "job.review"
        if wants_job and (self.job is None or self.project is not None):
            raise ValueError("job.review takes job and no project")
        if not wants_job and (self.project is None or self.job is not None):
            raise ValueError(f"{self.intent} takes project and no job")
        if self.intent == "campaign.progress" and not self.roots:
            raise ValueError("campaign.progress requires explicit roots")
        if self.intent == "session.orchestration" and not self.session_refs:
            raise ValueError("session.orchestration requires session_refs")
        return self


class ContextComponent(GatewayModel):
    name: str
    # The owner's terminal state, not a two-way reachability flag: see
    # `products.Availability`.
    status: Availability
    source_revision: str | None = None
    snapshot_ref: str
    source_ref: str | None = None
    data: Any = None
    reason: str | None = None
    # The owner's own per-component gap names, preserved verbatim.
    component_failures: dict[str, str] = Field(default_factory=dict)
    # Set when this component's data did not fit `total_budget_bytes` and was
    # left in the snapshot instead; `snapshot_ref` reads the complete value.
    inline_omitted: bool = False
    presentation: Literal["full", "compact", "unavailable"] = "full"
    full_product_pointer: str | None = Field(
        default=None,
        description="JSON pointer in snapshot_ref to the complete owner product; compact owner pointers are relative to it.",
    )


class ComposedContext(GatewayModel):
    ref: str = Field(description="Canonical ref of the composed target.")
    intent: str
    target_ref: str
    snapshot_ref: str = Field(
        description="sinnix://results/<id>; readable through results.get or MCP resources."
    )
    context_schema: str | None = None
    components: list[ContextComponent]
    component_plan: list[dict[str, Any]] = Field(default_factory=list)
    total_budget_bytes: int
    availability: Availability = "available"
    next_actions: list[str] = Field(default_factory=list)


_NEXT_ACTIONS: dict[str, list[str]] = {
    "campaign.progress": ["campaign.progress", "beads.get"],
    "session.orchestration": ["sessions.orchestration", "sessions.query"],
    "verification.regression": ["campaign.progress", "jobs.get"],
    "project.trajectory": ["campaign.progress", "sessions.query"],
    "project.overview": ["batches.start", "jobs.list", "events.tail"],
    "project.triage": ["batches.start", "jobs.list", "events.tail"],
    "job.review": ["jobs.logs", "jobs.retry", "jobs.cancel"],
    "incident": ["events.tail", "jobs.list", "wait.for"],
}


def _resolve_project(runtime: Runtime, locator: Any) -> str:
    project = locator.resolve(runtime)
    runtime.projects._project(project)
    return project


async def _compose(runtime: Runtime, inp: ComposeInput) -> ComposedContext:
    from ..contexts import source_revision
    from .products import (
        CampaignInput,
        OrchestrationInput,
        OwnerProduct,
        _campaign,
        _orchestration,
        owner_product,
    )

    if inp.job is not None:
        task_id, ref, job_id = inp.job.resolve()
        identity = {"task_id": task_id, "max_bytes": 64000}
        if job_id is not None:
            identity["job_id"] = job_id
        try:
            value = await anyio.to_thread.run_sync(runtime._job, "job.result", identity)
        except ProtocolError as exc:
            if exc.code not in {"owner_failed", "unavailable", "deadline"}:
                raise
            product = OwnerProduct(
                owner="agentctl",
                availability="unavailable",
                reason=str(exc),
                source_ref=ref,
            )
        else:
            key = "job_id" if job_id is not None else "task_id"
            if str(value.get(key)) != str(identity[key]):
                raise ProtocolError(
                    "owner_failed", "job owner response names another job"
                )
            ref = f"sinnix://jobs/{value['task_id']}"
            product = OwnerProduct(
                owner="agentctl", availability="available", data=value, source_ref=ref
            )

    else:
        assert inp.project is not None
        project = await anyio.to_thread.run_sync(_resolve_project, runtime, inp.project)
        ref = project_ref(project)
    if inp.intent == "job.review":
        pass
    elif inp.intent == "campaign.progress":
        product = (
            await _campaign(
                runtime,
                CampaignInput(
                    project=inp.project,
                    roots=inp.roots,
                    at=inp.at,
                    baseline=inp.baseline,
                    refresh_id=inp.refresh_id,
                    deadline_at=inp.deadline_at,
                ),
            )
        ).product
    elif inp.intent == "session.orchestration":
        value = await _orchestration(
            runtime,
            OrchestrationInput(
                session_refs=inp.session_refs,
                deadline_at=inp.deadline_at,
            ),
        )
        # The composite keeps its parts' worst state instead of asking only
        # whether any part was available: one session behind a named gap makes
        # the whole orchestration answer gap-shaped, and every part reporting
        # an empty scope is an empty answer, not an available one.
        availability = combine_availability(
            [item.availability for item in value.sessions]
        )
        product = OwnerProduct(
            owner="polylogue",
            availability=availability,
            reason=next(
                (
                    item.reason
                    for item in value.sessions
                    if item.availability != "available" and item.reason
                ),
                "Requested session products are unavailable"
                if availability == "unavailable"
                else None,
            ),
            data=value.model_dump(),
            source_ref="sinnix://mcp/polylogue",
            component_failures={
                name: detail
                for item in value.sessions
                for name, detail in item.component_failures.items()
            },
        )
    elif inp.intent == "incident":
        value = await anyio.to_thread.run_sync(
            runtime.observe.machine_query, "overview"
        )
        product = OwnerProduct(
            owner="sinnix-observe",
            availability="unavailable"
            if value.get("available") is False
            else "available",
            data=value,
            reason=value.get("reason"),
            source_ref="sinnix://machine/overview",
        )
    else:
        product = await owner_product(
            runtime,
            "lynchpin",
            "lynchpin_project",
            {
                "action": "project_context",
                "project": project,
                "intent": inp.intent,
                "roots": inp.roots,
                "at": inp.at.owner_value() if inp.at else None,
                "budget_bytes": min(
                    56000, max(8192, runtime.config.max_result_bytes - 8192)
                ),
                **({"refresh_id": inp.refresh_id} if inp.refresh_id else {}),
            },
            deadline_at=inp.deadline_at,
        )
    # Persistence identifies this observation. Domain components, ordering,
    # coverage and the owner's terminal state remain exactly as the owner
    # returned them; the snapshot holds the complete product whatever its
    # size, and `_within_budget` bounds only the copy returned in band.
    observed_product = product.model_dump()
    context = await anyio.to_thread.run_sync(
        runtime.persist_context,
        {
            "schema": "sinnix.owner-context.v2",
            "ref": ref,
            "target_ref": ref,
            "intent": inp.intent,
            "total_budget_bytes": runtime.config.max_result_bytes,
            "component_plan": [],
            "components": [
                {
                    "name": product.owner,
                    "status": product.availability,
                    "source_revision": source_revision(observed_product),
                    "source_ref": product.source_ref,
                    "data": observed_product,
                    "reason": product.reason,
                    "component_failures": dict(product.component_failures),
                }
            ],
        },
    )
    # Leave room for the standard result envelope and include model defaults
    # before measuring the presentation, rather than adding them afterwards.
    context["context_schema"] = context["schema"]
    context["next_actions"] = _NEXT_ACTIONS[inp.intent]
    context["availability"] = product.availability
    bounded = _within_budget(context)
    return ComposedContext(
        **{
            key: value
            for key, value in bounded.items()
            if key in ComposedContext.model_fields
        },
    )


def _native_json(value: Any, active: set[int] | None = None) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if not isinstance(value, (dict, list, tuple)):
        return False
    active = set() if active is None else active
    identity = id(value)
    if identity in active:
        return False
    active.add(identity)
    try:
        if isinstance(value, dict):
            return all(
                (key is None or isinstance(key, (str, int, float, bool)))
                and _native_json(child, active)
                for key, child in value.items()
            )
        return all(_native_json(child, active) for child in value)
    finally:
        active.remove(identity)


_COMPONENT_DATA = TypeAdapter(Any)


def _presentation_size(context: Mapping[str, Any]) -> int:
    fields = {
        key: item
        for key, item in context.items()
        if key in ComposedContext.model_fields
    }
    model = ComposedContext.model_validate(fields)
    # Include typed defaults while keeping native owner data shared. Non-JSON
    # values still follow Pydantic's Any serialization, as in the full dump.
    serialized = model.model_dump(exclude={"components": {"__all__": {"data"}}})
    for row, component in zip(serialized["components"], model.components, strict=True):
        data = component.data
        row["data"] = data if _native_json(data) else _COMPONENT_DATA.dump_python(data)
    return canonical_size(serialized, default=str)


def _within_budget(
    context: Mapping[str, Any], *, reserve_bytes: int = 0
) -> dict[str, Any]:
    """Use the owner's compact view when full data exceeds the payload bound.

    The immutable snapshot always retains the original. Unsupported or unusable
    presentations are explicitly unavailable, independently of transport success.
    """
    budget = int(context["total_budget_bytes"])
    budget -= min(4096, max(1, budget // 2)) + reserve_bytes

    size = _presentation_size

    if size(context) <= budget:
        return dict(context)
    bounded = dict(context)
    components = []
    for index, component in enumerate(context["components"]):
        entry = dict(component)
        product = entry.get("data")
        data = product.get("data") if isinstance(product, dict) else None
        projection = data.get("presentation") if isinstance(data, dict) else None
        if (
            entry["name"] == "lynchpin"
            and isinstance(projection, dict)
            and projection.get("product") == "project_context_compact"
            and projection.get("outcome") in {"ok", "partial"}
            and projection.get("components")
        ):
            entry["data"] = {**product, "data": projection, "owner_metadata": None}
            entry["presentation"] = "compact"
            entry["full_product_pointer"] = f"/components/{index}/data/data"
            entry["reason"] = (
                "Owner-selected compact view; full observation is in snapshot_ref"
            )
        components.append(entry)
    bounded["components"] = components
    if size(bounded) <= budget:
        return bounded
    components = []
    for component in context["components"]:
        entry = dict(component)
        entry["data"] = None
        entry["inline_omitted"] = True
        entry["presentation"] = "unavailable"
        entry["status"] = "unavailable"
        entry["component_failures"] = {}
        entry["reason"] = (
            entry.get("reason")
            or f"inline data omitted: over the {budget}-byte context budget"
        )
        components.append(entry)
    bounded["components"] = components
    bounded["availability"] = "unavailable"
    if size(bounded) > budget:
        # Even metadata can exceed one frame. Let the common result transport
        # retain the complete original and return its resumable artifact ref.
        return dict(context)
    return bounded


ACTIONS: tuple[Action, ...] = (
    Action(
        name="context.compose",
        family=VerbFamily.CONTEXT,
        owner="context",
        summary="Compose bounded project, job, incident, campaign, orchestration, regression or trajectory evidence from its owners.",
        Input=ComposeInput,
        Output=ComposedContext,
        handler=_compose,
        resource_kinds=("project", "checkout", "job", "context_snapshot"),
        next_actions=(
            "jobs.list",
            "jobs.logs",
            "batches.start",
            "events.tail",
            "wait.for",
        ),
        aliases=(
            "orient",
            "overview",
            "situation",
            "what is going on",
            "triage",
            "review job",
            "incident",
        ),
        documentation="The owner supplies domain composition and a compact presentation when full data exceeds the inline budget. snapshot_ref retains the exact observation. availability and component presentation report usability independently of transport success; omitted data is unavailable.",
        examples=(
            Example(
                title="Orient in sinnix",
                input={
                    "intent": "project.overview",
                    "project": {"project": "sinnix"},
                },
            ),
            Example(
                title="Review a job",
                input={"intent": "job.review", "job": {"task_id": 41}},
            ),
            Example(
                title="Incident overview",
                input={"intent": "incident", "project": {"project": "sinnix"}},
            ),
        ),
    ),
)
