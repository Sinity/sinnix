"""Typed action contract: schema honesty, locators, content blocks."""

from __future__ import annotations

import base64
import json
import struct
import zlib
from pathlib import Path

import anyio
import pytest
from mcp.types import CallToolResult, ImageContent
from sinnix_agent_gateway.action import Action, MutationControls, RequestControls
from sinnix_agent_gateway.actions import ALL_ACTIONS, visible
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.contracts import VerbFamily
from sinnix_agent_gateway.locators import (
    FileLocator,
    decode_file_ref,
    encode_file_ref,
)
from sinnix_agent_gateway.schemas import GatewayModel
from sinnix_agent_gateway.tooling import build_tool, tool_signature_matches


def config(tmp_path: Path) -> GatewayConfig:
    project = tmp_path / "project"
    project.mkdir()
    return GatewayConfig(
        state_dir=tmp_path / "state",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        approved_manifest_hash="approved-fixture-hash",
    )


def call(server, name: str, arguments: dict):
    async def invoke():
        return await server.call_tool(name, arguments)

    return anyio.run(invoke)


def structured(result) -> dict:
    if isinstance(result, CallToolResult):
        assert result.structured_content is not None
        return result.structured_content
    return result


def tiny_png() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return (
            struct.pack(">I", len(payload))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    raw = b"\x00\xff\x00\x00\xff"  # one row, filter 0, one RGB pixel
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def test_every_action_publishes_its_model_schema(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    runtime = server._sinnix_revision_publisher.runtime
    for action in ALL_ACTIONS:
        tool = build_tool(action, runtime)
        assert tool_signature_matches(tool, action), action.name
        schema = tool.parameters
        assert schema.get("additionalProperties") is False, action.name
        assert "parameters" not in schema["properties"], action.name
        assert tool.output_schema is None
        assert "data" in action.output_schema()["properties"]
        assert "title" not in schema
        assert action.examples, f"{action.name} declares no example"
        if action.family in {VerbFamily.CHANGE, VerbFamily.OPERATE, VerbFamily.RUN}:
            assert issubclass(action.Input, MutationControls)
            assert "idempotency_key" in schema["required"]
        else:
            assert not issubclass(action.Input, MutationControls)
            assert "idempotency_key" not in schema["properties"]


def test_tools_list_carries_typed_actions_next_to_verbs(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")

    async def names():
        return {tool.name: tool for tool in await server.list_tools()}

    tools = anyio.run(names)
    assert {"files.stat", "files.list", "files.read"} <= set(tools)
    read = tools["files.read"]
    locator = read.input_schema["$defs"]["FileLocator"]["properties"]
    assert "path" in locator and "ref" in locator
    assert read.input_schema["properties"]["representation"]["enum"] == [
        "auto",
        "text",
        "binary",
    ]
    assert read.annotations is not None and read.annotations.read_only_hint is True


def test_action_declaration_invariants() -> None:
    class Input(RequestControls):
        pass

    class Output(GatewayModel):
        ok: bool

    with pytest.raises(ValueError, match="dotted"):
        Action(
            name="plain",
            family=VerbFamily.QUERY,
            owner="x",
            summary="s",
            Input=Input,
            Output=Output,
            handler=lambda r, i: None,
        )
    with pytest.raises(ValueError, match="MutationControls"):
        Action(
            name="x.change",
            family=VerbFamily.CHANGE,
            owner="x",
            summary="s",
            Input=Input,
            Output=Output,
            handler=lambda r, i: None,
        )
    with pytest.raises(ValueError, match="mutation controls"):

        class Mutating(MutationControls):
            pass

        Action(
            name="x.read",
            family=VerbFamily.QUERY,
            owner="x",
            summary="s",
            Input=Mutating,
            Output=Output,
            handler=lambda r, i: None,
        )


def test_file_locator_round_trips_paths_and_refs() -> None:
    path = "/realm/tmp/example file.txt"
    ref = encode_file_ref(path)
    assert decode_file_ref(ref) == path
    assert FileLocator(path=path).resolve() == (path, ref)
    assert FileLocator(ref=ref).resolve() == (path, ref)
    with pytest.raises(ValueError, match="exactly one"):
        FileLocator()
    with pytest.raises(ValueError, match="exactly one"):
        FileLocator(path=path, ref=ref)


def test_files_actions_accept_paths_and_return_child_refs(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    root = tmp_path / "tree"
    root.mkdir()
    (root / "b.txt").write_text("beta\nline two\nline three\n")
    (root / "a.txt").write_text("alpha")
    (root / ".hidden").write_text("")
    (root / "sub").mkdir()

    listing = structured(call(server, "files.list", {"target": {"path": str(root)}}))
    assert listing["result"]["outcome"] == "ok", listing
    names = [entry["name"] for entry in listing["data"]["entries"]]
    assert names == ["a.txt", "b.txt", "sub"]
    child = listing["data"]["entries"][1]
    assert decode_file_ref(child["ref"]) == str(root / "b.txt")
    assert child["kind"] == "file" and child["bytes"] == 25

    hidden = structured(
        call(
            server,
            "files.list",
            {"target": {"path": str(root)}, "include_hidden": True},
        )
    )
    assert ".hidden" in [e["name"] for e in hidden["data"]["entries"]]

    stat = structured(call(server, "files.stat", {"target": {"ref": child["ref"]}}))
    assert stat["data"]["kind"] == "file"
    assert stat["data"]["sha256"] and stat["data"]["media_type"].startswith("text/")
    assert "files.read" in stat["data"]["affordances"]

    read = structured(call(server, "files.read", {"target": {"ref": child["ref"]}}))
    assert read["data"]["text"] == "beta\nline two\nline three\n"
    assert read["data"]["artifact"] is None

    lines = structured(
        call(
            server,
            "files.read",
            {"target": {"path": str(root / "b.txt")}, "line_start": 2, "line_count": 1},
        )
    )
    assert lines["data"]["text"] == "line two"
    assert lines["data"]["line_start"] == 2 and lines["data"]["line_end"] == 2
    assert lines["data"]["total_lines"] == 3 and lines["data"]["truncated"] is True

    missing = call(server, "files.stat", {"target": {"path": str(root / "nope")}})
    assert isinstance(missing, CallToolResult) and missing.is_error
    assert structured(missing)["error"]["code"] == "not_found"

    bad = call(server, "files.stat", {"target": {}})
    assert structured(bad)["error"]["code"] == "invalid_request"
    assert structured(bad)["error"]["details"]["problems"][0]["field"] == "target"


def test_image_read_returns_an_image_block(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    image = tmp_path / "pixel.png"
    image.write_bytes(tiny_png())
    result = call(server, "files.read", {"target": {"path": str(image)}})
    assert isinstance(result, CallToolResult) and not result.is_error
    blocks = [block for block in result.content if isinstance(block, ImageContent)]
    assert len(blocks) == 1
    assert blocks[0].mime_type == "image/png"
    assert base64.b64decode(blocks[0].data) == image.read_bytes()
    data = structured(result)["data"]
    assert data["text"] is None
    assert data["artifact"]["representation"] == "image"
    assert data["artifact"]["media_type"] == "image/png"
    assert data["artifact"]["sha256"] == data["sha256"]
    encoded = json.dumps(structured(result))
    assert "�" not in encoded


def test_observer_sees_read_actions_only() -> None:
    assert all(action.principals >= {"operator"} for action in ALL_ACTIONS)
    assert {a.name for a in visible("observer")} >= {"files.read"}


def test_files_search_paths_and_content(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    root = tmp_path / "corpus"
    (root / "deep").mkdir(parents=True)
    (root / "one.png").write_bytes(tiny_png())
    (root / "deep" / "two.PNG").write_bytes(tiny_png())
    (root / "notes.md").write_text("alpha\nscreenshot_probe here\nomega\n")
    (root / "deep" / "log.txt").write_text("nothing\n")

    pngs = structured(
        call(
            server,
            "files.search",
            {
                "roots": [{"path": str(root)}],
                "extensions": ["png"],
                "case_insensitive": True,
            },
        )
    )
    assert pngs["data"]["engine"] == "fd"
    assert sorted(m["name"] for m in pngs["data"]["matches"]) == ["one.png", "two.PNG"]
    assert all(decode_file_ref(m["ref"]) == m["path"] for m in pngs["data"]["matches"])

    by_glob = structured(
        call(
            server,
            "files.search",
            {"roots": [{"path": str(root)}], "name_glob": "*.md"},
        )
    )
    assert [m["name"] for m in by_glob["data"]["matches"]] == ["notes.md"]

    grep = structured(
        call(
            server,
            "files.search",
            {
                "roots": [{"path": str(root)}],
                "content_regex": "screenshot_probe",
                "context_lines": 1,
            },
        )
    )
    assert grep["data"]["engine"] == "rg"
    (match,) = grep["data"]["matches"]
    assert match["name"] == "notes.md" and match["match_count"] == 1
    numbers = [(line["line_number"], line["is_match"]) for line in match["lines"]]
    assert (2, True) in numbers and (1, False) in numbers

    limited = structured(
        call(
            server,
            "files.search",
            {"roots": [{"path": str(root)}], "kind": "file", "limit": 1},
        )
    )
    assert limited["data"]["returned"] == 1 and limited["data"]["truncated"] is True


def test_files_patch_modes_and_preconditions(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    target = tmp_path / "notes.md"
    target.write_text("one\ntwo\nthree\nfour\n")
    before = structured(call(server, "files.stat", {"target": {"path": str(target)}}))[
        "data"
    ]["sha256"]

    ranged = structured(
        call(
            server,
            "files.patch",
            {
                "target": {"path": str(target)},
                "edit": {
                    "mode": "range",
                    "start_line": 2,
                    "end_line": 3,
                    "replacement": "TWO\nTHREE",
                    "expected_text": "two\nthree",
                },
                "expected_sha256": before,
                "idempotency_key": "patch-1",
            },
        )
    )
    assert ranged["result"]["outcome"] == "ok", ranged
    assert target.read_text() == "one\nTWO\nTHREE\nfour\n"
    assert ranged["data"]["before_sha256"] == before
    assert ranged["data"]["after_sha256"] != before

    stale = call(
        server,
        "files.patch",
        {
            "target": {"path": str(target)},
            "edit": {
                "mode": "range",
                "start_line": 1,
                "end_line": 1,
                "replacement": "x",
            },
            "expected_sha256": before,
            "idempotency_key": "patch-2",
        },
    )
    assert structured(stale)["error"]["code"] == "precondition_failed"
    assert target.read_text() == "one\nTWO\nTHREE\nfour\n"

    unified = structured(
        call(
            server,
            "files.patch",
            {
                "target": {"path": str(target)},
                "edit": {
                    "mode": "unified",
                    "patch": "--- a\n+++ b\n@@ -1,2 +1,2 @@\n-one\n+ONE\n TWO\n@@ -4,1 +4,1 @@\n-four\n+FOUR\n",
                },
                "idempotency_key": "patch-3",
            },
        )
    )
    assert (
        unified["data"]["applied_hunks"] == 2
        and unified["data"]["rejected_hunks"] == []
    )
    assert target.read_text() == "ONE\nTWO\nTHREE\nFOUR\n"

    partial = structured(
        call(
            server,
            "files.patch",
            {
                "target": {"path": str(target)},
                "edit": {
                    "mode": "unified",
                    "patch": "@@ -1,1 +1,1 @@\n-ONE\n+1\n@@ -3,1 +3,1 @@\n-nope\n+never\n",
                },
                "idempotency_key": "patch-4",
            },
        )
    )
    assert partial["data"]["applied_hunks"] == 1
    assert partial["data"]["rejected_hunks"][0]["reason"] == "context does not match"
    assert target.read_text().startswith("1\n")

    dry = structured(
        call(
            server,
            "files.patch",
            {
                "target": {"path": str(target)},
                "edit": {
                    "mode": "range",
                    "start_line": 1,
                    "end_line": 1,
                    "replacement": "dry",
                },
                "dry_run": True,
                "idempotency_key": "patch-5",
            },
        )
    )
    assert dry["data"]["dry_run"] is True and target.read_text().startswith("1\n")

    replay = structured(
        call(
            server,
            "files.patch",
            {
                "target": {"path": str(target)},
                "edit": {
                    "mode": "range",
                    "start_line": 1,
                    "end_line": 1,
                    "replacement": "dry",
                },
                "dry_run": True,
                "idempotency_key": "patch-5",
            },
        )
    )
    assert replay["result"]["result_id"] == dry["result"]["result_id"]


def test_files_change_operations(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    root = tmp_path / "box"

    made = structured(
        call(
            server,
            "files.change",
            {
                "target": {"path": str(root / "nested")},
                "change": {"operation": "mkdir", "parents": True},
                "idempotency_key": "c1",
            },
        )
    )
    assert made["data"]["created"] is True and (root / "nested").is_dir()

    created = structured(
        call(
            server,
            "files.change",
            {
                "target": {"path": str(root / "a.txt")},
                "change": {"operation": "create", "content": "a\n"},
                "idempotency_key": "c2",
            },
        )
    )
    assert created["data"]["created"] is True and created["data"]["sha256"]
    again = call(
        server,
        "files.change",
        {
            "target": {"path": str(root / "a.txt")},
            "change": {"operation": "create", "content": "b\n"},
            "idempotency_key": "c3",
        },
    )
    assert structured(again)["error"]["code"] == "conflict"

    appended = structured(
        call(
            server,
            "files.change",
            {
                "target": {"path": str(root / "a.txt")},
                "change": {"operation": "append", "content": "more\n"},
                "idempotency_key": "c4",
            },
        )
    )
    assert appended["data"]["previous_sha256"] == created["data"]["sha256"]
    assert (root / "a.txt").read_text() == "a\nmore\n"

    moved = structured(
        call(
            server,
            "files.change",
            {
                "target": {"path": str(root / "a.txt")},
                "change": {
                    "operation": "move",
                    "destination": {"path": str(root / "nested" / "a.txt")},
                },
                "idempotency_key": "c5",
            },
        )
    )
    assert moved["data"]["removed"] is True
    assert decode_file_ref(moved["data"]["destination_ref"]) == str(
        root / "nested" / "a.txt"
    )
    assert not (root / "a.txt").exists() and (root / "nested" / "a.txt").exists()

    stale = call(
        server,
        "files.change",
        {
            "target": {"path": str(root / "nested" / "a.txt")},
            "change": {"operation": "replace", "content": "x"},
            "expected_sha256": "0" * 64,
            "idempotency_key": "c6",
        },
    )
    assert structured(stale)["error"]["code"] == "precondition_failed"

    removed = structured(
        call(
            server,
            "files.change",
            {
                "target": {"path": str(root / "nested" / "a.txt")},
                "change": {"operation": "remove"},
                "idempotency_key": "c7",
            },
        )
    )
    assert (
        removed["data"]["removed"] is True and not (root / "nested" / "a.txt").exists()
    )

    (tmp_path / "obs").mkdir()
    observer = create_server(config(tmp_path / "obs"), "observer")

    async def observer_tools():
        return {tool.name for tool in await observer.list_tools()}

    assert "files.change" not in anyio.run(observer_tools)


def test_gateway_status_and_catalog_are_typed(tmp_path: Path) -> None:
    server = create_server(config(tmp_path), "operator")
    status = structured(call(server, "gateway.status", {}))
    assert status["result"]["outcome"] == "ok", status
    assert status["data"]["principal"] == "operator"
    assert status["data"]["tool_count"] > 10
    assert status["data"]["route_preflight"]["status"] in {"ready", "degraded"}

    catalog = structured(call(server, "gateway.catalog", {"query": "screenshot"}))
    assert catalog["result"]["outcome"] == "ok", catalog
    names = [row["name"] for row in catalog["data"]["actions"]]
    assert "files.read" in names  # alias "screenshot file"
    assert catalog["data"]["catalog_sha256"] == status["data"]["action_catalog_hash"]

    everything = structured(call(server, "gateway.catalog", {"include_schemas": True}))
    rows = {row["name"]: row for row in everything["data"]["actions"]}
    assert rows["files.read"]["input_schema"]["properties"]["target"]
    assert "host_file" in {r["kind"] for r in everything["data"]["resources"]}
    host_file = next(
        r for r in everything["data"]["resources"] if r["kind"] == "host_file"
    )
    assert "files.read" in host_file["actions"]

    by_family = structured(call(server, "gateway.catalog", {"family": "change"}))
    assert {row["family"] for row in by_family["data"]["actions"]} == {"change"}
