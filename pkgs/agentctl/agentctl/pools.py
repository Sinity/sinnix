"""The declared width of every pueue group.

Groups live in pueued's own state, not in a configuration file, so a changed
declaration reaches the queue only by being applied to the daemon that already
runs: a restart marks every running task Killed. Applying the declaration
creates a missing group and resizes a drifted one, and lowering a width stops
nothing — pueue considers the limit when it next schedules. A group's tasks,
its paused state, and any group the declaration does not name are untouched.

Width is all this declaration controls. Pueue's normal queue dependencies and
operator stashes remain its admission state; nothing here changes them.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from . import pueue
from .config import PoolPolicy
from .pueue import PueueError, Task

# This runs as pueued starts, and the daemon answers only once its socket is
# bound.
DAEMON_WAIT_SECONDS = 10.0
_POLL_SECONDS = 0.2


def _live(wait_seconds: float) -> dict[str, int]:
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            return pueue.groups()
        except PueueError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_POLL_SECONDS)


def apply(
    declared: Mapping[str, PoolPolicy], *, wait_seconds: float = DAEMON_WAIT_SECONDS
) -> dict[str, Any]:
    """Bring every declared group to its declared parallelism."""
    live = _live(wait_seconds)
    created: list[dict[str, Any]] = []
    resized: list[dict[str, Any]] = []
    unchanged: list[str] = []
    for group in sorted(declared):
        slots = declared[group].parallel
        if group not in live:
            pueue.group_add(group, slots)
            created.append({"group": group, "parallel": slots})
        elif live[group] != slots:
            pueue.set_parallel(group, slots)
            resized.append({"group": group, "from": live[group], "to": slots})
        else:
            unchanged.append(group)
    return {
        "created": created,
        "resized": resized,
        "unchanged": unchanged,
        # Reported, never removed: a removed group strands the tasks queued
        # in it.
        "undeclared": sorted(set(live) - set(declared)),
    }
