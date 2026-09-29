"""Pressure admission with an incremental, regenerable spool projection.

Pueue owns dependencies and ordinary stashes. This module pauses a group with
``pause --wait`` and reports recovery candidates for an operator to resume.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from sinnix_lib.atomic_json import read_json, write_json_atomic
from sinnix_lib.ledger import append_jsonl

from . import pueue
from .pueue import PueueError

IO_FULL_FREEZE = 25.0
MEMORY_FULL_FREEZE = 25.0
RESUME_BELOW = 10.0
CLOSE_ORDER = {
    "io": ("pytest-heavy", "pytest", "bulk"),
    "memory": ("pytest-heavy", "pytest", "normal", "bulk", "pytest-quick"),
}
MANAGED_GROUPS = ("agent", "pytest-heavy", "pytest", "pytest-quick", "normal", "bulk")
OWNER = "agentctl"
CHECKPOINT_SCHEMA = 1
QUICK_GROUP = "pytest-quick"
QUICK_FLOOR = 1
QUICK_CEILING = 8
QUICK_JOB_BUDGET = 1024**3  # Observed maximum: 988 MiB in 106 focused slots.
CGROUP_ROOT = Path("/sys/fs/cgroup")


@dataclass
class SpoolState:
    pauses: dict[str, dict[str, Any]] = field(default_factory=dict)
    cursor: dict[str, int] | None = None

    def apply(self, event: Mapping[str, Any]) -> None:
        if event.get("kind") == "backpressure":
            group, action = event.get("group"), event.get("action")
            if not isinstance(group, str):
                return
            if action == "closed":
                signal = event.get("signal")
                self.pauses[group] = {
                    "owner": event.get("owner"),
                    "signals": signal.split("+") if isinstance(signal, str) else [],
                }
            elif action in {"opened", "released"}:
                self.pauses.pop(group, None)

    def recorded_by_automation(self) -> set[str]:
        return {
            group
            for group, record in self.pauses.items()
            if record.get("owner") == OWNER
        }


def _checkpoint_path(spool: Path | None, checkpoint: Path | None) -> Path | None:
    if checkpoint is not None:
        return checkpoint
    return spool.with_name(f"{spool.name}.backpressure-state.json") if spool else None


def _load_checkpoint(path: Path | None) -> SpoolState:
    if path is None:
        return SpoolState()
    raw = read_json(path)
    if raw is None:
        return SpoolState()
    if not isinstance(raw, dict) or raw.get("schema_version") != CHECKPOINT_SCHEMA:
        return SpoolState()
    state = SpoolState()
    if isinstance(raw.get("pauses"), dict):
        state.pauses = {
            group: dict(record)
            for group, record in raw["pauses"].items()
            if isinstance(group, str) and isinstance(record, dict)
        }
    cursor = raw.get("cursor")
    if isinstance(cursor, dict) and all(
        isinstance(cursor.get(key), int) for key in ("device", "inode", "offset")
    ):
        state.cursor = dict(cursor)
    return state


def _save_checkpoint(path: Path | None, state: SpoolState) -> None:
    if path is None:
        return
    payload = {
        "schema_version": CHECKPOINT_SCHEMA,
        "cursor": state.cursor,
        "pauses": state.pauses,
    }
    try:
        write_json_atomic(path, payload, fsync=False)
    except OSError:
        return


def event_state(spool: Path | None, *, checkpoint: Path | None = None) -> SpoolState:
    """Advance by new bytes only, retaining ownership across rotation/truncation."""
    checkpoint_path = _checkpoint_path(spool, checkpoint)
    state = _load_checkpoint(checkpoint_path)
    if spool is None:
        return state
    try:
        with spool.open("rb") as handle:
            # Attribute bytes to the inode actually opened, not a path that
            # may have rotated between stat and open.
            metadata = os.fstat(handle.fileno())
            identity = {"device": metadata.st_dev, "inode": metadata.st_ino}
            offset = 0
            if (
                state.cursor is not None
                and all(
                    state.cursor.get(key) == value for key, value in identity.items()
                )
                and 0 <= state.cursor["offset"] <= metadata.st_size
            ):
                offset = state.cursor["offset"]
            handle.seek(offset)
            appended = handle.read()
    except OSError:
        return state
    complete, separator, _partial = appended.rpartition(b"\n")
    if separator:
        consumed = len(complete) + 1
        for line in complete.splitlines():
            try:
                event = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(event, dict):
                state.apply(event)
        offset += consumed
    state.cursor = {**identity, "offset": offset}
    _save_checkpoint(checkpoint_path, state)
    return state


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
        value := _value(pressure, "io_full_avg60")
    ) is not None and value >= IO_FULL_FREEZE:
        active.append("io")
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


def _can_reopen(
    group: str, record: Mapping[str, Any], pressure: Mapping[str, float | None]
) -> bool:
    signals = record.get("signals")
    sources = (
        tuple(signal for signal in signals if signal in CLOSE_ORDER)
        if isinstance(signals, list)
        else ()
    )
    # Old events had no signal. Require all readings known and quiet rather
    # than accidentally releasing after an invalid PSI read.
    sources = sources or tuple(CLOSE_ORDER)
    sources = tuple(
        dict.fromkeys(
            (
                *sources,
                *(signal for signal in CLOSE_ORDER if group in CLOSE_ORDER[signal]),
            )
        )
    )
    return _pressure_complete(pressure) and all(
        (value := _recovery_pressure(pressure, signal)) is not None
        and value < RESUME_BELOW
        for signal in sources
    )


def _quick_headroom() -> int | None:
    """Read the quick leaf and its parents; the tightest live limit wins."""
    try:
        shown = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                "--value",
                "--property=ControlGroup",
                "agentctl-pytest-quick.slice",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        if not shown.startswith("/") or ".." in Path(shown).parts:
            return None
        leaf = (CGROUP_ROOT / shown.lstrip("/")).resolve()
        if not leaf.is_relative_to(CGROUP_ROOT.resolve()) or leaf == CGROUP_ROOT:
            return None
        available = []
        # The cgroup v2 root has no memory.current and carries no limit, so
        # the walk stops below it.
        for scope in (leaf, *leaf.parents):
            if scope == CGROUP_ROOT.resolve():
                break
            current = int((scope / "memory.current").read_text().strip())
            for name in ("memory.high", "memory.max"):
                raw = (scope / name).read_text().strip()
                if raw != "max":
                    available.append(int(raw) - current)
        return min(available) if available else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _adjust_quick_width(
    spool: Path | None, groups: Mapping[str, str], pressure: Mapping[str, float | None]
) -> dict[str, Any] | None:
    if groups.get(QUICK_GROUP) not in {"Running", "Paused"}:
        return None
    try:
        width = pueue.groups().get(QUICK_GROUP)
    except PueueError as error:
        return {"action": "unavailable", "group": QUICK_GROUP, "error": str(error)}
    if not isinstance(width, int) or width < QUICK_FLOOR:
        return {
            "action": "unavailable",
            "group": QUICK_GROUP,
            "error": "invalid quick pool width",
        }
    memory = _recovery_pressure(pressure, "memory")
    headroom = _quick_headroom()
    if memory is None or headroom is None:
        return {"action": "unknown-capacity", "group": QUICK_GROUP}
    if groups[QUICK_GROUP] == "Paused" and memory < RESUME_BELOW:
        return None
    if (
        groups[QUICK_GROUP] == "Paused"
        or memory >= RESUME_BELOW
        or headroom < QUICK_JOB_BUDGET
    ):
        target = max(QUICK_FLOOR, width - 1)
    else:
        target = min(QUICK_CEILING, width + 1)
    if target == width:
        return None
    try:
        pueue.set_parallel(QUICK_GROUP, target)
    except PueueError as error:
        return {"action": "failed", "group": QUICK_GROUP, "error": str(error)}
    return _append(
        spool,
        {
            "action": "width-changed",
            "group": QUICK_GROUP,
            "from": width,
            "to": target,
            "memory_headroom": headroom,
            "memory_full": memory,
        },
    )


def _append(spool: Path | None, event: Mapping[str, object]) -> dict[str, Any]:
    record = {
        "schema_version": 1,
        "emitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "backpressure",
        "owner": OWNER,
        **dict(event),
    }
    if spool is not None:
        try:
            append_jsonl(spool, record, fsync=False)
        except OSError:
            pass
    return record


def tick(
    *,
    spool: Path | None,
    pressure_root: Path = Path("/proc/pressure"),
    checkpoint: Path | None = None,
) -> dict[str, Any]:
    """Close or reopen one admission group. Never stops or stashes tasks."""
    pressure = read_pressure(pressure_root)
    state = event_state(spool, checkpoint=checkpoint)
    checkpoint_path = _checkpoint_path(spool, checkpoint)
    try:
        groups = pueue.groups_status()
    except PueueError as error:
        return {"action": "unavailable", "error": str(error), "pressure": pressure}
    for name in sorted(state.recorded_by_automation()):
        if groups.get(name) == "Running":
            state.apply(_append(spool, {"action": "released", "group": name}))
    _save_checkpoint(checkpoint_path, state)
    signals = over_threshold(pressure)
    signal = "+".join(signals) or None
    paused = [name for name in MANAGED_GROUPS if groups.get(name) == "Paused"]
    # Native pause has no generation or owner. An operator may have reasserted
    # the pause while it was already paused, so an old event cannot authorize
    # an automatic resume. The operator can explicitly resume with pueue.
    recovery_needed = [
        name
        for name in paused
        if name in state.recorded_by_automation()
        and _can_reopen(name, state.pauses[name], pressure)
    ]
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
            event = _append(
                spool,
                {"action": "closed", "group": target, "signal": signal, **pressure},
            )
            state.apply(event)
            _save_checkpoint(checkpoint_path, state)
            return {**event, "manual_recovery": recovery_needed}
    width_change = _adjust_quick_width(spool, groups, pressure)
    if width_change is not None:
        return {**width_change, "manual_recovery": recovery_needed}
    return {
        "action": "hold" if _pressure_complete(pressure) else "unknown-pressure",
        "frozen": paused,
        "manual_recovery": recovery_needed,
        "signal": signal,
        **pressure,
    }
