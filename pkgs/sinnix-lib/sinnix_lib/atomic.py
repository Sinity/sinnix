"""One publish for state files.

Write the new content to an unnamed file (``O_TMPFILE``) in the destination's
own directory, give it a name only once its bytes are complete, then rename
over the destination: a reader sees either the whole old file or the whole new
one, never a partial write, and a failed write leaves the old content
untouched. A process killed while writing or syncing leaves nothing behind,
because the content has no name until that work is done; on a filesystem
without ``O_TMPFILE`` a private named temporary is used instead and removed on
every path a Python process can still run.

``fsync`` has no default. Each caller states whether its content must survive
a crash, because the answer differs per file. There is no file-only sync
level: fsyncing a file whose new directory entry is not synced does not
guarantee the published name is findable afterwards, so it buys latency
without buying the guarantee.

Serialization belongs to the caller. ``atomic_json.write_json_atomic`` and
``ledger.write_jsonl_atomic`` are the JSON and JSONL encoders over this.
"""

from __future__ import annotations

import errno
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, TextIO

PRIVATE_MODE = 0o600

_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
# Errors meaning "this filesystem or kernel has no O_TMPFILE", as open(2)
# lists them; anything else is a real failure to report.
_NO_TMPFILE = {errno.EOPNOTSUPP, errno.EISDIR, errno.EINVAL, errno.ENOENT}


def _validate_name(name: str) -> None:
    """Reject names that could turn an ``*at`` operation into traversal."""
    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise ValueError("target name must be a non-special basename")
    encoded = os.fsencode(name)
    if b"/" in encoded or b"\x00" in encoded:
        raise ValueError("target name must be a non-special basename")


def _temporary_names(target_name: str) -> Iterator[str]:
    for _ in range(8):
        yield f".{target_name}.atomic-tmp-{uuid.uuid4().hex}"
    raise OSError("could not allocate a private atomic temporary")


def _allocate(directory: int, target_name: str, mode: int) -> tuple[int, str | None]:
    """A writable descriptor in *directory*, and its name if it has one."""
    flag = getattr(os, "O_TMPFILE", 0)
    if flag:
        try:
            return os.open(
                ".", os.O_WRONLY | flag | _CLOEXEC, mode, dir_fd=directory
            ), None
        except OSError as error:
            if error.errno not in _NO_TMPFILE:
                raise
    for candidate in _temporary_names(target_name):
        try:
            descriptor = os.open(
                candidate,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | _CLOEXEC,
                mode,
                dir_fd=directory,
            )
        except FileExistsError:
            continue
        return descriptor, candidate
    raise AssertionError("unreachable")


def _link(descriptor: int, directory: int, name: str) -> None:
    """Give an unnamed file a name; raises FileExistsError if *name* exists."""
    os.link(
        f"/proc/self/fd/{descriptor}",
        name,
        dst_dir_fd=directory,
        follow_symlinks=True,
    )


def _name_unnamed(descriptor: int, directory: int, target_name: str) -> str:
    for candidate in _temporary_names(target_name):
        try:
            _link(descriptor, directory, candidate)
        except FileExistsError:
            continue
        return candidate
    raise AssertionError("unreachable")


def atomic_publish_at(
    directory: int,
    target_name: str,
    payload: bytes | BinaryIO,
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
    owned by the caller. Binary input streams are copied in bounded chunks;
    a failed read leaves the prior destination unchanged.
    """
    _validate_name(target_name)
    temporary_name: str | None = None
    descriptor = -1
    try:
        descriptor, temporary_name = _allocate(directory, target_name, mode)
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            os.fchmod(handle.fileno(), mode & 0o777)
            if isinstance(payload, bytes):
                handle.write(payload)
            else:
                for chunk in iter(lambda: payload.read(65_536), b""):
                    handle.write(chunk)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())

        if exclusive:
            try:
                if temporary_name is None:
                    _link(descriptor, directory, target_name)
                else:
                    os.link(
                        temporary_name,
                        target_name,
                        src_dir_fd=directory,
                        dst_dir_fd=directory,
                    )
            except FileExistsError:
                return False
        else:
            if temporary_name is None:
                temporary_name = _name_unnamed(descriptor, directory, target_name)
            os.replace(
                temporary_name,
                target_name,
                src_dir_fd=directory,
                dst_dir_fd=directory,
            )
            temporary_name = None
        if fsync:
            os.fsync(directory)
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
    directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | _CLOEXEC)
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
    _validate_name(destination.name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | _CLOEXEC)
    temporary = None
    descriptor = -1
    try:
        descriptor, temporary = _allocate(directory, destination.name, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as handle:
            os.fchmod(handle.fileno(), mode & 0o777)
            yield handle
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        if temporary is None:
            temporary = _name_unnamed(descriptor, directory, destination.name)
        os.replace(
            temporary,
            destination.name,
            src_dir_fd=directory,
            dst_dir_fd=directory,
        )
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
