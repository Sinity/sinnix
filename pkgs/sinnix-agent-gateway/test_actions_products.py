from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.actions import batches, contexts, jobs, products
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


async def owner_fixture(runtime, _input):
    return SimpleNamespace(
        product=await products.owner_product(
            runtime, "fixture-owner", "fixture-read", {}
        )
    )


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
    _, runtime, _ = make_server(tmp_path, monkeypatch)
    runtime.mcp_broker = Broker({"result": json.dumps(owner_data)})
    result = anyio.run(
        owner_fixture,
        runtime,
        products.CampaignInput(project={"project": "fixture"}, roots=["fixture-1"]),
    )
    product = result.product
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
                "task_id": 1,
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
    _, runtime, _ = make_server(tmp_path, monkeypatch)
    runtime.mcp_broker = Broker(data)
    result = anyio.run(
        owner_fixture,
        runtime,
        products.CampaignInput(project={"project": "fixture"}, roots=["fixture-1"]),
    )
    assert result.product.availability == "unavailable"
    assert result.product.data == data


def test_native_campaign_pins_history_without_current_job_evidence(
    tmp_path, monkeypatch
):
    _, runtime, fake = make_server(tmp_path, monkeypatch)
    calls = []

    def closure(project, roots, **kwargs):
        calls.append((project, roots, kwargs))
        return {
            "owner_product": {
                "revision": kwargs["at"],
                "closure": {"complete": False},
                "items": [
                    {
                        "id": "fixture-1",
                        "status": "closed",
                        "notes": "reported delivered",
                    }
                ],
            }
        }

    monkeypatch.setattr(runtime.beads, "campaign_closure", closure)
    runtime.mcp_broker = Broker(failure=True)
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
    assert [x[2]["at"] for x in calls] == ["newer", "older"]
    assert calls[0][2] == {
        "at": "newer",
        "relation": "blocks",
        "direction": "prerequisites",
        "max_nodes": 500,
        "max_depth": 50,
    }
    data = result.product.data
    assert (
        data["components"]["tasks"]["data"]["owner_product"]["items"][0]["status"]
        == "closed"
    )
    assert data["delivery"]["state"] == data["acceptance"]["state"] == "unknown"
    assert data["components"]["agentctl"]["status"] == "unavailable"
    assert not fake.calls and not runtime.mcp_broker.calls


@pytest.mark.parametrize("intent", ["verification.regression", "project.trajectory"])
def test_native_historical_context_refuses_without_explicit_task_scope(
    tmp_path, monkeypatch, intent
):
    from sinnix_agent_gateway.results import ProtocolError

    _, runtime, fake = make_server(tmp_path, monkeypatch)
    with pytest.raises(ProtocolError, match="historical selectors"):
        anyio.run(
            contexts._compose,
            runtime,
            contexts.ComposeInput(
                intent=intent, project={"project": "fixture"}, at={"revision": "older"}
            ),
        )
    assert not fake.calls


def test_lynchpin_envelope_preserves_metadata_and_inner_unavailability(
    tmp_path, monkeypatch
):
    _, runtime, _ = make_server(tmp_path, monkeypatch)
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
    server, _, fake = make_server(tmp_path, monkeypatch, with_git=True)
    fake.responses["job.shell.start"] = {
        **RUNNING,
        "job_id": "fixture-shell-abc",
    }
    view = {
        **(DONE if terminal else RUNNING),
        "job_id": "fixture-shell-abc",
        "task_id": "44",
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
    assert data["task_id"] == 44
    assert data["outcome"] == ("terminal" if terminal else "running")
    assert data["output"]["content"] == "output"
    wait_call = next(c for c in fake.calls if c.operation == "job.wait")
    assert wait_call.arguments["timeout_seconds"] == 5
    assert wait_call.arguments["job_id"] == "fixture-shell-abc"
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
    _, runtime, _ = make_server(tmp_path, monkeypatch)
    runtime.mcp_broker = Broker(
        {
            "sessions": [],
            "outcome": {"state": state, "reason": "retained history is incomplete"},
        }
    )
    result = anyio.run(
        owner_fixture,
        runtime,
        products.CampaignInput(project={"project": "fixture"}, roots=["fixture-1"]),
    )
    product = result.product
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
    _, runtime, _ = make_server(tmp_path, monkeypatch)
    runtime.mcp_broker = Broker({"sessions": [], "coverage": {"complete": True}})
    result = anyio.run(
        owner_fixture,
        runtime,
        products.CampaignInput(project={"project": "fixture"}, roots=["fixture-1"]),
    )
    assert result.product.availability == "available"


def test_component_failures_are_carried_and_make_the_answer_degraded(
    tmp_path, monkeypatch
):
    """Polylogue's ContextPreamble carries `component_failures` and no outcome
    field at all, so named per-component gaps are its only gap signal. Breaks if
    the gateway drops them: a context assembled from a failed lineage lookup
    reaches the caller labelled available, with nothing naming what is missing."""
    _, runtime, _ = make_server(tmp_path, monkeypatch)
    failures = {"session_lineage": "TimeoutError: lineage lookup timed out"}
    runtime.mcp_broker = Broker(
        {"recent_related_sessions": [], "component_failures": failures}
    )
    result = anyio.run(
        owner_fixture,
        runtime,
        products.CampaignInput(project={"project": "fixture"}, roots=["fixture-1"]),
    )
    product = result.product
    assert product.availability == "degraded"
    assert product.component_failures == failures
    assert "session_lineage" in (product.reason or "")


def test_native_campaign_current_receipts_do_not_promote_acceptance(
    tmp_path, monkeypatch
):
    _, runtime, fake = make_server(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runtime.beads,
        "campaign_closure",
        lambda *a, **kw: {
            "owner_product": {
                "revision": "tasks",
                "closure": {"complete": True},
                "items": [
                    {"id": "fixture-1", "status": "closed", "notes": "reported success"}
                ],
            }
        },
    )
    fake.responses["job.list"] = {
        "jobs": [DONE],
        "truncated": True,
        "next_cursor": "retained-next",
    }
    result = anyio.run(
        products._campaign,
        runtime,
        products.CampaignInput(project={"project": "fixture"}, roots=["fixture-1"]),
    )
    assert result.product.data["components"]["agentctl"]["data"]["jobs"] == [DONE]
    assert (
        result.product.data["components"]["agentctl"]["data"]["next_cursor"]
        == "retained-next"
    )
    assert result.product.data["acceptance"]["state"] == "unknown"
    assert result.product.availability == "degraded"


def test_native_campaign_action_retains_exact_immutable_observation(
    tmp_path, monkeypatch
):
    _, runtime, fake = make_server(tmp_path, monkeypatch)
    owner = {
        "revision": "task-revision",
        "closure": {"complete": True},
        "items": [
            {"id": "fixture-1", "status": "closed", "notes": "reported delivery"}
        ],
    }
    monkeypatch.setattr(
        runtime.beads, "campaign_closure", lambda *a, **kw: {"owner_product": owner}
    )
    fake.responses["job.list"] = {"jobs": [DONE], "truncated": False}
    monkeypatch.setattr(server_module, "ALL_ACTIONS", products.ACTIONS)
    server = create_server(runtime.config)
    response = call(
        server,
        "campaign.progress",
        {"project": {"project": "fixture"}, "roots": ["fixture-1"]},
    )
    assert response["result"]["outcome"] == "ok", response
    assert response["result"]["owner"] == "beads"
    expected = response["data"]
    owner["items"][0]["notes"] = "later report"
    saved = runtime.results.read(response["result"]["result_id"])
    assert saved["data"] == expected
    assert (
        saved["data"]["product"]["data"]["components"]["tasks"]["data"][
            "owner_product"
        ]["items"][0]["notes"]
        == "reported delivery"
    )


def test_task_owner_failure_keeps_native_job_evidence_and_unknown_scope(
    tmp_path, monkeypatch
):
    from sinnix_agent_gateway.beads import BeadsError

    _, runtime, fake = make_server(tmp_path, monkeypatch)

    def unavailable(*a, **kw):
        raise BeadsError("configured authority unavailable")

    monkeypatch.setattr(runtime.beads, "campaign_closure", unavailable)
    fake.responses["job.list"] = {"jobs": [DONE], "truncated": False}
    result = anyio.run(
        products._campaign,
        runtime,
        products.CampaignInput(project={"project": "fixture"}, roots=["fixture-1"]),
    )
    assert result.product.data["components"]["tasks"]["status"] == "unavailable"
    assert result.product.data["components"]["agentctl"]["data"]["jobs"] == [DONE]
    assert result.product.data["scope_delta"]["state"] == "unknown"
    assert result.product.data["acceptance"]["state"] == "unknown"
    assert "tasks" in result.product.component_failures


@pytest.mark.parametrize("intent", ["verification.regression", "project.trajectory"])
def test_explicit_context_roots_use_same_historical_native_closure(
    tmp_path, monkeypatch, intent
):
    _, runtime, fake = make_server(tmp_path, monkeypatch)
    calls = []

    def closure(project, roots, **kwargs):
        calls.append((project, roots, kwargs["at"]))
        return {
            "owner_product": {
                "revision": kwargs["at"],
                "closure": {"complete": True},
                "items": [],
            }
        }

    monkeypatch.setattr(runtime.beads, "campaign_closure", closure)
    result = anyio.run(
        contexts._compose,
        runtime,
        contexts.ComposeInput(
            intent=intent,
            project={"project": "fixture"},
            roots=["fixture-1"],
            at={"revision": "current"},
            baseline={"revision": "baseline"},
        ),
    )
    assert calls == [
        ("fixture", ["fixture-1"], "current"),
        ("fixture", ["fixture-1"], "baseline"),
    ]
    assert result.components[0].data["data"]["acceptance"]["state"] == "unknown"
    assert not fake.calls


def test_all_native_owners_unavailable_is_not_an_empty_campaign(tmp_path, monkeypatch):
    from sinnix_agent_gateway.beads import BeadsError
    from sinnix_agent_gateway.results import ProtocolError

    _, runtime, _ = make_server(tmp_path, monkeypatch)

    def tasks(*args, **kwargs):
        raise BeadsError("task owner offline")

    def jobs(*args, **kwargs):
        raise ProtocolError("unavailable", "retained jobs offline")

    monkeypatch.setattr(runtime.beads, "campaign_closure", tasks)
    monkeypatch.setattr(runtime, "_job", jobs)
    result = anyio.run(
        products._campaign,
        runtime,
        products.CampaignInput(project={"project": "fixture"}, roots=["fixture-1"]),
    )
    assert result.product.availability == "unavailable"
    assert set(result.product.component_failures) == {"tasks", "agentctl"}
    assert result.product.data["acceptance"]["state"] == "unknown"
