from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping

from sinnix_mcp.refs import RefTemplate

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


@dataclass(frozen=True)
class ResourceSpec:
    """The one executable declaration for a canonical resource kind."""

    kind: str
    ref_template: RefTemplate
    owner: str
    readable_projections: tuple[str, ...] = ()
    supports_query: bool = False
    availability_probe: AvailabilityProbe | None = field(default=None, compare=False)

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

    def catalog_row(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ref_template": self.ref_template.template,
            "owner": self.owner,
            "readable_projections": list(self.readable_projections),
            "supports_query": self.supports_query,
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
    receipt_policy: str = "none"
    examples: tuple[Mapping[str, Any], ...] = ()
    documentation: str = ""

    def __post_init__(self) -> None:
        if not self.name or "." not in self.name:
            raise ValueError("action name must be a dotted canonical name")
        if not self.domain or not self.owner or not self.route:
            raise ValueError(f"action {self.name!r} requires domain, owner, and route")
        if not self.principals:
            raise ValueError(f"action {self.name!r} requires at least one principal")
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

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "verb": self.verb.value,
            "domain": self.domain,
            "owner": self.owner,
            "route": self.route,
            "effect": self.effect.value,
            "principals": sorted(self.principals),
            "resource_kinds": list(self.resource_kinds),
            "supports_idempotency": self.supports_idempotency,
            "supports_precondition": self.supports_precondition,
            "execution_profile": self.execution_profile,
            "receipt_policy": self.receipt_policy,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "examples": [dict(example) for example in self.examples],
            "documentation": self.documentation,
        }
