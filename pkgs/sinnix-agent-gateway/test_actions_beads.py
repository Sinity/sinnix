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


def test_row_revisions_round_trip_exactly_as_strings(tmp_path):
    """Fails if a 64-bit row revision reaches the client as a JSON number.

    A ChatGPT session saw -8662698054174296873 rounded to
    -8662698054174297000. Every revision leaves as a decimal string, and the
    same string sent back as expected_version reaches the owner as the exact
    integer, for tokens beyond 2**53 of both signs.
    """
    import json

    server, log = server_fixture(tmp_path)
    negative, positive = -8662698054174296873, 2**62 + 3
    state = tmp_path / "owner-state.json"
    value = json.loads(state.read_text())
    value["items"][0]["revision"] = negative
    value["items"][1]["revision"] = positive
    state.write_text(json.dumps(value))

    listed = call(
        server,
        "beads.query",
        {"projects": ["fixture"], "filters": {"status": "open"}},
    )
    assert listed["result"]["outcome"] == "ok", listed

    def revisions(node):
        if isinstance(node, dict):
            for key, item in node.items():
                if key == "revision":
                    yield item
                yield from revisions(item)
        elif isinstance(node, list):
            for item in node:
                yield from revisions(item)

    seen = list(revisions(listed["data"]["items"]))
    assert str(negative) in seen and str(positive) in seen
    assert not any(isinstance(item, int) for item in seen)

    action = next(row for row in beads.ACTIONS if row.name == "beads.update")
    field = action.input_schema()["$defs"]["UpdateIssueRequest"]["properties"][
        "expected_version"
    ]
    assert {"type": "string", "pattern": "^-?[0-9]{1,20}$"} in field["anyOf"]

    for token in (negative, positive):
        response = call(
            server,
            "beads.update",
            {
                "project": {"project": "fixture"},
                "idempotency_key": f"guarded-{token}",
                "path": {"id": "fixture-1"},
                "body": {
                    "actor": "fixture-operator",
                    "expected_version": str(token),
                    "patch": {"notes": "guarded"},
                },
            },
        )
        assert response["result"]["outcome"] == "ok", response
        assert commands(log)[-1]["payload"]["body"]["expected_version"] == token
        echoed = response["data"]["owner_result"]["request"]["body"]
        assert echoed["expected_version"] == str(token)


def test_a_lost_changeset_response_is_recovered_by_its_key(tmp_path):
    """Fails if a committed create can only be recovered by running it again.

    A three-create changeset returned 502 through the tunnel yet committed.
    audit.operation, addressed by the key the caller chose, returns the
    committed response with its created ids and never reaches the owner.
    """
    server, log = server_fixture(tmp_path)
    request = {
        "project": {"project": "fixture"},
        "idempotency_key": "curation-creates",
        "body": {
            "actor": "operator",
            "items": [
                {"kind": "create", "create": {"key": "a", "title": "first new"}},
                {"kind": "create", "create": {"key": "b", "title": "second new"}},
            ],
        },
    }
    committed = call(server, "beads.changeset", request)
    assert committed["result"]["outcome"] == "ok", committed
    owner_calls = len(commands(log))

    lookup = {"action": "beads.changeset", "idempotency_key": "curation-creates"}
    recovered = call(server, "audit.operation", lookup)
    assert recovered["result"]["outcome"] == "ok", recovered
    data = recovered["data"]
    assert data["state"] == "confirmed"
    assert data["response"]["data"] == committed["data"]
    assert data["receipt_ref"] == committed["receipt"]["ref"]
    assert len(commands(log)) == owner_calls

    never = call(
        server, "audit.operation", {**lookup, "idempotency_key": "never-sent"}
    )["data"]
    assert never["state"] == "unknown" and never["response"] is None


def test_an_abandoned_claim_reads_as_indeterminate_and_a_live_one_as_pending(
    tmp_path,
):
    """Fails if a claim whose caller died reads as still pending, or vice versa."""
    from sinnix_agent_gateway.audit import AuditService
    from sinnix_agent_gateway.capabilities import Principal

    config, _ = fixture(tmp_path)
    audit = AuditService(config, Principal.for_name("operator"))
    assert audit.claim_idempotency("beads.create", "live", "sha")[0] == "new"
    assert audit.operation("beads.create", "live")["state"] == "pending"

    assert audit.claim_idempotency("beads.create", "dead", "sha")[0] == "new"
    # The process lock goes with the claimant; the row stays pending.
    audit.release_idempotency("beads.create", "dead")
    assert audit.operation("beads.create", "dead")["state"] == "indeterminate"
