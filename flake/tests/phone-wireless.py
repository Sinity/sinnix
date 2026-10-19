"""Exercise the installed hook's state transitions without a real phone."""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

source = Path(sys.argv[1]).read_text()
hook = source.split("boot_script=$(cat <<'BOOT'\n", 1)[1].split("\nBOOT\n", 1)[0]


def connected(bssid):
    return f'Wifi is enabled\nWifi is connected to "Fixture"\nWifiInfo: SSID: "Fixture", BSSID: {bssid}, MAC: 02:00:00:00:00:01\n'


A = connected("aa:bb:cc:dd:ee:01")
B = connected("aa:bb:cc:dd:ee:02")
OFF = "Wifi is enabled\nWifi is not connected\n"
MOCK = r"""
step() { cat "$PROBE_ROOT/step"; }
getprop() { if [ "$(step)" -lt "$BOOT_READY" ]; then echo 0; else echo 1; fi; }
cmd() {
  [ "$*" = 'wifi status' ] || return 1
  i=$(step)
  if [ -f "$PROBE_ROOT/manual-off-$i" ]; then echo 0 > "$PROBE_ROOT/enabled"; fi
  if [ -f "$PROBE_ROOT/error-$i" ]; then return 1; fi
  cat "$PROBE_ROOT/frame-$i"
}
settings() {
  [ "$*" = 'put global adb_wifi_enabled 1' ] || return 1
  step >> "$PROBE_ROOT/writes"
  echo 1 > "$PROBE_ROOT/enabled"
}
sleep() {
  i=$(($(step) + 1))
  if [ "$i" -ge "$FRAME_COUNT" ]; then
    python3 -c 'import pathlib,sys; (pathlib.Path(sys.argv[1])/"wireless.sh").unlink()' "$PROBE_ROOT"
    exit 0
  fi
  printf '%s\n' "$i" > "$PROBE_ROOT/step"
}
"""


def run(frames, *, boot_ready=0, errors=(), manual_off=()):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        script = root / "wireless.sh"
        script.write_text(
            hook.replace("/data/adb/sinnix-wireless-adb", str(root / "owner"))
        )
        (root / "mocks").write_text(MOCK)
        (root / "step").write_text("0\n")
        for i, frame in enumerate(frames):
            (root / f"frame-{i}").write_text(frame)
        for i in errors:
            (root / f"error-{i}").touch()
        for i in manual_off:
            (root / f"manual-off-{i}").touch()
        result = subprocess.run(
            ["bash", str(script)],
            env={
                **os.environ,
                "BASH_ENV": str(root / "mocks"),
                "PROBE_ROOT": str(root),
                "BOOT_READY": str(boot_ready),
                "FRAME_COUNT": str(len(frames)),
            },
            text=True,
            capture_output=True,
            timeout=5,
        )
        assert result.returncode == 0, result.stderr
        writes = root / "writes"
        if manual_off:
            assert (root / "enabled").read_text().strip() == "0"
        return (
            [int(line) for line in writes.read_text().splitlines()]
            if writes.exists()
            else []
        )


# Boot can complete after the predecessor's six-minute cutoff. Association
# can arrive later still; neither state may permanently abandon recovery.
assert run([OFF] * 43 + [A, A], boot_ready=40) == [43]
# Steady association, including a deliberate settings-off observation, does
# not get rewritten. Only a later observed reconnect/BSSID change requests it.
assert run([OFF, A, A, A, OFF, A, B, B]) == [1, 5, 6]
assert run([A, A, A, A], manual_off=(1,)) == [0]
# A command failure or unsupported/redacted status is not a disconnect and
# must not fabricate a reconnect that overrides a same-association disable.
assert run([A, A, A], errors=(1,)) == [0]
assert run([A, connected("02:00:00:00:00:00"), A]) == [0]
assert run([A, "unrecognized status\n", A]) == [0]
# Disablement/disassociation is explicit evidence of a network transition.
assert run([A, "Wifi is disabled\n", A]) == [0, 2]
print(
    "Wireless persistence: delayed boot/association, reconnect, BSSID change, same-association disable and unreadable state passed"
)

# Bad restore arguments must refuse before enabling debugging or changing
# the boot hook. Shell mocks observe all effects rather than matching text.
restore = source.split("adb-restore)\n", 1)[1].split("  ;;\nclip-push)", 1)[0]
for arguments in (["--unknown"], ["--persistent", "--unknown"]):
    result = subprocess.run(
        [
            "bash",
            "-c",
            "set -euo pipefail\nadb() { echo adb-effect; }; install_wireless_adb_boot() { echo hook-effect; };\n"
            + restore,
            "restore",
            *arguments,
        ],
        env={**os.environ, "SINNIX_PHONE_ADB_SERIAL": "fixture"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert not result.stdout, result.stdout
print("Wireless restore: invalid arguments refuse before device effects passed")

# Exercise the encoded root update command locally: the first owned hook is
# retained outside service.d and never overwritten on a later update.
installer = source[
    source.index("install_wireless_adb_boot() {") : source.index(
        "# The grants the app needs"
    )
]
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    command_file = root / "command"
    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail\nsinnix-remote-command() { python3 "$ENCODER" "$@"; }; adb_shell_args() { printf %s "$3" > "$COMMAND_FILE"; };\n'
            + installer
            + "\ninstall_wireless_adb_boot",
        ],
        env={**os.environ, "ENCODER": sys.argv[2], "COMMAND_FILE": str(command_file)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    native_root = root / "native"
    service = native_root / "service.d"
    service.mkdir(parents=True)
    target = service / "sinnix-wireless-adb.sh"
    original = b"#!/system/bin/sh\n# Sinnix-owned authenticated wireless ADB startup hook.\noriginal-payload\n"
    target.write_bytes(original)
    target.chmod(0o700)
    command = (
        command_file.read_text()
        .replace("/data/adb", str(native_root))
        .replace("/system/bin/sh", shutil.which("bash"))
    )
    mock_file = root / "native-mocks"
    mock_file.write_text(
        'getprop() { echo 1; }; cmd() { echo "Wifi is not connected"; }; settings() { return 0; };\n'
    )
    environment = {**os.environ, "BASH_ENV": str(mock_file)}
    owner_file = native_root / "sinnix-wireless-adb/owner"

    def stop_owner():
        if owner_file.exists():
            pid, birth, *_ = owner_file.read_text().split()
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            assert str(target).encode() in cmdline
            assert Path(f"/proc/{pid}/stat").read_text().split()[21] == birth
            os.kill(int(pid), signal.SIGTERM)
            deadline = time.monotonic() + 2
            while owner_file.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert not owner_file.exists()

    try:
        for _ in range(2):
            result = subprocess.run(
                ["bash", "-c", command],
                env=environment,
                capture_output=True,
                text=True,
                timeout=8,
            )
            assert result.returncode == 0, result.stderr
            backup = native_root / "sinnix-wireless-adb/original.sh"
            assert backup.read_bytes() == original
            assert backup.stat().st_mode & 0o777 == 0o400
            assert backup.parent.stat().st_mode & 0o777 == 0o700
            assert target.stat().st_mode & 0o777 == 0o700
            assert (
                target.read_text()
                == hook.replace("/data/adb", str(native_root)).replace(
                    "/system/bin/sh", shutil.which("bash")
                )
                + "\n"
            )
            assert "WIRELESS_ADB_OWNER_ACTIVE" in result.stdout
            owner_before = owner_file.read_bytes()
            duplicate = subprocess.run(
                ["bash", str(target)],
                env=environment,
                capture_output=True,
                text=True,
                timeout=2,
            )
            assert duplicate.returncode == 0
            assert owner_file.read_bytes() == owner_before
        # A stale/reused PID record must never grant authority to stop it.
        saved = owner_file.read_bytes()
        pid, birth, *_ = saved.decode().split()
        owner_file.write_text(f"{pid} 0\n")
        try:
            refused = subprocess.run(
                ["bash", "-c", command],
                env=environment,
                capture_output=True,
                text=True,
                timeout=8,
            )
            assert refused.returncode != 0
            assert Path(f"/proc/{pid}/stat").read_text().split()[21] == birth
        finally:
            owner_file.write_bytes(saved)
        stop_owner()
        target.write_text("foreign owner\n")
        result = subprocess.run(
            ["bash", "-c", command],
            env=environment,
            capture_output=True,
            text=True,
            timeout=8,
        )
        assert result.returncode != 0
        assert target.read_text() == "foreign owner\n"
        assert backup.read_bytes() == original
    finally:
        stop_owner()
print(
    "Wireless hook update: preimage/private modes, exact owner restart, single owner and foreign hook refusal passed"
)
