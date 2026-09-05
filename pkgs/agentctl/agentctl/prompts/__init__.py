"""The landing prompts, shipped as package data."""

from __future__ import annotations

from importlib import resources


def template(name: str) -> str:
    """The text of ``<name>.md`` beside this module; callers ``.format`` it."""
    return resources.files(__package__).joinpath(f"{name}.md").read_text()
