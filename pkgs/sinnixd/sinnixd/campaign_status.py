"""Bounded coordinator orientation assembled from authoritative local stores."""

from __future__ import annotations

from pathlib import Path
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Mapping

from .reactor import CampaignBoard

MAX_LANES = 64
MAX_QUEUE = 32
MAX_WATCHES = 16
ERROR_MAX_AGE = timedelta(hours=24)
ACTIVE_PHASES = {
    "submitted",
    "running",
    "cancelling",
    "stopping",
    "launch-unknown",
    "observation-unknown",
    "outcome-unknown",
}
QUEUED_PHASES = {
    "queued",
    "waiting",
    "blocked",
    "dependency-wait",
    "waiting-dependencies",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _job_row(
    record: Any,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    value = record.to_dict() if hasattr(record, "to_dict") else record
    value = _mapping(value)
    return _mapping(value.get("spec")), _mapping(value.get("state")), value


def _campaign(record: Any) -> Mapping[str, Any]:
    spec, _state, _value = _job_row(record)
    return _mapping(
        _mapping(_mapping(spec.get("contract")).get("parameters")).get("campaign")
    )


def _label(record: Any) -> str | None:
    spec, _state, _value = _job_row(record)
    value = _mapping(spec.get("contract")).get("coordinator_label")
    return value if isinstance(value, str) and value else None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )


def _lane(record: Any, bucket: str, *, cause: Any = None) -> dict[str, Any]:
    spec, state, value = _job_row(record)
    checkout = _mapping(spec.get("checkout"))
    campaign = _campaign(record)
    row: dict[str, Any] = {
        "job_id": value.get("job_id"),
        "project": spec.get("project_id"),
        "group": campaign.get("group"),
        "beads": campaign.get("bead_ids", []),
        "phase": state.get("phase"),
        "workspace": checkout.get("path") or checkout.get("checkout_id"),
        "bucket": bucket,
    }
    if bucket == "queued":
        admission = _mapping(state.get("admission"))
        row["blocked_by"] = (
            list(admission.get("blocked_by", []))
            if isinstance(admission.get("blocked_by"), list)
            else []
        )
    if bucket == "wedged":
        row["cause"] = (
            cause
            or state.get("error")
            or state.get("failure")
            or state.get("phase")
            or "terminal failure"
        )
    if bucket == "unpublished":
        row["receipt_route"] = "agentctl lane publish <workspace>"
        row["judgment_owner"] = "coordinator"
    return row


def build_campaign_status(
    project_id: str,
    records: Iterable[Any],
    board: CampaignBoard,
    admission: Mapping[str, Any],
    *,
    coordinator_label: str | None = None,
    now: datetime | None = None,
    state_root: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Compose a bounded digest without retaining coordinator state."""
    all_records = [record for record in records if _campaign(record)]
    project_records = [
        record
        for record in all_records
        if _job_row(record)[0].get("project_id") == project_id
    ]
    if coordinator_label is None:
        labels = {_label(record) for record in project_records if _label(record)}
        if len(labels) == 1:
            coordinator_label = next(iter(labels))
    if coordinator_label:
        selected = [
            record for record in all_records if _label(record) == coordinator_label
        ]
    else:
        selected = project_records
    selected.sort(
        key=lambda record: str(_job_row(record)[2].get("created_at", "")), reverse=True
    )

    lanes = {"running": [], "queued": [], "wedged": [], "unpublished": []}
    for record in selected[:MAX_LANES]:
        _spec, state, _value = _job_row(record)
        phase = state.get("phase")
        if state.get("terminal") is not True and phase in QUEUED_PHASES:
            bucket = "queued"
        elif state.get("terminal") is not True or phase in ACTIVE_PHASES:
            bucket = "running"
        elif phase == "succeeded":
            bucket = "unpublished"
        else:
            bucket = "wedged"
        cause = state.get("terminal_reason") or state.get("error")
        lanes[bucket].append(_lane(record, bucket, cause=cause))
    for bucket in lanes:
        lanes[bucket] = lanes[bucket][:MAX_LANES]

    queue = [
        dict(item)
        for item in board.judgment_queue[-MAX_QUEUE:]
        if isinstance(item, Mapping)
    ]
    pools = _mapping(admission.get("pools"))
    budget = {
        name: {
            "budget_bytes": _mapping(value).get("memory_budget_bytes"),
            "occupied": len(_mapping(value).get("holders", []))
            if isinstance(_mapping(value).get("holders", []), list)
            else 0,
        }
        for name, value in sorted(pools.items())
        if isinstance(name, str)
    }
    host = _mapping(admission.get("host"))
    head = (
        _mapping(_mapping(admission).get("queue", [])[0])
        if isinstance(_mapping(admission).get("queue", []), list)
        and _mapping(admission).get("queue")
        else {}
    )
    admission_digest = {
        "budget": budget,
        "occupied_memory_bytes": host.get("occupied_memory_bytes"),
        "budget_memory_bytes": host.get("budget_memory_bytes"),
        "head_of_queue": {
            key: head.get(key)
            for key in ("job_id", "pool", "blocked_by", "position")
            if key in head
        }
        or None,
    }
    current = now or datetime.now(UTC)
    errors = []
    for item in board.errors:
        at = _timestamp(item.get("at"))
        if at is not None and current - at <= ERROR_MAX_AGE:
            errors.append(dict(item))
    watches = [
        {
            "job_id": row.get("job_id"),
            "project": row.get("project"),
            "phase": row.get("phase"),
        }
        for row in (lanes["running"] + lanes["queued"])
        if row.get("phase") in {"watching", "watch", "running"}
    ][:MAX_WATCHES]
    raw_corpus = board.corpus_health
    failures = raw_corpus.get("failures")
    failing_gate = (
        dict(failures[-1])
        if isinstance(failures, list) and failures and isinstance(failures[-1], Mapping)
        else None
    )
    corpus = {
        key: raw_corpus[key]
        for key in (
            "operation",
            "status",
            "consecutive_failures",
            "latest_job_id",
            "latest_phase",
            "updated_at",
        )
        if key in raw_corpus
    }
    corpus["failing_gate"] = failing_gate
    lanes_next: list[dict[str, Any]] = []
    master_corpus: dict[str, Any] | None = None
    if state_root is not None:
        from .lane_facts import closed_bead_ids, collect, lane_view, latest_corpus, latest_sweep_pulls

        master_corpus = latest_corpus(state_root, project_id)
        lanes_next = [
            lane_view(facts)
            for facts in collect(
                project_id,
                state_root=state_root,
                receipt_pulls=latest_sweep_pulls(state_root),
                closed_beads=closed_bead_ids(project_root, wait=False) if project_root is not None else (),
            )
        ][:MAX_LANES]
    return {
        "schema": "sinnix.agentctl.campaign-status.v1",
        "project_id": project_id,
        "master_corpus": master_corpus,
        "lanes_next": lanes_next,
        "coordinator_label": coordinator_label,
        "projects": sorted(
            {
                str(row.get("project"))
                for bucket in lanes.values()
                for row in bucket
                if row.get("project")
            }
        ),
        "lanes": lanes,
        "harvest": {"queue_depth": len(queue), "queue": queue},
        "admission": admission_digest,
        "corpus_health": corpus,
        "errors": errors[-8:],
        "background_watches": watches,
        "board_updated_at": board.updated_at,
    }
