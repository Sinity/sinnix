from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import agentctl.evidence_history as history
import pytest
from agentctl.evidence_history import (
    MAX_GIT_OUTPUT_BYTES,
    GitHistoryError,
    discover_git_history,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(root: Path, message: str, filename: str) -> None:
    (root / filename).write_text(message, encoding="utf-8")
    _git(root, "add", filename)
    _git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        message,
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--initial-branch=main")
    return root


def test_discovers_exact_token_and_canonical_reference_from_reachable_history(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    _commit(root, "unrelated sinnix-42x", "one")
    _commit(
        root,
        "Implement sinnix-42 and trailer\n\nTask: "
        "sinnix://projects/demo/beads/sinnix-42",
        "two",
    )
    head = _git(root, "rev-parse", "HEAD")

    result = discover_git_history(
        root,
        project="demo",
        bead="sinnix-42",
        observed_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
    )

    assert result["reference"] == "HEAD"
    assert result["coverage"] == {
        "source": "git",
        "reachable_from": "HEAD",
        "commits_scanned": 2,
        "max_commits": 100,
        "complete": True,
    }
    assert len(result["links"]) == 1
    link = result["links"][0]
    assert link["commit_sha"] == head
    assert link["matched_references"] == [
        "sinnix://projects/demo/beads/sinnix-42",
        "sinnix-42",
    ]
    assert link["observed_at"] == "2026-09-11T12:00:00+00:00"
    assert link["association_only"] is True
    assert link["acceptance"] == "unknown"
    assert result["association_only"] is True
    assert result["acceptance"] == "unknown"


def test_token_matching_avoids_prefix_collisions_and_honors_explicit_ref_and_limit(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    _commit(root, "sinnix-4", "one")
    _commit(root, "sinnix-42 is not the requested task", "two")
    wanted = _git(root, "rev-parse", "HEAD~1")

    result = discover_git_history(
        root, project="demo", bead="sinnix-4", reference="HEAD~1", limit=1
    )

    assert result["coverage"]["commits_scanned"] == 1
    assert result["coverage"]["reachable_from"] == "HEAD~1"
    assert result["links"][0]["commit_sha"] == wanted
    assert result["links"][0]["matched_reference"] == "sinnix-4"


def test_foreign_or_suffix_canonical_references_are_not_associated(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    _commit(root, "sinnix://projects/other/beads/sinnix-42", "foreign")
    _commit(root, "sinnix://projects/demo/beads/sinnix-42/child", "suffix")

    result = discover_git_history(root, project="demo", bead="sinnix-42")

    assert result["links"] == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"project": "demo/x"}, "project"),
        ({"bead": "sinnix-4/extra"}, "bead"),
        ({"reference": "-n"}, "ref"),
        ({"reference": "HEAD bad"}, "ref"),
        ({"limit": 0}, "limit"),
        ({"limit": True}, "limit"),
        ({"limit": MAX_GIT_OUTPUT_BYTES}, "limit"),
    ],
)
def test_validates_inputs(
    tmp_path: Path, kwargs: dict[str, object], message: str
) -> None:
    root = _repo(tmp_path)
    arguments: dict[str, object] = {"project": "demo", "bead": "sinnix-4"}
    arguments.update(kwargs)
    with pytest.raises(GitHistoryError, match=message):
        discover_git_history(root, **arguments)  # type: ignore[arg-type]


def test_git_failure_is_reported_without_claiming_no_history(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(GitHistoryError, match="git log failed"):
        discover_git_history(root, project="demo", bead="sinnix-4", reference="missing")


def test_rejects_git_output_over_the_read_bound(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    real_popen = history.subprocess.Popen

    def oversized(*_args, **_kwargs):
        return real_popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'x' * (4 * 1024 * 1024 + 1))",
            ],
            stdout=_kwargs["stdout"],
            stderr=_kwargs["stderr"],
        )

    monkeypatch.setattr(history.subprocess, "Popen", oversized)
    with pytest.raises(GitHistoryError, match="output exceeds"):
        discover_git_history(root, project="demo", bead="sinnix-4")


def test_deadline_applies_after_process_closes_output(
    tmp_path: Path, monkeypatch
) -> None:
    root = _repo(tmp_path)
    real_popen = history.subprocess.Popen

    def closed_output(*_args, **_kwargs):
        return real_popen(
            [
                sys.executable,
                "-c",
                "import os,time; os.close(1); os.close(2); time.sleep(10)",
            ],
            stdout=_kwargs["stdout"],
            stderr=_kwargs["stderr"],
        )

    monkeypatch.setattr(history.subprocess, "Popen", closed_output)
    monkeypatch.setattr(history, "CALL_TIMEOUT_SECONDS", 0.1)
    with pytest.raises(GitHistoryError, match="timed out"):
        discover_git_history(root, project="demo", bead="sinnix-4")
