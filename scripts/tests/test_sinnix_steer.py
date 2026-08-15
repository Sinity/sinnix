"""Smoke tests for the steering store CLI (`scripts/sinnix-steer`, sinnix-jfiy.1).

Loaded via importlib since the script has no `.py` suffix (frontmatter-packaged,
executed by its shebang) — same pattern as test_capture_notifications_listener.py.
"""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "sinnix-steer"

_loader = SourceFileLoader("sinnix_steer", str(SCRIPT_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec is not None
steer = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = steer
_loader.exec_module(steer)


def _use_tmp_store(tmp_path, monkeypatch):
    store_dir = tmp_path / "steering"
    export_dir = tmp_path / "export"
    monkeypatch.setattr(steer, "STORE_DIR", store_dir)
    monkeypatch.setattr(steer, "STORE_PATH", store_dir / "steering.sqlite")
    monkeypatch.setattr(steer, "EXPORT_DIR", export_dir)


def test_schema_creates_on_first_connect(tmp_path, monkeypatch):
    _use_tmp_store(tmp_path, monkeypatch)
    conn = steer.get_db()
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"commitments", "activities", "reviews"} <= tables


def test_intent_add_list_roundtrip(tmp_path, monkeypatch, capsys):
    _use_tmp_store(tmp_path, monkeypatch)
    args = steer.build_parser().parse_args(
        ["intent", "add", "write the thing", "--forecast", "0.7"]
    )
    assert steer.cmd_intent_add(args) == 0
    capsys.readouterr()

    list_args = steer.build_parser().parse_args(["intent", "list", "--json"])
    assert steer.cmd_intent_list(list_args) == 0
    out = capsys.readouterr().out
    assert "write the thing" in out
    assert "0.7" in out


def test_intent_done_requires_open_status(tmp_path, monkeypatch, capsys):
    _use_tmp_store(tmp_path, monkeypatch)
    add_args = steer.build_parser().parse_args(["intent", "add", "task"])
    steer.cmd_intent_add(add_args)
    capsys.readouterr()

    conn = steer.get_db()
    cid = conn.execute("SELECT id FROM commitments").fetchone()["id"]

    done_args = steer.build_parser().parse_args(["intent", "done", cid])
    assert steer.cmd_intent_done(done_args) == 0

    # Second done on an already-closed commitment must fail (rowcount == 0 path).
    assert steer.cmd_intent_done(done_args) == 1


def test_activity_menu_filters_by_energy_or_any(tmp_path, monkeypatch, capsys):
    _use_tmp_store(tmp_path, monkeypatch)
    for name, kind, energy in [
        ("deep work", "task", "good"),
        ("read a book", "leisure", "low"),
        ("check email", "task", "any"),
    ]:
        args = steer.build_parser().parse_args(
            ["activity", "add", name, "--kind", kind, "--energy", energy]
        )
        steer.cmd_activity_add(args)
    capsys.readouterr()

    menu_args = steer.build_parser().parse_args(
        ["activity", "menu", "--energy", "low", "--json"]
    )
    steer.cmd_activity_menu(menu_args)
    out = capsys.readouterr().out
    assert "read a book" in out
    assert "check email" in out  # energy_tier == 'any' always included
    assert "deep work" not in out


def test_seed_is_idempotent_and_includes_experiment(tmp_path, monkeypatch, capsys):
    _use_tmp_store(tmp_path, monkeypatch)
    seed_args = steer.build_parser().parse_args(["seed"])

    assert steer.cmd_seed(seed_args) == 0
    first_out = capsys.readouterr().out
    assert f"seeded {len(steer.SEED_ACTIVITIES) + 1} new activities" in first_out

    conn = steer.get_db()
    experiment = conn.execute(
        "SELECT * FROM activities WHERE kind = 'experiment'"
    ).fetchone()
    assert experiment["name"] == "sleep-schedule stabilization"
    assert experiment["hypothesis"] is not None
    assert "PLACEHOLDER" in experiment["prereg_prediction"]

    # Second run must be a no-op (idempotent on activity name).
    assert steer.cmd_seed(seed_args) == 0
    second_out = capsys.readouterr().out
    assert "seeded 0 new activities" in second_out
    total = conn.execute("SELECT COUNT(*) AS n FROM activities").fetchone()["n"]
    assert total == len(steer.SEED_ACTIVITIES) + 1


def test_export_writes_jsonl(tmp_path, monkeypatch, capsys):
    _use_tmp_store(tmp_path, monkeypatch)
    add_args = steer.build_parser().parse_args(["intent", "add", "exportable"])
    steer.cmd_intent_add(add_args)
    capsys.readouterr()

    export_args = steer.build_parser().parse_args(["export"])
    assert steer.cmd_export(export_args) == 0
    files = list((tmp_path / "export").glob("*.jsonl"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "exportable" in content
