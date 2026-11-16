from __future__ import annotations

DEFAULT_TIMEOUT_SECONDS = 3_600
# Agents run until they finish; a coordinator cancels by hand. The value is
# the unit's watchdog, not a budget: a week, so a stuck agent is still
# reaped eventually.
MAX_AGENT_TIMEOUT_SECONDS = 7 * 24 * 3_600
MAX_DECLARED_OPERATION_TIMEOUT_SECONDS = 28_800
# Deadline for one external tool call (pueue, wt, git including fetch and push, gh, bd, systemctl),
# so a hung tool surfaces as an error; sized for checkout creation under disk contention.
CALL_TIMEOUT_SECONDS = 300
SYSTEMCTL_TIMEOUT_SECONDS = 30
# Hex characters shown of a run id's suffix, a commit, or a job id.
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
        and (0 if kind == "declared-operation" else 1)
        <= value
        <= maximum_timeout_seconds(kind)
    )
