"""Declaration inventory with one complete, revision-bound census observation.

Historical legacy rows are retained by the producer but are never current
usage proof. Shell history, activation logs and producer mtimes describe
observations; incomplete route coverage cannot establish unusedness.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

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


class DeclarationIndex(dict):
    """Read diagnostics stay outside the declaration fingerprint."""

    def __init__(self, value=(), *, status: str, reason: str = ""):
        super().__init__(value)
        self.metadata = {"status": status, "reason": reason}


def load_index(path: Path | None) -> dict[str, Any]:
    """Read declarations with separate missing/access/format diagnostics.

    Invalid declarations supply no rows. Diagnostics are attributes, so they
    do not change the digest used to join a census to its declarations.
    """
    if path is None:
        return DeclarationIndex(status="not-configured")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        try:
            path.lstat()
        except FileNotFoundError:
            return DeclarationIndex(status="missing")
        except OSError as error:
            return DeclarationIndex(status="unavailable", reason=str(error))
        return DeclarationIndex(status="unavailable", reason="index link target is unavailable")
    except OSError as error:
        return DeclarationIndex(status="unavailable", reason=str(error))
    except (UnicodeError, json.JSONDecodeError) as error:
        return DeclarationIndex(status="invalid", reason=str(error))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return DeclarationIndex(status="invalid", reason="unsupported declaration schema")
    if not isinstance(value.get("rows"), list):
        return DeclarationIndex(status="invalid", reason="declaration rows must be an array")
    return DeclarationIndex(value, status="selected")


class Census(dict):
    """Selected observation and its gaps travel together through every consumer."""

    def __init__(self, rows=(), metadata=None):
        super().__init__(rows)
        self.metadata = metadata or {"status": "unavailable", "coverage_gaps": [{"source": "census", "status": "unavailable"}]}


def reverse_records(stream, progress=None, cancelled=None, chunk_size=64 * 1024):
    """Yield records newest first, retaining only the current complete record.

    An unterminated tail is discarded chunk by chunk, even if it is very large.
    None marks that discarded tail. Cancellation is checked between reads and
    record decodes; KeyboardInterrupt also propagates normally.
    """
    stream.seek(0, 2)
    size = position = stream.tell()
    scanned = 0
    fragments = []
    terminated = False
    if position:
        stream.seek(position - 1)
        terminated = stream.read(1) == b"\n"
        if terminated:
            position -= 1
    while position:
        if cancelled and cancelled():
            raise InterruptedError("census read cancelled")
        start = max(0, position - chunk_size)
        stream.seek(start)
        chunk = stream.read(position - start)
        scanned += len(chunk)
        if progress:
            progress(scanned, size)
        pieces = chunk.split(b"\n")
        for suffix in reversed(pieces[1:]):
            if cancelled and cancelled():
                raise InterruptedError("census read cancelled")
            if terminated:
                fragments.append(suffix)
                yield b"".join(reversed(fragments))
            else:
                yield None
            fragments = []
            terminated = True
        if terminated:
            fragments.append(pieces[0])
        position = start
    if terminated and fragments:
        yield b"".join(reversed(fragments))
    elif size and not terminated:
        yield None


def load_census(path: Path | None, *, progress: Callable[[int, int], None] | None = None,
                cancelled: Callable[[], bool] | None = None) -> Census:
    """Select a whole completed observation by actual JSONL boundaries.

    Read backwards in chunks, stopping at the first supported complete run.
    There is no byte cutoff masquerading as absence; only one candidate record
    is assembled at a time, and torn tails do not accumulate in memory.
    """
    if path is None:
        return Census()
    scanned = total = 0
    reported = 0
    def report(read, size):
        nonlocal scanned, total, reported
        scanned, total = read, size
        if progress:
            progress(read, size)
        elif read - reported >= 4 * 1024 * 1024:
            print(f"sinnix capabilities: scanned {read} of {size} census bytes", file=sys.stderr)
            reported = read
    try:
        with path.open("rb") as stream:
            return _select_census(reverse_records(stream, report, cancelled), lambda: (scanned, total))
    except InterruptedError:
        return Census(metadata={"status": "cancelled", "bytes_scanned": scanned,
                                "coverage_gaps": [{"source": "census", "status": "cancelled", "reason": "observation selection cancelled; no absence inferred"}]})
    except OSError as error:
        return Census(metadata={"status": "unavailable", "coverage_gaps": [
            {"source": "census", "status": "unavailable", "reason": str(error)}]})


def _select_census(records, scan_counts) -> Census:
    invalid = False
    for line in records:
        if line is None:
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
            selected[key] = {**row, "ts": value["ts"], "window_days": value.get("window_days"),
                             "since": value.get("since"), "until": value.get("until")}
        else:
            meta = {k: value.get(k) for k in ("snapshot_id", "ts", "collected_at", "since", "until", "window_days",
                                            "declaration_revision", "declaration_sources", "index_digest", "classes", "coverage_gaps")}
            meta.update(status="selected", ignored_incomplete_tail=invalid,
                        bytes_scanned=scan_counts()[0], ledger_bytes=scan_counts()[1], age_seconds=max(0, int(time.time()) - value["ts"]))
            return Census(selected, meta)
        invalid = True
    return Census(metadata={"status": "historical-or-unavailable", "bytes_scanned": scan_counts()[0],
                            "coverage_gaps": [{"source": "census", "status": "unavailable", "reason": "no complete supported snapshot in ledger; legacy rows are historical"}]})


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
        "since": row.get("since"), "until": row.get("until"),
        "coverage_gaps": row.get("coverage_gaps") or [], "caller_identity": "unknown",
    }


def coverage_lines(value: dict[str, Any]) -> list[str]:
    """Readable gap reasons from the same projection used by every surface."""
    return [f"{gap.get('source') or gap.get('class') or 'coverage'}: {gap.get('status', 'unknown')} — {gap.get('reason') or 'coverage not established'}"
            for gap in value.get("coverage_gaps") or [] if isinstance(gap, dict)]


def evidence_lines(census: dict[str, Any] | None) -> list[str]:
    if not census:
        return []
    lines = [f"Collected at {census.get('ts', 'unknown')}; window {census.get('since') or '?'} to {census.get('until') or '?'} ({census.get('window_days') or '?'} days); caller identity unknown"]
    for name, source in (census.get("sources") or {}).items():
        if not source:
            continue
        fields = [f"{key}={source[key]}" for key in ("status", "type", "n", "time_basis", "since_ns", "until_ns", "earliest_retained", "latest_retained", "retention", "count_basis", "last", "action") if source.get(key) is not None]
        lines.append(f"{name}: " + "; ".join(fields))
        outcomes = source.get("outcomes") or {}
        if outcomes:
            lines.append(f"{name} outcomes: " + ", ".join(f"{key}={count}" for key, count in sorted(outcomes.items())))
        for key in ("limitation", "scope"):
            if source.get(key):
                lines.append(f"{name}: {source[key]}")
    lines.extend(coverage_lines(census))
    lines.extend(f"Reference: {path}" for path in census.get("consumer_paths") or [])
    lines.extend(f"Declared dependency consumer: {name}" for name in census.get("dependency_consumers") or [])
    if census.get("static_ref_scope"):
        lines.append(f"Reference scope: {census['static_ref_scope']}")
    if census.get("never_prune"):
        lines.append("Secret inventory: never prune")
    return lines


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
        merged["evidence_details"] = evidence_lines(merged["census"])
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
        "index_present": index.get("schema") == SCHEMA,
        "index_status": getattr(index, "metadata", {"status": "selected" if index.get("schema") == SCHEMA else "unavailable"}),
        "rows": rows,
        "groups": groups,
        "counts": {group["kind"]: len(group["rows"]) for group in groups},
        "census_status": meta,
        "census_details": coverage_lines(meta),
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
