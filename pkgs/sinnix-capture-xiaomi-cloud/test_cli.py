"""Run entry points with an upstream trap; no credentials or network access."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

source = Path(os.environ.get("XIAOMI_TEST_ROOT", Path(__file__).parent))
bun = os.environ.get("BUN", "bun")
cases = [(["--help"], 0), (["-h"], 0), (["--unknown"], 2),
         (["unexpected"], 2), (["--help", "unexpected"], 2), (["--"], 1), ([], 1)]
results = []
with tempfile.TemporaryDirectory(prefix="xiaomi-cli-") as temporary:
    root = Path(temporary)
    for entry in ("xiaomi-sync.ts", "xiaomi-login.ts"):
        for index, (args, expected) in enumerate(cases):
            case = root / (entry + str(index))
            upstream = case / "upstream/src/xiaomi"
            upstream.mkdir(parents=True)
            shutil.copy2(source / entry, case / entry)
            (upstream / "client.ts").write_text('''
import {writeFileSync} from "node:fs";
writeFileSync(process.env.PROBE_IMPORT!, "imported");
function dispatch(): never {
  writeFileSync(process.env.PROBE_DISPATCH!, "dispatched");
  throw new Error("fixture normal dispatch reached");
}
export class XiaomiAuth {
  constructor() { dispatch(); }
  static fromToken(_path: string): never { return dispatch(); }
}
export class MiHealthClient {}
''')
            env = dict(os.environ, PROBE_IMPORT=str(case / "imported"),
                       PROBE_DISPATCH=str(case / "dispatched"),
                       XIAOMI_CLOUD_STATE=str(case / "state"),
                       XIAOMI_CLOUD_LANE=str(case / "lane"))
            result = subprocess.run([bun, "run", str(case / entry), *args], env=env,
                                    capture_output=True, text=True, timeout=5)
            ok = result.returncode == expected
            if expected != 1:
                output = result.stdout if expected == 0 else result.stderr
                ok &= "Usage:" in output and not (case / "imported").exists()
                ok &= not (case / "state").exists() and not (case / "lane").exists()
            else:
                ok &= (case / "dispatched").exists() and "fixture normal dispatch reached" in result.stderr
            results.append({"entry": entry, "args": args, "exit": result.returncode,
                            "expected": expected, "passed": bool(ok)})
print(json.dumps(results, indent=2))
assert all(row["passed"] for row in results), "entry arguments reached the credential/network client"
print(f"{len(results)} CLI cases passed without credential or network access")
