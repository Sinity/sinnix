from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .daemon import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnix-capture-a11y")
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument(
        "--subtree-interval-seconds",
        type=float,
        default=30.0,
        help="Minimum seconds between periodic focused-window accessible-subtree dumps",
    )
    parser.add_argument(
        "--text-debounce-seconds",
        type=float,
        default=2.0,
        help="Minimum seconds between accepted text-changed records for the same accessible object",
    )
    parser.add_argument("--max-depth", type=int, default=40, help="Maximum subtree walk depth")
    parser.add_argument("--max-nodes", type=int, default=2000, help="Maximum node count per subtree dump")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    return run(
        capture_root=args.capture_root,
        subtree_interval_seconds=args.subtree_interval_seconds,
        text_debounce_seconds=args.text_debounce_seconds,
        max_depth=args.max_depth,
        max_nodes=args.max_nodes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
