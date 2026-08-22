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
from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.execution import ExecutionResult, OwnerDiagnosticError
from sinnix_agent_gateway.capabilities import PolicyError
from sinnix_agent_gateway.cli import build_manifest, parser
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.jobs import JobError
from sinnix_agent_gateway.projects import ProjectError
from sinnix_agent_gateway.schemas import AgentLaunchRequest


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


def test_official_sdk_principals_have_stable_distinct_manifests(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    readonly = anyio.run(build_manifest, cfg, "observer")
    local = anyio.run(build_manifest, cfg, "agent-control")
    operator = anyio.run(build_manifest, cfg, "operator")
    readonly_names = {row["name"] for row in readonly["tools"]}
    local_names = {row["name"] for row in local["tools"]}
    operator_names = {row["name"] for row in operator["tools"]}
    assert {
        "files_read",
        "project_read",
        "session_list",
        "session_read",
        "machine_query",
        "desktop_read",
        "desktop_capture",
        "terminal_read",
        "browser_read",
        "browser_capture",
        "capability_search",
        "capability_describe",
        "tasks_read",
        "memory_search",
        "memory_get",
        "timeline_query",
        "mcp_catalog",
        "mcp_read",
    } <= readonly_names
    assert {
        "files_write",
        "project_write",
        "agent_launch",
        "machine_action",
        "desktop_action",
        "terminal_action",
        "browser_action",
        "shell_run",
        "shell_start",
    }.isdisjoint(readonly_names)
    assert "shell_query" not in readonly_names
    assert {"agent_launch", "job_cancel", "capability_search", "capability_describe"} <= local_names
    assert {
        "desktop_action",
        "desktop_read",
        "desktop_capture",
        "files_read",
        "machine_action",
        "session_list",
        "browser_action",
        "browser_read",
        "browser_capture",
        "terminal_action",
        "terminal_read",
        "shell_run",
        "shell_start",
        "tasks_read",
        "tasks_write",
        "memory_search",
        "memory_get",
        "timeline_query",
        "mcp_catalog",
        "mcp_read",
        "mcp_write",
    }.isdisjoint(local_names)
    assert {
        "files_write",
        "project_write",
        "project_apply_patch",
        "session_search",
        "machine_action",
        "desktop_action",
        "desktop_read",
        "desktop_capture",
        "browser_action",
        "browser_read",
        "browser_capture",
        "terminal_action",
        "terminal_read",
        "shell_run",
        "shell_start",
        "capability_search",
        "capability_describe",
        "tasks_read",
        "tasks_write",
        "memory_search",
        "memory_get",
        "timeline_query",
        "mcp_catalog",
        "mcp_read",
        "mcp_write",
    } <= operator_names
    assert "project_context" in readonly_names & local_names & operator_names
    assert readonly["sha256"] != local["sha256"] != operator["sha256"]
    assert all(
        "inputSchema" in row and "outputSchema" in row for row in readonly["tools"]
    )
    assert all(
        row["annotations"]
        == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
        for row in readonly["tools"]
    )


def test_stdio_transport_negotiates_and_lists_readonly_tools(tmp_path: Path) -> None:
    cfg = config(tmp_path)
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
        args.extend(
            [
                "--config",
                str(config_path),
                "--principal",
                "observer",
                "serve",
            ]
        )
        parameters = StdioServerParameters(
            command=command,
            args=args,
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                templates = await session.list_resource_templates()
                names = {tool.name for tool in tools.tools}
                assert initialized.server_info.name == "sinnix-agent-gateway"
                assert {"status", "catalog", "project_read"} <= names
                assert "project_write" not in names
                assert "agent_launch" not in names
                assert {
                    "sinnix://gateway/v2/actions/{action_name}",
                    "sinnix://gateway/v2/resources/{resource_kind}",
                    "sinnix://receipts/{receipt_id}",
                    "sinnix://results/{result_id}",
                } <= {template.uri_template for template in templates.resource_templates}
                action_resource = await session.read_resource(
                    "sinnix://gateway/v2/actions/gateway.catalog"
                )
                action_contract = json.loads(action_resource.contents[0].text)
                resource_resource = await session.read_resource(
                    "sinnix://gateway/v2/resources/bead"
                )
                resource_contract = json.loads(resource_resource.contents[0].text)
                documentation = await session.read_resource(
                    "sinnix://gateway/v2/documentation"
                )
                documentation_rows = json.loads(documentation.contents[0].text)
                assert action_contract["action"]["schema_ref"] == (
                    "sinnix://gateway/v2/actions/gateway.catalog"
                )
                assert resource_contract["resource"] == {
                    "availability": "declared",
                    "contract_ref": "sinnix://gateway/v2/resources/bead",
                    "kind": "bead",
                    "owner": "beads",
                    "principals": ["agent-control", "observer", "operator"],
                    "readable_projections": ["summary", "history", "graph"],
                    "ref_template": "sinnix://projects/{project_id}/beads/{bead_id}",
                    "supports_query": True,
                }
                assert {row["name"] for row in documentation_rows["actions"]} == {
                    "gateway.catalog",
                    "gateway.status",
                }
                assert all(
                    "observer" in row["principals"]
                    for row in documentation_rows["resources"]
                )
                result = await session.call_tool("status", {})
                status_envelope = json.loads(result.content[0].text)
                status = status_envelope["data"]
                assert status_envelope["schema"] == "sinnix.gateway-result.v2"
                assert status_envelope["result"]["action"] == "gateway.status"
                assert status_envelope["result"]["outcome"] == "ok"
                assert status_envelope["receipt"]["ref"].startswith("sinnix://receipts/")
                assert status["principal"] == "observer"
                assert status["route_preflight"]["routes"]
                assert status["manifests"]["live_server"]["sha256"]
                assert status["manifests"]["comparisons"] == {
                    "live_to_nix_approved": "unobserved",
                    "live_to_chatgpt_observed": "unobserved",
                    "nix_approved_to_chatgpt_observed": "unobserved",
                }
                result_resource = await session.read_resource(
                    status_envelope["result"]["ref"]
                )
                receipt_resource = await session.read_resource(
                    status_envelope["receipt"]["ref"]
                )
                assert json.loads(result_resource.contents[0].text) == status_envelope
                assert json.loads(receipt_resource.contents[0].text)["outcome"] == "ok"
                catalog_result = await session.call_tool("catalog", {"text": "gateway"})
                catalog_envelope = json.loads(catalog_result.content[0].text)
                catalog = catalog_envelope["data"]
                assert catalog_envelope["result"]["action"] == "gateway.catalog"
                assert [action["name"] for action in catalog["actions"]] == [
                    "gateway.status",
                    "gateway.catalog",
                ]
                invalid_catalog_result = await session.call_tool(
                    "catalog", {"verb": "unrecognized"}
                )
                invalid_catalog = json.loads(invalid_catalog_result.content[0].text)
                assert invalid_catalog["result"]["outcome"] == "error"
                assert invalid_catalog["error"]["code"] == "invalid_request"
                assert invalid_catalog["receipt"]["ref"].startswith(
                    "sinnix://receipts/"
                )
                mcp_catalog_result = await session.call_tool("mcp_catalog", {})
                assert json.loads(mcp_catalog_result.content[0].text) == {"servers": []}

    anyio.run(probe)


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


def test_runtime_returns_owner_diagnostic_and_audits_its_reference(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    response = {
        "available": False,
        "failure_class": "command_timeout",
        "route": "terminal-kitty",
        "exit_status": None,
        "timed_out": True,
        "output_exceeded": False,
        "diagnostic_artifact_id": "fixture-artifact",
    }

    def fail() -> None:
        raise OwnerDiagnosticError(response)

    assert runtime.execute("terminal_read", fail) == {
        "operation": "terminal_read",
        **response,
    }
    event = runtime.audit.tail(1)["events"][0]
    assert event["outcome"] == "error"
    assert event["payload"] == {
        "failure_class": "command_timeout",
        "route": "terminal-kitty",
        "exit_status": None,
        "timed_out": True,
        "output_exceeded": False,
        "diagnostic_artifact_id": "fixture-artifact",
    }


def test_runtime_audit_carries_returned_job_correlation(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "agent-control")
    runtime.execute(
        "agent_launch", lambda: {"job_id": "job-correlation", "secret": "hidden"}
    )
    payload = runtime.audit.tail(1)["events"][0]["payload"]
    assert payload == {"job_id": "job-correlation", "correlation_id": "job-correlation"}


def test_runtime_audit_carries_upstream_mcp_target(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    runtime.execute(
        "mcp_read",
        lambda: {
            "server": "fixture",
            "tool": "fixture_read",
            "mode": "read",
            "secret": "hidden",
        },
    )

    assert runtime.audit.tail(1)["events"][0]["payload"] == {
        "server": "fixture",
        "tool": "fixture_read",
        "mode": "read",
    }


def test_runtime_audit_carries_returned_transient_unit(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    runtime.execute(
        "shell_run",
        lambda: {"unit": "sinnix-gateway-run-fixture.service", "secret": "hidden"},
    )
    payload = runtime.audit.tail(1)["events"][0]["payload"]
    assert payload == {"unit": "sinnix-gateway-run-fixture.service"}


def test_runtime_audit_carries_execution_job_and_scope(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    runtime.execute(
        "shell_start",
        lambda: {
            "job_id": "shell-fixture",
            "unit": "sinnix-gateway-exec-shell-fixture.scope",
            "secret": "hidden",
        },
    )

    payload = runtime.audit.tail(1)["events"][0]["payload"]

    assert payload == {
        "job_id": "shell-fixture",
        "unit": "sinnix-gateway-exec-shell-fixture.scope",
        "correlation_id": "shell-fixture",
    }


def test_runtime_audit_carries_returned_owner_receipt(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    runtime.execute(
        "machine_action",
        lambda: {"receipt_id": "owner-receipt", "secret": "hidden"},
    )
    payload = runtime.audit.tail(1)["events"][0]["payload"]
    assert payload == {"receipt_id": "owner-receipt"}


def test_runtime_audit_carries_file_mutation_receipt(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    runtime.execute(
        "files_write",
        lambda: {
            "operation": "move",
            "path": "/realm/tmp/work/gateway-demo/fixture.txt",
            "destination": "/realm/tmp/work/gateway-demo/moved.txt",
            "bytes": 7,
            "previous_sha256": None,
            "sha256": "fixture-hash",
            "secret": "hidden",
        },
    )

    payload = runtime.audit.tail(1)["events"][0]["payload"]

    assert payload == {
        "operation": "move",
        "path": "/realm/tmp/work/gateway-demo/fixture.txt",
        "destination": "/realm/tmp/work/gateway-demo/moved.txt",
        "bytes": 7,
        "sha256": "fixture-hash",
    }


def test_gateway_status_reports_distinct_manifest_provenance(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    runtime = Runtime.create(cfg, "observer")
    status = runtime.observe.gateway_status(
        "observer", "capability-hash", "approved-fixture-hash", "catalog-hash", "v2-test"
    )
    assert status["principal_contract_hash"] == "capability-hash"
    assert status["catalog"] == {
        "revision": "v2-test",
        "action_catalog_hash": "catalog-hash",
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
            }
        )
    )
    status = runtime.observe.gateway_status(
        "observer", "capability-hash", "approved-fixture-hash", "catalog-hash", "v2-test"
    )
    assert set(status["manifests"]["comparisons"].values()) == {"match"}

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
        "observer", "capability-hash", "approved-fixture-hash", "catalog-hash", "v2-test"
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
    assert status["manifests"]["comparisons"] == {
        "live_to_nix_approved": "unobserved",
        "live_to_chatgpt_observed": "unobserved",
        "nix_approved_to_chatgpt_observed": "unobserved",
    }


def test_state_is_private_and_artifact_ids_are_opaque(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    runtime = Runtime.create(cfg, "agent-control")
    source = cfg.state_dir / "jobs" / "job.log"
    source.write_bytes(b"abcdef")
    source.chmod(0o600)
    first = runtime.artifacts.register(source, kind="log", owner_id="job-a")
    second = runtime.artifacts.register(source, kind="log", owner_id="job-a")
    assert first != second
    assert oct(cfg.state_dir.stat().st_mode & 0o777) == "0o700"
    chunk = runtime.artifacts.read(first, offset=3, max_bytes=3)
    assert chunk["base64"] == "ZGVm"
    assert "source" not in chunk


def test_malformed_job_records_are_visible(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "agent-control")
    (runtime.jobs.root / "broken.json").write_text("{not-json")
    result = runtime.jobs.list()
    assert result["jobs"] == []
    assert result["malformed_records"][0]["record"] == "broken.json"


def test_job_list_preserves_schema_three_manifests(tmp_path: Path) -> None:
    controller = tmp_path / "agent-job-control"
    controller.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        "print((pathlib.Path(sys.argv[2]) / f'{sys.argv[5]}.json').read_text())\n"
    )
    controller.chmod(0o700)
    cfg = dataclasses.replace(config(tmp_path), agent_controller=controller)
    runtime = Runtime.create(cfg, "agent-control")
    manifest = {
        "schema_version": 3,
        "job_id": "schema-three-job",
        "lifecycle": "completed",
        "launcher": {"scope_unit": "sinnix-agent-job-schema-three-job.scope"},
    }
    (runtime.jobs.root / "schema-three-job.json").write_text(json.dumps(manifest))

    result = runtime.jobs.list()

    assert [job["job_id"] for job in result["jobs"]] == ["schema-three-job"]
    assert result["malformed_records"] == []


def test_gateway_status_uses_shared_native_controller(tmp_path: Path) -> None:
    controller = tmp_path / "agent-job-control"
    controller.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        "value=json.loads((pathlib.Path(sys.argv[2]) / f'{sys.argv[5]}.json').read_text())\n"
        "value['lifecycle']='timed_out'\n"
        "value['live']={'available':True,'Result':'timeout','MemoryHigh':'2G'}\n"
        "print(json.dumps(value))\n"
    )
    controller.chmod(0o700)
    cfg = dataclasses.replace(config(tmp_path), agent_controller=controller)
    runtime = Runtime.create(cfg, "agent-control")
    manifest = {
        "schema_version": 2,
        "job_id": "deadline-job",
        "lifecycle": "running",
        "launcher": {
            "pid": 1,
            "proc_start": "1",
            "scope_unit": "sinnix-agent-job-deadline-job.scope",
            "cgroup": "/fixture",
        },
        "worktree": str(cfg.projects["fixture"].path),
    }
    (runtime.jobs.root / "deadline-job.json").write_text(json.dumps(manifest))
    status = runtime.jobs.status("deadline-job")
    assert status["lifecycle"] == "timed_out"
    assert status["live"]["Result"] == "timeout"
    assert status["live"]["MemoryHigh"] == "2G"


def test_gateway_rejects_runner_job_id_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "00000000-0000-4000-8000-000000000001"
    runner = tmp_path / "runner"
    runner.write_text("#!/bin/sh\nexit 2\n")
    runner.chmod(0o700)
    cfg = dataclasses.replace(config(tmp_path), agent_runner=runner)
    runtime = Runtime.create(cfg, "agent-control")
    old_prompt = runtime.jobs.root / f"{job_id}.prompt.md"
    old_prompt.write_text("original")
    (runtime.jobs.root / f"{job_id}.json").write_text(
        json.dumps({"schema_version": 2, "job_id": job_id, "launch_id": "original"})
    )
    monkeypatch.setattr("sinnix_agent_gateway.jobs.uuid.uuid4", lambda: job_id)
    with pytest.raises(JobError, match="collision"):
        runtime.jobs.launch_agent(
            AgentLaunchRequest(project_id="fixture", prompt="new", backend="codex")
        )
    assert old_prompt.read_text() == "original"


def test_agent_environment_is_explicitly_allowlisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SINNIX_GATEWAY_PROBE_SECRET", "must-not-propagate")
    runtime = Runtime.create(config(tmp_path), "agent-control")
    environment = runtime.jobs._environment()
    assert "SINNIX_GATEWAY_PROBE_SECRET" not in environment
    assert "PATH" in environment


def test_unknown_principal_is_rejected_before_server_creation(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        create_server(config(tmp_path), "unknown")


def test_cli_rejects_retired_profile_flag() -> None:
    with pytest.raises(SystemExit):
        parser().parse_args(["--profile", "observer", "info"])


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
                    }
                },
            }
        )
    )
    loaded = GatewayConfig.load(path)
    assert loaded.projects["fixture"].path == project
    assert loaded.projects["fixture"].observer_read is True


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


def test_machine_report_timeout_is_a_typed_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")

    monkeypatch.setattr(
        runtime.observe.execution,
        "run",
        lambda *_args, **_kwargs: ExecutionResult(
            command=("sinnix-observe",),
            exit_status=-15,
            stdout=b"",
            stderr=b"",
            timed_out=True,
            failure_class="command_timeout",
        ),
    )
    result = runtime.observe.machine_report()
    assert result["failure_class"] == "collector_timeout"


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

    machine_report = runtime.observe.machine_report()
    overview = runtime.observe.machine_query("overview")
    units = runtime.observe.machine_query("units", cursor=20, limit=3)

    assert machine_report["available"] is True
    assert machine_report["operation"] == "overview"
    assert machine_report["sections"]["live_pressure"] == {"state": "quiet"}
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
        lambda command, _profile: calls.append(command)
        or ExecutionResult(
            command=tuple(command),
            exit_status=0,
            stdout=json.dumps(report).encode(),
            stderr=b"",
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
        {"unit": f"fixture-{index}.service", "detail": "x" * 700}
        for index in range(3)
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
