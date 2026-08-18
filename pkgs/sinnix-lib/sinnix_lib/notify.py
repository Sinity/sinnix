"""Desktop notification across live graphical sessions.

Four scripts hand-rolled the "does notify-send exist, which bus do I speak
to" dance; system-manager callers additionally need the sudo/session-bus
bridge the health sentinel carried. One implementation, both cases.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

USER_BUS_ROOT = Path("/run/user")


def notify_desktop(
    title: str,
    body: str,
    *,
    urgency: str = "normal",
    app_name: str = "sinnix",
    user_bus_root: Path = USER_BUS_ROOT,
) -> bool:
    """Best-effort desktop notification; True when at least one delivery
    succeeded. Never raises — notification is advisory by definition.
    """
    exe = shutil.which("notify-send")
    if exe is None:
        return False
    args = [exe, f"--urgency={urgency}", f"--app-name={app_name}", title, body]
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return subprocess.run(args, check=False, capture_output=True).returncode == 0
    delivered = False
    for bus in sorted(user_bus_root.glob("*/bus")):
        uid = bus.parent.name
        if uid == "0" or not bus.is_socket():
            continue
        env = dict(
            os.environ,
            DBUS_SESSION_BUS_ADDRESS=f"unix:path={bus}",
            XDG_RUNTIME_DIR=str(bus.parent),
        )
        cmd = args
        if os.geteuid() == 0:
            cmd = [
                "sudo",
                "-u",
                f"#{uid}",
                "--preserve-env=DBUS_SESSION_BUS_ADDRESS,XDG_RUNTIME_DIR",
                *args,
            ]
        if (
            subprocess.run(cmd, check=False, capture_output=True, env=env).returncode
            == 0
        ):
            delivered = True
    return delivered
