from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest
from sinnix_agent_gateway import projects as projects_module
from sinnix_agent_gateway.capabilities import Principal
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
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
    )
    return ProjectService(config, Principal.for_name("observer")), project, linked


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
    assert rows[0]["lifecycle"] == "configured-root"
    assert rows[1]["checkout_id"].startswith("worktree-")
    assert rows[1]["path"] == str(linked)
    assert rows[1]["branch"] == "fixture-linked"
    assert rows[1]["lifecycle"] == "linked-worktree"
    assert projects.checkout("fixture", rows[1]["checkout_id"])["checkout"] == rows[1]


def test_worktree_porcelain_accepts_valueless_git_markers() -> None:
    records = ProjectService._worktree_records(
        """worktree /fixture
HEAD 0123456789abcdef
bare
detached
locked
prunable

"""
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


def test_project_mutation_requires_an_explicit_checkout_when_ambiguous(
    tmp_path: Path,
) -> None:
    projects, _project, linked = project_service(tmp_path)
    operator = ProjectService(projects.config, Principal.for_name("operator"))
    linked_checkout = operator.checkouts("fixture")["checkouts"][1]["checkout_id"]

    with pytest.raises(ProjectError, match="checkout_id is required"):
        operator.write("fixture", "operator.txt", "not selected")

    operator.write("fixture", "operator.txt", "selected", linked_checkout)

    assert (linked / "operator.txt").read_text() == "selected"


@pytest.mark.parametrize("operation", ["write", "apply_patch"])
def test_project_mutation_publishes_through_pinned_parent_when_replaced_by_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    _observer, project, _linked = project_service(tmp_path)
    operator = ProjectService(_observer.config, Principal.for_name("operator"))
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
    operator = ProjectService(_observer.config, Principal.for_name("operator"))

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
    operator = ProjectService(_observer.config, Principal.for_name("operator"))
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
    observer = ProjectService(_observer.config, Principal.for_name("observer"))
    temporary = project / ".tracked.gateway-tmp-fixture"
    temporary.write_text("private temporary\n")

    with pytest.raises(ProjectError, match="excluded by project policy"):
        observer.read("fixture", temporary.name, checkout_id="default")
    assert all(
        row["path"] != temporary.name for row in observer.tree("fixture")["entries"]
    )
    assert observer.search("fixture", "private temporary")["matches"] == []


def test_project_patch_rename_removes_source_without_ingesting_ignored_files(
    tmp_path: Path,
) -> None:
    _observer, project, _linked = project_service(tmp_path)
    operator = ProjectService(_observer.config, Principal.for_name("operator"))
    source = project / "old.txt"
    source.write_text("tracked\n")
    git(project, "add", "old.txt")
    git(project, "commit", "--quiet", "-m", "tracked rename source")
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
    assert (project / "new.txt").read_text() == "tracked\n"
    assert ignored.read_text() == "must never enter the object database"
    assert (
        subprocess.run(
            ["git", "-C", str(project), "cat-file", "-e", private_object],
            check=False,
            capture_output=True,
        ).returncode
        != 0
    )


def git_stdout(path: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()
