from __future__ import annotations

DEFAULT_TIMEOUT_SECONDS = 3_600
# An implementation agent routinely needs more than an hour.
MAX_AGENT_TIMEOUT_SECONDS = 14_400
MAX_DECLARED_OPERATION_TIMEOUT_SECONDS = 28_800
# Hard ceiling on one agent's unit; the job plane's MemoryHigh is 20G.
AGENT_MEMORY_MAX = "4G"
# One round trip to a local tool (pueue, wt, gh, git, bd). A minute
# distinguishes a wedged daemon from a slow one.
CALL_TIMEOUT_SECONDS = 60
SYSTEMCTL_TIMEOUT_SECONDS = 30
# Hex characters shown of a run id's suffix, a commit, or a job reference.
SHORT_ID = 8
# What a queued command leaves behind: its exit status, a JSON document, a
# pytest report, or an agent's last message.
RESULT_KINDS = frozenset({"exit", "json", "pytest", "last-message"})
# The kinds a descriptor may declare; `last-message` belongs to agents alone.
DECLARABLE_RESULT_KINDS = frozenset({"exit", "json", "pytest"})


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
