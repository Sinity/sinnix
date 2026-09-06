from __future__ import annotations

import subprocess

from conftest import load_script

picker = load_script("sinnix-picker")


def test_duplicate_labels_select_the_chosen_row(monkeypatch):
    entries = [
        picker.Entry("stack", "Same title", "https://one.example"),
        picker.Entry("stack", "Same title", "https://two.example"),
    ]
    launches = []
    monkeypatch.setattr(picker, "gather", lambda: entries)
    monkeypatch.setattr(
        picker.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["fuzzel"], 0, "[stack] Same title -- https://two.example\t1\n", ""
        ),
    )
    monkeypatch.setattr(
        picker.subprocess,
        "Popen",
        lambda command, **kwargs: launches.append((command, kwargs)),
    )

    assert picker.main() == 0
    assert launches == [
        (
            ["sinnix-reading-stack", "open", "--url", "https://two.example"],
            {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "start_new_session": True,
            },
        )
    ]


def test_gather_deduplicates_urls_across_sources(monkeypatch):
    monkeypatch.setattr(
        picker,
        "load_reading_stack",
        lambda: [picker.Entry("stack", "Queued", "https://same.example")],
    )
    monkeypatch.setattr(picker, "load_recent_dirs", lambda: [])
    monkeypatch.setattr(picker, "load_clipboard", lambda: [])
    monkeypatch.setattr(
        picker,
        "load_chrome_bookmarks",
        lambda: [picker.Entry("mark", "Bookmark", "https://same.example")],
    )
    monkeypatch.setattr(picker, "load_raindrop", lambda: [])
    monkeypatch.setattr(
        picker,
        "load_history",
        lambda: [picker.Entry("hist", "History", "https://other.example")],
    )

    assert picker.gather() == [
        picker.Entry("stack", "Queued", "https://same.example"),
        picker.Entry("hist", "History", "https://other.example"),
    ]
