"""Read the latest bounded configuration drift report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPORT = Path("/realm/data/machine/config-drift.jsonl")


def collect_config_drift(path: Path = REPORT) -> dict[str, Any]:
    if not path.is_file():
        return {
            "available": False,
            "status": "unavailable",
            "reason": "report missing",
            "rows": [],
        }
    try:
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
    drifted = [row for row in rows if row.get("match") is False]
    unavailable = [row for row in rows if row.get("status") == "unavailable"]
    status = "drifted" if drifted else "degraded" if unavailable else "healthy"
    return {
        "available": True,
        "status": status,
        "row_count": len(rows),
        "drift_count": len(drifted),
        "unavailable_count": len(unavailable),
        "rows": rows,
    }
