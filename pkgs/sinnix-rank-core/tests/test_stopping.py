from rank_core.fit import fit
from rank_core.stopping import top_k_stability
from rank_core.store import Comparison


def make_pair(id_, a, b, winner):
    return Comparison(id=id_, at="2026-08-18T00:00:00Z", kind="pair", set=[a, b], winner=winner, weight=1.0)


def test_stopping_low_confidence_with_few_comparisons():
    # A single comparison between two of four items barely constrains
    # anything; top-1 stability across posterior draws should be low.
    result = fit(["A", "B", "C", "D"], [make_pair("c0", "A", "B", "A")])
    report = top_k_stability(result, k=1, samples=500, seed=1)
    assert report.p_stable < 0.6


def test_stopping_high_confidence_with_many_consistent_comparisons():
    comparisons = []
    order = ["A", "B", "C", "D"]
    i = 0
    for _ in range(40):
        for a_idx in range(len(order)):
            for b_idx in range(a_idx + 1, len(order)):
                comparisons.append(make_pair(f"c{i}", order[a_idx], order[b_idx], order[a_idx]))
                i += 1
    result = fit(order, comparisons)
    report = top_k_stability(result, k=1, samples=500, seed=1)
    assert report.p_stable > 0.9
    assert report.top_k == ["A"]


def test_stopping_is_deterministic_given_seed():
    result = fit(["A", "B", "C"], [make_pair("c0", "A", "B", "A"), make_pair("c1", "B", "C", "B")])
    r1 = top_k_stability(result, k=2, samples=200, seed=42)
    r2 = top_k_stability(result, k=2, samples=200, seed=42)
    assert r1 == r2
