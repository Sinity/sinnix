"""The pueue adapter, exercised against payloads recorded from pueue 4.0.4.

The stub replays documents captured from the live daemon rather than shapes
invented here, and records the argv it was called with, so a wrong flag or a
misread enum fails.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest
from sinnixd import pueue

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
        "agent": {"status": "Running", "parallel_tasks": 4},
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
        command=("sinnixd-queue-run", "input.json"),
        working_directory=tmp_path,
        after=(3, 5),
    )

    assert task_id == 7
    assert _calls(stub_pueue)[0] == [
        "add",
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
        "sinnixd-queue-run",
        "input.json",
    ]


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
    assert pueue.groups() == {"agent": 4, "bulk": 1, "default": 1, "pytest": 1}


def test_log_returns_one_task_captured_output(stub_pueue: Path) -> None:
    assert pueue.log(0) == "\nerr"


def test_freeze_and_resume_name_the_group(stub_pueue: Path) -> None:
    pueue.pause("agent")
    pueue.resume("agent")

    assert _calls(stub_pueue) == [
        ["pause", "--group", "agent"],
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
