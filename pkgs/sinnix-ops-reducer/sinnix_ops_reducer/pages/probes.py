"""Live host probes the pages need and the reducer's snapshot does not carry.

These probe systemd unit state and nvidia-smi's one-line GPU summary on
request, so the numbers a page prints are the numbers at the moment it was
asked for.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{path} does not exist"
    except OSError as error:
        return None, f"{path} unreadable: {error}"
    except json.JSONDecodeError as error:
        return None, f"{path} is not valid JSON: {error}"
    if not isinstance(value, dict):
        return None, f"{path} is not a JSON object"
    return value, None


def systemctl(manager: str, *arguments: str, timeout: int = 15) -> str | None:
    binary = shutil.which("systemctl") or "systemctl"
    scope = "--user" if manager == "user" else "--system"
    try:
        result = subprocess.run(
            [binary, scope, *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout


def show_units(
    manager: str, units: Iterable[str], properties: Iterable[str]
) -> dict[str, dict[str, str]]:
    """`systemctl show` a batch of units, keyed by unit id.

    The manager matters: asking the system manager about a user unit reports
    not-found, which would render as "not installed" and hide a service that is
    running perfectly well.
    """
    names = [unit for unit in units if unit]
    if not names:
        return {}
    output = systemctl(
        manager,
        "show",
        *(f"--property={name}" for name in ("Id", *properties)),
        *names,
    )
    if output is None:
        return {}
    states: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            if current.get("Id"):
                states[current["Id"]] = current
            current = {}
            continue
        key, _, value = line.partition("=")
        current[key] = value
    if current.get("Id"):
        states[current["Id"]] = current
    return states


UNIT_PROPERTIES = ("ActiveState", "SubState", "UnitFileState", "LoadState")


def unit_states(units: list[tuple[str, str]]) -> dict[str, dict[str, str]]:
    states: dict[str, dict[str, str]] = {}
    for manager in {manager for manager, _ in units}:
        states.update(
            show_units(
                manager,
                [unit for owner, unit in units if owner == manager],
                UNIT_PROPERTIES,
            )
        )
    return states


def monotonic_now_us() -> int | None:
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            return int(float(handle.read().split()[0]) * 1_000_000)
    except (OSError, ValueError, IndexError):
        return None


def gpu_summary() -> str | None:
    nvidia = shutil.which("nvidia-smi")
    if not nvidia:
        return None
    try:
        result = subprocess.run(
            [
                nvidia,
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = result.stdout.strip().splitlines()
    return line[0].strip() if line else None


def project_of(path: str | None) -> str | None:
    if not path:
        return None
    parts = Path(path).parts
    for anchor in ("project", "worktrees"):
        if anchor in parts:
            index = parts.index(anchor)
            if index + 1 < len(parts):
                return parts[index + 1]
    return None
