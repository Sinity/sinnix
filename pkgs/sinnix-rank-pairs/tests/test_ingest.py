"""`ingest` drains the hub spool into a domain exactly once per judgment.

The drain runs on every arriving comparison (the `rank_pairs_ingest` operation), so a
record it fails to recognise as already-seen is appended again on every burst.
"""

from __future__ import annotations

import argparse
import json
import os


def write_items(domain, ids=("a", "b", "c")):
    domain.dir.mkdir(parents=True, exist_ok=True)
    domain.items_path.write_text(json.dumps([{"id": i} for i in ids]))


def spool(elicit, records):
    path = elicit.FEEDBACK_DIR / "2026-09-05.jsonl"
    with path.open("a") as handle:
        for record in records:
            handle.write(json.dumps({"payload": record}) + "\n")


def judgment(elicit, record_id, a="a", b="b", outcome=1.0):
    return {
        "schema": elicit.SCHEMA,
        "domain": "wallpaper",
        "id": record_id,
        "a": a,
        "b": b,
        "outcome": outcome,
        "at": "2026-09-05T10:00:00Z",
    }


def raw_ids(domain):
    if not domain.comparisons_path.exists():
        return []
    return [
        json.loads(line).get("id")
        for line in domain.comparisons_path.read_text().splitlines()
        if line.strip() and "delete" not in json.loads(line)
    ]


def test_a_tombstoned_record_is_not_re_imported(elicit_module, domain, capsys):
    """The live wallpaper log holds 3,045 copies of one undone record because
    dedup asked `load_comparisons`, which drops tombstoned rows. A record the
    operator undid is still a record this domain has seen."""
    write_items(domain)
    spool(elicit_module, [judgment(elicit_module, "smoke-1")])
    args = argparse.Namespace()

    elicit_module.cmd_ingest(domain, args)
    domain.append({"delete": "smoke-1"})
    assert domain.load_comparisons() == []

    for _ in range(5):
        elicit_module.cmd_ingest(domain, args)

    assert raw_ids(domain) == ["smoke-1"]
    assert domain.load_comparisons() == []
    assert "ingested 0 comparisons" in capsys.readouterr().out


def test_repeated_drains_import_each_judgment_once(elicit_module, domain, capsys):
    write_items(domain)
    spool(
        elicit_module,
        [judgment(elicit_module, "one"), judgment(elicit_module, "two", b="c")],
    )
    args = argparse.Namespace()

    elicit_module.cmd_ingest(domain, args)
    assert "ingested 2 comparisons" in capsys.readouterr().out
    elicit_module.cmd_ingest(domain, args)
    assert "ingested 0 comparisons" in capsys.readouterr().out
    assert sorted(raw_ids(domain)) == ["one", "two"]


def test_an_undo_posted_from_the_page_tombstones_once(elicit_module, domain, capsys):
    write_items(domain)
    spool(
        elicit_module,
        [
            judgment(elicit_module, "one"),
            {"schema": elicit_module.SCHEMA, "domain": "wallpaper", "delete": "one"},
        ],
    )
    args = argparse.Namespace()

    elicit_module.cmd_ingest(domain, args)
    out = capsys.readouterr().out
    assert "ingested 1 comparisons, 1 undos" in out

    elicit_module.cmd_ingest(domain, args)
    assert "ingested 0 comparisons, 0 undos" in capsys.readouterr().out
    tombstones = [
        line
        for line in domain.comparisons_path.read_text().splitlines()
        if "delete" in json.loads(line)
    ]
    assert len(tombstones) == 1


def test_records_for_another_domain_or_schema_are_left_alone(elicit_module, domain):
    write_items(domain)
    spool(
        elicit_module,
        [
            dict(judgment(elicit_module, "other-domain"), domain="keybinds"),
            dict(judgment(elicit_module, "other-schema"), schema="something-else"),
            {"schema": elicit_module.SCHEMA, "domain": "wallpaper", "id": "malformed"},
        ],
    )
    elicit_module.cmd_ingest(domain, argparse.Namespace())
    assert raw_ids(domain) == []


def test_the_default_state_root_is_the_owned_one(elicit_module):
    """Instantiated from the module default, not an env override: nothing sets
    SINNIX_ELICIT_DIR for the installed tool."""
    assert os.environ.get("SINNIX_ELICIT_DIR") is None
    assert str(elicit_module.BASE_DIR) == "/realm/state/elicit"
    assert (
        str(elicit_module.Domain("wallpaper").model_path)
        == "/realm/state/elicit/wallpaper/model.json"
    )


def test_balanced_undo_and_new_answer_refreshes_model(elicit_module, domain):
    write_items(domain)
    domain.append(judgment(elicit_module, "old"))
    elicit_module.cmd_rank(domain, argparse.Namespace(json=False))
    assert json.loads(domain.model_path.read_text())["ranking"][0]["id"] == "a"
    spool(elicit_module, [
        {"schema": elicit_module.SCHEMA, "domain": domain.name, "delete": "old"},
        judgment(elicit_module, "new", outcome=0.0),
    ])
    elicit_module.cmd_autoingest(None, argparse.Namespace())
    model = json.loads(domain.model_path.read_text())
    assert model["n_comparisons"] == 1
    assert model["ranking"][0]["id"] == "b"


def test_failed_refit_retries_without_new_feedback(elicit_module, domain, monkeypatch):
    import pytest

    write_items(domain)
    spool(elicit_module, [judgment(elicit_module, "one")])
    original = elicit_module.fit_and_save_model
    with monkeypatch.context() as patch:
        def fail(*args):
            raise RuntimeError("synthetic fit failure")
        patch.setattr(elicit_module, "fit_and_save_model", fail)
        with pytest.raises(RuntimeError, match="synthetic fit failure"):
            elicit_module.cmd_autoingest(None, argparse.Namespace())
    assert len(domain.load_comparisons()) == 1
    assert not domain.model_path.exists()
    elicit_module.cmd_autoingest(None, argparse.Namespace())
    assert json.loads(domain.model_path.read_text())["n_comparisons"] == 1
    assert elicit_module.fit_and_save_model is original


def test_roster_change_refreshes_model_once(elicit_module, domain):
    write_items(domain)
    domain.append(judgment(elicit_module, "one"))
    elicit_module.cmd_rank(domain, argparse.Namespace(json=False))
    items = json.loads(domain.items_path.read_text())
    items[0]["label"] = "revised option label"
    domain.items_path.write_text(json.dumps(items))
    elicit_module.cmd_autoingest(None, argparse.Namespace())
    model = json.loads(domain.model_path.read_text())
    assert model["ranking"][0]["label"] == "revised option label"
    before = domain.model_path.read_bytes(), domain.model_path.stat().st_mtime_ns
    elicit_module.cmd_autoingest(None, argparse.Namespace())
    assert (domain.model_path.read_bytes(), domain.model_path.stat().st_mtime_ns) == before


def test_domain_paths_cannot_escape_state_root(elicit_module, tmp_path, monkeypatch):
    import pytest

    root = tmp_path / "elicit"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(elicit_module, "BASE_DIR", root)
    for name in ("", ".", "..", "../outside", str(outside), "escape", "escape/child"):
        with pytest.raises(ValueError, match="domain"):
            elicit_module.Domain(name)
    assert elicit_module.Domain("nested/options").dir == root / "nested/options"
