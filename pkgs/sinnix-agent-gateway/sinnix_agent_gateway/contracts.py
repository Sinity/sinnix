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

    def catalog_row(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "contract_ref": self.contract_ref,
            "ref_template": self.ref_template.template,
            "owner": self.owner,
            "principals": sorted(self.principals),
            "readable_projections": list(self.readable_projections),
            "supports_query": self.supports_query,
            "availability": "declared",
        }


@dataclass(frozen=True)
class ActionSpec:
    """The one executable declaration for a public gateway action.

    The initial registry intentionally declares only actions backed by the V2
    substrate. Legacy MCP tools are migrated one owner at a time and must not
    be copied into a second manual inventory.
    """

    name: str
    verb: VerbFamily
    domain: str
    owner: str
    route: str
    effect: EffectMode
    principals: frozenset[str]
    input_schema: JsonSchema
    output_schema: JsonSchema
    resource_kinds: tuple[str, ...] = ()
    supports_idempotency: bool = False
    supports_precondition: bool = False
    execution_profile: str | None = None
    receipt_policy: str = "audit"
    storage_effects: frozenset[StorageEffect] = OBSERVABILITY_PERSISTENCE
    failure_codes: frozenset[str] | None = None
    examples: tuple[Mapping[str, Any], ...] = ()
    documentation: str = ""

    def __post_init__(self) -> None:
        if not self.name or "." not in self.name:
            raise ValueError("action name must be a dotted canonical name")
        if not self.domain or not self.owner or not self.route:
            raise ValueError(f"action {self.name!r} requires domain, owner, and route")
        if not self.principals:
            raise ValueError(f"action {self.name!r} requires at least one principal")
        unknown_principals = self.principals - KNOWN_PRINCIPALS
        if unknown_principals:
            raise ValueError(
                f"action {self.name!r} names unknown principals: {sorted(unknown_principals)}"
            )
        if not isinstance(self.input_schema, Mapping) or not self.input_schema.get("type"):
            raise ValueError(f"action {self.name!r} requires an input JSON Schema")
        if not isinstance(self.output_schema, Mapping) or not self.output_schema.get("type"):
            raise ValueError(f"action {self.name!r} requires an output JSON Schema")
        if len(set(self.resource_kinds)) != len(self.resource_kinds):
            raise ValueError(f"action {self.name!r} repeats resource kinds")
        for example in self.examples:
            if not isinstance(example, Mapping) or not isinstance(
                example.get("input"), Mapping
            ):
                raise ValueError(
                    f"action {self.name!r} examples require an input object"
                )
        if self.effect is EffectMode.READ and self.verb not in {
            VerbFamily.STATUS,
            VerbFamily.CATALOG,
            VerbFamily.QUERY,
            VerbFamily.GET,
            VerbFamily.CONTEXT,
            VerbFamily.EVENTS,
            VerbFamily.WAIT,
        }:
            raise ValueError(f"read action {self.name!r} uses a mutating verb")
        if self.effect is not EffectMode.READ and self.verb in {
            VerbFamily.STATUS,
            VerbFamily.CATALOG,
            VerbFamily.QUERY,
            VerbFamily.GET,
            VerbFamily.CONTEXT,
            VerbFamily.EVENTS,
            VerbFamily.WAIT,
        }:
            raise ValueError(f"mutating action {self.name!r} uses a read verb")
        if self.receipt_policy not in {"none", "audit", "owner"}:
            raise ValueError(f"action {self.name!r} has unknown receipt policy")
        if not self.storage_effects <= frozenset(StorageEffect):
            raise ValueError(f"action {self.name!r} has unknown storage effects")
        if self.failure_codes is not None and not self.failure_codes <= KNOWN_TYPED_FAILURES:
            raise ValueError(f"action {self.name!r} has unknown typed failures")
        if self.receipt_policy == "audit" and StorageEffect.AUDIT_APPEND not in self.storage_effects:
            raise ValueError(f"action {self.name!r} audit receipts require audit persistence")

    @property
    def typed_failures(self) -> frozenset[str]:
        return (self.failure_codes or KNOWN_TYPED_FAILURES) | (
            {"precondition_failed"} if self.supports_precondition else set()
        ) | ({"idempotency_conflict"} if self.supports_idempotency else set())

    @property
    def schema_ref(self) -> str:
        return f"sinnix://gateway/v2/actions/{quote(self.name, safe='.')}"

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "schema_ref": self.schema_ref,
            "verb": self.verb.value,
            "domain": self.domain,
            "owner": self.owner,
            "route": self.route,
            "availability": "declared",
            "effect": self.effect.value,
            "principals": sorted(self.principals),
            "resource_kinds": list(self.resource_kinds),
            "supports_idempotency": self.supports_idempotency,
            "supports_precondition": self.supports_precondition,
            "execution_profile": self.execution_profile,
            "receipt_policy": self.receipt_policy,
            "storage_effects": sorted(effect.value for effect in self.storage_effects),
            "typed_failures": sorted(self.typed_failures),
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "examples": [dict(example) for example in self.examples],
            "documentation": self.documentation,
        }
