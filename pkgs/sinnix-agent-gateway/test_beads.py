"""Beads transport and observation persistence against synthetic native envelopes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sinnix_agent_gateway.beads import BeadsError, BeadsService
from sinnix_agent_gateway.config import (
    GatewayConfig,
    ProjectConfig,
    TaskAuthorityConfig,
)


def beads_service(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project = tmp_path / "project"
    project.mkdir()
    authority = tmp_path / "tasks" / ".beads"
    (authority / "dolt").mkdir(parents=True)
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
import json,pathlib,sys,os
args=sys.argv[1:]
payload=json.load(sys.stdin) if 'owner' in args else None
with pathlib.Path({str(log)!r}).open('a') as output:
    output.write(json.dumps({{'argv':args,'payload':payload,'actor':os.environ.get('BEADS_ACTOR')}})+'\\n')
root=args[args.index('--directory')+1]
state=json.loads(pathlib.Path({str(state)!r}).read_text())
if args[-1]=='where': value={{'path':{str(authority)!r},'database_path':{str(authority / "dolt")!r}}}
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
                task_authority=TaskAuthorityConfig(
                    owner="beads",
                    workspace=authority,
                    database=authority / "dolt",
                ),
            )
        },
        beads_command=str(runner),
    )
    return BeadsService(config), log


def commands(log: Path):
    return [json.loads(line) for line in log.read_text().splitlines()]


def test_task_reads_and_mutations_do_not_require_source_checkout(tmp_path):
    beads, log = beads_service(tmp_path)
    project = beads.config.projects["fixture"]
    project.path.rmdir()
    assert beads.query(project_ids=["fixture"], view="all")["items"]
    value = beads.native(
        "fixture",
        "updateIssue",
        {
            "path": {"id": "fixture-1"},
            "body": {"actor": "operator", "patch": {"notes": "neutral fixture"}},
        },
        write=True,
    )
    assert value["native_operation"] == "updateIssue"
    for call in commands(log):
        argv = call["argv"]
        assert argv[argv.index("--directory") + 1] == str(
            project.task_authority.workspace
        )
        assert argv[argv.index("--db") + 1] == str(project.task_authority.database)
    assert not project.path.exists()


def test_query_preserves_native_request_and_continues_frozen_observation(tmp_path):
    beads, log = beads_service(tmp_path)
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
    beads, log = beads_service(tmp_path)
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


@pytest.mark.parametrize("field", ["created", "updated", "closed"])
@pytest.mark.parametrize(
    "old,new",
    [
        ("2026-10-16T01:30:00+02:00", "2026-10-16T00:00:00Z"),
        ("2026-10-16T00:00:00Z", "2026-10-16T00:00:00.000000001Z"),
        ("2026-10-15T23:00:00Z", "2026-10-15T22:00:00-02:00"),
    ],
)
def test_date_order_preserves_instants_and_nanoseconds(tmp_path, field, old, new):
    from sinnix_agent_gateway.actions.beads import Order

    beads, _ = beads_service(tmp_path)
    state = tmp_path / "owner-state.json"
    value = json.loads(state.read_text())
    value["items"][0][field + "_at"] = old
    value["items"][1][field + "_at"] = new
    state.write_text(json.dumps(value))
    for direction, expected in (
        ("newest_first", ["fixture-2", "fixture-1"]),
        ("oldest_first", ["fixture-1", "fixture-2"]),
    ):
        rows = beads.query(
            project_ids=["fixture"],
            order=Order(field=field, direction=direction).owner_order(),
        )
        assert [row["id"] for row in rows["items"]] == expected
        # Canonical sorting must not rewrite the owner's timestamp evidence.
        assert {row["id"]: row["fields"][field + "_at"] for row in rows["items"]} == {
            "fixture-1": old,
            "fixture-2": new,
        }


@pytest.mark.parametrize("invalid", [123, "not-a-date", "2026-10-16T00:00:00"])
def test_invalid_owner_date_is_explicit_partial_coverage(tmp_path, invalid):
    beads, _ = beads_service(tmp_path)
    state = tmp_path / "owner-state.json"
    value = json.loads(state.read_text())
    value["items"][0]["created_at"] = invalid
    state.write_text(json.dumps(value))
    rows = beads.query(project_ids=["fixture"], order={"field": "created"})
    assert rows["items"] == []
    assert rows["coverage"]["fixture"]["state"] == "partial"
    assert rows["coverage"]["fixture"]["code"] == "owner_failed"


def test_date_order_is_named_newest_or_oldest_first(tmp_path):
    """Fails if a created order can list the oldest tasks without asking.

    A ChatGPT curation session sent {field: created, reverse: true} meaning
    "newest first" and got July records. The public order names its
    direction, and the ambiguous flag is refused rather than guessed.
    """
    from pydantic import ValidationError
    from sinnix_agent_gateway.actions.beads import Order

    beads, _ = beads_service(tmp_path)
    state = tmp_path / "owner-state.json"
    value = json.loads(state.read_text())
    value["items"][0]["created_at"] = "2026-07-01T00:00:00Z"
    value["items"][1]["created_at"] = "2026-09-28T00:00:00Z"
    state.write_text(json.dumps(value))

    def listed(order: Order) -> list[str]:
        rows = beads.query(project_ids=["fixture"], order=order.owner_order())
        return [row["id"] for row in rows["items"]]

    assert listed(Order(field="created")) == ["fixture-2", "fixture-1"]
    assert listed(Order(field="created", direction="newest_first")) == [
        "fixture-2",
        "fixture-1",
    ]
    assert listed(Order(field="created", direction="oldest_first")) == [
        "fixture-1",
        "fixture-2",
    ]
    with pytest.raises(ValidationError):
        Order.model_validate({"field": "created", "reverse": True})
    with pytest.raises(ValidationError):
        Order(field="created", direction="ascending")


def test_run_actor_reaches_beads_subprocess(tmp_path):
    from sinnix_agent_gateway.calllog import RUN_ID

    beads, log = beads_service(tmp_path)
    token = RUN_ID.set("wfr_fixture")
    try:
        beads.native(
            "fixture",
            "updateIssue",
            {"path": {"id": "fixture-1"}, "body": {"patch": {"notes": "fixture"}}},
            write=True,
        )
    finally:
        RUN_ID.reset(token)
    assert commands(log)
    assert all(
        row["actor"] == "sinnix-gateway:operator:wfr_fixture" for row in commands(log)
    )
