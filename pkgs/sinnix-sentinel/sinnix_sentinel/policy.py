"""Health-policy check implementations (translation of the bash main body).

Each check function takes the loaded JSON policy plus a :class:`CheckSet`
and a :class:`NotificationQueue`, and records results. Restart/GC actions
go through :mod:`systemd` and obey ``observe_only``.

The bash sentinel mixes ``record_check`` (always-on) with ``queue_action_event``
(only when ``CORRECTIVE_ACTIONS=true``). We keep that split: corrective
behaviour is gated on ``corrective`` AND ``not observe_only``.

Line-range citations below point at scripts/sinnix-sentinel for review.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import systemd
from .baseline import baseline_append, read_baselines
from .events import CheckSet
from .notify import NotificationQueue


# ── tiny helpers ──────────────────────────────────────────────────────────
def _run(cmd: List[str], *, sudo: bool = False) -> subprocess.CompletedProcess:
    if sudo and os.geteuid() != 0 and shutil.which("sudo"):
        cmd = ["sudo", "-n", *cmd]
    return subprocess.run(cmd, check=False, text=True, capture_output=True)


def _stat_median_stdev(values: List[float]) -> tuple[float, float, int]:
    if not values:
        return 0.0, 0.0, 0
    n = len(values)
    median = statistics.median(values)
    stdev = statistics.stdev(values) if n > 1 else 0.0
    return median, stdev, n


def _floats(samples: List[str]) -> List[float]:
    out: List[float] = []
    for s in samples:
        try:
            out.append(float(s))
        except ValueError:
            continue
    return out


# ── 1. Hardware ───────────────────────────────────────────────────────────
def check_hardware(checks: CheckSet, notifs: NotificationQueue) -> None:
    """SMART status (bash lines 235-255)."""

    if not shutil.which("smartctl"):
        return
    proc = _run(["smartctl", "-H", "/dev/nvme0n1"], sudo=True)
    text = (proc.stdout or "") + (proc.stderr or "")
    if re.search(r"test result: (PASSED|OK)", text, re.IGNORECASE):
        checks.record("hardware", "smart", "ok", "NVMe health passed")
    elif re.search(
        r"permission denied|a password is required|sudo:|not permitted",
        text,
        re.IGNORECASE,
    ):
        checks.record(
            "hardware",
            "smart",
            "warn",
            "NVMe SMART check skipped (insufficient permissions)",
        )
    else:
        checks.record("hardware", "smart", "fail", "NVMe health CRITICAL or UNKNOWN")
        notifs.push("critical", "sentinel: NVMe SMART health check FAILED")


# ── 2. Reboot ─────────────────────────────────────────────────────────────
def _readlink(p: str) -> str:
    try:
        return os.readlink(p)
    except OSError:
        return "unknown"


def check_reboot(
    checks: CheckSet, notifs: NotificationQueue, *, observe_only: bool
) -> None:
    """Kernel + nvidia driver reboot detection (bash lines 257-302)."""

    reboot_needed = False
    reason_parts: List[str] = []

    booted = _readlink("/run/booted-system/kernel")
    current = _readlink("/run/current-system/kernel")
    current_sys = _readlink("/run/current-system")

    if booted != "unknown" and current != "unknown" and booted != current:
        reboot_needed = True
        reason_parts.append("kernel updated")

    if os.path.exists("/proc/driver/nvidia/version"):
        loaded_nv = ""
        try:
            with open("/proc/driver/nvidia/version", "r", encoding="utf-8") as fh:
                for line in fh:
                    if "NVRM version:" in line:
                        toks = line.split()
                        for i, t in enumerate(toks):
                            if t == "Module" and i + 1 < len(toks):
                                loaded_nv = toks[i + 1]
                                break
                        break
        except OSError:
            pass

        current_nv = ""
        if shutil.which("nvidia-smi"):
            p = _run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]
            )
            current_nv = (p.stdout or "").splitlines()[0].strip() if p.stdout else ""

        if loaded_nv and not current_nv:
            reboot_needed = True
            reason_parts.append("nvidia driver check failed")
        elif loaded_nv and current_nv and loaded_nv != current_nv:
            reboot_needed = True
            reason_parts.append(f"nvidia {loaded_nv} -> {current_nv}")

    reboot_state_file = Path(
        os.environ.get(
            "SINNIX_REBOOT_STATE_FILE",
            "/var/lib/sinnix-sentinel/reboot-last-notified-system",
        )
    )

    if reboot_needed:
        reason = "; ".join(reason_parts)
        checks.record("reboot", "required", "warn", reason)
        try:
            last_notified = reboot_state_file.read_text(encoding="utf-8").strip()
        except OSError:
            last_notified = ""
        if current_sys != "unknown" and current_sys != last_notified:
            notifs.push("critical", f"sentinel: reboot required ({reason})")
            if not observe_only:
                try:
                    reboot_state_file.parent.mkdir(parents=True, exist_ok=True)
                    reboot_state_file.write_text(current_sys + "\n", encoding="utf-8")
                except OSError:
                    pass
    else:
        checks.record("reboot", "required", "ok", "no reboot needed")
        if not observe_only:
            try:
                reboot_state_file.unlink()
            except OSError:
                pass


# ── 3. Services ───────────────────────────────────────────────────────────
def check_services(
    policy: Dict[str, Any],
    checks: CheckSet,
    notifs: NotificationQueue,
    *,
    corrective: bool,
    observe_only: bool,
) -> None:
    """Service / timer status (bash lines 304-335)."""

    for svc in policy.get("services", []) or []:
        name = svc.get("name", "")
        unit = svc.get("unit", "")
        unit_type = svc.get("type", "service")
        restartable = svc.get("restartable", False)

        scope = systemd.pick_unit_scope(unit_type, unit)

        if unit_type == "timer":
            if systemd.is_enabled(scope, unit):
                nxt = systemd.show_property(scope, unit, "NextElapseUSecRealtime")
                detail = "timer enabled"
                if nxt:
                    detail += f" (next: {nxt})"
                checks.record("services", name, "ok", detail)
            else:
                checks.record("services", name, "fail", "timer not enabled")
            continue

        active = systemd.show_property(scope, unit, "ActiveState") or "unknown"
        if active == "active":
            mem_raw = systemd.show_property(scope, unit, "MemoryCurrent") or "0"
            try:
                mem_mb = int(mem_raw) // 1048576
            except ValueError:
                mem_mb = 0
            checks.record(
                "services", name, "ok", f"active ({mem_mb}MB)" if mem_mb else "active"
            )
        else:
            checks.record("services", name, "fail", active)
            if corrective and restartable:
                ok, _intent = systemd.restart_unit(
                    scope, unit, observe_only=observe_only
                )
                if ok:
                    notifs.push("normal", f"sentinel: restarted {name}")
                # action-event recording is handled by the caller via notif queue;
                # the bash sentinel writes a queued action event — see cli.py
                # which inspects observe_only and re-synthesises the action JSON.


# ── 4. MCP fanout ────────────────────────────────────────────────────────
_AGENT_PATTERNS = [
    ("codex", re.compile(r"\bcodex\b", re.IGNORECASE)),
    ("claude", re.compile(r"\bclaude(?:-code)?\b", re.IGNORECASE)),
    ("gemini", re.compile(r"\bgemini\b", re.IGNORECASE)),
    ("opencode", re.compile(r"\bopencode\b", re.IGNORECASE)),
    ("cursor", re.compile(r"\bcursor\b", re.IGNORECASE)),
    ("aider", re.compile(r"\baider\b", re.IGNORECASE)),
    ("qwen", re.compile(r"\bqwen\b", re.IGNORECASE)),
    ("goose", re.compile(r"\bgoose\b", re.IGNORECASE)),
    ("jules", re.compile(r"\bjules\b", re.IGNORECASE)),
]


def _infer_mcp_type(cmd: str) -> Optional[str]:
    lower = cmd.lower()
    if "context7" in lower:
        return "context7"
    if "firecrawl" in lower:
        return "firecrawl"
    if "playwright" in lower and "mcp" in lower:
        return "playwright"
    m = re.search(r"@modelcontextprotocol/server-([a-z0-9._-]+)", lower)
    if m:
        return m.group(1)
    m = re.search(r"\bmcp-([a-z0-9._-]+)\b", lower)
    if m:
        return m.group(1)
    return None


def _mcp_telemetry(threshold: int) -> Dict[str, Any]:
    """Direct Python port of the embedded heredoc (bash lines 340-446)."""

    proc = _run(["ps", "-eo", "pid=,ppid=,args=", "--no-headers"])
    pid_map: Dict[int, tuple[int, str]] = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid_map[int(parts[0])] = (int(parts[1]), parts[2])
        except ValueError:
            continue

    def infer_agent(start_ppid: int) -> tuple[str, str]:
        seen: set[int] = set()
        current = start_ppid
        while current and current not in seen:
            seen.add(current)
            if current not in pid_map:
                break
            parent_ppid, parent_args = pid_map[current]
            for label, rx in _AGENT_PATTERNS:
                if rx.search(parent_args):
                    return f"{label}:{current}", parent_args
            current = parent_ppid
        parent_args = pid_map.get(start_ppid, (0, "unknown-parent"))[1]
        return f"unclassified:{start_ppid}", parent_args

    pair_counts: Dict[tuple[str, str], Dict[str, Any]] = {}
    total = 0
    for _pid, (ppid, args) in pid_map.items():
        mcp_type = _infer_mcp_type(args)
        if not mcp_type:
            continue
        total += 1
        agent_key, agent_cmd = infer_agent(ppid)
        key = (agent_key, mcp_type)
        if key not in pair_counts:
            pair_counts[key] = {
                "agent": agent_key,
                "mcp_type": mcp_type,
                "count": 0,
                "agent_cmd": agent_cmd,
                "sample_mcp_cmd": args,
            }
        pair_counts[key]["count"] += 1

    pairs = sorted(
        pair_counts.values(),
        key=lambda x: (-x["count"], x["agent"], x["mcp_type"]),
    )
    violations = [p for p in pairs if p["count"] > threshold]
    return {
        "total": total,
        "pair_count": len(pairs),
        "agent_count": len({p["agent"] for p in pairs}),
        "pairs": pairs,
        "violations": violations,
    }


def check_mcp(checks: CheckSet, notifs: NotificationQueue, *, threshold: int) -> None:
    """MCP child fanout (bash lines 337-470)."""

    tel = _mcp_telemetry(threshold)
    total = tel["total"]
    pair_count = tel["pair_count"]
    agent_count = tel["agent_count"]
    pairs = tel["pairs"]
    violations = tel["violations"]

    checks.record(
        "mcp",
        "processes_total",
        "ok",
        f"{total} MCP process(es) across {agent_count} coding-agent instance(s) "
        f"and {pair_count} instance/type pair(s)",
    )

    if violations:
        detail = " | ".join(
            f"{p['agent']} {p['mcp_type']}={p['count']}x" for p in violations[:6]
        )
        checks.record(
            "mcp",
            "per_type_per_agent_fanout",
            "fail",
            f"{len(violations)} agent/type pair(s) exceed threshold={threshold}; {detail}",
        )
        notifs.push(
            "critical",
            f"sentinel: MCP per-type fanout exceeded (threshold={threshold})",
        )
    else:
        hot = " | ".join(
            f"{p['agent']} {p['mcp_type']}={p['count']}x" for p in pairs[:6]
        )
        checks.record(
            "mcp",
            "per_type_per_agent_fanout",
            "ok",
            f"all agent/type pairs <= {threshold}; {hot}",
        )


# ── 5. Captures ───────────────────────────────────────────────────────────
def check_captures(policy: Dict[str, Any], checks: CheckSet, now_epoch: int) -> None:
    """Capture freshness (bash lines 472-492)."""

    for cap in policy.get("captures", []) or []:
        name = cap.get("name", "")
        path = cap.get("path", "")
        max_h = float(cap.get("maxStaleHours", 0) or 0)
        if not path or not os.path.isdir(path):
            checks.record("captures", name, "warn", f"missing: {path}")
            continue

        newest_ts = 0.0
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    mt = os.stat(os.path.join(root, f)).st_mtime
                    if mt > newest_ts:
                        newest_ts = mt
                except OSError:
                    continue

        if newest_ts == 0.0:
            checks.record("captures", name, "warn", "empty")
            continue

        age_s = now_epoch - newest_ts
        age_h = age_s / 3600
        status = "ok"
        if age_s > max_h * 3600:
            status = "warn"
        if age_s > max_h * 3600 * 4:
            status = "fail"
        checks.record("captures", name, status, f"{age_h:.1f}h fresh")


# ── 6. Storage ────────────────────────────────────────────────────────────
def _df_pct(path: str) -> int:
    p = _run(["df", path, "--output=pcent"])
    try:
        return int(re.sub(r"[^0-9]", "", p.stdout.splitlines()[-1]) or "0")
    except (IndexError, ValueError):
        return 0


def _df_avail_h(path: str) -> str:
    p = _run(["df", "-h", path, "--output=avail"])
    try:
        return p.stdout.splitlines()[-1].strip()
    except IndexError:
        return ""


def check_storage(policy: Dict[str, Any], checks: CheckSet) -> None:
    """Mount usage (bash lines 494-507)."""

    for m in policy.get("mounts", []) or []:
        path = m.get("path", "")
        warn_pct = int(m.get("warnPct", 0))
        fail_pct = int(m.get("failPct", 0))
        if not os.path.ismount(path):
            checks.record("mounts", path, "fail", "NOT MOUNTED")
            continue
        used = _df_pct(path)
        avail = _df_avail_h(path)
        status = "ok"
        if used >= warn_pct:
            status = "warn"
        if used >= fail_pct:
            status = "fail"
        checks.record("mounts", path, status, f"{used}% used ({avail} free)")


# ── 7. Backups ────────────────────────────────────────────────────────────
_TS_RE = re.compile(r"(\d{8}T\d{6}[+-]\d{4})")


def check_backups(policy: Dict[str, Any], checks: CheckSet, now_epoch: int) -> None:
    """Snapshot + borg backup freshness (bash lines 509-575)."""

    backups = policy.get("backups", {}) or {}
    snapshot_dirs: List[str] = backups.get("snapshotDirs", []) or []
    max_stale = float(backups.get("maxStaleHours", 2) or 2)
    target_repos: List[str] = backups.get("backupTargets") or (
        [backups["backupTarget"]] if backups.get("backupTarget") else []
    )

    for d in snapshot_dirs:
        if not os.path.isdir(d):
            checks.record("backups", d, "warn", "missing")
            continue
        listing = _run(["sudo", "ls", "-A", d])
        names = [
            n for n in (listing.stdout or "").split() if n and not n.startswith(".")
        ]
        if not names:
            checks.record("backups", d, "warn", "no snapshots")
            continue
        newest_name = sorted(names)[-1]
        m = _TS_RE.search(newest_name)
        if m:
            ts_str = m.group(1)
            formatted = (
                f"{ts_str[0:4]}-{ts_str[4:6]}-{ts_str[6:8]} "
                f"{ts_str[9:11]}:{ts_str[11:13]}:{ts_str[13:15]} {ts_str[15:20]}"
            )
            p = _run(["date", "-d", formatted, "+%s"])
            try:
                newest_ts = int((p.stdout or "0").strip() or 0)
            except ValueError:
                newest_ts = 0
        else:
            p = _run(["sudo", "stat", "-c", "%Y", os.path.join(d, newest_name)])
            try:
                newest_ts = int((p.stdout or "0").strip() or 0)
            except ValueError:
                newest_ts = 0

        age_h = (now_epoch - newest_ts) / 3600
        status = "ok"
        if age_h > max_stale:
            status = "warn"
        if age_h > max_stale * 12:
            status = "fail"
        checks.record("backups", d, status, f"latest={newest_name} ({age_h:.1f}h ago)")

    for target_repo in target_repos:
        if not target_repo:
            continue
        repo_name = os.path.basename(target_repo) or "borg"
        exists = _run(["sudo", "test", "-d", target_repo]).returncode == 0
        if not exists:
            checks.record(
                "backups", repo_name, "fail", f"target missing: {target_repo}"
            )
            continue
        cfg_exists = (
            _run(["sudo", "test", "-f", f"{target_repo}/config"]).returncode == 0
        )
        if not cfg_exists:
            checks.record("backups", repo_name, "warn", "not a borg repo")
            continue
        if not shutil.which("borg"):
            checks.record("backups", repo_name, "warn", "borg missing")
            continue
        lock_file = _run(["sudo", "test", "-f", f"{target_repo}/lock"]).returncode == 0
        lock_dir = (
            _run(["sudo", "test", "-d", f"{target_repo}/lock.exclusive"]).returncode
            == 0
        )
        if lock_file or lock_dir:
            checks.record(
                "backups",
                repo_name,
                "ok",
                "repository active (currently backing up)",
            )
            continue
        listing = _run(["sudo", "borg", "list", "--json", "--last", "1", target_repo])
        try:
            data = json.loads(listing.stdout or '{"archives":[]}')
        except json.JSONDecodeError:
            data = {"archives": []}
        archives = data.get("archives") or []
        if not archives:
            checks.record("backups", repo_name, "warn", "empty repo")
            continue
        archive_name = archives[0].get("name", "")
        archive_time = archives[0].get("time", "")
        p = _run(["date", "-d", archive_time, "+%s"])
        try:
            ts = int((p.stdout or "0").strip() or 0)
        except ValueError:
            ts = 0
        age_h = (now_epoch - ts) / 3600
        status = "ok"
        if age_h > max_stale:
            status = "warn"
        if archive_name.endswith(".failed"):
            status = "warn"
        checks.record(
            "backups",
            repo_name,
            status,
            f"latest={archive_name} ({age_h:.1f}h ago)",
        )


# ── 8/9/10. Memory / Load / Processes ────────────────────────────────────
def _meminfo() -> Dict[str, int]:
    out: Dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    try:
                        out[key] = int(parts[1])
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def check_memory(checks: CheckSet, notifs: NotificationQueue) -> None:
    """Memory + swap (bash lines 577-608)."""

    info = _meminfo()
    mem_total_gb = info.get("MemTotal", 0) // 1024 // 1024
    mem_avail_gb = info.get("MemAvailable", 0) // 1024 // 1024
    swap_total_gb = info.get("SwapTotal", 0) // 1024 // 1024
    swap_free_gb = info.get("SwapFree", 0) // 1024 // 1024
    swap_used_gb = swap_total_gb - swap_free_gb

    if mem_avail_gb < 2:
        checks.record(
            "memory",
            "available",
            "fail",
            f"{mem_avail_gb}G available - OOM risk",
        )
        notifs.push(
            "critical", f"sentinel: memory critical - {mem_avail_gb}G available"
        )
    elif mem_avail_gb < 4:
        checks.record(
            "memory",
            "available",
            "warn",
            f"{mem_avail_gb}G available of {mem_total_gb}G",
        )
    else:
        checks.record(
            "memory",
            "available",
            "ok",
            f"{mem_avail_gb}G available of {mem_total_gb}G",
        )

    baseline_append("mem_avail_gb", mem_avail_gb)

    if swap_total_gb > 0 and swap_used_gb > 0:
        pct = swap_used_gb * 100 // swap_total_gb
        status = "warn" if pct > 75 else "ok"
        checks.record(
            "memory",
            "swap",
            status,
            f"{swap_used_gb}G used of {swap_total_gb}G ({pct}%)",
        )


def _loadavg() -> tuple[float, float, float]:
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as fh:
            parts = fh.read().split()
            return float(parts[0]), float(parts[1]), float(parts[2])
    except (OSError, ValueError, IndexError):
        return 0.0, 0.0, 0.0


def check_load(checks: CheckSet) -> None:
    """1m loadavg vs rolling baseline (bash lines 610-639)."""

    load_1m, _, _ = _loadavg()
    baseline_append("load_1m", load_1m)
    samples = _floats(read_baselines().get("load_1m", []))
    median, stdev, count = _stat_median_stdev(samples)
    if count >= 6:
        threshold = median + 3 * stdev
        if load_1m > threshold:
            checks.record(
                "load",
                "1m",
                "warn",
                f"{load_1m} (baseline {median:.2f}±{stdev:.2f}, 3σ spike)",
            )
        else:
            checks.record(
                "load",
                "1m",
                "ok",
                f"{load_1m} (baseline {median:.2f}±{stdev:.2f})",
            )
    elif count > 0:
        checks.record(
            "load",
            "1m",
            "ok",
            f"{load_1m} (building baseline: {count} samples)",
        )
    else:
        checks.record("load", "1m", "ok", f"{load_1m} (collecting baseline)")


def check_processes(checks: CheckSet) -> None:
    """Total + zombie processes vs baseline (bash lines 641-682)."""

    proc_total = 0
    proc_zombies = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        proc_total += 1
        try:
            with open(f"/proc/{entry}/status", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("State:"):
                        state = line.split()[1] if len(line.split()) > 1 else ""
                        if state.lower().startswith("z"):
                            proc_zombies += 1
                        break
        except OSError:
            continue

    if proc_zombies > 5:
        checks.record(
            "processes", "zombies", "warn", f"{proc_zombies} zombie processes"
        )
    else:
        checks.record("processes", "zombies", "ok", str(proc_zombies))

    baseline_append("proc_total", proc_total)
    samples = _floats(read_baselines().get("proc_total", []))
    median, stdev, count = _stat_median_stdev(samples)
    if count >= 6:
        threshold = int(median + 3 * stdev)
        if proc_total > threshold and stdev > 0:
            checks.record(
                "processes",
                "total",
                "warn",
                f"{proc_total} (baseline {median:.2f}±{stdev:.2f}, explosion)",
            )
        else:
            checks.record(
                "processes",
                "total",
                "ok",
                f"{proc_total} (baseline {median:.2f}±{stdev:.2f})",
            )
    elif count > 0:
        checks.record(
            "processes",
            "total",
            "ok",
            f"{proc_total} (building baseline: {count} samples)",
        )
    else:
        checks.record("processes", "total", "ok", f"{proc_total} (collecting baseline)")


# ── 11. Thermal ──────────────────────────────────────────────────────────
def check_thermal(checks: CheckSet, notifs: NotificationQueue) -> None:
    """Thermal zones (bash lines 684-703)."""

    issues = 0
    import glob

    for zone in sorted(glob.glob("/sys/class/thermal/thermal_zone[0-9]*/temp")):
        try:
            temp_c = int(open(zone, "r", encoding="utf-8").read().strip()) // 1000
        except (OSError, ValueError):
            continue
        zone_name = os.path.basename(os.path.dirname(zone))
        if temp_c > 85:
            issues += 1
            checks.record("thermal", zone_name, "fail", f"{temp_c}°C - overheating")
            notifs.push("critical", f"sentinel: {zone_name} at {temp_c}°C")
        elif temp_c > 75:
            issues += 1
            checks.record("thermal", zone_name, "warn", f"{temp_c}°C - elevated")

    if issues == 0:
        try:
            t0 = (
                int(open("/sys/class/thermal/thermal_zone0/temp", "r").read().strip())
                // 1000
            )
        except (OSError, ValueError):
            t0 = 0
        checks.record("thermal", "all_zones", "ok", f"all zones ≤75°C (zone0={t0}°C)")


# ── 12. Disk fill rate ──────────────────────────────────────────────────
def check_disk_fill_rate(checks: CheckSet) -> None:
    """Trend extrapolation per mount (bash lines 705-730)."""

    for mount_path in ("/", "/nix"):
        mount_name = mount_path.replace("/", "_root").lstrip("_") or "root"
        used = _df_pct(mount_path)
        key = f"disk_{mount_name}_pct"
        baseline_append(key, used)
        vals = _floats(read_baselines().get(key, []))
        n = len(vals)
        if n < 12:
            continue
        first = vals[0]
        span_hours = n / 6  # 10-minute interval
        delta = used - first
        rate_per_day = (delta / span_hours) * 24
        if rate_per_day > 2 and used < 95:
            days_left = (100 - used) / rate_per_day if rate_per_day > 0 else 0
            checks.record(
                "disk_rate",
                mount_name,
                "warn",
                f"{used}% used, filling at {rate_per_day:.1f}%/day (~{days_left:.0f}d until full)",
            )
        elif rate_per_day > 0.5:
            checks.record(
                "disk_rate",
                mount_name,
                "ok",
                f"{used}% used, {rate_per_day:.1f}%/day (normal)",
            )
        else:
            checks.record(
                "disk_rate",
                mount_name,
                "ok",
                f"{used}% used, stable ({rate_per_day:.1f}%/day)",
            )


# ── 13. Nix ──────────────────────────────────────────────────────────────
def check_nix(
    checks: CheckSet,
    notifs: NotificationQueue,
    *,
    corrective: bool,
    observe_only: bool,
) -> None:
    """Nix generations + GC trigger (bash lines 732-751)."""

    p = _run(
        ["nix-env", "--list-generations", "--profile", "/nix/var/nix/profiles/system"],
        sudo=True,
    )
    gens = len(p.stdout.splitlines()) if p.returncode == 0 and p.stdout else "?"
    checks.record("nix", "generations", "ok", f"{gens} system generations")

    root_pct = _df_pct("/")
    if root_pct >= 92:
        if systemd.is_active("system", "nix-gc.service"):
            checks.record(
                "nix",
                "gc_trigger",
                "warn",
                f"root at {root_pct}%, nix-gc already running",
            )
        else:
            # the bash sentinel triggers nix-gc unconditionally on >=92%, NOT
            # only under --correct. We preserve that exact behaviour.
            ok, _intent = systemd.start_unit(
                "system", "nix-gc.service", observe_only=observe_only
            )
            if ok:
                checks.record(
                    "nix",
                    "gc_trigger",
                    "warn",
                    f"root at {root_pct}% - triggered nix-gc",
                )
                notifs.push(
                    "critical", f"sentinel: disk {root_pct}% - triggered nix-gc"
                )
            else:
                checks.record(
                    "nix",
                    "gc_trigger",
                    "fail",
                    f"root at {root_pct}% - failed to trigger nix-gc",
                )


# ── 14. Journal ─────────────────────────────────────────────────────────
def check_journal(policy: Dict[str, Any], checks: CheckSet) -> None:
    """Journalctl pattern grep per policy entry (bash lines 753-760)."""

    for j in policy.get("journal", []) or []:
        pattern = j.get("pattern", "")
        severity = j.get("severity", "warn")
        window = j.get("window", "1 hour ago")
        if not pattern:
            continue
        p = _run(
            [
                "journalctl",
                "--boot",
                "--since",
                window,
                "--grep",
                pattern,
                "--quiet",
            ]
        )
        count = len([line for line in (p.stdout or "").splitlines() if line])
        status = severity if count > 0 else "ok"
        checks.record("journal", pattern, status, f"{count} matches in last {window}")


# ── 15. Pressure watchdog feedback ──────────────────────────────────────
_WATCHDOG_KINDS = (
    "sinex.invocation.lacks_declared_resource_class",
    "sinex.invocation.lacks_control_group",
    "sinex.invocation.lacks_io_bytes",
    "sinex.invocation.lacks_psi_window",
    "sinex.invocation.lacks_recorded_unit",
    "systemd.unit.lacks_control_group",
)


def check_pressure_watchdog(checks: CheckSet, notifs: NotificationQueue) -> None:
    """Pressure-watchdog metadata gaps (bash lines 762-804)."""

    window = os.environ.get("SINNIX_WATCHDOG_WINDOW", "5 min ago")
    try:
        threshold = int(os.environ.get("SINNIX_WATCHDOG_THRESHOLD", "5"))
    except ValueError:
        threshold = 5
    p = _run(
        [
            "journalctl",
            "--identifier=sinnix-pressure-watchdog",
            "--since",
            window,
            "--no-pager",
            "--quiet",
        ]
    )
    log = p.stdout or ""
    breaches: List[str] = []
    for kind in _WATCHDOG_KINDS:
        count = log.count(f"{kind}:")
        if count >= threshold:
            breaches.append(f"{kind}={count}")
    if breaches:
        checks.record(
            "pressure",
            "watchdog_metadata_gaps",
            "warn",
            f"{len(breaches)} kind(s) breached in last {window}: {' '.join(breaches)}",
        )
        notifs.push(
            "warning",
            f"sentinel: pressure watchdog reports {len(breaches)} metadata-gap kind(s) breached",
        )
    else:
        checks.record(
            "pressure",
            "watchdog_metadata_gaps",
            "ok",
            f"no kind exceeded {threshold} in last {window}",
        )


# ── now timestamp helpers ───────────────────────────────────────────────
def now_strings() -> tuple[str, int]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ"), int(now.timestamp())
