from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from sinnixd.queue_run import (
    MAX_LOG_BYTES,
    REFUSED_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    main,
)


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
    # The private input carries a resolved environment and must not outlive it.
    assert not launch.exists()


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
    assert log.endswith("[sinnixd: output truncated]\n")


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


def test_a_checkout_that_no_longer_matches_its_binding_refuses(
    tmp_path: Path,
) -> None:
    """The binding is frozen at dispatch; a moved or spoofed checkout fails closed."""
    launch = write_launch(
        tmp_path,
        argv=["true"],
        checkout={
            "project_id": "fixture",
            "project_path": str(tmp_path),
            "checkout_id": "worktree-0123456789abcdef",
            "path": str(tmp_path / "absent"),
            "git_common_dir": str(tmp_path / ".git"),
            "head": "0" * 40,
        },
    )

    assert main([str(launch)]) == REFUSED_EXIT_CODE

    assert "checkout revalidation failed" in (tmp_path / "log").read_text()
    assert events(tmp_path) == []


def test_the_wrapper_records_the_group_its_command_leads(tmp_path: Path) -> None:
    """Cancel reaps that group; without the file the process tree survives.

    Anti-vacuity: `pueue kill` sends SIGKILL to its own group, which the
    command left, so this file is the only handle on what it started.
    """
    import os
    import signal
    import threading
    import time

    marker = tmp_path / "survivor"
    launch = write_launch(
        tmp_path,
        argv=["sh", "-c", f"(sleep 5; touch {marker}) & sleep 5"],
        timeout_seconds=60,
    )
    group_path = Path(str(tmp_path / "log") + ".pgid")
    result: list[int] = []
    worker = threading.Thread(target=lambda: result.append(main([str(launch)])))
    worker.start()
    deadline = time.monotonic() + 10
    while not group_path.exists():
        assert time.monotonic() < deadline, "the wrapper never recorded a group"
        time.sleep(0.05)

    pgid = int(group_path.read_text().strip())
    assert pgid != os.getpgrp(), "the command must lead its own group"
    os.killpg(pgid, signal.SIGKILL)
    worker.join(timeout=20)

    time.sleep(4)
    assert not marker.exists()
    assert not group_path.exists(), "a finished job leaves no stale group file"
