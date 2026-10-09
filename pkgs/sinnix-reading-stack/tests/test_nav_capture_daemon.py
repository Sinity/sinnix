from __future__ import annotations

import io

import pytest
from conftest import load_script

daemon = load_script("sinnix-nav-capture-daemon")


@pytest.mark.parametrize(
    ("length", "raw"),
    [
        ("invalid", b"{}"),
        ("-1", b"{}"),
        ("9", b"{}"),
        ("2", b"[]"),
        ("4", b"null"),
        ("1", b"\xff"),
    ],
)
def test_invalid_body_returns_400_without_capture(length, raw, monkeypatch):
    handler = object.__new__(daemon.Handler)
    handler.headers = {"Content-Length": length}
    handler.rfile = io.BytesIO(raw)
    handler.path = "/v1/link-event"
    responses = []
    handler._respond = responses.append
    calls = []
    monkeypatch.setattr(
        daemon, "sinnix_capture_write", lambda *args: calls.append(args)
    )
    handler.do_POST()
    assert responses == [400]
    assert calls == []
    if length in ("invalid", "-1"):
        assert handler.rfile.tell() == 0


def test_valid_body_reaches_capture(monkeypatch):
    handler = object.__new__(daemon.Handler)
    handler.headers = {"Content-Length": "17"}
    handler.rfile = io.BytesIO(b'{"trigger":"tap"}')
    handler.path = "/v1/link-event"
    responses = []
    handler._respond = responses.append
    calls = []
    monkeypatch.setattr(
        daemon, "sinnix_capture_write", lambda *args: calls.append(args)
    )
    handler.do_POST()
    assert responses == [204]
    assert calls == [("browser-nav-edges", {"trigger": "tap"})]


def test_reading_stack_push_passes_provenance_and_note(monkeypatch):
    calls = []
    monkeypatch.setattr(
        daemon.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    daemon.reading_stack_push(
        {
            "target_url": "https://target.example/article",
            "target_title": "Target article",
            "source_url": "https://source.example/list",
            "source_title": "Source list",
            "anchor_text": "Read this next",
            "note": "Compare with the earlier report",
        }
    )

    assert calls == [
        (
            [
                "sinnix-reading-stack",
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
            ],
            {"check": True, "capture_output": True},
        )
    ]
