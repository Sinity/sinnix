"""Literal, serialized journal appends and private file creation."""

import fcntl
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/rawlog"


def test_new_journal_is_owner_only(tmp_path):
    log = tmp_path / "raw-log.md"
    binary = tmp_path / "bin"
    binary.mkdir()
    notify = binary / "notify-send"
    notify.write_text("#!/bin/sh\nexit 0\n")
    notify.chmod(0o755)
    result = subprocess.run(
        ["bash", str(SCRIPT), "neutral fixture entry"],
        env={
            **os.environ,
            "RAWLOG_FILE": str(log),
            "PATH": str(binary) + ":" + os.environ["PATH"],
        },
        capture_output=True,
        text=True,
        umask=0,
    )
    assert result.returncode == 0, result.stderr
    assert log.stat().st_mode & 0o777 == 0o600
    assert "neutral fixture entry" in log.read_text()


def journal_env(tmp_path, notify_status=0):
    binary = tmp_path / "tools"
    binary.mkdir()
    notify = binary / "notify-send"
    notify.write_text(
        f"#!{sys.executable}\n"
        + """
import os,pathlib,sys
pathlib.Path(os.environ['NOTIFY_MARKER']).touch()
sys.exit(int(os.environ['NOTIFY_STATUS']))
"""
    )
    notify.chmod(0o755)
    log = tmp_path / "journal.md"
    env = {
        "PATH": f"{binary}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "RAWLOG_FILE": str(log),
        "NOTIFY_STATUS": str(notify_status),
        "NOTIFY_MARKER": str(tmp_path / "notified"),
    }
    return log, env


@pytest.mark.parametrize("message", ["-e", "-n", "-E"])
def test_option_shaped_messages_are_literal_entries(tmp_path, message):
    log, env = journal_env(tmp_path)
    result = subprocess.run(
        ["bash", str(SCRIPT), message], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert log.exists(), "literal entry was discarded"
    assert log.read_text().splitlines()[-1].endswith(" " + message)


def test_notification_failure_does_not_report_a_saved_entry_as_failed(tmp_path):
    log, env = journal_env(tmp_path, notify_status=7)
    result = subprocess.run(
        ["bash", str(SCRIPT), "neutral entry"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "notified").exists()
    assert log.read_text().count("neutral entry") == 1


def test_appenders_respect_journal_lock_and_initialize_once(tmp_path):
    log, env = journal_env(tmp_path)
    ready = tmp_path / "ready"
    ready.mkdir()
    date = tmp_path / "tools" / "date"
    date.write_text(
        f"#!{sys.executable}\n"
        + """
import os,pathlib,sys
(pathlib.Path(os.environ['READY']) / str(os.getpid())).touch()
os.execv(os.environ['REAL_DATE'], [os.environ['REAL_DATE'], *sys.argv[1:]])
"""
    )
    date.chmod(0o755)
    env.update(READY=str(ready), REAL_DATE=shutil.which("date"))
    processes = []
    try:
        with log.open("ab") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                for message in ("first neutral entry", "second neutral entry"):
                    processes.append(
                        subprocess.Popen(
                            ["bash", str(SCRIPT), message],
                            env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            start_new_session=True,
                        )
                    )
                deadline = time.monotonic() + 5
                while len(list(ready.iterdir())) < 2:
                    assert time.monotonic() < deadline, (
                        "appenders never reached the write phase"
                    )
                    time.sleep(0.01)
                time.sleep(0.1)
                assert log.read_bytes() == b"", (
                    "appender bypassed the held journal lock"
                )
                assert all(proc.poll() is None for proc in processes)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        for proc in processes:
            proc.communicate(timeout=5)
            assert proc.returncode == 0
        text = log.read_text()
        assert text.count("id: logs.raw-log") == 1
        assert (
            text.count("first neutral entry") == text.count("second neutral entry") == 1
        )
    finally:
        for proc in processes:
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate(timeout=5)


def test_fifo_journal_target_is_refused_without_blocking(tmp_path):
    log, env = journal_env(tmp_path)
    os.mkfifo(log)
    result = subprocess.run(
        ["bash", str(SCRIPT), "neutral entry"],
        env=env,
        capture_output=True,
        text=True,
        timeout=2,
    )
    assert result.returncode != 0


def test_existing_journal_prefix_and_inode_are_preserved(tmp_path):
    log, env = journal_env(tmp_path)
    before = b"---\nid: logs.raw-log\n---\n\n# Raw log\n\n- **2000-01-01 00:00:00** retained fixture\n"
    log.write_bytes(before)
    inode = log.stat().st_ino
    result = subprocess.run(
        ["bash", str(SCRIPT), "new neutral entry"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert log.read_bytes().startswith(before)
    assert log.stat().st_ino == inode
    assert log.read_text().count("id: logs.raw-log") == 1
