from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

SCHEMA_VERSION = 5
# Interval between explicit `wal_checkpoint(TRUNCATE)` runs on the main
# writer connection; see the checkpoint block at the bottom of the heartbeat
# loop for why the implicit autocheckpoint is not enough here.
WAL_CHECKPOINT_INTERVAL_S = 900.0
UTC = dt.timezone.utc
DISKSTAT_FIELDS = (
    "reads_completed",
    "reads_merged",
    "sectors_read",
    "read_time_ms",
    "writes_completed",
    "writes_merged",
    "sectors_written",
    "write_time_ms",
    "ios_in_progress",
    "io_time_ms",
    "weighted_io_time_ms",
    "discards_completed",
    "discards_merged",
    "sectors_discarded",
    "discard_time_ms",
    "flushes_completed",
    "flush_time_ms",
)
PROC_IO_FIELDS = (
    "read_bytes",
    "write_bytes",
    "cancelled_write_bytes",
    "rchar",
    "wchar",
    "syscr",
    "syscw",
)
# /proc/vmstat keys captured verbatim as cumulative counters (consumers
# compute deltas), same convention as the psi *_total_us columns. These are
# the reclaim/refault/swap/OOM signals that the 2026-07-06 lag investigation
# found invisible to telemetry: workingset_refault_file=967M and
# pgscan_file=21.8e9 during the incident, with zero PSI-memory signal because
# the box was still meeting demand via reclaim, just slowly.
VMSTAT_FIELDS = (
    "workingset_refault_file",
    "workingset_refault_anon",
    "workingset_activate_file",
    "workingset_activate_anon",
    "pgscan_kswapd",
    "pgscan_direct",
    "pgsteal_kswapd",
    "pgsteal_direct",
    "pswpin",
    "pswpout",
    "allocstall_normal",
    "allocstall_movable",
    "oom_kill",
)


def now_iso() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat()


def read_text(path: str | Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def float_or_none(value: object) -> float | None:
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def int_or_none(value: object) -> int | None:
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def run_cmd(
    args: list[str], timeout: float = 3.0
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args, check=False, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def sysfs_temp_c(path: str | Path | None) -> float | None:
    if not path:
        return None
    value = float_or_none(read_text(path))
    if value is None:
        return None
    return round(value / 1000.0, 2)


def find_hwmon(target: str, occurrence: int = 1) -> Path | None:
    seen = 0
    for raw in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        path = Path(raw)
        if read_text(path / "name") == target:
            seen += 1
            if seen == occurrence:
                return path
    return None


def max_coretemp(coretemp: Path | None) -> float | None:
    if coretemp is None:
        return None
    values = [sysfs_temp_c(path) for path in coretemp.glob("temp*_input")]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def discover_rapl() -> list[dict[str, object]]:
    zones = []
    for raw in sorted(glob.glob("/sys/class/powercap/intel-rapl*")):
        path = Path(raw)
        name = read_text(path / "name")
        if not name or not (path / "energy_uj").exists():
            continue
        max_range = int_or_none(read_text(path / "max_energy_range_uj"))
        zones.append({"path": str(path), "name": name, "max": max_range})
    return zones


def read_rapl_energy(zones: list[dict[str, object]]) -> dict[str, int]:
    readings = {}
    for zone in zones:
        value = int_or_none(read_text(Path(str(zone["path"])) / "energy_uj"))
        if value is not None:
            readings[str(zone["path"])] = value
    return readings


def rapl_watts(
    zones: list[dict[str, object]],
    before: dict[str, int],
    after: dict[str, int],
    elapsed_s: float,
) -> dict[str, float]:
    watts = {}
    if elapsed_s <= 0:
        return watts
    for zone in zones:
        path = str(zone["path"])
        if path not in before or path not in after:
            continue
        delta = after[path] - before[path]
        max_range = zone.get("max")
        if delta < 0 and isinstance(max_range, int):
            delta += max_range
        watts[str(zone["name"])] = round((delta / 1_000_000.0) / elapsed_s, 3)
    return watts


def parse_psi(path: str) -> dict[str, float]:
    out = {}
    raw = read_text(path) or ""
    for line in raw.splitlines():
        parts = line.split()
        if not parts:
            continue
        prefix = parts[0]
        for item in parts[1:]:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            parsed = float_or_none(value)
            if parsed is not None:
                out[f"{prefix}_{key}"] = parsed
    return out


def dstate_tasks() -> tuple[int, str | None]:
    proc = run_cmd(["ps", "-eo", "stat,pid,wchan:32,comm,args"], timeout=3)
    if proc is None:
        return 0, "ps_failed"
    count = 0
    waits = []
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split(None, 4)
        if len(parts) >= 4 and parts[0].startswith("D"):
            count += 1
            waits.append(parts[2])
    return count, ",".join(sorted(set(waits))) if waits else None


def read_proc_io(pid: str) -> dict[str, int] | None:
    raw = read_text(Path("/proc") / pid / "io")
    if not raw:
        return None
    values: dict[str, int] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key in PROC_IO_FIELDS:
            parsed = int_or_none(value.strip())
            if parsed is not None:
                values[key] = parsed
    return values if values else None


def process_start_time_ticks(pid: str) -> int | None:
    raw = read_text(Path("/proc") / pid / "stat")
    if not raw or ")" not in raw:
        return None
    fields_after_comm = raw.rsplit(")", 1)[1].strip().split()
    if len(fields_after_comm) <= 19:
        return None
    return int_or_none(fields_after_comm[19])


def process_cgroup(pid: str) -> str | None:
    raw = read_text(Path("/proc") / pid / "cgroup")
    if not raw:
        return None
    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[1] == "":
            return parts[2]
    return None


def process_unit_from_cgroup(cgroup: str | None) -> tuple[str | None, str | None]:
    if not cgroup:
        return None, None
    for segment in reversed(cgroup.split("/")):
        if segment.endswith((".service", ".scope")):
            scope = "user" if "user.slice" in cgroup else "system"
            return systemd_unescape_fragment(segment), scope
    return None, None


def systemd_unescape_fragment(fragment: str) -> str:
    return re.sub(
        r"\\x([0-9A-Fa-f]{2})",
        lambda match: chr(int(match.group(1), 16)),
        fragment,
    )


def process_identity(pid: str) -> dict[str, object] | None:
    start_time = process_start_time_ticks(pid)
    if start_time is None:
        return None
    proc = Path("/proc") / pid
    comm = read_text(proc / "comm")
    try:
        exe = os.readlink(proc / "exe")
    except OSError:
        exe = None
    try:
        cmdline = (proc / "cmdline").read_bytes().replace(b"\0", b" ")
        command_line = cmdline.decode("utf-8", errors="replace").strip()
    except OSError:
        command_line = None
    cgroup = process_cgroup(pid)
    unit, scope = process_unit_from_cgroup(cgroup)
    return {
        "pid": int_or_none(pid),
        "process_start_time_ticks": start_time,
        "comm": comm,
        "exe": exe,
        "command_line": command_line[:500] if command_line else None,
        "cgroup": cgroup,
        "unit": unit,
        "scope": scope,
    }


def process_io_snapshot() -> dict[tuple[int, int], dict[str, object]]:
    snapshot: dict[tuple[int, int], dict[str, object]] = {}
    for proc_dir in Path("/proc").glob("[0-9]*"):
        pid = proc_dir.name
        counters = read_proc_io(pid)
        if counters is None:
            continue
        identity = process_identity(pid)
        if identity is None:
            continue
        parsed_pid = identity.get("pid")
        start_time = identity.get("process_start_time_ticks")
        if not isinstance(parsed_pid, int) or not isinstance(start_time, int):
            continue
        snapshot[(parsed_pid, start_time)] = {**identity, "counters": counters}
    return snapshot


def parse_smaps_rollup(pid: str) -> dict[str, int] | None:
    raw = read_text(Path("/proc") / pid / "smaps_rollup")
    if not raw:
        return None
    values: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[0].endswith(":"):
            continue
        parsed = int_or_none(parts[1])
        if parsed is not None:
            values[parts[0][:-1]] = parsed
    return values if values else None


def process_memory_rows(
    observed_at: str,
    host: str,
    boot_id: str | None,
    *,
    limit: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if limit <= 0:
        return rows
    for proc_dir in Path("/proc").glob("[0-9]*"):
        pid = proc_dir.name
        rollup = parse_smaps_rollup(pid)
        if not rollup or rollup.get("Pss", 0) <= 0:
            continue
        identity = process_identity(pid)
        if identity is None:
            continue
        parsed_pid = identity.get("pid")
        start_time = identity.get("process_start_time_ticks")
        if not isinstance(parsed_pid, int) or not isinstance(start_time, int):
            continue
        rows.append(
            {
                "observed_at": observed_at,
                "host": host,
                "boot_id": boot_id,
                "schema_version": SCHEMA_VERSION,
                "pid": parsed_pid,
                "process_start_time_ticks": start_time,
                "comm": identity.get("comm"),
                "exe": identity.get("exe"),
                "command_line": identity.get("command_line"),
                "cgroup": identity.get("cgroup"),
                "unit": identity.get("unit"),
                "scope": identity.get("scope"),
                "rss_kb": rollup.get("Rss", 0),
                "pss_kb": rollup.get("Pss", 0),
                "pss_anon_kb": rollup.get("Pss_Anon"),
                "pss_file_kb": rollup.get("Pss_File"),
                "pss_shmem_kb": rollup.get("Pss_Shmem"),
                "private_clean_kb": rollup.get("Private_Clean", 0),
                "private_dirty_kb": rollup.get("Private_Dirty", 0),
                "shared_clean_kb": rollup.get("Shared_Clean", 0),
                "shared_dirty_kb": rollup.get("Shared_Dirty", 0),
                "swap_kb": rollup.get("Swap", 0),
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row["pss_kb"]),
            -int(row["private_dirty_kb"]) - int(row["private_clean_kb"]),
            str(row.get("comm") or ""),
        )
    )
    return rows[:limit]


def insert_process_memory_rows(
    conn: sqlite3.Connection, rows: list[dict[str, object]]
) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO process_memory_sample (
          observed_at, host, boot_id, schema_version,
          pid, process_start_time_ticks, comm, exe, cgroup, unit, scope,
          command_line, rss_kb, pss_kb, pss_anon_kb, pss_file_kb,
          pss_shmem_kb, private_clean_kb, private_dirty_kb,
          shared_clean_kb, shared_dirty_kb, swap_kb
        ) VALUES (
          :observed_at, :host, :boot_id, :schema_version,
          :pid, :process_start_time_ticks, :comm, :exe, :cgroup, :unit, :scope,
          :command_line, :rss_kb, :pss_kb, :pss_anon_kb, :pss_file_kb,
          :pss_shmem_kb, :private_clean_kb, :private_dirty_kb,
          :shared_clean_kb, :shared_dirty_kb, :swap_kb
        )
        """,
        rows,
    )


def positive_delta(before: object, after: object) -> int:
    if not isinstance(before, int) or not isinstance(after, int) or after < before:
        return 0
    return after - before


def process_io_delta_rows(
    observed_at: str,
    host: str,
    boot_id: str | None,
    previous: dict[tuple[int, int], dict[str, object]],
    current: dict[tuple[int, int], dict[str, object]],
    *,
    interval_s: float,
    limit: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if interval_s <= 0:
        interval_s = 0.0
    for key, after_row in current.items():
        before_row = previous.get(key)
        if before_row is None:
            continue
        before = before_row.get("counters")
        after = after_row.get("counters")
        if not isinstance(before, dict) or not isinstance(after, dict):
            continue
        deltas = {
            field: positive_delta(before.get(field), after.get(field))
            for field in PROC_IO_FIELDS
        }
        total_bytes = deltas["read_bytes"] + deltas["write_bytes"]
        total_syscalls = deltas["syscr"] + deltas["syscw"]
        if total_bytes <= 0 and total_syscalls <= 0:
            continue
        rows.append(
            {
                "observed_at": observed_at,
                "host": host,
                "boot_id": boot_id,
                "schema_version": SCHEMA_VERSION,
                "interval_s": interval_s,
                "pid": after_row.get("pid"),
                "process_start_time_ticks": after_row.get("process_start_time_ticks"),
                "comm": after_row.get("comm"),
                "exe": after_row.get("exe"),
                "command_line": after_row.get("command_line"),
                "cgroup": after_row.get("cgroup"),
                "unit": after_row.get("unit"),
                "scope": after_row.get("scope"),
                "read_bytes_delta": deltas["read_bytes"],
                "write_bytes_delta": deltas["write_bytes"],
                "cancelled_write_bytes_delta": deltas["cancelled_write_bytes"],
                "read_chars_delta": deltas["rchar"],
                "write_chars_delta": deltas["wchar"],
                "read_syscalls_delta": deltas["syscr"],
                "write_syscalls_delta": deltas["syscw"],
                "total_bytes_delta": total_bytes,
                "total_syscalls_delta": total_syscalls,
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row["total_bytes_delta"]),
            -int(row["total_syscalls_delta"]),
            str(row.get("comm") or ""),
        )
    )
    return rows[:limit]


def insert_process_io_deltas(
    conn: sqlite3.Connection, rows: list[dict[str, object]]
) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO process_io_delta_sample (
          observed_at, host, boot_id, schema_version, interval_s,
          pid, process_start_time_ticks, comm, exe, cgroup, unit, scope,
          command_line,
          read_bytes_delta, write_bytes_delta, cancelled_write_bytes_delta,
          read_chars_delta, write_chars_delta, read_syscalls_delta,
          write_syscalls_delta, total_bytes_delta, total_syscalls_delta
        ) VALUES (
          :observed_at, :host, :boot_id, :schema_version, :interval_s,
          :pid, :process_start_time_ticks, :comm, :exe, :cgroup, :unit, :scope,
          :command_line,
          :read_bytes_delta, :write_bytes_delta, :cancelled_write_bytes_delta,
          :read_chars_delta, :write_chars_delta, :read_syscalls_delta,
          :write_syscalls_delta, :total_bytes_delta, :total_syscalls_delta
        )
        """,
        rows,
    )


def should_capture_block_device(device: str) -> bool:
    # loop/ram/zram are noise for host contention attribution. Keep physical
    # disks, their partitions, and dm-* mapper devices so analysis can choose
    # either whole-device or filesystem-facing counters.
    return not (
        device.startswith("loop")
        or device.startswith("ram")
        or device.startswith("zram")
        or device.startswith("fd")
    )


def block_device_stats(
    observed_at: str, host: str, boot_id: str | None
) -> list[dict[str, object]]:
    raw = read_text("/proc/diskstats")
    if not raw:
        return []
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        device = parts[2]
        if not should_capture_block_device(device):
            continue
        row: dict[str, object] = {
            "observed_at": observed_at,
            "host": host,
            "boot_id": boot_id,
            "schema_version": SCHEMA_VERSION,
            "major": int_or_none(parts[0]),
            "minor": int_or_none(parts[1]),
            "device": device,
        }
        values = [int_or_none(value) for value in parts[3:]]
        for index, field in enumerate(DISKSTAT_FIELDS):
            row[field] = values[index] if index < len(values) else None
        rows.append(row)
    return rows


def insert_block_device_stats(
    conn: sqlite3.Connection, observed_at: str, host: str, boot_id: str | None
) -> None:
    rows = block_device_stats(observed_at, host, boot_id)
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO block_device_sample (
          observed_at, host, boot_id, schema_version, major, minor, device,
          reads_completed, reads_merged, sectors_read, read_time_ms,
          writes_completed, writes_merged, sectors_written, write_time_ms,
          ios_in_progress, io_time_ms, weighted_io_time_ms,
          discards_completed, discards_merged, sectors_discarded,
          discard_time_ms, flushes_completed, flush_time_ms
        ) VALUES (
          :observed_at, :host, :boot_id, :schema_version, :major, :minor, :device,
          :reads_completed, :reads_merged, :sectors_read, :read_time_ms,
          :writes_completed, :writes_merged, :sectors_written, :write_time_ms,
          :ios_in_progress, :io_time_ms, :weighted_io_time_ms,
          :discards_completed, :discards_merged, :sectors_discarded,
          :discard_time_ms, :flushes_completed, :flush_time_ms
        )
        """,
        rows,
    )


def cgroup_io_stats(
    observed_at: str,
    host: str,
    boot_id: str | None,
    *,
    unit: str,
    scope: str,
    control_group: str | None,
) -> list[dict[str, object]]:
    if not control_group:
        return []
    path = Path("/sys/fs/cgroup") / control_group.lstrip("/") / "io.stat"
    raw = read_text(path)
    if not raw:
        return []
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        parts = line.split()
        if not parts or ":" not in parts[0]:
            continue
        major_text, minor_text = parts[0].split(":", 1)
        row: dict[str, object] = {
            "observed_at": observed_at,
            "host": host,
            "boot_id": boot_id,
            "schema_version": SCHEMA_VERSION,
            "unit": unit,
            "scope": scope,
            "control_group": control_group,
            "major": int_or_none(major_text),
            "minor": int_or_none(minor_text),
            "rbytes": None,
            "wbytes": None,
            "rios": None,
            "wios": None,
            "dbytes": None,
            "dios": None,
        }
        for item in parts[1:]:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            if key in row:
                row[key] = int_or_none(value)
        rows.append(row)
    return rows


def cgroup_pressure_stats(
    observed_at: str,
    host: str,
    boot_id: str | None,
    *,
    unit: str,
    scope: str,
    control_group: str | None,
) -> dict[str, object] | None:
    if not control_group:
        return None
    root = Path("/sys/fs/cgroup") / control_group.lstrip("/")
    cpu = parse_psi(str(root / "cpu.pressure"))
    io = parse_psi(str(root / "io.pressure"))
    memory = parse_psi(str(root / "memory.pressure"))
    if not cpu and not io and not memory:
        return None
    return {
        "observed_at": observed_at,
        "host": host,
        "boot_id": boot_id,
        "schema_version": SCHEMA_VERSION,
        "unit": unit,
        "scope": scope,
        "control_group": control_group,
        "cpu_some_avg10": cpu.get("some_avg10"),
        "cpu_some_avg60": cpu.get("some_avg60"),
        "cpu_some_avg300": cpu.get("some_avg300"),
        "cpu_some_total_us": cpu.get("some_total"),
        "io_some_avg10": io.get("some_avg10"),
        "io_some_avg60": io.get("some_avg60"),
        "io_some_avg300": io.get("some_avg300"),
        "io_some_total_us": io.get("some_total"),
        "io_full_avg10": io.get("full_avg10"),
        "io_full_avg60": io.get("full_avg60"),
        "io_full_avg300": io.get("full_avg300"),
        "io_full_total_us": io.get("full_total"),
        "memory_some_avg10": memory.get("some_avg10"),
        "memory_some_avg60": memory.get("some_avg60"),
        "memory_some_avg300": memory.get("some_avg300"),
        "memory_some_total_us": memory.get("some_total"),
        "memory_full_avg10": memory.get("full_avg10"),
        "memory_full_avg60": memory.get("full_avg60"),
        "memory_full_avg300": memory.get("full_avg300"),
        "memory_full_total_us": memory.get("full_total"),
    }


def cgroup_memory_stat(control_group: str | None) -> dict[str, int | None]:
    if not control_group:
        return {}
    path = Path("/sys/fs/cgroup") / control_group.lstrip("/") / "memory.stat"
    raw = read_text(path)
    if not raw:
        return {}
    values: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        parsed = int_or_none(parts[1])
        if parsed is not None:
            values[parts[0]] = parsed
    return {
        "memory_anon_bytes": values.get("anon"),
        "memory_file_bytes": values.get("file"),
        "memory_kernel_bytes": values.get("kernel"),
        "memory_slab_bytes": values.get("slab"),
        "memory_sock_bytes": values.get("sock"),
        "memory_shmem_bytes": values.get("shmem"),
        "memory_swapcached_bytes": values.get("swapcached"),
        "memory_zswap_bytes": values.get("zswap"),
        "memory_zswapped_bytes": values.get("zswapped"),
    }


def cgroup_path(control_group: str | None) -> Path | None:
    if not control_group:
        return None
    return Path("/sys/fs/cgroup") / control_group.lstrip("/")


def parse_cgroup_spec(raw: str) -> tuple[str, str, str] | None:
    parts = raw.split("|", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        return None
    label, scope, control_group = (part.strip() for part in parts)
    return label, scope, control_group


def parse_cgroup_events(control_group: str | None) -> dict[str, int | None]:
    root = cgroup_path(control_group)
    raw = read_text(root / "cgroup.events") if root is not None else None
    if not raw:
        return {}
    values: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        parsed = int_or_none(parts[1])
        if parsed is not None:
            values[parts[0]] = parsed
    return {
        "cgroup_populated": values.get("populated"),
        "cgroup_frozen": values.get("frozen"),
    }


def parse_memory_events(control_group: str | None) -> dict[str, int | None]:
    # cgroup v2 memory.events: cumulative counters distinct from cgroup.events
    # above (which tracks populated/frozen, not memory pressure). `high`/`max`
    # here are breach counts, not the memory.high/memory.max byte limits
    # already captured as memory_high_bytes/memory_max_bytes.
    root = cgroup_path(control_group)
    raw = read_text(root / "memory.events") if root is not None else None
    if not raw:
        return {}
    values: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        parsed = int_or_none(parts[1])
        if parsed is not None:
            values[parts[0]] = parsed
    return {
        "memory_events_high": values.get("high"),
        "memory_events_max": values.get("max"),
        "memory_events_oom": values.get("oom"),
        "memory_events_oom_kill": values.get("oom_kill"),
    }


def cgroup_memory_sample(
    observed_at: str,
    host: str,
    boot_id: str | None,
    *,
    label: str,
    scope: str,
    control_group: str,
) -> dict[str, object] | None:
    root = cgroup_path(control_group)
    if root is None or not root.exists():
        return None
    stat = cgroup_memory_stat(control_group)
    events = parse_cgroup_events(control_group)
    mem_events = parse_memory_events(control_group)
    return {
        "observed_at": observed_at,
        "host": host,
        "boot_id": boot_id,
        "schema_version": SCHEMA_VERSION,
        "label": label,
        "scope": scope,
        "control_group": control_group,
        "memory_current_bytes": int_or_none(read_text(root / "memory.current")),
        "memory_peak_bytes": int_or_none(read_text(root / "memory.peak")),
        "memory_swap_current_bytes": int_or_none(
            read_text(root / "memory.swap.current")
        ),
        "memory_swap_peak_bytes": int_or_none(read_text(root / "memory.swap.peak")),
        "memory_high_bytes": int_or_none(read_text(root / "memory.high")),
        "memory_max_bytes": int_or_none(read_text(root / "memory.max")),
        "memory_anon_bytes": stat.get("memory_anon_bytes"),
        "memory_file_bytes": stat.get("memory_file_bytes"),
        "memory_kernel_bytes": stat.get("memory_kernel_bytes"),
        "memory_slab_bytes": stat.get("memory_slab_bytes"),
        "memory_sock_bytes": stat.get("memory_sock_bytes"),
        "memory_shmem_bytes": stat.get("memory_shmem_bytes"),
        "memory_swapcached_bytes": stat.get("memory_swapcached_bytes"),
        "memory_zswap_bytes": stat.get("memory_zswap_bytes"),
        "memory_zswapped_bytes": stat.get("memory_zswapped_bytes"),
        "cgroup_populated": events.get("cgroup_populated"),
        "cgroup_frozen": events.get("cgroup_frozen"),
        "cgroup_freeze": int_or_none(read_text(root / "cgroup.freeze")),
        "memory_events_high": mem_events.get("memory_events_high"),
        "memory_events_max": mem_events.get("memory_events_max"),
        "memory_events_oom": mem_events.get("memory_events_oom"),
        "memory_events_oom_kill": mem_events.get("memory_events_oom_kill"),
    }


def cgroup_memory_samples(
    observed_at: str,
    host: str,
    boot_id: str | None,
    specs: list[tuple[str, str, str]],
) -> list[dict[str, object]]:
    rows = []
    for label, scope, control_group in specs:
        row = cgroup_memory_sample(
            observed_at,
            host,
            boot_id,
            label=label,
            scope=scope,
            control_group=control_group,
        )
        if row is not None:
            rows.append(row)
    return rows


def service_cgroup_memory_sample(
    observed_at: str,
    host: str,
    boot_id: str | None,
    *,
    unit: str,
    scope: str,
    control_group: str | None,
) -> dict[str, object] | None:
    if not control_group:
        return None
    return cgroup_memory_sample(
        observed_at,
        host,
        boot_id,
        label=f"unit:{unit}",
        scope=scope,
        control_group=control_group,
    )


def insert_cgroup_memory_stats(
    conn: sqlite3.Connection, rows: list[dict[str, object]]
) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO cgroup_memory_sample (
          observed_at, host, boot_id, schema_version, label, scope, control_group,
          memory_current_bytes, memory_peak_bytes, memory_swap_current_bytes,
          memory_swap_peak_bytes, memory_high_bytes, memory_max_bytes,
          memory_anon_bytes, memory_file_bytes, memory_kernel_bytes,
          memory_slab_bytes, memory_sock_bytes, memory_shmem_bytes,
          memory_swapcached_bytes, memory_zswap_bytes, memory_zswapped_bytes,
          cgroup_populated, cgroup_frozen, cgroup_freeze,
          memory_events_high, memory_events_max, memory_events_oom,
          memory_events_oom_kill
        ) VALUES (
          :observed_at, :host, :boot_id, :schema_version, :label, :scope,
          :control_group, :memory_current_bytes, :memory_peak_bytes,
          :memory_swap_current_bytes, :memory_swap_peak_bytes,
          :memory_high_bytes, :memory_max_bytes, :memory_anon_bytes,
          :memory_file_bytes, :memory_kernel_bytes, :memory_slab_bytes,
          :memory_sock_bytes, :memory_shmem_bytes, :memory_swapcached_bytes,
          :memory_zswap_bytes, :memory_zswapped_bytes, :cgroup_populated,
          :cgroup_frozen, :cgroup_freeze,
          :memory_events_high, :memory_events_max, :memory_events_oom,
          :memory_events_oom_kill
        )
        """,
        rows,
    )


def insert_cgroup_io_stats(
    conn: sqlite3.Connection, rows: list[dict[str, object]]
) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO service_cgroup_io_sample (
          observed_at, host, boot_id, schema_version, unit, scope,
          control_group, major, minor, rbytes, wbytes, rios, wios, dbytes, dios
        ) VALUES (
          :observed_at, :host, :boot_id, :schema_version, :unit, :scope,
          :control_group, :major, :minor, :rbytes, :wbytes, :rios, :wios,
          :dbytes, :dios
        )
        """,
        rows,
    )


def insert_cgroup_pressure_stats(
    conn: sqlite3.Connection, rows: list[dict[str, object]]
) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO service_cgroup_pressure_sample (
          observed_at, host, boot_id, schema_version, unit, scope,
          control_group,
          cpu_some_avg10, cpu_some_avg60, cpu_some_avg300, cpu_some_total_us,
          io_some_avg10, io_some_avg60, io_some_avg300, io_some_total_us,
          io_full_avg10, io_full_avg60, io_full_avg300, io_full_total_us,
          memory_some_avg10, memory_some_avg60, memory_some_avg300,
          memory_some_total_us,
          memory_full_avg10, memory_full_avg60, memory_full_avg300,
          memory_full_total_us
        ) VALUES (
          :observed_at, :host, :boot_id, :schema_version, :unit, :scope,
          :control_group,
          :cpu_some_avg10, :cpu_some_avg60, :cpu_some_avg300, :cpu_some_total_us,
          :io_some_avg10, :io_some_avg60, :io_some_avg300, :io_some_total_us,
          :io_full_avg10, :io_full_avg60, :io_full_avg300, :io_full_total_us,
          :memory_some_avg10, :memory_some_avg60, :memory_some_avg300,
          :memory_some_total_us,
          :memory_full_avg10, :memory_full_avg60, :memory_full_avg300,
          :memory_full_total_us
        )
        """,
        rows,
    )


# NVML handle is initialized once at startup and reused; reads are direct
# library calls (no subprocess), so 1 Hz sampling is cheap and per-sample
# latency is sub-millisecond. nvidia-smi is no longer in the hot path.
_nvml_handle: object | None = None
_nvml_error: str | None = None
# True only when pynvml itself is absent — a permanent condition, so we stop
# retrying. An NVMLError at init (driver/libnvidia-ml not ready at boot) is
# transient and must be retried, or a single bad startup permanently kills GPU
# capture until the next service restart (the 2026-05-24 incident).
_nvml_unavailable: bool = False
_nvml_lock = threading.Lock()
_nvml_last_init_attempt: float = 0.0
_NVML_REINIT_BACKOFF_S: float = 30.0


def nvml_init() -> bool:
    """(Re)initialize the NVML handle. Returns True iff a handle is ready.

    Thread-safe and idempotent: callable from both the heartbeat loop and the
    GPU sampler thread. ImportError is permanent (``_nvml_unavailable``); an
    NVMLError is transient and left retryable.
    """
    global _nvml_handle, _nvml_error, _nvml_unavailable, _nvml_last_init_attempt
    with _nvml_lock:
        if _nvml_handle is not None:
            return True
        if _nvml_unavailable:
            return False
        _nvml_last_init_attempt = time.monotonic()
        try:
            import pynvml
        except ImportError:
            _nvml_error = "gpu.pynvml_unavailable"
            _nvml_unavailable = True
            return False
        try:
            pynvml.nvmlInit()
            _nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            _nvml_error = None
            return True
        except pynvml.NVMLError as exc:  # type: ignore[attr-defined]
            _nvml_error = f"gpu.nvml_init_failed:{exc}"
            _nvml_handle = None
            return False


def nvml_ensure() -> bool:
    """Lazily (re)init NVML with a backoff. Returns True iff a handle is ready."""
    global _nvml_handle
    if _nvml_handle is not None:
        return True
    if _nvml_unavailable:
        return False
    if time.monotonic() - _nvml_last_init_attempt < _NVML_REINIT_BACKOFF_S:
        return False
    return nvml_init()


def gpu_metrics() -> tuple[dict[str, object], list[str]]:
    global _nvml_handle
    if not nvml_ensure():
        return {}, [_nvml_error or "gpu.nvml_not_initialized"]
    import pynvml

    h = _nvml_handle
    gaps: list[str] = []
    result: dict[str, object] = {}

    def safe(field: str, fn):
        try:
            result[field] = fn()
        except pynvml.NVMLError as exc:  # type: ignore[attr-defined]
            gaps.append(f"gpu.{field}:{exc}")
            result[field] = None

    safe("gpu_power_w", lambda: pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0)
    safe(
        "gpu_power_limit_w", lambda: pynvml.nvmlDeviceGetEnforcedPowerLimit(h) / 1000.0
    )
    safe(
        "gpu_temp_c",
        lambda: float(pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)),
    )
    safe("gpu_fan_pct", lambda: float(pynvml.nvmlDeviceGetFanSpeed(h)))
    util = None
    try:
        util = pynvml.nvmlDeviceGetUtilizationRates(h)
    except pynvml.NVMLError as exc:  # type: ignore[attr-defined]
        gaps.append(f"gpu.utilization:{exc}")
    result["gpu_util_pct"] = float(util.gpu) if util else None
    result["gpu_mem_util_pct"] = float(util.memory) if util else None
    safe(
        "gpu_clock_mhz",
        lambda: float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_GRAPHICS)),
    )
    safe(
        "gpu_mem_clock_mhz",
        lambda: float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM)),
    )
    try:
        result["gpu_pstate"] = f"P{pynvml.nvmlDeviceGetPerformanceState(h)}"
    except pynvml.NVMLError as exc:  # type: ignore[attr-defined]
        gaps.append(f"gpu.pstate:{exc}")
        result["gpu_pstate"] = None
    safe("gpu_pcie_gen", lambda: int(pynvml.nvmlDeviceGetCurrPcieLinkGeneration(h)))
    safe("gpu_pcie_width", lambda: int(pynvml.nvmlDeviceGetCurrPcieLinkWidth(h)))
    # If every probe failed the handle is dead (GPU reset / driver reload):
    # drop it so nvml_ensure() re-initializes on the next call rather than
    # emitting all-null rows indefinitely.
    if gaps and all(v is None for v in result.values()):
        with _nvml_lock:
            _nvml_handle = None
    return result, gaps


def gpu_sampler_thread(
    db_path: str,
    host: str,
    boot_id: str | None,
    interval: float,
    stop: threading.Event,
) -> None:
    # Dedicated thread with its own SQLite connection: high-frequency GPU
    # samples land in gpu_sample without contending with the main heartbeat
    # writer. WAL mode permits concurrent writers.
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    try:
        while not stop.is_set():
            try:
                metrics, _gaps = gpu_metrics()
                if metrics:
                    conn.execute(
                        """
                        INSERT INTO gpu_sample (
                          observed_at, host, boot_id,
                          gpu_power_w, gpu_power_limit_w, gpu_temp_c, gpu_fan_pct,
                          gpu_util_pct, gpu_mem_util_pct,
                          gpu_clock_mhz, gpu_mem_clock_mhz,
                          gpu_pstate, gpu_pcie_gen, gpu_pcie_width
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now_iso(),
                            host,
                            boot_id,
                            metrics.get("gpu_power_w"),
                            metrics.get("gpu_power_limit_w"),
                            metrics.get("gpu_temp_c"),
                            metrics.get("gpu_fan_pct"),
                            metrics.get("gpu_util_pct"),
                            metrics.get("gpu_mem_util_pct"),
                            metrics.get("gpu_clock_mhz"),
                            metrics.get("gpu_mem_clock_mhz"),
                            metrics.get("gpu_pstate"),
                            metrics.get("gpu_pcie_gen"),
                            metrics.get("gpu_pcie_width"),
                        ),
                    )
                    conn.commit()
            except Exception as exc:  # noqa: BLE001 - the sampler must outlive any probe/DB fault
                # A bare exception here would silently kill the only writer to
                # gpu_sample and freeze GPU telemetry with no signal — the same
                # outage class (2026-05-24) the NVML self-heal addresses, but on
                # the DB/probe path instead of the handle path. Log to stderr
                # (captured by journald) and keep sampling; handle-level faults
                # are recovered by the self-heal in gpu_metrics().
                print(
                    f"gpu-sampler: sample failed: {exc!r}", file=sys.stderr, flush=True
                )
            stop.wait(interval)
    finally:
        conn.close()


def hardware_state(host: str, rapl_zones: list[dict[str, object]]) -> dict[str, object]:
    cpu0 = Path("/sys/devices/system/cpu/cpu0/cpufreq")
    return {
        "schema_version": SCHEMA_VERSION,
        "host": host,
        "boot_id": read_text("/proc/sys/kernel/random/boot_id"),
        "captured_at": now_iso(),
        "kernel": os.uname().release,
        "machine": os.uname().machine,
        "cpu_driver": read_text(cpu0 / "scaling_driver"),
        "cpu_governor": read_text(cpu0 / "scaling_governor"),
        "cpu_min_freq_khz": int_or_none(read_text(cpu0 / "scaling_min_freq")),
        "cpu_max_freq_khz": int_or_none(read_text(cpu0 / "scaling_max_freq")),
        "cpu_no_turbo": int_or_none(
            read_text("/sys/devices/system/cpu/intel_pstate/no_turbo")
        ),
        "rapl_zones": rapl_zones,
    }


def ensure_columns(
    conn: sqlite3.Connection, table: str, columns: dict[str, str]
) -> None:
    existing = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, column_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS metric_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          interval_s REAL NOT NULL,
          latency_oversleep_ms REAL,
          collector_duration_ms REAL,
          cpu_package_w REAL,
          cpu_core_w REAL,
          cpu_pkg_c REAL,
          cpu_max_core_c REAL,
          ddr5_1_c REAL,
          ddr5_2_c REAL,
          nvme_1_c REAL,
          nvme_2_c REAL,
          motherboard_temps_json TEXT NOT NULL DEFAULT '[]',
          gpu_temp_c REAL,
          gpu_power_w REAL,
          gpu_power_limit_w REAL,
          gpu_fan_pct REAL,
          gpu_util_pct REAL,
          gpu_mem_util_pct REAL,
          gpu_clock_mhz REAL,
          gpu_mem_clock_mhz REAL,
          gpu_pstate TEXT,
          gpu_pcie_gen INTEGER,
          gpu_pcie_width INTEGER,
          load_1m REAL,
          load_5m REAL,
          mem_total_mb INTEGER,
          mem_used_mb INTEGER,
          mem_avail_mb INTEGER,
          mem_anon_mb INTEGER,
          mem_file_cache_mb INTEGER,
          mem_slab_reclaimable_mb INTEGER,
          mem_slab_unreclaimable_mb INTEGER,
          mem_dirty_mb INTEGER,
          mem_writeback_mb INTEGER,
          mem_shmem_mb INTEGER,
          swap_used_mb INTEGER,
          cpu_psi_some_avg10 REAL,
          cpu_psi_some_avg60 REAL,
          cpu_psi_some_avg300 REAL,
          cpu_psi_some_total_us REAL,
          io_psi_some_avg10 REAL,
          io_psi_some_avg60 REAL,
          io_psi_some_avg300 REAL,
          io_psi_some_total_us REAL,
          io_psi_full_avg10 REAL,
          io_psi_full_avg60 REAL,
          io_psi_full_avg300 REAL,
          io_psi_full_total_us REAL,
          memory_psi_some_avg10 REAL,
          memory_psi_some_avg60 REAL,
          memory_psi_some_avg300 REAL,
          memory_psi_some_total_us REAL,
          memory_psi_full_avg10 REAL,
          memory_psi_full_avg60 REAL,
          memory_psi_full_avg300 REAL,
          memory_psi_full_total_us REAL,
          dstate_task_count INTEGER,
          dstate_wchan_summary TEXT,
          gap_codes_json TEXT NOT NULL DEFAULT '[]',
          vmstat_workingset_refault_file INTEGER,
          vmstat_workingset_refault_anon INTEGER,
          vmstat_workingset_activate_file INTEGER,
          vmstat_workingset_activate_anon INTEGER,
          vmstat_pgscan_kswapd INTEGER,
          vmstat_pgscan_direct INTEGER,
          vmstat_pgsteal_kswapd INTEGER,
          vmstat_pgsteal_direct INTEGER,
          vmstat_pswpin INTEGER,
          vmstat_pswpout INTEGER,
          vmstat_allocstall_normal INTEGER,
          vmstat_allocstall_movable INTEGER,
          vmstat_oom_kill INTEGER
        );
        CREATE INDEX IF NOT EXISTS metric_sample_observed_at ON metric_sample(observed_at);
        CREATE TABLE IF NOT EXISTS hardware_state (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          captured_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS hardware_state_captured_at ON hardware_state(captured_at);
        CREATE TABLE IF NOT EXISTS gpu_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          gpu_power_w REAL,
          gpu_power_limit_w REAL,
          gpu_temp_c REAL,
          gpu_fan_pct REAL,
          gpu_util_pct REAL,
          gpu_mem_util_pct REAL,
          gpu_clock_mhz REAL,
          gpu_mem_clock_mhz REAL,
          gpu_pstate TEXT,
          gpu_pcie_gen INTEGER,
          gpu_pcie_width INTEGER
        );
        CREATE INDEX IF NOT EXISTS gpu_sample_observed_at ON gpu_sample(observed_at);
        CREATE TABLE IF NOT EXISTS service_state (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          unit TEXT NOT NULL,
          scope TEXT NOT NULL,
          active_state TEXT,
          sub_state TEXT,
          main_pid INTEGER,
          control_group TEXT,
          memory_current_bytes INTEGER,
          memory_anon_bytes INTEGER,
          memory_file_bytes INTEGER,
          memory_kernel_bytes INTEGER,
          memory_slab_bytes INTEGER,
          memory_sock_bytes INTEGER,
          memory_shmem_bytes INTEGER,
          memory_swapcached_bytes INTEGER,
          memory_zswap_bytes INTEGER,
          memory_zswapped_bytes INTEGER,
          cpu_usage_nsec INTEGER,
          io_read_bytes INTEGER,
          io_write_bytes INTEGER
        );
        CREATE INDEX IF NOT EXISTS service_state_unit_time ON service_state(unit, observed_at);
        CREATE TABLE IF NOT EXISTS block_device_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          major INTEGER,
          minor INTEGER,
          device TEXT NOT NULL,
          reads_completed INTEGER,
          reads_merged INTEGER,
          sectors_read INTEGER,
          read_time_ms INTEGER,
          writes_completed INTEGER,
          writes_merged INTEGER,
          sectors_written INTEGER,
          write_time_ms INTEGER,
          ios_in_progress INTEGER,
          io_time_ms INTEGER,
          weighted_io_time_ms INTEGER,
          discards_completed INTEGER,
          discards_merged INTEGER,
          sectors_discarded INTEGER,
          discard_time_ms INTEGER,
          flushes_completed INTEGER,
          flush_time_ms INTEGER
        );
        CREATE INDEX IF NOT EXISTS block_device_sample_device_time ON block_device_sample(device, observed_at);
        CREATE INDEX IF NOT EXISTS block_device_sample_observed_at ON block_device_sample(observed_at);
        CREATE TABLE IF NOT EXISTS service_cgroup_io_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          unit TEXT NOT NULL,
          scope TEXT NOT NULL,
          control_group TEXT,
          major INTEGER,
          minor INTEGER,
          rbytes INTEGER,
          wbytes INTEGER,
          rios INTEGER,
          wios INTEGER,
          dbytes INTEGER,
          dios INTEGER
        );
        CREATE INDEX IF NOT EXISTS service_cgroup_io_sample_unit_time ON service_cgroup_io_sample(unit, observed_at);
        CREATE INDEX IF NOT EXISTS service_cgroup_io_sample_device_time ON service_cgroup_io_sample(major, minor, observed_at);
        CREATE TABLE IF NOT EXISTS service_cgroup_pressure_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          unit TEXT NOT NULL,
          scope TEXT NOT NULL,
          control_group TEXT,
          cpu_some_avg10 REAL,
          cpu_some_avg60 REAL,
          cpu_some_avg300 REAL,
          cpu_some_total_us REAL,
          io_some_avg10 REAL,
          io_some_avg60 REAL,
          io_some_avg300 REAL,
          io_some_total_us REAL,
          io_full_avg10 REAL,
          io_full_avg60 REAL,
          io_full_avg300 REAL,
          io_full_total_us REAL,
          memory_some_avg10 REAL,
          memory_some_avg60 REAL,
          memory_some_avg300 REAL,
          memory_some_total_us REAL,
          memory_full_avg10 REAL,
          memory_full_avg60 REAL,
          memory_full_avg300 REAL,
          memory_full_total_us REAL
        );
        CREATE INDEX IF NOT EXISTS service_cgroup_pressure_sample_unit_time ON service_cgroup_pressure_sample(unit, observed_at);
        CREATE TABLE IF NOT EXISTS cgroup_memory_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          label TEXT NOT NULL,
          scope TEXT NOT NULL,
          control_group TEXT NOT NULL,
          memory_current_bytes INTEGER,
          memory_peak_bytes INTEGER,
          memory_swap_current_bytes INTEGER,
          memory_swap_peak_bytes INTEGER,
          memory_high_bytes INTEGER,
          memory_max_bytes INTEGER,
          memory_anon_bytes INTEGER,
          memory_file_bytes INTEGER,
          memory_kernel_bytes INTEGER,
          memory_slab_bytes INTEGER,
          memory_sock_bytes INTEGER,
          memory_shmem_bytes INTEGER,
          memory_swapcached_bytes INTEGER,
          memory_zswap_bytes INTEGER,
          memory_zswapped_bytes INTEGER,
          cgroup_populated INTEGER,
          cgroup_frozen INTEGER,
          cgroup_freeze INTEGER,
          memory_events_high INTEGER,
          memory_events_max INTEGER,
          memory_events_oom INTEGER,
          memory_events_oom_kill INTEGER
        );
        CREATE INDEX IF NOT EXISTS cgroup_memory_sample_label_time ON cgroup_memory_sample(label, observed_at);
        CREATE INDEX IF NOT EXISTS cgroup_memory_sample_scope_time ON cgroup_memory_sample(scope, observed_at);
        CREATE TABLE IF NOT EXISTS kill_event (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          killer TEXT NOT NULL,
          victim_comm TEXT,
          victim_pid INTEGER,
          victim_rss_mib INTEGER,
          cgroup_path TEXT,
          oom_score INTEGER,
          raw_line TEXT NOT NULL,
          journal_cursor TEXT
        );
        CREATE INDEX IF NOT EXISTS kill_event_observed_at ON kill_event(observed_at);
        CREATE INDEX IF NOT EXISTS kill_event_killer_time ON kill_event(killer, observed_at);
        CREATE TABLE IF NOT EXISTS process_io_delta_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          interval_s REAL NOT NULL,
          pid INTEGER NOT NULL,
          process_start_time_ticks INTEGER NOT NULL,
          comm TEXT,
          exe TEXT,
          command_line TEXT,
          cgroup TEXT,
          unit TEXT,
          scope TEXT,
          read_bytes_delta INTEGER NOT NULL,
          write_bytes_delta INTEGER NOT NULL,
          cancelled_write_bytes_delta INTEGER NOT NULL,
          read_chars_delta INTEGER NOT NULL,
          write_chars_delta INTEGER NOT NULL,
          read_syscalls_delta INTEGER NOT NULL,
          write_syscalls_delta INTEGER NOT NULL,
          total_bytes_delta INTEGER NOT NULL,
          total_syscalls_delta INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS process_io_delta_sample_observed_at ON process_io_delta_sample(observed_at);
        CREATE INDEX IF NOT EXISTS process_io_delta_sample_unit_time ON process_io_delta_sample(unit, observed_at);
        CREATE INDEX IF NOT EXISTS process_io_delta_sample_process_time ON process_io_delta_sample(pid, process_start_time_ticks, observed_at);
        CREATE TABLE IF NOT EXISTS process_memory_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          pid INTEGER NOT NULL,
          process_start_time_ticks INTEGER NOT NULL,
          comm TEXT,
          exe TEXT,
          command_line TEXT,
          cgroup TEXT,
          unit TEXT,
          scope TEXT,
          rss_kb INTEGER NOT NULL,
          pss_kb INTEGER NOT NULL,
          pss_anon_kb INTEGER,
          pss_file_kb INTEGER,
          pss_shmem_kb INTEGER,
          private_clean_kb INTEGER NOT NULL,
          private_dirty_kb INTEGER NOT NULL,
          shared_clean_kb INTEGER NOT NULL,
          shared_dirty_kb INTEGER NOT NULL,
          swap_kb INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS process_memory_sample_observed_at ON process_memory_sample(observed_at);
        CREATE INDEX IF NOT EXISTS process_memory_sample_unit_time ON process_memory_sample(unit, observed_at);
        CREATE INDEX IF NOT EXISTS process_memory_sample_process_time ON process_memory_sample(pid, process_start_time_ticks, observed_at);
        CREATE TABLE IF NOT EXISTS source_status (
          source TEXT PRIMARY KEY,
          checked_at TEXT NOT NULL,
          status TEXT NOT NULL,
          reason TEXT,
          payload_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS network_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          host TEXT NOT NULL,
          boot_id TEXT,
          schema_version INTEGER NOT NULL,
          interface TEXT NOT NULL,
          gateway_ip TEXT NOT NULL,
          ping_json TEXT NOT NULL DEFAULT '{}',
          bloat_json TEXT,
          iface_json TEXT NOT NULL DEFAULT '{}',
          nic_json TEXT NOT NULL DEFAULT '{}',
          tcp_json TEXT NOT NULL DEFAULT '{}',
          dns_ms INTEGER,
          pmtu_1492 INTEGER,
          conntrack_json TEXT NOT NULL DEFAULT '{}',
          gap_codes_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE UNIQUE INDEX IF NOT EXISTS network_sample_host_observed_at ON network_sample(host, observed_at);
        CREATE INDEX IF NOT EXISTS network_sample_observed_at ON network_sample(observed_at);
        """
    )
    ensure_columns(
        conn,
        "metric_sample",
        {
            "cpu_psi_some_avg60": "REAL",
            "cpu_psi_some_avg300": "REAL",
            "cpu_psi_some_total_us": "REAL",
            "io_psi_some_avg60": "REAL",
            "io_psi_some_avg300": "REAL",
            "io_psi_some_total_us": "REAL",
            "io_psi_full_avg60": "REAL",
            "io_psi_full_avg300": "REAL",
            "io_psi_full_total_us": "REAL",
            "memory_psi_some_avg60": "REAL",
            "memory_psi_some_avg300": "REAL",
            "memory_psi_some_total_us": "REAL",
            "memory_psi_full_avg60": "REAL",
            "memory_psi_full_avg300": "REAL",
            "memory_psi_full_total_us": "REAL",
            "mem_total_mb": "INTEGER",
            "mem_anon_mb": "INTEGER",
            "mem_file_cache_mb": "INTEGER",
            "mem_slab_reclaimable_mb": "INTEGER",
            "mem_slab_unreclaimable_mb": "INTEGER",
            "mem_dirty_mb": "INTEGER",
            "mem_writeback_mb": "INTEGER",
            "mem_shmem_mb": "INTEGER",
            "vmstat_workingset_refault_file": "INTEGER",
            "vmstat_workingset_refault_anon": "INTEGER",
            "vmstat_workingset_activate_file": "INTEGER",
            "vmstat_workingset_activate_anon": "INTEGER",
            "vmstat_pgscan_kswapd": "INTEGER",
            "vmstat_pgscan_direct": "INTEGER",
            "vmstat_pgsteal_kswapd": "INTEGER",
            "vmstat_pgsteal_direct": "INTEGER",
            "vmstat_pswpin": "INTEGER",
            "vmstat_pswpout": "INTEGER",
            "vmstat_allocstall_normal": "INTEGER",
            "vmstat_allocstall_movable": "INTEGER",
            "vmstat_oom_kill": "INTEGER",
            "zram_orig_mb": "INTEGER",
            "zram_compr_mb": "INTEGER",
            "zram_mem_used_mb": "INTEGER",
            "swaps_json": "TEXT",
        },
    )
    ensure_columns(
        conn,
        "cgroup_memory_sample",
        {
            "memory_events_high": "INTEGER",
            "memory_events_max": "INTEGER",
            "memory_events_oom": "INTEGER",
            "memory_events_oom_kill": "INTEGER",
        },
    )
    ensure_columns(
        conn,
        "service_state",
        {
            "memory_anon_bytes": "INTEGER",
            "memory_file_bytes": "INTEGER",
            "memory_kernel_bytes": "INTEGER",
            "memory_slab_bytes": "INTEGER",
            "memory_sock_bytes": "INTEGER",
            "memory_shmem_bytes": "INTEGER",
            "memory_swapcached_bytes": "INTEGER",
            "memory_zswap_bytes": "INTEGER",
            "memory_zswapped_bytes": "INTEGER",
        },
    )
    ensure_columns(
        conn,
        "process_io_delta_sample",
        {
            "command_line": "TEXT",
        },
    )


def parse_ping(ip: str) -> dict[str, object]:
    proc = run_cmd(["ping", "-c", "3", "-i", "0.2", "-W", "1", "-q", ip], timeout=5)
    if proc is None:
        return {
            "ip": ip,
            "loss": 100,
            "min_ms": None,
            "avg_ms": None,
            "max_ms": None,
            "status": "timeout",
        }
    out = "\n".join([proc.stdout, proc.stderr])
    loss_match = re.search(r"([0-9.]+)% packet loss", out)
    rtt_match = re.search(r"(?:rtt|round-trip).* = ([0-9.]+)/([0-9.]+)/([0-9.]+)/", out)
    return {
        "ip": ip,
        "loss": float_or_none(loss_match.group(1)) if loss_match else 100.0,
        "min_ms": float_or_none(rtt_match.group(1)) if rtt_match else None,
        "avg_ms": float_or_none(rtt_match.group(2)) if rtt_match else None,
        "max_ms": float_or_none(rtt_match.group(3)) if rtt_match else None,
        "status": "ok" if proc.returncode == 0 else "failed",
    }


def ethtool_value(dev: str, pattern: str) -> str | None:
    proc = run_cmd(["ethtool", dev], timeout=3)
    if proc is None or proc.returncode != 0:
        return None
    match = re.search(pattern, proc.stdout)
    return match.group(1) if match else None


def network_probe(
    host: str, boot_id: str | None, interface: str, gateway: str, *, do_bloat: bool
) -> dict[str, object]:
    gaps: list[str] = []
    observed_at = now_iso()
    ping = {
        "gateway": parse_ping(gateway),
        "cloudflare": parse_ping("1.1.1.1"),
        "google": parse_ping("8.8.8.8"),
        "cdn": parse_ping("104.16.0.1"),
    }
    bloat = None
    if do_bloat:
        curl_proc = None
        try:
            curl_proc = subprocess.Popen(
                [
                    "curl",
                    "-4",
                    "-o",
                    "/dev/null",
                    "-s",
                    "--max-time",
                    "6",
                    "https://speed.cloudflare.com/__down?bytes=10000000",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
            bloat = parse_ping("8.8.8.8")
        except OSError:
            gaps.append("network.bufferbloat_curl_unavailable")
        finally:
            if curl_proc is not None:
                curl_proc.terminate()
                try:
                    curl_proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    curl_proc.kill()

    iface_root = Path("/sys/class/net") / interface / "statistics"
    iface = {}
    for key in (
        "rx_bytes",
        "tx_bytes",
        "rx_errors",
        "tx_errors",
        "rx_dropped",
        "tx_dropped",
        "collisions",
    ):
        value = int_or_none(read_text(iface_root / key))
        iface[key] = value if value is not None else 0
    if not iface_root.exists():
        gaps.append("network.interface_missing")

    speed = int_or_none(ethtool_value(interface, r"Speed:\s*([0-9]+)"))
    duplex = ethtool_value(interface, r"Duplex:\s*(\w+)") or "unknown"
    link = ethtool_value(interface, r"Link detected:\s*(\w+)") or "unknown"
    nic = {"speed_mbps": speed or 0, "duplex": duplex, "link": link}

    tcp_line = ""
    try:
        lines = Path("/proc/net/snmp").read_text(encoding="utf-8").splitlines()
        tcp_rows = [line for line in lines if line.startswith("Tcp:")]
        tcp_line = tcp_rows[-1] if len(tcp_rows) >= 2 else ""
    except OSError:
        gaps.append("network.proc_net_snmp_unavailable")
    tcp_parts = tcp_line.split()
    tcp = {
        "retrans": int_or_none(tcp_parts[12]) if len(tcp_parts) > 12 else None,
        "in_errs": int_or_none(tcp_parts[13]) if len(tcp_parts) > 13 else None,
        "out_rsts": int_or_none(tcp_parts[14]) if len(tcp_parts) > 14 else None,
        "established": 0,
        "timewait": 0,
    }
    established = run_cmd(["ss", "-tn", "state", "established"], timeout=3)
    timewait = run_cmd(["ss", "-tn", "state", "time-wait"], timeout=3)
    if established is not None:
        tcp["established"] = max(len(established.stdout.splitlines()) - 1, 0)
    if timewait is not None:
        tcp["timewait"] = max(len(timewait.stdout.splitlines()) - 1, 0)

    dns_start = time.monotonic()
    dns = run_cmd(["nslookup", "example.com"], timeout=3)
    dns_ms = int((time.monotonic() - dns_start) * 1000)
    if dns is None or dns.returncode != 0:
        gaps.append("network.dns_probe_failed")

    pmtu = run_cmd(
        ["ping", "-c", "1", "-W", "2", "-M", "do", "-s", "1464", "8.8.8.8"], timeout=4
    )
    conntrack = {
        "count": int_or_none(read_text("/proc/sys/net/netfilter/nf_conntrack_count")),
        "max": int_or_none(read_text("/proc/sys/net/netfilter/nf_conntrack_max")),
    }
    return {
        "observed_at": observed_at,
        "host": host,
        "boot_id": boot_id,
        "schema_version": SCHEMA_VERSION,
        "interface": interface,
        "gateway_ip": gateway,
        "ping_json": json.dumps(ping, sort_keys=True),
        "bloat_json": json.dumps(bloat, sort_keys=True) if bloat is not None else None,
        "iface_json": json.dumps(iface, sort_keys=True),
        "nic_json": json.dumps(nic, sort_keys=True),
        "tcp_json": json.dumps(tcp, sort_keys=True),
        "dns_ms": dns_ms,
        "pmtu_1492": int(pmtu is not None and pmtu.returncode == 0),
        "conntrack_json": json.dumps(conntrack, sort_keys=True),
        "gap_codes_json": json.dumps(sorted(set(gaps))),
    }


def insert_network_sample(conn: sqlite3.Connection, row: dict[str, object]) -> int:
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO network_sample (
          observed_at, host, boot_id, schema_version, interface, gateway_ip,
          ping_json, bloat_json, iface_json, nic_json, tcp_json, dns_ms,
          pmtu_1492, conntrack_json, gap_codes_json
        ) VALUES (
          :observed_at, :host, :boot_id, :schema_version, :interface, :gateway_ip,
          :ping_json, :bloat_json, :iface_json, :nic_json, :tcp_json, :dns_ms,
          :pmtu_1492, :conntrack_json, :gap_codes_json
        )
        """,
        row,
    )
    return int(cur.rowcount)


def memory_metrics() -> dict[str, int | None]:
    values = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value = line.split(":", 1)
        amount = int_or_none(value.strip().split()[0])
        if amount is not None:
            values[key] = amount
    total = values.get("MemTotal")
    avail = values.get("MemAvailable")
    swap_total = values.get("SwapTotal", 0)
    swap_free = values.get("SwapFree", 0)
    cached = values.get("Cached", 0)
    buffers = values.get("Buffers", 0)
    sreclaimable = values.get("SReclaimable", 0)
    return {
        "mem_total_mb": int(total / 1024) if total is not None else None,
        "mem_used_mb": int((total - avail) / 1024)
        if total is not None and avail is not None
        else None,
        "mem_avail_mb": int(avail / 1024) if avail is not None else None,
        "mem_anon_mb": int(values.get("AnonPages", 0) / 1024),
        "mem_file_cache_mb": int((cached + buffers) / 1024),
        "mem_slab_reclaimable_mb": int(sreclaimable / 1024),
        "mem_slab_unreclaimable_mb": int(values.get("SUnreclaim", 0) / 1024),
        "mem_dirty_mb": int(values.get("Dirty", 0) / 1024),
        "mem_writeback_mb": int(values.get("Writeback", 0) / 1024),
        "mem_shmem_mb": int(values.get("Shmem", 0) / 1024),
        "swap_used_mb": int((swap_total - swap_free) / 1024)
        if swap_total is not None and swap_free is not None
        else None,
    }


def swap_tier_metrics() -> dict[str, object]:
    """Sample the tiered swap posture: zram compression economics + per-device
    occupancy. zram mm_stat answers "how much RAM is the compressed tier
    actually costing vs holding" (the load-bearing number for the sinnix-mys
    zram-return decision); /proc/swaps shows how pressure distributes across
    the zram (prio 100) and NVMe-file (prio 10) tiers."""
    out: dict[str, object] = {
        "zram_orig_mb": None,
        "zram_compr_mb": None,
        "zram_mem_used_mb": None,
        "swaps_json": None,
    }
    try:
        fields = Path("/sys/block/zram0/mm_stat").read_text(encoding="utf-8").split()
        # mm_stat: orig_data_size compr_data_size mem_used_total mem_limit
        #          mem_used_max same_pages pages_compacted [huge_pages ...]
        out["zram_orig_mb"] = int(int(fields[0]) / 1048576)
        out["zram_compr_mb"] = int(int(fields[1]) / 1048576)
        out["zram_mem_used_mb"] = int(int(fields[2]) / 1048576)
    except (OSError, ValueError, IndexError):
        pass
    try:
        swaps = []
        for line in Path("/proc/swaps").read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 5:
                swaps.append(
                    {
                        "device": parts[0],
                        "type": parts[1],
                        "size_kb": int_or_none(parts[2]),
                        "used_kb": int_or_none(parts[3]),
                        "priority": int_or_none(parts[4]),
                    }
                )
        out["swaps_json"] = json.dumps(swaps, sort_keys=True)
    except OSError:
        pass
    return out


def vmstat_metrics() -> dict[str, int | None]:
    values: dict[str, int] = {}
    for line in Path("/proc/vmstat").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        parsed = int_or_none(parts[1])
        if parsed is not None:
            values[parts[0]] = parsed
    return {f"vmstat_{key}": values.get(key) for key in VMSTAT_FIELDS}


def systemctl_props(
    unit: str, *, user: bool = False, user_name: str | None = None
) -> dict[str, str]:
    cmd = ["systemctl"]
    if user:
        if user_name:
            cmd.extend(["--user", f"--machine={user_name}@"])
        else:
            cmd.append("--user")
    cmd += [
        "show",
        unit,
        "--no-pager",
        "-p",
        "ActiveState",
        "-p",
        "SubState",
        "-p",
        "MainPID",
        "-p",
        "ControlGroup",
        "-p",
        "MemoryCurrent",
        "-p",
        "CPUUsageNSec",
        "-p",
        "IOReadBytes",
        "-p",
        "IOWriteBytes",
    ]
    try:
        proc = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=3
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    props = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            props[key] = value
    return props


def insert_service_states(
    conn: sqlite3.Connection,
    host: str,
    boot_id: str | None,
    units: list[str],
    user_name: str,
) -> None:
    observed_at = now_iso()
    rows = []
    io_rows: list[dict[str, object]] = []
    pressure_rows: list[dict[str, object]] = []
    cgroup_memory_rows: list[dict[str, object]] = []
    for unit in units:
        user = unit == "polylogued.service"
        props = systemctl_props(unit, user=user, user_name=user_name)
        if not props:
            continue
        scope = "user" if user else "system"
        control_group = props.get("ControlGroup")
        memory_stat = cgroup_memory_stat(control_group)
        rows.append(
            (
                observed_at,
                host,
                boot_id,
                unit,
                scope,
                props.get("ActiveState"),
                props.get("SubState"),
                int_or_none(props.get("MainPID")),
                control_group,
                int_or_none(props.get("MemoryCurrent")),
                memory_stat.get("memory_anon_bytes"),
                memory_stat.get("memory_file_bytes"),
                memory_stat.get("memory_kernel_bytes"),
                memory_stat.get("memory_slab_bytes"),
                memory_stat.get("memory_sock_bytes"),
                memory_stat.get("memory_shmem_bytes"),
                memory_stat.get("memory_swapcached_bytes"),
                memory_stat.get("memory_zswap_bytes"),
                memory_stat.get("memory_zswapped_bytes"),
                int_or_none(props.get("CPUUsageNSec")),
                int_or_none(props.get("IOReadBytes")),
                int_or_none(props.get("IOWriteBytes")),
            )
        )
        io_rows.extend(
            cgroup_io_stats(
                observed_at,
                host,
                boot_id,
                unit=unit,
                scope=scope,
                control_group=control_group,
            )
        )
        pressure = cgroup_pressure_stats(
            observed_at,
            host,
            boot_id,
            unit=unit,
            scope=scope,
            control_group=control_group,
        )
        if pressure is not None:
            pressure_rows.append(pressure)
        service_memory = service_cgroup_memory_sample(
            observed_at,
            host,
            boot_id,
            unit=unit,
            scope=scope,
            control_group=control_group,
        )
        if service_memory is not None:
            cgroup_memory_rows.append(service_memory)
    if rows:
        conn.executemany(
            """
            INSERT INTO service_state (
              observed_at, host, boot_id, unit, scope, active_state, sub_state,
              main_pid, control_group, memory_current_bytes,
              memory_anon_bytes, memory_file_bytes, memory_kernel_bytes,
              memory_slab_bytes, memory_sock_bytes, memory_shmem_bytes,
              memory_swapcached_bytes, memory_zswap_bytes, memory_zswapped_bytes,
              cpu_usage_nsec, io_read_bytes, io_write_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    insert_cgroup_io_stats(conn, io_rows)
    insert_cgroup_pressure_stats(conn, pressure_rows)
    insert_cgroup_memory_stats(conn, cgroup_memory_rows)


# journalctl -g pre-filters at the journald layer so a cursor-less backfill
# over weeks of history doesn't have to pipe every uninteresting line through
# Python. Patterns calibrated 2026-07-06 against this host's real incidents
# (2026-06-30 earlyoom storm, 2026-07-04 79x-kitten storm) — see the earlyoom
# message shape below; systemd-oomd and kernel-OOM patterns are best-effort
# from documented formats since this host has not yet had a real kill from
# either (raw_line is always kept so an imperfect field match loses nothing).
KILL_EVENT_GREP = (
    r"sending (SIGTERM|SIGKILL) to process|"
    r"^Killed process|"
    r"oom-kill:constraint=|"
    r"^Killed /"
)
KILL_EVENT_PATTERNS = (
    (
        "earlyoom",
        re.compile(
            r'sending (?:SIGTERM|SIGKILL) to process (?P<pid>\d+) uid \d+ '
            r'"(?P<comm>[^"]+)": oom_score (?P<oom_score>\d+), '
            r"oom_score_adj -?\d+, VmRSS (?P<rss_mib>\d+) MiB"
        ),
    ),
    (
        "kernel-oom",
        re.compile(
            r"Killed process (?P<pid>\d+) \((?P<comm>[^)]+)\).*?"
            r"anon-rss:(?P<anon_rss_kb>\d+)kB"
        ),
    ),
    (
        "memcg-oom",
        re.compile(
            r"oom-kill:constraint=(?P<constraint>\S+).*?"
            r"task_memcg=(?P<memcg>\S+).*?task=(?P<comm>\S+),pid=(?P<pid>\d+)"
        ),
    ),
    (
        "systemd-oomd",
        re.compile(
            r"^Killed (?P<cgroup>\S+)(?: with pid (?P<pid>\d+) \((?P<comm>[^)]+)\))? due to"
        ),
    ),
)
# First run (no stored cursor) backfills from here: journald is
# Storage=persistent SystemMaxUse=32G and this predates the earliest incident
# this issue was written to investigate. Only used once — every subsequent
# run resumes from the persisted cursor regardless of this constant.
KILL_EVENT_BACKFILL_SINCE = "2026-06-17"
KILL_EVENT_SOURCE = "machine.kill_event"


def classify_kill_line(message: str) -> tuple[str, dict[str, object]] | None:
    for killer, pattern in KILL_EVENT_PATTERNS:
        match = pattern.search(message)
        if match:
            return killer, match.groupdict()
    return None


def load_kill_event_cursor(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT payload_json FROM source_status WHERE source = ?",
        (KILL_EVENT_SOURCE,),
    ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row[0]).get("cursor")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def save_kill_event_cursor(conn: sqlite3.Connection, cursor: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO source_status (source, checked_at, status, reason, payload_json) VALUES (?, ?, ?, ?, ?)",
        (KILL_EVENT_SOURCE, now_iso(), "ok", None, json.dumps({"cursor": cursor})),
    )


def scan_kill_events(
    host: str, boot_id: str | None, after_cursor: str | None
) -> tuple[list[dict[str, object]], str | None]:
    cmd = ["journalctl", "-o", "json", "--no-pager", "-g", KILL_EVENT_GREP]
    if after_cursor:
        cmd += ["--after-cursor", after_cursor]
    else:
        cmd += ["--since", KILL_EVENT_BACKFILL_SINCE]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return [], None
    rows: list[dict[str, object]] = []
    new_cursor = after_cursor
    for line in proc.stdout.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        cursor = entry.get("__CURSOR")
        if cursor:
            new_cursor = cursor
        message = entry.get("MESSAGE")
        if not isinstance(message, str):
            continue
        classified = classify_kill_line(message)
        if classified is None:
            continue
        killer, fields = classified
        rows.append(
            {
                "observed_at": now_iso(),
                "host": host,
                "boot_id": boot_id,
                "schema_version": SCHEMA_VERSION,
                "killer": killer,
                "victim_comm": fields.get("comm"),
                "victim_pid": int_or_none(fields.get("pid")),
                "victim_rss_mib": int_or_none(fields.get("rss_mib"))
                or (
                    int(anon_rss_kb) // 1024
                    if (anon_rss_kb := fields.get("anon_rss_kb")) is not None
                    else None
                ),
                "cgroup_path": fields.get("memcg") or fields.get("cgroup"),
                "oom_score": int_or_none(fields.get("oom_score")),
                "raw_line": message,
                "journal_cursor": cursor,
            }
        )
    return rows, new_cursor


def insert_kill_events(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO kill_event (
          observed_at, host, boot_id, schema_version, killer, victim_comm,
          victim_pid, victim_rss_mib, cgroup_path, oom_score, raw_line,
          journal_cursor
        ) VALUES (
          :observed_at, :host, :boot_id, :schema_version, :killer, :victim_comm,
          :victim_pid, :victim_rss_mib, :cgroup_path, :oom_score, :raw_line,
          :journal_cursor
        )
        """,
        rows,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--service-interval", type=float, default=60.0)
    parser.add_argument("--network-interval", type=float, default=300.0)
    parser.add_argument("--gpu-interval", type=float, default=1.0)
    parser.add_argument("--network-interface", default="enp4s0")
    parser.add_argument("--network-gateway", default="192.168.1.1")
    parser.add_argument("--bufferbloat-interval", type=float, default=1800.0)
    parser.add_argument("--network-probe-once", action="store_true")
    parser.add_argument("--process-io-top", type=int, default=40)
    parser.add_argument("--process-memory-top", type=int, default=50)
    parser.add_argument("--process-memory-interval", type=float, default=60.0)
    parser.add_argument("--kill-event-interval", type=float, default=30.0)
    parser.add_argument("--cgroups", default="")
    parser.add_argument("--units", default="")
    parser.add_argument("--user-name", required=True)
    args = parser.parse_args()

    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    coretemp = find_hwmon("coretemp")
    gwmi = find_hwmon("gigabyte_wmi")
    spd1 = find_hwmon("spd5118", 1)
    spd2 = find_hwmon("spd5118", 2)
    nvme1 = find_hwmon("nvme", 1)
    nvme2 = find_hwmon("nvme", 2)
    rapl_zones = discover_rapl()
    boot_id = read_text("/proc/sys/kernel/random/boot_id")
    units = [unit for unit in args.units.split(",") if unit]
    cgroup_specs = [
        spec
        for raw in args.cgroups.split(",")
        if raw
        for spec in [parse_cgroup_spec(raw)]
        if spec is not None
    ]

    nvml_init()

    state = hardware_state(args.host, rapl_zones)
    state["hwmon"] = {
        "coretemp": str(coretemp) if coretemp else None,
        "gigabyte_wmi": str(gwmi) if gwmi else None,
        "spd5118": [str(path) for path in (spd1, spd2) if path],
        "nvme": [str(path) for path in (nvme1, nvme2) if path],
        "fan_rpm": None,
        "fan_rpm_gap": "hwmon.fan_input_unavailable",
    }
    manifest.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    with sqlite3.connect(db) as conn:
        init_db(conn)
        if args.network_probe_once:
            inserted = insert_network_sample(
                conn,
                network_probe(
                    args.host,
                    read_text("/proc/sys/kernel/random/boot_id"),
                    args.network_interface,
                    args.network_gateway,
                    do_bloat=True,
                ),
            )
            conn.execute(
                "INSERT OR REPLACE INTO source_status (source, checked_at, status, reason, payload_json) VALUES (?, ?, ?, ?, ?)",
                (
                    "machine.network",
                    now_iso(),
                    "ok",
                    None,
                    json.dumps({"inserted": inserted}),
                ),
            )
            conn.commit()
            return 0

        conn.execute(
            "INSERT INTO hardware_state (captured_at, host, boot_id, schema_version, payload_json) VALUES (?, ?, ?, ?, ?)",
            (
                now_iso(),
                args.host,
                boot_id,
                SCHEMA_VERSION,
                json.dumps(state, sort_keys=True),
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO source_status (source, checked_at, status, reason, payload_json) VALUES (?, ?, ?, ?, ?)",
            (
                "machine-telemetry",
                now_iso(),
                "ok",
                None,
                json.dumps({"schema_version": SCHEMA_VERSION}),
            ),
        )
        conn.commit()

        prev_energy = read_rapl_energy(rapl_zones)
        prev_time = time.monotonic()
        next_service = 0.0
        next_network = 0.0
        next_process_memory = 0.0
        next_kill_event = 0.0
        next_wal_checkpoint = time.monotonic() + WAL_CHECKPOINT_INTERVAL_S
        kill_event_cursor = load_kill_event_cursor(conn)
        last_bloat = 0.0

        # Probe fan-tacho capability once at startup. Many motherboards
        # (e.g. Gigabyte boards with no IT87/NCT677x driver match) never
        # expose fan*_input under /sys/class/hwmon — that is a
        # capability fact for the hardware, not a per-sample regression.
        # Emitting fan.hwmon_unavailable on every sample turned the
        # gap into 35% of the substrate's regression signal (per the
        # 2026-05-18 gap-summary first-run). Probe once: if fans were
        # never there, the manifest already records the capability gap;
        # only emit the per-sample code if fans were present at startup
        # and then disappeared (driver reload / hardware fault).
        had_fans_at_startup = any(Path("/sys/class/hwmon").glob("hwmon*/fan*_input"))

        # High-frequency GPU sampler — runs whenever the interval is positive
        # (set to 0 to disable) and pynvml is present. It starts even if the
        # initial nvml_init() failed transiently: gpu_metrics() → nvml_ensure()
        # retries with a backoff, so a bad-boot NVML state self-heals instead of
        # permanently disabling GPU capture until the next restart.
        gpu_stop = threading.Event()
        gpu_thread: threading.Thread | None = None
        if not _nvml_unavailable and args.gpu_interval > 0:
            gpu_thread = threading.Thread(
                target=gpu_sampler_thread,
                args=(str(db), args.host, boot_id, args.gpu_interval, gpu_stop),
                name="gpu-sampler",
                daemon=True,
            )
            gpu_thread.start()

        prev_process_io = process_io_snapshot()

        while True:
            target = time.monotonic() + args.interval
            time.sleep(args.interval)
            sample_start = time.monotonic()
            elapsed = sample_start - prev_time
            oversleep_ms = max((sample_start - target) * 1000.0, 0.0)

            gaps = []
            energy = read_rapl_energy(rapl_zones)
            watts = rapl_watts(rapl_zones, prev_energy, energy, elapsed)
            prev_energy = energy
            prev_time = sample_start
            if not rapl_zones:
                gaps.append("rapl.no_zones")
            elif not watts:
                gaps.append("rapl.no_watts")

            gpu, gpu_gaps = gpu_metrics()
            gaps.extend(gpu_gaps)
            # Only flag missing fan tachos if they were present at startup
            # and then went away — otherwise this is hardware capability,
            # not a regression. See the had_fans_at_startup comment above.
            if had_fans_at_startup and not any(
                Path("/sys/class/hwmon").glob("hwmon*/fan*_input")
            ):
                gaps.append("fan.hwmon_unavailable")

            psi_cpu = parse_psi("/proc/pressure/cpu")
            psi_io = parse_psi("/proc/pressure/io")
            psi_mem = parse_psi("/proc/pressure/memory")
            dstate_count, dstate_waits = dstate_tasks()
            mem = memory_metrics()
            vmstat = vmstat_metrics()
            swap_tiers = swap_tier_metrics()
            load_parts = read_text("/proc/loadavg")
            load_1 = load_5 = None
            if load_parts:
                parts = load_parts.split()
                load_1 = float_or_none(parts[0])
                load_5 = float_or_none(parts[1]) if len(parts) > 1 else None

            mb_temps = []
            if gwmi:
                for path in sorted(gwmi.glob("temp*_input")):
                    value = sysfs_temp_c(path)
                    if value is not None:
                        mb_temps.append(value)

            current_process_io = process_io_snapshot()
            collector_duration_ms = (time.monotonic() - sample_start) * 1000.0
            observed_at = now_iso()
            process_io_rows = process_io_delta_rows(
                observed_at,
                args.host,
                boot_id,
                prev_process_io,
                current_process_io,
                interval_s=elapsed,
                limit=max(args.process_io_top, 0),
            )
            prev_process_io = current_process_io
            row = {
                "observed_at": observed_at,
                "host": args.host,
                "boot_id": boot_id,
                "schema_version": SCHEMA_VERSION,
                "interval_s": elapsed,
                "latency_oversleep_ms": round(oversleep_ms, 3),
                "collector_duration_ms": round(collector_duration_ms, 3),
                "cpu_package_w": watts.get("package-0"),
                "cpu_core_w": watts.get("core"),
                "cpu_pkg_c": sysfs_temp_c(coretemp / "temp1_input")
                if coretemp
                else None,
                "cpu_max_core_c": max_coretemp(coretemp),
                "ddr5_1_c": sysfs_temp_c(spd1 / "temp1_input") if spd1 else None,
                "ddr5_2_c": sysfs_temp_c(spd2 / "temp1_input") if spd2 else None,
                "nvme_1_c": sysfs_temp_c(nvme1 / "temp1_input") if nvme1 else None,
                "nvme_2_c": sysfs_temp_c(nvme2 / "temp1_input") if nvme2 else None,
                "motherboard_temps_json": json.dumps(mb_temps),
                "gpu_temp_c": gpu.get("gpu_temp_c"),
                "gpu_power_w": gpu.get("gpu_power_w"),
                "gpu_power_limit_w": gpu.get("gpu_power_limit_w"),
                "gpu_fan_pct": gpu.get("gpu_fan_pct"),
                "gpu_util_pct": gpu.get("gpu_util_pct"),
                "gpu_mem_util_pct": gpu.get("gpu_mem_util_pct"),
                "gpu_clock_mhz": gpu.get("gpu_clock_mhz"),
                "gpu_mem_clock_mhz": gpu.get("gpu_mem_clock_mhz"),
                "gpu_pstate": gpu.get("gpu_pstate"),
                "gpu_pcie_gen": gpu.get("gpu_pcie_gen"),
                "gpu_pcie_width": gpu.get("gpu_pcie_width"),
                "load_1m": load_1,
                "load_5m": load_5,
                "mem_total_mb": mem["mem_total_mb"],
                "mem_used_mb": mem["mem_used_mb"],
                "mem_avail_mb": mem["mem_avail_mb"],
                "mem_anon_mb": mem["mem_anon_mb"],
                "mem_file_cache_mb": mem["mem_file_cache_mb"],
                "mem_slab_reclaimable_mb": mem["mem_slab_reclaimable_mb"],
                "mem_slab_unreclaimable_mb": mem["mem_slab_unreclaimable_mb"],
                "mem_dirty_mb": mem["mem_dirty_mb"],
                "mem_writeback_mb": mem["mem_writeback_mb"],
                "mem_shmem_mb": mem["mem_shmem_mb"],
                "swap_used_mb": mem["swap_used_mb"],
                "cpu_psi_some_avg10": psi_cpu.get("some_avg10"),
                "cpu_psi_some_avg60": psi_cpu.get("some_avg60"),
                "cpu_psi_some_avg300": psi_cpu.get("some_avg300"),
                "cpu_psi_some_total_us": psi_cpu.get("some_total"),
                "io_psi_some_avg10": psi_io.get("some_avg10"),
                "io_psi_some_avg60": psi_io.get("some_avg60"),
                "io_psi_some_avg300": psi_io.get("some_avg300"),
                "io_psi_some_total_us": psi_io.get("some_total"),
                "io_psi_full_avg10": psi_io.get("full_avg10"),
                "io_psi_full_avg60": psi_io.get("full_avg60"),
                "io_psi_full_avg300": psi_io.get("full_avg300"),
                "io_psi_full_total_us": psi_io.get("full_total"),
                "memory_psi_some_avg10": psi_mem.get("some_avg10"),
                "memory_psi_some_avg60": psi_mem.get("some_avg60"),
                "memory_psi_some_avg300": psi_mem.get("some_avg300"),
                "memory_psi_some_total_us": psi_mem.get("some_total"),
                "memory_psi_full_avg10": psi_mem.get("full_avg10"),
                "memory_psi_full_avg60": psi_mem.get("full_avg60"),
                "memory_psi_full_avg300": psi_mem.get("full_avg300"),
                "memory_psi_full_total_us": psi_mem.get("full_total"),
                "dstate_task_count": dstate_count,
                "dstate_wchan_summary": dstate_waits,
                "gap_codes_json": json.dumps(sorted(set(gaps))),
                **vmstat,
                **swap_tiers,
            }
            conn.execute(
                """
                INSERT INTO metric_sample (
                  observed_at, host, boot_id, schema_version, interval_s,
                  latency_oversleep_ms, collector_duration_ms,
                  cpu_package_w, cpu_core_w, cpu_pkg_c, cpu_max_core_c,
                  ddr5_1_c, ddr5_2_c, nvme_1_c, nvme_2_c,
                  motherboard_temps_json, gpu_temp_c, gpu_power_w,
                  gpu_power_limit_w, gpu_fan_pct, gpu_util_pct,
                  gpu_mem_util_pct, gpu_clock_mhz, gpu_mem_clock_mhz,
                  gpu_pstate, gpu_pcie_gen, gpu_pcie_width, load_1m,
                  load_5m, mem_total_mb, mem_used_mb, mem_avail_mb,
                  mem_anon_mb, mem_file_cache_mb, mem_slab_reclaimable_mb,
                  mem_slab_unreclaimable_mb, mem_dirty_mb, mem_writeback_mb,
                  mem_shmem_mb, swap_used_mb,
                  cpu_psi_some_avg10, cpu_psi_some_avg60,
                  cpu_psi_some_avg300, cpu_psi_some_total_us,
                  io_psi_some_avg10, io_psi_some_avg60,
                  io_psi_some_avg300, io_psi_some_total_us,
                  io_psi_full_avg10, io_psi_full_avg60,
                  io_psi_full_avg300, io_psi_full_total_us,
                  memory_psi_some_avg10, memory_psi_some_avg60,
                  memory_psi_some_avg300, memory_psi_some_total_us,
                  memory_psi_full_avg10, memory_psi_full_avg60,
                  memory_psi_full_avg300, memory_psi_full_total_us,
                  dstate_task_count,
                  dstate_wchan_summary, gap_codes_json,
                  vmstat_workingset_refault_file, vmstat_workingset_refault_anon,
                  vmstat_workingset_activate_file, vmstat_workingset_activate_anon,
                  vmstat_pgscan_kswapd, vmstat_pgscan_direct,
                  vmstat_pgsteal_kswapd, vmstat_pgsteal_direct,
                  vmstat_pswpin, vmstat_pswpout,
                  vmstat_allocstall_normal, vmstat_allocstall_movable,
                  vmstat_oom_kill,
                  zram_orig_mb, zram_compr_mb, zram_mem_used_mb, swaps_json
                ) VALUES (
                  :observed_at, :host, :boot_id, :schema_version, :interval_s,
                  :latency_oversleep_ms, :collector_duration_ms,
                  :cpu_package_w, :cpu_core_w, :cpu_pkg_c, :cpu_max_core_c,
                  :ddr5_1_c, :ddr5_2_c, :nvme_1_c, :nvme_2_c,
                  :motherboard_temps_json, :gpu_temp_c, :gpu_power_w,
                  :gpu_power_limit_w, :gpu_fan_pct, :gpu_util_pct,
                  :gpu_mem_util_pct, :gpu_clock_mhz, :gpu_mem_clock_mhz,
                  :gpu_pstate, :gpu_pcie_gen, :gpu_pcie_width, :load_1m,
                  :load_5m, :mem_total_mb, :mem_used_mb, :mem_avail_mb,
                  :mem_anon_mb, :mem_file_cache_mb, :mem_slab_reclaimable_mb,
                  :mem_slab_unreclaimable_mb, :mem_dirty_mb, :mem_writeback_mb,
                  :mem_shmem_mb, :swap_used_mb,
                  :cpu_psi_some_avg10, :cpu_psi_some_avg60,
                  :cpu_psi_some_avg300, :cpu_psi_some_total_us,
                  :io_psi_some_avg10, :io_psi_some_avg60,
                  :io_psi_some_avg300, :io_psi_some_total_us,
                  :io_psi_full_avg10, :io_psi_full_avg60,
                  :io_psi_full_avg300, :io_psi_full_total_us,
                  :memory_psi_some_avg10, :memory_psi_some_avg60,
                  :memory_psi_some_avg300, :memory_psi_some_total_us,
                  :memory_psi_full_avg10, :memory_psi_full_avg60,
                  :memory_psi_full_avg300, :memory_psi_full_total_us,
                  :dstate_task_count,
                  :dstate_wchan_summary, :gap_codes_json,
                  :vmstat_workingset_refault_file, :vmstat_workingset_refault_anon,
                  :vmstat_workingset_activate_file, :vmstat_workingset_activate_anon,
                  :vmstat_pgscan_kswapd, :vmstat_pgscan_direct,
                  :vmstat_pgsteal_kswapd, :vmstat_pgsteal_direct,
                  :vmstat_pswpin, :vmstat_pswpout,
                  :vmstat_allocstall_normal, :vmstat_allocstall_movable,
                  :vmstat_oom_kill,
                  :zram_orig_mb, :zram_compr_mb, :zram_mem_used_mb, :swaps_json
                )
                """,
                row,
            )
            insert_block_device_stats(conn, observed_at, args.host, boot_id)
            insert_process_io_deltas(conn, process_io_rows)
            if args.process_memory_interval > 0 and sample_start >= next_process_memory:
                insert_process_memory_rows(
                    conn,
                    process_memory_rows(
                        observed_at,
                        args.host,
                        boot_id,
                        limit=max(args.process_memory_top, 0),
                    ),
                )
                next_process_memory = sample_start + args.process_memory_interval
            if sample_start >= next_service:
                insert_service_states(conn, args.host, boot_id, units, args.user_name)
                insert_cgroup_memory_stats(
                    conn,
                    cgroup_memory_samples(
                        observed_at, args.host, boot_id, cgroup_specs
                    ),
                )
                next_service = sample_start + args.service_interval
            if args.network_interval > 0 and sample_start >= next_network:
                do_bloat = (
                    args.bufferbloat_interval > 0
                    and sample_start - last_bloat >= args.bufferbloat_interval
                )
                insert_network_sample(
                    conn,
                    network_probe(
                        args.host,
                        boot_id,
                        args.network_interface,
                        args.network_gateway,
                        do_bloat=do_bloat,
                    ),
                )
                if do_bloat:
                    last_bloat = sample_start
                next_network = sample_start + args.network_interval
            if args.kill_event_interval > 0 and sample_start >= next_kill_event:
                kill_rows, new_cursor = scan_kill_events(
                    args.host, boot_id, kill_event_cursor
                )
                insert_kill_events(conn, kill_rows)
                if new_cursor and new_cursor != kill_event_cursor:
                    kill_event_cursor = new_cursor
                    save_kill_event_cursor(conn, new_cursor)
                next_kill_event = sample_start + args.kill_event_interval
            conn.commit()
            # SQLite's PASSIVE autocheckpoints never shrink the WAL file, and
            # they silently make no progress while any reader (lynchpin
            # analysis queries over this DB) holds an older snapshot. Left
            # alone, one long-reader episode grew the WAL to 1.3 GiB and it
            # stayed there indefinitely (2026-07-10, sinnix-bdi). TRUNCATE
            # both drains and shrinks it; with the 5s busy handler a blocked
            # attempt degrades to a logged retry on the next interval instead
            # of stalling sampling.
            if sample_start >= next_wal_checkpoint:
                next_wal_checkpoint = sample_start + WAL_CHECKPOINT_INTERVAL_S
                try:
                    ck = conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
                    if ck and ck[0]:
                        print(
                            "wal-checkpoint: blocked by concurrent reader "
                            f"(log_frames={ck[1]} checkpointed={ck[2]}); retrying next interval",
                            flush=True,
                        )
                except sqlite3.Error as exc:
                    print(f"wal-checkpoint: failed: {exc!r}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
