"""One publish for state files.

Write to a private temporary in the destination's own directory, then rename
over the destination: a reader sees either the whole old file or the whole new
one, never a partial write, and a failed write leaves the old content
untouched. The temporary is removed on every path.

``fsync`` has no default. Each caller states whether its content must survive
a crash, because the answer differs per file. There is no file-only sync
level: fsyncing a file whose new directory entry is not synced does not
guarantee the published name is findable afterwards, so it buys latency
without buying the guarantee.

Serialization belongs to the caller. ``atomic_json.write_json_atomic`` and
``ledger.write_jsonl_atomic`` are the JSON and JSONL encoders over this.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

PRIVATE_MODE = 0o600


def _validate_name(name: str) -> None:
    """Reject names that could turn an ``*at`` operation into traversal."""
    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise ValueError("target name must be a non-special basename")
    encoded = os.fsencode(name)
    if b"/" in encoded or b"\x00" in encoded:
        raise ValueError("target name must be a non-special basename")


def atomic_publish_at(
    directory: int,
    target_name: str,
    payload: bytes,
    *,
    fsync: bool,
    mode: int = PRIVATE_MODE,
    exclusive: bool = False,
) -> bool:
    """Publish *payload* below an already pinned directory descriptor.

    ``target_name`` is a single directory entry name.  All temporary-file,
    link, rename, and cleanup operations use *directory*, so a caller can
    pin an untrusted checkout before changing it and cannot be redirected by
    a concurrent replacement of a path component.  The descriptor remains
    owned by the caller.
    """
    _validate_name(target_name)
    temporary_name: str | None = None
    descriptor = -1
    try:
        for _ in range(8):
            candidate = f".{target_name}.atomic-tmp-{uuid.uuid4().hex}"
            try:
                descriptor = os.open(
                    candidate,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | os.O_NOFOLLOW
                    | getattr(os, "O_CLOEXEC", 0),
                    mode,
                    dir_fd=directory,
                )
            except FileExistsError:
                continue
            temporary_name = candidate
            break
        if temporary_name is None:
            raise OSError("could not allocate a private atomic temporary")

        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            os.fchmod(handle.fileno(), mode & 0o777)
            handle.write(payload)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())

        if exclusive:
            try:
                os.link(
                    temporary_name,
                    target_name,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                )
            except FileExistsError:
                return False
        else:
            os.replace(
                temporary_name,
                target_name,
                src_dir_fd=directory,
                dst_dir_fd=directory,
            )
        if fsync:
            os.fsync(directory)
        temporary_name = None if not exclusive else temporary_name
        return True
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=directory)
            except FileNotFoundError:
                pass


def atomic_publish(
    destination: Path | str,
    payload: bytes,
    *,
    fsync: bool,
    mode: int = PRIVATE_MODE,
    exclusive: bool = False,
) -> bool:
    """Publish *payload* at *destination* as one indivisible step.

    ``exclusive`` publishes by hard link instead of rename, so an existing
    destination is never replaced -- for content nobody may silently
    overwrite, such as a key other state is already derived from. Returns
    whether this call published; False means ``exclusive`` and the
    destination already existed.

    The temporary carries the final mode from creation rather than being
    chmod'd afterwards: a private state file must never be briefly readable
    by anyone else, however narrow the window.
    """
    destination = Path(destination)
    directory = destination.parent
    temporary = directory / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, mode
        )
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(payload)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        if exclusive:
            try:
                os.link(temporary, destination)
            except FileExistsError:
                return False
        else:
            os.replace(temporary, destination)
        if fsync:
            directory_descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)
    return True
