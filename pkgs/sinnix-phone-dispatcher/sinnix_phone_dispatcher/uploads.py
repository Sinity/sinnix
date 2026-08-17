"""The phone's own bulk capture uploads (ambient audio, camera), landed as
whole files rather than streamed like the telemetry receiver's lines."""

from __future__ import annotations

import hashlib
import os
from http import HTTPStatus

from .state import UPLOAD_LANES, UPLOAD_NAME_RE, now_iso


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
