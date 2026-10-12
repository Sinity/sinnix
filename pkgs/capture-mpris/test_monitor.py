"""Regression coverage for the MPRIS shared subprocess boundary."""

import sys
import json
import tempfile
import threading
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

from sinnix_lib.process import Result, run

MONITOR = SourceFileLoader(
    "capture_mpris_monitor", str(Path(__file__).with_name("monitor.py"))
).load_module()


class MonitorTest(unittest.TestCase):
    def test_timeout_becomes_missing_position_and_duration(self):
        timeout = run(
            [sys.executable, "-c", "import time; time.sleep(1)"], timeout=0.01
        )
        self.assertIsNotNone(timeout.error)

        with patch.object(MONITOR, "run", return_value=timeout):
            self.assertEqual(
                MONITOR.fetch_position_and_duration("playerctl", "demo"),
                (None, None),
            )


    def test_slow_inflight_write_keeps_changes_and_coalesces_only_waiting_heartbeats(self):
        entered, release = threading.Event(), threading.Event()
        writes = []
        def capture(_binary, _root, _lane, payload, ts):
            if not writes:
                entered.set()
                self.assertTrue(release.wait(5))
            writes.append((ts, payload.copy()))
        with patch.object(MONITOR, "write_envelope", side_effect=capture):
            writer = MONITOR.EnvelopeWriter("capture", "root", "mpris")
            try:
                writer.enqueue({"event": "track", "player": "fixture", "title": "A"}, 1.0)
                self.assertTrue(entered.wait(5))
                writer.enqueue({"event": "status", "player": "fixture", "title": "A", "status": "Paused"}, 2.0)
                writer.enqueue({"event": "track", "player": "fixture", "title": "B"}, 3.0)
                writer.enqueue({"event": "heartbeat", "player": "fixture", "title": "B", "position_seconds": 4}, 4.0)
                writer.enqueue({"event": "heartbeat", "player": "fixture", "title": "B", "position_seconds": 5}, 5.0)
                self.assertEqual(len(writer.pending), 4)
            finally:
                release.set()
                writer.close()
        self.assertEqual([ts for ts, _ in writes], [1.0, 2.0, 3.0, 5.0])
        self.assertEqual([p["event"] for _, p in writes], ["track", "status", "track", "heartbeat"])

    def test_failed_write_retains_pending_without_blind_retry(self):
        with patch.object(MONITOR, "write_envelope", side_effect=RuntimeError("ambiguous failure")) as capture:
            writer = MONITOR.EnvelopeWriter("capture", "root", "mpris")
            writer.enqueue({"event": "track", "title": "fixture"}, 1.0)
            writer.close()
            self.assertIsInstance(writer.failure, RuntimeError)
            self.assertEqual(len(writer.pending), 1)
            self.assertEqual(capture.call_count, 1)

    def test_write_waits_past_old_timeout_and_preserves_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "capture"
            receipt = Path(directory) / "receipt.json"
            stub.write_text(f"#!{sys.executable}\nimport json,sys,time\ntime.sleep(10.2)\nopen({str(receipt)!r}, 'w').write(json.dumps(sys.argv[1:]))\n")
            stub.chmod(0o700)
            MONITOR.write_envelope(str(stub), directory, "mpris", {"event": "track", "title": "fixture"}, 123.25)
            argv = json.loads(receipt.read_text())
            self.assertEqual(argv[-2:], ["--ts", "123.25"])
            self.assertEqual(json.loads(argv[argv.index("--payload") + 1])["title"], "fixture")


    def test_invalid_player_metadata_does_not_discard_the_event(self):
        for value in ("not a number", "nan", "inf"):
            result = Result(("playerctl",), 0, value, "")
            with patch.object(MONITOR, "run", return_value=result):
                self.assertEqual(MONITOR.fetch_position_and_duration("playerctl", "fixture"), (None, None))
