from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def lake(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[3] / "scripts" / "sinnix-stt"
    loader = importlib.machinery.SourceFileLoader("sinnix_stt_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(module, "ACTIVITY", tmp_path / "activity")
    monkeypatch.setattr(module, "MACHINE", tmp_path / "machine")
    monkeypatch.setattr(module, "TRANSCRIPT_DIR", tmp_path / "transcripts")
    monkeypatch.setattr(module, "LEDGER", module.TRANSCRIPT_DIR / "transcribed.jsonl")
    monkeypatch.setattr(module, "models_present", lambda: True)
    calls = []

    def transcribe(path):
        calls.append(path)
        return {"file": str(path), "speech_seconds": 1, "text": path.read_text()}

    monkeypatch.setattr(module, "transcribe_file", transcribe)
    phone = module.MACHINE / "phone" / "ambient" / "same.opus"
    mic = module.ACTIVITY / "audio" / "src-mic" / "same.opus"
    for path, text in ((phone, "room"), (mic, "desk")):
        path.parent.mkdir(parents=True)
        path.write_text(text)
    return module, calls, phone, mic


def run_lake(module):
    assert module.cmd_lake(argparse.Namespace(lane=None, limit=0)) == 0


def test_same_name_and_size_in_different_lanes_transcribe_once_each(lake):
    module, calls, phone, mic = lake
    run_lake(module)
    run_lake(module)
    assert calls == [phone, mic]
    rows = [json.loads(line) for line in module.LEDGER.read_text().splitlines()]
    assert [(row["lane"], row["file"], row["bytes"]) for row in rows] == [
        ("phone", "same.opus", 4),
        ("src-mic", "same.opus", 4),
    ]
    transcripts = [
        json.loads(line)
        for path in module.TRANSCRIPT_DIR.glob("*.jsonl")
        if path != module.LEDGER
        for line in path.read_text().splitlines()
    ]
    assert {(row["lane"], row["text"]) for row in transcripts} == {
        ("phone", "room"),
        ("src-mic", "desk"),
    }


def test_legacy_row_without_lane_does_not_hide_current_sources(lake):
    module, calls, phone, mic = lake
    module.TRANSCRIPT_DIR.mkdir()
    legacy = json.dumps({"file": "same.opus", "bytes": 4}) + "\n"
    module.LEDGER.write_text(legacy)
    run_lake(module)
    run_lake(module)
    assert calls == [phone, mic]
    assert module.LEDGER.read_text().startswith(legacy)


def test_lane_qualified_history_and_repaired_size(lake):
    module, calls, phone, mic = lake
    module.TRANSCRIPT_DIR.mkdir()
    prior = json.dumps({"lane": "phone", "file": "same.opus", "bytes": 4}) + "\n"
    module.LEDGER.write_text(prior)
    run_lake(module)
    assert calls == [mic]
    phone.write_text("repaired recording")
    run_lake(module)
    run_lake(module)
    assert calls == [mic, phone]
    assert module.LEDGER.read_text().startswith(prior)
