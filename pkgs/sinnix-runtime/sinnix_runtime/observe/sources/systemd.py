"""systemctl-driven collectors: managed units, slices, and runtime inventory."""

from __future__ import annotations

import subprocess
from typing import Any

from sinnix_lib.process import run
from sinnix_lib.systemd import show_units
from sinnix_lib.values import int_or_none

from ..runtime_inventory import (
    load_inventory,
    managed_units,
    observed_slices,
    resource_class_for_unit,
    workload_for_unit,
)
from ..util import words

UNIT_PROPERTIES = (
    "Id",
    "LoadState",
    "ActiveState",
    "SubState",
    "MainPID",
    "ControlGroup",
    "Slice",
    "MemoryCurrent",
    "MemorySwapCurrent",
    "NRestarts",
    "MemoryHigh",
    "MemoryMax",
    "CPUWeight",
    "IOWeight",
    "IODeviceLatencyTargetUSec",
    "IOReadBandwidthMax",
    "IOWriteBandwidthMax",
    "IOSchedulingClass",
    "Nice",
    "TimeoutStartUSec",
    "TimeoutStopUSec",
    "WantedBy",
    "Wants",
    "PartOf",
    "NextElapseUSecRealtime",
    "Persistent",
    "Result",
)


def collect_noctalia_health() -> dict[str, Any]:
    result = run(["noctalia", "config", "validate"], timeout=3)
    if result.error is not None:
        return {
            "status": "unavailable",
            "config_warning_count": None,
            "plugin_compatibility": "unknown",
        }
    output = f"{result.stdout}\n{result.stderr}"
    warnings = sum(
        1 for line in output.splitlines() if "WRN" in line or "warning" in line.lower()
    )
    return {
        "status": "healthy" if result.returncode == 0 else "invalid",
        "config_warning_count": warnings,
        "plugin_compatibility": "compatible"
        if result.returncode == 0 and warnings == 0
        else "warning",
    }


def systemctl_show(unit: str, user: bool = False) -> dict[str, str]:
    try:
        props = show_units(
            [unit], user=user, properties=UNIT_PROPERTIES, timeout=3
        ).get(unit)
    except (OSError, subprocess.TimeoutExpired):
        props = None
    if props is None:
        return {"Id": unit, "LoadState": "unknown"}
    props.setdefault("Id", unit)
    return props


def unit_row(unit: str, manager: str, props: dict[str, str]) -> dict[str, Any]:
    return {
        "unit": unit,
        "manager": manager,
        "active_state": props.get("ActiveState"),
        "sub_state": props.get("SubState"),
        "load_state": props.get("LoadState"),
        "main_pid": int_or_none(props.get("MainPID")),
        "control_group": props.get("ControlGroup") or None,
        "slice": props.get("Slice") or None,
        "resource_class": resource_class_for_unit(unit),
        "workload": workload_for_unit(unit),
        "policy": {
            "memory_current": props.get("MemoryCurrent"),
            "memory_swap_current": props.get("MemorySwapCurrent"),
            "restart_count": props.get("NRestarts"),
            "memory_high": props.get("MemoryHigh"),
            "memory_max": props.get("MemoryMax"),
            "cpu_weight": props.get("CPUWeight"),
            "io_weight": props.get("IOWeight"),
            "io_device_latency_target": props.get("IODeviceLatencyTargetUSec"),
            "io_read_bandwidth_max": props.get("IOReadBandwidthMax"),
            "io_write_bandwidth_max": props.get("IOWriteBandwidthMax"),
            "io_scheduling_class": props.get("IOSchedulingClass"),
            "nice": props.get("Nice"),
            "timeout_start": props.get("TimeoutStartUSec"),
            "timeout_stop": props.get("TimeoutStopUSec"),
        },
        "timer": {
            "next_elapse": props.get("NextElapseUSecRealtime") or None,
            "persistent": props.get("Persistent") or None,
        },
        "relationships": {
            "wanted_by": words(props.get("WantedBy")),
            "wants": words(props.get("Wants")),
            "part_of": words(props.get("PartOf")),
        },
        "result": props.get("Result") or None,
        "health": collect_noctalia_health()
        if unit == "noctalia.service" and manager == "user"
        else None,
    }


def collect_systemd_units(offline: bool) -> list[dict[str, Any]]:
    if offline:
        return []
    rows: list[dict[str, Any]] = []
    for manager in ("system", "user"):
        units = managed_units(manager)
        try:
            states = show_units(
                units,
                user=manager == "user",
                properties=UNIT_PROPERTIES,
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            states = {}
        for unit in units:
            props = states.get(unit, {"Id": unit, "LoadState": "unknown"})
            if props.get("LoadState") != "not-found":
                rows.append(unit_row(unit, manager, props))
    return rows


def collect_resource_slices(offline: bool) -> list[dict[str, Any]]:
    if offline:
        return []
    rows: list[dict[str, Any]] = []
    for manager in ("system", "user"):
        units = [unit for candidate, unit in observed_slices() if candidate == manager]
        try:
            states = show_units(
                units,
                user=manager == "user",
                properties=UNIT_PROPERTIES,
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            states = {}
        for unit in units:
            props = states.get(unit, {"Id": unit, "LoadState": "unknown"})
            if props.get("LoadState") != "not-found":
                rows.append(unit_row(unit, manager, props))
    return rows


def collect_runtime_inventory(offline: bool) -> dict[str, Any]:
    if offline:
        return {"offline": True}
    return load_inventory()


CURRENT_PROPERTIES = (
    "Id",
    "LoadState",
    "ActiveState",
    "SubState",
    "InvocationID",
    "MainPID",
    "Slice",
)


def collect_current_units(offline: bool) -> list[dict[str, Any]]:
    """Two manager reads; no per-unit commands or health probe fanout."""
    if offline:
        return []
    rows = []
    for manager in ("system", "user"):
        units = managed_units(manager)
        states = show_units(
            units, user=manager == "user", properties=CURRENT_PROPERTIES, timeout=1
        )
        if units and not states:
            raise RuntimeError(f"{manager} systemd manager unavailable")
        for unit, props in states.items():
            rows.append(
                {
                    "unit": unit,
                    "manager": manager,
                    "load_state": props.get("LoadState"),
                    "active_state": props.get("ActiveState"),
                    "sub_state": props.get("SubState"),
                    "main_pid": int_or_none(props.get("MainPID")),
                    "slice": props.get("Slice"),
                    "expected_target": {
                        "kind": "unit",
                        "unit": unit,
                        "manager": manager,
                        "properties": {
                            key: props[key]
                            for key in (
                                "LoadState",
                                "ActiveState",
                                "SubState",
                                "InvocationID",
                            )
                            if key in props
                        },
                    },
                }
            )
    return rows
