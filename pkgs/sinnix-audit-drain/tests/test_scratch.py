"""Audit staging is private and cannot leak between temporary allocations."""
import os
from pathlib import Path
import shutil
import subprocess

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-audit-drain"


def run_drain(tmp_path, failure=False):
    binary = tmp_path / "bin"
    binary.mkdir()
    cursor = tmp_path / "cursor"
    cursor.mkdir()
    watermark = cursor / "last-run"
    watermark.write_text("1700000000\n")
    counter = tmp_path / "allocations"
    mktemp = binary / "mktemp"
    mktemp.write_text(f"#!/bin/sh\nn=0; [ ! -f '{counter}' ] || n=$(cat '{counter}'); n=$((n+1)); echo $n > '{counter}'; [ $n -ne 2 ] || exit 70; exec {shutil.which('mktemp')} \"$@\"\n")
    mktemp.chmod(0o755)
    search = binary / "ausearch"
    search.write_text("#!/bin/sh\n" + ("echo synthetic-error >&2; exit 2\n" if failure else "exit 1\n"))
    search.chmod(0o755)
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, umask=0,
        env={**os.environ, "PATH": str(binary) + ":" + os.environ["PATH"],
             "SINNIX_AUDIT_LANE": str(tmp_path / "lane"), "SINNIX_AUDIT_WATERMARK": str(watermark)})
    return result, cursor, watermark


def test_single_allocation_cannot_leave_first_file(tmp_path):
    result, cursor, watermark = run_drain(tmp_path)
    assert result.returncode == 0, result.stderr
    assert {p.name for p in cursor.iterdir()} == {"last-run"}
    assert (tmp_path / "allocations").read_text().strip() == "1"


def test_failed_audit_read_cleans_scratch_and_holds_cursor(tmp_path):
    result, cursor, watermark = run_drain(tmp_path, failure=True)
    assert result.returncode == 1
    assert watermark.read_text() == "1700000000\n"
    assert {p.name for p in cursor.iterdir()} == {"last-run"}
    assert (tmp_path / "lane").stat().st_mode & 0o777 == 0o700
