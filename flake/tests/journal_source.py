"""Exercise the evaluated journal source script without touching host storage."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(sys.argv.pop()).read_text()


class JournalSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.parent = self.base / "state"
        self.parent.mkdir()
        self.root = self.parent / "journal"
        self.calls = self.base / "calls.jsonl"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        command = self.bin / "command"
        command.write_text(
            "#!" + sys.executable + "\n"
            "import json, os, pathlib, sys\n"
            "name = pathlib.Path(sys.argv[0]).name\n"
            "with open(os.environ['CALLS'], 'a') as f:\n"
            "    f.write(json.dumps([name, *sys.argv[1:]]) + '\\n')\n"
            "if name == 'btrfs':\n"
            "    if os.environ.get('FAIL_CREATE'): sys.exit(1)\n"
            "    pathlib.Path(sys.argv[-1]).mkdir()\n"
            "elif name == 'install': pathlib.Path(sys.argv[-1]).mkdir()\n"
        )
        command.chmod(0o755)
        for name in ("btrfs", "chown", "chmod", "install"):
            (self.bin / name).symlink_to(command)
        self.script = self.base / "script"
        self.script.write_text(
            SCRIPT.replace("/realm/state", str(self.parent))
        )

    def run_script(self, **extra):
        return subprocess.run(
            ["bash", "-e", str(self.script)],
            env={**os.environ, "PATH": str(self.bin) + ":" + os.environ["PATH"],
                 "CALLS": str(self.calls), **extra},
            capture_output=True,
            text=True,
        )

    def recorded_calls(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_absent_source_created_once_with_journal_permissions(self):
        self.assertEqual(self.run_script().returncode, 0)
        self.assertTrue(self.root.is_dir())
        self.assertEqual(self.recorded_calls(), [
            ["btrfs", "subvolume", "create", str(self.root)],
            ["chown", "root:systemd-journal", str(self.root)],
            ["chmod", "2755", str(self.root)],
        ])
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(len(self.recorded_calls()), 3)

    def test_absent_parent_is_provisioned(self):
        self.parent.rmdir()
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.recorded_calls()[0][0], "install")
        self.assertTrue(self.root.is_dir())

    def test_existing_store_keeps_bytes_and_metadata(self):
        self.root.mkdir(mode=0o700)
        payload = self.root / "retained.journal"
        payload.write_bytes(b"retained native journal fixture")
        before = self.root.stat(), payload.stat(), payload.read_bytes()
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(before, (self.root.stat(), payload.stat(), payload.read_bytes()))
        self.assertEqual(self.recorded_calls(), [])

    def test_wrong_source_types_refuse_without_mutation(self):
        for kind in ("file", "dangling-link", "directory-link"):
            with self.subTest(kind=kind):
                if kind == "file":
                    self.root.write_bytes(b"retained")
                else:
                    self.root.symlink_to(self.parent if kind == "directory-link" else "absent")
                before = self.root.lstat()
                self.assertNotEqual(self.run_script().returncode, 0)
                self.assertEqual(self.root.lstat(), before)
                self.assertEqual(self.recorded_calls(), [])
                self.root.unlink()

    def test_wrong_parent_types_refuse(self):
        self.parent.rmdir()
        for kind in ("file", "symlink"):
            with self.subTest(kind=kind):
                if kind == "file":
                    self.parent.write_bytes(b"retained")
                else:
                    self.parent.symlink_to(self.base)
                self.assertNotEqual(self.run_script().returncode, 0)
                self.assertEqual(self.recorded_calls(), [])
                self.parent.unlink()

    def test_creation_failure_does_not_change_permissions(self):
        self.assertNotEqual(self.run_script(FAIL_CREATE="1").returncode, 0)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.recorded_calls(), [
            ["btrfs", "subvolume", "create", str(self.root)],
        ])


if __name__ == "__main__":
    unittest.main()
