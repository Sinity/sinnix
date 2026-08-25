from __future__ import annotations

import http.client
import json
import socket
from typing import Any, Callable

from .capabilities import Capability, Principal
from .config import GatewayConfig


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
        self, method: str, path: str, body: bytes | None = None
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        try:
            connection = self.connection_factory(str(self.config.ops_socket_path))
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            payload_bytes = response.read(self.config.max_result_bytes + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise MachineActionError("ops reducer endpoint is unavailable") from exc
        finally:
            try:
                connection.close()
            except (OSError, UnboundLocalError):
                pass
        if len(payload_bytes) > self.config.max_result_bytes:
            raise MachineActionError("ops reducer response exceeded response bound")
        try:
            payload = json.loads(payload_bytes)
        except json.JSONDecodeError as exc:
            raise MachineActionError(
                "ops reducer returned a malformed response"
            ) from exc
        if response.status >= 400:
            message = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(message, str):
                raise MachineActionError(f"ops reducer rejected request: {message}")
            raise MachineActionError("ops reducer rejected request")
        if not isinstance(payload, dict):
            raise MachineActionError("ops reducer returned a malformed response")
        return payload

    def snapshot(self) -> dict[str, Any]:
        """Read the authority revision required by a subsequent machine action."""
        self.principal.require(Capability.MACHINE_READ)
        payload = self._request("GET", "/v1/revision")
        if (
            payload.get("schema") != "sinnix-ops-v1"
            or isinstance(payload.get("sequence"), bool)
            or not isinstance(payload.get("sequence"), int)
            or payload["sequence"] < 0
            or not isinstance(payload.get("observed_at"), str)
        ):
            raise MachineActionError("ops reducer returned a malformed snapshot")
        return {
            "available": True,
            "operation": "actions",
            "owner": "ops-reducer",
            "schema": payload["schema"],
            "observed_at": payload["observed_at"],
            "revision": payload["sequence"],
            "degradation": payload.get("degradation"),
            "sources": payload.get("sources", {}),
        }

    def execute(
        self,
        action: str,
        target: dict[str, Any],
        expected_revision: int,
        idempotency_key: str,
        operator_reason: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.principal.require(Capability.MACHINE_ACTION)
        request = {
            "action": action,
            "target": target,
            "expected_revision": expected_revision,
            "idempotency_key": idempotency_key,
            "operator_reason": operator_reason,
            "parameters": parameters or {},
        }
        return self._request(
            "POST", "/v1/actions", json.dumps(request, separators=(",", ":")).encode()
        )
