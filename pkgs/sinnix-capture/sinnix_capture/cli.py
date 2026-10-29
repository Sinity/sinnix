from __future__ import annotations

import argparse
import json
import math
import os
import select
import sys
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from .query import query as query_lanes
from .selection import capture_selection
from .writer import CaptureWriter

# A stream batch is written when its oldest line has waited this long, when
# it holds this many lines, or at end of input. Each batch costs one sync per
# lane file, so on a steady trickle this bounds syncs to a few per second.
STREAM_BATCH_SECONDS = 1.0
STREAM_BATCH_RECORDS = 1000


def stream_batches(
    fd: int,
    *,
    max_seconds: float = STREAM_BATCH_SECONDS,
    max_records: int = STREAM_BATCH_RECORDS,
) -> Iterator[list[tuple[str, float]]]:
    """Group the lines read from ``fd`` into ``(line, arrival ts)`` batches."""
    pending: list[tuple[str, float]] = []
    partial = b""
    deadline: float | None = None
    while True:
        timeout = None if deadline is None else max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            yield pending
            pending, deadline = [], None
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            if partial:
                pending.append((partial.decode("utf-8", "replace"), time.time()))
            if pending:
                yield pending
            return
        arrived = time.time()
        *lines, partial = (partial + chunk).split(b"\n")
        for line in lines:
            pending.append((line.decode("utf-8", "replace"), arrived))
            if len(pending) >= max_records:
                yield pending
                pending, deadline = [], None
        if pending and deadline is None:
            deadline = time.monotonic() + max_seconds


def _cmd_write(args: argparse.Namespace) -> int:
    if args.ts is not None:
        try:
            if not math.isfinite(args.ts):
                raise ValueError("non-finite timestamp")
            datetime.fromtimestamp(args.ts, timezone.utc)
        except (ValueError, OverflowError, OSError):
            print(
                "--ts must be a finite, representable Unix timestamp", file=sys.stderr
            )
            return 2
    writer = CaptureWriter(args.capture_root, args.lane)

    def emit(envelopes: list[dict]) -> None:
        if args.print_envelope:
            for envelope in envelopes:
                print(json.dumps(envelope, sort_keys=True), flush=True)

    if args.stream:
        if args.ts is not None:
            print("--ts is for one record, not a stream", file=sys.stderr)
            return 2
        if args.payload is not None:
            print("--stream and --payload are mutually exclusive", file=sys.stderr)
            return 2
        # One long-lived writer draining NDJSON, so a high-rate lane pays one
        # process start rather than one per record, and one set of syncs per
        # batch rather than per record. A malformed line must not take the
        # stream down with it -- report it and keep draining, the same
        # contract the per-record callers have.
        for batch in stream_batches(sys.stdin.fileno()):
            records = []
            for line, arrived in batch:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append((json.loads(line), arrived))
                except ValueError as exc:
                    print(f"sinnix-capture: dropped a record: {exc}", file=sys.stderr)
            emit(writer.write_batch(records, raw_ref=args.raw_ref))
        return 0

    payload = (
        json.loads(args.payload) if args.payload is not None else json.load(sys.stdin)
    )
    emit([writer.write(payload, raw_ref=args.raw_ref, ts=args.ts)])
    return 0


def _cmd_selection(args: argparse.Namespace) -> int:
    try:
        return capture_selection(
            capture_root=args.capture_root,
            lane=args.lane,
            list_command=args.list_command,
            paste_command=args.paste_command,
            window_command=args.window_command,
            dedup_state=args.dedup_state,
            debounce_ms=args.debounce_ms,
            debounce_state=args.debounce_state,
        )
    except ValueError as exc:
        print(f"sinnix-capture: {exc}", file=sys.stderr)
        return 2


def _cmd_import_clipse(args: argparse.Namespace) -> int:
    from .clipse_import import import_clipse

    report = import_clipse(
        capture_root=args.capture_root,
        lane=args.lane,
        history_path=args.history,
        tmp_files=args.tmp_files,
    )
    print(json.dumps(report.__dict__, sort_keys=True))
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
        "--ts",
        type=float,
        default=None,
        help="Observed Unix timestamp for a queued single record",
    )
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

    selection_p = sub.add_parser(
        "selection",
        help="Capture the current Wayland selection into a lane",
    )
    selection_p.add_argument("--capture-root", required=True, type=Path)
    selection_p.add_argument("--lane", required=True)
    selection_p.add_argument(
        "--list-command",
        required=True,
        help="Command printing the offered MIME types, one per line",
    )
    selection_p.add_argument(
        "--paste-command",
        required=True,
        help="Command printing the selection; the chosen MIME type is appended to its argv",
    )
    selection_p.add_argument(
        "--window-command",
        default=None,
        help="Command printing the focused window as JSON, for source attribution",
    )
    selection_p.add_argument(
        "--dedup-state",
        default=None,
        type=Path,
        help="Track the last captured content here and skip an immediate repeat of it",
    )
    selection_p.add_argument(
        "--debounce-ms",
        default=None,
        type=int,
        help="Settle this long and yield to any newer trigger, collapsing one gesture's re-offers",
    )
    selection_p.add_argument(
        "--debounce-state",
        default=None,
        type=Path,
        help="Trigger file the debounce window arbitrates on",
    )
    selection_p.set_defaults(func=_cmd_selection)

    import_p = sub.add_parser(
        "import-clipse",
        help="Import a clipse clipboard_history.json (and its tmp_files images) into a lane",
    )
    import_p.add_argument("--capture-root", required=True, type=Path)
    import_p.add_argument("--lane", default="clipboard")
    import_p.add_argument("--history", required=True, type=Path)
    import_p.add_argument(
        "--tmp-files",
        default=None,
        type=Path,
        help="clipse image directory; unreferenced files are imported as orphans",
    )
    import_p.set_defaults(func=_cmd_import_clipse)

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
