"""Prime's phone transport and retained-state tools.

The app pushes durable requests and captures over HTTP. Local dispatch handles
retained requests through the same execution boundary. Only verified completed
outcomes acknowledge identical retries; partial or unknown effects stay retained.
The service also owns the phone's always-on telemetry receiver.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .dispatch import cmd_dispatch, cmd_notify
from .glance import build_glance
from .server import cmd_serve
from .state import LAKE_ROOT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser(
        "serve",
        help="the live plane (Unix socket) plus the always-on telemetry receiver (TCP)",
    )
    serve.add_argument(
        "--socket",
        default=os.environ.get(
            "SINNIX_PHONE_DISPATCHER_SOCKET",
            f"{os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')}/sinnix/phone-dispatcher.sock",
        ),
    )
    serve.add_argument(
        "--phone-stream-host",
        default=os.environ.get("SINNIX_PHONE_STREAM_HOST", ""),
        help="tailscale0 bind address for the always-on telemetry receiver (never 0.0.0.0)",
    )
    serve.add_argument(
        "--phone-stream-port",
        type=int,
        default=int(os.environ.get("SINNIX_PHONE_STREAM_PORT", "0") or 0),
    )
    serve.add_argument(
        "--capture-root",
        default=os.environ.get("SINNIX_PHONE_CAPTURE_ROOT", ""),
        help="sinnix.paths.machineRoot -- where phone-<kind> capture lanes are written",
    )
    serve.set_defaults(func=cmd_serve)

    dispatch = sub.add_parser(
        "dispatch", help="the file plane: execute drained intents"
    )
    dispatch.add_argument("--outbox", default=str(LAKE_ROOT / "outbox"))
    dispatch.set_defaults(func=cmd_dispatch)

    notify = sub.add_parser("notify", help="queue an interruption for the phone")
    notify.add_argument("title")
    notify.add_argument("body")
    notify.add_argument("--route")
    notify.set_defaults(func=cmd_notify)

    glance = sub.add_parser("glance", help="print the phone's glance as JSON")
    glance.set_defaults(
        func=lambda _a: (print(json.dumps(build_glance(), indent=2)), 0)[1]
    )

    repair = sub.add_parser(
        "repair-events",
        help="repair a closed event day from device bytes, preserving the old file",
    )
    repair.add_argument("--day", required=True)
    repair.add_argument("--source", type=Path, required=True)
    repair.add_argument("--expected-sha256", required=True)
    repair.set_defaults(func=_repair_events)

    event_status = sub.add_parser(
        "event-status", help="read the bounded retained event tail"
    )
    event_status.add_argument("--file", type=Path)
    event_status.set_defaults(func=_event_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def _repair_events(args: argparse.Namespace) -> int:
    from .uploads import repair_event_day

    print(
        json.dumps(
            repair_event_day(args.day, args.source, args.expected_sha256), indent=2
        )
    )
    return 0


def _event_status(args: argparse.Namespace) -> int:
    from .event_status import read_event_status

    print(json.dumps(read_event_status(args.file)))
    return 0
