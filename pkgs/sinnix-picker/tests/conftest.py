"""Load a packaged script as a module.

The scripts under test carry a shebang and no `.py` suffix, and the suite runs
against the layout the packaged check reproduces: `parents[3]/scripts/<name>`
relative to this file.
"""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def load_script(name: str):
    loader = SourceFileLoader(name.replace("-", "_"), str(SCRIPTS_DIR / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module
