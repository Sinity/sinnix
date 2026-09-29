"""The codex-review status pass and its stall re-trigger over a fake `gh`.

Each test runs the production pass (paged PR listing, complete comment reads,
status diffing, the re-trigger comment) against a fake `gh` that serves PRs and
comments two per page and records every write. A pass that re-requested a
review before STALL_SECONDS, re-requested on a draft, a waived PR or a head
Codex already reviewed, lost the per-head marker (including one on a later
comments page), refused a new head its own request, posted in a dry run, or
posted after a failed comment read would fail here. So would one that
re-requested while a code-review usage-limit notice on any open PR was younger
than QUOTA_RETRY_SECONDS, probed with more than one request, sent further
requests while the probe awaited its answer, or never resumed after it; that
requested anything or left a head pending while `codex-review` was not a
required context of the default branch; or that wrote anything after failing
to read the branch protection.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = next(
    parent / "scripts" / "codex-review-status"
    for parent in Path(__file__).resolve().parents
    if (parent / "scripts" / "codex-review-status").is_file()
)
_loader = importlib.machinery.SourceFileLoader("codex_review_status", str(SCRIPT))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
status = importlib.util.module_from_spec(_spec)
sys.modules[_loader.name] = status
_loader.exec_module(status)

PAGE = 2
REPO = "owner/repo"
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
HEAD_A = "a" * 40
HEAD_B = "b" * 40


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


QUOTA_BODY = (
    "You have reached your Codex usage limits for code reviews. You can see your "
    "limits in the [Codex usage dashboard](https://chatgpt.com/codex/cloud/settings/usage)."
)


def _quota(at: datetime, body: str = QUOTA_BODY) -> dict:
    return {
        "url": "https://example.test/quota",
        "body": body,
        "createdAt": _iso(at),
        "author": {"login": "chatgpt-codex-connector"},
    }


def _marker(sha: str) -> str:
    return f"@codex review\n\n<!-- codex-review-retrigger: {sha} -->"


def _summary(sha: str, state: str) -> dict:
    body = (
        "<!-- codex-pull-request-review-summary -->\n"
        "| Check | State | Commit |\n|---|---|---|\n"
        f"| **Code Review** | **{state}** | `{sha[:9]}` |\n"
    )
    return {
        "url": "https://example.test/summary",
        "body": body,
        "createdAt": _iso(NOW - timedelta(days=1)),
        "author": {"login": "chatgpt-codex-connector"},
    }


def _note(text: str, at: datetime = NOW - timedelta(days=1)) -> dict:
    return {
        "url": "https://example.test/c",
        "body": text,
        "createdAt": _iso(at),
        "author": {"login": "someone"},
    }


class FakeGitHub:
    def __init__(self, prs: list[dict], *, fail_comment_pages: bool = False) -> None:
        self.prs = {pr["number"]: pr for pr in prs}
        self.fail_comment_pages = fail_comment_pages
        self.fail_comments_of: set[int] = set()
        self.required = ["ci/quick-gate", "codex-review"]
        self.protection_error = False
        self.now = NOW
        self.requests: list[tuple[int, str]] = []
        self.statuses: list[tuple[str, str]] = []

    def pr(
        self,
        number: int,
        *,
        head: str = HEAD_A,
        draft: bool = False,
        labels: tuple[str, ...] = (),
        comments: list[dict] | None = None,
        current: str | None = status.WAITING,
        age: timedelta = timedelta(minutes=30),
    ) -> None:
        context = None
        if current is not None:
            context = {
                "state": "PENDING",
                "description": current,
                "createdAt": _iso(NOW - age),
            }
        self.prs[number] = {
            "number": number,
            "url": f"https://example.test/pull/{number}",
            "isDraft": draft,
            "headRefOid": head,
            "labels": {"nodes": [{"name": label} for label in labels]},
            "_comments": list(comments or []),
            "_context": context,
        }

    def _comments(self, pr: dict, cursor: str | None) -> dict:
        start = int(cursor or 0)
        nodes = pr["_comments"][start : start + PAGE]
        more = start + PAGE < len(pr["_comments"])
        return {
            "pageInfo": {
                "hasNextPage": more,
                "endCursor": str(start + PAGE) if more else None,
            },
            "nodes": nodes,
        }

    def gh(self, *args: str) -> str:
        fields = {}
        for flag, value in zip(args, args[1:], strict=False):
            if flag in {"-f", "-F"}:
                key, _, val = value.partition("=")
                fields[key] = val
        if args[:2] == ("api", "graphql"):
            query = fields["query"]
            if "pullRequests(states: OPEN" in query:
                numbers = sorted(self.prs)
                start = int(fields.get("cursor") or 0)
                more = start + PAGE < len(numbers)
                nodes = []
                for number in numbers[start : start + PAGE]:
                    pr = self.prs[number]
                    nodes.append(
                        {
                            **{k: v for k, v in pr.items() if not k.startswith("_")},
                            "comments": self._comments(pr, None),
                            "commits": {
                                "nodes": [
                                    {"commit": {"status": {"context": pr["_context"]}}}
                                ]
                            },
                        }
                    )
                info = {
                    "hasNextPage": more,
                    "endCursor": str(start + PAGE) if more else None,
                }
                return json.dumps(
                    {
                        "data": {
                            "repository": {
                                "pullRequests": {"pageInfo": info, "nodes": nodes}
                            }
                        }
                    }
                )
            if "pullRequest(number:" in query:
                if self.fail_comment_pages or int(fields["number"]) in self.fail_comments_of:
                    raise status.GhError("simulated outage")
                pr = self.prs[int(fields["number"])]
                page = self._comments(pr, fields.get("cursor"))
                return json.dumps(
                    {"data": {"repository": {"pullRequest": {"comments": page}}}}
                )
            raise AssertionError(f"unexpected query: {query}")
        if args[:2] == ("api", f"repos/{REPO}"):
            return json.dumps({"default_branch": "master"})
        if args[:2] == (
            "api",
            f"repos/{REPO}/branches/master/protection/required_status_checks",
        ):
            if self.protection_error:
                raise status.GhError("gh api failed: Not Found (HTTP 404)")
            return json.dumps(
                {
                    "contexts": self.required,
                    "checks": [{"context": c, "app_id": None} for c in self.required],
                }
            )
        path = args[3]
        if path.endswith("/comments"):
            number = int(path.split("/")[-2])
            body = fields["body"]
            self.requests.append((number, body))
            self.prs[number]["_comments"].append(_note(body, self.now))
            return "{}"
        if "/statuses/" in path:
            sha = path.rsplit("/", 1)[1]
            self.statuses.append((sha, fields["description"]))
            for pr in self.prs.values():
                if pr["headRefOid"] == sha:
                    pr["_context"] = {
                        "state": fields["state"].upper(),
                        "description": fields["description"],
                        "createdAt": _iso(self.now),
                    }
            return "{}"
        raise AssertionError(f"unexpected gh call: {args}")

    def sync(self, *, now: datetime = NOW, dry_run: bool = False) -> int:
        self.now = now
        return status.sync_repository(REPO, dry_run=dry_run, now=now)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    github = FakeGitHub([])
    monkeypatch.setattr(status, "gh", github.gh)
    return github


def test_stalled_head_gets_exactly_one_request(fake: FakeGitHub) -> None:
    fake.pr(1)
    fake.sync()
    assert fake.requests == [
        (1, f"@codex review\n\n<!-- codex-review-retrigger: {HEAD_A} -->")
    ]
    assert fake.statuses == [(HEAD_A, status.REREQUESTED)]
    # Later passes, however late, find the marker on GitHub and stay quiet.
    fake.sync(now=NOW + timedelta(hours=10))
    assert len(fake.requests) == 1


def test_head_younger_than_the_threshold_is_not_rerequested(fake: FakeGitHub) -> None:
    fake.pr(1, age=timedelta(minutes=19))
    fake.sync()
    assert fake.requests == []


def test_first_sighting_starts_the_clock_instead_of_requesting(
    fake: FakeGitHub,
) -> None:
    fake.pr(1, current=None)
    fake.sync()
    assert fake.requests == []
    assert fake.statuses == [(HEAD_A, status.WAITING)]
    fake.sync(now=NOW + timedelta(minutes=21))
    assert [number for number, _ in fake.requests] == [1]


@pytest.mark.parametrize(
    "setup",
    [
        {"draft": True, "current": "draft: Codex reviews once marked ready"},
        {"labels": ("codex-review-waived",)},
        {"comments": [_summary(HEAD_A, "Completed")]},
        {"comments": [_summary(HEAD_A, "Running")]},
    ],
    ids=["draft", "waived", "reviewed", "reviewing"],
)
def test_heads_that_are_not_waiting_are_never_rerequested(
    fake: FakeGitHub, setup: dict
) -> None:
    fake.pr(1, **setup)
    fake.sync()
    assert fake.requests == []


def test_marker_on_a_later_comments_page_prevents_a_second_request(
    fake: FakeGitHub,
) -> None:
    marker = f"@codex review\n\n<!-- codex-review-retrigger: {HEAD_A} -->"
    fake.pr(1, comments=[_note("one"), _note("two"), _note("three"), _note(marker)])
    fake.sync()
    assert fake.requests == []
    assert fake.statuses == [(HEAD_A, status.REREQUESTED)]


def test_summary_on_a_later_comments_page_is_read(fake: FakeGitHub) -> None:
    fake.pr(1, comments=[_note("one"), _note("two"), _summary(HEAD_A, "Completed")])
    fake.sync()
    assert fake.statuses == [(HEAD_A, f"Codex review completed on {HEAD_A[:9]}")]


def test_a_new_head_gets_its_own_request(fake: FakeGitHub) -> None:
    fake.pr(1)
    fake.sync()
    old = fake.prs[1]
    fake.pr(1, head=HEAD_B, comments=old["_comments"])
    fake.sync()
    assert [body.rsplit(" ", 2)[-2] for _, body in fake.requests] == [HEAD_A, HEAD_B]


def test_every_open_pr_page_is_read(fake: FakeGitHub) -> None:
    for number in range(1, 6):
        fake.pr(number)
    fake.sync()
    assert sorted(number for number, _ in fake.requests) == [1, 2, 3, 4, 5]


def test_dry_run_posts_nothing(
    fake: FakeGitHub, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.pr(1)
    fake.sync(dry_run=True)
    assert fake.requests == [] and fake.statuses == []
    assert (
        f"would request Codex review on {REPO}#1 {HEAD_A[:9]}"
        in capsys.readouterr().out
    )


def test_failed_comment_read_posts_nothing(fake: FakeGitHub) -> None:
    fake.fail_comment_pages = True
    fake.pr(1, comments=[_note("one"), _note("two"), _note("three")])
    fake.sync()
    assert fake.requests == [] and fake.statuses == []


def test_quota_notice_after_the_request_holds_the_head_back(fake: FakeGitHub) -> None:
    requested = NOW - timedelta(minutes=30)
    notice = requested + timedelta(seconds=8)
    fake.pr(
        1,
        comments=[_note(_marker(HEAD_A), requested), _quota(notice)],
        current=status.REREQUESTED,
        age=timedelta(minutes=30),
    )
    fake.sync()
    limited = status.LIMITED.format(since=_iso(notice))
    assert fake.requests == []
    assert fake.statuses == [(HEAD_A, limited)]
    # A new head during the wait draws no request either.
    fake.pr(1, head=HEAD_B, comments=fake.prs[1]["_comments"], current=None)
    fake.sync(now=NOW + timedelta(hours=1))
    fake.sync(now=NOW + timedelta(hours=2))
    assert fake.requests == []
    assert fake.statuses[-1] == (HEAD_B, limited)


def test_quota_notice_on_one_pr_holds_every_pr(fake: FakeGitHub) -> None:
    notice = NOW - timedelta(minutes=5)
    fake.pr(1, comments=[_quota(notice)], current=status.REREQUESTED)
    fake.pr(2, head=HEAD_B)
    fake.sync()
    assert fake.requests == []
    limited = status.LIMITED.format(since=_iso(notice))
    assert sorted(fake.statuses) == [(HEAD_A, limited), (HEAD_B, limited)]


def test_security_review_notice_does_not_hold_requests(fake: FakeGitHub) -> None:
    security = QUOTA_BODY.replace("code reviews", "security reviews")
    fake.pr(1, comments=[_quota(NOW - timedelta(minutes=5), security)])
    fake.sync()
    assert [number for number, _ in fake.requests] == [1]


def test_requests_resume_through_a_single_probe(fake: FakeGitHub) -> None:
    notice = NOW - timedelta(seconds=status.QUOTA_RETRY_SECONDS + 60)
    limited = status.LIMITED.format(since=_iso(notice))
    fake.pr(
        1,
        comments=[_note(_marker(HEAD_A), notice - timedelta(seconds=8)), _quota(notice)],
        current=limited,
        age=timedelta(hours=3),
    )
    fake.pr(2, head=HEAD_B, current=limited, age=timedelta(hours=3))
    fake.pr(3, head="c" * 40, current=limited, age=timedelta(hours=3))
    fake.sync()
    # One probe for the repository, not one per PR.
    assert [number for number, _ in fake.requests] == [1]
    # While the probe awaits Codex's answer, the other PRs keep waiting.
    fake.sync(now=NOW + timedelta(minutes=5))
    assert len(fake.requests) == 1
    # Unanswered past the grace period, the probe was accepted: every stalled
    # head gets its request once, and the probed head gets no second one.
    later = NOW + timedelta(seconds=status.PROBE_GRACE_SECONDS + 60)
    fake.sync(now=later)
    fake.sync(now=later + timedelta(minutes=5))
    assert sorted(number for number, _ in fake.requests) == [1, 2, 3]


def test_a_probe_answered_by_another_notice_restarts_the_wait(
    fake: FakeGitHub,
) -> None:
    notice = NOW - timedelta(seconds=status.QUOTA_RETRY_SECONDS + 60)
    limited = status.LIMITED.format(since=_iso(notice))
    fake.pr(1, comments=[_quota(notice)], current=limited, age=timedelta(hours=3))
    fake.pr(2, head=HEAD_B, current=limited, age=timedelta(hours=3))
    fake.sync()
    assert [number for number, _ in fake.requests] == [1]
    answer = NOW + timedelta(seconds=10)
    fake.prs[1]["_comments"].append(_quota(answer))
    fake.sync(now=NOW + timedelta(minutes=15))
    fake.sync(now=answer + timedelta(seconds=status.QUOTA_RETRY_SECONDS - 60))
    assert len(fake.requests) == 1
    assert fake.statuses[-1][1] == status.LIMITED.format(since=_iso(answer))
    fake.sync(now=answer + timedelta(seconds=status.QUOTA_RETRY_SECONDS + 60))
    assert len(fake.requests) == 2


def test_an_unread_pr_holds_requests_on_every_pr(fake: FakeGitHub) -> None:
    # PR 1's second comments page (which may hold a quota notice) fails.
    fake.pr(1, comments=[_note("one"), _note("two"), _note("three")])
    fake.pr(2, head=HEAD_B)
    fake.fail_comments_of = {1}
    fake.sync()
    assert fake.requests == []
    assert fake.statuses == []


def test_gate_off_requests_nothing_and_passes_every_head(fake: FakeGitHub) -> None:
    fake.required = ["ci/quick-gate"]
    notice = NOW - timedelta(seconds=status.QUOTA_RETRY_SECONDS + 60)
    limited = status.LIMITED.format(since=_iso(notice))
    # A probe would be due here, and PR 2 has stalled past the threshold.
    fake.pr(1, comments=[_quota(notice)], current=limited, age=timedelta(hours=3))
    fake.pr(2, head=HEAD_B)
    fake.pr(3, head="c" * 40, labels=("codex-review-waived",))
    fake.sync()
    assert fake.requests == []
    assert sorted(fake.statuses) == [
        (HEAD_A, status.GATE_OFF),
        (HEAD_B, status.GATE_OFF),
        ("c" * 40, "waived by the codex-review-waived label"),
    ]
    assert {pr["_context"]["state"] for pr in fake.prs.values()} == {"SUCCESS"}


def test_restoring_the_gate_restores_waiting_and_requests(fake: FakeGitHub) -> None:
    fake.required = []
    fake.pr(1)
    fake.sync()
    assert fake.statuses == [(HEAD_A, status.GATE_OFF)]
    fake.required = ["codex-review"]
    later = NOW + timedelta(hours=1)
    fake.sync(now=later)
    assert fake.statuses[-1] == (HEAD_A, status.WAITING)
    assert fake.requests == []
    fake.sync(now=later + timedelta(seconds=status.STALL_SECONDS + 60))
    assert [number for number, _ in fake.requests] == [1]


def test_unreadable_protection_writes_nothing(fake: FakeGitHub) -> None:
    fake.protection_error = True
    fake.pr(1, current=None)
    fake.pr(2, head=HEAD_B)
    with pytest.raises(status.GhError):
        fake.sync()
    assert fake.requests == [] and fake.statuses == []
