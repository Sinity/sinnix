"""The /capabilities/ page: what this machine can do, and how to invoke it.

The other pages answer "what is happening". This one answers the question that
has no other surface: what exists at all. Its rows come from the eval-time
capability index (/etc/sinnix/capability-index.json), joined here with two
things the index cannot know -- whether the unit behind a capability is
currently running, and what the weekly usage census concluded about whether the
capability has ever been used.

There are no buttons. Discovering a capability is not an action verb, and the
things you would want to do with one (start a service, run a script) already
have their own page or their own shell.
"""

from __future__ import annotations

from typing import Any

from ..capabilities import VERDICT_TONES
from .probes import unit_states
from .services import unit_status
from .shell import badge, card, esc, page, row, tile

# Kinds whose rows name a systemd unit worth probing for live state.
UNIT_KINDS = {"service", "ai-backend"}


def verdict_badge(census: dict[str, Any] | None) -> str:
    if not census:
        return ""
    verdict = str(census.get("verdict") or "unknown")
    tone = VERDICT_TONES.get(verdict, "muted")
    runs = census.get("shell_runs")
    title = (
        f"usage census verdict over the last {census.get('window_days') or '?'} days"
    )
    if runs:
        title += f"; {runs} shell invocations"
    return f'<span class="badge {tone}" title="{esc(title)}">{esc(verdict)}</span>'


def enabled_badge(enabled: Any) -> str:
    if enabled is None:
        return ""
    return badge("enabled", "ok") if enabled else badge("off", "muted")


def capability_row(entry: dict[str, Any], states: dict[str, dict[str, str]]) -> str:
    name = str(entry.get("name", ""))
    meta: list[str] = []
    unit = entry.get("unit")
    if entry.get("kind") in UNIT_KINDS and unit:
        info = states.get(str(unit), {})
        # A backend behind a public endpoint is socket-activated: "inactive" is
        # its resting state, not a fault, and unit_status already knows to say
        # "idle" for those rather than raising an eyebrow.
        status, _tone = unit_status(info, bool(entry.get("endpoint")))
        meta.append(status)
    meta.append(enabled_badge(entry.get("enabled")))
    meta.append(verdict_badge(entry.get("census")))
    invoke = entry.get("invoke")
    if invoke:
        meta.append(f"<code>{esc(invoke)}</code>")
    for key in ("endpoint", "path", "tier", "category", "client", "mcpProfile"):
        value = entry.get(key)
        if not value:
            continue
        # Every script is "default" tier unless it says otherwise; printing that
        # on 78 of 81 rows is noise, not information.
        if key == "tier" and value == "default":
            continue
        meta.append(esc(str(value)))
    owner = entry.get("owner")
    if owner:
        meta.append(f'<span class="sub">{esc(owner)}</span>')
    docs = entry.get("docs")
    if docs:
        meta.append(f'<span class="sub">{esc(docs)}</span>')
    searchable = " ".join(
        str(part)
        for part in (
            name,
            entry.get("description"),
            invoke,
            entry.get("kind"),
            owner,
            (entry.get("census") or {}).get("verdict"),
        )
        if part
    ).lower()
    return row(
        f"<strong>{esc(name)}</strong> {esc(entry.get('description') or '')}",
        meta,
        search=searchable,
    )


def render_capabilities(
    manifest: dict[str, Any],
    view: dict[str, Any],
    generated: str,
) -> str:
    host = str(manifest.get("host") or view.get("host") or "sinnix")
    groups = view.get("groups") or []
    missing = ""
    if not view.get("index_present"):
        # The hub's own routes are supplied by this process, so rows exist even
        # with no index at all. Saying "unavailable" only when the page is empty
        # would hide exactly that case.
        missing = card(
            "Capability index unavailable",
            '<p class="sub">Only the hub\'s own routes are listed below. The '
            "rest of this page renders "
            "<code>/etc/sinnix/capability-index.json</code>, which every "
            "generation writes from the declarations in the config; its absence "
            "means this host was built before the index existed, or the reducer "
            "was pointed at another path.</p>",
            wide=True,
        )
    if not groups:
        return page("capabilities", host, [], "/capabilities/", missing)

    rows = view.get("rows") or []
    unit_targets = [
        (str(entry.get("manager") or "system"), str(entry["unit"]))
        for entry in rows
        if entry.get("kind") in UNIT_KINDS and entry.get("unit")
    ]
    states = unit_states(unit_targets) if unit_targets else {}

    never_used = sum(
        1
        for entry in rows
        if (entry.get("census") or {}).get("verdict") == "unused-in-window"
    )
    off = sum(1 for entry in rows if entry.get("enabled") is False)

    body = missing + (
        '<div class="tiles">'
        + tile(str(len(rows)), "capabilities")
        + tile(str(len(groups)), "kinds", "info")
        + tile(str(view.get("censused") or 0), "with a usage verdict")
        + tile(str(never_used), "unused in window", "warn" if never_used else "")
        + tile(str(off), "declared but off", "muted")
        + "</div>"
    )

    body += (
        '<section class="card wide"><h2>Everything, filterable</h2>'
        '<p class="sub">Derived at evaluation time from the declarations '
        "themselves — script frontmatter, the module factories' required "
        "descriptions, the command and MCP registries, SKILL.md frontmatter, "
        "the runtime inventory. Usage verdicts come from the weekly census "
        "(<code>sinnix census</code>); a capability with no verdict is one the "
        "census does not cover.</p>"
        '<input class="filter" id="filter" type="search" '
        'placeholder="filter by name, description, invocation, or verdict" '
        'autocomplete="off" autocapitalize="off" spellcheck="false">'
    )
    for group in groups:
        blocks = "".join(capability_row(entry, states) for entry in group["rows"])
        body += (
            f'<div class="group cols"><h3>{esc(group["label"])} '
            f"({len(group['rows'])}) — {esc(group['note'])}</h3>{blocks}</div>"
        )
    body += "</section>"

    chips = [f"{len(rows)} capabilities"]
    revision = view.get("revision")
    if revision:
        chips.append(f"rev {str(revision)[:12]}")
    return page("capabilities", host, chips, "/capabilities/", body)
