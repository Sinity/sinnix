"""Stateless publication sweep: converge open publication PRs to merged.

One pass derives everything from GitHub and the PR body and stores nothing.
A PR whose hosted review is clean (the reviewer's +1 reaction) and whose CI
is not red merges; findings, conflicts, and absent reviews become typed
spool events for the judgment loop. The bead named by the PR's trailer
closes at merge with the receipt reference — the decision point and the
bookkeeping point are the same act, so a missing-receipt class cannot
exist.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

REVIEWER_LOGIN = "chatgpt-codex-connector"
REVIEW_ABSENT_GRACE_SECONDS = 30 * 60
DEFAULT_SPOOL = Path("/realm/state/agentctl/events.jsonl")
MAX_PR_PAGE = 50

Run = Callable[..., subprocess.CompletedProcess[str]]


class SweepError(RuntimeError):
    """The sweep could not derive the state it acts on."""


@dataclass(frozen=True)
class PullState:
    """Everything one merge decision needs, derived fresh each pass."""

    number: int
    head: str
    created_at: str
    mergeable: str
    ci_red: bool
    review_clean: bool
    review_findings: int
    bead_id: str | None
    receipt_ref: str | None

    @property
    def review_arrived(self) -> bool:
        return self.review_clean or self.review_findings > 0


def parse_trailers(body: str) -> tuple[str | None, str | None]:
    """Read the neutral Bead/Receipt trailer lines harvest stamps."""
    bead = receipt = None
    for line in body.splitlines():
        name, separator, value = line.partition(":")
        if not separator:
            continue
        if name.strip() == "Bead" and value.strip():
            bead = value.strip()
        elif name.strip() == "Receipt" and value.strip():
            receipt = value.strip()
    return bead, receipt


def decide(pull: PullState, *, now: datetime) -> str:
    """The routing table. Pure; every branch is a typed outcome."""
    if pull.mergeable == "CONFLICTING":
        return "conflict"
    if pull.ci_red:
        return "ci-red"
    if pull.review_findings > 0:
        return "findings"
    if pull.review_clean:
        return "merge"
    created = datetime.fromisoformat(pull.created_at.replace("Z", "+00:00"))
    if (now - created).total_seconds() >= REVIEW_ABSENT_GRACE_SECONDS:
        # A third party's outage must not stall publication; merging with the
        # flag on record is fail-open with the failure named, never silent.
        return "merge-review-absent"
    return "wait"


def _command(
    run: Run, argv: Sequence[str], *, timeout: float = 60
) -> subprocess.CompletedProcess[str]:
    try:
        return run(
            list(argv), capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SweepError(f"command unavailable: {argv[0]} ({error})") from error


def _gh_json(run: Run, argv: Sequence[str]) -> Any:
    result = _command(run, argv, timeout=120)
    if result.returncode != 0:
        raise SweepError(result.stderr.strip() or f"gh failed: {' '.join(argv)}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SweepError("gh returned invalid JSON") from error


def derive_pull_states(repo: str, run: Run) -> list[PullState]:
    rows = _gh_json(
        run,
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(MAX_PR_PAGE),
            "--json",
            "number,headRefOid,createdAt,mergeable,body,statusCheckRollup",
        ],
    )
    if not isinstance(rows, list):
        raise SweepError("gh pr list returned a non-list")
    states: list[PullState] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        number = row.get("number")
        if not isinstance(number, int):
            continue
        bead, receipt = parse_trailers(str(row.get("body") or ""))
        if receipt is None:
            # Not a harvest publication (dependabot, hand PRs): out of scope.
            continue
        rollup = row.get("statusCheckRollup")
        ci_red = isinstance(rollup, list) and any(
            isinstance(check, Mapping)
            and (
                check.get("conclusion") == "FAILURE" or check.get("state") == "FAILURE"
            )
            for check in rollup
        )
        reactions = _gh_json(
            run,
            [
                "gh",
                "api",
                f"repos/{repo}/issues/{number}/reactions",
                "--jq",
                f'[.[] | select(.user.login == "{REVIEWER_LOGIN}[bot]"'
                f' or .user.login == "{REVIEWER_LOGIN}") | .content]',
            ],
        )
        review_clean = isinstance(reactions, list) and "+1" in reactions
        comments = _gh_json(
            run,
            [
                "gh",
                "api",
                f"repos/{repo}/pulls/{number}/comments",
                "--jq",
                f'[.[] | select(.user.login == "{REVIEWER_LOGIN}[bot]")] | length',
            ],
        )
        states.append(
            PullState(
                number=number,
                head=str(row.get("headRefOid") or ""),
                created_at=str(row.get("createdAt") or ""),
                mergeable=str(row.get("mergeable") or "UNKNOWN"),
                ci_red=ci_red,
                review_clean=review_clean,
                review_findings=comments if isinstance(comments, int) else 0,
                bead_id=bead,
                receipt_ref=receipt,
            )
        )
    return states


def _append_event(spool: Path, event: Mapping[str, Any]) -> None:
    try:
        spool.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with spool.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(dict(event), sort_keys=True, separators=(",", ":")) + "\n"
            )
    except OSError:
        pass


def _close_bead(
    bead_id: str, reason: str, *, project_root: Path, run: Run
) -> str | None:
    result = _command(
        run,
        [
            "bd",
            "close",
            bead_id,
            "--force",
            "--actor",
            "publication-sweep",
            "--reason",
            reason,
        ],
        timeout=30,
    )
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout).strip()[:300]


def sweep(
    repo: str,
    *,
    project: str,
    project_root: Path,
    spool: Path = DEFAULT_SPOOL,
    run: Run = subprocess.run,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One pass. Returns the JSON receipt of every action taken."""
    observed = now or datetime.now(UTC)
    actions: list[dict[str, Any]] = []
    for pull in derive_pull_states(repo, run):
        verdict = decide(pull, now=observed)
        action: dict[str, Any] = {
            "pr": pull.number,
            "head": pull.head,
            "verdict": verdict,
            "bead": pull.bead_id,
        }
        if verdict in {"merge", "merge-review-absent"}:
            merged = _command(
                run,
                [
                    "gh",
                    "pr",
                    "merge",
                    str(pull.number),
                    "--repo",
                    repo,
                    "--squash",
                ],
                timeout=120,
            )
            if merged.returncode != 0:
                action["error"] = (merged.stderr or merged.stdout).strip()[:300]
                _append_event(
                    spool,
                    {
                        "kind": "publication-sweep",
                        "project": project,
                        "pr": pull.number,
                        "outcome": "merge-failed",
                        "detail": action["error"],
                        "emitted_at": observed.isoformat(),
                    },
                )
            else:
                action["merged"] = True
                if pull.bead_id:
                    reason = (
                        f"Published: PR #{pull.number} merged; receipt "
                        f"{pull.receipt_ref}."
                    )
                    if verdict == "merge-review-absent":
                        reason += " Hosted review absent past grace (fail-open)."
                    close_error = _close_bead(
                        pull.bead_id, reason, project_root=project_root, run=run
                    )
                    if close_error is not None:
                        action["bead_close_error"] = close_error
                _append_event(
                    spool,
                    {
                        "kind": "publication-sweep",
                        "project": project,
                        "pr": pull.number,
                        "outcome": verdict,
                        "bead": pull.bead_id,
                        "emitted_at": observed.isoformat(),
                    },
                )
        elif verdict in {"findings", "conflict", "ci-red"}:
            _append_event(
                spool,
                {
                    "kind": "publication-sweep",
                    "project": project,
                    "pr": pull.number,
                    "outcome": verdict,
                    "findings": pull.review_findings,
                    "bead": pull.bead_id,
                    "receipt": pull.receipt_ref,
                    "emitted_at": observed.isoformat(),
                },
            )
        actions.append(action)
    return {
        "schema": "sinnix.publication-sweep.v1",
        "repo": repo,
        "observed_at": observed.isoformat(),
        "actions": actions,
    }


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-publication-sweep")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--event-spool", type=Path, default=DEFAULT_SPOOL)
    parsed = parser.parse_args(arguments)
    try:
        receipt = sweep(
            parsed.repo,
            project=parsed.project,
            project_root=parsed.project_root,
            spool=parsed.event_spool,
        )
    except SweepError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
