"""Close queue admission under host pressure instead of killing what is running.

One pass: read the host's pressure, pause or resume one pueue group, record
the transition, exit. A timer runs it. Nothing here loops or sleeps, and
nothing is cancelled — a paused group's tasks keep their work and resume.
"""

from __future__ import annotations

import argparse
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

# A signal that caused a closure remains latched while it is at or above this
# level. Each signal is evaluated independently, so unrelated pressure cannot
# keep a group closed.
RESUME_BELOW = 10.0

# Conversations stay admissible under both signals. Their fixed six-slot cap
# and cgroup limits bound them; pressure gates the heavy work they can launch.
CLOSE_ORDER = {
    "io": ("pytest", "bulk"),
    "memory": ("pytest", "normal", "bulk"),
}
MANAGED_GROUPS = ("agent", "pytest", "normal", "bulk")


def read_pressure(root: Path = Path("/proc/pressure")) -> dict[str, float]:
    """The host's `full` stall averages. Absent PSI reads as no pressure."""
    values = {"memory_full_avg60": 0.0, "io_full_avg60": 0.0}
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
                if key == "avg60":
                    try:
                        values[f"{resource}_full_avg60"] = float(raw)
                    except ValueError:
                        pass
    return values


def over_threshold(pressure: Mapping[str, float]) -> str | None:
    """The signal that says freeze, or None."""
    if pressure.get("io_full_avg60", 0.0) >= IO_FULL_FREEZE:
        return "io"
    if pressure.get("memory_full_avg60", 0.0) >= MEMORY_FULL_FREEZE:
        return "memory"
    return None


def _signal_pressure(pressure: Mapping[str, float], signal: str) -> float:
    return pressure.get(f"{signal}_full_avg60", 0.0)


def _desired_paused(
    pressure: Mapping[str, float], paused: Sequence[str]
) -> set[str]:
    """Keep existing closures latched per signal until that signal clears."""
    desired: set[str] = set()
    for signal, groups in CLOSE_ORDER.items():
        if _signal_pressure(pressure, signal) >= RESUME_BELOW:
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


def tick(*, spool: Path | None, pressure_root: Path = Path("/proc/pressure")) -> dict:
    """Close or reopen one admission group. Never stops running tasks."""
    pressure = read_pressure(pressure_root)
    try:
        groups = pueue.groups_status()
    except PueueError as error:
        return {"action": "unavailable", "error": str(error), "pressure": pressure}

    paused = [name for name in MANAGED_GROUPS if groups.get(name) == "Paused"]
    signal = over_threshold(pressure)

    desired_paused = _desired_paused(pressure, paused)
    obsolete = [name for name in paused if name not in desired_paused]
    if obsolete:
        target = obsolete[0]
        try:
            pueue.resume(target)
        except PueueError as error:
            return {"action": "failed", "group": target, "error": str(error)}
        event = {"action": "opened", "group": target, "signal": signal, **pressure}
        _append(spool, event)
        return event

    if signal is not None:
        close_order = CLOSE_ORDER[signal]
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-backpressure")
    parser.add_argument(
        "--event-spool", type=Path, default=Path("/realm/state/agentctl/events.jsonl")
    )
    parsed = parser.parse_args(argv)
    print(json.dumps(tick(spool=parsed.event_spool), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
