"""The one computation behind every operator view.

``compute`` is a pure function of collected facts, the stored "last looked"
time and the clock. Every string it emits is assembled from those facts; a
sentence an agent wrote (a commit subject, a task title) appears only as a
quoted field next to the commit or task that carries it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from . import SCHEMA, claims, sessions
from .history import (
    SIZES,
    bead_kind,
    bead_own_range,
    bead_size,
    estimate_range,
    parse_time,
    summarize,
)

# A running job is overdue beyond twice the upper end of its usual range, and
# at least ten minutes past it, once enough runs back the range.
OVERRUN_FACTOR = 2.0
OVERRUN_MARGIN_SECONDS = 600
OVERRUN_MIN_SAMPLES = 5
SILENT_SECONDS = 1800
REPEAT_FAILURES = 3
REPEAT_WINDOW_SECONDS = 2 * 3600
# A streak whose last failure is older than this is no longer a loop.
REPEAT_LAST_SECONDS = 3600
EARLIER_FINISHED_ROWS = 15
RECENT_JOB_ROWS = 20


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def age(value: Any, now: datetime) -> int | None:
    moment = parse_time(value)
    return max(0, int((now - moment).total_seconds())) if moment else None


def span(seconds: float | int | None) -> str:
    if seconds is None:
        return "?"
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{round(seconds / 60)}m"
    if seconds < 2 * 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def range_text(summary: Mapping[str, Any] | None) -> str:
    """A range with its backing, for example ``2m to 9m (212 successful runs)``."""
    if not summary or not summary.get("samples"):
        return f"no history ({(summary or {}).get('basis', 'no samples')})"
    text = (
        f"{span(summary['low_seconds'])} to {span(summary['high_seconds'])}, "
        f"median {span(summary['median_seconds'])} "
        f"({summary['samples']} {summary['basis']})"
    )
    return text + (" [few samples]" if summary.get("thin") else "")


# ---------------------------------------------------------------- waiting


def waiting_rows(inputs: Mapping[str, Any], now: datetime) -> list[dict[str, Any]]:
    rows = []
    for project, beads in sorted((inputs.get("beads") or {}).items()):
        for item in beads.get("human") or []:
            since = item.get("updated_at") or item.get("created_at")
            rows.append(
                {
                    "source": "beads",
                    "project": project,
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "priority": item.get("priority"),
                    "since": item.get("created_at"),
                    "age_seconds": age(item.get("created_at"), now),
                    "updated_at": since,
                    "answer_with": f"bd human respond {item.get('id')}",
                }
            )
    for item in (inputs.get("plannotator") or {}).get("items") or []:
        rows.append(
            {
                "source": "plannotator",
                "project": item.get("project"),
                "id": item.get("id"),
                "title": item.get("title"),
                "priority": None,
                "since": item.get("since"),
                "age_seconds": age(item.get("since"), now),
            }
        )
    rows.sort(
        key=lambda row: (
            row["priority"] is None,
            row["priority"] or 0,
            -(row["age_seconds"] or 0),
        )
    )
    return rows


# ---------------------------------------------------------------- running


def wait_text(job: Mapping[str, Any], now: datetime) -> str | None:
    wait = job.get("wait")
    if not isinstance(wait, dict):
        wait = {}
    group = wait.get("group") or job.get("group")
    reason = wait.get("reason")

    def named(items: Any) -> str:
        parts = []
        for item in items or []:
            running = age(item.get("started_at"), now)
            parts.append(
                f"{item.get('label')} (#{item.get('task_id')}"
                + (f", running {span(running)}" if running is not None else "")
                + ")"
            )
        return ", ".join(parts)

    if isinstance(job.get("deferred"), dict):
        deferred = job["deferred"]
        return f"deferred until {deferred.get('until')}: {deferred.get('reason')}"
    if str(job.get("phase")) == "stashed":
        return "held in the queue (stashed)"
    if reason == "memory":
        line = f"waiting for memory: needs {wait.get('memory_mib')} MiB"
        if wait.get("free_mib") is not None:
            line += f", {wait.get('free_mib')} of {wait.get('ceiling_mib')} MiB free"
        if isinstance(wait.get("behind"), dict):
            line += f", behind {named([wait['behind']])}"
        return line
    if reason == "deferred":
        return "deferred by its starter"
    if reason == "group-paused":
        return f"pool {group} is paused in the queue"
    if reason == "dependencies":
        return "waits for job " + ", ".join(
            f"#{dep}" for dep in wait.get("waiting_for") or []
        )
    if reason == "pool-full":
        return f"pool {group} full behind {named(wait.get('occupied_by'))}"
    if reason == "priority-order":
        return f"position {wait.get('position')} in pool {group} behind {named(wait.get('ahead'))}"
    if reason == "ready":
        return f"next to start in pool {group}"
    return str(reason) if reason else None


def job_range(inputs: Mapping[str, Any], label: str) -> dict[str, Any]:
    history = inputs.get("job_history") or {}
    runs = (history.get("run_seconds") or {}).get(label) or []
    summary = summarize(runs, f"successful runs of {label}")
    other = (history.get("task_runner_seconds") or {}).get(label) or []
    if other:
        summary["task_runner"] = summarize(other, f"passed task-runner runs of {label}")
    return summary


def running_rows(
    inputs: Mapping[str, Any], now: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Unfinished jobs: (running, queued), each saying what and for whom."""
    jobs = (inputs.get("jobs") or {}).get("jobs") or []
    running, queued = [], []
    for job in jobs:
        if not isinstance(job, dict) or job.get("terminal") is True:
            continue
        phase = str(job.get("phase") or "")
        since = job.get("started_at") if phase == "running" else job.get("enqueued_at")
        label = str(job.get("label") or "")
        row = {
            "project": job.get("project"),
            "operation": job.get("operation"),
            "label": label,
            "task_id": job.get("task_id"),
            "job_id": job.get("job_id"),
            "attempt": job.get("attempt"),
            "phase": phase,
            "pool": job.get("group"),
            "command": job.get("command"),
            "working_directory": job.get("working_directory") or job.get("path"),
            "caller": job.get("caller"),
            "since": since,
            "seconds": age(since, now),
            "expected": job_range(inputs, label),
            "expected_target": job.get("expected_target"),
            "log_idle_seconds": job.get("log_idle_seconds"),
        }
        if job.get("announce") is True:
            row["announce"] = True
            row["revision"] = job.get("revision")
        if isinstance(job.get("deferred"), dict):
            row["deferred"] = job["deferred"]
        if phase == "running":
            running.append(row)
        else:
            row["waiting_because"] = wait_text(job, now)
            queued.append(row)
    running.sort(key=lambda row: -(row["seconds"] or 0))
    queued.sort(key=lambda row: -(row["seconds"] or 0))
    return running, queued


# ---------------------------------------------------------------- stalled


def stalled_rows(
    inputs: Mapping[str, Any], running: list[dict[str, Any]], now: datetime
) -> list[dict[str, Any]]:
    rows = []
    for job in running:
        expected, seconds = job["expected"], job["seconds"]
        base = {
            "project": job["project"],
            "label": job["label"],
            "task_id": job["task_id"],
            "job_id": job["job_id"],
        }
        if (
            seconds is not None
            and expected.get("samples", 0) >= OVERRUN_MIN_SAMPLES
            and seconds
            > max(
                expected["high_seconds"] * OVERRUN_FACTOR,
                expected["high_seconds"] + OVERRUN_MARGIN_SECONDS,
            )
        ):
            rows.append(
                {
                    **base,
                    "signal": "overrun",
                    "text": f"{job['label']} (#{job['task_id']}) has run {span(seconds)}; "
                    f"its usual range is {range_text(expected)}",
                }
            )
        idle = job.get("log_idle_seconds")
        if isinstance(idle, (int, float)) and idle >= SILENT_SECONDS:
            rows.append(
                {
                    **base,
                    "signal": "silent",
                    "text": f"{job['label']} (#{job['task_id']}) holds a slot in pool "
                    f"{job['pool']} and has written no output for {span(idle)}",
                }
            )
    recent = (inputs.get("job_history") or {}).get("recent") or []
    streaks: dict[tuple[Any, Any], dict[str, Any]] = {}
    for event in recent:  # oldest first
        key = (event.get("label"), event.get("working_directory"))
        ended = age(event.get("ended_at"), now)
        if (
            event.get("outcome") == "success"
            or ended is None
            or ended > REPEAT_WINDOW_SECONDS
        ):
            streaks.pop(key, None)
            continue
        if event.get("outcome") in {"cancelled", "refused"}:
            continue
        streak = streaks.setdefault(
            key, {"count": 0, "exit_codes": set(), "event": event}
        )
        streak["count"] += 1
        streak["exit_codes"].add(event.get("exit_code"))
        streak["event"] = event
    for (label, directory), streak in streaks.items():
        event = streak["event"]
        if (
            streak["count"] >= REPEAT_FAILURES
            and len(streak["exit_codes"]) == 1
            and (age(event.get("ended_at"), now) or 0) <= REPEAT_LAST_SECONDS
        ):
            rows.append(
                {
                    "project": event.get("project"),
                    "label": label,
                    "task_id": event.get("task_id"),
                    "job_id": event.get("job_id"),
                    "signal": "repeated-failure",
                    "text": f"{label} failed {streak['count']} times in a row in {directory} "
                    f"with exit {event.get('exit_code')}, last at {event.get('ended_at')}",
                }
            )
    return rows


# ---------------------------------------------------------------- finished


def change_rows(
    inputs: Mapping[str, Any], memory: dict[str, Any], now: datetime
) -> list[dict[str, Any]]:
    """Every recent change on a default branch with its computed state.

    ``finished`` needs the change on the default branch, its check passed (or
    none reported), and, where the product is deployed on this machine, the
    running revision containing it. ``merged_not_live`` is the same change
    before the running revision contains it.
    """
    deployed = inputs.get("deployed") or {}
    deployment_known = bool(deployed.get("host_revision"))
    pulls = inputs.get("pulls") or {}
    finished_at: dict[str, str] = memory.setdefault("finished_at", {})
    seeded: list[str] = memory.setdefault("seeded_projects", [])
    rows = []
    for project, git in sorted((inputs.get("git") or {}).items()):
        commits = git.get("commits") or []
        hosted = pulls.get(project) or {}
        by_commit = {
            pull.get("merge_commit"): pull
            for pull in hosted.get("merged") or []
            if pull.get("merge_commit")
        }
        deployment = (deployed.get("projects") or {}).get(project) or {"kind": "none"}
        contained = deployment.get("contains")
        # Before a project's first full observation nothing is known about
        # when its changes went live, so they take their merge time.
        first_observation = project not in seeded
        complete = deployment_known and "merged" in hosted
        seen_keys = set()
        for commit in commits:
            sha = commit["commit"]
            pull = by_commit.get(sha)
            check = (
                pull.get("check")
                if pull
                else ("none" if "merged" in hosted else "unknown")
            )
            if check in {"failing", "pending", "unknown"}:
                state = f"check_{check}"
            elif not deployment_known or (
                deployment.get("kind") != "none" and contained is None
            ):
                state = "live_unknown"
            elif deployment.get("kind") == "none" or sha in contained:
                state = "finished"
            else:
                state = "merged_not_live"
            key = f"{project}:{sha}"
            seen_keys.add(key)
            if state == "finished" and key not in finished_at:
                finished_at[key] = commit["at"] if first_observation else iso(now)
            rows.append(
                {
                    "project": project,
                    "commit": sha,
                    "short": sha[:9],
                    "subject": commit.get("subject"),
                    "merged_at": commit.get("at"),
                    "pull": {"number": pull.get("number"), "url": pull.get("url")}
                    if pull
                    else None,
                    "check": check,
                    "deployment": deployment.get("kind"),
                    "state": state,
                    "finished_at": finished_at.get(key)
                    if state == "finished"
                    else None,
                    "citation": f"{project} {sha[:9]}"
                    + (
                        f", pull request {pull.get('number')}, check {check}"
                        if pull
                        else ""
                    ),
                }
            )
        if complete and first_observation:
            seeded.append(project)
        if commits:  # a failed read keeps what was recorded
            for key in [
                key
                for key in finished_at
                if key.startswith(f"{project}:") and key not in seen_keys
            ]:
                del finished_at[key]
    return rows


# ---------------------------------------------------------------- products


def product_rows(
    inputs: Mapping[str, Any], changes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    deployed = inputs.get("deployed") or {}
    rows = []
    for project in inputs.get("projects") or []:
        name = project["id"]
        beads = (inputs.get("beads") or {}).get(name) or {}
        git = (inputs.get("git") or {}).get(name) or {}
        pulls = (inputs.get("pulls") or {}).get(name) or {}
        deployment = dict(
            (deployed.get("projects") or {}).get(name) or {"kind": "none"}
        )
        deployment.pop("contains", None)
        commits = git.get("commits") or []
        own = [change for change in changes if change["project"] == name]
        rows.append(
            {
                "project": name,
                "root": project.get("root"),
                "tasks": {
                    "open": beads.get("open"),
                    "in_progress": beads.get("in_progress_count"),
                    "waiting_on_operator": len(beads.get("human") or [])
                    if "human" in beads
                    else None,
                    "error": beads.get("error"),
                },
                "checks": pulls.get("default_check")
                or {
                    "state": "unknown",
                    "failing": [],
                    "reason": pulls.get("error") or "no hosted check read",
                },
                "last_merged": {
                    "commit": commits[0]["commit"],
                    "subject": commits[0].get("subject"),
                    "at": commits[0].get("at"),
                }
                if commits
                else None,
                "default_branch": git.get("default_branch"),
                "deployment": deployment,
                "merged_not_live": sum(
                    1 for change in own if change["state"] == "merged_not_live"
                ),
                "units": [
                    {
                        "unit": unit.get("unit"),
                        # A masked unit is stopped on purpose; say so.
                        "state": "masked"
                        if unit.get("load_state") == "masked"
                        else unit.get("active_state"),
                    }
                    for unit in inputs.get("units") or []
                    if isinstance(unit, dict)
                    and str(unit.get("unit") or "").startswith(name.replace("_", "-"))
                ],
                "error": git.get("error"),
            }
        )
    return rows


# ---------------------------------------------------------------- forecast


def forecast(
    inputs: Mapping[str, Any],
    running: list[dict[str, Any]],
    queued: list[dict[str, Any]],
) -> dict[str, Any]:
    samples = inputs.get("closed_beads") or []
    history = inputs.get("job_history") or {}
    tasks = []
    for project, beads in sorted((inputs.get("beads") or {}).items()):
        for item in beads.get("in_progress") or []:
            kind, size = bead_kind(item), bead_size(item)
            tasks.append(
                {
                    "project": project,
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "kind": kind,
                    "size": size,
                    "own_range": bead_own_range(item),
                    "started_at": item.get("started_at"),
                    "history": estimate_range(samples, kind, size),
                }
            )
    claimed = [s for s in samples if s["claimed_seconds"] is not None]
    waits = [
        seconds
        for values in (history.get("wait_seconds") or {}).values()
        for seconds in values
    ]
    return {
        "jobs": [
            {
                "label": job["label"],
                "task_id": job["task_id"],
                "phase": job["phase"],
                "elapsed_seconds": job["seconds"] if job["phase"] == "running" else 0,
                "expected": job["expected"],
            }
            for job in [*running, *queued]
        ],
        "tasks": tasks,
        "sizes": [
            {
                "size": size,
                "claim_to_close": summarize(
                    (s["claimed_seconds"] for s in claimed if s["size"] == size),
                    f"closed tasks of size {size}",
                ),
            }
            for size in SIZES
        ],
        # The four clocks, each from the source that can measure it.
        "clocks": {
            "agent_working": {
                **summarize(
                    (s["claimed_seconds"] for s in claimed),
                    "closed tasks, claim to close",
                ),
                "caveat": "claim to close includes time the agent spent waiting",
            },
            "waiting_for_machine": summarize(waits, "jobs, enqueue to start"),
            "waiting_for_operator": summarize(
                (s["total_seconds"] for s in samples if s["human"]),
                "closed tasks labelled human, created to closed",
            ),
            "total_elapsed": summarize(
                (s["total_seconds"] for s in samples), "closed tasks, created to closed"
            ),
        },
        "history": history.get("counts") or {},
    }


# ---------------------------------------------------------------- coordination

# The idle time and terminal quiet a session needs before the state calls it
# a parking candidate; `sinnix sessions park` takes its own.
SESSION_IDLE_SECONDS = 2 * 3600
SESSION_TOUCHED_SECONDS = 30 * 60


def claim_rows(inputs: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    active = [
        row
        for row in inputs.get("claims") or []
        if (parse_time(row.get("expires_at")) or now) > now
    ]
    return {"active": active, "overlaps": claims.overlaps(active)}


def session_rows(inputs: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    facts = inputs.get("agent_sessions")
    if facts is None:
        return {"rows": [], "memory_bytes": None, "candidates": 0, "read": False}
    rows = sessions.judge(
        facts,
        job_sessions=sessions.job_sessions_of(inputs.get("jobs") or {}),
        now=now.timestamp(),
        idle_seconds=SESSION_IDLE_SECONDS,
        touched_seconds=SESSION_TOUCHED_SECONDS,
    )
    return {
        "rows": rows,
        "memory_bytes": sum(row["memory_bytes"] or 0 for row in rows),
        "candidates": sum(1 for row in rows if row["candidate"]),
        "read": True,
    }


# ---------------------------------------------------------------- compute


def compute(
    inputs: Mapping[str, Any], memory: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """The state document. ``memory`` holds ``last_looked_at`` and is updated
    in place with the first time each change was observed finished."""
    last_looked = parse_time(memory.get("last_looked_at"))
    waiting = waiting_rows(inputs, now)
    running, queued = running_rows(inputs, now)
    stalled = stalled_rows(inputs, running, now)
    changes = change_rows(inputs, memory, now)
    claimed = claim_rows(inputs, now)
    agent_sessions = session_rows(inputs, now)
    activations = [row for row in [*running, *queued] if row.get("announce")]

    finished = [change for change in changes if change["state"] == "finished"]
    finished.sort(key=lambda change: change["finished_at"] or "", reverse=True)

    def is_new(change: dict[str, Any]) -> bool:
        moment = parse_time(change["finished_at"])
        return last_looked is None or (moment is not None and moment > last_looked)

    new = [change for change in finished if is_new(change)]
    earlier = [change for change in finished if not is_new(change)]
    not_live = [change for change in changes if change["state"] == "merged_not_live"]
    unverified = [
        change
        for change in changes
        if change["state"]
        in {"check_failing", "check_pending", "check_unknown", "live_unknown"}
    ]
    recent = list((inputs.get("job_history") or {}).get("recent") or [])[
        -RECENT_JOB_ROWS:
    ]
    recent.reverse()
    failed = [
        event
        for event in recent
        if event.get("outcome") not in {"success", "cancelled"}
        and (
            last_looked is None
            or (parse_time(event.get("ended_at")) or now) > last_looked
        )
    ]
    return {
        "schema": SCHEMA,
        "generated_at": iso(now),
        "last_looked_at": memory.get("last_looked_at"),
        "counts": {
            "waiting": len(waiting),
            "running": len(running),
            "queued": len(queued),
            "stalled": len(stalled),
            "finished_new": len(new),
            "merged_not_live": len(not_live),
            "failed_new": len(failed),
            "activations": len(activations),
            "claims": len(claimed["active"]),
            "claims_overlapping": len(claimed["overlaps"]),
            "sessions": len(agent_sessions["rows"]),
            "parking_candidates": agent_sessions["candidates"],
        },
        "waiting": waiting,
        "running": running,
        "queued": queued,
        "stalled": stalled,
        "activations": activations,
        "claims": claimed,
        "sessions": agent_sessions,
        "finished": {
            "new": new,
            "merged_not_live": not_live,
            "unverified": unverified,
            "earlier": earlier[:EARLIER_FINISHED_ROWS],
        },
        "forecast": forecast(inputs, running, queued),
        "products": product_rows(inputs, changes),
        "limits": inputs.get("limits") or {},
        "rest": {
            "recent_jobs": recent,
            "failed_new": failed,
            "pools": (inputs.get("jobs") or {}).get("groups") or {},
        },
        # Reserved for later additions; nothing writes these yet.
        "muted": None,
        "small_next_move": None,
        "sources": inputs.get("sources") or {},
    }
