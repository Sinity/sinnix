"""Stopping / confidence statement: the gap neither resorter nor
ranker-4wise closed (both documented "you click until bored, nothing says
top-k is stable").

Gwern's own footnote sketch, made cheap: sample theta_i ~ N(theta_hat_i,
se_i) k times, take the top-k item set of each sample, and report the
fraction of samples whose top-k set equals the most common one. Confident
fits (small se, well-separated theta) converge to near-1.0 quickly; a fit
built on few/inconsistent comparisons stays low no matter how it's read.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from .fit import FitResult


@dataclass
class StabilityReport:
    top_k: list[str]
    p_stable: float
    k: int
    samples: int


def top_k_stability(
    fit_result: FitResult, k: int = 1, samples: int = 500, seed: int | None = None
) -> StabilityReport:
    records = list(fit_result.records.values())
    k = max(1, min(k, len(records)))
    if not records:
        return StabilityReport(top_k=[], p_stable=0.0, k=k, samples=samples)

    rng = random.Random(seed)
    counts: Counter[frozenset[str]] = Counter()
    for _ in range(samples):
        draw = [(r.id, rng.gauss(r.theta, max(r.se, 1e-9))) for r in records]
        draw.sort(key=lambda pair: -pair[1])
        counts[frozenset(item_id for item_id, _ in draw[:k])] += 1

    top_set, hits = counts.most_common(1)[0]
    ordered = sorted(top_set, key=lambda item_id: -fit_result.records[item_id].theta)
    return StabilityReport(top_k=ordered, p_stable=hits / samples, k=k, samples=samples)
