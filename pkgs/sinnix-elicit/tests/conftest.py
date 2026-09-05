"""Load `scripts/sinnix-elicit` as a module (no .py suffix, shebang-packaged)."""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "sinnix-elicit"


def _load():
    loader = SourceFileLoader("sinnix_elicit", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


elicit = _load()


@pytest.fixture()
def elicit_module():
    return elicit


@pytest.fixture()
def domain(tmp_path, monkeypatch):
    """A domain rooted in tmp_path, reached the way the CLI reaches it."""
    monkeypatch.setattr(elicit, "BASE_DIR", tmp_path / "elicit")
    monkeypatch.setattr(elicit, "FEEDBACK_DIR", tmp_path / "hub-feedback")
    (tmp_path / "hub-feedback").mkdir()
    return elicit.Domain("wallpaper")
