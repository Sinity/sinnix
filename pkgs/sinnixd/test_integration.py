from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sinnixd.integration import (
    IntegrationError,
    IntegrationUnit,
    pack,
    unintegrated_content,
)


def _repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for argv in (
        ["git", "init", "-q", "-b", "master"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(argv, cwd=path, check=True, capture_output=True)


def _commit(path: Path, name: str, body: str) -> None:
    (path / name).write_text(body)
    subprocess.run(["git", "add", name], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", f"add {name}"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_landed_content_is_not_reported_as_unintegrated(tmp_path: Path) -> None:
    """A branch keeps its commits after a squash-merge lands its content.

    Anti-vacuity: comparing only `base...HEAD` reports this branch as pending
    forever, which is what made finished work look like a backlog.
    """
    repo = tmp_path / "repo"
    _repo(repo)
    _commit(repo, "base.txt", "base\n")
    subprocess.run(
        ["git", "checkout", "-qb", "lane"], cwd=repo, check=True, capture_output=True
    )
    _commit(repo, "feature.txt", "feature\n")
    subprocess.run(
        ["git", "checkout", "-q", "master"], cwd=repo, check=True, capture_output=True
    )

    subprocess.run(
        ["git", "checkout", "-q", "lane"], cwd=repo, check=True, capture_output=True
    )
    base = tmp_path / "base"
    subprocess.run(
        ["git", "worktree", "add", "-q", "--detach", str(base), "master"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert unintegrated_content(repo, "master", repo=base) == ("feature.txt",)

    # Land the same content on master the way a squash-merge does.
    subprocess.run(
        ["git", "checkout", "-q", "master"], cwd=repo, check=True, capture_output=True
    )
    _commit(repo, "feature.txt", "feature\n")
    subprocess.run(
        ["git", "checkout", "-q", "lane"], cwd=repo, check=True, capture_output=True
    )
    assert unintegrated_content(repo, "master", repo=base) == ()


def _unit(name: str, *files: str, dirty: bool = False) -> IntegrationUnit:
    return IntegrationUnit(
        name, Path("/realm/worktrees") / name, f"f/{name}", files, dirty
    )


def test_pack_keeps_file_sets_disjoint_within_a_batch() -> None:
    """Two lanes editing one file must not share a batch.

    Anti-vacuity: dropping the intersection check puts both `a` and `b` in the
    first batch, so their merge conflict looks like a base problem.
    """
    batches = pack([_unit("a", "x.py"), _unit("b", "x.py"), _unit("c", "y.py")])

    assert len(batches) == 2
    assert {u.workspace for u in batches[0].units} == {"a", "c"}
    assert [u.workspace for u in batches[1].units] == ["b"]


def test_pack_excludes_dirty_units_and_bounds_batch_size() -> None:
    """Uncommitted work is not integrable, and a batch stays reviewable."""
    units = [_unit(f"u{i}", f"f{i}.py") for i in range(5)] + [
        _unit("d", "z.py", dirty=True)
    ]
    batches = pack(units, max_units=2)

    assert all(len(b.units) <= 2 for b in batches)
    assert "d" not in {u.workspace for b in batches for u in b.units}
    with pytest.raises(IntegrationError):
        pack(units, max_units=0)


def test_a_branch_differing_only_in_lane_scratch_carries_no_work(
    tmp_path: Path,
) -> None:
    """`.lane/*` is gitignored publication text, not a change to integrate.

    Anti-vacuity: without the filter these branches pack into batches and each
    merge re-adds files the repository ignores.
    """
    from sinnixd.integration import discover_units

    repo = tmp_path / "repo"
    _repo(repo)
    _commit(repo, "base.txt", "base\n")
    common = Path(
        subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    worktrees = tmp_path / "worktrees"
    worktrees.mkdir()
    lane = worktrees / "lane"
    subprocess.run(
        ["git", "worktree", "add", "-q", str(lane), "-b", "lane", "master"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (lane / ".lane").mkdir()
    _commit(lane, ".lane/title", "fix: something\n")

    assert discover_units(worktrees, common, "master") == []
