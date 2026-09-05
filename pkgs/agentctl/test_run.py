from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from agentctl import pueue
from agentctl.run import (
    CANCELLED_EXIT_CODE,
    MAX_LOG_BYTES,
    REFUSED_EXIT_CODE,
    SLOT_OCCUPIED_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    VANISHED_EXIT_CODE,
    cancel_marker_for,
    main,
    outcome_path_for,
    unit_description,
    unit_for,
)
from conftest import FakePueue


def user_manager() -> None:
    """Skip unless this test can start a real transient service."""
    if not Path(f"/run/user/{os.getuid()}/bus").exists():
        pytest.skip("no user systemd bus is available")


def write_launch(tmp_path: Path, name: str = "launch.json", **overrides: Any) -> Path:
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
        "log_path": str(tmp_path / "job-a.log"),
        "event_spool_path": str(tmp_path / "events.jsonl"),
    }
    launch.update(overrides)
    path = tmp_path / name
    path.write_text(json.dumps(launch))
    return path


def events(tmp_path: Path) -> list[dict[str, Any]]:
    spool = tmp_path / "events.jsonl"
    if not spool.exists():
        return []
    return [json.loads(line) for line in spool.read_text().splitlines()]


def log_of(tmp_path: Path) -> str:
    return (tmp_path / "job-a.log").read_text()


def outcome_of(tmp_path: Path) -> dict[str, Any]:
    return json.loads(outcome_path_for(tmp_path / "job-a.log").read_text())


def described(pool: str, task: object) -> str:
    return unit_description(pueue.daemon_tag(), pool, str(task))


@dataclass
class FakeSystemd:
    """`systemd-run` and `systemctl` on PATH, driven by files the test writes.

    The runner exports every `--setenv`, honours the stdout/stderr properties
    and execs the command; `systemctl show` prints `show.out`, `list-units`
    prints `units.out`, and every call lands in the ledger.
    """

    root: Path

    @property
    def show(self) -> Path:
        return self.root / "show.out"

    @property
    def units(self) -> Path:
        return self.root / "units.out"

    def run_argv(self) -> list[str]:
        recorder = self.root / "systemd-run-argv"
        return recorder.read_text().splitlines() if recorder.exists() else []

    def systemctl_calls(self) -> list[list[str]]:
        ledger = self.root / "systemctl-calls"
        if not ledger.exists():
            return []
        return [line.split() for line in ledger.read_text().splitlines()]

    def active(self, *units: tuple[str, str | None]) -> None:
        """Units `list-units` reports running, each with its Description."""
        self.units.write_text(
            "".join(
                f"{unit} loaded active running {description or ''}\n"
                for unit, description in units
            )
        )

    def terminal(self, **properties: str) -> None:
        shown = {
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "Result": "success",
            "ExecMainStatus": "0",
            "ExecMainCode": "exited",
            **properties,
        }
        self.show.write_text("".join(f"{k}={v}\n" for k, v in shown.items()))


@pytest.fixture
def fake_systemd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeSystemd:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    fake = FakeSystemd(tmp_path)
    fake.terminal()
    fake.units.write_text("")
    runner = fake_bin / "systemd-run"
    runner.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > {tmp_path / 'systemd-run-argv'}\n"
        "out=/dev/stdout; err=/dev/stderr\n"
        'while [ "$1" != "--" ]; do\n'
        '  case "$1" in\n'
        '    --setenv=*) export "${1#--setenv=}" ;;\n'
        '    -p) shift; case "$1" in\n'
        '      StandardOutput=*) out="${1#*:}" ;;\n'
        '      StandardError=*) err="${1#*:}" ;;\n'
        "    esac ;;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "shift\n"
        'exec "$@" >>"$out" 2>>"$err"\n'
    )
    runner.chmod(0o755)
    systemctl = fake_bin / "systemctl"
    systemctl.write_text(
        "#!/bin/sh\n"
        f"printf 'systemctl %s\\n' \"$*\" >> {tmp_path / 'systemctl-calls'}\n"
        'case "$*" in\n'
        f"  *show*) cat {fake.show} ;;\n"
        f"  *list-units*) cat {fake.units} ;;\n"
        "esac\n"
    )
    systemctl.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    return fake


def test_a_successful_command_spools_its_start_and_finish(tmp_path: Path) -> None:
    launch = write_launch(tmp_path, argv=["sh", "-c", "echo out; echo err >&2"])

    assert main([str(launch)]) == 0

    assert "out" in log_of(tmp_path) and "err" in log_of(tmp_path)
    spooled = events(tmp_path)
    assert [event["phase"] for event in spooled] == ["started", "finished"]
    # The callback spools `queue-task` finish events; the start must carry the
    # same kind or a lane's timeline shows only its endings.
    assert {event["kind"] for event in spooled} == {"queue-task"}
    assert spooled[0]["job_id"] == "job-a"
    assert spooled[1]["outcome"] == "success"
    assert outcome_of(tmp_path)["outcome"] == "success"


def test_worker_exports_queue_identity_to_the_child(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
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
    assert log_of(tmp_path) == "job-a fixture check pytest"


def test_a_declared_pool_runs_the_child_as_a_service_that_exits_with_its_cgroup(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """The unit is named for the launch input, so a canceller rebuilds it from
    `pueue status` alone; it ends with its cgroup, so the wait does too."""
    launch = write_launch(
        tmp_path,
        pool="pytest",
        argv=["sh", "-c", 'printf "%s" "$AGENTCTL_QUEUE_WORKER"'],
    )

    assert main([str(launch)]) == 0

    argv = fake_systemd.run_argv()
    unit = unit_for(launch, "pytest")
    assert unit.endswith(".service")
    assert f"--unit={unit}" in argv
    assert "--slice=agentctl-pytest.slice" in argv
    assert "--wait" in argv and "--collect" not in argv
    for setting in (
        "ExitType=cgroup",
        "KillMode=control-group",
        "IOAccounting=yes",
        "RuntimeMaxSec=30",
        f"StandardOutput=append:{tmp_path / 'job-a.log'}",
        f"StandardError=append:{tmp_path / 'job-a.log'}",
    ):
        assert argv[argv.index(setting) - 1] == "-p"
    assert log_of(tmp_path) == "1"
    assert [
        "systemctl",
        "--user",
        "reset-failed",
        unit,
    ] in fake_systemd.systemctl_calls()


def test_a_launch_input_without_a_pool_is_contained_by_its_pueue_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_systemd: FakeSystemd,
    fake_pueue: FakePueue,
) -> None:
    """A repository queueing the wrapper itself still gets a cgroup."""
    monkeypatch.setenv("PUEUE_GROUP", "pytest")
    launch = write_launch(tmp_path)
    assert "pool" not in json.loads(launch.read_text())

    assert main([str(launch)]) == 0

    assert f"--unit={unit_for(launch, 'pytest')}" in fake_systemd.run_argv()


def test_the_start_event_records_the_group_the_task_actually_ran_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_systemd: FakeSystemd,
    fake_pueue: FakePueue,
) -> None:
    monkeypatch.setenv("PUEUE_GROUP", "bulk")
    launch = write_launch(tmp_path, pool="pytest")

    assert main([str(launch)]) == 0

    assert [event["pool"] for event in events(tmp_path)] == ["bulk", "bulk"]
    assert "--slice=agentctl-bulk.slice" in fake_systemd.run_argv()


def test_units_stay_distinct_when_their_launch_inputs_share_a_name() -> None:
    """Two checkouts name their launch inputs alike; one cancel must not reach both."""
    stem = "pytest-slot-4242"
    long_stem = "x" * 400
    units = {
        unit_for(f"/realm/worktrees/{name}/.cache/verify/{stem}.json", "pytest")
        for name in ("checkout-a", "checkout-b")
    } | {
        unit_for(f"/inputs/{long_stem}{suffix}.json", "pytest")
        for suffix in ("-one", "-two")
    }

    assert len(units) == 4
    assert all(unit.startswith("agentctl-pytest-") for unit in units)
    assert all(len(unit) < 256 for unit in units)


def test_scope_properties_bound_the_task_unit_itself(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    launch = write_launch(
        tmp_path,
        pool="agent",
        scope_properties=["MemoryMax=10G", "CPUWeight=50"],
    )

    assert main([str(launch)]) == 0

    argv = fake_systemd.run_argv()
    for setting in ("MemoryMax=10G", "CPUWeight=50"):
        assert argv[argv.index(setting) - 1] == "-p"
        assert argv.index(setting) < argv.index("--")


@pytest.mark.parametrize(
    "setting",
    [
        "--property=Delegate=yes",
        "ExecStartPost=/bin/sh -c evil",
        "User=root",
        "Delegate=yes",
        "MemoryMax=; rm -rf /",
    ],
)
def test_a_property_that_does_not_bound_the_task_is_refused(
    tmp_path: Path, setting: str
) -> None:
    """A launch input may lower what its own task consumes, and nothing else."""
    launch = write_launch(tmp_path, scope_properties=[setting])

    assert main([str(launch)]) == REFUSED_EXIT_CODE


def test_a_failing_command_reports_its_own_exit_status(tmp_path: Path) -> None:
    launch = write_launch(tmp_path, argv=["sh", "-c", "exit 3"])

    assert main([str(launch)]) == 3
    assert outcome_of(tmp_path) == {
        "outcome": "failed",
        "exit_code": 3,
        "unit": None,
        "pool": None,
        "systemd_result": None,
    }


def test_a_failing_service_reports_the_main_process_status(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """The status is read from the unit, not from `systemd-run`'s own exit."""
    fake_systemd.terminal(Result="exit-code", ExecMainStatus="3")
    launch = write_launch(tmp_path, pool="pytest", argv=["sh", "-c", "exit 3"])

    assert main([str(launch)]) == 3
    assert outcome_of(tmp_path)["outcome"] == "failed"
    assert outcome_of(tmp_path)["systemd_result"] == "exit-code"


def test_a_typed_result_is_stdout_alone_and_the_log_keeps_the_diagnostics(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """Merging stderr into the artifact corrupts every JSON receipt."""
    launch = write_launch(
        tmp_path,
        pool="pytest",
        argv=["sh", "-c", "echo warming up >&2; printf '{\"passed\": 4}'"],
        result_kind="json",
        result_path=str(tmp_path / "job-a.result"),
    )

    assert main([str(launch)]) == 0

    assert json.loads((tmp_path / "job-a.result").read_text()) == {"passed": 4}
    assert "warming up" in log_of(tmp_path)
    argv = fake_systemd.run_argv()
    assert f"StandardOutput=file:{tmp_path / 'job-a.result'}" in argv
    assert f"StandardError=append:{tmp_path / 'job-a.log'}" in argv


def test_the_declared_timeout_is_the_unit_runtime_limit(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    fake_systemd.terminal(Result="timeout")
    launch = write_launch(tmp_path, pool="pytest", timeout_seconds=7)

    assert main([str(launch)]) == TIMEOUT_EXIT_CODE

    assert "RuntimeMaxSec=7" in fake_systemd.run_argv()
    assert "timed out after 7 seconds" in log_of(tmp_path)
    assert outcome_of(tmp_path)["outcome"] == "timeout"


def test_outside_the_queue_the_timeout_is_enforced_by_the_wrapper(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "still-running"
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", f"(sleep 30; touch {marker}) & sleep 30"],
        timeout_seconds=1,
    )

    assert main([str(launch)]) == TIMEOUT_EXIT_CODE

    assert "timed out after 1 seconds" in log_of(tmp_path)
    assert subprocess.run(["sleep", "2"], check=False).returncode == 0
    assert not marker.exists()


def test_a_cancel_marker_turns_a_stopped_unit_into_a_cancellation(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """`systemctl stop` ends the wait with success; only the marker says why."""
    marker = cancel_marker_for(tmp_path / "job-a.log")
    marker.write_text("stale")
    launch = write_launch(tmp_path, pool="pytest", argv=["sh", "-c", f"touch {marker}"])

    assert main([str(launch)]) == CANCELLED_EXIT_CODE

    assert outcome_of(tmp_path)["outcome"] == "cancelled"
    assert not marker.exists()
    assert events(tmp_path)[-1]["outcome"] == "cancelled"


def test_a_unit_that_cannot_be_observed_after_the_wait_is_vanished(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """A failed unit stays loaded; one that is gone after a failing wait is lost."""
    fake_systemd.show.write_text("LoadState=not-found\nResult=success\n")
    launch = write_launch(tmp_path, pool="pytest", argv=["sh", "-c", "exit 3"])

    assert main([str(launch)]) == VANISHED_EXIT_CODE

    assert outcome_of(tmp_path)["outcome"] == "vanished"
    assert "vanished" in log_of(tmp_path)


def test_a_single_slot_pool_held_by_a_running_task_refuses_the_run(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """Two payloads never share the pytest slot, whatever pueue admitted."""
    other = fake_pueue.add(
        group="pytest",
        label="other:verify",
        command=("agentctl-run", "/inputs/other.json"),
        working_directory=tmp_path,
    )
    fake_systemd.active(
        (unit_for("/inputs/other.json", "pytest"), described("pytest", other))
    )
    launch = write_launch(tmp_path, pool="pytest")

    assert main([str(launch)]) == SLOT_OCCUPIED_EXIT_CODE

    assert fake_systemd.run_argv() == []
    assert outcome_of(tmp_path)["outcome"] == "slot_occupied"
    assert "occupied" in log_of(tmp_path)
    assert [call for call in fake_systemd.systemctl_calls() if "stop" in call] == []


def test_a_unit_no_queued_task_owns_also_holds_the_slot(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    fake_systemd.active(
        ("agentctl-pytest-stray-0123456789ab.service", described("pytest", 99))
    )
    launch = write_launch(tmp_path, pool="pytest")

    assert main([str(launch)]) == SLOT_OCCUPIED_EXIT_CODE
    assert fake_systemd.run_argv() == []


def test_a_unit_of_another_daemon_or_pool_does_not_hold_the_slot(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """A private pueued's units share the slice; a name-only match is not ownership."""
    fake_systemd.active(
        ("agentctl-pytest-other-0123456789ab.service", "agentctl:ffffffffffff:pytest:3"),
        ("agentctl-pytest-x-job-0123456789ab.service", described("pytest-x", 4)),
        ("agentctl-pytest-old-0123456789ab.service", "7"),
    )
    launch = write_launch(tmp_path, pool="pytest")

    assert main([str(launch)]) == 0
    assert [call for call in fake_systemd.systemctl_calls() if "stop" in call] == []


def test_a_unit_whose_task_is_terminal_is_an_orphan_and_is_settled(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """A SIGKILLed wrapper leaves its service running; the next run stops it."""
    orphan = fake_pueue.add(
        group="pytest",
        label="other:verify",
        command=("agentctl-run", "/inputs/other.json"),
        working_directory=tmp_path,
    )
    fake_pueue.kill_directly(orphan)
    unit = unit_for("/inputs/other.json", "pytest")
    fake_systemd.active((unit, described("pytest", orphan)))
    launch = write_launch(tmp_path, pool="pytest")

    assert main([str(launch)]) == 0

    assert ["systemctl", "--user", "stop", unit] in fake_systemd.systemctl_calls()
    assert f"settled_orphan {unit}" in log_of(tmp_path)
    assert fake_systemd.run_argv() != []


def test_a_multi_slot_pool_is_not_guarded(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    fake_systemd.active(
        ("agentctl-agent-other-0123456789ab.service", described("agent", 5))
    )
    launch = write_launch(tmp_path, pool="agent")

    assert main([str(launch)]) == 0


def test_the_unit_description_names_the_daemon_pool_and_task(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    launch = write_launch(tmp_path, pool="pytest")
    task_id = fake_pueue.add(
        group="pytest",
        label="fixture:check",
        command=("agentctl-run", str(launch)),
        working_directory=tmp_path,
    )

    assert main([str(launch)]) == 0
    assert f"--description={described('pytest', task_id)}" in fake_systemd.run_argv()
    assert [event["task_id"] for event in events(tmp_path)] == [None, task_id]


def test_a_pool_without_a_slice_policy_runs_under_the_normal_slice(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    fake_pueue.groups["fixture-land"] = 1
    launch = write_launch(tmp_path, pool="fixture-land")

    assert main([str(launch)]) == 0

    argv = fake_systemd.run_argv()
    assert "--slice=agentctl-normal.slice" in argv
    assert f"--unit={unit_for(launch, 'fixture-land')}" in argv
    assert any(argument == "--slice=agentctl-pytest.slice" for argument in argv) is False


def test_an_oversized_log_is_truncated_with_a_marker(tmp_path: Path) -> None:
    launch = write_launch(
        tmp_path, argv=["sh", "-c", f"yes x | head -c {MAX_LOG_BYTES * 3}"]
    )

    assert main([str(launch)]) == 0

    log = log_of(tmp_path)
    assert len(log) <= MAX_LOG_BYTES
    assert log.endswith("[agentctl: output truncated]\n")


def test_the_environment_is_exactly_what_the_descriptor_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUST_NOT_INHERIT", "leaked")
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", "env"],
        environment={"PATH": os.environ["PATH"], "DECLARED": "yes"},
    )

    assert main([str(launch)]) == 0

    assert "DECLARED=yes" in log_of(tmp_path)
    assert "MUST_NOT_INHERIT" not in log_of(tmp_path)


def test_a_command_that_cannot_start_is_a_refusal_not_a_crash(tmp_path: Path) -> None:
    launch = write_launch(tmp_path, argv=["definitely-not-a-command"])

    assert main([str(launch)]) == REFUSED_EXIT_CODE

    assert "could not start" in log_of(tmp_path)


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

    assert not (tmp_path / "job-a.log").exists()
    assert events(tmp_path) == []


def test_an_absent_launch_input_refuses(tmp_path: Path) -> None:
    assert main([str(tmp_path / "absent.json")]) == REFUSED_EXIT_CODE


def test_a_vanished_working_directory_refuses_before_running(tmp_path: Path) -> None:
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", "echo ran > ran"],
        working_directory=str(tmp_path / "gone"),
    )

    assert main([str(launch)]) == REFUSED_EXIT_CODE

    assert "working directory is gone" in log_of(tmp_path)
    assert not (tmp_path / "ran").exists()


def test_the_launch_input_survives_for_a_restart(tmp_path: Path) -> None:
    launch = write_launch(tmp_path)

    assert main([str(launch)]) == 0
    assert launch.exists()
    assert main([str(launch)]) == 0


def test_the_wrapper_returns_only_once_the_unit_cgroup_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_pueue: FakePueue
) -> None:
    """Proven against the user manager: the leader exits at once, the child
    holds the cgroup, and the wait ends with the child."""
    user_manager()
    monkeypatch.setenv("PUEUE_GROUP", "fixture")
    launch = write_launch(
        tmp_path, argv=["sh", "-c", "sleep 1 & exit 0"], timeout_seconds=60
    )

    started = time.monotonic()
    assert main([str(launch)]) == 0
    elapsed = time.monotonic() - started

    assert elapsed >= 1.0, "the wrapper returned while its unit still ran"
    assert outcome_of(tmp_path)["outcome"] == "success"
    assert outcome_of(tmp_path)["unit"] == unit_for(launch, "fixture")


def test_worker_mirrors_the_pre_rename_names_for_older_consumers(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    launch = write_launch(
        tmp_path,
        argv=[
            "sh",
            "-c",
            'printf \'%s %s %s %s\' "$SINNIXD_JOB_ID" "$SINNIXD_PROJECT_ID" "$SINNIXD_OPERATION" "$SINNIXD_QUEUE_POOL"',
        ],
        pool="pytest",
    )

    assert main([str(launch)]) == 0
    assert log_of(tmp_path) == "job-a fixture check pytest"


def test_a_killed_waiter_leaves_its_unit_which_the_next_run_settles_or_yields_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_pueue: FakePueue
) -> None:
    """SIGKILL on the wrapper stops nothing inside the unit. The next run in
    the pool yields while pueue still counts the task running, and settles
    the orphan once the task is terminal."""
    user_manager()
    pool = "fixture"
    fake_pueue.groups[pool] = 1
    first = write_launch(
        tmp_path, argv=["sleep", "60"], timeout_seconds=120, pool=pool
    )
    first_task = fake_pueue.add(
        group=pool,
        label="fixture:check",
        command=("agentctl-run", str(first)),
        working_directory=tmp_path,
    )
    unit = unit_for(first, pool)
    # The waiter runs out of process with a pueue that answers like the fake.
    stub = tmp_path / "stub-bin"
    stub.mkdir()
    groups = json.dumps({pool: {"status": "Running", "parallel_tasks": 1}})
    status = json.dumps(
        {
            "tasks": {
                str(first_task): {
                    "id": first_task,
                    "command": f"agentctl-run {first}",
                    "group": pool,
                    "label": "fixture:check",
                    "path": str(tmp_path),
                    "status": {"Running": {"start": "2026-09-03T08:00:01+00:00"}},
                }
            }
        }
    )
    (stub / "pueue").write_text(
        "#!/bin/sh\n"
        f"case \"$1\" in group) echo '{groups}' ;; status) echo '{status}' ;; esac\n"
    )
    (stub / "pueue").chmod(0o755)
    waiter = subprocess.Popen(
        [sys.executable, "-m", "agentctl.run", str(first)],
        env={
            **os.environ,
            "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
            "PYTHONPATH": str(Path(__file__).parent),
        },
    )
    try:
        deadline = time.monotonic() + 30
        while (
            subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", unit], check=False
            ).returncode
            != 0
        ):
            assert time.monotonic() < deadline, "the unit never started"
            time.sleep(0.2)
        waiter.kill()
        waiter.wait()
        assert (
            subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", unit], check=False
            ).returncode
            == 0
        ), "killing the waiter must not stop the unit"

        second_log = tmp_path / "second.log"
        second = write_launch(
            tmp_path, "second.json", pool=pool, log_path=str(second_log), job_id="job-b"
        )
        assert main([str(second)]) == SLOT_OCCUPIED_EXIT_CODE
        assert f"occupied by {unit}" in second_log.read_text()

        fake_pueue.kill_directly(first_task)
        assert main([str(second)]) == 0
        assert f"settled_orphan {unit}" in second_log.read_text()
        assert (
            subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", unit], check=False
            ).returncode
            != 0
        )
    finally:
        subprocess.run(["systemctl", "--user", "stop", unit], check=False)
        subprocess.run(["systemctl", "--user", "reset-failed", unit], check=False)
        if waiter.poll() is None:
            waiter.kill()


def test_a_restarted_task_accounts_its_outcome_again(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """`pueue restart --in-place` reruns the same command line; each run
    leaves its own outcome record and a paired start/finish."""
    launch = write_launch(tmp_path, pool="pytest", argv=["sh", "-c", "exit 3"])
    fake_systemd.terminal(Result="exit-code", ExecMainStatus="3")
    task_id = fake_pueue.add(
        group="pytest",
        label="fixture:check",
        command=("agentctl-run", str(launch)),
        working_directory=tmp_path,
    )
    assert main([str(launch)]) == 3
    assert outcome_of(tmp_path)["outcome"] == "failed"
    fake_pueue.fail(task_id, exit_code=3)

    fake_pueue.restart(task_id)
    fake_pueue.running(task_id)
    fake_systemd.terminal()
    assert main([str(launch)]) == 0

    assert outcome_of(tmp_path) == {
        "outcome": "success",
        "exit_code": 0,
        "unit": unit_for(launch, "pytest"),
        "pool": "pytest",
        "systemd_result": "success",
    }
    spooled = events(tmp_path)
    assert [(e["phase"], e.get("outcome")) for e in spooled] == [
        ("started", None),
        ("finished", "failed"),
        ("started", None),
        ("finished", "success"),
    ]
    assert {e["task_id"] for e in spooled if e["phase"] == "finished"} == {task_id}
