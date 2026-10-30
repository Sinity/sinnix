"""Composed, budgeted context for one intent: orientation, triage, job review, incident."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal, Mapping

import anyio
from pydantic import Field, TypeAdapter, model_validator

from ..action import Action, Example, RequestControls
from ..contracts import VerbFamily
from ..locators import JobLocator, ProjectLocator, project_ref
from ..payloads import canonical_size
from ..results import ProtocolError
from ..schemas import GatewayModel
from .products import Availability, HistoricalSelector

if TYPE_CHECKING:
    from ..runtime import Runtime

Intent = Literal[
    "project.overview",
    "project.triage",
    "job.review",
    "incident",
    "campaign.progress",
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
    at: HistoricalSelector | None = None
    baseline: HistoricalSelector | None = None
    refresh_id: str | None = None
    evidence: list[Literal["sinex", "polylogue"]] = Field(
        default_factory=list,
        max_length=2,
        description="Optional live product status reads for project overview or triage.",
    )

    @model_validator(mode="after")
    def target_matches_intent(self) -> ComposeInput:
        wants_job = self.intent == "job.review"
        if wants_job and (self.job is None or self.project is not None):
            raise ValueError("job.review takes job and no project")
        if not wants_job and (self.project is None or self.job is not None):
            raise ValueError(f"{self.intent} takes project and no job")
        if self.intent == "campaign.progress" and not self.roots:
            raise ValueError("campaign.progress requires explicit roots")
        if self.evidence and self.intent not in {"project.overview", "project.triage"}:
            raise ValueError(
                "optional evidence takes a live project overview or triage"
            )
        return self


class ContextComponent(GatewayModel):
    name: str
    # The owner's terminal state, not a two-way reachability flag: see
    # `products.Availability`.
    status: Availability
    source_revision: str | None = None
    revision_kind: Literal["owner", "observation"] = "owner"
    coverage: dict[str, Any] = Field(default_factory=dict)
    required: bool = True
    observed_at: str | None = None
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
    "verification.regression": ["campaign.progress", "jobs.get"],
    "project.trajectory": ["campaign.progress", "mcp.tools"],
    "project.overview": ["operations.run", "jobs.list", "events.tail"],
    "project.triage": ["operations.run", "jobs.list", "events.tail"],
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
        OwnerProduct,
        _campaign,
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
    if inp.intent in {"project.overview", "project.triage"} or (
        inp.intent in {"verification.regression", "project.trajectory"}
        and not inp.roots
    ):
        return await _native_project_context(runtime, inp, project, ref)
    if inp.intent == "job.review":
        pass
    elif inp.intent in {
        "campaign.progress",
        "verification.regression",
        "project.trajectory",
    }:
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
    elif inp.intent == "incident":
        value = await anyio.to_thread.run_sync(
            runtime.observe.machine_query, "overview"
        )
        product = OwnerProduct(
            owner="sinnix-observe",
            availability=(
                "unavailable" if value.get("available") is False else "available"
            ),
            data=value,
            reason=value.get("reason"),
            source_ref="sinnix://machine/overview",
        )
    # Persistence identifies this observation. Domain components, ordering,
    # coverage and the owner's terminal state remain exactly as the owner
    # returned them; the snapshot holds the complete product whatever its
    # size, and `_within_budget` bounds only the copy returned in band.
    observed_product = product.model_dump()
    return await _finish_context(
        runtime,
        inp,
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
                    "revision_kind": "observation",
                    "source_ref": product.source_ref,
                    "data": observed_product,
                    "reason": product.reason,
                    "component_failures": dict(product.component_failures),
                }
            ],
        },
        product.availability,
    )


async def _finish_context(
    runtime: Runtime,
    inp: ComposeInput,
    value: dict[str, Any],
    availability: Availability,
) -> ComposedContext:
    value = {
        **value,
        "availability": availability,
        "next_actions": _NEXT_ACTIONS[inp.intent],
    }
    # Persist the same explicit unknown/default metadata the typed client sees,
    # while sharing potentially large owner data until the snapshot is written.
    components = []
    for row in value["components"]:
        component = ContextComponent.model_validate({"snapshot_ref": "pending", **row})
        components.append(
            {**component.model_dump(exclude={"data"}), "data": component.data}
        )
    value = {**value, "components": components}
    context = await anyio.to_thread.run_sync(runtime.persist_context, value)
    # Leave room for the standard result envelope and include model defaults
    # before measuring the presentation, rather than adding them afterwards.
    context["context_schema"] = context["schema"]
    context["next_actions"] = _NEXT_ACTIONS[inp.intent]
    context["availability"] = availability
    bounded = _within_budget(context)
    return ComposedContext(
        **{
            key: value
            for key, value in bounded.items()
            if key in ComposedContext.model_fields
        },
    )


async def _native_project_context(
    runtime: Runtime, inp: ComposeInput, project: str, ref: str
) -> ComposedContext:
    from ..beads import BeadsError
    from ..contexts import source_revision
    from ..projects import ProjectError
    from .products import owner_product

    if inp.at is not None or inp.baseline is not None or inp.refresh_id is not None:
        raise ProtocolError(
            "unsupported_capability",
            "Native project orientation observes current owners; historical selectors require an owner historical product",
        )
    components: dict[str, dict[str, Any]] = {}

    async def observe(name: str, source_ref: str, fn: Any) -> None:
        try:
            data = await anyio.to_thread.run_sync(fn)
            revision = data.get("revision")
            if name == "git":
                revision = source_revision(data)
            elif name == "agentctl":
                revision = (data.get("snapshot") or {}).get("source_revision")
            components[name] = {
                "name": name,
                "status": "degraded" if data.get("truncated") else "available",
                "data": data,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "source_ref": source_ref,
                "source_revision": revision or source_revision(data),
                "revision_kind": (
                    "owner" if revision and name != "git" else "observation"
                ),
                "coverage": {
                    "complete": not bool(data.get("truncated")),
                    "scope": "current project",
                },
            }
        except (BeadsError, ProjectError, ProtocolError, OSError) as exc:
            components[name] = {
                "name": name,
                "status": "unavailable",
                "source_ref": source_ref,
                "reason": str(exc),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "coverage": {"complete": False},
            }

    async with anyio.create_task_group() as group:
        group.start_soon(observe, "git", ref, lambda: runtime.projects.summary(project))
        group.start_soon(
            observe,
            "beads",
            f"{ref}/task-authority",
            lambda: runtime.beads.task_authority_status(project),
        )
        group.start_soon(
            observe,
            "agentctl",
            "sinnix://gateway/actions/jobs.list",
            lambda: runtime._job("job.list", {"project_id": project, "limit": 20}),
        )
    for name, tool in (("sinex", "sinex_status"), ("polylogue", "status")):
        requested = name in inp.evidence
        component: dict[str, Any] = {
            "name": name,
            "status": "unavailable",
            "required": False,
            "source_ref": f"sinnix://mcp/{name}/tools/{tool}",
            "coverage": {
                "requested": requested,
                "scope": "global product status; project attribution unknown",
            },
            "reason": "Optional product evidence was not requested",
        }
        if requested:
            product = await owner_product(
                runtime, name, tool, {}, deadline_at=inp.deadline_at
            )
            component.update(
                observed_at=datetime.now(timezone.utc).isoformat(),
                status=product.availability,
                data=product.model_dump(),
                reason=product.reason,
                component_failures=product.component_failures,
            )
            if product.data is not None:
                position = product.data.get("commit_seq") if name == "sinex" else None
                component.update(
                    source_revision=(
                        str(position)
                        if position is not None
                        else source_revision(product.data)
                    ),
                    revision_kind="owner" if position is not None else "observation",
                )
        components[name] = component
    ordered = [
        components[name] for name in ("git", "beads", "agentctl", "sinex", "polylogue")
    ]
    if inp.intent in {"verification.regression", "project.trajectory"}:
        ordered.append(
            {
                "name": "acceptance",
                "status": "unavailable",
                "required": True,
                "coverage": {
                    "complete": False,
                    "scope": "independent delivery, acceptance and regression assessment",
                },
                "reason": "Current Git, task status and retained job receipts do not establish delivery, acceptance, historical trajectory or regression",
            }
        )
    required = ordered[:3]
    failures = [
        c
        for c in ordered
        if c["status"] in {"unavailable", "degraded"}
        and (c.get("required", True) or c["coverage"].get("requested"))
    ]
    availability: Availability = (
        "available"
        if not failures
        else (
            "degraded"
            if any(c["status"] == "available" for c in required)
            else "unavailable"
        )
    )
    return await _finish_context(
        runtime,
        inp,
        {
            "schema": "sinnix.native-project-context.v1",
            "ref": ref,
            "target_ref": ref,
            "intent": inp.intent,
            "total_budget_bytes": runtime.config.max_result_bytes,
            "component_plan": [
                {"name": c["name"], "required": c.get("required", True)}
                for c in ordered
            ],
            "components": ordered,
        },
        availability,
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
    """Bound inline component data while retaining the complete immutable snapshot."""
    budget = int(context["total_budget_bytes"])
    budget -= min(4096, max(1, budget // 2)) + reserve_bytes

    size = _presentation_size

    if size(context) <= budget:
        return dict(context)
    bounded = dict(context)
    components = [dict(component) for component in context["components"]]
    bounded["components"] = components
    for entry in sorted(
        components,
        key=lambda c: canonical_size(c.get("data"), default=str),
        reverse=True,
    ):
        if size(bounded) <= budget:
            break
        if entry.get("data") is None:
            continue
        entry["data"] = None
        entry["inline_omitted"] = True
        entry["presentation"] = "unavailable"
        entry["status"] = "unavailable"
        entry["component_failures"] = {}
        entry["reason"] = (
            entry.get("reason")
            or f"inline data omitted: over the {budget}-byte context budget"
        )
        bounded["availability"] = (
            "degraded"
            if any(
                c.get("data") is not None
                and c["status"] in {"available", "degraded", "empty"}
                for c in components
            )
            else "unavailable"
        )
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
        summary="Compose bounded project, job, incident, campaign, regression or trajectory evidence from its owners.",
        Input=ComposeInput,
        Output=ComposedContext,
        handler=_compose,
        resource_kinds=("project", "checkout", "job", "context_snapshot"),
        next_actions=(
            "jobs.list",
            "jobs.logs",
            "operations.run",
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
        documentation="Native owners supply bounded task closure, current project state and retained job receipts. Delivery, acceptance and historical comparisons remain unknown without independent evidence. snapshot_ref retains the exact observation. availability and component presentation report usability independently of transport success; omitted data is unavailable.",
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
