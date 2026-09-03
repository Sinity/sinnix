from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Condition, Event, Lock, RLock
from typing import Any, Iterable, Iterator
from uuid import UUID, uuid4

from . import pueue, queue_run
from .limits import (
    DEFAULT_TIMEOUT_SECONDS,
    maximum_timeout_seconds,
    valid_timeout_seconds,
)
from .projects import (
    ProjectAdapter,
    ProjectConfigError,
    ProjectOperation,
    RegisteredCheckout,
    revalidate_registered_checkout,
)
from .pueue import PueueError, PueueGroupError, Task

DEFAULT_WAIT_SECONDS = 30
MAX_WAIT_SECONDS = 3600
MAX_TERMINAL_EVENT_ENTRIES = 4096
MAX_EVENT_SPOOL_BYTES = 64 * 1024 * 1024
SYSTEMD_COMMAND_TIMEOUT_SECONDS = 0.25
MAX_LOG_BYTES = 64_000
MAX_LOG_ARTIFACT_BYTES = 1_048_576
MAX_RESULT_BYTES = 64_000
MAX_HANDOFF_BYTES = 64_000
JOB_SCHEMA_VERSION = 7
JOB_UNIT_PREFIX = "sinnixd-job-"
QUEUE_ERROR_CODE = "queue-job-error"
QUEUE_CONFIGURATION_ERROR_CODE = "queue-configuration-error"
SCHEDULE_STATE_SCHEMA_VERSION = 1
SCHEDULE_UNIT_PREFIX = "sinnixd-schedule-"
CAPACITY_SCHEMA_VERSION = 1
CAPACITY_RETRY_DELAYS_SECONDS = (5, 30, 120)
# pueue's group name grammar; sinnixd only validates shape and passes it
# through as the pueue group name.
_POOL_NAME = re.compile(r"[a-z][a-z0-9-]{0,63}")


def default_state_dir() -> Path:
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        / "sinnixd"
    )


def scheduled_operation_id(project_id: str, operation_name: str) -> str:
    return f"{project_id}:{operation_name}"


def scheduled_timer_unit(schedule_id: str) -> str:
    return SCHEDULE_UNIT_PREFIX + hashlib.sha256(schedule_id.encode()).hexdigest()[:24]


class JobRecordError(ValueError):
    """Raised when a persisted job record cannot be reconstructed safely."""


class JobResultError(ValueError):
    """Raised when a declared result artifact is unavailable or invalid."""


class JobResultLimitError(JobResultError):
    """Raised when a valid declared result exceeds the caller's response bound."""


def _job_order_key(record: "GenericJobRecord") -> tuple[str, str]:
    return record.created_at, record.job_id


def _dimensions(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("job dimensions must be an object")
    allowed = (str, int, float, bool, type(None))
    if any(
        not isinstance(key, str)
        or not key
        or not isinstance(item, allowed)
        or isinstance(item, (bytes, bytearray))
        for key, item in value.items()
    ):
        raise ValueError("job dimensions must map names to scalar JSON values")
    return dict(value)


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
    """Open a store-reserved artifact without accepting a replacement link."""
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


def timer_persistent(on_calendar: str) -> bool:
    """Catch up a missed daily or weekly run; never a sub-hourly one.

    A transient timer has no trigger stamp, so a persistent one fires the
    moment it is registered. Every daemon restart re-registers all timers,
    which ran the ten-minute sweep twice at each deploy; a missed sub-hourly
    tick is harmless, while a missed nightly corpus run is a lost night.
    """
    spec = on_calendar.strip()
    return not (spec.startswith("*:") or spec.startswith("*-*-* *:"))


class TimerError(RuntimeError):
    """Raised when systemd cannot register or inspect a calendar timer."""


@dataclass(frozen=True)
class UserSystemdJobs:
    """Register and reconcile calendar timers through the user manager.

    pueue executes and observes every job; systemd's only remaining role is
    the durable wake-up a calendar schedule needs, which pueue does not
    provide.
    """

    def schedule_timer(
        self, *, unit: str, on_calendar: str, command: Sequence[str]
    ) -> None:
        self._run(
            [
                "systemd-run",
                "--user",
                "--quiet",
                f"--unit={unit}",
                f"--on-calendar={on_calendar}",
                f"--timer-property=Persistent={'true' if timer_persistent(on_calendar) else 'false'}",
                "--",
                *command,
            ]
        )

    def timer_exists(self, unit: str) -> bool:
        try:
            output = self._run(
                [
                    "systemctl",
                    "--user",
                    "show",
                    f"{unit}.timer",
                    "--property=LoadState",
                ]
            )
        except TimerError:
            return False
        return output.strip() == "LoadState=loaded"

    def unschedule_timer(self, unit: str) -> None:
        try:
            self._run(
                [
                    "systemctl",
                    "--user",
                    "stop",
                    f"{unit}.timer",
                    f"{unit}.service",
                ]
            )
        except TimerError:
            # Registration is reconciled from the durable schedule map. A
            # missing transient unit is already the desired state.
            return

    @staticmethod
    def _run(
        args: Sequence[str], *, timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS
    ) -> str:
        try:
            result = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as error:
            raise TimerError(f"systemd command is unavailable: {args[0]}") from error
        except subprocess.TimeoutExpired as error:
            raise TimerError("systemd command timed out") from error
        except OSError as error:
            raise TimerError(f"systemd command failed: {args[0]}: {error}") from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.strip() or error.stdout.strip() or str(error)
            raise TimerError(detail) from error
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
    costs one extra bounded observation. pueue's own task state remains the
    sole state authority.
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


_USAGE_NUMBER = r"([0-9][0-9,]*)"


def parse_backend_usage(log: str) -> dict[str, int | str | None]:
    """Parse only explicit backend usage fields, retaining nulls when absent."""
    usage: dict[str, int | str | None] = {
        "input_tokens": None,
        "output_tokens": None,
        "cached_tokens": None,
        "model": None,
    }

    def number(value: Any) -> int | None:
        try:
            parsed = int(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    def update(value: Mapping[str, Any]) -> None:
        aliases = {
            "input_tokens": ("input_tokens", "inputTokens"),
            "output_tokens": ("output_tokens", "outputTokens"),
            "cached_tokens": (
                "cached_tokens",
                "cachedTokens",
                "cache_read_input_tokens",
                "cacheReadInputTokens",
            ),
        }
        for target, names in aliases.items():
            for name in names:
                if target not in usage or usage[target] is not None:
                    continue
                parsed = number(value.get(name))
                if parsed is not None:
                    usage[target] = parsed
        model = value.get("model")
        if usage["model"] is None and isinstance(model, str) and model:
            usage["model"] = model

    for line in log.splitlines():
        try:
            value = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            value = None
        if isinstance(value, Mapping):
            update(value)
            nested = value.get("usage")
            if isinstance(nested, Mapping):
                update(nested)

        text = line.replace(",", "")
        patterns = {
            "input_tokens": rf"\binput(?:[_ ]tokens?)?\s*[:=]\s*{_USAGE_NUMBER}",
            "output_tokens": rf"\boutput(?:[_ ]tokens?)?\s*[:=]\s*{_USAGE_NUMBER}",
            "cached_tokens": rf"\b(?:cached|cache[_ ]read[_ ]input)(?:[_ ]tokens?)?\s*[:=]\s*{_USAGE_NUMBER}",
        }
        for target, pattern in patterns.items():
            if usage[target] is None:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    usage[target] = number(match.group(1))
        if usage["model"] is None:
            match = re.search(r"\bmodel\s*[:=]\s*([^\s,]+)", line, flags=re.IGNORECASE)
            if match:
                usage["model"] = match.group(1)
    return usage


def backend_capacity_event(backend: str, log: str) -> str | None:
    """Return a bounded capacity reason for known Codex and Claude failures."""
    if backend not in {"codex", "claude"}:
        return None
    lowered = log.lower()
    patterns = (
        r"\b429\b",
        r"\b529\b",
        r"rate[_ -]?limit(?:ed|ing)?",
        r"too many requests",
        r"overloaded(?:_error| error)?",
        r"server is busy",
        r"server overloaded",
        r"temporarily unavailable",
        r"try again later",
        r"usage limit",
        r"quota exceeded",
        r"out of credits",
        r"capacity(?: exceeded| unavailable)?",
        r"resource[_ -]?exhausted",
    )
    match = next(
        (
            found
            for pattern in patterns
            if (found := re.search(pattern, lowered)) is not None
        ),
        None,
    )
    if match is None:
        return None
    line = next(
        (line.strip() for line in log.splitlines() if match.group(0) in line.lower()),
        match.group(0),
    )
    return line[:512]


def _terminal_usage(record: "GenericJobRecord") -> dict[str, int | str | None]:
    content = _read_private_artifact(record.log_path, MAX_LOG_ARTIFACT_BYTES)
    if content is None:
        return parse_backend_usage("")
    return parse_backend_usage(content.decode(errors="replace"))


def _run_telemetry(
    record: "GenericJobRecord", state: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the safe machine-execution history projection for one terminal run."""
    finished_at = state.get("observed_at")
    started_at = record.created_at
    duration_seconds: float | None = None
    if isinstance(started_at, str) and isinstance(finished_at, str):
        try:
            duration_seconds = max(
                0.0,
                (
                    datetime.fromisoformat(finished_at)
                    - datetime.fromisoformat(started_at)
                ).total_seconds(),
            )
        except ValueError:
            pass
    command = record.spec.to_dict().get("command", {})
    contract = record.spec.contract
    backend = contract.get("backend") if isinstance(contract, Mapping) else None
    return {
        "schema_version": 1,
        "command": command,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "phase": state.get("phase"),
        "resources": state.get("resources"),
        "backend": backend if isinstance(backend, str) else None,
        "backend_usage": state.get("usage"),
    }


# GenericJobSpec.result_kind names to queue_run.py's RESULT_KINDS.
_QUEUE_RESULT_KINDS = {
    "exit-status": "exit",
    "last-message": "last-message",
    "json": "json",
    "pytest": "pytest",
}


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
    result_verdict: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    pool: str = "interactive"
    exclusive_keys: tuple[str, ...] = ()
    dependency_job_ids: tuple[str, ...] = ()
    scratch: str = "none"
    dimensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in {
            "declared-operation",
            "foreground-command",
            "operator-shell",
            "attested-agent",
            "delivery-operation",
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
        coordinator_label = self.contract.get("coordinator_label")
        if coordinator_label is not None and (
            not isinstance(coordinator_label, str)
            or not coordinator_label
            or len(coordinator_label) > 128
        ):
            raise ValueError(
                "job coordinator_label must be a non-empty string up to 128 characters"
            )
        if self.result_kind not in {"exit-status", "last-message", "json", "pytest"}:
            raise ValueError("job result kind is invalid")
        if self.result_verdict and self.result_kind != "json":
            raise ValueError("job result verdict requires a JSON result")
        if not isinstance(self.result_verdict, Mapping):
            raise ValueError("job result verdict is invalid")
        if not _POOL_NAME.fullmatch(self.pool):
            raise ValueError("job pool is invalid")
        if any(not isinstance(key, str) or not key for key in self.exclusive_keys):
            raise ValueError("job exclusive keys are invalid")
        if len(set(self.exclusive_keys)) != len(self.exclusive_keys):
            raise ValueError("job exclusive keys must be unique")
        if any(
            not isinstance(value, str) or not value for value in self.dependency_job_ids
        ):
            raise ValueError("job dependency IDs are invalid")
        try:
            _dimensions(self.dimensions)
        except ValueError as error:
            raise ValueError(str(error)) from error
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
            "result_verdict": {
                key: list(value) for key, value in self.result_verdict.items()
            },
            "admission": {
                "pool": self.pool,
                "exclusive_keys": list(self.exclusive_keys),
                "dependencies": list(self.dependency_job_ids),
                "scratch": self.scratch,
            },
            "dimensions": dict(self.dimensions),
        }
        if self.kind != "declared-operation":
            result["command"] = {
                "digest": self.command_digest or _command_digest(self.command),
                "display": (
                    "synthetic foreground command"
                    if self.kind == "foreground-command"
                    else f"{self.kind} contract runner"
                ),
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
                result_verdict={
                    key: tuple(outcomes)
                    for key, outcomes in value.get("result_verdict", {}).items()
                },
                pool=admission.get("pool", "interactive"),
                exclusive_keys=tuple(admission.get("exclusive_keys", ())),
                dependency_job_ids=tuple(admission.get("dependencies", ())),
                scratch=admission.get("scratch", "none"),
                dimensions=_dimensions(value.get("dimensions", {})),
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
    handoff_path: Path | None
    created_at: str
    cancel_requested_at: str | None = None
    admission_estimate_recorded: bool = False
    # The pueue task handle for this job's current launch attempt. Internal
    # only: a job that has never launched, or whose handle pueue has
    # forgotten, is resolved by scanning tasks() for the job's label.
    queue_task_id: int | None = None
    state: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": JOB_SCHEMA_VERSION,
            "job_id": self.job_id,
            "unit": self.unit,
            "spec": self.spec.to_dict(),
            "artifacts": {
                "log": str(self.log_path),
                "result": (
                    str(self.result_path) if self.result_path is not None else None
                ),
                "scratch": (
                    str(self.scratch_path) if self.scratch_path is not None else None
                ),
                "handoff": (
                    str(self.handoff_path) if self.handoff_path is not None else None
                ),
            },
            "created_at": self.created_at,
            "cancel_requested_at": self.cancel_requested_at,
            "admission_estimate_recorded": self.admission_estimate_recorded,
            "queue_task_id": self.queue_task_id,
            "state": dict(self.state),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], root: Path) -> GenericJobRecord:
        job_id = value.get("job_id")
        unit = value.get("unit")
        artifacts = value.get("artifacts")
        schema_version = value.get("schema_version")
        if schema_version not in {4, 5, 6, JOB_SCHEMA_VERSION} or not isinstance(
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
        raw_handoff = artifacts.get("handoff")
        handoff_path: Path | None = None
        if raw_handoff is not None:
            if not isinstance(raw_handoff, str):
                raise JobRecordError("job handoff artifact is invalid")
            handoff_path = Path(raw_handoff).resolve()
            handoffs_root = (root / "handoffs").resolve()
            if handoffs_root not in handoff_path.parents:
                raise JobRecordError("job handoff artifact escapes state root")
        spec = value.get("spec")
        state = value.get("state", {})
        if not isinstance(spec, Mapping) or not isinstance(state, Mapping):
            raise JobRecordError("job record spec or state is invalid")
        created_at = value.get("created_at")
        cancelled = value.get("cancel_requested_at")
        admission_estimate_recorded = value.get("admission_estimate_recorded", False)
        queue_task_id = value.get("queue_task_id")
        if (
            not isinstance(created_at, str)
            or (cancelled is not None and not isinstance(cancelled, str))
            or not isinstance(admission_estimate_recorded, bool)
            or (
                queue_task_id is not None
                and (
                    not isinstance(queue_task_id, int)
                    or isinstance(queue_task_id, bool)
                )
            )
        ):
            raise JobRecordError("job record timestamps are invalid")
        parsed_spec = GenericJobSpec.from_dict(spec, require_parameter_digest=True)
        return cls(
            job_id=job_id,
            unit=unit,
            spec=parsed_spec,
            log_path=log_path,
            result_path=result_path,
            scratch_path=scratch_path,
            handoff_path=handoff_path,
            created_at=created_at,
            cancel_requested_at=cancelled,
            admission_estimate_recorded=admission_estimate_recorded,
            queue_task_id=queue_task_id,
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
    def handoffs_root(self) -> Path:
        return self.root / "handoffs"

    @property
    def job_dirs_root(self) -> Path:
        return self.root / "job-dirs"

    @property
    def tmpfs_scratch_root(self) -> Path:
        configured = os.environ.get("SINNIXD_TMPFS_SCRATCH_ROOT")
        return Path(configured) if configured else Path("/dev/shm/sinnixd")

    @property
    def nvme_scratch_root(self) -> Path:
        configured = os.environ.get("SINNIXD_NVME_SCRATCH_ROOT")
        return Path(configured) if configured else Path("/realm/tmp/work/sinnixd")

    @property
    def capacity_path(self) -> Path:
        return self.root / "capacity.json"

    @property
    def inputs_root(self) -> Path:
        return self.root / "inputs"

    @property
    def locks_root(self) -> Path:
        return self.root / "locks"

    @property
    def active_records_path(self) -> Path:
        return self.root / "active-jobs.json"

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

    def create(
        self, spec: GenericJobSpec, job_id: str | None = None
    ) -> GenericJobRecord:
        _ensure_durable_directory(self.records_root)
        _ensure_durable_directory(self.logs_root)
        _ensure_durable_directory(self.handoffs_root)
        self.job_dirs_root.mkdir(mode=0o700, parents=True, exist_ok=True)
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
            job_dir = self.job_dirs_root / candidate
            try:
                job_dir.mkdir(mode=0o700)
            except FileExistsError as error:
                raise JobRecordError("job directory already exists") from error
            handoff_path = self.handoffs_root / f"{candidate}.json"
            record = GenericJobRecord(
                job_id=candidate,
                unit=job_unit_name(candidate),
                spec=spec,
                log_path=log_path.resolve(),
                result_path=result_path.resolve() if result_path is not None else None,
                scratch_path=scratch_path,
                handoff_path=handoff_path.resolve(),
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
        protected = active | self._unreadable_record_ids()
        for root in (self.tmpfs_scratch_root, self.nvme_scratch_root):
            if not root.exists():
                continue
            resolved_root = root.resolve()
            for path in sorted(resolved_root.iterdir()):
                try:
                    _ = job_unit_name(path.name)
                except (ValueError, JobRecordError):
                    continue
                if (
                    path.name not in protected
                    and path.is_dir()
                    and not path.is_symlink()
                ):
                    self._cleanup_scratch_path(resolved_root, path)

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
        return self._launch_from_path(self.inputs_root / f"{job_id}.launch")

    def _launch_from_path(self, path: Path) -> tuple[tuple[str, ...], dict[str, str]]:
        content = _read_private_artifact(path, 128 * 1024)
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

    def write_agent_launch(
        self, job_id: str, command: Sequence[str], environment: Mapping[str, str]
    ) -> None:
        self.write_declared_launch(job_id, command, environment)
        source = self.inputs_root / f"{job_id}.launch"
        target = self.inputs_root / f"{job_id}.agent-launch"
        os.replace(source, target)
        _fsync_directory(self.inputs_root)

    def agent_launch(self, job_id: str) -> tuple[tuple[str, ...], dict[str, str]]:
        _ = job_unit_name(job_id)
        return self._launch_from_path(self.inputs_root / f"{job_id}.agent-launch")

    def cleanup_agent_launch(self, job_id: str) -> None:
        path = self.inputs_root / f"{job_id}.agent-launch"
        path.unlink(missing_ok=True)
        if self.inputs_root.exists():
            _fsync_directory(self.inputs_root)

    def write_queue_launch(self, job_id: str, launch: Mapping[str, Any]) -> Path:
        """Persist the private launch input the queued ``sinnixd-queue-run`` reads.

        Rewritten on every launch attempt (initial submit, capacity retry,
        recovered restart), so an existing file is replaced rather than
        treated as a collision.
        """
        _ = job_unit_name(job_id)
        _ensure_durable_directory(self.inputs_root)
        path = self.inputs_root / f"{job_id}.queue-launch.json"
        payload = json.dumps(dict(launch), sort_keys=True).encode()
        path.unlink(missing_ok=True)
        with _open_private_artifact(path) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.inputs_root)
        return path

    def cleanup_queue_launch(self, job_id: str) -> None:
        path = self.inputs_root / f"{job_id}.queue-launch.json"
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
                # An unreadable record file is external tampering, not a job
                # state: it is skipped here and named by _unreadable_record_ids.
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
                return records
            records: list[GenericJobRecord] = []
            recovered_ids: set[str] = set(job_ids)
            for job_id in job_ids:
                try:
                    record = self.load(job_id)
                except JobRecordError:
                    continue
                if record.state.get("terminal"):
                    recovered_ids.discard(job_id)
                    continue
                records.append(record)
            if recovered_ids != job_ids:
                self._write_active_record_ids(recovered_ids)
            return records

    def _unreadable_record_ids(self) -> set[str]:
        if not self.records_root.exists():
            return set()
        unreadable: set[str] = set()
        for path in self.records_root.glob("*.json"):
            try:
                self.load(path.stem)
            except JobRecordError:
                unreadable.add(path.stem)
        return unreadable

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
            existing = self._active_record_ids()
            job_ids = existing or set()
            was_active = job_id in job_ids
            if existing is not None and was_active == active:
                return
            if active:
                job_ids.add(job_id)
            else:
                job_ids.discard(job_id)
            self._write_active_record_ids(job_ids)

    def _write_active_record_ids(self, job_ids: set[str]) -> None:
        self._write_job_id_index(self.active_records_path, job_ids)

    @staticmethod
    def _write_job_id_index(path: Path, job_ids: set[str]) -> None:
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

    def write_handoff(
        self, record: GenericJobRecord, payload: Mapping[str, Any]
    ) -> None:
        if record.handoff_path is None:
            raise JobRecordError("job handoff artifact is unavailable")
        if record.handoff_path.parent != self.handoffs_root.resolve():
            raise JobRecordError("job handoff artifact escapes state root")
        content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        if len(content) > MAX_HANDOFF_BYTES:
            raise JobRecordError("job handoff artifact exceeds its byte limit")
        try:
            with _open_private_artifact(record.handoff_path) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            return
        _fsync_directory(self.handoffs_root)

    def _record_path(self, job_id: str) -> Path:
        _ = job_unit_name(job_id)
        return self.records_root / f"{job_id}.json"

    def delete_records(self, job_ids: Iterable[str]) -> int:
        """Delete records and every artifact they own.

        A job record and its artifacts live exactly as long as the thing they
        served. Nothing here is time-based: the caller has already established
        that the owner is gone.
        """
        deleted = 0
        owned_tasks: list[int] = []
        for job_id in sorted(set(job_ids)):
            try:
                record = self.load(job_id)
            except JobRecordError:
                record = None
            if record is not None:
                if record.queue_task_id is not None:
                    owned_tasks.append(record.queue_task_id)
                for artifact in (
                    record.log_path,
                    record.result_path,
                    record.handoff_path,
                ):
                    if artifact is not None:
                        artifact.unlink(missing_ok=True)
                if record.scratch_path is not None:
                    shutil.rmtree(record.scratch_path, ignore_errors=True)
            shutil.rmtree(self.job_dirs_root / job_id, ignore_errors=True)
            for path in (
                self._record_path(job_id),
                self.locks_root / f"{job_id}.lock",
                self.root / "retry-prompts" / f"{job_id}.prompt",
                self.inputs_root / f"{job_id}.json",
                self.inputs_root / f"{job_id}.prompt",
                self.inputs_root / f"{job_id}.launch",
                self.inputs_root / f"{job_id}.agent-launch",
                self.inputs_root / f"{job_id}.queue-launch.json",
            ):
                path.unlink(missing_ok=True)
            self._set_active_record(job_id, active=False)
        if owned_tasks:
            try:
                pueue.remove(owned_tasks)
            except PueueError:
                # The store owns these records regardless; a queue that
                # cannot be reached still leaves a consistent durable state.
                pass
            deleted += 1
        if deleted and self.records_root.exists():
            _fsync_directory(self.records_root)
        return deleted

    def records_for_checkout(self, checkout_path: str) -> tuple[str, ...]:
        """Job ids whose declared checkout is this working tree."""
        return tuple(
            record.job_id
            for record in self.list()
            if isinstance(record.spec.checkout, Mapping)
            and record.spec.checkout.get("path") == checkout_path
        )

    @staticmethod
    def _owned_elsewhere(record: GenericJobRecord) -> bool:
        """True when something other than the operation itself owns this record.

        A plan holds its nodes' job ids, so a node's record is deleted with the
        plan (or with the workspace it ran in), never by a sibling node
        finishing the same operation on the same checkout.
        """
        return isinstance(record.spec.contract.get("plan"), Mapping)

    def superseded_records(self, record: GenericJobRecord) -> tuple[str, ...]:
        """Terminal records this run replaces.

        The same operation, on the same checkout, is the same question: a timer
        firing hourly and an operator re-running a gate both make the previous
        terminal answer unreadable. Records a plan owns are exempt — the plan
        outlives any one node.
        """
        checkout = (
            record.spec.checkout.get("path")
            if isinstance(record.spec.checkout, Mapping)
            else None
        )
        if (
            record.spec.operation is None
            or not isinstance(checkout, str)
            or self._owned_elsewhere(record)
        ):
            return ()
        return tuple(
            other.job_id
            for other in self.list()
            if other.job_id != record.job_id
            and other.state.get("terminal")
            and other.spec.operation == record.spec.operation
            and other.spec.project_id == record.spec.project_id
            and isinstance(other.spec.checkout, Mapping)
            and other.spec.checkout.get("path") == checkout
            and other.created_at < record.created_at
            and not self._owned_elsewhere(other)
        )


@dataclass
class GenericJobs:
    """Common durable job route for declared operations and foreground commands."""

    systemd: UserSystemdJobs
    store: GenericJobStore
    wait_poll_seconds: float = 1.0
    event_spool_path: Path | None = None
    recover_on_init: bool = True
    events: TerminalEvents = field(default_factory=TerminalEvents, repr=False)
    _spooled: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        # Recovery observes only the durable nonterminal set, so a daemon
        # restart cannot serialize systemd calls or per-job locks across the
        # historical corpus. Auxiliary processes (the delivery runner) open
        # the store read-mostly with recover_on_init=False so they never race
        # the daemon's recovery, scratch cleanup, or retention.
        if not self.recover_on_init:
            return
        records = (
            self.store.active_records() if self.store.records_root.exists() else []
        )
        self.store.cleanup_inactive_scratch(records)
        for record in records:
            with self.store.locked(record.job_id):
                record = self.store.load(record.job_id)
                if (
                    record.spec.kind == "declared-operation"
                    and record.state.get("phase") == "launching"
                ):
                    record = self._recover_unpublished_declared_locked(record)
                if record.state.get("terminal"):
                    self._finalize_terminal(record)
                else:
                    self._get_locked(record.job_id)

    def register_schedules(
        self,
        schedules: Sequence[tuple[ProjectAdapter, ProjectOperation]],
        *,
        agentctl_executable: str = "/run/current-system/sw/bin/agentctl",
    ) -> None:
        """Reconcile declared OnCalendar operations with user-manager timers.

        The timer is only a durable wake-up. Its command returns to the daemon,
        which creates the ordinary declared-operation job and records the
        firing provenance in the job spec. The schedule map is durable so a
        daemon restart can remove retired or changed transient units.
        """
        desired: dict[str, dict[str, str]] = {}
        for project, operation in schedules:
            assert operation.schedule is not None
            schedule_id = scheduled_operation_id(project.project_id, operation.name)
            unit = scheduled_timer_unit(schedule_id)
            desired[schedule_id] = {
                "project_id": project.project_id,
                "operation": operation.name,
                "schedule": operation.schedule,
                "unit": unit,
                "descriptor_digest": project.digest,
            }

        state_path = self.store.root / "schedules.json"
        if not desired and not state_path.exists():
            # Nothing declared and nothing to retire: never touch the store
            # root (service construction must not create state directories
            # for projects that declare no schedules).
            return
        previous: dict[str, dict[str, str]] = {}
        if state_path.exists():
            try:
                raw = json.loads(state_path.read_text())
                if not isinstance(raw, Mapping):
                    raise ValueError("schedule state must be an object")
                entries = raw.get("schedules")
                if raw.get(
                    "schema_version"
                ) != SCHEDULE_STATE_SCHEMA_VERSION or not isinstance(entries, list):
                    raise ValueError("schedule state has an unsupported schema")
                for entry in entries:
                    if not isinstance(entry, Mapping) or not isinstance(
                        entry.get("id"), str
                    ):
                        raise ValueError("schedule state contains an invalid entry")
                    value = {
                        key: entry.get(key)
                        for key in (
                            "project_id",
                            "operation",
                            "schedule",
                            "unit",
                            "descriptor_digest",
                        )
                    }
                    if any(
                        not isinstance(item, str) or not item for item in value.values()
                    ):
                        raise ValueError("schedule state contains invalid metadata")
                    previous[entry["id"]] = value
            except (OSError, json.JSONDecodeError, ValueError) as error:
                raise JobRecordError(
                    f"could not read schedule state: {error}"
                ) from error

        for schedule_id, entry in previous.items():
            if schedule_id not in desired:
                self.systemd.unschedule_timer(entry["unit"])

        for schedule_id, entry in desired.items():
            prior = previous.get(schedule_id)
            if prior == entry and self.systemd.timer_exists(entry["unit"]):
                continue
            self.systemd.unschedule_timer(entry["unit"])
            self.systemd.schedule_timer(
                unit=entry["unit"],
                on_calendar=entry["schedule"],
                command=(
                    agentctl_executable,
                    "job",
                    "fire",
                    entry["project_id"],
                    entry["operation"],
                    "--schedule-id",
                    schedule_id,
                ),
            )

        _ensure_durable_directory(self.store.root)
        temporary = state_path.with_suffix(".json.tmp")
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(
                    {
                        "schema_version": SCHEDULE_STATE_SCHEMA_VERSION,
                        "schedules": [
                            {"id": schedule_id, **entry}
                            for schedule_id, entry in sorted(desired.items())
                        ],
                    },
                    handle,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, state_path)
            _fsync_directory(self.store.root)
        finally:
            temporary.unlink(missing_ok=True)

    def _recover_unpublished_declared_locked(
        self, record: GenericJobRecord
    ) -> GenericJobRecord:
        """Recover the record/input publication window without guessing at pueue.

        A complete private input proves the durable intent can launch. An
        incomplete input is terminal only when this job never reached pueue
        (no queue_task_id was ever recorded); otherwise recovery retains the
        record.
        """
        try:
            self.store.declared_launch(record.job_id)
        except JobRecordError:
            if record.queue_task_id is not None:
                return record
            failed = self._with_state(
                record,
                {
                    "phase": "launch-failed",
                    "terminal": True,
                    "error": {"code": "declared-launch-input-incomplete"},
                    "observed_at": _timestamp(),
                },
            )
            self.store.save(failed)
            return failed
        self._launch_declared(record, record.spec)
        return self.store.load(record.job_id)

    def _capacity_state(self) -> dict[str, Any]:
        path = self.store.capacity_path
        if not path.exists():
            return {"schema_version": CAPACITY_SCHEMA_VERSION, "backends": {}}
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return {"schema_version": CAPACITY_SCHEMA_VERSION, "backends": {}}
        if (
            not isinstance(value, Mapping)
            or value.get("schema_version") != CAPACITY_SCHEMA_VERSION
            or not isinstance(value.get("backends"), Mapping)
        ):
            return {"schema_version": CAPACITY_SCHEMA_VERSION, "backends": {}}
        return {
            "schema_version": CAPACITY_SCHEMA_VERSION,
            "backends": dict(value["backends"]),
        }

    def _save_capacity_state(self, value: Mapping[str, Any]) -> None:
        path = self.store.capacity_path
        _ensure_durable_directory(path.parent)
        temporary = path.with_suffix(".json.tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)

    def capacity_status(self) -> dict[str, Any]:
        return self._capacity_state()

    def _record_capacity_event(
        self, record: GenericJobRecord, reason: str, retry_at: str | None
    ) -> None:
        backend = record.spec.contract.get("backend")
        if not isinstance(backend, str) or not backend:
            return
        state = self._capacity_state()
        state["backends"][backend] = {
            "last_event": _timestamp(),
            "reason": reason,
            "cooldown_until": retry_at,
            "job_id": record.job_id,
        }
        self._save_capacity_state(state)

    @staticmethod
    def _capacity_retry_at(record: GenericJobRecord) -> datetime | None:
        retry_at = record.state.get("capacity", {}).get("retry_at")
        if not isinstance(retry_at, str):
            return None
        try:
            return datetime.fromisoformat(retry_at)
        except ValueError:
            return None

    def _prepare_capacity_retry(self, record: GenericJobRecord) -> GenericJobRecord:
        """Relaunch a capacity-blocked attested-agent job once its cooldown elapses."""
        retry_at = self._capacity_retry_at(record)
        if retry_at is None or datetime.now(UTC) < retry_at:
            return record
        command, environment = self.store.agent_launch(record.job_id)
        if record.result_path:
            record.result_path.unlink(missing_ok=True)
            record.result_path.with_suffix(".overflow").unlink(missing_ok=True)
        self._launch(record, record.spec, command=command, environment=environment)
        return self.store.load(record.job_id)

    def _job_environment(
        self,
        record: GenericJobRecord,
        base: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        environment = dict(record.spec.environment if base is None else base)
        job_dir = (self.store.job_dirs_root / record.job_id).resolve()
        environment["SINNIXD_JOB_DIR"] = str(job_dir)
        ssh_config = self._job_ssh_config(job_dir)
        if ssh_config is not None and "GIT_SSH_COMMAND" not in environment:
            environment["GIT_SSH_COMMAND"] = f"ssh -F {ssh_config}"
        return environment

    @staticmethod
    def _job_ssh_config(job_dir: Path) -> Path | None:
        """A user-owned copy of ~/.ssh/config for the job's mount namespace.

        ReadOnlyPaths on a user unit implies a user namespace, which remaps
        every other-uid file — including a Home-Manager config symlinked into
        the nix store — to nobody. OpenSSH then fatally refuses the config
        ("Bad owner or permissions") and every lane fetch/push dies. A copy in
        the job dir keeps the invoking user's uid inside the namespace, so
        ssh accepts it.
        """
        source = Path.home() / ".ssh" / "config"
        try:
            content = source.read_text()
        except OSError:
            return None
        target = job_dir / "ssh_config"
        try:
            descriptor = os.open(
                target, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(descriptor, "w") as handle:
                handle.write(content)
        except OSError:
            return None
        return target

    def _pueue_label(self, spec: GenericJobSpec, job_id: str) -> str:
        return f"{spec.project_id}:{spec.operation}:{job_id}"

    def _dependency_task_ids(self, dependency_job_ids: Sequence[str]) -> list[int]:
        """Task ids for a job's already-terminal dependencies, where known.

        Dependencies are resolved by `_dependency_block` before `_launch` ever
        runs, so `after=` is a redundant structural guard, not the mechanism
        that makes launch wait for them.
        """
        task_ids: list[int] = []
        for dependency_id in dependency_job_ids:
            try:
                dependency = self.store.load(dependency_id)
            except JobRecordError:
                continue
            if dependency.queue_task_id is not None:
                task_ids.append(dependency.queue_task_id)
        return task_ids

    def _launch(
        self,
        record: GenericJobRecord,
        spec: GenericJobSpec,
        *,
        command: Sequence[str] | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        resolved_command = tuple(command) if command is not None else spec.command
        resolved_environment = self._job_environment(record, environment)
        launch_input: dict[str, Any] = {
            "job_id": record.job_id,
            "project_id": spec.project_id,
            "operation": spec.operation,
            "kind": spec.kind,
            "argv": list(resolved_command),
            "environment": dict(resolved_environment),
            "working_directory": spec.working_directory,
            "timeout_seconds": spec.timeout_seconds,
            "result_kind": _QUEUE_RESULT_KINDS[spec.result_kind],
            "log_path": str(record.log_path),
        }
        if record.result_path is not None:
            launch_input["result_path"] = str(record.result_path)
        if self.event_spool_path is not None:
            launch_input["event_spool_path"] = str(self.event_spool_path)
        if spec.checkout is not None:
            launch_input["checkout"] = dict(spec.checkout)
        input_path = self.store.write_queue_launch(record.job_id, launch_input)
        try:
            task_id = pueue.add(
                group=spec.pool,
                label=self._pueue_label(spec, record.job_id),
                command=("sinnixd-queue-run", str(input_path)),
                working_directory=Path(spec.working_directory),
                after=self._dependency_task_ids(spec.dependency_job_ids),
            )
        except PueueGroupError as error:
            return self._refuse_launch(record, str(error))
        except PueueError:
            return self._reconcile_launch_error(record)
        queued = replace(record, queue_task_id=task_id)
        queued = self._with_state(
            queued,
            {"phase": "queued", "terminal": False, "observed_at": _timestamp()},
        )
        self.store.save(queued)
        return self._public(queued, queued.state)

    def _launch_declared(
        self, record: GenericJobRecord, spec: GenericJobSpec
    ) -> dict[str, Any]:
        """Launch a declared operation.

        `sinnixd-queue-run` re-validates the bound checkout at its own exec
        boundary, closing the check-to-exec interval instead of trusting the
        checkout binding captured when the record was created.
        """
        try:
            command, environment = self.store.declared_launch(record.job_id)
            checkout = spec.checkout
            if checkout is not None:
                checkout_binding = dict(checkout)
                if checkout_binding.get("checkout_id") == "default":
                    # Default-checkout operations (scheduled runs, project-root
                    # jobs) follow the project head: master moving between
                    # record creation and launch is normal, not identity
                    # drift. Workspace-bound jobs keep exact-head binding —
                    # their verification receipts are only meaningful at the
                    # recorded commit.
                    resolved = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(checkout_binding.get("path", "")),
                            "rev-parse",
                            "HEAD",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                    )
                    refreshed = resolved.stdout.strip()
                    if resolved.returncode == 0 and re.fullmatch(
                        r"[0-9a-f]{40}", refreshed
                    ):
                        checkout_binding["head"] = refreshed
                        record = replace(
                            record, spec=replace(record.spec, checkout=checkout_binding)
                        )
                        self.store.save(record)
                        environment = {
                            **environment,
                            "SINNIXD_CHECKOUT_HEAD": refreshed,
                        }
                revalidate_registered_checkout(checkout_binding)
        except (JobRecordError, ProjectConfigError) as launch_error:
            terminal = self._with_state(
                record,
                {
                    "phase": (
                        "checkout-missing"
                        if self._checkout_path_missing(record)
                        else "launch-failed"
                    ),
                    "terminal": True,
                    "launch_evidence": "not-started",
                    "error": (
                        {
                            "code": "checkout-missing",
                            "message": "registered checkout is unavailable",
                        }
                        if self._checkout_path_missing(record)
                        else {
                            "code": "launch-refused",
                            "message": str(launch_error),
                        }
                    ),
                    "observed_at": _timestamp(),
                },
            )
            self.store.save(terminal)
            self._finalize_terminal(terminal)
            return self._public(terminal, terminal.state)
        return self._launch(record, spec, command=command, environment=environment)

    def _dependency_block(self, spec: GenericJobSpec) -> Mapping[str, Any] | None:
        """Return the blocking state a job with unmet dependencies must carry.

        `None` means every dependency has succeeded. Only declared-operation
        and attested-agent jobs may hold a non-terminal block (`waiting-
        dependencies`); every other kind is a caller error, not a queue.
        """
        for job_id in spec.dependency_job_ids:
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
                    "dependencies": list(spec.dependency_job_ids),
                }
            if not dependency["state"].get("terminal"):
                return {
                    "phase": "waiting-dependencies",
                    "terminal": False,
                    "observed_at": _timestamp(),
                    "dependencies": list(spec.dependency_job_ids),
                }
        return None

    def start(
        self,
        spec: GenericJobSpec,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        candidate = job_id or str(uuid4())
        # Dependency observations acquire their own job locks; do them before
        # the candidate lock so a dependency chain never nests job locks.
        blocked = self._dependency_block(spec) if spec.dependency_job_ids else None
        with self.store.locked(candidate):
            record = self.store.create(spec, candidate)
            if spec.kind == "attested-agent":
                launch_path = self.store.inputs_root / f"{candidate}.agent-launch"
                if not launch_path.exists():
                    self.store.write_agent_launch(
                        candidate, spec.command, spec.environment
                    )
            if blocked is not None:
                if not blocked.get("terminal") and spec.kind not in {
                    "declared-operation",
                    "attested-agent",
                }:
                    raise ValueError(
                        "immediate job dependencies are not terminal; "
                        "use a queued job kind for dependency waiting"
                    )
                blocked_record = self._with_state(record, blocked)
                self.store.save(blocked_record)
                if blocked.get("terminal"):
                    self._finalize_terminal(blocked_record)
                return self._public(blocked_record, blocked_record.state)
            return self._launch(record, spec)

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
        dependency_job_ids: Sequence[str] = (),
        dimensions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if principal not in {"agent-control", "operator"}:
            raise ValueError(
                "declared operations require agent-control or operator principal"
            )
        if checkout is not None and checkout.project_id != project.project_id:
            raise ValueError("declared job checkout belongs to another project")
        if (
            operation.checkout == "default"
            and checkout is not None
            and checkout.checkout_id != "default"
        ):
            raise ValueError(
                f"operation {operation.name} runs only on the default checkout, "
                f"not {checkout.checkout_id}"
            )
        dependency_ids = tuple(dependency_job_ids)
        for dependency_id in dependency_ids:
            self.store.load(dependency_id)
        operation_argv, parameter_digest = operation.derive_argv(parameters)
        workdir = checkout.path if checkout is not None else project.root
        environment = project.environment.values()
        job_id = str(uuid4())
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
        spec = GenericJobSpec(
            kind="declared-operation",
            command=project.environment.command_for(operation_argv),
            working_directory=str(workdir),
            environment=environment,
            project_id=project.project_id,
            operation=operation.name,
            parameter_digest=parameter_digest,
            principal=principal,
            timeout_seconds=operation.timeout_seconds,
            checkout=checkout.to_dict() if checkout is not None else None,
            contract=dict(contract or {}),
            result_kind={"exit": "exit-status", "json": "json", "pytest": "pytest"}[
                operation.result
            ],
            result_verdict=operation.verdict,
            pool=operation.pool,
            dependency_job_ids=dependency_ids,
            dimensions=_dimensions(dimensions or {}),
        )
        record = self.store.create(spec, job_id)
        try:
            self.store.write_declared_launch(
                job_id, record.spec.command, record.spec.environment
            )
        except BaseException:
            self.store.cleanup_scratch(record)
            raise
        blocked = self._dependency_block(spec) if spec.dependency_job_ids else None
        if blocked is not None:
            blocked_record = self._with_state(record, blocked)
            self.store.save(blocked_record)
            if blocked.get("terminal"):
                self._finalize_terminal(blocked_record)
            return self._public(blocked_record, blocked_record.state)
        return self._launch_declared(record, spec)

    SCHEDULE_RECONCILE_INTERVAL_SECONDS = 300.0
    schedule_reconcile: Callable[[], None] | None = None

    def run_schedule_reconciler(self, stop_event: Event) -> None:
        """Reconcile OnCalendar timers independently of clients."""
        while not stop_event.is_set():
            # Timer registration is a convergence loop, not a startup act: a
            # back-to-back restart raced registration to an empty durable map
            # and every scheduled operation (the nightly corpus included)
            # silently disarmed until the next restart (2026-09-01 21:49).
            if self.schedule_reconcile is not None:
                try:
                    self.schedule_reconcile()
                except Exception:
                    print("schedule reconciler: reconcile failed", file=sys.stderr)
                    traceback.print_exc()
            stop_event.wait(self.SCHEDULE_RECONCILE_INTERVAL_SECONDS)

    def _finalize_terminal(self, record: GenericJobRecord) -> None:
        """Handle a just-observed terminal transition exactly once per process.

        Already-terminal records re-observed later (restart recovery, repeat
        gets) go through _terminal_cleanup directly and are never re-spooled:
        a terminal record cannot transition again, so the once-set only needs
        process scope.
        """
        if record.job_id not in self._spooled:
            self._spooled.add(record.job_id)
            self._spool_terminal_event(record)
        self._terminal_cleanup(record)
        self.store.delete_records(self.store.superseded_records(record))

    def _spool_terminal_event(self, record: GenericJobRecord) -> None:
        checkout = record.spec.checkout
        self.spool_event(
            {
                "job_id": record.job_id,
                "kind": record.spec.kind,
                "project": record.spec.project_id,
                "phase": record.state.get("phase"),
                "verdict": record.state.get("verdict"),
                "completed_at": record.state.get("observed_at"),
                "checkout": checkout.get("checkout_id")
                if isinstance(checkout, Mapping)
                else None,
                "coordinator_label": record.spec.contract.get("coordinator_label"),
            }
        )
        parameters = record.spec.contract.get("parameters")
        campaign = (
            parameters.get("campaign") if isinstance(parameters, Mapping) else None
        )
        if isinstance(campaign, Mapping):
            coordinator_label = record.spec.contract.get("coordinator_label")
            self.spool_event(
                {
                    "kind": "campaign",
                    "transition": "node terminal",
                    "wave_id": campaign.get("wave_id"),
                    "group": campaign.get("group"),
                    "job_id": record.job_id,
                    "phase": record.state.get("phase"),
                    "coordinator_label": coordinator_label,
                }
            )
            wave_id = campaign.get("wave_id")
            if isinstance(wave_id, str):
                wave_jobs = [
                    item
                    for item in self.store.list()
                    if not item.state.get("terminal")
                    and isinstance(item.spec.contract.get("parameters"), Mapping)
                    and isinstance(
                        item.spec.contract["parameters"].get("campaign")
                        if isinstance(item.spec.contract.get("parameters"), Mapping)
                        else None,
                        Mapping,
                    )
                    and item.spec.contract["parameters"]["campaign"].get("wave_id")
                    == wave_id
                ]
                if not wave_jobs:
                    self.spool_event(
                        {
                            "kind": "campaign",
                            "transition": "wave drained",
                            "wave_id": wave_id,
                            "project": record.spec.project_id,
                            "coordinator_label": coordinator_label,
                        }
                    )

    def spool_event(self, event: Mapping[str, Any]) -> None:
        """Append one bounded advisory event to the existing event spool."""
        if self.event_spool_path is None:
            return
        # Every daemon-owned spool record carries the reactor event schema;
        # legacy producers may omit it and are still accepted by the reactor
        # during the one-way v0 migration.
        line = json.dumps(
            # Every event dates itself: campaign/harvest kinds shipped
            # without any timestamp for a week and their history had to be
            # reconstructed by interpolation.
            {"schema_version": 1, "emitted_at": _timestamp(), **dict(event)},
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            _ensure_durable_directory(self.event_spool_path.parent)
            try:
                if self.event_spool_path.stat().st_size > MAX_EVENT_SPOOL_BYTES:
                    os.replace(
                        self.event_spool_path,
                        self.event_spool_path.with_suffix(".jsonl.old"),
                    )
            except FileNotFoundError:
                pass
            with open(self.event_spool_path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            # The spool is an advisory watch point, never state authority.
            pass

    def _terminal_cleanup(self, record: GenericJobRecord) -> None:
        self.events.fire(record.job_id)
        self.store.cleanup_scratch(record)
        self.store.cleanup_queue_launch(record.job_id)
        if record.spec.kind == "declared-operation":
            self.store.cleanup_declared_launch(record.job_id)
        elif record.spec.kind == "attested-agent":
            self.store.cleanup_agent_launch(record.job_id)

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
            return self._get_locked(job_id)

    def list(
        self,
        *,
        principal: str = "operator",
        limit: int = 100,
        project_id: str | None = None,
        phases: tuple[str, ...] = (),
        kinds: tuple[str, ...] = (),
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
        if any(not isinstance(kind, str) or not kind for kind in kinds):
            raise ValueError("job list kinds must be non-empty strings")
        query = {
            "active_only": active_only,
            "kinds": sorted(set(kinds)),
            "phases": sorted(set(phases)),
            "project_id": project_id,
        }
        source_records = (
            self.store.active_records() if active_only else self.store.list()
        )
        records = sorted(
            (
                record
                for record in source_records
                if principal == "operator" or record.spec.principal == principal
                if project_id is None or record.spec.project_id == project_id
                if not query["phases"] or record.state.get("phase") in query["phases"]
                if not query["kinds"] or record.spec.kind in query["kinds"]
                if not active_only or not record.state.get("terminal", False)
            ),
            key=_job_order_key,
            reverse=True,
        )
        has_more = len(records) > limit
        page = records[:limit]
        return {
            "jobs": [self._list_row(record) for record in page],
            "limit": limit,
            "query": query,
            "total": len(records),
            "truncated": has_more,
            "snapshot": {"ordering": "created_at_desc_job_id_desc"},
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
            with self.store.locked(job_id):
                status = self._get_locked(job_id)
                queue_task_id = self.store.load(job_id).queue_task_id
            if status["state"]["terminal"]:
                return status
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {**status, "wait_timed_out": True}
            if queue_task_id is not None:
                # pueue holds the task until it reaches a final state, so the
                # wait blocks there rather than sampling the record. Polling
                # returns a running phase to a caller that asked for the
                # terminal one.
                try:
                    pueue.wait(queue_task_id, timeout_seconds=remaining)
                except PueueError:
                    # A wait that could not be placed is not evidence about the
                    # job; re-observe after a bounded pause.
                    self.events.wait_terminal(
                        (job_id,),
                        min(
                            self.wait_poll_seconds,
                            max(0.0, deadline - time.monotonic()),
                        ),
                    )
                continue
            # Nothing is queued yet: the job is waiting on a dependency or on a
            # launch that failed, and only re-observation can advance it.
            self.events.wait_terminal(
                (job_id,),
                min(self.wait_poll_seconds, max(0.0, deadline - time.monotonic())),
            )

    def cancel(self, job_id: str, *, reason: str) -> dict[str, Any]:
        terminal: GenericJobRecord | None = None
        with self.store.locked(job_id):
            status = self._get_locked(job_id)
            if status["state"]["terminal"]:
                return {**status, "cancel_requested": False, "already_terminal": True}
            record = self.store.load(job_id)
            if record.queue_task_id is None:
                # Never reached pueue: blocked on dependencies, or a launch
                # attempt whose task id has not yet been observed. There is
                # no queued process to kill.
                cancelled = self._with_state(
                    record,
                    {
                        "phase": "cancelled",
                        "terminal": True,
                        "launch_evidence": "not-started",
                        "cancellation": {
                            "reason": reason,
                            "requested_at": _timestamp(),
                        },
                        "observed_at": _timestamp(),
                    },
                )
                cancelled = replace(cancelled, cancel_requested_at=_timestamp())
                self.store.save(cancelled)
                terminal = cancelled
                response = {
                    **self._public(cancelled, cancelled.state),
                    "cancel_requested": True,
                    "already_terminal": False,
                }
            else:
                intent = self._with_state(
                    record,
                    {
                        **record.state,
                        "cancellation": {
                            "reason": reason,
                            "requested_at": record.cancel_requested_at or _timestamp(),
                        },
                    },
                )
                intent = replace(
                    intent,
                    cancel_requested_at=record.cancel_requested_at or _timestamp(),
                )
                self.store.save(intent)
                try:
                    pueue.kill(record.queue_task_id)
                except PueueError:
                    pass
                response = {
                    **self._get_locked(job_id),
                    "cancel_requested": True,
                    "already_terminal": False,
                }
        if terminal is not None:
            self._finalize_terminal(terminal)
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
        phase = state.get("phase")
        error = state.get("error")
        exit_code = error.get("exit_code") if isinstance(error, Mapping) else None
        if phase == "succeeded":
            return {"code": 0, "result": "success"}
        if phase == "timeout":
            return {"code": queue_run.TIMEOUT_EXIT_CODE, "result": "timeout"}
        if phase == "launch-failed":
            return {
                "code": exit_code
                if exit_code is not None
                else queue_run.REFUSED_EXIT_CODE,
                "result": "launch-failed",
            }
        if phase == "cancelled":
            return {
                "code": exit_code if exit_code is not None else -1,
                "result": "killed",
            }
        if phase == "failed" and isinstance(exit_code, int):
            return {"code": exit_code, "result": "failed"}
        raise JobResultError("job exit result is unavailable")

    def _resolve_task(self, record: GenericJobRecord) -> Task | None:
        """Return this job's pueue task, resolving a forgotten handle by label."""
        tasks = pueue.tasks()
        if record.queue_task_id is not None:
            task = tasks.get(record.queue_task_id)
            if task is not None:
                return task
        label = self._pueue_label(record.spec, record.job_id)
        for task in tasks.values():
            if task.label == label:
                return task
        return None

    def _get_locked(self, job_id: str) -> dict[str, Any]:
        record = self.store.load(job_id)
        if record.state.get("phase") == "capacity":
            retry_at = self._capacity_retry_at(record)
            if retry_at is not None and datetime.now(UTC) < retry_at:
                return self._public(record, record.state)
            record = self._prepare_capacity_retry(record)
            if record.state.get("phase") == "capacity":
                return self._public(record, record.state)
        if record.state.get("phase") == "waiting-dependencies":
            blocked = self._dependency_block(record.spec)
            if blocked is None:
                if record.spec.kind == "declared-operation":
                    return self._launch_declared(record, record.spec)
                return self._launch(record, record.spec)
            if blocked.get("terminal"):
                record = self._with_state(record, blocked)
                self.store.save(record)
                self._finalize_terminal(record)
            return self._public(record, record.state)
        if record.state.get("terminal"):
            self._terminal_cleanup(record)
            return self._public(record, record.state)
        task: Task | None = None
        try:
            task = self._resolve_task(record)
        except PueueError:
            state = self._observation_unknown_state()
        else:
            state = self._classify(task, record)
        if state.get("terminal"):
            state["telemetry"] = _run_telemetry(record, state)
        if isinstance(record.state.get("dimensions"), Mapping):
            state["dimensions"] = {
                **record.spec.dimensions,
                **record.state["dimensions"],
            }
        updated = self._with_state(record, state)
        if task is not None and updated.queue_task_id != task.task_id:
            # A forgotten handle was resolved by label; persist it so the
            # next observation does not need to scan every task again.
            updated = replace(updated, queue_task_id=task.task_id)
        if self._observation_unchanged(record, updated):
            return self._public(record, state)
        self.store.save(updated)
        if state.get("terminal"):
            self._finalize_terminal(updated)
        return self._public(updated, state)

    @staticmethod
    def _observation_unchanged(
        record: GenericJobRecord, updated: GenericJobRecord
    ) -> bool:
        """True when a re-observation would rewrite only its own timestamp.

        Skipping the durable save then spares an fsync pair per poll on the
        wear-limited state volume without dropping any state transition.
        """
        if record.queue_task_id != updated.queue_task_id:
            return False
        before = {
            key: value for key, value in record.state.items() if key != "observed_at"
        }
        after = {
            key: value for key, value in updated.state.items() if key != "observed_at"
        }
        return before == after

    def _reconcile_launch_error(self, record: GenericJobRecord) -> dict[str, Any]:
        """Keep a failed pueue.add retryable: a wedged queue is not proof the job is dead."""
        # The launch input was written before pueue.add was attempted; it
        # describes a task pueue never queued and must not linger.
        self.store.cleanup_queue_launch(record.job_id)
        state = {
            "phase": "launch-unknown",
            "error": {"code": QUEUE_ERROR_CODE},
            "terminal": False,
            "observed_at": _timestamp(),
        }
        updated = self._with_state(record, state)
        self.store.save(updated)
        return self._public(updated, state)

    def _refuse_launch(self, record: GenericJobRecord, message: str) -> dict[str, Any]:
        """Terminalize a launch no retry can fix, naming what to repair."""
        self.store.cleanup_queue_launch(record.job_id)
        state = {
            "phase": "launch-failed",
            "error": {"code": QUEUE_CONFIGURATION_ERROR_CODE, "message": message},
            "terminal": True,
            "observed_at": _timestamp(),
        }
        updated = self._with_state(record, state)
        self.store.save(updated)
        self._finalize_terminal(updated)
        return self._public(updated, state)

    @staticmethod
    def _observation_unknown_state() -> dict[str, Any]:
        """Keep transport failures retryable until pueue supplies an observation."""
        return {
            "phase": "observation-unknown",
            "error": {"code": QUEUE_ERROR_CODE},
            "terminal": False,
            "observed_at": _timestamp(),
        }

    def _classify(self, task: Task | None, record: GenericJobRecord) -> dict[str, Any]:
        # Observation rebuilds phase state from pueue truth, but the
        # cancellation block is decision evidence recorded by the actor that
        # stopped the job; rebuilding must not erase it.
        forensic = {
            key: dict(record.state[key])
            for key in ("cancellation",)
            if isinstance(record.state.get(key), Mapping)
        }
        if task is None:
            if record.queue_task_id is None:
                # The job never reached pueue, so pueue has nothing to say
                # about it. The recorded launch error is the only account of
                # why, and it holds until a retry replaces this state.
                launch_error = record.state.get("error")
                return {
                    **forensic,
                    "phase": record.state.get("phase") or "launch-unknown",
                    **(
                        {"error": dict(launch_error)}
                        if isinstance(launch_error, Mapping)
                        else {}
                    ),
                    "terminal": bool(record.state.get("terminal")),
                    "observed_at": _timestamp(),
                }
            return {
                **forensic,
                "phase": "missing",
                "terminal": True,
                "observed_at": _timestamp(),
            }
        if task.status in {"Queued", "Stashed", "Paused"}:
            return {
                **forensic,
                "phase": "queued",
                "terminal": False,
                "observed_at": _timestamp(),
            }
        if task.status == "Running":
            return {
                **forensic,
                "phase": "running",
                "terminal": False,
                "observed_at": _timestamp(),
            }
        semantic = self._declared_json_verdict(record, task)
        if semantic is not None:
            phase, verdict, error = semantic
            state = {
                **forensic,
                "phase": phase,
                "terminal": True,
                "verdict": verdict,
                "result_evidence": "declared-verdict",
                "observed_at": _timestamp(),
            }
            if error is not None:
                state["error"] = {"code": "RESULT_INVALID", "message": error}
            state["usage"] = _terminal_usage(record)
            state["terminal_cause"] = self._terminal_cause(record, task, phase)
            return state
        if task.succeeded:
            if record.spec.result_kind in {
                "last-message",
                "json",
                "pytest",
            } and not self._has_valid_result_artifact(record):
                phase = "failed"
                error: Mapping[str, Any] | None = {
                    "code": "RESULT_INVALID",
                    "message": "declared result artifact is unavailable or invalid",
                }
            else:
                phase = "succeeded"
                error = None
            state = {
                **forensic,
                "phase": phase,
                "terminal": True,
                "observed_at": _timestamp(),
            }
            if error is not None:
                state["error"] = error
            state["usage"] = _terminal_usage(record)
            state["terminal_cause"] = self._terminal_cause(record, task, phase)
            return state
        capacity_reason = None
        capacity_attempt = int(record.state.get("capacity_attempt", 0))
        retry_at: str | None = None
        if task.result == "Failed":
            if task.exit_code == queue_run.TIMEOUT_EXIT_CODE:
                phase = "timeout"
            elif task.exit_code == queue_run.REFUSED_EXIT_CODE:
                phase = "launch-failed"
            else:
                phase = "failed"
                if record.spec.kind == "attested-agent":
                    backend = record.spec.contract.get("backend")
                    content = _read_private_artifact(
                        record.log_path, MAX_LOG_ARTIFACT_BYTES
                    )
                    capacity_reason = backend_capacity_event(
                        backend if isinstance(backend, str) else "",
                        content.decode(errors="replace") if content is not None else "",
                    )
        elif task.result == "Killed":
            phase = "cancelled"
        else:  # DependencyFailed, FailedToSpawn, or an unrecognized result
            phase = "launch-failed"
        terminal = True
        if capacity_reason is not None:
            capacity_attempt += 1
            terminal = capacity_attempt > len(CAPACITY_RETRY_DELAYS_SECONDS)
            if not terminal:
                retry_at = (
                    datetime.now(UTC)
                    + timedelta(
                        seconds=CAPACITY_RETRY_DELAYS_SECONDS[capacity_attempt - 1]
                    )
                ).isoformat()
            self._record_capacity_event(record, capacity_reason, retry_at)
            phase = "capacity"
        state = {
            **forensic,
            "phase": phase,
            "terminal": terminal,
            **(
                {
                    "capacity_attempt": capacity_attempt,
                    "capacity": {
                        "backend": record.spec.contract.get("backend"),
                        "reason": capacity_reason,
                        "retry_at": retry_at,
                        "exhausted": terminal,
                    },
                }
                if capacity_reason is not None
                else {}
            ),
            "observed_at": _timestamp(),
        }
        if state.get("terminal"):
            if task.exit_code is not None:
                state["error"] = {"code": "EXIT_CODE", "exit_code": task.exit_code}
            state["usage"] = _terminal_usage(record)
            state["terminal_cause"] = self._terminal_cause(record, task, phase)
        return state

    def _declared_json_verdict(
        self, record: GenericJobRecord, task: Task
    ) -> tuple[str, str | None, str | None] | None:
        """Classify a declared JSON operation from its bounded outcome field."""
        if (
            record.spec.kind != "declared-operation"
            or record.spec.result_kind != "json"
            or not record.spec.result_verdict
            or not task.succeeded
        ):
            return None
        if not self._has_valid_result_artifact(record):
            return "failed", None, "declared JSON result is unavailable or incomplete"
        try:
            assert record.result_path is not None
            content = _read_private_artifact(record.result_path, MAX_RESULT_BYTES)
            assert content is not None
            value = self._parse_json_result(content)
        except (AssertionError, JobResultError) as error:
            return "failed", None, str(error)
        outcome = value.get("outcome")
        if not isinstance(outcome, str) or not outcome:
            return "failed", None, "declared JSON result outcome is missing"
        for category, outcomes in record.spec.result_verdict.items():
            if outcome in outcomes:
                return (
                    {
                        "success": "succeeded",
                        "refusal": "refused",
                        "failure": "failed",
                    }[category],
                    outcome,
                    None,
                )
        return "failed", outcome, "declared JSON result outcome is undeclared"

    @staticmethod
    def _terminal_cause(
        record: GenericJobRecord, task: Task, phase: str
    ) -> dict[str, Any]:
        """Keep the small failure explanation operators need beside the phase."""
        content = _read_private_artifact(record.log_path, MAX_LOG_ARTIFACT_BYTES)
        lines = (
            content.decode(errors="replace").splitlines() if content is not None else []
        )
        tail = [line for line in lines if line.strip()][-8:]
        if phase == "timeout":
            return {"kind": "timeout", "stderr_tail": tail}
        if record.spec.kind == "attested-agent" and any(
            marker in "\n".join(tail).lower()
            for marker in ("checkout", "preflight", "typed-job", "usage:", "runner")
        ):
            kind = "runner-refusal"
        else:
            kind = "exit-code"
        return {"kind": kind, "exit_code": task.exit_code, "stderr_tail": tail}

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
            handoff_path=record.handoff_path,
            created_at=record.created_at,
            cancel_requested_at=record.cancel_requested_at,
            admission_estimate_recorded=record.admission_estimate_recorded,
            queue_task_id=record.queue_task_id,
            state=dict(state),
        )

    def _list_row(self, record: GenericJobRecord) -> dict[str, Any]:
        """Render one listing row inside a per-row fault boundary.

        One stale checkout binding, unreadable result, or failed systemd
        observation degrades its own row; it must never abort the whole
        window (sinnix-8rch). Deep inspection with typed errors stays on
        job.get.
        """
        enrichment = "reconciliation"
        try:
            if record.state.get("terminal"):
                enrichment = "render"
                return self._public(record, record.state)
            return self.get(record.job_id)
        except Exception as error:
            phase = record.state.get("phase")
            return {
                "job_id": record.job_id,
                "kind": record.spec.kind,
                "project_id": record.spec.project_id,
                "operation": record.spec.operation,
                "created_at": record.created_at,
                "state": {
                    "phase": phase if isinstance(phase, str) else None,
                    "terminal": bool(record.state.get("terminal", False)),
                },
                "degraded": {
                    "enrichment": enrichment,
                    "error": f"{type(error).__name__}: {error}"[:300],
                },
            }

    def _public(
        self, record: GenericJobRecord, state: Mapping[str, Any]
    ) -> dict[str, Any]:
        checkout_status = self._checkout_status(record)
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
            "checkout": (
                dict(record.spec.checkout) if record.spec.checkout is not None else None
            ),
            **(
                {"checkout_status": checkout_status}
                if checkout_status is not None
                else {}
            ),
            "contract": dict(record.spec.contract),
            "dimensions": {
                **record.spec.dimensions,
                **(
                    record.state.get("dimensions", {})
                    if isinstance(record.state.get("dimensions"), Mapping)
                    else {}
                ),
            },
            "created_at": record.created_at,
            "timeout_seconds": record.spec.timeout_seconds,
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
                "handoff": (
                    {
                        "ref": f"sinnix://jobs/{record.job_id}/artifacts/handoff",
                        "max_bytes": MAX_HANDOFF_BYTES,
                    }
                    if record.handoff_path is not None
                    else None
                ),
            },
            "state": dict(state),
        }

    @staticmethod
    def _checkout_path_missing(record: GenericJobRecord) -> bool:
        checkout = record.spec.checkout
        path = checkout.get("path") if isinstance(checkout, Mapping) else None
        return isinstance(path, str) and bool(path) and not Path(path).is_dir()

    @staticmethod
    def _checkout_status(record: GenericJobRecord) -> dict[str, str] | None:
        checkout = record.spec.checkout
        if not isinstance(checkout, Mapping):
            return None
        path = checkout.get("path")
        if not isinstance(path, str) or not path:
            return {"state": "missing"}
        try:
            available = Path(path).is_dir()
        except OSError:
            available = False
        return None if available else {"state": "missing", "path": path}


def _command_digest(command: Sequence[str]) -> str:
    return hashlib.sha256("\0".join(command).encode()).hexdigest()


def _parameter_digest(parameters: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()
