import datetime as dt
from fractions import Fraction

import pytest
from sinnix_fs.forecast import project

NOW = 1800000000


def fixture_rows():
    return [
        {
            "id": index + 1,
            "segment_id": "fixture",
            "host": "host",
            "path": "/fixture",
            "observed_at": dt.datetime.fromtimestamp(
                NOW - 30 * 86400 + index * 300, dt.timezone.utc
            ).isoformat(),
            "status": "observed",
            "filesystem_uuid": "uuid",
            "filesystem_type": "btrfs",
            "mount_root": "/",
            "f_blocks": 2**53 + 17,
            "f_frsize": 4096,
            "f_bavail": 2**52 - index,
        }
        for index in range(30 * 288 + 1)
    ]


def test_exact_thirty_day_projection_preserves_integer_precision():
    rows = fixture_rows()
    result = project(rows, rows[-1], now=NOW)
    assert result["status"] == "projected"
    assert result["consumed_bytes"] == 8640 * 4096
    projected = Fraction(
        result["projected_available_bytes"]["numerator"],
        result["projected_available_bytes"]["denominator"],
    )
    assert projected == (2**52 - 2 * 8640) * 4096


@pytest.mark.parametrize(
    "field,value", [("filesystem_uuid", None), ("f_bavail", 1.5), ("mount_root", None)]
)
def test_missing_exact_identity_cannot_forecast(field, value):
    rows = fixture_rows()
    current = {**rows[-1], field: value}
    assert project(rows, current, now=NOW)["status"] == "incomparable_history"


@pytest.mark.parametrize(
    "field,value",
    [
        ("filesystem_uuid", "replacement"),
        ("f_blocks", 2**53 + 18),
        ("mount_root", "/different"),
    ],
)
def test_identity_or_capacity_change_splits_history(field, value):
    rows = fixture_rows()
    rows[-1][field] = value
    result = project(rows, rows[-1], now=NOW)
    assert result["status"] == "insufficient_history" and result["sample_count"] == 1


def test_stale_gap_short_and_failure_states():
    rows = fixture_rows()
    assert project(rows, rows[-1], now=NOW + 901)["status"] == "stale"
    assert (
        project(rows[:-10] + rows[-1:], rows[-1], now=NOW)["status"] == "gapped_history"
    )
    assert project(rows[-2:], rows[-1], now=NOW)["status"] == "insufficient_history"
    rows[-2]["status"] = "unavailable"
    assert project(rows, rows[-1], now=NOW)["sample_count"] == 1


def test_cleanup_does_not_cancel_observed_consumption():
    rows = fixture_rows()
    rows[4000]["f_bavail"] += 1000000
    result = project(rows, rows[-1], now=NOW)
    assert result["status"] == "projected"
    assert result["consumed_bytes"] > 8640 * 4096


def test_forecast_surface_reports_exact_thresholds_and_old_coverage(monkeypatch):
    from pathlib import Path

    from sinnix_fs import forecast as module

    rows = fixture_rows()
    for row in rows:
        row["f_bavail"] = 0
    monkeypatch.setattr(
        module,
        "read_history",
        lambda *a: {
            "rows": rows,
            "generation": "fixture-generation",
            "pre_feature_segments": ["legacy"],
        },
    )
    monkeypatch.setattr(module, "observe_capacity", lambda path: dict(rows[-1]))
    monkeypatch.setattr(
        module.os, "uname", lambda: type("Host", (), {"nodename": "host"})()
    )
    result = module.forecast(
        [(Path("/fixture"), 15, 10)],
        now=dt.datetime.fromtimestamp(NOW, dt.timezone.utc),
    )
    projection = result["volumes"][0]["forecast"]
    assert projection["status"] == "projected"
    assert projection["thresholds"]["defer"]["seconds_until_crossing"] == {
        "numerator": 0,
        "denominator": 1,
    }
    assert result["pre_feature_segments"] == ["legacy"]
