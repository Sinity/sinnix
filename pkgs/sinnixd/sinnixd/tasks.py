from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from sinnix_mcp import ErrorCode
from sinnix_mcp.execution import ExecutionProfile, ExecutionResult, OwnerExecution, OwnerRoute

from .projects import ProjectAdapter, ProjectCatalog


MAX_TASK_OUTPUT_BYTES = 200_000
MAX_TASK_STDERR_BYTES = 8_192
TASK_TIMEOUT_SECONDS = 30
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_READ_PRINCIPALS = frozenset({"observer", "agent-control", "operator"})
_WRITE_PRINCIPALS = frozenset({"agent-control", "operator"})
_MUTATIONS = frozenset(
    {
        "task.claim",
        "task.note",
        "task.relate",
        "task.complete",
        "task.release",
        "task.reconcile",
    }
)


class TaskError(ValueError):
    """A task request failed with a protocol-safe error classification."""

    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        super().__init__(message)


class TaskCommandBoundary(Protocol):
    """Injectable process boundary for the current task backend."""

    def run(self, *, argv: tuple[str, ...], cwd: Path) -> ExecutionResult: ...


@dataclass(frozen=True)
class BeadsCommandBoundary:
    """Bounded fixed-argv execution of the current Beads backend."""

    execution: OwnerExecution = field(default_factory=OwnerExecution)
    executable: str = "bd"

    def run(self, *, argv: tuple[str, ...], cwd: Path) -> ExecutionResult:
        return self.execution.run(
            (self.executable, *argv),
            ExecutionProfile(
                route=OwnerRoute("task-backend"),
                timeout_seconds=TASK_TIMEOUT_SECONDS,
                max_stdout_bytes=MAX_TASK_OUTPUT_BYTES,
                max_stderr_bytes=MAX_TASK_STDERR_BYTES,
                max_combined_output_bytes=MAX_TASK_OUTPUT_BYTES + MAX_TASK_STDERR_BYTES,
                cwd=cwd,
            ),
        )


@dataclass
class TaskService:
    """Backend-neutral AgentCTL task operations over the current Beads backend."""

    projects: ProjectCatalog
    boundary: TaskCommandBoundary = field(default_factory=BeadsCommandBoundary)
    _locks_guard: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _project_locks: dict[str, threading.Lock] = field(default_factory=dict, init=False, repr=False)

    def execute(
        self,
        *,
        operation: str,
        arguments: dict[str, Any] | Any,
        principal: str,
    ) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "task arguments must be an object")
        write = operation in _MUTATIONS
        self._authorize(principal, write=write)
        project = self._project(arguments)
        if write:
            with self._lock_for(project.project_id):
                return self._execute(project, operation, arguments)
        return self._execute(project, operation, arguments)

    def _execute(
        self,
        project: ProjectAdapter,
        operation: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if operation == "task.list":
            command = self._list_command(arguments)
            result = self._run(project, command, readonly=True)
        elif operation == "task.get":
            self._require_exact(arguments, {"project_id", "task_id"}, operation)
            result = self._run(project, ("show", self._task_id(arguments["task_id"])), readonly=True)
        elif operation == "task.claim":
            self._require_exact(arguments, {"project_id", "task_id"}, operation)
            result = self._run(project, ("update", self._task_id(arguments["task_id"]), "--claim"), readonly=False)
        elif operation == "task.note":
            self._require_exact(arguments, {"project_id", "task_id", "text"}, operation)
            result = self._run(
                project,
                ("note", self._task_id(arguments["task_id"]), self._string(arguments["text"], "text", 32_000)),
                readonly=False,
            )
        elif operation == "task.relate":
            self._require_exact(arguments, {"project_id", "task_id", "related_task_id"}, operation)
            result = self._run(
                project,
                (
                    "link",
                    self._task_id(arguments["task_id"]),
                    self._task_id(arguments["related_task_id"], "related_task_id"),
                    "--type",
                    "related",
                ),
                readonly=False,
            )
        elif operation == "task.complete":
            self._require_allowed(arguments, {"project_id", "task_id", "reason"}, {"project_id", "task_id"}, operation)
            command = ["close", self._task_id(arguments["task_id"])]
            if "reason" in arguments:
                command.extend(("--reason", self._string(arguments["reason"], "reason", 32_000)))
            result = self._run(project, tuple(command), readonly=False)
        elif operation == "task.release":
            self._require_allowed(arguments, {"project_id", "task_id", "reason", "if_assignee"}, {"project_id", "task_id"}, operation)
            command = ["unclaim", self._task_id(arguments["task_id"])]
            if "reason" in arguments:
                command.extend(("--reason", self._string(arguments["reason"], "reason", 32_000)))
            if "if_assignee" in arguments:
                command.extend(("--if-assignee", self._string(arguments["if_assignee"], "if_assignee", 256)))
            result = self._run(project, tuple(command), readonly=False)
        elif operation == "task.reconcile":
            self._require_exact(arguments, {"project_id"}, operation)
            result = self._run(project, ("sync", "--no-adopt"), readonly=False)
        elif operation == "task.snapshot":
            self._require_exact(arguments, {"project_id"}, operation)
            result = self._run(project, ("export",), readonly=True, json_lines=True)
        else:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, f"unsupported task operation: {operation}")
        return {"project_id": project.project_id, "operation": operation, "result": result}

    def _run(
        self,
        project: ProjectAdapter,
        command: tuple[str, ...],
        *,
        readonly: bool,
        json_lines: bool = False,
    ) -> Any:
        argv = ("--directory", str(project.root), "--json", *( ("--readonly",) if readonly else () ), *command)
        result = self.boundary.run(argv=argv, cwd=project.root)
        if result.timed_out or result.failure_class == "command_timeout":
            raise TaskError(ErrorCode.OWNER_UNAVAILABLE, "task backend timed out")
        if (
            result.output_exceeded
            or result.failure_class == "command_output_bound"
            or len(result.stdout) > MAX_TASK_OUTPUT_BYTES
            or len(result.stderr) > MAX_TASK_STDERR_BYTES
        ):
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task backend response exceeded the output bound")
        if result.failure_class is not None:
            code = ErrorCode.OWNER_UNAVAILABLE if result.failure_class.startswith("command_unavailable") else ErrorCode.OPERATION_FAILED
            raise TaskError(code, "task backend command failed")
        if result.exit_status != 0:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task backend command failed")
        try:
            if json_lines:
                records = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines() if line]
                if not all(isinstance(record, dict) for record in records):
                    raise ValueError("task snapshot records must be objects")
                return records
            return json.loads(result.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise TaskError(ErrorCode.RESULT_INVALID, "task backend returned invalid JSON") from error

    def _list_command(self, arguments: dict[str, Any]) -> tuple[str, ...]:
        self._require_allowed(
            arguments,
            {"project_id", "status", "assignee", "label", "limit", "include_closed", "ready"},
            {"project_id"},
            "task.list",
        )
        command = ["list", "--flat"]
        for name, flag in (("include_closed", "--all"), ("ready", "--ready")):
            if name in arguments:
                if not isinstance(arguments[name], bool):
                    raise TaskError(ErrorCode.INVALID_ARGUMENT, f"{name} must be boolean")
                if arguments[name]:
                    command.append(flag)
        for name, flag in (("status", "--status"), ("assignee", "--assignee"), ("label", "--label")):
            if name in arguments:
                command.extend((flag, self._string(arguments[name], name, 256)))
        limit = arguments.get("limit", 100)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1_000:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "limit must be an integer from 1 through 1000")
        command.extend(("--limit", str(limit)))
        return tuple(command)

    def _project(self, arguments: dict[str, Any]) -> ProjectAdapter:
        project_id = self._string(arguments.get("project_id"), "project_id", 128)
        try:
            return self.projects.get(project_id)
        except KeyError as error:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, str(error)) from error

    def _lock_for(self, project_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._project_locks.setdefault(project_id, threading.Lock())

    @staticmethod
    def _authorize(principal: str, *, write: bool) -> None:
        allowed = _WRITE_PRINCIPALS if write else _READ_PRINCIPALS
        if principal not in allowed:
            capability = "task mutation" if write else "task read"
            raise TaskError(ErrorCode.POLICY_DENIED, f"{capability} requires an authorized principal")

    @staticmethod
    def _require_exact(arguments: dict[str, Any], expected: set[str], operation: str) -> None:
        if set(arguments) != expected:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, f"{operation} requires exactly: {', '.join(sorted(expected))}")

    @staticmethod
    def _require_allowed(arguments: dict[str, Any], allowed: set[str], required: set[str], operation: str) -> None:
        if set(arguments) - allowed or not required <= set(arguments):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, f"{operation} received invalid arguments")

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 8_192) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, f"{name} must be a non-empty bounded string")
        return value

    def _task_id(self, value: Any, name: str = "task_id") -> str:
        value = self._string(value, name, 128)
        if not _ID_RE.fullmatch(value):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, f"{name} is malformed")
        return value
