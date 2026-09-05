"""One local `git` call; the caller names the exception class a failure raises."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .limits import CALL_TIMEOUT_SECONDS


def git(
    path: Path,
    *arguments: str,
    timeout: float = CALL_TIMEOUT_SECONDS,
    error: type[Exception],
) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise error(f"git {arguments[0]} failed in {path}: {failure}") from failure
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise error(f"git {' '.join(arguments[:2])}: {detail}")
    return completed.stdout.strip()
