"""agentctl: an in-process CLI over pueue, worktrunk, gh and bd.

Every verb runs to completion in this process, does what it was told, and
reports. Reads print tables in local time; `--json` prints the document.
Exit status: 0 done, 2 refused (usage, validation, policy), 3 a tool agentctl
drives failed (pueue, wt, gh, git, bd), 4 the waited job did not succeed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import backpressure, batch, launch, operator_view, schedule
from .batch import BatchError, BatchRefusal
from .config import Config, ConfigError, load_config, resolve_project
from .github import GithubError
from .launch import JobError
from .operator_view import age, local_clock, table
from .packets import PacketError
from .projects import ProjectConfigError, ProjectEnvironmentError
from .pueue import PueueError
from .schedule import TimerError
from .worktrunk import WorktrunkError

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_USAGE = 2
EXIT_SUBSTRATE = 3
EXIT_JOB_NOT_SUCCEEDED = 4

DEFAULT_WAIT_SECONDS = 3_600
DEFAULT_EVENT_LINES = 40
FOLLOW_POLL_SECONDS = 1.0

_REFUSALS = (
    BatchRefusal,
    ConfigError,
    JobError,
    PacketError,
    ProjectConfigError,
    ProjectEnvironmentError,
    KeyError,
)
_SUBSTRATE_ERRORS = (BatchError, GithubError, PueueError, TimerError, WorktrunkError)


def _agent_arguments(target: argparse.ArgumentParser) -> None:
    target.add_argument("--backend")
    target.add_argument("--model")
    target.add_argument("--effort")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="agentctl",
        description="Jobs over pueue, batches over worktrunk + gh + bd, one operator view.",
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

    batch_verb = verbs.add_parser(
        "batch", help="several workers on one base commit, landed as one candidate"
    )
    batch_verbs = batch_verb.add_subparsers(dest="batch_verb", required=True)
    batch_start = batch_verbs.add_parser("start")
    batch_start.add_argument("project")
    batch_start.add_argument(
        "bead", nargs="*", help="seed beads; each one's dispatch group is a worker"
    )
    batch_start.add_argument(
        "--worker",
        action="append",
        default=[],
        metavar="BEADS",
        help="an explicit worker: comma-separated bead ids, the first leads",
    )
    batch_start.add_argument(
        "--workers",
        choices=batch.HARNESSES,
        default="queued",
        dest="harness",
        help="queued: agentctl runs the workers; external: another harness does",
    )
    _agent_arguments(batch_start)
    for name in ("land", "status"):
        one = batch_verbs.add_parser(name)
        one.add_argument("run_id")
        one.add_argument("--project", help=project_help)
    batch_list = batch_verbs.add_parser("list")
    batch_list.add_argument("project", nargs="?", help=project_help)
    batch_result = batch_verbs.add_parser(
        "result", help="file a worker's schema-validated result"
    )
    batch_result.add_argument("run_id")
    batch_result.add_argument("worker_id")
    batch_result.add_argument("path", type=Path)
    batch_resume = batch_verbs.add_parser(
        "resume", help="queue a fresh agent into a worker's worktree"
    )
    batch_resume.add_argument("run_id")
    batch_resume.add_argument("--worker", required=True, dest="worker_id")
    batch_resume.add_argument("--project", help=project_help)
    _agent_arguments(batch_resume)

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

    pressure = verbs.add_parser(
        "backpressure", help="freeze or thaw the job queue against host pressure"
    )
    pressure_verbs = pressure.add_subparsers(dest="backpressure_verb", required=True)
    pressure_verbs.add_parser("tick")
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
        survivors = job["reaped"]["scope"]["survivors"]
        out.emit(
            job,
            out.job_line(job)
            + (f"; {len(survivors)} processes survived the reap" if survivors else ""),
        )
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


def _run_line(document: Mapping[str, Any]) -> str:
    workers = ", ".join(
        f"{worker['id']}[{worker.get('stage') or ('task ' + str(worker.get('task_id')) if worker.get('task_id') is not None else 'external')}]"
        for worker in document["workers"]
    )
    landing = document["landing"]
    return (
        f"run {document['run_id']} {document['project']} {document['harness']} "
        f"base {document['base_commit'][:12]} stage {document.get('stage', '-')}\n"
        f"workers: {workers}\n"
        f"landing: task {landing.get('task_id')} candidate {str(landing.get('candidate_sha') or '-')[:12]}"
        f"{' PR #' + str(landing['pr_number']) if landing.get('pr_number') else ''}"
        f"{' failure ' + landing['failure']['code'] if landing.get('failure') else ''}"
    )


def _batch(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    verb = arguments.batch_verb
    if verb == "start":
        project = resolve_project(config, arguments.project)
        workers = [
            [item.strip() for item in group.split(",") if item.strip()]
            for group in arguments.worker
        ]
        started = batch.start(
            config,
            project,
            arguments.bead,
            workers=workers or None,
            harness=arguments.harness,
            backend=arguments.backend,
            model=arguments.model,
            effort=arguments.effort,
        )
        note = (
            "already prepared; nothing launched"
            if started.get("existing") and not started.get("resumed")
            else "preparation completed"
            if started.get("resumed")
            else "started"
        )
        out.emit(started, f"{_run_line(started)}\n{note}")
        return EXIT_OK
    if verb == "land":
        project = resolve_project(
            config, arguments.project or _run_project(config, arguments.run_id)
        )
        landed = batch.land(config, project, arguments.run_id)
        acceptance = landed["acceptance"] or {}
        members = acceptance.get("members", {})
        out.emit(
            landed,
            f"{_run_line(landed)}\nlanded {acceptance.get('candidate_sha', '')[:12]}: "
            + ", ".join(
                f"{bead} {state['state']}" for bead, state in sorted(members.items())
            )
            + (
                f"\nresidual: {'; '.join(acceptance['residual'])}"
                if acceptance.get("residual")
                else ""
            ),
        )
        return EXIT_OK
    if verb == "status":
        project = resolve_project(
            config, arguments.project or _run_project(config, arguments.run_id)
        )
        document = batch.status(config, arguments.run_id, project=project)
        out.emit(document, _run_line(document))
        return EXIT_OK
    if verb == "list":
        project = resolve_project(config, arguments.project)
        rows = [
            batch.status(config, run.run_id)
            for run in batch.list_runs(config, project.project_id)
        ]
        out.emit(
            rows,
            table(
                ("run", "harness", "stage", "workers", "candidate"),
                [
                    (
                        row["run_id"],
                        row["harness"],
                        row["stage"],
                        " ".join(f"{w['id']}:{w['stage']}" for w in row["workers"]),
                        str(row["landing"].get("candidate_sha") or "-")[:12],
                    )
                    for row in rows
                ],
            )
            if rows
            else "(no runs)",
        )
        return EXIT_OK
    if verb == "result":
        filed = batch.result(
            config, arguments.run_id, arguments.worker_id, arguments.path
        )
        out.emit(
            filed,
            f"recorded result for {arguments.worker_id} in {arguments.run_id}"
            + (
                " and released the landing task"
                if filed.get("landing_released")
                else ""
            ),
        )
        return EXIT_OK
    if verb == "resume":
        project = resolve_project(
            config, arguments.project or _run_project(config, arguments.run_id)
        )
        resumed = batch.resume(
            config,
            project,
            arguments.run_id,
            arguments.worker_id,
            backend=arguments.backend,
            model=arguments.model,
            effort=arguments.effort,
        )
        out.emit(
            resumed, f"resumed {arguments.worker_id}: {out.job_line(resumed['job'])}"
        )
        return EXIT_OK
    raise AssertionError(verb)


def _run_project(config: Config, run_id: str) -> str:
    return batch.load(config, run_id).project


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
    if verb == "batch":
        return _batch(arguments, config, out)
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
    if verb == "backpressure":
        out.emit(backpressure.tick(spool=config.event_spool))
        return EXIT_OK
    raise AssertionError(verb)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    out = Output(arguments.json)
    try:
        config = load_config(arguments.config)
        return _dispatch(arguments, config, out)
    except _REFUSALS as error:
        message = (
            error.args[0] if isinstance(error, KeyError) and error.args else str(error)
        )
        print(f"agentctl: {message}", file=sys.stderr)
        return EXIT_REFUSED
    except _SUBSTRATE_ERRORS as error:
        print(f"agentctl: {error}", file=sys.stderr)
        return EXIT_SUBSTRATE


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
