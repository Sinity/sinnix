"""PSI pressure + blocked-task collectors."""

from __future__ import annotations

from typing import Any

from sinnix_lib.process import run
from sinnix_lib.procfs import parse_colon_numeric
from sinnix_lib.procfs import parse_psi as parse_psi_text
from sinnix_lib.values import float_or_none, int_or_none, read_text


def parse_psi(path: str) -> dict[str, Any]:
    raw = read_text(path) or ""
    # Keep the raw kernel text and empty record rows as part of Observe's
    # public evidence shape; the shared parser owns field validation.
    result: dict[str, Any] = {"raw": raw}
    result.update(
        {
            record: {key: float(value) for key, value in fields.items()}
            for record, fields in parse_psi_text(raw).items()
        }
    )
    for line in raw.splitlines():
        parts = line.split()
        if parts:
            result.setdefault(parts[0], {})
    return result


def collect_pressure(offline: bool) -> dict[str, Any]:
    if offline:
        return {"offline": True}
    pressure = {
        "cpu": parse_psi("/proc/pressure/cpu"),
        "memory": parse_psi("/proc/pressure/memory"),
        "io": parse_psi("/proc/pressure/io"),
    }
    pressure["free_h"] = run(["free", "-h"], timeout=1).stdout
    meminfo = parse_colon_numeric(read_text("/proc/meminfo"))
    pressure["meminfo_mb"] = {
        key: value // 1024
        for key, value in meminfo.items()
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"} and value >= 0
    }
    return pressure


def collect_blocked_tasks(offline: bool) -> list[dict[str, Any]]:
    if offline:
        return []
    result = run(
        [
            "ps",
            "-eo",
            "stat,pid,ppid,etimes,pcpu,pmem,rss,wchan:32,comm,args",
        ],
        timeout=5,
    )
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split(None, 9)
        if len(parts) < 10 or not parts[0].startswith("D"):
            continue
        rows.append(
            {
                "stat": parts[0],
                "pid": int_or_none(parts[1]),
                "ppid": int_or_none(parts[2]),
                "elapsed_secs": int_or_none(parts[3]),
                "cpu_pct": float_or_none(parts[4]),
                "mem_pct": float_or_none(parts[5]),
                "rss_kb": int_or_none(parts[6]),
                "wchan": parts[7],
                "comm": parts[8],
                "cmdline": parts[9],
            }
        )
    return rows
