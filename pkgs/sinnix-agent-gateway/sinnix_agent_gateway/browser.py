from __future__ import annotations

import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any

from .artifacts import ArtifactService
from .capabilities import Capability, Principal
from .config import GatewayConfig
from sinnix_mcp.execution import ExecutionProfile, OwnerExecution, OwnerRoute


class BrowserError(ValueError):
    pass


class BrowserService:
    def __init__(
        self, config: GatewayConfig, principal: Principal, artifacts: ArtifactService
    ):
        self.config = config
        self.principal = principal
        self.artifacts = artifacts
        self.execution = OwnerExecution()

    @property
    def _targets_path(self) -> Path:
        return self.config.state_dir / "browser-targets.json"

    def _run(self, arguments: list[str], timeout: int = 30) -> dict[str, Any]:
        result = self.execution.run(
            [self.config.chrome_control_command, *arguments],
            ExecutionProfile(
                route=OwnerRoute("browser-chrome"),
                timeout_seconds=timeout,
                max_stdout_bytes=self.config.max_result_bytes,
            ),
        )
        if result.failure_class == "command_unavailable:FileNotFoundError":
            raise BrowserError("Chrome control unavailable: FileNotFoundError")
        if result.failure_class == "command_timeout":
            raise BrowserError("Chrome control unavailable: TimeoutExpired")
        if result.failure_class == "command_output_bound":
            raise BrowserError("Chrome control response exceeded response bound")
        if result.failure_class is not None:
            detail = result.stderr_excerpt()
            raise BrowserError(
                f"Chrome control command failed: {detail}" if detail else "Chrome control command failed"
            )
        return {"result": result.decode_json_or_text()}

    @staticmethod
    def _string(value: Any, name: str, maximum: int = 64_000) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise BrowserError(f"{name} must be a non-empty string")
        return value

    def _load_targets(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self._targets_path.read_text())
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError):
            raise BrowserError("gateway browser target registry is malformed") from None
        if not isinstance(raw, dict) or any(
            not isinstance(page_id, str) or not isinstance(value, dict)
            for page_id, value in raw.items()
        ):
            raise BrowserError("gateway browser target registry is malformed")
        return raw

    def _save_targets(self, targets: dict[str, dict[str, Any]]) -> None:
        self.config.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self._targets_path.with_name(
            f".{self._targets_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            temporary.write_text(json.dumps(targets, sort_keys=True, separators=(",", ":")))
            temporary.chmod(0o600)
            os.replace(temporary, self._targets_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _require_owned_target(self, page_id: str) -> str:
        page_id = self._string(page_id, "page_id", 256)
        if page_id not in self._load_targets():
            raise BrowserError(
                "browser action target is not a gateway-created agent window"
            )
        return page_id

    def capture(
        self,
        page_id: str,
        image_format: str = "png",
        full_page: bool = False,
        quality: int | None = None,
    ) -> dict[str, Any]:
        self.principal.require(Capability.BROWSER_READ)
        page_id = self._require_owned_target(page_id)
        if image_format not in {"png", "jpeg"}:
            raise BrowserError("image_format must be png or jpeg")
        if not isinstance(full_page, bool):
            raise BrowserError("full_page must be boolean")
        if quality is not None and (
            isinstance(quality, bool) or not isinstance(quality, int) or not 1 <= quality <= 100
        ):
            raise BrowserError("quality must be 1-100")
        capture_dir = self.config.state_dir / "captures" / uuid.uuid4().hex
        capture_dir.mkdir(mode=0o700, parents=True)
        source = capture_dir / f"browser.{image_format}"
        command = [
            "screenshot",
            page_id,
            "--format",
            image_format,
            "--out",
            str(source),
        ]
        if full_page:
            command.append("--full-page")
        if quality is not None:
            command.extend(["--quality", str(quality)])
        self._run(command)
        try:
            source = source.resolve(strict=True)
        except OSError as exc:
            raise BrowserError("Chrome control did not produce its declared screenshot") from exc
        if capture_dir.resolve() not in source.parents or not source.is_file():
            raise BrowserError("Chrome control returned a file outside gateway capture state")
        receipt = self.artifacts.attest_capture(
            capture_dir,
            source="chrome-cdp",
            target={"kind": "gateway-owned-browser-target", "page_id": page_id},
            files=[source],
        )
        artifact_id = self.artifacts.register(
            source,
            kind="browser-screenshot",
            owner_id="browser-capture",
        )
        return {
            "operation": "screenshot",
            "page_id": page_id,
            "artifact_id": artifact_id,
            "artifact": {
                "artifact_id": artifact_id,
                "bytes": source.stat().st_size,
                "content_type": mimetypes.guess_type(source.name)[0]
                or "application/octet-stream",
            },
            "receipt": {
                "capture_id": receipt["capture_id"],
                "source": receipt["source"],
                "target": receipt["target"],
            },
            "capture": {"image_format": image_format, "full_page": full_page},
        }

    def read(
        self,
        operation: str,
        page_id: str | None = None,
        selector: str | None = None,
    ) -> dict[str, Any]:
        self.principal.require(Capability.BROWSER_READ)
        if operation in {"status", "list", "list_tabs"}:
            if page_id is not None or selector is not None:
                raise BrowserError(f"{operation} does not accept page_id or selector")
            command = {"status": "status", "list": "list", "list_tabs": "list-tabs"}[operation]
            return {"operation": operation, **self._run([command])}
        if operation not in {"info", "get_text", "get_html"}:
            raise BrowserError(
                "unknown browser read operation; available: "
                "['get_html', 'get_text', 'info', 'list', 'list_tabs', 'status']"
            )
        page_id = self._string(page_id, "page_id", 256)
        command = {"info": "info", "get_text": "get-text", "get_html": "get-html"}[operation]
        arguments = [command, page_id]
        if selector is not None:
            if operation == "info":
                raise BrowserError("info does not accept selector")
            arguments.extend(["--selector", self._string(selector, "selector", 8_192)])
        return {"operation": operation, "page_id": page_id, **self._run(arguments)}

    def action(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.principal.require(Capability.BROWSER_ACTION)
        if not isinstance(arguments, dict):
            raise BrowserError("arguments must be an object")
        if operation == "agent_window":
            if set(arguments) - {"url"}:
                raise BrowserError("agent_window accepts only optional url")
            command = ["agent-window"]
            if "url" in arguments:
                command.extend(["--url", self._string(arguments["url"], "url")])
            result = self._run(command)
            target = result["result"]
            if isinstance(target, str):
                for line in target.splitlines():
                    try:
                        candidate = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
                        target = candidate
                        break
            if not isinstance(target, dict) or not isinstance(target.get("id"), str):
                raise BrowserError("agent-window did not return a page ID")
            if target.get("parked") is not True:
                try:
                    self._run(["close", target["id"]])
                except BrowserError:
                    pass
                raise BrowserError("agent-window was not parked on the hidden workspace")
            targets = self._load_targets()
            targets[target["id"]] = target
            self._save_targets(targets)
            return {"operation": operation, "target": target}
        page_id = self._require_owned_target(arguments.get("page_id"))
        execution_timeout = 30
        if operation == "navigate":
            if set(arguments) != {"page_id", "url"}:
                raise BrowserError("navigate requires page_id and url")
            command = ["navigate", page_id, "--url", self._string(arguments["url"], "url")]
        elif operation == "reload":
            if set(arguments) != {"page_id"}:
                raise BrowserError("reload requires only page_id")
            command = ["reload", page_id]
        elif operation == "inject_text":
            allowed = {"page_id", "text", "selector"}
            if not {"page_id", "text"} <= set(arguments) or set(arguments) - allowed:
                raise BrowserError("inject_text requires page_id, text, and optional selector")
            command = [
                "inject-text",
                page_id,
                "--text",
                self._string(arguments["text"], "text"),
            ]
            if "selector" in arguments:
                command.extend(["--selector", self._string(arguments["selector"], "selector", 8_192)])
        elif operation == "click":
            if set(arguments) != {"page_id", "selector"}:
                raise BrowserError("click requires page_id and selector")
            command = ["click", page_id, "--selector", self._string(arguments["selector"], "selector", 8_192)]
        elif operation == "fill_form":
            if set(arguments) != {"page_id", "selector", "value"}:
                raise BrowserError("fill_form requires page_id, selector, and value")
            command = [
                "fill-form",
                page_id,
                "--selector",
                self._string(arguments["selector"], "selector", 8_192),
                "--value",
                self._string(arguments["value"], "value"),
            ]
        elif operation in {"evaluate", "await"}:
            javascript_key = "javascript"
            allowed = {"page_id", javascript_key, "timeout_seconds"}
            if not {"page_id", javascript_key} <= set(arguments) or set(arguments) - allowed:
                raise BrowserError(f"{operation} requires page_id, javascript, and optional timeout_seconds")
            timeout = arguments.get("timeout_seconds", 30)
            if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 300:
                raise BrowserError("timeout_seconds must be 1-300")
            command = [
                "evaluate" if operation == "evaluate" else "await",
                page_id,
                "--js",
                self._string(arguments[javascript_key], javascript_key),
            ]
            if operation == "await":
                command.extend(["--timeout-sec", str(timeout)])
                execution_timeout = timeout + 10
        elif operation == "wait_selector":
            allowed = {"page_id", "selector", "timeout_seconds"}
            if not {"page_id", "selector"} <= set(arguments) or set(arguments) - allowed:
                raise BrowserError("wait_selector requires page_id, selector, and optional timeout_seconds")
            timeout = arguments.get("timeout_seconds", 30)
            if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 300:
                raise BrowserError("timeout_seconds must be 1-300")
            command = [
                "wait-selector",
                page_id,
                "--selector",
                self._string(arguments["selector"], "selector", 8_192),
                "--timeout-sec",
                str(timeout),
            ]
            execution_timeout = timeout + 10
        elif operation == "close":
            if set(arguments) != {"page_id"}:
                raise BrowserError("close requires only page_id")
            command = ["close", page_id]
        else:
            raise BrowserError(
                "unknown browser action; available: ['agent_window', 'await', 'click', "
                "'close', 'evaluate', 'fill_form', 'inject_text', 'navigate', 'reload', "
                "'wait_selector']"
            )
        result = {
            "operation": operation,
            "page_id": page_id,
            **self._run(command, execution_timeout),
        }
        if operation == "close":
            targets = self._load_targets()
            targets.pop(page_id, None)
            self._save_targets(targets)
        return result
