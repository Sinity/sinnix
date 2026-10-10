"""Mount/discard/iostat collector."""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any

from sinnix_lib.process import run
from sinnix_lib.values import read_text

from ..runtime_inventory import monitored_mount_paths, polylogue_archive
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
    paths.extend(monitored_mount_paths())
    for path in dict.fromkeys(path for path in paths if path):
        result = run(
            # A mounted filesystem can cover an autofs entrance. The reverse
            # search selects the visible top mount and emits exactly one row.
            ["findmnt", "-T", path, "-d", "backward", "-f", "-J", "-o",
             "TARGET,SOURCE,FSTYPE,OPTIONS"],
            timeout=5,
        )
        row = None
        if result.ok:
            try:
                document = json.loads(result.stdout)
            except json.JSONDecodeError:
                document = None
            entries = document.get("filesystems") if isinstance(document, dict) else None
            if isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict):
                candidate = entries[0]
                if (isinstance(candidate.get("target"), str)
                        and isinstance(candidate.get("fstype"), str)
                        and all(candidate.get(key) is None or isinstance(candidate[key], str)
                                for key in ("source", "options"))):
                    row = candidate
        if row is not None:
            mounts.append({"path": path, **{
                key: row.get(key) for key in ("target", "source", "fstype", "options")
            }})
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
