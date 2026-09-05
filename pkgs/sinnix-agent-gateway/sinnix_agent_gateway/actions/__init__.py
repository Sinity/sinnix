"""Every typed gateway action, validated once at import."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..action import Action, validate_actions
from ..registry import REGISTRY
from . import (
    activity,
    artifacts,
    audit,
    beads,
    browser,
    contexts,
    desktop,
    files,
    gateway,
    jobs,
    machine,
    mcp_tools,
    processes,
    projects,
    terminals,
    waits,
)

REVISION = "v3-typed-actions"

ALL_ACTIONS: tuple[Action, ...] = validate_actions(
    (
        *gateway.ACTIONS,
        *files.ACTIONS,
        *projects.ACTIONS,
        *beads.ACTIONS,
        *jobs.ACTIONS,
        *waits.ACTIONS,
        *contexts.ACTIONS,
        *desktop.ACTIONS,
        *terminals.ACTIONS,
        *browser.ACTIONS,
        *machine.ACTIONS,
        *processes.ACTIONS,
        *mcp_tools.ACTIONS,
        *artifacts.ACTIONS,
        *activity.ACTIONS,
        *audit.ACTIONS,
    ),
)

BY_NAME: dict[str, Action] = {action.name: action for action in ALL_ACTIONS}


def visible(principal: str) -> tuple[Action, ...]:
    return tuple(action for action in ALL_ACTIONS if principal in action.principals)


def catalog_hash(principal: str) -> str:
    """Digest of the principal-visible action contract: names and schemas."""
    rows = [
        {
            "name": action.name,
            "family": action.family.value,
            "input": action.input_schema(),
            "output": action.output_schema(),
        }
        for action in visible(principal)
    ]
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def resource_rows(principal: str) -> list[dict[str, Any]]:
    """Resource kinds with the visible actions that read or change them."""
    by_kind: dict[str, list[str]] = {}
    for action in visible(principal):
        for kind in action.resource_kinds:
            by_kind.setdefault(kind, []).append(action.name)
    rows = []
    for resource in REGISTRY.resources:
        if principal not in resource.principals:
            continue
        rows.append(
            {
                "kind": resource.kind,
                "owner": resource.owner,
                "ref_template": resource.ref_template.template,
                "actions": sorted(by_kind.get(resource.kind, [])),
            }
        )
    return rows
