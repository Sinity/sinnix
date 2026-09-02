"""The operator's view of a campaign: what is happening, what is stuck, what is next.

Two renderings over data that already exists (the campaign status payload,
the job store, the event spool). Nothing here decides anything; it says
whether the loop is doing what it should and names the first thing that is
not.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Waits longer than these are worth a look; the loop should have moved on.
STALE_QUEUED_SECONDS = 20 * 60
STALE_RUNNING_SECONDS = {
    "harvest": 30 * 60,
    "verify_quick": 20 * 60,
    "verify_affected": 90 * 60,
    "verify_all": 120 * 60,
}
STALE_LANE_WAIT_SECONDS = 6 * 60 * 60
REACTOR_TICK_STALE_SECONDS = 5 * 60
GHOST_SECONDS = 24 * 60 * 60

ACTIVE_PHASES = frozenset(
    {
        "queued",
        "capacity",
        "submitted",
        "waiting-dependencies",
        "running",
        "launching",
        "cancelling",
    }
)


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        value = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
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


def _seconds_since(stamp: str | None, now: datetime) -> float:
    moment = _parse(stamp)
    return (now - moment).total_seconds() if moment else 0.0


def _local(stamp: str | None) -> str:
    moment = _parse(stamp)
    return moment.astimezone().strftime("%H:%M") if moment else "?"


def load_jobs(jobs_root: Path, project: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        paths = list(jobs_root.glob("*.json"))
    except OSError:
        return rows
    for path in paths:
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(value, Mapping)
            and (value.get("spec") or {}).get("project_id") == project
        ):
            rows.append(dict(value))
    return rows


def _job_label(job: Mapping[str, Any]) -> str:
    spec = job.get("spec") or {}
    if spec.get("kind") == "attested-agent":
        contract = spec.get("contract") or {}
        label = (
            contract.get("coordinator_label") if isinstance(contract, Mapping) else None
        )
        parameters = (
            contract.get("parameters") if isinstance(contract, Mapping) else None
        )
        if label:
            return f"agent:{label}"
        if isinstance(parameters, Mapping) and parameters.get("campaign"):
            return "agent:lane"
        return "agent"
    return str(spec.get("operation") or spec.get("kind") or "job")


def _job_workspace(job: Mapping[str, Any]) -> str:
    checkout = (job.get("spec") or {}).get("checkout") or {}
    return str(checkout.get("path") or "").rsplit("/", 1)[-1]


def _reactor_last_dispatch(spool: Path) -> str | None:
    """Timestamp of the newest reactor dispatch event, read from the tail of the spool."""
    try:
        size = spool.stat().st_size
        with spool.open("rb") as handle:
            handle.seek(max(0, size - 512_000))
            tail = handle.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for line in reversed(tail):
        if '"kind":"dispatch"' in line or '"kind": "dispatch"' in line:
            try:
                return str(json.loads(line).get("emitted_at") or "")
            except json.JSONDecodeError:
                continue
    return None


def checks(
    status: Mapping[str, Any],
    jobs: Iterable[Mapping[str, Any]],
    *,
    now: datetime,
    reactor_active: bool,
    last_dispatch: str | None,
) -> list[str]:
    """Unequivocal 'should be happening' checks; each line names one thing that is not."""
    problems: list[str] = []
    if not reactor_active:
        problems.append(
            "reactor is STOPPED: nothing advances until `systemctl --user start sinnixd-reactor`"
        )
    elif (
        last_dispatch is None
        or _seconds_since(last_dispatch, now) > REACTOR_TICK_STALE_SECONDS
    ):
        problems.append(
            f"reactor has not dispatched for {_age(last_dispatch, now)} (lanes may all be waiting; see below)"
        )
    corpus = status.get("master_corpus") or {}
    if not corpus:
        problems.append("no complete corpus run on record")
    elif not corpus.get("green"):
        problems.append(
            f"master corpus is RED: {corpus.get('red')} red / {corpus.get('passed')} passed at {corpus.get('head')} ({_age(corpus.get('finished_at'), now)} ago)"
        )
    queued = [
        j
        for j in jobs
        if (j.get("state") or {}).get("phase")
        in {"queued", "capacity", "submitted", "waiting-dependencies"}
    ]
    for job in sorted(queued, key=lambda j: str(j.get("created_at") or "")):
        waited = _seconds_since(job.get("created_at"), now)
        if waited > STALE_QUEUED_SECONDS:
            blocked = (job.get("state") or {}).get("blocked_by") or []
            problems.append(
                f"{_job_label(job)} {_job_workspace(job)} queued {_age(job.get('created_at'), now)} (blocked_by {','.join(map(str, blocked)) or '?'})"
            )
            break
    for job in jobs:
        state = job.get("state") or {}
        if state.get("phase") != "running":
            continue
        limit = STALE_RUNNING_SECONDS.get(_job_label(job))
        if limit and _seconds_since(job.get("created_at"), now) > limit:
            problems.append(
                f"{_job_label(job)} {_job_workspace(job)} running {_age(job.get('created_at'), now)}, past its usual {limit // 60}m"
            )
    for row in status.get("lanes_next") or []:
        nxt = row.get("next") or {}
        if nxt.get("kind") == "park":
            problems.append(f"{row.get('workspace')} PARKED: {nxt.get('reason')}")
    return problems


def render_overview(
    status: Mapping[str, Any],
    jobs: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    reactor_active: bool,
    last_dispatch: str | None,
) -> str:
    """One screen: health checks, lanes by next action, active jobs, corpus."""
    moment = now or datetime.now(UTC)
    lines: list[str] = []
    problems = checks(
        status,
        jobs,
        now=moment,
        reactor_active=reactor_active,
        last_dispatch=last_dispatch,
    )
    lines.append(
        f"== {status.get('project_id')} at {moment.astimezone().strftime('%Y-%m-%d %H:%M')} "
        f"| reactor {'active' if reactor_active else 'STOPPED'}, last dispatch {_age(last_dispatch, moment)} ago"
    )
    lines.append("== needs attention" if problems else "== nothing needs attention")
    lines.extend(f"  ! {item}" for item in problems)
    corpus = status.get("master_corpus") or {}
    if corpus:
        lines.append(
            f"== master corpus: {'GREEN' if corpus.get('green') else 'RED'} {corpus.get('red')} red / {corpus.get('passed')} passed, "
            f"head {corpus.get('head')}, {_age(corpus.get('finished_at'), moment)} ago, job {str(corpus.get('job_id'))[:8]}"
        )
    active = [j for j in jobs if (j.get("state") or {}).get("phase") in ACTIVE_PHASES]
    active.sort(key=lambda j: str(j.get("created_at") or ""))
    ghosts = [
        j for j in active if _seconds_since(j.get("created_at"), moment) > GHOST_SECONDS
    ]
    active = [j for j in active if j not in ghosts]
    lines.append(
        f"== jobs: {len(active)} active"
        + (
            f", {len(ghosts)} ghosts older than a day (cancel them: `agentctl job cancel <id>`)"
            if ghosts
            else ""
        )
    )
    for job in ghosts[:3]:
        lines.append(
            f"  ghost {str(job.get('job_id'))[:8]} {_job_label(job):18} {_job_workspace(job):34} {(job.get('state') or {}).get('phase'):10} {_age(job.get('created_at'), moment):>6}"
        )
    for job in active:
        state = job.get("state") or {}
        lines.append(
            f"  {str(job.get('job_id'))[:8]} {_job_label(job):18} {_job_workspace(job):34} {state.get('phase'):10} {_age(job.get('created_at'), moment):>6}"
        )
    rows = list(status.get("lanes_next") or [])
    kinds = Counter(str((row.get("next") or {}).get("kind")) for row in rows)
    lines.append(
        "== lanes: "
        + ", ".join(f"{count} {kind}" for kind, count in kinds.most_common())
    )
    order = [
        "park",
        "retry",
        "verify",
        "harvest",
        "publish",
        "integrate",
        "rebase",
        "review-fix",
        "await-sweep",
        "wait",
        "done",
        "idle",
    ]
    for row in sorted(
        rows,
        key=lambda r: (
            order.index(str((r.get("next") or {}).get("kind")))
            if str((r.get("next") or {}).get("kind")) in order
            else 99,
            str(r.get("workspace")),
        ),
    ):
        nxt = row.get("next") or {}
        if nxt.get("kind") in {"idle", "done"}:
            continue
        pull = row.get("pr") or {}
        pr = f"PR {pull.get('number')} {pull.get('verdict')}" if pull else ""
        receipt = row.get("receipt") or {}
        flags = (
            f"{len(receipt.get('flags') or [])} flags" if receipt.get("flags") else ""
        )
        lines.append(
            f"  {str(row.get('workspace')):34} {str(row.get('bead') or ''):18} {str(nxt.get('kind')):11} {str(nxt.get('reason') or '')[:48]:48} {pr} {flags}".rstrip()
        )
    idle = [
        str(r.get("workspace"))
        for r in rows
        if (r.get("next") or {}).get("kind") in {"idle", "done"}
    ]
    if idle:
        lines.append(f"  ({len(idle)} idle/done: {', '.join(sorted(idle))[:200]})")
    errors = status.get("errors") or []
    if errors:
        lines.append(f"== last errors ({len(errors)})")
        for item in errors[-5:]:
            lines.append(
                f"  {str(item.get('at') or item.get('recorded_at') or '')[:16]} {str(item.get('message') or item)[:120]}"
            )
    return "\n".join(lines)


def _spool_events_for(
    spool: Path, job_ids: set[str], workspace: str
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        with spool.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if workspace not in line and not any(
                    job_id in line for job_id in job_ids
                ):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, Mapping):
                    events.append(dict(event))
    except OSError:
        return events
    return events


def render_lane_log(
    workspace: str,
    status: Mapping[str, Any],
    jobs: list[dict[str, Any]],
    spool: Path,
    *,
    now: datetime | None = None,
) -> str:
    """One lane's timeline: every job bound to it, the events about it, and the current verdict."""
    moment = now or datetime.now(UTC)
    mine = [j for j in jobs if _job_workspace(j) == workspace]
    ids = {str(j.get("job_id")) for j in mine}
    lines = [f"== {workspace}"]
    row = next(
        (r for r in status.get("lanes_next") or [] if r.get("workspace") == workspace),
        None,
    )
    if row:
        nxt = row.get("next") or {}
        lines.append(
            f"bead {row.get('bead')} head {row.get('head')} pushed {row.get('pushed')} lane {row.get('lane')} holder {row.get('holder')}"
        )
        lines.append(f"next: {nxt.get('kind')} — {nxt.get('reason')}")
        if row.get("pr"):
            lines.append(f"pr: {json.dumps(row['pr'])}")
        if row.get("receipt"):
            lines.append(f"receipt: {json.dumps(row['receipt'])[:300]}")
    entries: list[tuple[str, str]] = []
    for job in mine:
        state = job.get("state") or {}
        created = str(job.get("created_at") or "")
        end = str(state.get("completed_at") or state.get("observed_at") or "")
        phase = str(state.get("phase") or "")
        entries.append(
            (
                created,
                f"{_local(created)} {_job_label(job):18} {str(job.get('job_id'))[:8]} created",
            )
        )
        if state.get("terminal"):
            entries.append(
                (
                    end,
                    f"{_local(end)} {_job_label(job):18} {str(job.get('job_id'))[:8]} {phase} after {_age(created, _parse(end) or moment)}",
                )
            )
        else:
            entries.append(
                (
                    created,
                    f"{'':5} {'':18} {'':8} … {phase} for {_age(created, moment)}",
                )
            )
    for event in _spool_events_for(spool, ids, workspace):
        kind = str(event.get("kind") or "")
        if kind in {"declared-operation", "attested-agent"}:
            continue
        stamp = str(event.get("emitted_at") or "")
        detail = " ".join(
            f"{k}={str(v).replace(chr(10), ' ')}"
            for k, v in sorted(event.items())
            if k not in {"kind", "emitted_at", "schema_version", "project", "workspace"}
            and not isinstance(v, (dict, list))
        )
        entries.append((stamp, f"{_local(stamp)} {kind:18} {detail[:110]}"))
    entries.sort(key=lambda item: item[0])
    lines.append("== timeline (local time)")
    lines.extend(f"  {text}" for _, text in entries)
    return "\n".join(lines)


__all__ = ["checks", "load_jobs", "render_lane_log", "render_overview"]
