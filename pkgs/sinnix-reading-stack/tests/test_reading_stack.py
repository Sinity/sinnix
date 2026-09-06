from __future__ import annotations

import json

from conftest import load_script

reading_stack = load_script("sinnix-reading-stack")


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
