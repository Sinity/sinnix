"""Attested agent-scope orphan and coldness observations."""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..runtime_inventory import load_inventory, workload_for_cgroup
from ..util import int_or_none


COLD_CPU_PERCENT = 1.0
COLD_IO_BPS = 4096.0
SWAP_CRITERION_SECONDS = 48 * 60 * 60


def _proc_start(path: Path) -> str | None:
    try:
        fields = path.read_text(encoding="utf-8").split()
        return fields[21] if len(fields) > 21 else None
    except OSError:
        return None


def _proc_cgroup(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split(":", 2)
            if len(parts) == 3 and parts[0] == "0":
                return parts[2]
    except OSError:
        pass
    return None


def _number(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def _io_bytes(path: Path) -> int:
    total = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            for field in line.split():
                if field.startswith(("rbytes=", "wbytes=")):
                    total += int_or_none(field.split("=", 1)[1]) or 0
    except (OSError, ValueError):
        return 0
    return total


def _age_seconds(value: Any, now: float) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return max(0, int(now - parsed.timestamp()))
    except ValueError:
        return None


def _identity_revision(job: dict[str, Any]) -> str:
    launcher = job.get("launcher") if isinstance(job.get("launcher"), dict) else {}
    identity = {
        "job_id": job.get("job_id"),
        "pid": launcher.get("pid"),
        "proc_start": launcher.get("proc_start"),
        "cgroup": launcher.get("cgroup"),
    }
    return hashlib.sha256(str(sorted(identity.items())).encode()).hexdigest()[:16]


def _peak_for_cgroup(cgroup: str, below: dict[str, Any]) -> dict[str, Any] | None:
    for row in below.get("cgroup_peaks", []):
        observed = str(row.get("cgroup") or "")
        if observed == cgroup or cgroup in observed or observed in cgroup:
            return row
    return None


def classify_jobs(
    jobs: list[dict[str, Any]],
    below: dict[str, Any] | None = None,
    *,
    proc_root: Path | None = None,
    cgroup_root: Path | None = None,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Return evidence for each manifest without taking any action."""

    proc_root = proc_root or Path(os.environ.get("SINNIX_ORPHAN_PROC_ROOT", "/proc"))
    cgroup_root = cgroup_root or Path(
        os.environ.get("SINNIX_ORPHAN_CGROUP_ROOT", "/sys/fs/cgroup")
    )
    below = below or {}
    now = time.time() if now is None else now
    inventory = load_inventory()
    rows: list[dict[str, Any]] = []
    for job in jobs:
        launcher = job.get("launcher") if isinstance(job.get("launcher"), dict) else {}
        pid = launcher.get("pid")
        expected_start = str(launcher.get("proc_start") or "")
        expected_cgroup = str(launcher.get("cgroup") or "")
        pid_path = proc_root / str(pid) if isinstance(pid, int) else proc_root / "missing"
        current_start = _proc_start(pid_path / "stat")
        current_cgroup = _proc_cgroup(pid_path / "cgroup")
        launcher_live = bool(
            current_start
            and expected_start
            and current_start == expected_start
            and current_cgroup == expected_cgroup
        )
        if launcher_live:
            attestation = "valid"
        elif current_start is None:
            attestation = "dead_launcher"
        elif current_start != expected_start:
            attestation = "pid_reuse"
        elif current_cgroup != expected_cgroup:
            attestation = "cgroup_mismatch"
        else:
            attestation = "unattested"

        cgroup_path = cgroup_root / expected_cgroup.lstrip("/") if expected_cgroup else None
        procs: list[int] = []
        if cgroup_path is not None:
            try:
                procs = [
                    int(value)
                    for value in (cgroup_path / "cgroup.procs").read_text().split()
                    if value.isdigit()
                ]
            except (OSError, ValueError):
                pass
        descendants = [value for value in procs if value != pid]
        workload = workload_for_cgroup(expected_cgroup)
        expendability = workload.get("expendability", "unknown")
        peak = _peak_for_cgroup(expected_cgroup, below)
        swap_bytes = _number(cgroup_path / "memory.swap.current") if cgroup_path else 0
        io_bytes = _io_bytes(cgroup_path / "io.stat") if cgroup_path else 0
        cpu_percent = float(peak.get("max_cpu_pct", 0.0)) if peak else None
        io_bps = float(peak.get("max_rw_bps", 0.0)) if peak else None
        cold = bool(
            not launcher_live
            and descendants
            and swap_bytes > 0
            and peak
            and int(peak.get("samples", 0)) >= 2
            and cpu_percent is not None
            and cpu_percent <= COLD_CPU_PERCENT
            and io_bps is not None
            and io_bps <= COLD_IO_BPS
        )
        orphaned = not launcher_live and bool(descendants) and attestation in {
            "dead_launcher",
            "pid_reuse",
            "cgroup_mismatch",
        }
        rows.append(
            {
                "job_id": job.get("job_id"),
                "identity_revision": _identity_revision(job),
                "age_seconds": _age_seconds(job.get("created_at"), now),
                "attestation": attestation,
                "launcher_live": launcher_live,
                "launcher_pid": pid,
                "expected_cgroup": expected_cgroup,
                "descendant_pids": descendants,
                "orphaned": orphaned,
                "workload": workload,
                "expendability": expendability,
                "coldness": {
                    "candidate": cold,
                    "cpu_percent_max": cpu_percent,
                    "io_bytes_per_second_max": io_bps,
                    "swap_bytes": swap_bytes,
                    "cgroup_io_bytes": io_bytes,
                    "history_samples": int(peak.get("samples", 0)) if peak else 0,
                },
                "swap_criterion": {
                    "required_seconds": SWAP_CRITERION_SECONDS,
                    "observed_seconds": None,
                    "status": "evidence_unavailable",
                    "source": "below history window",
                },
                "proposed_action": "notify",
            }
        )
    return rows
