"""Jobs over pueue: the launch input, the label, the artifacts, and the reads."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

import pytest
from conftest import FakePueue, read_launch
from sinnixd import launch
from sinnixd.config import Config
from sinnixd.launch import JobError
from sinnixd.projects import load_project_adapter
from sinnixd.pueue import PueueGroupError
from sinnixd.queue_run import REFUSED_EXIT_CODE, TIMEOUT_EXIT_CODE, scope_unit_for


def test_start_writes_the_launch_input_and_queues_the_wrapper_in_the_pool(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """Breaks if the argv, pool, label or artifact paths stop coming from the descriptor."""
    project = load_project_adapter(project_root)

    started = launch.start_operation(config, project, project.operation("verify"))

    added = fake_pueue.added[0]
    assert added["group"] == "pytest"
    assert added["label"] == "fixture:verify"
    assert added["command"][0] == "sinnixd-queue-run"
    assert added["working_directory"] == project_root
    input_path = Path(added["command"][1])
    assert input_path.stat().st_mode & 0o777 == 0o600
    written = json.loads(input_path.read_text())
    assert written["argv"] == ["env", "fixture-verify"]
    assert written["timeout_seconds"] == 120
    assert written["pool"] == "pytest"
    assert launch.scope_unit(fake_pueue.task(1)) == scope_unit_for(
        input_path, "pytest"
    )
    assert written["result_kind"] == "json"
    assert written["result_path"].endswith(".result")
    assert written["event_spool_path"] == str(config.event_spool)
    assert "PATH" in written["environment"]
    assert started["job_id"] == 1
    assert started["phase"] == "running"
    assert started["project"] == "fixture"
    assert started["operation"] == "verify"
    assert started["kind"] == "declared-operation"


def test_operation_started_by_an_agent_preserves_its_routing_principal(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SINNIXD_PRINCIPAL", "agent-control")
    monkeypatch.setenv("SINNIXD_LANE_BEAD", "fx-1")
    project = load_project_adapter(project_root)

    started = launch.start_operation(config, project, project.operation("check"))

    written = read_launch(config, fake_pueue.task(started["job_id"]))
    assert written["environment"]["SINNIXD_PRINCIPAL"] == "agent-control"
    assert written["environment"]["SINNIXD_LANE_BEAD"] == "fx-1"


def test_extra_argv_is_appended_after_the_declared_exec(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)

    started = launch.start_operation(
        config, project, project.operation("check"), extra_argv=("--apply",)
    )

    written = read_launch(config, fake_pueue.task(started["job_id"]))
    assert written["argv"] == ["env", "true", "--apply"]


def test_cached_operation_reuses_an_active_and_completed_exact_receipt(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            '[operations.verify]\ndescription = "Fixture typed verification"',
            '[operations.verify]\ndescription = "Fixture typed verification"\ncache = "tree+environment"',
        )
    )
    monkeypatch.setattr(
        launch,
        "_git",
        lambda path, *arguments: {
            ("rev-parse", "HEAD"): "a" * 40,
            ("rev-parse", "HEAD^{tree}"): "b" * 40,
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
        }[arguments],
    )
    project = load_project_adapter(project_root)

    first = launch.start_operation(config, project, project.operation("verify"))
    second = launch.start_operation(config, project, project.operation("verify"))
    fake_pueue.succeed(first["job_id"])
    third = launch.start_operation(config, project, project.operation("verify"))

    assert len(fake_pueue.added) == 1
    assert second["job_id"] == first["job_id"]
    assert third["job_id"] == first["job_id"]
    assert second["reused"] is True and third["reused"] is True
    written = read_launch(config, fake_pueue.task(first["job_id"]))
    assert written["tree_receipt"] == {
        "head": "a" * 40,
        "tree": "b" * 40,
        "dirty": False,
    }
    assert written["environment_receipt"]["digest"].startswith("sha256:")


def test_operation_dependencies_are_pueue_edges(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
) -> None:
    descriptor = project_root / ".agentctl" / "project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exec = ["fixture-verify"]\npool = "pytest"',
            'exec = ["fixture-verify"]\npool = "pytest"\ndependencies = ["check"]',
        )
    )
    project = load_project_adapter(project_root)

    started = launch.start_operation(config, project, project.operation("verify"))

    assert started["job_id"] == 2
    assert [item["label"] for item in fake_pueue.added] == [
        "fixture:check",
        "fixture:verify",
    ]
    assert fake_pueue.added[1]["after"] == (1,)


def test_a_default_checkout_operation_refuses_a_worktree(
    fake_pueue: FakePueue, config: Config, project_root: Path, tmp_path: Path
) -> None:
    """The corpus run belongs to the master boundary; a lane cannot start it."""
    project = load_project_adapter(project_root)
    worktree = tmp_path / "worktrees" / "fixture-lane"
    worktree.mkdir(parents=True)

    with pytest.raises(JobError, match="main checkout"):
        launch.start_operation(
            config, project, project.operation("nightly"), workspace=worktree
        )
    assert fake_pueue.added == []


def test_an_unknown_pool_is_a_typed_refusal_and_leaves_no_input_behind(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    fake_pueue.groups.pop("pytest")

    with pytest.raises(PueueGroupError):
        launch.start_operation(config, project, project.operation("verify"))

    assert list(config.inputs_dir.glob("*")) == []


def test_fire_skips_while_the_same_operation_is_active(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """A timer firing into a still-running corpus must not stack a second one."""
    project = load_project_adapter(project_root)
    operation = project.operation("nightly")

    first = launch.fire(config, project, operation)
    second = launch.fire(config, project, operation)
    fake_pueue.succeed(first["job_id"])
    third = launch.fire(config, project, operation)

    assert first["fired"] is True
    assert second == {"fired": False, "label": "fixture:nightly", "active": [1]}
    assert third["fired"] is True and third["job_id"] == 2


def test_fire_refuses_an_operation_without_a_schedule(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    with pytest.raises(JobError, match="declares no schedule"):
        launch.fire(config, project, project.operation("check"))


def test_phases_come_from_pueue_results_and_the_wrapper_exit_codes(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    ids = [
        launch.start_operation(config, project, project.operation("check"))["job_id"]
        for _ in range(6)
    ]
    fake_pueue.succeed(ids[0])
    fake_pueue.fail(ids[1], exit_code=3)
    fake_pueue.fail(ids[2], exit_code=TIMEOUT_EXIT_CODE)
    fake_pueue.fail(ids[3], exit_code=REFUSED_EXIT_CODE)
    fake_pueue.kill_directly(ids[4])
    fake_pueue.queue(ids[5])

    phases = [launch.get_job(task_id)["phase"] for task_id in ids]

    assert phases == [
        "succeeded",
        "failed",
        "timed-out",
        "refused",
        "cancelled",
        "queued",
    ]


def test_logs_and_result_are_read_by_the_reference_in_the_task_command(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """No ledger maps task ids to artifacts; the task's own command line does."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("verify"))
    written = read_launch(config, fake_pueue.task(started["job_id"]))
    Path(written["log_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(written["log_path"]).write_text("ran\n")
    Path(written["result_path"]).write_text('{"passed": 3}')
    fake_pueue.set_log(started["job_id"], "wrapper stderr")
    fake_pueue.succeed(started["job_id"])

    assert "ran" in launch.logs(config, started["job_id"])
    assert "wrapper stderr" in launch.logs(config, started["job_id"])
    outcome = launch.result(config, started["job_id"])
    assert outcome["kind"] == "artifact"
    assert outcome["value"] == {"passed": 3}
    assert outcome["phase"] == "succeeded"


def test_result_of_an_exit_operation_is_the_status_alone(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.succeed(started["job_id"])

    outcome = launch.result(config, started["job_id"])

    assert outcome["kind"] == "exit" and outcome["value"] is None
    assert outcome["exit_code"] == 0


def test_cancel_kills_the_task_then_stops_the_scope_that_held_its_workload(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    recording_systemctl: Callable[[], list[list[str]]],
) -> None:
    """pueue's SIGKILL cannot be caught, so the workload is reaped from outside.

    That the reap really ends the tree is proven against a live daemon in
    test_pueue.py; this is the wiring, including the scope named before the
    kill removes the command that names it.
    """
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    unit = launch.scope_unit(fake_pueue.task(started["job_id"]))

    cancelled = launch.cancel(config, started["job_id"])

    assert fake_pueue.killed == [started["job_id"]]
    assert ["systemctl", "--user", "stop", unit] in recording_systemctl()
    assert cancelled["cancelled"] == "killed"
    assert cancelled["phase"] == "cancelled"


def test_cancelling_a_queued_task_drops_it_out_of_the_queue(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    """A task that never started has no process, and pueue refuses to kill it.

    Anti-vacuity: the refusal leaves the task queued, so a cancel that only
    kills reports failure and the task runs a minute later regardless.
    """
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.queue(started["job_id"])

    cancelled = launch.cancel(config, started["job_id"])

    assert fake_pueue.removed == [started["job_id"]]
    assert fake_pueue.task(started["job_id"]) is None
    assert cancelled["cancelled"] == "dropped"
    assert cancelled["phase"] == "cancelled" and cancelled["terminal"] is True


def test_a_task_whose_launch_input_agentctl_did_not_write_names_its_own_scope(
    fake_pueue: FakePueue,
    config: Config,
    tmp_path: Path,
    recording_systemctl: Callable[[], list[list[str]]],
) -> None:
    """A repository may queue the wrapper with its own launch input.

    Anti-vacuity: such an input sits in that checkout, not under the state
    directory, and a reap that looks only there reaches nothing at all.
    """
    foreign = tmp_path / "checkout" / ".cache" / "verify" / "pytest-slot-42.json"
    foreign.parent.mkdir(parents=True)
    foreign.write_text(json.dumps({"log_path": str(foreign.parent / "slot.log")}))
    task_id = fake_pueue.add(
        group="pytest",
        label="polylogue:test:42",
        command=("/run/current-system/sw/bin/sinnixd-queue-run", str(foreign)),
        working_directory=tmp_path / "checkout",
    )

    cancelled = launch.cancel(config, task_id)

    unit = scope_unit_for(foreign, "pytest")
    assert ["systemctl", "--user", "stop", unit] in recording_systemctl()
    assert cancelled["reaped"]["scope"]["unit"] == unit


def test_a_command_that_only_mentions_the_wrapper_owns_no_scope_and_no_artifacts(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    tmp_path: Path,
    recording_systemctl: Callable[[], list[list[str]]],
) -> None:
    """Ownership is what a task runs, not what its command line contains.

    Anti-vacuity: this command carries the wrapper's name and a real launch
    input path, so reading the command as text hands an unrelated task another
    task's scope to stop and another task's log to print.
    """
    project = load_project_adapter(project_root)
    victim = launch.start_operation(config, project, project.operation("check"))
    borrowed = launch.launch_input_path(fake_pueue.task(victim["job_id"]))
    task_id = fake_pueue.add(
        group="pytest",
        label="other:report:1",
        command=("sh", "-c", f"echo sinnixd-queue-run {borrowed}"),
        working_directory=tmp_path,
    )
    task = fake_pueue.task(task_id)

    assert launch.launch_input_path(task) is None
    assert launch.scope_unit(task) is None
    cancelled = launch.cancel(config, task_id)

    assert cancelled["reaped"]["scope"] == {
        "unit": None,
        "stopped": False,
        "survivors": [],
    }
    assert [call for call in recording_systemctl() if "stop" in call] == []


def test_an_artifact_outside_the_task_own_directories_is_not_published(
    fake_pueue: FakePueue, config: Config, tmp_path: Path
) -> None:
    """A launch input names its own artifact paths, and only its own.

    Anti-vacuity: `job logs` prints what the input declares, so an input naming
    a file in another tree publishes that file to whoever asks for the log.
    """
    private = tmp_path / "elsewhere" / "credentials"
    private.parent.mkdir(parents=True)
    private.write_text("secret material")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    outside = checkout / "outside.json"
    outside.write_text(json.dumps({"log_path": str(private)}))
    reachable = checkout / "reachable.json"
    reachable.write_text(json.dumps({"log_path": str(checkout / "own.log")}))
    (checkout / "own.log").write_text("this task's own output\n")

    tasks = {
        name: fake_pueue.add(
            group="pytest",
            label=f"polylogue:test:{name}",
            command=("sinnixd-queue-run", str(path)),
            working_directory=checkout,
        )
        for name, path in (("outside", outside), ("reachable", reachable))
    }
    for task_id in tasks.values():
        fake_pueue.set_log(task_id, "wrapper stderr")

    assert launch.logs(config, tasks["outside"]) == "wrapper stderr"
    assert "secret material" not in launch.logs(config, tasks["outside"])
    # The same rule must publish the artifacts a task really does own.
    assert "this task's own output" in launch.logs(config, tasks["reachable"])


def test_an_artifact_that_is_not_a_regular_file_is_refused_without_blocking(
    tmp_path: Path,
) -> None:
    """A read bounded by the caller, on a file that cannot block it.

    Anti-vacuity: opening a fifo with no writer blocks until one appears, and
    reading a whole file to slice it afterwards is bounded by nothing.
    """
    fifo = tmp_path / "log"
    os.mkfifo(fifo)
    regular = tmp_path / "regular"
    regular.write_bytes(b"x" * 4096)

    assert launch.read_bounded(fifo, 64) is None
    assert launch.read_bounded(tmp_path, 64) is None
    assert launch.read_bounded(tmp_path / "absent", 64) is None
    assert launch.read_bounded(regular, 64) == b"x" * 64


def test_retry_is_pueue_restart_and_only_for_terminal_tasks(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))

    with pytest.raises(JobError, match="still running"):
        launch.retry(started["job_id"])
    fake_pueue.fail(started["job_id"], exit_code=1)
    retried = launch.retry(started["job_id"])

    assert fake_pueue.restarted == [started["job_id"]]
    assert retried["phase"] == "queued"


def test_wait_returns_the_terminal_view_and_reports_a_timeout_as_such(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    fake_pueue.finish_when_waited(started["job_id"], lambda fake: fake.succeed(1))

    waited = launch.wait(started["job_id"], timeout_seconds=5)
    assert waited["phase"] == "succeeded"

    second = launch.start_operation(config, project, project.operation("check"))
    timed_out = launch.wait(second["job_id"], timeout_seconds=1)
    assert timed_out["wait_timed_out"] is True
    assert timed_out["phase"] == "running"


def test_list_filters_by_project_prefix(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)
    launch.start_operation(config, project, project.operation("check"))
    fake_pueue.add(
        group="normal",
        label="other:check",
        command=("true",),
        working_directory=project_root,
    )

    assert [row["label"] for row in launch.list_jobs("fixture")] == ["fixture:check"]
    assert len(launch.list_jobs()) == 2
