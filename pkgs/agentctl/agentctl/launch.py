"""Jobs: one pueue task per launch, and the artifacts pueue has no notion of.

A job is a pueue task in the descriptor's pool with label
``<project>:<operation>``. Its id is the pueue task id; pueue's state is the
job's state. agentctl adds only the launch input `agentctl-run` consumes
(argv, environment, timeout, artifact paths) and reads bounded views of the complete log and
typed result back by the launch reference embedded in the task's command.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from . import artifacts, gitcmd, manifest, pueue
from .config import Config
from .launch_input import scratch_path, write_input
from .limits import CALL_TIMEOUT_SECONDS, SHORT_ID, SYSTEMCTL_TIMEOUT_SECONDS
from .projects import ProjectAdapter, ProjectOperation
from .pueue import PueueError, PueueGroupError, PueueTimeout, Task
from .run import (
    CANCELLED_EXIT_CODE,
    MAX_LOG_BYTES,
    MAX_RESULT_BYTES,
    REFUSED_EXIT_CODE,
    SLOT_OCCUPIED_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    VANISHED_EXIT_CODE,
    Outcome,
    append_event,
    cancel_marker_for,
    outcome_path_for,
    systemd_environment,
    unit_for,
    unit_pool,
)

QUEUE_RUN_EXECUTABLE = "agentctl-run"
# A launch input carries argv and a resolved environment; the largest this
# workstation has queued is 21 KB. The bound is what keeps a task from naming
# an arbitrarily large file and having agentctl read it.
MAX_LAUNCH_INPUT_BYTES = 1_048_576
# The label kinds under which a batch queues agents rather than declared operations.
AGENT_OPERATIONS = frozenset({"worker", "resume", "integrate", "review"})
# A previous runtime used this marker to stash tasks for cross-pool exclusion.
# New launches never write it. It remains only so one bounded retirement pass
# can identify those historical holds without touching ordinary stashes.
HOLD_REASON = "pool-exclusivity"
# How long a wait blocks on one task id before re-reading which id the job
# it waits for is at.
WAIT_SLICE_SECONDS = 5.0
# How long a cancel waits for the wrapper to record `cancelled` after its
# unit is stopped before pueue kills the wrapper outright.
CANCEL_SETTLE_SECONDS = 15.0
CANCEL_POLL_SECONDS = 0.5
MAX_SNAPSHOT_ROWS = 100
MAX_SNAPSHOT_TEXT = 256


class JobError(RuntimeError):
    """A launch or read that agentctl itself refuses; pueue's own refusals are PueueError."""


class EnqueueUncertain(JobError):
    """Pueue may have accepted a launch whose acknowledgement was lost."""

    def __init__(self, reference: str, error: PueueError) -> None:
        self.reference = reference
        self.error = error
        super().__init__(f"pueue acceptance is unknown for launch {reference}: {error}")


def label_for(project_id: str, operation: str) -> str:
    return f"{project_id}:{operation}"


# A reference names one file under inputs/, so it is a single path component
# in the characters a sanitised label leaves.
REFERENCE = re.compile(r"^[A-Za-z0-9._-]+$")


def _reference(label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "job"
    return f"{safe}-{uuid.uuid4().hex[:SHORT_ID]}"


def _git(path: Path, *arguments: str) -> str:
    return gitcmd.git(path, *arguments, error=JobError)


def _tree_receipt(path: Path) -> dict[str, Any]:
    head = _git(path, "rev-parse", "HEAD")
    tree = _git(path, "rev-parse", "HEAD^{tree}")
    dirty = bool(_git(path, "status", "--porcelain=v1", "--untracked-files=all"))
    return {"head": head, "tree": tree, "dirty": dirty}


def _environment_receipt(
    project: ProjectAdapter,
    operation: ProjectOperation,
    environment: Mapping[str, str],
    extra_argv: Sequence[str] = (),
) -> dict[str, str]:
    payload = {
        "descriptor": project.digest,
        "kind": project.environment.kind,
        "command": list(project.environment.command),
        "operation": operation.name,
        "argv": [*operation.command, *extra_argv],
        "environment": sorted(environment.items()),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {"digest": "sha256:" + hashlib.sha256(encoded).hexdigest()}


def _launch_input(config: Config, task: Task) -> dict[str, Any] | None:
    path = launch_input_path(task)
    if path is None or not _task_owned(config, task, path):
        return None
    raw = read_bounded(path, MAX_LAUNCH_INPUT_BYTES)
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _matching_task(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    working_directory: Path,
    tree_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, str],
) -> Task | None:
    label = label_for(project.project_id, operation.name)
    for task in sorted(pueue.tasks().values(), key=lambda item: item.task_id):
        if task.label != label:
            continue
        launch_input = _launch_input(config, task)
        if launch_input is None:
            continue
        if (
            launch_input.get("working_directory") != str(working_directory)
            or launch_input.get("tree_receipt") != dict(tree_receipt)
            or launch_input.get("environment_receipt") != dict(environment_receipt)
        ):
            continue
        if not task.terminal or task.succeeded:
            return task
    return None


def enqueue(
    config: Config,
    *,
    project: ProjectAdapter,
    operation: str,
    label: str,
    group: str,
    argv: Sequence[str],
    working_directory: Path,
    timeout_seconds: int,
    result_kind: str,
    environment: Mapping[str, str],
    kind: str = "declared-operation",
    scratch: str = "none",
    after: Sequence[int] = (),
    stashed: bool = False,
    unit_properties: Sequence[str] = (),
    tree_receipt: Mapping[str, Any] | None = None,
    environment_receipt: Mapping[str, str] | None = None,
    binding: Mapping[str, Any] | None = None,
    reference: str | None = None,
    before_enqueue: Callable[[str], None] | None = None,
    owner_request_key: str | None = None,
    request_digest: str | None = None,
) -> dict[str, Any]:
    """Write the launch input, add the pueue task, return the job view.

    ``binding`` is what the caller ties the task to (``beads``, ``run_id``);
    it is stored as written and read back on ``job get``. ``scratch`` names
    the tier of the job-owned directory the wrapper creates and removes.
    """
    reference = reference or _reference(label)
    if not REFERENCE.fullmatch(reference):
        raise JobError(f"invalid launch reference: {reference!r}")
    log_path = config.jobs_dir / f"{reference}.log"
    environment = dict(environment)
    if config.config_path is not None:
        # A queued task calls agentctl again (`batch result`, `batch land`);
        # without the config it read the default one and answers about another
        # state directory.
        environment["AGENTCTL_CONFIG"] = str(config.config_path)
    launch: dict[str, Any] = {
        "job_id": reference,
        "project_id": project.project_id,
        "operation": operation,
        "pool": group,
        "kind": kind,
        "label": label,
        "argv": list(argv),
        "environment": environment,
        "working_directory": str(working_directory),
        "timeout_seconds": timeout_seconds,
        "result_kind": result_kind,
        "log_path": str(log_path),
        "event_spool_path": str(config.event_spool),
    }
    if owner_request_key is not None:
        launch["owner_request_key"] = owner_request_key
        launch["request_digest"] = request_digest
    if unit_properties:
        launch["unit_properties"] = list(unit_properties)
    if tree_receipt is not None:
        launch["tree_receipt"] = dict(tree_receipt)
    if environment_receipt is not None:
        launch["environment_receipt"] = dict(environment_receipt)
    if binding:
        launch["binding"] = dict(binding)
    scratch_dir = scratch_path(scratch, reference)
    if scratch_dir is not None:
        launch["scratch"] = {"kind": scratch, "path": str(scratch_dir)}
    if result_kind != "exit":
        launch["result_path"] = str(config.jobs_dir / f"{reference}.result")
    input_path = config.inputs_dir / f"{reference}.json"
    write_input(input_path, launch)
    if before_enqueue is not None:
        before_enqueue(reference)
    try:
        task_id = pueue.add(
            group=group,
            label=label,
            command=(QUEUE_RUN_EXECUTABLE, str(input_path)),
            working_directory=working_directory,
            after=after,
            stashed=stashed,
        )
    except PueueGroupError:
        # `pueue add` checks the live group catalog before raising this typed
        # error, so no task could have been admitted under the missing group.
        if not (owner_request_key is not None and after):
            input_path.unlink(missing_ok=True)
        raise
    except PueueError as error:
        # The daemon can accept a task before its client loses the response.
        # Keep the input so a caller can reconcile its exact launch reference
        # against pueue before trying to submit another task.
        raise EnqueueUncertain(reference, error) from error
    # The task id goes back into the input so its artifacts can be found
    # after pueue has forgotten the task.
    launch["queue_task_id"] = task_id
    write_input(input_path, launch)
    task = pueue.task(task_id)
    return (
        job_view(task)
        if task is not None
        else {"job_id": task_id, "label": label, "reference": reference}
    )


def retire_legacy_holds(
    config: Config, latest_events: Mapping[int, Mapping[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Retire only verified, still-stashed holds made by the old policy.

    A launch marker alone is deliberately insufficient: it survives ordinary
    task transitions and could belong to an operator or external stash. The
    event stream must say that its latest record is an unresolved ``held``.
    Terminal tasks are observations only, never candidates for enqueue.
    """
    try:
        tasks = pueue.tasks()
    except PueueError as error:
        return {"retired": [], "ambiguous": [{"error": str(error)}], "skipped": []}
    retired: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for task in sorted(tasks.values(), key=lambda item: item.task_id):
        launch_input = _launch_input(config, task)
        hold = launch_input.get("hold") if launch_input else None
        if not isinstance(hold, Mapping) or hold.get("reason") != HOLD_REASON:
            continue
        row = {"task_id": task.task_id, "label": task.label, "pool": task.group}
        if task.terminal:
            skipped.append({**row, "reason": "terminal"})
            continue
        event = latest_events.get(task.task_id)
        if not isinstance(event, Mapping) or event.get("action") != "held":
            ambiguous.append({**row, "reason": "no-unresolved-hold-event"})
            continue
        reference = launch_input.get("job_id")
        event_reference = event.get("job_id", event.get("reference"))
        same_reference = isinstance(reference, str) and reference == event_reference
        # Old held events did not carry a reference. Their hold timestamp is
        # copied exactly from the launch marker; with the original task id it
        # is the only safe corroboration available after an upgrade.
        event_held_at = event.get("held_at")
        marker_held_at = hold.get("held_at")
        same_legacy_marker = (
            event_reference is None
            and isinstance(event_held_at, str)
            and bool(event_held_at)
            and event_held_at == marker_held_at
            and launch_input.get("queue_task_id") == task.task_id
        )
        if not (same_reference or same_legacy_marker):
            ambiguous.append({**row, "reason": "unverified-hold-identity"})
            continue
        if task.status != "Stashed":
            ambiguous.append({**row, "reason": f"status-{task.status.lower()}"})
            continue
        try:
            pueue.enqueue(task.task_id)
        except PueueError as error:
            ambiguous.append({**row, "reason": "enqueue-failed", "error": str(error)})
            continue
        retired.append(row)
        append_event(
            config.event_spool,
            {"kind": "pool-hold", "action": "retired", **row},
        )
    return {"retired": retired, "ambiguous": ambiguous, "skipped": skipped}


def _owner_reference(key: str) -> str:
    if not isinstance(key, str) or not key or len(key) > 4096:
        raise JobError(
            "owner_request_key must be a nonempty string of at most 4096 characters"
        )
    return "request-" + hashlib.sha256(key.encode()).hexdigest()


def lookup_operation_request(
    config: Config, owner_request_key: str
) -> dict[str, Any] | None:
    """Reconcile the owner key against retained input and pueue; never submit.

    An input without a queue acknowledgement or execution evidence represents
    an uncertain submission. An absent queue row alone cannot prove rejection.
    """
    reference = _owner_reference(owner_request_key)
    path = config.inputs_dir / f"{reference}.json"
    raw = read_bounded(path, MAX_LAUNCH_INPUT_BYTES)
    if raw is None:
        if path.exists():
            raise JobError(f"unreadable owner launch {reference}")
        return None
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise JobError(f"invalid owner launch {reference}") from error
    if (
        not isinstance(document, dict)
        or document.get("owner_request_key") != owner_request_key
    ):
        raise JobError(f"owner launch identity mismatch for {reference}")
    task = find_task(pueue.tasks(), document.get("queue_task_id", -1), reference)
    if task is not None:
        return {**get_job(task.task_id, config, reference), "reused": True}
    if document.get("queue_task_id") is not None or artifacts.attempts(document):
        return {
            **get_job(document.get("queue_task_id", -1), config, reference),
            "reused": True,
        }
    raise EnqueueUncertain(
        reference, PueueError("retained launch has no acknowledged queue task")
    )


def start_operation(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    *,
    workspace: Path | None = None,
    extra_argv: Sequence[str] = (),
    owner_request_key: str | None = None,
) -> dict[str, Any]:
    """Launch an operation; an optional durable owner key prevents resubmission."""
    if owner_request_key is None:
        return _start_operation(
            config,
            project,
            operation,
            workspace=workspace,
            extra_argv=extra_argv,
            stack=(),
        )
    reference = _owner_reference(owner_request_key)
    config.inputs_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "project": project.project_id,
                "operation": operation.name,
                "workspace": str((workspace or project.root).resolve()),
                "extra_argv": list(extra_argv),
                "descriptor": project.digest,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    with (config.inputs_dir / f"{reference}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = config.inputs_dir / f"{reference}.json"
        raw = read_bounded(path, MAX_LAUNCH_INPUT_BYTES)
        if raw is not None:
            try:
                previous = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as error:
                raise JobError(f"invalid owner launch {reference}") from error
            if (
                not isinstance(previous, dict)
                or previous.get("request_digest") != fingerprint
            ):
                raise JobError(
                    "owner_request_key was already used for a different launch request"
                )
        existing = lookup_operation_request(config, owner_request_key)
        if existing is not None:
            return existing
        return _start_operation(
            config,
            project,
            operation,
            workspace=workspace,
            extra_argv=extra_argv,
            stack=(),
            owner_request_key=owner_request_key,
            request_digest=fingerprint,
        )


def _start_operation(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    *,
    workspace: Path | None,
    extra_argv: Sequence[str],
    stack: tuple[str, ...],
    owner_request_key: str | None = None,
    request_digest: str | None = None,
) -> dict[str, Any]:
    """Start one operation after its declared pueue dependencies."""
    if operation.name in stack:
        raise JobError(
            f"{project.project_id} operation dependencies contain a cycle at "
            f"{operation.name}"
        )
    working_directory = (workspace or project.root).resolve()
    if operation.checkout == "default" and working_directory != project.root:
        raise JobError(
            f"{project.project_id}.{operation.name} runs only on the project's main checkout"
        )
    if not working_directory.is_dir():
        raise JobError(f"working directory does not exist: {working_directory}")
    environment = project.environment.values()
    for key in ("AGENTCTL_PRINCIPAL", "AGENTCTL_LANE_BEAD"):
        if value := os.environ.get(key):
            environment[key] = value
    tree_receipt = None
    environment_receipt = None
    if operation.cache == "tree+environment" and owner_request_key is None:
        tree_receipt = _tree_receipt(working_directory)
        if tree_receipt["dirty"]:
            tree_receipt = None
        else:
            environment_receipt = _environment_receipt(
                project, operation, environment, extra_argv
            )
            existing = _matching_task(
                config,
                project,
                operation,
                working_directory,
                tree_receipt,
                environment_receipt,
            )
            if existing is not None:
                existing_input = _launch_input(config, existing) or {}
                return {
                    **job_view(existing),
                    "reused": True,
                    **{
                        key: existing_input[key]
                        for key in ("tree_receipt", "environment_receipt")
                        if key in existing_input
                    },
                }
    if owner_request_key is not None and operation.dependencies:
        # Persist the parent intent before any dependency can be submitted.
        # A crash here is uncertain, not permission to duplicate dependencies.
        reference = _owner_reference(owner_request_key)
        write_input(
            config.inputs_dir / f"{reference}.json",
            {
                "job_id": reference,
                "owner_request_key": owner_request_key,
                "request_digest": request_digest,
                "project_id": project.project_id,
                "operation": operation.name,
                "label": label_for(project.project_id, operation.name),
                "pool": operation.pool,
                "working_directory": str(working_directory),
                "log_path": str(config.jobs_dir / f"{reference}.log"),
                "submission": "preparing-dependencies",
            },
        )
    dependency_ids: list[int] = []
    for dependency_name in operation.dependencies:
        try:
            dependency = project.operation(dependency_name)
        except KeyError as error:
            raise JobError(
                f"{project.project_id}.{operation.name} depends on undeclared "
                f"operation {dependency_name}"
            ) from error
        started = _start_operation(
            config,
            project,
            dependency,
            workspace=workspace,
            extra_argv=(),
            stack=(*stack, operation.name),
        )
        dependency_id = started.get("job_id")
        if not isinstance(dependency_id, int):
            raise JobError(
                f"{project.project_id}.{dependency_name} did not return a task id"
            )
        dependency_ids.append(dependency_id)
    started = enqueue(
        config,
        project=project,
        operation=operation.name,
        label=label_for(project.project_id, operation.name),
        group=operation.pool,
        argv=project.environment.command_for((*operation.command, *extra_argv)),
        working_directory=working_directory,
        timeout_seconds=operation.timeout_seconds,
        result_kind=operation.result,
        environment=environment,
        scratch=operation.scratch,
        after=dependency_ids,
        reference=(
            _owner_reference(owner_request_key)
            if owner_request_key is not None
            else None
        ),
        owner_request_key=owner_request_key,
        request_digest=request_digest,
        tree_receipt=tree_receipt,
        environment_receipt=environment_receipt,
    )
    if tree_receipt is not None:
        started["tree_receipt"] = tree_receipt
    if environment_receipt is not None:
        started["environment_receipt"] = environment_receipt
    return started


def fire(
    config: Config, project: ProjectAdapter, operation: ProjectOperation
) -> dict[str, Any]:
    """A timer's launch: skipped while the same operation is still queued or running."""
    label = label_for(project.project_id, operation.name)
    active = [
        task
        for task in pueue.tasks().values()
        if task.label == label and not task.terminal
    ]
    if active:
        return {
            "fired": False,
            "label": label,
            "active": [task.task_id for task in active],
        }
    started = start_operation(config, project, operation)
    return {"fired": True, **started}


def phase_of(task: Task) -> str:
    if not task.terminal:
        return task.status.lower()
    if task.result == "Success":
        return "succeeded"
    if task.result == "Killed":
        return "cancelled"
    if task.result == "DependencyFailed":
        return "dependency-failed"
    if task.result == "FailedToSpawn":
        return "launch-failed"
    return _WRAPPER_PHASES.get(task.exit_code, "failed")


# The wrapper's own exit statuses, named as run.Outcome names them; any
# other status is the command's.
_WRAPPER_PHASES = {
    TIMEOUT_EXIT_CODE: Outcome.TIMEOUT.value,
    REFUSED_EXIT_CODE: "refused",
    CANCELLED_EXIT_CODE: Outcome.CANCELLED.value,
    VANISHED_EXIT_CODE: Outcome.VANISHED.value,
    SLOT_OCCUPIED_EXIT_CODE: Outcome.SLOT_OCCUPIED.value,
}


def launch_input_path(task: Task) -> Path | None:
    """The launch input a task's command names, or None for any other command.

    pueue records one command per task; the wrapper's is its own name and one
    absolute path, and nothing else. A command that merely contains that text
    runs a different program, and claiming its artifacts or its scope would
    reap a task that no one cancelled.
    """
    try:
        words = shlex.split(task.command)
    except ValueError:
        return None
    if len(words) != 2 or PurePosixPath(words[0]).name != QUEUE_RUN_EXECUTABLE:
        return None
    candidate = PurePosixPath(words[1])
    if not candidate.is_absolute() or candidate.suffix != ".json":
        return None
    return Path(words[1])


def _task_owned(config: Config, task: Task, path: Path) -> bool:
    """Whether a task may read this path back as one of its own artifacts.

    A task owns agentctl's state directory and the working directory pueue
    recorded for it; a launch input naming anything else is publishing another
    owner's file through `job logs`. Both sides are resolved, so neither a
    parent reference nor a symlink planted inside a root reaches outside one.
    """
    roots = [config.state_dir]
    if task.path.startswith("/"):
        roots.append(Path(task.path))
    try:
        resolved = path.resolve()
        return any(resolved.is_relative_to(root.resolve()) for root in roots)
    except OSError:
        return False


def read_bounded(path: Path, limit: int) -> bytes | None:
    """At most ``limit`` bytes of a regular file, or None for anything else.

    A launch input names its own artifact paths, so the read must survive one
    naming a device or a fifo: opening without blocking and proving the file is
    regular before reading is what keeps `job logs` from hanging on it.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        chunks: list[bytes] = []
        remaining = limit
        while remaining > 0:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    except OSError:
        return None
    finally:
        os.close(descriptor)


def launch_reference(task: Task) -> str | None:
    path = launch_input_path(task)
    return path.stem if path is not None else None


def unit_of(task: Task) -> str | None:
    """The transient service holding this task's workload.

    Derived from the queue's own record so a cancel reaches the unit after the
    wrapper is gone and after the launch input its owner wrote has been deleted.
    """
    path = launch_input_path(task)
    pool = unit_pool(task.group)
    return unit_for(path, pool) if path is not None and pool else None


def job_view(task: Task) -> dict[str, Any]:
    project, _, operation = task.label.partition(":")
    # Agent labels are <project>:<kind>:<run>[:<worker>] for a batch's agents.
    agent = operation.split(":", 1)[0] in AGENT_OPERATIONS and ":" in operation
    return {
        "job_id": task.task_id,
        "label": task.label,
        "kind": "attested-agent" if agent else "declared-operation",
        "project": project,
        "operation": operation,
        "group": task.group,
        "dependencies": list(task.dependencies),
        "phase": phase_of(task),
        "terminal": task.terminal,
        "result": task.result,
        "exit_code": task.exit_code,
        "path": task.path,
        "reference": launch_reference(task),
        "enqueued_at": task.enqueued_at,
        "started_at": task.started_at,
        "ended_at": task.ended_at,
    }


def list_jobs(project_id: str | None = None) -> list[dict[str, Any]]:
    tasks = pueue.tasks().values()
    rows = [
        job_view(task)
        for task in sorted(tasks, key=lambda item: item.task_id)
        if project_id is None or task.label.startswith(f"{project_id}:")
    ]
    return rows


def snapshot_jobs(limit: int, config: Config | None = None) -> dict[str, Any]:
    """A bounded operator projection of one Pueue status response.

    Active tasks receive the available rows first.  Terminal history stays in
    Pueue, with explicit coverage telling a caller what this view omitted.
    """
    if not 1 <= limit <= MAX_SNAPSHOT_ROWS:
        raise JobError(f"job snapshot limit must be between 1 and {MAX_SNAPSHOT_ROWS}")
    queue = pueue.status()
    groups: dict[str, dict[str, Any]] = {}
    for name, detail in queue.groups.items():
        groups[name] = {
            "status": str(detail.get("status") or ""),
            "parallel": int(detail.get("parallel_tasks") or 0),
            "running": 0,
            "queued": 0,
            "paused": 0,
            "stashed": 0,
            "terminal": 0,
            "total": 0,
        }
    active: list[Task] = []
    terminal: list[Task] = []
    for task in queue.tasks.values():
        group = groups.get(task.group)
        if group is None:
            group = groups.setdefault(
                task.group,
                {
                    "status": "",
                    "parallel": 0,
                    "running": 0,
                    "queued": 0,
                    "paused": 0,
                    "stashed": 0,
                    "terminal": 0,
                    "total": 0,
                },
            )
        group["total"] += 1
        if task.terminal:
            group["terminal"] += 1
            terminal.append(task)
        else:
            state = task.status.lower()
            if state in {"running", "queued", "paused", "stashed"}:
                group[state] += 1
            active.append(task)
    active.sort(key=lambda task: task.task_id, reverse=True)
    terminal.sort(key=lambda task: task.task_id, reverse=True)
    selected = [*active, *terminal][:limit]
    returned_active = sum(not task.terminal for task in selected)
    returned_terminal = len(selected) - returned_active
    return {
        "schema": "sinnix.agentctl.job-snapshot.v1",
        "limit": limit,
        "groups": groups,
        "jobs": [_snapshot_row(task, config) for task in selected],
        "omitted": {
            "total": len(queue.tasks) - len(selected),
            "active": len(active) - returned_active,
            "terminal": len(terminal) - returned_terminal,
        },
        "coverage": {
            "active": {"total": len(active), "returned": returned_active},
            "terminal": {"total": len(terminal), "returned": returned_terminal},
        },
        "truncated": len(queue.tasks) > len(selected),
    }


def _snapshot_row(task: Task, config: Config | None = None) -> dict[str, Any]:
    """One snapshot row with foreign queue strings bounded for transport."""
    row = job_view(task)
    if config is not None:
        row["attempt"] = _artifact_view(config, task)["attempt"]
    shortened = []
    for key in ("label", "operation", "path", "reference"):
        value = row.get(key)
        if isinstance(value, str) and len(value) > MAX_SNAPSHOT_TEXT:
            row[key] = value[: MAX_SNAPSHOT_TEXT - 1] + "…"
            shortened.append(key)
    if shortened:
        row["shortened"] = shortened
    return row


def attach_bindings(
    config: Config, rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Each row with the binding recorded in the launch input its task names.

    One queue read for the whole page, so a caller pages first and pays for
    the launch inputs of the rows it returns.
    """
    tasks = pueue.tasks()
    attached = []
    for row in rows:
        task = tasks.get(row.get("job_id"))
        binding = (_launch_input(config, task) or {}).get("binding") if task else None
        attached.append({**row, "binding": binding} if binding else dict(row))
    return attached


def _task(task_id: int) -> Task:
    task = pueue.task(task_id)
    if task is None:
        raise JobError(f"pueue has no task {task_id}")
    return task


def _read_task(config: Config, task_id: int, reference: str | None) -> Task:
    task = find_task(pueue.tasks(), task_id, reference)
    if task is not None:
        return task
    if reference is None or not REFERENCE.fullmatch(reference):
        raise JobError(
            f"pueue has no task {reference or task_id}; archived reads require a reference"
        )
    path = config.inputs_dir / f"{reference}.json"
    raw = read_bounded(path, MAX_LAUNCH_INPUT_BYTES)
    try:
        document = json.loads(raw) if raw else None
    except (ValueError, UnicodeDecodeError):
        document = None
    if not isinstance(document, dict):
        raise JobError(f"no retained launch {reference}")
    return Task(
        task_id=document.get("queue_task_id", task_id),
        label=document.get("label", ""),
        group=document.get("pool", ""),
        status="Archived",
        result=None,
        exit_code=None,
        path=document.get("working_directory", ""),
        dependencies=(),
        command=shlex.join((QUEUE_RUN_EXECUTABLE, str(path))),
    )


def _artifact_view(
    config: Config, task: Task, attempt: int | None = None
) -> dict[str, Any]:
    document = _launch_input(config, task) or {}
    reference = launch_reference(task)
    if not document.get("log_path") and reference is not None:
        # Older queue entries can outlive their input while their conventional
        # state-directory artifacts remain available by the command reference.
        document = {
            "log_path": str(config.jobs_dir / f"{reference}.log"),
            "result_path": str(config.jobs_dir / f"{reference}.result"),
        }
    records = artifacts.attempts(document) if document.get("log_path") else []
    # Retain ownership checks even for externally authored launch inputs.
    for record in records:
        record["artifacts"] = {
            key: value
            for key, value in record["artifacts"].items()
            if _task_owned(config, task, Path(value))
        }
    selected = (
        next((record for record in records if record["attempt"] == attempt), None)
        if attempt is not None
        else (records[-1] if records else None)
    )
    if attempt is not None and selected is None and not (attempt == 0 and not records):
        raise JobError(f"launch {launch_reference(task)} has no attempt {attempt}")
    return {
        "attempt": selected["attempt"] if selected else 0,
        "artifacts": selected["artifacts"] if selected else {},
        "attempts": records,
        "input_path": str(launch_input_path(task)),
    }


def get_job(
    task_id: int,
    config: Config | None = None,
    reference: str | None = None,
    *,
    attempt: int | None = None,
    attempt_offset: int = 0,
    attempt_limit: int = 100,
) -> dict[str, Any]:
    if attempt_offset < 0 or not 1 <= attempt_limit <= 100:
        raise JobError(
            "attempt_offset must be nonnegative and attempt_limit must be 1..100"
        )
    task = (
        _read_task(config, task_id, reference)
        if config
        else addressed(task_id, reference)
    )
    if config is None:
        return job_view(task)
    return _job_detail(config, task, attempt, attempt_offset, attempt_limit)


def _job_detail(
    config: Config,
    task: Task,
    attempt: int | None,
    attempt_offset: int = 0,
    attempt_limit: int = 100,
) -> dict[str, Any]:
    view = job_view(task)
    binding = (_launch_input(config, task) or {}).get("binding")
    if binding:
        view["binding"] = binding
    view.update(_artifact_view(config, task, attempt))
    receipt = _outcome(config, task, view["attempt"]).get("outcome") or {}
    records = view["attempts"]
    view["attempts"] = records[attempt_offset : attempt_offset + attempt_limit]
    view["attempt_count"] = len(records)
    view["next_attempt_offset"] = (
        attempt_offset + attempt_limit
        if attempt_offset + attempt_limit < len(records)
        else None
    )
    if receipt:
        view["outcome"] = receipt
    view["queue_present"] = task.status != "Archived"
    if task.status == "Archived":
        view.update(
            phase=(
                "succeeded"
                if receipt.get("outcome") == "success"
                else receipt.get("outcome", "unknown")
            ),
            terminal=bool(receipt),
            exit_code=receipt.get("exit_code"),
        )
    if isinstance(receipt.get("scratch"), dict):
        view["scratch"] = receipt["scratch"]
    return view


def _artifact(
    config: Config, task: Task, suffix: str, attempt: int | None = None
) -> Path | None:
    key = {".log": "log", ".result": "result"}[suffix]
    view = _artifact_view(config, task, attempt)
    declared = view["artifacts"].get(key)
    if declared is None and attempt is None:
        declared = (_launch_input(config, task) or {}).get(key + "_path")
    if isinstance(declared, str) and declared:
        path = Path(declared)
        return path.resolve() if _task_owned(config, task, path) else None
    reference = launch_reference(task)
    return (
        config.jobs_dir / f"{reference}{suffix}"
        if reference and attempt is None
        else None
    )


def read_job_artifact(
    config: Config,
    task_id: int,
    reference: str | None = None,
    *,
    attempt: int | None = None,
    artifact: str = "log",
    offset: int = 0,
    limit: int = MAX_RESULT_BYTES,
) -> dict[str, Any]:
    """A byte-addressed bounded view and canonical path to the complete artifact.

    Text decodes this page as UTF-8 with replacement; base64 preserves exact
    bytes, including characters split across byte offsets. Follow next_offset
    with the returned attempt number to remain on one invocation during retries.
    """
    task = _read_task(config, task_id, reference)
    return _read_artifact(config, task, attempt, artifact, offset, limit)


def _read_artifact(
    config: Config,
    task: Task,
    attempt: int | None,
    artifact: str,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    import base64

    if artifact not in {"log", "result", "outcome"}:
        raise JobError(f"unknown artifact {artifact!r}")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_LOG_BYTES
    ):
        raise JobError(
            f"offset must be nonnegative and limit must be 1..{MAX_LOG_BYTES}"
        )
    view = _artifact_view(config, task, attempt)
    declared = view["artifacts"].get(artifact)
    path = Path(declared).resolve() if declared else None
    raw = b""
    size = 0
    available = False
    if path is not None:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        except OSError:
            descriptor = None
        if descriptor is not None:
            try:
                status = os.fstat(descriptor)
                if stat.S_ISREG(status.st_mode):
                    size = status.st_size
                    available = True
                    os.lseek(descriptor, offset, os.SEEK_SET)
                    raw = os.read(descriptor, limit)
            finally:
                os.close(descriptor)
    next_offset = offset + len(raw)
    return {
        "reference": launch_reference(task),
        "attempt": view["attempt"],
        "artifact": artifact,
        "path": str(path) if path else None,
        "available": available,
        "offset": offset,
        "size_bytes": size,
        "returned_bytes": len(raw),
        "next_offset": next_offset if next_offset < size else None,
        "complete": available and offset == 0 and len(raw) == size,
        "text": raw.decode("utf-8", "replace"),
        "base64": base64.b64encode(raw).decode("ascii"),
    }


def task_logs(config: Config, task: Task, *, attempt: int | None = None) -> str:
    path = _artifact(config, task, ".log", attempt)
    raw = read_bounded(path, MAX_LOG_BYTES) if path is not None else None
    text = raw.decode("utf-8", "replace") if raw else ""
    # Pueue's wrapper capture belongs only to the current queue invocation.
    wrapper = (
        pueue.log(task.task_id) if attempt is None and task.status != "Archived" else ""
    )
    if wrapper.strip():
        text = f"{text}\n[wrapper]\n{wrapper}" if text else wrapper
    return text


def logs(
    config: Config,
    task_id: int,
    reference: str | None = None,
    *,
    attempt: int | None = None,
) -> str:
    return task_logs(config, _read_task(config, task_id, reference), attempt=attempt)


def result(
    config: Config,
    task_id: int,
    reference: str | None = None,
    *,
    attempt: int | None = None,
    offset: int = 0,
    limit: int = MAX_RESULT_BYTES,
) -> dict[str, Any]:
    """Bound the view only; large typed results remain complete valid artifacts."""
    task = _read_task(config, task_id, reference)
    view = _job_detail(config, task, attempt)
    page = _read_artifact(config, task, view["attempt"], "result", offset, limit)
    value: Any = None
    if page["complete"]:
        try:
            value = json.loads(page["text"])
        except json.JSONDecodeError:
            value = page["text"]
    return {
        **view,
        "kind": "artifact" if page["available"] else "exit",
        "value": value,
        "page": page,
    }


def _outcome(config: Config, task: Task, attempt: int | None = None) -> dict[str, Any]:
    log = _artifact(config, task, ".log", attempt)
    raw = read_bounded(outcome_path_for(log), 4096) if log is not None else None
    try:
        record = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        record = None
    return {"outcome": record} if isinstance(record, dict) else {}


def _unit_active(unit: str) -> bool:
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", unit],
            capture_output=True,
            check=False,
            timeout=SYSTEMCTL_TIMEOUT_SECONDS,
            env=systemd_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def cancel(
    config: Config,
    task_id: int,
    *,
    reference: str | None = None,
    expected_attempt: int | None = None,
    settle_seconds: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Optionally compare an attempt token while holding its allocation lock."""
    if expected_attempt is None:
        return _cancel(
            config,
            task_id,
            reference=reference,
            settle_seconds=settle_seconds,
            sleep=sleep,
        )
    if reference is None:
        raise JobError("expected_attempt requires a stable launch reference")
    task = addressed(task_id, reference)
    document = _launch_input(config, task) or {}
    log = document.get("log_path")
    if not log or not _task_owned(config, task, Path(log)):
        raise JobError("cannot verify the job's execution attempt")
    root = artifacts.root_for(Path(log))
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".allocation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = _artifact_view(config, task)["attempt"]
        if current != expected_attempt:
            raise JobError(
                f"execution attempt changed: expected {expected_attempt}, found {current}"
            )
        return _cancel(
            config,
            task.task_id,
            reference=reference,
            settle_seconds=settle_seconds,
            sleep=sleep,
        )


def _cancel(
    config: Config,
    task_id: int,
    *,
    reference: str | None = None,
    settle_seconds: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Make the task not run: drop it while queued, stop its unit while running.

    pueue kills the wrapper with SIGKILL, which stops nothing inside the unit
    and leaves no outcome record, so the unit is stopped first and the
    wrapper is given ``settle_seconds`` to record `cancelled` and exit on its
    own; only a wrapper still running after that is killed. `systemctl stop`
    ends the wrapper's wait with a success status, which is why the cancel
    marker is written before it: the wrapper reports `cancelled` when it
    finds one, and consumes the marker.
    """
    if settle_seconds is None:
        settle_seconds = CANCEL_SETTLE_SECONDS
    task = addressed(task_id, reference)
    task_id = task.task_id
    view = job_view(task)
    if task.terminal:
        return {**view, "state": "terminal", "unit": None}
    if task.started_at is None:
        try:
            pueue.remove([task_id])
        except PueueError:
            task = _task(task_id)
        else:
            removed = []
            return {
                **view,
                "phase": "cancelled",
                "terminal": True,
                "state": "removed",
                "unit": None,
                "removed": removed,
            }
    unit = unit_of(task)
    declared_log = (_launch_input(config, task) or {}).get("log_path")
    log = (
        Path(declared_log)
        if declared_log and _task_owned(config, task, Path(declared_log))
        else None
    )
    if log is not None:
        marker = cancel_marker_for(log)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("")
    if unit is not None:
        subprocess.run(
            ["systemctl", "--user", "stop", unit],
            capture_output=True,
            check=False,
            timeout=CALL_TIMEOUT_SECONDS,
            env=systemd_environment(),
        )
    deadline = time.monotonic() + settle_seconds
    current = pueue.task(task_id)
    while current is not None and not current.terminal:
        if time.monotonic() >= deadline:
            try:
                pueue.kill(task_id)
            except PueueError:
                pass
            current = pueue.task(task_id)
            break
        sleep(CANCEL_POLL_SECONDS)
        current = pueue.task(task_id)
    state = "failed" if unit is not None and _unit_active(unit) else "stopped"
    return {
        **(job_view(current) if current is not None else view),
        "state": state,
        "unit": unit,
        **_outcome(config, current if current is not None else task),
    }


def _unlink_all(paths: Sequence[Path]) -> list[str]:
    removed = []
    for path in paths:
        try:
            path.unlink()
            removed.append(str(path))
        except OSError:
            continue
    return removed


def clean(config: Config, task_id: int, reference: str | None = None) -> dict[str, Any]:
    """Remove a terminal queue entry; retain its launch and execution evidence."""
    if reference is not None and not REFERENCE.fullmatch(reference):
        raise JobError(f"{reference!r} is not a launch reference")
    task = _read_task(config, task_id, reference)
    if task.status != "Archived" and not task.terminal:
        raise JobError(
            f"task {task.task_id} is still {task.status.lower()}; cancel it first"
        )
    view = get_job(task.task_id, config, launch_reference(task))
    if task.status != "Archived":
        pueue.remove([task.task_id])
    log = _artifact(config, task, ".log")
    removed = _unlink_all([cancel_marker_for(log)]) if log is not None else []
    return {**view, "cleaned": True, "removed": removed, "retained": True}


def _live_run_jobs(config: Config, tasks: Mapping[int, Task]) -> set[int]:
    """Jobs a live batch still needs, including attempts predating stable references."""
    runs = [run for run in manifest.list_runs(config, strict=True) if run.live]
    run_ids = {run.run_id for run in runs}
    worktrees: set[str] = set()
    retained: set[int] = set()
    for run in runs:
        records = [*run.workers, run.landing]
        records.extend(
            record
            for key in ("verify_run", "review_verdict")
            if isinstance(record := run.landing.get(key), dict)
        )
        for record in records:
            reference = (
                record.get("pending_launch")
                or record.get("task_reference")
                or record.get("reference")
            )
            task_id = record.get("task_id", record.get("job_id"))
            task = find_task(tasks, task_id, reference)
            if task is not None:
                retained.add(task.task_id)
            retained.update(
                value
                for value in (record.get("task_ids") or [])
                if isinstance(value, int)
            )
            for key in ("worktree", "integration_worktree"):
                if isinstance(path := record.get(key), str):
                    worktrees.add(path)
    for task in tasks.values():
        written = _launch_input(config, task) or {}
        binding = written.get("binding") or {}
        label = task.label.split(":")
        batch_label = (
            len(label) >= 3
            and label[1] in AGENT_OPERATIONS | {"land"}
            and label[2] in run_ids
        )
        if task.path in worktrees or binding.get("run_id") in run_ids or batch_label:
            retained.add(task.task_id)
    return retained


def clean_terminal(config: Config) -> list[dict[str, Any]]:
    """Clean terminal wrapper jobs except those still needed by a live batch."""
    tasks = pueue.tasks()
    retained = _live_run_jobs(config, tasks)
    return [
        clean(config, task.task_id, launch_reference(task))
        for task in sorted(tasks.values(), key=lambda item: item.task_id)
        if task.terminal
        and task.task_id not in retained
        and launch_input_path(task) is not None
    ]


def retry(task_id: int, reference: str | None = None) -> dict[str, Any]:
    """pueue's in-place restart: the same launch input runs again under the same id."""
    task = addressed(task_id, reference)
    if not task.terminal:
        raise JobError(f"task {task.task_id} is still {task.status.lower()}")
    pueue.restart(task.task_id)
    return get_job(task.task_id)


def find_task(
    tasks: Mapping[int, Task], task_id: object, reference: object = None
) -> Task | None:
    """Resolve a stored job identity after pueue may have reassigned its id."""
    if isinstance(reference, str):
        return next(
            (task for task in tasks.values() if launch_reference(task) == reference),
            None,
        )
    return tasks.get(task_id) if isinstance(task_id, int) else None


def vanished(
    tasks: Mapping[int, Task], task_id: object, reference: object = None
) -> bool:
    """Whether a recorded job identity names nothing the queue holds any more.

    pueue's state is a file it can lose: after a reset its task ids start at
    zero again, so every id recorded before it names either nothing or a
    stranger's task. A record that named no task in the first place — an
    external worker, a landing not yet queued — has not vanished.
    """
    if not isinstance(task_id, int) and not isinstance(reference, str):
        return False
    return find_task(tasks, task_id, reference) is None


def addressed(task_id: int, reference: str | None = None) -> Task:
    """The task carrying this job now, whatever id the queue moved it to.

    `pueue switch` exchanges the ids of two queued tasks, so an id names a
    position in the queue and not a job. The launch reference does name one:
    pueue carries a task's command wherever it moves the task, and the
    reference is the launch input path inside that command. A caller that
    holds a reference addresses its own job; one that holds only an id
    addresses whatever the queue keeps at that position, which one read of
    that position answers.
    """
    if reference is None:
        return _task(task_id)
    task = find_task(pueue.tasks(), task_id, reference)
    if task is None:
        raise JobError(f"pueue has no task for job {reference}")
    return task


def _wait_slice(task: Task, remaining: float) -> float:
    """How long to block on one task id before proving the job still has it.

    `pueue switch` moves only a queued or stashed task, so a running task
    keeps its id until it is terminal and the whole remaining wait blocks on
    it; anything else is re-read often enough to notice the queue reordering.
    """
    if task.status == "Running":
        return max(remaining, 1.0)
    return max(min(remaining, WAIT_SLICE_SECONDS), 1.0)


def wait(
    task_id: int,
    *,
    timeout_seconds: float,
    reference: str | None = None,
) -> dict[str, Any]:
    """Block until the job is terminal, following it across queue task ids.

    ``reference`` is the launch reference the caller started; without one the
    job is the one the queue holds at ``task_id`` when the wait begins. A
    caller that followed the id alone would wake on a stranger's task, or
    sleep past the end of its own.
    """
    deadline = time.monotonic() + timeout_seconds
    if reference is None:
        reference = launch_reference(_task(task_id))
    task = addressed(task_id, reference)
    detail: str | None = None
    while True:
        if task.terminal:
            return job_view(task)
        remaining = deadline - time.monotonic()
        if remaining <= 0 or detail is not None:
            view = {**job_view(task), "wait_timed_out": True}
            return view if detail is None else {**view, "detail": detail}
        blocking = _wait_slice(task, remaining)
        try:
            pueue.wait(task.task_id, timeout_seconds=blocking)
        except PueueTimeout:
            # A slice covering the whole remaining wait is the caller's own
            # timeout; a shorter one expired only to re-read the queue.
            if blocking >= remaining:
                return {**job_view(task), "wait_timed_out": True}
        except PueueError as error:
            detail = str(error)
        task = addressed(task_id, reference)
