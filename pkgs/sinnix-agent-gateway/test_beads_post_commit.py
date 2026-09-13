"""Owner acknowledgements require no optional post-write enrichment."""

from __future__ import annotations

from conftest import call
from sinnix_agent_gateway.beads import BeadsError
from test_actions_beads import server_fixture
from test_beads import beads_service, commands


def test_native_acknowledgement_is_returned_without_post_write_reads(tmp_path):
    beads, log = beads_service(tmp_path)
    result = beads.native(
        "fixture",
        "createIssue",
        {"body": {"actor": "operator", "title": "task"}},
        write=True,
    )
    assert result["revision"] == "native-after"
    assert commands(log)[-1]["argv"][-3:] == ["owner", "call", "createIssue"]


def test_interrupted_native_mutation_is_not_automatically_replayed(
    tmp_path, monkeypatch
):
    server, _ = server_fixture(tmp_path)
    runtime = server._sinnix_revision_publisher.runtime
    calls = []

    def interrupted(*args, **kwargs):
        calls.append(args)
        raise BeadsError("owner reply lost after possible commit", "deadline")

    monkeypatch.setattr(runtime.beads, "native", interrupted)
    payload = {
        "project": {"project": "fixture"},
        "idempotency_key": "lost-reply",
        "body": {"actor": "operator", "title": "task"},
    }
    first = call(server, "beads.create", payload)
    assert first["result"]["outcome"] == "error"
    second = call(server, "beads.create", payload)
    assert second["result"]["outcome"] == "error"
    assert len(calls) == 1
