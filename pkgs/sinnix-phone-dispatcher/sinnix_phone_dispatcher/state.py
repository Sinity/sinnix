"""Shared constants, directories, and receipt/notify writers.

The receipt/notify/push JSON on disk keeps its original (non-compact,
non-sorted) formatting exactly, so it stays byte-for-byte what the drain and
the phone app already parse -- this is the on-disk-format boundary
sinnix_lib.atomic_json does not cross for this package (see pkg.nix).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import uuid
from pathlib import Path

SCHEMA = "sinnix.phone.receipt/1"

STATE_DIR = Path(os.environ.get("SINNIX_PHONE_STATE_DIR", "/realm/state/sinnix-phone"))
LAKE_ROOT = Path(os.environ.get("SINNIX_PHONE_LAKE", "/realm/data/machine/phone"))

# What prime has waiting for the device. The app FETCHES this over
# /phone/v1/inbox on its own cadence and confirms each one-shot it landed;
# nothing on this side pushes it anywhere. A receipt written here while the
# phone is in a pocket on the other side of the city is a receipt the phone
# collects when it next has a network, which is the same durability the
# outbound direction gets from the app's spool.
INBOX_DIR = STATE_DIR / "inbox"
RECEIPTS_DIR = INBOX_DIR / "receipts"
NOTIFY_DIR = INBOX_DIR / "notify"
DECKS_DIR = INBOX_DIR / "decks"

# Executed tokens, one file each. A directory rather than a database because
# the only query is "have I seen this", the only write is "now I have", and a
# filesystem answers both atomically.
TOKENS_DIR = STATE_DIR / "tokens"

MAX_BODY = 8 << 20  # a shared image can be large; an intent never is

# Bulk capture files the phone uploads itself, rather than waiting to be
# pulled. A 5-minute ambient chunk is ~3.6 MB; the cap is generous enough for
# a long orphan recovered after a crash and small enough that a confused
# client cannot fill the disk in one request.
MAX_UPLOAD = 128 << 20

# Where an upload may land, keyed by the lane the phone names. An allowlist
# rather than a path parameter: the phone chooses the file NAME, and a client
# that could also choose the directory could write anywhere this service can.
UPLOAD_LANES = {
    "ambient": LAKE_ROOT / "ambient",
    "camera": LAKE_ROOT / "camera",
    "download": LAKE_ROOT / "download",
    # Voice notes, PPG/IMU traces and shared files, with their metadata
    # sidecars. `sinnix-score` reads this directory by the same name.
    "outbox": LAKE_ROOT / "outbox",
}

# The app's own event log. Not an UPLOAD_LANE: a day file is appended to all
# day rather than finalized, so it arrives as byte ranges through /events
# (uploads.append_events) instead of as a whole file through /chunk.
EVENTS_DIR = LAKE_ROOT / "events"

EVENTS_DAY_RE = re.compile(r"^\d{8}$")

# A batch is a slice of a day file, sized by the phone. Generous next to the
# 512 KiB the app actually ships, and far below MAX_UPLOAD: a client that
# thinks it can hand over a 3.5 GB day file in one request (one exists, from
# a Health Connect backfill) should be told no by a number rather than by the
# machine running out of memory.
MAX_EVENT_BATCH = 8 << 20

# One path segment of an upload name. Chunk names are minted by the app from
# a UTC stamp (`ambient-20260817T103201Z.m4a`, `.orphan` when a crash
# truncated one) and would fit a far tighter pattern, but the same check now
# guards the mirror lanes, where the segments are whatever the operator's own
# camera, browser and file manager wrote -- `Samsung Health`, `IMG_20260817
# (1).jpg`. The characters that matter are the ones NOT here: no separator,
# and a first character that cannot begin `.` or `..`, which is what makes a
# traversing name impossible rather than filtered.
UPLOAD_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@,+()'!&#=~-]{0,127}$")

TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for d in (RECEIPTS_DIR, NOTIFY_DIR, DECKS_DIR, TOKENS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def emit_receipt(
    kind: str, title: str, body: str, send_token: str | None, route: str | None = None
) -> None:
    """Leave a receipt for the phone.

    Written into the push directory rather than sent anywhere: the phone may be
    off the tailnet, asleep, or out of the house, and a receipt is exactly the
    kind of message that must survive all three. The drain delivers it and the
    app deletes it once shown.
    """
    ensure_dirs()
    name = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}.json"
    payload = {
        "schema": SCHEMA,
        "kind": kind,
        "title": title,
        "body": body,
        "send_token": send_token,
        "route": route,
        "at": now_iso(),
    }
    tmp = RECEIPTS_DIR / (name + ".part")
    tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    tmp.rename(RECEIPTS_DIR / name)


def notify_phone(title: str, body: str, route: str | None = None) -> None:
    """Interrupt the operator through the phone. Sent by prime itself, not by an intent."""
    ensure_dirs()
    name = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}.json"
    payload = {
        "schema": SCHEMA,
        "title": title,
        "body": body,
        "route": route,
        "at": now_iso(),
    }
    tmp = NOTIFY_DIR / (name + ".part")
    tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    tmp.rename(NOTIFY_DIR / name)
