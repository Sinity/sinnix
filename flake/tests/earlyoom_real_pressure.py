"""Finite guest-only pressure and independent protected latency observer."""

import ctypes
import json
import mmap
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

MIB = 1024 * 1024


def mark_ready(out, name):
    stat = Path("/proc/self/stat").read_text()
    token = stat.rsplit(")", 1)[1].split()[19]
    temporary = out / f"{name}.ready-new"
    temporary.write_text(
        json.dumps(
            {"pid": os.getpid(), "start_ticks": token, "monotonic": time.monotonic()}
        )
    )
    temporary.replace(out / f"{name}.ready")


def wait_for_go(out, name, timeout=30):
    mark_ready(out, name)
    deadline = time.monotonic() + timeout
    while not (out / "go").exists():
        assert time.monotonic() < deadline, f"{name}: readiness barrier expired"
        time.sleep(0.02)
    return float((out / "go").read_text())


def running_identity(proc, expected_start):
    try:
        stat = (proc / "stat").read_text()
    except FileNotFoundError:
        return None
    parts = stat.rsplit(")", 1)[1].split()
    if parts[19] != expected_start or parts[0] in ("Z", "X") or int(parts[21]) <= 0:
        return None
    return stat


def main():
    mode = sys.argv[1]
    out = Path("/run/real-pressure")
    out.mkdir(exist_ok=True)
    if mode == "graphics":
        classes = {
            str(path): path.read_text().strip()
            for path in Path("/sys/bus/pci/devices").glob("*/class")
        }
        diagnostic = {
            "pci_classes": classes,
            "bochs_loaded": Path("/sys/module/bochs").exists(),
            "framebuffer_present": Path("/sys/class/graphics/fb0").exists(),
        }
        (out / "graphics.json").write_text(json.dumps(diagnostic, indent=2))
        assert (
            not diagnostic["bochs_loaded"] and not diagnostic["framebuffer_present"]
        ), diagnostic
        assert not any(value.startswith("0x03") for value in classes.values()), (
            diagnostic
        )
    elif mode == "victim":
        assert ctypes.CDLL(None).prctl(15, b"fixture-agent", 0, 0, 0) == 0
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        (out / "victim.pid").write_text(str(os.getpid()))
        chunks = []
        # Real incompressible anonymous pages. Hard allocation and wall-time bounds
        # remain effective if the daemon fails; the VM test also has an outer bound.
        end = wait_for_go(out, "victim") + 90
        for _ in range(768):
            if time.monotonic() >= end:
                break
            chunk = mmap.mmap(-1, 2 * MIB, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
            chunk.write(os.urandom(2 * MIB))
            chunks.append(chunk)
            time.sleep(0.015)
        while time.monotonic() < end:
            for chunk in chunks:
                chunk[0] = (chunk[0] + 1) % 256
        sys.exit(2)  # surviving to this deadline is a failed emergency recovery
    elif mode == "observe":
        assert ctypes.CDLL(None).prctl(15, b"kitty", 0, 0, 0) == 0
        hold = bytearray(32 * MIB)
        for offset in range(0, len(hold), 4096):
            hold[offset] = 1
        (out / "protected-status.txt").write_text(Path("/proc/self/status").read_text())
        (out / "protected.pid").write_text(str(os.getpid()))
        deadline = time.monotonic() + 30
        with (out / "latency.jsonl").open("w", buffering=1) as output:
            output.write(json.dumps({"monotonic": time.monotonic()}) + "\n")
            mark_ready(out, "observe")
            while True:
                now = time.monotonic()
                if (out / "go").exists():
                    if now > float((out / "go").read_text()) + 115:
                        break
                else:
                    assert now < deadline, "observe: readiness barrier expired"
                output.write(json.dumps({"monotonic": now}) + "\n")
                time.sleep(0.05)
    elif mode == "sample":
        end = wait_for_go(out, "sample") + 115
        runtime = Path("/sys/fs/cgroup")
        paths = {"root": runtime}
        with (out / "samples.jsonl").open("w", buffering=1) as output:
            while time.monotonic() < end:
                started = time.monotonic()
                victim_file = out / "victim.pid"
                victim_pid = (
                    int(victim_file.read_text()) if victim_file.exists() else None
                )
                alive_before = (
                    Path(f"/proc/{victim_pid}").exists() if victim_pid else None
                )
                for label, pid in [("tool", victim_pid), ("interactive", None)]:
                    if label in paths:
                        continue
                    if label == "interactive":
                        pid_file = out / "protected.pid"
                        pid = int(pid_file.read_text()) if pid_file.exists() else None
                    if pid and Path(f"/proc/{pid}/cgroup").exists():
                        relative = (
                            Path(f"/proc/{pid}/cgroup")
                            .read_text()
                            .strip()
                            .split("::", 1)[1]
                        )
                        paths[label] = (runtime / relative.lstrip("/")).parent
                sample = {
                    "capture_started": started,
                    "cgroup_paths": {k: str(v) for k, v in paths.items()},
                }
                sample["zram_mm_stat"] = Path("/sys/block/zram0/mm_stat").read_text()
                for name in (
                    "meminfo",
                    "swaps",
                    "vmstat",
                    "pressure/memory",
                    "pressure/io",
                ):
                    sample[name] = Path("/proc", name).read_text()
                for label in ("root", "tool", "interactive"):
                    sample[label] = {}
                    for name in (
                        "memory.current",
                        "memory.swap.current",
                        "memory.events",
                        "memory.pressure",
                        "io.pressure",
                        "io.stat",
                    ):
                        path = paths[label] / name if label in paths else None
                        sample[label][name] = (
                            path.read_text() if path and path.exists() else None
                        )
                alive_after = (
                    Path(f"/proc/{victim_pid}").exists() if victim_pid else None
                )
                sample["victim_alive"] = alive_before and alive_after
                sample["monotonic"] = time.monotonic()
                sample["capture_seconds"] = sample["monotonic"] - started
                output.write(json.dumps(sample) + "\n")
                time.sleep(0.02)
    elif mode == "transition":
        # Warm the actual PSI average through reclaim before allowing the final
        # guest RAM ramp. This scales fixture budgets, never kernel sensors.
        commands = {name: shutil.which(name) for name in ("runuser", "systemctl")}
        assert all(commands.values()), commands
        preflight = subprocess.run(
            [
                commands["runuser"],
                "-u",
                "fixture",
                "--",
                "env",
                "XDG_RUNTIME_DIR=/run/user/1000",
                commands["systemctl"],
                "--user",
                "show",
                "agent-tool.slice",
                "-p",
                "MemoryHigh",
                "--value",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert int(preflight.stdout.strip()) == 900 * MIB, preflight.stdout
        (out / "transition-preflight.json").write_text(
            json.dumps(
                {"commands": commands, "memory_high": int(preflight.stdout.strip())}
            )
        )
        deadline = wait_for_go(out, "transition") + 30
        pid = int((out / "victim.pid").read_text())
        proc = Path(f"/proc/{pid}")
        expected = json.loads((out / "victim.ready").read_text())["start_ticks"]
        while True:
            stat = running_identity(proc, expected)
            if stat is None:
                (out / "transition.json").write_text(
                    json.dumps(
                        {
                            "status": "skipped_victim_exit",
                            "monotonic": time.monotonic(),
                            "victim_pid": pid,
                        }
                    )
                )
                return
            assert time.monotonic() < deadline, (
                "real PSI/zram warmup deadline not reached"
            )
            pressure = Path("/proc/pressure/memory").read_text()
            full = float(pressure.split("full avg10=")[1].split()[0])
            mem = {
                line.split(":", 1)[0]: int(line.split()[1])
                for line in Path("/proc/meminfo").read_text().splitlines()
            }
            assert time.monotonic() < deadline, (
                "real PSI/zram warmup deadline exceeded during read"
            )
            if full >= 10 and mem["SwapFree"] / mem["SwapTotal"] <= 0.10:
                break
            assert time.monotonic() < deadline, (
                "real PSI/zram warmup deadline not reached"
            )
            time.sleep(0.1)
        pid = int((out / "victim.pid").read_text())
        proc = Path(f"/proc/{pid}")
        stat_before = running_identity(proc, expected)
        if stat_before is None:
            (out / "transition.json").write_text(
                json.dumps(
                    {
                        "status": "skipped_victim_exit",
                        "monotonic": time.monotonic(),
                        "victim_pid": pid,
                    }
                )
            )
            return
        relative = (proc / "cgroup").read_text().strip().split("::", 1)[1]
        high = Path("/sys/fs/cgroup", relative.lstrip("/")).parent / "memory.high"
        transition = {
            "status": "budget_raised",
            "monotonic_before": time.monotonic(),
            "victim_pid": pid,
            "victim_stat_before": stat_before,
            "victim_alive_before": proc.exists(),
            "memory_psi": pressure,
            "meminfo": mem,
            "memory_high_before": high.read_text(),
        }
        subprocess.run(
            [
                commands["runuser"],
                "-u",
                "fixture",
                "--",
                "env",
                "XDG_RUNTIME_DIR=/run/user/1000",
                commands["systemctl"],
                "--user",
                "set-property",
                "--runtime",
                "agent-tool.slice",
                "MemoryHigh=1000M",
            ],
            check=True,
            timeout=5,
        )
        transition.update(
            monotonic_after=time.monotonic(),
            victim_alive_after=proc.exists(),
            victim_stat_after=running_identity(proc, expected),
            memory_high_after=high.read_text(),
        )
        (out / "transition.json").write_text(json.dumps(transition, indent=2))
        assert int(transition["memory_high_before"]) == 900 * MIB, transition
        assert int(transition["memory_high_after"]) == 1000 * MIB, transition
        assert transition["victim_alive_before"], transition
    elif mode == "io":
        # At most 256 MiB written and read; recovery can interrupt this finite work.
        fd = os.open(
            "/mnt/pressure/finite.bin", os.O_CREAT | os.O_RDWR | os.O_DIRECT, 0o600
        )
        buf = mmap.mmap(-1, MIB)
        buf.write(os.urandom(MIB))
        wait_for_go(out, "io")
        try:
            for _ in range(256):
                assert os.write(fd, buf) == MIB
            os.fdatasync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            for _ in range(256):
                assert os.readv(fd, [buf]) == MIB
        finally:
            os.close(fd)
    else:
        raise ValueError(mode)


if __name__ == "__main__":
    main()
