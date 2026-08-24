from __future__ import annotations

import anyio

from sinnix_agent_gateway.waits import BoundedWaitService, WaitEvidence, WaitRequest, WaitTarget


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def test_timeout_returns_current_evidence_and_continuation_without_background_work() -> None:
    clock = Clock()
    service = BoundedWaitService(
        lambda _request: WaitEvidence(False, {"phase": "running"}, "rev-running"),
        clock=clock.now,
        sleeper=clock.sleep,
    )

    result = service.wait(WaitRequest(WaitTarget.JOB_TERMINAL, "sinnix://jobs/job-1", timeout_seconds=1, poll_seconds=0.4))

    assert result["outcome"] == "timeout"
    assert result["evidence"] == {"phase": "running"}
    assert result["continuation"]
    assert clock.value == 1.0


def test_cancellation_returns_evidence_without_spawning_work() -> None:
    service = BoundedWaitService(lambda _request: WaitEvidence(False, {"status": "open"}, "rev"), sleeper=lambda _seconds: None)
    result = service.wait(
        WaitRequest(WaitTarget.BEAD_STATUS, "sinnix://projects/p/beads/b", timeout_seconds=10),
        cancelled=lambda: True,
    )
    assert result["outcome"] == "cancelled"
    assert result["evidence"]["status"] == "open"
    assert result["continuation"]


def test_async_wait_observes_request_cancellation_between_owner_polls() -> None:
    calls = 0

    def resolve(_request: WaitRequest) -> WaitEvidence:
        nonlocal calls
        calls += 1
        return WaitEvidence(False, {"poll": calls}, f"rev-{calls}")

    service = BoundedWaitService(resolve)

    async def scenario() -> None:
        result = await service.wait_async(
            WaitRequest(WaitTarget.BEAD_STATUS, "sinnix://projects/p/beads/b", timeout_seconds=2, poll_seconds=0.01),
            cancelled=lambda: calls >= 2,
        )
        assert result["outcome"] == "cancelled"
        assert result["evidence"] == {"poll": 2}

    anyio.run(scenario)
