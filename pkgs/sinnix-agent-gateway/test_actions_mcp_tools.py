"""Typed MCP broker actions with a fake upstream session."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from mcp.types import ImageContent
from sinnix_agent_gateway.actions import mcp_tools
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.locators import McpToolLocator
from sinnix_agent_gateway.runtime import Runtime
from test_actions_machine import call
from test_mcp_broker import FakeSession, FakeTransport

BY_NAME = {action.name: action for action in mcp_tools.ACTIONS}


def test_offline_owner_keeps_stale_contract_in_typed_catalogs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = runtime(tmp_path, "operator", monkeypatch)
    call(rt, "mcp.tools", {}, BY_NAME)

    async def failed(*_args: object) -> dict:
        return {"availability": "unavailable", "reason": "fixture offline"}

    monkeypatch.setattr(rt.mcp_broker, "_probe", failed)
    tools = call(rt, "mcp.tools", {"text": "lookup"}, BY_NAME)["data"]
    assert tools["servers_unavailable"]["fixture"] == "fixture offline"
    assert tools["tools"][0]["schema_stale"] is True
    assert tools["tools"][0]["availability"] == "unavailable"
    servers = call(rt, "mcp.servers", {"servers": ["fixture"]}, BY_NAME)["data"]
    assert servers["servers"][0]["last_successful_probe"]
    assert servers["servers"][0]["schema_complete"] is True
    from sinnix_agent_gateway.actions.gateway import ACTIONS

    catalog = call(
        rt,
        "gateway.catalog",
        {"query": "lookup"},
        {action.name: action for action in ACTIONS},
    )["data"]
    assert catalog["mcp_tools"][0]["schema_stale"] is True
    assert "mcp.fixture" in catalog["mcp_unavailable"]


class WriteSession(FakeSession):
    async def list_tools(self, *, params: object | None = None) -> object:
        tools = (await super().list_tools(params=params)).tools
        tools.append(
            SimpleNamespace(
                name="refresh",
                description="Fixture refresh",
                inputSchema={"type": "object"},
                annotations=None,
            )
        )
        return SimpleNamespace(tools=tools, next_cursor=None)

    async def call_tool(self, name, arguments):
        return SimpleNamespace(
            model_dump=lambda **_: {
                "content": [{"type": "text", "text": name}],
                "isError": False,
            }
        )


def runtime(
    tmp_path: Path,
    principal: str,
    monkeypatch: pytest.MonkeyPatch,
    session=WriteSession,
    max_result_bytes: int = 262_144,
) -> Runtime:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client", lambda _p, **_k: FakeTransport()
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", session)
    cfg = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        max_result_bytes=max_result_bytes,
        ops_socket_path=tmp_path / "ops.sock",
        mcp_broker_servers={
            "fixture": {
                "description": "Fixture",
                "transport": "stdio",
                "tier": "evidence",
                "brokered": True,
                "command": "fixture-mcp",
                "args": [],
                "env": {},
            },
            "blocked": {
                "description": "Excluded",
                "transport": "stdio",
                "tier": "browser",
                "brokered": False,
                "reason": "preserves browser isolation",
            },
        },
    )
    return Runtime.create(cfg, principal)


def test_locator_forms() -> None:
    assert McpToolLocator(server="a", tool="b").resolve() == (
        "a",
        "b",
        "sinnix://mcp/a/tools/b",
    )
    assert McpToolLocator(ref="sinnix://mcp/a/tools/b").resolve() == (
        "a",
        "b",
        "sinnix://mcp/a/tools/b",
    )
    with pytest.raises(ValueError):
        McpToolLocator(server="a")


def test_servers_tools_call_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = runtime(tmp_path, "operator", monkeypatch)
    servers = {
        row["name"]: row
        for row in call(rt, "mcp.servers", {}, BY_NAME)["data"]["servers"]
    }
    assert (
        servers["fixture"]["availability"] == "available"
        and servers["fixture"]["tool_count"] == 2
    ), servers["fixture"]
    assert (
        servers["fixture"]["latency_ms"] is not None
        and servers["fixture"]["last_successful_probe"]
    )
    assert (
        servers["blocked"]["availability"] == "unavailable"
        and servers["blocked"]["brokered"] is False
    )
    unknown = call(rt, "mcp.servers", {"servers": ["nope"]}, BY_NAME)
    assert unknown["error"]["code"] == "not_found"

    tools = call(rt, "mcp.tools", {"text": "lookup"}, BY_NAME)["data"]
    assert [row["ref"] for row in tools["tools"]] == [
        "sinnix://mcp/fixture/tools/lookup"
    ]
    assert (
        tools["tools"][0]["effect"] == "read"
        and "query" in tools["tools"][0]["input_schema"]["properties"]
    )
    assert tools["servers_unavailable"] == {"blocked": "preserves browser isolation"}
    assert (
        call(rt, "mcp.tools", {"effect": "change"}, BY_NAME)["data"]["tools"][0]["name"]
        == "refresh"
    )

    read = call(
        rt,
        "mcp.call",
        {
            "target": {"server": "fixture", "tool": "lookup"},
            "arguments": {"query": "x"},
        },
        BY_NAME,
    )
    assert read["data"]["response"]["content"][0]["text"] == "lookup"
    refused = call(
        rt,
        "mcp.call",
        {"target": {"server": "fixture", "tool": "refresh"}, "arguments": {}},
        BY_NAME,
    )
    assert refused["error"]["code"] == "invalid_request"
    missing = call(
        rt,
        "mcp.call",
        {"target": {"server": "fixture", "tool": "absent"}, "arguments": {}},
        BY_NAME,
    )
    assert missing["error"]["code"] == "not_found"
    write = call(
        rt,
        "mcp.change",
        {
            "target": {"ref": "sinnix://mcp/fixture/tools/refresh"},
            "arguments": {},
            "idempotency_key": "refresh-1",
        },
        BY_NAME,
    )
    assert write["result"]["outcome"] == "ok" and write["data"]["mode"] == "write"


def test_tools_filters_complete_server_catalog_before_page_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class LargeCatalogSession(FakeSession):
        async def list_tools(self, *, params: object | None = None) -> object:
            tools = [
                SimpleNamespace(
                    name=f"tool_{index:04d}",
                    description="Fixture catalog entry " + ("x" * 120),
                    inputSchema={"type": "object", "properties": {}},
                    annotations=SimpleNamespace(read_only_hint=True),
                )
                for index in range(120)
            ]
            return SimpleNamespace(tools=tools, next_cursor=None)

    rt = runtime(
        tmp_path, "operator", monkeypatch, LargeCatalogSession, max_result_bytes=4_096
    )

    result = call(
        rt,
        "mcp.tools",
        {"server": "fixture", "text": "tool_0119"},
        BY_NAME,
    )

    assert result["data"]["total"] == 1
    assert [row["name"] for row in result["data"]["tools"]] == ["tool_0119"]
    assert result["data"]["truncated"] is False


def test_tools_reports_incomplete_upstream_coverage_for_no_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_mcp_broker import RepeatingCursorSession

    rt = runtime(tmp_path, "operator", monkeypatch, RepeatingCursorSession)
    result = call(
        rt,
        "mcp.tools",
        {"server": "fixture", "text": "absent"},
        BY_NAME,
    )

    assert result["data"]["tools"] == []
    assert result["data"]["truncated"] is True
    assert "fixture" in result["data"]["coverage_incomplete"]


def test_broker_timeout_is_diagnosable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = runtime(tmp_path, "operator", monkeypatch)

    class Hanging(FakeSession):
        async def initialize(self) -> None:
            import asyncio

            raise asyncio.TimeoutError

    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", Hanging)
    row = {
        r["name"]: r
        for r in call(rt, "mcp.servers", {"servers": ["fixture"]}, BY_NAME)["data"][
            "servers"
        ]
    }["fixture"]
    assert row["failure_class"] == "timeout" and row["last_successful_probe"] is None


def test_self_broker_routes_direct_read_with_content_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = runtime(tmp_path, "operator", monkeypatch)
    image = tmp_path / "fixture.png"
    image.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb7\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    async def invoke() -> object:
        return await mcp_tools._call(
            rt,
            mcp_tools.CallInput(
                target={"server": "sinnix-agent-gateway", "tool": "files.read"},
                arguments={"target": {"path": str(image)}},
            ),
        )

    result = anyio.run(invoke)
    assert isinstance(result, mcp_tools.ActionResult)
    assert result.data.response["media_type"] == "image/png"
    assert isinstance(result.blocks[0], ImageContent)
