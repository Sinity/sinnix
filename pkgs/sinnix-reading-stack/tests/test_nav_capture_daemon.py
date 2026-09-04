from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path


def _load_script(name: str):
    script = Path(__file__).resolve().parents[3] / "scripts" / name
    loader = SourceFileLoader(name.replace("-", "_"), str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


daemon = _load_script("sinnix-nav-capture-daemon")


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
