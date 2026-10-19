from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping

from .refs import RefTemplate
from .schemas import ERROR_CODES

# The gateway has one caller. Persisted rows, result envelopes and cursor keys
# still carry its name, so stored data and live cursors stay valid.
PRINCIPAL = "operator"

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


KNOWN_TYPED_FAILURES = ERROR_CODES


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
