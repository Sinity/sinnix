"""Exercise BCR intake with real decoding and a controlled ADB transport."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

source = Path(sys.argv[1]).read_text()
function = source[
    source.index("drain_bcr_calls_adb() {") : source.index("nix_userland_identity() {")
]
builder = source[
    source.index("adb_shell_args() {") : source.index("# The grants the app needs")
]
mock = r"""
sinnix-remote-command() { python3 "$BCR_ENCODER" "$@"; }
adb_resolve() { return 0; }
adb_any() {
  case "$1" in
    pull)
      if [ "$BCR_MODE" = "failed" ]; then
        printf cut > "$3"
        return 1
      fi
      cp "$BCR_FIXTURE" "$3"
      ;;
    shell)
      shift
      [ "$1" = -T ] && shift
      case "$1" in
        find*)
          [ "$BCR_MODE" != "inventory-failed" ] || return 1
          printf '%s\0' '/sdcard/Android/data/com.chiller3.bcr/files/neutral call.oga'
          ;;
        stat*)
          # Confirm the device shell receives an escaped path with spaces.
          [[ "$1" == *"'"*'neutral call.oga'*"'"* ]] || return 1
          stat -c %s "$BCR_FIXTURE"
          ;;
        test*) return 1 ;;
        *) return 1 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}
"""
with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    fixture = root / "fixture.oga"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            "-c:a",
            "libopus",
            str(fixture),
        ],
        check=True,
    )
    harness = (
        "set -euo pipefail\n" + mock + builder + function + "\ndrain_bcr_calls_adb\n"
    )

    def run(mode, lake):
        return subprocess.run(
            ["bash", "-c", harness],
            env={
                **os.environ,
                "BCR_MODE": mode,
                "BCR_FIXTURE": str(fixture),
                "LAKE_ROOT": str(lake),
                "BCR_ENCODER": sys.argv[2],
            },
            capture_output=True,
            text=True,
        )

    lake = root / "lake"
    result = run("normal", lake)
    assert result.returncode == 0, result.stderr + result.stdout
    archive = lake / "calls" / "neutral call.oga"
    assert archive.read_bytes() == fixture.read_bytes()
    ledger = lake / "calls" / "levels.jsonl"
    row = json.loads(ledger.read_text())
    assert row["duration_seconds"] > 0 and row["captured_nothing"] is False
    result = run("normal", lake)
    assert result.returncode == 0 and len(ledger.read_text().splitlines()) == 1
    # A cut transfer must preserve the previous archive and never add a receipt.
    archive.write_bytes(b"previous")
    before = ledger.read_bytes()
    result = run("failed", lake)
    assert result.returncode != 0
    assert archive.read_bytes() == b"previous" and ledger.read_bytes() == before
    assert not list((lake / "calls").glob(".incoming.*"))
    result = run("normal", lake)
    assert result.returncode == 0 and archive.read_bytes() == fixture.read_bytes()
    result = run("inventory-failed", lake)
    assert result.returncode != 0
    # Invalid audio must not be cached as successfully audited.
    fixture.write_bytes(b"invalid audio")
    broken = root / "broken"
    result = run("normal", broken)
    assert result.returncode != 0
    assert (broken / "calls" / "levels.jsonl").read_text() == ""
print(
    "BCR intake: real decode, repeat, cut transfer, recovery, inventory and corrupt audio passed"
)

# Transport selection must follow changing TLS ports and ignore other devices.
resolver = source[source.index("adb_resolve() {"):source.index("\nadb_any() {")]
transport_mock = r"""
timeout() { shift; "$@"; }
adb() {
  case "$1" in
    devices) printf 'List of devices attached\nother-device\tdevice\n' ;;
    connect) printf '%s\n' "$2" >> "$CONNECT_LOG" ;;
    -s)
      case "$3" in
        get-state) [ "$2" = other-device ] ;;
        shell)
          case "$2" in
            other-device) echo other-serial ;;
            192.0.2.5:45678) echo enrolled ;;
            *) return 1 ;;
          esac ;;
      esac ;;
  esac
}
avahi-browse() {
  printf '%s\n' '=;eth0;IPv4;adb-other-random;_adb-tls-connect._tcp;local;other.local;192.0.2.6;44444;'
  [ "$DISCOVERY" != missing ] || return 0
  printf '%s\n' '=;eth0;IPv4;adb-enrolled-random;_adb-tls-connect._tcp;local;phone.local;192.0.2.5;45678;'
}
"""
with tempfile.TemporaryDirectory() as scratch:
    log = Path(scratch) / "connections"
    for mode in ("available", "missing"):
        result = subprocess.run(["bash", "-c", "set -euo pipefail\nADB_RESOLVED=''\n" + transport_mock + resolver + "\nadb_resolve\nprintf '%s' \"$ADB_RESOLVED\""], env={**os.environ, "SINNIX_PHONE_ADB_SERIAL":"enrolled", "DISCOVERY":mode, "CONNECT_LOG":str(log)}, capture_output=True, text=True)
        if mode == "available":
            assert result.returncode == 0, result.stderr
            assert result.stdout == "192.0.2.5:45678"
            assert log.read_text().splitlines() == ["192.0.2.5:45678"]
        else:
            assert result.returncode != 0
            assert "unavailable" in result.stderr
print("Wireless ADB: changing TLS endpoint, enrolled serial, wrong device and unavailable discovery passed")

restore = source.split("adb-restore)\n", 1)[1].split("  ;;\nclip-push)", 1)[0]
result = subprocess.run(["bash", "-c", "set -euo pipefail\nadb() { return 0; }\ninstall_wireless_adb_boot() { echo boot-installed; }\nset -- --persistent\n" + restore], env={**os.environ,"SINNIX_PHONE_ADB_SERIAL":"enrolled"}, capture_output=True, text=True)
assert result.returncode == 0, result.stderr
assert "boot-installed" in result.stdout

# Ambient recovery must qualify bytes rather than infer identity from length.
ambient = source[source.index("drain_ambient_adb() {"):source.index("# Preserve and audit BCR call recordings.")]
ambient_mock = r'''
sinnix-remote-command() { python3 "$BCR_ENCODER" "$@"; }
adb_resolve() { return 0; }
adb_any() {
  case "$1" in
    pull)
      case "$AMBIENT_MODE" in
        failed) printf cut > "$3"; return 1 ;;
        truncated) printf cut > "$3" ;;
        changed) cp "$BCR_FIXTURE" "$3"; printf changed > "$BCR_FIXTURE" ;;
        *) cp "$BCR_FIXTURE" "$3" ;;
      esac
      ;;
    shell)
      shift
      if [ "$1" = -T ]; then shift; fi
      case "$1" in
        find*) printf '%s\0' '/sdcard/sinnix-ambient/neutral chunk.m4a' ;;
        sha256sum*)
          [ "$AMBIENT_MODE" != unavailable ] || return 1
          sha256sum "$BCR_FIXTURE" ;;
        *) return 1 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}
'''
with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    fixture = root / "payload"
    fixture.write_bytes(b"verified neutral fixture")
    lake = root / "lake"
    harness = "set -euo pipefail\n" + ambient_mock + builder + ambient + "\ndrain_ambient_adb\n"

    def run_ambient(mode):
        fixture.write_bytes(b"verified neutral fixture")
        return subprocess.run(["bash", "-c", harness], capture_output=True, text=True,
                              env={**os.environ, "AMBIENT_MODE": mode, "BCR_FIXTURE": str(fixture),
                                   "BCR_ENCODER": sys.argv[2], "LAKE_ROOT": str(lake)})

    result = run_ambient("normal")
    assert result.returncode == 0, result.stdout + result.stderr
    target = lake / "ambient" / "neutral chunk.m4a"
    assert target.read_bytes() == fixture.read_bytes()
    # Same length is not continuity. Preserve both versions; retries are stable.
    original = b"X" * fixture.stat().st_size
    target.write_bytes(original)
    result = run_ambient("normal")
    assert result.returncode == 0, result.stdout + result.stderr
    versions = list(target.parent.glob("*.conflict-*"))
    assert len(versions) == 1 and versions[0].read_bytes() == fixture.read_bytes()
    assert target.read_bytes() == original
    result = run_ambient("normal")
    assert result.returncode == 0 and len(list(target.parent.glob("*.conflict-*"))) == 1
    for mode in ["failed", "truncated", "unavailable", "changed"]:
        result = run_ambient(mode)
        assert result.returncode != 0
        assert target.read_bytes() == original
        assert any(p.read_bytes() == b"cut" for p in target.parent.glob(".incoming.*"))
    outside = root / "outside"
    outside.write_bytes(b"unrelated")
    target.unlink()
    target.symlink_to(outside)
    result = run_ambient("normal")
    assert result.returncode == 0 and outside.read_bytes() == b"unrelated"

    # A directory at the conflict destination must never receive a nested link.
    versions[0].unlink()
    versions[0].mkdir()
    result = run_ambient("normal")
    assert result.returncode != 0 and not list(versions[0].iterdir())
    assert outside.read_bytes() == b"unrelated"
