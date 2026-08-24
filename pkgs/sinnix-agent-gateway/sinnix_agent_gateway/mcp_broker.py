from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .artifacts import ArtifactService
from .capabilities import Capability, Principal
from .config import GatewayConfig
from sinnix_mcp.execution import (
    EnvironmentProfile,
    ExecutionProfile,
    OwnerExecution,
    OwnerRoute,
)


class McpBrokerError(ValueError):
    pass


class McpEnvironmentError(McpBrokerError):
    pass


class McpBrokerService:
    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        artifacts: ArtifactService,
        execution: OwnerExecution | None = None,
    ):
        self.config = config
        self.principal = principal
        self.artifacts = artifacts
        self.execution = execution

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 8_192) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise McpBrokerError(f"{name} must be a bounded non-empty string")
        return value

    async def catalog(self) -> dict[str, Any]:
        """Return admitted upstream tool contracts from bounded handshakes."""
        self.principal.require(Capability.MCP_READ)
        rows = sorted(self.config.mcp_broker_servers.items())
        probes = await asyncio.gather(
            *(self._catalog_server(name, row) for name, row in rows if isinstance(row, dict))
        )
        servers = list(probes)
        full_response = {"servers": servers}
        if len(json.dumps(full_response, sort_keys=True, separators=(",", ":")).encode()) > self.config.max_result_bytes:
            catalog_artifact = self._store_json_artifact(
                full_response, kind="mcp-catalog", owner_id="mcp-broker", source="mcp-catalog"
            )
        else:
            catalog_artifact = None
        while True:
            response = {"servers": servers}
            if catalog_artifact is not None:
                response["truncated"] = True
                response["catalog_artifact"] = catalog_artifact
            if len(json.dumps(response, sort_keys=True, separators=(",", ":")).encode()) <= self.config.max_result_bytes:
                return response
            candidates = [
                server for server in servers
                if isinstance(server.get("tools"), list) and server["tools"]
            ]
            if not candidates:
                if catalog_artifact is None:
                    catalog_artifact = self._store_json_artifact(
                        response, kind="mcp-catalog", owner_id="mcp-broker", source="mcp-catalog"
                    )
                return {
                    "truncated": True,
                    "catalog_artifact": catalog_artifact,
                }
            largest = max(candidates, key=lambda server: len(json.dumps(server["tools"])))
            largest["tools"].pop()
            largest["tools_truncated"] = True

    async def _catalog_server(self, name: str, row: dict[str, Any]) -> dict[str, Any]:
        server = {
            "name": name,
            "description": row.get("description"),
            "transport": row.get("transport"),
            "tier": row.get("tier"),
            "brokered": row.get("brokered") is True,
        }
        if row.get("brokered") is not True:
            return {
                **server,
                "availability": "unavailable",
                "reason": row.get("reason", "not admitted to the broker"),
            }
        try:
            configured = self._server(name)
        except McpBrokerError as exc:
            return {
                **server,
                "availability": "unavailable",
                "failure_class": "configuration_error",
                "reason": str(exc),
            }
        try:
            environment = self._environment(configured)
            probe = await self._probe(configured, name, environment)
        except McpBrokerError as exc:
            return {
                **server,
                "availability": "unavailable",
                "failure_class": "environment_unavailable",
                "reason": str(exc),
            }
        return {**server, **probe}

    def _environment(self, server: dict[str, Any]) -> dict[str, str]:
        route = OwnerRoute(
            "mcp-broker",
            (
                EnvironmentProfile.USER_BUS
                if self.principal.name == "observer"
                else EnvironmentProfile.PLAIN
            ),
        )
        execution = self.execution or OwnerExecution()
        environment, missing = execution.environment_for(route, server["env"])
        if missing is not None:
            raise McpEnvironmentError(f"observer MCP environment is missing {missing}")
        return environment

    async def _probe(
        self, server: dict[str, Any], server_name: str, environment: dict[str, str]
    ) -> dict[str, Any]:
        """Prove one upstream can initialize and disclose its live tools."""
        parameters, observer_unit = self._parameters(server, environment)
        stderr_directory = self.config.state_dir / "captures" / uuid.uuid4().hex
        stderr_directory.mkdir(mode=0o700, parents=True)
        stderr_path = stderr_directory / "stderr.log"

        async def inspect() -> tuple[list[dict[str, Any]], int]:
            with stderr_path.open("w", encoding="utf-8") as stderr:
                async with stdio_client(parameters, errlog=stderr) as (read, write_stream):
                    async with ClientSession(read, write_stream) as session:
                        await session.initialize()
                        tools = (await session.list_tools()).tools
            contracts = [self._tool_contract(server_name, tool) for tool in tools]
            return contracts, sum(contract["effect"] == "read" for contract in contracts)

        try:
            tools, read_only_tool_count = await asyncio.wait_for(inspect(), timeout=5)
        except asyncio.TimeoutError:
            if observer_unit is not None:
                self._stop(observer_unit)
            artifact_id = self._store_upstream_stderr(
                stderr_directory, server_name, "tools/list"
            )
            result: dict[str, Any] = {
                "availability": "unavailable",
                "failure_class": "timeout",
                "reason": "upstream did not complete initialize and tools/list within 5 seconds",
            }
            if artifact_id is not None:
                result["diagnostic_artifact_id"] = artifact_id
            return result
        except Exception:
            if observer_unit is not None:
                self._stop(observer_unit)
            artifact_id = self._store_upstream_stderr(
                stderr_directory, server_name, "tools/list"
            )
            result = {
                "availability": "unavailable",
                "failure_class": "upstream_unavailable",
                "reason": "upstream did not complete initialize and tools/list",
            }
            if artifact_id is not None:
                result["diagnostic_artifact_id"] = artifact_id
            return result
        shutil.rmtree(stderr_directory, ignore_errors=True)
        return {
            "availability": "available",
            "tool_count": len(tools),
            "read_only_tool_count": read_only_tool_count,
            "tools": tools,
        }

    def _tool_contract(self, server_name: str, tool: Any) -> dict[str, Any]:
        """Expose the upstream's actual namespaced schema and declared effect."""
        name = getattr(tool, "name", None)
        if not isinstance(name, str) or not name:
            raise McpBrokerError("MCP server returned a tool without a name")
        schema = getattr(tool, "inputSchema", getattr(tool, "input_schema", None))
        if not isinstance(schema, dict):
            raise McpBrokerError(f"MCP tool {name!r} has no input schema")
        read_only = getattr(getattr(tool, "annotations", None), "read_only_hint", None) is True
        contract: dict[str, Any] = {
            "name": name,
            "ref": f"sinnix://mcp/{server_name}/tools/{name}",
            "description": getattr(tool, "description", None),
            "effect": "read" if read_only else "change",
        }
        encoded_schema = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded_schema) <= max(1, self.config.max_result_bytes // 2):
            contract["input_schema"] = schema
        else:
            artifact = self._store_json_artifact(
                schema,
                kind="mcp-schema",
                owner_id=server_name,
                source="mcp-schema",
                target={"server": server_name, "tool": name},
            )
            contract.update(
                {
                    "input_schema": {
                        "type": "object",
                        "additionalProperties": True,
                        "x-sinnix-schema-truncated": True,
                    },
                    "input_schema_artifact": artifact,
                    "input_schema_bytes": len(encoded_schema),
                }
            )
        return contract

    def _server(self, name: str) -> dict[str, Any]:
        name = self._string(name, "server", 128)
        try:
            server = self.config.mcp_broker_servers[name]
        except KeyError as exc:
            raise McpBrokerError(f"unknown MCP server: {name}") from exc
        if server.get("brokered") is not True:
            raise McpBrokerError(
                server.get("reason", "MCP server is not admitted to the broker")
            )
        if server.get("transport") != "stdio":
            raise McpBrokerError("MCP server transport is not supported by this broker")
        command = server.get("command")
        args = server.get("args", [])
        environment = server.get("env", {})
        if (
            not isinstance(command, str)
            or not command
            or not isinstance(args, list)
            or any(not isinstance(value, str) for value in args)
            or not isinstance(environment, dict)
            or any(not isinstance(key, str) or not isinstance(value, str) for key, value in environment.items())
        ):
            raise McpBrokerError("MCP broker server configuration is malformed")
        return server

    @staticmethod
    def _tool(tools: list[Any], name: str) -> Any | None:
        for tool in tools:
            if tool.name == name:
                return tool
        return None

    @staticmethod
    def _response_payload(result: Any) -> dict[str, Any]:
        if hasattr(result, "model_dump"):
            return result.model_dump(by_alias=True, exclude_none=True, mode="json")
        raise McpBrokerError("MCP server returned an unsupported tool result")

    def _parameters(
        self, server: dict[str, Any], environment: dict[str, str]
    ) -> tuple[StdioServerParameters, str | None]:
        if self.principal.name != "observer":
            return (
                StdioServerParameters(
                    command=server["command"], args=server["args"], env=environment
                ),
                None,
            )
        unit = f"sinnix-gateway-mcp-read-{uuid.uuid4().hex}.service"
        unit_environment = [
            f"--setenv={name}={value}" for name, value in sorted(environment.items())
        ]
        return (
            StdioServerParameters(
                command=self.config.systemd_run_command,
                args=[
                    "--user",
                    "--pipe",
                    "--quiet",
                    "--collect",
                    f"--unit={unit}",
                    *unit_environment,
                    "--property=RuntimeMaxSec=30",
                    "--property=ReadOnlyPaths=/",
                    "--property=PrivateTmp=true",
                    "--property=NoNewPrivileges=true",
                    "--property=ProtectSystem=strict",
                    "--property=ProtectHome=read-only",
                    "--property=PrivateNetwork=true",
                    "--",
                    server["command"],
                    *server["args"],
                ],
                env=environment,
            ),
            unit,
        )

    def _stop(self, unit: str) -> None:
        execution = self.execution or OwnerExecution()
        execution.run(
            [self.config.systemctl_command, "--user", "stop", unit],
            ExecutionProfile(
                route=OwnerRoute(
                    "mcp-broker-cancel", EnvironmentProfile.USER_BUS_OPTIONAL
                ),
                timeout_seconds=5,
                max_stdout_bytes=16_384,
                max_stderr_bytes=8_192,
            ),
        )

    def _store_large_response(
        self, server_name: str, tool_name: str, encoded: bytes
    ) -> dict[str, Any]:
        directory = self.config.state_dir / "captures" / uuid.uuid4().hex
        directory.mkdir(mode=0o700, parents=True)
        source = directory / "mcp-response.json"
        source.write_bytes(encoded)
        receipt = self.artifacts.attest_capture(
            directory,
            source="mcp-upstream",
            target={"server": server_name, "tool": tool_name},
            files=[source],
        )
        artifact_id = self.artifacts.register(
            source,
            kind="mcp-response",
            owner_id=server_name,
        )
        return {
            "artifact_id": artifact_id,
            "bytes": len(encoded),
            "content_type": "application/json",
            "receipt": {
                "capture_id": receipt["capture_id"],
                "source": receipt["source"],
                "target": receipt["target"],
            },
        }

    def _store_json_artifact(
        self,
        payload: Any,
        *,
        kind: str,
        owner_id: str,
        source: str,
        target: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.artifacts.register_json(
            payload,
            kind=kind,
            owner_id=owner_id,
            source=source,
            target=target or {"owner": owner_id},
        )

    def _store_upstream_stderr(
        self, directory: Path, server_name: str, tool_name: str
    ) -> str | None:
        source = directory / "stderr.log"
        if not source.exists() or source.stat().st_size == 0:
            shutil.rmtree(directory, ignore_errors=True)
            return None
        self.artifacts.attest_capture(
            directory,
            source="mcp-upstream-stderr",
            target={"server": server_name, "tool": tool_name},
            files=[source],
        )
        return self.artifacts.register(source, kind="mcp-stderr", owner_id=server_name)

    async def call(
        self, server_name: str, tool_name: str, arguments: dict[str, Any], *, write: bool
    ) -> dict[str, Any]:
        self.principal.require(Capability.MCP_WRITE if write else Capability.MCP_READ)
        server_name = self._string(server_name, "server", 128)
        tool_name = self._string(tool_name, "tool", 256)
        if not isinstance(arguments, dict):
            raise McpBrokerError("arguments must be an object")
        server = self._server(server_name)
        parameters, observer_unit = self._parameters(server, self._environment(server))
        stderr_directory = self.config.state_dir / "captures" / uuid.uuid4().hex
        stderr_directory.mkdir(mode=0o700, parents=True)
        stderr_path = stderr_directory / "stderr.log"

        async def invoke() -> dict[str, Any]:
            tool: Any | None = None
            response: Any | None = None
            with stderr_path.open("w", encoding="utf-8") as stderr:
                async with stdio_client(parameters, errlog=stderr) as (read, write_stream):
                    async with ClientSession(read, write_stream) as session:
                        await session.initialize()
                        tool = self._tool((await session.list_tools()).tools, tool_name)
                        if tool is not None:
                            read_only = getattr(
                                getattr(tool, "annotations", None), "read_only_hint", None
                            )
                            if (not write and read_only is True) or (
                                write and read_only is not True
                            ):
                                response = await session.call_tool(tool_name, arguments)

            if tool is None:
                raise McpBrokerError(f"MCP server does not expose tool {tool_name!r}")
            read_only = getattr(getattr(tool, "annotations", None), "read_only_hint", None)
            if not write and read_only is not True:
                raise McpBrokerError(
                    "MCP tool is not explicitly declared read-only; select mcp.change through change"
                )
            if write and read_only is True:
                raise McpBrokerError("MCP tool is declared read-only; invoke its read contract")
            if response is None:
                raise McpBrokerError("MCP server returned no tool result")
            return self._response_payload(response)

        try:
            response = await asyncio.wait_for(invoke(), timeout=30)
        except McpBrokerError:
            if observer_unit is not None:
                self._stop(observer_unit)
            shutil.rmtree(stderr_directory, ignore_errors=True)
            raise
        except Exception as exc:
            if observer_unit is not None:
                self._stop(observer_unit)
            artifact_id = self._store_upstream_stderr(
                stderr_directory, server_name, tool_name
            )
            diagnostic = f"; diagnostic artifact {artifact_id}" if artifact_id else ""
            raise McpBrokerError(
                f"MCP upstream {server_name} is unavailable: {type(exc).__name__}{diagnostic}"
            ) from exc
        shutil.rmtree(stderr_directory, ignore_errors=True)
        encoded = json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
        result = {
            "server": server_name,
            "tool": tool_name,
            "mode": "write" if write else "read",
        }
        if len(encoded) > self.config.max_result_bytes:
            result["artifact"] = self._store_large_response(
                server_name, tool_name, encoded
            )
            result["artifact_id"] = result["artifact"]["artifact_id"]
            result["truncated"] = True
        else:
            result["response"] = response
            result["truncated"] = False
        return result
