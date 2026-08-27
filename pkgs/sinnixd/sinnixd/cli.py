from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from sinnix_mcp import ErrorCode, ErrorEnvelope, RequestEnvelope, ResponseEnvelope

from .api import ProtocolError, SinnixdClientError, UnixSocketServer, call
from .fleet import (
    DEFAULT_FLEET_LIMIT,
    DEFAULT_GH_LIMIT,
    DEFAULT_RECENT_HOURS,
    read_evidence,
    read_fleet,
    render_evidence,
    render_fleet,
)
from .jobs import GenericJobs, GenericJobStore, UserSystemdJobs, default_state_dir
from .limits import DEFAULT_TIMEOUT_SECONDS
from .packets import (
    PacketConfig,
    PacketError,
    SubprocessBdReader,
    checkout_id_from_workspace_response,
    compile_launch_snapshot,
    derived_workspace,
    plan_table,
    project_id_from_descriptor,
    resolve_project_root,
    runtime_dimensions,
)
from .projects import ProjectCatalog
from .service import SinnixdService


def _dependency_argument(value: str) -> tuple[str, str]:
    relation, separator, task_id = value.partition(":")
    if not separator or not relation or not task_id:
        raise argparse.ArgumentTypeError("--dependency must be relation:task-id")
    return relation, task_id


def _metadata_argument(value: str) -> tuple[str, str]:
    key, separator, metadata_value = value.partition("=")
    if not separator or not key:
        raise argparse.ArgumentTypeError("--set-metadata must be key=value")
    return key, metadata_value


def _packet_notes(response: dict[str, object]) -> list[dict[str, object]]:
    payload = response.get("payload")
    value = payload.get("value") if isinstance(payload, dict) else None
    notes = value.get("notes") if isinstance(value, dict) else None
    if not isinstance(notes, list):
        return []
    return [dict(note) for note in notes if isinstance(note, dict)]


def _attach_packet_notes(
    response: dict[str, object], notes: list[dict[str, object]]
) -> dict[str, object]:
    if not notes:
        return response
    payload = response.get("payload")
    value = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or not isinstance(value, dict):
        return response
    return {
        **response,
        "payload": {**payload, "value": {**value, "notes": notes}},
    }


def _packet_step_failure(
    response: dict[str, object],
    step: str,
    *,
    rollback: dict[str, object] | None = None,
) -> dict[str, object]:
    """Identify the failed packet-launch step while retaining its error code."""
    error = response.get("error")
    error_value = dict(error) if isinstance(error, dict) else {}
    message = error_value.get("message")
    detail = message if isinstance(message, str) and message else "operation failed"
    rollback_state = "completed"
    if rollback is not None:
        rollback_state = "completed" if rollback.get("ok") is True else "failed"
    error_value["code"] = error_value.get("code", "OPERATION_FAILED")
    error_value["message"] = (
        f"packet launch step {step} failed ({rollback_state} rollback): {detail}"
    )
    return {**response, "ok": False, "error": error_value}


def _add_agent_launch_arguments(
    target: argparse.ArgumentParser, *, required: bool
) -> None:
    target.add_argument("--project", required=required)
    target.add_argument("--checkout", required=required)
    target.add_argument("--prompt-file", type=Path, required=required)
    target.add_argument("--backend", required=required)
    target.add_argument("--model", required=required)
    target.add_argument("--effort", required=required)
    target.add_argument("--credential-profile", default="subscription")
    target.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    target.add_argument("--dimensions-json", default="{}")
    target.add_argument(
        "--coordinator-label",
        "--coordinator",
        "--campaign-label",
        dest="coordinator_label",
        help="Optional campaign/coordinator label copied to terminal events.",
    )
    target.add_argument(
        "--bypass-admission",
        action="store_true",
        help="Start immediately for an emergency, bypassing agent admission.",
    )


def default_socket_path() -> Path:
    return (
        Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        / "sinnixd.sock"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="agentctl")
    result.add_argument("--socket", type=Path, default=default_socket_path())
    result.add_argument(
        "--plain",
        action="store_true",
        help="Print the payload value as text instead of the response envelope.",
    )
    subcommands = result.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    fleet = subcommands.add_parser(
        "fleet", help="Show active, queued, and recent jobs with best-effort joins."
    )
    fleet.add_argument("--state-dir", type=Path, default=default_state_dir())
    fleet.add_argument(
        "--limit", type=int, choices=range(1, 201), default=DEFAULT_FLEET_LIMIT
    )
    fleet.add_argument("--recent-hours", type=float, default=DEFAULT_RECENT_HOURS)
    fleet.add_argument(
        "--gh-limit", type=int, choices=range(0, 33), default=DEFAULT_GH_LIMIT
    )
    fleet.add_argument("--json", action="store_true")
    evidence = subcommands.add_parser(
        "evidence", help="Show all locally available evidence for one job or workspace."
    )
    evidence.add_argument("unit_id", metavar="job-id|workspace-id")
    evidence.add_argument("--state-dir", type=Path, default=default_state_dir())
    evidence.add_argument("--gh-limit", type=int, choices=range(0, 2), default=1)
    evidence.add_argument("--json", action="store_true")
    shell = subcommands.add_parser("shell")
    shell.add_argument("--project", required=True)
    shell.add_argument("--checkout", required=True)
    shell.add_argument("--cwd", default=".")
    shell.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    shell.add_argument("argv", nargs=argparse.REMAINDER)
    agent = subcommands.add_parser("agent")
    _add_agent_launch_arguments(agent, required=False)
    agent_subcommands = agent.add_subparsers(dest="agent_command", required=False)
    launch = agent_subcommands.add_parser(
        "launch", help="Dispatch an attested agent job (same as bare `agent`)."
    )
    _add_agent_launch_arguments(launch, required=True)
    agent_list = agent_subcommands.add_parser("list")
    agent_list.add_argument("--limit", type=int, choices=range(1, 1001), default=100)
    agent_list.add_argument("--cursor")
    agent_list.add_argument("--project")
    agent_list.add_argument("--phase", action="append", default=[])
    agent_list.add_argument("--active", action="store_true")
    agent_status = agent_subcommands.add_parser("status")
    agent_status.add_argument("job_id")
    agent_wait = agent_subcommands.add_parser("wait")
    agent_wait.add_argument("job_ids", nargs="+", metavar="job_id")
    agent_wait.add_argument("--any", dest="wait_any", action="store_true")
    agent_wait.add_argument("--timeout-seconds", type=int, default=30)
    agent_result = agent_subcommands.add_parser("result")
    agent_result.add_argument("job_id")
    agent_result.add_argument("--max-bytes", type=int, default=64_000)
    project = subcommands.add_parser("project")
    project_subcommands = project.add_subparsers(dest="project_command", required=True)
    project_subcommands.add_parser("list")
    get = project_subcommands.add_parser("get")
    get.add_argument("project_id")
    operations = project_subcommands.add_parser("operations")
    operations.add_argument("project_id")
    workspace = subcommands.add_parser("workspace")
    workspace_subcommands = workspace.add_subparsers(
        dest="workspace_command", required=True
    )
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
    workspace_dispose.add_argument("--acknowledge-published", action="store_true")
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
    workspace_publish.add_argument("--packet-job")
    workspace_publish.add_argument("--title", required=True)
    workspace_publish.add_argument("--body", default="")
    workspace_publish.add_argument(
        "--wait",
        action="store_true",
        help="Block on the delivery job and print its receipt instead of the job id.",
    )
    workspace_review = workspace_subcommands.add_parser("review-status")
    workspace_review.add_argument("workspace_id")
    workspace_land = workspace_subcommands.add_parser("land")
    workspace_land.add_argument("workspace_id")
    workspace_land.add_argument("--job", required=True)
    workspace_land.add_argument("--packet-job")
    workspace_land.add_argument(
        "--wait",
        action="store_true",
        help="Block on the delivery job and print its receipt instead of the job id.",
    )
    workspace_finish = workspace_subcommands.add_parser("finish")
    workspace_finish.add_argument("workspace_id")
    workspace_finish_integrated = workspace_subcommands.add_parser("finish-integrated")
    workspace_finish_integrated.add_argument("workspace_id")
    workspace_finish_integrated.add_argument("--target", required=True)
    packet = subcommands.add_parser("packet")
    packet_subcommands = packet.add_subparsers(dest="packet_command", required=True)
    packet_finalize = packet_subcommands.add_parser("finalize")
    packet_finalize.add_argument("workspace_id")
    packet_finalize.add_argument("--verification-job", required=True)
    packet_finalize.add_argument("--packet-job", required=True)
    packet_status = packet_subcommands.add_parser("status")
    packet_status.add_argument("saga_id")
    packet_launch = packet_subcommands.add_parser(
        "launch", help="Compile a bead dispatch group and launch one agent lane."
    )
    packet_launch.add_argument("bead_id")
    packet_launch.add_argument("--project")
    packet_launch.add_argument("--plan", action="store_true")
    packet_launch.add_argument("--credential-profile", default="subscription")
    packet_launch.add_argument(
        "--coordinator-label",
        "--coordinator",
        "--campaign-label",
        dest="coordinator_label",
        help="Optional campaign/coordinator label copied to terminal events.",
    )
    packet_launch.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS
    )
    campaign = subcommands.add_parser(
        "campaign", help="Schedule a ready-Beads packet campaign wave."
    )
    campaign_subcommands = campaign.add_subparsers(
        dest="campaign_command", required=True
    )
    campaign_run = campaign_subcommands.add_parser("run")
    campaign_run.add_argument("--project", required=True)
    campaign_run.add_argument("--limit", type=int)
    campaign_run.add_argument("--bead", dest="bead_ids", action="append")
    campaign_run.add_argument("--dry-run", action="store_true")
    job = subcommands.add_parser("job")
    job_subcommands = job.add_subparsers(dest="job_command", required=True)
    start = job_subcommands.add_parser("start")
    start.add_argument("project_id")
    start.add_argument("operation")
    start.add_argument(
        "--workspace",
        "--checkout",
        dest="workspace",
        help="Managed workspace ID (the --checkout spelling is an equivalent convenience alias).",
    )
    start.add_argument("--parameters-json", default="{}")
    start.add_argument("--bead-binding-json")
    start.add_argument("--dimensions-json", default="{}")
    fire = job_subcommands.add_parser(
        "fire", help="Fire one daemon-registered scheduled operation."
    )
    fire.add_argument("project_id")
    fire.add_argument("operation")
    fire.add_argument("--schedule-id", required=True)
    get = job_subcommands.add_parser("get")
    get.add_argument("job_id")
    retry = job_subcommands.add_parser("retry")
    retry.add_argument("job_id")
    retry.add_argument("--hint")
    retry.add_argument("--escalate", action="store_true")
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
    job_list.add_argument("--kind", action="append", default=[])
    job_list.add_argument(
        "--active", "--active-only", dest="active", action="store_true"
    )
    wait = job_subcommands.add_parser("wait")
    wait.add_argument("job_ids", nargs="+", metavar="job_id")
    wait.add_argument(
        "--any",
        dest="wait_any",
        action="store_true",
        help="With multiple job ids, return when the first reaches a terminal state.",
    )
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
    plan = subcommands.add_parser("plan")
    plan_subcommands = plan.add_subparsers(dest="plan_command", required=True)
    plan_submit = plan_subcommands.add_parser("submit")
    plan_submit.add_argument("project_id")
    plan_submit.add_argument("--input-generation", required=True)
    plan_submit.add_argument("--node-operation")
    plan_submit.add_argument("--workspace")
    plan_submit.add_argument("--checkout")
    plan_submit.add_argument("--plan-file", type=Path, required=True)
    plan_get = plan_subcommands.add_parser("get")
    plan_get.add_argument("plan_id")
    plan_list = plan_subcommands.add_parser("list")
    plan_list.add_argument("--project")
    plan_wait = plan_subcommands.add_parser("wait")
    plan_wait.add_argument("plan_id")
    plan_wait.add_argument("--timeout-seconds", type=int, default=30)
    plan_result = plan_subcommands.add_parser("result")
    plan_result.add_argument("plan_id")
    plan_result.add_argument("--max-bytes", type=int, default=64_000)
    owner = subcommands.add_parser("owner")
    owner_subcommands = owner.add_subparsers(dest="owner_command", required=True)
    call_owner = owner_subcommands.add_parser("call")
    call_owner.add_argument("owner")
    call_owner.add_argument("operation")
    call_owner.add_argument("--arguments-json", default="{}")
    task = subcommands.add_parser("task")
    task_subcommands = task.add_subparsers(dest="task_command", required=True)
    # task list/get were deliberately removed: read task state through the
    # task backend CLI (bd) directly; agentctl owns only journalled mutations,
    # reconcile, and the authority-bound snapshot.
    task_create = task_subcommands.add_parser("create")
    task_create.add_argument("project_id")
    task_create.add_argument("title")
    task_create.add_argument("--description", required=True)
    task_create.add_argument(
        "--type",
        dest="issue_type",
        choices=(
            "bug",
            "feature",
            "task",
            "epic",
            "chore",
            "decision",
            "spike",
            "story",
            "milestone",
        ),
        required=True,
    )
    task_create.add_argument("--priority", type=int, choices=range(5), required=True)
    task_create.add_argument("--label", action="append", default=[])
    task_create.add_argument("--parent")
    task_create.add_argument(
        "--dependency", action="append", type=_dependency_argument, default=[]
    )
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
    task_note.add_argument("text", nargs="?")
    task_note.add_argument("--text", dest="text_option")
    task_note.add_argument("--request-id", required=True)
    task_update = task_subcommands.add_parser("update")
    task_update.add_argument("project_id")
    task_update.add_argument("task_id")
    task_update.add_argument(
        "--set-metadata",
        action="append",
        type=_metadata_argument,
        default=[],
        required=True,
    )
    task_update.add_argument("--request-id", required=True)
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
    result.add_argument(
        "--event-spool",
        type=Path,
        default=Path("/realm/state/agentctl/events.jsonl"),
        help="Append-only JSONL of terminal job events (the zero-polling watch point).",
    )
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


_JOB_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


def _expand_job_id(value: str) -> str:
    """Accept the abbreviated job ids that fleet output and events print."""
    if _JOB_ID_RE.fullmatch(value) or len(value) < 4:
        return value
    matches = sorted(
        path.stem
        for path in (default_state_dir() / "jobs").glob(f"{value}*.json")
        if _JOB_ID_RE.fullmatch(path.stem)
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        parser().error(f"job id prefix {value!r} matches {len(matches)} jobs")
    return value


def _render_plain(response: Mapping[str, Any]) -> str:
    """The payload value as text, for callers that want the answer not the envelope."""
    if response.get("ok") is not True:
        error = response.get("error")
        message = error.get("message") if isinstance(error, Mapping) else None
        return f"ERROR: {message or 'request failed'}"
    payload = response.get("payload")
    value = payload.get("value") if isinstance(payload, Mapping) else payload
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping) and isinstance(value.get("content"), str):
        return value["content"]
    return json.dumps(value, indent=1, sort_keys=True)


def main() -> int:
    arguments = parser().parse_args()
    if isinstance(getattr(arguments, "job_id", None), str):
        arguments.job_id = _expand_job_id(arguments.job_id)
    if isinstance(getattr(arguments, "job_ids", None), list):
        arguments.job_ids = [_expand_job_id(item) for item in arguments.job_ids]
    for option in ("job", "packet_job", "verification_job"):
        if isinstance(getattr(arguments, option, None), str):
            setattr(arguments, option, _expand_job_id(getattr(arguments, option)))
    if arguments.command == "fleet":
        payload = read_fleet(
            GenericJobStore(arguments.state_dir),
            limit=arguments.limit,
            recent_hours=arguments.recent_hours,
            gh_limit=arguments.gh_limit,
        )
        print(
            json.dumps(payload, indent=2, sort_keys=True)
            if arguments.json
            else render_fleet(payload)
        )
        return 0
    if arguments.command == "evidence":
        payload = read_evidence(
            GenericJobStore(arguments.state_dir),
            arguments.unit_id,
            gh_limit=arguments.gh_limit,
        )
        print(
            json.dumps(payload, indent=2, sort_keys=True)
            if arguments.json
            else render_evidence(payload)
        )
        return 0 if payload["unit_kind"] != "absent" else 1
    if arguments.command == "status":
        request = _request("runtime.status", "sinnixd", {})
    elif arguments.command == "shell":
        shell_argv = (
            arguments.argv[1:]
            if arguments.argv and arguments.argv[0] == "--"
            else arguments.argv
        )
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
    elif arguments.command == "agent" and arguments.agent_command == "list":
        request = _request(
            "job.list",
            "systemd-jobs",
            {
                "limit": arguments.limit,
                "cursor": arguments.cursor,
                "project_id": arguments.project,
                "phases": arguments.phase,
                "kinds": ["attested-agent"],
                "active_only": arguments.active,
            },
        )
    elif arguments.command == "agent" and arguments.agent_command == "status":
        request = _request("job.get", "systemd-jobs", {"job_id": arguments.job_id})
    elif arguments.command == "agent" and arguments.agent_command == "wait":
        if len(arguments.job_ids) > 1 and not arguments.wait_any:
            parser().error("waiting on multiple job ids requires --any")
        request = _request(
            "job.wait",
            "systemd-jobs",
            {
                **(
                    {"job_ids": arguments.job_ids}
                    if arguments.wait_any
                    else {"job_id": arguments.job_ids[0]}
                ),
                "timeout_seconds": arguments.timeout_seconds,
            },
        )
    elif arguments.command == "agent" and arguments.agent_command == "result":
        request = _request(
            "job.result",
            "systemd-jobs",
            {"job_id": arguments.job_id, "max_bytes": arguments.max_bytes},
        )
    elif arguments.command == "agent":
        missing = [
            f"--{name.replace('_', '-')}"
            for name in (
                "project",
                "checkout",
                "prompt_file",
                "backend",
                "model",
                "effort",
            )
            if getattr(arguments, name) is None
        ]
        if missing:
            parser().error(
                "agent dispatch requires "
                + ", ".join(missing)
                + " (or use: agent launch|list|status|wait|result)"
            )
        try:
            prompt = arguments.prompt_file.read_text()
        except OSError as error:
            parser().error(f"could not read --prompt-file: {error}")
        if not prompt or len(prompt.encode()) > 200_000:
            parser().error("--prompt-file must contain at most 200000 non-empty bytes")
        try:
            dimensions = json.loads(arguments.dimensions_json)
        except json.JSONDecodeError as error:
            parser().error(f"--dimensions-json must be valid JSON: {error.msg}")
        if not isinstance(dimensions, dict):
            parser().error("--dimensions-json must be a JSON object")
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
                "admission_bypass": arguments.bypass_admission,
                **(
                    {"coordinator_label": arguments.coordinator_label}
                    if arguments.coordinator_label is not None
                    else {}
                ),
                **({"dimensions": dimensions} if dimensions else {}),
            },
            "agent-control",
        )
    elif arguments.command == "project" and arguments.project_command == "list":
        request = _request("project.list", "project-adapters", {})
    elif arguments.command == "project" and arguments.project_command == "get":
        request = _request(
            "project.get", "project-adapters", {"project_id": arguments.project_id}
        )
    elif arguments.command == "project":
        request = _request(
            "project.operations",
            "project-adapters",
            {"project_id": arguments.project_id},
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "list":
        payload = {"project_id": arguments.project} if arguments.project else {}
        request = _request("workspace.list", "git-workspaces", payload)
    elif arguments.command == "workspace" and arguments.workspace_command == "get":
        request = _request(
            "workspace.get", "git-workspaces", {"workspace_id": arguments.workspace_id}
        )
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
        payload = {"workspace_id": arguments.workspace_id}
        if arguments.acknowledge_published:
            payload["acknowledge_published"] = True
        request = _request(
            "workspace.dispose",
            "git-workspaces",
            payload,
            "agent-control",
        )
    elif (
        arguments.command == "workspace" and arguments.workspace_command == "checkpoint"
    ):
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
            {
                "workspace_id": arguments.workspace_id,
                "checkpoint_id": arguments.checkpoint_id,
            },
            "agent-control",
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "recover":
        request = _request(
            "workspace.recover",
            "git-workspaces",
            {
                "workspace_id": arguments.workspace_id,
                "checkpoint_id": arguments.checkpoint_id,
            },
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
            "workspace.publish",
            "git-workspaces",
            {
                "workspace_id": arguments.workspace_id,
                "job_id": arguments.job,
                "title": arguments.title,
                "body": arguments.body,
                **(
                    {"packet_job_id": arguments.packet_job}
                    if arguments.packet_job
                    else {}
                ),
            },
            "agent-control",
        )
    elif (
        arguments.command == "workspace"
        and arguments.workspace_command == "review-status"
    ):
        request = _request(
            "workspace.review-status",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id},
        )
    elif arguments.command == "workspace" and arguments.workspace_command == "land":
        request = _request(
            "workspace.land",
            "git-workspaces",
            {
                "workspace_id": arguments.workspace_id,
                "job_id": arguments.job,
                **(
                    {"packet_job_id": arguments.packet_job}
                    if arguments.packet_job
                    else {}
                ),
            },
            "agent-control",
        )
    elif (
        arguments.command == "workspace"
        and arguments.workspace_command == "finish-integrated"
    ):
        request = _request(
            "workspace.finish-integrated",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id, "target_ref": arguments.target},
            "agent-control",
        )
    elif arguments.command == "workspace":
        request = _request(
            "workspace.finish",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id},
            "agent-control",
        )
    elif arguments.command == "packet" and arguments.packet_command == "finalize":
        request = _request(
            "packet.finalize",
            "packet-saga",
            {
                "workspace_id": arguments.workspace_id,
                "verification_job_id": arguments.verification_job,
                "packet_job_id": arguments.packet_job,
            },
            "operator",
        )
    elif arguments.command == "packet" and arguments.packet_command == "status":
        request = _request(
            "packet.status",
            "packet-saga",
            {"saga_id": arguments.saga_id},
            "operator",
        )
    elif arguments.command == "campaign" and arguments.campaign_command == "run":
        request = _request(
            "campaign.run",
            "campaign-orchestrator",
            {
                "project_id": arguments.project,
                "limit": arguments.limit,
                "bead_ids": arguments.bead_ids,
                "dry_run": arguments.dry_run,
            },
            "operator",
        )
    elif arguments.command == "packet" and arguments.packet_command == "launch":
        try:
            project_root = resolve_project_root(arguments.project)
            project_id = project_id_from_descriptor(project_root)
            packet_config = PacketConfig.load(project_root)
            snapshot = compile_launch_snapshot(
                arguments.bead_id,
                project_root=project_root,
                project_id=project_id,
                reader=SubprocessBdReader(project_root),
                config=packet_config,
            )
        except PacketError as error:
            parser().error(str(error))
        if arguments.plan:
            print(plan_table(snapshot, packet_config))
            return 0
        workspace_name, branch = derived_workspace(snapshot, packet_config)
        create_request = _request(
            "workspace.create",
            "git-workspaces",
            {
                "project_id": project_id,
                "name": workspace_name,
                "branch": branch,
                "base": None,
                "recover_dead": True,
            },
            "agent-control",
        )
        try:
            created = call(arguments.socket, create_request)
        except (OSError, ProtocolError, SinnixdClientError):
            created = _unavailable_response(create_request)
        if created.get("ok") is not True:
            response = _packet_step_failure(created, "workspace.create")
        else:
            response: dict[str, object] | None = None
            packet_notes = _packet_notes(created)
            payload = created.get("payload")
            value = payload.get("value") if isinstance(payload, dict) else None
            workspace_id = (
                value.get("workspace_id") if isinstance(value, dict) else None
            )

            def compensate(
                step_response: dict[str, object], step: str
            ) -> dict[str, object]:
                if not isinstance(workspace_id, str) or not workspace_id:
                    return _packet_step_failure(step_response, step)
                dispose_request = _request(
                    "workspace.dispose",
                    "git-workspaces",
                    {"workspace_id": workspace_id},
                    "agent-control",
                )
                try:
                    disposed = call(arguments.socket, dispose_request)
                except (OSError, ProtocolError, SinnixdClientError):
                    disposed = _unavailable_response(dispose_request)
                return _packet_step_failure(step_response, step, rollback=disposed)

            try:
                checkout_id = checkout_id_from_workspace_response(created)
            except PacketError:
                if not isinstance(workspace_id, str) or not workspace_id:
                    response = _packet_step_failure(
                        {
                            "ok": False,
                            "error": {
                                "code": "RESULT_INVALID",
                                "message": (
                                    "workspace.create did not return a workspace identity"
                                ),
                            },
                        },
                        "workspace.create",
                    )
                else:
                    get_request = _request(
                        "workspace.get",
                        "git-workspaces",
                        {"workspace_id": workspace_id},
                        "agent-control",
                    )
                    try:
                        status = call(arguments.socket, get_request)
                    except (OSError, ProtocolError, SinnixdClientError):
                        status = _unavailable_response(get_request)
                    if status.get("ok") is not True:
                        response = compensate(status, "workspace.get")
                        checkout_id = ""
                    else:
                        try:
                            checkout_id = checkout_id_from_workspace_response(status)
                        except PacketError as error:
                            response = compensate(
                                {
                                    "ok": False,
                                    "error": {
                                        "code": "RESULT_INVALID",
                                        "message": str(error),
                                    },
                                },
                                "workspace.get",
                            )
                            checkout_id = ""
            if response is None:
                dimensions = snapshot.dimensions.to_dict()
                agent_request = _request(
                    "job.agent.start",
                    "systemd-jobs",
                    {
                        "project_id": project_id,
                        "checkout_id": checkout_id,
                        "prompt": snapshot.prompt,
                        "backend": snapshot.dimensions.backend,
                        "model": snapshot.dimensions.model,
                        "effort": snapshot.dimensions.effort,
                        "credential_profile": arguments.credential_profile,
                        "timeout_seconds": arguments.timeout_seconds,
                        "coordinator_label": arguments.coordinator_label,
                        "result": "last-message",
                        "parameters": {
                            "template_version": packet_config.template_version,
                            "dimensions": dimensions,
                            "campaign": {
                                "group": snapshot.group,
                                "bead_ids": list(snapshot.bead_ids),
                            },
                            **({"packet_notes": packet_notes} if packet_notes else {}),
                        },
                        "dimensions": runtime_dimensions(snapshot.dimensions),
                        "exclusive_keys": list(snapshot.dimensions.conflict_keys),
                        "reject_conflicts": True,
                    },
                    "agent-control",
                )
                try:
                    response = call(arguments.socket, agent_request)
                except (OSError, ProtocolError, SinnixdClientError):
                    response = _unavailable_response(agent_request)
                if response.get("ok") is not True:
                    response = compensate(response, "job.agent.start")
                response = _attach_packet_notes(response, packet_notes)
    elif arguments.command == "job" and arguments.job_command == "start":
        try:
            parameters = json.loads(arguments.parameters_json)
        except json.JSONDecodeError as error:
            parser().error(f"--parameters-json must be valid JSON: {error.msg}")
        if not isinstance(parameters, dict):
            parser().error("--parameters-json must be a JSON object")
        binding = None
        if arguments.bead_binding_json is not None:
            try:
                binding = json.loads(arguments.bead_binding_json)
            except json.JSONDecodeError as error:
                parser().error(f"--bead-binding-json must be valid JSON: {error.msg}")
            if not isinstance(binding, dict):
                parser().error("--bead-binding-json must be a JSON object")
        try:
            dimensions = json.loads(arguments.dimensions_json)
        except json.JSONDecodeError as error:
            parser().error(f"--dimensions-json must be valid JSON: {error.msg}")
        if not isinstance(dimensions, dict):
            parser().error("--dimensions-json must be a JSON object")
        request = _request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": arguments.project_id,
                "operation": arguments.operation,
                "workspace_id": arguments.workspace,
                "parameters": parameters,
                **({"dimensions": dimensions} if dimensions else {}),
                **({"bead_binding": binding} if binding is not None else {}),
            },
        )
    elif arguments.command == "job" and arguments.job_command == "fire":
        request = _request(
            "job.fire",
            "systemd-jobs",
            {
                "project_id": arguments.project_id,
                "operation": arguments.operation,
                "schedule_id": arguments.schedule_id,
            },
        )
    elif arguments.command == "plan" and arguments.plan_command == "submit":
        if arguments.workspace is not None and arguments.checkout is not None:
            parser().error("plan submit accepts --workspace or --checkout, not both")
        try:
            plan_input = json.loads(arguments.plan_file.read_text())
        except (OSError, json.JSONDecodeError) as error:
            parser().error(f"--plan-file must contain valid JSON: {error}")
        if isinstance(plan_input, list):
            nodes = plan_input
        elif isinstance(plan_input, dict) and isinstance(plan_input.get("nodes"), list):
            nodes = plan_input["nodes"]
        else:
            parser().error(
                "--plan-file must contain a node array or an object with nodes"
            )
        request_arguments: dict[str, object] = {
            "project_id": arguments.project_id,
            "input_generation": arguments.input_generation,
            "nodes": nodes,
        }
        if arguments.node_operation is not None:
            request_arguments["node_operation"] = arguments.node_operation
        if arguments.workspace is not None:
            request_arguments["workspace_id"] = arguments.workspace
        if arguments.checkout is not None:
            request_arguments["checkout_id"] = arguments.checkout
        request = _request("plan.submit", "project-plans", request_arguments)
    elif arguments.command == "plan" and arguments.plan_command == "get":
        request = _request("plan.get", "project-plans", {"plan_id": arguments.plan_id})
    elif arguments.command == "plan" and arguments.plan_command == "list":
        request = _request(
            "plan.list",
            "project-plans",
            ({"project_id": arguments.project} if arguments.project else {}),
        )
    elif arguments.command == "plan" and arguments.plan_command == "wait":
        request = _request(
            "plan.wait",
            "project-plans",
            {
                "plan_id": arguments.plan_id,
                "timeout_seconds": arguments.timeout_seconds,
            },
        )
    elif arguments.command == "plan" and arguments.plan_command == "result":
        request = _request(
            "plan.result",
            "project-plans",
            {"plan_id": arguments.plan_id, "max_bytes": arguments.max_bytes},
        )
    elif arguments.command == "job" and arguments.job_command in {"get", "status"}:
        request = _request("job.get", "systemd-jobs", {"job_id": arguments.job_id})
    elif arguments.command == "job" and arguments.job_command == "retry":
        request = _request(
            "job.retry",
            "systemd-jobs",
            {
                "job_id": arguments.job_id,
                **({"hint": arguments.hint} if arguments.hint is not None else {}),
                "escalate": arguments.escalate,
            },
            "agent-control",
        )
    elif arguments.command == "job" and arguments.job_command == "list":
        request = _request(
            "job.list",
            "systemd-jobs",
            {
                "limit": arguments.limit,
                "cursor": arguments.cursor,
                "project_id": arguments.project,
                "phases": arguments.phase,
                "kinds": arguments.kind,
                "active_only": arguments.active,
            },
        )
    elif arguments.command == "job" and arguments.job_command == "wait":
        if len(arguments.job_ids) > 1 and not arguments.wait_any:
            parser().error("waiting on multiple job ids requires --any")
        request = _request(
            "job.wait",
            "systemd-jobs",
            {
                **(
                    {"job_ids": arguments.job_ids}
                    if arguments.wait_any
                    else {"job_id": arguments.job_ids[0]}
                ),
                "timeout_seconds": arguments.timeout_seconds,
            },
        )
    elif arguments.command == "job" and arguments.job_command == "logs":
        request = _request(
            "job.logs",
            "systemd-jobs",
            {
                "job_id": arguments.job_id,
                "offset": arguments.offset,
                "max_bytes": arguments.max_bytes,
            },
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
        if arguments.task_command == "create":
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
        elif arguments.task_command in {
            "claim",
            "complete",
            "release",
            "note",
            "relate",
            "update",
        }:
            task_arguments["task_id"] = arguments.task_id
            if arguments.task_command == "note":
                if (arguments.text is None) == (arguments.text_option is None):
                    parser().error(
                        "task note requires exactly one of positional text or --text"
                    )
                task_arguments["text"] = (
                    arguments.text_option
                    if arguments.text_option is not None
                    else arguments.text
                )
            elif arguments.task_command == "relate":
                task_arguments["related_task_id"] = arguments.related_task_id
            elif arguments.task_command == "update":
                task_arguments["metadata"] = dict(arguments.set_metadata)
            elif arguments.task_command in {"complete", "release"}:
                if arguments.reason is not None:
                    task_arguments["reason"] = arguments.reason
                if arguments.task_command == "complete":
                    task_arguments["merge_sha"] = arguments.merge_sha
                if (
                    arguments.task_command == "release"
                    and arguments.if_assignee is not None
                ):
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
    if not (arguments.command == "packet" and arguments.packet_command == "launch"):
        try:
            response = call(arguments.socket, request)
            if (
                getattr(arguments, "wait", False)
                and arguments.command == "workspace"
                and response.get("ok") is True
            ):
                response = _wait_for_delivery(arguments.socket, response)
        except (OSError, ProtocolError, SinnixdClientError):
            response = _unavailable_response(request)
    if getattr(arguments, "plain", False):
        print(_render_plain(response))
    else:
        print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response.get("ok") is True else 1


def _wait_for_delivery(
    socket_path: Path, started: dict[str, object]
) -> dict[str, object]:
    """Follow a delivery job to its receipt for the --wait convenience."""
    payload = started.get("payload")
    value = payload.get("value") if isinstance(payload, dict) else None
    job_id = value.get("job_id") if isinstance(value, dict) else None
    timeout_seconds = value.get("timeout_seconds") if isinstance(value, dict) else None
    if not isinstance(job_id, str):
        return started
    wait_request = _request(
        "job.wait",
        "systemd-jobs",
        {
            "job_id": job_id,
            "timeout_seconds": timeout_seconds + 10
            if isinstance(timeout_seconds, int)
            else 800,
        },
    )
    waited = call(socket_path, wait_request)
    waited_value = (
        waited.get("payload", {}).get("value")
        if isinstance(waited.get("payload"), dict)
        else None
    )
    state = waited_value.get("state") if isinstance(waited_value, dict) else None
    if not isinstance(state, dict) or state.get("phase") != "succeeded":
        return waited
    return call(
        socket_path,
        _request("job.result", "systemd-jobs", {"job_id": job_id}),
    )


def daemon_main() -> None:
    arguments = daemon_parser().parse_args()
    service = SinnixdService(
        ProjectCatalog(arguments.project_root),
        jobs=GenericJobs(
            UserSystemdJobs(),
            GenericJobStore(arguments.state_dir),
            notify_socket=arguments.socket,
            event_spool_path=arguments.event_spool,
        ),
        native_runner=arguments.native_runner,
    )
    UnixSocketServer(arguments.socket, service).serve_forever()
