from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import selectors
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from collections.abc import Callable, Mapping, Sequence
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
JOB_SCHEMA_VERSION = 4
JOB_UNIT_PREFIX = "sinnixd-job-"
SYSTEMD_ERROR_CODE = "systemd-job-error"
ADMISSION_SCHEMA_VERSION = 1
MAX_ADMISSION_CACHE_ENTRIES = 128
MAX_ADMISSION_ESTIMATES = 128
MIB = 1024 * 1024
POOL_POLICIES = {
    "interactive": {"workers": 4, "memory_budget": 3 * 1024 * MIB, "default_estimate": 256 * MIB},
    "normal": {"workers": 3, "memory_budget": 8 * 1024 * MIB, "default_estimate": 1024 * MIB},
    "bulk": {"workers": 1, "memory_budget": 18 * 1024 * MIB, "default_estimate": 8 * 1024 * MIB},
}


def default_state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "sinnixd"


class SystemdJobError(RuntimeError):
    """Raised when systemd cannot create or inspect a transient job service."""


class SystemdJobTimeout(SystemdJobError):
    """Raised only when the bounded systemd subprocess times out."""


class JobRecordError(ValueError):
    """Raised when a persisted job record cannot be reconstructed safely."""


class JobResultError(ValueError):
    """Raised when a declared result artifact is unavailable or invalid."""


class JobResultLimitError(JobResultError):
    """Raised when a valid declared result exceeds the caller's response bound."""


def _open_private_parent(path: Path) -> int:
    """Open and validate the private directory holding one capture artifact."""
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_descriptor = os.open(path.parent, directory_flags)
    parent = os.fstat(parent_descriptor)
    if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
        os.close(parent_descriptor)
        raise PermissionError(f"artifact parent is not private: {path.parent}")
    return parent_descriptor


def _private_regular_artifact(descriptor: int, path: Path, *, require_private_mode: bool = True) -> None:
    artifact = os.fstat(descriptor)
    if (
        artifact.st_uid != os.getuid()
        or (require_private_mode and artifact.st_mode & 0o077)
        or not stat.S_ISREG(artifact.st_mode)
        or artifact.st_nlink != 1
    ):
        raise PermissionError(f"capture artifact is not private: {path}")


def _open_private_artifact(path: Path) -> Any:
    """Create one capture artifact without following a same-user symlink."""
    parent_descriptor = _open_private_parent(path)
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_descriptor,
        )
    finally:
        os.close(parent_descriptor)
    try:
        _private_regular_artifact(descriptor, path)
    except BaseException:
        os.close(descriptor)
        raise
    return os.fdopen(descriptor, "wb")


def _open_preallocated_private_artifact(path: Path) -> Any:
    """Open the store-reserved log artifact without accepting a replacement link."""
    parent_descriptor = _open_private_parent(path)
    try:
        descriptor = os.open(path.name, os.O_WRONLY | os.O_NOFOLLOW, dir_fd=parent_descriptor)
    finally:
        os.close(parent_descriptor)
    try:
        _private_regular_artifact(descriptor, path)
        os.ftruncate(descriptor, 0)
    except BaseException:
        os.close(descriptor)
        raise
    return os.fdopen(descriptor, "wb")


def _read_private_artifact(path: Path, max_bytes: int, *, offset: int = 0) -> bytes | None:
    """Read one bounded, private regular artifact without following a replacement link."""
    try:
        parent_descriptor = _open_private_parent(path)
    except OSError:
        return None
    try:
        try:
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_descriptor)
        except OSError:
            return None
        try:
            _private_regular_artifact(descriptor, path, require_private_mode=False)
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                handle.seek(offset)
                return handle.read(max_bytes + 1)
        except OSError:
            return None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    finally:
        os.close(parent_descriptor)


def _write_private_marker(path: Path) -> None:
    with _open_private_artifact(path) as handle:
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


def _completion_marker_path(log_path: Path) -> Path:
    return log_path.with_suffix(".complete")


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
        json_result_path: Path | None = None,
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
        json_result_path: Path | None = None,
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
        ]
        if json_result_path is not None:
            args.extend(
                [
                    "--result-path",
                    str(json_result_path),
                    "--result-overflow-path",
                    str(json_result_path.with_suffix(".overflow")),
                ]
            )
        args.extend(["--", "/run/current-system/sw/bin/env", "-i"])
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
                "--property=MemoryPeak",
            ],
            timeout_seconds=timeout_seconds,
        )
        properties: dict[str, str] = {}
        for line in output.splitlines():
            key, separator, value = line.partition("=")
            if not key or not separator:
                raise SystemdJobError("systemd show output is malformed")
            properties[key] = value
        if "LoadState" not in properties:
            raise SystemdJobError("systemd show output is malformed")
        return properties

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
            raise SystemdJobTimeout("systemd command timed out") from error
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


def _host_pressure() -> Mapping[str, float]:
    """Read only admission evidence; it never acts on existing cgroups."""
    values: dict[str, float] = {"memory_full_avg10": 0.0}
    try:
        for line in Path("/proc/pressure/memory").read_text().splitlines():
            if line.startswith("full "):
                for item in line.split()[1:]:
                    key, _, value = item.partition("=")
                    if key == "avg10":
                        values["memory_full_avg10"] = float(value)
    except (OSError, ValueError):
        values["memory_full_avg10"] = 1.0
    return values


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
    parameter_digest: str | None = None
    principal: str | None = None
    checkout: Mapping[str, str] | None = None
    contract: Mapping[str, Any] = field(default_factory=dict)
    result_kind: str = "exit-status"
    pool: str = "interactive"
    exclusive_keys: tuple[str, ...] = ()
    dependency_job_ids: tuple[str, ...] = ()
    cache_key: str | None = None
    estimate_key: str | None = None
    estimate_memory_bytes: int | None = None
    scratch: str = "none"

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
        if self.parameter_digest is not None and (
            len(self.parameter_digest) != 64 or any(value not in "0123456789abcdef" for value in self.parameter_digest)
        ):
            raise ValueError("job parameter digest is invalid")
        if self.kind == "declared-operation" and self.parameter_digest is None:
            raise ValueError("declared operation jobs require a parameter digest")
        if self.kind != "declared-operation" and self.parameter_digest is not None:
            raise ValueError("only declared operation jobs may have a parameter digest")
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
        if self.result_kind not in {"exit-status", "last-message", "json", "pytest"}:
            raise ValueError("job result kind is invalid")
        if self.pool not in POOL_POLICIES:
            raise ValueError("job pool is invalid")
        if any(not isinstance(key, str) or not key for key in self.exclusive_keys):
            raise ValueError("job exclusive keys are invalid")
        if len(set(self.exclusive_keys)) != len(self.exclusive_keys):
            raise ValueError("job exclusive keys must be unique")
        if any(not isinstance(value, str) or not value for value in self.dependency_job_ids):
            raise ValueError("job dependency IDs are invalid")
        if self.cache_key is not None and (len(self.cache_key) != 64 or any(value not in "0123456789abcdef" for value in self.cache_key)):
            raise ValueError("job cache key is invalid")
        if self.estimate_key is not None and (not isinstance(self.estimate_key, str) or not self.estimate_key):
            raise ValueError("job estimate key is invalid")
        if self.estimate_memory_bytes is not None and (
            not isinstance(self.estimate_memory_bytes, int) or isinstance(self.estimate_memory_bytes, bool) or self.estimate_memory_bytes < 1
        ):
            raise ValueError("job memory estimate is invalid")
        if self.scratch not in {"none", "tmpfs", "nvme"}:
            raise ValueError("job scratch is invalid")
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
            "admission": {
                "pool": self.pool,
                "exclusive_keys": list(self.exclusive_keys),
                "dependencies": list(self.dependency_job_ids),
                "cache_key": self.cache_key,
                "estimate_key": self.estimate_key,
                "estimate_memory_bytes": self.estimate_memory_bytes,
                "scratch": self.scratch,
            },
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
            result["parameters"] = {"digest": self.parameter_digest}
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, require_parameter_digest: bool = False) -> GenericJobSpec:
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
        raw_parameters = value.get("parameters")
        parameter_digest: str | None = None
        if kind == "declared-operation":
            if raw_parameters is None and not require_parameter_digest:
                parameter_digest = _parameter_digest({})
            elif not isinstance(raw_parameters, Mapping) or set(raw_parameters) != {"digest"}:
                raise JobRecordError("declared job spec has invalid parameter metadata")
            else:
                parameter_digest = raw_parameters.get("digest")
        elif raw_parameters is not None:
            raise JobRecordError("non-declared job spec has parameter metadata")
        admission = value.get("admission", {})
        if not isinstance(admission, Mapping):
            raise JobRecordError("job admission metadata is invalid")
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
                parameter_digest=parameter_digest,
                principal=value.get("principal"),
                checkout=value.get("checkout"),
                contract=value.get("contract", {}),
                result_kind=value.get("result_kind", "exit-status"),
                pool=admission.get("pool", "interactive"),
                exclusive_keys=tuple(admission.get("exclusive_keys", ())),
                dependency_job_ids=tuple(admission.get("dependencies", ())),
                cache_key=admission.get("cache_key"),
                estimate_key=admission.get("estimate_key"),
                estimate_memory_bytes=admission.get("estimate_memory_bytes"),
                scratch=admission.get("scratch", "none"),
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
    scratch_path: Path | None
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
                "scratch": str(self.scratch_path) if self.scratch_path is not None else None,
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
        schema_version = value.get("schema_version")
        if schema_version not in {2, 3, JOB_SCHEMA_VERSION} or not isinstance(job_id, str):
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
        raw_scratch = artifacts.get("scratch")
        scratch_path: Path | None = None
        if raw_scratch is not None:
            if not isinstance(raw_scratch, str):
                raise JobRecordError("job scratch artifact is invalid")
            scratch_path = Path(raw_scratch).resolve()
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
            spec=GenericJobSpec.from_dict(spec, require_parameter_digest=schema_version >= 4),
            log_path=log_path,
            result_path=result_path,
            scratch_path=scratch_path,
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

    @property
    def tmpfs_scratch_root(self) -> Path:
        configured = os.environ.get("SINNIXD_TMPFS_SCRATCH_ROOT")
        return Path(configured) if configured else Path("/dev/shm/sinnixd")

    @property
    def nvme_scratch_root(self) -> Path:
        configured = os.environ.get("SINNIXD_NVME_SCRATCH_ROOT")
        return Path(configured) if configured else Path("/realm/tmp/work/sinnixd")

    @property
    def admission_path(self) -> Path:
        return self.root / "admission.json"

    @property
    def inputs_root(self) -> Path:
        return self.root / "inputs"

    def create(self, spec: GenericJobSpec, job_id: str | None = None) -> GenericJobRecord:
        _ensure_durable_directory(self.records_root)
        _ensure_durable_directory(self.logs_root)
        if spec.result_kind in {"last-message", "json", "pytest"}:
            _ensure_durable_directory(self.results_root)
        candidates = (job_id,) if job_id is not None else tuple(str(uuid4()) for _ in range(8))
        for candidate in candidates:
            _ = job_unit_name(candidate)
            path = self._record_path(candidate)
            if path.exists():
                continue
            log_path = self.logs_root / f"{candidate}.log"
            try:
                with _open_private_artifact(log_path):
                    pass
            except FileExistsError:
                continue
            _fsync_directory(self.logs_root)
            result_path = (
                self.results_root / f"{candidate}.result"
                if spec.result_kind in {"last-message", "json", "pytest"}
                else None
            )
            scratch_path = self._allocate_scratch(spec.scratch, candidate)
            record = GenericJobRecord(
                job_id=candidate,
                unit=job_unit_name(candidate),
                spec=spec,
                log_path=log_path.resolve(),
                result_path=result_path.resolve() if result_path is not None else None,
                scratch_path=scratch_path,
                created_at=_timestamp(),
                state={"phase": "launching", "terminal": False, "observed_at": _timestamp()},
            )
            self.save(record)
            return record
        raise JobRecordError("could not allocate a unique job ID")

    def _allocate_scratch(self, kind: str, job_id: str) -> Path | None:
        if kind == "none":
            return None
        root = self.tmpfs_scratch_root if kind == "tmpfs" else self.nvme_scratch_root
        _ensure_durable_directory(root)
        path = root / job_id
        try:
            path.mkdir(mode=0o700)
        except FileExistsError as error:
            raise JobRecordError("scratch path already exists") from error
        _fsync_directory(root)
        return path.resolve()

    def cleanup_scratch(self, record: GenericJobRecord) -> None:
        if record.scratch_path is None:
            return
        root = self.tmpfs_scratch_root.resolve() if record.spec.scratch == "tmpfs" else self.nvme_scratch_root.resolve()
        path = record.scratch_path.resolve()
        if path.parent != root or path.name != record.job_id:
            raise JobRecordError("job scratch artifact escapes owned root")
        if path.exists():
            shutil.rmtree(path)
            _fsync_directory(root)

    def write_declared_launch(self, job_id: str, command: Sequence[str], environment: Mapping[str, str]) -> None:
        _ = job_unit_name(job_id)
        _ensure_durable_directory(self.inputs_root)
        path = self.inputs_root / f"{job_id}.launch"
        payload = json.dumps({"command": list(command), "environment": dict(environment)}, sort_keys=True).encode()
        with _open_private_artifact(path) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.inputs_root)

    def declared_launch(self, job_id: str) -> tuple[tuple[str, ...], dict[str, str]]:
        _ = job_unit_name(job_id)
        content = _read_private_artifact(self.inputs_root / f"{job_id}.launch", 128 * 1024)
        try:
            value = json.loads(content.decode()) if content is not None else None
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise JobRecordError("declared job launch input is invalid") from error
        if not isinstance(value, Mapping) or set(value) != {"command", "environment"}:
            raise JobRecordError("declared job launch input is invalid")
        command = value["command"]
        environment = value["environment"]
        if (
            not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command)
            or not isinstance(environment, Mapping) or any(not isinstance(key, str) or not key or not isinstance(item, str) for key, item in environment.items())
        ):
            raise JobRecordError("declared job launch input is invalid")
        return tuple(command), dict(environment)

    def cleanup_declared_launch(self, job_id: str) -> None:
        path = self.inputs_root / f"{job_id}.launch"
        path.unlink(missing_ok=True)
        if self.inputs_root.exists():
            _fsync_directory(self.inputs_root)

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
    pressure_probe: Callable[[], Mapping[str, float]] = _host_pressure
    _admission_lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        # A restart never guesses about a running process. It only removes
        # scratch already attached to a durable terminal record, then lets
        # later observations reconcile active services through systemd.
        for record in self.store.list():
            if record.state.get("terminal"):
                self.store.cleanup_scratch(record)
                if record.spec.kind == "declared-operation":
                    self.store.cleanup_declared_launch(record.job_id)

    def _admission_state(self) -> dict[str, Any]:
        path = self.store.admission_path
        if not path.exists():
            return {"schema_version": ADMISSION_SCHEMA_VERSION, "active": {}, "cache": {}, "estimates": {}}
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            # Conservatively recover by forgetting optimizations. Existing
            # records/systemd evidence still determine all real jobs.
            return {"schema_version": ADMISSION_SCHEMA_VERSION, "active": {}, "cache": {}, "estimates": {}}
        if not isinstance(value, Mapping) or value.get("schema_version") != ADMISSION_SCHEMA_VERSION:
            return {"schema_version": ADMISSION_SCHEMA_VERSION, "active": {}, "cache": {}, "estimates": {}}
        if not all(isinstance(value.get(key), Mapping) for key in ("active", "cache", "estimates")):
            return {"schema_version": ADMISSION_SCHEMA_VERSION, "active": {}, "cache": {}, "estimates": {}}
        return {"schema_version": ADMISSION_SCHEMA_VERSION, **{key: dict(value[key]) for key in ("active", "cache", "estimates")}}

    def _save_admission_state(self, value: Mapping[str, Any]) -> None:
        path = self.store.admission_path
        _ensure_durable_directory(path.parent)
        temporary = path.with_suffix(".json.tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)

    @staticmethod
    def _bounded(mapping: Mapping[str, Any], limit: int) -> dict[str, Any]:
        return dict(sorted(mapping.items(), key=lambda item: str(item[1].get("touched_at", "")) if isinstance(item[1], Mapping) else "")[-limit:])

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
                    json_result_path=record.result_path if spec.result_kind in {"json", "pytest"} else None,
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
        parameters: Mapping[str, Any],
        checkout: RegisteredCheckout | None = None,
    ) -> dict[str, Any]:
        if checkout is not None and checkout.project_id != project.project_id:
            raise ValueError("declared job checkout belongs to another project")
        with self._admission_lock:
            return self._start_declared_locked(project, operation, correlation_id, parameters, checkout, ())

    def _start_declared_locked(
        self,
        project: ProjectAdapter,
        operation: ProjectOperation,
        correlation_id: str,
        parameters: Mapping[str, Any],
        checkout: RegisteredCheckout | None,
        lineage: tuple[str, ...],
    ) -> dict[str, Any]:
        if operation.name in lineage:
            raise ValueError("declared operation dependency cycle")
        dependency_ids = tuple(
            self._start_declared_locked(project, project.operation(name), correlation_id, {}, checkout, (*lineage, operation.name))["job_id"]
            for name in operation.dependencies
        )
        operation_argv, parameter_digest = operation.derive_argv(parameters)
        workdir = checkout.path if checkout is not None else project.root
        environment = project.environment.values()
        tree = self._cache_tree(workdir)
        cache_key = self._cache_key(project, operation, parameter_digest, environment, tree)
        state = self._admission_state()
        if cache_key is not None:
            cached = state["cache"].get(cache_key)
            if isinstance(cached, Mapping) and isinstance(cached.get("job_id"), str):
                try:
                    record = self.store.load(cached["job_id"])
                except JobRecordError:
                    state["cache"].pop(cache_key, None)
                else:
                    if record.state.get("phase") == "succeeded" and record.state.get("terminal"):
                        response = self._public(record, record.state)
                        response["reused"] = True
                        return response
        if cache_key is not None:
            active_id = state["active"].get(cache_key)
            if isinstance(active_id, str):
                try:
                    record = self.store.load(active_id)
                except JobRecordError:
                    state["active"].pop(cache_key, None)
                else:
                    if not record.state.get("terminal"):
                        subscribers = int(record.state.get("subscribers", 1)) + 1
                        updated = self._with_state(record, {**record.state, "subscribers": subscribers, "coalesced": True})
                        self.store.save(updated)
                        response = self._public(updated, updated.state)
                        response["coalesced"] = True
                        return response
        job_id = str(uuid4())
        environment.update({
            "SINNIXD_JOB_ID": job_id, "SINNIXD_CORRELATION_ID": correlation_id,
            "SINNIXD_PROJECT_ID": project.project_id, "SINNIXD_OPERATION": operation.name,
        })
        if checkout is not None:
            environment.update({"SINNIXD_CHECKOUT_ID": checkout.checkout_id, "SINNIXD_CHECKOUT_HEAD": checkout.head})
        estimate_key = f"{project.project_id}:{operation.name}"
        learned = state["estimates"].get(estimate_key)
        estimate = learned.get("bytes") if isinstance(learned, Mapping) else operation.estimate_memory_bytes
        spec = GenericJobSpec(
            kind="declared-operation", command=(*project.environment.command, *operation_argv),
            working_directory=str(workdir), environment=environment, project_id=project.project_id,
            operation=operation.name, parameter_digest=parameter_digest,
            checkout=checkout.to_dict() if checkout is not None else None,
            result_kind={"exit": "exit-status", "json": "json", "pytest": "pytest"}[operation.result],
            pool=operation.pool, exclusive_keys=operation.exclusive_keys, dependency_job_ids=dependency_ids,
            cache_key=cache_key, estimate_key=estimate_key, estimate_memory_bytes=estimate,
            scratch=operation.scratch,
        )
        record = self.store.create(spec, job_id)
        try:
            self.store.write_declared_launch(job_id, spec.command, spec.environment)
        except BaseException:
            self.store.cleanup_scratch(record)
            raise
        queued = self._with_state(record, {
            "phase": "queued", "terminal": False, "observed_at": _timestamp(), "subscribers": 1,
            "dependencies": list(dependency_ids), "admission": {"pool": spec.pool, "estimate_memory_bytes": self._estimate(spec, state)},
        })
        self.store.save(queued)
        if cache_key is not None:
            state["active"][cache_key] = job_id
        self._save_admission_state(state)
        self._admit_locked()
        record = self.store.load(job_id)
        return self._public(record, record.state)

    @staticmethod
    def _cache_tree(path: Path) -> str | None:
        try:
            clean = subprocess.run(["git", "-C", str(path), "status", "--porcelain"], capture_output=True, text=True, timeout=2)
            if clean.returncode != 0 or clean.stdout:
                return None
            tree = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD^{tree}"], capture_output=True, text=True, timeout=2)
            return tree.stdout.strip() if tree.returncode == 0 and len(tree.stdout.strip()) == 40 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    @staticmethod
    def _cache_key(project: ProjectAdapter, operation: ProjectOperation, parameter_digest: str, environment: Mapping[str, str], tree: str | None) -> str | None:
        if operation.cache != "tree+environment" or tree is None:
            return None
        payload = {"project": project.project_id, "operation": operation.name, "parameters": parameter_digest, "tree": tree, "environment": dict(sorted(environment.items()))}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _estimate(spec: GenericJobSpec, state: Mapping[str, Any]) -> int:
        if spec.estimate_memory_bytes is not None:
            return spec.estimate_memory_bytes
        return POOL_POLICIES[spec.pool]["default_estimate"]

    def _admit_locked(self) -> None:
        state = self._admission_state()
        records = self.store.list()
        active: dict[str, list[GenericJobRecord]] = {pool: [] for pool in POOL_POLICIES}
        for record in records:
            if record.spec.kind == "declared-operation" and not record.state.get("terminal") and record.state.get("phase") in {"submitted", "running", "cancelling", "stopping", "launch-unknown", "observation-unknown", "outcome-unknown"}:
                active[record.spec.pool].append(record)
        pressure = self.pressure_probe()
        for record in records:
            if record.spec.kind != "declared-operation" or record.state.get("phase") not in {"queued", "waiting-dependencies"}:
                continue
            blocked = self._dependency_block(record)
            if blocked is not None:
                updated = self._with_state(record, blocked)
                self.store.save(updated)
                if blocked.get("terminal"):
                    self.store.cleanup_scratch(updated)
                    self.store.cleanup_declared_launch(updated.job_id)
                    self._finish_admission(updated, state)
                continue
            policy = POOL_POLICIES[record.spec.pool]
            estimate = self._estimate(record.spec, state)
            occupied = sum(self._estimate(item.spec, state) for item in active[record.spec.pool])
            exclusive = {key for pool_records in active.values() for item in pool_records for key in item.spec.exclusive_keys}
            pressure_blocked = (
                record.spec.pool != "interactive"
                and estimate >= policy["memory_budget"] // 2
                and float(pressure.get("memory_full_avg10", 0.0)) >= 0.2
            )
            if (
                len(active[record.spec.pool]) >= policy["workers"]
                or occupied + estimate > policy["memory_budget"]
                or bool(exclusive.intersection(record.spec.exclusive_keys))
                or pressure_blocked
            ):
                continue
            try:
                command, environment = self.store.declared_launch(record.job_id)
                if record.scratch_path is not None:
                    environment["TMPDIR"] = str(record.scratch_path)
                self.systemd.start(unit=record.unit, command=command, working_directory=record.spec.working_directory,
                                   environment=environment, timeout_seconds=record.spec.timeout_seconds,
                                   log_path=record.log_path, json_result_path=record.result_path if record.spec.result_kind in {"json", "pytest"} else None)
            except SystemdJobError:
                self._reconcile_launch_error(record)
                reconciled = self.store.load(record.job_id)
                if reconciled.state.get("terminal"):
                    self.store.cleanup_scratch(reconciled)
                    self.store.cleanup_declared_launch(reconciled.job_id)
                    self._finish_admission(reconciled, state)
            except JobRecordError:
                failed = self._with_state(record, {"phase": "launch-failed", "terminal": True, "observed_at": _timestamp()})
                self.store.save(failed)
                self.store.cleanup_scratch(failed)
                self.store.cleanup_declared_launch(failed.job_id)
                self._finish_admission(failed, state)
            else:
                submitted = self._with_state(record, {**record.state, "phase": "submitted", "terminal": False, "observed_at": _timestamp()})
                self.store.save(submitted)
                active[record.spec.pool].append(submitted)

    def _dependency_block(self, record: GenericJobRecord) -> Mapping[str, Any] | None:
        for job_id in record.spec.dependency_job_ids:
            try:
                dependency = self._get_locked(job_id)
            except JobRecordError:
                return {"phase": "dependency-failed", "terminal": True, "observed_at": _timestamp()}
            if dependency["state"].get("terminal") and dependency["state"].get("phase") != "succeeded":
                return {"phase": "dependency-failed", "terminal": True, "observed_at": _timestamp(), "dependencies": list(record.spec.dependency_job_ids)}
            if not dependency["state"].get("terminal"):
                return {"phase": "waiting-dependencies", "terminal": False, "observed_at": _timestamp(), "dependencies": list(record.spec.dependency_job_ids)}
        return None

    def _finish_admission(self, record: GenericJobRecord, state: dict[str, Any]) -> None:
        if record.spec.cache_key is not None and state["active"].get(record.spec.cache_key) == record.job_id:
            state["active"].pop(record.spec.cache_key, None)
        if (
            record.state.get("phase") == "succeeded"
            and record.spec.cache_key is not None
            and (record.spec.result_kind == "exit-status" or self._has_authoritative_result(record))
        ):
            state["cache"][record.spec.cache_key] = {"job_id": record.job_id, "touched_at": _timestamp()}
            state["cache"] = self._bounded(state["cache"], MAX_ADMISSION_CACHE_ENTRIES)
        peak = self._memory_peak(record.state.get("systemd", {}))
        if peak is not None and record.spec.estimate_key is not None:
            state["estimates"][record.spec.estimate_key] = {"bytes": peak, "touched_at": _timestamp()}
            state["estimates"] = self._bounded(state["estimates"], MAX_ADMISSION_ESTIMATES)
        self._save_admission_state(state)

    @staticmethod
    def _memory_peak(properties: Any) -> int | None:
        if not isinstance(properties, Mapping):
            return None
        value = properties.get("MemoryPeak")
        try:
            peak = int(value)
        except (TypeError, ValueError):
            return None
        return peak if peak > 0 else None

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
            status = self._get_locked(job_id)
        with self._admission_lock:
            self._admit_locked()
        return status

    def list(self) -> dict[str, Any]:
        with self._admission_lock:
            self._admit_locked()
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
                    wait_deadline=deadline,
                )
            with self._admission_lock:
                self._admit_locked()
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
            with self._admission_lock:
                self._admit_locked()
            return {**reconciled, "cancel_requested": True, "already_terminal": False}

    def logs(self, job_id: str, *, offset: int = 0, max_bytes: int = MAX_LOG_BYTES) -> dict[str, Any]:
        if offset < 0 or not 1 <= max_bytes <= MAX_LOG_BYTES:
            raise ValueError(f"log range must use offset >= 0 and max_bytes between 1 and {MAX_LOG_BYTES}")
        with self.store.locked(job_id):
            record = self.store.load(job_id)
        content = _read_private_artifact(record.log_path, max_bytes, offset=offset)
        if content is None:
            raise JobResultError("job log artifact is unavailable")
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
            if record.spec.result_kind != "exit-status":
                raise ValueError("job has no result artifact")
            with self.store.locked(job_id):
                record = self.store.load(job_id)
                if not record.state.get("terminal"):
                    self._get_locked(job_id)
                    record = self.store.load(job_id)
            return {
                "job_id": job_id,
                "kind": "exit-status",
                "value": self._parse_exit_result(record.state),
            }
        content = _read_private_artifact(record.result_path, MAX_RESULT_BYTES)
        if content is None:
            raise JobResultError("job result artifact is unavailable")
        artifact = {
            "ref": f"sinnix://jobs/{job_id}/artifacts/result",
            "max_bytes": MAX_RESULT_BYTES,
            "kind": record.spec.result_kind,
        }
        if len(content) > MAX_RESULT_BYTES or record.result_path.with_suffix(".overflow").exists():
            raise JobResultError("job result exceeds the artifact limit")
        if record.spec.result_kind in {"json", "pytest"}:
            if len(content) > max_bytes:
                raise JobResultLimitError("job JSON result exceeds the requested response limit")
            value = self._parse_json_result(content)
            return {"job_id": job_id, "kind": record.spec.result_kind, "value": value, "artifact": artifact}
        return {
            "job_id": job_id,
            "kind": record.spec.result_kind,
            "content": content[:max_bytes].decode(errors="replace"),
            "truncated": len(content) > max_bytes,
            "artifact": artifact,
        }

    @staticmethod
    def _parse_json_result(content: bytes) -> dict[str, Any]:
        try:
            value = json.loads(content.decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise JobResultError("job JSON result is malformed") from error
        if not isinstance(value, dict):
            raise JobResultError("job JSON result must be an object")
        return value

    @staticmethod
    def _parse_exit_result(state: Mapping[str, Any]) -> dict[str, Any]:
        properties = state.get("systemd")
        if not isinstance(properties, Mapping):
            raise JobResultError("job exit result is not yet observed")
        status = properties.get("ExecMainStatus")
        try:
            return {"code": int(status), "result": str(properties.get("Result", "unknown"))}
        except (TypeError, ValueError) as error:
            raise JobResultError("job exit result is malformed") from error

    def _get_locked(
        self,
        job_id: str,
        *,
        systemd_timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
        wait_deadline: float | None = None,
    ) -> dict[str, Any]:
        record = self.store.load(job_id)
        if record.state.get("phase") in {"queued", "waiting-dependencies"}:
            return self._public(record, record.state)
        if record.state.get("terminal") and not self._terminal_state_requires_reconciliation(record):
            return self._public(record, record.state)
        try:
            properties = dict(
                self.systemd.show(record.unit, timeout_seconds=systemd_timeout_seconds)
            )
        except SystemdJobTimeout:
            if wait_deadline is not None and time.monotonic() >= wait_deadline:
                return self._public(record, record.state)
            state = self._observation_unknown_state()
        except SystemdJobError:
            state = self._observation_unknown_state()
        else:
            state = self._classify(properties, record)
        updated = self._with_state(record, state)
        self.store.save(updated)
        if state.get("terminal"):
            self.store.cleanup_scratch(updated)
            if updated.spec.kind == "declared-operation":
                self.store.cleanup_declared_launch(updated.job_id)
                with self._admission_lock:
                    self._finish_admission(updated, self._admission_state())
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

    @staticmethod
    def _observation_unknown_state() -> dict[str, Any]:
        """Keep transport failures retryable until systemd supplies an observation."""
        return {
            "phase": "observation-unknown",
            "error": {"code": SYSTEMD_ERROR_CODE},
            "terminal": False,
            "observed_at": _timestamp(),
        }

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
            if self._has_authoritative_result(record):
                return {
                    "phase": "succeeded",
                    "terminal": True,
                    "systemd": dict(properties),
                    "result_evidence": "completed",
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
            if record.cancel_requested_at is not None:
                return {
                    "phase": "outcome-unknown",
                    "terminal": False,
                    "systemd": dict(properties),
                    "cancellation": self._cancel_intent(record),
                    "observed_at": _timestamp(),
                }
            return {"phase": "missing", "terminal": True, "systemd": dict(properties), "observed_at": _timestamp()}
        if self._has_schema_v3_native_success(record, properties):
            return {
                "phase": "succeeded",
                "terminal": True,
                "systemd": dict(properties),
                "result_evidence": "native-v3",
                "observed_at": _timestamp(),
            }
        active = properties.get("ActiveState", "unknown")
        if active in {"active", "activating", "reloading"}:
            phase = "running"
            terminal = False
        elif active == "deactivating":
            phase = "cancelling" if record.cancel_requested_at is not None else "stopping"
            terminal = False
        elif properties.get("Result") == "success" and properties.get("ExecMainStatus") == "0":
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

    def _terminal_state_requires_reconciliation(self, record: GenericJobRecord) -> bool:
        phase = record.state.get("phase")
        properties = record.state.get("systemd")
        if not isinstance(properties, Mapping):
            properties = {}
        if phase == "succeeded" and properties.get("LoadState") != "loaded":
            return not self._has_authoritative_result(record)
        if phase == "cancelled" and not self._stop_acknowledgement_matches(record):
            return properties.get("LoadState") != "loaded" or not self._cancel_matches(properties, record)
        return False

    @staticmethod
    def _has_valid_result_artifact(record: GenericJobRecord) -> bool:
        if record.result_path is None:
            return False
        content = _read_private_artifact(record.result_path, MAX_RESULT_BYTES)
        if (
            content is None
            or not content
            or len(content) > MAX_RESULT_BYTES
            or record.result_path.with_suffix(".overflow").exists()
        ):
            return False
        if record.spec.result_kind == "last-message":
            return True
        if record.spec.result_kind not in {"json", "pytest"}:
            return False
        try:
            value = json.loads(content.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return isinstance(value, dict)

    def _has_authoritative_result(self, record: GenericJobRecord) -> bool:
        completed = _completion_marker_path(record.log_path).is_file()
        if record.spec.result_kind == "exit-status":
            return completed
        return completed and self._has_valid_result_artifact(record)

    def _has_schema_v3_native_success(self, record: GenericJobRecord, properties: Mapping[str, str]) -> bool:
        return (
            record.spec.kind == "attested-agent"
            and record.spec.result_kind == "last-message"
            and record.cancel_requested_at is None
            and properties.get("ActiveState") == "inactive"
            and properties.get("Result") == "success"
            and record.state.get("lifecycle") == "succeeded"
            and record.state.get("exit_status") == 0
            and not isinstance(record.state.get("exit_status"), bool)
            and self._has_valid_result_artifact(record)
        )

    @staticmethod
    def _with_state(record: GenericJobRecord, state: Mapping[str, Any]) -> GenericJobRecord:
        return GenericJobRecord(
            job_id=record.job_id,
            unit=record.unit,
            spec=record.spec,
            log_path=record.log_path,
            result_path=record.result_path,
            scratch_path=record.scratch_path,
            created_at=record.created_at,
            cancel_requested_at=record.cancel_requested_at,
            cancel_requested_invocation_id=record.cancel_requested_invocation_id,
            cancel_stop_acknowledged_at=record.cancel_stop_acknowledged_at,
            cancel_stop_acknowledged_invocation_id=record.cancel_stop_acknowledged_invocation_id,
            state=dict(state),
        )

    @staticmethod
    def _with_cancel_intent(record: GenericJobRecord, invocation_id: Any) -> GenericJobRecord:
        existing_intent = record.cancel_requested_at is not None
        observed_invocation = invocation_id if isinstance(invocation_id, str) and invocation_id else None
        return GenericJobRecord(
            job_id=record.job_id,
            unit=record.unit,
            spec=record.spec,
            log_path=record.log_path,
            result_path=record.result_path,
            scratch_path=record.scratch_path,
            created_at=record.created_at,
            cancel_requested_at=record.cancel_requested_at or _timestamp(),
            cancel_requested_invocation_id=(
                record.cancel_requested_invocation_id if existing_intent else observed_invocation
            ),
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
            scratch_path=record.scratch_path,
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
    def _cancel_intent(record: GenericJobRecord) -> dict[str, str]:
        assert record.cancel_requested_at is not None
        intent = {"requested_at": record.cancel_requested_at}
        if record.cancel_requested_invocation_id is not None:
            intent["invocation_id"] = record.cancel_requested_invocation_id
        return intent

    @staticmethod
    def _public(record: GenericJobRecord, state: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "unit": record.unit,
            "kind": record.spec.kind,
            "project_id": record.spec.project_id,
            "operation": record.spec.operation,
            "parameters": (
                {"digest": record.spec.parameter_digest}
                if record.spec.kind == "declared-operation"
                else None
            ),
            "principal": record.spec.principal,
            "checkout": dict(record.spec.checkout) if record.spec.checkout is not None else None,
            "contract": dict(record.spec.contract),
            "created_at": record.created_at,
            "timeout_seconds": record.spec.timeout_seconds,
            "artifacts": {
                "log": {"ref": f"sinnix://jobs/{record.job_id}/artifacts/log", "max_bytes": MAX_LOG_BYTES},
                "result": (
                    {
                        "ref": f"sinnix://jobs/{record.job_id}/artifacts/result",
                        "max_bytes": MAX_RESULT_BYTES,
                        "kind": record.spec.result_kind,
                    }
                    if record.result_path is not None
                    else None
                ),
            },
            "state": dict(state),
        }


def _command_digest(command: Sequence[str]) -> str:
    return hashlib.sha256("\0".join(command).encode()).hexdigest()


def _parameter_digest(parameters: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


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
    parser.add_argument("--result-path", type=Path)
    parser.add_argument("--result-overflow-path", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(arguments)
    if (
        not parsed.command
        or parsed.command[0] != "--"
        or not 1 <= parsed.max_bytes <= MAX_LOG_ARTIFACT_BYTES
        or (parsed.result_path is None) != (parsed.result_overflow_path is None)
    ):
        parser.error("requires --max-bytes within the artifact cap and a command after --")
    command = parsed.command[1:]
    remaining = parsed.max_bytes
    overflowed = False
    log_handle = _open_preallocated_private_artifact(parsed.log_path)
    result_handle = _open_private_artifact(parsed.result_path) if parsed.result_path is not None else None
    result_remaining = MAX_RESULT_BYTES
    result_overflowed = False
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if parsed.result_path is not None else subprocess.STDOUT,
        )
        assert process.stdout is not None
        streams = selectors.DefaultSelector()
        streams.register(process.stdout, selectors.EVENT_READ, "stdout")
        if process.stderr is not None:
            streams.register(process.stderr, selectors.EVENT_READ, "stderr")
        try:
            while streams.get_map():
                for key, _ in streams.select():
                    chunk = key.fileobj.read1(65_536)
                    if not chunk:
                        streams.unregister(key.fileobj)
                        continue
                    accepted = chunk[:remaining]
                    log_handle.write(accepted)
                    remaining -= len(accepted)
                    if len(chunk) > len(accepted) and not overflowed:
                        _write_private_marker(parsed.overflow_path)
                        overflowed = True
                    if key.data == "stdout" and result_handle is not None:
                        accepted_result = chunk[:result_remaining]
                        result_handle.write(accepted_result)
                        result_remaining -= len(accepted_result)
                        if len(chunk) > len(accepted_result) and not result_overflowed:
                            assert parsed.result_overflow_path is not None
                            _write_private_marker(parsed.result_overflow_path)
                            result_overflowed = True
            log_handle.flush()
            os.fsync(log_handle.fileno())
        finally:
            streams.close()
        if result_handle is not None:
            result_handle.flush()
            os.fsync(result_handle.fileno())
        return_code = process.wait()
    finally:
        log_handle.close()
        if result_handle is not None:
            result_handle.close()
    if return_code == 0:
        _write_private_marker(_completion_marker_path(parsed.log_path))
    return return_code


def capture_cli() -> None:
    raise SystemExit(capture_main())


if __name__ == "__main__":
    raise SystemExit(capture_main(sys.argv[2:] if len(sys.argv) > 1 and sys.argv[1] == "capture" else None))
