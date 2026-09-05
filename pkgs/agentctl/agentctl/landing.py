"""Landing a batch: integrate, verify, review, publish, accept."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from . import gitcmd, github, launch, prompts, pueue, results, worktrunk
from .agents import (
    PUSH_TIMEOUT_SECONDS,
    WORKTREE_STATE_DIR,
    binding,
    queue_agent,
    workspace_of,
    worktree_path,
)
from .beads import Beads, SubprocessBeads
from .config import Config
from .github import GithubError
from .launch import JobError
from .limits import CALL_TIMEOUT_SECONDS, MAX_AGENT_TIMEOUT_SECONDS
from .manifest import (
    BatchError,
    BatchRefusal,
    Run,
    land_update,
    load,
    now,
    project_locked,
    update,
)
from .projects import ProjectAdapter
from .prompts import PromptError
from .pueue import PueueError
from .worktrunk import WorktrunkError

HOSTED_CHECK_TIMEOUT_SECONDS = 2 * 3_600
POLL_INTERVAL_SECONDS = 15
# How many times the default branch may move under a run before landing
# stops with `target_moved_twice`.
MAX_REFRESHES = 1


def _git(path: Path, *arguments: str, timeout: float = CALL_TIMEOUT_SECONDS) -> str:
    return gitcmd.git(path, *arguments, timeout=timeout, error=BatchError)


def _refuse_unless_workers_done(run: Run) -> None:
    if run.acceptance is not None:
        raise BatchRefusal("already_accepted", f"run {run.run_id} has landed")
    tasks = pueue.tasks() if run.harness == "queued" else {}
    for worker in run.workers:
        if run.harness == "queued":
            task_id = worker.get("task_id")
            task = tasks.get(task_id) if isinstance(task_id, int) else None
            if task is None:
                raise BatchRefusal(
                    "worker_not_done", f"worker {worker['id']} has no task"
                )
            if not task.terminal:
                raise BatchRefusal(
                    "worker_not_done",
                    f"worker {worker['id']} task {task_id} is {task.status.lower()}",
                )
            if not task.succeeded:
                raise BatchRefusal(
                    "worker_failed",
                    f"worker {worker['id']} task {task_id} {task.result}",
                )
        if not worker.get("result"):
            raise BatchRefusal(
                "worker_result_missing", f"worker {worker['id']} filed no valid result"
            )


def _worker_results(run: Run) -> list[dict[str, Any]]:
    return [dict(worker["result"]) for worker in run.workers if worker.get("result")]


def _integrate(config: Config, project: ProjectAdapter, run: Run, base: str) -> str:
    """Merge every worker branch onto ``base`` in the integration worktree; return HEAD."""
    branch = run.landing["integration_branch"]
    existing = worktrunk.worktrunk_find(project.root, branch)
    if existing is not None and (existing.path is None or not existing.path.is_dir()):
        # The branch is registered but its directory is gone; `wt` refuses
        # to create a worktree for a branch it already lists.
        try:
            worktrunk.worktrunk_remove(project.root, branch, force=True)
        except WorktrunkError as error:
            raise BatchRefusal(
                "integration_worktree_missing",
                f"{branch} is registered without a worktree directory and "
                f"could not be unregistered: {error}",
            ) from error
        existing = None
    if existing is not None and existing.path is not None:
        path = existing.path
        try:
            _git(path, "merge", "--abort")
        except BatchError:
            pass
        _git(path, "reset", "--hard", base)
    else:
        created = worktrunk.worktrunk_create(
            project.root, branch, path=worktree_path(project, branch), base=base
        )
        if created.path is None:
            raise WorktrunkError(f"wt created {branch} without a path")
        path = created.path
    run = land_update(config, run.run_id, integration_worktree=str(path))
    branches = [worker["branch"] for worker in run.workers]
    for position, worker_branch in enumerate(branches):
        try:
            _git(path, "merge", "--no-ff", "--no-edit", worker_branch)
            continue
        except BatchError:
            conflicts = _git(path, "diff", "--name-only", "--diff-filter=U")
        worker = run.workers[0]
        prompt = prompts.landing_template("integrate").format(
            run_id=run.run_id,
            base=base,
            branch=worker_branch,
            conflicts="\n".join(f"- {name}" for name in conflicts.splitlines())
            or "- (see git status)",
            remaining="\n".join(f"- {name}" for name in branches[position + 1 :])
            or "- (none)",
            results=json.dumps(_worker_results(run), indent=2, sort_keys=True),
        )
        job = queue_agent(
            config,
            project,
            label=f"{project.project_id}:integrate:{run.run_id}",
            worktree=path,
            prompt=prompt,
            prompt_name="integrate.md",
            backend=str(worker.get("backend") or ""),
            model=str(worker.get("model") or ""),
            effort=str(worker.get("effort") or ""),
            binding=binding(run, None),
        )
        waited = launch.wait(job["job_id"], timeout_seconds=MAX_AGENT_TIMEOUT_SECONDS)
        if waited.get("phase") != "succeeded":
            raise BatchRefusal(
                "integration_failed",
                f"integration task {job['job_id']} {waited.get('phase')}",
            )
        dirty = [
            line
            for line in _git(path, "status", "--porcelain=v1").splitlines()
            if not (
                line.startswith("??") and line[3:].startswith(f"{WORKTREE_STATE_DIR}/")
            )
        ]
        if dirty:
            raise BatchRefusal(
                "integration_dirty", "integration agent left an unclean tree"
            )
        for name in branches:
            try:
                _git(path, "merge-base", "--is-ancestor", name, "HEAD")
            except BatchError as error:
                raise BatchRefusal(
                    "integration_incomplete", f"{name} is not merged"
                ) from error
        break
    return _git(path, "rev-parse", "HEAD")


def _wait_seconds(sleep: Callable[[float], None], deadline: float) -> bool:
    if time.monotonic() >= deadline:
        return False
    sleep(POLL_INTERVAL_SECONDS)
    return True


def _ensure_pr(project: ProjectAdapter, run: Run, path: Path, candidate: str) -> int:
    workspace = workspace_of(project)
    branch = run.landing["integration_branch"]
    github.push_branch(
        path,
        branch,
        sha=candidate,
        lease=github.remote_head(path, branch),
        timeout=PUSH_TIMEOUT_SECONDS,
    )
    number = run.landing.get("pr_number")
    pull = (
        github.pull_request(project.root, number) if isinstance(number, int) else None
    )
    if pull is None or pull.get("state") != "OPEN":
        pull = github.pull_request_for_branch(project.root, branch)
    if pull is None:
        titles = ", ".join(worker["id"] for worker in run.workers)
        return github.create_pull_request(
            project.root,
            head=branch,
            base=workspace.base_branch,
            title=f"batch {run.run_id}: {titles}"[:72],
            body=f"Batch `{run.run_id}` on base `{run.base_commit}`.\n\nMembers: "
            + ", ".join(run.beads)
            + "\n",
        )
    return int(pull["number"])


def _verify(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    path: Path,
    candidate: str,
    sleep: Callable[[float], None],
) -> tuple[Run, dict[str, Any]]:
    profile = run.verify_profile or workspace_of(project).verify.get("candidate")
    if not profile:
        raise BatchRefusal(
            "no_candidate_profile",
            f"{project.project_id} declares no [workspace].verify.candidate",
        )
    if profile.startswith("hosted:"):
        check = profile.removeprefix("hosted:")
        number = _ensure_pr(project, run, path, candidate)
        run = land_update(config, run.run_id, pr_number=number)
        deadline = time.monotonic() + HOSTED_CHECK_TIMEOUT_SECONDS
        while True:
            pull = github.pull_request(project.root, number) or {}
            if pull.get("headRefOid") == candidate:
                state = github.hosted_check_state(pull, check)
                if state == "success":
                    receipt = {
                        "kind": "hosted",
                        "check": check,
                        "pr": number,
                        "candidate_sha": candidate,
                        "phase": "succeeded",
                    }
                    return run, receipt
                if state == "failure":
                    raise BatchRefusal(
                        "verify_failed", f"hosted check {check} failed on PR #{number}"
                    )
            if not _wait_seconds(sleep, deadline):
                raise BatchRefusal(
                    "verify_timeout", f"hosted check {check} did not finish"
                )
    operation = project.operation(profile)
    started = launch.start_operation(config, project, operation, workspace=path)
    job_id = started.get("job_id")
    if not isinstance(job_id, int):
        raise JobError(f"verification {profile} returned no task id")
    waited = launch.wait(job_id, timeout_seconds=operation.timeout_seconds)
    if waited.get("phase") != "succeeded":
        raise BatchRefusal(
            "verify_failed", f"{profile} task {job_id} {waited.get('phase')}"
        )
    return run, {
        "kind": "operation",
        "operation": profile,
        "job_id": job_id,
        "candidate_sha": candidate,
        "phase": "succeeded",
    }


def _review(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    path: Path,
    base: str,
    candidate: str,
) -> dict[str, Any]:
    worker = run.workers[0]
    prompt = prompts.landing_template("review").format(
        candidate=candidate,
        base=base,
        results=json.dumps(_worker_results(run), indent=2, sort_keys=True),
    )
    job = queue_agent(
        config,
        project,
        label=f"{project.project_id}:review:{run.run_id}",
        worktree=path,
        prompt=prompt,
        prompt_name="review.md",
        backend=str(worker.get("backend") or ""),
        model=str(worker.get("model") or ""),
        effort=str(worker.get("effort") or ""),
        schema="judge",
        binding=binding(run, None),
    )
    waited = launch.wait(job["job_id"], timeout_seconds=MAX_AGENT_TIMEOUT_SECONDS)
    if waited.get("phase") != "succeeded":
        raise BatchRefusal(
            "review_failed", f"review task {job['job_id']} {waited.get('phase')}"
        )
    verdict, errors = results.load_result(
        path / WORKTREE_STATE_DIR / "review.result.json", kind="judge"
    )
    if errors:
        raise BatchRefusal("review_invalid", "; ".join(errors[:6]))
    record = {**verdict, "candidate_sha": candidate, "job_id": job["job_id"]}
    if verdict["verdict"] != "pass":
        raise BatchRefusal(
            "review_rejected",
            f"verdict {verdict['verdict']}: " + "; ".join(verdict["evidence"][:3]),
            verdict=record,
        )
    return record


def _remote_base(project: ProjectAdapter) -> str:
    branch = workspace_of(project).base_branch
    _git(
        project.root, "fetch", "--quiet", "origin", branch, timeout=PUSH_TIMEOUT_SECONDS
    )
    return _git(
        project.root,
        "rev-parse",
        "--verify",
        f"refs/remotes/origin/{branch}^{{commit}}",
    )


def _publish(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    path: Path,
    base: str,
    candidate: str,
    sleep: Callable[[float], None],
) -> dict[str, Any] | None:
    """Publish the candidate; None means the target moved and a refresh is due."""
    workspace = workspace_of(project)
    if _remote_base(project) != base:
        return None
    if workspace.publish == "master":
        try:
            _git(
                path,
                "push",
                f"--force-with-lease=refs/heads/{workspace.base_branch}:{base}",
                "origin",
                f"{candidate}:refs/heads/{workspace.base_branch}",
                timeout=PUSH_TIMEOUT_SECONDS,
            )
        except BatchError as error:
            message = str(error)
            # Only a lease that no longer matches means the target moved;
            # a protected branch or a hook rejects the same push forever.
            if "stale info" in message or "fetch first" in message:
                return None
            if "rejected" in message:
                raise BatchRefusal("publish_rejected", message) from error
            raise
        return {"policy": "master", "candidate_sha": candidate, "base_commit": base}
    number = _ensure_pr(project, run, path, candidate)
    run = land_update(config, run.run_id, pr_number=number)
    required = github.required_checks(project.root, workspace.base_branch)
    deadline = time.monotonic() + HOSTED_CHECK_TIMEOUT_SECONDS
    while True:
        pull = github.pull_request(project.root, number) or {}
        if pull.get("headRefOid") != candidate:
            raise BatchRefusal(
                "head_moved", f"PR #{number} head is no longer {candidate[:12]}"
            )
        state = github.check_rollup(pull, required)
        if state == "ready":
            break
        if state == "failed":
            raise BatchRefusal(
                "checks_failed", f"PR #{number} has a failing required check"
            )
        if not _wait_seconds(sleep, deadline):
            raise BatchRefusal("checks_timeout", f"PR #{number} checks did not finish")
    try:
        github.merge_pr(project.root, number, candidate)
    except GithubError as error:
        if "no longer" in str(error):
            raise BatchRefusal("head_moved", str(error)) from error
        raise
    return {
        "policy": "pr",
        "pr": number,
        "candidate_sha": candidate,
        "base_commit": base,
    }


def _accept(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    beads: Beads,
    *,
    candidate: str,
    verify_run: Mapping[str, Any],
    review_verdict: Mapping[str, Any],
    published: Mapping[str, Any],
) -> Run:
    verdicts = results.satisfied_beads(_worker_results(run))
    beads_state: dict[str, dict[str, str]] = {}
    for bead_id in run.beads:
        if verdicts.get(bead_id):
            try:
                beads.close(
                    bead_id, reason=f"batch {run.run_id} {candidate}", actor=run.actor
                )
                beads_state[bead_id] = {
                    "state": "closed",
                    "evidence": f"batch {run.run_id} {candidate}",
                }
            except BatchError as error:
                beads_state[bead_id] = {
                    "state": "open",
                    "evidence": f"close failed: {error}",
                }
        else:
            residual = (
                f"batch {run.run_id} landed {candidate} without satisfying every criterion"
                if bead_id in verdicts
                else f"batch {run.run_id} landed {candidate}; no worker result covered this bead"
            )
            try:
                beads.comment(bead_id, residual, actor=run.actor)
            except BatchError as error:
                residual += f" (comment failed: {error})"
            beads_state[bead_id] = {"state": "open", "evidence": residual}
    acceptance = {
        "candidate_sha": candidate,
        "verify_run": dict(verify_run),
        "review_verdict": dict(review_verdict),
        "published": dict(published),
        "beads": beads_state,
        "advisory": _advisory(project, published),
        "recorded_at": now(),
        "residual": [],
    }

    def record(document: dict[str, Any]) -> None:
        document["acceptance"] = acceptance
        document["landing"]["failure"] = None

    run = update(config, run.run_id, record)
    residual: list[str] = []
    # A worker's worktree is removed only once every bead it carried is
    # closed; the integration worktree is published and always goes.
    removable = [run.landing["integration_branch"]]
    for worker in run.workers:
        still_open = [
            bead_id
            for bead_id in worker["beads"]
            if beads_state[bead_id]["state"] != "closed"
        ]
        if still_open:
            residual.append(
                f"{worker['branch']}: worktree kept; {', '.join(still_open)} still open"
            )
        else:
            removable.append(worker["branch"])
    with project_locked(config, project.project_id):
        for branch in removable:
            try:
                worktrunk.worktrunk_remove(project.root, branch, force=True)
            except WorktrunkError as error:
                residual.append(f"{branch}: {error}")
    if residual:

        def note(document: dict[str, Any]) -> None:
            document["acceptance"]["residual"] = residual

        run = update(config, run.run_id, note)
    return run


def _advisory(
    project: ProjectAdapter, published: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The hosted reviews and comments on the candidate PR. Never a gate."""
    number = published.get("pr")
    if published.get("policy") != "pr" or not isinstance(number, int):
        return []
    try:
        return github.pull_request_advisory(project.root, number)
    except GithubError:
        return []


def land(
    config: Config,
    project: ProjectAdapter,
    run_id: str,
    *,
    beads: Beads | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Integrate, verify, review, publish, accept. Refuses until every worker is done."""
    run = load(config, run_id)
    if run.project != project.project_id:
        raise BatchRefusal("project", f"run {run_id} belongs to {run.project}")
    beads = beads or SubprocessBeads(project.root)
    try:
        _refuse_unless_workers_done(run)
        base = str(run.landing.get("refreshed_base") or run.base_commit)
        while True:
            candidate = _integrate(config, project, run, base)
            if candidate == base:
                raise BatchRefusal(
                    "empty_candidate",
                    f"integration produced no change on {base[:12]}",
                )
            run = land_update(
                config,
                run_id,
                candidate_sha=candidate,
                verify_run=None,
                review_verdict=None,
                failure=None,
            )
            path = Path(run.landing["integration_worktree"])
            run, verify_run = _verify(config, project, run, path, candidate, sleep)
            run = land_update(config, run_id, verify_run=verify_run)
            review_verdict = _review(config, project, run, path, base, candidate)
            run = land_update(config, run_id, review_verdict=review_verdict)
            published = _publish(config, project, run, path, base, candidate, sleep)
            if published is not None:
                break
            if int(run.landing.get("refreshes") or 0) >= MAX_REFRESHES:
                raise BatchRefusal(
                    "target_moved_twice",
                    f"{workspace_of(project).base_branch} moved again during landing",
                )
            base = _remote_base(project)
            run = land_update(
                config,
                run_id,
                refreshes=int(run.landing.get("refreshes") or 0) + 1,
                refreshed_base=base,
                candidate_sha=None,
                verify_run=None,
                review_verdict=None,
            )
        run = _accept(
            config,
            project,
            run,
            beads,
            candidate=candidate,
            verify_run=verify_run,
            review_verdict=review_verdict,
            published=published,
        )
    except BatchRefusal as refusal:
        if refusal.code not in {
            "already_accepted",
            "worker_not_done",
            "worker_failed",
            "worker_result_missing",
        }:
            land_update(config, run_id, failure=refusal.to_dict())
        raise
    except (
        BatchError,
        PueueError,
        WorktrunkError,
        GithubError,
        JobError,
        PromptError,
    ) as error:
        land_update(config, run_id, failure={"code": "substrate", "detail": str(error)})
        raise
    return run.to_dict()
