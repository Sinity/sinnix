"""Read-output limits must not become task-data truncation limits."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from sinnix_agent_gateway.beads import BeadsError
from test_beads import beads_service

REVISION = "0123456789abcdefghijklmnopqrstuv"


def owner_program(service, body):
    Path(service.config.beads_command).write_text(
        f"#!{sys.executable}\nimport json,sys,time\n" + body
    )


@pytest.mark.parametrize(
    "command",
    [
        ["sql", "SELECT fixture"],
        ["show", "fixture-1"],
        ["comments", "fixture-1"],
        ["list"],
    ],
)
def test_read_stdout_over_transport_cap_is_collected_without_truncation(
    tmp_path, command
):
    service, _ = beads_service(tmp_path)
    owner_program(
        service, "print(json.dumps({'text':'λ'*300000}, ensure_ascii=False))\n"
    )
    value = service._run(service.config.projects["fixture"], command, False)
    assert value == {"text": "λ" * 300000}
    assert len(json.dumps(value).encode()) > service.config.max_result_bytes


@pytest.mark.parametrize("write", [True, False])
def test_owner_stderr_remains_bounded(tmp_path, write):
    service, _ = beads_service(tmp_path)
    owner_program(service, "print('x'*300000, file=sys.stderr)\n")
    with pytest.raises(BeadsError) as caught:
        service._run(service.config.projects["fixture"], ["fixture"], write)
    assert caught.value.code == "response_bound"


@pytest.mark.parametrize("write", [True, False])
def test_large_owner_response_preserves_exit_failure_and_timeout(
    tmp_path, monkeypatch, write
):
    service, _ = beads_service(tmp_path)
    project = service.config.projects["fixture"]
    owner_program(
        service,
        "print(json.dumps({'text':'x'*300000})); print('owner rejected query',file=sys.stderr); sys.exit(7)\n",
    )
    with pytest.raises(BeadsError, match="owner rejected query") as caught:
        service._run(project, ["fixture"], write)
    assert caught.value.code == "owner_failed"
    owner_program(service, "time.sleep(2)\n")
    original = service.execution.run

    def short_timeout(command, profile, **kwargs):
        assert profile.timeout_seconds == 30
        return original(command, replace(profile, timeout_seconds=0.05), **kwargs)

    monkeypatch.setattr(service.execution, "run", short_timeout)
    with pytest.raises(BeadsError) as caught:
        service._run(project, ["fixture"], write)
    assert caught.value.code == "deadline"


def test_query_over_ten_thousand_rows_preserves_requested_immutable_pages(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    project = service.config.projects["fixture"]
    monkeypatch.setattr(
        service, "_attest", lambda *_: (project, {"revision": REVISION})
    )
    rows = [
        {"id": f"fixture-{i:05d}", "title": "item", "status": "open"}
        for i in range(10001)
    ]

    def read(_project, command, write, **kwargs):
        assert command == ["owner", "read"] and not write
        return {
            "revision": REVISION,
            "items": rows,
            "total": len(rows),
            "total_exact": True,
            "has_more": False,
        }

    monkeypatch.setattr(service, "_run", read)
    first = service.query(project_ids=["fixture"], view="all", limit=10000)
    assert len(first["items"]) == 10000 and first["page"]["total"] == 10001
    monkeypatch.setattr(
        service, "_run", lambda *a, **kw: pytest.fail("continuation reread the owner")
    )
    last = service.query(
        project_ids=["fixture"],
        view="all",
        limit=10000,
        cursor=first["page"]["next_cursor"],
    )
    assert len(last["items"]) == 1
    assert last["items"][0]["id"] == "fixture-10000"
