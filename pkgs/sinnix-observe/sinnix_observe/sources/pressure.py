"""PSI pressure + blocked-task collectors."""

from __future__ import annotations

from typing import Any

from ..util import float_or_none, int_or_none, read_text, run_cmd


def parse_psi(path: str) -> dict[str, Any]:
    result: dict[str, Any] = {"raw": read_text(path) or ""}
    for line in result["raw"].splitlines():
        parts = line.split()
        if not parts:
            continue
        row: dict[str, float] = {}
        for item in parts[1:]:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            try:
                row[key] = float(value)
            except ValueError:
                pass
        result[parts[0]] = row
    return result


def collect_pressure(offline: bool) -> dict[str, Any]:
    if offline:
        return {"offline": True}
    pressure = {
        "cpu": parse_psi("/proc/pressure/cpu"),
        "memory": parse_psi("/proc/pressure/memory"),
        "io": parse_psi("/proc/pressure/io"),
    }
    free = run_cmd(["free", "-h"])
    pressure["free_h"] = free.stdout if free else ""
    return pressure


def collect_blocked_tasks(offline: bool) -> list[dict[str, Any]]:
    if offline:
        return []
    proc = run_cmd(
        [
            "ps",
            "-eo",
            "stat,pid,ppid,etimes,pcpu,pmem,rss,wchan:32,comm,args",
        ]
    )
    rows: list[dict[str, Any]] = []
    if not proc:
        return rows
    for line in proc.stdout.splitlines()[1:]:
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
