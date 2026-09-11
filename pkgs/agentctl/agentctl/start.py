"""Starting a batch, filing a worker's result, resuming a worker."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import gitcmd, launch, pueue, results, worktrunk
from .agents import (
    PUSH_TIMEOUT_SECONDS,
    WORKTREE_STATE_DIR,
    binding,
    ensure_landing_groups,
    other_worktrees,
    queue_agent,
    queue_landing,
    requeue_landing,
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
    landing_recovery_locked,
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
    BdReader,
    PromptConfig,
    PromptError,
    compile_worker_prompt,
    resolve_group,
    resume_prompt,
    scope_authority,
    scope_violations,
    validate_effort,
    validate_members,
    write_scope,
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


def focused_verification(
    config: Config, project: ProjectAdapter, worktree: Path
) -> str | None:
    """The command a worker runs for the descriptor's focused verification."""
    operation = workspace_of(project).verify.get("focused")
    if not operation:
        return None
    return (
        f"{config.agentctl_executable} job start {project.project_id} {operation} "
        f"--workspace {worktree} --wait"
    )


def _latest_attempt_selection(worker: Mapping[str, Any]) -> tuple[str, str, str] | None:
    """The last complete selection recorded at launch time, if there is one.

    Attempt records are the audit authority for a resumed worker.  A manifest
    written before they existed has no such authority, so its historical
    selection remains unknown rather than being reconstructed from its current
    fields.
    """
    attempts = worker.get("attempts")
    if not isinstance(attempts, list):
        return None
    for attempt in reversed(attempts):
        if not isinstance(attempt, Mapping):
            continue
        backend, model, effort = (
            attempt.get("backend"),
            attempt.get("model"),
            attempt.get("effort"),
        )
        if all(isinstance(value, str) and value for value in (backend, model, effort)):
            return backend, model, effort
    return None


def _worker_selection_value(worker: Mapping[str, Any], key: str) -> str | None:
    value = worker.get(key)
    return value if isinstance(value, str) and value else None


def _effective_selection(
    worker: Mapping[str, Any],
    packets: PromptConfig,
    *,
    backend: str | None,
    model: str | None,
    effort: str | None,
) -> tuple[str, str, str]:
    """Resolve one validated selection for both dispatch and the manifest."""
    recorded = _latest_attempt_selection(worker)
    previous_backend = (
        recorded[0] if recorded else _worker_selection_value(worker, "backend")
    )
    previous_model = (
        recorded[1] if recorded else _worker_selection_value(worker, "model")
    )
    previous_effort = (
        recorded[2] if recorded else _worker_selection_value(worker, "effort")
    )
    effective_backend = backend or previous_backend or packets.default_backend
    effective_model = packets.resolve_model(
        effective_backend, model or previous_model or packets.default_model
    )
    effective_effort = validate_effort(
        effort or previous_effort or packets.default_effort
    )
    return effective_backend, effective_model, effective_effort


def _attempt(
    *,
    task_id: int,
    task_reference: Any,
    prompt_path: Path,
    result_path: Path,
    backend: str,
    model: str,
    effort: str,
    number: int,
) -> dict[str, Any]:
    """The immutable facts agentctl knows for one worker launch."""
    return {
        "number": number,
        "task_id": task_id,
        "task_reference": task_reference,
        "prompt_path": str(prompt_path),
        "result_path": str(result_path),
        "backend": backend,
        "model": model,
        "effort": effort,
    }


def _bead_revisions(beads: Sequence[Mapping[str, Any]]) -> dict[str, str | None]:
    """The exact revisions embedded in this worker's prompt snapshot."""
    revisions: dict[str, str | None] = {}
    for bead in beads:
        bead_id = bead.get("id")
        binding = bead.get("evidence_binding")
        if not isinstance(bead_id, str) or not bead_id:
            continue
        value = binding.get("bead_revision") if isinstance(binding, Mapping) else None
        revisions[bead_id] = value if isinstance(value, str) and value else None
    return revisions


def _evidence_binding(beads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The v2 facts copied into the dispatch packet, retained with its worker."""
    records: list[dict[str, Any]] = []
    for bead in beads:
        binding = bead.get("evidence_binding")
        if not isinstance(binding, Mapping):
            continue
        records.append(
            {
                "id": bead.get("id"),
                "v2_available": binding.get("v2_available") is True,
                "bead_revision": binding.get("bead_revision"),
                "criteria": list(binding.get("criteria") or ()),
            }
        )
    return records


def _v2_binding_errors(worker: Mapping[str, Any], value: Mapping[str, Any]) -> list[str]:
    """A v2 claim must copy stable owner facts from this worker's launch."""
    if value.get("schema_version") != results.RESULT_SCHEMA_VERSION:
        return []
    records = worker.get("evidence_binding")
    if not isinstance(records, list):
        return ["v2 result has no dispatch-time stable acceptance binding"]
    expected = {
        row.get("id"): row
        for row in records
        if isinstance(row, Mapping)
        and isinstance(row.get("id"), str)
        and row.get("v2_available") is True
    }
    if set(expected) != set(worker.get("beads") or ()):
        return ["v2 result requires Beads-authored stable acceptance IDs and revisions"]
    submitted = {
        row.get("id"): row
        for row in value.get("beads") or ()
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    }
    if set(submitted) != set(expected):
        return ["v2 result beads do not match the dispatch binding"]
    errors: list[str] = []
    for bead_id, expected_bead in expected.items():
        actual = submitted[bead_id]
        if actual.get("bead_revision") != expected_bead.get("bead_revision"):
            errors.append(f"v2 result {bead_id} bead_revision differs from dispatch")
        expected_criteria = {
            (criterion.get("ac_id"), criterion.get("text"))
            for criterion in expected_bead.get("criteria") or ()
            if isinstance(criterion, Mapping)
        }
        actual_criteria = {
            (criterion.get("ac_id"), criterion.get("text"))
            for criterion in actual.get("criteria") or ()
            if isinstance(criterion, Mapping)
        }
        if actual_criteria != expected_criteria:
            errors.append(f"v2 result {bead_id} criteria differ from dispatch")
    return errors


def result_provenance(
    run: Run, worker: Mapping[str, Any], value: Mapping[str, Any]
) -> dict[str, Any]:
    """One consumer projection: requested dispatch vs untrusted worker claims.

    The runner currently stores only a structured worker result, not a signed
    backend receipt, so executor identity, usage and sessions are never
    promoted from that result into an observed fact.
    """
    attempts = (
        worker.get("attempts") if isinstance(worker.get("attempts"), list) else []
    )
    latest = attempts[-1] if attempts and isinstance(attempts[-1], Mapping) else {}
    worker_claim = {
        key: value.get(key)
        for key in (
            "planned_model",
            "actual_executor_model",
            "actual_executor_observed_by",
            "measured_usage",
            "parent_session_ref",
            "child_session_ref",
            "model_segments",
        )
        if key in value
    }
    return {
        "schema_version": 1,
        "dispatch": {
            "execution": run.harness,
            "requested": {
                key: latest.get(key) for key in ("backend", "model", "effort")
            },
            "attempt": latest.get("number"),
            "task_id": latest.get("task_id"),
            "launch_reference": latest.get("task_reference"),
        },
        "bead_revisions": dict(worker.get("bead_revisions") or {}),
        "result_schema_version": value.get("schema_version"),
        "worker_claim": worker_claim or None,
        "observed_executor": None,
        "actual_executor_model": None,
        "measured_usage": None,
        "session_correlation": None,
    }


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
    ensure_landing_groups(project.project_id)
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
                    "focused_verification": focused_verification(config, project, path),
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
                write_scope=list(snapshot.write_scope),
                scope_authority=list(scope_authority(snapshot.beads)),
                bead_revisions=_bead_revisions(snapshot.beads),
                evidence_binding=_evidence_binding(snapshot.beads),
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
                inaccessible=other_worktrees(project, run, worker_id),
            )
            run = set_worker(
                config,
                run.run_id,
                index,
                task_id=job["job_id"],
                task_reference=job.get("reference"),
                attempts=[
                    _attempt(
                        task_id=job["job_id"],
                        task_reference=job.get("reference"),
                        prompt_path=path / WORKTREE_STATE_DIR / "prompt.md",
                        result_path=result_path(path),
                        backend=worker["backend"],
                        model=worker["model"],
                        effort=worker["effort"],
                        number=1,
                    )
                ],
            )
    if run.landing.get("task_id") is None:
        after = [
            worker["task_id"]
            for worker in run.workers
            if worker.get("task_id") is not None
        ]
        landing_id = queue_landing(
            config, project, run, after=after, stashed=run.harness == "external"
        )
        landing_task = pueue.task(landing_id)
        run = land_update(
            config,
            run.run_id,
            task_id=landing_id,
            task_reference=launch.launch_reference(landing_task)
            if landing_task is not None
            else None,
            # Only the external harness starts its landing stashed for result
            # filing. A normal queued landing can later be stashed by an
            # operator, which is not ours to release.
            waiting_for_results=run.harness == "external",
        )

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
        # By branch, not by the recorded worktree: provisioning that failed
        # between `wt` creating one and the manifest recording it would
        # otherwise leave the worktree behind with nothing naming it.
        try:
            if worktrunk.worktrunk_find(project.root, worker["branch"]) is not None:
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


def _scope_check(
    run: Run, worker: Mapping[str, Any], candidate: str, reader: BdReader
) -> dict[str, Any]:
    """The candidate's changed paths against the worker's declared write scope."""
    worktree = worker.get("worktree")
    if not worktree:
        return {}
    changed = gitcmd.git(
        Path(worktree),
        "diff",
        "--name-only",
        f"{run.base_commit}..{candidate}",
        error=BatchError,
    ).splitlines()
    stored_scope = worker.get("write_scope")
    globs = list(stored_scope) if isinstance(stored_scope, list) else []
    if not globs:
        for bead_id in worker["beads"]:
            try:
                globs.extend(write_scope(reader.show(bead_id)))
            except PromptError:
                continue
    if not globs:
        return {"scope": "undeclared", "changed_paths": changed}
    # The declared scope is a planning estimate, never a fence: a fix's real
    # footprint is known only once it exists. Paths outside it are recorded
    # for the reviewer; the landing merge is what detects a real conflict.
    outside = scope_violations(changed, globs)
    return {
        "scope": "declared",
        "changed_paths": changed,
        "write_scope": globs,
        "outside_scope": outside,
        "scope_authority": worker.get("scope_authority", []),
    }


def correct_scope(
    config: Config,
    run_id: str,
    worker_id: str,
    candidate: str,
    authorizations: Sequence[str],
) -> dict[str, Any]:
    """Record a coordinator-authorized scope correction for an existing worker."""
    run = load(config, run_id)
    worker = run.worker(worker_id)
    worktree = Path(str(worker.get("worktree") or ""))
    head = gitcmd.git(worktree, "rev-parse", "HEAD", error=BatchError)
    if candidate != head:
        raise BatchRefusal(
            "candidate_mismatch",
            f"scope correction names {candidate[:12]} but {worktree} is at {head[:12]}",
        )
    assigned = set(worker["beads"])
    parsed: dict[str, set[str]] = {}
    for item in authorizations:
        bead_id, separator, glob = item.partition("=")
        if not separator or bead_id not in assigned or not glob:
            raise BatchRefusal("members", f"invalid scope authorization {item!r}")
        parsed.setdefault(glob, set()).add(bead_id)
    authority = [
        {"glob": glob, "beads": sorted(parsed[glob])} for glob in sorted(parsed)
    ]
    corrected = [row["glob"] for row in authority]

    def record(document: dict[str, Any]) -> None:
        for entry in document["workers"]:
            if entry["id"] != worker_id:
                continue
            history = list(entry.get("scope_corrections") or [])
            history.append(
                {
                    "at": now(),
                    "candidate_sha": candidate,
                    "old_scope": list(entry.get("write_scope") or []),
                    "corrected_scope": corrected,
                    "authority": authority,
                }
            )
            entry["write_scope"] = corrected
            entry["scope_authority"] = authority
            entry["scope_corrections"] = history

    return update(config, run_id, record).worker(worker_id)


def _rebind_candidate(worktree: Path, *, filed: str, head: str) -> str:
    dirty = gitcmd.git(worktree, "status", "--porcelain", error=BatchError).strip()
    if dirty:
        raise BatchRefusal(
            "candidate_mismatch",
            f"result names {filed[:12]} but {worktree} is at {head[:12]} with uncommitted changes",
        )
    try:
        gitcmd.git(
            worktree, "merge-base", "--is-ancestor", filed, head, error=BatchError
        )
    except BatchError as error:
        raise BatchRefusal(
            "candidate_mismatch",
            f"result names {filed[:12]} but {worktree} is at {head[:12]}, which does not descend from it",
        ) from error
    return head


def result(
    config: Config,
    run_id: str,
    worker_id: str,
    path: Path,
    *,
    project: ProjectAdapter | None = None,
    reader: BdReader | None = None,
) -> dict[str, Any]:
    """File a worker's result after validating it and binding it to the worktree head."""
    run = load(config, run_id)
    if run.abandoned is not None:
        raise BatchRefusal("abandoned", f"run {run_id} was abandoned")
    worker = run.worker(worker_id)
    value, errors = results.load_result(path, kind="worker")
    if errors:
        raise BatchRefusal("invalid_result", "; ".join(errors[:6]), errors=errors)
    binding_errors = _v2_binding_errors(worker, value)
    if binding_errors:
        raise BatchRefusal(
            "result_evidence_binding",
            "; ".join(binding_errors),
            errors=binding_errors,
        )
    worktree = worker.get("worktree")
    if worktree:
        head = gitcmd.git(Path(worktree), "rev-parse", "HEAD", error=BatchError)
        if head != value["candidate_sha"]:
            # A worker that committed once more after writing its result is
            # still the same worker: take the head when the tree is clean and
            # the head descends from what was filed.
            value["candidate_sha"] = _rebind_candidate(
                Path(worktree), filed=value["candidate_sha"], head=head
            )
    if value["candidate_sha"] == run.base_commit:
        verdicts = results.satisfied_beads([value])
        # Nothing was committed. When every criterion holds, the wanted state
        # already did and the evidence is the deliverable; otherwise the worker
        # ends without work to land. Either way the result is the record, and
        # the run lands its remaining workers.
        value["kind"] = (
            "verified"
            if all(verdicts.get(bead_id) for bead_id in worker["beads"])
            else "no_op"
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
    if reader is None:
        if project is None:
            raise BatchError("batch result needs the project to read write scopes")
        reader = SubprocessBeads(project.root)
    scope = _scope_check(run, worker, value["candidate_sha"], reader)

    def record(document: dict[str, Any]) -> None:
        for entry in document["workers"]:
            if entry["id"] == worker_id:
                entry["result"] = value
                entry["provenance"] = result_provenance(run, entry, value)
                entry["result_path"] = str(path)
                entry["result_recorded_at"] = now()
                entry.update(scope)

    run = update(config, run_id, record)
    released = False
    lost: int | None = None
    requeued: int | None = None
    requeue_error: str | None = None
    # The manifest update above makes this result durable. The recovery itself
    # needs one broader lock: concurrent final results otherwise both read the
    # lost landing, then each enqueue a replacement and race to relink it.
    # Reload after acquiring it so a waiter acts on every result and relink
    # made by the process ahead of it.
    with landing_recovery_locked(config, run_id):
        run = load(config, run_id)
        landing_id = run.landing.get("task_id")
        reference = run.landing.get("task_reference")
        if run.live and isinstance(landing_id, int):
            try:
                tasks = pueue.tasks()
            except PueueError as error:
                # The result record is already durable. A temporary unreadable
                # queue is not proof that the landing vanished, and must not
                # turn a successful result filing into a failed command.
                requeue_error = str(error)
                tasks = None
            if tasks is None:
                return {
                    **run.worker(worker_id),
                    "landing_task": landing_id,
                    "landing_released": released,
                    "landing_vanished": lost,
                    "landing_requeued": requeued,
                    "landing_requeue_error": requeue_error,
                }
            task = launch.find_task(tasks, landing_id, reference)
            if task is None:
                # The queue lost the landing task with its state. Nothing else
                # would queue another, and the manifest would keep naming a task
                # id that resolves to nothing, so the run would wait forever.
                lost = landing_id
                if project is not None:
                    try:
                        run, requeued = requeue_landing(config, project, run, tasks)
                    except (PueueError, JobError) as error:
                        # Filing the result is this verb's work; a recovery that
                        # the queue refuses is reported, never raised over it.
                        requeue_error = str(error)
            elif (
                task.status == "Stashed"
                and all(item.get("result") for item in run.workers)
                and (
                    run.landing.get("waiting_for_results") is True
                    # Old external manifests used the same protocol before
                    # ownership was recorded. Do not infer it for queued
                    # landings: their stash may be an operator's.
                    or (
                        run.harness == "external"
                        and "waiting_for_results" not in run.landing
                    )
                )
            ):
                # This is an agentctl-marked result wait, not an arbitrary
                # pueue stash. Clear the marker after enqueueing so a later
                # operator restash cannot be released by a repeated filing.
                pueue.enqueue(task.task_id)
                released = True
                run = land_update(
                    config, run_id, waiting_for_results=False
                )
    return {
        **run.worker(worker_id),
        "landing_task": run.landing.get("task_id"),
        "landing_released": released,
        "landing_vanished": lost,
        "landing_requeued": requeued,
        "landing_requeue_error": requeue_error,
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
    current = launch.find_task(
        tasks, worker.get("task_id"), worker.get("task_reference")
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
    prompt_name = f"resume-{attempt}.md"
    effective_backend, effective_model, effective_effort = _effective_selection(
        worker,
        packets,
        backend=backend,
        model=model,
        effort=effort,
    )
    job = queue_agent(
        config,
        project,
        label=f"{project.project_id}:resume:{run_id}:{worker_id}",
        worktree=path,
        prompt=prompt,
        prompt_name=prompt_name,
        backend=effective_backend,
        model=effective_model,
        effort=effective_effort,
        schema="worker",
        then=worker_then(config, run_id, worker_id, resume_result),
        binding={
            **binding(run, worker_id),
            "requested": {
                "backend": effective_backend,
                "model": effective_model,
                "effort": effective_effort,
            },
            "attempt": attempt,
        },
        inaccessible=other_worktrees(project, run, worker_id),
    )
    task_id = job["job_id"]

    def record(document: dict[str, Any]) -> None:
        for entry in document["workers"]:
            if entry["id"] == worker_id:
                entry["task_id"] = task_id
                entry["task_ids"] = [*entry.get("task_ids", []), task_id]
                entry["task_reference"] = job.get("reference")
                entry["backend"] = effective_backend
                entry["model"] = effective_model
                entry["effort"] = effective_effort
                entry["result"] = None
                entry["result_path"] = str(resume_result)
                prompt_path = path / WORKTREE_STATE_DIR / prompt_name
                entry["prompt_path"] = str(prompt_path)
                entry["attempts"] = [
                    *(
                        entry.get("attempts")
                        if isinstance(entry.get("attempts"), list)
                        else []
                    ),
                    _attempt(
                        task_id=task_id,
                        task_reference=job.get("reference"),
                        prompt_path=prompt_path,
                        result_path=resume_result,
                        backend=effective_backend,
                        model=effective_model,
                        effort=effective_effort,
                        number=attempt,
                    ),
                ]
        document["landing"]["failure"] = None

    run = update(config, run_id, record)
    landing_id = run.landing.get("task_id")
    if run.harness == "queued":
        # A landing task waits on the worker tasks it was queued behind; the
        # new worker task is not among them, so any landing that has not
        # started is replaced by one queued behind every current worker task.
        old = launch.find_task(tasks, landing_id, run.landing.get("task_reference"))
        replace = old is None or old.status != "Running"
        if old is not None and replace:
            pueue.remove([old.task_id])
        if replace:
            current_tasks = pueue.tasks()
            after = [
                task.task_id
                for item in run.workers
                if (
                    task := launch.find_task(
                        current_tasks,
                        item.get("task_id"),
                        item.get("task_reference"),
                    )
                )
                is not None
            ]
            new_landing = queue_landing(
                config, project, run, after=after, stashed=False
            )

            def relink(document: dict[str, Any]) -> None:
                document["landing"]["task_id"] = new_landing
                task = pueue.task(new_landing)
                document["landing"]["task_reference"] = (
                    launch.launch_reference(task) if task is not None else None
                )
                document["landing"]["waiting_for_results"] = False

            run = update(config, run_id, relink)
    return {**run.to_dict(), "job": job, "worker": worker_id}
