"""``sinnix state`` and ``sinnix estimate``: the state document in a terminal.

``sinnix state`` reads the document the hub server already computed. It never
moves the "last looked" time: that advances only when the operator opens the
panel or the page.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..status import default_socket_path, fetch_socket_json
from . import sources
from .engine import range_text
from .history import SIZES, estimate_range, summarize
from .service import AGENTCTL_CONFIG, OperatorState
from .text import render_text

MEMORY_PATH = Path("/realm/state/hub/operator-state.json")


def local_service(agentctl_config: Path = AGENTCTL_CONFIG) -> OperatorState:
    """The same engine in this process, for a host whose hub is not running."""
    from ..agent_jobs import AgentCtlClient

    service = OperatorState(
        MEMORY_PATH, jobs=AgentCtlClient().snapshot, agentctl_config=agentctl_config
    )
    service._save = lambda: None  # type: ignore[method-assign]  # a reader writes nothing
    service.refresh_all()
    return service


def state_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sinnix state",
        description="What is running, what waits on the operator, what failed and what finished, across all registered projects.",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the state document as JSON"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="compute in this process instead of asking the hub server (slow)",
    )
    parser.add_argument("--socket", type=Path, default=default_socket_path())
    parser.add_argument(
        "--agentctl-config",
        type=Path,
        default=AGENTCTL_CONFIG,
        help="with --local: the agentctl config that lists the projects",
    )
    args = parser.parse_args(argv)
    state: dict[str, Any] | None = None
    if not args.local:
        state = fetch_socket_json(args.socket, "/v1/state", timeout=20)
        if state is None:
            print(
                "sinnix state: the hub server did not answer; computing locally",
                file=sys.stderr,
            )
    if state is None:
        state = local_service(args.agentctl_config).current()
    if args.json:
        print(json.dumps(state, sort_keys=True))
    else:
        sys.stdout.write(render_text(state))
    return 0


def estimate_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sinnix estimate",
        description="How long work like this has taken before, with the number of past samples behind each range.",
    )
    verbs = parser.add_subparsers(dest="verb", required=True)
    task = verbs.add_parser("range", help="closed tasks of one kind and size")
    task.add_argument(
        "kind",
        help="kind of work: a kind: label value or an issue type (bug, feature, task, ...); 'any' for all",
    )
    task.add_argument("size", choices=(*SIZES, "any"))
    task.add_argument("--project", help="only this project's closed tasks")
    job = verbs.add_parser(
        "job",
        help="one declared operation, from the job log and the task-runner history",
    )
    job.add_argument("project")
    job.add_argument("operation")
    for verb in (task, job):
        verb.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.verb == "range":
        samples: list[dict[str, Any]] = []
        errors = []
        for project in sources.registered_projects(AGENTCTL_CONFIG):
            if args.project and project["id"] != args.project:
                continue
            if not (Path(project["root"]) / ".beads").exists():
                continue
            try:
                samples += sources.closed_bead_samples(
                    project["id"], project["root"], now
                )
            except Exception as error:
                errors.append(f"{project['id']}: {error}")
        result = estimate_range(
            samples,
            None if args.kind == "any" else args.kind,
            None if args.size == "any" else args.size,
        )
        result["errors"] = errors
        if args.json:
            print(json.dumps(result, sort_keys=True))
            return 0
        print(
            f"Tasks of kind {args.kind}, size {args.size}, closed in the last {sources.CLOSED_BEADS_DAYS} days:"
        )
        print(f"  claim to close:   {range_text(result['claim_to_close'])}")
        print(f"  created to close: {range_text(result['created_to_close'])}")
        if result.get("fallback"):
            print(f"  note: {result['fallback']}")
        for key in ("claim_to_close",):
            if result[key].get("note"):
                print(f"  note: {result[key]['note']}")
        print(
            f"  {result['size_labelled_samples']} of these carry a size: label; "
            "the others are sized from their single estimate in minutes"
        )
        for error in errors:
            print(f"  unavailable: {error}")
        return 0
    from .history import JobLog, TaskRunnerHistory
    from .service import TASK_RUNNER_HISTORY

    label = f"{args.project}:{args.operation}"
    config = json.loads(AGENTCTL_CONFIG.read_text(encoding="utf-8"))
    log = JobLog(Path(config["event_spool"]))
    log.refresh()
    runner = TaskRunnerHistory(TASK_RUNNER_HISTORY)
    runner.refresh()
    result = {
        "label": label,
        "job_log": summarize(
            log.run_seconds.get(label) or [],
            f"successful runs of {label} in the job log",
        ),
        "task_runner": summarize(
            runner.run_seconds.get(label) or [], f"passed task-runner runs of {label}"
        ),
    }
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"{label}:")
        print(f"  job log:     {range_text(result['job_log'])}")
        print(f"  task runner: {range_text(result['task_runner'])}")
    return 0
