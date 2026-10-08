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
