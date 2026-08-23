from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from .refs import SinnixRef


class Authority(StrEnum):
    """The authority that decides a fact or effect for an owner."""

    OWNER = "owner"
    SYSTEMD = "systemd"
    GIT = "git"
    TASK_BACKEND = "task_backend"
    EXTERNAL = "external"


class Lifecycle(StrEnum):
    """The effect/lifecycle boundary exposed by an owner."""

    READ_ONLY = "read_only"
    DAEMON_OWNED = "daemon_owned"
    WINDOW_GATED = "window_gated"
    OPERATOR_CONFIRMED = "operator_confirmed"


@dataclass(frozen=True)
class OwnerSpec:
    """One authoritative operation namespace and its supported protocol versions."""

    namespace: str
    owner: str
    authority: Authority
    lifecycle: Lifecycle
    versions: frozenset[int]
    service_ref: SinnixRef | None = None
    source_scoped: bool = False
    documentation: str = ""

    def __post_init__(self) -> None:
        parts = self.namespace.split(".")
        if not parts or any(not part.isidentifier() for part in parts):
            raise ValueError(f"namespace must be dotted identifiers: {self.namespace!r}")
        if not self.owner:
            raise ValueError("owner registration requires an owner")
        if not self.versions or any(version < 1 for version in self.versions):
            raise ValueError("owner registration requires one or more positive protocol versions")
        if self.source_scoped and self.authority is not Authority.OWNER:
            raise ValueError("source-scoped owners must retain their own source authority")

    def supports(self, operation: str, version: int) -> bool:
        return (
            operation == self.namespace or operation.startswith(self.namespace + ".")
        ) and version in self.versions

    def catalog_row(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "owner": self.owner,
            "authority": self.authority.value,
            "lifecycle": self.lifecycle.value,
            "versions": sorted(self.versions),
            "service_ref": str(self.service_ref) if self.service_ref else None,
            "source_scoped": self.source_scoped,
            "documentation": self.documentation,
        }


class OwnerRegistry:
    """Resolve an operation to one authoritative owner without prefix ambiguity."""

    def __init__(self, owners: Iterable[OwnerSpec] = ()) -> None:
        self._owners: dict[str, OwnerSpec] = {}
        for owner in owners:
            self.register(owner)

    def register(self, owner: OwnerSpec) -> None:
        if owner.namespace in self._owners:
            raise ValueError(f"duplicate owner namespace: {owner.namespace}")
        for existing in self._owners.values():
            if owner.namespace.startswith(existing.namespace + ".") or existing.namespace.startswith(owner.namespace + "."):
                raise ValueError(
                    "owner namespaces cannot overlap: "
                    f"{owner.namespace!r} and {existing.namespace!r}"
                )
        self._owners[owner.namespace] = owner

    def resolve(self, operation: str, version: int = 1) -> OwnerSpec:
        matches = [owner for owner in self._owners.values() if owner.supports(operation, version)]
        if not matches:
            raise KeyError(f"no owner supports {operation!r} at protocol version {version}")
        if len(matches) != 1:
            raise ValueError(f"ambiguous owner registration for {operation!r}")
        return matches[0]

    def catalog(self) -> list[dict[str, Any]]:
        return [self._owners[name].catalog_row() for name in sorted(self._owners)]
