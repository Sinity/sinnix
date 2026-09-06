from __future__ import annotations

from conftest import load_script

daemon = load_script("sinnix-nav-capture-daemon")


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
