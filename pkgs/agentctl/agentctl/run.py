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
ordinary service exits with its cgroup (``ExitType=cgroup``). A verifier with
required services uses ``ExitType=main`` so systemd stops daemonized children
when verification ends. Without ``--no-block``,
``systemd-run`` waits for unit startup; ``Type=exec`` makes its successful
return confirm the command was exec'd before releasing the allocation lock.
After that, the wrapper observes service completion while a canceller can
stop the unit without this wrapper's help. RemainAfterExit retains terminal
status until the wrapper reads it, then the wrapper stops and releases its unit.

"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from sinnix_lib.atomic import atomic_publish
from sinnix_lib.ledger import append_jsonl
from sinnix_lib.secrets import mask_secret_values, secret_values

from . import artifacts, pueue
from .launch_input import QueueInputError, read_input, secret_environment
from .limits import SYSTEMCTL_TIMEOUT_SECONDS

# Default transport bounds. Captured artifacts are retained in full.
MAX_LOG_BYTES = 8_000_000
MAX_RESULT_BYTES = 64_000

# Exit statuses of the wrapper itself. 124 is timeout(1)'s, 130 is a
# SIGINT-shaped cancellation, 126 a command that could not be observed and
# 121 a unit the out-of-memory killer ended (no common tool exits 121).
TIMEOUT_EXIT_CODE = 124
REFUSED_EXIT_CODE = 125
CANCELLED_EXIT_CODE = 130
VANISHED_EXIT_CODE = 126
OUT_OF_MEMORY_EXIT_CODE = 121
BUS_CONNECT_RETRY_SECONDS = 10
USER_BUS_CONNECTION_REFUSED = (
    b"Failed to connect to user scope bus via local transport: Connection refused"
)
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
    OUT_OF_MEMORY = "out-of-memory"


# Pool slices sit under agent-ctl.slice, inside the host's agent budget
# (agent.slice); slice names encode that hierarchy. Unit names keep their
# own prefix.
POOL_SLICE_PREFIX = "agent-ctl"
UNIT_PREFIX = "agentctl"
# The pools with a declared slice policy. Any other pueue group (a fixture,
# the default group) runs under the normal slice.
POLICY_POOLS = frozenset(
    {
        "agent",
        "pytest",
        "pytest-heavy",
        "pytest-quick",
        "bulk",
        "normal",
        "interactive",
        "shell-quick",
        "shell-long",
        "compile",
        "background",
        "measure",
        "system-build",
        "codex",
    }
)
DEFAULT_SLICE_POOL = "normal"
# Measurements cannot be retried without losing the run, so their units rank
# low for the kernel OOM killer and last for oomd within their own cgroup.
PROTECTED_POOLS = frozenset({"measure"})
RUN_EXECUTABLE = "agentctl-run"
DESCRIPTION_PREFIX = "agentctl"

# The bytes of a unit name kept for the launch input's own stem. Unit names
# are bounded, and the prefix, the pool and the digest come first.
UNIT_STEM_BYTES = 100

# Git checks around cached commands must remain bounded.
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
    return f"{UNIT_PREFIX}-{pool}-{stem}-{digest}.service"


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


def _start_service(
    command: Sequence[str],
    marker: Path,
    attempt: int,
    log: Any,
):
    """Serialize startup with cancellation; retry only a confirmed absent unit."""
    root = _attempt_root_for_marker(marker)
    unit = next(
        (arg.removeprefix("--unit=") for arg in command if arg.startswith("--unit=")),
        None,
    )
    deadline = None
    delay = 0.25

    def note(message: str) -> None:
        if log is None:
            print(message, file=sys.stderr)
        else:
            log.write((message + "\n").encode())
            log.flush()

    while True:
        with (root / ".allocation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if _marker_targets(marker, attempt):
                return None
            # Keep client diagnostics separate from payload stderr: a payload
            # must never be able to print its way into a startup retry.
            with tempfile.TemporaryFile(dir=root) as errors:
                client = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=errors,
                    check=False,
                    # Only the startup client needs a stable diagnostic locale;
                    # the payload environment is declared separately on the unit.
                    env={**systemd_environment(), "LC_ALL": "C"},
                )
                errors.seek(0)
                retryable = (
                    client.returncode != 0
                    and errors.read(512).strip() == USER_BUS_CONNECTION_REFUSED
                    and not errors.read(1)
                )
                errors.seek(0)
                if log is None:
                    while block := errors.read(65536):
                        sys.stderr.write(
                            block.decode("utf-8", errors="backslashreplace")
                        )
                else:
                    shutil.copyfileobj(errors, log)
                    log.flush()
        if not retryable or unit is None:
            return client
        if deadline is None:
            deadline = time.monotonic() + BUS_CONNECT_RETRY_SECONDS
            note(
                "startup connection refused; waiting for confirmed unit absence before retry"
            )
        # Neither backoff nor manager observation may retain the cancellation lock.
        while True:
            if _marker_targets(marker, attempt):
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                note(
                    "startup connection recovery budget exhausted; service not resubmitted"
                )
                return client
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, 1.0)
            if _marker_targets(marker, attempt):
                return None
            properties = _unit_snapshot(unit)
            if properties is not None and properties.get("LoadState") != "not-found":
                note("startup unit is not confirmed absent; service not resubmitted")
                return client
            if time.monotonic() < deadline and properties is not None:
                note(
                    "user manager confirms unit absent; retrying the same service identity"
                )
                break


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


def content_tree(cwd: Path) -> str | None:
    """Git tree id of the working copy, including untracked nonignored files.

    Built in a throwaway index seeded from the real one, so the real index is
    never written and unchanged files keep their cached stat data. `git add`
    stores blobs for changed files in the object database; Git's own gc
    reclaims them if no commit ever refers to them.
    """
    index, error = _git_probe(cwd, "rev-parse", "--git-path", "index")
    if error is not None or index is None:
        return None
    with tempfile.TemporaryDirectory(prefix="agentctl-tree-") as scratch:
        scratch_index = Path(scratch) / "index"
        real_index = Path(index) if Path(index).is_absolute() else cwd / index
        try:
            shutil.copyfile(real_index, scratch_index)
        except FileNotFoundError:
            pass
        except OSError:
            return None
        environment = {
            **os.environ,
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_INDEX_FILE": str(scratch_index),
        }
        try:
            for arguments in (["add", "-A"], ["write-tree"]):
                completed = subprocess.run(
                    ["git", "-C", str(cwd), *arguments],
                    capture_output=True,
                    text=True,
                    timeout=GIT_OBSERVATION_TIMEOUT_SECONDS * 6,
                    env=environment,
                )
                if completed.returncode != 0:
                    return None
        except (OSError, subprocess.TimeoutExpired):
            return None
        return completed.stdout.strip() or None


def git_observation(cwd: Path, *, observed_at: str | None = None) -> dict[str, Any]:
    """Observe checkout identity at one bounded point in the job.

    The values are retained when available, while ``status`` and ``reason``
    make partial or failed probes explicit. A dirty checkout also records
    ``content_tree``, the tree id of its working copy. Matching start/end
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
    observation: dict[str, Any] = {
        "observed_at": observed_at
        or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "head": head,
        "tree": tree,
        "dirty": dirty,
    }
    if dirty is True:
        observation["content_tree"] = content_tree(cwd)
        if observation["content_tree"] is None:
            errors.append("content")
    observation["status"] = "observed" if not errors else "unavailable"
    observation["reason"] = (
        None if not errors else "git_" + "_".join(errors) + "_unavailable"
    )
    return observation


def execution_receipt(
    start: Mapping[str, Any], end: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare two endpoint observations without claiming interval immutability."""
    available = all(
        observation.get("status") == "observed" for observation in (start, end)
    )
    same = all(
        start.get(field) == end.get(field)
        for field in ("head", "tree", "dirty", "content_tree")
    )
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
        "schema_version": 2,
        "start": dict(start),
        "end": dict(end),
        "binding": binding,
        "reason": reason,
    }


def remove_scratch(path: Path | None) -> str | None:
    """Drop owned scratch, reporting failures without hiding command status."""
    if path is None:
        return None
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return None
    except OSError as error:
        # Do not copy a potentially sensitive child filename into the result.
        return f"{type(error).__name__} (errno {error.errno})"
    return None


class _Scratch:
    """One attempt's files may be removed only after its unit stops."""

    def __init__(self) -> None:
        self.path: Path | None = None
        self.unit: str | None = None
        self.cleaned = False

    def release_unit(self) -> str | None:
        if self.unit is None:
            return None
        if _systemctl("stop", self.unit) is None:
            observed = _unit_snapshot(self.unit)
            if observed is None or (
                observed.get("LoadState") != "not-found"
                and not _unit_is_terminal(observed)
            ):
                return "unit termination unconfirmed; cleanup deferred"
        _systemctl("reset-failed", self.unit)
        self.unit = None
        return None

    def cleanup(self) -> str | None:
        if self.cleaned:
            return None
        self.cleaned = True
        error = self.release_unit()
        if error is not None:
            return error
        path, self.path = self.path, None
        return remove_scratch(path)


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
        "show",
        "-p",
        "LoadState,ActiveState,SubState,Result,ExecMainStatus,ExecMainCode,Type,ActiveEnterTimestampMonotonic,Job",
        unit,
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


def _unit_is_terminal(properties: Mapping[str, str]) -> bool:
    if properties.get("Job", "") not in {"", "0"}:
        return False
    return properties.get("LoadState") == "loaded" and (
        properties.get("ActiveState") in {"inactive", "failed"}
        or (
            properties.get("ActiveState") == "active"
            and properties.get("SubState") == "exited"
        )
    )


def _wait_for_unit(unit: str) -> dict[str, str]:
    """Observe completion; systemd alone owns the queued command's deadline.

    The launch budget cannot prove an active or stopping unit completed.
    Failed property reads retain ownership until the manager recovers or
    cancellation stops it. Neither elapsed wrapper time nor a query failure
    proves command completion.
    """
    delay = UNIT_POLL_INITIAL_SECONDS
    while True:
        properties = _unit_snapshot(unit)
        if properties is not None:
            load_state = properties.get("LoadState")
            if load_state and load_state != "loaded":
                return {}
            if _unit_is_terminal(properties):
                return properties
        time.sleep(delay)
        delay = min(delay * 2, UNIT_POLL_MAX_SECONDS)


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
        f"RuntimeMaxSec={launch['timeout_seconds'] or 'infinity'}",
        "Type=exec",
        "ExitType=cgroup",
        "KillMode=control-group",
        "RemainAfterExit=yes",
        "IOAccounting=yes",
        # Job units rank above Chrome tab renderers (200-300) for global OOM kills.
        "OOMScoreAdjust=900" if pool not in PROTECTED_POOLS else "OOMScoreAdjust=100",
        # A kernel OOM kill of any process ends the whole unit at once
        # (memory.oom.group), so a job never continues with a killed child.
        "OOMPolicy=kill",
        *(("ManagedOOMPreference=avoid",) if pool in PROTECTED_POOLS else ()),
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
    cancelled: bool, properties: Mapping[str, str] | None
) -> tuple[Outcome, int]:
    """What the unit's terminal state and cancellation say it did.

    Startup acknowledgement does not report command completion. The retained
    unit must supply its terminal status; a missing unit or failed observation
    leaves the command outcome unresolved.
    """
    if cancelled:
        return Outcome.CANCELLED, CANCELLED_EXIT_CODE
    if properties is None:
        return Outcome.VANISHED, VANISHED_EXIT_CODE
    if not properties or not _unit_is_terminal(properties):
        return Outcome.VANISHED, VANISHED_EXIT_CODE
    if properties.get("Result") == "timeout":
        return Outcome.TIMEOUT, TIMEOUT_EXIT_CODE
    # The kernel's and systemd-oomd's kills both end the unit with this result.
    if properties.get("Result") == "oom-kill":
        return Outcome.OUT_OF_MEMORY, OUT_OF_MEMORY_EXIT_CODE
    try:
        status = int(properties.get("ExecMainStatus", ""))
    except ValueError:
        return Outcome.VANISHED, VANISHED_EXIT_CODE
    # `show` prints the CLD_* code: 2 killed by a signal, 3 dumped core.
    if properties.get("ExecMainCode") in {"2", "3", "killed", "dumped"}:
        status += 128
    if properties.get("Result") == "success" and status == 0:
        if properties.get("ExecMainCode") not in {"1", "exited"}:
            # A loaded but never-executed unit also reports default zero status.
            return Outcome.VANISHED, VANISHED_EXIT_CODE
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
        status = process.wait(timeout=launch["timeout_seconds"] or None)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        return Outcome.TIMEOUT, TIMEOUT_EXIT_CODE
    except BaseException:
        # The foreground caller also owns an operation without a deadline.
        # Settle its original process group before propagating cancellation.
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # The original group exited between observation and kill.
        process.wait()
        raise
    return (Outcome.SUCCESS, 0) if status == 0 else (Outcome.FAILED, status)


def _mask_logs(paths: Sequence[Path], values: tuple[bytes, ...]) -> None:
    """Replace secret values a command printed, once nothing writes the logs.

    The masks keep each value's length, so recorded byte offsets stay valid.
    """
    if not values:
        return
    for path in dict.fromkeys(paths):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        masked = mask_secret_values(data, values)
        if masked != data:
            atomic_publish(path, masked, fsync=True, mode=0o600)


def run(launch: Mapping[str, Any], *, launch_input: str) -> int:
    """Run one queued command, retaining complete output for this invocation."""
    scratch_owner = _Scratch()
    try:
        return _run(launch, launch_input=launch_input, scratch_owner=scratch_owner)
    finally:
        error = scratch_owner.cleanup()
        if error is not None:
            print(
                f"agentctl: {error}; unit={scratch_owner.unit} scratch={scratch_owner.path}",
                file=sys.stderr,
            )


def _run(
    launch: Mapping[str, Any], *, launch_input: str, scratch_owner: _Scratch
) -> int:
    declared_log_path = Path(launch["log_path"])
    marker = cancel_marker_for(declared_log_path)
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

    event = {
        "kind": "queue-task",
        "job_id": launch["job_id"],
        "attempt": launch["attempt"],
        "task_id": int(os.environ["PUEUE_ID"])
        if os.environ.get("PUEUE_ID", "").isdecimal()
        else launch.get("queue_task_id"),
        "label": launch.get("label", ""),
        "job_kind": launch.get("kind", "declared-operation"),
        "project": launch["project_id"],
        "operation": launch["operation"],
        "pool": launch.get("pool"),
        "unit": None,
        "working_directory": launch["working_directory"],
    }

    def publish_outcome(record: Mapping[str, Any]) -> None:
        # Inventories stay with the attempt owner. The finish event references
        # the exact published bytes, never the mutable latest-attempt alias.
        payload = json.dumps(record, sort_keys=True).encode()
        path = outcome_path_for(log_path)
        atomic_publish(path, payload, fsync=True, mode=0o600)
        append_event(
            spool_path,
            {
                **event,
                "phase": "finished",
                "outcome": record["outcome"],
                "exit_code": record["exit_code"],
                "outcome_ref": {
                    "path": str(path.absolute()),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                },
            },
        )

    def refused(*, scratch_error: str | None = None) -> int:
        record: dict[str, Any] = {
            "outcome": "refused",
            "exit_code": REFUSED_EXIT_CODE,
            "attempt": launch["attempt"],
        }
        if scratch_owner.unit is not None:
            record["unit"] = scratch_owner.unit
        if scratch_error is not None:
            if scratch_dir is None:
                record["unit_error"] = scratch_error
            else:
                record["scratch"] = {
                    "path": str(scratch_dir),
                    "cleanup_error": scratch_error,
                }
        request = artifacts.cancellation(declared_log_path, launch["attempt"])
        if request:
            record["cancellation"] = request
        publish_outcome(record)
        return REFUSED_EXIT_CODE

    scratch = launch.get("scratch")
    scratch_dir = Path(scratch["path"]) if scratch else None
    pool = unit_pool(os.environ.get("PUEUE_GROUP")) or unit_pool(launch.get("pool"))
    unit = unit_for(launch_input, pool) if pool else None
    daemon = pueue.daemon_tag()
    event.update(pool=pool, unit=unit)
    if unit is not None:
        root = _attempt_root_for_marker(marker)
        with (root / ".allocation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            scratch_owner.unit = unit
            error = scratch_owner.release_unit()
            if error is not None:
                log_path.write_text(f"could not stop previous unit {unit}\n")
                return refused(scratch_error=error)
    if not Path(launch["working_directory"]).is_dir():
        log_path.write_text(
            f"working directory is gone: {launch['working_directory']}\n"
        )
        return refused()
    cached = (
        launch.get("tree_receipt") is not None
        and launch.get("environment_receipt") is not None
    )
    start_git = git_observation(Path(launch["working_directory"])) if cached else None
    if scratch_dir is not None:
        try:
            scratch_dir.parent.mkdir(parents=True, exist_ok=True)
            # Existing material has not been created by this attempt. Never
            # adopt it, follow its link, or later remove it as owned scratch.
            scratch_dir.mkdir(mode=0o700)
            scratch_owner.path = scratch_dir
        except OSError as error:
            log_path.write_text(f"could not create the scratch directory: {error}\n")
            return refused()

    append_event(spool_path, {**event, "phase": "started"})

    # Pass the queue identity to the command so nested calls know they are workers.
    environment = dict(launch["environment"])
    # Secret values join the child's environment only; the launch input and
    # every identity computed from it keep their names alone.
    secrets, lost_secrets = secret_environment(Path(launch_input), launch)
    environment.update(secrets)
    # This attempt supplies its own identity rather than inheriting a parent job.
    for field in (
        "JOB_ID",
        "CORRELATION_ID",
        "PROJECT_ID",
        "OPERATION",
        "CHECKOUT_ID",
        "CHECKOUT_HEAD",
    ):
        environment.pop(f"AGENTCTL_{field}", None)
    environment.update(
        {
            "DEVKIT_JOB_RUNNER": "agentctl",
            "DEVKIT_JOB_ID": str(launch["job_id"]),
            "AGENTCTL_CORRELATION_ID": str(launch["job_id"]),
            "AGENTCTL_JOB_ID": str(launch["job_id"]),
            "AGENTCTL_PROJECT_ID": str(launch["project_id"]),
            "AGENTCTL_OPERATION": str(launch["operation"]),
            "AGENTCTL_QUEUE_WORKER": "1",
        }
    )
    root = launch.get("project_root")
    checkout_path, _ = _git_probe(
        Path(launch["working_directory"]), "rev-parse", "--show-toplevel"
    )
    if isinstance(root, str) and root and checkout_path:
        path = Path(checkout_path).resolve()
        environment["AGENTCTL_CHECKOUT_ID"] = (
            "default"
            if path == Path(root).resolve()
            else "worktree-" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
        )
    head = (
        start_git.get("head")
        if start_git is not None
        else _git_probe(Path(launch["working_directory"]), "rev-parse", "HEAD")[0]
    )
    if isinstance(head, str) and head:
        environment["AGENTCTL_CHECKOUT_HEAD"] = head
    if pool:
        environment["AGENTCTL_POOL"] = pool
    environment.pop("DEVKIT_SCRATCH", None)
    if scratch_dir is not None:
        environment["AGENTCTL_SCRATCH"] = str(scratch_dir)
        environment["DEVKIT_SCRATCH"] = str(scratch_dir)
        environment["TMPDIR"] = str(scratch_dir)
    argv = list(launch["argv"])
    executable = shutil.which(argv[0], path=environment.get("PATH", os.defpath))
    properties: dict[str, str] = {}
    # Both files are appended to, by this process and by systemd alike, so
    # neither writer overwrites what the other put there.
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_bytes(b"")
    stdout_path.write_bytes(b"")
    with open(log_path, "ab") as log, open(stdout_path, "ab") as stdout:
        if lost_secrets:
            log.write(
                "secret environment no longer held (runtime directory was "
                f"reset): {', '.join(lost_secrets)}\n".encode()
            )
            log.flush()
        if _marker_targets(marker, launch["attempt"]):
            outcome, status = Outcome.CANCELLED, CANCELLED_EXIT_CODE
        else:
            if executable is None:
                log.write(
                    f"could not start the command: {argv[0]} not found\n".encode()
                )
                return refused(scratch_error=scratch_owner.cleanup())
            argv[0] = executable
            try:
                if unit is None or pool is None:
                    outcome, status = _run_bare(argv, launch, environment, stdout, log)
                else:
                    command = _service_command(
                        launch,
                        unit=unit,
                        pool=pool,
                        description=unit_description(
                            daemon,
                            pool,
                            str(event["task_id"])
                            if event["task_id"] is not None
                            else launch_input,
                        ),
                        argv=argv,
                        environment=environment,
                        stdout=stdout_path,
                        log_path=log_path,
                    )
                    # Acceptance can precede a lost startup acknowledgement.
                    scratch_owner.unit = unit
                    client = _start_service(
                        command,
                        marker,
                        launch["attempt"],
                        log,
                    )
                    if client is None:
                        outcome, status = Outcome.CANCELLED, CANCELLED_EXIT_CODE
                    else:
                        return_code = client.returncode
                        if return_code == 0:
                            properties = _wait_for_unit(unit)
                        else:
                            properties = _unit_snapshot(unit)
                            if (
                                properties is None
                                or not properties.get("LoadState")
                                or (
                                    properties.get("LoadState") == "loaded"
                                    and not _unit_is_terminal(properties)
                                )
                            ):
                                # An acknowledgement can be lost after acceptance.
                                # Observe that unit; never resubmit its payload.
                                properties = _wait_for_unit(unit)
                        outcome, status = _classify(
                            _marker_targets(marker, launch["attempt"]),
                            properties,
                        )
                        # Capture terminal status before releasing this unit.
                        # Stop also ends retained verifier descendants.
                        release_error = scratch_owner.release_unit()
                        if release_error is not None:
                            log.write((release_error + "\n").encode())
                            outcome, status = (
                                Outcome.VANISHED,
                                VANISHED_EXIT_CODE,
                            )
                        if outcome is Outcome.VANISHED:
                            log.write(
                                f"unit {unit} vanished (rc {return_code})\n".encode()
                            )
            except OSError as error:
                action = "control" if scratch_owner.unit is not None else "start"
                log.write(f"could not {action} the command: {error}\n".encode())
                return refused(scratch_error=scratch_owner.cleanup())
            if outcome is Outcome.OUT_OF_MEMORY:
                log.write(
                    b"killed: out of memory in the agent budget "
                    b"(docs/resource-control.md)\n"
                )
            if outcome is Outcome.TIMEOUT:
                message = (
                    f"timed out after {launch['timeout_seconds']} seconds\n"
                    if unit is None or pool is None
                    else "unit runtime deadline expired\n"
                )
                log.write(message.encode())
    with (_attempt_root_for_marker(marker) / ".allocation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if _marker_targets(marker, launch["attempt"]):
            marker.unlink(missing_ok=True)
        fcntl.flock(lock, fcntl.LOCK_UN)
    _mask_logs((log_path, stdout_path), secret_values(secrets))

    record: dict[str, Any] = {
        "attempt": launch["attempt"],
        "outcome": outcome.value,
        "exit_code": status,
        "unit": unit,
        "pool": pool,
        "systemd_result": properties.get("Result") if properties is not None else None,
    }
    if start_git is not None:
        end_git = git_observation(Path(launch["working_directory"]))
        record["execution_receipt"] = execution_receipt(start_git, end_git)
        record["execution_evidence"] = {
            "environment_identity": hashlib.sha256(
                json.dumps(launch.get("environment") or {}, sort_keys=True).encode()
            ).hexdigest(),
        }
    request = artifacts.cancellation(declared_log_path, launch["attempt"])
    if request:
        record["cancellation"] = request
    if scratch_dir is not None:
        cleanup_error = scratch_owner.cleanup()
        if cleanup_error is not None:
            record["scratch"] = {
                "path": str(scratch_dir),
                "cleanup_error": cleanup_error,
            }
    publish_outcome(record)
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
