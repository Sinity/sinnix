"""Composed, budgeted context for one intent: orientation, triage, job review, incident."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from ..action import ALL_PRINCIPALS, Action, Example, RequestControls
from ..contracts import VerbFamily
from ..locators import JobLocator, ProjectLocator, project_ref
from ..results import ProtocolError
from ..schemas import GatewayModel
from .products import HistoricalSelector

if TYPE_CHECKING:
    from ..runtime import Runtime

Intent = Literal[
    "project.orientation",
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
        description="Required for project.orientation, project.triage and incident.",
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
    status: Literal["available", "unavailable"]
    source_revision: str | None = None
    snapshot_ref: str
    source_ref: str | None = None
    data: Any = None
    reason: str | None = None


class ComposedContext(GatewayModel):
    ref: str = Field(description="Canonical ref of the composed target.")
    intent: str
    target_ref: str
    snapshot_ref: str = Field(
        description="sinnix://contexts/<id>; readable again by ref."
    )
    context_schema: str | None = None
    components: list[ContextComponent]
    component_plan: list[dict[str, Any]] = Field(default_factory=list)
    total_budget_bytes: int
    project: Any = Field(
        default=None,
        description="Flattened when every orientation component is available.",
    )
    tasks: Any = None
    authority: Any = None
    job: Any = None
    result: Any = None
    events: Any = None
    runtime: Any = None
    transitions: Any = None
    receipts: Any = None
    jobs: Any = None
    affordances: list[str] = Field(default_factory=list)


_AFFORDANCES: dict[str, list[str]] = {
    "campaign.progress": ["campaign.progress", "beads.get"],
    "session.orchestration": ["sessions.orchestration", "sessions.query"],
    "verification.regression": ["campaign.progress", "jobs.get"],
    "project.trajectory": ["campaign.progress", "sessions.query"],
    "project.orientation": ["batches.start", "jobs.list", "events.tail"],
    "project.triage": ["batches.start", "jobs.list", "events.tail"],
    "job.review": ["jobs.logs", "jobs.retry", "jobs.cancel"],
    "incident": ["events.tail", "jobs.list", "wait.for"],
}


async def _compose(runtime: Runtime, inp: ComposeInput) -> ComposedContext:
    launch_reference = None
    if inp.job is not None:
        _, ref, launch_reference = inp.job.resolve()
    else:
        assert inp.project is not None
        ref = project_ref(inp.project.resolve(runtime))
    if inp.intent in {
        "campaign.progress",
        "session.orchestration",
        "verification.regression",
        "project.trajectory",
    }:
        from ..contexts import ComponentResult, ComponentSpec
        from .products import (
            CampaignInput,
            OrchestrationInput,
            _campaign,
            _orchestration,
            owner_product,
        )

        assert inp.project is not None
        project = inp.project.resolve(runtime)
        runtime.projects._project(project)
        if inp.intent == "campaign.progress":
            try:
                value = (
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
                ).model_dump()
                result = ComponentResult.available("campaign", value, source_ref=ref)
            except ProtocolError as exc:
                if exc.code not in {
                    "unavailable",
                    "owner_failed",
                    "unsupported_capability",
                }:
                    raise
                result = ComponentResult.unavailable(
                    "campaign", str(exc), source_ref=ref
                )
        elif inp.intent == "session.orchestration":
            value = (
                await _orchestration(
                    runtime,
                    OrchestrationInput(
                        session_refs=inp.session_refs, deadline_at=inp.deadline_at
                    ),
                )
            ).model_dump()
            if any(row["availability"] == "available" for row in value["sessions"]):
                result = ComponentResult.available(
                    "orchestration", value, source_ref="sinnix://mcp/polylogue"
                )
            else:
                result = ComponentResult.unavailable(
                    "orchestration",
                    "; ".join(
                        row.get("reason") or "Owner unavailable"
                        for row in value["sessions"]
                    ),
                    source_ref="sinnix://mcp/polylogue",
                )
        else:
            product = await owner_product(
                runtime,
                "lynchpin",
                "lynchpin_project",
                {
                    "action": inp.intent.replace(".", "_"),
                    "project": project,
                    **({"refresh_id": inp.refresh_id} if inp.refresh_id else {}),
                },
                deadline_at=inp.deadline_at,
            )
            result = (
                ComponentResult.available(
                    "evidence", product.data, source_ref=product.source_ref
                )
                if product.availability == "available"
                else ComponentResult.unavailable(
                    "evidence",
                    product.reason or "Owner unavailable",
                    source_ref=product.source_ref,
                )
            )
        context = runtime.context_composer.compose(
            inp.intent, ref, [ComponentSpec(result.name, 56000, lambda: result)]
        )
        if runtime.context_snapshots is None:
            raise ProtocolError("unavailable", "Context snapshot store is unavailable")
        runtime.context_snapshots.put(context)
        context = {"ref": ref, **context}
    else:
        context = runtime.compose_context(
            ref, inp.intent, launch_reference=launch_reference
        )
    return ComposedContext(
        ref=context["ref"],
        intent=context["intent"],
        target_ref=context["target_ref"],
        snapshot_ref=context["snapshot_ref"],
        context_schema=context.get("schema"),
        components=[ContextComponent(**row) for row in context["components"]],
        component_plan=list(context.get("component_plan") or []),
        total_budget_bytes=int(context["total_budget_bytes"]),
        **{
            key: context[key]
            for key in ComposedContext.model_fields
            if key in context
            and key
            not in {
                "ref",
                "intent",
                "target_ref",
                "snapshot_ref",
                "components",
                "component_plan",
                "total_budget_bytes",
                "affordances",
                "context_schema",
            }
        },
        affordances=_AFFORDANCES[inp.intent],
    )


ACTIONS: tuple[Action, ...] = (
    Action(
        name="context.compose",
        family=VerbFamily.CONTEXT,
        owner="context",
        summary="Compose bounded project, job, incident, campaign, orchestration, regression or trajectory evidence from its owners.",
        Input=ComposeInput,
        Output=ComposedContext,
        handler=_compose,
        principals=ALL_PRINCIPALS,
        resource_kinds=("project", "checkout", "job", "context_snapshot"),
        affordances=(
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
        documentation="Each component is budgeted and isolated: an unavailable owner marks its component unavailable with a reason instead of failing the call. The snapshot is persisted under snapshot_ref.",
        examples=(
            Example(
                title="Orient in sinnix",
                input={
                    "intent": "project.orientation",
                    "project": {"project": "sinnix"},
                },
            ),
            Example(
                title="Review a job",
                input={"intent": "job.review", "job": {"job_id": 41}},
            ),
            Example(
                title="Incident overview",
                input={"intent": "incident", "project": {"project": "sinnix"}},
            ),
        ),
    ),
)
