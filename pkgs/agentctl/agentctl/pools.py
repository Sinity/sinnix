"""The declared policy of every pueue group: its width and its exclusivity.

Groups live in pueued's own state, not in a configuration file, so a changed
declaration reaches the queue only by being applied to the daemon that already
runs: a restart marks every running task Killed. Applying the declaration
creates a missing group and resizes a drifted one, and lowering a width stops
nothing — pueue considers the limit when it next schedules. A group's tasks,
its paused state, and any group the declaration does not name are untouched.

Width is all pueue admits by: each group is scheduled on its own, so two pools
that must not share the host — the corpus pytest run and a wave of agents on a
32 GB workstation — are agentctl's to keep apart. `exclusive_with` declares
that pair, and the functions below are the whole of its arithmetic: which
pools a pool excludes, and which live tasks a launch must wait behind.
`launch` holds and releases against them; nothing here talks to the queue
except `apply`.
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
        # pueued has nowhere to keep this half of the declaration, so the pass
        # reports what agentctl itself will hold against.
        "exclusive": {
            group: list(partners)
            for group in sorted(declared)
            if (partners := exclusive_partners(declared, group))
        },
    }


def exclusive_partners(
    declared: Mapping[str, PoolPolicy], pool: str
) -> tuple[str, ...]:
    """The pools whose tasks must not run while ``pool``'s do.

    The relation is symmetric in effect, so declaring it on either side is
    enough: `pytest` excluding `agent` also keeps an agent out while a pytest
    task runs.
    """
    policy = declared.get(pool)
    partners = set(policy.exclusive_with if policy is not None else ())
    partners.update(
        name for name, other in declared.items() if pool in other.exclusive_with
    )
    partners.discard(pool)
    return tuple(sorted(partners))


def blocking_tasks(
    declared: Mapping[str, PoolPolicy],
    pool: str,
    tasks: Mapping[int, Task],
    *,
    task_id: int | None = None,
    held: frozenset[int] = frozenset(),
) -> tuple[int, ...]:
    """The live tasks a launch into ``pool`` must wait behind.

    Every unfinished task in an excluded pool blocks, with one exception that
    is what keeps the rule from deadlocking: a task already held for this same
    reason and queued *after* ``task_id`` is waiting for us, not we for it.
    Order is the pueue task id, so each side waits only on what it found
    already there; at admission there is no id yet and everything live blocks.
    """
    partners = exclusive_partners(declared, pool)
    if not partners:
        return ()
    return tuple(
        sorted(
            other.task_id
            for other in tasks.values()
            if other.group in partners
            and not other.terminal
            and not (
                other.task_id in held
                and task_id is not None
                and other.task_id > task_id
            )
        )
    )
