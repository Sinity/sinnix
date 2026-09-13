"""Typed archive adapters preserve owner input/output and authority."""

from __future__ import annotations

import pytest
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.actions import activity
from sinnix_agent_gateway.app import create_server
from test_actions_jobs import call
from test_actions_jobs import make_server as job_server
from test_actions_products import Broker


def make_server(tmp_path, principal, monkeypatch):
    _, runtime, fake = job_server(tmp_path, principal, monkeypatch)
    monkeypatch.setattr(server_module, "visible_actions", lambda _: activity.ACTIONS)
    return create_server(runtime.config, principal), runtime, fake


@pytest.mark.parametrize(
    "action,payload,operation",
    [
        (
            "sessions.list",
            {"repo": "fixture", "continuation": "indexed-page"},
            "sessions.list",
        ),
        ("sessions.search", {"expression": "needle", "offset": 20}, "sessions.search"),
        ("sessions.read", {"ref": "session:fixture", "offset": 20}, "sessions.read"),
        ("sessions.raw.list", {"origin": "claude-code-session"}, "sessions.raw.list"),
        (
            "sessions.raw.search",
            {
                "origin": "codex-session",
                "query": "needle",
                "continuation": "source-page",
            },
            "sessions.raw.search",
        ),
        (
            "sessions.raw.read",
            {"reference": "codex:fixture.jsonl", "offset": 4, "max_bytes": 8},
            "sessions.raw.read",
        ),
        (
            "sessions.raw.timeline",
            {"origins": ["codex-session"], "since": "2026-01-01T00:00:00Z"},
            "sessions.raw.timeline",
        ),
        (
            "memory.raw.search",
            {"query": "needle", "source_cursors": {"codex-session": None}},
            "memory.raw.search",
        ),
        (
            "timeline.query",
            {"since": "2026-01-01T00:00:00Z", "continuation": "events-page"},
            "sessions.timeline",
        ),
        ("sessions.resume", {"session_id": "fixture"}, "context.resume"),
    ],
)
def test_native_operation_envelope_survives_transport(
    tmp_path, monkeypatch, action, payload, operation
):
    server, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    data = {
        "items": [{"reference": "codex:fixture.jsonl", "indexed_session_id": None}],
        "continuation": "owner-next",
        "coverage": {
            "complete": False,
            "gaps": ["missing source"],
            "authority": "original-local-session-jsonl",
            "time_basis": "session-file-mtime",
        },
    }
    runtime.mcp_broker = Broker(data)
    result = call(server, action, payload)
    assert result["result"]["outcome"] == "ok", result
    assert result["data"]["owner_product"]["data"] == data
    sent = runtime.mcp_broker.calls[0][2]["session_operation"]
    assert sent["operation"] == operation
    for key, value in payload.items():
        assert sent[key] == value
    assert set(sent).isdisjoint({"actor", "request_id", "reason", "deadline_at"})


@pytest.mark.parametrize(
    "action,payload",
    [
        ("sessions.raw.search", {"origin": "codex", "query": "needle"}),
        ("sessions.raw.search", {"origin": "codex-session", "query": ""}),
        ("sessions.list", {"limit": 0}),
        (
            "sessions.raw.read",
            {"reference": "codex:fixture.jsonl", "max_bytes": 100000},
        ),
    ],
)
def test_native_input_constraints_reject_before_owner(
    tmp_path, monkeypatch, action, payload
):
    server, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker()
    result = call(server, action, payload)
    assert result["result"]["outcome"] == "error"
    assert not runtime.mcp_broker.calls


def test_archive_unavailable_is_retained_without_local_fallback(tmp_path, monkeypatch):
    server, runtime, _ = make_server(tmp_path, "observer", monkeypatch)
    runtime.mcp_broker = Broker(failure=True)
    result = call(
        server, "sessions.raw.search", {"origin": "codex-session", "query": "needle"}
    )
    assert result["result"]["outcome"] == "ok"
    assert result["data"]["owner_product"]["availability"] == "unavailable"


def test_owner_models_generate_action_inputs_without_drift():
    controls = {"request_id", "actor", "reason", "deadline_at"}
    owner = activity.session_owner
    models = {
        "sessions.list": owner.SessionList,
        "sessions.search": owner.SessionSearch,
        "sessions.read": owner.SessionRead,
        "sessions.raw.list": owner.RawList,
        "sessions.raw.search": owner.RawSearch,
        "sessions.raw.read": owner.RawRead,
        "sessions.raw.timeline": owner.RawTimeline,
        "memory.raw.search": owner.RawMemorySearch,
        "timeline.query": owner.SessionTimeline,
        "sessions.resume": owner.ResumeContext,
    }
    actions = {action.name: action for action in activity.ACTIONS}
    for name, model in models.items():
        expected = model.model_json_schema()
        actual = actions[name].Input.model_json_schema()
        native_operation = {
            "timeline.query": "sessions.timeline",
            "sessions.resume": "context.resume",
        }.get(name, name)
        expected["properties"]["operation"] = {
            "const": native_operation,
            "default": native_operation,
            "title": "Operation",
            "type": "string",
        }
        assert {
            key: value
            for key, value in actual["properties"].items()
            if key not in controls
        } == expected["properties"]
        assert actual.get("required", []) == expected.get("required", [])
        assert actual.get("$defs", {}) == expected.get("$defs", {})
