"""The /work/ page: what is running, as named workloads rather than a process list."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .probes import (
    HEAVY_CLASSES,
    collect_scopes,
    project_of,
)
from .shell import (
    ACTION_SCRIPT,
    age_since,
    as_int,
    badge,
    bytes_human,
    card,
    duration_human,
    empty,
    esc,
    log_card,
    meter,
    page,
    parse_iso,
    row,
    tile,
)

WORKLOAD_CONTROL_NOTE = (
    "Ad-hoc <code>sinnix-scope</code> placements can be stopped from here (the "
    "reducer admits a scope target by name-shape plus live-state, not "
    "pre-registration) but only stopped, not restarted or reconfigured -- a "
    "scope has no service definition to relaunch from. Escalating past a plain "
    "stop, if a placement ignores SIGTERM, still means the terminal that owns it."
)


def slice_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    slices = state.get("resource_slices")
    if not isinstance(slices, list):
        return []
    rows = []
    for entry in slices:
        if not isinstance(entry, dict) or entry.get("active_state") != "active":
            continue
        policy = entry.get("policy") if isinstance(entry.get("policy"), dict) else {}
        current = as_int(policy.get("memory_current"))
        if current is None or current < 8 * 1024 * 1024:
            continue
        rows.append(
            {
                "unit": entry.get("unit"),
                "manager": entry.get("manager"),
                "current": current,
                "high": as_int(policy.get("memory_high")),
                "max": as_int(policy.get("memory_max")),
                "swap": as_int(policy.get("memory_swap_current")),
                "cpu_weight": policy.get("cpu_weight"),
            }
        )
    rows.sort(key=lambda item: item["current"], reverse=True)
    return rows


def work_verdict(
    in_flight: list[Any], heavy: list[Any], failed_recent: int
) -> tuple[str, str, str]:
    """(tone, headline, detail) for the work page's lead banner.

    This slot used to report the heavy-work lease, which was deliberately
    removed from sinnix -- so the page's most prominent line had become a
    permanent "Heavy-work lease not in use" about a subsystem that no longer
    exists, occupying the spot where the actual verdict belongs. The tiles
    below already carry the real numbers; this says what they mean.
    """
    if failed_recent:
        return (
            "bad",
            f"{failed_recent} of the last 10 runs failed",
            "check the project ledger below",
        )
    if in_flight:
        detail = f"{len(heavy)} of them heavy" if heavy else "none of them heavy"
        return (
            "info",
            f"{len(in_flight)} command{'s' if len(in_flight) != 1 else ''} in flight",
            detail,
        )
    return "muted", "Nothing running", "no scopes in flight and no recent failures"


def ledger_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = state.get("workload_rows")
    if not isinstance(rows, list):
        return []
    ledger = [
        entry
        for entry in rows
        if isinstance(entry, dict) and entry.get("kind") == "project-ledger"
    ]
    ledger.sort(key=lambda entry: str(entry.get("started_at") or ""), reverse=True)
    return ledger


def gateway_jobs(state: dict[str, Any]) -> list[dict[str, Any]]:
    gateway = state.get("agent_gateway")
    jobs = gateway.get("jobs") if isinstance(gateway, dict) else None
    return (
        [job for job in jobs if isinstance(job, dict)] if isinstance(jobs, list) else []
    )


def orphan_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    gateway = state.get("agent_gateway")
    rows = gateway.get("orphaned_jobs") if isinstance(gateway, dict) else None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("orphaned")]


# --------------------------------------------------------------------------
# work page
# --------------------------------------------------------------------------


LONG_LIVED_SECONDS = 24 * 3600


def scope_block(
    entry: dict[str, Any],
    jobs_by_id: dict[str, dict[str, Any]],
    slice_limits: dict[str, int],
) -> str:
    job = jobs_by_id.get(entry["job_id"]) if entry.get("job_id") else None
    controls = ""
    if job is not None:
        declared = job.get("declared") if isinstance(job.get("declared"), dict) else {}
        headline = (
            f"<strong>{esc(job.get('backend') or 'agent')} {esc(job.get('model') or '')}</strong>"
            f" in <code>{esc(project_of(job.get('worktree')) or job.get('worktree') or '?')}</code>"
        )
        meta = [badge("gateway job", "info"), esc(duration_human(entry.get("elapsed")))]
        if declared.get("work_item"):
            meta.append(f"work item <code>{esc(declared['work_item'])}</code>")
        if job.get("effort"):
            meta.append(f"effort {esc(job['effort'])}")
        controls = (
            f"<button class=\"act danger\" onclick=\"act('interrupt','job_id',"
            f"'{esc(entry['job_id'])}',this)\">interrupt</button>"
        )
    elif entry.get("job_id"):
        headline = f"<strong>gateway job</strong> <code>{esc(entry['job_id'])}</code>"
        meta = [
            badge("gateway job", "info"),
            esc(duration_human(entry.get("elapsed"))),
            "no manifest in the current snapshot",
        ]
    else:
        klass = entry.get("class")
        project = entry.get("project")
        where = f" in <code>{esc(project)}</code>" if project else ""
        headline = f"<strong>{esc(entry['command'])}</strong>{where}"
        meta = [
            badge(
                f"{klass} class" if klass else "unclassified scope",
                "warn" if klass in HEAVY_CLASSES else "muted",
            ),
            esc(duration_human(entry.get("elapsed"))),
        ]
        if entry.get("slice"):
            meta.append(f"<code>{esc(entry['slice'])}</code>")
        controls = (
            f"<button class=\"act danger\" onclick=\"act('stop','scope',"
            f"'{esc(entry['unit'])}',this)\">stop</button>"
        )

    elapsed = entry.get("elapsed")
    if elapsed is not None and elapsed > LONG_LIVED_SECONDS:
        meta.append(badge("long-lived", "muted"))
    # A scope's own MemoryHigh is the per-job cap where one exists (agent
    # scopes carry 8G/12G); otherwise the ceiling that actually binds it is the
    # slice's, which is the number the operator cares about during a build.
    ceiling = entry.get("memory_high") or entry.get("memory_max")
    ceiling_owner = "scope"
    if not ceiling and entry.get("slice") in slice_limits:
        ceiling = slice_limits[entry["slice"]]
        ceiling_owner = str(entry["slice"])
    memory = entry.get("memory")
    bar = ""
    tone = ""
    if memory is not None:
        if ceiling:
            bar = meter(memory, ceiling)
            meta.append(
                f"{esc(bytes_human(memory))} of {esc(bytes_human(ceiling))} "
                f"{esc(ceiling_owner)} ceiling"
            )
            if memory / ceiling > 0.9:
                tone = "bad"
        else:
            meta.append(esc(bytes_human(memory)))
    return row(headline + bar, meta, controls, tone)


def scope_groups(
    scopes: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Sort live scopes into the four things they actually are."""
    heavy, sessions, jobs, other = [], [], [], []
    for entry in scopes:
        if entry.get("job_id"):
            jobs.append(entry)
        elif entry.get("class") in HEAVY_CLASSES:
            heavy.append(entry)
        elif entry.get("class") == "agent":
            sessions.append(entry)
        else:
            other.append(entry)
    for bucket in (heavy, sessions, jobs, other):
        bucket.sort(key=lambda item: item.get("elapsed") or 0)
    return [
        ("build, nix-build and heavy scopes", heavy),
        ("agent-gateway jobs", jobs),
        ("agent sessions", sessions),
        ("other scopes", other),
    ]


def running_ledger(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [entry for entry in ledger_rows(state) if entry.get("status") == "running"]


def live_work_card(
    scopes: list[dict[str, Any]], state: dict[str, Any], now: dt.datetime
) -> str:
    jobs_by_id = {
        job["job_id"]: job
        for job in gateway_jobs(state)
        if isinstance(job.get("job_id"), str)
    }
    slice_limits = {
        str(entry["unit"]): entry["high"] or entry["max"]
        for entry in slice_rows(state)
        if entry.get("unit") and (entry.get("high") or entry.get("max"))
    }
    body = ""
    in_flight = running_ledger(state)
    if in_flight:
        blocks = ""
        for entry in in_flight:
            started = parse_iso(entry.get("started_at"))
            elapsed = (now - started).total_seconds() if started else None
            blocks += row(
                f"<strong>{esc(entry.get('project') or '?')}</strong> is running "
                f"<code>{esc(entry.get('name') or entry.get('command') or '?')}</code>",
                [
                    badge("in flight", "info"),
                    esc(duration_human(elapsed)),
                    esc(str(entry.get("resource_class") or "")),
                ],
            )
        body += f'<div class="group"><h3>project commands in flight</h3>{blocks}</div>'
    for label, bucket in scope_groups(scopes):
        if not bucket:
            continue
        blocks = "".join(
            scope_block(entry, jobs_by_id, slice_limits) for entry in bucket
        )
        body += f'<div class="group"><h3>{esc(label)}</h3>{blocks}</div>'
    if not body:
        return card(
            "Running now",
            empty(
                "Nothing is placed in a sinnix scope and no project command is in "
                "flight — no agent session, build, or scoped command is running."
            ),
            "project commands, agent sessions, gateway jobs and sinnix-scope placements",
            wide=True,
            anchor="running",
        )
    subtitle = (
        f"{len(in_flight)} project command{'s' if len(in_flight) != 1 else ''} in flight, "
        f"{len(scopes)} live scope{'s' if len(scopes) != 1 else ''}. {WORKLOAD_CONTROL_NOTE}"
    )
    return (
        '<section class="card wide" id="running"><h2>Running now</h2>'
        f'<p class="sub">{subtitle}</p>{body}</section>'
    )


def slices_card(state: dict[str, Any]) -> str:
    rows = slice_rows(state)
    if not rows:
        return card("Slice budgets", empty("no slice accounting in the snapshot"))
    blocks = ""
    for entry in rows[:8]:
        limit = entry["high"] or entry["max"]
        headline = f"<code>{esc(entry['unit'])}</code>"
        if entry.get("manager"):
            headline += f' <span class="sub">{esc(entry["manager"])}</span>'
        meta = [
            f"{esc(bytes_human(entry['current']))} of {esc(bytes_human(limit))} "
            f"{'high' if entry['high'] else 'max'}"
            if limit
            else f"{esc(bytes_human(entry['current']))}, no memory ceiling"
        ]
        if entry.get("cpu_weight") and entry["cpu_weight"] not in {"[not set]", None}:
            meta.append(f"CPUWeight {esc(entry['cpu_weight'])}")
        if entry.get("swap"):
            meta.append(f"swap {esc(bytes_human(entry['swap']))}")
        blocks += row(headline + meter(entry["current"], limit), meta)
    return (
        '<section class="card"><h2>Slice budgets</h2>'
        '<p class="sub">Where sinnix puts work, and what it is allowed to '
        "cost. Sacrificial slices carry real ceilings; the protected ones do "
        "not.</p>"
        f"{blocks}</section>"
    )


def ledger_card(state: dict[str, Any], now: dt.datetime) -> str:
    rows = ledger_rows(state)
    if not rows:
        return card(
            "Recent project runs",
            empty("no project ledger rows in the snapshot"),
            "xtask, cargo and friends record what they ran and what it cost",
        )
    blocks = ""
    for entry in rows[:10]:
        status = str(entry.get("status") or "unknown")
        tone = {"success": "ok", "failed": "bad", "running": "info"}.get(
            status, "muted"
        )
        metrics = entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
        headline = (
            f"<strong>{esc(entry.get('project') or '?')}</strong> "
            f"<code>{esc(entry.get('name') or entry.get('command') or '?')}</code>"
        )
        meta = [badge(status, tone)]
        if entry.get("duration_secs"):
            meta.append(f"ran {esc(duration_human(entry['duration_secs']))}")
        rss = metrics.get("rss_mb")
        if isinstance(rss, (int, float)):
            meta.append(f"peak {rss / 1024:.1f} G")
        meta.append(
            esc(age_since(entry.get("finished_at") or entry.get("started_at"), now))
        )
        blocks += row(headline, meta, tone="bad" if status == "failed" else "")
    return (
        '<section class="card"><h2>Recent project runs</h2>'
        '<p class="sub">The project ledger — what the devshell-routed commands '
        "actually did, from the same records lynchpin reads.</p>"
        f"{blocks}</section>"
    )


def agent_jobs_card(
    state: dict[str, Any], live_job_ids: set[str], now: dt.datetime
) -> str:
    jobs = [job for job in gateway_jobs(state) if job.get("job_id") not in live_job_ids]
    jobs.sort(key=lambda job: str(job.get("updated_at") or ""), reverse=True)
    orphans = {
        row["job_id"]: row
        for row in orphan_rows(state)
        if isinstance(row.get("job_id"), str)
    }
    if not jobs and not orphans:
        return card("Agent jobs", empty("the gateway has no recorded jobs"))
    blocks = ""
    for job in jobs[:10]:
        job_id = str(job.get("job_id") or "")
        lifecycle = str(job.get("lifecycle") or "unknown")
        orphan = orphans.get(job_id)
        tone = {"completed": "ok", "failed": "bad", "cancelled": "muted"}.get(
            lifecycle, "info"
        )
        declared = job.get("declared") if isinstance(job.get("declared"), dict) else {}
        headline = (
            f"<strong>{esc(job.get('backend') or 'agent')}</strong> "
            f"{esc(job.get('model') or '')} · "
            f"<code>{esc(project_of(job.get('worktree')) or '?')}</code>"
        )
        meta = [badge(lifecycle, tone), esc(age_since(job.get("updated_at"), now))]
        if declared.get("work_item"):
            meta.append(f"work item <code>{esc(declared['work_item'])}</code>")
        if isinstance(job.get("exit_status"), int):
            meta.append(f"exit {job['exit_status']}")
        controls = ""
        row_tone = ""
        if orphan is not None:
            policy = (
                orphan.get("policy") if isinstance(orphan.get("policy"), dict) else {}
            )
            proposed = str(policy.get("proposed_action") or "notify")
            meta.append(badge(f"orphaned, {proposed}", "warn"))
            row_tone = "warn"
            controls = (
                f"<button class=\"act danger\" onclick=\"act('interrupt','job_id',"
                f"'{esc(job_id)}',this)\">interrupt</button>"
            )
        blocks += row(headline, meta, controls, row_tone)
    return (
        '<section class="card wide"><h2>Agent jobs, recently</h2>'
        '<p class="sub">Attested gateway jobs whose launcher has exited. An '
        "orphan is one whose scope outlived its launcher; the reducer will only "
        "accept a reap after two identical cold expendable observations.</p>"
        f"{blocks}</section>"
    )


def render_work(
    manifest: dict[str, Any],
    snapshot: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
    generated: str,
) -> str:
    host = str(manifest.get("host", "sinnix"))
    now = dt.datetime.now(dt.timezone.utc)
    scopes = collect_scopes(inventory)
    state = (snapshot or {}).get("state")
    state = state if isinstance(state, dict) else {}

    heavy = [entry for entry in scopes if entry.get("class") in HEAVY_CLASSES]
    agents = [
        entry
        for entry in scopes
        if entry.get("job_id") or entry.get("class") == "agent"
    ]
    in_flight = running_ledger(state)
    recent = ledger_rows(state)[:10]
    failed_recent = sum(1 for entry in recent if entry.get("status") == "failed")
    tone, headline, detail = work_verdict(in_flight, heavy, failed_recent)
    body = (
        f'<div class="verdict {tone if tone != "muted" else ""}">'
        f"<p>{headline}.</p>"
        f'<p class="sub">{detail}</p></div>'
    )
    body += (
        '<div class="tiles">'
        + tile(str(len(in_flight)), "commands in flight", "info" if in_flight else "")
        + tile(str(len(heavy)), "heavy scopes", "warn" if heavy else "")
        + tile(str(len(agents)), "agent sessions")
        + tile(
            str(failed_recent), "of last 10 runs failed", "bad" if failed_recent else ""
        )
        + "</div>"
    )
    live_job_ids = {entry["job_id"] for entry in scopes if entry.get("job_id")}
    body += live_work_card(scopes, state, now)
    body += slices_card(state)
    body += ledger_card(state, now)
    body += agent_jobs_card(state, live_job_ids, now)
    body += log_card()
    if snapshot is None:
        body += card(
            "Reducer snapshot unavailable",
            '<p class="sub">Live scopes above come straight from systemd and are '
            "current; slice budgets, the project ledger, and agent jobs need the "
            "reducer.</p>",
            wide=True,
        )
    return page(
        "work",
        host,
        [f"rendered {generated[11:19]}"],
        "/work/",
        body,
        tail=ACTION_SCRIPT,
    )
