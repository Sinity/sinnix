from __future__ import annotations

import subprocess
from pathlib import Path

from sinnixd.lanes import GENERATED_PATHS, derive_units, disposable, refresh_base, stuck


def _run(argv: list[str], cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, capture_output=True)


def _repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for argv in (
        ["git", "init", "-q", "-b", "master"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        _run(argv, path)


def _commit(path: Path, name: str, body: str, message: str | None = None) -> None:
    (path / name).write_text(body)
    _run(["git", "add", name], path)
    _run(["git", "commit", "-qm", message or f"add {name}"], path)


def _common_dir(repo: Path) -> Path:
    return Path(
        subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    """A repo plus a worktree root holding one lane per state under test."""
    repo = tmp_path / "repo"
    _repo(repo)
    _commit(repo, "base.txt", "base\n")
    trees = tmp_path / "worktrees"
    trees.mkdir()

    # holds content master does not have
    _run(["git", "worktree", "add", "-q", "-b", "held", str(trees / "held")], repo)
    _commit(trees / "held", "held.txt", "held\n")

    # its content landed on master, so only the commits remain
    _run(["git", "worktree", "add", "-q", "-b", "landed", str(trees / "landed")], repo)
    _commit(trees / "landed", "landed.txt", "landed\n")
    # A squash-merge lands the same content under a different commit.
    _commit(repo, "landed.txt", "landed\n", message="squash: landed.txt")

    # nothing beyond master
    _run(["git", "worktree", "add", "-q", "-b", "spent", str(trees / "spent")], repo)
    return repo, trees


def test_a_branch_holding_content_is_stuck_and_never_disposable(tmp_path: Path) -> None:
    """Work with no landed copy stays visible; gc must refuse it.

    Anti-vacuity: classifying on commits-ahead instead of content marks the
    landed lane as held too, and classifying on a pull request marks the held
    lane disposable -- the failure that sent shipped worktrees to deletion.
    """
    repo, trees = _fixture(tmp_path)

    units = {
        unit.workspace: unit
        for unit in derive_units(
            trees, _common_dir(repo), "master", jobs_dir=tmp_path / "none", live_cwds=()
        )
    }

    assert units["held"].state == "unpublished"
    assert units["held"].files == ("held.txt",)
    assert units["landed"].state == "integrated"
    assert units["landed"].commits_ahead == 1
    assert units["spent"].state == "empty"

    assert [unit.workspace for unit in stuck(units.values())] == ["held"]
    assert sorted(unit.workspace for unit in disposable(units.values())) == [
        "landed",
        "spent",
    ]


def test_a_live_checkout_is_never_disposable(tmp_path: Path) -> None:
    """A process working in a checkout outranks every other signal.

    Anti-vacuity: dropping the live check makes the spent lane disposable while
    something is still using it.
    """
    repo, trees = _fixture(tmp_path)

    units = {
        unit.workspace: unit
        for unit in derive_units(
            trees,
            _common_dir(repo),
            "master",
            jobs_dir=tmp_path / "none",
            live_cwds=(str(trees / "spent"),),
        )
    }

    assert units["spent"].state == "running"
    assert "spent" not in {unit.workspace for unit in disposable(units.values())}


def test_gate_leftovers_are_not_uncommitted_work(tmp_path: Path) -> None:
    """A checkout holding only generated files is disposable, not dirty.

    Anti-vacuity: counting every untracked path makes this lane dirty, and every
    checkout a gate has touched then blocks its own disposal forever.
    """
    repo, trees = _fixture(tmp_path)
    for name in GENERATED_PATHS:
        target = trees / "spent" / name.rstrip("/")
        if name.endswith("/"):
            target.mkdir(exist_ok=True)
            (target / "leftover").write_text("generated\n")
        else:
            target.write_text("generated\n")

    units = {
        unit.workspace: unit
        for unit in derive_units(
            trees, _common_dir(repo), "master", jobs_dir=tmp_path / "none", live_cwds=()
        )
    }

    assert units["spent"].state == "empty"
    assert units["spent"] in disposable(units.values())


def test_uncommitted_changes_are_stuck_rather_than_collected(tmp_path: Path) -> None:
    """Dirty work is a decision, not garbage.

    Anti-vacuity: without the dirty check this lane classifies empty and gc
    deletes uncommitted work.
    """
    repo, trees = _fixture(tmp_path)
    (trees / "spent" / "scratch.txt").write_text("unsaved\n")

    units = {
        unit.workspace: unit
        for unit in derive_units(
            trees, _common_dir(repo), "master", jobs_dir=tmp_path / "none", live_cwds=()
        )
    }

    assert units["spent"].state == "dirty"
    assert units["spent"] in stuck(units.values())
    assert units["spent"] not in disposable(units.values())


def test_refresh_base_only_fetches_a_remote_tracking_ref(tmp_path: Path) -> None:
    """A local base has no remote to update, and must not be treated as one.

    Anti-vacuity: without the split, a bare local branch name is handed to
    `git fetch` as a remote and the derivation reports a failure that is not one.
    """
    repo, _trees = _fixture(tmp_path)

    assert refresh_base(repo, "master") is False
    assert refresh_base(repo, "./master") is False
