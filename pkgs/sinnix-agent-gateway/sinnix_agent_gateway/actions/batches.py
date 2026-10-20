"""Read retained batch manifests and their native job observations.

A batch is agentctl's run manifest; ``runtime.jobs`` (``LocalJobs``) answers
every batch operation from it. Worker and landing tasks are ordinary jobs, so
every view here carries the same pueue task identity ``jobs.*`` uses and bead
membership comes from the manifest, never from a task label.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import Field

from ..action import (
    Action,
    Example,
    RequestControls,
)
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


# What a run's stage lets the caller do next; nothing here dispatches.
_TERMINAL_STAGES = {"landed", "abandoned"}

# agentctl's refusal codes as a typed failure plus the action that follows.
# A code absent here keeps the owner's own class.
_REFUSALS: dict[str, tuple[str, str]] = {
    "admission_closed": ("conflict", "operations.run"),
    "unknown_run": ("not_found", "batches.list"),
    "ambiguous_run": ("conflict", "batches.list"),
    "worker_missing": ("not_found", "batches.status"),
    "project": ("invalid_request", "batches.list"),
    "members": ("conflict", "beads.query"),
    "already_accepted": ("conflict", "batches.status"),
    "abandoned": ("conflict", "batches.list"),
    "landing_in_progress": ("conflict", "jobs.wait"),
    "worker_active": ("conflict", "jobs.wait"),
    "verify_running": ("conflict", "jobs.wait"),
    "worker_not_done": ("conflict", "jobs.wait"),
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
    task_id: int | None = None
    job_ref: str | None = None
    job_id: str | None = Field(
        default=None,
        description="This worker's job as jobs.* addresses it across a reorder.",
    )
    task_ids: list[int] = Field(
        default_factory=list,
        description="Every task this worker has had, oldest first.",
    )
    backend: str | None = None
    model: str | None = None
    effort: str | None = None
    provenance: dict[str, Any] | None = Field(
        default=None,
        description="Agentctl dispatch and worker claims; absent measured executor fields remain unknown.",
    )
    attempts: list[dict[str, Any]] | None = Field(
        default=None,
        description="Retained native retry history, if supplied by agentctl.",
    )
    result_filed: bool = False
    state: JobState | None = None


class LandingView(GatewayModel):
    task_id: int | None = None
    job_ref: str | None = None
    job_id: str | None = Field(
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
    next_actions: list[str] = Field(default_factory=list)


def _state(raw: Any) -> JobState | None:
    if not isinstance(raw, Mapping):
        return None
    return JobState(
        phase=raw.get("phase"),
        terminal=raw.get("terminal"),
        exit_code=raw.get("exit_code"),
        dependencies=raw.get("dependencies"),
    )


def _name(raw: Any) -> str | None:
    return str(raw) if isinstance(raw, str) and raw else None


def _task_id(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _worker_view(project_id: str, payload: Mapping[str, Any]) -> WorkerView:
    beads = [str(bead) for bead in payload.get("beads") or []]
    worktree = payload.get("worktree")
    task_id = _task_id(payload.get("task_id"))
    return WorkerView(
        worker_id=str(payload.get("worker_id")),
        beads=beads,
        bead_refs=[bead_ref(project_id, bead) for bead in beads],
        branch=payload.get("branch"),
        worktree=worktree,
        worktree_ref=encode_file_ref(worktree) if worktree else None,
        stage=payload.get("stage"),
        task_id=task_id,
        job_ref=job_ref(task_id) if task_id is not None else None,
        job_id=_name(payload.get("job_id")),
        task_ids=[
            value
            for value in (_task_id(item) for item in payload.get("task_ids") or [])
            if value is not None
        ],
        backend=payload.get("backend"),
        model=payload.get("model"),
        effort=payload.get("effort"),
        provenance=payload.get("provenance"),
        attempts=payload.get("attempts"),
        result_filed=bool(payload.get("result_filed")),
        state=_state(payload.get("state")),
    )


def _next_actions(stage: str | None, accepted: bool, abandoned: Any) -> list[str]:
    if accepted or abandoned or (stage in _TERMINAL_STAGES):
        return ["batches.list"]
    if stage == "working":
        return ["batches.status", "jobs.wait", "jobs.logs"]
    return ["batches.status", "jobs.logs"]


def _run_view(payload: Mapping[str, Any]) -> RunView:
    run_id = payload.get("run_id")
    project_id = payload.get("project_id")
    if not isinstance(run_id, str) or not isinstance(project_id, str):
        raise ProtocolError("owner_failed", "batch owner omitted the run identity")
    landing = (
        payload.get("landing") if isinstance(payload.get("landing"), Mapping) else {}
    )
    landing_job = _task_id(landing.get("task_id"))
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
            task_id=landing_job,
            job_ref=job_ref(landing_job) if landing_job is not None else None,
            job_id=_name(landing.get("job_id")),
            state=_state(landing.get("state")),
            integration_branch=landing.get("integration_branch"),
            candidate_sha=landing.get("candidate_sha"),
            pr_number=landing.get("pr_number"),
            failure=landing.get("failure"),
        ),
        acceptance=payload.get("acceptance"),
        abandoned=payload.get("abandoned"),
        next_actions=_next_actions(stage, accepted, payload.get("abandoned")),
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
    return _run_view(_owner(runtime, "batch.status", inp.target.resolve()))


# ----------------------------------------------------------------- start


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
        resource_kinds=("project", "run", "job"),
        next_actions=("batches.status", "jobs.logs", "jobs.wait"),
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
        resource_kinds=("run", "bead", "job"),
        next_actions=("jobs.logs", "jobs.wait", "batches.list"),
        aliases=(
            "batch status",
            "run status",
            "how is the batch",
            "agentctl batch status",
        ),
        documentation="Worker and landing task_id fields are numeric pueue queue positions; job_id fields are stable strings. Pass both in jobs.logs, jobs.wait or jobs.cancel targets so calls follow the job across a reorder.",
        examples=(
            Example(title="By run suffix", input={"target": _SUFFIX}),
            Example(title="By canonical ref", input={"target": {"ref": _RUN}}),
        ),
    ),
)
