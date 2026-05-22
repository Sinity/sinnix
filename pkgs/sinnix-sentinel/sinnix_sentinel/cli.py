"""Command-line entrypoint for the Python sentinel port.

Defaults to ``--observe-only``: corrective actions and notifications are
suppressed and the run is reported as a parallel observer. The bash sentinel
remains the live system actor.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

from . import policy as policy_mod
from .events import (
    CheckSet,
    append_events,
    diff_health_events,
    load_previous_health,
    prev_health_file_path,
    write_health,
)
from .notify import NotificationQueue, dispatch


def _load_policy() -> dict:
    path = os.environ.get("SINNIX_HEALTH_POLICY", "/etc/sinnix/health-policy.json")
    if not os.path.isfile(path):
        print(f"FATAL: health policy not found at {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _mcp_threshold() -> int:
    raw = os.environ.get("SINNIX_MCP_CHILD_THRESHOLD", "2")
    try:
        v = int(raw)
        return v if v >= 0 else 2
    except ValueError:
        return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sinnix-sentinel-py",
        description=(
            "Python port of sinnix-sentinel. Defaults to --observe-only "
            "so it can run alongside the live bash sentinel."
        ),
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--json", dest="json_only", action="store_true")
    p.add_argument("--correct", action="store_true", help="enable corrective actions")
    p.add_argument("--no-correct", action="store_true")
    p.add_argument("--no-notify", action="store_true")
    p.add_argument(
        "--observe-only",
        action="store_true",
        default=True,
        help=(
            "Default ON. Log intended actions but do not invoke notify-send, "
            "restart services, or write health.json/events.jsonl in destructive "
            "ways. Use --live to disable."
        ),
    )
    p.add_argument(
        "--live",
        dest="observe_only",
        action="store_false",
        help="DANGEROUS: enable real side effects. Not for normal operation.",
    )
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    corrective_env = os.environ.get("SINNIX_CORRECTIVE_ACTIONS", "false") == "true"
    corrective = (corrective_env or args.correct) and not args.no_correct

    notifications_enabled = (
        os.environ.get("SINNIX_NOTIFICATIONS", "true") == "true"
    ) and not args.no_notify

    observe_only = args.observe_only

    policy = _load_policy()
    threshold = _mcp_threshold()

    checks = CheckSet()
    notifs = NotificationQueue()
    now_ts, now_epoch = policy_mod.now_strings()

    # Run all checks in the bash order so that any side-channel ordering
    # (e.g. baseline samples landing before fill-rate reads them) matches.
    policy_mod.check_hardware(checks, notifs)
    policy_mod.check_reboot(checks, notifs, observe_only=observe_only)
    policy_mod.check_services(
        policy, checks, notifs, corrective=corrective, observe_only=observe_only
    )
    policy_mod.check_mcp(checks, notifs, threshold=threshold)
    policy_mod.check_captures(policy, checks, now_epoch)
    policy_mod.check_storage(policy, checks)
    policy_mod.check_backups(policy, checks, now_epoch)
    policy_mod.check_memory(checks, notifs)
    policy_mod.check_load(checks)
    policy_mod.check_processes(checks)
    policy_mod.check_thermal(checks, notifs)
    policy_mod.check_disk_fill_rate(checks)
    policy_mod.check_nix(
        checks, notifs, corrective=corrective, observe_only=observe_only
    )
    policy_mod.check_journal(policy, checks)
    policy_mod.check_pressure_watchdog(checks, notifs)

    health = checks.to_health_json(now_ts)
    previous = load_previous_health()
    events = diff_health_events(now_ts, health, previous)

    if args.json_only:
        json.dump(health, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if observe_only:
        # Print a clear, parsable observer summary; do NOT touch live state files
        # except printing. The bash sentinel remains the source of truth.
        summary = (
            f"SENTINEL[observe]: {health['overall'].upper()} "
            f"({checks.ok} ok, {checks.fail} fail, {checks.warn} warn) "
            f"would-emit={len(events)} events, would-notify={len(notifs)}"
        )
        print(summary)
        if args.verbose:
            for ev in events:
                print(f"  event: {json.dumps(ev)}")
            for n in notifs:
                print(f"  notify[{n.urgency}]: {n.message}")
        return 1 if checks.fail > 0 else 0

    # Live mode (requires explicit --live). Still gated on writable parent.
    if previous is not None:
        try:
            prev_health_file_path().parent.mkdir(parents=True, exist_ok=True)
            prev_health_file_path().write_text(
                json.dumps(previous) + "\n", encoding="utf-8"
            )
        except OSError:
            pass

    write_health(health)
    append_events(events)
    dispatch(notifs, enabled=notifications_enabled, observe_only=False)

    if not args.verbose:
        print(
            f"SENTINEL: {health['overall'].upper()} "
            f"({checks.ok} ok, {checks.fail} fail, {checks.warn} warn)"
        )
    return 1 if checks.fail > 0 else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
