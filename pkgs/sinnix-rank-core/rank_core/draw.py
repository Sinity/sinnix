"""Draw policies: which item to hand the operator right now, from a fitted
ranking, as an explicit decision-assistance mechanism rather than always
handing back rank 1.

Thompson sampling is the default per the design doc's argument: argmax
overfits ranking noise and starves near-top items of data (statistical), and
a system-drawn choice from a vetted top set carries no self-justification
burden (the doc's operator-specific reasoning) -- the same precommitment
value as steering's decide-once satisficing menus. `top` and `softmax` are
offered explicitly for callers that want deterministic or temperature-tuned
behavior instead.
"""

from __future__ import annotations

import math
import random

from .fit import FitResult


def draw_top(fit_result: FitResult) -> str | None:
    ranked = fit_result.ranked()
    return ranked[0].id if ranked else None


def draw_softmax(
    fit_result: FitResult, temperature: float = 1.0, rng: random.Random | None = None
) -> str | None:
    records = list(fit_result.records.values())
    if not records:
        return None
    rng = rng or random.Random()
    temperature = max(temperature, 1e-6)
    weights = [math.exp(r.theta / temperature) for r in records]
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for rec, w in zip(records, weights, strict=True):
        acc += w
        if r <= acc:
            return rec.id
    return records[-1].id


def draw_thompson(
    fit_result: FitResult, rng: random.Random | None = None
) -> str | None:
    records = list(fit_result.records.values())
    if not records:
        return None
    rng = rng or random.Random()
    samples = [(r.id, rng.gauss(r.theta, max(r.se, 1e-9))) for r in records]
    samples.sort(key=lambda pair: -pair[1])
    return samples[0][0]


POLICIES = {"top": draw_top, "softmax": draw_softmax, "thompson": draw_thompson}
DEFAULT_POLICY = "thompson"


def draw(fit_result: FitResult, policy: str = DEFAULT_POLICY, **kwargs) -> str | None:
    if policy not in POLICIES:
        raise ValueError(
            f"unknown draw policy {policy!r}, choose one of {sorted(POLICIES)}"
        )
    return POLICIES[policy](fit_result, **kwargs)
