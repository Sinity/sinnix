"""Beads transport and observation persistence against synthetic native envelopes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sinnix_agent_gateway.beads import BeadsError, BeadsService
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import (
    GatewayConfig,
    ProjectConfig,
    TaskAuthorityConfig,
)


def beads_service(tmp_path: Path, principal: str = "operator"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project = tmp_path / "project"
    project.mkdir()
    log = tmp_path / "commands.jsonl"
    state = tmp_path / "owner-state.json"
    state.write_text(
        json.dumps(
            {
                "revision": "working-0",
                "items": [
                    {
                        "id": "fixture-1",
                        "title": "first",
                        "status": "open",
                        "revision": "native-row-1",
                    },
                    {
                        "id": "fixture-2",
                        "title": "second",
                        "status": "open",
                        "revision": "native-row-2",
                    },
                ],
            }
        )
    )
    runner = tmp_path / "bd"
    runner.write_text(f"""#!{sys.executable}
import json,pathlib,sys
args=sys.argv[1:]
payload=json.load(sys.stdin) if 'owner' in args else None
with pathlib.Path({str(log)!r}).open('a') as output:
    output.write(json.dumps({{'argv':args,'payload':payload}})+'\\n')
root=args[args.index('--directory')+1]
state=json.loads(pathlib.Path({str(state)!r}).read_text())
if args[-1]=='where': value={{'path':root+'/.beads','database_path':root+'/.beads/dolt'}}
elif args[-1]=='status': value={{'summary':{{'total_issues':len(state['items'])}}}}
elif args[-2:]==['owner','read']:
    rows=state['items']
    if payload.get('roots'): rows=[r for r in rows if r['id'] in payload['roots']]
    if payload.get('aggregate') is not None: rows=[{{'count':len(rows)}}]
    value={{'items':rows,'revision':payload.get('at') or state['revision'],'total':len(rows),
           'total_exact':True,'has_more':False,'closure':{{'complete':True}},
           'temporal':{{'requested':payload.get('at'),'known_at':None}}}}
elif 'call' in args:
    if payload.get('body',{{}}).get('actor')=='conflict':
        print(json.dumps({{'code':'precondition_failed','detail':'row revision changed'}}));sys.exit(1)
    value={{'native_operation':args[-1],'request':payload,'revision':'native-after'}}
else: value={{'ok':True}}
print(json.dumps(value))
""")
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture",
                path=project,
                observer_read=True,
                task_authority=TaskAuthorityConfig(
                    owner="beads",
                    workspace=project / ".beads",
                    database=project / ".beads/dolt",
                ),
            )
        },
        beads_command=str(runner),
    )
    return BeadsService(config, Principal.for_name(principal)), log


def commands(log: Path):
    return [json.loads(line) for line in log.read_text().splitlines()]


def test_query_preserves_native_request_and_continues_frozen_observation(tmp_path):
    beads, log = beads_service(tmp_path, "observer")
    arguments = {
        "project_ids": ["fixture"],
        "filters": {"status": "open"},
        "expression": 'title = "needle"',
        "native_filters": {"label_any": ["one", "two"]},
        "includes": ["comments"],
        "limit": 1,
    }
    first = beads.query(**arguments)
    query = [
        row
        for row in commands(log)
        if row["payload"] and row["payload"].get("expression")
    ][0]
    assert query["payload"]["filters"] == arguments["filters"]
    assert query["payload"]["native_filters"] == arguments["native_filters"]
    assert query["payload"]["include"] == ["comments"]
    assert query["payload"]["projection"] == "summary"
    before = len(commands(log))
    (tmp_path / "owner-state.json").write_text(
        json.dumps({"revision": "working-1", "items": []})
    )
    second = beads.query(**arguments, cursor=first["page"]["next_cursor"])
    assert second["items"][0]["id"] == "fixture-2"
    assert len(commands(log)) == before
    assert first["items"][0]["native"]["revision"] == "native-row-1"
    assert beads.query(**arguments)["items"] == []


def test_get_and_closure_pin_exact_native_revision_and_keep_native_evidence(tmp_path):
    beads, log = beads_service(tmp_path, "observer")
    value = beads.get("fixture", "fixture-1", as_of="historic", includes=["history"])
    assert value["task_revision"] == "historic"
    value = beads.campaign_closure(
        "fixture", ["fixture-1"], at="historic", relation="blocks"
    )
    assert value["owner_product"]["temporal"]["known_at"] is None
    payload = commands(log)[-1]["payload"]
    assert payload["direction"] == "dependencies" and payload["relations"] == ["blocks"]
    assert payload["provenance"] is True


def test_native_mutation_preserves_body_and_owner_preconditions(tmp_path):
    beads, log = beads_service(tmp_path)
    payload = {
        "path": {"id": "fixture-1"},
        "body": {
            "actor": "operator",
            "expected_version": "native-row-1",
            "patch": {"notes": "new"},
        },
    }
    value = beads.native("fixture", "updateIssue", payload, write=True)
    assert value["request"] == payload
    assert commands(log)[-1]["payload"] == payload
    assert "--readonly" not in commands(log)[-1]["argv"]
    with pytest.raises(BeadsError) as raised:
        beads.native(
            "fixture", "updateIssue", {"body": {"actor": "conflict"}}, write=True
        )
    assert raised.value.code == "precondition_failed"
    assert raised.value.details["owner_error"]["detail"] == "row revision changed"


def test_authority_and_write_policy_are_checked_before_native_action(tmp_path):
    beads, log = beads_service(tmp_path, "observer")
    with pytest.raises(PolicyError):
        beads.native("fixture", "createIssue", {}, write=True)
    assert not log.exists()
