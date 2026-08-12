import json

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
