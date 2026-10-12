"""MPRIS media-player capture daemon.

Watches ``org.mpris.MediaPlayer2.*`` players via ``playerctl --follow``
(the "most recently updated player" semantics documented in playerctl(1))
and appends one sinnix-capture-v1 envelope per track/status change to the
``mpris`` capture lane, plus a periodic heartbeat while a player's
PlaybackStatus is "Playing" -- so long, single-track listening sessions
still carry periodic position markers between track boundaries instead of
going silent for the whole session.

Design note on the follow format: playerctl's ``--follow`` only re-emits a
line when the *rendered format string* changes for the most recently
updated player. The format used here deliberately tracks player identity,
playback status, and title/artist/album -- and deliberately excludes
position, which changes every second and would turn "follow" into a tight
poll loop. Position and duration are instead queried fresh when observed, before
queuing the capture (both for change events and for heartbeats).

Every actual capture write shells out to the ``sinnix-capture`` CLI
(``sinnix-capture write --lane mpris``) rather than importing the writer
library directly. Command execution uses the shared ``sinnix_lib`` result
contract for player probes. Capture writes wait for completion on a separate
worker; a storage stall must not kill an in-flight append. Change events are
queued in order and only waiting heartbeats are coalesced. The queue is
process-local; a failed write retains pending events without an automatic
retry, because that write may already have committed.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from collections import deque

from sinnix_lib.process import run

FIELD_SEP = "\x1f"  # ASCII unit separator; vanishingly unlikely in track metadata
FOLLOW_FIELDS = ("player", "status", "title", "artist", "album")
FOLLOW_FORMAT = FIELD_SEP.join(
    f"{{{{{f}}}}}" for f in ("playerName", "status", "title", "artist", "album")
)


def log(msg: str) -> None:
    print(f"capture-mpris: {msg}", file=sys.stderr, flush=True)


@dataclass
class PlayerState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    player: str | None = None
    status: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    seen: bool = False


def fetch_position_and_duration(
    playerctl_bin: str, player: str
) -> tuple[float | None, float | None]:
    position = run([playerctl_bin, "-p", player, "position"], timeout=10)
    position_text = position.text
    try:
        position_seconds = float(position_text) if position_text else None
        if position_seconds is not None and not math.isfinite(position_seconds):
            position_seconds = None
    except (ValueError, OverflowError):
        position_seconds = None

    duration = run(
        [playerctl_bin, "-p", player, "metadata", "mpris:length"], timeout=10
    )
    duration_text = duration.text
    try:
        duration_seconds = (int(duration_text) / 1_000_000.0) if duration_text else None
    except (ValueError, OverflowError):
        duration_seconds = None

    return position_seconds, duration_seconds


def write_envelope(
    sinnix_capture_bin: str,
    capture_root: str,
    lane: str,
    payload: dict,
    ts: float,
) -> None:
    result = subprocess.run(
        [
            sinnix_capture_bin,
            "write",
            "--capture-root",
            capture_root,
            "--lane",
            lane,
            "--payload",
            json.dumps(payload),
            "--ts",
            str(ts),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"sinnix-capture write failed (rc={result.returncode}): {result.stderr.strip()}")



class EnvelopeWriter:
    """One in-flight write, preserving change events while storage is slow."""

    def __init__(self, capture_bin: str, root: str, lane: str):
        self.args = (capture_bin, root, lane)
        self.condition = threading.Condition()
        self.pending: deque[tuple[float, dict]] = deque()
        self.current: tuple[float, dict] | None = None
        self.closing = False
        self.failure: Exception | None = None
        self.thread = threading.Thread(target=self._drain, daemon=True, name="mpris-writer")
        self.thread.start()

    def enqueue(self, payload: dict, ts: float) -> None:
        item = (ts, dict(payload))
        with self.condition:
            if self.closing:
                raise RuntimeError("capture writer is closing")
            # Only replace a waiting heartbeat for the same playback state;
            # never replace a change event or the write already in flight.
            if self.pending and self.pending[-1] is not self.current:
                previous = self.pending[-1][1]
                keys = ("player", "status", "title", "artist", "album")
                if payload.get("event") == previous.get("event") == "heartbeat" and all(
                    payload.get(key) == previous.get(key) for key in keys
                ):
                    self.pending[-1] = item
                    self.condition.notify()
                    return
            self.pending.append(item)
            self.condition.notify()

    def _drain(self) -> None:
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.pending or self.closing)
                if not self.pending:
                    return
                self.current = self.pending[0]
                ts, payload = self.current
            try:
                write_envelope(*self.args, payload, ts)
            except Exception as exc:
                # An error may follow a committed record. Keep the current and
                # waiting events; a blind retry could allocate duplicate seqs.
                with self.condition:
                    self.failure = exc
                log(f"capture writer stopped; pending events retained in memory: {exc}")
                return
            with self.condition:
                self.pending.popleft()
                self.current = None

    def close(self) -> None:
        with self.condition:
            self.closing = True
            self.condition.notify()
        self.thread.join()

def classify_change(
    state: PlayerState, player: str, status: str, title: str, artist: str, album: str
) -> str:
    if not state.seen:
        return "initial"
    if (player, title, artist, album) != (
        state.player,
        state.title,
        state.artist,
        state.album,
    ):
        return "track"
    if status != state.status:
        return "status"
    return "update"


def handle_follow_line(
    line: str,
    state: PlayerState,
    playerctl_bin: str,
    writer: EnvelopeWriter,
) -> None:
    observed_at = time.time()
    parts = line.split(FIELD_SEP)
    if len(parts) != len(FOLLOW_FIELDS):
        log(f"ignoring malformed follow line ({len(parts)} fields): {line!r}")
        return
    player, status, title, artist, album = parts

    with state.lock:
        if not player:
            # No active player right now (e.g. the last one just exited).
            # Nothing meaningful to write; clear state so a stale heartbeat
            # doesn't fire and so the next real player is treated as fresh.
            state.seen = False
            state.player = None
            state.status = None
            state.title = None
            state.artist = None
            state.album = None
            return

        kind = classify_change(state, player, status, title, artist, album)
        state.seen = True
        state.player = player
        state.status = status
        state.title = title
        state.artist = artist
        state.album = album

    position_seconds, duration_seconds = fetch_position_and_duration(
        playerctl_bin, player
    )
    payload = {
        "event": kind,
        "player": player,
        "status": status,
        "title": title or None,
        "artist": artist or None,
        "album": album or None,
        "position_seconds": position_seconds,
        "duration_seconds": duration_seconds,
    }
    writer.enqueue(payload, observed_at)


def follow_loop(
    state: PlayerState,
    playerctl_bin: str,
    writer: EnvelopeWriter,
    retry_backoff_seconds: float,
) -> None:
    follow_cmd = [playerctl_bin, "--follow", "metadata", "--format", FOLLOW_FORMAT]
    while True:
        try:
            proc = subprocess.Popen(
                follow_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            log(f"playerctl binary not found: {playerctl_bin}")
            sys.exit(1)

        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                handle_follow_line(
                    line, state, playerctl_bin, writer
                )
            except (
                Exception
            ) as exc:  # defensive: one bad event must not kill the daemon
                log(f"error handling follow line {line!r}: {exc}")

        rc = proc.wait()
        stderr_tail = proc.stderr.read().strip() if proc.stderr else ""
        log(
            f"playerctl --follow exited (rc={rc}) {stderr_tail}; retrying in {retry_backoff_seconds}s"
        )
        time.sleep(retry_backoff_seconds)


def heartbeat_loop(
    state: PlayerState,
    playerctl_bin: str,
    writer: EnvelopeWriter,
    interval_seconds: float,
) -> None:
    while True:
        time.sleep(interval_seconds)
        with state.lock:
            if not (state.seen and state.status == "Playing" and state.player):
                continue
            player, status, title, artist, album = (
                state.player,
                state.status,
                state.title,
                state.artist,
                state.album,
            )

        observed_at = time.time()
        position_seconds, duration_seconds = fetch_position_and_duration(
            playerctl_bin, player
        )
        payload = {
            "event": "heartbeat",
            "player": player,
            "status": status,
            "title": title or None,
            "artist": artist or None,
            "album": album or None,
            "position_seconds": position_seconds,
            "duration_seconds": duration_seconds,
        }
        writer.enqueue(payload, observed_at)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture-root", required=True, help="sinnix-capture root directory"
    )
    parser.add_argument("--lane", default="mpris", help="Capture lane name")
    parser.add_argument("--playerctl-bin", default="playerctl")
    parser.add_argument("--sinnix-capture-bin", default="sinnix-capture")
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=60.0,
        help="Seconds between heartbeats while Playing",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=5.0,
        help="Seconds to wait before relaunching a dead playerctl --follow",
    )
    args = parser.parse_args(argv)

    state = PlayerState()
    writer = EnvelopeWriter(args.sinnix_capture_bin, args.capture_root, args.lane)

    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(
            state,
            args.playerctl_bin,
            writer,
            args.heartbeat_interval,
        ),
        daemon=True,
        name="mpris-heartbeat",
    )
    heartbeat_thread.start()

    follow_loop(
        state,
        args.playerctl_bin,
        writer,
        args.retry_backoff,
    )
    return 0  # unreachable: follow_loop retries forever


if __name__ == "__main__":
    raise SystemExit(main())
