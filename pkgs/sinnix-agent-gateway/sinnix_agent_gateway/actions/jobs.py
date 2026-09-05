"""Jobs: pueue tasks through agentctl's launch routes, in process.

A job is a pueue task; ``runtime.jobs`` (``LocalJobs``) answers every job
operation. Responses carry every identity the caller needs next: project,
bead, checkout, pueue task id, and a typed next action on refusal.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Literal

import anyio
from pydantic import Field

from ..action import (
    ALL_PRINCIPALS,
    CONTROL_OPERATOR,
    OPERATOR_ONLY,
    Action,
    Example,
    MutationControls,
    RequestControls,
)
from ..capabilities import Capability
from ..contracts import VerbFamily
from ..locators import (
    BeadLocator,
    CheckoutLocator,
    JobLocator,
    ProjectLocator,
    bead_ref,
    encode_file_ref,
    job_ref,
    project_ref,
)
from ..results import ProtocolError
from ..schemas import GatewayModel

if TYPE_CHECKING:
    from ..runtime import Runtime

Backend = Literal["claude", "codex", "gemini", "grok", "antigravity"]
Phase = str

# ------------------------------------------------------------------ views


class JobState(GatewayModel):
    phase: str | None = None
    terminal: bool | None = None
    exit_code: int | None = None


class LaneBinding(GatewayModel):
    """The bead, branch and worktree an agent task was queued for."""

    bead: str | None = None
    bead_ref: str | None = None
    branch: str | None = None
    worktree: str | None = None
    worktree_ref: str | None = None


class JobView(GatewayModel):
    ref: str
    job_id: int
    label: str | None = None
    kind: str | None = None
    project_id: str | None = None
    project_ref: str | None = None
    operation: str | None = None
    group: str | None = None
    checkout_path: str | None = None
    checkout_ref: str | None = None
    state: JobState = Field(default_factory=JobState)
    enqueued_at: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    lane: LaneBinding | None = None
    affordances: list[str] = Field(default_factory=list)


def _lane_binding(payload: Mapping[str, Any]) -> LaneBinding | None:
    """The bead an agent task serves, from what the job owner carries today.

    An agent label is ``<project>:lane:<bead>`` or ``<project>:rebase:<bead>``
    and its working directory is the lane worktree. TODO(xteo.19): read the
    bead, branch and worktree from the launch input once ``job get`` exposes
    the binding fields; the branch is not derivable here.
    """
    raw = payload.get("lane") if isinstance(payload.get("lane"), Mapping) else {}
    label = str(payload.get("label") or "")
    parts = label.split(":", 2)
    from_label = (
        parts[2] if len(parts) == 3 and parts[1] in {"lane", "rebase"} else None
    )
    bead = raw.get("bead") or from_label
    if not bead:
        return None
    project_id = payload.get("project_id") or parts[0]
    checkout = (
        payload.get("checkout") if isinstance(payload.get("checkout"), Mapping) else {}
    )
    worktree = raw.get("worktree") or checkout.get("path") or None
    return LaneBinding(
        bead=bead,
        bead_ref=bead_ref(project_id, bead) if project_id else None,
        branch=raw.get("branch"),
        worktree=worktree,
        worktree_ref=encode_file_ref(worktree) if worktree else None,
    )


def _job_view(payload: Mapping[str, Any]) -> JobView:
    try:
        job_id = int(payload["job_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolError("owner_failed", "job owner omitted the job id") from exc
    state = payload.get("state") if isinstance(payload.get("state"), Mapping) else {}
    project_id = payload.get("project_id")
    checkout = (
        payload.get("checkout") if isinstance(payload.get("checkout"), Mapping) else {}
    )
    path = checkout.get("path") or None
    terminal = state.get("terminal")
    affordances = ["jobs.get", "jobs.logs"]
    affordances.append("jobs.retry" if terminal else "jobs.wait")
    if not terminal:
        affordances.append("jobs.cancel")
    return JobView(
        ref=job_ref(job_id),
        job_id=job_id,
        label=payload.get("label"),
        kind=payload.get("kind"),
        project_id=project_id,
        project_ref=project_ref(project_id) if project_id else None,
        operation=payload.get("operation"),
        group=payload.get("group"),
        checkout_path=path,
        checkout_ref=encode_file_ref(path) if path else None,
        state=JobState(
            phase=state.get("phase"),
            terminal=terminal,
            exit_code=state.get("exit_code"),
        ),
        enqueued_at=payload.get("enqueued_at"),
        started_at=payload.get("started_at"),
        ended_at=payload.get("ended_at"),
        lane=_lane_binding(payload),
        affordances=affordances,
    )


def _job(
    runtime: Runtime, operation: str, job_id: int, **arguments: Any
) -> dict[str, Any]:
    """One LocalJobs operation on a job, proving the answer names that job."""
    result = runtime._job(operation, {"job_id": job_id, **arguments})
    if str(result.get("job_id")) != str(job_id):
        raise ProtocolError(
            "owner_failed", f"job owner {operation} response names another job"
        )
    return result


# --------------------------------------------------------------- refusals


_NEXT_ACTIONS: tuple[tuple[str, str, str], ...] = (
    ("already has a worktree", "conflict", "agent.for_bead"),
    ("has no worktree", "not_found", "agent.for_bead"),
    ("not a configured project", "not_found", "projects.list"),
)


def _refusal(exc: ProtocolError, identities: Mapping[str, Any]) -> ProtocolError:
    """An owner refusal with the identities the caller has and the action that follows."""
    message = str(exc)
    code = exc.code
    details: dict[str, Any] = {
        **exc.details,
        **{k: v for k, v in identities.items() if v is not None},
    }
    for needle, mapped, next_action in _NEXT_ACTIONS:
        if needle in message:
            code, details["next_action"] = mapped, next_action
            break
    return ProtocolError(
        code, message, details=details, diagnostic_refs=exc.diagnostic_refs
    )


def _owner_call(
    fn: Callable[..., Any], identities: Mapping[str, Any], **kwargs: Any
) -> Any:
    try:
        return fn(**kwargs)
    except ProtocolError as exc:
        raise _refusal(exc, identities) from exc


def _workspace(
    runtime: Runtime, locator: CheckoutLocator
) -> tuple[str, str | None, str]:
    """``(project_id, absolute worktree path or None for the root, checkout ref)``."""
    resolved = locator.resolve(runtime)
    if resolved.checkout_id is None:
        return resolved.project_id, None, resolved.checkout_ref
    from ..projects import ProjectError

    try:
        row = runtime.projects.checkout(resolved.project_id, resolved.checkout_id)
    except ProjectError as exc:
        raise ProtocolError("not_found", str(exc)) from exc
    return resolved.project_id, str(row["checkout"]["path"]), resolved.checkout_ref


# ------------------------------------------------------------------ list


class ListInput(RequestControls):
    project: ProjectLocator | None = Field(
        default=None, description="Only jobs labelled with this project."
    )
    limit: int = Field(default=100, ge=1, le=1_000)
    cursor: str | None = Field(default=None, min_length=1, max_length=512)


class JobPage(GatewayModel):
    jobs: list[JobView]
    limit: int
    total: int | None = None
    truncated: bool
    next_cursor: str | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)


def _list(runtime: Runtime, inp: ListInput) -> JobPage:
    runtime.principal.require(Capability.JOB_READ)
    arguments: dict[str, Any] = {"limit": inp.limit}
    if inp.cursor is not None:
        arguments["cursor"] = inp.cursor
    if inp.project is not None:
        arguments["project_id"] = inp.project.resolve(runtime)
    page = runtime._job("job.list", arguments)
    rows = page.get("jobs")
    if not isinstance(rows, list) or len(rows) > inp.limit:
        raise ProtocolError("owner_failed", "job owner list response is malformed")
    return JobPage(
        jobs=[_job_view(row) for row in rows],
        limit=inp.limit,
        total=page.get("total"),
        truncated=bool(page.get("truncated")),
        next_cursor=page.get("next_cursor"),
        snapshot=dict(page.get("snapshot") or {}),
    )


# ------------------------------------------------------------------- get


class GetInput(RequestControls):
    target: JobLocator
    projection: Literal["summary", "log", "result"] = "summary"
    offset: int = Field(default=0, ge=0, description="Log byte offset.")
    max_bytes: int = Field(default=64_000, ge=1, le=262_144)


class JobLog(GatewayModel):
    ref: str
    job_id: int
    content: str
    offset: int
    max_bytes: int
    returned_bytes: int
    truncated: bool
    next_offset: int | None = None
    affordances: list[str] = Field(default_factory=list)


class JobResult(GatewayModel):
    kind: str | None = Field(default=None, description="exit or artifact.")
    value: Any = None


class JobDetail(JobView):
    projection: Literal["summary", "log", "result"] = "summary"
    log: JobLog | None = None
    result: JobResult | None = None


def _log(runtime: Runtime, job_id: int, offset: int, max_bytes: int) -> JobLog:
    raw = _job(runtime, "job.logs", job_id, offset=offset, max_bytes=max_bytes)
    content = str(raw.get("content") or "")
    truncated = bool(raw.get("truncated"))
    returned = len(content.encode())
    return JobLog(
        ref=job_ref(job_id),
        job_id=job_id,
        content=content,
        offset=offset,
        max_bytes=max_bytes,
        returned_bytes=returned,
        truncated=truncated,
        next_offset=offset + returned if truncated else None,
        affordances=["jobs.get", "jobs.logs"],
    )


def _get(runtime: Runtime, inp: GetInput) -> JobDetail:
    runtime.principal.require(Capability.JOB_READ)
    job_id, _ = inp.target.resolve()
    view = _job_view(_job(runtime, "job.get", job_id))
    detail = JobDetail(**view.model_dump(), projection=inp.projection)
    if inp.projection == "log":
        detail.log = _log(runtime, job_id, inp.offset, inp.max_bytes)
    elif inp.projection == "result":
        raw = _job(runtime, "job.result", job_id, max_bytes=inp.max_bytes)
        detail.result = JobResult(kind=raw.get("kind"), value=raw.get("value"))
    return detail


class LogsInput(RequestControls):
    target: JobLocator
    offset: int = Field(default=0, ge=0)
    max_bytes: int = Field(default=64_000, ge=1, le=262_144)


def _logs(runtime: Runtime, inp: LogsInput) -> JobLog:
    runtime.principal.require(Capability.JOB_READ)
    job_id, _ = inp.target.resolve()
    return _log(runtime, job_id, inp.offset, inp.max_bytes)


# ------------------------------------------------------------------ wait


class JobWaitInput(RequestControls):
    target: JobLocator
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class JobWait(GatewayModel):
    ref: str
    job_id: int
    outcome: Literal["terminal", "timeout"]
    timed_out: bool
    job: JobView
    detail: str | None = None
    affordances: list[str] = Field(default_factory=list)


async def _wait(runtime: Runtime, inp: JobWaitInput) -> JobWait:
    """Block on pueue in a worker thread; a cancelled MCP request abandons it."""
    runtime.principal.require(Capability.JOB_READ)
    job_id, ref = inp.target.resolve()
    raw = await anyio.to_thread.run_sync(
        lambda: _job(runtime, "job.wait", job_id, timeout_seconds=inp.timeout_seconds),
        abandon_on_cancel=True,
    )
    timed_out = bool(raw.get("timed_out"))
    view = _job_view(raw)
    return JobWait(
        ref=ref,
        job_id=job_id,
        outcome="timeout" if timed_out else "terminal",
        timed_out=timed_out,
        job=view,
        detail=raw.get("detail"),
        affordances=["jobs.wait", "jobs.cancel"]
        if timed_out
        else ["jobs.get", "jobs.logs"],
    )


# ---------------------------------------------------------------- cancel


class CancelInput(MutationControls):
    target: JobLocator
    expected_phase: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Refuse unless the job is still in this phase (queued, running, ...).",
    )


class CancelResult(GatewayModel):
    ref: str
    job_id: int
    previous_phase: str | None = None
    job: JobView
    cancel_requested: bool
    already_terminal: bool
    cancelled: str | None = Field(
        default=None, description="killed, dropped, terminal or forgotten."
    )
    scope_unit: str | None = None
    scope_stopped: bool | None = None
    survivors: list[int] = Field(
        default_factory=list,
        description="PIDs that outlived the reap; not empty means the cancel is incomplete.",
    )
    warnings: list[str] = Field(default_factory=list)
    affordances: list[str] = Field(default_factory=list)


def _cancel(runtime: Runtime, inp: CancelInput) -> CancelResult:
    runtime.principal.require(Capability.JOB_CANCEL)
    job_id, ref = inp.target.resolve()
    expected = inp.expected_phase
    if inp.preconditions:
        if set(inp.preconditions) - {"expected_phase"}:
            raise ProtocolError(
                "invalid_request", "job preconditions are not recognized"
            )
        expected = expected or inp.preconditions.get("expected_phase")
    before = _job_view(_job(runtime, "job.get", job_id))
    if expected is not None and before.state.phase != expected:
        raise ProtocolError(
            "precondition_failed",
            "job phase no longer matches",
            details={
                "ref": ref,
                "expected_phase": expected,
                "phase": before.state.phase,
            },
        )
    raw = _job(runtime, "job.cancel", job_id)
    if not isinstance(raw.get("cancel_requested"), bool):
        raise ProtocolError(
            "owner_failed",
            "job owner cancel response does not prove cancellation truth",
        )
    reaped = raw.get("reaped") if isinstance(raw.get("reaped"), Mapping) else {}
    scope = reaped.get("scope") if isinstance(reaped.get("scope"), Mapping) else {}
    survivors = [int(pid) for pid in scope.get("survivors") or []]
    warnings = (
        [f"{len(survivors)} processes survived the reap; the job's scope is not empty"]
        if survivors
        else []
    )
    return CancelResult(
        ref=ref,
        job_id=job_id,
        previous_phase=before.state.phase,
        job=_job_view(raw),
        cancel_requested=raw["cancel_requested"],
        already_terminal=bool(raw.get("already_terminal")),
        cancelled=raw.get("cancelled"),
        scope_unit=scope.get("unit"),
        scope_stopped=scope.get("stopped"),
        survivors=survivors,
        warnings=warnings,
        affordances=["jobs.get", "jobs.logs", "jobs.retry"],
    )


class RetryInput(MutationControls):
    target: JobLocator


def _retry(runtime: Runtime, inp: RetryInput) -> JobView:
    runtime.principal.require(Capability.JOB_START)
    job_id, _ = inp.target.resolve()
    return _job_view(_job(runtime, "job.retry", job_id))


# ------------------------------------------------------------------- run


class OperationRunInput(MutationControls):
    checkout: CheckoutLocator = Field(
        description="The project (its configured root) or one of its worktrees."
    )
    operation: str = Field(
        min_length=1, max_length=128, description="A declared operation name."
    )


def _run_operation(runtime: Runtime, inp: OperationRunInput) -> JobView:
    project_id, workspace, _ = _workspace(runtime, inp.checkout)
    result = _owner_call(
        runtime.v2_run_declared_operation,
        {"project": project_id, "operation": inp.operation, "checkout": workspace},
        project_id=project_id,
        operation=inp.operation,
        workspace_id=workspace,
        parameters=None,
    )
    return _job_view(result)


class ShellRunInput(MutationControls):
    checkout: CheckoutLocator
    argv: list[str] = Field(min_length=1, max_length=128)
    cwd: str = Field(
        default=".",
        min_length=1,
        max_length=4_096,
        description="Relative to the checkout; may not leave it.",
    )
    timeout_seconds: int = Field(default=3_600, ge=1, le=3_600)


def _run_shell(runtime: Runtime, inp: ShellRunInput) -> JobView:
    project_id, workspace, _ = _workspace(runtime, inp.checkout)
    if any(not argument for argument in inp.argv):
        raise ProtocolError("invalid_request", "argv entries must be non-empty")
    result = _owner_call(
        runtime.v2_run_shell,
        {"project": project_id, "checkout": workspace},
        project_id=project_id,
        checkout_id=workspace or "default",
        argv=inp.argv,
        cwd=inp.cwd,
        timeout_seconds=inp.timeout_seconds,
    )
    return _job_view(result)


# ----------------------------------------------------------------- lanes


class LaneStarted(GatewayModel):
    ref: str = Field(description="The agent job's canonical ref.")
    job: JobView
    project_id: str
    project_ref: str
    bead: str
    bead_ref: str
    beads: list[str] = Field(default_factory=list)
    branch: str | None = None
    worktree: str | None = None
    worktree_ref: str | None = None
    backend: str | None = None
    model: str | None = None
    effort: str | None = None
    affordances: list[str] = Field(default_factory=list)


def _lane_started(
    project_id: str, bead: str, lane: Mapping[str, Any], job: Mapping[str, Any]
) -> LaneStarted:
    view = _job_view(job)
    worktree = lane.get("worktree")
    return LaneStarted(
        ref=view.ref,
        job=view,
        project_id=project_id,
        project_ref=project_ref(project_id),
        bead=bead,
        bead_ref=bead_ref(project_id, bead),
        beads=[str(item) for item in lane.get("beads") or [bead]],
        branch=lane.get("branch"),
        worktree=worktree,
        worktree_ref=encode_file_ref(worktree) if worktree else None,
        backend=lane.get("backend"),
        model=lane.get("model"),
        effort=lane.get("effort"),
        affordances=["jobs.wait", "jobs.logs", "jobs.cancel"],
    )


class AgentChoice(MutationControls):
    backend: Backend | None = Field(
        default=None, description="Defaults to the bead's model policy."
    )
    model: str | None = Field(default=None, min_length=1, max_length=256)
    effort: str | None = Field(default=None, min_length=1, max_length=32)


class LaneStartInput(AgentChoice):
    bead: BeadLocator


def _lane_start(runtime: Runtime, inp: LaneStartInput) -> LaneStarted:
    project_id, bead_id, ref = inp.bead.resolve(runtime)
    result = _owner_call(
        runtime.v2_run_for_bead,
        {"project": project_id, "bead": bead_id, "bead_ref": ref},
        reference=ref,
        backend=inp.backend,
        model=inp.model,
        reasoning_effort=inp.effort,
    )
    lane = result.get("lane") if isinstance(result.get("lane"), Mapping) else {}
    return _lane_started(project_id, str(lane.get("bead") or bead_id), lane, result)


# --------------------------------------------------------------- actions


_JOB = "sinnix://jobs/41"

ACTIONS: tuple[Action, ...] = (
    Action(
        name="jobs.list",
        family=VerbFamily.QUERY,
        owner="systemd-jobs",
        summary="List queued jobs (pueue tasks) newest first, optionally for one project.",
        Input=ListInput,
        Output=JobPage,
        handler=_list,
        principals=ALL_PRINCIPALS,
        resource_kinds=("job",),
        affordances=("jobs.get", "jobs.logs", "jobs.wait", "jobs.cancel"),
        aliases=("queue", "pueue status", "running jobs", "tasks"),
        examples=(
            Example(title="Newest 20 jobs", input={"limit": 20}),
            Example(
                title="One project's jobs", input={"project": {"project": "sinnix"}}
            ),
        ),
    ),
    Action(
        name="jobs.get",
        family=VerbFamily.GET,
        owner="systemd-jobs",
        summary="One job's state and bead binding, with its log range or typed result on request.",
        Input=GetInput,
        Output=JobDetail,
        handler=_get,
        principals=ALL_PRINCIPALS,
        resource_kinds=("job",),
        affordances=("jobs.logs", "jobs.wait", "jobs.cancel", "jobs.retry"),
        aliases=("job status", "job result", "job output", "phase"),
        examples=(
            Example(title="Job summary", input={"target": {"job_id": 41}}),
            Example(
                title="Typed result",
                input={"target": {"ref": _JOB}, "projection": "result"},
            ),
        ),
    ),
    Action(
        name="jobs.logs",
        family=VerbFamily.GET,
        owner="systemd-jobs",
        summary="A byte range of a job's bounded log (workload output, then the wrapper's stderr).",
        Input=LogsInput,
        Output=JobLog,
        handler=_logs,
        principals=ALL_PRINCIPALS,
        resource_kinds=("job",),
        affordances=("jobs.get", "jobs.wait"),
        aliases=("job log", "tail", "output", "stdout"),
        examples=(
            Example(title="First 64 KB of a log", input={"target": {"job_id": 41}}),
            Example(
                title="Continue from an offset",
                input={"target": {"ref": _JOB}, "offset": 64_000, "max_bytes": 64_000},
            ),
        ),
    ),
    Action(
        name="jobs.wait",
        family=VerbFamily.WAIT,
        owner="systemd-jobs",
        summary="Block until one job reaches a terminal phase or the bounded timeout passes.",
        Input=JobWaitInput,
        Output=JobWait,
        handler=_wait,
        principals=ALL_PRINCIPALS,
        resource_kinds=("job",),
        affordances=("jobs.get", "jobs.logs", "jobs.cancel"),
        aliases=("wait for job", "block", "until done"),
        documentation="The wait runs in a worker thread; cancelling the MCP request abandons it without stopping the job.",
        examples=(
            Example(
                title="Wait a minute",
                input={"target": {"job_id": 41}, "timeout_seconds": 60},
            ),
        ),
    ),
    Action(
        name="jobs.cancel",
        family=VerbFamily.OPERATE,
        owner="systemd-jobs",
        summary="Kill one job (or drop it from the queue) and reap its scope's cgroup.",
        Input=CancelInput,
        Output=CancelResult,
        handler=_cancel,
        principals=CONTROL_OPERATOR,
        resource_kinds=("job",),
        affordances=("jobs.get", "jobs.logs", "jobs.retry"),
        aliases=("kill", "stop job", "abort"),
        supports_precondition=True,
        documentation="Pass expected_phase to refuse when the job already moved on. Survivors lists PIDs that outlived the reap.",
        examples=(
            Example(
                title="Cancel a running job",
                input={
                    "target": {"job_id": 41},
                    "expected_phase": "running",
                    "idempotency_key": "cancel-41",
                },
            ),
        ),
    ),
    Action(
        name="jobs.retry",
        family=VerbFamily.OPERATE,
        owner="systemd-jobs",
        summary="Re-run a terminal job in place with the same launch input and id (pueue restart).",
        Input=RetryInput,
        Output=JobView,
        handler=_retry,
        principals=CONTROL_OPERATOR,
        resource_kinds=("job",),
        affordances=("jobs.wait", "jobs.get"),
        aliases=("restart", "rerun", "requeue"),
        examples=(
            Example(
                title="Retry job 41",
                input={"target": {"job_id": 41}, "idempotency_key": "retry-41"},
            ),
        ),
    ),
    Action(
        name="operations.run",
        family=VerbFamily.RUN,
        owner="systemd-jobs",
        summary="Queue one project-declared operation in its declared pool on the root or a worktree.",
        Input=OperationRunInput,
        Output=JobView,
        handler=_run_operation,
        principals=CONTROL_OPERATOR,
        resource_kinds=("project", "checkout", "job"),
        affordances=("jobs.wait", "jobs.logs", "jobs.get", "jobs.cancel"),
        aliases=("agentctl job start", "run check", "run lint", "verify", "build"),
        examples=(
            Example(
                title="Run sinnix check",
                input={
                    "checkout": {"project": "sinnix"},
                    "operation": "check",
                    "idempotency_key": "check-1",
                },
            ),
            Example(
                title="Run on a worktree",
                input={
                    "checkout": {"path": "/realm/worktrees/sinnix-example"},
                    "operation": "lint",
                    "idempotency_key": "lint-worktree-1",
                },
            ),
        ),
    ),
    Action(
        name="shell.run",
        family=VerbFamily.RUN,
        owner="systemd-jobs",
        summary="Queue one argv in the interactive pool inside a checkout's declared environment.",
        Input=ShellRunInput,
        Output=JobView,
        handler=_run_shell,
        principals=OPERATOR_ONLY,
        resource_kinds=("project", "checkout", "job"),
        affordances=("jobs.wait", "jobs.logs", "jobs.cancel"),
        aliases=("exec", "command", "bash", "run command"),
        documentation="cwd is confined to the checkout; the job's log carries the output.",
        examples=(
            Example(
                title="git status in sinnix",
                input={
                    "checkout": {"project": "sinnix"},
                    "argv": ["git", "status", "--short"],
                    "timeout_seconds": 300,
                    "idempotency_key": "status-1",
                },
            ),
        ),
    ),
    Action(
        name="agent.for_bead",
        family=VerbFamily.RUN,
        owner="systemd-jobs",
        summary="Start a lane for one bead: compile the prompt, create the worktree, queue the agent.",
        Input=LaneStartInput,
        Output=LaneStarted,
        handler=_lane_start,
        principals=CONTROL_OPERATOR,
        resource_kinds=("project", "bead", "job"),
        affordances=("jobs.wait", "jobs.logs", "jobs.cancel"),
        aliases=("lane start", "dispatch", "agentctl lane start", "work on bead"),
        documentation="backend, model and effort default to the bead's model policy. A bead that already has a worktree is refused with conflict.",
        examples=(
            Example(
                title="Start a lane",
                input={
                    "bead": {"id": "sinnix-abc1"},
                    "idempotency_key": "lane-sinnix-abc1",
                },
            ),
            Example(
                title="Pin the agent",
                input={
                    "bead": {"ref": "sinnix://projects/sinnix/beads/sinnix-abc1"},
                    "backend": "codex",
                    "model": "gpt-5.6-terra",
                    "effort": "high",
                    "idempotency_key": "lane-sinnix-abc1-codex",
                },
            ),
        ),
    ),
)
