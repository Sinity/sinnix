import json
import os
import time

from sinnix_observe.sources.drift import collect_config_drift


def test_drift_source_preserves_unavailable_and_drifted_rows(tmp_path):
    path = tmp_path / "config-drift.jsonl"
    path.write_text(
        json.dumps(
            {"check": "sysctl:vm.swappiness", "match": False, "status": "drifted"}
        )
        + "\n"
        + json.dumps({"check": "zram", "match": None, "status": "unavailable"})
        + "\n"
    )
    report = collect_config_drift(path)
    assert report["status"] == "drifted"
    assert report["drift_count"] == 1
    assert report["unavailable_count"] == 1


def test_empty_snapshot_is_degraded(tmp_path):
    path = tmp_path / "config-drift.jsonl"
    path.write_text("")

    report = collect_config_drift(path)

    assert report["available"] is True
    assert report["status"] == "degraded"
    assert report["row_count"] == 0
    assert report["reason"] == "report has no check rows"


def test_old_snapshot_is_stale_even_when_all_checks_matched(tmp_path):
    path = tmp_path / "config-drift.jsonl"
    path.write_text(
        json.dumps(
            {"check": "sysctl:vm.swappiness", "match": True, "status": "matched"}
        )
        + "\n"
    )
    old = time.time() - 16 * 60
    os.utime(path, (old, old))

    report = collect_config_drift(path)

    assert report["status"] == "stale"
    assert report["row_count"] == 1
    assert report["age_seconds"] >= 16 * 60


def test_fresh_positive_snapshot_can_be_healthy(tmp_path):
    path = tmp_path / "config-drift.jsonl"
    path.write_text(
        json.dumps(
            {"check": "sysctl:vm.swappiness", "match": True, "status": "matched"}
        )
        + "\n"
    )

    report = collect_config_drift(path)

    assert report["status"] == "healthy"
    assert report["row_count"] == 1
