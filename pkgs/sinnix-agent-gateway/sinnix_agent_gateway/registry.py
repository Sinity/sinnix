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

    revision = "v2-operator-verbs"

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
            **REQUEST_CONTROL_PROPERTIES,
            **dict(schema.get("properties", {})),
        },
    }


EMPTY_OBJECT_SCHEMA: dict[str, Any] = _with_request_controls(
    {"type": "object", "additionalProperties": False}
)
V2_ENVELOPE_SCHEMA: dict[str, Any] = V2ToolEnvelope.model_json_schema()
MACHINE_OPERATIONS = (
    "focus",
    "interrupt",
    "freeze",
    "thaw",
    "reset_policy",
    "set_policy",
    "park",
    "rebuild_override",
    "restart",
    "start",
    "stop",
)
RESOURCE_GET_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref"],
        "properties": {
            "ref": {"type": "string", "minLength": 1, "maxLength": 2_048},
            "projection": {
                "enum": ["summary", "log", "result"],
                "default": "summary",
            },
            "offset": {"type": "integer", "minimum": 0, "default": 0},
            "max_bytes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 262_144,
                "default": 64_000,
            },
            "includes": {"type": "array", "maxItems": 8, "items": {"enum": ["blockers", "comments", "history", "events", "dependencies", "dependents", "children", "refs"]}},
            "as_of": {"type": "string", "minLength": 1, "maxLength": 128},
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

AGENT_RUN_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "project_id",
            "prompt",
            "backend",
            "model",
            "reasoning_effort",
            "idempotency_key",
        ],
        "properties": {
            "project_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "checkout_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "prompt": {"type": "string", "minLength": 1, "maxLength": 200_000},
            "backend": {"enum": ["claude", "codex", "gemini", "grok", "antigravity"]},
            "model": {"type": "string", "minLength": 1, "maxLength": 256},
            "reasoning_effort": {"type": "string", "minLength": 1, "maxLength": 32},
            "timeout_seconds": {
                "type": "integer",
                "minimum": 30,
                "maximum": 86_400,
                "default": 14_400,
            },
            "credential_profile": {
                "enum": ["subscription", "api"],
                "default": "subscription",
            },
        },
    }
)

JOB_CANCEL_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref", "idempotency_key", "preconditions"],
        "properties": {
            "ref": {
                "type": "string",
                "minLength": 1,
                "maxLength": 2_048,
                "pattern": "^sinnix://jobs/[^/]+$",
            },
            "preconditions": {
                "type": "object",
                "additionalProperties": False,
                "required": ["expected_phase"],
                "properties": {
                    "expected_phase": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 128,
                    },
                },
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

PROJECT_QUERY_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref", "query"],
        "properties": {
            "ref": {
                "type": "string",
                "minLength": 1,
                "maxLength": 2_048,
                "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
            },
            "query": {"type": "string", "minLength": 1, "maxLength": 1_000},
            "max_matches": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1_000,
                "default": 200,
            },
        },
    }
)

PROJECT_CONTEXT_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref"],
        "properties": {
            "ref": {
                "type": "string",
                "minLength": 1,
                "maxLength": 2_048,
                "pattern": "^sinnix://projects/[^/]+$",
            },
        },
    }
)

PROJECT_CHANGE_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref", "operation", "idempotency_key", "preconditions"],
        "properties": {
            "ref": {
                "type": "string",
                "minLength": 1,
                "maxLength": 2_048,
                "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
            },
            "operation": {"enum": ["write", "apply_patch"]},
            "path": {"type": "string", "minLength": 1, "maxLength": 4_096},
            "content": {"type": "string", "maxLength": 262_144},
            "patch": {"type": "string", "minLength": 1, "maxLength": 262_144},
            "preconditions": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": False,
                "properties": {
                    "head": {"type": "string", "pattern": "^[0-9a-f]{40,64}$"},
                    "dirty_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
            },
        },
    }
)


def _owner_change_schema(
    *,
    ref_pattern: str,
    operations: tuple[str, ...],
    precondition_properties: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "ref": {
            "type": "string",
            "minLength": 1,
            "maxLength": 8_192,
            "pattern": ref_pattern,
        },
        "operation": {"enum": list(operations)},
        "parameters": {
            "type": "object",
            "maxProperties": 32,
        },
    }
    if precondition_properties is not None:
        properties["preconditions"] = {
            "type": "object",
            "additionalProperties": False,
            "properties": dict(precondition_properties),
        }
    return _with_request_controls(
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["ref", "operation", "parameters", "idempotency_key"],
            "properties": properties,
        }
    )


PROJECT_CHANGE_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
    operations=("apply_patch", "write"),
    precondition_properties={
        "head": {"type": "string", "pattern": "^[0-9a-f]{40,64}$"},
        "dirty_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    },
)


FILES_CHANGE_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
    operations=("append", "copy", "mkdir", "move", "remove", "replace"),
    precondition_properties={
        "expected_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    },
)

BEADS_CHANGE_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://projects/[^/]+(?:/beads/[^/]+)?$",
    operations=(
        "claim",
        "close",
        "comment",
        "create",
        "dependency.add",
        "dependency.remove",
        "memory.forget",
        "memory.remember",
        "graph.create",
        "relate",
        "reopen",
        "unclaim",
        "unrelate",
        "update",
        "reparent",
    ),
    precondition_properties={
        "expected_task_revision": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "expected_etag": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "expected_status": {"type": "string", "maxLength": 64},
        "expected_assignee": {"type": ["string", "null"], "maxLength": 256},
    },
)

BEADS_QUERY_SCHEMA: dict[str, Any] = _with_request_controls(
    {"type": "object", "additionalProperties": False, "required": ["action_name", "parameters"], "properties": {
        "action_name": {"const": "beads.query"},
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "project_ids": {"type": "array", "minItems": 1, "maxItems": 32, "items": {"type": "string", "minLength": 1, "maxLength": 128}},
            "view": {"enum": ["query", "ready", "blocked", "open", "all", "recent", "overdue", "deferred", "unassigned", "stale_claims", "epic_progress", "changed_since"]},
            "filters": {"type": "object", "maxProperties": 32}, "expression": {"type": "string", "minLength": 1, "maxLength": 4000}, "native_filters": {"type": "object", "maxProperties": 40},
            "order": {"type": "object", "additionalProperties": False, "properties": {"field": {"enum": ["priority", "created", "updated", "closed", "status", "id", "title", "type", "assignee"]}, "reverse": {"type": "boolean"}}},
            "includes": {"type": "array", "maxItems": 8, "items": {"enum": ["comments", "history", "events", "dependencies", "dependents", "children", "refs"]}},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200}, "cursor": {"type": "string", "minLength": 1, "maxLength": 256},
            "graph": {"type": "object", "additionalProperties": False, "properties": {"bead_id": {"type": "string"}, "direction": {"enum": ["down", "up", "both"]}, "edge_type": {"type": "string"}, "status": {"type": "string"}, "depth": {"type": "integer", "minimum": 1, "maximum": 20}, "max_rows": {"type": "integer", "minimum": 1, "maximum": 1000}, "mermaid": {"type": "boolean"}}},
            "memory": {"type": "object", "additionalProperties": False, "properties": {"key": {"type": "string"}, "query": {"type": "string"}}},
        }},
    }}
)

BEADS_CHANGE_SCHEMA["properties"]["parameters"] = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "id": {"type": "string", "minLength": 1, "maxLength": 128}, "mode": {"enum": ["preview", "apply"]},
        "preview_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "title": {"type": "string", "maxLength": 512},
        "text": {"type": "string", "maxLength": 32000}, "depends_on": {"type": "string", "maxLength": 128},
        "other_id": {"type": "string", "maxLength": 128}, "parent_id": {"type": "string", "maxLength": 128},
        "type": {"type": "string", "maxLength": 64}, "reason": {"type": "string", "maxLength": 32000}, "key": {"type": "string", "maxLength": 256}, "graph": {"type": "object", "maxProperties": 256},
        "patch": {"type": "object", "additionalProperties": False, "properties": {
            "set": {"type": "object"},
            "labels": {"type": "object", "additionalProperties": False, "properties": {"add": {"type": "array", "items": {"type": "string"}}, "remove": {"type": "array", "items": {"type": "string"}}, "replace": {"type": "array", "items": {"type": "string"}}}},
            "metadata": {"type": "object", "additionalProperties": False, "properties": {"set": {"type": "object"}, "unset": {"type": "array", "items": {"type": "string"}}}},
            "notes": {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {"text": {"type": "string", "maxLength": 32000}, "mode": {"enum": ["append", "replace"]}}},
            "unset": {"type": "array", "items": {"enum": ["due", "defer", "parent"]}},
        }},
    },
}

BEADS_CHANGESET_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://projects/[^/]+$",
    operations=("apply", "preview"),
)
BEADS_CHANGESET_SCHEMA["properties"]["parameters"] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["actions"],
    "properties": {
        "actions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 128,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ref", "operation", "parameters"],
                "properties": {
                    "ref": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 8_192,
                        "pattern": r"^sinnix://projects/[^/]+(?:/beads/[^/]+)?$",
                    },
                    "operation": {"enum": list(BEADS_CHANGE_SCHEMA["properties"]["operation"]["enum"])},
                    "parameters": {"type": "object", "maxProperties": 32},
                    "preconditions": BEADS_CHANGE_SCHEMA["properties"]["preconditions"],
                    "bind": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64,
                        "pattern": r"^[A-Za-z][A-Za-z0-9_]{0,63}$",
                    },
                },
            },
        },
        "on_error": {"enum": ["stop", "continue"]},
        "preview_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    },
}

BEADS_OPERATE_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://projects/[^/]+$",
    operations=("backup.create", "backup.list", "backup.restore", "snapshot.publish", "sync.pull", "sync.push"),
)
BEADS_OPERATE_SCHEMA["properties"]["parameters"] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "backup_id": {"type": "string", "minLength": 1, "maxLength": 256},
    },
}

MCP_CHANGE_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://mcp/[^/]+/tools/[^/]+$",
    operations=("call",),
)

DESKTOP_OPERATE_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://desktop/current$",
    operations=("dispatch", "focus_window", "keyword", "paste", "send_keystate", "send_shortcut"),
)

TERMINAL_OPERATE_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://terminals/[^/]+$",
    operations=("focus", "key", "run", "send"),
)

BROWSER_OPERATE_SCHEMA = _owner_change_schema(
    ref_pattern=r"^sinnix://browser/(?:agent-workspace|pages/[^/]+)$",
    operations=("agent_window", "await", "click", "close", "evaluate", "fill_form", "inject_text", "navigate", "reload", "wait_selector"),
)

MACHINE_OPERATE_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ref",
            "action",
            "parameters",
            "reason",
            "idempotency_key",
            "preconditions",
        ],
        "properties": {
            "ref": {
                "type": "string",
                "minLength": 1,
                "maxLength": 2_048,
                "pattern": "^sinnix://(?:jobs|machine|processes)/",
            },
            "action": {
                "enum": list(MACHINE_OPERATIONS)
            },
            "parameters": {"type": "object"},
            "preconditions": {
                "type": "object",
                "additionalProperties": False,
                "required": ["expected_revision"],
                "properties": {
                    "expected_revision": {"type": "integer", "minimum": 0},
                },
            },
        },
    }
)

AUDIT_EVENTS_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1_000,
                "default": 100,
            },
        },
    }
)

# The public ``query`` verb deliberately stays compact.  The exact owner
# contract is selected by ``action_name`` and retrieved lazily from the
# generated action-schema resource, so expanding an owner does not bloat the
# top-level MCP manifest.
OWNER_QUERY_SCHEMA: dict[str, Any] = _with_request_controls(
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ref": {"type": "string", "minLength": 1, "maxLength": 2_048},
            "parameters": {"type": "object", "additionalProperties": True},
        },
    }
)


def _owner_query_action(
    name: str,
    domain: str,
    owner: str,
    route: str,
    principals: frozenset[str],
    resource_kinds: tuple[str, ...],
    documentation: str,
) -> ActionSpec:
    return ActionSpec(
        name=name,
        verb=VerbFamily.QUERY,
        domain=domain,
        owner=owner,
        route=route,
        effect=EffectMode.READ,
        principals=principals,
        input_schema=OWNER_QUERY_SCHEMA,
        output_schema=V2_ENVELOPE_SCHEMA,
        resource_kinds=resource_kinds,
        documentation=documentation,
    )


def _owner_query_actions() -> tuple[ActionSpec, ...]:
    all_principals = frozenset({"observer", "agent-control", "operator"})
    observer_operator = frozenset({"observer", "operator"})
    return (
        _owner_query_action("projects.list", "projects", "projects", "projects.list", all_principals, ("project",), "List principal-visible projects without host paths."),
        _owner_query_action("projects.tree", "projects", "projects", "projects.tree", all_principals, ("project", "checkout"), "List a bounded canonical project tree without following symlinks."),
        _owner_query_action("projects.read", "projects", "projects", "projects.read", all_principals, ("project", "checkout"), "Read a bounded project file through a canonical project or checkout ref."),
        _owner_query_action("projects.diff", "projects", "projects", "projects.diff", all_principals, ("project", "checkout"), "Read a bounded Git diff through a canonical project or checkout ref."),
        _owner_query_action("machine.query", "machine", "machine", "observe.machine_query", all_principals, ("machine_unit", "process"), "Read one bounded, provenance-carrying machine section; overview replaces the retired whole-machine report."),
        _owner_query_action("capabilities.query", "capabilities", "capability-index", "capability_index.query", all_principals, ("capability",), "Search or exactly describe generated machine capabilities."),
        _owner_query_action("mcp.query", "mcp", "mcp-broker", "mcp.call.read", observer_operator, ("mcp_tool",), "Discover brokered MCP servers or invoke a declared read-only upstream tool."),
        _owner_query_action("desktop.query", "desktop", "desktop", "desktop.read", observer_operator, ("desktop",), "Read desktop state or capture output without changing focus."),
        _owner_query_action("terminals.query", "terminals", "terminals", "terminals.read", observer_operator, ("terminal",), "List terminals or read bounded terminal evidence."),
        _owner_query_action("browser.query", "browser", "browser", "browser.read", observer_operator, ("browser_page",), "Read browser state or capture only a registered gateway-owned browser target."),
        _owner_query_action("files.query", "files", "files", "files.read", observer_operator, ("host_file",), "Stat, list, or read a bounded principal-authorized host path."),
        _owner_query_action("sessions.query", "sessions", "sessions", "sessions.query", observer_operator, ("session",), "List, read, or search bounded provider-scoped coding sessions."),
        _owner_query_action("memory.query", "memory", "memory", "memory.query", observer_operator, ("session",), "Search or retrieve semantic memory while retaining source provenance."),
        _owner_query_action("timeline.query", "timeline", "timeline", "timeline.query", observer_operator, ("session",), "Query available session evidence without claiming unavailable upstream coverage."),
        _owner_query_action("artifacts.query", "artifacts", "artifacts", "artifacts.query", all_principals, ("artifact",), "List opaque artifact metadata or read a bounded artifact range."),
        _owner_query_action("audit.verify", "audit", "audit", "audit.verify", all_principals, ("receipt",), "Verify the tamper-evident audit hash chain."),
        _owner_query_action("captures.query", "captures", "captures", "captures.query", all_principals, ("capture_lane",), "List visible capture lanes or query their declared native owner roots."),
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
        ResourceSpec("process", RefTemplate("process", "sinnix://processes/{pid}/{start_ticks}"), "machine", ("status",), True),
        ResourceSpec("browser_page", RefTemplate("browser_page", "sinnix://browser/pages/{page_id}"), "browser", ("summary", "content"), True),
        ResourceSpec("browser_workspace", RefTemplate("browser_workspace", "sinnix://browser/agent-workspace"), "browser", ("summary",), False, principals=frozenset({"operator"})),
        ResourceSpec("terminal", RefTemplate("terminal", "sinnix://terminals/{terminal_id}"), "terminals", ("summary", "scrollback"), True),
        ResourceSpec("desktop", RefTemplate("desktop", "sinnix://desktop/current"), "desktop", ("summary",), False, principals=frozenset({"operator"})),
        ResourceSpec("host_file", RefTemplate("host_file", "sinnix://files/{file_token}"), "files", ("summary",), False, principals=frozenset({"operator"})),
        ResourceSpec("mcp_tool", RefTemplate("mcp_tool", "sinnix://mcp/{server}/tools/{tool}"), "mcp-broker", ("summary",), False, principals=frozenset({"operator"})),
        ResourceSpec("capture_lane", RefTemplate("capture_lane", "sinnix://captures/{lane}"), "captures", ("summary", "query"), True),
        ResourceSpec("capability", RefTemplate("capability", "sinnix://capabilities/{name}"), "capability-index", ("summary",), True),
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
            resource_kinds=("project", "checkout", "bead", "task_authority", "job"),
            examples=({"input": {"ref": "sinnix://projects/sinnix"}},),
            documentation="Resolve one canonical project, checkout, Beads task, or task-authority reference.",
        ),
        ActionSpec(
            name="projects.query",
            verb=VerbFamily.QUERY,
            domain="projects",
            owner="projects",
            route="projects.search",
            effect=EffectMode.READ,
            principals=frozenset({"observer", "agent-control", "operator"}),
            input_schema=PROJECT_QUERY_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "checkout"),
            examples=(
                {
                    "input": {
                        "ref": "sinnix://projects/sinnix",
                        "query": "mkServiceModule",
                        "max_matches": 20,
                    }
                },
            ),
            documentation="Search one canonical project or checkout through the bounded project owner.",
        ),
        ActionSpec(
            name="beads.query",
            verb=VerbFamily.QUERY,
            domain="beads",
            owner="beads",
            route="beads.query",
            effect=EffectMode.READ,
            principals=frozenset({"observer", "agent-control", "operator"}),
            input_schema=BEADS_QUERY_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "bead", "task_authority"),
            examples=({"input": {"action_name": "beads.query", "parameters": {"project_ids": ["polylogue"], "view": "query", "filters": {"status": "open", "priority": {"op": "<=", "value": 1}}, "includes": ["dependencies"], "limit": 50}}},),
            documentation="Query canonical project-qualified Beads resources with bounded snapshot paging and explicit coverage.",
        ),
        ActionSpec(
            name="projects.context",
            verb=VerbFamily.CONTEXT,
            domain="projects",
            owner="project-context",
            route="project_context.context",
            effect=EffectMode.READ,
            principals=frozenset({"observer", "agent-control", "operator"}),
            input_schema=PROJECT_CONTEXT_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "checkout", "bead", "task_authority"),
            examples=(
                {"input": {"ref": "sinnix://projects/sinnix"}},
            ),
            documentation="Compose Git and bounded task orientation for one canonical project.",
        ),
        ActionSpec(
            name="audit.events",
            verb=VerbFamily.EVENTS,
            domain="audit",
            owner="audit",
            route="audit.tail",
            effect=EffectMode.READ,
            principals=frozenset({"observer", "agent-control", "operator"}),
            input_schema=AUDIT_EVENTS_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("receipt",),
            receipt_policy="audit",
            examples=({"input": {"limit": 100}},),
            documentation="Read bounded audit events visible to the active principal.",
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
            name="projects.change",
            verb=VerbFamily.CHANGE,
            domain="projects",
            owner="projects",
            route="projects.change",
            effect=EffectMode.CHANGE,
            principals=frozenset({"operator"}),
            input_schema=PROJECT_CHANGE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "checkout"),
            supports_idempotency=True,
            supports_precondition=True,
            receipt_policy="audit",
            examples=(
                {
                    "input": {
                        "ref": "sinnix://projects/sinnix/checkouts/default",
                        "operation": "write",
                        "path": "README.md",
                        "content": "updated content\\n",
                        "preconditions": {"head": "a" * 40},
                        "idempotency_key": "project-write-example",
                    }
                },
            ),
            documentation="Apply one bounded, precondition-checked project write or patch through a canonical project or checkout reference.",
        ),
        ActionSpec(
            name="files.change",
            verb=VerbFamily.CHANGE,
            domain="files",
            owner="files",
            route="files.change",
            effect=EffectMode.CHANGE,
            principals=frozenset({"operator"}),
            input_schema=FILES_CHANGE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("host_file",),
            supports_idempotency=True,
            supports_precondition=True,
            receipt_policy="audit",
            examples=({"input": {"ref": "sinnix://files/L3JlYWxtL3RtcC9maWxl", "operation": "replace", "parameters": {"content": "updated content\\n"}, "idempotency_key": "file-replace-example"}},),
            documentation="Apply one bounded host-file mutation through an opaque canonical file reference.",
        ),
        ActionSpec(
            name="beads.change",
            verb=VerbFamily.CHANGE,
            domain="beads",
            owner="beads",
            route="beads.write",
            effect=EffectMode.CHANGE,
            principals=frozenset({"operator"}),
            input_schema=BEADS_CHANGE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "bead", "task_authority"),
            supports_idempotency=True,
            supports_precondition=True,
            receipt_policy="audit",
            examples=({"input": {"ref": "sinnix://projects/sinnix", "operation": "comment", "parameters": {"id": "sinnix-example", "text": "recorded by the operator"}, "idempotency_key": "bead-comment-example"}},),
            documentation="Perform one structured, attested Beads mutation for a canonical project.",
        ),
        ActionSpec(
            name="beads.changeset",
            verb=VerbFamily.CHANGE,
            domain="beads",
            owner="beads",
            route="beads.changeset",
            effect=EffectMode.CHANGE,
            principals=frozenset({"operator"}),
            input_schema=BEADS_CHANGESET_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "bead", "task_authority"),
            supports_idempotency=True,
            supports_precondition=True,
            receipt_policy="audit",
            examples=({"input": {"ref": "sinnix://projects/sinnix", "operation": "preview", "parameters": {"actions": [{"ref": "sinnix://projects/sinnix", "operation": "create", "parameters": {"title": "parent"}, "bind": "parent"}, {"ref": "sinnix://projects/sinnix", "operation": "create", "parameters": {"title": "child", "parent": "$parent"}}]}, "idempotency_key": "beads-changeset-example"}},),
            documentation="Preview or apply an ordered, project-partitioned Beads changeset with explicit step outcomes and no global rollback claim.",
        ),
        ActionSpec(
            name="beads.operate",
            verb=VerbFamily.OPERATE,
            domain="beads",
            owner="beads",
            route="beads.maintenance",
            effect=EffectMode.OPERATE,
            principals=frozenset({"operator"}),
            input_schema=BEADS_OPERATE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "task_authority"),
            supports_idempotency=True,
            receipt_policy="audit",
            examples=({"input": {"ref": "sinnix://projects/sinnix", "operation": "snapshot.publish", "parameters": {}, "idempotency_key": "beads-publish-example"}},),
            documentation="Run one explicit Beads publication, Dolt sync, or supported backup operation. Ordinary mutations do not publish JSONL or create Git commits.",
        ),
        ActionSpec(
            name="mcp.change",
            verb=VerbFamily.CHANGE,
            domain="mcp",
            owner="mcp-broker",
            route="mcp.call.write",
            effect=EffectMode.CHANGE,
            principals=frozenset({"operator"}),
            input_schema=MCP_CHANGE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("mcp_tool",),
            supports_idempotency=True,
            receipt_policy="audit",
            examples=({"input": {"ref": "sinnix://mcp/lynchpin/tools/refresh", "operation": "call", "parameters": {}, "idempotency_key": "mcp-refresh-example"}},),
            documentation="Call one brokered upstream MCP tool whose live metadata does not declare it read-only.",
        ),
        ActionSpec(
            name="machine.operate",
            verb=VerbFamily.OPERATE,
            domain="machine",
            owner="ops-reducer",
            route="ops.actions.execute",
            effect=EffectMode.OPERATE,
            principals=frozenset({"operator"}),
            input_schema=MACHINE_OPERATE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("job", "machine_unit", "process"),
            supports_idempotency=True,
            supports_precondition=True,
            receipt_policy="owner",
            examples=(
                {
                    "input": {
                        "ref": "sinnix://machine/units/user/example.service",
                        "action": "restart",
                        "parameters": {},
                        "reason": "apply the approved restart",
                        "preconditions": {"expected_revision": 42},
                        "idempotency_key": "restart-example",
                    }
                },
            ),
            documentation="Submit one revision-checked ops-reducer action against a canonical attested target reference.",
        ),
        ActionSpec(
            name="agents.run",
            verb=VerbFamily.RUN,
            domain="agents",
            owner="systemd-jobs",
            route="job.agent.start",
            effect=EffectMode.RUN,
            principals=frozenset({"agent-control"}),
            input_schema=AGENT_RUN_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("project", "checkout", "job"),
            supports_idempotency=True,
            receipt_policy="audit",
            examples=(
                {
                    "input": {
                        "project_id": "sinnix",
                        "prompt": "Inspect the declared task and report evidence.",
                        "backend": "codex",
                        "model": "gpt-5.6-terra",
                        "reasoning_effort": "high",
                        "idempotency_key": "agent-inspect-example",
                    }
                },
            ),
            documentation="Launch one typed attested coding-agent job and return its daemon-owned handle.",
        ),
        ActionSpec(
            name="jobs.cancel",
            verb=VerbFamily.OPERATE,
            domain="jobs",
            owner="systemd-jobs",
            route="job.cancel",
            effect=EffectMode.OPERATE,
            principals=frozenset({"agent-control", "operator"}),
            input_schema=JOB_CANCEL_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("job",),
            supports_idempotency=True,
            supports_precondition=True,
            receipt_policy="audit",
            examples=(
                {
                    "input": {
                        "ref": "sinnix://jobs/3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c",
                        "preconditions": {"expected_phase": "running"},
                        "idempotency_key": "cancel-example",
                    }
                },
            ),
            documentation="Request cancellation for one phase-checked daemon job and return the owner truth without asserting terminal completion.",
        ),
        ActionSpec(
            name="desktop.operate",
            verb=VerbFamily.OPERATE,
            domain="desktop",
            owner="desktop",
            route="desktop.action",
            effect=EffectMode.OPERATE,
            principals=frozenset({"operator"}),
            input_schema=DESKTOP_OPERATE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("desktop",),
            supports_idempotency=True,
            receipt_policy="audit",
            examples=({"input": {"ref": "sinnix://desktop/current", "operation": "focus_window", "parameters": {"window": "address:0xfixture"}, "idempotency_key": "desktop-focus-example"}},),
            documentation="Operate the current desktop through the declared Hyprland owner route.",
        ),
        ActionSpec(
            name="terminals.operate",
            verb=VerbFamily.OPERATE,
            domain="terminals",
            owner="terminals",
            route="terminals.action",
            effect=EffectMode.OPERATE,
            principals=frozenset({"operator"}),
            input_schema=TERMINAL_OPERATE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("terminal",),
            supports_idempotency=True,
            receipt_policy="audit",
            examples=({"input": {"ref": "sinnix://terminals/7", "operation": "send", "parameters": {"text": "printf fixture", "enter": True}, "idempotency_key": "terminal-send-example"}},),
            documentation="Operate one canonical Kitty terminal without accepting an arbitrary matcher.",
        ),
        ActionSpec(
            name="browser.operate",
            verb=VerbFamily.OPERATE,
            domain="browser",
            owner="browser",
            route="browser.action",
            effect=EffectMode.OPERATE,
            principals=frozenset({"operator"}),
            input_schema=BROWSER_OPERATE_SCHEMA,
            output_schema=V2_ENVELOPE_SCHEMA,
            resource_kinds=("browser_workspace", "browser_page"),
            supports_idempotency=True,
            receipt_policy="audit",
            examples=({"input": {"ref": "sinnix://browser/agent-workspace", "operation": "agent_window", "parameters": {"url": "https://example.test"}, "idempotency_key": "browser-window-example"}},),
            documentation="Create or operate only a gateway-owned browser target on the hidden agent workspace.",
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
    return CatalogRegistry(resources, (*actions, *_owner_query_actions()))


REGISTRY = build_registry()
