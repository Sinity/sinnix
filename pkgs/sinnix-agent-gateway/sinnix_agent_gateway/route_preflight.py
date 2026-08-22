from __future__ import annotations

import json
import os
from typing import Any, Callable

from .captures import queryable_capture_lanes
from .config import GatewayConfig
from .execution import (
    EnvironmentProfile,
    ExecutionProfile,
    ExecutionResult,
    OwnerExecution,
    OwnerRoute,
)


class GatewayRoutePreflight:
    """Probe bounded direct owner routes without returning owner payloads."""

    def __init__(
        self, config: GatewayConfig, execution: OwnerExecution | None = None
    ) -> None:
        self.config = config
        self.execution = execution or OwnerExecution()

    def _probe(
        self,
        name: str,
        command: list[str],
        route: OwnerRoute,
        decoder: str,
        decode: Callable[[ExecutionResult], Any],
        valid: Callable[[Any], bool],
        timeout_seconds: int = 5,
    ) -> dict[str, Any]:
        result = self.execution.run(
            command,
            ExecutionProfile(
                route=route,
                timeout_seconds=timeout_seconds,
                max_stdout_bytes=16_384,
            ),
        )
        evidence = {
            "route": name,
            "command": list(result.command),
            "decoder": decoder,
            "timeout_seconds": timeout_seconds,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
            "exit_status": result.exit_status,
        }
        if result.failure_class is not None:
            return {
                **evidence,
                "status": (
                    "unavailable"
                    if result.failure_class.startswith("command_unavailable:")
                    or result.failure_class.startswith("environment_unavailable:")
                    else "degraded"
                ),
                "failure_class": result.failure_class,
            }
        try:
            payload = decode(result)
        except json.JSONDecodeError:
            return {
                **evidence,
                "status": "degraded",
                "failure_class": "malformed_output",
            }
        if not valid(payload):
            return {
                **evidence,
                "status": "degraded",
                "failure_class": "unexpected_output_shape",
            }
        return {**evidence, "status": "pass"}

    @staticmethod
    def _is_json_object(value: Any, key: str) -> bool:
        return isinstance(value, dict) and key in value

    def _capture_probe(self) -> dict[str, Any]:
        lanes = queryable_capture_lanes(self.config.runtime_inventory)
        if not lanes:
            return {
                "route": "capture.query",
                "status": "unavailable",
                "failure_class": "queryable_lane_unavailable",
            }
        lane = sorted(lanes)[0]
        capture = lanes[lane]
        return self._probe(
            "capture.query",
            [
                self.config.capture_command,
                "query",
                "--capture-root",
                str(capture.root),
                "--since",
                "0",
                "--lane",
                lane,
            ],
            OwnerRoute("capture-query"),
            "json_lane_summary_list",
            ExecutionResult.decode_json,
            lambda value: isinstance(value, list)
            and any(
                isinstance(record, dict) and record.get("lane") == lane
                for record in value
            ),
        )

    def run(self) -> dict[str, Any]:
        routes = [
            self._probe(
                "machine.observe",
                [
                    self.config.observe_command,
                    "--format",
                    "json",
                    "--section",
                    "pressure",
                    "--limit",
                    "1",
                ],
                OwnerRoute("machine-observe", EnvironmentProfile.TERMINAL),
                "json_object_with_schema",
                ExecutionResult.decode_json,
                lambda value: self._is_json_object(value, "schema"),
            ),
            self._capture_probe(),
            self._probe(
                "desktop.hypr",
                [self.config.hypr_control_command, "screenshot-probe"],
                OwnerRoute("desktop-hypr", EnvironmentProfile.WAYLAND),
                "json_object_with_focused",
                ExecutionResult.decode_json,
                lambda value: self._is_json_object(value, "focused"),
            ),
            self._probe(
                "desktop.screenshot",
                [self.config.screenshot_control_command, "probe"],
                OwnerRoute("desktop-screenshot", EnvironmentProfile.WAYLAND),
                "json_object_with_tools",
                ExecutionResult.decode_json,
                lambda value: self._is_json_object(value, "tools"),
            ),
            self._probe(
                "terminal.kitty",
                [self.config.kitty_control_command, "list", "--json"],
                OwnerRoute("terminal-kitty", EnvironmentProfile.TERMINAL),
                "json_list",
                ExecutionResult.decode_json,
                lambda value: isinstance(value, list),
            ),
            self._probe(
                "browser.chrome",
                [self.config.chrome_control_command, "status"],
                OwnerRoute("browser-chrome"),
                "json_object_with_browser",
                ExecutionResult.decode_json,
                lambda value: self._is_json_object(value, "Browser"),
            ),
            self._probe(
                "beads",
                [self.config.beads_command, "--version"],
                OwnerRoute("beads"),
                "non_empty_text",
                ExecutionResult.decode_json_or_text,
                lambda value: isinstance(value, str) and bool(value.strip()),
            ),
        ]
        if any(server.get("brokered") for server in self.config.mcp_broker_servers.values()):
            bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
            runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
            routes.append(
                {
                    "route": "mcp.user_bus",
                    "status": "pass" if bus and runtime_dir else "degraded",
                    "failure_class": (
                        None if bus and runtime_dir else "user_bus_environment_missing"
                    ),
                    "dbus_session_bus_address": bool(bus),
                    "xdg_runtime_dir": bool(runtime_dir),
                }
            )
        return {
            "status": (
                "ready" if all(row["status"] == "pass" for row in routes) else "degraded"
            ),
            "routes": routes,
        }
