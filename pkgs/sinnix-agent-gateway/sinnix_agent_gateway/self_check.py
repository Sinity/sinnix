from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .config import GatewayConfig


class GatewaySelfCheck:
    """Non-mutating route preflight for configured gateway owners."""

    def __init__(self, config: GatewayConfig):
        self.config = config

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

    def run(self) -> dict[str, Any]:
        routes = [
            self._command_check("machine.observe", self.config.observe_command),
            self._command_check("capture.query", self.config.capture_command),
            self._command_check("desktop.hypr", self.config.hypr_control_command),
            self._command_check(
                "desktop.screenshot", self.config.screenshot_control_command
            ),
            self._command_check("terminal.kitty", self.config.kitty_control_command),
            self._command_check("browser.chrome", self.config.chrome_control_command),
            self._command_check("beads", self.config.beads_command),
        ]
        if any(server.get("brokered") for server in self.config.mcp_broker_servers.values()):
            bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
            runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
            routes.append(
                {
                    "route": "mcp.user_bus",
                    "status": "pass" if bus and runtime_dir else "degraded",
                    "failure_class": None if bus and runtime_dir else "user_bus_environment_missing",
                    "dbus_session_bus_address": bool(bus),
                    "xdg_runtime_dir": bool(runtime_dir),
                }
            )
        return {
            "status": "ready" if all(row["status"] == "pass" for row in routes) else "degraded",
            "routes": routes,
        }
