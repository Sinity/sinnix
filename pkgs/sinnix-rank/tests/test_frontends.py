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
