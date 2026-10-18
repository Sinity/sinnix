from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import load_script

reading_stack = load_script("sinnix-reading-stack")


def test_large_capture_payload_uses_stdin(capture_writer):
    payload = {"title": "synthetic title " * 12000, "url": "https://example.test/"}
    reading_stack._capture("push", payload)
    observed = json.loads(capture_writer.read_text())
    assert observed["payload"] == {"event": "push", **payload}
    assert "--payload" not in observed["argv"]
    assert payload["title"] not in observed["argv"]


def configure_state(monkeypatch, tmp_path):
    monkeypatch.setattr(reading_stack, "STATE_FILE", tmp_path / "reading-stack.json")
    monkeypatch.setattr(reading_stack, "_capture", lambda *_: None)


def test_push_retains_link_provenance_and_optional_note(monkeypatch, tmp_path):
    configure_state(monkeypatch, tmp_path)

    assert (
        reading_stack.main(
            [
                "push",
                "--url",
                "https://target.example/article",
                "--title",
                "Target article",
                "--source-url",
                "https://source.example/list",
                "--source-title",
                "Source list",
                "--anchor-text",
                "Read this next",
                "--note",
                "Compare with the earlier report",
            ]
        )
        == 0
    )

    [entry] = json.loads(reading_stack.STATE_FILE.read_text())
    assert entry["url"] == "https://target.example/article"
    assert entry["source_url"] == "https://source.example/list"
    assert entry["source_title"] == "Source list"
    assert entry["anchor_text"] == "Read this next"
    assert entry["note"] == "Compare with the earlier report"


def test_open_launches_viewer_then_consumes_and_records_pop(monkeypatch, tmp_path):
    configure_state(monkeypatch, tmp_path)
    events = []
    launches = []
    monkeypatch.setattr(
        reading_stack,
        "_capture",
        lambda event, payload: events.append((event, payload)),
    )
    monkeypatch.setattr(
        reading_stack.subprocess,
        "Popen",
        lambda command, **kwargs: launches.append((command, kwargs)),
    )

    assert (
        reading_stack.main(
            [
                "push",
                "--url",
                "https://target.example/article",
                "--anchor-text",
                "Target",
            ]
        )
        == 0
    )
    assert reading_stack.main(["open", "--url", "https://target.example/article"]) == 0

    assert launches == [
        (
            ["sinnix-browser-app", "https://target.example/article"],
            {"start_new_session": True},
        )
    ]
    assert json.loads(reading_stack.STATE_FILE.read_text()) == []
    assert [event for event, _payload in events] == ["push", "pop"]


@pytest.mark.parametrize("kind", ["push", "pop", "open", "capture"])
def test_overlapping_mutations_preserve_entries_and_capture_order(
    monkeypatch, tmp_path, kind
):
    configure_state(monkeypatch, tmp_path)
    first = "https://first.example/item"
    second = "https://second.example/item"
    seed = [] if kind in {"push", "capture"} else [{"url": first}, {"url": second}]
    reading_stack._save(seed[:1] if kind == "open" else seed)
    ready, release, entered, done = (threading.Event() for _ in range(4))
    role = threading.local()
    events, launches = [], []
    real_save = reading_stack._save

    def pause():
        ready.set()
        assert release.wait(5), "first operation was not released"

    def save(items):
        if role.number == 1 and kind in {"push", "pop"}:
            pause()
        real_save(items)

    def capture(event, payload):
        if role.number == 1 and kind == "capture":
            pause()
        events.append((event, payload["url"]))

    def launch(command, **kwargs):
        launches.append(command)
        if role.number == 1 and kind == "open":
            pause()

    monkeypatch.setattr(reading_stack, "_save", save)
    monkeypatch.setattr(reading_stack, "_capture", capture)
    monkeypatch.setattr(reading_stack.subprocess, "Popen", launch)

    def mutate(number):
        role.number = number
        if number == 2:
            entered.set()
        try:
            argv = (
                ["push", "--url", first if number == 1 else second]
                if kind in {"push", "capture"}
                else [kind]
            )
            return reading_stack.main(argv)
        finally:
            if number == 2:
                done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(mutate, 1)
        try:
            assert ready.wait(5)
            two = pool.submit(mutate, 2)
            assert entered.wait(5)
            done.wait(0.25)
        finally:
            release.set()
        results = [one.result(timeout=5), two.result(timeout=5)]
    urls = [row["url"] for row in reading_stack._load()]
    if kind in {"push", "capture"}:
        assert results == [0, 0]
        assert urls == [second, first]
        assert urls == [url for event, url in events if event == "push"][::-1]
    elif kind == "pop":
        assert results == [0, 0]
        assert urls == []
        assert events == [("pop", first), ("pop", second)]
    else:
        assert results == [0, 1]
        assert urls == []
        assert launches == [["sinnix-browser-app", first]]
        assert events == [("pop", first)]


def test_failed_viewer_launch_retains_entry(monkeypatch, tmp_path):
    configure_state(monkeypatch, tmp_path)
    reading_stack.main(["push", "--url", "https://first.example/item"])
    before = reading_stack.STATE_FILE.read_bytes()

    def unavailable(*args, **kwargs):
        raise FileNotFoundError("synthetic viewer unavailable")

    monkeypatch.setattr(reading_stack.subprocess, "Popen", unavailable)
    monkeypatch.setattr(
        reading_stack,
        "_capture",
        lambda *_: pytest.fail("failed launch must not capture a pop"),
    )
    assert reading_stack.main(["open"]) == 1
    assert reading_stack.STATE_FILE.read_bytes() == before


def test_state_publication_is_private(monkeypatch, tmp_path):
    configure_state(monkeypatch, tmp_path)
    assert reading_stack.main(["push", "--url", "https://first.example/item"]) == 0
    assert reading_stack.STATE_FILE.stat().st_mode & 0o777 == 0o600
