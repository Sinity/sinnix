"""Validate bounded recovery and refuse capped responses without credentials/network."""
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

source = Path(__file__).parent
bun = os.environ["BUN"]
with tempfile.TemporaryDirectory(prefix="xiaomi-recovery-") as tmp:
    root = Path(tmp)
    upstream = root / "upstream/src/xiaomi"
    upstream.mkdir(parents=True)
    shutil.copy2(source / "witness-sync.ts", root / "witness-sync.ts")
    (upstream / "client.ts").write_text('''
import {writeFileSync, appendFileSync} from "node:fs";
writeFileSync(process.env.IMPORTED!, "yes");
Date.now = () => Date.UTC(2026, 9, 16, 12, 34, 56);
export class XiaomiAuth {
  static fromToken(_path: string) { return {token: {user_id: "1"}}; }
}
export class MiHealthClient {
  async getSleep() {return [];}
  async getHeartRate() {return [];}
  async getSpo2History() {return [];}
  async getSteps() {return [];}
  async getAggregatedData() {return [];}
  async getFitnessData(_uid, key, start, end) {
    appendFileSync(process.env.WINDOWS!, JSON.stringify({key, start, end}) + "\\n");
    if (start % 86400 !== 0 || end - start + 1 > 7 * 86400) {
      throw new Error("raw query is not a bounded complete-day window");
    }
    return Array.from({length: Number(process.env.ROWS)}, (_, i) => ({time: start + i, value: "{}"}));
  }
}
''')
    for index, days in enumerate(["0", "-1", "36", "NaN", "Infinity", "1.5"]):
        marker = root / f"imported-{index}"
        result = subprocess.run([bun, "run", str(root / "witness-sync.ts")],
            env={**os.environ, "XIAOMI_WITNESS_WINDOW_DAYS": days, "IMPORTED": str(marker)},
            capture_output=True, text=True, timeout=5)
        assert result.returncode == 64 and not marker.exists(), result.stderr
    for rows in (2, 100000):
        state = root / f"state-{rows}"
        state.mkdir()
        (state / "seen-hashes.json").write_text('{"retained":"prior-digest"}')
        lane = root / f"lane-{rows}"
        result = subprocess.run([bun, "run", str(root / "witness-sync.ts")], env={**os.environ,
            "XIAOMI_WITNESS_WINDOW_DAYS": "35", "IMPORTED": str(root / "imported"),
            "XIAOMI_WITNESS_STATE": str(state), "XIAOMI_WITNESS_LANE": str(lane), "ROWS": str(rows), "WINDOWS": str(root / f"windows-{rows}")},
            capture_output=True, text=True, timeout=10)
        data = [json.loads(line) for file in lane.glob("*.jsonl") for line in file.read_text().splitlines()]
        receipt = data[-1]
        assert receipt["window_days"] == 35
        assert json.loads((state / "seen-hashes.json").read_text())["retained"] == "prior-digest"
        if rows == 2:
            assert result.returncode == 0 and receipt["failures"] == 0
            windows = [json.loads(line) for line in (root / f"windows-{rows}").read_text().splitlines()]
            for key in {window["key"] for window in windows}:
                spans = [window for window in windows if window["key"] == key]
                assert len(spans) == 6
                assert spans[0]["start"] == int(datetime(2026, 9, 11, tzinfo=UTC).timestamp())
                assert spans[-1]["end"] == int(datetime(2026, 10, 16, 12, 34, 56, tzinfo=UTC).timestamp())
                assert all(a["end"] + 1 == b["start"] for a, b in zip(spans[:-1], spans[1:], strict=True))
            assert len([row for row in data if row["kind"].startswith("vendor_raw_")]) == 48
        else:
            assert result.returncode != 0 and receipt["failures"] == 8
            assert not any(row["kind"].startswith("vendor_raw_") for row in data)
            assert not (state / "credential-expired").exists()
print("Recovery bounds, valid history revisions, capped-response refusal and prior state preservation passed")
