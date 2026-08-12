#!/usr/bin/env python3
"""Supersession leak detector: prove a report iteration subsumes its
predecessor instead of smearing it.

LLM iteration reliably leaks content — regeneration-from-memory drops
whatever wasn't actively recalled (confirmed 2026-08-12: seven units lost
across one report lineage, including two entire sections). This check makes
"the new version replaces the old" a claim that must survive a diff.

Usage:
  check-superset.py OLD.html NEW.html [--rename "old heading=new heading"]...

Checks:
  1. Every h2/h3 heading in OLD exists in NEW (case-insensitive substring),
     unless listed in --rename (each rename is a *declared* editorial
     decision, not a waiver class).
  2. If NEW has a figures sidecar (NEW.html.data.json), every top-level
     figure family present in the sidecar should plausibly be rendered —
     reported as warnings, since rendering is heuristic.

Exit 0 = subsumption holds; 1 = leaks found (listed); 2 = usage error.
Prose-level leaks (paragraphs under a surviving heading) are NOT caught —
for sections that were restructured, read the diff; this tool bounds the
damage, it does not replace judgment.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def headings(path: Path):
    text = path.read_text(errors="replace")
    return [re.sub(r"<[^>]+>", "", h).strip()
            for h in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", text, re.S)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--rename", action="append", default=[],
                    metavar="OLD=NEW", help="declared heading rename")
    args = ap.parse_args()
    if not args.old.exists() or not args.new.exists():
        print("both files must exist", file=sys.stderr)
        return 2
    renames = {}
    for r in args.rename:
        if "=" not in r:
            print(f"bad --rename {r!r}, need OLD=NEW", file=sys.stderr)
            return 2
        old, new = r.split("=", 1)
        renames[old.strip().lower()] = new.strip().lower()

    old_h = headings(args.old)
    new_text = args.new.read_text(errors="replace")
    new_join = " ||| ".join(h.lower() for h in headings(args.new))

    leaks = []
    for h in old_h:
        hl = h.lower()
        if hl in new_join:
            continue
        if hl in renames:
            if renames[hl] in new_join:
                continue
            leaks.append(f"{h}  (declared rename target {renames[hl]!r} also missing)")
            continue
        leaks.append(h)

    sidecar = Path(str(args.new) + ".data.json")
    warnings = []
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text())
            for family, val in data.items():
                if family.startswith("_") or not isinstance(val, dict):
                    continue
                for key, v in val.items():
                    if isinstance(v, list) and len(v) > 2 and \
                            key.replace("_", " ")[:12] not in new_text.lower():
                        warnings.append(f"{family}.{key}: collected "
                                        f"({len(v)} items) — confirm it is rendered")
        except Exception as exc:
            warnings.append(f"sidecar unreadable: {exc}")

    for w in warnings:
        print(f"WARN {w}")
    if leaks:
        print(f"LEAKED {len(leaks)} heading(s) from {args.old.name}:")
        for l in leaks:
            print(f"  - {l}")
        return 1
    print(f"subsumption holds: {len(old_h)} predecessor headings all present "
          f"({len(renames)} declared rename(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
