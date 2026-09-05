"""Composed, budgeted context for one intent: orientation, triage, job review, incident."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from ..action import ALL_PRINCIPALS, Action, Example, RequestControls
from ..contracts import VerbFamily
from ..locators import JobLocator, ProjectLocator, project_ref
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime

Intent = Literal["project.orientation", "project.triage", "job.review", "incident"]


class ComposeInput(RequestControls):
    intent: Intent
    project: ProjectLocator | None = Field(
        default=None,
        description="Required for project.orientation, project.triage and incident.",
    )
    job: JobLocator | None = Field(default=None, description="Required for job.review.")

    @model_validator(mode="after")
    def target_matches_intent(self) -> ComposeInput:
        wants_job = self.intent == "job.review"
        if wants_job and (self.job is None or self.project is not None):
            raise ValueError("job.review takes job and no project")
        if not wants_job and (self.project is None or self.job is not None):
            raise ValueError(f"{self.intent} takes project and no job")
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
    "project.orientation": ["agent.for_bead", "jobs.list", "events.tail"],
    "project.triage": ["agent.for_bead", "jobs.list", "events.tail"],
    "job.review": ["jobs.logs", "jobs.retry", "jobs.cancel"],
    "incident": ["events.tail", "jobs.list", "wait.for"],
}


def _compose(runtime: Runtime, inp: ComposeInput) -> ComposedContext:
    if inp.job is not None:
        _, ref = inp.job.resolve()
    else:
        assert inp.project is not None
        ref = project_ref(inp.project.resolve(runtime))
    context = runtime.compose_context(ref, inp.intent)
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
        summary="Compose a bounded snapshot for one intent: project orientation or triage, job review, or an incident.",
        Input=ComposeInput,
        Output=ComposedContext,
        handler=_compose,
        principals=ALL_PRINCIPALS,
        resource_kinds=("project", "checkout", "job", "context_snapshot"),
        affordances=(
            "jobs.list",
            "jobs.logs",
            "agent.for_bead",
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
