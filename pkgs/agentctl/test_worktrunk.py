from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

import pytest
from agentctl import landing
from agentctl.worktrunk import (
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


def _worktree(root: Path, branch: str, path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "-q", "-b", branch, str(path)],
        check=True,
    )


def _spy(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Every argv this process runs from here on."""
    calls: list[list[str]] = []
    original = subprocess.run

    def record(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        return original(argv, **kwargs)

    monkeypatch.setattr(subprocess, "run", record)
    return calls


def test_create_places_the_worktree_at_the_requested_path_and_remove_reverses_it(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path / "repo")
    target = tmp_path / "worktrees" / "lane"

    created = worktrunk_create(root, "feature/lane", path=target, base="master")

    assert created.path == target
    assert created.branch == "feature/lane"
    assert target.is_dir()

    worktrunk_remove(root, "feature/lane")

    assert not target.exists()
    assert worktrunk_find(root, "feature/lane") is None


def test_terminal_release_keeps_the_exact_branch_head(tmp_path: Path) -> None:
    """Anti-vacuity: branch deletion would make this worker commit unreachable."""
    root = _repository(tmp_path / "repo")
    target = tmp_path / "worktrees" / "lane"
    worktrunk_create(root, "batch/run/worker", path=target, base="master")
    (target / "worker.txt").write_text("candidate\n")
    subprocess.run(["git", "-C", str(target), "add", "worker.txt"], check=True)
    _commit(target, "worker candidate")
    head = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (root / "worker.txt").write_text("candidate\n")
    subprocess.run(["git", "-C", str(root), "add", "worker.txt"], check=True)
    _commit(root, "squash landing")

    worktrunk_remove(root, "batch/run/worker", keep_branch=True, reap=False)

    retained = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "refs/heads/batch/run/worker^{commit}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert not target.exists()
    assert retained == head


def test_detached_recovery_retains_each_head_after_a_failed_release(tmp_path: Path) -> None:
    """Anti-vacuity: one retry cannot replace the prior detached recovery ref."""
    root = _repository(tmp_path / "repo")
    first = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (root / "later.txt").write_text("later\n")
    subprocess.run(["git", "-C", str(root), "add", "later.txt"], check=True)
    _commit(root, "later detached head")
    second = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    checkout = tmp_path / "worktrees" / "detached"

    first_ref = landing._recovery_ref(root, "run", checkout, first)
    second_ref = landing._recovery_ref(root, "run", checkout, second)

    assert first_ref != second_ref
    for ref, expected in ((first_ref, first), (second_ref, second)):
        retained = subprocess.run(
            ["git", "-C", str(root), "rev-parse", f"{ref}^{{commit}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert retained == expected


def test_a_missing_repository_is_a_typed_refusal(tmp_path: Path) -> None:
    with pytest.raises(WorktrunkError):
        worktrunk_list(tmp_path / "absent")


def test_the_listing_reads_the_registry_and_marks_gits_own_checkout(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path / "repo")
    _worktree(root, "feature/lane", tmp_path / "lane")

    listed = worktrunk_list(root)

    assert [(tree.branch, tree.path, tree.main) for tree in listed] == [
        ("master", root, True),
        ("feature/lane", tmp_path / "lane", False),
    ]


def test_a_lookup_over_a_hundred_worktrees_statuses_none_of_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: the `wt list` this replaced ran three `git status` per
    worktree, one of which refreshes that worktree's index. Measured over 101
    worktrees it was 303 status processes for a single branch lookup, and over
    the 169 live ones it saturated the disk for minutes.
    """
    root = _repository(tmp_path / "repo")
    for index in range(100):
        _worktree(root, f"unrelated/{index}", tmp_path / f"w{index}")
    calls = _spy(monkeypatch)

    found = worktrunk_find(root, "unrelated/42")

    assert found is not None and found.path == tmp_path / "w42"
    assert not [call for call in calls if "status" in call]
    assert not [call for call in calls if Path(call[0]).name == "wt"]


def test_a_branch_with_no_worktree_is_found_without_a_path(tmp_path: Path) -> None:
    """A caller about to create a worktree must tell this from an absent branch."""
    root = _repository(tmp_path / "repo")
    subprocess.run(["git", "-C", str(root), "branch", "feature/idle"], check=True)

    assert worktrunk_find(root, "feature/idle") == Worktree(
        branch="feature/idle", path=None
    )
    assert worktrunk_find(root, "feature/never-existed") is None


def test_a_worktree_whose_directory_is_gone_keeps_its_registered_path(
    tmp_path: Path,
) -> None:
    """The landing unregisters such a branch before recreating it, so the
    lookup must publish the path rather than drop the entry."""
    root = _repository(tmp_path / "repo")
    _worktree(root, "feature/lane", tmp_path / "lane")
    subprocess.run(["rm", "-rf", str(tmp_path / "lane")], check=True)

    found = worktrunk_find(root, "feature/lane")

    assert found is not None
    assert found.path == tmp_path / "lane"
    assert not found.path.is_dir()


def test_a_detached_worktree_does_not_answer_for_its_former_branch(
    tmp_path: Path,
) -> None:
    """A worktree that carries no branch must not shadow or break a lookup."""
    root = _repository(tmp_path / "repo")
    target = tmp_path / "worktrees" / "lane"
    worktrunk_create(root, "feature/lane", path=target, base="master")
    subprocess.run(["git", "-C", str(target), "checkout", "-q", "--detach"], check=True)

    listed = worktrunk_list(root)

    assert any(tree.branch is None for tree in listed), (
        "the fixture must actually produce a branchless item"
    )
    assert worktrunk_find(root, "feature/lane") == Worktree(
        branch="feature/lane", path=None
    )
    assert worktrunk_find(root, "master") == Worktree(
        branch="master", path=root, main=True
    )


def _fake_wt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    """A `wt` earlier on PATH than the real one, running ``body``."""
    directory = tmp_path / "wt-bin"
    directory.mkdir(exist_ok=True)
    script = directory / "wt"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    runtime = tmp_path / "runtime"
    runtime.mkdir(exist_ok=True)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    return script


def test_two_removals_in_one_repository_never_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: the fixture holds the repository for 200 ms, so without the
    per-repository lock the two calls interleave every time."""
    root = _repository(tmp_path / "repo")
    ledger = tmp_path / "ledger"
    _fake_wt(
        tmp_path,
        monkeypatch,
        f'printf "enter %s\\n" "$4" >> {ledger}\n'
        "sleep 0.2\n"
        f'printf "exit %s\\n" "$4" >> {ledger}\n',
    )

    threads = [
        threading.Thread(target=worktrunk_remove, args=(root, name))
        for name in ("feature/one", "feature/two")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    lines = [line.split() for line in ledger.read_text().splitlines()]
    assert [step for step, _branch in lines] == ["enter", "exit", "enter", "exit"]
    assert lines[0][1] == lines[1][1] and lines[2][1] == lines[3][1]


def test_removal_returns_only_once_the_shared_index_lock_is_released(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity: wt's force removal returned before its own Git cleanup
    finished and left an unowned index lock behind, blocking the next
    fast-forward in a repository agentctl does not own."""
    root = _repository(tmp_path / "repo")
    index_lock = root / ".git" / "index.lock"
    _fake_wt(
        tmp_path,
        monkeypatch,
        f": > {index_lock}\n"
        f"( sleep 0.5; rm -f {index_lock} ) >/dev/null 2>&1 &\n"
        "exit 0\n",
    )

    worktrunk_remove(root, "feature/lane")

    assert not index_lock.exists()


def test_an_index_lock_the_mutation_did_not_create_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lock from another process is not this call's to wait for or to delete."""
    root = _repository(tmp_path / "repo")
    index_lock = root / ".git" / "index.lock"
    index_lock.write_text("")
    _fake_wt(tmp_path, monkeypatch, "exit 0\n")

    worktrunk_remove(root, "feature/lane")

    assert index_lock.exists()
