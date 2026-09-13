"""Public snapshot references survive owner changes and server recreation."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import anyio
from conftest import error, ok
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.capabilities import Capability
from test_actions_beads import commands, fixture
from test_contexts import historical_context


def read_resource(server, reference: str) -> dict:
    async def read():
        result = await server.read_resource(reference)
        return json.loads(list(result)[0].content)

    return anyio.run(read)


def test_beads_public_snapshot_and_frozen_paging_after_restart(tmp_path: Path) -> None:
    config, log = fixture(tmp_path)
    server = create_server(config, "observer")
    query = {"projects": ["fixture"], "view": "open", "limit": 1}
    first = ok(server, "beads.query", query)
    reference = first["page"]["snapshot_ref"]
    cursor = first["page"]["next_cursor"]
    (tmp_path / "owner-state.json").write_text(json.dumps({"writes": 10, "created": 0}))
    restarted = create_server(config, "observer")
    reads = len(commands(log))
    second = ok(restarted, "beads.query", {**query, "cursor": cursor})
    assert [row["id"] for row in second["items"]] == ["fixture-2"]
    assert second["source_revisions"] == first["source_revisions"]
    assert second["coverage"] == first["coverage"]
    assert second["totals"] == first["totals"]
    assert len(commands(log)) == reads
    stored = ok(restarted, "results.get", {"ref": reference})["envelope"]
    assert [row["id"] for row in stored["rows"]] == ["fixture-1", "fixture-2"]
    assert stored["metadata"]["coverage"] == first["coverage"]
    assert read_resource(restarted, reference) == stored
    assert (
        error(restarted, "beads.query", {**query, "view": "all", "cursor": cursor})
        == "stale_cursor"
    )
    other = create_server(config, "operator")
    assert error(other, "beads.query", {**query, "cursor": cursor}) == "stale_cursor"
    assert error(other, "results.get", {"ref": reference}) == "not_found"


def test_context_public_retrieval_after_restart_retains_provenance(
    tmp_path: Path,
) -> None:
    config, _ = fixture(tmp_path)
    server = create_server(config, "observer")
    context = ok(
        server,
        "context.compose",
        {"intent": "project.orientation", "project": {"project": "fixture"}},
    )
    reference = context["snapshot_ref"]
    restarted = create_server(config, "observer")
    stored = ok(restarted, "results.get", {"ref": reference})["envelope"]
    retained = stored["rows"][0]
    assert retained["intent"] == context["intent"]
    assert retained["target_ref"] == context["target_ref"]
    assert retained["component_plan"] == context["component_plan"]
    for original, row in zip(
        context["components"], retained["components"], strict=True
    ):
        assert row["name"] == original["name"]
        assert row["source_revision"] == original["source_revision"]
        assert row.get("source_ref") == original.get("source_ref")
        assert row.get("data") == original.get("data")
        assert row["snapshot_ref"] == reference
    assert read_resource(restarted, reference) == stored
    assert (
        error(create_server(config, "operator"), "results.get", {"ref": reference})
        == "not_found"
    )


def test_historical_context_refs_remain_publicly_readable_without_rewrite(
    tmp_path: Path,
) -> None:
    config, _ = fixture(tmp_path)
    snapshot = historical_context()
    reference = snapshot["snapshot_ref"]
    path = (
        config.state_dir
        / "contexts"
        / "observer"
        / f"{reference.rsplit('/', 1)[1]}.json"
    )
    path.parent.mkdir(parents=True)
    contents = json.dumps(snapshot).encode()
    path.write_bytes(contents)
    before = path.stat().st_mtime_ns
    server = create_server(config, "observer")
    assert ok(server, "results.get", {"ref": reference})["envelope"] == snapshot
    assert read_resource(server, reference)["data"]["envelope"] == snapshot
    assert (
        error(create_server(config, "operator"), "results.get", {"ref": reference})
        == "not_found"
    )
    assert path.read_bytes() == contents and path.stat().st_mtime_ns == before


def test_legacy_beads_cursor_imports_frozen_rows_without_modifying_source(
    tmp_path: Path,
) -> None:
    config, _ = fixture(tmp_path)
    request = {
        "principal": "observer",
        "projects": ["fixture"],
        "view": "open",
        "filters": {},
        "expression": None,
        "native": {},
        "order": {},
        "includes": [],
        "at": None,
        "projection": "summary",
        "aggregate": None,
    }
    key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    token = "a" * 64
    path = config.state_dir / "beads-snapshots" / f"{token}.json"
    path.parent.mkdir(parents=True)
    rows = [
        {"id": "fixture-1", "project_id": "fixture", "fields": {"title": "original"}},
        {"id": "fixture-2", "project_id": "fixture", "fields": {"title": "frozen"}},
    ]
    contents = json.dumps(
        {
            "key": key,
            "source_revision": "old-revision",
            "expires_at": time.time() + 300,
            "rows": rows,
            "metadata": {},
        }
    )
    path.write_text(contents)
    server = create_server(config, "observer")
    page = ok(
        server,
        "beads.query",
        {"projects": ["fixture"], "view": "open", "limit": 1, "cursor": f"{token}.1"},
    )
    assert page["items"][0]["id"] == "fixture-2"
    assert (
        ok(server, "results.get", {"ref": page["page"]["snapshot_ref"]})["envelope"][
            "rows"
        ]
        == rows
    )
    assert path.read_text() == contents


def test_published_prompt_accepts_its_declared_target(tmp_path: Path) -> None:
    config, _ = fixture(tmp_path)
    server = create_server(config, "observer")

    async def get():
        return await server.get_prompt(
            "orient-project", {"ref": "sinnix://projects/fixture"}
        )

    prompt = anyio.run(get)
    assert (
        json.loads(prompt.messages[0].content.text)["intent"] == "project.orientation"
    )


def test_historical_context_read_requires_audit_capability(tmp_path: Path) -> None:
    config, _ = fixture(tmp_path)
    snapshot = historical_context()
    reference = snapshot["snapshot_ref"]
    path = (
        config.state_dir
        / "contexts"
        / "observer"
        / f"{reference.rsplit('/', 1)[1]}.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(snapshot))
    server = create_server(config, "observer")
    runtime = server._sinnix_revision_publisher.runtime
    runtime.principal = replace(
        runtime.principal,
        capabilities=runtime.principal.capabilities - {Capability.AUDIT_READ},
    )
    assert error(server, "results.get", {"ref": reference}) == "policy_denied"
