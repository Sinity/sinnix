"""Lenient scalar reads for /sys, /proc and command output.

A missing file, an empty field and an unparseable value are all "no value".
Collectors scrape surfaces that appear and disappear with hardware, kernel
version and privilege, so an absence must stay distinguishable from a
measurement without becoming an exception on the way.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def read_text(path: str | Path) -> str | None:
    """Stripped contents of a small file, or None when it cannot be read."""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
