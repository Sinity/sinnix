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
from sinnix_agent_gateway import observe as observe_module
from sinnix_agent_gateway.app import Runtime, create_server
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
        "shell_query",
    } <= readonly_names
    assert {"files_write", "project_write", "agent_launch", "shell_run"}.isdisjoint(
        readonly_names
    )
    assert {"agent_launch", "job_cancel"} <= local_names
    assert {"files_read", "session_list", "shell_run"}.isdisjoint(local_names)
    assert {
        "files_write",
        "project_write",
        "project_apply_patch",
        "session_search",
        "shell_run",
    } <= operator_names
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
                names = {tool.name for tool in tools.tools}
                assert initialized.server_info.name == "sinnix-agent-gateway"
                assert "project_read" in names
                assert "project_write" not in names
                assert "agent_launch" not in names
                result = await session.call_tool("gateway_status", {})
                status = json.loads(result.content[0].text)
                assert status["principal"] == "observer"
                assert status["manifests"]["live_server"]["sha256"]
                assert status["manifests"]["comparisons"] == {
                    "live_to_nix_approved": "unobserved",
                    "live_to_chatgpt_observed": "unobserved",
                    "nix_approved_to_chatgpt_observed": "unobserved",
                }

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


def test_runtime_audit_carries_returned_job_correlation(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "agent-control")
    runtime.execute(
        "agent_launch", lambda: {"job_id": "job-correlation", "secret": "hidden"}
    )
    payload = runtime.audit.tail(1)["events"][0]["payload"]
    assert payload == {"job_id": "job-correlation", "correlation_id": "job-correlation"}


def test_runtime_audit_carries_returned_transient_unit(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    runtime.execute(
        "shell_run",
        lambda: {"unit": "sinnix-gateway-run-fixture.service", "secret": "hidden"},
    )
    payload = runtime.audit.tail(1)["events"][0]["payload"]
    assert payload == {"unit": "sinnix-gateway-run-fixture.service"}


def test_gateway_status_reports_distinct_manifest_provenance(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    runtime = Runtime.create(cfg, "observer")
    status = runtime.observe.gateway_status(
        "observer", "capability-hash", "approved-fixture-hash"
    )
    assert status["capability_contract_hash"] == "capability-hash"
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
        "observer", "capability-hash", "approved-fixture-hash"
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
        "observer", "capability-hash", "approved-fixture-hash"
    )
    assert status["manifests"]["comparisons"] == {
        "live_to_nix_approved": "match",
        "live_to_chatgpt_observed": "mismatch",
        "nix_approved_to_chatgpt_observed": "mismatch",
    }


def test_gateway_status_keeps_unapproved_principal_unobserved(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")

    status = runtime.observe.gateway_status(
        "operator", "capability-hash", "operator-live-hash"
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

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("sinnix-observe", 20)

    monkeypatch.setattr(observe_module.subprocess, "run", timeout)
    result = runtime.observe.machine_report()
    assert result["failure_class"] == "collector_timeout"
