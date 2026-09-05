"""Close queue admission under host pressure instead of killing what is running.

One pass: read the host's pressure, pause or resume one pueue group, record
the transition, exit. A timer runs it. Nothing here loops or sleeps, and
nothing is cancelled — a paused group's tasks keep their work and resume.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Mapping, Sequence

from . import pueue
from .pueue import PueueError

# Measured 2026-09-02 12:29Z: io full avg10 reached 76% under eight concurrent
# normal-pool jobs, against single digits on an idle host. 25% was the point
# where new work stopped being admitted, and it is the point where the queue
# now freezes instead.
IO_FULL_FREEZE = 25.0

# systemd-oomd on this host kills at memory full 50% sustained 30s. Freezing at
# half of that leaves the queue a margin to go quiet before oomd chooses a
# victim, which is the whole difference between freezing and thrashing.
MEMORY_FULL_FREEZE = 25.0

# A signal that caused a closure remains latched while its current 10-second
# pressure is at or above this level. Freeze decisions use avg60 to avoid
# reacting to spikes; recovery uses avg10 so completed load does not hold the
# queue closed for several stale minutes.
RESUME_BELOW = 10.0

# Conversations stay admissible under both signals. Their fixed six-slot cap
# and cgroup limits bound them; pressure gates the heavy work they can launch.
CLOSE_ORDER = {
    "io": ("pytest", "bulk"),
    "memory": ("pytest", "normal", "bulk"),
}
MANAGED_GROUPS = ("agent", "pytest", "normal", "bulk")

# Every pause this module records names itself, and `tick` reopens only a
# group whose most recent pause event is its own: an operator's
# `pueue pause -g X` leaves no event and stays paused until the operator says.
OWNER = "agentctl"


def read_pressure(root: Path = Path("/proc/pressure")) -> dict[str, float]:
    """The host's `full` stall averages. Absent PSI reads as no pressure."""
    values = {
        "memory_full_avg10": 0.0,
        "memory_full_avg60": 0.0,
        "io_full_avg10": 0.0,
        "io_full_avg60": 0.0,
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
            for field in fields[1:]:
                key, _, raw = field.partition("=")
                if key in {"avg10", "avg60"}:
                    try:
                        values[f"{resource}_full_{key}"] = float(raw)
                    except ValueError:
                        pass
    return values


def over_threshold(pressure: Mapping[str, float]) -> tuple[str, ...]:
    """Every signal that currently requires reduced admission."""
    active = []
    if pressure.get("io_full_avg60", 0.0) >= IO_FULL_FREEZE:
        active.append("io")
    if pressure.get("memory_full_avg60", 0.0) >= MEMORY_FULL_FREEZE:
        active.append("memory")
    return tuple(active)


def _recovery_pressure(pressure: Mapping[str, float], signal: str) -> float:
    return pressure.get(
        f"{signal}_full_avg10",
        pressure.get(f"{signal}_full_avg60", 0.0),
    )


def _desired_paused(pressure: Mapping[str, float], paused: Sequence[str]) -> set[str]:
    """Keep existing closures latched per signal until that signal clears."""
    desired: set[str] = set()
    for signal, groups in CLOSE_ORDER.items():
        if _recovery_pressure(pressure, signal) >= RESUME_BELOW:
            desired.update(group for group in paused if group in groups)
    return desired


def _append(spool: Path | None, event: Mapping[str, object]) -> None:
    if spool is None:
        return
    line = json.dumps(
        {
            "schema_version": 1,
            "emitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": "backpressure",
            "owner": OWNER,
            **dict(event),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        spool.parent.mkdir(parents=True, exist_ok=True)
        with open(spool, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


def paused_by_us(spool: Path | None) -> set[str]:
    """Groups whose latest pause event in the spool is this module's own."""
    if spool is None:
        return set()
    try:
        lines = spool.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    latest: dict[str, bool] = {}
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("kind") != "backpressure":
            continue
        group = event.get("group")
        if not isinstance(group, str):
            continue
        if event.get("action") == "closed":
            latest[group] = event.get("owner") == OWNER
        elif event.get("action") == "opened":
            latest.pop(group, None)
    return {group for group, ours in latest.items() if ours}


def tick(*, spool: Path | None, pressure_root: Path = Path("/proc/pressure")) -> dict:
    """Close or reopen one admission group. Never stops running tasks."""
    pressure = read_pressure(pressure_root)
    try:
        groups = pueue.groups_status()
    except PueueError as error:
        return {"action": "unavailable", "error": str(error), "pressure": pressure}

    paused = [name for name in MANAGED_GROUPS if groups.get(name) == "Paused"]
    signals = over_threshold(pressure)
    signal = "+".join(signals) or None

    desired_paused = _desired_paused(pressure, paused)
    ours = paused_by_us(spool)
    obsolete = [name for name in paused if name not in desired_paused and name in ours]
    if obsolete:
        target = obsolete[0]
        try:
            pueue.resume(target)
        except PueueError as error:
            return {"action": "failed", "group": target, "error": str(error)}
        event = {"action": "opened", "group": target, "signal": signal, **pressure}
        _append(spool, event)
        return event

    if signals:
        close_order = tuple(
            dict.fromkeys(group for active in signals for group in CLOSE_ORDER[active])
        )
        running = [name for name in close_order if groups.get(name) == "Running"]
        if not running:
            return {
                "action": "hold",
                "frozen": paused,
                "signal": signal,
                **pressure,
            }
        target = running[0]
        try:
            pueue.pause(target)
        except PueueError as error:
            return {"action": "failed", "group": target, "error": str(error)}
        event = {"action": "closed", "group": target, "signal": signal, **pressure}
        _append(spool, event)
        return event

    return {
        "action": "hold",
        "frozen": paused,
        "signal": signal,
        **pressure,
    }
