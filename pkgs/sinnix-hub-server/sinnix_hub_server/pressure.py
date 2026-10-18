"""The machine's memory pressure, measured the way the incidents were.

Thresholds come from the 2026-08-18 clustering of this host's own telemetry.
Swap headroom is the early warning: across 29 freeze onsets, ten minutes before
the machine froze the median swap was 90% consumed while available memory still
read ~12.8 GiB, so swap headroom is the lane's primary number. `memory_psi_full`
is the honest "is anything stalled".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sinnix_lib.procfs import parse_cgroup_v2, parse_colon_numeric, parse_psi

# Swap consumed. The median onset was preceded by 90% ten minutes out; 75% is
# the earliest line the record supports, and the point of the lane is lead time.
SWAP_PRE_FREEZE_PERCENT = 75.0
# memory PSI full: the share of the last ten seconds during which EVERY task
# was stalled. 20 is "degraded" in the incident inventory.
MEMORY_STALL_PSI = 20.0

PROC = Path("/proc")

SWAP_LANE_KEY = "pressure:swap-headroom"
SWAP_LANE_TYPE = "swap_headroom"
SWAP_LANE_UNIT = "swap headroom"


@dataclass(frozen=True)
class Sample:
    """One reading of the four numbers that decide, and nothing else."""

    swap_used_mb: int | None = None
    swap_total_mb: int | None = None
    mem_avail_mb: int | None = None
    mem_total_mb: int | None = None
    memory_psi_full: float | None = None
    memory_psi_some: float | None = None
    io_psi_full: float | None = None
    cpu_psi_some: float | None = None

    @property
    def swap_percent(self) -> float | None:
        if not self.swap_total_mb or self.swap_used_mb is None:
            return None
        return self.swap_used_mb / self.swap_total_mb * 100.0

    @property
    def readable(self) -> bool:
        return any(
            value is not None
            for value in (
                self.swap_percent,
                self.memory_psi_full,
                self.io_psi_full,
                self.mem_avail_mb,
            )
        )


def read_psi(path: Path) -> dict[str, float]:
    """`some`/`full` avg10 out of one /proc/pressure file.

    A kernel without PSI, or a container without the file, yields an empty
    dict rather than zeros: "not measured" and "measured at zero" are opposite
    claims and only one of them is safe to act on.
    """
    try:
        records = parse_psi(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    return {
        name: float(fields["avg10"])
        for name, fields in records.items()
        if "avg10" in fields
    }


def read_meminfo(path: Path) -> dict[str, int]:
    """/proc/meminfo as MiB, for the handful of keys this module reads."""
    wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    try:
        values = parse_colon_numeric(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    return {key: values[key] // 1024 for key in wanted if key in values}


def sample(proc: Path = PROC) -> Sample:
    memory = read_psi(proc / "pressure" / "memory")
    io = read_psi(proc / "pressure" / "io")
    cpu = read_psi(proc / "pressure" / "cpu")
    meminfo = read_meminfo(proc / "meminfo")
    swap_total = meminfo.get("SwapTotal")
    swap_free = meminfo.get("SwapFree")
    return Sample(
        swap_used_mb=(
            swap_total - swap_free
            if swap_total is not None and swap_free is not None
            else None
        ),
        swap_total_mb=swap_total,
        mem_avail_mb=meminfo.get("MemAvailable"),
        mem_total_mb=meminfo.get("MemTotal"),
        memory_psi_full=memory.get("full"),
        memory_psi_some=memory.get("some"),
        io_psi_full=io.get("full"),
        cpu_psi_some=cpu.get("some"),
    )


def swap_lane_status(reading: Sample) -> tuple[str, str] | None:
    """(status, evidence) for the swap-headroom lane, or None if unmeasurable.

    Three states, because swap headroom being gone has two very different
    meanings and calling either of them healthy would be a lie:

      * `pre-freeze` -- swap at or past 75% while memory PSI full is still
        below 20. This is the pair the whole lane exists for: the warning has
        arrived and the machine still works, so a decision is possible.
      * `stalled` -- swap saturated AND tasks already stalling. The warning is
        late; this is the freeze.
      * `healthy` -- swap has headroom.
    """
    percent = reading.swap_percent
    if percent is None:
        return None
    evidence = (
        f"swap_percent={percent:.1f};"
        f"swap_used_mb={reading.swap_used_mb};"
        f"swap_total_mb={reading.swap_total_mb};"
        f"memory_psi_full={'null' if reading.memory_psi_full is None else reading.memory_psi_full};"
        f"mem_avail_mb={'null' if reading.mem_avail_mb is None else reading.mem_avail_mb};"
        f"pre_freeze_percent={SWAP_PRE_FREEZE_PERCENT};"
        f"stall_psi={MEMORY_STALL_PSI}"
    )
    if percent < SWAP_PRE_FREEZE_PERCENT:
        return "healthy", evidence
    if (
        reading.memory_psi_full is not None
        and reading.memory_psi_full >= MEMORY_STALL_PSI
    ):
        return "stalled", evidence
    return "pre-freeze", evidence


def sweep_swap_headroom(reading: Sample, emitter: Any) -> None:
    """The lane, on the health sweep's own tick and through its own emitter.

    Deliberately not a second mechanism: it shares the confirm-2 debounce, the
    `sinnix-health-transition-v1` ledger, the dedup state file, and the
    notification rules with every other lane. A machine with no swap
    configured registers the key without judging it, so the sweep's prune does
    not treat the lane as one it no longer emits.
    """
    verdict = swap_lane_status(reading)
    if verdict is None:
        emitter.observe(SWAP_LANE_KEY)
        return
    status, evidence = verdict
    emitter.emit(SWAP_LANE_KEY, SWAP_LANE_TYPE, SWAP_LANE_UNIT, status, evidence)


def parse_cgroup(text: str) -> tuple[str, str]:
    """(owning unit, owning slice) out of a cgroup v2 membership line."""
    path = parse_cgroup_v2(text)
    if path is None:
        return "", ""
    unit = ""
    slice_unit = ""
    for segment in path.split("/"):
        if segment.endswith((".scope", ".service")):
            unit = segment
        elif segment.endswith(".slice"):
            slice_unit = segment
    return unit, slice_unit
