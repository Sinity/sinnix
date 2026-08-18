import random

from rank_core.fit import fit
from rank_core.store import Comparison


def make_pair(id_, a, b, winner):
    return Comparison(
        id=id_,
        at="2026-08-18T00:00:00Z",
        kind="pair",
        set=[a, b],
        winner=winner,
        weight=1.0,
    )


def test_fit_recovers_known_preference_order():
    # Ground truth: A > B > C > D. Feed enough noisy-but-consistent-majority
    # pairwise comparisons (round robin, repeated) and expect the fit's
    # theta ordering to match exactly. Mutation check: reversing every
    # winner (A loses to B, etc.) must flip the recovered order too.
    order = ["A", "B", "C", "D"]
    rng = random.Random(7)
    comparisons = []
    i = 0
    for _rep in range(20):
        for x_idx in range(len(order)):
            for y_idx in range(x_idx + 1, len(order)):
                x, y = order[x_idx], order[y_idx]
                # x should beat y (x ranks higher / earlier in `order`); flip
                # a small fraction of outcomes to keep it realistically noisy.
                winner = x if rng.random() > 0.1 else y
                comparisons.append(make_pair(f"c{i}", x, y, winner))
                i += 1

    result = fit(order, comparisons)
    ranked_ids = [r.id for r in result.ranked()]
    assert ranked_ids == order


def test_fit_reversed_outcomes_reverse_order():
    order = ["A", "B", "C", "D"]
    comparisons = [
        make_pair(f"c{i}", x, y, y)  # y (the "loser" in `order`) always wins
        for i, (x, y) in enumerate(
            (order[a], order[b])
            for a in range(len(order))
            for b in range(a + 1, len(order))
        )
    ]
    result = fit(order, comparisons)
    ranked_ids = [r.id for r in result.ranked()]
    assert ranked_ids == list(reversed(order))


def test_fit_choice_set_pl_extension():
    # A 4-wise choice set "A beats {A,B,C,D}" repeated should push A's theta
    # above the other three, which stay roughly tied.
    comparisons = [
        Comparison(
            id=f"c{i}",
            at="2026-08-18T00:00:00Z",
            kind="choice-set",
            set=["A", "B", "C", "D"],
            winner="A",
            weight=1.0,
        )
        for i in range(30)
    ]
    result = fit(["A", "B", "C", "D"], comparisons)
    ranked_ids = [r.id for r in result.ranked()]
    assert ranked_ids[0] == "A"


def test_fit_seeds_items_with_zero_comparisons():
    result = fit(["A", "B", "Z"], [make_pair("c0", "A", "B", "A")])
    assert "Z" in result.records
    assert result.records["Z"].matches == 0
    assert result.records["Z"].se > result.records["A"].se


def test_fit_components_detects_disconnected_islands():
    comparisons = [
        make_pair("c0", "A", "B", "A"),
        make_pair("c1", "C", "D", "C"),
    ]
    result = fit(["A", "B", "C", "D"], comparisons)
    assert result.records["A"].component == result.records["B"].component
    assert result.records["C"].component == result.records["D"].component
    assert result.records["A"].component != result.records["C"].component


def test_fit_tie_splits_into_half_weight_records():
    tie = Comparison(
        id="c0",
        at="2026-08-18T00:00:00Z",
        kind="pair",
        set=["A", "B"],
        winner=None,
        weight=1.0,
    )
    result = fit(["A", "B"], [tie])
    assert abs(result.records["A"].theta - result.records["B"].theta) < 1e-9


def test_fit_decay_reduces_influence_of_old_comparisons():
    # Recent comparisons say B > A repeatedly; old (decayed away) comparisons
    # say A > B. With a short half-life, the recent signal should dominate.
    old = [make_pair(f"old{i}", "A", "B", "A") for i in range(20)]
    for c in old:
        c.at = "2020-01-01T00:00:00Z"
    recent = [make_pair(f"new{i}", "A", "B", "B") for i in range(5)]
    now_epoch = 1755561600.0  # 2025-08-19 (arbitrary "now" fixture)
    result = fit(["A", "B"], old + recent, half_life_days=7, now_epoch=now_epoch)
    assert result.records["B"].theta > result.records["A"].theta
