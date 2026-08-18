import random
from collections import Counter

from rank_core.draw import draw_thompson, draw_top
from rank_core.fit import fit
from rank_core.store import Comparison


def make_pair(id_, a, b, winner):
    return Comparison(id=id_, at="2026-08-18T00:00:00Z", kind="pair", set=[a, b], winner=winner, weight=1.0)


def _fit_with_uncertainty():
    # A clearly ahead but thinly-evidenced (high se); B/C close behind with
    # more evidence -- exactly the regime where Thompson should sometimes
    # not pick the top item, while argmax always must.
    comparisons = [make_pair("c0", "A", "B", "A")]
    for i in range(20):
        comparisons.append(make_pair(f"c{i+1}", "B", "C", "B" if i % 3 else "C"))
    return fit(["A", "B", "C"], comparisons)


def test_draw_top_always_picks_the_argmax():
    result = _fit_with_uncertainty()
    expected = result.ranked()[0].id
    for _ in range(50):
        assert draw_top(result) == expected


def test_draw_thompson_sometimes_diverges_from_argmax():
    result = _fit_with_uncertainty()
    top_id = result.ranked()[0].id
    rng = random.Random(11)
    picks = Counter(draw_thompson(result, rng=rng) for _ in range(500))
    assert picks[top_id] > 0  # still favors the top item most of the time
    assert picks[top_id] < 500  # but not deterministically -- this is the point
    assert len(picks) > 1


def test_draw_unknown_policy_raises():
    import pytest

    from rank_core.draw import draw

    result = _fit_with_uncertainty()
    with pytest.raises(ValueError):
        draw(result, policy="nonexistent")
