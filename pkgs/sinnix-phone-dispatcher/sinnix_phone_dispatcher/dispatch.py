"""Executing intents that reached prime as files, and queuing an
operator-initiated notification.

The glance/steering writer that used to live here is gone with the drain that
read it: both are built on request now, by the routes the app fetches (see
inbox.py). `dispatch` stays as the repair verb for intents already sitting in
the lake's outbox -- the app posts them to /intent itself."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import stat
import sys
from pathlib import Path

from .execute import execute
from .state import ensure_dirs, notify_phone


def cmd_dispatch(args: argparse.Namespace) -> int:
    """Execute every intent the drain collected.

    A file is deleted only when execute() answers `ok`: a completed effect,
    this time or an earlier one under the same token. Every other outcome --
    failed, partial, indeterminate, a token conflict -- keeps the file and
    fails the run, because the file is the only record of what was asked.
    A crash mid-sweep therefore repeats a request rather than losing it, and
    the token ledger decides whether a repeat may act.
    """
    ensure_dirs()
    outbox = Path(args.outbox)
    try:
        # scandir reports access/type failures; Path.glob can hide them as an
        # empty sweep, which would incorrectly claim the retained work ran.
        with os.scandir(outbox) as entries:
            paths = sorted(
                outbox / entry.name
                for entry in entries
                if fnmatch.fnmatchcase(entry.name, "intent-*.json")
            )
    except FileNotFoundError:
        print(f"dispatch: no outbox at {outbox}")
        return 0
    except OSError as exc:
        print(f"dispatch: outbox unavailable at {outbox} ({exc})", file=sys.stderr)
        return 1
    executed = 0
    failed = 0
    for path in paths:
        try:
            with open(
                path,
                encoding="utf-8",
                opener=lambda name, flags: os.open(
                    name, flags | os.O_NONBLOCK | os.O_NOFOLLOW
                ),
            ) as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError("intent must be a regular file")
                intent = json.load(source)
            if not isinstance(intent, dict):
                raise ValueError("intent must be a JSON object")
        except (OSError, ValueError) as exc:
            # Left in place, loudly. A malformed intent is a bug worth seeing,
            # and deleting the evidence would make it a bug nobody can see.
            print(
                f"dispatch: {path.name} is not readable JSON ({exc})", file=sys.stderr
            )
            failed += 1
            continue
        result = execute(intent)
        if result.get("ok"):
            path.unlink(missing_ok=True)
            executed += 1
        else:
            print(
                f"dispatch: {path.name} {result.get('outcome')}: {result.get('detail')}",
                file=sys.stderr,
            )
            failed += 1
    print(f"dispatch: executed {executed}, kept {failed}")
    return 1 if failed else 0


def cmd_notify(args: argparse.Namespace) -> int:
    notify_phone(args.title, args.body, args.route)
    print("notify: queued for the next drain")
    return 0
