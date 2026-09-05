"""Typed Beads actions over a fake ``bd`` owner command."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anyio
import pytest
from mcp.types import CallToolResult
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.action import MutationControls, validate_actions
from sinnix_agent_gateway.actions import beads, files
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import (
    GatewayConfig,
    ProjectConfig,
    TaskAuthorityConfig,
)
from sinnix_agent_gateway.contracts import VerbFamily
from sinnix_agent_gateway.tooling import build_tool, tool_signature_matches

ACTIONS = validate_actions(
    (*files.ACTIONS, *beads.ACTIONS), also_known=("projects.context", "projects.get")
)

FAKE_BD = """#!{python}
import json, pathlib, sys
log = pathlib.Path({log!r}); log.open('a').write(json.dumps(sys.argv[1:]) + '\\n')
project = {project!r}
state_path = pathlib.Path({state!r})
state = json.loads(state_path.read_text()) if state_path.exists() else {{'writes': 0, 'created': 0}}
args = sys.argv[1:]
root = next((args[i + 1] for i, v in enumerate(args) if v == '--directory'), project)
rows = [
    {{'id': 'fixture-1', 'title': 'first gateway task', 'status': 'open', 'priority': 1, 'notes': 'n1', 'description': 'd1'}},
    {{'id': 'fixture-2', 'title': 'second task', 'status': 'open', 'priority': 2}},
    {{'id': 'fixture-3', 'title': 'third gateway task', 'status': 'closed', 'priority': 3}},
]
def save():
    state['writes'] += 1; state_path.write_text(json.dumps(state))
if args[-1] == 'where':
    print(json.dumps({{'path': root + '/.beads', 'database_path': root + '/.beads/dolt', 'schema_version': 1}}))
elif args[-1] == 'status':
    print(json.dumps({{'summary': {{'total_issues': 3 + state['writes']}}}}))
elif 'export' in args:
    dest = pathlib.Path(args[args.index('-o') + 1]); dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({{'writes': state['writes']}}) + '\\n'); print(json.dumps({{'exported': str(dest)}}))
elif 'create' in args and '--dry-run' not in args:
    state['created'] += 1; save()
    print(json.dumps({{'id': 'fixture-created-%d' % state['created'], 'title': args[args.index('create') + 1], 'status': 'open'}}))
elif '--dry-run' in args:
    print(json.dumps({{'dry_run': True}}))
elif '--format' in args:
    print('flowchart TD\\n  fixture-1 --> fixture-2')
elif '--refs' in args:
    print(json.dumps({{'schema_version': 1, 'fixture-1': []}}))
elif 'show' in args:
    wanted = next((x for x in args if x.startswith('fixture-')), 'fixture-1')
    row = next((r for r in rows if r['id'] == wanted), {{'id': wanted, 'title': 'created', 'status': 'open'}})
    print(json.dumps(row))
elif 'dep' in args:
    print(json.dumps({{'issues': [{{'id': 'fixture-2', 'dependency_type': 'blocks'}}]}}))
elif 'backup' in args and 'list' in args:
    print(json.dumps({{'backups': ['b1']}}))
else:
    if '--readonly' not in args and any(x in args for x in ('update', 'unclaim', 'close', 'reopen', 'comments', 'remember', 'forget', 'dolt', 'backup')):
        save()
    selected = rows
    if '--title-contains' in args:
        needle = args[args.index('--title-contains') + 1].lower()
        selected = [r for r in rows if needle in r['title'].lower()]
    if '--limit' in args:
        selected = selected[: int(args[args.index('--limit') + 1])]
    print(json.dumps({{'issues': selected}}))
"""


def fixture(tmp_path: Path) -> tuple[GatewayConfig, Path]:
    project = tmp_path / "project"
    project.mkdir()
    log = tmp_path / "commands.jsonl"
    runner = tmp_path / "bd"
    runner.write_text(
        FAKE_BD.format(
            python=sys.executable,
            log=str(log),
            project=str(project),
            state=str(tmp_path / "owner-state.json"),
        )
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture",
                path=project,
                observer_read=True,
                task_authority=TaskAuthorityConfig(
                    owner="beads",
                    workspace=project / ".beads",
                    database=project / ".beads" / "dolt",
                ),
            )
        },
        beads_command=str(runner),
        approved_manifest_hash="approved-fixture-hash",
    )
    return config, log


def commands(log: Path) -> list[list[str]]:
    return [json.loads(line) for line in log.read_text().splitlines()]


@pytest.fixture(autouse=True)
def serve_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server_module,
        "visible_actions",
        lambda principal: tuple(a for a in ACTIONS if principal in a.principals),
    )


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
    config, _ = fixture(tmp_path)
    runtime = create_server(config, "operator")._sinnix_revision_publisher.runtime
    for action in beads.ACTIONS:
        tool = build_tool(action, runtime)
        assert tool_signature_matches(tool, action), action.name
        assert action.examples and action.aliases and action.affordances
        mutating = action.family in {VerbFamily.CHANGE, VerbFamily.OPERATE}
        assert issubclass(action.Input, MutationControls) is mutating
    change = next(a for a in beads.ACTIONS if a.name == "beads.change")
    operations = change.input_schema()["properties"]["change"]["discriminator"][
        "mapping"
    ]
    assert {
        "create",
        "update",
        "claim",
        "close",
        "comment",
        "dependency.add",
        "reparent",
        "memory.remember",
        "graph.create",
    } <= set(operations)
    filters = beads.NativeFilters.model_json_schema()["properties"]
    assert {
        "title_contains",
        "label",
        "updated_after",
        "stale_days",
        "no_assignee",
    } <= set(filters)


def test_query_passes_limit_to_the_owner_and_pages(tmp_path: Path) -> None:
    config, log = fixture(tmp_path)
    server = create_server(config, "observer")
    first = ok(
        server, "beads.query", {"projects": ["fixture"], "view": "open", "limit": 1}
    )
    assert first["kind"] == "bead_query" and first["project_refs"] == [
        "sinnix://projects/fixture"
    ]
    assert [row["id"] for row in first["items"]] == ["fixture-1"]
    assert first["items"][0]["ref"] == "sinnix://projects/fixture/beads/fixture-1"
    listing = next(c for c in commands(log) if "list" in c)
    assert listing[listing.index("--limit") + 1] == "1"
    assert first["coverage"]["fixture"]["state"] == "complete"
    assert first["page"]["next_cursor"] is None
    assert "beads.get" in first["affordances"]

    filtered = ok(
        server,
        "beads.query",
        {
            "projects": ["fixture"],
            "view": "open",
            "native_filters": {"title_contains": "gateway"},
            "limit": 10,
        },
    )
    assert [row["id"] for row in filtered["items"]] == ["fixture-1", "fixture-3"]

    unfiltered = ok(server, "beads.query", {"projects": ["fixture"], "view": "query"})
    assert (
        unfiltered["items"] == []
        and unfiltered["coverage"]["fixture"]["state"] == "partial"
    )
    assert unfiltered["warnings"] == ["partial_source"]
    assert (
        error(server, "beads.query", {"projects": ["missing"], "view": "open"})
        == "not_found"
    )
    assert (
        error(
            server,
            "beads.query",
            {"projects": ["fixture"], "native_filters": {"bogus": "x"}},
        )
        == "invalid_request"
    )
    assert (
        error(server, "beads.query", {"graph": {"bead": "fixture-1"}})
        == "invalid_request"
    )

    graph = ok(
        server,
        "beads.query",
        {
            "projects": ["fixture"],
            "graph": {"bead": "fixture-1", "direction": "both", "mermaid": True},
        },
    )
    assert graph["kind"] == "bead_graph" and graph["graph"]["ref"].endswith(
        "/beads/fixture-1"
    )
    assert graph["graph"]["mermaid"].startswith("flowchart")

    memory = ok(
        server, "beads.query", {"projects": ["fixture"], "memory": {"query": "gateway"}}
    )
    assert memory["kind"] == "bead_memory" and memory["memory"]["kind"] == "bead_memory"


def test_get_resolves_ids_refs_and_titles(tmp_path: Path) -> None:
    config, _ = fixture(tmp_path)
    server = create_server(config, "agent-control")

    by_id = ok(
        server,
        "beads.get",
        {"target": {"id": "fixture-1"}, "includes": ["dependencies", "comments"]},
    )
    assert by_id["ref"] == "sinnix://projects/fixture/beads/fixture-1"
    assert by_id["project_id"] == "fixture" and by_id["bead_id"] == "fixture-1"
    assert by_id["bead"]["fields"]["title"] == "first gateway task"
    assert set(by_id["bead"]["includes"]) == {"comments", "dependencies"}

    by_ref = ok(
        server, "beads.get", {"target": {"ref": by_id["ref"]}, "projection": "graph"}
    )
    assert by_ref["graph"]["direction"] == "both" and by_ref["graph"]["depth"] == 2

    notes = ok(
        server,
        "beads.get",
        {
            "target": {"project": "fixture", "title_contains": "second"},
            "projection": "notes",
        },
    )
    assert notes["bead_id"] == "fixture-2"
    assert set(notes["bead"]) == {
        "ref",
        "id",
        "project_id",
        "task_revision",
        "etag",
        "fields",
    }

    ambiguous = call(
        server,
        "beads.get",
        {"target": {"project": "fixture", "title_contains": "gateway"}},
    )
    assert ambiguous["error"]["code"] == "conflict"
    candidates = ambiguous["error"]["details"]["candidates"]
    assert [c["ref"].rsplit("/", 1)[1] for c in candidates] == [
        "fixture-1",
        "fixture-3",
    ]
    assert (
        error(
            server,
            "beads.get",
            {"target": {"project": "fixture", "title_contains": "zzz"}},
        )
        == "not_found"
    )
    assert (
        error(server, "beads.get", {"target": {"id": "unknown-1"}}) == "invalid_request"
    )


def test_change_operations_preview_apply_and_preconditions(tmp_path: Path) -> None:
    config, log = fixture(tmp_path)
    server = create_server(config, "operator")
    comment = {"operation": "comment", "target": {"id": "fixture-1"}, "text": "hello"}

    preview = ok(
        server,
        "beads.change",
        {"change": comment, "mode": "preview", "idempotency_key": "c0"},
    )
    assert preview["mode"] == "preview" and preview["command"] == [
        "comments",
        "add",
        "fixture-1",
        "hello",
    ]
    assert (
        preview["ref"] == "sinnix://projects/fixture/beads/fixture-1"
        and preview["bead_id"] == "fixture-1"
    )
    assert preview["after_revision"] is None

    applied = ok(
        server,
        "beads.change",
        {
            "change": comment,
            "preview_digest": preview["preview_digest"],
            "idempotency_key": "c1",
        },
    )
    assert (
        applied["mode"] == "apply"
        and applied["after_revision"] != applied["before_revision"]
    )
    assert applied["owner_history_ref"].endswith("/beads/fixture-1/history")

    stale = call(
        server,
        "beads.change",
        {
            "change": comment,
            "preview_digest": preview["preview_digest"],
            "idempotency_key": "c2",
        },
    )
    assert stale["error"]["code"] == "precondition_failed"

    created = ok(
        server,
        "beads.change",
        {
            "change": {
                "operation": "create",
                "project": {"project": "fixture"},
                "title": "new",
                "type": "task",
                "priority": "2",
                "labels": ["a", "b"],
            },
            "idempotency_key": "cr1",
        },
    )
    assert created["bead_id"] == "fixture-created-1" and created["ref"].endswith(
        "/beads/fixture-created-1"
    )
    create = next(c for c in commands(log) if "create" in c and "--dry-run" not in c)
    assert create[create.index("--labels") + 1] == "a,b" and "--type" in create

    closed = ok(
        server,
        "beads.change",
        {
            "change": {
                "operation": "close",
                "target": {"ref": "sinnix://projects/fixture/beads/fixture-2"},
                "reason": "done",
                "force": True,
            },
            "expected": {"expected_status": "open"},
            "idempotency_key": "cl1",
        },
    )
    close = next(c for c in commands(log) if "close" in c)
    close = close[close.index("close") :]
    assert (
        close[:2] == ["close", "fixture-2"]
        and "--force" in close
        and "--reason" in close
    )
    assert closed["preconditions"] == {"expected_status": "open"}
    wrong = call(
        server,
        "beads.change",
        {
            "change": {"operation": "close", "target": {"id": "fixture-2"}},
            "expected": {"expected_status": "in_progress"},
            "idempotency_key": "cl2",
        },
    )
    assert wrong["error"]["code"] == "precondition_failed"

    updated = ok(
        server,
        "beads.change",
        {
            "change": {
                "operation": "update",
                "target": {"id": "fixture-1"},
                "patch": {"set": {"priority": "0"}, "labels": {"add": ["x"]}},
            },
            "idempotency_key": "u1",
        },
    )
    assert updated["operation"] == "update"
    dep = ok(
        server,
        "beads.change",
        {
            "change": {
                "operation": "dependency.add",
                "target": {"id": "fixture-1"},
                "depends_on": "fixture-2",
            },
            "idempotency_key": "d1",
        },
    )
    assert dep["command"] == [
        "dep",
        "add",
        "fixture-1",
        "fixture-2",
        "--type",
        "blocks",
    ]
    memory = ok(
        server,
        "beads.change",
        {
            "change": {
                "operation": "memory.remember",
                "target": {"id": "fixture-1"},
                "key": "k",
                "text": "t",
            },
            "idempotency_key": "m1",
        },
    )
    assert (
        memory["command"] == ["remember", "t", "--key", "k"]
        and memory["bead_id"] == "fixture-1"
    )
    assert (
        error(
            server,
            "beads.change",
            {"change": comment, "preconditions": {"nope": 1}, "idempotency_key": "bad"},
        )
        == "invalid_request"
    )
    assert (
        error(
            server,
            "beads.change",
            {
                "change": {"operation": "explode", "target": {"id": "fixture-1"}},
                "idempotency_key": "bad2",
            },
        )
        == "invalid_request"
    )


def test_agent_control_may_read_but_not_mutate(tmp_path: Path) -> None:
    config, _ = fixture(tmp_path)
    server = create_server(config, "agent-control")

    async def names():
        return {tool.name for tool in await server.list_tools()}

    tools = anyio.run(names)
    assert {"beads.query", "beads.get"} <= tools
    assert not {"beads.change", "beads.changeset", "beads.operate"} & tools


def test_changeset_and_operate(tmp_path: Path) -> None:
    config, log = fixture(tmp_path)
    server = create_server(config, "operator")
    steps = [
        {
            "operation": "create",
            "parameters": {"title": "Epic", "type": "epic"},
            "bind": "epic",
        },
        {"operation": "create", "parameters": {"title": "Child", "parent": "$epic"}},
        {"operation": "comment", "bead": "fixture-1", "parameters": {"text": "linked"}},
    ]
    anchor = {"project": {"project": "fixture"}}
    preview = ok(
        server, "beads.changeset", {**anchor, "steps": steps, "idempotency_key": "cs0"}
    )
    assert (
        preview["mode"] == "preview" and preview["ref"] == "sinnix://projects/fixture"
    )
    assert [row["ref"] for row in preview["actions"]][
        2
    ] == "sinnix://projects/fixture/beads/fixture-1"
    assert preview["actions"][0]["bind"] == "epic"

    applied = ok(
        server,
        "beads.changeset",
        {
            **anchor,
            "mode": "apply",
            "steps": steps,
            "preview_digest": preview["preview_digest"],
            "idempotency_key": "cs1",
        },
    )
    assert [row["outcome"] for row in applied["outcomes"]] == ["applied"] * 3
    assert applied["outcomes"][0]["bound_ref"].endswith("/beads/fixture-created-1")
    assert applied["partial_completion"] is False
    child = [
        c
        for c in commands(log)
        if "create" in c and "Child" in c and "--dry-run" not in c
    ][0]
    assert child[child.index("--parent") + 1] == "fixture-created-1"
    assert (
        error(
            server,
            "beads.changeset",
            {
                **anchor,
                "steps": steps,
                "preconditions": {"expected_status": "open"},
                "idempotency_key": "cs2",
            },
        )
        == "invalid_request"
    )
    assert (
        error(
            server,
            "beads.changeset",
            {
                **anchor,
                "steps": [
                    {"operation": "comment", "parameters": {"text": "x"}, "bind": "b"}
                ],
                "idempotency_key": "cs3",
            },
        )
        == "invalid_request"
    )

    published = ok(
        server,
        "beads.operate",
        {
            **anchor,
            "operation": {"operation": "snapshot.publish"},
            "idempotency_key": "op1",
        },
    )
    assert (
        published["operation"] == "snapshot.publish"
        and published["ref"] == "sinnix://projects/fixture"
    )
    assert published["publication"] is not None
    listed = ok(
        server,
        "beads.operate",
        {**anchor, "operation": {"operation": "backup.list"}, "idempotency_key": "op2"},
    )
    assert listed["owner_result"] == {"backups": ["b1"]}
    restore = ok(
        server,
        "beads.operate",
        {
            **anchor,
            "operation": {"operation": "backup.restore", "backup_id": "b1"},
            "idempotency_key": "op3",
        },
    )
    assert restore["operation"] == "backup.restore"
    assert any(
        c[:3] == ["backup", "restore", "b1"] or c[-3:] == ["backup", "restore", "b1"]
        for c in commands(log)
    )
    assert (
        error(
            server,
            "beads.operate",
            {
                **anchor,
                "operation": {"operation": "backup.restore"},
                "idempotency_key": "op4",
            },
        )
        == "invalid_request"
    )
