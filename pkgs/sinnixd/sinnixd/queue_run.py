"""The command every queued task runs.

pueue owns the queue, the process, and the terminal result. It knows nothing
about project descriptors, result artifacts, or the event spool, so one
wrapper carries those between agentctl and the command:

    sinnixd-queue-run <private-input-path>

The path is the only argument because pueue joins a task's arguments into one
string for its shell; a single unspaced path cannot be re-split whatever the
shell does with it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

# The bounded artifacts a queued command may leave behind. A command that
# prints more is truncated with a marker, never allowed to fill the disk.
MAX_LOG_BYTES = 64_000
MAX_RESULT_BYTES = 64_000
OVERFLOW_MARKER = "\n[sinnixd: output truncated]\n"

# The exit status the wrapper reports when it enforced the declared timeout.
# 124 is what timeout(1) uses, so a reader needs no sinnixd-specific table.
TIMEOUT_EXIT_CODE = 124

# The status for a refusal before the command ran at all: a working directory
# that no longer exists, or an unreadable launch input.
REFUSED_EXIT_CODE = 125

RESULT_KINDS = frozenset({"exit", "json", "pytest", "last-message"})
POOL_NAME = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
POOL_SLICE_PREFIX = "sinnixd-pueue"

_REQUIRED_FIELDS = (
    "job_id",
    "project_id",
    "operation",
    "argv",
    "environment",
    "working_directory",
    "timeout_seconds",
    "result_kind",
    "log_path",
)


class QueueInputError(ValueError):
    """The private launch input is absent, malformed, or not this contract."""


def _read_input(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise QueueInputError(f"launch input is unreadable: {error}") from error
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise QueueInputError("launch input is not JSON") from error
    if not isinstance(value, dict):
        raise QueueInputError("launch input is not an object")
    missing = [field for field in _REQUIRED_FIELDS if field not in value]
    if missing:
        raise QueueInputError(f"launch input omits {', '.join(sorted(missing))}")
    argv = value["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) for item in argv)
    ):
        raise QueueInputError("launch input argv must be a non-empty list of strings")
    environment = value["environment"]
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in environment.items()
    ):
        raise QueueInputError("launch input environment must be a string map")
    if value["result_kind"] not in RESULT_KINDS:
        raise QueueInputError(f"unknown result kind: {value['result_kind']!r}")
    timeout = value["timeout_seconds"]
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise QueueInputError("launch input timeout_seconds must be a positive integer")
    pool = value.get("pool")
    if pool is not None and (
        not isinstance(pool, str) or POOL_NAME.fullmatch(pool) is None
    ):
        raise QueueInputError("launch input pool must be a lowercase pueue group name")
    return value


def scope_unit_for(job_id: object, pool: str) -> str:
    """Name the transient scope that carries one queued task's workload."""
    safe_job_id = re.sub(r"[^A-Za-z0-9_.-]", "-", str(job_id)).strip("-") or "job"
    return f"{POOL_SLICE_PREFIX}-{pool}-{safe_job_id[:160]}.scope"


def _scoped_command(launch: Mapping[str, Any]) -> tuple[list[str], str | None]:
    """Put new launches in the slice for their declared pueue pool.

    Launches from before pool scopes were introduced have no ``pool`` field;
    retaining their direct execution keeps historical retries readable. Every
    launch produced by ``agentctl`` carries the field.
    """
    pool = launch.get("pool")
    if pool is None:
        return list(launch["argv"]), None
    unit = scope_unit_for(launch["job_id"], pool)
    return (
        [
            "systemd-run",
            "--user",
            "--scope",
            "--quiet",
            "--collect",
            f"--unit={unit}",
            f"--slice={POOL_SLICE_PREFIX}-{pool}.slice",
            "--",
            *launch["argv"],
        ],
        unit,
    )


def append_event(spool_path: Path | None, event: Mapping[str, Any]) -> None:
    """Append one advisory lifecycle event. The spool is never state authority."""
    if spool_path is None:
        return
    line = json.dumps(
        {
            "schema_version": 1,
            "emitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **dict(event),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        spool_path.parent.mkdir(parents=True, exist_ok=True)
        with open(spool_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


def _bound(path: Path, limit: int) -> None:
    """Truncate a captured artifact to its limit, marking that it overflowed."""
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size <= limit:
        return
    marker = OVERFLOW_MARKER.encode()
    with open(path, "r+b") as handle:
        handle.truncate(max(limit - len(marker), 0))
        handle.seek(0, os.SEEK_END)
        handle.write(marker)


def _terminate(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            return
        process.wait(timeout=10)


def _stop_scope(unit: str | None) -> None:
    """Stop a transient scope when the queue runner times out."""
    if unit is None:
        return
    try:
        subprocess.run(
            ["systemctl", "--user", "stop", unit],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def run(launch: Mapping[str, Any]) -> int:
    """Run one queued command and leave its bounded artifacts behind."""
    log_path = Path(launch["log_path"])
    spool_path = (
        Path(launch["event_spool_path"]) if launch.get("event_spool_path") else None
    )
    result_kind = launch["result_kind"]
    result_path = Path(launch["result_path"]) if launch.get("result_path") else None

    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not Path(launch["working_directory"]).is_dir():
        log_path.write_text(
            f"working directory is gone: {launch['working_directory']}\n"
        )
        return REFUSED_EXIT_CODE

    append_event(
        spool_path,
        {
            # pueue's completion callback spools `queue-task` finish events;
            # the start carries the same kind so one lane's timeline pairs.
            "kind": "queue-task",
            "job_id": launch["job_id"],
            "label": launch.get("label", ""),
            "job_kind": launch.get("kind", "declared-operation"),
            "project": launch["project_id"],
            "operation": launch["operation"],
            "pool": launch.get("pool"),
            "scope_unit": launch.get("scope_unit"),
            "phase": "started",
            "working_directory": launch["working_directory"],
        },
    )

    # A typed result is the command's stdout alone; stderr and everything else
    # belongs in the log, or trailing diagnostics would corrupt the document.
    capture_stdout = result_path is not None and result_kind in {"json", "pytest"}
    # The queue is the admission boundary.  Pass its identity to the child so
    # project-native runners can distinguish a worker from a lane-side request.
    child_environment = dict(launch["environment"])
    child_environment.update(
        {
            "SINNIXD_JOB_ID": str(launch["job_id"]),
            "SINNIXD_PROJECT_ID": str(launch["project_id"]),
            "SINNIXD_OPERATION": str(launch["operation"]),
            "SINNIXD_QUEUE_WORKER": "1",
        }
    )
    command, scope_unit = _scoped_command(launch)
    with open(log_path, "wb") as log:
        stdout: Any = log
        result_file = None
        if capture_stdout:
            assert result_path is not None
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_file = open(result_path, "wb")
            stdout = result_file
        try:
            process = subprocess.Popen(
                command,
                cwd=launch["working_directory"],
                env=child_environment,
                stdout=stdout,
                stderr=log,
                start_new_session=True,
            )
        except OSError as error:
            if result_file is not None:
                result_file.close()
            log.write(f"could not start the command: {error}\n".encode())
            return REFUSED_EXIT_CODE

        # `pueue kill` sends SIGKILL, so no handler here can ever run and the
        # command's own session would outlive a cancel. Record the group the
        # command leads; `agentctl job cancel` reaps it after pueue kills.
        group_path = Path(f"{log_path}.pgid")
        try:
            group_path.write_text(str(os.getpgid(process.pid)))
        except OSError:
            pass
        try:
            returncode = process.wait(timeout=launch["timeout_seconds"])
        except subprocess.TimeoutExpired:
            _stop_scope(scope_unit)
            _terminate(process)
            log.write(f"timed out after {launch['timeout_seconds']} seconds\n".encode())
            returncode = TIMEOUT_EXIT_CODE
        finally:
            group_path.unlink(missing_ok=True)
            if result_file is not None:
                result_file.close()

    _bound(log_path, MAX_LOG_BYTES)
    if result_path is not None:
        _bound(result_path, MAX_RESULT_BYTES)
    return returncode


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-queue-run")
    parser.add_argument("launch_input", type=Path)
    parsed = parser.parse_args(arguments)
    try:
        launch = _read_input(parsed.launch_input)
    except QueueInputError as error:
        print(str(error), file=sys.stderr)
        return REFUSED_EXIT_CODE
    # The input stays for `pueue restart`: a retry re-executes this same
    # command line. It is mode 0600 and lives with the task that names it.
    return run(launch)


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
