from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def source_revision(value: Any) -> str:
    """Return a stable revision for an owner observation.

    The gateway does not assign semantic revisions to owners. When an owner
    gives us no revision, this digest identifies exactly the bounded value we
    observed and is marked as an observation revision in the context output.
    """

    return hashlib.sha256(_canonical(value)).hexdigest()


class ContextSnapshotStore:
    """Persist a bounded set of immutable, principal-scoped context snapshots."""

    def __init__(
        self, state_dir: Path, principal: str, *, max_entries: int = 64
    ) -> None:
        if not principal or max_entries < 1:
            raise ValueError(
                "context snapshot store requires a principal and positive bound"
            )
        self.root = state_dir / "contexts" / principal
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root.chmod(0o700)
        self.max_entries = max_entries

    @staticmethod
    def _snapshot_id(snapshot: Mapping[str, Any]) -> str:
        body = {key: value for key, value in snapshot.items() if key != "snapshot_ref"}
        components = body.get("components")
        if isinstance(components, list):
            body["components"] = [
                {**component, "snapshot_ref": "pending"}
                if isinstance(component, Mapping)
                else component
                for component in components
            ]
        return source_revision(body)

    def put(self, snapshot: Mapping[str, Any]) -> str:
        snapshot_id = self._snapshot_id(snapshot)
        snapshot_ref = f"sinnix://contexts/{snapshot_id}"
        if snapshot.get("snapshot_ref") != snapshot_ref:
            raise ValueError("context snapshot ref does not match its content")
        destination = self.root / f"{snapshot_id}.json"
        if not destination.exists():
            temporary = self.root / f".{snapshot_id}.{uuid.uuid4().hex}.tmp"
            try:
                with temporary.open("x", encoding="utf-8") as handle:
                    json.dump(snapshot, handle, sort_keys=True, separators=(",", ":"))
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.chmod(0o600)
                os.replace(temporary, destination)
                directory_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                temporary.unlink(missing_ok=True)
        os.utime(destination, None)
        retained = sorted(
            self.root.glob("*.json"),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
            reverse=True,
        )
        for stale in retained[self.max_entries :]:
            stale.unlink(missing_ok=True)
        return snapshot_ref

    def get(self, snapshot_id: str) -> dict[str, Any]:
        if len(snapshot_id) != 64 or any(
            char not in "0123456789abcdef" for char in snapshot_id
        ):
            raise KeyError(snapshot_id)
        path = self.root / f"{snapshot_id}.json"
        try:
            snapshot = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise KeyError(snapshot_id) from exc
        if not isinstance(snapshot, dict) or self._snapshot_id(snapshot) != snapshot_id:
            raise KeyError(snapshot_id)
        os.utime(path, None)
        return snapshot


@dataclass(frozen=True)
class ComponentResult:
    name: str
    status: str
    source_revision: str | None = None
    data: Any = None
    reason: str | None = None
    source_ref: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"available", "unavailable"}:
            raise ValueError(f"unknown context component status: {self.status}")
        if self.status == "available" and not isinstance(self.source_revision, str):
            raise ValueError("available context components require a source revision")
        if self.status != "available" and not self.reason:
            raise ValueError("unavailable components require a reason")

    @classmethod
    def available(
        cls,
        name: str,
        data: Any,
        *,
        revision: str | None = None,
        source_ref: str | None = None,
    ) -> "ComponentResult":
        return cls(
            name=name,
            status="available",
            source_revision=revision or source_revision(data),
            data=data,
            source_ref=source_ref,
        )

    @classmethod
    def unavailable(
        cls,
        name: str,
        reason: str,
        *,
        revision: str | None = None,
        source_ref: str | None = None,
    ) -> "ComponentResult":
        return cls(
            name=name,
            status="unavailable",
            source_revision=revision,
            reason=reason,
            source_ref=source_ref,
        )

    def as_dict(self, snapshot_ref: str) -> dict[str, Any]:
        row: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "source_revision": self.source_revision,
            "snapshot_ref": snapshot_ref,
        }
        if self.source_ref is not None:
            row["source_ref"] = self.source_ref
        if self.status == "available":
            row["data"] = self.data
        else:
            row["reason"] = self.reason
        return row


@dataclass(frozen=True)
class ComponentSpec:
    name: str
    budget_bytes: int
    probe: Callable[[], ComponentResult]

    def __post_init__(self) -> None:
        if not self.name or self.budget_bytes < 128:
            raise ValueError(
                "context components require a name and useful positive budget"
            )


@dataclass(frozen=True)
class ContextIntentSpec:
    name: str
    total_budget_bytes: int
    components: tuple[tuple[str, int], ...]


CONTEXT_INTENTS: dict[str, ContextIntentSpec] = {
    "project.orientation": ContextIntentSpec(
        "project.orientation",
        48_000,
        (
            ("project", 12_000),
            ("checkout", 12_000),
            ("tasks", 16_000),
            ("authority", 8_000),
        ),
    ),
    "project.triage": ContextIntentSpec(
        "project.triage",
        56_000,
        (
            ("project", 12_000),
            ("open_beads", 18_000),
            ("stale_claims", 14_000),
            ("changes", 8_000),
        ),
    ),
    "bead.work": ContextIntentSpec(
        "bead.work",
        64_000,
        (
            ("bead", 18_000),
            ("project", 12_000),
            ("checkout", 12_000),
            ("assignment", 14_000),
            ("blockers", 8_000),
        ),
    ),
    "bead.review": ContextIntentSpec(
        "bead.review",
        64_000,
        (
            ("bead", 16_000),
            ("job", 16_000),
            ("checkout", 12_000),
            ("diff", 12_000),
            ("evidence", 8_000),
        ),
    ),
    "job.review": ContextIntentSpec(
        "job.review",
        56_000,
        (("job", 18_000), ("result", 18_000), ("project", 10_000), ("events", 8_000)),
    ),
    "incident": ContextIntentSpec(
        "incident",
        56_000,
        (
            ("runtime", 16_000),
            ("transitions", 14_000),
            ("receipts", 12_000),
            ("jobs", 8_000),
        ),
    ),
}


class RevisionReuseCache:
    """Ephemeral cache whose key always includes the owner source revision."""

    def __init__(self, *, max_entries: int = 256, max_bytes: int = 2_000_000) -> None:
        if max_entries < 1 or max_bytes < 1:
            raise ValueError("context cache bounds must be positive")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._values: OrderedDict[tuple[str, str], tuple[ComponentResult, int]] = (
            OrderedDict()
        )
        self._bytes = 0

    @staticmethod
    def _size(result: ComponentResult) -> int:
        return len(_canonical(result.as_dict("sinnix://context/cache")))

    def get(self, component: str, revision: str) -> ComponentResult | None:
        key = (component, revision)
        value = self._values.get(key)
        if value is None:
            return None
        self._values.move_to_end(key)
        return value[0]

    def put(self, result: ComponentResult) -> ComponentResult:
        if result.status == "available" and result.source_revision is not None:
            key = (result.name, result.source_revision)
            size = self._size(result)
            if size > self.max_bytes:
                return result
            previous = self._values.pop(key, None)
            if previous is not None:
                self._bytes -= previous[1]
            self._values[key] = (result, size)
            self._bytes += size
            while len(self._values) > self.max_entries or self._bytes > self.max_bytes:
                _, (_, evicted_size) = self._values.popitem(last=False)
                self._bytes -= evicted_size
        return result

    def clear_revision(self, component: str, revision: str) -> None:
        value = self._values.pop((component, revision), None)
        if value is not None:
            self._bytes -= value[1]


class ContextComposer:
    """Compose independent owner observations into one bounded context."""

    def __init__(self, *, cache: RevisionReuseCache | None = None) -> None:
        self.cache = cache or RevisionReuseCache()

    @staticmethod
    def _bound_component(result: ComponentResult, budget: int) -> ComponentResult:
        if result.status != "available":
            return result
        encoded = _canonical(result.data)
        if len(encoded) <= budget:
            return result
        return ComponentResult.unavailable(
            result.name,
            f"component exceeded its {budget}-byte context budget",
            revision=result.source_revision,
            source_ref=result.source_ref,
        )

    def compose(
        self,
        intent: str,
        target_ref: str,
        components: list[ComponentSpec],
        *,
        total_budget_bytes: int | None = None,
    ) -> dict[str, Any]:
        try:
            declared = CONTEXT_INTENTS[intent]
        except KeyError as exc:
            raise ValueError(f"unknown context intent: {intent}") from exc
        total_budget = total_budget_bytes or declared.total_budget_bytes
        if total_budget < 512 or total_budget > declared.total_budget_bytes:
            raise ValueError(
                "context total budget is outside the declared intent bound"
            )
        budgets = dict(declared.components)
        expected = set(budgets)
        supplied = {component.name for component in components}
        if not supplied <= expected:
            raise ValueError(
                f"context contains undeclared components: {sorted(supplied - expected)}"
            )
        if len(supplied) != len(components):
            raise ValueError("context contains duplicate components")
        supplied_by_name = {component.name: component for component in components}
        rows: list[ComponentResult] = []
        for name, _budget in declared.components:
            component = supplied_by_name.get(name)
            if component is None:
                rows.append(
                    ComponentResult.unavailable(name, "component plan was not supplied")
                )
                continue
            try:
                result = component.probe()
                if not isinstance(result, ComponentResult):
                    raise TypeError("context component did not return ComponentResult")
            except Exception as exc:  # component isolation is part of the contract
                result = ComponentResult.unavailable(
                    component.name, str(exc) or "owner unavailable"
                )
            if result.status == "available" and result.source_revision is not None:
                cached = self.cache.get(result.name, result.source_revision)
                result = cached if cached is not None else self.cache.put(result)
            rows.append(
                self._bound_component(
                    result, min(component.budget_bytes, budgets[component.name])
                )
            )

        provisional = {
            "schema": "sinnix.gateway-context.v1",
            "intent": intent,
            "target_ref": target_ref,
            "components": [],
            "component_plan": [
                {"name": name, "budget_bytes": budget}
                for name, budget in declared.components
            ],
            "total_budget_bytes": total_budget,
        }
        digest_rows = [row.as_dict("pending") for row in rows]
        digest = source_revision({**provisional, "components": digest_rows})
        snapshot_ref = f"sinnix://contexts/{digest}"
        provisional["snapshot_ref"] = snapshot_ref
        provisional["components"] = [row.as_dict(snapshot_ref) for row in rows]
        encoded = _canonical(provisional)
        if len(encoded) > total_budget:
            # Drop only component payloads. Status, reason, plan, and source
            # revisions remain, so a caller can continue each healthy route.
            for index in sorted(
                range(len(rows)),
                key=lambda item: (
                    len(_canonical(rows[item].data))
                    if rows[item].status == "available"
                    else 0
                ),
                reverse=True,
            ):
                if rows[index].status != "available":
                    continue
                rows[index] = ComponentResult.unavailable(
                    rows[index].name,
                    "context total budget would be exceeded",
                    revision=rows[index].source_revision,
                    source_ref=rows[index].source_ref,
                )
                provisional["components"] = [row.as_dict(snapshot_ref) for row in rows]
                if len(_canonical(provisional)) <= total_budget:
                    break
        if len(_canonical(provisional)) > total_budget:
            raise ValueError("context metadata exceeds its total budget")
        return provisional


def intent_spec(intent: str) -> ContextIntentSpec:
    try:
        return CONTEXT_INTENTS[intent]
    except KeyError as exc:
        raise ValueError(f"unknown context intent: {intent}") from exc
