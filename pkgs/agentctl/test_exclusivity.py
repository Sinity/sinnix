"""Pools that must not run together: the hold, its order, and its release.

The incident: on a 32 GB workstation Polylogue's corpus `verify_all` never
finished beside a wave of agents — killed at 137, cancelled at its 14400s
budget, 8% done after 85 minutes — so every landing wave went unverified.
pueue admits each group on its own and has no notion of one group excluding
another, so the pair is agentctl's to keep apart: a launch into an excluded
pool is stashed with its reason, and released once that pool has drained.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agentctl import agents, cli, launch, operator_view, pools
from agentctl.config import Config, ConfigError, PoolPolicy, load_config
from agentctl.projects import ProjectAdapter, load_project_adapter
from conftest import FakeBd, FakePueue, bead, read_launch

NOW = datetime(2026, 9, 11, 3, 17, tzinfo=UTC)

DECLARED = {
    "agent": PoolPolicy(parallel=6),
    # The declaration under test: the corpus pool excludes the agent pool.
    "pytest": PoolPolicy(parallel=1, exclusive_with=("agent",)),
    "normal": PoolPolicy(parallel=2),
    "bulk": PoolPolicy(parallel=1),
}


@pytest.fixture
def exclusive(config: Config) -> Config:
    return replace(config, pools=DECLARED)


@pytest.fixture
def project(project_root: Path) -> ProjectAdapter:
    return load_project_adapter(project_root)


def agent_task(fake_pueue: FakePueue, project_root: Path, label: str) -> int:
    """A worker already running in the `agent` pool."""
    return fake_pueue.add(
        group="agent",
        label=label,
        command=("agentctl-run", "/nonexistent/other.json"),
        working_directory=project_root,
    )


def corpus(config: Config, project: ProjectAdapter) -> int:
    """Start the fixture's pytest-pool verification, as a timer or an operator does."""
    return launch.start_operation(config, project, project.operation("verify"))[
        "job_id"
    ]


def test_a_corpus_run_is_held_while_the_agent_pool_is_busy(
    fake_pueue: FakePueue, exclusive: Config, config: Config, project: ProjectAdapter
) -> None:
    """The run waits in the queue instead of contending with the wave.

    Anti-vacuity: the same launch under a declaration without the exclusion
    starts at once, so this pins the declaration and not the fixture.
    """
    worker = agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")

    held = corpus(exclusive, project)

    task = fake_pueue.task(held)
    assert task.status == "Stashed"
    hold = read_launch(exclusive, task)["hold"]
    assert hold["reason"] == "pool-exclusivity"
    assert hold["pool"] == "pytest"
    assert hold["excluded_by"] == ["agent"]
    assert hold["waiting_for"] == [worker]
    assert hold["held_at"]

    admitted = corpus(config, project)
    assert fake_pueue.task(admitted).status == "Running"


def test_a_hold_is_released_once_the_excluded_pool_has_drained(
    fake_pueue: FakePueue, exclusive: Config, project: ProjectAdapter
) -> None:
    worker = agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")
    held = corpus(exclusive, project)

    waiting = launch.release_holds(exclusive)
    assert waiting["released"] == []
    assert waiting["waiting"] == [
        {
            "task_id": held,
            "label": "fixture:verify",
            "pool": "pytest",
            "excluded_by": ["agent"],
            "waiting_for": [worker],
        }
    ]

    fake_pueue.succeed(worker)
    released = launch.release_holds(exclusive)

    assert [row["task_id"] for row in released["released"]] == [held]
    assert fake_pueue.task(held).status == "Queued"
    assert fake_pueue.enqueued == [held]
    # Released once: the pass has nothing left to hold, and a task it already
    # let go is not enqueued again on the next minute's tick.
    assert launch.release_holds(exclusive) == {"released": [], "waiting": []}
    assert fake_pueue.enqueued == [held]


def test_withdrawing_the_exclusion_releases_what_it_was_holding(
    fake_pueue: FakePueue, exclusive: Config, project: ProjectAdapter
) -> None:
    """A declaration is a live policy, not a one-way door.

    Anti-vacuity: a pass that skipped the read when nothing is declared
    exclusive would leave the task stashed for as long as the queue lives.
    """
    agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")
    held = corpus(exclusive, project)
    assert fake_pueue.task(held).status == "Stashed"

    withdrawn = replace(exclusive, pools={**DECLARED, "pytest": PoolPolicy(parallel=1)})

    assert [row["task_id"] for row in launch.release_holds(withdrawn)["released"]] == [
        held
    ]
    assert fake_pueue.task(held).status == "Queued"


def test_an_agent_queued_while_the_corpus_waits_runs_after_it(
    fake_pueue: FakePueue, exclusive: Config, project: ProjectAdapter, tmp_path: Path
) -> None:
    """The second half: while the corpus is due, no new agent is admitted.

    The order is the task id, which is what keeps two exclusive pools from
    holding each other forever: the corpus waits only for the wave it found,
    and the agent queued behind it waits for the corpus.
    """
    worker = agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")
    held = corpus(exclusive, project)
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    later = agents.queue_agent(
        exclusive,
        project,
        label="fixture:worker:run-2:fx-2",
        worktree=worktree,
        prompt="do the work",
        prompt_name="prompt.md",
        backend="codex",
        model="fixture-model",
        effort="low",
    )["job_id"]

    assert fake_pueue.task(later).status == "Stashed"
    fake_pueue.succeed(worker)

    first = launch.release_holds(exclusive)
    # Anti-deadlock: the wave drained, so the corpus goes even though an agent
    # is held; a rule that let held tasks block each other would release none.
    assert [row["task_id"] for row in first["released"]] == [held]
    assert [row["task_id"] for row in first["waiting"]] == [later]
    assert [row["waiting_for"] for row in first["waiting"]] == [[held]]

    fake_pueue.running(held)
    assert launch.release_holds(exclusive)["released"] == []
    fake_pueue.succeed(held)

    second = launch.release_holds(exclusive)
    assert [row["task_id"] for row in second["released"]] == [later]
    assert fake_pueue.task(later).status == "Queued"


def test_a_launch_from_inside_an_agent_is_never_held(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worker's own verification must not wait for the worker to finish.

    The agent's task already occupies the excluded pool, so holding what it
    started against that pool would wait for a task that is waiting for it.
    """
    monkeypatch.setenv("AGENTCTL_PRINCIPAL", "agent-control")
    agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")

    started = corpus(exclusive, project)

    assert fake_pueue.task(started).status == "Running"
    assert "hold" not in read_launch(exclusive, fake_pueue.task(started))


def test_a_task_stashed_for_another_reason_is_never_released(
    fake_pueue: FakePueue, exclusive: Config, project: ProjectAdapter
) -> None:
    """An external harness's landing waits for its worker's result, not for a pool.

    Anti-vacuity: a pass that enqueued every stashed task in a drained pool
    would start it before the result it is stashed for exists.
    """
    stashed = launch.enqueue(
        exclusive,
        project=project,
        operation="land:run-1",
        label="fixture:land:run-1",
        group="pytest",
        argv=("true",),
        working_directory=project.root,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
        stashed=True,
    )["job_id"]

    assert "hold" not in read_launch(exclusive, fake_pueue.task(stashed))
    assert launch.release_holds(exclusive) == {"released": [], "waiting": []}
    assert fake_pueue.task(stashed).status == "Stashed"
    assert fake_pueue.enqueued == []


def test_a_scheduled_corpus_waits_for_the_drain_instead_of_piling_up(
    fake_pueue: FakePueue, exclusive: Config, project: ProjectAdapter
) -> None:
    """The nightly firing: one held task, and the next firing is skipped.

    03:17 with a wave running is exactly when the corpus died; held, it is
    still the operation's one active launch, so the timer adds no second.
    """
    agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")

    fired = launch.fire(exclusive, project, project.operation("verify"))

    assert fired["fired"] is True
    assert fake_pueue.task(fired["job_id"]).status == "Stashed"

    again = launch.fire(exclusive, project, project.operation("verify"))
    assert again == {
        "fired": False,
        "label": "fixture:verify",
        "active": [fired["job_id"]],
    }


def test_the_view_names_the_hold_and_the_pool_it_waits_for(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`agentctl view` must say why an idle pool is not running its work."""
    # Another project's wave: what holds this project's task is usually not
    # this project's own task, so the screen must still name it.
    worker = agent_task(fake_pueue, project.root, "other:worker:run-9:fx-9")
    held = corpus(exclusive, project)
    monkeypatch.setattr(
        operator_view,
        "SubprocessBdReader",
        lambda root: FakeBd(beads={"fx-1": bead("fx-1", "One")}),
    )

    snapshot = operator_view.collect(exclusive, project, now=NOW)

    assert snapshot.holds[held]["excluded_by"] == ["agent"]
    assert snapshot.holds[held]["waiting_for"] == [worker]
    document = snapshot.to_dict()
    assert document["groups"]["pytest"]["held"] == 1
    assert document["jobs"][0]["hold"]["excluded_by"] == ["agent"]
    assert "held for agent" in operator_view.render(snapshot)


def test_the_admission_pass_releases_what_the_drain_freed(
    fake_pueue: FakePueue,
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The minute timer is the release: `backpressure tick` is one admission pass."""
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(
        json.dumps(
            {
                "project_roots": [str(project_root)],
                "state_dir": str(tmp_path / "state"),
                "event_spool": str(tmp_path / "events.jsonl"),
                "pools": {
                    "agent": 6,
                    "pytest": {"parallel": 1, "exclusive_with": ["agent"]},
                },
            }
        )
    )
    monkeypatch.setenv("AGENTCTL_CONFIG", str(configuration))
    config = load_config(configuration)
    worker = agent_task(fake_pueue, project_root, "fixture:worker:run-1:fx-1")
    held = corpus(config, load_project_adapter(project_root))
    fake_pueue.succeed(worker)

    assert cli.main(["backpressure", "tick", "--json"]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert [row["task_id"] for row in printed["released"]] == [held]
    assert printed["held"] == []
    assert fake_pueue.task(held).status == "Queued"
    spooled = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
    ]
    holds = [event for event in spooled if event["kind"] == "pool-hold"]
    assert [event["action"] for event in holds] == ["held", "released"]


def test_a_real_daemon_holds_the_launch_and_starts_it_at_the_drain(
    live_pueue: str, exclusive: Config, project: ProjectAdapter, tmp_path: Path
) -> None:
    """The contract against a real pueued, which is where it has to hold.

    Only the daemon can show that a held task keeps its place in the queue
    rather than being paused or killed, and that `pueue enqueue` is all it
    takes to start it once the excluded pool is empty.
    """
    from agentctl import pueue as pueue_module

    pueue_module.group_add("agent", 2)
    pueue_module.group_add("pytest", 1)
    worker = pueue_module.add(
        group="agent",
        label="fixture:worker:run-1:fx-1",
        command=("sleep", "60"),
        working_directory=tmp_path,
    )
    deadline = time.monotonic() + 20
    while pueue_module.task(worker).status != "Running":
        assert time.monotonic() < deadline, "the fixture worker never started"
        time.sleep(0.1)

    held = launch.enqueue(
        exclusive,
        project=project,
        operation="verify",
        label="fixture:verify",
        group="pytest",
        argv=("true",),
        working_directory=tmp_path,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
    )["job_id"]

    assert pueue_module.task(held).status == "Stashed"
    assert launch.release_holds(exclusive)["waiting"][0]["waiting_for"] == [worker]
    # The wave is what holds it: the group itself is open, and the queue still
    # has the task.
    assert pueue_module.groups_status()["pytest"] == "Running"

    pueue_module.kill(worker)
    deadline = time.monotonic() + 20
    while not pueue_module.task(worker).terminal:
        assert time.monotonic() < deadline, "the fixture worker was not killed"
        time.sleep(0.1)

    assert [row["task_id"] for row in launch.release_holds(exclusive)["released"]] == [
        held
    ]
    assert pueue_module.task(held).status != "Stashed"


def test_the_declaration_reads_both_shapes_and_refuses_a_partner_it_has_not_declared(
    tmp_path: Path,
) -> None:
    """A typo in `exclusive_with` would silently admit the pair it forbids."""
    path = tmp_path / "agentctl.json"
    path.write_text(
        json.dumps(
            {
                "pools": {
                    "agent": 12,
                    "pytest": {"parallel": 2, "exclusive_with": ["agent"]},
                }
            }
        )
    )

    declared = load_config(path).pools

    assert declared["agent"] == PoolPolicy(parallel=12)
    assert declared["pytest"] == PoolPolicy(parallel=2, exclusive_with=("agent",))

    for broken in (
        {"pytest": {"parallel": 2, "exclusive_with": ["agents"]}},
        {"pytest": {"parallel": 2, "exclusive_with": ["pytest"]}},
        {"pytest": {"parallel": 2, "exclusive_with": "agent"}},
        {"pytest": {"exclusive_with": ["agent"]}},
        {"agent": 1, "pytest": {"parallel": 2, "excludes": ["agent"]}},
    ):
        path.write_text(json.dumps({"pools": broken}))
        with pytest.raises(ConfigError):
            load_config(path)


def test_an_exclusion_declared_on_one_side_holds_on_both() -> None:
    """Anti-vacuity: a one-way reading would admit the agent wave mid-corpus."""
    assert pools.exclusive_partners(DECLARED, "pytest") == ("agent",)
    assert pools.exclusive_partners(DECLARED, "agent") == ("pytest",)
    assert pools.exclusive_partners(DECLARED, "bulk") == ()
