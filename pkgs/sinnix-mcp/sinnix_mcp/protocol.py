from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from .refs import SinnixRef

PROTOCOL_SCHEMA_VERSION = 1
ERROR_SCHEMA_VERSION = 1
DEFAULT_INLINE_PAYLOAD_BYTES = 262_144


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    POLICY_DENIED = "POLICY_DENIED"
    OWNER_UNAVAILABLE = "OWNER_UNAVAILABLE"
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"
    RESOURCE_DEFERRED = "RESOURCE_DEFERRED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    OPERATION_FAILED = "OPERATION_FAILED"
    RESULT_INVALID = "RESULT_INVALID"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _validate_uuid(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a UUID")
    try:
        UUID(value)
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{name} must be a UUID") from error


@dataclass(frozen=True)
class SourceBinding:
    """Names the authority generation from which a result was read or derived."""

    source_ref: SinnixRef
    generation: str
    root_digest: str

    def __post_init__(self) -> None:
        if not self.generation:
            raise ValueError("source binding requires a non-empty generation")
        if not self.root_digest.startswith("sha256:") or len(self.root_digest) != 71:
            raise ValueError("source binding root_digest must be a sha256: digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "source_ref": str(self.source_ref),
            "generation": self.generation,
            "root_digest": self.root_digest,
        }


@dataclass(frozen=True)
class OpaquePayload:
    """A bounded inline result or an immutable opaque artifact reference."""

    inline: Any | None = None
    ref: SinnixRef | None = None
    digest: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    inline_limit: int = field(default=DEFAULT_INLINE_PAYLOAD_BYTES, repr=False, compare=False)

    def __post_init__(self) -> None:
        inline_present = self.inline is not None
        opaque_present = self.ref is not None
        if inline_present == opaque_present:
            raise ValueError("payload requires exactly one of inline or ref")
        if inline_present:
            if len(_canonical_json(self.inline)) > self.inline_limit:
                raise ValueError("inline payload exceeds its configured bound")
            if any(value is not None for value in (self.digest, self.media_type, self.size_bytes)):
                raise ValueError("inline payload cannot carry opaque artifact metadata")
        else:
            if self.digest is None or not self.digest.startswith("sha256:") or len(self.digest) != 71:
                raise ValueError("opaque payload requires a sha256: digest")
            if not self.media_type:
                raise ValueError("opaque payload requires a media_type")
            if self.size_bytes is None or self.size_bytes < 0:
                raise ValueError("opaque payload requires a non-negative size_bytes")

    @classmethod
    def bounded(cls, value: Any, *, limit: int = DEFAULT_INLINE_PAYLOAD_BYTES) -> "OpaquePayload":
        return cls(inline=value, inline_limit=limit)

    def to_dict(self) -> dict[str, Any]:
        if self.inline is not None:
            return {"kind": "inline", "value": self.inline}
        return {
            "kind": "opaque",
            "ref": str(self.ref),
            "digest": self.digest,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class RequestEnvelope:
    """One versioned request from a stateless frontend to an authoritative owner."""

    request_id: str
    correlation_id: str
    operation: str
    owner: str
    principal: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    schema: int = PROTOCOL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema != PROTOCOL_SCHEMA_VERSION:
            raise ValueError(f"unsupported request schema: {self.schema}")
        _validate_uuid("request_id", self.request_id)
        _validate_uuid("correlation_id", self.correlation_id)
        if not isinstance(self.operation, str) or not self.operation or "." not in self.operation:
            raise ValueError("operation must be a dotted canonical name")
        if not isinstance(self.owner, str) or not isinstance(self.principal, str):
            raise ValueError("request requires owner and principal")
        if not self.owner or not self.principal:
            raise ValueError("request requires owner and principal")
        if self.idempotency_key is not None:
            if not isinstance(self.idempotency_key, str) or not self.idempotency_key:
                raise ValueError("idempotency_key cannot be empty")
        if not isinstance(self.arguments, Mapping):
            raise ValueError("arguments must be an object")
        arguments = dict(self.arguments)
        if not all(isinstance(key, str) for key in arguments):
            raise ValueError("arguments keys must be strings")
        _ = _canonical_json(arguments)
        object.__setattr__(self, "arguments", MappingProxyType(arguments))

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "operation": self.operation,
            "owner": self.owner,
            "principal": self.principal,
            "arguments": dict(self.arguments),
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class ErrorEnvelope:
    code: ErrorCode
    message: str
    details: OpaquePayload = field(default_factory=lambda: OpaquePayload.bounded({}))
    schema: int = ERROR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema != ERROR_SCHEMA_VERSION:
            raise ValueError(f"unsupported error schema: {self.schema}")
        if not self.message:
            raise ValueError("error message cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "code": self.code.value,
            "message": self.message,
            "details": self.details.to_dict(),
        }


@dataclass(frozen=True)
class ResponseEnvelope:
    request_id: str
    correlation_id: str
    owner: str
    payload: OpaquePayload | None = None
    error: ErrorEnvelope | None = None
    source_bindings: tuple[SourceBinding, ...] = ()
    receipt_ref: SinnixRef | None = None
    schema: int = PROTOCOL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema != PROTOCOL_SCHEMA_VERSION:
            raise ValueError(f"unsupported response schema: {self.schema}")
        _validate_uuid("request_id", self.request_id)
        _validate_uuid("correlation_id", self.correlation_id)
        if not self.owner:
            raise ValueError("response requires an owner")
        if (self.payload is None) == (self.error is None):
            raise ValueError("response requires exactly one of payload or error")

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": self.schema,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "owner": self.owner,
            "ok": self.ok,
            "source_bindings": [binding.to_dict() for binding in self.source_bindings],
            "receipt_ref": str(self.receipt_ref) if self.receipt_ref else None,
        }
        if self.payload is not None:
            result["payload"] = self.payload.to_dict()
        else:
            result["error"] = self.error.to_dict() if self.error else None
        return result
