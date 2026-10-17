"""Read file inputs without blocking on special filesystem objects."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def read_regular_text(path: Path, *, encoding: str = "utf-8") -> str:
    """Follow ordinary file links, checking the opened descriptor before reading."""
    with open(
        path,
        encoding=encoding,
        opener=lambda name, flags: os.open(name, flags | os.O_NONBLOCK),
    ) as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError(f"expected a regular file: {path}")
        return handle.read()
