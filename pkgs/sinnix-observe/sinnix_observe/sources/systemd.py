"""systemctl-driven collectors: managed units, slices, and sentinel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..util import int_or_none, run_cmd, split_props, words
from ..workload_policy import (
    observed_slices,
    observed_units,
    resource_class_for_unit,
)


def systemctl_show(unit: str, user: bool = False) -> dict[str, str]:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd += [
        "show",
        unit,
        "--no-pager",
        "-p",
        "Id",
        "-p",
        "LoadState",
        "-p",
        "ActiveState",
        "-p",
        "SubState",
        "-p",
        "MainPID",
        "-p",
        "ControlGroup",
        "-p",
        "Slice",
        "-p",
        "MemoryCurrent",
        "-p",
        "MemoryHigh",
        "-p",
        "MemoryMax",
        "-p",
        "CPUWeight",
        "-p",
        "IOWeight",
        "-p",
        "IODeviceLatencyTargetUSec",
        "-p",
        "IOReadBandwidthMax",
        "-p",
        "IOWriteBandwidthMax",
        "-p",
        "IOSchedulingClass",
        "-p",
        "Nice",
        "-p",
        "TimeoutStartUSec",
        "-p",
        "TimeoutStopUSec",
        "-p",
        "WantedBy",
        "-p",
        "Wants",
        "-p",
        "PartOf",
        "-p",
        "NextElapseUSecRealtime",
        "-p",
        "Persistent",
        "-p",
        "Result",
    ]
    proc = run_cmd(cmd, timeout=3)
    if not proc or proc.returncode not in (0, 1):
        return {"Id": unit, "LoadState": "unknown"}
    props = split_props(proc.stdout)
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
        "policy": {
            "memory_current": props.get("MemoryCurrent"),
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
    }


def collect_systemd_units(offline: bool) -> list[dict[str, Any]]:
    if offline:
        return []
    rows: list[dict[str, Any]] = []
    for unit in observed_units("system"):
        props = systemctl_show(unit, user=False)
        if props.get("LoadState") == "not-found":
            continue
        rows.append(unit_row(unit, "system", props))
    for unit in observed_units("user"):
        props = systemctl_show(unit, user=True)
        if props.get("LoadState") == "not-found":
            continue
        rows.append(unit_row(unit, "user", props))
    return rows


def collect_resource_slices(offline: bool) -> list[dict[str, Any]]:
    if offline:
        return []
    rows: list[dict[str, Any]] = []
    for manager, unit in observed_slices():
        props = systemctl_show(unit, user=manager == "user")
        if props.get("LoadState") == "not-found":
            continue
        rows.append(unit_row(unit, manager, props))
    return rows


def collect_sentinel(offline: bool) -> dict[str, Any]:
    if offline:
        return {"offline": True}
    state = {"service": systemctl_show("sinnix-sentinel.service")}
    policy = Path("/etc/sinnix/health-policy.json")
    if policy.exists():
        try:
            state["health_policy"] = json.loads(policy.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state["health_policy_error"] = str(policy)
    health = Path("/run/sinnix/health.json")
    if health.exists():
        try:
            state["latest_health"] = json.loads(health.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state["latest_health_error"] = str(health)
    return state
