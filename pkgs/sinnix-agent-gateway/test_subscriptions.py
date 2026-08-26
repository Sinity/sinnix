from __future__ import annotations

import anyio
from mcp.shared.subscriptions import ResourceUpdated
from sinnix_agent_gateway.subscriptions import (
    EVENTS_RESOURCE_URI,
    EventSpoolPublisher,
    OwnerRevisionPublisher,
)


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


def test_event_spool_publishes_once_per_complete_record_and_waits_for_partial_line(
    tmp_path,
) -> None:
    spool = tmp_path / "events.jsonl"
    bus = Bus()
    publisher = EventSpoolPublisher(spool, bus)

    async def scenario() -> None:
        spool.write_bytes(b'{"job_id":"one"}\n{"job_id":"two"')
        assert await publisher.poll_once() == 1
        assert [item.uri for item in bus.updates] == [EVENTS_RESOURCE_URI]

        with spool.open("ab") as handle:
            handle.write(b"}\n")
        assert await publisher.poll_once() == 1
        assert len(bus.updates) == 2
        assert await publisher.poll_once() == 0

    anyio.run(scenario)


def test_event_spool_cursor_restarts_after_rotation(tmp_path) -> None:
    spool = tmp_path / "events.jsonl"
    bus = Bus()
    publisher = EventSpoolPublisher(spool, bus)

    async def scenario() -> None:
        spool.write_text('{"job_id":"before"}\n')
        assert await publisher.poll_once() == 1
        rotated = spool.with_suffix(".jsonl.old")
        spool.replace(rotated)
        spool.write_text('{"job_id":"after"}\n')
        assert await publisher.poll_once() == 1
        assert len(bus.updates) == 2

    anyio.run(scenario)
