"""Starting a batch, filing a worker's result, resuming a worker."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from . import gitcmd, pueue, results, worktrunk
from .agents import (
    PUSH_TIMEOUT_SECONDS,
    WORKTREE_STATE_DIR,
    binding,
    landing_group,
    queue_agent,
    queue_landing,
    result_path,
    worker_then,
    workspace_of,
    worktree_path,
    write_prompt,
)
from .beads import Beads, SubprocessBeads
from .config import Config
from .launch import JobError
from .manifest import (
    HARNESSES,
    REVIEW_PROFILE,
    BatchError,
    BatchRefusal,
    Run,
    create,
    land_update,
    list_runs,
    load,
    manifest_path,
    new_run_id,
    now,
    project_locked,
    set_worker,
    update,
)
from .projects import ProjectAdapter
from .prompts import (
    PromptConfig,
    PromptError,
    compile_worker_prompt,
    resolve_group,
    resume_prompt,
    validate_members,
)
from .pueue import PueueError
from .worktrunk import WorktrunkError


def _member_sets(
    reader: Beads, seeds: Sequence[str], workers: Sequence[Sequence[str]] | None
) -> list[tuple[str, tuple[str, ...]]]:
    if workers:
        return [
            (list(group)[0], tuple(dict.fromkeys(group))) for group in workers if group
        ]
    if not seeds:
        raise BatchRefusal(
            "members", "a batch needs at least one seed bead or --worker"
        )
    sets: list[tuple[str, tuple[str, ...]]] = []
    for seed in seeds:
        leader, members = resolve_group(seed, reader)
        if not any(leader == existing for existing, _members in sets):
            sets.append((leader if leader in members else members[0], members))
    return sets


def _live_runs(config: Config, project_id: str) -> list[Run]:
    return [run for run in list_runs(config, project_id) if run.live]


def _base_commit(project: ProjectAdapter) -> str:
    base = workspace_of(project).default_base
    if base.startswith("origin/"):
        try:
            gitcmd.git(
                project.root,
                "fetch",
                "--quiet",
                "origin",
                timeout=PUSH_TIMEOUT_SECONDS,
                error=BatchError,
            )
        except BatchError:
            pass
    return gitcmd.git(
        project.root, "rev-parse", "--verify", f"{base}^{{commit}}", error=BatchError
    )


def _prepare(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    beads: Beads,
    *,
    backend: str | None,
    model: str | None,
    effort: str | None,
) -> Run:
    """Claim, create, enqueue — each step skipped where the manifest records it done."""
    packets = PromptConfig.from_project(project, shared_template=config.worker_contract)
    if run.harness == "queued":
        pueue.group_add(landing_group(project.project_id), 1)
    for index, worker in enumerate(run.workers):
        worker_id = worker["id"]
        if not worker.get("claimed"):
            # Each claim is recorded as it lands, so a failure part-way
            # through a worker releases exactly the beads it took.
            for bead_id in worker["beads"]:
                if bead_id in (run.workers[index].get("claimed_beads") or []):
                    continue
                beads.claim(bead_id, actor=run.actor)
                run = set_worker(
                    config,
                    run.run_id,
                    index,
                    claimed_beads=[
                        *(run.workers[index].get("claimed_beads") or []),
                        bead_id,
                    ],
                )
            run = set_worker(config, run.run_id, index, claimed=True)
        if not worker.get("worktree"):
            branch = worker["branch"]
            existing = worktrunk.worktrunk_find(project.root, branch)
            created = (
                existing
                if existing and existing.path
                else worktrunk.worktrunk_create(
                    project.root,
                    branch,
                    path=worktree_path(project, branch),
                    base=run.base_commit,
                )
            )
            if created.path is None:
                raise WorktrunkError(f"wt created {branch} without a path")
            path = created.path
            snapshot = compile_worker_prompt(
                worker_id,
                project_id=project.project_id,
                reader=beads,
                config=packets,
                backend=backend,
                model=model,
                effort=effort,
                member_ids=worker["beads"],
                branch=branch,
                batch={
                    "run_id": run.run_id,
                    "base_commit": run.base_commit,
                    "worktree": str(path),
                    "result_path": str(result_path(path)),
                    "result_schema": str(
                        path / WORKTREE_STATE_DIR / "worker.schema.json"
                    ),
                    "harness": run.harness,
                },
            )
            prompt_path = write_prompt(path, "prompt.md", snapshot.prompt)
            results.write_schema(
                path / WORKTREE_STATE_DIR / "worker.schema.json", "worker"
            )
            run = set_worker(
                config,
                run.run_id,
                index,
                worktree=str(path),
                prompt_path=str(prompt_path),
                result_path=str(result_path(path)),
                backend=snapshot.dimensions.backend,
                model=snapshot.dimensions.model,
                effort=snapshot.dimensions.effort,
            )
            worker = run.workers[index]
        if run.harness == "queued" and worker.get("task_id") is None:
            path = Path(worker["worktree"])
            job = queue_agent(
                config,
                project,
                label=f"{project.project_id}:worker:{run.run_id}:{worker_id}",
                worktree=path,
                prompt=(path / WORKTREE_STATE_DIR / "prompt.md").read_text(),
                prompt_name="prompt.md",
                backend=worker["backend"],
                model=worker["model"],
                effort=worker["effort"],
                schema="worker",
                then=worker_then(config, run.run_id, worker_id, result_path(path)),
                binding=binding(run, worker_id),
            )
            run = set_worker(config, run.run_id, index, task_id=job["job_id"])
    if run.landing.get("task_id") is None:
        after = [
            worker["task_id"]
            for worker in run.workers
            if worker.get("task_id") is not None
        ]
        landing_id = queue_landing(
            config, project, run, after=after, stashed=run.harness == "external"
        )
        run = land_update(config, run.run_id, task_id=landing_id)

    def mark_prepared(document: dict[str, Any]) -> None:
        document["prepared"] = True

    return update(config, run.run_id, mark_prepared)


def _rollback(
    config: Config, project: ProjectAdapter, run_id: str, beads: Beads
) -> None:
    try:
        run = load(config, run_id)
    except BatchRefusal:
        return
    for worker in run.workers:
        claimed = worker.get("claimed_beads") or (
            worker["beads"] if worker.get("claimed") else []
        )
        for bead_id in claimed:
            try:
                beads.unclaim(bead_id, actor=run.actor)
            except BatchError:
                pass
        if worker.get("worktree"):
            try:
                worktrunk.worktrunk_remove(project.root, worker["branch"], force=True)
            except WorktrunkError:
                pass
    manifest_path(config, run_id).unlink(missing_ok=True)
    manifest_path(config, run_id).with_suffix(".lock").unlink(missing_ok=True)


def start(
    config: Config,
    project: ProjectAdapter,
    seeds: Sequence[str],
    *,
    workers: Sequence[Sequence[str]] | None = None,
    harness: str = "queued",
    backend: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    reader: Beads | None = None,
) -> dict[str, Any]:
    """Validate the members, write the manifest, claim, create worktrees, enqueue.

    A run already prepared for the same member set is returned unchanged; one
    left half-prepared is completed. Nothing launches twice.
    """
    if harness not in HARNESSES:
        raise BatchRefusal("harness", f"harness must be one of {HARNESSES}")
    workspace = workspace_of(project)
    beads = reader or SubprocessBeads(project.root)
    member_sets = _member_sets(beads, seeds, workers)
    requested = {bead for _leader, members in member_sets for bead in members}
    claimed: set[str] = set()
    for live in _live_runs(config, project.project_id):
        if set(live.beads) == requested:
            if live.prepared:
                return {**live.to_dict(), "resumed": False, "existing": True}
            with project_locked(config, project.project_id):
                completed = _prepare(
                    config,
                    project,
                    live,
                    beads,
                    backend=backend,
                    model=model,
                    effort=effort,
                )
            return {**completed.to_dict(), "resumed": True, "existing": True}
        claimed.update(live.beads)
    refusals = validate_members(
        beads, [members for _leader, members in member_sets], claimed=claimed
    )
    if refusals:
        raise BatchRefusal(
            "members",
            "; ".join(f"{item.bead}: {item.detail}" for item in refusals),
            refusals=[item.to_dict() for item in refusals],
        )
    base_commit = _base_commit(project)
    run_id = new_run_id(project.project_id)
    run = Run(
        run_id=run_id,
        project=project.project_id,
        base_commit=base_commit,
        created_at=now(),
        harness=harness,
        runtime_revision=os.path.realpath(config.agentctl_executable),
        verify_profile=workspace.verify.get("candidate"),
        review_profile=REVIEW_PROFILE,
        workers=tuple(
            {
                "id": leader,
                "beads": list(members),
                "branch": f"batch/{run_id}/{leader}",
                "worktree": None,
                "task_id": None,
                "task_ids": [],
                "claimed": False,
                "claimed_beads": [],
                "prompt_path": None,
                "result_path": None,
                "result": None,
            }
            for leader, members in member_sets
        ),
        landing={
            "task_id": None,
            "integration_branch": f"batch/{run_id}/integration",
            "integration_worktree": None,
            "pr_number": None,
            "candidate_sha": None,
            "verify_run": None,
            "review_verdict": None,
            "refreshes": 0,
            "failure": None,
        },
        acceptance=None,
        prepared=False,
    )
    create(config, run)
    try:
        with project_locked(config, project.project_id):
            prepared = _prepare(
                config,
                project,
                run,
                beads,
                backend=backend,
                model=model,
                effort=effort,
            )
    except (
        BatchRefusal,
        BatchError,
        PromptError,
        PueueError,
        WorktrunkError,
        JobError,
    ):
        _rollback(config, project, run_id, beads)
        raise
    return {**prepared.to_dict(), "resumed": False, "existing": False}


def result(config: Config, run_id: str, worker_id: str, path: Path) -> dict[str, Any]:
    """File a worker's result after validating it and binding it to the worktree head."""
    run = load(config, run_id)
    worker = run.worker(worker_id)
    value, errors = results.load_result(path, kind="worker")
    if errors:
        raise BatchRefusal("invalid_result", "; ".join(errors[:6]), errors=errors)
    worktree = worker.get("worktree")
    if worktree:
        head = gitcmd.git(Path(worktree), "rev-parse", "HEAD", error=BatchError)
        if head != value["candidate_sha"]:
            raise BatchRefusal(
                "candidate_mismatch",
                f"result names {value['candidate_sha'][:12]} but {worktree} is at {head[:12]}",
            )
    if value["candidate_sha"] == run.base_commit:
        raise BatchRefusal(
            "empty_candidate",
            f"result names the base commit {run.base_commit[:12]}; a worker with nothing to commit is not a candidate",
        )
    if worktree:
        # Landing merges every worker branch onto the run's base; a candidate
        # that does not descend from it carries work from somewhere else.
        try:
            gitcmd.git(
                Path(worktree),
                "merge-base",
                "--is-ancestor",
                run.base_commit,
                value["candidate_sha"],
                error=BatchError,
            )
        except BatchError as error:
            raise BatchRefusal(
                "candidate_off_base",
                f"result names {value['candidate_sha'][:12]}, which does not "
                f"descend from the run's base {run.base_commit[:12]}",
            ) from error
    unknown = {entry["id"] for entry in value["beads"]} - set(worker["beads"])
    if unknown:
        raise BatchRefusal(
            "foreign_beads",
            "result covers beads outside the worker: " + ", ".join(sorted(unknown)),
        )

    def record(document: dict[str, Any]) -> None:
        for entry in document["workers"]:
            if entry["id"] == worker_id:
                entry["result"] = value
                entry["result_path"] = str(path)
                entry["result_recorded_at"] = now()

    run = update(config, run_id, record)
    released = False
    landing_id = run.landing.get("task_id")
    if (
        run.harness == "external"
        and isinstance(landing_id, int)
        and all(item.get("result") for item in run.workers)
    ):
        task = pueue.task(landing_id)
        if task is not None and task.status == "Stashed":
            pueue.enqueue(landing_id)
            released = True
    return {
        **run.worker(worker_id),
        "landing_task": landing_id,
        "landing_released": released,
    }


def resume(
    config: Config,
    project: ProjectAdapter,
    run_id: str,
    worker_id: str,
    *,
    backend: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    """Queue a fresh agent into the worker's worktree with its original packet."""
    run = load(config, run_id)
    if run.acceptance is not None:
        raise BatchRefusal("already_accepted", f"run {run_id} has landed")
    if run.abandoned is not None:
        raise BatchRefusal("abandoned", f"run {run_id} was abandoned")
    worker = run.worker(worker_id)
    worktree = worker.get("worktree")
    if not worktree or not Path(worktree).is_dir():
        raise BatchRefusal(
            "worker_missing",
            f"worker {worker_id} has no worktree; start the batch instead",
        )
    tasks = pueue.tasks()
    current = (
        tasks.get(worker["task_id"]) if isinstance(worker.get("task_id"), int) else None
    )
    if current is not None and not current.terminal:
        raise BatchRefusal(
            "worker_active", f"task {current.task_id} is still {current.status.lower()}"
        )
    packets = PromptConfig.from_project(project, shared_template=config.worker_contract)
    beads = SubprocessBeads(project.root)
    path = Path(worktree)
    packet_path = path / WORKTREE_STATE_DIR / "prompt.md"
    prompt = resume_prompt(
        config=packets,
        bead=beads.show(worker_id),
        branch=worker["branch"],
        base=run.base_commit,
        worktree=path,
        packet=packet_path.read_text() if packet_path.is_file() else None,
    )
    # Each resume keeps its own packet and result beside the original.
    attempt = len(worker.get("task_ids") or []) + 1
    while (path / WORKTREE_STATE_DIR / f"resume-{attempt}.md").exists():
        attempt += 1
    resume_result = path / WORKTREE_STATE_DIR / f"resume-{attempt}.result.json"
    job = queue_agent(
        config,
        project,
        label=f"{project.project_id}:resume:{run_id}:{worker_id}",
        worktree=path,
        prompt=prompt,
        prompt_name=f"resume-{attempt}.md",
        backend=backend or worker.get("backend") or packets.default_backend,
        model=model or worker.get("model") or packets.default_model,
        effort=effort or worker.get("effort") or packets.default_effort,
        schema="worker",
        then=worker_then(config, run_id, worker_id, resume_result),
        binding=binding(run, worker_id),
    )
    task_id = job["job_id"]

    def record(document: dict[str, Any]) -> None:
        for entry in document["workers"]:
            if entry["id"] == worker_id:
                entry["task_id"] = task_id
                entry["task_ids"] = [*entry.get("task_ids", []), task_id]
                entry["result"] = None
                entry["result_path"] = str(resume_result)
                entry["prompt_path"] = str(
                    path / WORKTREE_STATE_DIR / f"resume-{attempt}.md"
                )
        document["landing"]["failure"] = None

    run = update(config, run_id, record)
    landing_id = run.landing.get("task_id")
    if run.harness == "queued":
        # A landing task waits on the worker tasks it was queued behind; the
        # new worker task is not among them, so any landing that has not
        # started is replaced by one queued behind every current worker task.
        old = tasks.get(landing_id) if isinstance(landing_id, int) else None
        replace = old is None or old.status != "Running"
        if old is not None and replace:
            pueue.remove([landing_id])
        if replace:
            after = [
                item["task_id"]
                for item in run.workers
                if isinstance(item.get("task_id"), int)
            ]
            new_landing = queue_landing(
                config, project, run, after=after, stashed=False
            )

            def relink(document: dict[str, Any]) -> None:
                document["landing"]["task_id"] = new_landing

            run = update(config, run_id, relink)
    return {**run.to_dict(), "job": job, "worker": worker_id}
