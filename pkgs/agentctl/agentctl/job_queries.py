"""Job queries over queue tasks and saved output.

Reads select attempts and mask secrets. Waiting observes completion.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from sinnix_lib.secrets import mask_secret_values, masked_window, secret_values

from . import artifacts, pueue
from .config import Config
from .launch_input import secret_environment
from .pueue import PueueError, PueueTimeout, Task
from .run import (
    CANCELLED_EXIT_CODE,
    MAX_LOG_BYTES,
    MAX_RESULT_BYTES,
    OUT_OF_MEMORY_EXIT_CODE,
    REFUSED_EXIT_CODE,
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
    """The running and waiting jobs in each requested group."""
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
                "project": task.label.partition(":")[0],
                "project_root": document.get("project_root"),
                "working_directory": document.get("working_directory") or task.path,
                "priority": task.priority,
                "phase": phase_of(task),
                # The command comes from this job's launch input.
                "argv": [str(word) for word in argv]
                if isinstance(argv, list)
                else None,
                "since": since,
                "seconds": int(age) if age is not None else None,
            }

        running = [
            row(task, task.started_at) for task in members if task.status == "Running"
        ]
        # Pueue orders by priority descending, then ID ascending.
        queued = [
            {
                **row(task, task.enqueued_at),
                "dependencies": list(task.dependencies),
                "waiting_for": [dep for dep in task.dependencies if dep in live.tasks],
            }
            for task in sorted(members, key=lambda task: (-task.priority, task.task_id))
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
            "paused": [
                row(task, task.started_at)
                for task in members
                if task.status == "Paused"
            ],
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

    A terminal job has no queue. A queued job names its dependencies and the
    running jobs and higher-priority jobs ahead of it.
    """
    group = job.get("group")
    if job.get("terminal") or not isinstance(group, str) or not group:
        return None
    live = pueue.live()
    task = live.tasks.get(job.get("task_id"))
    if task is not None and job.get("job_id") not in {None, job_id_of(task)}:
        task = None
    group = task.group if task else group
    state = queue_state(config, [group], now=now, live=live)[group]
    result = {
        **state,
        "position": None,
        "ahead": [],
        "waiting_for": [],
        "occupied_by": [],
    }
    if task is None:
        return {**result, "reason": "not-in-live-queue"}
    if task.status == "Running":
        return {**result, "reason": "running"}
    if task.status == "Paused":
        return {**result, "reason": "task-paused"}
    if task.status == "Stashed":
        return {**result, "reason": "stashed"}
    waiting = [dep for dep in task.dependencies if dep in live.tasks]
    if state["status"] == "Paused":
        return {**result, "reason": "group-paused", "waiting_for": waiting}
    if waiting:
        return {**result, "reason": "dependencies", "waiting_for": waiting}
    eligible = [entry for entry in state["queued"] if not entry["waiting_for"]]
    ids = [entry["task_id"] for entry in eligible]
    if task.task_id not in ids:
        return {**result, "reason": "not-queued"}
    position = ids.index(task.task_id)
    running_jobs = [*state["running"], *state["paused"]]
    width = state["parallel"]
    free = max(0, width - len(running_jobs)) if width else len(eligible)
    reason = (
        "ready" if position < free else "pool-full" if not free else "priority-order"
    )
    return {
        **result,
        "reason": reason,
        "position": position + 1,
        "ahead": ids[:position],
        "occupied_by": running_jobs if reason != "ready" else [],
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
    OUT_OF_MEMORY_EXIT_CODE: Outcome.OUT_OF_MEMORY.value,
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
    return {
        "task_id": task.task_id,
        "label": task.label,
        "kind": "declared-operation",
        "project": project,
        "operation": operation,
        "group": task.group,
        "dependencies": list(task.dependencies),
        "priority": task.priority if task.status != "Archived" else None,
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
    waits = wait_reasons(active, queue.groups)
    selected = [*active, *terminal][:limit]
    returned_active = sum(not task.terminal for task in selected)
    returned_terminal = len(selected) - returned_active
    return {
        "schema": "sinnix.agentctl.job-snapshot.v1",
        "limit": limit,
        "groups": groups,
        "jobs": [
            {**_snapshot_row(task, config), **waits.get(task.task_id, {})}
            for task in selected
        ],
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


def wait_reasons(
    active: Sequence[Task], groups: Mapping[str, Mapping[str, Any]]
) -> dict[int, dict[str, Any]]:
    """Why each queued task has not started, from one queue snapshot.

    The reasons match ``job_queue``: a paused group, an unfinished dependency,
    a full pool (naming the jobs that hold it), or queue order (naming the
    jobs ahead).
    """

    def brief(task: Task) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "label": task.label[:MAX_SNAPSHOT_TEXT],
            "job_id": job_id_of(task),
            "started_at": task.started_at,
        }

    live_ids = {task.task_id for task in active}
    reasons: dict[int, dict[str, Any]] = {}
    by_group: dict[str, list[Task]] = {}
    for task in active:
        by_group.setdefault(task.group, []).append(task)
    for name, members in by_group.items():
        detail = groups.get(name) or {}
        holding = [task for task in members if task.status in {"Running", "Paused"}]
        width = int(detail.get("parallel_tasks") or 0)
        paused = str(detail.get("status") or "") == "Paused"
        queued = sorted(
            (task for task in members if task.status == "Queued"),
            key=lambda task: (-task.priority, task.task_id),
        )
        eligible = [
            task
            for task in queued
            if not any(dep in live_ids for dep in task.dependencies)
        ]
        free = max(0, width - len(holding)) if width else len(eligible)
        for task in queued:
            waiting_for = [dep for dep in task.dependencies if dep in live_ids]
            if paused:
                wait: dict[str, Any] = {"reason": "group-paused"}
            elif waiting_for:
                wait = {"reason": "dependencies", "waiting_for": waiting_for}
            else:
                position = eligible.index(task)
                if position < free:
                    wait = {"reason": "ready"}
                elif not free:
                    wait = {
                        "reason": "pool-full",
                        "occupied_by": [brief(item) for item in holding[:4]],
                    }
                else:
                    wait = {"reason": "priority-order"}
                wait["position"] = position + 1
                if position:
                    wait["ahead"] = [brief(item) for item in eligible[:position][:4]]
            reasons[task.task_id] = {"wait": {**wait, "group": name}}
    return reasons


def _snapshot_row(task: Task, config: Config | None = None) -> dict[str, Any]:
    """One snapshot row with foreign queue strings bounded for transport."""
    row = job_view(task)
    if config is not None:
        view = artifact_view(config, task)
        row["attempt"] = view["attempt"]
        if not task.terminal:
            # What an unfinished job runs and for whom, from its launch input.
            document = read_launch_input(config, task) or {}
            argv = document.get("argv")
            if isinstance(argv, list):
                command = " ".join(str(word) for word in argv)
                row["command"] = (
                    command
                    if len(command) <= MAX_SNAPSHOT_TEXT
                    else command[: MAX_SNAPSHOT_TEXT - 1] + "…"
                )
            if isinstance(document.get("caller"), dict):
                row["caller"] = document["caller"]
            if document.get("announce") is True:
                row["announce"] = True
                if isinstance(document.get("revision"), dict):
                    row["revision"] = document["revision"]
            if task.status == "Stashed" and isinstance(document.get("deferred"), dict):
                row["deferred"] = document["deferred"]
            if not row.get("enqueued_at") and document.get("enqueued_at"):
                # pueue reports no enqueue time for a held task.
                row["enqueued_at"] = document["enqueued_at"]
            if isinstance(document.get("working_directory"), str):
                row["working_directory"] = document["working_directory"][
                    :MAX_SNAPSHOT_TEXT
                ]
            if log := view["artifacts"].get("log"):
                row["log_path"] = log
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

    Read the selected task IDs once and check each optional job ID.
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
    attached = []
    for row in rows:
        task_id, job_id = row.get("task_id"), row.get("job_id")
        task = tasks.get(task_id)
        if task is not None and job_id is not None and job_id_of(task) != job_id:
            task = None
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


def task_by_id(task_id: int, job_id: str | None = None) -> Task:
    """Read one queue task, checking the optional job ID on that same row."""
    task = _task(task_id)
    if job_id is not None and job_id_of(task) != job_id:
        raise JobError(f"task {task_id} does not match job {job_id}")
    return task


def read_task(config: Config, task_id: int, job_id: str | None = None) -> Task:
    task = pueue.task(task_id) if task_id >= 0 else None
    if task is not None:
        if job_id is not None and job_id_of(task) != job_id:
            raise JobError(f"task {task_id} does not match job {job_id}")
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
    if task_id >= 0 and document.get("queue_task_id") != task_id:
        raise JobError(f"task {task_id} does not match retained job {job_id}")
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
    task = read_task(config, task_id, job_id) if config else task_by_id(task_id, job_id)
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
    if isinstance(timeout, int) and not isinstance(timeout, bool) and timeout >= 0:
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
    record = _outcome_from_path(outcome_path).get("outcome") or {}
    records = view["attempts"]
    view["attempts"] = records[attempt_offset : attempt_offset + attempt_limit]
    view["attempt_count"] = len(records)
    view["next_attempt_offset"] = (
        attempt_offset + attempt_limit
        if attempt_offset + attempt_limit < len(records)
        else None
    )
    if record:
        view["outcome"] = record
    view["queue_present"] = task.status != "Archived"
    if task.status == "Archived":
        view.update(
            phase=(
                "succeeded"
                if record.get("outcome") == "success"
                else record.get("outcome", "unknown")
            ),
            terminal=bool(record),
            exit_code=record.get("exit_code"),
        )
    if isinstance(record.get("scratch"), dict):
        view["scratch"] = record["scratch"]
    log = launch_input.get("log_path")
    if log:
        number = view["attempt"]
        if attempt is None and task.started_at is not None:
            number = artifacts.attempt_for_start(launch_input, task.started_at)
        elif attempt is None and task.status == "Archived":
            pending = artifacts.cancellation(Path(log), number + 1)
            if pending and pending.get("stopped"):
                number += 1
        request = artifacts.cancellation(Path(log), number)
        queued = artifacts.cancellation(Path(log), 0) if attempt is None else None
        request = queued or request
        if request:
            view["cancellation"] = request
            if request.get("stopped") and (task.terminal or task.status == "Archived"):
                view.update(
                    phase="cancelled",
                    terminal=True,
                    started=request.get("started", True),
                )
                view["exit_code"] = CANCELLED_EXIT_CODE
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
    """A bounded byte page and the path to the complete output file.

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


def outcome(config: Config, task: Task, attempt: int | None = None) -> dict[str, Any]:
    log = artifact_path(config, task, ".log", attempt)
    return _outcome_from_path(outcome_path_for(log) if log is not None else None)


def _outcome_from_path(path: Path | None) -> dict[str, Any]:
    record = read_outcome(path, MAX_OUTCOME_BYTES)
    return {"outcome": record} if record is not None else {}


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


def wait(
    task_id: int,
    *,
    timeout_seconds: float,
    job_id: str | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Wait on the assigned task ID and check its optional job ID on each read."""
    task = read_task(config, task_id, job_id) if config else task_by_id(task_id, job_id)
    view = _job_detail(config, task, None) if config else job_view(task)
    if view["terminal"]:
        return view
    if task.status == "Archived":
        raise JobError(f"job {job_id} has no terminal result")
    detail = None
    try:
        pueue.wait(task_id, timeout_seconds=timeout_seconds)
    except PueueTimeout:
        pass
    except PueueError as error:
        detail = str(error)
    task = read_task(config, task_id, job_id) if config else task_by_id(task_id, job_id)
    view = _job_detail(config, task, None) if config else job_view(task)
    if view["terminal"]:
        return view
    return {**view, "wait_timed_out": True, **({"detail": detail} if detail else {})}
