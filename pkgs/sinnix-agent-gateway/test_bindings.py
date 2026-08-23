from __future__ import annotations

from dataclasses import replace

import pytest

from sinnix_agent_gateway.bindings import TargetToolBinding, TargetToolBindings
from sinnix_agent_gateway.registry import CatalogRegistry, REGISTRY, RegistryError


VALID_BINDINGS = (
    TargetToolBinding("status", "gateway.status", "gateway", "observe.gateway_status"),
    TargetToolBinding("catalog", "gateway.catalog", "registry", "registry.search"),
    TargetToolBinding("get", "resources.get", "resolver", "resources.get"),
    TargetToolBinding("query", "projects.query", "projects", "projects.search"),
    TargetToolBinding(
        "context", "projects.context", "project-context", "project_context.context"
    ),
    TargetToolBinding("events", "audit.events", "audit", "audit.tail"),
    TargetToolBinding("wait", "jobs.wait", "systemd-jobs", "job.wait"),
    TargetToolBinding("run", "shell.run", "systemd-jobs", "job.shell.start"),
    TargetToolBinding("run", "agents.run", "systemd-jobs", "job.agent.start"),
    TargetToolBinding("change", "projects.change", "projects", "projects.change"),
    TargetToolBinding("operate", "machine.operate", "ops-reducer", "ops.actions.execute"),
    TargetToolBinding("operate", "jobs.cancel", "systemd-jobs", "job.cancel"),
)


def test_target_tool_bindings_cover_every_declared_action() -> None:
    bindings = TargetToolBindings(REGISTRY, VALID_BINDINGS)

    assert bindings.action_for_tool("status") is REGISTRY.action("gateway.status")
    assert bindings.action_for_tool("catalog") is REGISTRY.action("gateway.catalog")
    assert bindings.action_for_tool("get") is REGISTRY.action("resources.get")
    assert bindings.action_for_tool("query") is REGISTRY.action("projects.query")
    assert bindings.action_for_tool("context") is REGISTRY.action("projects.context")
    assert bindings.action_for_tool("events") is REGISTRY.action("audit.events")
    assert bindings.action_for_tool("wait") is REGISTRY.action("jobs.wait")
    assert bindings.action_for_tool("run", "shell.run") is REGISTRY.action("shell.run")
    assert bindings.action_for_tool("run", "agents.run") is REGISTRY.action("agents.run")
    assert bindings.action_for_tool("change") is REGISTRY.action("projects.change")
    assert bindings.action_for_tool("operate", "machine.operate") is REGISTRY.action("machine.operate")
    assert bindings.action_for_tool("operate", "jobs.cancel") is REGISTRY.action("jobs.cancel")


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
    assert bindings.is_visible("run", "observer") is False
    assert bindings.is_visible("change", "operator")
    assert bindings.is_visible("operate", "operator")
    assert bindings.is_visible("operate", "agent-control")
    assert bindings.is_visible("change", "observer") is False
    assert bindings.is_visible("operate", "observer") is False
    with pytest.raises(RegistryError, match="cannot invoke"):
        bindings.action_for_tool("run", "agents.run", "observer")


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
            (
                *VALID_BINDINGS[:8],
                TargetToolBinding("operate", "agents.run", "systemd-jobs", "job.agent.start"),
                *VALID_BINDINGS[9:],
            ),
            "must use action 'agents.run' verb 'run'",
        ),
    ],
)
def test_target_tool_bindings_reject_contract_drift(
    bindings: tuple[TargetToolBinding, ...], message: str
) -> None:
    with pytest.raises(RegistryError, match=message):
        TargetToolBindings(REGISTRY, bindings)
