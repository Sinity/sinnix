"""agentctl: an in-process CLI over pueue, worktrunk, gh and bd.

Every verb runs to completion in this process, does what it was told, and
reports. Reads print tables in local time; `--json` prints the document.
Exit status: 0 done, 1 refused or failed, 2 usage, 3 the waited job did not
succeed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import lanes, launch, operator_view, schedule
from .config import Config, ConfigError, load_config, resolve_project
from .lanes import LaneError
from .launch import JobError
from .operator_view import age, local_clock, table
from .packets import PacketError
from .projects import ProjectConfigError, ProjectEnvironmentError
from .pueue import PueueError
from .schedule import TimerError
from .worktrunk import WorktrunkError

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_JOB_NOT_SUCCEEDED = 3

DEFAULT_WAIT_SECONDS = 3_600
DEFAULT_EVENT_LINES = 40
FOLLOW_POLL_SECONDS = 1.0

_ERRORS = (
    ConfigError,
    JobError,
    LaneError,
    PacketError,
    ProjectConfigError,
    ProjectEnvironmentError,
    PueueError,
    TimerError,
    WorktrunkError,
    KeyError,
)


def _agent_arguments(target: argparse.ArgumentParser) -> None:
    target.add_argument("--backend")
    target.add_argument("--model")
    target.add_argument("--effort")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="agentctl",
        description="Jobs over pueue, lanes over worktrunk + gh + bd, one operator view.",
    )
    root.add_argument(
        "--config", type=Path, help="agentctl.json (default /etc/sinnix/agentctl.json)"
    )
    root.add_argument(
        "--json", action="store_true", help="print the document instead of a table"
    )
    verbs = root.add_subparsers(dest="verb", required=True)
    project_help = (
        "project id or path (default: the checkout enclosing the working directory)"
    )

    project = verbs.add_parser("project", help="the configured project descriptors")
    project_verbs = project.add_subparsers(dest="project_verb", required=True)
    project_verbs.add_parser("list")
    for name in ("get", "operations"):
        one = project_verbs.add_parser(name)
        one.add_argument("project", nargs="?", help=project_help)

    job = verbs.add_parser("job", help="declared operations as pueue tasks")
    job_verbs = job.add_subparsers(dest="job_verb", required=True)
    start = job_verbs.add_parser("start")
    start.add_argument("project", help="project id or path")
    start.add_argument("operation")
    start.add_argument(
        "--workspace",
        type=Path,
        help="run in this worktree instead of the project root",
    )
    start.add_argument("--wait", action="store_true")
    start.add_argument("--timeout-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    start.add_argument(
        "extra", nargs="*", help="arguments appended to the declared exec (after --)"
    )
    fire = job_verbs.add_parser(
        "fire", help="a timer's launch: skipped while the operation is active"
    )
    fire.add_argument("project")
    fire.add_argument("operation")
    listing = job_verbs.add_parser("list")
    listing.add_argument("--project", help="filter by project id")
    listing.add_argument("--active", action="store_true")
    for name in ("get", "logs", "result", "cancel", "retry"):
        one = job_verbs.add_parser(name)
        one.add_argument("job_id", type=int)
    wait = job_verbs.add_parser("wait")
    wait.add_argument("job_id", type=int)
    wait.add_argument("--timeout-seconds", type=int, default=DEFAULT_WAIT_SECONDS)

    lane = verbs.add_parser(
        "lane", help="a worktree with an agent in it and a PR at the end"
    )
    lane_verbs = lane.add_subparsers(dest="lane_verb", required=True)
    lane_start = lane_verbs.add_parser("start")
    lane_start.add_argument("project")
    lane_start.add_argument("bead")
    _agent_arguments(lane_start)
    publish = lane_verbs.add_parser("publish")
    publish.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="the worktree (default: cwd)",
    )
    publish.add_argument("--bead")
    publish.add_argument("--title")
    publish.add_argument("--body-file", type=Path)
    rebase = lane_verbs.add_parser("rebase")
    rebase.add_argument("project")
    rebase.add_argument("bead")
    _agent_arguments(rebase)
    sync = lane_verbs.add_parser("sync")
    sync.add_argument("project", nargs="?", help=project_help)
    sync.add_argument("--actor", default="agentctl")

    refill = verbs.add_parser(
        "refill", help="start lanes for ready beads without a worktree or PR"
    )
    refill.add_argument("project", nargs="?", help=project_help)
    refill.add_argument("--limit", type=int, default=1)
    refill.add_argument("--dry-run", action="store_true")
    _agent_arguments(refill)

    view = verbs.add_parser("view", help="the operator screen")
    view.add_argument("project", nargs="?", help=project_help)

    events = verbs.add_parser(
        "events", help="the event spool: started and finished tasks, backpressure"
    )
    events_verbs = events.add_subparsers(dest="events_verb", required=True)
    tail = events_verbs.add_parser("tail")
    tail.add_argument("--lines", type=int, default=DEFAULT_EVENT_LINES)
    tail.add_argument("--follow", action="store_true")
    tail.add_argument("--project", help="filter by project id")

    timers = verbs.add_parser("schedule", help="calendar timers for declared schedules")
    timers_verbs = timers.add_subparsers(dest="schedule_verb", required=True)
    timers_verbs.add_parser("apply")
    return root


class Output:
    def __init__(self, as_json: bool) -> None:
        self.as_json = as_json
        self.now = datetime.now(UTC)

    def emit(self, document: Any, text: str | None = None) -> None:
        """The document as JSON, or the text a person reads (JSON when none)."""
        if self.as_json or text is None:
            print(json.dumps(document, indent=2, sort_keys=True))
        else:
            print(text)

    def job_line(self, job: Mapping[str, Any]) -> str:
        started = job.get("started_at") or job.get("enqueued_at")
        ended = job.get("ended_at")
        when = (
            f"finished {local_clock(ended)} after {age(started, operator_view.parse_stamp(ended) or self.now)}"
            if ended
            else f"since {local_clock(started)} ({age(started, self.now)})"
        )
        exit_text = (
            f" exit {job['exit_code']}" if job.get("exit_code") not in (None, 0) else ""
        )
        return f"job {job['job_id']} {job['label']} {job['phase']}{exit_text} {when}"

    def jobs_table(self, rows: Sequence[Mapping[str, Any]]) -> str:
        if not rows:
            return "(no jobs)"
        return table(
            ("id", "label", "phase", "started", "elapsed", "exit", "cwd"),
            [
                (
                    row["job_id"],
                    row["label"],
                    row["phase"],
                    local_clock(row.get("started_at") or row.get("enqueued_at")),
                    age(
                        row.get("started_at") or row.get("enqueued_at"),
                        operator_view.parse_stamp(row.get("ended_at")) or self.now,
                    ),
                    "" if row.get("exit_code") is None else row["exit_code"],
                    row.get("path", ""),
                )
                for row in rows
            ],
        )


def _job(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    verb = arguments.job_verb
    if verb == "start":
        project = resolve_project(config, arguments.project)
        operation = project.operation(arguments.operation)
        started = launch.start_operation(
            config,
            project,
            operation,
            workspace=arguments.workspace,
            extra_argv=tuple(arguments.extra),
        )
        if arguments.wait:
            started = launch.wait(
                started["job_id"], timeout_seconds=arguments.timeout_seconds
            )
        out.emit(started, out.job_line(started))
        if started.get("terminal"):
            return (
                EXIT_OK
                if started.get("phase") == "succeeded"
                else EXIT_JOB_NOT_SUCCEEDED
            )
        return EXIT_OK
    if verb == "fire":
        project = resolve_project(config, arguments.project)
        fired = launch.fire(config, project, project.operation(arguments.operation))
        text = (
            out.job_line(fired)
            if fired.get("fired")
            else f"{fired['label']} not fired: task(s) {fired['active']} still active"
        )
        out.emit(fired, text)
        return EXIT_OK
    if verb == "list":
        rows = launch.list_jobs(arguments.project)
        if arguments.active:
            rows = [row for row in rows if not row["terminal"]]
        out.emit(rows, out.jobs_table(rows))
        return EXIT_OK
    if verb == "get":
        job = launch.get_job(arguments.job_id)
        out.emit(job, out.job_line(job))
        return EXIT_OK
    if verb == "logs":
        sys.stdout.write(launch.logs(config, arguments.job_id))
        return EXIT_OK
    if verb == "result":
        result = launch.result(config, arguments.job_id)
        value = result.get("value")
        text = (
            out.job_line(result)
            if result.get("kind") == "exit"
            else (
                value
                if isinstance(value, str)
                else json.dumps(value, indent=2, sort_keys=True)
            )
        )
        out.emit(result, text)
        return EXIT_OK
    if verb == "cancel":
        job = launch.cancel(config, arguments.job_id)
        out.emit(job, out.job_line(job))
        return EXIT_OK
    if verb == "retry":
        job = launch.retry(arguments.job_id)
        out.emit(job, out.job_line(job))
        return EXIT_OK
    if verb == "wait":
        waited = launch.wait(
            arguments.job_id, timeout_seconds=arguments.timeout_seconds
        )
        out.emit(
            waited,
            out.job_line(waited)
            + (" (wait timed out)" if waited.get("wait_timed_out") else ""),
        )
        return EXIT_OK if waited.get("phase") == "succeeded" else EXIT_JOB_NOT_SUCCEEDED
    raise AssertionError(verb)


def _lane(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    verb = arguments.lane_verb
    if verb == "start":
        project = resolve_project(config, arguments.project)
        started = lanes.lane_start(
            config,
            project,
            arguments.bead,
            backend=arguments.backend,
            model=arguments.model,
            effort=arguments.effort,
        )
        out.emit(
            started,
            f"lane {started['bead']} on {started['branch']} at {started['worktree']}\n"
            f"{started['backend']} {started['model']} {started['effort']}: {out.job_line(started['job'])}",
        )
        return EXIT_OK
    if verb == "publish":
        published = lanes.lane_publish(
            config,
            arguments.path,
            bead_id=arguments.bead,
            title=arguments.title,
            body_file=arguments.body_file,
        )
        out.emit(
            published,
            f"PR #{published['pr']} {'opened' if published['created'] else 'already open'} "
            f"for {published['branch']}: {published['subject']}\n"
            f"{'auto-merge armed' if published['auto_merge'] else 'auto-merge unavailable'}: "
            f"{published['url']}\n"
            f"next action: {published['next_action']}",
        )
        return EXIT_OK
    if verb == "rebase":
        project = resolve_project(config, arguments.project)
        rebased = lanes.lane_rebase(
            config,
            project,
            arguments.bead,
            backend=arguments.backend,
            model=arguments.model,
            effort=arguments.effort,
        )
        out.emit(
            rebased,
            f"rebase {rebased['bead']} in {rebased['worktree']}: {out.job_line(rebased['job'])}",
        )
        return EXIT_OK
    if verb == "sync":
        project = resolve_project(config, arguments.project)
        synced = lanes.lane_sync(config, project, actor=arguments.actor)
        lines = [
            f"closed {len(synced['closed'])} bead(s): {', '.join(synced['closed']) or '-'}",
            f"removed {len(synced['removed'])} worktree(s): {', '.join(synced['removed']) or '-'}",
        ]
        if synced["remaining"]:
            lines.append(
                table(
                    ("branch", "bead", "state", "pr", "note"),
                    [
                        (
                            row["branch"],
                            row.get("bead") or "",
                            f"{row['state']}{' dirty' if row.get('dirty') else ''}",
                            f"#{row['pr']} {row['pr_state']}" if row.get("pr") else "-",
                            row.get("reason") or "",
                        )
                        for row in synced["remaining"]
                    ],
                )
            )
        out.emit(synced, "\n".join(lines))
        return EXIT_OK
    raise AssertionError(verb)


def _event_line(event: Mapping[str, Any]) -> str:
    stamp = local_clock(event.get("emitted_at"), seconds=True)
    kind = str(event.get("kind") or "")
    if kind == "queue-task":
        label = str(event.get("label") or "")
        if event.get("phase") == "started":
            return f"{stamp} {label} started"
        result = str(event.get("result") or "")
        exit_code = event.get("exit_code")
        return f"{stamp} {label} finished {result}{f' exit {exit_code}' if exit_code not in (None, '', '0', 0) else ''} (task {event.get('task_id')})"
    if kind == "backpressure":
        return f"{stamp} backpressure {event.get('action')} {event.get('group') or ''}".rstrip()
    detail = " ".join(
        f"{key}={value}"
        for key, value in sorted(event.items())
        if key not in {"kind", "emitted_at", "schema_version"}
        and not isinstance(value, (dict, list))
    )
    return f"{stamp} {kind} {detail}"


def _events(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    spool = config.event_spool
    project = arguments.project

    def wanted(line: str) -> bool:
        return (
            project is None
            or f'"{project}:' in line
            or f'"project":"{project}"' in line
        )

    def show(line: str) -> None:
        line = line.rstrip("\n")
        if out.as_json:
            print(line, flush=True)
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            print(line, flush=True)
            return
        print(_event_line(event) if isinstance(event, Mapping) else line, flush=True)

    try:
        with spool.open("r", encoding="utf-8", errors="replace") as handle:
            lines = [line for line in handle if wanted(line)]
            for line in lines[-arguments.lines :]:
                show(line)
            if not arguments.follow:
                return EXIT_OK
            while True:
                line = handle.readline()
                if not line:
                    time.sleep(FOLLOW_POLL_SECONDS)
                    continue
                if wanted(line):
                    show(line)
    except FileNotFoundError:
        print(f"agentctl: no event spool at {spool}", file=sys.stderr)
        return EXIT_REFUSED
    except KeyboardInterrupt:
        return EXIT_OK


def _dispatch(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    verb = arguments.verb
    if verb == "project":
        if arguments.project_verb == "list":
            catalog = config.catalog()
            document = {
                "projects": catalog.list(),
                "unavailable": [
                    {"root": root, "reason": reason}
                    for root, reason in sorted(catalog.unavailable.items())
                ],
            }
            lines = [f"{row['id']:14} {row['root']}" for row in document["projects"]]
            lines.extend(
                f"{'(out of service)':14} {row['root']}: {row['reason']}"
                for row in document["unavailable"]
            )
            out.emit(document, "\n".join(lines) or "(no projects configured)")
            return EXIT_OK
        project = resolve_project(config, arguments.project)
        if arguments.project_verb == "get":
            out.emit(project.catalog_row())
        else:
            rows = [operation.catalog_row() for operation in project.operations]
            out.emit(
                rows,
                table(
                    (
                        "operation",
                        "pool",
                        "result",
                        "timeout",
                        "schedule",
                        "description",
                    ),
                    [
                        (
                            row["name"],
                            row["pool"],
                            row["result"],
                            f"{row['timeout_seconds']}s",
                            row["schedule"] or "-",
                            row["description"],
                        )
                        for row in rows
                    ],
                ),
            )
        return EXIT_OK
    if verb == "job":
        return _job(arguments, config, out)
    if verb == "lane":
        return _lane(arguments, config, out)
    if verb == "refill":
        project = resolve_project(config, arguments.project)
        refilled = lanes.refill(
            config,
            project,
            limit=arguments.limit,
            dry_run=arguments.dry_run,
            backend=arguments.backend,
            model=arguments.model,
            effort=arguments.effort,
        )
        lines = [
            f"{refilled['ready']} ready, {refilled['taken']} taken, "
            f"{len(refilled['candidates'])} candidate(s): {', '.join(refilled['candidates']) or '-'}"
        ]
        if refilled["dry_run"]:
            lines.append("dry run: nothing started")
        lines.extend(
            f"started {row['bead']} on {row['branch']}: {out.job_line(row['job'])}"
            for row in refilled["started"]
        )
        lines.extend(
            f"failed {row['bead']}: {row['error']}" for row in refilled["failed"]
        )
        out.emit(refilled, "\n".join(lines))
        return EXIT_REFUSED if refilled["failed"] else EXIT_OK
    if verb == "view":
        project = resolve_project(config, arguments.project)
        snapshot = operator_view.collect(config, project, now=out.now)
        out.emit(snapshot.to_dict(), operator_view.render(snapshot))
        return EXIT_OK
    if verb == "events":
        return _events(arguments, config, out)
    if verb == "schedule":
        applied = schedule.apply(config)
        lines = [
            f"{row['unit']}.timer {row['project']}:{row['operation']} {row['schedule']}"
            for row in applied["timers"]
        ]
        lines.append(
            f"started {len(applied['started'])}, stopped {len(applied['stopped'])}"
        )
        lines.extend(
            f"(out of service) {row['root']}: {row['reason']}"
            for row in applied["unavailable"]
        )
        out.emit(applied, "\n".join(lines))
        return EXIT_OK
    raise AssertionError(verb)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    out = Output(arguments.json)
    try:
        config = load_config(arguments.config)
        return _dispatch(arguments, config, out)
    except _ERRORS as error:
        message = (
            error.args[0] if isinstance(error, KeyError) and error.args else str(error)
        )
        print(f"agentctl: {message}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
