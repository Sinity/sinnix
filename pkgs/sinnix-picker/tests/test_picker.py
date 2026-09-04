from __future__ import annotations

import importlib.util
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path


def _load_script(name: str):
    script = Path(__file__).resolve().parents[3] / "scripts" / name
    loader = SourceFileLoader(name.replace("-", "_"), str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


picker = _load_script("sinnix-picker")


def test_duplicate_labels_select_the_chosen_row(monkeypatch):
    entries = [
        picker.Entry("stack", "Same title", "https://one.example"),
        picker.Entry("stack", "Same title", "https://two.example"),
    ]
    launches = []
    monkeypatch.setattr(picker, "gather", lambda: entries)
    monkeypatch.setattr(
        picker.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["fuzzel"], 0, "[stack] Same title -- https://two.example\t1\n", ""
        ),
    )
    monkeypatch.setattr(
        picker.subprocess,
        "Popen",
        lambda command, **kwargs: launches.append((command, kwargs)),
    )

    assert picker.main() == 0
    assert launches == [
        (
            ["sinnix-reading-stack", "open", "--url", "https://two.example"],
            {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "start_new_session": True,
            },
        )
    ]
