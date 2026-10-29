from __future__ import annotations

import io
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest
from sinnix_agent_gateway import projects as projects_module
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.projects import ProjectError, ProjectService


def git(path: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), *arguments], check=True, capture_output=True
    )


def project_service(tmp_path: Path) -> tuple[ProjectService, Path, Path]:
    project = tmp_path / "project"
    linked = tmp_path / "linked"
    project.mkdir()
    git(project, "init", "--quiet")
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "user.email", "fixture@example.invalid")
    (project / "README.md").write_text("fixture\n")
    git(project, "add", "README.md")
    git(project, "commit", "--quiet", "-m", "initial fixture")
    git(project, "worktree", "add", "--quiet", "-b", "fixture-linked", str(linked))
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
    )
    return ProjectService(config), project, linked


def test_project_checkouts_are_git_derived_and_explicit(tmp_path: Path) -> None:
    projects, project, linked = project_service(tmp_path)

    rows = projects.checkouts("fixture")["checkouts"]

    assert len(rows) == 2
    assert rows[0]["checkout_id"] == "default"
    assert rows[0]["path"] == str(project)
    assert rows[0]["head"] == git_stdout(project, "rev-parse", "HEAD")
    assert rows[0]["branch"] == "master"
    assert rows[0]["upstream"] is None
    assert len(rows[0]["dirty_sha256"]) == 64
    assert rows[0]["lifecycle"] == "configured-default"
    assert rows[1]["checkout_id"].startswith("worktree-")
    assert rows[1]["path"] == str(linked)
    assert rows[1]["branch"] == "fixture-linked"
    assert rows[1]["lifecycle"] == "linked-worktree"
    assert projects.checkout("fixture", rows[1]["checkout_id"])["checkout"] == rows[1]


def test_read_only_project_views_do_not_run_repository_fsmonitor(
    tmp_path: Path,
) -> None:
    projects, project, _linked = project_service(tmp_path)
    marker = tmp_path / "fsmonitor-ran"
    hook = tmp_path / "fsmonitor"
    hook.write_text(f"#!/bin/sh\nprintf invoked >> '{marker}'\nprintf 'token\\0'\n")
    hook.chmod(0o700)
    git(project, "config", "core.fsmonitor", str(hook))
    git(project, "status", "--porcelain")
    assert marker.exists(), "fixture must demonstrate native fsmonitor invocation"
    marker.unlink()

    observer = ProjectService(projects.config)
    assert observer.summary("fixture")["branch"]["head"] == "master"
    assert observer.checkouts("fixture")["checkouts"]
    assert not marker.exists()


def test_worktree_porcelain_accepts_valueless_git_markers() -> None:
    records = ProjectService._worktree_records(
        "worktree /fixture\0HEAD 0123456789abcdef\0bare\0detached\0locked\0prunable\0\0"
    )

    assert records == [
        {
            "worktree": "/fixture",
            "HEAD": "0123456789abcdef",
            "bare": "",
            "detached": "",
            "locked": "",
            "prunable": "",
        }
    ]


def test_project_mutation_uses_configured_default_with_linked_checkout(
    tmp_path: Path,
) -> None:
    projects, _project, linked = project_service(tmp_path)
    operator = ProjectService(projects.config)
    linked_checkout = operator.checkouts("fixture")["checkouts"][1]["checkout_id"]

    operator.write("fixture", "operator.txt", "default")

    operator.write("fixture", "operator.txt", "selected", linked_checkout)

    assert (_project / "operator.txt").read_text() == "default"
    assert (linked / "operator.txt").read_text() == "selected"


@pytest.mark.parametrize("operation", ["write", "apply_patch"])
def test_project_mutation_publishes_through_pinned_parent_when_replaced_by_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    _observer, project, _linked = project_service(tmp_path)
    operator = ProjectService(_observer.config)
    safe_parent = project / "safe"
    safe_parent.mkdir()
    target = safe_parent / "tracked.txt"
    target.write_text("before\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_target = outside / "tracked.txt"
    outside_target.write_text("outside\n")
    moved_parent = project / "safe-real"

    original_open = projects_module._open_pinned_directory
    replaced = False

    def hostile_open(
        config: ProjectConfig, parts: tuple[str, ...], *, create: bool
    ) -> int:
        nonlocal replaced
        descriptor = original_open(config, parts, create=create)
        if not replaced and parts == ("safe",):
            safe_parent.rename(moved_parent)
            safe_parent.symlink_to(outside, target_is_directory=True)
            replaced = True
        return descriptor

    monkeypatch.setattr(projects_module, "_open_pinned_directory", hostile_open)
    if operation == "write":
        operator.write("fixture", "safe/tracked.txt", "after\n", "default")
    else:
        operator.apply_patch(
            "fixture",
            """diff --git a/safe/tracked.txt b/safe/tracked.txt
--- a/safe/tracked.txt
+++ b/safe/tracked.txt
@@ -1 +1 @@
-before
+after
""",
            "default",
        )

    assert replaced is True
    assert outside_target.read_text() == "outside\n"
    assert (moved_parent / "tracked.txt").read_text() == "after\n"


def test_project_write_cleans_collision_safe_temporary_after_publication_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _observer, project, _linked = project_service(tmp_path)
    operator = ProjectService(_observer.config)

    def fail_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("injected publication failure")

    monkeypatch.setattr(projects_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected publication failure"):
        operator.write("fixture", "failure.txt", "must not publish", "default")

    assert list(project.glob(".*.gateway-tmp-*")) == []
    assert not (project / "failure.txt").exists()


def test_project_write_syncs_file_and_parent_directory_before_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _observer, project, _linked = project_service(tmp_path)
    operator = ProjectService(_observer.config)
    original_fsync = projects_module.os.fsync
    synced_kinds: list[str] = []

    def recording_fsync(descriptor: int) -> None:
        mode = projects_module.os.fstat(descriptor).st_mode
        synced_kinds.append("directory" if stat.S_ISDIR(mode) else "file")
        original_fsync(descriptor)

    monkeypatch.setattr(projects_module.os, "fsync", recording_fsync)
    operator.write("fixture", "durable/result.txt", "published", "default")

    assert (project / "durable" / "result.txt").read_text() == "published"
    assert "file" in synced_kinds
    assert synced_kinds.count("directory") >= 2


def test_gateway_temporary_artifacts_are_excluded_from_project_apis(
    tmp_path: Path,
) -> None:
    _observer, project, _linked = project_service(tmp_path)
    observer = ProjectService(_observer.config)
    temporary = project / ".tracked.gateway-tmp-fixture"
    temporary.write_text("private temporary\n")

    with pytest.raises(ProjectError, match="excluded by project policy"):
        observer.read("fixture", temporary.name, checkout_id="default")
    assert all(
        row["path"] != temporary.name for row in observer.tree("fixture")["entries"]
    )
    assert observer.search("fixture", "private temporary")["matches"] == []


@pytest.mark.parametrize("dirty", [False, True])
def test_project_patch_rename_removes_source_without_ingesting_ignored_files(
    tmp_path: Path,
    dirty: bool,
) -> None:
    _observer, project, _linked = project_service(tmp_path)
    operator = ProjectService(_observer.config)
    source = project / "old.txt"
    source.write_text("tracked\n")
    git(project, "add", "old.txt")
    git(project, "commit", "--quiet", "-m", "tracked rename source")
    expected = "uncommitted work\n" if dirty else "tracked\n"
    source.write_text(expected)
    ignored = project / "private.payload"
    ignored.write_text("must never enter the object database")
    (project / ".gitignore").write_text("private.payload\n")
    private_object = git_stdout(project, "hash-object", "private.payload")

    operator.apply_patch(
        "fixture",
        """diff --git a/old.txt b/new.txt
similarity index 100%
rename from old.txt
rename to new.txt
""",
        "default",
    )

    assert not source.exists()
    assert (project / "new.txt").read_text() == expected
    assert ignored.read_text() == "must never enter the object database"
    assert (
        subprocess.run(
            ["git", "-C", str(project), "cat-file", "-e", private_object],
            check=False,
            capture_output=True,
        ).returncode
        != 0
    )


def test_failed_rename_destination_keeps_the_dirty_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer, project, _linked = project_service(tmp_path)
    operator = ProjectService(observer.config)
    source = project / "a.txt"
    source.write_text("committed\n")
    git(project, "add", "a.txt")
    git(project, "commit", "--quiet", "-m", "rename fixture")
    source.write_text("uncommitted work\n")
    publish = operator._publish_index_entry

    def fail_destination(project_config, relative, entry, **kwargs):
        if relative == "z.txt":
            raise ProjectError("synthetic destination failure")
        return publish(project_config, relative, entry, **kwargs)

    monkeypatch.setattr(operator, "_publish_index_entry", fail_destination)
    with pytest.raises(ProjectError, match="synthetic destination failure"):
        operator.apply_patch(
            "fixture",
            """diff --git a/a.txt b/z.txt
similarity index 100%
rename from a.txt
rename to z.txt
""",
            "default",
        )
    assert source.read_text() == "uncommitted work\n"
    assert not (project / "z.txt").exists()


def git_stdout(path: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.parametrize("operation", ["export", "content_revision"])
def test_project_sources_refuse_symlinked_parent(
    tmp_path: Path, operation: str
) -> None:
    projects, project, _linked = project_service(tmp_path)
    nested = project / "nested"
    nested.mkdir()
    (nested / "data.txt").write_text("tracked fixture\n")
    git(project, "add", "nested/data.txt")
    git(project, "commit", "--quiet", "-m", "nested fixture")
    nested.rename(tmp_path / "original")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data.txt").write_text("outside fixture\n")
    nested.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ProjectError, match="symlink"):
        if operation == "content_revision":
            projects_module._content_revision(project)
        else:
            projects.export("fixture")
    assert not list((tmp_path / "state" / "captures").glob("*/project-export.zip"))


def test_project_export_preserves_leaf_symlink_payload(tmp_path: Path) -> None:
    projects, project, _linked = project_service(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside fixture\n")
    (project / "link.txt").symlink_to(outside)
    result = projects.export("fixture", mode="tracked+untracked")
    with (
        zipfile.ZipFile(result["archive"]) as bundle,
        zipfile.ZipFile(io.BytesIO(bundle.read("extras.zip"))) as extras,
    ):
        assert extras.read("link.txt") == str(outside).encode()
        assert stat.S_ISLNK(extras.getinfo("link.txt").external_attr >> 16)


def test_project_sources_allow_deleted_parent(tmp_path: Path) -> None:
    projects, project, _linked = project_service(tmp_path)
    nested = project / "nested"
    nested.mkdir()
    (nested / "data.txt").write_text("fixture\n")
    git(project, "add", "nested/data.txt")
    git(project, "commit", "--quiet", "-m", "nested fixture")
    (nested / "data.txt").unlink()
    nested.rmdir()
    assert projects_module._content_revision(project)
    result = projects.export("fixture")
    restored = tmp_path / "restored"
    restored.mkdir()
    patch = tmp_path / "working-tree.patch"
    with zipfile.ZipFile(result["archive"]) as bundle:
        with zipfile.ZipFile(io.BytesIO(bundle.read("HEAD.zip"))) as head:
            assert head.read("nested/data.txt") == b"fixture\n"
            head.extractall(restored)
        patch.write_bytes(bundle.read("working-tree.patch"))
    git(restored, "init", "--quiet")
    git(restored, "apply", "--binary", str(patch))
    assert not (restored / "nested" / "data.txt").exists()


def test_project_source_read_pins_parent_during_replacement(
    tmp_path: Path, monkeypatch
) -> None:
    _projects, project, _linked = project_service(tmp_path)
    nested = project / "nested"
    nested.mkdir()
    (nested / "data.txt").write_text("fixture\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data.txt").write_text("outside fixture\n")
    original = projects_module._open_source_file

    def replace_parent(path):
        nested.rename(tmp_path / "original")
        nested.symlink_to(outside, target_is_directory=True)
        return original(path)

    monkeypatch.setattr(projects_module, "_open_source_file", replace_parent)
    with (
        projects_module._source_path(project, Path("nested/data.txt")) as path,
        projects_module._open_source_file(path) as handle,
    ):
        assert handle.read() == b"fixture\n"


def test_project_source_read_refuses_leaf_replaced_with_symlink(tmp_path: Path) -> None:
    _projects, project, _linked = project_service(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside fixture\n")
    with projects_module._source_path(project, Path("README.md")) as path:
        (project / "README.md").unlink()
        (project / "README.md").symlink_to(outside)
        with pytest.raises(ProjectError, match="changed or is unavailable"):
            projects_module._open_source_file(path)


def test_project_read_refuses_parent_replaced_after_path_check(
    tmp_path: Path, monkeypatch
) -> None:
    projects, project, _linked = project_service(tmp_path)
    nested = project / "nested"
    nested.mkdir()
    (nested / "data.txt").write_text("fixture\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data.txt").write_text("outside fixture\n")
    original = projects._safe_path

    def replace_parent(*args, **kwargs):
        target = original(*args, **kwargs)
        nested.rename(tmp_path / "original")
        nested.symlink_to(outside, target_is_directory=True)
        return target

    monkeypatch.setattr(projects, "_safe_path", replace_parent)
    with pytest.raises(ProjectError, match="symlink"):
        projects._read_file(
            projects.config.projects["fixture"], "nested/data.txt", 1, None, 1024
        )


@pytest.mark.parametrize("replacement", ["other_repository", "repository_subdirectory"])
def test_registered_checkout_replaced_by_symlink_is_not_authorized(
    tmp_path: Path, replacement: str
) -> None:
    projects, project, linked = project_service(tmp_path)
    checkout_id = next(
        row["checkout_id"]
        for row in projects.checkouts("fixture")["checkouts"]
        if row["path"] == str(linked)
    )
    if replacement == "other_repository":
        target = tmp_path / "other-repository"
        target.mkdir()
        git(target, "init", "--quiet")
        git(target, "config", "user.name", "Fixture")
        git(target, "config", "user.email", "fixture@example.invalid")
        (target / "README.md").write_text("other repository fixture\n")
        git(target, "add", ".")
        git(target, "commit", "--quiet", "-m", "other fixture")
    else:
        target = project / "nested"
        target.mkdir()
        (target / "README.md").write_text("subdirectory fixture\n")
    linked.rename(tmp_path / "preserved-linked")
    linked.symlink_to(target, target_is_directory=True)
    # Native Git still advertises the original registration in both cases.
    assert str(linked) in git_stdout(project, "worktree", "list", "--porcelain")
    candidates = projects.checkout_candidates("fixture")
    assert [row["path"] for row in candidates] == [str(project)]
    with pytest.raises(ProjectError, match="unknown configured checkout"):
        projects.code_checkout(
            "fixture", checkout_id, write=False, require_explicit=False
        )


@pytest.mark.parametrize("rename", [False, True])
def test_small_patch_of_large_dirty_file_does_not_use_response_budget(tmp_path, rename):
    operator, project, _linked = project_service(tmp_path)
    source = project / "large.txt"
    payload = ("multibyte λ evidence\n" * 180_000).encode()
    source.write_bytes(b"before\n" + payload)
    source.chmod(0o755)
    git(project, "add", "large.txt")
    git(project, "commit", "--quiet", "-m", "large fixture")
    dirty = source.read_bytes() + b"uncommitted tail\n"
    source.write_bytes(dirty)
    assert len(dirty) > operator.config.max_result_bytes
    original_index = git_stdout(project, "write-tree")
    if rename:
        patch = "diff --git a/large.txt b/renamed.txt\nsimilarity index 100%\nrename from large.txt\nrename to renamed.txt\n"
        expected = dirty
        target = project / "renamed.txt"
    else:
        patch = "diff --git a/large.txt b/large.txt\n--- a/large.txt\n+++ b/large.txt\n@@ -1,4 +1,4 @@\n-before\n+after\n multibyte λ evidence\n multibyte λ evidence\n multibyte λ evidence\n"
        expected = b"after\n" + dirty[len(b"before\n") :]
        target = source
    operator.apply_patch("fixture", patch, "default")
    assert target.read_bytes() == expected
    assert target.stat().st_mode & 0o777 == 0o755
    assert git_stdout(project, "write-tree") == original_index
    if rename:
        assert not source.exists()


def test_blob_spooling_failure_preserves_working_file(tmp_path, monkeypatch):
    operator, project, _linked = project_service(tmp_path)
    source = project / "README.md"
    before = source.read_bytes()

    def fail_spool(*args, **kwargs):
        raise OSError("synthetic disk full")

    monkeypatch.setattr(operator, "_index_blob", fail_spool)
    with pytest.raises(OSError, match="disk full"):
        operator.apply_patch(
            "fixture",
            "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-fixture\n+changed\n",
            "default",
        )
    assert source.read_bytes() == before


def test_patch_path_metadata_streams_across_frames_without_losing_names(
    tmp_path, monkeypatch
):
    operator, project, _linked = project_service(tmp_path)
    names = [f"f{i:04d}-" + "λ" * 45 + ".txt" for i in range(700)]
    patch = "".join(
        f"diff --git a/{name} b/{name}\nnew file mode 100644\nindex 0000000..e69de29\n"
        for name in names
    )
    assert len(patch.encode()) < operator.config.max_result_bytes
    assert sum(len(name.encode()) + 5 for name in names) > 64_000
    original_index = git_stdout(project, "write-tree")
    read_blobs = []
    original_result = operator._owner_result

    def record_blob(command, *args, **kwargs):
        if command[:3] == ["git", "cat-file", "blob"]:
            read_blobs.append(command[3])
        return original_result(command, *args, **kwargs)

    monkeypatch.setattr(operator, "_owner_result", record_blob)
    operator.apply_patch("fixture", patch, "default")
    assert len(read_blobs) == 1
    assert sorted(path.name for path in project.glob("f*.txt")) == names
    assert all((project / name).read_bytes() == b"" for name in names)
    assert git_stdout(project, "write-tree") == original_index


@pytest.mark.parametrize(
    "name",
    [
        'literal"quote',
        "literal\ttab",
        "literal\nline",
        "literal\rcarriage",
        "literal-żółć",
    ],
)
def test_checkout_discovery_preserves_literal_worktree_paths(tmp_path, name):
    projects, project, _linked = project_service(tmp_path)
    special = tmp_path / name
    git(project, "worktree", "add", "--quiet", "-b", "fixture-special", str(special))
    rows = projects.checkouts("fixture")["checkouts"]
    matching = [row for row in rows if row["path"] == str(special)]
    assert len(matching) == 1
    assert matching[0]["branch"] == "fixture-special"
    assert projects.checkout("fixture", matching[0]["checkout_id"])["checkout"][
        "path"
    ] == str(special)


@pytest.mark.parametrize(
    "output",
    [
        "worktree /fixture\nHEAD abc\n\n",
        "worktree /fixture\0HEAD abc\0",
        "worktree /fixture\0HEAD abc\0HEAD duplicate\0\0",
        "worktree /fixture\0unknown-marker\0\0",
    ],
)
def test_worktree_inventory_refuses_malformed_or_incomplete_nul_records(output):
    with pytest.raises(ProjectError, match="porcelain"):
        ProjectService._worktree_records(output)


def test_non_utf8_worktree_inventory_is_unavailable_not_substituted(tmp_path):
    import os

    projects, project, _linked = project_service(tmp_path)
    special = tmp_path / os.fsdecode(b"invalid-\xff")
    git(project, "worktree", "add", "--quiet", "-b", "fixture-special", str(special))
    with pytest.raises(ProjectError, match="not valid UTF-8"):
        projects.checkouts("fixture")
