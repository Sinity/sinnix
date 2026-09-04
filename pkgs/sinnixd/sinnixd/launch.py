"""Jobs: one pueue task per launch, and the artifacts pueue has no notion of.

A job is a pueue task in the descriptor's pool with label
``<project>:<operation>``. Its id is the pueue task id; pueue's state is the
job's state. agentctl adds only the launch input `sinnixd-queue-run` consumes
(argv, environment, timeout, artifact paths) and reads the bounded log and
typed result back by the launch reference embedded in the task's command.
"""

from __future__ import annotations

import json
import os
import re
import signal
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import pueue
from .config import Config
from .projects import ProjectAdapter, ProjectOperation
from .pueue import PueueError, Task
from .queue_run import (
    MAX_LOG_BYTES,
    MAX_RESULT_BYTES,
    REFUSED_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
)

QUEUE_RUN_EXECUTABLE = "sinnixd-queue-run"
_LAUNCH_REFERENCE = re.compile(
    r"sinnixd-queue-run (?P<path>\S+/inputs/(?P<ref>[A-Za-z0-9._-]+)\.json)"
)
_RESULT_KINDS = {"exit": "exit", "json": "json", "pytest": "pytest"}


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
) -> dict[str, Any]:
    """Write the launch input, add the pueue task, return the job view."""
    reference = _reference(label)
    log_path = config.jobs_dir / f"{reference}.log"
    launch: dict[str, Any] = {
        "job_id": reference,
        "project_id": project.project_id,
        "operation": operation,
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
        )
    except PueueError:
        input_path.unlink(missing_ok=True)
        raise
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
    working_directory = (workspace or project.root).resolve()
    if operation.checkout == "default" and working_directory != project.root:
        raise JobError(
            f"{project.project_id}.{operation.name} runs only on the project's main checkout"
        )
    if not working_directory.is_dir():
        raise JobError(f"working directory does not exist: {working_directory}")
    environment = project.environment.values()
    for key in ("SINNIXD_PRINCIPAL", "SINNIXD_LANE_BEAD"):
        if value := os.environ.get(key):
            environment[key] = value
    return enqueue(
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
    )


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
    if task.exit_code == TIMEOUT_EXIT_CODE:
        return "timed-out"
    if task.exit_code == REFUSED_EXIT_CODE:
        return "refused"
    return "failed"


def launch_reference(task: Task) -> str | None:
    match = _LAUNCH_REFERENCE.search(task.command)
    return match.group("ref") if match else None


def job_view(task: Task) -> dict[str, Any]:
    project, _, operation = task.label.partition(":")
    # Agent labels are <project>:lane:<bead> or <project>:rebase:<bead>.
    agent = operation.split(":", 1)[0] in {"lane", "rebase"} and ":" in operation
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


def get_job(task_id: int) -> dict[str, Any]:
    return job_view(_task(task_id))


def _artifact(config: Config, task: Task, suffix: str) -> Path | None:
    reference = launch_reference(task)
    return config.jobs_dir / f"{reference}{suffix}" if reference else None


def logs(config: Config, task_id: int) -> str:
    """The command's bounded log; pueue's own capture holds the wrapper's stderr."""
    task = _task(task_id)
    path = _artifact(config, task, ".log")
    text = ""
    if path is not None:
        try:
            text = path.read_bytes()[:MAX_LOG_BYTES].decode("utf-8", "replace")
        except OSError:
            text = ""
    wrapper = pueue.log(task_id)
    if wrapper.strip():
        text = f"{text}\n[wrapper]\n{wrapper}" if text else wrapper
    return text


def result(config: Config, task_id: int) -> dict[str, Any]:
    """The typed result artifact, or the exit status when the operation declares none."""
    task = _task(task_id)
    view = job_view(task)
    path = _artifact(config, task, ".result")
    if path is None or not path.exists():
        return {**view, "kind": "exit", "value": None}
    raw = path.read_bytes()
    if len(raw) > MAX_RESULT_BYTES:
        raise JobError(
            f"result artifact for task {task_id} exceeds {MAX_RESULT_BYTES} bytes"
        )
    text = raw.decode("utf-8", "replace")
    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError:
        value = text
    return {**view, "kind": "artifact", "value": value}


def cancel(config: Config, task_id: int) -> dict[str, Any]:
    """Ask pueue to kill the task, then reap the process group the wrapper led.

    pueue kills with SIGKILL, which the wrapper cannot catch; the command's
    own session survives unless someone signals the group it recorded.
    """
    task = _task(task_id)
    pueue.kill(task_id)
    group_path = _artifact(config, task, ".log.pgid")
    if group_path is not None:
        try:
            pgid = int(group_path.read_text().strip())
            os.killpg(pgid, signal.SIGTERM)
        except (OSError, ValueError):
            pass
    return get_job(task_id)


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
