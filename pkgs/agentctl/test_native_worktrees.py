"""Native cleanup is driven by publication and custody, never branch spelling."""

import json
import subprocess
from pathlib import Path

import pytest
from agentctl import native_worktrees as native
from agentctl import worktree_cleanup as cleanup
from agentctl import worktrunk
from test_cleanup_hidden import checkout as checkout
from test_cleanup_hidden import git


@pytest.fixture
def owned(checkout, fake_pueue, monkeypatch):
    config, project, path = checkout
    monkeypatch.setattr(
        native,
        "_owners",
        lambda *_: {
            path: {"terminal": True, "heads": {git(path, "rev-parse", "HEAD")}}
        },
    )
    monkeypatch.setattr(native.github, "gh_json", lambda *a, **k: [])
    monkeypatch.setattr(
        native.worktree_processes, "users", lambda paths: {p: [] for p in paths}
    )
    return config, project, path


def cache(path):
    target = path / "target"
    target.mkdir()
    (target / "CACHEDIR.TAG").write_bytes(native.CACHE_TAG + b"\n")
    (target / "compiled").write_bytes(b"disposable synthetic output")
    # A real Git ignore, with no uncommitted source change.
    common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    with open(common + "/info/exclude", "a") as f:
        f.write("\ntarget/\n")
    return target


def clean(owned):
    return native.clean_native(owned[0], owned[1])


def test_native_ancestor_removes_checkout_cache_and_branch_with_recovery(owned):
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


def test_squash_plus_unrelated_default_change_is_subsumed(owned):
    _, project, path = owned
    (path / "feature").write_text("published\n")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    head = git(path, "rev-parse", "HEAD")
    (project.root / "feature").write_text("published\n")
    (project.root / "other").write_text("other\n")
    git(project.root, "add", ".")
    git(project.root, "commit", "-qm", "squash and independent work")
    assert head not in native.Published(project).commits
    assert git(path, "rev-parse", "HEAD^{tree}") not in native.Published(project).trees
    assert clean(owned)["removed"] == ["candidate"]


def test_unique_unpublished_change_is_kept(owned):
    _, _, path = owned
    (path / "feature").write_text("unpublished\n")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    result = clean(owned)
    assert (
        not result["removed"]
        and result["kept"][0]["reason"] == "publication not proved"
    )
    assert (path / "feature").read_text() == "unpublished\n"


@pytest.mark.parametrize("kind", ["dirty", "ignored", "locked", "holder", "active"])
def test_native_custody_keeps_work_and_cache(owned, monkeypatch, kind):
    _, project, path = owned
    target = cache(path)
    if kind == "dirty":
        (path / "tracked.txt").write_text("unsaved")
    elif kind == "ignored":
        (path / "ignored-private").write_text("private")
    elif kind == "locked":
        trees = (
            worktrunk.Worktree("master", project.root, True),
            worktrunk.Worktree("candidate", path, locked=True),
        )
        monkeypatch.setattr(worktrunk, "worktrunk_list", lambda _: trees)
    elif kind == "holder":
        monkeypatch.setattr(
            native.worktree_processes,
            "users",
            lambda paths: {p: ["mapped executable"] for p in paths},
        )
    else:
        monkeypatch.setattr(
            native, "_owners", lambda *_: {path: {"terminal": False, "heads": set()}}
        )
    result = clean(owned)
    assert not result["removed"] and result["kept"]
    assert (target / "compiled").read_bytes() == b"disposable synthetic output"


def test_target_only_remnant_uses_retained_owner_and_does_not_scan_cache(
    owned, monkeypatch
):
    _, project, path = owned
    head = git(path, "rev-parse", "HEAD")
    git(project.root, "worktree", "remove", str(path))
    path.mkdir()
    cache_dir = path / "target"
    cache_dir.mkdir()
    (cache_dir / "CACHEDIR.TAG").write_bytes(native.CACHE_TAG + b"\n")
    (cache_dir / "compiled").write_bytes(b"output")
    monkeypatch.setattr(
        native, "_owners", lambda *_: {path: {"terminal": True, "heads": {head}}}
    )
    monkeypatch.setattr(
        worktrunk,
        "worktrunk_list",
        lambda _: (worktrunk.Worktree("master", project.root, True),),
    )
    assert clean(owned)["removed"] == [str(path)]
    assert not path.exists()


def test_retained_invocation_binds_ownership_and_unknown_outcome_keeps_it(checkout):
    config, project, path = checkout
    config.inputs_dir.mkdir(parents=True)
    config.jobs_dir.mkdir(parents=True)
    doc = {
        "project_id": project.project_id,
        "working_directory": str(path),
        "log_path": str(config.jobs_dir / "fixture.log"),
    }
    (config.inputs_dir / (project.project_id + "-fixture.json")).write_text(
        json.dumps(doc)
    )
    output = config.jobs_dir / "fixture.outcome"
    output.write_text(
        json.dumps(
            {
                "execution_receipt": {
                    "end": {
                        "status": "observed",
                        "head": git(path, "rev-parse", "HEAD"),
                    }
                }
            }
        )
    )
    owner = native._owners(config, project, {})[path]
    assert owner["terminal"] and owner["heads"]
    output.unlink()
    assert not native._owners(config, project, {})[path]["terminal"]
    disposition = native.job_queries.disposition_path(
        config.inputs_dir / (project.project_id + "-fixture.json")
    )
    disposition.write_text(json.dumps({"outcome": "cancelled", "started": False}))
    assert native._owners(config, project, {})[path]["terminal"]
    disposition.write_text(json.dumps({"outcome": "cancelled", "unresolved": True}))
    assert not native._owners(config, project, {})[path]["terminal"]


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
    (target / "CACHEDIR.TAG").write_bytes(native.CACHE_TAG + b"\n")
    (target / "object").write_bytes(b"compiled")
    other = root / "untouched"
    other.mkdir()
    (other / "private").write_bytes(b"other cache")
    monkeypatch.setenv("SINNIX_CARGO_CACHE_ROOT", str(root))
    result = clean(owned)
    assert (
        result["removed"] == ["candidate"] and not path.exists() and not parent.exists()
    )
    assert (other / "private").read_bytes() == b"other cache"


def test_external_cache_holder_preserves_checkout_and_output(
    owned, monkeypatch, tmp_path
):
    import hashlib
    import os

    _, _, path = owned
    root = tmp_path / "cache"
    target = (
        root
        / str(os.getuid())
        / hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]
        / "target"
    )
    target.mkdir(parents=True)
    (target / "CACHEDIR.TAG").write_bytes(native.CACHE_TAG + b"\n")
    monkeypatch.setenv("SINNIX_CARGO_CACHE_ROOT", str(root))
    monkeypatch.setattr(
        native.worktree_processes,
        "users",
        lambda paths: {
            p: (["mapped compiler output"] if p == target else []) for p in paths
        },
    )
    assert clean(owned)["kept"] and path.exists() and target.exists()


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

    def pulls(*args, **kwargs):
        calls.append(args)
        return [{"headRefOid": head, "mergeCommit": {"oid": base}}]

    monkeypatch.setattr(native.github, "gh_json", pulls)
    proof = native.Published(project)
    assert proof.contains(head) and proof.contains(head) and len(calls) == 1
    (path / "later").write_text("unpublished")
    git(path, "add", "later")
    git(path, "commit", "-qm", "later")
    assert not proof.contains(git(path, "rev-parse", "HEAD"))


def test_holder_census_is_fresh_after_artifact_preservation(owned, monkeypatch):
    _, _, path = owned
    calls = []

    def users(paths):
        calls.append(paths)
        return {p: (["new holder"] if len(calls) == 2 else []) for p in paths}

    monkeypatch.setattr(native.worktree_processes, "users", users)
    result = clean(owned)
    assert len(calls) == 2 and result["kept"] and path.exists()


def test_target_alias_from_another_checkout_pins_the_cache(
    owned, monkeypatch, tmp_path
):
    _, project, path = owned
    cache(path)
    other = tmp_path / "other-owner"
    other.mkdir()
    (other / "target").symlink_to(path / "target", target_is_directory=True)
    trees = (
        worktrunk.Worktree("master", project.root, True),
        worktrunk.Worktree("candidate", path),
        worktrunk.Worktree("other", other),
    )
    monkeypatch.setattr(worktrunk, "worktrunk_list", lambda _: trees)
    result = clean(owned)
    assert result["kept"] and "target alias" in result["kept"][0]["reason"]
    assert (path / "target/compiled").exists()


def test_a_new_commit_after_publication_proof_is_not_removed(owned, monkeypatch):
    _, _, path = owned
    preserve = native._preserve_artifacts

    def changed(*args, **kwargs):
        result = preserve(*args, **kwargs)
        (path / "new-work").write_text("unpublished")
        git(path, "add", "new-work")
        git(path, "commit", "-qm", "new work")
        return result

    monkeypatch.setattr(native, "_preserve_artifacts", changed)
    result = clean(owned)
    assert result["kept"] and (path / "new-work").read_text() == "unpublished"


def test_live_native_job_target_argument_pins_a_different_checkout(
    owned, monkeypatch, tmp_path
):
    from types import SimpleNamespace

    _, _, path = owned
    cache(path)
    task = SimpleNamespace(
        terminal=False, task_id=7, path=str(tmp_path / "elsewhere"), status="Running"
    )
    monkeypatch.setattr(native.pueue, "tasks", lambda: {7: task})
    monkeypatch.setattr(
        native.job_queries,
        "read_launch_input",
        lambda *_: {
            "argv": ["env", "CARGO_TARGET_DIR=" + str(path / "target"), "cargo", "test"]
        },
    )
    result = clean(owned)
    assert result["kept"] and "active job 7" in result["kept"][0]["reason"]
    assert (path / "target/compiled").exists()


def test_cache_tag_survives_interrupted_child_removal(owned, monkeypatch):
    _, _, path = owned
    target = cache(path)
    (target / "objects").mkdir()
    (target / "objects/object").write_bytes(b"cache")
    remove = cleanup.shutil.rmtree

    def interrupted(child, *args, **kwargs):
        if child == target / "objects":
            raise KeyboardInterrupt()
        return remove(child, *args, **kwargs)

    monkeypatch.setattr(cleanup.shutil, "rmtree", interrupted)
    with pytest.raises(KeyboardInterrupt):
        cleanup._remove_cache(target)
    assert (target / "CACHEDIR.TAG").read_bytes().startswith(native.CACHE_TAG)
    assert cleanup._cargo_cache(path, registered=True) == target
    monkeypatch.setattr(cleanup.shutil, "rmtree", remove)
    cleanup._remove_cache(target)
    assert not target.exists()


def test_declared_native_executable_is_retained_before_cache_retirement(owned):
    from dataclasses import replace

    config, project, path = owned
    target = cache(path)
    exe = target / "proof"
    exe.write_bytes(b"synthetic executable")
    exe.chmod(0o755)
    project = replace(
        project,
        workspace=replace(project.workspace, retain_artifacts=("target/proof",)),
    )
    result = native.clean_native(config, project)
    assert result["removed"] == ["candidate"]
    destination = next(
        row["destination"] for row in result["artifacts"] if row["source"] == str(exe)
    )
    assert Path(destination).read_bytes() == b"synthetic executable"


def test_generic_compiled_executable_is_not_a_permanent_pin(owned):
    _, _, path = owned
    target = cache(path)
    exe = target / "package"
    exe.write_bytes(b"compiler output")
    exe.chmod(0o755)
    assert clean(owned)["removed"] == ["candidate"]


def test_native_junit_report_survives_source_and_cache_retirement(owned):
    config, _, path = owned
    target = cache(path)
    report = target / "nextest/default/devkit-junit.xml"
    report.parent.mkdir(parents=True)
    report.write_text("<testsuites/>")
    result = clean(owned)
    assert result["removed"] == ["candidate"]
    destination = next(
        row["destination"]
        for row in result["artifacts"]
        if row["source"] == str(report)
    )
    assert Path(destination).read_text() == "<testsuites/>"


def test_bulk_forge_precedes_optional_blob_merging(owned, monkeypatch):
    _, project, path = owned
    (path / "feature").write_text("candidate")
    git(path, "add", "feature")
    git(path, "commit", "-qm", "feature")
    head = git(path, "rev-parse", "HEAD")
    base = git(project.root, "rev-parse", "HEAD")
    original = native._git

    def refuse_merge(root, *args, **kwargs):
        if args[0] in ("merge-tree", "merge-base"):
            raise AssertionError("forge proof must avoid optional merge")
        return original(root, *args, **kwargs)

    monkeypatch.setattr(native, "_git", refuse_merge)
    monkeypatch.setattr(
        native.github,
        "gh_json",
        lambda *a, **k: [{"headRefOid": head, "mergeCommit": {"oid": base}}],
    )
    assert native.Published(project).contains(head)


def test_empty_untracked_source_directories_do_not_hold_a_completed_checkout(owned):
    _, _, path = owned
    (path / "src/retired/module").mkdir(parents=True)
    assert clean(owned)["removed"] == ["candidate"]


def test_shared_holder_census_sees_a_mapping_after_its_descriptor_closed(
    tmp_path, monkeypatch
):
    import sys

    from agentctl import worktree_processes

    root = tmp_path / "checkout"
    root.mkdir()
    value = root / "mapped"
    value.write_bytes(b"neutral mapped fixture")
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            'import mmap,sys; f=open(sys.argv[1],"rb"); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ); f.close(); print("ready",flush=True); sys.stdin.read()',
            str(value),
        ],
        cwd=tmp_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        original = Path.iterdir
        monkeypatch.setattr(
            Path,
            "iterdir",
            lambda path: (
                iter([Path("/proc") / str(child.pid)])
                if path == Path("/proc")
                else original(path)
            ),
        )
        users = worktree_processes.users([root])
        assert any("mapping" in user for user in users[root])
    finally:
        child.communicate("", timeout=5)


def test_lock_acquired_during_preservation_prevents_cache_retirement(
    owned, monkeypatch
):
    _, project, path = owned
    target = cache(path)
    calls = []

    def trees(_):
        calls.append(1)
        return (
            worktrunk.Worktree("master", project.root, True),
            worktrunk.Worktree("candidate", path, locked=len(calls) > 1),
        )

    monkeypatch.setattr(worktrunk, "worktrunk_list", trees)
    result = clean(owned)
    assert result["kept"] and (target / "compiled").exists()


def test_explicit_path_can_retire_authors_registered_foreground_only_checkout(
    owned, monkeypatch, tmp_path
):
    config, project, path = owned
    other = tmp_path / "other-checkout"
    git(project.root, "worktree", "add", "-qb", "other", str(other), "master")
    monkeypatch.setattr(native, "_owners", lambda *_: {})
    result = native.clean_native(config, project, {path})
    assert result["removed"] == ["candidate"] and not path.exists() and other.exists()


def test_explicit_path_does_not_override_unavailable_job_evidence(owned, monkeypatch):
    config, project, path = owned
    monkeypatch.setattr(
        native, "_owners", lambda *_: {path: {"terminal": False, "heads": set()}}
    )
    result = native.clean_native(config, project, {path})
    assert result["kept"] and path.exists()


def test_ignored_python_bytecode_is_disposable_but_other_bytes_are_kept(owned):
    import importlib.util

    config, project, path = owned
    common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    with open(common + "/info/exclude", "a") as handle:
        handle.write("\n__pycache__/\n")
    output = path / "__pycache__"
    output.mkdir()
    (output / "module.cpython-314.pyc").write_bytes(
        importlib.util.MAGIC_NUMBER + b"\0" * 12
    )
    valuable = output / "private.txt"
    valuable.write_text("unpublished bytes")
    assert clean(owned)["kept"] and valuable.read_text() == "unpublished bytes"
    valuable.unlink()
    assert clean(owned)["removed"] == ["candidate"]


def test_tagged_ignored_tool_cache_is_disposable(owned):
    _, _, path = owned
    common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    with open(common + "/info/exclude", "a") as handle:
        handle.write("\n.ruff_cache/\n")
    output = path / ".ruff_cache"
    output.mkdir()
    (output / "CACHEDIR.TAG").write_bytes(native.CACHE_TAG)
    (output / "compiler-state").write_bytes(b"derived cache")
    assert clean(owned)["removed"] == ["candidate"]
