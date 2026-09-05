"""The `gh` adapter: pull requests by number, their checks, and the merge.

agentctl never infers a PR from a branch name sweep: a run stores the number
it created and asks for that. A merge names the exact head it verified.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

GH_TIMEOUT_SECONDS = 60
_PR_FIELDS = (
    "number,url,title,state,isDraft,mergeable,headRefName,headRefOid,baseRefName,"
    "mergeCommit,autoMergeRequest,statusCheckRollup,reviewDecision,updatedAt"
)
_FAILED = {
    "FAILURE",
    "ERROR",
    "CANCELLED",
    "TIMED_OUT",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
}
_PASSED = {"SUCCESS", "NEUTRAL"}


class GithubError(RuntimeError):
    """gh refused a request or published output this module cannot read."""


def _run(argv: Sequence[str], *, cwd: Path, timeout: float = GH_TIMEOUT_SECONDS) -> str:
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


def pull_request_for_branch(root: Path, branch: str) -> Mapping[str, Any] | None:
    """The open PR whose head is ``branch``, or None."""
    value = gh_json(
        ["pr", "list", "--state", "open", "--head", branch, "--json", _PR_FIELDS],
        cwd=root,
    )
    rows = (
        [row for row in value if isinstance(row, Mapping)]
        if isinstance(value, list)
        else []
    )
    return dict(rows[0]) if rows else None


def create_pull_request(
    root: Path, *, head: str, base: str, title: str, body: str
) -> int:
    """Open a PR and return its number, read from the URL gh prints."""
    output = _run(
        [
            "gh",
            "pr",
            "create",
            "--head",
            head,
            "--base",
            base,
            "--title",
            title,
            "--body",
            body,
        ],
        cwd=root,
    )
    match = re.search(r"/pull/(\d+)", output)
    if match is None:
        raise GithubError(f"gh pr create printed no PR URL: {output.strip()!r}")
    return int(match.group(1))


def required_checks(root: Path, base_branch: str) -> tuple[str, ...]:
    """The base branch's required status contexts; none when unprotected."""
    try:
        value = gh_json(
            [
                "api",
                f"repos/{{owner}}/{{repo}}/branches/{base_branch}/protection/required_status_checks/contexts",
            ],
            cwd=root,
        )
    except GithubError as error:
        if "404" in str(error) or "not protected" in str(error).lower():
            return ()
        raise
    return (
        tuple(item for item in value if isinstance(item, str))
        if isinstance(value, list)
        else ()
    )


def _check_name(check: Mapping[str, Any]) -> str:
    return str(check.get("name") or check.get("context") or "")


def _check_outcome(check: Mapping[str, Any]) -> str:
    """One rollup entry as passed, failed, skipped or pending."""
    conclusion = str(check.get("conclusion") or "").upper()
    state = str(check.get("state") or "").upper()
    status = str(check.get("status") or "").upper()
    if conclusion in _FAILED or state in _FAILED:
        return "failed"
    if conclusion == "SKIPPED":
        return "skipped"
    if conclusion in _PASSED or state == "SUCCESS":
        return "passed"
    if status == "COMPLETED" and conclusion:
        return "failed"
    return "pending"


def check_rollup(pull: Mapping[str, Any], required: Sequence[str] = ()) -> str:
    """``failed``, ``pending`` or ``ready`` for the PR's checks.

    A required check that is missing from the rollup or was skipped has not
    passed: it is pending, never ready. Without a required list every check
    present must have passed.
    """
    rollup = pull.get("statusCheckRollup")
    entries = (
        [check for check in rollup if isinstance(check, Mapping)]
        if isinstance(rollup, list)
        else []
    )
    outcomes = {_check_name(check): _check_outcome(check) for check in entries}
    if any(outcome == "failed" for outcome in outcomes.values()):
        return "failed"
    for name in required:
        if outcomes.get(name) != "passed":
            return "pending"
    if not required and (
        not entries or any(outcome != "passed" for outcome in outcomes.values())
    ):
        return "pending" if entries else "ready"
    if any(outcome == "pending" for outcome in outcomes.values()):
        return "pending"
    return "ready"


def hosted_check_state(pull: Mapping[str, Any], name: str) -> str:
    """``success``, ``failure``, ``pending`` or ``missing`` for one named check."""
    rollup = pull.get("statusCheckRollup")
    if not isinstance(rollup, list):
        return "missing"
    for check in rollup:
        if isinstance(check, Mapping) and _check_name(check) == name:
            outcome = _check_outcome(check)
            if outcome == "passed":
                return "success"
            if outcome == "failed":
                return "failure"
            return "pending"
    return "missing"


def pull_request_advisory(root: Path, number: int) -> list[dict[str, Any]]:
    """The PR's reviews and comments: author, state, head sha, url."""
    value = gh_json(
        ["pr", "view", str(number), "--json", "reviews,comments"], cwd=root
    )
    document = value if isinstance(value, Mapping) else {}
    rows: list[dict[str, Any]] = []
    for kind, key in (("review", "reviews"), ("comment", "comments")):
        entries = document.get(key)
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, Mapping):
                continue
            author = entry.get("author")
            commit = entry.get("commit")
            rows.append(
                {
                    "kind": kind,
                    "author": author.get("login") if isinstance(author, Mapping) else None,
                    "state": entry.get("state"),
                    "head_sha": commit.get("oid") if isinstance(commit, Mapping) else None,
                    "url": entry.get("url"),
                }
            )
    return rows


def merge_pr(root: Path, number: int, sha: str) -> None:
    """Squash-merge the PR only while its head is still ``sha``."""
    try:
        _run(
            ["gh", "pr", "merge", str(number), "--squash", "--match-head-commit", sha],
            cwd=root,
        )
    except GithubError as error:
        message = str(error)
        if "head" in message.lower() and (
            "match" in message.lower() or "mismatch" in message.lower()
        ):
            raise GithubError(
                f"PR #{number} head is no longer {sha[:12]}: {message}"
            ) from error
        raise


def push_branch(
    root: Path, branch: str, *, sha: str, lease: str | None, timeout: float = 2_400
) -> None:
    """Push ``sha`` to ``origin/<branch>``, leasing on the head last observed there."""
    arguments = ["git", "-C", str(root), "push"]
    if lease is None:
        arguments.append(f"--force-with-lease=refs/heads/{branch}:")
    else:
        arguments.append(f"--force-with-lease=refs/heads/{branch}:{lease}")
    arguments.extend(("origin", f"{sha}:refs/heads/{branch}"))
    _run(arguments, cwd=root, timeout=timeout)


def remote_head(root: Path, branch: str) -> str | None:
    """The remote branch's head, or None when the branch does not exist there."""
    output = _run(
        ["git", "-C", str(root), "ls-remote", "origin", f"refs/heads/{branch}"],
        cwd=root,
    )
    rows = output.split()
    if not rows:
        return None
    if len(rows) != 2 or not re.fullmatch(r"[0-9a-f]{40}", rows[0]):
        raise GithubError(f"git ls-remote returned an unexpected result for {branch}")
    return rows[0]
