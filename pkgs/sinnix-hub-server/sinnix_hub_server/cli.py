from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
from pathlib import Path

from sinnix_runtime import capabilities, health
from sinnix_runtime import inventory as runtime_inventory
from sinnix_runtime.actions import ActionService
from sinnix_runtime.agent_jobs import AgentCtlClient
from sinnix_runtime.ambient import product_source
from sinnix_runtime.client import UnixConnection
from sinnix_runtime.clodex_usage import clodex_usage
from sinnix_runtime.snapshot import SnapshotBuilder, observe_section

from . import feedback, pages
from .feedback import CoalescingTrigger, FeedbackSpool
from .server import FAILURE_PATH, ensure_token, serve
from .state import StateLayer


def post_failure(
    socket_path: Path,
    unit: str,
    result: str,
    *,
    manager: str | None = None,
) -> bool:
    payload: dict[str, str] = {"unit": unit, "result": result}
    if manager is not None:
        payload["manager"] = manager
    body = json.dumps(payload)
    try:
        connection = UnixConnection(str(socket_path), timeout=5.0)
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
    """`sinnix-hub-server emit-failure` -- what systemd's OnFailure= runs.

    It posts to the hub server first so that one process owns the dedup state; if
    the hub server is down (which is itself a moment when units fail) it writes the
    same transition directly, under the same lock and to the same files, so a
    failure is never lost to the recorder being the thing that failed.
    """
    parser = argparse.ArgumentParser(prog="sinnix-hub-server emit-failure")
    parser.add_argument("--unit", required=True)
    parser.add_argument("--result", default="unknown")
    parser.add_argument("--manager", choices=("user", "system"))
    parser.add_argument(
        "--socket",
        type=Path,
        default=Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
        / "sinnix"
        / "hub.sock",
    )
    parser.add_argument(
        "--inventory", type=Path, default=runtime_inventory.default_path()
    )
    args = parser.parse_args(argv)
    if post_failure(args.socket, args.unit, args.result, manager=args.manager):
        return 0
    runtime, _ = runtime_inventory.load(args.inventory)
    health.emit_failure(args.unit, args.result, runtime or {}, manager=args.manager)
    print(
        f"sinnix-hub-server: recorded {args.unit} failure directly; "
        "the hub server was unreachable",
        file=sys.stderr,
    )
    return 0


def capabilities_command(argv: list[str]) -> int:
    """`sinnix-hub-server capabilities` -- the merged capability index.

    The Nix-generated declarations plus the hub's own routes, on stdout, from
    the process that owns the merge rather than a reimplementation of it.
    """
    parser = argparse.ArgumentParser(prog="sinnix-hub-server capabilities")
    parser.add_argument(
        "--index",
        type=Path,
        default=capabilities.DEFAULT_INDEX,
        help="capability index JSON",
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
    view = pages.capability_view(args.index)
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
    index_status = view.get("index_status") or {}
    print(
        f"Declaration index: {index_status.get('status', 'unavailable')}; {index_status.get('reason', '')}"
    )
    for group in view["groups"]:
        print(f"\n{group['label']} ({len(group['rows'])}) — {group['note']}")
        for row in group["rows"]:
            invoke = row.get("invoke") or ""
            print(f"  {row['name']:<34} {invoke:<34} {row['description']}")
    return 0


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "emit-failure":
        raise SystemExit(emit_failure_command(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "capabilities":
        raise SystemExit(capabilities_command(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        from sinnix_runtime.status import main as status_main

        raise SystemExit(status_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "observe":
        from sinnix_runtime.observe.cli import main as observe_main

        raise SystemExit(observe_main(sys.argv[2:]))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")),
    )
    parser.add_argument("--state-dir", type=Path, default=Path("/realm/state/hub"))
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument(
        "--ambient-product",
        type=Path,
        default=Path(
            os.environ.get(
                "SINNIX_AMBIENT_PRODUCT",
                "/realm/project/shared/analysis/lynchpin/ambient_intelligence.json",
            )
        ),
    )
    parser.add_argument("--anchor-events", type=Path, default=None)
    parser.add_argument("--hyprland-events", type=Path, default=None)
    parser.add_argument(
        "--inventory", type=Path, default=runtime_inventory.default_path()
    )
    parser.add_argument(
        "--feedback-dir",
        type=Path,
        default=Path("/realm/state/hub-feedback"),
        help=(
            "Spool directory for annotations posted to /feedback: one "
            "append-only JSONL file per UTC day, which agents read directly."
        ),
    )
    parser.add_argument(
        "--rank-ingest-command",
        default=None,
        type=feedback.parse_command_argv,
        help=(
            "Command run (coalesced) when a `sinnix rank session` judgment lands "
            "in the feedback spool. Given as a JSON argv array; absent means "
            "nothing is triggered."
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
    root = args.runtime_dir / "sinnix"
    root.mkdir(parents=True, exist_ok=True)
    layer = StateLayer.build(
        runtime_root=root, state_dir=args.state_dir, feedback_dir=args.feedback_dir
    )
    token = ensure_token(layer.token_path)
    agentctl = AgentCtlClient(args.agentctl)
    builder = SnapshotBuilder(
        layer.snapshot_path,
        layer.token_path,
        lambda: observe_section("current"),
        layer.sequence_path,
        section_source=observe_section,
        ambient_source=product_source(args.ambient_product),
        agent_jobs_source=agentctl.snapshot,
        clodex_usage_source=lambda: clodex_usage(args.clodex_usage),
    )
    builder.anchor_event_path = args.anchor_events or (root / "afk-resume.json")
    builder.hyprland_event_path = args.hyprland_events or (root / "hyprland-events")
    actions = ActionService(
        builder.snapshot,
        args.inventory,
        layer.receipts_path,
        agent_jobs=agentctl,
    )
    rank_ingest = (
        CoalescingTrigger(args.rank_ingest_command)
        if args.rank_ingest_command
        else None
    )
    feedback_spool = FeedbackSpool(layer.feedback_spool_dir, rank_ingest=rank_ingest)
    fds = list(range(3, 3 + int(os.environ.get("LISTEN_FDS", "0"))))
    serve(
        builder,
        token,
        fds,
        args.interval,
        actions,
        hub_manifest=args.hub_manifest,
        inventory_path=args.inventory,
        feedback=feedback_spool,
    )
