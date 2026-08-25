from __future__ import annotations

import json
from pathlib import Path

import pytest
from sinnix_agent_gateway.contexts import (
    CONTEXT_INTENTS,
    ComponentResult,
    ComponentSpec,
    ContextComposer,
    ContextSnapshotStore,
    RevisionReuseCache,
)
from sinnix_agent_gateway.runtime import _orientation_task_summary


def test_orientation_task_summary_retains_routing_and_drops_large_bodies() -> None:
    result = _orientation_task_summary(
        {
            "items": [
                {
                    "id": "fixture-1",
                    "ref": "sinnix://projects/fixture/beads/fixture-1",
                    "title": "Do the work",
                    "priority": 1,
                    "task_revision": "a" * 64,
                    "description": "x" * 100_000,
                    "acceptance_criteria": "y" * 100_000,
                }
            ],
            "page": {"total": 1},
            "coverage": {"fixture": {"state": "complete"}},
        }
    )

    assert result["items"] == [
        {
            "id": "fixture-1",
            "ref": "sinnix://projects/fixture/beads/fixture-1",
            "title": "Do the work",
            "priority": 1,
            "task_revision": "a" * 64,
        }
    ]
    assert result["page"] == {"total": 1}
    assert len(json.dumps(result)) < 1_000


def test_context_snapshot_survives_store_recreation_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    snapshot = ContextComposer().compose(
        "project.orientation",
        "sinnix://projects/fixture",
        [
            ComponentSpec(
                "project",
                12_000,
                lambda: ComponentResult.available("project", {"head": "a"}),
            ),
            ComponentSpec(
                "checkout",
                12_000,
                lambda: ComponentResult.available("checkout", {"head": "a"}),
            ),
            ComponentSpec(
                "tasks",
                16_000,
                lambda: ComponentResult.available("tasks", {"items": []}),
            ),
            ComponentSpec(
                "authority",
                8_000,
                lambda: ComponentResult.available("authority", {"revision": "a"}),
            ),
        ],
    )
    snapshot_id = snapshot["snapshot_ref"].rsplit("/", 1)[1]
    ContextSnapshotStore(tmp_path, "observer").put(snapshot)

    restarted = ContextSnapshotStore(tmp_path, "observer")
    assert restarted.get(snapshot_id) == snapshot
    path = tmp_path / "contexts" / "observer" / f"{snapshot_id}.json"
    path.write_text(path.read_text().replace('"head":"a"', '"head":"b"'))
    with pytest.raises(KeyError):
        restarted.get(snapshot_id)


def test_declared_contexts_are_bounded_and_isolate_unavailable_components() -> None:
    composer = ContextComposer()
    result = composer.compose(
        "project.orientation",
        "sinnix://projects/fixture",
        [
            ComponentSpec(
                "project",
                12_000,
                lambda: ComponentResult.available("project", {"head": "a"}),
            ),
            ComponentSpec(
                "checkout",
                12_000,
                lambda: ComponentResult.unavailable(
                    "checkout", "checkout owner offline"
                ),
            ),
            ComponentSpec(
                "tasks",
                16_000,
                lambda: ComponentResult.available("tasks", {"items": [1, 2]}),
            ),
            ComponentSpec(
                "authority",
                8_000,
                lambda: ComponentResult.unavailable(
                    "authority", "owner freshness evidence is unavailable", revision="b"
                ),
            ),
        ],
    )

    assert set(result) >= {"intent", "component_plan", "components", "snapshot_ref"}
    assert result["snapshot_ref"].startswith("sinnix://contexts/")
    assert (
        len(json.dumps(result, separators=(",", ":")).encode())
        <= CONTEXT_INTENTS["project.orientation"].total_budget_bytes
    )
    states = {row["name"]: row["status"] for row in result["components"]}
    assert states == {
        "project": "available",
        "checkout": "unavailable",
        "tasks": "available",
        "authority": "unavailable",
    }
    assert all(
        row["snapshot_ref"] == result["snapshot_ref"] for row in result["components"]
    )


def test_component_budget_marks_only_the_oversized_component_unavailable() -> None:
    result = ContextComposer().compose(
        "bead.work",
        "sinnix://projects/fixture/beads/fixture-1",
        [
            ComponentSpec(
                "bead",
                128,
                lambda: ComponentResult.available("bead", {"body": "x" * 1_000}),
            ),
            ComponentSpec(
                "project",
                12_000,
                lambda: ComponentResult.available("project", {"ok": True}),
            ),
            ComponentSpec(
                "checkout",
                12_000,
                lambda: ComponentResult.available("checkout", {"ok": True}),
            ),
            ComponentSpec(
                "assignment",
                14_000,
                lambda: ComponentResult.available("assignment", {"ok": True}),
            ),
            ComponentSpec(
                "blockers",
                8_000,
                lambda: ComponentResult.available("blockers", {"ok": True}),
            ),
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


def test_revision_cache_evicts_by_entries_and_bytes_before_growth() -> None:
    cache = RevisionReuseCache(max_entries=2, max_bytes=500)
    first = ComponentResult.available("first", {"value": "a"}, revision="a")
    second = ComponentResult.available("second", {"value": "b"}, revision="b")
    third = ComponentResult.available("third", {"value": "c"}, revision="c")
    cache.put(first)
    cache.put(second)
    cache.put(third)
    assert cache.get("first", "a") is None
    assert cache.get("second", "b") is second
    assert cache.get("third", "c") is third


def test_revision_cache_rejects_oversized_component_without_insertion() -> None:
    cache = RevisionReuseCache(max_entries=4, max_bytes=128)
    oversized = ComponentResult.available(
        "large", {"body": "x" * 10_000}, revision="large"
    )
    cache.put(oversized)
    assert cache.get("large", "large") is None


def test_missing_declared_component_is_explicitly_unavailable() -> None:
    result = ContextComposer().compose(
        "project.triage",
        "sinnix://projects/fixture",
        [
            ComponentSpec(
                "project",
                12_000,
                lambda: ComponentResult.available("project", {"ok": True}),
            )
        ],
    )
    rows = {row["name"]: row for row in result["components"]}
    assert {row["status"] for name, row in rows.items() if name != "project"} == {
        "unavailable"
    }
