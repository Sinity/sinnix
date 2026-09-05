"""`ask`, `session` and `pairs` ask the questions the shared engine chooses.

Selection used to be this file's own resorter heuristic, which never crossed
connected components and deduped only against pairs carrying `a`/`b`. These
assert the shared behaviour through `pick_pairs`, which every one of the three
surfaces calls.
"""

from __future__ import annotations

import random


def roster(n):
    return [{"id": f"i{k}", "label": f"Item {k}"} for k in range(n)]


def judged(record_id, a, b, outcome=1.0):
    return {"id": record_id, "kind": "pair", "a": a, "b": b, "outcome": outcome}


def split_domain():
    """Six items in two islands: {i0,i1,i2} and {i3,i4,i5}, never crossed."""
    items = roster(6)
    comparisons = [
        judged("c0", "i0", "i1"),
        judged("c1", "i1", "i2"),
        judged("c2", "i3", "i4"),
        judged("c3", "i4", "i5"),
    ]
    return items, comparisons


def side(item_id):
    return "left" if int(item_id[1:]) < 3 else "right"


def test_the_first_pair_bridges_a_split_domain(elicit_module):
    items, comparisons = split_domain()
    for seed in range(20):
        pairs, _ = elicit_module.pick_pairs(
            items, comparisons, 1, rng=random.Random(seed)
        )
        assert len(pairs) == 1
        assert {side(i) for i in pairs[0]} == {"left", "right"}


def test_an_answered_pair_is_not_asked_again(elicit_module):
    items, comparisons = split_domain()
    answered = {frozenset((c["a"], c["b"])) for c in comparisons}
    pairs, _ = elicit_module.pick_pairs(items, comparisons, 6, rng=random.Random(3))

    offered = [frozenset(pair) for pair in pairs]
    assert not (set(offered) & answered)
    assert len(set(offered)) == len(offered)


def test_a_session_asks_no_more_pairs_than_the_domain_holds(elicit_module):
    items = roster(4)
    pairs, _ = elicit_module.pick_pairs(items, [], 20, rng=random.Random(1))

    assert len(pairs) == 6  # four items have six distinct pairs
    assert len({frozenset(pair) for pair in pairs}) == 6


def test_pick_pairs_reports_the_fit_the_surfaces_display(elicit_module):
    items, comparisons = split_domain()
    _pairs, records = elicit_module.pick_pairs(
        items, comparisons, 1, rng=random.Random(0)
    )

    assert set(records) == {item["id"] for item in items}
    assert all(record["se"] > 0 for record in records.values())
