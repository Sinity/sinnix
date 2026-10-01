from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anyio
from mcp.shared.subscriptions import ResourceUpdated, ServerEvent


class DemandAwareSubscriptionBus:
    """Track open MCP listen streams while preserving the bus contract."""

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self._subscriber_count = 0

    async def publish(self, event: ServerEvent) -> None:
        await self.delegate.publish(event)

    def subscribe(self, listener: Callable[[ServerEvent], None]) -> Callable[[], None]:
        unsubscribe = self.delegate.subscribe(listener)
        self._subscriber_count += 1
        active = True

        def remove() -> None:
            nonlocal active
            if not active:
                return
            active = False
            self._subscriber_count -= 1
            unsubscribe()

        return remove

    def has_subscribers(self) -> bool:
        return self._subscriber_count > 0


class SupervisedPublisher:
    """Keep optional notification failures outside the server task group."""

    def __init__(self) -> None:
        self.last_success_at: float | None = None
        self.last_error: str | None = None
        self.consecutive_failures = 0

    def status(self) -> dict[str, Any]:
        return {
            "state": (
                "degraded"
                if self.last_error
                else "ready" if self.last_success_at is not None else "pending"
            ),
            "last_success_age_seconds": (
                max(0.0, time.monotonic() - self.last_success_at)
                if self.last_success_at is not None
                else None
            ),
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }

    async def run(self, interval_seconds: float) -> None:
        while True:
            try:
                await self.poll_once()
            except Exception as exc:
                # AnyIO cancellation derives from BaseException and must escape.
                self.last_error = type(exc).__name__
                self.consecutive_failures += 1
                delay = min(
                    30.0, interval_seconds * 2 ** min(self.consecutive_failures, 5)
                )
            else:
                self.last_success_at = time.monotonic()
                self.last_error = None
                self.consecutive_failures = 0
                delay = interval_seconds
            await anyio.sleep(delay)


class OwnerRevisionPublisher(SupervisedPublisher):
    """Publish resource updates from owner revision observations, not responses."""

    def __init__(
        self,
        runtime: Any,
        bus: Any,
        *,
        should_poll: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.bus = bus
        self._revisions: dict[str, str] = {}
        self._should_poll = should_poll or getattr(bus, "has_subscribers", None)

    async def poll_once(self) -> None:
        if self._should_poll is not None and not self._should_poll():
            return
        observations = self.runtime.owner_revision_observations()
        for reference, revision in observations.items():
            previous = self._revisions.get(reference)
            if previous is not None and previous != revision:
                await self.bus.publish(ResourceUpdated(uri=reference))
            self._revisions[reference] = revision


EVENTS_RESOURCE_URI = "sinnix://gateway/v2/events"


class EventSpoolPublisher(SupervisedPublisher):
    """Turn new rows of agentctl's event spool into MCP resource-update pushes.

    This publisher only keeps a best-effort cursor over the spool: a missed
    notification is recovered when the client reads the resource, and a
    partial final line is retained for the next pass.
    """

    def __init__(
        self,
        spool: Path,
        bus: Any,
        *,
        should_poll: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__()
        self.spool = spool
        self.bus = bus
        self._identity: tuple[int, int] | None = None
        self._offset = 0
        self._should_poll = should_poll or getattr(bus, "has_subscribers", None)
        self._demand_active = self._should_poll is None

    async def poll_once(self) -> int:
        if self._should_poll is not None:
            demanded = self._should_poll()
            if not demanded:
                self._demand_active = False
                return 0
            if not self._demand_active:
                self._prime_cursor()
                self._demand_active = True
                return 0
        try:
            stat = self.spool.stat()
        except FileNotFoundError:
            return 0
        identity = (stat.st_dev, stat.st_ino)
        if self._identity != identity or stat.st_size < self._offset:
            self._identity = identity
            self._offset = 0
        published = 0
        with self.spool.open("rb") as handle:
            handle.seek(self._offset)
            while True:
                start = handle.tell()
                line = handle.readline()
                if not line or not line.endswith(b"\n"):
                    self._offset = start
                    break
                end = handle.tell()
                try:
                    event = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._offset = end
                    continue
                if not isinstance(event, dict):
                    self._offset = end
                    continue
                await self.bus.publish(ResourceUpdated(uri=EVENTS_RESOURCE_URI))
                self._offset = end
                published += 1
        return published

    def _prime_cursor(self) -> None:
        """Skip backlog accumulated while no listen stream was open."""
        try:
            stat = self.spool.stat()
        except FileNotFoundError:
            self._identity = None
            self._offset = 0
            return
        self._identity = (stat.st_dev, stat.st_ino)
        self._offset = stat.st_size
