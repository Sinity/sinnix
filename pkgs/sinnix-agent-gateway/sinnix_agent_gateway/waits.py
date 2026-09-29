from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping

import anyio


class WaitTarget(StrEnum):
    JOB_TERMINAL = "job_terminal"
    BEAD_STATUS = "bead_status"
    BEAD_REVISION = "bead_revision"
    UNIT_STATE = "unit_state"
    FILE_HASH = "file_hash"
    CAPTURE_FRESHNESS = "capture_freshness"
    RECEIPT_APPEARANCE = "receipt_appearance"


@dataclass(frozen=True)
class WaitRequest:
    target: WaitTarget
    reference: str
    expected: Mapping[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30
    poll_seconds: float = 0.25

    def __post_init__(self) -> None:
        if not isinstance(self.reference, str) or not self.reference:
            raise ValueError("wait reference is required")
        if not isinstance(self.expected, Mapping):
            raise ValueError("wait expected state must be an object")
        if (
            not isinstance(self.timeout_seconds, int)
            or isinstance(self.timeout_seconds, bool)
            or not 1 <= self.timeout_seconds <= 300
        ):
            raise ValueError("wait timeout_seconds must be 1-300")
        if (
            not isinstance(self.poll_seconds, (int, float))
            or isinstance(self.poll_seconds, bool)
            or not 0.01 <= self.poll_seconds <= 5
        ):
            raise ValueError("wait poll_seconds must be 0.01-5")


@dataclass(frozen=True)
class WaitEvidence:
    satisfied: bool
    evidence: Mapping[str, Any]
    source_revision: str


class BoundedWaitService:
    """Poll one owner synchronously within a deadline. Never starts work."""

    def __init__(
        self,
        resolver: Callable[[WaitRequest], WaitEvidence],
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.resolver = resolver
        self.clock = clock
        self.sleeper = sleeper

    @staticmethod
    def _continuation(request: WaitRequest, evidence: WaitEvidence) -> str:
        payload = {
            "target": request.target.value,
            "reference": request.reference,
            "expected": dict(request.expected),
            "source_revision": evidence.source_revision,
        }
        return hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()

    @staticmethod
    def _answer(
        request: WaitRequest,
        outcome: str,
        polls: int,
        current: WaitEvidence,
        *,
        late: bool = False,
    ) -> dict[str, Any]:
        evidence = dict(current.evidence)
        if late:
            # The observation finished after the deadline. It is current
            # evidence, but it cannot satisfy a wait that had already ended.
            evidence["observed_after_deadline"] = True
            evidence["observed_satisfied"] = current.satisfied
        return {
            "schema": "sinnix.gateway-wait.v1",
            "outcome": outcome,
            "target": request.target.value,
            "ref": request.reference,
            "polls": polls,
            "evidence": evidence,
            "source_revision": current.source_revision,
            "continuation": None
            if outcome == "satisfied"
            else BoundedWaitService._continuation(request, current),
        }

    def wait(
        self,
        request: WaitRequest,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Poll until satisfied or the deadline passes.

        The deadline applies to each observation, not only between polls: an
        observation that completes after it is reported as evidence of a
        timeout, never as satisfaction.
        """
        deadline = self.clock() + request.timeout_seconds
        polls = 0
        while True:
            current = self.resolver(request)
            if self.clock() > deadline:
                return self._answer(request, "timeout", polls, current, late=True)
            if current.satisfied:
                return self._answer(request, "satisfied", polls, current)
            if cancelled is not None and cancelled():
                return self._answer(request, "cancelled", polls, current)
            remaining = deadline - self.clock()
            if remaining <= 0:
                return self._answer(request, "timeout", polls, current)
            self.sleeper(min(request.poll_seconds, remaining))
            polls += 1

    async def wait_async(
        self,
        request: WaitRequest,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Poll through the MCP request task and observe its cancellation event.

        Each observation runs under the remaining budget; one still running at
        the deadline is abandoned and the wait times out on the last evidence.
        """
        deadline = self.clock() + request.timeout_seconds
        polls = 0
        pending = WaitEvidence(False, {}, "unobserved")
        if cancelled is not None and cancelled():
            return self._answer(
                request, "cancelled", 0, WaitEvidence(False, {}, "cancelled")
            )
        current = pending
        while True:
            observed: WaitEvidence | None = None
            with anyio.move_on_after(max(0.0, deadline - self.clock())):
                observed = await anyio.to_thread.run_sync(
                    self.resolver, request, abandon_on_cancel=True
                )
            if observed is None:
                return self._answer(request, "timeout", polls, current)
            current = observed
            if self.clock() > deadline:
                return self._answer(request, "timeout", polls, current, late=True)
            if current.satisfied:
                return self._answer(request, "satisfied", polls, current)
            if cancelled is not None and cancelled():
                return self._answer(request, "cancelled", polls, current)
            remaining = deadline - self.clock()
            if remaining <= 0:
                return self._answer(request, "timeout", polls, current)
            await anyio.sleep(min(request.poll_seconds, remaining))
            polls += 1
