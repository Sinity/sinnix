"""Shared fakes: an in-memory pueue and a Beads reader over fixture beads.

Tests drive job execution by mutating task state directly instead of
shelling out to a real pueued. The `live_pueue` fixture is the exception:
contracts that only a real daemon can settle run against a private one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pytest
from agentctl import launch as launch_module
from agentctl import pueue as pueue_module
from agentctl.config import Config
from agentctl.prompts import PromptError
from agentctl.pueue import PueueError, PueueGroupError, PueueTimeout, Task


@dataclass
class FakePueue:
    """An in-memory pueue daemon: enough surface for the launch route."""

    next_id: int = 1
    _tasks: dict[int, Task] = field(default_factory=dict)
    added: list[dict[str, Any]] = field(default_factory=list)
    killed: list[int] = field(default_factory=list)
    restarted: list[int] = field(default_factory=list)
    removed: list[int] = field(default_factory=list)
    resized: list[tuple[str, int, int]] = field(default_factory=list)
    waited: list[int] = field(default_factory=list)
    enqueued: list[int] = field(default_factory=list)
    _logs: dict[int, str] = field(default_factory=dict)
    _on_wait: dict[int, Callable[["FakePueue"], None]] = field(default_factory=dict)
    groups: dict[str, int] = field(
        # The groups the deployed pueued creates. A pool outside this set is
        # a configuration defect and the launch must refuse, exactly as it
        # does on the machine.
        default_factory=lambda: {
            "default": 1,
            "agent": 6,
            "interactive": 1,
            "normal": 1,
            "pytest": 1,
            "bulk": 1,
        }
    )
    paused: set[str] = field(default_factory=set)
    fail_add: bool = False
    fail_tasks: bool = False
    # Seconds a `wait` that never saw its task finish has consumed.
    clock: float = 0.0

    def add(
        self,
        *,
        group: str,
        label: str,
        command: Sequence[str],
        working_directory: Path,
        after: Sequence[int] = (),
        stashed: bool = False,
        priority: int = 0,
    ) -> int:
        if self.fail_add:
            raise PueueError("fixture pueue add failed")
        if group not in self.groups:
            raise PueueGroupError(group)
        task_id = self.next_id
        self.next_id += 1
        # An idle group starts a task with no dependencies at once; one queued
        # behind others waits for them, and a stashed one waits to be enqueued.
        status = "Stashed" if stashed else "Queued" if after else "Running"
        self._tasks[task_id] = Task(
            task_id=task_id,
            label=label,
            group=group,
            status=status,
            result=None,
            exit_code=None,
            path=str(working_directory),
            dependencies=tuple(after),
            command=" ".join(command),
            enqueued_at="2026-09-03T08:00:00+00:00",
            started_at="2026-09-03T08:00:01+00:00" if status == "Running" else None,
        )
        self.added.append(
            {
                "task_id": task_id,
                "group": group,
                "label": label,
                "priority": priority,
                "command": tuple(command),
                "working_directory": working_directory,
                "after": tuple(after),
                "stashed": stashed,
            }
        )
        return task_id

    def enqueue(self, task_id: int) -> None:
        task = self._tasks[task_id]
        if task.status == "Stashed":
            self._tasks[task_id] = replace(task, status="Queued")
        self.enqueued.append(task_id)

    def group_add(self, name: str, parallel: int) -> None:
        self.groups.setdefault(name, parallel)

    def set_parallel(self, group: str, parallel: int) -> None:
        self.resized.append((group, self.groups[group], parallel))
        self.groups[group] = parallel

    def tasks(self) -> dict[int, Task]:
        if self.fail_tasks:
            raise PueueError("fixture pueue status failed")
        return dict(self._tasks)

    def task(self, task_id: int) -> Task | None:
        return self._tasks.get(task_id)

    def kill(self, task_id: int) -> None:
        task = self._tasks.get(task_id)
        # pueued kills a process; asked to kill a task that has none it fails
        # the request and leaves the task queued, to run later.
        if task is not None and task.started_at is None:
            raise PueueError(f"The command failed for tasks: {task_id}")
        self.killed.append(task_id)
        if task is not None and not task.terminal:
            self._tasks[task_id] = replace(
                task, status="Done", result="Killed", exit_code=None
            )

    def restart(self, task_id: int) -> None:
        self.restarted.append(task_id)
        task = self._tasks[task_id]
        self._tasks[task_id] = replace(
            task, status="Queued", result=None, exit_code=None
        )

    def remove(self, task_ids: Sequence[int]) -> None:
        for task_id in task_ids:
            self._tasks.pop(task_id, None)
        self.removed.extend(task_ids)

    def wait(self, task_id: int, *, timeout_seconds: float) -> Task:
        """The registered transition runs, else the whole timeout elapses.

        A caller slices its wait, so a task left unfinished here is waited
        for again: a test whose task never finishes keeps it `Running`, where
        one slice covers the whole deadline.
        """
        self.waited.append(task_id)
        transition = self._on_wait.pop(task_id, None)
        if transition is not None:
            transition(self)
        task = self._tasks.get(task_id)
        if task is None or not task.terminal:
            self.clock += timeout_seconds
            raise PueueTimeout(f"fixture task {task_id} did not finish in time")
        return task

    def switch(self, first: int, second: int) -> None:
        """`pueue switch`: two queued tasks exchange their ids, as 4.0.4 does.

        The daemon refuses any other state, so a test cannot move a task the
        real queue would have left where it was.
        """
        one, other = self._tasks[first], self._tasks[second]
        if not {one.status, other.status} <= {"Queued", "Stashed"}:
            raise PueueError("Tasks have to be either queued or stashed.")
        self._tasks[first] = replace(other, task_id=first)
        self._tasks[second] = replace(one, task_id=second)

    def finish_when_waited(
        self, task_id: int, transition: Callable[["FakePueue"], None]
    ) -> None:
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
        self._set(task_id, status="Queued", started_at=None)

    def succeed(self, task_id: int, *, exit_code: int = 0) -> None:
        self._set(
            task_id,
            status="Done",
            result="Success",
            exit_code=exit_code,
            ended_at="2026-09-03T08:10:00+00:00",
        )

    def fail(self, task_id: int, *, exit_code: int) -> None:
        self._set(
            task_id,
            status="Done",
            result="Failed",
            exit_code=exit_code,
            ended_at="2026-09-03T08:10:00+00:00",
        )

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
def live_pueue(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A private pueued: the adapter's parsing proven against the real daemon.

    The runtime directory is overridden so this daemon never touches the
    operator's socket or pid file, and it lives under the shortest available
    temporary root because a Unix socket path over SUN_LEN cannot be bound.
    """
    root = Path(tempfile.mkdtemp(prefix="pq", dir=tempfile.gettempdir()))
    home = root / "h"
    (home / ".config" / "pueue").mkdir(parents=True)
    (home / ".config" / "pueue" / "pueue.yml").write_text(
        "shared:\n"
        f"  pueue_directory: {root / 'd'}\n"
        f"  runtime_directory: {root / 'r'}\n"
        "  use_unix_socket: true\n"
        "daemon:\n"
        "  default_parallel_tasks: 2\n"
    )
    (root / "d").mkdir()
    (root / "r").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    environment = {"HOME": str(home), "PATH": os.environ["PATH"]}
    # Every call below must reach this daemon and no other. A config or runtime
    # directory inherited from the invoking user resolves to the operator's
    # live socket, where `shutdown` stops the machine's real queue.
    resolved = subprocess.run(
        ["pueue", "status", "--json"], env=environment, capture_output=True, text=True
    )
    assert resolved.returncode != 0, (
        "a daemon answered before this fixture started one: the environment "
        "still points at someone else's pueued"
    )
    # pueued daemonises but its child inherits the parent's stdio; capturing
    # into a pipe would block until that child exits, which is never.
    with open(root / "daemon.log", "w") as daemon_log:
        subprocess.run(
            ["pueued", "-d"],
            env=environment,
            check=True,
            stdout=daemon_log,
            stderr=subprocess.STDOUT,
        )
    deadline = time.monotonic() + 30
    while True:
        probe = subprocess.run(
            ["pueue", "status", "--json"], env=environment, capture_output=True
        )
        if probe.returncode == 0:
            break
        if time.monotonic() > deadline:
            raise AssertionError(f"pueued did not start: {probe.stderr!r}")
        time.sleep(0.1)
    try:
        yield str(home)
    finally:
        subprocess.run(
            ["pueue", "shutdown"], env=environment, capture_output=True, timeout=30
        )
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def fake_pueue(monkeypatch: pytest.MonkeyPatch) -> FakePueue:
    fake = FakePueue()
    for name in (
        "add",
        "tasks",
        "task",
        "kill",
        "restart",
        "remove",
        "wait",
        "groups_status",
        "enqueue",
        "group_add",
        "set_parallel",
        "pause",
        "resume",
        "log",
    ):
        monkeypatch.setattr(pueue_module, name, getattr(fake, name))
    monkeypatch.setattr(pueue_module, "groups", lambda: dict(fake.groups))
    return fake


@pytest.fixture(autouse=True)
def _no_cancel_settle_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fake task never exits on its own; tests of the wait pass their own."""
    monkeypatch.setattr(launch_module, "CANCEL_SETTLE_SECONDS", 0.0)


@pytest.fixture(autouse=True)
def _no_inherited_queue_group(monkeypatch: pytest.MonkeyPatch) -> None:
    """The suite must not inherit the group of a pueue task that runs it.

    `PUEUE_GROUP` is what the wrapper containerises by, so a suite run from
    inside a queued task would otherwise scope every fixture launch for real.
    """
    monkeypatch.delenv("PUEUE_GROUP", raising=False)


@pytest.fixture
def recording_systemctl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[], list[list[str]]]:
    """A systemctl on PATH recording its argv; returns a reader for the calls.

    The reap's real argv is the contract, so this replaces the executable rather
    than the function that runs it.
    """
    directory = tmp_path / "systemctl-bin"
    directory.mkdir(exist_ok=True)
    ledger = directory / "calls"
    script = directory / "systemctl"
    # systemd refuses to stop a unit that was never created; a fake that
    # reported success would hide a reap that reached nothing.
    script.write_text(
        f'#!/bin/sh\nprintf "systemctl %s\\n" "$*" >> {ledger}\n'
        'case "$*" in *stop*) exit 1 ;; *is-active*) exit 3 ;; esac\n'
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")

    def calls() -> list[list[str]]:
        if not ledger.exists():
            return []
        return [line.split() for line in ledger.read_text().splitlines()]

    return calls


@dataclass
class FakeBd:
    """A Beads reader over fixture beads; records every close."""

    beads: dict[str, dict[str, Any]] = field(default_factory=dict)
    closed: list[tuple[str, str]] = field(default_factory=list)

    def show(self, bead_id: str) -> Mapping[str, Any]:
        try:
            return dict(self.beads[bead_id])
        except KeyError as error:
            raise PromptError(f"bd show {bead_id} returned an invalid bead") from error

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
agent_memory_max = "10G"
verify = {{ focused = "verify_quick", candidate = "check", corpus = "verify" }}
publish = "master"

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

[operations.verify_quick]
description = "Fixture quick verification"
exec = ["fixture-verify-quick"]
pool = "pytest"
result = "exit"
timeout_seconds = 120

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
    (root / "contract.md").write_text(
        "# Worker contract\n\nCommit by path, push, never merge.\n"
    )
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
        worker_contract=project_root / "contract.md",
        event_spool=tmp_path / "events.jsonl",
        state_dir=tmp_path / "state",
        agentctl_executable="/fixture/agentctl",
    )


def read_launch(config: Config, task: Task) -> dict[str, Any]:
    """The launch input a fake task's command names."""
    _, _, path = task.command.partition(" ")
    return json.loads(Path(path).read_text())
