"""``sinnix quota ok``: may discretionary work start on the subscription now?

Discretionary work (a research run, a review, a skill test) is work its
starter says can wait. It waits while a subscription's weekly usage is above
a threshold, so it does not compete with work that cannot wait. The check
never classifies work itself: a caller asks on behalf of a job it marked.

Exit status: 0 the work may start, 1 it should wait, 3 usage could not be
read (the caller decides; ``agentctl job start --discretionary`` starts).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping

from . import sources

DEFAULT_THRESHOLD_PERCENT = 85.0
WEEK_MINUTES = 7 * 24 * 60
EXIT_OK, EXIT_WAIT, EXIT_UNKNOWN = 0, 1, 3


def weekly(limits: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Each provider's weekly window: ``percent`` and ``resets_at``."""
    readings: dict[str, dict[str, Any]] = {}
    claude = limits.get("claude") or {}
    if claude.get("seven_day_percent") is not None:
        readings["claude"] = {
            "percent": float(claude["seven_day_percent"]),
            "resets_at": claude.get("seven_day_resets_at"),
        }
    for window in (limits.get("codex") or {}).get("windows") or []:
        if (window.get("window_minutes") or 0) >= WEEK_MINUTES and window.get(
            "used_percent"
        ) is not None:
            readings["codex"] = {
                "percent": float(window["used_percent"]),
                "resets_at": window.get("resets_at"),
            }
    return readings


def verdict(
    limits: Mapping[str, Any],
    *,
    provider: str = "claude",
    threshold: float = DEFAULT_THRESHOLD_PERCENT,
) -> dict[str, Any]:
    """Whether discretionary work may start, with one line saying why.

    ``provider`` names the subscription that gates: ``claude``, ``codex`` or
    ``any`` (wait while either is above the threshold). ``ok`` is None when a
    gating provider's usage is not known.
    """
    readings = weekly(limits)
    names = ("claude", "codex") if provider == "any" else (provider,)
    known = [name for name in names if name in readings]
    above = [name for name in known if readings[name]["percent"] >= threshold]
    described = ", ".join(
        f"{name.capitalize()} weekly usage {readings[name]['percent']:.0f}%"
        for name in ("claude", "codex")
        if name in readings
    )
    result: dict[str, Any] = {
        "purpose": "discretionary",
        "provider": provider,
        "threshold_percent": threshold,
        "weekly": readings,
        "resets_at": None,
    }
    if above:
        # Wait for the last of the windows that are above the threshold.
        resets = [readings[name]["resets_at"] for name in above]
        result["resets_at"] = max(resets) if all(resets) else None
        return {
            **result,
            "ok": False,
            "reason": f"{described}; {' and '.join(n.capitalize() for n in above)} "
            f"at or above the {threshold:.0f}% threshold for discretionary work"
            + (f", resets {result['resets_at']}" if result["resets_at"] else ""),
        }
    if len(known) < len(names) and not (provider == "any" and known):
        missing = [name for name in names if name not in readings]
        errors = "; ".join(
            f"{name}: {(limits.get(name) or {}).get('error') or 'no weekly window read'}"
            for name in missing
        )
        return {**result, "ok": None, "reason": f"usage could not be read ({errors})"}
    return {
        **result,
        "ok": True,
        "reason": f"{described}; below the {threshold:.0f}% threshold for discretionary work",
    }


def read_limits() -> dict[str, Any]:
    """Current usage from the owners: ``claude-quota`` and the newest Codex
    session file. A provider that cannot be read carries its error."""
    limits: dict[str, Any] = {}
    for name, collect in (
        ("claude", sources.claude_usage),
        ("codex", sources.codex_usage),
    ):
        try:
            limits[name] = collect()
        except Exception as error:
            limits[name] = {"error": f"{type(error).__name__}: {error}"[:200]}
    return limits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sinnix quota",
        description="Whether work that can wait may use the subscription now.",
    )
    verbs = parser.add_subparsers(dest="verb", required=True)
    ok = verbs.add_parser("ok", help="exit 0 to start, 1 to wait, 3 when unknown")
    ok.add_argument(
        "--for",
        dest="purpose",
        required=True,
        choices=("discretionary",),
        help="the kind of work asking; only discretionary work is ever asked to wait",
    )
    ok.add_argument(
        "--provider",
        choices=("claude", "codex", "any"),
        default="claude",
        help="the subscription that gates (default claude)",
    )
    ok.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD_PERCENT,
        metavar="PERCENT",
        help=f"weekly usage at which the work waits (default {DEFAULT_THRESHOLD_PERCENT:.0f})",
    )
    ok.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    if not 0 < arguments.threshold <= 100:
        parser.error("--threshold is a percentage between 0 and 100")
    result = verdict(
        read_limits(), provider=arguments.provider, threshold=arguments.threshold
    )
    if arguments.json:
        print(json.dumps(result, sort_keys=True))
    else:
        word = {True: "ok", False: "wait", None: "unknown"}[result["ok"]]
        print(f"{word}: {result['reason']}")
    return {True: EXIT_OK, False: EXIT_WAIT, None: EXIT_UNKNOWN}[result["ok"]]


if __name__ == "__main__":
    sys.exit(main())
