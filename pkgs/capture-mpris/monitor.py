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
poll loop. Position and duration are instead queried fresh, on demand, at
write time (both for change events and for heartbeats).

Every actual capture write shells out to the ``sinnix-capture`` CLI
(``sinnix-capture write --lane mpris``) rather than importing the writer
library directly, so this script has no Python dependency beyond the
standard library.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

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


def run(argv: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", str(exc)


def fetch_position_and_duration(
    playerctl_bin: str, player: str
) -> tuple[float | None, float | None]:
    rc, out, _err = run([playerctl_bin, "-p", player, "position"])
    position_seconds = float(out) if rc == 0 and out else None

    rc, out, _err = run([playerctl_bin, "-p", player, "metadata", "mpris:length"])
    duration_seconds = (int(out) / 1_000_000.0) if rc == 0 and out else None

    return position_seconds, duration_seconds


def write_envelope(
    sinnix_capture_bin: str,
    capture_root: str,
    lane: str,
    payload: dict,
) -> None:
    rc, _out, err = run(
        [
            sinnix_capture_bin,
            "write",
            "--capture-root",
            capture_root,
            "--lane",
            lane,
            "--payload",
            json.dumps(payload),
        ]
    )
    if rc != 0:
        log(f"sinnix-capture write failed (rc={rc}): {err}")


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
    sinnix_capture_bin: str,
    capture_root: str,
    lane: str,
) -> None:
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
    write_envelope(sinnix_capture_bin, capture_root, lane, payload)


def follow_loop(
    state: PlayerState,
    playerctl_bin: str,
    sinnix_capture_bin: str,
    capture_root: str,
    lane: str,
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
                    line, state, playerctl_bin, sinnix_capture_bin, capture_root, lane
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
    sinnix_capture_bin: str,
    capture_root: str,
    lane: str,
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
        write_envelope(sinnix_capture_bin, capture_root, lane, payload)


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

    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(
            state,
            args.playerctl_bin,
            args.sinnix_capture_bin,
            args.capture_root,
            args.lane,
            args.heartbeat_interval,
        ),
        daemon=True,
        name="mpris-heartbeat",
    )
    heartbeat_thread.start()

    follow_loop(
        state,
        args.playerctl_bin,
        args.sinnix_capture_bin,
        args.capture_root,
        args.lane,
        args.retry_backoff,
    )
    return 0  # unreachable: follow_loop retries forever


if __name__ == "__main__":
    raise SystemExit(main())
