from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import selectors
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Condition, Lock, RLock
from typing import Any, Iterator, Protocol
from uuid import UUID, uuid4

from .limits import (
    DEFAULT_TIMEOUT_SECONDS,
    maximum_timeout_seconds,
    valid_timeout_seconds,
)
from .projects import (
    OperationService,
    ProjectAdapter,
    ProjectConfigError,
    ProjectOperation,
    RegisteredCheckout,
    revalidate_registered_checkout,
)

DEFAULT_WAIT_SECONDS = 30
MAX_WAIT_SECONDS = 3600
MAX_WAIT_ANY_JOBS = 32
MAX_TERMINAL_EVENT_ENTRIES = 4096
NOTIFY_TIMEOUT_SECONDS = 2.0
SYSTEMD_COMMAND_TIMEOUT_SECONDS = 0.25
CANCEL_OUTCOME_RECONCILIATION_GRACE_SECONDS = 300
MAX_LOG_BYTES = 64_000
MAX_LOG_ARTIFACT_BYTES = 1_048_576
MAX_RESULT_BYTES = 64_000
JOB_SCHEMA_VERSION = 5
JOB_UNIT_PREFIX = "sinnixd-job-"
JOB_LIST_CURSOR_SCHEMA_VERSION = 1
MAX_JOB_LIST_CURSOR_BYTES = 512
SYSTEMD_ERROR_CODE = "systemd-job-error"
ADMISSION_SCHEMA_VERSION = 1
MAX_ADMISSION_CACHE_ENTRIES = 128
MAX_ADMISSION_ESTIMATES = 128
MIB = 1024 * 1024
POOL_POLICIES = {
    "interactive": {
        "workers": 4,
        "memory_budget": 3 * 1024 * MIB,
        "default_estimate": 256 * MIB,
    },
    "normal": {
        "workers": 3,
        "memory_budget": 8 * 1024 * MIB,
        "default_estimate": 1024 * MIB,
    },
    "bulk": {
        "workers": 1,
        "memory_budget": 18 * 1024 * MIB,
        "default_estimate": 8 * 1024 * MIB,
    },
}


def default_state_dir() -> Path:
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        / "sinnixd"
    )


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


class JobPageCursorError(ValueError):
    """Raised when a job-list continuation does not bind its original view."""


def _job_order_key(record: "GenericJobRecord") -> tuple[str, str]:
    return record.created_at, record.job_id


def _encode_job_list_cursor(
    *,
    principal: str,
    query: Mapping[str, Any],
    snapshot: tuple[str, str],
    after: tuple[str, str],
) -> str:
    payload = {
        "schema": JOB_LIST_CURSOR_SCHEMA_VERSION,
        "principal": principal,
        "query": dict(query),
        "snapshot": list(snapshot),
        "after": list(after),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(encoded).decode().rstrip("=")


def _decode_job_list_cursor(
    cursor: str, *, principal: str, query: Mapping[str, Any]
) -> tuple[tuple[str, str], tuple[str, str]]:
    if (
        not isinstance(cursor, str)
        or not cursor
        or len(cursor.encode()) > MAX_JOB_LIST_CURSOR_BYTES
    ):
        raise JobPageCursorError("job list cursor is invalid")
    try:
        decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        value = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise JobPageCursorError("job list cursor is invalid") from error
    if (
        not isinstance(value, Mapping)
        or set(value) != {"schema", "principal", "query", "snapshot", "after"}
        or value["schema"] != JOB_LIST_CURSOR_SCHEMA_VERSION
        or value["principal"] != principal
        or value["query"] != dict(query)
    ):
        raise JobPageCursorError("job list cursor does not belong to this principal")

    def pair(name: str) -> tuple[str, str]:
        candidate = value[name]
        if (
            not isinstance(candidate, list)
            or len(candidate) != 2
            or any(not isinstance(item, str) for item in candidate)
        ):
            raise JobPageCursorError("job list cursor is invalid")
        return candidate[0], candidate[1]

    snapshot = pair("snapshot")
    after = pair("after")
    if after > snapshot:
        raise JobPageCursorError("job list cursor is invalid")
    return snapshot, after


def _open_private_parent(path: Path) -> int:
    """Open and validate the private directory holding one capture artifact."""
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_descriptor = os.open(path.parent, directory_flags)
    parent = os.fstat(parent_descriptor)
    if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
        os.close(parent_descriptor)
        raise PermissionError(f"artifact parent is not private: {path.parent}")
    return parent_descriptor


def _private_regular_artifact(
    descriptor: int, path: Path, *, require_private_mode: bool = True
) -> None:
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
        descriptor = os.open(
            path.name, os.O_WRONLY | os.O_NOFOLLOW, dir_fd=parent_descriptor
        )
    finally:
        os.close(parent_descriptor)
    try:
        _private_regular_artifact(descriptor, path)
        os.ftruncate(descriptor, 0)
    except BaseException:
        os.close(descriptor)
        raise
    return os.fdopen(descriptor, "wb")


def _read_private_artifact(
    path: Path, max_bytes: int, *, offset: int = 0
) -> bytes | None:
    """Read one bounded, private regular artifact without following a replacement link."""
    try:
        parent_descriptor = _open_private_parent(path)
    except OSError:
        return None
    try:
        try:
            descriptor = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_descriptor
            )
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
        notify_socket: Path | None = None,
        notify_job_id: str | None = None,
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
        notify_socket: Path | None = None,
        notify_job_id: str | None = None,
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
        if notify_socket is not None and notify_job_id is not None:
            args.extend(
                [
                    "--notify-socket",
                    str(notify_socket),
                    "--notify-job-id",
                    notify_job_id,
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
    def _run(
        args: Sequence[str], *, timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS
    ) -> str:
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
            raise SystemdJobError(
                f"systemd command is unavailable: {args[0]}"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise SystemdJobTimeout("systemd command timed out") from error
        except OSError as error:
            raise SystemdJobError(
                f"systemd command failed: {args[0]}: {error}"
            ) from error
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


class TerminalEvents:
    """In-process wake-ups for terminal job transitions.

    Events only accelerate observation: firing is best-effort, a missed event
    is recovered by the fallback observation cadence, and a spurious event
    costs one extra bounded observation. Systemd observation remains the sole
    state authority.
    """

    def __init__(self) -> None:
        self._condition = Condition()
        self._fired: dict[str, float] = {}

    def fire(self, job_id: str) -> None:
        with self._condition:
            self._fired[job_id] = time.monotonic()
            if len(self._fired) > MAX_TERMINAL_EVENT_ENTRIES:
                for stale in sorted(self._fired, key=self._fired.__getitem__)[
                    : len(self._fired) - MAX_TERMINAL_EVENT_ENTRIES
                ]:
                    del self._fired[stale]
            self._condition.notify_all()

    def wait_terminal(self, job_ids: Sequence[str], seconds: float) -> bool:
        """Block up to ``seconds`` for a fired event covering any of ``job_ids``."""
        with self._condition:
            if any(job_id in self._fired for job_id in job_ids):
                return True
            if seconds > 0:
                self._condition.wait(seconds)
            return any(job_id in self._fired for job_id in job_ids)


def notify_job_exit(socket_path: Path, job_id: str, exit_code: int) -> None:
    """Best-effort daemon wake-up sent by the capture wrapper at process exit.

    Failure is silent by design: the daemon may be down or restarting, and the
    observation path recovers the outcome without this accelerator.
    """
    request_id = str(uuid4())
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "dispatch",
            "params": {
                "request_id": request_id,
                "correlation_id": str(uuid4()),
                "operation": "job.notify-exit",
                "owner": "systemd-jobs",
                "principal": "agent-control",
                "arguments": {"job_id": job_id, "exit_code": exit_code},
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(NOTIFY_TIMEOUT_SECONDS)
        connection.connect(str(socket_path))
        connection.sendall(struct.pack("!I", len(payload)) + payload)
        connection.recv(4)


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


def _loopback_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


@dataclass(frozen=True)
class ServiceLeasePort:
    name: str
    environment: str
    port: int

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "environment": self.environment, "port": self.port}


@dataclass(frozen=True)
class ServiceLease:
    """Bounded public ownership of declared loopback ports for one generic job."""

    lease_id: str
    readiness: str
    lifetime: str
    ports: tuple[ServiceLeasePort, ...]
    host: str = "127.0.0.1"

    def __post_init__(self) -> None:
        try:
            UUID(self.lease_id)
        except (ValueError, AttributeError) as error:
            raise ValueError("service lease ID is invalid") from error
        if (
            self.host != "127.0.0.1"
            or self.readiness not in {"none", "project-command"}
            or self.lifetime != "job"
        ):
            raise ValueError("service lease metadata is invalid")
        if not self.ports or len(self.ports) > 8:
            raise ValueError("service lease ports are invalid")
        names = [port.name for port in self.ports]
        environments = [port.environment for port in self.ports]
        ports = [port.port for port in self.ports]
        if (
            len(set(names)) != len(names)
            or len(set(environments)) != len(environments)
            or len(set(ports)) != len(ports)
            or any(
                not isinstance(port.name, str)
                or not port.name
                or not isinstance(port.environment, str)
                or not port.environment
                or not isinstance(port.port, int)
                or isinstance(port.port, bool)
                or not 1024 <= port.port <= 65535
                for port in self.ports
            )
        ):
            raise ValueError("service lease ports are invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.lease_id,
            "host": self.host,
            "readiness": self.readiness,
            "lifetime": self.lifetime,
            "ports": [port.to_dict() for port in self.ports],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ServiceLease:
        if set(value) != {"id", "host", "readiness", "lifetime", "ports"}:
            raise JobRecordError("service lease metadata is invalid")
        raw_ports = value.get("ports")
        if not isinstance(raw_ports, list):
            raise JobRecordError("service lease ports are invalid")
        ports: list[ServiceLeasePort] = []
        for port in raw_ports:
            if not isinstance(port, Mapping) or set(port) != {
                "name",
                "environment",
                "port",
            }:
                raise JobRecordError("service lease ports are invalid")
            try:
                ports.append(
                    ServiceLeasePort(port["name"], port["environment"], port["port"])
                )
            except (KeyError, TypeError) as error:
                raise JobRecordError("service lease ports are invalid") from error
        try:
            return cls(
                lease_id=value["id"],
                host=value["host"],
                readiness=value["readiness"],
                lifetime=value["lifetime"],
                ports=tuple(ports),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise JobRecordError("service lease metadata is invalid") from error


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
    coalesce_key: str | None = None
    cache_key: str | None = None
    estimate_key: str | None = None
    estimate_memory_bytes: int | None = None
    scratch: str = "none"
    lease: ServiceLease | None = None

    def __post_init__(self) -> None:
        if self.kind not in {
            "declared-operation",
            "foreground-command",
            "operator-shell",
            "attested-agent",
        }:
            raise ValueError("job kind is invalid")
        if not self.command and not self.command_digest:
            raise ValueError("job needs a launch command or command digest")
        if self.command and any(
            not isinstance(value, str) or not value for value in self.command
        ):
            raise ValueError("job command must be non-empty strings")
        if self.command_digest is not None and (
            len(self.command_digest) != 64
            or any(value not in "0123456789abcdef" for value in self.command_digest)
        ):
            raise ValueError("job command digest is invalid")
        if self.parameter_digest is not None and (
            len(self.parameter_digest) != 64
            or any(value not in "0123456789abcdef" for value in self.parameter_digest)
        ):
            raise ValueError("job parameter digest is invalid")
        if self.kind == "declared-operation" and self.parameter_digest is None:
            raise ValueError("declared operation jobs require a parameter digest")
        if self.kind != "declared-operation" and self.parameter_digest is not None:
            raise ValueError("only declared operation jobs may have a parameter digest")
        if not isinstance(self.working_directory, str) or not self.working_directory:
            raise ValueError("job working_directory must be non-empty")
        maximum_timeout = maximum_timeout_seconds(self.kind)
        if not valid_timeout_seconds(self.timeout_seconds, kind=self.kind):
            raise ValueError(
                f"job timeout_seconds must be between 1 and {maximum_timeout}"
            )
        if any(
            not isinstance(key, str) or not key or not isinstance(value, str)
            for key, value in self.environment.items()
        ):
            raise ValueError("job environment must be string key/value pairs")
        if any(not isinstance(key, str) or not key for key in self.environment_keys):
            raise ValueError("job environment metadata must be non-empty strings")
        if self.principal is not None and self.principal not in {
            "operator",
            "agent-control",
        }:
            raise ValueError("job principal is invalid")
        if self.kind == "operator-shell" and self.principal != "operator":
            raise ValueError("operator shell jobs require the operator principal")
        if self.kind == "attested-agent" and self.principal not in {
            "agent-control",
            "operator",
        }:
            raise ValueError(
                "attested agent jobs require the agent-control or operator principal"
            )
        if self.kind in {"operator-shell", "attested-agent"} and not self.checkout:
            raise ValueError("typed jobs require a registered checkout")
        if self.checkout is not None and (
            set(self.checkout)
            != {
                "project_id",
                "project_path",
                "checkout_id",
                "path",
                "git_common_dir",
                "head",
            }
            or any(
                not isinstance(value, str) or not value
                for value in self.checkout.values()
            )
        ):
            raise ValueError("job checkout identity is invalid")
        if not isinstance(self.contract, Mapping) or any(
            not isinstance(key, str) or not key for key in self.contract
        ):
            raise ValueError("job contract is invalid")
        if self.result_kind not in {"exit-status", "last-message", "json", "pytest"}:
            raise ValueError("job result kind is invalid")
        if self.pool not in POOL_POLICIES:
            raise ValueError("job pool is invalid")
        if any(not isinstance(key, str) or not key for key in self.exclusive_keys):
            raise ValueError("job exclusive keys are invalid")
        if len(set(self.exclusive_keys)) != len(self.exclusive_keys):
            raise ValueError("job exclusive keys must be unique")
        if any(
            not isinstance(value, str) or not value for value in self.dependency_job_ids
        ):
            raise ValueError("job dependency IDs are invalid")
        for name, key in (("coalesce", self.coalesce_key), ("cache", self.cache_key)):
            if key is not None and (
                len(key) != 64 or any(value not in "0123456789abcdef" for value in key)
            ):
                raise ValueError(f"job {name} key is invalid")
        if self.estimate_key is not None and (
            not isinstance(self.estimate_key, str) or not self.estimate_key
        ):
            raise ValueError("job estimate key is invalid")
        if self.estimate_memory_bytes is not None and (
            not isinstance(self.estimate_memory_bytes, int)
            or isinstance(self.estimate_memory_bytes, bool)
            or self.estimate_memory_bytes < 1
        ):
            raise ValueError("job memory estimate is invalid")
        if self.scratch not in {"none", "tmpfs", "nvme"}:
            raise ValueError("job scratch is invalid")
        if self.lease is not None and (
            self.kind != "declared-operation"
            or not self.project_id
            or not self.operation
        ):
            raise ValueError("only declared operations may own service leases")
        if self.kind == "operator-shell" and self.result_kind != "exit-status":
            raise ValueError("operator shell jobs only support exit-status results")
        if self.kind == "attested-agent" and self.result_kind != "last-message":
            raise ValueError("attested agent jobs require last-message results")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "working_directory": self.working_directory,
            "environment_keys": sorted(
                set(self.environment) | set(self.environment_keys)
            ),
            "timeout_seconds": self.timeout_seconds,
            "project_id": self.project_id,
            "operation": self.operation,
            "principal": self.principal,
            "checkout": dict(self.checkout) if self.checkout is not None else None,
            "contract": dict(self.contract),
            "result_kind": self.result_kind,
            "lease": self.lease.to_dict() if self.lease is not None else None,
            "admission": {
                "pool": self.pool,
                "exclusive_keys": list(self.exclusive_keys),
                "dependencies": list(self.dependency_job_ids),
                "coalesce_key": self.coalesce_key,
                "cache_key": self.cache_key,
                "estimate_key": self.estimate_key,
                "estimate_memory_bytes": self.estimate_memory_bytes,
                "scratch": self.scratch,
            },
        }
        if self.kind != "declared-operation":
            result["command"] = {
                "digest": self.command_digest or _command_digest(self.command),
                "display": "synthetic foreground command"
                if self.kind == "foreground-command"
                else f"{self.kind} contract runner",
            }
        else:
            result["command"] = {
                "display": "declared project operation",
            }
            result["parameters"] = {"digest": self.parameter_digest}
        return result

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, require_parameter_digest: bool = False
    ) -> GenericJobSpec:
        command = value.get("command")
        environment_keys = value.get("environment_keys")
        if (
            not isinstance(command, Mapping)
            or not isinstance(environment_keys, list)
            or any(not isinstance(key, str) or not key for key in environment_keys)
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
            elif not isinstance(raw_parameters, Mapping) or set(raw_parameters) != {
                "digest"
            }:
                raise JobRecordError("declared job spec has invalid parameter metadata")
            else:
                parameter_digest = raw_parameters.get("digest")
        elif raw_parameters is not None:
            raise JobRecordError("non-declared job spec has parameter metadata")
        admission = value.get("admission", {})
        if not isinstance(admission, Mapping):
            raise JobRecordError("job admission metadata is invalid")
        raw_lease = value.get("lease")
        if raw_lease is not None and not isinstance(raw_lease, Mapping):
            raise JobRecordError("job service lease metadata is invalid")
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
                coalesce_key=admission.get("coalesce_key"),
                cache_key=admission.get("cache_key"),
                estimate_key=admission.get("estimate_key"),
                estimate_memory_bytes=admission.get("estimate_memory_bytes"),
                scratch=admission.get("scratch", "none"),
                lease=ServiceLease.from_dict(raw_lease)
                if raw_lease is not None
                else None,
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
                "result": str(self.result_path)
                if self.result_path is not None
                else None,
                "scratch": str(self.scratch_path)
                if self.scratch_path is not None
                else None,
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
        if schema_version not in {2, 3, 4, JOB_SCHEMA_VERSION} or not isinstance(
            job_id, str
        ):
            raise JobRecordError("job record schema or ID is invalid")
        if unit != job_unit_name(job_id):
            raise JobRecordError("job record unit does not match its ID")
        if not isinstance(artifacts, Mapping) or not isinstance(
            artifacts.get("log"), str
        ):
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
            or (
                stop_acknowledged is not None and not isinstance(stop_acknowledged, str)
            )
            or (stop_invocation is not None and not isinstance(stop_invocation, str))
            or (stop_acknowledged is None) != (stop_invocation is None)
            or (
                stop_acknowledged is not None
                and (cancelled is None or stop_invocation != invocation)
            )
        ):
            raise JobRecordError("job record timestamps are invalid")
        parsed_spec = GenericJobSpec.from_dict(
            spec, require_parameter_digest=schema_version >= 4
        )
        if parsed_spec.lease is not None and parsed_spec.lease.lease_id != job_id:
            raise JobRecordError("service lease ID does not match its job")
        return cls(
            job_id=job_id,
            unit=unit,
            spec=parsed_spec,
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
    def readiness_root(self) -> Path:
        return self.root / "readiness"

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

    @property
    def leases_root(self) -> Path:
        return self.root / "leases"

    @property
    def locks_root(self) -> Path:
        return self.root / "locks"

    @property
    def active_records_path(self) -> Path:
        return self.root / "active-jobs.json"

    @property
    def service_lease_records_path(self) -> Path:
        return self.root / "unreleased-service-leases.json"

    @contextmanager
    def locked_active_records(self) -> Iterator[None]:
        _ensure_durable_directory(self.root)
        lock_path = self.root / "active-jobs.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @contextmanager
    def locked_service_lease_records(self) -> Iterator[None]:
        _ensure_durable_directory(self.root)
        lock_path = self.root / "unreleased-service-leases.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @contextmanager
    def locked_service_leases(self) -> Iterator[None]:
        _ensure_durable_directory(self.leases_root)
        lock_path = self.leases_root / ".lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def allocate_service_lease(
        self, job_id: str, service: OperationService
    ) -> ServiceLease:
        _ = job_unit_name(job_id)
        with self.locked(job_id):
            with self.locked_service_leases():
                lease = self._allocate_service_lease_locked(job_id, service)
                self._save_service_lease(lease)
                return lease

    def create_declared_service_record(
        self,
        *,
        job_id: str,
        service: OperationService,
        build_spec: Callable[[ServiceLease], GenericJobSpec],
    ) -> GenericJobRecord:
        """Create one recoverable declared-service intent before its first launch.

        The lock order is per-job, then the cross-process lease lock.  A
        failed private-input write is known to precede any systemd start, so
        this method can terminalize and discard that intent safely.
        """
        with self.locked(job_id):
            with self.locked_service_leases():
                lease = self._allocate_service_lease_locked(job_id, service)
                record = self.create(build_spec(lease), job_id)
                try:
                    self.write_declared_launch(
                        record.job_id, record.spec.command, record.spec.environment
                    )
                    self._save_service_lease(lease)
                except BaseException:
                    failed = replace(
                        record,
                        state={
                            "phase": "launch-failed",
                            "terminal": True,
                            "observed_at": _timestamp(),
                        },
                    )
                    self.save(failed)
                    self.cleanup_scratch(failed)
                    self.cleanup_declared_launch(failed.job_id)
                    self._mark_service_lease_released(lease.lease_id)
                    raise
                return record

    def reconcile_service_leases(
        self,
        records: Sequence[GenericJobRecord],
        observe_unit: Callable[[str], Mapping[str, str]],
    ) -> list[GenericJobRecord]:
        with self.locked_service_leases():
            return self._reconcile_service_leases_locked(records, observe_unit)

    def recover_service_leases(
        self,
        observe_unit: Callable[[str], Mapping[str, str]],
    ) -> list[GenericJobRecord]:
        """Recover live leases without serializing historical terminal jobs."""
        return self.reconcile_service_leases(self.active_records(), observe_unit)

    def _reconcile_service_leases_locked(
        self,
        records: Sequence[GenericJobRecord],
        observe_unit: Callable[[str], Mapping[str, str]],
    ) -> list[GenericJobRecord]:
        active = {
            record.job_id: record.spec.lease
            for record in records
            if not record.state.get("terminal") and record.spec.lease is not None
        }
        existing = self._service_leases()
        protected: dict[str, ServiceLease] = {}
        recovered = list(records)
        for lease_id, lease in existing.items():
            if lease_id in active:
                continue
            try:
                record = self.load(lease_id)
            except JobRecordError:
                record = None
            if record is not None and record.spec.lease == lease:
                if not record.state.get("terminal"):
                    active[lease_id] = lease
                    recovered.append(record)
                    self._set_active_record(record.job_id, active=True)
                    continue
                if self._terminal_service_lease_releasable(record):
                    self._mark_service_lease_released(lease_id)
                    continue
            try:
                properties = observe_unit(job_unit_name(lease_id))
            except SystemdJobError:
                protected[lease_id] = lease
                continue
            if properties.get("LoadState") != "not-found":
                protected[lease_id] = lease
            else:
                if record is None or record.spec.lease != lease:
                    self._mark_service_lease_released(lease_id)
                else:
                    protected[lease_id] = lease
        occupied: set[int] = set()
        for lease in protected.values():
            ports = {port.port for port in lease.ports}
            if occupied.intersection(ports):
                raise JobRecordError(
                    "protected service lease ports collide during recovery"
                )
            occupied.update(ports)
        for lease_id, lease in sorted(active.items()):
            assert lease is not None
            ports = {port.port for port in lease.ports}
            if occupied.intersection(ports):
                raise JobRecordError(
                    "active service lease ports collide during recovery"
                )
            occupied.update(ports)
            self._service_lease_released_path(lease_id).unlink(missing_ok=True)
            if existing.get(lease_id) != lease:
                self._save_service_lease(lease)
        for lease_id, lease in protected.items():
            self._service_lease_released_path(lease_id).unlink(missing_ok=True)
            if existing.get(lease_id) != lease:
                self._save_service_lease(lease)
        _fsync_directory(self.leases_root)
        return recovered

    @staticmethod
    def _terminal_service_lease_releasable(record: GenericJobRecord) -> bool:
        """Accept only durable, unit-bound evidence that a lease-owning job ended."""
        if record.spec.lease is None or not record.state.get("terminal"):
            return False
        phase = record.state.get("phase")
        properties = record.state.get("systemd")
        if not isinstance(properties, Mapping):
            return record.state.get("launch_evidence") == "not-started"
        load_state = properties.get("LoadState")
        if load_state == "not-found":
            cancellation = record.state.get("cancellation")
            return (
                phase in {"missing", "launch-failed"}
                or (
                    phase == "succeeded"
                    and record.state.get("result_evidence") == "completed"
                )
                or (
                    phase == "cancelled"
                    and record.cancel_stop_acknowledged_invocation_id
                    == record.cancel_requested_invocation_id
                    and record.cancel_stop_acknowledged_invocation_id is not None
                )
                or (
                    phase == "outcome-unknown"
                    and record.state.get("outcome_evidence")
                    == "unit-collected-after-cancellation-grace"
                    and record.cancel_requested_at is not None
                    and isinstance(cancellation, Mapping)
                    and cancellation.get("requested_at") == record.cancel_requested_at
                )
            )
        if load_state != "loaded":
            return False
        invocation = properties.get("InvocationID")
        if not isinstance(invocation, str) or not invocation:
            return False
        bound = record.state.get("lease_invocation_id", invocation)
        if bound != invocation:
            return False
        active = properties.get("ActiveState")
        result = properties.get("Result")
        status = properties.get("ExecMainStatus")
        if phase == "succeeded":
            return active == "inactive" and result == "success" and status == "0"
        if phase == "timed_out":
            return active in {"inactive", "failed"} and result == "timeout"
        if phase == "cancelled":
            return (
                active == "inactive"
                and result == "signal"
                and record.cancel_stop_acknowledged_invocation_id == invocation
            )
        return (
            phase == "failed"
            and active in {"inactive", "failed"}
            and status not in {None, "0"}
        )

    def release_terminal_service_lease(self, record: GenericJobRecord) -> None:
        if not self._terminal_service_lease_releasable(record):
            return
        assert record.spec.lease is not None
        with self.locked_service_leases():
            self._mark_service_lease_released(record.spec.lease.lease_id)

    def _allocate_service_lease_locked(
        self, job_id: str, service: OperationService
    ) -> ServiceLease:
        occupied = {
            port.port
            for lease in self._service_leases().values()
            for port in lease.ports
        }
        for record in self.service_lease_records():
            assert record.spec.lease is not None
            occupied.update(port.port for port in record.spec.lease.ports)
        allocations: list[ServiceLeasePort] = []
        for slot in service.ports:
            port = next(
                (
                    candidate
                    for candidate in range(slot.minimum, slot.maximum + 1)
                    if candidate not in occupied and _loopback_port_available(candidate)
                ),
                None,
            )
            if port is None:
                raise JobRecordError(
                    f"no loopback port is available for service slot {slot.name}"
                )
            occupied.add(port)
            allocations.append(ServiceLeasePort(slot.name, slot.environment, port))
        return ServiceLease(
            job_id, service.readiness, service.lifetime, tuple(allocations)
        )

    def service_lease_ports_available(self, lease: ServiceLease | None) -> bool:
        """Confirm the descriptor-owned ports were not claimed before launch.

        A declared command binds its own port, so Sinnixd cannot retain the
        socket without imposing a socket-activation protocol on every project.
        This last check turns a claim between allocation and systemd launch
        into a terminal launch failure that releases the durable lease.
        """
        if lease is None:
            return True
        with self.locked_service_leases():
            return all(_loopback_port_available(port.port) for port in lease.ports)

    def _service_leases(self) -> dict[str, ServiceLease]:
        leases: dict[str, ServiceLease] = {}
        for path in sorted(self.leases_root.glob("*.json")):
            try:
                value = json.loads(path.read_text())
                if not isinstance(value, Mapping):
                    raise JobRecordError("service lease metadata is invalid")
                lease = ServiceLease.from_dict(value)
            except (OSError, json.JSONDecodeError, JobRecordError):
                path.unlink(missing_ok=True)
                continue
            if path != self._service_lease_path(lease.lease_id):
                path.unlink(missing_ok=True)
                continue
            leases[lease.lease_id] = lease
        return leases

    def _save_service_lease(self, lease: ServiceLease) -> None:
        path = self._service_lease_path(lease.lease_id)
        temporary = path.with_suffix(".json.tmp")
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(lease.to_dict(), handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            _fsync_directory(self.leases_root)
        finally:
            temporary.unlink(missing_ok=True)

    def _service_lease_path(self, lease_id: str) -> Path:
        _ = job_unit_name(lease_id)
        return self.leases_root / f"{lease_id}.json"

    def _service_lease_released_path(self, lease_id: str) -> Path:
        _ = job_unit_name(lease_id)
        return self.leases_root / f"{lease_id}.released"

    def _service_lease_released(self, lease_id: str) -> bool:
        return (
            _read_private_artifact(self._service_lease_released_path(lease_id), 1)
            == b""
        )

    def _mark_service_lease_released(self, lease_id: str) -> None:
        self._service_lease_path(lease_id).unlink(missing_ok=True)
        marker = self._service_lease_released_path(lease_id)
        if not self._service_lease_released(lease_id):
            marker.unlink(missing_ok=True)
            _write_private_marker(marker)
        self._set_service_lease_record(lease_id, active=False)
        _fsync_directory(self.leases_root)

    def create(
        self, spec: GenericJobSpec, job_id: str | None = None
    ) -> GenericJobRecord:
        _ensure_durable_directory(self.records_root)
        _ensure_durable_directory(self.logs_root)
        if spec.result_kind in {"last-message", "json", "pytest"}:
            _ensure_durable_directory(self.results_root)
        candidates = (
            (job_id,) if job_id is not None else tuple(str(uuid4()) for _ in range(8))
        )
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
                state={
                    "phase": "launching",
                    "terminal": False,
                    "observed_at": _timestamp(),
                },
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

    def scratch_path_for(self, kind: str, job_id: str) -> Path | None:
        """Return the deterministic job-owned scratch path before allocation."""
        if kind == "none":
            return None
        _ = job_unit_name(job_id)
        root = self.tmpfs_scratch_root if kind == "tmpfs" else self.nvme_scratch_root
        return (root / job_id).resolve()

    def cleanup_scratch(self, record: GenericJobRecord) -> None:
        if record.scratch_path is None:
            return
        root = (
            self.tmpfs_scratch_root.resolve()
            if record.spec.scratch == "tmpfs"
            else self.nvme_scratch_root.resolve()
        )
        path = record.scratch_path.resolve()
        if path.parent != root or path.name != record.job_id:
            raise JobRecordError("job scratch artifact escapes owned root")
        self._cleanup_scratch_path(root, path)

    def prepare_scratch(self, record: GenericJobRecord) -> Path | None:
        if record.scratch_path is None:
            return None
        root = (
            self.tmpfs_scratch_root
            if record.spec.scratch == "tmpfs"
            else self.nvme_scratch_root
        )
        _ensure_durable_directory(root)
        root = root.resolve()
        path = record.scratch_path
        if path.parent != root or path.name != record.job_id:
            raise JobRecordError("job scratch artifact escapes owned root")
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            artifact = path.lstat()
            if (
                artifact.st_uid != os.getuid()
                or artifact.st_mode & 0o077
                or not stat.S_ISDIR(artifact.st_mode)
            ):
                raise JobRecordError(
                    "job scratch artifact is not a private directory"
                ) from None
        else:
            _fsync_directory(root)
        return path

    def cleanup_inactive_scratch(self, records: Sequence[GenericJobRecord]) -> None:
        active = {
            record.job_id for record in records if not record.state.get("terminal")
        }
        for root in (self.tmpfs_scratch_root, self.nvme_scratch_root):
            if not root.exists():
                continue
            resolved_root = root.resolve()
            for path in sorted(resolved_root.iterdir()):
                try:
                    _ = job_unit_name(path.name)
                except (ValueError, JobRecordError):
                    continue
                if path.name not in active and path.is_dir() and not path.is_symlink():
                    self._cleanup_scratch_path(resolved_root, path)

    def prepare_service_readiness(self, job_id: str) -> Path:
        _ = job_unit_name(job_id)
        _ensure_durable_directory(self.readiness_root)
        path = self.readiness_root / job_id
        path.unlink(missing_ok=True)
        return path

    def service_ready(self, job_id: str) -> bool:
        _ = job_unit_name(job_id)
        path = self.readiness_root / job_id
        try:
            return (
                not path.is_symlink()
                and path.is_file()
                and path.read_text() == f"{job_id}\n"
            )
        except OSError:
            return False

    def cleanup_service_readiness(self, job_id: str) -> None:
        _ = job_unit_name(job_id)
        path = self.readiness_root / job_id
        if path.exists() or path.is_symlink():
            path.unlink()
            _fsync_directory(self.readiness_root)

    def cleanup_inactive_readiness(self, records: Sequence[GenericJobRecord]) -> None:
        if not self.readiness_root.exists():
            return
        active = {
            record.job_id for record in records if not record.state.get("terminal")
        }
        for path in sorted(self.readiness_root.iterdir()):
            try:
                _ = job_unit_name(path.name)
            except (ValueError, JobRecordError):
                continue
            if path.name not in active:
                path.unlink(missing_ok=True)

    @staticmethod
    def _cleanup_scratch_path(root: Path, path: Path) -> None:
        if path.exists():
            # Test tools may deliberately remove write bits from fixtures under
            # TMPDIR. The terminal job owns this entire bounded tree, so restore
            # owner traversal/write permission before removing it. Never follow
            # symlinks while doing so.
            path.chmod(path.stat().st_mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            for directory, names, _files in os.walk(path, followlinks=False):
                current = Path(directory)
                current.chmod(
                    current.stat().st_mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
                )
                for name in names:
                    child = current / name
                    if not child.is_symlink():
                        child.chmod(
                            child.stat().st_mode
                            | stat.S_IRUSR
                            | stat.S_IWUSR
                            | stat.S_IXUSR
                        )
            shutil.rmtree(path)
            _fsync_directory(root)

    def write_declared_launch(
        self, job_id: str, command: Sequence[str], environment: Mapping[str, str]
    ) -> None:
        _ = job_unit_name(job_id)
        _ensure_durable_directory(self.inputs_root)
        path = self.inputs_root / f"{job_id}.launch"
        payload = json.dumps(
            {"command": list(command), "environment": dict(environment)}, sort_keys=True
        ).encode()
        with _open_private_artifact(path) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.inputs_root)

    def declared_launch(self, job_id: str) -> tuple[tuple[str, ...], dict[str, str]]:
        _ = job_unit_name(job_id)
        content = _read_private_artifact(
            self.inputs_root / f"{job_id}.launch", 128 * 1024
        )
        try:
            value = json.loads(content.decode()) if content is not None else None
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise JobRecordError("declared job launch input is invalid") from error
        if not isinstance(value, Mapping) or set(value) != {"command", "environment"}:
            raise JobRecordError("declared job launch input is invalid")
        command = value["command"]
        environment = value["environment"]
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(item, str) or not item for item in command)
            or not isinstance(environment, Mapping)
            or any(
                not isinstance(key, str) or not key or not isinstance(item, str)
                for key, item in environment.items()
            )
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
            _ensure_durable_directory(self.locks_root)
            lock_path = self.locks_root / f"{job_id}.lock"
            descriptor = os.open(
                lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

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

    def list(self, *, limit: int | None = None) -> list[GenericJobRecord]:
        if limit is not None and limit < 1:
            raise ValueError("job record list limit must be positive")
        if not self.records_root.exists():
            return []
        records: list[GenericJobRecord] = []
        for path in sorted(self.records_root.glob("*.json")):
            try:
                records.append(self.load(path.stem))
            except JobRecordError:
                continue
            if limit is not None and len(records) >= limit:
                break
        return records

    def count(self) -> int:
        if not self.records_root.exists():
            return 0
        return sum(1 for _ in self.records_root.glob("*.json"))

    def active_records(self) -> list[GenericJobRecord]:
        """Return the durable nonterminal set without reopening historical jobs.

        Older stores receive a one-time, lock-free migration from record files.
        Thereafter every record save maintains the index before a new live
        record is published and after a terminal record is published, so a
        crash can leave only a harmless stale index entry.
        """
        with self.locked_active_records():
            job_ids = self._active_record_ids()
            if job_ids is None:
                all_records = self.list()
                records = [
                    record for record in all_records if not record.state.get("terminal")
                ]
                self._write_active_record_ids({record.job_id for record in records})
                if self._service_lease_record_ids() is None:
                    with self.locked_service_lease_records():
                        self._write_service_lease_record_ids(
                            {
                                record.job_id
                                for record in all_records
                                if record.spec.lease is not None
                                and not self._service_lease_released(record.job_id)
                            }
                        )
                return records
            records: list[GenericJobRecord] = []
            recovered_ids: set[str] = set()
            for job_id in job_ids:
                try:
                    record = self.load(job_id)
                except JobRecordError:
                    continue
                if record.state.get("terminal"):
                    continue
                records.append(record)
                recovered_ids.add(job_id)
            if recovered_ids != job_ids:
                self._write_active_record_ids(recovered_ids)
            return records

    def _active_record_ids(self) -> set[str] | None:
        path = self.active_records_path
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        raw_ids = (
            value.get("jobs")
            if isinstance(value, Mapping) and value.get("schema_version") == 1
            else None
        )
        if not isinstance(raw_ids, list) or any(
            not isinstance(job_id, str) for job_id in raw_ids
        ):
            return None
        try:
            return {str(UUID(job_id)) for job_id in raw_ids}
        except ValueError:
            return None

    def _set_active_record(self, job_id: str, *, active: bool) -> None:
        _ = job_unit_name(job_id)
        with self.locked_active_records():
            job_ids = self._active_record_ids() or set()
            if active:
                job_ids.add(job_id)
            else:
                job_ids.discard(job_id)
            self._write_active_record_ids(job_ids)

    def _write_active_record_ids(self, job_ids: set[str]) -> None:
        path = self.active_records_path
        temporary = path.with_suffix(".json.tmp")
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(
                    {"schema_version": 1, "jobs": sorted(job_ids)},
                    handle,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            _fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def service_lease_records(self) -> list[GenericJobRecord]:
        """Return the bounded set whose ports remain reserved despite missing artifacts."""
        with self.locked_service_lease_records():
            job_ids = self._service_lease_record_ids()
            if job_ids is None:
                records = [
                    record
                    for record in self.list()
                    if record.spec.lease is not None
                    and not self._service_lease_released(record.job_id)
                ]
                self._write_service_lease_record_ids(
                    {record.job_id for record in records}
                )
                return records
            records: list[GenericJobRecord] = []
            recovered_ids: set[str] = set()
            for job_id in job_ids:
                try:
                    record = self.load(job_id)
                except JobRecordError:
                    continue
                if record.spec.lease is None or self._service_lease_released(job_id):
                    continue
                records.append(record)
                recovered_ids.add(job_id)
            if recovered_ids != job_ids:
                self._write_service_lease_record_ids(recovered_ids)
            return records

    def _service_lease_record_ids(self) -> set[str] | None:
        path = self.service_lease_records_path
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        raw_ids = (
            value.get("jobs")
            if isinstance(value, Mapping) and value.get("schema_version") == 1
            else None
        )
        if not isinstance(raw_ids, list) or any(
            not isinstance(job_id, str) for job_id in raw_ids
        ):
            return None
        try:
            return {str(UUID(job_id)) for job_id in raw_ids}
        except ValueError:
            return None

    def _set_service_lease_record(self, job_id: str, *, active: bool) -> None:
        _ = job_unit_name(job_id)
        with self.locked_service_lease_records():
            job_ids = self._service_lease_record_ids() or set()
            if active:
                job_ids.add(job_id)
            else:
                job_ids.discard(job_id)
            self._write_service_lease_record_ids(job_ids)

    def _write_service_lease_record_ids(self, job_ids: set[str]) -> None:
        path = self.service_lease_records_path
        temporary = path.with_suffix(".json.tmp")
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(
                    {"schema_version": 1, "jobs": sorted(job_ids)},
                    handle,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            _fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, record: GenericJobRecord) -> None:
        path = self._record_path(record.job_id)
        _ensure_durable_directory(path.parent)
        if not record.state.get("terminal"):
            self._set_active_record(record.job_id, active=True)
        if not self.service_lease_records_path.exists():
            self._set_service_lease_record(record.job_id, active=False)
        if record.spec.lease is not None and not self._service_lease_released(
            record.job_id
        ):
            self._set_service_lease_record(record.job_id, active=True)
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
        if record.state.get("terminal"):
            self._set_active_record(record.job_id, active=False)

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
    before_admission_start: Callable[[str], None] | None = None
    notify_socket: Path | None = None
    events: TerminalEvents = field(default_factory=TerminalEvents, repr=False)
    _admission_lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        # Recovery observes only the durable nonterminal set. Terminal lease
        # artifacts carry their own bounded reconciliation path, so a daemon
        # restart cannot serialize systemd calls or per-job locks across the
        # historical corpus.
        if self.store.records_root.exists() or self.store.leases_root.exists():
            records = self.store.recover_service_leases(self.systemd.show)
        else:
            records = []
        self.store.cleanup_inactive_scratch(records)
        self.store.cleanup_inactive_readiness(records)
        finalized: list[GenericJobRecord] = []
        for record in records:
            with self.store.locked(record.job_id):
                record = self.store.load(record.job_id)
                if (
                    record.spec.kind == "declared-operation"
                    and record.state.get("phase") == "launching"
                ):
                    record = self._recover_unpublished_declared_locked(record)
                if record.state.get("terminal"):
                    self._terminal_cleanup(record)
                else:
                    self._get_locked(record.job_id)
                    record = self.store.load(record.job_id)
                    if record.state.get("terminal"):
                        finalized.append(record)
        if finalized:
            with self._admission_lock:
                state = self._admission_state()
                for record in finalized:
                    self._finish_admission(record, state)

    def _recover_unpublished_declared_locked(
        self, record: GenericJobRecord
    ) -> GenericJobRecord:
        """Recover the record/input publication window without guessing at systemd.

        A complete private input proves the durable intent can be queued.  An
        incomplete input is terminal only when systemd authoritatively reports
        that no unit exists; otherwise recovery retains the record and lease.
        """
        try:
            self.store.declared_launch(record.job_id)
        except JobRecordError:
            try:
                properties = self.systemd.show(record.unit)
            except SystemdJobError:
                return record
            if properties.get("LoadState") != "not-found":
                return record
            failed = self._with_state(
                record,
                {
                    "phase": "launch-failed",
                    "terminal": True,
                    "error": {"code": "declared-launch-input-incomplete"},
                    "systemd": dict(properties),
                    "observed_at": _timestamp(),
                },
            )
            self.store.save(failed)
            return failed
        queued = self._with_state(
            record,
            {
                "phase": "queued",
                "terminal": False,
                "observed_at": _timestamp(),
                "subscribers": 1,
                "dependencies": list(record.spec.dependency_job_ids),
                "admission": {
                    "pool": record.spec.pool,
                    "estimate_memory_bytes": self._estimate(
                        record.spec, self._admission_state()
                    ),
                },
            },
        )
        self.store.save(queued)
        return queued

    def _admission_state(self) -> dict[str, Any]:
        path = self.store.admission_path
        if not path.exists():
            return {
                "schema_version": ADMISSION_SCHEMA_VERSION,
                "active": {},
                "cache": {},
                "estimates": {},
            }
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            # Conservatively recover by forgetting optimizations. Existing
            # records/systemd evidence still determine all real jobs.
            return {
                "schema_version": ADMISSION_SCHEMA_VERSION,
                "active": {},
                "cache": {},
                "estimates": {},
            }
        if (
            not isinstance(value, Mapping)
            or value.get("schema_version") != ADMISSION_SCHEMA_VERSION
        ):
            return {
                "schema_version": ADMISSION_SCHEMA_VERSION,
                "active": {},
                "cache": {},
                "estimates": {},
            }
        if not all(
            isinstance(value.get(key), Mapping)
            for key in ("active", "cache", "estimates")
        ):
            return {
                "schema_version": ADMISSION_SCHEMA_VERSION,
                "active": {},
                "cache": {},
                "estimates": {},
            }
        return {
            "schema_version": ADMISSION_SCHEMA_VERSION,
            **{key: dict(value[key]) for key in ("active", "cache", "estimates")},
        }

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
        return dict(
            sorted(
                mapping.items(),
                key=lambda item: (
                    str(item[1].get("touched_at", ""))
                    if isinstance(item[1], Mapping)
                    else ""
                ),
            )[-limit:]
        )

    def start(self, spec: GenericJobSpec, job_id: str | None = None) -> dict[str, Any]:
        candidate = job_id or str(uuid4())
        with self.store.locked(candidate):
            record = self.store.create(spec, candidate)
            try:
                if not self.store.service_lease_ports_available(spec.lease):
                    raise SystemdJobError(
                        "leased loopback port became unavailable before launch"
                    )
                self.systemd.start(
                    unit=record.unit,
                    command=spec.command,
                    working_directory=spec.working_directory,
                    environment=spec.environment,
                    timeout_seconds=spec.timeout_seconds,
                    log_path=record.log_path,
                    json_result_path=record.result_path
                    if spec.result_kind in {"json", "pytest"}
                    else None,
                    **self._notify_arguments(record.job_id),
                )
            except SystemdJobError:
                return self._reconcile_launch_error(record)
            submitted = self._with_state(
                record,
                {"phase": "submitted", "terminal": False, "observed_at": _timestamp()},
            )
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
        principal: str = "operator",
        contract: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if principal not in {"agent-control", "operator"}:
            raise ValueError(
                "declared operations require agent-control or operator principal"
            )
        if checkout is not None and checkout.project_id != project.project_id:
            raise ValueError("declared job checkout belongs to another project")
        with self._admission_lock:
            return self._start_declared_locked(
                project,
                operation,
                correlation_id,
                principal,
                parameters,
                checkout,
                (),
                contract or {},
            )

    def _start_declared_locked(
        self,
        project: ProjectAdapter,
        operation: ProjectOperation,
        correlation_id: str,
        principal: str,
        parameters: Mapping[str, Any],
        checkout: RegisteredCheckout | None,
        lineage: tuple[str, ...],
        contract: Mapping[str, Any],
    ) -> dict[str, Any]:
        if operation.name in lineage:
            raise ValueError("declared operation dependency cycle")
        dependency_jobs = tuple(
            self._start_declared_locked(
                project,
                project.operation(name),
                correlation_id,
                principal,
                {},
                checkout,
                (*lineage, operation.name),
                {},
            )
            for name in operation.dependencies
        )
        dependency_ids = tuple(job["job_id"] for job in dependency_jobs)
        dependency_environment: dict[str, str] = {}
        for dependency_id in dependency_ids:
            dependency = self.store.load(dependency_id)
            if dependency.spec.lease is None:
                continue
            for port in dependency.spec.lease.ports:
                existing = dependency_environment.get(port.environment)
                if existing is not None and existing != str(port.port):
                    raise ValueError(
                        f"declared operation dependencies provide conflicting {port.environment} leases"
                    )
                dependency_environment[port.environment] = str(port.port)
        operation_argv, parameter_digest = operation.derive_argv(parameters)
        workdir = checkout.path if checkout is not None else project.root
        environment = project.environment.values()
        tree = self._cache_tree(workdir)
        coalesce_key = (
            self._operation_identity_key(
                project,
                operation,
                parameter_digest,
                principal,
                environment,
                tree,
                checkout,
            )
            if operation.service is None or operation.cache == "tree+environment"
            else None
        )
        cache_key = coalesce_key if operation.cache == "tree+environment" else None
        state = self._admission_state()
        if cache_key is not None:
            cached = state["cache"].get(cache_key)
            if isinstance(cached, Mapping) and isinstance(cached.get("job_id"), str):
                try:
                    record = self.store.load(cached["job_id"])
                except JobRecordError:
                    state["cache"].pop(cache_key, None)
                else:
                    if record.state.get("phase") == "succeeded" and record.state.get(
                        "terminal"
                    ):
                        response = self._public(record, record.state)
                        response["reused"] = True
                        return response
        if coalesce_key is not None:
            active_id = state["active"].get(coalesce_key)
            if isinstance(active_id, str):
                try:
                    record = self.store.load(active_id)
                except JobRecordError:
                    state["active"].pop(coalesce_key, None)
                else:
                    if not record.state.get("terminal"):
                        subscribers = int(record.state.get("subscribers", 1)) + 1
                        updated = self._with_state(
                            record,
                            {
                                **record.state,
                                "subscribers": subscribers,
                                "coalesced": True,
                            },
                        )
                        self.store.save(updated)
                        response = self._public(updated, updated.state)
                        response["coalesced"] = True
                        return response
        job_id = str(uuid4())
        readiness_path = (
            self.store.prepare_service_readiness(job_id)
            if operation.service is not None
            and operation.service.readiness == "project-command"
            else None
        )
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
        estimate_key = f"{project.project_id}:{operation.name}"
        learned = state["estimates"].get(estimate_key)
        estimate = (
            learned.get("bytes")
            if isinstance(learned, Mapping)
            else operation.estimate_memory_bytes
        )

        def build_spec(lease: ServiceLease | None) -> GenericJobSpec:
            launch_environment = dict(environment)
            launch_environment.update(dependency_environment)
            if lease is not None:
                launch_environment.update(
                    {port.environment: str(port.port) for port in lease.ports}
                )
                if readiness_path is not None:
                    launch_environment["SINNIXD_SERVICE_READY_FILE"] = str(
                        readiness_path
                    )
            scratch_path = self.store.scratch_path_for(operation.scratch, job_id)
            payload_overrides: dict[str, str] = {}
            if scratch_path is not None:
                launch_environment["TMPDIR"] = str(scratch_path)
                payload_overrides["TMPDIR"] = str(scratch_path)
            return GenericJobSpec(
                kind="declared-operation",
                command=project.environment.command_for(
                    operation_argv, overrides=payload_overrides
                ),
                working_directory=str(workdir),
                environment=launch_environment,
                project_id=project.project_id,
                operation=operation.name,
                parameter_digest=parameter_digest,
                principal=principal,
                timeout_seconds=operation.timeout_seconds,
                checkout=checkout.to_dict() if checkout is not None else None,
                contract=dict(contract),
                result_kind={"exit": "exit-status", "json": "json", "pytest": "pytest"}[
                    operation.result
                ],
                pool=operation.pool,
                exclusive_keys=operation.exclusive_keys,
                dependency_job_ids=dependency_ids,
                coalesce_key=coalesce_key,
                cache_key=cache_key,
                estimate_key=estimate_key,
                estimate_memory_bytes=estimate,
                scratch=operation.scratch,
                lease=lease,
            )

        spec = build_spec(None)
        try:
            if operation.service is None:
                record = self.store.create(spec, job_id)
            else:
                record = self.store.create_declared_service_record(
                    job_id=job_id,
                    service=operation.service,
                    build_spec=build_spec,
                )
        except BaseException:
            raise
        try:
            if operation.service is None:
                self.store.write_declared_launch(
                    job_id, record.spec.command, record.spec.environment
                )
        except BaseException:
            self.store.cleanup_scratch(record)
            raise
        queued = self._with_state(
            record,
            {
                "phase": "queued",
                "terminal": False,
                "observed_at": _timestamp(),
                "subscribers": 1,
                "dependencies": list(dependency_ids),
                "admission": {
                    "pool": spec.pool,
                    "estimate_memory_bytes": self._estimate(spec, state),
                },
            },
        )
        self.store.save(queued)
        if coalesce_key is not None:
            state["active"][coalesce_key] = job_id
        self._save_admission_state(state)
        self._admit_locked()
        record = self.store.load(job_id)
        return self._public(record, record.state)

    @staticmethod
    def _cache_tree(path: Path) -> str | None:
        try:
            clean = subprocess.run(
                ["git", "-C", str(path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if clean.returncode != 0 or clean.stdout:
                return None
            tree = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD^{tree}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return (
                tree.stdout.strip()
                if tree.returncode == 0 and len(tree.stdout.strip()) == 40
                else None
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

    @staticmethod
    def _operation_identity_key(
        project: ProjectAdapter,
        operation: ProjectOperation,
        parameter_digest: str,
        principal: str,
        environment: Mapping[str, str],
        tree: str | None,
        checkout: RegisteredCheckout | None,
    ) -> str | None:
        if tree is None:
            return None
        payload = {
            "project": project.project_id,
            "operation": operation.name,
            "parameters": parameter_digest,
            "principal": principal,
            "tree": tree,
            "environment": dict(sorted(environment.items())),
        }
        if operation.service is not None:
            payload["service_scope"] = {
                "project_root": str(project.root.resolve()),
                "checkout": checkout.to_dict() if checkout is not None else None,
            }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _estimate(spec: GenericJobSpec, state: Mapping[str, Any]) -> int:
        estimate = (
            spec.estimate_memory_bytes
            if spec.estimate_memory_bytes is not None
            else POOL_POLICIES[spec.pool]["default_estimate"]
        )
        # A pool budget governs concurrent accounting, not whether a lone job
        # may ever run. Historical peaks can exceed that budget (the process is
        # still contained by its systemd slice); without this cap such a job is
        # permanently unadmittable even when the pool is empty.
        return min(estimate, POOL_POLICIES[spec.pool]["memory_budget"])

    def _admit_locked(self) -> None:
        state = self._admission_state()
        records = self.store.active_records()
        active: dict[str, list[GenericJobRecord]] = {pool: [] for pool in POOL_POLICIES}
        for record in records:
            if (
                record.spec.kind == "declared-operation"
                and not record.state.get("terminal")
                and record.state.get("phase")
                in {
                    "submitted",
                    "running",
                    "cancelling",
                    "stopping",
                    "launch-unknown",
                    "observation-unknown",
                    "outcome-unknown",
                }
            ):
                active[record.spec.pool].append(record)
        pressure = self.pressure_probe()
        for snapshot in records:
            if snapshot.spec.kind != "declared-operation":
                continue
            # Dependency observations acquire their own job locks.  Do them
            # before the candidate lock so admission never nests job locks in
            # an order determined by the dependency graph.
            blocked = self._dependency_block(snapshot)
            with self.store.locked(snapshot.job_id):
                record = self.store.load(snapshot.job_id)
                if record.state.get("terminal") or record.state.get("phase") not in {
                    "queued",
                    "waiting-dependencies",
                }:
                    continue
                if blocked is not None:
                    updated = self._with_state(record, blocked)
                    self.store.save(updated)
                    if blocked.get("terminal"):
                        self._terminal_cleanup(updated)
                        self._finish_admission(updated, state)
                    continue
                policy = POOL_POLICIES[record.spec.pool]
                estimate = self._estimate(record.spec, state)
                occupied = sum(
                    self._estimate(item.spec, state)
                    for item in active[record.spec.pool]
                )
                exclusive = {
                    key
                    for pool_records in active.values()
                    for item in pool_records
                    for key in item.spec.exclusive_keys
                }
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
            if self.before_admission_start is not None:
                self.before_admission_start(record.job_id)
            terminal: GenericJobRecord | None = None
            submitted: GenericJobRecord | None = None
            with self.store.locked(record.job_id):
                current = self.store.load(record.job_id)
                if current.state.get("terminal") or current.state.get("phase") not in {
                    "queued",
                    "waiting-dependencies",
                }:
                    continue
                try:
                    if not self.store.service_lease_ports_available(current.spec.lease):
                        raise SystemdJobError(
                            "leased loopback port became unavailable before launch"
                        )
                    command, environment = self.store.declared_launch(current.job_id)
                    if scratch_path := self.store.prepare_scratch(current):
                        environment["TMPDIR"] = str(scratch_path)
                    if current.spec.checkout is not None:
                        revalidate_registered_checkout(current.spec.checkout)
                        # The contract runner repeats this proof in the unit
                        # before it execs the project command. Git worktrees
                        # have no lock we can share with arbitrary writers, so
                        # this closes the check-to-exec interval as well as the
                        # admission boundary itself.
                        from .contracts import contract_runner_executable

                        command = (
                            str(contract_runner_executable()),
                            "--declared",
                            "--job-id",
                            current.job_id,
                            "--unit",
                            current.unit,
                            "--state-root",
                            str(self.store.root),
                        )
                    self.systemd.start(
                        unit=current.unit,
                        command=command,
                        working_directory=current.spec.working_directory,
                        environment=environment,
                        timeout_seconds=current.spec.timeout_seconds,
                        log_path=current.log_path,
                        json_result_path=current.result_path
                        if current.spec.result_kind in {"json", "pytest"}
                        else None,
                        **self._notify_arguments(current.job_id),
                    )
                except SystemdJobError:
                    self._reconcile_launch_error(current)
                    terminal = self.store.load(current.job_id)
                except (JobRecordError, ProjectConfigError):
                    terminal = self._with_state(
                        current,
                        {
                            "phase": "launch-failed",
                            "terminal": True,
                            "launch_evidence": "not-started",
                            "observed_at": _timestamp(),
                        },
                    )
                    self.store.save(terminal)
                    self._terminal_cleanup(terminal)
                else:
                    submitted = self._with_state(
                        current,
                        {
                            **current.state,
                            "phase": "submitted",
                            "terminal": False,
                            "observed_at": _timestamp(),
                        },
                    )
                    self.store.save(submitted)
            if terminal is not None and terminal.state.get("terminal"):
                self._terminal_cleanup(terminal)
                self._finish_admission(terminal, state)
            elif submitted is not None:
                active[submitted.spec.pool].append(submitted)

    def _dependency_block(self, record: GenericJobRecord) -> Mapping[str, Any] | None:
        for job_id in record.spec.dependency_job_ids:
            try:
                with self.store.locked(job_id):
                    dependency = self._get_locked(job_id)
            except JobRecordError:
                return {
                    "phase": "dependency-failed",
                    "terminal": True,
                    "launch_evidence": "not-started",
                    "observed_at": _timestamp(),
                }
            if (
                dependency["state"].get("terminal")
                and dependency["state"].get("phase") != "succeeded"
            ):
                return {
                    "phase": "dependency-failed",
                    "terminal": True,
                    "launch_evidence": "not-started",
                    "observed_at": _timestamp(),
                    "dependencies": list(record.spec.dependency_job_ids),
                }
            if not dependency["state"].get("terminal"):
                dependency_record = self.store.load(job_id)
                lease = dependency_record.spec.lease
                if (
                    lease is not None
                    and dependency["state"].get("phase") in {"submitted", "running"}
                    and (lease.readiness == "none" or self.store.service_ready(job_id))
                    and all(
                        not _loopback_port_available(port.port) for port in lease.ports
                    )
                ):
                    continue
                return {
                    "phase": "waiting-dependencies",
                    "terminal": False,
                    "observed_at": _timestamp(),
                    "dependencies": list(record.spec.dependency_job_ids),
                }
        return None

    def _finish_admission(
        self, record: GenericJobRecord, state: dict[str, Any]
    ) -> None:
        active_key = record.spec.coalesce_key or record.spec.cache_key
        if active_key is not None and state["active"].get(active_key) == record.job_id:
            state["active"].pop(active_key, None)
        if (
            record.state.get("phase") == "succeeded"
            and record.spec.lease is None
            and record.spec.cache_key is not None
            and (
                record.spec.result_kind == "exit-status"
                or self._has_authoritative_result(record)
            )
        ):
            state["cache"][record.spec.cache_key] = {
                "job_id": record.job_id,
                "touched_at": _timestamp(),
            }
            state["cache"] = self._bounded(state["cache"], MAX_ADMISSION_CACHE_ENTRIES)
        peak = self._memory_peak(record.state.get("systemd", {}))
        if (
            record.state.get("phase") == "succeeded"
            and peak is not None
            and record.spec.estimate_key is not None
        ):
            state["estimates"][record.spec.estimate_key] = {
                "bytes": peak,
                "touched_at": _timestamp(),
            }
            state["estimates"] = self._bounded(
                state["estimates"], MAX_ADMISSION_ESTIMATES
            )
        self._save_admission_state(state)

    def _terminal_cleanup(self, record: GenericJobRecord) -> None:
        self.events.fire(record.job_id)
        self.store.cleanup_scratch(record)
        self.store.cleanup_service_readiness(record.job_id)
        if record.spec.kind == "declared-operation":
            self.store.cleanup_declared_launch(record.job_id)
        self.store.release_terminal_service_lease(record)

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
        principal: str = "agent-control",
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
                principal=principal,
            ),
            job_id,
        )

    def get(self, job_id: str) -> dict[str, Any]:
        with self.store.locked(job_id):
            status = self._get_locked(job_id)
        with self._admission_lock:
            if status["state"].get("terminal"):
                self._finish_admission(self.store.load(job_id), self._admission_state())
            self._admit_locked()
        return status

    def list(
        self,
        *,
        principal: str = "operator",
        limit: int = 100,
        cursor: str | None = None,
        project_id: str | None = None,
        phases: tuple[str, ...] = (),
        active_only: bool = False,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 1_000:
            raise ValueError("job list limit must be between 1 and 1000")
        if project_id is not None and (
            not isinstance(project_id, str) or not project_id
        ):
            raise ValueError("job list project_id must be a non-empty string")
        if any(not isinstance(phase, str) or not phase for phase in phases):
            raise ValueError("job list phases must be non-empty strings")
        query = {
            "active_only": active_only,
            "phases": sorted(set(phases)),
            "project_id": project_id,
        }
        with self._admission_lock:
            self._admit_locked()
        records = sorted(
            (
                record
                for record in self.store.list()
                if principal == "operator" or record.spec.principal == principal
                if project_id is None or record.spec.project_id == project_id
                if not query["phases"] or record.state.get("phase") in query["phases"]
                if not active_only or not record.state.get("terminal", False)
            ),
            key=_job_order_key,
            reverse=True,
        )
        if cursor is None:
            snapshot = _job_order_key(records[0]) if records else ("", "")
            after: tuple[str, str] | None = None
        else:
            snapshot, after = _decode_job_list_cursor(
                cursor, principal=principal, query=query
            )
        snapshot_records = [
            record for record in records if _job_order_key(record) <= snapshot
        ]
        if after is not None:
            snapshot_records = [
                record for record in snapshot_records if _job_order_key(record) < after
            ]
        page_records = snapshot_records[: limit + 1]
        has_more = len(page_records) > limit
        records = page_records[:limit]
        next_cursor = (
            _encode_job_list_cursor(
                principal=principal,
                query=query,
                snapshot=snapshot,
                after=_job_order_key(records[-1]),
            )
            if has_more and records
            else None
        )
        return {
            "jobs": [
                self._public(record, record.state)
                if record.state.get("terminal")
                else self.get(record.job_id)
                for record in records
            ],
            "limit": limit,
            "query": query,
            "total": len(snapshot_records) if after is None else None,
            "truncated": has_more,
            "next_cursor": next_cursor,
            "snapshot": {
                "ordering": "created_at_desc_job_id_desc",
                "ceiling": list(snapshot),
            },
        }

    def wait(
        self, job_id: str, timeout_seconds: int = DEFAULT_WAIT_SECONDS
    ) -> dict[str, Any]:
        if not 1 <= timeout_seconds <= MAX_WAIT_SECONDS:
            raise ValueError(
                f"wait timeout_seconds must be between 1 and {MAX_WAIT_SECONDS}"
            )
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with self.store.locked(job_id):
                    record = self.store.load(job_id)
                    return {
                        **self._public(record, record.state),
                        "wait_timed_out": True,
                    }
            with self.store.locked(job_id):
                status = self._get_locked(
                    job_id,
                    systemd_timeout_seconds=min(
                        SYSTEMD_COMMAND_TIMEOUT_SECONDS, remaining
                    ),
                    wait_deadline=deadline,
                )
            with self._admission_lock:
                self._admit_locked()
            if status["state"]["terminal"]:
                return status
            if time.monotonic() >= deadline:
                return {**status, "wait_timed_out": True}
            self.events.wait_terminal(
                (job_id,),
                min(self.wait_poll_seconds, max(0.0, deadline - time.monotonic())),
            )

    def wait_any(
        self, job_ids: Sequence[str], timeout_seconds: int = DEFAULT_WAIT_SECONDS
    ) -> dict[str, Any]:
        """Return the first terminal job among ``job_ids``, or a bounded timeout."""
        if not 1 <= timeout_seconds <= MAX_WAIT_SECONDS:
            raise ValueError(
                f"wait timeout_seconds must be between 1 and {MAX_WAIT_SECONDS}"
            )
        if (
            not job_ids
            or len(job_ids) > MAX_WAIT_ANY_JOBS
            or len(set(job_ids)) != len(job_ids)
        ):
            raise ValueError(
                f"wait_any requires 1-{MAX_WAIT_ANY_JOBS} distinct job ids"
            )
        deadline = time.monotonic() + timeout_seconds
        while True:
            phases: dict[str, Any] = {}
            for job_id in job_ids:
                with self.store.locked(job_id):
                    status = self._get_locked(job_id)
                with self._admission_lock:
                    self._admit_locked()
                if status["state"]["terminal"]:
                    return {**status, "completed_job_id": job_id}
                phases[job_id] = status["state"].get("phase")
            if time.monotonic() >= deadline:
                return {"wait_timed_out": True, "jobs": phases}
            self.events.wait_terminal(
                job_ids,
                min(self.wait_poll_seconds, max(0.0, deadline - time.monotonic())),
            )

    def _notify_arguments(self, job_id: str) -> dict[str, Any]:
        """Capture notify args only when configured, so fakes with strict
        start signatures keep proving the unextended launch contract."""
        if self.notify_socket is None:
            return {}
        return {"notify_socket": self.notify_socket, "notify_job_id": job_id}

    def notify_exit(self, job_id: str) -> dict[str, Any]:
        """Record a capture-reported exit as a wake-up; observation stays authoritative."""
        _ = job_unit_name(job_id)
        _ = self.store.load(job_id)
        self.events.fire(job_id)
        return {"job_id": job_id, "notified": True}

    def cancel(self, job_id: str) -> dict[str, Any]:
        terminal: GenericJobRecord | None = None
        with self.store.locked(job_id):
            status = self._get_locked(job_id)
            if status["state"]["terminal"]:
                return {**status, "cancel_requested": False, "already_terminal": True}
            record = self.store.load(job_id)
            if record.state.get("phase") in {"queued", "waiting-dependencies"}:
                cancelled = self._with_state(
                    record,
                    {
                        "phase": "cancelled",
                        "terminal": True,
                        "launch_evidence": "not-started",
                        "observed_at": _timestamp(),
                    },
                )
                self.store.save(cancelled)
                terminal = cancelled
                response = {
                    **self._public(cancelled, cancelled.state),
                    "cancel_requested": True,
                    "already_terminal": False,
                }
            else:
                intent = self._with_cancel_intent(
                    record, status["state"].get("systemd", {}).get("InvocationID")
                )
                self.store.save(intent)
                self.systemd.stop(intent.unit)
                acknowledged = self._with_stop_acknowledgement(
                    intent,
                    status["state"].get("systemd", {}).get("InvocationID"),
                )
                self.store.save(acknowledged)
                response = {
                    **self._get_locked(job_id),
                    "cancel_requested": True,
                    "already_terminal": False,
                }
        with self._admission_lock:
            if terminal is not None:
                self._terminal_cleanup(terminal)
                self._finish_admission(terminal, self._admission_state())
            elif response["state"].get("terminal"):
                self._finish_admission(self.store.load(job_id), self._admission_state())
            self._admit_locked()
        return response

    def logs(
        self, job_id: str, *, offset: int = 0, max_bytes: int = MAX_LOG_BYTES
    ) -> dict[str, Any]:
        if offset < 0 or not 1 <= max_bytes <= MAX_LOG_BYTES:
            raise ValueError(
                f"log range must use offset >= 0 and max_bytes between 1 and {MAX_LOG_BYTES}"
            )
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

    def result(
        self, job_id: str, *, max_bytes: int = MAX_RESULT_BYTES
    ) -> dict[str, Any]:
        if not 1 <= max_bytes <= MAX_RESULT_BYTES:
            raise ValueError(
                f"result max_bytes must be between 1 and {MAX_RESULT_BYTES}"
            )
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
                "value": self._parse_exit_result(record),
            }
        content = _read_private_artifact(record.result_path, MAX_RESULT_BYTES)
        if content is None:
            raise JobResultError("job result artifact is unavailable")
        artifact = {
            "ref": f"sinnix://jobs/{job_id}/artifacts/result",
            "max_bytes": MAX_RESULT_BYTES,
            "kind": record.spec.result_kind,
        }
        if (
            len(content) > MAX_RESULT_BYTES
            or record.result_path.with_suffix(".overflow").exists()
        ):
            raise JobResultError("job result exceeds the artifact limit")
        if record.spec.result_kind in {"json", "pytest"}:
            if len(content) > max_bytes:
                raise JobResultLimitError(
                    "job JSON result exceeds the requested response limit"
                )
            value = self._parse_json_result(content)
            return {
                "job_id": job_id,
                "kind": record.spec.result_kind,
                "value": value,
                "artifact": artifact,
            }
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

    def _parse_exit_result(self, record: GenericJobRecord) -> dict[str, Any]:
        state = record.state
        properties = state.get("systemd")
        phase = state.get("phase")
        if (
            isinstance(properties, Mapping)
            and properties.get("LoadState") == "loaded"
            and phase
            in {
                "succeeded",
                "failed",
                "timed_out",
                "cancelled",
            }
        ):
            status = properties.get("ExecMainStatus")
            result = properties.get("Result")
            if not isinstance(result, str) or not result:
                raise JobResultError("job exit result is unavailable")
            try:
                return {"code": int(status), "result": result}
            except (TypeError, ValueError) as error:
                raise JobResultError("job exit result is malformed") from error
        if (
            phase == "succeeded"
            and state.get("result_evidence") == "completed"
            and self._has_authoritative_result(record)
        ):
            return {"code": 0, "result": "success"}
        raise JobResultError("job exit result is unavailable")

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
        if record.state.get(
            "terminal"
        ) and not self._terminal_state_requires_reconciliation(record):
            self._terminal_cleanup(record)
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
        if self._observation_unchanged(record, updated):
            return self._public(record, state)
        self.store.save(updated)
        if state.get("terminal"):
            self._terminal_cleanup(updated)
        return self._public(updated, state)

    @staticmethod
    def _observation_unchanged(
        record: GenericJobRecord, updated: GenericJobRecord
    ) -> bool:
        """True when a re-observation would rewrite only its own timestamp.

        Skipping the durable save then spares an fsync pair per poll on the
        wear-limited state volume without dropping any state transition.
        """
        before = {key: value for key, value in record.state.items() if key != "observed_at"}
        after = {key: value for key, value in updated.state.items() if key != "observed_at"}
        return before == after

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
                "systemd": dict(properties),
                "observed_at": _timestamp(),
            }
            updated = self._with_state(record, state)
            self.store.save(updated)
            self._terminal_cleanup(updated)
            return self._public(updated, state)
        state = self._classify(properties, record)
        updated = self._with_state(record, state)
        self.store.save(updated)
        if state.get("terminal"):
            self._terminal_cleanup(updated)
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

    def _classify(
        self, properties: Mapping[str, str], record: GenericJobRecord
    ) -> dict[str, Any]:
        if self._is_authoritative_not_started_cancellation(record):
            return dict(record.state)
        if properties.get("LoadState") != "loaded":
            if record.spec.kind == "declared-operation" and record.state.get(
                "phase"
            ) in {
                "launching",
                "queued",
                "waiting-dependencies",
            }:
                return {
                    "phase": record.state["phase"],
                    "terminal": False,
                    "systemd": dict(properties),
                    "observed_at": _timestamp(),
                }
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
                terminal = self._cancellation_reconciliation_grace_expired(record)
                return {
                    "phase": "outcome-unknown",
                    "terminal": terminal,
                    "systemd": dict(properties),
                    "cancellation": self._cancel_intent(record),
                    **(
                        {"outcome_evidence": "unit-collected-after-cancellation-grace"}
                        if terminal
                        else {}
                    ),
                    "observed_at": _timestamp(),
                }
            return {
                "phase": "missing",
                "terminal": True,
                "systemd": dict(properties),
                "observed_at": _timestamp(),
            }
        if record.spec.lease is not None:
            bound = record.state.get("lease_invocation_id")
            invocation = properties.get("InvocationID")
            if isinstance(bound, str) and bound and bound != invocation:
                return {
                    "phase": "observation-unknown",
                    "error": {"code": SYSTEMD_ERROR_CODE},
                    "terminal": False,
                    "systemd": dict(properties),
                    "lease_invocation_id": bound,
                    "observed_at": _timestamp(),
                }
        if self._has_schema_v3_native_success(record, properties):
            return self._with_service_lease_invocation(
                record,
                properties,
                {
                    "phase": "succeeded",
                    "terminal": True,
                    "systemd": dict(properties),
                    "result_evidence": "native-v3",
                    "observed_at": _timestamp(),
                },
            )
        active = properties.get("ActiveState", "unknown")
        if active in {"active", "activating", "reloading"}:
            phase = "running"
            terminal = False
        elif active == "deactivating":
            phase = (
                "cancelling" if record.cancel_requested_at is not None else "stopping"
            )
            terminal = False
        elif (
            properties.get("Result") == "success"
            and properties.get("ExecMainStatus") == "0"
        ):
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
        return self._with_service_lease_invocation(
            record,
            properties,
            {
                "phase": phase,
                "terminal": terminal,
                "systemd": dict(properties),
                "observed_at": _timestamp(),
            },
        )

    @staticmethod
    def _with_service_lease_invocation(
        record: GenericJobRecord,
        properties: Mapping[str, str],
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        if record.spec.lease is None:
            return dict(state)
        invocation = properties.get("InvocationID")
        if not isinstance(invocation, str) or not invocation:
            return dict(state)
        return {**state, "lease_invocation_id": invocation}

    @staticmethod
    def _cancellation_reconciliation_grace_expired(record: GenericJobRecord) -> bool:
        if record.cancel_requested_at is None:
            return False
        try:
            requested_at = datetime.fromisoformat(record.cancel_requested_at)
        except ValueError:
            return False
        if requested_at.tzinfo is None:
            return False
        return (
            datetime.now(UTC) - requested_at
        ).total_seconds() >= CANCEL_OUTCOME_RECONCILIATION_GRACE_SECONDS

    def _terminal_state_requires_reconciliation(self, record: GenericJobRecord) -> bool:
        if self._is_authoritative_not_started_cancellation(record):
            return False
        if (
            record.spec.lease is not None
            and not self.store._service_lease_released(record.spec.lease.lease_id)
            and not self.store._terminal_service_lease_releasable(record)
        ):
            return True
        phase = record.state.get("phase")
        properties = record.state.get("systemd")
        if not isinstance(properties, Mapping):
            properties = {}
        if phase == "succeeded" and properties.get("LoadState") != "loaded":
            return not self._has_authoritative_result(record)
        if phase == "cancelled" and not self._stop_acknowledgement_matches(record):
            return properties.get("LoadState") != "loaded" or not self._cancel_matches(
                properties, record
            )
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

    def _has_schema_v3_native_success(
        self, record: GenericJobRecord, properties: Mapping[str, str]
    ) -> bool:
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
    def _with_state(
        record: GenericJobRecord, state: Mapping[str, Any]
    ) -> GenericJobRecord:
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
    def _with_cancel_intent(
        record: GenericJobRecord, invocation_id: Any
    ) -> GenericJobRecord:
        existing_intent = record.cancel_requested_at is not None
        observed_invocation = (
            invocation_id if isinstance(invocation_id, str) and invocation_id else None
        )
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
                record.cancel_requested_invocation_id
                if existing_intent
                else observed_invocation
            ),
            cancel_stop_acknowledged_at=record.cancel_stop_acknowledged_at,
            cancel_stop_acknowledged_invocation_id=record.cancel_stop_acknowledged_invocation_id,
            state=dict(record.state),
        )

    @staticmethod
    def _with_stop_acknowledgement(
        record: GenericJobRecord, invocation_id: Any
    ) -> GenericJobRecord:
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
    def _cancel_matches(
        properties: Mapping[str, str], record: GenericJobRecord
    ) -> bool:
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
            and record.cancel_stop_acknowledged_invocation_id
            == record.cancel_requested_invocation_id
        )

    @staticmethod
    def _is_authoritative_not_started_cancellation(record: GenericJobRecord) -> bool:
        return (
            record.state.get("phase") == "cancelled"
            and record.state.get("terminal") is True
            and record.state.get("launch_evidence") == "not-started"
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

    def _public(
        self, record: GenericJobRecord, state: Mapping[str, Any]
    ) -> dict[str, Any]:
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
            "checkout": dict(record.spec.checkout)
            if record.spec.checkout is not None
            else None,
            "contract": dict(record.spec.contract),
            "created_at": record.created_at,
            "timeout_seconds": record.spec.timeout_seconds,
            "lease": (
                {
                    **record.spec.lease.to_dict(),
                    "state": (
                        "released"
                        if state.get("terminal")
                        and self.store._service_lease_released(
                            record.spec.lease.lease_id
                        )
                        else "active"
                    ),
                }
                if record.spec.lease is not None
                else None
            ),
            "artifacts": {
                "log": {
                    "ref": f"sinnix://jobs/{record.job_id}/artifacts/log",
                    "max_bytes": MAX_LOG_BYTES,
                },
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
        json.dumps(
            parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
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
    parser.add_argument("--notify-socket", type=Path)
    parser.add_argument("--notify-job-id")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(arguments)
    if (
        not parsed.command
        or parsed.command[0] != "--"
        or not 1 <= parsed.max_bytes <= MAX_LOG_ARTIFACT_BYTES
        or (parsed.result_path is None) != (parsed.result_overflow_path is None)
        or (parsed.notify_socket is None) != (parsed.notify_job_id is None)
    ):
        parser.error(
            "requires --max-bytes within the artifact cap and a command after --"
        )
    command = parsed.command[1:]
    remaining = parsed.max_bytes
    overflowed = False
    log_handle = _open_preallocated_private_artifact(parsed.log_path)
    result_handle = (
        _open_private_artifact(parsed.result_path)
        if parsed.result_path is not None
        else None
    )
    result_remaining = MAX_RESULT_BYTES
    result_overflowed = False
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
            if parsed.result_path is not None
            else subprocess.STDOUT,
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
    if parsed.notify_socket is not None and parsed.notify_job_id is not None:
        try:
            notify_job_exit(parsed.notify_socket, parsed.notify_job_id, return_code)
        except (OSError, ValueError):
            pass
    return return_code


def capture_cli() -> None:
    raise SystemExit(capture_main())


if __name__ == "__main__":
    raise SystemExit(
        capture_main(
            sys.argv[2:] if len(sys.argv) > 1 and sys.argv[1] == "capture" else None
        )
    )
