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
        ComposeInput.model_validate({"intent": "incident", "job": {"job_id": 1}})


@pytest.mark.parametrize(
    "intent",
    [
        "project.orientation",
        "project.triage",
        "project.trajectory",
        "verification.regression",
    ],
)
def test_project_context_preserves_owner_components_and_observes_each_time(
    tmp_path, monkeypatch, intent
):
    server, runtime, _ = make_server(tmp_path, "operator", monkeypatch, with_git=True)
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
    server, runtime, fake = make_server(tmp_path, "operator", monkeypatch)
    receipt = {
        **DONE,
        "artifacts": {"stdout": "/private/fixture-output"},
        "attempt_count": 2,
        "content": "original result",
        "page": {"next_offset": 10},
    }
    fake.responses["job.result"] = receipt
    review = call(
        server, "context.compose", {"intent": "job.review", "job": {"job_id": 41}}
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


@pytest.mark.parametrize("target", [{"job_id": 41}, {"ref": "sinnix://jobs/41"}])
def test_job_review_follows_launch_identity_across_reorders(
    tmp_path, monkeypatch, target
):
    server, _, fake = make_server(tmp_path, "operator", monkeypatch)
    reference = "fixture-worker-original"

    def observe(args):
        assert args["launch_reference"] == reference
        return {
            **DONE,
            "job_id": "43",
            "launch_reference": reference,
            "content": "original output",
        }

    fake.responses["job.result"] = observe
    response = call(
        server,
        "context.compose",
        {"intent": "job.review", "job": {**target, "launch_reference": reference}},
    )
    assert response["result"]["outcome"] == "ok", response
    assert response["data"]["ref"] == "sinnix://jobs/43"
    assert (
        response["data"]["components"][0]["data"]["data"]["content"]
        == "original output"
    )


def test_job_review_rejects_another_launch(tmp_path, monkeypatch):
    server, _, fake = make_server(tmp_path, "operator", monkeypatch)
    fake.responses["job.result"] = {
        **DONE,
        "launch_reference": "replacement",
        "content": "wrong output",
    }
    response = call(
        server,
        "context.compose",
        {"intent": "job.review", "job": {"job_id": 41, "launch_reference": "original"}},
    )
    assert response["result"]["outcome"] == "error"
    assert "wrong output" not in str(response)


def test_oversized_orientation_uses_owner_projection_and_retains_exact_snapshot(tmp_path, monkeypatch):
    import json
    from sinnix_agent_gateway.contexts import canonical_bytes
    from functools import partial
    import test_actions_jobs
    from sinnix_agent_gateway.config import GatewayConfig
    monkeypatch.setattr(test_actions_jobs, "GatewayConfig", partial(GatewayConfig, max_result_bytes=16384))
    server, runtime, _ = make_server(tmp_path, "operator", monkeypatch, with_git=True)
    projection = {"product": "project_context_compact", "outcome": "partial", "components": [{"name": "tasks", "status": "available", "full_data_pointer": "/components/0/data", "sections": {"work": {"items": [{"id": "fixture-1"}], "observed_count": 100, "omitted_count": 99}}}]}
    product = {"outcome": "partial", "components": [{"name": "tasks", "data": {"description": "original bytes " * 20000}}], "presentation": projection}
    runtime.mcp_broker = Broker({"ok": True, "data": product})
    response = call(server, "context.compose", {"intent": "project.orientation", "project": {"project": "fixture"}})
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
    from sinnix_agent_gateway.actions import audit
    from sinnix_agent_gateway import server as server_module
    from test_actions_jobs import OWNED
    monkeypatch.setattr(server_module, "visible_actions", lambda principal: (*OWNED, *audit.ACTIONS))
    from sinnix_agent_gateway.app import create_server
    server = create_server(runtime.config, "operator")
    page = call(server, "results.get", {"ref": value["snapshot_ref"]})
    assert page["result"]["outcome"] == "ok", page


@pytest.mark.parametrize("presentation", [None, {"product": "project_context_compact", "outcome": "unavailable", "components": []}])
def test_unusable_oversized_orientation_is_explicitly_unavailable(tmp_path, monkeypatch, presentation):
    server, runtime, _ = make_server(tmp_path, "operator", monkeypatch, with_git=True)
    product = {"components": [{"data": "界" * 200000}], "presentation": presentation}
    runtime.mcp_broker = Broker({"ok": True, "data": product})
    response = call(server, "context.compose", {"intent": "project.orientation", "project": {"project": "fixture"}})
    assert response["result"]["outcome"] == "ok", response
    assert response["data"]["availability"] == "unavailable"
    component = response["data"]["components"][0]
    assert component["status"] == "unavailable"
    assert component["presentation"] == "unavailable"
    assert component["inline_omitted"]
    assert component["data"] is None
    saved = runtime.results.read(response["data"]["snapshot_ref"].rsplit("/", 1)[1])["rows"][0]
    assert saved["components"][0]["status"] == "available"
    assert saved["components"][0]["data"]["data"] == product


def test_projects_context_uses_the_same_compact_component_contract(tmp_path, monkeypatch):
    from sinnix_agent_gateway.actions import projects
    from sinnix_agent_gateway import server as server_module
    from sinnix_agent_gateway.app import create_server
    from test_actions_jobs import OWNED
    _, runtime, _ = make_server(tmp_path, "operator", monkeypatch, with_git=True)
    projection = {"product": "project_context_compact", "outcome": "partial", "components": [{"name": "tasks", "status": "available", "sections": {"work": {"items": [{"id": "fixture-1"}], "observed_count": 1, "omitted_count": 0}}}]}
    runtime.mcp_broker = Broker({"ok": True, "data": {"outcome": "partial", "evidence": "fixture" * 100000, "presentation": projection}})
    monkeypatch.setattr(server_module, "visible_actions", lambda principal: (*OWNED, *projects.ACTIONS))
    server = create_server(runtime.config, "operator")
    response = call(server, "projects.context", {"target": {"project": "fixture"}})
    assert response["result"]["outcome"] == "ok", response
    value = response["data"]
    assert value["availability"] == "degraded"
    assert value["components"][0]["presentation"] == "compact"
    assert value["components"][0]["full_product_pointer"] == "/components/0/data/data"
    assert value["components"][0]["data"]["data"] == projection
    assert value["project_id"] == "fixture"


def test_project_wrapper_metadata_cannot_hide_orientation_in_an_artifact(tmp_path, monkeypatch):
    from functools import partial
    import test_actions_jobs
    from sinnix_agent_gateway.config import GatewayConfig
    from sinnix_agent_gateway.actions import projects
    from sinnix_agent_gateway import server as server_module
    from sinnix_agent_gateway.app import create_server
    from sinnix_agent_gateway.contexts import canonical_bytes
    from test_actions_jobs import OWNED
    monkeypatch.setattr(test_actions_jobs, "GatewayConfig", partial(GatewayConfig, max_result_bytes=16384))
    _, runtime, _ = make_server(tmp_path, "operator", monkeypatch, with_git=True)
    projection = {"product": "project_context_compact", "outcome": "ok", "components": [{"name": "tasks", "status": "available"}]}
    product = {"outcome": "ok", "evidence": "", "presentation": projection}
    runtime.mcp_broker = Broker({"ok": True, "data": product})
    monkeypatch.setattr(server_module, "visible_actions", lambda principal: (*OWNED, *projects.ACTIONS))
    server = create_server(runtime.config, "operator")
    arguments = {"intent": "project.orientation", "project": {"project": "fixture"}}
    initial = call(server, "context.compose", arguments)
    assert initial["result"]["outcome"] == "ok", initial
    product["evidence"] = "x" * (16384 - 4096 - len(canonical_bytes(initial["data"])) - 16)
    composed = call(server, "context.compose", arguments)
    assert composed["data"]["components"][0]["presentation"] == "full"
    response = call(server, "projects.context", {"target": {"project": "fixture"}})
    assert response["result"]["outcome"] == "ok", response
    assert "truncated" not in response["data"]
    assert response["data"]["components"][0]["presentation"] == "compact"
    assert len(canonical_bytes(response["data"])) <= 16384 - 4096
