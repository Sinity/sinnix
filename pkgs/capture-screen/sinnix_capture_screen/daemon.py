"""sinnix-capture-screen daemon: Hyprland-event + idle-pause + 30s-floor
triggered per-window screen frame capture, p-hash deduped, WebP-encoded.

FRAME-GRAB MECHANISM (read before touching this file). Frames come from
`grim`, not from Noctalia's own screenshot IPC. Noctalia's ScreenshotService
exposes only whole-OUTPUT and REGION capture (`noctalia msg screenshot-region`
/ `screenshot-fullscreen`), fire-and-forget to a fixed directory plus optional
clipboard copy, with no raw-bytes-to-stdout mode and no per-window capture at
all -- there is nothing there this daemon could drive per-window, per-trigger,
at low latency, without disk and clipboard side effects on every capture.

`grim` speaks the same wlr-screencopy protocol Noctalia's native path uses, so
this is not a downgrade. The known black-frame failure is compositor-side, not
client-side: it is fixed by `render:keep_unmodified_copy = 1` plus
`render:use_shader_blur_blend = true`
(modules/features/desktop/hyprland/default.nix), which is global to every
wlr-screencopy client. That fix does not always hold -- the underlying
Hyprland/NVIDIA HDR screencopy bug can recur even with both options set, with
the signature "GBM: Failed to allocate a GBM buffer: format XR30 isn't
supported by primary backend" in hyprland.log, and both grim and Noctalia go
solid-color together when it does. This daemon does not try to fix that;
`is_degenerate_frame()` (hashing.py) refuses to persist a flat single-color
frame, and this module logs loudly and counts it as a capture-attempt failure
rather than writing black frames into the lake forever.

Per-window framing is done by cropping grim's capture to the focused window's
geometry (`hyprctl activewindow -j`'s `at`/`size`) via grim's own
-g "X,Y WxH" region mechanism.

TYPING-PAUSE TRIGGER: a keystroke-timing signal is not cheaply available here.
`libinput debug-events` needs to open /dev/input/event*, which is unprivileged
only for a systemd --user service tied to the active graphical session's logind
seat ACL -- a whole subprocess/permission shape for a coarse pause signal.
Instead this daemon polls `hyprctl cursorpos` (already called for other
reasons) once per loop tick and fires `hashing.PauseDetector` when the cursor
has been stationary for `--idle-pause-seconds`. That approximates "user stopped
interacting", not literally "user stopped typing".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import sys
import time
from pathlib import Path

from . import capture, hypr
from .hashing import (
    CaptureAttemptGate,
    DailyThrottleGuard,
    PauseDetector,
    ThrottleState,
    is_degenerate_frame,
    is_near_duplicate,
    phash64,
    should_capture_periodic,
)


def _load_throttle_state(path: Path, clock) -> ThrottleState | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    today = time.strftime("%Y-%m-%d", time.gmtime(clock()))
    if data.get("day") != today:
        return None  # stale from a previous day; start fresh
    return ThrottleState(
        day=str(data.get("day")),
        bytes_written=int(data.get("bytes_written", 0)),
        tripped=bool(data.get("tripped", False)),
    )


def _save_throttle_state(path: Path, state: ThrottleState) -> None:
    path.write_text(
        json.dumps(
            {
                "day": state.day,
                "bytes_written": state.bytes_written,
                "tripped": state.tripped,
            }
        )
    )


def _window_key(window: dict | None) -> str:
    if window is None:
        return "unknown"
    return f"{window.get('class')}\x00{window.get('title')}"


def run(args: argparse.Namespace) -> int:
    if not args.runtime_dir or not args.instance_signature:
        print(
            "sinnix-capture-screen: --runtime-dir/--instance-signature are unset and "
            "XDG_RUNTIME_DIR/HYPRLAND_INSTANCE_SIGNATURE are not in the environment "
            "-- refusing to guess a socket path.",
            file=sys.stderr,
        )
        return 1
    read_json = hypr.make_hyprctl_json_reader(args.hyprctl_bin)
    sock_path = hypr.socket2_path(args.runtime_dir, args.instance_signature)
    try:
        sock = hypr.connect_socket2(sock_path)
        sock.setblocking(False)
    except OSError as exc:
        print(
            f"sinnix-capture-screen: cannot connect to Hyprland socket2 at {sock_path}: {exc}",
            file=sys.stderr,
        )
        return 1

    throttle_state_path = args.capture_root / args.lane / "throttle-state.json"
    throttle_state_path.parent.mkdir(parents=True, exist_ok=True)
    throttle = DailyThrottleGuard(
        ceiling_bytes=args.daily_ceiling_bytes,
        state=_load_throttle_state(throttle_state_path, time.time),
    )

    pause_detector = PauseDetector(idle_seconds=args.idle_pause_seconds)
    attempt_gate = CaptureAttemptGate()
    last_hash_by_window: dict[str, int] = {}
    last_capture_ts: float | None = None
    seq = 0
    buf = b""

    def do_capture(trigger: str) -> None:
        nonlocal last_capture_ts, seq
        attempt_now = time.monotonic()
        if not attempt_gate.allow(attempt_now):
            return
        now = time.time()
        last_capture_ts = now
        window = hypr.get_active_window(read_json)
        monitors = hypr.get_monitors(read_json)
        monitor_name = (
            hypr.monitor_name_for_id(monitors, window.get("monitor_id"))
            if window
            else None
        )
        if monitor_name is None and monitors:
            monitor_name = monitors[0].get("name")
        if monitor_name is None:
            attempt_gate.record_failure(attempt_now)
            return

        geometry = window.get("geometry") if window else {}
        grim_geometry = None
        if window and all(
            geometry.get(k) is not None for k in ("x", "y", "width", "height")
        ):
            grim_geometry = f"{geometry['x']},{geometry['y']} {geometry['width']}x{geometry['height']}"

        png_bytes, grim_error = capture.run_grim(
            args.grim_bin, monitor_name, grim_geometry
        )
        if png_bytes is None:
            attempt_gate.record_failure(attempt_now)
            print(
                f"sinnix-capture-screen: grim capture failed (trigger={trigger} "
                f"monitor={monitor_name} geometry={grim_geometry}): {grim_error}",
                file=sys.stderr,
            )
            return

        im = capture.load_image(png_bytes)
        gray = capture.image_to_phash_array(im)
        if is_degenerate_frame(gray):
            attempt_gate.record_failure(attempt_now)
            print(
                f"sinnix-capture-screen: refusing degenerate (flat/black) frame -- "
                f"trigger={trigger} monitor={monitor_name} window={_window_key(window)}. "
                "This usually means a live compositor screencopy regression (see "
                "daemon.py module docstring, sinnix-xuk/sinnix-kvc); not writing it.",
                file=sys.stderr,
            )
            return

        window_key = _window_key(window)
        new_hash = phash64(gray)
        if is_near_duplicate(
            last_hash_by_window.get(window_key),
            new_hash,
            threshold=args.dedup_hamming_threshold,
        ):
            last_hash_by_window[window_key] = new_hash
            attempt_gate.record_success()
            return
        last_hash_by_window[window_key] = new_hash

        webp_bytes = capture.encode_webp(
            im, max_width=args.max_width, quality=args.quality
        )
        allowed, newly_tripped = throttle.allow(len(webp_bytes))
        _save_throttle_state(throttle_state_path, throttle.state)
        if newly_tripped:
            print(
                f"sinnix-capture-screen: DAILY VOLUME CEILING TRIPPED "
                f"({throttle.state.bytes_written}/{throttle.ceiling_bytes} bytes) -- this is a "
                "runaway-bug backstop, not a policy cap; capture writes are suspended until "
                "the UTC day rolls over. If this trips under normal use, raise "
                "--daily-ceiling-bytes or investigate a stuck dedup/trigger loop.",
                file=sys.stderr,
            )
        if not allowed:
            return

        sha256 = hashlib.sha256(webp_bytes).hexdigest()
        seq += 1
        filename = capture.frame_filename(
            now, window.get("class") if window else None, seq
        )
        payload = capture.build_frame_payload(
            ts=now,
            window_class=window.get("class") if window else None,
            window_title=window.get("title") if window else None,
            workspace=window.get("workspace") if window else None,
            geometry=geometry,
            monitor=monitor_name,
            sha256=sha256,
            trigger=trigger,
        )
        written_path = capture.write_frame(
            payload=payload,
            webp_bytes=webp_bytes,
            capture_root=args.capture_root,
            lane=args.lane,
            sinnix_capture_bin=args.sinnix_capture_bin,
            filename=filename,
        )
        if written_path is None:
            attempt_gate.record_failure(attempt_now)
        else:
            attempt_gate.record_success()

    try:
        while True:
            timeout = 1.0
            ready, _, _ = select.select([sock], [], [], timeout)
            if ready:
                chunk = sock.recv(65536)
                if chunk == b"":
                    print(
                        "sinnix-capture-screen: Hyprland socket2 closed",
                        file=sys.stderr,
                    )
                    return 1
                buf += chunk
                capture_for_event_burst = False
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", "replace")
                    if hypr.is_trigger_event(text):
                        capture_for_event_burst = True
                if capture_for_event_burst:
                    do_capture("hyprland-event")

            now = time.time()
            pos = hypr.get_cursor_pos(read_json)
            if pos is not None and pause_detector.sample(now, *pos):
                do_capture("idle-pause")

            if should_capture_periodic(
                now, last_capture_ts, floor_seconds=args.periodic_floor_seconds
            ):
                do_capture("periodic-floor")
    finally:
        sock.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capture-screen")
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--lane", default="screen-frames")
    # Defaults come from the environment a systemd --user service tied to
    # graphical-session.target already inherits (UWSM/Hyprland populate
    # these at session start into the user manager's own environment, the
    # same inheritance every other Hyprland-dependent user unit in this
    # repo relies on -- e.g. activitywatch-watcher-awatcher.service).
    # Explicit flags remain available for tests/manual invocation.
    parser.add_argument("--runtime-dir", default=os.environ.get("XDG_RUNTIME_DIR"))
    parser.add_argument(
        "--instance-signature", default=os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    )
    parser.add_argument("--grim-bin", default="grim")
    parser.add_argument("--hyprctl-bin", default="hyprctl")
    parser.add_argument("--sinnix-capture-bin", default="sinnix-capture")
    parser.add_argument("--periodic-floor-seconds", type=float, default=30.0)
    parser.add_argument("--idle-pause-seconds", type=float, default=3.0)
    parser.add_argument("--dedup-hamming-threshold", type=int, default=4)
    parser.add_argument("--max-width", type=int, default=1920)
    parser.add_argument("--quality", type=int, default=80)
    parser.add_argument(
        "--daily-ceiling-bytes",
        type=int,
        default=1_000_000_000,
        help="Runaway-bug backstop, not a policy cap (default: 1GB/day)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
