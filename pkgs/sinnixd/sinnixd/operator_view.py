"""The operator's one screen: queue, lanes, PRs, ready work.

Assembled from `pueue status --json`, `wt list --format=json`,
`gh pr list --json` and `bd ready --json`; rendered as text in local time.
Every "next" here is a description of the mechanical state, not a decision:
nothing in this module dispatches.
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
        agents = agents_by_bead(self.tasks)
        return {
            "schema": "sinnix.agentctl.view.v2",
            "project": self.project_id,
            "at": self.now.isoformat(),
            "groups": {
                name: {"status": status, **_group_counts(self.tasks, name)}
                for name, status in sorted(self.groups.items())
            },
            "jobs": [job_view(task) for task in self.tasks],
            "lanes": [lane_dict(row, agents.get(row.bead or ""), self.now) for row in self.lanes],
            "ready": [
                {"id": bead.get("id"), "title": bead.get("title"), "type": bead.get("issue_type")}
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
        elif status and status != "COMPLETED":
            outcomes.append("pending")
        else:
            outcomes.append("pending")
    if "fail" in outcomes:
        return "fail"
    if "pending" in outcomes:
        return "pending"
    return "pass"


def pr_summary(pull: Mapping[str, Any] | None) -> dict[str, Any] | None:
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
        "updated_at": pull.get("updatedAt"),
    }


def agents_by_bead(tasks: Sequence[Task]) -> dict[str, Task]:
    """The newest lane or rebase task per bead."""
    newest: dict[str, Task] = {}
    for task in tasks:
        parts = task.label.split(":")
        if len(parts) == 3 and parts[1] in {"lane", "rebase"}:
            current = newest.get(parts[2])
            if current is None or task.task_id > current.task_id:
                newest[parts[2]] = task
    return newest


def lane_stage(row: LaneRow, agent: Task | None) -> tuple[str, str]:
    """(stage, next): what the lane's facts say it is, and what follows mechanically."""
    tree = row.worktree
    pull = pr_summary(row.pr)
    if tree.integrated or (pull and pull["state"] == "MERGED"):
        return "merged", "lane sync"
    if pull and pull["state"] == "OPEN":
        if pull["mergeable"] == "CONFLICTING":
            return "conflicting", "lane rebase"
        if pull["checks"] == "fail":
            return "checks failing", "fix in lane, push"
        if pull["checks"] == "pending":
            return "checks running", "wait"
        if pull["review"] == "CHANGES_REQUESTED":
            return "changes requested", "fix in lane, push"
        if pull["auto_merge"]:
            return "auto-merge armed", "wait for merge"
        return "pr open", "gh pr merge --auto --squash"
    if pull and pull["state"] == "CLOSED":
        return "pr closed", "lane sync or restart"
    if agent is not None:
        phase = job_view(agent)["phase"]
        kind = agent.label.split(":")[1]
        if phase in {"queued", "paused"}:
            return f"{kind} {phase}", "wait"
        if phase == "running":
            return f"{kind} running", "wait"
        if phase == "succeeded":
            return "unpublished", "lane publish"
        return f"{kind} {phase}", "job logs, then lane rebase"
    return "idle", "lane rebase or publish"


def lane_dict(row: LaneRow, agent: Task | None, now: datetime) -> dict[str, Any]:
    tree = row.worktree
    stage, following = lane_stage(row, agent)
    since = agent.started_at or agent.enqueued_at if agent else None
    return {
        "lane": tree.path.name if tree.path else tree.branch,
        "branch": tree.branch,
        "worktree": str(tree.path) if tree.path else None,
        "bead": row.bead,
        "stage": stage,
        "next": following,
        "since": since,
        "elapsed": age(since, now) if since else None,
        "dirty": tree.dirty,
        "wt_state": tree.state,
        "head": tree.head,
        "agent": job_view(agent) if agent else None,
        "pr": pr_summary(row.pr),
    }


def _group_counts(tasks: Sequence[Task], group: str) -> dict[str, int]:
    counts = Counter(task.status.lower() for task in tasks if task.group == group and not task.terminal)
    return {"running": counts.get("running", 0), "queued": counts.get("queued", 0), "paused": counts.get("paused", 0)}


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
    lines = [f"== {snapshot.project_id} at {now.astimezone().strftime('%Y-%m-%d %H:%M')}"]
    lines.extend(f"  ! {error}" for error in snapshot.errors)

    group_text = []
    for group, status in sorted(snapshot.groups.items()):
        counts = _group_counts(snapshot.tasks, group)
        detail = " ".join(f"{count} {state}" for state, count in counts.items() if count)
        group_text.append(f"{group} {detail or 'idle'}{' PAUSED' if status == 'Paused' else ''}")
    lines.append("== queue: " + (" · ".join(group_text) or "pueue unavailable"))

    failed = [
        task
        for task in snapshot.tasks
        if task.terminal and not task.succeeded and task.result != "Killed"
    ]
    failed.sort(key=lambda task: task.ended_at or "", reverse=True)
    agents = agents_by_bead(snapshot.tasks)
    lane_facts = [(row, lane_stage(row, agents.get(row.bead or ""))) for row in snapshot.lanes]
    attention = [
        (row, stage) for row, (stage, _next) in lane_facts
        if stage in {"conflicting", "checks failing", "changes requested"} or stage.endswith(("failed", "timed-out", "refused", "cancelled"))
    ]
    if failed or attention:
        lines.append("== needs attention")
        for task in failed[:MAX_FAILED_SHOWN]:
            exit_text = f" exit {task.exit_code}" if task.exit_code is not None else ""
            lines.append(
                f"  ! job {task.task_id} {task.label} {job_view(task)['phase']}{exit_text}"
                f" at {local_clock(task.ended_at)} ({age(task.ended_at, now)} ago)"
            )
        for row, stage in attention:
            name = row.worktree.path.name if row.worktree.path else row.worktree.branch
            pull = pr_summary(row.pr)
            pr_text = f" PR #{pull['number']}" if pull else ""
            lines.append(f"  ! {name} {stage}{pr_text}")
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
            ).replace("\n", "\n  ").join(("  ", ""))
        )

    lines.append(f"== lanes: {len(snapshot.lanes)}")
    if lane_facts:
        rows = []
        for row, (stage, following) in sorted(lane_facts, key=lambda item: item[0].worktree.branch or ""):
            agent = agents.get(row.bead or "")
            since = (agent.started_at or agent.enqueued_at) if agent else None
            pull = pr_summary(row.pr)
            pr_text = (
                f"#{pull['number']} {str(pull['state']).lower()} checks:{pull['checks']}"
                f"{' auto' if pull['auto_merge'] else ''}"
                if pull
                else "-"
            )
            rows.append(
                (
                    row.worktree.path.name if row.worktree.path else row.worktree.branch,
                    row.bead or "",
                    stage + (" dirty" if row.worktree.dirty else ""),
                    f"{local_clock(since)} {age(since, now)}" if since else "-",
                    f"#{agent.task_id}" if agent else "-",
                    pr_text,
                    following,
                )
            )
        lines.append(
            table(("lane", "bead", "stage", "since", "job", "pr", "next"), rows)
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


__all__ = ["Snapshot", "collect", "render", "table", "age", "local_clock", "lane_stage"]
