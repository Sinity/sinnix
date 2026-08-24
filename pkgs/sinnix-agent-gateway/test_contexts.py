from __future__ import annotations

import json

from sinnix_agent_gateway.contexts import (
    CONTEXT_INTENTS,
    ComponentResult,
    ComponentSpec,
    ContextComposer,
    RevisionReuseCache,
)


def test_declared_contexts_are_bounded_and_isolate_unavailable_components() -> None:
    composer = ContextComposer()
    result = composer.compose(
        "project.orientation",
        "sinnix://projects/fixture",
        [
            ComponentSpec("project", 12_000, lambda: ComponentResult.available("project", {"head": "a"})),
            ComponentSpec("checkout", 12_000, lambda: ComponentResult.unavailable("checkout", "checkout owner offline")),
            ComponentSpec("tasks", 16_000, lambda: ComponentResult.available("tasks", {"items": [1, 2]})),
            ComponentSpec("authority", 8_000, lambda: ComponentResult.stale("authority", "owner revision is stale", revision="b")),
        ],
    )

    assert set(result) >= {"intent", "component_plan", "components", "snapshot_ref"}
    assert result["snapshot_ref"].startswith("sinnix://contexts/")
    assert len(json.dumps(result, separators=(",", ":")).encode()) <= CONTEXT_INTENTS["project.orientation"].total_budget_bytes
    states = {row["name"]: row["status"] for row in result["components"]}
    assert states == {"project": "available", "checkout": "unavailable", "tasks": "available", "authority": "stale"}
    assert all(row["snapshot_ref"] == result["snapshot_ref"] for row in result["components"])


def test_component_budget_marks_only_the_oversized_component_unavailable() -> None:
    result = ContextComposer().compose(
        "bead.work",
        "sinnix://projects/fixture/beads/fixture-1",
        [
            ComponentSpec("bead", 128, lambda: ComponentResult.available("bead", {"body": "x" * 1_000})),
            ComponentSpec("project", 12_000, lambda: ComponentResult.available("project", {"ok": True})),
            ComponentSpec("checkout", 12_000, lambda: ComponentResult.available("checkout", {"ok": True})),
            ComponentSpec("assignment", 14_000, lambda: ComponentResult.available("assignment", {"ok": True})),
            ComponentSpec("blockers", 8_000, lambda: ComponentResult.available("blockers", {"ok": True})),
        ],
    )
    rows = {row["name"]: row for row in result["components"]}
    assert rows["bead"]["status"] == "unavailable"
    assert rows["project"]["status"] == "available"
    assert "data" not in rows["bead"]


def test_revision_cache_never_reuses_a_different_owner_revision() -> None:
    cache = RevisionReuseCache()
    first = ComponentResult.available("project", {"value": 1}, revision="rev-a")
    second = ComponentResult.available("project", {"value": 2}, revision="rev-b")
    cache.put(first)
    cache.put(second)

    assert cache.get("project", "rev-a") is first
    assert cache.get("project", "rev-b") is second
    assert cache.get("project", "rev-c") is None


def test_missing_declared_component_is_explicitly_unavailable() -> None:
    result = ContextComposer().compose(
        "project.triage",
        "sinnix://projects/fixture",
        [ComponentSpec("project", 12_000, lambda: ComponentResult.available("project", {"ok": True}))],
    )
    rows = {row["name"]: row for row in result["components"]}
    assert {row["status"] for name, row in rows.items() if name != "project"} == {"unavailable"}
