"""The hub session page, `explain` and `list`."""

from __future__ import annotations

import argparse
import json


def test_a_session_page_posts_rank_judgments_for_its_domain(
    rank_module, domain, store, tmp_path
):
    store.add_items(
        [
            rank_module.Item(id=i, label=f"option {i}", meta={"description": i})
            for i in "abcd"
        ]
    )

    assert rank_module.cmd_session(argparse.Namespace(domain=domain, pairs=3)) == 0

    [page] = (tmp_path / "report" / "rank" / domain).glob("session-*.html")
    text = page.read_text()
    session = json.loads(text.split("const SESSION = ", 1)[1].split(";\n", 1)[0])
    assert session["schema"] == rank_module.SCHEMA == "sinnix-rank-v1"
    assert session["domain"] == domain
    assert 1 <= len(session["pairs"]) <= 3
    assert all(len(pair) == 2 and set(pair) <= set("abcd") for pair in session["pairs"])
    assert "set: pair, winner: winner" in text


def test_explain_tracks_the_feature_the_choices_follow(rank_module, domain, store):
    store.add_items(
        [
            rank_module.Item(
                id=f"i{n}",
                label=f"item {n}",
                meta={
                    "features": {"brightness": float(n), "noise": float((n * 7) % 5)}
                },
            )
            for n in range(6)
        ]
    )
    for brighter in range(1, 6):
        for darker in range(brighter):
            store.record_comparison(
                [f"i{brighter}", f"i{darker}"], winner=f"i{brighter}", kind="pair"
            )

    items, comparisons, result = rank_module._fit_domain(store)
    report = rank_module.explain(items, comparisons, result)

    top = report["features"][0]
    assert top["feature"] == "brightness"
    assert top["choice_weight"] > 0
    assert top["theta_correlation"] > 0.9
    assert report["n_comparisons_used"] == 15


def test_explain_says_so_when_items_carry_no_features(rank_module, domain, store):
    store.add_items([rank_module.Item(id=i, label=i) for i in "ab"])
    items, comparisons, result = rank_module._fit_domain(store)
    assert "note" in rank_module.explain(items, comparisons, result)


def test_list_names_every_domain(rank_module, domain, store, capsys):
    store.add_items([rank_module.Item(id=i, label=i) for i in "ab"])
    nested = rank_module.Store(rank_module.domain_dir("nested/options"))
    nested.add_items([rank_module.Item(id="x", label="x")])

    rank_module.cmd_list(argparse.Namespace())

    assert capsys.readouterr().out.splitlines() == [
        "nested/options: 1 items, 0 comparisons",
        "wallpaper: 2 items, 0 comparisons",
    ]


def test_record_and_retract_with_next_answer_in_one_call(
    rank_module, domain, store, capsys
):
    """A front end driving a loop gets the recorded id, the next set with item
    metadata, and the evidence from the same process."""
    store.add_items(
        [
            rank_module.Item(id="a", label="option a", meta={"path": "/x/a"}),
            rank_module.Item(id="b", label="option b"),
            rank_module.Item(id="c", label="option c"),
        ]
    )
    parser = rank_module.build_parser()

    args = parser.parse_args(
        ["record", domain, "--set", "a,b", "--winner", "a", "--next"]
    )
    assert args.func(args) == 0
    recorded = json.loads(capsys.readouterr().out)
    assert [c.id for c in store.load_comparisons()] == [recorded["comparison"]]
    following = recorded["next"]
    assert len(following["set"]) == 2
    assert following["evidence"]["operator_comparisons"] == 1
    assert following["evidence"]["settled"] is False
    by_id = {item["id"]: item for item in following["set"]}
    assert "meta" not in by_id.get("b", {}) and "meta" not in by_id.get("c", {})
    if "a" in by_id:
        assert by_id["a"]["meta"] == {"path": "/x/a"}

    args = parser.parse_args(
        ["retract", domain, "--comparison", recorded["comparison"], "--next"]
    )
    assert args.func(args) == 0
    retracted = json.loads(capsys.readouterr().out)
    assert retracted["retracted"] == recorded["comparison"]
    assert retracted["next"]["evidence"]["operator_comparisons"] == 0
    assert store.load_comparisons() == []


def test_next_json_carries_item_metadata(rank_module, domain, store, capsys):
    store.add_items(
        [
            rank_module.Item(id="a", label="option a", meta={"path": "/x/a"}),
            rank_module.Item(id="b", label="option b", meta={"path": "/x/b"}),
        ]
    )
    args = rank_module.build_parser().parse_args(["next", domain, "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {item["meta"]["path"] for item in payload["set"]} == {"/x/a", "/x/b"}
    assert payload["evidence"]["items"] == 2
