"""PR publication waits for its pushed candidate without accepting another head."""

from pathlib import Path
from typing import Any

import pytest
from agentctl import github, landing as landing_module, manifest
from agentctl.batch import BatchRefusal
from test_batch import MOVED, OTHER, SHA, Harness, harness as harness_fixture
from test_batch import prepared_run, pr_project


def _pull(number: int, head: str, *, merged: bool = False) -> dict[str, Any]:
    return {
        "number": number,
        "state": "MERGED" if merged else "OPEN",
        "headRefOid": head,
        "statusCheckRollup": [],
        "mergeCommit": {"oid": "9" * 40} if merged else None,
    }


@pytest.fixture
def harness(harness_fixture: Harness) -> Harness:
    return harness_fixture


def test_publication_waits_for_exact_candidate_after_push(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr_project(harness)
    run = prepared_run(harness, "fx-solo")
    reads: list[str] = []
    calls: list[tuple[str, str]] = []
    merged = False
    api_heads = iter([SHA, SHA, SHA, SHA])

    monkeypatch.setattr(github, "remote_head", lambda root, name: MOVED)
    monkeypatch.setattr(
        github,
        "push_branch",
        lambda root, name, *, sha, lease, timeout=0: calls.append(("push", lease)),
    )
    monkeypatch.setattr(
        github,
        "pull_request_for_branch",
        lambda root, name: _pull(7, MOVED),
    )

    def pull(root: Path, number: int) -> dict[str, Any]:
        nonlocal merged
        head = next(api_heads)
        reads.append(head)
        return _pull(number, head, merged=merged)

    monkeypatch.setattr(github, "pull_request", pull)
    monkeypatch.setattr(github, "hosted_check_state", lambda pull, name: "success")
    monkeypatch.setattr(github, "check_rollup", lambda pull, required=(): "ready")

    def merge(root: Path, number: int, candidate: str) -> None:
        nonlocal merged
        assert candidate == SHA and SHA in reads
        calls.append(("merge", candidate))
        merged = True

    monkeypatch.setattr(github, "merge_pr", merge)
    monkeypatch.setattr(github, "delete_remote_branch", lambda root, name: None)

    result = landing_module._publish(
        harness.config,
        harness.project,
        manifest.load(harness.config, run["run_id"]),
        Path(run["workers"][0]["worktree"]),
        "b" * 40,
        SHA,
        lambda seconds: None,
        harness.beads,
    )

    assert calls[0] == ("push", MOVED)
    assert reads[:2] == [SHA, SHA]
    assert calls[-1] == ("merge", SHA)
    assert result and result["candidate_sha"] == SHA


def test_publication_refuses_third_head_during_propagation(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr_project(harness)
    run = prepared_run(harness, "fx-solo")
    pushes: list[str | None] = []
    merges: list[str] = []
    monkeypatch.setattr(github, "remote_head", lambda root, name: MOVED)
    monkeypatch.setattr(
        github,
        "push_branch",
        lambda root, name, *, sha, lease, timeout=0: pushes.append(lease),
    )
    monkeypatch.setattr(github, "pull_request_for_branch", lambda root, name: _pull(7, MOVED))
    monkeypatch.setattr(github, "pull_request", lambda root, number: _pull(number, OTHER))
    monkeypatch.setattr(
        github, "merge_pr", lambda root, number, candidate: merges.append(candidate)
    )

    with pytest.raises(BatchRefusal, match="head_moved"):
        landing_module._publish(
            harness.config,
            harness.project,
            manifest.load(harness.config, run["run_id"]),
            Path(run["workers"][0]["worktree"]),
            "b" * 40,
            SHA,
            lambda seconds: None,
            harness.beads,
        )

    assert pushes == [MOVED]
    assert merges == []


def test_publication_refuses_unobserved_candidate_at_deadline(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr_project(harness)
    run = prepared_run(harness, "fx-solo")
    clock = [0.0]
    sleeps: list[float] = []
    merges: list[str] = []
    monkeypatch.setattr(landing_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(github, "remote_head", lambda root, name: MOVED)
    monkeypatch.setattr(github, "push_branch", lambda *args, **kwargs: None)
    monkeypatch.setattr(github, "pull_request_for_branch", lambda root, name: _pull(7, MOVED))
    monkeypatch.setattr(github, "pull_request", lambda root, number: _pull(number, MOVED))
    monkeypatch.setattr(
        github, "merge_pr", lambda root, number, candidate: merges.append(candidate)
    )

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    with pytest.raises(BatchRefusal, match="checks_failed") as refused:
        landing_module._publish(
            harness.config,
            harness.project,
            manifest.load(harness.config, run["run_id"]),
            Path(run["workers"][0]["worktree"]),
            "b" * 40,
            SHA,
            sleep,
            harness.beads,
        )

    assert refused.value.to_dict()["timed_out"] is True
    assert sum(sleeps) == landing_module.PR_PROPAGATION_TIMEOUT_SECONDS
    assert merges == []


def test_publication_refuses_head_move_after_candidate_observed(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr_project(harness)
    run = prepared_run(harness, "fx-solo")
    reads = iter([SHA, OTHER])
    checks: list[str] = []
    merges: list[str] = []
    monkeypatch.setattr(github, "remote_head", lambda root, name: MOVED)
    monkeypatch.setattr(github, "push_branch", lambda *args, **kwargs: None)
    monkeypatch.setattr(github, "pull_request_for_branch", lambda root, name: _pull(7, MOVED))
    monkeypatch.setattr(
        github, "pull_request", lambda root, number: _pull(number, next(reads))
    )
    monkeypatch.setattr(
        github,
        "check_rollup",
        lambda pull, required=(): checks.append("check") or "ready",
    )
    monkeypatch.setattr(
        github, "merge_pr", lambda root, number, candidate: merges.append(candidate)
    )

    with pytest.raises(BatchRefusal, match="head_moved"):
        landing_module._publish(
            harness.config,
            harness.project,
            manifest.load(harness.config, run["run_id"]),
            Path(run["workers"][0]["worktree"]),
            "b" * 40,
            SHA,
            lambda seconds: None,
            harness.beads,
        )

    assert checks == [] and merges == []


def test_publication_does_not_retry_unrelated_github_errors(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr_project(harness)
    run = prepared_run(harness, "fx-solo")
    calls: list[str] = []

    def remote_head(root: Path, branch: str) -> str:
        calls.append("remote_head")
        raise github.GithubError("GitHub API unavailable")

    monkeypatch.setattr(github, "remote_head", remote_head)
    monkeypatch.setattr(
        github,
        "push_branch",
        lambda *args, **kwargs: calls.append("push"),
    )

    with pytest.raises(github.GithubError, match="API unavailable"):
        landing_module._publish(
            harness.config,
            harness.project,
            manifest.load(harness.config, run["run_id"]),
            Path(run["workers"][0]["worktree"]),
            "b" * 40,
            SHA,
            lambda seconds: None,
            harness.beads,
        )

    assert calls == ["remote_head"]


def test_publication_maps_a_lease_race_to_head_moved(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr_project(harness)
    run = prepared_run(harness, "fx-solo")
    pushes: list[str] = []
    monkeypatch.setattr(github, "remote_head", lambda root, branch: MOVED)

    def push(root: Path, branch: str, *, sha: str, lease: str | None, timeout=0) -> None:
        pushes.append(lease or "")
        raise github.GithubError("git push: stale info")

    monkeypatch.setattr(github, "push_branch", push)

    with pytest.raises(BatchRefusal, match="head_moved"):
        landing_module._publish(
            harness.config,
            harness.project,
            manifest.load(harness.config, run["run_id"]),
            Path(run["workers"][0]["worktree"]),
            "b" * 40,
            SHA,
            lambda seconds: None,
            harness.beads,
        )
    assert pushes == [MOVED]
