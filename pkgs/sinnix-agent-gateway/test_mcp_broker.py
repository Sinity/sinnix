from __future__ import annotations

import asyncio
import base64
import json
import fcntl
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence, TextIO

import anyio
import pytest
from sinnix_agent_gateway.artifacts import ArtifactService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.mcp_broker import (
    McpBrokerDeadlineError,
    McpBrokerError,
    McpBrokerService,
    McpBrokerTimeoutError,
)
from sinnix_agent_gateway.owner_execution import (
    ExecutionProfile,
    ExecutionResult,
    OwnerExecution,
)


class FakeTransport:
    async def __aenter__(self) -> tuple[object, object]:
        return object(), object()

    async def __aexit__(self, *args: object) -> None:
        return None


class RecordingExecution(OwnerExecution):
    def __init__(self, base_environment: dict[str, str] | None = None) -> None:
        super().__init__(base_environment)
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

    async def list_tools(self, *, params: object | None = None) -> object:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="lookup",
                    description="Fixture lookup",
                    inputSchema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                    annotations=SimpleNamespace(read_only_hint=True),
                )
            ],
            next_cursor=None,
        )

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "content": [{"type": "text", "text": f"{name}:{arguments['query']}"}],
                "isError": False,
            }
        )


class TwoPageSession(FakeSession):
    calls: list[str | None] = []

    async def list_tools(self, *, params: object | None = None) -> object:
        cursor = getattr(params, "cursor", None)
        self.calls.append(cursor)
        if cursor is None:
            return SimpleNamespace(tools=[tool("first")], next_cursor="page-2")
        if cursor == "page-2":
            return SimpleNamespace(tools=[tool("second")], next_cursor=None)
        raise AssertionError(f"unexpected cursor: {cursor!r}")


def tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=f"Fixture {name} tool",
        inputSchema={"type": "object", "properties": {"query": {"type": "string"}}},
        annotations=SimpleNamespace(read_only_hint=True),
    )


class RepeatingCursorSession(FakeSession):
    calls: list[str | None] = []

    async def list_tools(self, *, params: object | None = None) -> object:
        cursor = getattr(params, "cursor", None)
        self.calls.append(cursor)
        return SimpleNamespace(tools=[tool("first")], next_cursor="loop")


def test_concurrent_catalog_refresh_shares_one_owner_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    calls = 0

    async def probe(*_args: object) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return {"availability": "available", "tools": [], "tool_count": 0}

    monkeypatch.setattr(broker, "_probe", probe)

    async def run() -> None:
        await asyncio.gather(
            broker.catalog(server_names={"fixture"}),
            broker.catalog(server_names={"fixture"}),
        )

    anyio.run(run)
    assert calls == 1


def test_concurrent_broker_instances_share_discovery_in_the_same_state_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = broker_service(tmp_path, "operator")
    second = broker_service(tmp_path, "operator")
    calls = 0

    async def probe(*_args: object) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return {"availability": "available", "tools": [], "tool_count": 0}

    monkeypatch.setattr(first, "_probe", probe)
    monkeypatch.setattr(second, "_probe", probe)

    async def run() -> None:
        await asyncio.gather(
            first.catalog(server_names={"fixture"}),
            second.catalog(server_names={"fixture"}),
        )

    anyio.run(run)
    assert calls == 1


def test_separate_processes_share_owner_discovery(tmp_path: Path) -> None:
    source = """import asyncio, json, sys
from pathlib import Path
import anyio
from test_mcp_broker import broker_service
root = Path(sys.argv[1])
broker = broker_service(root, "operator")
async def probe(*args):
    with (root / "probes").open("a") as output:
        output.write("probe\\n")
    await asyncio.sleep(0.3)
    return {"availability": "available", "tools": []}
broker._probe = probe
async def run():
    (root / sys.argv[2]).touch()
    while not all((root / name).exists() for name in ("first", "second")):
        await asyncio.sleep(0.01)
    print(json.dumps(await broker.catalog(server_names={"fixture"})))
anyio.run(run)
"""
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", source, str(tmp_path), name],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name in ("first", "second")
    ]
    try:
        for process in processes:
            output, error = process.communicate(timeout=15)
            assert process.returncode == 0, error
            assert json.loads(output)["servers"][0]["schema_complete"] is True
        assert (tmp_path / "probes").read_text().splitlines() == ["probe"]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()


def test_discovery_wait_timeout_preserves_schema_and_private_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)
    anyio.run(broker.catalog)
    row = broker.config.mcp_broker_servers["fixture"]
    identity = hashlib.sha256(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = broker._discovery_path("fixture", identity)
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.DEFAULT_MCP_CALL_TIMEOUT_SECONDS", 0.03
    )
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = anyio.run(broker.catalog)
    server = next(s for s in result["servers"] if s["name"] == "fixture")
    assert server["failure_class"] == "discovery_wait_timeout"
    assert server["schema_stale"] and server["schema_complete"]
    assert server["tools"][0]["name"] == "lookup"


def test_catalog_failure_retains_complete_contract_across_broker_instances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)
    good = anyio.run(broker.catalog)
    contracts = next(s for s in good["servers"] if s["name"] == "fixture")["tools"]
    reopened = broker_service(tmp_path, "operator")

    async def failed(*_args: object) -> dict[str, Any]:
        return {"availability": "unavailable", "reason": "fixture temporarily offline"}

    monkeypatch.setattr(reopened, "_probe", failed)
    result = anyio.run(reopened.catalog)
    server = next(s for s in result["servers"] if s["name"] == "fixture")
    assert server["availability"] == "unavailable"
    assert server["tools"] == contracts
    assert server["schema_stale"] is True
    assert server["schema_complete"] is True


def test_partial_discovery_cannot_replace_complete_schema_and_config_invalidates_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)
    anyio.run(broker.catalog)

    async def partial(*_args: object) -> dict[str, Any]:
        return {
            "availability": "available",
            "coverage_complete": False,
            "tools": [],
            "reason": "repeated cursor",
        }

    monkeypatch.setattr(broker, "_probe", partial)
    result = anyio.run(broker.catalog)
    row = next(s for s in result["servers"] if s["name"] == "fixture")
    assert row["schema_stale"] and row["schema_complete"]
    assert row["coverage_complete"] is False
    assert [t["name"] for t in row["tools"]] == ["lookup"]
    broker.config.mcp_broker_servers["fixture"]["args"] = ["--changed-owner"]
    result = anyio.run(broker.catalog)
    row = next(s for s in result["servers"] if s["name"] == "fixture")
    assert row["schema_complete"] is False
    assert row["tools"] == []


def test_cancelled_catalog_reader_does_not_cancel_shared_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    calls = 0

    async def run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()

        async def probe(*_args: object) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return {"availability": "available", "tools": []}

        monkeypatch.setattr(broker, "_probe", probe)
        first = asyncio.create_task(broker.catalog(server_names={"fixture"}))
        await entered.wait()
        second = asyncio.create_task(broker.catalog(server_names={"fixture"}))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        result = await second
        assert result["servers"][0]["schema_complete"]

    anyio.run(run)
    assert calls == 1


def test_retained_read_schema_cannot_authorize_changed_live_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)
    anyio.run(broker.catalog)

    class ChangedSession(FakeSession):
        async def list_tools(self, *, params: object | None = None) -> object:
            result = await super().list_tools(params=params)
            result.tools[0].annotations = None
            return result

    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", ChangedSession)

    async def invoke() -> None:
        await broker.call("fixture", "lookup", {"query": "neutral"}, write=False)

    with pytest.raises(McpBrokerError, match="not explicitly declared read-only"):
        anyio.run(invoke)


def test_catalog_and_invocation_traverse_every_tool_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    TwoPageSession.calls.clear()
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", TwoPageSession)

    catalog = anyio.run(broker.catalog)
    fixture = next(
        server for server in catalog["servers"] if server["name"] == "fixture"
    )
    assert [item["name"] for item in fixture["tools"]] == ["first", "second"]
    assert [item["ref"] for item in fixture["tools"]] == [
        "sinnix://mcp/fixture/tools/first",
        "sinnix://mcp/fixture/tools/second",
    ]
    result = anyio.run(
        lambda: broker.call("fixture", "second", {"query": "page two"}, write=False)
    )
    assert result["response"]["content"][0]["text"] == "second:page two"
    assert TwoPageSession.calls == [None, "page-2", None, "page-2"]


def test_repeated_tool_cursor_reports_partial_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    RepeatingCursorSession.calls.clear()
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.ClientSession", RepeatingCursorSession
    )

    catalog = anyio.run(broker.catalog)
    fixture = next(
        server for server in catalog["servers"] if server["name"] == "fixture"
    )
    assert fixture["availability"] == "available"
    assert fixture["coverage_complete"] is False
    assert fixture["failure_class"] == "pagination_incomplete"
    assert fixture["tools"][0]["name"] == "first"
    assert RepeatingCursorSession.calls == [None, "loop"]
    with pytest.raises(McpBrokerError, match="tool listing is incomplete"):
        anyio.run(lambda: broker.call("fixture", "missing", {}, write=False))


def broker_service(
    tmp_path: Path, principal_name: str, max_bytes: int = 262_144
) -> McpBrokerService:
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


class LargeSchemaSession(FakeSession):
    async def list_tools(self, *, params: object | None = None) -> object:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="lookup",
                    description="Fixture lookup",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "x" * 8_000}
                        },
                    },
                    annotations=SimpleNamespace(read_only_hint=True),
                )
            ],
            next_cursor=None,
        )


def test_catalog_artifactizes_an_oversized_tool_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator", max_bytes=4_096)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.ClientSession", LargeSchemaSession
    )

    catalog = anyio.run(broker.catalog)
    assert (
        len(json.dumps(catalog, separators=(",", ":")).encode())
        <= broker.config.max_result_bytes
    )
    fixture = next(
        server for server in catalog["servers"] if server["name"] == "fixture"
    )
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

    result = anyio.run(broker.catalog)
    fixture = next(row for row in result["servers"] if row["name"] == "fixture")
    assert fixture.pop("schema_complete") is True
    assert fixture.pop("schema_stale") is False
    assert fixture.pop("schema_observed_at") == fixture.pop("probed_at")
    assert len(fixture.pop("owner_contract_digest")) == 64
    assert result == {
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
                "tools": [
                    {
                        "name": "lookup",
                        "ref": "sinnix://mcp/fixture/tools/lookup",
                        "description": "Fixture lookup",
                        "input_schema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                        "effect": "read",
                    }
                ],
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

    row = result["servers"][1]
    assert row.pop("schema_complete") is True
    assert row.pop("schema_stale") is False
    assert row.pop("schema_observed_at") == row.pop("probed_at")
    assert len(row.pop("owner_contract_digest")) == 64
    assert row == {
        "name": "fixture",
        "description": "Fixture server",
        "transport": "stdio",
        "tier": "evidence",
        "brokered": True,
        "availability": "available",
        "tool_count": 1,
        "read_only_tool_count": 1,
        "tools": [
            {
                "name": "fixture_read",
                "ref": "sinnix://mcp/fixture/tools/fixture_read",
                "description": "Fixture read tool",
                "input_schema": {"type": "object", "properties": {}},
                "effect": "read",
            }
        ],
    }


def test_real_stdio_catalog_tail_is_discoverable_and_session_stays_warm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator", max_bytes=4_096)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    fixture = write_stdio_fixture(
        tmp_path,
        """import json
import pathlib
import sys

counter = pathlib.Path(sys.argv[1])
counter.write_text(str(int(counter.read_text()) + 1) if counter.exists() else "1")
tools = [{
    "name": f"fixture_{index:04d}",
    "description": "fixture tool " + ("x" * 120),
    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
    "annotations": {"readOnlyHint": True},
} for index in range(120)]

for line in sys.stdin:
    request = json.loads(line)
    method = request["method"]
    if method == "initialize":
        result = {
            "protocolVersion": request["params"]["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fixture", "version": "1"},
        }
    elif method == "tools/list":
        result = {"tools": tools}
    elif method == "tools/call":
        result = {
            "content": [{"type": "text", "text": request["params"]["name"]}],
            "isError": False,
        }
    else:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
""",
    )
    counter = tmp_path / "launches.txt"
    broker.config.mcp_broker_servers["fixture"].update(
        command=sys.executable, args=[str(fixture), str(counter)]
    )

    async def discover_and_call() -> tuple[dict[str, Any], dict[str, Any]]:
        async with broker.lifespan():
            bounded = await broker.catalog()
            complete = await broker.catalog(server_names={"fixture"}, bounded=False)
            result = await broker.call(
                "fixture", "fixture_0119", {"query": "tail"}, write=False
            )
            return bounded, {"complete": complete, "call": result}

    bounded, complete_and_call = anyio.run(discover_and_call)
    bounded_fixture = next(
        server for server in bounded["servers"] if server["name"] == "fixture"
    )
    complete_fixture = complete_and_call["complete"]["servers"][0]

    assert bounded["truncated"] is True
    assert "fixture_0119" not in {
        tool["name"] for tool in bounded_fixture.get("tools", [])
    }
    assert "fixture_0119" in {tool["name"] for tool in complete_fixture["tools"]}
    assert complete_and_call["call"]["response"]["content"][0]["text"] == "fixture_0119"
    assert counter.read_text() == "1"


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


def test_gateway_lifespan_reuses_healthy_upstream_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    launches = 0
    closes = 0

    class CountingTransport(FakeTransport):
        async def __aexit__(self, *args: object) -> None:
            nonlocal closes
            closes += 1
            await super().__aexit__(*args)

    def stdio(_params: object, **_kwargs: object) -> FakeTransport:
        nonlocal launches
        launches += 1
        return CountingTransport()

    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.stdio_client", stdio)
    monkeypatch.setattr("sinnix_agent_gateway.mcp_broker.ClientSession", FakeSession)

    async def calls() -> tuple[dict[str, object], dict[str, object]]:
        async with broker.lifespan():
            await broker.catalog()
            first = await broker.call(
                "fixture", "lookup", {"query": "first"}, write=False
            )
            second = await broker.call(
                "fixture", "lookup", {"query": "second"}, write=False
            )
            return first, second

    first, second = anyio.run(calls)

    assert first["response"]["content"][0]["text"] == "lookup:first"
    assert second["response"]["content"][0]["text"] == "lookup:second"
    assert launches == 1
    assert closes == 1


def test_failed_persistent_write_is_not_resent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    calls = 0
    launches = 0

    class UncertainWriteSession(FakeSession):
        async def list_tools(self, *, params: object | None = None) -> object:
            response = await super().list_tools(params=params)
            response.tools[0].annotations = None
            return response

        async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
            nonlocal calls
            calls += 1
            raise OSError("connection lost after dispatch")

    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: launch(),
    )
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.ClientSession", UncertainWriteSession
    )

    def launch() -> FakeTransport:
        nonlocal launches
        launches += 1
        return FakeTransport()

    async def invoke() -> None:
        async with broker.lifespan():
            with pytest.raises(McpBrokerError, match="session failed"):
                await broker.call("fixture", "lookup", {"query": "mutate"}, write=True)
            await broker.catalog()

    anyio.run(invoke)

    assert calls == 1
    assert launches == 2


@pytest.mark.parametrize("annotation", [None, False])
def test_read_only_subroute_requires_exact_tool_and_explicit_selector(
    tmp_path, monkeypatch, annotation
):
    broker = broker_service(tmp_path, "operator")
    broker.config.mcp_broker_servers["fixture"]["readOnlyRoutes"] = [
        {"tool": "lookup", "arguments": {"projection": "sessions"}}
    ]
    calls = []

    class UnannotatedSession(FakeSession):
        async def list_tools(self, *, params=None):
            response = await super().list_tools(params=params)
            response.tools[0].annotations = (
                None
                if annotation is None
                else SimpleNamespace(read_only_hint=annotation)
            )
            return response

        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return await super().call_tool(name, arguments)

    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda *args, **kwargs: FakeTransport(),
    )
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.ClientSession", UnannotatedSession
    )
    safe = {"query": "fixture", "projection": "sessions"}
    result = anyio.run(lambda: broker.call("fixture", "lookup", safe, write=False))
    assert result["response"]["content"][0]["text"] == "lookup:fixture"
    for arguments in (
        {"query": "fixture"},
        {"query": "fixture", "projection": "write"},
    ):
        with pytest.raises(McpBrokerError, match="not explicitly declared read-only"):
            anyio.run(
                lambda arguments=arguments: broker.call(
                    "fixture", "lookup", arguments, write=False
                )
            )
    with pytest.raises(McpBrokerError, match="declared read-only"):
        anyio.run(lambda: broker.call("fixture", "lookup", safe, write=True))
    with pytest.raises(McpBrokerError, match="does not expose tool"):
        anyio.run(lambda: broker.call("fixture", "another-tool", safe, write=False))
    assert calls == [("lookup", safe)]


def test_read_only_tools_admit_unannotated_tools(tmp_path, monkeypatch) -> None:
    broker = broker_service(tmp_path, "operator")
    broker.config.mcp_broker_servers["fixture"]["readOnlyTools"] = ["lookup"]
    calls = []

    class UnannotatedSession(FakeSession):
        async def list_tools(self, *, params=None):
            response = await super().list_tools(params=params)
            response.tools[0].annotations = None
            return response

        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return await super().call_tool(name, arguments)

    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda *args, **kwargs: FakeTransport(),
    )
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.ClientSession", UnannotatedSession
    )
    result = anyio.run(
        lambda: broker.call("fixture", "lookup", {"query": "fixture"}, write=False)
    )
    assert result["response"]["content"][0]["text"] == "lookup:fixture"
    catalog = anyio.run(broker.catalog)
    fixture = next(
        server for server in catalog["servers"] if server["name"] == "fixture"
    )
    assert fixture["tools"][0]["effect"] == "read"
    assert fixture["read_only_tool_count"] == 1
    with pytest.raises(McpBrokerError, match="declared read-only"):
        anyio.run(
            lambda: broker.call("fixture", "lookup", {"query": "fixture"}, write=True)
        )
    assert calls == [("lookup", {"query": "fixture"})]


@pytest.mark.parametrize("tools", [True, [""], [1], ["x" * 129]])
def test_read_only_tools_rejects_malformed_configuration(tmp_path, tools) -> None:
    broker = broker_service(tmp_path, "operator")
    broker.config.mcp_broker_servers["fixture"]["readOnlyTools"] = tools
    with pytest.raises(McpBrokerError, match="configuration is malformed"):
        broker._server("fixture")


@pytest.mark.parametrize(
    "routes",
    [
        True,
        [{"tool": "lookup", "arguments": {}}],
        [{"tool": "lookup", "arguments": {"projection": True}}],
        [{"tool": "lookup"}],
    ],
)
def test_read_only_subroute_rejects_unbounded_or_malformed_configuration(
    tmp_path, routes
):
    broker = broker_service(tmp_path, "operator")
    broker.config.mcp_broker_servers["fixture"]["readOnlyRoutes"] = routes
    with pytest.raises(McpBrokerError, match="configuration is malformed"):
        broker._server("fixture")


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
    broker = broker_service(tmp_path, "operator", max_bytes=10)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
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


class HangingCallSession(FakeSession):
    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        await asyncio.sleep(60)
        return await super().call_tool(name, arguments)


def test_broker_uses_declared_timeout_and_classifies_upstream_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = broker_service(tmp_path, "operator")
    broker.config.mcp_broker_servers["fixture"]["callTimeoutSeconds"] = 1
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.ClientSession", HangingCallSession
    )

    with pytest.raises(McpBrokerTimeoutError, match="timed out after 1s"):
        anyio.run(
            lambda: broker.call("fixture", "lookup", {"query": "fixture"}, write=False)
        )


def test_broker_enforces_caller_deadline_before_launch(tmp_path: Path) -> None:
    broker = broker_service(tmp_path, "operator")

    with pytest.raises(McpBrokerDeadlineError, match="deadline elapsed"):
        anyio.run(
            lambda: broker.call(
                "fixture",
                "lookup",
                {},
                write=False,
                deadline_at=time.time() - 1,
            )
        )


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
        "fixture": {"brokered": True, "callTimeoutSeconds": 30}
    }


@pytest.mark.parametrize("value", [0, -1, 3_601, 1.5, True, "30"])
def test_gateway_config_rejects_invalid_mcp_call_timeout(
    tmp_path: Path, value: object
) -> None:
    config_path = tmp_path / "gateway.json"
    config_path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {},
                "mcpBrokerServers": {"fixture": {"callTimeoutSeconds": value}},
            }
        )
    )

    with pytest.raises(ValueError, match="callTimeoutSeconds"):
        GatewayConfig.load(config_path)


@pytest.mark.parametrize(
    ("call_budget", "probe_budget", "failure_class"),
    [(3, 3, "timeout"), (300, 30, "discovery_timeout")],
)
def test_probe_distinguishes_capped_discovery_from_call_route_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    call_budget,
    probe_budget,
    failure_class,
) -> None:
    broker = broker_service(tmp_path, "operator")
    broker.config.mcp_broker_servers["fixture"]["callTimeoutSeconds"] = call_budget
    budgets = []
    wait_for = asyncio.wait_for

    class SlowInitialization(FakeSession):
        async def initialize(self) -> None:
            await asyncio.sleep(60)

    async def short_test_wait(awaitable, *, timeout):
        budgets.append(timeout)
        return await wait_for(awaitable, timeout=min(timeout, 0.02))

    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.asyncio.wait_for", short_test_wait
    )
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.stdio_client",
        lambda _params, **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr(
        "sinnix_agent_gateway.mcp_broker.ClientSession", SlowInitialization
    )
    result = anyio.run(broker.catalog)
    row = next(row for row in result["servers"] if row["name"] == "fixture")
    assert budgets[0] == pytest.approx(probe_budget, abs=0.02)
    assert 0 < budgets[1] <= probe_budget
    assert row["availability"] == "unavailable"
    assert row["failure_class"] == failure_class
    if call_budget > probe_budget:
        assert "configured call route is not proven unavailable" in row["reason"]
        assert "callTimeoutSeconds 300" in row["reason"]
    else:
        assert "within 3 seconds" in row["reason"]
