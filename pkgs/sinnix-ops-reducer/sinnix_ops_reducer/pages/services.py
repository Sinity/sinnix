"""The /services/ page: every attested runtime surface, with lifecycle controls."""

from __future__ import annotations

from typing import Any

from ..actions import POLICY_PROPERTIES
from .probes import unit_states
from .shell import (
    ACTION_SCRIPT,
    badge,
    card,
    esc,
    log_card,
    page,
    row,
    tile,
)


def surface_rows(inventory: dict[str, Any] | None) -> list[dict[str, Any]]:
    surfaces = inventory.get("surfaces") if isinstance(inventory, dict) else None
    if not isinstance(surfaces, dict):
        return []
    rows = []
    for name, surface in surfaces.items():
        if not isinstance(surface, dict) or not surface.get("unit"):
            continue
        observe = (
            surface.get("observe") if isinstance(surface.get("observe"), dict) else {}
        )
        activation = (
            surface.get("activation")
            if isinstance(surface.get("activation"), dict)
            else {}
        )
        effective_resources = (
            surface.get("effectiveResources")
            if isinstance(surface.get("effectiveResources"), dict)
            else {}
        )
        rows.append(
            {
                "name": name,
                "unit": str(surface["unit"]),
                "manager": str(surface.get("manager") or "system"),
                "kind": str(surface.get("kind") or "service"),
                "resource_class": str(surface.get("resourceClass") or "unclassified"),
                "restartable": bool(observe.get("restartable")),
                "activation": activation,
                "effective_resources": effective_resources,
            }
        )
    rows.sort(key=lambda item: (item["resource_class"], item["name"]))
    return rows


def policy_controls(unit: str, effective_resources: dict[str, Any]) -> str:
    """set_policy/reset_policy controls for whichever properties this
    surface's own effectiveResources actually declares.

    The action API refuses a property the runtime inventory has not already
    set for the target ("property is not declared by the runtime
    inventory"), so a control is only ever offered for a property this
    surface can actually accept -- there is nothing here for the operator to
    discover only works after a 403. `reset_policy` is one verb that
    restores every declared property at once (it re-reads the inventory's
    own values), so one button covers all of them regardless of how many
    chips are shown."""
    declared = [
        (key, effective_resources[key])
        for key in POLICY_PROPERTIES
        if effective_resources.get(key) not in (None, "")
    ]
    if not declared:
        return ""
    chips = "".join(
        f'<span class="sub"><code>{esc(key)}</code> {esc(str(value))} '
        f"<button class=\"act\" onclick=\"setPolicy('{esc(unit)}','{esc(key)}',"
        f"'{esc(str(value))}',this)\">adjust</button></span>"
        for key, value in declared
    )
    reset = (
        f"<button class=\"act\" onclick=\"act('reset_policy','unit',"
        f"'{esc(unit)}',this)\">reset to inventory defaults</button>"
    )
    return chips + reset


def unit_status(
    info: dict[str, str], socket_activated: bool = False
) -> tuple[str, str]:
    """(badge html, tone) for one unit's live state."""
    load = info.get("LoadState", "")
    active = info.get("ActiveState")
    if load in {"not-found", ""}:
        return badge("not installed", "muted"), "muted"
    if info.get("UnitFileState") == "masked":
        return badge("masked", "bad"), "bad"
    if active == "active":
        return badge(info.get("SubState") or "active", "ok"), "ok"
    if active == "failed":
        return badge("failed", "bad"), "bad"
    if socket_activated:
        return badge("idle", "muted"), "muted"
    return badge(
        active or "inactive", "warn" if active == "activating" else "muted"
    ), "muted"


def lifecycle_controls(
    unit: str, restartable: bool, installed: bool, active: bool
) -> str:
    if not installed:
        return (
            '<span class="sub">registered in the inventory, unknown to systemd</span>'
        )
    if not restartable:
        return (
            '<span class="sub" title="the runtime inventory does not declare '
            "observe.restartable, and the action API refuses lifecycle verbs "
            'for it">not restartable</span>'
        )
    verbs = ("stop", "restart") if active else ("start",)
    return "".join(
        f'<button class="act{" danger" if verb == "stop" else ""}" '
        f"onclick=\"act('{verb}','unit','{esc(unit)}',this)\">{verb}</button>"
        for verb in verbs
    )


def render_services(
    manifest: dict[str, Any],
    inventory: dict[str, Any] | None,
    generated: str,
) -> str:
    host = str(manifest.get("host", "sinnix"))
    rows = surface_rows(inventory)
    if not rows:
        body = card(
            "Runtime inventory unavailable",
            '<p class="sub">Without <code>/etc/sinnix/runtime-inventory.json</code> '
            "there is no attested set of units to show, and the action API would "
            "refuse every target anyway.</p>",
            wide=True,
        )
        return page("services", host, [], "/services/", body)

    states = unit_states([(entry["manager"], entry["unit"]) for entry in rows])
    groups: dict[str, list[str]] = {}
    counts = {"active": 0, "failed": 0, "restartable": 0}
    for entry in rows:
        info = states.get(entry["unit"], {})
        socket_activated = entry["activation"].get("mode") == "socket-proxy"
        status, tone = unit_status(info, socket_activated)
        installed = info.get("LoadState") not in {"not-found", "", None}
        active = info.get("ActiveState") == "active"
        counts["active"] += 1 if active else 0
        counts["failed"] += 1 if tone == "bad" else 0
        counts["restartable"] += 1 if entry["restartable"] else 0
        meta = [status, f"<code>{esc(entry['unit'])}</code>", esc(entry["manager"])]
        if entry["kind"] != "service":
            meta.append(esc(entry["kind"]))
        endpoint = entry["activation"].get("publicEndpoint")
        if endpoint:
            meta.append(f"<code>{esc(endpoint)}</code>")
        controls = lifecycle_controls(
            entry["unit"], entry["restartable"], installed, active
        )
        if installed:
            controls += policy_controls(entry["unit"], entry["effective_resources"])
        groups.setdefault(entry["resource_class"], []).append(
            row(
                f"<strong>{esc(entry['name'])}</strong>",
                meta,
                controls,
                "bad" if tone == "bad" else "",
                search=f"{entry['name']} {entry['unit']} {entry['resource_class']}".lower(),
            )
        )

    body = (
        '<div class="tiles">'
        + tile(str(len(rows)), "attested surfaces")
        + tile(str(counts["active"]), "active", "ok")
        + tile(
            str(counts["failed"]), "failed or masked", "bad" if counts["failed"] else ""
        )
        + tile(str(counts["restartable"]), "controllable here", "info")
        + "</div>"
    )
    grouped = "".join(
        f'<div class="group cols"><h3>{esc(name)}</h3>{"".join(blocks)}</div>'
        for name, blocks in sorted(groups.items())
    )
    body += (
        '<section class="card wide"><h2>Every governed unit</h2>'
        '<p class="sub">Grouped by the resource class that decides its slice, '
        "weights, and ceilings. Lifecycle buttons post to the reducer's bounded "
        "action API, which independently re-checks that the unit is attested and "
        "declares <code>observe.restartable</code>. <code>adjust</code> chips "
        "cover whichever properties the runtime inventory already declares for "
        "that surface (MemoryHigh, MemoryMax, MemoryLow, CPUWeight, IOWeight, "
        "Nice); <code>reset to inventory defaults</code> restores every one of "
        "them at once from the inventory's own value, so a live tweak is "
        "reversible by construction.</p>"
        '<input class="filter" id="filter" type="search" placeholder="filter by name, unit, or class" '
        'autocomplete="off" autocapitalize="off" spellcheck="false">'
        f"{grouped}</section>"
    )
    body += log_card()
    return page(
        "services",
        host,
        [f"{len(rows)} surfaces"],
        "/services/",
        body,
        tail=ACTION_SCRIPT,
    )
