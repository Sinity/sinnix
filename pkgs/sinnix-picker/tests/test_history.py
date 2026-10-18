from __future__ import annotations

import json
import os
import tracemalloc

import pytest
from conftest import load_script

picker = load_script("sinnix-picker")


def test_history_late_updates_preserve_first_occurrence_ties(monkeypatch, tmp_path):
    path = tmp_path / "history.jsonl"
    rows = [
        ("b", "01", "b first"),
        ("a", "05", "a"),
        ("d", "00", "d old"),
        ("c", "05", "c"),
        ("b", "05", "b new"),
        ("b", "05", "b equal ignored"),
        ("d", "06", "d new"),
    ]
    path.write_text(
        "\n".join(
            json.dumps(
                {
                    "norm": norm,
                    "iso_time": ts,
                    "title": title,
                    "url": f"https://{norm}.test",
                }
            )
            for norm, ts, title in rows
        )
    )
    monkeypatch.setattr(picker, "HISTORY_PATH", path)
    monkeypatch.setattr(picker, "HISTORY_LIMIT", 3)
    assert [(e.label, e.payload) for e in picker.load_history()] == [
        ("d new", "https://d.test"),
        ("b new", "https://b.test"),
        ("a", "https://a.test"),
    ]


def test_history_norm_title_fallbacks_and_large_payloads(monkeypatch, tmp_path):
    path = tmp_path / "history.jsonl"
    title = "🙂\u2028" + "x" * 150_000
    rows = [
        {"url": "https://one.test", "iso_time": "", "title": ""},
        {"norm": "one", "url": "https://two.test", "iso_time": "later", "title": title},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows))
    monkeypatch.setattr(picker, "HISTORY_PATH", path)
    assert [(e.label, e.payload) for e in picker.load_history()] == [
        (title, "https://two.test"),
        ("https://one.test", "https://one.test"),
    ]


def test_history_does_not_retain_all_unique_payloads(monkeypatch, tmp_path):
    path = tmp_path / "history.jsonl"
    with path.open("w") as handle:
        for i in range(20_000):
            handle.write(
                json.dumps(
                    {
                        "norm": str(i),
                        "iso_time": f"{i:06d}",
                        "title": f"{i}:" + "x" * 512,
                        "url": f"https://{i}.test",
                    }
                )
                + "\n"
            )
    monkeypatch.setattr(picker, "HISTORY_PATH", path)
    monkeypatch.setattr(picker, "HISTORY_LIMIT", 20)
    tracemalloc.start()
    try:
        rows = picker.load_history()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(rows) == 20 and rows[0].payload == "https://19999.test"
    assert peak < 2_000_000


def test_history_rereads_only_selected_record_bytes(monkeypatch, tmp_path):
    path = tmp_path / "history.jsonl"
    lines = [
        json.dumps(
            {"url": f"https://{i}.test", "iso_time": f"{i:03d}", "title": "x" * 500}
        ).encode()
        + b"\n"
        for i in range(100)
    ]
    path.write_bytes(b"".join(lines))
    monkeypatch.setattr(picker, "HISTORY_PATH", path)
    monkeypatch.setattr(picker, "HISTORY_LIMIT", 3)
    original = os.pread
    reads = []

    def counted(fd, size, offset):
        reads.append(size)
        return original(fd, size, offset)

    monkeypatch.setattr(os, "pread", counted)
    assert [row.payload for row in picker.load_history()] == [
        "https://99.test",
        "https://98.test",
        "https://97.test",
    ]
    assert reads == [len(line) for line in reversed(lines[-3:])]


def test_history_temp_failure_closes_database_and_preserves_input(
    monkeypatch, tmp_path, capsys
):
    path = tmp_path / "history.jsonl"
    original = json.dumps({"url": "https://fixture.test"}).encode()
    path.write_bytes(original)
    closed = []
    connect = picker.sqlite3.connect

    class Broken(picker.sqlite3.Connection):
        def executemany(self, *args, **kwargs):
            raise picker.sqlite3.OperationalError("temporary store full fixture")

        def close(self):
            super().close()
            closed.append(True)

    monkeypatch.setattr(
        picker.sqlite3, "connect", lambda _: connect("", factory=Broken)
    )
    monkeypatch.setattr(picker, "HISTORY_PATH", path)
    assert picker.load_history() == []
    assert closed == [True]
    assert "temporary store full fixture" in capsys.readouterr().err
    assert path.read_bytes() == original


@pytest.mark.parametrize("replace", [False, True])
def test_history_offsets_follow_open_inode_and_refuse_in_place_changes(
    monkeypatch, tmp_path, capsys, replace
):
    path = tmp_path / "history.jsonl"
    path.write_text(json.dumps({"url": "https://original.test"}) + "\n")
    connect = picker.sqlite3.connect

    class Changed(picker.sqlite3.Connection):
        def execute(self, statement, *args, **kwargs):
            if statement.startswith("SELECT position"):
                if replace:
                    other = tmp_path / "replacement"
                    other.write_text(
                        json.dumps({"url": "https://replacement.test"}) + "\n"
                    )
                    other.replace(path)
                else:
                    info = path.stat()
                    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 1))
            return super().execute(statement, *args, **kwargs)

    monkeypatch.setattr(
        picker.sqlite3, "connect", lambda _: connect("", factory=Changed)
    )
    monkeypatch.setattr(picker, "HISTORY_PATH", path)
    rows = picker.load_history()
    if replace:
        assert [row.payload for row in rows] == ["https://original.test"]
        assert capsys.readouterr().err == ""
    else:
        assert rows == []
        assert "changed while being read" in capsys.readouterr().err
