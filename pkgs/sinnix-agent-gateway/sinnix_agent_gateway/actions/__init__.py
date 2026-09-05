"""Every typed gateway action, validated once at import."""

from __future__ import annotations

from ..action import Action, validate_actions
from ..registry import REGISTRY
from . import files

# Affordances may still name legacy registry actions while owners migrate.
ALL_ACTIONS: tuple[Action, ...] = validate_actions(
    (*files.ACTIONS,), also_known=(action.name for action in REGISTRY.actions)
)

BY_NAME: dict[str, Action] = {action.name: action for action in ALL_ACTIONS}


def visible(principal: str) -> tuple[Action, ...]:
    return tuple(action for action in ALL_ACTIONS if principal in action.principals)
