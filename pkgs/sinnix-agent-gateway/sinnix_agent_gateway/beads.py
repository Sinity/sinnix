from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from difflib import unified_diff
from pathlib import Path
from typing import Any, Mapping

from sinnix_mcp.execution import ExecutionProfile, OwnerExecution, OwnerRoute

from .capabilities import Capability, Principal
from .config import GatewayConfig, ProjectConfig, TaskAuthorityConfig
from .results import ProtocolError


class BeadsError(ProtocolError):
    """An owner-backed failure which remains typed at the V2 boundary."""

    def __init__(
        self, message: str, code: str = "invalid_request", *, details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(code, message, details=details)


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_FIELDS = frozenset({"status", "priority", "type", "assignee", "owner", "label", "title", "description", "notes", "created", "updated", "started", "closed", "id", "spec", "pinned", "ephemeral", "template", "parent", "mol_type"})
_LIST_FLAGS = {
    "assignee": "--assignee", "closed_after": "--closed-after", "closed_before": "--closed-before",
    "created_after": "--created-after", "created_before": "--created-before", "defer_after": "--defer-after",
    "defer_before": "--defer-before", "desc_contains": "--desc-contains", "due_after": "--due-after",
    "due_before": "--due-before", "external_contains": "--external-contains", "external_ref": "--external-ref",
    "has_metadata_key": "--has-metadata-key", "id": "--id", "label_pattern": "--label-pattern",
    "label_regex": "--label-regex", "mol_type": "--mol-type", "notes_contains": "--notes-contains",
    "parent": "--parent", "priority": "--priority", "priority_max": "--priority-max",
    "priority_min": "--priority-min", "spec": "--spec", "status": "--status", "title": "--title",
    "title_contains": "--title-contains", "type": "--type", "updated_after": "--updated-after",
    "updated_before": "--updated-before", "wisp_type": "--wisp-type",
}
_LIST_REPEAT_FLAGS = {"label": "--label", "label_any": "--label-any", "exclude_label": "--exclude-label", "exclude_type": "--exclude-type", "metadata_field": "--metadata-field"}
_LIST_BOOLEAN_FLAGS = {"all": "--all", "deferred": "--deferred", "empty_description": "--empty-description", "include_gates": "--include-gates", "include_infra": "--include-infra", "include_templates": "--include-templates", "no_assignee": "--no-assignee", "no_labels": "--no-labels", "no_parent": "--no-parent", "no_pinned": "--no-pinned", "overdue": "--overdue", "pinned": "--pinned", "ready": "--ready"}
_READY_BOOLEAN_FLAGS = {"gated": "--gated", "include_deferred": "--include-deferred", "include_ephemeral": "--include-ephemeral", "unassigned": "--unassigned"}
_MAX_PAGE = 200
_MAX_CHANGESET_ACTIONS = 128
_SYMBOL_RE = re.compile(r"^\$([A-Za-z][A-Za-z0-9_]{0,63})$")
_PROJECT_REF_RE = re.compile(r"^sinnix://projects/([^/]+)(?:/beads/([^/]+))?$")


class BeadsService:
    """Typed canonical owner adapter; response snapshots are not a task mirror."""

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config, self.principal = config, principal
        self.execution = OwnerExecution(base_environment={})

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 8192, empty: bool = False) -> str:
        if not isinstance(value, str) or len(value) > maximum or (not empty and not value):
            raise BeadsError(f"{name} must be a bounded string")
        return value

    def _id(self, value: Any, name: str = "id") -> str:
        value = self._string(value, name, 128)
        if not _ID_RE.fullmatch(value):
            raise BeadsError(f"{name} is malformed")
        return value

    @staticmethod
    def _limit(value: Any, default: int = 50, maximum: int = _MAX_PAGE) -> int:
        value = default if value is None else value
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise BeadsError(f"limit must be 1-{maximum}")
        return value

    @staticmethod
    def project_ref(project_id: str) -> str:
        return f"sinnix://projects/{project_id}"

    @classmethod
    def bead_ref(cls, project_id: str, bead_id: str) -> str:
        return f"{cls.project_ref(project_id)}/beads/{bead_id}"

    def _project(self, project_id: str, write: bool) -> ProjectConfig:
        self.principal.require(Capability.TASK_WRITE if write else Capability.TASK_READ)
        try:
            project = self.config.projects[self._string(project_id, "project_id", 128)]
        except KeyError as exc:
            raise BeadsError(f"unknown project: {project_id}") from exc
        if self.principal.name == "observer" and not project.observer_read:
            raise BeadsError(f"project is unavailable to {self.principal.name}")
        if not project.path.is_dir():
            raise BeadsError(f"project checkout is unavailable: {project_id}")
        return project

    def _authority(self, project_id: str, write: bool) -> tuple[ProjectConfig, TaskAuthorityConfig]:
        project = self._project(project_id, write)
        if project.task_authority is None:
            raise BeadsError(f"project has no declared Beads task authority: {project_id}")
        return project, project.task_authority

    def _run(self, project: ProjectConfig, args: list[str], write: bool, *, text: bool = False) -> Any:
        command = [self.config.beads_command, "--directory", str(project.path), "--json"]
        if not write:
            command.append("--readonly")
        command += args
        result = self.execution.run(command, ExecutionProfile(
            route=OwnerRoute("beads"), timeout_seconds=30, cwd=project.path,
            max_stdout_bytes=self.config.max_result_bytes, max_stderr_bytes=self.config.max_result_bytes,
            environment={"HOME": str(Path.home()), "LANG": os.environ.get("LANG", "C.UTF-8"), "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"), "BEADS_ACTOR": f"sinnix-gateway:{self.principal.name}"},
        ))
        if result.failure_class == "command_timeout": raise BeadsError("Beads operation timed out", "deadline")
        if result.failure_class == "command_output_bound": raise BeadsError("Beads response exceeded configured bound", "response_bound")
        if result.failure_class:
            error = (result.stdout + b"\n" + result.stderr).decode("utf-8", "replace").strip()
            code = "precondition_failed" if result.exit_status == 13 or "--if-" in error else "owner_failed"
            raise BeadsError(error or "Beads operation failed", code)
        if text:
            return result.stdout.decode("utf-8", "replace")
        try: return json.loads(result.stdout)
        except json.JSONDecodeError as exc: raise BeadsError("Beads did not return JSON", "owner_failed") from exc

    def task_authority_status(self, project_id: str) -> dict[str, Any]:
        project, authority = self._authority(project_id, False)
        where, status = self._run(project, ["where"], False), self._run(project, ["status"], False)
        if not isinstance(where, Mapping) or not isinstance(where.get("path"), str) or not isinstance(where.get("database_path"), str):
            raise BeadsError("Beads where did not return path and database_path")
        if Path(where["path"]).resolve() != authority.workspace or Path(where["database_path"]).resolve() != authority.database:
            raise BeadsError("task_authority_mismatch: configured Beads workspace or database does not match bd where")
        if not isinstance(status, Mapping): raise BeadsError("Beads status did not return an object")
        revision = hashlib.sha256(json.dumps(status, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"project_id": project_id, "ref": self.project_ref(project_id), "owner": authority.owner, "publication_policy": authority.publication_policy, "project_uuid": authority.project_uuid, "schema_version": where.get("schema_version"), "revision": revision, "summary": status.get("summary"), "attested": True}

    def _attest(self, project_id: str, write: bool) -> tuple[ProjectConfig, dict[str, Any]]:
        project, _ = self._authority(project_id, write)
        return project, self.task_authority_status(project_id)

    @staticmethod
    def _issues(value: Any) -> list[dict[str, Any]]:
        rows = value if isinstance(value, list) else value.get("issues") if isinstance(value, Mapping) else None
        if rows is None and isinstance(value, Mapping) and isinstance(value.get("issue"), Mapping): rows = [value["issue"]]
        if rows is None and isinstance(value, Mapping) and isinstance(value.get("id"), str): rows = [value]
        if not isinstance(rows, list) or any(not isinstance(row, Mapping) or not isinstance(row.get("id"), str) for row in rows):
            raise BeadsError("Beads response omitted normalized issue records")
        return [dict(row) for row in rows]

    def _normalize(self, project_id: str, row: Mapping[str, Any], revision: str) -> dict[str, Any]:
        bead_id = self._id(row["id"])
        parent = row.get("parent_id", row.get("parent"))
        if isinstance(parent, Mapping): parent = parent.get("id")
        native_keys = {"id", "title", "description", "design", "acceptance_criteria", "status", "priority", "issue_type", "assignee", "owner", "created_at", "updated_at", "started_at", "closed_at", "close_reason", "labels", "metadata", "notes", "parent", "parent_id", "dependencies", "external_ref", "spec_id", "due_at", "defer_until", "estimate", "ephemeral"}
        links = {key: f"{self.bead_ref(project_id, bead_id)}/{key}" for key in ("comments", "history", "events", "dependencies", "dependents", "children", "refs", "jobs", "receipts")}
        links["project"] = self.project_ref(project_id)
        parent_ref = self.bead_ref(project_id, parent) if isinstance(parent, str) and _ID_RE.fullmatch(parent) else None
        if parent_ref is not None:
            links["parent"] = parent_ref
        etag = hashlib.sha256(json.dumps(dict(row), sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
        return {"ref": self.bead_ref(project_id, bead_id), "id": bead_id, "project_id": project_id, "task_revision": revision, "etag": etag, "fields": {key: row[key] for key in sorted(native_keys - {"id", "parent", "parent_id", "dependencies"}) if key in row}, "parent_ref": parent_ref, "links": links, "native": {key: value for key, value in row.items() if key not in native_keys}}

    def _includes(self, project: ProjectConfig, project_id: str, bead_id: str, includes: set[str]) -> dict[str, Any]:
        commands = {"comments": ["comments", bead_id], "history": ["history", bead_id, "--limit", "20"], "events": ["history", bead_id, "--events", "--limit", "20"], "dependencies": ["dep", "list", bead_id, "--direction", "down"], "dependents": ["dep", "list", bead_id, "--direction", "up"], "children": ["list", "--parent", bead_id, "--flat", "--limit", str(_MAX_PAGE), "--max-rows", str(_MAX_PAGE)], "refs": ["show", bead_id, "--refs"]}
        unsupported = includes - set(commands)
        unsupported -= {"blockers"}
        if unsupported: raise BeadsError(f"unsupported_capability: unsupported Beads includes: {sorted(unsupported)}")
        result = {name: self._run(project, commands[name], False) for name in sorted(includes - {"blockers"})}
        if "blockers" in includes:
            rows = self._issues(self._run(project, ["dep", "list", bead_id, "--direction", "down", "--type", "blocks"], False))
            result["blockers"] = {"count": len(rows), "items": [{key: row.get(key) for key in ("id", "title", "status", "priority", "dependency_type")} for row in rows]}
        return result

    def get(self, project_id: str, bead_id: str, *, includes: list[str] | None = None, as_of: str | None = None) -> dict[str, Any]:
        if as_of is not None:
            as_of = self._string(as_of, "as_of", 256)
        if not isinstance(includes or [], list) or not all(isinstance(item, str) for item in includes or []): raise BeadsError("includes must be a list of strings")
        project, status = self._attest(project_id, False)
        command = ["show", self._id(bead_id)]
        requested = set(includes or [])
        for include, flag in (("comments", "--include-comments"), ("dependents", "--include-dependents")):
            if include in requested:
                command.append(flag)
        if as_of is not None:
            command += ["--as-of", as_of]
        result = self._normalize(project_id, self._issues(self._run(project, command, False))[0], status["revision"])
        result["includes"] = self._includes(project, project_id, result["id"], requested)
        result["as_of"] = as_of
        return result

    @staticmethod
    def _filter_expression(filters: Mapping[str, Any]) -> str:
        def atom(field: str, value: Any) -> str:
            if field not in _FIELDS:
                raise BeadsError(f"unsupported Beads query field {field!r}", "unsupported_capability")
            op, raw = (value.get("op"), value.get("value")) if isinstance(value, Mapping) else ("=", value)
            if op not in {"=", "!=", ">", ">=", "<", "<="}:
                raise BeadsError("filter op is invalid")
            if isinstance(raw, bool): encoded = str(raw).lower()
            elif isinstance(raw, (int, float)) and not isinstance(raw, bool): encoded = str(raw)
            elif isinstance(raw, str) and raw and len(raw) <= 1000: encoded = json.dumps(raw) if any(c.isspace() for c in raw) else raw
            else: raise BeadsError(f"filter {field!r} has an invalid value")
            return f"{field}{op}{encoded}"

        def compile_node(node: Any) -> str:
            if not isinstance(node, Mapping) or not node:
                raise BeadsError("filter AST node must be a non-empty object")
            if set(node) == {"and"} or set(node) == {"or"}:
                key = next(iter(node)); children = node[key]
                if not isinstance(children, list) or not children:
                    raise BeadsError(f"filters.{key} must be a non-empty list")
                return "(" + f" {key.upper()} ".join(compile_node(item) for item in children) + ")"
            if set(node) == {"not"}:
                return "NOT (" + compile_node(node["not"]) + ")"
            return " AND ".join(atom(field, value) for field, value in sorted(node.items()))

        return compile_node(filters) if any(key in filters for key in {"and", "or", "not"}) else " AND ".join(atom(field, value) for field, value in sorted(filters.items()))

    def _native_list_filters(self, values: Mapping[str, Any], *, view: str) -> list[str]:
        if not isinstance(values, Mapping):
            raise BeadsError("native_filters must be an object")
        ready_allowed = {"assignee", "exclude_label", "exclude_type", "has_metadata_key", "label", "label_any", "label_pattern", "label_regex", "metadata_field", "mol", "mol_type", "parent", "priority", "type", *(_READY_BOOLEAN_FLAGS)}
        if view == "ready" and set(values) - ready_allowed:
            raise BeadsError(f"unsupported native ready filters: {sorted(set(values) - ready_allowed)}", "unsupported_capability")
        command: list[str] = []
        for key, flag in _LIST_FLAGS.items():
            if key not in values:
                continue
            command += [flag, self._string(str(values[key]), f"native_filters.{key}", 1_000)]
        for key, flag in _LIST_REPEAT_FLAGS.items():
            if key not in values:
                continue
            items = values[key]
            if not isinstance(items, list) or not items or len(items) > 32:
                raise BeadsError(f"native_filters.{key} must be a bounded non-empty string list")
            for item in items:
                command += [flag, self._string(item, f"native_filters.{key}", 1_000)]
        for key, flag in _LIST_BOOLEAN_FLAGS.items():
            if key in values:
                if values[key] is not True:
                    raise BeadsError(f"native_filters.{key} must be true when supplied")
                command.append(flag)
        for key, flag in _READY_BOOLEAN_FLAGS.items():
            if key in values:
                if values[key] is not True:
                    raise BeadsError(f"native_filters.{key} must be true when supplied")
                command.append(flag)
        unknown = set(values) - set(_LIST_FLAGS) - set(_LIST_REPEAT_FLAGS) - set(_LIST_BOOLEAN_FLAGS) - set(_READY_BOOLEAN_FLAGS) - {"mol", "stale_days"}
        if "mol" in values:
            command += ["--mol", self._string(str(values["mol"]), "native_filters.mol", 128)]
        if unknown:
            raise BeadsError(f"unsupported native list filters: {sorted(unknown)}", "unsupported_capability")
        return command

    def _snapshot_page(self, key: str, source_revision: str, rows: list[dict[str, Any]], limit: int, cursor: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        directory = self.config.state_dir / "beads-snapshots"; directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if cursor is None:
            token = hashlib.sha256(f"{key}:{source_revision}:{time.time_ns()}".encode()).hexdigest(); payload = {"key": key, "source_revision": source_revision, "expires_at": time.time() + 300, "rows": rows}; (directory / f"{token}.json").write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"))); offset = 0
        else:
            try:
                token, value = cursor.split(".", 1); offset = int(value); payload = json.loads((directory / f"{token}.json").read_text())
            except (OSError, ValueError, json.JSONDecodeError) as exc: raise BeadsError("stale_cursor: Beads snapshot is unavailable") from exc
            if payload.get("expires_at", 0) < time.time() or payload.get("key") != key: raise BeadsError("stale_cursor: Beads snapshot expired or belongs to another query")
            if payload.get("source_revision") != source_revision: raise BeadsError("source_changed: Beads source changed during paging")
            rows = payload["rows"]
        page = rows[offset:offset + limit]; next_cursor = f"{token}.{offset + limit}" if offset + limit < len(rows) else None
        return page, {"kind": "snapshot", "cursor": cursor, "next_cursor": next_cursor, "offset": offset, "next_offset": offset + limit if next_cursor else None, "total": len(rows), "expires_at": payload["expires_at"], "snapshot_ref": f"sinnix://results/beads-{token}"}

    def query(self, *, project_ids: list[str] | None, view: str = "query", filters: Mapping[str, Any] | None = None, expression: str | None = None, native_filters: Mapping[str, Any] | None = None, order: Mapping[str, Any] | None = None, includes: list[str] | None = None, limit: int | None = None, cursor: str | None = None) -> dict[str, Any]:
        project_ids = sorted(self.config.projects) if project_ids is None else project_ids
        if not isinstance(project_ids, list) or not project_ids or len(project_ids) > 32 or len(set(project_ids)) != len(project_ids): raise BeadsError("project_ids must contain 1-32 unique projects")
        if filters is not None and not isinstance(filters, Mapping): raise BeadsError("filters must be an object")
        expression = self._string(expression, "expression", 4000) if expression is not None else None
        generated = self._filter_expression(filters or {})
        expression = f"({generated}) AND ({expression})" if generated and expression else generated or expression
        if not isinstance(includes or [], list) or not all(isinstance(item, str) for item in includes or []): raise BeadsError("includes must be strings")
        requested = set(includes or [])
        native_args = self._native_list_filters(native_filters or {}, view=view)
        if view == "query" and native_filters:
            raise BeadsError("query supports standard filters and native expression, not list-only filters", "unsupported_capability")
        if view == "stale_claims" and set(native_filters or {}) - {"stale_days"}:
            raise BeadsError("stale_claims supports only native_filters.stale_days", "unsupported_capability")
        if view == "blocked" and native_filters:
            raise BeadsError("blocked has no owner-native filter flags", "unsupported_capability")
        rows: list[dict[str, Any]] = []; coverage: dict[str, Any] = {}; revisions: dict[str, str] = {}; parsed: dict[str, Any] = {}
        for project_id in sorted(project_ids):
            try:
                project, status = self._attest(project_id, False); revisions[project_id] = status["revision"]
                if expression: parsed[project_id] = self._run(project, ["query", expression, "--parse-only"], False)
                if (expression or view == "query") and native_args:
                    raise BeadsError("native list filters cannot be combined with the owner query route", "unsupported_capability")
                if view == "ready": command = ["ready", "--limit", str(_MAX_PAGE), "--max-rows", str(_MAX_PAGE), "--explain"]
                elif view == "blocked": command = ["blocked"]
                elif view in {"open", "all", "recent", "overdue", "deferred", "unassigned", "stale_claims", "epic_progress", "changed_since"}:
                    command = ["list", "--flat", "--limit", str(_MAX_PAGE), "--max-rows", str(_MAX_PAGE)]
                    command += {"open": ["--status", "open"], "all": ["--all"], "recent": ["--sort", "updated", "--reverse"], "overdue": ["--overdue"], "deferred": ["--deferred"], "unassigned": ["--no-assignee"], "epic_progress": ["--type", "epic"]}.get(view, [])
                    if view == "stale_claims":
                        command = ["stale", "--status", "in_progress", "--limit", str(_MAX_PAGE)]
                        if "stale_days" in (native_filters or {}): command += ["--days", str(native_filters["stale_days"])]
                    if view == "changed_since" and "updated_after" not in (native_filters or {}):
                        raise BeadsError("changed_since requires native_filters.updated_after")
                elif view == "query":
                    if not expression: raise BeadsError("query view requires filters or expression")
                    command = ["query", expression, "--limit", str(_MAX_PAGE)]
                else: raise BeadsError(f"unsupported_capability: unknown Beads view {view!r}")
                if expression and view != "query": command = ["query", expression, "--limit", str(_MAX_PAGE)]
                elif view != "stale_claims": command += native_args
                if order:
                    if not isinstance(order, Mapping) or set(order) - {"field", "reverse"} or order.get("field") not in {"priority", "created", "updated", "closed", "status", "id", "title", "type", "assignee"}: raise BeadsError("order is unsupported")
                    command += ["--sort", str(order["field"])] + (["--reverse"] if order.get("reverse") else [])
                normalized = [self._normalize(project_id, row, status["revision"]) for row in self._issues(self._run(project, command, False))]
                for row in normalized:
                    if requested: row["includes"] = self._includes(project, project_id, row["id"], requested)
                rows += normalized; coverage[project_id] = {"state": "complete", "returned": len(normalized), "total": len(normalized), "total_exact": len(normalized) < _MAX_PAGE, "paging": "owner_native_unavailable" if len(normalized) == _MAX_PAGE else "complete", "revision": status["revision"]}
            except BeadsError as exc: coverage[project_id] = {"state": "partial", "error": str(exc), "code": exc.code}
        rows.sort(key=lambda row: (row["project_id"], row["id"])); key = hashlib.sha256(json.dumps({"principal": self.principal.name, "projects": sorted(project_ids), "view": view, "filters": filters or {}, "expression": expression, "order": order or {}, "includes": sorted(requested)}, sort_keys=True, separators=(",", ":")).encode()).hexdigest(); source_revision = hashlib.sha256(json.dumps(revisions, sort_keys=True).encode()).hexdigest(); page_rows, page = self._snapshot_page(key, source_revision, rows, self._limit(limit), cursor)
        totals = {"returned": len(rows), "projects": len(project_ids), "healthy_projects": sum(item["state"] == "complete" for item in coverage.values()), "partial_projects": sum(item["state"] == "partial" for item in coverage.values()), "exact": all(item.get("total_exact", False) for item in coverage.values() if item["state"] == "complete") and not any(item["state"] == "partial" for item in coverage.values())}
        warnings = ["partial_source" for item in coverage.values() if item["state"] == "partial"]
        if any(item.get("paging") == "owner_native_unavailable" for item in coverage.values()): warnings.append("owner_paging_unavailable")
        return {"kind": "bead_query", "items": page_rows, "page": page, "coverage": coverage, "totals": totals, "source_revisions": revisions, "native_parse": parsed, "owner_capabilities": {"native_expression_parse": True, "native_offset_paging": False, "exact_query_total": False}, "warnings": warnings}

    def graph(self, project_id: str, bead_id: str, *, direction: str = "down", edge_type: str | None = None, status: str | None = None, depth: int = 1, max_rows: int = 200, mermaid: bool = False) -> dict[str, Any]:
        project, authority = self._attest(project_id, False); root = self._id(bead_id); depth = self._limit(depth, 1, 20); max_rows = self._limit(max_rows, 200, 1000)
        if direction not in {"down", "up", "both"}: raise BeadsError("direction must be down, up, or both")
        if status is not None: status = self._string(status, "status", 64)
        tree_command = ["dep", "tree", root, "--direction", direction, "--max-depth", str(depth), "--max-rows", str(max_rows)]
        if edge_type is not None: edge_type = self._string(edge_type, "edge_type", 64)
        if status is not None: tree_command += ["--status", status]
        tree = self._run(project, tree_command, False)
        mermaid_projection = self._run(project, tree_command + ["--format", "mermaid"], False, text=True) if mermaid else None
        cycle_rows = self._run(project, ["dep", "cycles"], False)
        queue, nodes, edges, cycles = [(root, 0)], {root}, [], []
        while queue:
            current, level = queue.pop(0)
            if level >= depth: continue
            commands = (["down", ["dep", "list", current, "--direction", "down"]], ["up", ["dep", "list", current, "--direction", "up"]])
            for relation, command in commands:
                if direction not in {relation, "both"}: continue
                typed_command = command + (["--type", edge_type] if edge_type else [])
                for row in self._issues(self._run(project, typed_command, False)):
                    other = self._id(row["id"]); kind = str(row.get("dependency_type", row.get("type", "depends-on")))
                    if edge_type and edge_type != kind: continue
                    edges.append({"from": self.bead_ref(project_id, current), "to": self.bead_ref(project_id, other), "relation": relation, "type": kind})
                    if len(edges) > max_rows:
                        raise BeadsError("graph exceeds max_rows", "response_bound")
                    if other == root: cycles.append([root, current, root])
                    if other not in nodes: nodes.add(other); queue.append((other, level + 1))
                    if len(nodes) > max_rows: raise BeadsError("response_bound: graph exceeds max_rows")
        owner_cycles = cycle_rows if isinstance(cycle_rows, list) else []
        result = {"ref": self.bead_ref(project_id, root), "task_revision": authority["revision"], "direction": direction, "edge_type": edge_type, "status": status, "depth": depth, "max_rows": max_rows, "nodes": [{"id": item, "ref": self.bead_ref(project_id, item)} for item in sorted(nodes)], "edges": edges, "cycles": cycles, "owner_cycles": owner_cycles, "native_tree": tree, "owner_capabilities": {"tree_type_filter": False, "edge_list_type_filter": True, "native_cycle_detection": True, "native_mermaid": True}, "partial": False}
        if mermaid: result["mermaid"] = mermaid_projection
        return result

    def memories(self, project_id: str, *, key: str | None = None, query: str | None = None) -> dict[str, Any]:
        project, _ = self._attest(project_id, False)
        if key and query: raise BeadsError("memory reads accept key or query, not both")
        command = ["recall", self._string(key, "key", 256)] if key else ["memories", self._string(query, "query", 1000)] if query else ["memories"]
        return {"kind": "bead_memory", "project_id": project_id, "result": self._run(project, command, False)}

    def _compile(self, operation: str, parameters: Mapping[str, Any]) -> tuple[str | None, list[str]]:
        values = dict(parameters)
        if operation == "create":
            command = ["create", self._string(values.pop("title", None), "title", 512)]
            flags = {"description": "--description", "design": "--design", "acceptance": "--acceptance", "type": "--type", "priority": "--priority", "assignee": "--assignee", "parent": "--parent", "due": "--due", "defer": "--defer", "external_ref": "--external-ref", "spec_id": "--spec-id", "status": "--status"}
            for key, flag in flags.items():
                if key in values: command += [flag, self._string(values.pop(key), key, 32000)]
            for key, flag in (("labels", "--labels"), ("dependencies", "--deps")):
                if key in values:
                    items = values.pop(key)
                    if not isinstance(items, list) or not all(isinstance(item, str) and item for item in items): raise BeadsError(f"{key} must be strings")
                    command += [flag, ",".join(items)]
            notes = values.pop("notes", None)
            if notes is not None:
                if not isinstance(notes, Mapping) or notes.get("mode", "append") != "append": raise BeadsError("create notes use append mode only")
                command += ["--append-notes", self._string(notes.get("text"), "notes.text", 32000)]
            if values: raise BeadsError(f"create received unsupported parameters: {sorted(values)}")
            return None, command
        if operation == "graph.create":
            graph = values.pop("graph", None)
            if not isinstance(graph, Mapping) or not graph:
                raise BeadsError("graph.create requires a bounded graph object")
            encoded = json.dumps(graph, sort_keys=True, separators=(",", ":"))
            if len(encoded.encode()) > 262_144:
                raise BeadsError("graph.create graph exceeds the owner input bound", "response_bound")
            if values:
                raise BeadsError(f"graph.create received unsupported parameters: {sorted(values)}")
            return None, ["create", "--graph", "@gateway-json:" + encoded]
        target = self._id(values.pop("id", None))
        if operation == "update":
            patch = values.pop("patch", None)
            if not isinstance(patch, Mapping) or not patch or values: raise BeadsError("update requires only a non-empty structural patch")
            command = ["update", target]; scalar = {"title": "--title", "description": "--description", "design": "--design", "acceptance": "--acceptance", "status": "--status", "priority": "--priority", "assignee": "--assignee", "due": "--due", "defer": "--defer", "estimate": "--estimate", "external_ref": "--external-ref", "spec_id": "--spec-id", "parent": "--parent"}
            values_set = patch.get("set", {})
            if not isinstance(values_set, Mapping): raise BeadsError("patch.set must be an object")
            for key, value in values_set.items():
                if key not in scalar: raise BeadsError(f"unsupported scalar patch {key!r}")
                command += [scalar[key], self._string(str(value), key, 32000, key in {"due", "defer", "parent"})]
            labels = patch.get("labels", {})
            if labels:
                if not isinstance(labels, Mapping) or set(labels) - {"add", "remove", "replace"}: raise BeadsError("patch.labels is invalid")
                for key, flag in (("add", "--add-label"), ("remove", "--remove-label"), ("replace", "--set-labels")):
                    for item in labels.get(key, []): command += [flag, self._string(item, f"labels.{key}", 256)]
            metadata = patch.get("metadata", {})
            if metadata:
                if not isinstance(metadata, Mapping) or set(metadata) - {"set", "unset"}: raise BeadsError("patch.metadata is invalid")
                for key, value in metadata.get("set", {}).items(): command += ["--set-metadata", f"{self._string(key, 'metadata key', 256)}={self._string(str(value), 'metadata value', 4000)}"]
                for key in metadata.get("unset", []): command += ["--unset-metadata", self._string(key, "metadata key", 256)]
            notes = patch.get("notes")
            if notes is not None:
                if not isinstance(notes, Mapping) or notes.get("mode", "append") not in {"append", "replace"}: raise BeadsError("patch.notes must explicitly choose append or replace")
                command += ["--append-notes" if notes.get("mode", "append") == "append" else "--notes", self._string(notes.get("text"), "patch.notes.text", 32000)]
            unset = patch.get("unset", [])
            if unset:
                if not isinstance(unset, list) or any(item not in {"due", "defer", "parent"} for item in unset): raise BeadsError("patch.unset supports due, defer, and parent")
                for item in unset: command += [scalar[item], ""]
            if set(patch) - {"set", "labels", "metadata", "notes", "unset"} or len(command) == 2: raise BeadsError("update patch contains no supported change")
            return target, command
        if operation == "claim": command = ["update", target, "--claim"]
        elif operation == "unclaim": command = ["unclaim", target]
        elif operation == "close": command = ["close", target]
        elif operation == "reopen": command = ["reopen", target]
        elif operation == "comment": command = ["comments", "add", target, self._string(values.pop("text", None), "text", 32000)]
        elif operation == "dependency.add": command = ["dep", "add", target, self._id(values.pop("depends_on", None), "depends_on"), "--type", self._string(values.pop("type", "blocks"), "type", 64)]
        elif operation == "dependency.remove": command = ["dep", "remove", target, self._id(values.pop("depends_on", None), "depends_on")]
        elif operation == "relate": command = ["dep", "relate", target, self._id(values.pop("other_id", None), "other_id")]
        elif operation == "unrelate": command = ["dep", "unrelate", target, self._id(values.pop("other_id", None), "other_id")]
        elif operation == "reparent": command = ["update", target, "--parent", self._string(values.pop("parent_id", ""), "parent_id", 128, True)]
        elif operation == "memory.remember": command = ["remember", self._string(values.pop("text", None), "text", 32000), "--key", self._string(values.pop("key", None), "key", 256)]
        elif operation == "memory.forget": command = ["forget", self._string(values.pop("key", None), "key", 256)]
        else: raise BeadsError(f"unsupported_capability: Beads operation {operation!r} is not declared")
        if operation in {"unclaim", "close", "reopen"} and "reason" in values: command += ["--reason", self._string(values.pop("reason"), "reason", 32000)]
        if values: raise BeadsError(f"{operation} received unsupported parameters: {sorted(values)}")
        return target, command

    def _with_graph_file(self, command: list[str]) -> tuple[list[str], Path | None]:
        marker = next((item for item in command if item.startswith("@gateway-json:")), None)
        if marker is None:
            return command, None
        graph_dir = self.config.state_dir / "beads-graph-inputs"; graph_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=graph_dir, prefix="graph-", suffix=".json", delete=False)
        try:
            handle.write(marker.removeprefix("@gateway-json:")); handle.flush(); os.fsync(handle.fileno())
        finally:
            handle.close()
        return [str(path) if path != marker else str(handle.name) for path in command], Path(handle.name)

    @staticmethod
    def _public_command(command: list[str]) -> list[str]:
        return ["<bounded-native-graph-plan>" if item.startswith("@gateway-json:") else item for item in command]

    @staticmethod
    def _atomicity(operation: str, native_validation: str) -> str:
        return "owner_atomic" if operation == "graph.create" and native_validation == "dry_run" else "per_step_commits"

    def change(self, project_id: str, operation: str, parameters: Mapping[str, Any], *, mode: str = "apply", preconditions: Mapping[str, Any] | None = None, preview_digest: str | None = None) -> dict[str, Any]:
        if mode not in {"preview", "apply"}: raise BeadsError("mode must be preview or apply")
        project, before_status = self._attest(project_id, mode == "apply"); target, command = self._compile(operation, parameters)
        before = self.get(project_id, target) if target else None
        if preconditions is not None:
            if not isinstance(preconditions, Mapping) or set(preconditions) - {"expected_task_revision", "expected_status", "expected_assignee", "expected_etag"}: raise BeadsError("Beads preconditions are not recognized")
            if preconditions.get("expected_task_revision") not in {None, before_status["revision"]}: raise BeadsError("task revision no longer matches", "precondition_failed")
            if target and any(key in preconditions for key in {"expected_status", "expected_assignee", "expected_etag"}):
                assert before is not None
                fields = before["fields"]
                if "expected_status" in preconditions and fields.get("status") != preconditions["expected_status"]: raise BeadsError("status no longer matches", "precondition_failed")
                if "expected_assignee" in preconditions and fields.get("assignee") != preconditions["expected_assignee"]: raise BeadsError("assignee no longer matches", "precondition_failed")
                if "expected_etag" in preconditions and before["etag"] != preconditions["expected_etag"]: raise BeadsError("etag no longer matches", "precondition_failed", details={"semantics": "gateway_best_effort"})
                if operation == "update":
                    if "expected_status" in preconditions: command += ["--if-status", str(preconditions["expected_status"])]
                    if "expected_assignee" in preconditions:
                        expected_assignee = preconditions["expected_assignee"]
                        if expected_assignee is not None and not isinstance(expected_assignee, str): raise BeadsError("expected_assignee must be a string or null")
                        command += ["--if-assignee", expected_assignee or ""]
                elif operation == "unclaim" and isinstance(preconditions.get("expected_assignee"), str):
                    command += ["--if-assignee", preconditions["expected_assignee"]]
        digest = hashlib.sha256(json.dumps({"project": project_id, "operation": operation, "command": self._public_command(command), "revision": before_status["revision"]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        preview = {"mode": "preview", "preview_digest": digest, "project_ref": self.project_ref(project_id), "target_ref": self.bead_ref(project_id, target) if target else None, "owner_route": "beads.cli", "owner_version": before_status.get("schema_version"), "command": self._public_command(command), "preconditions": dict(preconditions or {}), "before": before, "before_revision": before_status["revision"], "precondition_semantics": {"expected_status": "native" if operation == "update" else "gateway_best_effort", "expected_assignee": "native" if operation in {"update", "unclaim"} else "gateway_best_effort", "expected_etag": "gateway_best_effort"}, "atomicity": "per_step_commits"}
        native_command, graph_path = self._with_graph_file(command)
        native_validation = "unavailable"
        try:
            if mode == "preview":
                if operation in {"create", "graph.create"}:
                    self._run(project, native_command + ["--dry-run"], True)
                    native_validation = "dry_run"
                preview["native_validation"] = native_validation
                preview["atomicity"] = self._atomicity(operation, native_validation)
                return preview
            if preview_digest is not None and preview_digest != digest: raise BeadsError("preview digest or source revision is stale", "precondition_failed")
            if operation == "graph.create":
                self._run(project, native_command + ["--dry-run"], True)
                native_validation = "dry_run"
            native = self._run(project, native_command, True); after_status = self.task_authority_status(project_id)
        finally:
            if graph_path is not None: graph_path.unlink(missing_ok=True)
        created: dict[str, Any] | None = None
        if target is None and operation == "create":
            created_rows = self._issues(native)
            created = self._normalize(project_id, created_rows[0], after_status["revision"])
        after = self.get(project_id, target) if target else created
        history = self._includes(project, project_id, target, {"history"}).get("history") if target else None
        return {**preview, "mode": "apply", "before": before, "after": after, "before_revision": before_status["revision"], "after_revision": after_status["revision"], "owner_result": native, "owner_history_ref": f"{self.bead_ref(project_id, target)}/history" if target else (created or {}).get("links", {}).get("history"), "owner_history": history, "native_validation": native_validation, "atomicity": self._atomicity(operation, native_validation)}

    @staticmethod
    def _symbolic_references(value: Any) -> set[str]:
        if isinstance(value, str):
            match = _SYMBOL_RE.fullmatch(value)
            return {match.group(1)} if match else set()
        if isinstance(value, Mapping):
            return set().union(*(BeadsService._symbolic_references(item) for item in value.values())) if value else set()
        if isinstance(value, list):
            return set().union(*(BeadsService._symbolic_references(item) for item in value)) if value else set()
        return set()

    @staticmethod
    def _canonical_references(value: Any) -> set[str]:
        if isinstance(value, str):
            return {value} if value.startswith("sinnix://") else set()
        if isinstance(value, Mapping):
            return set().union(*(BeadsService._canonical_references(item) for item in value.values())) if value else set()
        if isinstance(value, list):
            return set().union(*(BeadsService._canonical_references(item) for item in value)) if value else set()
        return set()

    @staticmethod
    def _replace_symbols(value: Any, symbols: Mapping[str, str], *, placeholders: bool = False) -> Any:
        if isinstance(value, str):
            match = _SYMBOL_RE.fullmatch(value)
            if match is None:
                return value
            name = match.group(1)
            if placeholders:
                return f"symbol-{name}"
            try:
                return symbols[name]
            except KeyError as exc:
                raise BeadsError(f"unresolved symbolic reference: ${name}", "precondition_failed") from exc
        if isinstance(value, Mapping):
            return {key: BeadsService._replace_symbols(item, symbols, placeholders=placeholders) for key, item in value.items()}
        if isinstance(value, list):
            return [BeadsService._replace_symbols(item, symbols, placeholders=placeholders) for item in value]
        return value

    @staticmethod
    def _compensation_hint(operation: str, parameters: Mapping[str, Any], result: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        inverse = {
            "claim": "unclaim",
            "close": "reopen",
            "dependency.add": "dependency.remove",
            "relate": "unrelate",
        }.get(operation)
        if operation == "create" and result and isinstance(result.get("after"), Mapping):
            created = result["after"].get("id")
            if isinstance(created, str):
                return {"kind": "suggested_action", "operation": "close", "parameters": {"id": created}, "automatic": False}
        if inverse is not None:
            fields = {key: parameters[key] for key in ("id", "depends_on", "other_id") if key in parameters}
            return {"kind": "suggested_action", "operation": inverse, "parameters": fields, "automatic": False}
        if operation == "graph.create":
            return {"kind": "manual", "reason": "native graph creation is atomic, but its created nodes require explicit follow-up actions to compensate", "automatic": False}
        return None

    @staticmethod
    def _validate_changeset_preconditions(value: Any, index: int) -> Mapping[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, Mapping) or set(value) - {"expected_task_revision", "expected_status", "expected_assignee", "expected_etag"}:
            raise BeadsError(f"changeset action {index} preconditions are not recognized")
        revision = value.get("expected_task_revision")
        etag = value.get("expected_etag")
        status = value.get("expected_status")
        assignee = value.get("expected_assignee")
        if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision)):
            raise BeadsError(f"changeset action {index} expected_task_revision is malformed")
        if etag is not None and (not isinstance(etag, str) or not re.fullmatch(r"[0-9a-f]{64}", etag)):
            raise BeadsError(f"changeset action {index} expected_etag is malformed")
        if status is not None and (not isinstance(status, str) or len(status) > 64):
            raise BeadsError(f"changeset action {index} expected_status is malformed")
        if assignee is not None and (not isinstance(assignee, str) or len(assignee) > 256):
            raise BeadsError(f"changeset action {index} expected_assignee is malformed")
        return dict(value)

    def _changeset_plan(self, actions: Any, on_error: Any) -> dict[str, Any]:
        if on_error is None:
            on_error = "stop"
        if on_error not in {"stop", "continue"}:
            raise BeadsError("on_error must be stop or continue")
        if not isinstance(actions, list) or not actions or len(actions) > _MAX_CHANGESET_ACTIONS:
            raise BeadsError(f"actions must contain 1-{_MAX_CHANGESET_ACTIONS} ordered items")
        plan: list[dict[str, Any]] = []
        bindings: dict[str, str] = {}
        source_revisions: dict[str, str] = {}
        for index, raw in enumerate(actions):
            if not isinstance(raw, Mapping) or set(raw) - {"ref", "operation", "parameters", "preconditions", "bind"}:
                raise BeadsError(f"changeset action {index} has unsupported fields")
            if not {"ref", "operation", "parameters"} <= set(raw):
                raise BeadsError(f"changeset action {index} requires ref, operation, and parameters")
            match = _PROJECT_REF_RE.fullmatch(str(raw["ref"]))
            if match is None:
                raise BeadsError(f"changeset action {index} ref is not a canonical project or bead reference")
            project_id, bead_id = match.groups()
            operation = self._string(raw["operation"], f"actions[{index}].operation", 64)
            parameters = raw["parameters"]
            if not isinstance(parameters, Mapping):
                raise BeadsError(f"changeset action {index} parameters must be an object")
            parameters = dict(parameters)
            preconditions = self._validate_changeset_preconditions(raw.get("preconditions"), index)
            if bead_id is not None:
                parameters.setdefault("id", bead_id)
            bind = raw.get("bind")
            if bind is not None:
                bind = self._string(bind, f"actions[{index}].bind", 64)
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", bind) or operation != "create":
                    raise BeadsError(f"changeset action {index} bind is valid only for create")
                if bind in bindings:
                    raise BeadsError(f"changeset bind is duplicated: {bind}")
                bindings[bind] = project_id
            for reference in self._canonical_references(parameters):
                foreign = _PROJECT_REF_RE.fullmatch(reference)
                if foreign is not None and foreign.group(1) != project_id:
                    raise BeadsError("cross-project Beads graph edges are unsupported", "unsupported_capability")
            plan.append({"index": index, "project_id": project_id, "ref": str(raw["ref"]), "operation": operation, "parameters": parameters, "preconditions": preconditions, "bind": bind})
            if project_id not in source_revisions:
                source_revisions[project_id] = self.task_authority_status(project_id)["revision"]
        for item in plan:
            for symbol in self._symbolic_references(item["parameters"]):
                if symbol not in bindings:
                    raise BeadsError(f"changeset references unknown symbol: ${symbol}")
                if bindings[symbol] != item["project_id"]:
                    raise BeadsError("cross-project Beads graph edges are unsupported", "unsupported_capability")
            self._compile(item["operation"], self._replace_symbols(item["parameters"], {}, placeholders=True))
        payload = {"on_error": on_error, "actions": [{key: item[key] for key in ("ref", "operation", "parameters", "preconditions", "bind")} for item in plan], "source_revisions": source_revisions}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        projects = list(source_revisions)
        owner_atomic = len(plan) == 1 and plan[0]["operation"] == "graph.create"
        atomicity = "owner_atomic" if owner_atomic else "cross_project_partitioned" if len(projects) > 1 else "per_step_commits"
        return {"plan": plan, "on_error": on_error, "source_revisions": source_revisions, "preview_digest": digest, "atomicity": atomicity}

    def changeset(self, actions: Any, *, mode: str, on_error: Any = None, preview_digest: str | None = None) -> dict[str, Any]:
        if mode not in {"preview", "apply"}:
            raise BeadsError("changeset mode must be preview or apply")
        prepared = self._changeset_plan(actions, on_error)
        native_validations: dict[int, str] = {}
        if mode == "preview":
            for item in prepared["plan"]:
                if item["operation"] == "graph.create":
                    validation = self.change(item["project_id"], item["operation"], item["parameters"], mode="preview")
                    native_validations[item["index"]] = validation["native_validation"]
        owner_atomic = prepared["atomicity"] == "owner_atomic" and (mode == "apply" or native_validations.get(0) == "dry_run")
        atomicity = "owner_atomic" if owner_atomic else "per_step_commits" if prepared["atomicity"] == "owner_atomic" else prepared["atomicity"]
        public_plan = [{"index": item["index"], "ref": item["ref"], "operation": item["operation"], "bind": item["bind"], "native_validation": native_validations.get(item["index"], "not_required"), "compensation": self._compensation_hint(item["operation"], item["parameters"])} for item in prepared["plan"]]
        response = {"mode": mode, "owner_route": "beads.changeset", "source_revisions": prepared["source_revisions"], "preview_digest": prepared["preview_digest"], "on_error": prepared["on_error"], "atomicity": atomicity, "partitions": [{"project_ref": self.project_ref(project_id), "source_revision": revision, "action_indexes": [item["index"] for item in prepared["plan"] if item["project_id"] == project_id]} for project_id, revision in prepared["source_revisions"].items()], "actions": public_plan, "compensation": {"automatic": False, "claim": "No global rollback is attempted. Each applied step includes only a suggested compensation hint."}}
        if mode == "preview":
            return response
        if preview_digest is not None and preview_digest != prepared["preview_digest"]:
            raise BeadsError("changeset preview digest or per-project source revision is stale", "precondition_failed")
        symbols: dict[str, str] = {}
        outcomes: list[dict[str, Any]] = []
        halted = False
        for item in prepared["plan"]:
            outcome = {"index": item["index"], "ref": item["ref"], "operation": item["operation"]}
            if halted:
                outcomes.append({**outcome, "outcome": "skipped", "reason": "on_error=stop after an earlier failed step"})
                continue
            try:
                parameters = self._replace_symbols(item["parameters"], symbols)
                applied = self.change(item["project_id"], item["operation"], parameters, mode="apply", preconditions=item["preconditions"])
                if item["bind"] is not None:
                    after = applied.get("after")
                    if not isinstance(after, Mapping) or not isinstance(after.get("id"), str):
                        raise BeadsError("owner create response omitted the bead id required by changeset bind", "owner_failed")
                    symbols[item["bind"]] = after["id"]
                outcomes.append({**outcome, "outcome": "applied", "before_revision": applied["before_revision"], "after_revision": applied["after_revision"], "result_ref": applied.get("after", {}).get("ref") if isinstance(applied.get("after"), Mapping) else None, "bound_ref": self.bead_ref(item["project_id"], symbols[item["bind"]]) if item["bind"] is not None else None, "compensation": self._compensation_hint(item["operation"], parameters, applied)})
            except BeadsError as exc:
                outcomes.append({**outcome, "outcome": "failed", "error": {"code": exc.code, "message": str(exc)}, "compensation": self._compensation_hint(item["operation"], item["parameters"])})
                halted = prepared["on_error"] == "stop"
        after_revisions = {project_id: self.task_authority_status(project_id)["revision"] for project_id in prepared["source_revisions"]}
        return {**response, "outcomes": outcomes, "after_source_revisions": after_revisions, "partial_completion": any(item["outcome"] == "failed" for item in outcomes)}

    def operate(self, project_id: str, operation: str, parameters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        project, before = self._attest(project_id, True)
        parameters = dict(parameters or {})
        if operation == "snapshot.publish":
            if parameters:
                raise BeadsError("snapshot.publish accepts no parameters")
            directory = self.config.state_dir / "beads-publications" / project_id
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            destination = directory / "issues.jsonl"
            before_text = destination.read_text() if destination.exists() else ""
            owner_result = self._run(project, ["export", "-o", str(destination)], True, text=True)
            after_text = destination.read_text() if destination.exists() else ""
            diff = "".join(unified_diff(before_text.splitlines(keepends=True), after_text.splitlines(keepends=True), fromfile="previous", tofile="published", n=3))
            if len(diff.encode()) > self.config.max_result_bytes:
                diff = diff[: self.config.max_result_bytes] + "\n[diff truncated]\n"
            publication = {"destination": str(destination), "before_sha256": hashlib.sha256(before_text.encode()).hexdigest(), "after_sha256": hashlib.sha256(after_text.encode()).hexdigest(), "changed": before_text != after_text, "diff": diff}
        elif operation == "sync.push":
            if parameters:
                raise BeadsError("sync.push accepts no parameters")
            owner_result, publication = self._run(project, ["dolt", "push"], True), None
        elif operation == "sync.pull":
            if parameters:
                raise BeadsError("sync.pull accepts no parameters")
            owner_result, publication = self._run(project, ["dolt", "pull"], True), None
        elif operation == "backup.create":
            if parameters:
                raise BeadsError("backup.create accepts no parameters")
            owner_result, publication = self._run(project, ["backup", "create"], True), None
        elif operation == "backup.list":
            if parameters:
                raise BeadsError("backup.list accepts no parameters")
            owner_result, publication = self._run(project, ["backup", "list"], False), None
        elif operation == "backup.restore":
            backup_id = self._string(parameters.pop("backup_id", None), "backup_id", 256)
            if parameters:
                raise BeadsError("backup.restore accepts only backup_id")
            owner_result, publication = self._run(project, ["backup", "restore", backup_id], True), None
        else:
            raise BeadsError(f"unsupported_capability: Beads maintenance operation {operation!r} is not declared")
        after = self.task_authority_status(project_id)
        return {"project_ref": self.project_ref(project_id), "owner_route": "beads.maintenance", "operation": operation, "before_revision": before["revision"], "after_revision": after["revision"], "owner_result": owner_result, "publication": publication, "atomicity": "per_step_commits", "git_bookkeeping": "none"}
