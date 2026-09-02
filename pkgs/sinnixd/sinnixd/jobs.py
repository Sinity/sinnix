from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import selectors
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Condition, Event, Lock, RLock
from typing import Any, Iterable, Iterator, Protocol
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
MAX_TERMINAL_EVENT_ENTRIES = 4096
NOTIFY_TIMEOUT_SECONDS = 2.0
MAX_EVENT_SPOOL_BYTES = 64 * 1024 * 1024
SYSTEMD_COMMAND_TIMEOUT_SECONDS = 0.25
CGROUP_ROOT = Path("/sys/fs/cgroup")
CANCEL_OUTCOME_RECONCILIATION_GRACE_SECONDS = 300
MAX_LOG_BYTES = 64_000
MAX_LOG_ARTIFACT_BYTES = 1_048_576
MAX_RESULT_BYTES = 64_000
MAX_HANDOFF_BYTES = 64_000
JOB_SCHEMA_VERSION = 6
JOB_UNIT_PREFIX = "sinnixd-job-"
SYSTEMD_ERROR_CODE = "systemd-job-error"
SCHEDULE_STATE_SCHEMA_VERSION = 1
SCHEDULE_UNIT_PREFIX = "sinnixd-schedule-"
ADMISSION_SCHEMA_VERSION = 2
CAPACITY_SCHEMA_VERSION = 1
CAPACITY_RETRY_DELAYS_SECONDS = (5, 30, 120)
# Sustained IO stall blocks new admissions and never evicts. Measured
# 2026-09-02 12:29Z: io full avg10 76% under eight concurrent normal-pool
# jobs, against single digits on an idle host.
IO_FULL_BLOCK_THRESHOLD = 25.0
POOL_SLICES = {
    "interactive": "sinnixd-work-interactive.slice",
    "normal": "sinnixd-work-normal.slice",
    "bulk": "sinnixd-work-bulk.slice",
    "pytest": "sinnixd-work-pytest.slice",
    "agent": "sinnixd-work-agent.slice",
}
# memory_max is the hard cgroup ceiling every unit in the pool runs under
# (raised to a declared estimate when one is larger); swap_max bounds how
# far a unit may push the host into swap. Admission estimates bound nothing
# by themselves: an integrator lane admitted at the 1 GiB default peaked at
# 19.3 GB on 2026-09-01 and drove swap to 97% before systemd-oomd acted.
# Concurrency is the only per-pool bound. Memory belongs to the slice
# hierarchy: sinnixd.slice carries MemoryHigh and MemorySwapMax for the whole
# job plane and the desktop slices carry MemoryLow, so jobs collectively use
# what is left without any admission arithmetic on bytes.
POOL_POLICIES = {
    # Operator-facing work; four is a screenful of concurrent shells.
    "interactive": {"workers": 4},
    # Harvests and gates are disk-bound: eight saturated the disk (io full
    # avg10 25% over five minutes, 2026-09-02 11:30Z), three starved the queue.
    "normal": {"workers": 5},
    # One whole-corpus or reindex run on the host at a time.
    "bulk": {"workers": 1},
    # One test run at a time: a run writes a scratch archive per test and two
    # of them saturate the disk for every other process.
    "pytest": {"workers": 1},
    # Agent lanes are API-bound; the cap guards CPU-burst collision on 24
    # threads.
    "agent": {"workers": 16},
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


class AdmissionConflictError(ValueError):
    """A keyed packet lane overlaps a currently running keyed lane."""

    code = "conflict-key-overlap"

    def __init__(self, conflicts: Mapping[str, Sequence[str]]) -> None:
        self.conflicts = {
            key: tuple(sorted(job_ids)) for key, job_ids in sorted(conflicts.items())
        }
        details = ", ".join(
            f"{key} ({'/'.join(job_ids)})" for key, job_ids in self.conflicts.items()
        )
        super().__init__(f"packet launch refused: {self.code}; overlap: {details}")


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
        pool: str,
    ) -> None: ...

    def show(
        self,
        unit: str,
        *,
        timeout_seconds: float = SYSTEMD_COMMAND_TIMEOUT_SECONDS,
    ) -> Mapping[str, str]: ...

    def stop(self, unit: str) -> None: ...

    def schedule_timer(
        self, *, unit: str, on_calendar: str, command: Sequence[str]
    ) -> None: ...

    def timer_exists(self, unit: str) -> bool: ...

    def unschedule_timer(self, unit: str) -> None: ...


def timer_persistent(on_calendar: str) -> bool:
    """Catch up a missed daily or weekly run; never a sub-hourly one.

    A transient timer has no trigger stamp, so a persistent one fires the
    moment it is registered. Every daemon restart re-registers all timers,
    which ran the ten-minute sweep twice at each deploy; a missed sub-hourly
    tick is harmless, while a missed nightly corpus run is a lost night.
    """
    spec = on_calendar.strip()
    return not (spec.startswith("*:") or spec.startswith("*-*-* *:"))


@dataclass(frozen=True)
class UserSystemdJobs:
    """Launch and inspect transient user services through the user manager."""

    # Lane jobs may read operator tooling, configuration, and durable runtime
    # state, but those paths must remain owned by the host and its services.
    @staticmethod
    def lane_read_only_paths() -> tuple[str, ...]:
        home = Path.home()
        config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        return (
            str(home / ".local" / "bin"),
            str(home / ".claude"),
            str(config),
            "/realm/state",
        )

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
        pool: str,
    ) -> None:
        args = [
            "systemd-run",
            "--user",
            "--quiet",
            f"--unit={unit}",
            f"--slice={POOL_SLICES[pool]}",
            f"--property=WorkingDirectory={working_directory}",
            f"--property=RuntimeMaxSec={timeout_seconds}s",
            *(
                f"--property=ReadOnlyPaths={path}"
                for path in self.lane_read_only_paths()
            ),
            # The event spool is the one /realm/state path jobs may append:
            # harvest and sibling operations emit their typed transitions
            # there, and the blanket ReadOnlyPaths silently swallowed every
            # such event from 2026-08-27 (declared-harvest cutover) to
            # 2026-09-01 — the reactor never saw a review-required receipt.
            "--property=ReadWritePaths=/realm/state/agentctl",
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
                "--property=MemoryCurrent",
                "--property=MemoryPeak",
                "--property=MemorySwapCurrent",
                "--property=CPUUsageNSec",
                "--property=IOReadBytes",
                "--property=IOWriteBytes",
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
        # Stopping is a request, not a wait. A blocking stop runs until the
        # unit's own shutdown finishes, which for an agent unit is seconds --
        # far past the command budget every other systemd call is sized for.
        self._run(["systemctl", "--user", "--no-block", "stop", unit])

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
        except SystemdJobError:
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
        except SystemdJobError:
            # Registration is reconciled from the durable schedule map. A
            # missing transient unit is already the desired state.
            return

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


def notify_job_exit(
    socket_path: Path,
    job_id: str,
    exit_code: int,
    dimensions: Mapping[str, Any] | None = None,
) -> None:
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
                "arguments": {
                    "job_id": job_id,
                    "exit_code": exit_code,
                    **(
                        {"dimensions": dict(dimensions)}
                        if dimensions is not None
                        else {}
                    ),
                },
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


def host_pressure() -> Mapping[str, float]:
    """Read host capacity and stall evidence without acting on cgroups."""
    values: dict[str, float] = {
        "memory_full_avg10": 100.0,
        "memory_full_avg60": 100.0,
        "io_full_avg10": 100.0,
        "memory_total_bytes": 0.0,
        "memory_available_bytes": 0.0,
        "swap_total_bytes": 0.0,
        "swap_free_bytes": 0.0,
        "managed_memory_bytes": 0.0,
    }

    def pressure_average(resource: str, kind: str, average: str) -> float:
        for line in Path(f"/proc/pressure/{resource}").read_text().splitlines():
            if line.startswith(f"{kind} "):
                for item in line.split()[1:]:
                    key, _, value = item.partition("=")
                    if key == average:
                        return float(value)
        raise ValueError(f"{resource} PSI lacks {kind} {average}")

    for average, key in (
        ("avg10", "memory_full_avg10"),
        ("avg60", "memory_full_avg60"),
    ):
        try:
            values[key] = pressure_average("memory", "full", average)
        except (OSError, ValueError):
            pass
    try:
        values["io_full_avg10"] = pressure_average("io", "full", "avg10")
    except (OSError, ValueError):
        pass

    try:
        meminfo = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            name, separator, raw = line.partition(":")
            if separator and raw.strip().endswith(" kB"):
                meminfo[name] = int(raw.strip().removesuffix(" kB")) * 1024
        for source, target in (
            ("MemTotal", "memory_total_bytes"),
            ("MemAvailable", "memory_available_bytes"),
            ("SwapTotal", "swap_total_bytes"),
            ("SwapFree", "swap_free_bytes"),
        ):
            values[target] = float(meminfo[source])
    except (KeyError, OSError, ValueError):
        pass

    uid = os.getuid()
    managed_memory = (
        CGROUP_ROOT
        / "user.slice"
        / f"user-{uid}.slice"
        / f"user@{uid}.service"
        / "sinnixd.slice"
        / "sinnixd-work.slice"
        / "memory.current"
    )
    try:
        values["managed_memory_bytes"] = float(managed_memory.read_text().strip())
    except (OSError, ValueError):
        pass
    return values


def _unmetered_pressure() -> Mapping[str, float]:
    return {}


def _cgroup_inactive_file(properties: Mapping[str, str]) -> int:
    """Reclaimable page cache charged to the unit; 0 when unobservable."""
    control_group = properties.get("ControlGroup")
    if not (isinstance(control_group, str) and control_group.startswith("/")):
        return 0
    relative = Path(control_group.lstrip("/"))
    if ".." in relative.parts:
        return 0
    try:
        stat = (CGROUP_ROOT / relative / "memory.stat").read_text()
    except OSError:
        return 0
    for line in stat.splitlines():
        if line.startswith("inactive_file "):
            try:
                return max(0, int(line.split()[1]))
            except (IndexError, ValueError):
                return 0
    return 0


def _terminal_resources(properties: Mapping[str, str]) -> dict[str, Any]:
    """Capture bounded terminal resource evidence without making it authoritative."""
    pressure: str | None = None
    control_group = properties.get("ControlGroup")
    if isinstance(control_group, str) and control_group.startswith("/"):
        relative = Path(control_group.lstrip("/"))
        if ".." not in relative.parts:
            try:
                pressure = (CGROUP_ROOT / relative / "memory.pressure").read_text()
            except OSError:
                pass

    def integer(name: str) -> int | None:
        try:
            value = int(properties.get(name, ""))
        except (TypeError, ValueError):
            return None
        return value if value >= 0 else None

    return {
        "cpu_usage_nsec": integer("CPUUsageNSec"),
        "io_read_bytes": integer("IOReadBytes"),
        "io_write_bytes": integer("IOWriteBytes"),
        "memory_pressure": pressure,
    }


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
    lifetime: str
    ports: tuple[ServiceLeasePort, ...]
    host: str = "127.0.0.1"

    def __post_init__(self) -> None:
        try:
            UUID(self.lease_id)
        except (ValueError, AttributeError) as error:
            raise ValueError("service lease ID is invalid") from error
        if self.host != "127.0.0.1" or self.lifetime != "job":
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
            "lifetime": self.lifetime,
            "ports": [port.to_dict() for port in self.ports],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ServiceLease:
        if set(value) - {"readiness"} != {"id", "host", "lifetime", "ports"}:
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
    result_verdict: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    pool: str = "interactive"
    exclusive_keys: tuple[str, ...] = ()
    dependency_job_ids: tuple[str, ...] = ()
    scratch: str = "none"
    lease: ServiceLease | None = None
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
        try:
            _dimensions(self.dimensions)
        except ValueError as error:
            raise ValueError(str(error)) from error
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
            "result_verdict": {
                key: list(value) for key, value in self.result_verdict.items()
            },
            "lease": self.lease.to_dict() if self.lease is not None else None,
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
                result_verdict={
                    key: tuple(outcomes)
                    for key, outcomes in value.get("result_verdict", {}).items()
                },
                pool=admission.get("pool", "interactive"),
                exclusive_keys=tuple(admission.get("exclusive_keys", ())),
                dependency_job_ids=tuple(admission.get("dependencies", ())),
                scratch=admission.get("scratch", "none"),
                dimensions=_dimensions(value.get("dimensions", {})),
                lease=(
                    ServiceLease.from_dict(raw_lease) if raw_lease is not None else None
                ),
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
    cancel_requested_invocation_id: str | None = None
    cancel_stop_acknowledged_at: str | None = None
    cancel_stop_acknowledged_invocation_id: str | None = None
    admission_estimate_recorded: bool = False
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
            "cancel_requested_invocation_id": self.cancel_requested_invocation_id,
            "cancel_stop_acknowledged_at": self.cancel_stop_acknowledged_at,
            "cancel_stop_acknowledged_invocation_id": self.cancel_stop_acknowledged_invocation_id,
            "admission_estimate_recorded": self.admission_estimate_recorded,
            "state": dict(self.state),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], root: Path) -> GenericJobRecord:
        job_id = value.get("job_id")
        unit = value.get("unit")
        artifacts = value.get("artifacts")
        schema_version = value.get("schema_version")
        if schema_version not in {4, 5, JOB_SCHEMA_VERSION} or not isinstance(
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
        invocation = value.get("cancel_requested_invocation_id")
        stop_acknowledged = value.get("cancel_stop_acknowledged_at")
        stop_invocation = value.get("cancel_stop_acknowledged_invocation_id")
        admission_estimate_recorded = value.get("admission_estimate_recorded", False)
        if (
            not isinstance(created_at, str)
            or (cancelled is not None and not isinstance(cancelled, str))
            or (invocation is not None and not isinstance(invocation, str))
            or (
                stop_acknowledged is not None and not isinstance(stop_acknowledged, str)
            )
            or (stop_invocation is not None and not isinstance(stop_invocation, str))
            or not isinstance(admission_estimate_recorded, bool)
            or (stop_acknowledged is None) != (stop_invocation is None)
            or (
                stop_acknowledged is not None
                and (cancelled is None or stop_invocation != invocation)
            )
        ):
            raise JobRecordError("job record timestamps are invalid")
        parsed_spec = GenericJobSpec.from_dict(spec, require_parameter_digest=True)
        if parsed_spec.lease is not None and parsed_spec.lease.lease_id != job_id:
            raise JobRecordError("service lease ID does not match its job")
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
            cancel_requested_invocation_id=invocation,
            cancel_stop_acknowledged_at=stop_acknowledged,
            cancel_stop_acknowledged_invocation_id=stop_invocation,
            admission_estimate_recorded=admission_estimate_recorded,
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
    def capacity_path(self) -> Path:
        return self.root / "capacity.json"

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
        return ServiceLease(job_id, service.lifetime, tuple(allocations))

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
        protected = active | self._unreadable_record_ids()
        for path in sorted(self.readiness_root.iterdir()):
            try:
                _ = job_unit_name(path.name)
            except (ValueError, JobRecordError):
                continue
            if path.name not in protected:
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
            existing = self._service_lease_record_ids()
            job_ids = existing or set()
            was_active = job_id in job_ids
            if existing is not None and was_active == active:
                return
            if active:
                job_ids.add(job_id)
            else:
                job_ids.discard(job_id)
            self._write_service_lease_record_ids(job_ids)

    def _write_service_lease_record_ids(self, job_ids: set[str]) -> None:
        self._write_job_id_index(self.service_lease_records_path, job_ids)

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
        for job_id in sorted(set(job_ids)):
            try:
                record = self.load(job_id)
            except JobRecordError:
                record = None
            if record is not None:
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
            shutil.rmtree(self.readiness_root / job_id, ignore_errors=True)
            for path in (
                self._record_path(job_id),
                self.locks_root / f"{job_id}.lock",
                self.root / "retry-prompts" / f"{job_id}.prompt",
                self.inputs_root / f"{job_id}.json",
                self.inputs_root / f"{job_id}.prompt",
                self.inputs_root / f"{job_id}.launch",
                self.inputs_root / f"{job_id}.agent-launch",
                self._service_lease_path(job_id),
                self._service_lease_released_path(job_id),
            ):
                path.unlink(missing_ok=True)
            self._set_active_record(job_id, active=False)
            self._set_service_lease_record(job_id, active=False)
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

    systemd: SystemdJobs
    store: GenericJobStore
    wait_poll_seconds: float = 1.0
    admission_retry_seconds: float = 1.0
    pressure_probe: Callable[[], Mapping[str, float]] = _unmetered_pressure
    before_admission_start: Callable[[str], None] | None = None
    notify_socket: Path | None = None
    event_spool_path: Path | None = None
    recover_on_init: bool = True
    events: TerminalEvents = field(default_factory=TerminalEvents, repr=False)
    _admission_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _admission_written: str | None = field(default=None, init=False, repr=False)
    _admission_observed_at: float = field(default=0.0, init=False, repr=False)
    _spooled: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        # Recovery observes only the durable nonterminal set. Terminal lease
        # artifacts carry their own bounded reconciliation path, so a daemon
        # restart cannot serialize systemd calls or per-job locks across the
        # historical corpus. Auxiliary processes (the delivery runner) open
        # the store read-mostly with recover_on_init=False so they never race
        # the daemon's recovery, scratch cleanup, or retention.
        if not self.recover_on_init:
            return
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
                    self._finalize_terminal(record)
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
                "dependencies": list(record.spec.dependency_job_ids),
                "admission": {"pool": record.spec.pool},
            },
        )
        self.store.save(queued)
        return queued

    def _admission_state(self) -> dict[str, Any]:
        path = self.store.admission_path
        empty = {
            "schema_version": ADMISSION_SCHEMA_VERSION,
            "active": {},
            "claims": {},
        }
        if not path.exists():
            return dict(empty)
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            # Conservatively recover by forgetting optimizations. Existing
            # records/systemd evidence still determine all real jobs.
            return dict(empty)
        if not isinstance(value, Mapping) or value.get("schema_version") not in {
            1,
            ADMISSION_SCHEMA_VERSION,
        }:
            return dict(empty)
        if not isinstance(value.get("active"), Mapping):
            return dict(empty)
        return {
            "schema_version": ADMISSION_SCHEMA_VERSION,
            "active": dict(value["active"]),
            "claims": (
                dict(value["claims"])
                if isinstance(value.get("claims"), Mapping)
                else {}
            ),
        }

    def _admission_claim(self, record: GenericJobRecord) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "pool": record.spec.pool,
            "exclusive_keys": list(record.spec.exclusive_keys),
            "created_at": record.created_at,
            "project_id": record.spec.project_id,
            "operation": record.spec.operation,
        }

    def admission_ledger(self, project_id: str | None = None) -> dict[str, Any]:
        """Return the durable admission claims and their current arithmetic."""
        with self._admission_lock:
            self._admit_locked()
            state = self._admission_state()
            records = self.store.active_records()
            if project_id is not None:
                records = tuple(
                    record for record in records if record.spec.project_id == project_id
                )
            managed = [
                record
                for record in records
                if record.spec.kind in {"declared-operation", "attested-agent"}
                and not record.state.get("terminal")
            ]
            active = [
                record
                for record in managed
                if record.state.get("phase")
                in {
                    "submitted",
                    "running",
                    "cancelling",
                    "stopping",
                    "launch-unknown",
                    "observation-unknown",
                    "outcome-unknown",
                }
            ]
            queued = [
                record
                for record in managed
                if record.state.get("phase") in {"queued", "waiting-dependencies"}
            ]
            pressure = self.pressure_probe()
            holders = [
                {
                    **dict(state["claims"].get(record.job_id, {})),
                    "phase": record.state.get("phase"),
                }
                for record in sorted(active, key=_job_order_key)
            ]
            queue = []
            for position, record in enumerate(
                sorted(queued, key=lambda item: (item.created_at, item.job_id)), 1
            ):
                pool_active = [
                    item for item in active if item.spec.pool == record.spec.pool
                ]
                policy = POOL_POLICIES[record.spec.pool]
                exclusive = sorted(
                    {
                        key
                        for item in active
                        for key in item.spec.exclusive_keys
                        if key in record.spec.exclusive_keys
                    }
                )
                blocked_by = record.state.get("admission", {}).get("blocked_by", [])
                queue.append(
                    {
                        "position": position,
                        "job_id": record.job_id,
                        "phase": record.state.get("phase"),
                        "pool": record.spec.pool,
                        "blocked_by": list(blocked_by)
                        if isinstance(blocked_by, list)
                        else [],
                        "arithmetic": {
                            "pool_workers": {
                                "occupied": len(pool_active),
                                "limit": policy["workers"],
                            },
                            "exclusive_keys": exclusive,
                        },
                    }
                )
            return {
                "schema_version": ADMISSION_SCHEMA_VERSION,
                "pools": {
                    name: {
                        "workers": policy["workers"],
                        "holders": [
                            holder for holder in holders if holder.get("pool") == name
                        ],
                    }
                    for name, policy in POOL_POLICIES.items()
                },
                "host": {
                    "io_full_avg60": float(pressure.get("io_full_avg60", 0.0)),
                },
                "claims": dict(state["claims"]),
                "queue": queue,
            }

    def _save_admission_state(self, value: Mapping[str, Any]) -> None:
        """Persist the admission snapshot when it changed.

        Observe paths recompute admission on every call; an unchanged
        snapshot must not cost two fsyncs on the state disk each time.
        """
        path = self.store.admission_path
        text = json.dumps(value, sort_keys=True) + "\n"
        if self._admission_written is None and path.exists():
            with contextlib.suppress(OSError):
                self._admission_written = path.read_text()
        if text == self._admission_written:
            return
        _ensure_durable_directory(path.parent)
        temporary = path.with_suffix(".json.tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
        self._admission_written = text

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
        retry_at = self._capacity_retry_at(record)
        if retry_at is None or datetime.now(UTC) < retry_at:
            return record
        queued = self._with_state(
            record,
            {
                **record.state,
                "phase": "queued",
                "terminal": False,
                "observed_at": _timestamp(),
            },
        )
        self.store.save(queued)
        return queued

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

    def _active_key_conflicts(self, keys: Sequence[str]) -> dict[str, tuple[str, ...]]:
        requested = set(keys)
        if not requested:
            return {}
        running_phases = {
            "submitted",
            "running",
            "cancelling",
            "stopping",
            "launch-unknown",
            "observation-unknown",
            "outcome-unknown",
        }
        conflicts: dict[str, list[str]] = {}
        for record in self.store.active_records():
            if (
                record.spec.kind != "attested-agent"
                or record.state.get("phase") not in running_phases
                or record.state.get("terminal")
            ):
                continue
            for key in requested.intersection(record.spec.exclusive_keys):
                conflicts.setdefault(key, []).append(record.job_id)
        return {key: tuple(value) for key, value in conflicts.items()}

    def start(
        self,
        spec: GenericJobSpec,
        job_id: str | None = None,
        *,
        reject_conflicts: bool = False,
    ) -> dict[str, Any]:
        candidate = job_id or str(uuid4())
        if spec.kind == "attested-agent":
            with self._admission_lock:
                self._admit_locked()
                if reject_conflicts:
                    conflicts = self._active_key_conflicts(spec.exclusive_keys)
                    if conflicts:
                        raise AdmissionConflictError(conflicts)
                with self.store.locked(candidate):
                    record = self.store.create(spec, candidate)
                    launch_path = self.store.inputs_root / f"{candidate}.agent-launch"
                    if not launch_path.exists():
                        self.store.write_agent_launch(
                            candidate, spec.command, spec.environment
                        )
                    queued = self._with_state(
                        record,
                        {
                            "phase": "queued",
                            "terminal": False,
                            "observed_at": _timestamp(),
                            "admission": {"pool": spec.pool},
                        },
                    )
                    self.store.save(queued)
                self._admit_locked()
                record = self.store.load(candidate)
                return self._public(record, record.state)
        # The immediate path never revisits a job, so an unmet dependency must
        # settle here: a terminally failed one fails the job before launch and
        # a live one is a caller error rather than a silent unchecked launch.
        # Dependency locks are taken before the candidate lock, matching the
        # admission loop's ordering.
        immediate_block = (
            self._dependency_block(spec) if spec.dependency_job_ids else None
        )
        with self.store.locked(candidate):
            record = self.store.create(spec, candidate)
            if immediate_block is not None:
                if not immediate_block.get("terminal"):
                    raise SystemdJobError(
                        "immediate job dependencies are not terminal; "
                        "use a queued job kind for dependency waiting"
                    )
                blocked_record = self._with_state(record, immediate_block)
                self.store.save(blocked_record)
                self._finalize_terminal(blocked_record)
                return self._public(blocked_record, blocked_record.state)
            try:
                if not self.store.service_lease_ports_available(spec.lease):
                    raise SystemdJobError(
                        "leased loopback port became unavailable before launch"
                    )
                self.systemd.start(
                    unit=record.unit,
                    command=spec.command,
                    working_directory=spec.working_directory,
                    environment=self._job_environment(record),
                    timeout_seconds=spec.timeout_seconds,
                    log_path=record.log_path,
                    pool=spec.pool,
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
        dependency_job_ids: Sequence[str] = (),
        dimensions: Mapping[str, Any] | None = None,
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
                tuple(dependency_job_ids),
                dimensions,
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
        external_dependency_job_ids: tuple[str, ...] = (),
        dimensions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if operation.name in lineage:
            raise ValueError("declared operation dependency cycle")
        if (
            operation.checkout == "default"
            and checkout is not None
            and checkout.checkout_id != "default"
        ):
            raise ValueError(
                f"operation {operation.name} runs only on the default checkout, "
                f"not {checkout.checkout_id}"
            )
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
        if lineage:
            external_ids: tuple[str, ...] = ()
        else:
            external_ids = external_dependency_job_ids
        for dependency_id in external_ids:
            self.store.load(dependency_id)
        dependency_ids = (*external_ids, *dependency_ids)
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
        state = self._admission_state()
        if operation.supersede == "queued":
            self._supersede_queued(project.project_id, operation.name, principal, state)
        job_id = str(uuid4())
        readiness_path = (
            self.store.prepare_service_readiness(job_id)
            if operation.service is not None
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
                result_verdict=operation.verdict,
                pool=operation.pool,
                exclusive_keys=operation.exclusive_keys,
                dependency_job_ids=dependency_ids,
                scratch=operation.scratch,
                lease=lease,
                dimensions=_dimensions(dimensions or {}) if not lineage else {},
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
                "dependencies": list(dependency_ids),
                "admission": {"pool": spec.pool},
            },
        )
        self.store.save(queued)
        self._save_admission_state(state)
        self._admit_locked()
        record = self.store.load(job_id)
        return self._public(record, record.state)

    def _supersede_queued(
        self,
        project_id: str,
        operation_name: str,
        principal: str,
        state: MutableMapping[str, Any],
    ) -> None:
        """Cancel this operation's own not-yet-started jobs.

        A superseding operation's later run subsumes its earlier ones, so a
        queue of them is waste that also holds admission capacity.
        """
        for record in self.store.active_records():
            if record.state.get("phase") not in {"queued", "waiting-dependencies"}:
                continue
            if (
                record.spec.project_id != project_id
                or record.spec.operation != operation_name
                or record.spec.principal != principal
            ):
                continue
            with self.store.locked(record.job_id):
                current = self.store.load(record.job_id)
                if current.state.get("terminal"):
                    continue
                superseded = self._with_state(
                    current,
                    {
                        "phase": "cancelled",
                        "terminal": True,
                        "launch_evidence": "not-started",
                        "superseded": True,
                        "observed_at": _timestamp(),
                    },
                )
                self.store.save(superseded)
            self._finalize_terminal(superseded)
            self._finish_admission(superseded, state)

    @classmethod
    def _memory_observation(cls, record: GenericJobRecord) -> dict[str, Any]:
        state_observation = record.state.get("memory_observation")
        if isinstance(state_observation, Mapping) and str(
            state_observation.get("attribution_source", "")
        ).startswith("explicit-"):
            observation = dict(state_observation)
            observation.setdefault("attribution_source", "explicit-phase-observation")
            return observation
        phase_peaks = record.state.get("memory_peaks")
        if isinstance(phase_peaks, Mapping):
            return {
                "whole_unit_memory_peak_bytes": cls._memory_peak(
                    record.state.get("systemd", {})
                ),
                "agent_memory_peak_bytes": phase_peaks.get("agent"),
                "verification_memory_peak_bytes": phase_peaks.get("verification"),
                "attribution_source": "explicit-phase-peaks",
            }
        whole = max(
            (
                value
                for value in (
                    cls._memory_peak(record.state.get("systemd", {})),
                    cls._memory_peak(record.state.get("pre_stop_systemd", {})),
                )
                if value is not None
            ),
            default=None,
        )
        return {
            "whole_unit_memory_peak_bytes": whole,
            "agent_memory_peak_bytes": whole if record.spec.pool == "agent" else None,
            "verification_memory_peak_bytes": (
                whole if record.spec.pool != "agent" else None
            ),
            "attribution_source": "systemd-unit-pool-attribution",
        }

    @staticmethod
    def _queued_seconds(record: "GenericJobRecord") -> float:
        try:
            started = datetime.fromisoformat(record.created_at)
        except (TypeError, ValueError):
            return 0.0
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        return (datetime.now(UTC) - started).total_seconds()

    @staticmethod
    def _host_pressure_blocks(pressure: Mapping[str, float]) -> bool:
        """Sustained IO stall stops new admissions and never costs running work."""
        return float(pressure.get("io_full_avg60", 0.0)) >= IO_FULL_BLOCK_THRESHOLD

    @staticmethod
    def _systemd_memory(properties: Mapping[str, str]) -> int:
        values: list[int] = []
        for name in ("MemoryCurrent", "MemorySwapCurrent"):
            try:
                value = int(properties.get(name, ""))
            except (TypeError, ValueError):
                continue
            if value > 0:
                values.append(value)
        if values:
            # Page cache is reclaimed under pressure, not held; counting it
            # taught inflated estimates for IO-heavy jobs.
            return max(0, sum(values) - _cgroup_inactive_file(properties))
        peak = GenericJobs._memory_peak(properties)
        return peak or 0

    ADMISSION_OBSERVE_INTERVAL_SECONDS = 2.0

    def _admit_observed(self) -> None:
        """Admission for read paths: at most once per interval.

        Reads carry no new admission evidence of their own; a poll storm
        must not turn into a full admission pass per request.
        """
        now = time.monotonic()
        if now - self._admission_observed_at < self.ADMISSION_OBSERVE_INTERVAL_SECONDS:
            return
        self._admission_observed_at = now
        self._admit_locked()

    def _admit_locked(self) -> None:
        state = self._admission_state()
        records = self.store.active_records()
        for snapshot in records:
            if snapshot.state.get("phase") != "capacity":
                continue
            with self.store.locked(snapshot.job_id):
                current = self.store.load(snapshot.job_id)
                self._prepare_capacity_retry(current)
        records = sorted(self.store.active_records(), key=_job_order_key)
        active: dict[str, list[GenericJobRecord]] = {pool: [] for pool in POOL_POLICIES}
        for record in records:
            if (
                record.spec.kind in {"declared-operation", "attested-agent"}
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
        state["claims"] = {
            record.job_id: self._admission_claim(record)
            for pool_records in active.values()
            for record in pool_records
        }
        self._save_admission_state(state)
        pressure = self.pressure_probe()
        host_pressure_blocked = self._host_pressure_blocks(pressure)
        for snapshot in records:
            if snapshot.spec.kind not in {"declared-operation", "attested-agent"}:
                continue
            # Dependency observations acquire their own job locks.  Do them
            # before the candidate lock so admission never nests job locks in
            # an order determined by the dependency graph.
            blocked = self._dependency_block(snapshot.spec)
            terminal_blocked: GenericJobRecord | None = None
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
                        self._finalize_terminal(updated)
                        terminal_blocked = updated
                else:
                    policy = POOL_POLICIES[record.spec.pool]
                    exclusive = {
                        key
                        for pool_records in active.values()
                        for item in pool_records
                        for key in item.spec.exclusive_keys
                    }
                    blocked_by = [
                        reason
                        for reason, blocked_now in (
                            (
                                "pool-workers",
                                len(active[record.spec.pool]) >= policy["workers"],
                            ),
                            (
                                "exclusive-key",
                                bool(
                                    exclusive.intersection(record.spec.exclusive_keys)
                                ),
                            ),
                            (
                                "host-pressure",
                                record.spec.pool != "interactive"
                                and host_pressure_blocked,
                            ),
                        )
                        if blocked_now
                    ]
                    if blocked_by:
                        admission = {
                            **(
                                dict(record.state.get("admission", {}))
                                if isinstance(record.state.get("admission"), Mapping)
                                else {}
                            ),
                            "blocked_by": blocked_by,
                            "host": {
                                "io_full_avg60": float(
                                    pressure.get("io_full_avg60", 0.0)
                                ),
                            },
                        }
                        previous_admission = record.state.get("admission")
                        previous_blocked_by = (
                            previous_admission.get("blocked_by")
                            if isinstance(previous_admission, Mapping)
                            else None
                        )
                        if previous_blocked_by != blocked_by:
                            self.store.save(
                                self._with_state(
                                    record,
                                    {
                                        **record.state,
                                        "observed_at": _timestamp(),
                                        "admission": admission,
                                    },
                                )
                            )
                        continue
            if terminal_blocked is not None:
                self._finish_admission(terminal_blocked, state)
                continue
            if blocked is not None:
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
                    if current.spec.kind == "declared-operation":
                        command, environment = self.store.declared_launch(
                            current.job_id
                        )
                    else:
                        command, environment = self.store.agent_launch(current.job_id)
                    self.store.prepare_scratch(current)
                    if current.spec.kind == "attested-agent" and current.result_path:
                        current.result_path.unlink(missing_ok=True)
                        current.result_path.with_suffix(".overflow").unlink(
                            missing_ok=True
                        )
                        _completion_marker_path(current.log_path).unlink(
                            missing_ok=True
                        )
                    if (
                        current.spec.kind == "declared-operation"
                        and current.spec.checkout is not None
                    ):
                        checkout_binding = dict(current.spec.checkout)
                        if checkout_binding.get("checkout_id") == "default":
                            # Default-checkout operations (scheduled runs,
                            # project-root jobs) follow the project head: the
                            # binding head was captured when the job was
                            # created, and master moving in between is normal,
                            # not identity drift. Workspace-bound jobs keep
                            # exact-head binding — their verification receipts
                            # are only meaningful at the recorded commit.
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
                                current = replace(
                                    current,
                                    spec=replace(
                                        current.spec, checkout=checkout_binding
                                    ),
                                )
                                self.store.save(current)
                                # The unit environment carries the same
                                # binding the runner proves against the
                                # record; a refreshed record with an
                                # enqueue-time environment fails every
                                # queued default-checkout job once master
                                # moves (three corpus runs on 2026-09-02).
                                environment = {
                                    **environment,
                                    "SINNIXD_CHECKOUT_HEAD": refreshed,
                                }
                        revalidate_registered_checkout(checkout_binding)
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
                        environment=self._job_environment(current, environment),
                        timeout_seconds=current.spec.timeout_seconds,
                        log_path=current.log_path,
                        pool=current.spec.pool,
                        json_result_path=current.result_path
                        if current.spec.result_kind in {"json", "pytest"}
                        else None,
                        **self._notify_arguments(current.job_id),
                    )
                except SystemdJobError:
                    self._reconcile_launch_error(current)
                    terminal = self.store.load(current.job_id)
                except (JobRecordError, ProjectConfigError) as launch_error:
                    terminal = self._with_state(
                        current,
                        {
                            "phase": (
                                "checkout-missing"
                                if self._checkout_path_missing(current)
                                else "launch-failed"
                            ),
                            "terminal": True,
                            "launch_evidence": "not-started",
                            "error": (
                                {
                                    "code": "checkout-missing",
                                    "message": "registered checkout is unavailable",
                                }
                                if self._checkout_path_missing(current)
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
                else:
                    admission = (
                        dict(current.state.get("admission", {}))
                        if isinstance(current.state.get("admission"), Mapping)
                        else {}
                    )
                    admission.pop("blocked_by", None)
                    admission.pop("host", None)
                    submitted = self._with_state(
                        current,
                        {
                            **current.state,
                            "phase": "submitted",
                            "terminal": False,
                            "admission": admission,
                            "admitted_at": _timestamp(),
                            "observed_at": _timestamp(),
                        },
                    )
                    self.store.save(submitted)
            if terminal is not None and terminal.state.get("terminal"):
                self._finalize_terminal(terminal)
                self._finish_admission(terminal, state)
            elif submitted is not None:
                active[submitted.spec.pool].append(submitted)
        state["claims"] = {
            record.job_id: self._admission_claim(record)
            for pool_records in active.values()
            for record in pool_records
        }
        self._save_admission_state(state)

    # A unit's lease outlives its process by the time systemd takes to report
    # the unit inactive; reaping sooner frees a port still bound.
    LEASE_REAP_GRACE_SECONDS = 120.0

    def _reap_orphaned_leases(self) -> None:
        """Cancel service-lease jobs nothing depends on any more.

        lifetime=job binds a lease to the service job's own life, so leases
        outlived their lanes and held whole pools (three dev_services jobs
        blocked every harvest on pool-workers, 2026-09-01). A young lease is
        left alone: its dependent may still be queuing.
        """
        records = self.store.active_records()
        depended_on: set[str] = set()
        for record in records:
            if not record.state.get("terminal"):
                depended_on.update(record.spec.dependency_job_ids)
        now = time.time()
        for record in records:
            if (
                record.spec.lease is None
                or record.state.get("terminal")
                or record.job_id in depended_on
            ):
                continue
            try:
                created = datetime.fromisoformat(record.created_at).timestamp()
            except (TypeError, ValueError):
                continue
            if now - created < self.LEASE_REAP_GRACE_SECONDS:
                continue
            try:
                self.cancel(record.job_id, reason="lease-released")
            except Exception:
                print("lease reap failed for", record.job_id, file=sys.stderr)
                traceback.print_exc()

    SCHEDULE_RECONCILE_INTERVAL_SECONDS = 300.0
    schedule_reconcile: Callable[[], None] | None = None

    def run_admission_scheduler(self, stop_event: Event) -> None:
        """Protect the host and retry queued admission independently of clients."""
        last_schedule_reconcile = 0.0
        while not stop_event.is_set():
            # Timer registration is a convergence loop, not a startup act: a
            # back-to-back restart raced registration to an empty durable map
            # and every scheduled operation (the nightly corpus included)
            # silently disarmed until the next restart (2026-09-01 21:49).
            if (
                self.schedule_reconcile is not None
                and time.monotonic() - last_schedule_reconcile
                >= self.SCHEDULE_RECONCILE_INTERVAL_SECONDS
            ):
                last_schedule_reconcile = time.monotonic()
                try:
                    self.schedule_reconcile()
                except Exception:
                    print(
                        "admission scheduler: schedule reconcile failed",
                        file=sys.stderr,
                    )
                    traceback.print_exc()
            # One failed sweep must not end the daemon. An exception escaping
            # here kills the only thread that owns the active set, orphaning
            # every running unit and wedging all later admission.
            try:
                with self._admission_lock:
                    self._admit_locked()
            except Exception:
                print("admission scheduler: admission sweep failed", file=sys.stderr)
                traceback.print_exc()
            try:
                self._reap_orphaned_leases()
            except Exception:
                print("admission scheduler: lease reap failed", file=sys.stderr)
                traceback.print_exc()
            stop_event.wait(self.admission_retry_seconds)

    def _dependency_block(self, spec: GenericJobSpec) -> Mapping[str, Any] | None:
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
                dependency_record = self.store.load(job_id)
                lease = dependency_record.spec.lease
                if (
                    lease is not None
                    and dependency["state"].get("phase") in {"submitted", "running"}
                    and self.store.service_ready(job_id)
                    and all(
                        not _loopback_port_available(port.port) for port in lease.ports
                    )
                ):
                    continue
                return {
                    "phase": "waiting-dependencies",
                    "terminal": False,
                    "observed_at": _timestamp(),
                    "dependencies": list(spec.dependency_job_ids),
                }
        return None

    def _finish_admission(
        self, record: GenericJobRecord, state: dict[str, Any]
    ) -> None:
        with self.store.locked(record.job_id):
            record = self.store.load(record.job_id)
            if record.admission_estimate_recorded:
                return
            self._save_admission_state(state)
            self.store.save(replace(record, admission_estimate_recorded=True))

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
        self.store.cleanup_service_readiness(record.job_id)
        if record.spec.kind == "declared-operation":
            self.store.cleanup_declared_launch(record.job_id)
        elif record.spec.kind == "attested-agent":
            self.store.cleanup_agent_launch(record.job_id)
        self.store.release_terminal_service_lease(record)

    def _preserve_timeout(self, record: GenericJobRecord) -> dict[str, Any]:
        checkout = record.spec.checkout
        checkout_path: Path | None = None
        error: str | None = None
        diffstat = ""
        wip_commit: str | None = None
        dirty = False
        if record.spec.kind == "attested-agent" and isinstance(checkout, Mapping):
            try:
                checkout_path = revalidate_registered_checkout(checkout)
                status = subprocess.run(
                    ["git", "status", "--porcelain", "--untracked-files=all"],
                    cwd=checkout_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if status.returncode != 0:
                    raise OSError(status.stderr.strip() or "git status failed")
                dirty = bool(status.stdout)
                if dirty:
                    staged = subprocess.run(
                        ["git", "add", "-A"],
                        cwd=checkout_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                    )
                    if staged.returncode != 0:
                        raise OSError(staged.stderr.strip() or "git add failed")
                diff = subprocess.run(
                    ["git", "diff", "--stat", "--cached" if dirty else "HEAD"],
                    cwd=checkout_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if diff.returncode == 0:
                    diffstat = diff.stdout.strip()
                if dirty:
                    committed = subprocess.run(
                        [
                            "git",
                            "commit",
                            "--quiet",
                            "-m",
                            f"wip: preserved at timeout {record.job_id}",
                        ],
                        cwd=checkout_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                    )
                    if committed.returncode != 0:
                        raise OSError(committed.stderr.strip() or "git commit failed")
                    head = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=checkout_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                    )
                    if head.returncode == 0:
                        wip_commit = head.stdout.strip()
            except (
                OSError,
                subprocess.SubprocessError,
                ProjectConfigError,
                JobRecordError,
            ) as caught:
                error = str(caught)

        content = _read_private_artifact(record.log_path, MAX_LOG_ARTIFACT_BYTES)
        log_tail = (
            content.decode(errors="replace").splitlines()[-100:]
            if content is not None
            else []
        )
        payload: dict[str, Any] = {
            "schema_version": 1,
            "job_id": record.job_id,
            "dirty": dirty,
            "wip_commit": wip_commit,
            "diffstat": diffstat,
            "log_tail": log_tail,
        }
        if error is not None:
            payload["error"] = error
        try:
            self.store.write_handoff(record, payload)
            handoff_written = record.handoff_path is not None
        except (JobRecordError, OSError) as caught:
            handoff_written = False
            error = error or str(caught)
        details = {
            "dirty": dirty,
            "wip_commit": wip_commit,
            "diffstat": diffstat,
            "handoff_written": handoff_written,
        }
        if error is not None:
            details["error"] = error
        return details

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
            else:
                self._admit_observed()
        return status

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
        with self._admission_lock:
            self._admit_observed()
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
        with self._admission_lock:
            self._admit_locked()
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
            if status["state"]["terminal"]:
                return status
            if time.monotonic() >= deadline:
                return {**status, "wait_timed_out": True}
            self.events.wait_terminal(
                (job_id,),
                min(self.wait_poll_seconds, max(0.0, deadline - time.monotonic())),
            )

    def _notify_arguments(self, job_id: str) -> dict[str, Any]:
        """Capture notify args only when configured, so fakes with strict
        start signatures keep proving the unextended launch contract."""
        if self.notify_socket is None:
            return {}
        return {"notify_socket": self.notify_socket, "notify_job_id": job_id}

    def notify_exit(
        self, job_id: str, dimensions: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Record a capture-reported exit as a wake-up; observation stays authoritative."""
        _ = job_unit_name(job_id)
        with self.store.locked(job_id):
            record = self.store.load(job_id)
            if dimensions is not None:
                amended = _dimensions(dimensions)
                self.store.save(
                    self._with_state(
                        record,
                        {
                            **record.state,
                            "dimensions": {
                                **record.spec.dimensions,
                                **record.state.get("dimensions", {}),
                                **amended,
                            },
                        },
                    )
                )
        self.events.fire(job_id)
        return {
            "job_id": job_id,
            "notified": True,
            **({"dimensions": dict(dimensions)} if dimensions is not None else {}),
        }

    def cancel(self, job_id: str, *, reason: str) -> dict[str, Any]:
        terminal: GenericJobRecord | None = None
        pre_stop_systemd: Mapping[str, str] | None = None
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
                        "cancellation": {
                            "reason": reason,
                            "requested_at": _timestamp(),
                        },
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
                observed = status["state"].get("systemd")
                if isinstance(observed, Mapping):
                    pre_stop_systemd = {
                        str(key): str(value) for key, value in observed.items()
                    }
                intent = self._with_cancel_intent(
                    record,
                    status["state"].get("systemd", {}).get("InvocationID"),
                    reason=reason,
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
                if pre_stop_systemd is not None:
                    observed_record = self.store.load(job_id)
                    observed_record = self._with_state(
                        observed_record,
                        {
                            **observed_record.state,
                            "pre_stop_systemd": dict(pre_stop_systemd),
                        },
                    )
                    self.store.save(observed_record)
                    response = {
                        **self._public(observed_record, observed_record.state),
                        "cancel_requested": True,
                        "already_terminal": False,
                    }
        with self._admission_lock:
            if terminal is not None:
                self._finalize_terminal(terminal)
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
        if record.state.get("phase") == "capacity":
            retry_at = self._capacity_retry_at(record)
            if retry_at is not None and datetime.now(UTC) < retry_at:
                return self._public(record, record.state)
            record = self._prepare_capacity_retry(record)
            if record.state.get("phase") == "queued":
                return self._public(record, record.state)
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
        if state.get("terminal"):
            state["telemetry"] = _run_telemetry(record, state)
        if isinstance(record.state.get("dimensions"), Mapping):
            state["dimensions"] = {
                **record.spec.dimensions,
                **record.state["dimensions"],
            }
        updated = self._with_state(record, state)
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
        before = {
            key: value for key, value in record.state.items() if key != "observed_at"
        }
        after = {
            key: value for key, value in updated.state.items() if key != "observed_at"
        }
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
                "terminal_cause": {
                    "kind": "runner-refusal",
                    "stderr_tail": [],
                },
                "observed_at": _timestamp(),
            }
            state["telemetry"] = _run_telemetry(record, state)
            updated = self._with_state(record, state)
            self.store.save(updated)
            self._finalize_terminal(updated)
            return self._public(updated, state)
        state = self._classify(properties, record)
        updated = self._with_state(record, state)
        self.store.save(updated)
        if state.get("terminal"):
            self._finalize_terminal(updated)
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
        # Observation rebuilds phase state from systemd truth, but the
        # cancellation/preemption blocks are decision evidence recorded by the
        # actor that stopped the job; rebuilding must not erase them.
        forensic = {
            key: dict(record.state[key])
            for key in ("cancellation", "preemption")
            if isinstance(record.state.get(key), Mapping)
        }
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
                    **forensic,
                    "phase": record.state["phase"],
                    "terminal": False,
                    "systemd": dict(properties),
                    "observed_at": _timestamp(),
                }
            if record.state.get("phase") == "launch-unknown":
                return {
                    **forensic,
                    "phase": "launch-failed",
                    "error": {"code": SYSTEMD_ERROR_CODE},
                    "terminal": True,
                    "systemd": dict(properties),
                    "terminal_cause": self._terminal_cause(
                        record, properties, "failed"
                    ),
                    "observed_at": _timestamp(),
                }
            if self._has_authoritative_result(record):
                return {
                    **forensic,
                    "phase": "succeeded",
                    "terminal": True,
                    "systemd": dict(properties),
                    "result_evidence": "completed",
                    "observed_at": _timestamp(),
                }
            if self._stop_acknowledgement_matches(record):
                return {
                    **forensic,
                    "phase": "cancelled",
                    "terminal": True,
                    "systemd": dict(properties),
                    "cancellation": self._stop_acknowledgement(record),
                    "observed_at": _timestamp(),
                }
            if record.cancel_requested_at is not None:
                terminal = self._cancellation_reconciliation_grace_expired(record)
                return {
                    **forensic,
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
                **forensic,
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
                    **forensic,
                    "phase": "observation-unknown",
                    "error": {"code": SYSTEMD_ERROR_CODE},
                    "terminal": False,
                    "systemd": dict(properties),
                    "lease_invocation_id": bound,
                    "observed_at": _timestamp(),
                }
        semantic = self._declared_json_verdict(record, properties)
        if semantic is not None:
            phase, verdict, error = semantic
            state = {
                **forensic,
                "phase": phase,
                "terminal": True,
                "systemd": dict(properties),
                "verdict": verdict,
                "result_evidence": "declared-verdict",
                "observed_at": _timestamp(),
            }
            if error is not None:
                state["error"] = {"code": "RESULT_INVALID", "message": error}
            state["resources"] = _terminal_resources(properties)
            state["usage"] = _terminal_usage(record)
            state["terminal_cause"] = self._terminal_cause(record, properties, phase)
            return self._with_service_lease_invocation(record, properties, state)
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
        capacity_reason = None
        capacity_attempt = int(record.state.get("capacity_attempt", 0))
        if (
            phase == "failed"
            and record.spec.kind == "attested-agent"
            and properties.get("Result") == "exit-code"
        ):
            backend = record.spec.contract.get("backend")
            content = _read_private_artifact(record.log_path, MAX_LOG_ARTIFACT_BYTES)
            capacity_reason = backend_capacity_event(
                backend if isinstance(backend, str) else "",
                content.decode(errors="replace") if content is not None else "",
            )
            if capacity_reason is not None:
                capacity_attempt += 1
                terminal = capacity_attempt > len(CAPACITY_RETRY_DELAYS_SECONDS)
                retry_at = None
                if not terminal:
                    retry_at = (
                        datetime.now(UTC)
                        + timedelta(
                            seconds=CAPACITY_RETRY_DELAYS_SECONDS[capacity_attempt - 1]
                        )
                    ).isoformat()
                self._record_capacity_event(record, capacity_reason, retry_at)
                phase = "capacity"
        state = self._with_service_lease_invocation(
            record,
            properties,
            {
                **forensic,
                "phase": phase,
                "terminal": terminal,
                "systemd": dict(properties),
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
            },
        )
        state["memory_observation"] = self._memory_observation(
            replace(record, state=state)
        )
        if state.get("terminal"):
            state["resources"] = _terminal_resources(properties)
            state["usage"] = _terminal_usage(record)
            state["terminal_cause"] = self._terminal_cause(record, properties, phase)
            if state.get("phase") == "timed_out":
                state["timeout_wip"] = self._preserve_timeout(record)
        return state

    def _declared_json_verdict(
        self, record: GenericJobRecord, properties: Mapping[str, str]
    ) -> tuple[str, str | None, str | None] | None:
        """Classify a declared JSON operation from its bounded outcome field."""
        if (
            record.spec.kind != "declared-operation"
            or record.spec.result_kind != "json"
            or not record.spec.result_verdict
            or properties.get("ActiveState") not in {"inactive", "failed"}
            or properties.get("Result") != "success"
            or properties.get("ExecMainStatus") != "0"
        ):
            return None
        if not self._has_authoritative_result(record):
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
        record: GenericJobRecord, properties: Mapping[str, str], phase: str
    ) -> dict[str, Any]:
        """Keep the small failure explanation operators need beside the phase."""
        content = _read_private_artifact(record.log_path, MAX_LOG_ARTIFACT_BYTES)
        lines = (
            content.decode(errors="replace").splitlines() if content is not None else []
        )
        tail = [line for line in lines if line.strip()][-8:]
        if phase == "timed_out" or properties.get("Result") == "timeout":
            return {"kind": "timeout", "stderr_tail": tail}
        status = properties.get("ExecMainStatus")
        try:
            exit_code: int | None = int(status) if status is not None else None
        except (TypeError, ValueError):
            exit_code = None
        if record.spec.kind == "attested-agent" and any(
            marker in "\n".join(tail).lower()
            for marker in ("checkout", "preflight", "typed-job", "usage:", "runner")
        ):
            kind = "runner-refusal"
        else:
            kind = "exit-code"
        return {"kind": kind, "exit_code": exit_code, "stderr_tail": tail}

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
            cancel_requested_invocation_id=record.cancel_requested_invocation_id,
            cancel_stop_acknowledged_at=record.cancel_stop_acknowledged_at,
            cancel_stop_acknowledged_invocation_id=(
                record.cancel_stop_acknowledged_invocation_id
            ),
            admission_estimate_recorded=record.admission_estimate_recorded,
            state=dict(state),
        )

    @staticmethod
    def _with_cancel_intent(
        record: GenericJobRecord, invocation_id: Any, *, reason: str = "operator-cancel"
    ) -> GenericJobRecord:
        existing_intent = record.cancel_requested_at is not None
        record = GenericJobs._with_state(
            record,
            {
                **record.state,
                "cancellation": {
                    **(
                        dict(record.state.get("cancellation", {}))
                        if isinstance(record.state.get("cancellation"), Mapping)
                        else {}
                    ),
                    "reason": (
                        dict(record.state.get("cancellation", {})).get("reason")
                        if existing_intent
                        and isinstance(record.state.get("cancellation"), Mapping)
                        and dict(record.state.get("cancellation", {})).get("reason")
                        else reason
                    ),
                    "requested_at": record.cancel_requested_at or _timestamp(),
                },
            },
        )
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
            handoff_path=record.handoff_path,
            created_at=record.created_at,
            cancel_requested_at=record.cancel_requested_at or _timestamp(),
            cancel_requested_invocation_id=(
                record.cancel_requested_invocation_id
                if existing_intent
                else observed_invocation
            ),
            cancel_stop_acknowledged_at=record.cancel_stop_acknowledged_at,
            cancel_stop_acknowledged_invocation_id=(
                record.cancel_stop_acknowledged_invocation_id
            ),
            admission_estimate_recorded=record.admission_estimate_recorded,
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
            handoff_path=record.handoff_path,
            created_at=record.created_at,
            cancel_requested_at=record.cancel_requested_at,
            cancel_requested_invocation_id=record.cancel_requested_invocation_id,
            cancel_stop_acknowledged_at=_timestamp(),
            cancel_stop_acknowledged_invocation_id=invocation,
            admission_estimate_recorded=record.admission_estimate_recorded,
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
        acknowledgement = {
            "stop_acknowledged_at": record.cancel_stop_acknowledged_at,
            "invocation_id": record.cancel_stop_acknowledged_invocation_id,
        }
        cancellation = record.state.get("cancellation")
        if isinstance(cancellation, Mapping) and isinstance(
            cancellation.get("reason"), str
        ):
            acknowledgement["reason"] = cancellation["reason"]
        return acknowledgement

    @staticmethod
    def _cancel_intent(record: GenericJobRecord) -> dict[str, str]:
        assert record.cancel_requested_at is not None
        intent = {"requested_at": record.cancel_requested_at}
        if record.cancel_requested_invocation_id is not None:
            intent["invocation_id"] = record.cancel_requested_invocation_id
        cancellation = record.state.get("cancellation")
        if isinstance(cancellation, Mapping) and isinstance(
            cancellation.get("reason"), str
        ):
            intent["reason"] = cancellation["reason"]
        return intent

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


def capture_executable() -> Path:
    module_path = Path(__file__).resolve()
    if len(module_path.parents) > 4 and module_path.parents[3].name == "lib":
        return module_path.parents[4] / "bin" / "sinnixd-capture"
    return Path(sys.executable).with_name("sinnixd-capture")


def _capture_dimensions() -> dict[str, Any] | None:
    job_dir = os.environ.get("SINNIXD_JOB_DIR")
    if not job_dir:
        return None
    path = Path(job_dir) / "dimensions.json"
    try:
        value = json.loads(path.read_text())
        return _dimensions(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None


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
            stderr=(
                subprocess.PIPE if parsed.result_path is not None else subprocess.STDOUT
            ),
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
            notify_job_exit(
                parsed.notify_socket,
                parsed.notify_job_id,
                return_code,
                _capture_dimensions(),
            )
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
