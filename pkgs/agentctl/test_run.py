from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from agentctl import artifacts, cli, pueue
from agentctl import run as run_module
from agentctl.config import Config
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


def test_supervisor_import_rss_stays_small() -> None:
    # A queued job keeps this interpreter resident until its unit exits.
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            "import agentctl.run; "
            "print(open('/proc/self/status').read().split('VmRSS:')[1].splitlines()[0].split()[0])",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert int(child.stdout.strip()) < 50_000


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


def test_git_observation_is_read_only_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def probe(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        output = {
            "rev-parse": "head\n" if command[-1] == "HEAD" else "tree\n",
            "status": " M changed.py\n",
        }[command[3]]
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr(run_module.subprocess, "run", probe)

    monkeypatch.setattr(
        "agentctl.content_identity.content_manifest",
        lambda _path: {"schema_version": 1, "sha256": "fixture"},
    )
    observed = run_module.git_observation(tmp_path, observed_at="2026-09-11T00:00:00Z")

    assert observed == {
        "observed_at": "2026-09-11T00:00:00Z",
        "content_manifest": {"schema_version": 1, "sha256": "fixture"},
        "head": "head",
        "tree": "tree",
        "dirty": True,
        "status": "observed",
        "reason": None,
    }
    assert [command[3:] for command in calls] == [
        ["rev-parse", "HEAD"],
        ["rev-parse", "HEAD^{tree}"],
        ["status", "--porcelain=v1", "--untracked-files=all"],
    ]


def test_execution_receipt_distinguishes_changed_and_unavailable_endpoints() -> None:
    start = {
        "observed_at": "start",
        "head": "a",
        "tree": "b",
        "dirty": False,
        "status": "observed",
        "reason": None,
    }
    changed = {**start, "observed_at": "end", "tree": "c"}

    assert run_module.execution_receipt(start, changed)["binding"] == "changed"
    unavailable = {**changed, "status": "unavailable", "reason": "git_tree_unavailable"}
    receipt = run_module.execution_receipt(start, unavailable)
    assert receipt["binding"] == "unavailable"
    assert receipt["reason"] == "git_observation_unavailable"


def test_run_records_execution_receipt_even_without_cache_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launch = write_launch(tmp_path, argv=["true"])
    observations = iter(
        [
            {
                "observed_at": "start",
                "head": "a",
                "tree": "b",
                "dirty": False,
                "status": "observed",
                "reason": None,
            },
            {
                "observed_at": "end",
                "head": "a",
                "tree": "b",
                "dirty": False,
                "status": "observed",
                "reason": None,
            },
        ]
    )
    monkeypatch.setattr(
        run_module, "git_observation", lambda *_args: next(observations)
    )

    assert main([str(launch)]) == 0
    outcome = outcome_of(tmp_path)
    assert outcome["attempt"] == 1
    receipt = outcome["execution_receipt"]
    assert receipt["binding"] == "unchanged_endpoints"
    assert receipt["start"]["head"] == "a"
    reference = events(tmp_path)[-1]["outcome_ref"]
    assert (
        json.loads(Path(reference["path"]).read_text())["execution_receipt"] == receipt
    )
    assert (
        reference["sha256"]
        == hashlib.sha256(Path(reference["path"]).read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("follow", [False, True])
def test_large_receipt_completion_reaches_tail_and_follow(
    tmp_path: Path,
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    follow: bool,
) -> None:
    # Exercise the real producer and reader, not a fabricated compact event.
    # Before the fix this inventory duplicated into the spool and disappeared.
    inventory = {
        f"file-{i}.py": {"sha256": "a" * 64, "bytes": i} for i in range(15_000)
    }
    observation = {
        "status": "observed",
        "head": "a",
        "tree": "b",
        "dirty": False,
        "content_manifest": {"sha256": "neutral", "files": inventory},
    }
    monkeypatch.setattr(run_module, "git_observation", lambda *_args: observation)
    launch = write_launch(tmp_path)
    config.event_spool.touch()

    def produce() -> None:
        assert main([str(launch)]) == 0

    sleeps = 0

    def on_idle(_seconds: float) -> None:
        nonlocal sleeps
        sleeps += 1
        if sleeps == 1:
            produce()
        else:
            raise KeyboardInterrupt

    if follow:
        # Replace only the CLI's clock reference, not subprocess's time.sleep.
        monkeypatch.setattr(cli, "time", SimpleNamespace(sleep=on_idle))
    else:
        produce()
    arguments = argparse.Namespace(
        project="fixture", follow=follow, lines=0 if follow else 40
    )
    assert cli._events(arguments, config, cli.Output(as_json=True, full=False)) == 0
    observed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event["phase"] for event in observed] == ["started", "finished"]
    terminal = observed[-1]
    assert {
        key: terminal[key]
        for key in ("job_id", "attempt", "project", "operation", "outcome", "exit_code")
    } == {
        "job_id": "job-a",
        "attempt": 1,
        "project": "fixture",
        "operation": "check",
        "outcome": "success",
        "exit_code": 0,
    }
    reference = terminal["outcome_ref"]
    path = Path(reference["path"])
    assert path == tmp_path / "job-a.attempts/1/output.outcome"
    payload = path.read_bytes()
    assert len(payload) > cli.MAX_EVENT_LINE_BYTES
    assert reference["sha256"] == hashlib.sha256(payload).hexdigest()
    receipt = json.loads(payload)["execution_receipt"]
    assert receipt["start"] == receipt["end"] == observation
    assert (
        max(len(line) for line in config.event_spool.read_bytes().splitlines()) < 4096
    )
    assert "execution_receipt" not in terminal and "execution_evidence" not in terminal


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
    outcome = outcome_path_for(tmp_path / "job-a.log")
    assert outcome.stat().st_mode & 0o777 == 0o600
    assert not list(outcome.parent.glob(f".{outcome.name}.atomic-tmp-*"))


def test_event_append_failure_preserves_the_completed_owner_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_append(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("synthetic spool unavailable")

    monkeypatch.setattr(run_module, "append_jsonl", fail_append)
    launch = write_launch(tmp_path)

    assert main([str(launch)]) == 0
    assert outcome_of(tmp_path)["outcome"] == "success"
    assert outcome_of(tmp_path)["exit_code"] == 0
    assert events(tmp_path) == []


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
    """The unit is recoverable from pueue; wrapper completion follows its cgroup."""
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
    assert "--collect" not in argv
    for setting in (
        "ExitType=cgroup",
        "KillMode=control-group",
        "IOAccounting=yes",
        "RuntimeMaxSec=30",
        f"StandardOutput=append:{(tmp_path / 'job-a.log').resolve()}",
        f"StandardError=append:{(tmp_path / 'job-a.log').resolve()}",
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
        unit_for(f"/realm/worktree/{name}/.cache/verify/{stem}.json", "pytest")
        for name in ("checkout-a", "checkout-b")
    } | {
        unit_for(f"/inputs/{long_stem}{suffix}.json", "pytest")
        for suffix in ("-one", "-two")
    }

    assert len(units) == 4
    assert all(unit.startswith("agentctl-pytest-") for unit in units)
    assert all(len(unit) < 256 for unit in units)


def test_unit_properties_bound_the_task_unit_itself(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    launch = write_launch(
        tmp_path,
        pool="agent",
        unit_properties=["MemoryMax=10G", "CPUWeight=50"],
    )

    assert main([str(launch)]) == 0

    argv = fake_systemd.run_argv()
    for setting in ("MemoryMax=10G", "CPUWeight=50"):
        assert argv[argv.index(setting) - 1] == "-p"
        assert argv.index(setting) < argv.index("--")


def test_path_properties_bound_what_the_unit_can_reach(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    launch = write_launch(
        tmp_path,
        pool="agent",
        unit_properties=[
            "ReadOnlyPaths=/realm/project/x",
            "ReadWritePaths=/realm/project/x/.git",
            "InaccessiblePaths=-/realm/worktree/x-other",
        ],
    )

    assert main([str(launch)]) == 0

    argv = fake_systemd.run_argv()
    for setting in (
        "ReadOnlyPaths=/realm/project/x",
        "ReadWritePaths=/realm/project/x/.git",
        "InaccessiblePaths=-/realm/worktree/x-other",
    ):
        assert argv[argv.index(setting) - 1] == "-p"


@pytest.mark.parametrize(
    "setting",
    [
        "--property=Delegate=yes",
        "ExecStartPost=/bin/sh -c evil",
        "User=root",
        "Delegate=yes",
        "MemoryMax=; rm -rf /",
        "ReadOnlyPaths=relative/path",
        "InaccessiblePaths=/a /b",
        "BindPaths=/realm/project/x",
    ],
)
def test_a_property_that_does_not_bound_the_task_is_refused(
    tmp_path: Path, setting: str
) -> None:
    """A launch input may lower what its own task consumes, and nothing else."""
    launch = write_launch(tmp_path, unit_properties=[setting])

    assert main([str(launch)]) == REFUSED_EXIT_CODE


def test_a_declared_scratch_is_created_exported_measured_and_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The footprint is the job's own record; the result artifact stays the
    command's document, so nothing a parser reads is invented here."""
    monkeypatch.setenv("AGENTCTL_TMPFS_SCRATCH_ROOT", str(tmp_path / "tmpfs"))
    scratch = tmp_path / "tmpfs" / "job-a"
    launch = write_launch(
        tmp_path,
        argv=[
            "sh",
            "-c",
            'test "$TMPDIR" = "$AGENTCTL_SCRATCH" '
            "&& temporary=$(mktemp) "
            '&& dd if=/dev/zero of="$temporary" bs=1024 count=4 '
            "2>/dev/null "
            '&& printf \'{"scratch": "%s", "temporary": "%s"}\' "$AGENTCTL_SCRATCH" "$temporary"',
        ],
        result_kind="json",
        result_path=str(tmp_path / "job-a.result"),
        scratch={"kind": "tmpfs", "path": str(scratch)},
    )

    assert main([str(launch)]) == 0

    footprint = outcome_of(tmp_path)["scratch"]
    assert footprint["kind"] == "tmpfs" and footprint["path"] == str(scratch)
    assert footprint["files"] == 1 and footprint["bytes"] == 4096
    assert footprint["truncated"] is False
    reference = events(tmp_path)[-1]["outcome_ref"]
    assert json.loads(Path(reference["path"]).read_text())["scratch"] == footprint
    assert not scratch.exists() and (tmp_path / "tmpfs").is_dir()
    # The result artifact carries the command's stdout and nothing agentctl added.
    document = json.loads((tmp_path / "job-a.result").read_text())
    assert document["scratch"] == str(scratch)
    assert Path(document["temporary"]).parent == scratch


def test_a_job_declaring_no_scratch_records_none(tmp_path: Path) -> None:
    launch = write_launch(tmp_path, argv=["sh", "-c", "exit 0"])

    assert main([str(launch)]) == 0
    assert "scratch" not in outcome_of(tmp_path)


def test_a_refused_launch_leaves_no_scratch_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command that never started still owned a directory; it goes with the run."""
    monkeypatch.setenv("AGENTCTL_TMPFS_SCRATCH_ROOT", str(tmp_path / "tmpfs"))
    scratch = tmp_path / "tmpfs" / "job-a"
    launch = write_launch(
        tmp_path,
        argv=["agentctl-no-such-command"],
        scratch={"kind": "tmpfs", "path": str(scratch)},
    )

    assert main([str(launch)]) == REFUSED_EXIT_CODE
    assert not scratch.exists()


def test_a_scratch_path_outside_its_tier_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wrapper removes this directory afterwards; it must own it first."""
    monkeypatch.setenv("AGENTCTL_TMPFS_SCRATCH_ROOT", str(tmp_path / "tmpfs"))
    elsewhere = tmp_path / "elsewhere"
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", "exit 0"],
        scratch={"kind": "tmpfs", "path": str(elsewhere)},
    )

    assert main([str(launch)]) == REFUSED_EXIT_CODE
    assert not elsewhere.exists()

    unknown = write_launch(
        tmp_path,
        name="unknown.json",
        scratch={"kind": "disk", "path": str(tmp_path / "tmpfs" / "job-a")},
    )
    assert main([str(unknown)]) == REFUSED_EXIT_CODE


def test_a_failing_command_reports_its_own_exit_status(tmp_path: Path) -> None:
    launch = write_launch(tmp_path, argv=["sh", "-c", "exit 3"])

    assert main([str(launch)]) == 3
    outcome = outcome_of(tmp_path)
    assert {
        key: outcome[key]
        for key in ("outcome", "exit_code", "unit", "pool", "systemd_result")
    } == {
        "outcome": "failed",
        "exit_code": 3,
        "unit": None,
        "pool": None,
        "systemd_result": None,
    }
    assert outcome["execution_receipt"]["binding"] == "unavailable"


def test_a_lock_stranded_during_the_attempt_is_named_and_left_alone(
    tmp_path: Path,
) -> None:
    """Breaks if a lock a killed job left in its checkout goes unreported, is
    removed by the wrapper, or a lock that was already there is blamed on it."""
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    lock = repo / ".git" / "index.lock"
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", f": > {lock}"],
        working_directory=str(repo),
    )

    assert main([str(launch)]) == 0

    assert outcome_of(tmp_path)["stranded_index_locks"] == [
        {"lock": str(lock), "checkout": "main"}
    ]
    assert f"stranded index lock: {lock}" in log_of(tmp_path)
    assert lock.exists()

    # Anti-vacuity for attribution: the same lock, older than the next attempt.
    os.utime(lock, ns=(0, 0))
    again = write_launch(
        tmp_path, name="again.json", argv=["true"], working_directory=str(repo)
    )
    assert main([str(again)]) == 0
    assert outcome_of(tmp_path)["stranded_index_locks"] == []


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
    assert f"StandardOutput=file:{(tmp_path / 'job-a.result').resolve()}" in argv
    assert f"StandardError=append:{(tmp_path / 'job-a.log').resolve()}" in argv


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
    marker.write_text(json.dumps({"attempt": 1}))
    launch = write_launch(tmp_path, pool="pytest", argv=["sh", "-c", f"touch {marker}"])

    assert main([str(launch)]) == CANCELLED_EXIT_CODE

    assert outcome_of(tmp_path)["outcome"] == "cancelled"
    assert not marker.exists()
    assert events(tmp_path)[-1]["outcome"] == "cancelled"


def test_runner_outcome_retains_request_after_consuming_cancel_marker(
    tmp_path: Path,
    fake_systemd: FakeSystemd,
    fake_pueue: FakePueue,
) -> None:
    from agentctl import artifacts

    request = {
        "attempt": 1,
        "actor": "fixture-worker",
        "reason": "stop requested",
        "uid": 1000,
        "requested_at": "2026-01-01T00:00:00+00:00",
    }
    log = tmp_path / "job-a.log"
    destination = artifacts.cancellation_path(log, 1)
    destination.parent.mkdir()
    destination.write_text(json.dumps(request))
    marker = cancel_marker_for(log)
    marker.write_text(json.dumps({"attempt": 1}))
    launch = write_launch(tmp_path, pool="pytest")
    assert main([str(launch)]) == CANCELLED_EXIT_CODE
    assert outcome_of(tmp_path)["cancellation"] == request
    assert not marker.exists()


def test_refused_attempt_retains_cancel_request_without_claiming_cancellation(
    tmp_path: Path,
) -> None:
    from agentctl import artifacts

    request = {"attempt": 1, "actor": "fixture-worker", "reason": "stop requested"}
    destination = artifacts.cancellation_path(tmp_path / "job-a.log", 1)
    destination.parent.mkdir()
    destination.write_text(json.dumps(request))
    launch = write_launch(tmp_path, working_directory=str(tmp_path / "missing"))
    assert main([str(launch)]) == REFUSED_EXIT_CODE
    assert outcome_of(tmp_path)["outcome"] == "refused"
    assert outcome_of(tmp_path)["cancellation"] == request


def test_cancel_during_preparation_prevents_service_creation(
    tmp_path: Path,
    fake_systemd: FakeSystemd,
    fake_pueue: FakePueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation after allocation remains attached through Git preparation.

    Anti-vacuity: the old unconditional marker unlink let this workload create
    its side-effect file and return success.
    """
    side_effect = tmp_path / "workload-started"
    launch = write_launch(
        tmp_path,
        pool="pytest",
        argv=["sh", "-c", f"touch {side_effect}"],
    )
    marker = cancel_marker_for(tmp_path / "job-a.log")

    def cancel_during_git(_cwd: Path) -> dict[str, Any]:
        marker.write_text(json.dumps({"attempt": 1}))
        return {"status": "unavailable"}

    monkeypatch.setattr(run_module, "git_observation", cancel_during_git)

    assert main([str(launch)]) == CANCELLED_EXIT_CODE

    assert not side_effect.exists()
    assert fake_systemd.run_argv() == []
    assert outcome_of(tmp_path)["outcome"] == "cancelled"
    assert events(tmp_path)[-1]["outcome"] == "cancelled"


def test_property_failures_do_not_hold_the_cancellation_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown unit state after admission does not block cancellation.

    systemd-run's default service mode waits for startup, and Type=exec makes
    its successful return an exec acknowledgement. Property reads happen after
    that acknowledgement and
    outside the allocation lock, so a temporary observation failure cannot
    strand cancellation behind the workload.
    """
    marker = cancel_marker_for(tmp_path / "job-a.log")
    root = tmp_path / "job-a.attempts"
    root.mkdir()
    observation_failed = threading.Event()
    cancellation_finished = threading.Event()
    outcome: list[tuple[run_module.Outcome, int]] = []

    def admitted(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def observation(_unit: str) -> dict[str, str] | None:
        if not marker.exists():
            observation_failed.set()
            return None
        return {"LoadState": "not-found"}

    monkeypatch.setattr(run_module.subprocess, "run", admitted)
    monkeypatch.setattr(run_module, "_unit_snapshot", observation)

    def run_and_observe() -> None:
        client = run_module._start_service(["systemd-run", "--quiet"], marker, 1, None)
        assert client is not None
        properties = run_module._wait_for_unit("fixture.service", 30)
        outcome.append(
            run_module._classify(
                client.returncode, run_module._marker_targets(marker, 1), properties
            )
        )

    submitter = threading.Thread(target=run_and_observe)
    submitter.start()
    assert observation_failed.wait(5)

    def cancel() -> None:
        with (root / ".allocation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            marker.write_text(json.dumps({"attempt": 1}))
            fcntl.flock(lock, fcntl.LOCK_UN)
        cancellation_finished.set()

    canceller = threading.Thread(target=cancel)
    canceller.start()
    assert cancellation_finished.wait(5)
    submitter.join(5)
    canceller.join(5)
    assert not submitter.is_alive() and not canceller.is_alive()
    assert outcome == [(run_module.Outcome.CANCELLED, CANCELLED_EXIT_CODE)]
    assert json.loads(marker.read_text()) == {"attempt": 1}


def test_persistent_unit_observation_failure_is_bounded_and_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lost systemd connection cannot hold the wrapper or imply success."""
    clock = [0.0]

    def monotonic() -> float:
        value = clock[0]
        clock[0] += 1
        return value

    monkeypatch.setattr(run_module, "_unit_snapshot", lambda _unit: None)
    monkeypatch.setattr(run_module.time, "monotonic", monotonic)
    monkeypatch.setattr(run_module.time, "sleep", lambda _delay: None)

    properties = run_module._wait_for_unit("fixture.service", timeout_seconds=2)

    assert properties is None
    assert run_module._classify(0, False, properties) == (
        run_module.Outcome.VANISHED,
        run_module.VANISHED_EXIT_CODE,
    )


def test_unit_wait_backs_off_to_a_bounded_poll_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A long job must not poll the shared user manager at 20 Hz for its whole
    run: two dozen such waiters starve the manager's job dispatch."""
    clock = [0.0]
    delays: list[float] = []
    observations = [0]

    def sleep(delay: float) -> None:
        delays.append(delay)
        clock[0] += delay

    def snapshot(_unit: str) -> dict[str, str]:
        observations[0] += 1
        state = "inactive" if clock[0] >= 600 else "active"
        return {"LoadState": "loaded", "ActiveState": state}

    monkeypatch.setattr(run_module, "_unit_snapshot", snapshot)
    monkeypatch.setattr(run_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(run_module.time, "sleep", sleep)

    properties = run_module._wait_for_unit("fixture.service", timeout_seconds=3600)

    assert properties == {"LoadState": "loaded", "ActiveState": "inactive"}
    assert delays[0] == run_module.UNIT_POLL_INITIAL_SECONDS
    assert max(delays) == run_module.UNIT_POLL_MAX_SECONDS
    # Ten minutes of running cost a few hundred observations, not 12,000.
    assert observations[0] < 600 / run_module.UNIT_POLL_MAX_SECONDS + 20


def test_retry_discards_predecessor_cancel_but_keeps_new_attempt_cancel(
    tmp_path: Path,
    fake_systemd: FakeSystemd,
    fake_pueue: FakePueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = write_launch(tmp_path, pool="pytest", argv=["true"])
    marker = cancel_marker_for(tmp_path / "job-a.log")
    assert main([str(launch)]) == 0

    # A delayed cancel from attempt one is stale when attempt two allocates.
    marker.write_text(json.dumps({"attempt": 1}))

    def cancel_attempt_two(_cwd: Path) -> dict[str, Any]:
        marker.write_text(json.dumps({"attempt": 2}))
        return {"status": "unavailable"}

    monkeypatch.setattr(run_module, "git_observation", cancel_attempt_two)

    assert main([str(launch)]) == CANCELLED_EXIT_CODE

    records = artifacts.attempts(json.loads(launch.read_text()))
    assert len(records) == 2
    assert (
        json.loads(Path(records[0]["artifacts"]["outcome"]).read_text())["outcome"]
        == "success"
    )
    assert (
        json.loads(Path(records[1]["artifacts"]["outcome"]).read_text())["outcome"]
        == "cancelled"
    )


def test_a_unit_that_cannot_be_observed_after_the_wait_is_vanished(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """A failed unit stays loaded; one that is gone after a failing wait is lost."""
    fake_systemd.show.write_text("LoadState=not-found\nResult=success\n")
    launch = write_launch(tmp_path, pool="pytest", argv=["sh", "-c", "exit 3"])

    assert main([str(launch)]) == VANISHED_EXIT_CODE

    assert outcome_of(tmp_path)["outcome"] == "vanished"
    assert "vanished" in log_of(tmp_path)


def test_run_publishes_vanished_when_unit_state_remains_unobservable(
    tmp_path: Path,
    fake_systemd: FakeSystemd,
    fake_pueue: FakePueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper publishes a typed unresolved outcome if show keeps failing."""
    clock = [0.0]

    def monotonic() -> float:
        value = clock[0]
        clock[0] += 100
        return value

    monkeypatch.setattr(run_module, "_unit_snapshot", lambda _unit: None)
    monkeypatch.setattr(run_module.time, "monotonic", monotonic)
    monkeypatch.setattr(run_module.time, "sleep", lambda _delay: None)
    launch = write_launch(tmp_path, pool="pytest", timeout_seconds=1)

    assert main([str(launch)]) == VANISHED_EXIT_CODE

    record = outcome_of(tmp_path)
    assert record["outcome"] == "vanished"
    assert record["exit_code"] == VANISHED_EXIT_CODE
    assert record["systemd_result"] is None


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
        (
            "agentctl-pytest-other-0123456789ab.service",
            "agentctl:ffffffffffff:pytest:3",
        ),
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
    assert (
        any(argument == "--slice=agentctl-pytest.slice" for argument in argv) is False
    )


def test_output_larger_than_eight_mb_is_preserved_completely(tmp_path: Path) -> None:
    launch = write_launch(
        tmp_path, argv=["sh", "-c", f"yes x | head -c {MAX_LOG_BYTES * 3}"]
    )

    assert main([str(launch)]) == 0

    log = log_of(tmp_path)
    assert len(log) == MAX_LOG_BYTES * 3
    assert log == "x\n" * (MAX_LOG_BYTES * 3 // 2)


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
    outcome = outcome_path_for(tmp_path / "job-a.log")
    assert outcome.stat().st_mode & 0o777 == 0o600
    assert not list(outcome.parent.glob(f".{outcome.name}.atomic-tmp-*"))

    (finished,) = events(tmp_path)
    assert finished["phase"] == "finished"
    assert finished["project"] == "fixture" and finished["operation"] == "check"
    assert finished["outcome"] == "refused"
    canonical = tmp_path / "job-a.attempts" / "1" / "output.outcome"
    assert finished["outcome_ref"]["path"] == str(canonical)
    payload = canonical.read_bytes()
    assert finished["outcome_ref"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert json.loads(payload)["outcome"] == "refused"


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


def test_a_killed_waiter_leaves_its_unit_which_the_next_run_settles_or_yields_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_pueue: FakePueue
) -> None:
    """SIGKILL on the wrapper stops nothing inside the unit. The next run in
    the pool yields while pueue still counts the task running, and settles
    the orphan once the task is terminal."""
    user_manager()
    pool = "fixture"
    fake_pueue.groups[pool] = 1
    first = write_launch(tmp_path, argv=["sleep", "60"], timeout_seconds=120, pool=pool)
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
            "PYTHONPATH": os.pathsep.join(
                filter(None, (str(Path(__file__).parent), os.environ.get("PYTHONPATH")))
            ),
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


def test_a_reordered_task_spools_the_id_the_queue_moved_it_to(
    tmp_path: Path, fake_systemd: FakeSystemd, fake_pueue: FakePueue
) -> None:
    """`pueue switch` exchanges two queued task ids before either runs.

    Anti-vacuity: the spool is how a reader finds the queue task behind a
    job, so a finish event naming the id the task was enqueued with sends
    that reader to another job's log.
    """
    launch = write_launch(tmp_path, pool="pytest", argv=["true"])
    task_id = fake_pueue.add(
        group="pytest",
        label="fixture:check",
        command=("agentctl-run", str(launch)),
        working_directory=tmp_path,
    )
    other = fake_pueue.add(
        group="pytest",
        label="fixture:check",
        command=("agentctl-run", str(tmp_path / "other.json")),
        working_directory=tmp_path,
    )
    fake_pueue.queue(task_id)
    fake_pueue.queue(other)
    fake_pueue.switch(task_id, other)
    fake_pueue.running(other)
    fake_systemd.terminal()

    assert main([str(launch)]) == 0

    spooled = events(tmp_path)
    assert {e["task_id"] for e in spooled if e["phase"] == "finished"} == {other}
    assert {e["job_id"] for e in spooled} == {"job-a"}


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

    outcome = outcome_of(tmp_path)
    assert {
        key: outcome[key]
        for key in ("outcome", "exit_code", "unit", "pool", "systemd_result")
    } == {
        "outcome": "success",
        "exit_code": 0,
        "unit": unit_for(launch, "pytest"),
        "pool": "pytest",
        "systemd_result": "success",
    }
    assert outcome["execution_receipt"]["binding"] == "unavailable"
    spooled = events(tmp_path)
    assert [(e["phase"], e.get("outcome")) for e in spooled] == [
        ("started", None),
        ("finished", "failed"),
        ("started", None),
        ("finished", "success"),
    ]
    assert {e["task_id"] for e in spooled if e["phase"] == "finished"} == {task_id}
    assert [
        json.loads(Path(event["outcome_ref"]["path"]).read_text())["execution_receipt"][
            "binding"
        ]
        for event in spooled
        if event["phase"] == "finished"
    ] == ["unavailable", "unavailable"]
    assert [
        json.loads(Path(e["outcome_ref"]["path"]).read_text())["exit_code"]
        for e in spooled
        if e["phase"] == "finished"
    ] == [3, 0]


def test_event_append_takes_the_spool_lock_and_repairs_a_torn_tail(
    tmp_path: Path,
) -> None:
    """Breaks if a lifecycle event writes while another spool writer holds
    the ledger lock, or appends after an interrupted line."""
    spool = tmp_path / "events.jsonl"
    spool.write_text('{"kind":"backpressure"}\n{"kind":"torn')
    lock = os.open(tmp_path / "events.jsonl.lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(lock, fcntl.LOCK_EX)
    writer = threading.Thread(
        target=run_module.append_event, args=(spool, {"kind": "queue-task"})
    )
    writer.start()
    writer.join(timeout=0.3)
    assert writer.is_alive()
    assert spool.read_text().endswith('"torn')
    fcntl.flock(lock, fcntl.LOCK_UN)
    os.close(lock)
    writer.join(timeout=5)
    assert not writer.is_alive()
    kinds = [json.loads(line)["kind"] for line in spool.read_text().splitlines()]
    assert kinds == ["backpressure", "queue-task"]


@pytest.mark.parametrize("dirty", [False, True])
@pytest.mark.parametrize("linked", [False, True])
@pytest.mark.parametrize("subdirectory", [False, True])
def test_worker_exports_observed_native_provenance(
    tmp_path, fake_systemd, fake_pueue, dirty, linked, subdirectory
):
    import hashlib
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit",
                    "--allow-empty", "-qm", "neutral"], check=True)
    (tmp_path / ".git/info/exclude").write_text("*\n!neutral.txt\n")
    (tmp_path / "neutral.txt").write_text("committed fixture")
    subprocess.run(["git", "-C", str(tmp_path), "add", "neutral.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit",
                    "-qm", "track neutral fixture"], check=True)
    head = subprocess.check_output(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True
    ).strip()
    if dirty:
        (tmp_path / "neutral.txt").write_text("uncommitted fixture")
    assert run_module.git_observation(tmp_path)["dirty"] is dirty
    root = tmp_path / "other-root" if linked else tmp_path
    fields = ["JOB_ID", "CORRELATION_ID", "PROJECT_ID", "OPERATION",
              "CHECKOUT_ID", "CHECKOUT_HEAD"]
    command = "import os,json;print(json.dumps({k:os.environ.get('AGENTCTL_'+k) for k in " + repr(fields) + "}))"
    cwd = tmp_path / "sub" if subdirectory else tmp_path
    cwd.mkdir(exist_ok=True)
    launch = write_launch(
        tmp_path, pool="pytest", project_root=str(root), working_directory=str(cwd),
        argv=[sys.executable, "-c", command],
        tree_receipt={"head": "stale-cache-head"},
        environment={"PATH": os.environ["PATH"], "AGENTCTL_CHECKOUT_HEAD": "parent-head",
                     "AGENTCTL_CORRELATION_ID": "parent-request"},
    )
    assert main([str(launch)]) == 0
    row = json.loads(log_of(tmp_path))
    assert row == {
        "JOB_ID": "job-a", "CORRELATION_ID": "job-a",
        "PROJECT_ID": "fixture", "OPERATION": "check",
        "CHECKOUT_HEAD": head,
        "CHECKOUT_ID": "worktree-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:16]
            if linked else "default",
    }


def test_worker_does_not_invent_missing_checkout_evidence(
    tmp_path, fake_systemd, fake_pueue
):
    command = "import os,json;print(json.dumps({k:os.environ.get('AGENTCTL_'+k) for k in ['CHECKOUT_ID','CHECKOUT_HEAD']}))"
    launch = write_launch(
        tmp_path, pool="pytest", argv=[sys.executable, "-c", command],
        environment={"PATH": os.environ["PATH"], "AGENTCTL_CHECKOUT_ID": "parent",
                     "AGENTCTL_CHECKOUT_HEAD": "parent"},
    )
    assert main([str(launch)]) == 0
    assert json.loads(log_of(tmp_path)) == {"CHECKOUT_ID": None, "CHECKOUT_HEAD": None}
