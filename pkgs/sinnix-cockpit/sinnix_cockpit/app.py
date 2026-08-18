"""Read-only cockpit over the steering store: /today, /calibration, /activities.

Plain server-rendered HTML with a meta-refresh tag for liveness, no
client-side JS framework: every route is read-only, so there are no forms and
no partial-swap interactivity to justify pulling a client-side library into a
fully offline localhost service. Revisit if a write-capable route lands.
"""

from __future__ import annotations

import html
import sqlite3

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import store

app = FastAPI(title="sinnix-cockpit")

_NAV = (
    '<nav><a href="/today">today</a> | '
    '<a href="/calibration">calibration</a> | '
    '<a href="/activities">activities</a></nav>'
)

_STYLE = """
<style>
  body { font-family: system-ui, sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; }
  nav { margin-bottom: 1.5rem; }
  nav a { margin-right: 1rem; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: 0.3rem 0.6rem; border-bottom: 1px solid #ddd; }
  .empty { color: #888; font-style: italic; }
  .forecast { color: #666; font-size: 0.9em; }
</style>
"""


def _page(title: str, body: str) -> str:
    return (
        f'<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="30">'
        f"<title>{html.escape(title)}</title>{_STYLE}</head>"
        f"<body>{_NAV}<h1>{html.escape(title)}</h1>{body}</body></html>"
    )


def _store_unavailable(body: str) -> str:
    return (
        f'<p class="empty">{html.escape(body)} — steering store not yet '
        f"initialized (run <code>sinnix-steer intent add ...</code> or "
        f"<code>sinnix-steer ritual morning</code> once).</p>"
    )


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return _page(
        "sinnix-cockpit",
        "<p>Read-only view of the personal steering store: today's intentions "
        "(<a href='/today'>today</a>), forecast accuracy "
        "(<a href='/calibration'>calibration</a>), and the standing menu "
        "(<a href='/activities'>activities</a>). "
        "What steering is and why: <code>docs/steering.md</code> in sinnix.</p>",
    )


@app.get("/today", response_class=HTMLResponse)
def today() -> str:
    try:
        conn = store.get_db()
    except sqlite3.OperationalError:
        return _page("Today", _store_unavailable("Today's intentions"))
    rows = store.open_commitments(conn)
    if not rows:
        body = '<p class="empty">No open commitments.</p>'
    else:
        items = []
        for r in rows:
            forecast = (
                f' <span class="forecast">[{int(r["forecast_p"] * 100)}%]</span>'
                if r["forecast_p"] is not None
                else ""
            )
            items.append(f"<li>{html.escape(r['text'])}{forecast}</li>")
        body = "<ul>" + "".join(items) + "</ul>"
    return _page("Today", body)


@app.get("/calibration", response_class=HTMLResponse)
def calibration() -> str:
    try:
        conn = store.get_db()
    except sqlite3.OperationalError:
        return _page("Calibration", _store_unavailable("Calibration curve"))
    buckets = store.calibration_buckets(conn)
    total_scored = sum(b["n"] for b in buckets)
    if total_scored == 0:
        body = (
            '<p class="empty">No scored (done/missed + forecasted) commitments yet.</p>'
        )
    else:
        rows = []
        for b in buckets:
            actual = (
                f"{b['actual_rate'] * 100:.0f}%"
                if b["actual_rate"] is not None
                else "—"
            )
            rows.append(
                f"<tr><td>{b['label']}</td><td>{b['n']}</td><td>{actual}</td></tr>"
            )
        body = (
            "<table><tr><th>Forecast bucket</th><th>N</th><th>Actual completion rate</th></tr>"
            + "".join(rows)
            + "</table>"
        )
    return _page("Calibration", body)


@app.get("/activities", response_class=HTMLResponse)
def activities() -> str:
    try:
        conn = store.get_db()
    except sqlite3.OperationalError:
        return _page("Activities", _store_unavailable("Activity menu"))
    rows = store.activities(conn)
    if not rows:
        body = '<p class="empty">No activities in the registry.</p>'
    else:
        table_rows = []
        for r in rows:
            mins = f"~{r['est_minutes']}m" if r["est_minutes"] else "—"
            table_rows.append(
                f"<tr><td>{html.escape(r['name'])}</td><td>{r['kind']}</td>"
                f"<td>{r['energy_tier']}</td><td>{mins}</td></tr>"
            )
        body = (
            "<table><tr><th>Name</th><th>Kind</th><th>Energy</th><th>Est.</th></tr>"
            + "".join(table_rows)
            + "</table>"
        )
    return _page("Activities", body)
