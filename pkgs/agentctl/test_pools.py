"""Declared group parallelism applied to a daemon that keeps running.

The live test is the contract: only a real pueued can show that a resize
leaves the queue, the running task and the pause alone. The stub tests pin
what the pass does when nothing has drifted and what it refuses to touch.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from agentctl import cli, pools, pueue
from conftest import FakePueue


def _groups(home: str) -> dict[str, dict]:
    environment = {"HOME": home, "PATH": os.environ["PATH"]}
    printed = subprocess.run(
        ["pueue", "group", "--json"],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(printed)


def test_a_drifted_group_is_resized_without_restarting_the_daemon(
    live_pueue: str, tmp_path: Path
) -> None:
    """The bug: a switch left `pytest` at 3 and two concurrent runs were OOM-killed.

    Anti-vacuity: a mechanism that restarted pueued to pick up the
    declaration would return the sleeping task as Killed and reset the pause.
    """
    subprocess.run(["pueue", "group", "add", "pytest", "--parallel", "3"], check=True)
    running = pueue.add(
        group="default",
        label="fixture:running:job-a",
        command=("sleep", "60"),
        working_directory=tmp_path,
    )
    deadline = time.monotonic() + 20
    while pueue.task(running).status != "Running":
        assert time.monotonic() < deadline, "task never started"
        time.sleep(0.1)
    subprocess.run(["pueue", "pause", "--group", "pytest"], check=True)
    queued = pueue.add(
        group="pytest",
        label="fixture:queued:job-b",
        command=("true",),
        working_directory=tmp_path,
    )
    assert _groups(live_pueue)["pytest"]["parallel_tasks"] == 3

    applied = pools.apply({"pytest": 1, "bulk": 1})

    after = _groups(live_pueue)
    assert after["pytest"]["parallel_tasks"] == 1
    assert applied["resized"] == [{"group": "pytest", "from": 3, "to": 1}]
    assert applied["created"] == [{"group": "bulk", "parallel": 1}]
    # The queue is untouched: a paused group stays paused with its task
    # queued, and the task the daemon was running is still running.
    assert after["pytest"]["status"] == "Paused"
    assert pueue.task(queued).status == "Queued"
    assert pueue.task(running).status == "Running"
    # `default` is real and undeclared; the pass reports it and leaves it.
    assert applied["undeclared"] == ["default"]

    pueue.kill(running)


def test_a_matching_daemon_is_left_alone(fake_pueue: FakePueue) -> None:
    """Anti-vacuity: a pass that resized unconditionally would write every run."""
    fake_pueue.groups.clear()
    fake_pueue.groups.update({"pytest": 1, "agent": 8})

    applied = pools.apply({"pytest": 1, "agent": 8})

    assert applied["unchanged"] == ["agent", "pytest"]
    assert applied["resized"] == [] and applied["created"] == []
    assert fake_pueue.resized == []


def test_applying_twice_changes_nothing_the_second_time(fake_pueue: FakePueue) -> None:
    fake_pueue.groups.clear()
    fake_pueue.groups.update({"pytest": 3})

    first = pools.apply({"pytest": 1})
    second = pools.apply({"pytest": 1})

    assert [entry["group"] for entry in first["resized"]] == ["pytest"]
    assert second["resized"] == [] and second["unchanged"] == ["pytest"]
    assert fake_pueue.resized == [("pytest", 3, 1)]


def test_a_daemon_that_is_not_up_yet_is_waited_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The job starts with pueued, whose socket is bound after the unit is active."""
    answers = [
        pools.PueueError("connection refused"),
        pools.PueueError("connection refused"),
        {"pytest": 1},
    ]

    def groups() -> dict[str, int]:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(pools.pueue, "groups", groups)
    monkeypatch.setattr(pools, "_POLL_SECONDS", 0.0)

    assert pools.apply({"pytest": 1})["unchanged"] == ["pytest"]
    assert answers == []


def test_a_daemon_that_never_answers_fails_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def groups() -> dict[str, int]:
        raise pools.PueueError("connection refused")

    monkeypatch.setattr(pools.pueue, "groups", groups)
    monkeypatch.setattr(pools, "_POLL_SECONDS", 0.0)

    with pytest.raises(pools.PueueError):
        pools.apply({"pytest": 1}, wait_seconds=0.0)


def test_the_cli_applies_the_configured_pools(
    fake_pueue: FakePueue, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_pueue.groups.clear()
    fake_pueue.groups.update({"pytest": 3})
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(json.dumps({"pools": {"pytest": 1}}))
    monkeypatch.setenv("AGENTCTL_CONFIG", str(configuration))

    assert cli.main(["pools", "apply", "--json"]) == 0
    assert fake_pueue.groups["pytest"] == 1


def test_a_configuration_declaring_no_pools_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: an empty declaration must not read as `everything matches`."""
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(json.dumps({}))
    monkeypatch.setenv("AGENTCTL_CONFIG", str(configuration))

    assert cli.main(["pools", "apply"]) == cli.EXIT_REFUSED


@pytest.mark.parametrize(
    "declaration",
    [{"pytest": 0}, {"pytest": "1"}, {"pytest": True}, {"Pytest": 1}, {"pytest": -1}],
)
def test_an_invalid_declaration_is_refused(
    declaration: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(json.dumps({"pools": declaration}))
    monkeypatch.setenv("AGENTCTL_CONFIG", str(configuration))

    assert cli.main(["pools", "apply"]) == cli.EXIT_REFUSED
