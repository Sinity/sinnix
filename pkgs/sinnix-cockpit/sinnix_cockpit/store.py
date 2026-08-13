"""Read-only access to the steering sqlite store.

Schema is the same v1 defined in scripts/sinnix-steer. Duplicated here
rather than imported because sinnix-steer is a separate frontmatter-packaged
script (no `.py` suffix, not importable as
a normal module from a different Nix derivation) — this module only ever
SELECTs, never CREATEs or writes, so schema drift would show up immediately
as a missing-column error rather than silent corruption.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def store_path() -> Path:
    state_dir = Path(os.environ.get("SINNIX_STEERING_STATE_DIR", "/realm/state/steering"))
    return state_dir / "steering.sqlite"


def get_db() -> sqlite3.Connection:
    path = store_path()
    # Read-only: if the store doesn't exist yet (sinnix-steer never ran),
    # connect in read-only mode against a file URI so sqlite doesn't silently
    # create an empty (schema-less) database out from under the CLI.
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def open_commitments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM commitments WHERE status = 'open' ORDER BY created_at DESC"
    ).fetchall()


def activities(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM activities ORDER BY kind, name").fetchall()


def calibration_buckets(conn: sqlite3.Connection) -> list[dict]:
    """Forecast-vs-outcome calibration, bucketed in 20-point-wide forecast bins.

    Only over closed commitments (done/missed) that carried a forecast_p —
    open commitments have no outcome yet and can't inform calibration.
    """
    rows = conn.execute(
        "SELECT forecast_p, status FROM commitments "
        "WHERE status IN ('done', 'missed') AND forecast_p IS NOT NULL"
    ).fetchall()
    buckets = [
        {"label": f"{lo}-{hi}%", "lo": lo, "hi": hi, "n": 0, "done": 0}
        for lo, hi in [(0, 20), (21, 40), (41, 60), (61, 80), (81, 100)]
    ]
    for row in rows:
        pct = row["forecast_p"] * 100
        for bucket in buckets:
            if bucket["lo"] <= pct <= bucket["hi"]:
                bucket["n"] += 1
                if row["status"] == "done":
                    bucket["done"] += 1
                break
    for bucket in buckets:
        bucket["actual_rate"] = (bucket["done"] / bucket["n"]) if bucket["n"] else None
    return buckets
