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
from contextlib import contextmanager
from collections.abc import Iterator
from typing import TextIO
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
    """Publish *payload* at *destination* through the pinned-dirfd primitive.

    The public path API keeps its existing caller contract while sharing the
    same collision, cleanup, durability, and exclusive-publication behavior
    as callers which already hold a directory descriptor.
    """
    destination = Path(destination)
    directory = os.open(
        destination.parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        return atomic_publish_at(
            directory,
            destination.name,
            payload,
            fsync=fsync,
            mode=mode,
            exclusive=exclusive,
        )
    finally:
        os.close(directory)


@contextmanager
def atomic_text_writer(
    destination: Path | str, *, fsync: bool, mode: int = PRIVATE_MODE
) -> Iterator[TextIO]:
    """Stream text into a private sibling, publishing only on clean exit."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
    temporary = None
    descriptor = -1
    try:
        for _ in range(8):
            candidate = f".{destination.name}.atomic-tmp-{uuid.uuid4().hex}"
            try:
                descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=directory)
                temporary = candidate
                break
            except FileExistsError:
                continue
        if temporary is None:
            raise OSError("could not allocate a private atomic temporary")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            os.fchmod(handle.fileno(), mode & 0o777)
            yield handle
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        os.replace(temporary, destination.name, src_dir_fd=directory, dst_dir_fd=directory)
        temporary = None
        if fsync:
            os.fsync(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
        os.close(directory)
