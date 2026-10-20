"""Bounded native-unit fixtures. Never run a real rebuild or activation."""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--guard", type=Path, required=True)
args = parser.parse_args()
GUARD = args.guard.resolve(strict=True)
lines = [
    line
    for line in GUARD.read_text().replace("\\\n", " ").splitlines()
    if line.strip() and not line.startswith("#!")
]
assert len(lines) == 1
command = shlex.split(lines[0])
assert (
    len(command) == 6
    and command[0] == "exec"
    and command[3] == "--chrt"
    and command[-1] == "$@"
), command
source = Path(command[2])
assert (
    source.read_bytes()
    == Path(__file__).parents[1].joinpath("rebuild-guard.py").read_bytes()
)
CTL, RUNNER, BASH = (
    shutil.which(name) for name in ("systemctl", "systemd-run", "bash")
)
assert CTL and RUNNER and BASH
owned = []
results = []
os.umask(0o077)


def call(argv, *, check=True):
    return subprocess.run(argv, capture_output=True, text=True, timeout=10, check=check)


def props(unit):
    r = call(
        [
            CTL,
            "--user",
            "show",
            unit,
            "-p",
            "LoadState",
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "MainPID",
            "-p",
            "ExecMainStatus",
        ],
        check=False,
    )
    assert r.returncode == 0, (unit, r.stdout, r.stderr)
    return dict(line.split("=", 1) for line in r.stdout.splitlines())


def wait_for(predicate, message, seconds=8):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError(message)


def unit_name(kind):
    name = "sinnix-rebuild-fixture-" + kind + "-" + uuid.uuid4().hex[:12] + ".service"
    owned.append(name)
    return name


def native_args(unit, *, owner=False):
    values = [
        "RuntimeMaxSec=25s",
        "TimeoutStopSec=5s",
        "MemoryMax=96M",
        "KillMode=control-group",
        "CPUSchedulingPolicy=other",
        "IOSchedulingClass=best-effort",
        "IOSchedulingPriority=6",
        "ExitType=cgroup" if owner else "ExitType=main",
    ]
    if owner:
        values.append("RemainAfterExit=yes")
    return [
        RUNNER,
        "--user",
        "--quiet",
        "--service-type=exec",
        "--unit=" + unit,
        *([] if owner else ["--collect"]),
        *[arg for v in values for arg in ("-p", v)],
    ]


def identity(pid):
    return int(Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[19])


def payload(marker, *, code=0, hang=False, ignore=False, noisy=False):
    return (
        "import os,json,time,signal; from pathlib import Path; "
        'ticks=int(Path("/proc/self/stat").read_text().rsplit(") ",1)[1].split()[19]); '
        f'Path({str(marker)!r}).write_text(json.dumps({{"pid":os.getpid(),"ticks":ticks,"scheduler":os.sched_getscheduler(0)}})); '
        + (
            "signal.signal(signal.SIGTERM,signal.SIG_IGN); os.setsid(); "
            if ignore
            else ""
        )
        + (
            '\nwhile True: os.write(2,b"x"*65536)\n'
            if noisy
            else "time.sleep(20)"
            if hang
            else f"raise SystemExit({code})"
        )
    )


def child_gone(unit):
    p = props(unit)
    return (
        p
        if p.get("ActiveState") in ("inactive", "failed")
        and p.get("MainPID", "0") == "0"
        else None
    )


def payload_gone(data):
    try:
        return identity(data["pid"]) != data["ticks"]
    except FileNotFoundError:
        return True


def interrupt(_sig, _frame):
    raise SystemExit(143)


signal.signal(signal.SIGTERM, interrupt)
signal.signal(signal.SIGINT, interrupt)
try:
    with tempfile.TemporaryDirectory(prefix="rebuild-native-") as tmp:
        root = Path(tmp)
        for kind, code, action, ignore in [
            ("normal", 0, None, False),
            ("failure", 7, None, False),
            ("stop", 0, "stop", False),
            ("kill", 0, "kill", True),
        ]:
            owner, child = unit_name("caller"), unit_name("work")
            marker = root / (kind + ".json")
            inner = native_args(child) + [
                "--wait",
                "--pipe",
                str(GUARD),
                "--owner-pid",
                "$$",
                "--owner-start-ticks",
                "TICKS",
                "--",
                sys.executable,
                "-c",
                payload(marker, code=code, hang=bool(action), ignore=ignore),
            ]
            # The production wrapper captures the same kernel start-time field.
            body = 'set -euo pipefail\nIFS= read -r s < /proc/$$/stat\ns="${s##*) }"\nread -r -a f <<< "$s"\n'
            words = [
                shlex.quote(a)
                if a not in ("$$", "TICKS")
                else ('"$$"' if a == "$$" else '"${f[19]}"')
                for a in inner
            ]
            body += " ".join(words) + " &\nwait $!\n"
            script = root / (kind + ".sh")
            script.write_text(body)
            call(native_args(owner, owner=True) + [BASH, str(script)])
            wait_for(marker.exists, "payload did not start: " + kind)
            data = json.loads(marker.read_text())
            assert data["scheduler"] == os.SCHED_BATCH, data
            if action:
                controller = props(child)["MainPID"]
                assert int(controller) > 0
                assert os.sched_getscheduler(int(controller)) == os.SCHED_OTHER
                if action == "stop":
                    call([CTL, "--user", "stop", owner])
                else:
                    call(
                        [
                            CTL,
                            "--user",
                            "kill",
                            "--kill-whom=main",
                            "--signal=KILL",
                            owner,
                        ]
                    )
                final = wait_for(
                    lambda child=child: child_gone(child),
                    "work survived caller " + action,
                )
                wait_for(
                    lambda data=data: payload_gone(data),
                    "payload survived native cgroup cleanup",
                )
            else:
                final = wait_for(
                    lambda owner=owner: (
                        props(owner) if props(owner).get("MainPID") == "0" else None
                    ),
                    "normal caller did not finish",
                )
                assert final["ExecMainStatus"] == str(code), final
                wait_for(
                    lambda child=child: child_gone(child),
                    "completed work remained active",
                )
            results.append(
                {
                    "case": kind,
                    "owner": owner,
                    "child": child,
                    "payload": data,
                    "final": final,
                }
            )
            call([CTL, "--user", "stop", owner, child], check=False)
            call([CTL, "--user", "reset-failed", owner, child], check=False)

        # A dead or replaced caller must not launch a command, or restart its unit.
        for kind, stale in [("late", False), ("identity", True)]:
            marker = root / (kind + ".json")
            with subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(20)"]
            ) as owner:
                ticks = identity(owner.pid)
                if not stale:
                    owner.terminate()
                    owner.wait(timeout=5)
                child = unit_name("late")
                r = call(
                    native_args(child)
                    + [
                        "--wait",
                        "--pipe",
                        str(GUARD),
                        "--owner-pid",
                        str(owner.pid),
                        "--owner-start-ticks",
                        str(ticks + 1 if stale else ticks),
                        "--",
                        sys.executable,
                        "-c",
                        payload(marker),
                    ],
                    check=False,
                )
                assert r.returncode == 143 and not marker.exists(), (
                    kind,
                    r.returncode,
                    r.stderr,
                )
                assert child_gone(child)
                if owner.poll() is None:
                    owner.terminate()
            results.append(
                {
                    "case": kind,
                    "child": child,
                    "status": r.returncode,
                    "payload_started": False,
                }
            )

        # Keep the output reader alive without draining it. Exit must not need
        # writable caller-owned stdout/stderr after the caller disappears.
        marker = root / "backpressure.json"
        with subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(20)"]
        ) as owner:
            child = unit_name("blocked-output")
            runner = subprocess.Popen(
                native_args(child)
                + [
                    "--wait",
                    "--pipe",
                    str(GUARD),
                    "--owner-pid",
                    str(owner.pid),
                    "--owner-start-ticks",
                    str(identity(owner.pid)),
                    "--",
                    sys.executable,
                    "-c",
                    payload(marker, noisy=True),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                wait_for(marker.exists, "noisy payload did not start")
                data = json.loads(marker.read_text())
                time.sleep(0.2)
                owner.kill()
                owner.wait(timeout=5)
                final = wait_for(
                    lambda child=child: child_gone(child),
                    "guard blocked on caller output",
                )
                wait_for(
                    lambda data=data: payload_gone(data),
                    "noisy payload survived cleanup",
                )
                stdout, stderr = runner.communicate(timeout=5)
                results.append(
                    {
                        "case": "blocked-output",
                        "child": child,
                        "status": runner.returncode,
                        "stdout_bytes": len(stdout),
                        "stderr_bytes": len(stderr),
                        "final": final,
                    }
                )
            finally:
                call([CTL, "--user", "stop", child], check=False)
                if runner.poll() is None:
                    runner.kill()
                runner.communicate(timeout=5)
                if owner.poll() is None:
                    owner.kill()
finally:
    for unit in owned:
        call([CTL, "--user", "stop", unit], check=False)
        call([CTL, "--user", "reset-failed", unit], check=False)
    for unit in owned:
        assert props(unit)["ActiveState"] == "inactive", unit

print(
    json.dumps(
        {
            "schema": "sinnix-rebuild-lifetime-v1",
            "ok": True,
            "guard": str(GUARD),
            "artifact_kind": "nix-store"
            if str(GUARD).startswith("/nix/store/")
            else "source-preview",
            "guard_sha256": hashlib.sha256(GUARD.read_bytes()).hexdigest(),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "cases": results,
            "cleaned_units": len(owned),
        }
    )
)
