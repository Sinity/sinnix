"""Retirement coverage for the removed cross-pool admission policy."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from agentctl import launch
from agentctl.config import Config, PoolPolicy
from agentctl.projects import ProjectAdapter, load_project_adapter
from conftest import FakePueue, read_launch


def heavy_policy(config: Config) -> Config:
    return replace(
        config,
        pools={
            "agent": PoolPolicy(parallel=2),
            "pytest": PoolPolicy(parallel=2),
            "pytest-heavy": PoolPolicy(parallel=1, exclusive_with=("agent",)),
        },
    )


def agent_task(config: Config, project: ProjectAdapter) -> int:
    return launch.enqueue(
        config,
        project=project,
        operation="worker",
        label="fixture:worker",
        group="agent",
        argv=("true",),
        working_directory=project.root,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
    )["job_id"]


def test_new_launches_do_not_stash_or_read_cross_pool_policy(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    job = launch.start_operation(config, project, project.operation("verify"))["job_id"]
    assert fake_pueue.task(job).status == "Running"
    assert "hold" not in launch._launch_input(config, fake_pueue.task(job))


def test_heavy_verification_waits_for_an_agent_wave(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    config = heavy_policy(config)
    fake_pueue.groups["pytest-heavy"] = 1
    worker = agent_task(config, project)
    corpus = replace(project.operation("verify"), pool="pytest-heavy")

    held = launch.start_operation(config, project, corpus)["job_id"]

    task = fake_pueue.task(held)
    assert task.status == "Stashed"
    assert read_launch(config, task)["hold"]["waiting_for"] == [worker]


def test_affected_verification_stays_admissible_beside_agents(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    config = heavy_policy(config)
    agent_task(config, project)

    affected = launch.start_operation(config, project, project.operation("verify"))[
        "job_id"
    ]

    assert fake_pueue.task(affected).group == "pytest"
    assert fake_pueue.task(affected).status == "Running"


def test_heavy_hold_releases_after_the_agent_wave_drains(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    config = heavy_policy(config)
    fake_pueue.groups["pytest-heavy"] = 1
    worker = agent_task(config, project)
    corpus = replace(project.operation("verify"), pool="pytest-heavy")
    held = launch.start_operation(config, project, corpus)["job_id"]
    fake_pueue.kill_directly(worker)

    result = launch.release_holds(config)

    assert [row["task_id"] for row in result["released"]] == [held]
    assert fake_pueue.task(held).status == "Queued"


def test_operator_restash_after_automatic_release_keeps_its_intent(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    config = heavy_policy(config)
    fake_pueue.groups["pytest-heavy"] = 1
    worker = agent_task(config, project)
    corpus = replace(project.operation("verify"), pool="pytest-heavy")
    held = launch.start_operation(config, project, corpus)["job_id"]
    fake_pueue.kill_directly(worker)

    released = launch.release_holds(config)
    task = fake_pueue.task(held)
    assert task is not None and task.status == "Queued"
    assert "hold" not in read_launch(config, task)

    # The operator explicitly stashes the task after AgentCTL has released it.
    fake_pueue._tasks[held] = replace(task, status="Stashed")
    later = launch.release_holds(config)

    assert later["released"] == []
    assert fake_pueue.enqueued == [held]
    assert fake_pueue.task(held).status == "Stashed"
    assert [row["task_id"] for row in released["released"]] == [held]


def test_reordered_hold_follows_launch_reference_and_is_consumed(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """A moved queue id must not leave an old hold that releases an operator restash."""
    project = load_project_adapter(project_root)
    config = heavy_policy(config)
    fake_pueue.groups["pytest-heavy"] = 1
    worker = agent_task(config, project)
    corpus = replace(project.operation("verify"), pool="pytest-heavy")
    held = launch.start_operation(config, project, corpus)["job_id"]
    other = launch.enqueue(
        config,
        project=project,
        operation="verify",
        label="fixture:other",
        group="pytest",
        argv=("true",),
        working_directory=project.root,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
        stashed=True,
    )["job_id"]
    fake_pueue.switch(held, other)
    fake_pueue.kill_directly(worker)

    released = launch.release_holds(config)

    assert [row["task_id"] for row in released["released"]] == [other]
    assert fake_pueue.enqueued == [other]
    moved = fake_pueue.task(other)
    assert moved is not None
    assert read_launch(config, moved)["queue_task_id"] == other
    assert "hold" not in read_launch(config, moved)
    fake_pueue._tasks[other] = replace(moved, status="Stashed")
    assert launch.release_holds(config)["released"] == []
    assert fake_pueue.enqueued == [other]


def test_removed_hold_and_reused_queue_id_do_not_release_another_launch(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """A stale input from a removed queue row cannot authorize its reused id."""
    project = load_project_adapter(project_root)
    config = heavy_policy(config)
    fake_pueue.groups["pytest-heavy"] = 1
    worker = agent_task(config, project)
    corpus = replace(project.operation("verify"), pool="pytest-heavy")
    held = launch.start_operation(config, project, corpus)["job_id"]
    assert fake_pueue.task(held).status == "Stashed"
    fake_pueue._tasks.pop(held)
    replacement = launch.enqueue(
        config,
        project=project,
        operation="verify",
        label="fixture:replacement",
        group="pytest",
        argv=("true",),
        working_directory=project.root,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
        stashed=True,
    )["job_id"]
    fake_pueue._tasks[held] = replace(fake_pueue._tasks.pop(replacement), task_id=held)
    fake_pueue.kill_directly(worker)

    assert launch.release_holds(config)["released"] == []
    assert fake_pueue.enqueued == []
    assert fake_pueue.task(held).status == "Stashed"


def test_enqueue_acknowledgement_and_hold_release_share_admission_lock(
    fake_pueue: FakePueue, config: Config, project_root: Path, monkeypatch
) -> None:
    """Release cannot consume an incomplete input then have its hold restored."""
    project = load_project_adapter(project_root)
    config = heavy_policy(config)
    fake_pueue.groups["pytest-heavy"] = 1
    worker = agent_task(config, project)
    corpus = replace(project.operation("verify"), pool="pytest-heavy")
    original_add = fake_pueue.add

    def add_after_partner_drains(**kwargs):
        task_id = original_add(**kwargs)
        fake_pueue.kill_directly(worker)
        return task_id

    monkeypatch.setattr(launch.pueue, "add", add_after_partner_drains)
    original_lock = launch.admission_lock
    release_results = []
    interleaved = False

    @contextmanager
    def release_on_unlock(cfg):
        nonlocal interleaved
        with original_lock(cfg):
            yield
        if not interleaved:
            interleaved = True
            release_results.append(launch.release_holds(cfg))

    monkeypatch.setattr(launch, "admission_lock", release_on_unlock)
    held = launch.start_operation(config, project, corpus)["job_id"]
    assert [row["task_id"] for row in release_results[0]["released"]] == [held]
    assert fake_pueue.enqueued == [held]
    task = fake_pueue.task(held)
    assert task is not None and "hold" not in read_launch(config, task)
    fake_pueue._tasks[held] = replace(task, status="Stashed")
    assert launch.release_holds(config)["released"] == []
    assert fake_pueue.enqueued == [held]


def test_retry_respects_active_exclusive_partner(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """A terminal heavy task cannot resume beside an active agent on retry."""
    project = load_project_adapter(project_root)
    config = heavy_policy(config)
    fake_pueue.groups["pytest-heavy"] = 1
    corpus = replace(project.operation("verify"), pool="pytest-heavy")
    started = launch.start_operation(config, project, corpus)
    fake_pueue.fail(started["job_id"], exit_code=1)
    worker = agent_task(config, project)

    retried = launch.retry(config, started["job_id"], started["reference"])

    assert retried["phase"] == "stashed"
    task = fake_pueue.task(started["job_id"])
    assert task is not None and task.status == "Stashed"
    assert read_launch(config, task)["hold"]["waiting_for"] == [worker]
    fake_pueue.kill_directly(worker)
    assert [row["task_id"] for row in launch.release_holds(config)["released"]] == [
        task.task_id
    ]
    assert fake_pueue.task(task.task_id).status == "Queued"
