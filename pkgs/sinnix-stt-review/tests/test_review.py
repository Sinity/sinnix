import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def subject():
    path = Path(__file__).resolve().parents[3] / "scripts/sinnix-stt-review"
    loader = importlib.machinery.SourceFileLoader("review", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_resume_preserves_evidence_and_rejects_changed_audio(
    subject, tmp_path, monkeypatch
):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"synthetic-audio")
    output = tmp_path / "output"
    monkeypatch.setenv("ELEVENLABS_API_KEY", "synthetic-key")
    monkeypatch.setattr(
        sys, "argv", ["review", "--output-dir", str(output), str(audio)]
    )
    response = {
        "text": "Ala.",
        "words": [
            {
                "type": "word",
                "text": "Ala.",
                "start": 1.2,
                "end": 1.7,
                "speaker_id": "speaker_0",
                "logprob": -2.1,
            }
        ],
    }
    calls = []

    def transcribe(path, key, parameters):
        calls.append(parameters)
        return response

    monkeypatch.setattr(subject, "request_transcript", transcribe)
    assert subject.main() == 0
    assert subject.main() == 0
    assert len(calls) == 1
    assert calls[0]["language_code"] == "pol"
    assert json.loads((output / "clip.wav.scribe.json").read_text()) == response
    review = json.loads((output / "review-spans.json").read_text())
    assert review[0]["start"] == 1.2
    assert review[0]["low_logprob_words"] == response["words"]
    audio.write_bytes(b"changed-audio")
    with pytest.raises(SystemExit):
        subject.main()
    assert len(calls) == 1


def test_speaker_turns_and_recording_clock(subject):
    words = [
        {"type": "word", "text": "A", "start": 0, "end": 1, "speaker_id": "a"},
        {"type": "spacing", "text": " ", "start": 1, "end": 1, "speaker_id": "a"},
        {"type": "word", "text": "B", "start": 1, "end": 2, "speaker_id": "b"},
        {"type": "word", "text": "C", "start": 5, "end": 6, "speaker_id": "b"},
    ]
    assert [[w["text"] for w in turn] for turn in subject.turns(words)] == [
        ["A"],
        ["B"],
        ["C"],
    ]
    assert subject.clock_label(Path("ambient-20260101T120000Z.m4a"), 10) == "13:00:10"
    assert subject.clock_label(Path("clip.wav"), 10) == "10.00s"


def test_confident_word_with_long_alignment_is_flagged(subject, tmp_path):
    word = {"type": "word", "text": "Ala", "start": 1.0, "end": 35.0, "logprob": -0.01}
    (tmp_path / "raw.json").write_text(json.dumps({"text": "Ala", "words": [word]}))
    subject.render(
        [
            {
                "source": "clip.wav",
                "raw_file": "raw.json",
                "parameters": {"language_code": "pol"},
            }
        ],
        tmp_path,
    )
    assert json.loads((tmp_path / "review-spans.json").read_text()) == []
    assert json.loads((tmp_path / "alignment-review.json").read_text()) == [
        {"source": "clip.wav", "word": word}
    ]


def test_network_failure_can_resume_without_reuploading_completed_files(
    subject, tmp_path, monkeypatch, capsys
):
    paths = [tmp_path / "first.wav", tmp_path / "second.wav"]
    for path in paths:
        path.write_bytes(b"synthetic-audio")
    output = tmp_path / "output"
    monkeypatch.setenv("ELEVENLABS_API_KEY", "synthetic-secret")
    monkeypatch.setattr(
        sys, "argv", ["review", "--output-dir", str(output), *map(str, paths)]
    )
    calls = []

    def transcribe(path, key, parameters):
        calls.append(path.name)
        if len(calls) == 2:
            raise subject.urllib.error.URLError("synthetic-secret")
        return {"text": "Ala", "words": []}

    monkeypatch.setattr(subject, "request_transcript", transcribe)
    assert subject.main() == 1
    assert "synthetic-secret" not in capsys.readouterr().err
    assert subject.main() == 0
    assert calls == ["first.wav", "second.wav", "second.wav"]
    assert len(json.loads((output / "manifest.json").read_text())) == 2


def test_changed_settings_refuse_cached_response(subject, tmp_path, monkeypatch):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"synthetic-audio")
    argv = ["review", "--output-dir", str(tmp_path / "output"), str(audio)]
    monkeypatch.setenv("ELEVENLABS_API_KEY", "synthetic-key")
    monkeypatch.setattr(sys, "argv", argv)
    calls = []

    def transcribe(*args):
        calls.append(args)
        return {"text": "Ala", "words": []}

    monkeypatch.setattr(subject, "request_transcript", transcribe)
    assert subject.main() == 0
    monkeypatch.setattr(sys, "argv", [*argv, "--language", "eng"])
    with pytest.raises(SystemExit):
        subject.main()
    assert len(calls) == 1
