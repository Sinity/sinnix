from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from .devices import POLL_INTERVAL_SECONDS, probe_coverage, run_devices
from .indexer import run_index_pass
from .pause import parse_duration, write_gap_record
from .topology import run_topology


def _add_capture_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--capture-root", required=True, type=Path)


def _add_excludes(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--exclude-source",
        action="append",
        default=[],
        metavar="REGEX",
        help="Case-insensitive regex matched against a capture source's "
        "node.name and node.description; matches are never recorded (repeatable)",
    )
    parser.add_argument(
        "--exclude-sink",
        action="append",
        default=[],
        metavar="REGEX",
        help="Same, for playback sinks (recorded through their monitor ports)",
    )


def _cmd_record_devices(args: argparse.Namespace) -> int:
    return run_devices(
        capture_root=args.capture_root,
        exclude_sources=args.exclude_source,
        exclude_sinks=args.exclude_sink,
        asr_source_pattern=args.asr_source,
        pw_record_bin=args.pw_record_bin,
        pw_dump_bin=args.pw_dump_bin,
        opusenc_bin=args.opusenc_bin,
        tee_socket_path=args.tee_socket,
        poll_interval=args.poll_interval,
    )


def _cmd_devices_probe(args: argparse.Namespace) -> int:
    code, detail = probe_coverage(
        capture_root=args.capture_root,
        pw_dump_bin=args.pw_dump_bin,
        exclude_patterns={
            "source": args.exclude_source,
            "sink": args.exclude_sink,
        },
        max_age_seconds=args.max_age,
    )
    print(json.dumps(detail, sort_keys=True))
    return code


def _cmd_topology(args: argparse.Namespace) -> int:
    return run_topology(capture_root=args.capture_root, pw_mon_bin=args.pw_mon_bin)


def _cmd_index(args: argparse.Namespace) -> int:
    since_ts = time.time() - args.lookback_hours * 3600
    indexed = run_index_pass(
        capture_root=args.capture_root,
        channels=None if args.channels is None else tuple(args.channels),
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

    devices_parser = subparsers.add_parser(
        "record-devices",
        help="Supervise one always-on recorder per live PipeWire source and sink",
    )
    _add_capture_root(devices_parser)
    _add_excludes(devices_parser)
    devices_parser.add_argument("--pw-record-bin", default="pw-record")
    devices_parser.add_argument("--pw-dump-bin", default="pw-dump")
    devices_parser.add_argument("--opusenc-bin", default="opusenc")
    devices_parser.add_argument(
        "--asr-source",
        default=None,
        metavar="REGEX",
        help="Which capture source feeds the low-latency ASR tee. Names one "
        "device for transcription only; it privileges no lane in the archive, "
        "which records every device regardless",
    )
    devices_parser.add_argument(
        "--tee-socket",
        type=Path,
        default=None,
        help="SEQPACKET socket path mirroring raw PCM from the --asr-source "
        "device (its format is published alongside as <socket>.json)",
    )
    devices_parser.add_argument(
        "--poll-interval", type=float, default=POLL_INTERVAL_SECONDS
    )
    devices_parser.set_defaults(func=_cmd_record_devices)

    probe_parser = subparsers.add_parser(
        "devices-probe",
        help="Exit 0 if every non-excluded live device is being written to, "
        "1 if any is not, 2 if the graph could not be read",
    )
    _add_capture_root(probe_parser)
    _add_excludes(probe_parser)
    probe_parser.add_argument("--pw-dump-bin", default="pw-dump")
    probe_parser.add_argument("--max-age", type=float, default=600.0)
    probe_parser.set_defaults(func=_cmd_devices_probe)

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
        default=None,
        help="Channel directories under <capture-root>/audio to index "
        "(default: every one present, since per-source channels appear at runtime)",
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
