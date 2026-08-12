"""Pure, bounded accessible-subtree walker.

Operates on any object exposing the small ``AccessibleNode`` protocol below
-- ``daemon.py`` adapts real AT-SPI2 (pyatspi) accessible objects into this
shape, keeping this module importable and unit-testable without a running
AT-SPI2 bus or the ``gi``/``pyatspi`` bindings at all.
"""

from __future__ import annotations

from typing import Protocol


class AccessibleNode(Protocol):
    def role_name(self) -> str: ...

    def name(self) -> str: ...

    def text(self) -> str | None: ...

    def children(self) -> list["AccessibleNode"]: ...


def build_subtree(
    node: AccessibleNode,
    *,
    max_depth: int = 40,
    max_nodes: int = 2000,
) -> dict:
    """Walk ``node`` depth-first into a nested ``{role, name, text?,
    children?, truncated?}`` dict.

    Bounded on two axes so a single dump of a pathological subtree (e.g. a
    Chromium tab that renders its full DOM as AT-SPI nodes) cannot grow
    unbounded: ``max_depth`` caps how deep a branch is followed, and
    ``max_nodes`` caps the total node count across the whole walk. Either
    limit sets a ``truncated`` marker on the node where the walk stopped
    instead of silently dropping data.
    """
    counter = {"n": 0}

    def walk(n: AccessibleNode, depth: int) -> dict | None:
        if counter["n"] >= max_nodes:
            return None
        counter["n"] += 1
        entry: dict = {"role": n.role_name(), "name": n.name()}
        text = n.text()
        if text:
            entry["text"] = text
        if depth >= max_depth:
            entry["truncated"] = "max_depth"
            return entry
        children_out = []
        for child in n.children():
            if counter["n"] >= max_nodes:
                entry["truncated"] = "max_nodes"
                break
            child_entry = walk(child, depth + 1)
            if child_entry is None:
                entry["truncated"] = "max_nodes"
                break
            children_out.append(child_entry)
        if children_out:
            entry["children"] = children_out
        return entry

    return walk(node, 0) or {"role": "", "name": "", "truncated": "max_nodes"}
