"""`ingest` drains the hub spool into domains exactly once per judgment.

The drain runs on every arriving judgment (the `rank_ingest` operation), so a
record it fails to recognise as already-seen is appended again on every burst.
"""

from __future__ import annotations

import argparse
import json

import pytest


def write_items(rank, store, ids=("a", "b", "c")):
    store.add_items([rank.Item(id=i, label=f"option {i}") for i in ids])


def spool(rank, records):
    path = rank.FEEDBACK_DIR / "2026-09-05.jsonl"
    with path.open("a") as handle:
        for record in records:
            handle.write(json.dumps({"payload": record}) + "\n")


def judgment(rank, record_id, members=("a", "b"), winner="a", domain="wallpaper"):
    return {
        "schema": rank.SCHEMA,
        "domain": domain,
        "session": "20260905-100000",
        "id": record_id,
        "set": list(members),
        "winner": winner,
        "at": "2026-09-05T10:00:00Z",
    }


def raw_records(store):
    if not store.comparisons_path.exists():
        return []
    return [
        json.loads(line)
        for line in store.comparisons_path.read_text().splitlines()
        if line.strip()
    ]


def raw_ids(store):
    return [r.get("id") for r in raw_records(store) if "delete" not in r]


def ingest(rank, *domains):
    return rank.cmd_ingest(argparse.Namespace(domains=list(domains)))


def test_a_judgment_lands_in_the_store_record_shape(rank_module, store):
    write_items(rank_module, store)
    spool(rank_module, [judgment(rank_module, "one", winner="b")])

    ingest(rank_module)

    [record] = raw_records(store)
    assert record["kind"] == "pair"
    assert record["set"] == ["a", "b"]
    assert record["winner"] == "b"
    assert record["context"] == "20260905-100000"
    assert [c.winner for c in store.load_comparisons()] == ["b"]


def test_a_tie_is_a_pair_without_a_winner(rank_module, store):
    write_items(rank_module, store)
    spool(rank_module, [judgment(rank_module, "tie", winner=None)])

    ingest(rank_module)

    [comparison] = store.load_comparisons()
    assert comparison.kind == "pair" and comparison.winner is None


def test_a_tombstoned_record_is_not_re_imported(rank_module, store, capsys):
    """A record the operator undid is still a record this domain has seen;
    deduping against the live comparisons re-imports it on every drain."""
    write_items(rank_module, store)
    spool(rank_module, [judgment(rank_module, "smoke-1")])

    ingest(rank_module)
    store.undo("smoke-1")
    assert store.load_comparisons() == []

    for _ in range(5):
        ingest(rank_module)

    assert raw_ids(store) == ["smoke-1"]
    assert store.load_comparisons() == []
    assert "ingested 0 judgments" in capsys.readouterr().out


def test_repeated_drains_import_each_judgment_once(rank_module, store, capsys):
    write_items(rank_module, store)
    spool(
        rank_module,
        [judgment(rank_module, "one"), judgment(rank_module, "two", ("a", "c"))],
    )

    ingest(rank_module)
    assert "ingested 2 judgments" in capsys.readouterr().out
    ingest(rank_module)
    assert "ingested 0 judgments" in capsys.readouterr().out
    assert sorted(raw_ids(store)) == ["one", "two"]


def test_an_undo_posted_from_the_page_tombstones_once(rank_module, store, capsys):
    write_items(rank_module, store)
    spool(
        rank_module,
        [
            judgment(rank_module, "one"),
            {"schema": rank_module.SCHEMA, "domain": "wallpaper", "delete": "one"},
        ],
    )

    ingest(rank_module)
    assert "ingested 1 judgments, 1 undos" in capsys.readouterr().out
    ingest(rank_module)
    assert "ingested 0 judgments, 0 undos" in capsys.readouterr().out
    assert len([r for r in raw_records(store) if "delete" in r]) == 1


def test_records_outside_the_domain_or_roster_are_left_alone(rank_module, store):
    write_items(rank_module, store)
    spool(
        rank_module,
        [
            judgment(rank_module, "other-domain", domain="keybinds"),
            dict(judgment(rank_module, "other-schema"), schema="something-else"),
            {"schema": rank_module.SCHEMA, "domain": "wallpaper", "id": "malformed"},
            judgment(rank_module, "unknown-item", ("a", "zzz")),
            judgment(rank_module, "foreign-winner", winner="c"),
            judgment(rank_module, "self-pair", ("a", "a")),
        ],
    )
    ingest(rank_module)
    assert raw_ids(store) == []


def test_a_named_domain_limits_the_drain(rank_module, domain, capsys):
    for name in ("wallpaper", "themes"):
        write_items(rank_module, rank_module.Store(rank_module.domain_dir(name)))
    spool(
        rank_module,
        [judgment(rank_module, "w1"), judgment(rank_module, "t1", domain="themes")],
    )

    ingest(rank_module, "themes")

    themes = rank_module.Store(rank_module.domain_dir("themes"))
    wallpaper = rank_module.Store(rank_module.domain_dir("wallpaper"))
    assert raw_ids(themes) == ["t1"]
    assert raw_ids(wallpaper) == []


def test_the_default_root_is_the_shared_ranking_capture(monkeypatch):
    """Instantiated from the module default, not an env override."""
    import importlib

    monkeypatch.delenv("SINNIX_RANK_ROOT", raising=False)
    from conftest import _load

    fresh = _load()
    importlib.invalidate_caches()
    assert str(fresh.CAPTURE_ROOT) == "/realm/activity/shared/ranking"


def test_domain_paths_cannot_escape_the_root(rank_module, tmp_path, monkeypatch):
    root = tmp_path / "ranking"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(rank_module, "CAPTURE_ROOT", root)
    for name in ("", ".", "..", "../outside", str(outside), "escape", "escape/child"):
        with pytest.raises(ValueError, match="domain"):
            rank_module.domain_dir(name)
    assert rank_module.domain_dir("nested/options") == root / "nested/options"
