from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest

from sinnix_agent_gateway.artifacts import ArtifactService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.mcp_broker import McpBrokerError, McpBrokerService


class FakeTransport:
    async def __aenter__(self) -> tuple[object, object]:
        return object(), object()

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeSession:
    def __init__(self, _read: object, _write: object):
        pass

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def initialize(self) -> None:
        return None

    async def list_tools(self) -> object:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="lookup",
                    annotations=SimpleNamespace(read_only_hint=True),
                )
            ]
        )

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "content": [{"type": "text", "text": f"{name}:{arguments['query']}"}],
                "isError": False,
            }
        )


def broker_service(tmp_path: Path, principal_name: str, max_bytes: int = 262_144) -> McpBrokerService:
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        max_result_bytes=max_bytes,
        mcp_broker_servers={
            "fixture": {
                "description": "Fixture server",
                "transport": "stdio",
                "tier": "evidence",
                "brokered": True,
                "command": "fixture-mcp",
                "args": ["--fixture"],
                "env": {"FIXTURE": "1"},
            },
            "blocked": {
                "description": "Excluded server",
                "transport": "stdio",
                "tier": "browser",
                "brokered": False,
                "reason": "preserves browser isolation",
            },
        },
    )
    principal = Principal.for_name(principal_name)
    return McpBrokerService(config, principal, ArtifactService(config, principal))


def test_catalog_reports_registry_admission_without_connecting(tmp_path: Path) -> None:
    broker = broker_service(tmp_path, "observer")

    assert broker.catalog() == {
        "servers": [
            {
                "name": "blocked",
                "description": "Excluded server",
                "transport": "stdio",
                "tier": "browser",
                "brokered": False,
                "availability": "unavailable",
                "reason": "preserves browser isolation",
            },
            {
                "name": "fixture",
                "description": "Fixture server",
                "transport": "stdio",
                "tier": "evidence",
                "brokered": True,
                "availability": "unprobed",
            },
        ]
    }


def test_broker_enforces_live_read_only_tool_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    captured = []

    def stdio(parameters: object) -> FakeTransport:
        captured.append(parameters)
        return FakeTransport()

    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.stdio_client", stdio)
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)

    result = anyio.run(
        lambda: broker.call("fixture", "lookup", {"query": "fixture"}, write=False)
    )

    assert result["response"]["content"][0]["text"] == "lookup:fixture"
    assert captured[0].command == "fixture-mcp"
    assert captured[0].args == ["--fixture"]
    with pytest.raises(McpBrokerError, match="declared read-only"):
        anyio.run(
            lambda: broker.call("fixture", "lookup", {"query": "fixture"}, write=True)
        )


def test_observer_broker_runs_upstream_in_read_only_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "observer")
    captured = []

    def stdio(parameters: object) -> FakeTransport:
        captured.append(parameters)
        return FakeTransport()

    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.stdio_client", stdio)
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)

    anyio.run(lambda: broker.call("fixture", "lookup", {"query": "fixture"}, write=False))

    assert captured[0].command == broker.config.systemd_run_command
    assert "--property=ReadOnlyPaths=/" in captured[0].args
    assert "--property=PrivateNetwork=true" in captured[0].args
    assert "--property=InaccessiblePaths=/run/user" in captured[0].args
    separator = captured[0].args.index("--")
    assert captured[0].args[separator + 1 :] == ["fixture-mcp", "--fixture"]


def test_observer_broker_stops_failed_read_only_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "observer")
    stopped = []
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client", lambda _params: FakeTransport()
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)
    monkeypatch.setattr(broker, "_stop", stopped.append)

    with pytest.raises(McpBrokerError, match="does not expose"):
        anyio.run(lambda: broker.call("fixture", "missing", {}, write=False))

    assert len(stopped) == 1
    assert stopped[0].startswith("sinnix-gateway-mcp-read-")


def test_broker_artifactizes_large_upstream_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "observer", max_bytes=10)
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.stdio_client", lambda _params: FakeTransport())
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)

    result = anyio.run(
        lambda: broker.call("fixture", "lookup", {"query": "fixture"}, write=False)
    )
    artifact = broker.artifacts.read(result["artifact_id"])

    assert result["truncated"] is True
    assert result["artifact"]["receipt"]["target"] == {
        "server": "fixture",
        "tool": "lookup",
    }
    assert artifact["content_type"] == "application/json"
    assert "source" not in artifact


def test_broker_rejects_excluded_server_before_launch(tmp_path: Path) -> None:
    broker = broker_service(tmp_path, "operator")

    with pytest.raises(McpBrokerError, match="browser isolation"):
        anyio.run(lambda: broker.call("blocked", "lookup", {}, write=False))


def test_gateway_config_loads_broker_servers(tmp_path: Path) -> None:
    config_path = tmp_path / "gateway.json"
    config_path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {},
                "mcpBrokerServers": {"fixture": {"brokered": True}},
            }
        )
    )

    assert GatewayConfig.load(config_path).mcp_broker_servers == {
        "fixture": {"brokered": True}
    }
