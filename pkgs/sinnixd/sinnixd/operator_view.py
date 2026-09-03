"""The operator's one screen: queue, lanes, PRs, ready work.

Assembled from `pueue status --json`, `wt list --format=json --full`,
`gh pr list --json` and `bd ready --json`; rendered as text. Nothing here
decides anything.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from . import pueue
from .config import Config
from .launch import job_view
from .lanes import LaneRow, lane_rows
from .packets import PacketError, SubprocessBdReader
from .projects import ProjectAdapter
from .pueue import PueueError, Task
from .worktrunk import WorktrunkError

MAX_READY_SHOWN = 8
MAX_FAILED_SHOWN = 6


@dataclass(frozen=True)
class Snapshot:
    project_id: str
    now: datetime
    tasks: tuple[Task, ...]
    groups: Mapping[str, str]
    lanes: tuple[LaneRow, ...]
    ready: tuple[Mapping[str, Any], ...]
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "sinnix.agentctl.view.v2",
            "project": self.project_id,
            "at": self.now.isoformat(),
            "groups": dict(self.groups),
            "jobs": [job_view(task) for task in self.tasks],
            "lanes": [_lane_dict(row) for row in self.lanes],
            "ready": [
                {"id": bead.get("id"), "title": bead.get("title"), "type": bead.get("issue_type")}
                for bead in self.ready
            ],
            "errors": list(self.errors),
        }


def _lane_dict(row: LaneRow) -> dict[str, Any]:
    tree = row.worktree
    return {
        "branch": tree.branch,
        "worktree": str(tree.path) if tree.path else None,
        "bead": row.bead,
        "state": tree.state,
        "dirty": tree.dirty,
        "head": tree.head,
        "pr": _pr_summary(row.pr),
    }


def _checks(pull: Mapping[str, Any]) -> str:
    rollup = pull.get("statusCheckRollup")
    if not isinstance(rollup, list) or not rollup:
        return "none"
    outcomes: list[str] = []
    for check in rollup:
        if not isinstance(check, Mapping):
            continue
        verdict = str(check.get("conclusion") or check.get("state") or "").upper()
        status = str(check.get("status") or "").upper()
        if verdict in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
            outcomes.append("pass")
        elif verdict in {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
            outcomes.append("fail")
        elif status and status != "COMPLETED" or verdict in {"PENDING", "EXPECTED", ""}:
            outcomes.append("pending")
        else:
            outcomes.append("pending")
    if "fail" in outcomes:
        return "fail"
    if "pending" in outcomes:
        return "pending"
    return "pass"


def _pr_summary(pull: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if pull is None:
        return None
    return {
        "number": pull.get("number"),
        "state": pull.get("state"),
        "url": pull.get("url"),
        "draft": bool(pull.get("isDraft")),
        "mergeable": pull.get("mergeable"),
        "review": pull.get("reviewDecision") or None,
        "checks": _checks(pull),
        "auto_merge": bool(pull.get("autoMergeRequest")),
    }


def collect(config: Config, project: ProjectAdapter, *, now: datetime | None = None) -> Snapshot:
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
    try:
        lanes = tuple(lane_rows(project, full=False))
    except (WorktrunkError, PacketError, RuntimeError) as error:
        lanes = ()
        errors.append(f"lanes: {error}")
    try:
        ready = tuple(SubprocessBdReader(project.root).ready())
    except PacketError as error:
        ready = ()
        errors.append(f"bd: {error}")
    return Snapshot(
        project_id=project.project_id,
        now=now or datetime.now(UTC),
        tasks=tasks,
        groups=groups,
        lanes=lanes,
        ready=ready,
        errors=tuple(errors),
    )


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _age(stamp: str | None, now: datetime) -> str:
    moment = _parse(stamp)
    if moment is None:
        return "?"
    seconds = int((now - moment).total_seconds())
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}"


def _task_rows(tasks: Sequence[Task], *, terminal: bool) -> list[Task]:
    return [task for task in tasks if task.terminal is terminal]


def render(snapshot: Snapshot) -> str:
    now = snapshot.now
    lines = [f"== {snapshot.project_id} at {now.astimezone().strftime('%Y-%m-%d %H:%M')}"]
    lines.extend(f"  ! {error}" for error in snapshot.errors)

    active = _task_rows(snapshot.tasks, terminal=False)
    by_group: dict[str, Counter[str]] = {}
    for task in active:
        by_group.setdefault(task.group, Counter())[task.status.lower()] += 1
    group_text = []
    for group, status in sorted(snapshot.groups.items()):
        counts = by_group.get(group, Counter())
        detail = " ".join(f"{count} {state}" for state, count in sorted(counts.items()))
        group_text.append(
            f"{group} {detail or 'idle'}{' PAUSED' if status == 'Paused' else ''}"
        )
    lines.append("== queue: " + (" · ".join(group_text) or "pueue unavailable"))

    failed = [
        task
        for task in _task_rows(snapshot.tasks, terminal=True)
        if not task.succeeded and task.result != "Killed"
    ]
    failed.sort(key=lambda task: task.ended_at or "", reverse=True)
    conflicting = [
        row for row in snapshot.lanes if row.pr and row.pr.get("mergeable") == "CONFLICTING"
    ]
    red = [row for row in snapshot.lanes if row.pr and _checks(row.pr) == "fail"]
    if failed or conflicting or red:
        lines.append("== needs attention")
        for task in failed[:MAX_FAILED_SHOWN]:
            lines.append(
                f"  ! job {task.task_id} {task.label} {job_view(task)['phase']}"
                f"{f' exit {task.exit_code}' if task.exit_code is not None else ''}"
                f" ({_age(task.ended_at, now)} ago)"
            )
        for row in conflicting:
            lines.append(f"  ! PR #{row.pr['number']} {row.worktree.branch} CONFLICTING")
        for row in red:
            if row in conflicting:
                continue
            lines.append(f"  ! PR #{row.pr['number']} {row.worktree.branch} checks failing")
    else:
        lines.append("== nothing needs attention")

    lines.append(f"== jobs: {len(active)} active")
    for task in active:
        lines.append(
            f"  {task.task_id:>4} {task.label[:40]:40} {task.status.lower():8}"
            f" {_age(task.started_at or task.enqueued_at, now):>6}"
        )

    agent_by_bead: dict[str, Task] = {}
    for task in snapshot.tasks:
        parts = task.label.split(":")
        if len(parts) == 3 and parts[1] in {"lane", "rebase"}:
            current = agent_by_bead.get(parts[2])
            if current is None or task.task_id > current.task_id:
                agent_by_bead[parts[2]] = task
    lines.append(f"== lanes: {len(snapshot.lanes)}")
    for row in sorted(snapshot.lanes, key=lambda item: item.worktree.branch or ""):
        tree = row.worktree
        name = tree.path.name if tree.path else (tree.branch or "?")
        agent = agent_by_bead.get(row.bead or "")
        agent_text = (
            f"{agent.label.split(':')[1]} {job_view(agent)['phase']} #{agent.task_id}"
            if agent
            else "-"
        )
        pull = _pr_summary(row.pr)
        pr_text = (
            f"PR #{pull['number']} {pull['state']} checks:{pull['checks']}"
            f"{' ' + str(pull['mergeable']).lower() if pull['mergeable'] else ''}"
            f"{' auto' if pull['auto_merge'] else ''}"
            if pull
            else "no PR"
        )
        state = f"{tree.state}{' dirty' if tree.dirty else ''}"
        lines.append(
            f"  {name[:36]:36} {str(row.bead or '')[:18]:18} {state[:18]:18} {agent_text[:26]:26} {pr_text}"
        )

    lines.append(f"== ready: {len(snapshot.ready)} beads")
    for bead in snapshot.ready[:MAX_READY_SHOWN]:
        lines.append(
            f"  {str(bead.get('id') or ''):18} {str(bead.get('issue_type') or ''):8} "
            f"{str(bead.get('title') or '')[:70]}"
        )
    return "\n".join(lines)


__all__ = ["Snapshot", "collect", "render"]
