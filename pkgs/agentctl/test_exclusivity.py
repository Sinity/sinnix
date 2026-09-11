"""Pools that must not run together: the hold, its order, and its release.

The incident: on a 32 GB workstation Polylogue's corpus `verify_all` never
finished beside a wave of agents — killed at 137, cancelled at its 14400s
budget, 8% done after 85 minutes — so every landing wave went unverified.
pueue admits each group on its own and has no notion of one group excluding
another, so the pair is agentctl's to keep apart: a launch into an excluded
pool is stashed with its reason, and released once that pool has drained.
"""

from __future__ import annotations

import fcntl
import json
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agentctl import agents, cli, launch, operator_view, pools, pueue
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


def test_a_corpus_launched_from_inside_the_wave_is_refused(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worker does not start the run its own wave is the reason to hold.

    Every batch worker runs with `AGENTCTL_PRINCIPAL=agent-control`, so keying
    the exemption on the principal exempted exactly the launch the declaration
    exists to stop: a corpus run started from inside a wave ran beside it.
    Holding it instead would wait for the worker that started it, so it is
    refused, and nothing is queued.
    """
    monkeypatch.setenv("AGENTCTL_PRINCIPAL", "agent-control")
    monkeypatch.setenv("AGENTCTL_POOL", "agent")
    worker = agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")

    with pytest.raises(launch.JobError) as refusal:
        corpus(exclusive, project)

    assert "excludes pool 'agent'" in str(refusal.value)
    assert list(fake_pueue.tasks()) == [worker]


def test_a_workers_focused_selection_runs_beside_its_own_wave(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal is the corpus pool's, not the agent's.

    A worker's bounded selection runs in a pool nothing excludes, which is
    what keeps the rule from stopping the verification every worker owes its
    own candidate.
    """
    monkeypatch.setenv("AGENTCTL_PRINCIPAL", "agent-control")
    monkeypatch.setenv("AGENTCTL_POOL", "agent")
    agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")

    focused = launch.start_operation(exclusive, project, project.operation("check"))[
        "job_id"
    ]

    assert fake_pueue.task(focused).group == "normal"
    assert fake_pueue.task(focused).status == "Running"
    assert "hold" not in read_launch(exclusive, fake_pueue.task(focused))


def test_a_launch_from_a_pool_the_target_does_not_exclude_is_held(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A landing's own pool is not excluded, so its corpus launch waits its turn.

    Anti-vacuity: refusing every nested launch would turn a hold that resolves
    at the drain into a failure, and the wave's backstop would go unrun.
    """
    monkeypatch.setenv("AGENTCTL_PRINCIPAL", "agent-control")
    monkeypatch.setenv("AGENTCTL_POOL", "fixture-land")
    worker = agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")

    held = corpus(exclusive, project)

    assert fake_pueue.task(held).status == "Stashed"
    assert read_launch(exclusive, fake_pueue.task(held))["hold"]["waiting_for"] == [
        worker
    ]


def lock_is_held(config: Config) -> bool:
    """Whether some open file description holds the host's admission lock.

    flock associates a lock with the open file description, so a second open
    of the same path is denied even inside the process that holds it.
    """
    path = config.state_dir / launch.ADMISSION_LOCK_NAME
    with open(path, "a", encoding="utf-8") as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(probe, fcntl.LOCK_UN)
        return False


def test_the_queue_is_read_and_joined_under_one_lock(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admission is one step, not a read and a later add.

    pueue has no conditional add: agentctl decides the hold from a status it
    read, and two launches into mutually exclusive pools would otherwise each
    read a queue the other had not joined and both be admitted. The lock is
    the proof, so the test watches it across both calls.
    """
    inside: list[tuple[str, bool]] = []
    read, add = pueue.tasks, pueue.add

    def watched_tasks() -> dict[int, object]:
        inside.append(("tasks", lock_is_held(exclusive)))
        return read()

    def watched_add(**arguments: object) -> int:
        inside.append(("add", lock_is_held(exclusive)))
        return add(**arguments)

    monkeypatch.setattr(pueue, "tasks", watched_tasks)
    monkeypatch.setattr(pueue, "add", watched_add)
    agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")

    held = corpus(exclusive, project)

    assert inside == [("tasks", True), ("add", True)]
    assert fake_pueue.task(held).status == "Stashed"
    # And the lock is a section, not a leak: the next launch can take it.
    assert lock_is_held(exclusive) is False


def test_a_launch_refuses_rather_than_admitting_itself_without_the_lock(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lock it cannot take stops the launch; it does not fall through to add."""
    monkeypatch.setattr(launch, "ADMISSION_LOCK_SECONDS", 0.2)
    path = exclusive.state_dir / launch.ADMISSION_LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as blocker:
        fcntl.flock(blocker, fcntl.LOCK_EX)

        with pytest.raises(launch.JobError) as refusal:
            corpus(exclusive, project)

    assert "admission.lock" in str(refusal.value)
    assert fake_pueue.tasks() == {}


def test_two_launches_into_exclusive_pools_cannot_both_be_admitted(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The race the lock exists for, run.

    Both pools are idle, and the corpus launch is held inside its own
    admission — long enough for a second launch into the excluded pool to
    arrive. Without the lock that second launch reads the very status the
    first read, finds the pool empty and starts: the corpus and the wave run
    together, which is the one outcome the declaration forbids.
    """
    read = pueue.tasks
    inside = threading.Event()

    def slow_tasks() -> dict[int, object]:
        status = read()
        if not inside.is_set():
            inside.set()
            time.sleep(0.5)
        return status

    monkeypatch.setattr(pueue, "tasks", slow_tasks)

    def launch_into(pool: str, label: str) -> int:
        return launch.enqueue(
            exclusive,
            project=project,
            operation=label.split(":", 1)[1],
            label=label,
            group=pool,
            argv=("true",),
            working_directory=project.root,
            timeout_seconds=60,
            result_kind="exit",
            environment={},
        )["job_id"]

    admitted: dict[str, int] = {}
    first = threading.Thread(
        target=lambda: admitted.__setitem__(
            "corpus", launch_into("pytest", "fixture:verify")
        )
    )
    first.start()
    assert inside.wait(10), "the first launch never reached the queue"

    worker = launch_into("agent", "fixture:worker")
    first.join(30)

    assert not first.is_alive()
    assert fake_pueue.task(admitted["corpus"]).status == "Running"
    assert fake_pueue.task(worker).status == "Stashed"
    assert read_launch(exclusive, fake_pueue.task(worker))["hold"]["waiting_for"] == [
        admitted["corpus"]
    ]


def test_the_release_pass_holds_the_admission_lock(
    fake_pueue: FakePueue,
    exclusive: Config,
    project: ProjectAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Releasing a hold is admitting work, so it takes the same lock.

    A pass that decided from a queue a concurrent launch was already joining
    would enqueue against the wave it was meant to wait for.
    """
    worker = agent_task(fake_pueue, project.root, "fixture:worker:run-1:fx-1")
    corpus(exclusive, project)
    fake_pueue.succeed(worker)
    seen: list[bool] = []
    enqueue = pueue.enqueue

    def watched_enqueue(task_id: int) -> None:
        seen.append(lock_is_held(exclusive))
        enqueue(task_id)

    monkeypatch.setattr(pueue, "enqueue", watched_enqueue)

    released = launch.release_holds(exclusive)

    assert seen == [True]
    assert len(released["released"]) == 1


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
