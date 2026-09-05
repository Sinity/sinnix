from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from sinnix_agent_gateway import actions as action_set
from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.artifacts import ArtifactError
from sinnix_agent_gateway.capabilities import PolicyError
from sinnix_agent_gateway.cli import (
    build_manifest,
    semantic_canary,
    verify_approval,
)
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.projects import ProjectError
from sinnix_agent_gateway.server import _bounded_resource_json
from sinnix_mcp.execution import ExecutionResult


def config(tmp_path: Path, *, observer_read: bool = True) -> GatewayConfig:
    project = tmp_path / "project"
    project.mkdir()
    return GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture",
                path=project,
                observer_read=observer_read,
            )
        },
        approved_manifest_hash="approved-fixture-hash",
    )


def test_gateway_resource_bounds_fall_back_to_an_attested_artifact(
    tmp_path: Path,
) -> None:
    runtime = Runtime.create(
        dataclasses.replace(config(tmp_path), max_result_bytes=2_048), "observer"
    )

    encoded = _bounded_resource_json(runtime, {"payload": "x" * 4_000}, "fixture")
    envelope = json.loads(encoded)

    assert len(encoded.encode()) <= runtime.config.max_result_bytes
    assert envelope["truncated"] is True
    assert envelope["artifact"]["ref"].startswith("sinnix://artifacts/")
    assert runtime.artifacts.list()["artifacts"][0]["kind"] == "gateway-fixture"


def test_readonly_policy_is_checked_inside_write_operation(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    runtime = Runtime.create(cfg, "observer")
    assert runtime.projects.list()["projects"][0]["writable"] is False
    target = cfg.projects["fixture"].path / "forbidden.txt"
    with pytest.raises(PolicyError):
        runtime.projects.write("fixture", target.name, "forbidden")
    assert not target.exists()


def test_operator_project_writes_do_not_depend_on_observer_visibility(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path, observer_read=False)
    subprocess.run(["git", "init", "--quiet", cfg.projects["fixture"].path], check=True)
    runtime = Runtime.create(cfg, "operator")
    target = cfg.projects["fixture"].path / "operator.txt"

    result = runtime.projects.write("fixture", target.name, "operator authority")

    assert result["bytes"] == len("operator authority")
    assert target.read_text() == "operator authority"
    assert runtime.projects.list()["projects"][0]["observer_read"] is False
    assert runtime.projects.list()["projects"][0]["writable"] is True


def test_project_read_applies_late_line_range_before_byte_bound(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    target = cfg.projects["fixture"].path / "large.txt"
    target.write_text("".join(f"line-{line:04d} padding\n" for line in range(1, 301)))
    runtime = Runtime.create(cfg, "observer")
    result = runtime.projects.read("fixture", "large.txt", 250, 251, 128)
    assert "line-0250" in result["content"]
    assert "line-0251" in result["content"]


def test_project_subprocess_output_is_bounded_before_storage(tmp_path: Path) -> None:
    cfg = dataclasses.replace(config(tmp_path), max_result_bytes=4096)
    runtime = Runtime.create(cfg, "observer")
    output = runtime.projects._run_bounded(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 10000000)"],
        cfg.projects["fixture"].path,
    )
    assert len(output.encode()) == 4096


def test_project_subprocess_failure_surfaces_bounded_stderr(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")

    with pytest.raises(ProjectError, match="project diagnostic"):
        runtime.projects._run_bounded(
            [
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('project diagnostic'); raise SystemExit(2)",
            ],
            runtime.config.projects["fixture"].path,
        )


def test_project_apply_patch_streams_patch_to_git(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    subprocess.run(["git", "init", "--quiet", cfg.projects["fixture"].path], check=True)
    target = cfg.projects["fixture"].path / "tracked.txt"
    target.write_text("before\n")
    runtime = Runtime.create(cfg, "operator")

    result = runtime.projects.apply_patch(
        "fixture",
        """diff --git a/tracked.txt b/tracked.txt
--- a/tracked.txt
+++ b/tracked.txt
@@ -1 +1 @@
-before
+after
""",
    )

    assert result == {"project_id": "fixture", "applied": True}
    assert target.read_text() == "after\n"


def test_project_diff_rejects_option_injection_before_external_driver(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path)
    project = cfg.projects["fixture"].path
    marker = tmp_path / "external-diff-ran"
    driver = tmp_path / "external-diff"
    driver.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n"
    )
    driver.chmod(0o700)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Gateway Test"], cwd=project, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "gateway-test@example.invalid"],
        cwd=project,
        check=True,
    )
    subprocess.run(
        ["git", "config", "diff.hostile.command", str(driver)],
        cwd=project,
        check=True,
    )
    (project / ".gitattributes").write_text("tracked.txt diff=hostile\n")
    (project / "tracked.txt").write_text("before\n")
    subprocess.run(
        ["git", "add", ".gitattributes", "tracked.txt"], cwd=project, check=True
    )
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=project, check=True)
    (project / "tracked.txt").write_text("after\n")

    runtime = Runtime.create(cfg, "observer")
    with pytest.raises(ProjectError, match="invalid git ref"):
        runtime.projects.diff("fixture", "--ext-diff")
    assert not marker.exists()
    result = runtime.projects.diff("fixture", "HEAD")
    assert "before" in result["diff"] and "after" in result["diff"]
    assert not marker.exists()


def test_project_tree_and_read_reject_symlink_escape(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    (cfg.projects["fixture"].path / "escape.txt").symlink_to(outside)
    runtime = Runtime.create(cfg, "observer")
    with pytest.raises(ProjectError):
        runtime.projects.read("fixture", "escape.txt")
    assert runtime.projects.tree("fixture")["entries"] == []


def test_remote_project_tools_hide_local_only_agent_state(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    project = cfg.projects["fixture"].path
    private_files = (
        project / ".agent" / "scratch" / "private.md",
        project / ".beads" / "interactions.jsonl",
        project / ".beads" / "dolt-server-config.yaml",
        project / ".claude" / "settings.json",
        project / ".mcp.json",
        project / "dots" / "codex" / "skills" / ".system" / "private.md",
    )
    for path in private_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("gateway-private-marker")

    runtime = Runtime.create(cfg, "observer")
    for path in private_files:
        with pytest.raises(ProjectError):
            runtime.projects.read("fixture", str(path.relative_to(project)))

    tree_paths = {
        entry["path"] for entry in runtime.projects.tree("fixture")["entries"]
    }
    assert not tree_paths.intersection(
        str(path.relative_to(project)) for path in private_files
    )
    assert runtime.projects.search("fixture", "gateway-private-marker")["matches"] == []


def test_audit_chain_survives_concurrent_writers(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        list(
            executor.map(
                lambda ordinal: runtime.audit.append(
                    "concurrency_probe", "ok", {"ordinal": ordinal}
                ),
                range(240),
            )
        )
    verification = runtime.audit.verify()
    assert verification["valid"] is True
    assert verification["checked"] == 240
    assert len(verification["head_hash"]) == 64
    assert {event["principal"] for event in runtime.audit.tail(240)["events"]} == {
        "observer"
    }


def test_v2_events_are_principal_scoped_and_receipted(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    observer = Runtime.create(cfg, "observer")
    operator = Runtime.create(cfg, "operator")
    observer.audit.append("observer_event", "ok")
    operator.audit.append("operator_event", "ok")

    response = observer.execute_v2(
        action_set.BY_NAME["events.tail"],
        lambda: observer.v2_events(100),
        {"limit": 100},
    )

    events = response["data"]["events"]
    assert {event["principal"] for event in events} == {"observer"}
    audit_events = [event for event in events if event["kind"] == "gateway_receipt"]
    assert {event["operation"] for event in audit_events} == {"observer_event"}
    assert response["meta"]["resource_refs"] == [
        f"sinnix://receipts/{audit_events[0]['event_id']}"
    ]
    assert response["receipt"]["ref"].startswith("sinnix://receipts/")


def test_gateway_status_reports_distinct_manifest_provenance(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    runtime = Runtime.create(cfg, "observer")
    status = runtime.observe.gateway_status(
        "observer",
        "capability-hash",
        "approved-fixture-hash",
        "catalog-hash",
        "v2-test",
    )
    assert status["principal_contract_hash"] == "capability-hash"
    assert status["tool_manifest_hash"] == "approved-fixture-hash"
    assert status["action_catalog_hash"] == "catalog-hash"
    assert status["catalog"] == {
        "revision": "v2-test",
        "live_action_catalog": {
            "principal": "observer",
            "sha256": "catalog-hash",
        },
        "chatgpt_observed": None,
        "comparisons": {
            "live_to_chatgpt_observed": "unobserved",
        },
    }
    assert status["manifests"]["comparisons"] == {
        "live_to_nix_approved": "match",
        "live_to_chatgpt_observed": "unobserved",
        "nix_approved_to_chatgpt_observed": "unobserved",
    }

    snapshot = cfg.state_dir / "connector-snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema": "sinnix.gateway-connector-snapshot.v1",
                "principal": "observer",
                "manifest_sha256": "approved-fixture-hash",
                "action_catalog_sha256": "catalog-hash",
            }
        )
    )
    status = runtime.observe.gateway_status(
        "observer",
        "capability-hash",
        "approved-fixture-hash",
        "catalog-hash",
        "v2-test",
    )
    assert set(status["manifests"]["comparisons"].values()) == {"match"}
    assert status["catalog"]["chatgpt_observed"] == {
        "principal": "observer",
        "sha256": "catalog-hash",
    }
    assert set(status["catalog"]["comparisons"].values()) == {"match"}

    snapshot.write_text(
        json.dumps(
            {
                "schema": "sinnix.gateway-connector-snapshot.v1",
                "principal": "observer",
                "manifest_sha256": "stale-hash",
            }
        )
    )
    status = runtime.observe.gateway_status(
        "observer",
        "capability-hash",
        "approved-fixture-hash",
        "catalog-hash",
        "v2-test",
    )
    assert status["manifests"]["comparisons"] == {
        "live_to_nix_approved": "match",
        "live_to_chatgpt_observed": "mismatch",
        "nix_approved_to_chatgpt_observed": "mismatch",
    }


def test_gateway_status_reports_broker_route_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = dataclasses.replace(
        config(tmp_path),
        mcp_broker_servers={
            "lynchpin": {"brokered": True},
            "polylogue": {"brokered": True},
        },
    )
    runtime = Runtime.create(cfg, "observer")
    monkeypatch.setattr(
        runtime.route_preflight,
        "run",
        lambda: {"status": "ready", "routes": []},
    )

    async def catalog() -> dict[str, object]:
        return {
            "servers": [
                {
                    "name": "lynchpin",
                    "brokered": True,
                    "availability": "available",
                    "tool_count": 8,
                    "read_only_tool_count": 3,
                },
                {
                    "name": "polylogue",
                    "brokered": True,
                    "availability": "unavailable",
                    "failure_class": "upstream_unavailable",
                },
            ]
        }

    monkeypatch.setattr(runtime.mcp_broker, "catalog", catalog)
    status = anyio.run(
        runtime.gateway_status,
        "capability-hash",
        "approved-fixture-hash",
        "catalog-hash",
        "v2-test",
    )

    assert status["route_preflight"] == {
        "status": "degraded",
        "routes": [
            {
                "route": "mcp.lynchpin",
                "status": "pass",
                "tool_count": 8,
                "read_only_tool_count": 3,
            },
            {
                "route": "mcp.polylogue",
                "status": "unavailable",
                "tool_count": None,
                "read_only_tool_count": None,
                "failure_class": "upstream_unavailable",
            },
        ],
    }


def test_gateway_status_keeps_unapproved_principal_unobserved(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")

    status = runtime.observe.gateway_status(
        "operator", "capability-hash", "operator-live-hash", "catalog-hash", "v2-test"
    )

    assert status["manifests"]["nix_approved"] is None
    assert status["catalog"]["chatgpt_observed"] is None
    assert set(status["catalog"]["comparisons"].values()) == {"unobserved"}
    assert status["manifests"]["comparisons"] == {
        "live_to_nix_approved": "unobserved",
        "live_to_chatgpt_observed": "unobserved",
        "nix_approved_to_chatgpt_observed": "unobserved",
    }


def test_state_is_private_and_artifact_ids_are_opaque(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    runtime = Runtime.create(cfg, "agent-control")
    directory = cfg.state_dir / "diagnostics" / "fixture"
    directory.mkdir(parents=True)
    source = directory / "fixture.log"
    source.write_bytes(b"abcdef")
    source.chmod(0o600)
    (directory / "receipt.json").write_text(
        json.dumps(
            {
                "schema": "sinnix.gateway-diagnostic-receipt.v1",
                "diagnostic_id": "fixture",
                "files": [source.name],
            }
        )
    )
    first = runtime.artifacts.register(source, kind="log", owner_id="job-a")
    second = runtime.artifacts.register(source, kind="log", owner_id="job-a")
    assert first != second
    assert oct(cfg.state_dir.stat().st_mode & 0o777) == "0o700"
    chunk = runtime.artifacts.read(first, offset=3, max_bytes=3)
    assert chunk["base64"] == "ZGVm"
    assert "source" not in chunk


def test_artifacts_are_scoped_to_the_creating_principal(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    operator = Runtime.create(cfg, "operator")
    observer = Runtime.create(cfg, "observer")

    operator_artifact = operator.artifacts.register_json(
        {"secret": "operator-only"},
        kind="operator-fixture",
        owner_id="operator-test",
        source="test.operator",
        target={"id": "operator"},
    )

    assert observer.artifacts.list()["artifacts"] == []
    with pytest.raises(ArtifactError, match="unavailable to this principal"):
        observer.artifacts.read(operator_artifact["artifact_id"])

    observer_artifact = observer.artifacts.register_json(
        {"visible": True},
        kind="observer-fixture",
        owner_id="observer-test",
        source="test.observer",
        target={"id": "observer"},
    )
    assert (
        observer.artifacts.read(observer_artifact["artifact_id"])["kind"]
        == "observer-fixture"
    )
    assert (
        operator.artifacts.read(observer_artifact["artifact_id"])["kind"]
        == "observer-fixture"
    )


def test_unknown_principal_is_rejected_before_server_creation(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        create_server(config(tmp_path), "unknown")


def test_approval_check_requires_the_current_paired_contract(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    approved = dataclasses.replace(
        cfg,
        approved_manifest_hash=anyio.run(build_manifest, cfg, "observer")["sha256"],
    )

    assert verify_approval(approved, "observer") == {
        "principal": "observer",
        "tool_manifest_hash": approved.approved_manifest_hash,
        "action_catalog_hash": action_set.catalog_hash("observer"),
    }

    with pytest.raises(ValueError, match="tool manifest drift"):
        verify_approval(
            dataclasses.replace(approved, approved_manifest_hash="stale"), "observer"
        )
    with pytest.raises(ValueError, match="principal"):
        verify_approval(approved, "operator")


def test_semantic_canary_exercises_catalog_and_project_list_envelopes(
    tmp_path: Path,
) -> None:
    result = anyio.run(semantic_canary, config(tmp_path), "observer")

    assert result["principal"] == "observer"
    assert result["catalog_actions"] >= 4
    assert result["projects"] == 1


def test_config_load_uses_one_project_contract(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    path = tmp_path / "gateway.json"
    path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {
                    "fixture": {
                        "path": str(project),
                        "observerRead": True,
                        "devtoolsEntrypoint": "nix develop",
                        "taskAuthority": {
                            "owner": "beads",
                            "workspace": str(project / ".beads"),
                            "database": str(project / ".beads" / "dolt"),
                            "publicationPolicy": "dolt-sync",
                        },
                    }
                },
            }
        )
    )
    loaded = GatewayConfig.load(path)
    assert loaded.projects["fixture"].path == project
    assert loaded.projects["fixture"].observer_read is True
    assert loaded.projects["fixture"].devtools_entrypoint == "nix develop"
    assert loaded.projects["fixture"].task_authority is not None
    assert (
        loaded.projects["fixture"].task_authority.database
        == project / ".beads" / "dolt"
    )


def test_config_rejects_retired_project_visibility_fields(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    path = tmp_path / "gateway.json"
    path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {
                    "fixture": {
                        "path": str(project),
                        "remoteRead": True,
                    }
                },
            }
        )
    )

    with pytest.raises(ValueError, match="retired gateway field"):
        GatewayConfig.load(path)


def test_machine_query_selects_and_pages_large_collector_report(tmp_path: Path) -> None:
    report = {
        "schema": "sinnix.observe.v1",
        "generated_at": "2026-08-21T00:00:00Z",
        "window": {"start": "2026-08-20T00:00:00Z"},
        "live_pressure": {"state": "quiet"},
        "config_drift": {"state": "clean"},
        "gaps_summary": {"count": 0},
        "storage": {"available": True},
        "sources": {"observe": "live"},
        "below": {"available": True},
        "systemd_units": [{"unit": f"fixture-{index}.service"} for index in range(100)],
        "workload_rows": [{"workload": "fixture"}],
        "resource_slices": [{"slice": "agent.slice"}],
        "blocked_tasks": [],
        "runtime_inventory": {"surfaces": []},
        "agent_gateway": {"available": True},
        "chrome_io": {"available": True},
        "polylogue_live_attempts": {"available": False},
        "sinex_xtask_history": {"available": False},
    }
    collector = tmp_path / "observe-fixture"
    collector.write_text(
        f"""#!{sys.executable}
import json
import sys

report = {report!r}
section = sys.argv[sys.argv.index("--section") + 1]
if section == "units":
    cursor = int(sys.argv[sys.argv.index("--cursor") + 1])
    page_limit = int(sys.argv[sys.argv.index("--page-limit") + 1])
    rows = report["systemd_units"]
    next_cursor = cursor + len(rows[cursor : cursor + page_limit])
    report["systemd_units"] = {{
        "total": len(rows),
        "cursor": cursor,
        "next_cursor": next_cursor if next_cursor < len(rows) else None,
        "rows": rows[cursor : cursor + page_limit],
    }}
print(json.dumps(report))
"""
    )
    collector.chmod(0o700)
    cfg = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        observe_command=str(collector),
        max_result_bytes=1_024,
    )
    runtime = Runtime.create(cfg, "observer")

    overview = runtime.observe.machine_query("overview")
    units = runtime.observe.machine_query("units", cursor=20, limit=3)

    assert overview["available"] is True
    assert overview["source"]["schema"] == "sinnix.observe.v1"
    assert overview["sections"]["live_pressure"] == {"state": "quiet"}
    assert units["total"] == 100
    assert units["cursor"] == 20
    assert units["next_cursor"] == 23
    assert [row["unit"] for row in units["rows"]] == [
        "fixture-20.service",
        "fixture-21.service",
        "fixture-22.service",
    ]


def test_machine_section_overflow_is_retained_as_an_attested_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Runtime.create(
        dataclasses.replace(config(tmp_path), max_result_bytes=1_024), "observer"
    )
    report = {
        "schema": "sinnix.observe.v1",
        "generated_at": "2026-08-21T00:00:00Z",
        "window": {},
        "live_pressure": {"detail": "x" * 4_000},
    }
    monkeypatch.setattr(
        runtime.observe,
        "_collect_report",
        lambda operation, cursor=0, page_limit=None: {
            "available": True,
            "report": report,
        },
    )

    result = runtime.observe.machine_query("pressure")

    assert result["available"] is True
    assert result["truncated"] is True
    assert result["artifact"]["ref"].startswith("sinnix://artifacts/")


def test_machine_query_requests_owner_selected_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    calls = []
    report = {
        "schema": "sinnix.observe.v1",
        "generated_at": "2026-08-21T00:00:00Z",
        "window": {},
        "systemd_units": {"total": 0, "cursor": 0, "next_cursor": None, "rows": []},
    }
    monkeypatch.setattr(
        runtime.observe.execution,
        "run",
        lambda command, _profile: (
            calls.append(command)
            or ExecutionResult(
                command=tuple(command),
                exit_status=0,
                stdout=json.dumps(report).encode(),
                stderr=b"",
            )
        ),
    )

    result = runtime.observe.machine_query("units")

    assert result["available"] is True
    assert calls == [
        [
            runtime.config.observe_command,
            "--format",
            "json",
            "--limit",
            "20",
            "--section",
            "units",
            "--cursor",
            "0",
            "--page-limit",
            "100",
        ]
    ]


def test_machine_query_reduces_page_to_response_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Runtime.create(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            max_result_bytes=1_024,
        ),
        "observer",
    )
    rows = [
        {"unit": f"fixture-{index}.service", "detail": "x" * 700} for index in range(3)
    ]

    def collect(_operation: str, cursor: int, page_limit: int) -> dict[str, object]:
        selected = rows[cursor : cursor + page_limit]
        next_cursor = cursor + len(selected)
        return {
            "available": True,
            "report": {
                "schema": "sinnix.observe.v1",
                "generated_at": "2026-08-21T00:00:00Z",
                "window": {},
                "systemd_units": {
                    "total": len(rows),
                    "cursor": cursor,
                    "next_cursor": next_cursor if next_cursor < len(rows) else None,
                    "rows": selected,
                },
            },
        }

    monkeypatch.setattr(runtime.observe, "_collect_report", collect)

    result = runtime.observe.machine_query("units", limit=3)

    assert len(result["rows"]) == 1
    assert result["next_cursor"] == 1


def test_manifests_are_typed_actions_filtered_by_principal(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    observer = anyio.run(build_manifest, cfg, "observer")
    operator = anyio.run(build_manifest, cfg, "operator")
    operator_names = {row["name"] for row in operator["tools"]}
    observer_names = {row["name"] for row in observer["tools"]}
    assert operator_names == {a.name for a in action_set.visible("operator")}
    assert observer_names == {a.name for a in action_set.visible("observer")}
    assert observer_names < operator_names
    assert "files.change" not in observer_names and "files.change" in operator_names
    for row in operator["tools"]:
        action = action_set.BY_NAME[row["name"]]
        assert row["inputSchema"] == action.input_schema()
        assert row["inputSchema"].get("additionalProperties") is False
        assert "parameters" not in row["inputSchema"]["properties"]
        assert "outputSchema" not in row
        expected_read = action.family.value in {
            "status",
            "catalog",
            "query",
            "get",
            "context",
            "events",
            "wait",
        }
        assert row["annotations"]["readOnlyHint"] is expected_read
    assert observer["sha256"] != operator["sha256"]
    assert operator["measurement"]["tool_count"] == len(operator_names)


def test_stdio_transport_negotiates_typed_tools(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    subprocess.run(["git", "init", "--quiet", cfg.projects["fixture"].path], check=True)
    config_path = tmp_path / "gateway.json"
    config_path.write_text(
        json.dumps(
            {
                "stateDir": str(cfg.state_dir),
                "projects": {
                    "fixture": {
                        "path": str(cfg.projects["fixture"].path),
                        "observerRead": True,
                    }
                },
            }
        )
    )

    async def probe() -> None:
        executable = os.environ.get("SINNIX_GATEWAY_TEST_EXECUTABLE")
        command = executable or sys.executable
        args = [] if executable else ["-m", "sinnix_agent_gateway.cli"]
        args.extend(["--config", str(config_path), "--principal", "observer", "serve"])
        async with stdio_client(StdioServerParameters(command=command, args=args)) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                assert initialized.server_info.name == "sinnix-agent-gateway"
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                assert "gateway.status" in tools and "projects.list" in tools
                assert "files.change" not in tools
                assert tools["files.read"].input_schema["properties"]["target"]
                templates = await session.list_resource_templates()
                assert templates.next_cursor
                status = await session.call_tool("gateway.status", {})
                assert status.structured_content is not None
                assert status.structured_content["result"]["outcome"] == "ok"
                assert status.structured_content["data"]["principal"] == "observer"
                projects = await session.call_tool("projects.list", {})
                assert (
                    projects.structured_content["data"]["projects"][0]["project_id"]
                    == "fixture"
                )
                denied = await session.call_tool(
                    "files.read", {"target": {"path": "/run/agenix/secret"}}
                )
                assert denied.is_error
                assert denied.structured_content["error"]["code"] in {
                    "policy_denied",
                    "not_found",
                }

    anyio.run(probe)
