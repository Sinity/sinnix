"""Jobs over pueue: the launch input, the label, the artifacts, and the reads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import FakePueue, read_launch
from sinnixd import launch
from sinnixd.config import Config
from sinnixd.launch import JobError
from sinnixd.projects import load_project_adapter
from sinnixd.pueue import PueueGroupError
from sinnixd.queue_run import REFUSED_EXIT_CODE, TIMEOUT_EXIT_CODE


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
    assert written["result_kind"] == "json"
    assert written["result_path"].endswith(".result")
    assert written["event_spool_path"] == str(config.event_spool)
    assert "PATH" in written["environment"]
    assert started["job_id"] == 1
    assert started["phase"] == "running"
    assert started["project"] == "fixture"
    assert started["operation"] == "verify"
    assert started["kind"] == "declared-operation"


def test_extra_argv_is_appended_after_the_declared_exec(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    project = load_project_adapter(project_root)

    started = launch.start_operation(
        config, project, project.operation("check"), extra_argv=("--apply",)
    )

    written = read_launch(config, fake_pueue.task(started["job_id"]))
    assert written["argv"] == ["env", "true", "--apply"]


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

    assert phases == ["succeeded", "failed", "timed-out", "refused", "cancelled", "queued"]


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


def test_cancel_kills_the_task_and_signals_the_recorded_process_group(
    fake_pueue: FakePueue, config: Config, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pueue's SIGKILL cannot be caught; the wrapper's recorded group is what gets reaped."""
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    written = read_launch(config, fake_pueue.task(started["job_id"]))
    group_path = Path(written["log_path"] + ".pgid")
    group_path.parent.mkdir(parents=True, exist_ok=True)
    group_path.write_text("424242")
    signalled: list[tuple[int, int]] = []
    monkeypatch.setattr(launch.os, "killpg", lambda pgid, sig: signalled.append((pgid, sig)))

    cancelled = launch.cancel(config, started["job_id"])

    assert fake_pueue.killed == [started["job_id"]]
    assert signalled == [(424242, launch.signal.SIGTERM)]
    assert cancelled["phase"] == "cancelled"


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
        group="normal", label="other:check", command=("true",), working_directory=project_root
    )

    assert [row["label"] for row in launch.list_jobs("fixture")] == ["fixture:check"]
    assert len(launch.list_jobs()) == 2
