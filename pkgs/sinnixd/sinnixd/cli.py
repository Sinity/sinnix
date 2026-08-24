from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from sinnix_mcp import ErrorCode, ErrorEnvelope, RequestEnvelope, ResponseEnvelope

from .api import ProtocolError, SinnixdClientError, UnixSocketServer, call
from .jobs import GenericJobStore, GenericJobs, UserSystemdJobs, default_state_dir
from .limits import DEFAULT_TIMEOUT_SECONDS
from .projects import ProjectCatalog
from .service import SinnixdService


def _dependency_argument(value: str) -> tuple[str, str]:
    relation, separator, task_id = value.partition(":")
    if not separator or not relation or not task_id:
        raise argparse.ArgumentTypeError("--dependency must be relation:task-id")
    return relation, task_id


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
    shell.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    shell.add_argument("argv", nargs=argparse.REMAINDER)
    agent = subcommands.add_parser("agent")
    agent.add_argument("--project", required=True)
    agent.add_argument("--checkout", required=True)
    agent.add_argument("--prompt-file", type=Path, required=True)
    agent.add_argument("--backend", required=True)
    agent.add_argument("--model", required=True)
    agent.add_argument("--effort", required=True)
    agent.add_argument("--credential-profile", default="subscription")
    agent.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
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
    workspace_dispose = workspace_subcommands.add_parser("dispose")
    workspace_dispose.add_argument("workspace_id")
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
    workspace_finish_integrated = workspace_subcommands.add_parser("finish-integrated")
    workspace_finish_integrated.add_argument("workspace_id")
    workspace_finish_integrated.add_argument("--target", required=True)
    job = subcommands.add_parser("job")
    job_subcommands = job.add_subparsers(dest="job_command", required=True)
    start = job_subcommands.add_parser("start")
    start.add_argument("project_id")
    start.add_argument("operation")
    start.add_argument("--workspace")
    start.add_argument("--parameters-json", default="{}")
    get = job_subcommands.add_parser("get")
    get.add_argument("job_id")
    status = job_subcommands.add_parser("status")
    status.add_argument("job_id")
    status.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON (accepted explicitly for scripting; JSON is the default output format).",
    )
    job_list = job_subcommands.add_parser("list")
    job_list.add_argument("--limit", type=int, choices=range(1, 1001), default=100)
    job_list.add_argument("--cursor")
    job_list.add_argument("--project")
    job_list.add_argument("--phase", action="append", default=[])
    job_list.add_argument("--active", action="store_true")
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
    task_list.add_argument("--cursor")
    task_list.add_argument("--sort", choices=("priority", "created", "updated", "closed", "status", "id", "title", "type", "assignee"))
    task_list.add_argument("--reverse", action="store_true")
    task_list.add_argument("--include-closed", action="store_true")
    task_list.add_argument("--ready", action="store_true")
    task_get = task_subcommands.add_parser("get")
    task_get.add_argument("project_id")
    task_get.add_argument("task_id")
    task_create = task_subcommands.add_parser("create")
    task_create.add_argument("project_id")
    task_create.add_argument("title")
    task_create.add_argument("--description", required=True)
    task_create.add_argument("--type", dest="issue_type", choices=("bug", "feature", "task", "epic", "chore", "decision", "spike", "story", "milestone"), required=True)
    task_create.add_argument("--priority", type=int, choices=range(5), required=True)
    task_create.add_argument("--label", action="append", default=[])
    task_create.add_argument("--parent")
    task_create.add_argument("--dependency", action="append", type=_dependency_argument, default=[])
    task_create.add_argument("--request-id", required=True)
    for command in ("claim", "complete", "release"):
        command_parser = task_subcommands.add_parser(command)
        command_parser.add_argument("project_id")
        command_parser.add_argument("task_id")
        command_parser.add_argument("--request-id", required=True)
        if command in {"complete", "release"}:
            command_parser.add_argument("--reason")
        if command == "complete":
            command_parser.add_argument("--merge-sha", required=True)
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
    principal: str = "operator",
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


def _unavailable_response(request: RequestEnvelope) -> dict[str, object]:
    return ResponseEnvelope(
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        owner=request.owner,
        error=ErrorEnvelope(ErrorCode.OWNER_UNAVAILABLE, "sinnixd is unavailable"),
    ).to_dict()


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
    elif arguments.command == "workspace" and arguments.workspace_command == "dispose":
        request = _request(
            "workspace.dispose",
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
    elif arguments.command == "workspace" and arguments.workspace_command == "finish-integrated":
        request = _request(
            "workspace.finish-integrated",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id, "target_ref": arguments.target},
            "agent-control",
        )
    elif arguments.command == "workspace":
        request = _request(
            "workspace.finish", "git-workspaces", {"workspace_id": arguments.workspace_id}, "agent-control"
        )
    elif arguments.command == "job" and arguments.job_command == "start":
        try:
            parameters = json.loads(arguments.parameters_json)
        except json.JSONDecodeError as error:
            parser().error(f"--parameters-json must be valid JSON: {error.msg}")
        if not isinstance(parameters, dict):
            parser().error("--parameters-json must be a JSON object")
        request = _request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": arguments.project_id,
                "operation": arguments.operation,
                "workspace_id": arguments.workspace,
                "parameters": parameters,
            },
        )
    elif arguments.command == "job" and arguments.job_command in {"get", "status"}:
        request = _request("job.get", "systemd-jobs", {"job_id": arguments.job_id})
    elif arguments.command == "job" and arguments.job_command == "list":
        request = _request(
            "job.list",
            "systemd-jobs",
            {
                "limit": arguments.limit,
                "cursor": arguments.cursor,
                "project_id": arguments.project,
                "phases": arguments.phase,
                "active_only": arguments.active,
            },
        )
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
            if arguments.cursor is not None:
                task_arguments["cursor"] = arguments.cursor
            for name in ("status", "assignee", "label"):
                value = getattr(arguments, name)
                if value is not None:
                    task_arguments[name] = value
            if arguments.sort is not None:
                task_arguments["order"] = {"field": arguments.sort, "reverse": arguments.reverse}
            elif arguments.reverse:
                parser().error("--reverse requires --sort")
            for name in ("include_closed", "ready"):
                if getattr(arguments, name):
                    task_arguments[name] = True
        elif arguments.task_command == "create":
            task_arguments.update(
                {
                    "title": arguments.title,
                    "description": arguments.description,
                    "issue_type": arguments.issue_type,
                    "priority": arguments.priority,
                    "labels": arguments.label,
                    "dependencies": [
                        {"relation": relation, "task_id": task_id}
                        for relation, task_id in arguments.dependency
                    ],
                }
            )
            if arguments.parent is not None:
                task_arguments["parent_task_id"] = arguments.parent
        elif arguments.task_command in {"get", "claim", "complete", "release", "note", "relate"}:
            task_arguments["task_id"] = arguments.task_id
            if arguments.task_command == "note":
                task_arguments["text"] = arguments.text
            elif arguments.task_command == "relate":
                task_arguments["related_task_id"] = arguments.related_task_id
            elif arguments.task_command in {"complete", "release"}:
                if arguments.reason is not None:
                    task_arguments["reason"] = arguments.reason
                if arguments.task_command == "complete":
                    task_arguments["merge_sha"] = arguments.merge_sha
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
    try:
        response = call(arguments.socket, request)
    except (OSError, ProtocolError, SinnixdClientError):
        response = _unavailable_response(request)
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
