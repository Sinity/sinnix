from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from sinnix_cockpit import store
from sinnix_cockpit.app import app

SCHEMA = """
CREATE TABLE commitments (
    id TEXT PRIMARY KEY, text TEXT NOT NULL, created_at TEXT NOT NULL,
    window_start TEXT, window_end TEXT, forecast_p REAL,
    status TEXT NOT NULL, outcome_at TEXT, outcome_note TEXT,
    activity_id TEXT, review_id TEXT
);
CREATE TABLE activities (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
    est_minutes INTEGER, energy_tier TEXT NOT NULL, standing_notes TEXT,
    hypothesis TEXT, prereg_prediction TEXT, metric_ref TEXT, experiment_status TEXT
);
CREATE TABLE reviews (
    id TEXT PRIMARY KEY, ts TEXT NOT NULL, window TEXT NOT NULL,
    generated_summary TEXT, operator_notes TEXT
);
"""


@pytest.fixture()
def seeded_store(tmp_path, monkeypatch):
    db_path = tmp_path / "steering.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO commitments (id, text, created_at, forecast_p, status) "
        "VALUES ('c1', 'ship the walking skeleton', '2026-08-13T08:00:00', 0.7, 'open')"
    )
    conn.execute(
        "INSERT INTO commitments (id, text, created_at, forecast_p, status, outcome_at) "
        "VALUES ('c2', 'past thing', '2026-08-01T08:00:00', 0.5, 'done', '2026-08-01T20:00:00')"
    )
    conn.execute(
        "INSERT INTO activities (id, name, kind, est_minutes, energy_tier) "
        "VALUES ('a1', 'deep work block', 'task', 90, 'good')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(store, "store_path", lambda: db_path)
    return db_path


def test_today_renders_open_commitment_with_forecast(seeded_store):
    client = TestClient(app)
    resp = client.get("/today")
    assert resp.status_code == 200
    assert "ship the walking skeleton" in resp.text
    assert "70%" in resp.text
    assert "past thing" not in resp.text  # closed, not open


def test_activities_renders_registry(seeded_store):
    client = TestClient(app)
    resp = client.get("/activities")
    assert resp.status_code == 200
    assert "deep work block" in resp.text
    assert "good" in resp.text


def test_calibration_renders_bucket_for_closed_forecasted_commitment(seeded_store):
    client = TestClient(app)
    resp = client.get("/calibration")
    assert resp.status_code == 200
    assert "41-60%" in resp.text  # c2's 0.5 forecast falls in this bucket
    assert "100%" in resp.text  # c2 was done -> 1/1 actual rate


def test_today_handles_missing_store_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "store_path", lambda: tmp_path / "does-not-exist.sqlite")
    client = TestClient(app)
    resp = client.get("/today")
    assert resp.status_code == 200
    assert "not yet initialized" in resp.text
