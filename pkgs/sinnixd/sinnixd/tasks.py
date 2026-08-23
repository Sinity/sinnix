from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from sinnix_mcp import ErrorCode
from sinnix_mcp.execution import ExecutionProfile, ExecutionResult, OwnerExecution, OwnerRoute
from sinnix_lib.lock import flock

from .jobs import DEFAULT_TIMEOUT_SECONDS, GenericJobSpec, GenericJobs, _ensure_durable_directory, _fsync_directory
from .projects import ProjectAdapter, ProjectCatalog


MAX_TASK_OUTPUT_BYTES = 200_000
MAX_TASK_STDERR_BYTES = 8_192
MAX_TASK_OUTCOME_BYTES = MAX_TASK_OUTPUT_BYTES + 4_096
TASK_TIMEOUT_SECONDS = 30
TASK_RECONCILE_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
BEADS_EXECUTABLE = "bd"
FLOCK_EXECUTABLE = "/run/current-system/sw/bin/flock"
DEFAULT_TASK_STATE_ROOT = Path("/realm/state/tasks")
TASK_AUTHORITY_RECEIPT = "authority.json"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
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
_IDEMPOTENT_MUTATIONS = frozenset(
    {
        "task.claim",
        "task.note",
        "task.relate",
        "task.complete",
        "task.release",
    }
)


class TaskError(ValueError):
    """A task request failed with a protocol-safe error classification."""

    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        super().__init__(message)


def default_task_state_root() -> Path:
    return Path(os.environ.get("SINNIXD_TASK_STATE_ROOT", str(DEFAULT_TASK_STATE_ROOT)))


@dataclass(frozen=True)
class TaskAuthority:
    """One activated external task authority, bound by a verified cutover receipt."""

    project_id: str
    root: Path
    database: Path
    source_database: Path

    @classmethod
    def load(cls, state_root: Path, project: ProjectAdapter) -> TaskAuthority:
        root = state_root / project.project_id
        database = root / "dolt"
        receipt_path = root / TASK_AUTHORITY_RECEIPT
        try:
            receipt = json.loads(receipt_path.read_text())
        except FileNotFoundError as error:
            raise TaskError(ErrorCode.OWNER_UNAVAILABLE, "task authority is not activated") from error
        except (OSError, json.JSONDecodeError) as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority receipt is unavailable") from error
        expected_fields = {"schema", "project_id", "database", "source_database", "verification"}
        if not isinstance(receipt, dict) or set(receipt) != expected_fields:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority receipt is malformed")
        source_database_value = receipt["source_database"]
        if not isinstance(source_database_value, str) or not Path(source_database_value).is_absolute():
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority receipt is malformed")
        source_database = Path(source_database_value)
        if (
            receipt["schema"] != 1
            or receipt["project_id"] != project.project_id
            or receipt["database"] != str(database)
        ):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority receipt is malformed")
        verification = receipt["verification"]
        verification_fields = {
            "source_export_sha256",
            "destination_export_sha256",
            "source_rows",
            "destination_rows",
        }
        if not isinstance(verification, dict) or set(verification) != verification_fields:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority receipt is malformed")
        source_digest = verification["source_export_sha256"]
        destination_digest = verification["destination_export_sha256"]
        source_rows = verification["source_rows"]
        destination_rows = verification["destination_rows"]
        if (
            not isinstance(source_digest, str)
            or not _SHA256_RE.fullmatch(source_digest)
            or source_digest != destination_digest
            or isinstance(source_rows, bool)
            or not isinstance(source_rows, int)
            or source_rows < 0
            or source_rows != destination_rows
        ):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority verification is incomplete")
        if root.is_symlink() or database.is_symlink() or not database.is_dir():
            raise TaskError(ErrorCode.OWNER_UNAVAILABLE, "canonical task database is unavailable")
        try:
            canonical_database = database.resolve(strict=True)
        except OSError as error:
            raise TaskError(ErrorCode.OWNER_UNAVAILABLE, "canonical task database is unavailable") from error
        if not source_database.is_symlink():
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority cutover is ambiguous")
        try:
            active_source = source_database.resolve(strict=True)
        except OSError as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority cutover is ambiguous") from error
        if active_source != canonical_database:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority cutover is ambiguous")
        return cls(
            project_id=project.project_id,
            root=root,
            database=database,
            source_database=source_database,
        )


@dataclass(frozen=True)
class TaskOutcomeJournal:
    """Durable, backend-neutral outcomes for idempotent task mutations."""

    root: Path

    def lock_path(self, project_id: str) -> Path:
        return self.root / "locks" / f"{self._component(project_id)}.lock"

    def load(
        self,
        *,
        project_id: str,
        operation: str,
        task_id: str,
        request_id: str,
        arguments_digest: str,
    ) -> dict[str, Any] | None:
        path = self._path(project_id, operation, task_id, request_id)
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task outcome journal is unavailable") from error
        if not isinstance(value, dict) or set(value) != {
            "schema",
            "project_id",
            "operation",
            "task_id",
            "request_id",
            "arguments_digest",
            "outcome",
        }:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task outcome journal is malformed")
        if (
            value["schema"] != 1
            or value["project_id"] != project_id
            or value["operation"] != operation
            or value["task_id"] != task_id
            or value["request_id"] != request_id
        ):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task outcome journal is malformed")
        if value["arguments_digest"] != arguments_digest:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "request_id belongs to a different task mutation")
        outcome = value["outcome"]
        if not isinstance(outcome, dict) or set(outcome) != {"project_id", "operation", "result"}:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task outcome journal is malformed")
        if outcome["project_id"] != project_id or outcome["operation"] != operation:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task outcome journal is malformed")
        return outcome

    def save(
        self,
        *,
        project_id: str,
        operation: str,
        task_id: str,
        request_id: str,
        arguments_digest: str,
        outcome: dict[str, Any],
    ) -> None:
        value = {
            "schema": 1,
            "project_id": project_id,
            "operation": operation,
            "task_id": task_id,
            "request_id": request_id,
            "arguments_digest": arguments_digest,
            "outcome": outcome,
        }
        try:
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        except (TypeError, ValueError) as error:
            raise TaskError(ErrorCode.RESULT_INVALID, "task backend returned invalid JSON") from error
        if len(encoded) > MAX_TASK_OUTCOME_BYTES:
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task outcome exceeds the storage bound")
        path = self._path(project_id, operation, task_id, request_id)
        _ensure_durable_directory(path.parent)
        temporary = path.with_suffix(".json.tmp")
        try:
            descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.write(b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            _fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def _path(self, project_id: str, operation: str, task_id: str, request_id: str) -> Path:
        return (
            self.root
            / self._component(project_id)
            / self._component(operation)
            / self._component(task_id)
            / f"{self._component(request_id)}.json"
        )

    @staticmethod
    def _component(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()


class TaskCommandBoundary(Protocol):
    """Injectable process boundary for the current task backend."""

    def run(
        self,
        *,
        argv: tuple[str, ...],
        cwd: Path,
        lock_path: Path | None = None,
    ) -> ExecutionResult: ...


@dataclass(frozen=True)
class BeadsCommandBoundary:
    """Bounded fixed-argv execution of the current Beads backend."""

    execution: OwnerExecution = field(default_factory=OwnerExecution)
    executable: str = "bd"

    def run(
        self,
        *,
        argv: tuple[str, ...],
        cwd: Path,
        lock_path: Path | None = None,
    ) -> ExecutionResult:
        command = (self.executable, *argv)
        if lock_path is not None:
            command = (FLOCK_EXECUTABLE, "--exclusive", str(lock_path), *command)
        return self.execution.run(
            command,
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
    jobs: GenericJobs
    boundary: TaskCommandBoundary = field(default_factory=BeadsCommandBoundary)
    outcomes: TaskOutcomeJournal | None = None
    task_state_root: Path = field(default_factory=default_task_state_root)
    _locks_guard: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _project_locks: dict[str, threading.Lock] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.task_state_root.is_absolute():
            raise ValueError("task state root must be absolute")
        if self.outcomes is None:
            self.outcomes = TaskOutcomeJournal(self.jobs.store.root / "task-outcomes")

    def execute(
        self,
        *,
        operation: str,
        arguments: dict[str, Any] | Any,
        principal: str,
        mutation_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "task arguments must be an object")
        write = operation in _MUTATIONS
        self._authorize(principal, write=write)
        project = self._project(arguments)
        if write:
            with self._lock_for(project.project_id):
                if operation in _IDEMPOTENT_MUTATIONS:
                    return self._execute_idempotent_mutation(
                        project,
                        operation,
                        arguments,
                        self._mutation_id(mutation_id),
                    )
                return self._execute(project, operation, arguments)
        return self._execute(project, operation, arguments)

    def _execute_idempotent_mutation(
        self,
        project: ProjectAdapter,
        operation: str,
        arguments: dict[str, Any],
        request_id: str,
    ) -> dict[str, Any]:
        command = self._mutation_command(operation, arguments)
        task_id = self._task_id(arguments["task_id"])
        arguments_digest = "sha256:" + hashlib.sha256(
            json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        assert self.outcomes is not None
        with flock(self.outcomes.lock_path(project.project_id)):
            prior = self.outcomes.load(
                project_id=project.project_id,
                operation=operation,
                task_id=task_id,
                request_id=request_id,
                arguments_digest=arguments_digest,
            )
            if prior is not None:
                return prior
            outcome = {
                "project_id": project.project_id,
                "operation": operation,
                "result": self._run(project, command, readonly=False),
            }
            self.outcomes.save(
                project_id=project.project_id,
                operation=operation,
                task_id=task_id,
                request_id=request_id,
                arguments_digest=arguments_digest,
                outcome=outcome,
            )
            self._after_mutation_commit(outcome)
            return outcome

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
        elif operation in _IDEMPOTENT_MUTATIONS:
            result = self._run(project, self._mutation_command(operation, arguments), readonly=False)
        elif operation == "task.reconcile":
            self._require_exact(arguments, {"project_id"}, operation)
            result = self._start_reconcile(project)
        elif operation == "task.snapshot":
            self._require_exact(arguments, {"project_id"}, operation)
            result = self._run(project, ("export",), readonly=True, json_lines=True)
        else:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, f"unsupported task operation: {operation}")
        return {"project_id": project.project_id, "operation": operation, "result": result}

    def _mutation_command(self, operation: str, arguments: dict[str, Any]) -> tuple[str, ...]:
        if operation == "task.claim":
            self._require_exact(arguments, {"project_id", "task_id"}, operation)
            return ("update", self._task_id(arguments["task_id"]), "--claim")
        if operation == "task.note":
            self._require_exact(arguments, {"project_id", "task_id", "text"}, operation)
            return ("note", self._task_id(arguments["task_id"]), self._string(arguments["text"], "text", 32_000))
        if operation == "task.relate":
            self._require_exact(arguments, {"project_id", "task_id", "related_task_id"}, operation)
            return (
                "dep",
                "relate",
                self._task_id(arguments["task_id"]),
                self._task_id(arguments["related_task_id"], "related_task_id"),
            )
        if operation == "task.complete":
            self._require_allowed(arguments, {"project_id", "task_id", "reason"}, {"project_id", "task_id"}, operation)
            command = ["close", self._task_id(arguments["task_id"])]
            if "reason" in arguments:
                command.extend(("--reason", self._string(arguments["reason"], "reason", 32_000)))
            return tuple(command)
        if operation == "task.release":
            self._require_allowed(arguments, {"project_id", "task_id", "reason", "if_assignee"}, {"project_id", "task_id"}, operation)
            command = ["unclaim", self._task_id(arguments["task_id"])]
            if "reason" in arguments:
                command.extend(("--reason", self._string(arguments["reason"], "reason", 32_000)))
            if "if_assignee" in arguments:
                command.extend(("--if-assignee", self._string(arguments["if_assignee"], "if_assignee", 256)))
            return tuple(command)
        raise AssertionError(f"unsupported idempotent mutation: {operation}")

    @staticmethod
    def _after_mutation_commit(outcome: dict[str, Any]) -> None:
        """Test seam for simulating a response failure after durable persistence."""

        _ = outcome

    def _run(
        self,
        project: ProjectAdapter,
        command: tuple[str, ...],
        *,
        readonly: bool,
        json_lines: bool = False,
    ) -> Any:
        authority = self._authority(project)
        argv = (
            "--directory",
            str(project.root),
            "--db",
            str(authority.database),
            "--json",
            *(("--readonly",) if readonly else ()),
            *command,
        )
        result = self.boundary.run(
            argv=argv,
            cwd=project.root,
            lock_path=None if readonly else self._lock_path(project),
        )
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

    def _start_reconcile(self, project: ProjectAdapter) -> dict[str, Any]:
        """Schedule the fixed Beads reconciliation outside the owner request."""

        job_id = str(uuid4())
        lock_path = self._lock_path(project)
        authority = self._authority(project)
        environment = project.environment.values()
        environment.update(
            {
                "SINNIXD_JOB_ID": job_id,
                "SINNIXD_PROJECT_ID": project.project_id,
                "SINNIXD_OPERATION": "task.reconcile",
            }
        )
        return self.jobs.start(
            GenericJobSpec(
                kind="foreground-command",
                command=(
                    FLOCK_EXECUTABLE,
                    "--exclusive",
                    str(lock_path),
                    BEADS_EXECUTABLE,
                    "--directory",
                    str(project.root),
                    "--db",
                    str(authority.database),
                    "--json",
                    "sync",
                    "--no-adopt",
                ),
                working_directory=str(project.root),
                environment=environment,
                timeout_seconds=TASK_RECONCILE_TIMEOUT_SECONDS,
                project_id=project.project_id,
                operation="task.reconcile",
            ),
            job_id,
        )

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

    def _authority(self, project: ProjectAdapter) -> TaskAuthority:
        return TaskAuthority.load(self.task_state_root, project)

    def _lock_path(self, project: ProjectAdapter) -> Path:
        self.jobs.store.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        return self.jobs.store.root / f"task-{project.project_id}.lock"

    def _mutation_id(self, value: str | None) -> str:
        value = self._string(value, "request_id", 128)
        if not _ID_RE.fullmatch(value):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "request_id is malformed")
        return value

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
