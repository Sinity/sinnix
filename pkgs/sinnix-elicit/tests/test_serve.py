"""`serve` drives the comparison loop over HTTP against the real store.

Every assertion goes through a running server on a loopback port, because the
surface being tested is the request handling: the routes are what the page
calls, and an in-process call to `ServeSession` would prove nothing about them.
"""

from __future__ import annotations

import json
import struct
import threading
import urllib.error
import urllib.request
import zlib

import pytest
from rank_core import fit as rank_fit
from rank_core import top_k_stability


# ── fixture images: synthetic PNGs, generated here, never repository content ──
def png(width=8, height=8, rgb=(200, 40, 40)):
    def chunk(tag, payload):
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.fixture()
def image_domain(domain, tmp_path):
    """A four-item image roster, each item's file written by this test."""
    stash = tmp_path / "stash"
    stash.mkdir()
    items = []
    for index, name in enumerate(("alpha", "beta", "gamma", "delta")):
        path = stash / f"{name}.png"
        path.write_bytes(png(rgb=(40 * index, 200 - 40 * index, 90)))
        items.append({"id": name, "label": f"{name} 8x8", "image": str(path)})
    domain.dir.mkdir(parents=True, exist_ok=True)
    domain.items_path.write_text(json.dumps(items))
    return domain


class Client:
    def __init__(self, base):
        self.base = base

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as response:
            return response.status, response.headers, response.read()

    def json_get(self, path):
        return json.loads(self.get(path)[2])

    def post(self, path, payload):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())


@pytest.fixture()
def serving(elicit_module, image_domain):
    server, state = elicit_module.build_serve_server(
        image_domain, port=0, top_k=2, seed=7
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Client(f"http://127.0.0.1:{server.server_port}"), state
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()


def raw_records(domain):
    if not domain.comparisons_path.exists():
        return []
    return [
        json.loads(line)
        for line in domain.comparisons_path.read_text().splitlines()
        if line.strip()
    ]


def judgments(domain):
    return [r for r in raw_records(domain) if "delete" not in r]


def test_a_judgment_lands_in_the_store_in_the_domains_own_record_shape(
    serving, image_domain
):
    client, _state = serving
    pair = client.json_get("/next")["pair"]

    client.post(
        "/answer",
        {"id": "j1", "a": pair["a"]["id"], "b": pair["b"]["id"], "outcome": 1},
    )

    records = judgments(image_domain)
    assert len(records) == 1
    assert records[0]["kind"] == "pair"
    assert records[0]["a"] == pair["a"]["id"]
    assert records[0]["b"] == pair["b"]["id"]
    assert records[0]["outcome"] == 1.0
    assert records[0]["id"] == "j1"
    assert records[0]["session"].startswith("serve")
    # The store, read back the way every other surface reads it.
    assert len(image_domain.load_comparisons()) == 1


def test_a_resubmitted_judgment_is_appended_once_even_after_it_was_undone(
    serving, image_domain
):
    """Dedup is against every id the log has ever carried, tombstones included.
    Asking `load_comparisons` instead re-appends an undone judgment on every
    retry -- the shape that put 3,045 copies of one record in the live
    wallpaper log."""
    client, _state = serving
    pair = client.json_get("/next")["pair"]
    body = {"id": "j1", "a": pair["a"]["id"], "b": pair["b"]["id"], "outcome": 1}

    client.post("/answer", body)
    client.post("/answer", body)
    client.post("/undo", {})
    for _ in range(3):
        client.post("/answer", body)

    assert [r["id"] for r in judgments(image_domain)] == ["j1"]
    assert image_domain.load_comparisons() == []


def test_a_judgment_another_writer_already_appended_is_not_appended_again(
    serving, image_domain
):
    """`sinnix-elicit autoingest` drains the hub spool into the same log while
    this loop runs, so the id set the dedup asks must be re-read from the log
    rather than frozen when the server started."""
    client, _state = serving
    image_domain.append(
        {
            "id": "drained-1",
            "kind": "pair",
            "a": "alpha",
            "b": "beta",
            "outcome": 1.0,
            "session": "hub",
        }
    )

    client.post("/answer", {"id": "drained-1", "a": "alpha", "b": "beta", "outcome": 0})

    records = judgments(image_domain)
    assert [r["id"] for r in records] == ["drained-1"]
    assert records[0]["outcome"] == 1.0


def test_undo_tombstones_rather_than_rewriting_the_log(serving, image_domain):
    client, _state = serving
    pair = client.json_get("/next")["pair"]
    client.post(
        "/answer",
        {"id": "j1", "a": pair["a"]["id"], "b": pair["b"]["id"], "outcome": 0},
    )

    payload = client.post("/undo", {})

    assert [r["id"] for r in judgments(image_domain)] == ["j1"]
    assert [r["delete"] for r in raw_records(image_domain) if "delete" in r] == ["j1"]
    assert payload["status"]["comparisons"] == 0


def test_an_already_judged_pair_is_not_asked_again_while_fresh_ones_remain(
    serving, image_domain
):
    client, _state = serving
    asked = []
    for index in range(5):
        pair = client.json_get("/next")["pair"]
        key = frozenset((pair["a"]["id"], pair["b"]["id"]))
        assert key not in asked, f"pair {sorted(key)} asked twice"
        asked.append(key)
        client.post(
            "/answer",
            {
                "id": f"j{index}",
                "a": pair["a"]["id"],
                "b": pair["b"]["id"],
                "outcome": 1,
            },
        )


def test_skip_asks_something_else_and_records_nothing(serving, image_domain):
    client, _state = serving
    pair = client.json_get("/next")["pair"]

    payload = client.post("/skip", {"a": pair["a"]["id"], "b": pair["b"]["id"]})

    assert frozenset(
        (payload["pair"]["a"]["id"], payload["pair"]["b"]["id"])
    ) != frozenset((pair["a"]["id"], pair["b"]["id"]))
    assert judgments(image_domain) == []


def test_status_reports_the_engines_own_fit_and_stopping_statistic(
    serving, image_domain, elicit_module
):
    client, _state = serving
    for index, (winner, loser) in enumerate([("alpha", "beta"), ("alpha", "gamma")]):
        client.post(
            "/answer", {"id": f"j{index}", "a": winner, "b": loser, "outcome": 1}
        )

    status = client.json_get("/status")

    ids = [str(i["id"]) for i in json.loads(image_domain.items_path.read_text())]
    expected_fit = rank_fit(
        ids,
        elicit_module.to_comparisons(image_domain.load_comparisons(), set(ids)),
    )
    expected_stability = top_k_stability(expected_fit, k=2, samples=200, seed=0)
    assert [row["id"] for row in status["top"]] == [
        r.id for r in expected_fit.ranked()[:2]
    ]
    assert status["top"][0]["id"] == "alpha"
    assert status["stability"]["p_stable"] == round(expected_stability.p_stable, 3)
    assert status["stability"]["top_k"] == list(expected_stability.top_k)
    assert status["comparisons"] == 2
    assert status["judged_items"] == 3
    assert status["items"] == 4


def test_an_unjudged_roster_is_not_reported_as_settled(serving):
    client, _state = serving
    status = client.json_get("/status")
    assert status["comparisons"] == 0
    assert status["stability"]["settled"] is False
    assert status["components"] == 4


def test_images_come_from_the_roster_and_nothing_else(serving, image_domain, tmp_path):
    client, _state = serving
    secret = tmp_path / "secret.png"
    secret.write_bytes(png(rgb=(1, 2, 3)))

    status, headers, body = client.get("/image/alpha")
    assert status == 200
    assert headers["Content-Type"] == "image/png"
    assert body == (tmp_path / "stash" / "alpha.png").read_bytes()

    for path in ("/image/nosuchitem", f"/image/{secret}", "/image/../../etc/passwd"):
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            client.get(path)
        assert excinfo.value.code == 404


def test_the_page_is_served_and_names_its_domain(serving):
    client, _state = serving
    status, headers, body = client.get("/")
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    page = body.decode()
    assert '"domain": "wallpaper"' in page
    assert "__CONFIG_JSON__" not in page
    assert "/answer" in page and "ArrowLeft" in page


def test_a_malformed_judgment_is_refused_and_writes_nothing(serving, image_domain):
    client, _state = serving
    for body in (
        {"id": "x", "a": "alpha", "b": "alpha", "outcome": 1},
        {"id": "x", "a": "alpha", "b": "not-an-item", "outcome": 1},
        {"id": "x", "a": "alpha", "b": "beta", "outcome": 0.7},
    ):
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            client.post("/answer", body)
        assert excinfo.value.code == 400
    assert judgments(image_domain) == []


def test_a_second_run_resumes_from_the_log(elicit_module, image_domain, serving):
    client, _state = serving
    pair = client.json_get("/next")["pair"]
    client.post(
        "/answer",
        {"id": "j1", "a": pair["a"]["id"], "b": pair["b"]["id"], "outcome": 1},
    )

    resumed = elicit_module.ServeSession(image_domain, top_k=2, seed=1)

    assert resumed.status()["comparisons"] == 1
    assert "j1" in resumed.known_ids
    assert resumed.recorded == []
    fresh = resumed.next_payload()["pair"]
    assert frozenset((fresh["a"]["id"], fresh["b"]["id"])) != frozenset(
        (pair["a"]["id"], pair["b"]["id"])
    )


def test_quit_saves_the_refit_model(serving, image_domain):
    client, _state = serving
    client.post("/answer", {"id": "j1", "a": "alpha", "b": "beta", "outcome": 1})

    payload = client.post("/quit", {})

    assert payload["done"] is True
    model = json.loads(image_domain.model_path.read_text())
    assert model["n_comparisons"] == 1
    assert model["ranking"][0]["id"] == "alpha"
