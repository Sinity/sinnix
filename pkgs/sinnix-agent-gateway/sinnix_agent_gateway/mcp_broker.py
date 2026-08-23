from __future__ import annotations

import asyncio
import json
import shutil
import uuid
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
        """Return current upstream availability from bounded MCP handshakes."""
        self.principal.require(Capability.MCP_READ)
        rows = sorted(self.config.mcp_broker_servers.items())
        probes = await asyncio.gather(
            *(self._catalog_server(name, row) for name, row in rows if isinstance(row, dict))
        )
        return {"servers": list(probes)}

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
        environment = self._environment(configured)
        return {**server, **await self._probe(configured, name, environment)}

    def _environment(self, server: dict[str, Any]) -> dict[str, str]:
        route = OwnerRoute(
            "mcp-broker",
            (
                EnvironmentProfile.USER_BUS_OPTIONAL
                if self.principal.name == "observer"
                else EnvironmentProfile.PLAIN
            ),
        )
        execution = self.execution or OwnerExecution()
        environment, _ = execution.environment_for(route, server["env"])
        return environment

    async def _probe(
        self, server: dict[str, Any], server_name: str, environment: dict[str, str]
    ) -> dict[str, Any]:
        """Prove one upstream can initialize and disclose its live tools."""
        parameters, observer_unit = self._parameters(server, environment)
        stderr_directory = self.config.state_dir / "captures" / uuid.uuid4().hex
        stderr_directory.mkdir(mode=0o700, parents=True)
        stderr_path = stderr_directory / "stderr.log"

        async def inspect() -> tuple[int, int]:
            with stderr_path.open("w", encoding="utf-8") as stderr:
                async with stdio_client(parameters, errlog=stderr) as (read, write_stream):
                    async with ClientSession(read, write_stream) as session:
                        await session.initialize()
                        tools = (await session.list_tools()).tools
            return len(tools), sum(
                getattr(getattr(tool, "annotations", None), "read_only_hint", None)
                is True
                for tool in tools
            )

        try:
            tool_count, read_only_tool_count = await asyncio.wait_for(inspect(), timeout=5)
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
            "tool_count": tool_count,
            "read_only_tool_count": read_only_tool_count,
        }

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
                    "MCP tool is not explicitly declared read-only; use mcp_write"
                )
            if write and read_only is True:
                raise McpBrokerError("MCP tool is declared read-only; use mcp_read")
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
