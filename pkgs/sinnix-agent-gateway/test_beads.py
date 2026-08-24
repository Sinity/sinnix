from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sinnix_agent_gateway.beads import BeadsError, BeadsService
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig, TaskAuthorityConfig


def beads_service(tmp_path: Path, principal: str = "operator") -> tuple[BeadsService, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    project = tmp_path / "project"; project.mkdir()
    other_project = tmp_path / "other-project"; other_project.mkdir()
    log = tmp_path / "commands.jsonl"; runner = tmp_path / "bd"
    runner.write_text(
        f"#!{sys.executable}\nimport json, pathlib, sys\n"
        f"log=pathlib.Path({str(log)!r}); log.open('a').write(json.dumps(sys.argv[1:])+'\\n')\n"
        f"project={str(project)!r}\n"
        f"other_project={str(other_project)!r}\n"
        f"state_path={str(tmp_path / 'owner-state.json')!r}\n"
        "state=json.loads(pathlib.Path(state_path).read_text()) if pathlib.Path(state_path).exists() else {'writes': 0, 'created': 0}\n"
        "args=sys.argv[1:]\n"
        "root=next((args[index + 1] for index, value in enumerate(args) if value == '--directory'), project)\n"
        "if args[-1]=='where': print(json.dumps({'path': root+'/.beads','database_path':root+'/.beads/dolt','schema_version':1}))\n"
        "elif args[-1]=='status': print(json.dumps({'summary':{'total_issues':2 + state['writes']}}))\n"
        "elif 'unrelated-write' in args: state['writes'] += 1; pathlib.Path(state_path).write_text(json.dumps(state)); print(json.dumps({'unrelated': True}))\n"
        "elif 'force-fail' in args: print('forced owner failure', file=sys.stderr); raise SystemExit(7)\n"
        "elif 'export' in args:\n"
        "    destination=pathlib.Path(args[args.index('-o')+1])\n"
        "    destination.parent.mkdir(parents=True, exist_ok=True)\n"
        "    destination.write_text(json.dumps({'writes':state['writes']}, sort_keys=True)+'\\n')\n"
        "    print(json.dumps({'exported':str(destination)}))\n"
        "elif 'create' in args and '--dry-run' not in args:\n"
        "    state['writes'] += 1; state['created'] += 1; pathlib.Path(state_path).write_text(json.dumps(state)); print(json.dumps({'id':f'fixture-created-{state[\"created\"]}','title':'created','status':'open'}))\n"
        "elif '--dry-run' in args: print(json.dumps({'dry_run':True}))\n"
        "elif '--format' in args: print('flowchart TD\\n  fixture-1 --> fixture-2')\n"
        "elif '--refs' in args: print(json.dumps({'schema_version':1, 'fixture-1':[]}))\n"
        "elif 'show' in args: print(json.dumps({'id':next((x for x in args if x.startswith('fixture-')), 'fixture-1'),'title':'fixture','status':'open','notes':'long existing notes','labels':['lane:gateway']}))\n"
        "elif 'dep' in args: print(json.dumps({'issues':[{'id':'fixture-2','dependency_type':'blocks'}]}))\n"
        "else:\n"
        "    if '--readonly' not in args and any(item in args for item in ('update','unclaim','close','reopen','comments','remember','forget','dolt','backup')):\n"
        "        state['writes'] += 1; pathlib.Path(state_path).write_text(json.dumps(state))\n"
        "    print(json.dumps({'issues':[{'id':'fixture-1','title':'first','status':'open'},{'id':'fixture-2','title':'second','status':'open'}]}))\n"
    ); runner.chmod(0o700)
    cfg = GatewayConfig(state_dir=tmp_path / "state", projects={
        "fixture": ProjectConfig(project_id="fixture", path=project, observer_read=True, task_authority=TaskAuthorityConfig(owner="beads", workspace=project / ".beads", database=project / ".beads" / "dolt")),
        "other": ProjectConfig(project_id="other", path=other_project, observer_read=True, task_authority=TaskAuthorityConfig(owner="beads", workspace=other_project / ".beads", database=other_project / ".beads" / "dolt")),
    }, beads_command=str(runner))
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


def test_ready_query_requests_issue_rows_without_unbounded_explanation(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)

    result = beads.query(project_ids=["fixture"], view="ready", limit=20)

    ready = next(command for command in commands(log) if "ready" in command)
    assert "--explain" not in ready
    assert ready[ready.index("--limit") + 1] == "20"
    assert result["items"]
    assert result["coverage"]["fixture"]["total_exact"] is True


def test_get_graph_and_memory_keep_owner_features_explicit(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    item = beads.get("fixture", "fixture-1", includes=["blockers", "comments", "history", "dependencies", "dependents", "children", "refs"], as_of="HEAD")
    graph = beads.graph("fixture", "fixture-1", direction="both", edge_type="blocks", status="open", max_rows=10, mermaid=True)
    assert item["task_revision"] and item["includes"]["history"]
    assert graph["nodes"][0]["ref"].startswith("sinnix://projects/fixture/beads/")
    assert "flowchart TD" in graph["mermaid"]
    assert item["as_of"] == "HEAD" and item["links"]["jobs"].endswith("/jobs")
    assert item["includes"]["blockers"]["items"][0]["id"] == "fixture-2"
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
    worker, _ = beads_service(tmp_path / "worker", "agent-control")
    assert worker.get("fixture", "fixture-1")["ref"].endswith("fixture-1")
    with pytest.raises(PolicyError, match="task.write"):
        worker.change("fixture", "close", {"id":"fixture-1"})


def test_operator_close_requires_an_explicit_true_force_override(tmp_path: Path) -> None:
    beads, _log = beads_service(tmp_path)

    preview = beads.change(
        "fixture",
        "close",
        {"id": "fixture-1", "reason": "accepted evidence", "force": True},
        mode="preview",
    )

    assert preview["command"][-1] == "--force"
    with pytest.raises(BeadsError, match="force must be true"):
        beads.change("fixture", "close", {"id": "fixture-1", "force": False}, mode="preview")


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


def test_changeset_preview_is_non_mutating_and_binds_created_beads(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    actions = [
        {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "parent"}, "bind": "parent"},
        {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "child", "parent": "$parent"}, "bind": "child"},
        {"ref": "sinnix://projects/fixture", "operation": "dependency.add", "parameters": {"id": "$child", "depends_on": "$parent"}},
    ]
    preview = beads.changeset(actions, mode="preview")
    assert preview["atomicity"] == "per_step_commits"
    assert all("outcome" not in item for item in preview["actions"])
    assert all("create" not in command or "--dry-run" in command for command in commands(log))
    applied = beads.changeset(actions, mode="apply", preview_digest=preview["preview_digest"])
    assert [item["outcome"] for item in applied["outcomes"]] == ["applied", "applied", "applied"]
    assert applied["outcomes"][1]["bound_ref"].endswith("fixture-created-2")
    dependency = next(command for command in commands(log) if "dep" in command and "add" in command)
    assert "fixture-created-2" in dependency and "fixture-created-1" in dependency


def test_changeset_reports_failure_skips_and_never_sweeps_an_unrelated_writer(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    actions = [
        {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "first"}},
        {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "force-fail"}},
        {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "skipped"}},
    ]
    result = beads.changeset(actions, mode="apply")
    assert [item["outcome"] for item in result["outcomes"]] == ["applied", "failed", "skipped"]
    continued = beads.changeset([
        {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "force-fail"}},
        {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "continues"}},
    ], mode="apply", on_error="continue")
    assert [item["outcome"] for item in continued["outcomes"]] == ["failed", "applied"]
    runner = tmp_path / "bd"
    subprocess.run([str(runner), "unrelated-write"], check=True, capture_output=True, text=True)
    preview = beads.changeset(actions[:1], mode="preview")
    subprocess.run([str(runner), "unrelated-write"], check=True, capture_output=True, text=True)
    with pytest.raises(BeadsError, match="stale"):
        beads.changeset(actions[:1], mode="apply", preview_digest=preview["preview_digest"])
    assert all(item["operation"] == "create" for item in result["outcomes"])
    assert any("unrelated-write" in command for command in commands(log))


def test_changeset_rejects_cross_project_graph_edges_before_mutation(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    with pytest.raises(BeadsError, match="cross-project"):
        beads.changeset([
            {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "first"}, "bind": "first"},
            {"ref": "sinnix://projects/other", "operation": "create", "parameters": {"title": "second", "parent": "$first"}},
        ], mode="preview")
    assert all("create" not in command for command in commands(log))


def test_changeset_partitions_independent_projects_and_validates_every_precondition(tmp_path: Path) -> None:
    beads, _ = beads_service(tmp_path)
    actions = [
        {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "one"}},
        {"ref": "sinnix://projects/other", "operation": "create", "parameters": {"title": "two"}},
    ]
    applied = beads.changeset(actions, mode="apply")
    assert applied["atomicity"] == "cross_project_partitioned"
    assert set(applied["source_revisions"]) == {"fixture", "other"}
    assert [item["outcome"] for item in applied["outcomes"]] == ["applied", "applied"]
    with pytest.raises(BeadsError, match="expected_task_revision"):
        beads.changeset([
            {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "blocked"}},
            {"ref": "sinnix://projects/fixture", "operation": "create", "parameters": {"title": "bad"}, "preconditions": {"expected_task_revision": "not-a-revision"}},
        ], mode="apply")


def test_graph_changeset_is_owner_atomic_only_after_native_validation(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    actions = [
        {"ref": "sinnix://projects/fixture", "operation": "graph.create", "parameters": {"graph": {"issues": [{"title": "parent"}, {"title": "child"}]}}},
    ]
    preview = beads.changeset(actions, mode="preview")
    assert preview["atomicity"] == "owner_atomic"
    assert preview["actions"][0]["native_validation"] == "dry_run"
    result = beads.changeset(actions, mode="apply", preview_digest=preview["preview_digest"])
    assert result["atomicity"] == "owner_atomic"
    assert result["outcomes"][0]["outcome"] == "applied"
    assert any("--graph" in command and "--dry-run" in command for command in commands(log))


def test_explicit_maintenance_operations_publish_a_deterministic_snapshot_receipt(tmp_path: Path) -> None:
    beads, log = beads_service(tmp_path)
    first = beads.operate("fixture", "snapshot.publish")
    second = beads.operate("fixture", "snapshot.publish")
    assert first["publication"]["after_sha256"] == second["publication"]["after_sha256"]
    assert second["publication"]["changed"] is False and second["publication"]["diff"] == ""
    assert first["git_bookkeeping"] == "none"
    beads.operate("fixture", "sync.push")
    beads.operate("fixture", "sync.pull")
    beads.operate("fixture", "backup.create")
    beads.operate("fixture", "backup.list")
    beads.operate("fixture", "backup.restore", {"backup_id": "fixture-backup"})
    assert any("dolt" in command and "push" in command for command in commands(log))
    assert any("dolt" in command and "pull" in command for command in commands(log))
    assert any("backup" in command and "create" in command for command in commands(log))
    assert any("backup" in command and "restore" in command and "fixture-backup" in command for command in commands(log))
