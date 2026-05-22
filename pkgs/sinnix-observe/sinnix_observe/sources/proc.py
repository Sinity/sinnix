"""Parsers for /proc/<pid>/{io,status,cgroup}."""

from __future__ import annotations

from pathlib import Path

from ..util import int_or_none, read_text


def parse_proc_io(path: Path) -> dict[str, int]:
    raw = read_text(path)
    result: dict[str, int] = {}
    if not raw:
        return result
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed = int_or_none(value.strip())
        if parsed is not None:
            result[key.strip()] = parsed
    return result


def parse_proc_status(path: Path) -> dict[str, str]:
    raw = read_text(path)
    result: dict[str, str] = {}
    if not raw:
        return result
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def parse_proc_cgroup(path: Path) -> str | None:
    raw = read_text(path)
    if not raw:
        return None
    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[0] == "0":
            return parts[2]
    return raw.splitlines()[0] if raw.splitlines() else None
