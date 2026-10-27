"""Desktop notifications across sessions and curated phone inbox notifications.

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


def notify_phone(title: str, body: str, *, key: str, window: int = 300) -> bool:
    """Queue a curated phone alarm once per key/window, without network IO.

    Dispatcher notify writes the existing durable inbox; the phone drains it
    later. Bound even the local command and never retry from the caller.
    """
    import hashlib
    import json
    import time

    from .atomic import atomic_publish
    from .lock import LockBusy, flock
    from .paths import runtime_dir, user_runtime_dir

    try:
        exe = shutil.which("sinnix-phone-dispatcher")
        if exe is None:
            return False
        command = [exe, "notify", title, body]
        if os.geteuid() == 0:
            # System OnFailure paths enqueue as the graphical session owner,
            # so the phone drain can read and remove the inbox files.
            buses = [
                bus
                for bus in sorted(USER_BUS_ROOT.glob("*/bus"))
                if bus.parent.name != "0" and bus.is_socket()
            ]
            if not buses:
                return False
            command = ["sudo", "-u", f"#{buses[0].parent.name}", "--", *command]
            root = runtime_dir() / "phone-notifications"
        else:
            root = user_runtime_dir() / "sinnix/phone-notifications"
        root.mkdir(parents=True, exist_ok=True)
        with flock(root / "lock", blocking=False):
            state = root / "recent.json"
            now = time.time()
            try:
                recent = json.loads(state.read_text())
            except (OSError, ValueError):
                recent = {}
            if not isinstance(recent, dict):
                recent = {}
            recent = {
                k: v
                for k, v in recent.items()
                if isinstance(v, (int, float)) and 0 <= now - v < window
            }
            token = hashlib.sha256(key.encode()).hexdigest()
            if token in recent:
                return False
            # Reserve before delivery, so an unavailable sink cannot cause a
            # burst of attempts. State contains hashes, never notification text.
            recent[token] = now
            atomic_publish(state, json.dumps(recent).encode(), fsync=False, mode=0o600)
            return (
                subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                ).returncode
                == 0
            )
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, LockBusy):
        return False
