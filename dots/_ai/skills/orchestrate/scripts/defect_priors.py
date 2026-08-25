#!/usr/bin/env python3
"""Defect-prior scoreboard: rank polylogue modules for the next hunt wave.

Prior = LOC x thin-test-coverage x churn x past-defect-density, minus
recently-swept penalty. Machines rank, models judge. Consumers: the
overseer's hunt dispatch; the sweep ledger lives beside the output.

Usage: defect_priors.py [--repo /realm/project/polylogue] [--top 25]
Sweep ledger (optional): .agent/scratch/sweep-ledger.jsonl in the repo,
rows {"module": "polylogue/foo.py", "lens": "...", "commit": "...",
"date": "..."} - a module swept at a commit is penalized until it churns.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def sh(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=300
    ).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/realm/project/polylogue")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()
    repo = Path(args.repo)

    # LOC per product file
    loc: dict[str, int] = {}
    for f in repo.glob("polylogue/**/*.py"):
        rel = str(f.relative_to(repo))
        try:
            loc[rel] = sum(1 for _ in f.open(errors="replace"))
        except OSError:
            continue

    # churn: commits touching each file in the last 60 days
    churn: dict[str, int] = defaultdict(int)
    out = sh(["git", "log", "--since=60.days", "--name-only", "--pretty=format:"], repo)
    for line in out.splitlines():
        line = line.strip()
        if line in loc:
            churn[line] += 1

    # covering-test proxy: how many test files mention the module's import path
    # (cheap stand-in when no testmon db is readable; testmon db preferred)
    covered: dict[str, int] = defaultdict(int)
    testmon = repo / ".cache" / "testmon" / "testmondata"
    if testmon.exists():
        try:
            import sqlite3

            conn = sqlite3.connect(f"file:{testmon}?mode=ro&immutable=1", uri=True)
            for fname, cnt in conn.execute(
                "SELECT ff.filename, COUNT(DISTINCT n.name) FROM node_fingerprint nf "
                "JOIN node n ON n.id = nf.node_id "
                "JOIN fingerprint fp ON fp.id = nf.fingerprint_id "
                "JOIN file_fp ff ON ff.id = fp.file_fp_id GROUP BY ff.filename"
            ):
                if fname in loc:
                    covered[fname] = cnt
            conn.close()
        except Exception:
            covered.clear()
    if not covered:
        grep = sh(
            ["grep", "-rl", "-E", "from polylogue|import polylogue", "tests/"], repo
        )
        test_files = [t for t in grep.splitlines() if t.endswith(".py")]
        for t in test_files:
            body = (repo / t).read_text(errors="replace")
            for rel in loc:
                mod = rel[:-3].replace("/", ".")
                if mod in body:
                    covered[rel] += 1

    # past defect density: bead descriptions mentioning the file (best effort)
    defects: dict[str, int] = defaultdict(int)
    try:
        beads = subprocess.run(
            ["bd", "list", "--json", "--all"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
        blob = beads if beads else "[]"
        for rel in loc:
            defects[rel] = len(re.findall(re.escape(rel), blob))
    except Exception:
        pass

    # sweep ledger penalty
    swept: dict[str, str] = {}
    ledger = repo / ".agent" / "scratch" / "sweep-ledger.jsonl"
    head = sh(["git", "rev-parse", "HEAD"], repo).strip()
    if ledger.exists():
        for line in ledger.open():
            try:
                row = json.loads(line)
                swept[row["module"]] = row.get("commit", "")
            except Exception:
                continue

    rows = []
    for rel, n in loc.items():
        if n < 60:
            continue
        cov = covered.get(rel, 0)
        thin = 1.0 / (1.0 + cov)
        ch = 1.0 + math.log1p(churn.get(rel, 0))
        dd = 1.0 + 0.5 * defects.get(rel, 0)
        penalty = 0.25 if swept.get(rel) == head else 1.0
        score = n * thin * ch * dd * penalty
        rows.append(
            (score, rel, n, cov, churn.get(rel, 0), defects.get(rel, 0), rel in swept)
        )

    rows.sort(reverse=True)
    print(f"{'score':>10}  {'LOC':>5} {'cov':>4} {'chn':>3} {'bd':>3} swept  module")
    for score, rel, n, cov, ch, dd, sw in rows[: args.top]:
        print(
            f"{score:10.0f}  {n:5d} {cov:4d} {ch:3d} {dd:3d} {'y' if sw else '-':>5}  {rel}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
