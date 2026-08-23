from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .contracts import ActionSpec, EffectMode, ResourceSpec, VerbFamily
from .schemas import V2ToolEnvelope
from sinnix_mcp.refs import RefTemplate, SinnixRef


class RegistryError(ValueError):
    """Raised when executable catalog declarations cannot form one contract."""


CatalogAvailabilityResolver = Callable[[str, str], tuple[str, str | None]]


@dataclass(frozen=True)
class CatalogSearch:
    text: str | None = None
    domain: str | None = None
    verb: VerbFamily | None = None
    effect: EffectMode | None = None
    resource_kind: str | None = None
    project: str | None = None
    availability: str | None = None
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

    def resource(self, kind: str) -> ResourceSpec:
        try:
            return self._resources_by_kind[kind]
        except KeyError as error:
            raise RegistryError(f"unknown resource kind: {kind!r}") from error

    def reference(self, kind: str, values: dict[str, str]) -> str:
        return str(self.resource(kind).ref_template.format(values))

    def action_schema(self, name: str, principal: str | None = None) -> dict[str, Any]:
        action = self.action(name)
        if principal is not None and principal not in action.principals:
            raise RegistryError(f"principal {principal!r} cannot read action {name!r}")
        return {
            "revision": self.revision,
            "action": action.catalog_row(),
        }

    def resource_contract(self, kind: str, principal: str | None = None) -> dict[str, Any]:
        resource = self.resource(kind)
        if principal is not None and principal not in resource.principals:
            raise RegistryError(f"principal {principal!r} cannot read resource {kind!r}")
        return {
            "revision": self.revision,
            "resource": resource.catalog_row(),
        }

    def documentation_rows(self, principal: str | None = None) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "resources": self._resource_rows(principal=principal),
            "actions": self._action_rows(principal=principal),
        }

    def _resource_rows(
        self,
        *,
        principal: str | None = None,
        resource_kind: str | None = None,
        availability: str | None = None,
        text: str | None = None,
        project: str | None = None,
        availability_resolver: CatalogAvailabilityResolver | None = None,
    ) -> list[dict[str, Any]]:
        rows = []
        for resource in self.resources:
            if principal is not None and principal not in resource.principals:
                continue
            if resource_kind is not None and resource.kind != resource_kind:
                continue
            if project is not None and "project_id" not in resource.ref_template.variables:
                continue
            row = resource.catalog_row()
            searchable = " ".join(
                [
                    resource.kind,
                    resource.owner,
                    resource.ref_template.template,
                    *resource.readable_projections,
                ]
            ).casefold()
            if text is not None and text not in searchable:
                continue
            if availability_resolver is not None:
                state, reason = availability_resolver("resource", resource.kind)
                row["availability"] = state
                if reason is not None:
                    row["availability_reason"] = reason
            if availability is not None and row["availability"] != availability:
                continue
            rows.append(row)
        return rows

    def _action_rows(self, *, principal: str | None = None) -> list[dict[str, Any]]:
        return [
            action.catalog_row()
            for action in self.actions
            if principal is None or principal in action.principals
        ]

    def action_catalog_hash(self, principal: str | None = None) -> str:
        payload = {
            "revision": self.revision,
            "principal": principal,
            "resources": self._resource_rows(principal=principal),
            "actions": self._action_rows(principal=principal),
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

    def search(
        self,
        search: CatalogSearch = CatalogSearch(),
        *,
        availability_resolver: CatalogAvailabilityResolver | None = None,
    ) -> dict[str, Any]:
        text = search.text.casefold() if search.text else None
        actions = []
        for action in self.actions:
            if search.principal and search.principal not in action.principals:
                continue
            row = action.catalog_row()
            if availability_resolver is not None:
                state, reason = availability_resolver("action", action.name)
                row["availability"] = state
                if reason is not None:
                    row["availability_reason"] = reason
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
            if search.project and not any(
                "project_id" in self.resource(kind).ref_template.variables
                for kind in action.resource_kinds
            ):
                continue
            if search.availability and row["availability"] != search.availability:
                continue
            actions.append(row)
        resources = self._resource_rows(
            principal=search.principal,
            resource_kind=search.resource_kind,
            availability=search.availability,
            text=text,
            project=search.project,
            availability_resolver=availability_resolver,
        )
        return {
            "revision": self.revision,
            "action_catalog_hash": self.action_catalog_hash(search.principal),
            "principal": search.principal,
            "project": search.project,
            "resources": resources,
            "actions": actions,
        }


REQUEST_CONTROL_PROPERTIES: dict[str, Any] = {
    "request_id": {"type": "string", "minLength": 1, "maxLength": 128},
    "actor": {"type": "string", "minLength": 1, "maxLength": 256},
    "reason": {"type": "string", "minLength": 1, "maxLength": 2_000},
    "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 256},
    "deadline_at": {"type": "number"},
    "preconditions": {"type": "object"},
}


def _with_request_controls(schema: Mapping[str, Any]) -> dict[str, Any]:
    if schema.get("type") != "object":
        raise RegistryError("V2 request schemas must be objects")
    return {
        **dict(schema),
        "properties": {
            **dict(schema.get("properties", {})),
            **REQUEST_CONTROL_PROPERTIES,
        },
    }


EMPTY_OBJECT_SCHEMA: dict[str, Any] = _with_request_controls(
    {"type": "object", "additionalProperties": False}
)
V2_ENVELOPE_SCHEMA: dict[str, Any] = V2ToolEnvelope.model_json_schema()
RESOURCE_GET_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref"],
        "properties": {
            "ref": {"type": "string", "minLength": 1, "maxLength": 2_048},
        },
    }
)

JOB_WAIT_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref"],
        "properties": {
            "ref": {
                "type": "string",
                "minLength": 1,
                "maxLength": 2_048,
                "pattern": "^sinnix://jobs/[^/]+$",
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 1,
                "maximum": 300,
                "default": 30,
            },
        },
    }
)

SHELL_RUN_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["project_id", "checkout_id", "argv", "idempotency_key"],
        "properties": {
            "project_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "checkout_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "argv": {
                "type": "array",
                "minItems": 1,
                "maxItems": 128,
                "items": {"type": "string", "minLength": 1, "maxLength": 32_768},
            },
            "cwd": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4_096,
                "default": ".",
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 1,
                "maximum": 3_600,
                "default": 3_600,
            },
        },
    }
)

CATALOG_QUERY_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string", "maxLength": 512},
            "domain": {"type": "string", "maxLength": 128},
            "verb": {"enum": [verb.value for verb in VerbFamily]},
            "effect": {"enum": [effect.value for effect in EffectMode]},
            "resource_kind": {"type": "string", "maxLength": 128},
            "project": {"type": "string", "minLength": 1, "maxLength": 128},
            "availability": {"enum": ["available", "unavailable"]},
        },
    }
)


def build_registry() -> CatalogRegistry:
    resources = (
        ResourceSpec("project", RefTemplate("project", "sinnix://projects/{project_id}"), "projects", ("summary", "git", "tree"), True),
        ResourceSpec("checkout", RefTemplate("checkout", "sinnix://projects/{project_id}/checkouts/{checkout_id}"), "projects", ("summary", "git", "files"), True),
        ResourceSpec("bead", RefTemplate("bead", "sinnix://projects/{project_id}/beads/{bead_id}"), "beads", ("summary", "history", "graph"), True),
        ResourceSpec("task_authority", RefTemplate("task_authority", "sinnix://projects/{project_id}/task-authority"), "beads", ("status",), False),
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
            output_schema=V2_ENVELOPE_SCHEMA,
            examples=({"input": {}},),
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
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=tuple(resource.kind for resource in resources),
            examples=(
                {
                    "input": {
                        "resource_kind": "bead",
                        "availability": "available",
                    }
                },
            ),
            documentation="Search the generated V2 resource and action catalog.",
        ),
        ActionSpec(
            name="resources.get",
            verb=VerbFamily.GET,
            domain="resources",
            owner="resolver",
            route="resources.get",
            effect=EffectMode.READ,
            principals=frozenset({"observer", "agent-control", "operator"}),
            input_schema=RESOURCE_GET_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "checkout", "bead", "task_authority"),
            examples=({"input": {"ref": "sinnix://projects/sinnix"}},),
            documentation="Resolve one canonical project, checkout, Beads task, or task-authority reference.",
        ),
        ActionSpec(
            name="jobs.wait",
            verb=VerbFamily.WAIT,
            domain="jobs",
            owner="systemd-jobs",
            route="job.wait",
            effect=EffectMode.READ,
            principals=frozenset({"observer", "agent-control", "operator"}),
            input_schema=JOB_WAIT_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("job",),
            examples=(
                {
                    "input": {
                        "ref": "sinnix://jobs/3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c",
                        "timeout_seconds": 30,
                    }
                },
            ),
            documentation="Wait for a bounded interval on one daemon-owned job reference.",
        ),
        ActionSpec(
            name="shell.run",
            verb=VerbFamily.RUN,
            domain="shell",
            owner="systemd-jobs",
            route="job.shell.start",
            effect=EffectMode.RUN,
            principals=frozenset({"operator"}),
            input_schema=SHELL_RUN_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "checkout", "job"),
            supports_idempotency=True,
            receipt_policy="audit",
            examples=(
                {
                    "input": {
                        "project_id": "sinnix",
                        "checkout_id": "default",
                        "argv": ["git", "status", "--short"],
                        "cwd": ".",
                        "timeout_seconds": 300,
                        "idempotency_key": "shell-status-example",
                    }
                },
            ),
            documentation="Start one typed operator-shell job and return its daemon-owned handle.",
        ),
    )
    return CatalogRegistry(resources, actions)


REGISTRY = build_registry()
