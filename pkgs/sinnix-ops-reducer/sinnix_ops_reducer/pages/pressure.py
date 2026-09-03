"""The /pressure/ page: which pressure regime the machine is in, and what — if
anything — is worth doing about it.

The dashboard already answers "is anything broken". This page answers the
question that had no surface at all: the machine is slow *right now*, why, and
is there a decision to make. It is built from the 2026-08-18 incident
clustering rather than from what is easy to display, which means it deliberately
refuses three things every conventional monitor shows:

  * no "memory used" headline -- during the six-hour freezes that actually hurt,
    available memory read 12.8 GiB and looked fine;
  * no naive top-consumers list -- ranked by RSS it points at Chrome, which is
    never a cause, and it hides a `bd list` holding 19 GiB of swap;
  * no button where no action exists -- the spike regime has a ~2 minute lead
    time and no verb fast enough, and the page says so instead of pretending.

The action surface is the existing bounded API: `park` with a deadline on the
scheduled backup units, `stop` on an admitted individual process, and
`interrupt` on a queued job. The queue card is pueue's groups: a paused group
is the backpressure timer holding new work back.
Where the taxonomy named an action the API cannot express -- a process-level
stop, a MemoryHigh change on a slice -- the page names the gap. That is the
/shaders/ doctrine: report, and say why the button is absent.
"""

from __future__ import annotations

import time
from typing import Any

from .. import pressure as pressure_model
from ..actions import process_admitted_slices
from .queue import queue_card
from .shell import (
    ACTION_SCRIPT,
    badge,
    bytes_human,
    card,
    duration_human,
    empty,
    esc,
    log_card,
    meter,
    page,
    row,
    tile,
)

# The ranked window, and how much of it becomes rows. The window is wider than
# the table because session processes are summarised rather than listed: on a
# calm live host eight of the top ten were Chrome renderers, and a table that
# spends its rows on them has no room left for the one that matters.
HOG_SCAN = 48
HOG_ROWS = 12

CHEAPNESS_TONE = {
    pressure_model.CHEAPNESS_RERUNNABLE: "ok",
    pressure_model.CHEAPNESS_EXPENSIVE: "bad",
    pressure_model.CHEAPNESS_SESSION: "info",
    pressure_model.CHEAPNESS_UNKNOWN: "muted",
}

CHEAPNESS_NOTE = {
    pressure_model.CHEAPNESS_RERUNNABLE: "a re-run, nothing else",
    pressure_model.CHEAPNESS_EXPENSIVE: "the whole job",
    pressure_model.CHEAPNESS_SESSION: "your session; never a cause",
    # Deliberately not a guess. Whether an agent session or an unrecognised
    # binary is expendable right now is exactly the judgment the machine does
    # not have and the operator does.
    pressure_model.CHEAPNESS_UNKNOWN: "not inferable — your call",
}

MISSING_VERBS_NOTE = (
    "<strong>Per-process stop</strong> is live on the re-runnable rows below "
    "(sinnix-mble): stopping a runaway <code>rg</code> or <code>bd list</code> "
    "is costless and correct, and it now reaches the one process rather than "
    "the parent workload. It is admitted by cgroup membership, not by name — only "
    "processes currently inside <code>agent.slice</code>, "
    "<code>build.slice</code>, or a slice the runtime inventory marks "
    "sacrificial can be targeted — so the button is offered only where the "
    "action would actually be accepted. Two gaps remain, and the hub will not "
    "grow a private path around either of them. "
    "<strong>A slice policy change</strong> (<code>MemoryHigh</code> on "
    "<code>agent.slice</code>) is refused because <code>set_policy</code> "
    "resolves its target through the runtime inventory, and slices are not "
    "registered surfaces there. Nothing drains swap or reclaims a slice's "
    "swapped pages at all; that is a genuine gap rather than a verb waiting "
    "to be surfaced."
)


def scheduled_runs(now_us: int) -> list[pressure_model.ScheduledRun]:
    """The live timer table, joined with how long each unit's last run took.

    `systemctl list-timers` reports realtime microseconds since the epoch, so
    the "in nine minutes" figures are relative to a wall-clock now, not to the
    monotonic clock the duration properties use.
    """
    runs = pressure_model.select_scheduled(pressure_model.list_timers(), now_us)
    facts = pressure_model.unit_run_facts([run.unit for run in runs if run.unit])
    return [
        pressure_model.ScheduledRun(
            timer=run.timer,
            unit=run.unit,
            next_seconds=run.next_seconds,
            last_seconds=run.last_seconds,
            last_duration_seconds=facts.get(run.unit, {}).get("last_duration_seconds"),
            active=bool(facts.get(run.unit, {}).get("active")),
        )
        for run in runs
    ]


def parkable_units(inventory: dict[str, Any] | None) -> set[str]:
    """Units `park` will actually accept.

    Mirrors the action API's own admission (`sinnix-pressure-park` derives its
    parkable set from `backup-maintenance` system services in the runtime
    inventory, and the action resolver refuses any unit the inventory does not
    carry) so the page never offers a button that answers 403.
    """
    surfaces = inventory.get("surfaces") if isinstance(inventory, dict) else None
    if not isinstance(surfaces, dict):
        return set()
    return {
        str(surface["unit"])
        for surface in surfaces.values()
        if isinstance(surface, dict)
        and surface.get("unit")
        and surface.get("resourceClass") == "backup-maintenance"
        and str(surface.get("manager") or "system") == "system"
        and str(surface.get("kind") or "service") == "service"
    }


def headroom_card(reading: pressure_model.Sample) -> str:
    """The primary widget. Swap first, because swap goes first."""
    percent = reading.swap_percent
    if percent is None:
        return card(
            "Swap headroom",
            empty("no swap configured, or /proc/meminfo unreadable"),
            "the ten-minute warning this machine gets before a freeze",
            wide=True,
        )
    tone = (
        "bad"
        if percent >= pressure_model.SWAP_PRE_FREEZE_PERCENT
        else "warn"
        if percent >= 50
        else "ok"
    )
    body = (
        '<div class="tiles">'
        + tile(f"{percent:.0f}%", "of swap consumed", tone)
        + tile(
            f"{max(0, (reading.swap_total_mb or 0) - (reading.swap_used_mb or 0)):,} MiB",
            "headroom left",
            tone,
        )
        + "</div>"
        + meter(reading.swap_used_mb, reading.swap_total_mb, tone)
        + f'<p class="sub">{reading.swap_used_mb:,} of {reading.swap_total_mb:,} MiB '
        f"(zram at priority 100, then the swapfile). At "
        f"{pressure_model.SWAP_PRE_FREEZE_PERCENT:.0f}% this machine is about ten "
        "minutes from a freeze; the median measured onset was preceded by 90% "
        "consumed while available memory still read 12.8 GiB.</p>"
    )
    return card(
        "Swap headroom",
        body,
        "the only number that moves before a freeze rather than during one",
        wide=True,
    )


def stall_card(reading: pressure_model.Sample) -> str:
    """Second: is anything actually stalled, which is a different question."""
    full = reading.memory_psi_full
    if full is None:
        return card("Memory stall", empty("/proc/pressure/memory unreadable"))
    tone = (
        "bad"
        if full >= pressure_model.MEMORY_FROZEN_PSI
        else "warn"
        if full >= pressure_model.MEMORY_STALL_PSI
        else "ok"
    )
    some = reading.memory_psi_some
    body = (
        f'<div class="tiles">{tile(f"{full:.1f}", "memory psi full avg10", tone)}'
        + (tile(f"{some:.1f}", "psi some avg10") if some is not None else "")
        + "</div>"
        f'<p class="sub">Full PSI is the share of the last ten seconds in which '
        "<em>every</em> task was stalled — the honest answer to whether the "
        f"machine is working. {pressure_model.MEMORY_STALL_PSI:.0f}% is degraded, "
        f"{pressure_model.MEMORY_FROZEN_PSI:.0f}% is the frozen state that ran "
        "78-82% for six consecutive hours on 2026-08-14. 84% of this machine's "
        "emergency kills happened below 10.</p>"
    )
    return card("Memory stall", body, "is anything actually waiting")


def io_card(reading: pressure_model.Sample) -> str:
    full = reading.io_psi_full
    if full is None:
        return card("Disk stall", empty("/proc/pressure/io unreadable"))
    tone = (
        "bad"
        if full >= pressure_model.IO_SATURATED_PSI
        else "warn"
        if full >= 10
        else "ok"
    )
    return card(
        "Disk stall",
        f'<div class="tiles">{tile(f"{full:.1f}", "io psi full avg10", tone)}</div>'
        '<p class="sub">High here with memory fine is the backup/scrub shape: '
        "301 hours of it since May, in episodes of 1.5 to 6 hours, always with "
        "10-18 GiB of memory available. It is scheduled work, not an "
        "emergency.</p>",
        "the other way this machine goes unresponsive",
    )


def available_card(reading: pressure_model.Sample) -> str:
    """Last, and deliberately quiet: the number that reads fine during the
    freeze and triggers the killer during a burst it should have survived."""
    available = reading.mem_avail_mb
    if available is None:
        return card("Available memory", empty("/proc/meminfo unreadable"))
    total = reading.mem_total_mb
    figure = f"{available:,} MiB" + (f" of {total:,}" if total else "")
    return card(
        "Available memory",
        f'<p class="sub">{esc(figure)} — shown last on purpose. During the '
        "freezes this page exists to catch it read 12.8 GiB and said nothing "
        "was wrong; during a healthy swap-backed burst it dips under 1 GiB and "
        "is what earlyoom kills on, at 3% stall. Read it after the two numbers "
        "above, never instead of them.</p>",
        "de-emphasised, and that is the finding",
    )


def hog_row(
    process: pressure_model.Process,
    admitted_slices: frozenset[str] | set[str] = frozenset(),
) -> str:
    meta = [
        badge(process.cheapness, CHEAPNESS_TONE.get(process.cheapness, "muted")),
        f"{esc(bytes_human(process.rss_kb * 1024))} resident",
        f"{esc(bytes_human(process.swap_kb * 1024))} swapped",
        f"costs {esc(CHEAPNESS_NOTE.get(process.cheapness, 'unknown'))}",
        f"pid {process.pid}",
    ]
    if process.unit:
        meta.insert(1, f"<code>{esc(process.unit)}</code>")
    if process.slice_unit:
        meta.append(esc(process.slice_unit))
    controls = ""
    rerunnable = process.cheapness == pressure_model.CHEAPNESS_RERUNNABLE
    if rerunnable and process.slice_unit in admitted_slices:
        # The pid/start_ticks pin travels in the button itself -- act() posts
        # it straight into target.process, so the receipt's identity check
        # sees exactly what this row observed, not a name the operator typed.
        controls += (
            "<button class=\"act danger\" onclick=\"act('stop','process',"
            f'{{pid: {process.pid}, start_ticks: {process.start_ticks}}},this)">'
            "stop this process</button>"
        )
    elif rerunnable:
        # Re-runnable does not mean admitted: the boundary is cgroup
        # membership, and a re-runnable command outside agent.slice,
        # build.slice, or a sacrificial slice answers 403. Say so rather than
        # silently withholding the button.
        meta.append(badge("no process-stop button (cgroup not admitted)", "muted"))
    tone = ""
    if process.swap_kb > process.rss_kb and process.swap_kb > 1024 * 1024:
        tone = "warn"
    return row(
        f"<strong>{esc(process.command or process.comm)}</strong>", meta, controls, tone
    )


def session_summary(processes: list[pressure_model.Process]) -> str:
    """Every session process as one row, at the bottom, with its total.

    Chrome self-sets `oom_score_adj 300` on renderers, so it wins every naive
    ranking and loses every argument about cause: 26 of them were killed in six
    minutes on 2026-08-16 to free 1.7 GiB, after the job that had actually
    filled memory was already dead. They are counted here — hiding them would
    make the totals lie — and they are not given rows they would otherwise take
    from the processes an operator can act on.
    """
    if not processes:
        return ""
    resident = sum(process.rss_kb for process in processes)
    swapped = sum(process.swap_kb for process in processes)
    return row(
        f"<strong>{len(processes)} session processes</strong> "
        "(browser, terminals, the shell)",
        [
            badge(pressure_model.CHEAPNESS_SESSION, "info"),
            f"{esc(bytes_human(resident * 1024))} resident",
            f"{esc(bytes_human(swapped * 1024))} swapped",
            "collapsed on purpose: a symptom, never a cause",
        ],
    )


def hogs_card(
    processes: list[pressure_model.Process],
    admitted_slices: frozenset[str] | set[str] = frozenset(),
) -> str:
    if not processes:
        return card("What is holding memory", empty("no process table available"))
    actionable = [
        process
        for process in processes
        if process.cheapness != pressure_model.CHEAPNESS_SESSION
    ]
    session = [
        process
        for process in processes
        if process.cheapness == pressure_model.CHEAPNESS_SESSION
    ]
    blocks = "".join(
        hog_row(process, admitted_slices) for process in actionable[:HOG_ROWS]
    )
    blocks += session_summary(session)
    return (
        '<section class="card wide"><h2>What is holding memory</h2>'
        '<p class="sub">Ranked on resident <em>plus</em> swapped pages, because '
        "an RSS-ordered list is wrong here: a <code>bd list</code> measured at "
        "8.2 GiB resident and 19.4 GiB swapped sits mid-table in every tool "
        "that ignores the second column. The cost column is the one to read "
        "before acting — a re-runnable tool invocation is free to stop and the "
        "agent will re-run it better scoped, an expensive job is not, and "
        "session processes are summed at the bottom rather than given rows they "
        f"would take from something actionable. {MISSING_VERBS_NOTE}</p>"
        f"{blocks}</section>"
    )


def scheduled_card(runs: list[pressure_model.ScheduledRun], parkable: set[str]) -> str:
    if not runs:
        return card(
            "Scheduled pressure",
            empty("no backup, scrub or dump timers are scheduled"),
            "the IO pressure that is knowable in advance",
        )
    blocks = ""
    for run in runs:
        meta = []
        if run.next_seconds is not None:
            meta.append(
                f"next in {esc(duration_human(run.next_seconds))}"
                if run.next_seconds > 0
                else "due now"
            )
        else:
            meta.append("not scheduled")
        if run.last_seconds is not None:
            meta.append(f"last ran {esc(duration_human(run.last_seconds))} ago")
        if run.last_duration_seconds is not None:
            meta.append(f"took {esc(duration_human(run.last_duration_seconds))}")
        controls = ""
        if run.active:
            meta.insert(0, badge("running now", "info"))
        if run.unit in parkable and run.active:
            controls = (
                f'<button class="act" onclick="parkUnit('
                f"'{esc(run.unit)}',this)\">park it</button>"
            )
        elif run.unit in parkable:
            # park writes cgroup.freeze, and an inactive unit has no cgroup to
            # write: the action would return a receipt saying "accepted" having
            # frozen nothing, which is worse than no button.
            meta.append('<span class="sub">idle — park freezes a running cgroup</span>')
        else:
            meta.append(
                badge("no park verb", "muted")
                + '<span class="sub"> not a runtime-inventory surface</span>'
            )
        blocks += row(f"<code>{esc(run.unit or run.timer)}</code>", meta, controls)
    return (
        '<section class="card wide"><h2>Scheduled pressure</h2>'
        '<p class="sub">Borg, btrbk, the scrubs and the SQLite dumps: 20 hours '
        "of io-frozen time since July came from these, and every one of them is "
        "declared by a timer, so this predicts rather than alarms. "
        "<code>park</code> freezes the unit's cgroup and schedules its own thaw "
        "— the deadline is part of the action, so a parked backup cannot be "
        "forgotten. The scrub timers are generated by nixpkgs rather than "
        "declared as sinnix surfaces, so the action API will not accept them; "
        "reschedule those instead of parking them.</p>"
        f"{blocks}</section>"
    )


def regime_banner(regime: pressure_model.Regime) -> str:
    cluster = (
        f" <span class='chip'>{esc(regime.cluster)}</span>" if regime.cluster else ""
    )
    return (
        f'<div class="verdict {regime.tone if regime.tone != "muted" else ""}">'
        f"<p><strong>{esc(regime.name)}</strong>{cluster} — {esc(regime.headline)}.</p>"
        f'<p class="sub">{esc(regime.detail)}</p></div>'
    )


def render_pressure(
    manifest: dict[str, Any],
    snapshot: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
    generated: str,
    reading: pressure_model.Sample | None = None,
    processes: list[pressure_model.Process] | None = None,
    runs: list[pressure_model.ScheduledRun] | None = None,
    now_us: int | None = None,
) -> str:
    host = str(manifest.get("host", "sinnix"))
    reading = pressure_model.sample() if reading is None else reading
    regime = pressure_model.classify(reading)
    processes = (
        pressure_model.scan_processes(HOG_SCAN) if processes is None else processes
    )
    if runs is None:
        runs = scheduled_runs(int(time.time() * 1e6) if now_us is None else now_us)

    state = (snapshot or {}).get("state")
    state = state if isinstance(state, dict) else {}
    body = regime_banner(regime)
    body += headroom_card(reading)
    body += stall_card(reading)
    body += io_card(reading)
    body += queue_card(state)
    body += hogs_card(processes, process_admitted_slices(inventory))
    body += scheduled_card(runs, parkable_units(inventory))
    body += available_card(reading)
    body += log_card()

    chips = [regime.name, f"rendered {generated[11:19]}"]
    return page("pressure", host, chips, "/pressure/", body, tail=ACTION_SCRIPT)
