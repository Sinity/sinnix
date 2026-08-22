from __future__ import annotations

from dataclasses import replace

import pytest

from sinnix_agent_gateway.bindings import TargetToolBinding, TargetToolBindings
from sinnix_agent_gateway.registry import CatalogRegistry, REGISTRY, RegistryError


VALID_BINDINGS = (
    TargetToolBinding("status", "gateway.status", "gateway", "observe.gateway_status"),
    TargetToolBinding("catalog", "gateway.catalog", "registry", "registry.search"),
    TargetToolBinding("get", "resources.get", "resolver", "resources.get"),
)


def test_target_tool_bindings_cover_every_declared_action() -> None:
    bindings = TargetToolBindings(REGISTRY, VALID_BINDINGS)

    assert bindings.action_for_tool("status") is REGISTRY.action("gateway.status")
    assert bindings.action_for_tool("catalog") is REGISTRY.action("gateway.catalog")
    assert bindings.action_for_tool("get") is REGISTRY.action("resources.get")


def test_target_tool_bindings_enforce_declared_principal() -> None:
    status = replace(REGISTRY.action("gateway.status"), principals=frozenset({"observer"}))
    registry = CatalogRegistry(
        REGISTRY.resources,
        (status, REGISTRY.action("gateway.catalog"), REGISTRY.action("resources.get")),
    )
    bindings = TargetToolBindings(registry, VALID_BINDINGS)

    assert bindings.is_visible("status", "observer")
    with pytest.raises(RegistryError, match="cannot invoke"):
        bindings.action_for_tool("status", "operator")


@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        (VALID_BINDINGS[:1], "missing target tool bindings"),
        (
            (
                TargetToolBinding("status", "gateway.status", "registry", "observe.gateway_status"),
                VALID_BINDINGS[1],
                VALID_BINDINGS[2],
            ),
            "does not match action 'gateway.status' owner",
        ),
        (
            (
                TargetToolBinding("status", "gateway.status", "gateway", "registry.search"),
                VALID_BINDINGS[1],
                VALID_BINDINGS[2],
            ),
            "does not match action 'gateway.status' route",
        ),
        (
            (
                TargetToolBinding("status", "gateway.unknown", "gateway", "gateway.unknown"),
                VALID_BINDINGS[1],
                VALID_BINDINGS[2],
            ),
            "unknown actions",
        ),
        (
            (
                VALID_BINDINGS[0],
                TargetToolBinding("status", "gateway.catalog", "registry", "registry.search"),
                VALID_BINDINGS[2],
            ),
            "unique tool names",
        ),
    ],
)
def test_target_tool_bindings_reject_contract_drift(
    bindings: tuple[TargetToolBinding, ...], message: str
) -> None:
    with pytest.raises(RegistryError, match=message):
        TargetToolBindings(REGISTRY, bindings)
