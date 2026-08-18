"""The hub's pages, rendered on request from the reducer's own state.

Every page is complete HTML: the browser fetches no data to show state. That
is deliberate -- a phone on a flaky link, or a page left open overnight, still
shows the system as of a timestamp it prints, rather than an empty skeleton
waiting on XHR. Only the *action* buttons need JavaScript, and they talk to the
bounded action API this same process serves.

Six routes, one shell:

  /           the three-second read: a verdict, a row of tiles, then detail
  /work/      what is *running* -- named workloads, not a process list
  /services/  every attested runtime surface, with lifecycle controls
  /ai/        the local AI backends and their activation semantics
  /shaders/   the Hyprland screen-shader library, and what is applied
  /reports/   served by Caddy off disk; the pages only link to it

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

from .ai import render_ai
from .dashboard import render_dashboard
from .probes import load_json
from .services import render_services
from .shaders import render_shaders
from .work import render_work

MANIFEST_SCHEMA = "sinnix-hub-manifest-v1"

ROUTES = ("/", "/work/", "/services/", "/ai/", "/shaders/")

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


def render(
    path: str,
    manifest: dict[str, Any],
    snapshot: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
    snapshot_error: str | None = None,
) -> str:
    generated = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    route = canonical(path)
    if route == "/work/":
        return render_work(manifest, snapshot, inventory, generated)
    if route == "/services/":
        return render_services(manifest, inventory, generated)
    if route == "/ai/":
        return render_ai(manifest, inventory, generated)
    if route == "/shaders/":
        return render_shaders(manifest, generated)
    return render_dashboard(manifest, snapshot, snapshot_error, inventory, generated)


__all__ = [
    "ALIASES",
    "MANIFEST_SCHEMA",
    "ROUTES",
    "canonical",
    "is_page_route",
    "load_manifest",
    "render",
]
