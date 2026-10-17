"""Read file inputs without blocking on special filesystem objects."""

from __future__ import annotations

import io
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


@contextmanager
def _regular_input(path: Path) -> Iterator[BinaryIO]:
    with open(
        path, "rb", opener=lambda name, flags: os.open(name, flags | os.O_NONBLOCK),
    ) as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError(f"expected a regular file: {path}")
        yield handle


def read_regular_text(path: Path, *, encoding: str = "utf-8") -> str:
    """Follow ordinary file links, checking the opened descriptor before reading."""
    with _regular_input(path) as binary, io.TextIOWrapper(binary, encoding=encoding) as text:
        return text.read()


def read_regular_bytes(path: Path, *, max_bytes: int | None = None) -> bytes:
    """Read at most the requested byte budget plus one byte to detect overflow."""
    if max_bytes is not None and max_bytes < 0:
        raise ValueError("file read bound must be nonnegative")
    with _regular_input(path) as handle:
        raw = handle.read() if max_bytes is None else handle.read(max_bytes + 1)
    if max_bytes is not None and len(raw) > max_bytes:
        raise ValueError(f"file exceeds {max_bytes} byte bound: {path}")
    return raw
