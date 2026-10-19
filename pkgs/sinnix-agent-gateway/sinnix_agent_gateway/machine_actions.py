from __future__ import annotations

import http.client
import json
import socket
from typing import Any, Callable
from urllib.parse import quote

from .config import GatewayConfig
from .permissions import Permission, Principal


class MachineActionError(ValueError):
    pass


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float = 15.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self.path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class MachineActionService:
    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        connection_factory: Callable[
            [str], http.client.HTTPConnection
        ] = UnixConnection,
    ) -> None:
        self.config = config
        self.principal = principal
        self.connection_factory = connection_factory

    def _request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        *,
        missing_ok: bool = False,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        try:
            connection = self.connection_factory(str(self.config.hub_socket_path))
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            payload_bytes = response.read(self.config.max_result_bytes + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise MachineActionError("hub server endpoint is unavailable") from exc
        finally:
            try:
                connection.close()
            except (OSError, UnboundLocalError):
                pass
        if len(payload_bytes) > self.config.max_result_bytes:
            raise MachineActionError("hub server response exceeded response bound")
        try:
            payload = json.loads(payload_bytes)
        except json.JSONDecodeError as exc:
            raise MachineActionError(
                "hub server returned a malformed response"
            ) from exc
        if response.status == 404 and missing_ok:
            return {}
        if response.status >= 400:
            message = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(message, str):
                raise MachineActionError(f"hub server rejected request: {message}")
            raise MachineActionError("hub server rejected request")
        if not isinstance(payload, dict):
            raise MachineActionError("hub server returned a malformed response")
        return payload

    def snapshot(self) -> dict[str, Any]:
        """Read current hub observation status."""
        self.principal.require(Permission.MACHINE_READ)
        payload = self._request("GET", "/v1/revision")
        if (
            payload.get("schema") != "sinnix-hub-v1"
            or isinstance(payload.get("sequence"), bool)
            or not isinstance(payload.get("sequence"), int)
            or payload["sequence"] < 0
            or not isinstance(payload.get("observed_at"), str)
        ):
            raise MachineActionError("hub server returned a malformed snapshot")
        return {
            "available": True,
            "operation": "actions",
            "owner": "hub-server",
            "schema": payload["schema"],
            "observed_at": payload["observed_at"],
            "revision": payload["sequence"],
            "degradation": payload.get("degradation"),
            "sources": payload.get("sources", {}),
        }

    def prepare(
        self,
        action: str,
        target: dict[str, Any],
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.principal.require(Permission.MACHINE_READ)
        request = {"action": action, "target": target, "parameters": parameters or {}}
        payload = self._request(
            "POST",
            "/v1/actions/prepare",
            json.dumps(request, separators=(",", ":")).encode(),
        )
        if (
            payload.get("action") != action
            or payload.get("target") != target
            or not isinstance(payload.get("expected_target"), dict)
            or not payload["expected_target"]
            or not isinstance(payload.get("observed_at"), str)
        ):
            raise MachineActionError("hub server returned malformed action preparation")
        return payload

    def lookup(self, idempotency_key: str) -> dict[str, Any] | None:
        """Read the retained owner outcome without submitting an action again."""
        self.principal.require(Permission.MACHINE_ACTION)
        return (
            self._request(
                "GET", "/v1/actions/" + quote(idempotency_key, safe=""), missing_ok=True
            )
            or None
        )

    def execute(
        self,
        action: str,
        target: dict[str, Any],
        expected_target: dict[str, Any],
        idempotency_key: str,
        operator_reason: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.principal.require(Permission.MACHINE_ACTION)
        request = {
            "action": action,
            "target": target,
            "expected_target": expected_target,
            "idempotency_key": idempotency_key,
            "operator_reason": operator_reason,
            "parameters": parameters or {},
        }
        return self._request(
            "POST", "/v1/actions", json.dumps(request, separators=(",", ":")).encode()
        )
