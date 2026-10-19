"""Cards over the job plane: pueue's groups, agentctl's jobs, a project's lanes."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from .shell import (
    age_since,
    badge,
    card,
    duration_human,
    empty,
    esc,
    js_arg,
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
    return (
        [job for job in jobs if isinstance(job, dict)] if isinstance(jobs, list) else []
    )


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
            f"{esc(detail.get('running', 0))} running of {esc(detail.get('parallel', 0))}",
            f"{esc(detail.get('queued', 0))} queued",
        ]
        if detail.get("paused"):
            meta.append(f"{esc(detail['paused'])} paused")
        blocks += row(f"<code>{esc(name)}</code>", meta, tone="warn" if paused else "")
    return (
        '<section class="card"><h2>Queue</h2>'
        '<p class="sub">pueue\'s groups, one per pool; a paused group '
        "holds new work. The pause may be operator-requested or automatic.</p>"
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
            f'<button class="act danger" data-expected-target="{esc(json.dumps(job.get("expected_target")))}" onclick="act(\'interrupt\',\'job_id\','
            f'{js_arg(str(job.get("job_id")))},this)">interrupt</button>'
        )
    headline = (
        f"<strong>{esc(str(job.get('label') or job.get('job_id') or '?'))}</strong>"
        f' <span class="sub">#{esc(str(job.get("job_id") or ""))}</span>'
    )
    return row(headline, meta, controls, "bad" if phase == "failed" else "")


def jobs_card(state: dict[str, Any], now: dt.datetime) -> str:
    jobs = sorted(
        jobs_of(state),
        key=lambda job: (
            job.get("terminal") is not True,
            str(job.get("enqueued_at") or ""),
        ),
        reverse=True,
    )
    blocks = (
        "".join(job_row(job, now) for job in jobs[:12])
        if jobs
        else empty("no jobs in this snapshot")
    )
    omitted = job_plane(state).get("omitted")
    omitted = omitted if isinstance(omitted, dict) else {}
    return (
        '<section class="card wide"><h2>Jobs</h2>'
        '<p class="sub">Active jobs first, then recent completed jobs, labelled '
        "<code>project:operation</code>. An interrupt is "
        "<code>agentctl job cancel</code>. "
        f"Showing {min(len(jobs), 12)} of {len(jobs)} snapshot jobs. "
        f"Owner omitted: {esc(omitted.get('active', 'unknown'))} active, "
        f"{esc(omitted.get('terminal', 'unknown'))} completed. "
        "Project run and worker details: <code>agentctl view &lt;project&gt;</code>."
        f"</p>{blocks}</section>"
    )
