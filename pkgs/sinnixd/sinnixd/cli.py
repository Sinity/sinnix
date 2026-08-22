from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from sinnix_mcp import RequestEnvelope

from .api import UnixSocketServer, call
from .projects import ProjectCatalog
from .service import SinnixdService


def default_socket_path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sinnixd.sock"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="agentctl")
    result.add_argument("--socket", type=Path, default=default_socket_path())
    subcommands = result.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    project = subcommands.add_parser("project")
    project_subcommands = project.add_subparsers(dest="project_command", required=True)
    project_subcommands.add_parser("list")
    get = project_subcommands.add_parser("get")
    get.add_argument("project_id")
    operations = project_subcommands.add_parser("operations")
    operations.add_argument("project_id")
    job = subcommands.add_parser("job")
    job_subcommands = job.add_subparsers(dest="job_command", required=True)
    start = job_subcommands.add_parser("start")
    start.add_argument("project_id")
    start.add_argument("operation")
    status = job_subcommands.add_parser("status")
    status.add_argument("job_id")
    cancel = job_subcommands.add_parser("cancel")
    cancel.add_argument("job_id")
    return result


def daemon_parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="sinnixd")
    result.add_argument("--socket", type=Path, default=default_socket_path())
    result.add_argument("--project-root", type=Path, action="append", required=True)
    return result


def _request(operation: str, owner: str, arguments: dict[str, object]) -> RequestEnvelope:
    return RequestEnvelope(
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
        operation=operation,
        owner=owner,
        principal="local-cli",
        arguments=arguments,
    )


def main() -> None:
    arguments = parser().parse_args()
    if arguments.command == "status":
        request = _request("runtime.status", "sinnixd", {})
    elif arguments.command == "project" and arguments.project_command == "list":
        request = _request("project.list", "project-adapters", {})
    elif arguments.command == "project" and arguments.project_command == "get":
        request = _request("project.get", "project-adapters", {"project_id": arguments.project_id})
    elif arguments.command == "project":
        request = _request(
            "project.operations", "project-adapters", {"project_id": arguments.project_id}
        )
    elif arguments.job_command == "start":
        request = _request(
            "job.start",
            "systemd-jobs",
            {"project_id": arguments.project_id, "operation": arguments.operation},
        )
    elif arguments.job_command == "status":
        request = _request("job.status", "systemd-jobs", {"job_id": arguments.job_id})
    else:
        request = _request("job.cancel", "systemd-jobs", {"job_id": arguments.job_id})
    print(json.dumps(call(arguments.socket, request), indent=2, sort_keys=True))


def daemon_main() -> None:
    arguments = daemon_parser().parse_args()
    service = SinnixdService(ProjectCatalog(arguments.project_root))
    UnixSocketServer(arguments.socket, service).serve_forever()
