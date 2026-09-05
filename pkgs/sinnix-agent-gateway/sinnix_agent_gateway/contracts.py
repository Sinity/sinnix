from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping
from urllib.parse import quote

from sinnix_mcp.refs import RefTemplate

KNOWN_PRINCIPALS = frozenset({"observer", "agent-control", "operator"})

JsonSchema = Mapping[str, Any]
AvailabilityProbe = Callable[[], Mapping[str, Any]]


class VerbFamily(StrEnum):
    STATUS = "status"
    CATALOG = "catalog"
    QUERY = "query"
    GET = "get"
    CONTEXT = "context"
    EVENTS = "events"
    WAIT = "wait"
    CHANGE = "change"
    OPERATE = "operate"
    RUN = "run"


class EffectMode(StrEnum):
    READ = "read"
    CHANGE = "change"
    OPERATE = "operate"
    RUN = "run"


class StorageEffect(StrEnum):
    """Gateway-owned persistence that can accompany a protocol action."""

    AUDIT_APPEND = "audit_append"
    RESULT_SNAPSHOT = "result_snapshot"


OBSERVABILITY_PERSISTENCE = frozenset(
    {StorageEffect.AUDIT_APPEND, StorageEffect.RESULT_SNAPSHOT}
)

BASE_TYPED_FAILURES = frozenset(
    {
        "invalid_request",
        "not_found",
        "unavailable",
        "response_bound",
        "owner_failed",
        "policy_denied",
    }
)
KNOWN_TYPED_FAILURES = BASE_TYPED_FAILURES | {
    "precondition_failed",
    "idempotency_conflict",
    "stale_cursor",
    "source_changed",
    "conflict",
    "partial_completion",
    "deadline",
    "unsupported_capability",
}


@dataclass(frozen=True)
class ResourceSpec:
    """The one executable declaration for a canonical resource kind."""

    kind: str
    ref_template: RefTemplate
    owner: str
    readable_projections: tuple[str, ...] = ()
    supports_query: bool = False
    availability_probe: AvailabilityProbe | None = field(default=None, compare=False)
    principals: frozenset[str] = KNOWN_PRINCIPALS

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("resource kind cannot be empty")
        if self.ref_template.kind != self.kind:
            raise ValueError(
                f"resource {self.kind!r} must use a template with the same kind "
                f"(got {self.ref_template.kind!r})"
            )
        if not self.owner:
            raise ValueError(f"resource {self.kind!r} requires an owner")
        if not self.principals:
            raise ValueError(f"resource {self.kind!r} requires at least one principal")
        unknown_principals = self.principals - KNOWN_PRINCIPALS
        if unknown_principals:
            raise ValueError(
                f"resource {self.kind!r} names unknown principals: {sorted(unknown_principals)}"
            )

    @property
    def contract_ref(self) -> str:
        return f"sinnix://gateway/v2/resources/{quote(self.kind, safe='')}"
