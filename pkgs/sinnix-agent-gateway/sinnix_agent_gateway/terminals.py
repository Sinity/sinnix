from __future__ import annotations

import json
import subprocess
import tempfile
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig


class TerminalError(ValueError):
    pass


class TerminalService:
    _CAPTURE_EXTENTS = {
        "screen",
        "all",
        "selection",
        "last_cmd_output",
        "last_non_empty_output",
    }

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal

    def _run(self, arguments: list[str]) -> dict[str, Any]:
        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    [self.config.kitty_control_command, *arguments],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                    check=False,
                )
                output.seek(0)
                data = output.read(self.config.max_result_bytes + 1)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TerminalError(f"Kitty control unavailable: {type(exc).__name__}") from exc
        if len(data) > self.config.max_result_bytes:
            raise TerminalError("Kitty control response exceeded response bound")
        if result.returncode != 0:
            raise TerminalError("Kitty control command failed")
        text = data.decode("utf-8", errors="replace")
        try:
            value: Any = json.loads(text)
        except json.JSONDecodeError:
            value = text
        return {"result": value}

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 64_000) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise TerminalError(f"{name} must be a non-empty string")
        return value

    def read(self, operation: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        self.principal.require(Capability.TERMINAL_READ)
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise TerminalError("arguments must be an object")
        if operation == "list":
            if arguments:
                raise TerminalError("list does not accept arguments")
            return {"operation": operation, **self._run(["list", "--json"])}
        if operation == "capture":
            allowed = {"match", "extent", "ansi"}
            if "match" not in arguments or set(arguments) - allowed:
                raise TerminalError("capture requires match and optional extent or ansi")
            extent = arguments.get("extent", "last_cmd_output")
            if extent not in self._CAPTURE_EXTENTS:
                raise TerminalError(f"unsupported capture extent: {extent!r}")
            command = [
                "capture",
                "--match",
                self._string(arguments["match"], "match", 512),
                "--extent",
                extent,
            ]
            if arguments.get("ansi") is True:
                command.append("--ansi")
            elif "ansi" in arguments and not isinstance(arguments["ansi"], bool):
                raise TerminalError("ansi must be boolean")
            return {"operation": operation, **self._run(command)}
        raise TerminalError("unknown terminal read operation; available: ['capture', 'list']")

    def action(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.principal.require(Capability.TERMINAL_ACTION)
        if not isinstance(arguments, dict):
            raise TerminalError("arguments must be an object")
        if operation == "focus":
            if set(arguments) != {"match"}:
                raise TerminalError("focus requires only match")
            match = self._string(arguments["match"], "match", 512)
            return {"operation": operation, "target": match, **self._run(["focus", "--match", match])}
        if operation == "send":
            allowed = {"match", "text", "enter", "bracketed_paste"}
            if not {"match", "text"} <= set(arguments) or set(arguments) - allowed:
                raise TerminalError(
                    "send requires match, text, and optional enter or bracketed_paste"
                )
            command = [
                "send",
                "--match",
                self._string(arguments["match"], "match", 512),
                "--text",
                self._string(arguments["text"], "text"),
            ]
            for key, flag in (("enter", "--enter"), ("bracketed_paste", "--bracketed-paste")):
                if arguments.get(key) is True:
                    command.append(flag)
                elif key in arguments and not isinstance(arguments[key], bool):
                    raise TerminalError(f"{key} must be boolean")
            return {"operation": operation, **self._run(command)}
        if operation == "key":
            if set(arguments) != {"match", "keys"}:
                raise TerminalError("key requires match and keys")
            keys = arguments["keys"]
            if (
                not isinstance(keys, list)
                or not keys
                or len(keys) > 16
                or any(not isinstance(key, str) or not key or len(key) > 128 for key in keys)
            ):
                raise TerminalError("keys must contain 1-16 non-empty strings")
            return {
                "operation": operation,
                **self._run(
                    [
                        "key",
                        "--match",
                        self._string(arguments["match"], "match", 512),
                        "--keys",
                        *keys,
                    ]
                ),
            }
        if operation == "run":
            if set(arguments) != {"match", "command"}:
                raise TerminalError("run requires match and command")
            return {
                "operation": operation,
                **self._run(
                    [
                        "run",
                        "--match",
                        self._string(arguments["match"], "match", 512),
                        "--command",
                        self._string(arguments["command"], "command"),
                    ]
                ),
            }
        raise TerminalError(
            "unknown terminal action; available: ['focus', 'key', 'run', 'send']"
        )
