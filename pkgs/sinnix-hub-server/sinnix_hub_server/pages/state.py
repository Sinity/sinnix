"""The state page: every project's agent work on one screen.

It renders the document the operator-state engine computed and adds nothing
of its own. Order follows what the operator acts on: what waits on him, what
runs, what finished since he last looked, then the rest. Opening the page in a
browser moves "last looked" to the state it showed.
"""

from __future__ import annotations

import json
from typing import Any

from sinnix_runtime.operator_state import text
from sinnix_runtime.operator_state.engine import range_text, span

from .shell import (
    ACTION_SCRIPT,
    badge,
    card,
    empty,
    esc,
    js_arg,
    log_card,
    page,
    row,
    tile,
)

STATE_TONE = {
    "finished": "ok",
    "merged_not_live": "warn",
    "check_failing": "bad",
    "check_pending": "info",
    "check_unknown": "muted",
    "live_unknown": "muted",
}

# Moves "last looked" once the page is actually visible. `?peek=1` leaves it
# alone, for a screenshot or an agent reading the page.
LOOKED_SCRIPT = """
<script>
(function(){
  if (new URLSearchParams(location.search).has('peek')) return;
  function looked(){
    if (document.visibilityState !== 'visible') return;
    document.removeEventListener('visibilitychange', looked);
    fetch('/ops/v1/state/looked', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({generated_at: document.body.dataset.generatedAt})
    }).catch(function(){});
  }
  document.addEventListener('visibilitychange', looked);
  looked();
})();
</script>
"""


def job_button(verb: str, label: str, job: dict[str, Any]) -> str:
    """Cancel or retry one job through the hub's action API."""
    target = job.get("expected_target")
    if not isinstance(target, dict):
        if not job.get("job_id") or not isinstance(job.get("attempt"), int):
            return ""
        target = {"kind": "job", "job_id": job["job_id"], "attempt": job["attempt"]}
    return (
        f'<button class="act{" danger" if verb == "interrupt" else ""}" '
        f'data-expected-target="{esc(json.dumps(target))}" '
        f"onclick=\"act('{verb}','task_id',{js_arg(str(job.get('task_id')))},this)\">{label}</button>"
    )


def waiting_card(state: dict[str, Any]) -> str:
    rows = "".join(
        row(
            f"<strong>{esc(item.get('title'))}</strong>",
            [
                badge(str(item.get("project") or item["source"]), "warn"),
                f"<code>{esc(item.get('id'))}</code>",
                f"waiting {esc(span(item.get('age_seconds')))}",
                f"<code>{esc(item['answer_with'])}</code>"
                if item.get("answer_with")
                else "",
            ],
            tone="warn",
        )
        for item in state["waiting"]
    )
    return card(
        f"Waiting on you ({state['counts']['waiting']})",
        rows or empty("Nothing needs you."),
        "Open tasks labelled <code>human</code> in every registered project.",
        wide=True,
        anchor="waiting",
    )


def job_row(job: dict[str, Any]) -> str:
    meta = [
        badge(job["phase"], "info" if job["phase"] == "running" else "muted"),
        f"pool <code>{esc(job['pool'])}</code>",
        f"{esc(job['phase'])} {esc(span(job['seconds']))}",
        f"for {esc(text.caller_text(job.get('caller')))}",
    ]
    if job.get("waiting_because"):
        meta.append(f"<strong>{esc(job['waiting_because'])}</strong>")
    if job.get("command"):
        meta.append(f"<code>{esc(job['command'])}</code>")
    if job.get("working_directory"):
        meta.append(f"in <code>{esc(job['working_directory'])}</code>")
    meta.append(f"usually {esc(range_text(job['expected']))}")
    return row(
        f'<strong>{esc(job["label"])}</strong> <span class="sub">#{esc(job["task_id"])}</span>',
        meta,
        job_button("interrupt", "cancel", job),
    )


def running_card(state: dict[str, Any]) -> str:
    jobs = [*state["running"], *state["queued"]]
    counts = state["counts"]
    return card(
        f"Running ({counts['running']} running, {counts['queued']} queued)",
        "".join(job_row(job) for job in jobs) or empty("No job is running or queued."),
        "Declared operations in the job queue, across all projects. A queued job says what it waits behind.",
        wide=True,
        anchor="running",
    )


def change_row(change: dict[str, Any]) -> str:
    pull = change.get("pull") or {}
    link = (
        f'<a href="{esc(pull["url"])}">pull request {esc(pull["number"])}</a>, check {esc(change["check"])}'
        if pull.get("url")
        else "direct commit, no hosted check"
    )
    return row(
        f"<strong>{esc(change['project'])}</strong> <code>{esc(change['short'])}</code> "
        f"<q>{esc(change.get('subject'))}</q>",
        [
            badge(
                text.STATE_WORDS.get(change["state"], change["state"]),
                STATE_TONE.get(change["state"], "muted"),
            ),
            link,
            f"merged {esc(change.get('merged_at'))}",
            f"observed finished {esc(change['finished_at'])}"
            if change.get("finished_at")
            else "",
        ],
        tone="warn" if change["state"] == "merged_not_live" else "",
    )


def finished_cards(state: dict[str, Any]) -> str:
    finished, counts = state["finished"], state["counts"]
    out = card(
        f"Finished since you last looked ({counts['finished_new']})",
        "".join(change_row(change) for change in finished["new"])
        or empty("Nothing new."),
        "On the default branch, its check passed (or the change had none), and the revision running "
        f"on this machine contains it where the product is deployed here. Last looked: "
        f"{esc(state.get('last_looked_at') or 'never')}. The quoted text is the commit subject.",
        wide=True,
        anchor="finished",
    )
    out += card(
        f"Merged, not yet live ({counts['merged_not_live']})",
        "".join(change_row(change) for change in finished["merged_not_live"])
        or empty("Every merged change is in the running revision."),
        "On the default branch, but the running revision does not contain it yet.",
        wide=True,
        anchor="not-live",
    )
    if finished["unverified"]:
        out += card(
            f"Merged, not verified ({len(finished['unverified'])})",
            "".join(change_row(change) for change in finished["unverified"]),
            "The check is failing, still running, or could not be read.",
            wide=True,
        )
    return out


def stalled_card(state: dict[str, Any]) -> str:
    rows = "".join(
        row(esc(item["text"]), [badge(item["signal"], "bad")], tone="bad")
        for item in state["stalled"]
    )
    return card(
        f"Stalled or looping ({state['counts']['stalled']})",
        rows or empty("No signal."),
        "Three computed signals: a job far beyond its usual range, a running job with no output for "
        "30 minutes, and the same job failing three times in a row with one exit code.",
        anchor="stalled",
    )


def forecast_card(state: dict[str, Any]) -> str:
    forecast = state["forecast"]
    tasks = "".join(
        row(
            f"<strong>{esc(task['project'])}</strong> <code>{esc(task['id'])}</code> {esc(task.get('title'))}",
            [
                f"kind {esc(task['kind'])}, size {esc(task['size'] or 'not set')}",
                f"history: {esc(range_text(task['history']['claim_to_close']))}",
                esc(task["history"].get("fallback") or ""),
                f"own range {esc(span(task['own_range']['low_seconds']))} to {esc(span(task['own_range']['high_seconds']))}"
                if task.get("own_range")
                else "no own range recorded",
            ],
        )
        for task in forecast["tasks"]
    )
    body = "".join(row(esc(line), []) for line in text.clock_lines(forecast))
    body += "".join(
        row(
            f"size <strong>{esc(size['size'])}</strong>",
            [esc(range_text(size["claim_to_close"]))],
        )
        for size in forecast["sizes"]
    )
    body += (
        f"<details><summary>Tasks in progress ({len(forecast['tasks'])}), "
        f"each with the range of past tasks like it</summary>{tasks}</details>"
    )
    counts = forecast.get("history") or {}
    return card(
        "Forecast",
        body,
        "Ranges are the 10th to 90th percentile of past durations, each with the number of samples "
        "behind it; with fewer than 8 samples the range is the observed minimum to maximum. "
        f"History read: {esc(json.dumps(counts, sort_keys=True))}. "
        "<code>sinnix estimate range &lt;kind&gt; &lt;size&gt;</code> answers the same question in a terminal.",
        wide=True,
        anchor="forecast",
    )


def products_card(state: dict[str, Any]) -> str:
    rows = ""
    for product in state["products"]:
        line = text.product_line(product)
        tone = "bad" if product["checks"].get("state") == "failing" else ""
        last = product.get("last_merged") or {}
        rows += row(
            f"<strong>{esc(product['project'])}</strong>",
            [
                esc(line.partition(": ")[2]),
                f"last merged: <q>{esc(last.get('subject'))}</q> [<code>{esc(str(last.get('commit'))[:9])}</code>]"
                if last
                else "",
            ],
            tone=tone,
        )
    return card(
        "Products",
        rows or empty("No registered project."),
        "Computed per registered project: open tasks, the default branch's hosted check, the last "
        "merged change, the revision running here, and the state of its units.",
        wide=True,
        anchor="products",
    )


def limits_card(state: dict[str, Any]) -> str:
    return card(
        "Limits and load",
        "".join(row(esc(line), []) for line in text.limit_lines(state["limits"])),
        "Page cache is file-backed memory only. Full memory with a small page cache and high IO "
        "pressure is an overloaded machine even when memory pressure reads low.",
        anchor="limits",
    )


def coordination_cards(state: dict[str, Any]) -> str:
    out = ""
    if state["activations"]:
        out += card(
            f"Activations ({state['counts']['activations']})",
            "".join(
                row(esc(text.activation_line(item)), [])
                for item in state["activations"]
            ),
            "Queued and running jobs that change the live machine, with who asked and the commit "
            "their checkout stood on. The queue runs them one after another.",
            anchor="activations",
        )
    claimed = state["claims"]
    if claimed["active"]:
        out += card(
            f"Path claims ({state['counts']['claims']}, {state['counts']['claims_overlapping']} overlapping)",
            "".join(
                row(esc(line), [], tone="warn" if line.startswith("overlap:") else "")
                for line in text.claim_lines(claimed)
            ),
            "Advisory: a claim says which session works under a path and blocks nothing. "
            "Two sessions on overlapping paths are listed first.",
            anchor="claims",
        )
    return out


def sessions_card(state: dict[str, Any]) -> str:
    return card(
        text.sessions_title(state),
        "".join(row(esc(line), []) for line in text.session_lines(state["sessions"]))
        or empty("No interactive agent session."),
        "Interactive agent sessions with the memory each holds and how long it has been idle. "
        "A candidate is idle, resumable by ID and waits on nothing; `sinnix sessions park` ends "
        "candidates only when run with --apply.",
        wide=True,
        anchor="sessions",
    )


def recent_card(state: dict[str, Any]) -> str:
    rows = ""
    for job in state["rest"]["recent_jobs"]:
        failed = job.get("outcome") not in {"success", "cancelled"}
        rows += row(
            f'<strong>{esc(job.get("label"))}</strong> <span class="sub">#{esc(job.get("task_id"))}</span>',
            [
                badge(
                    str(job.get("outcome")),
                    "ok"
                    if job.get("outcome") == "success"
                    else "bad"
                    if failed
                    else "muted",
                ),
                f"exit {esc(job.get('exit_code'))}",
                f"ran {esc(span(job.get('seconds')))}",
                f"ended {esc(job.get('ended_at'))}",
                f"for {esc(text.caller_text(job.get('caller')))}",
                f"in <code>{esc(job.get('working_directory'))}</code>",
            ],
            job_button("retry", "retry", job) if failed else "",
            "bad" if failed else "",
        )
    return card(
        "Recent jobs",
        rows or empty("The job log has no finished job yet."),
        "The latest finished jobs from the job log, newest first. Retry restarts a job that ended without success.",
        wide=True,
        anchor="recent",
    )


def sources_card(state: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><th>{esc(name)}</th><td>{esc(health.get('age_seconds'))} s old, every "
        f"{esc(int(health.get('period_seconds') or 0))} s, last read took {esc(health.get('last_cost_seconds'))} s"
        f"{('; error: ' + esc(health['error'])) if health.get('error') else ''}</td></tr>"
        for name, health in (state.get("sources") or {}).items()
    )
    return (
        '<details class="card wide"><summary>Sources and their age</summary>'
        f'<table class="kv">{rows}</table></details>'
    )


def render_state(
    manifest: dict[str, Any], state: dict[str, Any] | None, generated: str
) -> str:
    host = str(manifest.get("host", "sinnix"))
    if not state:
        body = card(
            "State unavailable",
            empty("The operator-state engine has not produced a document yet."),
            wide=True,
        )
        return page(
            "state",
            host,
            [f"rendered {generated[11:19]}"],
            "/state/",
            body,
            reports_port=manifest.get("reportsPort"),
        )
    counts = state["counts"]
    body = (
        '<div class="tiles">'
        + tile(
            str(counts["waiting"]),
            "waiting on you",
            "warn" if counts["waiting"] else "ok",
            "#waiting",
        )
        + tile(
            str(counts["running"]),
            "running",
            "info" if counts["running"] else "",
            "#running",
        )
        + tile(str(counts["queued"]), "queued", "", "#running")
        + tile(
            str(counts["finished_new"]),
            "finished since you looked",
            "ok" if counts["finished_new"] else "",
            "#finished",
        )
        + tile(
            str(counts["merged_not_live"]),
            "merged, not yet live",
            "warn" if counts["merged_not_live"] else "",
            "#not-live",
        )
        + tile(
            str(counts["stalled"]),
            "stalled or looping",
            "bad" if counts["stalled"] else "",
            "#stalled",
        )
        + "</div>"
    )
    body += waiting_card(state) + running_card(state) + coordination_cards(state)
    body += finished_cards(state)
    body += stalled_card(state) + limits_card(state) + sessions_card(state)
    body += forecast_card(state)
    body += products_card(state) + recent_card(state) + log_card() + sources_card(state)
    document = page(
        "state",
        host,
        [f"computed {str(state['generated_at'])[11:19]} UTC"],
        "/state/",
        body,
        tail=ACTION_SCRIPT + LOOKED_SCRIPT,
        reports_port=manifest.get("reportsPort"),
    )
    return document.replace(
        "<body>", f'<body data-generated-at="{esc(state["generated_at"])}">', 1
    )
