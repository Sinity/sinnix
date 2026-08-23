from __future__ import annotations

import pytest

from sinnix_agent_gateway.contracts import (
    BASE_TYPED_FAILURES,
    ActionSpec,
    EffectMode,
    ResourceSpec,
    VerbFamily,
)
from sinnix_mcp.refs import RefTemplate, ReferenceError, SinnixRef
from sinnix_agent_gateway.registry import CatalogRegistry, CatalogSearch, RegistryError, REGISTRY


RETAINED_OWNER_ACTIONS = {
    "project inspection": "projects.read",
    "machine observation": "machine.query",
    "capability discovery": "capabilities.query",
    "brokered MCP reads": "mcp.query",
    "desktop evidence": "desktop.query",
    "terminal evidence": "terminals.query",
    "browser evidence": "browser.query",
    "host-file reads": "files.query",
    "session evidence": "sessions.query",
    "memory evidence": "memory.query",
    "timeline evidence": "timeline.query",
    "artifact access": "artifacts.query",
    "audit verification": "audit.verify",
    "capture evidence": "captures.query",
}


def test_canonical_reference_round_trips_escaped_segments() -> None:
    reference = RefTemplate(
        "bead", "sinnix://projects/{project_id}/beads/{bead_id}"
    ).format({"project_id": "sinnix main", "bead_id": "sinnix-gw2.5"})

    assert str(reference) == "sinnix://projects/sinnix%20main/beads/sinnix-gw2.5"
    assert SinnixRef.parse(str(reference)) == reference
    resource, values = REGISTRY.resolve(reference)
    assert resource.kind == "bead"
    assert values == {"project_id": "sinnix main", "bead_id": "sinnix-gw2.5"}


@pytest.mark.parametrize(
    "value",
    [
        "https://projects/sinnix",
        "sinnix://projects/../sinnix",
        "sinnix://projects/%2E%2E/sinnix",
        "sinnix://projects/sinnix?path=/etc/passwd",
        "sinnix://projects/a%2Fb",
    ],
)
def test_reference_rejects_path_interpretation(value: str) -> None:
    with pytest.raises(ReferenceError):
        SinnixRef.parse(value)


def test_registry_rejects_overlapping_resource_templates() -> None:
    resources = (
        ResourceSpec("one", RefTemplate("one", "sinnix://things/{item}"), "fixture"),
        ResourceSpec("two", RefTemplate("two", "sinnix://things/{other}"), "fixture"),
    )

    with pytest.raises(RegistryError, match="overlap"):
        CatalogRegistry(resources, ())


def test_catalog_is_principal_filtered_and_hashes_actions() -> None:
    observer_catalog = REGISTRY.search(CatalogSearch(principal="observer"))
    operator_catalog = REGISTRY.search(CatalogSearch(principal="operator"))

    observer_actions = {row["name"] for row in observer_catalog["actions"]}
    operator_actions = {row["name"] for row in operator_catalog["actions"]}
    assert {
        "gateway.status",
        "gateway.catalog",
        "resources.get",
        "projects.query",
        "beads.query",
        "projects.context",
        "audit.events",
        "jobs.wait",
        "machine.query",
        "captures.query",
        "artifacts.query",
    } <= observer_actions
    assert {
        "gateway.status",
        "gateway.catalog",
        "resources.get",
        "projects.query",
        "beads.query",
        "projects.context",
        "audit.events",
        "jobs.wait",
        "shell.run",
        "projects.change",
        "files.change",
        "beads.change",
        "beads.changeset",
        "mcp.change",
        "machine.operate",
        "beads.operate",
        "jobs.cancel",
        "desktop.operate",
        "terminals.operate",
        "browser.operate",
        "files.query",
        "mcp.query",
        "sessions.query",
    } <= operator_actions
    assert "shell.run" not in observer_actions
    assert "projects.change" not in observer_actions
    assert observer_catalog["action_catalog_hash"] != operator_catalog["action_catalog_hash"]
    assert {row["kind"] for row in observer_catalog["resources"]} >= {
        "project",
        "checkout",
        "bead",
        "job",
        "artifact",
        "receipt",
        "result",
        "machine_unit",
        "process",
        "browser_page",
        "terminal",
        "capture_lane",
        "session",
        "context_snapshot",
    }


def test_action_failure_contracts_follow_public_controls_and_owner_capabilities() -> None:
    read_failures = BASE_TYPED_FAILURES | {"deadline"}

    assert REGISTRY.action("jobs.query").typed_failures == read_failures
    assert REGISTRY.action("agents.run").typed_failures == read_failures | {
        "conflict",
        "idempotency_conflict"
    }
    assert REGISTRY.action("mcp.change").typed_failures == read_failures | {
        "conflict",
        "idempotency_conflict",
        "unsupported_capability",
    }
    assert "precondition_failed" in REGISTRY.action("jobs.cancel").typed_failures
    assert "precondition_failed" not in REGISTRY.action("jobs.query").typed_failures
    for action in REGISTRY.actions:
        properties = action.input_schema["properties"]
        assert ("preconditions" in properties) is action.supports_precondition


def test_every_retained_owner_capability_has_a_read_action_and_resource_route() -> None:
    for capability, action_name in RETAINED_OWNER_ACTIONS.items():
        action = REGISTRY.action(action_name)
        assert action.effect is EffectMode.READ, capability
        assert action.verb is VerbFamily.QUERY, capability
        assert action.resource_kinds, capability
        assert all(REGISTRY.resource(kind) for kind in action.resource_kinds), capability


def test_resource_contracts_and_discovery_are_principal_filtered() -> None:
    resources = (
        ResourceSpec(
            "shared",
            RefTemplate("shared", "sinnix://fixtures/shared/{item}"),
            "fixture",
            principals=frozenset({"observer", "operator"}),
        ),
        ResourceSpec(
            "operator_only",
            RefTemplate("operator_only", "sinnix://fixtures/operator/{item}"),
            "fixture",
            principals=frozenset({"operator"}),
        ),
    )
    registry = CatalogRegistry(resources, ())

    observer_search = registry.search(CatalogSearch(principal="observer"))
    observer_documentation = registry.documentation_rows("observer")

    assert [row["kind"] for row in observer_search["resources"]] == ["shared"]
    assert [row["kind"] for row in observer_documentation["resources"]] == ["shared"]
    with pytest.raises(RegistryError, match="cannot read resource"):
        registry.resource_contract("operator_only", "observer")
    assert registry.resource_contract("operator_only", "operator")["resource"][
        "kind"
    ] == "operator_only"


def test_action_catalog_hash_changes_when_authority_changes() -> None:
    base = ActionSpec(
        name="fixture.read",
        verb=VerbFamily.QUERY,
        domain="fixture",
        owner="fixture",
        route="fixture.read",
        effect=EffectMode.READ,
        principals=frozenset({"observer"}),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )
    widened = ActionSpec(
        name="fixture.read",
        verb=VerbFamily.QUERY,
        domain="fixture",
        owner="fixture",
        route="fixture.read",
        effect=EffectMode.READ,
        principals=frozenset({"observer", "operator"}),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    assert CatalogRegistry((), (base,)).action_catalog_hash() != CatalogRegistry(
        (), (widened,)
    ).action_catalog_hash()


def test_catalog_contract_resources_preserve_generated_schema_metadata() -> None:
    action = REGISTRY.action_schema("gateway.catalog", "observer")
    resource = REGISTRY.resource_contract("bead")
    catalog = REGISTRY.search(
        CatalogSearch(availability="declared", principal="observer")
    )

    assert action["action"]["schema_ref"] == (
        "sinnix://gateway/v2/actions/gateway.catalog"
    )
    assert action["action"]["effect"] == "read"
    assert action["action"]["input_schema"]["properties"]["availability"] == {
        "enum": ["available", "unavailable"]
    }
    assert action["action"]["examples"] == [
        {"input": {"resource_kind": "bead", "availability": "available"}}
    ]
    assert resource["resource"]["contract_ref"] == "sinnix://gateway/v2/resources/bead"
    assert all(row["availability"] == "declared" for row in catalog["resources"])
    assert all(row["availability"] == "declared" for row in catalog["actions"])


def test_action_contract_rejects_missing_schema_and_unknown_principal() -> None:
    with pytest.raises(ValueError, match="input JSON Schema"):
        ActionSpec(
            name="fixture.read",
            verb=VerbFamily.QUERY,
            domain="fixture",
            owner="fixture",
            route="fixture.read",
            effect=EffectMode.READ,
            principals=frozenset({"observer"}),
            input_schema={},
            output_schema={"type": "object"},
        )
    with pytest.raises(ValueError, match="unknown principals"):
        ActionSpec(
            name="fixture.read",
            verb=VerbFamily.QUERY,
            domain="fixture",
            owner="fixture",
            route="fixture.read",
            effect=EffectMode.READ,
            principals=frozenset({"unrecognized"}),
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
    with pytest.raises(ValueError, match="examples require an input object"):
        ActionSpec(
            name="fixture.read",
            verb=VerbFamily.QUERY,
            domain="fixture",
            owner="fixture",
            route="fixture.read",
            effect=EffectMode.READ,
            principals=frozenset({"observer"}),
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            examples=({},),
        )


def test_resource_get_contract_formats_canonical_project_relationships() -> None:
    action = REGISTRY.action_schema("resources.get", "observer")["action"]

    assert action["input_schema"]["properties"]["includes"]["maxItems"] == 8
    assert action["input_schema"]["properties"]["as_of"]["maxLength"] == 128

    assert action["verb"] == "get"
    assert action["resource_kinds"] == [
        "project",
        "checkout",
        "bead",
        "task_authority",
        "job",
    ]
    assert action["input_schema"]["required"] == ["ref"]
    assert action["input_schema"]["properties"]["projection"]["enum"] == [
        "summary",
        "log",
        "result",
    ]
    assert REGISTRY.reference(
        "checkout", {"project_id": "sinnix main", "checkout_id": "default"}
    ) == "sinnix://projects/sinnix%20main/checkouts/default"


def test_catalog_search_filters_resource_kind_and_text() -> None:
    result = REGISTRY.search(CatalogSearch(resource_kind="bead", text="bead"))

    assert [action["name"] for action in result["actions"]] == [
        "gateway.catalog",
        "resources.get",
        "beads.query",
        "projects.context",
        "beads.change",
        "beads.changeset",
    ]
    assert result["resources"] == [
        {
            "kind": "bead",
            "contract_ref": "sinnix://gateway/v2/resources/bead",
            "ref_template": "sinnix://projects/{project_id}/beads/{bead_id}",
            "owner": "beads",
            "principals": ["agent-control", "observer", "operator"],
            "readable_projections": ["summary", "history", "graph"],
            "supports_query": True,
            "availability": "declared",
        }
    ]


def test_catalog_search_scopes_contracts_to_project_resources() -> None:
    result = REGISTRY.search(CatalogSearch(project="sinnix"))

    assert result["project"] == "sinnix"
    assert {resource["kind"] for resource in result["resources"]} == {
        "project",
        "checkout",
        "bead",
        "task_authority",
    }
    assert {action["name"] for action in result["actions"]} == {
        "gateway.catalog",
        "resources.get",
        "projects.query",
        "beads.query",
        "projects.context",
        "projects.change",
        "beads.change",
        "beads.changeset",
        "beads.operate",
        "operations.run",
        "agents.run",
        "shell.run",
        "projects.list",
        "projects.tree",
        "projects.read",
        "projects.diff",
    }


def test_catalog_search_applies_text_to_resource_contracts() -> None:
    result = REGISTRY.search(CatalogSearch(text="scrollback"))

    assert result["actions"] == []
    assert [resource["kind"] for resource in result["resources"]] == ["terminal"]


def test_run_and_wait_contracts_are_closed_and_authority_scoped() -> None:
    agent = REGISTRY.action_schema("agents.run", "agent-control")["action"]
    run = REGISTRY.action_schema("shell.run", "operator")["action"]
    wait = REGISTRY.action_schema("jobs.wait", "observer")["action"]

    assert run["verb"] == "run"
    assert run["effect"] == "run"
    assert run["owner"] == "systemd-jobs"
    assert run["route"] == "job.shell.start"
    assert run["principals"] == ["operator"]
    assert run["supports_idempotency"] is True
    assert run["input_schema"]["additionalProperties"] is False
    assert run["input_schema"]["required"] == [
        "project_id",
        "checkout_id",
        "argv",
        "idempotency_key",
    ]
    assert set(run["input_schema"]["properties"]).isdisjoint(
        {"environment", "as_root", "command", "unit"}
    )
    assert agent["verb"] == "run"
    assert agent["owner"] == "systemd-jobs"
    assert agent["route"] == "job.agent.start"
    assert agent["principals"] == ["agent-control", "operator"]
    assert agent["input_schema"]["additionalProperties"] is False
    assert agent["input_schema"]["required"] == [
        "project_id",
        "prompt",
        "backend",
        "model",
        "reasoning_effort",
        "idempotency_key",
    ]
    assert wait["verb"] == "wait"
    assert wait["effect"] == "read"
    assert wait["owner"] == "systemd-jobs"
    assert wait["route"] == "job.wait"
    assert wait["principals"] == ["agent-control", "observer", "operator"]
    assert wait["input_schema"]["additionalProperties"] is False
    assert wait["input_schema"]["required"] == ["ref"]
    assert wait["input_schema"]["properties"]["timeout_seconds"]["maximum"] == 300
    with pytest.raises(RegistryError, match="cannot read action"):
        REGISTRY.action_schema("shell.run", "observer")


def test_change_and_operate_contracts_bind_closed_canonical_owner_targets() -> None:
    change = REGISTRY.action_schema("projects.change", "operator")["action"]
    operate = REGISTRY.action_schema("machine.operate", "operator")["action"]
    cancel = REGISTRY.action_schema("jobs.cancel", "agent-control")["action"]

    assert change["verb"] == "change"
    assert change["effect"] == "change"
    assert change["owner"] == "projects"
    assert change["route"] == "projects.change"
    assert change["resource_kinds"] == ["project", "checkout"]
    assert change["supports_idempotency"] is True
    assert change["supports_precondition"] is True
    assert change["input_schema"]["required"] == [
        "ref",
        "operation",
        "parameters",
        "idempotency_key",
    ]
    assert change["input_schema"]["properties"]["operation"] == {
        "enum": ["apply_patch", "write"]
    }
    assert change["input_schema"]["properties"]["preconditions"]["additionalProperties"] is False

    assert operate["verb"] == "operate"
    assert operate["effect"] == "operate"
    assert operate["owner"] == "ops-reducer"
    assert operate["route"] == "ops.actions.execute"
    assert operate["resource_kinds"] == ["job", "machine_unit", "process"]
    assert operate["supports_idempotency"] is True
    assert operate["supports_precondition"] is True
    assert operate["input_schema"]["properties"]["preconditions"] == {
        "type": "object",
        "additionalProperties": False,
        "required": ["expected_revision"],
        "properties": {"expected_revision": {"type": "integer", "minimum": 0}},
    }
    with pytest.raises(RegistryError, match="cannot read action"):
        REGISTRY.action_schema("machine.operate", "observer")
    assert cancel["verb"] == "operate"
    assert cancel["owner"] == "systemd-jobs"
    assert cancel["route"] == "job.cancel"
    assert cancel["principals"] == ["agent-control", "operator"]
    assert cancel["resource_kinds"] == ["job"]
    assert cancel["input_schema"]["properties"]["preconditions"] == {
        "type": "object",
        "additionalProperties": False,
        "required": ["expected_phase"],
        "properties": {
            "expected_phase": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
            }
        },
    }


def test_collapsed_mutation_contracts_are_operator_only_and_canonical() -> None:
    expected = {
        "files.change": ("change", "files", "files.change", ["host_file"]),
        "beads.change": ("change", "beads", "beads.write", ["project", "bead", "task_authority"]),
        "beads.changeset": ("change", "beads", "beads.changeset", ["project", "bead", "task_authority"]),
        "mcp.change": ("change", "mcp-broker", "mcp.call.write", ["mcp_tool"]),
        "beads.operate": ("operate", "beads", "beads.maintenance", ["project", "task_authority"]),
        "desktop.operate": ("operate", "desktop", "desktop.action", ["desktop"]),
        "terminals.operate": ("operate", "terminals", "terminals.action", ["terminal"]),
        "browser.operate": ("operate", "browser", "browser.action", ["browser_workspace", "browser_page"]),
    }

    for action_name, (verb, owner, route, resources) in expected.items():
        action = REGISTRY.action_schema(action_name, "operator")["action"]
        assert (action["verb"], action["owner"], action["route"]) == (verb, owner, route)
        assert action["resource_kinds"] == resources
        assert action["supports_idempotency"] is True
        assert action["input_schema"]["required"] == [
            "ref",
            "operation",
            "parameters",
            "idempotency_key",
        ]
        with pytest.raises(RegistryError, match="cannot read action"):
            REGISTRY.action_schema(action_name, "observer")


def test_query_context_and_events_contracts_bind_existing_read_owners() -> None:
    query = REGISTRY.action_schema("projects.query", "observer")["action"]
    context = REGISTRY.action_schema("projects.context", "agent-control")["action"]
    events = REGISTRY.action_schema("audit.events", "operator")["action"]

    assert query["verb"] == "query"
    assert query["owner"] == "projects"
    assert query["route"] == "projects.search"
    assert query["input_schema"]["additionalProperties"] is False
    assert query["input_schema"]["required"] == ["ref", "query"]
    assert query["input_schema"]["properties"]["ref"]["pattern"] == (
        "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$"
    )
    assert query["input_schema"]["properties"]["max_matches"]["maximum"] == 1_000
    beads = REGISTRY.action_schema("beads.query", "observer")["action"]
    assert beads["owner"] == "beads"
    assert beads["route"] == "beads.query"
    assert beads["input_schema"]["properties"]["parameters"]["properties"]["cursor"]["maxLength"] == 256
    assert "preview_digest" in REGISTRY.action_schema("beads.change", "operator")["action"]["input_schema"]["properties"]["parameters"]["properties"]
    changeset = REGISTRY.action_schema("beads.changeset", "operator")["action"]
    assert changeset["route"] == "beads.changeset"
    assert changeset["input_schema"]["properties"]["operation"]["enum"] == ["apply", "preview"]
    assert changeset["input_schema"]["properties"]["parameters"]["properties"]["actions"]["maxItems"] == 128
    assert changeset["input_schema"]["properties"]["parameters"]["properties"]["on_error"]["enum"] == ["stop", "continue"]
    maintenance = REGISTRY.action_schema("beads.operate", "operator")["action"]
    assert maintenance["route"] == "beads.maintenance"
    assert maintenance["input_schema"]["properties"]["operation"]["enum"] == ["backup.create", "backup.list", "backup.restore", "snapshot.publish", "sync.pull", "sync.push"]
    assert context["verb"] == "context"
    assert context["owner"] == "project-context"
    assert context["route"] == "project_context.context"
    assert context["input_schema"]["additionalProperties"] is False
    assert context["input_schema"]["required"] == ["ref"]
    assert events["verb"] == "events"
    assert events["owner"] == "audit"
    assert events["route"] == "audit.tail"
    assert events["resource_kinds"] == ["receipt"]
    assert events["input_schema"]["additionalProperties"] is False
    assert events["input_schema"]["properties"]["limit"]["maximum"] == 1_000
