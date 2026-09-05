"""Batches: several workers on one base commit, one landing, one acceptance record.

A run's inputs and outcomes live in one manifest under
``<state_dir>/runs/<run_id>.json``; pueue holds the live task state, Beads
the claims, worktrunk the worktrees, GitHub the PR. ``start`` writes the
manifest and builds the task graph, ``land`` integrates, verifies, reviews,
publishes and records acceptance, and both are re-runnable.
"""

from __future__ import annotations

import fcntl
import json
import os
import shlex
import subprocess
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Protocol, Sequence

from . import github, launch, pueue, results, worktrunk
from .config import Config
from .github import GithubError
from .launch import JobError
from .limits import MAX_AGENT_TIMEOUT_SECONDS
from .packets import (
    PacketConfig,
    PacketError,
    SubprocessBdReader,
    compile_launch_snapshot,
    rebase_prompt,
    resolve_group,
    validate_members,
)
from .projects import ProjectAdapter
from .pueue import PueueError
from .worktrunk import WorktrunkError

AGENT_GROUP = "agent"
# Hex characters in a run id's random suffix; tables show the suffix alone.
SHORT_RUN_ID = 8
HARNESSES = ("queued", "external")
REVIEW_PROFILE = "review"
GIT_TIMEOUT_SECONDS = 60
PUSH_TIMEOUT_SECONDS = 2_400
HOSTED_CHECK_TIMEOUT_SECONDS = 2 * 3_600
POLL_INTERVAL_SECONDS = 15
# How many times the default branch may move under a run before landing
# stops with `target_moved_twice`.
MAX_REFRESHES = 1

REVIEW_PROMPT = """# Review packet

Review the candidate `{candidate}` against base `{base}` in this worktree:
`git diff {base}..{candidate}` is the whole change surface, `git log
{base}..{candidate}` its history. The workers' own results follow. Read the
diff completely, run what you need to refute their claims, and answer with
one JSON object conforming to the judge schema: `verdict` is `pass` only when
the change is correct, complete for its beads' acceptance criteria and safe to
publish; `evidence` cites paths and lines; `unsupported` lists what you could
not establish. Do not modify files, Beads, or the repository.

## Worker results

```json
{results}
```
"""

INTEGRATE_PROMPT = """# Integration packet

This worktree is the integration branch of batch `{run_id}` on base `{base}`.
`git merge --no-ff` of `{branch}` stopped on conflicts in:

{conflicts}

Resolve them against the beads' intent, commit the merge, then merge every
remaining worker branch in this order with `git merge --no-ff --no-edit`:

{remaining}

Leave a clean tree with every listed branch merged. Do not rebase, push, or
touch Beads. Resolve honestly; a conflict you cannot resolve is reported, not
forced.

## Worker results

```json
{results}
```
"""


class BatchRefusal(RuntimeError):
    """A batch step agentctl refuses; ``code`` is stable, ``detail`` is for people."""

    def __init__(self, code: str, detail: str, **extra: Any) -> None:
        self.code = code
        self.detail = detail
        self.extra = extra
        super().__init__(f"{code}: {detail}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, **self.extra}


class BatchError(RuntimeError):
    """A tool agentctl drives (git, bd) failed."""


# ---------------------------------------------------------------- Beads


class Beads(Protocol):
    def show(self, bead_id: str) -> Mapping[str, Any]: ...

    def list(self) -> Sequence[Mapping[str, Any]]: ...

    def claim(self, bead_id: str, *, actor: str) -> None: ...

    def unclaim(self, bead_id: str, *, actor: str) -> None: ...

    def close(self, bead_id: str, *, reason: str, actor: str) -> None: ...

    def comment(self, bead_id: str, text: str, *, actor: str) -> None: ...


class SubprocessBeads(SubprocessBdReader):
    """`bd` reads and the four writes a batch makes, run in the project root."""

    def _write(self, arguments: Sequence[str], *, actor: str) -> None:
        try:
            completed = subprocess.run(
                [self.executable, "--actor", actor, *arguments],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise BatchError(
                f"bd {' '.join(arguments)} failed in {self.root}"
            ) from error
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise BatchError(f"bd {' '.join(arguments[:2])}: {detail}")

    def claim(self, bead_id: str, *, actor: str) -> None:
        self._write(("update", bead_id, "--claim"), actor=actor)

    def unclaim(self, bead_id: str, *, actor: str) -> None:
        self._write(("unclaim", bead_id, "--if-assignee", actor), actor=actor)

    def close(self, bead_id: str, *, reason: str, actor: str) -> None:
        self._write(("close", bead_id, "--reason", reason), actor=actor)

    def comment(self, bead_id: str, text: str, *, actor: str) -> None:
        self._write(("comment", bead_id, text), actor=actor)


# ---------------------------------------------------------------- manifest


@dataclass(frozen=True)
class Run:
    """The manifest, typed at the top level; nested records stay dicts."""

    run_id: str
    project: str
    base_commit: str
    created_at: str
    harness: str
    runtime_revision: str
    verify_profile: str | None
    review_profile: str
    workers: tuple[dict[str, Any], ...]
    landing: dict[str, Any]
    acceptance: dict[str, Any] | None
    prepared: bool

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Run:
        try:
            return cls(
                run_id=str(value["run_id"]),
                project=str(value["project"]),
                base_commit=str(value["base_commit"]),
                created_at=str(value["created_at"]),
                harness=str(value["harness"]),
                runtime_revision=str(value.get("runtime_revision") or ""),
                verify_profile=value.get("verify_profile"),
                review_profile=str(value.get("review_profile") or REVIEW_PROFILE),
                workers=tuple(dict(item) for item in value["workers"]),
                landing=dict(value["landing"]),
                acceptance=dict(value["acceptance"])
                if value.get("acceptance")
                else None,
                prepared=bool(value.get("prepared")),
            )
        except (KeyError, TypeError) as error:
            raise BatchRefusal(
                "manifest", f"unreadable run manifest: {error}"
            ) from error

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project": self.project,
            "base_commit": self.base_commit,
            "created_at": self.created_at,
            "harness": self.harness,
            "runtime_revision": self.runtime_revision,
            "verify_profile": self.verify_profile,
            "review_profile": self.review_profile,
            "workers": [dict(item) for item in self.workers],
            "landing": dict(self.landing),
            "acceptance": dict(self.acceptance) if self.acceptance else None,
            "prepared": self.prepared,
        }

    def worker(self, worker_id: str) -> dict[str, Any]:
        for item in self.workers:
            if item["id"] == worker_id:
                return item
        raise BatchRefusal("worker", f"run {self.run_id} has no worker {worker_id}")

    @property
    def members(self) -> tuple[str, ...]:
        return tuple(bead for item in self.workers for bead in item["beads"])

    @property
    def actor(self) -> str:
        return f"agentctl-batch-{self.run_id}"


def runs_dir(config: Config) -> Path:
    return config.state_dir / "runs"


def manifest_path(config: Config, run_id: str) -> Path:
    return runs_dir(config) / f"{run_id}.json"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write(path: Path, document: Mapping[str, Any]) -> None:
    payload = json.dumps(document, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload)
    os.replace(temporary, path)


def create(config: Config, run: Run) -> None:
    """Write the manifest once; a second writer for the same id is refused."""
    path = manifest_path(config, run.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise BatchRefusal(
            "exists", f"run {run.run_id} already has a manifest"
        ) from error
    with os.fdopen(descriptor, "w") as handle:
        handle.write(json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n")


def load(config: Config, run_id: str) -> Run:
    path = manifest_path(config, run_id)
    try:
        return Run.from_dict(json.loads(path.read_text()))
    except FileNotFoundError as error:
        raise BatchRefusal(
            "unknown_run", f"no run {run_id} under {path.parent}"
        ) from error
    except json.JSONDecodeError as error:
        raise BatchRefusal("manifest", f"{path} is not JSON: {error}") from error


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    lock = path.with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def update(config: Config, run_id: str, fn: Callable[[dict[str, Any]], None]) -> Run:
    """Apply ``fn`` to the manifest document under the file lock and return the result."""
    path = manifest_path(config, run_id)
    with _locked(path):
        run = load(config, run_id)
        document = run.to_dict()
        fn(document)
        updated = Run.from_dict(document)
        _write(path, updated.to_dict())
    return updated


def list_runs(config: Config, project_id: str | None = None) -> list[Run]:
    directory = runs_dir(config)
    if not directory.is_dir():
        return []
    runs = []
    for path in sorted(directory.glob("*.json")):
        try:
            run = Run.from_dict(json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError, BatchRefusal):
            continue
        if project_id is None or run.project == project_id:
            runs.append(run)
    return runs


# ---------------------------------------------------------------- helpers


def _git(path: Path, *arguments: str, timeout: float = GIT_TIMEOUT_SECONDS) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BatchError(f"git {arguments[0]} failed in {path}: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise BatchError(f"git {' '.join(arguments[:2])}: {detail}")
    return completed.stdout.strip()


def _workspace(project: ProjectAdapter):
    if project.workspace is None:
        raise BatchRefusal(
            "workspace", f"project {project.project_id} declares no [workspace]"
        )
    return project.workspace


def worktree_path(project: ProjectAdapter, branch: str) -> Path:
    """`<workspace.root>/<repo>-<branch>`, the placement `wt` is configured for."""
    return _workspace(project).root / f"{project.root.name}-{branch.replace('/', '-')}"


def landing_group(project_id: str) -> str:
    return f"{project_id}-land"


def _write_prompt(worktree: Path, name: str, prompt: str) -> Path:
    lane_dir = worktree / ".lane"
    lane_dir.mkdir(mode=0o700, exist_ok=True)
    path = lane_dir / name
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
) -> dict[str, Any]:
    """Queue one agent in the agent group; ``then`` runs after a successful agent.

    With ``schema`` the backend must answer with a conforming JSON document,
    written beside the prompt as ``<prompt stem>.result.json``.
    """
    workspace = _workspace(project)
    prompt_path = _write_prompt(worktree, prompt_name, prompt)
    stem = prompt_name.rsplit(".", 1)[0]
    schema_path = (
        results.write_schema(worktree / ".lane" / f"{schema}.schema.json", schema)
        if schema
        else None
    )
    result_path = worktree / ".lane" / f"{stem}.result.{'json' if schema else 'md'}"
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
        scope_properties=(f"MemoryMax={workspace.agent_memory_max}",),
    )


def _result_path(worktree: Path) -> Path:
    return worktree / ".lane" / "prompt.result.json"


def _worker_then(
    config: Config, run_id: str, worker_id: str, worktree: Path
) -> tuple[str, ...]:
    return (
        config.agentctl_executable,
        "batch",
        "result",
        run_id,
        worker_id,
        str(_result_path(worktree)),
    )


def _queue_landing(
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


# ---------------------------------------------------------------- start


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
    return [run for run in list_runs(config, project_id) if run.acceptance is None]


def _base_commit(project: ProjectAdapter) -> str:
    base = _workspace(project).default_base
    if base.startswith("origin/"):
        try:
            _git(
                project.root, "fetch", "--quiet", "origin", timeout=PUSH_TIMEOUT_SECONDS
            )
        except BatchError:
            pass
    return _git(project.root, "rev-parse", "--verify", f"{base}^{{commit}}")


def _new_run_id(project_id: str, leaders: Sequence[str]) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{project_id}-{stamp}-{uuid.uuid4().hex[:SHORT_RUN_ID]}"


def short_run_id(run_id: str) -> str:
    """The run's random suffix, which every verb accepts in place of the id."""
    return run_id.rsplit("-", 1)[-1]


def resolve_run_id(config: Config, token: str) -> str:
    """A full run id, or the one run whose suffix is ``token``."""
    if manifest_path(config, token).is_file():
        return token
    matches = [
        run.run_id for run in list_runs(config) if short_run_id(run.run_id) == token
    ]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise BatchRefusal(
            "ambiguous_run", f"{token} names {len(matches)} runs: {', '.join(matches)}"
        )
    raise BatchRefusal("unknown_run", f"no run {token} under {runs_dir(config)}")


def _set_worker(config: Config, run_id: str, index: int, **fields: Any) -> Run:
    def apply(document: dict[str, Any]) -> None:
        entry = document["workers"][index]
        for key, value in fields.items():
            if key == "task_id":
                entry["task_ids"] = [*entry.get("task_ids", []), value]
            entry[key] = value

    return update(config, run_id, apply)


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
    packets = PacketConfig.load(project.root)
    if run.harness == "queued":
        pueue.group_add(landing_group(project.project_id), 1)
    for index, worker in enumerate(run.workers):
        worker_id = worker["id"]
        if not worker.get("claimed"):
            for bead_id in worker["beads"]:
                beads.claim(bead_id, actor=run.actor)
            run = _set_worker(config, run.run_id, index, claimed=True)
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
            snapshot = compile_launch_snapshot(
                worker["leader"],
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
                    "worker_id": worker_id,
                    "base_commit": run.base_commit,
                    "worktree": str(path),
                    "result_path": str(_result_path(path)),
                    "result_schema": str(path / ".lane" / "worker.schema.json"),
                    "harness": run.harness,
                },
            )
            _write_prompt(path, "prompt.md", snapshot.prompt)
            results.write_schema(path / ".lane" / "worker.schema.json", "worker")
            run = _set_worker(
                config,
                run.run_id,
                index,
                worktree=str(path),
                result_path=str(_result_path(path)),
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
                prompt=(path / ".lane" / "prompt.md").read_text(),
                prompt_name="prompt.md",
                backend=worker["backend"],
                model=worker["model"],
                effort=worker["effort"],
                schema="worker",
                then=_worker_then(config, run.run_id, worker_id, path),
            )
            run = _set_worker(config, run.run_id, index, task_id=job["job_id"])
    if run.landing.get("task_id") is None:
        after = [
            worker["task_id"]
            for worker in run.workers
            if worker.get("task_id") is not None
        ]
        landing_id = _queue_landing(
            config, project, run, after=after, stashed=run.harness == "external"
        )
        run = _land_update(config, run.run_id, task_id=landing_id)

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
        if worker.get("claimed"):
            for bead_id in worker["beads"]:
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
    workspace = _workspace(project)
    beads = reader or SubprocessBeads(project.root)
    member_sets = _member_sets(beads, seeds, workers)
    requested = {bead for _leader, members in member_sets for bead in members}
    claimed: set[str] = set()
    for live in _live_runs(config, project.project_id):
        if set(live.members) == requested:
            if live.prepared:
                return {**live.to_dict(), "resumed": False, "existing": True}
            return {
                **_prepare(
                    config,
                    project,
                    live,
                    beads,
                    backend=backend,
                    model=model,
                    effort=effort,
                ).to_dict(),
                "resumed": True,
                "existing": True,
            }
        claimed.update(live.members)
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
    run_id = _new_run_id(
        project.project_id, [leader for leader, _members in member_sets]
    )
    run = Run(
        run_id=run_id,
        project=project.project_id,
        base_commit=base_commit,
        created_at=_now(),
        harness=harness,
        runtime_revision=os.path.realpath(config.agentctl_executable),
        verify_profile=workspace.verify.get("candidate"),
        review_profile=REVIEW_PROFILE,
        workers=tuple(
            {
                "id": leader,
                "leader": leader,
                "beads": list(members),
                "branch": f"batch/{run_id}/{leader}",
                "worktree": None,
                "task_id": None,
                "task_ids": [],
                "claimed": False,
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
        prepared = _prepare(
            config, project, run, beads, backend=backend, model=model, effort=effort
        )
    except (
        BatchRefusal,
        BatchError,
        PacketError,
        PueueError,
        WorktrunkError,
        JobError,
    ):
        _rollback(config, project, run_id, beads)
        raise
    return {**prepared.to_dict(), "resumed": False, "existing": False}


# ---------------------------------------------------------------- result / resume


def result(config: Config, run_id: str, worker_id: str, path: Path) -> dict[str, Any]:
    """File a worker's result after validating it and binding it to the worktree head."""
    run = load(config, run_id)
    worker = run.worker(worker_id)
    value, errors = results.load_result(path, kind="worker")
    if errors:
        raise BatchRefusal("invalid_result", "; ".join(errors[:6]), errors=errors)
    worktree = worker.get("worktree")
    if worktree:
        head = _git(Path(worktree), "rev-parse", "HEAD")
        if head != value["candidate_sha"]:
            raise BatchRefusal(
                "candidate_mismatch",
                f"result names {value['candidate_sha'][:12]} but {worktree} is at {head[:12]}",
            )
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
                entry["result_recorded_at"] = _now()

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
    worker = run.worker(worker_id)
    worktree = worker.get("worktree")
    if not worktree or not Path(worktree).is_dir():
        raise BatchRefusal(
            "worktree", f"worker {worker_id} has no worktree; start the batch instead"
        )
    tasks = pueue.tasks()
    current = (
        tasks.get(worker["task_id"]) if isinstance(worker.get("task_id"), int) else None
    )
    if current is not None and not current.terminal:
        raise BatchRefusal(
            "worker_active", f"task {current.task_id} is still {current.status.lower()}"
        )
    packets = PacketConfig.load(project.root)
    beads = SubprocessBeads(project.root)
    path = Path(worktree)
    packet_path = path / ".lane" / "prompt.md"
    prompt = rebase_prompt(
        config=packets,
        bead=beads.show(worker["leader"]),
        branch=worker["branch"],
        base=run.base_commit,
        worktree=path,
        packet=packet_path.read_text() if packet_path.is_file() else None,
    )
    job = queue_agent(
        config,
        project,
        label=f"{project.project_id}:resume:{run_id}:{worker_id}",
        worktree=path,
        prompt=prompt,
        prompt_name="prompt.md",
        backend=backend or worker.get("backend") or packets.default_backend,
        model=model or worker.get("model") or packets.default_model,
        effort=effort or worker.get("effort") or packets.default_effort,
        schema="worker",
        then=_worker_then(config, run_id, worker_id, path),
    )
    task_id = job["job_id"]

    def record(document: dict[str, Any]) -> None:
        for entry in document["workers"]:
            if entry["id"] == worker_id:
                entry["task_id"] = task_id
                entry["task_ids"] = [*entry.get("task_ids", []), task_id]
                entry["result"] = None
        document["landing"]["failure"] = None

    run = update(config, run_id, record)
    landing_id = run.landing.get("task_id")
    if run.harness == "queued":
        # The old landing task depended on the failed worker task and is done
        # for good; the new one waits on every worker's current task.
        old = tasks.get(landing_id) if isinstance(landing_id, int) else None
        if old is not None and old.terminal:
            pueue.remove([landing_id])
        if old is None or old.terminal:
            after = [
                item["task_id"]
                for item in run.workers
                if isinstance(item.get("task_id"), int)
            ]
            new_landing = _queue_landing(
                config, project, run, after=after, stashed=False
            )

            def relink(document: dict[str, Any]) -> None:
                document["landing"]["task_id"] = new_landing

            run = update(config, run_id, relink)
    return {**run.to_dict(), "job": job, "worker": worker_id}


# ---------------------------------------------------------------- land


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


def _land_update(config: Config, run_id: str, **landing: Any) -> Run:
    def apply(document: dict[str, Any]) -> None:
        document["landing"].update(landing)

    return update(config, run_id, apply)


def _worker_results(run: Run) -> list[dict[str, Any]]:
    return [dict(worker["result"]) for worker in run.workers if worker.get("result")]


def _integrate(config: Config, project: ProjectAdapter, run: Run, base: str) -> str:
    """Merge every worker branch onto ``base`` in the integration worktree; return HEAD."""
    branch = run.landing["integration_branch"]
    existing = worktrunk.worktrunk_find(project.root, branch)
    if existing is not None and existing.path is not None and existing.path.is_dir():
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
    run = _land_update(config, run.run_id, integration_worktree=str(path))
    branches = [worker["branch"] for worker in run.workers]
    for position, worker_branch in enumerate(branches):
        try:
            _git(path, "merge", "--no-ff", "--no-edit", worker_branch)
            continue
        except BatchError:
            conflicts = _git(path, "diff", "--name-only", "--diff-filter=U")
        worker = run.workers[0]
        prompt = INTEGRATE_PROMPT.format(
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
            if not line[3:].startswith(".lane/")
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
    workspace = _workspace(project)
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
        titles = ", ".join(worker["leader"] for worker in run.workers)
        return github.create_pull_request(
            project.root,
            head=branch,
            base=workspace.base_branch,
            title=f"batch {run.run_id}: {titles}"[:72],
            body=f"Batch `{run.run_id}` on base `{run.base_commit}`.\n\nMembers: "
            + ", ".join(run.members)
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
    profile = run.verify_profile or _workspace(project).verify.get("candidate")
    if not profile:
        raise BatchRefusal(
            "no_candidate_profile",
            f"{project.project_id} declares no [workspace].verify.candidate",
        )
    if profile.startswith("hosted:"):
        check = profile.removeprefix("hosted:")
        number = _ensure_pr(project, run, path, candidate)
        run = _land_update(config, run.run_id, pr_number=number)
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
    prompt = REVIEW_PROMPT.format(
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
    )
    waited = launch.wait(job["job_id"], timeout_seconds=MAX_AGENT_TIMEOUT_SECONDS)
    if waited.get("phase") != "succeeded":
        raise BatchRefusal(
            "review_failed", f"review task {job['job_id']} {waited.get('phase')}"
        )
    verdict, errors = results.load_result(
        path / ".lane" / "review.result.json", kind="judge"
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
    branch = _workspace(project).base_branch
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
    workspace = _workspace(project)
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
            if "stale info" in str(error) or "rejected" in str(error):
                return None
            raise
        return {"policy": "master", "candidate_sha": candidate, "base_commit": base}
    number = _ensure_pr(project, run, path, candidate)
    run = _land_update(config, run.run_id, pr_number=number)
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
    members: dict[str, dict[str, str]] = {}
    for bead_id in run.members:
        if verdicts.get(bead_id):
            try:
                beads.close(
                    bead_id, reason=f"batch {run.run_id} {candidate}", actor=run.actor
                )
                members[bead_id] = {
                    "state": "closed",
                    "evidence": f"batch {run.run_id} {candidate}",
                }
            except BatchError as error:
                members[bead_id] = {
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
            members[bead_id] = {"state": "open", "evidence": residual}
    acceptance = {
        "candidate_sha": candidate,
        "verify_run": dict(verify_run),
        "review_verdict": dict(review_verdict),
        "published": dict(published),
        "members": members,
        "recorded_at": _now(),
        "residual": [],
    }

    def record(document: dict[str, Any]) -> None:
        document["acceptance"] = acceptance
        document["landing"]["failure"] = None

    run = update(config, run.run_id, record)
    residual: list[str] = []
    for branch in [
        *(worker["branch"] for worker in run.workers),
        run.landing["integration_branch"],
    ]:
        try:
            worktrunk.worktrunk_remove(project.root, branch, force=True)
        except WorktrunkError as error:
            residual.append(f"{branch}: {error}")
    if residual:

        def note(document: dict[str, Any]) -> None:
            document["acceptance"]["residual"] = residual

        run = update(config, run.run_id, note)
    return run


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
            run = _land_update(
                config,
                run_id,
                candidate_sha=candidate,
                verify_run=None,
                review_verdict=None,
                failure=None,
            )
            path = Path(run.landing["integration_worktree"])
            run, verify_run = _verify(config, project, run, path, candidate, sleep)
            run = _land_update(config, run_id, verify_run=verify_run)
            review_verdict = _review(config, project, run, path, base, candidate)
            run = _land_update(config, run_id, review_verdict=review_verdict)
            published = _publish(config, project, run, path, base, candidate, sleep)
            if published is not None:
                break
            if int(run.landing.get("refreshes") or 0) >= MAX_REFRESHES:
                raise BatchRefusal(
                    "target_moved_twice",
                    f"{_workspace(project).base_branch} moved again during landing",
                )
            base = _remote_base(project)
            run = _land_update(
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
            _land_update(config, run_id, failure=refusal.to_dict())
        raise
    except (
        BatchError,
        PueueError,
        WorktrunkError,
        GithubError,
        JobError,
        PacketError,
    ) as error:
        _land_update(
            config, run_id, failure={"code": "substrate", "detail": str(error)}
        )
        raise
    return run.to_dict()


# ---------------------------------------------------------------- status


def status(
    config: Config, run_id: str, *, project: ProjectAdapter | None = None
) -> dict[str, Any]:
    """The manifest with each task's pueue view and the landing PR's state."""
    run = load(config, run_id)
    tasks = pueue.tasks()
    document = run.to_dict()
    for worker in document["workers"]:
        task_id = worker.get("task_id")
        task = tasks.get(task_id) if isinstance(task_id, int) else None
        worker["task"] = launch.job_view(task) if task else None
        worker["stage"] = worker_stage(worker, task)
    landing_id = document["landing"].get("task_id")
    landing_task = tasks.get(landing_id) if isinstance(landing_id, int) else None
    document["landing"]["task"] = (
        launch.job_view(landing_task) if landing_task else None
    )
    document["stage"] = run_stage(
        run,
        landing_task,
        [
            tasks.get(w["task_id"]) if isinstance(w.get("task_id"), int) else None
            for w in run.workers
        ],
    )
    number = run.landing.get("pr_number")
    if project is not None and isinstance(number, int):
        try:
            pull = github.pull_request(project.root, number)
        except GithubError as error:
            pull = {"error": str(error)}
        document["landing"]["pr"] = pull
    return document


def worker_stage(worker: Mapping[str, Any], task: pueue.Task | None) -> str:
    """What the worker is doing, from pueue first and the manifest second."""
    if task is not None and not task.terminal:
        return task.status.lower()
    if worker.get("result"):
        return "done"
    if task is not None and task.terminal:
        return launch.phase_of(task)
    return "awaiting result" if worker.get("worktree") else "unprepared"


def run_stage(
    run: Run, landing: pueue.Task | None, worker_tasks: Sequence[pueue.Task | None]
) -> str:
    """The run as one word: an active worker or landing task is never landed."""
    if any(task is not None and not task.terminal for task in worker_tasks):
        return "working"
    if landing is not None and not landing.terminal:
        return "stashed" if landing.status == "Stashed" else "landing"
    if run.acceptance is not None:
        return "landed"
    failure = run.landing.get("failure")
    if failure:
        return f"failed: {failure.get('code')}"
    if not run.prepared:
        return "unprepared"
    if landing is not None and landing.terminal and not landing.succeeded:
        return f"landing {launch.phase_of(landing)}"
    return (
        "awaiting workers"
        if not all(w.get("result") for w in run.workers)
        else "ready to land"
    )
