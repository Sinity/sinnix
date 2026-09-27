"""Calendar timers for declared `schedule` operations.

systemd's only role: the durable wake-up a calendar needs. Each declared
schedule is one transient user timer running `agentctl job fire`. The timer
set is reconciled from the descriptors alone — the unit name encodes the
project, operation, expression, agentctl executable and selected config path,
so a changed input is a new unit and the old one is stopped. The set has one
host-wide owner: applying another config replaces the prior timer set. No
state file.
"""

from __future__ import annotations

import hashlib
import subprocess
from typing import Any, Sequence

from .config import Config
from .limits import SYSTEMCTL_TIMEOUT_SECONDS

UNIT_PREFIX = "agentctl-schedule-"


class TimerError(RuntimeError):
    """systemd could not register, list, or stop a timer."""


def _run(argv: Sequence[str], *, check: bool = True) -> str:
    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=SYSTEMCTL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TimerError(f"{argv[0]} failed: {error}") from error
    if check and completed.returncode != 0:
        raise TimerError(completed.stderr.strip() or f"{' '.join(argv[:3])} failed")
    return completed.stdout


def timer_persistent(on_calendar: str) -> bool:
    """Catch up a missed daily or rarer firing; never a sub-hourly one."""
    spec = on_calendar.strip()
    return not (spec.startswith("*:") or spec.startswith("*-*-* *:"))


def unit_for(
    project_id: str,
    operation: str,
    schedule: str,
    executable: str,
    config_path: str | None = None,
) -> str:
    identity = f"{project_id}:{operation}:{schedule}:{executable}"
    if config_path is not None:
        identity += f":{config_path}"
    digest = hashlib.sha256(identity.encode()).hexdigest()
    return UNIT_PREFIX + digest[:24]


def existing_units() -> set[str]:
    output = _run(
        [
            "systemctl",
            "--user",
            "list-units",
            "--all",
            "--plain",
            "--no-legend",
            f"{UNIT_PREFIX}*.timer",
        ]
    )
    units: set[str] = set()
    for line in output.splitlines():
        name = line.split()[0] if line.split() else ""
        if name.startswith(UNIT_PREFIX) and name.endswith(".timer"):
            units.add(name[: -len(".timer")])
    return units


def apply(config: Config) -> dict[str, Any]:
    """Make the live timer set equal the declared schedules."""
    catalog = config.catalog()
    desired: dict[str, dict[str, str]] = {}
    for project, operation in catalog.scheduled_operations():
        assert operation.schedule is not None
        unit = unit_for(
            project.project_id,
            operation.name,
            operation.schedule,
            config.agentctl_executable,
            str(config.config_path) if config.config_path is not None else None,
        )
        desired[unit] = {
            "project": project.project_id,
            "operation": operation.name,
            "schedule": operation.schedule,
        }
    present = existing_units()
    stopped = sorted(present - set(desired))
    for unit in stopped:
        # A transient timer's service unit exists only while it is running;
        # stopping the timer alone is the whole retirement when it is not.
        _run(["systemctl", "--user", "stop", f"{unit}.timer"])
        _run(
            ["systemctl", "--user", "stop", "--no-block", f"{unit}.service"],
            check=False,
        )
    started: list[str] = []
    for unit, entry in sorted(desired.items()):
        if unit in present:
            continue
        persistent = "true" if timer_persistent(entry["schedule"]) else "false"
        command = [config.agentctl_executable]
        if config.config_path is not None:
            command.extend(["--config", str(config.config_path)])
        command.extend(["job", "fire", entry["project"], entry["operation"]])
        _run(
            [
                "systemd-run",
                "--user",
                "--quiet",
                f"--unit={unit}",
                f"--on-calendar={entry['schedule']}",
                f"--timer-property=Persistent={persistent}",
                "--",
                *command,
            ]
        )
        started.append(unit)
    return {
        "timers": [{"unit": unit, **entry} for unit, entry in sorted(desired.items())],
        "started": started,
        "stopped": stopped,
        "unavailable": [
            {"root": root, "reason": reason}
            for root, reason in sorted(catalog.unavailable.items())
        ],
    }
