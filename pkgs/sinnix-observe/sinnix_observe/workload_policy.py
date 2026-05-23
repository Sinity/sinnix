"""Sinnix workload policy loader shared by observe collectors."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_POLICY: dict[str, Any] = {
    "schema": "sinnix-workload-policy-v1",
    "observedUnits": {
        "system": [
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
            "sinex-document-scan.service",
            "btrbk.service",
            "btrbk.timer",
            "borgbackup-job-realm.service",
            "borgbackup-job-persist.service",
            "borgbackup-check.service",
        ],
        "user": [
            "polylogued.service",
            "polylogue-browser-capture.service",
        ],
    },
    "observedSlices": {
        "system": [
            "nix-build.slice",
            "background.slice",
            "system-critical.slice",
        ],
        "user": [
            "agent.slice",
            "build.slice",
            "nix-build.slice",
            "background.slice",
        ],
    },
    "unitClasses": {
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
        "sinex-document-scan.service": "background-maintenance",
    },
}


def policy_path() -> Path:
    return Path(
        os.environ.get(
            "SINNIX_WORKLOAD_POLICY_FILE",
            "/etc/sinnix/workload-policy.json",
        )
    )


def load_policy() -> dict[str, Any]:
    path = policy_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return deepcopy(DEFAULT_POLICY)


def observed_units(manager: str) -> list[str]:
    return list(load_policy().get("observedUnits", {}).get(manager, []))


def observed_slices() -> list[tuple[str, str]]:
    policy = load_policy()
    slices = policy.get("observedSlices", {})
    rows: list[tuple[str, str]] = []
    for manager in ("user", "system"):
        for unit in slices.get(manager, []):
            rows.append((manager, unit))
    return rows


def resource_class_for_unit(unit: str) -> str | None:
    value = load_policy().get("unitClasses", {}).get(unit)
    return str(value) if value else None


def resource_class_from_cgroup(cgroup: str) -> str | None:
    if "build.slice" in cgroup or "nix-build.slice" in cgroup:
        return "developer-build"
    if "background.slice" in cgroup:
        return "background-maintenance"
    if "agent.slice" in cgroup:
        return "interactive-agent"
    if "app-graphical.slice" in cgroup or "app.slice" in cgroup:
        return "interactive"
    if "system.slice" in cgroup:
        return "system"
    return None
