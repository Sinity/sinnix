from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from . import capabilities, feedback, health, pages
from .actions import ActionService
from .agent_jobs import AgentCtlClient, AgentCtlError
from .ambient import product_source
from .clodex_usage import clodex_usage
from .feedback import CoalescingTrigger, FeedbackSpool
from .reducer import Reducer, observe_source
from .server import FAILURE_PATH, ensure_token, serve
from .state import StateLayer


class UnixConnection(http.client.HTTPConnection):
    """HTTP over the reducer's Unix socket, so the fast path speaks to the
    running process rather than to its state file behind its back."""

    def __init__(self, path: str, timeout: float = 5.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self.path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def lane_views(
    agentctl: AgentCtlClient,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Every project's `agentctl view`, with the projects that refused named."""
    views: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        projects = agentctl.projects()
    except AgentCtlError as error:
        return views, [str(error)]
    for project in projects:
        try:
            views.append(agentctl.view(project))
        except AgentCtlError as error:
            errors.append(f"{project}: {error}")
    return views, errors


def post_failure(socket_path: Path, unit: str, result: str) -> bool:
    body = json.dumps({"unit": unit, "result": result})
    try:
        connection = UnixConnection(str(socket_path))
        connection.request(
            "POST", FAILURE_PATH, body, {"Content-Type": "application/json"}
        )
        response = connection.getresponse()
        response.read()
        return response.status < 400
    except (OSError, http.client.HTTPException):
        return False
    finally:
        try:
            connection.close()
        except (OSError, NameError, UnboundLocalError):
            pass


def emit_failure_command(argv: list[str]) -> int:
    """`sinnix-ops-reducer emit-failure` -- what systemd's OnFailure= runs.

    It posts to the reducer first so that one process owns the dedup state; if
    the reducer is down (which is itself a moment when units fail) it writes the
    same transition directly, under the same lock and to the same files, so a
    failure is never lost to the recorder being the thing that failed.
    """
    parser = argparse.ArgumentParser(prog="sinnix-ops-reducer emit-failure")
    parser.add_argument("--unit", required=True)
    parser.add_argument("--result", default="unknown")
    parser.add_argument(
        "--socket",
        type=Path,
        default=Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
        / "sinnix"
        / "ops.sock",
    )
    parser.add_argument(
        "--inventory", type=Path, default=Path("/etc/sinnix/runtime-inventory.json")
    )
    args = parser.parse_args(argv)
    if post_failure(args.socket, args.unit, args.result):
        return 0
    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        inventory = {}
    health.emit_failure(args.unit, args.result, inventory)
    print(
        f"sinnix-ops-reducer: recorded {args.unit} failure directly; "
        "the reducer was unreachable",
        file=sys.stderr,
    )
    return 0


def capabilities_command(argv: list[str]) -> int:
    """`sinnix-ops-reducer capabilities` -- the merged capability index.

    The same view the hub's /capabilities/ page renders, on stdout, so a
    consumer that is not a browser (`sinnix cheatsheet`, an agent, a shell) gets
    it from the process that owns the merge rather than re-implementing the join
    against the raw files.
    """
    parser = argparse.ArgumentParser(prog="sinnix-ops-reducer capabilities")
    parser.add_argument(
        "--index",
        type=Path,
        default=capabilities.DEFAULT_INDEX,
        help="capability index JSON",
    )
    parser.add_argument(
        "--census",
        type=Path,
        default=capabilities.DEFAULT_CENSUS,
        help="usage census JSONL joined onto the rows",
    )
    parser.add_argument(
        "--kind", action="append", help="restrict to one kind (repeatable)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the merged view as JSON instead of a table",
    )
    args = parser.parse_args(argv)
    view = pages.capability_view(args.index, args.census)
    if args.kind:
        wanted = set(args.kind)
        view["groups"] = [group for group in view["groups"] if group["kind"] in wanted]
        view["rows"] = [row for row in view["rows"] if row.get("kind") in wanted]
    if args.json:
        json.dump(view, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    if not view["groups"]:
        print(
            f"no capability index at {args.index}; this host was built before it existed",
            file=sys.stderr,
        )
        return 1
    for group in view["groups"]:
        print(f"\n{group['label']} ({len(group['rows'])}) — {group['note']}")
        for row in group["rows"]:
            invoke = row.get("invoke") or ""
            verdict = (row.get("census") or {}).get("verdict") or ""
            print(
                f"  {row['name']:<34} {invoke:<34} {verdict:<18} {row['description']}"
            )
    return 0


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "emit-failure":
        raise SystemExit(emit_failure_command(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "capabilities":
        raise SystemExit(capabilities_command(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "orient":
        from .orient import main as orient_main

        raise SystemExit(orient_main(sys.argv[2:]))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")),
    )
    parser.add_argument(
        "--state-dir", type=Path, default=Path("/realm/state/sinnix-ops")
    )
    parser.add_argument(
        "--observe-command",
        nargs="+",
        default=["sinnix-observe", "--format", "json", "--limit", "10"],
    )
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument(
        "--ambient-product",
        type=Path,
        default=Path(
            os.environ.get(
                "SINNIX_AMBIENT_PRODUCT",
                "/realm/project/sinity-lynchpin/.lynchpin/generated/analysis/ambient_intelligence.json",
            )
        ),
    )
    parser.add_argument("--anchor-events", type=Path, default=None)
    parser.add_argument("--hyprland-events", type=Path, default=None)
    parser.add_argument(
        "--inventory", type=Path, default=Path("/etc/sinnix/runtime-inventory.json")
    )
    parser.add_argument(
        "--feedback-dir",
        type=Path,
        default=Path("/realm/data/derived/hub-feedback"),
        help=(
            "Spool directory for annotations posted to /feedback: one "
            "append-only JSONL file per UTC day, which agents read directly."
        ),
    )
    parser.add_argument(
        "--elicit-command",
        default=None,
        help=(
            "Command run (coalesced) when a sinnix-elicit record lands in the "
            "feedback spool, replacing the periodic drain. Given as a full "
            "argv, space-separated; absent means nothing is triggered."
        ),
    )
    parser.add_argument(
        "--elicit-model-dir",
        type=Path,
        default=feedback.ELICIT_MODEL_DIR_DEFAULT,
        help=(
            "sinnix-elicit's own preferences root (its --items/rank state, one "
            "directory per domain). Read-only: GET /feedback/elicit/<domain> "
            "serves that domain's latest model.json back, so an elicit "
            "comparison session can preview 'learning so far' mid-session."
        ),
    )
    parser.add_argument(
        "--hub-manifest",
        type=Path,
        default=None,
        help=(
            "Nix-generated hub manifest (routes, AI roster, frontends) the "
            "server-rendered pages read; absent means a host with no hub, "
            "whose pages still render from the inventory and the snapshot."
        ),
    )
    parser.add_argument(
        "--capability-index",
        type=Path,
        default=capabilities.DEFAULT_INDEX,
        help=(
            "Nix-generated capability index the /capabilities/ page renders: "
            "every declared feature, service, script, command, skill, lane, MCP "
            "server and agent lane, with how to invoke it."
        ),
    )
    parser.add_argument(
        "--usage-census",
        type=Path,
        default=capabilities.DEFAULT_CENSUS,
        help=(
            "Weekly usage census JSONL (sinnix-census), joined onto the "
            "capability rows so a capability nothing has ever used says so."
        ),
    )
    parser.add_argument(
        "--agentctl",
        default=os.environ.get(
            "SINNIX_AGENTCTL",
            "agentctl",
        ),
    )
    parser.add_argument(
        "--clodex-usage",
        type=Path,
        default=None,
        help="Clodex routed inference accounting JSONL",
    )
    args = parser.parse_args()
    observe_command = list(args.observe_command)
    if len(observe_command) == 1:
        observe_command += ["--format", "json", "--limit", "10"]
    root = args.runtime_dir / "sinnix"
    root.mkdir(parents=True, exist_ok=True)
    layer = StateLayer.build(
        runtime_root=root, state_dir=args.state_dir, feedback_dir=args.feedback_dir
    )
    token = ensure_token(layer.token_path)
    agentctl = AgentCtlClient(args.agentctl)
    reducer = Reducer(
        layer.snapshot_path,
        layer.token_path,
        observe_source(observe_command),
        layer.reducer_state_path,
        ambient_source=product_source(args.ambient_product),
        agent_jobs_source=agentctl.snapshot,
        clodex_usage_source=lambda: clodex_usage(args.clodex_usage),
    )
    reducer.anchor_event_path = args.anchor_events or (root / "afk-resume.json")
    reducer.hyprland_event_path = args.hyprland_events or (root / "hyprland-events")
    actions = ActionService(
        reducer.snapshot,
        args.inventory,
        layer.receipts_path,
        agent_jobs=agentctl,
    )
    elicit = (
        CoalescingTrigger(args.elicit_command.split()) if args.elicit_command else None
    )
    feedback_spool = FeedbackSpool(layer.feedback_spool_dir, elicit=elicit)
    fds = list(range(3, 3 + int(os.environ.get("LISTEN_FDS", "0"))))
    serve(
        reducer,
        token,
        fds,
        args.interval,
        actions,
        hub_manifest=args.hub_manifest,
        inventory_path=args.inventory,
        feedback=feedback_spool,
        elicit_model_dir=args.elicit_model_dir,
        capability_index_path=args.capability_index,
        usage_census_path=args.usage_census,
        lanes_source=lambda: lane_views(agentctl),
    )
