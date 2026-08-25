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

    def wait(
        self,
        request: WaitRequest,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        deadline = self.clock() + request.timeout_seconds
        polls = 0
        current = self.resolver(request)
        while True:
            if current.satisfied:
                return {
                    "schema": "sinnix.gateway-wait.v1",
                    "outcome": "satisfied",
                    "target": request.target.value,
                    "ref": request.reference,
                    "polls": polls,
                    "evidence": dict(current.evidence),
                    "source_revision": current.source_revision,
                    "continuation": None,
                }
            if cancelled is not None and cancelled():
                return {
                    "schema": "sinnix.gateway-wait.v1",
                    "outcome": "cancelled",
                    "target": request.target.value,
                    "ref": request.reference,
                    "polls": polls,
                    "evidence": dict(current.evidence),
                    "source_revision": current.source_revision,
                    "continuation": self._continuation(request, current),
                }
            remaining = deadline - self.clock()
            if remaining <= 0:
                return {
                    "schema": "sinnix.gateway-wait.v1",
                    "outcome": "timeout",
                    "target": request.target.value,
                    "ref": request.reference,
                    "polls": polls,
                    "evidence": dict(current.evidence),
                    "source_revision": current.source_revision,
                    "continuation": self._continuation(request, current),
                }
            self.sleeper(min(request.poll_seconds, remaining))
            polls += 1
            current = self.resolver(request)

    async def wait_async(
        self,
        request: WaitRequest,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Poll through the MCP request task and observe its cancellation event."""
        deadline = self.clock() + request.timeout_seconds
        polls = 0

        async def resolve() -> WaitEvidence:
            return await anyio.to_thread.run_sync(
                self.resolver, request, abandon_on_cancel=True
            )

        if cancelled is not None and cancelled():
            return {
                "schema": "sinnix.gateway-wait.v1",
                "outcome": "cancelled",
                "target": request.target.value,
                "ref": request.reference,
                "polls": 0,
                "evidence": {},
                "source_revision": "cancelled",
                "continuation": self._continuation(
                    request, WaitEvidence(False, {}, "cancelled")
                ),
            }
        current = await resolve()
        while True:
            if current.satisfied:
                return {
                    "schema": "sinnix.gateway-wait.v1",
                    "outcome": "satisfied",
                    "target": request.target.value,
                    "ref": request.reference,
                    "polls": polls,
                    "evidence": dict(current.evidence),
                    "source_revision": current.source_revision,
                    "continuation": None,
                }
            if cancelled is not None and cancelled():
                return {
                    "schema": "sinnix.gateway-wait.v1",
                    "outcome": "cancelled",
                    "target": request.target.value,
                    "ref": request.reference,
                    "polls": polls,
                    "evidence": dict(current.evidence),
                    "source_revision": current.source_revision,
                    "continuation": self._continuation(request, current),
                }
            remaining = deadline - self.clock()
            if remaining <= 0:
                return {
                    "schema": "sinnix.gateway-wait.v1",
                    "outcome": "timeout",
                    "target": request.target.value,
                    "ref": request.reference,
                    "polls": polls,
                    "evidence": dict(current.evidence),
                    "source_revision": current.source_revision,
                    "continuation": self._continuation(request, current),
                }
            await anyio.sleep(min(request.poll_seconds, remaining))
            polls += 1
            current = await resolve()
