from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from .indexer import run_index_pass
from .pause import parse_duration, write_gap_record
from .recorder import run_recorder
from .segment import CHANNEL_PROFILES
from .topology import run_topology


def _add_capture_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--capture-root", required=True, type=Path)


def _cmd_record(args: argparse.Namespace) -> int:
    return run_recorder(
        channel=args.channel,
        capture_root=args.capture_root,
        pw_record_bin=args.pw_record_bin,
        pw_metadata_bin=args.pw_metadata_bin,
        pw_dump_bin=args.pw_dump_bin,
        opusenc_bin=args.opusenc_bin,
        tee_socket_path=args.tee_socket,
    )


def _cmd_topology(args: argparse.Namespace) -> int:
    return run_topology(capture_root=args.capture_root, pw_mon_bin=args.pw_mon_bin)


def _cmd_index(args: argparse.Namespace) -> int:
    since_ts = time.time() - args.lookback_hours * 3600
    indexed = run_index_pass(
        capture_root=args.capture_root,
        channels=tuple(args.channels),
        since_ts=since_ts,
        ffmpeg_bin=args.ffmpeg_bin,
    )
    logging.getLogger("sinnix_audio_capture.cli").info("indexed %d segment(s)", indexed)
    return 0


def _cmd_pause(args: argparse.Namespace) -> int:
    duration_seconds = parse_duration(args.duration)
    record = write_gap_record(
        capture_root=args.capture_root,
        duration_seconds=duration_seconds,
        reason=args.reason,
    )
    logging.getLogger("sinnix_audio_capture.cli").info("wrote gap record: %s", record)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnix-audio-capture")
    parser.add_argument("--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser(
        "record", help="Run the always-on recorder loop for one canonical channel"
    )
    record_parser.add_argument(
        "--channel", required=True, choices=sorted(CHANNEL_PROFILES)
    )
    _add_capture_root(record_parser)
    record_parser.add_argument("--pw-record-bin", default="pw-record")
    record_parser.add_argument("--pw-metadata-bin", default="pw-metadata")
    record_parser.add_argument("--pw-dump-bin", default="pw-dump")
    record_parser.add_argument("--opusenc-bin", default="opusenc")
    record_parser.add_argument(
        "--tee-socket",
        type=Path,
        default=None,
        help="SEQPACKET socket path to mirror raw mic PCM to (mic channel only)",
    )
    record_parser.set_defaults(func=_cmd_record)

    topology_parser = subparsers.add_parser(
        "topology",
        help="Stream pw-mon Node/Port/Link add/remove events to the audio-topology lane",
    )
    _add_capture_root(topology_parser)
    topology_parser.add_argument("--pw-mon-bin", default="pw-mon")
    topology_parser.set_defaults(func=_cmd_topology)

    index_parser = subparsers.add_parser(
        "index", help="Run a Silero VAD index pass over recently-closed Opus segments"
    )
    _add_capture_root(index_parser)
    index_parser.add_argument(
        "--channels",
        nargs="+",
        default=sorted(CHANNEL_PROFILES),
        choices=sorted(CHANNEL_PROFILES),
    )
    index_parser.add_argument(
        "--lookback-hours",
        type=float,
        default=26.0,
        help="Only index segments modified within this many hours (timer's own lookback window)",
    )
    index_parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    index_parser.set_defaults(func=_cmd_index)

    pause_parser = subparsers.add_parser(
        "pause",
        help="Write a gap record annotating an interval as intentionally uninteresting",
    )
    pause_parser.add_argument(
        "duration", help="e.g. '30s', '5m', '2h', or a bare number of seconds"
    )
    pause_parser.add_argument("--reason", default=None)
    _add_capture_root(pause_parser)
    pause_parser.set_defaults(func=_cmd_pause)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
