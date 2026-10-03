"""Declaration inventory with one complete, revision-bound census observation.

Historical legacy rows are retained by the producer but are never current
usage proof. Shell history, activation logs and producer mtimes describe
observations; incomplete route coverage cannot establish unusedness.
"""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "sinnix-capability-index-v1"
DEFAULT_INDEX = Path("/etc/sinnix/capability-index.json")
DEFAULT_CENSUS = Path("/realm/device/sinnix-prime/usage-census.jsonl")

# Which census class covers which capability kind. The census keys services by
# runtime-surface name, which is why a service row is also matched against every
# surface its module declared (`surfaces` in the index row).
CENSUS_CLASSES = {
    "script": "scripts",
    "service": "services",
    "ai-backend": "services",
    "mcp-server": "mcp-servers",
    "skill": "skills",
    "feature": "features",
    "command": "commands",
    "capture-lane": "capture-lanes",
    "agent-lane": "agent-lanes",
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
    "shell-match-observed": "info",
    "attempt-observed": "info",
    "historical": "muted",
    "referenced-only": "info",
    "informational-no-static-consumers": "muted",
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


class Census(dict):
    """Selected observation and its gaps travel together through every consumer."""

    def __init__(self, rows=(), metadata=None):
        super().__init__(rows)
        self.metadata = metadata or {"status": "unavailable", "coverage_gaps": [{"source": "census", "status": "unavailable"}]}


def load_census(path: Path | None) -> Census:
    """Read at most 16 MiB of the append-only report tail; select a whole run.

    A torn tail is ignored. No per-name mixing, legacy resurrection, or full
    historical ledger read. If no complete observation fits, report the gap.
    """
    if path is None:
        return Census()
    budget = 16 * 1024 * 1024
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            start = max(0, size - budget)
            stream.seek(start)
            data = stream.read(budget)
    except OSError:
        return Census()
    lines = data.splitlines(keepends=True)
    if start:
        lines = lines[1:]  # may begin in the middle of a record
    invalid = False
    for line in reversed(lines):
        if not line.endswith(b"\n"):
            invalid = True
            continue
        try:
            value = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            invalid = True
            continue
        if not isinstance(value, dict) or value.get("schema") != "sinnix-usage-census-v2":
            continue
        rows = value.get("rows")
        if value.get("complete") is not True or not isinstance(rows, list) or value.get("row_count") != len(rows):
            invalid = True
            continue
        if (not isinstance(value.get("ts"), int) or not isinstance(value.get("classes"), list)
                or not isinstance(value.get("coverage_gaps"), list)):
            invalid = True
            continue
        sources = value.get("declaration_sources") or {}
        if (not isinstance(sources, dict)
                or not isinstance(sources.get("runtime_inventory", {}), dict)):
            invalid = True
            continue
        selected = {}
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get("class"), str)
                    or not isinstance(row.get("name"), str) or not isinstance(row.get("evidence"), dict)
                    or row.get("verdict") not in {"unknown", "referenced-only", "shell-match-observed", "attempt-observed"}):
                break
            key = (row["class"], row["name"])
            if key in selected or row["class"] not in value["classes"]:
                break
            selected[key] = {**row, "ts": value["ts"], "window_days": value.get("window_days")}
        else:
            meta = {k: value.get(k) for k in ("snapshot_id", "ts", "collected_at", "since", "until", "window_days",
                                            "declaration_revision", "declaration_sources", "index_digest", "classes", "coverage_gaps")}
            meta.update(status="selected", ignored_incomplete_tail=invalid,
                        tail_bounded=start > 0, age_seconds=max(0, int(time.time()) - value["ts"]))
            return Census(selected, meta)
        invalid = True
    return Census(metadata={"status": "historical-or-unavailable", "tail_bounded": start > 0,
                            "coverage_gaps": [{"source": "census", "status": "unavailable", "reason": "no complete supported snapshot in bounded tail; legacy rows are historical"}]})


def _evidence(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    def source(name):
        return evidence.get(name) if isinstance(evidence.get(name), dict) else {}
    atuin, gateway, journald, filesystem = (source(k) for k in ("atuin", "gateway", "journald", "filesystem"))
    allowed = {"n", "last", "status", "type", "caller_identity", "time_basis", "retention",
               "earliest_retained", "latest_retained", "since_ns", "until_ns", "limitation",
               "identities", "count_basis", "action", "outcomes", "scope"}
    sources = {name: {k: v for k, v in source(name).items() if k in allowed}
               for name in ("atuin", "gateway", "journald", "filesystem")}
    return {
        "sources": sources, "never_prune": row.get("never_prune", False),
        "static_ref_scope": row.get("static_ref_scope"),
        "verdict": str(row.get("verdict") or "unknown"),
        "shell_matches": atuin.get("n"), "shell_last": atuin.get("last"),
        "typed_attempts": gateway.get("n"), "outcomes": gateway.get("outcomes"),
        "activation_matches": journald.get("n"),
        "path_written_in_window": filesystem.get("n"), "path_last_write": filesystem.get("last"),
        "static_refs": len(row.get("static_refs") or []), "consumer_paths": row.get("static_refs") or [],
        "dependency_consumers": row.get("dependency_consumers") or [],
        "window_days": row.get("window_days"), "ts": row.get("ts"),
        "coverage_gaps": row.get("coverage_gaps") or [], "caller_identity": "unknown",
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
    meta = dict(getattr(census, "metadata", {"status": "unavailable", "coverage_gaps": []}))
    digest = hashlib.sha256(json.dumps(index, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if meta.get("status") == "selected" and (meta.get("index_digest") != digest or meta.get("declaration_revision") != index.get("revision")):
        meta.update(status="declaration-mismatch", coverage_gaps=[*meta.get("coverage_gaps", []),
                    {"source": "census", "status": "historical", "reason": "observation belongs to a different declaration inventory"}])
        census = {}
    # Weekly cadence has no authority to imply a fresh run after two weeks.
    if meta.get("status") == "selected" and meta.get("age_seconds", 0) > 14 * 86400:
        meta.update(status="stale", coverage_gaps=[*meta.get("coverage_gaps", []),
                    {"source": "census", "status": "historical", "reason": "producer observation older than two weekly periods"}])
        census = {}
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
        "census_status": meta,
        "censused": sum(1 for row in rows if row.get("census")),
    }


def build(
    index_path: Path | None = DEFAULT_INDEX,
    census_path: Path | None = DEFAULT_CENSUS,
    extra_rows: Iterable[dict[str, Any]] = (),
    runtime_inventory_path: Path | None = Path("/etc/sinnix/runtime-inventory.json"),
) -> dict[str, Any]:
    census = load_census(census_path)
    sources = census.metadata.get("declaration_sources") or {}
    expected = (sources.get("runtime_inventory") or {}).get("digest")
    if expected and "services" in census.metadata.get("classes", []):
        try:
            observed = hashlib.sha256(runtime_inventory_path.read_bytes()).hexdigest() if runtime_inventory_path else None
        except OSError:
            observed = None
        if observed != expected:
            census.clear()
            census.metadata.update(status="declaration-mismatch", coverage_gaps=[*census.metadata.get("coverage_gaps", []),
                                   {"source": "runtime-inventory", "status": "historical", "reason": "runtime declaration fingerprint differs or is unavailable"}])
    return merge(load_index(index_path), census, extra_rows)
