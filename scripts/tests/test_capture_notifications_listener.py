"""Notification transforms and synthetic subprocess lifecycle checks.

`scripts/sinnix-capture-notifications-listener` has no `.py` suffix (it is a
frontmatter-packaged sinnix script, executed by the shebang), so it is
loaded here via importlib.util rather than a normal package import. This
directory is not scanned by flake/script-discovery.nix (readDir there is
non-recursive and filters to `kind == "regular"` at the top level of
`scripts/`, so a subdirectory is invisible to it).
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPT_PATH = (
    Path(os.environ.get("NOTIFICATIONS_LISTENER_SCRIPT", Path(__file__).resolve().parent.parent / "sinnix-capture-notifications-listener"))
)

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
            {
                "urgency": {"type": "y", "data": 1},
                "sender-pid": {"type": "x", "data": 1297637},
            },
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


def run_monitor_fixture(tmp_path, mode):
    monitor = tmp_path / "monitor"
    monitor.write_text(f"#!{sys.executable}\n" + '''import json,os,signal,sys
mode=os.environ["MONITOR_MODE"]
if mode == "killed":
    os.kill(os.getpid(), signal.SIGKILL)
if mode in ("diagnostics", "stop"):
    if mode == "diagnostics":
        sys.stderr.write("synthetic monitor diagnostic\\n" * 10000)
        sys.stderr.flush()
    print(os.environ["NOTIFY_RECORD"], flush=True)
if mode == "stop":
    signal.pause()
sys.exit(0)
''')
    monitor.chmod(0o700)
    writer = tmp_path / "writer"
    marker = tmp_path / "forwarded.json"
    writer.write_text(f"#!{sys.executable}\nimport os,sys,pathlib\npathlib.Path(os.environ['FORWARDED']).write_text(sys.stdin.read())\n")
    writer.chmod(0o700)
    command = [sys.executable, str(SCRIPT_PATH), "--busctl-bin", str(monitor),
               "--capture-bin", str(writer), "--capture-root", str(tmp_path)]
    with subprocess.Popen(command, env=dict(os.environ, MONITOR_MODE=mode,
                          NOTIFY_RECORD=json.dumps(REAL_NOTIFY_RECORD), FORWARDED=str(marker)),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          start_new_session=True) as process:
        try:
            if mode == "stop":
                deadline = time.monotonic() + 3
                while not marker.exists():
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(command, 3)
                    time.sleep(0.01)
                process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        return process.returncode, stdout, stderr, marker


def test_unexpected_clean_monitor_exit_requests_service_restart(tmp_path):
    status, _, _, _ = run_monitor_fixture(tmp_path, "clean")
    assert status == 1


def test_unexpected_monitor_signal_requests_service_restart(tmp_path):
    status, _, _, _ = run_monitor_fixture(tmp_path, "killed")
    assert status == 1


def test_monitor_diagnostics_cannot_block_notification_forwarding(tmp_path):
    status, _, stderr, marker = run_monitor_fixture(tmp_path, "diagnostics")
    assert status == 1
    assert "synthetic monitor diagnostic" in stderr
    assert json.loads(marker.read_text())["summary"] == REAL_NOTIFY_RECORD["payload"]["data"][3]


def test_requested_listener_shutdown_is_successful(tmp_path):
    status, _, _, marker = run_monitor_fixture(tmp_path, "stop")
    assert status == 0
    assert marker.exists()
