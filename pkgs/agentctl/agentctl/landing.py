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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import gitcmd, github, launch, prompts, pueue, results, worktrunk
from .agents import (
    LANDING_AGENT_GROUP,
    WORKTREE_STATE_DIR,
    binding,
    other_worktrees,
    pending_task,
    queue_agent,
    requeue_landing,
    workspace_of,
    worktree_path,
    write_prompt,
)
from .beads import Beads, SubprocessBeads
from .checkout import PUSH_TIMEOUT_SECONDS
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
    landing_recovery_locked,
    list_runs,
    load,
    now,
    project_locked,
    transition_locked,
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
# The job wrapper enforces an operation's timeout from the moment the job
# starts; this margin lets it kill the command and record the outcome before
# the landing stops waiting for that terminal record.
VERIFY_EXIT_GRACE_SECONDS = 120
# Git emits seven marker characters by default, but ``git merge-file`` also
# supports a larger marker size.  Labels on the opening, base (diff3), and
# closing markers are separated by whitespace; the separator is important so
# a source line such as ``===================== =====`` cannot match the
# opening seven equals.  The middle marker has no label and therefore gets
# its own branch that only permits trailing whitespace.
CONFLICT_MARKER = r"^(<{7,}|>{7,}|\|{7,})([[:space:]].*)?$" r"|^={7,}[[:space:]]*$"
# How many times the default branch may move under a run before landing
# stops with `target_moved_twice`.
MAX_REFRESHES = 1


def _git(
    path: Path,
    *arguments: str,
    timeout: float = CALL_TIMEOUT_SECONDS,
    owned: bool = False,
    main_checkout: bool = False,
) -> str:
    return gitcmd.git(
        path,
        *arguments,
        timeout=timeout,
        error=BatchError,
        owned=owned,
        main_checkout=main_checkout,
    )


def _refuse_unless_live(run: Run) -> None:
    if run.acceptance is not None:
        raise BatchRefusal("already_accepted", f"run {run.run_id} has landed")
    if run.abandoned is not None:
        raise BatchRefusal("abandoned", f"run {run.run_id} was abandoned")


def _refuse_unless_workers_done(run: Run) -> None:
    _refuse_unless_live(run)
    tasks = pueue.tasks() if run.harness == "queued" else {}
    for worker in run.workers:
        # The result document is the evidence; how the task ended after
        # writing it (cancelled, timed out, killed, or lost with the queue's
        # own state) is not.
        if worker.get("result"):
            continue
        if run.harness == "queued":
            task_id = worker.get("task_id")
            task = launch.find_task(tasks, task_id, worker.get("task_reference"))
            if task is None:
                raise BatchRefusal(
                    "worker_not_done",
                    (
                        f"worker {worker['id']} has no task"
                        if task_id is None
                        else f"worker {worker['id']} task {task_id} is gone from pueue "
                        "and filed no result"
                    ),
                )
            if not task.terminal:
                raise BatchRefusal(
                    "worker_not_done",
                    f"worker {worker['id']} task {task_id} is {task.status.lower()}",
                )
        raise BatchRefusal(
            "worker_result_missing", f"worker {worker['id']} filed no valid result"
        )


def _worker_results(run: Run) -> list[dict[str, Any]]:
    return [dict(worker["result"]) for worker in run.workers if worker.get("result")]


class ClosureRefusal(BatchError):
    """A typed reason a bead stays open after its batch landed.

    ``reason`` separates the three things closure depends on: the executed
    evidence (``no_binding``, ``unsatisfied``), the semantic task contract
    (``acceptance_changed``, ``contract_changed``) and the owner row at close
    time (``unobservable``, ``claim_moved``, ``revision_unusable``).  A row
    revision that only moved for notes, status or claims is none of these: it
    is re-read and becomes the close precondition.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _dispatch_binding(
    worker: Mapping[str, Any], bead_id: str
) -> Mapping[str, Any] | None:
    for row in worker.get("evidence_binding") or ():
        if isinstance(row, Mapping) and row.get("id") == bead_id:
            return row
    return None


def _contract_drift(
    binding: Mapping[str, Any], current: Mapping[str, Any]
) -> ClosureRefusal | None:
    """The semantic contract comparison; the row revision is deliberately absent."""
    if any(
        current.get(key) != binding.get(key)
        for key in ("acceptance_digest", "criteria")
    ):
        return ClosureRefusal("acceptance_changed", "acceptance changed after dispatch")
    if not isinstance(binding.get("semantic_digest"), str) or current.get(
        "semantic_digest"
    ) != binding.get("semantic_digest"):
        return ClosureRefusal(
            "contract_changed", "task contract changed after dispatch"
        )
    return None


def _closure_verdicts(
    run: Run, beads: Beads
) -> tuple[dict[str, bool], dict[str, ClosureRefusal]]:
    """Closure eligibility from the immutable dispatch snapshot.

    Publication may preserve a legacy worker result, but it cannot turn that
    worker's free-form criteria into task completion.  A new strict dispatch
    records a v2 binding; its semantic contract must still be current when
    landing decides whether to close the Bead.  The owner row revision is not
    compared here: ``_close_revision`` re-reads it as the close precondition.
    """
    claimed = results.satisfied_beads(_worker_results(run))
    verdicts: dict[str, bool] = {}
    residuals: dict[str, ClosureRefusal] = {}
    for worker in run.workers:
        result = worker.get("result")
        for bead_id in worker["beads"]:
            binding = _dispatch_binding(worker, bead_id)
            verdicts[bead_id] = False
            if (
                not isinstance(result, Mapping)
                or binding is None
                or binding.get("v2_available") is not True
                or result.get("schema_version") != results.RESULT_SCHEMA_VERSION
            ):
                residuals[bead_id] = ClosureRefusal(
                    "no_binding", "no closure-eligible dispatch acceptance binding"
                )
                continue
            try:
                current = prompts.evidence_binding(beads.show(bead_id))
            except (BatchError, PromptError) as error:
                residuals[bead_id] = ClosureRefusal(
                    "unobservable", f"current acceptance could not be observed: {error}"
                )
                continue
            drift = _contract_drift(binding, current)
            if drift is not None:
                residuals[bead_id] = drift
            elif not claimed.get(bead_id):
                residuals[bead_id] = ClosureRefusal(
                    "unsatisfied", "dispatch acceptance was not fully satisfied"
                )
            else:
                verdicts[bead_id] = True
    return verdicts, residuals


def _close_revision(run: Run, beads: Beads, bead_id: str) -> int:
    """Re-observe the row and return the exact owner CAS token.

    The row may have moved since dispatch for notes or status; that is
    re-observation, not invalidation.  Closing still requires the semantic
    contract to be unchanged and the run to hold the claim it took at start.
    """
    worker = next(worker for worker in run.workers if bead_id in worker["beads"])
    binding = _dispatch_binding(worker, bead_id)
    if binding is None:
        raise ClosureRefusal(
            "no_binding", "no closure-eligible dispatch acceptance binding"
        )
    try:
        bead = beads.show(bead_id)
        current = prompts.evidence_binding(bead)
    except (BatchError, PromptError) as error:
        raise ClosureRefusal(
            "unobservable", f"current task could not be observed: {error}"
        ) from error
    drift = _contract_drift(binding, current)
    if drift is not None:
        raise ClosureRefusal(drift.reason, f"{drift} before close")
    assignee = bead.get("assignee")
    if assignee != run.actor:
        raise ClosureRefusal(
            "claim_moved",
            f"task is assigned to {assignee or 'nobody'}, not the run actor {run.actor}",
        )
    revision = current.get("bead_revision")
    if not isinstance(revision, str) or not revision.isdecimal():
        raise ClosureRefusal(
            "revision_unusable",
            "current owner revision is not an exact decimal integer",
        )
    expected_version = int(revision, 10)
    if not 0 <= expected_version < 2**64:
        raise ClosureRefusal(
            "revision_unusable",
            "current owner revision is outside the unsigned 64-bit range",
        )
    return expected_version


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
        or worker.get(
            "integration_head", (worker.get("result") or {}).get("candidate_sha")
        )
        != run.base_commit
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


def _record_landing_agent_attempt(
    config: Config,
    run_id: str,
    *,
    kind: str,
    job: Mapping[str, Any],
    requested: Mapping[str, str],
    prompt_path: Path,
) -> None:
    """Retain the dispatch facts for an integration or review agent.

    Pueue remains the authority for the task's live and terminal phase.  The
    manifest keeps the launch identity and requested selection so a failed or
    subsequently cleaned task does not erase how the landing was dispatched.
    """
    attempt = {
        "kind": kind,
        "job_id": job.get("job_id"),
        "launch_reference": job.get("reference"),
        "requested": dict(requested),
        "prompt_path": str(prompt_path),
    }

    def record(document: dict[str, Any]) -> None:
        attempts = list(document["landing"].get("agent_attempts") or [])
        attempts.append(attempt)
        document["landing"]["agent_attempts"] = attempts

    update(config, run_id, record)


def _landing_inputs(
    config: Config, project: ProjectAdapter, run: Run, base: str, beads: Beads
) -> str:
    """Bind reuse to declared inputs, including the evidence the reviewer sees."""
    workers = _observe_worker_heads(config, project, run, beads)
    run = load(config, run.run_id)
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


def _observe_worker_heads(
    config: Config, project: ProjectAdapter, run: Run, beads: Beads
) -> list[dict[str, Any]]:
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
        # A later branch commit changes integration scope, not the worker's
        # submitted claim or the verification tied to that claim.
        if worker.get("integration_head") != head:
            from .start import _scope_check

            scope = _scope_check(run, worker, head, beads)
            worker_id = worker["id"]

            def observe(
                document: dict[str, Any],
                *,
                worker_id: str = worker_id,
                head: str = head,
                scope: dict[str, Any] = scope,
            ) -> None:
                for entry in document["workers"]:
                    if entry["id"] == worker_id:
                        entry["integration_head"] = head
                        entry.update(scope)

            run = update(config, run.run_id, observe)
            worker = run.worker(worker_id)
        workers.append(
            {
                "branch": worker["branch"],
                "head": head,
                "result": worker["result"],
                "scope": worker.get("changed_paths"),
            }
        )
    return workers


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
        _clear_stranded_lock(config, run, path)
        try:
            _git(path, "merge", "--abort", owned=True)
        except BatchError as error:
            if gitcmd.stranded_index_lock(error) is not None:
                raise
        _git(path, "reset", "--hard", base, owned=True)
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
    workers = _landable(run)
    branches = [worker["branch"] for worker in workers]
    targets = [
        str(worker.get("integration_head") or worker["result"]["candidate_sha"])
        for worker in workers
    ]
    for position, (worker_branch, target) in enumerate(
        zip(branches, targets, strict=True)
    ):
        try:
            _git(path, "merge", "--no-ff", "--no-edit", target, owned=True)
            continue
        except BatchError as error:
            if gitcmd.stranded_index_lock(error) is not None:
                raise
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
        selection = _review_agent(project, run)
        job = queue_agent(
            config,
            project,
            label=f"{project.project_id}:integrate:{run.run_id}",
            worktree=path,
            prompt=prompt,
            prompt_name="integrate.md",
            group=LANDING_AGENT_GROUP,
            **selection,
            binding=binding(run, None),
            inaccessible=other_worktrees(project, run, None),
        )
        _record_landing_agent_attempt(
            config,
            run.run_id,
            kind="integration",
            job=job,
            requested=selection,
            prompt_path=path / WORKTREE_STATE_DIR / "integrate.md",
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
        _refuse_unless_integrated(path, targets, who="integration agent")
        break
    candidate = _git(path, "rev-parse", "HEAD")
    _refuse_conflict_markers(path, base, candidate)
    return candidate


def _clear_stranded_lock(config: Config, run: Run, path: Path) -> None:
    """Release the run's own integration worktree from a lock a killed landing left."""
    lock = gitcmd.clear_stranded_lock(path)
    if lock is not None:
        land_update(
            config,
            run.run_id,
            index_lock_cleared={"lock": str(lock), "at": now()},
        )


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
        path,
        [
            str(worker.get("integration_head") or worker["result"]["candidate_sha"])
            for worker in _landable(run)
        ],
        who="the kept worktree",
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
    claims = {
        entry["id"]: {
            str(item.get("ac_id") or ""): item for item in entry.get("criteria") or ()
        }
        for result in _worker_results(run)
        for entry in result.get("beads") or ()
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
    }
    criteria: dict[str, list[str]] = {}
    for worker in run.workers:
        for evidence in worker.get("evidence_binding") or ():
            if (
                not isinstance(evidence, Mapping)
                or evidence.get("v2_available") is not True
            ):
                continue
            bead_id = evidence.get("id")
            if not isinstance(bead_id, str):
                continue
            criteria[bead_id] = [
                f"- [{'x' if claims.get(bead_id, {}).get(str(item.get('ac_id')), {}).get('status') in {'satisfied', 'superseded'} else ' '}] "
                f"{str(item.get('text') or '')[: prompts.RESULT_TEXT_CHARS]}"
                for item in evidence.get("criteria") or ()
                if isinstance(item, Mapping)
            ]
    lines = [f"Batch `{run.run_id}` on base `{run.base_commit[:12]}`.", ""]
    for bead_id in run.beads:
        try:
            bead_title = str(beads.show(bead_id).get("title") or "")
        except PromptError:
            bead_title = ""
        lines.append(f"**{bead_id}** {bead_title}".rstrip())
        lines.extend(criteria.get(bead_id, []))
        lines.append("")
    # GitHub refuses a longer body. Past the limit, keep every item's verdict
    # without its narration, then only the pointer to the stored results,
    # which always hold the complete narration.
    for detail in ("narrated", "verdicts", "pointer"):
        body = "\n".join([*lines, *_self_review_lines(run, detail=detail)])
        body = body.rstrip() + "\n"
        if len(body) <= GITHUB_BODY_CHARS:
            break
    return title, body


# GitHub's maximum pull-request body length, in characters.
GITHUB_BODY_CHARS = 65_536


def _self_review_lines(run: Run, *, detail: str = "narrated") -> list[str]:
    """Each filed worker's self-review, as the PR body's Self-review section.

    ``detail`` is ``narrated`` (every item with its narration), ``verdicts``
    (each item's verdict only) or ``pointer`` (the pass counts only), the
    shorter forms for a body that would otherwise exceed GitHub's limit.
    """
    sections: list[str] = []
    for worker in run.workers:
        result = worker.get("result")
        review = result.get("self_review") if isinstance(result, Mapping) else None
        if not isinstance(review, Mapping):
            continue
        sources = ", ".join(f"`{source}`" for source in review.get("checklists") or ())
        sections.append(
            f"**{worker['id']}**: {review.get('passes')} pass(es) against {sources}"
        )
        for item in review.get("items") or ():
            if not isinstance(item, Mapping) or detail == "pointer":
                continue
            mark = "- [x]" if item.get("applies") else "- N/A"
            text = f"{mark} {item.get('item') or ''}"
            sections.append(
                f"{text}: {item.get('narration') or ''}"
                if detail == "narrated"
                else text
            )
        sections.append("")
    if not sections:
        return []
    note = (
        []
        if detail == "narrated"
        else [
            f"The self-review exceeds GitHub's body limit; each worker's filed "
            f"result holds it in full (`agentctl batch status {run.run_id}`).",
            "",
        ]
    )
    return ["## Self-review", "", *note, *sections]


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
    """Describe a terminal verification outcome from the job's own record."""
    phase = str(job.get("phase") or "vanished")
    exit_code = job.get("exit_code")
    duration = _job_duration_seconds(job)
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


def _run_seconds(job: Mapping[str, Any], first_seen: float) -> float:
    """How long a started job has run, from its start time when pueue has one.

    A reused job may have started before this landing did, so the landing's
    own observation is only the fallback for a missing or unparseable time.
    """
    started = job.get("started_at")
    try:
        begun = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        return max(0.0, (datetime.now(UTC) - begun).total_seconds())
    except (TypeError, ValueError):
        return time.monotonic() - first_seen


def _await_verification(
    profile: str, job_id: int, reference: Any, timeout_seconds: float
) -> dict[str, Any]:
    """Wait for a verification job to reach a terminal state.

    Time the job spends queued (behind a paused or full pool) does not count:
    the operation's timeout bounds the command's run, and the wrapper enforces
    it from the job's start. A job still not terminal once it has run for its
    timeout plus the wrapper's grace is `verify_running`, a retryable refusal:
    landing again reuses the same task rather than submitting another check.
    A zero runtime deadline keeps observing that same job until it settles;
    an observation interval never becomes an execution budget.
    """
    limit = timeout_seconds + VERIFY_EXIT_GRACE_SECONDS if timeout_seconds else None
    first_seen: float | None = None
    wait_for = limit if limit is not None else VERIFY_EXIT_GRACE_SECONDS
    while True:
        waited = launch.wait(job_id, timeout_seconds=wait_for, reference=reference)
        # `launch.wait` can return the last non-terminal view at the instant
        # its deadline passes; pueue's current record decides.
        try:
            task = launch.find_task(
                pueue.tasks(), waited.get("job_id", job_id), reference
            )
        except PueueError:
            task = None
        if task is not None:
            waited = {**waited, **launch.job_view(task)}
        if waited.get("terminal"):
            return waited
        job_id = int(waited.get("job_id", job_id))
        if waited.get("detail"):
            raise BatchRefusal(
                "verify_running",
                f"{profile} task {job_id} is {waited.get('phase')}; "
                f"the queue could not be read: {waited['detail']}",
            )
        if not waited.get("started_at"):
            first_seen = None
            wait_for = limit if limit is not None else VERIFY_EXIT_GRACE_SECONDS
            continue
        if first_seen is None:
            first_seen = time.monotonic()
        ran = _run_seconds(waited, first_seen)
        if limit is not None and ran >= limit:
            raise BatchRefusal(
                "verify_running",
                f"{profile} task {job_id} is still {waited.get('phase')} after "
                f"{int(ran)}s of its {timeout_seconds:g}s budget; "
                "landing again waits for the same task",
            )
        wait_for = limit - ran if limit is not None else VERIFY_EXIT_GRACE_SECONDS


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
            "tree": _git(path, "rev-parse", "HEAD^{tree}"),
            "dirty": bool(_git(path, "status", "--porcelain")),
        }
    except BatchError:
        return {"head": None, "tree": None, "dirty": None}


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
    *,
    _retried_unbound_cache: bool = False,
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
                attestation = _hosted_check_attestation(pull, check, candidate)
                if not attestation:
                    receipt["status"] = "unknown"
                    receipt["detail"] = (
                        f"hosted check {check} succeeded without a candidate-bound tested SHA"
                    )
                receipt.update(attestation)
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
    waited = _await_verification(
        profile, job_id, started.get("reference"), operation.timeout_seconds
    )
    if waited.get("phase") != "succeeded":
        raise BatchRefusal(
            "verify_failed",
            _verification_failure_detail(profile, waited, operation.timeout_seconds),
            timed_out=waited.get("phase") == "timeout",
        )
    after = _worktree_attestation(path)
    clean_candidate = (
        before["head"] == candidate
        and after["head"] == candidate
        and before.get("tree") is not None
        and after.get("tree") == before.get("tree")
        and before["dirty"] is False
        and after["dirty"] is False
    )
    reference = started.get("reference")
    if not isinstance(reference, str) or not reference:
        raise BatchRefusal(
            "verify_failed",
            f"verification {profile} succeeded without an AgentCTL launch reference",
        )
    task = launch.find_task(pueue.tasks(), waited["job_id"], started.get("reference"))
    execution = (
        launch.successful_cached_attempt(
            config,
            task,
            {"head": candidate, "tree": before.get("tree"), "dirty": False},
            started.get("environment_receipt")
            if isinstance(started.get("environment_receipt"), Mapping)
            else None,
        )
        if task is not None and clean_candidate
        else None
    )
    if execution is None and clean_candidate:
        if started.get("reused") is True and not _retried_unbound_cache:
            # An active task can be reused before its execution binding exists.
            # If it ran a different checkout, keep that queue record as
            # diagnostic evidence and submit one fresh verification.
            return _verify(
                config,
                project,
                run,
                path,
                candidate,
                sleep,
                beads,
                _retried_unbound_cache=True,
            )
        raise BatchRefusal(
            "verify_failed",
            f"verification {profile} succeeded without an attempt bound to clean candidate {candidate[:12]}",
        )
    receipt = {
        "kind": "operation",
        "operation": profile,
        "job_id": waited["job_id"],
        "candidate_sha": candidate,
        "requested_sha": candidate,
        "phase": "succeeded",
        "status": "passed",
        "reference": reference,
        "receipt": f"agentctl://jobs/{waited['job_id']}/{reference}",
        "command": list(operation.command),
        "head_before": before["head"],
        "head_after": after["head"],
        "git_dirty": (
            False
            if clean_candidate
            else (True if before["dirty"] is True or after["dirty"] is True else None)
        ),
        "recorded_at": now(),
    }
    if clean_candidate and execution is not None:
        receipt["tested_sha"] = candidate
        receipt["executed_attempt"] = execution["attempt"]
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
    selection = _review_agent(project, run)
    job = queue_agent(
        config,
        project,
        label=f"{project.project_id}:review:{run.run_id}",
        worktree=path,
        prompt=prompt,
        prompt_name="review.md",
        group=LANDING_AGENT_GROUP,
        **selection,
        schema="judge",
        binding=binding(run, None),
        inaccessible=other_worktrees(project, run, None),
    )
    _record_landing_agent_attempt(
        config,
        run.run_id,
        kind="review",
        job=job,
        requested=selection,
        prompt_path=path / WORKTREE_STATE_DIR / "review.md",
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


def _advance_main_checkout(project: ProjectAdapter, candidate: str) -> str:
    """Move the clean main checkout after a master push so live dots follow it."""
    root = project.root
    branch = workspace_of(project).base_branch
    try:
        if _git(root, "symbolic-ref", "--quiet", "--short", "HEAD") != branch:
            return "skipped: main checkout is on another branch"
        if _git(root, "status", "--porcelain", "--untracked-files=normal"):
            return "skipped: main checkout has local changes"
        head = _git(root, "rev-parse", "HEAD")
        if head == candidate:
            return "already current"
        if _git(root, "merge-base", head, candidate) != head:
            return "skipped: main checkout cannot fast-forward to published commit"
        # The one index write agentctl makes in a main checkout: live dots
        # links read the published files from it.
        _git(root, "merge", "--ff-only", candidate, main_checkout=True)
    except BatchError as error:
        return f"failed: {error}"
    return f"fast-forwarded to {candidate}"


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
        return {
            "policy": "master",
            "candidate_sha": candidate,
            "base_commit": base,
            "main_checkout": _advance_main_checkout(project, candidate),
        }
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
    verdicts, closure_residuals = _closure_verdicts(run, beads)
    beads_state: dict[str, dict[str, str]] = {}
    # What reached the default branch: the squash-merge commit under the PR
    # policy, the candidate itself under the master policy.
    landed = str(published.get("merge_commit") or candidate)
    for bead_id in run.beads:
        refusal = closure_residuals.get(bead_id) or ClosureRefusal(
            "no_binding", "no closure evidence"
        )
        if verdicts.get(bead_id):
            try:
                expected_version = _close_revision(run, beads, bead_id)
                beads.close(
                    bead_id,
                    reason=f"batch {run.run_id} {landed}",
                    actor=run.actor,
                    expected_version=expected_version,
                )
                beads_state[bead_id] = {
                    "state": "closed",
                    "evidence": f"batch {run.run_id} {landed}",
                }
                continue
            except ClosureRefusal as error:
                refusal = error
            except BatchError as error:
                beads_state[bead_id] = {
                    "state": "open",
                    "reason": "close_failed",
                    "evidence": f"close failed: {error}",
                }
                continue
        residual = f"batch {run.run_id} landed {landed}; {refusal}"
        try:
            beads.comment(bead_id, residual, actor=run.actor)
        except BatchError as error:
            residual += f" (comment failed: {error})"
        # The batch is over; a claim it leaves behind only hides the bead
        # from the next dispatch.  A claim another actor took is theirs.
        if refusal.reason != "claim_moved":
            try:
                beads.unclaim(bead_id, actor=run.actor)
            except BatchError as error:
                residual += f" (unclaim failed: {error})"
        beads_state[bead_id] = {
            "state": "open",
            "reason": refusal.reason,
            "evidence": residual,
        }
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
    one after a landing failed or the queue lost it, so a caller that cannot
    hold a process for the whole landing still drives it through pueue. The
    replacement is placed like every other requeue: behind the worker tasks
    still running, and stashed while a worker owes a result, because a
    landing that runs before then only refuses `worker_not_done`.
    """
    run = load(config, run_id)
    with (
        transition_locked(config, run.run_id),
        landing_recovery_locked(config, run.run_id),
    ):
        run = load(config, run.run_id)
        if run.project != project.project_id:
            raise BatchRefusal("project", f"run {run_id} belongs to {run.project}")
        _refuse_unless_live(run)
        tasks = pueue.tasks()
        task_id = run.landing.get("task_id")
        if run.landing.get("pending_launch"):
            run, queued = requeue_landing(config, project, run, tasks)
            return {**run.to_dict(), "landing_task_id": queued}
        current = launch.find_task(tasks, task_id, run.landing.get("task_reference"))
        if current is not None and not current.terminal:
            raise BatchRefusal(
                "landing_in_progress",
                f"landing task {task_id} is {current.status.lower()}",
            )
        run, queued = requeue_landing(config, project, run, tasks)
        return {**run.to_dict(), "landing_task_id": queued}


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
    with (
        transition_locked(config, run.run_id, blocking=False),
        landing_locked(config, run.run_id),
    ):
        run = load(config, run.run_id)
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
        _observe_worker_heads(config, project, run, beads)
        run = load(config, run_id)
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
            evidence = {"kind": kind, "candidate_sha": base}
            if project.workspace.review == "none":
                review_verdict = _review_by_policy(run, evidence, base)
            else:
                path = Path(run.workers[0]["worktree"])
                run = land_update(config, run_id, verify_run=evidence)
                review_verdict = _review(config, project, run, path, base, base, beads)
            run = _accept(
                config,
                project,
                run,
                beads,
                candidate=base,
                verify_run=evidence,
                review_verdict=review_verdict,
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
        stranded = gitcmd.stranded_index_lock(error)
        failure: dict[str, Any] = {"code": "substrate", "detail": str(error)}
        if stranded is not None:
            failure = {
                "code": "git_index_lock_stranded",
                "detail": str(error),
                "lock": str(stranded.lock),
                "removed": stranded.removed,
            }
        land_update(config, run_id, failure=failure)
        raise
    return run.to_dict()


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _process_users(path: Path) -> list[str]:
    """Current-directory and open-file users outside pueue's authority."""
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
            continue
        try:
            targets = _process_open_files(entry)
        except PermissionError:
            try:
                owner = entry.stat().st_uid
            except FileNotFoundError:
                continue
            # As with cwd, foreign users outside our inspection authority
            # are not represented as observed holders or observed non-holders.
            if owner != os.getuid():
                continue
            targets = _stable_privileged_open_files(entry)
        for target in targets:
            if target.is_absolute() and _under(target, path):
                users.append(f"pid {entry.name} open file {target}")
                break
    return users


def _process_open_files(entry: Path) -> list[Path]:
    targets: list[Path] = []
    try:
        descriptors = tuple((entry / "fd").iterdir())
        for descriptor in descriptors:
            try:
                targets.append(Path(os.readlink(descriptor)))
            except FileNotFoundError:
                # A descriptor closed while the process was being inspected.
                continue
    except FileNotFoundError:
        return []
    except PermissionError:
        raise
    except OSError as error:
        if error.errno in {errno.ENOENT, errno.ESRCH}:
            return []
        raise BatchError(
            f"cannot inspect process {entry.name} open files: {error}"
        ) from error
    return targets


def _privileged_open_files(entry: Path) -> list[Path]:
    try:
        completed = subprocess.run(
            [
                "sudo",
                "-n",
                "find",
                str(entry / "fd"),
                "-maxdepth",
                "1",
                "-type",
                "l",
                "-printf",
                "%l\\0",
            ],
            capture_output=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BatchError(
            f"cannot inspect process {entry.name} open files: {error}"
        ) from error
    if completed.returncode != 0:
        raise BatchError(
            f"cannot inspect process {entry.name} open files: {os.fsdecode(completed.stderr).strip()}"
        )
    return [
        Path(os.fsdecode(target)) for target in completed.stdout.split(b"\0") if target
    ]


def _stable_privileged_open_files(entry: Path) -> list[Path]:
    start = _process_starttime(entry)
    if start is None:
        return []
    try:
        targets = _privileged_open_files(entry)
    except BatchError:
        if _process_starttime(entry) is None:
            return []
        raise
    end = _process_starttime(entry)
    if end is None:
        return []
    if end != start:
        raise BatchError(f"process {entry.name} changed during open-file probe")
    return targets


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
    delete_branch: bool = False,
) -> str | None:
    """Release one terminal checkout while retaining its Git history.

    Returns why it was kept, or None once it is gone.
    """

    def retire_branch() -> None:
        head = gitcmd.git(
            project.root,
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}^{{commit}}",
            ok_statuses=(0, 1),
            error=BatchError,
        )
        if head:
            _recovery_ref(project.root, run_id, recorded_path or project.root, head)
            _git(project.root, "update-ref", "-d", f"refs/heads/{branch}", head)

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
        if delete_branch:
            try:
                retire_branch()
            except BatchError as error:
                return f"branch kept; {error}"
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
            if detached or delete_branch:
                _recovery_ref(project.root, run_id, path, head)
            if not detached and branch_head != head:
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
    if delete_branch:
        # The checkout is gone (or was already absent), so this ref can now be
        # removed without invalidating a registered worktree.
        try:
            retire_branch()
        except BatchError as error:
            return f"branch kept; {error}"
    return None


def _drop_worktrees(
    config: Config, project: ProjectAdapter, run: Run, *, published: str | None = None
) -> list[str]:
    with project_locked(config, project.project_id):
        return _drop_worktrees_locked(config, project, run, published=published)


def _drop_worktrees_locked(
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
    with (
        transition_locked(config, run.run_id),
        landing_locked(config, run.run_id),
        landing_recovery_locked(config, run.run_id),
        project_locked(config, project.project_id),
    ):
        run = load(config, run.run_id)
        _refuse_unless_live(run)
        tasks = pueue.tasks()
        for worker in run.workers:
            if worker.get("pending_launch"):
                pending_task(config, worker["pending_launch"], tasks)
        if run.landing.get("pending_launch"):
            pending_task(config, run.landing["pending_launch"], tasks)
        landing_id = run.landing.get("task_id")
        landing_task = launch.find_task(
            tasks,
            landing_id,
            run.landing.get("pending_launch") or run.landing.get("task_reference"),
        )
        if landing_task is not None and landing_task.status == "Running":
            raise BatchRefusal(
                "landing_in_progress", f"landing task {landing_id} is running"
            )
        residual: list[str] = []
        for worker in run.workers:
            task_id = worker.get("task_id")
            task = launch.find_task(
                pueue.tasks(),
                task_id,
                worker.get("pending_launch") or worker.get("task_reference"),
            )
            if task is not None and not task.terminal:
                launch.cancel(
                    config,
                    task.task_id,
                    actor=run.actor,
                    reason=reason or "batch abandoned",
                )
        if landing_task is not None and not landing_task.terminal:
            launch.cancel(
                config,
                landing_task.task_id,
                actor=run.actor,
                reason=reason or "batch abandoned",
            )
        for bead_id in run.beads:
            try:
                beads.unclaim(bead_id, actor=run.actor)
            except BatchError as error:
                residual.append(f"{bead_id}: unclaim failed: {error}")
        residual.extend(_drop_worktrees_locked(config, project, run))
        record = {"reason": reason, "at": now(), "residual": residual}

        def mark(document: dict[str, Any]) -> None:
            document["abandoned"] = record

        return update(config, run_id, mark).to_dict()


# A batch's own worktree branches: `batch/<run id>/<worker id or integration>`.
_BATCH_BRANCH = re.compile(r"^batch/(?P<run>[^/]+)/[^/]+$")


def _branch_reachable_from(root: Path, branch: str, base: str) -> bool:
    """Whether the branch tip is already preserved by the default branch."""
    try:
        gitcmd.git(
            root,
            "merge-base",
            "--is-ancestor",
            f"refs/heads/{branch}",
            base,
            error=BatchError,
        )
    except BatchError:
        return False
    return True


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
            checkout_absent = (registered is None or registered.path is None) and (
                recorded_path is None or not recorded_path.exists()
            )
            if registered is None or registered.path is None:
                if recorded_path is None or not recorded_path.exists():
                    # A terminal manifest still owns the branch when its
                    # checkout has already disappeared.
                    may_delete = owner is not None and (
                        owner.acceptance is not None
                        or (
                            owner.abandoned is not None
                            and bool(default_base)
                            and _branch_reachable_from(
                                project.root, branch, default_base
                            )
                        )
                    )
                    if not may_delete:
                        if owner is not None and owner.abandoned is not None:
                            kept.append(
                                {
                                    "branch": branch,
                                    "reason": (
                                        "branch kept; commits are not reachable from default branch"
                                        if default_base
                                        else "branch kept; default branch could not be resolved"
                                    ),
                                }
                            )
                            continue
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
                delete_branch=(
                    owner is not None
                    and (
                        owner.acceptance is not None
                        or (
                            owner.abandoned is not None
                            and bool(default_base)
                            and _branch_reachable_from(
                                project.root, branch, default_base
                            )
                        )
                    )
                ),
            )
            if reason:
                kept.append({"branch": branch, "reason": reason})
            elif checkout_absent:
                absent.append(branch)
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
