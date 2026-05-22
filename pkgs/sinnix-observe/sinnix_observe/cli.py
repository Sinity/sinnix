"""argparse entry + top-level orchestration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any

from . import SCHEMA
from .joins import build_workload_rows
from .render import render_human
from .sources.below import collect_below
from .sources.chrome import collect_chrome_io
from .sources.polylogue import collect_polylogue_live_attempts
from .sources.pressure import collect_blocked_tasks, collect_pressure
from .sources.storage import collect_storage
from .sources.systemd import (
    collect_resource_slices,
    collect_sentinel,
    collect_systemd_units,
)
from .sources.xtask import collect_sinex_xtask
from .util import utc_now

DEFAULT_BEGIN = os.environ.get("SINNIX_OBSERVE_BEGIN", "10 min ago")
DEFAULT_DURATION = os.environ.get("SINNIX_OBSERVE_DURATION", "10 min")
DEFAULT_LIMIT = int(os.environ.get("SINNIX_OBSERVE_LIMIT", "10"))


def collect_report(args: argparse.Namespace) -> dict[str, Any]:
    pressure = collect_pressure(args.offline)
    blocked = collect_blocked_tasks(args.offline)
    storage = collect_storage(args.offline)
    systemd_units = collect_systemd_units(args.offline)
    slices = collect_resource_slices(args.offline)
    sinex = collect_sinex_xtask(args.limit)
    polylogue = collect_polylogue_live_attempts(args.limit)
    below = collect_below(args.since, args.duration, args.limit, args.offline)
    chrome_io = collect_chrome_io(args.offline, below, args.limit)
    workload_rows = build_workload_rows(systemd_units, sinex, polylogue, below)
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "window": {"since": args.since, "duration": args.duration},
        "sources": {
            "sinex_xtask_history": {
                "path": sinex.get("db"),
                "available": sinex.get("available"),
            },
            "polylogue_live_attempts": {
                "path": polylogue.get("db"),
                "available": polylogue.get("available"),
            },
            "below": {"available": below.get("available")},
        },
        "live_pressure": pressure,
        "blocked_tasks": blocked,
        "storage": storage,
        "systemd_units": systemd_units,
        "sentinel": collect_sentinel(args.offline),
        "resource_slices": slices,
        "chrome_io": chrome_io,
        "sinex_xtask_history": sinex,
        "polylogue_live_attempts": polylogue,
        "below": below,
        "workload_rows": workload_rows,
        "gaps_summary": dict(
            Counter(gap for row in workload_rows for gap in row.get("gaps", []))
        ),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["human", "json"], default="human")
    parser.add_argument("--since", default=DEFAULT_BEGIN)
    parser.add_argument("--duration", default=DEFAULT_DURATION)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip live /proc/systemd/below collectors; useful for fixtures",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = collect_report(args)
    if args.format == "json":
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
