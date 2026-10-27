"""Closed-month exports must be complete before their capture is acknowledged."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HEADER = "family\tport\tconns\trx_bytes\trx_pkts\ttx_bytes\ttx_pkts"
ROW = "4\t443\t2\t100\t1\t200\t2"
PERIOD = "2026-01-01"


class PeriodCapture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tools = self.root / "bin"
        self.tools.mkdir()
        (self.root / "scratch").mkdir()
        self.env = dict(
            os.environ,
            PATH=str(self.tools) + ":" + os.environ["PATH"],
            FIXTURE_ROOT=str(self.root),
            TMPDIR=str(self.root / "scratch"),
        )
        self.executable(
            "nlbw",
            r"""import os,sys
mode=os.environ['EXPORT_MODE']
if mode=='failed':
 print('partial')
 print('fixture export unavailable',file=sys.stderr)
 sys.exit(17)
if mode=='malformed':
 print('incomplete export')
 sys.exit(0)
if mode!='empty': print(os.environ['CSV_HEADER'])
if mode=='rows': print(os.environ['CSV_ROW'])
""",
        )
        self.env.update(CSV_HEADER=HEADER, CSV_ROW=ROW)
        self.periods = Path(os.environ["ROUTER_PERIODS_SCRIPT"])

    def executable(self, name, body):
        path = self.tools / name
        path.write_text("#!" + sys.executable + "\n" + body)
        path.chmod(0o700)
        return path

    def remote(self, mode):
        return subprocess.run(
            ["sh", str(self.periods), PERIOD],
            env=dict(self.env, EXPORT_MODE=mode),
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_export_failure_is_not_success(self):
        result = self.remote("failed")
        self.assertEqual(result.returncode, 17)
        self.assertIn("fixture export unavailable", result.stderr)
        self.assertIn("partial", result.stdout)

    def test_empty_export_is_unavailable(self):
        self.prepare_receiver()
        result = self.poll("empty")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.months(), [])
        self.assertEqual(self.marker.read_text(), "")
        self.assertEqual(self.watermark.read_text(), "12\nfixture\n")

    def test_valid_empty_month_has_a_header(self):
        result = self.remote("header")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"===NLBW_PERIOD:{PERIOD}===\n{HEADER}\n")

    def test_populated_month_keeps_export(self):
        result = self.remote("rows")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout, f"===NLBW_PERIOD:{PERIOD}===\n{HEADER}\n{ROW}\n"
        )

    def prepare_receiver(self):
        self.capture = self.root / "capture"
        state = self.capture / ".state"
        state.mkdir(parents=True)
        self.watermark = state / "syslog-watermark"
        self.watermark.write_text("0\nretained\n")
        self.marker = state / "nlbw-captured-periods"
        self.executable(
            "ssh",
            r"""import os,sys,subprocess
from pathlib import Path
text=sys.stdin.read()
if text==Path(os.environ['ROUTER_PERIODS_SCRIPT']).read_text():
 result=subprocess.run(['sh','-s','--','2026-01-01'],input=text,text=True)
 sys.exit(result.returncode)
print('===LEASES===\n===ASSOC===\n===NLBW_PERIODS===\n2026-01-01\n===NLBW_CURRENT===')
print(os.environ['CSV_HEADER'])
print(os.environ['CSV_ROW'])
print('===SYSLOG===\nfixture syslog\n===END===')
print('WATERMARK 12|fixture',file=sys.stderr)
""",
        )
        self.writer = self.executable(
            "capture",
            r"""import json,os,sys
from pathlib import Path
lane=sys.argv[sys.argv.index('--lane')+1]
if os.environ.get('CAPTURE_FAIL_LANE')==lane:
 sys.exit(19)
with (Path(os.environ['FIXTURE_ROOT'])/'captured.jsonl').open('a') as out:
 out.write(json.dumps({'lane':lane,'payload':json.load(sys.stdin)})+'\n')
""",
        )

    def poll(self, mode):
        return subprocess.run(
            [
                "bash",
                os.environ["ROUTER_POLL_SCRIPT"],
                "fixture",
                str(self.writer),
                str(self.capture),
                os.environ["ROUTER_REMOTE_POLL_SCRIPT"],
                str(self.periods),
            ],
            env=dict(self.env, EXPORT_MODE=mode),
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_scratch_is_one_allocation_and_removed_on_transport_failure(self):
        self.prepare_receiver()
        self.executable("ssh", "import sys; sys.exit(37)\n")
        result = self.poll("rows")
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(list((self.root / "scratch").iterdir()), [])

    def test_scratch_is_removed_on_sigterm(self):
        self.prepare_receiver()
        self.executable(
            "ssh",
            """import os,signal
from pathlib import Path
for path in Path(os.environ['TMPDIR']).glob('sinnix-router-poll.*'):
 os.kill(int(path.name.split('.')[1]), signal.SIGTERM)
""",
        )
        result = self.poll("rows")
        self.assertEqual(result.returncode, 143, result.stderr)
        self.assertEqual(list((self.root / "scratch").iterdir()), [])

    def months(self):
        path = self.root / "captured.jsonl"
        rows = (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )
        return [
            r["payload"]
            for r in rows
            if r["lane"] == "nlbw" and r["payload"]["period"] == PERIOD
        ]

    def test_failed_export_leaves_month_retryable_without_stranding_syslog(self):
        self.prepare_receiver()
        result = self.poll("failed")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.months(), [])
        self.assertEqual(self.marker.read_text(), "")
        self.assertEqual(self.watermark.read_text(), "12\nfixture\n")
        captures = [
            json.loads(line)
            for line in (self.root / "captured.jsonl").read_text().splitlines()
        ]
        self.assertTrue(
            any(
                r["lane"] == "syslog" and r["payload"] == {"lines": ["fixture syslog"]}
                for r in captures
            )
        )
        result = self.poll("rows")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.months()), 1)
        self.assertEqual(self.months()[0]["rows"][0]["rx_bytes"], 100)
        self.assertEqual(self.marker.read_text(), PERIOD + "\n")
        self.assertEqual(self.watermark.read_text(), "12\nfixture\n")
        self.assertEqual(self.poll("rows").returncode, 0)
        self.assertEqual(len(self.months()), 1)

    def test_malformed_export_is_not_a_measured_zero(self):
        self.prepare_receiver()
        result = self.poll("malformed")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.months(), [])
        self.assertEqual(self.marker.read_text(), "")
        self.assertEqual(self.watermark.read_text(), "12\nfixture\n")

    def test_failed_syslog_write_cannot_advance_its_watermark(self):
        self.prepare_receiver()
        self.env["CAPTURE_FAIL_LANE"] = "syslog"
        result = self.poll("rows")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.watermark.read_text(), "0\nretained\n")
        self.assertEqual(len(self.months()), 1)
        self.env.pop("CAPTURE_FAIL_LANE")
        self.assertEqual(self.poll("rows").returncode, 0)
        self.assertEqual(self.watermark.read_text(), "12\nfixture\n")
        self.assertEqual(len(self.months()), 1)

    def test_valid_zero_month_is_acknowledged(self):
        self.prepare_receiver()
        result = self.poll("header")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.months(), [{"period": PERIOD, "rows": []}])
        self.assertEqual(self.marker.read_text(), PERIOD + "\n")


if __name__ == "__main__":
    unittest.main()
