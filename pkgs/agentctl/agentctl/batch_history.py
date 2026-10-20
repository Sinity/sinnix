"""Read original batch records without loading or running the workflow engine."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from .config import Config


class HistoryError(RuntimeError):
    def __init__(self, code: str, detail: str, **extra: Any) -> None:
        self.code = code
        self.detail = detail
        self.extra = extra
        super().__init__(f"{code}: {detail}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, **self.extra}


class HistoryRefusal(HistoryError):
    """A requested record identity is missing, ambiguous, or invalid."""


@dataclass(frozen=True)
class Run:
    """Convenience reads over the complete original document, including unknown fields."""

    _document: dict[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Run:
        try:
            if not isinstance(value, Mapping):
                raise TypeError("run document must be an object")
            for key in ("run_id", "project", "base_commit", "created_at", "harness"):
                value[key]
            dict(value["landing"])
            for worker in value["workers"]:
                dict(worker)
            for key in ("acceptance", "abandoned"):
                if value.get(key):
                    dict(value[key])
            for artifact in value.get("artifacts") or ():
                dict(artifact)
        except (KeyError, TypeError, ValueError) as exc:
            raise HistoryError("manifest", f"unreadable run manifest: {exc}") from exc
        return cls(copy.deepcopy(dict(value)))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)

    @property
    def run_id(self) -> str:
        return str(self._document["run_id"])

    @property
    def project(self) -> str:
        return str(self._document["project"])

    @property
    def base_commit(self) -> str:
        return str(self._document["base_commit"])

    @property
    def created_at(self) -> str:
        return str(self._document["created_at"])

    @property
    def harness(self) -> str:
        return str(self._document["harness"])

    @property
    def runtime_revision(self) -> str:
        return str(self._document.get("runtime_revision") or "")

    @property
    def verify_profile(self) -> str | None:
        return self._document.get("verify_profile")

    @property
    def review_profile(self) -> str:
        return str(self._document.get("review_profile") or "review")

    @property
    def workers(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(dict(row)) for row in self._document["workers"])

    @property
    def landing(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._document["landing"]))

    @property
    def acceptance(self) -> dict[str, Any] | None:
        value = self._document.get("acceptance")
        return copy.deepcopy(dict(value)) if value else None

    @property
    def abandoned(self) -> dict[str, Any] | None:
        value = self._document.get("abandoned")
        return copy.deepcopy(dict(value)) if value else None

    @property
    def prepared(self) -> bool:
        return bool(self._document.get("prepared"))

    @property
    def preparation_error(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._document.get("preparation_error"))

    @property
    def artifacts(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            copy.deepcopy(row) for row in self._document.get("artifacts") or ()
        )

    @property
    def live(self) -> bool:
        return self.acceptance is None and self.abandoned is None

    @property
    def beads(self) -> tuple[str, ...]:
        return tuple(bead for worker in self.workers for bead in worker["beads"])

    @property
    def actor(self) -> str:
        return f"agentctl-batch-{self.run_id}"

    def worker(self, worker_id: str) -> dict[str, Any]:
        for worker in self.workers:
            if worker["id"] == worker_id:
                return worker
        raise HistoryRefusal(
            "worker_missing", f"run {self.run_id} has no worker {worker_id}"
        )


def runs_dir(config: Config) -> Path:
    return config.state_dir / "runs"


def manifest_path(config: Config, run_id: str) -> Path:
    if not run_id or Path(run_id).name != run_id or run_id in (".", ".."):
        raise HistoryRefusal("unknown_run", "run identity must be one filename")
    return runs_dir(config) / f"{run_id}.json"


def load(config: Config, run_id: str) -> Run:
    path = manifest_path(config, run_id)
    try:
        return Run.from_dict(json.loads(path.read_text()))
    except FileNotFoundError as exc:
        raise HistoryRefusal(
            "unknown_run", f"no run {run_id} under {path.parent}"
        ) from exc
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise HistoryError("manifest", f"cannot read {path}: {exc}") from exc


def list_runs(
    config: Config, project_id: str | None = None, *, strict: bool = True
) -> list[Run]:
    directory = runs_dir(config)
    try:
        paths = sorted(path for path in directory.iterdir() if path.suffix == ".json")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise HistoryError("manifest", f"cannot inventory {directory}: {exc}") from exc
    result = []
    for path in paths:
        try:
            run = load(config, path.stem)
        except HistoryError:
            if strict:
                raise
            continue
        if project_id is None or run.project == project_id:
            result.append(run)
    return result


def short_run_id(run_id: str) -> str:
    return run_id.rsplit("-", 1)[-1]


def resolve_run_id(config: Config, token: str) -> str:
    if manifest_path(config, token).is_file():
        return token
    matches = [
        run.run_id for run in list_runs(config) if short_run_id(run.run_id) == token
    ]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise HistoryRefusal("ambiguous_run", f"{token} names {len(matches)} runs")
    raise HistoryRefusal("unknown_run", f"no run {token} under {runs_dir(config)}")
