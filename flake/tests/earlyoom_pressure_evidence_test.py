"""Readiness and numeric journal cases use neutral synthetic metadata."""

import importlib.util
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from earlyoom_pressure_evidence import daemon_decision, validate_helper

spec = importlib.util.spec_from_file_location(
    "pressure_fixture", Path(__file__).with_name("earlyoom_real_pressure.py")
)
assert spec and spec.loader
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class Evidence(unittest.TestCase):
    def test_ready_go_and_deadline(self):
        with tempfile.TemporaryDirectory(dir="/realm/tmp/work") as directory:
            out = Path(directory)
            result = []
            worker = threading.Thread(
                target=lambda: result.append(
                    fixture.wait_for_go(out, "test", timeout=2)
                )
            )
            worker.start()
            deadline = time.monotonic() + 2
            while not (out / "test.ready").exists():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.001)
            self.assertFalse(result)
            ready = json.loads((out / "test.ready").read_text())
            self.assertGreater(ready["pid"], 0)
            self.assertGreater(int(ready["start_ticks"]), 0)
            (out / "go").write_text("12.5")
            worker.join(2)
            self.assertEqual(result, [12.5])
        with tempfile.TemporaryDirectory(dir="/realm/tmp/work") as directory:
            with self.assertRaisesRegex(AssertionError, "barrier expired"):
                fixture.wait_for_go(Path(directory), "timeout", timeout=0)

    def test_before_stop_outcomes(self):
        active = {
            "CollectMode": "inactive",
            "Result": "success",
            "ActiveState": "active",
            "MainPID": "42",
            "ExecMainStatus": "0",
        }
        validate_helper("pressure-sampler.service", active)
        completed = active | {"ActiveState": "inactive", "MainPID": "0"}
        validate_helper("pressure-transition.service", completed)
        validate_helper("pressure-io.service", completed)
        for unit, changes in [
            (
                "pressure-transition.service",
                {"Result": "exit-code", "ExecMainStatus": "1"},
            ),
            ("pressure-transition.service", {"CollectMode": "inactive-or-failed"}),
            ("pressure-sampler.service", {"ActiveState": "inactive", "MainPID": "0"}),
            ("pressure-io.service", {"Result": "timeout"}),
        ]:
            with self.assertRaises(AssertionError):
                validate_helper(unit, active | changes)

    def test_strict_daemon_block(self):
        messages = [
            "memory PSI full avg10 18.08 >= 10.00: kills enabled again",
            "mem avail: 71 of 1466 MiB (4.89%), swap free: 0 of 127 MiB (0.07%)",
            "low memory! at or below SIGKILL limits: mem 5.00%, swap 5.00%",
            'sending SIGKILL to process 42 uid 1000 "fixture-agent": oom_score 1700',
            "process 42 exited after 0.100 seconds",
        ]
        rows = [
            {
                "_PID": "7",
                "__MONOTONIC_TIMESTAMP": str(1_000_000 + i * 1000),
                "MESSAGE": message,
            }
            for i, message in enumerate(messages)
        ]

        def encode(value):
            return "\n".join(json.dumps(row) for row in value)

        self.assertAlmostEqual(
            daemon_decision(encode(rows), 42)["gate_to_exit_seconds"], 0.103, places=12
        )
        self.assertIsNone(daemon_decision(encode(rows), 43))
        for index, field, value in [
            (0, "MESSAGE", messages[0].replace("18.08", "4.16")),
            (1, "_PID", "8"),
            (1, "MESSAGE", messages[1].replace("4.89", "7.40")),
            (2, "MESSAGE", messages[2].replace("SIGKILL", "SIGTERM")),
            (3, "__MONOTONIC_TIMESTAMP", "900000"),
        ]:
            modified = [dict(row) for row in rows]
            modified[index][field] = value
            self.assertIsNone(daemon_decision(encode(modified), 42))
        self.assertIsNone(daemon_decision(encode(rows[1:]), 42))
        delayed = [dict(row) for row in rows]
        delayed[3]["__MONOTONIC_TIMESTAMP"] = "30800000"
        delayed[4]["__MONOTONIC_TIMESTAMP"] = "31700000"
        delayed[4]["MESSAGE"] = "process 42 exited after 0.900 seconds"
        self.assertIsNone(daemon_decision(encode(delayed), 42))


if __name__ == "__main__":
    unittest.main()
