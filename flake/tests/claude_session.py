"""Exports must preserve raw sessions and previous verified output."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HELPER = os.environ["SESSION_HELPER"]
RECORD = (
    json.dumps({"type": "user", "message": {"content": "Synthetic statement"}}) + "\n"
)


class SessionExports(unittest.TestCase):
    def run_helper(self, source, output=None):
        command = [sys.executable, HELPER, "prose", str(source)]
        if output is not None:
            command += ["--out", str(output)]
        return subprocess.run(command, capture_output=True, text=True, timeout=5)

    def test_input_aliases_refused_without_mutation(self):
        for kind in ("same", "hardlink", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                source = Path(temp) / "session.jsonl"
                source.write_text(RECORD)
                output = source if kind == "same" else Path(temp) / "alias"
                if kind == "hardlink":
                    os.link(source, output)
                elif kind == "symlink":
                    output.symlink_to(source)
                result = self.run_helper(source, output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(source.read_text(), RECORD)

    def test_success_is_private_and_preserves_raw_input(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "session.jsonl"
            source.write_text(RECORD)
            output = Path(temp) / "export.md"
            output.write_text("old export")
            output.chmod(0o644)
            result = self.run_helper(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Synthetic statement", output.read_text())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(source.read_text(), RECORD)
            self.assertIn("wrote", result.stderr)

    def test_read_only_export_is_not_overwritten(self):
        if os.geteuid() == 0:
            self.skipTest("root can write read-only files")
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "session.jsonl"
            source.write_text(RECORD)
            output = Path(temp) / "export.md"
            output.write_text("read-only retained export")
            output.chmod(0o444)
            result = self.run_helper(source, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), "read-only retained export")
            self.assertEqual(output.stat().st_mode & 0o777, 0o444)

    def test_read_failure_retains_previous_export(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "session.jsonl"
            raw = RECORD + "[]\n"
            source.write_text(raw)
            output = Path(temp) / "export.md"
            output.write_text("previous verified export")
            result = self.run_helper(source, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), "previous verified export")
            self.assertEqual(source.read_text(), raw)
            self.assertNotIn("wrote", result.stderr)
            self.assertEqual(
                sorted(p.name for p in Path(temp).iterdir()),
                ["export.md", "session.jsonl"],
            )

    def test_stdout_prose_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "session.jsonl"
            source.write_text(RECORD)
            result = self.run_helper(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## USER", result.stdout)
            self.assertIn("Synthetic statement", result.stdout)
            self.assertEqual(source.read_text(), RECORD)

    def test_inherited_ignored_signal_is_preserved(self):
        code = r"""import importlib.machinery,importlib.util,signal,sys
loader=importlib.machinery.SourceFileLoader("helper",sys.argv[1])
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec);loader.exec_module(module)
signal.signal(signal.SIGHUP,signal.SIG_IGN)
def inspect(args):
 assert signal.getsignal(signal.SIGHUP)==signal.SIG_IGN
module.cmd_list=inspect
sys.argv=["helper","list"]
module.main()
"""
        result = subprocess.run(
            [sys.executable, "-c", code, HELPER],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cancel_retains_previous_export_and_removes_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output, ready = (
                root / "session.jsonl",
                root / "export.md",
                root / "ready",
            )
            source.write_text(RECORD)
            output.write_text("previous verified export")
            code = r"""import importlib.machinery,importlib.util,json,sys,time
from pathlib import Path
helper,source,output,ready=sys.argv[1:]
loader=importlib.machinery.SourceFileLoader("helper",helper)
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec);loader.exec_module(module)
def records(path):
 yield {"type":"user","message":{"content":"Synthetic statement"}}
 Path(ready).touch()
 time.sleep(60)
module.iter_records=records
sys.argv=[helper,"prose",source,"--out",output]
module.main()
"""
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    code,
                    HELPER,
                    str(source),
                    str(output),
                    str(ready),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 3
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(ready.exists())
                process.send_signal(signal.SIGTERM)
                process.communicate(timeout=3)
                self.assertNotEqual(process.returncode, 0)
                self.assertEqual(output.read_text(), "previous verified export")
                self.assertEqual(source.read_text(), RECORD)
                self.assertEqual(
                    sorted(p.name for p in root.iterdir()),
                    ["export.md", "ready", "session.jsonl"],
                )
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()


unittest.main()
