from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig, ProjectConfig, TaskAuthorityConfig
from .execution import ExecutionProfile, OwnerExecution, OwnerRoute


class BeadsError(ValueError):
    pass


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class BeadsService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        self.execution = OwnerExecution(base_environment={})

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 8_192) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise BeadsError(f"{name} must be a non-empty string")
        return value

    def _id(self, value: Any, name: str = "id") -> str:
        value = self._string(value, name, 128)
        if not _ID_RE.fullmatch(value):
            raise BeadsError(f"{name} is malformed")
        return value

    def _project(self, project_id: str, *, write: bool) -> ProjectConfig:
        self.principal.require(Capability.TASK_WRITE if write else Capability.TASK_READ)
        project_id = self._string(project_id, "project_id", 128)
        try:
            project = self.config.projects[project_id]
        except KeyError as exc:
            raise BeadsError(f"unknown project: {project_id}") from exc
        if self.principal.name == "observer" and not project.observer_read:
            raise BeadsError(f"project is unavailable to {self.principal.name}")
        if not project.path.is_dir():
            raise BeadsError(f"project checkout is unavailable: {project_id}")
        return project

    def _authority(
        self, project_id: str, *, write: bool
    ) -> tuple[ProjectConfig, TaskAuthorityConfig]:
        project = self._project(project_id, write=write)
        authority = project.task_authority
        if authority is None:
            raise BeadsError(f"project has no declared Beads task authority: {project_id}")
        return project, authority

    @staticmethod
    def _where_payload(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise BeadsError("Beads where did not return an object")
        workspace = value.get("path")
        database = value.get("database_path")
        if not isinstance(workspace, str) or not isinstance(database, str):
            raise BeadsError("Beads where did not return path and database_path")
        return value

    def task_authority_status(self, project_id: str) -> dict[str, Any]:
        project, authority = self._authority(project_id, write=False)
        actual = self._where_payload(self._run(project, ["where"], write=False))
        actual_workspace = Path(actual["path"]).resolve()
        actual_database = Path(actual["database_path"]).resolve()
        if actual_workspace != authority.workspace or actual_database != authority.database:
            raise BeadsError(
                "task_authority_mismatch: configured Beads workspace or database "
                "does not match bd where"
            )
        status = self._run(project, ["status"], write=False)
        if not isinstance(status, dict):
            raise BeadsError("Beads status did not return an object")
        task_revision = hashlib.sha256(
            json.dumps(status, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "project_id": project.project_id,
            "owner": authority.owner,
            "publication_policy": authority.publication_policy,
            "project_uuid": authority.project_uuid,
            "schema_version": actual.get("schema_version"),
            "revision": task_revision,
            "summary": status.get("summary"),
            "attested": True,
        }

    def _attest_task_authority(self, project_id: str, *, write: bool) -> ProjectConfig:
        project, _ = self._authority(project_id, write=write)
        self.task_authority_status(project_id)
        return project

    def _run(self, project: ProjectConfig, arguments: list[str], *, write: bool) -> Any:
        command = [
            self.config.beads_command,
            "--directory",
            str(project.path),
            "--json",
        ]
        if not write:
            command.append("--readonly")
        command.extend(arguments)
        environment = {
            "HOME": str(Path.home()),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
            "BEADS_ACTOR": f"sinnix-gateway:{self.principal.name}",
        }
        result = self.execution.run(
            command,
            ExecutionProfile(
                route=OwnerRoute("beads"),
                timeout_seconds=30,
                max_stdout_bytes=self.config.max_result_bytes,
                max_stderr_bytes=self.config.max_result_bytes,
                cwd=project.path,
                environment=environment,
            ),
        )
        if result.failure_class == "command_timeout":
            raise BeadsError("Beads operation timed out")
        if result.failure_class == "command_output_bound":
            raise BeadsError("Beads response exceeded response bound")
        if result.failure_class is not None:
            error = (result.stdout + b"\n" + result.stderr).decode(
                "utf-8", errors="replace"
            ).strip()
            raise BeadsError(error or "Beads operation failed")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise BeadsError("Beads did not return JSON") from exc

    @staticmethod
    def _arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
        if arguments is None:
            return {}
        if not isinstance(arguments, dict):
            raise BeadsError("arguments must be an object")
        return arguments

    def read(
        self, project_id: str, operation: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        project = self._attest_task_authority(project_id, write=False)
        arguments = self._arguments(arguments)
        if operation == "list":
            allowed = {"status", "assignee", "label", "limit", "include_closed", "ready"}
            if set(arguments) - allowed:
                raise BeadsError("list received unsupported arguments")
            command = ["list", "--flat"]
            if arguments.get("include_closed") is True:
                command.append("--all")
            elif "include_closed" in arguments and not isinstance(arguments["include_closed"], bool):
                raise BeadsError("include_closed must be boolean")
            if arguments.get("ready") is True:
                command.append("--ready")
            elif "ready" in arguments and not isinstance(arguments["ready"], bool):
                raise BeadsError("ready must be boolean")
            for key, flag in (("status", "--status"), ("assignee", "--assignee"), ("label", "--label")):
                if key in arguments:
                    command.extend([flag, self._string(arguments[key], key, 256)])
            limit = arguments.get("limit", 100)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1_000:
                raise BeadsError("limit must be 1-1000")
            command.extend(["--limit", str(limit)])
        elif operation == "ready":
            if set(arguments) - {"limit"}:
                raise BeadsError("ready accepts only limit")
            limit = arguments.get("limit", 100)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1_000:
                raise BeadsError("limit must be 1-1000")
            command = ["ready", "--limit", str(limit)]
        elif operation in {"show", "comments", "history", "dependencies"}:
            if set(arguments) != {"id"}:
                raise BeadsError(f"{operation} requires only id")
            issue_id = self._id(arguments["id"])
            command = {
                "show": ["show", issue_id],
                "comments": ["comments", issue_id],
                "history": ["history", issue_id],
                "dependencies": ["dep", "list", issue_id],
            }[operation]
        elif operation == "blocked":
            if arguments:
                raise BeadsError("blocked accepts no arguments")
            command = ["blocked"]
        elif operation == "search":
            if set(arguments) - {"query", "limit"} or "query" not in arguments:
                raise BeadsError("search requires query and optional limit")
            query = self._string(arguments["query"], "query", 1_000)
            limit = arguments.get("limit", 100)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1_000:
                raise BeadsError("limit must be 1-1000")
            command = ["search", query, "--limit", str(limit)]
        else:
            raise BeadsError(
                "unknown Beads read operation; available: ['blocked', 'comments', "
                "'dependencies', 'history', 'list', 'ready', 'search', 'show']"
            )
        return {
            "project_id": project.project_id,
            "operation": operation,
            "result": self._run(project, command, write=False),
        }

    def write(self, project_id: str, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        project = self._attest_task_authority(project_id, write=True)
        arguments = self._arguments(arguments)
        if operation == "create":
            allowed = {"title", "description", "type", "priority", "labels", "parent", "dependencies", "append_notes"}
            if set(arguments) - allowed or "title" not in arguments:
                raise BeadsError("create requires title and supported optional fields")
            command = ["create", self._string(arguments["title"], "title", 512)]
            for key, flag, maximum in (("description", "--description", 32_000), ("type", "--type", 32), ("priority", "--priority", 8), ("parent", "--parent", 128), ("append_notes", "--append-notes", 32_000)):
                if key in arguments:
                    value = self._string(arguments[key], key, maximum)
                    if key == "parent":
                        value = self._id(value, "parent")
                    command.extend([flag, value])
            for key, flag in (("labels", "--labels"), ("dependencies", "--deps")):
                if key in arguments:
                    values = arguments[key]
                    if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value or len(value) > 256 for value in values):
                        raise BeadsError(f"{key} must be a non-empty list of bounded strings")
                    command.extend([flag, ",".join(values)])
        elif operation == "update":
            allowed = {"id", "title", "description", "status", "priority", "assignee", "add_labels", "remove_labels", "append_notes"}
            if set(arguments) - allowed or "id" not in arguments or len(arguments) == 1:
                raise BeadsError("update requires id and at least one supported field")
            command = ["update", self._id(arguments["id"])]
            for key, flag, maximum in (("title", "--title", 512), ("description", "--description", 32_000), ("status", "--status", 32), ("priority", "--priority", 8), ("assignee", "--assignee", 256), ("append_notes", "--append-notes", 32_000)):
                if key in arguments:
                    command.extend([flag, self._string(arguments[key], key, maximum)])
            for key, flag in (("add_labels", "--add-label"), ("remove_labels", "--remove-label")):
                if key in arguments:
                    values = arguments[key]
                    if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value or len(value) > 256 for value in values):
                        raise BeadsError(f"{key} must be a non-empty list of bounded strings")
                    for value in values:
                        command.extend([flag, value])
        elif operation == "claim":
            if set(arguments) != {"id"}:
                raise BeadsError("claim requires only id")
            command = ["update", self._id(arguments["id"]), "--claim"]
        elif operation in {"unclaim", "close", "reopen"}:
            allowed = {"id", "reason", "if_assignee"}
            if set(arguments) - allowed or "id" not in arguments:
                raise BeadsError(f"{operation} requires id and optional reason")
            issue_id = self._id(arguments["id"])
            command = [operation, issue_id]
            if "reason" in arguments:
                command.extend(["--reason", self._string(arguments["reason"], "reason", 32_000)])
            if "if_assignee" in arguments:
                if operation != "unclaim":
                    raise BeadsError("if_assignee is supported only by unclaim")
                command.extend(["--if-assignee", self._string(arguments["if_assignee"], "if_assignee", 256)])
        elif operation == "comment":
            if set(arguments) != {"id", "text"}:
                raise BeadsError("comment requires only id and text")
            command = [
                "comment",
                self._id(arguments["id"]),
                self._string(arguments["text"], "text", 32_000),
            ]
        elif operation == "dependency_add":
            if set(arguments) != {"issue_id", "depends_on", "type"}:
                raise BeadsError("dependency_add requires issue_id, depends_on, and type")
            command = [
                "dep",
                "add",
                self._id(arguments["issue_id"], "issue_id"),
                self._id(arguments["depends_on"], "depends_on"),
                "--type",
                self._string(arguments["type"], "type", 32),
            ]
        elif operation == "relate":
            if set(arguments) != {"left_id", "right_id"}:
                raise BeadsError("relate requires left_id and right_id")
            command = [
                "dep",
                "relate",
                self._id(arguments["left_id"], "left_id"),
                self._id(arguments["right_id"], "right_id"),
            ]
        else:
            raise BeadsError(
                "unknown Beads write operation; available: ['claim', 'close', 'comment', "
                "'create', 'dependency_add', 'relate', 'reopen', 'unclaim', 'update']"
            )
        return {
            "project_id": project.project_id,
            "operation": operation,
            "result": self._run(project, command, write=True),
        }
