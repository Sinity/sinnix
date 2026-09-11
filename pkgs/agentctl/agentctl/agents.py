"""Queueing a batch's agents and its landing task."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import launch, pueue, results
from .config import Config
from .limits import MAX_AGENT_TIMEOUT_SECONDS
from .manifest import BatchRefusal, Run, land_update
from .projects import ProjectAdapter, WorkspacePolicy
from .pueue import PueueError

AGENT_GROUP = "agent"
# The pool carrying the agents a landing owns (integration, review). It is
# not the `agent` pool, which backpressure and the operator pause to hold
# back new worker dispatch, and not `<project>-land`, whose single slot the
# landing task itself occupies while it waits.
LANDING_AGENT_GROUP = "land-agent"
# Two, so landings of different projects do not serialize behind each
# other; a landing waits for one agent at a time, so this never deadlocks.
LANDING_AGENT_PARALLELISM = 2
# The directory inside a worktree holding what agentctl writes for its agent:
# the prompt, the result schema and the result. Never committed.
WORKTREE_STATE_DIR = ".agentctl"
# A push or fetch runs the repository's pre-push gate.
PUSH_TIMEOUT_SECONDS = 2_400
# The agent kinds that must not publish or mutate tasks: their environment
# cannot push, has no forwarded credential, and sees a read-only `bd`.
RESTRICTED_KINDS = frozenset({"worker", "resume", "review"})
BD_SHIM = """#!/bin/sh
# agentctl: agents read Beads and never write them.
self=$(dirname "$0")
PATH=$(printf %s "$PATH" | tr ':' '\\n' | grep -vx "$self" | paste -sd:)
export PATH
exec bd --readonly "$@"
"""


def bd_shim_dir(config: Config) -> Path:
    """A directory holding only a `bd` that execs `bd --readonly`."""
    directory = config.state_dir / "shims"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    shim = directory / "bd"
    if not shim.is_file() or shim.read_text() != BD_SHIM:
        descriptor = os.open(
            shim, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o700
        )
        with os.fdopen(descriptor, "w") as handle:
            handle.write(BD_SHIM)
    os.chmod(shim, 0o700)
    return directory


def restrict_environment(config: Config, environment: dict[str, str]) -> None:
    """Take publication and task mutation out of an agent's reach: git cannot
    push, no SSH agent or GitHub token is forwarded, `bd` is read-only."""
    environment.pop("SSH_AUTH_SOCK", None)
    environment["GH_TOKEN"] = ""
    environment["GIT_CONFIG_COUNT"] = "2"
    environment["GIT_CONFIG_KEY_0"] = "remote.origin.pushurl"
    environment["GIT_CONFIG_VALUE_0"] = "/nonexistent"
    environment["GIT_CONFIG_KEY_1"] = "credential.helper"
    environment["GIT_CONFIG_VALUE_1"] = ""
    shim = str(bd_shim_dir(config))
    current = environment.get("PATH", os.defpath)
    environment["PATH"] = f"{shim}{os.pathsep}{current}" if current else shim


def path_properties(
    project: ProjectAdapter, *, inaccessible: Sequence[Path]
) -> tuple[str, ...]:
    """The unit's filesystem bounds: the project checkout read-only with its
    `.git` writable, and the named worktrees unreachable."""
    return (
        f"ReadOnlyPaths={project.root}",
        f"ReadWritePaths={project.root / '.git'}",
        *(f"InaccessiblePaths=-{path}" for path in inaccessible),
    )


def workspace_of(project: ProjectAdapter) -> WorkspacePolicy:
    if project.workspace is None:
        raise BatchRefusal(
            "workspace", f"project {project.project_id} declares no [workspace]"
        )
    return project.workspace


def worktree_path(project: ProjectAdapter, branch: str) -> Path:
    """`<workspace.root>/<repo>-<branch>`, the placement `wt` is configured for."""
    return (
        workspace_of(project).root / f"{project.root.name}-{branch.replace('/', '-')}"
    )


def landing_group(project_id: str) -> str:
    return f"{project_id}-land"


def ensure_landing_groups(project_id: str) -> None:
    """Create the groups a landing needs where the daemon lacks them.

    The landing task takes the project's single land slot and queues its own
    agents into `land-agent`, whatever `pools apply` has reached the daemon:
    a landing must not depend on the `agent` pool being open. A daemon that
    lost its state lost its groups with its tasks, so every path that queues
    a landing asks for them rather than assuming an earlier start's.
    """
    pueue.group_add(landing_group(project_id), 1)
    pueue.group_add(LANDING_AGENT_GROUP, LANDING_AGENT_PARALLELISM)


def write_prompt(worktree: Path, name: str, prompt: str) -> Path:
    state_dir = worktree / WORKTREE_STATE_DIR
    state_dir.mkdir(mode=0o700, exist_ok=True)
    path = state_dir / name
    descriptor = os.open(
        path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "w") as handle:
        handle.write(prompt)
    return path


def _agent_argv(
    config: Config,
    *,
    worktree: Path,
    prompt_path: Path,
    result_path: Path,
    backend: str,
    model: str,
    effort: str,
    schema_path: Path | None,
) -> tuple[str, ...]:
    """The runner's argv. Its containment is the queued task's own scope."""
    if not config.agent_runner.is_file() or not os.access(config.agent_runner, os.X_OK):
        raise BatchRefusal(
            "runner", f"agent runner is unavailable: {config.agent_runner}"
        )
    argv = [
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
    ]
    if schema_path is not None:
        argv.extend(["--output-schema", str(schema_path)])
    return tuple(argv)


def queue_agent(
    config: Config,
    project: ProjectAdapter,
    *,
    label: str,
    worktree: Path,
    prompt: str,
    prompt_name: str,
    backend: str,
    model: str,
    effort: str,
    schema: str | None = None,
    then: Sequence[str] = (),
    after: Sequence[int] = (),
    timeout_seconds: int = MAX_AGENT_TIMEOUT_SECONDS,
    binding: Mapping[str, Any] | None = None,
    inaccessible: Sequence[Path] = (),
    group: str = AGENT_GROUP,
) -> dict[str, Any]:
    """Queue one agent in ``group``; ``then`` runs after a successful agent.

    With ``schema`` the backend must answer with a conforming JSON document,
    written beside the prompt as ``<prompt stem>.result.json``. ``binding``
    names the beads, run and worker the task serves; `job get` shows it.
    ``inaccessible`` names the worktrees the unit must not reach.
    """
    workspace = workspace_of(project)
    prompt_path = write_prompt(worktree, prompt_name, prompt)
    stem = prompt_name.rsplit(".", 1)[0]
    schema_path = (
        results.write_schema(
            worktree / WORKTREE_STATE_DIR / f"{schema}.schema.json", schema
        )
        if schema
        else None
    )
    result_path = (
        worktree / WORKTREE_STATE_DIR / f"{stem}.result.{'json' if schema else 'md'}"
    )
    runner = _agent_argv(
        config,
        worktree=worktree,
        prompt_path=prompt_path,
        result_path=result_path,
        backend=backend,
        model=model,
        effort=effort,
        schema_path=schema_path,
    )
    if then:
        # One shell word list so the result is filed only after the agent
        # exits successfully; `"$@"` keeps the runner argv exactly as built.
        payload: tuple[str, ...] = (
            "bash",
            "-c",
            f'"$@" && exec {" ".join(shlex.quote(word) for word in then)}',
            "agentctl-worker",
            *runner,
        )
    else:
        payload = runner
    environment = project.environment.values()
    environment.setdefault("BEADS_ACTOR", label.replace(":", "-"))
    environment["AGENTCTL_PRINCIPAL"] = "agent-control"
    environment["AGENTCTL_PROJECT_ID"] = project.project_id
    operation = label.split(":", 1)[1]
    if operation.split(":", 1)[0] in RESTRICTED_KINDS:
        restrict_environment(config, environment)
    return launch.enqueue(
        config,
        project=project,
        operation=operation,
        label=label,
        group=group,
        argv=project.environment.command_for(payload),
        working_directory=worktree,
        timeout_seconds=timeout_seconds,
        result_kind="last-message",
        environment=environment,
        kind="attested-agent",
        after=after,
        unit_properties=(
            f"MemoryMax={workspace.agent_memory_max}",
            *path_properties(project, inaccessible=inaccessible),
        ),
        binding=binding,
    )


def other_worktrees(
    project: ProjectAdapter, run: Run, worker_id: str | None
) -> tuple[Path, ...]:
    """Every worker worktree of the run except ``worker_id``'s own; one not
    yet created is where `wt` will place it."""
    return tuple(
        Path(worker["worktree"])
        if worker.get("worktree")
        else worktree_path(project, worker["branch"])
        for worker in run.workers
        if worker["id"] != worker_id
    )


def binding(run: Run, worker_id: str | None) -> dict[str, Any]:
    worker = run.worker(worker_id) if worker_id else None
    beads = list(worker["beads"]) if worker else list(run.beads)
    requested = (
        {
            key: worker.get(key)
            for key in ("backend", "model", "effort")
            if isinstance(worker.get(key), str) and worker.get(key)
        }
        if worker
        else {}
    )
    return {
        "beads": beads,
        "run_id": run.run_id,
        "worker": worker_id,
        "execution": run.harness,
        "attempt": (len(worker.get("task_ids") or []) + 1) if worker else None,
        "requested": requested,
    }


def result_path(worktree: Path) -> Path:
    return worktree / WORKTREE_STATE_DIR / "prompt.result.json"


def worker_then(
    config: Config, run_id: str, worker_id: str, result: Path
) -> tuple[str, ...]:
    return (
        config.agentctl_executable,
        "batch",
        "result",
        run_id,
        worker_id,
        str(result),
    )


def queue_landing(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    *,
    after: Sequence[int],
    stashed: bool,
) -> int:
    started = launch.enqueue(
        config,
        project=project,
        operation=f"land:{run.run_id}",
        label=f"{project.project_id}:land:{run.run_id}",
        group=landing_group(project.project_id),
        argv=(config.agentctl_executable, "batch", "land", run.run_id),
        working_directory=project.root,
        timeout_seconds=MAX_AGENT_TIMEOUT_SECONDS,
        result_kind="exit",
        environment=project.environment.values(),
        after=after,
        stashed=stashed,
    )
    task_id = started.get("job_id")
    if not isinstance(task_id, int):
        raise PueueError("pueue returned no task id for the landing task")
    return task_id


def requeue_landing(
    config: Config,
    project: ProjectAdapter,
    run: Run,
    tasks: Mapping[int, pueue.Task],
) -> tuple[Run, int]:
    """Queue a replacement landing for a live run and record it on the run.

    One placement rule for every caller that queues a landing after the run
    started: wait for the worker tasks pueue still has and has not finished,
    and stay stashed while any worker still owes a result. A landing that can
    run at once refuses `worker_not_done` and ends as a failed task nobody is
    waiting on; `batch result` releases the stash once the last result is in.
    A worker that already ended is answered by the result it filed, and
    depending on an id the queue no longer has would strand the new task
    exactly as the old one was stranded.
    """
    after = [
        task.task_id
        for worker in run.workers
        if (
            task := launch.find_task(
                tasks, worker.get("task_id"), worker.get("task_reference")
            )
        )
        is not None
        and not task.terminal
    ]
    ensure_landing_groups(project.project_id)
    waiting_for_results = not all(worker.get("result") for worker in run.workers)
    landing_id = queue_landing(
        config,
        project,
        run,
        after=after,
        stashed=waiting_for_results,
    )
    queued = pueue.task(landing_id)
    return (
        land_update(
            config,
            run.run_id,
            task_id=landing_id,
            task_reference=launch.launch_reference(queued) if queued else None,
            waiting_for_results=waiting_for_results,
            failure=None,
        ),
        landing_id,
    )
