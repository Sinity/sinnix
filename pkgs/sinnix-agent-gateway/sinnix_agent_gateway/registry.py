from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .contracts import ActionSpec, EffectMode, ResourceSpec, VerbFamily
from sinnix_mcp.refs import RefTemplate, SinnixRef


class RegistryError(ValueError):
    """Raised when executable catalog declarations cannot form one contract."""


@dataclass(frozen=True)
class CatalogSearch:
    text: str | None = None
    domain: str | None = None
    verb: VerbFamily | None = None
    effect: EffectMode | None = None
    resource_kind: str | None = None
    principal: str | None = None


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _templates_overlap(left: RefTemplate, right: RefTemplate) -> bool:
    if len(left.segments) != len(right.segments):
        return False
    for left_segment, right_segment in zip(left.segments, right.segments, strict=True):
        left_variable = left_segment.startswith("{") and left_segment.endswith("}")
        right_variable = right_segment.startswith("{") and right_segment.endswith("}")
        if not left_variable and not right_variable and left_segment != right_segment:
            return False
    return True


class CatalogRegistry:
    """One declaration registry for V2 resource and action contracts."""

    revision = "v2-initial"

    def __init__(
        self,
        resources: Iterable[ResourceSpec],
        actions: Iterable[ActionSpec],
    ) -> None:
        self.resources = tuple(resources)
        self.actions = tuple(actions)
        self._resources_by_kind = {resource.kind: resource for resource in self.resources}
        self._actions_by_name = {action.name: action for action in self.actions}
        self._validate()

    def _validate(self) -> None:
        if len(self._resources_by_kind) != len(self.resources):
            raise RegistryError("resource kinds must be unique")
        if len(self._actions_by_name) != len(self.actions):
            raise RegistryError("action names must be unique")
        for index, resource in enumerate(self.resources):
            for other in self.resources[index + 1 :]:
                if _templates_overlap(resource.ref_template, other.ref_template):
                    raise RegistryError(
                        "resource templates overlap: "
                        f"{resource.ref_template.template} and {other.ref_template.template}"
                    )
        for action in self.actions:
            unknown = set(action.resource_kinds) - set(self._resources_by_kind)
            if unknown:
                raise RegistryError(
                    f"action {action.name!r} refers to unknown resource kinds: {sorted(unknown)}"
                )

    def action(self, name: str) -> ActionSpec:
        try:
            return self._actions_by_name[name]
        except KeyError as error:
            raise RegistryError(f"unknown action: {name!r}") from error

    def action_catalog_hash(self, principal: str | None = None) -> str:
        actions = [
            action.catalog_row()
            for action in self.actions
            if principal is None or principal in action.principals
        ]
        payload = {
            "revision": self.revision,
            "principal": principal,
            "resources": [resource.catalog_row() for resource in self.resources],
            "actions": actions,
        }
        return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()

    def resolve(self, reference: str | SinnixRef) -> tuple[ResourceSpec, dict[str, str]]:
        parsed = SinnixRef.parse(reference) if isinstance(reference, str) else reference
        matches = [
            (resource, values)
            for resource in self.resources
            if (values := resource.ref_template.match(parsed)) is not None
        ]
        if not matches:
            raise RegistryError(f"no resource template matches {parsed}")
        if len(matches) > 1:
            raise RegistryError(f"ambiguous resource reference: {parsed}")
        return matches[0]

    def search(self, search: CatalogSearch = CatalogSearch()) -> dict[str, Any]:
        text = search.text.casefold() if search.text else None
        actions = []
        for action in self.actions:
            row = action.catalog_row()
            searchable = " ".join(
                [
                    action.name,
                    action.domain,
                    action.owner,
                    action.route,
                    action.documentation,
                    *action.resource_kinds,
                ]
            ).casefold()
            if text and text not in searchable:
                continue
            if search.domain and action.domain != search.domain:
                continue
            if search.verb and action.verb is not search.verb:
                continue
            if search.effect and action.effect is not search.effect:
                continue
            if search.resource_kind and search.resource_kind not in action.resource_kinds:
                continue
            if search.principal and search.principal not in action.principals:
                continue
            actions.append(row)
        resources = [
            resource.catalog_row()
            for resource in self.resources
            if not search.resource_kind or resource.kind == search.resource_kind
        ]
        return {
            "revision": self.revision,
            "action_catalog_hash": self.action_catalog_hash(search.principal),
            "principal": search.principal,
            "resources": resources,
            "actions": actions,
        }


EMPTY_OBJECT_SCHEMA: dict[str, Any] = {"type": "object", "additionalProperties": False}
CATALOG_QUERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "text": {"type": "string", "maxLength": 512},
        "domain": {"type": "string", "maxLength": 128},
        "verb": {"enum": [verb.value for verb in VerbFamily]},
        "effect": {"enum": [effect.value for effect in EffectMode]},
        "resource_kind": {"type": "string", "maxLength": 128},
    },
}


def build_registry() -> CatalogRegistry:
    resources = (
        ResourceSpec("project", RefTemplate("project", "sinnix://projects/{project_id}"), "projects", ("summary", "git", "tree"), True),
        ResourceSpec("checkout", RefTemplate("checkout", "sinnix://projects/{project_id}/checkouts/{checkout_id}"), "projects", ("summary", "git", "files"), True),
        ResourceSpec("bead", RefTemplate("bead", "sinnix://projects/{project_id}/beads/{bead_id}"), "beads", ("summary", "history", "graph"), True),
        ResourceSpec("job", RefTemplate("job", "sinnix://jobs/{job_id}"), "jobs", ("summary", "output", "manifest"), True),
        ResourceSpec("artifact", RefTemplate("artifact", "sinnix://artifacts/{artifact_id}"), "artifacts", ("metadata", "content"), True),
        ResourceSpec("receipt", RefTemplate("receipt", "sinnix://receipts/{receipt_id}"), "audit", ("summary",), True),
        ResourceSpec("result", RefTemplate("result", "sinnix://results/{result_id}"), "results", ("metadata", "page"), True),
        ResourceSpec("machine_unit", RefTemplate("machine_unit", "sinnix://machine/units/{manager}/{unit}"), "machine", ("status", "health"), True),
        ResourceSpec("browser_page", RefTemplate("browser_page", "sinnix://browser/pages/{page_id}"), "browser", ("summary", "content"), True),
        ResourceSpec("terminal", RefTemplate("terminal", "sinnix://terminals/{terminal_id}"), "terminals", ("summary", "scrollback"), True),
        ResourceSpec("capture_lane", RefTemplate("capture_lane", "sinnix://captures/{lane}"), "captures", ("summary", "query"), True),
        ResourceSpec("session", RefTemplate("session", "sinnix://sessions/{provider}/{session_id}"), "sessions", ("summary", "messages"), True),
        ResourceSpec("context_snapshot", RefTemplate("context_snapshot", "sinnix://contexts/{snapshot_id}"), "context", ("summary", "sources"), True),
    )
    actions = (
        ActionSpec(
            name="gateway.status",
            verb=VerbFamily.STATUS,
            domain="gateway",
            owner="gateway",
            route="observe.gateway_status",
            effect=EffectMode.READ,
            principals=frozenset({"observer", "agent-control", "operator"}),
            input_schema=EMPTY_OBJECT_SCHEMA,
            output_schema={"type": "object"},
            documentation="Return independent gateway contract and availability observations.",
        ),
        ActionSpec(
            name="gateway.catalog",
            verb=VerbFamily.CATALOG,
            domain="gateway",
            owner="registry",
            route="registry.search",
            effect=EffectMode.READ,
            principals=frozenset({"observer", "agent-control", "operator"}),
            input_schema=CATALOG_QUERY_SCHEMA,
            output_schema={"type": "object"},
            resource_kinds=tuple(resource.kind for resource in resources),
            documentation="Search the generated V2 resource and action catalog.",
        ),
    )
    return CatalogRegistry(resources, actions)


REGISTRY = build_registry()
