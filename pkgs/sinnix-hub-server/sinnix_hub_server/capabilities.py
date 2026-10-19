"""The declaration inventory: every capability the host declares, plus the
hub's own routes, grouped by kind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "sinnix-capability-index-v1"
DEFAULT_INDEX = Path("/etc/sinnix/capability-index.json")

# Display order and the one-line framing for each kind. The order is the
# operator's reach order: the things typed daily first, the registries that
# answer "what is this thing called again" last.
KINDS: tuple[tuple[str, str, str], ...] = (
    ("hub-page", "Hub pages", "served by the hub"),
    ("command", "Devshell commands", "inside `nix develop` / direnv, from the repo"),
    ("script", "Scripts", "`sinnix <name>`, from anywhere"),
    ("service", "Services", "systemd units this host declares and governs"),
    ("ai-backend", "AI backends", "model endpoints, socket-activated"),
    ("capture-lane", "Capture lanes", "what this machine records about itself"),
    ("feature", "Features", "capabilities the host turns on or off wholesale"),
    ("skill", "Agent skills", "loadable procedure for Claude/Codex/Gemini"),
    ("mcp-server", "MCP servers", "tools agents can reach, by profile tier"),
    ("agent-cli", "Agent CLIs", "which client, which MCP profile, which backend"),
)

KIND_LABELS = {kind: label for kind, label, _ in KINDS}
KIND_ORDER = {kind: position for position, (kind, _, _) in enumerate(KINDS)}


class DeclarationIndex(dict):
    """Read diagnostics travel as an attribute, outside the declarations."""

    def __init__(self, value=(), *, status: str, reason: str = ""):
        super().__init__(value)
        self.metadata = {"status": status, "reason": reason}


def load_index(path: Path | None) -> dict[str, Any]:
    """Read declarations with separate missing/access/format diagnostics.

    Invalid declarations supply no rows.
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
        return DeclarationIndex(
            status="unavailable", reason="index link target is unavailable"
        )
    except OSError as error:
        return DeclarationIndex(status="unavailable", reason=str(error))
    except (UnicodeError, json.JSONDecodeError) as error:
        return DeclarationIndex(status="invalid", reason=str(error))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return DeclarationIndex(
            status="invalid", reason="unsupported declaration schema"
        )
    if not isinstance(value.get("rows"), list):
        return DeclarationIndex(
            status="invalid", reason="declaration rows must be an array"
        )
    return DeclarationIndex(value, status="selected")


def merge(
    index: dict[str, Any],
    extra_rows: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """One view: index rows plus the rows only this process can supply."""
    rows: list[dict[str, Any]] = []
    for row in list(index.get("rows") or []) + list(extra_rows):
        if not isinstance(row, dict) or not row.get("kind") or not row.get("name"):
            continue
        rows.append(dict(row))
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
        "index_status": getattr(
            index,
            "metadata",
            {"status": "selected" if index.get("schema") == SCHEMA else "unavailable"},
        ),
        "rows": rows,
        "groups": groups,
        "counts": {group["kind"]: len(group["rows"]) for group in groups},
    }


def build(
    index_path: Path | None = DEFAULT_INDEX,
    extra_rows: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    return merge(load_index(index_path), extra_rows)
