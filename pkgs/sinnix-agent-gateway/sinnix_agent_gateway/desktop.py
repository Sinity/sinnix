from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Any

from .artifacts import ArtifactService
from .capabilities import Capability, Principal
from .config import GatewayConfig
from .execution import (
    EnvironmentProfile,
    ExecutionProfile,
    OwnerDiagnosticError,
    OwnerExecution,
    OwnerRoute,
)


class DesktopError(ValueError):
    pass


class DesktopDiagnosticError(DesktopError, OwnerDiagnosticError):
    def __init__(self, response: dict[str, object]):
        OwnerDiagnosticError.__init__(self, response)


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
        self.execution = execution or OwnerExecution()

    def _command(self, owner: str, arguments: list[str]) -> list[str]:
        if owner == "hypr":
            return [self.config.hypr_control_command, *arguments]
        if owner == "screenshot":
            return [self.config.screenshot_control_command, *arguments]
        raise AssertionError(f"unknown desktop owner {owner}")

    def _run(self, owner: str, arguments: list[str]) -> dict[str, Any]:
        route = OwnerRoute(f"desktop-{owner}", EnvironmentProfile.WAYLAND)
        result = self.execution.run(
            self._command(owner, arguments),
            ExecutionProfile(
                route=route,
                timeout_seconds=15,
                max_stdout_bytes=self.config.max_result_bytes,
            ),
        )
        if result.failure_class is not None:
            raise DesktopDiagnosticError(
                self.artifacts.record_owner_diagnostic(route.name, result)
            )
        return {"owner": owner, "result": result.decode_json_or_text()}

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 8_192) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise DesktopError(f"{name} must be a non-empty string")
        return value

    def capture_output(self, fix_hdr: bool = True) -> dict[str, Any]:
        self.principal.require(Capability.DESKTOP_READ)
        if not isinstance(fix_hdr, bool):
            raise DesktopError("fix_hdr must be boolean")
        capture_dir = self.config.state_dir / "captures" / uuid.uuid4().hex
        capture_dir.mkdir(mode=0o700, parents=True)
        arguments = ["capture-output", "--out-dir", str(capture_dir), "--name", "gateway"]
        if fix_hdr:
            arguments.append("--fix-hdr")
        result = self._run("screenshot", arguments)
        response = result["result"]
        if not isinstance(response, dict):
            raise DesktopError("screenshot control did not return capture metadata")
        files_by_variant = []
        for variant, key in (("raw", "raw_files"), ("corrected", "corrected_files")):
            files = response.get(key, [])
            if not isinstance(files, list):
                raise DesktopError("screenshot control returned malformed capture metadata")
            for value in files:
                if not isinstance(value, str):
                    raise DesktopError("screenshot control returned malformed capture metadata")
                try:
                    source = Path(value).resolve(strict=True)
                except OSError as exc:
                    raise DesktopError("screenshot control did not produce its declared file") from exc
                if capture_dir.resolve() not in source.parents or not source.is_file():
                    raise DesktopError("screenshot control returned a file outside gateway capture state")
                files_by_variant.append((variant, source))
        if not files_by_variant:
            raise DesktopError("screenshot control did not produce any capture files")
        receipt = self.artifacts.attest_capture(
            capture_dir,
            source="desktop-output",
            target={"kind": "current-output"},
            files=[source for _, source in files_by_variant],
        )
        artifacts = [
            {
                "artifact_id": self.artifacts.register(
                    source,
                    kind="desktop-screenshot",
                    owner_id="desktop-capture",
                ),
                "variant": variant,
                "bytes": source.stat().st_size,
                "content_type": mimetypes.guess_type(source.name)[0]
                or "application/octet-stream",
            }
            for variant, source in files_by_variant
        ]
        return {
            "operation": "capture_output",
            "artifact_ids": [artifact["artifact_id"] for artifact in artifacts],
            "artifacts": artifacts,
            "receipt": {
                "capture_id": receipt["capture_id"],
                "source": receipt["source"],
                "target": receipt["target"],
            },
            "capture": {
                "fix_hdr": fix_hdr,
                "color_management": response.get("color_management"),
            },
        }

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
