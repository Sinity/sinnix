from __future__ import annotations

import json
from pathlib import Path

from sinnix_agent_gateway.parity import (
    LEGACY_MANIFEST_SCHEMA,
    PARITY_SCHEMA,
    V2_MIGRATIONS,
    legacy_parity_contract,
)
from sinnix_agent_gateway.registry import REGISTRY


def test_legacy_to_v2_parity_is_exhaustive_and_registry_bound() -> None:
    contract = legacy_parity_contract(REGISTRY)
    manifest = json.loads(
        (Path(__file__).parent / "sinnix_agent_gateway" / "legacy_manifest_v1.json").read_text()
    )

    assert contract["schema"] == PARITY_SCHEMA
    assert manifest["schema"] == LEGACY_MANIFEST_SCHEMA
    assert contract["legacy_manifest"] == {
        "commit": manifest["source_commit"],
        "tool_count": len(manifest["tools"]),
        "canonical_bytes": manifest["canonical_bytes"],
    }
    assert len(contract["rows"]) == len(manifest["tools"]) == 49
    assert {row["legacy_tool"] for row in contract["rows"]} == set(manifest["tools"])
    assert set(V2_MIGRATIONS) == set(manifest["tools"])
    assert all(row["bound"] == "owner_limit_and_result_snapshot" for row in contract["rows"])
    assert all(
        row["required_principals"]
        == tuple(sorted(REGISTRY.action(row["v2_action"]).principals))
        for row in contract["rows"]
    )
    assert all(
        row["typed_failures"]
        == tuple(sorted(REGISTRY.action(row["v2_action"]).typed_failures))
        for row in contract["rows"]
    )
    assert {row["receipt_policy"] for row in contract["rows"]} == {"audit", "owner"}


def test_parity_map_preserves_the_checked_in_historical_order() -> None:
    package_root = Path(__file__).parent
    manifest = json.loads(
        (package_root / "sinnix_agent_gateway" / "legacy_manifest_v1.json").read_text()
    )
    rows = legacy_parity_contract(REGISTRY)["rows"]

    assert len(manifest["tools"]) == 49
    assert [row["legacy_tool"] for row in rows] == manifest["tools"]
    assert list(V2_MIGRATIONS) == manifest["tools"]


def test_job_list_and_agent_launch_have_visible_v2_replacements() -> None:
    rows = {row["legacy_tool"]: row for row in legacy_parity_contract(REGISTRY)["rows"]}

    assert rows["job_list"]["v2_action"] == "jobs.query"
    assert rows["job_list"]["v2_route"] == "job.list"
    assert rows["agent_launch"]["v2_action"] == "agent.for_bead"
    assert rows["agent_launch"]["required_principals"] == ("agent-control", "operator")


def test_shell_query_semantic_change_is_explicit() -> None:
    row = {
        row["legacy_tool"]: row for row in legacy_parity_contract(REGISTRY)["rows"]
    }["shell_query"]

    assert row["v2_action"] == "shell.run"
    assert row["required_principals"] == ("operator",)
    assert row["semantic_change"] == (
        "V2 retires arbitrary read-only shell execution; typed shell jobs require "
        "operator authority."
    )
