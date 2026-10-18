"""Publication and failed-byte preservation through the real scrollback script."""
import json
import os
from pathlib import Path
import socket
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest


class ScrollbackCapture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.capture = self.root / "captures"
        tools = self.root / "bin"
        tools.mkdir()
        kitty = tools / "kitty"
        kitty.write_text(f"#!{sys.executable}\n" + '''import json,os,sys
if "ls" in sys.argv:
    failure=os.environ.get("KITTY_TEST_LS_FAILURE")
    if failure:
        target=sys.argv[sys.argv.index("--to")+1]
        path=target.removeprefix("unix:")
        reasons={"refused":"connection refused", "missing":"no such file or directory",
                 "permission denied":"permission denied"}
        if failure in reasons:
            reason=reasons[failure]
            sys.stderr.write(f"Error: Failed to connect to {target} with error: dial unix {path}: connect: {reason}\\n")
        else:
            sys.stderr.write(f"Error: {failure}\\n")
        sys.exit(1)
    print(os.environ.get("KITTY_TEST_INVENTORY", json.dumps([{"tabs":[{"windows":[{"id":7,"title":"fixture","cwd":"/synthetic"}]}]}])))
else:
    mode=os.environ["CAPTURE_TEST_MODE"]
    sys.stdout.write("complete scrollback" if mode=="success" else "partial bytes" if mode=="partial" else "")
    if mode!="success":
        sys.stderr.write("Error: No matching windows for expression: id:7\\n" if mode=="closed" else "capture transport failed\\n")
        sys.exit(1)
''')
        kitty.chmod(0o700)
        date = tools / "date"
        date.write_text(f"#!{sys.executable}\nprint('20260101T010203Z')\n")
        date.chmod(0o700)
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.env = dict(PATH=str(tools)+os.pathsep+os.environ["PATH"], HOME=str(self.root),
                        TMPDIR=str(self.scratch),
                        KITTY_SCROLLBACK_DIR=str(self.capture),
                        KITTY_SCROLLBACK_PROGRESS_MARKER=str(self.root/"progress"),
                        KITTY_LISTEN_ON="unix:/synthetic/kitty-host-123", KITTY_WINDOW_ID="7",
                        XDG_RUNTIME_DIR=str(self.root))
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(str(self.root / "kitty-host-123"))
        self.addCleanup(self.socket.close)

    def run_capture(self, mode, current=True):
        command = ["bash", os.environ["KITTY_CAPTURE_SCRIPT"], *(["--current"] if current else [])]
        with subprocess.Popen(command, env=dict(self.env, CAPTURE_TEST_MODE=mode),
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=True, umask=0) as process:
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

    def test_success_publishes_complete_bytes_and_metadata(self):
        result = self.run_capture("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        output, = self.capture.glob("*.ansi")
        self.assertEqual(output.read_text(), "complete scrollback")
        metadata = json.loads(output.with_suffix(".meta.json").read_text())
        self.assertEqual(metadata["ansi_file"], output.name)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertTrue((self.root/"progress").exists())
        self.assertFalse(list(self.capture.glob(".capture-*")))

    def test_failed_capture_retains_partial_bytes_without_publication(self):
        result = self.run_capture("partial")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(list(self.capture.glob("*.ansi")))
        output, = self.capture.glob(".capture-output.*")
        self.assertEqual(output.read_text(), "partial bytes")
        error, = self.capture.glob(".capture-error.*")
        self.assertIn("capture transport failed", error.read_text())
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root/"progress").exists())

    def test_empty_failure_is_distinct_from_closed_window(self):
        self.assertEqual(self.run_capture("failure").returncode, 1)
        self.assertTrue(list(self.capture.glob(".capture-error.*")))
        self.assertFalse((self.root/"progress").exists())

    def test_closed_empty_window_is_benign_and_leaves_no_artifacts(self):
        self.assertEqual(self.run_capture("closed").returncode, 2)
        self.assertEqual(list(self.capture.iterdir()), [])
        self.assertFalse((self.root/"progress").exists())

    def test_batch_reports_progress_publication_failure(self):
        self.env["KITTY_SCROLLBACK_PROGRESS_MARKER"] = str(self.root/"missing"/"progress")
        result = self.run_capture("success", current=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(list(self.capture.glob("*.ansi"))), 1)
        self.assertIn("1 failed", result.stdout)

    def test_directory_target_is_refused_without_writing_inside_it(self):
        self.assertEqual(self.run_capture("success").returncode, 0)
        output, = self.capture.glob("*.ansi")
        output.unlink()
        output.mkdir()
        self.assertEqual(self.run_capture("success").returncode, 1)
        self.assertEqual(list(output.iterdir()), [])
        staged, = self.capture.glob(".capture-output.*")
        self.assertEqual(staged.read_text(), "complete scrollback")

    def test_batch_reports_metadata_publication_failure(self):
        self.capture.mkdir()
        name = "20260101T010203Z-" + socket.gethostname() + "-pid123-win7-fixture.meta.json"
        (self.capture/name).mkdir()
        result = self.run_capture("success", current=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("✓", result.stdout)
        self.assertFalse((self.root/"progress").exists())

    def test_filename_collision_preserves_previous_capture(self):
        self.assertEqual(self.run_capture("success").returncode, 0)
        output, = self.capture.glob("*.ansi")
        output.write_text("previous capture")
        self.assertEqual(self.run_capture("success").returncode, 1)
        self.assertEqual(output.read_text(), "previous capture")
        staged, = self.capture.glob(".capture-output.*")
        self.assertEqual(staged.read_text(), "complete scrollback")

    def check_metadata_collision(self, kind):
        self.capture.mkdir()
        name = "20260101T010203Z-" + socket.gethostname() + "-pid123-win7-fixture.meta.json"
        metadata = self.capture / name
        target = self.root / "preserved"
        target.write_text("prior evidence")
        if kind == "symlink":
            metadata.symlink_to(target)
        elif kind == "fifo":
            os.mkfifo(metadata)
        else:
            metadata.write_text("existing sidecar")
        identity = metadata.lstat()
        result = self.run_capture("success")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(target.read_text(), "prior evidence")
        self.assertEqual(metadata.lstat(), identity)
        if kind != "fifo":
            self.assertEqual(metadata.read_text(), "prior evidence" if kind == "symlink" else "existing sidecar")
        staged, = self.capture.glob(".capture-metadata.*")
        self.assertEqual(json.loads(staged.read_text())["window_id"], 7)
        self.assertEqual(staged.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / "progress").exists())

    def test_metadata_collision_preserves_existing_file(self):
        self.check_metadata_collision("file")

    def test_metadata_collision_preserves_symlink_target(self):
        self.check_metadata_collision("symlink")

    def test_metadata_fifo_is_refused_without_waiting_for_a_reader(self):
        self.check_metadata_collision("fifo")


    def test_batch_refuses_malformed_inventory_without_capture(self):
        for payload in ("", "[]\n[]", "not json", "{}", '[{"tabs":[{"windows":[{"title":"missing id"}]}]}]'):
            with self.subTest(payload=payload):
                self.env["KITTY_TEST_INVENTORY"] = payload
                result = self.run_capture("success", current=False)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(list(self.capture.glob("*.ansi")))
                self.assertFalse((self.root / "progress").exists())

    def test_only_proven_stale_transport_errors_are_benign(self):
        for failure, expected in (("refused", 0), ("missing", 0),
                                  ("permission denied", 1), ("remote control disabled", 1),
                                  ("unknown transport failure", 1)):
            with self.subTest(failure=failure):
                self.env["KITTY_TEST_LS_FAILURE"] = failure
                result = self.run_capture("success", current=False)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertFalse(list(self.capture.glob("*.ansi")))
                self.assertFalse(list(self.capture.glob(".inventory-error.*")))
                self.assertFalse((self.root / "progress").exists())

    def test_empty_batch_inventory_is_valid(self):
        self.env["KITTY_TEST_INVENTORY"] = "[]"
        self.assertEqual(self.run_capture("success", current=False).returncode, 0)
        self.assertFalse(list(self.capture.glob("*.ansi")))

    def test_unavailable_runtime_directory_refuses_and_cleans_staging(self):
        for kind in ("missing", "denied", "file"):
            with self.subTest(kind=kind):
                runtime = self.root / kind
                if kind == "denied":
                    runtime.mkdir()
                    runtime.chmod(0)
                elif kind == "file":
                    runtime.touch()
                self.env["XDG_RUNTIME_DIR"] = str(runtime)
                try:
                    result = self.run_capture("success", current=False)
                finally:
                    if kind == "denied":
                        runtime.chmod(0o700)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(list(self.scratch.iterdir()), [])
                self.assertFalse((self.root / "progress").exists())

    def test_explicit_runtime_directory_link_is_scanned(self):
        alias = self.root / "runtime-link"
        alias.symlink_to(self.root, target_is_directory=True)
        self.env["XDG_RUNTIME_DIR"] = str(alias)
        result = self.run_capture("success", current=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(self.capture.glob("*.ansi"))), 1)

    def test_socket_inventory_uses_declared_writable_capture_home(self):
        blocked = self.root / "unwritable-scratch"
        blocked.mkdir()
        blocked.chmod(0)
        self.env["TMPDIR"] = str(blocked)
        try:
            result = self.run_capture("success", current=False)
        finally:
            blocked.chmod(0o700)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(self.capture.glob("*.ansi"))), 1)
        self.assertFalse(list(self.capture.glob(".socket-listing.*")))

    def test_second_allocation_failure_leaves_no_empty_error_file(self):
        wrapper = self.root / "bin" / "mktemp"
        wrapper.write_text(f"#!{sys.executable}\n" + """
import os,sys
if any('.capture-output.' in arg for arg in sys.argv[1:]):
    sys.exit(1)
os.execv(os.environ['REAL_MKTEMP'], [os.environ['REAL_MKTEMP'], *sys.argv[1:]])
""")
        wrapper.chmod(0o700)
        self.env["REAL_MKTEMP"] = shutil.which("mktemp")
        self.assertEqual(self.run_capture("success").returncode, 1)
        self.assertFalse(list(self.capture.glob(".capture-*")))


if __name__ == "__main__":
    unittest.main()
