from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _collector():
    path = Path(__file__).resolve().parents[1] / "collector.py"
    spec = importlib.util.spec_from_file_location(
        "capture_input_dynamics_collector", path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register in sys.modules before exec: the collector module uses
    # `from __future__ import annotations` (string annotations), and
    # @dataclass resolves those by looking the module up in
    # sys.modules[cls.__module__] -- without this it AttributeErrors on a
    # None module during WindowAccumulator's dataclass processing.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# A hand-constructed sample shaped like real `libinput debug-events` output:
# a user typing the word "HELLO" (deliberately distinctive so a leak would
# be easy to spot in an assertion), one mouse click, and a couple of
# pointer moves interleaved with an ignored device-management line.
SAMPLE_WINDOW_LINES = [
    " event9   DEVICE_ADDED      Logitech G502            seat0 default group1  cap:kpm",
    " event9   KEYBOARD_KEY      +8.900s    KEY_H (35) pressed",
    " event9   KEYBOARD_KEY      +8.950s    KEY_H (35) released",
    " event9   KEYBOARD_KEY      +9.020s    KEY_E (18) pressed",
    " event9   KEYBOARD_KEY      +9.060s    KEY_E (18) released",
    " event9   KEYBOARD_KEY      +9.140s    KEY_L (38) pressed",
    " event9   KEYBOARD_KEY      +9.180s    KEY_L (38) released",
    " event9   KEYBOARD_KEY      +9.260s    KEY_L (38) pressed",
    " event9   KEYBOARD_KEY      +9.300s    KEY_L (38) released",
    " event9   KEYBOARD_KEY      +9.380s    KEY_O (24) pressed",
    " event9   KEYBOARD_KEY      +9.420s    KEY_O (24) released",
    " event7   POINTER_MOTION    +9.500s    -1.00/  2.00 (-1.00/  2.00 unaccelerated)",
    " event7   POINTER_MOTION    +9.520s    -1.00/  2.00 (-1.00/  2.00 unaccelerated)",
    " event7   POINTER_BUTTON    +9.600s    BTN_LEFT (272) pressed, seat count: 1",
    " event7   POINTER_BUTTON    +9.650s    BTN_LEFT (272) released, seat count: 0",
]

# The raw key-name/keycode tokens present in the fixture above. If any of
# these ever appears in a produced window's JSON, the structural
# no-keystroke-content guarantee has been violated.
_KEY_IDENTITY_TOKENS = [
    "KEY_H",
    "KEY_E",
    "KEY_L",
    "KEY_O",
    "(35)",
    "(18)",
    "(38)",
    "(24)",
]


def test_parse_debug_event_line_keyboard_key_press() -> None:
    collector = _collector()

    parsed = collector.parse_debug_event_line(
        " event9   KEYBOARD_KEY      +8.900s    KEY_H (35) pressed"
    )

    assert parsed == ("KEYBOARD_KEY", 8.900, True)


def test_parse_debug_event_line_keyboard_key_release() -> None:
    collector = _collector()

    parsed = collector.parse_debug_event_line(
        " event9   KEYBOARD_KEY      +8.950s    KEY_H (35) released"
    )

    assert parsed == ("KEYBOARD_KEY", 8.950, False)


def test_parse_debug_event_line_pointer_motion() -> None:
    collector = _collector()

    parsed = collector.parse_debug_event_line(
        " event7   POINTER_MOTION    +9.500s    -1.00/  2.00 (-1.00/  2.00 unaccelerated)"
    )

    assert parsed == ("POINTER_MOTION", 9.500, None)


def test_parse_debug_event_line_pointer_button_press() -> None:
    collector = _collector()

    parsed = collector.parse_debug_event_line(
        " event7   POINTER_BUTTON    +9.600s    BTN_LEFT (272) pressed, seat count: 1"
    )

    assert parsed == ("POINTER_BUTTON", 9.600, True)


def test_parse_debug_event_line_ignores_device_management_lines() -> None:
    collector = _collector()

    parsed = collector.parse_debug_event_line(
        " event9   DEVICE_ADDED      Logitech G502            seat0 default group1  cap:kpm"
    )

    assert parsed is None


def test_build_window_from_lines_produces_one_aggregated_window() -> None:
    """Feed a batch of raw libinput-debug-events-shaped lines through the
    real parsing + aggregation path and check the resulting window matches
    hand-counted expectations -- this is the "one aggregated window from
    raw events" verification the mission asked for."""
    collector = _collector()

    window = collector.build_window_from_lines(
        SAMPLE_WINDOW_LINES,
        timestamp=1234567890.0,
        per_window={"class": "kitty", "title": "zsh", "workspace": "1"},
    )

    assert window["timestamp"] == 1234567890.0
    assert window["keystroke_count"] == 5  # H E L L O presses only, not releases
    assert window["pointer_move_count"] == 2
    assert window["pointer_click_count"] == 1  # BTN_LEFT press only, not release
    assert window["per_window"] == {"class": "kitty", "title": "zsh", "workspace": "1"}

    # Inter-keystroke intervals: 8.900 -> 9.020 -> 9.140 -> 9.260 -> 9.380
    # (press timestamps only), i.e. four 120ms gaps.
    assert window["key_interval_mean_ms"] is not None
    assert abs(window["key_interval_mean_ms"] - 120.0) < 1e-6
    assert window["key_interval_stddev_ms"] is not None
    assert abs(window["key_interval_stddev_ms"] - 0.0) < 1e-6


def test_build_window_from_lines_never_leaks_key_identity() -> None:
    """The structural guarantee, demonstrated: serialize the produced
    window and confirm none of the raw key-name/keycode tokens present in
    the input survive into it. A mutation that started threading
    parts[3]/parts[4] (the key name/code) into WindowAccumulator or
    to_window() would make this test fail."""
    collector = _collector()

    window = collector.build_window_from_lines(
        SAMPLE_WINDOW_LINES, timestamp=1234567890.0, per_window=None
    )
    serialized = json.dumps(window)

    for token in _KEY_IDENTITY_TOKENS:
        assert token not in serialized, (
            f"key-identity token {token!r} leaked into output window"
        )

    # Nothing spells out "HELLO" either, whether concatenated from
    # per-key letters or embedded as a substring of some derived field.
    assert "HELLO" not in serialized.upper()


def test_window_accumulator_single_keystroke_has_no_interval_stats() -> None:
    collector = _collector()

    acc = collector.WindowAccumulator()
    acc.record_key(1.0)
    window = acc.to_window(timestamp=1.0, per_window=None)

    assert window["keystroke_count"] == 1
    assert window["key_interval_mean_ms"] is None
    assert window["key_interval_stddev_ms"] is None


def test_window_accumulator_has_activity() -> None:
    collector = _collector()

    idle = collector.WindowAccumulator()
    assert idle.has_activity is False

    moved = collector.WindowAccumulator()
    moved.record_motion()
    assert moved.has_activity is True


def test_get_active_window_parses_hyprctl_json() -> None:
    collector = _collector()

    result = collector.get_active_window(
        lambda: json.dumps(
            {"class": "kitty", "title": "zsh", "workspace": {"id": 1, "name": "1"}}
        )
    )

    assert result == {"class": "kitty", "title": "zsh", "workspace": "1"}


def test_get_active_window_handles_failure() -> None:
    collector = _collector()

    assert collector.get_active_window(lambda: None) is None


def test_get_active_window_handles_invalid_json() -> None:
    collector = _collector()

    assert collector.get_active_window(lambda: "not json") is None


def test_write_window_shells_out_to_sinnix_capture(monkeypatch, tmp_path) -> None:
    collector = _collector()

    calls: list[list[str]] = []
    payloads: list[str] = []

    class FakeCompletedProcess:
        returncode = 0
        stderr = ""

    def fake_run(cmd, input=None, text=None, capture_output=None):  # noqa: A002
        calls.append(cmd)
        payloads.append(input)
        return FakeCompletedProcess()

    monkeypatch.setattr(collector.subprocess, "run", fake_run)

    window = {"timestamp": 1.0, "keystroke_count": 0}
    collector.write_window(window, tmp_path, "sinnix-capture")

    assert calls == [
        [
            "sinnix-capture",
            "write",
            "--capture-root",
            str(tmp_path),
            "--lane",
            "input-dynamics",
        ]
    ]
    assert json.loads(payloads[0]) == window
