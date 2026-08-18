"""The phone's own uploads: whole capture files (ambient audio, camera,
Downloads, outbox blobs) and byte ranges of the app's event log.

Two shapes because the data has two shapes. A closed chunk is immutable and
arrives once; a day file is appended to for twenty-four hours and has to
arrive continuously, which a route keyed by file name cannot express. What
they share is the part that matters -- the sender declares a sha256 over the
bytes it still holds, prime verifies before the write is visible, and a
repeat of something already landed answers ok rather than a conflict, because
the phone deletes its copy on an ok and retries on anything else.
"""

from __future__ import annotations

import hashlib
import os
from http import HTTPStatus
from pathlib import Path

from .state import (
    EVENTS_DAY_RE,
    EVENTS_DIR,
    MAX_EVENT_BATCH,
    UPLOAD_LANES,
    UPLOAD_NAME_RE,
    now_iso,
)


def store_upload(lane: str, name: str, body: bytes, declared_sha: str | None) -> tuple[HTTPStatus, dict]:
    """Land a capture file the phone pushed, or say precisely why not.

    This is the phone's own half of the ambient archive: the app uploads a
    chunk as soon as it is finalized and deletes its copy once this answers
    ok, which is why the answer has to be trustworthy in both directions. A
    false ok costs the only copy of that audio.

    So the write is the same shape as every durable write in this estate --
    into a sibling `.part`, fsynced, renamed -- and the hash is verified
    BEFORE the rename rather than trusted. The adb transport this replaces
    had to carry explicit truncated-transfer repair logic; a checksum the
    sender computed over the file it still holds turns that whole class of
    failure into one honest 422.

    Re-uploading a chunk already here is a success, not a conflict. The phone
    legitimately retries when an ok is lost on the way back, and a retry that
    answered 409 would strand the file on the device forever.
    """
    directory = UPLOAD_LANES.get(lane)
    if directory is None:
        return HTTPStatus.NOT_FOUND, {"ok": False, "detail": f"no upload lane {lane!r}"}
    if not UPLOAD_NAME_RE.match(name):
        return HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "unacceptable file name"}
    if not body:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "empty body"}

    digest = hashlib.sha256(body).hexdigest()
    if declared_sha and declared_sha.lower() != digest:
        return HTTPStatus.UNPROCESSABLE_ENTITY, {
            "ok": False,
            "detail": "sha256 mismatch; transfer was corrupted or truncated",
            "expected": declared_sha.lower(),
            "received": digest,
            "bytes": len(body),
        }

    target = directory / name
    if target.exists() and target.stat().st_size == len(body):
        return HTTPStatus.OK, {
            "ok": True,
            "duplicate": True,
            "bytes": len(body),
            "sha256": digest,
            "path": str(target),
        }

    part = directory / f"{name}.part"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with part.open("wb") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        # Match the lane's existing files rather than whatever umask this
        # service happens to run under: these sit beside chunks the drain's
        # rsync landed at 0660, and a lane where half the files are readable
        # by the group and half are not is a bug waiting for its first
        # group-reading consumer.
        part.chmod(0o660)
        part.replace(target)
    except OSError as exc:
        part.unlink(missing_ok=True)
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "detail": str(exc)}

    return HTTPStatus.OK, {
        "ok": True,
        "duplicate": False,
        "bytes": len(body),
        "sha256": digest,
        "path": str(target),
        "at": now_iso(),
    }


def _day_file(day: str) -> Path:
    return EVENTS_DIR / f"events-{day}.jsonl"


def events_cursor(day: str) -> tuple[HTTPStatus, dict]:
    """How much of that day prime already holds.

    The cursor is the file's own size, not a number kept beside it. A separate
    counter can disagree with the file after a crash, a restore, or an
    operator moving one aside, and every one of those disagreements ends with
    the phone either re-shipping a day or skipping one. The file cannot
    disagree with itself.
    """
    if not EVENTS_DAY_RE.match(day):
        return HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "day must be YYYYMMDD"}
    target = _day_file(day)
    return HTTPStatus.OK, {
        "ok": True,
        "day": day,
        "bytes": target.stat().st_size if target.is_file() else 0,
    }


def append_events(day: str, offset: int, body: bytes, declared_sha: str | None) -> tuple[HTTPStatus, dict]:
    """Land a slice of the app's event log at the offset it came from.

    The write is a positional `pwrite`, and that single choice is what makes
    the lane idempotent. A batch says which byte of the day it starts at, so
    re-delivering it writes the same bytes to the same place -- a retry after
    a lost ok, a re-send after the phone rewound, and a duplicate from a
    confused client are all the same harmless operation. An append at the end
    of the file, by contrast, would turn every lost acknowledgement into a
    duplicated stretch of the log.

    Two disagreements are possible and neither is silently absorbed:

    * the batch lies entirely behind prime's cursor -- a pure retry, answered
      ok with `duplicate`, and the phone advances;
    * the batch starts BEYOND prime's cursor -- prime is missing the bytes in
      between, which happens when the lake was restored from an older copy or
      a day file was moved aside. Writing it anyway would leave a hole padded
      with zeroes inside a JSONL file. It is answered 409 with prime's real
      cursor, and the phone rewinds to it; the phone still holds the whole day
      file until prime has all of it, so a rewind always has something to
      re-send.
    """
    if not EVENTS_DAY_RE.match(day):
        return HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "day must be YYYYMMDD"}
    if offset < 0:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "negative offset"}
    if not body:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "empty body"}
    if len(body) > MAX_EVENT_BATCH:
        return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "bytes": len(body)}

    digest = hashlib.sha256(body).hexdigest()
    if declared_sha and declared_sha.lower() != digest:
        return HTTPStatus.UNPROCESSABLE_ENTITY, {
            "ok": False,
            "detail": "sha256 mismatch; transfer was corrupted or truncated",
            "expected": declared_sha.lower(),
            "received": digest,
            "bytes": len(body),
        }

    target = _day_file(day)
    try:
        EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        size = target.stat().st_size if target.is_file() else 0
        if offset > size:
            return HTTPStatus.CONFLICT, {
                "ok": False,
                "detail": "prime is missing the bytes before this batch",
                "expected_offset": size,
                "day": day,
            }
        if offset + len(body) <= size:
            return HTTPStatus.OK, {
                "ok": True,
                "duplicate": True,
                "day": day,
                "bytes": len(body),
                "cursor": size,
            }
        fd = os.open(target, os.O_WRONLY | os.O_CREAT, 0o660)
        try:
            os.pwrite(fd, body, offset)
            os.fsync(fd)
        finally:
            os.close(fd)
        # O_CREAT does not apply the mode to a file that already exists, and
        # the day files the drain landed are 0660: a lane where half the files
        # are group-readable and half are not is a bug waiting for its first
        # group-reading consumer.
        os.chmod(target, 0o660)
    except OSError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "detail": str(exc)}

    return HTTPStatus.OK, {
        "ok": True,
        "duplicate": False,
        "day": day,
        "bytes": len(body),
        "cursor": offset + len(body),
        "sha256": digest,
        "at": now_iso(),
    }
