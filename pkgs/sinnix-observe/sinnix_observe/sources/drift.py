"""Read the latest bounded configuration drift report."""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from typing import Any

REPORT = Path("/realm/device/sinnix-prime/config-drift.jsonl")
# The producer runs every five minutes. Three missed intervals make the
# snapshot stale while allowing ordinary timer scheduling and brief load.
MAX_REPORT_AGE_SECONDS = 15 * 60


def collect_config_drift(path: Path = REPORT) -> dict[str, Any]:
    try:
        # Open first so permission errors keep their cause and a replaced path
        # cannot supply metadata for different bytes. Never block on a FIFO.
        with open(path, encoding="utf-8", opener=lambda name, flags: os.open(name, flags | os.O_NONBLOCK)) as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("report is not a regular file")
            modified_at = info.st_mtime
            rows = [json.loads(line) for line in handle if line.strip()]
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("report rows must be JSON objects")
    except (OSError, ValueError) as error:
        return {
            "available": False,
            "status": "unavailable",
            "reason": "report missing" if isinstance(error, FileNotFoundError) else str(error),
            "rows": [],
        }
    age_seconds = max(0, int(time.time() - modified_at))
    drifted = [row for row in rows if row.get("match") is False]
    unavailable = [row for row in rows if row.get("status") == "unavailable"]
    if age_seconds > MAX_REPORT_AGE_SECONDS:
        status = "stale"
    elif not rows or (
        not drifted
        and not unavailable
        and not any(row.get("match") is True for row in rows)
    ):
        status = "degraded"
    else:
        status = "drifted" if drifted else "degraded" if unavailable else "healthy"
    return {
        "available": True,
        "status": status,
        "age_seconds": age_seconds,
        "row_count": len(rows),
        "drift_count": len(drifted),
        "unavailable_count": len(unavailable),
        **({"reason": "report has no check rows"} if not rows else {}),
        "rows": rows,
    }
