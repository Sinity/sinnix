"""Cards over the job plane: pueue's groups, agentctl's jobs, a project's lanes."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .shell import (
    age_since,
    badge,
    card,
    duration_human,
    empty,
    esc,
    parse_iso,
    row,
)

PHASE_TONE = {
    "running": "info",
    "queued": "muted",
    "paused": "warn",
    "succeeded": "ok",
    "failed": "bad",
    "cancelled": "muted",
}


def job_plane(state: dict[str, Any]) -> dict[str, Any]:
    value = state.get("agentctl")
    return value if isinstance(value, dict) else {}


def jobs_of(state: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = job_plane(state).get("jobs")
    return [job for job in jobs if isinstance(job, dict)] if isinstance(jobs, list) else []


def groups_of(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups = job_plane(state).get("groups")
    if not isinstance(groups, dict):
        return {}
    return {
        str(name): detail for name, detail in groups.items() if isinstance(detail, dict)
    }


def active_jobs(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [job for job in jobs_of(state) if job.get("terminal") is not True]


def queue_card(state: dict[str, Any]) -> str:
    groups = groups_of(state)
    if not groups:
        return card("Queue", empty("pueue's groups are not in the snapshot"))
    blocks = ""
    for name, detail in sorted(groups.items()):
        status = str(detail.get("status") or "")
        paused = status.lower() == "paused"
        meta = [
            badge(status.lower() or "unknown", "warn" if paused else "ok"),
            f"{detail.get('running', 0)} running of {detail.get('parallel', 0)}",
            f"{detail.get('queued', 0)} queued",
        ]
        if detail.get("paused"):
            meta.append(f"{detail['paused']} paused")
        blocks += row(f"<code>{esc(name)}</code>", meta, tone="warn" if paused else "")
    return (
        '<section class="card"><h2>Queue</h2>'
        '<p class="sub">pueue\'s groups, one per pool; a paused group is the '
        "backpressure timer holding new work while the host stalls.</p>"
        f"{blocks}</section>"
    )


def job_row(job: dict[str, Any], now: dt.datetime) -> str:
    phase = str(job.get("phase") or "unknown")
    tone = PHASE_TONE.get(phase, "muted")
    since = job.get("started_at") or job.get("enqueued_at")
    started = parse_iso(job.get("started_at"))
    ended = parse_iso(job.get("ended_at"))
    meta = [badge(phase, tone), esc(str(job.get("group") or ""))]
    if started and ended:
        meta.append(f"ran {esc(duration_human((ended - started).total_seconds()))}")
    elif started:
        meta.append(f"running {esc(duration_human((now - started).total_seconds()))}")
    else:
        meta.append(esc(age_since(since, now)))
    if job.get("exit_code") not in (None, 0):
        meta.append(f"exit {esc(str(job['exit_code']))}")
    controls = ""
    if job.get("terminal") is not True:
        controls = (
            f"<button class=\"act danger\" onclick=\"act('interrupt','job_id',"
            f"'{esc(str(job.get('job_id')))}',this)\">interrupt</button>"
        )
    headline = (
        f"<strong>{esc(str(job.get('label') or job.get('job_id') or '?'))}</strong>"
        f' <span class="sub">#{esc(str(job.get("job_id") or ""))}</span>'
    )
    return row(headline, meta, controls, "bad" if phase == "failed" else "")


def jobs_card(state: dict[str, Any], now: dt.datetime) -> str:
    jobs = sorted(
        jobs_of(state),
        key=lambda job: str(job.get("enqueued_at") or ""),
        reverse=True,
    )
    if not jobs:
        return card("Jobs", empty("no pueue tasks"), "declared operations and lane agents")
    blocks = "".join(job_row(job, now) for job in jobs[:12])
    truncated = job_plane(state).get("truncated") is True
    return (
        '<section class="card wide"><h2>Jobs</h2>'
        '<p class="sub">Every pueue task, newest first: declared operations and '
        "lane agents, labelled <code>project:operation</code>. An interrupt is "
        "<code>agentctl job cancel</code>."
        + (" The snapshot holds the newest hundred." if truncated else "")
        + f"</p>{blocks}</section>"
    )


def lane_row(lane: dict[str, Any]) -> str:
    stage = str(lane.get("stage") or "")
    pr = lane.get("pr") if isinstance(lane.get("pr"), dict) else {}
    meta = [badge(stage or "unknown", "info" if stage else "muted")]
    if lane.get("bead"):
        meta.append(f"<code>{esc(str(lane['bead']))}</code>")
    if lane.get("elapsed"):
        meta.append(esc(str(lane["elapsed"])))
    if pr.get("number"):
        meta.append(
            f"PR #{esc(str(pr['number']))} {esc(str(pr.get('state') or ''))}".strip()
        )
    if lane.get("next"):
        meta.append(esc(str(lane["next"])))
    tone = "warn" if lane.get("dirty") else ""
    return row(f"<strong>{esc(str(lane.get('lane') or lane.get('branch') or '?'))}</strong>", meta, "", tone)


def lanes_card(views: list[dict[str, Any]], errors: list[str]) -> str:
    blocks = ""
    for view in views:
        lanes = [lane for lane in view.get("lanes", []) if isinstance(lane, dict)]
        if not lanes and not view.get("errors"):
            continue
        blocks += f'<div class="group"><h3>{esc(str(view.get("project") or "?"))}</h3>'
        blocks += "".join(lane_row(lane) for lane in lanes)
        for error in view.get("errors") or []:
            blocks += row(esc(str(error)), [badge("source error", "bad")], "", "bad")
        blocks += "</div>"
    for error in errors:
        blocks += row(esc(error), [badge("unavailable", "bad")], "", "bad")
    if not blocks:
        return card("Lanes", empty("no worktree lanes"), "agentctl view, per project")
    return (
        '<section class="card wide"><h2>Lanes</h2>'
        '<p class="sub"><code>agentctl view</code> per project: each worktree with '
        "its bead, stage, agent and pull request, read when this page is "
        "requested.</p>"
        f"{blocks}</section>"
    )
