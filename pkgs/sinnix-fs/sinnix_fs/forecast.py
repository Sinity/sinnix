"""Conservative thirty-day projections from exact, identity-bearing observations."""

from __future__ import annotations

import datetime as dt
import os
import sqlite3
from fractions import Fraction
from pathlib import Path

from machine_telemetry.capacity import read_history
from sinnix_lib.mounts import observe_capacity

HORIZON_SECONDS = 30 * 86400
MIN_SPAN_SECONDS = 30 * 86400
MAX_GAP_SECONDS = 1800
MAX_AGE_SECONDS = 900
DATABASE = Path("/realm/state/machine-telemetry/telemetry.sqlite")


def timestamp(value):
    stamp = dt.datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("capacity timestamp lacks timezone")
    return int(stamp.timestamp())


def series_identity(row):
    if row.get("status") != "observed" or not row.get("filesystem_uuid"):
        return None
    for field in ("f_blocks", "f_frsize", "f_bavail"):
        if type(row.get(field)) is not int or row[field] < 0:
            return None
    if not row["f_blocks"] or not row["f_frsize"] or not row.get("mount_root"):
        return None
    return (
        row.get("host"),
        row.get("path"),
        row["filesystem_uuid"],
        row["mount_root"],
        row.get("filesystem_type"),
        row["f_blocks"],
        row["f_frsize"],
    )


def project(rows, current, *, now):
    """Sum consumption between observations; cleanup increases never cancel growth."""
    result = {
        "horizon_seconds": HORIZON_SECONDS,
        "minimum_observation_span_seconds": MIN_SPAN_SECONDS,
        "maximum_gap_seconds": MAX_GAP_SECONDS,
        "maximum_age_seconds": MAX_AGE_SECONDS,
        "method": "sum of positive available-byte decreases divided by observed span",
    }
    key = series_identity(current)
    if key is None:
        return {
            **result,
            "status": "incomparable_history",
            "reason": "current exact identity unavailable",
        }
    usable = []
    for row in sorted(rows, key=lambda row: (timestamp(row["observed_at"]), row["id"])):
        if row.get("path") != current["path"] or row.get("host") != current["host"]:
            continue
        if series_identity(row) != key:
            usable = []
            continue
        usable.append(row)
    if not usable:
        return {**result, "status": "insufficient_history", "sample_count": 0}
    times = [timestamp(row["observed_at"]) for row in usable]
    span = times[-1] - times[0]
    gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
    result.update(
        sample_count=len(usable),
        observation_span_seconds=span,
        first_observed_at=usable[0]["observed_at"],
        last_observed_at=usable[-1]["observed_at"],
        maximum_observed_gap_seconds=max(gaps, default=0),
        selected_rows=[
            {"segment_id": row["segment_id"], "id": row["id"]} for row in usable
        ],
    )
    age = now - times[-1]
    if age < 0 or age > MAX_AGE_SECONDS:
        return {**result, "status": "stale", "age_seconds": age}
    if any(gap <= 0 or gap > MAX_GAP_SECONDS for gap in gaps):
        return {**result, "status": "gapped_history"}
    if span < MIN_SPAN_SECONDS:
        return {**result, "status": "insufficient_history"}
    available = [row["f_bavail"] * row["f_frsize"] for row in usable]
    consumed = sum(
        max(a - b, 0) for a, b in zip(available, available[1:], strict=False)
    )
    rate = Fraction(consumed, span)
    current_available = current["f_bavail"] * current["f_frsize"]
    projected = Fraction(current_available) - rate * HORIZON_SECONDS
    result.update(
        status="projected",
        consumed_bytes=consumed,
        current_available_bytes=current_available,
        consumption_bytes_per_second={
            "numerator": rate.numerator,
            "denominator": rate.denominator,
        },
        projected_available_bytes={
            "numerator": projected.numerator,
            "denominator": projected.denominator,
        },
        assumption="observed consumption continues; cleanup and future workloads can change the outcome",
    )
    return result


def forecast(volumes, *, database=DATABASE, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        history = read_history(
            database, (now - dt.timedelta(days=35)).date().isoformat()
        )
        output = []
        for path, target, floor in volumes:
            current = observe_capacity(path)
            current["host"] = os.uname().nodename
            projection = project(history["rows"], current, now=int(now.timestamp()))
            if projection["status"] == "projected":
                rate_value = projection["consumption_bytes_per_second"]
                rate = Fraction(rate_value["numerator"], rate_value["denominator"])
                total = current["f_blocks"] * current["f_frsize"]
                thresholds = {}
                for name, percent in (("target", target), ("defer", floor)):
                    remaining = Fraction(
                        projection["current_available_bytes"]
                    ) - Fraction(total * percent, 100)
                    crossing = (
                        Fraction(0)
                        if remaining <= 0
                        else remaining / rate
                        if rate
                        else None
                    )
                    thresholds[name] = {
                        "percent": percent,
                        "seconds_until_crossing": {
                            "numerator": crossing.numerator,
                            "denominator": crossing.denominator,
                        }
                        if crossing is not None
                        else None,
                    }
                projection["thresholds"] = thresholds
            output.append(
                {"path": str(path), "current": current, "forecast": projection}
            )
        return {
            "schema": "sinnix.capacity-forecast.v1",
            "volumes": output,
            "history_generation": history["generation"],
            "pre_feature_segments": history["pre_feature_segments"],
        }
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        return {
            "schema": "sinnix.capacity-forecast.v1",
            "status": "unavailable",
            "reason": str(error),
        }
