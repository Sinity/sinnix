"""Chrome I/O attribution: profile paths + /proc enumeration + below peaks."""

from __future__ import annotations

import glob
import os
import stat
from pathlib import Path
from typing import Any

from sinnix_lib.process import run
from sinnix_lib.values import int_or_none, read_text

from ..util import read_proc_cmdline
from .proc import parse_proc_cgroup, parse_proc_io, parse_proc_status

CHROME_PROFILE_GLOBS = [
    "/home/*/.config/chrome-ws",
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
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    candidates.append(config_home / "chrome-ws")
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
    if comm.strip().lower() in {"chrome", "chromium", "google-chrome"}:
        return True
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
    result = run(["du", "-s", "-B1", str(path)], timeout=2)
    if not result.ok:
        return None
    first = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
    return int_or_none(first.split()[0] if first else None)


def find_mount_for_path(path: Path) -> dict[str, Any]:
    result = run(
        ["findmnt", "-T", str(path), "-n", "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"],
        timeout=2,
    )
    if not result.stdout.strip():
        return {"unresolved": True}
    parts = result.stdout.strip().split(None, 3)
    return {
        "target": parts[0] if len(parts) > 0 else None,
        "source": parts[1] if len(parts) > 1 else None,
        "fstype": parts[2] if len(parts) > 2 else None,
        "options": parts[3] if len(parts) > 3 else None,
    }


def chrome_path_row(path: Path, include_size: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": str(path), "exists": None, "is_symlink": None, "realpath": None,
    }
    try:
        info = path.lstat()
        row["is_symlink"] = stat.S_ISLNK(info.st_mode)
        if row["is_symlink"]:
            info = path.stat()
        row.update(exists=True, is_directory=stat.S_ISDIR(info.st_mode), status="available")
        row["realpath"] = str(path.resolve(strict=False))
    except FileNotFoundError as exc:
        row.update(exists=False, status="dangling-link" if row["is_symlink"] else "missing", error=str(exc))
        return row
    except OSError as exc:
        row.update(exists=None, status="denied" if isinstance(exc, PermissionError) else "inaccessible", error=str(exc))
        return row
    row["mount"] = find_mount_for_path(path)
    if include_size:
        row["du_bytes"] = du_bytes(path)
    return row


def group_process_counters(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = ("rss_kb", "rchar", "wchar", "read_bytes", "write_bytes", "cancelled_write_bytes")
    groups: dict[str, dict[str, Any]] = {}
    for proc in processes:
        cgroup = proc.get("cgroup") or "(unknown)"
        row = groups.setdefault(cgroup, {
            "cgroup": cgroup, "processes": 0,
            "counter_coverage": {key: {"measured": 0, "missing": 0, "measured_sum": 0}
                                 for key in metrics},
        })
        row["processes"] += 1
        values = {**(proc.get("io") or {}), "rss_kb": proc.get("rss_kb")}
        for key in metrics:
            coverage = row["counter_coverage"][key]
            value = values.get(key)
            if value is None:
                coverage["missing"] += 1
            else:
                coverage["measured"] += 1
                coverage["measured_sum"] += int(value)
    for row in groups.values():
        for key, coverage in row["counter_coverage"].items():
            row[key] = None if coverage["missing"] else coverage["measured_sum"]
    return sorted(groups.values(), key=lambda row: (
        row["counter_coverage"]["write_bytes"]["measured_sum"]
        + row["counter_coverage"]["read_bytes"]["measured_sum"]), reverse=True)


def collect_chrome_io(
    offline: bool, below: dict[str, Any], limit: int
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "counter_scope": "live /proc/<pid>/io counters since each Chrome process started; cgroup totals are unknown when any observed process lacks a counter; counter_coverage retains measured subtotals",
        "profiles": [],
        "processes": [],
        "by_cgroup": [],
        "below_process_peaks": [],
    }
    if offline:
        result["offline"] = True
        return result

    for profile in chrome_profile_candidates():
        profile_row = chrome_path_row(profile, include_size=False)
        if profile_row["status"] == "missing":
            continue
        cache_rows = []
        if profile_row["status"] == "available":
            if not profile_row["is_directory"]:
                profile_row.update(status="wrong-type", error="Chrome profile is not a directory")
            else:
                for rel in CHROME_CACHE_RELATIVE_PATHS:
                    cache_row = chrome_path_row(profile / rel)
                    if cache_row["status"] != "missing":
                        cache_rows.append(cache_row)
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
        rss = (status.get("VmRSS") or "").split()
        result["processes"].append(
            {
                "pid": pid,
                "ppid": int_or_none(status.get("PPid")),
                "comm": comm,
                "state": status.get("State"),
                "rss_kb": int_or_none(rss[0] if rss else None),
                "cgroup": parse_proc_cgroup(proc_dir / "cgroup"),
                "io": io,
                "cmdline": cmdline[:300],
            }
        )

    result["by_cgroup"] = group_process_counters(result["processes"])
    result["processes"] = sorted(
        result["processes"],
        key=lambda proc: (
            (proc.get("io") or {}).get("write_bytes", 0)
            + (proc.get("io") or {}).get("read_bytes", 0)
        ),
        reverse=True,
    )[:limit]

    for proc in below.get("process_peaks", []):
        text = f"{proc.get('comm') or ''} {proc.get('cmdline') or ''}".lower()
        if is_chrome_process(str(proc.get("comm") or ""), text):
            result["below_process_peaks"].append(proc)
    result["below_process_peaks"] = result["below_process_peaks"][:limit]
    result["available"] = bool(
        any(row["status"] == "available" for row in result["profiles"])
        or result["processes"] or result["below_process_peaks"]
    )
    if not result["available"]:
        result["gaps"] = ["chrome_io.profile_unavailable" if result["profiles"] else "chrome_io.no_profile_or_process_seen"]
    return result
