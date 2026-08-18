"""Unit tests for sinnix-census's atuin word-boundary matching.

`scripts/sinnix-census` has no `.py` suffix (frontmatter-packaged script,
executed by its shebang), so it is loaded here via importlib.util rather than
a normal package import -- same technique as
scripts/tests/test_capture_notifications_listener.py.

The bead's spec calls for matching "anchored at word starts... to avoid
substring false positives". The real query at import time only guarded
three of the four word-boundary positions (exact, prefix, middle) and
silently dropped hits where the name is the *last* token of a longer command
(e.g. `sudo sinnix-cat`, no trailing space) -- a false negative that would
misreport a used script as unused. Fixed in the same change as these tests;
see the `f"% {name}"` clause in atuin_evidence().
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

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
