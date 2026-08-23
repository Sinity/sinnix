from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Iterator, Protocol
from uuid import UUID, uuid4

from .projects import ProjectAdapter, ProjectOperation, RegisteredCheckout

DEFAULT_TIMEOUT_SECONDS = 3_600
DEFAULT_WAIT_SECONDS = 30
MAX_WAIT_SECONDS = 300
SYSTEMD_COMMAND_TIMEOUT_SECONDS = 0.25
MAX_LOG_BYTES = 64_000
MAX_LOG_ARTIFACT_BYTES = 1_048_576
MAX_RESULT_BYTES = 64_000
JOB_SCHEMA_VERSION = 3
JOB_UNIT_PREFIX = "sinnixd-job-"
SYSTEMD_ERROR_CODE = "systemd-job-error"


def default_state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "sinnixd"


class SystemdJobError(RuntimeError):
    """Raised when systemd cannot create or inspect a transient job service."""


class JobRecordError(ValueError):
    """Raised when a persisted job record cannot be reconstructed safely."""


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_durable_directory(path: Path) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            raise OSError(f"could not find an existing parent for {path}")
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            continue
        _fsync_directory(directory.parent)


class SystemdJobs(Protocol):
    """The systemd boundary for every durable Sinnixd job."""

    def start(
        self,
        *,
        unit: str,
        command: Sequence[str],
        working_directory: str,
        environment: Mapping[str, str],
        timeout_seconds: int,
        log_path: Path,
    ) -> None: ...

    def show(
        self,
        unit: str,
        *,
        timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ) -> Mapping[str, str]: ...

    def stop(self, unit: str) -> None: ...


@dataclass(frozen=True)
class UserSystemdJobs:
    """Launch and inspect transient user services through the user manager."""

    def start(
        self,
        *,
        unit: str,
        command: Sequence[str],
        working_directory: str,
        environment: Mapping[str, str],
        timeout_seconds: int,
        log_path: Path,
    ) -> None:
        args = [
            "systemd-run",
            "--user",
            "--quiet",
            f"--unit={unit}",
            "--slice=agent.slice",
            f"--property=WorkingDirectory={working_directory}",
            f"--property=RuntimeMaxSec={timeout_seconds}s",
            "--property=StandardOutput=journal",
            "--property=StandardError=journal",
            "--",
            str(capture_executable()),
            "--log-path",
            str(log_path),
            "--overflow-path",
            str(log_path.with_suffix(".overflow")),
            "--max-bytes",
            str(MAX_LOG_ARTIFACT_BYTES),
            "--",
            "/run/current-system/sw/bin/env",
            "-i",
        ]
        args.extend(f"{key}={value}" for key, value in sorted(environment.items()))
        args.extend(command)
        self._run(args)

    def show(
        self,
        unit: str,
        *,
        timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ) -> Mapping[str, str]:
        output = self._run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=LoadState",
                "--property=ActiveState",
                "--property=SubState",
                "--property=MainPID",
                "--property=Result",
                "--property=ExecMainCode",
                "--property=ExecMainStatus",
                "--property=ControlGroup",
                "--property=InvocationID",
            ],
            timeout_seconds=timeout_seconds,
        )
        return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)

    def stop(self, unit: str) -> None:
        self._run(["systemctl", "--user", "stop", unit])

    @staticmethod
    def _run(args: Sequence[str], *, timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS) -> str:
        timeout_seconds = min(timeout_seconds, SYSTEMD_COMMAND_TIMEOUT_SECONDS)
        if timeout_seconds <= 0:
            raise ValueError("systemd command timeout must be positive")
        try:
            result = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as error:
            raise SystemdJobError(f"systemd command is unavailable: {args[0]}") from error
        except subprocess.TimeoutExpired as error:
            raise SystemdJobError("systemd command timed out") from error
        except OSError as error:
            raise SystemdJobError(f"systemd command failed: {args[0]}: {error}") from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.strip() or error.stdout.strip() or str(error)
            raise SystemdJobError(detail) from error
        return result.stdout


def job_unit_name(job_id: str) -> str:
    try:
        parsed = UUID(job_id)
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("job_id must be a UUID") from error
    return f"{JOB_UNIT_PREFIX}{parsed}.service"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class GenericJobSpec:
    """Reconstructible launch metadata for one systemd-owned job."""

    kind: str
    command: tuple[str, ...]
    working_directory: str
    environment: Mapping[str, str]
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    project_id: str | None = None
    operation: str | None = None
    environment_keys: tuple[str, ...] = ()
    command_digest: str | None = None
    principal: str | None = None
    checkout: Mapping[str, str] | None = None
    contract: Mapping[str, Any] = field(default_factory=dict)
    result_kind: str = "exit-status"

    def __post_init__(self) -> None:
        if self.kind not in {"declared-operation", "foreground-command", "operator-shell", "attested-agent"}:
            raise ValueError("job kind is invalid")
        if not self.command and not self.command_digest:
            raise ValueError("job needs a launch command or command digest")
        if self.command and any(not isinstance(value, str) or not value for value in self.command):
            raise ValueError("job command must be non-empty strings")
        if self.command_digest is not None and (
            len(self.command_digest) != 64 or any(value not in "0123456789abcdef" for value in self.command_digest)
        ):
            raise ValueError("job command digest is invalid")
        if not isinstance(self.working_directory, str) or not self.working_directory:
            raise ValueError("job working_directory must be non-empty")
        if not 1 <= self.timeout_seconds <= DEFAULT_TIMEOUT_SECONDS:
            raise ValueError(f"job timeout_seconds must be between 1 and {DEFAULT_TIMEOUT_SECONDS}")
        if any(
            not isinstance(key, str) or not key or not isinstance(value, str)
            for key, value in self.environment.items()
        ):
            raise ValueError("job environment must be string key/value pairs")
        if any(not isinstance(key, str) or not key for key in self.environment_keys):
            raise ValueError("job environment metadata must be non-empty strings")
        if self.principal is not None and self.principal not in {"operator", "agent-control"}:
            raise ValueError("job principal is invalid")
        if self.kind == "operator-shell" and self.principal != "operator":
            raise ValueError("operator shell jobs require the operator principal")
        if self.kind == "attested-agent" and self.principal != "agent-control":
            raise ValueError("attested agent jobs require the agent-control principal")
        if self.kind in {"operator-shell", "attested-agent"} and not self.checkout:
            raise ValueError("typed jobs require a registered checkout")
        if self.checkout is not None and (
            set(self.checkout) != {"project_id", "project_path", "checkout_id", "path", "git_common_dir", "head"}
            or any(not isinstance(value, str) or not value for value in self.checkout.values())
        ):
            raise ValueError("job checkout identity is invalid")
        if not isinstance(self.contract, Mapping) or any(not isinstance(key, str) or not key for key in self.contract):
            raise ValueError("job contract is invalid")
        if self.result_kind not in {"exit-status", "last-message"}:
            raise ValueError("job result kind is invalid")
        if self.kind == "operator-shell" and self.result_kind != "exit-status":
            raise ValueError("operator shell jobs only support exit-status results")
        if self.kind == "attested-agent" and self.result_kind != "last-message":
            raise ValueError("attested agent jobs require last-message results")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "working_directory": self.working_directory,
            "environment_keys": sorted(set(self.environment) | set(self.environment_keys)),
            "timeout_seconds": self.timeout_seconds,
            "project_id": self.project_id,
            "operation": self.operation,
            "principal": self.principal,
            "checkout": dict(self.checkout) if self.checkout is not None else None,
            "contract": dict(self.contract),
            "result_kind": self.result_kind,
        }
        if self.kind != "declared-operation":
            result["command"] = {
                "digest": self.command_digest or _command_digest(self.command),
                "display": "synthetic foreground command" if self.kind == "foreground-command" else f"{self.kind} contract runner",
            }
        else:
            result["command"] = {
                "display": "declared project operation",
            }
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> GenericJobSpec:
        command = value.get("command")
        environment_keys = value.get("environment_keys")
        if not isinstance(command, Mapping) or not isinstance(environment_keys, list) or any(
            not isinstance(key, str) or not key for key in environment_keys
        ):
            raise JobRecordError("job spec has invalid command or environment metadata")
        kind = value.get("kind")
        digest = command.get("digest")
        if kind != "declared-operation" and not isinstance(digest, str):
            raise JobRecordError("non-declared job spec requires a command digest")
        if kind == "declared-operation":
            digest = "0" * 64
        try:
            return cls(
                kind=kind,
                command=(),
                working_directory=value.get("working_directory"),
                environment={},
                timeout_seconds=value.get("timeout_seconds"),
                project_id=value.get("project_id"),
                operation=value.get("operation"),
                environment_keys=tuple(environment_keys),
                command_digest=digest,
                principal=value.get("principal"),
                checkout=value.get("checkout"),
                contract=value.get("contract", {}),
                result_kind=value.get("result_kind", "exit-status"),
            )
        except ValueError as error:
            raise JobRecordError(str(error)) from error


@dataclass(frozen=True)
class GenericJobRecord:
    job_id: str
    unit: str
    spec: GenericJobSpec
    log_path: Path
    result_path: Path | None
    created_at: str
    cancel_requested_at: str | None = None
    cancel_requested_invocation_id: str | None = None
    cancel_stop_acknowledged_at: str | None = None
    cancel_stop_acknowledged_invocation_id: str | None = None
    state: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": JOB_SCHEMA_VERSION,
            "job_id": self.job_id,
            "unit": self.unit,
            "spec": self.spec.to_dict(),
            "artifacts": {
                "log": str(self.log_path),
                "result": str(self.result_path) if self.result_path is not None else None,
            },
            "created_at": self.created_at,
            "cancel_requested_at": self.cancel_requested_at,
            "cancel_requested_invocation_id": self.cancel_requested_invocation_id,
            "cancel_stop_acknowledged_at": self.cancel_stop_acknowledged_at,
            "cancel_stop_acknowledged_invocation_id": self.cancel_stop_acknowledged_invocation_id,
            "state": dict(self.state),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], root: Path) -> GenericJobRecord:
        job_id = value.get("job_id")
        unit = value.get("unit")
        artifacts = value.get("artifacts")
        if value.get("schema_version") not in {2, JOB_SCHEMA_VERSION} or not isinstance(job_id, str):
            raise JobRecordError("job record schema or ID is invalid")
        if unit != job_unit_name(job_id):
            raise JobRecordError("job record unit does not match its ID")
        if not isinstance(artifacts, Mapping) or not isinstance(artifacts.get("log"), str):
            raise JobRecordError("job record log artifact is invalid")
        log_path = Path(artifacts["log"]).resolve()
        logs_root = (root / "logs").resolve()
        if logs_root not in log_path.parents:
            raise JobRecordError("job log artifact escapes state root")
        raw_result = artifacts.get("result")
        result_path: Path | None = None
        if raw_result is not None:
            if not isinstance(raw_result, str):
                raise JobRecordError("job result artifact is invalid")
            result_path = Path(raw_result).resolve()
            results_root = (root / "results").resolve()
            if results_root not in result_path.parents:
                raise JobRecordError("job result artifact escapes state root")
        spec = value.get("spec")
        state = value.get("state", {})
        if not isinstance(spec, Mapping) or not isinstance(state, Mapping):
            raise JobRecordError("job record spec or state is invalid")
        created_at = value.get("created_at")
        cancelled = value.get("cancel_requested_at")
        invocation = value.get("cancel_requested_invocation_id")
        stop_acknowledged = value.get("cancel_stop_acknowledged_at")
        stop_invocation = value.get("cancel_stop_acknowledged_invocation_id")
        if (
            not isinstance(created_at, str)
            or (cancelled is not None and not isinstance(cancelled, str))
            or (invocation is not None and not isinstance(invocation, str))
            or (stop_acknowledged is not None and not isinstance(stop_acknowledged, str))
            or (stop_invocation is not None and not isinstance(stop_invocation, str))
            or (stop_acknowledged is None) != (stop_invocation is None)
            or (stop_acknowledged is not None and (cancelled is None or stop_invocation != invocation))
        ):
            raise JobRecordError("job record timestamps are invalid")
        return cls(
            job_id=job_id,
            unit=unit,
            spec=GenericJobSpec.from_dict(spec),
            log_path=log_path,
            result_path=result_path,
            created_at=created_at,
            cancel_requested_at=cancelled,
            cancel_requested_invocation_id=invocation,
            cancel_stop_acknowledged_at=stop_acknowledged,
            cancel_stop_acknowledged_invocation_id=stop_invocation,
            state=dict(state),
        )


@dataclass
class GenericJobStore:
    """Durable metadata and artifact paths, never process ownership or queues."""

    root: Path
    _locks: dict[str, RLock] = field(default_factory=dict, init=False, repr=False)
    _locks_guard: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def records_root(self) -> Path:
        return self.root / "jobs"

    @property
    def logs_root(self) -> Path:
        return self.root / "logs"

    @property
    def results_root(self) -> Path:
        return self.root / "results"

    def create(self, spec: GenericJobSpec, job_id: str | None = None) -> GenericJobRecord:
        _ensure_durable_directory(self.records_root)
        _ensure_durable_directory(self.logs_root)
        if spec.result_kind == "last-message":
            _ensure_durable_directory(self.results_root)
        candidates = (job_id,) if job_id is not None else tuple(str(uuid4()) for _ in range(8))
        for candidate in candidates:
            _ = job_unit_name(candidate)
            path = self._record_path(candidate)
            if path.exists():
                continue
            log_path = self.logs_root / f"{candidate}.log"
            try:
                log_path.touch(mode=0o600, exist_ok=False)
            except FileExistsError:
                continue
            _fsync_directory(self.logs_root)
            result_path = self.results_root / f"{candidate}.result" if spec.result_kind == "last-message" else None
            record = GenericJobRecord(
                job_id=candidate,
                unit=job_unit_name(candidate),
                spec=spec,
                log_path=log_path.resolve(),
                result_path=result_path.resolve() if result_path is not None else None,
                created_at=_timestamp(),
                state={"phase": "launching", "terminal": False, "observed_at": _timestamp()},
            )
            self.save(record)
            return record
        raise JobRecordError("could not allocate a unique job ID")

    @contextmanager
    def locked(self, job_id: str) -> Iterator[None]:
        _ = job_unit_name(job_id)
        with self._locks_guard:
            lock = self._locks.setdefault(job_id, RLock())
        with lock:
            yield

    def load(self, job_id: str) -> GenericJobRecord:
        path = self._record_path(job_id)
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError as error:
            raise JobRecordError(f"unknown job: {job_id}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise JobRecordError(f"malformed job record: {job_id}") from error
        if not isinstance(value, Mapping):
            raise JobRecordError(f"malformed job record: {job_id}")
        return GenericJobRecord.from_dict(value, self.root)

    def list(self) -> list[GenericJobRecord]:
        if not self.records_root.exists():
            return []
        records: list[GenericJobRecord] = []
        for path in sorted(self.records_root.glob("*.json")):
            try:
                records.append(self.load(path.stem))
            except JobRecordError:
                continue
        return records

    def save(self, record: GenericJobRecord) -> None:
        path = self._record_path(record.job_id)
        _ensure_durable_directory(path.parent)
        temporary = path.with_suffix(".json.tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(record.to_dict(), handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            _fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def _record_path(self, job_id: str) -> Path:
        _ = job_unit_name(job_id)
        return self.records_root / f"{job_id}.json"


@dataclass
class GenericJobs:
    """Common durable job route for declared operations and foreground commands."""

    systemd: SystemdJobs
    store: GenericJobStore
    wait_poll_seconds: float = 0.1

    def start(self, spec: GenericJobSpec, job_id: str | None = None) -> dict[str, Any]:
        candidate = job_id or str(uuid4())
        with self.store.locked(candidate):
            record = self.store.create(spec, candidate)
            try:
                self.systemd.start(
                    unit=record.unit,
                    command=spec.command,
                    working_directory=spec.working_directory,
                    environment=spec.environment,
                    timeout_seconds=spec.timeout_seconds,
                    log_path=record.log_path,
                )
            except SystemdJobError:
                return self._reconcile_launch_error(record)
            submitted = self._with_state(record, {"phase": "submitted", "terminal": False, "observed_at": _timestamp()})
            self.store.save(submitted)
            return self._public(submitted, submitted.state)

    def start_declared(
        self,
        *,
        project: ProjectAdapter,
        operation: ProjectOperation,
        correlation_id: str,
        checkout: RegisteredCheckout | None = None,
    ) -> dict[str, Any]:
        if checkout is not None and checkout.project_id != project.project_id:
            raise ValueError("declared job checkout belongs to another project")
        job_id = str(uuid4())
        environment = project.environment.values()
        environment.update(
            {
                "SINNIXD_JOB_ID": job_id,
                "SINNIXD_CORRELATION_ID": correlation_id,
                "SINNIXD_PROJECT_ID": project.project_id,
                "SINNIXD_OPERATION": operation.name,
            }
        )
        if checkout is not None:
            environment.update(
                {
                    "SINNIXD_CHECKOUT_ID": checkout.checkout_id,
                    "SINNIXD_CHECKOUT_HEAD": checkout.head,
                }
            )
        return self.start(
            GenericJobSpec(
                kind="declared-operation",
                command=(*project.environment.command, *operation.command),
                working_directory=str(checkout.path if checkout is not None else project.root),
                environment=environment,
                project_id=project.project_id,
                operation=operation.name,
                checkout=checkout.to_dict() if checkout is not None else None,
            ),
            job_id,
        )

    def start_foreground(
        self,
        *,
        command: Sequence[str],
        working_directory: str,
        environment: Mapping[str, str],
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        job_id = str(uuid4())
        job_environment = dict(environment)
        job_environment["SINNIXD_JOB_ID"] = job_id
        return self.start(
            GenericJobSpec(
                kind="foreground-command",
                command=tuple(command),
                working_directory=working_directory,
                environment=job_environment,
                timeout_seconds=timeout_seconds,
            ),
            job_id,
        )

    def get(self, job_id: str) -> dict[str, Any]:
        with self.store.locked(job_id):
            return self._get_locked(job_id)

    def list(self) -> dict[str, Any]:
        return {"jobs": [self.get(record.job_id) for record in self.store.list()]}

    def wait(self, job_id: str, timeout_seconds: int = DEFAULT_WAIT_SECONDS) -> dict[str, Any]:
        if not 1 <= timeout_seconds <= MAX_WAIT_SECONDS:
            raise ValueError(f"wait timeout_seconds must be between 1 and {MAX_WAIT_SECONDS}")
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with self.store.locked(job_id):
                    record = self.store.load(job_id)
                    return {**self._public(record, record.state), "wait_timed_out": True}
            with self.store.locked(job_id):
                status = self._get_locked(
                    job_id,
                    systemd_timeout_seconds=min(SYSTEMD_COMMAND_TIMEOUT_SECONDS, remaining),
                )
            if status["state"]["terminal"]:
                return status
            if time.monotonic() >= deadline:
                return {**status, "wait_timed_out": True}
            time.sleep(min(self.wait_poll_seconds, max(0.0, deadline - time.monotonic())))

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self.store.locked(job_id):
            status = self._get_locked(job_id)
            if status["state"]["terminal"]:
                return {**status, "cancel_requested": False, "already_terminal": True}
            record = self.store.load(job_id)
            intent = self._with_cancel_intent(record, status["state"].get("systemd", {}).get("InvocationID"))
            self.store.save(intent)
            self.systemd.stop(intent.unit)
            acknowledged = self._with_stop_acknowledgement(
                intent,
                status["state"].get("systemd", {}).get("InvocationID"),
            )
            self.store.save(acknowledged)
            reconciled = self._get_locked(job_id)
            return {**reconciled, "cancel_requested": True, "already_terminal": False}

    def logs(self, job_id: str, *, offset: int = 0, max_bytes: int = MAX_LOG_BYTES) -> dict[str, Any]:
        if offset < 0 or not 1 <= max_bytes <= MAX_LOG_BYTES:
            raise ValueError(f"log range must use offset >= 0 and max_bytes between 1 and {MAX_LOG_BYTES}")
        with self.store.locked(job_id):
            record = self.store.load(job_id)
        try:
            with record.log_path.open("rb") as handle:
                handle.seek(offset)
                content = handle.read(max_bytes + 1)
        except FileNotFoundError:
            content = b""
        overflowed = record.log_path.with_suffix(".overflow").exists()
        return {
            "job_id": job_id,
            "offset": offset,
            "content": content[:max_bytes].decode(errors="replace"),
            "next_offset": offset + min(len(content), max_bytes),
            "truncated": len(content) > max_bytes,
            "artifact_truncated": overflowed,
        }

    def result(self, job_id: str, *, max_bytes: int = MAX_RESULT_BYTES) -> dict[str, Any]:
        if not 1 <= max_bytes <= MAX_RESULT_BYTES:
            raise ValueError(f"result max_bytes must be between 1 and {MAX_RESULT_BYTES}")
        with self.store.locked(job_id):
            record = self.store.load(job_id)
        if record.result_path is None:
            raise ValueError("job has no result artifact")
        try:
            with record.result_path.open("rb") as handle:
                content = handle.read(max_bytes + 1)
        except FileNotFoundError:
            content = b""
        return {
            "job_id": job_id,
            "kind": record.spec.result_kind,
            "content": content[:max_bytes].decode(errors="replace"),
            "truncated": len(content) > max_bytes,
            "artifact": {"ref": f"sinnix://jobs/{job_id}/artifacts/result", "max_bytes": MAX_RESULT_BYTES},
        }

    def _get_locked(
        self,
        job_id: str,
        *,
        systemd_timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        record = self.store.load(job_id)
        if record.state.get("terminal"):
            return self._public(record, record.state)
        try:
            properties = dict(
                self.systemd.show(record.unit, timeout_seconds=systemd_timeout_seconds)
            )
        except SystemdJobError:
            state = {
                "phase": "launch-unknown" if record.state.get("phase") == "launch-unknown" else "lost",
                "error": {"code": SYSTEMD_ERROR_CODE},
                "terminal": record.state.get("phase") != "launch-unknown",
                "observed_at": _timestamp(),
            }
        else:
            state = self._classify(properties, record)
        updated = self._with_state(record, state)
        self.store.save(updated)
        return self._public(updated, state)

    def _reconcile_launch_error(self, record: GenericJobRecord) -> dict[str, Any]:
        try:
            properties = dict(self.systemd.show(record.unit))
        except SystemdJobError:
            state = {
                "phase": "launch-unknown",
                "error": {"code": SYSTEMD_ERROR_CODE},
                "terminal": False,
                "observed_at": _timestamp(),
            }
            updated = self._with_state(record, state)
            self.store.save(updated)
            return self._public(updated, state)
        if properties.get("LoadState") == "not-found":
            state = {
                "phase": "launch-failed",
                "error": {"code": SYSTEMD_ERROR_CODE},
                "terminal": True,
                "observed_at": _timestamp(),
            }
            updated = self._with_state(record, state)
            self.store.save(updated)
            return self._public(updated, state)
        state = self._classify(properties, record)
        updated = self._with_state(record, state)
        self.store.save(updated)
        return self._public(updated, state)

    def _classify(self, properties: Mapping[str, str], record: GenericJobRecord) -> dict[str, Any]:
        if properties.get("LoadState") != "loaded":
            if record.state.get("phase") == "launch-unknown":
                return {
                    "phase": "launch-failed",
                    "error": {"code": SYSTEMD_ERROR_CODE},
                    "terminal": True,
                    "systemd": dict(properties),
                    "observed_at": _timestamp(),
                }
            if self._stop_acknowledgement_matches(record):
                return {
                    "phase": "cancelled",
                    "terminal": True,
                    "systemd": dict(properties),
                    "cancellation": self._stop_acknowledgement(record),
                    "observed_at": _timestamp(),
                }
            if properties.get("Result") == "success" and properties.get("ExecMainStatus", "0") == "0":
                return {
                    "phase": "succeeded",
                    "terminal": True,
                    "systemd": dict(properties),
                    "observed_at": _timestamp(),
                }
            return {"phase": "missing", "terminal": True, "systemd": dict(properties), "observed_at": _timestamp()}
        active = properties.get("ActiveState", "unknown")
        if active in {"active", "activating", "reloading"}:
            phase = "running"
            terminal = False
        elif active == "deactivating":
            phase = "cancelling" if record.cancel_requested_at is not None else "stopping"
            terminal = False
        elif properties.get("Result") == "success" and properties.get("ExecMainStatus", "0") == "0":
            phase = "succeeded"
            terminal = True
        elif properties.get("Result") == "timeout":
            phase = "timed_out"
            terminal = True
        elif self._cancel_matches(properties, record):
            phase = "cancelled"
            terminal = True
        else:
            phase = "failed"
            terminal = True
        return {"phase": phase, "terminal": terminal, "systemd": dict(properties), "observed_at": _timestamp()}

    @staticmethod
    def _with_state(record: GenericJobRecord, state: Mapping[str, Any]) -> GenericJobRecord:
        return GenericJobRecord(
            job_id=record.job_id,
            unit=record.unit,
            spec=record.spec,
            log_path=record.log_path,
            result_path=record.result_path,
            created_at=record.created_at,
            cancel_requested_at=record.cancel_requested_at,
            cancel_requested_invocation_id=record.cancel_requested_invocation_id,
            cancel_stop_acknowledged_at=record.cancel_stop_acknowledged_at,
            cancel_stop_acknowledged_invocation_id=record.cancel_stop_acknowledged_invocation_id,
            state=dict(state),
        )

    @staticmethod
    def _with_cancel_intent(record: GenericJobRecord, invocation_id: Any) -> GenericJobRecord:
        return GenericJobRecord(
            job_id=record.job_id,
            unit=record.unit,
            spec=record.spec,
            log_path=record.log_path,
            result_path=record.result_path,
            created_at=record.created_at,
            cancel_requested_at=record.cancel_requested_at or _timestamp(),
            cancel_requested_invocation_id=invocation_id if isinstance(invocation_id, str) else None,
            cancel_stop_acknowledged_at=record.cancel_stop_acknowledged_at,
            cancel_stop_acknowledged_invocation_id=record.cancel_stop_acknowledged_invocation_id,
            state=dict(record.state),
        )

    @staticmethod
    def _with_stop_acknowledgement(record: GenericJobRecord, invocation_id: Any) -> GenericJobRecord:
        invocation = invocation_id if isinstance(invocation_id, str) else None
        if invocation is None or invocation != record.cancel_requested_invocation_id:
            return record
        return GenericJobRecord(
            job_id=record.job_id,
            unit=record.unit,
            spec=record.spec,
            log_path=record.log_path,
            result_path=record.result_path,
            created_at=record.created_at,
            cancel_requested_at=record.cancel_requested_at,
            cancel_requested_invocation_id=record.cancel_requested_invocation_id,
            cancel_stop_acknowledged_at=_timestamp(),
            cancel_stop_acknowledged_invocation_id=invocation,
            state=dict(record.state),
        )

    @staticmethod
    def _cancel_matches(properties: Mapping[str, str], record: GenericJobRecord) -> bool:
        if record.cancel_requested_at is None:
            return False
        invocation = properties.get("InvocationID")
        return (
            isinstance(invocation, str)
            and invocation == record.cancel_requested_invocation_id
            and properties.get("Result") == "signal"
        )

    @staticmethod
    def _stop_acknowledgement_matches(record: GenericJobRecord) -> bool:
        return (
            record.cancel_stop_acknowledged_at is not None
            and record.cancel_stop_acknowledged_invocation_id is not None
            and record.cancel_stop_acknowledged_invocation_id == record.cancel_requested_invocation_id
        )

    @staticmethod
    def _stop_acknowledgement(record: GenericJobRecord) -> dict[str, str]:
        assert record.cancel_stop_acknowledged_at is not None
        assert record.cancel_stop_acknowledged_invocation_id is not None
        return {
            "stop_acknowledged_at": record.cancel_stop_acknowledged_at,
            "invocation_id": record.cancel_stop_acknowledged_invocation_id,
        }

    @staticmethod
    def _public(record: GenericJobRecord, state: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "unit": record.unit,
            "kind": record.spec.kind,
            "project_id": record.spec.project_id,
            "operation": record.spec.operation,
            "principal": record.spec.principal,
            "checkout": dict(record.spec.checkout) if record.spec.checkout is not None else None,
            "contract": dict(record.spec.contract),
            "created_at": record.created_at,
            "timeout_seconds": record.spec.timeout_seconds,
            "artifacts": {
                "log": {"ref": f"sinnix://jobs/{record.job_id}/artifacts/log", "max_bytes": MAX_LOG_BYTES},
                "result": (
                    {"ref": f"sinnix://jobs/{record.job_id}/artifacts/result", "max_bytes": MAX_RESULT_BYTES}
                    if record.result_path is not None
                    else None
                ),
            },
            "state": dict(state),
        }


def _command_digest(command: Sequence[str]) -> str:
    return hashlib.sha256("\0".join(command).encode()).hexdigest()


def capture_executable() -> Path:
    module_path = Path(__file__).resolve()
    if len(module_path.parents) > 4 and module_path.parents[3].name == "lib":
        return module_path.parents[4] / "bin" / "sinnixd-capture"
    return Path(sys.executable).with_name("sinnixd-capture")


def capture_main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-capture")
    parser.add_argument("--log-path", type=Path, required=True)
    parser.add_argument("--overflow-path", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(arguments)
    if not parsed.command or parsed.command[0] != "--" or not 1 <= parsed.max_bytes <= MAX_LOG_ARTIFACT_BYTES:
        parser.error("requires --max-bytes within the artifact cap and a command after --")
    command = parsed.command[1:]
    parsed.log_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parsed.overflow_path.unlink(missing_ok=True)
    remaining = parsed.max_bytes
    overflowed = False
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdout is not None
    with parsed.log_path.open("wb") as handle:
        while chunk := process.stdout.read1(65_536):
            accepted = b""
            if remaining:
                accepted = chunk[:remaining]
                handle.write(accepted)
                remaining -= len(accepted)
            if len(chunk) > len(accepted) and not overflowed:
                parsed.overflow_path.touch(mode=0o600)
                overflowed = True
        handle.flush()
        os.fsync(handle.fileno())
    return process.wait()


def capture_cli() -> None:
    raise SystemExit(capture_main())


if __name__ == "__main__":
    raise SystemExit(capture_main(sys.argv[2:] if len(sys.argv) > 1 and sys.argv[1] == "capture" else None))
