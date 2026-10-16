"""The packaged entry point reads installed config without executing it."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(os.environ.get("CHEATSHEET_TEST_SCRIPT", Path(__file__).resolve().parents[3] / "scripts/sinnix-cheatsheet"))

@pytest.fixture
def sheet(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    loader = importlib.machinery.SourceFileLoader("cheatsheet_test", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_installed_config_handles_multiline_and_escaped_strings(sheet, tmp_path):
    config = tmp_path / "config/qutebrowser/config.py"
    config.parent.mkdir(parents=True)
    config.write_text("raise RuntimeError('must never execute')\nconfig.bind('a', 'open example')\nconfig.bind(\n 'b',\n 'spawn \"quoted\"',\n)\nconfig.bind(dynamic, 'skip')\n")
    assert sheet.collect_qutebrowser_binds() == [
        {"key": "a", "action": "open example"},
        {"key": "b", "action": 'spawn "quoted"'},
    ]


@pytest.mark.parametrize("payload", [None, "", "broken("])
def test_absent_invalid_and_empty_config_are_distinct(sheet, tmp_path, payload):
    config = tmp_path / "config/qutebrowser/config.py"
    config.parent.mkdir(parents=True)
    if payload is not None:
        config.write_text(payload)
    rows = sheet.collect_qutebrowser_binds()
    if payload == "":
        assert rows == []
    else:
        assert "error" in rows[0]


def test_config_error_is_visible_and_escaped(sheet, monkeypatch):
    monkeypatch.setattr(sheet, "collect_qutebrowser_binds", lambda: [{"error": "denied <config>"}])
    monkeypatch.setattr(sheet, "collect_hypr_binds", lambda: [])
    monkeypatch.setattr(sheet, "collect_capabilities", lambda: {"groups": []})
    page = sheet.build_html("fixture")
    assert "denied &lt;config&gt;" in page and "denied <config>" not in page
