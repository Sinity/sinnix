from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.actions import activity, batches, contexts, jobs, products
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.execution import job_payload, worker_payload
from sinnix_agent_gateway.mcp_broker import McpBrokerError
from test_actions_jobs import DONE, RUNNING, call, make_server


class Broker:
    def __init__(self, data=None, failure=False):
        self.data = data or {
            "version": 1,
            "usage": {"tokens": None},
            "coverage": {"complete": False},
        }
        self.failure = failure
        self.calls = []

    async def owner_result(self, owner, tool, arguments, **kwargs):
        self.calls.append((owner, tool, arguments, kwargs))
        if self.failure:
            raise McpBrokerError("owner unavailable")
        return {"structuredContent": self.data}


@pytest.mark.parametrize(
    "owner_data",
    [
        {"sessions": [], "coverage": {"complete": False}},
        {"ok": False, "status": "error", "message": "archive unavailable"},
    ],
)
def test_owner_string_return_is_decoded_from_sdk_structured_wrapper(
    tmp_path, monkeypatch, owner_data
):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker({"result": json.dumps(owner_data)})
    result = anyio.run(
        products._orchestration,
        runtime,
        products.OrchestrationInput(session_refs=["session:a"]),
    )
    product = result.sessions[0]
    assert product.data == owner_data
    assert product.availability == (
        "unavailable" if owner_data.get("ok") is False else "available"
    )
    if owner_data.get("ok") is False:
        assert product.reason == "archive unavailable"


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
    assert broker.calls[0][2] == {
        "projection": "session-operations",
        "session_operation": {
            "operation": "sessions.orchestration",
            "ref": "session:a",
        },
    }


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


def test_campaign_owner_acquires_history_and_preserves_incomplete_scope(
    tmp_path, monkeypatch
):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    owner = {
        "closure": {
            "nodes": [{"id": "fixture-1", "status": "closed"}],
            "complete": False,
        },
        "baseline": {"temporal": {"resolved_revision": "older"}},
        "scope_delta": {"closed": ["fixture-1"], "complete": False},
        "items": [{"task_status": "closed", "evidence_state": "unknown"}],
    }
    runtime.mcp_broker = Broker(
        {"ok": True, "data": owner, "meta": {"owner": "lynchpin"}}
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
    assert result.product.data == owner
    assert runtime.mcp_broker.calls[0][2] == {
        "action": "campaign_progress",
        "project": "fixture",
        "roots": ["fixture-1"],
        "at": "newer",
        "baseline": "older",
        "relation": "blocks",
        "direction": "prerequisites",
        "max_nodes": 500,
        "max_depth": 50,
    }
    assert len(runtime.mcp_broker.calls) == 1


def test_structured_sessions_use_native_owner_pagination(tmp_path, monkeypatch):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker(
        {"items": [], "continuation": "owner-next", "coverage": {"complete": False}}
    )
    result = anyio.run(
        activity._sessions,
        runtime,
        activity.SessionsInput(
            request={
                "operation": "sessions.search",
                "expression": "late match",
                "limit": 3,
            }
        ),
    )
    assert result.data.owner_product.data["continuation"] == "owner-next"
    sent = runtime.mcp_broker.calls[0][2]["session_operation"]
    assert sent["operation"] == "sessions.search"
    assert sent["expression"] == "late match"
    assert sent["limit"] == 3


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
        runtime.results.read(result.snapshot_ref.rsplit("/", 1)[1])["rows"][0]["intent"]
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
        "action": "project_context",
        "intent": intent,
        "project": "fixture",
        "roots": [],
        "at": None,
        "refresh_id": "fixture-generation",
    }
    component = result.components[0]
    # `partial` is a named gap, not an available answer: flattening it to
    # `available` is what let a gap-shaped context reach a caller as
    # authoritative. Breaks if the gateway's unavailability set goes back to
    # deciding only reachable/unreachable.
    assert component.status == ("degraded" if outcome == "partial" else "unavailable")
    if outcome == "partial":
        assert component.data["data"] == owner_data
        assert component.data["data"]["counts"]["exact"] is None
    assert (
        runtime.results.read(result.snapshot_ref.rsplit("/", 1)[1])["rows"][0]["intent"]
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


# ---------------------------------------------------------------- four states
#
# The owner decides its terminal outcome once, in {ok, empty, degraded,
# error}, with `degraded` outranking `empty` so zero rows behind a named gap
# is never reported as an empty scope. Each test below breaks if the gateway
# goes back to a two-state unavailability set: both `degraded` and `empty`
# then fall through to `available` and the distinction is erased at the
# boundary the owner drew it for.


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("ok", "available"),
        ("empty", "empty"),
        ("degraded", "degraded"),
        ("error", "unavailable"),
    ],
)
def test_an_owner_terminal_outcome_survives_the_gateway(
    tmp_path, monkeypatch, state, expected
):
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker(
        {
            "sessions": [],
            "outcome": {"state": state, "reason": "retained history is incomplete"},
        }
    )
    result = anyio.run(
        products._orchestration,
        runtime,
        products.OrchestrationInput(session_refs=["session:a"]),
    )
    product = result.sessions[0]
    assert product.availability == expected
    if expected != "available":
        assert product.reason == "retained history is incomplete"


def test_zero_rows_without_a_declared_outcome_are_not_inferred_empty(
    tmp_path, monkeypatch
):
    """The gateway reads the owner's decision; it never makes one from the shape
    of the payload. Breaks if `empty` starts being inferred from an absent row
    set, which is what makes a broken owner surface indistinguishable from an
    owner whose scope really holds nothing."""
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker({"sessions": [], "coverage": {"complete": True}})
    result = anyio.run(
        products._orchestration,
        runtime,
        products.OrchestrationInput(session_refs=["session:a"]),
    )
    assert result.sessions[0].availability == "available"


def test_component_failures_are_carried_and_make_the_answer_degraded(
    tmp_path, monkeypatch
):
    """Polylogue's ContextPreamble carries `component_failures` and no outcome
    field at all, so named per-component gaps are its only gap signal. Breaks if
    the gateway drops them: a context assembled from a failed lineage lookup
    reaches the caller labelled available, with nothing naming what is missing."""
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    failures = {"session_lineage": "TimeoutError: lineage lookup timed out"}
    runtime.mcp_broker = Broker(
        {"recent_related_sessions": [], "component_failures": failures}
    )
    result = anyio.run(
        products._orchestration,
        runtime,
        products.OrchestrationInput(session_refs=["session:a"]),
    )
    product = result.sessions[0]
    assert product.availability == "degraded"
    assert product.component_failures == failures
    assert "session_lineage" in (product.reason or "")


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        ((), "empty"),
        (("available", "available"), "available"),
        (("empty", "empty"), "empty"),
        (("available", "empty"), "available"),
        (("available", "degraded"), "degraded"),
        (("empty", "degraded"), "degraded"),
        (("available", "unavailable"), "degraded"),
        (("empty", "unavailable"), "degraded"),
        (("unavailable", "unavailable"), "unavailable"),
    ],
)
def test_a_composite_keeps_its_worst_part(parts, expected):
    """A composite is only as honest as its worst part. Breaks if composition
    goes back to `any(part == "available")`, which reports a whole context as
    available on the strength of one part that answered."""
    assert products.combine_availability(list(parts)) == expected


def test_a_composed_context_carries_the_owner_state_and_its_failures(
    tmp_path, monkeypatch
):
    """The composed context is where the erased label was observed. Breaks if
    `_compose` stops propagating the product's state or its component failures
    into the returned component."""
    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    failures = {"assertion_guidance": "OperationalError: database is locked"}
    runtime.mcp_broker = Broker(
        {"sessions": [], "component_failures": failures, "outcome": {"state": "empty"}}
    )
    result = anyio.run(
        contexts._compose,
        runtime,
        contexts.ComposeInput(
            intent="session.orchestration",
            project={"project": "fixture"},
            session_refs=["session:a"],
        ),
    )
    component = result.components[0]
    assert component.status == "degraded"
    assert component.component_failures == failures


def test_a_composed_context_is_held_to_the_budget_it_declares(tmp_path, monkeypatch):
    """`total_budget_bytes` was declared and never enforced, which is why a
    262 KB budget returned a 4 MB result. Breaks if the bound is removed: the
    returned envelope exceeds the number it reports as its own budget."""
    import dataclasses

    _, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.config = dataclasses.replace(runtime.config, max_result_bytes=4_096)
    payload = {"sessions": [], "evidence": "x" * 64_000}
    runtime.mcp_broker = Broker(payload)
    result = anyio.run(
        contexts._compose,
        runtime,
        contexts.ComposeInput(
            intent="session.orchestration",
            project={"project": "fixture"},
            session_refs=["session:a"],
        ),
    )
    assert result.total_budget_bytes == 4_096
    assert len(result.model_dump_json().encode()) <= 4_096
    assert result.components[0].inline_omitted is True
    assert result.components[0].data is None
    # The complete observation is still readable at the snapshot ref: bounding
    # the in-band copy must not lose the evidence.
    snapshot = runtime.results.read(result.snapshot_ref.rsplit("/", 1)[1])
    assert (
        snapshot["rows"][0]["components"][0]["data"]["data"]["sessions"][0]["data"]
        == payload
    )
