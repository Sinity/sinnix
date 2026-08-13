"""sinnix-deslop CLI: filter stdin -> stdout, or a file in place with --in-place."""

from __future__ import annotations

import argparse
import sys

from .filter import deslop, load_rules


def main() -> int:
    ap = argparse.ArgumentParser(prog="sinnix-deslop", description=__doc__)
    ap.add_argument("file", nargs="?", help="file to clean (default: stdin)")
    ap.add_argument("--rules", help="override path to a phrases.txt-format rule file")
    ap.add_argument("--in-place", action="store_true", help="rewrite the input file instead of printing")
    args = ap.parse_args()

    rules = load_rules(args.rules)

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    cleaned = deslop(text, rules)

    if args.in_place:
        if not args.file:
            print("--in-place requires a file argument", file=sys.stderr)
            return 2
        with open(args.file, "w", encoding="utf-8") as f:
            f.write(cleaned + "\n")
    else:
        print(cleaned)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
