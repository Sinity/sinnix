from __future__ import annotations

import json
from pathlib import Path
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


EVENTS_RESOURCE_URI = "sinnix://gateway/v2/events"


class EventSpoolPublisher:
    """Turn new rows of agentctl's event spool into MCP resource-update pushes.

    This publisher only keeps a best-effort cursor over the spool: a missed
    notification is recovered when the client reads the resource, and a
    partial final line is retained for the next pass.
    """

    def __init__(self, spool: Path, bus: Any) -> None:
        self.spool = spool
        self.bus = bus
        self._identity: tuple[int, int] | None = None
        self._offset = 0

    async def poll_once(self) -> int:
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

    async def run(self, interval_seconds: float) -> None:
        await self.poll_once()
        while True:
            await anyio.sleep(interval_seconds)
            await self.poll_once()
