"""The hub's pages, rendered on request from the reducer's own state.

Every page is complete HTML: the browser fetches no data to show state. That
is deliberate -- a phone on a flaky link, or a page left open overnight, still
shows the system as of a timestamp it prints, rather than an empty skeleton
waiting on XHR. Only the *action* buttons need JavaScript, and they talk to the
bounded action API this same process serves.

Seven routes, one shell:

  /              the three-second read: a verdict, a row of tiles, then detail
  /work/         what is *running* -- named workloads, not a process list
  /services/     every attested runtime surface, with lifecycle controls
  /ai/           the local AI backends and their activation semantics
  /shaders/      the Hyprland screen-shader library, and what is applied
  /capabilities/ what this machine can do at all, and how to invoke it
  /reports/      served by Caddy off disk; the pages only link to it

The route table itself lives in shell.PAGES, with a line of prose per route,
because the capability index takes its `hub-page` rows from there: the routes
are declared in Python and nothing in Nix can see them.

These used to be written to static files by a 60s render-on-timer job. They
are rendered on request instead because the reducer already holds the state
they show: a page load reads the live snapshot rather than whatever the last
timer tick happened to catch, and there is no window of pages describing a
system that has since moved on.

Rendering never fails the request on a missing input: a degraded dashboard that
says "reducer snapshot unavailable" is more useful than no dashboard.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .. import capabilities as capability_index
from .ai import render_ai
from .capabilities import render_capabilities
from .dashboard import render_dashboard
from .probes import load_json
from .services import render_services
from .shaders import render_shaders
from .shell import PAGES
from .work import render_work

MANIFEST_SCHEMA = "sinnix-hub-manifest-v1"

ROUTES = ("/", "/work/", "/services/", "/ai/", "/shaders/", "/capabilities/")

# Where the route table is declared, for the `owner` column of the hub-page
# rows it produces.
PAGES_OWNER = "pkgs/sinnix-ops-reducer/sinnix_ops_reducer/pages/shell.py"

# `/work` without the slash is what a person types; Caddy redirects those, but
# a direct client of this socket gets the same courtesy here.
ALIASES = {path.rstrip("/"): path for path in ROUTES if path != "/"}


def is_page_route(path: str) -> bool:
    return path in ROUTES or path in ALIASES


def canonical(path: str) -> str:
    return ALIASES.get(path, path)


def load_manifest(path: Path | None) -> dict[str, Any]:
    """The Nix-generated hub manifest, or an empty one.

    An empty manifest is a renderable state, not an error: every page reads it
    with .get() defaults, so a host with no hub configured still gets pages
    that describe the system rather than a 500.
    """
    if path is None:
        return {}
    manifest, _error = load_json(path)
    if manifest is None or manifest.get("schema") != MANIFEST_SCHEMA:
        return {}
    return manifest


def hub_page_rows() -> list[dict[str, Any]]:
    """The hub's own routes as capability-index rows.

    The only kind of capability the Nix-side index cannot produce, because the
    routes are declared here. Same row shape as everything else, so the merged
    view and its consumers do not special-case them.
    """
    return [
        {
            "kind": "hub-page",
            "name": label,
            "description": description,
            "invoke": href,
            "enabled": None,
            "owner": PAGES_OWNER,
            "docs": "docs/hub.md",
        }
        for href, label, description in PAGES
    ]


def capability_view(
    index_path: Path | None, census_path: Path | None
) -> dict[str, Any]:
    return capability_index.build(index_path, census_path, hub_page_rows())


def render(
    path: str,
    manifest: dict[str, Any],
    snapshot: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
    snapshot_error: str | None = None,
    capability_index_path: Path | None = capability_index.DEFAULT_INDEX,
    usage_census_path: Path | None = capability_index.DEFAULT_CENSUS,
) -> str:
    generated = (
        dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    )
    route = canonical(path)
    if route == "/work/":
        return render_work(manifest, snapshot, inventory, generated)
    if route == "/services/":
        return render_services(manifest, inventory, generated)
    if route == "/ai/":
        return render_ai(manifest, inventory, generated)
    if route == "/shaders/":
        return render_shaders(manifest, generated)
    if route == "/capabilities/":
        return render_capabilities(
            manifest,
            capability_view(capability_index_path, usage_census_path),
            generated,
        )
    return render_dashboard(manifest, snapshot, snapshot_error, inventory, generated)


__all__ = [
    "ALIASES",
    "MANIFEST_SCHEMA",
    "PAGES",
    "ROUTES",
    "canonical",
    "capability_view",
    "hub_page_rows",
    "is_page_route",
    "load_manifest",
    "render",
]
