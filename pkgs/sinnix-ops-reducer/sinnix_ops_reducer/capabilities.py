"""The capability index, joined with what the host knows about using it.

`/etc/sinnix/capability-index.json` is built at evaluation time from the
declarations that already describe every capability (modules/lib/capability-index.nix).
It is a static document: it knows what exists and how to invoke it, and nothing
about whether any of it was ever used.

Two things this process already holds close that answer that:

  * the hub's own route table -- the only capability kind Nix cannot see,
    because the routes are declared here in Python (pages/__init__.py);
  * the weekly usage census (`sinnix-census`, /realm/data/machine/usage-census.jsonl),
    whose evidence-joined verdict per script, service, MCP server and skill has
    until now been a file nobody opens.

Merging them is what makes the index answer the question the operator actually
has: not "what did this config declare" but "what can this machine do, what of
it has ever been used, and how do I invoke it". A capability that shows
`unused-in-window` since it shipped is the census finally closing its loop.

The merge is deliberately non-fatal at every step: a missing index, a missing
census, a census row for something that no longer exists -- each degrades to
less information, never to an error. This is a discovery surface; refusing to
render it because one input is stale would be a worse failure than showing the
part that is fresh.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "sinnix-capability-index-v1"
DEFAULT_INDEX = Path("/etc/sinnix/capability-index.json")
DEFAULT_CENSUS = Path("/realm/data/machine/usage-census.jsonl")

# Which census class covers which capability kind. The census keys services by
# runtime-surface name, which is why a service row is also matched against every
# surface its module declared (`surfaces` in the index row).
CENSUS_CLASSES = {
    "script": "scripts",
    "service": "services",
    "ai-backend": "services",
    "mcp-server": "mcp-servers",
    "skill": "skills",
}

# Display order and the one-line framing for each kind. The order is the
# operator's reach order: the things typed daily first, the registries that
# answer "what is this thing called again" last.
KINDS: tuple[tuple[str, str, str], ...] = (
    ("hub-page", "Hub pages", "served by this process, at the address you are reading"),
    ("command", "Devshell commands", "inside `nix develop` / direnv, from the repo"),
    ("script", "Scripts", "`sinnix <name>`, from anywhere"),
    ("service", "Services", "systemd units this host declares and governs"),
    ("ai-backend", "AI backends", "model endpoints, socket-activated"),
    ("capture-lane", "Capture lanes", "what this machine records about itself"),
    ("feature", "Features", "capabilities the host turns on or off wholesale"),
    ("skill", "Agent skills", "loadable procedure for Claude/Codex/Gemini"),
    ("mcp-server", "MCP servers", "tools agents can reach, by profile tier"),
    ("agent-lane", "Agent CLI lanes", "which client, which MCP profile, which backend"),
)

KIND_LABELS = {kind: label for kind, label, _ in KINDS}
KIND_ORDER = {kind: position for position, (kind, _, _) in enumerate(KINDS)}

# Verdicts the census emits, ordered from "this is used" to "nothing knows".
VERDICT_TONES = {
    "active": "ok",
    "agent-only": "ok",
    "referenced-only": "info",
    "informational-no-static-consumers": "muted",
    "unused-in-window": "warn",
    "unknown": "muted",
}


def load_index(path: Path | None) -> dict[str, Any]:
    """The Nix-generated index, or an empty one.

    Schema-checked the same way the hub manifest is: a document of the wrong
    shape is treated as absent rather than rendered as if it were ours.
    """
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return {}
    return value


def load_census(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    """Latest census verdict per (class, name).

    The census is append-only -- every weekly run adds a full set of rows -- so
    the newest timestamp for a given key wins and older runs are ignored.
    """
    if path is None:
        return {}
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        key = (str(row.get("class", "")), str(row.get("name", "")))
        if not key[0] or not key[1]:
            continue
        previous = latest.get(key)
        if previous is None or int(row.get("ts", 0)) >= int(previous.get("ts", 0)):
            latest[key] = row
    return latest


def _evidence(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    atuin = evidence.get("atuin") if isinstance(evidence.get("atuin"), dict) else {}
    polylogue = (
        evidence.get("polylogue") if isinstance(evidence.get("polylogue"), dict) else {}
    )
    journald = (
        evidence.get("journald") if isinstance(evidence.get("journald"), dict) else {}
    )
    return {
        "verdict": str(row.get("verdict") or "unknown"),
        "shell_runs": atuin.get("n"),
        "shell_last": atuin.get("last"),
        "agent_mentions": polylogue.get("n"),
        "journal_lines": journald.get("n"),
        "static_refs": len(row.get("static_refs") or []),
        "window_days": row.get("window_days"),
    }


def census_for(
    row: dict[str, Any], census: dict[tuple[str, str], dict[str, Any]]
) -> dict[str, Any] | None:
    """The census verdict for one capability row, or None if it censuses nothing.

    A service is looked up by its own name first and then by each surface its
    module declared, because the census enumerates services from the runtime
    inventory: `polylogue` the service is `polylogued` the surface, and a
    name-only join would report the whole class as uncensused.
    """
    census_class = CENSUS_CLASSES.get(str(row.get("kind")))
    if census_class is None:
        return None
    candidates = [str(row.get("name"))]
    for surface in row.get("surfaces") or []:
        if isinstance(surface, dict) and surface.get("name"):
            candidates.append(str(surface["name"]))
    for candidate in candidates:
        hit = census.get((census_class, candidate))
        if hit is not None:
            return _evidence(hit)
    return None


def merge(
    index: dict[str, Any],
    census: dict[tuple[str, str], dict[str, Any]],
    extra_rows: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """One view: index rows plus the rows only this process can supply,
    each carrying its census verdict where one exists."""
    rows: list[dict[str, Any]] = []
    for row in list(index.get("rows") or []) + list(extra_rows):
        if not isinstance(row, dict) or not row.get("kind") or not row.get("name"):
            continue
        merged = dict(row)
        merged["census"] = census_for(row, census)
        rows.append(merged)
    rows.sort(
        key=lambda item: (
            KIND_ORDER.get(str(item.get("kind")), len(KIND_ORDER)),
            str(item.get("name")),
        )
    )
    groups = []
    for kind, label, note in KINDS:
        members = [row for row in rows if row.get("kind") == kind]
        if members:
            groups.append({"kind": kind, "label": label, "note": note, "rows": members})
    # A kind the index grew that this table does not know about is still shown,
    # rather than silently dropped -- the index is the source of truth for what
    # kinds exist, not this constant.
    for kind in sorted({str(row.get("kind")) for row in rows} - set(KIND_LABELS)):
        groups.append(
            {
                "kind": kind,
                "label": kind,
                "note": "",
                "rows": [row for row in rows if row.get("kind") == kind],
            }
        )
    return {
        "schema": SCHEMA,
        "host": index.get("host"),
        "revision": index.get("revision"),
        # The hub supplies its own rows, so a non-empty view is NOT evidence
        # that the Nix-side index was read. Consumers say which one is missing.
        "index_present": bool(index.get("rows")),
        "rows": rows,
        "groups": groups,
        "counts": {group["kind"]: len(group["rows"]) for group in groups},
        "censused": sum(1 for row in rows if row.get("census")),
    }


def build(
    index_path: Path | None = DEFAULT_INDEX,
    census_path: Path | None = DEFAULT_CENSUS,
    extra_rows: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    return merge(load_index(index_path), load_census(census_path), extra_rows)
