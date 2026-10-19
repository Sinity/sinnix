"""Queue state and cheap job addressing.

The live test drives a private pueued; the fake test proves a job read never
loads the queue's whole history.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from agentctl import launch, pueue
from agentctl.config import Config
from conftest import FakePueue

GROUP = "group"


def _until(task_id: int, status: str, *, seconds: float = 20.0) -> pueue.Task:
    deadline = time.monotonic() + seconds
    while True:
        task = pueue.task(task_id)
        if task is not None and task.status == status:
            return task
        if time.monotonic() > deadline:
            raise AssertionError(f"task {task_id} never reached {status}: {task}")
        time.sleep(0.05)


def test_queue_state_names_what_holds_each_slot_and_who_waits(
    live_pueue: str, config: Config, tmp_path: Path
) -> None:
    pueue.group_add(GROUP, 1)
    long = pueue.add(
        group=GROUP,
        label="fixture:shell",
        command=("sleep", "60"),
        working_directory=tmp_path,
    )
    _until(long, "Running")
    first = pueue.add(
        group=GROUP,
        label="fixture:shell",
        command=("true",),
        working_directory=tmp_path,
    )
    second = pueue.add(
        group=GROUP,
        label="fixture:shell",
        command=("true",),
        working_directory=tmp_path,
    )

    state = launch.queue_state(config, [GROUP])[GROUP]
    assert (state["parallel"], state["status"]) == (1, "Running")
    assert [entry["task_id"] for entry in state["running"]] == [long]
    assert [entry["task_id"] for entry in state["queued"]] == [first, second]
    assert state["queued_count"] == 2
    assert state["oldest_queued_seconds"] is not None

    position = launch.job_queue(config, launch.job_view(pueue.task(second)))
    assert position["position"] == 2 and position["ahead"] == [first]
    assert [entry["task_id"] for entry in position["occupied_by"]] == [long]
    running = launch.job_queue(config, launch.job_view(pueue.task(long)))
    assert running["position"] is None and running["occupied_by"] == []

    missing = launch.queue_state(config, ["absent"])["absent"]
    assert missing["known"] is False and missing["running"] == []
    pueue.kill(long)
    pueue.remove([first, second])


def test_a_job_read_by_job_id_never_loads_the_queue_history(
    fake_pueue: FakePueue, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: the full status read raises here, so a lookup that fell
    back to it would fail instead of answering."""
    inputs = tmp_path / "inputs"
    fake_pueue.groups[GROUP] = 1
    first = fake_pueue.add(
        group=GROUP,
        label="fixture:shell",
        command=("agentctl-run", str(inputs / "fixture-shell-aaaa1111.json")),
        working_directory=tmp_path,
    )
    moved = fake_pueue.add(
        group=GROUP,
        label="fixture:shell",
        command=("agentctl-run", str(inputs / "fixture-shell-bbbb2222.json")),
        working_directory=tmp_path,
    )
    snapshot = dict(fake_pueue._tasks)

    def history() -> dict[int, pueue.Task]:
        raise AssertionError("a job read loaded the whole queue history")

    monkeypatch.setattr(pueue, "tasks", history)
    monkeypatch.setattr(
        pueue,
        "tasks_by_command",
        lambda fragment: {
            key: task for key, task in snapshot.items() if fragment in task.command
        },
    )

    assert launch.locate(first, "fixture-shell-aaaa1111").task_id == first
    # The id now names another job: the job_id finds its own.
    assert launch.locate(first, "fixture-shell-bbbb2222").task_id == moved
    assert launch.locate(first, "fixture-shell-cccc3333") is None
