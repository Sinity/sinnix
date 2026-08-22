from __future__ import annotations

import pytest

from sinnix_agent_gateway.contracts import ActionSpec, EffectMode, ResourceSpec, VerbFamily
from sinnix_mcp.refs import RefTemplate, ReferenceError, SinnixRef
from sinnix_agent_gateway.registry import CatalogRegistry, CatalogSearch, RegistryError, REGISTRY


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

    assert observer_catalog["actions"] == operator_catalog["actions"]
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
        "browser_page",
        "terminal",
        "capture_lane",
        "session",
        "context_snapshot",
    }


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

    assert action["verb"] == "get"
    assert action["resource_kinds"] == [
        "project",
        "checkout",
        "bead",
        "task_authority",
    ]
    assert action["input_schema"]["required"] == ["ref"]
    assert REGISTRY.reference(
        "checkout", {"project_id": "sinnix main", "checkout_id": "default"}
    ) == "sinnix://projects/sinnix%20main/checkouts/default"


def test_catalog_search_filters_resource_kind_and_text() -> None:
    result = REGISTRY.search(CatalogSearch(resource_kind="bead", text="bead"))

    assert [action["name"] for action in result["actions"]] == [
        "gateway.catalog",
        "resources.get",
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
    }


def test_catalog_search_applies_text_to_resource_contracts() -> None:
    result = REGISTRY.search(CatalogSearch(text="scrollback"))

    assert result["actions"] == []
    assert [resource["kind"] for resource in result["resources"]] == ["terminal"]
