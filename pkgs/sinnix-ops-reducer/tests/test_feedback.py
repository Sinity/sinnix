"""The annotation spool's file contract, and the elicit drain arrival triggers.

The spool file is read directly by agents and by `sinnix-elicit ingest`, so the
envelope shape is asserted against the exact JSON text that lands on disk, not
against a re-parsed dict.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from sinnix_ops_reducer.feedback import (
    CoalescingTrigger,
    FeedbackSpool,
    is_elicit,
    resolve_elicit_model,
)
from sinnix_ops_reducer.reducer import Reducer
from sinnix_ops_reducer.server import Handler


def test_spool_line_carries_the_v1_envelope(tmp_path: Path) -> None:
    spool = FeedbackSpool(tmp_path)
    result = spool.append({"note": "hello"}, "http://hub/reports/x.html", "curl/8")
    file = Path(result["file"])
    assert file.parent == tmp_path
    assert file.name.endswith(".jsonl") and len(file.name) == len("2026-08-18.jsonl")
    line = file.read_text(encoding="utf-8").splitlines()[0]
    record = json.loads(line)
    assert record["schema"] == "sinnix-hub-feedback-v1"
    assert record["sequence"] == 1
    assert record["page"] == "http://hub/reports/x.html"
    assert record["user_agent"] == "curl/8"
    assert record["payload"] == {"note": "hello"}
    assert record["received_at"].endswith("+00:00")
    # Key order and spacing are part of what agents grep for.
    assert line.startswith('{"page": "http://hub/reports/x.html", "payload": ')
    assert '"schema": "sinnix-hub-feedback-v1"' in line
    assert spool.append({"note": "again"}, None, None)["sequence"] == 2


def test_only_elicit_payloads_trigger_the_drain(tmp_path: Path) -> None:
    fired = threading.Event()

    class Recording(CoalescingTrigger):
        def _run(self) -> bool:
            fired.set()
            return True

    trigger = Recording(["true"], delay=0.05)
    spool = FeedbackSpool(tmp_path, elicit=trigger)
    spool.append({"schema": "report-annotations", "note": "x"}, None, None)
    assert not fired.wait(0.3)
    spool.append(
        {"schema": "sinnix-elicit-v1", "domain": "wallpaper", "a": "1", "b": "2"},
        None,
        None,
    )
    assert fired.wait(2.0)


def test_a_burst_of_judgments_coalesces_into_one_run(tmp_path: Path) -> None:
    runs = []

    class Counting(CoalescingTrigger):
        def _run(self) -> bool:
            runs.append(time.monotonic())
            return True

    # The delay has to outlast the burst itself -- ten fsync'd appends are not
    # instant -- which is exactly the property the production 5s buys against a
    # comparison session.
    trigger = Counting(["true"], delay=1.0)
    spool = FeedbackSpool(tmp_path, elicit=trigger)
    for index in range(10):
        spool.append(
            {"schema": "sinnix-elicit-v1", "domain": "d", "n": index}, None, None
        )
    time.sleep(2.5)
    assert len(runs) == 1


def test_is_elicit_ignores_non_objects() -> None:
    assert is_elicit({"schema": "sinnix-elicit-v1"})
    assert not is_elicit(["sinnix-elicit-v1"])
    assert not is_elicit(None)


def test_resolve_elicit_model_rejects_traversal_and_odd_charsets(
    tmp_path: Path,
) -> None:
    assert resolve_elicit_model(tmp_path, "wallpapers") == tmp_path / "wallpapers" / (
        "model.json"
    )
    assert resolve_elicit_model(tmp_path, "../etc") is None
    assert resolve_elicit_model(tmp_path, "a/b") is None
    assert resolve_elicit_model(tmp_path, "") is None
    assert resolve_elicit_model(tmp_path, "a" * 65) is None
    assert resolve_elicit_model(tmp_path, "a" * 64) is not None


@pytest.fixture
def hub_server(tmp_path: Path):
    reducer = Reducer(tmp_path / "status.json", tmp_path / "token", lambda: {})
    reducer.refresh()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.reducer = reducer
    server.token = "fixture-token"
    server.is_unix = True
    server.hub_manifest = None
    server.inventory_path = tmp_path / "missing-inventory.json"
    server.feedback = FeedbackSpool(tmp_path / "spool")
    server.elicit_model_dir = tmp_path / "preferences"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", tmp_path / "spool"
    finally:
        server.shutdown()
        server.server_close()


def test_post_feedback_spools_and_answers_with_cors(hub_server) -> None:
    base, spool_dir = hub_server
    request = urllib.request.Request(
        base + "/feedback",
        data=json.dumps({"note": "from a report"}).encode(),
        headers={"Content-Type": "application/json", "Referer": "file:///tmp/r.html"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 201
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        body = json.loads(response.read())
    assert body["schema"] == "sinnix-hub-feedback-v1"
    spooled = json.loads(Path(body["file"]).read_text().splitlines()[0])
    assert spooled["payload"] == {"note": "from a report"}
    assert spooled["page"] == "file:///tmp/r.html"
    assert list(spool_dir.iterdir())


def test_preflight_and_health_are_answered(hub_server) -> None:
    base, _ = hub_server
    request = urllib.request.Request(base + "/feedback", method="OPTIONS")
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 204
        assert "POST" in response.headers["Access-Control-Allow-Methods"]
    with urllib.request.urlopen(base + "/feedback", timeout=10) as response:
        assert json.loads(response.read())["status"] == "ready"


def test_the_spool_refuses_bodies_it_cannot_trust(hub_server) -> None:
    base, _ = hub_server
    request = urllib.request.Request(
        base + "/feedback",
        data=b"not json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(request, timeout=10)
    assert raised.value.code == 400


def test_elicit_model_reads_the_domains_own_fit(hub_server, tmp_path: Path) -> None:
    """GET /feedback/elicit/<domain> is the one read this write-only sink
    grew: a domain's own model.json, read straight back for the in-session
    'learning so far' preview -- never the spool itself."""
    base, _ = hub_server
    domain_dir = tmp_path / "preferences" / "wallpapers"
    domain_dir.mkdir(parents=True)
    (domain_dir / "model.json").write_text(
        json.dumps({"schema": "sinnix-elicit-model-v1", "theta": {"a": 1.2}})
    )
    with urllib.request.urlopen(
        base + "/feedback/elicit/wallpapers", timeout=10
    ) as response:
        assert response.status == 200
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        body = json.loads(response.read())
    assert body["schema"] == "sinnix-elicit-v1"
    assert body["domain"] == "wallpapers"
    assert body["model"] == {"schema": "sinnix-elicit-model-v1", "theta": {"a": 1.2}}


def test_elicit_model_404s_before_any_rank_has_run(hub_server) -> None:
    base, _ = hub_server
    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(base + "/feedback/elicit/never-ranked", timeout=10)
    assert raised.value.code == 404


def test_elicit_model_refuses_a_traversal_shaped_domain(hub_server) -> None:
    base, _ = hub_server
    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(base + "/feedback/elicit/..%2f..%2fetc", timeout=10)
    assert raised.value.code == 400
