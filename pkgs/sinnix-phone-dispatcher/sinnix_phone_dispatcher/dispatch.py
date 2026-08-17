"""The file plane: executing drained intents, refreshing the state files the
drain pushes to the phone, and queuing an operator-initiated notification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .execute import execute
from .glance import build_glance, build_steering
from .state import INBOX_DIR, ensure_dirs, notify_phone


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
            print(f"dispatch: {path.name} is not readable JSON ({exc})", file=sys.stderr)
            failed += 1
            continue
        result = execute(intent)
        if result.get("ok") or result.get("duplicate"):
            path.unlink(missing_ok=True)
            executed += 1
        else:
            print(f"dispatch: {path.name} failed: {result.get('detail')}", file=sys.stderr)
            failed += 1
    print(f"dispatch: executed {executed}, failed {failed}")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    """Refresh the state files the drain pushes to the phone."""
    ensure_dirs()
    for name, builder in (("glance.json", build_glance), ("steering.json", build_steering)):
        target = INBOX_DIR / name
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_text(json.dumps(builder(), indent=2) + "\n", encoding="utf-8")
        tmp.rename(target)
        print(f"push: wrote {target}")
    return 0


def cmd_notify(args: argparse.Namespace) -> int:
    notify_phone(args.title, args.body, args.route)
    print("notify: queued for the next drain")
    return 0
