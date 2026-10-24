"""Job scratch outlives its active unit, not failed result bookkeeping."""

from __future__ import annotations

import fcntl
import json
import sys
import time
from pathlib import Path

import pytest
from agentctl import run
from test_run import outcome_of, user_manager, write_launch


def scratch_launch(tmp_path, monkeypatch, **overrides):
    root = tmp_path / "scratch"
    monkeypatch.setenv("AGENTCTL_TMPFS_SCRATCH_ROOT", str(root))
    path = root / "job-a"
    return path, write_launch(
        tmp_path, scratch={"kind": "tmpfs", "path": str(path)}, **overrides
    )


def test_post_exit_bookkeeping_failure_still_removes_owned_scratch(
    tmp_path, monkeypatch
):
    scratch, launch = scratch_launch(
        tmp_path, monkeypatch, argv=["sh", "-c", 'printf synthetic > "$TMPDIR/fixture"']
    )

    def fail_mask(*_args):
        raise RuntimeError("synthetic post-exit failure")

    monkeypatch.setattr(run, "_mask_logs", fail_mask)
    with pytest.raises(RuntimeError, match="synthetic post-exit failure"):
        run.main([str(launch)])
    assert not scratch.exists()
    assert (tmp_path / "job-a.log").exists()


@pytest.mark.parametrize("can_stop", [True, False])
def test_failed_unit_observation_stops_before_cleanup_or_retains_ownership(
    tmp_path, monkeypatch, can_stop
):
    user_manager()
    ready = tmp_path / "ready"
    code = (
        "import os,signal;from pathlib import Path;"
        'Path(os.environ["TMPDIR"],"fixture").write_text("synthetic");'
        f"Path({str(ready)!r}).write_text(str(os.getpid()));signal.pause()"
    )
    scratch, launch = scratch_launch(
        tmp_path, monkeypatch, pool="fixture", argv=[sys.executable, "-c", code]
    )
    unit = run.unit_for(launch, "fixture")
    original_start, original_ctl = run._start_service, run._systemctl

    def start(*args, **kwargs):
        result = original_start(*args, **kwargs)
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists()
        return result

    def fail_observation(*_args):
        raise OSError("synthetic observation failure")

    def ctl(*args):
        if not can_stop and args[0] == "stop" and args[-1] == unit:
            return None
        return original_ctl(*args)

    monkeypatch.setattr(run, "_start_service", start)
    monkeypatch.setattr(run, "_wait_for_unit", fail_observation)
    monkeypatch.setattr(run, "_systemctl", ctl)
    try:
        assert run.main([str(launch)]) == run.REFUSED_EXIT_CODE
        pid = int(ready.read_text())
        if can_stop:
            assert not Path(f"/proc/{pid}").exists(), (
                "the native child must exit before scratch is removed"
            )
            assert not scratch.exists()
        else:
            assert Path(f"/proc/{pid}").exists()
            assert (scratch / "fixture").read_text() == "synthetic"
            record = outcome_of(tmp_path)
            assert record["unit"] == unit
            assert "cleanup_error" in record["scratch"]
    finally:
        original_ctl("stop", unit)
        original_ctl("reset-failed", unit)


@pytest.mark.parametrize("exit_code", [0, 7])
def test_command_result_survives_scratch_cleanup(tmp_path, monkeypatch, exit_code):
    scratch, launch = scratch_launch(
        tmp_path,
        monkeypatch,
        argv=[
            sys.executable,
            "-c",
            'import os,sys;from pathlib import Path;Path(os.environ["TMPDIR"],"fixture").write_text("synthetic");print("retained command output");sys.exit(int(sys.argv[1]))',
            str(exit_code),
        ],
    )
    assert run.main([str(launch)]) == exit_code
    assert outcome_of(tmp_path)["exit_code"] == exit_code
    assert not scratch.exists()
    assert (tmp_path / "job-a.log").read_text() == "retained command output\n"


@pytest.mark.parametrize("cancel", [False, True])
def test_native_timeout_and_cancellation_remove_only_stopped_scratch(
    tmp_path, monkeypatch, cancel
):
    user_manager()
    ready = tmp_path / "ready"
    code = (
        "import os,signal;from pathlib import Path;"
        'Path(os.environ["TMPDIR"],"fixture").write_text("synthetic");'
        f"Path({str(ready)!r}).write_text(str(os.getpid()));signal.pause()"
    )
    scratch, launch = scratch_launch(
        tmp_path,
        monkeypatch,
        pool="fixture",
        timeout_seconds=1 if not cancel else 30,
        argv=[sys.executable, "-c", code],
    )
    unit = run.unit_for(launch, "fixture")
    original_start = run._start_service
    if cancel:

        def start(*args, **kwargs):
            result = original_start(*args, **kwargs)
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert ready.exists()
            marker = run.cancel_marker_for(tmp_path / "job-a.log")
            with (tmp_path / "job-a.attempts" / ".allocation.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                marker.write_text(json.dumps({"attempt": 1}))
                run._systemctl("stop", unit)
            return result

        monkeypatch.setattr(run, "_start_service", start)
    try:
        expected = run.CANCELLED_EXIT_CODE if cancel else run.TIMEOUT_EXIT_CODE
        assert run.main([str(launch)]) == expected
        assert ready.exists()
        assert not Path(f"/proc/{int(ready.read_text())}").exists()
        assert not scratch.exists()
        assert outcome_of(tmp_path)["scratch"]["bytes"] == len("synthetic")
    finally:
        run._systemctl("stop", unit)
        run._systemctl("reset-failed", unit)
