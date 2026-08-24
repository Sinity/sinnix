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
        self._bindings_by_tool: dict[str, tuple[TargetToolBinding, ...]] = {}
        for binding in self.bindings:
            self._bindings_by_tool.setdefault(binding.tool_name, ())
            self._bindings_by_tool[binding.tool_name] += (binding,)
        self._validate()

    def _validate(self) -> None:
        if len(self._bindings_by_action) != len(self.bindings):
            raise RegistryError("target tool bindings must name each action once")
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

    def action_for_tool(
        self,
        tool_name: str,
        action_name: str | None = None,
        principal: str | None = None,
    ):
        try:
            bindings = self._bindings_by_tool[tool_name]
        except KeyError as error:
            raise RegistryError(f"no target tool binding for {tool_name!r}") from error
        if action_name is None:
            if len(bindings) != 1:
                raise RegistryError(
                    f"target tool {tool_name!r} requires a declared action selector"
                )
            binding = bindings[0]
        else:
            try:
                binding = next(
                    binding
                    for binding in bindings
                    if binding.action_name == action_name
                )
            except StopIteration as error:
                raise RegistryError(
                    f"action {action_name!r} is not bound to target tool {tool_name!r}"
                ) from error
        action = self.registry.action(binding.action_name)
        if principal is not None and principal not in action.principals:
            raise RegistryError(
                f"principal {principal!r} cannot invoke action {action.name!r}"
            )
        return action

    def fallback_for_tool(self, tool_name: str, principal: str):
        """Return a visible action for recording a rejected selector request."""
        try:
            bindings = self._bindings_by_tool[tool_name]
        except KeyError as error:
            raise RegistryError(f"no target tool binding for {tool_name!r}") from error
        for binding in bindings:
            action = self.registry.action(binding.action_name)
            if principal in action.principals:
                return action
        # Stable protocol verbs remain present even when a principal has no
        # action in that family. The first declared contract is used only to
        # carry the typed policy-denied envelope; selector resolution has
        # already failed and no owner callback is dispatched.
        return self.registry.action(bindings[0].action_name)

    def is_visible(self, tool_name: str, principal: str) -> bool:
        del principal
        return tool_name in self._bindings_by_tool
