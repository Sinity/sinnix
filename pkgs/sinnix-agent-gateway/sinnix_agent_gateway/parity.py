"""Generated compatibility evidence for the retired Gateway V1 surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from .contracts import OBSERVABILITY_PERSISTENCE, ActionSpec
from .legacy_manifest import LEGACY_MANIFEST, LEGACY_MANIFEST_SCHEMA
from .registry import CatalogRegistry

PARITY_SCHEMA = "sinnix.gateway-legacy-parity.v1"

PreconditionSemantics = Literal["not_applicable", "supported"]
IdempotencySemantics = Literal["not_applicable", "required"]


@dataclass(frozen=True)
class LegacyMigration:
    legacy_route: str
    v2_action: str
    semantic_change: str | None = None


@dataclass(frozen=True)
class LegacyParityRow:
    """One generated V1 tool-to-V2 action compatibility record."""

    legacy_tool: str
    legacy_route: str
    v2_action: str
    v2_route: str
    required_principals: tuple[str, ...]
    bound: Literal["owner_limit_and_result_snapshot"]
    typed_failures: tuple[str, ...]
    preconditions: PreconditionSemantics
    idempotency: IdempotencySemantics
    receipt_policy: Literal["audit", "owner"]
    semantic_change: str | None = None


def _migration(
    route: str, action: str, *, semantic_change: str | None = None
) -> LegacyMigration:
    return LegacyMigration(route, action, semantic_change)


# This is deliberately a migration mapping, not a second legacy manifest. The
# pinned manifest is extracted from the historical app by the adjacent tool.
V2_MIGRATIONS = {
    "gateway_status": _migration("observe.gateway_status", "gateway.status"),
    "machine_report": _migration("observe.machine_report", "machine.query"),
    "machine_query": _migration("observe.machine_query", "machine.query"),
    "capability_search": _migration("capability_index.search", "capabilities.query"),
    "capability_describe": _migration("capability_index.describe", "capabilities.query"),
    "mcp_catalog": _migration("mcp_broker.catalog", "mcp.query"),
    "mcp_read": _migration("mcp_broker.call.read", "mcp.query"),
    "mcp_write": _migration("mcp_broker.call.write", "mcp.change"),
    "tasks_read": _migration("beads.read", "beads.query"),
    "tasks_write": _migration("beads.write", "beads.change"),
    "machine_action": _migration("ops.actions.execute", "machine.operate"),
    "desktop_read": _migration("desktop.read", "desktop.query"),
    "desktop_capture": _migration("desktop.capture", "desktop.query"),
    "desktop_action": _migration("desktop.action", "desktop.operate"),
    "terminal_read": _migration("terminals.read", "terminals.query"),
    "terminal_action": _migration("terminals.action", "terminals.operate"),
    "browser_read": _migration("browser.read", "browser.query"),
    "browser_capture": _migration("browser.capture", "browser.query"),
    "browser_action": _migration("browser.action", "browser.operate"),
    "project_list": _migration("projects.list", "projects.list"),
    "project_context": _migration("project_context.context", "projects.context"),
    "project_tree": _migration("projects.tree", "projects.tree"),
    "project_read": _migration("projects.read", "projects.read"),
    "project_search": _migration("projects.search", "projects.query"),
    "project_diff": _migration("projects.diff", "projects.diff"),
    "files_read": _migration("files.read", "files.query"),
    "files_write": _migration("files.write", "files.change"),
    "session_list": _migration("sessions.list", "sessions.query"),
    "session_read": _migration("sessions.read", "sessions.query"),
    "session_search": _migration("sessions.search", "sessions.query"),
    "memory_search": _migration("memory.search", "memory.query"),
    "memory_get": _migration("memory.get", "memory.query"),
    "timeline_query": _migration("timeline.query", "timeline.query"),
    "shell_query": _migration(
        "shell.query",
        "shell.run",
        semantic_change=(
            "V2 retires arbitrary read-only shell execution; typed shell jobs require "
            "operator authority."
        ),
    ),
    "shell_run": _migration("shell.run", "shell.run"),
    "shell_start": _migration("jobs.start_shell", "shell.run"),
    "job_list": _migration("jobs.list", "jobs.query"),
    "job_status": _migration("jobs.status", "resources.get"),
    "job_read_output": _migration("jobs.read_output", "resources.get"),
    "artifact_list": _migration("artifacts.list", "artifacts.query"),
    "artifact_read": _migration("artifacts.read", "artifacts.query"),
    "audit_tail": _migration("audit.tail", "audit.events"),
    "audit_verify": _migration("audit.verify", "audit.verify"),
    "capture_lanes": _migration("captures.lanes_visible", "captures.query"),
    "capture_query": _migration("captures.query", "captures.query"),
    "agent_launch": _migration("jobs.launch_agent", "agents.run"),
    "job_cancel": _migration("jobs.cancel", "jobs.cancel"),
    "project_write": _migration("projects.write", "projects.change"),
    "project_apply_patch": _migration("projects.apply_patch", "projects.change"),
}


def _row(legacy_tool: str, migration: LegacyMigration, action: ActionSpec) -> LegacyParityRow:
    return LegacyParityRow(
        legacy_tool=legacy_tool,
        legacy_route=migration.legacy_route,
        v2_action=action.name,
        v2_route=action.route,
        required_principals=tuple(sorted(action.principals)),
        bound="owner_limit_and_result_snapshot",
        typed_failures=tuple(sorted(action.typed_failures)),
        preconditions="supported" if action.supports_precondition else "not_applicable",
        idempotency="required" if action.supports_idempotency else "not_applicable",
        receipt_policy=action.receipt_policy,
        semantic_change=migration.semantic_change,
    )


def _validate_row(row: LegacyParityRow, registry: CatalogRegistry) -> None:
    action = registry.action(row.v2_action)
    if action.route != row.v2_route:
        raise ValueError(f"{row.legacy_tool} maps to an unexpected V2 route")
    if row.required_principals != tuple(sorted(action.principals)):
        raise ValueError(f"{row.legacy_tool} principal contract disagrees with V2")
    if row.bound != "owner_limit_and_result_snapshot":
        raise ValueError(f"{row.legacy_tool} has no bounded V2 result contract")
    if row.typed_failures != tuple(sorted(action.typed_failures)):
        raise ValueError(f"{row.legacy_tool} typed failures disagree with V2")
    if action.receipt_policy != row.receipt_policy:
        raise ValueError(f"{row.legacy_tool} receipt contract disagrees with V2")
    if not OBSERVABILITY_PERSISTENCE <= action.storage_effects:
        raise ValueError(f"{row.legacy_tool} lacks declared observability persistence")
    if action.supports_precondition != (row.preconditions == "supported"):
        raise ValueError(f"{row.legacy_tool} precondition contract disagrees with V2")
    if action.supports_idempotency != (row.idempotency == "required"):
        raise ValueError(f"{row.legacy_tool} idempotency contract disagrees with V2")


def legacy_parity_contract(registry: CatalogRegistry) -> dict[str, Any]:
    """Join the extracted V1 manifest to live V2 contracts on every request."""
    manifest = LEGACY_MANIFEST
    legacy_tools = manifest["tools"]
    assert isinstance(legacy_tools, list)
    if set(legacy_tools) != set(V2_MIGRATIONS):
        raise ValueError("legacy migrations must cover exactly the extracted tool set")
    rows = tuple(
        _row(
            legacy_tool,
            V2_MIGRATIONS[legacy_tool],
            registry.action(V2_MIGRATIONS[legacy_tool].v2_action),
        )
        for legacy_tool in legacy_tools
    )
    for row in rows:
        _validate_row(row, registry)
    return {
        "schema": PARITY_SCHEMA,
        "legacy_manifest": {
            "commit": manifest["source_commit"],
            "tool_count": len(legacy_tools),
            "canonical_bytes": manifest["canonical_bytes"],
        },
        "rows": [asdict(row) for row in rows],
    }
