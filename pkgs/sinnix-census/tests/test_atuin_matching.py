"""Unit tests for sinnix-census's atuin word-boundary matching.

`scripts/sinnix-census` has no `.py` suffix (frontmatter-packaged script,
executed by its shebang), so it is loaded here via importlib.util rather than
a normal package import -- same technique as
scripts/tests/test_capture_notifications_listener.py.

Matching covers exact, prefix, middle and final tokens, preserving literal
punctuation and case. Live SQLite records remain visible before checkpoint.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "sinnix-census"

_loader = SourceFileLoader("sinnix_census", str(SCRIPT_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec is not None
census = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = census
_loader.exec_module(census)


def _make_atuin_db(path: Path, commands: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE history (command TEXT, timestamp INTEGER)")
    for i, command in enumerate(commands):
        # Strictly increasing, all comfortably after since_ns=0.
        conn.executemany(
            "INSERT INTO history (command, timestamp) VALUES (?, ?)",
            [(command, (i + 1) * 1_000_000_000)],
        )
    conn.commit()
    conn.close()


def test_word_boundary_matches_all_four_positions_and_rejects_substrings(
    tmp_path, monkeypatch
):
    commands = [
        "sinnix-cat",  # exact whole-command match
        "sinnix-cat --verbose",  # name is the first token (prefix)
        "sudo sinnix-cat file.txt",  # name is a middle token
        "sudo sinnix-cat",  # name is the last token, no trailing space
        # Near-miss false positives: "sinnix-cat" as a mere substring of a
        # longer single token, never bounded by a real word boundary.
        "sinnix-catalog-sync",
        "run-sinnix-cat-helper",
        "notsinnix-cat-either",
    ]
    _make_atuin_db(tmp_path / ".local/share/atuin/history.db", commands)
    monkeypatch.setattr(census, "HOME", tmp_path)

    result = census.atuin_evidence(["sinnix-cat"], since_ns=0)

    assert result is not None
    # Anti-vacuity: a naive `LIKE f"%{name}%"` substring match would count 7
    # here instead of 4, since it does not exclude the three near-misses.
    assert result["sinnix-cat"]["n"] == 4


def test_word_boundary_excludes_all_near_miss_substrings_alone(tmp_path, monkeypatch):
    # Isolate the false-positive guard: with *only* substring near-misses
    # present (no genuine word-bounded usage at all), the match count must
    # be zero, proving the boundary check -- not merely a low count amid
    # real hits -- is what suppresses them.
    _make_atuin_db(
        tmp_path / ".local/share/atuin/history.db",
        ["sinnix-catalog-sync", "run-sinnix-cat-helper", "notsinnix-cat-either"],
    )
    monkeypatch.setattr(census, "HOME", tmp_path)

    result = census.atuin_evidence(["sinnix-cat"], since_ns=0)

    assert result is not None
    assert result["sinnix-cat"]["n"] == 0


def test_name_as_final_token_is_not_lost(tmp_path, monkeypatch):
    # Regression guard for the specific fix in this change: before it, a
    # command ending in the target name with no trailing space (the fourth
    # word-boundary position) was silently dropped.
    _make_atuin_db(tmp_path / ".local/share/atuin/history.db", ["sudo sinnix-cat"])
    monkeypatch.setattr(census, "HOME", tmp_path)

    result = census.atuin_evidence(["sinnix-cat"], since_ns=0)

    assert result is not None
    assert result["sinnix-cat"]["n"] == 1


@pytest.mark.parametrize(
    "name,near_miss",
    [("tool_name", "toolXname"), ("tool%name", "toolXname"), ("CaseTool", "casetool")],
)
def test_token_matching_is_literal_and_case_sensitive(
    tmp_path, monkeypatch, name, near_miss
):
    _make_atuin_db(
        tmp_path / ".local/share/atuin/history.db",
        [name, name + " --arg", "sudo " + name, near_miss + " --arg"],
    )
    monkeypatch.setattr(census, "HOME", tmp_path)
    assert census.atuin_evidence([name], since_ns=0)[name]["n"] == 3


@pytest.mark.parametrize("home_name", ["home", "home?#"])
def test_live_wal_records_and_punctuated_home_are_read(
    tmp_path, monkeypatch, home_name
):
    home = tmp_path / home_name
    database = home / ".local/share/atuin/history.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as writer:
        writer.execute("pragma journal_mode=wal")
        writer.execute("create table history (command text, timestamp integer)")
        writer.commit()
        writer.execute("pragma wal_checkpoint(truncate)")
        writer.execute("insert into history values ('neutral-tool', 1000000000)")
        writer.commit()
        assert database.with_name(database.name + "-wal").stat().st_size > 0
        monkeypatch.setattr(census, "HOME", home)
        result = census.atuin_evidence(["neutral-tool"], since_ns=0)
        assert result is not None and result["neutral-tool"]["n"] == 1


def test_polylogue_evidence_is_cached_by_query_and_window(monkeypatch):
    census._POLYLOGUE_EVIDENCE.clear()
    calls = []

    class Result:
        text = '{"items": [{"id": "one"}]}'

    def fake_run(command, **_kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr(census, "run", fake_run)
    assert census.polylogue_evidence("shared", 90) == {"n": 1, "last": None}
    assert census.polylogue_evidence("shared", 90) == {"n": 1, "last": None}
    assert census.polylogue_evidence("shared", 30) == {"n": 1, "last": None}
    assert len(calls) == 2
