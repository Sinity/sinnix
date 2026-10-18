"""Executing intents that reached prime as files, and queuing an
operator-initiated notification.

The glance writer that used to live here is gone with the drain that
read it: the glance is built on request now, by the route the app fetches (see
inbox.py). `dispatch` stays as the repair verb for intents already sitting in
the lake's outbox -- the app posts them to /intent itself."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

from .execute import execute
from .inbox import confirm_directory_entry
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
        directory = os.open(outbox, os.O_RDONLY | os.O_DIRECTORY)
    except FileNotFoundError:
        print(f"dispatch: no outbox at {outbox}")
        return 0
    except OSError as exc:
        print(f"dispatch: outbox unavailable at {outbox} ({exc})", file=sys.stderr)
        return 1
    try:
        return _dispatch_directory(directory)
    finally:
        os.close(directory)


def _dispatch_directory(directory: int) -> int:
    try:
        with os.scandir(directory) as entries:
            paths = sorted(
                entry.name
                for entry in entries
                if fnmatch.fnmatchcase(entry.name, "intent-*.json")
            )
    except OSError as exc:
        print(f"dispatch: outbox listing unavailable ({exc})", file=sys.stderr)
        return 1
    executed = 0
    failed = 0
    for path in paths:
        try:
            with open(
                path,
                "rb",
                opener=lambda name, flags: os.open(
                    name, flags | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory
                ),
            ) as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError("intent must be a regular file")
                body = source.read()
                intent = json.loads(body.decode("utf-8"))
            if not isinstance(intent, dict):
                raise ValueError("intent must be a JSON object")
        except (OSError, ValueError) as exc:
            # Left in place, loudly. A malformed intent is a bug worth seeing,
            # and deleting the evidence would make it a bug nobody can see.
            print(f"dispatch: {path} is not readable JSON ({exc})", file=sys.stderr)
            failed += 1
            continue
        result = execute(intent)
        if result.get("ok"):
            try:
                _, consumed = confirm_directory_entry(
                    path, path, hashlib.sha256(body).hexdigest(), directory, directory
                )
            except OSError as exc:
                consumed = {"ok": False, "detail": str(exc)}
            if consumed.get("ok"):
                executed += 1
            else:
                print(
                    f"dispatch: {path} completed but not consumed: {consumed}",
                    file=sys.stderr,
                )
                failed += 1
        else:
            print(
                f"dispatch: {path} {result.get('outcome')}: {result.get('detail')}",
                file=sys.stderr,
            )
            failed += 1
    print(f"dispatch: executed {executed}, kept {failed}")
    return 1 if failed else 0


def cmd_notify(args: argparse.Namespace) -> int:
    notify_phone(args.title, args.body, args.route)
    print("notify: queued for the next drain")
    return 0
