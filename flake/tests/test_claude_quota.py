import argparse
import contextlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.module = runpy.run_path("scripts/claude-quota")
        self.ns = self.module["history"].__globals__

    def test_missing_windows_status(self):
        for sample in ({"ts": 0, "five_hour": 12, "seven_day": None},
                       {"ts": 0, "five_hour": None, "seven_day": 20}):
            output = io.StringIO()
            with patch.dict(self.ns, fetch=lambda: sample, record=lambda _: None,
                            history=lambda: []), contextlib.redirect_stdout(output):
                self.assertEqual(self.module["cmd_status"](argparse.Namespace(json=False)), 0)
            self.assertIn("unknown", output.getvalue())
            self.assertNotIn("(in 0h00m)", output.getvalue())

    def test_missing_five_hour_has_no_burn_projection(self):
        with patch.dict(self.ns, history=lambda: [{"ts": 0, "five_hour": 10}]):
            self.assertIsNone(self.module["burn_rate"]({"ts": 1800, "five_hour": None}))

    def test_bounded_tail_and_incomplete_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.jsonl"
            row = {"ts": 123, "five_hour": 10}
            path.write_bytes(b"\xc3\xa9" * self.ns["HISTORY_BYTES"] + b"\n" +
                             json.dumps(row).encode() + b'\n[]\n{}\n{"ts":')
            original_open = Path.open
            reads = []

            class BoundedReader:
                def __enter__(self): return self
                def __exit__(self, *args): self.handle.close()
                def seek(self, *args): return self.handle.seek(*args)
                def read(self, size=-1):
                    self.assert_bound(size)
                    reads.append(size)
                    return self.handle.read(size)

            def opened(target, *args, **kwargs):
                reader = BoundedReader()
                reader.handle = original_open(target, *args, **kwargs)
                reader.assert_bound = lambda size: self.assertGreaterEqual(size, 0)
                return reader

            with patch.dict(self.ns, SAMPLES=path), patch.object(Path, "open", opened):
                self.assertEqual(self.module["history"](), [row])
            self.assertLessEqual(sum(reads), self.ns["HISTORY_BYTES"] + 1)

    def test_tail_retains_last_2000_complete_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.jsonl"
            path.write_text("".join(json.dumps({"ts": n}) + "\n" for n in range(2100)))
            with patch.dict(self.ns, SAMPLES=path):
                rows = self.module["history"]()
            self.assertEqual(len(rows), 2000)
            self.assertEqual(rows[0]["ts"], 100)
            self.assertEqual(rows[-1]["ts"], 2099)


if __name__ == "__main__":
    unittest.main()
