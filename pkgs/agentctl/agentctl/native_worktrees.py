"""Retire native job checkouts whose exact work is already published."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import (
    artifacts,
    gitcmd,
    github,
    job_queries,
    pueue,
    worktree_processes,
    worktrunk,
)
from .worktree_cleanup import (
    CleanupError,
    _digest,
    _drop_branch,
    _external_cache,
    _git,
    _ignored_caches,
    _preserve_artifacts,
    _recovery_ref,
    _remove_cache,
    project_locked,
)
from .worktree_cleanup import (
    _cargo_cache as _cache,
)

CACHE_TAG = b"Signature: 8a477f597d28d172789f06886806bc55"


def _base(project) -> str:
    names = [project.workspace.default_base] if project.workspace else []
    names.append("refs/remotes/origin/HEAD")
    branch = gitcmd.git(
        project.root,
        "symbolic-ref",
        "--quiet",
        "HEAD",
        ok_statuses=(0, 1),
        error=CleanupError,
    )
    if branch.startswith("refs/heads/"):
        names.extend(
            ("refs/remotes/origin/" + branch.removeprefix("refs/heads/"), branch)
        )
    for name in names:
        value = gitcmd.git(
            project.root,
            "rev-parse",
            "--verify",
            "--quiet",
            name + "^{commit}",
            ok_statuses=(0, 1),
            error=CleanupError,
        )
        if value:
            return value
    raise CleanupError("default branch could not be resolved")


class Published:
    """One default-branch history, with optional exact merged-PR witnesses."""

    def __init__(self, project):
        self.root = project.root
        self.base = _base(project)
        history = _git(self.root, "log", "--format=%H %T", self.base).splitlines()
        self.commits = set()
        self.trees = set()
        for row in history:
            commit, tree = row.split()
            self.commits.add(commit)
            self.trees.add(tree)
        self.pulls: dict[str, str] | None = None
        self.local_deadline: float | None = None

    def contains(self, head: str) -> bool:
        if head in self.commits:
            return True
        tree = _git(self.root, "rev-parse", head + "^{tree}")
        if tree in self.trees:
            return True
        if self.pulls is None:
            self.pulls = {}
            try:
                rows = github.gh_json(
                    [
                        "pr",
                        "list",
                        "--state",
                        "merged",
                        "--limit",
                        "1000",
                        "--json",
                        "headRefOid,mergeCommit",
                    ],
                    cwd=self.root,
                )
                for row in rows or []:
                    commit = (row.get("mergeCommit") or {}).get("oid")
                    if commit in self.commits:
                        self.pulls[row["headRefOid"]] = commit
            except github.GithubError:
                pass
        if head in self.pulls:
            return True
        if self.local_deadline is None:
            self.local_deadline = time.monotonic() + 2
        if time.monotonic() >= self.local_deadline:
            return False
        # Optional local proof is limited by tree metadata before any merge
        # reads blobs. Large historical rewrites stay explicitly unproved.
        try:
            common = _git(self.root, "merge-base", self.base, head, timeout=1)
            paths = _git(
                self.root,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "-z",
                common,
                head,
                timeout=1,
            ).split("\0")
            paths = [path for path in paths if path]
            if len(paths) > 64 or time.monotonic() >= self.local_deadline:
                return False
            size = 0
            for commit in (common, head, self.base):
                if time.monotonic() >= self.local_deadline:
                    return False
                for entry in _git(
                    self.root, "ls-tree", "-rlz", commit, "--", *paths, timeout=1
                ).split("\0"):
                    if entry:
                        fields = entry.split("\t", 1)[0].split()
                        size += int(fields[3])
                        if size > 2 * 1024 * 1024:
                            return False
            if time.monotonic() >= self.local_deadline:
                return False
            merged = _git(
                self.root, "merge-tree", "--write-tree", self.base, head, timeout=1
            )
            return merged.splitlines()[0] == _git(
                self.root, "rev-parse", self.base + "^{tree}"
            )
        except (CleanupError, ValueError):
            return False


def _owners(config, project, tasks, selected=None) -> dict[Path, dict[str, Any]]:
    """Read invocation ownership once, including queue entries already cleaned."""
    live = {job_queries.job_id_of(task): task for task in tasks.values()}
    found: dict[Path, dict[str, Any]] = {}
    for path in config.inputs_dir.glob(project.project_id + "-*.json"):
        raw = job_queries.read_bounded(path, job_queries.MAX_LAUNCH_INPUT_BYTES)
        try:
            doc = json.loads(raw) if raw else None
        except (ValueError, UnicodeError):
            continue
        if not isinstance(doc, dict) or doc.get("project_id") != project.project_id:
            continue
        cwd = Path(doc.get("working_directory", ""))
        if (
            not cwd.is_absolute()
            or cwd == project.root
            or (selected is not None and cwd not in selected)
        ):
            continue
        owner = found.setdefault(cwd, {"terminal": True, "heads": set()})
        task = live.get(path.stem)
        if task is not None and not task.terminal:
            owner["terminal"] = False
            continue
        outcome = None
        try:
            output = artifacts.paths_for(doc)["outcome"].resolve(strict=True)
            if output.is_relative_to(config.jobs_dir.resolve()):
                outcome = job_queries.read_outcome(
                    output, job_queries.MAX_OUTCOME_BYTES
                )
        except (KeyError, OSError, ValueError):
            pass
        if outcome is None:
            disposition = job_queries.read_outcome(
                job_queries.disposition_path(path), job_queries.MAX_OUTCOME_BYTES
            )
            cancelled = (
                disposition is not None
                and disposition.get("outcome") == "cancelled"
                and not disposition.get("unresolved")
            )
            if not cancelled and (task is None or not task.terminal):
                owner["terminal"] = False
            continue
        end = (outcome.get("execution_receipt") or {}).get("end") or {}
        if end.get("status") == "observed" and end.get("head"):
            owner["heads"].add(end["head"])
    return found


def _target_users(config, registry, roots):
    """Live native target arguments and existing aliases pin exact outputs."""
    pins = []
    for task in pueue.tasks().values():
        if task.terminal:
            continue
        doc = job_queries.read_launch_input(config, task) or {}
        env = doc.get("environment") or {}
        values = [
            env.get("CARGO_TARGET_DIR"),
            doc.get("working_directory"),
            doc.get("log_path"),
            doc.get("result_path"),
        ]
        argv = doc.get("argv") or []
        for i, value in enumerate(argv):
            if value.startswith(("CARGO_TARGET_DIR=", "--target-dir=")):
                values.append(value.split("=", 1)[1])
            elif value == "--target-dir" and i + 1 < len(argv):
                values.append(argv[i + 1])
        pins.extend(
            (Path(value).resolve(), f"active job {task.task_id} target {value}")
            for value in values
            if isinstance(value, str) and value.startswith("/")
        )
    for tree in registry:
        if tree.path and (tree.path / "target").is_symlink():
            pins.append(
                ((tree.path / "target").resolve(), f"target alias from {tree.path}")
            )
    return {
        root: [
            reason
            for target, reason in pins
            if target == root.resolve() or target.is_relative_to(root.resolve())
        ]
        for root in roots
    }


def clean_native(config, project, selected=None) -> dict[str, Any]:
    removed, kept, retained = [], [], []
    with project_locked(config, project.project_id):
        registry = worktrunk.worktrunk_list(project.root)
        tasks = pueue.tasks()
        owners = _owners(config, project, tasks, selected)
        # An explicit path is the author's completion claim for a registered
        # checkout that needed only foreground checks. Known job state wins.
        if selected is not None:
            for tree in registry:
                if tree.path in selected and not tree.main:
                    owners.setdefault(tree.path, {"terminal": True, "heads": set()})
        if not owners:
            return {
                "removed": [],
                "kept": [
                    {"branch": str(path), "reason": "no native invocation ownership"}
                    for path in selected or ()
                    if path.exists()
                ],
                "artifacts": [],
            }
        published = Published(project)
        candidates = []
        registered = {tree.path: tree for tree in registry if tree.path}
        for path, owner in owners.items():
            tree = registered.get(path)
            name = (tree.branch if tree else None) or str(path)
            reason = None
            if path.is_symlink():
                kept.append({"branch": name, "reason": "checkout path is a symlink"})
                continue
            if tree and tree.main:
                continue
            if tree and (tree.locked or (tree.branch or "").startswith("pre-rewrite")):
                reason = "explicitly locked or pre-rewrite checkout"
            elif not owner["terminal"]:
                reason = "native job is active or its terminal evidence is unavailable"
            elif not path.exists():
                try:
                    cache = _external_cache(path)
                    if cache:
                        kept.append(
                            {
                                "branch": name,
                                "reason": f"checkout absent; inspect exact compiler cache {cache} before retirement",
                            }
                        )
                except (OSError, CleanupError) as error:
                    kept.append({"branch": name, "reason": str(error)})
                continue
            elif tree:
                head = _git(path, "rev-parse", "HEAD")
                if not published.contains(head):
                    reason = "publication not proved"
                else:
                    candidates.append((path, tree, head))
            elif (path / ".git").exists() or not owner["heads"]:
                reason = "unregistered checkout needs inspection"
            elif any(
                entry.name not in {"target", ".agentctl"} for entry in path.iterdir()
            ):
                reason = "unregistered directory contains other bytes"
            else:
                heads = sorted(owner["heads"])
                head = next((head for head in heads if published.contains(head)), None)
                if head and _cache(path, registered=False):
                    candidates.append((path, None, head))
                else:
                    reason = "build remnant has no publication/cache proof"
            if reason:
                kept.append({"branch": name, "reason": reason})
        external = {}
        qualified = []
        for path, tree, head in candidates:
            try:
                external[path] = _external_cache(path)
            except (OSError, CleanupError) as error:
                kept.append({"branch": str(path), "reason": str(error)})
                continue
            qualified.append((path, tree, head))
        candidates = qualified

        def census():
            roots = [path for path, _, _ in candidates] + [
                cache for cache in external.values() if cache
            ]
            observed = worktree_processes.users(roots) if roots else {}
            aliases = _target_users(config, registry, roots)
            for root in roots:
                observed[root].extend(aliases[root])
            for path, _, _ in candidates:
                if external[path]:
                    observed[path].extend(observed[external[path]])
            return observed

        try:
            users = census()
            prepared = {}
            ready = []
            for path, tree, head in candidates:
                if users[path]:
                    kept.append(
                        {
                            "branch": str(path),
                            "reason": "active user: " + users[path][0],
                        }
                    )
                    continue
                try:
                    prepared[path] = _preserve_artifacts(
                        config, project, None, path, artifacts=retained
                    )
                except (OSError, CleanupError) as error:
                    kept.append({"branch": str(path), "reason": str(error)})
                    continue
                ready.append((path, tree, head))
            candidates = ready
            registry = worktrunk.worktrunk_list(project.root)
            # Preservation can take time. Refresh all process and native-job
            # holders once after it, before admitting this deletion batch.
            users = census()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            kept.extend(
                {"branch": str(path), "reason": f"holder census unavailable: {error}"}
                for path, _, _ in candidates
            )
            return {"removed": removed, "kept": kept, "artifacts": retained}
        for path, tree, head in candidates:
            name = (tree.branch if tree else None) or str(path)
            current = next((item for item in registry if item.path == path), None)
            if tree and (
                current is None or current.locked or current.branch != tree.branch
            ):
                kept.append(
                    {
                        "branch": name,
                        "reason": "worktree registration or lock changed during cleanup",
                    }
                )
                continue
            if users[path]:
                kept.append(
                    {"branch": name, "reason": "active user: " + users[path][0]}
                )
                continue
            cache = _cache(path, registered=tree is not None)
            if tree:
                reason = _drop_branch(
                    config,
                    project,
                    tree.branch or "",
                    base=published.base,
                    recorded_path=path,
                    artifacts=retained,
                    delete_branch=bool(tree.branch),
                    registry=registry,
                    process_users=lambda p: users.get(p, []),
                    disposable=tuple(
                        output for output in (cache, external[path]) if output
                    )
                    + _ignored_caches(path),
                    preserved_artifacts=prepared[path],
                    expected_head=head,
                )
                if reason:
                    kept.append({"branch": name, "reason": reason})
                    continue
            else:
                # A removed checkout may leave only its tagged build cache.
                # Every other byte must already have explicit artifact custody.
                copied = prepared[path]
                if cache is None:
                    kept.append(
                        {"branch": name, "reason": "build cache changed before removal"}
                    )
                    continue
                state = path / ".agentctl"
                files = [state, *state.rglob("*")] if state.exists() else []
                if any(
                    entry.name not in {"target", ".agentctl"}
                    for entry in path.iterdir()
                ):
                    kept.append(
                        {
                            "branch": name,
                            "reason": "build remnant changed before removal",
                        }
                    )
                    continue
                if any(
                    p.is_symlink()
                    or (
                        not p.is_dir()
                        and (
                            str(p) not in copied
                            or _digest(p) != _digest(Path(copied[str(p)]))
                        )
                    )
                    for p in files
                ):
                    kept.append(
                        {"branch": name, "reason": "unpreserved build-remnant evidence"}
                    )
                    continue
                _recovery_ref(project.root, None, path, head)
                if external[path]:
                    if _external_cache(path) != external[path]:
                        kept.append(
                            {
                                "branch": name,
                                "reason": "compiler cache changed before removal",
                            }
                        )
                        continue
                    _remove_cache(external[path])
                    external[path].parent.rmdir()
                _remove_cache(cache)
                shutil.rmtree(path)
            removed.append(name)
            print(f"retired {path}", file=sys.stderr, flush=True)
    return {"removed": removed, "kept": kept, "artifacts": retained}
