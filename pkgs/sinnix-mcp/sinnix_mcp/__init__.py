"""Shared protocol primitives for Sinnix MCP and local runtime frontends."""

from .owners import Authority, Lifecycle, OwnerRegistry, OwnerSpec
from .protocol import (
    ERROR_SCHEMA_VERSION,
    PROTOCOL_SCHEMA_VERSION,
    ErrorCode,
    ErrorEnvelope,
    OpaquePayload,
    RequestEnvelope,
    ResponseEnvelope,
    SourceBinding,
)
from .refs import RefTemplate, ReferenceError, SinnixRef

__all__ = [
    "Authority",
    "ERROR_SCHEMA_VERSION",
    "ErrorCode",
    "ErrorEnvelope",
    "Lifecycle",
    "OpaquePayload",
    "OwnerRegistry",
    "OwnerSpec",
    "PROTOCOL_SCHEMA_VERSION",
    "RefTemplate",
    "ReferenceError",
    "RequestEnvelope",
    "ResponseEnvelope",
    "SinnixRef",
    "SourceBinding",
]
