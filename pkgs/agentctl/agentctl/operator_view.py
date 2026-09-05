"""The operator's one screen: queue, runs and their workers, ready work.

Assembled from `pueue status --json`, the run manifests and `bd ready
--json`; rendered as text in local time.
Every "next" here is a description of the mechanical state, not a decision:
nothing in this module dispatches.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from . import batch, pueue
from .batch import Run, run_stage, worker_stage
from .config import Config
from .launch import job_view
from .packets import PacketError, SubprocessBdReader
from .projects import ProjectAdapter
from .pueue import PueueError, Task

MAX_READY_SHOWN = 8
MAX_FAILED_SHOWN = 6


@dataclass(frozen=True)
class Snapshot:
    project_id: str
    now: datetime
    tasks: tuple[Task, ...]
    groups: Mapping[str, str]
    runs: tuple[Run, ...]
    ready: tuple[Mapping[str, Any], ...]
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "sinnix.agentctl.view.v3",
            "project": self.project_id,
            "at": self.now.isoformat(),
            "groups": {
                name: {"status": status, **_group_counts(self.tasks, name)}
                for name, status in sorted(self.groups.items())
            },
            "jobs": [job_view(task) for task in self.tasks],
            "runs": [run_dict(run, self.tasks, self.now) for run in self.runs],
            "ready": [
                {
                    "id": bead.get("id"),
                    "title": bead.get("title"),
                    "type": bead.get("issue_type"),
                }
                for bead in self.ready
            ],
            "errors": list(self.errors),
        }


def parse_stamp(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def age(stamp: str | None, now: datetime) -> str:
    moment = parse_stamp(stamp)
    if moment is None:
        return "?"
    seconds = max(int((now - moment).total_seconds()), 0)
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    if seconds < 172800:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}"
    return f"{seconds // 86400}d"


def local_clock(stamp: str | None, *, seconds: bool = False) -> str:
    moment = parse_stamp(stamp)
    if moment is None:
        return "?"
    return moment.astimezone().strftime("%H:%M:%S" if seconds else "%H:%M")


def _task(tasks: Sequence[Task], task_id: Any) -> Task | None:
    if not isinstance(task_id, int):
        return None
    return next((task for task in tasks if task.task_id == task_id), None)


def run_dict(run: Run, tasks: Sequence[Task], now: datetime) -> dict[str, Any]:
    """One run's rows: stage from pueue first, the manifest second."""
    worker_tasks = [_task(tasks, worker.get("task_id")) for worker in run.workers]
    landing_task = _task(tasks, run.landing.get("task_id"))
    workers = []
    for worker, task in zip(run.workers, worker_tasks, strict=True):
        since = (task.started_at or task.enqueued_at) if task else None
        workers.append(
            {
                "id": worker["id"],
                "beads": list(worker["beads"]),
                "branch": worker["branch"],
                "worktree": worker.get("worktree"),
                "stage": worker_stage(worker, task),
                "job": task.task_id if task else None,
                "since": since,
                "elapsed": age(since, now) if since else None,
            }
        )
    landing = run.landing
    return {
        "run": run.run_id,
        "harness": run.harness,
        "base_commit": run.base_commit,
        "stage": run_stage(run, landing_task, worker_tasks),
        "next": run_next(run, landing_task, worker_tasks),
        "workers": workers,
        "landing": {
            "job": landing_task.task_id if landing_task else None,
            "phase": job_view(landing_task)["phase"] if landing_task else None,
            "candidate_sha": landing.get("candidate_sha"),
            "pr_number": landing.get("pr_number"),
            "failure": landing.get("failure"),
        },
        "accepted": run.acceptance is not None,
    }


def run_next(
    run: Run, landing: Task | None, worker_tasks: Sequence[Task | None]
) -> str:
    """What follows mechanically; nothing here dispatches."""
    stage = run_stage(run, landing, worker_tasks)
    if stage in {"working", "landing"}:
        return "wait"
    if stage == "landed":
        return "-"
    if stage == "stashed":
        return "batch result, then the landing task runs"
    if stage.startswith("failed") or stage.startswith("landing "):
        return (
            f"job logs {landing.task_id}, then batch land or batch resume"
            if landing
            else "batch land"
        )
    if stage == "unprepared":
        return "batch start again"
    if stage == "awaiting workers":
        failed = [
            task
            for task in worker_tasks
            if task is not None and task.terminal and not task.succeeded
        ]
        return "batch resume --worker" if failed else "batch result"
    return "batch land"


def _group_counts(tasks: Sequence[Task], group: str) -> dict[str, int]:
    counts = Counter(
        task.status.lower()
        for task in tasks
        if task.group == group and not task.terminal
    )
    return {
        "running": counts.get("running", 0),
        "queued": counts.get("queued", 0),
        "paused": counts.get("paused", 0),
    }


def collect(
    config: Config, project: ProjectAdapter, *, now: datetime | None = None
) -> Snapshot:
    errors: list[str] = []
    prefix = f"{project.project_id}:"
    try:
        tasks = tuple(
            task
            for task in sorted(pueue.tasks().values(), key=lambda item: item.task_id)
            if task.label.startswith(prefix)
        )
        groups = pueue.groups_status()
    except PueueError as error:
        tasks, groups = (), {}
        errors.append(f"pueue: {error}")
    runs = tuple(batch.list_runs(config, project.project_id))
    reader = SubprocessBdReader(project.root)
    try:
        ready = tuple(reader.ready())
    except PacketError as error:
        ready = ()
        errors.append(f"bd: {error}")
    return Snapshot(
        project_id=project.project_id,
        now=now or datetime.now(UTC),
        tasks=tasks,
        groups=groups,
        runs=runs,
        ready=ready,
        errors=tuple(errors),
    )


def table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Aligned columns; the last column is never padded."""
    cells = [[str(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in cells:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines = []
    for row in [list(headers), *cells]:
        lines.append(
            "  ".join(
                value if index == len(row) - 1 else value.ljust(widths[index])
                for index, value in enumerate(row)
            ).rstrip()
        )
    return "\n".join(lines)


def render(snapshot: Snapshot) -> str:
    now = snapshot.now
    lines = [
        f"== {snapshot.project_id} at {now.astimezone().strftime('%Y-%m-%d %H:%M')}"
    ]
    lines.extend(f"  ! {error}" for error in snapshot.errors)

    group_text = []
    for group, status in sorted(snapshot.groups.items()):
        counts = _group_counts(snapshot.tasks, group)
        detail = " ".join(
            f"{count} {state}" for state, count in counts.items() if count
        )
        group_text.append(
            f"{group} {detail or 'idle'}{' PAUSED' if status == 'Paused' else ''}"
        )
    lines.append("== queue: " + (" · ".join(group_text) or "pueue unavailable"))

    failed = [
        task
        for task in snapshot.tasks
        if task.terminal and not task.succeeded and task.result != "Killed"
    ]
    failed.sort(key=lambda task: task.ended_at or "", reverse=True)
    runs = [run_dict(run, snapshot.tasks, now) for run in snapshot.runs]
    attention = [
        row
        for row in runs
        if row["stage"].startswith(("failed", "landing "))
        or any(
            worker["stage"]
            in {"failed", "timeout", "refused", "cancelled", "launch-failed"}
            for worker in row["workers"]
        )
    ]
    if failed or attention:
        lines.append("== needs attention")
        for task in failed[:MAX_FAILED_SHOWN]:
            exit_text = f" exit {task.exit_code}" if task.exit_code is not None else ""
            lines.append(
                f"  ! job {task.task_id} {task.label} {job_view(task)['phase']}{exit_text}"
                f" at {local_clock(task.ended_at)} ({age(task.ended_at, now)} ago)"
            )
        for row in attention:
            lines.append(f"  ! run {row['run']} {row['stage']}: {row['next']}")
    else:
        lines.append("== nothing needs attention")

    active = [task for task in snapshot.tasks if not task.terminal]
    lines.append(f"== jobs: {len(active)} active")
    if active:
        lines.append(
            table(
                ("id", "label", "state", "started", "elapsed"),
                [
                    (
                        task.task_id,
                        task.label,
                        task.status.lower(),
                        local_clock(task.started_at or task.enqueued_at),
                        age(task.started_at or task.enqueued_at, now),
                    )
                    for task in active
                ],
            )
            .replace("\n", "\n  ")
            .join(("  ", ""))
        )

    open_runs = [row for row in runs if not row["accepted"]]
    lines.append(f"== runs: {len(open_runs)} open, {len(runs) - len(open_runs)} landed")
    if open_runs:
        rows = []
        for row in open_runs:
            for worker in row["workers"]:
                rows.append(
                    (
                        row["run"],
                        worker["id"],
                        worker["stage"],
                        f"{local_clock(worker['since'])} {worker['elapsed']}"
                        if worker["since"]
                        else "-",
                        f"#{worker['job']}" if worker["job"] is not None else "-",
                        "",
                    )
                )
            landing = row["landing"]
            rows.append(
                (
                    row["run"],
                    "landing",
                    row["stage"],
                    "-",
                    f"#{landing['job']}" if landing["job"] is not None else "-",
                    row["next"],
                )
            )
        lines.append(
            table(("run", "worker", "stage", "since", "job", "next"), rows)
            .replace("\n", "\n  ")
            .join(("  ", ""))
        )

    lines.append(f"== ready: {len(snapshot.ready)} beads")
    for bead in snapshot.ready[:MAX_READY_SHOWN]:
        lines.append(
            f"  {str(bead.get('id') or ''):18} {str(bead.get('issue_type') or ''):8} "
            f"{str(bead.get('title') or '')[:70]}"
        )
    return "\n".join(lines)


__all__ = ["Snapshot", "collect", "render", "table", "age", "local_clock", "run_dict"]
