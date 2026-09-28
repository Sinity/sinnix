"""The stacked-review-threads status pass over synthetic GraphQL responses.

Each test runs the production pass (listing, batched stack discovery, thread
reads, status diffing) against a fake runner that answers the script's aliased
queries from a branch -> merged PRs table, paginating at two nodes per page. A
pass that stopped descending past one level, walked a reused child branch
name only once, counted a PR merged into a child after the child merged,
excused a PR merged into the head before the root opened, dropped a second
page, passed a head it could not read, rewrote an unchanged status, or spent a
query per head with nothing stacked into it would fail here.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT = next(
    parent / "scripts" / "stacked-review-threads-status"
    for parent in Path(__file__).resolve().parents
    if (parent / "scripts" / "stacked-review-threads-status").is_file()
)
_loader = importlib.machinery.SourceFileLoader(
    "stacked_review_threads_status", str(SCRIPT)
)
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
status = importlib.util.module_from_spec(_spec)
sys.modules[_loader.name] = status
_loader.exec_module(status)

PAGE = 2
REPO = "owner/repo"


def _root(
    number: int, head: str, *, base: str = "master", fork: bool = False, current=None
) -> dict[str, Any]:
    context = None
    if current is not None:
        state, description, target = current
        context = {
            "state": state.upper(),
            "description": description,
            "targetUrl": target,
        }
    return {
        "number": number,
        "url": f"https://example.test/pull/{number}",
        "baseRefName": base,
        "headRefName": head,
        "headRefOid": f"{number:040x}",
        "isCrossRepository": fork,
        "commits": {
            "nodes": [
                {"commit": {"oid": f"{number:040x}", "status": {"context": context}}}
            ]
        },
    }


def _merged(
    number: int, head: str, merged: str, *resolved: bool, fork: bool = False
) -> dict[str, Any]:
    return {
        "number": number,
        "url": f"https://example.test/pull/{number}",
        "headRefName": head,
        "mergedAt": merged,
        "isCrossRepository": fork,
        "_threads": [
            {"id": f"T{number}_{index}", "isResolved": flag}
            for index, flag in enumerate(resolved)
        ],
    }


def _page(items: list, cursor: str | None) -> tuple[list, dict]:
    start = int(cursor or 0)
    end = start + PAGE
    more = end < len(items)
    return items[start:end], {
        "hasNextPage": more,
        "endCursor": str(end) if more else None,
    }


class FakeGitHub:
    def __init__(
        self,
        roots: list[dict],
        merged_into: dict[str, list[dict]],
        fail: set[str] | None = None,
    ) -> None:
        self.roots = roots
        self.merged_into = merged_into
        self.fail = fail or set()
        self.queries: list[str] = []
        self.branch_reads: list[str] = []
        self.thread_reads: list[int] = []
        self.posted: list[tuple[str, str, str, str, str]] = []

    def _pr(self, number: int) -> dict:
        return next(
            pr
            for prs in self.merged_into.values()
            for pr in prs
            if pr["number"] == number
        )

    def run(self, query: str, variables: dict[str, Any]) -> dict:
        if "states: OPEN" in query:
            self.queries.append("roots")
            nodes, info = _page(self.roots, variables.get("cursor"))
            repo = {
                "defaultBranchRef": {"name": "master"},
                "pullRequests": {"pageInfo": info, "nodes": nodes},
            }
            return {"repository": repo}
        if "states: MERGED" in query:
            self.queries.append("branches")
            if "branches" in self.fail:
                raise status.GhError("simulated outage")
            repo = {}
            for alias in re.findall(r"(b\d+): pullRequests", query):
                branch = variables[alias]
                self.branch_reads.append(branch)
                prs = [
                    {k: v for k, v in pr.items() if k != "_threads"}
                    for pr in self.merged_into.get(branch, [])
                ]
                nodes, info = _page(prs, variables.get("c" + alias[1:]))
                repo[alias] = {"pageInfo": info, "nodes": nodes}
            return {"repository": repo}
        if "reviewThreads" in query:
            self.queries.append("threads")
            if "threads" in self.fail:
                raise status.GhError("simulated outage")
            repo = {}
            for alias in re.findall(r"(p\d+): pullRequest\(", query):
                number = variables["n" + alias[1:]]
                self.thread_reads.append(number)
                nodes, info = _page(
                    self._pr(number)["_threads"], variables.get("c" + alias[1:])
                )
                repo[alias] = {"reviewThreads": {"pageInfo": info, "nodes": nodes}}
            return {"repository": repo}
        if "PullRequestReviewThread" in query:
            self.queries.append("links")
            data = {}
            for alias in re.findall(r"(t\d+): node", query):
                thread_id = variables[alias]
                data[alias] = {
                    "comments": {
                        "nodes": [{"url": f"https://example.test/{thread_id}"}]
                    }
                }
            return data
        raise AssertionError(f"unexpected query: {query}")

    def post(
        self, repository: str, sha: str, state: str, description: str, target: str
    ) -> None:
        self.posted.append((repository, sha, state, description, target))

    def sync(self) -> bool:
        return status.sync_repository(REPO, run=self.run, post=self.post)

    def verdicts(self) -> dict[int, tuple[str, str, str]]:
        self.sync()
        return {
            int(sha, 16): (state, description, target)
            for _, sha, state, description, target in self.posted
        }


def test_unresolved_threads_two_levels_down_fail_the_root() -> None:
    fake = FakeGitHub(
        roots=[_root(10, "feat")],
        merged_into={
            "feat": [_merged(11, "feat2", "2026-01-05T00:00:00Z", True)],
            "feat2": [_merged(12, "feat3", "2026-01-04T00:00:00Z", True, False, False)],
        },
    )
    assert fake.verdicts()[10] == (
        "failure",
        "unresolved review threads in stacked #12",
        "https://example.test/T12_1",
    )


def test_all_threads_resolved_passes() -> None:
    fake = FakeGitHub(
        roots=[_root(10, "feat")],
        merged_into={
            "feat": [_merged(11, "feat2", "2026-01-03T00:00:00Z", True, True)]
        },
    )
    assert fake.verdicts()[10][0] == "success"


def test_pr_merged_into_the_head_before_the_root_opened_still_counts() -> None:
    fake = FakeGitHub(
        roots=[_root(20, "feat")],
        merged_into={"feat": [_merged(5, "old", "2025-01-02T00:00:00Z", False)]},
    )
    assert fake.verdicts()[20][:2] == (
        "failure",
        "unresolved review threads in stacked #5",
    )


def test_pr_merged_into_a_child_after_the_child_merged_does_not_reach_the_root() -> (
    None
):
    fake = FakeGitHub(
        roots=[_root(30, "feat")],
        merged_into={
            "feat": [_merged(31, "feat2", "2026-01-04T00:00:00Z")],
            "feat2": [_merged(32, "feat3", "2026-01-06T00:00:00Z", False)],
        },
    )
    assert fake.verdicts()[30][0] == "success"
    assert 32 not in fake.thread_reads


def test_each_lifetime_of_a_reused_child_branch_is_walked_with_its_own_bound() -> None:
    fake = FakeGitHub(
        roots=[_root(80, "feat")],
        merged_into={
            "feat": [
                _merged(81, "child", "2026-01-04T00:00:00Z"),
                _merged(82, "child", "2026-01-07T00:00:00Z"),
            ],
            "child": [
                _merged(83, "g1", "2026-01-03T00:00:00Z", False),
                _merged(84, "g2", "2026-01-06T00:00:00Z", False),
            ],
        },
    )
    # 84 merged after 81 but before 82, so only the second lifetime admits it.
    assert fake.verdicts()[80][1] == "unresolved review threads in stacked #83, #84"


def test_a_fork_child_is_checked_but_its_head_name_is_not_walked_here() -> None:
    fake = FakeGitHub(
        roots=[_root(110, "feat")],
        merged_into={
            "feat": [
                _merged(111, "shared-name", "2026-01-05T00:00:00Z", False, fork=True)
            ],
            "shared-name": [_merged(112, "unrelated", "2026-01-04T00:00:00Z", False)],
        },
    )
    assert fake.verdicts()[110][1] == "unresolved review threads in stacked #111"
    assert "shared-name" not in fake.branch_reads


def test_a_fork_root_passes_without_walking_its_head_name() -> None:
    fake = FakeGitHub(
        roots=[_root(115, "feat", fork=True)],
        merged_into={"feat": [_merged(116, "x", "2026-01-05T00:00:00Z", False)]},
    )
    assert fake.verdicts()[115][0] == "success"
    assert fake.branch_reads == []


def test_threads_and_merged_prs_past_the_first_page_are_counted() -> None:
    fake = FakeGitHub(
        roots=[_root(40, "feat")],
        merged_into={
            "feat": [
                _merged(41, "a", "2026-01-03T00:00:00Z", True, True, False),
                _merged(42, "b", "2026-01-03T00:00:00Z", True),
                _merged(43, "c", "2026-01-03T00:00:00Z", False),
            ],
        },
    )
    assert fake.verdicts()[40][:2] == (
        "failure",
        "unresolved review threads in stacked #41, #43",
    )


def test_roots_past_the_first_page_are_evaluated_and_other_bases_ignored() -> None:
    fake = FakeGitHub(
        roots=[_root(1, "a"), _root(2, "b", base="a"), _root(3, "c")],
        merged_into={"c": [_merged(4, "d", "2026-01-03T00:00:00Z", False)]},
    )
    verdicts = fake.verdicts()
    assert set(verdicts) == {1, 3}
    assert verdicts[3][0] == "failure"


def test_branch_cycle_terminates() -> None:
    fake = FakeGitHub(
        roots=[_root(50, "a")],
        merged_into={
            "a": [_merged(51, "b", "2026-01-03T00:00:00Z")],
            "b": [_merged(52, "a", "2026-01-02T12:00:00Z", False)],
        },
    )
    assert fake.verdicts()[50][1] == "unresolved review threads in stacked #52"


def test_heads_with_nothing_stacked_share_one_branch_read_and_skip_thread_reads() -> (
    None
):
    fake = FakeGitHub(
        roots=[_root(number, f"h{number}") for number in range(1, 8)], merged_into={}
    )
    verdicts = fake.verdicts()
    assert {state for state, _, _ in verdicts.values()} == {"success"}
    assert fake.queries.count("branches") == 1
    assert "threads" not in fake.queries


@pytest.mark.parametrize("outage", ["branches", "threads"])
def test_a_read_failure_sets_pending_and_never_success(outage: str) -> None:
    previous = (
        "success",
        "no PR is stacked into this head",
        "https://example.test/pull/60",
    )
    fake = FakeGitHub(
        roots=[_root(60, "feat", current=previous)],
        merged_into={"feat": [_merged(61, "feat2", "2026-01-03T00:00:00Z", True)]},
        fail={outage},
    )
    assert fake.verdicts()[60][0] == "pending"


def test_a_failed_listing_writes_nothing() -> None:
    def broken(query: str, variables: dict) -> dict:
        raise status.GhError("simulated outage")

    with pytest.raises(status.GhError):
        status.sync_repository(
            REPO, run=broken, post=lambda *args: pytest.fail("posted")
        )


def test_an_unchanged_status_is_not_rewritten() -> None:
    fake = FakeGitHub(
        roots=[_root(70, "feat")],
        merged_into={"feat": [_merged(71, "x", "2026-01-03T00:00:00Z", False)]},
    )
    first = fake.verdicts()[70]
    settled = FakeGitHub(
        roots=[_root(70, "feat", current=first)], merged_into=fake.merged_into
    )
    settled.sync()
    assert settled.posted == []
