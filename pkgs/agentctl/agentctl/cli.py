"""agentctl: an in-process CLI over pueue, worktrunk, gh and bd.

Every verb runs to completion in this process, does what it was told, and
reports.

Reads print tables or JSON; native mutations print JSON and a summary line.
Batch and evidence verbs read retained records only. Worktree cleanup preserves
checkout-only bytes and original history before release.

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
import fcntl
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import (
    evidence,
    job_queries,
    launch,
    operator_view,
    pools,
    pressure,
    worktree_cleanup,
)
from .batch_history import HistoryError, HistoryRefusal, list_runs, load, resolve_run_id
from .config import Config, ConfigError, load_config, resolve_project
from .github import GithubError
from .job_queries import JobError
from .operator_view import DEFAULT_JOB_ROWS, Output, local_clock, table
from .projects import (
    ProjectAdapter,
    ProjectConfigError,
    ProjectEnvironmentError,
    ProjectOperation,
)
from .pueue import PueueError
from .task_reads import TaskReadError
from .worktree_cleanup import CleanupError
from .worktrunk import WorktrunkError

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_SUBSTRATE = 3
EXIT_JOB_NOT_SUCCEEDED = 4

DEFAULT_WAIT_SECONDS = 3_600
DEFAULT_EVENT_LINES = 40
FOLLOW_POLL_SECONDS = 1.0
MAX_EVENT_LINE_BYTES = 1024 * 1024

_REFUSALS = (
    HistoryRefusal,
    ConfigError,
    JobError,
    TaskReadError,
    ProjectConfigError,
    ProjectEnvironmentError,
)
_SUBSTRATE_ERRORS = (
    CleanupError,
    HistoryError,
    GithubError,
    PueueError,
    WorktrunkError,
)

PROJECT_HELP = "project id or checkout path (default: the checkout enclosing the working directory)"


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


def _job_id_option(target: argparse.ArgumentParser) -> None:
    target.add_argument(
        "--job-id",
        help="the job's stable id; addresses the job itself rather than "
        "whatever task id the queue currently keeps it at",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="agentctl",
        description="Native project jobs, preserved worktrees and retained history.",
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

    worktree = verbs.add_parser(
        "worktree", help="preserve and clean terminal owned checkouts"
    )
    worktree_verbs = worktree.add_subparsers(dest="worktree_verb", required=True)
    clean = worktree_verbs.add_parser(
        "clean", help="remove terminal owned checkouts, retaining unpreserved work"
    )
    clean.add_argument("selector", nargs="?", metavar="project", help=PROJECT_HELP)
    clean.add_argument(
        "--path",
        action="append",
        type=Path,
        help="retire only this completed checkout (repeatable)",
    )
    _project_option(clean)
    _output_arguments(clean)

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
    start.add_argument(
        "--idempotency-key",
        help="caller key that makes a repeated launch return the same job",
    )
    start.add_argument(
        "--if-idle",
        action="store_true",
        help="start nothing while the same operation is queued or running "
        "(what a timer runs)",
    )
    _output_arguments(start)
    listing = job_verbs.add_parser(
        "list", help=f"the newest {DEFAULT_JOB_ROWS} tasks, newest first"
    )
    listing.add_argument("--project", help="filter by project id")
    listing.add_argument("--active", action="store_true", help="only unfinished tasks")
    listing.add_argument(
        "--all", action="store_true", help="every task, not just the newest"
    )
    _output_arguments(listing)
    snapshot = job_verbs.add_parser(
        "snapshot", help="bounded groups and jobs from one pueue status response"
    )
    snapshot.add_argument("--limit", type=int, default=DEFAULT_JOB_ROWS)
    _output_arguments(snapshot)
    for name in ("get", "logs", "result", "cancel", "retry"):
        one = job_verbs.add_parser(name)
        one.add_argument("task_id", type=int)
        _job_id_option(one)
        if name in {"get", "logs", "result"}:
            one.add_argument(
                "--attempt", type=int, help="execution attempt (latest by default)"
            )
        if name == "cancel":
            one.add_argument(
                "--actor", help="declared requester; defaults to the OS user"
            )
            one.add_argument(
                "--reason", help="reason retained with cancellation evidence"
            )
            one.add_argument(
                "--expected-attempt",
                type=int,
                help="refuse if the selected launch has advanced to another attempt",
            )
        if name == "get":
            one.add_argument("--attempt-offset", type=int, default=0)
            one.add_argument("--attempt-limit", type=int, default=100)
        if name in {"logs", "result"}:
            one.add_argument(
                "--offset", type=int, default=0, help="byte offset in the artifact"
            )
            one.add_argument(
                "--limit", type=int, default=65536, help="maximum bytes in this page"
            )
        _output_arguments(one)
    clean = job_verbs.add_parser(
        "clean", help="remove a terminal queue task, retaining execution evidence"
    )
    clean.add_argument("task_id", type=int, nargs="?")
    _job_id_option(clean)
    clean.add_argument("--all-terminal", action="store_true")
    clean.add_argument(
        "--worktrees",
        action="store_true",
        help="also retire published checkouts after queue cleanup",
    )
    _output_arguments(clean)
    wait = job_verbs.add_parser("wait")
    wait.add_argument("task_id", type=int)
    _job_id_option(wait)
    wait.add_argument("--timeout-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    _output_arguments(wait)

    history = verbs.add_parser("batch", help="read retained batch history")
    history_verbs = history.add_subparsers(dest="batch_verb", required=True)
    status = history_verbs.add_parser(
        "status", help="read an original run with native job observations"
    )
    status.add_argument("run_id", help="a run id or its suffix")
    _project_option(status)
    _output_arguments(status)
    listing = history_verbs.add_parser("list", help="read retained runs for a project")
    listing.add_argument("selector", nargs="?", metavar="project", help=PROJECT_HELP)
    _project_option(listing)
    _output_arguments(listing)

    native_evidence = verbs.add_parser("evidence", help="read retained native evidence")
    evidence_verbs = native_evidence.add_subparsers(dest="evidence_verb", required=True)
    evidence_list = evidence_verbs.add_parser(
        "list", help="retained evidence of work done outside a batch, for one project"
    )
    evidence_list.add_argument(
        "selector", nargs="?", metavar="project", help=PROJECT_HELP
    )
    evidence_list.add_argument("--cursor")
    evidence_list.add_argument("--limit", type=int, default=evidence.MAX_PAGE_SIZE)
    _project_option(evidence_list)
    _output_arguments(evidence_list)
    evidence_get = evidence_verbs.add_parser(
        "get", help="retrieve one complete evidence record by id"
    )
    evidence_get.add_argument("evidence_id")
    _project_option(evidence_get)
    _output_arguments(evidence_get)

    view = verbs.add_parser("view", help="the operator screen")
    view.add_argument("selector", nargs="?", metavar="project", help=PROJECT_HELP)
    _project_option(view)
    _output_arguments(view)

    events = verbs.add_parser(
        "events", help="the event log: started and finished tasks, pressure pauses"
    )
    events_verbs = events.add_subparsers(dest="events_verb", required=True)
    tail = events_verbs.add_parser("tail")
    tail.add_argument("--lines", type=int, default=DEFAULT_EVENT_LINES)
    tail.add_argument("--follow", action="store_true")
    tail.add_argument("--project", help="filter by project id")
    _output_arguments(tail)

    admission = verbs.add_parser(
        "pools", help="the declared parallelism of every pueue group"
    )
    admission_verbs = admission.add_subparsers(dest="pools_verb", required=True)
    _output_arguments(admission_verbs.add_parser("apply"))

    pause = verbs.add_parser(
        "pressure", help="pause or reopen job groups against memory pressure"
    )
    pause_verbs = pause.add_subparsers(dest="pressure_verb", required=True)
    _output_arguments(pause_verbs.add_parser("tick"))
    return root


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


def _operation(project: ProjectAdapter, name: str) -> ProjectOperation:
    try:
        return project.operation(name)
    except KeyError as error:
        raise JobError(str(error.args[0])) from error


def _report_failure(config: Config, job: Mapping[str, Any]) -> None:
    """After a wait, a job that ended without success gets its failure lines
    and log tail on stderr, so the caller needs no second read."""
    if not job.get("terminal") or job.get("phase") == "succeeded":
        return
    try:
        task = job_queries.read_task(config, job["task_id"], job.get("job_id"))
        lines = job_queries.failure_excerpt(config, task)
    except (JobError, PueueError) as error:
        print(f"(log unavailable: {error})", file=sys.stderr)
        return
    for line in lines:
        print(f"  {line}", file=sys.stderr)
    print(f"  full log: agentctl job logs {job['task_id']}", file=sys.stderr)


def _job(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    verb = arguments.job_verb
    if verb == "start":
        project, rest = _split_target(config, arguments.project, arguments.target)
        if not rest:
            raise JobError("job start needs an operation")
        operation = _operation(project, rest[0])
        if arguments.if_idle and (active := launch.active_tasks(project, operation)):
            skipped = {
                "skipped": True,
                "label": launch.label_for(project.project_id, operation.name),
                "active": active,
            }
            out.write(
                skipped, f"{skipped['label']} skipped: task(s) {active} still active"
            )
            return EXIT_OK
        started = launch.start_operation(
            config,
            project,
            operation,
            workspace=arguments.workspace,
            idempotency_key=arguments.idempotency_key,
            extra_argv=(*rest[1:], *getattr(arguments, "extra", [])),
        )
        if arguments.wait:
            started = job_queries.wait(
                started["task_id"],
                timeout_seconds=arguments.timeout_seconds,
                job_id=started.get("job_id"),
                config=config,
            )
        out.write(started, out.job_line(started))
        _report_failure(config, started)
        if started.get("terminal") or started.get("wait_timed_out"):
            return (
                EXIT_OK
                if started.get("phase") == "succeeded"
                else EXIT_JOB_NOT_SUCCEEDED
            )
        return EXIT_OK
    if verb == "list":
        rows = job_queries.list_jobs(arguments.project)
        if arguments.active:
            rows = [row for row in rows if not row["terminal"]]
        rows.sort(key=lambda row: row["task_id"], reverse=True)
        if not arguments.all:
            rows = rows[:DEFAULT_JOB_ROWS]
        out.read(rows, out.jobs_table(rows))
        return EXIT_OK
    if verb == "snapshot":
        snapshot = job_queries.snapshot_jobs(arguments.limit, config)
        out.read(snapshot, out.jobs_table(snapshot["jobs"]))
        return EXIT_OK
    if verb == "get":
        job = job_queries.get_job(
            arguments.task_id,
            config,
            arguments.job_id,
            attempt=arguments.attempt,
            attempt_offset=arguments.attempt_offset,
            attempt_limit=arguments.attempt_limit,
        )
        out.read(job, out.job_line(job))
        return EXIT_OK
    if verb == "logs":
        page = job_queries.read_job_artifact(
            config,
            arguments.task_id,
            arguments.job_id,
            attempt=arguments.attempt,
            offset=arguments.offset,
            limit=arguments.limit,
        )
        out.read(page, page["text"])
        return EXIT_OK
    if verb == "result":
        result = job_queries.result(
            config,
            arguments.task_id,
            arguments.job_id,
            attempt=arguments.attempt,
            offset=arguments.offset,
            limit=arguments.limit,
        )
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
        job = launch.cancel(
            config,
            arguments.task_id,
            job_id=arguments.job_id,
            expected_attempt=arguments.expected_attempt,
            actor=arguments.actor,
            reason=arguments.reason,
        )
        out.write(job, f"{out.job_line(job)}; {job['state']}")
        return EXIT_REFUSED if job["state"] == "failed" else EXIT_OK
    if verb == "clean":
        if arguments.worktrees and not arguments.all_terminal:
            raise JobError("--worktrees requires --all-terminal")
        if arguments.all_terminal:
            rows = launch.clean_terminal(config)
            if arguments.worktrees:
                print(
                    f"cleaned {len(rows)} terminal queue task(s); checking completed worktrees",
                    file=sys.stderr,
                    flush=True,
                )
                worktrees = worktree_cleanup.clean_published(config)
                failed = any("error" in row for row in worktrees)
                out.write(
                    {
                        "jobs": rows,
                        "queue_cleanup": "completed",
                        "worktrees": worktrees,
                        "worktree_cleanup": "failed" if failed else "completed",
                    },
                    f"cleaned {len(rows)} terminal task(s); worktree cleanup "
                    + ("has failures" if failed else "completed"),
                )
                return EXIT_REFUSED if failed else EXIT_OK
            out.write(rows, f"cleaned {len(rows)} terminal task(s)")
            return EXIT_OK
        if arguments.task_id is None:
            raise JobError("job clean needs a task id or --all-terminal")
        job = launch.clean(config, arguments.task_id, arguments.job_id)
        out.write(job, f"{out.job_line(job)}; cleaned")
        return EXIT_OK
    if verb == "retry":
        job = launch.retry(config, arguments.task_id, arguments.job_id)
        out.write(job, out.job_line(job))
        return EXIT_OK
    if verb == "wait":
        waited = job_queries.wait(
            arguments.task_id,
            timeout_seconds=arguments.timeout_seconds,
            job_id=arguments.job_id,
            config=config,
        )
        out.read(
            waited,
            out.job_line(waited)
            + (" (wait timed out)" if waited.get("wait_timed_out") else ""),
        )
        _report_failure(config, waited)
        return EXIT_OK if waited.get("phase") == "succeeded" else EXIT_JOB_NOT_SUCCEEDED
    raise AssertionError(verb)


def _batch(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    if arguments.batch_verb == "status":
        run_id = resolve_run_id(config, arguments.run_id)
        project = resolve_project(
            config, arguments.project or load(config, run_id).project
        )
        document = operator_view.status(config, run_id, project=project)
        out.read(document, out.run_lines(document))
        return EXIT_OK
    if arguments.batch_verb == "list":
        project = _select_project(config, arguments.project, arguments.selector)
        rows = [
            operator_view.status(config, run.run_id, project=project)
            for run in list_runs(config, project.project_id)
        ]
        out.read(rows, out.runs_table(rows))
        return EXIT_OK
    raise AssertionError(arguments.batch_verb)


def _evidence(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    if arguments.evidence_verb == "list":
        project = _select_project(config, arguments.project, arguments.selector)
        records = evidence.list_records(
            config, project.project_id, cursor=arguments.cursor, limit=arguments.limit
        )
        out.read(records, json.dumps(records, indent=2, sort_keys=True))
        return EXIT_OK
    if arguments.evidence_verb == "get":
        project = resolve_project(config, arguments.project)
        record = evidence.get_record(config, project.project_id, arguments.evidence_id)
        out.read(record, json.dumps(record, indent=2, sort_keys=True))
        return EXIT_OK
    raise AssertionError(arguments.evidence_verb)


def _event_line(event: Mapping[str, Any]) -> str:
    if event.get("kind") == "event-gap":
        return (
            f"event gap: {event.get('reason', 'unavailable')} ({event.get('record_bytes', 'unknown')} bytes); "
            "project/job attribution unavailable"
        )
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
    if kind == pressure.EVENT_KIND:
        return f"{stamp} pressure {event.get('action')} {event.get('group') or ''}".rstrip()
    if kind == "pool-hold":
        excluded = ", ".join(str(pool) for pool in event.get("excluded_by") or ())
        return (
            f"{stamp} {event.get('label')} {event.get('action')} "
            f"(task {event.get('task_id')}, {event.get('pool')} excluded by {excluded})"
        )
    detail = " ".join(
        f"{key}={value}"
        for key, value in sorted(event.items())
        if key not in {"kind", "emitted_at", "schema_version"}
        and not isinstance(value, (dict, list))
    )
    return f"{stamp} {kind} {detail}"


_TAIL_BLOCK_BYTES = 64 * 1024


def _event_gap(reason: str, record_bytes: int) -> str:
    """A reader disposition, not an invented lifecycle event or project."""
    return json.dumps(
        {
            "schema_version": 1,
            "kind": "event-gap",
            "reason": reason,
            "record_bytes": record_bytes,
            "scope": "unattributed",
        },
        separators=(",", ":"),
    )


def _decode_event_line(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return _event_gap("invalid_utf8", len(raw))


def _last_matching_lines(
    handle: Any, count: int, wanted: Callable[[str], bool]
) -> list[str]:
    """The last ``count`` complete lines accepted by ``wanted``, oldest first.

    Reads the file backwards in fixed blocks, so memory is bounded by
    ``count`` lines plus one block regardless of the file's size.
    """
    if count <= 0:
        return []
    handle.seek(0, os.SEEK_END)
    position = handle.tell()
    found: list[str] = []
    carry = b""
    oversized_bytes = 0

    def accept(raw: bytes, size: int) -> None:
        if not size or len(found) == count:
            return
        line = (
            _event_gap("oversized_record", size)
            if size > MAX_EVENT_LINE_BYTES
            else _decode_event_line(raw)
        )
        if size > MAX_EVENT_LINE_BYTES or wanted(line):
            found.append(line)

    while position > 0 and len(found) < count:
        step = min(_TAIL_BLOCK_BYTES, position)
        position -= step
        handle.seek(position)
        block = handle.read(step)
        parts = block.split(b"\n")
        size = len(parts[-1]) + (oversized_bytes or len(carry))
        raw = b"" if oversized_bytes else parts[-1] + carry
        if len(parts) == 1 and position > 0:
            # Keep only the count once a line exceeds the decoding budget.
            carry = raw if size <= MAX_EVENT_LINE_BYTES else b""
            oversized_bytes = size if size > MAX_EVENT_LINE_BYTES else 0
            continue
        accept(raw, size)
        carry, oversized_bytes = b"", 0
        for raw in reversed(parts[1:-1]):
            accept(raw, len(raw))
        if len(parts) > 1:
            if position == 0:
                accept(parts[0], len(parts[0]))
            else:
                carry = parts[0]
    found.reverse()
    return found


def _events(arguments: argparse.Namespace, config: Config, out: Output) -> int:
    spool = config.event_spool
    project = arguments.project
    follow_lock: int | None = None
    if arguments.follow:
        config.state_dir.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256((project or "all").encode()).hexdigest()[:16]
        follow_lock = os.open(
            config.state_dir / f"events-follow-{identity}.lock",
            os.O_CREAT | os.O_RDWR,
            0o600,
        )
        try:
            fcntl.flock(follow_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(follow_lock)
            print(
                "agentctl: an event follow for this project is already running",
                file=sys.stderr,
            )
            return EXIT_REFUSED

    def wanted(line: str) -> bool:
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            return True
        if not isinstance(event, Mapping) or event.get("kind") == "event-gap":
            # A rejected record cannot safely be assigned to a project.
            return True
        if project is None:
            return True
        if isinstance(event.get("project"), str):
            return event["project"] == project
        return str(event.get("label") or "").startswith(project + ":")

    def show(line: str) -> None:
        line = line.rstrip("\n")
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            line = _event_gap("invalid_json", len(line.encode("utf-8")))
            event = json.loads(line)
        if not isinstance(event, Mapping):
            line = _event_gap("non_object_record", len(line.encode("utf-8")))
            event = json.loads(line)
        print(line if out.as_json else _event_line(event), flush=True)

    try:
        with spool.open("rb") as handle:
            # The spool is append-only and unbounded; memory stays at the
            # requested line count however large it grows.
            for line in _last_matching_lines(handle, arguments.lines, wanted):
                show(line)
            if not arguments.follow:
                return EXIT_OK
            handle.seek(0, os.SEEK_END)
            pending = b""
            oversized_bytes = 0
            while True:
                chunk = handle.read(64 * 1024)
                if not chunk:
                    time.sleep(FOLLOW_POLL_SECONDS)
                    continue
                for part in chunk.splitlines(keepends=True):
                    if oversized_bytes:
                        oversized_bytes += len(part)
                        if part.endswith(b"\n"):
                            show(_event_gap("oversized_record", oversized_bytes - 1))
                            oversized_bytes = 0
                        continue
                    size = len(pending) + len(part) - int(part.endswith(b"\n"))
                    if size > MAX_EVENT_LINE_BYTES:
                        pending = b""
                        if part.endswith(b"\n"):
                            show(_event_gap("oversized_record", size))
                        else:
                            oversized_bytes = size
                        continue
                    pending += part
                    if pending.endswith(b"\n"):
                        line = _decode_event_line(pending[:-1])
                        pending = b""
                        if wanted(line):
                            show(line)
    except FileNotFoundError:
        print(f"agentctl: no event spool at {spool}", file=sys.stderr)
        return EXIT_REFUSED
    except KeyboardInterrupt:
        return EXIT_OK
    finally:
        if follow_lock is not None:
            os.close(follow_lock)


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
            ("operation", "pool", "result", "timeout", "description"),
            [
                (
                    row["name"],
                    row["pool"],
                    row["result"],
                    (
                        f"{row['timeout_seconds']}s"
                        if row["timeout_seconds"]
                        else "until cancelled"
                    ),
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
    if verb == "worktree":
        if arguments.worktree_verb == "clean":
            project = _select_project(config, arguments.project, arguments.selector)
            cleaned = (
                worktree_cleanup.clean(config, project, paths=arguments.path)
                if arguments.path
                else worktree_cleanup.clean(config, project)
            )
            kept = [f"{row['branch']}: {row['reason']}" for row in cleaned["kept"]]
            out.write(
                cleaned,
                f"removed {len(cleaned['removed'])} worktree(s)"
                + (f"\nkept: {'; '.join(kept)}" if kept else ""),
            )
            return EXIT_OK
        raise AssertionError(arguments.worktree_verb)
    if verb == "batch":
        return _batch(arguments, config, out)
    if verb == "evidence":
        return _evidence(arguments, config, out)
    if verb == "view":
        project = _select_project(config, arguments.project, arguments.selector)
        snapshot = operator_view.collect(config, project, now=out.now)
        out.read(snapshot.to_dict(), operator_view.render(snapshot))
        return EXIT_OK
    if verb == "events":
        return _events(arguments, config, out)
    if verb == "pools":
        if not config.pools:
            raise ConfigError(f"{config.config_path} declares no pools")
        applied = pools.apply(config.pools)
        out.write(
            applied,
            f"pools: created {len(applied['created'])}, "
            f"resized {len(applied['resized'])}, "
            f"unchanged {len(applied['unchanged'])}",
        )
        return EXIT_OK
    if verb == "pressure":
        checkpoint = config.state_dir / "pressure-state.json"
        decision = pressure.tick(
            spool=config.event_spool, checkpoint=checkpoint, pools=config.pools
        )
        holds = (
            launch.release_holds(config)
            if decision.get("action") in {"hold", "clear"}
            else {"released": [], "waiting": []}
        )
        decision = {
            **decision,
            "holds_released": holds["released"],
            "holds_waiting": holds["waiting"],
        }
        summary = f"pressure {decision.get('action')}"
        if holds["released"] or holds["waiting"]:
            summary += (
                f"; pool holds: released {len(holds['released'])}, "
                f"waiting {len(holds['waiting'])}"
            )
        out.write(decision, summary)
        return EXIT_OK
    raise AssertionError(verb)


def main(argv: Sequence[str] | None = None) -> int:
    words = list(sys.argv[1:] if argv is None else argv)
    # Job start forwards arguments after a bare `--` to its operation,
    # wherever the options before it ended up. Other verbs reject them.
    extra: list[str] = []
    if "--" in words:
        cut = words.index("--")
        extra, words = words[cut + 1 :], words[:cut]
    command_parser = parser()
    arguments = command_parser.parse_args(words)
    if extra and not (arguments.verb == "job" and arguments.job_verb == "start"):
        command_parser.error("arguments after -- are only supported by job start")
    arguments.extra = extra
    out = Output(as_json=arguments.json, full=arguments.full)
    try:
        config = load_config(arguments.config)
        return _dispatch(arguments, config, out)
    except _REFUSALS as error:
        _report_error(error, out)
        return EXIT_REFUSED
    except _SUBSTRATE_ERRORS as error:
        _report_error(error, out)
        return EXIT_SUBSTRATE


def _report_error(error: Exception, out: Output) -> None:
    """Keep retained recovery work visible in either CLI representation."""
    run_id = getattr(error, "run_id", None)
    unprovisioned = getattr(error, "unprovisioned", [])
    rows = [row for row in unprovisioned if isinstance(row, Mapping)]
    if out.as_json:
        document: dict[str, Any] = {"error": str(error)}
        if isinstance(run_id, str) and run_id:
            document["retained_run"] = run_id
        if rows:
            document["unprovisioned"] = [dict(row) for row in rows]
        print(json.dumps(document, sort_keys=True))
        return
    print(f"agentctl: {error}", file=sys.stderr)
    if isinstance(run_id, str) and run_id:
        print(f"agentctl: retained run {run_id}", file=sys.stderr)
    for row in rows:
        worker = row.get("worker") or row.get("id") or "worker"
        beads = ", ".join(str(bead) for bead in row.get("beads") or [])
        reason = row.get("reason") or "unprovisioned"
        suffix = f" ({beads})" if beads else ""
        print(f"agentctl: pending {worker}{suffix}: {reason}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
