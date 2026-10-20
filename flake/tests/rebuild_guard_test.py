"""Exercise the exact guard payload referenced by the packaged executor."""

import gc
import importlib.util
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

GUARD = Path(sys.argv.pop(1))
line = next(
    line
    for line in GUARD.read_text().replace("\\\n", " ").splitlines()
    if line.startswith("exec ")
)
args = shlex.split(line)
assert args[0] == "exec" and args[3] == "--chrt" and args[-1] == "$@", args
SOURCE, CHRT = Path(args[2]), args[4]
spec = importlib.util.spec_from_file_location("rebuild_guard", SOURCE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class GuardTests(unittest.TestCase):
    def run_command(self, code):
        return guard.run_owned(
            os.getpid(),
            guard.start_ticks(os.getpid()),
            [sys.executable, "-c", code],
            CHRT,
        )

    def test_normal_completion_and_payload_cpu_policy(self):
        self.assertEqual(
            self.run_command(
                "import os; assert os.sched_getscheduler(0)==os.SCHED_BATCH"
            ),
            0,
        )

    def test_failure_and_signal_status_are_preserved(self):
        self.assertEqual(self.run_command("raise SystemExit(7)"), 7)
        self.assertEqual(
            self.run_command("import os,signal; os.kill(os.getpid(),signal.SIGTERM)"),
            143,
        )

    def test_reused_or_dead_caller_cannot_start_work(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "should-not-exist"
            argv = [
                sys.executable,
                "-c",
                f"from pathlib import Path; Path({str(marker)!r}).touch()",
            ]
            with self.assertRaises(guard.CallerGone):
                guard.run_owned(
                    os.getpid(), guard.start_ticks(os.getpid()) + 1, argv, CHRT
                )
            with subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"]
            ) as owner:
                ticks = guard.start_ticks(owner.pid)
                owner.terminate()
                owner.wait(timeout=5)
                with self.assertRaises(guard.CallerGone):
                    guard.run_owned(owner.pid, ticks, argv, CHRT)
            self.assertFalse(marker.exists())

    def test_unavailable_identity_is_not_reported_as_caller_exit(self):
        with patch.object(guard, "start_ticks", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                guard.run_owned(os.getpid(), 1, [sys.executable, "-c", "pass"], CHRT)

    def test_caller_exit_does_not_wait_for_surviving_workload(self):
        children = []
        spawn = os.posix_spawn

        def record(*args, **kwargs):
            pid = spawn(*args, **kwargs)
            children.append(pid)
            return pid

        with subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"]
        ) as owner:
            ticks = guard.start_ticks(owner.pid)
            try:
                code = f"import os,signal,time; os.kill({owner.pid},signal.SIGKILL); time.sleep(30)"
                with patch.object(os, "posix_spawn", side_effect=record):
                    with self.assertRaises(guard.CallerGone):
                        guard.run_owned(
                            owner.pid, ticks, [sys.executable, "-c", code], CHRT
                        )
                self.assertEqual(len(children), 1)
            finally:
                # In production systemd reaps the cgroup when its main guard
                # exits. This unit-free test explicitly owns these child PIDs.
                for pid in children:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.waitpid(pid, 0)
                if owner.poll() is None:
                    owner.kill()

    def test_pidfds_close_without_garbage_collection(self):
        self.run_command("pass")
        before = len(list(Path("/proc/self/fd").iterdir()))
        enabled = gc.isenabled()
        gc.disable()
        try:
            for _ in range(12):
                self.assertEqual(self.run_command("pass"), 0)
            self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), before)
        finally:
            if enabled:
                gc.enable()

    def test_cli_refuses_execution_outside_native_main_process(self):
        env = dict(os.environ)
        env.pop("SYSTEMD_EXEC_PID", None)
        result = subprocess.run(
            [
                str(GUARD),
                "--owner-pid",
                str(os.getpid()),
                "--owner-start-ticks",
                str(guard.start_ticks(os.getpid())),
                "--",
                sys.executable,
                "-c",
                "pass",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 64, result.stderr)
        self.assertIn("native service main process", result.stderr)


if __name__ == "__main__":
    unittest.main()
