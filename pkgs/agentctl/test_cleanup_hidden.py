"""Retirement must not discard bytes Git status omits."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from agentctl import worktree_cleanup as cleanup
from agentctl import worktrunk
from agentctl.worktrunk import Worktree


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def checkout(config, project_root, tmp_path, monkeypatch):
    from agentctl.projects import load_project_adapter

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    ):
        monkeypatch.delenv(name, raising=False)
    git(project_root, "init", "-q", "-b", "master")
    # Worktree commits share this repository's synthetic identity; the host's
    # global Git configuration is not part of the fixture.
    git(project_root, "config", "user.name", "Fixture")
    git(project_root, "config", "user.email", "fixture@example.test")
    (project_root / "tracked.txt").write_text("committed")
    (project_root / ".gitignore").write_text("ignored*\n.agentctl/receipt*\n")
    git(project_root, "add", ".")
    git(project_root, "commit", "-qm", "fixture")
    path = tmp_path / "checkout"
    git(project_root, "worktree", "add", "-qb", "candidate", str(path))
    tree = Worktree(branch="candidate", path=path)
    monkeypatch.setattr(
        worktrunk,
        "worktrunk_list",
        lambda root: (Worktree(branch="master", path=project_root, main=True), tree),
    )
    monkeypatch.setattr(worktrunk, "worktrunk_find", lambda root, branch: tree)
    monkeypatch.setattr(cleanup, "_task_users", lambda path: [])
    monkeypatch.setattr(cleanup, "_process_users", lambda path: [])

    def remove(root, branch, **kwargs):
        git(root, "worktree", "remove", str(path))

    monkeypatch.setattr(worktrunk, "worktrunk_remove", remove)
    return config, load_project_adapter(project_root), path


def drop(checkout):
    config, project, path = checkout
    return cleanup._drop_branch(
        config, project, "candidate", base=git(project.root, "rev-parse", "HEAD")
    )


@pytest.mark.parametrize("kind", ["ignored", "--assume-unchanged", "--skip-worktree"])
def test_cleanup_preserves_hidden_working_bytes(checkout, kind):
    _, _, path = checkout
    if kind == "ignored":
        target = path / "ignored-private.txt"
    else:
        target = path / "tracked.txt"
        git(path, "update-index", kind, "tracked.txt")
    target.write_bytes(b"unpublished fixture bytes")
    assert git(path, "status", "--porcelain") == ""
    before = target.read_bytes(), target.stat().st_ino, target.stat().st_mtime_ns
    reason = drop(checkout)
    assert reason and "kept" in reason
    assert (
        target.read_bytes(),
        target.stat().st_ino,
        target.stat().st_mtime_ns,
    ) == before


def test_cleanup_removes_clean_checkout_after_retaining_owned_artifacts(checkout):
    config, project, path = checkout
    receipt = path / ".agentctl/receipt-private.txt"
    receipt.write_bytes(b"retained fixture result")
    assert drop(checkout) is None
    assert not path.exists()
    retained = list((config.state_dir / "artifacts").rglob("receipt-private.txt.*"))
    assert len(retained) == 1 and retained[0].read_bytes() == b"retained fixture result"
    assert git(project.root, "rev-parse", "candidate") == git(
        project.root, "rev-parse", "master"
    )


def test_cleanup_refuses_reused_foreign_checkout_path(checkout, tmp_path, monkeypatch):
    config, project, path = checkout
    shutil.rmtree(path)
    git(tmp_path, "clone", "-q", str(project.root), str(path))
    retained = path / "ignored-private.txt"
    retained.write_bytes(b"foreign repository content")
    assert git(path, "status", "--porcelain") == ""
    assert git(path, "rev-parse", "HEAD") == git(project.root, "rev-parse", "candidate")

    def no_remove(*args, **kwargs):
        raise AssertionError("foreign checkout must refuse before removal")

    monkeypatch.setattr(worktrunk, "worktrunk_remove", no_remove)
    reason = drop(checkout)
    assert reason and "another Git repository" in reason
    assert retained.read_bytes() == b"foreign repository content"


def test_cleanup_keeps_artifact_changed_after_preservation(checkout, monkeypatch):
    _, _, path = checkout
    receipt = path / ".agentctl/receipt-private.txt"
    receipt.write_bytes(b"first result")
    original = cleanup._preserve_artifacts

    def changed(*args, **kwargs):
        copied = original(*args, **kwargs)
        receipt.write_bytes(b"later unpublished result")
        return copied

    monkeypatch.setattr(cleanup, "_preserve_artifacts", changed)
    reason = drop(checkout)
    assert reason and "changed after preservation" in reason
    assert receipt.read_bytes() == b"later unpublished result"


def test_cleanup_keeps_unknown_ignored_directory(checkout):
    _, _, path = checkout
    directory = path / "ignored-native-store"
    directory.mkdir()
    (directory / "private.bin").write_bytes(b"unknown retained evidence")
    reason = drop(checkout)
    assert reason and "ignored directory" in reason
    assert (directory / "private.bin").read_bytes() == b"unknown retained evidence"


def test_cleanup_keeps_inaccessible_detached_checkout(checkout, monkeypatch):
    config, project, path = checkout
    monkeypatch.setattr(
        worktrunk, "worktrunk_list", lambda root: (Worktree(branch=None, path=path),)
    )
    monkeypatch.setattr(worktrunk, "worktrunk_find", lambda root, branch: None)
    original = Path.stat

    def denied(candidate, *args, **kwargs):
        if candidate == path:
            raise PermissionError("synthetic checkout denial")
        return original(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", denied)

    def no_remove(*args, **kwargs):
        raise AssertionError("unavailable checkout must not reach removal")

    monkeypatch.setattr(worktrunk, "worktrunk_remove", no_remove)
    reason = cleanup._drop_branch(
        config,
        project,
        "candidate",
        base=git(project.root, "rev-parse", "HEAD"),
        recorded_path=path,
    )
    assert reason and "synthetic checkout denial" in reason


@pytest.fixture
def unregistered_branch(checkout, monkeypatch):
    config, project, path = checkout
    head = git(project.root, "rev-parse", "candidate")
    git(project.root, "worktree", "remove", str(path))
    monkeypatch.setattr(
        worktrunk,
        "worktrunk_list",
        lambda root: (Worktree(branch="master", path=project.root, main=True),),
    )
    monkeypatch.setattr(
        worktrunk,
        "worktrunk_find",
        lambda root, branch: Worktree(branch=branch, path=None),
    )
    return config, project, path, head


def test_absent_checkout_retirement_really_removes_branch_and_retains_head(
    unregistered_branch,
):
    config, project, path, head = unregistered_branch
    assert (
        cleanup._drop_branch(
            config,
            project,
            "candidate",
            base=head,
            recorded_path=path,
            delete_branch=True,
        )
        is None
    )
    missing = subprocess.run(
        [
            "git",
            "-C",
            str(project.root),
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/candidate",
        ],
        capture_output=True,
    )
    assert missing.returncode == 1
    assert (
        head
        in git(
            project.root,
            "for-each-ref",
            "--format=%(objectname)",
            "refs/agentctl/recovery",
        ).splitlines()
    )


@pytest.mark.parametrize("kind", ["denied", "broken_link", "wrong_parent"])
def test_unregistered_checkout_uncertainty_keeps_branch(
    unregistered_branch, tmp_path, kind
):
    config, project, path, head = unregistered_branch
    blocked = tmp_path / "blocked"
    payload = None
    if kind == "denied":
        blocked.mkdir()
        path = blocked / "residue"
        path.mkdir()
        payload = path / "unpublished.txt"
        payload.write_bytes(b"unpublished fixture bytes")
        blocked.chmod(0)
    elif kind == "broken_link":
        path.symlink_to(tmp_path / "missing")
    else:
        blocked.write_bytes(b"unexpected parent object")
        path = blocked / "residue"
    try:
        reason = cleanup._drop_branch(
            config,
            project,
            "candidate",
            base=head,
            recorded_path=path,
            delete_branch=True,
        )
        assert reason and "kept" in reason, (
            "unknown checkout presence authorized branch retirement"
        )
        assert git(project.root, "rev-parse", "candidate") == head
        assert not git(
            project.root,
            "for-each-ref",
            "--format=%(refname)",
            "refs/agentctl/recovery",
        )
    finally:
        if kind == "denied":
            blocked.chmod(0o700)
    if payload is not None:
        assert payload.read_bytes() == b"unpublished fixture bytes"
    if kind == "broken_link":
        assert path.is_symlink()


def test_post_removal_broken_link_is_retained_as_residue(checkout, monkeypatch):
    config, project, path = checkout
    head = git(project.root, "rev-parse", "candidate")

    def remove(root, branch, **kwargs):
        git(root, "worktree", "remove", str(path))
        path.symlink_to(path.parent / "absent")

    monkeypatch.setattr(worktrunk, "worktrunk_remove", remove)
    reason = cleanup._drop_branch(
        config, project, "candidate", base=head, recorded_path=path, delete_branch=True
    )
    assert reason and "remains after removal" in reason
    assert path.is_symlink()
    assert git(project.root, "rev-parse", "candidate") == head


def test_unreadable_untracked_agent_state_prevents_release(checkout, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root bypasses directory mode checks")
    config, project, path = checkout
    state = path / ".agentctl" / "interrupted"
    state.mkdir(parents=True)
    payload = state / "payload.bin"
    payload.write_bytes(b"original interrupted output")

    def refuse_removal(*args, **kwargs):
        pytest.fail("release attempted with inaccessible unpreserved state")

    monkeypatch.setattr(worktrunk, "worktrunk_remove", refuse_removal)
    state.chmod(0)
    try:
        reason = drop(checkout)
        assert reason and "not preserved" in reason
    finally:
        state.chmod(0o700)
    assert payload.read_bytes() == b"original interrupted output"
