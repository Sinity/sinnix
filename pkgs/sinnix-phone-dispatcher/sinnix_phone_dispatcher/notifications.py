"""Mirroring the phone's notifications onto the desktop.

The events plane (`POST /events`, `uploads.append_events`) is already the
arrival hook for everything the app's screens produce, including
`PhoneNotificationListener`'s post/dismiss stream (docs/phone.md,
"Notifications" -- `app`/`title`/`text`/`posted_at`/`ongoing`/`clearable`/
`key`, plus `grant_transition` on connect/disconnect). A `notification_posted`
line is itself the whole record; nothing here re-reads dumpsys or asks the
phone anything else, and nothing here is a second daemon -- this is a plain
function called from the write path, the same shape as
`external.trigger_score`. The desktop half reuses the one notify-send helper
every other unit already shares (`sinnix_lib.notify.notify_desktop`) rather
than re-implementing the D-Bus/session-bus dance.

Only genuinely NEW bytes are ever scanned -- `append_events` already resolves
a replayed or partially-overlapping batch, and this must not re-notify for a
line it already handled. A batch's byte boundary has no reason to land on a
line boundary, so a small per-day tail buffer holds an undecoded trailing
partial line until the batch that completes it arrives.

`ongoing` notifications are dropped rather than mirrored. Measured live
2026-08-18: 230 of 240 `notification_posted` events on an ordinary day were
Termux's own persistent session notification, reposted on every content tick
(`ongoing: true`) -- an unfiltered relay would have made the desktop mirror
useless noise before it delivered a single real message. Android's own
`ongoing` flag is exactly the signal that separates "a foreground service's
running status" from "something happened"; every one of the real
notifications sampled from the same day (Gmail, Twitter, SMS) carried
`ongoing: false`.
"""

from __future__ import annotations

import json
import sys
import threading

from sinnix_lib.notify import notify_desktop

#: Only posts create a desktop popup. `notification_removed` and
#: `grant_transition` are already visible in the lake for anyone querying it;
#: mirroring a dismissal as a second popup would just be noise.
_MIRRORED_KINDS = frozenset({"notification_posted"})

_lock = threading.Lock()
_tail_by_day: dict[str, bytes] = {}


def _forward(event: dict) -> None:
    if event.get("ongoing"):
        # A foreground service's persistent status line, not an event -- see
        # the module docstring for why this is not a corner case to special-
        # case later, it is the majority of the stream.
        return
    app = str(event.get("app") or "").strip()
    title = str(event.get("title") or "").strip() or "(no title)"
    text = str(event.get("text") or "")
    heading = f"{app}: {title}" if app else title
    try:
        notify_desktop(heading, text, app_name="sinnix-phone")
    except Exception as exc:  # noqa: BLE001 - advisory; must not break ingestion
        print(
            f"phone-dispatcher: notifications: forward failed: {exc}", file=sys.stderr
        )


def mirror_new_events(day: str, new_bytes: bytes) -> None:
    """Scan bytes newly landed in a day's event file, mirroring any
    `notification_posted` line to the desktop.

    Call with exactly the suffix of the file this write actually added, not
    the whole batch -- a batch may repeat bytes already handled (a retried
    upload, a rewound overlap), and re-notifying for those would pop a
    duplicate desktop notification for every retry.
    """
    if not new_bytes:
        return
    with _lock:
        buf = _tail_by_day.pop(day, b"") + new_bytes
        lines = buf.split(b"\n")
        # The last element is either b"" (buf ended cleanly on a newline) or
        # an undecoded tail -- either way it is not a line to parse yet.
        tail = lines.pop()
        if tail:
            _tail_by_day[day] = tail
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("kind") in _MIRRORED_KINDS:
            _forward(event)
