"""Exercise the deployed earlyoom arguments with synthetic host pressure."""

import os
import shlex
import signal
import subprocess
import sys
from pathlib import Path

binary, preload, arguments = sys.argv[1:]
args = shlex.split(arguments)
# Notification programs are irrelevant in dry-run fixtures.
args = [arg for arg in args if arg != "-n"]
assert "--dryrun" not in args
root = Path.cwd()


def run(name: str, available: int, swap_free: int, psi: int) -> str:
    meminfo = root / f"{name}.meminfo"
    meminfo.write_text(
        f"MemTotal: 1000000 kB\nMemAvailable: {available} kB\n"
        f"AnonPages: 800000 kB\nSwapTotal: 400000 kB\nSwapFree: {swap_free} kB\n"
    )
    pressure = root / f"{name}.pressure"
    pressure.write_text(
        f"some avg10={psi}.00 avg60=0.00 avg300=0.00 total=1\n"
        f"full avg10={psi}.00 avg60=0.00 avg300=0.00 total=1\n"
    )
    process = subprocess.Popen(
        [binary, *args, "--dryrun"],
        env={
            **os.environ,
            "LD_PRELOAD": preload,
            "EARLYOOM_TEST_MEMINFO": str(meminfo),
            "EARLYOOM_PSI_PATH": str(pressure),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        log, _ = process.communicate(timeout=2)
        raise AssertionError(f"{name}: earlyoom exited {process.returncode}\n{log}")
    except subprocess.TimeoutExpired:
        process.terminate()
        log, _ = process.communicate(timeout=5)
    assert process.returncode == -signal.SIGTERM, (name, process.returncode, log)
    assert "dryrun mode enabled" in log, log
    (root / f"{name}.log").write_text(log)
    return log


# Live failure: 4.59-4.91% available RAM and no free swap repeatedly sent
# SIGTERM to the same surviving victim. SIGKILL defaulted to 2.5% RAM.
log = run("exhausted", 49000, 0, 25)
assert "low memory! at or below SIGKILL limits" in log, log
assert "sending SIGKILL to process" in log, log

log = run("term-band", 49000, 28000, 25)
assert "low memory! at or below SIGTERM limits" in log, log
assert "sending SIGKILL to process" not in log, log

log = run("calm", 49000, 0, 3)
assert "not killing" in log, log
assert "low memory!" not in log, log

# Cold pages occupying swap do not establish an exhausted host.
log = run("available-memory", 400000, 0, 25)
assert "low memory!" not in log, log

log = run("available-swap", 49000, 80000, 25)
assert "low memory!" not in log, log
