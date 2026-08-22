from __future__ import annotations

import pytest

from sinnix_agent_gateway.contracts import ActionSpec, EffectMode, ResourceSpec, VerbFamily
from sinnix_agent_gateway.refs import RefTemplate, ReferenceError, SinnixRef
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


def test_catalog_search_filters_resource_kind_and_text() -> None:
    result = REGISTRY.search(CatalogSearch(resource_kind="bead", text="catalog"))

    assert [action["name"] for action in result["actions"]] == ["gateway.catalog"]
    assert result["resources"] == [
        {
            "kind": "bead",
            "ref_template": "sinnix://projects/{project_id}/beads/{bead_id}",
            "owner": "beads",
            "readable_projections": ["summary", "history", "graph"],
            "supports_query": True,
        }
    ]
