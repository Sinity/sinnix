import argparse
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-file-catalog"


class Output(io.StringIO):
    def __init__(self, terminal):
        super().__init__()
        self.terminal = terminal

    def isatty(self):
        return self.terminal


def load():
    loader = importlib.machinery.SourceFileLoader("catalog_terminal_fixture", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("terminal", [False, True])
def test_resolved_path_is_terminal_safe_and_pipe_exact(monkeypatch, terminal):
    module = load()
    value = "/neutral/雪\x1b[2J\x9b31m\nentry"
    monkeypatch.setattr(module, "load_catalog", lambda *a, **kw: {})
    monkeypatch.setattr(module, "resolve_historical_path", lambda *a, **kw: value)
    output = Output(terminal)
    with monkeypatch.context() as patch:
        patch.setattr(module.sys, "stdout", output)
        assert module.cmd_resolve(argparse.Namespace(catalog="neutral.json", path="old", id=None)) == 0
    if terminal:
        assert json.loads(output.getvalue()) == value
        assert "\x1b" not in output.getvalue() and "\x9b" not in output.getvalue()
    else:
        assert output.getvalue() == value + "\n"


@pytest.mark.parametrize("terminal", [False, True])
def test_error_paths_cannot_execute_terminal_controls(monkeypatch, terminal):
    module = load()
    value = "unavailable /neutral/\x1b]52;c;neutral\x07"
    output = Output(terminal)
    with monkeypatch.context() as patch:
        patch.setattr(module.sys, "stderr", output)
        assert module.fail(value) == 2
    expected = json.dumps(value, ensure_ascii=True) if terminal else value
    assert output.getvalue() == "sinnix-file-catalog: " + expected + "\n"


@pytest.mark.parametrize("terminal", [False, True])
def test_terminal_quoting_does_not_change_unicode_search(monkeypatch, terminal):
    module = load()
    asset = {"title": "雪", "kind": "file", "current_path": "/neutral/\x9b31m"}
    monkeypatch.setattr(module, "load_catalog", lambda *a, **kw: {"assets": [asset]})
    output = Output(terminal)
    with monkeypatch.context() as patch:
        patch.setattr(module.sys, "stdout", output)
        args = argparse.Namespace(catalog="neutral.json", text="雪", kind=None, offset=0, limit=None)
        assert module.cmd_search(args) == 0
    assert json.loads(output.getvalue()) == asset
    if terminal:
        assert "\x9b" not in output.getvalue()


@pytest.mark.parametrize("terminal", [False, True])
def test_catalog_bytes_do_not_depend_on_terminal(monkeypatch, tmp_path, terminal):
    module = load()
    monkeypatch.setattr(module, "now", lambda: "neutral fixed timestamp")
    catalog = {"assets": [{"title": "雪"}]}
    output = Output(terminal)
    path = tmp_path / "catalog.json"
    with monkeypatch.context() as patch:
        patch.setattr(module.sys, "stdout", output)
        module.write_catalog(path, catalog)
    assert path.read_text() == json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
