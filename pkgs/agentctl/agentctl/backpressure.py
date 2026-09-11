"""Pressure admission with an incremental, regenerable spool projection.

Pueue owns dependencies and stashes. This module only pauses a group with
``pause --wait`` and later resumes pauses it can prove it made.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from . import pueue
from .pueue import PueueError

IO_FULL_FREEZE = 25.0
MEMORY_FULL_FREEZE = 25.0
RESUME_BELOW = 10.0
CLOSE_ORDER = {
    "io": ("pytest", "bulk"),
    "memory": ("pytest", "normal", "bulk", "pytest-quick"),
}
MANAGED_GROUPS = ("agent", "pytest", "pytest-quick", "normal", "bulk")
OWNER = "agentctl"
CHECKPOINT_SCHEMA = 1


@dataclass
class SpoolState:
    pauses: dict[str, dict[str, Any]] = field(default_factory=dict)
    # The complete last unresolved event, not just its task id: task ids can
    # move under `pueue switch`, so retirement needs a corroborating identity.
    legacy_holds: dict[int, dict[str, Any]] = field(default_factory=dict)
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
        elif event.get("kind") == "pool-hold":
            task_id, action = event.get("task_id"), event.get("action")
            if not isinstance(task_id, int):
                return
            if action == "held":
                self.legacy_holds[task_id] = dict(event)
            elif action in {"released", "retired"}:
                self.legacy_holds.pop(task_id, None)

    def ours(self) -> set[str]:
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
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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
    if isinstance(raw.get("legacy_holds"), dict):
        state.legacy_holds = {
            int(task_id): dict(event)
            for task_id, event in raw["legacy_holds"].items()
            if isinstance(task_id, str)
            and task_id.isdigit()
            and isinstance(event, dict)
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
        "legacy_holds": {
            str(task_id): event for task_id, event in state.legacy_holds.items()
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        os.replace(temporary, path)
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
    record: Mapping[str, Any], pressure: Mapping[str, float | None]
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
    return _pressure_complete(pressure) and all(
        (value := _recovery_pressure(pressure, signal)) is not None
        and value < RESUME_BELOW
        for signal in sources
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
            spool.parent.mkdir(parents=True, exist_ok=True)
            with open(spool, "a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                )
        except OSError:
            pass
    return record


def paused_by_us(spool: Path | None, *, checkpoint: Path | None = None) -> set[str]:
    return event_state(spool, checkpoint=checkpoint).ours()


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
    for name in sorted(state.ours()):
        if groups.get(name) == "Running":
            state.apply(_append(spool, {"action": "released", "group": name}))
    _save_checkpoint(checkpoint_path, state)
    signals = over_threshold(pressure)
    signal = "+".join(signals) or None
    paused = [name for name in MANAGED_GROUPS if groups.get(name) == "Paused"]
    obsolete = [
        name
        for name in paused
        if name in state.ours() and _can_reopen(state.pauses[name], pressure)
    ]
    if obsolete:
        target = obsolete[0]
        try:
            pueue.resume(target)
        except PueueError as error:
            return {
                "action": "failed",
                "group": target,
                "error": str(error),
                "pressure": pressure,
            }
        event = _append(
            spool, {"action": "opened", "group": target, "signal": signal, **pressure}
        )
        state.apply(event)
        _save_checkpoint(checkpoint_path, state)
        return event
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
            return event
    return {
        "action": "hold" if _pressure_complete(pressure) else "unknown-pressure",
        "frozen": paused,
        "signal": signal,
        **pressure,
    }
