"""Typed artifact actions."""

from __future__ import annotations

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


def test_principal_scoping(tmp_path: Path) -> None:
    operator = runtime(tmp_path)
    artifact_id = register(operator, "op.txt", b"x", "note")
    observer = Runtime.create(operator.config, "observer")
    assert call(observer, "artifacts.list", {}, BY_NAME)["data"]["artifacts"] == []
    denied = call(
        observer, "artifacts.read", {"target": {"artifact_id": artifact_id}}, BY_NAME
    )
    assert denied["error"]["code"] == "policy_denied"
