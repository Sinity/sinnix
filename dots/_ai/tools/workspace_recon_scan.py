#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    p = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True
    )
    return p.returncode, p.stdout.rstrip("\n"), p.stderr.rstrip("\n")


def parse_status_porcelain(text: str) -> dict[str, int]:
    staged = 0
    unstaged = 0
    untracked = 0
    conflicted = 0
    lines = [ln for ln in text.splitlines() if ln]
    for ln in lines:
        if ln.startswith("??"):
            untracked += 1
            continue
        if len(ln) < 2:
            continue
        x, y = ln[0], ln[1]
        if x != " ":
            staged += 1
        if y != " ":
            unstaged += 1
        if x == "U" or y == "U":
            conflicted += 1
    return {
        "changed": len(lines),
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "conflicted": conflicted,
    }


def upstream_ahead_behind(repo: Path) -> tuple[int | None, int | None]:
    rc, out, _ = run(
        ["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"], cwd=repo
    )
    if rc != 0 or not out:
        return None, None
    parts = out.split()
    if len(parts) != 2:
        return None, None
    behind = int(parts[0])
    ahead = int(parts[1])
    return ahead, behind


@dataclass
class RepoInfo:
    path: str
    branch: str
    clean: bool
    changed: int
    staged: int
    unstaged: int
    untracked: int
    conflicted: int
    ahead: int | None
    behind: int | None
    last_commit_short: str
    last_commit_date: str
    size_mb: int | None = None


def repo_size_mb(repo: Path) -> int | None:
    rc, out, _ = run(["du", "-sm", str(repo)])
    if rc != 0 or not out:
        return None
    head = out.split()[0]
    try:
        return int(head)
    except ValueError:
        return None


def inspect_repo(repo: Path, include_size: bool) -> RepoInfo:
    _, branch, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    _, status, _ = run(["git", "status", "--porcelain"], cwd=repo)
    counts = parse_status_porcelain(status)

    _, lc_short, _ = run(["git", "log", "-1", "--pretty=format:%h %s"], cwd=repo)
    _, lc_date, _ = run(["git", "log", "-1", "--pretty=format:%cs"], cwd=repo)

    ahead, behind = upstream_ahead_behind(repo)
    size_mb = repo_size_mb(repo) if include_size else None

    return RepoInfo(
        path=str(repo),
        branch=branch or "DETACHED",
        clean=counts["changed"] == 0,
        changed=counts["changed"],
        staged=counts["staged"],
        unstaged=counts["unstaged"],
        untracked=counts["untracked"],
        conflicted=counts["conflicted"],
        ahead=ahead,
        behind=behind,
        last_commit_short=lc_short,
        last_commit_date=lc_date,
        size_mb=size_mb,
    )


def find_repos(root: Path, max_depth: int) -> list[Path]:
    repos: set[Path] = set()
    root = root.resolve()
    for current_root, dirs, _ in os.walk(root):
        cur = Path(current_root)
        rel_depth = len(cur.relative_to(root).parts)
        if rel_depth > max_depth:
            dirs[:] = []
            continue
        if ".git" in dirs:
            repos.add(cur)
            dirs[:] = []
            continue
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", "node_modules", ".venv", "target", "dist"}
        ]
    return sorted(repos)


def print_table(repos: Iterable[RepoInfo], root: Path) -> None:
    print("PATH\tBRANCH\tSTATE\tCHANGED\tAHEAD/BEHIND\tLAST_COMMIT")
    for r in repos:
        rel = Path(r.path).resolve().relative_to(root)
        state = "clean" if r.clean else "dirty"
        ab = f"{r.ahead if r.ahead is not None else '-'} / {r.behind if r.behind is not None else '-'}"
        print(
            f"{rel}\t{r.branch}\t{state}\t{r.changed}\t{ab}\t{r.last_commit_date} {r.last_commit_short}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Fast multi-repo workspace scanner")
    ap.add_argument("--root", default="/realm/project", help="Root directory to scan")
    ap.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Max directory depth for repo discovery",
    )
    ap.add_argument(
        "--workers", type=int, default=12, help="Concurrent repo inspectors"
    )
    ap.add_argument(
        "--changed-only", action="store_true", help="Only output dirty repos"
    )
    ap.add_argument(
        "--with-size", action="store_true", help="Include approximate repo size (MB)"
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of repos in output (0 = no limit)",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    repos = find_repos(root, args.max_depth)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        infos = list(ex.map(lambda p: inspect_repo(p, args.with_size), repos))

    if args.changed_only:
        infos = [r for r in infos if not r.clean]

    infos = sorted(infos, key=lambda r: (r.clean, -r.changed, r.path))

    if args.limit > 0:
        infos = infos[: args.limit]

    summary = {
        "root": str(root),
        "repo_count": len(repos),
        "shown_count": len(infos),
        "dirty_count": sum(1 for r in infos if not r.clean),
        "clean_count": sum(1 for r in infos if r.clean),
    }

    if args.json:
        payload = {"summary": summary, "repos": [asdict(r) for r in infos]}
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"root={summary['root']} repos={summary['repo_count']} shown={summary['shown_count']} "
            f"dirty={summary['dirty_count']} clean={summary['clean_count']}"
        )
        print_table(infos, root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
