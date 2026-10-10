from __future__ import annotations

import asyncio
import copy
import fcntl
import hashlib
import json
import math
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import PaginatedRequestParams

from .artifacts import ArtifactService
from .capabilities import Capability, Principal
from .config import (
    DEFAULT_MCP_CALL_TIMEOUT_SECONDS,
    GatewayConfig,
    validate_mcp_call_timeout,
)
from .owner_execution import (
    EnvironmentProfile,
    OwnerExecution,
    OwnerRoute,
)
from .payloads import retain


class McpBrokerError(ValueError):
    pass


class McpEnvironmentError(McpBrokerError):
    pass


class McpBrokerTimeoutError(McpBrokerError):
    pass


class McpBrokerDeadlineError(McpBrokerError):
    pass


MAX_MCP_TOOL_LIST_PAGES = 128
MAX_MCP_TOOL_COUNT = 10_000


@dataclass
class _SessionRequest:
    operation: str
    payload: Any
    reply: Any


class _PersistentSession:
    def __init__(self, service: "McpBrokerService", name: str, sender: Any):
        self.service = service
        self.name = name
        self.sender = sender

    async def initialize(self) -> None:
        return None

    async def list_tools(self, *, params: Any = None) -> Any:
        return await self._request("list_tools", params)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self._request("call_tool", (name, arguments))

    async def _request(self, operation: str, payload: Any) -> Any:
        send, receive = anyio.create_memory_object_stream[Any](1)
        async with send, receive:
            await self.sender.send(_SessionRequest(operation, payload, send))
            ok, value = await receive.receive()
        if not ok:
            await self.service._discard_session(self.name)
            raise value
        return value


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
        self._task_group: Any | None = None
        self._sessions: dict[str, _PersistentSession] = {}
        self._session_lock = anyio.Lock()
        self._discoveries: dict[tuple[str, str], asyncio.Task[dict[str, Any]]] = {}

    @asynccontextmanager
    async def lifespan(self):
        """Own warm upstream processes for exactly one gateway lifespan."""
        if self._task_group is not None:
            raise RuntimeError("MCP broker lifespan is already active")
        async with anyio.create_task_group() as task_group:
            self._task_group = task_group
            try:
                yield
            finally:
                discoveries = list(self._discoveries.values())
                for discovery in discoveries:
                    discovery.cancel()
                await asyncio.gather(*discoveries, return_exceptions=True)
                self._discoveries.clear()
                self._task_group = None
                self._sessions.clear()
                task_group.cancel_scope.cancel()

    async def _persistent_session(
        self,
        name: str,
        server: dict[str, Any],
        environment: dict[str, str],
        stderr_directory: Path,
    ) -> _PersistentSession | None:
        task_group = self._task_group
        if task_group is None:
            return None
        async with self._session_lock:
            session = self._sessions.get(name)
            if session is not None:
                return session
            sender, receiver = anyio.create_memory_object_stream[_SessionRequest](32)
            parameters = self._parameters(server, environment)
            stderr_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            stderr_path = stderr_directory / "stderr.log"
            session = await task_group.start(
                self._serve_session,
                name,
                parameters,
                stderr_path,
                receiver,
            )
            session.sender = sender
            self._sessions[name] = session
            return session

    async def _serve_session(
        self,
        name: str,
        parameters: StdioServerParameters,
        stderr_path: Path,
        receiver: Any,
        *,
        task_status: Any = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        current_tool = "initialize"
        started = False
        failed_request: _SessionRequest | None = None
        try:
            with stderr_path.open("w", encoding="utf-8") as stderr:
                async with stdio_client(parameters, errlog=stderr) as (
                    read,
                    write_stream,
                ):
                    async with ClientSession(read, write_stream) as client:
                        await client.initialize()
                        proxy = _PersistentSession(self, name, None)
                        task_status.started(proxy)
                        started = True
                        async with receiver:
                            async for request in receiver:
                                current_tool = (
                                    request.payload[0]
                                    if request.operation == "call_tool"
                                    else "tools/list"
                                )
                                try:
                                    if request.operation == "list_tools":
                                        result = await client.list_tools(
                                            params=request.payload
                                        )
                                    else:
                                        tool_name, arguments = request.payload
                                        result = await client.call_tool(
                                            tool_name, arguments
                                        )
                                except Exception:
                                    failed_request = request
                                    raise
                                else:
                                    try:
                                        await request.reply.send((True, result))
                                    except (
                                        anyio.BrokenResourceError,
                                        anyio.ClosedResourceError,
                                    ):
                                        # The caller timed out or disconnected. The
                                        # upstream result may already exist; keep it
                                        # only in this session and never resend it.
                                        continue
        except Exception as exc:
            artifact_id = self._store_upstream_stderr(
                stderr_path.parent, name, current_tool
            )
            diagnostic = f"; diagnostic artifact {artifact_id}" if artifact_id else ""
            message = McpBrokerError(
                f"MCP upstream {name} session failed: {type(exc).__name__}{diagnostic}"
            )
            if failed_request is not None:
                with anyio.CancelScope(shield=True):
                    try:
                        await failed_request.reply.send((False, message))
                    except (anyio.BrokenResourceError, anyio.ClosedResourceError):
                        pass
            if not started:
                task_status.started(exception=message)
            return
        finally:
            if stderr_path.exists() and stderr_path.stat().st_size == 0:
                shutil.rmtree(stderr_path.parent, ignore_errors=True)

    async def _discard_session(self, name: str) -> None:
        async with self._session_lock:
            self._sessions.pop(name, None)

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 8_192) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise McpBrokerError(f"{name} must be a bounded non-empty string")
        return value

    async def catalog(
        self, *, server_names: set[str] | None = None, bounded: bool = True
    ) -> dict[str, Any]:
        """Return admitted upstream tool contracts from bounded handshakes."""
        self.principal.require(Capability.MCP_READ)
        rows = sorted(
            (name, row)
            for name, row in self.config.mcp_broker_servers.items()
            if server_names is None or name in server_names
        )
        probes = await asyncio.gather(
            *(
                self._catalog_server(name, row)
                for name, row in rows
                if isinstance(row, dict)
            )
        )
        servers = list(probes)
        full_response = {"servers": servers}
        if (
            len(
                json.dumps(
                    full_response, sort_keys=True, separators=(",", ":")
                ).encode()
            )
            > self.config.max_result_bytes
        ):
            catalog_artifact = self._store_json_artifact(
                full_response,
                kind="mcp-catalog",
                owner_id="mcp-broker",
                source="mcp-catalog",
            )
        else:
            catalog_artifact = None
        if not bounded:
            return {
                "servers": servers,
                "truncated": catalog_artifact is not None
                or any(server.get("coverage_complete") is False for server in servers),
                "catalog_artifact": catalog_artifact,
            }
        while True:
            response = {"servers": servers}
            if catalog_artifact is not None:
                response["truncated"] = True
                response["catalog_artifact"] = catalog_artifact
            if (
                len(
                    json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
                )
                <= self.config.max_result_bytes
            ):
                return response
            candidates = [
                server
                for server in servers
                if isinstance(server.get("tools"), list) and server["tools"]
            ]
            if not candidates:
                if catalog_artifact is None:
                    catalog_artifact = self._store_json_artifact(
                        response,
                        kind="mcp-catalog",
                        owner_id="mcp-broker",
                        source="mcp-catalog",
                    )
                return {
                    "truncated": True,
                    "catalog_artifact": catalog_artifact,
                }
            largest = max(
                candidates, key=lambda server: len(json.dumps(server["tools"]))
            )
            largest["tools"].pop()
            largest["tools_truncated"] = True

    async def _catalog_server(self, name: str, row: dict[str, Any]) -> dict[str, Any]:
        # Share only concurrent discovery, never invocation results. A cancelled
        # reader must not cancel the bounded probe another reader is awaiting.
        identity = hashlib.sha256(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        key = (name, identity)
        task = self._discoveries.get(key)
        if task is None:
            task = asyncio.create_task(self._shared_discovery(name, row, identity))
            self._discoveries[key] = task

            def finished(done: asyncio.Task[dict[str, Any]]) -> None:
                if self._discoveries.get(key) is done:
                    self._discoveries.pop(key, None)
                if not done.cancelled():
                    done.exception()

            task.add_done_callback(finished)
        # Catalog presentation can trim tools; never let that mutate a shared
        # complete result or the last-good snapshot.
        return copy.deepcopy(await asyncio.shield(task))

    async def _shared_discovery(
        self, name: str, row: dict[str, Any], identity: str
    ) -> dict[str, Any]:
        if row.get("brokered") is not True:
            return await self._discover_server(name, row, identity)
        path = self._discovery_path(name, identity)
        latest_path = path.with_suffix(".probe.json")
        initial = self._read_json(latest_path)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        waited = False
        deadline = asyncio.get_running_loop().time() + DEFAULT_MCP_CALL_TIMEOUT_SECONDS
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    waited = True
                    if asyncio.get_running_loop().time() >= deadline:
                        previous = self._read_discovery(path)
                        return {
                            "name": name,
                            "brokered": True,
                            "availability": "unavailable",
                            "failure_class": "discovery_wait_timeout",
                            "reason": "another discovery did not finish within the discovery budget",
                            "schema_complete": previous is not None,
                            "schema_stale": previous is not None,
                            "schema_observed_at": (
                                previous["observed_at"] if previous else None
                            ),
                            "tools": previous["tools"] if previous else [],
                            "owner_contract_digest": identity,
                        }
                    await asyncio.sleep(0.02)
            latest = self._read_json(latest_path)
            if (
                waited
                and isinstance(latest, dict)
                and latest.get("refresh_id") != (initial or {}).get("refresh_id")
                and isinstance(latest.get("result"), dict)
            ):
                return latest["result"]
            result = await self._discover_server(name, row, identity, deadline)
            try:
                self._write_discovery(
                    latest_path,
                    {
                        "refresh_id": uuid.uuid4().hex,
                        "result": result,
                    },
                )
            except OSError as exc:
                result["schema_storage_error"] = type(exc).__name__
            return result
        finally:
            os.close(fd)

    def _discovery_path(self, name: str, identity: str) -> Path:
        digest = hashlib.sha256(name.encode()).hexdigest()
        return self.config.state_dir / "mcp-discovery" / f"{digest}-{identity}.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        try:
            with path.open(encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def _read_discovery(self, path: Path) -> dict[str, Any] | None:
        value = self._read_json(path)
        if (
            isinstance(value, dict)
            and value.get("version") == 1
            and isinstance(value.get("tools"), list)
            and isinstance(value.get("observed_at"), str)
            and all(
                isinstance(tool, dict)
                and isinstance(tool.get("name"), str)
                and isinstance(tool.get("ref"), str)
                and isinstance(tool.get("input_schema"), dict)
                and tool.get("effect") in {"read", "change"}
                for tool in value["tools"]
            )
        ):
            return value
        return None

    def _write_discovery(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".discovery-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    async def _discover_server(
        self,
        name: str,
        row: dict[str, Any],
        identity: str,
        deadline_at: float | None = None,
    ) -> dict[str, Any]:
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
            remaining = (
                max(0.001, deadline_at - asyncio.get_running_loop().time())
                if deadline_at is not None
                else DEFAULT_MCP_CALL_TIMEOUT_SECONDS
            )
            probe = await self._probe(configured, name, environment, remaining)
        except McpBrokerError as exc:
            probe = {
                "availability": "unavailable",
                "failure_class": "environment_unavailable",
                "reason": str(exc),
            }
        observed_at = datetime.now(timezone.utc).isoformat()
        path = self._discovery_path(name, identity)
        previous = self._read_discovery(path)
        complete = (
            probe.get("availability") == "available"
            and probe.get("coverage_complete") is not False
            and isinstance(probe.get("tools"), list)
        )
        if complete:
            previous = {
                "version": 1,
                "observed_at": observed_at,
                "tools": probe["tools"],
            }
            try:
                self._write_discovery(path, previous)
            except OSError as exc:
                probe["schema_storage_error"] = type(exc).__name__
        elif previous is not None:
            probe["tools"] = previous["tools"]
            probe["tool_count"] = len(previous["tools"])
            probe["read_only_tool_count"] = sum(
                tool.get("effect") == "read" for tool in previous["tools"]
            )
        probe.update(
            schema_complete=previous is not None,
            schema_stale=not complete and previous is not None,
            schema_observed_at=previous["observed_at"] if previous else None,
            probed_at=observed_at,
            owner_contract_digest=identity,
        )
        return {**server, **probe}

    def _environment(self, server: dict[str, Any]) -> dict[str, str]:
        route = OwnerRoute("mcp-broker", EnvironmentProfile.PLAIN)
        execution = self.execution or OwnerExecution()
        environment, missing = execution.environment_for(route, server.get("env", {}))
        if missing is not None:
            raise McpEnvironmentError(f"MCP environment is missing {missing}")
        return environment

    async def _probe(
        self,
        server: dict[str, Any],
        server_name: str,
        environment: dict[str, str],
        remaining_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Prove one upstream can initialize and disclose its live tools."""
        # Discovery stays bounded by the default even when a server declares a
        # longer call budget, so one slow upstream cannot stall gateway.status
        # for minutes. That cap means a probe deadline is not always the budget
        # the call route actually gets, and reporting both as a plain timeout
        # made a slow start indistinguishable from a dead route (sinnix-4rcy).
        call_timeout = self._call_timeout(server)
        timeout = min(call_timeout, DEFAULT_MCP_CALL_TIMEOUT_SECONDS)
        discovery_truncated = timeout < call_timeout
        if remaining_seconds is not None:
            timeout = min(timeout, remaining_seconds)
        parameters = self._parameters(server, environment)
        stderr_directory = self.config.state_dir / "captures" / uuid.uuid4().hex
        stderr_directory.mkdir(mode=0o700, parents=True)
        stderr_path = stderr_directory / "stderr.log"
        discovery_deadline = asyncio.get_running_loop().time() + timeout

        async def inspect() -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
            with stderr_path.open("w", encoding="utf-8") as stderr:
                async with stdio_client(parameters, errlog=stderr) as (
                    read,
                    write_stream,
                ):
                    async with ClientSession(read, write_stream) as session:
                        await session.initialize()
                        tools, coverage = await self._list_tools(session)
                        if not coverage["complete"] and coverage["pages_read"] == 0:
                            raise McpBrokerError(
                                f"upstream tools/list failed before returning a page: {coverage['reason']}"
                            )
            contracts = [self._tool_contract(server_name, tool) for tool in tools]
            return (
                contracts,
                sum(contract["effect"] == "read" for contract in contracts),
                coverage,
            )

        try:
            session = await asyncio.wait_for(
                self._persistent_session(
                    server_name, server, environment, stderr_directory
                ),
                timeout=timeout,
            )
            if session is None:
                tools, read_only_tool_count, coverage = await asyncio.wait_for(
                    inspect(),
                    timeout=max(
                        0.001, discovery_deadline - asyncio.get_running_loop().time()
                    ),
                )
            else:
                tools, coverage = await asyncio.wait_for(
                    self._list_tools(session),
                    timeout=max(
                        0.001, discovery_deadline - asyncio.get_running_loop().time()
                    ),
                )
                contracts = [self._tool_contract(server_name, tool) for tool in tools]
                read_only_tool_count = sum(
                    contract["effect"] == "read" for contract in contracts
                )
                tools = contracts
        except asyncio.TimeoutError:
            artifact_id = self._store_upstream_stderr(
                stderr_directory, server_name, "tools/list"
            )
            result: dict[str, Any] = {
                "availability": "unavailable",
                "failure_class": (
                    "discovery_timeout" if discovery_truncated else "timeout"
                ),
                "reason": (
                    (
                        f"upstream did not complete initialize and tools/list "
                        f"within the {timeout}s discovery budget; this server "
                        f"declares callTimeoutSeconds {call_timeout}, so the "
                        f"configured call route is not proven unavailable -- "
                        f"call it directly to decide, or lower "
                        f"callTimeoutSeconds so readiness can cover it"
                    )
                    if discovery_truncated
                    else (
                        f"upstream did not complete initialize and tools/list "
                        f"within {timeout} seconds"
                    )
                ),
            }
            if artifact_id is not None:
                result["diagnostic_artifact_id"] = artifact_id
            return result
        except Exception as exc:
            artifact_id = (
                None
                if "diagnostic artifact " in str(exc)
                else self._store_upstream_stderr(
                    stderr_directory, server_name, "tools/list"
                )
            )
            result = {
                "availability": "unavailable",
                "failure_class": "upstream_unavailable",
                "reason": (
                    str(exc)
                    if isinstance(exc, McpBrokerError)
                    else "upstream did not complete initialize and tools/list"
                ),
            }
            if artifact_id is not None:
                result["diagnostic_artifact_id"] = artifact_id
            return result
        shutil.rmtree(stderr_directory, ignore_errors=True)
        result = {
            "availability": "available",
            "tool_count": len(tools),
            "read_only_tool_count": read_only_tool_count,
            "tools": tools,
        }
        if not coverage["complete"]:
            result.update(
                {
                    "coverage_complete": False,
                    "failure_class": "pagination_incomplete",
                    "reason": coverage["reason"],
                    "pages_read": coverage["pages_read"],
                }
            )
        return result

    @staticmethod
    async def _list_tools(session: Any) -> tuple[list[Any], dict[str, Any]]:
        """Read all upstream tool pages, stopping safely on malformed cursors."""
        tools: list[Any] = []
        seen_cursors: set[str] = set()
        cursor: str | None = None
        pages_read = 0

        while pages_read < MAX_MCP_TOOL_LIST_PAGES:
            if cursor is not None:
                if cursor in seen_cursors:
                    return tools, {
                        "complete": False,
                        "pages_read": pages_read,
                        "reason": "upstream repeated a pagination cursor",
                    }
                seen_cursors.add(cursor)
            try:
                page = await session.list_tools(
                    params=PaginatedRequestParams(cursor=cursor)
                )
            except Exception as exc:
                return tools, {
                    "complete": False,
                    "pages_read": pages_read,
                    "reason": f"upstream tools/list failed on page {pages_read + 1} ({type(exc).__name__})",
                }
            pages_read += 1
            tools.extend(page.tools)
            if len(tools) > MAX_MCP_TOOL_COUNT:
                del tools[MAX_MCP_TOOL_COUNT:]
                return tools, {
                    "complete": False,
                    "pages_read": pages_read,
                    "reason": f"upstream tool listing exceeded {MAX_MCP_TOOL_COUNT} tools",
                }
            next_cursor = page.next_cursor
            if next_cursor is None:
                return tools, {
                    "complete": True,
                    "pages_read": pages_read,
                    "reason": None,
                }
            if not isinstance(next_cursor, str) or not next_cursor:
                return tools, {
                    "complete": False,
                    "pages_read": pages_read,
                    "reason": "upstream returned an invalid pagination cursor",
                }
            if next_cursor in seen_cursors:
                return tools, {
                    "complete": False,
                    "pages_read": pages_read,
                    "reason": "upstream repeated a pagination cursor",
                }
            if pages_read == MAX_MCP_TOOL_LIST_PAGES:
                return tools, {
                    "complete": False,
                    "pages_read": pages_read,
                    "reason": f"upstream tool listing exceeded {MAX_MCP_TOOL_LIST_PAGES} pages",
                }
            cursor = next_cursor
        raise AssertionError("bounded tools/list traversal exited without a result")

    def _tool_contract(self, server_name: str, tool: Any) -> dict[str, Any]:
        """Expose the upstream's actual namespaced schema and declared effect."""
        name = getattr(tool, "name", None)
        if not isinstance(name, str) or not name:
            raise McpBrokerError("MCP server returned a tool without a name")
        schema = getattr(tool, "inputSchema", getattr(tool, "input_schema", None))
        if not isinstance(schema, dict):
            raise McpBrokerError(f"MCP tool {name!r} has no input schema")
        server = self.config.mcp_broker_servers.get(server_name) or {}
        read_only = self._tool_is_read_only(
            server if isinstance(server, dict) else {}, tool
        )
        contract: dict[str, Any] = {
            "name": name,
            "ref": f"sinnix://mcp/{server_name}/tools/{name}",
            "description": getattr(tool, "description", None),
            "effect": "read" if read_only else "change",
        }
        encoded_schema = json.dumps(
            schema, sort_keys=True, separators=(",", ":")
        ).encode()
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
        read_only_routes = server.get("readOnlyRoutes", [])
        read_only_tools = server.get("readOnlyTools", [])
        if (
            not isinstance(command, str)
            or not command
            or not isinstance(args, list)
            or any(not isinstance(value, str) for value in args)
            or not isinstance(environment, dict)
            or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in environment.items()
            )
            or not isinstance(read_only_routes, list)
            or len(read_only_routes) > 64
            or any(
                not isinstance(route, dict)
                or set(route) != {"tool", "arguments"}
                or not isinstance(route["tool"], str)
                or not route["tool"]
                or not isinstance(route["arguments"], dict)
                or not route["arguments"]
                or any(
                    not isinstance(key, str)
                    or not key
                    or not isinstance(value, str)
                    or not value
                    for key, value in route["arguments"].items()
                )
                for route in read_only_routes
            )
            or not isinstance(read_only_tools, list)
            or len(read_only_tools) > 64
            or any(
                not isinstance(name, str) or not name or len(name) > 128
                for name in read_only_tools
            )
        ):
            raise McpBrokerError("MCP broker server configuration is malformed")
        return server

    @staticmethod
    def _annotated_read_only(tool: Any) -> bool:
        return (
            getattr(getattr(tool, "annotations", None), "read_only_hint", None) is True
        )

    @staticmethod
    def _tool_is_read_only(server: dict[str, Any], tool: Any) -> bool:
        if McpBrokerService._annotated_read_only(tool):
            return True
        name = getattr(tool, "name", None)
        admitted = server.get("readOnlyTools", [])
        return isinstance(name, str) and isinstance(admitted, list) and name in admitted

    @staticmethod
    def _request_is_read_only(
        server: dict[str, Any], tool: Any, arguments: dict[str, Any]
    ) -> bool:
        if McpBrokerService._tool_is_read_only(server, tool):
            return True
        return any(
            route["tool"] == tool.name
            and all(
                arguments.get(key) == value for key, value in route["arguments"].items()
            )
            for route in server.get("readOnlyRoutes", [])
        )

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
        self,
        server: dict[str, Any],
        environment: dict[str, str],
    ) -> StdioServerParameters:
        return StdioServerParameters(
            command=server["command"], args=server["args"], env=environment
        )

    @staticmethod
    def _call_timeout(server: dict[str, Any]) -> int:
        timeout = server.get("callTimeoutSeconds", DEFAULT_MCP_CALL_TIMEOUT_SECONDS)
        try:
            return validate_mcp_call_timeout(timeout)
        except ValueError as exc:
            raise McpBrokerError(str(exc)) from exc

    def _store_large_response(
        self, server_name: str, tool_name: str, encoded: bytes
    ) -> dict[str, Any]:
        directory = self.config.state_dir / "captures" / uuid.uuid4().hex
        directory.mkdir(mode=0o700, parents=True)
        source = directory / "mcp-response.json"
        retain(self.config.state_dir / "payloads", encoded, link=source)
        receipt = self.artifacts.attest_capture(
            directory,
            source="mcp-upstream",
            target={"server": server_name, "tool": tool_name},
            files=[source],
            durable=True,
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

    async def owner_result(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        write: bool,
        deadline_at: float | None = None,
    ) -> dict[str, Any]:
        self.principal.require(Capability.MCP_WRITE if write else Capability.MCP_READ)
        server_name = self._string(server_name, "server", 128)
        tool_name = self._string(tool_name, "tool", 256)
        if not isinstance(arguments, dict):
            raise McpBrokerError("arguments must be an object")
        server = self._server(server_name)
        call_timeout = self._call_timeout(server)
        timeout = call_timeout
        if deadline_at is not None and (
            not isinstance(deadline_at, (int, float))
            or isinstance(deadline_at, bool)
            or not math.isfinite(deadline_at)
        ):
            raise McpBrokerError("deadline_at must be a finite Unix timestamp")
        if deadline_at is not None:
            remaining = deadline_at - time.time()
            if remaining <= 0:
                raise McpBrokerDeadlineError(
                    f"MCP request deadline elapsed before calling {server_name}"
                )
            timeout = min(timeout, remaining)
        parameters = self._parameters(
            server,
            self._environment(server),
        )
        stderr_directory = self.config.state_dir / "captures" / uuid.uuid4().hex
        stderr_directory.mkdir(mode=0o700, parents=True)
        stderr_path = stderr_directory / "stderr.log"

        async def invoke_session(session: Any) -> dict[str, Any]:
            tool: Any | None = None
            response: Any | None = None
            await session.initialize()
            tools, coverage = await self._list_tools(session)
            tool = self._tool(tools, tool_name)
            if tool is None and not coverage["complete"]:
                raise McpBrokerError(
                    "MCP tool listing is incomplete; cannot determine "
                    f"whether the server exposes tool {tool_name!r}: "
                    f"{coverage['reason']}"
                )
            if tool is not None:
                read_only = self._request_is_read_only(server, tool, arguments)
                if (not write and read_only is True) or (
                    write and read_only is not True
                ):
                    response = await session.call_tool(tool_name, arguments)

            if tool is None:
                raise McpBrokerError(f"MCP server does not expose tool {tool_name!r}")
            read_only = self._request_is_read_only(server, tool, arguments)
            if not write and read_only is not True:
                raise McpBrokerError(
                    "MCP tool is not explicitly declared read-only; select mcp.change through change"
                )
            if write and read_only is True:
                raise McpBrokerError(
                    "MCP tool is declared read-only; invoke its read contract"
                )
            if response is None:
                raise McpBrokerError("MCP server returned no tool result")
            return self._response_payload(response)

        async def invoke() -> dict[str, Any]:
            persistent = await self._persistent_session(
                server_name, server, self._environment(server), stderr_directory
            )
            if persistent is not None:
                return await invoke_session(persistent)
            with stderr_path.open("w", encoding="utf-8") as stderr:
                async with stdio_client(parameters, errlog=stderr) as (
                    read,
                    write_stream,
                ):
                    async with ClientSession(read, write_stream) as session:
                        return await invoke_session(session)

        try:
            response = await asyncio.wait_for(invoke(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            artifact_id = self._store_upstream_stderr(
                stderr_directory, server_name, tool_name
            )
            diagnostic = f"; diagnostic artifact {artifact_id}" if artifact_id else ""
            if deadline_at is not None and time.time() >= deadline_at:
                raise McpBrokerDeadlineError(
                    f"MCP request deadline elapsed while calling {server_name}"
                    f"{diagnostic}"
                ) from exc
            raise McpBrokerTimeoutError(
                f"MCP upstream {server_name} timed out after {timeout:g}s{diagnostic}"
            ) from exc
        except McpBrokerError as exc:
            if "diagnostic artifact " not in str(exc):
                shutil.rmtree(stderr_directory, ignore_errors=True)
            raise
        except Exception as exc:
            artifact_id = self._store_upstream_stderr(
                stderr_directory, server_name, tool_name
            )
            diagnostic = f"; diagnostic artifact {artifact_id}" if artifact_id else ""
            raise McpBrokerError(
                f"MCP upstream {server_name} is unavailable: {type(exc).__name__}{diagnostic}"
            ) from exc
        shutil.rmtree(stderr_directory, ignore_errors=True)
        return response

    async def call(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        write: bool,
        deadline_at: float | None = None,
    ) -> dict[str, Any]:
        """Budget the external presentation after obtaining a lossless owner result."""
        response = await self.owner_result(
            server_name, tool_name, arguments, write=write, deadline_at=deadline_at
        )
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
