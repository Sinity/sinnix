"""Load `scripts/sinnix-rank` as a module (no .py suffix, shebang-packaged)."""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "sinnix-rank"


def _load():
    loader = SourceFileLoader("sinnix_rank", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


rank = _load()


@pytest.fixture()
def rank_module():
    return rank


@pytest.fixture()
def domain(tmp_path, monkeypatch):
    """A domain name rooted in tmp_path, reached the way the CLI reaches it."""
    monkeypatch.setattr(rank, "CAPTURE_ROOT", tmp_path / "ranking")
    monkeypatch.setattr(rank, "FEEDBACK_DIR", tmp_path / "hub-feedback")
    monkeypatch.setattr(rank, "REPORTS_DIR", tmp_path / "report")
    (tmp_path / "hub-feedback").mkdir()
    return "wallpaper"


@pytest.fixture()
def store(domain):
    return rank.Store(rank.domain_dir(domain))
