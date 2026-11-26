"""Memory admission across pools: a job starts only when the job plane holds it.

Each pueue group admits its own jobs, so groups alone let several large builds
start together and overfill the plane's ``MemoryMax``, where the kernel or
systemd-oomd kills one of them. A job with a memory reservation (its
operation's ``admission.memory_mib``, else its pool's ``memory_mib``) is
therefore added to pueue stashed and released into its group only when

- its group is running and has a free slot, so a released job starts at once
  and never waits inside a slot it occupies, and
- the plane's free memory covers the reservation.

Committed memory is what the plane uses now, page cache excluded, plus the
part of each running reservation its job has not used yet, plus the whole
reservation of every released job that has not started. When no reserved job
is running, the first held job is released whatever its size: a reservation
larger than the plane, or memory held by unreserved work (agents in the
plane waiting on these very jobs) never blocks the queue for good.

Held jobs are released in pueue's order (priority, then task id) across all
pools. A smaller job may pass one that does not fit, until that one has
waited ``HEAD_OF_LINE_SECONDS``; from then on nothing passes it.

There is no daemon. A pass runs, under one lock, when a job is added or
retried, when a job's wrapper finishes, when a job is cancelled, and from the
``agentctl-admit`` timer; every pass recomputes from pueue's state, the launch
inputs and the plane's cgroup, so no pass depends on another having run.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from . import pueue
from .config import Config
from .launch_input import write_input
from .limits import SYSTEMCTL_TIMEOUT_SECONDS
from .pueue import PueueError, Status, Task
from .run import POOL_SLICE_PREFIX, append_event, systemd_environment

PLANE_SLICE = f"{POOL_SLICE_PREFIX}.slice"
CGROUP_ROOT = Path("/sys/fs/cgroup")
# How long a held job that does not fit may be passed by smaller ones. Long
# enough that a type check slips in beside a running build, short enough that
# a full check is not starved by a stream of small jobs.
HEAD_OF_LINE_SECONDS = 600
MIB = 1024 * 1024
_HOLDING_STATES = frozenset({"Running", "Paused"})


@dataclass(frozen=True)
class Plane:
    """The job plane's ceiling and what it holds that reclaim cannot free."""

    ceiling_mib: int | None
    used_mib: int
    # Non-reclaimable memory of each job unit in the plane, by unit name.
    units_mib: Mapping[str, int] = field(default_factory=dict)


def _unreclaimable_mib(cgroup: Path) -> int | None:
    """``memory.current`` less clean page cache; tmpfs (shmem) stays counted."""
    try:
        current = int((cgroup / "memory.current").read_text())
        stat = {
            key: int(value)
            for key, _, value in (
                line.partition(" ")
                for line in (cgroup / "memory.stat").read_text().splitlines()
            )
            if value.strip().isdigit()
        }
    except (OSError, ValueError):
        return None
    reclaimable = stat.get("file", 0) - stat.get("shmem", 0)
    return max(0, current - max(0, reclaimable)) // MIB


def read_plane() -> Plane | None:
    """The plane's ``MemoryMax`` and usage, or None when systemd cannot say.

    A plane without a ceiling (``infinity``) admits by pool slots alone.
    """
    try:
        completed = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                "-p",
                "ControlGroup,MemoryMax",
                PLANE_SLICE,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=SYSTEMCTL_TIMEOUT_SECONDS,
            env=systemd_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    properties = dict(
        line.partition("=")[::2]
        for line in completed.stdout.splitlines()
        if "=" in line
    )
    maximum = properties.get("MemoryMax", "")
    ceiling = int(maximum) // MIB if maximum.isdigit() else None
    group = properties.get("ControlGroup", "")
    if not group:
        return Plane(ceiling, 0)
    root = CGROUP_ROOT / group.lstrip("/")
    units: dict[str, int] = {}
    for directory, children, _ in os.walk(root):
        for child in children:
            if child.endswith(".service"):
                if (used := _unreclaimable_mib(Path(directory) / child)) is not None:
                    units[child] = used
        children[:] = [child for child in children if child.endswith(".slice")]
    return Plane(ceiling, _unreclaimable_mib(root) or 0, units)


def reservation(document: Mapping[str, Any] | None) -> int:
    """The MiB a launch input reserves; zero for a job admitted by slots alone."""
    admission = (document or {}).get("admission")
    value = admission.get("memory_mib") if isinstance(admission, Mapping) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def is_held(document: Mapping[str, Any] | None) -> bool:
    """Whether agentctl, not an operator, stashed this job until it fits."""
    admission = (document or {}).get("admission")
    return isinstance(admission, Mapping) and admission.get("held") is True


def hold(document: Mapping[str, Any]) -> dict[str, Any]:
    """The launch input marked as waiting for admission from now."""
    admission = dict(document.get("admission") or {})
    admission["held"] = True
    admission["held_since"] = datetime.now(UTC).isoformat(timespec="seconds")
    return {**document, "admission": admission}


def _seconds_since(stamp: object, now: datetime) -> float:
    if not isinstance(stamp, str):
        return 0.0
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return 0.0
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return max(0.0, (now - moment).total_seconds())


def _deferred(document: Mapping[str, Any], now: datetime) -> bool:
    deferred = document.get("deferred")
    until = deferred.get("until") if isinstance(deferred, Mapping) else None
    if not isinstance(until, str):
        return False
    try:
        moment = datetime.fromisoformat(until)
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment > now


@dataclass
class Plan:
    """What one pass releases and why every other held job waits."""

    release: list[Task]
    waits: dict[int, dict[str, Any]]
    committed_mib: int
    ceiling_mib: int | None
    documents: dict[int, dict[str, Any]]


def plan(
    config: Config,
    live: Status,
    plane: Plane | None,
    *,
    exclude: int | None = None,
    now: datetime | None = None,
) -> Plan:
    """Decide which held jobs start now, from one queue snapshot and plane read.

    ``exclude`` is a task whose wrapper is finishing: its unit is gone, so it
    holds neither memory nor, a moment from now, its slot.
    """
    from .job_queries import job_id_of, read_launch_input, unit_of

    moment = now or datetime.now(UTC)
    tasks = {
        task_id: task for task_id, task in live.tasks.items() if task_id != exclude
    }
    documents = {
        task_id: document
        for task_id, task in tasks.items()
        if (document := read_launch_input(config, task)) is not None
    }
    units = plane.units_mib if plane is not None else {}
    # The excluded wrapper has already stopped its unit, so the plane's usage
    # no longer includes it.
    committed = plane.used_mib if plane is not None else 0
    reserved_active = False
    occupied: dict[str, int] = {}
    for task_id, task in tasks.items():
        reserved = reservation(documents.get(task_id))
        if task.status in _HOLDING_STATES:
            occupied[task.group] = occupied.get(task.group, 0) + 1
            if reserved:
                reserved_active = True
                used = units.get(unit_of(task) or "", 0)
                committed += max(0, reserved - used)
        elif task.status == "Queued" and not any(
            dependency in live.tasks for dependency in task.dependencies
        ):
            # About to start: it takes a slot and its whole reservation.
            occupied[task.group] = occupied.get(task.group, 0) + 1
            if reserved:
                reserved_active = True
                committed += reserved
    ceiling = plane.ceiling_mib if plane is not None else None
    held = sorted(
        (
            task
            for task_id, task in tasks.items()
            if task.status == "Stashed" and is_held(documents.get(task_id))
        ),
        key=lambda task: (-task.priority, task.task_id),
    )
    release: list[Task] = []
    waits: dict[int, dict[str, Any]] = {}
    blocking: Task | None = None
    for task in held:
        document = documents[task.task_id]
        need = reservation(document)
        detail = live.groups.get(task.group) or {}
        width = int(detail.get("parallel_tasks") or 0)
        if str(detail.get("status") or "") == "Paused":
            waits[task.task_id] = {"reason": "group-paused"}
            continue
        if _deferred(document, moment):
            waits[task.task_id] = {"reason": "deferred"}
            continue
        if width and occupied.get(task.group, 0) >= width:
            waits[task.task_id] = {"reason": "pool-full"}
            continue
        free = None if ceiling is None else ceiling - committed
        memory = {
            "reason": "memory",
            "memory_mib": need,
            "free_mib": max(0, free) if free is not None else None,
            "ceiling_mib": ceiling,
        }
        if blocking is not None:
            waits[task.task_id] = {
                **memory,
                "behind": {
                    "task_id": blocking.task_id,
                    "label": blocking.label,
                    "job_id": job_id_of(blocking),
                },
            }
            continue
        if free is None or need <= free or not reserved_active:
            release.append(task)
            committed += need
            reserved_active = True
            occupied[task.group] = occupied.get(task.group, 0) + 1
            continue
        waits[task.task_id] = memory
        admission = document.get("admission") or {}
        waited = _seconds_since(
            admission.get("held_since") or document.get("enqueued_at"), moment
        )
        if waited >= HEAD_OF_LINE_SECONDS:
            blocking = task
    return Plan(release, waits, committed, ceiling, documents)


def _lock_path(config: Config) -> Path:
    return config.state_dir / "admission.lock"


def admit(config: Config, *, exclude: int | None = None) -> dict[str, Any]:
    """Release every held job that fits now; return what was released and why
    the rest wait. Concurrent passes take turns on one lock."""
    from .job_queries import launch_input_path

    config.state_dir.mkdir(parents=True, exist_ok=True)
    with _lock_path(config).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        live = pueue.live()
        decided = plan(config, live, read_plane(), exclude=exclude)
        released: list[dict[str, Any]] = []
        for task in decided.release:
            try:
                pueue.enqueue(task.task_id)
            except PueueError:
                # Cancelled or removed since the snapshot; the next pass sees it.
                continue
            document = decided.documents[task.task_id]
            path = launch_input_path(task)
            admission = {
                key: value
                for key, value in (document.get("admission") or {}).items()
                if key not in {"held", "held_since"}
            }
            if path is not None:
                write_input(path, {**document, "admission": admission})
            row = {
                "task_id": task.task_id,
                "job_id": document.get("job_id"),
                "label": task.label,
                "group": task.group,
                "memory_mib": reservation(document),
            }
            released.append(row)
            append_event(
                config.event_spool,
                {
                    "kind": "admission",
                    "phase": "released",
                    **row,
                    "committed_mib": decided.committed_mib,
                    "ceiling_mib": decided.ceiling_mib,
                },
            )
    return {
        "released": released,
        "waiting": [
            {"task_id": task_id, **wait}
            for task_id, wait in sorted(decided.waits.items())
        ],
        "committed_mib": decided.committed_mib,
        "ceiling_mib": decided.ceiling_mib,
    }


def held_waits(
    config: Config, live: Status, plane: Plane | None = None
) -> dict[int, dict[str, Any]]:
    """Why each held job waits, without releasing anything. Empty when no job
    is held, so readers read the plane only when there is a reason to give."""
    from .job_queries import read_launch_input

    if not any(
        task.status == "Stashed" and is_held(read_launch_input(config, task))
        for task in live.tasks.values()
    ):
        return {}
    return plan(config, live, plane if plane is not None else read_plane()).waits


def wait_line(wait: Mapping[str, Any]) -> str:
    """One line for a held job's reason, as `job start` and `job wait` print it."""
    if wait.get("reason") != "memory":
        return f"waiting: {wait.get('reason')}"
    line = f"waiting for memory: needs {wait.get('memory_mib')} MiB"
    if wait.get("free_mib") is not None:
        line += f", {wait['free_mib']} of {wait.get('ceiling_mib')} MiB free"
    if isinstance(behind := wait.get("behind"), Mapping):
        line += f", behind {behind.get('label')} (task {behind.get('task_id')})"
    return line
