"""What the operator reads: a run's stage, the one screen, and the CLI's output.

Assembled from `pueue status --json`, the run manifests and `bd ready
--json`; rendered as text in local time. Every "next" here is a description
of the mechanical state, not a decision: nothing in this module dispatches.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from . import github, launch, pueue
from .config import Config
from .github import GithubError
from .launch import job_view
from .limits import SHORT_ID
from .manifest import Run, list_runs, load, short_run_id
from .projects import ProjectAdapter
from .prompts import PromptError, SubprocessBdReader
from .pueue import PueueError, Task

MAX_READY_SHOWN = 8
MAX_FAILED_SHOWN = 6
# A failure older than this has been seen; the screen shows recent ones.
ATTENTION_SECONDS = 6 * 3_600
# Bead types the ready list leaves out: neither is a unit of work.
UNREADY_TYPES = frozenset({"epic", "decision"})
DEFAULT_JOB_ROWS = 40


# ---------------------------------------------------------------- stage


def worker_stage(worker: Mapping[str, Any], task: Task | None) -> str:
    """What the worker is doing, from pueue first and the manifest second."""
    if task is not None and not task.terminal:
        return task.status.lower()
    if worker.get("result"):
        return "done"
    if task is not None and task.terminal:
        return launch.phase_of(task)
    return "awaiting result" if worker.get("worktree") else "unprepared"


def run_stage(
    run: Run, landing: Task | None, worker_tasks: Sequence[Task | None]
) -> str:
    """The run as one word: an active worker or landing task is never landed."""
    if any(task is not None and not task.terminal for task in worker_tasks):
        return "working"
    if landing is not None and not landing.terminal:
        return "stashed" if landing.status == "Stashed" else "landing"
    if run.acceptance is not None:
        return "landed"
    if run.abandoned is not None:
        return "abandoned"
    failure = run.landing.get("failure")
    if failure:
        return f"failed: {failure.get('code')}"
    if not run.prepared:
        return "unprepared"
    if landing is not None and landing.terminal and not landing.succeeded:
        return f"landing {launch.phase_of(landing)}"
    return (
        "awaiting workers"
        if not all(w.get("result") for w in run.workers)
        else "ready to land"
    )


def status(
    config: Config, run_id: str, *, project: ProjectAdapter | None = None
) -> dict[str, Any]:
    """The manifest with each task's pueue view and the landing PR's state."""
    run = load(config, run_id)
    tasks = pueue.tasks()
    document = run.to_dict()
    for worker in document["workers"]:
        task_id = worker.get("task_id")
        task = tasks.get(task_id) if isinstance(task_id, int) else None
        worker["task"] = job_view(task) if task else None
        worker["stage"] = worker_stage(worker, task)
    landing_id = document["landing"].get("task_id")
    landing_task = tasks.get(landing_id) if isinstance(landing_id, int) else None
    document["landing"]["task"] = job_view(landing_task) if landing_task else None
    document["stage"] = run_stage(
        run,
        landing_task,
        [
            tasks.get(w["task_id"]) if isinstance(w.get("task_id"), int) else None
            for w in run.workers
        ],
    )
    number = run.landing.get("pr_number")
    if project is not None and isinstance(number, int):
        try:
            pull = github.pull_request(project.root, number)
        except GithubError as error:
            pull = {"error": str(error)}
        document["landing"]["pr"] = pull
    return document


# ---------------------------------------------------------------- screen


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


def recent(stamp: str | None, now: datetime) -> bool:
    """Whether ``stamp`` lies within the attention window before ``now``."""
    moment = parse_stamp(stamp)
    return moment is not None and (now - moment).total_seconds() <= ATTENTION_SECONDS


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
    # When the run last changed: the landing task's end, else the latest
    # worker task's end, else the run's start.
    ended = [
        task.ended_at
        for task in (landing_task, *worker_tasks)
        if task is not None and task.ended_at
    ]
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
        "changed_at": max(ended) if ended else run.created_at,
    }


def run_next(
    run: Run, landing: Task | None, worker_tasks: Sequence[Task | None]
) -> str:
    """What follows mechanically; nothing here dispatches."""
    stage = run_stage(run, landing, worker_tasks)
    if stage in {"working", "landing"}:
        return "wait"
    if stage in {"landed", "abandoned"}:
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
    runs = tuple(list_runs(config, project.project_id))
    reader = SubprocessBdReader(project.root)
    try:
        ready = tuple(
            bead
            for bead in reader.ready()
            if str(bead.get("issue_type") or "") not in UNREADY_TYPES
        )
    except PromptError as error:
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
        if task.terminal
        and not task.succeeded
        and task.result != "Killed"
        and recent(task.ended_at, now)
    ]
    failed.sort(key=lambda task: task.ended_at or "", reverse=True)
    runs = [run_dict(run, snapshot.tasks, now) for run in snapshot.runs]
    attention = [
        row
        for row in runs
        if recent(row["changed_at"], now)
        and (
            row["stage"].startswith(("failed", "landing "))
            or any(
                worker["stage"]
                in {"failed", "timeout", "refused", "cancelled", "launch-failed"}
                for worker in row["workers"]
            )
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

    open_runs = [
        row for row in runs if not row["accepted"] and row["stage"] != "abandoned"
    ]
    landed = [row for row in runs if row["accepted"]]
    lines.append(
        f"== runs: {len(open_runs)} open, {len(landed)} landed, "
        f"{len(runs) - len(open_runs) - len(landed)} abandoned"
    )
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


# ---------------------------------------------------------------- CLI output


class Output:
    """One place that decides what stdout and stderr carry."""

    def __init__(self, *, as_json: bool, full: bool) -> None:
        self.as_json = as_json
        self.full = full
        self.now = datetime.now(UTC)

    def read(self, document: Any, text: str | None = None) -> None:
        """A read: the table a person reads, or the document with ``--json``."""
        if self.as_json or text is None:
            print(json.dumps(document, indent=2, sort_keys=True))
        else:
            print(text)

    def write(self, document: Any, summary: str) -> None:
        """A write: the document on stdout, one summary line on stderr."""
        print(json.dumps(document, indent=2, sort_keys=True))
        print(summary, file=sys.stderr)

    def run(self, run_id: str) -> str:
        return run_id if self.full else short_run_id(run_id)

    def sha(self, value: Any) -> str:
        text = str(value or "")
        if not text:
            return "-"
        return text if self.full else text[:SHORT_ID]

    def when(self, stamp: str | None, ended: str | None = None) -> str:
        """Local clock and age, e.g. ``14:02 3m``."""
        until = parse_stamp(ended) or self.now
        return f"{local_clock(stamp)} {age(stamp, until)}"

    def clock(self, stamp: str | None) -> str:
        """Local clock, with the date when the moment is not today."""
        moment = parse_stamp(stamp)
        if moment is None:
            return "?"
        local = moment.astimezone()
        if local.date() == self.now.astimezone().date():
            return local.strftime("%H:%M")
        return local.strftime("%m-%d %H:%M")

    def job_line(self, job: Mapping[str, Any]) -> str:
        started = job.get("started_at") or job.get("enqueued_at")
        ended = job.get("ended_at")
        when = (
            f"finished {local_clock(ended)} after {age(started, parse_stamp(ended) or self.now)}"
            if ended
            else f"since {local_clock(started)} ({age(started, self.now)})"
        )
        exit_text = (
            f" exit {job['exit_code']}" if job.get("exit_code") not in (None, 0) else ""
        )
        scratch = job.get("scratch")
        scratch_text = (
            f"; scratch {scratch['kind']} {scratch['bytes']} bytes in "
            f"{scratch['files']} file(s)"
            + (" (measurement truncated)" if scratch.get("truncated") else "")
            if isinstance(scratch, Mapping)
            else ""
        )
        return (
            f"job {job['job_id']} {job['label']} {job['phase']}{exit_text} "
            f"{when}{scratch_text}"
        )

    def jobs_table(self, rows: Sequence[Mapping[str, Any]]) -> str:
        if not rows:
            return "(no jobs)"
        return table(
            ("id", "label", "phase", "started", "age", "exit", "cwd"),
            [
                (
                    row["job_id"],
                    row["label"],
                    row["phase"],
                    self.clock(row.get("started_at") or row.get("enqueued_at")),
                    age(
                        row.get("started_at") or row.get("enqueued_at"),
                        parse_stamp(row.get("ended_at")) or self.now,
                    ),
                    "" if row.get("exit_code") is None else row["exit_code"],
                    row.get("path", ""),
                )
                for row in rows
            ],
        )

    def run_lines(self, document: Mapping[str, Any]) -> str:
        workers = ", ".join(
            f"{worker['id']}[{worker.get('stage') or ('task ' + str(worker.get('task_id')) if worker.get('task_id') is not None else 'external')}]"
            for worker in document["workers"]
        )
        landing = document["landing"]
        lines = [
            f"run {self.run(document['run_id'])} {document['project']} {document['harness']} "
            f"base {self.sha(document['base_commit'])} stage {document.get('stage', '-')} "
            f"started {self.when(document.get('created_at'))}",
            f"workers: {workers}",
        ]
        for worker in document["workers"]:
            prompt = worker.get("prompt_path") or (
                f"{worker['worktree']}/.agentctl/prompt.md"
                if worker.get("worktree")
                else "-"
            )
            lines.append(f"  {worker['id']}: prompt {prompt}")
            if document["harness"] == "external" and not worker.get("result"):
                result = worker.get("result_path") or (
                    f"{worker['worktree']}/.agentctl/prompt.result.json"
                    if worker.get("worktree")
                    else "<result.json>"
                )
                lines.append(
                    f"    next: agentctl batch result {document['run_id']} "
                    f"{worker['id']} {result}"
                )
        lines.append(
            f"landing: task {landing.get('task_id')} candidate {self.sha(landing.get('candidate_sha'))}"
            f"{' PR #' + str(landing['pr_number']) if landing.get('pr_number') else ''}"
            f"{' failure ' + landing['failure']['code'] if landing.get('failure') else ''}"
        )
        return "\n".join(lines)

    def runs_table(self, rows: Sequence[Mapping[str, Any]]) -> str:
        if not rows:
            return "(no runs)"
        return table(
            ("run", "harness", "stage", "started", "age", "workers", "candidate"),
            [
                (
                    self.run(row["run_id"]),
                    row["harness"],
                    row["stage"],
                    local_clock(row.get("created_at")),
                    age(row.get("created_at"), self.now),
                    " ".join(f"{w['id']}:{w['stage']}" for w in row["workers"]),
                    self.sha(row["landing"].get("candidate_sha")),
                )
                for row in rows
            ],
        )
