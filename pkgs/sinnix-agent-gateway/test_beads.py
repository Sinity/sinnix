from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sinnix_agent_gateway.beads import BeadsError, BeadsService
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig, TaskAuthorityConfig


def beads_service(tmp_path: Path, principal: str = "operator") -> tuple[BeadsService, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project = tmp_path / "project"; project.mkdir()
    log = tmp_path / "commands.jsonl"; runner = tmp_path / "bd"
    runner.write_text(
        f"#!{sys.executable}\nimport json, pathlib, sys\n"
        f"log=pathlib.Path({str(log)!r}); log.open('a').write(json.dumps(sys.argv[1:])+'\\n')\n"
        f"project={str(project)!r}\n"
        "args=sys.argv[1:]\n"
        "if args[-1]=='where': print(json.dumps({'path': project+'/.beads','database_path':project+'/.beads/dolt','schema_version':1}))\n"
        "elif args[-1]=='status': print(json.dumps({'summary':{'total_issues':2}}))\n"
        "elif '--format' in args: print('flowchart TD\\n  fixture-1 --> fixture-2')\n"
        "elif '--refs' in args: print(json.dumps({'schema_version':1, 'fixture-1':[]}))\n"
        "elif 'show' in args: print(json.dumps({'id':next((x for x in args if x.startswith('fixture-')), 'fixture-1'),'title':'fixture','status':'open','notes':'long existing notes','labels':['lane:gateway']}))\n"
        "elif 'dep' in args: print(json.dumps({'issues':[{'id':'fixture-2','dependency_type':'blocks'}]}))\n"
        "else: print(json.dumps({'issues':[{'id':'fixture-1','title':'first','status':'open'},{'id':'fixture-2','title':'second','status':'open'}]}))\n"
    ); runner.chmod(0o700)
    cfg = GatewayConfig(state_dir=tmp_path / "state", projects={"fixture": ProjectConfig(project_id="fixture", path=project, observer_read=True, task_authority=TaskAuthorityConfig(owner="beads", workspace=project / ".beads", database=project / ".beads" / "dolt"))}, beads_command=str(runner))
    return BeadsService(cfg, Principal.for_name(principal)), log


def commands(log: Path) -> list[list[str]]:
    return [json.loads(line) for line in log.read_text().splitlines()]


def test_query_normalizes_project_qualified_resources_and_snapshot_pages(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path, "observer")
    first = beads.query(project_ids=["fixture"], filters={"status": "open", "priority": {"op": "<=", "value": 1}}, includes=["comments"], limit=1)
    second = beads.query(project_ids=["fixture"], filters={"status": "open", "priority": {"op": "<=", "value": 1}}, includes=["comments"], limit=1, cursor=first["page"]["next_cursor"])
    assert first["items"][0]["ref"] == "sinnix://projects/fixture/beads/fixture-1"
    assert first["items"][0]["links"]["history"].endswith("/history")
    assert first["coverage"]["fixture"]["state"] == "complete"
    assert second["items"][0]["id"] == "fixture-2"
    assert any("--parse-only" in command for command in commands(log))


def test_query_compiles_native_list_filters_and_records_parse_parity(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    beads.query(
        project_ids=["fixture"],
        filters={"and": [{"status": "open"}, {"priority": {"op": "<=", "value": 1}}]},
        expression="label=polylogue AND label!=needs:operator",
    )
    result = beads.query(
        project_ids=["fixture"],
        view="open",
        native_filters={"updated_after": "7d", "exclude_label": ["needs:operator"], "priority_max": "P1"},
        includes=["dependencies"],
    )
    query = next(command for command in commands(log) if "list" in command and "--updated-after" in command)
    assert "--limit" in query and "--max-rows" in query
    assert result["totals"]["returned"] == 2
    assert result["owner_capabilities"]["native_offset_paging"] is False


def test_get_graph_and_memory_keep_owner_features_explicit(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    item = beads.get("fixture", "fixture-1", includes=["comments", "history", "dependencies", "dependents", "children", "refs"], as_of="HEAD")
    graph = beads.graph("fixture", "fixture-1", direction="both", edge_type="blocks", status="open", max_rows=10, mermaid=True)
    assert item["task_revision"] and item["includes"]["history"]
    assert graph["nodes"][0]["ref"].startswith("sinnix://projects/fixture/beads/")
    assert "flowchart TD" in graph["mermaid"]
    assert item["as_of"] == "HEAD" and item["links"]["jobs"].endswith("/jobs")
    assert graph["owner_capabilities"]["native_cycle_detection"] is True
    assert any(command[-2:] == ["--limit", "20"] for command in commands(log))


def test_preview_never_writes_and_apply_protects_notes_by_default(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    preview = beads.change("fixture", "update", {"id":"fixture-1", "patch":{"notes":{"text":"new context"}}}, mode="preview")
    assert preview["mode"] == "preview" and "--append-notes" in preview["command"]
    assert all("update" not in command for command in commands(log))
    result = beads.change("fixture", "update", {"id":"fixture-1", "patch":{"notes":{"text":"new context"}}}, preview_digest=preview["preview_digest"])
    assert result["before"]["fields"]["notes"] == "long existing notes"
    assert any("update" in command and "--append-notes" in command for command in commands(log))
    with pytest.raises(BeadsError, match="stale"):
        beads.change("fixture", "update", {"id":"fixture-1", "patch":{"notes":{"text":"x"}}}, preview_digest="0" * 64)


def test_replace_notes_requires_explicit_mode_and_cas_is_forwarded(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    preview = beads.change("fixture", "update", {"id":"fixture-1", "patch":{"notes":{"text":"intentional replacement", "mode":"replace"}}}, mode="preview", preconditions={"expected_status":"open", "expected_assignee":None})
    assert "--notes" in preview["command"] and "--append-notes" not in preview["command"]
    assert "--if-status" in preview["command"]
    with pytest.raises(BeadsError, match="status no longer matches"):
        beads.change("fixture", "update", {"id":"fixture-1", "patch":{"set":{"status":"closed"}}}, mode="preview", preconditions={"expected_status":"closed"})
    assert any("show" in command for command in commands(log))


def test_typed_mutations_and_owner_authority_are_enforced(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    beads.change("fixture", "dependency.add", {"id":"fixture-1", "depends_on":"fixture-2"})
    beads.change("fixture", "memory.remember", {"id":"fixture-1", "key":"gateway", "text":"fact"})
    assert any("dep" in command and "add" in command for command in commands(log))
    observer, _ = beads_service(tmp_path / "observer", "observer")
    with pytest.raises(PolicyError, match="task.write"):
        observer.change("fixture", "claim", {"id":"fixture-1"})


@pytest.mark.parametrize(("operation", "parameters"), [
    ("create", {"title": "created"}),
    ("update", {"id": "fixture-1", "patch": {"set": {"title": "updated"}}}),
    ("claim", {"id": "fixture-1"}), ("unclaim", {"id": "fixture-1"}),
    ("close", {"id": "fixture-1"}), ("reopen", {"id": "fixture-1"}),
    ("comment", {"id": "fixture-1", "text": "comment"}),
    ("dependency.add", {"id": "fixture-1", "depends_on": "fixture-2"}),
    ("dependency.remove", {"id": "fixture-1", "depends_on": "fixture-2"}),
    ("relate", {"id": "fixture-1", "other_id": "fixture-2"}),
    ("unrelate", {"id": "fixture-1", "other_id": "fixture-2"}),
    ("reparent", {"id": "fixture-1", "parent_id": "fixture-2"}),
    ("memory.remember", {"id": "fixture-1", "key": "fact", "text": "memory"}),
    ("memory.forget", {"id": "fixture-1", "key": "fact"}),
    ("graph.create", {"graph": {"issues": [{"title": "child"}]}}),
])
def test_every_declared_non_admin_mutation_has_preview_and_apply(tmp_path: Path, operation: str, parameters: dict[str, object]) -> None:
    beads, _ = beads_service(tmp_path)
    preview = beads.change("fixture", operation, parameters, mode="preview")
    applied = beads.change("fixture", operation, parameters, preview_digest=preview["preview_digest"])
    assert preview["command"] and applied["mode"] == "apply"


def test_create_graph_uses_native_dry_run_and_cleans_its_input(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    preview = beads.change("fixture", "graph.create", {"graph": {"issues": [{"title": "one"}]}}, mode="preview")
    assert preview["native_validation"] == "dry_run"
    assert all(not path.exists() for path in (tmp_path / "state" / "beads-graph-inputs").glob("*"))
    assert any("--graph" in command and "--dry-run" in command for command in commands(log))


def test_query_partial_sources_do_not_erase_healthy_projects(tmp_path: Path) -> None:
    beads, _ = beads_service(tmp_path)
    result = beads.query(project_ids=["fixture", "missing"], filters={"status":"open"})
    assert result["items"] and result["coverage"]["fixture"]["state"] == "complete"
    assert result["coverage"]["missing"]["state"] == "partial"
