"""Bounded coordinator orientation assembled from authoritative local stores."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from .reactor import CampaignBoard

MAX_LANES = 64
ERROR_MAX_AGE = timedelta(hours=24)


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
    """Compose a bounded digest without retaining coordinator state.

    The lane view is `lanes_next`: the facts of every managed workspace and
    the action they imply, read fresh from the same module the reactor
    dispatches from.
    """
    if coordinator_label is None:
        labels = {
            _label(record)
            for record in records
            if _campaign(record)
            and _job_row(record)[0].get("project_id") == project_id
            and _label(record)
        }
        if len(labels) == 1:
            coordinator_label = next(iter(labels))

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
    lanes_next: list[dict[str, Any]] = []
    master_corpus: dict[str, Any] | None = None
    if state_root is not None:
        from .lane_facts import (
            closed_bead_ids,
            collect,
            lane_view,
            latest_corpus,
            latest_sweep_pulls,
        )

        master_corpus = latest_corpus(state_root, project_id)
        lanes_next = [
            lane_view(facts)
            for facts in collect(
                project_id,
                state_root=state_root,
                receipt_pulls=latest_sweep_pulls(state_root),
                closed_beads=closed_bead_ids(project_root, wait=False)
                if project_root is not None
                else (),
            )
        ][:MAX_LANES]
    return {
        "schema": "sinnix.agentctl.campaign-status.v1",
        "project_id": project_id,
        "master_corpus": master_corpus,
        "lanes_next": lanes_next,
        "coordinator_label": coordinator_label,
        "admission": admission_digest,
        "errors": errors[-8:],
        "board_updated_at": board.updated_at,
    }
