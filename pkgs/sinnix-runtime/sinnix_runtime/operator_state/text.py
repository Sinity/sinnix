"""The state document as text: phrases shared by the terminal, panel and page."""

from __future__ import annotations

from typing import Any, Mapping

from . import claims, sessions
from .engine import range_text, span

PANEL_ROWS = 6
TEXT_FINISHED_ROWS = 20
IDLE_UNITS_NAMED = 4
STATE_WORDS = {
    "finished": "finished",
    "merged_not_live": "merged, not yet live",
    "check_failing": "merged, check failing",
    "check_pending": "merged, check pending",
    "check_unknown": "merged, check not read",
    "live_unknown": "merged, running revision not read",
}


def gib(value: Any) -> str:
    return f"{value / 2**30:.1f}G" if isinstance(value, (int, float)) else "?"


def caller_text(caller: Any) -> str:
    if not isinstance(caller, Mapping) or not caller:
        return "caller not recorded"
    parts = []
    if caller.get("bead"):
        parts.append(f"task {caller['bead']}")
    if caller.get("session"):
        parts.append(
            f"{caller.get('harness', 'agent')} session {str(caller['session'])[:8]}"
        )
    if caller.get("principal") and not parts:
        parts.append(str(caller["principal"]))
    return ", ".join(parts) or "caller not recorded"


def waiting_line(row: Mapping[str, Any]) -> str:
    where = f"{row['project']} " if row.get("project") else ""
    return f"{where}{row.get('id')}: {row.get('title')} (waiting {span(row.get('age_seconds'))})"


def job_line(row: Mapping[str, Any]) -> str:
    text = f"{row['label']} #{row['task_id']} in pool {row['pool']}, {row['phase']} {span(row['seconds'])}"
    if row.get("waiting_because"):
        text += f": {row['waiting_because']}"
    return f"{text}; for {caller_text(row.get('caller'))}"


def activation_line(row: Mapping[str, Any]) -> str:
    revision = row.get("revision") or {}
    commit = (
        f"commit {str(revision['commit'])[:9]}"
        + (" with uncommitted changes" if revision.get("dirty") else "")
        if revision.get("commit")
        else "commit not recorded"
    )
    return (
        f"{row['label']} #{row['task_id']} {row['phase']} {span(row['seconds'])}, "
        f"{commit}, in {row.get('working_directory')}; for {caller_text(row.get('caller'))}"
    )


def claim_lines(claimed: Mapping[str, Any]) -> list[str]:
    return [
        *(f"overlap: {claims.overlap_line(pair)}" for pair in claimed["overlaps"]),
        *(claims.claim_line(row) for row in claimed["active"]),
    ]


def session_lines(agent_sessions: Mapping[str, Any]) -> list[str]:
    if not agent_sessions.get("read"):
        return ["sessions not read yet"]
    return [sessions.session_line(row) for row in agent_sessions["rows"]]


def sessions_title(state: Mapping[str, Any]) -> str:
    agent_sessions, counts = state["sessions"], state["counts"]
    return (
        f"Agent sessions ({counts['sessions']}, {gib(agent_sessions.get('memory_bytes'))}, "
        f"{counts['parking_candidates']} parking candidate(s))"
    )


def change_line(row: Mapping[str, Any]) -> str:
    return f'{STATE_WORDS.get(row["state"], row["state"])}: "{row.get("subject")}" [{row["citation"]}]'


def pressure_text(pressure: Mapping[str, Any] | None) -> str:
    parts = []
    for resource in ("memory", "io", "cpu"):
        lane = (pressure or {}).get(resource) or {}
        some, full = lane.get("some") or {}, lane.get("full") or {}
        if some:
            parts.append(
                f"{resource} some {some.get('avg10', 0):.0f}%"
                + (f" full {full['avg10']:.0f}%" if "avg10" in full else "")
            )
    return "pressure (10s average): " + (", ".join(parts) or "unavailable")


def memory_text(limits: Mapping[str, Any]) -> str:
    memory = limits.get("memory") or {}
    if not memory:
        return "memory: unavailable"
    return (
        f"memory: {gib(memory.get('available'))} available of {gib(memory.get('total'))}, "
        f"page cache {gib(memory.get('page_cache'))}, "
        f"swap {gib(memory.get('swap_used'))} of {gib(memory.get('swap_total'))} used"
    )


def slice_lines(limits: Mapping[str, Any]) -> list[str]:
    lines = []
    for row in limits.get("slices") or []:
        limit = row.get("memory_max") or row.get("memory_high")
        lines.append(
            f"{row['slice']}: {gib(row.get('memory_current'))}"
            + (f" of {gib(limit)} limit" if limit else ", no limit")
            + (
                f" (high {gib(row['memory_high'])})"
                if row.get("memory_high") and row.get("memory_max")
                else ""
            )
        )
    return lines


def usage_lines(limits: Mapping[str, Any]) -> list[str]:
    lines = []
    claude = limits.get("claude") or {}
    if claude.get("error"):
        lines.append(f"Claude usage: unavailable ({claude['error']})")
    elif claude:
        parts = []
        for label, key in (("5-hour", "five_hour"), ("weekly", "seven_day")):
            percent = claude.get(f"{key}_percent")
            if percent is not None:
                parts.append(
                    f"{label} {percent:.0f}% used, resets {claude.get(f'{key}_resets_at')}"
                )
        lines.append(
            "Claude usage: "
            + ("; ".join(parts) or "no window reported")
            + f" (read {claude.get('observed_at')})"
        )
    codex = limits.get("codex") or {}
    if codex.get("error"):
        lines.append(f"Codex usage: unavailable ({codex['error']})")
    elif codex:
        parts = [
            f"{window.get('window_minutes', 0) // 60}-hour window {window.get('used_percent', 0):.0f}% used, resets {window.get('resets_at')}"
            for window in codex.get("windows") or []
        ]
        lines.append(
            "Codex usage: "
            + ("; ".join(parts) or "no window reported")
            + f" (read {codex.get('observed_at')})"
        )
    return lines


def limit_lines(limits: Mapping[str, Any]) -> list[str]:
    return [
        *usage_lines(limits),
        memory_text(limits),
        *slice_lines(limits),
        pressure_text(limits.get("pressure")),
    ]


def product_line(row: Mapping[str, Any]) -> str:
    tasks, checks, deployment = row["tasks"], row["checks"], row["deployment"]
    parts = [
        f"tasks {tasks.get('open', '?')} open, {tasks.get('in_progress', '?')} in progress"
        if tasks.get("open") is not None
        else "tasks not tracked"
        if not tasks.get("error")
        else f"tasks unavailable ({tasks['error']})",
        "check "
        + str(checks.get("state"))
        + (f" ({', '.join(checks['failing'])})" if checks.get("failing") else ""),
    ]
    if row.get("last_merged"):
        last = row["last_merged"]
        parts.append(f"last merged {last['commit'][:9]} at {last['at']}")
    if deployment.get("kind") == "none":
        parts.append("not deployed on this machine")
    else:
        parts.append(
            f"running {str(deployment.get('revision'))[:9]} ({deployment['kind']})"
            + (
                f", {row['merged_not_live']} merged not yet live"
                if row.get("merged_not_live")
                else ""
            )
        )
    units = row.get("units") or []
    idle = [
        f"{unit['unit']} ({unit.get('state')})"
        for unit in units
        if unit.get("state") not in {"active", "activating"}
    ]
    if units:
        parts.append(
            f"{len(units) - len(idle)} of {len(units)} units active"
            + (
                f", not running: {', '.join(idle[:IDLE_UNITS_NAMED])}"
                + (
                    f" and {len(idle) - IDLE_UNITS_NAMED} more"
                    if len(idle) > IDLE_UNITS_NAMED
                    else ""
                )
                if idle
                else ""
            )
        )
    return f"{row['project']}: " + "; ".join(parts)


def clock_lines(forecast: Mapping[str, Any]) -> list[str]:
    names = {
        "agent_working": "agent working time",
        "waiting_for_machine": "waiting for machine resources",
        "waiting_for_operator": "waiting for the operator",
        "total_elapsed": "total elapsed",
    }
    return [f"{names[key]}: {range_text(forecast['clocks'][key])}" for key in names]


def summary_lines(state: Mapping[str, Any]) -> dict[str, list[str]]:
    """Ready-made short lines for the desktop panel, in display order."""

    def head(rows: list[Any], render: Any) -> list[str]:
        lines = [render(row) for row in rows[:PANEL_ROWS]]
        if len(rows) > PANEL_ROWS:
            lines.append(f"and {len(rows) - PANEL_ROWS} more on the hub page")
        return lines

    finished = state["finished"]
    return {
        "waiting": head(state["waiting"], waiting_line),
        "running": head([*state["running"], *state["queued"]], job_line),
        "finished": head(finished["new"], change_line),
        "merged_not_live": head(finished["merged_not_live"], change_line),
        "stalled": head(state["stalled"], lambda row: row["text"]),
        "failed": head(
            state["rest"]["failed_new"],
            lambda row: (
                f"{row['label']} ended {row['outcome']} (exit {row['exit_code']}) at {row['ended_at']}"
            ),
        ),
        "limits": limit_lines(state["limits"]),
        "products": [product_line(row) for row in state["products"]],
        "activations": head(state["activations"], activation_line),
        "claims": claim_lines(state["claims"])[:PANEL_ROWS],
        "sessions": session_lines(state["sessions"])[:PANEL_ROWS],
    }


def render_text(state: Mapping[str, Any]) -> str:
    counts, finished, forecast = state["counts"], state["finished"], state["forecast"]
    out = [
        f"State of agent work at {state['generated_at']} (last looked: {state.get('last_looked_at') or 'never'})",
        "",
    ]

    def section(title: str, lines: list[str], empty: str) -> None:
        out.append(title)
        out.extend(f"  {line}" for line in lines) if lines else out.append(f"  {empty}")
        out.append("")

    section(
        f"Waiting on you ({counts['waiting']})",
        [waiting_line(r) for r in state["waiting"]],
        "nothing needs you",
    )
    section(
        f"Running ({counts['running']} running, {counts['queued']} queued)",
        [job_line(r) for r in [*state["running"], *state["queued"]]],
        "no jobs",
    )
    if state["activations"]:
        section(
            f"Activations ({counts['activations']})",
            [activation_line(r) for r in state["activations"]],
            "",
        )
    if state["claims"]["active"]:
        section(
            f"Path claims ({counts['claims']}, {counts['claims_overlapping']} overlapping)",
            claim_lines(state["claims"]),
            "",
        )
    new = [change_line(r) for r in finished["new"][:TEXT_FINISHED_ROWS]]
    if len(finished["new"]) > TEXT_FINISHED_ROWS:
        new.append(
            f"and {len(finished['new']) - TEXT_FINISHED_ROWS} more (all of them with --json)"
        )
    section(
        f"Finished since you last looked ({counts['finished_new']})", new, "nothing new"
    )
    section(
        f"Merged, not yet live ({counts['merged_not_live']})",
        [change_line(r) for r in finished["merged_not_live"]],
        "none",
    )
    if finished["unverified"]:
        section(
            "Merged, not verified", [change_line(r) for r in finished["unverified"]], ""
        )
    section(
        f"Stalled or looping ({counts['stalled']})",
        [r["text"] for r in state["stalled"]],
        "no signal",
    )
    section(
        "Forecast",
        [
            *(
                f"{job['label']} #{job['task_id']}: usually {range_text(job['expected'])}"
                for job in forecast["jobs"]
            ),
            *(
                f"{task['project']} {task['id']} ({task['kind']}, size {task['size'] or 'not set'}): "
                f"{range_text(task['history']['claim_to_close'])}"
                + (
                    f"; {task['history']['fallback']}"
                    if task["history"].get("fallback")
                    else ""
                )
                for task in forecast["tasks"]
            ),
            *clock_lines(forecast),
        ],
        "no history",
    )
    section(
        "Products",
        [product_line(r) for r in state["products"]],
        "no registered project",
    )
    section("Limits and load", limit_lines(state["limits"]), "unavailable")
    section(
        sessions_title(state),
        session_lines(state["sessions"]),
        "no interactive session",
    )
    stale = [
        f"{name}: {health['error']}"
        for name, health in state["sources"].items()
        if health.get("error")
    ]
    if stale:
        section("Sources with errors", stale, "")
    return "\n".join(out)
