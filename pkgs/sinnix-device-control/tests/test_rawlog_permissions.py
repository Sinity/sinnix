"""New operator journal files stay private even under a permissive caller."""
import os
from pathlib import Path
import subprocess

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/rawlog"


def test_new_journal_is_owner_only(tmp_path):
    log = tmp_path / "raw-log.md"
    binary = tmp_path / "bin"
    binary.mkdir()
    notify = binary / "notify-send"
    notify.write_text("#!/bin/sh\nexit 0\n")
    notify.chmod(0o755)
    result = subprocess.run(
        ["bash", str(SCRIPT), "neutral fixture entry"],
        env={**os.environ, "RAWLOG_FILE": str(log), "PATH": str(binary) + ":" + os.environ["PATH"]},
        capture_output=True, text=True, umask=0,
    )
    assert result.returncode == 0, result.stderr
    assert log.stat().st_mode & 0o777 == 0o600
    assert "neutral fixture entry" in log.read_text()
