"""The phone's own uploads: whole capture files (ambient audio, camera,
Downloads, outbox blobs) and byte ranges of the app's event log.

Two shapes because the data has two shapes. A closed chunk is immutable and
arrives once; a day file is appended to for twenty-four hours and has to
arrive continuously, which a route keyed by file name cannot express. What
they share is the part that matters -- the sender declares a sha256 over the
bytes it still holds, prime verifies before the write is visible, and a
repeat of something already landed answers ok rather than a conflict, because
the phone deletes its copy on an ok and retries on anything else.

An ok therefore describes bytes read back from where they were retained, never
the request that carried them. Upload deliveries serialize their
check-write-verify operation. Event writes and the separate closed-day repair
CLI share a filesystem lock, so a late delivery cannot be acknowledged into
an inode that repair is replacing.
"""

from __future__ import annotations

import hashlib
import os
import sys
from http import HTTPStatus
from pathlib import Path
from threading import Lock

from sinnix_lib.atomic import atomic_publish
from sinnix_lib.ledger import utc_ts
from sinnix_lib.lock import flock

from .notifications import mirror_new_events
from .state import (
    EVENTS_DAY_RE,
    EVENTS_DIR,
    MAX_EVENT_BATCH,
    UPLOAD_LANES,
    UPLOAD_NAME_RE,
)

AMBIENT_PROGRESS_MARKER = Path(
    os.environ.get(
        "SINNIX_PHONE_AMBIENT_PROGRESS_MARKER",
        "/realm/state/sinnix-phone/ambient-progress",
    )
)
_AMBIENT_PROGRESS_LOCK = Lock()
_UPLOAD_LOCK = Lock()


def _retained_digest(target: Path) -> tuple[int, str] | None:
    """Size and sha256 of what the destination holds, or None if nothing."""
    size = 0
    digest = hashlib.sha256()
    try:
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                size += len(chunk)
                digest.update(chunk)
    except FileNotFoundError:
        return None
    return size, digest.hexdigest()


def _retain(target: Path, body: bytes, digest: str) -> tuple[HTTPStatus, dict] | None:
    """Publish *body* at an empty *target* and read it back.

    None on success; otherwise the refusal to send. A read-back that differs
    from what was sent is a storage fault, answered 500 so the phone keeps its
    copy.
    """
    atomic_publish(target, body, fsync=True, mode=0o660)
    if _retained_digest(target) != (len(body), digest):
        return HTTPStatus.INTERNAL_SERVER_ERROR, {
            "ok": False,
            "detail": "retained upload failed read-back verification",
            "path": str(target),
        }
    return None


def _record_ambient_progress(target: Path) -> None:
    """Refresh the marker after a newly landed chunk, never on a retry."""
    with _AMBIENT_PROGRESS_LOCK:
        AMBIENT_PROGRESS_MARKER.touch()


#: How deep a lane path may go. `DCIM/Camera/IMG_0001.jpg` arrives as
#: `Camera/IMG_0001.jpg`; nothing on this phone nests further, and a cap means
#: a confused client cannot walk a directory tree into the lake.
MAX_NAME_DEPTH = 4


def safe_relative(lane_dir: Path, name: str) -> Path | None:
    """Resolve a client-chosen name under its lane, or None if it is not one.

    Every segment must match the same anchored pattern a flat chunk name does,
    which is what makes traversal impossible rather than filtered: `..` and `.`
    fail it on their first character, an empty segment fails it outright, and
    a segment with a separator cannot exist after the split.

    The containment check afterwards resolves both sides first, and that is
    not decoration: `Path.relative_to` is textual, so an unresolved
    `<lane>/Camera/../../escape.jpg` passes it while pointing two levels above
    the lane. Measured, by mutating the segment check away and watching that
    path land -- which is the whole reason the second check exists.
    """
    if not name or name.endswith("/"):
        return None
    parts = name.split("/")
    if len(parts) > MAX_NAME_DEPTH or not all(UPLOAD_NAME_RE.fullmatch(p) for p in parts):
        return None
    target = lane_dir.joinpath(*parts)
    try:
        target.resolve().relative_to(lane_dir.resolve())
    except (ValueError, OSError):
        return None
    return target


def store_upload(
    lane: str, name: str, body: bytes, declared_sha: str | None
) -> tuple[HTTPStatus, dict]:
    """Land a capture file the phone pushed, or say precisely why not.

    This is the phone's own half of the ambient archive: the app uploads a
    chunk as soon as it is finalized and deletes its copy once this answers
    ok, which is why the answer has to be trustworthy in both directions. A
    false ok costs the only copy of that audio.

    So the write is the same shape as every durable write on this host --
    into a sibling `.part`, fsynced, renamed -- and the hash is verified
    BEFORE the rename rather than trusted. The adb transport this replaces
    had to carry explicit truncated-transfer repair logic; a checksum the
    sender computed over the file it still holds turns that whole class of
    failure into one honest 422.

    Re-uploading a chunk already here is a success, not a conflict. The phone
    legitimately retries when an ok is lost on the way back, and a retry that
    answered 409 would strand the file on the device forever. "Already here"
    means the same bytes, compared by digest, not a file of the same length.
    """
    directory = UPLOAD_LANES.get(lane)
    if directory is None:
        return HTTPStatus.NOT_FOUND, {"ok": False, "detail": f"no upload lane {lane!r}"}
    target = safe_relative(directory, name)
    if target is None:
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

    try:
        # The lane's own subdirectory, when the name carried one: the camera
        # mirror keeps `Camera/`, `Screenshots/` and `Pictures/` because the
        # rsync that filled it did.
        target.parent.mkdir(parents=True, exist_ok=True)
        with _UPLOAD_LOCK:
            status, payload = _store_locked(lane, target, body, digest)
    except OSError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "detail": str(exc)}
    return status, payload


def _store_locked(
    lane: str, target: Path, body: bytes, digest: str
) -> tuple[HTTPStatus, dict]:
    """The check-write-verify of one upload, under the upload lock.

    A name already holding these exact bytes is a retry and answers ok. A name
    holding OTHER bytes -- a camera file edited in place, a sender that reused
    a name -- keeps what it holds, and the new payload is retained beside it
    under a name derived from its own digest. Refusing it instead would leave
    the phone re-offering the same file at the head of its queue forever;
    overwriting would destroy a copy the phone was already told was safe to
    delete. The answer names the conflict and the path the bytes went to.
    """
    retained = _retained_digest(target)
    conflict_with: str | None = None
    if retained is not None:
        if retained == (len(body), digest):
            return HTTPStatus.OK, {
                "ok": True,
                "duplicate": True,
                "bytes": retained[0],
                "sha256": retained[1],
                "path": str(target),
            }
        conflict_with = retained[1]
        target = target.with_name(f"{target.name}.conflict-{digest}")
        retained = _retained_digest(target)
        if retained is not None:
            if retained == (len(body), digest):
                return HTTPStatus.OK, {
                    "ok": True,
                    "duplicate": True,
                    "conflict": True,
                    "conflicts_with": conflict_with,
                    "bytes": retained[0],
                    "sha256": retained[1],
                    "path": str(target),
                }
            return HTTPStatus.INTERNAL_SERVER_ERROR, {
                "ok": False,
                "detail": "the digest-named conflict copy holds other bytes",
                "path": str(target),
            }

    refusal = _retain(target, body, digest)
    if refusal is not None:
        return refusal

    if lane == "ambient":
        try:
            # The file is already durably visible. If this one-path marker
            # cannot be updated, refuse the ack so the phone retains its copy;
            # the retry is idempotent and the next new chunk can recover too.
            _record_ambient_progress(target)
        except OSError as exc:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {
                "ok": False,
                "detail": f"ambient progress marker could not be written: {exc}",
            }

    payload = {
        "ok": True,
        "duplicate": False,
        "bytes": len(body),
        "sha256": digest,
        "path": str(target),
        "at": utc_ts(),
    }
    if conflict_with is not None:
        payload["conflict"] = True
        payload["conflicts_with"] = conflict_with
    return HTTPStatus.OK, payload


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


def append_events(
    day: str, offset: int, body: bytes, declared_sha: str | None
) -> tuple[HTTPStatus, dict]:
    """Land a slice of the app's event log at the offset it came from.

    The write is a positional `pwrite`, and that single choice is what makes
    the lane idempotent. A batch says which byte of the day it starts at, so
    re-delivering it writes the same bytes to the same place -- a retry after
    a lost ok, a re-send after the phone rewound, and a duplicate from a
    confused client are all the same harmless operation. An append at the end
    of the file, by contrast, would turn every lost acknowledgement into a
    duplicated stretch of the log.

    Three disagreements are possible and none is silently absorbed:

    * the batch lies entirely behind prime's cursor -- a pure retry, answered
      ok with `duplicate`, and the phone advances;
    * the batch starts BEYOND prime's cursor -- prime is missing the bytes in
      between, which happens when the lake was restored from an older copy or
      a day file was moved aside. Writing it anyway would leave a hole padded
      with zeroes inside a JSONL file. It is answered 409 with prime's real
      cursor, and the phone rewinds to it; the phone still holds the whole day
      file until prime has all of it, so a rewind always has something to
      re-send.
    * the batch overlaps bytes prime holds and they differ -- the phone's day
      file is append-only, so this is a fault on one side. It is answered 409
      WITHOUT a cursor: a cursor would tell the phone to skip ahead past the
      disagreement, which would acknowledge bytes prime does not hold.

    The write loops until every byte is down (a short `pwrite` is legal), and
    the whole batch's range is read back before it is acknowledged.
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
        with flock(EVENTS_DIR / ".write.lock"):
            size = target.stat().st_size if target.is_file() else 0
            if offset > size:
                return HTTPStatus.CONFLICT, {
                    "ok": False,
                    "detail": "prime is missing the bytes before this batch",
                    "expected_offset": size,
                    "day": day,
                }
            overlap = min(len(body), size - offset)
            if overlap and _read_range(target, offset, overlap) != body[:overlap]:
                return HTTPStatus.CONFLICT, {
                    "ok": False,
                    "conflict": "range_differs",
                    "detail": "prime holds different bytes in this batch's range",
                    "day": day,
                    "offset": offset,
                }
            if overlap == len(body):
                return HTTPStatus.OK, {
                    "ok": True,
                    "duplicate": True,
                    "day": day,
                    "bytes": len(body),
                    "cursor": size,
                    "sha256": digest,
                }
            fd = os.open(target, os.O_WRONLY | os.O_CREAT, 0o660)
            try:
                written = overlap
                while written < len(body):
                    count = os.pwrite(fd, body[written:], offset + written)
                    if count <= 0:
                        raise OSError(f"pwrite made no progress at byte {written}")
                    written += count
                os.fsync(fd)
            finally:
                os.close(fd)
            if _read_range(target, offset, len(body)) != body:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {
                    "ok": False,
                    "detail": "retained range failed read-back verification",
                    "day": day,
                }
        # O_CREAT does not apply the mode to a file that already exists, and
        # the day files the drain landed are 0660: a lane where half the files
        # are group-readable and half are not is a bug waiting for its first
        # group-reading consumer.
        os.chmod(target, 0o660)
    except OSError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "detail": str(exc)}

    # Only the bytes this write actually added, not the whole batch -- an
    # overlapping batch (the branch above already resolved it) repeats bytes
    # already scanned, and rescanning them would pop a duplicate desktop
    # notification for every retry. Advisory: a mirroring failure must never
    # turn a landed upload into one the phone believes it has to resend.
    try:
        mirror_new_events(day, body[overlap:])
    except Exception as exc:  # noqa: BLE001 - the upload above already landed
        print(
            f"phone-dispatcher: notifications: mirror_new_events failed: {exc}",
            file=sys.stderr,
        )

    return HTTPStatus.OK, {
        "ok": True,
        "duplicate": False,
        "day": day,
        "bytes": len(body),
        "cursor": offset + len(body),
        "sha256": digest,
        "at": utc_ts(),
    }


def _read_range(target: Path, offset: int, length: int) -> bytes:
    with target.open("rb") as stream:
        stream.seek(offset)
        return stream.read(length)


def repair_event_day(day: str, source: Path, expected_sha256: str) -> dict:
    """Replace a closed UTC day from verified device bytes, retaining the old inode."""
    import json
    import tempfile
    from datetime import datetime, timezone

    if not EVENTS_DAY_RE.fullmatch(day) or day >= datetime.now(timezone.utc).strftime(
        "%Y%m%d"
    ):
        raise ValueError("repair requires a closed UTC day")
    body = source.read_bytes()
    if not body or not body.endswith(b"\n"):
        raise ValueError("source must contain complete JSONL records")
    for line in body.splitlines():
        if not isinstance(json.loads(line), dict):
            raise ValueError("source contains a non-object record")
    target = _day_file(day)
    with flock(EVENTS_DIR / ".write.lock"):
        previous = target.read_bytes()
        old_sha = hashlib.sha256(previous).hexdigest()
        if old_sha != expected_sha256:
            raise ValueError("destination changed; expected SHA-256 does not match")
        new_sha = hashlib.sha256(body).hexdigest()
        if body == previous:
            return {"ok": True, "changed": False, "sha256": new_sha}
        backups = EVENTS_DIR / ".repairs"
        backups.mkdir(exist_ok=True)
        backup = backups / f"{day}-{old_sha}.jsonl"
        if not backup.exists():
            os.link(target, backup)
        if hashlib.sha256(backup.read_bytes()).hexdigest() != old_sha:
            raise ValueError("backup verification failed")
        pending: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=EVENTS_DIR, prefix=".repair-", delete=False
            ) as out:
                pending = Path(out.name)
                out.write(body)
                out.flush()
                os.fsync(out.fileno())
            if target.read_bytes() != previous:
                raise ValueError("destination changed during repair")
            os.chmod(pending, 0o660)
            os.replace(pending, target)
            pending = None
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)
        return {
            "ok": True,
            "changed": True,
            "day": day,
            "sha256": new_sha,
            "previous_sha256": old_sha,
            "backup": str(backup),
            "bytes": len(body),
        }
