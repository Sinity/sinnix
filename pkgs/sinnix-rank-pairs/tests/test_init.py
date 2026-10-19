"""Invalid roster replacement must preserve working preferences."""

import argparse
import json

import pytest


@pytest.mark.parametrize(
    "items",
    [
        [{"id": "same"}, {"id": "same"}],
        [{"id": 1}, {"id": "1"}],
        ["id", {"id": "a"}],
    ],
)
@pytest.mark.parametrize("existing", [False, True])
def test_invalid_init_cannot_publish_or_replace(
    elicit_module, domain, tmp_path, items, existing
):
    if existing:
        domain.dir.mkdir(parents=True)
        domain.items_path.write_text(json.dumps([{"id": "a"}, {"id": "b"}]))
        domain.comparisons_path.write_text(
            '{"id":"kept","a":"a","b":"b","outcome":1}\n'
        )
        domain.model_path.write_text('{"retained":"model preimage"}')
    paths = [domain.items_path, domain.comparisons_path, domain.model_path]

    def snapshot():
        return {
            p.name: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
            for p in paths
            if p.exists()
        }

    before = snapshot()
    supplied = tmp_path / "input.json"
    supplied.write_text(json.dumps(items))
    with pytest.raises(SystemExit, match="(duplicate item id|item.*object)"):
        elicit_module.cmd_init(
            domain,
            argparse.Namespace(
                items=str(supplied), force=existing, image_features=False
            ),
        )
    assert snapshot() == before
    if not existing:
        assert not domain.dir.exists()


def test_valid_replacement_keeps_identity_rules_and_history(
    elicit_module, domain, tmp_path
):
    domain.dir.mkdir(parents=True)
    domain.items_path.write_text(json.dumps([{"id": "a"}, {"id": "b"}, {"id": "c"}]))
    raw = '{"id":"kept","a":"a","b":"c","outcome":1}\n'
    domain.comparisons_path.write_text(raw)
    items = [{"id": "a", "label": "same label"}, {"id": "b", "label": "same label"}]
    supplied = tmp_path / "input.json"
    supplied.write_text(json.dumps(items))
    elicit_module.cmd_init(
        domain,
        argparse.Namespace(items=str(supplied), force=True, image_features=False),
    )
    assert domain.load_items()[0] == items
    assert domain.comparisons_path.read_text() == raw


def test_small_roster_remains_readable(elicit_module, domain):
    domain.dir.mkdir(parents=True)
    for items in ([], [{"id": "a"}]):
        domain.items_path.write_text(json.dumps(items))
        assert domain.load_items()[0] == items


def test_invalid_roster_fails_before_feature_extraction(
    elicit_module, domain, tmp_path, monkeypatch
):
    supplied = tmp_path / "input.json"
    supplied.write_text(
        json.dumps([{"id": "same", "image": "neutral.png"}, {"id": "same"}])
    )

    def no_features(*args, **kwargs):
        raise AssertionError("invalid roster must fail before feature extraction")

    monkeypatch.setattr(elicit_module.subprocess, "run", no_features)
    with pytest.raises(SystemExit, match="duplicate item id"):
        elicit_module.cmd_init(
            domain,
            argparse.Namespace(items=str(supplied), force=False, image_features=True),
        )
    assert not domain.dir.exists()
