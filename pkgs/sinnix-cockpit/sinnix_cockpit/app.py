"""Read-only cockpit over the steering store: /today, /calibration, /activities.

Plain server-rendered HTML with a meta-refresh tag for liveness, no
client-side JS framework: every route is read-only, so there are no forms and
no partial-swap interactivity to justify pulling a client-side library into a
fully offline localhost service. Revisit if a write-capable route lands.
"""

from __future__ import annotations

import html
import os
import sqlite3
from contextlib import closing
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from . import store

app = FastAPI(title="sinnix-cockpit")
app.state.listen_host = "127.0.0.1"
app.state.listen_port = int(os.environ.get("SINNIX_COCKPIT_PORT", "8791"))


@app.middleware("http")
async def browser_boundary(request: Request, call_next):
    headers = request.headers
    fields = (
        "host", "origin", "sec-fetch-site", "sec-fetch-mode",
        "sec-fetch-dest", "sec-fetch-user",
    )
    values = {name: headers.getlist(name) for name in fields}
    valid = len(values["host"]) == 1 and all(
        len(values[name]) <= 1 for name in fields[1:]
    )
    allowed = {app.state.listen_host.lower()}
    if allowed & {"127.0.0.1", "localhost", "::1"}:
        allowed.update({"127.0.0.1", "localhost", "::1"})
    try:
        host = urlsplit("http://" + values["host"][0]) if valid else None
        valid = valid and (
            host.hostname in allowed
            and (host.port if host.port is not None else 80) == app.state.listen_port
            and host.username is None and host.password is None
            and not host.path and not host.query and not host.fragment
        )
        if valid and values["origin"]:
            origin = urlsplit(values["origin"][0])
            valid = (
                origin.scheme == "http" and origin.hostname == host.hostname
                and (origin.port if origin.port is not None else 80) == app.state.listen_port
                and origin.username is None and origin.password is None
                and not origin.path and not origin.query and not origin.fragment
            )
    except ValueError:
        valid = False
    browser = any(values[name] for name in fields[2:])
    navigation = (
        request.method in {"GET", "HEAD"}
        and headers.get("sec-fetch-mode") == "navigate"
        and headers.get("sec-fetch-dest") == "document"
        and headers.get("sec-fetch-user") == "?1"
    )
    if browser and not navigation:
        valid = valid and headers.get("sec-fetch-site") in {"same-origin", "none"}
    if not valid:
        return HTMLResponse(
            "browser request origin or host refused", status_code=403,
            headers={"Connection": "close"},
        )
    return await call_next(request)

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


def _read_store(label, query):
    try:
        with closing(store.get_db()) as conn:
            return query(conn)
    except FileNotFoundError:
        return HTMLResponse(_page(label, _store_unavailable(label)))
    except (OSError, sqlite3.Error) as error:
        return HTMLResponse(
            _page(label, f"<p>Steering store unavailable: {html.escape(str(error))}</p>"),
            status_code=503,
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
def today():
    rows = _read_store("Today", store.open_commitments)
    if isinstance(rows, HTMLResponse):
        return rows
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
def calibration():
    buckets = _read_store("Calibration", store.calibration_buckets)
    if isinstance(buckets, HTMLResponse):
        return buckets
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
def activities():
    rows = _read_store("Activities", store.activities)
    if isinstance(rows, HTMLResponse):
        return rows
    if not rows:
        body = '<p class="empty">No activities in the registry.</p>'
    else:
        table_rows = []
        for r in rows:
            mins = f"~{r['est_minutes']}m" if r["est_minutes"] else "—"
            table_rows.append(
                f"<tr><td>{html.escape(r['name'])}</td><td>{html.escape(r['kind'])}</td>"
                f"<td>{html.escape(r['energy_tier'])}</td><td>{html.escape(mins)}</td></tr>"
            )
        body = (
            "<table><tr><th>Name</th><th>Kind</th><th>Energy</th><th>Est.</th></tr>"
            + "".join(table_rows)
            + "</table>"
        )
    return _page("Activities", body)
