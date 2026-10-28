"""Exercise screenshot custody with a synthetic adb executable."""

import os
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

# The Nix build sandbox has no /usr/bin/env, so fixtures name bash directly.
BASH = shutil.which("bash") or "/bin/sh"

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-phone"


def png():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\0\0\0"))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("mode", ["ok", "failed", "empty", "invalid", "truncated"])
@pytest.mark.parametrize("explicit", [False, True])
def test_screenshot_preserves_staging_until_verified(tmp_path, mode, explicit):
    binary = tmp_path / "bin"
    binary.mkdir()
    payload = tmp_path / "payload"
    payload.write_bytes(
        {"empty": b"", "invalid": b"not PNG", "truncated": png()[:-3]}.get(mode, png())
    )
    adb = binary / "adb"
    adb.write_text(f"""#!{BASH}
printf '%s\\n' "$*" >> "$CALLS"
if [ "$1" = pull ]; then
  cp "$PAYLOAD" "$3"
  [ "$MODE" != failed ]
fi
""")
    adb.chmod(0o755)
    xdg = binary / "xdg-user-dir"
    xdg.write_text(f'#!{BASH}\nprintf "%s\\n" "$PICTURES"\n')
    xdg.chmod(0o755)
    body = SCRIPT.read_text().split("\nscreenshot)\n")[1].split("\n  ;;")[0]
    out = tmp_path / "explicit.png"
    out.write_bytes(b"previous")
    env = {
        **os.environ,
        "PATH": f'{binary}:{os.environ["PATH"]}',
        "CALLS": str(tmp_path / "calls"),
        "PAYLOAD": str(payload),
        "MODE": mode,
        "PICTURES": str(tmp_path / "pictures"),
    }
    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail\nensure_adb() { :; }\nadb_phone() { adb "$@"; }\n'
            + body,
            "screenshot",
            *(["--out", str(out)] if explicit else []),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    calls = (tmp_path / "calls").read_text()
    assert ("shell rm -f" in calls) == (mode == "ok")
    assert (result.returncode == 0) == (mode == "ok"), result.stderr
    if mode == "ok":
        destination = Path(result.stdout.strip())
        assert destination.read_bytes() == png()
        if not explicit:
            assert destination.parent == tmp_path / "pictures/sinnix-phone"
    elif explicit:
        assert out.read_bytes() == b"previous"
    assert not list(tmp_path.rglob(".phone-shot.*"))
