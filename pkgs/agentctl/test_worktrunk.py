from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from agentctl.worktrunk import (
    LIST_SCHEMA_VERSION,
    ChecksFacts,
    PullFacts,
    Worktree,
    WorktrunkError,
    worktrunk_create,
    worktrunk_find,
    worktrunk_list,
    worktrunk_remove,
)


def _repository(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "master", str(root)], check=True)
    _commit(root, "init", allow_empty=True)
    return root


def _commit(root: Path, message: str, *, allow_empty: bool = False) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-q",
            *(("--allow-empty",) if allow_empty else ()),
            "-m",
            message,
        ],
        check=True,
    )


def test_list_pins_its_schema_over_a_user_config_that_selects_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: a user config selecting schema 1 must not reach the adapter.

    Schema 1 is a bare list with differently named fields, so reading it would
    make every access below silently wrong. The config here selects it
    explicitly, and the raw probe proves the config is in force, so dropping
    the per-call pin turns this red on any machine.
    """
    home = tmp_path / "home"
    (home / ".config" / "worktrunk").mkdir(parents=True)
    (home / ".config" / "worktrunk" / "config.toml").write_text(
        "[list]\njson-schema = 1\n"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    root = _repository(tmp_path / "repo")

    unpinned = subprocess.run(
        ["wt", "-C", str(root), "list", "--format=json"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert unpinned.stdout.lstrip().startswith("["), (
        "the fixture config must actually put wt on schema 1"
    )

    trees = worktrunk_list(root)

    assert LIST_SCHEMA_VERSION == 2
    assert [tree.branch for tree in trees] == ["master"]
    assert trees[0].main is True
    assert trees[0].path == root


def test_create_places_the_worktree_at_the_requested_path_and_remove_reverses_it(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path / "repo")
    target = tmp_path / "worktrees" / "lane"

    created = worktrunk_create(root, "feature/lane", path=target, base="master")

    assert created.path == target
    assert created.branch == "feature/lane"
    assert target.is_dir()
    assert worktrunk_find(root, "feature/lane") is not None

    worktrunk_remove(root, "feature/lane")

    assert not target.exists()
    assert worktrunk_find(root, "feature/lane") is None


def test_an_unpublished_branch_is_not_integrated(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    target = tmp_path / "worktrees" / "lane"
    worktrunk_create(root, "feature/lane", path=target, base="master")
    (target / "file.txt").write_text("content\n")
    subprocess.run(["git", "-C", str(target), "add", "file.txt"], check=True)
    _commit(target, "work")

    tree = worktrunk_find(root, "feature/lane")

    assert tree is not None
    assert tree.integrated is False
    assert tree.dirty is False


def test_a_missing_repository_is_a_typed_refusal(tmp_path: Path) -> None:
    with pytest.raises(WorktrunkError):
        worktrunk_list(tmp_path / "absent")


# Recorded from the live listing that broke the first `workspace create`: a
# detached worktree publishes `"branch": null` beside a valid path.
DETACHED_ITEM = {
    "branch": None,
    "head": {"sha": "dcc57853aedd35fb76cb18665016cfa51eac0cac"},
    "worktree": {
        "path": "/realm/worktrees/packet-polylogue-f16gi",
        "main": False,
        "detached": True,
        "changes": {"modified": True},
    },
    "display": {"state": "detached"},
}

BRANCH_ONLY_ITEM = {
    "branch": "feature/no-worktree",
    "head": {"sha": "3b56bb02205963d7edea903e0abfca8f02b6897a"},
    "display": {"state": "ahead"},
}


def test_a_detached_or_branch_only_item_is_read_not_refused() -> None:
    """Anti-vacuity: refusing either one failed the whole 84-item listing.

    One detached worktree anywhere in the repository made every workspace
    create, drop, and integrated check raise before doing anything.
    """
    detached = Worktree.from_item(DETACHED_ITEM)
    assert detached.branch is None
    assert detached.path == Path("/realm/worktrees/packet-polylogue-f16gi")
    assert detached.dirty is True

    branch_only = Worktree.from_item(BRANCH_ONLY_ITEM)
    assert branch_only.branch == "feature/no-worktree"
    assert branch_only.path is None
    assert branch_only.dirty is False


def test_an_item_with_neither_branch_nor_path_is_a_typed_refusal() -> None:
    with pytest.raises(WorktrunkError):
        Worktree.from_item({"display": {"state": "ahead"}})


FULL_ITEM = {
    "branch": "feature/reviewed",
    "head": {"sha": "3b56bb02205963d7edea903e0abfca8f02b6897a"},
    "display": {"state": "ahead"},
    "pr": {
        "number": 4501,
        "url": "https://github.com/o/r/pull/4501",
        "mergeable": True,
        "repo": "o/r",
    },
    "checks": {"status": "passed", "source": "hosted", "stale": False},
}


def test_a_full_item_parses_pr_and_checks() -> None:
    tree = Worktree.from_item(FULL_ITEM)
    assert tree.pr == PullFacts(
        number=4501, url="https://github.com/o/r/pull/4501", mergeable=True, repo="o/r"
    )
    assert tree.checks == ChecksFacts(status="passed", source="hosted", stale=False)


def test_an_item_without_pr_or_checks_leaves_them_absent() -> None:
    tree = Worktree.from_item(BRANCH_ONLY_ITEM)
    assert tree.pr is None
    assert tree.checks is None


def test_a_malformed_pr_or_checks_value_is_read_as_absent() -> None:
    """Defensive parsing: a shape wt has not published yet must not raise."""
    tree = Worktree.from_item(
        {**FULL_ITEM, "pr": {"number": "not-an-int"}, "checks": "not-a-mapping"}
    )
    assert tree.pr is None
    assert tree.checks is None


def test_worktrunk_list_only_asks_for_full_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    original = subprocess.run

    def spy(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        return original(argv, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    root = _repository(tmp_path / "repo")

    worktrunk_list(root)
    assert not any("--full" in call for call in calls)
    calls.clear()

    worktrunk_list(root, full=True)
    assert any("--full" in call for call in calls)


def test_find_skips_items_that_carry_no_branch(tmp_path: Path) -> None:
    """A detached worktree must not shadow or break a lookup by branch."""
    root = _repository(tmp_path / "repo")
    target = tmp_path / "worktrees" / "lane"
    worktrunk_create(root, "feature/lane", path=target, base="master")
    subprocess.run(["git", "-C", str(target), "checkout", "-q", "--detach"], check=True)

    listed = worktrunk_list(root)

    assert any(tree.branch is None for tree in listed), (
        "the fixture must actually produce a branchless item"
    )
    assert worktrunk_find(root, "feature/lane") is None
    assert worktrunk_find(root, "master") is not None
