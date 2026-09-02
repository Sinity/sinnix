"""The pueue adapter: the queue, its groups, and one task's observable state.

Sinnixd does not queue, admit, throttle, retry, or reap. pueued does, and its
own state is the record. This module is the only place that shells out to it.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class Task:
    """One entry of ``pueue status --json``, reduced to what sinnixd reads."""

    task_id: int
    label: str
    group: str
    status: str
    result: str | None
    exit_code: int | None
    path: str
    dependencies: tuple[int, ...]

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
        )


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
) -> int:
    """Enqueue one command and return the task id pueue assigned it."""
    if not command:
        raise PueueError("pueue add requires a command")
    arguments = [
        "add",
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
    arguments.append("--")
    arguments.extend(command)
    printed = _run(arguments).strip()
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


def log(task_id: int) -> str:
    document = _decode(_run(["log", str(task_id), "--json"]), "log")
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
    """Re-run a terminal task in place: pueue's retry, so sinnixd keeps none."""
    _run(["restart", "--in-place", str(task_id)])


def remove(task_ids: Sequence[int]) -> None:
    """Forget tasks. Ownership deletion, not a retention window."""
    if not task_ids:
        return
    _run(["remove", *(str(task_id) for task_id in task_ids)])


def pause(group: str) -> None:
    """Freeze a group: SIGSTOP to its running tasks, rather than thrashing."""
    _run(["pause", "--group", group])


def resume(group: str) -> None:
    _run(["start", "--group", group])
