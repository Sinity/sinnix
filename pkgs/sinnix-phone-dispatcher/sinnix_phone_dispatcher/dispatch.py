"""Executing intents that reached prime as files, and queuing an
operator-initiated notification.

The glance/steering writer that used to live here is gone with the drain that
read it: both are built on request now, by the routes the app fetches (see
inbox.py). `dispatch` stays as the repair verb for intents already sitting in
the lake's outbox -- the app posts them to /intent itself."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .execute import execute
from .state import ensure_dirs, notify_phone


def cmd_dispatch(args: argparse.Namespace) -> int:
    """Execute every intent the drain collected.

    Intents are deleted only after execution, and execution is idempotent, so
    the failure mode of a crash mid-sweep is a repeat rather than a loss.
    """
    ensure_dirs()
    outbox = Path(args.outbox)
    if not outbox.is_dir():
        print(f"dispatch: no outbox at {outbox}")
        return 0
    executed = 0
    failed = 0
    for path in sorted(outbox.glob("intent-*.json")):
        try:
            intent = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # Left in place, loudly. A malformed intent is a bug worth seeing,
            # and deleting the evidence would make it a bug nobody can see.
            print(
                f"dispatch: {path.name} is not readable JSON ({exc})", file=sys.stderr
            )
            failed += 1
            continue
        result = execute(intent)
        if result.get("ok") or result.get("duplicate"):
            path.unlink(missing_ok=True)
            executed += 1
        else:
            print(
                f"dispatch: {path.name} failed: {result.get('detail')}", file=sys.stderr
            )
            failed += 1
    print(f"dispatch: executed {executed}, failed {failed}")
    return 0


def cmd_notify(args: argparse.Namespace) -> int:
    notify_phone(args.title, args.body, args.route)
    print("notify: queued for the next drain")
    return 0
