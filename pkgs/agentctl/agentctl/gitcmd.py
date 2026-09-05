"""One local `git` call; the caller names the exception class a failure raises."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from .limits import CALL_TIMEOUT_SECONDS


def git(
    path: Path,
    *arguments: str,
    timeout: float = CALL_TIMEOUT_SECONDS,
    error: type[Exception],
    ok_statuses: Sequence[int] = (0,),
) -> str:
    """stdout of the call; any exit status outside ``ok_statuses`` raises ``error``."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise error(f"git {arguments[0]} failed in {path}: {failure}") from failure
    if completed.returncode not in ok_statuses:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise error(f"git {' '.join(arguments[:2])}: {detail}")
    return completed.stdout.strip()
