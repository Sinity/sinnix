from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import replace
from difflib import unified_diff
from pathlib import Path
from typing import Any, Mapping

from .owner_execution import ExecutionProfile, OwnerExecution, OwnerRoute

from .capabilities import Capability, Principal
from .config import GatewayConfig, ProjectConfig, TaskAuthorityConfig
from .results import ProtocolError, ResultError, ResultService


class BeadsError(ProtocolError):
    """An owner-backed failure which remains typed at the V2 boundary."""

    def __init__(
        self,
        message: str,
        code: str = "invalid_request",
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, details=details)


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_MAX_PAGE = 200


class BeadsService:
    """Typed canonical owner adapter; response snapshots are not a task mirror."""

    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        results: ResultService | None = None,
    ):
        self.config, self.principal = config, principal
        self.results = results or ResultService(config, principal)
        self.execution = OwnerExecution(base_environment={})

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 8192, empty: bool = False) -> str:
        if (
            not isinstance(value, str)
            or len(value) > maximum
            or (not empty and not value)
        ):
            raise BeadsError(f"{name} must be a bounded string")
        return value

    def _id(self, value: Any, name: str = "id") -> str:
        value = self._string(value, name, 128)
        if not _ID_RE.fullmatch(value):
            raise BeadsError(f"{name} is malformed")
        return value

    @staticmethod
    def _limit(value: Any, default: int = 50, maximum: int | None = _MAX_PAGE) -> int:
        value = default if value is None else value
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 1
            or (maximum is not None and value > maximum)
        ):
            raise BeadsError(
                f"limit must be 1-{maximum}"
                if maximum is not None
                else "limit must be a positive integer"
            )
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

    def _authority(
        self, project_id: str, write: bool
    ) -> tuple[ProjectConfig, TaskAuthorityConfig]:
        project = self._project(project_id, write)
        if project.task_authority is None:
            raise BeadsError(
                f"project has no declared Beads task authority: {project_id}"
            )
        return project, project.task_authority

    def _run(
        self,
        project: ProjectConfig,
        args: list[str],
        write: bool,
        *,
        text: bool = False,
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        command = [
            self.config.beads_command,
            "--directory",
            str(project.path),
            "--json",
        ]
        if not write:
            command.append("--readonly")
        command += args
        profile = ExecutionProfile(
            route=OwnerRoute("beads"),
            stdin_bytes=json.dumps(payload).encode() if payload is not None else None,
            timeout_seconds=30,
            cwd=project.path,
            max_stdout_bytes=self.config.max_result_bytes,
            max_stderr_bytes=self.config.max_result_bytes,
            environment={
                "HOME": str(Path.home()),
                "LANG": os.environ.get("LANG", "C.UTF-8"),
                "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
                "BEADS_ACTOR": f"sinnix-gateway:{self.principal.name}",
            },
        )
        # Owner output size is not a client-envelope limit or a transaction
        # guard: writes may commit before emitting their response. Stream to
        # managed scratch; final results use artifacts or snapshot pagination.
        with tempfile.TemporaryFile() as output:
            result = self.execution.run(
                command, profile, stdout_chunk_callback=output.write
            )
            output.seek(0)
            if result.failure_class is None:
                if text:
                    return output.read().decode("utf-8", "replace")
                try:
                    return json.load(output)
                except json.JSONDecodeError as exc:
                    raise BeadsError(
                        "Beads did not return JSON", "owner_failed"
                    ) from exc
            result = replace(result, stdout=output.read(self.config.max_result_bytes))
        if result.failure_class == "command_timeout":
            raise BeadsError("Beads operation timed out", "deadline")
        if result.failure_class == "command_output_bound":
            raise BeadsError(
                "Beads response exceeded configured bound", "response_bound"
            )
        error = (
            (result.stdout + b"\n" + result.stderr).decode("utf-8", "replace").strip()
        )
        code = "owner_failed"
        try:
            problem = json.loads(result.stdout)
        except (ValueError, TypeError):
            problem = None
        if isinstance(problem, dict):
            nested = problem.get("error")
            owner_code = problem.get("code") or (
                nested.get("code") if isinstance(nested, dict) else None
            )
            code = {
                "precondition_failed": "precondition_failed",
                "not_found": "not_found",
                "invalid_argument": "invalid_request",
                "invalid_request": "invalid_request",
                "source_changed": "source_changed",
                "unsupported_capability": "unsupported_capability",
            }.get(owner_code, code)
            error = problem.get("detail") or problem.get("message") or error
        elif result.exit_status == 13 or "--if-" in error:
            code = "precondition_failed"
        elif "source_changed" in error:
            code = "source_changed"
        raise BeadsError(
            error or "Beads operation failed",
            code,
            details={"owner_error": problem} if isinstance(problem, dict) else None,
        )

    def task_authority_status(self, project_id: str) -> dict[str, Any]:
        project, authority = self._authority(project_id, False)
        where, status, state = (
            self._run(project, ["where"], False),
            self._run(project, ["status"], False),
            self._run(
                project,
                ["owner", "read"],
                False,
                payload={"aggregate": {}, "limit": 1},
            ),
        )
        if (
            not isinstance(where, Mapping)
            or not isinstance(where.get("path"), str)
            or not isinstance(where.get("database_path"), str)
        ):
            raise BeadsError("Beads where did not return path and database_path")
        if (
            Path(where["path"]).resolve() != authority.workspace
            or Path(where["database_path"]).resolve() != authority.database
        ):
            raise BeadsError(
                "task_authority_mismatch: configured Beads workspace or database does not match bd where"
            )
        if not isinstance(status, Mapping):
            raise BeadsError("Beads status did not return an object")
        if not isinstance(state, dict) or not isinstance(state.get("revision"), str):
            raise BeadsError("Beads did not return its working-state revision")
        revision = state["revision"]
        return {
            "project_id": project_id,
            "ref": self.project_ref(project_id),
            "owner": authority.owner,
            "publication_policy": authority.publication_policy,
            "project_uuid": authority.project_uuid,
            "schema_version": where.get("schema_version"),
            "revision": revision,
            "summary": status.get("summary"),
            "attested": True,
        }

    def _attest(
        self, project_id: str, write: bool
    ) -> tuple[ProjectConfig, dict[str, Any]]:
        project, _ = self._authority(project_id, write)
        return project, self.task_authority_status(project_id)

    @staticmethod
    def _issues(value: Any) -> list[dict[str, Any]]:
        rows = (
            value
            if isinstance(value, list)
            else value.get("issues", value.get("items"))
            if isinstance(value, Mapping)
            else None
        )
        if (
            rows is None
            and isinstance(value, Mapping)
            and isinstance(value.get("issue"), Mapping)
        ):
            rows = [value["issue"]]
        if (
            rows is None
            and isinstance(value, Mapping)
            and isinstance(value.get("id"), str)
        ):
            rows = [value]
        if not isinstance(rows, list) or any(
            not isinstance(row, Mapping) or not isinstance(row.get("id"), str)
            for row in rows
        ):
            raise BeadsError("Beads response omitted normalized issue records")
        return [dict(row) for row in rows]

    def _normalize(
        self, project_id: str, row: Mapping[str, Any], revision: str
    ) -> dict[str, Any]:
        bead_id = self._id(row["id"])
        parent = row.get("parent_id", row.get("parent"))
        if isinstance(parent, Mapping):
            parent = parent.get("id")
        native_keys = {
            "id",
            "title",
            "description",
            "design",
            "acceptance_criteria",
            "status",
            "priority",
            "issue_type",
            "assignee",
            "owner",
            "created_at",
            "updated_at",
            "started_at",
            "closed_at",
            "close_reason",
            "labels",
            "metadata",
            "notes",
            "parent",
            "parent_id",
            "dependencies",
            "external_ref",
            "spec_id",
            "due_at",
            "defer_until",
            "estimate",
            "ephemeral",
        }
        links = {
            key: f"{self.bead_ref(project_id, bead_id)}/{key}"
            for key in (
                "comments",
                "history",
                "events",
                "dependencies",
                "dependents",
                "children",
                "refs",
                "jobs",
                "receipts",
            )
        }
        links["project"] = self.project_ref(project_id)
        parent_ref = (
            self.bead_ref(project_id, parent)
            if isinstance(parent, str) and _ID_RE.fullmatch(parent)
            else None
        )
        if parent_ref is not None:
            links["parent"] = parent_ref
        # Owner output changes shape with requested projections.  Bind the
        # canonical target ref to the owner revision instead of hashing a view.
        etag = hashlib.sha256(
            json.dumps(
                {"ref": self.bead_ref(project_id, bead_id), "revision": revision},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return {
            "ref": self.bead_ref(project_id, bead_id),
            "id": bead_id,
            "project_id": project_id,
            "task_revision": revision,
            "etag": etag,
            "fields": {
                key: row[key]
                for key in sorted(
                    native_keys - {"id", "parent", "parent_id", "dependencies"}
                )
                if key in row
            },
            "parent_ref": parent_ref,
            "links": links,
            "native": {
                key: value
                for key, value in row.items()
                if key not in native_keys and key != "includes"
            },
        }

    def get(
        self,
        project_id: str,
        bead_id: str,
        *,
        includes: list[str] | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        project, _ = self._attest(project_id, False)
        owner = self._run(
            project,
            ["owner", "read"],
            False,
            payload={
                "roots": [self._id(bead_id)],
                "depth": 0,
                "limit": 1,
                "include": includes or [],
                **({"at": as_of} if as_of else {}),
            },
        )
        rows = self._issues(owner)
        if not rows:
            raise BeadsError("Bead not found", "not_found")
        result = self._normalize(project_id, rows[0], owner["revision"])
        return {
            **result,
            "includes": rows[0].get("includes", {}),
            "as_of": as_of,
            "temporal": owner.get("temporal"),
        }

    def _snapshot_page(
        self,
        key: str,
        source_revision: str,
        rows: list[dict[str, Any]],
        limit: int,
        cursor: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        legacy_offset = None
        if cursor is not None and re.fullmatch(r"[0-9a-f]{64}\.[0-9]+", cursor):
            token, offset = cursor.split(".")
            try:
                legacy = json.loads(
                    (
                        self.config.state_dir / "beads-snapshots" / f"{token}.json"
                    ).read_text()
                )
                if legacy["key"] != key or time.time() >= legacy["expires_at"]:
                    raise ValueError("expired or mismatched cursor")
                rows = legacy["rows"]
                legacy_offset = int(offset)
                if not isinstance(rows, list) or not 0 <= legacy_offset < len(rows):
                    raise ValueError("invalid snapshot offset")
                source_revision = legacy["source_revision"]
                metadata = legacy.get("metadata", {})
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise BeadsError(
                    "Beads snapshot cursor is unavailable", "stale_cursor"
                ) from exc
            cursor = None
        try:
            if cursor is not None:
                page = self.results.continue_snapshot(
                    cursor, query_sha256=key, page_size=limit
                )
            else:
                writer = self.results.start_snapshot(
                    query_sha256=key,
                    source_revision=source_revision,
                    page_size=limit,
                    metadata=metadata,
                )
                try:
                    for row in rows:
                        writer.append(row)
                    page = self.results.finish_snapshot(writer)
                    if legacy_offset is not None:
                        cursor = self.results._cursor(
                            {
                                "snapshot_id": writer.snapshot_id,
                                "principal": self.principal.name,
                                "query_sha256": key,
                                "offset": legacy_offset,
                                "page_size": limit,
                                "expires_at": page["expires_at"],
                            }
                        )
                        page = self.results.continue_snapshot(
                            cursor, query_sha256=key, page_size=limit
                        )
                except Exception:
                    writer.abort()
                    raise
        except ResultError as exc:
            raise BeadsError(str(exc), exc.failure_class) from exc
        return page.pop("rows"), {
            "kind": "snapshot",
            "total": page.pop("row_count"),
            **page,
        }

    def query(
        self,
        *,
        project_ids: list[str] | None,
        view: str = "query",
        filters: Mapping[str, Any] | None = None,
        expression: str | None = None,
        native_filters: Mapping[str, Any] | None = None,
        order: Mapping[str, Any] | None = None,
        includes: list[str] | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        at: str | None = None,
        projection: str = "summary",
        aggregate: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        projects = sorted(self.config.projects) if project_ids is None else project_ids
        if (
            not isinstance(projects, list)
            or not 1 <= len(projects) <= 32
            or len(set(projects)) != len(projects)
        ):
            raise BeadsError("project_ids must contain 1-32 unique projects")
        for project_id in projects:
            self._project(project_id, False)
        page_limit = self._limit(limit, maximum=None)
        request = {
            "principal": self.principal.name,
            "projects": sorted(projects),
            "view": view,
            "filters": filters or {},
            "expression": expression,
            "native": native_filters or {},
            "order": order or {},
            "includes": sorted(includes or []),
            "at": at,
            "projection": projection,
            "aggregate": aggregate,
        }
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        if cursor:
            rows, page = self._snapshot_page(key, "", [], page_limit, cursor)
            metadata = page.pop("metadata")
            return {"kind": "bead_query", "items": rows, "page": page, **metadata}
        rows, coverage, revisions, temporals = [], {}, {}, {}
        for project_id in sorted(projects):
            try:
                project, _ = self._attest(project_id, False)
                owner = self._run(
                    project,
                    ["owner", "read"],
                    False,
                    payload={
                        "view": view,
                        "filters": filters or {},
                        "native_filters": native_filters or {},
                        "order": order or {},
                        "include": includes or [],
                        "limit": 0,
                        "projection": projection,
                        **({"expression": expression} if expression else {}),
                        **({"at": at} if at else {}),
                        **({"aggregate": aggregate} if aggregate is not None else {}),
                    },
                )
                revision = owner["revision"]
                temporal = owner.get("temporal")
                native_rows = owner["items"]
                details = {
                    "truncated": owner["has_more"],
                    "total": owner["total"],
                    "total_exact": owner["total_exact"],
                    "owner_coverage": owner.get("closure"),
                }
                normalized = (
                    [
                        {
                            "project_id": project_id,
                            "fields": row,
                            "task_revision": revision,
                        }
                        for row in native_rows
                    ]
                    if aggregate is not None
                    else [
                        {
                            **self._normalize(project_id, row, revision),
                            "includes": row.get("includes", {}),
                        }
                        for row in native_rows
                    ]
                )
                rows.extend(normalized)
                revisions[project_id] = revision
                temporals[project_id] = temporal
                coverage[project_id] = {
                    "state": "partial" if details["truncated"] else "complete",
                    "returned": len(normalized),
                    "revision": revision,
                    **details,
                }
            except BeadsError as exc:
                if exc.code == "invalid_request" and project_id in self.config.projects:
                    raise
                coverage[project_id] = {
                    "state": "partial",
                    "error": str(exc),
                    "code": exc.code,
                    "total_exact": False,
                }
        if aggregate is None:
            field = (order or {}).get(
                "field", "updated" if view == "recent" else "priority"
            )
            column = {
                "type": "issue_type",
                "created": "created_at",
                "updated": "updated_at",
                "closed": "closed_at",
            }.get(field, field)
            rows.sort(key=lambda row: (row["project_id"], row["id"]))
            reverse = (field in {"created", "updated", "closed"}) != bool(
                (order or {}).get("reverse", False)
            )

            def sort_value(row: dict[str, Any]) -> tuple[bool, Any]:
                value = row["id"] if field == "id" else row["fields"].get(column)
                return value is not None, value if value is not None else ""

            rows.sort(key=sort_value, reverse=reverse)
        metadata = {
            "coverage": coverage,
            "source_revisions": revisions,
            "temporal": temporals,
            "totals": {
                "returned": len(rows),
                "matched": sum(item.get("total", 0) for item in coverage.values()),
                "projects": len(projects),
                "healthy_projects": sum(
                    item["state"] == "complete" for item in coverage.values()
                ),
                "partial_projects": sum(
                    item["state"] == "partial" for item in coverage.values()
                ),
                "exact": all(
                    item.get("total_exact", False) for item in coverage.values()
                ),
            },
            "native_parse": {},
            "owner_capabilities": {
                "native_expression_parse": True,
                "native_owner_read": True,
                "native_offset_paging": False,
                "exact_query_total": True,
                "server_projection": True,
            },
            "warnings": (
                ["partial_source"]
                if any(item["state"] == "partial" for item in coverage.values())
                else []
            ),
        }
        revision_key = hashlib.sha256(
            json.dumps(revisions, sort_keys=True).encode()
        ).hexdigest()
        page_rows, page = self._snapshot_page(
            key, revision_key, rows, page_limit, None, metadata
        )
        page.pop("metadata")
        return {"kind": "bead_query", "items": page_rows, "page": page, **metadata}

    def campaign_closure(
        self,
        project_id: str,
        roots: list[str],
        *,
        at: str | None = None,
        relation: str | None = "blocks",
        direction: str = "prerequisites",
        max_nodes: int = 500,
        max_depth: int = 50,
    ) -> dict[str, Any]:
        project, _ = self._attest(project_id, False)
        owner = self._run(
            project,
            ["owner", "read"],
            False,
            payload={
                "roots": roots,
                "direction": {
                    "prerequisites": "dependencies",
                    "dependents": "dependents",
                    "both": "both",
                }[direction],
                "relations": [relation] if relation else [],
                "depth": max_depth,
                "limit": max_nodes,
                "provenance": True,
                **({"at": at} if at else {}),
            },
        )
        return {"project_id": project_id, "roots": roots, "owner_product": owner}

    def graph(
        self,
        project_id: str,
        bead_id: str,
        *,
        direction: str = "down",
        edge_type: str | None = None,
        status: str | None = None,
        depth: int = 1,
        max_rows: int = 200,
        mermaid: bool = False,
    ) -> dict[str, Any]:
        # Native tree and closure have distinct owner projections; retain both.
        project, _ = self._attest(project_id, False)
        command = [
            "dep",
            "tree",
            self._id(bead_id),
            "--direction",
            direction,
            "--max-depth",
            str(depth),
            "--max-rows",
            str(max_rows),
        ]
        if status:
            command.extend(["--status", status])
        result = {"native_tree": self._run(project, command, False)}
        if mermaid:
            result["mermaid"] = self._run(
                project, command + ["--format", "mermaid"], False, text=True
            )
        result["closure"] = self.campaign_closure(
            project_id,
            [bead_id],
            relation=edge_type,
            direction={"down": "prerequisites", "up": "dependents", "both": "both"}[
                direction
            ],
            max_nodes=max_rows,
            max_depth=depth,
        )["owner_product"]
        return result

    def memories(
        self, project_id: str, *, key: str | None = None, query: str | None = None
    ) -> dict[str, Any]:
        project, _ = self._attest(project_id, False)
        if key and query:
            raise BeadsError("memory reads accept key or query, not both")
        command = (
            ["recall", self._string(key, "key", 256)]
            if key
            else (
                ["memories", self._string(query, "query", 1000)]
                if query
                else ["memories"]
            )
        )
        return {
            "kind": "bead_memory",
            "project_id": project_id,
            "result": self._run(project, command, False),
        }

    def read(self, project_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        project, _ = self._attest(project_id, False)
        value = self._run(project, ["owner", "read"], False, payload=payload)
        if not isinstance(value, dict):
            raise BeadsError("Beads owner returned no object", "owner_failed")
        return value

    def native(
        self,
        project_id: str,
        operation: str,
        payload: Mapping[str, Any],
        *,
        write: bool,
    ) -> dict[str, Any]:
        project, _ = self._attest(project_id, write)
        value = self._run(project, ["owner", "call", operation], write, payload=payload)
        if not isinstance(value, dict):
            raise BeadsError("Beads owner returned no object", "owner_failed")
        return value

    def operate(
        self,
        project_id: str,
        operation: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        project, before = self._attest(project_id, True)
        parameters = dict(parameters or {})
        if operation == "snapshot.publish":
            if parameters:
                raise BeadsError("snapshot.publish accepts no parameters")
            directory = self.config.state_dir / "beads-publications" / project_id
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            destination = directory / "issues.jsonl"
            before_text = destination.read_text() if destination.exists() else ""
            owner_result = self._run(
                project, ["export", "-o", str(destination)], True, text=True
            )
            after_text = destination.read_text() if destination.exists() else ""
            diff = "".join(
                unified_diff(
                    before_text.splitlines(keepends=True),
                    after_text.splitlines(keepends=True),
                    fromfile="previous",
                    tofile="published",
                    n=3,
                )
            )
            if len(diff.encode()) > self.config.max_result_bytes:
                diff = diff[: self.config.max_result_bytes] + "\n[diff truncated]\n"
            publication = {
                "destination": str(destination),
                "before_sha256": hashlib.sha256(before_text.encode()).hexdigest(),
                "after_sha256": hashlib.sha256(after_text.encode()).hexdigest(),
                "changed": before_text != after_text,
                "diff": diff,
            }
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
            owner_result, publication = (
                self._run(project, ["backup", "create"], True),
                None,
            )
        elif operation == "backup.list":
            if parameters:
                raise BeadsError("backup.list accepts no parameters")
            owner_result, publication = (
                self._run(project, ["backup", "list"], False),
                None,
            )
        elif operation == "backup.restore":
            backup_id = self._string(
                parameters.pop("backup_id", None), "backup_id", 256
            )
            if parameters:
                raise BeadsError("backup.restore accepts only backup_id")
            owner_result, publication = (
                self._run(project, ["backup", "restore", backup_id], True),
                None,
            )
        else:
            raise BeadsError(
                f"unsupported_capability: Beads maintenance operation {operation!r} is not declared"
            )
        after = self.task_authority_status(project_id)
        return {
            "project_ref": self.project_ref(project_id),
            "owner_route": "beads.maintenance",
            "operation": operation,
            "before_revision": before["revision"],
            "after_revision": after["revision"],
            "owner_result": owner_result,
            "publication": publication,
            "atomicity": "per_step_commits",
            "git_bookkeeping": "none",
        }
