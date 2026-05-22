"""Mount/discard/iostat collector."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any

from ..util import read_text, run_cmd
from .systemd import systemctl_show


def collect_storage(offline: bool) -> dict[str, Any]:
    if offline:
        return {"offline": True, "mounts": [], "discard_queues": []}
    mounts = []
    paths = [
        "/",
        "/nix",
        "/persist",
        "/cache",
        "/realm",
        "/realm/data/captures/sinex",
        "/var/lib/postgresql",
        "/var/lib/sinex",
        str(Path.home() / ".local/share/polylogue"),
    ]
    for path in paths:
        proc = run_cmd(
            ["findmnt", "-T", path, "-n", "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"]
        )
        if proc and proc.stdout.strip():
            parts = proc.stdout.strip().split(None, 3)
            mounts.append(
                {
                    "path": path,
                    "target": parts[0] if len(parts) > 0 else None,
                    "source": parts[1] if len(parts) > 1 else None,
                    "fstype": parts[2] if len(parts) > 2 else None,
                    "options": parts[3] if len(parts) > 3 else None,
                }
            )
        else:
            mounts.append({"path": path, "unresolved": True})

    queues = []
    for pattern in ("/sys/block/nvme*n1", "/sys/block/sd*"):
        for dev in sorted(glob.glob(pattern)):
            queue = Path(dev) / "queue"
            queues.append(
                {
                    "device": Path(dev).name,
                    "discard_max_bytes": read_text(queue / "discard_max_bytes"),
                    "discard_granularity": read_text(queue / "discard_granularity"),
                    "rotational": read_text(queue / "rotational"),
                    "scheduler": read_text(queue / "scheduler"),
                    "wbt_lat_usec": read_text(queue / "wbt_lat_usec"),
                }
            )

    iostat = ""
    if os.environ.get("SINNIX_OBSERVE_IOSTAT", "1") != "0":
        proc = run_cmd(["iostat", "-xz", "1", "2"], timeout=4)
        iostat = proc.stdout if proc else ""

    return {
        "fstrim_timer": systemctl_show("fstrim.timer"),
        "fstrim_service": systemctl_show("fstrim.service"),
        "mounts": mounts,
        "discard_queues": queues,
        "iostat_xz": iostat,
    }
