"""Memory admission: held jobs start across pools only when the plane holds them."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pytest
from agentctl import admission, job_queries, launch
from agentctl import run as run_module
from agentctl.config import Config, ConfigError, PoolPolicy, load_config
from agentctl.launch_input import write_input
from agentctl.projects import load_project_adapter
from conftest import FakePueue, read_launch


@pytest.fixture
def reserving(config: Config) -> Config:
    """Normal and bulk jobs reserve memory; pytest jobs are admitted by slots."""
    return replace(
        config,
        pools={
            "normal": PoolPolicy(1, 4096),
            "bulk": PoolPolicy(1, 6144),
            "pytest": PoolPolicy(1, 0),
        },
    )


def start(config: Config, project_root: Path, operation: str) -> dict[str, Any]:
    project = load_project_adapter(project_root)
    return launch.start_operation(config, project, project.operation(operation))


def started_running(fake: FakePueue, config: Config, root: Path, op: str) -> int:
    """Start a job that admission releases, and let pueue run it."""
    task_id = start(config, root, op)["task_id"]
    assert fake.task(task_id).status == "Queued"
    fake.running(task_id)
    return task_id


def events(config: Config) -> list[dict[str, Any]]:
    if not config.event_spool.exists():
        return []
    return [json.loads(line) for line in config.event_spool.read_text().splitlines()]


def test_a_reserved_job_is_held_and_released_when_the_plane_has_room(
    fake_pueue: FakePueue,
    reserving: Config,
    project_root: Path,
    plane: Callable[..., None],
) -> None:
    plane(7680, 300)

    started = start(reserving, project_root, "check")

    assert fake_pueue.added[0]["stashed"] is True
    assert fake_pueue.enqueued == [started["task_id"]]
    task = fake_pueue.task(started["task_id"])
    assert task.status == "Queued"
    written = read_launch(reserving, task)
    # Released: the hold is cleared, the reservation stays on the record.
    assert written["admission"] == {"memory_mib": 4096, "source": "pool"}
    assert written["environment"]["AGENTCTL_ADMISSION_MEMORY_MIB"] == "4096"
    [event] = [row for row in events(reserving) if row["kind"] == "admission"]
    assert event["task_id"] == started["task_id"]
    assert event["memory_mib"] == 4096


def test_a_job_the_plane_cannot_hold_waits_for_memory_across_pools(
    fake_pueue: FakePueue,
    reserving: Config,
    project_root: Path,
    plane: Callable[..., None],
) -> None:
    """Breaks if pools admit independently again: the bulk job would start
    beside the normal one and overfill the 7.5 GiB plane."""
    plane(7680, 300)
    first = started_running(fake_pueue, reserving, project_root, "check")

    second = start(reserving, project_root, "nightly")

    assert fake_pueue.task(second["task_id"]).status == "Stashed"
    assert second["phase"] == "waiting-memory"
    assert second["wait"] == {
        "reason": "memory",
        "memory_mib": 6144,
        # 7680 - 300 used now - 4096 reserved by the running check.
        "free_mib": 3284,
        "ceiling_mib": 7680,
    }
    assert admission.wait_line(second["wait"]) == (
        "waiting for memory: needs 6144 MiB, 3284 of 7680 MiB free"
    )
    [row] = [
        row
        for row in job_queries.list_jobs(config=reserving)
        if row["task_id"] == second["task_id"]
    ]
    assert row["phase"] == "waiting-memory"
    snapshot = job_queries.snapshot_jobs(10, reserving)
    [held] = [row for row in snapshot["jobs"] if row["task_id"] == second["task_id"]]
    assert held["wait"]["reason"] == "memory"
    assert held["phase"] == "waiting-memory"
    queue = job_queries.job_queue(reserving, second)
    assert queue["reason"] == "memory"
    detail = job_queries.get_job(second["task_id"], reserving)
    assert detail["phase"] == "waiting-memory"
    assert detail["wait"]["memory_mib"] == 6144

    # The check finishes; its wrapper's pass releases the bulk job.
    fake_pueue.succeed(first)
    passed = admission.admit(reserving)

    assert [row["task_id"] for row in passed["released"]] == [second["task_id"]]
    assert fake_pueue.task(second["task_id"]).status == "Queued"


def test_a_job_using_more_than_it_reserved_is_charged_what_it_uses(
    fake_pueue: FakePueue,
    reserving: Config,
    project_root: Path,
    plane: Callable[..., None],
) -> None:
    plane(7680, 0)
    running = started_running(fake_pueue, reserving, project_root, "nightly")
    unit = job_queries.unit_of(fake_pueue.task(running))
    plane(7680, 7300, {unit: 7000})

    held = start(reserving, project_root, "check")

    assert held["wait"]["free_mib"] == 380
    assert fake_pueue.task(held["task_id"]).status == "Stashed"


def test_the_first_held_job_starts_when_no_reserved_job_runs(
    fake_pueue: FakePueue,
    reserving: Config,
    project_root: Path,
    plane: Callable[..., None],
) -> None:
    """A reservation above the ceiling, or memory held by unreserved work such
    as agents waiting on this very build, must not hold the queue for good."""
    plane(4096, 3000)

    started = start(reserving, project_root, "nightly")

    assert fake_pueue.task(started["task_id"]).status == "Queued"


def test_a_held_job_whose_pool_is_full_does_not_block_other_pools(
    fake_pueue: FakePueue, reserving: Config, project_root: Path
) -> None:
    started_running(fake_pueue, reserving, project_root, "check")

    second = start(reserving, project_root, "check")
    other = start(reserving, project_root, "nightly")

    assert fake_pueue.task(second["task_id"]).status == "Stashed"
    assert second["phase"] == "queued"
    assert second["wait"]["reason"] == "pool-full"
    assert fake_pueue.task(other["task_id"]).status == "Queued"


def _age_hold(config: Config, fake: FakePueue, task_id: int, seconds: int) -> None:
    task = fake.task(task_id)
    path = job_queries.launch_input_path(task)
    document = read_launch(config, task)
    since = datetime.now(UTC) - timedelta(seconds=seconds)
    document["admission"]["held_since"] = since.isoformat(timespec="seconds")
    write_input(path, document)


@pytest.mark.parametrize(
    ("waited", "passes"),
    [(60, True), (admission.HEAD_OF_LINE_SECONDS + 1, False)],
)
def test_a_smaller_job_passes_a_held_one_only_until_that_has_waited_long(
    fake_pueue: FakePueue,
    reserving: Config,
    project_root: Path,
    plane: Callable[..., None],
    waited: int,
    passes: bool,
) -> None:
    config = replace(
        reserving, pools={**reserving.pools, "pytest": PoolPolicy(1, 1024)}
    )
    plane(7680, 0)
    started_running(fake_pueue, config, project_root, "check")
    big = start(config, project_root, "nightly")
    _age_hold(config, fake_pueue, big["task_id"], waited)

    small = start(config, project_root, "verify")

    assert (fake_pueue.task(small["task_id"]).status == "Queued") is passes
    if not passes:
        assert small["wait"]["behind"]["task_id"] == big["task_id"]


def test_an_operator_stash_is_never_released(
    fake_pueue: FakePueue, reserving: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    stashed = launch.enqueue(
        reserving,
        project=project,
        operation="check",
        label="fixture:check",
        group="normal",
        argv=["true"],
        working_directory=project_root,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
        stashed=True,
    )

    admission.admit(reserving)

    assert fake_pueue.task(stashed["task_id"]).status == "Stashed"
    assert fake_pueue.enqueued == []
    assert job_queries.job_queue(reserving, stashed)["reason"] == "stashed"


def test_an_unreserved_job_is_added_to_its_pool_directly(
    fake_pueue: FakePueue, reserving: Config, project_root: Path
) -> None:
    started = start(reserving, project_root, "verify")

    assert fake_pueue.added[0]["stashed"] is False
    assert "admission" not in read_launch(
        reserving, fake_pueue.task(started["task_id"])
    )


def test_a_reserved_deferral_is_kept_by_admission_not_by_pueue_delay(
    fake_pueue: FakePueue, reserving: Config, project_root: Path
) -> None:
    """pueue's delayed enqueue would put the job in its pool unadmitted."""
    project = load_project_adapter(project_root)
    until = (datetime.now(UTC) + timedelta(hours=1)).isoformat(timespec="seconds")
    held = launch.enqueue(
        reserving,
        project=project,
        operation="check",
        label="fixture:check",
        group="normal",
        argv=["true"],
        working_directory=project_root,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
        deferred={"reason": "quota", "until": until, "delay_seconds": 3600},
    )

    assert fake_pueue.added[0]["delay_seconds"] is None
    assert fake_pueue.task(held["task_id"]).status == "Stashed"
    assert held["wait"]["reason"] == "deferred"


def test_a_retried_reserved_job_is_held_again(
    fake_pueue: FakePueue,
    reserving: Config,
    project_root: Path,
    plane: Callable[..., None],
) -> None:
    plane(7680, 0)
    first = started_running(fake_pueue, reserving, project_root, "check")
    fake_pueue.fail(first, exit_code=1)
    started_running(fake_pueue, reserving, project_root, "nightly")

    launch.retry(reserving, first)

    task = fake_pueue.task(first)
    assert task.status == "Stashed"
    assert admission.is_held(read_launch(reserving, task))


def test_a_finishing_wrapper_runs_a_pass_only_as_a_queue_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[int | None] = []
    monkeypatch.setattr(
        admission, "admit", lambda config, *, exclude=None: calls.append(exclude)
    )
    launched = {"environment": {"AGENTCTL_CONFIG": str(tmp_path / "absent.json")}}

    run_module._admit_after(launched)
    monkeypatch.setenv("PUEUE_ID", "17")
    run_module._admit_after(launched)

    assert calls == [17]


def test_a_pool_declares_its_default_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    location = tmp_path / "agentctl.json"
    location.write_text(
        json.dumps({"pools": {"normal": {"parallel": 1, "memory_mib": 4096}}})
    )
    assert load_config(location).pools["normal"] == PoolPolicy(1, 4096)
    location.write_text(
        json.dumps({"pools": {"normal": {"parallel": 1, "memory_mib": -1}}})
    )
    with pytest.raises(ConfigError, match="memory_mib"):
        load_config(location)


def test_plane_usage_excludes_clean_page_cache(tmp_path: Path) -> None:
    cgroup = tmp_path / "cg"
    cgroup.mkdir()
    (cgroup / "memory.current").write_text(str(5000 * admission.MIB))
    (cgroup / "memory.stat").write_text(
        f"anon {1000 * admission.MIB}\nfile {3500 * admission.MIB}\n"
        f"shmem {500 * admission.MIB}\n"
    )
    # 5000 - (3500 file - 500 tmpfs) = 2000 MiB that reclaim cannot free.
    assert admission._unreclaimable_mib(cgroup) == 2000
