"""Prime's answer to the phone.

The phone has two ways to reach prime and they carry identical JSON:

  * the FILE plane -- the app writes intents into its outbox, the wifi-gated
    drain collects them, and `dispatch` executes whatever landed. Always
    correct, cadence-limited to the drain interval;
  * the LIVE plane -- the app POSTs the same object to /phone/v1/* through the
    hub over the tailnet, and `serve` executes it immediately.

One implementation handles both, which is the point. If the live path had its
own execution logic the two planes would drift, and the drift would show up as
"it worked when I was home" -- the least debuggable class of bug.

Idempotency is the send_token. The drain can legitimately deliver the same
intent twice (a transfer whose exit status lied, a re-run after a partial
sweep), and an intent the phone also sent live arrives a second time by
design. Every execution records its token, and a token already seen is a
no-op that still emits its receipt, so the phone's confirmation does not
depend on which delivery won.

No auth, same as the rest of the hub: the tailnet is the boundary. Unlike the
feedback spool this surface does execute things, but everything it can execute
is something the operator's own account could do from a shell on this machine,
and every agent on this host is already root-equivalent.

A third channel lives in this same process, started by the same `serve`
command: the phone's persistent always-on telemetry push (speech, the app's
event mirror) used to be a separate unit, `sinnix-phone-receiver`, listening
on its own tailscale0 TCP port. It moved in here (sinnix-tjqi) because it was
already the dispatcher's sibling in everything but process boundary -- same
host, same tailnet, same "the app connects, prime demuxes" shape -- and a
second always-running Python process bought nothing a second thread did not.
The wire protocol, port, and on-disk lane layout are unchanged; the app was
not touched.

This was `scripts/sinnix-phone-dispatcher` until it moved to
pkgs/sinnix-phone-dispatcher (sinnix-svvz): a real Python package so it can
depend on pkgs/sinnix-capture instead of carrying a private port of its
writer, rather than a `runtimeInputs`-only shell wrapper around one file.
"""

from __future__ import annotations

import argparse
import json
import os

from .dispatch import cmd_dispatch, cmd_notify, cmd_push
from .glance import build_glance, build_steering
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

    push = sub.add_parser(
        "push", help="refresh glance.json and steering.json for the drain"
    )
    push.set_defaults(func=cmd_push)

    notify = sub.add_parser("notify", help="queue an interruption for the phone")
    notify.add_argument("title")
    notify.add_argument("body")
    notify.add_argument("--route")
    notify.set_defaults(func=cmd_notify)

    glance = sub.add_parser("glance", help="print the phone's glance as JSON")
    glance.set_defaults(
        func=lambda _a: (print(json.dumps(build_glance(), indent=2)), 0)[1]
    )

    steering = sub.add_parser(
        "steering", help="print the phone's steering view as JSON"
    )
    steering.set_defaults(
        func=lambda _a: (print(json.dumps(build_steering(), indent=2)), 0)[1]
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
