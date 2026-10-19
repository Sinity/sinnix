"""The annotation spool's file contract, and the ranking drain arrival triggers.

The spool file is read directly by agents and by `sinnix rank ingest`, so the
envelope shape is asserted against the exact JSON text that lands on disk, not
against a re-parsed dict.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sinnix_hub_server.feedback import (
    CoalescingTrigger,
    FeedbackSpool,
    is_rank_judgment,
    parse_command_argv,
)


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


def test_only_rank_judgments_trigger_the_drain(tmp_path: Path) -> None:
    fired = threading.Event()

    class Recording(CoalescingTrigger):
        def _run(self) -> bool:
            fired.set()
            return True

    trigger = Recording(["true"], delay=0.05)
    spool = FeedbackSpool(tmp_path, rank_ingest=trigger)
    spool.append({"schema": "report-annotations", "note": "x"}, None, None)
    assert not fired.wait(0.3)
    spool.append(
        {"schema": "sinnix-rank-v1", "domain": "wallpaper", "set": ["1", "2"]},
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
    spool = FeedbackSpool(tmp_path, rank_ingest=trigger)
    for index in range(10):
        spool.append(
            {"schema": "sinnix-rank-v1", "domain": "d", "n": index}, None, None
        )
    time.sleep(2.5)
    assert len(runs) == 1


def test_is_rank_judgment_ignores_non_objects() -> None:
    assert is_rank_judgment({"schema": "sinnix-rank-v1"})
    assert not is_rank_judgment(["sinnix-rank-v1"])
    assert not is_rank_judgment(None)


def test_drain_command_is_a_typed_argv() -> None:
    assert parse_command_argv('["agentctl", "job", "start", "sinnix"]') == [
        "agentctl",
        "job",
        "start",
        "sinnix",
    ]
    with pytest.raises(ValueError, match="JSON argv"):
        parse_command_argv("agentctl job start sinnix")
    with pytest.raises(ValueError, match="nonempty"):
        parse_command_argv("[]")


@pytest.fixture
def hub_server(hub_server_factory, tmp_path: Path) -> tuple[str, Path]:
    spool = tmp_path / "spool"
    base = hub_server_factory(feedback=FeedbackSpool(spool))
    return base, spool


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


def test_spool_rejects_invalid_content_length_before_append(hub_server) -> None:
    base, spool_dir = hub_server
    parsed = urlsplit(base)
    connection = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        connection.putrequest("POST", "/feedback")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", "not-a-number")
        connection.endheaders(b'{"note":"must not be appended"}')
        response = connection.getresponse()
        body = json.loads(response.read())
    finally:
        connection.close()

    assert response.status == 411
    assert body == {"error": "Content-Length required"}
    assert not list(spool_dir.glob("*.jsonl"))
