from __future__ import annotations

DEFAULT_TIMEOUT_SECONDS = 3_600
# Implementation lanes routinely need more than an hour; a 1h ceiling forced
# serial re-launch rounds that each paid a full context rebuild.
MAX_AGENT_TIMEOUT_SECONDS = 14_400
MAX_DECLARED_OPERATION_TIMEOUT_SECONDS = 28_800
# Hard ceiling on one agent's scope. The job plane's MemoryHigh is 20G; one
# lane may not take more than half of it.
AGENT_MEMORY_MAX = "4G"


def maximum_timeout_seconds(kind: str) -> int:
    return (
        MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
        if kind == "declared-operation"
        else MAX_AGENT_TIMEOUT_SECONDS
    )


def valid_timeout_seconds(value: object, *, kind: str) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= maximum_timeout_seconds(kind)
    )
