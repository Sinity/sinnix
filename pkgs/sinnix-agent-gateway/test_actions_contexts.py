"""Context adapters preserve native owner products and persisted observations."""

from __future__ import annotations

import pytest
from sinnix_agent_gateway.actions.contexts import ComposeInput
from test_actions_jobs import DONE, call, make_server
from test_actions_products import Broker


def test_compose_input_binds_target_to_intent():
    with pytest.raises(ValueError, match="job.review takes job"):
        ComposeInput.model_validate(
            {"intent": "job.review", "project": {"project": "x"}}
        )
    with pytest.raises(ValueError, match="takes project"):
        ComposeInput.model_validate({"intent": "incident", "job": {"task_id": 1}})


@pytest.mark.parametrize(
    "intent",
    [
        "project.trajectory",
        "verification.regression",
    ],
)
def test_project_context_preserves_owner_components_and_observes_each_time(
    tmp_path, monkeypatch, intent
):
    server, runtime, _ = make_server(tmp_path, monkeypatch, with_git=True)
    product = {
        "components": [
            {"name": "tasks", "status": "unavailable", "reason": "owner offline"}
        ],
        "coverage": {"complete": False},
        "counts": {"exact": None},
    }
    runtime.mcp_broker = Broker(
        {"ok": True, "data": product, "meta": {"source_mode": "owner_snapshots"}}
    )
    for _ in range(2):
        response = call(
            server,
            "context.compose",
            {"intent": intent, "project": {"project": "fixture"}},
        )
        assert response["result"]["outcome"] == "ok", response
        value = response["data"]
        assert value["components"][0]["data"]["data"] == product
        saved = runtime.results.read(value["snapshot_ref"].rsplit("/", 1)[1])["rows"][0]
        assert saved["components"][0]["data"]["data"] == product
    assert len(runtime.mcp_broker.calls) == 2
    assert runtime.mcp_broker.calls[0][2]["action"] == "project_context"
    assert runtime.mcp_broker.calls[0][2]["intent"] == intent


def test_job_review_preserves_native_receipt_and_incident_uses_observe(
    tmp_path, monkeypatch
):
    server, runtime, fake = make_server(tmp_path, monkeypatch)
    receipt = {
        **DONE,
        "artifacts": {"stdout": "/private/fixture-output"},
        "attempt_count": 2,
        "content": "original result",
        "page": {"next_offset": 10},
    }
    fake.responses["job.result"] = receipt
    review = call(
        server, "context.compose", {"intent": "job.review", "job": {"task_id": 41}}
    )
    assert review["result"]["outcome"] == "ok", review
    assert review["data"]["components"][0]["data"]["data"] == receipt
    assert [entry.operation for entry in fake.calls] == ["job.result"]
    observed = {
        "available": True,
        "gaps": ["history unavailable"],
        "live_pressure": {"memory": 1},
    }
    monkeypatch.setattr(runtime.observe, "machine_query", lambda operation: observed)
    incident = call(
        server,
        "context.compose",
        {"intent": "incident", "project": {"project": "fixture"}},
    )
    assert incident["result"]["outcome"] == "ok", incident
    assert incident["data"]["components"][0]["data"]["data"] == observed


@pytest.mark.parametrize("target", [{"task_id": 41}, {"ref": "sinnix://jobs/41"}])
def test_job_review_follows_launch_identity_across_reorders(
    tmp_path, monkeypatch, target
):
    server, _, fake = make_server(tmp_path, monkeypatch)
    job_id = "fixture-worker-original"

    def observe(args):
        assert args["job_id"] == job_id
        return {
            **DONE,
            "task_id": "43",
            "job_id": job_id,
            "content": "original output",
        }

    fake.responses["job.result"] = observe
    response = call(
        server,
        "context.compose",
        {"intent": "job.review", "job": {**target, "job_id": job_id}},
    )
    assert response["result"]["outcome"] == "ok", response
    assert response["data"]["ref"] == "sinnix://jobs/43"
    assert (
        response["data"]["components"][0]["data"]["data"]["content"]
        == "original output"
    )


def test_job_review_rejects_another_launch(tmp_path, monkeypatch):
    server, _, fake = make_server(tmp_path, monkeypatch)
    fake.responses["job.result"] = {
        **DONE,
        "job_id": "replacement",
        "content": "wrong output",
    }
    response = call(
        server,
        "context.compose",
        {"intent": "job.review", "job": {"task_id": 41, "job_id": "original"}},
    )
    assert response["result"]["outcome"] == "error"
    assert "wrong output" not in str(response)


def test_oversized_orientation_uses_owner_projection_and_retains_exact_snapshot(
    tmp_path, monkeypatch
):
    import json
    from functools import partial

    import test_actions_jobs
    from sinnix_agent_gateway.config import GatewayConfig
    from sinnix_agent_gateway.contexts import canonical_bytes

    monkeypatch.setattr(
        test_actions_jobs,
        "GatewayConfig",
        partial(GatewayConfig, max_result_bytes=16384),
    )
    server, runtime, _ = make_server(tmp_path, monkeypatch, with_git=True)
    projection = {
        "product": "project_context_compact",
        "outcome": "partial",
        "components": [
            {
                "name": "tasks",
                "status": "available",
                "full_data_pointer": "/components/0/data",
                "sections": {
                    "work": {
                        "items": [{"id": "fixture-1"}],
                        "observed_count": 100,
                        "omitted_count": 99,
                    }
                },
            }
        ],
    }
    product = {
        "outcome": "partial",
        "components": [
            {"name": "tasks", "data": {"description": "original bytes " * 20000}}
        ],
        "presentation": projection,
    }
    runtime.mcp_broker = Broker({"ok": True, "data": product})
    response = call(
        server,
        "context.compose",
        {"intent": "project.trajectory", "project": {"project": "fixture"}},
    )
    assert response["result"]["outcome"] == "ok", response
    value = response["data"]
    assert "truncated" not in value
    assert len(canonical_bytes(value)) <= 16384 - 4096
    assert len(json.dumps(response, ensure_ascii=False).encode()) <= 16384
    component = value["components"][0]
    assert component["presentation"] == "compact"
    assert component["data"]["data"] == projection
    assert value["availability"] == "degraded"
    assert runtime.mcp_broker.calls[0][2]["budget_bytes"] == 8192
    saved = runtime.results.read(value["snapshot_ref"].rsplit("/", 1)[1])["rows"][0]
    assert saved["components"][0]["data"]["data"] == product
    # Retrieve the same immutable observation through the public route.
    from sinnix_agent_gateway import server as server_module
    from sinnix_agent_gateway.actions import audit
    from test_actions_jobs import OWNED

    monkeypatch.setattr(server_module, "ALL_ACTIONS", (*OWNED, *audit.ACTIONS))
    from sinnix_agent_gateway.app import create_server

    server = create_server(runtime.config)
    page = call(server, "results.get", {"ref": value["snapshot_ref"]})
    assert page["result"]["outcome"] == "ok", page


@pytest.mark.parametrize(
    "presentation",
    [
        None,
        {
            "product": "project_context_compact",
            "outcome": "unavailable",
            "components": [],
        },
    ],
)
def test_unusable_oversized_orientation_is_explicitly_unavailable(
    tmp_path, monkeypatch, presentation
):
    server, runtime, _ = make_server(tmp_path, monkeypatch, with_git=True)
    product = {"components": [{"data": "界" * 200000}], "presentation": presentation}
    runtime.mcp_broker = Broker({"ok": True, "data": product})
    response = call(
        server,
        "context.compose",
        {"intent": "project.trajectory", "project": {"project": "fixture"}},
    )
    assert response["result"]["outcome"] == "ok", response
    assert response["data"]["availability"] == "unavailable"
    component = response["data"]["components"][0]
    assert component["status"] == "unavailable"
    assert component["presentation"] == "unavailable"
    assert component["inline_omitted"]
    assert component["data"] is None
    saved = runtime.results.read(response["data"]["snapshot_ref"].rsplit("/", 1)[1])[
        "rows"
    ][0]
    assert saved["components"][0]["status"] == "available"
    assert saved["components"][0]["data"]["data"] == product


def test_projects_context_preserves_native_components_and_bounds_large_pages(
    tmp_path, monkeypatch
):
    from functools import partial

    import test_actions_jobs
    from sinnix_agent_gateway import server as server_module
    from sinnix_agent_gateway.actions import projects
    from sinnix_agent_gateway.app import create_server
    from sinnix_agent_gateway.config import GatewayConfig
    from sinnix_agent_gateway.contexts import canonical_bytes
    from test_actions_jobs import OWNED

    monkeypatch.setattr(
        test_actions_jobs,
        "GatewayConfig",
        partial(GatewayConfig, max_result_bytes=16384),
    )
    _, runtime, jobs = make_server(tmp_path, monkeypatch, with_git=True)
    monkeypatch.setattr(
        runtime.beads,
        "task_authority_status",
        lambda project: {"revision": "tasks", "summary": {"total_issues": 2}},
    )
    jobs.responses["job.list"] = {
        "jobs": [{"output": "界" * 100000}],
        "truncated": False,
    }
    runtime.mcp_broker = Broker(failure=True)
    monkeypatch.setattr(server_module, "ALL_ACTIONS", (*OWNED, *projects.ACTIONS))
    server = create_server(runtime.config)
    response = call(server, "projects.context", {"target": {"project": "fixture"}})
    assert response["result"]["outcome"] == "ok", response
    value = response["data"]
    assert value["availability"] == "degraded"
    parts = {part["name"]: part for part in value["components"]}
    assert parts["git"]["status"] == "available"
    assert parts["agentctl"]["inline_omitted"]
    assert parts["agentctl"]["data"] is None
    saved = runtime.results.read(value["snapshot_ref"].rsplit("/", 1)[1])["rows"][0]
    assert saved["components"][2]["data"]["jobs"][0]["output"] == "界" * 100000
    assert value["project_id"] == "fixture"
    assert len(canonical_bytes(value)) <= 16384 - 4096
    assert not runtime.mcp_broker.calls


@pytest.mark.parametrize("available", [True, False])
def test_oversized_context_metadata_spills_complete_original_without_refusal(
    tmp_path, monkeypatch, available
):
    import base64
    import hashlib
    import json
    from functools import partial

    import test_actions_jobs
    from sinnix_agent_gateway.config import GatewayConfig

    monkeypatch.setattr(
        test_actions_jobs,
        "GatewayConfig",
        partial(GatewayConfig, max_result_bytes=16384),
    )
    server, runtime, _ = make_server(tmp_path, monkeypatch, with_git=True)
    reason = "complete metadata 界" * 2000
    observation = {
        "available": available,
        "reason": reason,
        "coverage": {"complete": False},
    }
    monkeypatch.setattr(runtime.observe, "machine_query", lambda operation: observation)
    response = call(
        server,
        "context.compose",
        {"intent": "incident", "project": {"project": "fixture"}},
    )
    assert response["result"]["outcome"] == "ok", response
    assert len(json.dumps(response, ensure_ascii=False).encode()) <= 16384
    artifact = response["data"]["artifact"]
    chunks = []
    offset = 0
    while offset is not None:
        page = runtime.artifacts.read(
            artifact["artifact_id"], offset=offset, max_bytes=4096
        )
        chunks.append(base64.b64decode(page["base64"]))
        offset = page["next_offset"]
    original = b"".join(chunks)
    assert hashlib.sha256(original).hexdigest() == page["sha256"]
    assert len(original) == artifact["bytes"]
    restored = json.loads(original)
    assert restored["availability"] == ("available" if available else "unavailable")
    assert restored["components"][0]["reason"] == reason
    assert restored["components"][0]["data"]["data"] == observation
    saved = runtime.results.read(restored["snapshot_ref"].rsplit("/", 1)[1])["rows"][0]
    assert saved["components"][0]["reason"] == reason


@pytest.mark.parametrize("kind", ["native", "model", "dataclass", "date"])
def test_presentation_size_preserves_typed_defaults_and_any_serialization(kind):
    from dataclasses import dataclass
    from datetime import date

    from pydantic import BaseModel
    from sinnix_agent_gateway.actions.contexts import (
        ComposedContext,
        _presentation_size,
    )
    from sinnix_agent_gateway.contexts import canonical_bytes

    class Model(BaseModel):
        label: str

    @dataclass
    class Record:
        label: str

    data = {
        "native": {"rows": ["界", (True, None)]},
        "model": Model(label="界"),
        "dataclass": Record(label="界"),
        "date": date(2026, 1, 1),
    }[kind]
    context = {
        "ref": "fixture",
        "intent": "project.overview",
        "target_ref": "fixture",
        "snapshot_ref": "snapshot",
        "total_budget_bytes": 4096,
        "components": [
            {
                "name": "fixture",
                "status": "available",
                "snapshot_ref": "snapshot",
                "data": data,
            }
        ],
    }
    expected = len(
        canonical_bytes(ComposedContext.model_validate(context).model_dump())
    )
    assert _presentation_size(context) == expected


def test_context_budget_does_not_copy_complete_native_owner_tree():
    import tracemalloc

    from sinnix_agent_gateway.actions.contexts import _within_budget

    data = {"rows": ["x" * 64] * 100000}
    context = {
        "ref": "fixture",
        "intent": "project.overview",
        "target_ref": "fixture",
        "snapshot_ref": "snapshot",
        "total_budget_bytes": 4096,
        "components": [
            {
                "name": "fixture",
                "status": "available",
                "snapshot_ref": "snapshot",
                "data": data,
            }
        ],
    }
    tracemalloc.start()
    try:
        result = _within_budget(context)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 1_000_000
    assert result["components"][0]["inline_omitted"]
    assert context["components"][0]["data"] is data
    assert len(data["rows"]) == 100000


@pytest.mark.parametrize("intent", ["project.overview", "project.triage"])
def test_live_project_context_reads_native_owners_without_lynchpin(
    tmp_path, monkeypatch, intent
):
    server, runtime, jobs = make_server(tmp_path, monkeypatch, with_git=True)
    runtime.mcp_broker = Broker(failure=True)
    monkeypatch.setattr(
        runtime.beads,
        "task_authority_status",
        lambda project: {
            "project_id": project,
            "revision": "current-tasks",
            "summary": {"total_issues": 2},
            "attested": True,
        },
    )
    jobs.responses["job.list"] = {
        "jobs": [],
        "snapshot": {"source_revision": "queue-position"},
        "truncated": False,
    }
    response = call(
        server, "context.compose", {"intent": intent, "project": {"project": "fixture"}}
    )
    assert response["result"]["outcome"] == "ok", response
    value = response["data"]
    assert value["availability"] == "available"
    assert value["context_schema"] == "sinnix.native-project-context.v1"
    parts = {part["name"]: part for part in value["components"]}
    assert parts["beads"]["source_revision"] == "current-tasks"
    assert parts["agentctl"]["source_revision"] == "queue-position"
    assert parts["git"]["data"]["latest_commit"]["id"]
    assert parts["polylogue"]["coverage"]["requested"] is False
    assert not runtime.mcp_broker.calls
    snapshot = runtime.results.read(value["snapshot_ref"].rsplit("/", 1)[1])["rows"][0]
    assert snapshot["components"][1]["data"] == parts["beads"]["data"]


def test_native_context_preserves_available_code_when_tasks_fail(tmp_path, monkeypatch):
    from sinnix_agent_gateway.beads import BeadsError

    server, runtime, jobs = make_server(tmp_path, monkeypatch, with_git=True)

    def unavailable(project):
        raise BeadsError("task authority unavailable")

    monkeypatch.setattr(runtime.beads, "task_authority_status", unavailable)
    jobs.responses["job.list"] = {"jobs": [], "truncated": False}
    response = call(
        server,
        "context.compose",
        {"intent": "project.overview", "project": {"project": "fixture"}},
    )
    value = response["data"]
    assert value["availability"] == "degraded", response
    parts = {part["name"]: part for part in value["components"]}
    assert parts["git"]["status"] == "available"
    assert parts["beads"]["status"] == "unavailable"
    assert parts["beads"]["source_revision"] is None
    assert parts["beads"]["coverage"]["complete"] is False
    assert "unavailable" in parts["beads"]["reason"]


@pytest.mark.parametrize("failure", [False, True])
def test_optional_status_keeps_native_position_and_global_coverage(
    tmp_path, monkeypatch, failure
):
    server, runtime, jobs = make_server(tmp_path, monkeypatch, with_git=True)
    monkeypatch.setattr(
        runtime.beads, "task_authority_status", lambda project: {"revision": "tasks"}
    )
    jobs.responses["job.list"] = {"jobs": [], "truncated": False}
    runtime.mcp_broker = Broker(
        {"commit_seq": 42, "search_index": {"position": 40, "behind": 2}},
        failure=failure,
    )
    response = call(
        server,
        "context.compose",
        {
            "intent": "project.overview",
            "project": {"project": "fixture"},
            "evidence": ["sinex"],
        },
    )
    part = next(p for p in response["data"]["components"] if p["name"] == "sinex")
    if failure:
        assert response["data"]["availability"] == "degraded"
        assert part["status"] == "unavailable"
        assert part["source_revision"] is None
        assert part["coverage"]["requested"] is True
        assert "unavailable" in part["reason"]
        return
    assert part["source_revision"] == "42"
    assert part["revision_kind"] == "owner"
    assert "global" in part["coverage"]["scope"]
    assert part["data"]["data"]["search_index"]["behind"] == 2
    assert part["observed_at"]
    assert [call[:2] for call in runtime.mcp_broker.calls] == [
        ("sinex", "sinex_status")
    ]
