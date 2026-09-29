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
service exits with its cgroup (``ExitType=cgroup``). Without ``--no-block``,
``systemd-run`` waits for unit startup; ``Type=exec`` makes its successful
return confirm the command was exec'd before releasing the allocation lock.
After that, the wrapper observes service completion while a canceller can
stop the unit without this wrapper's help.

The unit's Description is ``agentctl:<daemon>:<pool>:<pueue task id>``: the
pueue daemon the task belongs to and the exact pool, so the single-slot guard
considers only units of its own queue. Every other unit in the slice belongs to
another daemon (a test's private pueued) and is left alone.
"""

from __future__ import annotations

import argparse
import fcntl
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

from sinnix_lib.atomic import atomic_publish
from sinnix_lib.ledger import append_jsonl

from . import artifacts, pueue, worktrunk
from .launch_input import QueueInputError, read_input
from .limits import SYSTEMCTL_TIMEOUT_SECONDS
from .pueue import PueueError

# Default transport bounds. Captured artifacts are retained in full.
MAX_LOG_BYTES = 8_000_000
MAX_RESULT_BYTES = 64_000

# Exit statuses of the wrapper itself. 124 is timeout(1)'s, 130 is a
# SIGINT-shaped cancellation, 126 a command that could not be observed, and
# 75 is EX_TEMPFAIL: the slot is taken and the same task may run later.
TIMEOUT_EXIT_CODE = 124
REFUSED_EXIT_CODE = 125
CANCELLED_EXIT_CODE = 130
VANISHED_EXIT_CODE = 126
SLOT_OCCUPIED_EXIT_CODE = 75
UNIT_OBSERVATION_GRACE_SECONDS = 10
# Every running job's wrapper polls its unit through the user manager. A fixed
# 50 ms poll is 20 `systemctl show` calls a second per job; with two dozen jobs
# that saturates the manager, which then never dispatches queued unit starts.
# Start fast for short jobs, then back off to a bounded completion latency.
UNIT_POLL_INITIAL_SECONDS = 0.05
UNIT_POLL_MAX_SECONDS = 2.0


class Outcome(str, Enum):
    """How a run ended, as the result artifact and the finish event record it."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    VANISHED = "vanished"
    SLOT_OCCUPIED = "slot_occupied"


POOL_SLICE_PREFIX = "agentctl"
# The pools with a declared slice policy. Any other pueue group (a project's
# landing group, a fixture) runs under the normal slice.
POLICY_POOLS = frozenset(
    {
        "agent",
        "land-agent",
        "pytest",
        "pytest-heavy",
        "pytest-quick",
        "bulk",
        "normal",
        "interactive",
    }
)
DEFAULT_SLICE_POOL = "normal"
RUN_EXECUTABLE = "agentctl-run"
DESCRIPTION_PREFIX = "agentctl"

# The bytes of a unit name kept for the launch input's own stem. Unit names
# are bounded, and the prefix, the pool and the digest come first.
UNIT_STEM_BYTES = 100

# Files counted before the measurement stops and says so. A scratch tree
# larger than this is reported as a lower bound, never walked without end.
MAX_SCRATCH_ENTRIES = 100_000

# Git is probed for execution evidence, independently of the descriptor's
# cache policy.  These probes are deliberately bounded and read-only; failure
# is recorded as unavailable rather than changing the command's outcome.
GIT_OBSERVATION_TIMEOUT_SECONDS = 5.0


def unit_pool(group: str | None) -> str | None:
    """A pueue group as a unit name component."""
    if not isinstance(group, str):
        return None
    return re.sub(r"[^a-z0-9-]+", "-", group.strip().lower()).strip("-") or None


def pool_slice(pool: str) -> str:
    """The slice carrying a pool's units; pools without a policy share `normal`."""
    name = pool if pool in POLICY_POOLS else DEFAULT_SLICE_POOL
    return f"{POOL_SLICE_PREFIX}-{name}.slice"


def unit_description(daemon: str, pool: str, task: str) -> str:
    return f"{DESCRIPTION_PREFIX}:{daemon}:{pool}:{task}"


def unit_for(launch_input: object, pool: str) -> str:
    """Name the transient service carrying the task launched from ``launch_input``.

    The digest is of the whole path: a unit name is shorter than a path and
    drops the characters systemd reserves, and two tasks whose inputs differ
    only where the name is lossy must not share one unit.
    """
    text = str(PurePosixPath(str(launch_input)))
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    stem = re.sub(r"[^A-Za-z0-9_.-]", "-", PurePosixPath(text).stem).strip("-.")
    stem = stem[:UNIT_STEM_BYTES] or "job"
    return f"{POOL_SLICE_PREFIX}-{pool}-{stem}-{digest}.service"


def _sibling(log_path: object, suffix: str) -> Path:
    path = Path(str(log_path))
    stem = path.name[:-4] if path.name.endswith(".log") else path.name
    return path.with_name(stem + suffix)


def cancel_marker_for(log_path: object) -> Path:
    """``<jobs_dir>/<ref>.cancel``: written by the canceller before it stops the unit."""
    return _sibling(log_path, ".cancel")


def _marker_targets(marker: Path, attempt: int) -> bool:
    try:
        record = json.loads(marker.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(record, Mapping) and record.get("attempt") == attempt


def _attempt_root_for_marker(marker: Path) -> Path:
    stem = marker.name[:-7] if marker.name.endswith(".cancel") else marker.name
    return marker.parent / f"{stem}.attempts"


def _start_service(command: Sequence[str], marker: Path, attempt: int, log: Any):
    """Serialize service start acknowledgement with cancellation."""
    root = _attempt_root_for_marker(marker)
    with (root / ".allocation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if _marker_targets(marker, attempt):
            return None
        # Without --no-block, systemd-run waits for unit startup. Type=exec
        # makes successful return an exec acknowledgement rather than a
        # successful fork. This is the lock boundary; waiting for ActiveState
        # here can retain the lock until workload exit if a property read fails.
        return subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=log,
            check=False,
            env=systemd_environment(),
        )


def outcome_path_for(log_path: object) -> Path:
    """``<jobs_dir>/<ref>.outcome``: the wrapper's own record of how the run ended."""
    return _sibling(log_path, ".outcome")


def _git_probe(
    cwd: Path, *arguments: str, allow_empty: bool = False
) -> tuple[str | None, str | None]:
    """Return one read-only Git value and a stable failure token, if any."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            capture_output=True,
            text=True,
            timeout=GIT_OBSERVATION_TIMEOUT_SECONDS,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError:
        return None, "unavailable"
    value = (completed.stdout or "").strip()
    if completed.returncode != 0 or (not value and not allow_empty):
        return None, "unavailable"
    return value, None


def git_observation(cwd: Path, *, observed_at: str | None = None) -> dict[str, Any]:
    """Observe checkout identity at one bounded point in the job.

    The three values are retained when available, while ``status`` and
    ``reason`` make partial or failed probes explicit.  Matching start/end
    observations establish only unchanged endpoints; they cannot prove that a
    command did not modify and then restore the checkout between probes.
    """
    head, head_error = _git_probe(cwd, "rev-parse", "HEAD")
    tree, tree_error = _git_probe(cwd, "rev-parse", "HEAD^{tree}")
    dirty_value, dirty_error = _git_probe(
        cwd, "status", "--porcelain=v1", "--untracked-files=all", allow_empty=True
    )
    dirty: bool | None = None if dirty_error else bool(dirty_value)
    errors = [
        name
        for name, error in (
            ("head", head_error),
            ("tree", tree_error),
            ("dirty", dirty_error),
        )
        if error is not None
    ]
    from .content_identity import content_manifest

    content = content_manifest(cwd) if dirty is True else None
    return {
        "observed_at": observed_at
        or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "head": head,
        "tree": tree,
        "dirty": dirty,
        "content_manifest": content,
        "status": "observed" if not errors else "unavailable",
        "reason": None if not errors else "git_" + "_".join(errors) + "_unavailable",
    }


def execution_receipt(
    start: Mapping[str, Any], end: Mapping[str, Any]
) -> dict[str, Any]:
    """Bind two endpoint observations without claiming interval immutability."""
    available = all(
        observation.get("status") == "observed" for observation in (start, end)
    )
    same = all(
        start.get(field) == end.get(field) for field in ("head", "tree", "dirty")
    )
    content_start = start.get("content_manifest")
    content_end = end.get("content_manifest")
    if isinstance(content_start, Mapping) or isinstance(content_end, Mapping):
        same = (
            same
            and isinstance(content_start, Mapping)
            and isinstance(content_end, Mapping)
        )
        if isinstance(content_start, Mapping) and isinstance(content_end, Mapping):
            same = same and content_start.get("sha256") == content_end.get("sha256")
    if not available:
        binding = "unavailable"
        reason = "git_observation_unavailable"
    elif not same:
        binding = "changed"
        reason = "checkout_identity_changed_between_observations"
    else:
        binding = "unchanged_endpoints"
        reason = None
    return {
        "schema_version": 1,
        "start": dict(start),
        "end": dict(end),
        "binding": binding,
        "immutable_execution_attestation": None,
        "reason": reason,
    }


def remove_scratch(path: Path | None) -> None:
    """Drop a job's scratch directory; the job it belonged to is over."""
    if path is not None:
        shutil.rmtree(path, ignore_errors=True)


def scratch_footprint(path: Path) -> dict[str, Any]:
    """What the job left in its scratch: bytes and files, bounded by entry count.

    Sizes come from `lstat`, so a symlink counts as itself and never as the
    tree it points at.
    """
    total = 0
    files = 0
    truncated = False
    for directory, _directories, names in os.walk(path, followlinks=False):
        for name in names:
            if files >= MAX_SCRATCH_ENTRIES:
                truncated = True
                break
            try:
                total += os.lstat(os.path.join(directory, name)).st_size
            except OSError:
                continue
            files += 1
        if truncated:
            break
    return {"bytes": total, "files": files, "truncated": truncated}


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
    """Append one advisory lifecycle event. The spool is never state authority.

    Every spool writer goes through the shared ledger append, whose lock also
    covers its repair of an interrupted tail line.
    """
    if spool_path is None:
        return
    try:
        append_jsonl(
            spool_path,
            {
                "schema_version": 1,
                "emitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                **dict(event),
            },
        )
    except OSError:
        return


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


def _unit_snapshot(unit: str) -> dict[str, str] | None:
    """A successful show, including not-found, or None when observation failed."""
    shown = _systemctl(
        "show", "-p", "LoadState,ActiveState,Result,ExecMainStatus,ExecMainCode", unit
    )
    if shown is None:
        return None
    return dict(line.partition("=")[::2] for line in shown.splitlines() if "=" in line)


def unit_properties(unit: str) -> dict[str, str]:
    """The unit's terminal state, empty once systemd no longer knows it."""
    properties = _unit_snapshot(unit)
    return (
        properties
        if properties is not None and properties.get("LoadState") == "loaded"
        else {}
    )


def _wait_for_unit(unit: str, timeout_seconds: int) -> dict[str, str] | None:
    """Wait outside the allocation lock until completion or its observation deadline.

    Failed property queries are not evidence that the service completed. Bound
    the wait by the declared service runtime plus a short reporting grace so a
    broken systemd connection cannot strand the pueue wrapper indefinitely.
    """
    deadline = time.monotonic() + timeout_seconds + UNIT_OBSERVATION_GRACE_SECONDS
    delay = UNIT_POLL_INITIAL_SECONDS
    while time.monotonic() < deadline:
        properties = _unit_snapshot(unit)
        if properties is not None:
            load_state = properties.get("LoadState")
            active_state = properties.get("ActiveState")
            if load_state and load_state != "loaded":
                return {}
            if load_state == "loaded" and active_state in {"inactive", "failed"}:
                return properties
        time.sleep(delay)
        delay = min(delay * 2, UNIT_POLL_MAX_SECONDS)
    return None


def active_units(daemon: str, pool: str) -> dict[str, int | None]:
    """Every unit of this daemon's pool still running, whichever run created it.

    The name glob is a prefilter; the Description decides, so a pool whose
    name extends another's (``pytest-x``) and another daemon's units never
    count.
    """
    listed = _systemctl(
        "list-units",
        "--plain",
        "--no-legend",
        "--state=active,activating,deactivating",
        f"{POOL_SLICE_PREFIX}-{pool}-*",
    )
    prefix = unit_description(daemon, pool, "")
    units: dict[str, int | None] = {}
    for line in (listed or "").splitlines():
        columns = line.split(None, 4)
        if len(columns) == 5 and columns[4].strip().startswith(prefix):
            identity = columns[4].strip()[len(prefix) :]
            units[columns[0]] = int(identity) if identity.isdecimal() else None
    return units


def _occupancy(
    pool: str, unit: str, daemon: str, log: Any
) -> tuple[str, pueue.Task | None]:
    """Whether a single-slot pool is free, and the pueue task of this run.

    Returns ``("slot_occupied", ...)`` when a unit of this daemon's pool
    belongs to a task pueue still has running, or to no task this queue
    knows; a unit whose task is terminal is an orphan of a killed wrapper and
    is stopped here.
    """
    try:
        parallel = pueue.groups().get(pool)
        tasks = pueue.running_tasks(pool)
        units = active_units(daemon, pool) if parallel == 1 else {}
        if units:
            for task_id in units.values():
                if task_id is not None and task_id not in tasks:
                    owner = pueue.task_from_log(task_id)
                    if owner is not None:
                        tasks[task_id] = owner
    except PueueError:
        return "", None
    owners = {}
    for task in tasks.values():
        path = launch_input_of(task.command)
        if path is not None:
            owners[unit_for(path, pool)] = task
    own = owners.get(unit)
    if parallel != 1:
        return "", own
    for other in units:
        owner = owners.get(other)
        if other != unit and (owner is None or not owner.terminal):
            log.write(f"pool {pool} is occupied by {other}\n".encode())
            return "slot_occupied", own
        _systemctl("stop", other)
        _systemctl("reset-failed", other)
        log.write(f"settled_orphan {other}\n".encode())
    return "", own


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
        *(launch.get("unit_properties") or ()),
    ]
    return [
        "systemd-run",
        "--user",
        "--quiet",
        f"--unit={unit}",
        f"--slice={pool_slice(pool)}",
        f"--description={description}",
        *(f"--setenv={key}={value}" for key, value in environment.items()),
        *(argument for value in properties for argument in ("-p", value)),
        "--",
        *argv,
    ]


def _classify(
    client_status: int, cancelled: bool, properties: Mapping[str, str] | None
) -> tuple[Outcome, int]:
    """What the started unit says it did, or what its start request says.

    systemd unloads a successful transient service after it is inactive and
    keeps a failed one. A confirmed missing unit after a successful start
    request is therefore success; a failed observation is unresolved.
    """
    if cancelled:
        return Outcome.CANCELLED, CANCELLED_EXIT_CODE
    if properties is None:
        return Outcome.VANISHED, VANISHED_EXIT_CODE
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
    """Run one queued command, retaining complete output for this invocation."""
    marker = cancel_marker_for(launch["log_path"])
    launch = artifacts.begin(launch, launch_input)
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

    checkout = launch.get("checkout")

    def candidate_parts() -> tuple[Path, str, Path, str] | None:
        if not isinstance(checkout, Mapping) or checkout.get("kind") != "candidate":
            return None
        from .checkout import CANDIDATE_BRANCH_PREFIX

        root, branch, commit = (
            checkout.get(key) for key in ("root", "branch", "commit")
        )
        path = Path(launch["working_directory"])
        if (
            not all(isinstance(value, str) for value in (root, branch, commit))
            or not branch.startswith(CANDIDATE_BRANCH_PREFIX)
            or path == Path(root)
        ):
            raise ValueError("invalid candidate checkout ownership")
        return Path(root), branch, path, commit

    def release_candidate() -> None:
        if not isinstance(checkout, Mapping) or checkout.get("kind") != "candidate":
            return
        from .checkout import CheckoutError, release_candidate_checkout

        try:
            release_candidate_checkout(checkout, launch["working_directory"])
        except (CheckoutError, worktrunk.WorktrunkError) as error:
            with log_path.open("ab") as log:
                log.write(f"candidate cleanup deferred: {error}\n".encode())

    def refused() -> int:
        record = {
            "outcome": "refused",
            "exit_code": REFUSED_EXIT_CODE,
            "attempt": launch["attempt"],
        }
        atomic_publish(
            outcome_path_for(log_path),
            json.dumps(record, sort_keys=True).encode(),
            fsync=True,
            mode=0o600,
        )
        append_event(
            spool_path,
            {
                "kind": "queue-task",
                "job_id": launch["job_id"],
                "attempt": launch["attempt"],
                "phase": "finished",
                **record,
            },
        )
        release_candidate()
        return REFUSED_EXIT_CODE

    parts = candidate_parts()
    if parts is not None:
        root, branch, path, commit = parts
        try:
            registered = worktrunk.worktrunk_find(root, branch)
            if registered is None or registered.path is None:
                retained = (
                    checkout.get("cache_path")
                    if isinstance(checkout, Mapping)
                    else None
                )
                cache_path = Path(retained) if isinstance(retained, str) else None
                stub = path / ".cache"
                if path.exists():
                    if (
                        cache_path is None
                        or not stub.is_symlink()
                        or stub.resolve() != cache_path
                    ):
                        raise worktrunk.WorktrunkError("candidate path is occupied")
                    stub.unlink()
                    path.rmdir()
                try:
                    worktrunk.worktrunk_create(root, branch, path=path, base=commit)
                except worktrunk.WorktrunkError:
                    if (
                        cache_path is not None
                        and cache_path.is_dir()
                        and not path.exists()
                    ):
                        path.mkdir()
                        stub.symlink_to(cache_path, target_is_directory=True)
                    raise
                if cache_path is not None and cache_path.is_dir():
                    if (path / ".cache").is_dir():
                        shutil.rmtree(path / ".cache")
                    (path / ".cache").symlink_to(cache_path, target_is_directory=True)
            elif registered.path != path:
                raise worktrunk.WorktrunkError(
                    "candidate branch belongs to another path"
                )
            observed, error = _git_probe(path, "rev-parse", "HEAD")
            if error or observed != commit:
                raise worktrunk.WorktrunkError(
                    "candidate checkout moved from its pinned commit"
                )
        except worktrunk.WorktrunkError as error:
            log_path.write_text(f"candidate preparation failed: {error}\n")
            return refused()

    if not Path(launch["working_directory"]).is_dir():
        log_path.write_text(
            f"working directory is gone: {launch['working_directory']}\n"
        )
        return refused()
    # This is execution evidence, not the cache key captured by `job start`.
    # It is therefore collected for every operation, including cache=none.
    start_git = git_observation(Path(launch["working_directory"]))
    scratch = launch.get("scratch")
    scratch_dir = Path(scratch["path"]) if scratch else None
    if scratch_dir is not None:
        try:
            scratch_dir.parent.mkdir(parents=True, exist_ok=True)
            scratch_dir.mkdir(mode=0o700, exist_ok=True)
        except OSError as error:
            log_path.write_text(f"could not create the scratch directory: {error}\n")
            return refused()

    # The pueue group comes from `PUEUE_GROUP`, which pueued exports into every
    # task it spawns, so a launch input written by another repository is
    # contained exactly like one agentctl wrote.
    pool = unit_pool(os.environ.get("PUEUE_GROUP")) or unit_pool(launch.get("pool"))
    unit = unit_for(launch_input, pool) if pool else None
    daemon = pueue.daemon_tag()
    event = {
        "kind": "queue-task",
        "job_id": launch["job_id"],
        "attempt": launch["attempt"],
        "task_id": None,
        "label": launch.get("label", ""),
        "job_kind": launch.get("kind", "declared-operation"),
        "project": launch["project_id"],
        "operation": launch["operation"],
        "pool": pool,
        "unit": unit,
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
    if scratch_dir is not None:
        environment["AGENTCTL_SCRATCH"] = str(scratch_dir)
    argv = list(launch["argv"])
    executable = shutil.which(argv[0], path=environment.get("PATH", os.defpath))
    properties: dict[str, str] = {}
    # Both files are appended to, by this process and by systemd alike, so
    # neither writer overwrites what the other put there.
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_bytes(b"")
    stdout_path.write_bytes(b"")
    with open(log_path, "ab") as log, open(stdout_path, "ab") as stdout:
        if _marker_targets(marker, launch["attempt"]):
            outcome, status = Outcome.CANCELLED, CANCELLED_EXIT_CODE
        else:
            if executable is None:
                log.write(
                    f"could not start the command: {argv[0]} not found\n".encode()
                )
                remove_scratch(scratch_dir)
                return refused()
            argv[0] = executable
            try:
                if unit is None or pool is None:
                    outcome, status = _run_bare(argv, launch, environment, stdout, log)
                else:
                    refusal, own = _occupancy(pool, unit, daemon, log)
                    if own is not None:
                        event["task_id"] = own.task_id
                    if refusal:
                        outcome, status = Outcome.SLOT_OCCUPIED, SLOT_OCCUPIED_EXIT_CODE
                    else:
                        command = _service_command(
                            launch,
                            unit=unit,
                            pool=pool,
                            description=unit_description(
                                daemon,
                                pool,
                                str(own.task_id) if own is not None else launch_input,
                            ),
                            argv=argv,
                            environment=environment,
                            stdout=stdout_path,
                            log_path=log_path,
                        )
                        client = _start_service(command, marker, launch["attempt"], log)
                        if client is None:
                            outcome, status = Outcome.CANCELLED, CANCELLED_EXIT_CODE
                        else:
                            return_code = client.returncode
                            properties = (
                                _wait_for_unit(unit, launch["timeout_seconds"])
                                if return_code == 0
                                else unit_properties(unit)
                            )
                            outcome, status = _classify(
                                return_code,
                                _marker_targets(marker, launch["attempt"]),
                                properties,
                            )
                            _systemctl("reset-failed", unit)
                            if outcome is Outcome.VANISHED:
                                log.write(
                                    f"unit {unit} vanished (rc {return_code})\n".encode()
                                )
            except OSError as error:
                log.write(f"could not start the command: {error}\n".encode())
                remove_scratch(scratch_dir)
                return refused()
            if outcome is Outcome.TIMEOUT:
                log.write(
                    f"timed out after {launch['timeout_seconds']} seconds\n".encode()
                )
    with (_attempt_root_for_marker(marker) / ".allocation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if _marker_targets(marker, launch["attempt"]):
            marker.unlink(missing_ok=True)
        fcntl.flock(lock, fcntl.LOCK_UN)

    end_git = git_observation(Path(launch["working_directory"]))

    record: dict[str, Any] = {
        "attempt": launch["attempt"],
        "outcome": outcome.value,
        "exit_code": status,
        "unit": unit,
        "pool": pool,
        "systemd_result": properties.get("Result") if properties is not None else None,
        "execution_receipt": execution_receipt(start_git, end_git),
        "execution_evidence": {
            "schema_version": 1,
            "selector": list(launch.get("argv") or ()),
            "phase": "unit_lifecycle",
            "command_execution_observed": None,
            "result": {"outcome": outcome.value, "exit_code": status},
            "environment_identity": hashlib.sha256(
                json.dumps(launch.get("environment") or {}, sort_keys=True).encode()
            ).hexdigest(),
            "environment_identity_method": "sha256 of declared launch environment JSON",
            "published_artifact_refs": [],
            "coverage_gaps": [
                "Inner provisioning, collection, test and product phases require owner stage records."
            ],
        },
    }
    if scratch_dir is not None:
        # Measured now, while the unit has exited and nothing else writes
        # there; the record outlives the directory, which goes with the job.
        record["scratch"] = {
            "kind": str(scratch["kind"]),
            "path": str(scratch_dir),
            **scratch_footprint(scratch_dir),
        }
        remove_scratch(scratch_dir)
    atomic_publish(
        outcome_path_for(log_path),
        json.dumps(record, sort_keys=True).encode(),
        fsync=True,
        mode=0o600,
    )
    append_event(spool_path, {**event, "phase": "finished", **record})
    release_candidate()
    return status


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=RUN_EXECUTABLE)
    parser.add_argument("launch_input")
    parsed = parser.parse_args(arguments)
    try:
        launch = read_input(Path(parsed.launch_input))
    except QueueInputError as error:
        print(str(error), file=sys.stderr)
        return REFUSED_EXIT_CODE
    # The input stays for `pueue restart`: a retry re-executes this same
    # command line. The path travels on as written: a canceller reads that
    # same string out of the task's command to name the unit this run creates.
    return run(launch, launch_input=parsed.launch_input)


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
