"""Notification queue and dispatch (mirror of bash ``queue_notification`` / ``send_notification``).

In observe-only mode, ``dispatch`` records what would have been sent and
returns without invoking ``notify-send``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List


@dataclass
class Notification:
    urgency: str  # "normal" | "warning" | "critical"
    message: str


@dataclass
class NotificationQueue:
    items: List[Notification] = field(default_factory=list)

    def push(self, urgency: str, message: str) -> None:
        self.items.append(Notification(urgency=urgency, message=message))

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


def send_notification(urgency: str, message: str) -> None:
    """Dispatch via notify-send, optionally via runuser to the desktop user.

    Mirrors bash lines 99-119. Best-effort; silent on failure.
    """

    if shutil.which("notify-send") is None:
        return

    notify_user = os.environ.get("SINNIX_NOTIFY_USER", "")
    if notify_user:
        try:
            uid = subprocess.run(
                ["id", "-u", notify_user],
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            uid = ""
        bus_socket = f"/run/user/{uid}/bus" if uid else ""
        if (
            uid
            and bus_socket
            and os.path.exists(bus_socket)
            and shutil.which("runuser")
        ):
            subprocess.run(
                [
                    "runuser",
                    "-u",
                    notify_user,
                    "--",
                    "env",
                    f"DBUS_SESSION_BUS_ADDRESS=unix:path={bus_socket}",
                    f"XDG_RUNTIME_DIR=/run/user/{uid}",
                    "notify-send",
                    f"--urgency={urgency}",
                    "sinnix sentinel",
                    message,
                ],
                check=False,
                capture_output=True,
            )
            return

    subprocess.run(
        ["notify-send", f"--urgency={urgency}", "sinnix sentinel", message],
        check=False,
        capture_output=True,
    )


def dispatch(
    queue: NotificationQueue,
    *,
    enabled: bool,
    observe_only: bool,
) -> List[Notification]:
    """Send queued notifications unless observe-only.

    Returns the list of notifications that would have been (or were) sent,
    so the caller can log them.
    """

    if not enabled:
        return []
    if observe_only:
        return list(queue.items)
    for notif in queue.items:
        send_notification(notif.urgency, notif.message)
    return list(queue.items)
