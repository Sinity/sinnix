"""The run manifest: one JSON document per batch under ``<state_dir>/runs/``.

``start`` writes it once; every later step updates it under a file lock.
pueue holds the live task state, Beads the claims, worktrunk the worktrees,
GitHub the PR; the manifest records what agentctl decided and observed.
"""

from __future__ import annotations

import fcntl
import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from .config import Config
from .limits import SHORT_ID

HARNESSES = ("queued", "external")
REVIEW_PROFILE = "review"


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
    def beads(self) -> tuple[str, ...]:
        return tuple(bead for item in self.workers for bead in item["beads"])

    @property
    def actor(self) -> str:
        return f"agentctl-batch-{self.run_id}"


def runs_dir(config: Config) -> Path:
    return config.state_dir / "runs"


def manifest_path(config: Config, run_id: str) -> Path:
    return runs_dir(config) / f"{run_id}.json"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _dump(document: Mapping[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _write(path: Path, document: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(_dump(document))
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
        handle.write(_dump(run.to_dict()))


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
def _flock(lock: Path) -> Iterator[None]:
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _locked(path: Path) -> Iterator[None]:
    return _flock(path.with_suffix(".lock"))


def project_lock_path(config: Config, project_id: str) -> Path:
    return runs_dir(config) / f"{project_id}.lock"


def project_locked(config: Config, project_id: str) -> Iterator[None]:
    """One worktree creation or removal per project at a time: `wt` is not reentrant."""
    return _flock(project_lock_path(config, project_id))


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


def new_run_id(project_id: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{project_id}-{stamp}-{uuid.uuid4().hex[:SHORT_ID]}"


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


def set_worker(config: Config, run_id: str, index: int, **fields: Any) -> Run:
    def apply(document: dict[str, Any]) -> None:
        entry = document["workers"][index]
        for key, value in fields.items():
            if key == "task_id":
                entry["task_ids"] = [*entry.get("task_ids", []), value]
            entry[key] = value

    return update(config, run_id, apply)


def land_update(config: Config, run_id: str, **landing: Any) -> Run:
    def apply(document: dict[str, Any]) -> None:
        document["landing"].update(landing)

    return update(config, run_id, apply)
