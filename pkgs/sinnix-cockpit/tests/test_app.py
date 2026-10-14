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
    client = TestClient(app, base_url="http://127.0.0.1:8791")
    resp = client.get("/today")
    assert resp.status_code == 200
    assert "ship the walking skeleton" in resp.text
    assert "70%" in resp.text
    assert "past thing" not in resp.text  # closed, not open


def test_activities_renders_registry(seeded_store):
    client = TestClient(app, base_url="http://127.0.0.1:8791")
    resp = client.get("/activities")
    assert resp.status_code == 200
    assert "deep work block" in resp.text
    assert "good" in resp.text


def test_calibration_renders_bucket_for_closed_forecasted_commitment(seeded_store):
    client = TestClient(app, base_url="http://127.0.0.1:8791")
    resp = client.get("/calibration")
    assert resp.status_code == 200
    assert "41-60%" in resp.text  # c2's 0.5 forecast falls in this bucket
    assert "100%" in resp.text  # c2 was done -> 1/1 actual rate


def test_today_handles_missing_store_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "store_path", lambda: tmp_path / "does-not-exist.sqlite")
    client = TestClient(app, base_url="http://127.0.0.1:8791")
    resp = client.get("/today")
    assert resp.status_code == 200
    assert "not yet initialized" in resp.text


@pytest.mark.parametrize("headers", [
    {"Host": "rebound.example.invalid:8791"},
    {"Host": "127.0.0.1:80"},
    {"Host": "user@127.0.0.1:8791"},
    {"Host": "127.0.0.1:8791/path"},
    {"Origin": "https://example.invalid"},
    {"Origin": "null"},
    {"Origin": ""},
    {"Origin": "http://127.0.0.1:80"},
    {"Origin": "http://127.0.0.1:8791/"},
    {"Origin": "http://user@127.0.0.1:8791"},
    {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-site"},
    {"Sec-Fetch-Mode": "cors"},
    [("Origin", "http://127.0.0.1:8791"), ("Origin", "https://example.invalid")],
    [("Host", "127.0.0.1:8791"), ("Host", "rebound.example.invalid:8791")],
])
def test_browser_refusal_precedes_private_store_access(monkeypatch, headers):
    def forbidden():
        pytest.fail("refused request reached private store")
    monkeypatch.setattr(store, "get_db", forbidden)
    client = TestClient(app, base_url="http://127.0.0.1:8791")
    response = client.get("/today", headers=headers)
    assert response.status_code == 403
    assert response.headers["connection"] == "close"
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("headers", [
    {},
    {"Origin": "http://127.0.0.1:8791", "Sec-Fetch-Site": "same-origin"},
    {"Sec-Fetch-Site": "none"},
    {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate",
     "Sec-Fetch-Dest": "document", "Sec-Fetch-User": "?1"},
])
def test_native_same_origin_and_deliberate_navigation_work(seeded_store, headers):
    client = TestClient(app, base_url="http://127.0.0.1:8791")
    assert client.get("/today", headers=headers).status_code == 200


def test_cli_custom_listener_defines_the_boundary(monkeypatch):
    import sys
    import uvicorn
    from sinnix_cockpit.cli import main
    monkeypatch.setattr(app.state, "listen_host", app.state.listen_host)
    monkeypatch.setattr(app.state, "listen_port", app.state.listen_port)
    monkeypatch.setattr(sys, "argv", ["sinnix-cockpit", "--host", "localhost", "--port", "9876"])
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))
    main()
    assert calls[0]["host"] == "localhost" and calls[0]["port"] == 9876
    client = TestClient(app, base_url="http://localhost:9876")
    assert client.get("/", headers={"Origin": "http://localhost:9876"}).status_code == 200
    assert client.get("/", headers={"Host": "localhost:8791"}).status_code == 403


def test_store_filename_is_encoded_in_read_only_uri(seeded_store, monkeypatch):
    target = seeded_store.with_name("steering #?%.sqlite")
    seeded_store.rename(target)
    monkeypatch.setattr(store, "store_path", lambda: target)
    client = TestClient(app, base_url="http://127.0.0.1:8791")
    assert "ship the walking skeleton" in client.get("/today").text


@pytest.mark.parametrize("route", ["/today", "/activities", "/calibration"])
@pytest.mark.parametrize("failure", [PermissionError("denied"), sqlite3.OperationalError("locked")])
def test_unavailable_store_is_not_reported_as_uninitialized(monkeypatch, route, failure):
    def unavailable():
        raise failure
    monkeypatch.setattr(store, "get_db", unavailable)
    response = TestClient(app, base_url="http://127.0.0.1:8791").get(route)
    assert response.status_code == 503
    assert "store unavailable" in response.text
    assert "not yet initialized" not in response.text


def test_activity_fields_remain_text(seeded_store):
    hostile = '<img src=x onerror="alert(1)">'
    with sqlite3.connect(seeded_store) as conn:
        conn.execute("UPDATE activities SET kind=?, energy_tier=?, est_minutes=?", (hostile, hostile, hostile))
    response = TestClient(app, base_url="http://127.0.0.1:8791").get("/activities")
    assert hostile not in response.text
    assert response.text.count("&lt;img") == 3


@pytest.mark.parametrize("kind", ["directory", "broken-link", "invalid-database"])
def test_present_unusable_store_is_unavailable(tmp_path, monkeypatch, kind):
    target = tmp_path / "steering.sqlite"
    if kind == "directory":
        target.mkdir()
    elif kind == "broken-link":
        target.symlink_to(tmp_path / "missing-target")
    else:
        target.write_bytes(b"not a SQLite database")
    monkeypatch.setattr(store, "store_path", lambda: target)
    response = TestClient(app, base_url="http://127.0.0.1:8791").get("/today")
    assert response.status_code == 503
    assert "not yet initialized" not in response.text


@pytest.mark.parametrize("route", ["/today", "/activities", "/calibration"])
def test_failed_query_closes_its_read_connection(monkeypatch, route):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    monkeypatch.setattr(store, "get_db", lambda: conn)
    response = TestClient(app, base_url="http://127.0.0.1:8791").get(route)
    assert response.status_code == 503
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
