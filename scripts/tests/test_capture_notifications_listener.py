"""Unit tests for the notifications-capture listener's pure transform logic.

`scripts/sinnix-capture-notifications-listener` has no `.py` suffix (it is a
frontmatter-packaged sinnix script, executed by the shebang), so it is
loaded here via importlib.util rather than a normal package import. This
directory is not scanned by flake/script-discovery.nix (readDir there is
non-recursive and filters to `kind == "regular"` at the top level of
`scripts/`, so a subdirectory is invisible to it).
"""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "sinnix-capture-notifications-listener"

# The script has no `.py` suffix (it is a frontmatter-packaged sinnix
# script executed by its shebang), so importlib can't infer a loader from
# the extension -- build one explicitly.
_loader = SourceFileLoader("sinnix_capture_notifications_listener", str(SCRIPT_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec is not None
listener = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = listener
_loader.exec_module(listener)


# A real record captured live via `busctl --user monitor --json=short
# org.freedesktop.Notifications` while `notify-send "Sinnix Test" "capture-
# notifications probe body"` ran, trimmed to the fields the parser reads.
REAL_NOTIFY_RECORD = {
    "type": "method_call",
    "cookie": 9,
    "timestamp-realtime": 1786527275201630,
    "sender": ":1.7581",
    "destination": ":1.2444",
    "path": "/org/freedesktop/Notifications",
    "interface": "org.freedesktop.Notifications",
    "member": "Notify",
    "payload": {
        "type": "susssasa{sv}i",
        "data": [
            "notify-send",
            0,
            "",
            "Sinnix Test",
            "capture-notifications probe body",
            [],
            {"urgency": {"type": "y", "data": 1}, "sender-pid": {"type": "x", "data": 1297637}},
            -1,
        ],
    },
}


def test_notify_payload_extracts_the_documented_fields():
    payload = listener.notify_payload(REAL_NOTIFY_RECORD)
    assert payload is not None
    assert payload["app_name"] == "notify-send"
    assert payload["summary"] == "Sinnix Test"
    assert payload["body"] == "capture-notifications probe body"
    assert payload["urgency"] == 1
    assert payload["actions"] == []
    assert payload["timestamp"] == 1786527275.20163
    assert payload["hints"] == {"urgency": 1, "sender-pid": 1297637}
    assert payload["sender"] == ":1.7581"


def test_notify_payload_ignores_non_notify_calls():
    other = dict(REAL_NOTIFY_RECORD, member="GetServerInformation")
    assert listener.notify_payload(other) is None

    signal = dict(REAL_NOTIFY_RECORD, type="signal", member="NotificationClosed")
    assert listener.notify_payload(signal) is None

    other_iface = dict(REAL_NOTIFY_RECORD, interface="org.freedesktop.DBus")
    assert listener.notify_payload(other_iface) is None


def test_notify_payload_rejects_malformed_argument_count():
    truncated = dict(REAL_NOTIFY_RECORD)
    truncated["payload"] = {"type": "s", "data": ["only-app-name"]}
    assert listener.notify_payload(truncated) is None


def test_pair_actions_pairs_id_label_and_tolerates_odd_length():
    assert listener._pair_actions(["default", "Open", "close", "Dismiss"]) == [
        {"id": "default", "label": "Open"},
        {"id": "close", "label": "Dismiss"},
    ]
    # Odd-length array from a misbehaving sender must not raise.
    assert listener._pair_actions(["default", "Open", "orphan"]) == [
        {"id": "default", "label": "Open"},
    ]
    assert listener._pair_actions([]) == []


def test_hint_value_handles_missing_and_present_hints():
    hints = {"urgency": {"type": "y", "data": 2}}
    assert listener._hint_value(hints, "urgency") == 2
    assert listener._hint_value(hints, "missing") is None
    assert listener._hint_value({}, "urgency") is None
