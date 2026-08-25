"""Read-only joins over AgentCTL job, workspace, and delivery evidence."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from .jobs import GenericJobRecord, GenericJobStore, JobRecordError
from .workspaces import WorkspaceRecord, WorkspaceStore

ABSENT = "-"
DEFAULT_FLEET_LIMIT = 20
DEFAULT_RECENT_HOURS = 24.0
DEFAULT_GH_LIMIT = 8
MAX_INPUT_BYTES = 128 * 1024
GH_TIMEOUT_SECONDS = 2.0

GhLookup = Callable[[Path, str], Mapping[str, Any] | None]


def _mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _record_dict(record: GenericJobRecord) -> dict[str, Any]:
    value = record.to_dict()
    return value if isinstance(value, dict) else dict(value)


def _record_parts(
    record: GenericJobRecord,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    value = _record_dict(record)
    spec = _mapping(value.get("spec")) or {}
    state = _mapping(value.get("state")) or {}
    checkout = _mapping(spec.get("checkout")) or {}
    return spec, state, checkout


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _record_timestamp(record: GenericJobRecord) -> datetime | None:
    value = _record_dict(record)
    _spec, state, _checkout = _record_parts(record)
    return _parse_timestamp(state.get("observed_at")) or _parse_timestamp(
        value.get("created_at")
    )


def _age_seconds(record: GenericJobRecord, now: datetime) -> float | None:
    value = _record_dict(record)
    created = _parse_timestamp(value.get("created_at"))
    if created is None:
        return None
    return max(0.0, (now - created).total_seconds())


def _age_text(seconds: float | None) -> str:
    if seconds is None:
        return ABSENT
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, _remaining = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 48:
        return f"{hours}h {minutes}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def _normal_key(key: Any) -> str:
    return str(key).lower().replace("-", "_")


def _known_refs(value: Any, refs: dict[str, str]) -> None:
    mapping = _mapping(value)
    if mapping is None:
        return
    for key, child in mapping.items():
        normalized = _normal_key(key)
        if normalized in {"prompt_file", "prompt_path"} and isinstance(child, str):
            refs.setdefault("prompt_file", child)
        elif normalized in {
            "bead",
            "bead_id",
            "bead_ref",
            "beads_ref",
            "task_ref",
            "task_id",
        } and isinstance(child, str):
            refs.setdefault("bead", child)
        _known_refs(child, refs)


def _private_input(store: GenericJobStore, job_id: str) -> Mapping[str, Any] | None:
    path = store.inputs_root / f"{job_id}.json"
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            return None
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return _mapping(value)


def _refs_for_record(
    store: GenericJobStore, record: GenericJobRecord
) -> dict[str, Any]:
    value = _record_dict(record)
    spec, state, _checkout = _record_parts(record)
    refs: dict[str, str] = {}
    _known_refs(spec.get("contract"), refs)
    _known_refs(state, refs)
    private = _private_input(store, str(value.get("job_id", "")))
    _known_refs(private, refs)
    if "prompt_file" not in refs:
        prompt_path = store.inputs_root / f"{value.get('job_id')}.prompt"
        if prompt_path.is_file():
            refs["prompt_file"] = str(prompt_path)
    return {
        "prompt_file": refs.get("prompt_file"),
        "bead": refs.get("bead"),
    }


def _workspace_for_record(
    record: GenericJobRecord, workspaces: tuple[WorkspaceRecord, ...]
) -> dict[str, Any] | None:
    spec, state, checkout = _record_parts(record)
    identities = {
        value
        for value in (
            checkout.get("checkout_id"),
            spec.get("workspace_id"),
            state.get("workspace_id"),
        )
        if isinstance(value, str) and value
    }
    checkout_path = checkout.get("path")
    for workspace in workspaces:
        if workspace.workspace_id in identities:
            return workspace.to_dict()
        if isinstance(checkout_path, str) and checkout_path == str(workspace.path):
            return workspace.to_dict()
    return None


def _workspace_records(store: WorkspaceStore) -> tuple[WorkspaceRecord, ...]:
    try:
        return store.records()
    except (OSError, ValueError):
        return ()


def _phase(record: GenericJobRecord) -> str | None:
    _spec, state, _checkout = _record_parts(record)
    phase = state.get("phase")
    return phase if isinstance(phase, str) and phase else None


def _is_terminal(record: GenericJobRecord) -> bool:
    _spec, state, _checkout = _record_parts(record)
    return state.get("terminal") is True


def _bucket(record: GenericJobRecord) -> str:
    if _is_terminal(record):
        return "recent"
    if _phase(record) in {"queued", "waiting", "blocked", "dependency-wait"}:
        return "queued"
    return "active"


def _gh_pr_view(path: Path, branch: str) -> Mapping[str, Any] | None:
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                branch,
                "--json",
                "number,url,state,isDraft,mergeStateStatus,headRefOid,baseRefName",
            ],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _pr_for_workspace(
    workspace: Mapping[str, Any] | None, gh: GhLookup
) -> Mapping[str, Any] | None:
    if workspace is None:
        return None
    path = workspace.get("path")
    branch = workspace.get("branch")
    if not isinstance(path, str) or not isinstance(branch, str):
        return None
    return gh(Path(path), branch)


def _row(
    store: GenericJobStore,
    record: GenericJobRecord,
    workspaces: tuple[WorkspaceRecord, ...],
    now: datetime,
) -> dict[str, Any]:
    value = _record_dict(record)
    spec, state, _checkout = _record_parts(record)
    workspace = _workspace_for_record(record, workspaces)
    refs = _refs_for_record(store, record)
    age_seconds = _age_seconds(record, now)
    return {
        "job_id": value.get("job_id"),
        "project": spec.get("project_id"),
        "operation": spec.get("operation"),
        "kind": spec.get("kind"),
        "bucket": _bucket(record),
        "created_at": value.get("created_at"),
        "age_seconds": age_seconds,
        "age": _age_text(age_seconds),
        "phase": _phase(record),
        "terminal": state.get("terminal")
        if isinstance(state.get("terminal"), bool)
        else None,
        "bead": refs["bead"],
        "prompt_file": refs["prompt_file"],
        "workspace": workspace,
        "workspace_id": workspace.get("workspace_id") if workspace else None,
        "branch": workspace.get("branch") if workspace else None,
        "pr": None,
    }


def read_fleet(
    store: GenericJobStore,
    *,
    workspace_store: WorkspaceStore | None = None,
    limit: int = DEFAULT_FLEET_LIMIT,
    recent_hours: float = DEFAULT_RECENT_HOURS,
    gh_limit: int = DEFAULT_GH_LIMIT,
    now: datetime | None = None,
    gh: GhLookup = _gh_pr_view,
) -> dict[str, Any]:
    """Return active, queued, and recent job rows without changing state."""
    if limit < 1 or recent_hours < 0 or gh_limit < 0:
        raise ValueError("fleet limits must be non-negative, with a positive row limit")
    observed_now = now or datetime.now(UTC)
    if observed_now.tzinfo is None:
        observed_now = observed_now.replace(tzinfo=UTC)
    workspace_records = _workspace_records(
        workspace_store or WorkspaceStore(store.root)
    )
    # This is deliberately the only job-store list pass for the fleet view.
    records = store.list()
    cutoff = observed_now - timedelta(hours=recent_hours)
    selected: list[GenericJobRecord] = []
    for record in records:
        if not _is_terminal(record) or (
            (stamp := _record_timestamp(record)) is not None and stamp >= cutoff
        ):
            selected.append(record)
    selected.sort(key=lambda record: str(_record_dict(record).get("job_id", "")))
    selected.sort(
        key=lambda record: (
            _record_timestamp(record) or datetime.min.replace(tzinfo=UTC)
        ),
        reverse=True,
    )
    selected.sort(
        key=lambda record: {"active": 0, "queued": 1, "recent": 2}[_bucket(record)]
    )
    rows = [
        _row(store, record, workspace_records, observed_now)
        for record in selected[:limit]
    ]
    calls = 0
    for row in rows:
        if calls >= gh_limit:
            break
        workspace = _mapping(row.get("workspace"))
        if workspace is None:
            continue
        row["pr"] = _pr_for_workspace(workspace, gh)
        calls += 1
    counts = {
        bucket: sum(_bucket(record) == bucket for record in selected)
        for bucket in ("active", "queued", "recent")
    }
    return {
        "schema": "sinnix.agentctl.fleet.v1",
        "generated_at": observed_now.isoformat(),
        "counts": {**counts, "shown": len(rows), "records_seen": len(records)},
        "rows": rows,
    }


def _usage(record: GenericJobRecord) -> Mapping[str, Any] | None:
    _spec, state, _checkout = _record_parts(record)
    result: dict[str, Any] = {}
    for key in ("usage", "telemetry", "resource_usage"):
        if key in state:
            result[key] = state[key]
    systemd = _mapping(state.get("systemd"))
    if systemd is not None:
        fields = {
            key: systemd[key]
            for key in (
                "CPUUsageNSec",
                "MemoryPeak",
                "IOReadBytes",
                "IOWriteBytes",
                "TasksCurrent",
                "RuntimeMaxUSec",
            )
            if key in systemd
        }
        if fields:
            result["systemd"] = fields
    return result or None


def _artifact_refs(record: GenericJobRecord) -> Mapping[str, Any] | None:
    artifacts = _record_dict(record).get("artifacts")
    return dict(artifacts) if isinstance(artifacts, Mapping) else None


def _finalize_candidates(
    root: Path,
    identifier: str,
    record: GenericJobRecord | None,
    workspace: Mapping[str, Any] | None,
) -> list[Path]:
    candidates: list[Path] = []
    direct_names = (
        root / "finalize" / f"{identifier}.json",
        root / "finalize-records" / f"{identifier}.json",
        root / "saga" / f"{identifier}.json",
        root / "sagas" / f"{identifier}.json",
        root / f"finalize-{identifier}.json",
        root / f"{identifier}.finalize.json",
    )
    candidates.extend(direct_names)
    sources: list[Any] = []
    if record is not None:
        sources.extend((_record_dict(record),))
    if workspace is not None:
        sources.append(workspace)
    refs: dict[str, str] = {}

    def collect(value: Any) -> None:
        mapping = _mapping(value)
        if mapping is None:
            return
        for key, child in mapping.items():
            if _normal_key(key) in {
                "finalize_path",
                "finalize_record",
                "finalize_ref",
                "saga_path",
            } and isinstance(child, str):
                refs.setdefault("path", child)
            collect(child)

    for source in sources:
        collect(source)
    for reference in refs.values():
        path = Path(reference)
        if not path.is_absolute():
            path = root / path
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        candidates.append(path)

    verify_root = None
    if workspace and isinstance(workspace.get("path"), str):
        verify_root = Path(workspace["path"]) / ".cache" / "verify"
    if verify_root is not None and verify_root.is_dir():
        for path in verify_root.glob(f"*{identifier}*.json"):
            if any(token in path.name.lower() for token in ("final", "saga")):
                candidates.append(path)
    return list(dict.fromkeys(candidates))


def _finalize_record(
    root: Path,
    identifier: str,
    record: GenericJobRecord | None,
    workspace: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    for path in _finalize_candidates(root, identifier, record, workspace):
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, Mapping):
            return {
                "path": str(path),
                "record": dict(value),
                "saga_state": value.get(
                    "saga_state", value.get("saga", value.get("state"))
                ),
            }
    return None


def _matching_jobs(
    records: list[GenericJobRecord], workspace: Mapping[str, Any]
) -> list[GenericJobRecord]:
    workspace_id = workspace.get("workspace_id")
    workspace_path = workspace.get("path")
    result = []
    for record in records:
        _spec, _state, checkout = _record_parts(record)
        if (
            isinstance(workspace_id, str)
            and checkout.get("checkout_id") == workspace_id
        ) or (
            isinstance(workspace_path, str) and checkout.get("path") == workspace_path
        ):
            result.append(record)
    return result


def read_evidence(
    store: GenericJobStore,
    identifier: str,
    *,
    workspace_store: WorkspaceStore | None = None,
    gh_limit: int = 1,
    gh: GhLookup = _gh_pr_view,
) -> dict[str, Any]:
    """Return all locally available evidence for one job or workspace."""
    if gh_limit < 0:
        raise ValueError("gh limit must be non-negative")
    actual_workspace_store = workspace_store or WorkspaceStore(store.root)
    workspaces = _workspace_records(actual_workspace_store)
    workspace = next(
        (item.to_dict() for item in workspaces if item.workspace_id == identifier),
        None,
    )
    records: list[GenericJobRecord] = []
    if workspace is not None:
        records = _matching_jobs(store.list(), workspace)
        unit_kind = "workspace"
    else:
        try:
            records = [store.load(identifier)]
        except (JobRecordError, OSError, ValueError):
            unit_kind = "absent"
        else:
            unit_kind = "job"
        if records:
            workspace = _workspace_for_record(records[0], workspaces)
    primary = records[0] if len(records) == 1 else None
    pr = (
        _pr_for_workspace(workspace, gh) if workspace is not None and gh_limit else None
    )
    return {
        "schema": "sinnix.agentctl.evidence.v1",
        "identifier": identifier,
        "unit_kind": unit_kind,
        "record": _record_dict(primary) if primary is not None else None,
        "records": [_record_dict(record) for record in records],
        "artifact_refs": [_artifact_refs(record) for record in records],
        "usage": _usage(primary) if primary is not None else None,
        "usage_by_job": {
            str(_record_dict(record).get("job_id")): _usage(record)
            for record in records
        },
        "refs_by_job": {
            str(_record_dict(record).get("job_id")): _refs_for_record(store, record)
            for record in records
        },
        "workspace": workspace,
        "branch": workspace.get("branch") if workspace else None,
        "pr": pr,
        "saga": _finalize_record(
            store.root,
            identifier,
            primary,
            workspace,
        ),
    }


def _text(value: Any) -> str:
    if value is None or value == "":
        return ABSENT
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _pr_text(value: Mapping[str, Any] | None) -> str:
    if value is None:
        return ABSENT
    number = value.get("number")
    state = value.get("state")
    if number is not None and state:
        return f"#{number} {state}"
    if number is not None:
        return f"#{number}"
    return _text(value.get("url"))


def render_fleet(payload: Mapping[str, Any]) -> str:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return (
            "JOB  PROJECT  BEAD  PR  AGE  PHASE\n(no active, queued, or recent jobs)\n"
        )
    lines = [
        "JOB                                   PROJECT       BEAD         PR          AGE     PHASE"
    ]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"{_text(row.get('job_id')):<35} "
            f"{_text(row.get('project')):<12} "
            f"{_text(row.get('bead')):<10} "
            f"{_pr_text(_mapping(row.get('pr'))):<10} "
            f"{_text(row.get('age')):<7} "
            f"{_text(row.get('phase'))}"
        )
    return "\n".join(lines) + "\n"


def render_evidence(payload: Mapping[str, Any]) -> str:
    lines = [
        f"unit: {_text(payload.get('identifier'))} ({_text(payload.get('unit_kind'))})",
        f"record: {'present' if payload.get('record') is not None or payload.get('records') else ABSENT}",
        f"workspace: {'present' if _mapping(payload.get('workspace')) is not None else ABSENT}",
        f"branch: {_text(payload.get('branch'))}",
        f"pr: {_pr_text(_mapping(payload.get('pr')))}",
        f"saga: {'present' if payload.get('saga') is not None else ABSENT}",
    ]
    workspace = _mapping(payload.get("workspace"))
    if workspace is not None:
        lines.append(f"workspace_id: {_text(workspace.get('workspace_id'))}")
        lines.append(f"workspace_path: {_text(workspace.get('path'))}")
    refs = payload.get("refs_by_job")
    if isinstance(refs, Mapping):
        lines.append("refs:")
        for job_id, value in refs.items():
            mapping = _mapping(value) or {}
            lines.append(
                f"  {job_id}: bead={_text(mapping.get('bead'))} prompt_file={_text(mapping.get('prompt_file'))}"
            )
    artifacts = payload.get("artifact_refs")
    if isinstance(artifacts, list):
        lines.append("artifacts:")
        for value in artifacts:
            mapping = _mapping(value) or {}
            lines.append(
                f"  log={_text(mapping.get('log'))} result={_text(mapping.get('result'))} scratch={_text(mapping.get('scratch'))}"
            )
    usage = payload.get("usage")
    lines.append(
        "usage: " + (json.dumps(usage, sort_keys=True) if usage is not None else ABSENT)
    )
    if payload.get("record") is not None:
        lines.append("record_json:")
        lines.extend(
            "  " + line
            for line in json.dumps(
                payload["record"], indent=2, sort_keys=True
            ).splitlines()
        )
    if payload.get("saga") is not None:
        lines.append("saga_json:")
        lines.extend(
            "  " + line
            for line in json.dumps(
                payload["saga"], indent=2, sort_keys=True
            ).splitlines()
        )
    return "\n".join(lines) + "\n"
