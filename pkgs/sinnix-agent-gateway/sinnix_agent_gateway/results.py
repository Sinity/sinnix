from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from .capabilities import Capability, Principal
from .config import GatewayConfig


class ResultError(ValueError):
    """Raised when an immutable V2 response snapshot is unavailable."""

    def __init__(self, message: str, failure_class: str = "result_unavailable"):
        self.failure_class = failure_class
        super().__init__(message)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class ResultService:
    """Own immutable, principal-scoped snapshots of bounded V2 responses."""

    schema = "sinnix.gateway-result.v2"

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        config.initialize_state()
        self.root = config.state_dir / "results"

    @staticmethod
    def _page(payload: Any) -> dict[str, int | None | str] | None:
        if not isinstance(payload, Mapping):
            return None
        cursor = payload.get("cursor")
        next_cursor = payload.get("next_cursor")
        if isinstance(cursor, int) and (
            next_cursor is None or isinstance(next_cursor, int)
        ):
            page: dict[str, int | None | str] = {
                "kind": "cursor",
                "cursor": cursor,
                "next_cursor": next_cursor,
            }
            if isinstance(payload.get("total"), int):
                page["total"] = payload["total"]
            return page
        offset = payload.get("offset")
        next_offset = payload.get("next_offset")
        if isinstance(offset, int) and (
            next_offset is None or isinstance(next_offset, int)
        ):
            return {
                "kind": "offset",
                "offset": offset,
                "next_offset": next_offset,
            }
        return None

    @staticmethod
    def _result_ref(result_id: str) -> str:
        return f"sinnix://results/{result_id}"

    @staticmethod
    def _receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
        event_id = receipt.get("event_id")
        sequence = receipt.get("sequence")
        entry_hash = receipt.get("entry_hash")
        if (
            not isinstance(event_id, str)
            or not isinstance(sequence, int)
            or not isinstance(entry_hash, str)
        ):
            raise ResultError("audit receipt is malformed")
        return {
            "receipt_id": event_id,
            "ref": f"sinnix://receipts/{event_id}",
            "sequence": sequence,
            "entry_hash": entry_hash,
        }

    @staticmethod
    def _digest(envelope: Mapping[str, Any]) -> str:
        material = json.loads(_canonical(envelope))
        material["result"].pop("sha256", None)
        return hashlib.sha256(_canonical(material)).hexdigest()

    @staticmethod
    def _normalized_id(result_id: str) -> str:
        try:
            return str(uuid.UUID(result_id))
        except ValueError as exc:
            raise ResultError("invalid result ID") from exc

    def _path(self, result_id: str) -> Path:
        return self.root / f"{self._normalized_id(result_id)}.json"

    def require_payload_bound(self, payload: Any) -> None:
        try:
            payload_bytes = _canonical(payload)
        except (TypeError, ValueError) as exc:
            raise ResultError(
                "owner response is not JSON serializable", "result_malformed"
            ) from exc
        metadata_budget = min(4_096, max(1, self.config.max_result_bytes // 2))
        if len(payload_bytes) > max(1, self.config.max_result_bytes - metadata_budget):
            raise ResultError("owner response exceeded V2 result bound", "response_bound")

    def record(
        self,
        *,
        action: str,
        owner: str,
        route: str,
        outcome: str,
        payload: Any,
        receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        if outcome not in {"ok", "error"}:
            raise ResultError("result outcome must be ok or error")
        self.require_payload_bound(payload)
        result_id = str(uuid.uuid4())
        observed_at = time.time()
        envelope: dict[str, Any] = {
            "schema": self.schema,
            "result": {
                "result_id": result_id,
                "ref": self._result_ref(result_id),
                "action": action,
                "principal": self.principal.name,
                "owner": owner,
                "route": route,
                "outcome": outcome,
                "observed_at": observed_at,
            },
            "receipt": self._receipt(receipt),
            "page": self._page(payload),
        }
        envelope["data" if outcome == "ok" else "error"] = payload
        envelope["result"]["sha256"] = self._digest(envelope)
        encoded = _canonical(envelope)
        if len(encoded) > self.config.max_result_bytes:
            raise ResultError("V2 result envelope exceeded response bound", "response_bound")
        destination = self._path(result_id)
        temporary = self.root / f".{result_id}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return envelope

    def read(self, result_id: str) -> dict[str, Any]:
        self.principal.require(Capability.AUDIT_READ)
        result_id = self._normalized_id(result_id)
        path = self._path(result_id)
        try:
            envelope = json.loads(path.read_text())
        except FileNotFoundError as exc:
            raise ResultError("unknown result") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ResultError("malformed result snapshot") from exc
        result = envelope.get("result")
        if (
            not isinstance(result, dict)
            or envelope.get("schema") != self.schema
            or result.get("result_id") != result_id
            or result.get("ref") != self._result_ref(result_id)
            or result.get("principal") != self.principal.name
            or result.get("sha256") != self._digest(envelope)
        ):
            raise ResultError("malformed or unavailable result snapshot")
        return envelope
