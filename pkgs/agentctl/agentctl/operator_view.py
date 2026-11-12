"""What the operator reads: the one screen, and the CLI's output.

Assembled from `pueue status --json` and `bd ready --json`, each read from
its owner on every call; rendered as text in local time. Nothing in this
module dispatches.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import job_queries, pueue
from .config import Config
from .job_queries import job_view
from .limits import CALL_TIMEOUT_SECONDS
from .projects import ProjectAdapter
from .pueue import PueueError, Task

MAX_READY_SHOWN = 8
MAX_FAILED_SHOWN = 6
# A failure older than this has been seen; the screen shows recent ones.
ATTENTION_SECONDS = 6 * 3_600
# Bead types the ready list leaves out: neither is a unit of work.
UNREADY_TYPES = frozenset({"epic", "decision"})
DEFAULT_JOB_ROWS = 40


class TaskReadError(ValueError):
    """`bd ready` failed or returned something other than a list of beads."""


def ready_beads(root: Path, executable: str = "bd") -> list[Mapping[str, Any]]:
    """Beads' ready list for the project; `bd` finds its database from the cwd."""
    try:
        result = subprocess.run(
            [executable, "ready", "--limit", "0", "--json"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )
        value = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError) as error:
        raise TaskReadError(f"bd ready failed in {root}") from error
    except json.JSONDecodeError as error:
        raise TaskReadError("bd ready returned invalid JSON") from error
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in value
    ):
        raise TaskReadError("bd ready returned an invalid bead list")
    return value


# ---------------------------------------------------------------- screen


@dataclass(frozen=True)
class Snapshot:
    project_id: str
    now: datetime
    tasks: tuple[Task, ...]
    groups: Mapping[str, str]
    ready: tuple[Mapping[str, Any], ...]
    errors: tuple[str, ...] = field(default_factory=tuple)
    # Whether `tasks` is the queue's answer.
    queue_read: bool = True
    # Global active counts and nominal width from the same queue response.
    # Missing metadata is unknown, never inferred from project-only tasks.
    global_groups: Mapping[str, Mapping[str, int | None]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "sinnix.agentctl.view.v4",
            "project": self.project_id,
            "at": self.now.isoformat(),
            "queue_read": self.queue_read,
            "groups": {
                name: {
                    "status": status,
                    "scope": "project",
                    **_group_counts(self.tasks, name),
                    "global": self.global_groups.get(name) if self.queue_read else None,
                }
                for name, status in sorted(self.groups.items())
            },
            "jobs": [job_view(task) for task in self.tasks],
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


def _group_counts(
    tasks: Sequence[Task],
    group: str,
) -> dict[str, int]:
    counts = Counter(
        task.status.lower()
        for task in tasks
        if task.group == group and not task.terminal
    )
    return {
        "running": counts.get("running", 0),
        "queued": counts.get("queued", 0),
        "paused": counts.get("paused", 0),
        "stashed": counts.get("stashed", 0),
    }


def job_state(task: Task) -> str:
    """Pueue's actual state, including normal dependencies and stashes."""
    return task.status.lower()


def collect(
    config: Config, project: ProjectAdapter, *, now: datetime | None = None
) -> Snapshot:
    errors: list[str] = []
    prefix = f"{project.project_id}:"
    queue_read = True
    try:
        queue = pueue.status()
        every = tuple(sorted(queue.tasks.values(), key=lambda item: item.task_id))
        groups = {
            name: str(detail.get("status") or "")
            for name, detail in queue.groups.items()
        }
        global_groups: dict[str, dict[str, int | None]] = {}
        for name, detail in queue.groups.items():
            parallel = detail.get("parallel_tasks")
            global_groups[name] = {
                **_group_counts(every, name),
                "parallel": parallel
                if isinstance(parallel, int) and not isinstance(parallel, bool)
                else None,
            }
        tasks = tuple(task for task in every if task.label.startswith(prefix))
    except PueueError as error:
        tasks, groups, queue_read = (), {}, False
        global_groups = {}
        errors.append(f"pueue: {error}")
    try:
        ready = tuple(
            bead
            for bead in ready_beads(project.root)
            if str(bead.get("issue_type") or "") not in UNREADY_TYPES
        )
    except TaskReadError as error:
        ready = ()
        errors.append(f"bd: {error}")
    return Snapshot(
        project_id=project.project_id,
        now=now or datetime.now(UTC),
        tasks=tasks,
        groups=groups,
        ready=ready,
        errors=tuple(errors),
        queue_read=queue_read,
        global_groups=global_groups,
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
        global_counts = (
            snapshot.global_groups.get(group) if snapshot.queue_read else None
        )
        if global_counts is None:
            global_detail = "unknown"
        else:
            global_detail = (
                " ".join(
                    f"{global_counts[state]} {state}"
                    for state in ("running", "queued", "paused", "stashed")
                    if global_counts.get(state)
                )
                or "idle"
            )
            parallel = global_counts.get("parallel")
            global_detail += f", parallel {parallel if parallel is not None else '?'}"
        group_text.append(
            f"{group} global {global_detail}; {snapshot.project_id} {detail or 'idle'}"
            f"{' PAUSED' if status == 'Paused' else ''}"
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
    if failed:
        lines.append("== needs attention")
        for task in failed[:MAX_FAILED_SHOWN]:
            exit_text = f" exit {task.exit_code}" if task.exit_code is not None else ""
            lines.append(
                f"  ! job {task.task_id} {task.label} {job_queries.phase_of(task)}{exit_text}"
                f" at {local_clock(task.ended_at)} ({age(task.ended_at, now)} ago)"
            )
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
                        job_state(task),
                        local_clock(task.started_at or task.enqueued_at),
                        age(task.started_at or task.enqueued_at, now),
                    )
                    for task in active
                ],
            )
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

    def __init__(self, *, as_json: bool) -> None:
        self.as_json = as_json
        self.now = datetime.now(UTC)

    def read(self, document: Any, text: str | None = None) -> None:
        """A read: the table a person reads, or the document with ``--json``."""
        if self.as_json or text is None:
            print(json.dumps(document, indent=2, sort_keys=True))
        else:
            print(text)

    def write(self, document: Any, summary: str) -> None:
        """A write: the document on stdout, one summary line on stderr.

        Off a terminal the document is one line: timer units send stdout to
        the journal, where each indented line became its own entry.
        """
        indent = 2 if sys.stdout.isatty() else None
        print(json.dumps(document, indent=indent, sort_keys=True))
        print(summary, file=sys.stderr)

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
        # A blocking wait can outlive the command-start snapshot.
        now = datetime.now(UTC)
        started = job.get("started_at") or job.get("enqueued_at")
        ended = job.get("ended_at")
        when = (
            f"finished {local_clock(ended)} after {age(started, parse_stamp(ended) or now)}"
            if ended
            else f"since {local_clock(started)} ({age(started, now)})"
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
        selection_text = ""
        if any(
            key in job
            for key in (
                "descriptor_path",
                "project_root",
                "working_directory",
                "timeout_seconds",
            )
        ):
            timeout = job.get("timeout_seconds")
            budget = (
                "no runtime deadline"
                if timeout == 0
                else f"{timeout}s"
                if timeout is not None
                else "unknown"
            )
            selection_text = (
                f"; descriptor {job.get('descriptor_path', 'unknown')}"
                f"; descriptor root {job.get('project_root', 'unknown')}"
                f"; workspace {job.get('working_directory', 'unknown')}"
                f"; timeout {budget}"
            )
        queue_text = ""
        queue = job.get("queue")
        if isinstance(queue, Mapping):
            queue_text = (
                f"; pool {queue['group']}: {queue.get('reason', queue.get('status'))}"
            )
            entries = list(queue.get("occupied_by") or [])
            ahead = set(queue.get("ahead") or [])
            entries.extend(
                entry
                for entry in queue.get("queued") or []
                if entry["task_id"] in ahead
            )
            if entries:
                queue_text += "; waiting behind " + ", ".join(
                    f"job {entry['task_id']} {entry.get('job_id') or entry.get('label')} priority {entry.get('priority', 0)} "
                    f"({entry.get('project', '')} {entry.get('working_directory', '')})"
                    for entry in entries
                )
            if queue.get("waiting_for"):
                queue_text += "; dependencies " + ", ".join(
                    map(str, queue["waiting_for"])
                )
        return (
            f"job {job['task_id']} {job['label']} {job['phase']}{exit_text} "
            f"{when}{scratch_text}{selection_text}{queue_text}"
        )

    def jobs_table(self, rows: Sequence[Mapping[str, Any]]) -> str:
        if not rows:
            return "(no jobs)"
        return table(
            ("id", "label", "pool", "phase", "started", "age", "exit", "cwd"),
            [
                (
                    row["task_id"],
                    row["label"],
                    row.get("group", ""),
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
