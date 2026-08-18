from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import sys
from pathlib import Path

from . import health
from .actions import ActionService
from .ambient import product_source
from .feedback import CoalescingTrigger, FeedbackSpool
from .reducer import Reducer, observe_source
from .server import FAILURE_PATH, ensure_token, serve


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


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "emit-failure":
        raise SystemExit(emit_failure_command(sys.argv[2:]))
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
        "--agent-controller",
        default=os.environ.get(
            "SINNIX_AGENT_CONTROLLER",
            "/home/sinity/.config/hermes/skills/agent-orchestration/scripts/agent_job_control.sh",
        ),
    )
    args = parser.parse_args()
    observe_command = list(args.observe_command)
    if len(observe_command) == 1:
        observe_command += ["--format", "json", "--limit", "10"]
    root = args.runtime_dir / "sinnix"
    root.mkdir(parents=True, exist_ok=True)
    token = ensure_token(root / "ops.token")
    reducer = Reducer(
        root / "status.json",
        root / "ops.token",
        observe_source(observe_command),
        args.state_dir / "reducer.json",
        ambient_source=product_source(args.ambient_product),
    )
    reducer.anchor_event_path = args.anchor_events or (root / "afk-resume.json")
    reducer.hyprland_event_path = args.hyprland_events or (root / "hyprland-events")
    actions = ActionService(
        reducer.snapshot,
        args.inventory,
        args.state_dir / "action-receipts.json",
        controller=args.agent_controller,
    )
    elicit = (
        CoalescingTrigger(args.elicit_command.split())
        if args.elicit_command
        else None
    )
    feedback = FeedbackSpool(args.feedback_dir, elicit=elicit)
    fds = list(range(3, 3 + int(os.environ.get("LISTEN_FDS", "0"))))
    serve(
        reducer,
        token,
        fds,
        args.interval,
        actions,
        hub_manifest=args.hub_manifest,
        inventory_path=args.inventory,
        feedback=feedback,
    )
