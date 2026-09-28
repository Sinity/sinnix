"""Typed artifact actions."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from mcp.types import ImageContent
from sinnix_agent_gateway.actions import artifacts
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.runtime import Runtime
from sinnix_agent_gateway.tooling import build_tool
from test_actions import tiny_png
from test_actions_machine import call

BY_NAME = {action.name: action for action in artifacts.ACTIONS}


def runtime(tmp_path: Path, principal: str = "operator") -> Runtime:
    return Runtime.create(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            ops_socket_path=tmp_path / "ops.sock",
        ),
        principal,
    )


def register(rt: Runtime, name: str, data: bytes, kind: str) -> str:
    directory = rt.config.state_dir / "captures" / name
    directory.mkdir(parents=True)
    source = directory / name
    source.write_bytes(data)
    rt.artifacts.attest_capture(
        directory, source="test", target={"n": name}, files=[source]
    )
    return rt.artifacts.register(source, kind=kind, owner_id="test")


def test_list_get_read_text_and_image(tmp_path: Path) -> None:
    rt = runtime(tmp_path)
    text_id = register(rt, "note.txt", b"hello artifact\n", "note")
    image_id = register(rt, "shot.png", tiny_png(), "screenshot")
    listing = call(rt, "artifacts.list", {}, BY_NAME)["data"]
    assert {row["artifact_id"] for row in listing["artifacts"]} == {text_id, image_id}
    assert (
        call(rt, "artifacts.list", {"kind": "note"}, BY_NAME)["data"]["artifacts"][0][
            "ref"
        ]
        == f"sinnix://artifacts/{text_id}"
    )

    meta = call(rt, "artifacts.get", {"target": {"artifact_id": text_id}}, BY_NAME)[
        "data"
    ]
    assert (
        meta["content_type"] == "text/plain"
        and meta["bytes"] == 15
        and meta["source_name"] == "note.txt"
    )

    text = call(
        rt,
        "artifacts.read",
        {"target": {"ref": f"sinnix://artifacts/{text_id}"}, "max_bytes": 5},
        BY_NAME,
    )["data"]
    assert text["text"] == "hello" and text["truncated"] and text["next_offset"] == 5

    tool = build_tool(BY_NAME["artifacts.read"], rt)
    import anyio

    async def invoke():
        return await tool.fn(target={"artifact_id": image_id})

    result = anyio.run(invoke)
    assert result.structured_content["data"]["artifact"]["representation"] == "image"
    assert any(isinstance(block, ImageContent) for block in result.content)

    missing = call(
        rt,
        "artifacts.get",
        {"target": {"artifact_id": "00000000-0000-0000-0000-000000000000"}},
        BY_NAME,
    )
    assert missing["error"]["code"] == "not_found"


def test_text_chunks_preserve_utf8(tmp_path: Path) -> None:
    rt = runtime(tmp_path)
    original = "a🙂ż日" * 12
    artifact_id = register(rt, "unicode.txt", original.encode(), "note")
    parts = []
    offset = 0
    while True:
        data = call(
            rt,
            "artifacts.read",
            {
                "target": {"artifact_id": artifact_id},
                "offset": offset,
                "max_bytes": 4,
            },
            BY_NAME,
        )["data"]
        parts.append(data["text"])
        assert data["returned_bytes"] == len(data["text"].encode())
        if data["next_offset"] is None:
            break
        assert data["next_offset"] > offset
        offset = data["next_offset"]
    assert "".join(parts) == original


def test_binary_chunks_reassemble_registered_artifact(tmp_path: Path) -> None:
    rt = runtime(tmp_path)
    original = bytes(range(251)) * 37
    artifact_id = register(rt, "archive.zip", original, "project-export")
    parts = []
    offset = 0
    while True:
        data = call(
            rt,
            "artifacts.read",
            {
                "target": {"artifact_id": artifact_id},
                "representation": "binary",
                "offset": offset,
                "max_bytes": 701,
            },
            BY_NAME,
        )["data"]
        chunk = base64.b64decode(data["base64"], validate=True)
        assert len(chunk) == data["returned_bytes"]
        assert data["bytes"] == len(original)
        assert data["sha256"] == hashlib.sha256(original).hexdigest()
        parts.append(chunk)
        if data["next_offset"] is None:
            break
        assert data["next_offset"] == offset + len(chunk)
        offset = data["next_offset"]
    assert b"".join(parts) == original


def test_registered_artifact_is_bound_to_snapshot_not_mutable_source(
    tmp_path: Path,
) -> None:
    """Fails if a source edit silently changes bytes returned by an existing ref."""
    rt = runtime(tmp_path)
    artifact_id = register(rt, "mutable.txt", b"registered", "note")
    source = Path(rt.artifacts._metadata(artifact_id)["source"])
    source.write_bytes(b"changed source")
    result = call(
        rt,
        "artifacts.read",
        {"target": {"artifact_id": artifact_id}, "representation": "binary"},
        BY_NAME,
    )
    assert base64.b64decode(result["data"]["base64"]) == b"registered"


def test_text_read_serves_snapshot_after_source_edit(tmp_path: Path) -> None:
    """Fails if the text representation reads the mutable registered source."""
    rt = runtime(tmp_path)
    artifact_id = register(rt, "mutable.txt", b"registered", "note")
    source = Path(rt.artifacts._metadata(artifact_id)["source"])
    source.write_bytes(b"changed source")
    result = call(
        rt,
        "artifacts.read",
        {"target": {"artifact_id": artifact_id}, "representation": "text"},
        BY_NAME,
    )
    assert result["data"]["text"] == "registered"
    assert result["data"]["bytes"] == len(b"registered")


def test_artifact_without_snapshot_is_refused(tmp_path: Path) -> None:
    """Fails if a reference with no retained snapshot falls back to its source."""
    rt = runtime(tmp_path)
    artifact_id = register(rt, "legacy.txt", b"registered", "note")
    (rt.artifacts.root / artifact_id / "content").unlink()
    result = call(
        rt,
        "artifacts.read",
        {"target": {"artifact_id": artifact_id}, "representation": "text"},
        BY_NAME,
    )
    assert result["error"]["code"] == "not_found"


def test_mutated_artifact_snapshot_is_refused(tmp_path: Path) -> None:
    """Fails if altered retained bytes are served under the registered digest."""
    rt = runtime(tmp_path)
    artifact_id = register(rt, "tampered.txt", b"registered", "note")
    metadata = rt.artifacts._metadata(artifact_id)
    Path(metadata["_content"]).write_bytes(b"tampered!")
    result = call(
        rt,
        "artifacts.read",
        {"target": {"artifact_id": artifact_id}, "representation": "binary"},
        BY_NAME,
    )
    assert result["error"]["code"] == "invalid_request"


def test_filtered_listing_continues_immutable_snapshot(tmp_path: Path) -> None:
    rt = runtime(tmp_path)
    expected = {register(rt, f"note-{i}.txt", b"note", "note") for i in range(3)}
    for i in range(4):
        register(rt, f"other-{i}.txt", b"other", "other")
    request = {"kind": "note", "limit": 1}
    result = call(rt, "artifacts.list", request, BY_NAME)
    assert result["page"]["total"] == 3
    found = {result["data"]["artifacts"][0]["artifact_id"]}
    register(rt, "late.txt", b"late", "note")
    while result["page"]["next_cursor"]:
        result = call(
            rt,
            "artifacts.list",
            {**request, "cursor": result["page"]["next_cursor"]},
            BY_NAME,
        )
        found.update(row["artifact_id"] for row in result["data"]["artifacts"])
    assert found == expected
