"""Read-output limits must not become task-data truncation limits."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from sinnix_agent_gateway.beads import BeadsError
from sinnix_agent_gateway.beads_analytics import Analytics
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


def test_large_write_response_confirms_one_applied_mutation(tmp_path):
    service, log = beads_service(tmp_path)
    runner = Path(service.config.beads_command)
    marker = "elif 'unrelated-write' in args:"
    script = runner.read_text()
    assert marker in script
    runner.write_text(
        script.replace(
            marker,
            """elif 'update' in args:
    assert '--readonly' not in args
    state['writes'] += 1; state['revision'] += 1
    pathlib.Path(state_path).write_text(json.dumps(state))
    print(json.dumps({'id':'fixture-1','notes':'x'*300000}))
""" + marker,
        )
    )
    result = service.change(
        "fixture",
        "update",
        {"id": "fixture-1", "patch": {"notes": {"text": "fixture update"}}},
    )
    assert result["mutation_state"] == "applied"
    assert result["uncertainty"] is None
    assert result["owner_result"]["notes"] == "x" * 300000
    assert result["before_revision"] != result["after_revision"]
    assert json.loads((tmp_path / "owner-state.json").read_text())["writes"] == 1
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    assert sum("update" in command for command in commands) == 1


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


def test_large_closure_reaches_final_artifact_instead_of_owner_response_bound(tmp_path):
    from sinnix_agent_gateway.actions import BY_NAME
    from sinnix_agent_gateway.app import Runtime
    from test_results import _execute

    service, _ = beads_service(tmp_path)
    owner_program(
        service,
        """query=sys.argv[-1]
if 'acceptance_criteria' in query:
    print(json.dumps([{'id':f'fixture-{i}', 'status':'closed', 'issue_type':'task',
        'metadata':{'closure_role':'leaf','payload':'m'*4096},
        'acceptance_criteria':'a'*4096, 'bead_revision':'7773497739344011640'} for i in range(100)]))
else: print('[]')
""",
    )
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    result = analytical.closure(
        [f"fixture-{i}" for i in range(100)],
        relation_filter="blocks",
        direction="prerequisites",
        max_nodes=100,
        max_depth=1,
    )
    assert len(result["nodes"]) == 100
    assert result["coverage"]["complete"] is True
    assert all(row["bead_revision"] == "7773497739344011640" for row in result["nodes"])
    assert all(len(row["acceptance_criteria"]) == 4096 for row in result["nodes"])
    assert len(json.dumps(result).encode()) > 262144
    runtime = Runtime.create(service.config, "operator")
    response = _execute(
        runtime, BY_NAME["beads.closure"], lambda: result, {"fixture": "large"}
    )
    assert response["result"]["outcome"] == "ok"
    assert response["data"]["artifact"]["ref"].startswith("sinnix://artifacts/")
    assert response["meta"]["artifact_refs"] == [response["data"]["artifact"]["ref"]]


def test_query_over_ten_thousand_rows_preserves_requested_immutable_pages(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    project = service.config.projects["fixture"]
    monkeypatch.setattr(
        service, "_attest", lambda *_: (project, {"revision": REVISION})
    )
    monkeypatch.setattr(
        service, "task_authority_status", lambda *_: {"revision": REVISION}
    )
    owner_program(
        service,
        """query=sys.argv[-1]
if 'COUNT(*)' in query: print('[{"count":10001}]')
else:
    assert ' LIMIT ' not in query
    print(json.dumps([{'id':f'fixture-{i:05}', 'status':'open', 'title':'fixture', 'priority':1} for i in range(10001)]))
""",
    )
    first = service.query(project_ids=["fixture"], view="all", limit=2)
    assert first["page"]["total"] == 10001
    assert first["coverage"]["fixture"]["state"] == "complete"
    assert len(first["items"]) == 2
    assert first["items"][0]["id"] == "fixture-00000"
    owner_program(service, "raise SystemExit('continuation must not reread owner')\n")
    second = service.query(
        project_ids=["fixture"],
        view="all",
        limit=2,
        cursor=first["page"]["next_cursor"],
    )
    assert second["items"][0]["id"] == "fixture-00002"
    assert second["page"]["total"] == 10001
    from sinnix_agent_gateway.actions.beads import QueryInput

    assert QueryInput(view="all", limit=1000).limit == 1000
    large_page = service.query(
        project_ids=["fixture"],
        view="all",
        limit=1000,
        cursor=second["page"]["next_cursor"],
    )
    assert len(large_page["items"]) == 1000
    assert large_page["items"][0]["id"] == "fixture-00004"
    assert large_page["page"]["next_offset"] == 1004


@pytest.mark.parametrize(
    "code,message",
    [
        ("response_bound", "Beads response exceeded configured bound"),
        ("deadline", "Beads operation timed out"),
        ("owner_failed", "access denied for issues table"),
        ("owner_failed", "syntax error near row_lock"),
        (
            "owner_failed",
            'column "other_field" could not be found in any table in scope',
        ),
    ],
)
def test_owner_failures_do_not_masquerade_as_missing_row_revision(
    tmp_path, monkeypatch, code, message
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    calls = []

    def fail(statement):
        calls.append(statement)
        raise BeadsError(message, code)

    monkeypatch.setattr(analytical, "sql", fail)
    with pytest.raises(BeadsError) as caught:
        analytical.closure(
            ["fixture-1"],
            relation_filter="blocks",
            direction="prerequisites",
            max_nodes=10,
            max_depth=1,
        )
    assert caught.value.code == code
    assert len(calls) == 1


def test_historical_row_revision_fallback_accepts_exact_dolt_missing_column(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    message = 'column "row_lock" could not be found in any table in scope'
    node_reads = []

    def sql(statement):
        assert f"AS OF '{REVISION}'" in statement
        if "acceptance_criteria" not in statement:
            return []
        node_reads.append(statement)
        if "CAST(row_lock AS CHAR)" in statement:
            raise BeadsError(message, "owner_failed")
        return [{"id": "fixture-1", "status": "closed"}]

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.closure(
        ["fixture-1"],
        relation_filter="blocks",
        direction="prerequisites",
        max_nodes=10,
        max_depth=1,
    )
    assert result["coverage"]["complete"] is True
    assert result["nodes"][0]["bead_revision"] is None
    assert result["nodes"][0]["bead_revision_unavailable_reason"] == message
    assert len(node_reads) == 2
    assert node_reads[1] == node_reads[0].replace(
        ", CAST(row_lock AS CHAR) AS bead_revision", ""
    )


def test_explicit_historical_includes_return_all_rows_at_one_revision(tmp_path):
    service, _ = beads_service(tmp_path)
    owner_program(
        service,
        f"""query=sys.argv[-1]
assert "AS OF '{REVISION}'" in query
assert ' LIMIT ' not in query
print(json.dumps([{{'id':i,'text':'fixture'*300}} for i in range(301)]))
""",
    )
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    result = analytical.includes("fixture-1", {"comments", "children", "dependencies"})
    for included in result.values():
        assert included["count"] == 301
        assert included["state"] == "complete"
        assert included["truncated"] is False
        assert included["items"][-1]["id"] == 300
        assert included["revision"] == REVISION


def test_explicit_live_history_and_children_do_not_apply_hidden_limits(tmp_path):
    service, _ = beads_service(tmp_path)
    owner_program(
        service,
        """args=sys.argv[1:]
assert args[args.index('--limit')+1]=='0'
if '--max-rows' in args: assert args[args.index('--max-rows')+1]=='0'
print(json.dumps([{'id':i} for i in range(301)]))
""",
    )
    result = service._includes(
        service.config.projects["fixture"],
        "fixture",
        "fixture-1",
        {"history", "events", "children"},
    )
    assert all(len(rows) == 301 for rows in result.values())
