from __future__ import annotations

import argparse
import os
from pathlib import Path

from .actions import ActionService
from .ambient import product_source
from .feedback import CoalescingTrigger, FeedbackSpool
from .reducer import Reducer, observe_source
from .server import ensure_token, serve


def main() -> None:
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
