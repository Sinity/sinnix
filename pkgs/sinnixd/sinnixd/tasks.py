from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
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
MAX_TASK_MUTATION_INTENT_BYTES = 64_000
MAX_TASK_MUTATION_RECORD_BYTES = 8_192
MAX_TASK_MUTATION_RECORDS = 1_024
TASK_TIMEOUT_SECONDS = 30
TASK_RECONCILE_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
FLOCK_EXECUTABLE = "/run/current-system/sw/bin/flock"
DEFAULT_TASK_STATE_ROOT = Path("/realm/state/tasks")
TASK_AUTHORITY_RECEIPT = "authority.json"
TASK_MUTATION_JOURNAL_DIRECTORY = "sinnixd-task-mutations"
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
    def run(self, *, argv: tuple[str, ...], cwd: Path, environment: dict[str, str], lock_path: Path | None = None) -> ExecutionResult: ...


@dataclass(frozen=True)
class BeadsCommandBoundary:
    execution: OwnerExecution = field(default_factory=OwnerExecution)
    executable: str = "bd"

    def run(self, *, argv: tuple[str, ...], cwd: Path, environment: dict[str, str], lock_path: Path | None = None) -> ExecutionResult:
        command = (self.executable, *argv) if lock_path is None else (FLOCK_EXECUTABLE, "--exclusive", str(lock_path), self.executable, *argv)
        return self.execution.run(
            command,
            ExecutionProfile(route=OwnerRoute("task-backend"), timeout_seconds=TASK_TIMEOUT_SECONDS, max_stdout_bytes=MAX_TASK_OUTPUT_BYTES, max_stderr_bytes=MAX_TASK_STDERR_BYTES, max_combined_output_bytes=MAX_TASK_OUTPUT_BYTES + MAX_TASK_STDERR_BYTES, cwd=cwd, environment=environment),
        )


def _run_task_command(boundary: TaskCommandBoundary, authority: TaskAuthority, cwd: Path, command: tuple[str, ...], *, readonly: bool, json_lines: bool = False) -> Any:
    result = boundary.run(argv=("--json", *(("--readonly",) if readonly else ()), *command), cwd=cwd, environment={"BEADS_DIR": str(authority.root / ".beads")})
    if result.timed_out or result.failure_class == "command_timeout":
        raise TaskError(ErrorCode.OWNER_UNAVAILABLE, "task backend timed out")
    if result.output_exceeded or result.failure_class == "command_output_bound" or len(result.stdout) > MAX_TASK_OUTPUT_BYTES or len(result.stderr) > MAX_TASK_STDERR_BYTES:
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
            return self._execute(project, operation, arguments)
        with self._lock_for(project.project_id), flock(self._lock_path(project)):
            if operation in _IDEMPOTENT_MUTATIONS:
                return self._submit_mutation(project, operation, arguments, self._mutation_id(mutation_id))
            return self._execute(project, operation, arguments)

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

    def _execute(self, project: ProjectAdapter, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if operation == "task.list":
            result = self._run(project, self._list_command(arguments), readonly=True)
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

    def _run(self, project: ProjectAdapter, command: tuple[str, ...], *, readonly: bool, json_lines: bool = False) -> Any:
        return _run_task_command(self.boundary, self._authority(project), project.root, command, readonly=readonly, json_lines=json_lines)

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

    def _list_command(self, arguments: dict[str, Any]) -> tuple[str, ...]:
        self._require_allowed(arguments, {"project_id", "status", "assignee", "label", "limit", "include_closed", "ready"}, {"project_id"}, "task.list")
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
