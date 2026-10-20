"""Read the recorded pull request by number through gh.

Historical manifests supply the exact PR number. This adapter observes it
without creating, changing, merging, pushing or deleting forge state.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .limits import CALL_TIMEOUT_SECONDS

_PR_FIELDS = (
    "number,url,title,state,isDraft,mergeable,headRefName,headRefOid,baseRefName,"
    "mergeCommit,autoMergeRequest,statusCheckRollup,reviewDecision,updatedAt"
)


class GithubError(RuntimeError):
    """gh refused a request or published output this module cannot read."""


def _run(
    argv: Sequence[str], *, cwd: Path, timeout: float = CALL_TIMEOUT_SECONDS
) -> str:
    try:
        completed = subprocess.run(
            list(argv), cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as error:
        raise GithubError(f"{argv[0]} is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise GithubError(f"{' '.join(argv[:2])} timed out") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GithubError(detail or f"{' '.join(argv[:2])} failed")
    return completed.stdout


def gh_json(arguments: Sequence[str], *, cwd: Path) -> Any:
    output = _run(["gh", *arguments], cwd=cwd)
    try:
        return json.loads(output) if output.strip() else None
    except json.JSONDecodeError as error:
        raise GithubError("gh did not print JSON") from error


def pull_request(root: Path, number: int) -> Mapping[str, Any] | None:
    """The PR with that number, or None when the repository has none."""
    try:
        value = gh_json(["pr", "view", str(number), "--json", _PR_FIELDS], cwd=root)
    except GithubError as error:
        message = str(error).lower()
        if "could not resolve" in message or "not found" in message:
            return None
        raise
    return value if isinstance(value, Mapping) else None
