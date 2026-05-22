"""`below dump` cgroup + process peak history reader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..util import float_or_zero, run_cmd


def parse_below_tsv(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        rows.append(line.split("\t"))
    return rows


def collect_below(
    begin: str, duration: str, limit: int, offline: bool
) -> dict[str, Any]:
    fixture_cgroup = os.environ.get("SINNIX_OBSERVE_BELOW_CGROUP_TSV")
    fixture_process = os.environ.get("SINNIX_OBSERVE_BELOW_PROCESS_TSV")
    result: dict[str, Any] = {
        "available": False,
        "begin": begin,
        "duration": duration,
        "cgroup_peaks": [],
        "process_peaks": [],
    }
    if offline and not (fixture_cgroup or fixture_process):
        result["gaps"] = ["below.history.unavailable_offline"]
        return result

    if fixture_cgroup:
        try:
            cgroup_text = Path(fixture_cgroup).read_text(encoding="utf-8")
        except OSError:
            cgroup_text = ""
    else:
        proc = run_cmd(
            [
                "below",
                "dump",
                "cgroup",
                "-b",
                begin,
                "--duration",
                duration,
                "-f",
                "datetime name full_path cpu.usage_pct mem.total io.rwbytes_per_sec pressure.io_full_pct pressure.memory_full_pct",
                "-O",
                "tsv",
                "--raw",
                "--disable-title",
            ],
            timeout=10,
        )
        cgroup_text = proc.stdout if proc and proc.returncode == 0 else ""

    cgroup_by_path: dict[str, dict[str, Any]] = {}
    for row in parse_below_tsv(cgroup_text):
        if len(row) < 8:
            continue
        path = row[2]
        current = cgroup_by_path.setdefault(
            path,
            {
                "cgroup": path,
                "max_rw_bps": 0.0,
                "max_io_full_pct": 0.0,
                "max_memory_full_pct": 0.0,
                "max_rss_bytes": 0.0,
                "max_cpu_pct": 0.0,
                "samples": 0,
            },
        )
        current["samples"] += 1
        current["max_cpu_pct"] = max(current["max_cpu_pct"], float_or_zero(row[3]))
        current["max_rss_bytes"] = max(current["max_rss_bytes"], float_or_zero(row[4]))
        current["max_rw_bps"] = max(current["max_rw_bps"], float_or_zero(row[5]))
        current["max_io_full_pct"] = max(
            current["max_io_full_pct"], float_or_zero(row[6])
        )
        current["max_memory_full_pct"] = max(
            current["max_memory_full_pct"], float_or_zero(row[7])
        )

    if fixture_process:
        try:
            process_text = Path(fixture_process).read_text(encoding="utf-8")
        except OSError:
            process_text = ""
    else:
        proc = run_cmd(
            [
                "below",
                "dump",
                "process",
                "-b",
                begin,
                "--duration",
                duration,
                "-f",
                "datetime pid comm state cgroup io.rwbytes_per_sec mem.rss_bytes cpu.usage_pct cmdline",
                "-O",
                "tsv",
                "--raw",
                "--disable-title",
            ],
            timeout=10,
        )
        process_text = proc.stdout if proc and proc.returncode == 0 else ""

    process_by_pid: dict[str, dict[str, Any]] = {}
    for row in parse_below_tsv(process_text):
        if len(row) < 9 or not row[1].isdigit():
            continue
        pid = row[1]
        current = process_by_pid.setdefault(
            pid,
            {
                "pid": int(pid),
                "comm": row[2],
                "state": row[3],
                "cgroup": row[4],
                "cmdline": row[8][:240],
                "max_rw_bps": 0.0,
                "max_rss_bytes": 0.0,
                "max_cpu_pct": 0.0,
                "samples": 0,
            },
        )
        current["samples"] += 1
        current["max_rw_bps"] = max(current["max_rw_bps"], float_or_zero(row[5]))
        current["max_rss_bytes"] = max(current["max_rss_bytes"], float_or_zero(row[6]))
        current["max_cpu_pct"] = max(current["max_cpu_pct"], float_or_zero(row[7]))

    result["cgroup_peaks"] = sorted(
        cgroup_by_path.values(), key=lambda item: item["max_rw_bps"], reverse=True
    )[:limit]
    result["process_peaks"] = sorted(
        process_by_pid.values(), key=lambda item: item["max_rw_bps"], reverse=True
    )[:limit]
    result["available"] = bool(result["cgroup_peaks"] or result["process_peaks"])
    if not result["available"]:
        result["gaps"] = ["below.history.no_samples"]
    return result
