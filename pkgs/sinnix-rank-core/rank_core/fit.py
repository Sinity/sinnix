"""Plackett-Luce top-1 MM fit (Hunter 2004) with virtual-tie anchor
regularization, standard errors, and connected-component detection.

Generalized clean-room reimplementation of the model in stashbox's
ranker-4wise (ranker_core.fit_bradley_terry / bt-core.js): that code kept a
separate Bradley-Terry pairwise-edge accumulator alongside a Plackett-Luce
choice-set accumulator because pairs and choice-sets were tracked in two
`comparisons.jsonl` record shapes (kind: "seed"/"user4"). Here every
comparison is already a `set` + `winner` (store.Comparison), including plain
pairs (set of 2), so there is only one accumulator: pairs are simply the
size-2 case of the general Plackett-Luce top-1 MM update -- no separate BT
code path needed.

A pairwise tie (kind="pair", winner=None) is not representable in a top-1
choice model directly; it is split into two half-weight records (A beats
{A,B}, B beats {A,B}), the same trick ranker-4wise used for rating100-tied
seed pairs.
"""

from __future__ import annotations

import calendar
import math
import time
from dataclasses import dataclass, field

from .store import Comparison

BT_EPS = 1e-12


def _logistic(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def _parse_at(at: str) -> float:
    # at is UTC ("...Z"); calendar.timegm is the UTC-correct counterpart of
    # mktime (which interprets its struct_time as local time and would
    # silently shift ages by the local UTC offset -- the exact bug
    # ranker-4wise's Store.session_summary documents having hit once).
    try:
        return calendar.timegm(time.strptime(at, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return time.time()


def decay_weight(
    at: str, half_life_days: float | None, now_epoch: float | None = None
) -> float:
    """Exponential recency decay: weight halves every `half_life_days`. A
    `None` half-life disables decay (weight 1.0), the current default -- the
    doc calls the exact half-life a tunable, not something to get precisely
    right this pass, so this stays a config knob callers pass explicitly
    rather than a baked-in constant.
    """
    if not half_life_days:
        return 1.0
    now_epoch = now_epoch if now_epoch is not None else time.time()
    age_days = max(0.0, (now_epoch - _parse_at(at)) / 86400.0)
    return 0.5 ** (age_days / half_life_days)


@dataclass
class ItemFit:
    id: str
    theta: float
    se: float
    matches: float
    component: int = 0


@dataclass
class FitResult:
    records: dict[str, ItemFit] = field(default_factory=dict)
    tau: float = 1.0

    def ranked(self) -> list[ItemFit]:
        return sorted(self.records.values(), key=lambda r: -r.theta)


def _effective_records(
    comparisons: list[Comparison], half_life_days: float | None, now_epoch: float | None
):
    """(members, winner, weight) triples for every usable comparison."""
    out = []
    for c in comparisons:
        if c.kind in ("skip", "incomparable"):
            continue
        w = float(c.weight) * decay_weight(c.at, half_life_days, now_epoch)
        if c.kind == "pair" and c.winner is None:
            if len(c.set) != 2:
                continue
            a, b = c.set
            out.append(([a, b], a, w * 0.5))
            out.append(([a, b], b, w * 0.5))
            continue
        if c.winner is None or c.winner not in c.set or len(c.set) < 2:
            continue
        out.append((c.set, c.winner, w))
    return out


def fit(
    item_ids: list[str],
    comparisons: list[Comparison],
    tau: float = 1.0,
    tol: float = 1e-8,
    max_iter: int = 2000,
    half_life_days: float | None = None,
    now_epoch: float | None = None,
) -> FitResult:
    """Fit a Plackett-Luce top-1 model over choice-set comparisons.

    `item_ids` seeds every registered item into the fit even with zero
    comparisons (theta=0, infinite-ish se), so freshly-added items show up in
    `status`/selection immediately instead of being invisible until their
    first comparison.
    """
    records = _effective_records(comparisons, half_life_days, now_epoch)
    ids = sorted(
        {str(i) for i in item_ids} | {m for members, _, _ in records for m in members}
    )
    index = {sid: i for i, sid in enumerate(ids)}
    n = len(ids)
    if n == 0:
        return FitResult(records={}, tau=tau)

    choice_sets = [
        {
            "members": [index[m] for m in members],
            "winner": index[winner],
            "weight": weight,
        }
        for members, winner, weight in records
    ]
    by_item: list[list[int]] = [[] for _ in range(n)]
    for si, cs in enumerate(choice_sets):
        for m in cs["members"]:
            by_item[m].append(si)

    ability = [0.0] * n
    alpha = [1.0] * n
    for _ in range(max_iter):
        max_delta = 0.0
        set_alpha_sum = [sum(alpha[m] for m in cs["members"]) for cs in choice_sets]
        for i in range(n):
            w = 0.5 * tau  # virtual tie anchor (ability=0, weight tau/2)
            denom = tau / (alpha[i] + 1.0)
            for si in by_item[i]:
                cs = choice_sets[si]
                denom += cs["weight"] / max(set_alpha_sum[si], BT_EPS)
                if cs["winner"] == i:
                    w += cs["weight"]
            nxt = math.log(max(w / max(denom, BT_EPS), BT_EPS))
            max_delta = max(max_delta, abs(nxt - ability[i]))
            ability[i] = nxt
        alpha = [math.exp(a) for a in ability]
        if max_delta < tol:
            break

    _center(ability)
    alpha = [math.exp(a) for a in ability]

    matches = [0.0] * n
    info = [0.0] * n
    for i in range(n):
        p_anchor = _logistic(ability[i])
        info[i] += tau * p_anchor * (1 - p_anchor)
    for cs in choice_sets:
        sum_alpha = sum(alpha[m] for m in cs["members"])
        for m in cs["members"]:
            p = alpha[m] / max(sum_alpha, BT_EPS)
            info[m] += cs["weight"] * p * (1 - p)
            matches[m] += cs["weight"]

    result_records = {
        ids[i]: ItemFit(
            id=ids[i],
            theta=ability[i],
            se=1 / math.sqrt(max(info[i], BT_EPS)),
            matches=matches[i],
        )
        for i in range(n)
    }
    _assign_components(
        result_records,
        [
            (ids[cs["winner"]], ids[m])
            for cs in choice_sets
            for m in cs["members"]
            if m != cs["winner"]
        ],
    )
    return FitResult(records=result_records, tau=tau)


def _center(arr: list[float]) -> None:
    if not arr:
        return
    mean = sum(arr) / len(arr)
    for i in range(len(arr)):
        arr[i] -= mean


def _assign_components(
    records: dict[str, ItemFit], edges: list[tuple[str, str]]
) -> None:
    adj: dict[str, list[str]] = {sid: [] for sid in records}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].append(b)
            adj[b].append(a)
    comp = 0
    seen: set[str] = set()
    for sid in records:
        if sid in seen:
            continue
        comp += 1
        stack = [sid]
        seen.add(sid)
        while stack:
            cur = stack.pop()
            records[cur].component = comp
            for nxt in adj.get(cur, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
