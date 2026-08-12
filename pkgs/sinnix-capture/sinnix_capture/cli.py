from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .query import query as query_lanes
from .writer import CaptureWriter


def _cmd_write(args: argparse.Namespace) -> int:
    payload = (
        json.loads(args.payload) if args.payload is not None else json.load(sys.stdin)
    )
    writer = CaptureWriter(args.capture_root, args.lane)
    envelope = writer.write(payload, raw_ref=args.raw_ref)
    print(json.dumps(envelope, sort_keys=True))
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    results = query_lanes(args.capture_root, args.since, args.lanes)
    print(json.dumps(results, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnix-capture")
    sub = parser.add_subparsers(dest="command", required=True)

    write_p = sub.add_parser(
        "write", help="Append one sinnix-capture-v1 record to a lane"
    )
    write_p.add_argument("--capture-root", required=True, type=Path)
    write_p.add_argument("--lane", required=True)
    write_p.add_argument("--payload", help="JSON payload; reads stdin if omitted")
    write_p.add_argument(
        "--raw-ref",
        default=None,
        help="Pointer to a raw artifact this record summarizes",
    )
    write_p.set_defaults(func=_cmd_write)

    query_p = sub.add_parser("query", help="Per-lane record deltas since a timestamp")
    query_p.add_argument("--capture-root", required=True, type=Path)
    query_p.add_argument(
        "--since",
        type=float,
        default=0.0,
        help="Unix timestamp; records at or after this count toward records_since",
    )
    query_p.add_argument(
        "--lane",
        action="append",
        dest="lanes",
        help="Restrict to specific lane(s); default is every lane directory under capture-root",
    )
    query_p.set_defaults(func=_cmd_query)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
