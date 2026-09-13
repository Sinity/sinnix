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
        description="sinnix://results/<id>; readable through results.get or MCP resources."
    )
    context_schema: str | None = None
    components: list[ContextComponent]
    component_plan: list[dict[str, Any]] = Field(default_factory=list)
    total_budget_bytes: int
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
    from ..capabilities import Capability
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
        runtime.principal.require(Capability.JOB_READ)
        job_id, ref, launch_reference = inp.job.resolve()
        identity = {"job_id": job_id, "max_bytes": 64000}
        if launch_reference is not None:
            identity["launch_reference"] = launch_reference
        try:
            value = runtime._job("job.result", identity)
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
            key = "launch_reference" if launch_reference is not None else "job_id"
            if str(value.get(key)) != str(identity[key]):
                raise ProtocolError(
                    "owner_failed", "job owner response names another job"
                )
            ref = f"sinnix://jobs/{value['job_id']}"
            product = OwnerProduct(
                owner="agentctl", availability="available", data=value, source_ref=ref
            )

    else:
        assert inp.project is not None
        project = inp.project.resolve(runtime)
        runtime.projects._project(project)
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
        product = OwnerProduct(
            owner="polylogue",
            availability="available"
            if any(item.availability == "available" for item in value.sessions)
            else "unavailable",
            reason=None
            if any(item.availability == "available" for item in value.sessions)
            else "Requested session products are unavailable",
            data=value.model_dump(),
            source_ref="sinnix://mcp/polylogue",
        )
    elif inp.intent == "incident":
        runtime.principal.require(Capability.MACHINE_READ)
        value = runtime.observe.machine_query("overview")
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
        runtime.principal.require(Capability.TASK_READ)
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
                **({"refresh_id": inp.refresh_id} if inp.refresh_id else {}),
            },
            deadline_at=inp.deadline_at,
        )
    # Persistence identifies this observation. Domain components, ordering,
    # coverage and budgets remain exactly as the owner returned them.
    context = runtime.persist_context(
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
                    "source_revision": source_revision(product.model_dump()),
                    "source_ref": product.source_ref,
                    "data": product.model_dump(),
                    "reason": product.reason,
                }
            ],
        }
    )
    return ComposedContext(
        **{
            key: value
            for key, value in context.items()
            if key in ComposedContext.model_fields
        },
        context_schema=context["schema"],
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
        documentation="The selected owner supplies domain composition, source coverage and partial results. The gateway preserves its product and availability in an immutable observation under snapshot_ref.",
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
