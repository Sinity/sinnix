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
line boundary, so the retained capture file supplies any prefix from an earlier batch.
Incomplete records need no in-memory tail and survive dispatcher restarts.

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
import os

from sinnix_lib.notify import notify_desktop

#: Only posts create a desktop popup. `notification_removed` and
#: `grant_transition` are already visible in the lake for anyone querying it;
#: mirroring a dismissal as a second popup would just be noise.
_MIRRORED_KINDS = frozenset({"notification_posted"})

_SCAN_BYTES = 64 * 1024


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


def mirror_new_events(fd: int, start: int, end: int) -> None:
    """Mirror complete records whose terminating newline was newly appended.

    Read only the acknowledged range through the same opened capture object.
    Scan in fixed-size blocks before reading records so an unfinished line,
    however many uploads it spans, never accumulates in process memory.
    Parsing remains proportional to one complete record, not the day's log.
    """
    complete_end = None
    cursor = end
    while cursor > start:
        begin = max(start, cursor - _SCAN_BYTES)
        block = os.pread(fd, cursor - begin, begin)
        if len(block) != cursor - begin:
            raise OSError("notification capture range became unavailable")
        newline = block.rfind(b"\n")
        if newline >= 0:
            complete_end = begin + newline + 1
            break
        cursor = begin
    if complete_end is None:
        return

    # A prior upload can end midway through a record. Recover its beginning
    # from retained bytes; a completed prior record is never mirrored again.
    cursor = start
    while cursor:
        begin = max(0, cursor - _SCAN_BYTES)
        block = os.pread(fd, cursor - begin, begin)
        if len(block) != cursor - begin:
            raise OSError("notification capture prefix became unavailable")
        newline = block.rfind(b"\n")
        if newline >= 0:
            cursor = begin + newline + 1
            break
        cursor = begin
    with os.fdopen(os.dup(fd), "rb") as stream:
        stream.seek(cursor)
        while stream.tell() < complete_end:
            line = stream.readline(complete_end - stream.tell())
            if not line.endswith(b"\n"):
                raise OSError("notification capture record became unavailable")
            _mirror_line(line)


def _mirror_line(line: bytes) -> None:
    line = line.strip()
    if not line:
        return
    try:
        event = json.loads(line)
    except ValueError:
        # JSON syntax, UTF-8 decoding and integer digit-limit failures
        # are record-local; raw bytes have already been captured.
        return
    if not isinstance(event, dict):
        return
    if event.get("kind") in _MIRRORED_KINDS:
        _forward(event)
