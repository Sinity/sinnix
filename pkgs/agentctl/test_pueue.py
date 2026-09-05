"""The pueue adapter, exercised against payloads recorded from pueue 4.0.4.

The stub replays documents captured from the live daemon rather than shapes
invented here, and records the argv it was called with, so a wrong flag or a
misread enum fails.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from agentctl import launch, pueue
from agentctl.config import Config
from agentctl.run import scope_unit_for

# Recorded from `pueue status --json` on pueue 4.0.4 after one failing task.
LIVE_STATUS = {
    "tasks": {
        "0": {
            "id": 0,
            "original_command": "sh -c exit 3",
            "command": "sh -c exit 3",
            "path": "/realm/project/sinex",
            "envs": {"PATH": "/run/current-system/sw/bin"},
            "group": "default",
            "dependencies": [],
            "priority": 0,
            "label": "probe:schema",
            "status": {
                "Done": {
                    "enqueued_at": "2026-09-03T01:18:23.935179686+02:00",
                    "start": "2026-09-03T01:18:24.038100335+02:00",
                    "end": "2026-09-03T01:18:24.338953441+02:00",
                    "result": {"Failed": 3},
                }
            },
        },
        "1": {
            "id": 1,
            "path": "/realm/project/polylogue",
            "group": "agent",
            "dependencies": [0],
            "label": "polylogue:verify_affected:abc",
            "status": {"Running": {"start": "2026-09-03T01:19:00+02:00"}},
        },
        "2": {
            "id": 2,
            "path": "/realm/project/polylogue",
            "group": "pytest",
            "dependencies": [],
            "label": "polylogue:verify_all:master",
            "status": {"Done": {"result": "Success"}},
        },
    },
    "groups": {
        "agent": {"status": "Running", "parallel_tasks": 6},
        "bulk": {"status": "Running", "parallel_tasks": 1},
        "default": {"status": "Running", "parallel_tasks": 1},
        "pytest": {"status": "Running", "parallel_tasks": 1},
    },
}

LIVE_LOG = {
    "0": {
        "task": {"id": 0, "label": "probe:schema"},
        "output": "\nerr",
    }
}


@pytest.fixture
def stub_pueue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put a recording `pueue` on PATH that replays the captured documents."""
    calls = tmp_path / "calls"
    binary = tmp_path / "bin" / "pueue"
    binary.parent.mkdir(parents=True)
    binary.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"calls = {str(calls)!r}\n"
        f"status = {json.dumps(LIVE_STATUS)!r}\n"
        f"log = {json.dumps(LIVE_LOG)!r}\n"
        "open(calls, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "verb = sys.argv[1] if len(sys.argv) > 1 else ''\n"
        "if verb == 'status':\n"
        "    print(status)\n"
        "elif verb == 'group':\n"
        "    print(json.dumps(json.loads(status)['groups']))\n"
        "elif verb == 'log':\n"
        "    print(log)\n"
        "elif verb == 'add':\n"
        "    print('7')\n"
        "sys.exit(0)\n"
    )
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ['PATH']}")
    return calls


def _calls(path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_status_reads_each_task_state_result_and_exit_code(stub_pueue: Path) -> None:
    """Anti-vacuity: a misread of pueue's tagged enums makes a failure look Queued."""
    tasks = pueue.tasks()

    failed = tasks[0]
    assert failed.terminal and not failed.succeeded
    assert (failed.status, failed.result, failed.exit_code) == ("Done", "Failed", 3)
    assert failed.label == "probe:schema"

    running = tasks[1]
    assert running.status == "Running"
    assert not running.terminal
    assert running.result is None
    assert running.dependencies == (0,)

    passed = tasks[2]
    assert passed.terminal and passed.succeeded
    assert passed.exit_code == 0


def test_add_names_the_group_label_directory_and_dependencies(
    stub_pueue: Path, tmp_path: Path
) -> None:
    task_id = pueue.add(
        group="agent",
        label="polylogue:verify_affected:abc",
        command=("agentctl-run", "input.json"),
        working_directory=tmp_path,
        after=(3, 5),
    )

    assert task_id == 7
    assert _calls(stub_pueue)[0] == [
        "add",
        "--escape",
        "--group",
        "agent",
        "--label",
        "polylogue:verify_affected:abc",
        "--working-directory",
        str(tmp_path),
        "--print-task-id",
        "--after",
        "3",
        "--after",
        "5",
        "--",
        "agentctl-run",
        "input.json",
    ]


def test_add_stashed_holds_the_task_and_enqueue_releases_it(
    stub_pueue: Path, tmp_path: Path
) -> None:
    """The landing task of an external run waits stashed until its results are filed."""
    task_id = pueue.add(
        group="fixture-land",
        label="fixture:land:run-1",
        command=("agentctl", "batch", "land", "run-1"),
        working_directory=tmp_path,
        after=(3,),
        stashed=True,
    )
    pueue.enqueue(task_id)

    calls = _calls(stub_pueue)
    assert "--stashed" in calls[0]
    assert calls[0].index("--stashed") < calls[0].index("--")
    assert calls[1] == ["enqueue", "7"]


def test_group_add_creates_only_a_missing_group(stub_pueue: Path) -> None:
    pueue.group_add("agent", 8)
    pueue.group_add("fixture-land", 1)

    calls = _calls(stub_pueue)
    assert [call[0] for call in calls] == ["group", "group", "group"]
    assert calls[-1] == ["group", "add", "--parallel", "1", "fixture-land"]


def test_the_client_environment_carries_no_inherited_secret(
    stub_pueue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pueue writes the client's environment into world-readable state.json.

    Anti-vacuity: dropping the scrub would publish every inherited API key of
    whichever process called `pueue add`, which is the daemon's own environment.
    """
    monkeypatch.setenv("SECRET_API_KEY", "must-not-be-published")
    dump = tmp_path / "bin" / "pueue"
    dump.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"open({str(tmp_path / 'env')!r}, 'w').write(json.dumps(sorted(os.environ)))\n"
        "print('7')\n"
    )

    pueue.add(
        group="agent",
        label="lane",
        command=("true",),
        working_directory=tmp_path,
    )

    published = set(json.loads((tmp_path / "env").read_text()))
    assert "SECRET_API_KEY" not in published
    # Nothing the daemon inherited survives except the allowlist; the child
    # interpreter is free to set its own variables (LC_CTYPE) on top.
    inherited = set(os.environ) - set(pueue._CLIENT_ENVIRONMENT_KEYS)
    assert not published & inherited


def test_groups_publish_the_whole_admission_policy(stub_pueue: Path) -> None:
    assert pueue.groups() == {"agent": 6, "bulk": 1, "default": 1, "pytest": 1}


def test_log_reads_the_whole_output_not_a_tail(stub_pueue: Path) -> None:
    """Anti-vacuity: without --full pueue publishes a tail, which a result
    parser would read as the complete run."""
    assert pueue.log(0) == "\nerr"
    assert _calls(stub_pueue)[0] == ["log", "0", "--json", "--full"]


def test_pause_drains_running_tasks_and_resume_names_the_group(
    stub_pueue: Path,
) -> None:
    pueue.pause("agent")
    pueue.resume("agent")

    assert _calls(stub_pueue) == [
        ["pause", "--wait", "--group", "agent"],
        ["start", "--group", "agent"],
    ]


def test_restart_is_the_only_retry(stub_pueue: Path) -> None:
    pueue.restart(4)

    assert _calls(stub_pueue) == [["restart", "--in-place", "4"]]


def test_remove_of_nothing_does_not_call_pueue(stub_pueue: Path) -> None:
    pueue.remove(())

    assert not stub_pueue.exists()


def test_a_refusal_is_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(pueue.PueueError):
        pueue.tasks()


@pytest.fixture
def live_pueue(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A private pueued: the adapter's parsing proven against the real daemon.

    The runtime directory is overridden so this daemon never touches the
    operator's socket or pid file, and it lives under the shortest available
    temporary root because a Unix socket path over SUN_LEN cannot be bound.
    """
    root = Path(tempfile.mkdtemp(prefix="pq", dir=tempfile.gettempdir()))
    home = root / "h"
    (home / ".config" / "pueue").mkdir(parents=True)
    (home / ".config" / "pueue" / "pueue.yml").write_text(
        "shared:\n"
        f"  pueue_directory: {root / 'd'}\n"
        f"  runtime_directory: {root / 'r'}\n"
        "  use_unix_socket: true\n"
        "daemon:\n"
        "  default_parallel_tasks: 2\n"
    )
    (root / "d").mkdir()
    (root / "r").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    environment = {"HOME": str(home), "PATH": os.environ["PATH"]}
    # Every call below must reach this daemon and no other. A config or runtime
    # directory inherited from the invoking user resolves to the operator's
    # live socket, where `shutdown` stops the machine's real queue.
    resolved = subprocess.run(
        ["pueue", "status", "--json"], env=environment, capture_output=True, text=True
    )
    assert resolved.returncode != 0, (
        "a daemon answered before this fixture started one: the environment "
        "still points at someone else's pueued"
    )
    # pueued daemonises but its child inherits the parent's stdio; capturing
    # into a pipe would block until that child exits, which is never.
    with open(root / "daemon.log", "w") as daemon_log:
        subprocess.run(
            ["pueued", "-d"],
            env=environment,
            check=True,
            stdout=daemon_log,
            stderr=subprocess.STDOUT,
        )
    deadline = time.monotonic() + 30
    while True:
        probe = subprocess.run(
            ["pueue", "status", "--json"], env=environment, capture_output=True
        )
        if probe.returncode == 0:
            break
        if time.monotonic() > deadline:
            raise AssertionError(f"pueued did not start: {probe.stderr!r}")
        time.sleep(0.1)
    try:
        yield str(home)
    finally:
        subprocess.run(
            ["pueue", "shutdown"], env=environment, capture_output=True, timeout=30
        )
        shutil.rmtree(root, ignore_errors=True)


def test_the_adapter_drives_a_real_daemon_end_to_end(
    live_pueue: str, tmp_path: Path
) -> None:
    """Anti-vacuity: recorded payloads cannot catch a flag the real daemon rejects."""
    assert pueue.groups()["default"] >= 1

    failing = pueue.add(
        group="default",
        label="fixture:failing:job-a",
        command=("sh", "-c", "echo captured; exit 3"),
        working_directory=tmp_path,
    )
    finished = pueue.wait(failing, timeout_seconds=60)

    assert finished.terminal and not finished.succeeded
    assert (finished.result, finished.exit_code) == ("Failed", 3)
    assert finished.label == "fixture:failing:job-a"
    # Anti-vacuity for --escape: without it the shell splits this command and
    # neither the output nor the exit status is the one the caller asked for.
    assert "captured" in pueue.log(failing)

    dependent = pueue.add(
        group="default",
        label="fixture:dependent:job-b",
        command=("true",),
        working_directory=tmp_path,
        after=(failing,),
    )
    assert pueue.task(dependent) is not None
    assert pueue.task(dependent).dependencies == (failing,)

    pueue.remove([dependent])
    assert pueue.task(dependent) is None
    assert pueue.task(failing) is not None


def test_a_private_pueue_task_places_its_child_in_the_declared_pool_scope(
    live_pueue: str, tmp_path: Path
) -> None:
    """The private daemon must observe the same cgroup boundary as production."""
    if not Path(f"/run/user/{os.getuid()}/bus").exists():
        pytest.skip("no user systemd bus is available")

    launch_path = tmp_path / "launch.json"
    log_path = tmp_path / "queue.log"
    job_id = "private-job"
    subprocess.run(["pueue", "group", "add", "pytest"], check=True)
    subprocess.run(["pueue", "parallel", "-g", "pytest", "1"], check=True)
    launch_path.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "project_id": "fixture",
                "operation": "verify",
                "pool": "pytest",
                "argv": ["sh", "-c", "cat /proc/self/cgroup"],
                "environment": {
                    "HOME": os.environ["HOME"],
                    "PATH": os.environ["PATH"],
                    "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
                    "PYTHONPATH": str(Path(__file__).parent),
                },
                "working_directory": str(tmp_path),
                "timeout_seconds": 30,
                "result_kind": "exit",
                "label": "fixture:verify:private",
                "log_path": str(log_path),
            }
        )
    )
    task_id = pueue.add(
        group="pytest",
        label="fixture:verify:private",
        command=(
            "env",
            f"PYTHONPATH={Path(__file__).parent}",
            sys.executable,
            "-m",
            "agentctl.run",
            str(launch_path),
        ),
        working_directory=tmp_path,
    )

    finished = pueue.wait(task_id, timeout_seconds=60)

    assert finished.succeeded, pueue.log(task_id)
    cgroup = log_path.read_text()
    assert f"/{scope_unit_for(launch_path, 'pytest')}" in cgroup
    assert "/agentctl-pytest.slice/" in cgroup


def test_kill_reaches_the_whole_process_tree(live_pueue: str, tmp_path: Path) -> None:
    """Whether `pueue kill` stops a task's descendants decides how cancel works.

    Anti-vacuity: if the grandchild survives, cancelling a job leaves work
    running with nothing left to reap it.
    """
    marker = tmp_path / "survivor"
    task_id = pueue.add(
        group="default",
        label="fixture:tree:job",
        command=("sh", "-c", f"(sleep 6; touch {marker}) & sleep 6"),
        working_directory=tmp_path,
    )
    deadline = time.monotonic() + 20
    while (task := pueue.task(task_id)) is None or task.status != "Running":
        assert time.monotonic() < deadline, "task never started"
        time.sleep(0.1)

    pueue.kill(task_id)
    pueue.wait(task_id, timeout_seconds=30)
    time.sleep(8)

    assert not marker.exists(), (
        "pueue kill left a descendant running; cancel must reach the group itself"
    )


def test_kill_is_not_catchable_so_a_wrapper_cannot_clean_up(
    live_pueue: str, tmp_path: Path
) -> None:
    """`pueue kill` is not catchable, which is why the canceller stops the unit.

    Anti-vacuity: if pueue ever delivered a catchable signal, a wrapper could
    clean up its own detached session and agentctl's reaping would be dead
    weight. This turns red the day that changes.
    """
    caught = tmp_path / "caught"
    task_id = pueue.add(
        group="default",
        label="fixture:signal:job",
        command=(
            "sh",
            "-c",
            f"trap 'echo TERM > {caught}; exit 0' TERM; sleep 6; echo NONE > {caught}",
        ),
        working_directory=tmp_path,
    )
    deadline = time.monotonic() + 20
    while (task := pueue.task(task_id)) is None or task.status != "Running":
        assert time.monotonic() < deadline, "task never started"
        time.sleep(0.1)
    time.sleep(0.5)

    pueue.kill(task_id)
    pueue.wait(task_id, timeout_seconds=30)
    time.sleep(1)

    assert not caught.exists(), (
        "pueue delivered a catchable signal; the wrapper could clean up itself"
    )


def test_cancelling_a_task_reaps_every_descendant_it_started(
    live_pueue: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancel by task id ends the whole tree, and only it.

    Anti-vacuity: the grandchild leaves both the session and the process group,
    so a reap that signals the recorded group alone leaves it running. Only the
    cgroup still holds it.
    """
    if not Path(f"/run/user/{os.getuid()}/bus").exists():
        pytest.skip("no user systemd bus is available")
    monkeypatch.setenv(
        "DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus"
    )
    subprocess.run(["pueue", "group", "add", "pytest"], check=True)
    subprocess.run(["pueue", "parallel", "-g", "pytest", "1"], check=True)

    pids = tmp_path / "pids"
    scripts = {}
    for name, body in {
        "leader": '"$CHILD" &\nexec sleep 300\n',
        "child": 'setsid "$GRANDCHILD" &\nexec sleep 300\n',
        "grandchild": "exec sleep 300\n",
    }.items():
        script = tmp_path / f"{name}.sh"
        script.write_text(f'#!/bin/sh\necho "$$" >> "$PIDS"\n{body}')
        script.chmod(0o755)
        scripts[name] = script
    # The command must be a `agentctl-run` and one launch input, which is
    # what identifies a queued task's artifacts and the scope holding its
    # workload; anything else is another program that happens to be queued.
    wrapper = tmp_path / "agentctl-run"
    wrapper.write_text(
        f"#!/bin/sh\nexport PYTHONPATH={Path(__file__).parent}\n"
        f'exec {sys.executable} -m agentctl.run "$@"\n'
    )
    wrapper.chmod(0o755)
    launch_path = tmp_path / "reaped-job.json"
    launch_path.write_text(
        json.dumps(
            {
                "job_id": "reaped-job",
                "project_id": "fixture",
                "operation": "verify",
                "argv": [str(scripts["leader"])],
                "environment": {
                    "HOME": os.environ["HOME"],
                    "PATH": os.environ["PATH"],
                    "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
                    "PYTHONPATH": str(Path(__file__).parent),
                    "PIDS": str(pids),
                    "CHILD": str(scripts["child"]),
                    "GRANDCHILD": str(scripts["grandchild"]),
                },
                "working_directory": str(tmp_path),
                "timeout_seconds": 300,
                "result_kind": "exit",
                "label": "fixture:verify:reaped",
                "log_path": str(tmp_path / "reaped-job.log"),
            }
        )
    )
    config = Config(
        project_roots=(),
        agent_runner=tmp_path / "absent",
        worker_contract=tmp_path / "absent.md",
        event_spool=tmp_path / "events.jsonl",
        state_dir=tmp_path / "state",
        agentctl_executable="/fixture/agentctl",
    )
    task_id = pueue.add(
        group="pytest",
        label="fixture:verify:reaped",
        command=(str(wrapper), str(launch_path)),
        working_directory=tmp_path,
    )
    unrelated = pueue.add(
        group="default",
        label="fixture:unrelated:job",
        command=("sh", "-c", "sleep 4; exit 0"),
        working_directory=tmp_path,
    )
    deadline = time.monotonic() + 60
    while len(started := pids.read_text().split() if pids.exists() else []) < 3:
        assert time.monotonic() < deadline, (
            f"the workload never started: {(tmp_path / 'reaped-job.log').read_text()}"
        )
        time.sleep(0.1)
    descendants = [int(pid) for pid in started]
    unit = scope_unit_for(launch_path, "pytest")
    for pid in descendants:
        assert unit in Path(f"/proc/{pid}/cgroup").read_text(), (
            "a descendant outside the task's scope is one a cancel cannot reach"
        )

    cancelled = launch.cancel(config, task_id)

    assert cancelled["unit"] == unit
    assert cancelled["state"] == "stopped"
    assert pueue.wait(task_id, timeout_seconds=60).result in {"Killed", "Failed"}
    for pid in descendants:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    assert pueue.wait(unrelated, timeout_seconds=60).succeeded, (
        "cancelling one task must not disturb another"
    )
