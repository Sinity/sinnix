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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

REVIEWER_LOGIN = "chatgpt-codex-connector"
REVIEW_ABSENT_GRACE_SECONDS = 30 * 60
# One review round posts its inline findings within seconds of each other.
REVIEW_ROUND_SECONDS = 120
# Rounds are bounded by answers, not by a thumbs-up: once this many
# consecutive rounds have every finding answered in-thread, review has had
# its say (ten rounds on polylogue #4509, 2026-09-02, each costing a rebase).
REVIEW_ANSWERED_ROUNDS = 2
REVIEW_REQUEST_TEXT = "@codex review"
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
    answered_rounds: int = 0
    reviewed_head: str = ""
    review_request_pending: bool = False
    head_pushed_at: str = ""

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
        if pull.answered_rounds >= REVIEW_ANSWERED_ROUNDS:
            return "merge-answered"
        return "findings"
    if pull.review_clean:
        return "merge"
    # The grace runs from the head under review, not from the PR's birth: a
    # rebased head is new work the reviewer has not seen.
    since = max(pull.created_at, pull.head_pushed_at or "")
    created = datetime.fromisoformat(since.replace("Z", "+00:00"))
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
        head = str(row.get("headRefOid") or "")
        review = derive_review(repo, number, run, head=head)
        states.append(
            PullState(
                number=number,
                head=head,
                created_at=str(row.get("createdAt") or ""),
                mergeable=str(row.get("mergeable") or "UNKNOWN"),
                ci_red=ci_red,
                review_clean=review.clean,
                review_findings=review.open_findings,
                bead_id=bead,
                receipt_ref=receipt,
                answered_rounds=review.answered_rounds,
                reviewed_head=review.reviewed_head,
                review_request_pending=review.request_pending,
                head_pushed_at=_head_pushed_at(repo, head, run),
            )
        )
    return states


def _head_pushed_at(repo: str, head: str, run: Run) -> str:
    if not head:
        return ""
    try:
        value = _gh_json(run, ["gh", "api", f"repos/{repo}/commits/{head}", "--jq", ".commit.committer.date"])
    except SweepError:
        return ""
    return value if isinstance(value, str) else ""


@dataclass(frozen=True)
class ReviewState:
    clean: bool
    open_findings: int
    answered_rounds: int
    reviewed_head: str
    request_pending: bool


def answered_rounds(findings: Sequence[tuple[str, bool]]) -> int:
    """Consecutive rounds, newest first, in which every finding was answered.

    A finding is answered when a non-reviewer reply follows it in its thread
    (a fix commit named, or a refutation). Rounds are the reviewer's bursts
    of top-level comments within REVIEW_ROUND_SECONDS of each other.
    """
    ordered = sorted(findings, key=lambda item: item[0], reverse=True)
    rounds: list[list[bool]] = []
    round_start: datetime | None = None
    for stamp, answered in ordered:
        moment = _parse_stamp(stamp)
        if round_start is None or (round_start - moment).total_seconds() > REVIEW_ROUND_SECONDS:
            rounds.append([answered])
            round_start = moment
        else:
            rounds[-1].append(answered)
    count = 0
    for verdicts in rounds:
        if all(verdicts):
            count += 1
        else:
            break
    return count


def latest_review(
    clean_stamps: Sequence[str], finding_stamps: Sequence[str]
) -> tuple[bool, int]:
    """Judge by the reviewer's most recent verdict, not its whole history.

    Each re-review either reacts +1 (clean) or posts one round of inline
    findings. Findings older than the latest +1 were answered by the fix that
    earned it; findings from a round before the latest one were superseded
    by that re-review. Only the latest round, if newer than the latest +1,
    is open. Returns (clean, open findings).
    """
    latest_clean = max(clean_stamps, default="")
    newer = [stamp for stamp in finding_stamps if stamp > latest_clean]
    if not newer:
        return bool(latest_clean), 0
    round_start = _parse_stamp(max(newer)) - timedelta(seconds=REVIEW_ROUND_SECONDS)
    open_findings = [stamp for stamp in newer if _parse_stamp(stamp) >= round_start]
    return False, len(open_findings)


def _parse_stamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def derive_review(repo: str, number: int, run: Run, *, head: str = "") -> ReviewState:
    reactions = _gh_json(
        run,
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{number}/reactions",
            "--jq",
            f'[.[] | select((.user.login == "{REVIEWER_LOGIN}[bot]"'
            f' or .user.login == "{REVIEWER_LOGIN}") and .content == "+1")'
            " | .created_at]",
        ],
    )
    comments = _gh_json(
        run,
        [
            "gh",
            "api",
            f"repos/{repo}/pulls/{number}/comments?per_page=100",
            "--paginate",
            "--jq",
            "[.[] | {id, login: .user.login, reply_to: .in_reply_to_id, at: .created_at}]",
        ],
    )
    rows = [row for row in (comments if isinstance(comments, list) else []) if isinstance(row, Mapping)]
    reviewer_logins = {REVIEWER_LOGIN, f"{REVIEWER_LOGIN}[bot]"}
    replied_to = {
        row.get("reply_to")
        for row in rows
        if row.get("reply_to") is not None and row.get("login") not in reviewer_logins
    }
    top_level = [
        (str(row.get("at") or ""), row.get("id") in replied_to)
        for row in rows
        if row.get("login") in reviewer_logins and row.get("reply_to") is None
    ]
    clean, open_findings = latest_review(
        [stamp for stamp in reactions if isinstance(stamp, str)],
        [stamp for stamp, _answered in top_level],
    )
    latest_clean = max((stamp for stamp in reactions if isinstance(stamp, str)), default="")
    rounds = answered_rounds([item for item in top_level if item[0] > latest_clean]) if open_findings else 0
    reviews = _gh_json(
        run,
        [
            "gh",
            "api",
            f"repos/{repo}/pulls/{number}/reviews?per_page=100",
            "--jq",
            f'[.[] | select(.user.login == "{REVIEWER_LOGIN}[bot]" or .user.login == "{REVIEWER_LOGIN}")'
            " | {commit: .commit_id, at: .submitted_at}]",
        ],
    )
    review_rows = [row for row in (reviews if isinstance(reviews, list) else []) if isinstance(row, Mapping)]
    latest = max(review_rows, key=lambda row: str(row.get("at") or ""), default=None)
    reviewed_head = str(latest.get("commit") or "") if latest is not None else ""
    latest_review_at = str(latest.get("at") or "") if latest is not None else ""
    requests = _gh_json(
        run,
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{number}/comments?per_page=100",
            "--jq",
            f'[.[] | select(.body | test("{REVIEW_REQUEST_TEXT}")) | .created_at]',
        ],
    )
    latest_request = max((stamp for stamp in (requests if isinstance(requests, list) else []) if isinstance(stamp, str)), default="")
    # A head the reviewer has not seen, with no request newer than its last
    # verdict, waits for nobody: the sweep asks.
    request_pending = bool(head) and reviewed_head not in ("", head) and latest_request <= latest_review_at
    return ReviewState(clean, open_findings, rounds, reviewed_head, request_pending)


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
        if pull.review_request_pending and verdict in {"findings", "wait", "merge-answered"}:
            requested = _command(
                run,
                ["gh", "pr", "comment", str(pull.number), "--repo", repo, "--body", REVIEW_REQUEST_TEXT],
                timeout=60,
            )
            action["review_requested"] = requested.returncode == 0
        if verdict in {"merge", "merge-review-absent", "merge-answered"}:
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
                    elif verdict == "merge-answered":
                        reason += f" {REVIEW_ANSWERED_ROUNDS} review rounds answered in-thread."
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
                    "repo": repo,
                    "pr": pull.number,
                    "head": pull.head,
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
