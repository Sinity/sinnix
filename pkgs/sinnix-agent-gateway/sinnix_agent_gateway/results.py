from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .artifacts import ArtifactService
from .capabilities import Capability, Principal
from .config import GatewayConfig
from .schemas import V2ToolEnvelope

EXPECTED_ERROR_CODES = frozenset(
    {
        "invalid_request",
        "not_found",
        "unavailable",
        "precondition_failed",
        "stale_cursor",
        "source_changed",
        "conflict",
        "partial_completion",
        "deadline",
        "response_bound",
        "owner_failed",
        "policy_denied",
        "idempotency_conflict",
        "unsupported_capability",
    }
)


class ProtocolError(ValueError):
    """An expected V2 domain failure that remains visible to an MCP caller."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        diagnostic_refs: list[str] | None = None,
    ) -> None:
        if code not in EXPECTED_ERROR_CODES:
            raise ValueError(f"unknown protocol error code: {code}")
        self.code = code
        self.details = dict(details or {})
        self.diagnostic_refs = list(diagnostic_refs or [])
        super().__init__(message)


class ResultError(ValueError):
    """Raised when an immutable V2 response snapshot is unavailable."""

    def __init__(self, message: str, failure_class: str = "unavailable"):
        self.failure_class = failure_class
        super().__init__(message)


def derive_cursor_key(master_key: bytes, purpose: str, principal: str) -> bytes:
    """Derive a purpose and principal bound cursor key from the private key."""
    if not isinstance(master_key, bytes) or len(master_key) < 32:
        raise ResultError("cursor key is malformed", "unavailable")
    if (
        not isinstance(purpose, str)
        or not purpose
        or not isinstance(principal, str)
        or not principal
    ):
        raise ResultError("cursor key derivation scope is malformed", "unavailable")
    message = (
        b"sinnix-gateway-cursor-v1\0" + purpose.encode() + b"\0" + principal.encode()
    )
    return hmac.new(master_key, message, hashlib.sha256).digest()


@dataclass(frozen=True)
class RequestContext:
    """Caller attribution and transaction controls shared by every V2 action."""

    request_id: str
    request_sha256: str
    actor: str | None = None
    reason: str | None = None
    idempotency_key: str | None = None
    deadline_at: float | None = None
    preconditions: Mapping[str, Any] | None = None

    @classmethod
    def create(
        cls,
        request_sha256: str,
        *,
        request_id: str | None = None,
        actor: str | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
        deadline_at: float | None = None,
        preconditions: Mapping[str, Any] | None = None,
    ) -> "RequestContext":
        if len(request_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in request_sha256
        ):
            raise ResultError("request digest is malformed", "invalid_request")
        return cls(
            request_id=request_id or str(uuid.uuid4()),
            request_sha256=request_sha256,
            actor=actor,
            reason=reason,
            idempotency_key=idempotency_key,
            deadline_at=deadline_at,
            preconditions=preconditions,
        )


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class ResultSnapshotWriter:
    """Incrementally materialize an immutable JSONL snapshot without row buffering."""

    def __init__(
        self,
        service: "ResultService",
        *,
        query_sha256: str,
        source_revision: str,
        page_size: int,
    ) -> None:
        if page_size < 1:
            raise ResultError("snapshot page size must be positive", "invalid_request")
        self.service = service
        self.query_sha256 = query_sha256
        self.source_revision = source_revision
        self.page_size = page_size
        self.snapshot_id = str(uuid.uuid4())
        self.directory = service.snapshots_root / f".{self.snapshot_id}.writing"
        self.directory.mkdir(mode=0o700)
        self.rows_path = self.directory / "rows.jsonl"
        self.handle = self.rows_path.open("xb")
        self.first_page: list[Any] = []
        self.row_count = 0
        self.hasher = hashlib.sha256()
        self.closed = False

    def append(self, row: Any) -> None:
        if self.closed:
            raise ResultError("snapshot writer is closed", "unavailable")
        try:
            encoded = _canonical(row)
        except (TypeError, ValueError) as exc:
            raise ResultError(
                "JSONL owner row is not serializable", "owner_failed"
            ) from exc
        if len(encoded) > self.service.config.max_result_bytes:
            raise ResultError(
                "JSONL owner row exceeded response bound", "response_bound"
            )
        line = encoded + b"\n"
        self.handle.write(line)
        self.hasher.update(line)
        self.row_count += 1
        if len(self.first_page) < self.page_size:
            self.first_page.append(row)

    def abort(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.handle.close()
        for path in self.directory.glob("*"):
            path.unlink(missing_ok=True)
        self.directory.rmdir()

    def finish(self) -> dict[str, Any]:
        if self.closed:
            raise ResultError("snapshot writer is closed", "unavailable")
        self.closed = True
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.handle.close()
        expires_at = time.time() + self.service.cursor_ttl_seconds
        metadata = {
            "schema": "sinnix.gateway-result-snapshot.v1",
            "snapshot_id": self.snapshot_id,
            "principal": self.service.principal.name,
            "query_sha256": self.query_sha256,
            "source_revision": self.source_revision,
            "row_count": self.row_count,
            "expires_at": expires_at,
            "rows_sha256": self.hasher.hexdigest(),
        }
        metadata_path = self.directory / "metadata.json"
        metadata_path.write_bytes(_canonical(metadata))
        metadata_path.chmod(0o600)
        self.rows_path.chmod(0o600)
        destination = self.service.snapshots_root / self.snapshot_id
        os.replace(self.directory, destination)
        return metadata


class ResultService:
    """Own immutable, principal-scoped snapshots of bounded V2 responses."""

    schema = "sinnix.gateway-result.v3"
    cursor_ttl_seconds = 3_600

    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        artifacts: ArtifactService | None = None,
    ):
        self.config = config
        self.principal = principal
        self.artifacts = artifacts or ArtifactService(config, principal)
        config.initialize_state()
        self.root = config.state_dir / "results"
        self.snapshots_root = self.root / "snapshots"
        self.snapshots_root.mkdir(mode=0o700, exist_ok=True)
        self.snapshots_root.chmod(0o700)
        self.cursor_key_path = self.root / "cursor-key"
        if not self.cursor_key_path.exists():
            temporary = self.root / f".cursor-key.{uuid.uuid4().hex}.tmp"
            try:
                with temporary.open("xb") as output:
                    output.write(secrets.token_bytes(32))
                    output.flush()
                    os.fsync(output.fileno())
                temporary.chmod(0o600)
                try:
                    os.link(temporary, self.cursor_key_path)
                except FileExistsError:
                    pass
            finally:
                temporary.unlink(missing_ok=True)
        self.cursor_key = self.cursor_key_path.read_bytes()
        if len(self.cursor_key) < 32:
            raise ResultError("cursor key is malformed", "unavailable")

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

    def start_snapshot(
        self,
        *,
        query_sha256: str,
        source_revision: str,
        page_size: int = 100,
    ) -> ResultSnapshotWriter:
        if not source_revision:
            raise ResultError("snapshot source revision is required", "invalid_request")
        return ResultSnapshotWriter(
            self,
            query_sha256=query_sha256,
            source_revision=source_revision,
            page_size=page_size,
        )

    def _cursor(self, payload: Mapping[str, Any]) -> str:
        encoded = base64.urlsafe_b64encode(_canonical(payload)).rstrip(b"=")
        signature = hmac.new(self.cursor_key, encoded, hashlib.sha256).digest()
        return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

    def _decode_cursor(self, cursor: str) -> dict[str, Any]:
        try:
            encoded_text, signature_text = cursor.split(".", 1)
            encoded = encoded_text.encode()
            padding = b"=" * (-len(encoded) % 4)
            signature = base64.urlsafe_b64decode(
                signature_text + "=" * (-len(signature_text) % 4)
            )
            expected = hmac.new(self.cursor_key, encoded, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            decoded = base64.urlsafe_b64decode(encoded + padding)
            payload = json.loads(decoded)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResultError("cursor is invalid", "stale_cursor") from exc
        if not isinstance(payload, dict):
            raise ResultError("cursor is invalid", "stale_cursor")
        return payload

    def _snapshot_metadata(self, snapshot_id: str) -> tuple[dict[str, Any], Path]:
        try:
            snapshot_id = str(uuid.UUID(snapshot_id))
        except ValueError as exc:
            raise ResultError("cursor snapshot is invalid", "stale_cursor") from exc
        directory = self.snapshots_root / snapshot_id
        try:
            metadata = json.loads((directory / "metadata.json").read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ResultError("snapshot is unavailable", "stale_cursor") from exc
        if (
            metadata.get("schema") != "sinnix.gateway-result-snapshot.v1"
            or metadata.get("snapshot_id") != snapshot_id
            or metadata.get("principal") != self.principal.name
            or not isinstance(metadata.get("query_sha256"), str)
            or not isinstance(metadata.get("source_revision"), str)
            or not isinstance(metadata.get("row_count"), int)
            or not isinstance(metadata.get("expires_at"), (int, float))
        ):
            raise ResultError("snapshot is malformed", "stale_cursor")
        return metadata, directory

    def _snapshot_page(
        self,
        metadata: Mapping[str, Any],
        directory: Path,
        offset: int,
        *,
        page_size: int,
    ) -> dict[str, Any]:
        if offset < 0 or page_size < 1:
            raise ResultError("cursor page is invalid", "stale_cursor")
        rows = []
        next_offset = None
        with (directory / "rows.jsonl").open("rb") as handle:
            for index, line in enumerate(handle):
                if index < offset:
                    continue
                if len(rows) == page_size:
                    next_offset = index
                    break
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ResultError(
                        "snapshot row is malformed", "unavailable"
                    ) from exc
        return {
            "rows": rows,
            "row_count": metadata["row_count"],
            "offset": offset,
            "next_offset": next_offset,
        }

    def continue_snapshot(
        self,
        cursor: str,
        *,
        query_sha256: str,
        source_revision: str | None = None,
    ) -> dict[str, Any]:
        payload = self._decode_cursor(cursor)
        snapshot_id = payload.get("snapshot_id")
        offset = payload.get("offset")
        page_size = payload.get("page_size")
        if (
            payload.get("principal") != self.principal.name
            or payload.get("query_sha256") != query_sha256
            or not isinstance(snapshot_id, str)
            or not isinstance(offset, int)
            or not isinstance(page_size, int)
        ):
            raise ResultError("cursor does not match this request", "stale_cursor")
        metadata, directory = self._snapshot_metadata(snapshot_id)
        if (
            payload.get("expires_at") != metadata["expires_at"]
            or time.time() >= metadata["expires_at"]
        ):
            raise ResultError("cursor has expired", "stale_cursor")
        if metadata["query_sha256"] != query_sha256:
            raise ResultError("cursor query does not match snapshot", "stale_cursor")
        if (
            source_revision is not None
            and source_revision != metadata["source_revision"]
        ):
            raise ResultError("source changed after snapshot", "source_changed")
        page = self._snapshot_page(metadata, directory, offset, page_size=page_size)
        page["snapshot_ref"] = f"sinnix://results/{snapshot_id}"
        page["expires_at"] = metadata["expires_at"]
        page["cursor"] = cursor
        page["next_cursor"] = (
            self._cursor(
                {
                    "snapshot_id": snapshot_id,
                    "principal": self.principal.name,
                    "query_sha256": query_sha256,
                    "source_revision": metadata["source_revision"],
                    "offset": page["next_offset"],
                    "page_size": page_size,
                    "expires_at": metadata["expires_at"],
                }
            )
            if page["next_offset"] is not None
            else None
        )
        return page

    def require_payload_bound(self, payload: Any) -> None:
        try:
            payload_bytes = _canonical(payload)
        except (TypeError, ValueError) as exc:
            raise ResultError(
                "owner response is not JSON serializable", "owner_failed"
            ) from exc
        metadata_budget = min(4_096, max(1, self.config.max_result_bytes // 2))
        if len(payload_bytes) > max(1, self.config.max_result_bytes - metadata_budget):
            raise ResultError(
                "owner response exceeded V2 result bound", "response_bound"
            )

    def record(
        self,
        *,
        action: str,
        owner: str,
        route: str,
        outcome: str,
        payload: Any,
        receipt: Mapping[str, Any],
        request: RequestContext | None = None,
        meta: Mapping[str, Any] | None = None,
        page: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if outcome not in {"ok", "error"}:
            raise ResultError("result outcome must be ok or error", "invalid_request")
        request = request or RequestContext.create(hashlib.sha256(b"{}").hexdigest())
        artifact: dict[str, Any] | None = None
        try:
            self.require_payload_bound(payload)
        except ResultError as exc:
            if outcome != "ok" or exc.failure_class != "response_bound":
                raise
            artifact = self.artifacts.register_json(
                payload,
                kind="v2-result",
                owner_id=owner,
                source="v2-result",
                target={"action": action, "route": route},
            )
            payload = {"truncated": True, "artifact": artifact}
            self.require_payload_bound(payload)
        effective_meta = dict(meta or {})
        if artifact is not None:
            refs = set(effective_meta.get("artifact_refs", []))
            refs.add(artifact["ref"])
            effective_meta["artifact_refs"] = sorted(refs)
        metadata = {
            "source": {"owner": owner, "route": route},
            "source_revisions": {},
            "coverage": {},
            "warnings": [],
            "resource_refs": [],
            "artifact_refs": [],
            "correlation_id": request.request_id,
            **effective_meta,
        }
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
                "request_id": request.request_id,
                "request_sha256": request.request_sha256,
                "idempotency_key": request.idempotency_key,
            },
            "receipt": self._receipt(receipt),
            "page": dict(page) if page is not None else self._page(payload),
            "meta": metadata,
        }
        envelope["data"] = payload if outcome == "ok" else None
        envelope["error"] = payload if outcome == "error" else None
        envelope["result"]["sha256"] = self._digest(envelope)
        try:
            V2ToolEnvelope.model_validate(envelope)
        except ValueError as exc:
            raise ResultError(
                "V2 result envelope is malformed", "owner_failed"
            ) from exc
        encoded = _canonical(envelope)
        if len(encoded) > max(self.config.max_result_bytes, 4_096):
            raise ResultError(
                "V2 result envelope exceeded response bound", "response_bound"
            )
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

    def record_snapshot(
        self,
        *,
        action: str,
        owner: str,
        route: str,
        writer: ResultSnapshotWriter,
        receipt: Mapping[str, Any],
        request: RequestContext,
    ) -> dict[str, Any]:
        metadata = writer.finish()
        initial_cursor = self._cursor(
            {
                "snapshot_id": metadata["snapshot_id"],
                "principal": self.principal.name,
                "query_sha256": metadata["query_sha256"],
                "source_revision": metadata["source_revision"],
                "offset": writer.page_size,
                "page_size": writer.page_size,
                "expires_at": metadata["expires_at"],
            }
        )
        next_cursor = (
            initial_cursor if metadata["row_count"] > writer.page_size else None
        )
        return self.record(
            action=action,
            owner=owner,
            route=route,
            outcome="ok",
            payload={"rows": writer.first_page, "row_count": metadata["row_count"]},
            receipt=receipt,
            request=request,
            page={
                "kind": "snapshot",
                "cursor": None,
                "next_cursor": next_cursor,
                "total": metadata["row_count"],
                "expires_at": metadata["expires_at"],
                "snapshot_ref": f"sinnix://results/{metadata['snapshot_id']}",
            },
            meta={
                "source": {"owner": owner, "route": route},
                "source_revisions": {"owner": metadata["source_revision"]},
                "artifact_refs": [f"sinnix://results/{metadata['snapshot_id']}"],
            },
        )

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
