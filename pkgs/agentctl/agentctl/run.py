"""The command every queued task runs.

pueue owns the queue, the process, and the terminal result. It knows nothing
about project descriptors, result artifacts, or the event spool, so one
wrapper carries those between agentctl and the command:

    agentctl-run <private-input-path>

The path is the only argument because pueue joins a task's arguments into one
string for its shell; a single unspaced path cannot be re-split whatever the
shell does with it.

That path also names the task's containment: a transient service
``agentctl-<pueue group>-<stem>-<digest of the path>.service`` in the pool's
slice, every part of which a reader recovers from ``pueue status`` alone. The
service exits with its cgroup (``ExitType=cgroup``), so ``systemd-run --wait``
returns only once nothing the workload started is left, and a canceller stops
the unit without this wrapper's help.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from . import pueue
from .pueue import PueueError

# The bounded artifacts a queued command may leave behind. A command that
# prints more is truncated with a marker, never allowed to fill the disk.
MAX_LOG_BYTES = 64_000
MAX_RESULT_BYTES = 64_000
OVERFLOW_MARKER = "\n[agentctl: output truncated]\n"

# Exit statuses of the wrapper itself. 124 is timeout(1)'s, 130 is a
# SIGINT-shaped cancellation, 126 a command that could not be observed, and
# 75 is EX_TEMPFAIL: the slot is taken and the same task may run later.
TIMEOUT_EXIT_CODE = 124
REFUSED_EXIT_CODE = 125
CANCELLED_EXIT_CODE = 130
VANISHED_EXIT_CODE = 126
SLOT_OCCUPIED_EXIT_CODE = 75


class Outcome(str, Enum):
    """How a run ended, as the result artifact and the finish event record it."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    VANISHED = "vanished"
    SLOT_OCCUPIED = "slot_occupied"


RESULT_KINDS = frozenset({"exit", "json", "pytest", "last-message"})
POOL_NAME = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
POOL_SLICE_PREFIX = "agentctl"
RUN_EXECUTABLE = "agentctl-run"

# The unit settings agentctl passes through to `systemd-run -p`. Each one only
# bounds what the workload may consume, so a launch input can limit its own
# task and nothing else: no capability, no namespace, no credential, no
# execution setting is reachable from here.
SCOPE_PROPERTIES = frozenset(
    {
        "MemoryMax",
        "MemoryHigh",
        "MemorySwapMax",
        "MemoryZSwapMax",
        "TasksMax",
        "CPUWeight",
        "IOWeight",
    }
)
SCOPE_PROPERTY_VALUE = re.compile(r"(infinity|[0-9]+[KMGTPE]?)\Z")

# The bytes of a unit name kept for the launch input's own stem. Unit names
# are bounded, and the prefix, the pool and the digest come first.
SCOPE_STEM_BYTES = 100
SYSTEMCTL_TIMEOUT_SECONDS = 30

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
    properties = value.get("scope_properties")
    if properties is not None and (
        not isinstance(properties, list)
        or not all(supported_scope_property(item) for item in properties)
    ):
        raise QueueInputError(
            "launch input scope_properties must be "
            f"{'/'.join(sorted(SCOPE_PROPERTIES))} settings"
        )
    return value


def supported_scope_property(value: object) -> bool:
    """Whether a launch input may set this on its own unit."""
    if not isinstance(value, str):
        return False
    name, separator, size = value.partition("=")
    return bool(
        separator
        and name in SCOPE_PROPERTIES
        and SCOPE_PROPERTY_VALUE.fullmatch(size) is not None
    )


def scope_pool(group: str | None) -> str | None:
    """A pueue group as a slice name component."""
    if not isinstance(group, str):
        return None
    return re.sub(r"[^a-z0-9-]+", "-", group.strip().lower()).strip("-") or None


def scope_unit_for(launch_input: object, pool: str) -> str:
    """Name the transient service carrying the task launched from ``launch_input``.

    The digest is of the whole path: a unit name is shorter than a path and
    drops the characters systemd reserves, and two tasks whose inputs differ
    only where the name is lossy must not share one unit.
    """
    text = str(PurePosixPath(str(launch_input)))
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    stem = re.sub(r"[^A-Za-z0-9_.-]", "-", PurePosixPath(text).stem).strip("-.")
    stem = stem[:SCOPE_STEM_BYTES] or "job"
    return f"{POOL_SLICE_PREFIX}-{pool}-{stem}-{digest}.service"


def _sibling(log_path: object, suffix: str) -> Path:
    path = Path(str(log_path))
    stem = path.name[:-4] if path.name.endswith(".log") else path.name
    return path.with_name(stem + suffix)


def cancel_marker_for(log_path: object) -> Path:
    """``<jobs_dir>/<ref>.cancel``: written by the canceller before it stops the unit."""
    return _sibling(log_path, ".cancel")


def outcome_path_for(log_path: object) -> Path:
    """``<jobs_dir>/<ref>.outcome``: the wrapper's own record of how the run ended."""
    return _sibling(log_path, ".outcome")


def launch_input_of(command: str) -> str | None:
    """The launch input a queued command names, or None for any other command."""
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    if len(words) != 2 or PurePosixPath(words[0]).name != RUN_EXECUTABLE:
        return None
    return words[1] if PurePosixPath(words[1]).is_absolute() else None


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


def systemd_environment() -> dict[str, str]:
    """The wrapper's environment with the user manager reachable.

    pueued exports the `pueue add` client's environment, which the adapter
    scrubs to a few keys; the user bus is found by the runtime directory.
    """
    environment = dict(os.environ)
    environment.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return environment


def _systemctl(*arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["systemctl", "--user", *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=SYSTEMCTL_TIMEOUT_SECONDS,
            env=systemd_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout if completed.returncode == 0 else None


def unit_properties(unit: str) -> dict[str, str]:
    """The unit's terminal state, empty once systemd no longer knows it."""
    shown = _systemctl(
        "show", "-p", "LoadState,ActiveState,Result,ExecMainStatus,ExecMainCode", unit
    )
    properties = dict(
        line.partition("=")[::2] for line in (shown or "").splitlines() if "=" in line
    )
    return properties if properties.get("LoadState") == "loaded" else {}


def active_units(pool: str) -> list[str]:
    """Every unit still holding the pool slice, whichever run created it."""
    listed = _systemctl(
        "list-units",
        "--plain",
        "--no-legend",
        "--state=active,activating,deactivating",
        f"{POOL_SLICE_PREFIX}-{pool}-*",
    )
    return [line.split()[0] for line in (listed or "").splitlines() if line.strip()]


def _occupancy(pool: str, unit: str, launch_input: str, log: Any) -> tuple[str, str]:
    """Whether a single-slot pool is free, and the pueue task id of this run.

    Returns ``("slot_occupied", ...)`` when a unit in the slice belongs to a
    task pueue still has running, or to no task this queue knows; a unit whose
    task is terminal is an orphan of a killed wrapper and is stopped here.
    """
    try:
        parallel = pueue.groups().get(pool)
        tasks = pueue.tasks() if parallel == 1 else {}
    except PueueError:
        return "", ""
    owners = {}
    for task in tasks.values():
        path = launch_input_of(task.command)
        if path is not None:
            owners[scope_unit_for(path, pool)] = task
    own = owners.get(unit)
    description = str(own.task_id) if own is not None else launch_input
    if parallel != 1:
        return "", description
    for other in active_units(pool):
        owner = owners.get(other)
        if other != unit and (owner is None or not owner.terminal):
            log.write(f"pool {pool} is occupied by {other}\n".encode())
            return "slot_occupied", description
        _systemctl("stop", other)
        _systemctl("reset-failed", other)
        log.write(f"settled_orphan {other}\n".encode())
    return "", description


def _service_command(
    launch: Mapping[str, Any],
    *,
    unit: str,
    pool: str,
    description: str,
    argv: Sequence[str],
    environment: Mapping[str, str],
    stdout: Path,
    log_path: Path,
) -> list[str]:
    properties = [
        f"RuntimeMaxSec={launch['timeout_seconds']}",
        "Type=exec",
        "ExitType=cgroup",
        "KillMode=control-group",
        "IOAccounting=yes",
        f"WorkingDirectory={launch['working_directory']}",
        f"StandardOutput={'append' if stdout == log_path else 'file'}:{stdout}",
        f"StandardError=append:{log_path}",
        *(launch.get("scope_properties") or ()),
    ]
    return [
        "systemd-run",
        "--user",
        "--wait",
        "--quiet",
        f"--unit={unit}",
        f"--slice={POOL_SLICE_PREFIX}-{pool}.slice",
        f"--description={description}",
        *(f"--setenv={key}={value}" for key, value in environment.items()),
        *(argument for value in properties for argument in ("-p", value)),
        "--",
        *argv,
    ]


def _classify(
    client_status: int, marker: Path, properties: Mapping[str, str]
) -> tuple[Outcome, int]:
    """What the run's unit says it did, or what `systemd-run --wait` says.

    systemd unloads a successful transient service the moment it is inactive
    and keeps a failed one, so an unobservable unit after a zero client status
    is a success and after any other status is one nothing can account for.
    """
    if marker.exists():
        return Outcome.CANCELLED, CANCELLED_EXIT_CODE
    if not properties:
        if client_status == 0:
            return Outcome.SUCCESS, 0
        return Outcome.VANISHED, VANISHED_EXIT_CODE
    if properties.get("Result") == "timeout":
        return Outcome.TIMEOUT, TIMEOUT_EXIT_CODE
    try:
        status = int(properties.get("ExecMainStatus", ""))
    except ValueError:
        return Outcome.VANISHED, VANISHED_EXIT_CODE
    # `show` prints the CLD_* code: 2 killed by a signal, 3 dumped core.
    if properties.get("ExecMainCode") in {"2", "3", "killed", "dumped"}:
        status += 128
    if properties.get("Result") == "success" and status == 0:
        return Outcome.SUCCESS, 0
    return Outcome.FAILED, status or 1


def _run_bare(
    argv: Sequence[str],
    launch: Mapping[str, Any],
    environment: Mapping[str, str],
    stdout: Any,
    log: Any,
) -> tuple[Outcome, int]:
    """Outside the queue there is no group and no unit; only the caller can cancel."""
    process = subprocess.Popen(
        argv,
        cwd=launch["working_directory"],
        env=dict(environment),
        stdout=stdout,
        stderr=log,
        start_new_session=True,
    )
    try:
        status = process.wait(timeout=launch["timeout_seconds"])
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        return Outcome.TIMEOUT, TIMEOUT_EXIT_CODE
    return (Outcome.SUCCESS, 0) if status == 0 else (Outcome.FAILED, status)


def run(launch: Mapping[str, Any], *, launch_input: str) -> int:
    """Run one queued command and leave its bounded artifacts behind."""
    log_path = Path(launch["log_path"])
    spool_path = (
        Path(launch["event_spool_path"]) if launch.get("event_spool_path") else None
    )
    result_path = Path(launch["result_path"]) if launch.get("result_path") else None
    # A typed result is the command's stdout alone; stderr and everything else
    # belongs in the log, or trailing diagnostics would corrupt the document.
    stdout_path = (
        result_path
        if result_path is not None and launch["result_kind"] in {"json", "pytest"}
        else log_path
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not Path(launch["working_directory"]).is_dir():
        log_path.write_text(
            f"working directory is gone: {launch['working_directory']}\n"
        )
        return REFUSED_EXIT_CODE

    # The pueue group comes from `PUEUE_GROUP`, which pueued exports into every
    # task it spawns, so a launch input written by another repository is
    # contained exactly like one agentctl wrote.
    pool = scope_pool(os.environ.get("PUEUE_GROUP")) or scope_pool(launch.get("pool"))
    unit = scope_unit_for(launch_input, pool) if pool else None
    marker = cancel_marker_for(log_path)
    marker.unlink(missing_ok=True)
    event = {
        # pueue's completion callback spools `queue-task` finish events;
        # the start carries the same kind so one lane's timeline pairs.
        "kind": "queue-task",
        "job_id": launch["job_id"],
        "label": launch.get("label", ""),
        "job_kind": launch.get("kind", "declared-operation"),
        "project": launch["project_id"],
        "operation": launch["operation"],
        "pool": pool,
        "scope_unit": unit,
        "working_directory": launch["working_directory"],
    }
    append_event(spool_path, {**event, "phase": "started"})

    # The queue is the admission boundary. Pass its identity to the child so
    # project-native runners can distinguish a worker from a lane-side request.
    environment = dict(launch["environment"])
    environment.update(
        {
            "AGENTCTL_JOB_ID": str(launch["job_id"]),
            "AGENTCTL_PROJECT_ID": str(launch["project_id"]),
            "AGENTCTL_OPERATION": str(launch["operation"]),
            "AGENTCTL_QUEUE_WORKER": "1",
        }
    )
    if pool:
        environment["AGENTCTL_POOL"] = pool
    argv = list(launch["argv"])
    executable = shutil.which(argv[0], path=environment.get("PATH", os.defpath))
    properties: dict[str, str] = {}
    # Both files are appended to, by this process and by systemd alike, so
    # neither writer overwrites what the other put there.
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_bytes(b"")
    stdout_path.write_bytes(b"")
    with open(log_path, "ab") as log, open(stdout_path, "ab") as stdout:
        if executable is None:
            log.write(f"could not start the command: {argv[0]} not found\n".encode())
            return REFUSED_EXIT_CODE
        argv[0] = executable
        try:
            if unit is None or pool is None:
                outcome, status = _run_bare(argv, launch, environment, stdout, log)
            else:
                refusal, description = _occupancy(pool, unit, launch_input, log)
                if refusal:
                    outcome, status = Outcome.SLOT_OCCUPIED, SLOT_OCCUPIED_EXIT_CODE
                else:
                    command = _service_command(
                        launch,
                        unit=unit,
                        pool=pool,
                        description=description,
                        argv=argv,
                        environment=environment,
                        stdout=stdout_path,
                        log_path=log_path,
                    )
                    client = subprocess.run(
                        command, stderr=log, check=False, env=systemd_environment()
                    )
                    properties = unit_properties(unit)
                    outcome, status = _classify(client.returncode, marker, properties)
                    _systemctl("reset-failed", unit)
                    if outcome is Outcome.VANISHED:
                        log.write(
                            f"unit {unit} vanished (rc {client.returncode})\n".encode()
                        )
        except OSError as error:
            log.write(f"could not start the command: {error}\n".encode())
            return REFUSED_EXIT_CODE
        if outcome is Outcome.TIMEOUT:
            log.write(f"timed out after {launch['timeout_seconds']} seconds\n".encode())
    marker.unlink(missing_ok=True)

    record = {
        "outcome": outcome.value,
        "exit_code": status,
        "unit": unit,
        "pool": pool,
        "systemd_result": properties.get("Result"),
    }
    outcome_path_for(log_path).write_text(json.dumps(record, sort_keys=True))
    append_event(spool_path, {**event, "phase": "finished", **record})
    _bound(log_path, MAX_LOG_BYTES)
    if result_path is not None:
        _bound(result_path, MAX_RESULT_BYTES)
    return status


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=RUN_EXECUTABLE)
    parser.add_argument("launch_input")
    parsed = parser.parse_args(arguments)
    try:
        launch = _read_input(Path(parsed.launch_input))
    except QueueInputError as error:
        print(str(error), file=sys.stderr)
        return REFUSED_EXIT_CODE
    # The input stays for `pueue restart`: a retry re-executes this same
    # command line. The path travels on as written: a canceller reads that
    # same string out of the task's command to name the unit this run creates.
    return run(launch, launch_input=parsed.launch_input)


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
