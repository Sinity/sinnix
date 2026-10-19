"""Generated answers must describe complete, readable source observations."""

import importlib.machinery
import importlib.util
import json
import os
import random
import sqlite3
from types import SimpleNamespace

import pytest
from conftest import FORGE


@pytest.fixture
def forge(tmp_path, monkeypatch):
    monkeypatch.setenv("SINNIX_ACTIVITY_ROOT", str(tmp_path / "activity"))
    monkeypatch.setenv("SINNIX_PHONE_LAKE", str(tmp_path / "phone"))
    monkeypatch.setenv("ATUIN_DB", str(tmp_path / "history.db"))
    loader = importlib.machinery.SourceFileLoader("forge_counts", str(FORGE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.KEYLOG.mkdir(parents=True)
    module.capture_lane_path(module.ACTIVITY, "transcripts").mkdir(parents=True)
    (tmp_path / "phone" / "ambient").mkdir(parents=True)
    (tmp_path / "phone" / "ambient-levels.jsonl").write_text("")
    with sqlite3.connect(module.ATUIN_DB) as db:
        db.execute(
            "CREATE TABLE history(command TEXT COLLATE NOCASE, deleted_at TEXT, timestamp INTEGER)"
        )
    return module


@pytest.mark.parametrize("lines,expected", [(0, 0), (2, 2), (3, None)])
def test_line_limit_never_becomes_an_exact_count(forge, tmp_path, lines, expected):
    path = tmp_path / "ledger.jsonl"
    path.write_bytes(b"{}\n" * lines)
    assert forge._count_lines(path, limit=2) == expected


def test_unavailable_file_is_distinct_from_empty(forge, tmp_path):
    path = tmp_path / "missing.jsonl"
    assert forge._count_lines(path) is None
    path.write_text("{}\n")
    path.chmod(0)
    try:
        assert forge._count_lines(path) is None
    finally:
        path.chmod(0o600)


def test_unreadable_member_prevents_a_partial_transcript_total(forge):
    root = forge.capture_lane_path(forge.ACTIVITY, "transcripts")
    (root / "2026-10-15.jsonl").write_text("{}\n" * 3)
    denied = root / "2026-10-16.jsonl"
    denied.write_text("{}\n")
    denied.chmod(0)
    try:
        assert not any("transcri" in fact[0] for fact in forge.lake_facts())
    finally:
        denied.chmod(0o600)


def test_transcript_line_counts_are_not_audio_file_counts(forge):
    root = forge.capture_lane_path(forge.ACTIVITY, "transcripts")
    (root / "2026-10-15.jsonl").write_text("{}\n" * 3)
    (root / "2026-10-16.jsonl").write_text("{}\n" * 2)
    assert ("lines retained in transcript ledgers", 5, "lines") in forge.lake_facts()


def test_history_facts_are_not_a_capped_recent_sample(forge):
    with sqlite3.connect(forge.ATUIN_DB) as db:
        db.executemany(
            "INSERT INTO history VALUES (?,NULL,?)",
            (("git status", i) for i in range(200001)),
        )
        db.execute("INSERT INTO history VALUES ('nix build',NULL,-1)")
        db.execute("INSERT INTO history VALUES ('GIT status',NULL,-2)")
        db.execute("INSERT INTO history VALUES ('deleted','removed',999999)")
        db.execute("INSERT INTO history VALUES ('',NULL,999999)")
    facts = forge.lake_facts()
    assert ("shell commands in your recorded history", 200003, "commands") in facts
    assert ("distinct shell command lines you have run", 3, "commands") in facts


def test_missing_history_is_reported_as_unavailable_not_empty(forge, capsys):
    assert forge.lake_facts() == []
    assert not capsys.readouterr().err
    forge.ATUIN_DB.unlink()
    assert forge.lake_facts() == []
    assert "atuin unreadable" in capsys.readouterr().err
    assert forge.build_shell_deck(10, random.Random(1)) is None
    message = capsys.readouterr().err
    assert "atuin unreadable" in message and "only 0" not in message


def test_unreadable_day_does_not_become_a_complete_typing_profile(forge):
    (forge.KEYLOG / "2026-10-16.jsonl").write_text(
        json.dumps({"event": "press", "keycode": "KEY_A"}) + "\n"
    )
    good = forge.KEYLOG / "2026-10-15.jsonl"
    good.write_text((json.dumps({"event": "press", "keycode": "KEY_A"}) + "\n") * 1100)
    denied = forge.KEYLOG / "2026-10-16.jsonl"
    denied.chmod(0)
    try:
        assert forge.analyse_typing(days=2, max_lines=2000) is None
    finally:
        denied.chmod(0o600)


def test_typing_respects_the_exact_per_file_line_bound(forge):
    path = forge.KEYLOG / "2026-10-16.jsonl"
    path.write_text((json.dumps({"event": "press", "keycode": "KEY_A"}) + "\n") * 1100)
    assert forge.analyse_typing(days=1, max_lines=1000)["presses"] == 1000


def test_typing_does_not_validate_unselected_historical_entries(forge):
    (forge.KEYLOG / "2024-01-01.jsonl").mkdir()
    path = forge.KEYLOG / "2026-10-16.jsonl"
    path.write_text((json.dumps({"event": "press", "keycode": "KEY_A"}) + "\n") * 1100)
    profile = forge.analyse_typing(days=1, max_lines=2000)
    assert profile["presses"] == 1100 and profile["days"] == 1


def test_failed_typing_publication_preserves_the_previous_profile(
    forge, tmp_path, monkeypatch
):
    root = tmp_path / "profiles"
    root.mkdir()
    monkeypatch.setenv("SINNIX_TYPING_OUTPUT", str(root))
    dest = (
        root / f"{forge.dt.datetime.now(forge.dt.timezone.utc).date().isoformat()}.json"
    )
    dest.write_bytes(b'{"verified":"previous profile"}\n')
    before = dest.read_bytes()
    monkeypatch.setattr(
        forge,
        "analyse_typing",
        lambda *_: {
            "presses": 1100,
            "correction_rate": 0,
            "weakest": [],
        },
    )

    def failed_barrier(_fd):
        raise OSError("synthetic persistence failure")

    monkeypatch.setattr(os, "fsync", failed_barrier)
    with pytest.raises(OSError):
        forge.cmd_typing(SimpleNamespace(days=1, max_lines=1000))
    assert dest.read_bytes() == before


def test_personalized_deck_is_private_and_unchanged(forge, tmp_path, monkeypatch):
    directory = tmp_path / "private-decks"
    monkeypatch.setattr(forge, "DECKS_DIR", directory)
    payload = {"id": "fixture", "trials": [{"stimulus": "synthetic input"}]}
    previous = os.umask(0o022)
    try:
        path = forge.write_deck(payload)
    finally:
        os.umask(previous)
    assert directory.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == payload
