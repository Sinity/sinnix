"""Stable-identity job queries over native queue and retained invocation artifacts.

Reads preserve selected attempts, bounded/redacted bytes and historical job
identity. Waiting observes completion; it never changes admission or cancels.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from sinnix_lib.secrets import mask_secret_values, masked_window, secret_values

from . import artifacts, cgroups, pueue
from .config import Config
from .launch_input import secret_environment
from .pueue import PueueError, PueueTimeout, Task
from .run import (
    CANCELLED_EXIT_CODE,
    MAX_LOG_BYTES,
    MAX_RESULT_BYTES,
    REFUSED_EXIT_CODE,
    SLOT_OCCUPIED_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    VANISHED_EXIT_CODE,
    Outcome,
    outcome_path_for,
    unit_for,
    unit_pool,
)

QUEUE_RUN_EXECUTABLE = "agentctl-run"
# A launch input carries argv and a resolved environment; the largest this
# workstation has queued is 21 KB. The bound is what keeps a task from naming
# an arbitrarily large file and having agentctl read it.
MAX_LAUNCH_INPUT_BYTES = 1_048_576
# Bound on an outcome file read back; the largest historical one is 1.4 MB.
MAX_OUTCOME_BYTES = 2 * MAX_LAUNCH_INPUT_BYTES
# The label kinds under which a batch queues agents rather than declared operations.
AGENT_OPERATIONS = frozenset({"worker", "resume", "integrate", "review"})
# How long a wait blocks on one task id before re-reading which id the job
# it waits for is at.
WAIT_SLICE_SECONDS = 5.0
MAX_SNAPSHOT_ROWS = 100
MAX_SNAPSHOT_TEXT = 256


class JobError(RuntimeError):
    """A launch or read that agentctl itself refuses; pueue's own refusals are PueueError."""


def read_outcome(path: Path | None, limit: int) -> dict[str, Any] | None:
    """The outcome record at ``path``, or None when absent, oversized or invalid.

    Symlinks and nonregular files are refused, so a log alias cannot point
    the reader at an arbitrary file.
    """
    if path is None:
        return None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(descriptor, "rb") as handle:
        try:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                return None
            result = json.loads(handle.read(limit + 1))
        except (OSError, ValueError, UnicodeError, RecursionError):
            return None
    return result if isinstance(result, dict) else None


# A job id names one file under inputs/, so it is a single path component
# in the characters a sanitised label leaves.
JOB_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def read_launch_input(config: Config, task: Task) -> dict[str, Any] | None:
    path = launch_input_path(task)
    if path is None or not owns_path(config, task, path):
        return None
    raw = read_bounded(path, MAX_LAUNCH_INPUT_BYTES)
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _age_seconds(stamp: str | None, now: datetime) -> float | None:
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return max(0.0, (now - moment).total_seconds())


def queue_state(
    config: Config,
    groups: Sequence[str] | None = None,
    *,
    now: datetime | None = None,
    live: pueue.Status | None = None,
) -> dict[str, dict[str, Any]]:
    """Each group's occupancy from the unfinished tasks alone.

    What a caller needs to tell "queued behind X" from "hung": the width,
    who holds each slot and for how long, what is waiting and since when.
    """
    live = live or pueue.live()
    moment = now or datetime.now(UTC)
    selected = sorted(live.groups) if groups is None else list(groups)
    states: dict[str, dict[str, Any]] = {}
    for name in selected:
        detail = live.groups.get(name) or {}
        members = sorted(
            (task for task in live.tasks.values() if task.group == name),
            key=lambda task: task.task_id,
        )

        def row(task: Task, since: str | None) -> dict[str, Any]:
            age = _age_seconds(since, moment)
            document = read_launch_input(config, task) or {}
            argv = document.get("argv")
            return {
                "task_id": task.task_id,
                "label": task.label,
                "job_id": job_id_of(task),
                # What the slot is doing, from the launch input the job owns.
                "argv": [str(word) for word in argv]
                if isinstance(argv, list)
                else None,
                "since": since,
                "seconds": int(age) if age is not None else None,
            }

        running = [
            row(task, task.started_at) for task in members if task.status == "Running"
        ]
        queued = [
            {**row(task, task.enqueued_at), "dependencies": list(task.dependencies)}
            for task in members
            if task.status == "Queued"
        ]
        waits = [entry["seconds"] for entry in queued if entry["seconds"] is not None]
        states[name] = {
            "group": name,
            "known": name in live.groups,
            "status": str(detail.get("status") or "") or None,
            "parallel": int(detail.get("parallel_tasks") or 0) or None,
            "running": running,
            "running_count": len(running),
            "queued": queued,
            "queued_count": len(queued),
            "held_count": sum(
                1 for task in members if task.status in {"Stashed", "Paused"}
            ),
            "oldest_queued_seconds": max(waits) if waits else None,
        }
    return states


def job_queue(
    config: Config, job: Mapping[str, Any], *, now: datetime | None = None
) -> dict[str, Any] | None:
    """Where one unfinished job stands: its group's occupancy and its place.

    ``job`` is a job view. A terminal job has no queue. A queued job names the
    jobs ahead of it, the dependencies it waits for, and the running jobs that
    hold the slots it needs; a running job is reported with its group only.
    """
    group = job.get("group")
    if job.get("terminal") or not isinstance(group, str) or not group:
        return None
    state = queue_state(config, [group], now=now)[group]
    queued = job.get("phase") == "queued"
    task_id = job.get("task_id")
    ahead = (
        [
            entry["task_id"]
            for entry in state["queued"]
            if isinstance(task_id, int) and entry["task_id"] < task_id
        ]
        if queued
        else []
    )
    return {
        **state,
        "position": len(ahead) + 1 if queued else None,
        "ahead": ahead,
        "waiting_for": list(job.get("dependencies") or []) if queued else [],
        "occupied_by": state["running"] if queued else [],
    }


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


def owns_path(config: Config, task: Task, path: Path) -> bool:
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


def job_id_of(task: Task) -> str | None:
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
        "task_id": task.task_id,
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
        "job_id": job_id_of(task),
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
        row["attempt"] = artifact_view(config, task)["attempt"]
    shortened = []
    for key in ("label", "operation", "path", "job_id"):
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

    One selected-id read for the page. A queue id can move after listing,
    so a job id, when present, owns the binding's identity.
    """
    tasks = pueue.tasks_by_ids(
        [
            value
            for row in rows
            if isinstance(value := row.get("task_id"), int)
            and not isinstance(value, bool)
            and value >= 0
        ]
    )
    job_ids = index_tasks_by_job_id(tuple(tasks.values()))
    attached = []
    for row in rows:
        task_id, job_id = row.get("task_id"), row.get("job_id")
        task = find_task(tasks, task_id, job_id, job_ids=job_ids)
        if task is None and isinstance(job_id, str) and JOB_ID.fullmatch(job_id):
            task = locate(task_id, job_id)
        binding = (
            (read_launch_input(config, task) or {}).get("binding") if task else None
        )
        attached.append({**row, "binding": binding} if binding else dict(row))
    return attached


def _task(task_id: int) -> Task:
    task = pueue.task(task_id)
    if task is None:
        raise JobError(f"pueue has no task {task_id}")
    return task


def locate(task_id: int, job_id: str | None = None) -> Task | None:
    """The task carrying this job, read without the queue's whole history.

    The id is tried first, since a queue is rarely reordered; a job_id
    that does not match it is looked up by the one command that names its
    launch input.
    """
    task = pueue.task(task_id) if isinstance(task_id, int) and task_id >= 0 else None
    if job_id is None or (task is not None and job_id_of(task) == job_id):
        return task
    matches = pueue.tasks_by_command(f"{job_id}.json")
    return find_task(matches, task_id, job_id)


def read_task(config: Config, task_id: int, job_id: str | None) -> Task:
    task = locate(task_id, job_id)
    if task is not None:
        return task
    if job_id is None or not JOB_ID.fullmatch(job_id):
        raise JobError(
            f"pueue has no task {job_id or task_id}; archived reads require a job id"
        )
    path = config.inputs_dir / f"{job_id}.json"
    raw = read_bounded(path, MAX_LAUNCH_INPUT_BYTES)
    try:
        document = json.loads(raw) if raw else None
    except (ValueError, UnicodeDecodeError):
        document = None
    if not isinstance(document, dict):
        raise JobError(f"no retained launch {job_id}")
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


def artifact_view(
    config: Config, task: Task, attempt: int | None = None
) -> dict[str, Any]:
    document = read_launch_input(config, task) or {}
    job_id = job_id_of(task)
    if not document.get("log_path") and job_id is not None:
        # Older queue entries can outlive their input while their conventional
        # state-directory artifacts remain available by the job id in the command.
        document = {
            "log_path": str(config.jobs_dir / f"{job_id}.log"),
            "result_path": str(config.jobs_dir / f"{job_id}.result"),
        }
    records = artifacts.attempts(document) if document.get("log_path") else []
    # Retain ownership checks even for externally authored launch inputs.
    for record in records:
        record["artifacts"] = {
            key: value
            for key, value in record["artifacts"].items()
            if owns_path(config, task, Path(value))
        }
    selected = (
        next((record for record in records if record["attempt"] == attempt), None)
        if attempt is not None
        else (records[-1] if records else None)
    )
    if attempt is not None and selected is None and not (attempt == 0 and not records):
        raise JobError(f"launch {job_id_of(task)} has no attempt {attempt}")
    return {
        "attempt": selected["attempt"] if selected else 0,
        "artifacts": selected["artifacts"] if selected else {},
        "attempts": records,
        "input_path": str(launch_input_path(task)),
    }


def get_job(
    task_id: int,
    config: Config | None = None,
    job_id: str | None = None,
    *,
    attempt: int | None = None,
    attempt_offset: int = 0,
    attempt_limit: int = 100,
) -> dict[str, Any]:
    if attempt_offset < 0 or not 1 <= attempt_limit <= 100:
        raise JobError(
            "attempt_offset must be nonnegative and attempt_limit must be 1..100"
        )
    task = read_task(config, task_id, job_id) if config else addressed(task_id, job_id)
    if config is None:
        return job_view(task)
    return _job_detail(config, task, attempt, attempt_offset, attempt_limit)


def launch_selection(launch_input: Mapping[str, Any]) -> dict[str, Any]:
    """Public selection provenance from the retained input, never its environment."""
    selected = {
        key: launch_input[key]
        for key in ("descriptor_path", "project_root", "working_directory")
        if isinstance(launch_input.get(key), str) and launch_input[key]
    }
    timeout = launch_input.get("timeout_seconds")
    if isinstance(timeout, int) and not isinstance(timeout, bool) and timeout > 0:
        selected["timeout_seconds"] = timeout
    return selected


def _job_detail(
    config: Config,
    task: Task,
    attempt: int | None,
    attempt_offset: int = 0,
    attempt_limit: int = 100,
) -> dict[str, Any]:
    view = job_view(task)
    launch_input = read_launch_input(config, task) or {}
    view.update(launch_selection(launch_input))
    binding = launch_input.get("binding")
    if binding:
        view["binding"] = binding
    if launch_input.get("admission"):
        view["admission"] = launch_input["admission"]
    view.update(artifact_view(config, task, attempt))
    selected_outcome = view["artifacts"].get("outcome")
    outcome_path = Path(selected_outcome).resolve() if selected_outcome else None
    if outcome_path is not None and not owns_path(config, task, outcome_path):
        outcome_path = None
    receipt = _outcome_from_path(outcome_path).get("outcome") or {}
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
    disposition = read_disposition(config, task)
    if disposition:
        view["disposition"] = disposition
        view.update(
            _disposition_view(
                disposition,
                attempt=attempt,
                receipt=receipt,
                queue_terminal=task.terminal,
            )
        )
    if launch_input.get("log_path"):
        queued_cancel = (
            attempt is None and disposition and disposition.get("started") is False
        )
        request_attempt = 0 if queued_cancel else view["attempt"]
        if (
            attempt is None
            and not queued_cancel
            and task.started_at is not None
            and (
                request_attempt == 0
                or (not task.terminal and not unfinished_attempt(config, task))
            )
        ):
            request_attempt += 1
        request = artifacts.cancellation(
            Path(launch_input["log_path"]), request_attempt
        )
        if request:
            view["cancellation"] = request
    return view


def artifact_path(
    config: Config, task: Task, suffix: str, attempt: int | None = None
) -> Path | None:
    key = {".log": "log", ".result": "result"}[suffix]
    view = artifact_view(config, task, attempt)
    declared = view["artifacts"].get(key)
    if declared is None and attempt is None:
        declared = (read_launch_input(config, task) or {}).get(key + "_path")
    if isinstance(declared, str) and declared:
        path = Path(declared)
        return path.resolve() if owns_path(config, task, path) else None
    job_id = job_id_of(task)
    return config.jobs_dir / f"{job_id}{suffix}" if job_id and attempt is None else None


def read_job_artifact(
    config: Config,
    task_id: int,
    job_id: str | None = None,
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
    task = read_task(config, task_id, job_id)
    return _read_artifact(config, task, attempt, artifact, offset, limit)


def _read_artifact(
    config: Config,
    task: Task,
    attempt: int | None,
    artifact: str,
    offset: int,
    limit: int,
    *,
    selected_view: Mapping[str, Any] | None = None,
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
    view = (
        selected_view
        if selected_view is not None
        else artifact_view(config, task, attempt)
    )
    declared = view["artifacts"].get(artifact)
    path = Path(declared).resolve() if declared else None
    if path is not None and not owns_path(config, task, path):
        path = None
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
                    raw = masked_window(
                        lambda start, length, fd=descriptor: os.pread(
                            fd, length, start
                        ),
                        offset,
                        limit,
                        _secret_values(config, task),
                    )
            finally:
                os.close(descriptor)
    next_offset = offset + len(raw)
    return {
        "job_id": job_id_of(task),
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


def _secret_values(config: Config, task: Task) -> tuple[bytes, ...]:
    """Values to mask in what a job wrote: its own secrets and the reader's.

    The runner masks a finished job's logs on disk. A running job's logs, and
    logs written before masking existed, are masked as they are read.
    """
    environment = dict(os.environ)
    path = launch_input_path(task)
    value = read_launch_input(config, task)
    if path is not None and value is not None:
        environment.update(secret_environment(path, value)[0])
    return secret_values(environment)


def task_logs(config: Config, task: Task, *, attempt: int | None = None) -> str:
    path = artifact_path(config, task, ".log", attempt)
    raw = read_bounded(path, MAX_LOG_BYTES) if path is not None else None
    secrets = _secret_values(config, task)
    text = mask_secret_values(raw, secrets).decode("utf-8", "replace") if raw else ""
    # Pueue's wrapper capture belongs only to the current queue invocation.
    wrapper = (
        pueue.log(task.task_id) if attempt is None and task.status != "Archived" else ""
    )
    wrapper = mask_secret_values(wrapper.encode(), secrets).decode("utf-8", "replace")
    if wrapper.strip():
        text = f"{text}\n[wrapper]\n{wrapper}" if text else wrapper
    return text


# Lines that say why a build or test command failed: nextest's per-test
# verdicts, compiler errors, panics, the runner's own refusals and the devkit
# history pointer ("recorded as run N; details: xtask history failures N").
FAILURE_LINE = re.compile(
    r"^\s*(FAIL|TIMEOUT|SIGSEGV|SIGABRT|SIGKILL|SIGBUS|LEAK-FAIL)\s+\["
    r"|^(error|warning: build failed)(\[E\d+\])?:"
    r"|panicked at "
    r"|^\s*recorded as run \d+"
    r"|^(refused|timed out after|could not (start|control) the command)"
)
FAILURE_EXCERPT_LINES = 40
FAILURE_TAIL_LINES = 8


def failure_excerpt(config: Config, task: Task) -> list[str]:
    """What a person needs from a failed job's log without paging it: the
    matching failure lines, then the log's last lines, each kept once."""
    lines = task_logs(config, task).splitlines()
    tail = lines[-FAILURE_TAIL_LINES:]
    matched: list[str] = []
    for index, line in enumerate(lines[: len(lines) - len(tail)]):
        if FAILURE_LINE.search(line):
            matched.append(line)
            # A panic's message is the line after its location.
            if "panicked at " in line and index + 1 < len(lines) - len(tail):
                matched.append(lines[index + 1])
    room = FAILURE_EXCERPT_LINES - len(tail)
    if len(matched) > room:
        matched = [
            f"... {len(matched) - room} earlier failure line(s) omitted"
        ] + matched[-room:]
    return [*matched, *tail]


def logs(
    config: Config,
    task_id: int,
    job_id: str | None = None,
    *,
    attempt: int | None = None,
) -> str:
    return task_logs(config, read_task(config, task_id, job_id), attempt=attempt)


def result(
    config: Config,
    task_id: int,
    job_id: str | None = None,
    *,
    attempt: int | None = None,
    offset: int = 0,
    limit: int = MAX_RESULT_BYTES,
) -> dict[str, Any]:
    """Bound the view only; large typed results remain complete valid artifacts."""
    task = read_task(config, task_id, job_id)
    view = _job_detail(config, task, attempt)
    page = _read_artifact(
        config, task, view["attempt"], "result", offset, limit, selected_view=view
    )
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


def outcome(config: Config, task: Task, attempt: int | None = None) -> dict[str, Any]:
    log = artifact_path(config, task, ".log", attempt)
    return _outcome_from_path(outcome_path_for(log) if log is not None else None)


def _outcome_from_path(path: Path | None) -> dict[str, Any]:
    record = read_outcome(path, MAX_OUTCOME_BYTES)
    return {"outcome": record} if record is not None else {}


def disposition_path(input_path: Path) -> Path:
    return input_path.with_name(input_path.name + ".disposition")


def read_disposition(config: Config, task: Task) -> dict[str, Any] | None:
    path = launch_input_path(task)
    if path is None or not owns_path(config, task, path):
        return None
    raw = read_bounded(disposition_path(path), MAX_LAUNCH_INPUT_BYTES)
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return dict(value) if isinstance(value, dict) else None


def _disposition_view(
    disposition: Mapping[str, Any],
    *,
    attempt: int | None,
    receipt: Mapping[str, Any],
    queue_terminal: bool = True,
) -> dict[str, Any]:
    """Latest job disposition; a selected attempt keeps its own receipt."""
    if (
        attempt is not None
        and isinstance(disposition.get("attempt"), int)
        and disposition["attempt"] != attempt
    ):
        return {}
    if disposition.get("cancellation_incomplete") or (
        queue_terminal and "cgroup" in disposition
    ):
        obstacle = cgroups.cancellation_obstacle(disposition)
        if obstacle is not None:
            return {
                "phase": "unresolved",
                "started": True,
                "terminal": False,
                "cancellation_incomplete": True,
                "cgroup_observation": obstacle,
            }
        disposition = {**disposition, "unresolved": False}
    if disposition.get("unresolved"):
        return {"phase": "unresolved", "started": True}
    if disposition.get("outcome") != Outcome.CANCELLED.value:
        return {}
    started = disposition.get("started")
    overlay: dict[str, Any] = {
        "phase": Outcome.CANCELLED.value,
        "terminal": True,
        "started": started is not False,
    }
    if started is False:
        overlay["started"] = False
        if attempt is None:
            overlay["outcome"] = dict(disposition)
            overlay["exit_code"] = disposition.get("exit_code", CANCELLED_EXIT_CODE)
        elif receipt:
            overlay["outcome"] = dict(receipt)
    return overlay


def attempt_count(config: Config, task: Task) -> int:
    document = read_launch_input(config, task) or {}
    if not document.get("log_path"):
        return 0
    return len(artifacts.attempts(document))


def unfinished_attempt(config: Config, task: Task) -> bool:
    """Whether the latest allocated invocation has no outcome yet.

    A previous successful attempt with an outcome is not an active start; a
    wrapper that has allocated an attempt without finishing one is.
    """
    document = read_launch_input(config, task) or {}
    if not document.get("log_path"):
        return False
    records = artifacts.attempts(document)
    if not records:
        return False
    outcome = records[-1]["artifacts"].get("outcome")
    return not (isinstance(outcome, str) and Path(outcome).exists())


def find_task(
    tasks: Mapping[int, Task],
    task_id: object,
    job_id: object = None,
    *,
    job_ids: Mapping[str, Task] | None = None,
) -> Task | None:
    """Resolve a stored job identity after pueue may have reassigned its id."""
    if isinstance(job_id, str):
        if job_ids is not None:
            return job_ids.get(job_id)
        return next(
            (task for task in tasks.values() if job_id_of(task) == job_id),
            None,
        )
    return tasks.get(task_id) if isinstance(task_id, int) else None


def index_tasks_by_job_id(tasks: Sequence[Task]) -> dict[str, Task]:
    """Index launch identities once for callers resolving several saved jobs."""
    job_ids: dict[str, Task] = {}
    for task in tasks:
        job_id = job_id_of(task)
        if job_id is not None:
            job_ids.setdefault(job_id, task)
    return job_ids


def vanished(
    tasks: Mapping[int, Task],
    task_id: object,
    job_id: object = None,
    *,
    job_ids: Mapping[str, Task] | None = None,
) -> bool:
    """Whether a recorded job identity names nothing the queue holds any more.

    pueue's state is a file it can lose: after a reset its task ids start at
    zero again, so every id recorded before it names either nothing or a
    stranger's task. A record that named no task in the first place — an
    external worker, a landing not yet queued — has not vanished.
    """
    if not isinstance(task_id, int) and not isinstance(job_id, str):
        return False
    return find_task(tasks, task_id, job_id, job_ids=job_ids) is None


def addressed(task_id: int, job_id: str | None = None) -> Task:
    """The task carrying this job now, whatever id the queue moved it to.

    `pueue switch` exchanges the ids of two queued tasks, so an id names a
    position in the queue and not a job. The job id does name one:
    pueue carries a task's command wherever it moves the task, and the
    job_id is the launch input path inside that command. A caller that
    holds a job_id addresses its own job; one that holds only an id
    addresses whatever the queue keeps at that position, which one read of
    that position answers.
    """
    if job_id is None:
        return _task(task_id)
    task = locate(task_id, job_id)
    if task is None:
        raise JobError(f"pueue has no task for job {job_id}")
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
    job_id: str | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Block until the job is terminal, following it across queue task ids.

    ``job_id`` is the job id the caller started; without one the
    job is the one the queue holds at ``task_id`` when the wait begins. A
    caller that followed the id alone would wake on a stranger's task, or
    sleep past the end of its own.
    """
    deadline = time.monotonic() + timeout_seconds
    if job_id is None:
        job_id = job_id_of(_task(task_id))

    def observe() -> tuple[Task, dict[str, Any]]:
        nonlocal task_id
        task = (
            read_task(config, task_id, job_id)
            if config is not None
            else addressed(task_id, job_id)
        )
        # Keep the current hint; every lookup still checks the job id.
        task_id = task.task_id
        if config is not None and task.status == "Archived":
            view = _job_detail(config, task, None)
            if not view.get("terminal"):
                raise JobError(
                    f"job {job_id} is absent from pueue with no verified terminal outcome"
                )
            return task, view
        view = job_view(task)
        if config is not None:
            disposition = read_disposition(config, task)
            if disposition:
                view.update(
                    _disposition_view(
                        disposition,
                        attempt=None,
                        receipt={},
                        queue_terminal=task.terminal,
                    )
                )
        return task, view

    task, view = observe()
    detail: str | None = None
    while True:
        if view.get("terminal"):
            return view
        remaining = deadline - time.monotonic()
        if remaining <= 0 or detail is not None:
            timed_out = {**view, "wait_timed_out": True}
            return timed_out if detail is None else {**timed_out, "detail": detail}
        if task.terminal:
            # Queue completion can precede privileged descendant termination.
            time.sleep(min(remaining, 0.5))
            task, view = observe()
            continue
        blocking = _wait_slice(task, remaining)
        try:
            pueue.wait(task.task_id, timeout_seconds=blocking)
        except PueueTimeout:
            # A slice covering the whole remaining wait is the caller's own
            # timeout; a shorter one expired only to re-read the queue.
            if blocking >= remaining:
                task, view = observe()
                if view.get("terminal"):
                    return view
                return {**view, "wait_timed_out": True}
        except PueueError as error:
            detail = str(error)
        task, view = observe()
