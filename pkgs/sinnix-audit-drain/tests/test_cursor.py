"""An unreadable cursor must never become a new audit capture window."""
import os
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-audit-drain"


@pytest.mark.parametrize("kind", ["empty", "directory", "denied", "invalid"])
def test_bad_cursor_never_queries_audit_or_changes_cursor(tmp_path, kind):
    binary = tmp_path / "bin"
    binary.mkdir()
    marker = tmp_path / "queried"
    search = binary / "ausearch"
    search.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 1\n")
    search.chmod(0o755)
    cursor = tmp_path / "cursor"
    if kind == "directory":
        cursor.mkdir()
    else:
        cursor.write_bytes({"empty": b"", "denied": b"1700000000\n", "invalid": b"not-an-epoch\n"}[kind])
        if kind == "denied":
            cursor.chmod(0)
    result = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True,
        env={**os.environ, "PATH": str(binary) + ":" + os.environ["PATH"],
             "SINNIX_AUDIT_LANE": str(tmp_path / "lane"),
             "SINNIX_AUDIT_WATERMARK": str(cursor)},
    )
    assert result.returncode != 0
    assert not marker.exists(), result.stderr
    if kind == "directory":
        assert cursor.is_dir()
    else:
        cursor.chmod(0o600)
        assert cursor.read_bytes() == {"empty": b"", "denied": b"1700000000\n", "invalid": b"not-an-epoch\n"}[kind]


def test_absent_cursor_starts_first_window(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    marker = tmp_path / "queried"
    search = binary / "ausearch"
    search.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{marker}'\nexit 1\n")
    search.chmod(0o755)
    cursor = tmp_path / "cursor"
    result = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True,
        env={**os.environ, "PATH": str(binary) + ":" + os.environ["PATH"],
             "SINNIX_AUDIT_LANE": str(tmp_path / "lane"),
             "SINNIX_AUDIT_WATERMARK": str(cursor)},
    )
    assert result.returncode == 0, result.stderr
    assert marker.read_text().splitlines() == ["-ts", "today", "--format", "raw"]
    assert cursor.read_text().strip().isdigit()
