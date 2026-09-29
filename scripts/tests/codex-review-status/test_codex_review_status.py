"""The codex-review status pass and its stall re-trigger over a fake `gh`.

Each test runs the production pass (paged PR listing, complete comment reads,
status diffing, the re-trigger comment) against a fake `gh` that serves PRs and
comments two per page and records every write. A pass that re-requested a
review before STALL_SECONDS, re-requested on a draft, a waived PR or a head
Codex already reviewed, lost the per-head marker (including one on a later
comments page), refused a new head its own request, posted in a dry run, or
posted after a failed comment read would fail here.
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


def _summary(sha: str, state: str) -> dict:
    body = (
        "<!-- codex-pull-request-review-summary -->\n"
        "| Check | State | Commit |\n|---|---|---|\n"
        f"| **Code Review** | **{state}** | `{sha[:9]}` |\n"
    )
    return {
        "url": "https://example.test/summary",
        "body": body,
        "author": {"login": "chatgpt-codex-connector"},
    }


def _note(text: str) -> dict:
    return {
        "url": "https://example.test/c",
        "body": text,
        "author": {"login": "someone"},
    }


class FakeGitHub:
    def __init__(self, prs: list[dict], *, fail_comment_pages: bool = False) -> None:
        self.prs = {pr["number"]: pr for pr in prs}
        self.fail_comment_pages = fail_comment_pages
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
                if self.fail_comment_pages:
                    raise status.GhError("simulated outage")
                pr = self.prs[int(fields["number"])]
                page = self._comments(pr, fields.get("cursor"))
                return json.dumps(
                    {"data": {"repository": {"pullRequest": {"comments": page}}}}
                )
            raise AssertionError(f"unexpected query: {query}")
        path = args[3]
        if path.endswith("/comments"):
            number = int(path.split("/")[-2])
            body = fields["body"]
            self.requests.append((number, body))
            self.prs[number]["_comments"].append(_note(body))
            return "{}"
        if "/statuses/" in path:
            sha = path.rsplit("/", 1)[1]
            self.statuses.append((sha, fields["description"]))
            for pr in self.prs.values():
                if pr["headRefOid"] == sha:
                    pr["_context"] = {
                        "state": fields["state"].upper(),
                        "description": fields["description"],
                        "createdAt": _iso(NOW),
                    }
            return "{}"
        raise AssertionError(f"unexpected gh call: {args}")

    def sync(self, *, now: datetime = NOW, dry_run: bool = False) -> int:
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
