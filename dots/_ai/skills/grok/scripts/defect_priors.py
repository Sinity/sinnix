#!/usr/bin/env python3
"""Defect-prior scoreboard: rank Rust modules for the next hunt wave.

Prior = lines x thin tests x churn x past-defect mentions. Machines rank,
models judge. Tests live in a sibling `tests.rs` (or `<module>/tests.rs`), so
a module's test count is the number of `#[test]` functions there.

Usage: defect_priors.py [--repo /realm/project/polylogue/repo] [--top 25]
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

TEST_ATTR = re.compile(r"#\[(?:tokio::)?test")


def sh(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=300
    ).stdout


def sibling_tests(path: Path) -> Path | None:
    for candidate in (path.with_suffix("") / "tests.rs", path.parent / "tests.rs"):
        if candidate.is_file() and candidate != path:
            return candidate
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/realm/project/polylogue/repo")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()
    repo = Path(args.repo)

    loc: dict[str, int] = {}
    tests: dict[str, int] = {}
    for f in repo.glob("crates/*/src/**/*.rs"):
        if f.name == "tests.rs" or "/tests/" in str(f):
            continue
        rel = str(f.relative_to(repo))
        try:
            loc[rel] = sum(1 for _ in f.open(errors="replace"))
            sibling = sibling_tests(f)
            tests[rel] = (
                len(TEST_ATTR.findall(sibling.read_text(errors="replace")))
                if sibling
                else 0
            )
        except OSError:
            continue

    churn: dict[str, int] = defaultdict(int)
    out = sh(["git", "log", "--since=60.days", "--name-only", "--pretty=format:"], repo)
    for line in out.splitlines():
        if line.strip() in loc:
            churn[line.strip()] += 1

    defects: dict[str, int] = defaultdict(int)
    beads = (
        subprocess.run(
            ["bd", "list", "--json", "--all"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
        or "[]"
    )
    for rel in loc:
        defects[rel] = len(re.findall(re.escape(rel), beads))

    rows = []
    for rel, n in loc.items():
        if n < 60:
            continue
        thin = 1.0 / (1.0 + tests[rel])
        score = n * thin * (1.0 + math.log1p(churn[rel])) * (1.0 + 0.5 * defects[rel])
        rows.append((score, rel, n, tests[rel], churn[rel], defects[rel]))

    rows.sort(reverse=True)
    print(f"{'score':>10}  {'lines':>5} {'tests':>5} {'chn':>3} {'bd':>3}  module")
    for score, rel, n, t, ch, dd in rows[: args.top]:
        print(f"{score:10.0f}  {n:5d} {t:5d} {ch:3d} {dd:3d}  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
