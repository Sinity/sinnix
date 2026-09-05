"""The pueue adapter: the queue, its groups, and one task's observable state.

agentctl does not queue, admit, throttle, retry, or reap. pueued does, and its
own state is the record. This module is the only place that shells out to it.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

# pueue records the environment of the `pueue add` client into its state file,
# which is world-readable. A daemon that added tasks with its own environment
# would publish every inherited secret; the wrapper reconstructs the declared
# environment at exec time instead.
_CLIENT_ENVIRONMENT_KEYS = ("HOME", "PATH", "XDG_RUNTIME_DIR", "XDG_DATA_HOME")

# Every call is a local socket round trip. A minute distinguishes a wedged
# daemon from a slow one; `wait` is the one call that legitimately blocks and
# carries its own deadline.
CALL_TIMEOUT_SECONDS = 60

TERMINAL_STATUS = "Done"


class PueueError(RuntimeError):
    """pueue refused a request or published output this module cannot read."""


class PueueGroupError(PueueError):
    """The named group does not exist. A configuration defect, never transient."""

    def __init__(self, group: str) -> None:
        self.group = group
        super().__init__(
            f"pueue has no group {group!r}; create it with "
            f"`pueue group add {group}` and set its parallelism"
        )


@dataclass(frozen=True)
class Task:
    """One entry of ``pueue status --json``, reduced to what agentctl reads."""

    task_id: int
    label: str
    group: str
    status: str
    result: str | None
    exit_code: int | None
    path: str
    dependencies: tuple[int, ...]
    # The queued command line as pueue stores it. The wrapper's launch-input
    # path inside it is how a task's artifacts are found without a ledger.
    command: str = ""
    enqueued_at: str | None = None
    started_at: str | None = None
    ended_at: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status == TERMINAL_STATUS

    @property
    def succeeded(self) -> bool:
        return self.result == "Success"

    @classmethod
    def from_entry(cls, entry: Mapping[str, Any]) -> Task:
        status, detail = _variant(entry.get("status"))
        result, exit_code = _result(detail.get("result"))
        try:
            task_id = int(entry["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise PueueError("pueue task has no integer id") from error
        return cls(
            task_id=task_id,
            label=str(entry.get("label") or ""),
            group=str(entry.get("group") or ""),
            status=status,
            result=result,
            exit_code=exit_code,
            path=str(entry.get("path") or ""),
            dependencies=tuple(int(value) for value in entry.get("dependencies") or ()),
            command=str(entry.get("command") or ""),
            enqueued_at=_stamp(detail.get("enqueued_at")),
            started_at=_stamp(detail.get("start")),
            ended_at=_stamp(detail.get("end")),
        )


def _stamp(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _variant(value: Any) -> tuple[str, Mapping[str, Any]]:
    """Read one serde externally-tagged enum: ``"Name"`` or ``{"Name": {...}}``."""
    if isinstance(value, str):
        return value, {}
    if isinstance(value, Mapping) and len(value) == 1:
        name, detail = next(iter(value.items()))
        return str(name), detail if isinstance(detail, Mapping) else {}
    raise PueueError(f"pueue published an unreadable enum: {value!r}")


def _result(value: Any) -> tuple[str | None, int | None]:
    """Read a task result: ``"Success"``, ``"Killed"``, or ``{"Failed": 3}``."""
    if value is None:
        return None, None
    if isinstance(value, str):
        return value, 0 if value == "Success" else None
    if isinstance(value, Mapping) and len(value) == 1:
        name, payload = next(iter(value.items()))
        return str(name), payload if isinstance(payload, int) else None
    raise PueueError(f"pueue published an unreadable result: {value!r}")


def _client_environment() -> dict[str, str]:
    return {
        key: os.environ[key] for key in _CLIENT_ENVIRONMENT_KEYS if key in os.environ
    }


def daemon_tag() -> str:
    """A short name for the daemon this module's calls reach.

    The client resolves its daemon from ``$HOME/.config/pueue/pueue.yml``
    (this module forwards HOME alone, never XDG_CONFIG_HOME), so the tag is a
    digest of that path: one per daemon, stable across restarts, different for
    a daemon started under another home.
    """
    home = _client_environment().get("HOME") or str(Path.home())
    config = str(Path(home) / ".config" / "pueue" / "pueue.yml")
    return hashlib.sha256(config.encode()).hexdigest()[:12]


def _run(arguments: Sequence[str], *, timeout: float = CALL_TIMEOUT_SECONDS) -> str:
    try:
        completed = subprocess.run(
            ["pueue", *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_client_environment(),
        )
    except FileNotFoundError as error:
        raise PueueError("pueue is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise PueueError(f"pueue {arguments[0]} timed out") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PueueError(detail or f"pueue {arguments[0]} failed")
    return completed.stdout


def _decode(payload: str, what: str) -> Any:
    for index, character in enumerate(payload):
        if character in "{[":
            try:
                return json.loads(payload[index:])
            except json.JSONDecodeError:
                break
    raise PueueError(f"pueue {what} did not print a JSON document")


def add(
    *,
    group: str,
    label: str,
    command: Sequence[str],
    working_directory: Path,
    after: Sequence[int] = (),
    stashed: bool = False,
) -> int:
    """Enqueue one command and return the task id pueue assigned it.

    ``after`` lists the tasks this one waits for; ``stashed`` adds it held, to
    be released later by :func:`enqueue`.
    """
    if not command:
        raise PueueError("pueue add requires a command")
    # pueue joins the command into one string and runs it through a shell.
    # --escape quotes every argument so the string re-parses to this exact
    # argv; without it `sh -c "a; b"` silently becomes three shell words.
    arguments = [
        "add",
        "--escape",
        "--group",
        group,
        "--label",
        label,
        "--working-directory",
        str(working_directory),
        "--print-task-id",
    ]
    for dependency in after:
        arguments.extend(["--after", str(dependency)])
    if stashed:
        arguments.append("--stashed")
    arguments.append("--")
    arguments.extend(command)
    try:
        printed = _run(arguments).strip()
    except PueueError:
        # A missing group is the one add failure that retrying cannot fix.
        # Ask pueue which groups exist rather than matching its error text.
        if group not in groups():
            raise PueueGroupError(group) from None
        raise
    try:
        return int(printed.splitlines()[-1])
    except (IndexError, ValueError) as error:
        raise PueueError(f"pueue add did not print a task id: {printed!r}") from error


def tasks() -> dict[int, Task]:
    document = _decode(_run(["status", "--json"]), "status")
    if not isinstance(document, Mapping):
        raise PueueError("pueue status did not print an object")
    entries = document.get("tasks")
    if not isinstance(entries, Mapping):
        raise PueueError("pueue status published no tasks")
    parsed = (Task.from_entry(entry) for entry in entries.values())
    return {task.task_id: task for task in parsed}


def task(task_id: int) -> Task | None:
    return tasks().get(task_id)


def enqueue(task_id: int) -> None:
    """Release a stashed task into its group's queue."""
    _run(["enqueue", str(task_id)])


def group_add(name: str, parallel: int) -> None:
    """Create a group with that parallelism; an existing group is left as it is."""
    if name in groups():
        return
    _run(["group", "add", "--parallel", str(parallel), name])


def groups() -> dict[str, int]:
    """Every group's configured parallelism: the whole of the admission policy."""
    document = _decode(_run(["group", "--json"]), "group")
    if not isinstance(document, Mapping):
        raise PueueError("pueue group did not print an object")
    return {
        str(name): int(detail.get("parallel_tasks", 0))
        for name, detail in document.items()
        if isinstance(detail, Mapping)
    }


def groups_status() -> dict[str, str]:
    """Each group's run state: `Running` or `Paused`. Pausing is the freeze."""
    document = _decode(_run(["group", "--json"]), "group")
    if not isinstance(document, Mapping):
        raise PueueError("pueue group did not print an object")
    return {
        str(name): str(detail.get("status") or "")
        for name, detail in document.items()
        if isinstance(detail, Mapping)
    }


def log(task_id: int) -> str:
    # Without --full, pueue publishes only a tail of the captured output, so a
    # result parser would read a truncated document as the whole run.
    document = _decode(_run(["log", str(task_id), "--json", "--full"]), "log")
    if not isinstance(document, Mapping):
        raise PueueError("pueue log did not print an object")
    entry = document.get(str(task_id))
    if not isinstance(entry, Mapping):
        raise PueueError(f"pueue log published no entry for task {task_id}")
    return str(entry.get("output") or "")


def wait(task_id: int, *, timeout_seconds: float) -> Task:
    """Block until the task is terminal, then return its final state."""
    _run(["wait", str(task_id)], timeout=timeout_seconds)
    final = task(task_id)
    if final is None:
        raise PueueError(f"pueue forgot task {task_id} while waiting for it")
    return final


def kill(task_id: int) -> None:
    _run(["kill", str(task_id)])


def restart(task_id: int) -> None:
    """Re-run a terminal task in place: pueue's retry, so agentctl keeps none."""
    _run(["restart", "--in-place", str(task_id)])


def remove(task_ids: Sequence[int]) -> None:
    """Forget tasks. Ownership deletion, not a retention window."""
    if not task_ids:
        return
    _run(["remove", *(str(task_id) for task_id in task_ids)])


def pause(group: str) -> None:
    """Close a group's queue while allowing its running tasks to finish."""
    _run(["pause", "--wait", "--group", group])


def resume(group: str) -> None:
    _run(["start", "--group", group])
