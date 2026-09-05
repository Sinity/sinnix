from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

import pytest
from agentctl import queue_run
from agentctl.queue_run import (
    MAX_LOG_BYTES,
    REFUSED_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    cgroup_processes,
    main,
    scope_control_group,
    scope_unit_for,
)


def user_scopes(monkeypatch: pytest.MonkeyPatch, pool: str) -> dict[str, str]:
    """Run this test's workload in a real transient scope, or skip.

    Returns the launch environment: `systemd-run` is started with the declared
    environment and nothing else, so the user manager's socket has to be in it.
    """
    runtime = Path(f"/run/user/{os.getuid()}")
    if not (runtime / "bus").exists():
        pytest.skip("no user systemd bus is available")
    monkeypatch.setenv("PUEUE_GROUP", pool)
    return {"PATH": os.environ["PATH"], "XDG_RUNTIME_DIR": str(runtime)}


def write_launch(tmp_path: Path, **overrides: Any) -> Path:
    launch: dict[str, Any] = {
        "job_id": "job-a",
        "project_id": "fixture",
        "operation": "check",
        "argv": ["true"],
        "environment": {"PATH": os.environ["PATH"]},
        "working_directory": str(tmp_path),
        "timeout_seconds": 30,
        "result_kind": "exit",
        "label": "fixture:check:job-a",
        "log_path": str(tmp_path / "log"),
        "event_spool_path": str(tmp_path / "events.jsonl"),
    }
    launch.update(overrides)
    path = tmp_path / "launch.json"
    path.write_text(json.dumps(launch))
    return path


def events(tmp_path: Path) -> list[dict[str, Any]]:
    spool = tmp_path / "events.jsonl"
    if not spool.exists():
        return []
    return [json.loads(line) for line in spool.read_text().splitlines()]


def test_a_successful_command_spools_its_start_and_reports_its_status(
    tmp_path: Path,
) -> None:
    launch = write_launch(
        tmp_path, argv=["sh", "-c", "echo out; echo err >&2"], result_kind="exit"
    )

    assert main([str(launch)]) == 0

    log = (tmp_path / "log").read_text()
    assert "out" in log and "err" in log
    started = events(tmp_path)
    assert [event["phase"] for event in started] == ["started"]
    # The callback spools `queue-task` finish events; the start must carry the
    # same kind or a lane's timeline shows only its endings.
    assert started[0]["kind"] == "queue-task"
    assert started[0]["job_id"] == "job-a"
    assert started[0]["label"] == "fixture:check:job-a"


def test_worker_exports_queue_identity_to_the_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    runner = fake_bin / "systemd-run"
    runner.write_text(
        '#!/bin/sh\nwhile [ "$1" != "--" ]; do shift; done\nshift\nexec "$@"\n'
    )
    runner.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    launch = write_launch(
        tmp_path,
        argv=[
            "sh",
            "-c",
            'printf \'%s %s %s %s\' "$AGENTCTL_JOB_ID" "$AGENTCTL_PROJECT_ID" "$AGENTCTL_OPERATION" "$AGENTCTL_POOL"',
        ],
        pool="pytest",
    )

    assert main([str(launch)]) == 0
    assert (tmp_path / "log").read_text() == "job-a fixture check pytest"


@pytest.fixture
def recording_systemd_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[], list[str]]:
    """A systemd-run on PATH that records its argv and then runs the command."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    recorder = tmp_path / "systemd-run-argv"
    runner = fake_bin / "systemd-run"
    runner.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > {recorder}\n"
        'while [ "$1" != "--" ]; do shift; done\n'
        "shift\n"
        'exec "$@"\n'
    )
    runner.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    return lambda: recorder.read_text().splitlines() if recorder.exists() else []


def test_a_declared_pool_runs_the_child_in_its_named_systemd_scope(
    tmp_path: Path, recording_systemd_run: Callable[[], list[str]]
) -> None:
    """Breaks if a queued workload executes beside the queue runner again.

    The scope is named for the launch input, not for a field inside it, because
    that name is what a canceller can rebuild from `pueue status` alone.
    """
    launch = write_launch(
        tmp_path,
        pool="pytest",
        argv=[
            "sh",
            "-c",
            'printf "%s %s" "$AGENTCTL_QUEUE_WORKER" "$AGENTCTL_JOB_ID"',
        ],
    )

    assert main([str(launch)]) == 0

    scope_argv = recording_systemd_run()
    assert "--scope" in scope_argv
    assert "--collect" in scope_argv
    assert f"--unit={scope_unit_for(launch, 'pytest')}" in scope_argv
    assert "--slice=agentctl-pytest.slice" in scope_argv
    assert (tmp_path / "log").read_text() == "1 job-a"


def test_a_launch_input_without_a_pool_is_contained_by_its_pueue_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recording_systemd_run: Callable[[], list[str]],
) -> None:
    """A repository queueing the wrapper itself still gets a cgroup.

    Anti-vacuity: a workload with no scope inherits pueued.service's own
    cgroup, where a cancel has nothing to stop.
    """
    monkeypatch.setenv("PUEUE_GROUP", "pytest")
    launch = write_launch(tmp_path)
    assert "pool" not in json.loads(launch.read_text())

    assert main([str(launch)]) == 0

    assert f"--unit={scope_unit_for(launch, 'pytest')}" in recording_systemd_run()


def test_the_start_event_records_the_group_the_task_actually_ran_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recording_systemd_run: Callable[[], list[str]],
) -> None:
    """The pool a reader sees must be the one bounding the run.

    Anti-vacuity: pueued admits by its own group, so a launch input declaring
    another names the containment nowhere near the event that reports it.
    """
    monkeypatch.setenv("PUEUE_GROUP", "bulk")
    launch = write_launch(tmp_path, pool="pytest")

    assert main([str(launch)]) == 0

    assert [event["pool"] for event in events(tmp_path)] == ["bulk"]
    assert "--slice=agentctl-bulk.slice" in recording_systemd_run()


def test_scopes_stay_distinct_when_their_launch_inputs_share_a_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two checkouts name their launch inputs alike; one cancel must not reach both.

    Anti-vacuity: a name built from the basename alone, or truncated to fit a
    unit name, collides exactly here — and a colliding scope is another task's
    workload killed by a cancel that was never asked to touch it.
    """
    stem = "pytest-slot-4242"
    long_stem = "x" * 400
    units = {
        scope_unit_for(f"/realm/worktrees/{name}/.cache/verify/{stem}.json", "pytest")
        for name in ("checkout-a", "checkout-b")
    } | {
        scope_unit_for(f"/inputs/{long_stem}{suffix}.json", "pytest")
        for suffix in ("-one", "-two")
    }

    assert len(units) == 4
    assert all(unit.startswith("agentctl-pytest-") for unit in units)
    assert all(len(unit) < 256 for unit in units)


def test_a_scope_is_stopped_by_killing_its_cgroup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kill names a cgroup, never the pids read out of one.

    Anti-vacuity: signalling pids one by one races a descendant forking while
    the walk runs, and races the kernel handing a pid the walk already read to
    an unrelated process.
    """
    control_group = tmp_path / "scope-cgroup"
    control_group.mkdir()
    (control_group / "cgroup.kill").write_text("")
    (control_group / "cgroup.procs").write_text("")
    monkeypatch.setattr(queue_run, "scope_control_group", lambda unit: control_group)
    monkeypatch.setattr(queue_run.subprocess, "run", lambda *a, **k: None)

    reaped = queue_run.stop_scope("agentctl-fixture-job-0123456789ab.scope")

    assert (control_group / "cgroup.kill").read_text() == "1"
    assert reaped["stopped"] and reaped["survivors"] == []


def test_scope_properties_bound_the_task_scope_itself(
    tmp_path: Path, recording_systemd_run: Callable[[], list[str]]
) -> None:
    """A lane's memory ceiling belongs to the scope cancel can stop.

    Anti-vacuity: set on a scope of the workload's own making, the ceiling would
    hold, but the cancel that stops this unit would not reach it.
    """
    launch = write_launch(
        tmp_path, pool="agent", scope_properties=["MemoryMax=10G"], argv=["true"]
    )

    assert main([str(launch)]) == 0

    scope_argv = recording_systemd_run()
    assert scope_argv[scope_argv.index("MemoryMax=10G") - 1] == "-p"
    assert scope_argv.index("MemoryMax=10G") < scope_argv.index("--")


@pytest.mark.parametrize(
    "setting",
    [
        "--property=Delegate=yes",
        # A well-formed systemd setting that grants rather than bounds: the
        # scope is the workload's own containment, not a second launcher.
        "ExecStartPost=/bin/sh -c evil",
        "User=root",
        "Delegate=yes",
        "MemoryMax=; rm -rf /",
    ],
)
def test_a_scope_property_that_does_not_bound_the_task_is_refused(
    tmp_path: Path, setting: str
) -> None:
    """A launch input may lower what its own task consumes, and nothing else."""
    launch = write_launch(tmp_path, scope_properties=[setting])

    assert main([str(launch)]) == REFUSED_EXIT_CODE


def test_a_failing_command_reports_its_own_exit_status(tmp_path: Path) -> None:
    launch = write_launch(tmp_path, argv=["sh", "-c", "exit 3"])

    assert main([str(launch)]) == 3


def test_a_typed_result_is_stdout_alone_and_the_log_keeps_the_diagnostics(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: merging stderr into the artifact corrupts every JSON receipt."""
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", "echo warming up >&2; printf '{\"passed\": 4}'"],
        result_kind="json",
        result_path=str(tmp_path / "result.json"),
    )

    assert main([str(launch)]) == 0

    assert json.loads((tmp_path / "result.json").read_text()) == {"passed": 4}
    assert "warming up" in (tmp_path / "log").read_text()


def test_the_declared_timeout_is_enforced_because_pueue_has_none(
    tmp_path: Path,
) -> None:
    launch = write_launch(tmp_path, argv=["sleep", "30"], timeout_seconds=1)

    assert main([str(launch)]) == TIMEOUT_EXIT_CODE

    assert "timed out after 1 seconds" in (tmp_path / "log").read_text()


def test_a_timed_out_command_leaves_no_survivors(tmp_path: Path) -> None:
    """The command is killed as a process group; a child must not outlive it."""
    marker = tmp_path / "still-running"
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", f"(sleep 30; touch {marker}) & sleep 30"],
        timeout_seconds=1,
    )

    assert main([str(launch)]) == TIMEOUT_EXIT_CODE

    assert subprocess.run(["sleep", "3"], check=False).returncode == 0
    assert not marker.exists()


def test_an_oversized_log_is_truncated_with_a_marker(tmp_path: Path) -> None:
    launch = write_launch(
        tmp_path, argv=["sh", "-c", f"yes x | head -c {MAX_LOG_BYTES * 3}"]
    )

    assert main([str(launch)]) == 0

    log = (tmp_path / "log").read_text()
    assert len(log) <= MAX_LOG_BYTES
    assert log.endswith("[agentctl: output truncated]\n")


def test_the_environment_is_exactly_what_the_descriptor_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: inheriting the queue's environment would leak the daemon's."""
    monkeypatch.setenv("MUST_NOT_INHERIT", "leaked")
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", "env"],
        environment={"PATH": os.environ["PATH"], "DECLARED": "yes"},
    )

    assert main([str(launch)]) == 0

    log = (tmp_path / "log").read_text()
    assert "DECLARED=yes" in log
    assert "MUST_NOT_INHERIT" not in log


def test_a_command_that_cannot_start_is_a_refusal_not_a_crash(tmp_path: Path) -> None:
    launch = write_launch(tmp_path, argv=["definitely-not-a-command"])

    assert main([str(launch)]) == REFUSED_EXIT_CODE

    assert "could not start" in (tmp_path / "log").read_text()


@pytest.mark.parametrize(
    "overrides",
    (
        {"argv": []},
        {"argv": "true"},
        {"timeout_seconds": 0},
        {"timeout_seconds": True},
        {"result_kind": "invented"},
        {"environment": {"PATH": 3}},
    ),
)
def test_a_malformed_launch_input_refuses_before_running_anything(
    tmp_path: Path, overrides: dict[str, Any]
) -> None:
    launch = write_launch(tmp_path, **overrides)

    assert main([str(launch)]) == REFUSED_EXIT_CODE

    assert not (tmp_path / "log").exists()
    assert events(tmp_path) == []


def test_an_absent_launch_input_refuses(tmp_path: Path) -> None:
    assert main([str(tmp_path / "absent.json")]) == REFUSED_EXIT_CODE


def test_a_vanished_working_directory_refuses_before_running(tmp_path: Path) -> None:
    """A lane worktree removed between add and exec must not run in a cwd guess."""
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", "echo ran > ran"],
        working_directory=str(tmp_path / "gone"),
    )

    assert main([str(launch)]) == REFUSED_EXIT_CODE

    assert "working directory is gone" in (tmp_path / "log").read_text()
    assert not (tmp_path / "ran").exists()


def test_the_launch_input_survives_for_a_restart(tmp_path: Path) -> None:
    """`pueue restart` re-runs the same command line; it needs the same input."""
    launch = write_launch(tmp_path)

    assert main([str(launch)]) == 0
    assert launch.exists()
    assert main([str(launch)]) == 0


def test_the_wrapper_returns_only_once_its_scope_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A queued task is over when its cgroup is, not when its leader exits.

    Anti-vacuity: `systemd-run --scope` execs the workload, so the wait ends
    with the leader while a descendant that left its session runs on. Returning
    there reports the task terminal to pueue, which admits the next task into a
    group whose worker is still occupied.
    """
    environment = user_scopes(monkeypatch, "fixture")
    marker = tmp_path / "finished-after-the-leader"
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", f"setsid sh -c 'sleep 2; touch {marker}' & exit 0"],
        environment=environment,
        timeout_seconds=60,
    )

    assert main([str(launch)]) == 0

    assert marker.exists(), "the wrapper returned while its scope still ran"
    assert "left in the task scope" not in (tmp_path / "log").read_text()


def test_a_descendant_that_will_not_exit_is_killed_with_the_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Waiting out a leaked process would hold the group's worker indefinitely.

    Anti-vacuity: the sleeper outlives the grace, so only the kill ends it, and
    nothing is left in the scope when the wrapper returns.
    """
    environment = user_scopes(monkeypatch, "fixture")
    monkeypatch.setattr(queue_run, "REAP_GRACE_SECONDS", 0.5)
    started = tmp_path / "descendant-started"
    launch = write_launch(
        tmp_path,
        argv=[
            "sh",
            "-c",
            f"setsid sh -c 'touch {started}; sleep 300' & "
            f"while [ ! -e {started} ]; do sleep 0.05; done; exit 0",
        ],
        environment=environment,
        timeout_seconds=60,
    )

    assert main([str(launch)]) == 0

    reported = [
        line
        for line in (tmp_path / "log").read_text().splitlines()
        if line.startswith("killed what the command left in its scope")
    ]
    killed = [int(pid) for pid in re.findall(r"[0-9]+", "".join(reported))]
    assert killed, "the leaked descendant was neither waited out nor killed"
    assert not any(Path(f"/proc/{pid}").exists() for pid in killed)
    assert (
        cgroup_processes(scope_control_group(scope_unit_for(launch, "fixture"))) == []
    )
