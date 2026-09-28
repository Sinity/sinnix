"""Typed project actions over real git checkouts."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import anyio
import pytest
from conftest import call, error, ok
from sinnix_agent_gateway import projects as projects_module
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.action import MutationControls, validate_actions
from sinnix_agent_gateway.actions import files, projects
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.contracts import VerbFamily
from sinnix_agent_gateway.locators import BeadLocator, CheckoutLocator, ProjectLocator
from sinnix_agent_gateway.projects import ProjectError, ProjectPreconditionError
from sinnix_agent_gateway.tooling import build_tool, tool_signature_matches

ACTIONS = validate_actions(
    (*files.ACTIONS, *projects.ACTIONS),
    also_known=(
        "beads.query",
        "beads.get",
        "beads.update",
        "beads.changeset",
        "beads.operate",
    ),
)


@pytest.fixture(autouse=True)
def serve_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server_module,
        "visible_actions",
        lambda principal: tuple(a for a in ACTIONS if principal in a.principals),
    )


def git(path: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def test_search_large_lines_and_requested_count(tmp_path: Path) -> None:
    config, project, _ = fixture(tmp_path)
    server = create_server(config, "operator")
    rt = server._sinnix_revision_publisher.runtime
    long_line = "needle " + "x" * 300_000
    (project / "large.txt").write_text(long_line + "\n" + "needle\n" * 1100)
    result = rt.projects.search("fixture", "needle", 1200)
    assert not result["truncated"]
    assert len(result["matches"]) == 1101
    assert result["matches"][0]["text"] == long_line
    assert projects.SearchInput(
        target={"project": "fixture"}, query="needle", max_matches=1200
    )


def test_tree_exact_limit_and_large_requested_read(tmp_path: Path) -> None:
    config, project, _ = fixture(tmp_path)
    server = create_server(config, "operator")
    rt = server._sinnix_revision_publisher.runtime
    assert rt.projects.tree("fixture", max_entries=3)["truncated"] is False
    content = "large " + "x" * 300_000
    (project / "large.txt").write_text(content)
    result = rt.projects.read("fixture", "large.txt", max_bytes=400_000)
    assert result["content"] == content
    assert not result["truncated"]


def test_tree_pages_continue_past_default_limit(tmp_path: Path) -> None:
    config, project, _ = fixture(tmp_path)
    for index in range(6):
        (project / f"file-{index}.txt").write_text(str(index))
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime
    complete = runtime.projects.tree("fixture", max_entries=100)
    seen = []
    cursor = None
    while True:
        page = runtime.projects.tree("fixture", max_entries=2, start_after=cursor)
        seen.extend(row["path"] for row in page["entries"])
        cursor = page["next_start_after"]
        if cursor is None:
            break
    assert seen == [row["path"] for row in complete["entries"]]


def test_read_many_observes_checkout_once_per_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = fixture(tmp_path)
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime
    observed = []
    original = projects_module._content_revision

    def record(path: Path) -> str:
        observed.append(path)
        return original(path)

    monkeypatch.setattr(projects_module, "_content_revision", record)
    result = runtime.projects.read_many(
        "fixture",
        [
            {"path": "README.md", "start_line": 1, "end_line": 1, "max_bytes": 100},
            {"path": "src/main.py", "start_line": 1, "end_line": 1, "max_bytes": 100},
        ],
    )
    assert len(observed) == 2
    assert all(
        row["checkout_revision"] == result["checkout_revision"]
        for row in result["files"]
    )


def test_project_reads_reuse_verified_hashes_and_invalidate_changed_files(
    tmp_path: Path,
) -> None:
    config, project, _ = fixture(tmp_path)
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime
    projects_module._cached_file_sha256.cache_clear()
    first = runtime.projects.read("fixture", "README.md")
    cold_misses = projects_module._cached_file_sha256.cache_info().misses
    assert cold_misses >= 2

    repeated = runtime.projects.read("fixture", "README.md")
    assert repeated["checkout_revision"] == first["checkout_revision"]
    assert projects_module._cached_file_sha256.cache_info().misses == cold_misses

    changed = project / "src" / "main.py"
    before = changed.stat()
    changed.write_bytes(b"x" * before.st_size)
    os.utime(changed, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = runtime.projects.read("fixture", "README.md")
    assert after["checkout_revision"] != first["checkout_revision"]
    assert projects_module._cached_file_sha256.cache_info().misses == cold_misses + 1


def test_export_covers_source_and_continues_explicit_pages(tmp_path: Path) -> None:
    config, project, _ = fixture(tmp_path)
    (project / ".gitignore").write_text(".venv/\n")
    (project / ".venv").mkdir()
    (project / ".venv" / "generated.bin").write_bytes(b"x" * 100_000)
    (project / "large.txt").write_bytes(b"source" * 10_000)
    executable = project / "run.sh"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    (project / "run-link").symlink_to("run.sh")
    (project / "MANIFEST.json").write_text("source manifest\n")
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime

    whole = runtime.projects.export("fixture")
    assert whole["manifest"]["truncated"] is False
    with zipfile.ZipFile(whole["archive"]) as bundle:
        names = set(bundle.namelist())
        assert "large.txt" in names
        assert ".venv/generated.bin" not in names
        assert ".env" not in names
        assert ".git/config" not in names
        assert bundle.read("large.txt") == b"source" * 10_000
        assert bundle.read("MANIFEST.json") == b"source manifest\n"
        assert bundle.read(whole["manifest"]["manifest_path"])
        assert bundle.getinfo("run.sh").external_attr >> 16 & 0o777 == 0o755
        link_info = bundle.getinfo("run-link")
        assert link_info.external_attr >> 16 & 0o170000 == 0o120000
        assert bundle.read("run-link") == b"run.sh"
        entries = {row["path"]: row for row in whole["manifest"]["files"]}
        assert entries["run.sh"]["mode"] == 0o755
        assert entries["run-link"]["kind"] == "symlink"

    first = runtime.projects.export("fixture", max_files=2)
    assert first["manifest"]["truncated"] is True
    second = runtime.projects.export(
        "fixture",
        max_files=2,
        start_after=first["manifest"]["next_start_after"],
        expected_revision=first["manifest"]["checkout_revision"],
    )
    first_paths = {row["path"] for row in first["manifest"]["files"]}
    second_paths = {row["path"] for row in second["manifest"]["files"]}
    assert first_paths.isdisjoint(second_paths)
    page_paths = first_paths | second_paths
    cursor = second["manifest"]["next_start_after"]
    while cursor is not None:
        page = runtime.projects.export(
            "fixture",
            max_files=2,
            start_after=cursor,
            expected_revision=first["manifest"]["checkout_revision"],
        )
        page_paths.update(row["path"] for row in page["manifest"]["files"])
        cursor = page["manifest"]["next_start_after"]
    assert page_paths == {row["path"] for row in whole["manifest"]["files"]}
    with pytest.raises(ProjectError, match="increase max_bytes"):
        runtime.projects.export("fixture", max_bytes=1)
    (project / "README.md").write_text("changed\n")
    with pytest.raises(ProjectPreconditionError, match="previous export page"):
        runtime.projects.export(
            "fixture",
            max_files=2,
            start_after=first["manifest"]["next_start_after"],
            expected_revision=first["manifest"]["checkout_revision"],
        )


def fixture(tmp_path: Path) -> tuple[GatewayConfig, Path, Path]:
    project = tmp_path / "project"
    linked = tmp_path / "linked"
    project.mkdir()
    git(project, "init", "--quiet", "--initial-branch=master")
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "user.email", "fixture@example.invalid")
    (project / "README.md").write_text("fixture\nline two\nline three\n")
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("def mkServiceModule():\n    return 1\n")
    (project / ".env").write_text("SECRET=1\n")
    git(project, "add", ".")
    git(project, "commit", "--quiet", "-m", "initial fixture")
    git(project, "worktree", "add", "--quiet", "-b", "fixture-linked", str(linked))
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        approved_manifest_hash="approved-fixture-hash",
    )
    return config, project, linked


def test_actions_publish_honest_schemas(tmp_path: Path) -> None:
    config, _, _ = fixture(tmp_path)
    server = create_server(config, "operator")
    runtime = server._sinnix_revision_publisher.runtime
    for action in projects.ACTIONS:
        tool = build_tool(action, runtime)
        assert tool_signature_matches(tool, action), action.name
        assert tool.parameters.get("additionalProperties") is False
        assert action.examples and action.aliases and action.affordances
        mutating = action.family in {VerbFamily.CHANGE, VerbFamily.OPERATE}
        assert issubclass(action.Input, MutationControls) is mutating


def test_locators_require_exactly_one_selector() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ProjectLocator()
    with pytest.raises(ValueError, match="exactly one"):
        ProjectLocator(project="a", path="/b")
    with pytest.raises(ValueError, match="requires project"):
        CheckoutLocator(ref="sinnix://projects/a", checkout="default")
    with pytest.raises(ValueError, match="requires project"):
        BeadLocator(title_contains="x")
    with pytest.raises(ValueError, match="already names"):
        BeadLocator(ref="sinnix://projects/a/beads/a-1", project="a")


def test_list_get_and_locators_resolve_projects_and_checkouts(tmp_path: Path) -> None:
    config, project, linked = fixture(tmp_path)
    server = create_server(config, "operator")

    listing = ok(server, "projects.list", {})
    listed = listing["projects"][0]
    assert listed["ref"] == "sinnix://projects/fixture"
    assert listed["project_id"] == "fixture"
    assert listed["available"] is True
    assert listed["default_ref"] == "master"
    assert listed["repository_path"] == str(project.resolve())
    assert listed["repository_kind"] == "worktree"
    assert listed["default_checkout_id"] == "default"
    assert listed["default_checkout_path"] == str(project.resolve())
    assert {row["checkout_id"] for row in listed["checkouts"]} == {
        "default",
        projects_module.ProjectService._checkout_id(
            linked.resolve(), project.resolve()
        ),
    }
    assert listed["writable"] is True

    summary = ok(server, "projects.get", {"target": {"project": "fixture"}})
    assert summary["ref"] == "sinnix://projects/fixture/checkouts/default"
    assert summary["project_ref"] == "sinnix://projects/fixture"
    assert summary["checkout_id"] == "default"
    assert summary["project"]["branch"]["head"] == "master"
    assert summary["checkout"]["head"] == git(project, "rev-parse", "HEAD")
    assert len(summary["checkout"]["dirty_sha256"]) == 64
    assert summary["checkouts"] is None

    by_path = ok(
        server,
        "projects.get",
        {"target": {"path": str(linked / "README.md")}, "projection": "git"},
    )
    assert by_path["checkout_id"].startswith("worktree-")
    assert by_path["checkout"]["branch"] == "fixture-linked"
    assert [row["checkout_id"] for row in by_path["checkouts"]][0] == "default"
    assert (
        by_path["checkout_ref"]
        == f"sinnix://projects/fixture/checkouts/{by_path['checkout_id']}"
    )

    authority = ok(
        server,
        "projects.get",
        {"target": {"ref": by_path["checkout_ref"]}, "projection": "authority"},
    )
    assert (
        authority["code_revision"]
        and authority["canonical_checkout_ref"] == summary["checkout_ref"]
    )
    assert authority["task_authority"]["availability"] == "unavailable"
    assert authority["checkout"]["checkout_id"] == by_path["checkout_id"]

    assert error(server, "projects.get", {"target": {"project": "nope"}}) == "not_found"
    assert (
        error(
            server,
            "projects.get",
            {"target": {"project": "fixture", "checkout": "worktree-missing"}},
        )
        == "not_found"
    )
    assert (
        error(server, "projects.get", {"target": {"path": str(tmp_path / "elsewhere")}})
        == "not_found"
    )
    assert error(server, "projects.get", {"target": {}}) == "invalid_request"


def _bare_fixture(
    tmp_path: Path, *, default_checkout: Path | None
) -> tuple[GatewayConfig, Path, Path, Path]:
    source = tmp_path / "source"
    store = tmp_path / "repository.git"
    primary = tmp_path / "primary"
    secondary = tmp_path / "secondary"
    source.mkdir()
    git(source, "init", "--quiet", "--initial-branch=main")
    git(source, "config", "user.name", "Fixture")
    git(source, "config", "user.email", "fixture@example.invalid")
    (source / "README.md").write_text("bare repository fixture\n")
    git(source, "add", "README.md")
    git(source, "commit", "--quiet", "-m", "fixture")
    subprocess.run(
        ["git", "clone", "--quiet", "--bare", str(source), str(store)],
        check=True,
        capture_output=True,
    )
    git(store, "worktree", "add", "--quiet", "--detach", str(primary), "main")
    git(store, "worktree", "add", "--quiet", "--detach", str(secondary), "main")
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture",
                path=store,
                default_ref="refs/heads/main",
                default_checkout=default_checkout,
            )
        },
    )
    return config, store, primary, secondary


def test_bare_repository_lists_store_and_explicit_default_checkout(
    tmp_path: Path,
) -> None:
    config, store, primary, secondary = _bare_fixture(
        tmp_path, default_checkout=tmp_path / "primary"
    )
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime

    listed = runtime.projects.list()["projects"][0]
    assert listed["repository_kind"] == "bare"
    assert listed["default_ref"] == "refs/heads/main"
    assert listed["default_checkout_id"] == "default"
    assert len(listed["checkouts"]) == 2
    assert store.resolve().as_posix() not in {
        row["path"] for row in listed["checkouts"]
    }

    catalog = runtime.projects.checkouts("fixture")
    assert catalog["repository"] == {
        "kind": "bare",
        "path": str(store.resolve()),
        "default_ref": "refs/heads/main",
        "default_checkout_path": str(primary.resolve()),
    }
    default = next(
        row for row in catalog["checkouts"] if row["checkout_id"] == "default"
    )
    assert default["path"] == str(primary.resolve())
    assert all(row["path"] != str(store.resolve()) for row in catalog["checkouts"])
    assert runtime.projects.read("fixture", "README.md")["content"] == (
        "bare repository fixture\n"
    )
    assert (
        runtime.projects.read(
            "fixture",
            "README.md",
            checkout_id=projects_module.ProjectService._checkout_id(
                secondary.resolve(), store.resolve()
            ),
        )["content"]
        == "bare repository fixture\n"
    )
    public_view = ok(
        create_server(config, "operator"),
        "projects.get",
        {
            "target": {"project": "fixture", "checkout": "default"},
            "projection": "git",
        },
    )
    assert public_view["repository"]["kind"] == "bare"
    assert public_view["repository"]["path"] == str(store.resolve())
    assert public_view["checkout"]["path"] == str(primary.resolve())


def test_bare_repository_without_default_requires_explicit_checkout(
    tmp_path: Path,
) -> None:
    config, _store, _primary, _secondary = _bare_fixture(
        tmp_path, default_checkout=None
    )
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime
    listed = runtime.projects.list()["projects"][0]
    assert listed["repository_kind"] == "bare"
    assert listed["default_checkout_id"] is None
    assert len(listed["checkouts"]) == 2
    with pytest.raises(ProjectError, match="no configured default checkout"):
        runtime.projects.read("fixture", "README.md")
    selected = listed["checkouts"][0]
    assert (
        runtime.projects.read(
            "fixture", "README.md", checkout_id=selected["checkout_id"]
        )["content"]
        == "bare repository fixture\n"
    )
    server = create_server(config, "operator")
    assert (
        error(
            server,
            "projects.get",
            {"target": {"project": "fixture"}, "projection": "git"},
        )
        == "invalid_request"
    )


def test_bare_checkout_discovery_omits_missing_and_prunable_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, store, primary, secondary = _bare_fixture(
        tmp_path, default_checkout=tmp_path / "primary"
    )
    stale = tmp_path / "stale"
    git(store, "worktree", "add", "--quiet", "--detach", str(stale), "main")
    shutil.rmtree(stale)
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime
    service = runtime.projects
    original = service._run_spooled
    missing = tmp_path / "missing"

    def with_missing_record(command: list[str], cwd: Path, timeout: int = 15) -> str:
        output = original(command, cwd, timeout)
        if command[1:4] == ["worktree", "list", "--porcelain"]:
            output += (
                f"\nworktree {missing}\nHEAD {git(store, 'rev-parse', 'HEAD')}\n\n"
            )
        return output

    monkeypatch.setattr(service, "_run_spooled", with_missing_record)
    catalog = service.checkouts("fixture")
    paths = {row["path"] for row in catalog["checkouts"]}
    assert paths == {str(primary.resolve()), str(secondary.resolve())}
    assert str(stale) not in paths
    assert str(missing) not in paths


def test_public_project_list_obeys_scope_after_private_catalog_merge(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    excluded = tmp_path / "excluded"
    private = tmp_path / "private"
    for path in (allowed, excluded, private):
        path.mkdir()
    catalog = tmp_path / "private-projects.json"
    catalog.write_text(
        json.dumps({"projects": {"excluded-private": {"path": str(private)}}})
    )
    config_path = tmp_path / "gateway.json"
    config_path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {
                    "allowed-public": {"path": str(allowed)},
                    "excluded-public": {"path": str(excluded)},
                },
                "privateProjectCatalogFile": str(catalog),
                "endpoint": {"scope": {"projects": ["allowed-public"]}},
            }
        )
    )
    server = create_server(GatewayConfig.load(config_path), "operator")

    listing = ok(server, "projects.list", {})

    assert [row["project_id"] for row in listing["projects"]] == ["allowed-public"]


def test_public_project_list_keeps_empty_scope_broad(tmp_path: Path) -> None:
    public = tmp_path / "public"
    private = tmp_path / "private"
    public.mkdir()
    private.mkdir()
    catalog = tmp_path / "private-projects.json"
    catalog.write_text(
        json.dumps({"projects": {"private-fixture": {"path": str(private)}}})
    )
    config_path = tmp_path / "gateway.json"
    config_path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {"public-fixture": {"path": str(public)}},
                "privateProjectCatalogFile": str(catalog),
                "endpoint": {"scope": {"projects": []}},
            }
        )
    )
    server = create_server(GatewayConfig.load(config_path), "operator")

    listing = ok(server, "projects.list", {})

    assert [row["project_id"] for row in listing["projects"]] == [
        "private-fixture",
        "public-fixture",
    ]


def test_tree_read_diff_and_search_keep_authority_checks(tmp_path: Path) -> None:
    config, project, linked = fixture(tmp_path)
    server = create_server(config, "operator")
    target = {"target": {"project": "fixture"}}

    tree = ok(server, "projects.tree", {**target, "max_entries": 10})
    paths = [entry["path"] for entry in tree["entries"]]
    assert paths == ["src", "README.md", "src/main.py"] and tree["truncated"] is False
    assert ".env" not in paths

    read = ok(
        server,
        "projects.read",
        {**target, "path": "README.md", "start_line": 2, "end_line": 2},
    )
    assert read["content"] == "line two\n" and read["truncated"] is False
    assert read["path"] == "README.md" and read["project_id"] == "fixture"
    assert len(read["content_sha256"]) == 64
    assert len(read["checkout_revision"]) == 64
    many = ok(
        server,
        "projects.read_many",
        {
            **target,
            "files": [{"path": "README.md"}, {"path": "src/main.py"}],
        },
    )
    assert [row["path"] for row in many["files"]] == ["README.md", "src/main.py"]
    assert many["checkout_revision"] == read["checkout_revision"]
    export = ok(
        server,
        "projects.export",
        {**target, "max_files": 20, "max_bytes": 100_000},
    )
    assert export["manifest"]["file_count"] >= 2
    assert export["manifest"]["truncated"] is False
    assert "files" not in export["manifest"]
    assert export["manifest"]["manifest_path"] == "MANIFEST.json"
    assert export["artifact"]["ref"].startswith("sinnix://artifacts/")
    assert error(server, "projects.read", {**target, "path": ".env"}) == "policy_denied"
    assert (
        error(server, "projects.read", {**target, "path": "../outside"})
        == "policy_denied"
    )
    assert (
        error(server, "projects.read", {**target, "path": "missing.txt"}) == "not_found"
    )
    assert (
        error(server, "projects.read", {**target, "path": "/etc/passwd"})
        == "policy_denied"
    )

    (linked / "README.md").write_text("changed in linked\n")
    diff = ok(server, "projects.diff", {"target": {"path": str(linked)}})
    assert "changed in linked" in diff["diff"] and diff["checkout_id"].startswith(
        "worktree-"
    )
    assert ok(server, "projects.diff", target)["diff"] == ""
    assert (
        error(server, "projects.diff", {**target, "git_ref": "-rf"})
        == "invalid_request"
    )
    assert (
        error(server, "projects.diff", {**target, "git_ref": "no-such-ref"})
        == "invalid_request"
    )

    search = ok(
        server,
        "projects.search",
        {**target, "query": "mkServiceModule", "max_matches": 5},
    )
    assert search["matches"] == [
        {"path": "src/main.py", "line": 1, "text": "def mkServiceModule():"}
    ]
    assert search["truncated"] is False and search["query"] == "mkServiceModule"


def test_read_rechecks_resolved_symlink_targets_and_reports_emitted_bytes(
    tmp_path: Path,
) -> None:
    config, project, _ = fixture(tmp_path)
    secret = project / "secrets" / "fixture.txt"
    secret.parent.mkdir()
    secret.write_text("SYNTHETIC_PRIVATE\n")
    (project / "alias.txt").symlink_to("secrets/fixture.txt")
    (project / "aliasdir").symlink_to("secrets", target_is_directory=True)
    (project / "tiny.txt").write_text("abcde\n")
    server = create_server(config, "operator")
    target = {"target": {"project": "fixture"}}

    assert (
        error(server, "projects.read", {**target, "path": "alias.txt"})
        == "policy_denied"
    )
    assert (
        error(server, "projects.read", {**target, "path": "aliasdir/fixture.txt"})
        == "policy_denied"
    )
    bounded = ok(
        server,
        "projects.read",
        {**target, "path": "tiny.txt", "max_bytes": 3},
    )
    assert bounded["content"] == "abc" and bounded["bytes"] == 3
    assert bounded["truncated"] is True


def test_diff_omits_policy_excluded_paths(tmp_path: Path) -> None:
    config, project, _ = fixture(tmp_path)
    (project / ".env").write_text("SYNTHETIC_PRIVATE=hidden\n")
    (project / "README.md").write_text("visible change\n")
    server = create_server(config, "operator")

    result = ok(server, "projects.diff", {"target": {"project": "fixture"}})
    assert "visible change" in result["diff"]
    assert "SYNTHETIC_PRIVATE" not in result["diff"]
    assert ".env" not in result["diff"]


def test_revision_frames_file_boundaries_and_skips_ignored_files(
    tmp_path: Path, monkeypatch
) -> None:
    from sinnix_agent_gateway import projects as projects_module

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    git(first, "init", "--quiet")
    git(second, "init", "--quiet")
    for root in (first, second):
        git(root, "config", "user.email", "fixture@example.invalid")
    mode = (0o644).to_bytes(4, "big")
    (first / "a").write_bytes(b"x" + len(b"b").to_bytes(8, "big") + b"b" + mode + b"y")
    (second / "a").write_bytes(b"x")
    (second / "b").write_bytes(b"y")
    assert projects_module._content_revision(
        first
    ) != projects_module._content_revision(second)

    (first / ".gitignore").write_text("ignored.bin\n")
    ignored = first / "ignored.bin"
    ignored.write_bytes(b"synthetic ignored build output")
    original_open = Path.open

    def guarded_open(path: Path, *args, **kwargs):
        if path == ignored:
            raise AssertionError("ignored files must not be read for revisions")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    projects_module._content_revision(first)


def test_revision_tracks_symlink_target_and_mode(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    git(root, "init", "--quiet")
    (root / "first").write_text("first")
    (root / "second").write_text("second")
    link = root / "current"
    link.symlink_to("first")
    before = projects_module._content_revision(root)
    link.unlink()
    link.symlink_to("second")
    assert projects_module._content_revision(root) != before


def test_write_preserves_existing_mode_and_uses_readable_default(
    tmp_path: Path,
) -> None:
    config, project, _ = fixture(tmp_path)
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime
    script = project / "script.sh"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    runtime.projects.write(
        "fixture", "script.sh", "#!/bin/sh\necho updated\n", checkout_id="default"
    )
    assert script.read_text() == "#!/bin/sh\necho updated\n"
    assert script.stat().st_mode & 0o777 == 0o755
    runtime.projects.write("fixture", "new.txt", "new file\n", checkout_id="default")
    assert (project / "new.txt").stat().st_mode & 0o777 == 0o644


def test_diff_spools_complete_output_before_result_artifact(tmp_path: Path) -> None:
    config, project, _ = fixture(tmp_path)
    config = GatewayConfig(
        state_dir=config.state_dir,
        projects=config.projects,
        max_result_bytes=1_024,
        approved_manifest_hash=config.approved_manifest_hash,
    )
    server = create_server(config, "operator")
    (project / "README.md").write_text("changed " + "x" * 5_000 + "\n")

    response = call(server, "projects.diff", {"target": {"project": "fixture"}})
    assert response["result"]["outcome"] == "ok", response
    data = response["data"]
    assert data["truncated"] is True
    artifact_id = data["artifact"]["artifact_id"]
    runtime = server._sinnix_revision_publisher.runtime
    offset = 0
    chunks = []
    while True:
        page = runtime.artifacts.read(artifact_id, offset=offset, max_bytes=1_024)
        chunks.append(base64.b64decode(page["base64"]))
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    retained = json.loads(b"".join(chunks))
    assert retained["truncated"] is False
    assert "changed " + "x" * 5_000 in retained["diff"]


def test_change_requires_matching_preconditions_and_echoes_new_state(
    tmp_path: Path,
) -> None:
    config, project, _ = fixture(tmp_path)
    server = create_server(config, "operator")
    before = ok(server, "projects.get", {"target": {"project": "fixture"}})["checkout"]
    target = {"target": {"project": "fixture"}}

    missing = call(
        server,
        "projects.change",
        {
            **target,
            "change": {"operation": "write", "path": "notes.md", "content": "n\n"},
            "idempotency_key": "w0",
        },
    )
    assert missing["error"]["code"] == "precondition_failed"

    written = ok(
        server,
        "projects.change",
        {
            "target": {"ref": "sinnix://projects/fixture/checkouts/default"},
            "change": {
                "operation": "write",
                "path": "docs/notes.md",
                "content": "hello\n",
            },
            "expected_head": before["head"],
            "expected_dirty_sha256": before["dirty_sha256"],
            "idempotency_key": "w1",
        },
    )
    assert (project / "docs" / "notes.md").read_text() == "hello\n"
    assert (
        written["operation"] == "write"
        and written["bytes"] == 6
        and written["path"] == "docs/notes.md"
    )
    assert written["checkout"]["dirty_sha256"] != before["dirty_sha256"]
    assert written["checkout_ref"] == "sinnix://projects/fixture/checkouts/default"

    read_before = ok(
        server,
        "projects.read",
        {**target, "path": "README.md"},
    )
    (project / "README.md").write_text("changed outside gateway\n")
    guarded = call(
        server,
        "projects.change",
        {
            **target,
            "change": {
                "operation": "write",
                "path": "README.md",
                "content": "must not overwrite\n",
            },
            "expected_file_path": "README.md",
            "expected_file_sha256": read_before["content_sha256"],
            "idempotency_key": "w-file-stale",
        },
    )
    assert guarded["error"]["code"] == "precondition_failed"
    assert (project / "README.md").read_text() == "changed outside gateway\n"
    (project / "README.md").write_text("fixture\nline two\nline three\n")

    stale = call(
        server,
        "projects.change",
        {
            **target,
            "change": {
                "operation": "write",
                "path": "docs/notes.md",
                "content": "again\n",
            },
            "expected_dirty_sha256": before["dirty_sha256"],
            "idempotency_key": "w2",
        },
    )
    assert stale["error"]["code"] == "precondition_failed"
    assert (project / "docs" / "notes.md").read_text() == "hello\n"

    denied = call(
        server,
        "projects.change",
        {
            **target,
            "change": {"operation": "write", "path": ".env", "content": "x"},
            "expected_head": before["head"],
            "idempotency_key": "w3",
        },
    )
    assert denied["error"]["code"] == "policy_denied"

    patch = "--- a/README.md\n+++ b/README.md\n@@ -1,3 +1,3 @@\n-fixture\n+patched\n line two\n line three\n"
    applied = ok(
        server,
        "projects.change",
        {
            **target,
            "change": {"operation": "apply_patch", "patch": patch},
            "expected_head": before["head"],
            "idempotency_key": "p1",
        },
    )
    assert applied["operation"] == "apply_patch" and applied["applied"] is True
    assert (project / "README.md").read_text().startswith("patched\n")

    legacy = ok(
        server,
        "projects.change",
        {
            **target,
            "change": {
                "operation": "write",
                "path": "docs/legacy.md",
                "content": "l\n",
            },
            "preconditions": {"head": before["head"]},
            "idempotency_key": "w4",
        },
    )
    assert legacy["path"] == "docs/legacy.md"
    unknown = call(
        server,
        "projects.change",
        {
            **target,
            "change": {"operation": "write", "path": "a", "content": ""},
            "preconditions": {"nope": "x"},
            "idempotency_key": "w5",
        },
    )
    assert unknown["error"]["code"] == "invalid_request"


def test_context_composes_orientation_and_triage(tmp_path: Path) -> None:
    config, project, _ = fixture(tmp_path)
    server = create_server(config, "operator")
    (project / "README.md").write_text("dirty\n")

    orientation = ok(server, "projects.context", {"target": {"project": "fixture"}})
    assert (
        orientation["ref"] == "sinnix://projects/fixture"
        and orientation["intent"] == "project.orientation"
    )
    assert orientation["snapshot_ref"].startswith("sinnix://results/")
    assert orientation["components"][0]["name"] == "lynchpin"
    assert orientation["context_schema"] == "sinnix.owner-context.v2"

    triage = ok(
        server,
        "projects.context",
        {"target": {"ref": "sinnix://projects/fixture"}, "intent": "project.triage"},
    )
    for context in (orientation, triage):
        resource = anyio.run(server.read_resource, context["snapshot_ref"])
        stored = json.loads(list(resource)[0].content)["rows"][0]
        assert stored["intent"] == context["intent"]
        assert stored["target_ref"] == context["target_ref"]
        assert [row["source_revision"] for row in stored["components"]] == [
            row["source_revision"] for row in context["components"]
        ]
    assert [row["name"] for row in triage["components"]] == ["lynchpin"]
    assert (
        error(
            server,
            "projects.context",
            {"target": {"project": "fixture"}, "intent": "incident"},
        )
        == "invalid_request"
    )
