"""Generated Beads actions exercise exact native envelopes and gateway replay."""

from __future__ import annotations

from conftest import call
from sinnix_agent_gateway.actions import beads
from sinnix_agent_gateway.app import create_server
from test_beads import beads_service, commands


def fixture(tmp_path):
    service, log = beads_service(tmp_path)
    return service.config, log


def server_fixture(tmp_path):
    config, log = fixture(tmp_path)
    return create_server(config, "operator"), log


def test_native_update_preserves_explicit_null_metadata_and_row_version(tmp_path):
    server, log = server_fixture(tmp_path)
    body = {
        "actor": "fixture-operator",
        "expected_version": 7,
        "patch": {"metadata": {"set": {"nested": None}}, "notes": "new notes"},
    }
    action = next(row for row in beads.ACTIONS if row.name == "beads.update")
    model = action.Input.model_validate(
        {
            "project": {"project": "fixture"},
            "idempotency_key": "update-one",
            "path": {"id": "fixture-1"},
            "body": body,
        }
    )
    assert model.body.expected_version == 7
    value = call(
        server, "beads.update", model.model_dump(mode="json", exclude_unset=True)
    )
    assert value["result"]["outcome"] == "ok", value
    sent = commands(log)[-1]["payload"]
    assert sent["body"] == body
    again = call(
        server, "beads.update", model.model_dump(mode="json", exclude_unset=True)
    )
    assert again["result"]["result_id"] == value["result"]["result_id"]
    assert sum("call" in row["argv"] for row in commands(log)) == 1


def test_atomic_batch_reaches_owner_once_with_symbolic_references(tmp_path):
    server, log = server_fixture(tmp_path)
    body = {
        "actor": "operator",
        "items": [
            {
                "kind": "create",
                "create": {"key": "new", "title": "new task", "issue_type": "task"},
            },
            {
                "kind": "close",
                "close": {"target": {"key": "new"}, "reason": "complete"},
            },
        ],
    }
    response = call(
        server,
        "beads.changeset",
        {
            "project": {"project": "fixture"},
            "idempotency_key": "atomic-one",
            "body": body,
        },
    )
    assert response["result"]["outcome"] == "ok", response
    assert commands(log)[-1]["payload"] == {"body": body}
    assert commands(log)[-1]["argv"][-3:] == ["owner", "call", "applyBatch"]


def test_native_schema_rejects_unknown_fields_and_missing_actor(tmp_path):
    server, log = server_fixture(tmp_path)
    for body in (
        {"title": "task", "actor": "operator", "invented": 1},
        {"title": "task"},
    ):
        response = call(
            server,
            "beads.create",
            {"project": {"project": "fixture"}, "idempotency_key": "bad", "body": body},
        )
        assert response["result"]["outcome"] == "error", response
    assert not log.exists()


def test_each_native_operation_has_an_independent_typed_action():
    names = {action.name for action in beads.ACTIONS}
    assert {
        "beads.create",
        "beads.update",
        "beads.changeset",
        "beads.graph",
        "beads.memory.remember",
    } <= names
    for action in beads.ACTIONS:
        if action.name in {"beads.create", "beads.update", "beads.changeset"}:
            schema = action.Input.model_json_schema()
            assert schema["additionalProperties"] is False
            assert "body" in schema["properties"]
            assert {"project", "body", "idempotency_key"} <= set(schema["required"])
