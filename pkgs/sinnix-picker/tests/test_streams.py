from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import load_script

picker = load_script("sinnix-picker")


def test_clipboard_preserves_oversized_utf8_record(monkeypatch, tmp_path):
    monkeypatch.setattr(picker, "CLIPBOARD_DIR", tmp_path)
    monkeypatch.setattr(picker, "CLIPBOARD_LIMIT", 1)
    text = "before\u2028middle\u0085after🙂\n" + "x" * 150_000
    rows = [
        {"payload": {"category": "text", "text": "older"}},
        {"payload": {"category": "text", "text": text}},
    ]
    (tmp_path / "clipboard-20261018.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    )
    [entry] = picker.load_clipboard()
    assert entry.payload == text


def test_clipboard_never_reads_metadata_index(monkeypatch, tmp_path):
    monkeypatch.setattr(picker, "CLIPBOARD_DIR", tmp_path)
    index = tmp_path / "clipboard-index.jsonl"
    index.mkdir()  # A wrong-type metadata sidecar is still not a payload input.
    (tmp_path / "clipboard-20261018.jsonl").write_text(
        json.dumps({"payload": {"category": "text", "text": "retained"}}) + "\n"
    )
    real_open = os.open
    real_read_text = Path.read_text

    def checked_text(path, *args, **kwargs):
        assert path != index, "metadata index opened as payload"
        return real_read_text(path, *args, **kwargs)

    def checked_open(path, *args, **kwargs):
        assert os.fspath(path) != str(index), "metadata index opened as payload"
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", checked_open)
    monkeypatch.setattr(Path, "read_text", checked_text)
    assert picker.load_clipboard()[0].payload == "retained"


def test_reverse_reader_stops_at_recent_tail():
    class Counted(io.BytesIO):
        count = 0

        def read(self, size=-1):
            assert 0 <= size <= 65536
            result = super().read(size)
            self.count += len(result)
            return result

    source = Counted(b"old\n" * 100_000 + b"latest\n")
    assert next(row for row in picker._reverse_lines(source) if row) == b"latest"
    assert source.count <= 65536


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"first\nsecond\n", [b"second", b"first"]),
        (b"first\r\nsecond", [b"second", b"first\r"]),
        (b"first\n\nsecond", [b"second", b"first"]),
    ],
)
def test_reverse_reader_line_boundaries(raw, expected):
    assert [row for row in picker._reverse_lines(io.BytesIO(raw)) if row] == expected


def test_bookmarks_top_rows_match_stable_sort(monkeypatch, tmp_path):
    path = tmp_path / "bookmarks.csv"
    rows = [
        ("2026-01-01", "older", "", "https://old.example"),
        ("2026-02-01", "first tie", "folder", "https://one.example"),
        ("2026-02-01", "second tie", "", "https://two.example"),
        ("2026-03-01", "latest", "", "https://new.example"),
    ]
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("created", "title", "folder", "url"))
        writer.writerows(rows)
    monkeypatch.setattr(picker, "RAINDROP_CSV", path)
    monkeypatch.setattr(picker, "RAINDROP_LIMIT", 3)
    assert [(e.label, e.payload) for e in picker.load_raindrop()] == [
        ("latest", "https://new.example"),
        ("first tie (folder)", "https://one.example"),
        ("second tie", "https://two.example"),
    ]


def test_bookmarks_do_not_retain_all_candidate_strings(monkeypatch, tmp_path):
    class Value(str):
        live = 0
        peak = 0

        def __new__(cls, text):
            result = super().__new__(cls, text)
            cls.live += 1
            cls.peak = max(cls.live, cls.peak)
            return result

        def __del__(self):
            type(self).live -= 1

    def rows(*args, **kwargs):
        for i in range(10_000):
            yield {
                "created": Value(f"{i:08d}"),
                "title": Value(f"title{i}"),
                "folder": "",
                "url": Value(f"https://{i}.example"),
            }

    path = tmp_path / "bookmarks.csv"
    path.touch()
    monkeypatch.setattr(picker, "RAINDROP_CSV", path)
    monkeypatch.setattr(picker, "RAINDROP_LIMIT", 5)
    monkeypatch.setattr(picker.csv, "DictReader", rows)
    assert len(picker.load_raindrop()) == 5
    assert Value.peak < 100


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses read permissions")
@pytest.mark.parametrize("lane", ["clipboard", "bookmarks"])
def test_denied_source_is_diagnosed(monkeypatch, tmp_path, capsys, lane):
    path = tmp_path / lane
    if lane == "clipboard":
        path.mkdir()
        monkeypatch.setattr(picker, "CLIPBOARD_DIR", path)
        loader = picker.load_clipboard
    else:
        path.touch()
        monkeypatch.setattr(picker, "RAINDROP_CSV", path)
        loader = picker.load_raindrop
    path.chmod(0)
    try:
        assert loader() == []
        assert "unavailable" in capsys.readouterr().err
    finally:
        path.chmod(0o700 if lane == "clipboard" else 0o600)


def test_absent_optional_sources_are_supported(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(picker, "CLIPBOARD_DIR", tmp_path / "absent")
    monkeypatch.setattr(picker, "RAINDROP_CSV", tmp_path / "absent.csv")
    assert picker.load_clipboard() == picker.load_raindrop() == []
    assert capsys.readouterr().err == ""


def test_clipboard_wrong_root_type_is_diagnosed(monkeypatch, tmp_path, capsys):
    path = tmp_path / "wrong-root"
    path.touch()
    monkeypatch.setattr(picker, "CLIPBOARD_DIR", path)
    assert picker.load_clipboard() == []
    assert "unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("lane", ["clipboard", "bookmarks"])
def test_special_sources_do_not_block(tmp_path, lane):
    path = tmp_path / (
        "clipboard-20261018.jsonl" if lane == "clipboard" else "bookmarks.csv"
    )
    os.mkfifo(path)
    code = """
import importlib.util,sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
loader=SourceFileLoader('fixture_picker',sys.argv[1])
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec);sys.modules[loader.name]=module;loader.exec_module(module)
path=Path(sys.argv[2])
if sys.argv[3]=='clipboard': module.CLIPBOARD_DIR=path.parent; rows=module.load_clipboard()
else: module.RAINDROP_CSV=path; rows=module.load_raindrop()
assert rows==[]
"""
    result = subprocess.run(
        [sys.executable, "-c", code, picker.__file__, str(path), lane],
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode == 0, result.stderr
    assert "unavailable" in result.stderr
