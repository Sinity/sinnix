"""agentctl: an in-process CLI over pueue, worktrunk, gh and bd.

Every verb runs to completion in this process and prints one JSON document
(or text where a person reads it). There is no daemon and no socket.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from . import lanes, launch, operator_view, schedule
from .config import Config, ConfigError, load_config, resolve_project
from .lanes import LaneError
from .launch import JobError
from .limits import AGENT_MEMORY_MAX
from .packets import PacketError
from .projects import ProjectConfigError, ProjectEnvironmentError
from .pueue import PueueError
from .schedule import TimerError
from .worktrunk import WorktrunkError

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
    target.add_argument(
        "--memory-max",
        default=AGENT_MEMORY_MAX,
        help="MemoryMax of the agent's scope (systemd size, e.g. 10G)",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="agentctl",
        description="Jobs over pueue, lanes over worktrunk + gh + bd, one operator view.",
    )
    root.add_argument("--config", type=Path, help="agentctl.json (default /etc/sinnix/agentctl.json)")
    root.add_argument("--plain", action="store_true", help="print text where a table exists")
    verbs = root.add_subparsers(dest="verb", required=True)

    project = verbs.add_parser("project", help="the configured project descriptors")
    project_verbs = project.add_subparsers(dest="project_verb", required=True)
    project_verbs.add_parser("list")
    get = project_verbs.add_parser("get")
    get.add_argument("project")
    operations = project_verbs.add_parser("operations")
    operations.add_argument("project")

    job = verbs.add_parser("job", help="declared operations as pueue tasks")
    job_verbs = job.add_subparsers(dest="job_verb", required=True)
    start = job_verbs.add_parser("start")
    start.add_argument("project")
    start.add_argument("operation")
    start.add_argument("--workspace", type=Path, help="run in this worktree instead of the project root")
    start.add_argument("--wait", action="store_true")
    start.add_argument("--timeout-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    start.add_argument("extra", nargs="*", help="arguments appended to the declared exec (after --)")
    fire = job_verbs.add_parser("fire", help="a timer's launch: skipped while the operation is active")
    fire.add_argument("project")
    fire.add_argument("operation")
    listing = job_verbs.add_parser("list")
    listing.add_argument("--project")
    listing.add_argument("--active", action="store_true")
    for name in ("get", "logs", "result", "cancel", "retry"):
        one = job_verbs.add_parser(name)
        one.add_argument("job_id", type=int)
    wait = job_verbs.add_parser("wait")
    wait.add_argument("job_id", type=int)
    wait.add_argument("--timeout-seconds", type=int, default=DEFAULT_WAIT_SECONDS)

    lane = verbs.add_parser("lane", help="a worktree with an agent in it and a PR at the end")
    lane_verbs = lane.add_subparsers(dest="lane_verb", required=True)
    lane_start = lane_verbs.add_parser("start")
    lane_start.add_argument("project")
    lane_start.add_argument("bead")
    _agent_arguments(lane_start)
    publish = lane_verbs.add_parser("publish")
    publish.add_argument("path", type=Path)
    publish.add_argument("--bead")
    publish.add_argument("--title")
    publish.add_argument("--body-file", type=Path)
    rebase = lane_verbs.add_parser("rebase")
    rebase.add_argument("project")
    rebase.add_argument("bead")
    _agent_arguments(rebase)
    sync = lane_verbs.add_parser("sync")
    sync.add_argument("project")
    sync.add_argument("--actor", default="agentctl")

    refill = verbs.add_parser("refill", help="start lanes for ready beads without a worktree or PR")
    refill.add_argument("project")
    refill.add_argument("--limit", type=int, default=1)
    refill.add_argument("--dry-run", action="store_true")
    _agent_arguments(refill)

    view = verbs.add_parser("view", help="the operator screen")
    view.add_argument("project")
    view.add_argument("--json", action="store_true")

    events = verbs.add_parser("events", help="the pueue-callback event spool")
    events_verbs = events.add_subparsers(dest="events_verb", required=True)
    tail = events_verbs.add_parser("tail")
    tail.add_argument("--lines", type=int, default=DEFAULT_EVENT_LINES)
    tail.add_argument("--follow", action="store_true")
    tail.add_argument("--project")

    timers = verbs.add_parser("schedule", help="calendar timers for declared schedules")
    timers_verbs = timers.add_subparsers(dest="schedule_verb", required=True)
    timers_verbs.add_parser("apply")
    return root


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _job(arguments: argparse.Namespace, config: Config) -> int:
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
            started = launch.wait(started["job_id"], timeout_seconds=arguments.timeout_seconds)
        _print(started)
        return 0 if started.get("phase") in {"queued", "running", "succeeded"} else 1
    if verb == "fire":
        project = resolve_project(config, arguments.project)
        _print(launch.fire(config, project, project.operation(arguments.operation)))
        return 0
    if verb == "list":
        rows = launch.list_jobs(arguments.project)
        if arguments.active:
            rows = [row for row in rows if not row["terminal"]]
        if arguments.plain:
            for row in rows:
                print(f"{row['job_id']:>5} {row['label'][:48]:48} {row['phase']:14} {row['path']}")
        else:
            _print(rows)
        return 0
    if verb == "get":
        _print(launch.get_job(arguments.job_id))
        return 0
    if verb == "logs":
        sys.stdout.write(launch.logs(config, arguments.job_id))
        return 0
    if verb == "result":
        _print(launch.result(config, arguments.job_id))
        return 0
    if verb == "cancel":
        _print(launch.cancel(config, arguments.job_id))
        return 0
    if verb == "retry":
        _print(launch.retry(arguments.job_id))
        return 0
    if verb == "wait":
        waited = launch.wait(arguments.job_id, timeout_seconds=arguments.timeout_seconds)
        _print(waited)
        return 0 if waited.get("phase") == "succeeded" else 1
    raise AssertionError(verb)


def _lane(arguments: argparse.Namespace, config: Config) -> int:
    verb = arguments.lane_verb
    if verb == "start":
        project = resolve_project(config, arguments.project)
        _print(
            lanes.lane_start(
                config,
                project,
                arguments.bead,
                backend=arguments.backend,
                model=arguments.model,
                effort=arguments.effort,
                memory_max=arguments.memory_max,
            )
        )
        return 0
    if verb == "publish":
        _print(
            lanes.lane_publish(
                config,
                arguments.path,
                bead_id=arguments.bead,
                title=arguments.title,
                body_file=arguments.body_file,
            )
        )
        return 0
    if verb == "rebase":
        project = resolve_project(config, arguments.project)
        _print(
            lanes.lane_rebase(
                config,
                project,
                arguments.bead,
                backend=arguments.backend,
                model=arguments.model,
                effort=arguments.effort,
                memory_max=arguments.memory_max,
            )
        )
        return 0
    if verb == "sync":
        project = resolve_project(config, arguments.project)
        _print(lanes.lane_sync(config, project, actor=arguments.actor))
        return 0
    raise AssertionError(verb)


def _events(arguments: argparse.Namespace, config: Config) -> int:
    spool = config.event_spool
    project = arguments.project

    def wanted(line: str) -> bool:
        return project is None or f'"{project}:' in line or f'"project":"{project}"' in line

    try:
        with spool.open("r", encoding="utf-8", errors="replace") as handle:
            lines = [line.rstrip("\n") for line in handle if wanted(line)]
            for line in lines[-arguments.lines :]:
                print(line)
            if not arguments.follow:
                return 0
            while True:
                line = handle.readline()
                if not line:
                    time.sleep(FOLLOW_POLL_SECONDS)
                    continue
                if wanted(line):
                    print(line.rstrip("\n"), flush=True)
    except FileNotFoundError:
        print(f"no event spool at {spool}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


def _dispatch(arguments: argparse.Namespace, config: Config) -> int:
    verb = arguments.verb
    if verb == "project":
        catalog = config.catalog()
        if arguments.project_verb == "list":
            _print(
                {
                    "projects": catalog.list(),
                    "unavailable": [
                        {"root": root, "reason": reason}
                        for root, reason in sorted(catalog.unavailable.items())
                    ],
                }
            )
            return 0
        project = resolve_project(config, arguments.project)
        if arguments.project_verb == "get":
            _print(project.catalog_row())
        else:
            rows = [operation.catalog_row() for operation in project.operations]
            if arguments.plain:
                for row in rows:
                    print(f"{row['name']:28} {row['pool']:12} {row['result']:7} {row['description']}")
            else:
                _print(rows)
        return 0
    if verb == "job":
        return _job(arguments, config)
    if verb == "lane":
        return _lane(arguments, config)
    if verb == "refill":
        project = resolve_project(config, arguments.project)
        _print(
            lanes.refill(
                config,
                project,
                limit=arguments.limit,
                dry_run=arguments.dry_run,
                backend=arguments.backend,
                model=arguments.model,
                effort=arguments.effort,
            )
        )
        return 0
    if verb == "view":
        project = resolve_project(config, arguments.project)
        snapshot = operator_view.collect(config, project)
        if arguments.json:
            _print(snapshot.to_dict())
        else:
            print(operator_view.render(snapshot))
        return 0
    if verb == "events":
        return _events(arguments, config)
    if verb == "schedule":
        _print(schedule.apply(config))
        return 0
    raise AssertionError(verb)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        config = load_config(arguments.config)
        return _dispatch(arguments, config)
    except _ERRORS as error:
        message = error.args[0] if isinstance(error, KeyError) and error.args else str(error)
        print(f"agentctl: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
