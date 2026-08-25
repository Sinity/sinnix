from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from .audit import AuditService
from .beads import BeadsService
from .projects import ProjectService
from .results import derive_cursor_key

MAX_CURSOR_BYTES = 4_096
MAX_RESPONSE_BYTES = 262_144
# A cursor carries two independent owner revisions per selected project. The
# authenticated token is deliberately capped at 4 KiB, so the event scope is
# tighter than the registry-wide project bound.
MAX_EVENT_PROJECTS = 16
MAX_OWNER_REVISIONS = MAX_EVENT_PROJECTS * 2
MAX_RUNTIME_ROW_BYTES = 1_048_576


class EventCursorError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class OpaqueEventCursor:
    """A scope-bound cursor. It carries positions, never normalized event rows."""

    def __init__(self, *, principal: str, cursor_key: bytes) -> None:
        self.principal = principal
        self._key = derive_cursor_key(cursor_key, "events", principal)

    def _scope(self, projects: list[str]) -> str:
        return _digest({"principal": self.principal, "projects": sorted(projects)})

    @staticmethod
    def _initial_state() -> dict[str, Any]:
        return {
            "audit_sequence": 0,
            "runtime_offset": 0,
            "owner_revisions": {},
            "job_revision": None,
        }

    def encode(self, state: Mapping[str, Any], projects: list[str]) -> str:
        body = {"v": 1, "scope": self._scope(projects), "state": dict(state)}
        payload = base64.urlsafe_b64encode(_canonical(body)).decode().rstrip("=")
        mac = hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()
        value = f"{payload}.{mac}"
        if len(value.encode()) > MAX_CURSOR_BYTES:
            raise EventCursorError("event cursor exceeds its size bound")
        return value

    def decode(self, value: str | None, projects: list[str]) -> dict[str, Any]:
        if value is None:
            return self._initial_state()
        if (
            not isinstance(value, str)
            or len(value.encode()) > MAX_CURSOR_BYTES
            or "." not in value
        ):
            raise EventCursorError("event cursor is malformed or too large")
        payload, mac = value.rsplit(".", 1)
        expected = hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise EventCursorError("event cursor authentication failed")
        try:
            padded = payload + "=" * (-len(payload) % 4)
            body = json.loads(base64.urlsafe_b64decode(padded).decode())
        except (
            ValueError,
            json.JSONDecodeError,
            binascii.Error,
            UnicodeDecodeError,
        ) as exc:
            raise EventCursorError("event cursor is not valid JSON") from exc
        if (
            not isinstance(body, Mapping)
            or body.get("v") != 1
            or body.get("scope") != self._scope(projects)
        ):
            raise EventCursorError(
                "event cursor scope is stale or belongs to another principal"
            )
        state = body.get("state")
        if not isinstance(state, Mapping):
            raise EventCursorError("event cursor state is malformed")
        if set(state) != {
            "audit_sequence",
            "runtime_offset",
            "owner_revisions",
            "job_revision",
        }:
            raise EventCursorError("event cursor state is malformed")
        if any(
            not isinstance(state[key], int)
            or isinstance(state[key], bool)
            or state[key] < 0
            for key in ("audit_sequence", "runtime_offset")
        ):
            raise EventCursorError("event cursor position is malformed")
        owner_revisions = state["owner_revisions"]
        if (
            not isinstance(owner_revisions, Mapping)
            or len(owner_revisions) > MAX_OWNER_REVISIONS
        ):
            raise EventCursorError("event cursor owner state is too large")
        if any(
            not isinstance(key, str)
            or not isinstance(revision, str)
            or len(revision) > 256
            for key, revision in owner_revisions.items()
        ):
            raise EventCursorError("event cursor owner state is malformed")
        job_revision = state["job_revision"]
        if job_revision is not None and (
            not isinstance(job_revision, str) or len(job_revision) > 256
        ):
            raise EventCursorError("event cursor job state is malformed")
        return dict(state)


class NormalizedEventService:
    """Normalize owner evidence without creating a second event database."""

    def __init__(
        self,
        *,
        principal: str,
        cursor_key: bytes,
        projects: ProjectService,
        beads: BeadsService,
        audit: AuditService,
        transitions_path: Path,
        jobs: Callable[[int, str | None], Mapping[str, Any]] | None = None,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        self.principal = principal
        self.projects = projects
        self.beads = beads
        self.audit = audit
        self.transitions_path = transitions_path
        self.jobs = jobs
        if not 16_384 <= max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError("event response bound is outside the supported range")
        self.max_response_bytes = max_response_bytes
        self.cursor = OpaqueEventCursor(principal=principal, cursor_key=cursor_key)

    def _event(
        self,
        *,
        event_id: str,
        kind: str,
        source: str,
        source_revision: str,
        data: Mapping[str, Any],
        exact: bool,
        subject_ref: str | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "schema": "sinnix.gateway-event.v1",
            "principal": self.principal,
            "event_id": event_id,
            "kind": kind,
            "source": source,
            "source_revision": source_revision,
            "exact": exact,
            "observed_at": time.time(),
            "data": dict(data),
        }
        if subject_ref is not None:
            row["subject_ref"] = subject_ref
        return row

    def _bounded_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if len(_canonical(event)) <= min(self.max_response_bytes // 2, 65_536):
            return event
        compact = dict(event)
        compact["data"] = {
            "truncated": True,
            "original_bytes": len(_canonical(event.get("data", {}))),
            "original_digest": _digest(event.get("data", {})),
        }
        return compact

    def _fits(
        self, events: list[dict[str, Any]], sources: Mapping[str, Any], limit: int
    ) -> bool:
        payload = {
            "schema": "sinnix.gateway-events.v1",
            "principal": self.principal,
            "events": events,
            "sources": sources,
            "limit": limit,
            "truncated": True,
            "next_cursor": "x" * MAX_CURSOR_BYTES,
        }
        return len(_canonical(payload)) <= self.max_response_bytes

    def _accept(
        self,
        events: list[dict[str, Any]],
        sources: Mapping[str, Any],
        event: dict[str, Any],
        limit: int,
    ) -> bool:
        if len(events) >= limit:
            return False
        candidate = self._bounded_event(event)
        if not self._fits([*events, candidate], sources, limit):
            return False
        events.append(candidate)
        return True

    @staticmethod
    def _read_runtime_row(handle: Any) -> tuple[bytes | None, int, bool]:
        chunks: list[bytes] = []
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = handle.readline(65_536)
            if not chunk:
                return None, total, False
            total += len(chunk)
            digest.update(chunk)
            if total <= MAX_RUNTIME_ROW_BYTES:
                chunks.append(chunk)
            if chunk.endswith(b"\n"):
                if total > MAX_RUNTIME_ROW_BYTES:
                    marker = json.dumps(
                        {
                            "truncated": True,
                            "bytes": total,
                            "sha256": digest.hexdigest(),
                        }
                    ).encode()
                    return marker, total, True
                return b"".join(chunks), total, True

    def _runtime_events(
        self, offset: int, limit: int, accept: Callable[[dict[str, Any]], bool]
    ) -> tuple[int, dict[str, Any], bool]:
        try:
            with self.transitions_path.open("rb") as handle:
                handle.seek(max(0, offset))
                next_offset = offset
                while True:
                    start = handle.tell()
                    raw, _, complete = self._read_runtime_row(handle)
                    if not complete:
                        break
                    if raw is None:
                        break
                    try:
                        row = json.loads(raw)
                    except json.JSONDecodeError:
                        next_offset = handle.tell()
                        continue
                    if not isinstance(row, Mapping):
                        next_offset = handle.tell()
                        continue
                    revision = _digest(row)
                    event = self._event(
                        event_id=str(row.get("event_id") or f"offset:{start}"),
                        kind="runtime_transition",
                        source="ops-reducer.transitions",
                        source_revision=revision,
                        data=row,
                        exact=row.get("schema") == "sinnix-health-transition-v1",
                    )
                    if not accept(event):
                        return (
                            next_offset,
                            {"availability": "available", "offset": next_offset},
                            True,
                        )
                    next_offset = handle.tell()
                    if limit <= 0:
                        break
                probe = handle.read(1)
                if probe:
                    handle.seek(-1, 1)
                return (
                    next_offset,
                    {"availability": "available", "offset": next_offset},
                    bool(probe),
                )
        except OSError as exc:
            return offset, {"availability": "unavailable", "reason": str(exc)}, False

    def read(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
        project_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1_000
        ):
            raise ValueError("event limit must be 1-1000")
        selected = sorted(project_ids or self.projects.config.projects)
        if not selected or len(selected) > MAX_EVENT_PROJECTS:
            raise ValueError(
                f"event project scope must contain 1-{MAX_EVENT_PROJECTS} projects"
            )
        if any(
            project_id not in self.projects.config.projects for project_id in selected
        ):
            raise ValueError("event project scope contains an unknown project")
        state = self.cursor.decode(cursor, selected)
        events: list[dict[str, Any]] = []
        sources: dict[str, dict[str, Any]] = {}
        audit_sequence = int(state["audit_sequence"])
        owner_revisions = dict(state["owner_revisions"])
        job_revision = state["job_revision"]
        truncated = False

        audit_rows = self.audit.events_since(audit_sequence, limit)
        sources["gateway.audit"] = {
            "availability": "available",
            "last_sequence": audit_sequence,
        }
        for row in audit_rows:
            payload = row.get("payload", {})
            owner = payload.get("owner") if isinstance(payload, Mapping) else None
            kind = (
                "ops_receipt"
                if owner == "ops-reducer" or row.get("operation") == "machine.operate"
                else "gateway_receipt"
            )
            event = self._event(
                event_id=str(row["event_id"]),
                kind=kind,
                source="gateway.audit",
                source_revision=str(row["entry_hash"]),
                data=row,
                exact=True,
                subject_ref=(
                    payload.get("target_refs", [None])[0]
                    if isinstance(payload, Mapping) and payload.get("target_refs")
                    else None
                ),
            )
            event.update(
                {key: row[key] for key in ("operation", "outcome", "sequence")}
            )
            if not self._accept(events, sources, event, limit):
                truncated = True
                break
            audit_sequence = max(audit_sequence, int(row["sequence"]))
            sources["gateway.audit"]["last_sequence"] = audit_sequence
        if len(audit_rows) >= limit:
            truncated = True

        for project_id in selected:
            project_ref = f"sinnix://projects/{project_id}"
            try:
                summary = self.projects.summary(project_id)
                git_revision = _digest(summary)
                sources[f"git:{project_id}"] = {
                    "availability": "available",
                    "revision": git_revision,
                }
                key = f"git:{project_id}"
                if owner_revisions.get(key) != git_revision:
                    event = self._event(
                        event_id=f"git:{project_id}:{git_revision}",
                        kind="git_revision",
                        source="git.project",
                        source_revision=git_revision,
                        data={
                            "project_id": project_id,
                            "latest_commit": summary.get("latest_commit"),
                            "changes": summary.get("changes"),
                        },
                        exact=False,
                        subject_ref=project_ref,
                    )
                    if self._accept(events, sources, event, limit):
                        owner_revisions[key] = git_revision
                    else:
                        truncated = True
            except Exception as exc:
                sources[f"git:{project_id}"] = {
                    "availability": "unavailable",
                    "reason": str(exc),
                }
            try:
                authority = self.beads.task_authority_status(project_id)
                bead_revision = str(authority["revision"])
                sources[f"beads:{project_id}"] = {
                    "availability": "available",
                    "revision": bead_revision,
                }
                key = f"beads:{project_id}"
                if owner_revisions.get(key) != bead_revision:
                    event = self._event(
                        event_id=f"beads:{project_id}:{bead_revision}",
                        kind="owner_revision",
                        source="beads.owner",
                        source_revision=bead_revision,
                        data={
                            "project_id": project_id,
                            "revision": bead_revision,
                            "diff": authority.get("diff"),
                            "change": "owner revision changed",
                        },
                        exact=False,
                        subject_ref=f"{project_ref}/task-authority",
                    )
                    if self._accept(events, sources, event, limit):
                        owner_revisions[key] = bead_revision
                    else:
                        truncated = True
            except Exception as exc:
                sources[f"beads:{project_id}"] = {
                    "availability": "unavailable",
                    "reason": str(exc),
                }

        if self.jobs is not None and len(events) < limit:
            try:
                page = self.jobs(min(100, limit), None)
                jobs = page.get("jobs", []) if isinstance(page, Mapping) else []
                observation = {
                    "snapshot": page.get("snapshot")
                    if isinstance(page, Mapping)
                    else None,
                    "jobs": [
                        {"job_id": job.get("job_id"), "state": job.get("state")}
                        for job in jobs
                        if isinstance(job, Mapping)
                        and isinstance(job.get("job_id"), str)
                    ],
                }
                observed_revision = _digest(observation)
                sources["sinnixd.jobs"] = {
                    "availability": "available",
                    "count": len(jobs) if isinstance(jobs, list) else 0,
                    "revision": observed_revision,
                }
                if job_revision != observed_revision:
                    event = self._event(
                        event_id=f"jobs:{observed_revision}",
                        kind="job_state",
                        source="sinnixd.jobs",
                        source_revision=observed_revision,
                        data={
                            "snapshot": observation["snapshot"],
                            "jobs": observation["jobs"],
                        },
                        exact=False,
                        subject_ref="sinnix://jobs",
                    )
                    if self._accept(events, sources, event, limit):
                        job_revision = observed_revision
                    else:
                        truncated = True
                if isinstance(page, Mapping) and page.get("next_cursor"):
                    truncated = True
            except Exception as exc:
                sources["sinnixd.jobs"] = {
                    "availability": "unavailable",
                    "reason": str(exc),
                }

        runtime_offset = int(state["runtime_offset"])
        if len(events) < limit:
            runtime_offset, runtime_source, runtime_more = self._runtime_events(
                runtime_offset,
                limit - len(events),
                lambda event: self._accept(events, sources, event, limit),
            )
            sources["ops-reducer.transitions"] = runtime_source
            truncated = truncated or runtime_more
        else:
            sources["ops-reducer.transitions"] = {"availability": "not_requested"}

        next_state = {
            "audit_sequence": audit_sequence,
            "runtime_offset": runtime_offset,
            "owner_revisions": owner_revisions,
            "job_revision": job_revision,
        }
        next_cursor = self.cursor.encode(next_state, selected)
        response = {
            "schema": "sinnix.gateway-events.v1",
            "principal": self.principal,
            "events": events,
            "sources": sources,
            "next_cursor": next_cursor,
            "truncated": truncated or len(events) >= limit,
        }
        if len(_canonical(response)) > self.max_response_bytes:
            raise EventCursorError("event response exceeds its size bound")
        return response
