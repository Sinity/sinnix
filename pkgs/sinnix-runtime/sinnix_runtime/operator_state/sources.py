"""Collectors for the operator state: one function per owner of the facts.

Each collector makes a small, bounded read (one command, one file, a few
procfs entries) and returns plain data. ``service.OperatorState`` decides how
often each runs; none of them starts a build or walks a directory tree.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomllib

from .history import bead_sample

BD = "/run/current-system/sw/bin/bd"
COMMAND_TIMEOUT = 45.0
CHANGE_WINDOW_DAYS = 7
CHANGE_LIMIT = 40
CONTAINS_LIMIT = 5000
CLOSED_BEADS_DAYS = 120
GITHUB_URL = re.compile(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$")
FAILING = {
    "FAILURE",
    "ERROR",
    "CANCELLED",
    "TIMED_OUT",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
}


def run(
    argv: list[str], cwd: str | Path | None = None, timeout: float = COMMAND_TIMEOUT
) -> str:
    result = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]
        raise RuntimeError(
            f"{Path(argv[0]).name} exited {result.returncode}: {detail[0][:200]}"
        )
    return result.stdout


def utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def registered_projects(config_path: Path) -> list[dict[str, str]]:
    """The projects agentctl is configured with, from its own config file and
    the private project catalog that file names."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    roots = [Path(root) for root in config.get("project_roots") or []]
    catalog = config.get("private_project_catalog")
    if catalog:
        try:
            rows = json.loads(Path(catalog).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rows = {}
        rows = rows.get("projects", rows) if isinstance(rows, dict) else {}
        for row in rows.values() if isinstance(rows, dict) else []:
            if isinstance(row, dict) and row.get("agentctl") and row.get("path"):
                roots.append(Path(row["path"]))
    projects, seen = [], set()
    for root in roots:
        name = project_id(root)
        if name and name not in seen:
            seen.add(name)
            projects.append({"id": name, "root": str(root)})
    return projects


def project_id(root: Path) -> str | None:
    """The id a project's own descriptor declares."""
    try:
        with open(root / ".agentctl" / "project.toml", "rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    name = (value.get("project") or {}).get("id")
    return name if isinstance(name, str) else None


# ---------------------------------------------------------------- Beads


def beads_waiting(root: str) -> list[dict[str, Any]]:
    """Open issues labelled ``human``: the questions that block work."""
    value = json.loads(run([BD, "human", "list", "--json"], cwd=root) or "null")
    return [
        {
            key: row.get(key)
            for key in ("id", "title", "priority", "created_at", "updated_at", "status")
        }
        for row in value or []
        if isinstance(row, dict)
    ]


def beads_counts(root: str) -> dict[str, Any]:
    """Counts by status and the in-progress tasks, in two bounded reads."""
    counts = json.loads(run([BD, "count", "--by-status", "--json"], cwd=root))
    by_status = {group["group"]: group["count"] for group in counts.get("groups") or []}
    rows = json.loads(
        run(
            [
                BD,
                "list",
                "--status",
                "in_progress",
                "--brief",
                "--json",
                "--limit",
                "40",
            ],
            cwd=root,
        )
        or "[]"
    )
    keep = (
        "id",
        "title",
        "issue_type",
        "labels",
        "estimated_minutes",
        "metadata",
        "started_at",
        "assignee",
    )
    return {
        "open": by_status.get("open", 0),
        "in_progress_count": by_status.get("in_progress", 0),
        "in_progress": [{key: row.get(key) for key in keep} for row in rows or []],
    }


def closed_bead_samples(project: str, root: str, now: datetime) -> list[dict[str, Any]]:
    since = utc(now.timestamp() - CLOSED_BEADS_DAYS * 86400)[:10]
    rows = json.loads(
        run(
            [
                BD,
                "list",
                "--status",
                "closed",
                "--closed-after",
                since,
                "--brief",
                "--json",
                "--limit",
                "0",
            ],
            cwd=root,
            timeout=120,
        )
        or "[]"
    )
    samples = (bead_sample(project, row) for row in rows or [] if isinstance(row, dict))
    return [sample for sample in samples if sample is not None]


# ---------------------------------------------------------------- Git and checks


def default_branch(root: str) -> str:
    """``origin/<branch>``, or the checked-out branch of a repository without
    a remote default."""
    try:
        return run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=root
        ).strip()
    except RuntimeError:
        return run(["git", "symbolic-ref", "--short", "HEAD"], cwd=root).strip()


def git_changes(root: str) -> dict[str, Any]:
    """Recent first-parent commits on the default branch, newest first."""
    branch = default_branch(root)
    output = run(
        [
            "git",
            "log",
            branch,
            "--first-parent",
            f"-n{CHANGE_LIMIT}",
            f"--since={CHANGE_WINDOW_DAYS}.days",
            "--format=%H%x1f%ct%x1f%s",
        ],
        cwd=root,
    )
    commits = []
    for line in output.splitlines():
        sha, stamp, subject = line.split("\x1f", 2)
        commits.append({"commit": sha, "at": utc(int(stamp)), "subject": subject[:200]})
    return {"default_branch": branch, "commits": commits}


def git_fetch(root: str) -> None:
    remote, _, branch = default_branch(root).partition("/")
    if remote != "origin" or not branch:
        return  # nothing to fetch for a repository without a remote default
    run(
        ["git", "fetch", "--quiet", "--no-tags", "origin", branch], cwd=root, timeout=60
    )


def rollup_verdict(rollup: Any) -> str:
    verdicts = []
    for check in rollup or []:
        conclusion = str(check.get("conclusion") or check.get("state") or "").upper()
        status = str(check.get("status") or "").upper()
        if conclusion in FAILING:
            verdicts.append("failing")
        elif status in {
            "QUEUED",
            "IN_PROGRESS",
            "PENDING",
            "WAITING",
        } or conclusion in {"PENDING", "EXPECTED", ""}:
            verdicts.append("pending")
        else:
            verdicts.append("passed")
    if not verdicts:
        return "none"
    return (
        "failing"
        if "failing" in verdicts
        else "pending"
        if "pending" in verdicts
        else "passed"
    )


def hosted_checks(root: str, branch: str) -> dict[str, Any]:
    """Merged pull requests with their check verdicts, and the default branch's
    latest hosted runs. Two ``gh`` calls."""
    merged = json.loads(
        run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "merged",
                "--limit",
                "40",
                "--json",
                "number,title,url,mergedAt,mergeCommit,statusCheckRollup",
            ],
            cwd=root,
        )
    )
    runs = json.loads(
        run(
            [
                "gh",
                "run",
                "list",
                "--branch",
                branch,
                "--limit",
                "12",
                "--json",
                "name,conclusion,status,headSha,workflowName",
            ],
            cwd=root,
        )
    )
    # The newest run of each workflow describes the branch as it stands.
    latest: dict[str, dict[str, Any]] = {}
    for item in runs:
        latest.setdefault(str(item.get("workflowName") or item.get("name")), item)
    failing = sorted(
        name
        for name, item in latest.items()
        if str(item.get("conclusion")).upper() in FAILING
    )
    pending = sorted(
        name for name, item in latest.items() if item.get("status") != "completed"
    )
    state = (
        "failing"
        if failing
        else "pending"
        if pending
        else "passed"
        if latest
        else "none"
    )
    return {
        "merged": [
            {
                "number": pull.get("number"),
                "url": pull.get("url"),
                "merged_at": pull.get("mergedAt"),
                "merge_commit": (pull.get("mergeCommit") or {}).get("oid"),
                "check": rollup_verdict(pull.get("statusCheckRollup")),
            }
            for pull in merged
        ],
        "default_check": {
            "state": state,
            "failing": failing,
            "pending": pending,
            "head": next(iter(latest.values()), {}).get("headSha"),
        },
    }


def github_slug(root: str) -> str | None:
    try:
        url = run(["git", "remote", "get-url", "origin"], cwd=root).strip()
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return None
    match = GITHUB_URL.search(url)
    return f"{match.group(1)}/{match.group(2)}".lower() if match else None


# ---------------------------------------------------------------- deployment


def host_revision() -> str:
    return run(["nixos-version", "--configuration-revision"]).strip()


def contained_commits(root: str, revision: str) -> set[str] | None:
    try:
        return set(
            run(["git", "rev-list", f"-n{CONTAINS_LIMIT}", revision], cwd=root).split()
        )
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return None


def deployment(
    projects: list[dict[str, str]], slugs: dict[str, str | None]
) -> dict[str, Any]:
    """Which revision of each product runs on this machine.

    The host configuration is the project whose repository holds the running
    configuration revision. Another project is deployed when that revision's
    ``flake.lock`` pins its GitHub repository as a direct input.
    """
    revision = host_revision()
    result: dict[str, Any] = {"host_revision": revision, "projects": {}}
    host = None
    for project in projects:
        if not (Path(project["root"]) / "flake.lock").exists():
            continue
        probe = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
            cwd=project["root"],
            capture_output=True,
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
        if probe.returncode == 0:
            host = project
            break
    if host is None:
        return result
    result["projects"][host["id"]] = {
        "kind": "host",
        "revision": revision,
        "contains": contained_commits(host["root"], revision),
    }
    lock = json.loads(run(["git", "show", f"{revision}:flake.lock"], cwd=host["root"]))
    nodes = lock.get("nodes") or {}
    direct = (nodes.get(lock.get("root", "root")) or {}).get("inputs") or {}
    for name, target in sorted(direct.items()):
        locked = (
            (nodes.get(target) or {}).get("locked") if isinstance(target, str) else None
        )
        if not isinstance(locked, dict):
            continue
        if locked.get("type") == "github":
            slug = f"{locked.get('owner')}/{locked.get('repo')}".lower()
        else:
            match = GITHUB_URL.search(str(locked.get("url") or ""))
            if match is None:
                continue
            slug = f"{match.group(1)}/{match.group(2)}".lower()
        for project in projects:
            if project["id"] != host["id"] and slugs.get(project["id"]) == slug:
                # Several inputs may pin one repository; keep each, newest last.
                entry = result["projects"].setdefault(
                    project["id"],
                    {"kind": "flake-input", "inputs": [], "contains": set()},
                )
                entry["inputs"].append({"input": name, "revision": locked.get("rev")})
                contained = contained_commits(project["root"], locked.get("rev"))
                if contained is None:
                    entry["contains"] = None
                elif entry["contains"] is not None:
                    entry["contains"] |= contained
    for entry in result["projects"].values():
        if entry["kind"] == "flake-input":
            entry["revision"] = entry["inputs"][0]["revision"]
    return result


# ---------------------------------------------------------------- limits and load


def _pressure(resource: str) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for line in Path(f"/proc/pressure/{resource}").read_text().splitlines():
        kind, *fields = line.split()
        values = dict(field.split("=", 1) for field in fields)
        rows[kind] = {"avg10": float(values["avg10"]), "avg60": float(values["avg60"])}
    return rows


def _cgroup_number(path: Path) -> int | None:
    try:
        text = path.read_text().strip()
    except OSError:
        return None
    return int(text) if text.isdecimal() else None


def machine_load() -> dict[str, Any]:
    """Memory, page cache, swap, pressure and the agent slice, from procfs."""
    meminfo = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        name, _, rest = line.partition(":")
        meminfo[name] = int(rest.split()[0]) * 1024
    result: dict[str, Any] = {
        "memory": {
            "total": meminfo.get("MemTotal"),
            "available": meminfo.get("MemAvailable"),
            # File-backed pages only: `Cached` also counts tmpfs and shared memory.
            "page_cache": meminfo.get("Active(file)", 0)
            + meminfo.get("Inactive(file)", 0),
            "swap_total": meminfo.get("SwapTotal"),
            "swap_used": meminfo.get("SwapTotal", 0) - meminfo.get("SwapFree", 0),
        },
        "pressure": {},
        "slices": [],
    }
    for resource in ("memory", "io", "cpu"):
        try:
            result["pressure"][resource] = _pressure(resource)
        except (OSError, ValueError, KeyError):
            result["pressure"][resource] = None
    base = Path(
        f"/sys/fs/cgroup/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/agent.slice"
    )
    candidates = [base]
    try:
        candidates += sorted(
            child for child in base.iterdir() if child.name.endswith(".slice")
        )
    except OSError:
        pass
    for path in candidates:
        current = _cgroup_number(path / "memory.current")
        if current is None:
            continue
        result["slices"].append(
            {
                "slice": path.name,
                "memory_current": current,
                "memory_high": _cgroup_number(path / "memory.high"),
                "memory_max": _cgroup_number(path / "memory.max"),
                "swap_current": _cgroup_number(path / "memory.swap.current"),
            }
        )
    return result


def claude_usage() -> dict[str, Any]:
    """Claude subscription usage from the existing ``claude-quota`` tool."""
    value = json.loads(run(["claude-quota", "status", "--json"], timeout=30))
    return {
        "observed_at": utc(value["ts"]) if value.get("ts") else None,
        "five_hour_percent": value.get("five_hour"),
        "five_hour_resets_at": utc(value["five_hour_resets_at"])
        if value.get("five_hour_resets_at")
        else None,
        "seven_day_percent": value.get("seven_day"),
        "seven_day_resets_at": utc(value["seven_day_resets_at"])
        if value.get("seven_day_resets_at")
        else None,
        "burn_percent_per_hour": value.get("burn_pct_per_hour"),
    }


def codex_usage(sessions: Path | None = None) -> dict[str, Any]:
    """The rate limits the newest Codex session last reported.

    Reads the tail of one session file; Codex writes its limits there after
    each turn.
    """
    sessions = sessions or Path.home() / ".codex" / "sessions"
    newest: Path | None = None

    def newest_directory(parent: Path) -> list[Path]:
        return sorted(
            (entry for entry in parent.iterdir() if entry.is_dir()), reverse=True
        )

    for year in newest_directory(sessions)[:1]:
        for month in newest_directory(year)[:1]:
            for day in newest_directory(month)[:2]:
                files = sorted(day.glob("rollout-*.jsonl"), reverse=True)
                if files:
                    newest = files[0]
                    break
    if newest is None:
        raise RuntimeError("no Codex session file found")
    with open(newest, "rb") as handle:
        handle.seek(max(0, newest.stat().st_size - 400_000))
        tail = handle.read().decode("utf-8", "replace")
    position = tail.rfind('"rate_limits":')
    if position < 0:
        raise RuntimeError("the newest Codex session reports no limits yet")
    limits, _ = json.JSONDecoder().raw_decode(tail, position + len('"rate_limits":'))
    windows = []
    for name in ("primary", "secondary"):
        window = limits.get(name)
        if isinstance(window, dict):
            windows.append(
                {
                    "window_minutes": window.get("window_minutes"),
                    "used_percent": window.get("used_percent"),
                    "resets_at": utc(window["resets_at"])
                    if window.get("resets_at")
                    else None,
                }
            )
    return {
        "observed_at": utc(newest.stat().st_mtime),
        "plan": limits.get("plan_type"),
        "windows": windows,
    }
