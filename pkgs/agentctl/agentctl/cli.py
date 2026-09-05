"""agentctl: an in-process CLI over pueue, worktrunk, gh and bd.

Every verb runs to completion in this process, does what it was told, and
reports.

Output: a read verb (``project``, ``job list|get|logs|result|wait``,
``batch status|list``, ``view``, ``events tail``) prints a table in local
time with an age column, or the document with ``--json``. A write verb
(``job start|fire|cancel|retry|clean``, ``batch start|land|result|resume``,
``schedule apply``, ``backpressure tick``) prints the document as JSON on
stdout and one summary line on stderr. Tables show a run's 8-character
suffix and 8 characters of a commit; ``--full`` prints them whole, and every
verb that takes a run accepts either form.

The project is ``--project``, a leading positional that names a configured
project or a checkout path, or else the checkout enclosing the working
directory.

Exit status, the one table for the package:

  0  done
  1  refused (validation, policy, a missing object) or the action failed
  2  usage
  3  a tool agentctl drives failed (pueue, wt, gh, git, bd, systemd)
  4  the waited job (``job wait``, ``job start --wait``) did not succeed
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
from .projects import ProjectAdapter, ProjectConfigError, ProjectEnvironmentError
from .pueue import PueueError
from .schedule import TimerError
from .worktrunk import WorktrunkError

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_SUBSTRATE = 3
EXIT_JOB_NOT_SUCCEEDED = 4

DEFAULT_WAIT_SECONDS = 3_600
DEFAULT_EVENT_LINES = 40
FOLLOW_POLL_SECONDS = 1.0
SHORT_SHA = 8

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

PROJECT_HELP = "project id or checkout path (default: the checkout enclosing the working directory)"


def _agent_arguments(target: argparse.ArgumentParser) -> None:
    target.add_argument("--backend")
    target.add_argument("--model")
    target.add_argument("--effort")


def _output_arguments(target: argparse.ArgumentParser) -> None:
    """``--json`` and ``--full`` after the verb; the root flags set the defaults."""
    target.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print the document instead of a table",
    )
    target.add_argument(
        "--full",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print complete run ids and commits",
    )


def _project_option(target: argparse.ArgumentParser) -> None:
    target.add_argument("--project", help=PROJECT_HELP)


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
    root.add_argument(
        "--full", action="store_true", help="print complete run ids and commits"
    )
    verbs = root.add_subparsers(dest="verb", required=True)

    project = verbs.add_parser("project", help="the configured project descriptors")
    project_verbs = project.add_subparsers(dest="project_verb", required=True)
    _output_arguments(project_verbs.add_parser("list"))
    for name in ("get", "operations"):
        one = project_verbs.add_parser(name)
        one.add_argument("selector", nargs="?", metavar="project", help=PROJECT_HELP)
        _project_option(one)
        _output_arguments(one)

    job = verbs.add_parser("job", help="declared operations as pueue tasks")
    job_verbs = job.add_subparsers(dest="job_verb", required=True)
    start = job_verbs.add_parser("start")
    start.add_argument(
        "target",
        nargs="+",
        metavar="[project] operation [-- args]",
        help="the operation, optionally preceded by its project; "
        "arguments after -- are appended to the declared exec",
    )
    _project_option(start)
    start.add_argument(
        "--workspace",
        type=Path,
        help="run in this worktree instead of the project root",
    )
    start.add_argument("--wait", action="store_true")
    start.add_argument("--timeout-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    _output_arguments(start)
    fire = job_verbs.add_parser(
        "fire", help="a timer's launch: skipped while the operation is active"
    )
    fire.add_argument("target", nargs="+", metavar="[project] operation")
    _project_option(fire)
    _output_arguments(fire)
    listing = job_verbs.add_parser("list")
    listing.add_argument("--project", help="filter by project id")
    listing.add_argument("--active", action="store_true")
    _output_arguments(listing)
    for name in ("get", "logs", "result", "cancel", "retry"):
        one = job_verbs.add_parser(name)
        one.add_argument("job_id", type=int)
        _output_arguments(one)
    clean = job_verbs.add_parser(
        "clean", help="delete a terminal task and its artifacts (never by age)"
    )
    clean.add_argument("job_id", type=int, nargs="?")
    clean.add_argument("--all-terminal", action="store_true")
    clean.add_argument(
        "--daemon-era",
        action="store_true",
        help="delete the state subtrees no current verb reads",
    )
    _output_arguments(clean)
    wait = job_verbs.add_parser("wait")
    wait.add_argument("job_id", type=int)
    wait.add_argument("--timeout-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    _output_arguments(wait)

    batch_verb = verbs.add_parser(
        "batch", help="several workers on one base commit, landed as one candidate"
    )
    batch_verbs = batch_verb.add_subparsers(dest="batch_verb", required=True)
    batch_start = batch_verbs.add_parser("start")
    batch_start.add_argument(
        "target",
        nargs="*",
        metavar="[project] bead",
        help="seed beads, optionally preceded by the project; "
        "each bead's dispatch group is a worker",
    )
    _project_option(batch_start)
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
    _output_arguments(batch_start)
    for name in ("land", "status"):
        one = batch_verbs.add_parser(name)
        one.add_argument("run_id", help="a run id or its 8-character suffix")
        _project_option(one)
        _output_arguments(one)
    batch_list = batch_verbs.add_parser("list")
    batch_list.add_argument("selector", nargs="?", metavar="project", help=PROJECT_HELP)
    _project_option(batch_list)
    _output_arguments(batch_list)
    batch_result = batch_verbs.add_parser(
        "result", help="file a worker's schema-validated result"
    )
    batch_result.add_argument("run_id", help="a run id or its 8-character suffix")
    batch_result.add_argument("worker_id")
    batch_result.add_argument("path", type=Path)
    _output_arguments(batch_result)
    batch_resume = batch_verbs.add_parser(
        "resume", help="queue a fresh agent into a worker's worktree"
    )
    batch_resume.add_argument("run_id", help="a run id or its 8-character suffix")
    batch_resume.add_argument("--worker", required=True, dest="worker_id")
    _project_option(batch_resume)
    _agent_arguments(batch_resume)
    _output_arguments(batch_resume)

    view = verbs.add_parser("view", help="the operator screen")
    view.add_argument("selector", nargs="?", metavar="project", help=PROJECT_HELP)
    _project_option(view)
    _output_arguments(view)

    events = verbs.add_parser(
        "events", help="the event spool: started and finished tasks, backpressure"
    )
    events_verbs = events.add_subparsers(dest="events_verb", required=True)
    tail = events_verbs.add_parser("tail")
    tail.add_argument("--lines", type=int, default=DEFAULT_EVENT_LINES)
    tail.add_argument("--follow", action="store_true")
    tail.add_argument("--project", help="filter by project id")
    _output_arguments(tail)

    timers = verbs.add_parser("schedule", help="calendar timers for declared schedules")
    timers_verbs = timers.add_subparsers(dest="schedule_verb", required=True)
    _output_arguments(timers_verbs.add_parser("apply"))

    pressure = verbs.add_parser(
        "backpressure", help="freeze or thaw the job queue against host pressure"
    )
    pressure_verbs = pressure.add_subparsers(dest="backpressure_verb", required=True)
    _output_arguments(pressure_verbs.add_parser("tick"))
    return root


class Output:
    """One place that decides what stdout and stderr carry."""

    def __init__(self, *, as_json: bool, full: bool) -> None:
        self.as_json = as_json
        self.full = full
        self.now = datetime.now(UTC)

    def read(self, document: Any, text: str | None = None) -> None:
        """A read: the table a person reads, or the document with ``--json``."""
        if self.as_json or text is None:
            print(json.dumps(document, indent=2, sort_keys=True))
        else:
            print(text)

    def write(self, document: Any, summary: str) -> None:
        """A write: the document on stdout, one summary line on stderr."""
        print(json.dumps(document, indent=2, sort_keys=True))
        print(summary, file=sys.stderr)

    def run(self, run_id: str) -> str:
        return run_id if self.full else batch.short_run_id(run_id)

    def sha(self, value: Any) -> str:
        text = str(value or "")
        if not text:
            return "-"
        return text if self.full else text[:SHORT_SHA]

    def when(self, stamp: str | None, ended: str | None = None) -> str:
        """Local clock and age, e.g. ``14:02 3m``."""
        until = operator_view.parse_stamp(ended) or self.now
        return f"{local_clock(stamp)} {age(stamp, until)}"

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
            ("id", "label", "phase", "started", "age", "exit", "cwd"),
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

    def run_lines(self, document: Mapping[str, Any]) -> str:
        workers = ", ".join(
            f"{worker['id']}[{worker.get('stage') or ('task ' + str(worker.get('task_id')) if worker.get('task_id') is not None else 'external')}]"
            for worker in document["workers"]
        )
        landing = document["landing"]
        return (
            f"run {self.run(document['run_id'])} {document['project']} {document['harness']} "
            f"base {self.sha(document['base_commit'])} stage {document.get('stage', '-')} "
            f"started {self.when(document.get('created_at'))}\n"
            f"workers: {workers}\n"
            f"landing: task {landing.get('task_id')} candidate {self.sha(landing.get('candidate_sha'))}"
            f"{' PR #' + str(landing['pr_number']) if landing.get('pr_number') else ''}"
            f"{' failure ' + landing['failure']['code'] if landing.get('failure') else ''}"
        )

    def runs_table(self, rows: Sequence[Mapping[str, Any]]) -> str:
        if not rows:
            return "(no runs)"
        return table(
            ("run", "harness", "stage", "started", "age", "workers", "candidate"),
            [
                (
                    self.run(row["run_id"]),
                    row["harness"],
                    row["stage"],
                    local_clock(row.get("created_at")),
                    age(row.get("created_at"), self.now),
                    " ".join(f"{w['id']}:{w['stage']}" for w in row["workers"]),
                    self.sha(row["landing"].get("candidate_sha")),
                )
                for row in rows
            ],
        )


def _is_project(config: Config, token: str) -> bool:
    """A configured project id, or a directory holding a descriptor."""
    if token in {row["id"] for row in config.catalog().list()}:
        return True
    return (Path(token).expanduser() / ".agentctl" / "project.toml").is_file()


def _split_target(
    config: Config, explicit: str | None, target: Sequence[str]
) -> tuple[ProjectAdapter, list[str]]:
    """The project and the remaining positionals.

    ``--project`` wins; else a leading positional that names a project is the
    project; else the checkout enclosing the working directory.
    """
    rest = list(target)
    if explicit is None and rest and _is_project(config, rest[0]):
        explicit = rest.pop(0)
    return resolve_project(config, explicit), rest


def _select_project(
    config: Config, explicit: str | None, selector: str | None
) -> ProjectAdapter:
    return resolve_project(config, explicit or selector)


def _job(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    verb = arguments.job_verb
    if verb == "start":
        project, rest = _split_target(config, arguments.project, arguments.target)
        if not rest:
            raise JobError("job start needs an operation")
        operation = project.operation(rest[0])
        started = launch.start_operation(
            config,
            project,
            operation,
            workspace=arguments.workspace,
            extra_argv=(*rest[1:], *getattr(arguments, "extra", [])),
        )
        if arguments.wait:
            started = launch.wait(
                started["job_id"], timeout_seconds=arguments.timeout_seconds
            )
        out.write(started, out.job_line(started))
        if started.get("terminal"):
            return (
                EXIT_OK
                if started.get("phase") == "succeeded"
                else EXIT_JOB_NOT_SUCCEEDED
            )
        return EXIT_OK
    if verb == "fire":
        project, rest = _split_target(config, arguments.project, arguments.target)
        if len(rest) != 1:
            raise JobError("job fire needs exactly one operation")
        fired = launch.fire(config, project, project.operation(rest[0]))
        text = (
            out.job_line(fired)
            if fired.get("fired")
            else f"{fired['label']} not fired: task(s) {fired['active']} still active"
        )
        out.write(fired, text)
        return EXIT_OK
    if verb == "list":
        rows = launch.list_jobs(arguments.project)
        if arguments.active:
            rows = [row for row in rows if not row["terminal"]]
        out.read(rows, out.jobs_table(rows))
        return EXIT_OK
    if verb == "get":
        job = launch.get_job(arguments.job_id, config)
        out.read(job, out.job_line(job))
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
        out.read(result, text)
        return EXIT_OK
    if verb == "cancel":
        job = launch.cancel(config, arguments.job_id)
        out.write(job, f"{out.job_line(job)}; {job['state']}")
        return EXIT_REFUSED if job["state"] == "failed" else EXIT_OK
    if verb == "clean":
        if arguments.daemon_era:
            removed = launch.clean_daemon_era(config)
            out.write(
                removed,
                f"removed {len(removed['removed'])} daemon-era path(s) under {removed['state_dir']}",
            )
            return EXIT_OK
        if arguments.all_terminal:
            rows = launch.clean_terminal(config)
            out.write(rows, f"cleaned {len(rows)} terminal task(s)")
            return EXIT_OK
        if arguments.job_id is None:
            raise JobError("job clean needs a job id, --all-terminal or --daemon-era")
        job = launch.clean(config, arguments.job_id)
        out.write(job, f"{out.job_line(job)}; cleaned")
        return EXIT_OK
    if verb == "retry":
        job = launch.retry(arguments.job_id)
        out.write(job, out.job_line(job))
        return EXIT_OK
    if verb == "wait":
        waited = launch.wait(
            arguments.job_id, timeout_seconds=arguments.timeout_seconds
        )
        out.read(
            waited,
            out.job_line(waited)
            + (" (wait timed out)" if waited.get("wait_timed_out") else ""),
        )
        return EXIT_OK if waited.get("phase") == "succeeded" else EXIT_JOB_NOT_SUCCEEDED
    raise AssertionError(verb)


def _batch(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    verb = arguments.batch_verb
    if verb == "start":
        project, beads = _split_target(config, arguments.project, arguments.target)
        workers = [
            [item.strip() for item in group.split(",") if item.strip()]
            for group in arguments.worker
        ]
        started = batch.start(
            config,
            project,
            beads,
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
        out.write(started, f"{out.run_lines(started)}\n{note}")
        return EXIT_OK
    if verb == "land":
        run_id = batch.resolve_run_id(config, arguments.run_id)
        project = resolve_project(
            config, arguments.project or batch.load(config, run_id).project
        )
        landed = batch.land(config, project, run_id)
        acceptance = landed["acceptance"] or {}
        members = acceptance.get("members", {})
        out.write(
            landed,
            f"{out.run_lines(landed)}\nlanded {out.sha(acceptance.get('candidate_sha'))}: "
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
        run_id = batch.resolve_run_id(config, arguments.run_id)
        project = resolve_project(
            config, arguments.project or batch.load(config, run_id).project
        )
        document = batch.status(config, run_id, project=project)
        out.read(document, out.run_lines(document))
        return EXIT_OK
    if verb == "list":
        project = _select_project(config, arguments.project, arguments.selector)
        rows = [
            batch.status(config, run.run_id, project=project)
            for run in batch.list_runs(config, project.project_id)
        ]
        out.read(rows, out.runs_table(rows))
        return EXIT_OK
    if verb == "result":
        run_id = batch.resolve_run_id(config, arguments.run_id)
        filed = batch.result(config, run_id, arguments.worker_id, arguments.path)
        out.write(
            filed,
            f"recorded result for {arguments.worker_id} in {out.run(run_id)}"
            + (
                " and released the landing task"
                if filed.get("landing_released")
                else ""
            ),
        )
        return EXIT_OK
    if verb == "resume":
        run_id = batch.resolve_run_id(config, arguments.run_id)
        project = resolve_project(
            config, arguments.project or batch.load(config, run_id).project
        )
        resumed = batch.resume(
            config,
            project,
            run_id,
            arguments.worker_id,
            backend=arguments.backend,
            model=arguments.model,
            effort=arguments.effort,
        )
        out.write(
            resumed, f"resumed {arguments.worker_id}: {out.job_line(resumed['job'])}"
        )
        return EXIT_OK
    raise AssertionError(verb)


def _event_line(event: Mapping[str, Any]) -> str:
    stamp = local_clock(event.get("emitted_at"), seconds=True)
    kind = str(event.get("kind") or "")
    if kind == "queue-task":
        label = str(event.get("label") or "")
        task = f" (task {event['task_id']})" if event.get("task_id") is not None else ""
        if event.get("phase") == "started":
            return f"{stamp} {label} started{task}"
        outcome = str(event.get("outcome") or "")
        exit_code = event.get("exit_code")
        return f"{stamp} {label} finished {outcome}{f' exit {exit_code}' if exit_code not in (None, '', '0', 0) else ''}{task}"
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


def _project(arguments: argparse.Namespace, config: Config, out: Output) -> int:
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
        out.read(document, "\n".join(lines) or "(no projects configured)")
        return EXIT_OK
    project = _select_project(config, arguments.project, arguments.selector)
    if arguments.project_verb == "get":
        out.read(project.catalog_row())
        return EXIT_OK
    rows = [operation.catalog_row() for operation in project.operations]
    out.read(
        rows,
        table(
            ("operation", "pool", "result", "timeout", "schedule", "description"),
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


def _dispatch(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    verb = arguments.verb
    if verb == "project":
        return _project(arguments, config, out)
    if verb == "job":
        return _job(arguments, config, out)
    if verb == "batch":
        return _batch(arguments, config, out)
    if verb == "view":
        project = _select_project(config, arguments.project, arguments.selector)
        snapshot = operator_view.collect(config, project, now=out.now)
        out.read(snapshot.to_dict(), operator_view.render(snapshot))
        return EXIT_OK
    if verb == "events":
        return _events(arguments, config, out)
    if verb == "schedule":
        applied = schedule.apply(config)
        out.write(
            applied,
            f"{len(applied['timers'])} timer(s): started {len(applied['started'])}, "
            f"stopped {len(applied['stopped'])}, "
            f"{len(applied['unavailable'])} project(s) out of service",
        )
        return EXIT_OK
    if verb == "backpressure":
        decision = backpressure.tick(spool=config.event_spool)
        out.write(decision, f"backpressure {decision.get('action')}")
        return EXIT_OK
    raise AssertionError(verb)


def main(argv: Sequence[str] | None = None) -> int:
    words = list(sys.argv[1:] if argv is None else argv)
    # Everything after a bare `--` belongs to the operation, wherever the
    # options before it ended up.
    extra: list[str] = []
    if "--" in words:
        cut = words.index("--")
        extra, words = words[cut + 1 :], words[:cut]
    arguments = parser().parse_args(words)
    arguments.extra = extra
    out = Output(as_json=arguments.json, full=arguments.full)
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
