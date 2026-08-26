"""Build the campaign board as a short-lived view of its owners."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .fleet import read_fleet
from .jobs import GenericJobStore

BOARD_SCHEMA_VERSION = 2
DEFAULT_CACHE_SECONDS = 30
DEFAULT_LIMIT = 200


class BoardError(RuntimeError):
    """The live sources could not produce a board view."""


def _run_json(argv: list[str], *, cwd: Path) -> Any:
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=30, check=True)
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise BoardError(f"command failed: {' '.join(argv[:3])}") from error


def _bead_id(value: Any) -> str | None:
    return value.rsplit("/", 1)[-1] if isinstance(value, str) and value else None


def _pull_requests(root: Path) -> list[dict[str, Any]]:
    value = _run_json([
        "gh", "pr", "list", "--state", "all", "--limit", str(DEFAULT_LIMIT),
        "--json", "number,state,title,headRefName,baseRefName,mergedAt,url",
    ], cwd=root)
    if not isinstance(value, list):
        raise BoardError("gh returned an invalid pull-request list")
    try:
        repo_value = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"], cwd=root)
    except BoardError:
        return []
    repo = repo_value.get("nameWithOwner") if isinstance(repo_value, Mapping) else None
    if not isinstance(repo, str) or not repo:
        return []
    return [{"repo": repo, **dict(row)} for row in value
            if isinstance(row, Mapping) and isinstance(row.get("number"), int)]


def _beads(root: Path) -> dict[str, Mapping[str, Any]]:
    value = _run_json(["bd", "list", "--all", "--json"], cwd=root)
    if not isinstance(value, list):
        raise BoardError("bd returned an invalid bead list")
    return {str(row["id"]): row for row in value
            if isinstance(row, Mapping) and isinstance(row.get("id"), str)}


def build_campaign_board(*, state_dir: Path, project_roots: Mapping[str, Path],
                         now: datetime | None = None,
                         fleet: Mapping[str, Any] | None = None,
                         pull_requests: Mapping[str, list[Mapping[str, Any]]] | None = None,
                         beads: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None) -> dict[str, Any]:
    """Join live owners into a deterministic board, without event state."""
    observed = now or datetime.now(UTC)
    fleet_value = fleet if fleet is not None else read_fleet(
        GenericJobStore(state_dir), limit=DEFAULT_LIMIT, gh_limit=0
    )
    rows = fleet_value.get("rows", [])
    if not isinstance(rows, list):
        raise BoardError("fleet returned an invalid row list")
    live_prs = dict(pull_requests or {})
    live_beads = dict(beads or {})
    projects = {str(row.get("project")) for row in rows
                if isinstance(row, Mapping) and isinstance(row.get("project"), str)}
    for project in sorted(projects):
        root = project_roots.get(project)
        if root is None:
            continue
        if pull_requests is None:
            live_prs[project] = _pull_requests(root)
        if beads is None:
            live_beads[project] = _beads(root)
    lanes = {str(row["job_id"]): dict(row) for row in rows
             if isinstance(row, Mapping) and isinstance(row.get("job_id"), str)}
    branches = {row.get("branch"): row for row in lanes.values()
                if isinstance(row.get("branch"), str)}
    prs: dict[str, dict[str, Any]] = {}
    for project, project_prs in sorted(live_prs.items()):
        for raw in project_prs:
            if not isinstance(raw, Mapping):
                continue
            repo, number = raw.get("repo"), raw.get("number")
            if not isinstance(repo, str) or not repo or not isinstance(number, int):
                continue
            row = branches.get(raw.get("headRefName"))
            bead_id = _bead_id(row.get("bead")) if row else None
            bead = live_beads.get(project, {}).get(bead_id) if bead_id else None
            record = {key: raw[key] for key in raw if key != "repo"}
            record["repo"] = repo
            if bead_id:
                record["bead_id"] = bead_id
                if bead is not None and isinstance(bead.get("status"), str):
                    record["bead_status"] = bead["status"]
            prs[f"{repo}#{number}"] = record
    return {"schema_version": BOARD_SCHEMA_VERSION, "generated_at": observed.isoformat(),
            "source": "agentctl+git+github+beads", "lanes": dict(sorted(lanes.items())),
            "prs": dict(sorted(prs.items()))}


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def refresh_campaign_board(path: Path, **kwargs: Any) -> dict[str, Any]:
    value = build_campaign_board(**kwargs)
    _write_atomic(path, value)
    return value


def load_or_refresh_campaign_board(path: Path, *, cache_seconds: int = DEFAULT_CACHE_SECONDS,
                                   force: bool = False, **kwargs: Any) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
        age = datetime.now(UTC).timestamp() - path.stat().st_mtime
        if not force and age < cache_seconds and isinstance(value, Mapping) and value.get("schema_version") == BOARD_SCHEMA_VERSION:
            return dict(value)
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return refresh_campaign_board(path, **kwargs)
