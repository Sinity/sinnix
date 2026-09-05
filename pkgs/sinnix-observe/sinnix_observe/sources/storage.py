"""Mount/discard/iostat collector."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any

from sinnix_lib.process import run
from sinnix_lib.values import read_text

from ..runtime_inventory import polylogue_archive
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
        "/var/lib/postgresql",
        "/var/lib/sinex",
        str(polylogue_archive().get("archiveRoot", "")),
    ]
    for path in paths:
        result = run(
            ["findmnt", "-T", path, "-n", "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"],
            timeout=5,
        )
        if result.stdout.strip():
            parts = result.stdout.strip().split(None, 3)
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
        iostat = run(["iostat", "-xz", "1", "2"], timeout=4).stdout

    return {
        "fstrim_timer": systemctl_show("fstrim.timer"),
        "fstrim_service": systemctl_show("fstrim.service"),
        "mounts": mounts,
        "discard_queues": queues,
        "iostat_xz": iostat,
    }
