"""Read file inputs without blocking on special filesystem objects."""

from __future__ import annotations

import errno
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO


class NotRegularFile(OSError, ValueError):
    """The opened path is a FIFO, device, socket or directory."""

    def __init__(self, path: Path | str):
        super().__init__(errno.EINVAL, "not a regular file", str(path))


@contextmanager
def open_regular(
    path: Path | str, mode: str = "rb", *, encoding: str | None = None, errors: str | None = None,
) -> Iterator[IO]:
    """Open without blocking on a FIFO and refuse anything but a regular file.

    The type is checked on the opened descriptor, so a path replaced between
    lookup and open cannot pass the check with different bytes.
    """
    if "b" not in mode and encoding is None:
        encoding = "utf-8"
    with open(
        path, mode, encoding=encoding, errors=errors,
        opener=lambda name, flags: os.open(name, flags | os.O_NONBLOCK),
    ) as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise NotRegularFile(path)
        yield handle


def read_regular_text(path: Path, *, encoding: str = "utf-8") -> str:
    """Follow ordinary file links, checking the opened descriptor before reading."""
    with open_regular(path, "r", encoding=encoding) as text:
        return text.read()


def read_regular_bytes(path: Path, *, max_bytes: int | None = None) -> bytes:
    """Read at most the requested byte budget plus one byte to detect overflow."""
    if max_bytes is not None and max_bytes < 0:
        raise ValueError("file read bound must be nonnegative")
    with open_regular(path) as handle:
        raw = handle.read() if max_bytes is None else handle.read(max_bytes + 1)
    if max_bytes is not None and len(raw) > max_bytes:
        raise ValueError(f"file exceeds {max_bytes} byte bound: {path}")
    return raw
