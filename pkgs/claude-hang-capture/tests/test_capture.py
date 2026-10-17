import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "claude-hang-capture"


@pytest.mark.parametrize("project_exists", [False, True])
def test_capture_reports_output_when_transcript_directory_is_missing(tmp_path, project_exists):
    home = tmp_path / "home"
    home.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command, body in {
        "sudo": "exit 1",
        "gdb": "echo synthetic-native-stack",
        "ss": "exit 0",
        "systemctl": "exit 0",
        "sleep": "exit 0",
    }.items():
        path = bin_dir / command
        path.write_text(f"#!{shutil.which('bash')}\n" + body + "\n")
        path.chmod(0o755)
    cwd = tmp_path / "work"
    cwd.mkdir()
    if project_exists:
        import re
        project = home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
        project.mkdir(parents=True)
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=cwd)
    try:
        result = subprocess.run(
            ["bash", str(SCRIPT), str(process.pid)],
            env=dict(os.environ, HOME=str(home), TMPDIR=str(scratch), PATH=str(bin_dir) + os.pathsep + os.environ["PATH"]),
            capture_output=True, text=True, timeout=15,
        )
    finally:
        process.terminate()
        process.wait(timeout=5)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"pid {process.pid}: captured to " in result.stdout
    captures = list((scratch / "claude-hang").iterdir())
    assert len(captures) == 1
    assert (captures[0] / "native-stacks.txt").read_text().strip() == "synthetic-native-stack"
    if not project_exists:
        assert "transcript discovery unavailable" in (captures[0] / "summary.txt").read_text()
        assert (captures[0] / "transcript-discovery-error.txt").read_text()
