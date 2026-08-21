from __future__ import annotations

import json
import subprocess
import tempfile
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig


class DesktopError(ValueError):
    pass


class DesktopService:
    _READ_OPERATIONS = {
        "status": ("hypr", "status"),
        "active_window": ("hypr", "active-window"),
        "clients": ("hypr", "clients", "--json"),
        "workspaces": ("hypr", "workspaces"),
        "binds": ("hypr", "binds", "--json"),
        "screenshot_probe": ("hypr", "screenshot-probe"),
        "color_probe": ("screenshot", "probe"),
    }

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal

    def _command(self, owner: str, arguments: list[str]) -> list[str]:
        if owner == "hypr":
            return [self.config.hypr_control_command, *arguments]
        if owner == "screenshot":
            return [self.config.screenshot_control_command, *arguments]
        raise AssertionError(f"unknown desktop owner {owner}")

    def _run(self, owner: str, arguments: list[str]) -> dict[str, Any]:
        command = self._command(owner, arguments)
        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=15,
                    check=False,
                )
                output.seek(0)
                data = output.read(self.config.max_result_bytes + 1)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DesktopError(f"desktop control unavailable: {type(exc).__name__}") from exc
        if len(data) > self.config.max_result_bytes:
            raise DesktopError("desktop control response exceeded response bound")
        if result.returncode != 0:
            raise DesktopError("desktop control command failed")
        text = data.decode("utf-8", errors="replace")
        try:
            value: Any = json.loads(text)
        except json.JSONDecodeError:
            value = text
        return {"owner": owner, "result": value}

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 8_192) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise DesktopError(f"{name} must be a non-empty string")
        return value

    def read(self, operation: str) -> dict[str, Any]:
        self.principal.require(Capability.DESKTOP_READ)
        try:
            owner, *arguments = self._READ_OPERATIONS[operation]
        except KeyError as exc:
            raise DesktopError(
                f"unknown desktop read operation {operation!r}; "
                f"available: {sorted(self._READ_OPERATIONS)}"
            ) from exc
        return {"operation": operation, **self._run(owner, arguments)}

    def action(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.principal.require(Capability.DESKTOP_ACTION)
        if not isinstance(arguments, dict):
            raise DesktopError("arguments must be an object")
        if operation == "focus_window":
            if set(arguments) != {"window"}:
                raise DesktopError("focus_window requires only window")
            window = self._string(arguments["window"], "window")
            result = self._run("hypr", ["focus-window", window])
            return {
                "operation": operation,
                "target": {"window": window},
                **result,
                "postcondition": self.read("active_window")["result"],
            }
        if operation == "dispatch":
            if set(arguments) != {"dispatcher", "args"}:
                raise DesktopError("dispatch requires dispatcher and args")
            dispatcher = self._string(arguments["dispatcher"], "dispatcher", 128)
            extra = arguments["args"]
            if (
                not isinstance(extra, list)
                or len(extra) > 32
                or any(not isinstance(value, str) or len(value) > 8_192 for value in extra)
            ):
                raise DesktopError("dispatch args must contain at most 32 strings")
            return {
                "operation": operation,
                **self._run("hypr", ["dispatch", dispatcher, *extra]),
            }
        if operation == "send_shortcut":
            allowed = {"mods", "key", "window"}
            if not {"mods", "key"} <= set(arguments) or set(arguments) - allowed:
                raise DesktopError("send_shortcut requires mods, key, and optional window")
            command = [
                "send-shortcut",
                self._string(arguments["mods"], "mods", 128),
                self._string(arguments["key"], "key", 128),
            ]
            if "window" in arguments:
                command.append(self._string(arguments["window"], "window"))
            return {"operation": operation, **self._run("hypr", command)}
        if operation == "send_keystate":
            allowed = {"mods", "key", "state", "window"}
            if not {"mods", "key", "state"} <= set(arguments) or set(arguments) - allowed:
                raise DesktopError(
                    "send_keystate requires mods, key, state, and optional window"
                )
            state = self._string(arguments["state"], "state", 16)
            if state not in {"down", "repeat", "up"}:
                raise DesktopError("state must be down, repeat, or up")
            command = [
                "send-keystate",
                self._string(arguments["mods"], "mods", 128),
                self._string(arguments["key"], "key", 128),
                state,
            ]
            if "window" in arguments:
                command.append(self._string(arguments["window"], "window"))
            return {"operation": operation, **self._run("hypr", command)}
        if operation == "paste":
            allowed = {"window", "text", "enter"}
            if not {"window", "text"} <= set(arguments) or set(arguments) - allowed:
                raise DesktopError("paste requires window, text, and optional enter")
            command = [
                "paste",
                self._string(arguments["window"], "window"),
                "--text",
                self._string(arguments["text"], "text"),
            ]
            if arguments.get("enter") is True:
                command.append("--enter")
            elif "enter" in arguments and not isinstance(arguments["enter"], bool):
                raise DesktopError("enter must be boolean")
            return {"operation": operation, **self._run("hypr", command)}
        if operation == "keyword":
            if set(arguments) != {"name", "value"}:
                raise DesktopError("keyword requires name and value")
            return {
                "operation": operation,
                **self._run(
                    "hypr",
                    [
                        "keyword",
                        self._string(arguments["name"], "name", 256),
                        self._string(arguments["value"], "value"),
                    ],
                ),
            }
        raise DesktopError(
            f"unknown desktop action {operation!r}; available: "
            "['dispatch', 'focus_window', 'keyword', 'paste', "
            "'send_keystate', 'send_shortcut']"
        )
