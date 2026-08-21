from __future__ import annotations

import http.client
import json
import socket
from pathlib import Path
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
        connection_factory: Callable[[str], http.client.HTTPConnection] = UnixConnection,
    ) -> None:
        self.config = config
        self.principal = principal
        self.connection_factory = connection_factory

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
        try:
            connection = self.connection_factory(str(self.config.ops_socket_path))
            connection.request(
                "POST",
                "/v1/actions",
                json.dumps(request, separators=(",", ":")),
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            body = response.read(self.config.max_result_bytes + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise MachineActionError("ops reducer action endpoint is unavailable") from exc
        finally:
            try:
                connection.close()
            except (OSError, UnboundLocalError):
                pass
        if len(body) > self.config.max_result_bytes:
            raise MachineActionError("ops reducer receipt exceeded response bound")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MachineActionError("ops reducer returned malformed action response") from exc
        if response.status >= 400:
            message = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(message, str):
                raise MachineActionError(f"ops reducer rejected action: {message}")
            raise MachineActionError("ops reducer rejected action")
        if not isinstance(payload, dict):
            raise MachineActionError("ops reducer returned malformed action receipt")
        return payload
