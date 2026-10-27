"""Observe surviving unit members independently of systemd's active state."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .limits import SYSTEMCTL_TIMEOUT_SECONDS
from .run import systemd_environment

CGROUP_ROOT = Path("/sys/fs/cgroup")


def unit_cgroup(unit: str) -> str | None:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", "-p", "ControlGroup", unit],
            capture_output=True,
            text=True,
            check=False,
            timeout=SYSTEMCTL_TIMEOUT_SECONDS,
            env=systemd_environment(),
        )
        if result.returncode == 0:
            for line in (result.stdout or "").splitlines():
                if line.startswith("ControlGroup="):
                    return line.partition("=")[2]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def observe(unit: str, cgroup: str | None = None) -> dict[str, Any]:
    # Capture ControlGroup before stop: systemd can forget it while privileged
    # descendants still occupy the kernel cgroup.
    if not cgroup:
        cgroup = unit_cgroup(unit)
    observation: dict[str, Any] = {
        "unit": unit,
        "cgroup": cgroup,
        "status": "unresolved",
    }
    if cgroup == "":
        return {**observation, "status": "empty", "pids": []}
    if (
        not isinstance(cgroup, str)
        or not cgroup.startswith("/")
        or cgroup == "/"
        or ".." in Path(cgroup).parts
    ):
        return observation
    path = CGROUP_ROOT / cgroup.lstrip("/")
    try:
        try:
            path.stat()
        except FileNotFoundError:
            return {**observation, "status": "empty", "pids": []}

        # os.walk's default silently ignores unreadable subtrees.
        def unreadable(error):
            raise error

        pids = set()
        for directory, _children, _files in os.walk(path, onerror=unreadable):
            member = Path(directory) / "cgroup.procs"
            try:
                pids.update(int(pid) for pid in member.read_text().split())
            except FileNotFoundError:
                if Path(directory).exists():
                    return observation

    except (OSError, ValueError):
        return observation
    return {
        **observation,
        "status": "populated" if pids else "empty",
        "pids": sorted(pids),
    }


def cancellation_obstacle(
    disposition: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not disposition or not disposition.get("cancellation_incomplete"):
        return None
    unit = disposition.get("unit")
    if not isinstance(unit, str) or not unit:
        return {"status": "unresolved", "error": "cancellation has no unit identity"}
    observation = observe(unit, disposition.get("cgroup"))
    return observation if observation["status"] != "empty" else None
