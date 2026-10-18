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
from agentctl.config import PoolPolicy, load_config
from conftest import FakePueue


def declared(**widths: int) -> dict[str, PoolPolicy]:
    """The declaration as `/etc/sinnix/agentctl.json` parses into it."""
    return {name: PoolPolicy(parallel=parallel) for name, parallel in widths.items()}


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

    applied = pools.apply(declared(pytest=1, bulk=1))

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

    applied = pools.apply(declared(pytest=1, agent=8))

    assert applied["unchanged"] == ["agent", "pytest"]
    assert applied["resized"] == [] and applied["created"] == []
    assert fake_pueue.resized == []


def test_applying_twice_changes_nothing_the_second_time(fake_pueue: FakePueue) -> None:
    fake_pueue.groups.clear()
    fake_pueue.groups.update({"pytest": 3})

    first = pools.apply(declared(pytest=1))
    second = pools.apply(declared(pytest=1))

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

    assert pools.apply(declared(pytest=1))["unchanged"] == ["pytest"]
    assert answers == []


def test_a_daemon_that_never_answers_fails_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def groups() -> dict[str, int]:
        raise pools.PueueError("connection refused")

    monkeypatch.setattr(pools.pueue, "groups", groups)
    monkeypatch.setattr(pools, "_POLL_SECONDS", 0.0)

    with pytest.raises(pools.PueueError):
        pools.apply(declared(pytest=1), wait_seconds=0.0)


def test_the_cli_applies_the_configured_pools(
    fake_pueue: FakePueue, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_pueue.groups.clear()
    fake_pueue.groups.update({"pytest": 3})
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(json.dumps({"pools": {"pytest": {"parallel": 1}}}))
    monkeypatch.setenv("AGENTCTL_CONFIG", str(configuration))

    assert cli.main(["pools", "apply", "--json"]) == 0
    assert fake_pueue.groups["pytest"] == 1


def test_config_preserves_the_declared_heavy_pool_exclusion(tmp_path: Path) -> None:
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(
        json.dumps(
            {
                "pools": {
                    "agent": {"parallel": 12},
                    "pytest-heavy": {
                        "parallel": 1,
                        "exclusive_with": ["agent"],
                    },
                }
            }
        )
    )

    parsed = load_config(configuration)

    assert parsed.pools["pytest-heavy"] == PoolPolicy(
        parallel=1, exclusive_with=("agent",)
    )


def test_config_rejects_an_exclusion_partner_that_is_not_declared(
    tmp_path: Path,
) -> None:
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(
        json.dumps(
            {"pools": {"pytest-heavy": {"parallel": 1, "exclusive_with": ["agent"]}}}
        )
    )

    with pytest.raises(ValueError, match="undeclared pool"):
        load_config(configuration)


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


def test_pool_apply_preserves_adaptive_width(monkeypatch):
    from agentctl.config import AdaptivePool
    changes = []
    monkeypatch.setattr(pueue, "groups", lambda: {"quick": 3})
    monkeypatch.setattr(pueue, "set_parallel", lambda group, count: changes.append((group, count)))
    policy = {"quick": PoolPolicy(8, adaptive=AdaptivePool(1, 1024, "quick.slice"))}
    assert pools.apply(policy)["unchanged"] == ["quick"]
    assert changes == []


def test_adaptive_resize_keeps_live_mixed_jobs_and_operator_pause(live_pueue, tmp_path, monkeypatch):
    from agentctl import backpressure
    from agentctl.config import AdaptivePool
    subprocess.run(["pueue", "group", "add", "quick", "--parallel", "2"], check=True)
    subprocess.run(["pueue", "group", "add", "other", "--parallel", "1"], check=True)
    jobs = [pueue.add(group=group, label="fixture:adaptive:"+group,
                     command=("sleep", "60"), working_directory=tmp_path)
            for group in ["quick", "other"]]
    deadline = time.monotonic() + 20
    while not all(pueue.task(job).status == "Running" for job in jobs):
        assert time.monotonic() < deadline
        time.sleep(0.1)
    monkeypatch.setattr(backpressure, "slice_headroom", lambda unit: 2048)
    policy = {"quick": PoolPolicy(8, adaptive=AdaptivePool(1, 1024, "quick.slice"))}
    spool = tmp_path / "adaptive-events.jsonl"
    for psi, expected in [(0, 3), (11, 2)]:
        result = backpressure.adaptive_widths(policy, pueue.groups_status(),
                   {"memory_full_avg10": psi, "memory_full_avg60": psi}, spool)
        assert result[0]["to"] == expected
        assert pueue.groups()["quick"] == expected
        assert all(pueue.task(job).status == "Running" for job in jobs)
    subprocess.run(["pueue", "pause", "--group", "quick"], check=True)
    deadline = time.monotonic() + 20
    while pueue.task(jobs[0]).status != "Paused":
        assert time.monotonic() < deadline
        time.sleep(0.1)
    before = [pueue.task(job).status for job in jobs]
    assert before == ["Paused", "Running"]
    result = backpressure.adaptive_widths(policy, pueue.groups_status(),
                 {"memory_full_avg10": 0, "memory_full_avg60": 0}, spool)
    assert result[0]["status"] == "not-running"
    assert _groups(live_pueue)["quick"]["status"] == "Paused"
    assert [pueue.task(job).status for job in jobs] == before


@pytest.mark.parametrize("adaptive", [
    {"floor": 9, "job_memory_bytes": 1024, "slice": "quick.slice"},
    {"floor": 1, "job_memory_bytes": True, "slice": "quick.slice"},
    {"floor": 1, "job_memory_bytes": 1024, "slice": "../quick.slice"},
    {},
])
def test_invalid_adaptive_declaration_is_rejected(adaptive):
    from agentctl.config import _pools, ConfigError
    with pytest.raises(ConfigError): _pools({"quick": {"parallel": 8, "adaptive": adaptive}})


def test_project_landing_pool_with_underscore(live_pueue: str, tmp_path: Path) -> None:
    configuration = tmp_path / "agentctl.json"
    configuration.write_text(json.dumps({"pools": {"yt_polisher-land": {"parallel": 1}}}))
    policy = load_config(configuration).pools
    applied = pools.apply(policy)
    assert applied["created"] == [{"group": "yt_polisher-land", "parallel": 1}]
    assert _groups(live_pueue)["yt_polisher-land"]["parallel_tasks"] == 1
