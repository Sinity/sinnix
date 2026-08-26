#!/usr/bin/env python3
"""Derived campaign truth: one lifecycle state per unit of work.

SPEC WARNING (2026-08-26): this prototype's CLASSIFICATION is wrong and is kept
only for its data-joining shape. It decides "unpublished" from PR existence,
but worktree<->PR is not 1:1 — a branch ships a sequence of PRs, one PR carries
many beads, and content can land without that branch's PR. That over-reported
at-risk work 55 vs 5, and its gc would delete a worktree that shipped a slice
and then accumulated unpublished commits. The shipped surface must classify by
CONTENT: a unit holds unpublished work iff any file it introduces still differs
from master. See sinnix-235w.

Every stage of a lane's life already has an authoritative store — Beads for
intent, sinnixd job records for execution, git for artifacts, GitHub for
publication. Nothing joined them, so work fell through the gaps: finished
lanes whose harvest silently failed, branches that were never pushed, merged
worktrees nobody disposed. This derives the join from those stores only. It
holds no state of its own and can always be recomputed.

  campaign status      full table, one row per worktree
  campaign stuck       only rows needing action, with the reason
  campaign gc          disposable worktrees (add --apply to remove them)
  campaign launchable  ready beads with no unit in flight

Intended end state: this becomes `agentctl campaign status` (sinnix-txye).
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

WORKTREE_ROOT = pathlib.Path("/realm/worktrees")
JOBS = pathlib.Path.home() / ".local/state/sinnixd/jobs"
PROJECT_ROOTS = {
    "polylogue": pathlib.Path("/realm/project/polylogue"),
    "sinnix": pathlib.Path("/realm/project/sinnix"),
}


def run(cmd: list[str], cwd: pathlib.Path | None = None, timeout: int = 30) -> str:
    try:
        out = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return out.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""


def live_worktree_cwds() -> set[str]:
    """Paths that some process currently has as its working directory."""
    live: set[str] = set()
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            live.add(os.readlink(proc / "cwd"))
        except OSError:
            continue
    return live


def running_job_paths() -> set[str]:
    """Workspace paths owned by a job that has not reached a terminal state."""
    paths: set[str] = set()
    if not JOBS.is_dir():
        return paths
    for record in JOBS.glob("*.json"):
        try:
            data = json.loads(record.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("state", {}).get("terminal"):
            continue
        spec = data.get("spec", {}) or {}
        for key in ("workspace_path", "checkout_path", "working_directory"):
            value = spec.get(key)
            if isinstance(value, str) and value.startswith(str(WORKTREE_ROOT)):
                paths.add(value)
    return paths


def pr_index(project: str) -> dict[str, tuple[int, str]]:
    """branch -> (number, state) for every PR the repo knows about."""
    root = PROJECT_ROOTS.get(project)
    if root is None:
        return {}
    raw = run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--limit",
            "300",
            "--json",
            "number,state,headRefName",
        ],
        cwd=root,
        timeout=60,
    )
    try:
        rows = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return {}
    index: dict[str, tuple[int, str]] = {}
    for row in rows:
        branch = row.get("headRefName")
        if isinstance(branch, str) and branch not in index:
            index[branch] = (row.get("number", 0), row.get("state", "?"))
    return index


def closed_beads(project: str) -> set[str]:
    root = PROJECT_ROOTS.get(project)
    if root is None:
        return set()
    raw = run(
        ["bd", "list", "--status", "closed", "--limit", "4000"], cwd=root, timeout=60
    )
    found: set[str] = set()
    for line in raw.splitlines():
        for token in line.split():
            if token.startswith(f"{project}-"):
                found.add(token)
    return found


def units() -> list[dict[str, object]]:
    live_cwds = live_worktree_cwds()
    running = running_job_paths()
    pr_cache: dict[str, dict[str, tuple[int, str]]] = {}
    closed_cache: dict[str, set[str]] = {}
    rows: list[dict[str, object]] = []

    for path in sorted(WORKTREE_ROOT.iterdir() if WORKTREE_ROOT.is_dir() else []):
        if not path.is_dir():
            continue
        name = path.name
        project = (
            "polylogue"
            if "polylogue" in name
            else "sinnix"
            if "sinnix" in name
            else "?"
        )
        branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
        base = run(["git", "merge-base", "HEAD", "origin/master"], cwd=path)
        ahead_raw = (
            run(["git", "log", "--oneline", f"{base}..HEAD"], cwd=path) if base else ""
        )
        ahead = len([line for line in ahead_raw.splitlines() if line.strip()])
        dirty = bool(run(["git", "status", "--porcelain"], cwd=path))

        if project not in pr_cache:
            pr_cache[project] = pr_index(project)
            closed_cache[project] = closed_beads(project)
        pr = pr_cache[project].get(branch)

        bead = None
        prefix = f"packet-{project}-"
        if name.startswith(prefix):
            bead = f"{project}-{name[len(prefix) :]}"

        is_running = str(path) in running
        has_live_cwd = any(
            c == str(path) or c.startswith(str(path) + "/") for c in live_cwds
        )

        if is_running:
            state, reason = "running", "job in flight"
        elif dirty:
            state, reason = "dirty", "uncommitted changes"
        elif pr and pr[1] == "MERGED":
            state, reason = "merged", f"PR #{pr[0]} merged; worktree can be disposed"
        elif pr and pr[1] == "OPEN":
            state, reason = "published", f"PR #{pr[0]} open"
        elif pr and pr[1] == "CLOSED":
            state, reason = "pr-closed", f"PR #{pr[0]} closed unmerged"
        elif ahead > 0:
            state, reason = (
                "UNPUBLISHED",
                f"{ahead} commit(s) with no PR — work at risk",
            )
        elif bead and bead in closed_cache.get(project, set()):
            state, reason = "spent", "no commits; bead already closed"
        else:
            state, reason = "empty", "no commits, no PR"

        rows.append(
            {
                "name": name,
                "project": project,
                "branch": branch,
                "ahead": ahead,
                "dirty": dirty,
                "pr": f"#{pr[0]} {pr[1]}" if pr else "-",
                "bead": bead or "-",
                "state": state,
                "reason": reason,
                "live_cwd": has_live_cwd,
                "path": str(path),
            }
        )
    return rows


ACTIONABLE = {"UNPUBLISHED", "dirty", "pr-closed"}
DISPOSABLE = {"merged", "spent", "empty"}


def main() -> int:
    verb = sys.argv[1] if len(sys.argv) > 1 else "status"

    if verb == "launchable":
        os.execvp("launchable", ["launchable", *sys.argv[2:]])

    rows = units()

    if verb == "status":
        counts: dict[str, int] = {}
        for row in rows:
            counts[str(row["state"])] = counts.get(str(row["state"]), 0) + 1
        for row in sorted(rows, key=lambda r: (str(r["state"]), str(r["name"]))):
            print(
                f"{str(row['state']):<12} {str(row['name']):<42} {str(row['pr']):<14} {row['reason']}"
            )
        print(
            "\n"
            + "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            + f"  total={len(rows)}"
        )
        return 0

    if verb == "stuck":
        hits = [r for r in rows if r["state"] in ACTIONABLE]
        for row in sorted(hits, key=lambda r: str(r["state"])):
            print(
                f"{str(row['state']):<12} {str(row['name']):<42} {str(row['bead']):<22} {row['reason']}"
            )
        print(f"\n{len(hits)} unit(s) need action")
        return 1 if hits else 0

    if verb == "gc":
        apply = "--apply" in sys.argv
        candidates = [
            r
            for r in rows
            if r["state"] in DISPOSABLE and not r["live_cwd"] and not r["dirty"]
        ]
        for row in candidates:
            if not apply:
                print(f"WOULD DISPOSE {str(row['name']):<42} {row['reason']}")
                continue
            root = PROJECT_ROOTS.get(str(row["project"]))
            if root is None:
                continue
            removed = run(
                [
                    "git",
                    "-C",
                    str(root),
                    "worktree",
                    "remove",
                    "--force",
                    str(row["path"]),
                ],
                timeout=60,
            )
            run(
                ["git", "-C", str(root), "branch", "-D", str(row["branch"])], timeout=30
            )
            print(f"DISPOSED {row['name']} {removed}")
        print(
            f"\n{len(candidates)} disposable{' (dry run; pass --apply)' if not apply else ''}"
        )
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
