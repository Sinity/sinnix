"""Native abort reproduction against an explicitly isolated pueue daemon."""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def test_quiet_wait_survives_closed_output_and_panic_reporting():
    with tempfile.TemporaryDirectory(prefix="pqclosed-") as directory:
        root = Path(directory)
        config = root / "pueue.yml"
        config.write_text(
            f"shared:\n  pueue_directory: {root / 'd'}\n"
            f"  runtime_directory: {root / 'r'}\n  use_unix_socket: true\n"
            "daemon:\n  default_parallel_tasks: 2\n"
        )
        (root / "d").mkdir()
        (root / "r").mkdir()
        command = ["pueue", "--config", str(config)]
        probe = subprocess.run([*command, "status", "--json"], capture_output=True)
        assert probe.returncode != 0, "private configuration reached another daemon"
        with (root / "daemon.log").open("w") as log:
            daemon = subprocess.Popen(
                ["pueued", "--config", str(config)], stdout=log, stderr=log
            )
            try:
                deadline = time.monotonic() + 10
                while subprocess.run(
                    [*command, "status", "--json"], capture_output=True
                ).returncode:
                    assert daemon.poll() is None
                    assert time.monotonic() < deadline
                    time.sleep(0.05)
                # Prevent this deliberate synthetic abort from creating a host core.
                launcher = root / "undumpable.py"
                launcher.write_text(
                    "import ctypes, os, sys\n"
                    "assert ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) == 0\n"
                    "os.execvp(sys.argv[1], sys.argv[1:])\n"
                )
                for mode in ("panic", "abort", "quiet"):
                    quiet = mode == "quiet"
                    added = subprocess.run(
                        [*command, "add", "--print-task-id", "sleep", "1"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    task_id = added.stdout.strip()
                    read_fd, write_fd = os.pipe()
                    os.close(read_fd)
                    args = [*command, "wait", *(["--quiet"] if quiet else []), task_id]
                    child = subprocess.Popen(
                        [sys.executable, str(launcher), *args],
                        stdout=write_fd,
                        stderr=subprocess.PIPE if mode == "panic" else write_fd,
                        env={**os.environ, "RUST_BACKTRACE": "full"},
                    )
                    os.close(write_fd)
                    try:
                        if mode == "panic":
                            _, captured = child.communicate(timeout=5)
                            assert b"failed printing to stdout: Broken pipe" in captured
                            assert child.returncode == 101
                        else:
                            assert child.wait(timeout=5) == (
                                0 if quiet else -signal.SIGABRT
                            )
                    finally:
                        if child.poll() is None:
                            child.kill()
                            child.wait(timeout=5)
                    finished = subprocess.run(
                        [*command, "wait", "--quiet", task_id],
                        capture_output=True,
                        timeout=5,
                    )
                    assert finished.returncode == 0
            finally:
                subprocess.run([*command, "shutdown"], capture_output=True, timeout=5)
                if daemon.poll() is None:
                    daemon.terminate()
                daemon.wait(timeout=5)
