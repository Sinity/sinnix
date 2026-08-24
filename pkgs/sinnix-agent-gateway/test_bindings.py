from __future__ import annotations

from dataclasses import replace

import pytest

from sinnix_agent_gateway.bindings import TargetToolBinding, TargetToolBindings
from sinnix_agent_gateway.registry import CatalogRegistry, REGISTRY, RegistryError


VALID_BINDINGS = tuple(
    TargetToolBinding(action.verb.value, action.name, action.owner, action.route)
    for action in REGISTRY.actions
)


def test_target_tool_bindings_cover_every_declared_action() -> None:
    bindings = TargetToolBindings(REGISTRY, VALID_BINDINGS)

    assert bindings.action_for_tool("status") is REGISTRY.action("gateway.status")
    assert bindings.action_for_tool("catalog") is REGISTRY.action("gateway.catalog")
    assert bindings.action_for_tool("get") is REGISTRY.action("resources.get")
    assert bindings.action_for_tool("query", "projects.query") is REGISTRY.action("projects.query")
    assert bindings.action_for_tool("query", "beads.query") is REGISTRY.action("beads.query")
    assert bindings.action_for_tool("query", "machine.query") is REGISTRY.action("machine.query")
    with pytest.raises(RegistryError, match="requires a declared action selector"):
        bindings.action_for_tool("query")
    assert bindings.action_for_tool("context") is REGISTRY.action("projects.context")
    assert bindings.action_for_tool("events") is REGISTRY.action("audit.events")
    assert bindings.action_for_tool("wait") is REGISTRY.action("jobs.wait")
    assert bindings.action_for_tool("run", "shell.run") is REGISTRY.action("shell.run")
    assert bindings.action_for_tool("run", "agent.for_bead") is REGISTRY.action("agent.for_bead")
    assert bindings.action_for_tool("change", "projects.change") is REGISTRY.action("projects.change")
    assert bindings.action_for_tool("change", "files.change") is REGISTRY.action("files.change")
    assert bindings.action_for_tool("change", "beads.change") is REGISTRY.action("beads.change")
    assert bindings.action_for_tool("change", "beads.changeset") is REGISTRY.action("beads.changeset")
    assert bindings.action_for_tool("change", "mcp.change") is REGISTRY.action("mcp.change")
    assert bindings.action_for_tool("operate", "machine.operate") is REGISTRY.action("machine.operate")
    assert bindings.action_for_tool("operate", "beads.operate") is REGISTRY.action("beads.operate")
    assert bindings.action_for_tool("operate", "jobs.cancel") is REGISTRY.action("jobs.cancel")
    assert bindings.action_for_tool("operate", "desktop.operate") is REGISTRY.action("desktop.operate")
    assert bindings.action_for_tool("operate", "terminals.operate") is REGISTRY.action("terminals.operate")
    assert bindings.action_for_tool("operate", "browser.operate") is REGISTRY.action("browser.operate")


def test_target_tool_bindings_enforce_declared_principal() -> None:
    status = replace(REGISTRY.action("gateway.status"), principals=frozenset({"observer"}))
    registry = CatalogRegistry(
        REGISTRY.resources,
        tuple(
            status if action.name == "gateway.status" else action
            for action in REGISTRY.actions
        ),
    )
    bindings = TargetToolBindings(registry, VALID_BINDINGS)

    assert bindings.is_visible("status", "observer")
    with pytest.raises(RegistryError, match="cannot invoke"):
        bindings.action_for_tool("status", principal="operator")
    assert bindings.is_visible("wait", "observer")
    assert bindings.is_visible("run", "operator")
    assert bindings.is_visible("run", "agent-control")
    assert bindings.is_visible("run", "observer")
    assert bindings.is_visible("change", "operator")
    assert bindings.is_visible("operate", "operator")
    assert bindings.is_visible("operate", "agent-control")
    assert bindings.is_visible("change", "observer")
    assert bindings.is_visible("operate", "observer")
    assert bindings.fallback_for_tool("change", "observer").name == "projects.change"
    with pytest.raises(RegistryError, match="cannot invoke"):
        bindings.action_for_tool("run", "agent.for_bead", "observer")


@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        (VALID_BINDINGS[:1], "missing target tool bindings"),
        (
            (
                TargetToolBinding("status", "gateway.status", "registry", "observe.gateway_status"),
                VALID_BINDINGS[1],
                VALID_BINDINGS[2],
                *VALID_BINDINGS[3:],
            ),
            "does not match action 'gateway.status' owner",
        ),
        (
            (
                TargetToolBinding("status", "gateway.status", "gateway", "registry.search"),
                VALID_BINDINGS[1],
                VALID_BINDINGS[2],
                *VALID_BINDINGS[3:],
            ),
            "does not match action 'gateway.status' route",
        ),
        (
            (
                TargetToolBinding("status", "gateway.unknown", "gateway", "gateway.unknown"),
                VALID_BINDINGS[1],
                VALID_BINDINGS[2],
                *VALID_BINDINGS[3:],
            ),
            "unknown actions",
        ),
        (
            tuple(
                TargetToolBinding("operate", "agent.for_bead", "systemd-jobs", "job.agent.start")
                if binding.action_name == "agent.for_bead"
                else binding
                for binding in VALID_BINDINGS
            ),
            "must use action 'agent.for_bead' verb 'run'",
        ),
    ],
)
def test_target_tool_bindings_reject_contract_drift(
    bindings: tuple[TargetToolBinding, ...], message: str
) -> None:
    with pytest.raises(RegistryError, match=message):
        TargetToolBindings(REGISTRY, bindings)
