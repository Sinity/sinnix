"""`sinnix-elicit`'s fit is `rank_core.fit`, and it fits what it used to.

`legacy_fit_bradley_terry` below is the fitter this file carried before the
consolidation, kept verbatim as the reference the shared engine has to
reproduce. It pins the numerical contract of a live domain: an existing
`model.json` must not move because the model moved houses. Deleting it costs
the only evidence that the ranking the operator has been reading is the same
ranking.

Parity is proved over randomised comparison sets against a 126-item roster
matching the live wallpaper domain's shape, because that domain's own
comparisons are all tombstoned -- a fit over it has nothing to disagree about.
"""

from __future__ import annotations

import math
import random

import pytest

BT_EPS = 1e-12
ROSTER_SIZE = 126
FEATURE_KEYS = (
    "aspect",
    "contrast",
    "entropy",
    "hue",
    "log_pixels",
    "luminance",
    "saturation",
    "warmth",
)


# ──────────────────────────────────────────────────────────────────────────
# The pre-consolidation fitter, verbatim
# ──────────────────────────────────────────────────────────────────────────
def _bt_logistic(x):
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def legacy_fit_bradley_terry(items, comparisons, tau=1.0, tol=1e-8, max_iter=2000):
    ids = sorted({str(i["id"]) for i in items})
    known = set(ids)
    index = {sid: i for i, sid in enumerate(ids)}
    n = len(ids)

    edges = {}
    matches = [0.0] * n
    for c in comparisons:
        if c.get("kind") == "choice-set":
            continue
        a, b = index.get(str(c.get("a"))), index.get(str(c.get("b")))
        if a is None or b is None or a == b:
            continue
        try:
            y = float(c["outcome"])
        except (KeyError, TypeError, ValueError):
            continue
        win_a = 1.0 if y == 1 else (0.0 if y == 0 else 0.5)
        i, j = (a, b) if a < b else (b, a)
        e = edges.setdefault((i, j), [0.0, 0.0])
        if a == i:
            e[0] += win_a
            e[1] += 1.0 - win_a
        else:
            e[1] += win_a
            e[0] += 1.0 - win_a
        matches[a] += 1
        matches[b] += 1

    adj = [[] for _ in range(n)]
    for (i, j), (wi, wj) in edges.items():
        total = wi + wj
        adj[i].append({"j": j, "wins": wi, "total": total})
        adj[j].append({"j": i, "wins": wj, "total": total})

    choice_sets = []
    for c in comparisons:
        if c.get("kind") != "choice-set":
            continue
        members = [index[str(m)] for m in (c.get("set") or []) if str(m) in known]
        winner = index.get(str(c.get("winner")))
        if len(members) >= 2 and winner is not None and winner in members:
            choice_sets.append({"members": members, "winner": winner})
    sets_by_item = [[] for _ in range(n)]
    for si, cs in enumerate(choice_sets):
        for m in cs["members"]:
            sets_by_item[m].append(si)
            matches[m] += 1

    prior_by_id = {str(i["id"]): i.get("prior") for i in items}
    ability = [float(prior_by_id.get(sid) or 0.0) for sid in ids]
    anchor_alpha = [1.0] * n
    alpha = [math.exp(a) for a in ability]

    for _ in range(max_iter):
        max_delta = 0.0
        set_alpha_sum = [sum(alpha[m] for m in cs["members"]) for cs in choice_sets]
        for i in range(n):
            w = 0.5 * tau
            denom = tau / (alpha[i] + anchor_alpha[i])
            for e in adj[i]:
                w += e["wins"]
                denom += e["total"] / (alpha[i] + alpha[e["j"]])
            for si in sets_by_item[i]:
                denom += 1 / max(set_alpha_sum[si], BT_EPS)
                if choice_sets[si]["winner"] == i:
                    w += 1
            nxt = math.log(max(w / max(denom, BT_EPS), BT_EPS))
            max_delta = max(max_delta, abs(nxt - ability[i]))
            ability[i] = nxt
        alpha = [math.exp(a) for a in ability]
        if max_delta < tol:
            break

    mean = sum(ability) / n if n else 0.0
    ability = [a - mean for a in ability]
    alpha = [math.exp(a) for a in ability]

    records = {}
    for i in range(n):
        p_anchor = _bt_logistic(ability[i])
        info = tau * p_anchor * (1 - p_anchor)
        for e in adj[i]:
            p = _bt_logistic(ability[i] - ability[e["j"]])
            info += e["total"] * p * (1 - p)
        for si in sets_by_item[i]:
            sum_alpha = sum(alpha[m] for m in choice_sets[si]["members"])
            p = alpha[i] / max(sum_alpha, BT_EPS)
            info += p * (1 - p)
        records[ids[i]] = {
            "id": ids[i],
            "theta": ability[i],
            "se": 1 / math.sqrt(max(info, BT_EPS)),
            "matches": matches[i],
        }
    return records


# ──────────────────────────────────────────────────────────────────────────
# Randomised domains shaped like the live one
# ──────────────────────────────────────────────────────────────────────────
def synthetic_roster(rng: random.Random, size: int = ROSTER_SIZE, priors: bool = False):
    """A roster with the live wallpaper domain's shape: 12-hex-char ids, a
    dimensions+luminance label, an 8-key feature vector, optional prior."""
    items = []
    for _ in range(size):
        item = {
            "id": "".join(rng.choice("0123456789abcdef") for _ in range(12)),
            "label": f"{rng.choice([1920, 2560, 3840])}x{rng.choice([1080, 1200, 1440])}"
            f" lum={rng.random():.2f}",
            "features": {key: round(rng.uniform(0, 2), 5) for key in FEATURE_KEYS},
        }
        if priors:
            item["prior"] = round(rng.uniform(-1.5, 1.5), 3)
        items.append(item)
    # Ids are random; a collision would make the roster smaller than asked for
    # and quietly weaken every case built on it.
    assert len({i["id"] for i in items}) == size
    return items


def synthetic_comparisons(rng: random.Random, items, count: int, dangling: int = 0):
    """Comparison records of every shape the domain file can hold: decided
    pairs, ties, non-canonical tie encodings, repeated pairs, self-pairs,
    unparseable outcomes, choice sets of 3-5, and records naming ids that are
    not on the roster.
    """
    ids = [i["id"] for i in items]
    records = []
    for n in range(count):
        kind = rng.random()
        if kind < 0.55:
            a, b = rng.sample(ids, 2)
            outcome = rng.choice([1.0, 0.0, 0.5, 1, 0, "1", 0.73, None, "bad"])
            records.append(
                {"id": f"c{n}", "kind": "pair", "a": a, "b": b, "outcome": outcome}
            )
        elif kind < 0.65:
            a = rng.choice(ids)
            records.append(
                {"id": f"c{n}", "kind": "pair", "a": a, "b": a, "outcome": 1.0}
            )
        elif kind < 0.75:
            a, b = rng.sample(ids, 2)
            records.append({"id": f"c{n}", "kind": "pair", "a": a, "b": b})
        else:
            members = rng.sample(ids, rng.randint(3, 5))
            records.append(
                {
                    "id": f"c{n}",
                    "kind": "choice-set",
                    "set": members,
                    "winner": rng.choice(members),
                }
            )
    for n in range(dangling):
        ghost = f"retired-{n}"
        if rng.random() < 0.5:
            records.append(
                {
                    "id": f"d{n}",
                    "kind": "pair",
                    "a": ghost,
                    "b": rng.choice(ids),
                    "outcome": 1.0,
                }
            )
        else:
            members = rng.sample(ids, 3) + [ghost]
            records.append(
                {
                    "id": f"d{n}",
                    "kind": "choice-set",
                    "set": members,
                    "winner": rng.choice(members),
                }
            )
    rng.shuffle(records)
    return records


def assert_same_fit(expected, actual):
    assert set(expected) == set(actual)
    for item_id, want in expected.items():
        got = actual[item_id]
        assert got["theta"] == pytest.approx(want["theta"], abs=1e-6)
        assert got["se"] == pytest.approx(want["se"], abs=1e-6)
        assert got["matches"] == pytest.approx(want["matches"])


@pytest.mark.parametrize("seed", range(10))
def test_fit_reproduces_the_pre_consolidation_model(seed, elicit_module):
    rng = random.Random(seed)
    items = synthetic_roster(rng, priors=seed % 2 == 0)
    comparisons = synthetic_comparisons(
        rng, items, count=60 * (seed % 5 + 1), dangling=seed * 3
    )
    assert_same_fit(
        legacy_fit_bradley_terry(items, comparisons),
        elicit_module.fit_bradley_terry(items, comparisons),
    )


def test_fit_reproduces_the_pre_consolidation_model_with_no_comparisons(elicit_module):
    """The cold-start shape: every item present, flat, and the se the
    selection heuristic sorts on."""
    items = synthetic_roster(random.Random(99))
    assert_same_fit(
        legacy_fit_bradley_terry(items, []),
        elicit_module.fit_bradley_terry(items, []),
    )


def test_a_tie_is_two_half_weight_records(elicit_module):
    """The one representational change: a pairwise tie has no top-1 winner, so
    it becomes two half-weight records. It must still be one comparison's worth
    of evidence for each item, and must leave them level."""
    items = [{"id": "a"}, {"id": "b"}]
    fitted = elicit_module.fit_bradley_terry(
        items, [{"id": "t", "kind": "pair", "a": "a", "b": "b", "outcome": 0.5}]
    )
    assert fitted["a"]["matches"] == 1.0
    assert fitted["b"]["matches"] == 1.0
    assert fitted["a"]["theta"] == pytest.approx(fitted["b"]["theta"])


def test_a_comparison_naming_an_unknown_item_is_dropped_not_ranked(elicit_module):
    """rank_core fits comparison-only ids; this domain must not.

    items.json is the operator's declared roster. A record naming an id that
    is no longer on it is evidence about something deleted, and letting the
    engine seed it would put that item back into `rank` output and into the
    pair selection.
    """
    items = [{"id": "a"}, {"id": "b"}]
    comparisons = [
        {"id": "1", "kind": "pair", "a": "a", "b": "b", "outcome": 1.0},
        {"id": "2", "kind": "pair", "a": "ghost", "b": "b", "outcome": 1.0},
        {
            "id": "3",
            "kind": "choice-set",
            "set": ["a", "b", "ghost"],
            "winner": "ghost",
        },
    ]
    fitted = elicit_module.fit_bradley_terry(items, comparisons)
    assert set(fitted) == {"a", "b"}

    from rank_core import fit as rank_core_fit

    engine_ids = set(
        rank_core_fit(
            ["a", "b"], elicit_module.to_comparisons(comparisons, {"a", "b", "ghost"})
        ).records
    )
    assert "ghost" in engine_ids


def test_item_prior_does_not_move_the_converged_fit(elicit_module):
    """`prior` chose the MM starting point and nothing else. The anchored
    objective has one maximum, so dropping it leaves the fit where it was --
    which is why the engine has no prior to carry."""
    rng = random.Random(7)
    plain = synthetic_roster(rng, size=40)
    comparisons = synthetic_comparisons(random.Random(8), plain, count=200)
    primed = [
        dict(item, prior=round(random.Random(item["id"]).uniform(-2, 2), 3))
        for item in plain
    ]
    assert_same_fit(
        legacy_fit_bradley_terry(plain, comparisons),
        legacy_fit_bradley_terry(primed, comparisons),
    )
    assert_same_fit(
        legacy_fit_bradley_terry(primed, comparisons),
        elicit_module.fit_bradley_terry(primed, comparisons),
    )
