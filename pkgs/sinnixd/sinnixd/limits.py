from __future__ import annotations

DEFAULT_TIMEOUT_SECONDS = 3_600
MAX_DECLARED_OPERATION_TIMEOUT_SECONDS = 28_800


def maximum_timeout_seconds(kind: str) -> int:
    """Return the one timeout ceiling for a durable job kind."""
    return (
        MAX_DECLARED_OPERATION_TIMEOUT_SECONDS
        if kind == "declared-operation"
        else DEFAULT_TIMEOUT_SECONDS
    )


def valid_timeout_seconds(value: object, *, kind: str) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= maximum_timeout_seconds(kind)
    )
