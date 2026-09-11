from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest

from sinnix_agent_gateway.actions import contexts, products, activity
from sinnix_agent_gateway.actions import jobs, batches
from sinnix_agent_gateway.execution import job_payload, worker_payload
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.mcp_broker import McpBrokerError
from test_actions_jobs import make_server, call, DONE, RUNNING


class Broker:
    def __init__(self, data=None, failure=False):
        self.data = data or {
            "version": 1,
            "usage": {"tokens": None},
            "coverage": {"complete": False},
        }
        self.failure = failure
        self.calls = []

    async def call(self, owner, tool, arguments, **kwargs):
        self.calls.append((owner, tool, arguments, kwargs))
        if self.failure:
            raise McpBrokerError("owner unavailable")
        return {"response": {"structuredContent": self.data}}


def test_runtime_projection_keeps_requested_and_observed_evidence_separate():
    projection = {
        "dispatch": {"requested": {"model": "fixture-model"}, "attempt": 2},
        "actual_executor_model": None,
        "measured_usage": None,
    }
    worker = batches._worker_view(
        "fixture",
        worker_payload(
            {
                "id": "worker-1",
                "provenance": projection,
                "attempts": [{"number": 1}],
                "task": {"dependencies": [7]},
            }
        ),
    )
    assert worker.provenance == projection
    assert worker.attempts == [{"number": 1}]
    assert worker.state.dependencies == [7]
    job = jobs._job_view(
        job_payload(
            {
                "job_id": 1,
                "project": "fixture",
                "dependencies": [7],
                "binding": {
                    "beads": ["fixture-1"],
                    "execution": "external",
                    "requested": {"model": "fixture-model"},
                    "attempt": 2,
                },
            }
        )
    )
    assert job.state.dependencies == [7]
    assert job.binding.execution == "external"
    assert job.binding.attempt == 2


def test_orchestration_preserves_unknown_usage_and_deduplicates(tmp_path, monkeypatch):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    broker = Broker()
    runtime.mcp_broker = broker
    result = anyio.run(
        products._orchestration,
        runtime,
        products.OrchestrationInput(session_refs=["session:a", "session:a"]),
    )
    assert len(result.sessions) == 1
    assert result.sessions[0].data["usage"]["tokens"] is None
    assert broker.calls[0][2] == {"ref": "session:a", "projection": "orchestration"}


def test_mcp_product_response_is_a_principal_scoped_immutable_result(
    tmp_path, monkeypatch
):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker()
    monkeypatch.setattr(
        server_module, "visible_actions", lambda principal: products.ACTIONS
    )
    server = create_server(runtime.config, "observer")
    response = call(server, "sessions.orchestration", {"session_refs": ["session:a"]})
    assert response["result"]["outcome"] == "ok", response
    assert response["result"]["principal"] == "observer"
    snapshot = runtime.results.read(response["result"]["result_id"])
    assert snapshot["data"] == response["data"]
    runtime.mcp_broker.data["usage"]["tokens"] = 500
    assert (
        runtime.results.read(response["result"]["result_id"])["data"]["sessions"][0][
            "data"
        ]["usage"]["tokens"]
        is None
    )


@pytest.mark.parametrize(
    "data",
    [
        {"outcome": "error", "error": "unsupported"},
        {"available": False},
        {"availability": "unavailable"},
        {"outcome": {"state": "error"}},
        {"ok": False, "status": "error", "message": "unsupported"},
    ],
)
def test_owner_refusal_is_unavailable(tmp_path, monkeypatch, data):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker(data)
    result = anyio.run(
        products._orchestration,
        runtime,
        products.OrchestrationInput(session_refs=["session:a"]),
    )
    assert result.sessions[0].availability == "unavailable"
    assert result.sessions[0].data == data


def test_campaign_joins_selected_history_and_keeps_incomplete_scope(
    tmp_path, monkeypatch
):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    calls = []

    def closure(**arguments):
        calls.append(arguments)
        old = arguments["at"] == "older"
        return {
            "nodes": [{"id": "fixture-1", "status": "open" if old else "closed"}],
            "complete": old,
            "provenance_edges": [
                {"from": "fixture-2", "to": "fixture-1", "relation": "split_from"}
            ],
            "provenance_coverage": {
                "complete": old,
                "state": "complete" if old else "bounded",
            },
            "temporal": {"resolved_revision": arguments["at"], "known_at": None},
        }

    runtime.beads = SimpleNamespace(campaign_closure=closure)
    runtime.mcp_broker = Broker(
        {"items": [{"task_status": "closed", "evidence_state": "unknown"}]}
    )
    result = anyio.run(
        products._campaign,
        runtime,
        products.CampaignInput(
            project={"project": "fixture"},
            roots=["fixture-1"],
            at={"revision": "newer"},
            baseline={"revision": "older"},
        ),
    )
    assert [row["at"] for row in calls] == ["newer", "older"]
    assert result.scope_delta["closed"] == ["fixture-1"]
    assert result.scope_delta["complete"] is False
    sent = runtime.mcp_broker.calls[0][2]
    assert sent["bead_refs"] == ["sinnix://projects/fixture/beads/fixture-1"]
    assert sent["task_snapshot"]["temporal"]["resolved_revision"] == "newer"
    assert (
        sent["task_snapshot"]["provenance_edges"] == result.closure["provenance_edges"]
    )
    assert sent["task_snapshot"]["provenance_coverage"]["complete"] is False
    accounting = runtime.mcp_broker.calls[1][2]
    assert accounting["action"] == "campaign_scope_delta"
    assert accounting["task_snapshot"] == result.closure
    assert accounting["baseline_snapshot"] == result.baseline
    assert result.evidence.data["items"][0]["evidence_state"] == "unknown"


def test_structured_sessions_do_not_use_legacy_file_search(tmp_path, monkeypatch):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker()
    runtime.sessions = None
    result = anyio.run(
        activity._sessions,
        runtime,
        activity.SessionsInput(
            request={"operation": "structured", "expression": "late match", "limit": 3}
        ),
    )
    assert result.data.provider == "polylogue"
    assert result.data.truncated is None
    assert runtime.mcp_broker.calls[0][2] == {
        "expression": "late match",
        "limit": 3,
        "projection": "sessions",
    }


def test_context_owner_failure_is_persisted_as_unavailable(tmp_path, monkeypatch):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker(failure=True)
    result = anyio.run(
        contexts._compose,
        runtime,
        contexts.ComposeInput(
            intent="verification.regression", project={"project": "fixture"}
        ),
    )
    assert result.components[0].status == "unavailable"
    assert (
        runtime.context_snapshots.get(result.snapshot_ref.rsplit("/", 1)[1])["intent"]
        == "verification.regression"
    )


@pytest.mark.parametrize("intent", ["verification.regression", "project.trajectory"])
@pytest.mark.parametrize("outcome", ["partial", "unavailable"])
def test_historical_context_owner_contract_preserves_partial_and_unknown(
    tmp_path, monkeypatch, intent, outcome
):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    owner_data = {
        "product": intent.replace(".", "_"),
        "outcome": outcome,
        "sources": {"agentctl": {"coverage": "retained_history"}},
        "temporal": {"known_at": None, "watermark": None},
        "counts": {"exact": None},
        "gaps": ["retained history is incomplete"],
    }
    runtime.mcp_broker = Broker(
        {"ok": True, "data": owner_data, "meta": {"source_mode": "owner_snapshots"}}
    )
    result = anyio.run(
        contexts._compose,
        runtime,
        contexts.ComposeInput(
            intent=intent,
            project={"project": "fixture"},
            refresh_id="fixture-generation",
        ),
    )
    sent = runtime.mcp_broker.calls[0][2]
    assert sent == {
        "action": intent.replace(".", "_"),
        "project": "fixture",
        "refresh_id": "fixture-generation",
    }
    component = result.components[0]
    assert component.status == ("available" if outcome == "partial" else "unavailable")
    if outcome == "partial":
        assert component.data == owner_data
        assert component.data["counts"]["exact"] is None
    assert (
        runtime.context_snapshots.get(result.snapshot_ref.rsplit("/", 1)[1])["intent"]
        == intent
    )


def test_lynchpin_envelope_preserves_metadata_and_inner_unavailability(
    tmp_path, monkeypatch
):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker(
        {
            "ok": True,
            "data": {"availability": "unavailable", "reason": "no retained history"},
            "meta": {"source_mode": "owner_snapshots"},
        }
    )

    async def invoke():
        return await products.owner_product(
            runtime, "lynchpin", "lynchpin_project", {"action": "project_trajectory"}
        )

    product = anyio.run(invoke)
    assert product.availability == "unavailable"
    assert product.reason == "no retained history"
    assert product.owner_metadata == {"source_mode": "owner_snapshots"}


@pytest.mark.parametrize("terminal", [False, True])
def test_shell_wait_preserves_job_identity_and_returns_output(
    tmp_path: Path, monkeypatch, terminal
):
    server, _, fake = make_server(tmp_path, "operator", monkeypatch, with_git=True)
    fake.responses["job.shell.start"] = {
        **RUNNING,
        "launch_reference": "fixture-shell-abc",
    }
    view = {
        **(DONE if terminal else RUNNING),
        "launch_reference": "fixture-shell-abc",
        "job_id": "44",
    }
    fake.responses["job.wait"] = {**view, "timed_out": not terminal}
    fake.responses["job.logs"] = {**view, "content": "output", "truncated": False}
    result = call(
        server,
        "shell.run",
        {
            "checkout": {"project": "fixture"},
            "argv": ["true"],
            "wait": True,
            "idempotency_key": "shell-wait",
        },
    )
    assert result["result"]["outcome"] == "ok", result
    data = result["data"]
    assert data["job_id"] == 44
    assert data["outcome"] == ("terminal" if terminal else "timeout")
    assert data["output"]["content"] == "output"
    wait_call = next(c for c in fake.calls if c.operation == "job.wait")
    assert wait_call.arguments["timeout_seconds"] == 5
    assert wait_call.arguments["launch_reference"] == "fixture-shell-abc"
    assert (data["continuation"] is None) is terminal
