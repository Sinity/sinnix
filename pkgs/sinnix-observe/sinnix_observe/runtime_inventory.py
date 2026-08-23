"""Sinnix runtime inventory loader shared by observe collectors."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from .default_runtime_inventory import DEFAULT_RUNTIME_INVENTORY_JSON


def inventory_path() -> Path:
    return Path(
        os.environ.get(
            "SINNIX_RUNTIME_INVENTORY_FILE",
            "/etc/sinnix/runtime-inventory.json",
        )
    )


def _default_inventory() -> dict[str, Any]:
    return json.loads(DEFAULT_RUNTIME_INVENTORY_JSON)


def load_inventory() -> dict[str, Any]:
    path = inventory_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return deepcopy(_default_inventory())


def surfaces() -> dict[str, dict[str, Any]]:
    raw = load_inventory().get("surfaces", {})
    return {str(name): value for name, value in raw.items() if isinstance(value, dict)}


def managed_units(manager: str) -> list[str]:
    rows: list[str] = []
    for surface in surfaces().values():
        if surface.get("manager", "system") != manager:
            continue
        # Neither is a unit you can restart: a slice is a cgroup container,
        # and a scope names transient children by prefix.
        if surface.get("kind", "service") in {"slice", "scope"}:
            continue
        unit = surface.get("unit")
        if unit:
            rows.append(str(unit))
    return rows


def observed_slices() -> list[tuple[str, str]]:
    inventory = load_inventory()
    slices = inventory.get("slices", {})
    rows: list[tuple[str, str]] = []
    for manager in ("user", "system"):
        for name in slices.get(manager, {}):
            rows.append((manager, f"{name}.slice"))
    return rows


def resource_class_for_unit(unit: str) -> str | None:
    for surface in surfaces().values():
        if surface.get("unit") == unit:
            value = surface.get("resourceClass")
            return str(value) if value else None
    return None


def workload_for_unit(unit: str) -> dict[str, Any]:
    for surface in surfaces().values():
        if surface.get("unit") == unit:
            workload = surface.get("workload")
            return (
                dict(workload) if isinstance(workload, dict) else {"class": "unknown"}
            )
    return {
        "class": "unknown",
        "source": "unknown",
    }


def workload_for_cgroup(cgroup: str) -> dict[str, Any]:
    for surface in surfaces().values():
        unit = str(surface.get("unit") or "")
        if unit and unit in cgroup:
            workload = workload_for_unit(unit)
            return {**workload, "source": "unit", "unit": unit}
    return {
        "class": "unknown",
        "source": "unknown",
    }


def cgroup_segments(cgroup: str) -> set[str]:
    return {segment for segment in cgroup.split("/") if segment}


def resource_class_from_cgroup(cgroup: str) -> str | None:
    segments = cgroup_segments(cgroup)
    if "system.slice" in segments:
        return "system"
    return None
