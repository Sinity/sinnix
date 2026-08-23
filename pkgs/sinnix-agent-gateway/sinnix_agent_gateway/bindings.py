from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .registry import CatalogRegistry, RegistryError


@dataclass(frozen=True)
class TargetToolBinding:
    """Bind one public V2 MCP tool directly to its declared owner route."""

    tool_name: str
    action_name: str
    owner: str
    route: str

    def __post_init__(self) -> None:
        if not self.tool_name:
            raise ValueError("target tool name cannot be empty")
        if not self.action_name:
            raise ValueError("target tool binding requires an action name")
        if not self.owner or not self.route:
            raise ValueError("target tool binding requires an owner and route")


class TargetToolBindings:
    """Validate direct target-tool bindings against the V2 action registry."""

    def __init__(
        self,
        registry: CatalogRegistry,
        bindings: Iterable[TargetToolBinding],
    ) -> None:
        self.registry = registry
        self.bindings = tuple(bindings)
        self._bindings_by_action = {
            binding.action_name: binding for binding in self.bindings
        }
        self._bindings_by_tool = {
            binding.tool_name: binding for binding in self.bindings
        }
        self._validate()

    def _validate(self) -> None:
        if len(self._bindings_by_action) != len(self.bindings):
            raise RegistryError("target tool bindings must name each action once")
        if len(self._bindings_by_tool) != len(self.bindings):
            raise RegistryError("target tool bindings must have unique tool names")
        declared_actions = {action.name for action in self.registry.actions}
        bound_actions = set(self._bindings_by_action)
        unknown = bound_actions - declared_actions
        if unknown:
            raise RegistryError(
                f"target tool bindings name unknown actions: {sorted(unknown)}"
            )
        missing = declared_actions - bound_actions
        if missing:
            raise RegistryError(
                f"declared actions are missing target tool bindings: {sorted(missing)}"
            )
        for binding in self.bindings:
            action = self.registry.action(binding.action_name)
            if binding.owner != action.owner:
                raise RegistryError(
                    f"target tool {binding.tool_name!r} owner {binding.owner!r} does not "
                    f"match action {action.name!r} owner {action.owner!r}"
                )
            if binding.route != action.route:
                raise RegistryError(
                    f"target tool {binding.tool_name!r} route {binding.route!r} does not "
                    f"match action {action.name!r} route {action.route!r}"
                )
            if binding.tool_name != action.verb.value:
                raise RegistryError(
                    f"target tool {binding.tool_name!r} must use action {action.name!r} "
                    f"verb {action.verb.value!r}"
                )

    def action_for_tool(self, tool_name: str, principal: str | None = None):
        try:
            binding = self._bindings_by_tool[tool_name]
        except KeyError as error:
            raise RegistryError(f"no target tool binding for {tool_name!r}") from error
        action = self.registry.action(binding.action_name)
        if principal is not None and principal not in action.principals:
            raise RegistryError(
                f"principal {principal!r} cannot invoke action {action.name!r}"
            )
        return action

    def is_visible(self, tool_name: str, principal: str) -> bool:
        return principal in self.action_for_tool(tool_name).principals
