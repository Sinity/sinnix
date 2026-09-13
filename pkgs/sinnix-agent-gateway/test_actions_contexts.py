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
    server, runtime, _ = make_server(tmp_path, "observer", monkeypatch, with_git=True)
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
