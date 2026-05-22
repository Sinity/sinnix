"""Chrome I/O attribution: profile paths + /proc enumeration + below peaks."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any

from ..util import int_or_none, read_proc_cmdline, read_text, run_cmd
from .proc import parse_proc_cgroup, parse_proc_io, parse_proc_status

CHROME_PROFILE_GLOBS = [
    "/home/*/.config/chrome-ws",
    "/realm/home/.config/chrome-ws",
]

# Do not assume Chrome should move to /cache without evidence. This collector
# makes the current profile/cache placement and Chrome cgroup I/O counters
# visible first; exact per-file write tracing can be added later with eBPF if
# the lightweight /proc + below view shows Chrome is materially involved.
CHROME_CACHE_RELATIVE_PATHS = [
    "Default/Cache",
    "Default/Code Cache",
    "Default/GPUCache",
    "Default/Service Worker",
    "Default/IndexedDB",
    "Default/Local Storage",
    "Default/Session Storage",
    "Default/Storage",
    "Default/OptimizationGuidePredictionModels",
    "Default/OnDeviceHeadSuggestModel",
    "GrShaderCache",
    "ShaderCache",
    "Crashpad",
]


def chrome_profile_candidates() -> list[Path]:
    candidates: list[Path] = []
    override = os.environ.get("SINNIX_CHROME_PROFILE")
    if override:
        candidates.append(Path(override))
    candidates.append(Path.home() / ".config/chrome-ws")
    for pattern in CHROME_PROFILE_GLOBS:
        candidates.extend(Path(path) for path in glob.glob(pattern))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def is_chrome_process(comm: str, cmdline: str) -> bool:
    text = f"{comm} {cmdline}".lower()
    return any(
        token in text
        for token in (
            "google-chrome",
            "chrome-ws",
            "chrome_crashpad",
            "chromium",
            "chrome --type=",
            "/chrome ",
        )
    )


def du_bytes(path: Path) -> int | None:
    if os.environ.get("SINNIX_OBSERVE_CHROME_DU", "1") == "0":
        return None
    proc = run_cmd(["du", "-s", "-B1", str(path)], timeout=2)
    if not proc or proc.returncode != 0:
        return None
    first = proc.stdout.splitlines()[0] if proc.stdout.splitlines() else ""
    return int_or_none(first.split()[0] if first else None)


def find_mount_for_path(path: Path) -> dict[str, Any]:
    proc = run_cmd(
        ["findmnt", "-T", str(path), "-n", "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"],
        timeout=2,
    )
    if not proc or not proc.stdout.strip():
        return {"unresolved": True}
    parts = proc.stdout.strip().split(None, 3)
    return {
        "target": parts[0] if len(parts) > 0 else None,
        "source": parts[1] if len(parts) > 1 else None,
        "fstype": parts[2] if len(parts) > 2 else None,
        "options": parts[3] if len(parts) > 3 else None,
    }


def chrome_path_row(path: Path, include_size: bool = True) -> dict[str, Any]:
    exists = path.exists()
    row: dict[str, Any] = {
        "path": str(path),
        "exists": exists,
        "is_symlink": path.is_symlink(),
        "realpath": str(path.resolve(strict=False)),
    }
    if exists:
        row["mount"] = find_mount_for_path(path)
        if include_size:
            row["du_bytes"] = du_bytes(path)
    return row


def collect_chrome_io(
    offline: bool, below: dict[str, Any], limit: int
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "counter_scope": "live /proc/<pid>/io counters since each Chrome process started",
        "profiles": [],
        "processes": [],
        "by_cgroup": [],
        "below_process_peaks": [],
    }
    if offline:
        result["offline"] = True
        return result

    for profile in chrome_profile_candidates():
        if not profile.exists():
            continue
        profile_row = chrome_path_row(profile, include_size=False)
        cache_rows = []
        for rel in CHROME_CACHE_RELATIVE_PATHS:
            candidate = profile / rel
            if candidate.exists():
                cache_rows.append(chrome_path_row(candidate))
        profile_row["cache_paths"] = cache_rows
        result["profiles"].append(profile_row)

    for proc_dir in Path("/proc").glob("[0-9]*"):
        pid = int_or_none(proc_dir.name)
        if pid is None:
            continue
        comm = read_text(proc_dir / "comm") or ""
        cmdline = read_proc_cmdline(proc_dir / "cmdline")
        if not is_chrome_process(comm, cmdline):
            continue
        status = parse_proc_status(proc_dir / "status")
        io = parse_proc_io(proc_dir / "io")
        result["processes"].append(
            {
                "pid": pid,
                "ppid": int_or_none(status.get("PPid")),
                "comm": comm,
                "state": status.get("State"),
                "rss_kb": int_or_none((status.get("VmRSS") or "").split()[0]),
                "cgroup": parse_proc_cgroup(proc_dir / "cgroup"),
                "io": io,
                "cmdline": cmdline[:300],
            }
        )

    by_cgroup: dict[str, dict[str, Any]] = {}
    for proc in result["processes"]:
        cgroup = proc.get("cgroup") or "(unknown)"
        current = by_cgroup.setdefault(
            cgroup,
            {
                "cgroup": cgroup,
                "processes": 0,
                "rss_kb": 0,
                "rchar": 0,
                "wchar": 0,
                "read_bytes": 0,
                "write_bytes": 0,
                "cancelled_write_bytes": 0,
            },
        )
        current["processes"] += 1
        current["rss_kb"] += int(proc.get("rss_kb") or 0)
        io = proc.get("io") or {}
        for key in (
            "rchar",
            "wchar",
            "read_bytes",
            "write_bytes",
            "cancelled_write_bytes",
        ):
            current[key] += int(io.get(key) or 0)

    result["processes"] = sorted(
        result["processes"],
        key=lambda proc: (
            (proc.get("io") or {}).get("write_bytes", 0)
            + (proc.get("io") or {}).get("read_bytes", 0)
        ),
        reverse=True,
    )[:limit]
    result["by_cgroup"] = sorted(
        by_cgroup.values(),
        key=lambda row: row["write_bytes"] + row["read_bytes"],
        reverse=True,
    )

    for proc in below.get("process_peaks", []):
        text = f"{proc.get('comm') or ''} {proc.get('cmdline') or ''}".lower()
        if is_chrome_process(str(proc.get("comm") or ""), text):
            result["below_process_peaks"].append(proc)
    result["below_process_peaks"] = result["below_process_peaks"][:limit]
    result["available"] = bool(
        result["profiles"] or result["processes"] or result["below_process_peaks"]
    )
    if not result["available"]:
        result["gaps"] = ["chrome_io.no_profile_or_process_seen"]
    return result
