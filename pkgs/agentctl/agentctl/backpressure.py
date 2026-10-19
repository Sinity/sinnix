"""Pressure admission with an incremental, regenerable spool projection.

Pueue owns dependencies and ordinary stashes. This module pauses a group's
admission under memory pressure, records that pause in its event spool, and
reopens only groups whose last recorded pause is its own.
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
from .config import PoolPolicy
from .pueue import PueueError

MEMORY_FULL_FREEZE = 25.0
RESUME_BELOW = 10.0
CLOSE_ORDER = {
    "memory": ("pytest-heavy", "pytest", "normal", "bulk", "pytest-quick"),
}
MANAGED_GROUPS = ("agent", "pytest-heavy", "pytest", "pytest-quick", "normal", "bulk")
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
            elif action in {"opened", "released", "ownership-lost"}:
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
        write_json_atomic(path, payload, fsync=False)
    except OSError:
        return


def event_state(spool: Path | None, *, checkpoint: Path | None = None) -> SpoolState:
    """Advance by new bytes only, retaining ownership across rotation/truncation."""
    checkpoint_path = _checkpoint_path(spool, checkpoint)
    state = _load_checkpoint(checkpoint_path)
    if spool is None:
        return state
    previous = state
    state = SpoolState(
        pauses=dict(previous.pauses),
        legacy_holds=dict(previous.legacy_holds),
        cursor=previous.cursor,
    )
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
            # Replay one complete record at a time, through the observed
            # size. A growing writer cannot keep this pass open forever.
            # Leave a partial final record for the next pass.
            while offset < metadata.st_size:
                line = handle.readline(metadata.st_size - offset)
                if not line.endswith(b"\n"):
                    break
                offset += len(line)
                try:
                    event = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(event, dict):
                    state.apply(event)
    except OSError:
        # A failed replay cannot replace previously verified ownership or
        # publish a cursor past unread events.
        return previous
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
    # Retired I/O admission events no longer veto recovery. Memory remains
    # the admission signal, including when releasing an old I/O-only pause.
    # Unknown memory never silently becomes a quiet observation.
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


def _append(
    spool: Path | None, event: Mapping[str, object], *, required: bool = False
) -> dict[str, Any]:
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
            if required:
                raise
    elif required:
        raise ValueError("adaptive width changes require an event spool")
    return record


def paused_by_us(spool: Path | None, *, checkpoint: Path | None = None) -> set[str]:
    return event_state(spool, checkpoint=checkpoint).ours()


def _vanished_hold_retirements(state: SpoolState) -> list[dict[str, Any]]:
    """Retire tracked holds whose task pueue no longer knows about.

    A hold leaves the tracked set on its own ``released``/``retired`` event,
    but a held task removed by ``pueue clean`` emits neither, so its entry
    would otherwise be carried forever. pueue owns queue membership, so an
    absent task is authoritative: reconcile against it rather than let this
    checkpoint grow into a second ledger.
    """
    if not state.legacy_holds:
        return []
    try:
        live = pueue.tasks()
    except PueueError:
        return []
    return [
        {
            "kind": "pool-hold",
            "action": "retired",
            "task_id": task_id,
            "reason": "task-absent-from-pueue",
        }
        for task_id in sorted(state.legacy_holds)
        if task_id not in live
    ]


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


def tick(
    *,
    spool: Path | None,
    pressure_root: Path = Path("/proc/pressure"),
    checkpoint: Path | None = None,
    pools: Mapping[str, PoolPolicy] | None = None,
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
    for event in _vanished_hold_retirements(state):
        state.apply(_append(spool, event))
    _save_checkpoint(checkpoint_path, state)
    adaptive = adaptive_widths(pools or {}, groups, pressure, spool)
    signals = over_threshold(pressure)
    signal = "+".join(signals) or None
    paused = [name for name in MANAGED_GROUPS if groups.get(name) == "Paused"]
    obsolete = [
        name
        for name in paused
        if name in state.ours() and _can_reopen(name, state.pauses[name], pressure)
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
    action = "unknown-pressure"
    if _pressure_complete(pressure):
        action = "hold" if paused or signals else "clear"
    return {
        "action": action,
        "adaptive": adaptive,
        "frozen": paused,
        "unverified_pauses": [
            name for name in paused if name in state.pauses and name not in state.ours()
        ],
        "signal": signal,
        **pressure,
    }
