"""Exercise rendered maintenance scripts without touching torrents or systemd."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def verify(start: Path, stop: Path) -> None:
    for active, stop_fails, over_budget in (
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (False, False, True),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "bin"
            binary.mkdir()
            runtime = root / "runtime"
            runtime.mkdir()
            log = root / "calls.jsonl"
            payload = root / "fixture.part"
            payload.write_bytes(b"neutral payload")
            mock = (
                "#!"
                + sys.executable
                + "\n"
                + """
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["CALL_LOG"], "a") as out:
    out.write(json.dumps([name, *args]) + "\\n")
if name == "find":
    sys.stdout.buffer.write(os.fsencode(os.environ["PAYLOAD"]) + b"\\0")
elif name == "stat":
    print(2**50 if os.environ["OVER_BUDGET"] == "1" else 15)
elif name == "systemctl":
    if args[0] == "is-active":
        sys.exit(0 if os.environ["ACTIVE"] == "1" else 3)
    if args[0] == "stop" and os.environ["STOP_FAILS"] == "1":
        sys.exit(1)
"""
            )
            for name in ("systemctl", "find", "stat", "fallocate"):
                command = binary / name
                command.write_text(mock)
                command.chmod(0o755)
            env = {
                **os.environ,
                "PATH": str(binary) + os.pathsep + os.environ["PATH"],
                "RUNTIME_DIRECTORY": str(runtime),
                "CALL_LOG": str(log),
                "PAYLOAD": str(payload),
                "ACTIVE": str(int(active)),
                "STOP_FAILS": str(int(stop_fails)),
                "OVER_BUDGET": str(int(over_budget)),
                "TRANSMISSION_SPARSIFY_MAX_LOGICAL_GIB": "256",
                "TRANSMISSION_SPARSIFY_FORCE": "0",
            }
            result = subprocess.run(
                ["bash", str(start)], env=env, capture_output=True, timeout=10
            )
            after = subprocess.run(
                ["bash", str(stop)], env=env, capture_output=True, timeout=10
            )
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            context = (active, stop_fails, over_budget, calls)
            assert after.returncode == 0, context
            assert (result.returncode != 0) == (stop_fails or over_budget), context
            starts = [call for call in calls if call[:2] == ["systemctl", "start"]]
            assert bool(starts) == (active and not over_budget), context
            punches = [call for call in calls if call[0] == "fallocate"]
            assert bool(punches) == (not stop_fails and not over_budget), context
            assert payload.read_bytes() == b"neutral payload", context
            print(
                json.dumps(
                    {
                        "active": active,
                        "stop_fails": stop_fails,
                        "over_budget": over_budget,
                        "passed": True,
                    }
                )
            )


if __name__ == "__main__":
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
