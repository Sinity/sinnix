from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Mapping

from sinnix_mcp.execution import ExecutionProfile, OwnerExecution, OwnerRoute

from .capabilities import Capability, Principal
from .config import GatewayConfig, ProjectConfig, TaskAuthorityConfig


class BeadsError(ValueError):
    pass


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_FIELDS = frozenset({"status", "priority", "type", "assignee", "owner", "label", "title", "description", "notes", "created", "updated", "started", "closed", "id", "spec", "pinned", "ephemeral", "template", "parent", "mol_type"})
_MAX_PAGE = 200


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

    def _run(self, project: ProjectConfig, args: list[str], write: bool) -> Any:
        command = [self.config.beads_command, "--directory", str(project.path), "--json"]
        if not write:
            command.append("--readonly")
        command += args
        result = self.execution.run(command, ExecutionProfile(
            route=OwnerRoute("beads"), timeout_seconds=30, cwd=project.path,
            max_stdout_bytes=self.config.max_result_bytes, max_stderr_bytes=self.config.max_result_bytes,
            environment={"HOME": str(Path.home()), "LANG": os.environ.get("LANG", "C.UTF-8"), "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"), "BEADS_ACTOR": f"sinnix-gateway:{self.principal.name}"},
        ))
        if result.failure_class == "command_timeout": raise BeadsError("Beads operation timed out")
        if result.failure_class == "command_output_bound": raise BeadsError("response_bound: Beads response exceeded configured bound")
        if result.failure_class:
            error = (result.stdout + b"\n" + result.stderr).decode("utf-8", "replace").strip()
            raise BeadsError(error or "Beads operation failed")
        try: return json.loads(result.stdout)
        except json.JSONDecodeError as exc: raise BeadsError("Beads did not return JSON") from exc

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
        links = {key: f"{self.bead_ref(project_id, bead_id)}/{key}" for key in ("comments", "history", "dependencies", "dependents", "receipts")}
        links["project"] = self.project_ref(project_id)
        return {"ref": self.bead_ref(project_id, bead_id), "id": bead_id, "project_id": project_id, "task_revision": revision, "fields": {key: row[key] for key in sorted(native_keys - {"id", "parent", "parent_id", "dependencies"}) if key in row}, "parent_ref": self.bead_ref(project_id, parent) if isinstance(parent, str) and _ID_RE.fullmatch(parent) else None, "links": links, "native": {key: value for key, value in row.items() if key not in native_keys}}

    def _includes(self, project: ProjectConfig, project_id: str, bead_id: str, includes: set[str]) -> dict[str, Any]:
        commands = {"comments": ["comments", bead_id], "history": ["history", bead_id, "--limit", "100"], "events": ["history", bead_id, "--events", "--limit", "100"], "dependencies": ["dep", "list", bead_id], "dependents": ["dep", "list", bead_id, "--reverse"], "children": ["list", "--parent", bead_id, "--flat", "--limit", str(_MAX_PAGE)], "refs": ["show", bead_id]}
        unsupported = includes - set(commands)
        if unsupported: raise BeadsError(f"unsupported_capability: unsupported Beads includes: {sorted(unsupported)}")
        return {name: self._run(project, commands[name], False) for name in sorted(includes)}

    def get(self, project_id: str, bead_id: str, *, includes: list[str] | None = None, as_of: str | None = None) -> dict[str, Any]:
        if as_of is not None: raise BeadsError("unsupported_capability: Beads owner does not provide as_of reads")
        project, status = self._attest(project_id, False)
        result = self._normalize(project_id, self._issues(self._run(project, ["show", self._id(bead_id)], False))[0], status["revision"])
        if not isinstance(includes or [], list) or not all(isinstance(item, str) for item in includes or []): raise BeadsError("includes must be a list of strings")
        result["includes"] = self._includes(project, project_id, result["id"], set(includes or []))
        return result

    @staticmethod
    def _filter_expression(filters: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for field, value in sorted(filters.items()):
            if field not in _FIELDS: raise BeadsError(f"unsupported_capability: unsupported Beads query field {field!r}")
            op, raw = (value.get("op"), value.get("value")) if isinstance(value, Mapping) else ("=", value)
            if op not in {"=", "!=", ">", ">=", "<", "<="}: raise BeadsError("filter op is invalid")
            if isinstance(raw, bool): encoded = str(raw).lower()
            elif isinstance(raw, (int, float)): encoded = str(raw)
            elif isinstance(raw, str) and raw and len(raw) <= 1000: encoded = json.dumps(raw) if any(c.isspace() for c in raw) else raw
            else: raise BeadsError(f"filter {field!r} has an invalid value")
            parts.append(f"{field}{op}{encoded}")
        return " AND ".join(parts)

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

    def query(self, *, project_ids: list[str] | None, view: str = "query", filters: Mapping[str, Any] | None = None, expression: str | None = None, order: Mapping[str, Any] | None = None, includes: list[str] | None = None, limit: int | None = None, cursor: str | None = None) -> dict[str, Any]:
        project_ids = sorted(self.config.projects) if project_ids is None else project_ids
        if not isinstance(project_ids, list) or not project_ids or len(project_ids) > 32 or len(set(project_ids)) != len(project_ids): raise BeadsError("project_ids must contain 1-32 unique projects")
        if filters is not None and not isinstance(filters, Mapping): raise BeadsError("filters must be an object")
        expression = self._string(expression, "expression", 4000) if expression is not None else None
        generated = self._filter_expression(filters or {})
        expression = f"({generated}) AND ({expression})" if generated and expression else generated or expression
        requested = set(includes or [])
        if not all(isinstance(item, str) for item in requested): raise BeadsError("includes must be strings")
        rows: list[dict[str, Any]] = []; coverage: dict[str, Any] = {}; revisions: dict[str, str] = {}
        for project_id in sorted(project_ids):
            try:
                project, status = self._attest(project_id, False); revisions[project_id] = status["revision"]
                if expression: self._run(project, ["query", expression, "--parse-only"], False)
                if view == "ready": command = ["ready", "--limit", str(_MAX_PAGE), "--explain"]
                elif view == "blocked": command = ["blocked"]
                elif view in {"open", "all", "recent", "overdue", "deferred", "unassigned", "stale_claims", "epic_progress", "changed_since"}:
                    command = ["list", "--flat", "--limit", str(_MAX_PAGE)]
                    command += {"open": ["--status", "open"], "all": ["--all"], "recent": ["--sort", "updated", "--reverse"], "overdue": ["--overdue"], "deferred": ["--deferred"], "unassigned": ["--no-assignee"], "epic_progress": ["--type", "epic"]}.get(view, [])
                elif view == "query":
                    if not expression: raise BeadsError("query view requires filters or expression")
                    command = ["query", expression, "--limit", str(_MAX_PAGE)]
                else: raise BeadsError(f"unsupported_capability: unknown Beads view {view!r}")
                if expression and view != "query": command = ["query", expression, "--limit", str(_MAX_PAGE)]
                if order:
                    if not isinstance(order, Mapping) or set(order) - {"field", "reverse"} or order.get("field") not in {"priority", "created", "updated", "closed", "status", "id", "title", "type", "assignee"}: raise BeadsError("order is unsupported")
                    command += ["--sort", str(order["field"])] + (["--reverse"] if order.get("reverse") else [])
                normalized = [self._normalize(project_id, row, status["revision"]) for row in self._issues(self._run(project, command, False))]
                for row in normalized:
                    if requested: row["includes"] = self._includes(project, project_id, row["id"], requested)
                rows += normalized; coverage[project_id] = {"state": "complete", "returned": len(normalized), "revision": status["revision"]}
            except BeadsError as exc: coverage[project_id] = {"state": "partial", "error": str(exc)}
        rows.sort(key=lambda row: (row["project_id"], row["id"])); key = hashlib.sha256(json.dumps({"principal": self.principal.name, "projects": sorted(project_ids), "view": view, "filters": filters or {}, "expression": expression, "order": order or {}, "includes": sorted(requested)}, sort_keys=True, separators=(",", ":")).encode()).hexdigest(); source_revision = hashlib.sha256(json.dumps(revisions, sort_keys=True).encode()).hexdigest(); page_rows, page = self._snapshot_page(key, source_revision, rows, self._limit(limit), cursor)
        return {"kind": "bead_query", "items": page_rows, "page": page, "coverage": coverage, "source_revisions": revisions, "warnings": ["partial_source" for item in coverage.values() if item["state"] == "partial"]}

    def graph(self, project_id: str, bead_id: str, *, direction: str = "down", edge_type: str | None = None, depth: int = 1, max_rows: int = 200, mermaid: bool = False) -> dict[str, Any]:
        project, _ = self._attest(project_id, False); root = self._id(bead_id); depth = self._limit(depth, 1, 20); max_rows = self._limit(max_rows, 200, 1000)
        if direction not in {"down", "up", "both"}: raise BeadsError("direction must be down, up, or both")
        queue, nodes, edges, cycles = [(root, 0)], {root}, [], []
        while queue:
            current, level = queue.pop(0)
            if level >= depth: continue
            commands = (["down", ["dep", "list", current]], ["up", ["dep", "list", current, "--reverse"]])
            for relation, command in commands:
                if direction not in {relation, "both"}: continue
                for row in self._issues(self._run(project, command, False)):
                    other = self._id(row["id"]); kind = str(row.get("dependency_type", row.get("type", "depends-on")))
                    if edge_type and edge_type != kind: continue
                    edges.append({"from": self.bead_ref(project_id, current), "to": self.bead_ref(project_id, other), "relation": relation, "type": kind})
                    if other == root: cycles.append([root, current, root])
                    if other not in nodes: nodes.add(other); queue.append((other, level + 1))
                    if len(nodes) > max_rows: raise BeadsError("response_bound: graph exceeds max_rows")
        result = {"ref": self.bead_ref(project_id, root), "nodes": [{"id": item, "ref": self.bead_ref(project_id, item)} for item in sorted(nodes)], "edges": edges, "cycles": cycles, "partial": False}
        if mermaid: result["mermaid"] = "graph TD\n" + "\n".join(f"  {edge['from'].rsplit('/', 1)[-1]} -->|{edge['type']}| {edge['to'].rsplit('/', 1)[-1]}" for edge in edges)
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
            flags = {"description": "--description", "design": "--design", "acceptance": "--acceptance", "type": "--type", "priority": "--priority", "assignee": "--assignee", "parent": "--parent", "due": "--due", "defer": "--defer", "external_ref": "--external-ref", "spec_id": "--spec-id"}
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
            if set(patch) - {"set", "labels", "metadata", "notes"} or len(command) == 2: raise BeadsError("update patch contains no supported change")
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
        elif operation == "memory.remember": command = ["remember", self._string(values.pop("key", None), "key", 256), self._string(values.pop("text", None), "text", 32000)]
        elif operation == "memory.forget": command = ["forget", self._string(values.pop("key", None), "key", 256)]
        else: raise BeadsError(f"unsupported_capability: Beads operation {operation!r} is not declared")
        if operation in {"unclaim", "close", "reopen"} and "reason" in values: command += ["--reason", self._string(values.pop("reason"), "reason", 32000)]
        if values: raise BeadsError(f"{operation} received unsupported parameters: {sorted(values)}")
        return target, command

    def change(self, project_id: str, operation: str, parameters: Mapping[str, Any], *, mode: str = "apply", preconditions: Mapping[str, Any] | None = None, preview_digest: str | None = None) -> dict[str, Any]:
        if mode not in {"preview", "apply"}: raise BeadsError("mode must be preview or apply")
        project, before_status = self._attest(project_id, mode == "apply"); target, command = self._compile(operation, parameters)
        if preconditions is not None:
            if not isinstance(preconditions, Mapping) or set(preconditions) - {"expected_task_revision", "expected_status", "expected_assignee", "expected_etag"}: raise BeadsError("Beads preconditions are not recognized")
            if preconditions.get("expected_task_revision") not in {None, before_status["revision"]}: raise BeadsError("precondition_failed: task revision no longer matches")
            if target and any(key in preconditions for key in {"expected_status", "expected_assignee", "expected_etag"}):
                before = self.get(project_id, target); fields = before["fields"]
                if "expected_status" in preconditions and fields.get("status") != preconditions["expected_status"]: raise BeadsError("precondition_failed: status no longer matches")
                if "expected_assignee" in preconditions and fields.get("assignee") != preconditions["expected_assignee"]: raise BeadsError("precondition_failed: assignee no longer matches")
                if "expected_etag" in preconditions and before["task_revision"] != preconditions["expected_etag"]: raise BeadsError("precondition_failed: etag no longer matches")
                if "expected_status" in preconditions: command += ["--if-status", str(preconditions["expected_status"])]
                if "expected_assignee" in preconditions:
                    expected_assignee = preconditions["expected_assignee"]
                    if expected_assignee is not None and not isinstance(expected_assignee, str):
                        raise BeadsError("expected_assignee must be a string or null")
                    command += ["--if-assignee", expected_assignee or ""]
        digest = hashlib.sha256(json.dumps({"project": project_id, "operation": operation, "command": command, "revision": before_status["revision"]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        preview = {"mode": "preview", "preview_digest": digest, "project_ref": self.project_ref(project_id), "target_ref": self.bead_ref(project_id, target) if target else None, "owner_route": "beads.cli", "owner_version": before_status.get("schema_version"), "command": command, "preconditions": dict(preconditions or {}), "atomicity": "owner_per_issue"}
        if mode == "preview": return preview
        if preview_digest is not None and preview_digest != digest: raise BeadsError("precondition_failed: preview digest or source revision is stale")
        before = self.get(project_id, target) if target else None; native = self._run(project, command, True); after_status = self.task_authority_status(project_id); after = self.get(project_id, target) if target else None
        return {**preview, "mode": "apply", "before": before, "after": after, "before_revision": before_status["revision"], "after_revision": after_status["revision"], "owner_result": native, "owner_history_ref": f"{self.bead_ref(project_id, target)}/history" if target else None, "atomicity": "owner_native" if operation in {"claim", "close", "reopen", "comment", "dependency.add", "dependency.remove", "relate", "unrelate", "reparent", "memory.remember", "memory.forget"} else "owner_per_issue"}
