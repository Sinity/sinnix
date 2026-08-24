from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence, TextIO

import anyio
import pytest

from sinnix_agent_gateway.artifacts import ArtifactService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_mcp.execution import (
    EnvironmentProfile,
    ExecutionProfile,
    ExecutionResult,
    OwnerExecution,
)
from sinnix_agent_gateway.mcp_broker import McpBrokerError, McpBrokerService


class FakeTransport:
    async def __aenter__(self) -> tuple[object, object]:
        return object(), object()

    async def __aexit__(self, *args: object) -> None:
        return None


class RecordingExecution(OwnerExecution):
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], ExecutionProfile]] = []

    def run(self, command: Sequence[str], profile: ExecutionProfile) -> ExecutionResult:
        normalized = tuple(command)
        self.calls.append((normalized, profile))
        return ExecutionResult(normalized, 0, b"", b"")


class FailingTransport:
    def __init__(self, stderr: TextIO):
        self.stderr = stderr

    async def __aenter__(self) -> tuple[object, object]:
        self.stderr.write("upstream fixture failed\n")
        self.stderr.flush()
        raise OSError("fixture launch failure")

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
                    description="Fixture lookup",
                    inputSchema={"type": "object", "properties": {"query": {"type": "string"}}},
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
                "observerWritablePaths": ["%t/fixture-locks"],
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


def test_broker_stop_uses_the_shared_execution_kernel(tmp_path: Path) -> None:
    broker = broker_service(tmp_path, "observer")
    execution = RecordingExecution()
    broker.execution = execution

    broker._stop("sinnix-gateway-mcp-read-fixture.service")

    command, profile = execution.calls[0]
    assert command == (
        broker.config.systemctl_command,
        "--user",
        "stop",
        "sinnix-gateway-mcp-read-fixture.service",
    )
    assert profile.route.name == "mcp-broker-cancel"
    assert profile.route.environment_profile == EnvironmentProfile.USER_BUS_OPTIONAL
    assert profile.timeout_seconds == 5


def test_observer_catalog_reports_missing_user_bus_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    broker = broker_service(tmp_path, "observer")
    catalog = anyio.run(broker.catalog)

    fixture = next(server for server in catalog["servers"] if server["name"] == "fixture")
    assert fixture["availability"] == "unavailable"
    assert fixture["failure_class"] == "environment_unavailable"


class LargeSchemaSession(FakeSession):
    async def list_tools(self) -> object:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="lookup",
                    description="Fixture lookup",
                    inputSchema={
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "x" * 8_000}},
                    },
                    annotations=SimpleNamespace(read_only_hint=True),
                )
            ]
        )


def test_catalog_artifactizes_an_oversized_tool_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "observer", max_bytes=4_096)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", LargeSchemaSession)

    catalog = anyio.run(broker.catalog)
    assert len(json.dumps(catalog, separators=(",", ":")).encode()) <= broker.config.max_result_bytes
    fixture = next(server for server in catalog["servers"] if server["name"] == "fixture")
    tool = fixture["tools"][0]
    assert tool["input_schema"]["x-sinnix-schema-truncated"] is True
    assert tool["input_schema_artifact"]["ref"].startswith("sinnix://artifacts/")
    assert tool["input_schema_bytes"] > broker.config.max_result_bytes


def test_catalog_probes_admitted_servers_and_keeps_exclusions_static(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)

    assert anyio.run(broker.catalog) == {
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
                "availability": "available",
                "tool_count": 1,
                "read_only_tool_count": 1,
                "tools": [{"name": "lookup", "ref": "sinnix://mcp/fixture/tools/lookup", "description": "Fixture lookup", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}, "effect": "read"}],
            },
        ]
    }


def write_stdio_fixture(tmp_path: Path, source: str) -> Path:
    fixture = tmp_path / "fixture_mcp.py"
    fixture.write_text(source)
    return fixture


def test_catalog_probes_real_stdio_mcp_fixture(tmp_path: Path) -> None:
    broker = broker_service(tmp_path, "operator")
    fixture = write_stdio_fixture(
        tmp_path,
        """import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    if request[\"method\"] == \"initialize\":
        result = {
            \"protocolVersion\": request[\"params\"][\"protocolVersion\"],
            \"capabilities\": {\"tools\": {}},
            \"serverInfo\": {\"name\": \"fixture\", \"version\": \"1\"},
        }
    elif request[\"method\"] == \"tools/list\":
        result = {
            \"tools\": [{
                \"name\": \"fixture_read\",
                \"description\": \"Fixture read tool\",
                \"inputSchema\": {\"type\": \"object\", \"properties\": {}},
                \"annotations\": {\"readOnlyHint\": True},
            }]
        }
    else:
        continue
    print(json.dumps({\"jsonrpc\": \"2.0\", \"id\": request[\"id\"], \"result\": result}), flush=True)
""",
    )
    broker.config.mcp_broker_servers["fixture"].update(
        command=sys.executable, args=[str(fixture)]
    )

    result = anyio.run(broker.catalog)

    assert result["servers"][1] == {
        "name": "fixture",
        "description": "Fixture server",
        "transport": "stdio",
        "tier": "evidence",
        "brokered": True,
        "availability": "available",
        "tool_count": 1,
        "read_only_tool_count": 1,
        "tools": [{"name": "fixture_read", "ref": "sinnix://mcp/fixture/tools/fixture_read", "description": "Fixture read tool", "input_schema": {"type": "object", "properties": {}}, "effect": "read"}],
    }


def test_catalog_attests_real_stdio_probe_failure(tmp_path: Path) -> None:
    broker = broker_service(tmp_path, "operator")
    fixture = write_stdio_fixture(
        tmp_path,
        """import sys
sys.stderr.write(\"fixture launch failed\\n\")
sys.exit(17)
""",
    )
    broker.config.mcp_broker_servers["fixture"].update(
        command=sys.executable, args=[str(fixture)]
    )

    result = anyio.run(broker.catalog)
    fixture_result = result["servers"][1]

    assert fixture_result["availability"] == "unavailable"
    assert fixture_result["failure_class"] == "upstream_unavailable"
    artifact = broker.artifacts.read(fixture_result["diagnostic_artifact_id"])
    assert base64.b64decode(artifact["base64"]) == b"fixture launch failed\n"


def test_broker_enforces_live_read_only_tool_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    captured = []

    def stdio(parameters: object, **_kwargs: object) -> FakeTransport:
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
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    captured = []

    def stdio(parameters: object, **_kwargs: object) -> FakeTransport:
        captured.append(parameters)
        return FakeTransport()

    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.stdio_client", stdio)
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)

    anyio.run(lambda: broker.call("fixture", "lookup", {"query": "fixture"}, write=False))

    assert captured[0].command == broker.config.systemd_run_command
    assert "--property=ReadOnlyPaths=/" in captured[0].args
    assert "--property=ReadWritePaths=/run/user/1000/fixture-locks" in captured[0].args
    assert "--property=PrivateNetwork=true" in captured[0].args
    assert "--property=InaccessiblePaths=/run/user" not in captured[0].args
    assert "--setenv=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus" in captured[0].args
    assert "--setenv=XDG_RUNTIME_DIR=/run/user/1000" in captured[0].args
    assert captured[0].env["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/run/user/1000/bus"
    assert captured[0].env["XDG_RUNTIME_DIR"] == "/run/user/1000"
    separator = captured[0].args.index("--")
    assert captured[0].args[separator + 1 :] == ["fixture-mcp", "--fixture"]


def test_observer_broker_stops_failed_read_only_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "observer")
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    stopped = []
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client", lambda _params, **_kwargs: FakeTransport()
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)
    monkeypatch.setattr(broker, "_stop", stopped.append)

    with pytest.raises(McpBrokerError, match="does not expose"):
        anyio.run(lambda: broker.call("fixture", "missing", {}, write=False))

    assert len(stopped) == 1
    assert stopped[0].startswith("sinnix-gateway-mcp-read-")


def test_broker_attests_upstream_stderr_on_transport_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")

    def stdio(_parameters: object, *, errlog: TextIO) -> FailingTransport:
        return FailingTransport(errlog)

    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.stdio_client", stdio)

    with pytest.raises(McpBrokerError, match="diagnostic artifact"):
        anyio.run(lambda: broker.call("fixture", "lookup", {}, write=False))

    artifacts = broker.artifacts.list()["artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["kind"] == "mcp-stderr"
    assert artifacts[0]["owner_id"] == "fixture"
    artifact = broker.artifacts.read(artifacts[0]["artifact_id"])
    assert base64.b64decode(artifact["base64"]) == b"upstream fixture failed\n"


def test_broker_artifactizes_large_upstream_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "observer", max_bytes=10)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.stdio_client", lambda _params, **_kwargs: FakeTransport())
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
