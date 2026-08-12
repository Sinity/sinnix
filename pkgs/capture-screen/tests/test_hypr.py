from __future__ import annotations

import json

from sinnix_capture_screen.hypr import (
    get_active_window,
    get_cursor_pos,
    get_monitors,
    is_trigger_event,
    monitor_name_for_id,
    socket2_path,
)


def test_is_trigger_event_true_for_window_and_workspace_changes() -> None:
    assert is_trigger_event("activewindowv2>>6320d2725bf0") is True
    assert is_trigger_event("workspace>>2") is True
    assert is_trigger_event("focusedmon>>DP-3,2") is True
    assert is_trigger_event("openwindow>>abc,1,kitty,sinex") is True
    assert is_trigger_event("fullscreen>>1") is True


def test_is_trigger_event_false_for_high_frequency_noise() -> None:
    # moveresize/activelayout fire multiple times per second during a drag
    # or layout switch -- must NOT be trigger events, or event-driven
    # capture degenerates into continuous polling.
    assert is_trigger_event("moveresize>>1,100,100,50,50") is False
    assert is_trigger_event("activelayout>>keyboard,us") is False
    assert is_trigger_event("") is False
    assert is_trigger_event("garbage line") is False


def test_socket2_path_shape() -> None:
    path = socket2_path("/run/user/1000", "abc123")
    assert path == "/run/user/1000/hypr/abc123/.socket2.sock"


def test_get_active_window_parses_class_title_workspace_geometry() -> None:
    raw = json.dumps(
        {
            "class": "kitty",
            "title": "sinex",
            "workspace": {"id": 1, "name": "1"},
            "monitor": 0,
            "at": [1933, 23],
            "size": [1884, 2053],
        }
    )
    window = get_active_window(lambda args: raw)
    assert window == {
        "class": "kitty",
        "title": "sinex",
        "workspace": "1",
        "monitor_id": 0,
        "geometry": {"x": 1933, "y": 23, "width": 1884, "height": 2053},
    }


def test_get_active_window_returns_none_on_empty_desktop() -> None:
    # hyprctl activewindow -j returns `{}` when no window is focused.
    assert get_active_window(lambda args: "{}") is None


def test_get_active_window_returns_none_when_hyprctl_unreachable() -> None:
    assert get_active_window(lambda args: None) is None


def test_get_active_window_returns_none_on_malformed_json() -> None:
    assert get_active_window(lambda args: "not json") is None


def test_get_monitors_parses_list() -> None:
    raw = json.dumps([{"id": 0, "name": "DP-3", "width": 3840, "height": 2160}])
    monitors = get_monitors(lambda args: raw)
    assert monitors == [{"id": 0, "name": "DP-3", "width": 3840, "height": 2160}]


def test_get_monitors_empty_on_failure() -> None:
    assert get_monitors(lambda args: None) == []


def test_monitor_name_for_id_matches() -> None:
    monitors = [{"id": 0, "name": "DP-3"}, {"id": 1, "name": "HDMI-A-1"}]
    assert monitor_name_for_id(monitors, 1) == "HDMI-A-1"


def test_monitor_name_for_id_none_when_missing() -> None:
    assert monitor_name_for_id([{"id": 0, "name": "DP-3"}], 5) is None


def test_get_cursor_pos_parses_xy() -> None:
    assert get_cursor_pos(lambda args: json.dumps({"x": 1441, "y": 1209})) == (
        1441,
        1209,
    )


def test_get_cursor_pos_none_on_missing_fields() -> None:
    assert get_cursor_pos(lambda args: json.dumps({"x": 1441})) is None


def test_get_cursor_pos_none_on_failure() -> None:
    assert get_cursor_pos(lambda args: None) is None
