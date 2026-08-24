from __future__ import annotations

from typing import Any

import anyio
from mcp.shared.subscriptions import ResourceUpdated


class OwnerRevisionPublisher:
    """Publish resource updates from owner revision observations, not responses."""

    def __init__(self, runtime: Any, bus: Any) -> None:
        self.runtime = runtime
        self.bus = bus
        self._revisions: dict[str, str] = {}

    async def poll_once(self) -> None:
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
