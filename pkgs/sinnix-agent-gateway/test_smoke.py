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
from pydantic import ValidationError
from mcp.client.stdio import StdioServerParameters, stdio_client
from sinnix_agent_gateway import observe as observe_module
from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.capabilities import PolicyError
from sinnix_agent_gateway.files import FileError
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
            "operation": "replace",
            "path": "/realm/tmp/work/gateway-demo/fixture.txt",
            "bytes": 7,
            "previous_sha256": None,
            "sha256": "fixture-hash",
            "secret": "hidden",
        },
    )

    payload = runtime.audit.tail(1)["events"][0]["payload"]

    assert payload == {
        "operation": "replace",
        "path": "/realm/tmp/work/gateway-demo/fixture.txt",
        "bytes": 7,
        "sha256": "fixture-hash",
    }


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


def test_launch_agent_unlinks_prompt_when_subprocess_popen_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "00000000-0000-4000-8000-000000000002"
    launch_id = "deadbeefdeadbeefdeadbeefdeadbeef"
    runner = tmp_path / "runner"
    runner.write_text("#!/bin/sh\nexit 0\n")
    # Deliberately not executable: agent_runner.is_file() still passes the
    # pre-flight check, but subprocess.Popen raises a real PermissionError
    # (a subclass of OSError) when it tries to exec this file -- no mocking
    # of Popen itself, just an OS-enforced launch failure.
    runner.chmod(0o600)
    cfg = dataclasses.replace(config(tmp_path), agent_runner=runner)
    runtime = Runtime.create(cfg, "agent-control")
    monkeypatch.setattr("sinnix_agent_gateway.jobs.uuid.uuid4", lambda: job_id)
    monkeypatch.setattr("sinnix_agent_gateway.jobs.secrets.token_hex", lambda _n: launch_id)

    prompt_path = runtime.jobs.root / f"{job_id}.{launch_id}.prompt.md"
    with pytest.raises(JobError, match="failed to launch attested agent job"):
        runtime.jobs.launch_agent(
            AgentLaunchRequest(
                project_id="fixture", prompt="secret prompt body", backend="codex"
            )
        )

    assert not prompt_path.exists()
    leftover = list(runtime.jobs.root.glob(f"{job_id}.*.prompt.md"))
    assert leftover == [], f"prompt file(s) survived a launch failure: {leftover}"
    # An observer-scoped principal must not be able to read a prompt that a
    # failed launch left behind -- verify no readable file remains, not just
    # that the JobService's own handle is gone.
    observer_files = Runtime.create(runtime.config, "observer").files
    with pytest.raises(FileError, match="path does not exist"):
        observer_files.read("read", str(prompt_path))


def test_agent_worktree_authorization_reaches_runner_boundary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
    (project / "tracked.txt").write_text("tracked\n")
    subprocess.run(["git", "-C", str(project), "add", "tracked.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "user.name=Test",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    linked = tmp_path / "linked"
    subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "worktree",
            "add",
            "-q",
            "-b",
            "linked",
            str(linked),
        ],
        check=True,
    )
    capture = tmp_path / "runner-argv.json"
    runner = tmp_path / "runner"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        f"pathlib.Path({str(capture)!r}).write_text(json.dumps(args))\n"
        "values = dict(zip(args[::2], args[1::2]))\n"
        "state = pathlib.Path(values['--job-state-dir'])\n"
        "job = values['--job-id']\n"
        "launch = values['--launch-id']\n"
        "(state / f'{job}.json').write_text(json.dumps({'schema_version': 3, 'job_id': job, 'launch_id': launch}))\n"
    )
    runner.chmod(0o700)
    cfg = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        agent_runner=runner,
    )
    runtime = Runtime.create(cfg, "agent-control")

    result = runtime.jobs.launch_agent(
        AgentLaunchRequest(
            project_id="fixture",
            prompt="prompt",
            backend="codex",
            worktree=str(linked),
        )
    )
    args = json.loads(capture.read_text())
    values = dict(zip(args[::2], args[1::2]))
    assert result["accepted"] is True
    assert values["--workdir"] == str(linked)
    assert values["--registered-project"] == str(project)
    assert Path(values["--expected-git-common-dir"]).resolve() == (project / ".git").resolve()


def test_launch_agent_uses_local_workdir_for_non_git_registered_project(
    tmp_path: Path,
) -> None:
    # A registered project is not required to be a Git checkout (config.py
    # never enforces that). Before this fix, launch_agent unconditionally
    # passed --registered-project plus an *empty* --expected-git-common-dir
    # for such a project -- and the runner's own `${2:?msg}` argument parser
    # treats an empty value the same as a missing one, so every launch
    # against a non-Git registered project crashed at argument-parsing time,
    # before any of the runner's own validation logic ran (reproduced
    # directly against the runner script; not exercised here since this test
    # captures argv with a fixture runner rather than invoking the real one).
    # _authorized_agent_worktree guarantees `worktree` cannot differ from
    # the registered project in this case (any other requested worktree
    # fails to validate without a Git common directory to link against), so
    # --local-workdir is the exact non-attested opt-out for that guarantee,
    # not a weakening of it.
    project = tmp_path / "project"
    project.mkdir()  # deliberately not a Git checkout
    capture = tmp_path / "runner-argv.json"
    runner = tmp_path / "runner"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        f"pathlib.Path({str(capture)!r}).write_text(json.dumps(args))\n"
        "values, i = {}, 0\n"
        "while i < len(args):\n"
        "    if args[i] == '--local-workdir':\n"
        "        values['--local-workdir'] = True\n"
        "        i += 1\n"
        "    else:\n"
        "        values[args[i]] = args[i + 1]\n"
        "        i += 2\n"
        "state = pathlib.Path(values['--job-state-dir'])\n"
        "job = values['--job-id']\n"
        "launch = values['--launch-id']\n"
        "(state / f'{job}.json').write_text(json.dumps({'schema_version': 3, 'job_id': job, 'launch_id': launch}))\n"
    )
    runner.chmod(0o700)
    cfg = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        agent_runner=runner,
    )
    runtime = Runtime.create(cfg, "agent-control")

    result = runtime.jobs.launch_agent(
        AgentLaunchRequest(project_id="fixture", prompt="prompt", backend="codex")
    )
    args = json.loads(capture.read_text())
    assert result["accepted"] is True
    assert "--local-workdir" in args
    assert "--registered-project" not in args
    assert "--expected-git-common-dir" not in args
    # The crash-inducing case: an empty string ever reaching argv as a flag
    # value that the runner's `${var:?msg}` parser would reject.
    assert "" not in args


def test_agent_overlay_is_deferred_before_secret_state_is_created(
    tmp_path: Path,
) -> None:
    runtime = Runtime.create(config(tmp_path), "agent-control")
    with pytest.raises(ValidationError, match="deferred"):
        AgentLaunchRequest.model_validate(
            {
                "project_id": "fixture",
                "prompt": "secret prompt",
                "backend": "codex",
                "environment_overlay": {"API_TOKEN": "secret-value"},
            }
        )

    overlay_paths = list(runtime.jobs.root.glob("*.environment.json"))
    assert overlay_paths == []
    observer_files = Runtime.create(runtime.config, "observer").files
    with pytest.raises(FileError, match="path does not exist"):
        observer_files.read("read", str(runtime.jobs.root / "not-created.environment.json"))


def test_agent_overlay_rejects_reserved_identity_variables(tmp_path: Path) -> None:
    runtime = Runtime.create(config(tmp_path), "agent-control")
    with pytest.raises(ValidationError, match="reserved"):
        AgentLaunchRequest.model_validate(
            {
                "project_id": "fixture",
                "prompt": "prompt",
                "backend": "codex",
                "environment_overlay": {"SINNIX_CORRELATION_ID": "spoofed"},
            }
        )
    assert list(runtime.jobs.root.glob("*.environment.json")) == []


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
        f"#!{sys.executable}\nimport json\nprint(json.dumps({report!r}))\n"
    )
    collector.chmod(0o700)
    cfg = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        observe_command=str(collector),
        max_result_bytes=1_024,
    )
    runtime = Runtime.create(cfg, "observer")

    assert runtime.observe.machine_report()["failure_class"] == "response_bound"
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
    report = {
        "schema": "sinnix.observe.v1",
        "generated_at": "2026-08-21T00:00:00Z",
        "window": {},
        "systemd_units": [
            {"unit": f"fixture-{index}.service", "detail": "x" * 700}
            for index in range(3)
        ],
    }
    monkeypatch.setattr(
        runtime.observe,
        "_collect_report",
        lambda: {"available": True, "report": report},
    )

    result = runtime.observe.machine_query("units", limit=3)

    assert len(result["rows"]) == 1
    assert result["next_cursor"] == 1
