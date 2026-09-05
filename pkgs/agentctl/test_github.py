"""The gh adapter: checks never read as ready by omission, merges name their head."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from agentctl import github
from agentctl.github import GithubError


def check(
    name: str, conclusion: str | None = None, status: str = "COMPLETED"
) -> dict[str, Any]:
    entry: dict[str, Any] = {"__typename": "CheckRun", "name": name, "status": status}
    if conclusion is not None:
        entry["conclusion"] = conclusion
    return entry


def test_missing_or_skipped_required_checks_are_pending_never_ready() -> None:
    """Breaks if a merge could proceed on a check GitHub never ran."""
    pull = {"statusCheckRollup": [check("lint", "SUCCESS")]}
    assert github.check_rollup(pull, ("lint", "verify")) == "pending"
    skipped = {
        "statusCheckRollup": [check("lint", "SUCCESS"), check("verify", "SKIPPED")]
    }
    assert github.check_rollup(skipped, ("lint", "verify")) == "pending"
    assert github.check_rollup({"statusCheckRollup": []}, ("verify",)) == "pending"
    assert github.check_rollup({}, ("verify",)) == "pending"
    green = {
        "statusCheckRollup": [check("lint", "SUCCESS"), check("verify", "SUCCESS")]
    }
    assert github.check_rollup(green, ("lint", "verify")) == "ready"
    running = {
        "statusCheckRollup": [
            check("lint", "SUCCESS"),
            check("verify", status="IN_PROGRESS"),
        ]
    }
    assert github.check_rollup(running, ("lint", "verify")) == "pending"
    failed = {
        "statusCheckRollup": [check("lint", "FAILURE"), check("verify", "SUCCESS")]
    }
    assert github.check_rollup(failed, ("verify",)) == "failed"


def test_without_a_required_list_every_present_check_must_pass() -> None:
    assert github.check_rollup({"statusCheckRollup": []}) == "ready"
    assert (
        github.check_rollup({"statusCheckRollup": [check("x", "SUCCESS")]}) == "ready"
    )
    assert (
        github.check_rollup({"statusCheckRollup": [check("x", status="QUEUED")]})
        == "pending"
    )
    assert (
        github.check_rollup({"statusCheckRollup": [check("x", "SKIPPED")]}) == "pending"
    )


def test_hosted_check_state_names_one_check() -> None:
    pull = {
        "statusCheckRollup": [
            check("verify", "SUCCESS"),
            check("lint", "FAILURE"),
            check("slow", status="IN_PROGRESS"),
        ]
    }
    assert github.hosted_check_state(pull, "verify") == "success"
    assert github.hosted_check_state(pull, "lint") == "failure"
    assert github.hosted_check_state(pull, "slow") == "pending"
    assert github.hosted_check_state(pull, "absent") == "missing"
    assert github.hosted_check_state({}, "verify") == "missing"


@pytest.fixture
def recorded_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A `gh` on PATH that records argv and replays a scripted stdout/exit."""
    ledger = tmp_path / "calls"
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"stdout": "", "exit": 0}))
    binary = tmp_path / "bin" / "gh"
    binary.parent.mkdir()
    binary.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> {ledger}\n'
        f"python3 -c \"import json,sys; d=json.load(open('{script}')); sys.stdout.write(d['stdout']); sys.stderr.write(d.get('stderr','')); sys.exit(d['exit'])\"\n"
    )
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ['PATH']}")
    return {"ledger": ledger, "script": script}


def _calls(ledger: Path) -> list[str]:
    return ledger.read_text().splitlines() if ledger.exists() else []


def test_pull_request_is_read_by_number_and_absent_when_unknown(
    recorded_gh: dict[str, Any], tmp_path: Path
) -> None:
    recorded_gh["script"].write_text(
        json.dumps({"stdout": '{"number": 7, "state": "OPEN"}', "exit": 0})
    )
    assert github.pull_request(tmp_path, 7) == {"number": 7, "state": "OPEN"}
    assert _calls(recorded_gh["ledger"])[0].startswith("pr view 7 --json number,")

    recorded_gh["script"].write_text(
        json.dumps(
            {
                "stdout": "",
                "stderr": "GraphQL: Could not resolve to a PullRequest with the number of 99.",
                "exit": 1,
            }
        )
    )
    assert github.pull_request(tmp_path, 99) is None

    recorded_gh["script"].write_text(
        json.dumps({"stdout": "", "stderr": "HTTP 502", "exit": 1})
    )
    with pytest.raises(GithubError, match="502"):
        github.pull_request(tmp_path, 7)


def test_merge_names_the_verified_head_and_refuses_a_moved_one(
    recorded_gh: dict[str, Any], tmp_path: Path
) -> None:
    """Breaks if a squash could land a head other than the reviewed candidate."""
    sha = "b" * 40
    github.merge_pr(tmp_path, 12, sha)
    assert (
        _calls(recorded_gh["ledger"])[-1]
        == f"pr merge 12 --squash --match-head-commit {sha}"
    )

    recorded_gh["script"].write_text(
        json.dumps(
            {
                "stdout": "",
                "stderr": "X Pull request head commit does not match expected",
                "exit": 1,
            }
        )
    )
    with pytest.raises(GithubError, match="no longer"):
        github.merge_pr(tmp_path, 12, sha)


def test_create_pull_request_returns_the_number_from_the_url(
    recorded_gh: dict[str, Any], tmp_path: Path
) -> None:
    recorded_gh["script"].write_text(
        json.dumps({"stdout": "https://github.com/o/r/pull/31\n", "exit": 0})
    )
    assert (
        github.create_pull_request(
            tmp_path, head="b", base="master", title="t", body="x"
        )
        == 31
    )
    recorded_gh["script"].write_text(json.dumps({"stdout": "nothing\n", "exit": 0}))
    with pytest.raises(GithubError, match="no PR URL"):
        github.create_pull_request(
            tmp_path, head="b", base="master", title="t", body="x"
        )


def test_required_checks_are_empty_for_an_unprotected_branch(
    recorded_gh: dict[str, Any], tmp_path: Path
) -> None:
    recorded_gh["script"].write_text(
        json.dumps({"stdout": '["lint", "verify"]', "exit": 0})
    )
    assert github.required_checks(tmp_path, "master") == ("lint", "verify")
    recorded_gh["script"].write_text(
        json.dumps(
            {"stdout": "", "stderr": "HTTP 404: Branch not protected", "exit": 1}
        )
    )
    assert github.required_checks(tmp_path, "master") == ()
