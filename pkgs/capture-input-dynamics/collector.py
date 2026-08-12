"""sinnix-capture-input-dynamics: 1Hz aggregated pointer/keyboard timing.

STRUCTURAL PRIVACY GUARANTEE -- read before touching this file.

This lane observes `libinput debug-events` timing ONLY. It must be
structurally incapable of reconstructing what was typed; keystroke
*content* belongs exclusively to scribe-tap, a separate capture lane. The
guarantee is enforced by construction, not by convention, in two places:

  1. `parse_debug_event_line()` is the only place raw event text is
     touched. For a KEYBOARD_KEY line such as::

         event9   KEYBOARD_KEY      +8.923s    KEY_A (30) pressed

     splitting on whitespace gives
     ``["event9", "KEYBOARD_KEY", "+8.923s", "KEY_A", "(30)", "pressed"]``.
     Only `parts[1]` (event type) and `parts[2]` (timestamp) are ever bound
     to a variable that survives the call. The key-identity tokens
     (`parts[3]`, `parts[4]`) are never read, never assigned, and never
     passed to any function -- there is no code path in this file that can
     reach them. The only other token read is `parts[-1]`, the bare
     press/release STATE word, which carries no identity information.
     (POINTER_BUTTON lines are handled similarly: the state word isn't at
     a fixed index, so parts[3:] is scanned for it, but only the two
     literal words "pressed"/"released" are ever compared and returned --
     the button-identity tokens are discarded by never being bound to a
     variable that outlives the comparison.)
     Verify by inspection: grep this file for `parts[3]` or `parts[4]` --
     the only reference is the read-and-discard scan just described.

  2. `WindowAccumulator` (the aggregation state) only ever holds integer
     counters and a list of bare `float` timestamps (`_key_times`), used
     solely to compute inter-keystroke interval statistics. It has no
     field capable of holding a string, a key name, or an ordered
     sequence of distinct symbols -- so even a mis-wired caller could not
     smuggle key identity through it. `to_window()` (the only function
     that turns accumulator state into the JSON payload eventually
     written to disk) enumerates every field explicitly; there is no
     `**dict`/`vars()` passthrough that could leak an accidentally-added
     attribute.

A future reader changing this file should preserve both properties: never
bind `parts[3:]` from a KEYBOARD_KEY line to anything, and never add a
string-valued field to `WindowAccumulator` or `to_window()`'s output.
"""

from __future__ import annotations

import argparse
import json
import re
import select
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

TIMESTAMP_RE = re.compile(r"^\+?(\d+(?:\.\d+)?)s$")

# Event types this lane aggregates. Anything else (DEVICE_ADDED,
# DEVICE_REMOVED, POINTER_SCROLL_*, GESTURE_*, TABLET_*, ...) is ignored --
# out of scope for keyboard/pointer timing, not silently miscounted.
_KEYBOARD_KEY = "KEYBOARD_KEY"
_POINTER_BUTTON = "POINTER_BUTTON"
_POINTER_MOTION = "POINTER_MOTION"
_POINTER_MOTION_ABSOLUTE = "POINTER_MOTION_ABSOLUTE"


ParsedEvent = tuple[str, float, Optional[bool]]
"""(event_type, seconds_since_libinput_start, pressed_or_None)."""


def parse_debug_event_line(line: str) -> ParsedEvent | None:
    """Extract (event_type, timestamp, pressed) from one debug-events line.

    Returns None for event types this lane does not aggregate. See the
    module docstring for the structural guarantee this function upholds:
    it never reads a key-identity token.
    """
    parts = line.split()
    if len(parts) < 3:
        return None
    event_type = parts[1]
    ts_match = TIMESTAMP_RE.match(parts[2])
    if ts_match is None:
        return None
    ts = float(ts_match.group(1))

    if event_type == _KEYBOARD_KEY:
        # parts[3]/parts[4] hold the key name/code -- deliberately never
        # read (see module docstring). parts[-1] is the bare state word.
        pressed = parts[-1] == "pressed"
        return (_KEYBOARD_KEY, ts, pressed)
    if event_type == _POINTER_BUTTON:
        # The state word ("pressed," / "released,") is not at a fixed
        # index -- the line continues with ", seat count: N" -- so this
        # scans parts[3:] for it. Every token is transiently compared
        # against the two literal state words and discarded; the button
        # identity tokens (e.g. "BTN_LEFT", "(272)") are never bound to a
        # variable, returned, or retained anywhere -- only the boolean
        # press/release state survives this function.
        state_words = {token.rstrip(",") for token in parts[3:]}
        if "pressed" in state_words:
            pressed = True
        elif "released" in state_words:
            pressed = False
        else:
            return None
        return (_POINTER_BUTTON, ts, pressed)
    if event_type in (_POINTER_MOTION, _POINTER_MOTION_ABSOLUTE):
        return (_POINTER_MOTION, ts, None)
    return None


@dataclass
class WindowAccumulator:
    """Aggregation state for one 1Hz feature window.

    Every field is a counter or a list of bare floats. See the module
    docstring: this shape is what makes key-identity leakage structurally
    impossible, not just discouraged.
    """

    keystroke_count: int = 0
    pointer_move_count: int = 0
    pointer_click_count: int = 0
    _key_times: list[float] = field(default_factory=list)

    def record_key(self, ts: float) -> None:
        self.keystroke_count += 1
        self._key_times.append(ts)

    def record_click(self) -> None:
        self.pointer_click_count += 1

    def record_motion(self) -> None:
        self.pointer_move_count += 1

    @property
    def has_activity(self) -> bool:
        return bool(
            self.keystroke_count or self.pointer_move_count or self.pointer_click_count
        )

    def interval_stats_ms(self) -> tuple[float | None, float | None]:
        if len(self._key_times) < 2:
            return (None, None)
        deltas_ms = [
            (b - a) * 1000.0
            for a, b in zip(self._key_times, self._key_times[1:], strict=False)
        ]
        mean_ms = statistics.fmean(deltas_ms)
        stddev_ms = statistics.pstdev(deltas_ms) if len(deltas_ms) > 1 else 0.0
        return (mean_ms, stddev_ms)

    def to_window(self, timestamp: float, per_window: dict | None) -> dict:
        mean_ms, stddev_ms = self.interval_stats_ms()
        return {
            "timestamp": timestamp,
            "keystroke_count": self.keystroke_count,
            "key_interval_mean_ms": mean_ms,
            "key_interval_stddev_ms": stddev_ms,
            "pointer_move_count": self.pointer_move_count,
            "pointer_click_count": self.pointer_click_count,
            "per_window": per_window,
        }


def handle_line(line: str, acc: WindowAccumulator) -> None:
    """Feed one raw debug-events line into an accumulator."""
    parsed = parse_debug_event_line(line)
    if parsed is None:
        return
    event_type, ts, pressed = parsed
    if event_type == _KEYBOARD_KEY:
        if pressed:
            acc.record_key(ts)
    elif event_type == _POINTER_BUTTON:
        if pressed:
            acc.record_click()
    elif event_type == _POINTER_MOTION:
        acc.record_motion()


def build_window_from_lines(
    lines: Iterable[str], timestamp: float, per_window: dict | None
) -> dict:
    """Aggregate a batch of raw debug-events lines into one feature window.

    Pure helper shared by the live collector loop and by tests: given the
    raw lines observed during one window, produce exactly the JSON-shaped
    dict this lane writes via `sinnix-capture write`.
    """
    acc = WindowAccumulator()
    for line in lines:
        handle_line(line, acc)
    return acc.to_window(timestamp, per_window)


def get_active_window(run_hyprctl: Callable[[], str | None]) -> dict | None:
    """Resolve the current per-window attribution via `hyprctl activewindow -j`.

    `run_hyprctl` is injected so this is testable without a live Hyprland
    session; it should return the raw JSON text or None on failure.
    """
    raw = run_hyprctl()
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    workspace = data.get("workspace")
    return {
        "class": data.get("class"),
        "title": data.get("title"),
        "workspace": workspace.get("name") if isinstance(workspace, dict) else None,
    }


def _hyprctl_reader(hyprctl_bin: str) -> Callable[[], str | None]:
    def _read() -> str | None:
        try:
            proc = subprocess.run(
                [hyprctl_bin, "activewindow", "-j"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return proc.stdout

    return _read


def write_window(window: dict, capture_root: Path, sinnix_capture_bin: str) -> None:
    """Hand one aggregated window to the sinnix-capture writer over stdin.

    `window` is exactly the dict produced by `to_window()`/
    `build_window_from_lines()` above -- structurally free of key
    identity, so there is nothing to redact here.
    """
    proc = subprocess.run(
        [
            sinnix_capture_bin,
            "write",
            "--capture-root",
            str(capture_root),
            "--lane",
            "input-dynamics",
        ],
        input=json.dumps(window),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        print(
            f"sinnix-capture-input-dynamics: write failed (exit {proc.returncode}): {proc.stderr.strip()}",
            file=sys.stderr,
        )


def run(args: argparse.Namespace) -> int:
    cmd = [args.libinput_bin, "debug-events"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, bufsize=1)
    assert proc.stdout is not None
    read_hyprctl = _hyprctl_reader(args.hyprctl_bin)
    acc = WindowAccumulator()
    next_flush = time.time() + args.window_seconds
    try:
        while True:
            timeout = max(0.0, next_flush - time.time())
            ready, _, _ = select.select([proc.stdout], [], [], timeout)
            if ready:
                line = proc.stdout.readline()
                if line == "":
                    # libinput exited (device revoked, process killed, ...).
                    break
                handle_line(line, acc)
            now = time.time()
            if now >= next_flush:
                if acc.has_activity:
                    window = acc.to_window(next_flush, get_active_window(read_hyprctl))
                    write_window(window, args.capture_root, args.sinnix_capture_bin)
                acc = WindowAccumulator()
                next_flush += args.window_seconds
        return proc.wait()
    finally:
        if proc.poll() is None:
            proc.terminate()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capture-input-dynamics")
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--libinput-bin", default="libinput")
    parser.add_argument("--hyprctl-bin", default="hyprctl")
    parser.add_argument("--sinnix-capture-bin", default="sinnix-capture")
    parser.add_argument("--window-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
