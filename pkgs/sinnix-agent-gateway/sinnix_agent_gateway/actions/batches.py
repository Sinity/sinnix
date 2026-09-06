"""Batches: several workers on one base commit, landed as one candidate.

A batch is agentctl's run manifest; ``runtime.jobs`` (``LocalJobs``) answers
every batch operation from it. Worker and landing tasks are ordinary jobs, so
every view here carries the same pueue task identity ``jobs.*`` uses and bead
membership comes from the manifest, never from a task label.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from ..action import (
    ALL_PRINCIPALS,
    CONTROL_OPERATOR,
    Action,
    Example,
    MutationControls,
    RequestControls,
)
from ..capabilities import Capability
from ..contracts import VerbFamily
from ..locators import (
    ProjectLocator,
    RunLocator,
    bead_ref,
    encode_file_ref,
    job_ref,
    project_ref,
    run_ref,
)
from ..results import ProtocolError
from ..schemas import GatewayModel
from .jobs import JobState

if TYPE_CHECKING:
    from ..runtime import Runtime

Backend = Literal["claude", "codex", "gemini", "grok", "antigravity"]

# What a run's stage lets the caller do next; nothing here dispatches.
_TERMINAL_STAGES = {"landed", "abandoned"}

# agentctl's refusal codes as a typed failure plus the action that follows.
# A code absent here keeps the owner's own class.
_REFUSALS: dict[str, tuple[str, str]] = {
    "unknown_run": ("not_found", "batches.list"),
    "ambiguous_run": ("conflict", "batches.list"),
    "worker_missing": ("not_found", "batches.status"),
    "project": ("invalid_request", "batches.list"),
    "members": ("conflict", "beads.query"),
    "already_accepted": ("conflict", "batches.status"),
    "abandoned": ("conflict", "batches.list"),
    "landing_in_progress": ("conflict", "jobs.wait"),
    "worker_active": ("conflict", "jobs.wait"),
    "worker_not_done": ("conflict", "jobs.wait"),
    "worker_result_missing": ("conflict", "batches.resume"),
}


def _owner(
    runtime: Runtime, operation: str, arguments: Mapping[str, Any]
) -> dict[str, Any]:
    """One batch operation, with agentctl's refusal reported as what to do next."""
    try:
        return runtime._job(operation, arguments)
    except ProtocolError as exc:
        mapped = _REFUSALS.get(str(exc.details.get("refusal")))
        if mapped is None:
            raise
        code, next_action = mapped
        raise ProtocolError(
            code,
            str(exc),
            details={**exc.details, "next_action": next_action},
            diagnostic_refs=exc.diagnostic_refs,
        ) from exc


# ------------------------------------------------------------------ views


class WorkerView(GatewayModel):
    worker_id: str
    beads: list[str] = Field(default_factory=list)
    bead_refs: list[str] = Field(default_factory=list)
    branch: str | None = None
    worktree: str | None = None
    worktree_ref: str | None = None
    stage: str | None = Field(
        default=None, description="pueue's phase first, the manifest second."
    )
    job_id: int | None = None
    job_ref: str | None = None
    job_launch_reference: str | None = Field(
        default=None,
        description="This worker's job as jobs.* addresses it across a reorder.",
    )
    job_ids: list[int] = Field(
        default_factory=list,
        description="Every task this worker has had, oldest first.",
    )
    backend: str | None = None
    model: str | None = None
    effort: str | None = None
    result_filed: bool = False
    state: JobState | None = None


class LandingView(GatewayModel):
    job_id: int | None = None
    job_ref: str | None = None
    job_launch_reference: str | None = Field(
        default=None,
        description="The landing job as jobs.* addresses it across a reorder.",
    )
    state: JobState | None = None
    integration_branch: str | None = None
    candidate_sha: str | None = None
    pr_number: int | None = None
    failure: dict[str, Any] | None = Field(
        default=None, description="The refusal that stopped the last landing."
    )


class RunView(GatewayModel):
    ref: str
    run_id: str
    project_id: str
    project_ref: str
    base_commit: str | None = None
    created_at: str | None = None
    harness: str | None = None
    stage: str | None = None
    prepared: bool = False
    accepted: bool = False
    workers: list[WorkerView] = Field(default_factory=list)
    landing: LandingView = Field(default_factory=LandingView)
    acceptance: dict[str, Any] | None = Field(
        default=None, description="The landing's record: candidate, beads, residual."
    )
    abandoned: dict[str, Any] | None = None
    affordances: list[str] = Field(default_factory=list)


def _state(raw: Any) -> JobState | None:
    if not isinstance(raw, Mapping):
        return None
    return JobState(
        phase=raw.get("phase"),
        terminal=raw.get("terminal"),
        exit_code=raw.get("exit_code"),
    )


def _reference(raw: Any) -> str | None:
    return str(raw) if isinstance(raw, str) and raw else None


def _job_id(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _worker_view(project_id: str, payload: Mapping[str, Any]) -> WorkerView:
    beads = [str(bead) for bead in payload.get("beads") or []]
    worktree = payload.get("worktree")
    job_id = _job_id(payload.get("job_id"))
    return WorkerView(
        worker_id=str(payload.get("worker_id")),
        beads=beads,
        bead_refs=[bead_ref(project_id, bead) for bead in beads],
        branch=payload.get("branch"),
        worktree=worktree,
        worktree_ref=encode_file_ref(worktree) if worktree else None,
        stage=payload.get("stage"),
        job_id=job_id,
        job_ref=job_ref(job_id) if job_id is not None else None,
        job_launch_reference=_reference(payload.get("job_launch_reference")),
        job_ids=[
            value
            for value in (_job_id(item) for item in payload.get("job_ids") or [])
            if value is not None
        ],
        backend=payload.get("backend"),
        model=payload.get("model"),
        effort=payload.get("effort"),
        result_filed=bool(payload.get("result_filed")),
        state=_state(payload.get("state")),
    )


def _affordances(stage: str | None, accepted: bool, abandoned: Any) -> list[str]:
    if accepted or abandoned or (stage in _TERMINAL_STAGES):
        return ["batches.list"]
    if stage == "working":
        return ["batches.status", "jobs.wait", "jobs.logs"]
    return ["batches.status", "batches.land", "batches.resume"]


def _run_view(payload: Mapping[str, Any]) -> RunView:
    run_id = payload.get("run_id")
    project_id = payload.get("project_id")
    if not isinstance(run_id, str) or not isinstance(project_id, str):
        raise ProtocolError("owner_failed", "batch owner omitted the run identity")
    landing = (
        payload.get("landing") if isinstance(payload.get("landing"), Mapping) else {}
    )
    landing_job = _job_id(landing.get("job_id"))
    stage = payload.get("stage")
    accepted = bool(payload.get("accepted"))
    return RunView(
        ref=run_ref(project_id, run_id),
        run_id=run_id,
        project_id=project_id,
        project_ref=project_ref(project_id),
        base_commit=payload.get("base_commit"),
        created_at=payload.get("created_at"),
        harness=payload.get("harness"),
        stage=stage,
        prepared=bool(payload.get("prepared")),
        accepted=accepted,
        workers=[
            _worker_view(project_id, worker)
            for worker in payload.get("workers") or []
            if isinstance(worker, Mapping)
        ],
        landing=LandingView(
            job_id=landing_job,
            job_ref=job_ref(landing_job) if landing_job is not None else None,
            job_launch_reference=_reference(landing.get("job_launch_reference")),
            state=_state(landing.get("state")),
            integration_branch=landing.get("integration_branch"),
            candidate_sha=landing.get("candidate_sha"),
            pr_number=landing.get("pr_number"),
            failure=landing.get("failure"),
        ),
        acceptance=payload.get("acceptance"),
        abandoned=payload.get("abandoned"),
        affordances=_affordances(stage, accepted, payload.get("abandoned")),
    )


# ------------------------------------------------------------------ list


class ListInput(RequestControls):
    project: ProjectLocator | None = Field(
        default=None, description="Only runs of this project."
    )
    limit: int = Field(default=25, ge=1, le=200)


class RunPage(GatewayModel):
    runs: list[RunView]
    limit: int
    total: int
    truncated: bool


def _list(runtime: Runtime, inp: ListInput) -> RunPage:
    runtime.principal.require(Capability.JOB_READ)
    arguments: dict[str, Any] = {"limit": inp.limit}
    if inp.project is not None:
        arguments["project_id"] = inp.project.resolve(runtime)
    page = _owner(runtime, "batch.list", arguments)
    rows = page.get("runs")
    if not isinstance(rows, list):
        raise ProtocolError("owner_failed", "batch owner list response is malformed")
    return RunPage(
        runs=[_run_view(row) for row in rows],
        limit=inp.limit,
        total=int(page.get("total") or len(rows)),
        truncated=bool(page.get("truncated")),
    )


# ---------------------------------------------------------------- status


class StatusInput(RequestControls):
    target: RunLocator


def _status(runtime: Runtime, inp: StatusInput) -> RunView:
    runtime.principal.require(Capability.JOB_READ)
    return _run_view(_owner(runtime, "batch.status", inp.target.resolve()))


# ----------------------------------------------------------------- start


class AgentChoice(MutationControls):
    backend: Backend | None = Field(
        default=None, description="Defaults to the project descriptor's packet default."
    )
    model: str | None = Field(default=None, min_length=1, max_length=256)
    effort: str | None = Field(default=None, min_length=1, max_length=32)


class StartInput(AgentChoice):
    project: ProjectLocator
    beads: list[str] = Field(
        min_length=1,
        max_length=16,
        description="The bead ids to work; each becomes its own worker unless workers groups them.",
    )
    workers: list[list[str]] | None = Field(
        default=None,
        max_length=16,
        description="Group the beads into workers; every bead must appear in exactly one group.",
    )


class RunStarted(RunView):
    existing: bool = Field(
        default=False, description="The run already held these beads; nothing launched."
    )
    resumed: bool = Field(
        default=False, description="An unprepared run was carried to prepared."
    )


def _start(runtime: Runtime, inp: StartInput) -> RunStarted:
    runtime.principal.require(Capability.JOB_START)
    arguments: dict[str, Any] = {
        "project_id": inp.project.resolve(runtime),
        "beads": inp.beads,
        "backend": inp.backend,
        "model": inp.model,
        "effort": inp.effort,
    }
    if inp.workers is not None:
        arguments["workers"] = inp.workers
    result = _owner(runtime, "batch.start", arguments)
    return RunStarted(
        **_run_view(result).model_dump(),
        existing=bool(result.get("existing")),
        resumed=bool(result.get("resumed")),
    )


# ------------------------------------------------------------------ land


class LandInput(MutationControls):
    target: RunLocator


class LandQueued(RunView):
    landing_job_id: int = Field(description="The landing task this call queued.")
    landing_job_ref: str


def _land(runtime: Runtime, inp: LandInput) -> LandQueued:
    runtime.principal.require(Capability.JOB_START)
    result = _owner(runtime, "batch.land", inp.target.resolve())
    queued = _job_id(result.get("landing_job_id"))
    if queued is None:
        raise ProtocolError("owner_failed", "batch owner queued no landing task")
    return LandQueued(
        **_run_view(result).model_dump(),
        landing_job_id=queued,
        landing_job_ref=job_ref(queued),
    )


# ---------------------------------------------------------------- resume


class ResumeInput(AgentChoice):
    target: RunLocator
    worker: str = Field(
        min_length=1,
        max_length=128,
        description="The worker id, as batches.status names it.",
    )


class ResumeQueued(RunView):
    resumed_job_id: int = Field(description="The agent task this call queued.")
    resumed_job_ref: str


def _resume(runtime: Runtime, inp: ResumeInput) -> ResumeQueued:
    runtime.principal.require(Capability.JOB_START)
    result = _owner(
        runtime,
        "batch.resume",
        {
            **inp.target.resolve(),
            "worker_id": inp.worker,
            "backend": inp.backend,
            "model": inp.model,
            "effort": inp.effort,
        },
    )
    queued = _job_id(result.get("resumed_job_id"))
    if queued is None:
        raise ProtocolError("owner_failed", "batch owner queued no agent task")
    return ResumeQueued(
        **_run_view(result).model_dump(),
        resumed_job_id=queued,
        resumed_job_ref=job_ref(queued),
    )


# --------------------------------------------------------------- actions


_RUN = "sinnix://projects/sinnix/runs/sinnix-20260906-012123-a2c81926"
_SUFFIX = {"run_id": "a2c81926"}

ACTIONS: tuple[Action, ...] = (
    Action(
        name="batches.list",
        family=VerbFamily.QUERY,
        owner="systemd-jobs",
        summary="List batch runs newest first, with each worker's stage and task.",
        Input=ListInput,
        Output=RunPage,
        handler=_list,
        principals=ALL_PRINCIPALS,
        resource_kinds=("project", "run", "job"),
        affordances=("batches.status", "jobs.logs", "jobs.wait"),
        aliases=("runs", "agentctl batch list", "which batches", "active runs"),
        examples=(
            Example(title="Recent runs", input={"limit": 10}),
            Example(
                title="One project's runs", input={"project": {"project": "sinnix"}}
            ),
        ),
    ),
    Action(
        name="batches.status",
        family=VerbFamily.GET,
        owner="systemd-jobs",
        summary="One run: its stage, every worker's beads, worktree and task, and the landing.",
        Input=StatusInput,
        Output=RunView,
        handler=_status,
        principals=ALL_PRINCIPALS,
        resource_kinds=("run", "bead", "job"),
        affordances=("jobs.logs", "jobs.wait", "batches.land", "batches.resume"),
        aliases=(
            "batch status",
            "run status",
            "how is the batch",
            "agentctl batch status",
        ),
        documentation="Every id is a pueue task id: pass a worker's or the landing's job_id to jobs.logs, jobs.wait or jobs.cancel, with its job_launch_reference so the call survives a reorder.",
        examples=(
            Example(title="By run suffix", input={"target": _SUFFIX}),
            Example(title="By canonical ref", input={"target": {"ref": _RUN}}),
        ),
    ),
    Action(
        name="batches.start",
        family=VerbFamily.RUN,
        owner="systemd-jobs",
        summary="Start a batch: claim the beads, create a worktree per worker, queue the workers and the landing.",
        Input=StartInput,
        Output=RunStarted,
        handler=_start,
        principals=CONTROL_OPERATOR,
        resource_kinds=("project", "bead", "run", "job"),
        affordances=("batches.status", "jobs.wait", "jobs.logs", "jobs.cancel"),
        aliases=("dispatch", "agentctl batch start", "work on bead", "start agents"),
        documentation="backend, model and effort default to the project descriptor's packet defaults. Refused when a bead is claimed or already in a live run. The landing task is queued behind the workers and runs itself.",
        examples=(
            Example(
                title="One bead, one worker",
                input={
                    "project": {"project": "sinnix"},
                    "beads": ["sinnix-abc1"],
                    "idempotency_key": "batch-sinnix-abc1",
                },
            ),
            Example(
                title="Two workers, pinned agent",
                input={
                    "project": {"project": "sinnix"},
                    "beads": ["sinnix-abc1", "sinnix-abc2", "sinnix-abc3"],
                    "workers": [["sinnix-abc1", "sinnix-abc2"], ["sinnix-abc3"]],
                    "backend": "codex",
                    "model": "gpt-5.6-terra",
                    "effort": "high",
                    "idempotency_key": "batch-sinnix-abc1-3",
                },
            ),
        ),
    ),
    Action(
        name="batches.land",
        family=VerbFamily.RUN,
        owner="systemd-jobs",
        summary="Queue a landing task for a run: integrate, verify, review, publish, accept.",
        Input=LandInput,
        Output=LandQueued,
        handler=_land,
        principals=CONTROL_OPERATOR,
        resource_kinds=("run", "job"),
        affordances=("jobs.wait", "jobs.logs", "batches.status"),
        aliases=("land", "agentctl batch land", "publish the batch", "merge the run"),
        documentation="batches.start already queues the first landing behind the workers; this re-queues one after a landing failed. The landing runs as a job, so wait on landing_job_id rather than on this call.",
        examples=(
            Example(
                title="Re-run a failed landing",
                input={"target": _SUFFIX, "idempotency_key": "land-a2c81926"},
            ),
        ),
    ),
    Action(
        name="batches.resume",
        family=VerbFamily.RUN,
        owner="systemd-jobs",
        summary="Queue a fresh agent into one worker's existing worktree with its original packet.",
        Input=ResumeInput,
        Output=ResumeQueued,
        handler=_resume,
        principals=CONTROL_OPERATOR,
        resource_kinds=("run", "job"),
        affordances=("jobs.wait", "jobs.logs", "batches.status"),
        aliases=("resume worker", "agentctl batch resume", "retry the agent"),
        documentation="backend, model and effort default to the worker's own. Refused while the worker's task is still queued or running.",
        examples=(
            Example(
                title="Resume one worker",
                input={
                    "target": _SUFFIX,
                    "worker": "sinnix-abc1",
                    "idempotency_key": "resume-a2c81926-sinnix-abc1",
                },
            ),
        ),
    ),
)
