"""Publication and failed-byte preservation through the real scrollback script."""
import json
import os
from pathlib import Path
import socket
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
    print(json.dumps([{"tabs":[{"windows":[{"id":7,"title":"fixture","cwd":"/synthetic"}]}]}]))
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
        self.env = dict(os.environ, PATH=str(tools)+os.pathsep+os.environ["PATH"],
                        KITTY_SCROLLBACK_DIR=str(self.capture),
                        KITTY_SCROLLBACK_PROGRESS_MARKER=str(self.root/"progress"),
                        KITTY_LISTEN_ON="unix:/synthetic/kitty-host-123", KITTY_WINDOW_ID="7",
                        XDG_RUNTIME_DIR=str(self.root))
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(str(self.root / "kitty-host-123"))
        self.addCleanup(self.socket.close)

    def run_capture(self, mode, current=True):
        return subprocess.run(["bash", os.environ["KITTY_CAPTURE_SCRIPT"], *(["--current"] if current else [])],
                              env=dict(self.env, CAPTURE_TEST_MODE=mode),
                              text=True, capture_output=True, timeout=10, umask=0)

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


if __name__ == "__main__":
    unittest.main()
