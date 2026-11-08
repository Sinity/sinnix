"""Compare the booted system generation with the current one."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BOOTED = Path("/run/booted-system")
CURRENT = Path("/run/current-system")
# Parts of a generation that only take effect at boot.
BOOT_PARTS = ("kernel", "initrd", "kernel-modules")


def collect_system_generation(
    booted: Path = BOOTED, current: Path = CURRENT
) -> dict[str, Any]:
    """Report whether the running system needs a reboot to match the current generation."""
    try:
        booted_target = os.path.realpath(booted, strict=True)
        current_target = os.path.realpath(current, strict=True)
    except OSError as error:
        return {"available": False, "status": "unavailable", "reason": str(error)}
    changed = [
        part
        for part in BOOT_PARTS
        if (booted / part).exists() or (current / part).exists()
        if os.path.realpath(booted / part) != os.path.realpath(current / part)
    ]
    return {
        "available": True,
        "status": "reboot_required" if changed else "healthy",
        "booted": booted_target,
        "current": current_target,
        "boot_parts_changed": changed,
    }
