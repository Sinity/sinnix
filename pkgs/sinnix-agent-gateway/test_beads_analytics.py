from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from sinnix_agent_gateway.beads import BeadsError
from sinnix_agent_gateway.beads_analytics import Analytics, instant, literal
from test_beads import beads_service

REVISION = "0123456789abcdefghijklmnopqrstuv"


def test_timestamp_offsets_and_equal_time_commits_use_owner_topology(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"])
    calls = []

    def sql(statement):
        calls.append(statement)
        return [
            {
                "commit_hash": REVISION,
                "committed_at": "2026-09-01T08:00:00Z",
                "commit_order": 9,
            },
            {
                "commit_hash": "z" * 32,
                "committed_at": "2026-09-01T08:00:00Z",
                "commit_order": 8,
            },
        ]

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.resolve("2026-09-01T10:00:00+02:00")
    assert result["resolved_revision"] == REVISION
    assert literal("2026-09-01 08:00:00.000000") in calls[0]
    assert "DOLT_LOG('HEAD')" in calls[0] and "commit_order DESC" in calls[0]
    assert instant("2026-09-01T08:00:00Z") == instant("2026-09-01T10:00:00+02:00")
    with pytest.raises(BeadsError, match="timezone"):
        analytical.resolve("2026-09-01T08:00:00")
    monkeypatch.setattr(
        analytical,
        "sql",
        lambda statement: [
            {"commit_hash": REVISION, "committed_at": "2026-09-01T08:00:00Z"},
            {"commit_hash": "z" * 32, "committed_at": "2026-09-01T08:00:00Z"},
        ],
    )
    with pytest.raises(BeadsError, match="disambiguate"):
        analytical.resolve("2026-09-01T08:00:00Z")


def test_historical_get_never_rereads_live_includes(tmp_path):
    service, log = beads_service(tmp_path)
    result = service.get(
        "fixture",
        "fixture-1",
        as_of="2026-09-01T08:00:00Z",
        includes=["comments", "history", "dependencies"],
    )
    assert result["task_revision"] == REVISION
    assert result["includes"]["history"]["state"] == "unavailable"
    assert result["includes"]["comments"]["revision"] == REVISION
    from test_beads import commands

    owner = commands(log)
    assert not any(
        "--include-comments" in row or "--include-dependents" in row for row in owner
    )
    assert not any(
        "comments" in row or "history" in row or "dep" in row for row in owner
    )
    assert all(
        "AS OF '" + REVISION + "'" in row[-1]
        for row in owner
        if "sql" in row
        and ("FROM comments" in row[-1] or "FROM dependencies" in row[-1])
    )


def test_historical_title_and_graph_use_the_same_resolved_revision(
    tmp_path, monkeypatch
):
    from sinnix_agent_gateway.actions.beads import GetInput, _get

    service, _ = beads_service(tmp_path)
    calls = []

    def query(**kwargs):
        calls.append(kwargs)
        return {
            "coverage": {"fixture": {"state": "complete"}},
            "items": [
                {
                    "id": "fixture-1",
                    "ref": service.bead_ref("fixture", "fixture-1"),
                    "task_revision": REVISION,
                }
            ],
        }

    monkeypatch.setattr(service, "query", query)
    monkeypatch.setattr(
        service, "campaign_closure", lambda *args, **kwargs: {"resolved": kwargs["at"]}
    )
    result = _get(
        SimpleNamespace(config=service.config, beads=service),
        GetInput.model_validate(
            {
                "target": {"project": "fixture", "title_contains": "renamed later"},
                "as_of": "2026-09-01T08:00:00Z",
                "projection": "graph",
            }
        ),
    )
    assert calls[0]["at"] == "2026-09-01T08:00:00Z"
    assert result.bead["task_revision"] == REVISION
    assert result.graph == {"resolved": REVISION}


def test_pagination_preserves_all_rows_order_and_snapshot_after_owner_changes(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    calls = []

    def select(self, **kwargs):
        calls.append(self.project.project_id)
        return [
            {
                "id": f"fixture-{i:03}",
                "title": "neutral",
                "priority": 1,
                "updated_at": f"2026-09-{i % 9 + 1:02}T00:00:00Z",
            }
            for i in range(251)
        ], {"total": 251, "total_exact": True, "truncated": False}

    monkeypatch.setattr(Analytics, "select", select)
    request = {"project_ids": ["fixture"], "view": "recent", "limit": 200}
    first = service.query(**request)
    assert len(first["items"]) == 200 and first["page"]["total"] == 251
    assert first["items"][0]["fields"]["updated_at"] == "2026-09-09T00:00:00Z"
    assert first["items"][0]["id"] == "fixture-008"
    monkeypatch.setattr(
        service, "_run", lambda *args, **kwargs: pytest.fail("cursor reread live owner")
    )
    second = service.query(**request, cursor=first["page"]["next_cursor"])
    assert len(second["items"]) == 51 and second["page"]["next_cursor"] is None
    assert len({row["id"] for row in first["items"] + second["items"]}) == 251
    assert second["source_revisions"] == first["source_revisions"]
    with pytest.raises(BeadsError) as exc:
        service.query(**{**request, "view": "all"}, cursor=first["page"]["next_cursor"])
    assert exc.value.code == "stale_cursor"
    service.principal = type(service.principal).for_name("observer")
    with pytest.raises(BeadsError) as exc:
        service.query(**request, cursor=first["page"]["next_cursor"])
    assert exc.value.code == "stale_cursor"
    assert calls == ["fixture"]


def test_projection_and_aggregate_are_compiled_at_owner(tmp_path, monkeypatch):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"])
    statements = []

    def sql(statement):
        statements.append(statement)
        if "COUNT(*)" in statement:
            return [{"count": 150000}]
        pytest.fail("aggregate fetched issue bodies")

    monkeypatch.setattr(analytical, "sql", sql)
    rows, details = analytical.select(
        view="all",
        filters={},
        expression=None,
        native={"include_deferred": True},
        order={},
        projection="summary",
        aggregate={"group_by": ["status"]},
        max_rows=10000,
    )
    assert rows and details["total"] == 150000
    assert "GROUP BY i.status" in statements[-1]
    assert not any("description" in statement for statement in statements)
    with pytest.raises(BeadsError, match="narrow filters"):
        analytical.select(
            view="all",
            filters={},
            expression=None,
            native={},
            order={},
            projection="summary",
            aggregate=None,
            max_rows=10000,
        )


def test_filter_grammar_is_bounded_and_literals_cannot_become_sql(tmp_path):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"])
    assert (
        analytical.expression("status=open AND priority<=1")
        == "(i.status=" + literal("open") + " AND i.priority<=1)"
    )
    compiled = analytical.ast({"title": "' OR 1=1; DROP TABLE issues; --"})
    assert "DROP TABLE" not in compiled and "CONVERT(0x" in compiled
    for expression in [
        "parent>fixture-1",
        "status=open; DELETE",
        "unknown=value",
        "status=open extra",
    ]:
        with pytest.raises(BeadsError):
            analytical.expression(expression)
    with pytest.raises(BeadsError):
        analytical.native({"no_assignee": False})


@pytest.mark.parametrize(
    "kind", ["discovered_from", "split_from", "supersedes", "residual_of"]
)
def test_explicit_relationship_names_compile_to_native_spelling(tmp_path, kind):
    service, _ = beads_service(tmp_path)
    _, command = service._compile(
        "dependency.add", {"id": "fixture-1", "depends_on": "fixture-2", "type": kind}
    )
    assert command[-2:] == ["--type", kind.replace("_", "-")]


def test_closure_reports_nonroot_cycles_missing_frontier_and_explicit_roles(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    records = {
        "fixture-a": {
            "id": "fixture-a",
            "status": "open",
            "issue_type": "epic",
            "title": "gate sounding title",
        },
        "fixture-b": {
            "id": "fixture-b",
            "status": "open",
            "issue_type": "task",
            "metadata": {"closure_role": "gate"},
        },
        "fixture-c": {"id": "fixture-c", "status": "closed", "issue_type": "decision"},
        "fixture-x": {"id": "fixture-x", "status": "open", "issue_type": "task"},
    }
    dependencies = [
        ("fixture-a", "fixture-b", "blocks"),
        ("fixture-b", "fixture-c", "blocks"),
        ("fixture-c", "fixture-b", "blocks"),
        ("fixture-x", "fixture-missing", "blocks"),
        ("fixture-x", "fixture-origin", "split-from"),
    ]

    def sql(statement):
        assert "AS OF '" + REVISION + "'" in statement
        if "WHERE type IN" in statement:
            return [
                {"issue_id": source, "depends_on_issue_id": target, "type": kind}
                for source, target, kind in dependencies
                if kind == "split-from"
            ]
        matches = re.findall(r"CONVERT\(0x([0-9a-f]+) USING utf8mb4\)", statement)
        selected = {bytes.fromhex(value).decode() for value in matches}
        if "FROM issues" in statement and "JOIN" not in statement:
            return [records[node] for node in sorted(selected) if node in records]
        if "LEFT JOIN" in statement:
            return [
                {
                    "owner_id": source,
                    "id": target,
                    "status": records.get(target, {}).get("status"),
                }
                for source, target, kind in dependencies
                if source in selected and kind == "blocks"
            ]
        return [
            {
                "owner_id": source,
                "issue_id": source,
                "depends_on_issue_id": target,
                "type": kind,
            }
            for source, target, kind in dependencies
            if source in selected
        ]

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.closure(
        ["fixture-a", "fixture-x"],
        relation_filter=None,
        direction="prerequisites",
        max_nodes=20,
        max_depth=10,
    )
    assert result["cycles"] == [["fixture-b", "fixture-c"]]
    assert result["declared_gates"] == ["fixture-b"]
    assert result["declared_decisions"] == ["fixture-c"]
    assert "fixture-a" in result["unknown_roles"]
    assert result["frontier"] == [{"id": "fixture-missing", "reason": "missing"}]
    assert result["coverage"]["complete"] is False
    assert any(
        edge["relation"] == "split_from" and edge["native_relation"] == "split-from"
        for edge in result["provenance_edges"]
    )
    assert all(row["id"] != "fixture-origin" for row in result["nodes"])
    assert not any(edge["relation"] == "split_from" for edge in result["edges"])
    assert result["readiness"]["fixture-a"]["state"] == "blocked"


def test_closure_depth_bound_does_not_claim_truncated_node_is_leaf(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"])

    def sql(statement):
        if "FROM issues" in statement and "JOIN" not in statement:
            return [{"id": "fixture-a", "status": "open"}]
        if "LEFT JOIN" in statement:
            return []
        return [
            {
                "issue_id": "fixture-a",
                "owner_id": "fixture-a",
                "depends_on_issue_id": "fixture-b",
                "type": "blocks",
            }
        ]

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.closure(
        ["fixture-a"],
        relation_filter="blocks",
        direction="prerequisites",
        max_nodes=20,
        max_depth=0,
    )
    assert result["graph_leaves"] == []
    assert result["frontier"] == [{"id": "fixture-b", "reason": "depth_bound"}]


def test_external_dependency_keeps_readiness_and_leaf_coverage_unknown(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"])

    def sql(statement):
        if "FROM issues" in statement and "JOIN" not in statement:
            return [{"id": "fixture-a", "status": "open"}]
        if "LEFT JOIN" in statement:
            return [{"owner_id": "fixture-a", "id": None, "status": None}]
        return [
            {
                "issue_id": "fixture-a",
                "owner_id": "fixture-a",
                "depends_on_issue_id": None,
                "depends_on_external": "external-fixture",
                "type": "blocks",
            }
        ]

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.closure(
        ["fixture-a"],
        relation_filter="blocks",
        direction="prerequisites",
        max_nodes=20,
        max_depth=2,
    )
    assert result["graph_leaves"] == []
    assert result["readiness"]["fixture-a"]["state"] == "unknown"
    assert result["coverage"]["complete"] is False


def test_provenance_preserves_direction_external_origins_and_bounds(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    statements = []
    rows = [
        {
            "issue_id": "fixture-new",
            "depends_on_issue_id": "fixture-root",
            "type": "split-from",
        },
        {
            "issue_id": "fixture-root",
            "depends_on_external": "sinnix://projects/other/beads/other-origin",
            "type": "discovered-from",
        },
    ]

    def sql(statement):
        statements.append(statement)
        return rows

    monkeypatch.setattr(analytical, "sql", sql)
    edges, coverage = analytical.provenance(
        ["fixture-root"], max_edges=10, membership_complete=True
    )
    assert coverage["complete"] is True and coverage["revision"] == REVISION
    assert edges[0]["from"] == "fixture-new" and edges[0]["to"] == "fixture-root"
    assert edges[1]["to"] == "sinnix://projects/other/beads/other-origin"
    assert edges[1]["target_kind"] == "external"
    assert "AS OF '" + REVISION + "'" in statements[0]
    assert (
        "issue_id IN" in statements[0] and "OR depends_on_issue_id IN" in statements[0]
    )
    bounded, coverage = analytical.provenance(
        ["fixture-root"], max_edges=1, membership_complete=True
    )
    assert len(bounded) == 1 and coverage["complete"] is False
    assert coverage["frontier"] == [{"reason": "edge_bound", "max_edges": 1}]


def test_provenance_owner_failure_is_explicit_without_erasing_membership(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)

    def sql(statement):
        raise BeadsError("historical dependency table unavailable", "owner_failed")

    monkeypatch.setattr(analytical, "sql", sql)
    edges, coverage = analytical.provenance(
        ["fixture-root"], max_edges=10, membership_complete=True
    )
    assert edges == [] and coverage["complete"] is False
    assert coverage["frontier"][0]["reason"] == "owner_unavailable"


@pytest.mark.parametrize(
    "token", ["7773497739344011640", 7773497739344011640, "0", None, 1.5, True]
)
def test_closure_preserves_opaque_owner_row_revision_separate_from_snapshot(
    tmp_path, monkeypatch, token
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    statements = []

    def sql(statement):
        statements.append(statement)
        assert "AS OF '" + REVISION + "'" in statement
        if "FROM issues" in statement and "JOIN" not in statement:
            return [
                {
                    "id": "fixture-a",
                    "status": "open",
                    "bead_revision": token,
                    "current_revision": 1,
                }
            ]
        return []

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.closure(
        ["fixture-a"],
        relation_filter="blocks",
        direction="prerequisites",
        max_nodes=10,
        max_depth=1,
    )
    node = result["nodes"][0]
    valid = token is not None and not isinstance(token, (float, bool))
    assert node["bead_revision"] == (str(token) if valid else None)
    assert node["bead_revision_domain"] == ("beads_row_revision" if valid else None)
    assert node["bead_revision_coverage"] == (
        "partial_update_coverage" if valid else "unavailable"
    )
    assert "CAST(row_lock AS CHAR) AS bead_revision" in statements[0]
    assert node["bead_revision"] != REVISION


def test_historical_missing_row_revision_remains_unknown_without_live_fallback(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    statements = []

    def sql(statement):
        statements.append(statement)
        assert "AS OF '" + REVISION + "'" in statement
        if "CAST(row_lock AS CHAR)" in statement:
            raise BeadsError(
                "column row_lock absent in historical schema", "owner_failed"
            )
        if "FROM issues" in statement and "JOIN" not in statement:
            return [{"id": "fixture-a", "status": "closed"}]
        return []

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.closure(
        ["fixture-a"],
        relation_filter="blocks",
        direction="prerequisites",
        max_nodes=10,
        max_depth=1,
    )
    assert result["coverage"]["complete"] is True
    assert result["nodes"][0]["bead_revision"] is None
    assert result["nodes"][0]["bead_revision_domain"] is None
    assert "historical schema" in result["nodes"][0]["bead_revision_unavailable_reason"]
    assert (
        len(
            [
                statement
                for statement in statements
                if "FROM issues" in statement and "JOIN" not in statement
            ]
        )
        == 2
    )


def test_wide_closure_batches_nodes_edges_and_readiness_at_one_revision(
    tmp_path, monkeypatch
):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    records = {
        f"fixture-{index:03}": {
            "id": f"fixture-{index:03}",
            "status": "open",
            "issue_type": "task",
            "bead_revision": str(7773497739344011640 + index),
        }
        for index in range(75)
    }
    dependencies = [
        ("fixture-000", target) for target in sorted(records) if target != "fixture-000"
    ]
    statements = []

    def sql(statement):
        statements.append(statement)
        assert "AS OF '" + REVISION + "'" in statement
        assert "description" not in statement
        if "WHERE type IN" in statement:
            return []
        selected = {
            bytes.fromhex(value).decode()
            for value in re.findall(
                r"CONVERT\(0x([0-9a-f]+) USING utf8mb4\)", statement
            )
        }
        if "FROM issues" in statement and "JOIN" not in statement:
            return [records[node] for node in sorted(selected) if node in records]
        if "LEFT JOIN" in statement:
            return [
                {"owner_id": source, "id": target, "status": "open"}
                for source, target in dependencies
                if source in selected
            ]
        return [
            {
                "owner_id": source,
                "issue_id": source,
                "depends_on_issue_id": target,
                "type": "blocks",
            }
            for source, target in dependencies
            if source in selected
        ]

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.closure(
        ["fixture-000"],
        relation_filter="blocks",
        direction="prerequisites",
        max_nodes=100,
        max_depth=10,
    )
    assert len(result["nodes"]) == 75 and len(result["edges"]) == 74
    assert result["coverage"]["complete"] is True
    assert len(result["graph_leaves"]) == 74
    assert result["readiness"]["fixture-000"]["state"] == "blocked"
    assert result["nodes"][-1]["bead_revision"] == str(7773497739344011714)
    assert (
        len(statements) == 6
    )  # Two breadth levels, one readiness batch, one provenance batch.
    assert sum("CAST(row_lock AS CHAR)" in statement for statement in statements) == 2


def test_batched_edge_bounds_preserve_each_member_coverage(tmp_path, monkeypatch):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)

    def sql(statement):
        if "WHERE type IN" in statement or "LEFT JOIN" in statement:
            return []
        if "FROM issues" in statement and "JOIN" not in statement:
            return [
                {"id": "fixture-a", "status": "open"},
                {"id": "fixture-b", "status": "open"},
            ]
        assert "PARTITION BY m.id" in statement and "edge_rank <= 3" in statement
        return [
            {
                "owner_id": "fixture-a",
                "issue_id": "fixture-a",
                "depends_on_issue_id": f"fixture-child-{index}",
                "type": "blocks",
            }
            for index in range(3)
        ] + [
            {
                "owner_id": "fixture-b",
                "issue_id": "fixture-b",
                "depends_on_issue_id": "fixture-child-b",
                "type": "blocks",
            }
        ]

    monkeypatch.setattr(analytical, "sql", sql)
    result = analytical.closure(
        ["fixture-a", "fixture-b"],
        relation_filter="blocks",
        direction="prerequisites",
        max_nodes=2,
        max_depth=10,
    )
    assert [row for row in result["frontier"] if row["reason"] == "edge_bound"] == [
        {"id": "fixture-a", "reason": "edge_bound"}
    ]
    assert any(edge["from"] == "fixture-b" for edge in result["edges"])
    assert len(result["nodes"]) == 2 and result["coverage"]["complete"] is False


def test_batched_owner_rows_cannot_silently_lose_edge_ownership(tmp_path, monkeypatch):
    service, _ = beads_service(tmp_path)
    analytical = Analytics(service, service.config.projects["fixture"], REVISION)
    monkeypatch.setattr(
        analytical, "sql", lambda statement: [{"id": "fixture-b", "status": "closed"}]
    )
    with pytest.raises(BeadsError, match="ownership"):
        analytical._closure_edges(
            ["fixture-a"],
            direction="prerequisites",
            relation_filter="blocks",
            max_edges=10,
        )
    with pytest.raises(BeadsError, match="ownership"):
        analytical._closure_blockers(["fixture-a"], max_edges=10)
