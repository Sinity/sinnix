from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .query import query as query_lanes
from .writer import CaptureWriter


def _cmd_write(args: argparse.Namespace) -> int:
    writer = CaptureWriter(args.capture_root, args.lane)

    def emit(payload: dict) -> None:
        envelope = writer.write(payload, raw_ref=args.raw_ref)
        if args.print_envelope:
            print(json.dumps(envelope, sort_keys=True))

    if args.stream:
        if args.payload is not None:
            print("--stream and --payload are mutually exclusive", file=sys.stderr)
            return 2
        # One long-lived writer draining NDJSON, so a high-rate lane pays one
        # process start rather than one per record. A malformed line must not
        # take the stream down with it -- report it and keep draining, the
        # same contract the per-record callers have.
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                emit(json.loads(line))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                print(f"sinnix-capture: dropped a record: {exc}", file=sys.stderr)
        return 0

    emit(json.loads(args.payload) if args.payload is not None else json.load(sys.stdin))
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
    write_p.add_argument(
        "--stream",
        action="store_true",
        help="Drain NDJSON payloads from stdin, one record per line, until EOF",
    )
    # Off by default: under systemd this stdout goes straight to the journal,
    # so every captured record was being stored twice -- once in the lane file
    # and once on the root disk's persistent journal.
    write_p.add_argument(
        "--print-envelope",
        action="store_true",
        help="Print each written envelope to stdout (interactive/debug use)",
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
