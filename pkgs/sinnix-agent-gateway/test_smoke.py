from __future__ import annotations

import base64
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
from sinnix_agent_gateway.server import _query_owner
from sinnix_mcp.execution import ExecutionResult, OwnerDiagnosticError
from sinnix_agent_gateway.capabilities import PolicyError
from sinnix_agent_gateway.cli import build_manifest, parser, verify_approval
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.projects import ProjectError
from sinnix_agent_gateway.registry import REGISTRY


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
        approved_action_catalog_hash="catalog-hash",
    )


def test_official_sdk_principals_expose_only_protocol_verbs(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    observer = anyio.run(build_manifest, cfg, "observer")
    agent_control = anyio.run(build_manifest, cfg, "agent-control")
    operator = anyio.run(build_manifest, cfg, "operator")
    names = {row["name"] for row in operator["tools"]}

    assert names == {
        "status", "catalog", "query", "get", "context", "events", "wait",
        "change", "operate", "run",
    }
    assert {row["name"] for row in observer["tools"]} == {
        "status", "catalog", "query", "get", "context", "events", "wait",
    }
    assert {row["name"] for row in agent_control["tools"]} == {
        "status", "catalog", "query", "get", "context", "events", "wait",
        "operate", "run",
    }
    assert not any(row["annotations"]["readOnlyHint"] for row in operator["tools"])
    assert {
        row["name"]
        for row in operator["tools"]
        if row["annotations"] == {
            "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
            "openWorldHint": False,
        }
    } == {"status", "catalog", "query", "get", "context", "events", "wait"}
    assert next(row for row in operator["tools"] if row["name"] == "change")["annotations"] == {
        "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True,
        "openWorldHint": False,
    }
    assert next(row for row in operator["tools"] if row["name"] == "operate")["annotations"] == {
        "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True,
        "openWorldHint": False,
    }
    assert next(row for row in operator["tools"] if row["name"] == "run")["annotations"] == {
        "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
        "openWorldHint": True,
    }
    assert all(
        row["annotations"] == {
            "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
            "openWorldHint": False,
        }
        for row in observer["tools"]
    )
    assert all("inputSchema" in row and "outputSchema" in row for row in operator["tools"])
    assert observer["sha256"] != agent_control["sha256"] != operator["sha256"]
    assert operator["measurement"] == {
        "schema": "sinnix.gateway-schema-measurement.v1",
        "canonical_bytes": operator["measurement"]["canonical_bytes"],
        "tool_count": 10,
        "baseline": {
            "source_commit": "e5980a67eae343f954f695c46a8fadda83961a03",
            "canonical_bytes": 30_350,
            "tool_count": 49,
        },
        "token_lane": operator["measurement"]["token_lane"],
    }
    assert operator["measurement"]["canonical_bytes"] < 30_350
    assert operator["measurement"]["token_lane"] == {
        "status": "estimated",
        "method": "canonical_bytes_divided_by_4",
        "estimated_tokens": (operator["measurement"]["canonical_bytes"] + 3) // 4,
        "reason": "No tokenizer is a declared gateway runtime dependency.",
    }


def test_stdio_transport_negotiates_and_lists_readonly_tools(tmp_path: Path) -> None:
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
                assert names == {
                    "status", "catalog", "query", "get", "context", "events", "wait",
                }
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
                parity = await session.read_resource("sinnix://gateway/v2/legacy-parity")
                parity_rows = json.loads(parity.contents[0].text)
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
                assert {
                    "audit.events",
                    "gateway.catalog",
                    "gateway.status",
                    "jobs.wait",
                    "projects.context",
                    "projects.query",
                    "beads.query",
                    "resources.get",
                    "machine.query",
                    "captures.query",
                    "artifacts.query",
                    "files.query",
                    "sessions.query",
                    "mcp.query",
                } <= {row["name"] for row in documentation_rows["actions"]}
                assert parity_rows["legacy_manifest"]["tool_count"] == 49
                assert len(parity_rows["rows"]) == 49
                assert all(
                    "observer" in row["principals"]
                    for row in documentation_rows["resources"]
                )
                result = await session.call_tool("status", {})
                status_envelope = json.loads(result.content[0].text)
                status = status_envelope["data"]
                assert status_envelope["schema"] == "sinnix.gateway-result.v3"
                assert result.is_error is False
                assert result.structured_content == status_envelope
                status_tool = next(tool for tool in tools.tools if tool.name == "status")
                assert status_tool.output_schema != REGISTRY.action(
                    "gateway.status"
                ).output_schema
                assert action_contract["action"]["output_schema"] == REGISTRY.action(
                    "gateway.status"
                ).output_schema
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
                assert {
                    "gateway.status",
                    "gateway.catalog",
                } <= {action["name"] for action in catalog["actions"]}
                project_catalog_result = await session.call_tool(
                    "catalog", {"project": "fixture"}
                )
                project_catalog = json.loads(project_catalog_result.content[0].text)["data"]
                assert project_catalog["project"] == {
                    "project_id": "fixture",
                    "available": True,
                    "default_ref": "master",
                    "observer_read": True,
                    "writable": False,
                    "ref": "sinnix://projects/fixture",
                }
                assert {resource["kind"] for resource in project_catalog["resources"]} == {
                    "project",
                    "checkout",
                    "bead",
                    "task_authority",
                }
                assert all(
                    resource["availability"] == "available"
                    for resource in project_catalog["resources"]
                )
                unavailable_catalog_result = await session.call_tool(
                    "catalog", {"availability": "unavailable"}
                )
                unavailable_catalog = json.loads(
                    unavailable_catalog_result.content[0].text
                )["data"]
                assert unavailable_catalog["actions"] == []
                assert {resource["kind"] for resource in unavailable_catalog["resources"]} == {
                    "context_snapshot",
                    "result",
                }
                assert all(
                    resource["availability_reason"]
                    == "no migrated V2 action currently exposes this resource"
                    for resource in unavailable_catalog["resources"]
                )
                get_result = await session.call_tool(
                    "get", {"ref": "sinnix://projects/fixture"}
                )
                project_envelope = json.loads(get_result.content[0].text)
                project_resource = project_envelope["data"]
                assert project_envelope["result"]["action"] == "resources.get"
                assert project_resource["kind"] == "project"
                assert project_resource["project"]["project_id"] == "fixture"
                checkout = project_resource["checkouts"][0]
                assert checkout["ref"] == "sinnix://projects/fixture/checkouts/default"
                assert checkout["checkout_id"] == "default"
                assert project_resource["task_authority"]["availability"] == "unavailable"
                checkout_result = await session.call_tool("get", {"ref": checkout["ref"]})
                checkout_resource = json.loads(checkout_result.content[0].text)["data"]
                assert checkout_resource["kind"] == "checkout"
                assert checkout_resource["checkout"]["checkout"]["checkout_id"] == "default"
                query_result = await session.call_tool(
                    "query", {"ref": checkout["ref"], "query": "fixture"}
                )
                query_envelope = json.loads(query_result.content[0].text)
                assert query_envelope["result"]["action"] == "projects.query"
                assert query_envelope["data"]["ref"] == checkout["ref"]
                assert query_envelope["data"]["project_ref"] == "sinnix://projects/fixture"
                assert query_envelope["meta"]["resource_refs"] == [
                    "sinnix://projects/fixture",
                    checkout["ref"],
                ]
                context_result = await session.call_tool(
                    "context", {"ref": "sinnix://projects/fixture"}
                )
                context_envelope = json.loads(context_result.content[0].text)
                context = context_envelope["data"]
                assert context_envelope["result"]["action"] == "projects.context"
                assert context["ref"] == "sinnix://projects/fixture"
                assert context["authority"]["canonical_checkout_ref"] == checkout["ref"]
                assert len(context["authority"]["code_revision"]) == 64
                assert context["authority"]["task_authority"]["availability"] == "unavailable"
                events_result = await session.call_tool("events", {"limit": 100})
                events_envelope = json.loads(events_result.content[0].text)
                assert events_envelope["result"]["action"] == "audit.events"
                assert events_envelope["data"]["events"]
                assert all(
                    event["ref"] == f"sinnix://receipts/{event['event_id']}"
                    for event in events_envelope["data"]["events"]
                )
                invalid_catalog_result = await session.call_tool(
                    "catalog", {"verb": "unrecognized"}
                )
                invalid_catalog = json.loads(invalid_catalog_result.content[0].text)
                assert invalid_catalog_result.is_error is True
                assert invalid_catalog_result.structured_content == invalid_catalog
                assert invalid_catalog["result"]["outcome"] == "error"
                assert invalid_catalog["error"]["code"] == "invalid_request"
                assert invalid_catalog["receipt"]["ref"].startswith(
                    "sinnix://receipts/"
                )
                mcp_catalog_result = await session.call_tool(
                    "query", {"action_name": "mcp.query", "parameters": {"operation": "catalog"}}
                )
                assert json.loads(mcp_catalog_result.content[0].text)["data"] == {"servers": []}

    anyio.run(probe)


def test_public_v2_mutation_verbs_preserve_owner_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = config(tmp_path)
    runtime = Runtime.create(cfg, "operator")
    calls: dict[str, object] = {}

    def beads_change(project_id: str, operation: str, arguments: dict[str, object], **_kwargs: object) -> dict[str, object]:
        calls["beads"] = (project_id, operation, arguments)
        return {"project_id": project_id, "operation": operation, "mode": "apply", "atomicity": "owner_native"}

    async def mcp_call(
        server: str, tool: str, arguments: dict[str, object], *, write: bool
    ) -> dict[str, object]:
        calls["mcp"] = (server, tool, arguments, write)
        return {"server": server, "tool": tool, "mode": "write", "response": {"ok": True}}

    def desktop_owner(operation: str, arguments: dict[str, object]) -> dict[str, object]:
        calls["desktop"] = (operation, arguments)
        return {"operation": operation, "result": {"ok": True}}

    def terminal_owner(operation: str, arguments: dict[str, object]) -> dict[str, object]:
        calls["terminal"] = (operation, arguments)
        return {"operation": operation, "result": {"ok": True}}

    def browser_owner(operation: str, arguments: dict[str, object]) -> dict[str, object]:
        calls.setdefault("browser", []).append((operation, arguments))
        if operation == "agent_window":
            return {"operation": operation, "target": {"id": "agent-target", "parked": True}}
        return {"operation": operation, "page_id": arguments["page_id"], "result": {"ok": True}}

    monkeypatch.setattr(runtime.beads, "change", beads_change)
    monkeypatch.setattr(runtime.mcp_broker, "call", mcp_call)
    monkeypatch.setattr(runtime.desktop, "action", desktop_owner)
    monkeypatch.setattr(runtime.terminals, "action", terminal_owner)
    monkeypatch.setattr(runtime.browser, "action", browser_owner)
    monkeypatch.setattr(Runtime, "create", classmethod(lambda _cls, _cfg, _principal: runtime))
    server = create_server(cfg, "operator")
    target = tmp_path / "public-route.txt"
    file_token = base64.urlsafe_b64encode(str(target).encode()).decode().rstrip("=")

    async def invoke(name: str, arguments: dict[str, object]) -> dict[str, object]:
        response = await server.call_tool(name, arguments)
        assert response.structured_content is not None
        return response.structured_content

    file_result = anyio.run(
        invoke,
        "change",
        {
            "action_name": "files.change",
            "ref": f"sinnix://files/{file_token}",
            "operation": "replace",
            "parameters": {"content": "public route\n"},
            "idempotency_key": "public-file-change",
        },
    )
    beads_result = anyio.run(
        invoke,
        "change",
        {
            "action_name": "beads.change",
            "ref": "sinnix://projects/fixture",
            "operation": "comment",
            "parameters": {"id": "fixture-1", "text": "public route"},
            "idempotency_key": "public-beads-change",
        },
    )
    mcp_result = anyio.run(
        invoke,
        "change",
        {
            "action_name": "mcp.change",
            "ref": "sinnix://mcp/fixture/tools/mutate",
            "operation": "call",
            "parameters": {"value": "public route"},
            "idempotency_key": "public-mcp-change",
        },
    )
    desktop_result = anyio.run(
        invoke,
        "operate",
        {
            "action_name": "desktop.operate",
            "ref": "sinnix://desktop/current",
            "operation": "focus_window",
            "parameters": {"window": "address:0xfixture"},
            "idempotency_key": "public-desktop-operate",
        },
    )
    terminal_result = anyio.run(
        invoke,
        "operate",
        {
            "action_name": "terminals.operate",
            "ref": "sinnix://terminals/7",
            "operation": "send",
            "parameters": {"text": "printf fixture", "enter": True},
            "idempotency_key": "public-terminal-operate",
        },
    )
    window_result = anyio.run(
        invoke,
        "operate",
        {
            "action_name": "browser.operate",
            "ref": "sinnix://browser/agent-workspace",
            "operation": "agent_window",
            "parameters": {"url": "https://example.test"},
            "idempotency_key": "public-browser-window",
        },
    )
    browser_result = anyio.run(
        invoke,
        "operate",
        {
            "action_name": "browser.operate",
            "ref": "sinnix://browser/pages/agent-target",
            "operation": "navigate",
            "parameters": {"url": "https://example.test/next"},
            "idempotency_key": "public-browser-operate",
        },
    )
    unsupported = anyio.run(
        invoke,
        "change",
        {
            "action_name": "mcp.change",
            "ref": "sinnix://mcp/fixture/tools/mutate",
            "operation": "unsupported",
            "parameters": {},
            "idempotency_key": "public-mcp-unsupported",
        },
    )
    undeclared = anyio.run(
        invoke,
        "change",
        {
            "action_name": "undeclared.change",
            "ref": "sinnix://projects/fixture",
            "operation": "replace",
            "parameters": {},
            "idempotency_key": "public-undeclared-change",
        },
    )

    assert target.read_text() == "public route\n"
    assert calls["beads"] == ("fixture", "comment", {"id": "fixture-1", "text": "public route"})
    assert calls["mcp"] == ("fixture", "mutate", {"value": "public route"}, True)
    assert calls["desktop"] == ("focus_window", {"window": "address:0xfixture"})
    assert calls["terminal"] == ("send", {"match": "id:7", "text": "printf fixture", "enter": True})
    assert calls["browser"] == [
        ("agent_window", {"url": "https://example.test"}),
        ("navigate", {"page_id": "agent-target", "url": "https://example.test/next"}),
    ]
    assert [
        result["result"]["action"]
        for result in (file_result, beads_result, mcp_result, desktop_result, terminal_result, window_result, browser_result)
    ] == [
        "files.change",
        "beads.change",
        "mcp.change",
        "desktop.operate",
        "terminals.operate",
        "browser.operate",
        "browser.operate",
    ]
    assert window_result["data"]["target_ref"] == "sinnix://browser/pages/agent-target"
    assert browser_result["data"]["ref"] == "sinnix://browser/pages/agent-target"
    assert unsupported["error"]["code"] == "unsupported_capability"
    assert undeclared["error"]["code"] == "unsupported_capability"


def test_query_adapter_consumes_capture_selector_before_owner_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    captured: dict[str, object] = {}

    def query(*, lanes: list[str], since: float, limit: int) -> dict[str, object]:
        captured.update(lanes=lanes, since=since, limit=limit)
        return {"records": []}

    monkeypatch.setattr(runtime.captures, "query", query)
    result = anyio.run(
        _query_owner,
        runtime,
        "captures.query",
        None,
        None,
        200,
        {"operation": "query", "lanes": ["shell"], "since": 1.5, "limit": 4},
    )

    assert result == {"records": []}
    assert captured == {"lanes": ["shell"], "since": 1.5, "limit": 4}


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
        REGISTRY.action("audit.events"),
        lambda: observer.v2_events(100),
        {"limit": 100},
    )

    events = response["data"]["events"]
    assert {event["principal"] for event in events} == {"observer"}
    assert {event["operation"] for event in events} == {"observer_event"}
    assert response["meta"]["resource_refs"] == [
        f"sinnix://receipts/{events[0]['event_id']}"
    ]
    assert response["receipt"]["ref"].startswith("sinnix://receipts/")


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
        "agents.run", lambda: {"job_id": "job-correlation", "secret": "hidden"}
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
        "shell.run",
        lambda: {"unit": "sinnix-gateway-run-fixture.service", "secret": "hidden"},
    )
    payload = runtime.audit.tail(1)["events"][0]["payload"]
    assert payload == {"unit": "sinnix-gateway-run-fixture.service"}


def test_runtime_audit_carries_daemon_job_identity(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    runtime.execute(
        "shell.run",
        lambda: {
            "job_id": "shell-fixture",
            "unit": "sinnixd-job-shell-fixture.service",
            "secret": "hidden",
        },
    )

    payload = runtime.audit.tail(1)["events"][0]["payload"]

    assert payload == {
        "job_id": "shell-fixture",
        "unit": "sinnixd-job-shell-fixture.service",
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
        "files.change",
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
    assert status["tool_manifest_hash"] == "approved-fixture-hash"
    assert status["action_catalog_hash"] == "catalog-hash"
    assert status["catalog"] == {
        "revision": "v2-test",
        "live_action_catalog": {
            "principal": "observer",
            "sha256": "catalog-hash",
        },
        "nix_approved": {
            "principal": "observer",
            "sha256": "catalog-hash",
        },
        "chatgpt_observed": None,
        "comparisons": {
            "live_to_nix_approved": "match",
            "live_to_chatgpt_observed": "unobserved",
            "nix_approved_to_chatgpt_observed": "unobserved",
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
        "observer", "capability-hash", "approved-fixture-hash", "catalog-hash", "v2-test"
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
        "observer", "capability-hash", "approved-fixture-hash", "catalog-hash", "v2-test"
    )
    assert status["manifests"]["comparisons"] == {
        "live_to_nix_approved": "match",
        "live_to_chatgpt_observed": "mismatch",
        "nix_approved_to_chatgpt_observed": "mismatch",
    }


def test_gateway_status_reports_catalog_approval_drift(tmp_path: Path) -> None:
    cfg = dataclasses.replace(
        config(tmp_path), approved_action_catalog_hash="approved-catalog-hash"
    )
    runtime = Runtime.create(cfg, "observer")

    status = runtime.observe.gateway_status(
        "observer", "capability-hash", "approved-fixture-hash", "live-catalog-hash", "v2-test"
    )

    assert status["catalog"]["nix_approved"] == {
        "principal": "observer",
        "sha256": "approved-catalog-hash",
    }
    assert status["catalog"]["comparisons"]["live_to_nix_approved"] == "mismatch"


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
    assert status["catalog"]["nix_approved"] is None
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


def test_unknown_principal_is_rejected_before_server_creation(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        create_server(config(tmp_path), "unknown")


def test_approval_check_requires_the_current_paired_contract(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    approved = dataclasses.replace(
        cfg,
        approved_manifest_hash=anyio.run(build_manifest, cfg, "observer")["sha256"],
        approved_action_catalog_hash=REGISTRY.action_catalog_hash("observer"),
    )

    assert verify_approval(approved, "observer") == {
        "principal": "observer",
        "tool_manifest_hash": approved.approved_manifest_hash,
        "action_catalog_hash": approved.approved_action_catalog_hash,
    }

    with pytest.raises(ValueError, match="action catalog drift"):
        verify_approval(
            dataclasses.replace(
                approved, approved_action_catalog_hash="unapproved-catalog"
            ),
            "observer",
        )


def test_cli_exposes_catalog_hash_without_retired_profiles() -> None:
    assert parser().parse_args(["catalog-hash"]).command == "catalog-hash"
    assert parser().parse_args(["approval-check"]).command == "approval-check"
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
                "approvedActionCatalogHash": "fixture-catalog-hash",
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
    assert loaded.approved_action_catalog_hash == "fixture-catalog-hash"
    assert loaded.projects["fixture"].path == project
    assert loaded.projects["fixture"].observer_read is True
    assert loaded.projects["fixture"].devtools_entrypoint == "nix develop"
    assert loaded.projects["fixture"].task_authority is not None
    assert loaded.projects["fixture"].task_authority.database == project / ".beads" / "dolt"


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
