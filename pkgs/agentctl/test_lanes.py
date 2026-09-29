"""Pool promotion, queue state and cheap job addressing.

A promoting pool counts only its young running tasks against its width, so a
quick task never waits behind long work that happened to land in the same
pool. The live tests drive a private pueued; the fake tests prove a job read
never loads the queue's whole history.
"""

from __future__ import annotations

import dataclasses
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from agentctl import launch, pueue
from agentctl.config import Config, PoolPolicy, load_config
from conftest import FakePueue

LANE = "lane"


def _promoting(config: Config, *, parallel: int = 1, horizon: int = 20) -> Config:
    return dataclasses.replace(
        config,
        pools={LANE: PoolPolicy(parallel=parallel, promote_after_seconds=horizon)},
    )


def _until(task_id: int, status: str, *, seconds: float = 20.0) -> pueue.Task:
    deadline = time.monotonic() + seconds
    while True:
        task = pueue.task(task_id)
        if task is not None and task.status == status:
            return task
        if time.monotonic() > deadline:
            raise AssertionError(f"task {task_id} never reached {status}: {task}")
        time.sleep(0.05)


def _later(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def test_a_queued_task_starts_beside_long_work_that_holds_every_slot(
    live_pueue: str, config: Config, tmp_path: Path
) -> None:
    """Promotion admits the quick task; the long one keeps running untouched.

    Anti-vacuity: while the long task is younger than the horizon, promotion
    admits nothing and the quick task stays queued, so the later start is
    promotion's doing and not a free slot.
    """
    config = _promoting(config)
    pueue.group_add(LANE, 1)
    long = pueue.add(
        group=LANE,
        label="fixture:shell",
        command=("sleep", "60"),
        working_directory=tmp_path,
    )
    _until(long, "Running")
    quick = pueue.add(
        group=LANE,
        label="fixture:shell",
        command=("true",),
        working_directory=tmp_path,
    )
    assert pueue.task(quick).status == "Queued"

    assert launch.promote_overdue(config, LANE) == []
    assert pueue.task(quick).status == "Queued"

    assert launch.promote_overdue(config, LANE, now=_later(30)) == [quick]
    finished = pueue.wait(quick, timeout_seconds=20)
    assert finished.succeeded
    assert pueue.task(long).status == "Running"
    events = [json.loads(line) for line in config.event_spool.read_text().splitlines()]
    assert (events[-1]["kind"], events[-1]["action"]) == ("pool-promotion", "started")
    assert events[-1]["started"] == [quick] and events[-1]["overdue"] == [long]
    pueue.kill(long)


def test_promotion_leaves_a_paused_pool_and_dependent_tasks_alone(
    live_pueue: str, config: Config, tmp_path: Path
) -> None:
    config = _promoting(config)
    pueue.group_add(LANE, 1)
    long = pueue.add(
        group=LANE,
        label="fixture:shell",
        command=("sleep", "60"),
        working_directory=tmp_path,
    )
    _until(long, "Running")
    dependent = pueue.add(
        group=LANE,
        label="fixture:shell",
        command=("true",),
        working_directory=tmp_path,
        after=(long,),
    )
    # Its dependency is unfinished: forcing it would run it out of order.
    assert launch.promote_overdue(config, LANE, now=_later(30)) == []
    assert pueue.task(dependent).status == "Queued"

    pueue.remove([dependent])
    quick = pueue.add(
        group=LANE, label="fixture:shell", command=("true",), working_directory=tmp_path
    )
    pueue.pause(LANE)
    # A paused pool is an operator's or backpressure's decision to hold it.
    assert launch.promote_overdue(config, LANE, now=_later(30)) == []
    assert pueue.task(quick).status == "Queued"
    pueue.resume(LANE)
    pueue.kill(long)


def test_a_pool_without_a_horizon_never_promotes(
    fake_pueue: FakePueue, config: Config
) -> None:
    config = dataclasses.replace(config, pools={LANE: PoolPolicy(parallel=1)})
    fake_pueue.groups[LANE] = 1
    fake_pueue.fail_tasks = True  # any queue read would raise
    assert launch.promote_overdue(config, LANE, now=_later(3_600)) == []
    assert fake_pueue.started == []


def test_queue_state_names_what_holds_each_slot_and_who_waits(
    live_pueue: str, config: Config, tmp_path: Path
) -> None:
    config = _promoting(config)
    pueue.group_add(LANE, 1)
    long = pueue.add(
        group=LANE,
        label="fixture:shell",
        command=("sleep", "60"),
        working_directory=tmp_path,
    )
    _until(long, "Running")
    first = pueue.add(
        group=LANE, label="fixture:shell", command=("true",), working_directory=tmp_path
    )
    second = pueue.add(
        group=LANE, label="fixture:shell", command=("true",), working_directory=tmp_path
    )

    young = launch.queue_state(config, [LANE])[LANE]
    assert (young["parallel"], young["status"]) == (1, "Running")
    assert [entry["job_id"] for entry in young["running"]] == [long]
    assert young["running"][0]["promoted"] is False
    assert young["holding_count"] == 1
    assert [entry["job_id"] for entry in young["queued"]] == [first, second]
    assert young["queued_count"] == 2
    assert young["oldest_queued_seconds"] is not None

    position = launch.job_queue(config, launch.job_view(pueue.task(second)))
    assert position["position"] == 2 and position["ahead"] == [first]
    assert [entry["job_id"] for entry in position["occupied_by"]] == [long]
    running = launch.job_queue(config, launch.job_view(pueue.task(long)))
    assert running["position"] is None and running["occupied_by"] == []

    old = launch.queue_state(config, [LANE], now=_later(30))[LANE]
    assert old["running"][0]["promoted"] is True and old["holding_count"] == 0
    missing = launch.queue_state(config, ["absent"])["absent"]
    assert missing["known"] is False and missing["running"] == []
    pueue.kill(long)
    pueue.remove([first, second])


def test_a_job_read_by_reference_never_loads_the_queue_history(
    fake_pueue: FakePueue, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: the full status read raises here, so a lookup that fell
    back to it would fail instead of answering."""
    inputs = tmp_path / "inputs"
    fake_pueue.groups[LANE] = 1
    first = fake_pueue.add(
        group=LANE,
        label="fixture:shell",
        command=("agentctl-run", str(inputs / "fixture-shell-aaaa1111.json")),
        working_directory=tmp_path,
    )
    moved = fake_pueue.add(
        group=LANE,
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
    # The id now names another job: the reference finds its own.
    assert launch.locate(first, "fixture-shell-bbbb2222").task_id == moved
    assert launch.locate(first, "fixture-shell-cccc3333") is None


def _shell(fake: FakePueue, inputs: Path, name: str) -> tuple[int, str]:
    task_id = fake.add(
        group=LANE,
        label="fixture:shell",
        command=("agentctl-run", str(inputs / f"{name}.json")),
        working_directory=inputs,
    )
    return task_id, name


def test_reading_or_waiting_on_a_queued_job_promotes_it(
    fake_pueue: FakePueue, config: Config, tmp_path: Path
) -> None:
    """The routes callers poll are the ones that admit a job long work holds.

    Anti-vacuity: the same wait without the configuration (the route that
    predates promotion) leaves the job queued behind the long one.
    """
    config = _promoting(config)
    fake_pueue.groups[LANE] = 1
    inputs = tmp_path / "inputs"
    # The fake stamps starts in the past, so the long task is overdue.
    long, _ = _shell(fake_pueue, inputs, "fixture-shell-00000001")
    polled, polled_ref = _shell(fake_pueue, inputs, "fixture-shell-00000002")
    waited, waited_ref = _shell(fake_pueue, inputs, "fixture-shell-00000003")
    fake_pueue.queue(polled)
    fake_pueue.queue(waited)

    launch.wait(waited, timeout_seconds=1, reference=waited_ref)
    assert fake_pueue.task(waited).status == "Queued"
    assert fake_pueue.started == []

    read = launch.get_job(polled, config, polled_ref)
    assert fake_pueue.started == [polled] and read["phase"] == "running"

    fake_pueue.succeed(polled)
    answer = launch.wait(waited, timeout_seconds=1, reference=waited_ref, config=config)
    assert fake_pueue.started == [polled, waited]
    assert answer["phase"] == "running" and fake_pueue.task(long).status == "Running"


def test_a_task_pueue_started_first_is_not_a_promotion_failure(
    fake_pueue: FakePueue,
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pueue refuses to start a task its scheduler already started; the rest
    of the admission still happens and is recorded."""
    config = _promoting(config, parallel=2)
    fake_pueue.groups[LANE] = 2
    inputs = tmp_path / "inputs"
    _shell(fake_pueue, inputs, "fixture-shell-00000011")
    _shell(fake_pueue, inputs, "fixture-shell-00000012")
    raced, _ = _shell(fake_pueue, inputs, "fixture-shell-00000013")
    admitted, _ = _shell(fake_pueue, inputs, "fixture-shell-00000014")
    fake_pueue.queue(raced)
    fake_pueue.queue(admitted)
    real_start = fake_pueue.start

    def scheduler_wins(task_id: int) -> None:
        if task_id == raced:
            fake_pueue.running(raced)
        real_start(task_id)

    monkeypatch.setattr(pueue, "start", scheduler_wins)

    assert launch.promote_overdue(config, LANE) == [admitted]
    event = json.loads(config.event_spool.read_text().splitlines()[-1])
    assert event["action"] == "started" and event["started"] == [admitted]


def test_a_promotion_the_daemon_refuses_is_recorded_not_raised(
    fake_pueue: FakePueue,
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Red if a failed promotion fails the read that triggered it, or leaves
    no trace of why the job stayed queued."""
    config = _promoting(config)
    fake_pueue.groups[LANE] = 1
    inputs = tmp_path / "inputs"
    _shell(fake_pueue, inputs, "fixture-shell-00000021")
    queued, _ = _shell(fake_pueue, inputs, "fixture-shell-00000022")
    fake_pueue.queue(queued)

    def refused(task_id: int) -> None:
        raise pueue.PueueError("daemon refused")

    monkeypatch.setattr(pueue, "start", refused)

    assert launch.promote_overdue(config, LANE) == []
    event = json.loads(config.event_spool.read_text().splitlines()[-1])
    assert (event["action"], event["error"]) == ("failed", "daemon refused")
    assert fake_pueue.task(queued).status == "Queued"


def test_config_reads_a_pools_promotion_horizon(tmp_path: Path) -> None:
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(
        json.dumps(
            {"pools": {"shell-quick": {"parallel": 8, "promote_after_seconds": 20}}}
        )
    )
    assert load_config(configuration).pools["shell-quick"] == PoolPolicy(
        parallel=8, promote_after_seconds=20
    )
    configuration.write_text(
        json.dumps(
            {"pools": {"shell-quick": {"parallel": 8, "promote_after_seconds": 0}}}
        )
    )
    with pytest.raises(ValueError, match="promote_after_seconds"):
        load_config(configuration)
