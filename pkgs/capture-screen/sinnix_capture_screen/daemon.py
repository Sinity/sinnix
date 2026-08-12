"""sinnix-capture-screen daemon: Hyprland-event + idle-pause + 30s-floor
triggered per-window screen frame capture, p-hash deduped, WebP-encoded.

FRAME-GRAB MECHANISM (read before touching this file) -- sinnix-9pd 3.1
required "the Noctalia-native retained-screencopy path, NOT raw grim" per
the closed sinnix-xuk/sinnix-kvc black-frame bugs, with an explicit
fallback clause: "If Noctalia doesn't expose a scriptable screencopy
interface you can drive programmatically, fall back to the wlr-screencopy
protocol directly ... investigate precisely what the fix actually was
before choosing your approach." That investigation, done at authorship
time (2026-08-12):

  - Noctalia v5 (github:noctalia-dev/noctalia-shell, pinned rev
    3d7b9869) is a native C++/Qt app, not Quickshell-based. Its
    ScreenshotService (src/capture/screenshot_service.{h,cpp}) only
    exposes whole-OUTPUT and REGION capture via its IPC (`noctalia msg
    screenshot-region` / `screenshot-fullscreen [monitor|all|pick]`) --
    fire-and-forget, writes to a fixed configured directory + optional
    clipboard copy, no raw-bytes-to-stdout mode and no per-WINDOW capture
    at all (no hyprland-toplevel-export protocol is wired in its source --
    only wlr-screencopy-unstable-v1 and wlr-foreign-toplevel-management).
    There is no scriptable interface this daemon could drive per-window,
    per-trigger, at low latency, without writing to disk + clipboard side
    effects on every capture.
  - So per the bead's own fallback clause: this daemon drives `grim`
    directly. Critically, `grim` uses the SAME wlr-screencopy protocol
    Noctalia's native path uses -- the two closed bugs' fix was NOT
    "use Noctalia's binary instead of grim's", it was a Hyprland
    COMPOSITOR-side render setting: `render:keep_unmodified_copy = 1`
    (retain an unmodified SDR copy for screencopy clients) plus
    `render:use_shader_blur_blend = true`
    (modules/features/desktop/hyprland/default.nix), which sinnix-kvc's
    closure evidence shows fixed BOTH grim/grimblast raw captures AND
    Noctalia's native capture simultaneously -- sinnix-xuk's own closure
    reason states "current diagnostic grim/grimblast raw captures are
    non-black" once that setting was live. The setting is compositor-
    global, applying to any wlr-screencopy client; it is not something
    "Noctalia's binary" does that a `grim` invocation cannot. Per-window
    framing (vs. Noctalia's output/region-only granularity) is done here
    by cropping grim's capture to the focused window's geometry
    (`hyprctl activewindow -j`'s `at`/`size`), which is the same
    -g "X,Y WxH" mechanism grim already documents for slurp-driven region
    capture.

LIVE REGRESSION FOUND DURING THIS LANE'S AUTHORSHIP (2026-08-12, NOT fixed
by this change -- explicitly out of this bead's CORE-tier scope, flagged
for the coordinator/operator): re-testing on sinnix-prime live, BOTH grim
(direct `grim -o DP-3`) and Noctalia's native `noctalia msg
screenshot-fullscreen` currently produce solid single-color frames again.
`hyprland.log` shows the exact sinnix-xuk GBM error signature reappearing:
"GBM: Failed to allocate a GBM buffer: format XR30 isn't supported by
primary backend" / "Couldn't allocate a gbm buffer ... format XR30" --
live, right now, on this host, with `render:keep_unmodified_copy=1` and
`render:use_shader_blur_blend=true` both confirmed still set
(`hyprctl getoption`). This means the compositor-side fix that closed
sinnix-xuk/sinnix-kvc is not currently holding -- either an intermittent
recurrence of the same upstream Hyprland/NVIDIA HDR screencopy issue those
bugs already documented as "not fully resolved" upstream, or a fresh
regression. This daemon does NOT attempt to fix that live GPU/compositor
bug (out of scope, needs a dedicated operator-present session per
sinnix-xuk's own guidance); instead `is_degenerate_frame()` (hashing.py)
refuses to persist a flat/single-color frame and this module logs loudly
and counts it as a capture-attempt failure rather than silently writing
black frames into the lake forever. See the worker report for the full
live evidence (hyprland.log excerpt, `identify -verbose` stats).

TYPING-PAUSE TRIGGER: the bead allows "a simple idle-detection heuristic
... don't over-engineer this" if a Phase-1-style input-dynamics signal
isn't cheaply available. It wasn't, cheaply, here: `libinput debug-events`
(what sinnix-capture-input-dynamics uses) needs to open
/dev/input/event*, which is only unprivileged for a systemd --user service
tied to the active graphical session's logind seat ACL -- duplicating that
whole daemon's subprocess/permission shape inside capture-screen just for
a coarse pause signal would be exactly the over-engineering the bead
warns against. Instead this daemon polls `hyprctl cursorpos` (already
being called for other reasons) once per loop tick and fires
`hashing.PauseDetector` when the cursor has been stationary for
`--idle-pause-seconds`. This approximates "user stopped interacting", not
literally "user stopped typing"; a keystroke-timed version is a natural
follow-up once/if this daemon is rebuilt on the shared sinnix-capture
input primitives.
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
    last_hash_by_window: dict[str, int] = {}
    last_capture_ts: float | None = None
    seq = 0
    buf = b""

    def do_capture(trigger: str) -> None:
        nonlocal last_capture_ts, seq
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
            return

        geometry = window.get("geometry") if window else {}
        grim_geometry = None
        if window and all(
            geometry.get(k) is not None for k in ("x", "y", "width", "height")
        ):
            grim_geometry = f"{geometry['x']},{geometry['y']} {geometry['width']}x{geometry['height']}"

        png_bytes = capture.run_grim(args.grim_bin, monitor_name, grim_geometry)
        if png_bytes is None:
            print(
                f"sinnix-capture-screen: grim capture failed (trigger={trigger})",
                file=sys.stderr,
            )
            return

        im = capture.load_image(png_bytes)
        gray = capture.image_to_phash_array(im)
        if is_degenerate_frame(gray):
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
        capture.write_frame(
            payload=payload,
            webp_bytes=webp_bytes,
            capture_root=args.capture_root,
            lane=args.lane,
            sinnix_capture_bin=args.sinnix_capture_bin,
            filename=filename,
        )

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
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", "replace")
                    if hypr.is_trigger_event(text):
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
