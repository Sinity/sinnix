"""Load a packaged script as a module.

The scripts under test carry a shebang and no `.py` suffix, and the suite runs
against the layout the packaged check reproduces: `parents[3]/scripts/<name>`
relative to this file.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def load_script(name: str):
    loader = SourceFileLoader(name.replace("-", "_"), str(SCRIPTS_DIR / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture
def capture_writer(tmp_path, monkeypatch):
    directory = tmp_path / "bin"
    directory.mkdir()
    writer = directory / "sinnix-capture"
    receipt = tmp_path / "captured.json"
    writer.write_text(
        f"#!{sys.executable}\nimport json,os,sys,pathlib\n"
        "pathlib.Path(os.environ['CAPTURE_FIXTURE']).write_text(json.dumps("
        "{'argv':sys.argv[1:],'payload':json.loads(sys.stdin.read())}))\n"
    )
    writer.chmod(0o700)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("CAPTURE_FIXTURE", str(receipt))
    return receipt
