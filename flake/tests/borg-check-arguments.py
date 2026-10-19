"""Reject unbounded/invalid options before Borg or scratch access."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    env = {**os.environ, "TMPDIR": directory, "BORG_PASSCOMMAND": "synthetic"}
    cases = [
        ["--max-duration", value] for value in ("0", "-1", "1.5", "garbage", "01", "")
    ]
    cases += [["--within-days", value] for value in ("0", "-1", "garbage")]
    cases += [
        [option] for option in ("--repo", "--log", "--within-days", "--max-duration")
    ]
    for arguments in cases:
        result = subprocess.run(
            ["bash", sys.argv[1], *arguments], env=env, capture_output=True, text=True
        )
        assert result.returncode == 2, (arguments, result.returncode, result.stderr)
        assert not list(Path(directory).iterdir()), arguments
    # Valid values reach the credential guard, without starting a check.
    env.pop("BORG_PASSCOMMAND")
    for arguments in ([], ["--max-duration", "1"], ["--within-days", "1"]):
        result = subprocess.run(
            ["bash", sys.argv[1], *arguments], env=env, capture_output=True, text=True
        )
        assert (
            result.returncode == 2 and "BORG_PASSCOMMAND must be set" in result.stderr
        ), result
        assert not list(Path(directory).iterdir()), arguments
print("Borg drill argument boundaries passed")
