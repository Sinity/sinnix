"""argparse entry + top-level orchestration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any

from . import SCHEMA
from .joins import build_gateway_rows, build_workload_rows
from .render import render_human
from .sources.agent_gateway import collect_agent_gateway
from .sources.below import collect_below
from .sources.chrome import collect_chrome_io
from .sources.drift import collect_config_drift
from .sources.polylogue import collect_polylogue_live_attempts
from .sources.pressure import collect_blocked_tasks, collect_pressure
from .sources.sqlite_util import clear_sqlite_errors, sqlite_errors
from .sources.storage import collect_storage
from .sources.systemd import (
    collect_resource_slices,
    collect_runtime_inventory,
    collect_systemd_units,
)
from .sources.xtask import collect_sinex_xtask
from .util import utc_now

DEFAULT_BEGIN = os.environ.get("SINNIX_OBSERVE_BEGIN", "10 min ago")
DEFAULT_DURATION = os.environ.get("SINNIX_OBSERVE_DURATION", "10 min")
DEFAULT_LIMIT = int(os.environ.get("SINNIX_OBSERVE_LIMIT", "10"))


def _report_header(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "window": {"since": args.since, "duration": args.duration},
    }


def _sources(
    sinex: dict[str, Any],
    polylogue: dict[str, Any],
    config_drift: dict[str, Any] | None = None,
    below: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sources = {
        "sinex_xtask_history": {
            "path": sinex.get("db"),
            "available": sinex.get("available"),
        },
        "polylogue_live_attempts": {
            "path": polylogue.get("db"),
            "available": polylogue.get("available"),
        },
    }
    if config_drift is not None:
        sources["config_drift"] = {
            "available": config_drift.get("available"),
            "status": config_drift.get("status"),
            "drift_count": config_drift.get("drift_count", 0),
            "unavailable_count": config_drift.get("unavailable_count", 0),
        }
    if below is not None:
        sources["below"] = {"available": below.get("available")}
    sources["sqlite_errors"] = sqlite_errors()
    return sources


def _page(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    cursor = getattr(args, "cursor", 0)
    page_limit = getattr(args, "page_limit", None) or args.limit
    if cursor < 0:
        raise ValueError("cursor must be non-negative")
    if page_limit < 1:
        raise ValueError("page limit must be positive")
    selected = rows[cursor : cursor + page_limit]
    next_cursor = cursor + len(selected)
    return {
        "total": len(rows),
        "cursor": cursor,
        "next_cursor": next_cursor if next_cursor < len(rows) else None,
        "rows": selected,
    }


def collect_report(args: argparse.Namespace) -> dict[str, Any]:
    clear_sqlite_errors()
    section = getattr(args, "section", None)
    if section is not None and section != "overview":
        report = _report_header(args)
        if section == "pressure":
            report["live_pressure"] = collect_pressure(args.offline)
        elif section == "blocked_tasks":
            report["blocked_tasks"] = _page(collect_blocked_tasks(args.offline), args)
        elif section == "storage":
            report["storage"] = collect_storage(args.offline)
        elif section == "units":
            report["systemd_units"] = _page(collect_systemd_units(args.offline), args)
        elif section == "slices":
            report["resource_slices"] = _page(
                collect_resource_slices(args.offline), args
            )
        elif section == "runtime_inventory":
            report["runtime_inventory"] = collect_runtime_inventory(args.offline)
        elif section in {"gateway", "browser", "workloads"}:
            below = collect_below(args.since, args.duration, args.limit, args.offline)
            if section == "gateway":
                report["agent_gateway"] = collect_agent_gateway(args.limit, below)
            elif section == "browser":
                report["chrome_io"] = collect_chrome_io(args.offline, below, args.limit)
            else:
                systemd_units = collect_systemd_units(args.offline)
                sinex = collect_sinex_xtask(args.limit)
                polylogue = collect_polylogue_live_attempts(args.limit)
                gateway = collect_agent_gateway(args.limit, below)
                workload_rows = build_workload_rows(
                    systemd_units, sinex, polylogue, below
                ) + build_gateway_rows(gateway, below)
                report.update(
                    {
                        "sources": _sources(sinex, polylogue, below=below),
                        "workload_rows": _page(workload_rows, args),
                        "gaps_summary": dict(
                            Counter(
                                gap
                                for row in workload_rows
                                for gap in row.get("gaps", [])
                            )
                        ),
                    }
                )
        elif section == "ingestion":
            sinex = collect_sinex_xtask(args.limit)
            polylogue = collect_polylogue_live_attempts(args.limit)
            report.update(
                {
                    "sources": _sources(sinex, polylogue),
                    "sinex_xtask_history": sinex,
                    "polylogue_live_attempts": polylogue,
                }
            )
        else:
            raise ValueError(f"unknown report section: {section}")
        return report

    pressure = collect_pressure(args.offline)
    blocked = collect_blocked_tasks(args.offline)
    storage = collect_storage(args.offline)
    systemd_units = collect_systemd_units(args.offline)
    slices = collect_resource_slices(args.offline)
    sinex = collect_sinex_xtask(args.limit)
    polylogue = collect_polylogue_live_attempts(args.limit)
    below = collect_below(args.since, args.duration, args.limit, args.offline)
    chrome_io = collect_chrome_io(args.offline, below, args.limit)
    gateway = collect_agent_gateway(args.limit, below)
    config_drift = collect_config_drift()
    workload_rows = build_workload_rows(
        systemd_units, sinex, polylogue, below
    ) + build_gateway_rows(gateway, below)
    return {
        **_report_header(args),
        "sources": _sources(sinex, polylogue, config_drift, below),
        "live_pressure": pressure,
        "blocked_tasks": blocked,
        "storage": storage,
        "systemd_units": systemd_units,
        "runtime_inventory": collect_runtime_inventory(args.offline),
        "config_drift": config_drift,
        "resource_slices": slices,
        "chrome_io": chrome_io,
        "sinex_xtask_history": sinex,
        "polylogue_live_attempts": polylogue,
        "below": below,
        "agent_gateway": gateway,
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
    parser.add_argument("--cursor", type=int, default=0)
    parser.add_argument("--page-limit", type=int)
    parser.add_argument(
        "--section",
        choices=[
            "overview",
            "pressure",
            "blocked_tasks",
            "storage",
            "units",
            "slices",
            "runtime_inventory",
            "gateway",
            "browser",
            "ingestion",
            "workloads",
        ],
        help="Collect one JSON report section without running unrelated collectors",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip live /proc/systemd/below collectors; useful for fixtures",
    )
    args = parser.parse_args(argv)
    if args.section is not None and args.format != "json":
        parser.error("--section requires --format json")
    if args.cursor < 0:
        parser.error("--cursor must be non-negative")
    if args.page_limit is not None and args.page_limit < 1:
        parser.error("--page-limit must be positive")
    if args.section is None and (args.cursor or args.page_limit is not None):
        parser.error("--cursor and --page-limit require --section")
    return args


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
