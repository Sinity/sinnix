"""Read the latest bounded configuration drift report."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

REPORT = Path("/realm/machine/config-drift.jsonl")
# The producer runs every five minutes. Three missed intervals make the
# snapshot stale while allowing ordinary timer scheduling and brief load.
MAX_REPORT_AGE_SECONDS = 15 * 60


def collect_config_drift(path: Path = REPORT) -> dict[str, Any]:
    if not path.is_file():
        return {
            "available": False,
            "status": "unavailable",
            "reason": "report missing",
            "rows": [],
        }
    try:
        modified_at = path.stat().st_mtime
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as error:
        return {
            "available": False,
            "status": "unavailable",
            "reason": str(error),
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
