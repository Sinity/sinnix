from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


SCRIPT = Path(__file__).parents[3] / "scripts/sinnix-lake-refs"


@pytest.mark.parametrize("failure", ["missing", "file", "rg", "spawn"])
@pytest.mark.parametrize("command", ["scan", "check"])
def test_unavailable_scan_fails_without_overwriting_ledger(tmp_path, monkeypatch, capsys, failure, command):
    refs = SourceFileLoader("lake_refs", str(SCRIPT)).load_module()
    root = tmp_path / "source"
    if failure == "file":
        root.write_text("wrong object type")
    elif failure != "missing":
        root.mkdir()
    monkeypatch.setattr(refs, "REPOS", {"fixture": root})
    if failure == "rg":
        monkeypatch.setattr(refs.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=2, stdout="", stderr="synthetic scan failure"))
    elif failure == "spawn":
        def fail(*args, **kwargs):
            raise OSError("synthetic unavailable executable")
        monkeypatch.setattr(refs.subprocess, "run", fail)
    out = tmp_path / "ledger.jsonl"
    out.write_text("retained observations\n")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), command] + (["--out", str(out)] if command == "scan" else []))
    assert refs.main() == 2
    assert out.read_text() == "retained observations\n"
    assert "sinnix-lake-refs:" in capsys.readouterr().err


def test_readable_empty_source_is_a_valid_empty_result(tmp_path):
    refs = SourceFileLoader("lake_refs", str(SCRIPT)).load_module()
    assert refs.scan_repo("fixture", tmp_path) == []


def test_failed_publication_preserves_existing_ledger(tmp_path, monkeypatch):
    from sinnix_lib import atomic
    refs = SourceFileLoader("lake_refs", str(SCRIPT)).load_module()
    monkeypatch.setattr(refs, "REPOS", {"fixture": tmp_path})
    out = tmp_path / "ledger.jsonl"
    out.write_text("retained observations\n")
    def fail(*args, **kwargs):
        raise OSError("synthetic publication failure")
    monkeypatch.setattr(atomic.os, "replace", fail)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "scan", "--out", str(out)])
    assert refs.main() == 2
    assert out.read_text() == "retained observations\n"
