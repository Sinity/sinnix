"""Systemd admission for resumable full-volume backup drains."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MEMINFO = Path("/proc/meminfo")
INTERVAL = 30


def memory_mib(path: Path = MEMINFO) -> tuple[int, int]:
    fields = {}
    for line in path.read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("MemAvailable", "SwapFree"):
            fields[key] = int(value.split()[0]) // 1024
    return fields["MemAvailable"], fields["SwapFree"]


def command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=5)


def properties(unit: str, *names: str) -> dict[str, str]:
    result = command(["systemctl", "show", unit, *(
        f"--property={name}" for name in names
    )])
    if result.returncode:
        raise ValueError(f"cannot read systemd state for {unit}")
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


@dataclass(frozen=True)
class IndexProbe:
    user: str | None
    uid: int | None
    program: str
    allow_inactive: bool = False

    def state(self) -> str:
        if self.user is None:
            return "inactive"
        try:
            manager = properties(f"user@{self.uid}.service", "ActiveState")
            if manager.get("ActiveState") == "inactive":
                return "inactive"
            if manager.get("ActiveState") != "active":
                return "unknown"
            runtime = f"/run/user/{self.uid}"
            as_user = [
                "runuser", "-u", self.user, "--", "env",
                f"XDG_RUNTIME_DIR={runtime}",
                f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus",
            ]
            unit = command([*as_user, "systemctl", "--user", "show",
                            "polylogue-live.service", "--property=ActiveState", "--value"])
            if unit.returncode:
                return "unknown"
            state = unit.stdout.strip()
            if state == "inactive" and self.allow_inactive:
                return "inactive"
            if state != "active":
                return "unknown"
            result = command([*as_user, self.program, "status", "--json", "--deadline", "2000"])
            # A building index may return a typed degraded reply with exit 5.
            status = json.loads(result.stdout)["value"]
            index = status["index"]
            rebuilding = index["rebuilding"]["state"]
            if rebuilding in ("writing", "pending", "waiting", "building"):
                return "rebuilding"
            if rebuilding == "no" and index["installed"]["state"] == "current":
                if status["caught_up"] is True:
                    return "idle"
                if status["caught_up"] is False:
                    return "catching_up"
            return "unknown"
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            return "unknown"


def admission_reason(index: str, available: int, minimum: int) -> str | None:
    if index not in ("idle", "inactive"):
        return f"polylogue_index={index}"
    if available < minimum:
        return f"available_mib={available} required_mib={minimum}"
    return None


def yield_reason(index: str, available: int, swap_free: int) -> str | None:
    if index == "rebuilding":
        return "polylogue_index=rebuilding"
    # Lower emergency watermark than admission; avoid oscillation.
    if available < 1024 or (available < 2048 and swap_free < 1024):
        return f"critical_memory available_mib={available} swap_free_mib={swap_free}"
    return None


def wait_for_admission(probe: IndexProbe, minimum: int, *, once: bool) -> int:
    previous = None
    while True:
        try:
            available, _ = memory_mib()
            reason = admission_reason(probe.state(), available, minimum)
        except (OSError, ValueError, KeyError):
            reason = "memory_headroom_unknown"
        if reason is None:
            print("backup_admission=admitted", flush=True)
            return 0
        if reason != previous:
            print(f"backup_admission=waiting {reason}", flush=True)
        if once:
            return 75
        previous = reason
        time.sleep(INTERVAL)


def active_drains(units: list[str]) -> list[str]:
    running = []
    for unit in units:
        state = properties(unit, "SubState", "MainPID")
        # A oneshot waiting in ExecStartPre has no main PID. Leave it waiting.
        if state.get("SubState") in ("start", "running") and int(state.get("MainPID", "0")) > 0:
            running.append(unit)
    return running


def yield_drains(probe: IndexProbe, units: list[str]) -> int:
    try:
        running = active_drains(units)
        if not running:
            return 0
        available, swap_free = memory_mib()
        reason = yield_reason("unknown", available, swap_free)
        if reason is None:
            reason = yield_reason(probe.state(), available, swap_free)
        if reason is None:
            return 0
        print(f"backup_admission=requeue {reason} units={','.join(running)}", flush=True)
        # Systemd stops the old cgroup and reenters ExecStartPre; no backup
        # receipt is fabricated. The unacknowledged snapshot remains.
        result = command(["systemctl", "--no-block", "restart", *running])
        if result.returncode:
            print("backup admission: requeue failed", file=sys.stderr, flush=True)
        return result.returncode
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"backup admission: {error}", file=sys.stderr, flush=True)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("wait", "yield"))
    parser.add_argument("--user")
    parser.add_argument("--uid", type=int)
    parser.add_argument("--program", default="/run/current-system/sw/bin/polylogue")
    parser.add_argument("--allow-inactive", action="store_true")
    parser.add_argument("--min-available-mib", type=int, default=8192)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--unit", action="append", default=[])
    args = parser.parse_args(argv)
    if (args.user is None) != (args.uid is None):
        parser.error("--user and --uid must be specified together")
    probe = IndexProbe(args.user, args.uid, args.program, args.allow_inactive)
    if args.action == "wait":
        return wait_for_admission(probe, args.min_available_mib, once=args.once)
    return yield_drains(probe, args.unit)


if __name__ == "__main__":
    sys.exit(main())
