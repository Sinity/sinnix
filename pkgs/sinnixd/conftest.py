"""Shared pueue fake: tests drive job execution by mutating task state directly
instead of shelling out to a real pueued.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Sequence

import pytest
from sinnixd import pueue as pueue_module
from sinnixd.pueue import PueueError, Task


@dataclass
class FakePueue:
    """An in-memory pueue daemon: enough surface for GenericJobs' launch route."""

    next_id: int = 1
    _tasks: dict[int, Task] = field(default_factory=dict)
    added: list[dict[str, Any]] = field(default_factory=list)
    killed: list[int] = field(default_factory=list)
    removed: list[int] = field(default_factory=list)
    groups: dict[str, int] = field(
        default_factory=lambda: {
            "default": 1,
            "agent": 1,
            "interactive": 1,
            "normal": 1,
        }
    )
    fail_add: bool = False
    fail_tasks: bool = False

    def add(
        self,
        *,
        group: str,
        label: str,
        command: Sequence[str],
        working_directory: Path,
        after: Sequence[int] = (),
    ) -> int:
        if self.fail_add:
            raise PueueError("fixture pueue add failed")
        task_id = self.next_id
        self.next_id += 1
        self._tasks[task_id] = Task(
            task_id=task_id,
            label=label,
            group=group,
            # A fixture task is immediately running by default, matching an
            # idle group's real behavior; tests that need the queued window
            # itself call .queue(task_id) explicitly.
            status="Running",
            result=None,
            exit_code=None,
            path=str(working_directory),
            dependencies=tuple(after),
        )
        self.added.append(
            {
                "task_id": task_id,
                "group": group,
                "label": label,
                "command": tuple(command),
                "working_directory": working_directory,
                "after": tuple(after),
            }
        )
        return task_id

    def tasks(self) -> dict[int, Task]:
        if self.fail_tasks:
            raise PueueError("fixture pueue status failed")
        return dict(self._tasks)

    def task(self, task_id: int) -> Task | None:
        return self._tasks.get(task_id)

    def kill(self, task_id: int) -> None:
        self.killed.append(task_id)
        task = self._tasks.get(task_id)
        if task is not None and not task.terminal:
            self._tasks[task_id] = replace(
                task, status="Done", result="Killed", exit_code=None
            )

    def restart(self, task_id: int) -> None:
        task = self._tasks[task_id]
        self._tasks[task_id] = replace(
            task, status="Queued", result=None, exit_code=None
        )

    def remove(self, task_ids: Sequence[int]) -> None:
        for task_id in task_ids:
            self._tasks.pop(task_id, None)
        self.removed.extend(task_ids)

    def wait(self, task_id: int, *, timeout_seconds: float) -> Task:
        task = self._tasks.get(task_id)
        if task is None or not task.terminal:
            raise PueueError(f"fixture task {task_id} never reached a terminal state")
        return task

    def set_group(self, group: str, parallel_tasks: int) -> None:
        self.groups[group] = parallel_tasks

    def running(self, task_id: int) -> None:
        self._set(task_id, status="Running")

    def queue(self, task_id: int) -> None:
        self._set(task_id, status="Queued")

    def succeed(self, task_id: int, *, exit_code: int = 0) -> None:
        self._set(task_id, status="Done", result="Success", exit_code=exit_code)

    def fail(self, task_id: int, *, exit_code: int) -> None:
        self._set(task_id, status="Done", result="Failed", exit_code=exit_code)

    def dependency_fail(self, task_id: int) -> None:
        self._set(task_id, status="Done", result="DependencyFailed")

    def fail_to_spawn(self, task_id: int) -> None:
        self._set(task_id, status="Done", result="FailedToSpawn")

    def kill_directly(self, task_id: int) -> None:
        self._set(task_id, status="Done", result="Killed")

    def _set(self, task_id: int, **fields: Any) -> None:
        self._tasks[task_id] = replace(self._tasks[task_id], **fields)


@pytest.fixture
def fake_pueue(monkeypatch: pytest.MonkeyPatch) -> FakePueue:
    fake = FakePueue()
    monkeypatch.setattr(pueue_module, "add", fake.add)
    monkeypatch.setattr(pueue_module, "tasks", fake.tasks)
    monkeypatch.setattr(pueue_module, "task", fake.task)
    monkeypatch.setattr(pueue_module, "kill", fake.kill)
    monkeypatch.setattr(pueue_module, "restart", fake.restart)
    monkeypatch.setattr(pueue_module, "remove", fake.remove)
    monkeypatch.setattr(pueue_module, "wait", fake.wait)
    monkeypatch.setattr(pueue_module, "groups", lambda: dict(fake.groups))
    return fake
