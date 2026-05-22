"""systemctl helpers — the only module that touches the live system.

Mirrors bash ``pick_unit_scope`` / ``run_scoped_systemctl`` / ``unit_load_state``
(lines 129-171). In observe-only mode, ``set_property`` and ``restart_unit``
return what they WOULD have done instead of invoking systemctl.

Note: the bash sentinel does not itself call ``systemctl set-property``; that
helper is reserved for the pressure-watchdog companion (Phase L). It is
provided here as the single home for any future cgroup-property writes so
the rest of the package stays side-effect free.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


def notify_user() -> str:
    return os.environ.get("SINNIX_NOTIFY_USER", "")


def _user_manager_args() -> List[str]:
    user = notify_user()
    if not user:
        return []
    return [f"--machine={user}@.host", "--user"]


def run_scoped_systemctl(
    scope: str,
    *args: str,
    check: bool = False,
) -> subprocess.CompletedProcess:
    cmd = ["systemctl"]
    if scope == "user":
        cmd.extend(_user_manager_args())
    cmd.extend(args)
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def unit_load_state(scope: str, unit: str) -> str:
    try:
        result = run_scoped_systemctl(
            scope,
            "show",
            unit,
            "--property=LoadState",
            "--value",
        )
        return (result.stdout or "").strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""


def pick_unit_scope(unit_type: str, unit: str) -> str:
    """Decide whether to talk to the user or system manager (lines 150-171)."""

    user_args = _user_manager_args()
    if unit_type == "user" and user_args:
        return "user"

    if unit_type == "timer" and user_args:
        if unit_load_state("system", unit) == "loaded":
            return "system"
        if unit_load_state("user", unit) == "loaded":
            return "user"

    return "system"


def show_property(scope: str, unit: str, prop: str) -> str:
    try:
        result = run_scoped_systemctl(
            scope,
            "show",
            unit,
            f"--property={prop}",
            "--value",
        )
        return (result.stdout or "").strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""


def is_enabled(scope: str, unit: str) -> bool:
    try:
        result = run_scoped_systemctl(scope, "is-enabled", unit)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def is_active(scope: str, unit: str) -> bool:
    try:
        result = run_scoped_systemctl(scope, "is-active", unit)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


@dataclass
class IntendedAction:
    """A side effect that was suppressed because observe-only is on."""

    kind: str  # "restart" | "start" | "set-property"
    scope: str
    unit: str
    args: Tuple[str, ...] = ()


def restart_unit(
    scope: str,
    unit: str,
    *,
    observe_only: bool,
) -> Tuple[bool, Optional[IntendedAction]]:
    """Restart ``unit``. Returns (succeeded, intended_action_if_observed)."""

    if observe_only:
        return True, IntendedAction(kind="restart", scope=scope, unit=unit)
    try:
        result = run_scoped_systemctl(scope, "restart", unit)
        return result.returncode == 0, None
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False, None


def start_unit(
    scope: str,
    unit: str,
    *,
    observe_only: bool,
) -> Tuple[bool, Optional[IntendedAction]]:
    if observe_only:
        return True, IntendedAction(kind="start", scope=scope, unit=unit)
    try:
        result = run_scoped_systemctl(scope, "start", unit)
        return result.returncode == 0, None
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False, None


def set_property(
    scope: str,
    unit: str,
    properties: List[str],
    *,
    observe_only: bool,
) -> Tuple[bool, Optional[IntendedAction]]:
    """Reserved for the pressure-watchdog port (Phase L)."""

    if observe_only:
        return True, IntendedAction(
            kind="set-property",
            scope=scope,
            unit=unit,
            args=tuple(properties),
        )
    try:
        result = run_scoped_systemctl(scope, "set-property", unit, *properties)
        return result.returncode == 0, None
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False, None
