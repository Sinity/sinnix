"""Landing a batch: integrate, verify, review, publish, accept."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import gitcmd, github, launch, prompts, pueue, results, worktrunk
from .agents import (
    LANDING_AGENT_GROUP,
    PUSH_TIMEOUT_SECONDS,
    WORKTREE_STATE_DIR,
    binding,
    other_worktrees,
    queue_agent,
    queue_landing,
    workspace_of,
    worktree_path,
    write_prompt,
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
    landing_locked,
    list_runs,
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
# GitHub may briefly serve the branch head from before a successful push.
PR_PROPAGATION_TIMEOUT_SECONDS = 30
# A required check that GitHub has not reported at all within this window is
# `check_missing`: no runner will pick it up.
CHECK_MISSING_SECONDS = 600
POLL_INTERVAL_SECONDS = 15
# Git emits seven marker characters by default, but ``git merge-file`` also
# supports a larger marker size.  Labels on the opening, base (diff3), and
# closing markers are separated by whitespace; the separator is important so
# a source line such as ``===================== =====`` cannot match the
# opening seven equals.  The middle marker has no label and therefore gets
# its own branch that only permits trailing whitespace.
CONFLICT_MARKER = (
    r"^(<{7,}|>{7,}|\|{7,})([[:space:]].*)?$"
    r"|^={7,}[[:space:]]*$"
)
# How many times the default branch may move under a run before landing
# stops with `target_moved_twice`.
MAX_REFRESHES = 1


def _git(path: Path, *arguments: str, timeout: float = CALL_TIMEOUT_SECONDS) -> str:
    return gitcmd.git(path, *arguments, timeout=timeout, error=BatchError)


def _refuse_unless_live(run: Run) -> None:
    if run.acceptance is not None:
        raise BatchRefusal("already_accepted", f"run {run.run_id} has landed")
    if run.abandoned is not None:
        raise BatchRefusal("abandoned", f"run {run.run_id} was abandoned")


def _refuse_unless_workers_done(run: Run) -> None:
    _refuse_unless_live(run)
    tasks = pueue.tasks() if run.harness == "queued" else {}
    for worker in run.workers:
        if run.harness == "queued":
            task_id = worker.get("task_id")
            task = launch.find_task(tasks, task_id, worker.get("task_reference"))
            if task is None:
                raise BatchRefusal(
                    "worker_not_done", f"worker {worker['id']} has no task"
                )
            # The result document is the evidence; how the task ended after
            # writing it (cancelled, timed out, killed) is not.
            if not task.terminal and not worker.get("result"):
                raise BatchRefusal(
                    "worker_not_done",
                    f"worker {worker['id']} task {task_id} is {task.status.lower()}",
                )
        if not worker.get("result"):
            raise BatchRefusal(
                "worker_result_missing", f"worker {worker['id']} filed no valid result"
            )


def _worker_results(run: Run) -> list[dict[str, Any]]:
    return [dict(worker["result"]) for worker in run.workers if worker.get("result")]


# A result filed on the run's base commit carries no branch to integrate: the
# worker either proved its beads already hold (`verified`) or found nothing to
# do (`no_op`). Its evidence still reaches the reviewer and acceptance.
NO_CANDIDATE_KINDS = frozenset({"verified", "no_op"})


def _landable(run: Run) -> list[dict[str, Any]]:
    """The workers whose branch carries a commit for the candidate."""
    return [
        worker
        for worker in run.workers
        if (worker.get("result") or {}).get("kind") not in NO_CANDIDATE_KINDS
    ]


def _agent_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _handoff(path: Path, name: str, records: Sequence[Mapping[str, Any]]) -> str:
    """Bound inline context; keep exact evidence beside the prompt for inspection."""
    source = write_prompt(path, name, _agent_json(records))
    return _agent_json(
        [
            {
                **prompts.landing_record_view(record),
                "source": str(source),
                "index": index,
            }
            for index, record in enumerate(records)
        ]
    )


def _results_for_agents(run: Run, path: Path) -> str:
    return _handoff(path, "worker-results.json", _worker_results(run))


def _members_for_agents(run: Run, beads: Beads, path: Path) -> str:
    return _handoff(path, "members.json", prompts.landing_members(run.workers, beads))


def _review_agent(project: ProjectAdapter, run: Run) -> dict[str, str]:
    """Backend, model and effort of the reviewer and integrator: the
    descriptor's `[packets.review]`, else the leader worker's."""
    declared = project.packets.review
    if declared:
        return dict(declared)
    worker = run.workers[0]
    return {
        "backend": str(worker.get("backend") or ""),
        "model": str(worker.get("model") or ""),
        "effort": str(worker.get("effort") or ""),
    }


def _landing_inputs(
    config: Config, project: ProjectAdapter, run: Run, base: str, beads: Beads
) -> str:
    """Bind reuse to declared inputs, including the evidence the reviewer sees."""
    workers = []
    for worker in run.workers:
        head = _git(
            project.root, "rev-parse", "--verify", f"{worker['branch']}^{{commit}}"
        )
        if head != worker["result"]["candidate_sha"]:
            filed = worker["result"]["candidate_sha"]
            try:
                _git(project.root, "merge-base", "--is-ancestor", filed, head)
            except BatchError as error:
                raise BatchRefusal(
                    "candidate_mismatch",
                    f"worker {worker['id']} branch moved to {head[:12]}, which does not descend from its filed {filed[:12]}",
                ) from error
            worker_id = worker["id"]

            def rebind(
                document: dict[str, Any],
                *,
                worker_id: str = worker_id,
                head: str = head,
            ) -> None:
                for entry in document["workers"]:
                    if entry["id"] == worker_id and entry.get("result"):
                        entry["result"]["candidate_sha"] = head
                        # The branch carries a commit the result was filed
                        # without, so it is no longer a result with nothing
                        # to integrate.
                        entry["result"].pop("kind", None)

            run = update(config, run.run_id, rebind)
            worker = run.worker(worker_id)
        workers.append(
            {"branch": worker["branch"], "head": head, "result": worker["result"]}
        )
    try:
        runner = config.agent_runner.read_bytes()
    except OSError as error:
        raise BatchRefusal(
            "runner", f"cannot read {config.agent_runner}: {error}"
        ) from error
    contract = {
        "base": base,
        "workers": workers,
        "members": prompts.landing_members(run.workers, beads),
        "descriptor": project.digest,
        "verify_profile": run.verify_profile,
        "review_agent": _review_agent(project, run),
        "templates": {
            name: prompts.landing_template(name) for name in ("integrate", "review")
        },
        "schemas": results.SCHEMAS,
        "runner": hashlib.sha256(runner).hexdigest(),
    }
    return hashlib.sha256(_agent_json(contract).encode()).hexdigest()


def _integrate(
    config: Config, project: ProjectAdapter, run: Run, base: str, beads: Beads
) -> str:
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
        dirty = _dirty_paths(path)
        if dirty:
            land_update(config, run.run_id, integration_worktree=str(path))
            raise BatchRefusal(
                "integration_dirty",
                f"integration worktree {path} has uncommitted changes: "
                + ", ".join(dirty),
            )
        recorded = run.landing.get("candidate_sha")
        if recorded and _git(path, "rev-parse", "HEAD") != recorded:
            raise BatchRefusal(
                "integration_incomplete",
                f"{path} has a different HEAD; inspect it and use --keep-integration to preserve a manual fix",
            )
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
    run = land_update(
        config, run.run_id, integration_worktree=str(path), refreshed_base=base
    )
    branches = [worker["branch"] for worker in _landable(run)]
    for position, worker_branch in enumerate(branches):
        try:
            _git(path, "merge", "--no-ff", "--no-edit", worker_branch)
            continue
        except BatchError:
            conflicts = _git(path, "diff", "--name-only", "--diff-filter=U")
        prompt = prompts.landing_template("integrate").format(
            run_id=run.run_id,
            base=base,
            branch=worker_branch,
            conflicts="\n".join(f"- {name}" for name in conflicts.splitlines())
            or "- (see git status)",
            remaining="\n".join(f"- {name}" for name in branches[position + 1 :])
            or "- (none)",
            members=_members_for_agents(run, beads, path),
            results=_results_for_agents(run, path),
        )
        job = queue_agent(
            config,
            project,
            label=f"{project.project_id}:integrate:{run.run_id}",
            worktree=path,
            prompt=prompt,
            prompt_name="integrate.md",
            group=LANDING_AGENT_GROUP,
            **_review_agent(project, run),
            binding=binding(run, None),
            inaccessible=other_worktrees(project, run, None),
        )
        waited = launch.wait(
            job["job_id"],
            timeout_seconds=MAX_AGENT_TIMEOUT_SECONDS,
            reference=job.get("reference"),
        )
        if waited.get("phase") != "succeeded":
            raise BatchRefusal(
                "integration_failed",
                f"integration task {waited['job_id']} {waited.get('phase')}",
            )
        _refuse_unless_integrated(path, branches, who="integration agent")
        break
    candidate = _git(path, "rev-parse", "HEAD")
    _refuse_conflict_markers(path, base, candidate)
    return candidate


def _dirty_paths(path: Path) -> list[str]:
    return [
        line
        for line in _git(path, "status", "--porcelain=v1").splitlines()
        if not (line.startswith("??") and line[3:].startswith(f"{WORKTREE_STATE_DIR}/"))
    ]


def _refuse_unless_integrated(path: Path, branches: Sequence[str], *, who: str) -> None:
    if _dirty_paths(path):
        raise BatchRefusal("integration_dirty", f"{who} left an unclean tree")
    for name in branches:
        try:
            _git(path, "merge-base", "--is-ancestor", name, "HEAD")
        except BatchError as error:
            raise BatchRefusal(
                "integration_incomplete", f"{name} is not merged"
            ) from error


def _refuse_conflict_markers(path: Path, base: str, candidate: str) -> None:
    """Refuse a candidate whose changed files carry a conflict marker line."""
    changed = _git(path, "diff", "--name-only", f"{base}..{candidate}").splitlines()
    if not changed:
        return
    hits = gitcmd.git(
        path,
        "grep",
        "-nE",
        CONFLICT_MARKER,
        candidate,
        "--",
        *changed,
        ok_statuses=(0, 1),
        error=BatchError,
    )
    if hits:
        lines = hits.splitlines()
        raise BatchRefusal(
            "integration_conflict_markers",
            "conflict markers in " + "; ".join(lines[:6]),
            markers=lines,
        )


def _kept_integration(config: Config, run: Run, base: str) -> str:
    """The integration worktree's HEAD, checked as an integration would be."""
    worktree = run.landing.get("integration_worktree")
    if not worktree or not Path(worktree).is_dir():
        raise BatchRefusal(
            "integration_worktree_missing",
            f"run {run.run_id} has no integration worktree to keep",
        )
    path = Path(worktree)
    _refuse_unless_integrated(
        path, [worker["branch"] for worker in _landable(run)], who="the kept worktree"
    )
    candidate = _git(path, "rev-parse", "HEAD")
    try:
        _git(path, "merge-base", "--is-ancestor", base, candidate)
    except BatchError as error:
        raise BatchRefusal(
            "candidate_off_base",
            f"kept head {candidate[:12]} does not descend from {base[:12]}",
        ) from error
    _refuse_conflict_markers(path, base, candidate)
    return candidate


def _wait_seconds(sleep: Callable[[float], None], deadline: float) -> bool:
    if time.monotonic() >= deadline:
        return False
    sleep(POLL_INTERVAL_SECONDS)
    return True


def _pr_text(run: Run, beads: Beads) -> tuple[str, str]:
    """The PR title (the leader bead's subject) and body (titles, criteria)."""
    leader = run.workers[0]["id"]
    try:
        title = prompts.bead_subject(beads.show(leader))
    except PromptError:
        title = f"chore: batch {run.run_id}"
    criteria = {
        entry["id"]: [
            f"- [{'x' if item.get('status') in {'satisfied', 'superseded'} else ' '}] "
            f"{str(item.get('text') or '')[: prompts.RESULT_TEXT_CHARS]}"
            for item in entry.get("criteria") or ()
        ]
        for result in _worker_results(run)
        for entry in result.get("beads") or ()
    }
    lines = [f"Batch `{run.run_id}` on base `{run.base_commit[:12]}`.", ""]
    for bead_id in run.beads:
        try:
            bead_title = str(beads.show(bead_id).get("title") or "")
        except PromptError:
            bead_title = ""
        lines.append(f"**{bead_id}** {bead_title}".rstrip())
        lines.extend(criteria.get(bead_id, []))
        lines.append("")
    return title, "\n".join(lines).rstrip() + "\n"


def _await_candidate_head(
    project: ProjectAdapter,
    number: int,
    candidate: str,
    prior_head: str | None,
    sleep: Callable[[float], None],
    *,
    first_pull: Mapping[str, Any] | None = None,
) -> None:
    """Wait only for the pushed candidate to become visible through the PR API.

    ``prior_head`` is the exact remote head used by the push lease.  It is the
    only non-candidate head that can be a read-after-write result; any other
    head is an immediate refusal.  Once the candidate is observed this helper
    returns and every later publication read is candidate-bound again.
    """
    started = time.monotonic()
    deadline = started + PR_PROPAGATION_TIMEOUT_SECONDS
    pull = first_pull
    while True:
        if pull is None:
            pull = github.pull_request(project.root, number) or {}
        head = pull.get("headRefOid")
        if head == candidate:
            return
        if head != prior_head:
            raise BatchRefusal(
                "head_moved",
                f"PR #{number} head is neither the leased {str(prior_head)[:12]} "
                f"nor candidate {candidate[:12]}: {str(head)[:12]}",
            )
        if not _wait_seconds(sleep, deadline):
            raise BatchRefusal(
                "checks_failed",
                f"PR #{number} candidate {candidate[:12]} was not observable "
                "after the push",
                timed_out=True,
            )
        pull = None


def _merged(project: ProjectAdapter, run: Run, candidate: str) -> dict[str, Any] | None:
    """The stored PR as a publication when it is merged on exactly ``candidate``."""
    number = run.landing.get("pr_number")
    if not isinstance(number, int):
        return None
    pull = github.pull_request(project.root, number) or {}
    merged = github.merge_commit(pull)
    if merged is None or pull.get("headRefOid") != candidate:
        return None
    return {
        "policy": "pr",
        "pr": number,
        "candidate_sha": candidate,
        "merge_commit": merged,
    }


def _merged_earlier(project: ProjectAdapter, run: Run) -> dict[str, Any] | None:
    """A landing that merged its PR and stopped before accepting: its publication."""
    candidate = run.landing.get("candidate_sha")
    if workspace_of(project).publish != "pr" or not isinstance(candidate, str):
        return None
    return _merged(project, run, candidate)


def _ensure_pr(
    project: ProjectAdapter,
    run: Run,
    path: Path,
    candidate: str,
    beads: Beads,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    workspace = workspace_of(project)
    branch = run.landing["integration_branch"]
    prior_head = github.remote_head(path, branch)
    try:
        github.push_branch(
            path,
            branch,
            sha=candidate,
            lease=prior_head,
            timeout=PUSH_TIMEOUT_SECONDS,
        )
    except GithubError as error:
        # A lease race is a branch movement.  Do not retry it or overwrite the
        # head; all other push failures retain their original error semantics.
        message = str(error).lower()
        if "stale info" in message or "fetch first" in message:
            raise BatchRefusal(
                "head_moved", f"PR branch moved before pushing {candidate[:12]}"
            ) from error
        raise
    number = run.landing.get("pr_number")
    pull = (
        github.pull_request(project.root, number) if isinstance(number, int) else None
    )
    if pull is None or pull.get("state") != "OPEN":
        pull = github.pull_request_for_branch(project.root, branch)
    if pull is None:
        title, body = _pr_text(run, beads)
        number = github.create_pull_request(
            project.root,
            head=branch,
            base=workspace.base_branch,
            title=title,
            body=body,
        )
        _await_candidate_head(project, number, candidate, prior_head, sleep)
        return number
    number = int(pull["number"])
    _await_candidate_head(
        project, number, candidate, prior_head, sleep, first_pull=pull
    )
    return number


def _refuse_missing_checks(
    pull: Mapping[str, Any], required: Sequence[str], since: float, number: int
) -> None:
    """A required check GitHub never reported within the window is `check_missing`."""
    missing = [
        name for name in required if github.hosted_check_state(pull, name) == "missing"
    ]
    if missing and time.monotonic() - since >= CHECK_MISSING_SECONDS:
        raise BatchRefusal(
            "check_missing",
            f"PR #{number} never reported required check(s) {', '.join(missing)}",
            checks=missing,
        )


def _required_checks(project: ProjectAdapter, run: Run) -> tuple[str, ...]:
    """The checks a landing waits for: the one the descriptor declares as its
    candidate verification, and nothing else. Branch protection is GitHub's to
    enforce at the merge; a context it lists that no workflow reports is not
    this landing's evidence and must not stop it."""
    profile = run.verify_profile or workspace_of(project).verify.get("candidate") or ""
    return (profile.removeprefix("hosted:"),) if profile.startswith("hosted:") else ()


def _job_duration_seconds(job: Mapping[str, Any]) -> int | None:
    """Return a task's observed wall duration when its timestamps are usable."""
    started = job.get("started_at") or job.get("enqueued_at")
    ended = job.get("ended_at")
    if not isinstance(started, str) or not isinstance(ended, str):
        return None
    try:
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(ended.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((finish - start).total_seconds()))


def _verification_failure_detail(
    profile: str, job: Mapping[str, Any], timeout_seconds: float
) -> str:
    """Describe the observed terminal outcome, never the stale wait phase."""
    phase = str(job.get("phase") or "vanished")
    # A wait that consumed the operation budget can return the pre-terminal
    # queue view.  That is a timeout observation, not evidence that verification
    # is still running; a later queue read above may replace it with the wrapper
    # outcome (timeout, failed, cancelled, or vanished).
    if job.get("wait_timed_out") and not job.get("terminal"):
        phase = "timeout"
    exit_code = job.get("exit_code")
    duration = _job_duration_seconds(job)
    if phase == "timeout" and duration is None:
        duration = int(timeout_seconds)
    detail = f"{profile} task {job.get('job_id')} {phase}"
    facts: list[str] = []
    if exit_code is not None:
        facts.append(f"exit {exit_code}")
    facts.append(
        f"duration {duration}s" if duration is not None else "duration unknown"
    )
    if phase == "timeout":
        facts.append(f"budget {timeout_seconds:g}s")
    return f"{detail} ({', '.join(facts)})"


def _worktree_attestation(path: Path) -> dict[str, Any]:
    """Observe the checkout around a local verification without guessing.

    A successful command is useful only as evidence for the exact, clean
    candidate that the command ran against.  Git observation can itself fail
    (for example while a worktree is being removed); record that absence rather
    than turning it into a clean attestation.
    """
    try:
        return {
            "head": _git(path, "rev-parse", "HEAD"),
            "dirty": bool(_git(path, "status", "--porcelain")),
        }
    except BatchError:
        return {"head": None, "dirty": None}


def _hosted_check_attestation(
    pull: Mapping[str, Any], check: str, candidate: str
) -> dict[str, Any]:
    """Return only check-run facts GitHub explicitly associated with a SHA.

    The PR head and a merge are not substitutes for a check run's tested
    commit.  Different GitHub API versions use different spellings, so retain
    the complete rollup separately and recognize the common explicit SHA and
    URL/id fields here.
    """
    for entry in pull.get("statusCheckRollup") or ():
        if not isinstance(entry, Mapping):
            continue
        if entry.get("name", entry.get("context")) != check:
            continue
        observed = entry.get("headSha") or entry.get("head_sha")
        commit = entry.get("commit")
        if observed is None and isinstance(commit, Mapping):
            observed = commit.get("oid") or commit.get("sha")
        if observed != candidate:
            continue
        attestation: dict[str, Any] = {"tested_sha": candidate}
        for key in (
            "detailsUrl",
            "details_url",
            "targetUrl",
            "target_url",
            "url",
            "databaseId",
            "database_id",
            "id",
        ):
            value = entry.get(key)
            if value is not None:
                attestation["reference"] = str(value)
                break
        return attestation
    return {}


def _verify(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    path: Path,
    candidate: str,
    sleep: Callable[[float], None],
    beads: Beads,
) -> tuple[Run, dict[str, Any]]:
    profile = run.verify_profile or workspace_of(project).verify.get("candidate")
    if not profile:
        raise BatchRefusal(
            "no_candidate_profile",
            f"{project.project_id} declares no [workspace].verify.candidate",
        )
    if profile.startswith("hosted:"):
        check = profile.removeprefix("hosted:")
        number = _ensure_pr(project, run, path, candidate, beads, sleep)
        run = land_update(config, run.run_id, pr_number=number)
        started = time.monotonic()
        deadline = started + HOSTED_CHECK_TIMEOUT_SECONDS
        while True:
            pull = github.pull_request(project.root, number) or {}
            if pull.get("headRefOid") != candidate:
                raise BatchRefusal(
                    "head_moved", f"PR #{number} head is no longer {candidate[:12]}"
                )
            merged = github.merge_commit(pull)
            if merged is not None:
                # A merge is publication evidence, not a check-run receipt.
                # Keep that distinction so downstream acceptance never treats
                # branch protection or a merge as proof that this check ran.
                return run, {
                    "kind": "merged",
                    "check": check,
                    "pr": number,
                    "candidate_sha": candidate,
                    "requested_sha": candidate,
                    "phase": "unknown",
                    "status": "unknown",
                    "merge_commit": merged,
                    "recorded_at": now(),
                }
            _refuse_missing_checks(pull, (check,), started, number)
            state = github.hosted_check_state(pull, check)
            if state == "success":
                checks = [
                    entry
                    for entry in pull.get("statusCheckRollup") or ()
                    if isinstance(entry, Mapping)
                    and entry.get("name", entry.get("context")) == check
                ]
                receipt = {
                    "kind": "hosted",
                    "check": check,
                    "pr": number,
                    "candidate_sha": candidate,
                    "requested_sha": candidate,
                    "phase": "succeeded",
                    "status": "passed",
                    "checks": checks,
                    "recorded_at": now(),
                }
                receipt.update(_hosted_check_attestation(pull, check, candidate))
                return run, receipt
            if state == "failure":
                raise BatchRefusal(
                    "verify_failed", f"hosted check {check} failed on PR #{number}"
                )
            if not _wait_seconds(sleep, deadline):
                raise BatchRefusal(
                    "verify_failed",
                    f"hosted check {check} did not finish",
                    timed_out=True,
                )
    operation = project.operation(profile)
    before = _worktree_attestation(path)
    started = launch.start_operation(config, project, operation, workspace=path)
    job_id = started.get("job_id")
    if not isinstance(job_id, int):
        raise JobError(f"verification {profile} returned no task id")
    waited = launch.wait(
        job_id,
        timeout_seconds=operation.timeout_seconds,
        reference=started.get("reference"),
    )
    # `launch.wait` can return the last non-terminal view at the exact instant
    # the wrapper's descriptor timeout expires.  Reconcile against pueue's
    # current record before deciding, so a terminal timeout is reported as such
    # instead of being mislabelled `running`.
    try:
        task = launch.find_task(
            pueue.tasks(), waited.get("job_id", job_id), started.get("reference")
        )
    except PueueError:
        task = None
    if task is not None and (
        task.terminal or waited.get("phase") in {"running", "queued", "stashed"}
    ):
        waited = {**waited, **launch.job_view(task)}
    if waited.get("phase") != "succeeded":
        raise BatchRefusal(
            "verify_failed",
            _verification_failure_detail(profile, waited, operation.timeout_seconds),
            timed_out=waited.get("phase") == "timeout"
            or waited.get("wait_timed_out") is True,
        )
    after = _worktree_attestation(path)
    clean_candidate = (
        before["head"] == candidate
        and after["head"] == candidate
        and before["dirty"] is False
        and after["dirty"] is False
    )
    receipt = {
        "kind": "operation",
        "operation": profile,
        "job_id": waited["job_id"],
        "candidate_sha": candidate,
        "requested_sha": candidate,
        "phase": "succeeded",
        "status": "passed",
        "reference": started.get("reference"),
        "receipt": f"agentctl://jobs/{waited['job_id']}",
        "command": list(operation.command),
        "head_before": before["head"],
        "head_after": after["head"],
        "git_dirty": False
        if clean_candidate
        else (True if before["dirty"] is True or after["dirty"] is True else None),
        "recorded_at": now(),
    }
    if clean_candidate:
        receipt["tested_sha"] = candidate
    task = launch.find_task(pueue.tasks(), waited["job_id"], started.get("reference"))
    if task is not None:
        for key, suffix in (("log_path", ".log"), ("result_path", ".result")):
            artifact = launch._artifact(config, task, suffix)
            if artifact is not None and (suffix == ".log" or artifact.is_file()):
                receipt[key] = str(artifact)
    return run, receipt


def _review_by_policy(
    run: Run, verify_run: Mapping[str, Any], candidate: str
) -> dict[str, Any]:
    """The `review = "none"` policy: the candidate verification stands as the
    review record. The verdict says so, so acceptance never reads as reviewed."""
    return {
        "verdict": "pass",
        "policy": "none",
        "candidate_sha": candidate,
        "verification": dict(verify_run),
        "summary": "review policy none: landed on candidate verification alone",
    }


def _review(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    path: Path,
    base: str,
    candidate: str,
    beads: Beads,
) -> dict[str, Any]:
    prompt = prompts.landing_template("review").format(
        candidate=candidate,
        base=base,
        members=_members_for_agents(run, beads, path),
        results=_results_for_agents(run, path),
        verification=_handoff(
            path, "candidate-verification.json", [run.landing.get("verify_run") or {}]
        ),
    )
    job = queue_agent(
        config,
        project,
        label=f"{project.project_id}:review:{run.run_id}",
        worktree=path,
        prompt=prompt,
        prompt_name="review.md",
        group=LANDING_AGENT_GROUP,
        **_review_agent(project, run),
        schema="judge",
        binding=binding(run, None),
        inaccessible=other_worktrees(project, run, None),
    )
    waited = launch.wait(
        job["job_id"],
        timeout_seconds=MAX_AGENT_TIMEOUT_SECONDS,
        reference=job.get("reference"),
    )
    if waited.get("phase") != "succeeded":
        raise BatchRefusal(
            "review_failed", f"review task {waited['job_id']} {waited.get('phase')}"
        )
    verdict, errors = results.load_result(
        path / WORKTREE_STATE_DIR / "review.result.json", kind="judge"
    )
    if errors:
        raise BatchRefusal("review_invalid", "; ".join(errors[:6]))
    record = {
        **verdict,
        "candidate_sha": candidate,
        "job_id": waited["job_id"],
        "reference": job.get("reference"),
    }
    land_update(config, run.run_id, review_verdict=record)
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
    beads: Beads,
) -> dict[str, Any] | None:
    """Publish the candidate; None means the target moved and a refresh is due."""
    workspace = workspace_of(project)
    if workspace.publish == "pr":
        merged = _merged(project, run, candidate)
        if merged is not None:
            return {**merged, "base_commit": base}
    # A squash-merged PR absorbs a moved base; only a conflicting PR refreshes.
    elif _remote_base(project) != base:
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
    number = _ensure_pr(project, run, path, candidate, beads, sleep)
    run = land_update(config, run.run_id, pr_number=number)
    required = _required_checks(project, run)
    started = time.monotonic()
    deadline = started + HOSTED_CHECK_TIMEOUT_SECONDS
    while True:
        pull = github.pull_request(project.root, number) or {}
        if pull.get("headRefOid") != candidate:
            raise BatchRefusal(
                "head_moved", f"PR #{number} head is no longer {candidate[:12]}"
            )
        if github.merge_commit(pull):
            break
        if pull.get("mergeable") == "CONFLICTING":
            return None
        _refuse_missing_checks(pull, required, started, number)
        state = github.check_rollup(pull, required)
        if state == "ready":
            break
        if state == "failed":
            raise BatchRefusal(
                "checks_failed", f"PR #{number} has a failing required check"
            )
        if not _wait_seconds(sleep, deadline):
            raise BatchRefusal(
                "checks_failed", f"PR #{number} checks did not finish", timed_out=True
            )
    # Checks can become ready after the earlier observation.  Bind the merge
    # request to a fresh PR read immediately before consuming that readiness.
    pull = github.pull_request(project.root, number) or {}
    if pull.get("headRefOid") != candidate:
        raise BatchRefusal(
            "head_moved", f"PR #{number} head is no longer {candidate[:12]}"
        )
    if not github.merge_commit(pull):
        try:
            github.merge_pr(project.root, number, candidate)
        except github.MergeBlocked:
            # Branch protection gates on a check this landing does not wait
            # for; GitHub merges the head once that check reports.
            github.arm_auto_merge(project.root, number, candidate)
            pull = _await_auto_merge(project, number, candidate, sleep, deadline)
        except GithubError as error:
            if "no longer" in str(error):
                raise BatchRefusal("head_moved", str(error)) from error
            raise
        else:
            pull = github.pull_request(project.root, number) or {}
    merged = github.merge_commit(pull)
    if merged is None or pull.get("headRefOid") != candidate:
        raise BatchRefusal(
            "head_moved", f"PR #{number} did not merge on {candidate[:12]}"
        )
    published = {
        "policy": "pr",
        "pr": number,
        "candidate_sha": candidate,
        "base_commit": base,
        "merge_commit": merged,
    }
    try:
        github.delete_remote_branch(project.root, run.landing["integration_branch"])
    except GithubError as error:
        published["remote_branch"] = f"kept: {error}"
    return published


def _await_auto_merge(
    project: ProjectAdapter,
    number: int,
    candidate: str,
    sleep: Callable[[float], None],
    deadline: float,
) -> Mapping[str, Any]:
    """The PR once GitHub's auto-merge has landed ``candidate``."""
    while True:
        pull = github.pull_request(project.root, number) or {}
        if pull.get("headRefOid") != candidate:
            raise BatchRefusal(
                "head_moved", f"PR #{number} head is no longer {candidate[:12]}"
            )
        if github.merge_commit(pull):
            return pull
        if github.check_rollup(pull) == "failed":
            raise BatchRefusal(
                "checks_failed", f"PR #{number} has a failing required check"
            )
        if not _wait_seconds(sleep, deadline):
            raise BatchRefusal(
                "checks_failed",
                f"PR #{number} auto-merge did not complete",
                timed_out=True,
            )


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
    # What reached the default branch: the squash-merge commit under the PR
    # policy, the candidate itself under the master policy.
    landed = str(published.get("merge_commit") or candidate)
    for bead_id in run.beads:
        if verdicts.get(bead_id):
            try:
                beads.close(
                    bead_id, reason=f"batch {run.run_id} {landed}", actor=run.actor
                )
                beads_state[bead_id] = {
                    "state": "closed",
                    "evidence": f"batch {run.run_id} {landed}",
                }
            except BatchError as error:
                beads_state[bead_id] = {
                    "state": "open",
                    "evidence": f"close failed: {error}",
                }
        else:
            residual = (
                f"batch {run.run_id} landed {landed} without satisfying every criterion"
                if bead_id in verdicts
                else f"batch {run.run_id} landed {landed}; no worker result covered this bead"
            )
            try:
                beads.comment(bead_id, residual, actor=run.actor)
            except BatchError as error:
                residual += f" (comment failed: {error})"
            # The batch is over; a claim it leaves behind only hides the bead
            # from the next dispatch.
            try:
                beads.unclaim(bead_id, actor=run.actor)
            except BatchError as error:
                residual += f" (unclaim failed: {error})"
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
    residual = _drop_worktrees(config, project, run, published=candidate)
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


def queue(config: Config, project: ProjectAdapter, run_id: str) -> dict[str, Any]:
    """Queue a fresh landing task for a run whose landing is not already running.

    `batch start` queues the first landing behind the workers; this re-queues
    one after a landing failed, so a caller that cannot hold a process for the
    whole landing still drives it through pueue.
    """
    run = load(config, run_id)
    if run.project != project.project_id:
        raise BatchRefusal("project", f"run {run_id} belongs to {run.project}")
    _refuse_unless_live(run)
    task_id = run.landing.get("task_id")
    current = launch.find_task(
        pueue.tasks(), task_id, run.landing.get("task_reference")
    )
    if current is not None and not current.terminal:
        raise BatchRefusal(
            "landing_in_progress",
            f"landing task {task_id} is {current.status.lower()}",
        )
    queued = queue_landing(config, project, run, after=(), stashed=False)
    queued_task = pueue.task(queued)
    return {
        **land_update(
            config,
            run_id,
            task_id=queued,
            task_reference=launch.launch_reference(queued_task)
            if queued_task is not None
            else None,
            failure=None,
        ).to_dict(),
        "landing_task_id": queued,
    }


def land(
    config: Config,
    project: ProjectAdapter,
    run_id: str,
    *,
    beads: Beads | None = None,
    sleep: Callable[[float], None] = time.sleep,
    keep_integration: bool = False,
) -> dict[str, Any]:
    """Integrate, verify, review, publish, accept. Refuses until every worker is done.

    With ``keep_integration`` the integration worktree's current HEAD is the
    candidate: nothing is re-merged, so a hand fix there lands.
    """
    run = load(config, run_id)
    if run.project != project.project_id:
        raise BatchRefusal("project", f"run {run_id} belongs to {run.project}")
    beads = beads or SubprocessBeads(project.root)
    with landing_locked(config, run_id):
        return _land_locked(
            config, project, run, beads, sleep=sleep, keep_integration=keep_integration
        )


def _land_locked(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    beads: Beads,
    *,
    sleep: Callable[[float], None],
    keep_integration: bool,
) -> dict[str, Any]:
    run_id = run.run_id
    try:
        _refuse_unless_workers_done(run)
        base = str(run.landing.get("refreshed_base") or run.base_commit)
        if not _landable(run):
            # No worker committed anything, so there is no candidate to
            # integrate, verify or publish. Acceptance closes the beads whose
            # criteria the evidence satisfies and leaves the rest open.
            kind = (
                "verified"
                if all(
                    (worker.get("result") or {}).get("kind") == "verified"
                    for worker in run.workers
                )
                else "no_op"
            )
            run = _accept(
                config,
                project,
                run,
                beads,
                candidate=base,
                verify_run={"kind": kind, "candidate_sha": base},
                review_verdict={
                    "verdict": "pass",
                    "policy": kind,
                    "candidate_sha": base,
                },
                published={
                    "kind": kind,
                    "candidate_sha": base,
                    "base_commit": base,
                    "merge_commit": None,
                },
            )
            return run.to_dict()
        merged = _merged_earlier(project, run)
        if merged is not None:
            run = _accept(
                config,
                project,
                run,
                beads,
                candidate=str(run.landing["candidate_sha"]),
                verify_run=run.landing.get("verify_run") or {},
                review_verdict=run.landing.get("review_verdict") or {},
                published={**merged, "base_commit": base},
            )
            return run.to_dict()
        if not keep_integration:
            base = _remote_base(project)
        while True:
            inputs = _landing_inputs(config, project, run, base, beads)
            # A worker branch may have been rebound to its head above.
            run = load(config, run_id)
            reuse = inputs == run.landing.get("inputs_digest")
            candidate = (
                _kept_integration(config, run, base)
                if keep_integration or reuse
                else _integrate(config, project, run, base, beads)
            )
            if reuse and candidate != run.landing.get("candidate_sha"):
                if not keep_integration:
                    raise BatchRefusal(
                        "integration_incomplete",
                        "integration HEAD changed; inspect it and use --keep-integration to preserve a manual fix",
                    )
                reuse = False
            if candidate == base:
                raise BatchRefusal(
                    "empty_candidate",
                    f"integration produced no change on {base[:12]}",
                )
            run = land_update(
                config,
                run_id,
                candidate_sha=candidate,
                inputs_digest=inputs,
                verify_run=run.landing.get("verify_run") if reuse else None,
                review_verdict=run.landing.get("review_verdict") if reuse else None,
                failure=None,
            )
            path = Path(run.landing["integration_worktree"])
            verify_run = run.landing.get("verify_run") or {}
            if (
                verify_run.get("candidate_sha") != candidate
                or verify_run.get("phase") != "succeeded"
            ):
                run, verify_run = _verify(
                    config, project, run, path, candidate, sleep, beads
                )
            run = land_update(config, run_id, verify_run=verify_run)
            review_verdict = run.landing.get("review_verdict") or {}
            if (
                review_verdict.get("candidate_sha") != candidate
                or review_verdict.get("verdict") != "pass"
            ):
                review_verdict = (
                    _review_by_policy(run, verify_run, candidate)
                    if project.workspace.review == "none"
                    else _review(config, project, run, path, base, candidate, beads)
                )
            run = land_update(config, run_id, review_verdict=review_verdict)
            published = _publish(
                config, project, run, path, base, candidate, sleep, beads
            )
            if published is not None:
                break
            if keep_integration:
                raise BatchRefusal(
                    "publish_rejected",
                    f"{workspace_of(project).base_branch} moved past {base[:12]}; "
                    "a kept integration head is not refreshed",
                )
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
            "abandoned",
            "already_accepted",
            "worker_not_done",
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


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _process_users(path: Path) -> list[str]:
    """Current-directory users outside pueue's authority."""
    users: list[str] = []
    proc = Path("/proc")
    try:
        entries = tuple(proc.iterdir())
    except OSError as error:
        raise BatchError(f"cannot inspect process users: {error}") from error
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            cwd = Path(os.readlink(entry / "cwd"))
        except FileNotFoundError:
            continue
        except PermissionError:
            try:
                owner = entry.stat().st_uid
            except OSError as stat_error:
                if stat_error.errno in {errno.ENOENT, errno.ESRCH}:
                    continue
                raise BatchError(
                    f"cannot inspect process {entry.name} ownership: {stat_error}"
                ) from stat_error
            if owner != os.getuid():
                continue
            cwd = _stable_privileged_cwd(entry)
            if cwd is None:
                continue
        except OSError as error:
            if error.errno in {errno.ENOENT, errno.ESRCH}:
                continue
            raise BatchError(
                f"cannot inspect process {entry.name} cwd: {error}"
            ) from error
        if _under(cwd, path):
            users.append(f"pid {entry.name} cwd {cwd}")
    return users


def _process_starttime(entry: Path) -> str | None:
    try:
        payload = (entry / "stat").read_text()
        return payload.rsplit(")", 1)[1].split()[19]
    except OSError as error:
        if error.errno in {errno.ENOENT, errno.ESRCH}:
            return None
        raise BatchError(f"cannot identify process {entry.name}: {error}") from error
    except IndexError as error:
        raise BatchError(f"cannot identify process {entry.name}: {error}") from error


def _privileged_cwd(entry: Path) -> Path:
    try:
        completed = subprocess.run(
            ["sudo", "-n", "readlink", str(entry / "cwd")],
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BatchError(f"cannot inspect process {entry.name} cwd: {error}") from error
    if completed.returncode != 0 or not completed.stdout.strip():
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise BatchError(f"cannot inspect process {entry.name} cwd: {detail}")
    return Path(completed.stdout.strip())


def _stable_privileged_cwd(entry: Path) -> Path | None:
    start = _process_starttime(entry)
    if start is None:
        return None
    try:
        cwd = _privileged_cwd(entry)
    except BatchError:
        if _process_starttime(entry) is None:
            return None
        raise
    end = _process_starttime(entry)
    if end is None:
        return None
    if end != start:
        raise BatchError(f"process {entry.name} changed during cwd probe")
    return cwd


def _task_users(path: Path) -> list[str]:
    try:
        tasks = pueue.tasks().values()
    except PueueError as error:
        raise BatchError(f"cannot inspect pueue users: {error}") from error
    users = []
    for task in tasks:
        if task.terminal:
            continue
        try:
            task_path = Path(task.path)
        except TypeError:
            continue
        if task_path.is_absolute() and _under(task_path, path):
            users.append(f"task {task.task_id} {task.status.lower()} cwd {task_path}")
    return users


def _artifact_paths(path: Path, patterns: Sequence[str]) -> list[Path]:
    found: dict[Path, Path] = {}
    root = path.resolve()
    for pattern in patterns:
        for candidate in path.glob(pattern):
            if candidate.is_symlink():
                raise BatchError(f"artifact path escapes checkout: {candidate}")
            if candidate.is_dir():
                continue
            if not _under(candidate, root):
                raise BatchError(f"artifact path escapes checkout: {candidate}")
            try:
                mode = candidate.stat().st_mode
            except OSError as error:
                raise BatchError(
                    f"cannot read artifact {candidate}: {error}"
                ) from error
            if not stat.S_ISREG(mode):
                raise BatchError(f"artifact is not a regular file: {candidate}")
            found[candidate.relative_to(path)] = candidate
    return [found[key] for key in sorted(found)]


def _artifact_destination(
    config: Config, run_id: str, worktree: Path, relative: Path, digest: str
) -> Path:
    token = hashlib.sha256(str(worktree).encode()).hexdigest()[:16]
    return (
        config.state_dir
        / "artifacts"
        / run_id
        / token
        / relative.parent
        / f"{relative.name}.{digest[:16]}"
    )


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preserve_artifacts(
    config: Config,
    project: ProjectAdapter,
    run_id: str | None,
    path: Path,
    *,
    artifacts: list[dict[str, str]],
) -> dict[str, str]:
    patterns = (f"{WORKTREE_STATE_DIR}/**/*", *workspace_of(project).retain_artifacts)
    replacements: dict[str, str] = {}
    for source in _artifact_paths(path, patterns):
        relative = source.relative_to(path)
        before = _digest(source)
        destination = _artifact_destination(
            config, run_id or "orphan", path, relative, before
        )
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(destination.parent, 0o700)
        if destination.exists():
            if _digest(destination) != before:
                raise BatchError(f"artifact destination differs: {destination}")
        else:
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            shutil.copyfile(source, temporary)
            if _digest(temporary) != before:
                temporary.unlink(missing_ok=True)
                raise BatchError(f"artifact verification failed: {destination}")
            os.replace(temporary, destination)
        replacements[str(source)] = str(destination)
        artifacts.append({"source": str(source), "destination": str(destination)})
    return replacements


def _replace_paths(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_replace_paths(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_paths(item, replacements) for key, item in value.items()}
    return value


def _recovery_ref(root: Path, run_id: str | None, path: Path, head: str) -> str:
    token = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    ref = f"refs/agentctl/recovery/{run_id or 'orphan'}/{token}/{head}"
    existing = gitcmd.git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        f"{ref}^{{commit}}",
        ok_statuses=(0, 1),
        error=BatchError,
    )
    if existing and existing != head:
        raise BatchError(f"recovery ref differs: {ref}")
    if not existing:
        _git(root, "update-ref", ref, head)
    verified = _git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if verified != head:
        raise BatchError(f"recovery ref did not retain {head}: {ref}")
    return ref


def _drop_branch(
    config: Config,
    project: ProjectAdapter,
    branch: str,
    *,
    base: str,
    recorded_path: Path | None = None,
    run_id: str | None = None,
    artifacts: list[dict[str, str]] | None = None,
) -> str | None:
    """Release one terminal checkout while retaining its Git history.

    Returns why it was kept, or None once it is gone.
    """
    registry = worktrunk.worktrunk_list(project.root)
    tree = worktrunk.worktrunk_find(project.root, branch)
    path = tree.path if tree is not None else None
    removal_target = branch
    detached = False
    if recorded_path is not None:
        detached_tree = next(
            (
                item
                for item in registry
                if not item.main and item.branch is None and item.path == recorded_path
            ),
            None,
        )
        if detached_tree is not None:
            path = detached_tree.path
            removal_target = str(path)
            detached = True
    if path is None:
        if recorded_path is not None and recorded_path.exists():
            return f"worktree kept; checkout path is unregistered: {recorded_path}"
        return None
    if not path.is_dir():
        if removal_target == branch:
            return "worktree kept; checkout path is unavailable"
    else:
        try:
            dirty = _dirty_paths(path)
            users = [*_task_users(path), *_process_users(path)]
        except BatchError as error:
            return f"worktree kept; {error}"
        if dirty:
            return "worktree kept; uncommitted changes"
        if users:
            return f"worktree kept; active user: {users[0]}"
        try:
            head = _git(path, "rev-parse", "HEAD")
            branch_head = gitcmd.git(
                project.root,
                "rev-parse",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}^{{commit}}",
                ok_statuses=(0, 1),
                error=BatchError,
            )
            if detached:
                _recovery_ref(project.root, run_id, path, head)
            elif branch_head != head:
                return "worktree kept; branch no longer names checkout HEAD"
            copied = _preserve_artifacts(
                config,
                project,
                run_id,
                path,
                artifacts=artifacts if artifacts is not None else [],
            )
            if copied and run_id is not None:

                def retain(document: dict[str, Any]) -> None:
                    replacements = dict(copied)
                    for artifact in document.get("artifacts", []):
                        source = artifact.get("source")
                        destination = artifact.get("destination")
                        if source in copied and isinstance(destination, str):
                            replacements[destination] = copied[source]
                    history = list(document.get("artifacts", []))
                    updated = _replace_paths(
                        {
                            key: value
                            for key, value in document.items()
                            if key != "artifacts"
                        },
                        replacements,
                    )
                    document.clear()
                    document.update(updated)
                    document["artifacts"] = [
                        *history,
                        *(
                            {"source": source, "destination": destination}
                            for source, destination in copied.items()
                        ),
                    ]

                update(config, run_id, retain)
            if _dirty_paths(path):
                return "worktree kept; uncommitted changes"
            if detached and _git(path, "rev-parse", "HEAD") != head:
                return "worktree kept; detached checkout HEAD changed"
            if not detached:
                branch_head = gitcmd.git(
                    project.root,
                    "rev-parse",
                    "--verify",
                    "--quiet",
                    f"refs/heads/{branch}^{{commit}}",
                    ok_statuses=(0, 1),
                    error=BatchError,
                )
                if branch_head != _git(path, "rev-parse", "HEAD"):
                    return "worktree kept; branch no longer names checkout HEAD"
            users = [*_task_users(path), *_process_users(path)]
            if users:
                return f"worktree kept; active user: {users[0]}"
        except (BatchError, OSError) as error:
            return f"worktree kept; {error}"
    try:
        worktrunk.worktrunk_remove(
            project.root, removal_target, keep_branch=True, reap=False
        )
    except WorktrunkError as error:
        return str(error)
    if path.exists():
        return f"worktree kept; checkout path remains after removal: {path}"
    return None


def _drop_worktrees(
    config: Config, project: ProjectAdapter, run: Run, *, published: str | None = None
) -> list[str]:
    """Drop the run's worker and integration worktrees; name the ones kept.

    ``published`` is the candidate a landing published. The integration
    worktree is measured against it rather than against the run's base: its
    commits are out, so only uncommitted changes in it are still work.
    """
    branches = [
        (
            worker["branch"],
            run.base_commit,
            Path(worker["worktree"]) if worker.get("worktree") else None,
        )
        for worker in run.workers
    ]
    branches.append(
        (
            run.landing["integration_branch"],
            published or run.base_commit,
            (
                Path(run.landing["integration_worktree"])
                if run.landing.get("integration_worktree")
                else None
            ),
        )
    )
    residual: list[str] = []
    with project_locked(config, project.project_id):
        for branch, base, recorded_path in branches:
            kept = _drop_branch(
                config,
                project,
                branch,
                base=base,
                recorded_path=recorded_path,
                run_id=run.run_id,
            )
            if kept:
                residual.append(f"{branch}: {kept}")
    return residual


def abandon(
    config: Config,
    project: ProjectAdapter,
    run_id: str,
    *,
    reason: str = "",
    beads: Beads | None = None,
) -> dict[str, Any]:
    """Release a run: unclaim its members, remove the worktrees that hold no
    unpreserved work, mark the manifest abandoned."""
    run = load(config, run_id)
    if run.project != project.project_id:
        raise BatchRefusal("project", f"run {run_id} belongs to {run.project}")
    _refuse_unless_live(run)
    beads = beads or SubprocessBeads(project.root)
    landing_id = run.landing.get("task_id")
    landing_task = launch.find_task(
        pueue.tasks(), landing_id, run.landing.get("task_reference")
    )
    if landing_task is not None and landing_task.status == "Running":
        raise BatchRefusal(
            "landing_in_progress", f"landing task {landing_id} is running"
        )
    with landing_locked(config, run_id):
        residual: list[str] = []
        for worker in run.workers:
            task_id = worker.get("task_id")
            task = launch.find_task(
                pueue.tasks(), task_id, worker.get("task_reference")
            )
            if task is not None and not task.terminal:
                launch.cancel(config, task.task_id)
        if landing_task is not None and not landing_task.terminal:
            launch.cancel(config, landing_task.task_id)
        for bead_id in run.beads:
            try:
                beads.unclaim(bead_id, actor=run.actor)
            except BatchError as error:
                residual.append(f"{bead_id}: unclaim failed: {error}")
        residual.extend(_drop_worktrees(config, project, run))
        record = {"reason": reason, "at": now(), "residual": residual}

        def mark(document: dict[str, Any]) -> None:
            document["abandoned"] = record

        return update(config, run_id, mark).to_dict()


# A batch's own worktree branches: `batch/<run id>/<worker id or integration>`.
_BATCH_BRANCH = re.compile(r"^batch/(?P<run>[^/]+)/[^/]+$")


def clean(config: Config, project: ProjectAdapter) -> dict[str, Any]:
    """Remove the worktrees of runs that are over. Run state, never age.

    A worktree is a candidate only when its branch names a batch run of this
    project that no longer holds its beads: landed, abandoned, or with no
    manifest left at all. It is removed only when nothing would be lost with
    it, and one that is kept is named with the reason.
    """
    runs = {
        run.run_id: run for run in list_runs(config, project.project_id, strict=True)
    }
    try:
        default_base = _git(
            project.root,
            "rev-parse",
            "--verify",
            f"{workspace_of(project).default_base}^{{commit}}",
        )
    except (BatchError, BatchRefusal):
        # Without a base every commit is judged by the refs that hold it,
        # which is the check that decides preservation anyway.
        default_base = ""
    removed: list[str] = []
    absent: list[str] = []
    kept: list[dict[str, str]] = []
    retained_artifacts: list[dict[str, str]] = []
    with project_locked(config, project.project_id):
        targets: list[tuple[str, Run | None, Path | None]] = []
        for owner in runs.values():
            if owner.live:
                continue
            targets.extend(
                (worker["branch"], owner, Path(worker["worktree"]))
                for worker in owner.workers
                if worker.get("worktree")
            )
            integration = owner.landing.get("integration_worktree")
            if integration:
                targets.append(
                    (owner.landing["integration_branch"], owner, Path(integration))
                )
        for tree in worktrunk.worktrunk_list(project.root):
            match = _BATCH_BRANCH.match(tree.branch or "")
            if tree.main or match is None:
                continue
            owner = runs.get(match.group("run"))
            if owner is not None:
                continue
            if owner is None and not match.group("run").startswith(
                f"{project.project_id}-"
            ):
                continue
            targets.append((str(tree.branch), owner, None))
        seen: set[tuple[str, Path | None]] = set()
        for branch, owner, recorded_path in targets:
            key = (branch, recorded_path)
            if key in seen:
                continue
            seen.add(key)
            registered = worktrunk.worktrunk_find(project.root, branch)
            if recorded_path is not None:
                registered = registered or next(
                    (
                        tree
                        for tree in worktrunk.worktrunk_list(project.root)
                        if not tree.main
                        and tree.branch is None
                        and tree.path == recorded_path
                    ),
                    None,
                )
            if registered is None or registered.path is None:
                if recorded_path is None or not recorded_path.exists():
                    absent.append(branch)
                    continue
            copied: list[dict[str, str]] = []
            reason = _drop_branch(
                config,
                project,
                branch,
                base=owner.base_commit if owner else default_base,
                recorded_path=recorded_path,
                run_id=owner.run_id if owner else None,
                artifacts=copied,
            )
            if reason:
                kept.append({"branch": branch, "reason": reason})
            else:
                removed.append(branch)
            retained_artifacts.extend(copied)
    return {
        "project": project.project_id,
        "removed": removed,
        "absent": absent,
        "kept": kept,
        "artifacts": retained_artifacts,
    }
