"""Validate bounded recovery and refuse capped responses without credentials/network."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).parent
bun = os.environ["BUN"]
with tempfile.TemporaryDirectory(prefix="xiaomi-recovery-") as tmp:
    root = Path(tmp)
    upstream = root / "upstream/src/xiaomi"
    upstream.mkdir(parents=True)
    shutil.copy2(source / "witness-sync.ts", root / "witness-sync.ts")
    (upstream / "client.ts").write_text('''
import {writeFileSync} from "node:fs";
writeFileSync(process.env.IMPORTED!, "yes");
export class XiaomiAuth {
  static fromToken(_path: string) { return {token: {user_id: "1"}}; }
}
export class MiHealthClient {
  async getSleep() {return [];}
  async getHeartRate() {return [];}
  async getSpo2History() {return [];}
  async getSteps() {return [];}
  async getAggregatedData() {return [];}
  async getFitnessData() {
    return Array(Number(process.env.ROWS)).fill({time: 1757937600, value: "{}"});
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
            "XIAOMI_WITNESS_STATE": str(state), "XIAOMI_WITNESS_LANE": str(lane), "ROWS": str(rows)},
            capture_output=True, text=True, timeout=10)
        data = [json.loads(line) for file in lane.glob("*.jsonl") for line in file.read_text().splitlines()]
        receipt = data[-1]
        assert receipt["window_days"] == 35
        assert json.loads((state / "seen-hashes.json").read_text())["retained"] == "prior-digest"
        if rows == 2:
            assert result.returncode == 0 and receipt["failures"] == 0
            assert len([row for row in data if row["kind"].startswith("vendor_raw_")]) == 8
        else:
            assert result.returncode != 0 and receipt["failures"] == 8
            assert not any(row["kind"].startswith("vendor_raw_") for row in data)
            assert not (state / "credential-expired").exists()
print("Recovery bounds, valid history revisions, capped-response refusal and prior state preservation passed")
