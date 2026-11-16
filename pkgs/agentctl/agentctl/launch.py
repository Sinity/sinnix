"""Job creation, cancellation, retry and queue cleanup.

Pueue and systemd own execution state; artifacts owns invocation storage.
Job reads belong to job_queries.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import re
import subprocess
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import tomllib
from sinnix_lib.atomic import atomic_publish

from . import artifacts, gitcmd, job_queries, pueue
from .config import Config
from .launch_input import scratch_path, write_input
from .limits import CALL_TIMEOUT_SECONDS, SHORT_ID, SYSTEMCTL_TIMEOUT_SECONDS
from .projects import AdmissionEnvelope, ProjectAdapter, ProjectOperation
from .pueue import PueueError, PueueGroupError, PueueTimeout, Task
from .run import (
    cancel_marker_for,
    systemd_environment,
)

# Give the wrapper time to save output after its unit stops.
CANCEL_FINISH_SECONDS = 15.0


class EnqueueUncertain(job_queries.JobError):
    """Pueue may have accepted a launch whose acknowledgement was lost."""

    def __init__(self, job_id: str, error: PueueError) -> None:
        self.job_id = job_id
        self.error = error
        super().__init__(f"pueue acceptance is unknown for launch {job_id}: {error}")


def label_for(project_id: str, operation: str) -> str:
    return f"{project_id}:{operation}"


def _new_job_id(label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "job"
    return f"{safe}-{uuid.uuid4().hex[:SHORT_ID]}"


def _git(path: Path, *arguments: str) -> str:
    return gitcmd.git(path, *arguments, error=job_queries.JobError)


def _tree_receipt(path: Path) -> dict[str, Any]:
    head = _git(path, "rev-parse", "HEAD")
    tree = _git(path, "rev-parse", "HEAD^{tree}")
    dirty = bool(_git(path, "status", "--porcelain=v1", "--untracked-files=all"))
    return {"head": head, "tree": tree, "dirty": dirty}


def _environment_receipt(
    project: ProjectAdapter,
    operation: ProjectOperation,
    environment: Mapping[str, str],
    extra_argv: Sequence[str] = (),
) -> dict[str, str]:
    payload = {
        "descriptor": project.digest,
        "kind": project.environment.kind,
        "command": list(project.environment.command),
        "cache_inputs": list(project.environment.cache_inputs),
        "operation": operation.name,
        "argv": [*operation.command, *extra_argv],
        "environment": sorted(environment.items()),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {"digest": "sha256:" + hashlib.sha256(encoded).hexdigest()}


def _same_tree(recorded: object, requested: Mapping[str, Any]) -> bool:
    return (
        isinstance(recorded, Mapping)
        and recorded.get("dirty") is False
        and requested.get("dirty") is False
        and isinstance(recorded.get("tree"), str)
        and recorded.get("tree") == requested.get("tree")
    )


def _matching_task(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    tree_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, str],
) -> Task | None:
    # The key is the content tree, not the checkout or the commit: another
    # worktree, or another commit with the same tree, builds the same thing.
    label = label_for(project.project_id, operation.name)
    for task in sorted(pueue.tasks().values(), key=lambda item: item.task_id):
        if task.label != label:
            continue
        launch_input = job_queries.read_launch_input(config, task)
        if launch_input is None:
            continue
        if not _same_tree(
            launch_input.get("tree_receipt"), tree_receipt
        ) or launch_input.get("environment_receipt") != dict(environment_receipt):
            continue
        if not task.terminal:
            return task
        if (
            task.succeeded
            and successful_cached_attempt(
                config, task, tree_receipt, environment_receipt
            )
            is not None
        ):
            return task
    return _retained_match(config, label, tree_receipt, environment_receipt)


def _result_key_path(
    config: Config,
    label: str,
    tree_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, str],
) -> Path:
    key = json.dumps(
        [label, tree_receipt.get("tree"), environment_receipt.get("digest")]
    ).encode()
    return config.state_dir / "results" / hashlib.sha256(key).hexdigest()


def _record_result_key(
    config: Config,
    label: str,
    tree_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, str],
    job_id: str,
) -> None:
    """Point the request key at its newest job, so a later identical request
    finds the job after its queue entry is cleaned."""
    path = _result_key_path(config, label, tree_receipt, environment_receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_publish(path, job_id.encode(), fsync=False, mode=0o600)


def _retained_match(
    config: Config,
    label: str,
    tree_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, str],
) -> Task | None:
    path = _result_key_path(config, label, tree_receipt, environment_receipt)
    raw = job_queries.read_bounded(path, 256)
    job_id = raw.decode("ascii", errors="replace").strip() if raw else ""
    if not job_queries.JOB_ID.fullmatch(job_id):
        return None
    try:
        task = job_queries.read_task(config, -1, job_id)
    except job_queries.JobError:
        return None
    if task.label != label or (task.status != "Archived" and not task.terminal):
        # A live queue entry was already considered by the queue scan.
        return None
    return (
        task
        if successful_cached_attempt(config, task, tree_receipt, environment_receipt)
        is not None
        else None
    )


def successful_cached_attempt(
    config: Config,
    task: Task,
    tree_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, str] | None,
) -> dict[str, Any] | None:
    """Resolve a successful task only when its pinned execution matches its key.

    The enqueue-time tree and environment describe what was requested. The
    attempt receipt describes what the wrapper observed around execution; both
    must agree before a terminal task can satisfy a cached request. A job whose
    queue entry was cleaned is judged by its retained outcome alone.
    """
    archived = task.status == "Archived"
    if not archived and (not task.terminal or not task.succeeded):
        return None
    launch_path = job_queries.launch_input_path(task)
    launch_input = job_queries.read_launch_input(config, task)
    if (
        launch_path is None
        or launch_input is None
        or (
            environment_receipt is not None
            and (
                not _same_tree(launch_input.get("tree_receipt"), tree_receipt)
                or launch_input.get("environment_receipt") != dict(environment_receipt)
            )
        )
    ):
        return None
    expected_environment = hashlib.sha256(
        json.dumps(launch_input.get("environment") or {}, sort_keys=True).encode()
    ).hexdigest()
    attempts = artifacts.attempts(launch_input)
    if not attempts:
        return None
    # Pueue's terminal result describes the last execution. A successful older
    # attempt cannot stand in for a later restart that ran against another tree.
    for attempt in attempts[-1:]:
        if not isinstance(attempt, Mapping):
            return None
        number = attempt.get("attempt")
        artifact_map = attempt.get("artifacts")
        outcome_path = (
            Path(artifact_map["outcome"])
            if isinstance(artifact_map, Mapping)
            and isinstance(artifact_map.get("outcome"), str)
            else None
        )
        if (
            number is None
            or outcome_path is None
            or not job_queries.owns_path(config, task, outcome_path)
        ):
            continue
        # Attempt metadata pins the immutable artifact directory to this exact
        # launch input. A mutable latest alias alone is not execution evidence.
        metadata_path = outcome_path.parent / "attempt.json"
        metadata_raw = job_queries.read_bounded(metadata_path, 16_384)
        try:
            metadata = (
                json.loads(metadata_raw.decode("utf-8")) if metadata_raw else None
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            metadata = None
        if (
            not isinstance(metadata, Mapping)
            or metadata.get("attempt") != number
            or metadata.get("launch_input") != str(launch_path)
        ):
            continue
        outcome = job_queries.read_outcome(outcome_path, job_queries.MAX_OUTCOME_BYTES)
        if not isinstance(outcome, Mapping) or outcome.get("attempt") != number:
            continue
        execution = outcome.get("execution_receipt")
        evidence = outcome.get("execution_evidence")
        if (
            outcome.get("outcome") != "success"
            or not isinstance(execution, Mapping)
            or execution.get("binding") != "unchanged_endpoints"
            or not isinstance(evidence, Mapping)
            or evidence.get("environment_identity") != expected_environment
        ):
            continue
        observations = [execution.get("start"), execution.get("end")]
        if all(
            isinstance(observation, Mapping)
            and observation.get("status") == "observed"
            and observation.get("tree") == tree_receipt.get("tree")
            and observation.get("dirty") is False
            for observation in observations
        ):
            return {**dict(outcome), "attempt": number}
    return None


def enqueue(
    config: Config,
    *,
    project: ProjectAdapter,
    operation: str,
    label: str,
    group: str,
    argv: Sequence[str],
    working_directory: Path,
    timeout_seconds: int,
    result_kind: str,
    environment: Mapping[str, str],
    kind: str = "declared-operation",
    scratch: str = "none",
    admission: AdmissionEnvelope | None = None,
    after: Sequence[int] = (),
    stashed: bool = False,
    unit_properties: Sequence[str] = (),
    tree_receipt: Mapping[str, Any] | None = None,
    environment_receipt: Mapping[str, str] | None = None,
    binding: Mapping[str, Any] | None = None,
    job_id: str | None = None,
    before_enqueue: Callable[[str], None] | None = None,
    idempotency_key: str | None = None,
    request_digest: str | None = None,
    priority: int = 0,
    announce: bool = False,
    deferred: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the launch input, add the pueue task, return the job view.

    ``announce`` records the checkout's commit, so a later caller of an
    announced operation can be told what this one activates. ``deferred``
    (``reason``, ``until``, ``delay_seconds``) adds the task held; pueue
    releases it by itself at ``until``.

    ``binding`` is what the caller ties the task to (the gateway's call
    identity); it is stored as written and read back on ``job get``. ``scratch`` names
    the tier of the job-owned directory the wrapper creates and removes.
    """
    job_id = job_id or _new_job_id(label)
    if not job_queries.JOB_ID.fullmatch(job_id):
        raise job_queries.JobError(f"invalid job id: {job_id!r}")
    log_path = config.jobs_dir / f"{job_id}.log"
    environment = dict(environment)
    if config.config_path is not None:
        # A queued task may call agentctl again; without the config it would
        # read the default one and answer about another state directory.
        environment["AGENTCTL_CONFIG"] = str(config.config_path)
    launch: dict[str, Any] = {
        "job_id": job_id,
        "project_id": project.project_id,
        "project_root": str(project.root),
        "descriptor_path": str(project.descriptor),
        "operation": operation,
        "pool": group,
        "kind": kind,
        "label": label,
        "argv": list(argv),
        "environment": environment,
        "working_directory": str(working_directory),
        "timeout_seconds": timeout_seconds,
        "result_kind": result_kind,
        "log_path": str(log_path),
        "event_spool_path": str(config.event_spool),
        "enqueued_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if caller := caller_from_environment():
        launch["caller"] = caller
    if announce:
        launch["announce"] = True
        if (revision := _revision(working_directory)) is not None:
            launch["revision"] = revision
    if deferred is not None:
        launch["deferred"] = {
            key: deferred[key] for key in ("reason", "until") if deferred.get(key)
        }
    if idempotency_key is not None:
        launch["idempotency_key"] = idempotency_key
        launch["request_digest"] = request_digest
    if unit_properties:
        launch["unit_properties"] = list(unit_properties)
    if admission is not None:
        # The declared envelope, recorded on the job and exported to the
        # command so a workload's own sizing receipt has a declared number to
        # compare its measurement against. It bounds nothing by itself.
        launch["admission"] = admission.catalog_row()
        environment["AGENTCTL_ADMISSION_MEMORY_MIB"] = str(admission.memory_mib)
        launch["environment"] = environment
    if tree_receipt is not None:
        launch["tree_receipt"] = dict(tree_receipt)
    if environment_receipt is not None:
        launch["environment_receipt"] = dict(environment_receipt)
    if binding:
        launch["binding"] = dict(binding)
    scratch_dir = scratch_path(scratch, job_id)
    if scratch_dir is not None:
        launch["scratch"] = {"kind": scratch, "path": str(scratch_dir)}
    if result_kind != "exit":
        launch["result_path"] = str(config.jobs_dir / f"{job_id}.result")
    input_path = config.inputs_dir / f"{job_id}.json"
    write_input(input_path, launch)
    if before_enqueue is not None:
        before_enqueue(job_id)
    try:
        task_id = pueue.add(
            group=group,
            label=label,
            command=(job_queries.QUEUE_RUN_EXECUTABLE, str(input_path)),
            working_directory=working_directory,
            after=after,
            stashed=stashed,
            priority=priority,
            **(
                {"delay_seconds": int(deferred["delay_seconds"])}
                if deferred is not None
                else {}
            ),
        )
    except PueueGroupError:
        if not (idempotency_key is not None and after):
            input_path.unlink(missing_ok=True)
        raise
    except PueueError as error:
        raise EnqueueUncertain(job_id, error) from error
    launch["queue_task_id"] = task_id
    write_input(input_path, launch)
    task = pueue.task(task_id)
    view = (
        job_queries.job_view(task)
        if task is not None
        else {"task_id": task_id, "label": label, "job_id": job_id}
    )
    view.update(job_queries.launch_selection(launch))
    if "deferred" in launch:
        view["deferred"] = launch["deferred"]
    return view


def _revision(path: Path) -> dict[str, Any] | None:
    """The commit a checkout stands on, and whether it has uncommitted changes."""
    try:
        return {
            "commit": _git(path, "rev-parse", "HEAD"),
            "dirty": bool(
                _git(path, "status", "--porcelain=v1", "--untracked-files=no")
            ),
        }
    except job_queries.JobError:
        return None


def announced_jobs(config: Config) -> list[dict[str, Any]]:
    """Unfinished jobs of announced operations: who asked, since when, which commit.

    The queue already runs them one after another. This is what a caller is
    shown when it asks for another one.
    """
    rows = []
    for task in sorted(pueue.tasks().values(), key=lambda task: task.task_id):
        if task.terminal:
            continue
        document = job_queries.read_launch_input(config, task) or {}
        if document.get("announce") is not True:
            continue
        rows.append(
            {
                "task_id": task.task_id,
                "job_id": document.get("job_id"),
                "label": task.label,
                "phase": job_queries.phase_of(task),
                "since": task.started_at
                or document.get("enqueued_at")
                or task.enqueued_at,
                "caller": document.get("caller") or {},
                "revision": document.get("revision"),
                "working_directory": document.get("working_directory"),
            }
        )
    return rows


def announcement_line(row: Mapping[str, Any]) -> str:
    caller = row.get("caller") or {}
    who = (
        f"{caller.get('harness', 'agent')} session {str(caller['session'])[:8]}"
        if caller.get("session")
        else str(caller.get("principal") or "a caller that recorded no session")
    )
    if caller.get("bead"):
        who += f" (task {caller['bead']})"
    revision = row.get("revision") or {}
    commit = (
        f"commit {str(revision['commit'])[:9]}"
        + (" with uncommitted changes" if revision.get("dirty") else "")
        if revision.get("commit")
        else "commit not recorded"
    )
    return (
        f"{row['label']} #{row['task_id']} is {row['phase']} since {row.get('since')}, "
        f"for {who}, {commit}, in {row.get('working_directory')}"
    )


QUOTA_CHECK_TIMEOUT_SECONDS = 60


def discretionary_deferral(config: Config) -> dict[str, Any] | None:
    """Why and until when a discretionary job waits, or None when it may start.

    Asks the configured quota check. A check that is absent, fails or names no
    reset time defers nothing: the job starts and the note says why.
    """
    if not config.quota_check:
        return None
    try:
        result = subprocess.run(
            list(config.quota_check),
            capture_output=True,
            text=True,
            timeout=QUOTA_CHECK_TIMEOUT_SECONDS,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        verdict = json.loads(result.stdout)
        if not isinstance(verdict, dict) or verdict.get("ok") is not False:
            return None
        until = datetime.fromisoformat(str(verdict["resets_at"]))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None
    delay = int((until - datetime.now(UTC)).total_seconds()) + 60
    if delay <= 60:
        return None
    return {
        "reason": str(verdict.get("reason") or "subscription usage above threshold")[
            :240
        ],
        "until": until.astimezone(UTC).isoformat(timespec="seconds"),
        "delay_seconds": delay,
    }


# The harness variables that name the agent session a job was started from.
CALLER_SESSION_VARIABLES = (
    ("claude", "CLAUDE_CODE_SESSION_ID"),
    ("codex", "CODEX_THREAD_ID"),
)


def caller_from_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Who started this job, as far as the launching process can say.

    The operator view reads it to answer "for whom is this running": the agent
    session and, when the launcher exported one, the Bead it works on.
    """
    environ = os.environ if environ is None else environ
    caller: dict[str, str] = {}
    for harness, variable in CALLER_SESSION_VARIABLES:
        if session := environ.get(variable, "").strip():
            caller["harness"] = harness
            caller["session"] = session[:128]
            break
    if bead := environ.get("AGENTCTL_LANE_BEAD", "").strip():
        caller["bead"] = bead[:128]
    if principal := environ.get("AGENTCTL_PRINCIPAL", "").strip():
        caller["principal"] = principal[:128]
    return caller


def _idempotent_job_id(key: str) -> str:
    if not isinstance(key, str) or not key or len(key) > 4096:
        raise job_queries.JobError(
            "idempotency_key must be a nonempty string of at most 4096 characters"
        )
    return "request-" + hashlib.sha256(key.encode()).hexdigest()


def lookup_operation_request(
    config: Config, idempotency_key: str, request_digest: str | None = None
) -> dict[str, Any] | None:
    """Reconcile the idempotency key against retained input and pueue; never submit.

    An input without a queue acknowledgement or execution evidence represents
    an uncertain submission. An absent queue row alone cannot prove rejection.
    """
    job_id = _idempotent_job_id(idempotency_key)
    path = config.inputs_dir / f"{job_id}.json"
    raw = job_queries.read_bounded(path, job_queries.MAX_LAUNCH_INPUT_BYTES)
    if raw is None:
        if path.exists():
            raise job_queries.JobError(f"unreadable idempotent launch {job_id}")
        return None
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise job_queries.JobError(f"invalid idempotent launch {job_id}") from error
    if (
        not isinstance(document, dict)
        or document.get("idempotency_key") != idempotency_key
        or (
            request_digest is not None
            and document.get("request_digest") != request_digest
        )
    ):
        raise job_queries.JobError(f"idempotent launch identity mismatch for {job_id}")
    task_id = document.get("queue_task_id")
    if "queue_task_id" not in document:
        task = next(
            (
                entry
                for entry in pueue.tasks().values()
                if job_queries.job_id_of(entry) == job_id
            ),
            None,
        )
        if task is not None:
            task_id = task.task_id
            document["queue_task_id"] = task_id
            write_input(path, document)
    else:
        task = pueue.task(task_id) if isinstance(task_id, int) else None
    if task is not None and job_queries.job_id_of(task) != job_id:
        raise job_queries.JobError(f"task {task_id} does not match job {job_id}")
    if task is not None:
        return {**job_queries.get_job(task.task_id, config, job_id), "reused": True}
    if document.get("queue_task_id") is not None or artifacts.attempts(document):
        return {
            **job_queries.get_job(document.get("queue_task_id", -1), config, job_id),
            "reused": True,
        }
    raise EnqueueUncertain(
        job_id, PueueError("retained launch has no acknowledged queue task")
    )


def enqueue_request(
    config: Config,
    *,
    idempotency_key: str,
    request_digest: str,
    **arguments: Any,
) -> dict[str, Any]:
    """Submit one keyed job, or read its exact retained launch under the key lock."""
    job_id = _idempotent_job_id(idempotency_key)
    config.inputs_dir.mkdir(parents=True, exist_ok=True)
    with (config.inputs_dir / f"{job_id}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = lookup_operation_request(config, idempotency_key, request_digest)
        if existing is not None:
            return existing
        return enqueue(
            config,
            job_id=job_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            **arguments,
        )


def start_operation(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    *,
    workspace: Path | None = None,
    extra_argv: Sequence[str] = (),
    binding: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
    fresh: bool = False,
    priority: int = 0,
    discretionary: bool = False,
) -> dict[str, Any]:
    """Launch an operation; an idempotency key makes a repeated launch return the same job.

    `fresh` runs a cached operation even when a matching job exists; its
    receipts still serve later requests. `priority` is this job's pueue
    priority: within its pool a higher one starts first. `discretionary` is
    the starter saying this job can wait: it is held while the quota check
    reports the subscription above its threshold. Nothing else is ever held.
    """
    if (pool := default_branch_pool(project, operation.name)) is not None:
        operation = replace(operation, pool=pool)
    if idempotency_key is None:
        return _start_operation(
            config,
            project,
            operation,
            workspace=workspace,
            extra_argv=extra_argv,
            binding=binding,
            fresh=fresh,
            priority=priority,
            discretionary=discretionary,
        )
    job_id = _idempotent_job_id(idempotency_key)
    config.inputs_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "project": project.project_id,
                "operation": operation.name,
                "workspace": str((workspace or project.root).resolve()),
                "extra_argv": list(extra_argv),
                "descriptor": project.digest,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    with (config.inputs_dir / f"{job_id}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = config.inputs_dir / f"{job_id}.json"
        raw = job_queries.read_bounded(path, job_queries.MAX_LAUNCH_INPUT_BYTES)
        if raw is not None:
            try:
                previous = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as error:
                raise job_queries.JobError(
                    f"invalid idempotent launch {job_id}"
                ) from error
            if (
                not isinstance(previous, dict)
                or previous.get("request_digest") != fingerprint
            ):
                raise job_queries.JobError(
                    "idempotency_key was already used for a different launch request"
                )
        existing = lookup_operation_request(config, idempotency_key)
        if existing is not None:
            return existing
        return _start_operation(
            config,
            project,
            operation,
            workspace=workspace,
            extra_argv=extra_argv,
            binding=binding,
            idempotency_key=idempotency_key,
            request_digest=fingerprint,
            priority=priority,
            discretionary=discretionary,
        )


def default_branch_pool(project: ProjectAdapter, operation: str) -> str | None:
    """The pool the project's default branch declares for this operation.

    Pool placement is host scheduling policy, so it follows the merged
    descriptor rather than whatever a lane's branch carried when it was cut;
    the branch keeps defining the command and its arguments. None when the
    base has no descriptor or it does not declare the operation. A descriptor
    without a `[workspace]` table takes `origin/master`.
    """
    base = project.workspace.default_base if project.workspace else "origin/master"
    try:
        raw = gitcmd.git(
            project.root,
            "show",
            f"{base}:.agentctl/project.toml",
            error=job_queries.JobError,
        )
        declared = tomllib.loads(raw)["operations"][operation]["pool"]
    except (job_queries.JobError, tomllib.TOMLDecodeError, KeyError, TypeError):
        return None
    return declared if isinstance(declared, str) else None


def _start_operation(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    *,
    workspace: Path | None,
    extra_argv: Sequence[str],
    binding: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
    request_digest: str | None = None,
    fresh: bool = False,
    priority: int = 0,
    discretionary: bool = False,
) -> dict[str, Any]:
    working_directory = (workspace or project.root).resolve()
    if operation.arguments == "required" and not any(
        argument.strip() for argument in extra_argv
    ):
        raise job_queries.JobError(
            f'{project.project_id}.{operation.name} declares arguments = "required" '
            "but no arguments were supplied"
        )
    if not working_directory.is_dir():
        raise job_queries.JobError(
            f"working directory does not exist: {working_directory}"
        )
    environment = project.environment.values(
        host_values=config.inherited_environment,
        operation_values=dict(operation.environment),
    )
    for key in ("AGENTCTL_PRINCIPAL", "AGENTCTL_LANE_BEAD"):
        if value := os.environ.get(key):
            environment[key] = value
    tree_receipt = None
    environment_receipt = None
    if operation.cache == "tree+environment" and idempotency_key is None:
        tree_receipt = _tree_receipt(working_directory)
        if tree_receipt["dirty"]:
            tree_receipt = None
        else:
            environment_receipt = _environment_receipt(
                project, operation, environment, extra_argv
            )
            existing = (
                None
                if fresh
                else _matching_task(
                    config,
                    project,
                    operation,
                    tree_receipt,
                    environment_receipt,
                )
            )
            if existing is not None:
                existing_input = job_queries.read_launch_input(config, existing) or {}
                return {
                    **job_queries.job_view(existing),
                    **job_queries.launch_selection(existing_input),
                    "reused": True,
                    **{
                        key: existing_input[key]
                        for key in ("tree_receipt", "environment_receipt")
                        if key in existing_input
                    },
                }
    job_id = (
        _idempotent_job_id(idempotency_key)
        if idempotency_key is not None
        else _new_job_id(label_for(project.project_id, operation.name))
    )
    started = enqueue(
        config,
        project=project,
        operation=operation.name,
        label=label_for(project.project_id, operation.name),
        group=operation.pool,
        argv=project.environment.command_for((*operation.command, *extra_argv)),
        working_directory=working_directory,
        timeout_seconds=operation.timeout_seconds,
        result_kind=operation.result,
        environment=environment,
        scratch=operation.scratch,
        admission=operation.admission,
        unit_properties=operation.unit_properties,
        priority=priority,
        job_id=job_id,
        binding=binding,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
        tree_receipt=tree_receipt,
        environment_receipt=environment_receipt,
        announce=operation.announce,
        deferred=discretionary_deferral(config) if discretionary else None,
    )
    if tree_receipt is not None:
        started["tree_receipt"] = tree_receipt
    if environment_receipt is not None:
        started["environment_receipt"] = environment_receipt
    if tree_receipt is not None and environment_receipt is not None:
        _record_result_key(
            config,
            label_for(project.project_id, operation.name),
            tree_receipt,
            environment_receipt,
            started["job_id"],
        )
    return started


def active_tasks(project: ProjectAdapter, operation: ProjectOperation) -> list[int]:
    """Unfinished tasks of this operation; `job start --if-idle` skips while any exist."""
    label = label_for(project.project_id, operation.name)
    return [
        task.task_id
        for task in pueue.tasks().values()
        if task.label == label and not task.terminal
    ]


def _stop_unit(unit: str) -> None:
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "stop", unit],
            capture_output=True,
            check=False,
            timeout=CALL_TIMEOUT_SECONDS,
            env=systemd_environment(),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise job_queries.JobError(f"could not stop {unit}: {error}") from error
    if completed.returncode != 0 and _unit_state(unit) != "stopped":
        raise job_queries.JobError(f"could not stop {unit}")


def _unit_state(unit: str) -> str:
    """Classify the exact service; a failed query leaves cancellation unknown."""
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "show", "-p", "LoadState,ActiveState", unit],
            capture_output=True,
            text=True,
            check=False,
            timeout=SYSTEMCTL_TIMEOUT_SECONDS,
            env=systemd_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unresolved"
    if completed.returncode != 0:
        return "unresolved"
    properties = dict(
        line.partition("=")[::2]
        for line in (completed.stdout or "").splitlines()
        if "=" in line
    )
    if properties.get("LoadState") == "not-found":
        return "stopped"
    if properties.get("LoadState") != "loaded":
        return "unresolved"
    active = properties.get("ActiveState")
    if active in {"inactive", "failed"}:
        return "stopped"
    if active in {"active", "activating", "deactivating", "reloading"}:
        return "failed"
    return "unresolved"


def cancel(
    config: Config,
    task_id: int,
    *,
    job_id: str | None = None,
    expected_attempt: int | None = None,
    actor: str | None = None,
    reason: str | None = None,
    finish_seconds: float = CANCEL_FINISH_SECONDS,
) -> dict[str, Any]:
    """Stop the job's service before removing or killing its queue task."""
    actor = actor if actor is not None else pwd.getpwuid(os.getuid()).pw_name
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 256:
        raise job_queries.JobError(
            "cancellation actor must be nonempty and at most 256 characters"
        )
    if reason is not None and (not isinstance(reason, str) or len(reason) > 4096):
        raise job_queries.JobError(
            "cancellation reason must be at most 4096 characters"
        )
    if expected_attempt is not None and job_id is None:
        raise job_queries.JobError("expected_attempt requires a job id")
    task = job_queries.task_by_id(task_id, job_id)
    job_id = job_id or job_queries.job_id_of(task)
    unit = job_queries.unit_of(task)
    document = job_queries.read_launch_input(config, task) or {}
    log = document.get("log_path")
    if log is not None and not job_queries.owns_path(config, task, Path(log)):
        raise job_queries.JobError("cannot read the job's launch input")
    if log is None and job_id is not None:
        log = str(config.jobs_dir / f"{job_id}.log")
        document = {**document, "log_path": log}
    if log is None:
        if expected_attempt is not None:
            raise job_queries.JobError("cannot verify the job's execution attempt")
        if not task.terminal:
            if task.started_at is None:
                pueue.remove([task_id])
            else:
                pueue.kill(task_id)
        return {
            **job_queries.job_view(pueue.task(task_id) or task),
            "state": "terminal"
            if task.terminal
            else "removed"
            if task.started_at is None
            else "stopped",
            "unit": None,
            "already_terminal": task.terminal,
        }
    root = artifacts.root_for(Path(log))
    root.mkdir(parents=True, exist_ok=True)
    removed = False
    with (root / ".allocation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        task = job_queries.task_by_id(task_id, job_id)
        current = job_queries.artifact_view(config, task)["attempt"]
        if expected_attempt is not None and current != expected_attempt:
            raise job_queries.JobError(
                f"execution attempt changed: expected {expected_attempt}, found {current}"
            )
        if task.terminal:
            if unit is not None:
                _stop_unit(unit)
            return {
                **job_queries.job_view(task),
                "state": "terminal",
                "unit": unit,
                "already_terminal": True,
            }
        unfinished = job_queries.unfinished_attempt(config, task)
        started = task.started_at is not None or unfinished
        number = artifacts.attempt_for_start(document, task.started_at)
        request = _record_cancellation(
            document,
            number if task.started_at is not None else 0,
            {
                "actor": actor.strip(),
                "uid": os.getuid(),
                "reason": reason,
                "requested_at": datetime.now(UTC).isoformat(),
                "started": started,
            },
        )
        write_input(cancel_marker_for(log), {"attempt": number})
        if unit is not None:
            _stop_unit(unit)
        request = _record_cancellation(
            document, request["attempt"], {**request, "stopped": True}
        )
        selected = job_queries.task_by_id(task_id, job_id)
        if not selected.terminal and selected.started_at is None:
            try:
                pueue.remove([task_id])
                removed = True
            except PueueError:
                selected = job_queries.task_by_id(task_id, job_id)
                if not selected.terminal and selected.started_at is None:
                    raise
                if not selected.terminal:
                    pueue.kill(task_id)
        task = selected
    if not removed and not task.terminal:
        try:
            pueue.wait(task_id, timeout_seconds=finish_seconds)
        except PueueTimeout:
            with (root / ".allocation.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                selected = job_queries.task_by_id(task_id, job_id)
                if (
                    job_queries.artifact_view(config, selected)["attempt"] > number
                    or selected.started_at != task.started_at
                ):
                    raise job_queries.JobError(
                        "execution attempt changed during cancellation"
                    ) from None
                if not selected.terminal:
                    if selected.started_at is None:
                        pueue.remove([task_id])
                        removed = True
                    else:
                        pueue.kill(task_id)
    return {
        **job_queries.get_job(task_id, config, job_id),
        "state": "removed" if removed else "stopped",
        "unit": unit,
        "already_terminal": False,
        "cancellation": request,
    }


def _record_cancellation(
    document: Mapping[str, Any], attempt: int, request: Mapping[str, Any]
) -> dict[str, Any]:
    record = {**request, "attempt": attempt}
    try:
        path = artifacts.cancellation_path(Path(document["log_path"]), attempt)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_input(path, record)
    except OSError as error:
        raise job_queries.JobError(
            f"cannot record cancellation requester: {error}"
        ) from error
    return record


def clean(config: Config, task_id: int, job_id: str | None = None) -> dict[str, Any]:
    """Remove a terminal queue entry, keeping its input and output."""
    task = job_queries.read_task(config, task_id, job_id)
    if task.status != "Archived" and not task.terminal:
        raise job_queries.JobError(
            f"task {task_id} is still {task.status.lower()}; cancel it first"
        )
    view = job_queries.get_job(task_id, config, job_queries.job_id_of(task))
    if task.status != "Archived":
        pueue.remove([task_id])
    return {**view, "cleaned": True, "removed": [], "retained": True}


def clean_terminal(
    config: Config, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Remove jobs finished more than 24 hours ago; keep recent task IDs."""
    moment = now or datetime.now(UTC)
    removed = []
    for task in sorted(pueue.tasks().values(), key=lambda item: item.task_id):
        if (
            not task.terminal
            or not task.ended_at
            or job_queries.launch_input_path(task) is None
        ):
            continue
        try:
            ended = datetime.fromisoformat(task.ended_at)
        except ValueError:
            continue
        if ended.tzinfo is None:
            ended = ended.replace(tzinfo=UTC)
        if (moment - ended).total_seconds() > 24 * 60 * 60:
            removed.append(clean(config, task.task_id, job_queries.job_id_of(task)))
    return removed


def retry(config: Config, task_id: int, job_id: str | None = None) -> dict[str, Any]:
    """Restart a terminal task in place, after any cancellation finishes."""
    task = job_queries.task_by_id(task_id, job_id)
    document = job_queries.read_launch_input(config, task) or {}
    log = document.get("log_path")
    if log:
        if not job_queries.owns_path(config, task, Path(log)):
            raise job_queries.JobError("cannot read the job's launch input")
        root = artifacts.root_for(Path(log))
        root.mkdir(parents=True, exist_ok=True)
        with (root / ".allocation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            task = job_queries.task_by_id(task_id, job_id)
            if not task.terminal:
                raise job_queries.JobError(
                    f"task {task_id} is still {task.status.lower()}"
                )
            artifacts.cancellation_path(Path(log), 0).unlink(missing_ok=True)
            pueue.restart(task_id)
    else:
        if not task.terminal:
            raise job_queries.JobError(f"task {task_id} is still {task.status.lower()}")
        pueue.restart(task_id)
    return job_queries.get_job(task_id, config, job_id)
