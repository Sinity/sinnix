from __future__ import annotations

import importlib.util
import json
import sys
import types
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


atomic_json = types.ModuleType("sinnix_lib.atomic_json")
atomic_json.read_json = lambda path, default: (
    json.loads(path.read_text()) if path.exists() else default
)
atomic_json.write_json_atomic = lambda path, value: (
    path.parent.mkdir(parents=True, exist_ok=True),
    path.write_text(json.dumps(value)),
)
sinnix_lib = types.ModuleType("sinnix_lib")
sinnix_lib.atomic_json = atomic_json
sys.modules["sinnix_lib"] = sinnix_lib
sys.modules["sinnix_lib.atomic_json"] = atomic_json

reading_stack = _load_script("sinnix-reading-stack")


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
