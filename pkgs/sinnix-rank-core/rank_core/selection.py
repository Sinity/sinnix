"""Which set of items to present next.

Strategies lifted from ranker-4wise's Selector (least-compared/highest-SE
anchor, SE-weighted rank-window companions, recency exclusion, periodic
random exploration) and extended with the one thing the doc calls out as
missing from both prior implementations: ranker-4wise computes connected
components but never *acts* on them, so disconnected comparison subgraphs
keep mutually meaningless thetas forever.

A disconnected domain is therefore bridged on the first pick, and every
`bridge_every`-th pick after it. The first pick matters because the
single-question callers (`sinnix-rank next`, `sinnix-elicit ask`) build a
selector per invocation: a bridge that only came due on the fifth pick of a
selector's life would never be reached, and the components the fit reports as
incomparable would stay incomparable however long the operator kept
answering.

A selector also remembers the sets already put to the operator -- from the
recorded comparisons it is seeded with, and from its own picks -- and spends
its proposals on unasked questions instead.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .fit import FitResult, ItemFit


@dataclass
class Selector:
    item_ids: list[str]
    grid_n: int = 2
    explore_every: int = 4
    bridge_every: int = 5
    recent_window: int | None = None
    rng: random.Random = field(default_factory=random.Random)
    #: Proposals to spend looking for a set the operator has not seen before
    #: falling back to one they have.
    attempts: int = 32

    def __post_init__(self) -> None:
        if len(self.item_ids) < self.grid_n:
            raise ValueError(
                f"need at least {self.grid_n} items, got {len(self.item_ids)}"
            )
        self.counts: dict[str, int] = dict.fromkeys(self.item_ids, 0)
        #: Every set already put to the operator, answered or skipped.
        self.seen_sets: set[frozenset[str]] = set()
        self._fit: FitResult | None = None
        self._recent: list[tuple[str, ...]] = []
        self._window = (
            self.recent_window
            if self.recent_window is not None
            else max(3, self.grid_n * 3)
        )
        self._tick = 0

    def update_fit(self, fit_result: FitResult) -> None:
        self._fit = fit_result

    def observe(self, comparisons) -> int:
        """Seed from the domain's recorded comparisons: how often each item has
        been shown, and which sets have been asked about already."""
        seeded = 0
        for c in comparisons:
            for item_id in c.set:
                if item_id in self.counts:
                    self.counts[item_id] += 1
                    seeded += 1
            self.seen_sets.add(frozenset(c.set))
        return seeded

    def pick_set(self) -> tuple[list[str], str]:
        """Returns (item_ids, strategy_name)."""
        chosen, strategy = self._propose()
        for _ in range(max(0, self.attempts - 1)):
            if frozenset(chosen) not in self.seen_sets:
                break
            chosen, strategy = self._propose()
        self._accept(chosen)
        return chosen, strategy

    def pick_sets(self, n: int) -> list[tuple[list[str], str]]:
        """Up to `n` sets in one pass, none repeating another or anything the
        operator has already been asked. Fewer than `n` means the domain has
        no unasked question left to offer -- a page of twenty comparisons over
        six items is six comparisons.
        """
        out: list[tuple[list[str], str]] = []
        for _ in range(max(0, n)):
            before = len(self.seen_sets)
            chosen, strategy = self.pick_set()
            if len(self.seen_sets) == before:
                break
            out.append((chosen, strategy))
        return out

    def _propose(self) -> tuple[list[str], str]:
        tick = self._tick + 1
        components = self._components()
        recent_ids = {i for s in self._recent for i in s}
        pool = [i for i in self.item_ids if i not in recent_ids]
        if len(pool) < self.grid_n:
            pool = list(self.item_ids)

        if len(components) > 1 and (tick - 1) % self.bridge_every == 0:
            chosen, strategy = self._bridge(components, pool)
        elif tick % self.explore_every == 0:
            chosen, strategy = (
                self.rng.sample(pool, min(self.grid_n, len(pool))),
                "random",
            )
        else:
            chosen, strategy = self._uncertainty(pool), "uncertainty"

        self.rng.shuffle(chosen)  # position-bias mitigation (r4w does this too)
        return chosen, strategy

    def _accept(self, ids: list[str]) -> None:
        self._tick += 1
        for i in ids:
            self.counts[i] = self.counts.get(i, 0) + 1
        self._recent.append(tuple(ids))
        self._recent = self._recent[-self._window :]
        self.seen_sets.add(frozenset(ids))

    def _components(self) -> dict[int, list[str]]:
        if not self._fit or not self._fit.records:
            return {}
        by_component: dict[int, list[str]] = {}
        for item_id in self.item_ids:
            rec = self._fit.records.get(item_id)
            comp = rec.component if rec else 0
            by_component.setdefault(comp, []).append(item_id)
        return by_component

    def _bridge(
        self, components: dict[int, list[str]], pool: list[str]
    ) -> tuple[list[str], str]:
        comp_ids = list(components.keys())
        self.rng.shuffle(comp_ids)
        chosen: list[str] = []
        for comp in comp_ids:
            candidates = [i for i in components[comp] if i not in chosen]
            if candidates:
                chosen.append(self.rng.choice(candidates))
            if len(chosen) >= self.grid_n:
                break
        # top up from the general pool if fewer components than grid_n
        remaining = [i for i in pool if i not in chosen]
        while len(chosen) < self.grid_n and remaining:
            pick = self.rng.choice(remaining)
            chosen.append(pick)
            remaining.remove(pick)
        return chosen, "bridge"

    def _uncertainty(self, pool: list[str]) -> list[str]:
        anchor = self._choose_anchor(pool)
        if not self._fit or not self._fit.records:
            rank_index = {
                i: idx
                for idx, i in enumerate(
                    sorted(pool, key=lambda x: self.counts.get(x, 0))
                )
            }
        else:
            ranked = sorted(
                pool,
                key=lambda i: (
                    -self._fit.records.get(i, ItemFit(i, 0.0, float("inf"), 0)).theta
                ),
            )
            rank_index = {i: idx for idx, i in enumerate(ranked)}
        anchor_rank = rank_index[anchor]
        window = [
            i for i in pool if i != anchor and abs(rank_index[i] - anchor_rank) <= 15
        ] or [i for i in pool if i != anchor]
        if self._fit and self._fit.records:
            weights = [
                max(self._fit.records.get(i, ItemFit(i, 0.0, 1.0, 0)).se, 1e-6)
                for i in window
            ]
        else:
            weights = [1.0 / (1 + self.counts.get(i, 0)) for i in window]
        companions = _weighted_sample(
            window, weights, min(self.grid_n - 1, len(window)), self.rng
        )
        chosen = [anchor] + companions
        while len(chosen) < self.grid_n and len(pool) >= self.grid_n:
            extra = self.rng.choice(pool)
            if extra not in chosen:
                chosen.append(extra)
        return chosen

    def _choose_anchor(self, pool: list[str]) -> str:
        if self._fit and self._fit.records:
            by_se = sorted(
                pool,
                key=lambda i: (
                    -self._fit.records.get(i, ItemFit(i, 0.0, float("inf"), 0)).se
                ),
            )
            top = by_se[: max(1, min(16, len(by_se)))]
            return self.rng.choice(top)
        least_seen = sorted(pool, key=lambda i: self.counts.get(i, 0))
        return self.rng.choice(least_seen[: max(1, min(16, len(least_seen)))])


def build_selector(
    item_ids,
    comparisons,
    fit_result: FitResult | None = None,
    *,
    grid_n: int = 2,
    rng: random.Random | None = None,
    **kwargs,
) -> Selector:
    """A selector over one domain: its items, what has already been asked, and
    the fit those answers produce. Every frontend enters selection here, so
    "which question next" has one answer per domain state rather than one per
    surface.
    """
    selector = Selector(
        item_ids=list(item_ids),
        grid_n=grid_n,
        rng=rng if rng is not None else random.Random(),
        **kwargs,
    )
    selector.observe(comparisons)
    if fit_result is not None:
        selector.update_fit(fit_result)
    return selector


def _weighted_sample(
    items: list[str], weights: list[float], k: int, rng: random.Random
) -> list[str]:
    items = list(items)
    weights = list(weights)
    out = []
    for _ in range(min(k, len(items))):
        total = sum(weights) or 1.0
        r = rng.random() * total
        acc = 0.0
        idx = len(items) - 1
        for i, w in enumerate(weights):
            acc += w
            if r <= acc:
                idx = i
                break
        out.append(items.pop(idx))
        weights.pop(idx)
    return out
