from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

SCHEMA_VERSION = 2
UTC = dt.timezone.utc


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


# NVML handle is initialized once at startup and reused; reads are direct
# library calls (no subprocess), so 1 Hz sampling is cheap and per-sample
# latency is sub-millisecond. nvidia-smi is no longer in the hot path.
_nvml_handle: object | None = None
_nvml_error: str | None = None


def nvml_init() -> None:
    global _nvml_handle, _nvml_error
    try:
        import pynvml
    except ImportError:
        _nvml_error = "gpu.pynvml_unavailable"
        return
    try:
        pynvml.nvmlInit()
        _nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    except pynvml.NVMLError as exc:  # type: ignore[attr-defined]
        _nvml_error = f"gpu.nvml_init_failed:{exc}"
        _nvml_handle = None


def gpu_metrics() -> tuple[dict[str, object], list[str]]:
    if _nvml_handle is None:
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
          mem_used_mb INTEGER,
          mem_avail_mb INTEGER,
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
          gap_codes_json TEXT NOT NULL DEFAULT '[]'
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
          cpu_usage_nsec INTEGER,
          io_read_bytes INTEGER,
          io_write_bytes INTEGER
        );
        CREATE INDEX IF NOT EXISTS service_state_unit_time ON service_state(unit, observed_at);
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
    return {
        "mem_used_mb": int((total - avail) / 1024)
        if total is not None and avail is not None
        else None,
        "mem_avail_mb": int(avail / 1024) if avail is not None else None,
        "swap_used_mb": int((swap_total - swap_free) / 1024)
        if swap_total is not None and swap_free is not None
        else None,
    }


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
    for unit in units:
        user = unit == "polylogued.service"
        props = systemctl_props(unit, user=user, user_name=user_name)
        if not props:
            continue
        rows.append(
            (
                observed_at,
                host,
                boot_id,
                unit,
                "user" if user else "system",
                props.get("ActiveState"),
                props.get("SubState"),
                int_or_none(props.get("MainPID")),
                props.get("ControlGroup"),
                int_or_none(props.get("MemoryCurrent")),
                int_or_none(props.get("CPUUsageNSec")),
                int_or_none(props.get("IOReadBytes")),
                int_or_none(props.get("IOWriteBytes")),
            )
        )
    if rows:
        conn.executemany(
            """
            INSERT INTO service_state (
              observed_at, host, boot_id, unit, scope, active_state, sub_state,
              main_pid, control_group, memory_current_bytes, cpu_usage_nsec,
              io_read_bytes, io_write_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        # High-frequency GPU sampler — runs only if NVML initialized and
        # the interval is positive (set to 0 to disable).
        gpu_stop = threading.Event()
        gpu_thread: threading.Thread | None = None
        if _nvml_handle is not None and args.gpu_interval > 0:
            gpu_thread = threading.Thread(
                target=gpu_sampler_thread,
                args=(str(db), args.host, boot_id, args.gpu_interval, gpu_stop),
                name="gpu-sampler",
                daemon=True,
            )
            gpu_thread.start()

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

            collector_duration_ms = (time.monotonic() - sample_start) * 1000.0
            row = {
                "observed_at": now_iso(),
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
                "mem_used_mb": mem["mem_used_mb"],
                "mem_avail_mb": mem["mem_avail_mb"],
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
                  load_5m, mem_used_mb, mem_avail_mb, swap_used_mb,
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
                  dstate_wchan_summary, gap_codes_json
                ) VALUES (
                  :observed_at, :host, :boot_id, :schema_version, :interval_s,
                  :latency_oversleep_ms, :collector_duration_ms,
                  :cpu_package_w, :cpu_core_w, :cpu_pkg_c, :cpu_max_core_c,
                  :ddr5_1_c, :ddr5_2_c, :nvme_1_c, :nvme_2_c,
                  :motherboard_temps_json, :gpu_temp_c, :gpu_power_w,
                  :gpu_power_limit_w, :gpu_fan_pct, :gpu_util_pct,
                  :gpu_mem_util_pct, :gpu_clock_mhz, :gpu_mem_clock_mhz,
                  :gpu_pstate, :gpu_pcie_gen, :gpu_pcie_width, :load_1m,
                  :load_5m, :mem_used_mb, :mem_avail_mb, :swap_used_mb,
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
                  :dstate_wchan_summary, :gap_codes_json
                )
                """,
                row,
            )
            if sample_start >= next_service:
                insert_service_states(conn, args.host, boot_id, units, args.user_name)
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
            conn.commit()


if __name__ == "__main__":
    raise SystemExit(main())
