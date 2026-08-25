from __future__ import annotations

import anyio
from mcp.shared.subscriptions import ResourceUpdated
from sinnix_agent_gateway.subscriptions import OwnerRevisionPublisher


class Bus:
    def __init__(self) -> None:
        self.updates: list[ResourceUpdated] = []

    async def publish(self, update: ResourceUpdated) -> None:
        self.updates.append(update)


class Runtime:
    def __init__(self) -> None:
        self.revisions = {
            "sinnix://projects/fixture": "commit-a",
            "sinnix://projects/fixture/task-authority": "beads-a",
        }

    def owner_revision_observations(self) -> dict[str, str]:
        return dict(self.revisions)


def test_idle_owner_revision_changes_publish_the_changed_component() -> None:
    runtime = Runtime()
    bus = Bus()
    publisher = OwnerRevisionPublisher(runtime, bus)

    async def scenario() -> None:
        await publisher.poll_once()
        assert bus.updates == []
        runtime.revisions["sinnix://projects/fixture"] = "commit-b"
        await publisher.poll_once()
        assert [update.uri for update in bus.updates] == ["sinnix://projects/fixture"]
        await publisher.poll_once()
        assert len(bus.updates) == 1

    anyio.run(scenario)
