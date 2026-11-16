"""Publication checks, recovery refs and cache removal for completed worktrees."""

import os
import shutil
import subprocess

import pytest
from agentctl import worktree_cleanup as cleanup
from agentctl import worktrunk
from agentctl.worktrunk import Worktree

CACHE_TAG = b"Signature: 8a477f597d28d172789f06886806bc55"


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def checkout(config, project_root, tmp_path, monkeypatch, fake_pueue):
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
    git(project_root, "config", "user.name", "Fixture")
    git(project_root, "config", "user.email", "fixture@example.test")
    (project_root / "tracked.txt").write_text("committed")
    (project_root / ".gitignore").write_text("ignored*\n.agentctl/output*\n")
    git(project_root, "add", ".")
    git(project_root, "commit", "-qm", "fixture")
    path = tmp_path / "checkout"
    git(project_root, "worktree", "add", "-qb", "candidate", str(path))
    tree = Worktree(branch="candidate", path=path)
    registry = [Worktree(branch="master", path=project_root, main=True), tree]
    monkeypatch.setattr(worktrunk, "worktrunk_list", lambda root: tuple(registry))

    def remove(root, branch, **kwargs):
        git(root, "worktree", "remove", str(path))
        registry.remove(tree)

    monkeypatch.setattr(worktrunk, "worktrunk_remove", remove)
    return config, load_project_adapter(project_root), path


def drop(checkout):
    config, project, path = checkout
    result = cleanup.clean(config, project, paths=[path])
    return result["kept"][0]["reason"] if result["kept"] else None


def test_cleanup_refuses_reused_foreign_checkout_path(checkout, tmp_path, monkeypatch):
    _, project, path = checkout
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


def test_cleanup_keeps_inaccessible_detached_checkout(checkout, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root bypasses directory mode checks")
    _, _, path = checkout
    git(path, "checkout", "--detach")
    monkeypatch.setattr(
        worktrunk, "worktrunk_list", lambda root: (Worktree(branch=None, path=path),)
    )

    def no_remove(*args, **kwargs):
        raise AssertionError("unavailable checkout must not reach removal")

    monkeypatch.setattr(worktrunk, "worktrunk_remove", no_remove)
    mode = path.stat().st_mode & 0o7777
    path.chmod(0)
    try:
        reason = drop(checkout)
        assert reason and str(path) in reason
    finally:
        path.chmod(mode)
    assert path.is_dir()


def test_post_removal_broken_link_is_retained_as_residue(checkout, monkeypatch):
    _, project, path = checkout
    head = git(project.root, "rev-parse", "candidate")

    def remove(root, branch, **kwargs):
        git(root, "worktree", "remove", str(path))
        path.symlink_to(path.parent / "absent")

    monkeypatch.setattr(worktrunk, "worktrunk_remove", remove)
    reason = drop(checkout)
    assert reason and "remains after removal" in reason
    assert path.is_symlink()
    assert git(project.root, "rev-parse", "candidate") == head


def test_unreadable_untracked_agent_state_prevents_release(checkout, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root bypasses directory mode checks")
    _, _, path = checkout
    state = path / ".agentctl" / "interrupted"
    state.mkdir(parents=True)
    payload = state / "payload.bin"
    payload.write_bytes(b"original interrupted output")

    def refuse_removal(*args, **kwargs):
        pytest.fail("release attempted with inaccessible unpublished state")

    monkeypatch.setattr(worktrunk, "worktrunk_remove", refuse_removal)
    state.chmod(0)
    try:
        reason = drop(checkout)
        assert reason and "git status" in reason and ".agentctl/interrupted/" in reason
    finally:
        state.chmod(0o700)
    assert payload.read_bytes() == b"original interrupted output"


@pytest.fixture
def owned(checkout, fake_pueue, monkeypatch):
    monkeypatch.setattr(cleanup.github, "gh_json", lambda *a, **k: [])
    return checkout


def cache(path):
    target = path / "target"
    target.mkdir()
    (target / "CACHEDIR.TAG").write_bytes(CACHE_TAG + b"\n")
    (target / "compiled").write_bytes(b"disposable synthetic output")
    # A real Git ignore, with no uncommitted source change.
    common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    with open(common + "/info/exclude", "a") as f:
        f.write("\ntarget/\n")
    return target


def clean(owned):
    return cleanup.clean(owned[0], owned[1])


def test_ancestor_removes_checkout_cache_and_branch_with_recovery(owned):
    config, project, path = owned
    head = git(path, "rev-parse", "HEAD")
    cache(path)
    result = clean(owned)
    assert result["removed"] == ["candidate"] and not result["kept"]
    assert not path.exists()
    assert (
        head
        in git(
            project.root,
            "for-each-ref",
            "--format=%(objectname)",
            "refs/agentctl/recovery",
        ).splitlines()
    )
    assert (
        subprocess.run(
            [
                "git",
                "-C",
                str(project.root),
                "show-ref",
                "--quiet",
                "refs/heads/candidate",
            ]
        ).returncode
        == 1
    )


def test_unique_unpublished_change_is_kept(owned):
    _, _, path = owned
    (path / "feature").write_text("unpublished\n")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    result = clean(owned)
    assert not result["removed"]
    reason = result["kept"][0]["reason"]
    assert reason.startswith("publication not proved: HEAD ")
    assert "no merged PR for branch candidate" in reason
    assert (path / "feature").read_text() == "unpublished\n"


def origin(owned):
    """A bare origin with master and the candidate branch, as on the forge."""
    _, project, path = owned
    remote = project.root.parent / "origin.git"
    git(project.root.parent, "init", "-q", "--bare", "-b", "master", str(remote))
    git(project.root, "remote", "add", "origin", str(remote))
    git(project.root, "push", "-q", "origin", "master")
    git(project.root, "fetch", "-q", "origin")
    return remote


def squash_merge_on_forge(remote, content):
    """Land the change and unrelated work on origin's master, not locally."""
    clone = remote.parent / "merger"
    git(remote.parent, "clone", "-q", str(remote), str(clone))
    git(clone, "config", "user.name", "Fixture")
    git(clone, "config", "user.email", "fixture@example.test")
    (clone / "feature").write_text(content)
    (clone / "other").write_text("independent\n")
    git(clone, "add", ".")
    git(clone, "commit", "-qm", "squashed feature and later work")
    git(clone, "push", "-q", "origin", "master")
    return git(clone, "rev-parse", "HEAD")


def forge(monkeypatch, *rows):
    calls = []

    def pulls(arguments, **kwargs):
        calls.append(list(arguments))
        return list(rows)

    monkeypatch.setattr(cleanup.github, "gh_json", pulls)
    return calls


def test_squash_merged_pull_request_retires_checkout_and_branches(owned, monkeypatch):
    config, project, path = owned
    remote = origin(owned)
    (path / "feature").write_text("published\n")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    head = git(path, "rev-parse", "HEAD")
    git(path, "push", "-q", "origin", "candidate")
    merge = squash_merge_on_forge(remote, "published\n")
    calls = forge(
        monkeypatch, {"number": 7, "headRefOid": head, "mergeCommit": {"oid": merge}}
    )
    cache(path)
    result = clean(owned)
    assert result["removed"] == ["candidate"] and not result["kept"], result
    assert calls[0][4:6] == ["--head", "candidate"]
    assert not path.exists()
    assert git(remote, "branch", "--list", "candidate") == ""
    assert git(project.root, "branch", "--list", "candidate") == ""
    assert (
        head
        in git(
            project.root,
            "for-each-ref",
            "--format=%(objectname)",
            "refs/agentctl/recovery",
        ).splitlines()
    )


def test_default_branch_comes_from_origin_not_the_main_checkouts_branch(
    owned, monkeypatch
):
    from agentctl.projects import load_project_adapter

    config, project, path = owned
    # A descriptor without a workspace section names no default base.
    descriptor = project.root / ".agentctl" / "project.toml"
    text = descriptor.read_text()
    start = text.index("[workspace]")
    end = text.index("[operations.", start)
    descriptor.write_text(text[:start] + text[end:])
    project = load_project_adapter(project.root)
    assert project.workspace is None
    owned = (config, project, path)
    remote = origin(owned)
    # The main checkout sits on an older feature branch that origin also has.
    git(project.root, "switch", "-qc", "elsewhere")
    git(project.root, "push", "-q", "origin", "elsewhere")
    git(project.root, "fetch", "-q", "origin")
    # A checkout cloned long ago, or never fully fetched, has no origin/HEAD,
    # and fetching one branch does not create it.
    git(project.root, "remote", "set-head", "origin", "--delete")
    git(project.root, "config", "remote.origin.followRemoteHEAD", "never")
    (path / "feature").write_text("published\n")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    head = git(path, "rev-parse", "HEAD")
    merge = squash_merge_on_forge(remote, "published\n")
    forge(monkeypatch, {"number": 7, "headRefOid": head, "mergeCommit": {"oid": merge}})
    assert cleanup.Published(project).base == merge
    assert clean(owned)["removed"] == ["candidate"]


def test_unmerged_branch_on_forge_is_kept_with_the_missing_fact(owned, monkeypatch):
    _, _, path = owned
    remote = origin(owned)
    (path / "feature").write_text("published\n")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    git(path, "push", "-q", "origin", "candidate")
    squash_merge_on_forge(remote, "a different change\n")
    forge(monkeypatch)
    result = clean(owned)
    assert not result["removed"] and path.exists()
    assert "no merged PR for branch candidate" in result["kept"][0]["reason"]
    assert git(remote, "branch", "--list", "candidate").strip() == "candidate"


def test_merged_pull_request_with_another_head_is_kept(owned, monkeypatch):
    _, _, path = owned
    remote = origin(owned)
    (path / "feature").write_text("first\n")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    merged_head = git(path, "rev-parse", "HEAD")
    merge = squash_merge_on_forge(remote, "first\n")
    (path / "feature").write_text("second, never published\n")
    git(path, "commit", "-qam", "later")
    forge(
        monkeypatch,
        {"number": 7, "headRefOid": merged_head, "mergeCommit": {"oid": merge}},
    )
    result = clean(owned)
    assert not result["removed"] and path.exists()
    assert "no merged PR has head" in result["kept"][0]["reason"]


def test_dirty_squash_merged_checkout_is_kept_and_names_the_path(owned, monkeypatch):
    _, _, path = owned
    remote = origin(owned)
    (path / "feature").write_text("published\n")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    head = git(path, "rev-parse", "HEAD")
    merge = squash_merge_on_forge(remote, "published\n")
    forge(monkeypatch, {"number": 7, "headRefOid": head, "mergeCommit": {"oid": merge}})
    (path / "notes.txt").write_text("unfinished\n")
    result = clean(owned)
    assert not result["removed"] and (path / "notes.txt").exists()
    assert (
        result["kept"][0]["reason"] == "worktree kept; uncommitted changes: notes.txt"
    )
    (path / "notes.txt").unlink()
    (path / "tracked.txt").write_text("edited\n")
    result = clean(owned)
    assert (
        result["kept"][0]["reason"] == "worktree kept; uncommitted changes: tracked.txt"
    )


def test_exact_external_cache_is_removed_with_its_checkout(
    owned, monkeypatch, tmp_path
):
    _, _, path = owned
    import hashlib
    import os

    root = tmp_path / "compiler-cache"
    parent = (
        root
        / str(os.getuid())
        / hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]
    )
    target = parent / "target"
    target.mkdir(parents=True)
    (target / "CACHEDIR.TAG").write_bytes(CACHE_TAG + b"\n")
    (target / "object").write_bytes(b"compiled")
    (parent / "checkout").write_text(str(path.resolve()) + "\n")
    other = root / "untouched"
    other.mkdir()
    (other / "private").write_bytes(b"other cache")
    monkeypatch.setenv("SINNIX_CARGO_CACHE_ROOT", str(root))
    result = clean(owned)
    assert (
        result["removed"] == ["candidate"] and not path.exists() and not parent.exists()
    )
    assert (other / "private").read_bytes() == b"other cache"


def test_empty_nextest_directory_skeleton_is_disposable(owned):
    _, project, path = owned
    common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    with open(common + "/info/exclude", "a") as f:
        f.write("\ntarget/\n")
    (path / "target/nextest/run").mkdir(parents=True)
    assert clean(owned)["removed"] == ["candidate"]


def test_forge_head_must_match_exactly_and_merge_must_be_published(owned, monkeypatch):
    _, project, path = owned
    (path / "feature").write_text("candidate")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    head = git(path, "rev-parse", "HEAD")
    base = git(project.root, "rev-parse", "HEAD")
    calls = []
    merged = head

    def pulls(*args, **kwargs):
        calls.append(args)
        return [{"headRefOid": head, "mergeCommit": {"oid": merged}}]

    monkeypatch.setattr(cleanup.github, "gh_json", pulls)
    assert not cleanup.Published(project).contains(head)
    calls.clear()
    merged = base
    published = cleanup.Published(project)
    assert published.contains(head) and published.contains(head) and len(calls) == 1
    (path / "later").write_text("unpublished")
    git(path, "add", "later")
    git(path, "commit", "-qm", "later")
    assert not published.contains(git(path, "rev-parse", "HEAD"))


def test_a_new_commit_after_publication_check_is_not_removed(owned, monkeypatch):
    _, _, path = owned
    save_ref = cleanup._recovery_ref

    def changed(*args, **kwargs):
        result = save_ref(*args, **kwargs)
        (path / "new-work").write_text("unpublished")
        git(path, "add", "new-work")
        git(path, "commit", "-qm", "new work")
        return result

    monkeypatch.setattr(cleanup, "_recovery_ref", changed)
    result = clean(owned)
    assert result["kept"] and (path / "new-work").read_text() == "unpublished"


@pytest.mark.parametrize(
    "marker", [b"other checkout\n", b"", b"extra\nlines\n", b"\xff"]
)
def test_external_cache_with_wrong_checkout_marker_is_kept(
    owned, monkeypatch, tmp_path, marker
):
    import hashlib
    import os

    _, _, path = owned
    root = tmp_path / "cache"
    parent = (
        root
        / str(os.getuid())
        / hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]
    )
    target = parent / "target"
    target.mkdir(parents=True)
    (target / "CACHEDIR.TAG").write_bytes(CACHE_TAG + b"\n")
    (parent / "checkout").write_bytes(marker)
    monkeypatch.setenv("SINNIX_CARGO_CACHE_ROOT", str(root))
    result = clean(owned)
    assert result["kept"] and path.exists() and target.exists()
    assert (parent / "checkout").read_bytes() == marker


def test_external_cache_with_symlinked_checkout_marker_is_kept(
    owned, monkeypatch, tmp_path
):
    import hashlib
    import os

    _, _, path = owned
    root = tmp_path / "cache"
    parent = (
        root
        / str(os.getuid())
        / hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]
    )
    target = parent / "target"
    target.mkdir(parents=True)
    (target / "CACHEDIR.TAG").write_bytes(CACHE_TAG + b"\n")
    outside = tmp_path / "marker"
    outside.write_text(str(path.resolve()) + "\n")
    (parent / "checkout").symlink_to(outside)
    monkeypatch.setenv("SINNIX_CARGO_CACHE_ROOT", str(root))
    result = clean(owned)
    assert result["kept"] and path.exists() and target.exists()
    assert (parent / "checkout").is_symlink()
    assert outside.read_text() == str(path.resolve()) + "\n"


def test_equal_default_tree_removes_squashed_checkout(owned):
    _, project, path = owned
    (path / "feature").write_text("published")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    head = git(path, "rev-parse", "HEAD")
    (project.root / "feature").write_text("published")
    git(project.root, "add", "feature")
    git(project.root, "commit", "-qm", "squashed feature")
    published = cleanup.Published(project)
    assert head not in published.commits
    assert git(path, "rev-parse", "HEAD^{tree}") == published.tree
    assert clean(owned)["removed"] == ["candidate"]


def test_busy_worktree_removal_error_is_reported(owned, monkeypatch):
    _, _, path = owned

    def busy(*args, **kwargs):
        raise worktrunk.WorktrunkError("checkout is busy")

    monkeypatch.setattr(worktrunk, "worktrunk_remove", busy)
    result = clean(owned)
    assert result["kept"] == [{"branch": "candidate", "reason": "checkout is busy"}]
    assert not result["removed"] and path.is_dir()


@pytest.mark.parametrize("state", ["Queued", "Running", "Paused"])
@pytest.mark.parametrize("nested", [False, True])
def test_unfinished_queue_job_keeps_published_checkout(
    owned, fake_pueue, state, nested
):
    from dataclasses import replace

    _, _, path = owned
    working_directory = path / "build" if nested else path
    task_id = fake_pueue.add(
        group="normal",
        label="fixture:build",
        command=["agentctl-run", "/state/inputs/job.json"],
        working_directory=working_directory,
    )
    fake_pueue._tasks[task_id] = replace(fake_pueue._tasks[task_id], status=state)
    result = clean(owned)
    assert not result["removed"] and path.is_dir()
    assert result["kept"] == [
        {
            "branch": "candidate",
            "reason": f"unfinished job: task {task_id} 'fixture:build' {state.lower()} cwd {working_directory}",
        }
    ]


def test_ignored_files_are_removed_with_published_checkout(owned):
    _, _, path = owned
    (path / "ignored-output.bin").write_bytes(b"disposable output")
    result = clean(owned)
    assert result["removed"] == ["candidate"] and not result["kept"]
    assert not path.exists()
