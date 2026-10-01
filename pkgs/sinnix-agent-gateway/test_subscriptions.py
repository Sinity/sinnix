from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import anyio
import pytest
from mcp.shared.subscriptions import ResourceUpdated
from sinnix_agent_gateway.app import create_server
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.subscriptions import (
    EVENTS_RESOURCE_URI,
    DemandAwareSubscriptionBus,
    EventSpoolPublisher,
    OwnerRevisionPublisher,
)


class Bus:
    def __init__(self) -> None:
        self.updates: list[ResourceUpdated] = []
        self.listeners = []

    async def publish(self, update: ResourceUpdated) -> None:
        self.updates.append(update)

    def subscribe(self, listener) -> Callable[[], None]:
        self.listeners.append(listener)
        active = True

        def remove() -> None:
            nonlocal active
            if active:
                active = False
                self.listeners.remove(listener)

        return remove


class Runtime:
    def __init__(self) -> None:
        self.observation_calls = 0
        self.revisions = {
            "sinnix://projects/fixture": "commit-a",
            "sinnix://projects/fixture/task-authority": "beads-a",
        }

    def owner_revision_observations(self) -> dict[str, str]:
        self.observation_calls += 1
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


def test_server_lifespan_survives_optional_publisher_failure(tmp_path: Path) -> None:
    server = create_server(
        GatewayConfig(state_dir=tmp_path / "state", projects={}), "operator"
    )
    publisher = server._sinnix_revision_publisher
    publisher._should_poll = lambda: True
    attempts = 0

    def flaky_observation() -> dict[str, str]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("owner unavailable")
        return {}

    publisher.runtime.owner_revision_observations = flaky_observation

    async def scenario() -> None:
        async with server.lifespan(server):
            with anyio.fail_after(2):
                while publisher.status()["state"] != "degraded":
                    await anyio.sleep(0.001)
            response = await server.call_tool("gateway.catalog", {"query": "status"})
            assert response.structured_content["result"]["outcome"] == "ok"
            status = await server.call_tool("gateway.status", {})
            health = status.structured_content["data"]["subscription_publishers"]
            assert health["owner_revisions"]["last_error"] == "OSError"
            assert attempts == 1  # Status must use the cached publisher state.
            with anyio.fail_after(2):
                while publisher.status()["state"] != "ready":
                    await anyio.sleep(0.001)

    anyio.run(scenario)


def test_owner_observation_is_demand_driven_and_reconnects_cleanly() -> None:
    runtime = Runtime()
    bus = Bus()
    publisher = OwnerRevisionPublisher(runtime, bus, should_poll=lambda: False)

    async def scenario() -> None:
        await publisher.poll_once()
        assert runtime.observation_calls == 0

    anyio.run(scenario)


def test_demand_aware_bus_tracks_cancellation_and_reconnection() -> None:
    delegate = Bus()
    bus = DemandAwareSubscriptionBus(delegate)
    listeners = []

    def listener(event) -> None:
        listeners.append(event)

    remove = bus.subscribe(listener)
    assert bus.has_subscribers()
    remove()
    remove()
    assert not bus.has_subscribers()
    remove_again = bus.subscribe(listener)
    assert bus.has_subscribers()
    remove_again()
    assert not bus.has_subscribers()


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


def test_event_spool_demand_edges_skip_unobserved_backlog(tmp_path) -> None:
    spool = tmp_path / "events.jsonl"
    spool.write_text('{"job_id":"old"}\n')
    bus = Bus()
    demand = False
    publisher = EventSpoolPublisher(spool, bus, should_poll=lambda: demand)

    async def scenario() -> None:
        nonlocal demand
        assert await publisher.poll_once() == 0
        demand = True
        assert await publisher.poll_once() == 0
        with spool.open("a") as handle:
            handle.write('{"job_id":"new"}\n')
        assert await publisher.poll_once() == 1
        demand = False
        assert await publisher.poll_once() == 0
        with spool.open("a") as handle:
            handle.write('{"job_id":"while-away"}\n')
        demand = True
        assert await publisher.poll_once() == 0
        with spool.open("a") as handle:
            handle.write('{"job_id":"after-reconnect"}\n')
        assert await publisher.poll_once() == 1

    anyio.run(scenario)


def test_owner_failure_recovers_and_cancellation_stops_run() -> None:
    runtime = Runtime()
    bus = Bus()
    publisher = OwnerRevisionPublisher(runtime, bus)
    original = runtime.owner_revision_observations
    attempts = 0

    def flaky() -> dict[str, str]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("owner unavailable")
        return original()

    runtime.owner_revision_observations = flaky

    async def scenario() -> None:
        async with anyio.create_task_group() as group:
            group.start_soon(publisher.run, 0.01)
            with anyio.fail_after(1):
                while publisher.status()["state"] != "degraded":
                    await anyio.sleep(0.001)
            assert publisher.status()["last_error"] == "OSError"
            with anyio.fail_after(1):
                while publisher.status()["state"] != "ready":
                    await anyio.sleep(0.001)
            assert publisher.status()["last_success_age_seconds"] is not None
            runtime.revisions["sinnix://projects/fixture"] = "commit-b"
            with anyio.fail_after(1):
                while not bus.updates:
                    await anyio.sleep(0.001)
            assert bus.updates[0].uri == "sinnix://projects/fixture"
            group.cancel_scope.cancel()

    anyio.run(scenario)


@pytest.mark.parametrize("failure", ["stat", "open", "read", "publish"])
def test_event_spool_failures_retry_without_losing_row_or_replaying_backlog(
    tmp_path: Path, failure: str
) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"job_id":"old"}\n')
    bus = Bus()
    demand = False
    publisher = EventSpoolPublisher(path, bus, should_poll=lambda: demand)

    class FaultyHandle:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def seek(self, offset):
            return self.handle.seek(offset)

        def tell(self):
            return self.handle.tell()

        def readline(self):
            raise OSError("read unavailable")

    class FaultySpool:
        fail = True

        def stat(self):
            if self.fail and failure == "stat":
                raise OSError("stat unavailable")
            return path.stat()

        def open(self, mode):
            if self.fail and failure == "open":
                raise OSError("open unavailable")
            handle = path.open(mode)
            return FaultyHandle(handle) if self.fail and failure == "read" else handle

    spool = FaultySpool()
    publisher.spool = spool
    original_publish = bus.publish

    async def flaky_publish(update):
        if spool.fail and failure == "publish":
            raise OSError("publish unavailable")
        await original_publish(update)

    bus.publish = flaky_publish

    async def scenario() -> None:
        nonlocal demand
        assert await publisher.poll_once() == 0
        demand = True
        # Subscription starts at the current end, never at the old row.
        assert await publisher.poll_once() == 0
        path.write_text(path.read_text() + '{"job_id":"new"}\n')
        async with anyio.create_task_group() as group:
            group.start_soon(publisher.run, 0.01)
            with anyio.fail_after(1):
                while publisher.status()["state"] != "degraded":
                    await anyio.sleep(0.001)
            assert bus.updates == []
            spool.fail = False
            with anyio.fail_after(1):
                while publisher.status()["state"] != "ready":
                    await anyio.sleep(0.001)
            assert [item.uri for item in bus.updates] == [EVENTS_RESOURCE_URI]
            group.cancel_scope.cancel()

    anyio.run(scenario)
