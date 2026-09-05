import random

from rank_core.fit import fit
from rank_core.selection import Selector, build_selector
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


def test_selector_bridges_disconnected_components():
    # Two islands {A,B} and {C,D} with zero cross-comparisons: the fit must
    # report two components, and the selector -- once fed that fit -- must
    # schedule a bridging pick (an item from each island in the same set)
    # within its bridge_every window rather than never crossing.
    items = ["A", "B", "C", "D"]
    comparisons = [make_pair("c0", "A", "B", "A"), make_pair("c1", "C", "D", "C")]
    result = fit(items, comparisons)
    components = {r.id: r.component for r in result.records.values()}
    assert (
        len({components["A"], components["C"]}) == 2
    )  # sanity: genuinely disconnected

    selector = Selector(
        item_ids=items,
        grid_n=2,
        bridge_every=3,
        explore_every=1000,
        rng=random.Random(1),
    )
    selector.update_fit(result)

    saw_bridge = False
    for _ in range(9):  # 3x bridge_every guarantees at least one scheduled tick
        chosen, strategy = selector.pick_set()
        if strategy == "bridge":
            saw_bridge = True
            assert len({components[i] for i in chosen}) == 2
    assert saw_bridge


def test_selector_no_bridge_when_single_component():
    items = ["A", "B", "C", "D"]
    comparisons = [
        make_pair("c0", "A", "B", "A"),
        make_pair("c1", "B", "C", "B"),
        make_pair("c2", "C", "D", "C"),
    ]
    result = fit(items, comparisons)
    selector = Selector(
        item_ids=items,
        grid_n=2,
        bridge_every=1,
        explore_every=1000,
        rng=random.Random(1),
    )
    selector.update_fit(result)
    for _ in range(5):
        _, strategy = selector.pick_set()
        assert strategy != "bridge"


def test_selector_bridges_a_disconnected_domain_on_its_first_pick():
    # A single-question caller (`sinnix-rank next`, `sinnix-elicit ask`) builds
    # one selector and takes one pick from it, so a bridge that first comes due
    # on a later tick never happens at all: the components stay incomparable
    # however many questions the operator answers.
    items = [f"left-{n}" for n in range(6)] + [f"right-{n}" for n in range(6)]
    comparisons = [
        make_pair(f"l{n}", f"left-{n}", f"left-{n + 1}", f"left-{n}") for n in range(5)
    ] + [
        make_pair(f"r{n}", f"right-{n}", f"right-{n + 1}", f"right-{n}")
        for n in range(5)
    ]
    result = fit(items, comparisons)
    components = {r.id: r.component for r in result.records.values()}
    assert len({components[i] for i in items}) == 2  # sanity: genuinely split

    for seed in range(20):
        selector = build_selector(items, comparisons, result, rng=random.Random(seed))
        chosen, strategy = selector.pick_set()
        assert strategy == "bridge"
        assert len({components[i] for i in chosen}) == 2


def test_selector_does_not_re_ask_a_set_already_put_to_the_operator():
    items = ["A", "B", "C", "D"]
    comparisons = [make_pair("c0", "A", "B", "A"), make_pair("c1", "C", "D", "C")]
    result = fit(items, comparisons)

    selector = build_selector(items, comparisons, result, rng=random.Random(5))
    offered = [frozenset(chosen) for chosen, _ in selector.pick_sets(4)]

    assert frozenset({"A", "B"}) not in offered
    assert frozenset({"C", "D"}) not in offered
    assert len(set(offered)) == len(offered)


def test_pick_sets_stops_when_no_unasked_set_is_left():
    # Six options have fifteen distinct pairs; a page asking for fifty is
    # fifteen questions, not fifty with repeats.
    items = [f"i{n}" for n in range(6)]
    selector = build_selector(items, [], rng=random.Random(11))
    picked = selector.pick_sets(50)

    assert len(picked) == 15
    assert len({frozenset(chosen) for chosen, _ in picked}) == 15


def test_build_selector_seeds_counts_from_the_recorded_comparisons():
    items = ["A", "B", "C", "D"]
    comparisons = [make_pair("c0", "A", "B", "A")]
    selector = build_selector(items, comparisons, rng=random.Random(0))

    assert selector.counts["A"] == 1
    assert selector.counts["C"] == 0
    assert selector.seen_sets == {frozenset({"A", "B"})}


def test_selector_always_returns_grid_n_items():
    items = [f"i{n}" for n in range(6)]
    selector = Selector(item_ids=items, grid_n=2, rng=random.Random(3))
    for _ in range(20):
        chosen, _ = selector.pick_set()
        assert len(chosen) == 2
        assert len(set(chosen)) == 2
