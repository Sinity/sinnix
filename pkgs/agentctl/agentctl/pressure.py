"""Pressure pauses: stop admitting jobs to a group under memory pressure.

Pueue owns dependencies, stashes and every group's paused or running state,
and each tick reads that state from pueue. Under memory pressure a tick pauses
one running group of ``CLOSE_ORDER``; once pressure has receded it reopens one
paused group of that order. Groups outside the order are never touched. Each
change is reported to the event log, which nothing reads back.
"""

from __future__ import annotations

import math
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from sinnix_lib.ledger import append_jsonl

from . import pueue
from .config import PoolPolicy
from .pueue import PueueError

# Bound the whole pass, including hold release, below TimeoutStartSec=30s.
# The per-call cap alone cannot bound several sequential queue requests.
TICK_TIMEOUT_SECONDS = 20
TICK_CALL_TIMEOUT_SECONDS = 8

MEMORY_FULL_FREEZE = 25.0
RESUME_BELOW = 10.0
CLOSE_ORDER = {
    "memory": ("pytest-heavy", "pytest", "normal", "bulk", "pytest-quick"),
}
EVENT_KIND = "pressure"


def read_pressure(root: Path = Path("/proc/pressure")) -> dict[str, float | None]:
    """Unknown PSI is unknown; it never silently reads as zero."""
    values: dict[str, float | None] = {
        "memory_full_avg10": None,
        "memory_full_avg60": None,
        "io_full_avg10": None,
        "io_full_avg60": None,
    }
    for resource in ("memory", "io"):
        try:
            content = (root / resource).read_text()
        except OSError:
            continue
        for line in content.splitlines():
            fields = line.split()
            if not fields or fields[0] != "full":
                continue
            for metric in fields[1:]:
                key, _, raw = metric.partition("=")
                if key not in {"avg10", "avg60"}:
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue
                if math.isfinite(value) and value >= 0:
                    values[f"{resource}_full_{key}"] = value
    return values


def _value(pressure: Mapping[str, float | None], key: str) -> float | None:
    value = pressure.get(key)
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def over_threshold(pressure: Mapping[str, float | None]) -> tuple[str, ...]:
    active = []
    if (
        value := _value(pressure, "memory_full_avg60")
    ) is not None and value >= MEMORY_FULL_FREEZE:
        active.append("memory")
    return tuple(active)


def _recovery_pressure(
    pressure: Mapping[str, float | None], signal: str
) -> float | None:
    avg10 = _value(pressure, f"{signal}_full_avg10")
    return avg10 if avg10 is not None else _value(pressure, f"{signal}_full_avg60")


def _pressure_complete(pressure: Mapping[str, float | None]) -> bool:
    return all(
        _value(pressure, f"{signal}_full_avg60") is not None for signal in CLOSE_ORDER
    )


def _can_reopen(pressure: Mapping[str, float | None]) -> bool:
    """Every signal is known and below the resume threshold.

    Unknown memory never silently becomes a quiet observation.
    """
    return _pressure_complete(pressure) and all(
        (value := _recovery_pressure(pressure, signal)) is not None
        and value < RESUME_BELOW
        for signal in CLOSE_ORDER
    )


def _append(
    spool: Path | None, event: Mapping[str, object], *, required: bool = False
) -> dict[str, Any]:
    record = {
        "schema_version": 1,
        "emitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": EVENT_KIND,
        **dict(event),
    }
    if spool is not None:
        try:
            append_jsonl(spool, record, fsync=False)
        except OSError:
            if required:
                raise
    elif required:
        raise ValueError("adaptive width changes require an event spool")
    return record


def slice_headroom(unit: str, root: Path = Path("/sys/fs/cgroup")) -> int:
    """Read effective high/max headroom, including finite ancestor bounds."""
    result = subprocess.run(
        ["systemctl", "--user", "show", unit, "--property=ControlGroup", "--value"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    relative = result.stdout.strip()
    if not relative.startswith("/") or relative == "/" or ".." in Path(relative).parts:
        raise ValueError("slice has no active cgroup")
    current = root / relative.lstrip("/")
    bounds = []
    while current != root:
        used = int((current / "memory.current").read_text().strip())
        if used < 0:
            raise ValueError("negative memory.current")
        for limit_file in ("memory.high", "memory.max"):
            raw = (current / limit_file).read_text().strip()
            if raw != "max":
                bound = int(raw)
                if bound < 0:
                    raise ValueError("negative memory bound")
                bounds.append(bound - used)
        current = current.parent
    if not bounds:
        raise ValueError("slice has no finite memory bound")
    return min(bounds)


def adaptive_widths(pools, groups, pressure, spool):
    """Resize admission only. Missing pressure/accounting cannot raise width."""
    policies = {
        name: policy for name, policy in pools.items() if policy.adaptive is not None
    }
    if policies and spool is None:
        return [
            {
                "status": "unavailable",
                "error": "adaptive admission requires an event spool",
            }
        ]
    if not policies:
        return []
    try:
        widths = pueue.groups()
    except PueueError as error:
        return [{"status": "unavailable", "error": str(error)}]
    observations = []
    for group, policy in sorted(policies.items()):
        if groups.get(group) != "Running" or group not in widths:
            observations.append({"group": group, "status": "not-running"})
            continue
        adaptive = policy.adaptive
        try:
            headroom = slice_headroom(adaptive.slice)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            observations.append(
                {"group": group, "status": "unavailable", "error": str(error)}
            )
            continue
        psi = [
            _value(pressure, key) for key in ("memory_full_avg10", "memory_full_avg60")
        ]
        if any(value is None for value in psi):
            observations.append({"group": group, "status": "unknown-pressure"})
            continue
        before = widths[group]
        if max(psi) >= RESUME_BELOW or headroom <= adaptive.job_memory_bytes:
            after = max(adaptive.floor, before - 1)
        else:
            after = min(policy.parallel, before + 1)
        after = max(adaptive.floor, min(policy.parallel, after))
        observation = {
            "group": group,
            "from": before,
            "to": after,
            "headroom_bytes": headroom,
            "job_memory_bytes": adaptive.job_memory_bytes,
        }
        if after != before:
            try:
                pueue.set_parallel(group, after)
            except PueueError as error:
                observations.append(
                    {**observation, "status": "failed", "error": str(error)}
                )
                continue
            try:
                _append(
                    spool,
                    {"action": "resized", **observation, **pressure},
                    required=True,
                )
            except (OSError, ValueError) as error:
                observations.append(
                    {**observation, "status": "recording-failed", "error": str(error)}
                )
                continue
        observations.append(
            {**observation, "status": "resized" if after != before else "unchanged"}
        )
    return observations


class TickDeadline(Exception):
    """The complete pressure pass exhausted its wall-clock budget."""


def tick(
    *,
    spool: Path | None,
    pressure_root: Path = Path("/proc/pressure"),
    pools: Mapping[str, PoolPolicy] | None = None,
    release_holds: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the complete timer pass within one deadline (main thread only)."""

    def expired(_signum, _frame):
        raise TickDeadline("pressure tick deadline exceeded")

    previous_handler = signal.signal(signal.SIGALRM, expired)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, TICK_TIMEOUT_SECONDS)
    began = time.monotonic()
    try:
        with pueue.call_deadline(TICK_CALL_TIMEOUT_SECONDS):
            decision = _tick(
                spool=spool,
                pressure_root=pressure_root,
                pools=pools,
            )
            if release_holds is not None:
                holds = (
                    release_holds()
                    if decision.get("action") in {"hold", "clear"}
                    else {"released": [], "waiting": []}
                )
                decision.update(
                    holds_released=holds["released"], holds_waiting=holds["waiting"]
                )
            return decision
    except TickDeadline as error:
        return {"action": "unavailable", "error": str(error)}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0]:
            signal.setitimer(
                signal.ITIMER_REAL,
                max(0.000001, previous_timer[0] - (time.monotonic() - began)),
                previous_timer[1],
            )


def _tick(
    *,
    spool: Path | None,
    pressure_root: Path,
    pools: Mapping[str, PoolPolicy] | None,
) -> dict[str, Any]:
    pressure = read_pressure(pressure_root)
    try:
        groups = pueue.groups_status()
    except PueueError as error:
        return {"action": "unavailable", "error": str(error), "pressure": pressure}
    adaptive = adaptive_widths(pools or {}, groups, pressure, spool)
    signals = over_threshold(pressure)
    signal = "+".join(signals) or None
    order = tuple(
        dict.fromkeys(group for groups_of in CLOSE_ORDER.values() for group in groups_of)
    )
    paused = [name for name in order if groups.get(name) == "Paused"]
    if paused and _can_reopen(pressure):
        target = paused[0]
        try:
            pueue.resume(target)
        except PueueError as error:
            return {
                "action": "failed",
                "group": target,
                "error": str(error),
                "pressure": pressure,
            }
        return _append(
            spool, {"action": "opened", "group": target, "signal": signal, **pressure}
        )
    if signals:
        close_order = tuple(
            dict.fromkeys(group for active in signals for group in CLOSE_ORDER[active])
        )
        running = [name for name in close_order if groups.get(name) == "Running"]
        if running:
            target = running[0]
            try:
                pueue.pause(target)
            except PueueError as error:
                return {
                    "action": "failed",
                    "group": target,
                    "error": str(error),
                    "pressure": pressure,
                }
            return _append(
                spool,
                {"action": "closed", "group": target, "signal": signal, **pressure},
            )
    action = "unknown-pressure"
    if _pressure_complete(pressure):
        action = "hold" if paused or signals else "clear"
    return {
        "action": action,
        "adaptive": adaptive,
        "frozen": paused,
        "signal": signal,
        **pressure,
    }
