from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from sinnix_mcp import ErrorCode, SinnixRef
from sinnix_mcp.execution import ExecutionProfile, ExecutionResult, OwnerExecution, OwnerRoute
from sinnix_lib.lock import flock

from .jobs import DEFAULT_TIMEOUT_SECONDS, GenericJobSpec, GenericJobs, _ensure_durable_directory, _fsync_directory
from .projects import ProjectAdapter, ProjectCatalog


MAX_TASK_OUTPUT_BYTES = 200_000
MAX_TASK_STDERR_BYTES = 8_192
MAX_TASK_LIST_SOURCE_BYTES = 8_000_000
MAX_TASK_LIST_ROWS = 100_000
MAX_TASK_LIST_CURSOR_BYTES = 512
MAX_TASK_LIST_SNAPSHOT_BYTES = MAX_TASK_LIST_SOURCE_BYTES
MAX_TASK_LIST_SNAPSHOTS = 128
MAX_TASK_MUTATION_INTENT_BYTES = 64_000
MAX_TASK_MUTATION_RECORD_BYTES = 8_192
MAX_TASK_MUTATION_RECORDS = 1_024
TASK_TIMEOUT_SECONDS = 30
TASK_RECONCILE_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
FLOCK_EXECUTABLE = "/run/current-system/sw/bin/flock"
DEFAULT_TASK_STATE_ROOT = Path("/realm/state/tasks")
TASK_AUTHORITY_RECEIPT = "authority.json"
TASK_MUTATION_JOURNAL_DIRECTORY = "sinnixd-task-mutations"
TASK_LIST_SNAPSHOT_DIRECTORY = "sinnixd-task-list-snapshots"
TASK_LIST_CURSOR_KEY = "sinnixd-task-list-cursor.key"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_MERGE_SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_READ_PRINCIPALS = frozenset({"observer", "agent-control", "operator"})
_WRITE_PRINCIPALS = frozenset({"agent-control", "operator"})
_MUTATIONS = frozenset({"task.create", "task.claim", "task.note", "task.relate", "task.complete", "task.release", "task.reconcile"})
_IDEMPOTENT_MUTATIONS = frozenset({"task.create", "task.claim", "task.note", "task.relate", "task.complete", "task.release"})
_MUTATION_STATES = frozenset({"pending", "dispatching", "applied", "failed"})
_ISSUE_TYPES = frozenset({"bug", "feature", "task", "epic", "chore", "decision", "spike", "story", "milestone"})
_DEPENDENCY_RELATIONS = frozenset({"depends-on", "blocks", "tracks", "related", "discovered-from", "until", "caused-by", "validates", "relates-to", "supersedes"})
_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,63}$")


class TaskError(ValueError):
    """A task request failed with a protocol-safe error classification."""

    def __init__(self, code: ErrorCode, message: str, *, retryable: bool = False):
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class TaskListCursorError(TaskError):
    """A task-list cursor was malformed, mismatched, or no longer usable."""

    def __init__(self, message: str, *, stale: bool = False):
        super().__init__(ErrorCode.STALE_CURSOR if stale else ErrorCode.INVALID_ARGUMENT, message)


def _canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


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
    def load(cls, state_root: Path, project_id: str) -> TaskAuthority:
        root = state_root / project_id
        database = root / ".beads" / "dolt"
        try:
            receipt = json.loads((root / TASK_AUTHORITY_RECEIPT).read_text())
        except FileNotFoundError as error:
            raise TaskError(ErrorCode.OWNER_UNAVAILABLE, "task authority is not activated") from error
        except (OSError, json.JSONDecodeError) as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority receipt is unavailable") from error
        expected = {"schema", "project_id", "database", "source_database", "verification"}
        if not isinstance(receipt, dict) or set(receipt) != expected or receipt["schema"] != 1:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority receipt is malformed")
        source_value = receipt["source_database"]
        if receipt["project_id"] != project_id or receipt["database"] != str(database) or not isinstance(source_value, str) or not Path(source_value).is_absolute():
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority receipt is malformed")
        verification = receipt["verification"]
        verification_keys = {"source_export_sha256", "destination_export_sha256", "source_rows", "destination_rows"}
        if not isinstance(verification, dict) or set(verification) != verification_keys:
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
            or root.is_symlink()
            or database.is_symlink()
            or not database.is_dir()
        ):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority verification is incomplete")
        try:
            canonical_database = database.resolve(strict=True)
            source_database = Path(source_value)
            redirect_target = Path((source_database.parent / "redirect").read_text().strip()).resolve(strict=True)
        except (OSError, ValueError) as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority cutover is ambiguous") from error
        if source_database.exists() or source_database.is_symlink() or redirect_target != canonical_database.parent:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task authority cutover is ambiguous")
        return cls(project_id, root, database, source_database)


@dataclass(frozen=True)
class TaskMutationIdentity:
    """Stable key for one task intent. Only the digest is persisted publicly."""

    project_id: str
    operation: str
    task_id: str
    idempotency_sha256: str

    @classmethod
    def create(cls, project_id: str, operation: str, task_id: str, idempotency_key: str) -> TaskMutationIdentity:
        return cls(project_id, operation, task_id, cls.digest(idempotency_key))

    def public(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "operation": self.operation,
            "task_id": self.task_id,
            "idempotency_sha256": self.idempotency_sha256,
        }

    def record_key(self) -> str:
        return self.digest(json.dumps(self.public(), sort_keys=True, separators=(",", ":"))).removeprefix("sha256:")

    @staticmethod
    def digest(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class TaskMutationRecord:
    """Redacted journal state. The replayable command is a separate 0600 intent."""

    identity: TaskMutationIdentity
    arguments_sha256: str
    state: str
    attempts: int
    intent_sha256: str
    result: dict[str, Any] | None
    failure: dict[str, str] | None

    def receipt(self) -> dict[str, Any]:
        return {
            "identity": self.identity.public(),
            "state": self.state,
            "attempts": self.attempts,
            "result": self.result,
            "failure": self.failure,
        }


@dataclass(frozen=True)
class TaskMutationJournal:
    """Bounded, fsynced task mutation records in the canonical authority root."""

    root: Path
    max_records: int = MAX_TASK_MUTATION_RECORDS

    @property
    def records_root(self) -> Path:
        return self.root / "records"

    @property
    def intents_root(self) -> Path:
        return self.root / "intents"

    def load(self, identity: TaskMutationIdentity, arguments_sha256: str) -> TaskMutationRecord | None:
        record = self._load(identity)
        if record is not None and record.arguments_sha256 != arguments_sha256:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "idempotency identity belongs to a different task mutation")
        return record

    def create(self, identity: TaskMutationIdentity, arguments_sha256: str, command: tuple[str, ...]) -> TaskMutationRecord:
        if self._load(identity) is not None:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal changed during submission")
        if len(tuple(self.records_root.glob("*.json"))) >= self.max_records:
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task mutation journal is full")
        try:
            intent = json.dumps({"schema": 1, "command": list(command)}, sort_keys=True, separators=(",", ":")).encode()
        except (TypeError, ValueError) as error:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "task mutation intent is invalid") from error
        if len(intent) > MAX_TASK_MUTATION_INTENT_BYTES:
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task mutation intent exceeds the storage bound")
        intent_sha256 = "sha256:" + hashlib.sha256(intent + b"\n").hexdigest()
        self._write(self._intent_path(identity), intent)
        record = TaskMutationRecord(identity, arguments_sha256, "pending", 0, intent_sha256, None, None)
        self.save(record)
        return record

    def save(self, record: TaskMutationRecord) -> None:
        self._validate(record)
        value = {
            "schema": 1,
            "identity": record.identity.public(),
            "arguments_sha256": record.arguments_sha256,
            "state": record.state,
            "attempts": record.attempts,
            "intent_sha256": record.intent_sha256,
            "result": record.result,
            "failure": record.failure,
        }
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > MAX_TASK_MUTATION_RECORD_BYTES:
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task mutation receipt exceeds the storage bound")
        self._write(self._record_path(record.identity), encoded)

    def records(self) -> tuple[TaskMutationRecord, ...]:
        try:
            paths = sorted(self.records_root.glob("*.json"))
        except OSError as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is unavailable") from error
        if len(paths) > self.max_records:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal exceeds its bound")
        return tuple(self._read(path) for path in paths)

    def intent(self, record: TaskMutationRecord) -> tuple[str, ...]:
        try:
            encoded = self._intent_path(record.identity).read_bytes()
            value = json.loads(encoded)
        except FileNotFoundError as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation intent is missing") from error
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation intent is unavailable") from error
        if "sha256:" + hashlib.sha256(encoded).hexdigest() != record.intent_sha256:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation intent is malformed")
        command = value.get("command") if isinstance(value, dict) and value.get("schema") == 1 else None
        if not isinstance(command, list) or not command or len(command) > 32 or any(not isinstance(item, str) or not item or len(item) > 32_000 for item in command):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation intent is malformed")
        return tuple(command)

    def dispatching(self, record: TaskMutationRecord) -> TaskMutationRecord:
        updated = replace(record, state="dispatching", attempts=record.attempts + 1, failure=None)
        self.save(updated)
        return updated

    def pending(self, record: TaskMutationRecord, error: TaskError) -> TaskMutationRecord:
        updated = replace(record, state="pending", failure={"code": error.code.value})
        self.save(updated)
        return updated

    def applied(self, record: TaskMutationRecord, result: Any, *, created_task_id: str | None = None) -> TaskMutationRecord:
        try:
            encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        except (TypeError, ValueError) as error:
            raise TaskError(ErrorCode.RESULT_INVALID, "task backend returned invalid JSON") from error
        evidence: dict[str, Any] = {"sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}
        if created_task_id is not None:
            evidence["created_task_id"] = created_task_id
        updated = replace(record, state="applied", result=evidence, failure=None)
        self.save(updated)
        try:
            self._intent_path(updated.identity).unlink(missing_ok=True)
            _fsync_directory(self.intents_root)
        except OSError as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation intent cleanup failed") from error
        return updated

    def failed(self, record: TaskMutationRecord, error: TaskError) -> TaskMutationRecord:
        updated = replace(record, state="failed", failure={"code": error.code.value})
        self.save(updated)
        return updated

    def _load(self, identity: TaskMutationIdentity) -> TaskMutationRecord | None:
        path = self._record_path(identity)
        try:
            return self._read(path)
        except FileNotFoundError:
            return None

    def _read(self, path: Path) -> TaskMutationRecord:
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as error:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed") from error
        expected = {"schema", "identity", "arguments_sha256", "state", "attempts", "intent_sha256", "result", "failure"}
        if not isinstance(value, dict) or set(value) != expected or value["schema"] != 1:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        identity_value = value["identity"]
        if not isinstance(identity_value, dict) or set(identity_value) != {"project_id", "operation", "task_id", "idempotency_sha256"}:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        identity = TaskMutationIdentity(**identity_value)
        record = TaskMutationRecord(identity, value["arguments_sha256"], value["state"], value["attempts"], value["intent_sha256"], value["result"], value["failure"])
        self._validate(record)
        return record

    @staticmethod
    def _validate(record: TaskMutationRecord) -> None:
        if (
            not _ID_RE.fullmatch(record.identity.project_id)
            or not _ID_RE.fullmatch(record.identity.task_id)
            or record.identity.operation not in _IDEMPOTENT_MUTATIONS
            or not _SHA256_RE.fullmatch(record.identity.idempotency_sha256)
            or not _SHA256_RE.fullmatch(record.arguments_sha256)
            or record.state not in _MUTATION_STATES
            or isinstance(record.attempts, bool)
            or not isinstance(record.attempts, int)
            or not 0 <= record.attempts <= 1_000
            or not _SHA256_RE.fullmatch(record.intent_sha256)
        ):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        if record.result is not None and (
            not isinstance(record.result, dict)
            or set(record.result) not in ({"sha256", "bytes"}, {"sha256", "bytes", "created_task_id"})
            or not isinstance(record.result["sha256"], str)
            or not _SHA256_RE.fullmatch(record.result["sha256"])
            or isinstance(record.result["bytes"], bool)
            or not isinstance(record.result["bytes"], int)
            or not 0 <= record.result["bytes"] <= MAX_TASK_OUTPUT_BYTES
        ):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        if "created_task_id" in (record.result or {}) and not _ID_RE.fullmatch(record.result["created_task_id"]):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        if record.identity.operation == "task.create" and record.state == "applied" and "created_task_id" not in (record.result or {}):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        if record.identity.operation != "task.create" and "created_task_id" in (record.result or {}):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        if record.failure is not None and (
            not isinstance(record.failure, dict) or set(record.failure) != {"code"} or record.failure["code"] not in {code.value for code in ErrorCode}
        ):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        if record.state == "applied" and (record.result is None or record.failure is not None):
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        if record.state == "pending" and record.result is not None:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")
        if record.state == "failed" and record.failure is None:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task mutation journal is malformed")

    def _record_path(self, identity: TaskMutationIdentity) -> Path:
        return self.records_root / f"{identity.record_key()}.json"

    def _intent_path(self, identity: TaskMutationIdentity) -> Path:
        return self.intents_root / f"{identity.record_key()}.json"

    @staticmethod
    def _write(path: Path, encoded: bytes) -> None:
        _ensure_durable_directory(path.parent)
        temporary = path.with_suffix(path.suffix + ".tmp")
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


class TaskCommandBoundary(Protocol):
    def run(
        self,
        *,
        argv: tuple[str, ...],
        cwd: Path,
        environment: dict[str, str],
        lock_path: Path | None = None,
        max_stdout_bytes: int | None = None,
    ) -> ExecutionResult: ...


@dataclass(frozen=True)
class BeadsCommandBoundary:
    execution: OwnerExecution = field(default_factory=OwnerExecution)
    executable: str = "bd"

    def run(
        self,
        *,
        argv: tuple[str, ...],
        cwd: Path,
        environment: dict[str, str],
        lock_path: Path | None = None,
        max_stdout_bytes: int | None = None,
    ) -> ExecutionResult:
        command = (self.executable, *argv) if lock_path is None else (FLOCK_EXECUTABLE, "--exclusive", str(lock_path), self.executable, *argv)
        return self.execution.run(
            command,
            ExecutionProfile(route=OwnerRoute("task-backend"), timeout_seconds=TASK_TIMEOUT_SECONDS, max_stdout_bytes=max_stdout_bytes or MAX_TASK_OUTPUT_BYTES, max_stderr_bytes=MAX_TASK_STDERR_BYTES, max_combined_output_bytes=(max_stdout_bytes or MAX_TASK_OUTPUT_BYTES) + MAX_TASK_STDERR_BYTES, cwd=cwd, environment=environment),
        )


def _run_task_command(
    boundary: TaskCommandBoundary,
    authority: TaskAuthority,
    cwd: Path,
    command: tuple[str, ...],
    *,
    readonly: bool,
    json_lines: bool = False,
    max_stdout_bytes: int = MAX_TASK_OUTPUT_BYTES,
) -> Any:
    result = boundary.run(
        argv=("--json", *(("--readonly",) if readonly else ()), *command),
        cwd=cwd,
        environment={"BEADS_DIR": str(authority.root / ".beads")},
        **({"max_stdout_bytes": max_stdout_bytes} if max_stdout_bytes != MAX_TASK_OUTPUT_BYTES else {}),
    )
    if result.timed_out or result.failure_class == "command_timeout":
        raise TaskError(ErrorCode.OWNER_UNAVAILABLE, "task backend timed out")
    if result.output_exceeded or result.failure_class == "command_output_bound" or len(result.stdout) > max_stdout_bytes or len(result.stderr) > MAX_TASK_STDERR_BYTES:
        raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task backend response exceeded the output bound")
    if result.failure_class is not None:
        if result.failure_class.startswith("command_unavailable"):
            raise TaskError(ErrorCode.OWNER_UNAVAILABLE, "task backend is unavailable", retryable=True)
        raise TaskError(ErrorCode.OPERATION_FAILED, "task backend command failed")
    if result.exit_status != 0:
        raise TaskError(ErrorCode.OPERATION_FAILED, "task backend command failed")
    try:
        if json_lines:
            records = [json.loads(line) for line in result.stdout.decode().splitlines() if line]
            if not all(isinstance(record, dict) for record in records):
                raise ValueError
            return records
        return json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise TaskError(ErrorCode.RESULT_INVALID, "task backend returned invalid JSON") from error


def reconcile_task_mutations(*, journal: TaskMutationJournal, authority: TaskAuthority, cwd: Path, boundary: TaskCommandBoundary) -> tuple[dict[str, Any], ...]:
    """Replay pending intents; a crash after dispatch stays failed rather than duplicating it."""

    receipts: list[dict[str, Any]] = []
    for record in journal.records():
        if record.state == "dispatching":
            record = journal.failed(record, TaskError(ErrorCode.OWNER_UNAVAILABLE, "task outcome is unknown"))
        elif record.state == "pending":
            record = journal.dispatching(record)
            try:
                result = _run_task_command(boundary, authority, cwd, journal.intent(record), readonly=False)
                created_task_id = TaskService._created_task_id(result) if record.identity.operation == "task.create" else None
            except TaskError as error:
                record = journal.pending(record, error) if error.retryable else journal.failed(record, error)
            else:
                record = journal.applied(record, result, created_task_id=created_task_id)
        receipts.append(record.receipt())
    return tuple(receipts)


@dataclass
class TaskService:
    projects: ProjectCatalog
    jobs: GenericJobs
    boundary: TaskCommandBoundary = field(default_factory=BeadsCommandBoundary)
    task_state_root: Path = field(default_factory=default_task_state_root)
    _locks_guard: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _project_locks: dict[str, threading.Lock] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.task_state_root.is_absolute():
            raise ValueError("task state root must be absolute")

    def execute(self, *, operation: str, arguments: dict[str, Any] | Any, principal: str, mutation_id: str | None = None) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "task arguments must be an object")
        write = operation in _MUTATIONS
        self._authorize(principal, write=write)
        project = self._project(arguments)
        if not write:
            return self._execute(project, operation, arguments, principal=principal)
        with self._lock_for(project.project_id), flock(self._lock_path(project)):
            if operation in _IDEMPOTENT_MUTATIONS:
                return self._submit_mutation(project, operation, arguments, self._mutation_id(mutation_id))
            return self._execute(project, operation, arguments, principal=principal)

    def _submit_mutation(self, project: ProjectAdapter, operation: str, arguments: dict[str, Any], request_id: str) -> dict[str, Any]:
        command = self._mutation_command(operation, arguments)
        task_id = "create" if operation == "task.create" else self._task_id(arguments["task_id"])
        idempotency_key = self._merge_sha(arguments["merge_sha"]) if operation == "task.complete" else request_id
        identity = TaskMutationIdentity.create(project.project_id, operation, task_id, idempotency_key)
        arguments_sha256 = TaskMutationIdentity.digest(json.dumps(arguments, sort_keys=True, separators=(",", ":")))
        authority = self._authority(project)
        journal = TaskMutationJournal(authority.root / TASK_MUTATION_JOURNAL_DIRECTORY)
        record = journal.load(identity, arguments_sha256) or journal.create(identity, arguments_sha256, command)
        if record.state == "dispatching":
            record = journal.failed(record, TaskError(ErrorCode.OWNER_UNAVAILABLE, "task outcome is unknown"))
        elif record.state == "pending":
            record = journal.dispatching(record)
            try:
                result = _run_task_command(self.boundary, authority, project.root, command, readonly=False)
                created_task_id = self._created_task_id(result) if operation == "task.create" else None
            except TaskError as error:
                record = journal.pending(record, error) if error.retryable else journal.failed(record, error)
            else:
                record = journal.applied(record, result, created_task_id=created_task_id)
        response = {"project_id": project.project_id, "operation": operation, "result": record.receipt()}
        if operation == "task.create":
            response["owner_evidence"] = {
                "owner": "task-backend",
                "state": record.state,
                "attempts": record.attempts,
                "result": record.result,
                "failure": record.failure,
            }
            if record.state == "applied":
                assert record.result is not None
                response["task_ref"] = self._task_ref(project.project_id, record.result["created_task_id"])
        return response

    def _execute(self, project: ProjectAdapter, operation: str, arguments: dict[str, Any], *, principal: str) -> dict[str, Any]:
        if operation == "task.list":
            result = self._list(project, arguments, principal=principal)
        elif operation == "task.get":
            self._require_exact(arguments, {"project_id", "task_id"}, operation)
            result = self._run(project, ("show", self._task_id(arguments["task_id"])), readonly=True)
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
        if operation == "task.create":
            self._require_allowed(arguments, {"project_id", "title", "description", "issue_type", "priority", "labels", "parent_task_id", "dependencies"}, {"project_id", "title", "description", "issue_type", "priority", "labels", "dependencies"}, operation)
            issue_type = self._string(arguments["issue_type"], "issue_type", 32)
            if issue_type not in _ISSUE_TYPES:
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "issue_type is unsupported")
            priority = arguments["priority"]
            if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 4:
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "priority must be an integer from 0 through 4")
            command = [
                "create",
                "--title",
                self._string(arguments["title"], "title", 512),
                "--description",
                self._string(arguments["description"], "description", 32_000),
                "--type",
                issue_type,
                "--priority",
                str(priority),
            ]
            labels = self._labels(arguments["labels"])
            if labels:
                command.extend(("--labels", ",".join(labels)))
            if "parent_task_id" in arguments:
                command.extend(("--parent", self._task_id(arguments["parent_task_id"], "parent_task_id")))
            dependencies = self._dependencies(arguments["dependencies"])
            if dependencies:
                command.extend(("--deps", ",".join(f"{relation}:{task_id}" for relation, task_id in dependencies)))
            return tuple(command)
        if operation == "task.claim":
            self._require_exact(arguments, {"project_id", "task_id"}, operation)
            return ("update", self._task_id(arguments["task_id"]), "--claim")
        if operation == "task.note":
            self._require_exact(arguments, {"project_id", "task_id", "text"}, operation)
            return ("note", self._task_id(arguments["task_id"]), self._string(arguments["text"], "text", 32_000))
        if operation == "task.relate":
            self._require_exact(arguments, {"project_id", "task_id", "related_task_id"}, operation)
            return ("dep", "relate", self._task_id(arguments["task_id"]), self._task_id(arguments["related_task_id"], "related_task_id"))
        if operation == "task.complete":
            self._require_allowed(arguments, {"project_id", "task_id", "merge_sha", "reason"}, {"project_id", "task_id", "merge_sha"}, operation)
            command = ["close", self._task_id(arguments["task_id"])]
            self._merge_sha(arguments["merge_sha"])
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

    def _run(
        self,
        project: ProjectAdapter,
        command: tuple[str, ...],
        *,
        readonly: bool,
        json_lines: bool = False,
        max_stdout_bytes: int = MAX_TASK_OUTPUT_BYTES,
    ) -> Any:
        return _run_task_command(
            self.boundary,
            self._authority(project),
            project.root,
            command,
            readonly=readonly,
            json_lines=json_lines,
            max_stdout_bytes=max_stdout_bytes,
        )

    def _start_reconcile(self, project: ProjectAdapter) -> dict[str, Any]:
        job_id = str(uuid4())
        authority = self._authority(project)
        environment = project.environment.values()
        environment.update({"SINNIXD_JOB_ID": job_id, "SINNIXD_PROJECT_ID": project.project_id, "SINNIXD_OPERATION": "task.reconcile", "BEADS_DIR": str(authority.root / ".beads")})
        return self.jobs.start(
            GenericJobSpec(
                kind="foreground-command",
                command=(FLOCK_EXECUTABLE, "--exclusive", str(self._lock_path(project)), "sinnixd-task-reconcile", "--project-id", project.project_id, "--project-root", str(project.root), "--task-state-root", str(self.task_state_root)),
                working_directory=str(project.root), environment=environment, timeout_seconds=TASK_RECONCILE_TIMEOUT_SECONDS, project_id=project.project_id, operation="task.reconcile",
            ),
            job_id,
        )

    def _list(self, project: ProjectAdapter, arguments: dict[str, Any], *, principal: str) -> dict[str, Any]:
        limit, order, query = self._list_query(arguments)
        query_sha256 = _canonical_digest(query)
        cursor = arguments.get("cursor")
        if cursor is not None:
            snapshot_id, offset, source_revision = self._decode_task_list_cursor(
                project, principal=principal, query_sha256=query_sha256, cursor=cursor
            )
            snapshot = self._load_task_list_snapshot(
                project,
                snapshot_id,
                principal=principal,
                query_sha256=query_sha256,
                source_revision=source_revision,
            )
        else:
            result = self._run(
                project,
                self._list_command(arguments),
                readonly=True,
                max_stdout_bytes=MAX_TASK_LIST_SOURCE_BYTES,
            )
            if not isinstance(result, dict) or set(result) - {"issues"} or not isinstance(result.get("issues"), list):
                raise TaskError(ErrorCode.RESULT_INVALID, "task backend returned an invalid list result")
            rows = result["issues"]
            if len(rows) > MAX_TASK_LIST_ROWS or any(not isinstance(row, dict) for row in rows):
                raise TaskError(ErrorCode.RESULT_INVALID, "task backend returned invalid list rows")
            snapshot = self._create_task_list_snapshot(
                project, principal=principal, query_sha256=query_sha256, rows=rows
            )
            offset = 0

        rows = snapshot["rows"]
        if offset > len(rows):
            raise TaskListCursorError("task list cursor is beyond its snapshot", stale=True)
        page_rows = rows[offset : offset + limit]
        next_offset = offset + len(page_rows)
        next_cursor = (
            self._encode_task_list_cursor(
                project,
                snapshot,
                principal=principal,
                query_sha256=query_sha256,
                offset=next_offset,
            )
            if next_offset < len(rows)
            else None
        )
        page = {
            "issues": page_rows,
            "limit": limit,
            "total": len(rows),
            "truncated": next_cursor is not None,
            "next_cursor": next_cursor,
            "source_revision": snapshot["source_revision"],
            "coverage": {
                "state": "complete",
                "kind": "result_snapshot",
                "returned": len(rows),
                "total": len(rows),
                "total_exact": True,
                "source_revision": snapshot["source_revision"],
            },
            "page": {
                "kind": "snapshot",
                "offset": offset,
                "next_offset": next_offset if next_cursor is not None else None,
                "complete": next_cursor is None,
            },
        }
        if len(json.dumps(page, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()) > MAX_TASK_OUTPUT_BYTES:
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task list page exceeds the response bound")
        return page

    def _list_query(self, arguments: dict[str, Any]) -> tuple[int, dict[str, Any] | None, dict[str, Any]]:
        self._require_allowed(
            arguments,
            {"project_id", "status", "assignee", "label", "limit", "include_closed", "ready", "order", "cursor"},
            {"project_id"},
            "task.list",
        )
        limit = arguments.get("limit", 100)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1_000:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "limit must be an integer from 1 through 1000")
        filters: dict[str, Any] = {}
        for name in ("status", "assignee", "label"):
            if name in arguments:
                filters[name] = self._string(arguments[name], name, 256)
        for name in ("include_closed", "ready"):
            value = arguments.get(name, False)
            if not isinstance(value, bool):
                raise TaskError(ErrorCode.INVALID_ARGUMENT, f"{name} must be boolean")
            if value:
                filters[name] = True
        order = arguments.get("order")
        if order is not None:
            if not isinstance(order, Mapping) or set(order) - {"field", "reverse"} or "field" not in order:
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "order must contain a supported field and optional reverse")
            field_name = order["field"]
            if not isinstance(field_name, str) or field_name not in {"priority", "created", "updated", "closed", "status", "id", "title", "type", "assignee"}:
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "order field is unsupported")
            reverse = order.get("reverse", False)
            if not isinstance(reverse, bool):
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "order is malformed")
            order = {"field": field_name, "reverse": reverse}
        if "cursor" in arguments:
            cursor = arguments["cursor"]
            if not isinstance(cursor, str) or not cursor:
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "task list cursor must be a string")
            if len(cursor.encode()) > MAX_TASK_LIST_CURSOR_BYTES:
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "task list cursor exceeds its bound")
        query = {"project_id": arguments["project_id"], "filters": filters, "limit": limit, "order": order}
        return limit, order, query

    def _list_command(self, arguments: dict[str, Any]) -> tuple[str, ...]:
        _, order, _ = self._list_query(arguments)
        command = ["list", "--flat"]
        for name, flag in (("include_closed", "--all"), ("ready", "--ready")):
            if arguments.get(name, False):
                command.append(flag)
        for name, flag in (("status", "--status"), ("assignee", "--assignee"), ("label", "--label")):
            if name in arguments:
                command.extend((flag, self._string(arguments[name], name, 256)))
        if order is not None:
            command.extend(("--sort", order["field"]))
            if order["reverse"]:
                command.append("--reverse")
        command.extend(("--limit", "0", "--max-rows", str(MAX_TASK_LIST_ROWS)))
        return tuple(command)

    def _task_list_cursor_key(self, project: ProjectAdapter) -> bytes:
        path = self._authority(project).root / TASK_LIST_CURSOR_KEY
        try:
            key = path.read_bytes()
        except FileNotFoundError:
            key = secrets.token_bytes(32)
            self._write_bounded(path, key)
        if key.endswith(b"\n"):
            key = key[:-1]
        if len(key) != 32:
            raise TaskError(ErrorCode.OPERATION_FAILED, "task list cursor key is malformed")
        return key

    def _encode_task_list_cursor(
        self,
        project: ProjectAdapter,
        snapshot: Mapping[str, Any],
        *,
        principal: str,
        query_sha256: str,
        offset: int,
    ) -> str:
        payload = json.dumps(
            {
                "schema": 1,
                "snapshot_id": snapshot["snapshot_id"],
                "offset": offset,
                "principal": principal,
                "query_sha256": query_sha256,
                "source_revision": snapshot["source_revision"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        signature = hmac.new(self._task_list_cursor_key(project), encoded.encode(), hashlib.sha256).digest()
        cursor = encoded + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")
        if len(cursor.encode()) > MAX_TASK_LIST_CURSOR_BYTES:
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task list cursor exceeds its bound")
        return cursor

    def _decode_task_list_cursor(
        self,
        project: ProjectAdapter,
        *,
        principal: str,
        query_sha256: str,
        cursor: Any,
    ) -> tuple[str, int, str]:
        if not isinstance(cursor, str) or not cursor or len(cursor.encode()) > MAX_TASK_LIST_CURSOR_BYTES:
            raise TaskListCursorError("task list cursor is malformed")
        encoded, separator, supplied_signature = cursor.partition(".")
        if not separator or not encoded or not supplied_signature:
            raise TaskListCursorError("task list cursor is malformed")
        expected_signature = base64.urlsafe_b64encode(hmac.new(self._task_list_cursor_key(project), encoded.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise TaskListCursorError("task list cursor signature is invalid")
        try:
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TaskListCursorError("task list cursor is malformed") from error
        if not isinstance(payload, dict) or set(payload) != {"schema", "snapshot_id", "offset", "principal", "query_sha256", "source_revision"} or payload["schema"] != 1:
            raise TaskListCursorError("task list cursor is malformed")
        snapshot_id = payload["snapshot_id"]
        offset = payload["offset"]
        cursor_principal = payload["principal"]
        cursor_query_sha256 = payload["query_sha256"]
        source_revision = payload["source_revision"]
        if (
            not isinstance(snapshot_id, str)
            or not re.fullmatch(r"[0-9a-f]{32}", snapshot_id)
            or isinstance(offset, bool)
            or not isinstance(offset, int)
            or offset < 0
            or not isinstance(cursor_principal, str)
            or not cursor_principal
            or not isinstance(cursor_query_sha256, str)
            or not _SHA256_RE.fullmatch(cursor_query_sha256)
            or not isinstance(source_revision, str)
            or not _SHA256_RE.fullmatch(source_revision)
        ):
            raise TaskListCursorError("task list cursor is malformed")
        if cursor_principal != principal:
            raise TaskListCursorError("task list cursor does not belong to this principal")
        if cursor_query_sha256 != query_sha256:
            raise TaskListCursorError("task list cursor does not match this query")
        return snapshot_id, offset, source_revision

    def _create_task_list_snapshot(self, project: ProjectAdapter, *, principal: str, query_sha256: str, rows: list[Any]) -> dict[str, Any]:
        source_revision = _canonical_digest(rows)
        snapshot_id = secrets.token_hex(16)
        snapshot = {
            "schema": 1,
            "snapshot_id": snapshot_id,
            "principal": principal,
            "project_id": project.project_id,
            "query_sha256": query_sha256,
            "source_revision": source_revision,
            "rows": rows,
        }
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        if len(encoded) + 1 > MAX_TASK_LIST_SNAPSHOT_BYTES:
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task list snapshot exceeds its bound")
        root = self._authority(project).root / TASK_LIST_SNAPSHOT_DIRECTORY
        _ensure_durable_directory(root)
        snapshots = sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime_ns)
        for old in snapshots[: max(0, len(snapshots) - MAX_TASK_LIST_SNAPSHOTS + 1)]:
            old.unlink(missing_ok=True)
        self._write_bounded(self._task_list_snapshot_path(project, snapshot_id), encoded)
        return snapshot

    def _load_task_list_snapshot(
        self,
        project: ProjectAdapter,
        snapshot_id: str,
        *,
        principal: str,
        query_sha256: str,
        source_revision: str,
    ) -> dict[str, Any]:
        snapshot = self._read_task_list_snapshot(self._task_list_snapshot_path(project, snapshot_id))
        if snapshot["principal"] != principal:
            raise TaskListCursorError("task list cursor does not belong to this principal")
        if snapshot["project_id"] != project.project_id:
            raise TaskListCursorError("task list cursor does not belong to this project")
        if snapshot["query_sha256"] != query_sha256:
            raise TaskListCursorError("task list cursor does not match this query")
        if snapshot["source_revision"] != source_revision:
            raise TaskListCursorError("task list cursor source revision is stale", stale=True)
        return snapshot

    def _read_task_list_snapshot(self, path: Path) -> dict[str, Any]:
        try:
            encoded = path.read_bytes()
            if len(encoded) > MAX_TASK_LIST_SNAPSHOT_BYTES:
                raise ValueError
            snapshot = json.loads(encoded)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise TaskListCursorError("task list cursor snapshot is unavailable", stale=True) from error
        if not isinstance(snapshot, dict) or set(snapshot) != {"schema", "snapshot_id", "principal", "project_id", "query_sha256", "source_revision", "rows"} or snapshot["schema"] != 1:
            raise TaskListCursorError("task list cursor snapshot is malformed", stale=True)
        if not isinstance(snapshot["snapshot_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", snapshot["snapshot_id"]):
            raise TaskListCursorError("task list cursor snapshot is malformed", stale=True)
        if not isinstance(snapshot["principal"], str) or not isinstance(snapshot["project_id"], str) or not isinstance(snapshot["query_sha256"], str) or not isinstance(snapshot["source_revision"], str) or not _SHA256_RE.fullmatch(snapshot["query_sha256"]) or not _SHA256_RE.fullmatch(snapshot["source_revision"]) or not isinstance(snapshot["rows"], list) or len(snapshot["rows"]) > MAX_TASK_LIST_ROWS or any(not isinstance(row, dict) for row in snapshot["rows"]):
            raise TaskListCursorError("task list cursor snapshot is malformed", stale=True)
        if _canonical_digest(snapshot["rows"]) != snapshot["source_revision"]:
            raise TaskListCursorError("task list cursor snapshot content is stale", stale=True)
        return snapshot

    def _task_list_snapshot_path(self, project: ProjectAdapter, snapshot_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", snapshot_id):
            raise TaskListCursorError("task list cursor snapshot is malformed")
        return self._authority(project).root / TASK_LIST_SNAPSHOT_DIRECTORY / f"{snapshot_id}.json"

    @staticmethod
    def _write_bounded(path: Path, encoded: bytes) -> None:
        if len(encoded) > MAX_TASK_LIST_SNAPSHOT_BYTES:
            raise TaskError(ErrorCode.RESOURCE_EXHAUSTED, "task list state exceeds its bound")
        TaskMutationJournal._write(path, encoded)

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
        return TaskAuthority.load(self.task_state_root, project.project_id)

    def _lock_path(self, project: ProjectAdapter) -> Path:
        return self._authority(project).root / "sinnixd-task-mutations.lock"

    def _mutation_id(self, value: str | None) -> str:
        value = self._string(value, "request_id", 128)
        if not _ID_RE.fullmatch(value):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "request_id is malformed")
        return value

    def _merge_sha(self, value: Any) -> str:
        value = self._string(value, "merge_sha", 64)
        if not _MERGE_SHA_RE.fullmatch(value):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "merge_sha must be a lowercase Git SHA")
        return value

    @staticmethod
    def _authorize(principal: str, *, write: bool) -> None:
        if principal not in (_WRITE_PRINCIPALS if write else _READ_PRINCIPALS):
            raise TaskError(ErrorCode.POLICY_DENIED, "task mutation requires an authorized principal" if write else "task read requires an authorized principal")

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

    def _labels(self, value: Any) -> tuple[str, ...]:
        if not isinstance(value, list) or len(value) > 32:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "labels must be a list of at most 32 labels")
        if any(not isinstance(label, str) or not _LABEL_RE.fullmatch(label) for label in value) or len(set(value)) != len(value):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "labels are malformed")
        return tuple(value)

    def _dependencies(self, value: Any) -> tuple[tuple[str, str], ...]:
        if not isinstance(value, list) or len(value) > 32:
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "dependencies must be a list of at most 32 relations")
        dependencies: list[tuple[str, str]] = []
        for dependency in value:
            if not isinstance(dependency, dict) or set(dependency) != {"relation", "task_id"}:
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "dependency is malformed")
            relation = self._string(dependency["relation"], "dependency relation", 32)
            if relation not in _DEPENDENCY_RELATIONS:
                raise TaskError(ErrorCode.INVALID_ARGUMENT, "dependency relation is unsupported")
            dependencies.append((relation, self._task_id(dependency["task_id"], "dependency task_id")))
        if len(set(dependencies)) != len(dependencies):
            raise TaskError(ErrorCode.INVALID_ARGUMENT, "dependencies must be unique")
        return tuple(dependencies)

    @staticmethod
    def _created_task_id(result: Any) -> str:
        if not isinstance(result, dict):
            raise TaskError(ErrorCode.RESULT_INVALID, "task backend omitted the created task")
        value = result.get("id")
        if not isinstance(value, str) or not _ID_RE.fullmatch(value):
            raise TaskError(ErrorCode.RESULT_INVALID, "task backend omitted the created task")
        return value

    @staticmethod
    def _task_ref(project_id: str, task_id: str) -> str:
        return str(SinnixRef.parse(f"sinnix://projects/{project_id}/beads/{task_id}"))


def task_reconcile_main(argv: list[str] | None = None) -> int:
    """Internal fixed runner. Its caller holds the daemon project lock."""

    parser = argparse.ArgumentParser(prog="sinnixd-task-reconcile")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--task-state-root", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if not _ID_RE.fullmatch(arguments.project_id) or not arguments.project_root.is_absolute() or not arguments.task_state_root.is_absolute():
        parser.error("project ID and paths are invalid")
    try:
        authority = TaskAuthority.load(arguments.task_state_root, arguments.project_id)
        journal = TaskMutationJournal(authority.root / TASK_MUTATION_JOURNAL_DIRECTORY)
        receipts = reconcile_task_mutations(journal=journal, authority=authority, cwd=arguments.project_root, boundary=BeadsCommandBoundary())
        sync = _run_task_command(BeadsCommandBoundary(), authority, arguments.project_root, ("sync", "--no-adopt"), readonly=False)
    except TaskError as error:
        print(json.dumps({"state": "failed", "code": error.code.value}, sort_keys=True))
        return 1
    print(json.dumps({"state": "applied", "mutations": list(receipts), "sync_sha256": TaskMutationIdentity.digest(json.dumps(sync, sort_keys=True, separators=(",", ":")))}, sort_keys=True))
    return 0
