"""Build the driver, then run QEMU inside this declared operation's limits."""

import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

output = Path(sys.argv[1]).resolve()
output.mkdir(mode=0o700, parents=True, exist_ok=False)
# A Nix daemon build does not inherit this unit's memory/IO limits. Build only
# the driver here; the pressure VM itself runs as our direct descendant below.
build = subprocess.run(
    [
        "nix",
        "build",
        "--no-link",
        "--print-out-paths",
        "--max-jobs",
        "1",
        "--cores",
        "2",
        ".#packages.x86_64-linux.earlyoom-real-pressure-driver",
    ],
    text=True,
    stdout=subprocess.PIPE,
    check=True,
    timeout=1200,
)
driver = Path(build.stdout.strip()) / "bin/nixos-test-driver"
relative = Path("/proc/self/cgroup").read_text().strip().split("::", 1)[1]
group = Path("/sys/fs/cgroup", relative.lstrip("/"))
limits = {
    name: (group / name).read_text()
    for name in ("memory.max", "memory.swap.max", "io.max")
}
assert int(limits["memory.max"]) <= 4 * 1024**3, limits
assert limits["memory.swap.max"].strip() == "0", limits
devices = {}
for mount in ("/realm", "/nix"):
    source = (
        subprocess.check_output(
            ["findmnt", "--noheadings", "--output", "SOURCE", "--target", mount],
            text=True,
        )
        .strip()
        .split("[", 1)[0]
    )
    block = os.stat(source).st_rdev
    device = f"{os.major(block)}:{os.minor(block)}"
    # systemd IO limits apply to the containing whole block device.
    sysdev = Path("/sys/dev/block", device).resolve()
    if (sysdev / "partition").exists():
        device = (sysdev.parent / "dev").read_text().strip()
    rows = {
        row.split()[0]: dict(item.split("=", 1) for item in row.split()[1:])
        for row in limits["io.max"].splitlines()
    }
    assert device in rows, (mount, device, limits)
    assert all(0 < int(rows[device][key]) <= 8_000_000 for key in ("rbps", "wbps")), (
        mount,
        device,
        limits,
    )
    devices[mount] = device
runtime = Path(tempfile.mkdtemp(prefix="earlyoom-vm-", dir="/realm/tmp/work"))
assert runtime.stat().st_mode & 0o777 == 0o700
for suffix in ("vde1.ctl/ctl", "tmp/tmpXXXXXXXX/machine-console"):
    assert len(os.fsencode(runtime / suffix)) + 1 <= 108, (
        "UNIX socket path exceeds sockaddr_un"
    )
temporary = runtime / "tmp"
temporary.mkdir(mode=0o700)
(output / "runtime-owner.json").write_text(
    json.dumps(
        {
            "runtime_root": str(runtime),
            "owner_pid": os.getpid(),
            "cgroup": relative,
            "job_id": os.environ.get("AGENTCTL_JOB_ID"),
        }
    )
)
driver_env = os.environ | {"XDG_RUNTIME_DIR": str(runtime), "TMPDIR": str(temporary)}
owned = {}
started = time.monotonic()
returncode = None
child = None


def interrupted(signum, frame):
    raise SystemExit(f"interrupted by signal {signum}")


signal.signal(signal.SIGTERM, interrupted)


def stop_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass  # owned group already exited; still reap the recorded child


try:
    with (output / "driver.log").open("wb") as log:
        child = subprocess.Popen(
            [str(driver), "-o", str(output)],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=output,
            env=driver_env,
        )
        while child.poll() is None and time.monotonic() - started < 420:
            for process in Path("/proc").iterdir():
                if not process.name.isdecimal() or int(process.name) in owned:
                    continue
                try:
                    command = (process / "cmdline").read_bytes().split(b"\0")[0]
                    basename = os.fsdecode(command).rsplit("/", 1)[-1].lstrip(".")
                    kind = (
                        "qemu"
                        if basename.startswith("qemu-system-")
                        else "vde"
                        if basename.startswith(("vde_switch", "vde_plug2tap"))
                        else None
                    )
                    if kind is None:
                        continue
                    membership = (
                        (process / "cgroup").read_text().strip().split("::", 1)[1]
                    )
                    if membership != relative and not membership.startswith(
                        relative + "/"
                    ):
                        continue
                    if os.getpgid(int(process.name)) != child.pid:
                        continue
                    pid = int(process.name)
                    before_stat = (process / "stat").read_text()
                    before_start = before_stat.rsplit(")", 1)[1].split()[19]
                    fd = os.pidfd_open(pid)
                    try:
                        after_stat = (process / "stat").read_text()
                        after_start = after_stat.rsplit(")", 1)[1].split()[19]
                        after_group = (
                            (process / "cgroup").read_text().strip().split("::", 1)[1]
                        )
                        after_command = (
                            (process / "cmdline").read_bytes().split(b"\0")[0]
                        )
                        if (
                            before_start != after_start
                            or after_group != membership
                            or after_command != command
                            or os.getpgid(pid) != child.pid
                        ):
                            os.close(fd)
                            continue
                    except BaseException:
                        os.close(fd)
                        raise
                    owned[pid] = {
                        "fd": fd,
                        "cgroup": membership,
                        "stat": after_stat,
                        "start_ticks": after_start,
                        "command": os.fsdecode(after_command),
                        "kind": kind,
                    }
                except (FileNotFoundError, ProcessLookupError):
                    pass
            time.sleep(0.2)
        if child.poll() is None:
            stop_group(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                stop_group(child.pid, signal.SIGKILL)
        returncode = child.wait(timeout=1)
finally:
    if child is not None and child.poll() is None:
        stop_group(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            stop_group(child.pid, signal.SIGKILL)
            child.wait(timeout=1)
    if child is not None:
        returncode = child.returncode
    for process in owned.values():
        poll = select.poll()
        poll.register(process["fd"], select.POLLIN)
        process["terminal_before_cleanup"] = bool(poll.poll(0))
        if not process["terminal_before_cleanup"]:
            try:
                signal.pidfd_send_signal(process["fd"], signal.SIGKILL)
            except ProcessLookupError:
                pass
        process["terminal"] = bool(poll.poll(1000))
        os.close(process.pop("fd"))
    receipt = {
        "driver": str(driver),
        "driver_returncode": returncode,
        "seconds": time.monotonic() - started,
        "cgroup": relative,
        "limits": limits,
        "devices": devices,
        "runtime_root": str(runtime),
        "temporary_root": str(temporary),
        "qemu": owned,
    }
    if all(process["terminal"] for process in owned.values()):
        shutil.rmtree(runtime)
        receipt["runtime_cleaned"] = True
    else:
        receipt["runtime_cleaned"] = False
    (output / "host-receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)
assert any(process["kind"] == "qemu" for process in owned.values()), (
    "no QEMU cgroup membership observed"
)
assert all(p["terminal"] and p["terminal_before_cleanup"] for p in owned.values()), (
    "VM required forced cleanup"
)
assert returncode == 0, f"driver failed: {returncode}; inspect {output}/driver.log"
