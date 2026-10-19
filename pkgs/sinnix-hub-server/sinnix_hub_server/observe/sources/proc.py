"""Parsers for /proc/<pid>/{io,status,cgroup}."""

from __future__ import annotations

from pathlib import Path

from sinnix_lib.procfs import parse_cgroup_v2, parse_colon_numeric
from sinnix_lib.values import read_text


def parse_proc_io(path: Path) -> dict[str, int]:
    return parse_colon_numeric(read_text(path))


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
    return parse_cgroup_v2(read_text(path))
