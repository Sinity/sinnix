from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from conftest import call, ok
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig


def test_files_search_reports_regex_errors_and_applies_content_filters(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "recent.txt").write_text("needle\n")
    (root / "many.txt").write_text("needle\nneedle\nneedle\n")
    (root / "directory").mkdir()
    server = create_server(
        GatewayConfig(state_dir=tmp_path / "state", projects={}), "operator"
    )

    filtered = ok(
        server,
        "files.search",
        {
            "roots": [{"path": str(root)}],
            "content_regex": "needle",
            "kind": "directory",
            "min_bytes": 1000,
        },
    )
    assert filtered["matches"] == []
    complete = ok(
        server,
        "files.search",
        {"roots": [{"path": str(root)}], "content_regex": "needle", "limit": 2},
    )
    many = next(match for match in complete["matches"] if match["name"] == "many.txt")
    assert many["match_count"] == 3 and complete["truncated"] is False
    assert (
        call(
            server,
            "files.search",
            {"roots": [{"path": str(root)}], "content_regex": "["},
        )["error"]["code"]
        == "invalid_request"
    )


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def test_project_search_and_diff_expose_owner_output_bounds(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "--quiet")
    _git(project, "config", "user.name", "fixture")
    _git(project, "config", "user.email", "fixture@example.invalid")
    target = project / "fixture.txt"
    target.write_text("needle " + "x" * 5_000 + "\n")
    _git(project, "add", ".")
    _git(project, "commit", "--quiet", "-m", "fixture")
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        max_result_bytes=1_024,
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
    )
    server = create_server(config, "observer")

    search = ok(
        server,
        "projects.search",
        {"target": {"project": "fixture"}, "query": "needle"},
    )
    assert search["truncated"] is True
    target.write_text("changed " + "x" * 5_000 + "\n")
    diff = ok(server, "projects.diff", {"target": {"project": "fixture"}})
    assert diff["truncated"] is True
    assert diff.get("diff") or diff.get("artifact")


def test_files_patch_uses_git_apply_semantics_without_cross_file_writes(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.txt"
    target.write_bytes(b"one\ntwo")
    other = tmp_path / "other.txt"
    other.write_text("unchanged\n")
    server = create_server(
        GatewayConfig(state_dir=tmp_path / "state", projects={}), "operator"
    )
    patch = "--- a/target.txt\n+++ b/target.txt\n@@ -1,2 +1,2 @@\n-one\n+ONE\n two\n\\ No newline at end of file\n"
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    dry_run = ok(
        server,
        "files.patch",
        {
            "target": {"path": str(target)},
            "edit": {"mode": "unified", "patch": patch},
            "expected_sha256": before,
            "dry_run": True,
            "idempotency_key": "dry-run",
        },
    )
    assert dry_run["after_sha256"] != before and target.read_bytes() == b"one\ntwo"

    applied = ok(
        server,
        "files.patch",
        {
            "target": {"path": str(target)},
            "edit": {"mode": "unified", "patch": patch},
            "expected_sha256": before,
            "idempotency_key": "apply",
        },
    )
    assert target.read_bytes() == b"ONE\ntwo"
    assert applied["applied_hunks"] == 1
    assert other.read_text() == "unchanged\n"

    rejected = ok(
        server,
        "files.patch",
        {
            "target": {"path": str(target)},
            "edit": {
                "mode": "unified",
                "patch": "--- a/target.txt\n+++ b/target.txt\n@@ -1,1 +1,1 @@\n-nope\n+NOPE\n@@ -1,1 +1,1 @@\n-ONE\n+ONE2\n",
            },
            "idempotency_key": "partial",
        },
    )
    assert len(rejected["rejected_hunks"]) == 1
    assert target.read_bytes() == b"ONE2\ntwo"

    malformed = call(
        server,
        "files.patch",
        {
            "target": {"path": str(target)},
            "edit": {
                "mode": "unified",
                "patch": "--- a/target.txt\n+++ b/target.txt\n@@ -1,99 +1,1 @@\n-ONE\n+one\n",
            },
            "idempotency_key": "malformed",
        },
    )
    assert malformed["error"]["code"] == "invalid_request"
