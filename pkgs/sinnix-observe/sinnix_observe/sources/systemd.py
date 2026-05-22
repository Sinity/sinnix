"""systemctl-driven collectors: managed units, slices, and sentinel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..util import int_or_none, run_cmd, split_props, words

SYSTEM_UNITS = [
    "below.service",
    "sinnix-pressure-watchdog.service",
    "sinex-runtime.target",
    "sinex-runtime.timer",
    "sinex-ingestd.service",
    "sinex-filesystem-1.service",
    "sinex-gateway.service",
    "nats.service",
    "postgresql.service",
    "nix-gc.service",
    "nix-optimise.service",
    "sinex-blob-gc.service",
    "sinex-blob-fsck.service",
    "sinex-dev-cache-prune.service",
    "sinex-document-scan.service",
    "btrbk.service",
    "btrbk.timer",
    "borgbackup-job-realm.service",
    "borgbackup-job-persist.service",
    "borgbackup-check.service",
]

USER_UNITS = [
    "polylogued.service",
    "polylogue-browser-capture.service",
]

RESOURCE_CLASS_BY_UNIT = {
    "below.service": "observability",
    "sinnix-pressure-watchdog.service": "observability",
    "btrbk.service": "background-maintenance",
    "btrbk.timer": "background-maintenance",
    "borgbackup-job-realm.service": "background-maintenance",
    "borgbackup-job-persist.service": "background-maintenance",
    "borgbackup-check.service": "background-maintenance",
    "nix-gc.service": "background-maintenance",
    "nix-optimise.service": "background-maintenance",
    "polylogued.service": "capture-runtime",
    "polylogue-browser-capture.service": "capture-runtime",
    "sinex-runtime.target": "capture-runtime",
    "sinex-runtime.timer": "capture-runtime",
    "sinex-ingestd.service": "capture-runtime",
    "sinex-filesystem-1.service": "capture-runtime",
    "sinex-gateway.service": "capture-runtime",
    "nats.service": "capture-substrate",
    "postgresql.service": "capture-substrate",
    "sinex-blob-gc.service": "background-maintenance",
    "sinex-blob-fsck.service": "background-maintenance",
    "sinex-dev-cache-prune.service": "background-maintenance",
    "sinex-document-scan.service": "background-maintenance",
}


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
        "resource_class": RESOURCE_CLASS_BY_UNIT.get(unit),
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
    for unit in SYSTEM_UNITS:
        props = systemctl_show(unit, user=False)
        if props.get("LoadState") == "not-found":
            continue
        rows.append(unit_row(unit, "system", props))
    for unit in USER_UNITS:
        props = systemctl_show(unit, user=True)
        if props.get("LoadState") == "not-found":
            continue
        rows.append(unit_row(unit, "user", props))
    return rows


def collect_resource_slices(offline: bool) -> list[dict[str, Any]]:
    if offline:
        return []
    specs = [
        ("user", "agent.slice"),
        ("user", "build.slice"),
        ("user", "nix-build.slice"),
        ("user", "background.slice"),
        ("system", "nix-build.slice"),
        ("system", "background.slice"),
        ("system", "sinnix-maintenance.slice"),
    ]
    rows: list[dict[str, Any]] = []
    for manager, unit in specs:
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
