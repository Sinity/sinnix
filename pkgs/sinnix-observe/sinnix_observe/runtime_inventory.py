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
        if surface.get("kind", "service") in {"capture", "slice"}:
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


def cgroup_segments(cgroup: str) -> set[str]:
    return {segment for segment in cgroup.split("/") if segment}


def resource_class_from_cgroup(cgroup: str) -> str | None:
    segments = cgroup_segments(cgroup)
    command_classes = load_inventory().get("commandClasses", {})
    if isinstance(command_classes, dict):
        for command in command_classes.values():
            if not isinstance(command, dict):
                continue
            slice_name = command.get("slice")
            resource_class = command.get("resourceClass")
            if slice_name and resource_class and str(slice_name) in segments:
                return str(resource_class)
    if "system.slice" in segments:
        return "system"
    return None
