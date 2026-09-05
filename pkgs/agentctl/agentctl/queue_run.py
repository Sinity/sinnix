"""The command every queued task runs.

pueue owns the queue, the process, and the terminal result. It knows nothing
about project descriptors, result artifacts, or the event spool, so one
wrapper carries those between agentctl and the command:

    agentctl-run <private-input-path>

The path is the only argument because pueue joins a task's arguments into one
string for its shell; a single unspaced path cannot be re-split whatever the
shell does with it.

That path also names the task's containment. The workload runs in a transient
scope called ``agentctl-<pueue group>-<stem>-<digest of the path>.scope``,
every part of which a reader recovers from ``pueue status`` alone, so a
canceller reaps the whole cgroup without this wrapper's help and without the
launch input still existing.

The wrapper returns only once that scope holds nothing. ``systemd-run --scope``
execs the workload, so waiting on it ends when the leader exits while the scope
stays active for any descendant that outlived it; a wrapper returning there
reports the task terminal to pueue, which admits the next task into a group
whose worker is still occupied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

# The bounded artifacts a queued command may leave behind. A command that
# prints more is truncated with a marker, never allowed to fill the disk.
MAX_LOG_BYTES = 64_000
MAX_RESULT_BYTES = 64_000
OVERFLOW_MARKER = "\n[agentctl: output truncated]\n"

# The exit status the wrapper reports when it enforced the declared timeout.
# 124 is what timeout(1) uses, so a reader needs no agentctl-specific table.
TIMEOUT_EXIT_CODE = 124

# The status for a refusal before the command ran at all: a working directory
# that no longer exists, or an unreadable launch input.
REFUSED_EXIT_CODE = 125

RESULT_KINDS = frozenset({"exit", "json", "pytest", "last-message"})
POOL_NAME = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
POOL_SLICE_PREFIX = "agentctl"

# The transient scope settings agentctl passes through to `systemd-run -p`.
# Each one only lowers what the workload may consume, so a launch input can
# bound its own task and nothing else: no capability, no namespace, no
# credential, no execution setting is reachable from here.
SCOPE_PROPERTIES = frozenset(
    {"MemoryMax", "MemoryHigh", "MemorySwapMax", "MemoryZSwapMax", "TasksMax"}
)
SCOPE_PROPERTY_VALUE = re.compile(r"(infinity|[0-9]+[KMGTPE]?)\Z")

# How long a reap waits for a cgroup to drain before it reports what is left.
# Killing a cgroup is one write and returns in milliseconds; this bounds the
# pathological case, not the normal one.
REAP_GRACE_SECONDS = 5.0

# The bytes of a scope unit name kept for the launch input's own stem. Unit
# names are bounded, and the prefix, the pool and the digest come first.
SCOPE_STEM_BYTES = 100

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
    """Whether a launch input may set this on its own scope."""
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
    """Name the transient scope carrying the task launched from ``launch_input``.

    ``launch_input`` is the path the task's command names, as a string or a
    path, so a canceller reading only ``pueue status`` names the same unit the
    wrapper created. The digest is of that whole path: a unit name is shorter
    than a path and drops the characters systemd reserves, and two tasks whose
    inputs differ only where the name is lossy must not share one scope.
    """
    text = str(PurePosixPath(str(launch_input)))
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    stem = re.sub(r"[^A-Za-z0-9_.-]", "-", PurePosixPath(text).stem).strip("-.")
    stem = stem[:SCOPE_STEM_BYTES] or "job"
    return f"{POOL_SLICE_PREFIX}-{pool}-{stem}-{digest}.scope"


def _scoped_command(
    launch: Mapping[str, Any], launch_input: str
) -> tuple[list[str], str | None, str | None]:
    """Contain the workload in the scope named for its launch input and group.

    The pueue group comes from ``PUEUE_GROUP``, which pueued exports into every
    task it spawns, so a launch input written by another repository is contained
    exactly like one agentctl wrote. Invoked outside the queue there is no group
    and no scope: nothing but the caller can cancel such a run.
    """
    pool = scope_pool(os.environ.get("PUEUE_GROUP")) or scope_pool(launch.get("pool"))
    if pool is None:
        return list(launch["argv"]), None, None
    unit = scope_unit_for(launch_input, pool)
    properties = [
        argument
        for value in launch.get("scope_properties") or ()
        for argument in ("-p", value)
    ]
    return (
        [
            "systemd-run",
            "--user",
            "--scope",
            "--quiet",
            "--collect",
            f"--unit={unit}",
            f"--slice={POOL_SLICE_PREFIX}-{pool}.slice",
            *properties,
            "--",
            *launch["argv"],
        ],
        unit,
        pool,
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


def scope_control_group(unit: str) -> Path | None:
    """The cgroup directory a live transient scope owns."""
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "show", "--property=ControlGroup", "--value", unit],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    path = completed.stdout.strip()
    return Path(f"/sys/fs/cgroup{path}") if path.startswith("/") else None


def _live(pid: int) -> bool:
    """Whether a pid is a process rather than an unreaped exit status.

    A zombie stays in its cgroup until its parent reaps it, so counting one as
    a survivor would report a finished scope as still occupied.
    """
    try:
        # comm can contain spaces and parentheses; the field after the last
        # ')' is the process state.
        state = Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()
    except OSError:
        return False
    return bool(state) and state[0] != "Z"


def cgroup_processes(control_group: Path | None) -> list[int]:
    """Every live process in a cgroup and its descendants.

    A process may leave its session and its process group; it cannot leave the
    cgroup it was placed in, so this is the complete membership of a scope.
    """
    if control_group is None:
        return []
    found: set[int] = set()
    for procs in control_group.rglob("cgroup.procs"):
        try:
            found.update(int(line) for line in procs.read_text().split())
        except (OSError, ValueError):
            continue
    return sorted(pid for pid in found if _live(pid))


def kill_control_group(control_group: Path | None) -> bool:
    """Kill a cgroup and its descendants in one write.

    The kernel signals the whole subtree under its own lock, so nothing escapes
    by forking while the kill walks, and no pid read a moment earlier can have
    been reused by an unrelated process in between.
    """
    if control_group is None:
        return False
    try:
        (control_group / "cgroup.kill").write_text("1")
    except OSError:
        return False
    return True


def stop_scope(unit: str | None) -> dict[str, Any]:
    """Kill a transient scope and report what, if anything, outlived it.

    A scope is stopped when its task is over — pueue has SIGKILLed the wrapper,
    or the declared timeout expired — so there is nothing left to flush and the
    kill is immediate. Stopping the unit afterwards releases a scope that did
    not collect itself once empty.
    """
    if unit is None:
        return {"unit": None, "stopped": False, "survivors": []}
    control_group = scope_control_group(unit)
    kill_control_group(control_group)
    # systemd kills the control group too, and releases a unit whose cgroup the
    # kernel emptied under it; a unit already collected refuses, harmlessly.
    try:
        subprocess.run(
            ["systemctl", "--user", "stop", unit],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    survivors = _drain(control_group)
    return {"unit": unit, "stopped": not survivors, "survivors": survivors}


def _drain(control_group: Path | None) -> list[int]:
    """Kill a cgroup until it is empty; the pids still there when time ran out."""
    deadline = time.monotonic() + REAP_GRACE_SECONDS
    survivors = cgroup_processes(control_group)
    while survivors:
        kill_control_group(control_group)
        if time.monotonic() >= deadline:
            break
        time.sleep(0.05)
        survivors = cgroup_processes(control_group)
    return survivors


def settle_scope(unit: str | None) -> dict[str, list[int]]:
    """Wait for a scope to empty after its leader exited, then kill the rest.

    ``systemd-run --scope`` execs the workload, so the wrapper's wait ends with
    the leader while every descendant that left it keeps the scope active. The
    task is over by definition here, and its group's worker is not free until
    the cgroup is: what has not exited on its own is killed. Reports what
    outlived the command, and what outlived the kill as well.
    """
    settled: dict[str, list[int]] = {"outlived": [], "survivors": []}
    if unit is None:
        return settled
    control_group = scope_control_group(unit)
    if control_group is None:
        return settled
    deadline = time.monotonic() + REAP_GRACE_SECONDS
    while cgroup_processes(control_group) and time.monotonic() < deadline:
        time.sleep(0.05)
    outlived = cgroup_processes(control_group)
    if not outlived:
        return settled
    return {"outlived": outlived, "survivors": stop_scope(unit)["survivors"]}


def run(launch: Mapping[str, Any], *, launch_input: str) -> int:
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

    command, scope_unit, pool = _scoped_command(launch, launch_input)
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
            # The group pueue actually ran the task in, which is the group the
            # scope and its slice were named for; a launch input may declare
            # another or none at all.
            "pool": pool,
            "scope_unit": scope_unit,
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
            "AGENTCTL_JOB_ID": str(launch["job_id"]),
            "AGENTCTL_PROJECT_ID": str(launch["project_id"]),
            "AGENTCTL_OPERATION": str(launch["operation"]),
            "AGENTCTL_QUEUE_WORKER": "1",
        }
    )
    if pool:
        child_environment["AGENTCTL_POOL"] = str(pool)
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

        try:
            returncode = process.wait(timeout=launch["timeout_seconds"])
        except subprocess.TimeoutExpired:
            stop_scope(scope_unit)
            _terminate(process)
            log.write(f"timed out after {launch['timeout_seconds']} seconds\n".encode())
            returncode = TIMEOUT_EXIT_CODE
        else:
            settled = settle_scope(scope_unit)
            if settled["outlived"]:
                left = ", ".join(str(pid) for pid in settled["outlived"])
                log.write(
                    f"killed what the command left in its scope: {left}\n".encode()
                )
            if settled["survivors"]:
                alive = ", ".join(str(pid) for pid in settled["survivors"])
                log.write(f"still running after the kill: {alive}\n".encode())
        finally:
            if result_file is not None:
                result_file.close()

    _bound(log_path, MAX_LOG_BYTES)
    if result_path is not None:
        _bound(result_path, MAX_RESULT_BYTES)
    return returncode


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentctl-run")
    parser.add_argument("launch_input")
    parsed = parser.parse_args(arguments)
    try:
        launch = _read_input(Path(parsed.launch_input))
    except QueueInputError as error:
        print(str(error), file=sys.stderr)
        return REFUSED_EXIT_CODE
    # The input stays for `pueue restart`: a retry re-executes this same
    # command line. It is mode 0600 and lives with the task that names it.
    # The path travels on as written: a canceller reads that same string out
    # of the task's command to name the scope this run is about to create.
    return run(launch, launch_input=parsed.launch_input)


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
