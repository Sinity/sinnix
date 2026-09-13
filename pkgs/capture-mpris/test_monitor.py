"""Regression coverage for the MPRIS shared subprocess boundary."""

from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from sinnix_lib.process import run


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
