"""Jobs: one pueue task per launch, and the artifacts pueue has no notion of.

A job is a pueue task in the descriptor's pool with label
``<project>:<operation>``. Its id is the pueue task id; pueue's state is the
job's state. agentctl adds only the launch input `agentctl-run` consumes
(argv, environment, timeout, artifact paths) and reads the bounded log and
typed result back by the launch reference embedded in the task's command.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from . import pueue
from .config import Config
from .projects import ProjectAdapter, ProjectOperation
from .pueue import PueueError, Task
from .run import (
    CANCELLED_EXIT_CODE,
    MAX_LOG_BYTES,
    MAX_RESULT_BYTES,
    REFUSED_EXIT_CODE,
    SLOT_OCCUPIED_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    VANISHED_EXIT_CODE,
    Outcome,
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
_RESULT_KINDS = {"exit": "exit", "json": "json", "pytest": "pytest"}
# The label kinds under which a batch queues agents rather than declared operations.
AGENT_OPERATIONS = frozenset({"worker", "resume", "integrate", "review"})
# How long a cancel waits for the wrapper to record `cancelled` after its
# unit is stopped before pueue kills the wrapper outright.
CANCEL_SETTLE_SECONDS = 15.0
CANCEL_POLL_SECONDS = 0.5


class JobError(RuntimeError):
    """A launch or read that agentctl itself refuses; pueue's own refusals are PueueError."""


def label_for(project_id: str, operation: str) -> str:
    return f"{project_id}:{operation}"


def _reference(label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "job"
    return f"{safe}-{uuid.uuid4().hex[:8]}"


def _write_private(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)


def _git(path: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *arguments],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise JobError(f"could not read Git tree for {path}") from error
    if completed.returncode != 0:
        raise JobError(completed.stderr.strip() or "could not read Git tree")
    return completed.stdout.strip()


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
    after: Sequence[int] = (),
    stashed: bool = False,
    unit_properties: Sequence[str] = (),
    tree_receipt: Mapping[str, Any] | None = None,
    environment_receipt: Mapping[str, str] | None = None,
    binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the launch input, add the pueue task, return the job view.

    ``binding`` is what the caller ties the task to (``beads``, ``run_id``);
    it is stored as written and read back on ``job get``.
    """
    reference = _reference(label)
    log_path = config.jobs_dir / f"{reference}.log"
    launch: dict[str, Any] = {
        "job_id": reference,
        "project_id": project.project_id,
        "operation": operation,
        "pool": group,
        "kind": kind,
        "label": label,
        "argv": list(argv),
        "environment": dict(environment),
        "working_directory": str(working_directory),
        "timeout_seconds": timeout_seconds,
        "result_kind": result_kind,
        "log_path": str(log_path),
        "event_spool_path": str(config.event_spool),
    }
    if unit_properties:
        launch["scope_properties"] = list(unit_properties)
    if tree_receipt is not None:
        launch["tree_receipt"] = dict(tree_receipt)
    if environment_receipt is not None:
        launch["environment_receipt"] = dict(environment_receipt)
    if binding:
        launch["binding"] = dict(binding)
    if result_kind != "exit":
        launch["result_path"] = str(config.jobs_dir / f"{reference}.result")
    input_path = config.inputs_dir / f"{reference}.json"
    _write_private(
        input_path, json.dumps(launch, sort_keys=True, separators=(",", ":")).encode()
    )
    try:
        task_id = pueue.add(
            group=group,
            label=label,
            command=(QUEUE_RUN_EXECUTABLE, str(input_path)),
            working_directory=working_directory,
            after=after,
            stashed=stashed,
        )
    except PueueError:
        input_path.unlink(missing_ok=True)
        raise
    # The task id goes back into the input so its artifacts can be found
    # after pueue has forgotten the task.
    launch["queue_task_id"] = task_id
    _write_private(
        input_path, json.dumps(launch, sort_keys=True, separators=(",", ":")).encode()
    )
    task = pueue.task(task_id)
    return job_view(task) if task is not None else {"job_id": task_id, "label": label}


def start_operation(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    *,
    workspace: Path | None = None,
    extra_argv: Sequence[str] = (),
) -> dict[str, Any]:
    """Launch a declared operation on the project root or a worktree of it."""
    return _start_operation(
        config,
        project,
        operation,
        workspace=workspace,
        extra_argv=extra_argv,
        stack=(),
    )


def _start_operation(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    *,
    workspace: Path | None,
    extra_argv: Sequence[str],
    stack: tuple[str, ...],
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
    if operation.cache == "tree+environment":
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
        result_kind=_RESULT_KINDS[operation.result],
        environment=environment,
        after=dependency_ids,
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
    if operation.schedule is None:
        raise JobError(f"{project.project_id}.{operation.name} declares no schedule")
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


def _task(task_id: int) -> Task:
    task = pueue.task(task_id)
    if task is None:
        raise JobError(f"pueue has no task {task_id}")
    return task


def get_job(task_id: int, config: Config | None = None) -> dict[str, Any]:
    task = _task(task_id)
    view = job_view(task)
    binding = (_launch_input(config, task) or {}).get("binding") if config else None
    return {**view, "binding": binding} if binding else view


def _artifact(config: Config, task: Task, suffix: str) -> Path | None:
    """Where a task's log or result lands, when the task owns that path.

    The launch input declares its own paths; a task whose input agentctl wrote
    keeps them under the state directory, and one written by another repository
    keeps them in that checkout. A path outside both belongs to someone else
    and is not this task's artifact to publish.
    """
    declared = (_launch_input(config, task) or {}).get(
        {".log": "log_path", ".result": "result_path"}[suffix]
    )
    if isinstance(declared, str) and declared:
        path = Path(declared)
        return path if _task_owned(config, task, path) else None
    reference = launch_reference(task)
    return config.jobs_dir / f"{reference}{suffix}" if reference else None


def logs(config: Config, task_id: int) -> str:
    """The command's bounded log; pueue's own capture holds the wrapper's stderr."""
    task = _task(task_id)
    path = _artifact(config, task, ".log")
    raw = read_bounded(path, MAX_LOG_BYTES) if path is not None else None
    text = raw.decode("utf-8", "replace") if raw else ""
    wrapper = pueue.log(task_id)
    if wrapper.strip():
        text = f"{text}\n[wrapper]\n{wrapper}" if text else wrapper
    return text


def result(config: Config, task_id: int) -> dict[str, Any]:
    """The typed result artifact, or the exit status when the operation declares none."""
    task = _task(task_id)
    view = job_view(task)
    path = _artifact(config, task, ".result")
    raw = read_bounded(path, MAX_RESULT_BYTES + 1) if path is not None else None
    if raw is None:
        return {**view, "kind": "exit", "value": None}
    if len(raw) > MAX_RESULT_BYTES:
        raise JobError(
            f"result artifact for task {task_id} exceeds {MAX_RESULT_BYTES} bytes"
        )
    text = raw.decode("utf-8", "replace")
    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError:
        value = text
    return {**view, "kind": "artifact", "value": value, **_outcome(config, task)}


def _outcome(config: Config, task: Task) -> dict[str, Any]:
    """The wrapper's own record of how the run ended, when it left one."""
    log = _artifact(config, task, ".log")
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
            timeout=30,
            env=systemd_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def cancel(
    config: Config,
    task_id: int,
    *,
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
    task = _task(task_id)
    view = job_view(task)
    if task.terminal:
        return {**view, "state": "terminal", "unit": None}
    if task.started_at is None:
        try:
            pueue.remove([task_id])
        except PueueError:
            task = _task(task_id)
        else:
            removed = _unlink_all(_own_artifacts(config, task))
            return {
                **view,
                "phase": "cancelled",
                "terminal": True,
                "state": "removed",
                "unit": None,
                "removed": removed,
            }
    unit = unit_of(task)
    log = _artifact(config, task, ".log")
    if log is not None:
        marker = cancel_marker_for(log)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("")
    if unit is not None:
        subprocess.run(
            ["systemctl", "--user", "stop", unit],
            capture_output=True,
            check=False,
            timeout=60,
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


def _own_artifacts(config: Config, task: Task) -> list[Path]:
    paths: list[Path] = []
    for suffix in (".log", ".result"):
        artifact = _artifact(config, task, suffix)
        if artifact is not None:
            paths.append(artifact)
    log = _artifact(config, task, ".log")
    if log is not None:
        paths.extend((cancel_marker_for(log), outcome_path_for(log)))
    launch_input = launch_input_path(task)
    if launch_input is not None and _task_owned(config, task, launch_input):
        paths.append(launch_input)
    return paths


def clean(config: Config, task_id: int) -> dict[str, Any]:
    """Delete a terminal task and its artifacts. Ownership, never age.

    A task pueue no longer knows is cleaned by the artifacts its launch
    input under the state directory still names.
    """
    task = pueue.task(task_id)
    if task is None:
        removed = _unlink_all(_orphaned_artifacts(config, task_id))
        if not removed:
            raise JobError(f"pueue has no task {task_id}")
        return {"job_id": task_id, "cleaned": True, "removed": removed}
    if not task.terminal:
        raise JobError(
            f"task {task_id} is still {task.status.lower()}; cancel it first"
        )
    removed = _unlink_all(_own_artifacts(config, task))
    pueue.remove([task_id])
    return {**job_view(task), "cleaned": True, "removed": removed}


def _orphaned_artifacts(config: Config, task_id: int) -> list[Path]:
    """The artifacts of the launch input under inputs/ that names ``task_id``."""
    if not config.inputs_dir.is_dir():
        return []
    for input_path in sorted(config.inputs_dir.glob("*.json")):
        raw = read_bounded(input_path, MAX_LAUNCH_INPUT_BYTES)
        try:
            value = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or value.get("queue_task_id") != task_id:
            continue
        paths = [input_path]
        for key in ("log_path", "result_path"):
            declared = value.get(key)
            if isinstance(declared, str) and declared:
                path = Path(declared)
                if path.resolve().is_relative_to(config.state_dir.resolve()):
                    paths.append(path)
        log = value.get("log_path")
        if isinstance(log, str) and log:
            paths.extend((cancel_marker_for(log), outcome_path_for(log)))
        return paths
    return []


def clean_terminal(config: Config) -> list[dict[str, Any]]:
    """`clean` for every terminal task that ran the wrapper."""
    return [
        clean(config, task.task_id)
        for task in sorted(pueue.tasks().values(), key=lambda item: item.task_id)
        if task.terminal and launch_input_path(task) is not None
    ]


# State under the state directory that no verb reads.
DAEMON_ERA_PATHS = (
    "active-jobs.json",
    "schedules.json",
    "logs",
    "results",
    "jobs-archive",
    "active-jobs.lock",
    "admission.json",
    "capacity.json",
    "envelopes.json",
    "leases",
    "locks",
    "packet-sagas",
    "plans",
    "readiness",
    "retry-prompts",
    "unreleased-service-leases.json",
    "unreleased-service-leases.lock",
    "workspaces",
    "handoffs",
    "harvest-packets",
    "job-dirs",
    "native",
    "task-outcomes",
)
DAEMON_ERA_GLOBS = ("task-*.lock", "jobs/*.log.pgid")


def clean_daemon_era(config: Config) -> dict[str, Any]:
    """Delete the daemon-era subtrees under the state directory; idempotent."""
    root = config.state_dir
    candidates = [root / name for name in DAEMON_ERA_PATHS]
    for pattern in DAEMON_ERA_GLOBS:
        candidates.extend(sorted(root.glob(pattern)))
    removed: list[str] = []
    for path in candidates:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            continue
        removed.append(str(path))
    return {"state_dir": str(root), "removed": removed}


def retry(task_id: int) -> dict[str, Any]:
    """pueue's in-place restart: the same launch input runs again under the same id."""
    task = _task(task_id)
    if not task.terminal:
        raise JobError(f"task {task_id} is still {task.status.lower()}")
    pueue.restart(task_id)
    return get_job(task_id)


def wait(task_id: int, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    task = _task(task_id)
    if task.terminal:
        return job_view(task)
    remaining = max(deadline - time.monotonic(), 1.0)
    try:
        final = pueue.wait(task_id, timeout_seconds=remaining)
    except PueueError as error:
        current = pueue.task(task_id)
        if current is None:
            raise
        return {**job_view(current), "wait_timed_out": True, "detail": str(error)}
    return job_view(final)
