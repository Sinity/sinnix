import json
import time

from sinnix_ops_reducer.ambient import product_source


def test_product_source_accepts_current_product(tmp_path):
    path = tmp_path / "ambient.json"
    path.write_text(
        json.dumps(
            {"schema": "lynchpin-ambient-intelligence-v1", "logical_date": "2026-08-07"}
        )
    )
    assert product_source(path)()["logical_date"] == "2026-08-07"


def test_product_source_reports_stale_product(tmp_path):
    path = tmp_path / "ambient.json"
    path.write_text(json.dumps({"schema": "lynchpin-ambient-intelligence-v1"}))
    old = time.time() - 100
    import os

    os.utime(path, (old, old))
    try:
        product_source(path, max_age_seconds=1)()
    except RuntimeError as error:
        assert "stale" in str(error)
    else:
        raise AssertionError("stale product was accepted")
