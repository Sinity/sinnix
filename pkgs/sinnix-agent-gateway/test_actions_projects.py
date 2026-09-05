"""Typed project actions over real git checkouts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import anyio
import pytest
from mcp.types import CallToolResult
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.action import MutationControls, validate_actions
from sinnix_agent_gateway.actions import files, projects
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.contracts import VerbFamily
from sinnix_agent_gateway.locators import BeadLocator, CheckoutLocator, ProjectLocator
from sinnix_agent_gateway.tooling import build_tool, tool_signature_matches

ACTIONS = validate_actions(
    (*files.ACTIONS, *projects.ACTIONS),
    also_known=(
        "beads.query",
        "beads.get",
        "beads.change",
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


def fixture(
    tmp_path: Path, *, observer_read: bool = True
) -> tuple[GatewayConfig, Path, Path]:
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
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=observer_read
            )
        },
        approved_manifest_hash="approved-fixture-hash",
    )
    return config, project, linked


def call(server, name: str, arguments: dict) -> dict:
    async def invoke():
        return await server.call_tool(name, arguments)

    result = anyio.run(invoke)
    if isinstance(result, CallToolResult):
        assert result.structured_content is not None
        return result.structured_content
    return result


def ok(server, name: str, arguments: dict) -> dict:
    response = call(server, name, arguments)
    assert response["result"]["outcome"] == "ok", response
    return response["data"]


def error(server, name: str, arguments: dict) -> str:
    response = call(server, name, arguments)
    assert response["result"]["outcome"] != "ok", response
    return response["error"]["code"]


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
    assert listing["projects"] == [
        {
            "ref": "sinnix://projects/fixture",
            "project_id": "fixture",
            "available": True,
            "default_ref": "master",
            "observer_read": True,
            "writable": True,
        }
    ]

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


def test_tree_read_diff_and_search_keep_authority_checks(tmp_path: Path) -> None:
    config, project, linked = fixture(tmp_path)
    server = create_server(config, "observer")
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


def test_observer_cannot_see_hidden_projects(tmp_path: Path) -> None:
    config, _, _ = fixture(tmp_path, observer_read=False)
    server = create_server(config, "observer")
    assert ok(server, "projects.list", {})["projects"] == []
    assert (
        error(
            server,
            "projects.read",
            {"target": {"project": "fixture"}, "path": "README.md"},
        )
        == "policy_denied"
    )


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
    assert orientation["snapshot_ref"].startswith("sinnix://contexts/")
    by_name = {row["name"]: row for row in orientation["components"]}
    assert by_name["project"]["status"] == "available"
    assert by_name["project"]["data"]["changes"]["unstaged"] == 1
    assert by_name["checkout"]["data"]["checkout"]["checkout_id"] == "default"
    tasks = by_name["tasks"]
    assert (
        tasks["status"] == "unavailable"
        or tasks["data"]["coverage"]["fixture"]["state"] == "partial"
    )
    assert orientation["context_schema"] == "sinnix.gateway-context.v1"

    triage = ok(
        server,
        "projects.context",
        {"target": {"ref": "sinnix://projects/fixture"}, "intent": "project.triage"},
    )
    names = [row["name"] for row in triage["components"]]
    assert names == ["project", "open_beads", "stale_claims", "changes"]
    changes = next(row for row in triage["components"] if row["name"] == "changes")
    assert "dirty" in changes["data"]["diff"]
    assert (
        error(
            server,
            "projects.context",
            {"target": {"project": "fixture"}, "intent": "incident"},
        )
        == "invalid_request"
    )
