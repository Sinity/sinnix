from __future__ import annotations

import json
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


class OwnerRevisionPublisher:
    """Publish resource updates from owner revision observations, not responses."""

    def __init__(
        self,
        runtime: Any,
        bus: Any,
        *,
        should_poll: Callable[[], bool] | None = None,
    ) -> None:
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

    async def run(self, interval_seconds: float) -> None:
        await self.poll_once()
        while True:
            await anyio.sleep(interval_seconds)
            await self.poll_once()


EVENTS_RESOURCE_URI = "sinnix://gateway/v2/events"


class EventSpoolPublisher:
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
                self._offset = handle.tell()
                try:
                    event = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                await self.bus.publish(ResourceUpdated(uri=EVENTS_RESOURCE_URI))
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

    async def run(self, interval_seconds: float) -> None:
        await self.poll_once()
        while True:
            await anyio.sleep(interval_seconds)
            await self.poll_once()
