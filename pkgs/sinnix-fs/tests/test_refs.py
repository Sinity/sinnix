import sys
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__import__("sinnix_fs.layout", fromlist=["__file__"]).__file__)


def load_refs():
    loader = SourceFileLoader("realm_refs", str(SCRIPT))
    spec = spec_from_loader(loader.name, loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("failure", ["missing", "file", "rg", "spawn"])
def test_unavailable_scan_fails_rather_than_passing(
    tmp_path, monkeypatch, capsys, failure
):
    refs = load_refs()
    root = tmp_path / "source"
    if failure == "file":
        root.write_text("wrong object type")
    elif failure != "missing":
        root.mkdir()
    monkeypatch.setattr(refs, "REPOS", {"fixture": root})
    if failure == "rg":
        monkeypatch.setattr(
            refs.subprocess,
            "run",
            lambda *a, **kw: SimpleNamespace(
                returncode=2, stdout="", stderr="synthetic scan failure"
            ),
        )
    elif failure == "spawn":

        def fail(*args, **kwargs):
            raise OSError("synthetic unavailable executable")

        monkeypatch.setattr(refs.subprocess, "run", fail)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--refs"])
    assert refs.main() == 2
    assert "sinnix fs layout:" in capsys.readouterr().err


def test_readable_empty_source_is_a_valid_empty_result(tmp_path):
    refs = load_refs()
    assert refs.scan_repo("fixture", tmp_path) == []


@pytest.mark.parametrize(
    "existing,expected",
    [
        ({"/realm"}, "/realm"),
        ({"/realm", "/realm/subject"}, "/realm/subject"),
        ({"/"}, None),
    ],
)
def test_missing_path_reports_nearest_managed_ancestor(monkeypatch, existing, expected):
    from pathlib import PurePosixPath

    refs = load_refs()

    class SyntheticPath(PurePosixPath):
        def stat(self):
            if str(self) not in existing:
                raise FileNotFoundError(str(self))
            return SimpleNamespace(st_mode=0o40700)

    monkeypatch.setattr(refs, "Path", SyntheticPath)
    actual = refs.existing_ancestor("/realm/subject/missing")
    assert (str(actual) if actual is not None else None) == expected


def test_source_roles_retain_fixtures_and_documentation_without_live_false_alarms(
    tmp_path,
):
    refs = load_refs()
    paths = {
        "src/reader.py": '"""Example:\n/realm/example/doc\n"""\nROOT = "/realm/runtime/source"\nCOMMAND = """/realm/runtime/command"""\n',
        "scripts/tool": '#!/usr/bin/env python3\n"""Example:\n/realm/example/script\n"""\nROOT = "/realm/runtime/script"\n',
        "scripts/bash-tool": '#!/bin/sh\n"/realm/runtime/bash"\n',
        "src/unparsed.py": 'print "/realm/runtime/unparsed"\n',
        "tests/test_reader.py": 'ROOT = "/realm/fixture/tests"\n',
        "pkgs/worker/test_worker.py": 'ROOT = "/realm/fixture/package"\n',
        "flake/tests/runtime.nix": 'root = "/realm/fixture/vm";\n',
    }
    for name, text in paths.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    rows = refs.scan_repo("fixture", tmp_path)
    by_path = {row["path"]: row["kind"] for row in rows}
    assert by_path == {
        "/realm/example/doc": "cosmetic",
        "/realm/example/script": "cosmetic",
        "/realm/runtime/script": "live",
        "/realm/runtime/bash": "live",
        "/realm/runtime/unparsed": "live",
        "/realm/runtime/source": "live",
        "/realm/runtime/command": "live",
        "/realm/fixture/tests": "fixture",
        "/realm/fixture/package": "fixture",
        "/realm/fixture/vm": "fixture",
    }


@pytest.mark.parametrize(
    "filename", ["reader:legacy.py", "reader\ncurrent.py", "reader\rcurrent.py"]
)
def test_source_filename_separators_do_not_corrupt_rg_records(tmp_path, filename):
    refs = load_refs()
    source = tmp_path / filename
    source.write_text('ROOT = "/realm/synthetic/capture"\n')
    assert refs.scan_repo("fixture", tmp_path) == [
        {
            "repo": "fixture",
            "file": str(source),
            "line": 1,
            "path": "/realm/synthetic/capture",
            "kind": "live",
        }
    ]


def test_malformed_rg_record_fails_rather_than_passing(tmp_path, monkeypatch):
    refs = load_refs()
    monkeypatch.setattr(refs, "REPOS", {"fixture": tmp_path})
    monkeypatch.setattr(
        refs.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            returncode=0, stdout="malformed JSON\n", stderr=""
        ),
    )
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--refs"])
    assert refs.main() == 2


@pytest.mark.parametrize("failure", [PermissionError, NotADirectoryError])
@pytest.mark.parametrize("operation", ["check", "ancestor"])
def test_uninspectable_reference_is_not_reported_missing(
    monkeypatch, capsys, failure, operation
):
    refs = load_refs()
    target = Path("/realm/synthetic/private/record")
    original_stat = Path.stat

    def inspect(path, *args, **kwargs):
        if path == target:
            raise failure(13, "synthetic inspection failure", str(path))
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", inspect)
    if operation == "ancestor":
        with pytest.raises(failure):
            refs.existing_ancestor(str(target))
    else:
        monkeypatch.setattr(
            refs,
            "scan",
            lambda: [
                {
                    "kind": "live",
                    "path": str(target),
                    "repo": "fixture",
                    "file": "reader.py",
                    "line": 1,
                }
            ],
        )
        monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--refs"])
        assert refs.main() == 2
        err = capsys.readouterr().err
        assert "synthetic inspection failure" in err
        assert "do not exist" not in err
