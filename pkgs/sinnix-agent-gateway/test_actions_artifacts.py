"""Typed artifact actions."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

import pytest
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


def test_artifact_without_snapshot_is_retained_from_matching_source(
    tmp_path: Path,
) -> None:
    """Fails if a pre-snapshot ref breaks, or is served from a changed source."""
    rt = runtime(tmp_path)
    kept = register(rt, "kept.txt", b"registered", "note")
    changed = register(rt, "changed.txt", b"registered", "note")
    for artifact_id in (kept, changed):
        (rt.artifacts.root / artifact_id / "content").unlink()
    captures = rt.config.state_dir / "captures"
    (captures / "changed.txt" / "changed.txt").write_bytes(b"edited later")
    request = {"representation": "text"}

    result = call(
        rt, "artifacts.read", {"target": {"artifact_id": kept}, **request}, BY_NAME
    )
    assert result["data"]["text"] == "registered"
    assert (rt.artifacts.root / kept / "content").read_bytes() == b"registered"

    result = call(
        rt, "artifacts.read", {"target": {"artifact_id": changed}, **request}, BY_NAME
    )
    assert result["error"]["code"] == "not_found"
    assert not (rt.artifacts.root / changed / "content").exists()


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


def test_paged_binary_read_hashes_the_snapshot_once(
    tmp_path: Path, monkeypatch
) -> None:
    """Fails if each page of a binary read rehashes the whole artifact."""
    from sinnix_agent_gateway import artifacts as artifact_module

    rt = runtime(tmp_path)
    artifact_id = register(rt, "paged.bin", bytes(range(256)) * 64, "note")
    hashed: list[Path] = []
    real = artifact_module._sha256

    def counting(path: Path) -> str:
        hashed.append(path)
        return real(path)

    monkeypatch.setattr(artifact_module, "_sha256", counting)
    offset = 0
    while offset is not None:
        data = call(
            rt,
            "artifacts.read",
            {
                "target": {"artifact_id": artifact_id},
                "representation": "binary",
                "offset": offset,
                "max_bytes": 4096,
            },
            BY_NAME,
        )["data"]
        offset = data["next_offset"]
    assert len(hashed) <= 1


@pytest.mark.parametrize("representation", ["text", "binary"])
@pytest.mark.parametrize("bound", [4096, 262144])
def test_oversized_reads_stay_on_original_artifact_with_lossless_pages(
    tmp_path, representation, bound
):
    rt = Runtime.create(
        GatewayConfig(
            state_dir=tmp_path / "state", projects={}, max_result_bytes=bound
        ),
        "operator",
    )
    original = ('🙂"\\\n\t' * 30000).encode()
    artifact_id = register(rt, "large.txt", original, "note")
    ref = f"sinnix://artifacts/{artifact_id}"
    offset = 0
    chunks = []
    while True:
        request = {
            "target": {"ref": ref},
            "representation": representation,
            "offset": offset,
            "max_bytes": 10000000,
        }
        response = call(rt, "artifacts.read", request, BY_NAME)
        assert response["result"]["outcome"] == "ok", response
        assert (
            len(
                json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode()
            )
            <= bound
        )
        data = response["data"]
        assert data["ref"] == ref and data["artifact_id"] == artifact_id
        assert (
            "artifact_refs" not in response["meta"]
            or not response["meta"]["artifact_refs"]
        )
        assert data["offset"] == offset
        chunk = (
            base64.b64decode(data["base64"], validate=True)
            if representation == "binary"
            else data["text"].encode()
        )
        assert data["returned_bytes"] == len(chunk)
        assert data["sha256"] == hashlib.sha256(original).hexdigest()
        assert data["bytes"] == len(original)
        chunks.append(chunk)
        if offset == 0:
            replay = call(rt, "artifacts.read", request, BY_NAME)
            assert replay["data"] == data
        if data["next_offset"] is None:
            assert not data["truncated"]
            break
        assert data["next_offset"] == offset + len(chunk) > offset
        offset = data["next_offset"]
    assert len(chunks) > 1 and b"".join(chunks) == original
    assert len(list(rt.artifacts.root.glob("*/metadata.json"))) == 1


@pytest.mark.parametrize("representation", ["text", "binary"])
def test_cached_snapshot_rewrite_with_restored_mtime_is_refused(
    tmp_path, representation
):
    rt = runtime(tmp_path)
    artifact_id = register(rt, "warm-cache.txt", b"registered", "note")
    first = call(
        rt,
        "artifacts.read",
        {
            "target": {"artifact_id": artifact_id},
            "representation": representation,
            "max_bytes": 4,
        },
        BY_NAME,
    )
    assert first["error"] is None
    content = rt.artifacts.root / artifact_id / "content"
    before = content.stat()
    content.write_bytes(b"corrupted!")
    os.utime(content, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert content.stat().st_size == before.st_size
    assert content.stat().st_mtime_ns == before.st_mtime_ns
    result = call(
        rt,
        "artifacts.read",
        {
            "target": {"artifact_id": artifact_id},
            "representation": representation,
            "offset": 4,
        },
        BY_NAME,
    )
    assert result["error"]["code"] == "invalid_request"
