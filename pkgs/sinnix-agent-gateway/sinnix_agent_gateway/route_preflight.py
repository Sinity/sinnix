from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable

from .captures import queryable_capture_lanes
from .config import GatewayConfig
from .execution import EnvironmentProfile, ExecutionProfile, OwnerExecution, OwnerRoute


class GatewayRoutePreflight:
    """Probe bounded direct owner routes without returning owner payloads."""

    def __init__(
        self, config: GatewayConfig, execution: OwnerExecution | None = None
    ) -> None:
        self.config = config
        self.execution = execution or OwnerExecution()

    @staticmethod
    def _command_check(name: str, command: str) -> dict[str, Any]:
        path = Path(command)
        resolved = path if path.is_absolute() else shutil.which(command)
        if resolved is None:
            return {
                "route": name,
                "status": "unavailable",
                "failure_class": "command_unavailable",
                "command": command,
            }
        resolved_path = Path(resolved)
        if not resolved_path.exists():
            return {
                "route": name,
                "status": "unavailable",
                "failure_class": "command_unavailable",
                "command": str(resolved_path),
            }
        if not resolved_path.is_file() or not os.access(resolved_path, os.X_OK):
            return {
                "route": name,
                "status": "unavailable",
                "failure_class": "command_not_executable",
                "command": str(resolved_path),
            }
        return {
            "route": name,
            "status": "pass",
            "command": str(resolved_path),
            "absolute_configured_path": path.is_absolute(),
        }

    def _probe_json(
        self,
        name: str,
        command: list[str],
        route: OwnerRoute,
        decoder: str,
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
            payload = json.loads(result.stdout)
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
        return self._probe_json(
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
            lambda value: isinstance(value, list)
            and any(
                isinstance(record, dict) and record.get("lane") == lane
                for record in value
            ),
        )

    def run(self) -> dict[str, Any]:
        routes = [
            self._command_check("machine.observe", self.config.observe_command),
            self._capture_probe(),
            self._probe_json(
                "desktop.hypr",
                [self.config.hypr_control_command, "screenshot-probe"],
                OwnerRoute("desktop-hypr", EnvironmentProfile.WAYLAND),
                "json_object_with_focused",
                lambda value: self._is_json_object(value, "focused"),
            ),
            self._probe_json(
                "desktop.screenshot",
                [self.config.screenshot_control_command, "probe"],
                OwnerRoute("desktop-screenshot", EnvironmentProfile.WAYLAND),
                "json_object_with_tools",
                lambda value: self._is_json_object(value, "tools"),
            ),
            self._probe_json(
                "terminal.kitty",
                [self.config.kitty_control_command, "list", "--json"],
                OwnerRoute("terminal-kitty", EnvironmentProfile.TERMINAL),
                "json_list",
                lambda value: isinstance(value, list),
            ),
            self._probe_json(
                "browser.chrome",
                [self.config.chrome_control_command, "status"],
                OwnerRoute("browser-chrome"),
                "json_object_with_browser",
                lambda value: self._is_json_object(value, "Browser"),
            ),
            self._command_check("beads", self.config.beads_command),
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
