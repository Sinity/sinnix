from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


StableErrorCode = Literal[
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
]


class V2Error(GatewayModel):
    code: StableErrorCode
    message: str = Field(min_length=1, max_length=2_000)
    diagnostic_refs: list[str] = Field(default_factory=list, max_length=32)
    details: dict[str, Any] = Field(default_factory=dict)


class V2Result(GatewayModel):
    result_id: str = Field(min_length=1, max_length=128)
    ref: str = Field(min_length=1, max_length=2_048)
    action: str = Field(min_length=1, max_length=256)
    principal: str = Field(min_length=1, max_length=64)
    owner: str = Field(min_length=1, max_length=256)
    route: str = Field(min_length=1, max_length=512)
    outcome: Literal["ok", "error"]
    observed_at: float
    request_id: str = Field(min_length=1, max_length=128)
    request_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)
    sha256: str = Field(pattern="^[0-9a-f]{64}$")


class V2Receipt(GatewayModel):
    receipt_id: str = Field(min_length=1, max_length=128)
    ref: str = Field(min_length=1, max_length=2_048)
    sequence: int = Field(ge=1)
    entry_hash: str = Field(pattern="^[0-9a-f]{64}$")


class V2Page(GatewayModel):
    kind: Literal["cursor", "offset", "snapshot"]
    cursor: str | int | None = None
    next_cursor: str | int | None = None
    offset: int | None = Field(default=None, ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    expires_at: float | None = None
    snapshot_ref: str | None = Field(default=None, min_length=1, max_length=2_048)


class V2Meta(GatewayModel):
    source: dict[str, Any]
    source_revisions: dict[str, str] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    resource_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=256)


class V2ToolEnvelope(GatewayModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    protocol_schema: Literal["sinnix.gateway-result.v3"] = Field(alias="schema")
    result: V2Result
    receipt: V2Receipt
    page: V2Page | None = None
    data: Any | None = None
    error: V2Error | None = None
    meta: V2Meta

    @model_validator(mode="after")
    def validate_outcome(self) -> "V2ToolEnvelope":
        if self.result.outcome == "ok" and self.error is not None:
            raise ValueError("successful V2 responses cannot carry an error")
        if self.result.outcome == "error" and self.error is None:
            raise ValueError("failed V2 responses require a structured error")
        return self


class V2ManifestEnvelope(GatewayModel):
    """Compact top-level MCP schema; full action schemas stay lazy in the catalog."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    protocol_schema: Literal["sinnix.gateway-result.v3"] = Field(alias="schema")
    result: dict[str, Any]
    receipt: dict[str, Any]
    meta: dict[str, Any]
    page: dict[str, Any] | None = None
    data: Any | None = None
    error: dict[str, Any] | None = None


JsonObject = dict[str, Any]
