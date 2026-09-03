"""Lanes: a worktree with an agent in it, ending in a PR that merges itself.

worktrunk creates and removes the worktree (the project's own `wt.toml` hooks
provision it), pueue runs the agent, GitHub reviews and merges the PR, Beads
holds the task. agentctl joins them: compile the prompt, queue the agent,
push the branch, open the PR, arm auto-merge, and close what merged.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import launch, worktrunk
from .config import Config
from .limits import MAX_AGENT_TIMEOUT_SECONDS
from .packets import (
    PacketConfig,
    PacketError,
    SubprocessBdReader,
    bead_subject,
    compile_launch_snapshot,
    rebase_prompt,
)
from .projects import ProjectAdapter
from .worktrunk import Worktree, WorktrunkError

LANE_OPERATION = "lane"
REBASE_OPERATION = "rebase"
AGENT_GROUP = "agent"
# The scope's slice: the job plane, where pueued's own tasks live, so an
# agent's memory counts against the plane's budget and not the desktop's.
AGENT_SLICE = "sinnixd-work.slice"
GH_TIMEOUT_SECONDS = 60
PUSH_TIMEOUT_SECONDS = 2_400  # the push runs the repository's pre-push gate


class LaneError(RuntimeError):
    """A lane step agentctl refuses; the external tools' own refusals carry through."""


def _run(
    argv: Sequence[str], *, cwd: Path, timeout: float = GH_TIMEOUT_SECONDS
) -> str:
    try:
        completed = subprocess.run(
            list(argv), cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as error:
        raise LaneError(f"{argv[0]} is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise LaneError(f"{' '.join(argv[:2])} timed out") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise LaneError(detail or f"{' '.join(argv[:2])} failed")
    return completed.stdout


def gh_json(arguments: Sequence[str], *, cwd: Path) -> Any:
    output = _run(["gh", *arguments], cwd=cwd)
    try:
        return json.loads(output) if output.strip() else None
    except json.JSONDecodeError as error:
        raise LaneError("gh did not print JSON") from error


def _git(path: Path, *arguments: str, timeout: float = GH_TIMEOUT_SECONDS) -> str:
    return _run(["git", "-C", str(path), *arguments], cwd=path, timeout=timeout).strip()


def _sanitize(branch: str) -> str:
    return branch.replace("/", "-")


def worktree_path(project: ProjectAdapter, branch: str) -> Path:
    """`<workspace.root>/<repo>-<branch>`, the placement `wt` is configured for."""
    if project.workspace is None:
        raise LaneError(f"project {project.project_id} declares no [workspace]")
    return project.workspace.root / f"{project.root.name}-{_sanitize(branch)}"


def _write_prompt(worktree: Path, name: str, prompt: str) -> Path:
    lane_dir = worktree / ".lane"
    lane_dir.mkdir(mode=0o700, exist_ok=True)
    path = lane_dir / name
    descriptor = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(prompt)
    return path


def _agent_argv(
    config: Config,
    project: ProjectAdapter,
    *,
    worktree: Path,
    prompt_path: Path,
    result_path: Path,
    backend: str,
    model: str,
    effort: str,
    memory_max: str,
) -> tuple[str, ...]:
    if not config.agent_runner.is_file() or not os.access(config.agent_runner, os.X_OK):
        raise LaneError(f"agent runner is unavailable: {config.agent_runner}")
    runner = (
        str(config.agent_runner),
        "--agent",
        backend,
        "--workdir",
        str(worktree),
        "--prompt-file",
        str(prompt_path),
        "--last-file",
        str(result_path),
        "--model",
        model,
        "--reasoning-effort",
        effort,
    )
    scope = (
        "systemd-run",
        "--user",
        "--scope",
        "--quiet",
        f"--slice={AGENT_SLICE}",
        "-p",
        f"MemoryMax={memory_max}",
        "--",
        *runner,
    )
    return project.environment.command_for(scope)


def queue_agent(
    config: Config,
    project: ProjectAdapter,
    *,
    operation: str,
    bead_id: str,
    worktree: Path,
    prompt: str,
    prompt_name: str,
    backend: str,
    model: str,
    effort: str,
    timeout_seconds: int = MAX_AGENT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if project.workspace is None:
        raise LaneError(f"project {project.project_id} declares no [workspace]")
    prompt_path = _write_prompt(worktree, prompt_name, prompt)
    result_path = worktree / ".lane" / f"{prompt_name.rsplit('.', 1)[0]}.result.md"
    label = f"{project.project_id}:{operation}:{bead_id}"
    environment = project.environment.values()
    # Task-authority writes from an agent must not default to the operator.
    environment.setdefault("BEADS_ACTOR", f"agent-{bead_id}")
    environment["SINNIXD_PROJECT_ID"] = project.project_id
    environment["SINNIXD_LANE_BEAD"] = bead_id
    return launch.enqueue(
        config,
        project=project,
        operation=operation,
        label=label,
        group=AGENT_GROUP,
        argv=_agent_argv(
            config,
            project,
            worktree=worktree,
            prompt_path=prompt_path,
            result_path=result_path,
            backend=backend,
            model=model,
            effort=effort,
            memory_max=project.workspace.agent_memory_max,
        ),
        working_directory=worktree,
        timeout_seconds=timeout_seconds,
        result_kind="last-message",
        environment=environment,
        kind="attested-agent",
    )


def lane_start(
    config: Config,
    project: ProjectAdapter,
    bead_id: str,
    *,
    backend: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    """Compile the prompt, create the worktree, queue the agent."""
    packets = PacketConfig.load(project.root)
    snapshot = compile_launch_snapshot(
        bead_id,
        project_id=project.project_id,
        reader=SubprocessBdReader(project.root),
        config=packets,
        backend=backend,
        model=model,
        effort=effort,
    )
    existing = worktrunk.worktrunk_find(project.root, snapshot.branch)
    if existing is not None and existing.path is not None:
        raise LaneError(
            f"{snapshot.branch} already has a worktree at {existing.path}; "
            f"use `agentctl lane rebase {project.project_id} {bead_id}` to continue it"
        )
    created = worktrunk.worktrunk_create(
        project.root,
        snapshot.branch,
        path=worktree_path(project, snapshot.branch),
        base=project.workspace.default_base if project.workspace else None,
    )
    if created.path is None:
        raise WorktrunkError(f"wt created {snapshot.branch} without a path")
    job = queue_agent(
        config,
        project,
        operation=LANE_OPERATION,
        bead_id=snapshot.leader_id,
        worktree=created.path,
        prompt=snapshot.prompt,
        prompt_name="prompt.md",
        backend=snapshot.dimensions.backend,
        model=snapshot.dimensions.model,
        effort=snapshot.dimensions.effort,
    )
    return {
        "bead": snapshot.leader_id,
        "beads": list(snapshot.bead_ids),
        "branch": snapshot.branch,
        "worktree": str(created.path),
        "backend": snapshot.dimensions.backend,
        "model": snapshot.dimensions.model,
        "effort": snapshot.dimensions.effort,
        "job": job,
    }


def _bead_from_branch(packets: PacketConfig, branch: str) -> str | None:
    prefix = packets.branch_prefix.rstrip("/") + "/"
    return branch[len(prefix) :] if branch.startswith(prefix) else None


def _project_root_of(worktree: Path) -> Path:
    common = Path(_git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    return common.parent.resolve()


def _open_pr(worktree: Path, branch: str) -> Mapping[str, Any] | None:
    try:
        value = gh_json(
            ["pr", "view", branch, "--json", "number,url,state,autoMergeRequest"],
            cwd=worktree,
        )
    except LaneError as error:
        if "no pull requests found" in str(error).lower():
            return None
        raise
    return value if isinstance(value, Mapping) else None


def lane_publish(
    config: Config,
    worktree: Path,
    *,
    bead_id: str | None = None,
    title: str | None = None,
    body_file: Path | None = None,
) -> dict[str, Any]:
    """Push the branch, open the PR under the bead's subject, arm auto-merge."""
    worktree = worktree.resolve()
    if not (worktree / ".git").exists():
        raise LaneError(f"{worktree} is not a Git worktree")
    dirty = _git(worktree, "status", "--porcelain=v1", "--untracked-files=normal")
    dirty_paths = [line[3:] for line in dirty.splitlines() if not line[3:].startswith(".lane/")]
    if dirty_paths:
        raise LaneError(
            "worktree has uncommitted changes that would not be in the PR: "
            + ", ".join(dirty_paths[:8])
        )
    branch = _git(worktree, "symbolic-ref", "--quiet", "--short", "HEAD")
    root = _project_root_of(worktree)
    from .projects import load_project_adapter

    project = load_project_adapter(root)
    packets = PacketConfig.load(root)
    bead_id = bead_id or _bead_from_branch(packets, branch)
    subject = title
    bead: Mapping[str, Any] | None = None
    if subject is None:
        if bead_id is None:
            raise LaneError(
                f"{branch} does not name a bead; pass --bead or --title"
            )
        bead = SubprocessBdReader(root).show(bead_id)
        subject = bead_subject(bead)
    body_path = body_file or (worktree / ".lane" / "body.md")
    if body_path.is_file():
        body = body_path.read_text()
    elif bead is not None:
        body = (
            f"Bead {bead_id}: {bead.get('title', '')}\n\n"
            f"{bead.get('description', '')}".strip()
            + "\n"
        )
    else:
        body = f"{subject}\n"
    base = (project.workspace.default_base if project.workspace else "origin/master")
    base_branch = base.split("/", 1)[1] if base.startswith("origin/") else base

    _git(worktree, "push", "--set-upstream", "origin", branch, timeout=PUSH_TIMEOUT_SECONDS)
    pull = _open_pr(worktree, branch)
    created = False
    if pull is None or pull.get("state") == "MERGED":
        _run(
            [
                "gh",
                "pr",
                "create",
                "--head",
                branch,
                "--base",
                base_branch,
                "--title",
                subject,
                "--body",
                body,
            ],
            cwd=worktree,
        )
        created = True
        pull = _open_pr(worktree, branch)
        if pull is None:
            raise LaneError("gh pr create returned but the PR is not visible")
    number = pull.get("number")
    if not isinstance(number, int):
        raise LaneError("gh pr view published no PR number")
    if not pull.get("autoMergeRequest"):
        _run(["gh", "pr", "merge", str(number), "--auto", "--squash"], cwd=worktree)
    return {
        "branch": branch,
        "bead": bead_id,
        "subject": subject,
        "pr": number,
        "url": pull.get("url"),
        "created": created,
        "auto_merge": True,
    }


def lane_rebase(
    config: Config,
    project: ProjectAdapter,
    bead_id: str,
    *,
    backend: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    """Queue an agent with the rebase prompt into the bead's existing worktree."""
    packets = PacketConfig.load(project.root)
    branch = packets.branch_for(bead_id)
    tree = worktrunk.worktrunk_find(project.root, branch)
    if tree is None or tree.path is None:
        raise LaneError(f"{branch} has no worktree; start the lane instead")
    bead = SubprocessBdReader(project.root).show(bead_id)
    base = project.workspace.default_base if project.workspace else "origin/master"
    prompt = rebase_prompt(
        config=packets, bead=bead, branch=branch, base=base, worktree=tree.path
    )
    job = queue_agent(
        config,
        project,
        operation=REBASE_OPERATION,
        bead_id=bead_id,
        worktree=tree.path,
        prompt=prompt,
        prompt_name="rebase-prompt.md",
        backend=backend or packets.default_backend,
        model=model or packets.default_model,
        effort=effort or packets.default_effort,
    )
    return {"bead": bead_id, "branch": branch, "worktree": str(tree.path), "job": job}


def pull_requests(root: Path, *, state: str = "all", limit: int = 300) -> dict[str, dict[str, Any]]:
    """Open and recent PRs of the repository at ``root``, keyed by head branch."""
    value = gh_json(
        [
            "pr",
            "list",
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            "number,url,title,headRefName,state,isDraft,mergeable,reviewDecision,"
            "autoMergeRequest,statusCheckRollup,updatedAt",
        ],
        cwd=root,
    )
    rows = value if isinstance(value, list) else []
    by_head: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        head = str(row.get("headRefName") or "")
        # The newest PR for a branch is the one that describes it.
        if head and (head not in by_head or row.get("state") == "OPEN"):
            by_head[head] = dict(row)
    return by_head


@dataclass(frozen=True)
class LaneRow:
    worktree: Worktree
    bead: str | None
    pr: Mapping[str, Any] | None


def lane_rows(project: ProjectAdapter, *, full: bool = False) -> list[LaneRow]:
    packets = PacketConfig.load(project.root)
    trees = worktrunk.worktrunk_list(project.root, full=full)
    prs = pull_requests(project.root)
    rows: list[LaneRow] = []
    for tree in trees:
        if tree.main or tree.branch is None:
            continue
        rows.append(
            LaneRow(
                worktree=tree,
                bead=_bead_from_branch(packets, tree.branch),
                pr=prs.get(tree.branch),
            )
        )
    return rows


def lane_sync(config: Config, project: ProjectAdapter, *, actor: str = "agentctl") -> dict[str, Any]:
    """Close beads and remove worktrees whose PR merged; report the rest."""
    closed: list[str] = []
    removed: list[str] = []
    remaining: list[dict[str, Any]] = []
    reader = SubprocessBdReader(project.root)
    for row in lane_rows(project):
        tree = row.worktree
        assert tree.branch is not None
        merged = tree.integrated or (row.pr is not None and row.pr.get("state") == "MERGED")
        if not merged:
            remaining.append(
                {
                    "branch": tree.branch,
                    "worktree": str(tree.path) if tree.path else None,
                    "bead": row.bead,
                    "state": tree.state,
                    "dirty": tree.dirty,
                    "pr": row.pr.get("number") if row.pr else None,
                    "pr_state": row.pr.get("state") if row.pr else None,
                }
            )
            continue
        if tree.dirty:
            remaining.append(
                {
                    "branch": tree.branch,
                    "worktree": str(tree.path) if tree.path else None,
                    "bead": row.bead,
                    "state": tree.state,
                    "dirty": True,
                    "pr": row.pr.get("number") if row.pr else None,
                    "pr_state": "MERGED",
                    "reason": "merged but the worktree has uncommitted changes",
                }
            )
            continue
        if row.bead is not None:
            try:
                bead = reader.show(row.bead)
            except PacketError:
                bead = None
            if bead is not None and bead.get("status") not in {"closed"}:
                pr_ref = f"PR #{row.pr['number']}" if row.pr else "branch integrated"
                _run(
                    ["bd", "close", row.bead, "--actor", actor, "--reason", f"merged ({pr_ref})"],
                    cwd=project.root,
                )
                closed.append(row.bead)
        worktrunk.worktrunk_remove(project.root, tree.branch)
        removed.append(tree.branch)
    return {"closed": closed, "removed": removed, "remaining": remaining}


def refill(
    config: Config,
    project: ProjectAdapter,
    *,
    limit: int,
    dry_run: bool = False,
    backend: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    """Start lanes for ready beads that have neither a worktree nor a PR."""
    packets = PacketConfig.load(project.root)
    reader = SubprocessBdReader(project.root)
    ready = reader.ready()
    taken = {tree.branch for tree in worktrunk.worktrunk_list(project.root) if tree.branch}
    taken.update(pull_requests(project.root, state="open"))
    candidates: list[str] = []
    for bead in ready:
        bead_id = bead.get("id")
        if not isinstance(bead_id, str) or not bead_id:
            continue
        if str(bead.get("issue_type") or "") == "epic":
            continue
        if packets.branch_for(bead_id) in taken:
            continue
        candidates.append(bead_id)
        if len(candidates) >= limit:
            break
    started: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    if not dry_run:
        for bead_id in candidates:
            try:
                started.append(
                    lane_start(
                        config, project, bead_id, backend=backend, model=model, effort=effort
                    )
                )
            except (LaneError, PacketError, WorktrunkError) as error:
                failed.append({"bead": bead_id, "error": str(error)})
    return {
        "ready": len(ready),
        "taken": len(taken),
        "candidates": candidates,
        "started": started,
        "failed": failed,
        "dry_run": dry_run,
    }
