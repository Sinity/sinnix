from __future__ import annotations

import anyio
import pytest

from sinnix_agent_gateway.calllog import HttpRequest, RUN_ID, run_actor, run_id


@pytest.mark.parametrize("header, expected", [
    ("wfr_fixture/command", "wfr_fixture"),
    ("wfr_fixture", "wfr_fixture"),
    ("local-command", None),
    ("wfr_bad:actor/command", None),
    (None, None),
])
def test_tunnel_run_label(header, expected):
    assert run_id(HttpRequest(None, header, None)) == expected


def test_concurrent_run_context_reaches_threads_and_resets():
    async def scenario():
        async def call(value):
            token = RUN_ID.set(value)
            try:
                await anyio.sleep(0)
                assert await anyio.to_thread.run_sync(run_actor) == f"sinnix-gateway:operator:{value}"
            finally:
                RUN_ID.reset(token)
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(call, "wfr_one")
            tasks.start_soon(call, "wfr_two")
        assert run_actor() == "sinnix-gateway:operator"
    anyio.run(scenario)
