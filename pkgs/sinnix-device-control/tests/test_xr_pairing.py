"""USB setup failure must not open WiVRn pairing."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-xr"


def test_failed_usb_reverse_does_not_open_pairing(tmp_path):
    commands = {
        "sinnix": 'case "$*" in *get-serialno*) echo synthetic-quest;; esac\n',
        "adb": 'case "$*" in *list\\ packages*) echo package:org.meumeu.wivrn;; *reverse*) exit 7;; esac\n',
        "systemctl": "exit 0\n",
        "wivrnctl": 'echo pairing >> "$PAIRING_MARKER"\n',
    }
    for name, body in commands.items():
        path = tmp_path / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
    marker = tmp_path / "pairing"
    result = subprocess.run(
        ["bash", str(SCRIPT), "wivrn-wired"],
        env={
            **os.environ,
            "PATH": str(tmp_path) + ":" + os.environ["PATH"],
            "PAIRING_MARKER": str(marker),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not marker.exists(), "pairing opened despite failed USB transport"
