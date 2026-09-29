from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from agentctl import gitcmd


def _repository(root: Path) -> Path:
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "master", str(root)], check=True)
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
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
    )
    return root


def _linked(root: Path, path: Path) -> Path:
    subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "-q", "-b", path.name, str(path)],
        check=True,
    )
    return path


def _fake_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    """Put a `git` on PATH that runs ``body``; `$FAKE_LOCK` names the lock it takes."""
    directory = tmp_path / "fake-bin"
    directory.mkdir()
    script = directory / "git"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")


# A git killed while it holds the index lock: SIGTERM is ignored, so only the
# SIGKILL after the grace period stops it, and the lock is stranded.
KILLED_MID_WRITE = ': > "$FAKE_LOCK"\ntrap "" TERM\nexec sleep 30\n'
# A git that, like the real one, removes its lock when asked to stop.
CLEANS_UP_ON_TERM = (
    ': > "$FAKE_LOCK"\n'
    "sleep 30 & child=$!\n"
    "trap 'rm -f \"$FAKE_LOCK\"; kill $child; exit 143' TERM\n"
    "wait $child\n"
)


def test_git_calls_disable_optional_index_refreshes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_OPTIONAL_LOCKS", "1")
    _fake_git(tmp_path, monkeypatch, 'printf %s "$GIT_OPTIONAL_LOCKS"\n')

    assert gitcmd.git(tmp_path, "status", error=RuntimeError) == "0"


def test_an_index_write_in_a_main_checkout_is_refused_unless_declared(
    tmp_path: Path,
) -> None:
    """Breaks if queued work can write a main checkout's index by accident."""
    root = _repository(tmp_path / "repo")
    (root / "a").write_text("a\n")

    with pytest.raises(RuntimeError, match="refused in the main checkout"):
        gitcmd.git(root, "add", "a", error=RuntimeError)
    # Nothing was staged; reads stay allowed and the declared exception works.
    assert gitcmd.git(root, "status", "--porcelain", error=RuntimeError) == "?? a"
    gitcmd.git(root, "add", "a", error=RuntimeError, main_checkout=True)
    assert gitcmd.git(root, "status", "--porcelain", error=RuntimeError) == "A  a"

    linked = _linked(root, tmp_path / "linked")
    (linked / "b").write_text("b\n")
    gitcmd.git(linked, "add", "b", error=RuntimeError)
    assert gitcmd.git(linked, "status", "--porcelain", error=RuntimeError) == "A  b"


def test_a_killed_write_in_an_owned_worktree_releases_its_lock_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path / "repo")
    linked = _linked(root, tmp_path / "linked")
    lock = root / ".git" / "worktrees" / "linked" / "index.lock"
    monkeypatch.setenv("FAKE_LOCK", str(lock))
    monkeypatch.setattr(gitcmd, "TERMINATE_GRACE_SECONDS", 0.3)
    _fake_git(tmp_path, monkeypatch, KILLED_MID_WRITE)

    with pytest.raises(RuntimeError, match="removed the stranded") as failed:
        gitcmd.git(linked, "merge", "x", timeout=0.3, error=RuntimeError, owned=True)

    stranded = gitcmd.stranded_index_lock(failed.value)
    assert stranded is not None and stranded.lock == lock and stranded.removed
    assert not lock.exists()


@pytest.mark.parametrize("where", ["main", "unowned"])
def test_a_killed_write_elsewhere_is_named_and_its_lock_left_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    """Breaks if agentctl deletes a lock in a checkout it does not own."""
    root = _repository(tmp_path / "repo")
    if where == "main":
        path, lock, flags = root, root / ".git" / "index.lock", {"main_checkout": True}
    else:
        path = _linked(root, tmp_path / "linked")
        lock = root / ".git" / "worktrees" / "linked" / "index.lock"
        flags = {}
    monkeypatch.setenv("FAKE_LOCK", str(lock))
    monkeypatch.setattr(gitcmd, "TERMINATE_GRACE_SECONDS", 0.3)
    _fake_git(tmp_path, monkeypatch, KILLED_MID_WRITE)

    with pytest.raises(RuntimeError, match="remove it by hand") as failed:
        gitcmd.git(path, "merge", "x", timeout=0.3, error=RuntimeError, **flags)

    stranded = gitcmd.stranded_index_lock(failed.value)
    assert stranded is not None and stranded.lock == lock and not stranded.removed
    assert lock.exists()


def test_a_timeout_asks_git_to_stop_before_killing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the timeout sends SIGKILL first: git would strand its lock."""
    root = _repository(tmp_path / "repo")
    linked = _linked(root, tmp_path / "linked")
    lock = root / ".git" / "worktrees" / "linked" / "index.lock"
    monkeypatch.setenv("FAKE_LOCK", str(lock))
    _fake_git(tmp_path, monkeypatch, CLEANS_UP_ON_TERM)

    with pytest.raises(RuntimeError, match="timed out") as failed:
        gitcmd.git(linked, "merge", "x", timeout=0.3, error=RuntimeError)

    assert gitcmd.stranded_index_lock(failed.value) is None
    assert not lock.exists()


def test_a_lock_that_predates_the_call_is_not_reported_as_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path / "repo")
    linked = _linked(root, tmp_path / "linked")
    lock = root / ".git" / "worktrees" / "linked" / "index.lock"
    lock.write_text("")
    os.utime(lock, ns=(0, 0))
    _fake_git(tmp_path, monkeypatch, "exit 128\n")

    with pytest.raises(RuntimeError) as failed:
        gitcmd.git(linked, "merge", "x", error=RuntimeError, owned=True)

    assert gitcmd.stranded_index_lock(failed.value) is None
    assert lock.exists()


def test_a_held_lock_is_never_stranded_and_never_cleared(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    linked = _linked(root, tmp_path / "linked")
    lock = root / ".git" / "worktrees" / "linked" / "index.lock"
    with lock.open("w"):
        os.utime(lock, ns=(0, 0))
        assert os.getpid() in gitcmd.lock_holders(lock)
        assert not gitcmd.stranded_lock(lock, since_ns=0)
        assert gitcmd.clear_stranded_lock(linked) is None
    assert lock.exists()


def test_clearing_releases_only_an_old_unheld_lock_in_a_linked_worktree(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path / "repo")
    linked = _linked(root, tmp_path / "linked")
    own = root / ".git" / "worktrees" / "linked" / "index.lock"
    main = root / ".git" / "index.lock"
    own.write_text("")
    assert gitcmd.clear_stranded_lock(linked) is None  # a writer may have just made it

    for lock in (own, main):
        lock.write_text("")
        os.utime(lock, ns=(0, 0))

    assert gitcmd.clear_stranded_lock(root) is None
    assert main.exists()
    assert gitcmd.clear_stranded_lock(linked) == own
    assert not own.exists()
