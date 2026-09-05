"""Queueing a batch's agents and its landing task."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import launch, results
from .config import Config
from .limits import MAX_AGENT_TIMEOUT_SECONDS
from .manifest import BatchRefusal, Run
from .projects import ProjectAdapter, WorkspacePolicy
from .pueue import PueueError

AGENT_GROUP = "agent"
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
) -> dict[str, Any]:
    """Queue one agent in the agent group; ``then`` runs after a successful agent.

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
        group=AGENT_GROUP,
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
    beads = list(run.worker(worker_id)["beads"]) if worker_id else list(run.beads)
    return {"beads": beads, "run_id": run.run_id, "worker": worker_id}


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
