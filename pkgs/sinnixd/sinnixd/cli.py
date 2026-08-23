from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from sinnix_mcp import RequestEnvelope

from .api import UnixSocketServer, call
from .jobs import GenericJobStore, GenericJobs, UserSystemdJobs, default_state_dir
from .projects import ProjectCatalog
from .service import SinnixdService


def default_socket_path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sinnixd.sock"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="agentctl")
    result.add_argument("--socket", type=Path, default=default_socket_path())
    subcommands = result.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    shell = subcommands.add_parser("shell")
    shell.add_argument("--project", required=True)
    shell.add_argument("--checkout", required=True)
    shell.add_argument("--cwd", default=".")
    shell.add_argument("--timeout-seconds", type=int, default=3_600)
    shell.add_argument("argv", nargs=argparse.REMAINDER)
    agent = subcommands.add_parser("agent")
    agent.add_argument("--project", required=True)
    agent.add_argument("--checkout", required=True)
    agent.add_argument("--prompt-file", type=Path, required=True)
    agent.add_argument("--backend", required=True)
    agent.add_argument("--model", required=True)
    agent.add_argument("--effort", required=True)
    agent.add_argument("--credential-profile", default="subscription")
    agent.add_argument("--timeout-seconds", type=int, default=3_600)
    project = subcommands.add_parser("project")
    project_subcommands = project.add_subparsers(dest="project_command", required=True)
    project_subcommands.add_parser("list")
    get = project_subcommands.add_parser("get")
    get.add_argument("project_id")
    operations = project_subcommands.add_parser("operations")
    operations.add_argument("project_id")
    workspace = subcommands.add_parser("workspace")
    workspace_subcommands = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_list = workspace_subcommands.add_parser("list")
    workspace_list.add_argument("--project")
    workspace_get = workspace_subcommands.add_parser("get")
    workspace_get.add_argument("workspace_id")
    workspace_create = workspace_subcommands.add_parser("create")
    workspace_create.add_argument("project_id")
    workspace_create.add_argument("name")
    workspace_create.add_argument("--branch", required=True)
    workspace_create.add_argument("--base")
    workspace_adopt = workspace_subcommands.add_parser("adopt")
    workspace_adopt.add_argument("project_id")
    workspace_adopt.add_argument("checkout_id")
    workspace_adopt.add_argument("name")
    workspace_reap = workspace_subcommands.add_parser("reap")
    workspace_reap.add_argument("workspace_id")
    workspace_checkpoint = workspace_subcommands.add_parser("checkpoint")
    workspace_checkpoint.add_argument("workspace_id")
    workspace_restore = workspace_subcommands.add_parser("restore")
    workspace_restore.add_argument("workspace_id")
    workspace_restore.add_argument("checkpoint_id")
    workspace_recover = workspace_subcommands.add_parser("recover")
    workspace_recover.add_argument("workspace_id")
    workspace_recover.add_argument("checkpoint_id")
    workspace_stack = workspace_subcommands.add_parser("stack")
    workspace_stack.add_argument("parent_workspace_id")
    workspace_stack.add_argument("name")
    workspace_stack.add_argument("--branch", required=True)
    workspace_restack = workspace_subcommands.add_parser("restack")
    workspace_restack.add_argument("workspace_id")
    workspace_publish = workspace_subcommands.add_parser("publish")
    workspace_publish.add_argument("workspace_id")
    workspace_publish.add_argument("--job", required=True)
    workspace_publish.add_argument("--title", required=True)
    workspace_publish.add_argument("--body", default="")
    workspace_review = workspace_subcommands.add_parser("review-status")
    workspace_review.add_argument("workspace_id")
    workspace_land = workspace_subcommands.add_parser("land")
    workspace_land.add_argument("workspace_id")
    workspace_land.add_argument("--job", required=True)
    workspace_finish = workspace_subcommands.add_parser("finish")
    workspace_finish.add_argument("workspace_id")
    job = subcommands.add_parser("job")
    job_subcommands = job.add_subparsers(dest="job_command", required=True)
    start = job_subcommands.add_parser("start")
    start.add_argument("project_id")
    start.add_argument("operation")
    start.add_argument("--workspace")
    get = job_subcommands.add_parser("get")
    get.add_argument("job_id")
    job_subcommands.add_parser("list")
    wait = job_subcommands.add_parser("wait")
    wait.add_argument("job_id")
    wait.add_argument("--timeout-seconds", type=int, default=30)
    logs = job_subcommands.add_parser("logs")
    logs.add_argument("job_id")
    logs.add_argument("--offset", type=int, default=0)
    logs.add_argument("--max-bytes", type=int, default=64_000)
    job_result = job_subcommands.add_parser("result")
    job_result.add_argument("job_id")
    job_result.add_argument("--max-bytes", type=int, default=64_000)
    cancel = job_subcommands.add_parser("cancel")
    cancel.add_argument("job_id")
    owner = subcommands.add_parser("owner")
    owner_subcommands = owner.add_subparsers(dest="owner_command", required=True)
    call_owner = owner_subcommands.add_parser("call")
    call_owner.add_argument("owner")
    call_owner.add_argument("operation")
    call_owner.add_argument("--arguments-json", default="{}")
    task = subcommands.add_parser("task")
    task_subcommands = task.add_subparsers(dest="task_command", required=True)
    task_list = task_subcommands.add_parser("list")
    task_list.add_argument("project_id")
    task_list.add_argument("--status")
    task_list.add_argument("--assignee")
    task_list.add_argument("--label")
    task_list.add_argument("--limit", type=int, default=100)
    task_list.add_argument("--include-closed", action="store_true")
    task_list.add_argument("--ready", action="store_true")
    task_get = task_subcommands.add_parser("get")
    task_get.add_argument("project_id")
    task_get.add_argument("task_id")
    for command in ("claim", "complete", "release"):
        command_parser = task_subcommands.add_parser(command)
        command_parser.add_argument("project_id")
        command_parser.add_argument("task_id")
        command_parser.add_argument("--request-id", required=True)
        if command in {"complete", "release"}:
            command_parser.add_argument("--reason")
        if command == "release":
            command_parser.add_argument("--if-assignee")
    task_note = task_subcommands.add_parser("note")
    task_note.add_argument("project_id")
    task_note.add_argument("task_id")
    task_note.add_argument("text")
    task_note.add_argument("--request-id", required=True)
    task_relate = task_subcommands.add_parser("relate")
    task_relate.add_argument("project_id")
    task_relate.add_argument("task_id")
    task_relate.add_argument("related_task_id")
    task_relate.add_argument("--request-id", required=True)
    for command in ("reconcile", "snapshot"):
        command_parser = task_subcommands.add_parser(command)
        command_parser.add_argument("project_id")
    return result


def daemon_parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="sinnixd")
    result.add_argument("--socket", type=Path, default=default_socket_path())
    result.add_argument("--state-dir", type=Path, default=default_state_dir())
    result.add_argument("--project-root", type=Path, action="append", required=True)
    result.add_argument("--native-runner", type=Path, required=True)
    return result


def _request(
    operation: str,
    owner: str,
    arguments: dict[str, object],
    principal: str = "local-cli",
    *,
    idempotency_key: str | None = None,
) -> RequestEnvelope:
    return RequestEnvelope(
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
        operation=operation,
        owner=owner,
        principal=principal,
        arguments=arguments,
        idempotency_key=idempotency_key,
    )


def main() -> int:
    arguments = parser().parse_args()
    if arguments.command == "status":
        request = _request("runtime.status", "sinnixd", {})
    elif arguments.command == "shell":
        shell_argv = arguments.argv[1:] if arguments.argv and arguments.argv[0] == "--" else arguments.argv
        if not shell_argv:
            parser().error("shell requires a command after --")
        request = _request(
            "job.shell.start",
            "systemd-jobs",
            {
                "project_id": arguments.project,
                "checkout_id": arguments.checkout,
                "argv": shell_argv,
                "cwd": arguments.cwd,
                "timeout_seconds": arguments.timeout_seconds,
                "result": "exit-status",
            },
            "operator",
        )
    elif arguments.command == "agent":
        try:
            prompt = arguments.prompt_file.read_text()
        except OSError as error:
            parser().error(f"could not read --prompt-file: {error}")
        if not prompt or len(prompt.encode()) > 200_000:
            parser().error("--prompt-file must contain at most 200000 non-empty bytes")
        request = _request(
            "job.agent.start",
            "systemd-jobs",
            {
                "project_id": arguments.project,
                "checkout_id": arguments.checkout,
                "prompt": prompt,
                "backend": arguments.backend,
                "model": arguments.model,
                "effort": arguments.effort,
                "credential_profile": arguments.credential_profile,
                "timeout_seconds": arguments.timeout_seconds,
                "result": "last-message",
            },
            "agent-control",
        )
    elif arguments.command == "project" and arguments.project_command == "list":
        request = _request("project.list", "project-adapters", {})
    elif arguments.command == "project" and arguments.project_command == "get":
        request = _request("project.get", "project-adapters", {"project_id": arguments.project_id})
    elif arguments.command == "project":
        request = _request(
            "project.operations", "project-adapters", {"project_id": arguments.project_id}
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "list":
        payload = {"project_id": arguments.project} if arguments.project else {}
        request = _request("workspace.list", "git-workspaces", payload)
    elif arguments.command == "workspace" and arguments.workspace_command == "get":
        request = _request("workspace.get", "git-workspaces", {"workspace_id": arguments.workspace_id})
    elif arguments.command == "workspace" and arguments.workspace_command == "create":
        request = _request(
            "workspace.create",
            "git-workspaces",
            {
                "project_id": arguments.project_id,
                "name": arguments.name,
                "branch": arguments.branch,
                "base": arguments.base,
            },
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "adopt":
        request = _request(
            "workspace.adopt",
            "git-workspaces",
            {
                "project_id": arguments.project_id,
                "checkout_id": arguments.checkout_id,
                "name": arguments.name,
            },
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "reap":
        request = _request(
            "workspace.reap",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id},
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "checkpoint":
        request = _request(
            "workspace.checkpoint",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id},
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "restore":
        request = _request(
            "workspace.restore",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id, "checkpoint_id": arguments.checkpoint_id},
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "recover":
        request = _request(
            "workspace.recover", "git-workspaces",
            {"workspace_id": arguments.workspace_id, "checkpoint_id": arguments.checkpoint_id},
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "stack":
        request = _request(
            "workspace.stack",
            "git-workspaces",
            {
                "parent_workspace_id": arguments.parent_workspace_id,
                "name": arguments.name,
                "branch": arguments.branch,
            },
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "restack":
        request = _request(
            "workspace.restack",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id},
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "publish":
        request = _request(
            "workspace.publish", "git-workspaces",
            {"workspace_id": arguments.workspace_id, "job_id": arguments.job, "title": arguments.title, "body": arguments.body},
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "review-status":
        request = _request("workspace.review-status", "git-workspaces", {"workspace_id": arguments.workspace_id})
    elif arguments.command == "workspace" and arguments.workspace_command == "land":
        request = _request(
            "workspace.land", "git-workspaces",
            {"workspace_id": arguments.workspace_id, "job_id": arguments.job}, "agent-control",
        )
    elif arguments.command == "workspace":
        request = _request(
            "workspace.finish", "git-workspaces", {"workspace_id": arguments.workspace_id}, "agent-control"
        )
    elif arguments.command == "job" and arguments.job_command == "start":
        request = _request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": arguments.project_id,
                "operation": arguments.operation,
                "workspace_id": arguments.workspace,
            },
        )
    elif arguments.command == "job" and arguments.job_command == "get":
        request = _request("job.get", "systemd-jobs", {"job_id": arguments.job_id})
    elif arguments.command == "job" and arguments.job_command == "list":
        request = _request("job.list", "systemd-jobs", {})
    elif arguments.command == "job" and arguments.job_command == "wait":
        request = _request(
            "job.wait",
            "systemd-jobs",
            {"job_id": arguments.job_id, "timeout_seconds": arguments.timeout_seconds},
        )
    elif arguments.command == "job" and arguments.job_command == "logs":
        request = _request(
            "job.logs",
            "systemd-jobs",
            {"job_id": arguments.job_id, "offset": arguments.offset, "max_bytes": arguments.max_bytes},
        )
    elif arguments.command == "job" and arguments.job_command == "result":
        request = _request(
            "job.result",
            "systemd-jobs",
            {"job_id": arguments.job_id, "max_bytes": arguments.max_bytes},
        )
    elif arguments.command == "job":
        request = _request("job.cancel", "systemd-jobs", {"job_id": arguments.job_id})
    elif arguments.command == "task":
        task_arguments: dict[str, object] = {"project_id": arguments.project_id}
        if arguments.task_command == "list":
            task_arguments["limit"] = arguments.limit
            for name in ("status", "assignee", "label"):
                value = getattr(arguments, name)
                if value is not None:
                    task_arguments[name] = value
            for name in ("include_closed", "ready"):
                if getattr(arguments, name):
                    task_arguments[name] = True
        elif arguments.task_command in {"get", "claim", "complete", "release", "note", "relate"}:
            task_arguments["task_id"] = arguments.task_id
            if arguments.task_command == "note":
                task_arguments["text"] = arguments.text
            elif arguments.task_command == "relate":
                task_arguments["related_task_id"] = arguments.related_task_id
            elif arguments.task_command in {"complete", "release"}:
                if arguments.reason is not None:
                    task_arguments["reason"] = arguments.reason
                if arguments.task_command == "release" and arguments.if_assignee is not None:
                    task_arguments["if_assignee"] = arguments.if_assignee
        mutation_id = getattr(arguments, "request_id", None)
        request = _request(
            f"task.{arguments.task_command}",
            "task-backend",
            task_arguments,
            "operator",
            idempotency_key=mutation_id,
        )
    else:
        try:
            owner_arguments = json.loads(arguments.arguments_json)
        except json.JSONDecodeError as error:
            parser().error(f"--arguments-json must be valid JSON: {error.msg}")
        if not isinstance(owner_arguments, dict):
            parser().error("--arguments-json must be a JSON object")
        request = _request(arguments.operation, arguments.owner, owner_arguments)
    response = call(arguments.socket, request)
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response.get("ok") is True else 1


def daemon_main() -> None:
    arguments = daemon_parser().parse_args()
    service = SinnixdService(
        ProjectCatalog(arguments.project_root),
        jobs=GenericJobs(UserSystemdJobs(), GenericJobStore(arguments.state_dir)),
        native_runner=arguments.native_runner,
    )
    UnixSocketServer(arguments.socket, service).serve_forever()
