"""Typed MCP broker actions with a fake upstream session."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sinnix_agent_gateway.actions import mcp_tools
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.locators import McpToolLocator
from sinnix_agent_gateway.runtime import Runtime
from test_actions_machine import call
from test_mcp_broker import FakeSession, FakeTransport

BY_NAME = {action.name: action for action in mcp_tools.ACTIONS}


class WriteSession(FakeSession):
    async def list_tools(self) -> object:
        tools = (await super().list_tools()).tools
        tools.append(
            SimpleNamespace(
                name="refresh",
                description="Fixture refresh",
                inputSchema={"type": "object"},
                annotations=None,
            )
        )
        return SimpleNamespace(tools=tools)

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
    )
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


def test_observer_cannot_change_and_timeout_is_diagnosable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = runtime(tmp_path, "observer", monkeypatch)
    denied = call(
        rt,
        "mcp.change",
        {"target": {"server": "fixture", "tool": "refresh"}, "idempotency_key": "k"},
        BY_NAME,
    )
    assert denied["error"]["code"] == "policy_denied"

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
