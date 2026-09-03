"""The /work/ page: what is running, as named workloads rather than a process list."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from .queue import active_jobs, jobs_card, lanes_card, queue_card
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

LanesSource = Callable[[], tuple[list[dict[str, Any]], list[str]]]


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


def work_verdict(in_flight: list[Any], failed_recent: int) -> tuple[str, str, str]:
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
        return (
            "info",
            f"{len(in_flight)} command{'s' if len(in_flight) != 1 else ''} in flight",
            "submitted as named project operations",
        )
    return (
        "muted",
        "Nothing running",
        "no project operation in flight and no recent failures",
    )


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


def running_ledger(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [entry for entry in ledger_rows(state) if entry.get("status") == "running"]


def live_work_card(state: dict[str, Any], now: dt.datetime) -> str:
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
    if not body:
        return card(
            "Running now",
            empty("No named project operation is in flight."),
            "declared project operations",
            wide=True,
            anchor="running",
        )
    subtitle = f"{len(in_flight)} named project operation{'s' if len(in_flight) != 1 else ''} in flight."
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
        '<p class="sub">Where declared services and queued jobs run, and what they are allowed to '
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
        '<p class="sub">The project ledger, from the same records lynchpin reads.</p>'
        f"{blocks}</section>"
    )


def render_work(
    manifest: dict[str, Any],
    snapshot: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
    generated: str,
    lanes_source: LanesSource | None = None,
) -> str:
    host = str(manifest.get("host", "sinnix"))
    now = dt.datetime.now(dt.timezone.utc)
    state = (snapshot or {}).get("state")
    state = state if isinstance(state, dict) else {}

    in_flight = running_ledger(state)
    recent = ledger_rows(state)[:10]
    failed_recent = sum(1 for entry in recent if entry.get("status") == "failed")
    tone, headline, detail = work_verdict(in_flight, failed_recent)
    body = (
        f'<div class="verdict {tone if tone != "muted" else ""}">'
        f"<p>{headline}.</p>"
        f'<p class="sub">{detail}</p></div>'
    )
    body += (
        '<div class="tiles">'
        + tile(str(len(in_flight)), "commands in flight", "info" if in_flight else "")
        + tile(str(len(active_jobs(state))), "jobs queued or running")
        + tile(
            str(failed_recent), "of last 10 runs failed", "bad" if failed_recent else ""
        )
        + "</div>"
    )
    body += live_work_card(state, now)
    body += queue_card(state)
    body += slices_card(state)
    body += jobs_card(state, now)
    views, errors = lanes_source() if lanes_source is not None else ([], [])
    body += lanes_card(views, errors)
    body += ledger_card(state, now)
    body += log_card()
    if snapshot is None:
        body += card(
            "Reducer snapshot unavailable",
            '<p class="sub">Slice budgets, the queue, the jobs and the project ledger need the reducer.</p>',
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
