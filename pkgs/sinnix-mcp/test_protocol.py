from __future__ import annotations

from uuid import uuid4

import pytest

from sinnix_mcp import (
    Authority,
    ErrorCode,
    ErrorEnvelope,
    Lifecycle,
    OpaquePayload,
    OwnerRegistry,
    OwnerSpec,
    RequestEnvelope,
    ResponseEnvelope,
    SinnixRef,
    SourceBinding,
)


def test_request_digest_is_stable_for_equivalent_arguments() -> None:
    request_id = str(uuid4())
    correlation_id = str(uuid4())
    first = RequestEnvelope(
        request_id=request_id,
        correlation_id=correlation_id,
        operation="lynchpin.materialize.plan",
        owner="lynchpin",
        principal="operator",
        arguments={"b": 2, "a": 1},
    )
    second = RequestEnvelope(
        request_id=request_id,
        correlation_id=correlation_id,
        operation="lynchpin.materialize.plan",
        owner="lynchpin",
        principal="operator",
        arguments={"a": 1, "b": 2},
    )

    assert first.digest == second.digest


def test_payload_requires_bounded_inline_or_complete_opaque_metadata() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        OpaquePayload()
    with pytest.raises(ValueError, match="exceeds"):
        OpaquePayload.bounded({"text": "x" * 64}, limit=16)
    with pytest.raises(ValueError, match="media_type"):
        OpaquePayload(
            ref=SinnixRef.parse("sinnix://artifacts/example"),
            digest="sha256:" + "0" * 64,
            size_bytes=4,
        )


def test_response_preserves_source_generation_and_error_shape() -> None:
    request_id = str(uuid4())
    correlation_id = str(uuid4())
    response = ResponseEnvelope(
        request_id=request_id,
        correlation_id=correlation_id,
        owner="lynchpin",
        error=ErrorEnvelope(ErrorCode.OWNER_UNAVAILABLE, "source unavailable"),
        source_bindings=(
            SourceBinding(
                SinnixRef.parse("sinnix://projects/lynchpin/substrate"),
                "refresh-17",
                "sha256:" + "a" * 64,
            ),
        ),
    )

    assert response.to_dict() == {
        "schema": 1,
        "request_id": request_id,
        "correlation_id": correlation_id,
        "owner": "lynchpin",
        "ok": False,
        "source_bindings": [
            {
                "source_ref": "sinnix://projects/lynchpin/substrate",
                "generation": "refresh-17",
                "root_digest": "sha256:" + "a" * 64,
            }
        ],
        "receipt_ref": None,
        "error": {
            "schema": 1,
            "code": "OWNER_UNAVAILABLE",
            "message": "source unavailable",
            "details": {"kind": "inline", "value": {}},
        },
    }


def test_owner_registry_rejects_overlapping_namespaces_and_wrong_versions() -> None:
    registry = OwnerRegistry(
        [
            OwnerSpec(
                namespace="polylogue.archive",
                owner="polylogue",
                authority=Authority.OWNER,
                lifecycle=Lifecycle.DAEMON_OWNED,
                versions=frozenset({1}),
                source_scoped=True,
            )
        ]
    )

    assert registry.resolve("polylogue.archive.search").owner == "polylogue"
    with pytest.raises(KeyError):
        registry.resolve("polylogue.archive.search", version=2)
    with pytest.raises(ValueError, match="overlap"):
        registry.register(
            OwnerSpec(
                namespace="polylogue",
                owner="other",
                authority=Authority.OWNER,
                lifecycle=Lifecycle.READ_ONLY,
                versions=frozenset({1}),
            )
        )
