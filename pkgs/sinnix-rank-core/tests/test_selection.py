import random

from rank_core.fit import fit
from rank_core.selection import Selector
from rank_core.store import Comparison


def make_pair(id_, a, b, winner):
    return Comparison(id=id_, at="2026-08-18T00:00:00Z", kind="pair", set=[a, b], winner=winner, weight=1.0)


def test_selector_bridges_disconnected_components():
    # Two islands {A,B} and {C,D} with zero cross-comparisons: the fit must
    # report two components, and the selector -- once fed that fit -- must
    # schedule a bridging pick (an item from each island in the same set)
    # within its bridge_every window rather than never crossing.
    items = ["A", "B", "C", "D"]
    comparisons = [make_pair("c0", "A", "B", "A"), make_pair("c1", "C", "D", "C")]
    result = fit(items, comparisons)
    components = {r.id: r.component for r in result.records.values()}
    assert len({components["A"], components["C"]}) == 2  # sanity: genuinely disconnected

    selector = Selector(item_ids=items, grid_n=2, bridge_every=3, explore_every=1000, rng=random.Random(1))
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
    selector = Selector(item_ids=items, grid_n=2, bridge_every=1, explore_every=1000, rng=random.Random(1))
    selector.update_fit(result)
    for _ in range(5):
        _, strategy = selector.pick_set()
        assert strategy != "bridge"


def test_selector_always_returns_grid_n_items():
    items = [f"i{n}" for n in range(6)]
    selector = Selector(item_ids=items, grid_n=2, rng=random.Random(3))
    for _ in range(20):
        chosen, _ = selector.pick_set()
        assert len(chosen) == 2
        assert len(set(chosen)) == 2
