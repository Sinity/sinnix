from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any, Mapping
from uuid import uuid4

import tomllib
from sinnix_mcp import (
    ErrorCode,
    ErrorEnvelope,
    OpaquePayload,
    RequestEnvelope,
    ResponseEnvelope,
)

from .api import (
    ProtocolError,
    ResponseBudgetExceeded,
    SinnixdClientError,
    UnixSocketServer,
    call,
)
from .jobs import (
    GenericJobs,
    GenericJobStore,
    UserSystemdJobs,
    default_state_dir,
    host_pressure,
)
from .limits import DEFAULT_TIMEOUT_SECONDS, MAX_AGENT_TIMEOUT_SECONDS
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


def _continuation_preamble(project: str) -> str:
    """Generated environment preamble for prompts that skip packet compilation.

    Packet launches compile the worker contract into their prompts; a bare
    agent launch historically sent the prompt file verbatim, so continuation
    agents had to rediscover how to invoke the project tooling — one lane
    burned a full round on `command not found: devtools` (sinnix-05rs).
    """
    try:
        root = resolve_project_root(project)
        raw = tomllib.loads((root / ".agentctl" / "project.toml").read_text())
    except (PacketError, OSError, tomllib.TOMLDecodeError):
        return ""
    command = raw.get("environment", {}).get("command")
    if not isinstance(command, list) or not all(
        isinstance(item, str) and item for item in command
    ):
        return ""
    wrapper = " ".join(command)
    return (
        "# Continuation preamble (generated)\n\n"
        "You are continuing work in an existing project checkout. Any\n"
        "uncommitted work in the worktree is yours: assess it and continue.\n"
        "Run project commands through the declared environment wrapper from\n"
        "the worktree root:\n\n"
        f"    {wrapper} <command>\n\n"
        "The repository's own runner (e.g. `devtools`) lives inside that\n"
        "wrapper (or the worktree's .venv), not on the bare PATH.\n\n"
        "---\n\n"
    )


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
    target.add_argument(
        "--timeout-seconds", type=int, default=MAX_AGENT_TIMEOUT_SECONDS
    )
    target.add_argument("--dimensions-json", default="{}")
    target.add_argument(
        "--coordinator-label",
        "--coordinator",
        "--campaign-label",
        dest="coordinator_label",
        help="Optional campaign/coordinator label copied to terminal events.",
    )


def default_socket_path() -> Path:
    return (
        Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        / "sinnixd.sock"
    )


def _localize_stamp(value: object) -> object:
    """Render an ISO timestamp in host-local time for human output.

    Storage and wire stay timezone-aware UTC; only displays convert. A naive
    stamp is assumed UTC (every sinnixd producer writes aware UTC; the
    assumption covers foreign producers) and marked with the local zone all
    the same so the reader never has to guess.
    """
    if not isinstance(value, str) or len(value) < 19 or value[4] != "-":
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


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
    project = subcommands.add_parser("project")
    project_subcommands = project.add_subparsers(dest="project_command", required=True)
    project_subcommands.add_parser("list")
    project_subcommands.add_parser(
        "reload", help="Re-read every project descriptor without restarting."
    )
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
    workspace_drop = workspace_subcommands.add_parser(
        "drop",
        help="Delete a workspace, its branch, and every job record and artifact bound to it.",
    )
    workspace_drop.add_argument("workspace_id")
    workspace_drop.add_argument(
        "--target",
        dest="integration_target",
        help="Prove publication by tree-equivalence with this integrated ref.",
    )
    workspace_drop.add_argument(
        "--force",
        action="store_true",
        help="Drop without proving the content is published.",
    )
    workspace_checkpoint = workspace_subcommands.add_parser("checkpoint")
    workspace_checkpoint.add_argument("workspace_id")
    workspace_restore = workspace_subcommands.add_parser("restore")
    workspace_restore.add_argument("workspace_id")
    workspace_restore.add_argument("checkpoint_id")
    workspace_restore.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate the worktree from the branch when its path is gone.",
    )
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
    events = subcommands.add_parser("events")
    events_subcommands = events.add_subparsers(dest="events_command", required=True)
    events_tail = events_subcommands.add_parser(
        "tail", help="Read the shared event spool as typed one-line events."
    )
    events_tail.add_argument("--follow", "-f", action="store_true")
    events_tail.add_argument("--kind", help="Comma-separated event kinds to include.")
    events_tail.add_argument(
        "--all-kinds",
        action="store_true",
        help="Include host-maintenance kinds the agent plane does not act on.",
    )
    events_tail.add_argument(
        "--since", help="ISO timestamp lower bound (matches the 'at' field)."
    )
    events_tail.add_argument("--limit", type=int, default=200)
    events_tail.add_argument(
        "--spool", type=Path, default=Path("/realm/state/agentctl/events.jsonl")
    )
    lane = subcommands.add_parser("lane")
    lane_subcommands = lane.add_subparsers(dest="lane_command", required=True)
    lane_publish = lane_subcommands.add_parser(
        "publish",
        help="Mint a receipt and authorize it in one pass, deriving identity from records.",
    )
    lane_publish.add_argument("workspace")
    lane_publish.add_argument("--close", action="store_true")
    lane_publish.add_argument("--timeout-seconds", type=int, default=7200)
    lane_authorize = lane_subcommands.add_parser(
        "authorize",
        help="Record the operator's decision for a workspace's current head; the reactor publishes past the scanner on it.",
    )
    lane_authorize.add_argument("workspace")
    lane_authorize.add_argument("--reason", default="")
    packet = subcommands.add_parser("packet")
    packet_subcommands = packet.add_subparsers(dest="packet_command", required=True)
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
    campaign_view = campaign_subcommands.add_parser(
        "view",
        help="One screen for the operator: what needs attention, lanes by next action, active jobs, corpus.",
    )
    campaign_view.add_argument("--project", required=True)
    campaign_view.add_argument("--coordinator-label")
    campaign_view.add_argument(
        "--json",
        action="store_true",
        help="Print the status payload instead of the screen.",
    )
    campaign_log = campaign_subcommands.add_parser(
        "log",
        help="One lane's timeline: its jobs, the events about it, and its current verdict.",
    )
    campaign_log.add_argument("--project", required=True)
    campaign_log.add_argument("--workspace", required=True)
    campaign_integrate = campaign_subcommands.add_parser(
        "integrate",
        help="Group lane branches holding unintegrated content into batches.",
    )
    campaign_integrate.add_argument("--project", required=True)
    campaign_integrate.add_argument("--base", default="origin/master")
    campaign_integrate.add_argument("--max-units", type=int, default=8)
    campaign_integrate.add_argument(
        "--assemble",
        metavar="INDEX",
        type=int,
        help="Merge one batch onto a fresh branch instead of listing batches.",
    )
    campaign_integrate.add_argument("--name", default="batch")
    job = subcommands.add_parser("job")
    job_subcommands = job.add_subparsers(dest="job_command", required=True)
    start = job_subcommands.add_parser("start")
    start.add_argument("project_id")
    start.add_argument("operation")
    start.add_argument(
        "--workspace",
        help="Managed workspace name or ID.",
    )
    start.add_argument("--parameters-json", default="{}")
    start.add_argument("--bead-binding-json")
    start.add_argument("--dimensions-json", default="{}")
    start.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the started job and return its result.",
    )
    start.add_argument(
        "--wait-timeout-seconds",
        type=int,
        help="Maximum time to wait; defaults to the declared operation timeout.",
    )
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
    job_list = job_subcommands.add_parser("list")
    job_list.add_argument("--limit", type=int, choices=range(1, 1001), default=100)
    job_list.add_argument("--project")
    job_list.add_argument("--phase", action="append", default=[])
    job_list.add_argument("--kind", action="append", default=[])
    job_list.add_argument(
        "--active", "--active-only", dest="active", action="store_true"
    )
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
    admission = job_subcommands.add_parser(
        "admission", help="Show admission queue, claims, and blocking arithmetic."
    )
    admission.add_argument("--project")
    plan = subcommands.add_parser("plan")
    plan_subcommands = plan.add_subparsers(dest="plan_command", required=True)
    plan_submit = plan_subcommands.add_parser("submit")
    plan_submit.add_argument("project_id")
    plan_submit.add_argument("--node-operation")
    plan_submit.add_argument("--workspace")
    plan_submit.add_argument("--checkout")
    plan_submit.add_argument("--plan-file", type=Path, required=True)
    plan_get = plan_subcommands.add_parser("get")
    plan_get.add_argument("plan_id")
    plan_wait = plan_subcommands.add_parser("wait")
    plan_wait.add_argument("plan_id")
    plan_wait.add_argument("--timeout-seconds", type=int, default=30)
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
        error=ErrorEnvelope(
            ErrorCode.OWNER_UNAVAILABLE,
            "sinnixd is unavailable",
            details=OpaquePayload.bounded(
                {"operation": request.operation, "effect": "none"}
            ),
        ),
    ).to_dict()


def _client_error_response(
    request: RequestEnvelope, error: Exception
) -> dict[str, object]:
    """An exhausted response budget is not an outage; keep the two typed."""
    if isinstance(error, ResponseBudgetExceeded):
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner=request.owner,
            error=ErrorEnvelope(
                ErrorCode.RESPONSE_BUDGET_EXCEEDED,
                "sinnixd response budget exceeded",
                details=OpaquePayload.bounded(
                    {"operation": request.operation, "effect": error.effect}
                ),
            ),
        ).to_dict()
    code = getattr(error, "code", ErrorCode.OWNER_UNAVAILABLE)
    effect = getattr(error, "effect", "none")
    operation = getattr(error, "operation", request.operation)
    return ResponseEnvelope(
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        owner=request.owner,
        error=ErrorEnvelope(
            code,
            "sinnixd is unavailable"
            if code is ErrorCode.OWNER_UNAVAILABLE
            else "sinnixd request failed",
            details=OpaquePayload.bounded({"operation": operation, "effect": effect}),
        ),
    ).to_dict()


_JOB_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)


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
        candidates = ", ".join(matches[:8])
        parser().error(
            f"job id prefix {value!r} matches {len(matches)} jobs: {candidates}"
        )
    return value


#: Spool kinds written by host maintenance rather than the agent plane.
NON_AGENT_EVENT_KINDS = frozenset({"service_failure"})


def _operator_view(arguments: argparse.Namespace) -> int:
    """`campaign view` / `campaign log`: the status payload plus local job and spool reads, rendered for a person."""
    from .jobs import default_state_dir
    from .operator_view import load_jobs, render_lane_log, render_overview
    from .publication_sweep import DEFAULT_SPOOL

    label = getattr(arguments, "coordinator_label", None)
    request = _request(
        "campaign.status",
        "campaign-orchestrator",
        {
            "project_id": arguments.project,
            **({"coordinator_label": label} if label else {}),
        },
        "operator",
    )
    try:
        response = call(arguments.socket, request)
    except (OSError, ResponseBudgetExceeded) as error:
        response = _client_error_response(request, error)
    if response.get("ok") is not True:
        print(_render_plain(response))
        return 1
    payload = response.get("payload") or {}
    status = (
        payload.get("value")
        if isinstance(payload, Mapping) and isinstance(payload.get("value"), Mapping)
        else payload
    )
    if getattr(arguments, "json", False):
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0
    jobs = load_jobs(default_state_dir() / "jobs", arguments.project)
    if arguments.campaign_command == "log":
        print(render_lane_log(arguments.workspace, status, jobs, DEFAULT_SPOOL))
        return 0
    active = subprocess.run(
        ["systemctl", "--user", "is-active", "sinnixd-reactor"],
        capture_output=True,
        text=True,
        check=False,
    )
    from .operator_view import _reactor_last_dispatch

    print(
        render_overview(
            status,
            jobs,
            reactor_active=active.stdout.strip() == "active",
            last_dispatch=_reactor_last_dispatch(DEFAULT_SPOOL),
        )
    )
    return 0


def _render_plain(response: Mapping[str, Any]) -> str:
    """The payload value as text, for callers that want the answer not the envelope."""
    if response.get("ok") is not True:
        error = response.get("error")
        message = error.get("message") if isinstance(error, Mapping) else None
        code = error.get("code") if isinstance(error, Mapping) else None
        details = error.get("details") if isinstance(error, Mapping) else None
        detail_value = details.get("value") if isinstance(details, Mapping) else None
        operation = (
            detail_value.get("operation") if isinstance(detail_value, Mapping) else None
        )
        effect = (
            detail_value.get("effect") if isinstance(detail_value, Mapping) else None
        )
        context = ""
        if isinstance(code, str):
            context = f" [{code}"
            if isinstance(operation, str):
                context += f" operation={operation}"
            if isinstance(effect, str):
                context += f" effect={effect}"
            context += "]"
        return f"ERROR{context}: {message or 'request failed'}"
    payload = response.get("payload")
    value = payload.get("value") if isinstance(payload, Mapping) else payload
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping) and isinstance(value.get("content"), str):
        return value["content"]
    if isinstance(value, Mapping) and isinstance(value.get("workspaces"), list):
        rows = []
        for item in value["workspaces"]:
            if isinstance(item, Mapping):
                rows.append(
                    f"{str(item.get('name') or '')[:40]:40} "
                    f"{str(item.get('project_id') or ''):12} "
                    f"{str(item.get('branch') or '')[:48]:48} "
                    f"{item.get('workspace_id') or ''}"
                )
        return "\n".join(rows) if rows else "(no workspaces)"
    if isinstance(value, Mapping) and "job_id" in value and "state" in value:
        state = value.get("state")
        phase = state.get("phase") if isinstance(state, Mapping) else None
        cause = state.get("terminal_cause") if isinstance(state, Mapping) else None
        checkout = value.get("checkout")
        where = checkout.get("path") if isinstance(checkout, Mapping) else ""
        cause_text = ""
        if isinstance(cause, Mapping):
            kind = cause.get("kind")
            code = cause.get("exit_code")
            tail = cause.get("stderr_tail")
            detail = tail[-1] if isinstance(tail, list) and tail else None
            cause_text = f" cause={kind}"
            if code is not None:
                cause_text += f" exit={code}"
            if isinstance(detail, str) and detail:
                cause_text += f" detail={detail}"
        return (
            f"{value['job_id']} {value.get('operation') or value.get('kind') or ''} "
            f"phase={phase}{cause_text} project={value.get('project_id')} {where}"
        )
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
        if not prompt.startswith("# Dispatch packet ("):
            prompt = _continuation_preamble(arguments.project) + prompt
            if len(prompt.encode()) > 200_000:
                parser().error(
                    "--prompt-file leaves no room for the continuation preamble; trim it"
                )
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
    elif arguments.command == "project" and arguments.project_command == "reload":
        request = _request("project.reload", "project-adapters", {})
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
    elif arguments.command == "workspace" and arguments.workspace_command == "drop":
        request = _request(
            "workspace.drop",
            "git-workspaces",
            {
                "workspace_id": arguments.workspace_id,
                **({"force": True} if arguments.force else {}),
                **(
                    {"integration_target": arguments.integration_target}
                    if arguments.integration_target
                    else {}
                ),
            },
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
                **({"recreate": True} if arguments.recreate else {}),
            },
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
    elif arguments.command == "workspace" and arguments.workspace_command == "finish":
        request = _request(
            "workspace.finish",
            "git-workspaces",
            {"workspace_id": arguments.workspace_id},
            "agent-control",
        )
    elif arguments.command == "events" and arguments.events_command == "tail":
        kinds = (
            {part.strip() for part in arguments.kind.split(",") if part.strip()}
            if arguments.kind
            else None
        )
        # The spool is shared with host maintenance, whose failures agents
        # cannot act on and which outnumber agent events on this host.
        excluded = (
            frozenset() if arguments.all_kinds or kinds else NON_AGENT_EVENT_KINDS
        )

        def emit(line: str) -> None:
            line = line.strip()
            if not line:
                return
            try:
                event = json.loads(line)
            except ValueError:
                return
            if not isinstance(event, dict):
                return
            if kinds is not None and event.get("kind") not in kinds:
                return
            if event.get("kind") in excluded:
                return
            stamp = str(
                event.get("at")
                or event.get("observed_at")
                or event.get("completed_at")
                or event.get("emitted_at")
                or ""
            )
            if arguments.since and stamp and stamp < arguments.since:
                return
            if getattr(arguments, "plain", False):
                print(json.dumps(event, sort_keys=True), flush=True)
                return
            kind = str(event.get("kind") or "event")
            rest = " ".join(
                f"{key}={_localize_stamp(event[key])}"
                for key in sorted(event)
                if key not in {"kind"} and not isinstance(event[key], (dict, list))
            )
            print(f"{kind} {rest}"[:2000], flush=True)

        spool: Path = arguments.spool
        try:
            existing = spool.read_text().splitlines()
        except OSError:
            existing = []
        for line in existing[-arguments.limit :]:
            emit(line)
        if arguments.follow:
            import time as _time

            with open(spool, "r") as handle:
                handle.seek(0, os.SEEK_END)
                while True:
                    line = handle.readline()
                    if line:
                        emit(line)
                    else:
                        _time.sleep(0.5)
        return 0
    elif arguments.command == "lane" and arguments.lane_command == "authorize":
        list_request = _request("workspace.list", "git-workspaces", {})
        try:
            listing = call(arguments.socket, list_request)
        except (OSError, ProtocolError, SinnixdClientError) as error:
            listing = _client_error_response(list_request, error)
        workspaces = (
            listing.get("payload", {}).get("value", {}).get("workspaces", [])
            if isinstance(listing, dict) and listing.get("ok") is True
            else []
        )
        record = next(
            (
                item
                for item in workspaces
                if arguments.workspace in {item.get("name"), item.get("workspace_id")}
            ),
            None,
        )
        if record is None or not isinstance(record.get("path"), str):
            print(
                json.dumps(
                    {"ok": False, "error": f"unknown workspace: {arguments.workspace}"},
                    sort_keys=True,
                )
            )
            return 1
        worktree = Path(record["path"])
        head = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            print(
                json.dumps(
                    {"ok": False, "error": "workspace head is unreadable"},
                    sort_keys=True,
                )
            )
            return 1
        authorization = {
            "head": head,
            "reason": arguments.reason,
            "at": datetime.now(UTC).isoformat(),
            "by": "operator",
            "workspace": record.get("name"),
        }
        (worktree / ".lane").mkdir(exist_ok=True)
        (worktree / ".lane" / "authorization.json").write_text(
            json.dumps(authorization, sort_keys=True) + "\n"
        )
        print(
            json.dumps(
                {"ok": True, "authorization": authorization}, indent=1, sort_keys=True
            )
        )
        return 0
    elif arguments.command == "lane" and arguments.lane_command == "publish":
        # The reply always names the harvest job once one exists; a failure
        # before enqueue is a typed step error, never a fake unknown-workspace
        # or RESULT_INVALID (sinnix-e307).
        def _lane_publish_reply(
            *,
            ok: bool,
            step: str | None = None,
            job_id: str | None = None,
            phase: str | None = None,
            outcome: str | None = None,
            error: object = None,
            result: object = None,
        ) -> dict[str, object]:
            reply: dict[str, object] = {"ok": ok}
            if job_id is not None:
                reply["job_id"] = job_id
            if phase is not None:
                reply["phase"] = phase
            if outcome is not None:
                reply["outcome"] = outcome
            if step is not None:
                reply["failed_step"] = step
            if error is not None:
                reply["error"] = error
            if result is not None:
                reply["result"] = result
            return reply

        list_request = _request("workspace.list", "git-workspaces", {})
        try:
            listing = call(arguments.socket, list_request)
        except (OSError, ProtocolError, SinnixdClientError) as error:
            listing = _client_error_response(list_request, error)
        if not (isinstance(listing, dict) and listing.get("ok") is True):
            print(
                json.dumps(
                    _lane_publish_reply(
                        ok=False,
                        step="workspace.list",
                        error=listing.get("error")
                        if isinstance(listing, dict)
                        else None,
                    ),
                    indent=1,
                    sort_keys=True,
                )
            )
            return 1
        workspaces = listing.get("payload", {}).get("value", {}).get("workspaces", [])
        record = next(
            (
                item
                for item in workspaces
                if arguments.workspace in {item.get("name"), item.get("workspace_id")}
            ),
            None,
        )
        if record is None:
            print(
                json.dumps(
                    _lane_publish_reply(
                        ok=False,
                        step="workspace.list",
                        error={
                            "code": "INVALID_ARGUMENT",
                            "message": f"unknown workspace: {arguments.workspace}",
                        },
                    ),
                    indent=1,
                    sort_keys=True,
                )
            )
            return 1
        start_request = _request(
            "job.start",
            "systemd-jobs",
            {
                "project_id": record["project_id"],
                "operation": "harvest",
                "workspace_id": record["name"],
                "parameters": {
                    "publish": True,
                    **({"close": True} if arguments.close else {}),
                },
            },
        )
        try:
            started = call(arguments.socket, start_request)
        except (OSError, ProtocolError, SinnixdClientError) as error:
            started = _client_error_response(start_request, error)
        job_id = (
            started.get("payload", {}).get("value", {}).get("job_id")
            if isinstance(started, dict)
            else None
        )
        if not isinstance(job_id, str):
            print(
                json.dumps(
                    _lane_publish_reply(
                        ok=False,
                        step="job.start",
                        error=started.get("error")
                        if isinstance(started, dict)
                        else None,
                    ),
                    indent=1,
                    sort_keys=True,
                )
            )
            return 1
        wait_request = _request(
            "job.wait",
            "systemd-jobs",
            {"job_id": job_id, "timeout_seconds": arguments.timeout_seconds},
        )
        try:
            call(arguments.socket, wait_request)
        except (OSError, ProtocolError, SinnixdClientError):
            pass
        get_request = _request("job.get", "systemd-jobs", {"job_id": job_id})
        try:
            status = call(arguments.socket, get_request)
        except (OSError, ProtocolError, SinnixdClientError) as error:
            status = _client_error_response(get_request, error)
        state = (
            status.get("payload", {}).get("value", {}).get("state", {})
            if isinstance(status, dict)
            else {}
        )
        phase = state.get("phase") if isinstance(state, dict) else None
        if not (isinstance(state, dict) and state.get("terminal")):
            print(
                json.dumps(
                    _lane_publish_reply(
                        ok=False,
                        job_id=job_id,
                        phase=phase if isinstance(phase, str) else None,
                        error={
                            "code": "HARVEST_PENDING",
                            "message": (
                                "the harvest job is enqueued but not terminal; "
                                f"follow it with: agentctl job wait {job_id}"
                            ),
                        },
                    ),
                    indent=1,
                    sort_keys=True,
                )
            )
            return 2
        result_request = _request("job.result", "systemd-jobs", {"job_id": job_id})
        try:
            response = call(arguments.socket, result_request)
        except (OSError, ProtocolError, SinnixdClientError) as error:
            response = _client_error_response(result_request, error)
        payload_value = (
            response.get("payload", {}).get("value", {})
            if isinstance(response, dict)
            else {}
        )
        inner = payload_value.get("value") if isinstance(payload_value, dict) else None
        outcome = inner.get("outcome") if isinstance(inner, dict) else None
        ok = outcome in {"HARVEST_OK", "HARVEST_EMPTY"}
        print(
            json.dumps(
                _lane_publish_reply(
                    ok=ok,
                    job_id=job_id,
                    phase=phase if isinstance(phase, str) else None,
                    outcome=outcome if isinstance(outcome, str) else None,
                    result=response,
                ),
                indent=1,
                sort_keys=True,
            )
        )
        return 0 if ok else 1
    elif arguments.command == "campaign" and arguments.campaign_command == "integrate":
        from .integration import assemble, discover_units, pack

        root = resolve_project_root(arguments.project)
        common = Path(
            subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
        )
        units = discover_units(Path("/realm/worktrees"), common, arguments.base)
        batches = pack(units, arguments.max_units)
        if arguments.assemble is None:
            payload = {
                "project_id": arguments.project,
                "units": len(units),
                "batches": [batch.to_dict() for batch in batches],
            }
        else:
            if not 0 <= arguments.assemble < len(batches):
                parser().error(f"no batch at index {arguments.assemble}")
            batch = batches[arguments.assemble]
            payload = assemble(
                batch,
                repo=root,
                worktree=Path("/realm/worktrees") / arguments.name,
                branch=f"integration/{arguments.name}",
                base=arguments.base,
            )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
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
    elif arguments.command == "campaign" and arguments.campaign_command in {
        "view",
        "log",
    }:
        return _operator_view(arguments)
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
        except (OSError, ProtocolError, SinnixdClientError) as error:
            created = _client_error_response(create_request, error)
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
                    "workspace.drop",
                    "git-workspaces",
                    {"workspace_id": workspace_id},
                    "agent-control",
                )
                try:
                    disposed = call(arguments.socket, dispose_request)
                except (OSError, ProtocolError, SinnixdClientError) as error:
                    disposed = _client_error_response(dispose_request, error)
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
                    except (OSError, ProtocolError, SinnixdClientError) as error:
                        status = _client_error_response(get_request, error)
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
                except (OSError, ProtocolError, SinnixdClientError) as error:
                    response = _client_error_response(agent_request, error)
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
    elif arguments.command == "plan" and arguments.plan_command == "wait":
        request = _request(
            "plan.wait",
            "project-plans",
            {
                "plan_id": arguments.plan_id,
                "timeout_seconds": arguments.timeout_seconds,
            },
        )
    elif arguments.command == "job" and arguments.job_command == "get":
        request = _request("job.get", "systemd-jobs", {"job_id": arguments.job_id})
    elif arguments.command == "job" and arguments.job_command == "retry":
        request = _request(
            "job.retry",
            "systemd-jobs",
            {
                "job_id": arguments.job_id,
                **({"hint": arguments.hint} if arguments.hint is not None else {}),
            },
            "agent-control",
        )
    elif arguments.command == "job" and arguments.job_command == "list":
        request = _request(
            "job.list",
            "systemd-jobs",
            {
                "limit": arguments.limit,
                "project_id": arguments.project,
                "phases": arguments.phase,
                "kinds": arguments.kind,
                "active_only": arguments.active,
            },
        )
    elif arguments.command == "job" and arguments.job_command == "wait":
        request = _request(
            "job.wait",
            "systemd-jobs",
            {
                "job_id": arguments.job_id,
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
    elif arguments.command == "job" and arguments.job_command == "admission":
        request = _request(
            "job.admission",
            "systemd-jobs",
            {"project_id": arguments.project} if arguments.project else {},
        )
    elif arguments.command == "job":
        request = _request("job.cancel", "systemd-jobs", {"job_id": arguments.job_id})
    else:
        parser().error(f"unsupported command: {arguments.command}")
    wait_succeeded = True
    if not (arguments.command == "packet" and arguments.packet_command == "launch"):
        try:
            response = call(arguments.socket, request)
            if (
                getattr(arguments, "wait", False)
                and arguments.command == "workspace"
                and response.get("ok") is True
            ):
                response = _wait_for_delivery(arguments.socket, response)
            elif (
                getattr(arguments, "wait", False)
                and arguments.command == "job"
                and arguments.job_command == "start"
                and response.get("ok") is True
            ):
                response, wait_succeeded = _wait_for_job(
                    arguments.socket,
                    response,
                    timeout_seconds=arguments.wait_timeout_seconds,
                )
        except (OSError, ProtocolError, SinnixdClientError) as error:
            response = _client_error_response(request, error)
            wait_succeeded = False
    if getattr(arguments, "plain", False):
        print(_render_plain(response))
    else:
        print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response.get("ok") is True and wait_succeeded else 1


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


def _wait_for_job(
    socket_path: Path,
    started: dict[str, object],
    *,
    timeout_seconds: int | None,
) -> tuple[dict[str, object], bool]:
    """Follow a started job through terminal state and return its result."""
    payload = started.get("payload")
    value = payload.get("value") if isinstance(payload, dict) else None
    job_id = value.get("job_id") if isinstance(value, dict) else None
    declared_timeout = value.get("timeout_seconds") if isinstance(value, dict) else None
    if not isinstance(job_id, str):
        return started, False
    wait_for = timeout_seconds if timeout_seconds is not None else declared_timeout
    if not isinstance(wait_for, int) or wait_for < 1:
        return started, False
    deadline = time.monotonic() + wait_for
    while True:
        remaining = int(deadline - time.monotonic())
        if remaining < 1:
            return started, False
        waited = call(
            socket_path,
            _request(
                "job.wait",
                "systemd-jobs",
                {"job_id": job_id, "timeout_seconds": min(3600, remaining)},
            ),
        )
        waited_value = (
            waited.get("payload", {}).get("value") if isinstance(waited, dict) else None
        )
        state = waited_value.get("state") if isinstance(waited_value, dict) else None
        if not isinstance(state, dict):
            return waited, False
        if state.get("terminal") is True:
            if state.get("phase") != "succeeded":
                return waited, False
            result = call(
                socket_path,
                _request("job.result", "systemd-jobs", {"job_id": job_id}),
            )
            return result, result.get("ok") is True


def daemon_main() -> None:
    arguments = daemon_parser().parse_args()
    stop_event = Event()
    scheduler_errors: list[BaseException] = []
    service = SinnixdService(
        ProjectCatalog(arguments.project_root, tolerant=True),
        jobs=GenericJobs(
            UserSystemdJobs(),
            GenericJobStore(arguments.state_dir),
            pressure_probe=host_pressure,
            notify_socket=arguments.socket,
            event_spool_path=arguments.event_spool,
        ),
        native_runner=arguments.native_runner,
    )

    def schedule_admission() -> None:
        try:
            service.jobs.run_admission_scheduler(stop_event)
        except BaseException as error:
            scheduler_errors.append(error)
            stop_event.set()

    scheduler = Thread(
        target=schedule_admission,
        name="sinnixd-admission",
        daemon=True,
    )
    scheduler.start()
    try:
        UnixSocketServer(arguments.socket, service).serve_forever(stop_event)
    finally:
        stop_event.set()
        scheduler.join()
    if scheduler_errors:
        raise scheduler_errors[0]
