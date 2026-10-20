"""Job mutations: admission, enqueue, cancellation, retry and queue cleanup.

Pueue and systemd own execution state; artifacts owns invocation storage.
Stable-identity reads and bounded artifact projections belong to job_queries.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import re
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence, TextIO

from . import artifacts, gitcmd, job_queries, manifest, pools, pueue
from .config import Config
from .launch_input import scratch_path, write_input
from .limits import CALL_TIMEOUT_SECONDS, SHORT_ID, SYSTEMCTL_TIMEOUT_SECONDS
from .projects import AdmissionEnvelope, ProjectAdapter, ProjectOperation
from .pueue import PueueError, PueueGroupError, Task
from .run import (
    Outcome,
    append_event,
    cancel_marker_for,
    systemd_environment,
)

# A stashed task written by AgentCTL's admission policy carries this marker.
HOLD_REASON = "pool-exclusivity"
LAUNCHER_POOL_VARIABLE = "AGENTCTL_POOL"
ADMISSION_LOCK_NAME = "admission.lock"
ADMISSION_LOCK_SECONDS = 60.0
ADMISSION_LOCK_POLL_SECONDS = 0.05
# How long a cancel waits for the wrapper to record `cancelled` after its
# unit is stopped before pueue kills the wrapper outright.
CANCEL_SETTLE_SECONDS = 15.0
CANCEL_POLL_SECONDS = 0.5


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


def _matching_task(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    working_directory: Path,
    tree_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, str],
) -> Task | None:
    label = label_for(project.project_id, operation.name)
    for task in sorted(pueue.tasks().values(), key=lambda item: item.task_id):
        if task.label != label:
            continue
        launch_input = job_queries.read_launch_input(config, task)
        if launch_input is None:
            continue
        if (
            launch_input.get("working_directory") != str(working_directory)
            or launch_input.get("tree_receipt") != dict(tree_receipt)
            or launch_input.get("environment_receipt") != dict(environment_receipt)
        ):
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
    return None


def successful_cached_attempt(
    config: Config,
    task: Task,
    tree_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, str] | None,
) -> dict[str, Any] | None:
    """Resolve a successful task only when its pinned execution matches its key.

    The enqueue-time tree and environment describe what was requested. The
    attempt receipt describes what the wrapper observed around execution; both
    must agree before a terminal task can satisfy a cached request.
    """
    if not task.terminal or not task.succeeded:
        return None
    launch_path = job_queries.launch_input_path(task)
    launch_input = job_queries.read_launch_input(config, task)
    if (
        launch_path is None
        or launch_input is None
        or (
            environment_receipt is not None
            and (
                launch_input.get("tree_receipt") != dict(tree_receipt)
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
            and observation.get("head") == tree_receipt.get("head")
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
) -> dict[str, Any]:
    """Write the launch input, add the pueue task, return the job view.

    ``binding`` is what the caller ties the task to (``beads``, ``run_id``);
    it is stored as written and read back on ``job get``. ``scratch`` names
    the tier of the job-owned directory the wrapper creates and removes.
    """
    job_id = job_id or _new_job_id(label)
    if not job_queries.JOB_ID.fullmatch(job_id):
        raise job_queries.JobError(f"invalid job id: {job_id!r}")
    log_path = config.jobs_dir / f"{job_id}.log"
    environment = dict(environment)
    if config.config_path is not None:
        # A queued task calls agentctl again (`batch result`, `batch land`);
        # without the config it read the default one and answers about another
        # state directory.
        environment["AGENTCTL_CONFIG"] = str(config.config_path)
    launch: dict[str, Any] = {
        "job_id": job_id,
        "project_id": project.project_id,
        "project_root": str(project.root),
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
    with admission_lock(config):
        hold = None if stashed else _admission_hold(config, group, label=label)
        if hold is not None:
            launch["hold"] = hold
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
                stashed=stashed or hold is not None,
            )
        except PueueGroupError:
            if not (idempotency_key is not None and after):
                input_path.unlink(missing_ok=True)
            raise
        except PueueError as error:
            raise EnqueueUncertain(job_id, error) from error
        # Keep queue acknowledgement and the hold marker in the same admission
        # transaction. A release between add and this write could enqueue a
        # task while the stale local launch value restores its consumed hold.
        launch["queue_task_id"] = task_id
        write_input(input_path, launch)
        if hold is not None:
            append_event(
                config.event_spool,
                {"kind": "pool-hold", "action": "held", "task_id": task_id, **hold},
            )
    task = pueue.task(task_id)
    return (
        job_queries.job_view(task)
        if task is not None
        else {"task_id": task_id, "label": label, "job_id": job_id}
    )


@contextmanager
def admission_lock(config: Config) -> Iterator[None]:
    """Serialize the queue observation and enqueue that admission depends on."""
    path = config.state_dir / ADMISSION_LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + ADMISSION_LOCK_SECONDS
    with path.open("a", encoding="utf-8") as handle:
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise job_queries.JobError(
                        f"another launch has held {path} for over 60s"
                    ) from error
                time.sleep(ADMISSION_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _admission_hold(config: Config, group: str, *, label: str) -> dict[str, Any] | None:
    partners = pools.exclusive_partners(config.pools, group)
    if not partners:
        return None
    launcher = os.environ.get(LAUNCHER_POOL_VARIABLE)
    if launcher in partners:
        raise job_queries.JobError(
            f"{label} runs in pool {group!r}, which excludes its launcher {launcher!r}"
        )
    blocking = pools.blocking_tasks(config.pools, group, pueue.live().tasks)
    if not blocking:
        return None
    return {
        "reason": HOLD_REASON,
        "pool": group,
        "excluded_by": list(partners),
        "waiting_for": list(blocking),
        "held_at": manifest.now(),
    }


def _hold_of(config: Config, task: Task) -> dict[str, Any] | None:
    if task.status != "Stashed":
        return None
    value = job_queries.read_launch_input(config, task)
    hold = value.get("hold") if value else None
    if (
        not isinstance(hold, Mapping)
        or hold.get("reason") != HOLD_REASON
        or hold.get("pool") != task.group
        or value.get("job_id") != job_queries.job_id_of(task)
        or value.get("pool") != task.group
    ):
        return None
    return dict(hold)


def _consume_hold(config: Config, task: Task, expected: Mapping[str, Any]) -> bool:
    """Clear the exact admission intent after its queued task was released.

    The launch input outlives queue transitions. Leaving the marker there would
    make a later operator stash look like an unresolved AgentCTL hold.
    """
    path = job_queries.launch_input_path(task)
    value = job_queries.read_launch_input(config, task)
    if (
        path is None
        or value is None
        or value.get("job_id") != job_queries.job_id_of(task)
        or value.get("pool") != task.group
        or value.get("hold") != dict(expected)
    ):
        return False
    updated = dict(value)
    updated.pop("hold", None)
    updated["queue_task_id"] = task.task_id
    write_input(path, updated)
    return True


def release_holds(config: Config) -> dict[str, list[dict[str, Any]]]:
    """Release only AgentCTL-created cross-pool holds whose partners drained."""
    try:
        with admission_lock(config):
            tasks = pueue.live().tasks
            held = {
                task.task_id: hold
                for task in tasks.values()
                if (hold := _hold_of(config, task)) is not None
            }
            released: list[dict[str, Any]] = []
            waiting: list[dict[str, Any]] = []
            for task_id in sorted(held):
                task = tasks[task_id]
                blockers = pools.blocking_tasks(
                    config.pools,
                    task.group,
                    tasks,
                    task_id=task_id,
                    held=frozenset(held),
                )
                row = {
                    "task_id": task_id,
                    "label": task.label,
                    "pool": task.group,
                    "excluded_by": list(
                        pools.exclusive_partners(config.pools, task.group)
                    ),
                    "waiting_for": list(blockers),
                }
                if blockers:
                    waiting.append(row)
                    continue
                pueue.enqueue(task_id)
                _consume_hold(config, task, held[task_id])
                released.append(row)
                append_event(
                    config.event_spool,
                    {"kind": "pool-hold", "action": "released", **row},
                )
            return {"released": released, "waiting": waiting}
    except (job_queries.JobError, PueueError) as error:
        return {"released": [], "waiting": [{"error": str(error)}]}


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
    task = job_queries.find_task(
        pueue.tasks(), document.get("queue_task_id", -1), job_id
    )
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
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Launch an operation; an idempotency key makes a repeated launch return the same job."""
    if idempotency_key is None:
        return _start_operation(
            config,
            project,
            operation,
            workspace=workspace,
            extra_argv=extra_argv,
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
            idempotency_key=idempotency_key,
            request_digest=fingerprint,
        )


def _working_directory(
    project: ProjectAdapter, operation: ProjectOperation, workspace: Path | None
) -> Path:
    """The tree this operation runs in.

    `any` takes the caller's tree. `default` refuses every tree but the
    project root; it selects nothing, so a caller that passes no workspace
    still lands in whatever state that checkout is in.
    """
    working_directory = (workspace or project.root).resolve()
    if operation.checkout == "default" and working_directory != project.root:
        raise job_queries.JobError(
            f"{project.project_id}.{operation.name} runs only on the project's main checkout"
        )
    return working_directory


def _start_operation(
    config: Config,
    project: ProjectAdapter,
    operation: ProjectOperation,
    *,
    workspace: Path | None,
    extra_argv: Sequence[str],
    idempotency_key: str | None = None,
    request_digest: str | None = None,
) -> dict[str, Any]:
    working_directory = _working_directory(project, operation, workspace)
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
    environment = project.environment.values(host_values=config.inherited_environment)
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
            existing = _matching_task(
                config,
                project,
                operation,
                working_directory,
                tree_receipt,
                environment_receipt,
            )
            if existing is not None:
                existing_input = job_queries.read_launch_input(config, existing) or {}
                return {
                    **job_queries.job_view(existing),
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
        job_id=job_id,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
        tree_receipt=tree_receipt,
        environment_receipt=environment_receipt,
    )
    if tree_receipt is not None:
        started["tree_receipt"] = tree_receipt
    if environment_receipt is not None:
        started["environment_receipt"] = environment_receipt
    return started


def active_tasks(project: ProjectAdapter, operation: ProjectOperation) -> list[int]:
    """Unfinished tasks of this operation; `job start --if-idle` skips while any exist."""
    label = label_for(project.project_id, operation.name)
    return [
        task.task_id
        for task in pueue.tasks().values()
        if task.label == label and not task.terminal
    ]


# A not-started cancellation is a launch-input disposition, never an attempt
# outcome file: writing the compatibility outcome path would look like a
# started attempt and could clobber a previous successful retry's alias.
NOT_STARTED_CANCEL = {"outcome": Outcome.CANCELLED.value, "started": False}


def _write_disposition(
    config: Config, task: Task, disposition: Mapping[str, Any]
) -> None:
    path = job_queries.launch_input_path(task)
    if path is None or not job_queries.owns_path(config, task, path):
        raise job_queries.JobError("cannot record cancellation disposition")
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.with_name(path.name + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        write_input(job_queries.disposition_path(path), dict(disposition))


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
    settle_seconds: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Optionally compare an attempt token while holding its allocation lock."""
    actor = actor if actor is not None else pwd.getpwuid(os.getuid()).pw_name
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 256:
        raise job_queries.JobError(
            "cancellation actor must be nonempty and at most 256 characters"
        )
    if reason is not None and (not isinstance(reason, str) or len(reason) > 4096):
        raise job_queries.JobError(
            "cancellation reason must be at most 4096 characters"
        )
    request = {
        "actor": actor.strip(),
        "uid": os.getuid(),
        "reason": reason,
        "requested_at": datetime.now(UTC).isoformat(),
    }
    if expected_attempt is None:
        return _cancel(
            config,
            task_id,
            job_id=job_id,
            settle_seconds=settle_seconds,
            sleep=sleep,
            cancellation=request,
        )
    if job_id is None:
        raise job_queries.JobError("expected_attempt requires a stable job id")
    task = job_queries.addressed(task_id, job_id)
    document = job_queries.read_launch_input(config, task) or {}
    log = document.get("log_path")
    if not log or not job_queries.owns_path(config, task, Path(log)):
        raise job_queries.JobError("cannot verify the job's execution attempt")
    root = artifacts.root_for(Path(log))
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".allocation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = job_queries.artifact_view(config, task)["attempt"]
        if current != expected_attempt:
            raise job_queries.JobError(
                f"execution attempt changed: expected {expected_attempt}, found {current}"
            )
        return _cancel(
            config,
            task.task_id,
            job_id=job_id,
            settle_seconds=settle_seconds,
            sleep=sleep,
            allocation_lock=lock,
            expected_attempt=expected_attempt,
            cancellation=request,
        )


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


def _retain_disposition(
    config: Config, task: Task, disposition: Mapping[str, Any], *, owned: bool
) -> None:
    if owned:
        _write_disposition(config, task, disposition)


def _unresolved_cancel(
    view: Mapping[str, Any],
    *,
    unit: str | None,
    disposition: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        **view,
        "phase": "unresolved",
        "started": True,
        "state": "unresolved",
        "unit": unit,
        "disposition": dict(disposition),
    }


def _cancelled_not_started(
    view: Mapping[str, Any], disposition: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        **view,
        "phase": Outcome.CANCELLED.value,
        "terminal": True,
        "started": False,
        "state": "removed",
        "unit": None,
        "removed": [],
        "disposition": dict(disposition),
    }


def _cancel_not_started(
    config: Config,
    task: Task,
    view: Mapping[str, Any],
    *,
    allocation_locked: bool = False,
    cancellation: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Drop a queued launch and retain cancelled/not-started, or give up.

    Returns None only when the queue still holds a started attempt: the
    caller must address that attempt. A started attempt whose queue row is
    already gone is unresolved, never not-started.
    """
    intent = {"cancel_requested": True, "confirmed": False}
    try:
        _write_disposition(config, task, intent)
        owned = True
    except job_queries.JobError:
        owned = False
    document = job_queries.read_launch_input(config, task) or {}
    if owned:
        view = {**view, "cancellation": _record_cancellation(document, 0, cancellation)}
    log = document.get("log_path")
    lock_root = None
    marker = None
    if (
        owned
        and isinstance(log, str)
        and job_queries.owns_path(config, task, Path(log))
    ):
        marker = cancel_marker_for(log)
        marker.parent.mkdir(parents=True, exist_ok=True)
        lock_root = artifacts.root_for(Path(log))
        lock_root.mkdir(parents=True, exist_ok=True)
    lock_handle = None
    if lock_root is not None and not allocation_locked:
        lock_handle = (lock_root / ".allocation.lock").open("a")
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
    try:
        before = job_queries.attempt_count(config, task)
        marker_attempt = None
        if marker is not None:
            records = artifacts.attempts(document)
            latest = records[-1]["attempt"] if records else 0
            marker_attempt = (
                latest
                if latest and job_queries.unfinished_attempt(config, task)
                else latest + 1
            )
            write_input(marker, {"attempt": marker_attempt})
        current = pueue.task(task.task_id)
        if current is not None and current.started_at is not None:
            return None
        if job_queries.unfinished_attempt(
            config, current if current is not None else task
        ):
            if current is not None and current.started_at is not None:
                return None
            unresolved = {
                **intent,
                "unresolved": True,
                "reason": "runner started during cancel",
            }
            target = current if current is not None else task
            _retain_disposition(config, target, unresolved, owned=owned)
            return _unresolved_cancel(
                job_queries.job_view(target) if current is not None else view,
                unit=job_queries.unit_of(target),
                disposition=unresolved,
            )
        if current is not None:
            try:
                pueue.remove([current.task_id])
            except PueueError:
                current = pueue.task(current.task_id)
                if current is not None and (
                    current.started_at is not None
                    or job_queries.unfinished_attempt(config, current)
                ):
                    return None
                if current is not None:
                    unresolved = {
                        **intent,
                        "unresolved": True,
                        "reason": "queue still holds the not-started launch after remove failed",
                    }
                    _retain_disposition(config, current, unresolved, owned=owned)
                    return _unresolved_cancel(
                        job_queries.job_view(current),
                        unit=job_queries.unit_of(current),
                        disposition=unresolved,
                    )
        current = pueue.task(task.task_id)
        started = (
            job_queries.attempt_count(config, task) > before
            or job_queries.unfinished_attempt(config, task)
            or (current is not None and current.started_at is not None)
        )
        if started and current is not None:
            return None
        if started:
            unresolved = {
                **intent,
                "unresolved": True,
                "reason": "runner started during cancel",
            }
            _retain_disposition(config, task, unresolved, owned=owned)
            return _unresolved_cancel(
                view, unit=job_queries.unit_of(task), disposition=unresolved
            )
        if current is not None:
            unresolved = {
                **intent,
                "unresolved": True,
                "reason": "queue still holds the launch after remove",
            }
            _retain_disposition(config, current, unresolved, owned=owned)
            return _unresolved_cancel(
                job_queries.job_view(current),
                unit=job_queries.unit_of(current),
                disposition=unresolved,
            )
        confirmed = dict(NOT_STARTED_CANCEL)
        if marker is not None and marker_attempt is not None:
            try:
                if json.loads(marker.read_text()).get("attempt") == marker_attempt:
                    marker.unlink(missing_ok=True)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                pass
        _retain_disposition(config, task, confirmed, owned=owned)
        return _cancelled_not_started(view, confirmed)
    finally:
        if lock_handle is not None:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)
            lock_handle.close()


def _cancel(
    config: Config,
    task_id: int,
    *,
    job_id: str | None = None,
    settle_seconds: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
    allocation_lock: TextIO | None = None,
    expected_attempt: int | None = None,
    cancellation: Mapping[str, Any],
) -> dict[str, Any]:
    """Make the task not run: drop it while queued, stop its unit while running.

    pueue kills the wrapper with SIGKILL, which stops nothing inside the unit
    and leaves no outcome record, so the unit is stopped first and the
    wrapper is given ``settle_seconds`` to record `cancelled` and exit on its
    own; only a wrapper still running after that is killed. `systemctl stop`
    ends the wrapper's wait with a success status, which is why the cancel
    marker is written before it: the wrapper reports `cancelled` when it
    finds one, and consumes the marker.
    """
    if settle_seconds is None:
        settle_seconds = CANCEL_SETTLE_SECONDS
    task = job_queries.addressed(task_id, job_id)
    task_id = task.task_id
    view = job_queries.job_view(task)
    if task.terminal:
        return {**view, "state": "terminal", "unit": None, "already_terminal": True}
    if task.started_at is None:
        stopped = _cancel_not_started(
            config,
            task,
            view,
            allocation_locked=allocation_lock is not None,
            cancellation=cancellation,
        )
        if stopped is not None:
            return {**stopped, "already_terminal": False}
        live = pueue.task(task_id)
        if live is None:
            raise job_queries.JobError(
                "cancel raced runner start and the queue no longer holds the launch"
            )
        task = live
        view = job_queries.job_view(task)
    unit = job_queries.unit_of(task)
    declared_log = (job_queries.read_launch_input(config, task) or {}).get("log_path")
    log = (
        Path(declared_log)
        if declared_log and job_queries.owns_path(config, task, Path(declared_log))
        else None
    )
    if log is not None:
        marker = cancel_marker_for(log)
        marker.parent.mkdir(parents=True, exist_ok=True)
        root = artifacts.root_for(log)
        root.mkdir(parents=True, exist_ok=True)
        allocation = (root / ".allocation.lock").open("a")
        if allocation_lock is None:
            fcntl.flock(allocation, fcntl.LOCK_EX)
        try:
            records = artifacts.attempts(
                job_queries.read_launch_input(config, task) or {}
            )
            latest = records[-1]["attempt"] if records else 0
            active_attempt = (
                expected_attempt
                if allocation_lock is not None
                else latest
                if latest and job_queries.unfinished_attempt(config, task)
                else latest + 1
            )
            request = _record_cancellation(
                job_queries.read_launch_input(config, task) or {},
                active_attempt,
                cancellation,
            )
            write_input(marker, {"attempt": active_attempt})
            if unit is not None:
                subprocess.run(
                    ["systemctl", "--user", "stop", unit],
                    capture_output=True,
                    check=False,
                    timeout=CALL_TIMEOUT_SECONDS,
                    env=systemd_environment(),
                )
        finally:
            if allocation_lock is None:
                fcntl.flock(allocation, fcntl.LOCK_UN)
            allocation.close()
    elif unit is not None:
        subprocess.run(
            ["systemctl", "--user", "stop", unit],
            capture_output=True,
            check=False,
            timeout=CALL_TIMEOUT_SECONDS,
            env=systemd_environment(),
        )
    # The guard pins selection through publication of the stop request. The
    # wrapper needs the same lock to consume its marker and publish completion.
    if allocation_lock is not None:
        fcntl.flock(allocation_lock, fcntl.LOCK_UN)
    deadline = time.monotonic() + settle_seconds
    current = pueue.task(task_id)
    while current is not None and not current.terminal:
        if time.monotonic() >= deadline:
            try:
                if allocation_lock is None:
                    pueue.kill(task_id)
                else:
                    # A restart may allocate after the request lock is released.
                    # Never escalate an old guarded request onto a newer wrapper.
                    fcntl.flock(allocation_lock, fcntl.LOCK_EX)
                    try:
                        observed = pueue.task(task_id)
                        if job_queries.artifact_view(config, task)[
                            "attempt"
                        ] != expected_attempt or (
                            observed is not None
                            and (
                                job_queries.job_id_of(observed)
                                != job_queries.job_id_of(task)
                                or observed.started_at != task.started_at
                            )
                        ):
                            raise job_queries.JobError(
                                "execution attempt changed while waiting for cancellation"
                            )
                        # A published receipt means finalization has passed the
                        # lock and may exit/restart while pueue acknowledges it.
                        if (
                            observed is not None
                            and not observed.terminal
                            and job_queries.unfinished_attempt(config, task)
                        ):
                            pueue.kill(task_id)
                    finally:
                        fcntl.flock(allocation_lock, fcntl.LOCK_UN)
            except PueueError:
                pass
            current = pueue.task(task_id)
            break
        sleep(CANCEL_POLL_SECONDS)
        current = pueue.task(task_id)
    state = _unit_state(unit) if unit is not None else "stopped"
    return {
        **(job_queries.job_view(current) if current is not None else view),
        "state": state,
        **({"unresolved": True} if state == "unresolved" else {}),
        "unit": unit,
        **job_queries.outcome(
            config, current if current is not None else task, attempt=expected_attempt
        ),
        "already_terminal": False,
        **({"cancellation": request} if log is not None else {}),
    }


def _unlink_all(paths: Sequence[Path]) -> list[str]:
    removed = []
    for path in paths:
        try:
            path.unlink()
            removed.append(str(path))
        except OSError:
            continue
    return removed


def clean(config: Config, task_id: int, job_id: str | None = None) -> dict[str, Any]:
    """Remove a terminal queue entry; retain its launch and execution evidence."""
    if job_id is not None and not job_queries.JOB_ID.fullmatch(job_id):
        raise job_queries.JobError(f"{job_id!r} is not a job id")
    task = job_queries.read_task(config, task_id, job_id)
    if task.status != "Archived" and not task.terminal:
        raise job_queries.JobError(
            f"task {task.task_id} is still {task.status.lower()}; cancel it first"
        )
    view = job_queries.get_job(task.task_id, config, job_queries.job_id_of(task))
    if task.status != "Archived":
        pueue.remove([task.task_id])
    log = job_queries.artifact_path(config, task, ".log")
    removed = _unlink_all([cancel_marker_for(log)]) if log is not None else []
    return {**view, "cleaned": True, "removed": removed, "retained": True}


def _live_run_jobs(config: Config, tasks: Mapping[int, Task]) -> set[int]:
    """Jobs a live batch still needs, including attempts predating stable job ids."""
    runs = [run for run in manifest.list_runs(config, strict=True) if run.live]
    run_ids = {run.run_id for run in runs}
    worktrees: set[str] = set()
    retained: set[int] = set()
    for run in runs:
        records = [*run.workers, run.landing]
        records.extend(
            record
            for key in ("verify_run", "review_verdict")
            if isinstance(record := run.landing.get(key), dict)
        )
        for record in records:
            job_id = record.get("pending_launch") or record.get("job_id")
            task_id = record.get("task_id")
            task = job_queries.find_task(tasks, task_id, job_id)
            if task is not None:
                retained.add(task.task_id)
            retained.update(
                value
                for value in (record.get("task_ids") or [])
                if isinstance(value, int)
            )
            for key in ("worktree", "integration_worktree"):
                if isinstance(path := record.get(key), str):
                    worktrees.add(path)
    for task in tasks.values():
        written = job_queries.read_launch_input(config, task) or {}
        binding = written.get("binding") or {}
        label = task.label.split(":")
        batch_label = (
            len(label) >= 3
            and label[1] in job_queries.AGENT_OPERATIONS | {"land"}
            and label[2] in run_ids
        )
        if task.path in worktrees or binding.get("run_id") in run_ids or batch_label:
            retained.add(task.task_id)
    return retained


def clean_terminal(config: Config) -> list[dict[str, Any]]:
    """Clean terminal wrapper jobs except those still needed by a live batch."""
    tasks = pueue.tasks()
    retained = _live_run_jobs(config, tasks)
    return [
        clean(config, task.task_id, job_queries.job_id_of(task))
        for task in sorted(tasks.values(), key=lambda item: item.task_id)
        if task.terminal
        and task.task_id not in retained
        and job_queries.launch_input_path(task) is not None
    ]


def retry(config: Config, task_id: int, job_id: str | None = None) -> dict[str, Any]:
    """Restart in place, applying the same cross-pool admission as a new launch."""
    with admission_lock(config):
        task = job_queries.addressed(task_id, job_id)
        if not task.terminal:
            raise job_queries.JobError(
                f"task {task.task_id} is still {task.status.lower()}"
            )
        hold = _admission_hold(config, task.group, label=task.label)
        if hold is not None:
            value = job_queries.read_launch_input(config, task)
            path = job_queries.launch_input_path(task)
            if (
                value is None
                or path is None
                or value.get("job_id") != job_queries.job_id_of(task)
            ):
                raise job_queries.JobError(
                    f"task {task.task_id} has no owned launch input for a held retry"
                )
            pueue.restart(task.task_id, stashed=True)
            write_input(path, {**value, "queue_task_id": task.task_id, "hold": hold})
            append_event(
                config.event_spool,
                {
                    "kind": "pool-hold",
                    "action": "held",
                    "task_id": task.task_id,
                    **hold,
                },
            )
        else:
            pueue.restart(task.task_id)
    return job_queries.get_job(task.task_id, config, job_id)
