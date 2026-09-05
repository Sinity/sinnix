"""One declaration per gateway action.

An ``Action`` binds a name, a verb family, an ``Input`` model, an ``Output``
model and a handler. The MCP tool, its input and output JSON schemas, the
catalog row, the CLI subcommand, the generated documentation and the fixtures
are all derived from this one object, so a schema seen in ``tools/list`` is
the schema the handler validates against.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import quote

from mcp.types import ContentBlock, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, create_model

from .contracts import (
    KNOWN_PRINCIPALS,
    KNOWN_TYPED_FAILURES,
    OBSERVABILITY_PERSISTENCE,
    EffectMode,
    StorageEffect,
    VerbFamily,
)
from .schemas import GatewayModel, V2ToolEnvelope

ALL_PRINCIPALS = KNOWN_PRINCIPALS
OBSERVER_OPERATOR = frozenset({"observer", "operator"})
OPERATOR_ONLY = frozenset({"operator"})
CONTROL_OPERATOR = frozenset({"agent-control", "operator"})

READ_FAMILIES = frozenset(
    {
        VerbFamily.STATUS,
        VerbFamily.CATALOG,
        VerbFamily.QUERY,
        VerbFamily.GET,
        VerbFamily.CONTEXT,
        VerbFamily.EVENTS,
        VerbFamily.WAIT,
    }
)

FAMILY_EFFECT: dict[VerbFamily, EffectMode] = {
    **{family: EffectMode.READ for family in READ_FAMILIES},
    VerbFamily.CHANGE: EffectMode.CHANGE,
    VerbFamily.OPERATE: EffectMode.OPERATE,
    VerbFamily.RUN: EffectMode.RUN,
}

_READ_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
_MUTATION_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
)
_RUN_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True
)

FAMILY_ANNOTATIONS: dict[VerbFamily, ToolAnnotations] = {
    **{family: _READ_ANNOTATIONS for family in READ_FAMILIES},
    VerbFamily.CHANGE: _MUTATION_ANNOTATIONS,
    VerbFamily.OPERATE: _MUTATION_ANNOTATIONS,
    VerbFamily.RUN: _RUN_ANNOTATIONS,
}


class RequestControls(GatewayModel):
    """Caller attribution shared by every action; read actions ignore the rest."""

    request_id: str | None = Field(
        default=None, max_length=128, description="Caller-chosen correlation id."
    )
    actor: str | None = Field(default=None, min_length=1, max_length=256)
    reason: str | None = Field(default=None, min_length=1, max_length=2_000)
    deadline_at: float | None = Field(
        default=None, description="Unix timestamp after which the call is refused."
    )


class MutationControls(RequestControls):
    """Effectful actions carry an idempotency key and optional preconditions."""

    idempotency_key: str = Field(
        min_length=1,
        max_length=256,
        description="Replaying the same key with the same request returns the stored response.",
    )
    preconditions: dict[str, Any] | None = Field(
        default=None,
        description="Owner-checked preconditions; a mismatch fails with precondition_failed.",
    )


class Example(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    input: dict[str, Any]


class TruncatedData(GatewayModel):
    """A response whose data exceeded the bound and was retained as an artifact."""

    truncated: Literal[True]
    artifact: dict[str, Any]


class ActionResult:
    """A handler's result with optional MCP content blocks (images, resources)."""

    __slots__ = ("data", "blocks", "page")

    def __init__(
        self,
        data: Any,
        *,
        blocks: Iterable[ContentBlock] = (),
        page: dict[str, Any] | None = None,
    ) -> None:
        self.data = data
        self.blocks = list(blocks)
        self.page = page


Handler = Callable[..., Any | Awaitable[Any]]


@dataclass(frozen=True)
class Action:
    name: str
    family: VerbFamily
    owner: str
    summary: str
    Input: type[RequestControls]
    Output: type[BaseModel]
    handler: Handler = field(compare=False)
    principals: frozenset[str] = ALL_PRINCIPALS
    domain: str = ""
    resource_kinds: tuple[str, ...] = ()
    affordances: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    examples: tuple[Example, ...] = ()
    documentation: str = ""
    supports_precondition: bool = False
    execution_profile: str | None = None
    receipt_policy: str = "audit"
    storage_effects: frozenset[StorageEffect] = OBSERVABILITY_PERSISTENCE
    failure_codes: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if "." not in self.name:
            raise ValueError("action name must be a dotted canonical name")
        if not self.owner or not self.summary:
            raise ValueError(f"action {self.name!r} requires an owner and summary")
        if not self.principals or not self.principals <= KNOWN_PRINCIPALS:
            raise ValueError(f"action {self.name!r} names unknown principals")
        if not self.domain:
            object.__setattr__(self, "domain", self.name.split(".", 1)[0])
        if not issubclass(self.Input, RequestControls):
            raise ValueError(f"action {self.name!r} Input must extend RequestControls")
        mutating = issubclass(self.Input, MutationControls)
        if self.effect is EffectMode.READ and mutating:
            raise ValueError(f"read action {self.name!r} carries mutation controls")
        if self.effect is not EffectMode.READ and not mutating:
            raise ValueError(f"mutating action {self.name!r} needs MutationControls")
        if len(set(self.resource_kinds)) != len(self.resource_kinds):
            raise ValueError(f"action {self.name!r} repeats resource kinds")
        if self.receipt_policy not in {"none", "audit", "owner"}:
            raise ValueError(f"action {self.name!r} has unknown receipt policy")
        if (
            self.failure_codes is not None
            and not self.failure_codes <= KNOWN_TYPED_FAILURES
        ):
            raise ValueError(f"action {self.name!r} has unknown typed failures")
        for example in self.examples:
            self.Input.model_validate(example.input)

    # -- ActionSpec-compatible surface consumed by the runtime kernel -------

    @property
    def verb(self) -> VerbFamily:
        return self.family

    @property
    def effect(self) -> EffectMode:
        return FAMILY_EFFECT[self.family]

    @property
    def route(self) -> str:
        return self.name

    @property
    def supports_idempotency(self) -> bool:
        return self.effect is not EffectMode.READ

    @property
    def typed_failures(self) -> frozenset[str]:
        return (
            (self.failure_codes or KNOWN_TYPED_FAILURES)
            | ({"precondition_failed"} if self.supports_precondition else set())
            | ({"idempotency_conflict"} if self.supports_idempotency else set())
        )

    @property
    def schema_ref(self) -> str:
        return f"sinnix://gateway/v2/actions/{quote(self.name, safe='.')}"

    @property
    def annotations(self) -> ToolAnnotations:
        return FAMILY_ANNOTATIONS[self.family]

    @property
    def is_async(self) -> bool:
        return inspect.iscoroutinefunction(self.handler)

    def input_schema(self) -> dict[str, Any]:
        return self.Input.model_json_schema(by_alias=True)

    def envelope_model(self) -> type[V2ToolEnvelope]:
        """The typed response envelope: ``data`` is this action's Output."""
        return create_model(
            f"{self.Output.__name__}Envelope",
            __base__=V2ToolEnvelope,
            data=(self.Output | TruncatedData | None, None),
        )

    def output_schema(self) -> dict[str, Any]:
        return self.envelope_model().model_json_schema(by_alias=True)

    def catalog_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "schema_ref": self.schema_ref,
            "verb": self.family.value,
            "domain": self.domain,
            "owner": self.owner,
            "route": self.route,
            "availability": "declared",
            "effect": self.effect.value,
            "principals": sorted(self.principals),
            "resource_kinds": list(self.resource_kinds),
            "affordances": list(self.affordances),
            "aliases": list(self.aliases),
            "supports_idempotency": self.supports_idempotency,
            "supports_precondition": self.supports_precondition,
            "execution_profile": self.execution_profile,
            "receipt_policy": self.receipt_policy,
            "storage_effects": sorted(effect.value for effect in self.storage_effects),
            "typed_failures": sorted(self.typed_failures),
            "input_schema": self.input_schema(),
            "output_schema": self.output_schema(),
            "examples": [example.model_dump() for example in self.examples],
            "documentation": self.documentation or self.summary,
        }


def validate_actions(
    actions: Iterable[Action], *, also_known: Iterable[str] = ()
) -> tuple[Action, ...]:
    """Import-time invariants over the whole action set."""
    ordered = tuple(actions)
    names = [action.name for action in ordered]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate action names: {duplicates}")
    known = set(names) | set(also_known)
    for action in ordered:
        unknown = sorted(set(action.affordances) - known)
        if unknown:
            raise ValueError(
                f"action {action.name!r} affordances name unknown actions: {unknown}"
            )
    return ordered
