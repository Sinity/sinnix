"""Shared fakes: an in-memory pueue and a Beads reader over fixture beads.

Tests drive job execution by mutating task state directly instead of
shelling out to a real pueued.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pytest
from sinnixd import pueue as pueue_module
from sinnixd.config import Config
from sinnixd.packets import PacketError
from sinnixd.pueue import PueueError, PueueGroupError, Task


@dataclass
class FakePueue:
    """An in-memory pueue daemon: enough surface for the launch route."""

    next_id: int = 1
    _tasks: dict[int, Task] = field(default_factory=dict)
    added: list[dict[str, Any]] = field(default_factory=list)
    killed: list[int] = field(default_factory=list)
    restarted: list[int] = field(default_factory=list)
    removed: list[int] = field(default_factory=list)
    waited: list[int] = field(default_factory=list)
    _logs: dict[int, str] = field(default_factory=dict)
    _on_wait: dict[int, Callable[["FakePueue"], None]] = field(default_factory=dict)
    groups: dict[str, int] = field(
        # The groups the deployed pueued creates. A pool outside this set is
        # a configuration defect and the launch must refuse, exactly as it
        # does on the machine.
        default_factory=lambda: {
            "default": 1,
            "agent": 4,
            "interactive": 1,
            "normal": 1,
            "pytest": 1,
            "bulk": 1,
        }
    )
    paused: set[str] = field(default_factory=set)
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
        if group not in self.groups:
            raise PueueGroupError(group)
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
            command=" ".join(command),
            enqueued_at="2026-09-03T08:00:00+00:00",
            started_at="2026-09-03T08:00:01+00:00",
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
            self._tasks[task_id] = replace(task, status="Done", result="Killed", exit_code=None)

    def restart(self, task_id: int) -> None:
        self.restarted.append(task_id)
        task = self._tasks[task_id]
        self._tasks[task_id] = replace(task, status="Queued", result=None, exit_code=None)

    def remove(self, task_ids: Sequence[int]) -> None:
        for task_id in task_ids:
            self._tasks.pop(task_id, None)
        self.removed.extend(task_ids)

    def wait(self, task_id: int, *, timeout_seconds: float) -> Task:
        self.waited.append(task_id)
        transition = self._on_wait.pop(task_id, None)
        if transition is not None:
            transition(self)
        task = self._tasks.get(task_id)
        if task is None or not task.terminal:
            raise PueueError(f"fixture task {task_id} never reached a terminal state")
        return task

    def finish_when_waited(self, task_id: int, transition: Callable[["FakePueue"], None]) -> None:
        self._on_wait[task_id] = transition

    def groups_status(self) -> dict[str, str]:
        return {
            name: "Paused" if name in self.paused else "Running" for name in self.groups
        }

    def pause(self, group: str) -> None:
        self.paused.add(group)

    def resume(self, group: str) -> None:
        self.paused.discard(group)

    def running(self, task_id: int) -> None:
        self._set(task_id, status="Running")

    def queue(self, task_id: int) -> None:
        self._set(task_id, status="Queued")

    def succeed(self, task_id: int, *, exit_code: int = 0) -> None:
        self._set(task_id, status="Done", result="Success", exit_code=exit_code,
                  ended_at="2026-09-03T08:10:00+00:00")

    def fail(self, task_id: int, *, exit_code: int) -> None:
        self._set(task_id, status="Done", result="Failed", exit_code=exit_code,
                  ended_at="2026-09-03T08:10:00+00:00")

    def dependency_fail(self, task_id: int) -> None:
        self._set(task_id, status="Done", result="DependencyFailed")

    def fail_to_spawn(self, task_id: int) -> None:
        self._set(task_id, status="Done", result="FailedToSpawn")

    def kill_directly(self, task_id: int) -> None:
        self._set(task_id, status="Done", result="Killed")

    def set_log(self, task_id: int, output: str) -> None:
        self._logs[task_id] = output

    def log(self, task_id: int) -> str:
        return self._logs.get(task_id, "")

    def _set(self, task_id: int, **fields: Any) -> None:
        self._tasks[task_id] = replace(self._tasks[task_id], **fields)


@pytest.fixture
def fake_pueue(monkeypatch: pytest.MonkeyPatch) -> FakePueue:
    fake = FakePueue()
    for name in (
        "add", "tasks", "task", "kill", "restart", "remove", "wait",
        "groups_status", "pause", "resume", "log",
    ):
        monkeypatch.setattr(pueue_module, name, getattr(fake, name))
    monkeypatch.setattr(pueue_module, "groups", lambda: dict(fake.groups))
    return fake


@dataclass
class FakeBd:
    """A Beads reader over fixture beads; records every close."""

    beads: dict[str, dict[str, Any]] = field(default_factory=dict)
    closed: list[tuple[str, str]] = field(default_factory=list)

    def show(self, bead_id: str) -> Mapping[str, Any]:
        try:
            return dict(self.beads[bead_id])
        except KeyError as error:
            raise PacketError(f"bd show {bead_id} returned an invalid bead") from error

    def list(self) -> Sequence[Mapping[str, Any]]:
        return [dict(bead) for bead in self.beads.values()]

    def ready(self) -> Sequence[Mapping[str, Any]]:
        return [
            dict(bead)
            for bead in self.beads.values()
            if bead.get("status") == "open" and not bead.get("blocked")
        ]


def bead(
    bead_id: str,
    title: str,
    *,
    issue_type: str = "task",
    status: str = "open",
    description: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": bead_id,
        "title": title,
        "issue_type": issue_type,
        "status": status,
        "description": description,
        "metadata": dict(metadata or {}),
    }


DESCRIPTOR = """schema = 1

[project]
id = "fixture"
display_name = "Fixture"
root_markers = ["marker"]

[environment]
kind = "plain"
command = ["env"]
inherit = ["PATH"]

[workspace]
root = "{worktrees}"
default_base = "origin/master"

[packets]
template = "contract.md"
atlas_dir = "atlas"

[packets.defaults]
backend = "codex"
model = "fixture-model"
effort = "low"

[operations.check]
description = "Fixture check"
exec = ["true"]
pool = "normal"
result = "exit"

[operations.verify]
description = "Fixture typed verification"
exec = ["fixture-verify"]
pool = "pytest"
result = "json"
timeout_seconds = 120

[operations.nightly]
description = "Fixture nightly corpus"
exec = ["fixture-nightly"]
pool = "bulk"
checkout = "default"
schedule = "*-*-* 03:17:00"
"""


def write_project(root: Path, *, worktrees: Path | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "marker").write_text("")
    (root / ".agentctl").mkdir(exist_ok=True)
    (root / ".agentctl" / "project.toml").write_text(
        DESCRIPTOR.format(worktrees=worktrees or root.parent / "worktrees")
    )
    (root / "contract.md").write_text("# Worker contract\n\nCommit by path, push, never merge.\n")
    (root / "atlas").mkdir(exist_ok=True)
    (root / "atlas" / "core.md").write_text("# core\n")
    return root


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return write_project(tmp_path / "fixture")


@pytest.fixture
def config(tmp_path: Path, project_root: Path) -> Config:
    runner = tmp_path / "runner.sh"
    runner.write_text("#!/bin/sh\nexit 0\n")
    runner.chmod(0o755)
    return Config(
        project_roots=(project_root,),
        agent_runner=runner,
        event_spool=tmp_path / "events.jsonl",
        state_dir=tmp_path / "state",
        agentctl_executable="/fixture/agentctl",
    )


def read_launch(config: Config, task: Task) -> dict[str, Any]:
    """The launch input a fake task's command names."""
    _, _, path = task.command.partition(" ")
    return json.loads(Path(path).read_text())
