"""Comparison fixtures shared by the fit, selection, stopping and draw suites.

The timestamp is fixed so a comparison's identity never depends on when the
suite ran; the engine orders by the log's own sequence, not by wall clock.
"""

from __future__ import annotations

from rank_core.store import Comparison

COMPARISON_AT = "2026-08-18T00:00:00Z"


def make_pair(id_: str, a: str, b: str, winner: str) -> Comparison:
    return Comparison(
        id=id_,
        at=COMPARISON_AT,
        kind="pair",
        set=[a, b],
        winner=winner,
        weight=1.0,
    )
