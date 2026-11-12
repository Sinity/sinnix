"""Queue state and cheap job addressing.

The live test drives a private pueued; the fake test proves a job read never
loads the queue's whole history.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

import pytest
from agentctl import job_queries, pueue
from agentctl.config import Config, PoolPolicy
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

    state = job_queries.queue_state(config, [GROUP])[GROUP]
    assert (state["parallel"], state["status"]) == (1, "Running")
    assert [entry["task_id"] for entry in state["running"]] == [long]
    assert [entry["task_id"] for entry in state["queued"]] == [first, second]
    assert state["queued_count"] == 2
    assert state["oldest_queued_seconds"] is not None

    position = job_queries.job_queue(config, job_queries.job_view(pueue.task(second)))
    assert position["position"] == 2 and position["ahead"] == [first]
    assert [entry["task_id"] for entry in position["occupied_by"]] == [long]
    running = job_queries.job_queue(config, job_queries.job_view(pueue.task(long)))
    assert running["position"] is None and running["occupied_by"] == []

    missing = job_queries.queue_state(config, ["absent"])["absent"]
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

    assert job_queries.locate(first, "fixture-shell-aaaa1111").task_id == first
    # The id now names another job: the job_id finds its own.
    assert job_queries.locate(first, "fixture-shell-bbbb2222").task_id == moved
    assert job_queries.locate(first, "fixture-shell-cccc3333") is None


def _native_job(
    fake,
    config,
    tmp_path,
    name,
    *,
    status="Queued",
    group="normal",
    priority=0,
    dependencies=(),
):
    config.inputs_dir.mkdir(parents=True, exist_ok=True)
    identity = "fixture-" + name
    path = config.inputs_dir / (identity + ".json")
    path.write_text(
        json.dumps(
            {
                "job_id": identity,
                "project_root": str(tmp_path / name),
                "working_directory": str(tmp_path / name),
                "pool": group,
            }
        )
    )
    task_id = fake.add(
        group=group,
        label=name + ":check",
        command=("agentctl-run", str(path)),
        working_directory=tmp_path / name,
        priority=priority,
    )
    fake._tasks[task_id] = replace(
        fake.task(task_id), status=status, dependencies=dependencies
    )
    return fake.task(task_id)


def test_queue_uses_native_priority_and_names_current_cross_project_holder(
    fake_pueue, config, tmp_path
):
    ended = _native_job(fake_pueue, config, tmp_path, "ended", status="Running")
    fake_pueue.succeed(ended.task_id)
    holder = _native_job(
        fake_pueue, config, tmp_path, "other-project", status="Running"
    )
    early = _native_job(fake_pueue, config, tmp_path, "earlier")
    urgent = _native_job(fake_pueue, config, tmp_path, "urgent", priority=50)
    answer = job_queries.job_queue(config, job_queries.job_view(early))
    assert answer["position"] == 2 and answer["ahead"] == [urgent.task_id]
    assert answer["reason"] == "pool-full"
    assert [r["task_id"] for r in answer["occupied_by"]] == [holder.task_id]
    assert [
        (r["job_id"], r["project"], r["working_directory"])
        for r in answer["occupied_by"]
    ] == [("fixture-other-project", "other-project", str(tmp_path / "other-project"))]
    assert [r["priority"] for r in answer["queued"]] == [50, 0]
    assert ended.task_id not in [r["task_id"] for r in answer["running"]]
    assert job_queries.job_queue(config, job_queries.job_view(urgent))["ahead"] == []


def test_queue_distinguishes_dependencies_pause_and_available_slots(
    fake_pueue, config, tmp_path
):
    dependency = _native_job(
        fake_pueue, config, tmp_path, "dependency", group="bulk", status="Running"
    )
    blocked = _native_job(
        fake_pueue,
        config,
        tmp_path,
        "blocked",
        priority=100,
        dependencies=(dependency.task_id,),
    )
    ready = _native_job(fake_pueue, config, tmp_path, "ready")
    answer = job_queries.job_queue(config, job_queries.job_view(blocked))
    assert answer["reason"] == "dependencies" and answer["waiting_for"] == [
        dependency.task_id
    ]
    answer = job_queries.job_queue(config, job_queries.job_view(ready))
    assert answer["reason"] == "ready" and answer["ahead"] == []
    fake_pueue.paused.add("normal")
    assert (
        job_queries.job_queue(config, job_queries.job_view(ready))["reason"]
        == "group-paused"
    )
    fake_pueue.paused.clear()
    fake_pueue._tasks[ready.task_id] = replace(ready, status="Paused")
    next_job = _native_job(fake_pueue, config, tmp_path, "next")
    answer = job_queries.job_queue(config, job_queries.job_view(next_job))
    assert answer["reason"] == "pool-full"
    assert answer["occupied_by"][0]["phase"] == "paused"
    fake_pueue.groups["normal"] = 0
    assert (
        job_queries.job_queue(config, job_queries.job_view(next_job))["reason"]
        == "ready"
    )


def test_admission_inspection_recomputes_blockers_instead_of_retained_ids(
    fake_pueue, config, tmp_path
):
    config = replace(
        config,
        pools={
            "normal": PoolPolicy(1, exclusive_with=("bulk",)),
            "bulk": PoolPolicy(1),
        },
    )
    old = _native_job(
        fake_pueue, config, tmp_path, "old", status="Running", group="bulk"
    )
    fake_pueue.succeed(old.task_id)
    current = _native_job(
        fake_pueue, config, tmp_path, "current", status="Running", group="bulk"
    )
    held = _native_job(fake_pueue, config, tmp_path, "held", status="Stashed")
    path = config.inputs_dir / "fixture-held.json"
    data = json.loads(path.read_text())
    data["hold"] = {
        "reason": "pool-exclusivity",
        "pool": "normal",
        "waiting_for": [old.task_id],
    }
    path.write_text(json.dumps(data))
    answer = job_queries.job_queue(config, job_queries.job_view(held))
    assert answer["reason"] == "pool-exclusivity"
    assert answer["waiting_for"] == [current.task_id]
    assert answer["occupied_by"][0]["job_id"] == "fixture-current"
    fake_pueue.succeed(current.task_id)
    answer = job_queries.job_queue(config, job_queries.job_view(held))
    assert answer["reason"] == "admission-release"
    assert answer["waiting_for"] == [] and answer["occupied_by"] == []
    data.pop("hold")
    path.write_text(json.dumps(data))
    assert (
        job_queries.job_queue(config, job_queries.job_view(held))["reason"] == "stashed"
    )


def test_inspection_follows_stable_job_and_never_names_a_reused_id_as_its_blocker(
    fake_pueue, config, tmp_path
):
    first = _native_job(fake_pueue, config, tmp_path, "first")
    second = _native_job(fake_pueue, config, tmp_path, "second", priority=50)
    old = job_queries.job_view(first)
    fake_pueue._tasks[first.task_id] = replace(second, task_id=first.task_id)
    fake_pueue._tasks[second.task_id] = replace(first, task_id=second.task_id)
    answer = job_queries.job_queue(config, old)
    assert answer["position"] == 2
    assert answer["ahead"] == [first.task_id]
    fake_pueue.succeed(second.task_id)
    answer = job_queries.job_queue(config, old)
    assert answer["reason"] == "not-in-live-queue"
    assert answer["occupied_by"] == [] and answer["position"] is None
