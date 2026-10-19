"""Every typed gateway action, validated once at import."""

from __future__ import annotations

import hashlib
import json
from functools import cache
from typing import Any

from ..action import Action, validate_actions
from ..registry import REGISTRY
from . import (
    activity,
    artifacts,
    audit,
    batches,
    beads,
    browser,
    contexts,
    desktop,
    files,
    gateway,
    jobs,
    machine,
    mcp_tools,
    organization,
    processes,
    products,
    projects,
    terminals,
    waits,
)

REVISION = "v3-typed-actions"

ALL_ACTIONS: tuple[Action, ...] = validate_actions(
    (
        *gateway.ACTIONS,
        *files.ACTIONS,
        *organization.ACTIONS,
        *projects.ACTIONS,
        *beads.ACTIONS,
        *jobs.ACTIONS,
        *batches.ACTIONS,
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
        *products.ACTIONS,
        *audit.ACTIONS,
    ),
)

BY_NAME: dict[str, Action] = {action.name: action for action in ALL_ACTIONS}


@cache
def catalog_hash() -> str:
    """Digest of every catalog row field.

    The generated contract promises that examples and next_actions participate
    in this digest alongside names and schemas. The action set is fixed for
    this process; the digest is computed once, at the server startup warm-up.
    Hashing the complete catalog row keeps that promise true when another
    documented action field is added later.
    """
    rows = [action.catalog_row() for action in ALL_ACTIONS]
    rows.sort(key=lambda row: row["name"])
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def resource_rows() -> list[dict[str, Any]]:
    """Resource kinds with the actions that read or change them."""
    by_kind: dict[str, list[str]] = {}
    for action in ALL_ACTIONS:
        for kind in action.resource_kinds:
            by_kind.setdefault(kind, []).append(action.name)
    rows = []
    for resource in REGISTRY.resources:
        rows.append(
            {
                "kind": resource.kind,
                "owner": resource.owner,
                "ref_template": resource.ref_template.template,
                "actions": sorted(by_kind.get(resource.kind, [])),
            }
        )
    return rows
